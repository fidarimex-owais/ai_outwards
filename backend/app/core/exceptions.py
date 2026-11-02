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


class AllLLMsFailed(AppError):
    def __init__(self, session_id: str, detail: str = ""):
        self.session_id = session_id
        message = f"All LLM providers failed for session {session_id}"
        if detail:
            message += f": {detail}"
        super().__init__(message)
