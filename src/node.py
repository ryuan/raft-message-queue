import zmq
import json
import sys
import time
from threading import Thread
from timer import ResettableTimer
from request_vote_rpc import RequestVote
from log_manager import LogManager


class Node:
    def __init__(self, fp, idx):
        self.ip, self.port, self.peers = self.parse_config_json(fp, idx)

        self.role = 'Follower'
        self.currentTerm = 0
        self.commitIndex = 0
        self.lastApplied = 0

        self.log_manager = LogManager(self.port)


        self.election_countdown = ResettableTimer(self.start_election)

        self.start_listening()
        self.start_follower()

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

                elif message["type"] == "status" and message["method"] == "GET":
                    socket.send_json({"role": self.role, "term": 0})
                else:
                    socket.send_json({"fatal_failure": True})

                time.sleep(0.1)

        except:
            socket.close()
            context.term()

    def start_follower(self):
        print("Node is running as a follower.")

        self.role = 'Follower'
        self.follower_thread = Thread(target=self.follower)
        self.follower_thread.start()

    def follower(self):
        self.election_countdown.start()
        print("Server started with timeout of: " + str(self.election_countdown.gen_time))

        # self.role = 'Follower'
        # self.last_update = time.time()
        # election_timeout = 5 * random.random() + 5
        
        # while time.time() - self.last_update <= election_timeout:
        #     print(time.time() - self.last_update)
        #     pass
        # self.start_election()

        # while True:
        #     self.last_update = time.time()
        #     election_timeout = 5 * random.random() + 5
            
        #     while time.time() - self.last_update <= election_timeout:
        #         pass
        #     if self.election_thread.is_alive():
        #         self.election_thread.kill()
        #     self.start_election()

    def start_election(self):
        print("Node is now a candidate.")

        self.role = 'Candidate'
        self.election_thread = Thread(target=self.candidate)
        self.election_thread.start()

    def candidate(self):
        print("I'm going to collect votes")

        self.election_countdown.reset()
        print("Election started with timeout of: " + str(self.election_countdown.gen_time))

        self.broadcast(RequestVote(
            self.log_manager.current_term, 
            self.port, 
            self.log_manager.last_log_index, 
            self.log_manager.last_log_term).to_message()
            )

    def broadcast(self, message):
        print("Broadcasting vote request message to peers:", message)
        print("Identified peers: ", self.peers)

        peer_context = zmq.Context()

        for ip, port in self.peers:
            print(port)
            peer_socket = peer_context.socket(zmq.REQ)
            peer_socket.connect(f"tcp://{ip}:{port}")

            try:
                print(f"Sending vote request to port {port}")
                peer_socket.send_json(message)
                time.sleep(0.5)
                peer_socket.close()
            except Exception as e:
                print("Closing socket due to error ", str(e))
                peer_socket.close()

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
