import threading


class LogManager:
    client_lock = threading.Lock()

    def __init__(self, server_id, peers):
        self.server_id = server_id

        self.data = {}
        self.log = [{"term": 0, "message": None}] # dummy to set all log initial index & term to same

        self.voted_for = None
        self.votes_collected = {}

        self.appended_entry_record = {}

        self.current_term = 0
        self.last_log_index = 0
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

    def reset_votes(self, peers):
        for ip, port, int_port in peers:
            self.votes_collected[int_port] = False

    def term_at_index(self, prev_log_index):
        if len(self.log)-1 >= prev_log_index:
            return self.log[prev_log_index]["term"]
        else:
            return self.last_log_term

    def min_index_of_term(self, term):
        for i, entry in enumerate(self.log):
            if entry["term"] == term:
                return i
        return None
    
    def max_index_of_term(self, term):
        for i, entry in enumerate(reversed(list(self.log))):
            if entry["term"] == term:
                return i
        return None

    def check_log_index_term(self, prev_log_index, prev_log_term):
        result = False
        if len(self.log)-1 >= prev_log_index:
            if self.log[prev_log_index]["term"] == prev_log_term:
                result = True
        return result

    def delete_forward_log_entries(self, prev_log_index):
        self.log = self.log[:prev_log_index+1]

    def fetch_entries(self, index):
        return self.log[index+1:]

    def make_entry(self, message):
        return {"term": self.current_term, "message": message}

    def append_to_log(self, entry):
        print("Appending entry to log: ", entry)

        self.log.append(entry)

        self.last_log_index += 1
        self.last_log_term = entry["term"]

        print("Log after appending entry: ", self.log)

    def catch_up(self, index):
        for i, entry in enumerate(self.log[index:self.last_log_index]):
            if i != 0:
                self.commit_to_state_machine(entry)

    def commit_to_state_machine(self, entry):
        print("Committing this entry to state machine: ", entry)

        message = entry["message"]

        with self.client_lock:
            if message["type"] == "topic" and message["method"] == "PUT":
                self.set(message["topic"], [])
                print(f"Committed entry to state machine: topic <{message['topic']}> created")
                return None
            elif message["type"] == "message" and message["method"] == "PUT":
                self.append(message["topic"],message["message"])
                print(f"Committed entry to state machine: topic <{message['topic']}> updated with message <{message['message']}>")
                return None
            elif message["type"] == "message" and message["method"] == "GET":
                popped_message = self.pop(message["topic"])
                print(f"Committed entry to state machine: topic <{message['topic']}> popped message <{popped_message}>")
                return popped_message
            else:
                return None