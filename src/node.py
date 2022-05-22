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
        self.ip, self.port, self.int_port, self.peers = self.parse_config_json(fp, idx)

        self.role = 'Follower'

        self.appended_entry_record = {}
        self.current_entry = None
        self.current_entry_committed = False
        self.popped_message = None

        self.commit_index = 0
        self.last_applied = 0

        self.latest_leader = None

        self.log_manager = LogManager(self.int_port, self.peers)

        self.election_countdown = ResettableTimer(self.start_election)
        self.heartbeat_countdown = None

        self.reset_appended_entry_record()
        self.start_listening()
        self.follower()

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

        self.log_manager.voted_for = self.int_port
        self.process_vote(self.int_port)

        if self.role != 'Leader':
            self.broadcast(
                RequestVote(
                    term=self.log_manager.current_term, 
                    candidate_id=self.int_port, 
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
                leader_id=self.int_port,
                prev_log_index=self.log_manager.last_log_index,
                prev_log_term=self.log_manager.last_log_term,
                entries=[],
                leader_commit=self.commit_index
            ).to_message()
        )

        self.heartbeat_countdown = ResettableTimer(self.heartbeat, interval_lb=4000, interval_ub=4000)
        self.heartbeat_countdown.start()
        print("Heartbeat timer started with timeout of: " + str(self.heartbeat_countdown.gen_time))

    def broadcast(self, message):
        print("Broadcasting request message to peers:", message)
        print("Identified peers: ", self.peers)

        peer_context = zmq.Context().instance()

        for ip, port, int_port in self.peers:
            peer_socket = peer_context.socket(zmq.REQ)
            # peer_socket.setsockopt(zmq.LINGER, 0)
            peer_socket.connect(f"tcp://{ip}:{int_port}")

            try:
                print(f"Sending request to port {int_port}")
                peer_socket.send_json(message)
                time.sleep(1e-5)
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
                result = {"port": self.int_port, "term": self.log_manager.current_term, "vote": True}
            else:
                result = {"port": self.int_port, "term": self.log_manager.current_term, "vote": False}

            response = {"type": "vote", "method": "RES", "message": result}
            socket.send_json(response)

            self.log_manager.voted_for = request.candidate_id
            self.send_message(request.candidate_id, response)
        elif message["type"] == "vote" and message["method"] == "RES":
            v_port, v_term, vote = message["message"]["port"], message["message"]["term"], message["message"]["vote"]

            if vote == True:
                if self.role != "Leader":
                    self.process_vote(v_port)
            else:
                pass

            socket.send_json("ok")
        elif message["type"] == "append" and message["method"] == "REQ":
            request = AppendEntries.from_message(message)

            term_at_req_index = self.log_manager.term_at_index(request.prev_log_index)
            min_index_of_term = self.log_manager.min_index_of_term(term_at_req_index)

            if request.term < self.log_manager.current_term:
                result = {"port": self.int_port, "term": self.log_manager.current_term, "earliest_index_of_term": min_index_of_term, "max_term_at_tried_index": term_at_req_index, "success": False}
            else:
                self.follower()
                if self.heartbeat_countdown:
                    self.heartbeat_countdown = None
                    
                self.log_manager.current_term = request.term
                self.latest_leader = request.leader_id
                
                if self.log_manager.check_log_index_term(request.prev_log_index, request.prev_log_term):
                    self.log_manager.delete_forward_log_entries(request.prev_log_index)

                    for entry in request.entries:
                        self.log_manager.append_to_log(entry)

                    if request.leader_commit > self.commit_index:
                        self.commit_index = min(request.leader_commit, self.log_manager.last_log_index)

                    if self.commit_index > self.last_applied:
                        self.commit_past_entries(self.last_applied, self.commit_index)

                    result = {"port": self.int_port, "term": self.log_manager.current_term, "earliest_index_of_term": min_index_of_term, "max_term_at_tried_index": term_at_req_index, "success": True}
                else:
                    result = {"port": self.int_port, "term": self.log_manager.current_term, "earliest_index_of_term": min_index_of_term, "max_term_at_tried_index": term_at_req_index, "success": False}

            response = {"type": "append", "method": "RES", "message": result}
            socket.send_json(response)

            self.send_message(request.leader_id, response)
        elif message["type"] == "append" and message["method"] == "RES":
            r_port, r_term, r_min_term_index, r_indexed_term, r_success = message["message"]["port"], message["message"]["term"], message["message"]["earliest_index_of_term"], message["message"]["max_term_at_tried_index"], message["message"]["success"]

            if r_success == True:
                if self.current_entry is not None:
                    self.process_appended_entry(r_port)
            elif r_term > self.log_manager.current_term:
                self.log_manager.current_term = r_term
                self.cleanup()
                self.follower()
            else:
                if self.log_manager.max_index_of_term(r_indexed_term) is not None:
                    new_attempt_index = self.log_manager.max_index_of_term(r_indexed_term)
                else:
                    new_attempt_index = r_min_term_index - 1
                new_attempt_term = self.log_manager.log[new_attempt_index]["term"]
                new_attempt_entries = self.log_manager.fetch_entries(new_attempt_index)

                message = AppendEntries(
                    term=self.log_manager.current_term,
                    leader_id=self.int_port,
                    prev_log_index=new_attempt_index,
                    prev_log_term=new_attempt_term,
                    entries=[new_attempt_entries],
                    leader_commit=self.commit_index
                ).to_message()

                self.send_message(r_port, message)

            socket.send_json("ok")
        elif message["type"] == "commit" and message["method"] == "REQ":
            if message["success"] == True:
                self.commit_past_entries(self.last_applied, self.commit_index+1)

            socket.send_json("ok")

    def send_message(self, rec_port, message):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)

        for ip, port, int_port in self.peers:
            if int_port == rec_port:
                socket.connect(f"tcp://{ip}:{rec_port}")

        try:
            socket.send_json(message)
            print(f"Sent result to {rec_port}: {message}")
            time.sleep(1e-5)

            response = socket.recv_json()
            print(f"Received response from {rec_port}: {response}")

            socket.close()
        except Exception as e:
            print("Closing socket due to error ", str(e))
            socket.close()

    def process_vote(self, port):
        self.log_manager.votes_collected[port] = True

        count_trues = len(list(filter(lambda x: x is True, self.log_manager.votes_collected.values())))
        count_falses = len(list(filter(lambda x: x is False, self.log_manager.votes_collected.values())))

        if count_trues >= count_falses:
            print("Node wins election for term ", str(self.log_manager.current_term))

            self.leader()
            self.log_manager.reset_votes(self.peers)

    def process_appended_entry(self, port):
        self.appended_entry_record[port] = True

        count_trues = len(list(filter(lambda x: x is True, self.appended_entry_record.values())))
        count_falses = len(list(filter(lambda x: x is False, self.appended_entry_record.values())))

        if count_trues >= count_falses:
            print("Committing entry: ", self.current_entry)

            self.commit_past_entries(self.last_applied, self.log_manager.last_log_index)
            self.popped_message = self.log_manager.commit_to_state_machine(self.current_entry)

            self.current_entry_committed = True
            message = {"type": "commit", "method": "REQ", "success": True}
            self.broadcast(message)

            self.current_entry = None
            self.current_entry_committed = False
            
            self.reset_appended_entry_record()

    def commit_past_entries(self, start_i, end_i):
        self.log_manager.catch_up(start_i, end_i)
        self.commit_index = min(self.commit_index, end_i)
        self.last_applied = self.commit_index

    def reset_appended_entry_record(self):
        for ip, port, int_port in self.peers:
            self.appended_entry_record[int_port] = False

    def respond_client(self, socket, message):
        if message["type"] == "status" and message["method"] == "GET":
            socket.send_json({"role": self.role, "term": self.log_manager.current_term})

        elif self.role == 'Leader':
            if message["type"] == "topic" and message["method"] == "PUT":
                if message["topic"] not in self.log_manager.keys() and isinstance(message["topic"], str):
                    self.update_logs(message)
                    # self.log_manager.set(message["topic"], [])
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "topic" and message["method"] == "GET":
                socket.send_json({"success": True, "topics": self.log_manager.keys()})

            elif message["type"] == "message" and message["method"] == "PUT":
                if message["topic"] in self.log_manager.keys() and isinstance(message["topic"], str) and isinstance(message["message"], str):
                    self.update_logs(message)
                    # self.log_manager.append(message["topic"], message["message"])
                    socket.send_json({"success": True})
                else:
                    socket.send_json({"success": False})
            elif message["type"] == "message" and message["method"] == "GET":
                if isinstance(message["topic"], str) and self.log_manager.data.get(message["topic"]):
                    self.update_logs(message)
                    socket.send_json({"success": True, "message": self.popped_message})
                else:
                    socket.send_json({"success": False})

        elif self.role != 'Leader':
            self.send_message(self.latest_leader, message)

        else:
            socket.send_json({"success": False})

    def update_logs(self, message):
        log_entry = self.log_manager.make_entry(message)
        self.current_entry = log_entry
        self.log_manager.append_to_log(log_entry)

        prev_log_index = self.log_manager.last_log_index - 1 # reverse the increment from appending to leader's log

        self.broadcast(
            AppendEntries(
                term=self.log_manager.current_term,
                leader_id=self.int_port,
                prev_log_index=prev_log_index,
                prev_log_term=self.log_manager.log[prev_log_index]["term"],
                entries=[log_entry],
                leader_commit=self.commit_index
            ).to_message()
        )

        while not self.current_entry_committed:
            pass

    def start_listening(self):
        self.server_listener_thread = Thread(target=self.s_listen, args=())
        self.server_listener_thread.start()

        self.client_listener_thread = Thread(target=self.c_listen, args=())
        self.client_listener_thread.start()

    def s_listen(self):
        context = zmq.Context()
        s_socket = context.socket(zmq.REP)
        s_socket.setsockopt(zmq.LINGER, 0)
        s_socket.bind(f"tcp://{self.ip}:{self.int_port}")
        print(f"Bound to servers on port {self.int_port}")

        try:
            while True:
                message = s_socket.recv_json()
                print("Received message: ", message)
                self.respond_server(s_socket, message)
                time.sleep(1e-5)
        except:
            s_socket.close()
            context.term()

    def c_listen(self):
        context = zmq.Context()
        c_socket = context.socket(zmq.REP)
        c_socket.setsockopt(zmq.LINGER, 0)
        c_socket.bind(f"tcp://{self.ip}:{self.port}")
        print(f"Bound to clients on port {self.port}")

        try:
            while True:
                message = c_socket.recv_json()
                print("Received message: ", message)
                self.respond_client(c_socket, message)
                time.sleep(1e-5)
        except:
            c_socket.close()
            context.term()

    def cleanup(self):
        self.reset_appended_entry_record()
        self.current_entry = None
        self.current_entry_committed = False
        self.popped_message = None
        self.heartbeat_countdown = None

    def parse_config_json(self, fp, idx):
        config_json = json.load(open(fp))

        my_ip, my_port, my_int_port = None, None, None
        peers = []
        for i, address in enumerate(config_json["addresses"]):
            ip, port, int_port = address["ip"], address["port"], address["internal_port"]
            if i == idx:
                my_ip, my_port, my_int_port = ip, port, int_port
            else:
                peers.append((ip, port, int_port))

        return my_ip, my_port, my_int_port, peers


if __name__ == "__main__":
    config_json_fp = sys.argv[1]
    config_json_idx = int(sys.argv[2])

    Node(config_json_fp, config_json_idx)
