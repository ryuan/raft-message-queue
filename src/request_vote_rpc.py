from dataclasses import dataclass, asdict


@dataclass
class RequestVote:
    term: int
    candidate_id: int
    last_log_index: int
    last_log_term: int

    def to_message(self):
        return asdict(self)

    @classmethod
    def from_message(cls, message):
        numeric_markers = message.replace("can_I_count_on_your_vote_in_term ", "").split(" ")
        current_term, index, latest_log_term = int(numeric_markers[0]), int(numeric_markers[3]), int(numeric_markers[4])

        return RequestVote(
            term=current_term,
            last_log_index=index,
            last_log_term=latest_log_term,
        )