class AppError(Exception):
    """Base class for all application-raised errors."""


class SessionNotFound(AppError):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session not found: {session_id}")


class SessionExpired(AppError):
    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"Session expired: {session_id}")


class InvalidTransition(AppError):
    def __init__(self, current_state: str, attempted_event: str):
        self.current_state = current_state
        self.attempted_event = attempted_event
        super().__init__(
            f"Cannot handle '{attempted_event}' while session is in state '{current_state}'"
        )


class InvalidCredentials(AppError):
    def __init__(self):
        super().__init__("Invalid username or password")


class UnknownField(AppError):
    def __init__(self, field_key: str):
        self.field_key = field_key
        super().__init__(f"Unknown field key: {field_key}")


class TooManyLoginAttempts(AppError):
    def __init__(self, username: str):
        self.username = username
        super().__init__(f"Too many failed login attempts for {username}")


class AllLLMsFailed(AppError):
    def __init__(self, session_id: str, detail: str = ""):
        self.session_id = session_id
        message = f"All LLM providers failed for session {session_id}"
        if detail:
            message += f": {detail}"
        super().__init__(message)


class ExtractionParseFailed(AppError):
    """The LLM responded (no outage - AllLLMsFailed doesn't apply), but its response wasn't
    valid JSON. Distinct from a field being genuinely ambiguous: that's the LLM's judgment
    call on the answer's content, this is the response itself being unusable. Without this
    distinction, a single malformed response silently marks every field ambiguous, which looks
    indistinguishable from the user having said nothing - instead this should surface as a
    clear "please try again," not a silent, unexplained reset."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        super().__init__(f"LLM response was not valid JSON for session {session_id}")
