import zmq
import json
import sys
import time
from threading import Thread

from timer import ResettableTimer
from log_manager import LogManager
from request_vote_rpc import RequestVote
from append_entries_rpc import AppendEntries


class Node:
    def __init__(self, fp, idx):
        self.ip, self.port, self.peers = self.parse_config_json(fp, idx)

        self.role = 'Follower'

        self.commit_index = 0
        self.last_applied = 0

        self.log_manager = LogManager(self.port, self.peers)

        self.election_countdown = ResettableTimer(self.start_election)
        self.heartbeat_countdown = None

        self.start_listening()
        self.follower()

    def start_listening(self):
        self.listener_thread = Thread(target=self.listen, args=(self.ip, self.port))
        self.listener_thread.start()

    def listen(self, ip, port):
        context = zmq.Context()
        socket = context.socket(zmq.REP)

        socket.setsockopt(zmq.LINGER, 0)
        socket.bind(f"tcp://{ip}:{port}")
        print(f"Bound to server on port {port}")

        try:
            while True:
                message = socket.recv_json()
                print("Received message: ", message)

                if message["type"] == "vote" or message["type"] == "heartbeat":
                    self.respond_server(socket, message)
                else:
                    self.respond_client(socket, message)

                time.sleep(1e-5)
        except:
            socket.close()
            context.term()

    def follower(self):
        print("\nNode is running as a follower.")

        self.role = 'Follower'
        self.heartbeat_countdown = None

        self.election_countdown.reset()
        print("Election timer started with timeout of: " + str(self.election_countdown.gen_time))

        self.log_manager.voted_for = None

    def start_election(self):
        print("\nNode started an election and will now collect votes.")

        self.log_manager.current_term += 1
        self.log_manager.reset_votes(self.peers)

        self.candidate()

    def candidate(self):
        print("Node is running as a candidate.")

        self.role = 'Candidate'
        self.election_countdown.reset()
        print("Election timer started with timeout of: " + str(self.election_countdown.gen_time))

        self.log_manager.voted_for = self.port
        self.process_vote(self.port)

        if self.role != 'Leader':
            self.broadcast(
                RequestVote(
                    term=self.log_manager.current_term, 
                    candidate_id=self.port, 
                    last_log_index=self.log_manager.last_log_index, 
                    last_log_term=self.log_manager.last_log_term
                ).to_message()
            )

    def leader(self):
        print("\nNode is running as a leader.")

        self.role = 'Leader'

        self.election_countdown.stop()

        self.heartbeat()

    def heartbeat(self):
        self.broadcast(
            AppendEntries(
                term=self.log_manager.current_term,
                leader_id=self.port,
                prev_log_index=self.log_manager.last_log_index,
                prev_log_term=self.log_manager.last_log_term,
                entries=[],
                leader_commit=self.commit_index
            ).to_message()
        )

        self.heartbeat_countdown = ResettableTimer(self.heartbeat, interval_lb=1000, interval_ub=1200)
        self.heartbeat_countdown.start()
        print("Heartbeat timer started with timeout of: " + str(self.heartbeat_countdown.gen_time))

    def broadcast(self, message):
        print("Broadcasting request message to peers:", message)
        print("Identified peers: ", self.peers)

        peer_context = zmq.Context()

        for ip, port in self.peers:
            peer_socket = peer_context.socket(zmq.REQ)
            peer_socket.connect(f"tcp://{ip}:{port}")

            try:
                print(f"Sending request to port {port}")
                peer_socket.send_json(message)
                peer_socket.close()
            except Exception as e:
                print("Closing socket due to error ", str(e))
                peer_socket.close()

    def respond_server(self, socket, message):
        if message["type"] == "vote" and message["method"] == "REQ":
            request = RequestVote.from_message(message)

            if (request.term > self.log_manager.current_term 
                and request.last_log_index >= self.log_manager.last_log_index 
                and request.last_log_term >= self.log_manager.last_log_term
                and (self.log_manager.voted_for == None or self.log_manager.voted_for == request.candidate_id)):
                result = {"port": self.port, "term": self.log_manager.current_term, "vote": True}
            else:
                result = {"port": self.port, "term": self.log_manager.current_term, "vote": False}

            response = {"type": "vote", "method": "RES", "message": result}
            socket.send_json(response)

            self.log_manager.voted_for = request.candidate_id
            self.send_result(request.candidate_id, response)
        elif message["type"] == "vote" and message["method"] == "RES":
            v_port, v_term, vote = message["message"]["port"], message["message"]["term"], message["message"]["vote"]

            if vote == True:
                self.process_vote(v_port)
            else:
                pass

            socket.send_json("ok")
        elif message["type"] == "heartbeat" and message["method"] == "REQ":
            request = AppendEntries.from_message(message)

            if request.term < self.log_manager.current_term:
                result = {"port": self.port, "term": self.log_manager.current_term, "success": False}
            else:
                self.follower()
                if self.heartbeat_countdown:
                    self.heartbeat_countdown = None
                self.log_manager.current_term = request.term

                # need to update log and data
                pass

                result = {"term": self.log_manager.current_term, "success": True}

            response = {"type": "heartbeat", "method": "RES", "message": result}
            socket.send_json(response)

            self.send_result(request.leader_id, response)
        elif message["type"] == "heartbeat" and message["method"] == "RES":
            f_term, f_success = message["message"]["term"], message["message"]["success"]

            # double check that term from response is higher
            if f_success == False and f_term > self.log_manager.current_term:
                # need to update log and data to term
                pass

            socket.send_json("ok")

    def send_result(self, rec_port, message):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)

        for ip, port in self.peers:
            if port == rec_port:
                socket.connect(f"tcp://{ip}:{rec_port}")

        socket.send_json(message)
        print(f"Sent result to {rec_port}: {message}")

        response = socket.recv_json()
        print(f"Received response from {rec_port}: {response}")

    def process_vote(self, port):
        self.log_manager.votes_collected[port] = True

        count_trues = len(list(filter(lambda x: x is True, self.log_manager.votes_collected.values())))
        count_falses = len(list(filter(lambda x: x is False, self.log_manager.votes_collected.values())))

        print(count_trues)
        print(count_falses)
        if count_trues >= count_falses:
            print("Node wins election for term ", str(self.log_manager.current_term))

            self.log_manager.reset_votes(self.peers)
            self.leader()

    def respond_client(self, socket, message):
        if message["type"] == "status" and message["method"] == "GET":
            socket.send_json({"role": self.role, "term": self.log_manager.current_term})

        elif self.role == 'Leader':
            if message["type"] == "topic" and message["method"] == "PUT":
                if message["topic"] not in self.log_manager.keys() and isinstance(message["topic"], str):
                    self.log_manager.set(message["topic"], [])
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "topic" and message["method"] == "GET":
                socket.send_json({"success": True, "topics": self.log_manager.keys()})

            elif message["type"] == "message" and message["method"] == "PUT":
                if message["topic"] in self.log_manager.keys() and isinstance(message["topic"], str) and isinstance(message["message"], str):
                    self.log_manager.append(message["topic"], message["message"])
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "message" and message["method"] == "GET":
                if isinstance(message["topic"], str) and self.log_manager.data.get(message["topic"]):
                    socket.send_json({"success": True, "message": self.log_manager.pop(message["topic"])})
                else:
                    socket.send_json({"success": False})
        else:
            socket.send_json({"success": False})

    def parse_config_json(self, fp, idx):
        config_json = json.load(open(fp))

        my_ip, my_port = None, None
        peers = []
        for i, address in enumerate(config_json["addresses"]):
            ip, port = address["ip"], address["port"]
            if i == idx:
                my_ip, my_port = ip, port
            else:
                peers.append((ip, port))

        return my_ip, my_port, peers


if __name__ == "__main__":
    config_json_fp = sys.argv[1]
    config_json_idx = int(sys.argv[2])

    Node(config_json_fp, config_json_idx)
