from enum import Enum


class SessionState(str, Enum):
    IDLE = "IDLE"
    COLLECTING = "COLLECTING"
    CLARIFICATION = "CLARIFICATION"
    AWAITING_CONFIRMATION = "AWAITING_CONFIRMATION"
    SAVING = "SAVING"
    COMPLETED = "COMPLETED"
    PAUSED = "PAUSED"  # all LLM providers failed; conversation preserved in Redis, user asked to retry
