from dataclasses import dataclass, asdict


@dataclass
class AppendEntries:
    term: int
    leader_id: int
    prev_log_index: int
    prev_log_term: int
    entries: list
    leader_commit: int

    def to_message(self):
        message = {"type": "heartbeat", "method": "REQ", "message": asdict(self)}
        return message

    @classmethod
    def from_message(cls, message):
        req_data = message["message"]
        req_term, req_leader_id, req_prev_log_index, req_prev_log_term, req_entries, req_leader_commit = req_data["term"], req_data["leader_id"], req_data["prev_log_index"], req_data["prev_log_term"], req_data["entries"], req_data["leader_commit"]

        return AppendEntries(
            term=req_term,
            leader_id=req_leader_id,
            prev_log_index=req_prev_log_index,
            prev_log_term=req_prev_log_term,
            entries=req_entries,
            leader_commit=req_leader_commit
        )