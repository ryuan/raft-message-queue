from dataclasses import dataclass, asdict


@dataclass
class RequestVote:
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int

    def to_message(self):
        message = {"type": "vote", "method": "REQ", "message": asdict(self)}
        return message

    @classmethod
    def from_message(cls, message):
        req_data = message["message"]
        req_term, req_id, req_last_log_index, req_last_log_term = req_data["term"], req_data["candidate_id"], req_data["last_log_index"], req_data["last_log_term"]

        return RequestVote(
            term=req_term,
            candidate_id=req_id,
            last_log_index=req_last_log_index,
            last_log_term=req_last_log_term,
        )