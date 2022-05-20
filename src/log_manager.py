import threading
import os
from urllib import response


class LogManager:
    client_lock = threading.Lock()

    def __init__(self, server_id, peers):
        self.server_id = server_id

        self.data = {}
        self.log = []

        self.voted_for = None
        self.votes_collected = {}

        self.appended_entry_record = {}

        self.current_term = 0
        self.last_log_index = 1
        self.last_log_term = 0

        self.reset_votes(peers)

    def keys(self):
        return list(self.data.keys())

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value

    def append(self, key, value):
        self.data[key].append(value)

    def pop(self, key):
        return self.data.get(key).pop(0)

    def delete(self, key):
        del self.data[key]

    def reset_votes(self, peers):
        for ip, port in peers:
            self.votes_collected[port] = False

    def commit_to_state_machine(self, entry):
        print("Committing this entry to state machine: ", entry)

        final_entry = {"index": self.last_log_index, "term": self.last_log_term, "entry": entry}

        with self.client_lock:
            if entry["type"] == "topic" and entry["method"] == "PUT":
                self.log.append(final_entry)
                self.set(entry["topic"], [])
                response = f"Committed entry to state machine: topic <{entry['topic']}> created"
            elif entry["type"] == "message" and entry["method"] == "PUT":
                self.log.append(final_entry)
                self.append(entry["topic"],entry["message"])
                response = f"Committed entry to state machine: topic <{entry['topic']}> updated with message <{entry['message']}>"
            elif entry["type"] == "message" and entry["method"] == "GET":
                self.log.append(final_entry)
                popped_message = self.pop(entry["topic"])
                response = f"Committed entry to state machine: topic <{entry['topic']}> popped message <{popped_message}>"
            else:
                pass

        return response