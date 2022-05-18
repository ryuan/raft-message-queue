import threading
import os


class LogManager:
    client_lock = threading.Lock()

    def __init__(self, server_id, peers):
        self.server_id = server_id

        self.data = {}
        self.log = []

        self.voted_for = None
        self.votes_collected = {}

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