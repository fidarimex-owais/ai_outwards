import redis

from app.core.config import settings
from app.core.exceptions import InvalidCredentials, TooManyLoginAttempts
from app.core.security import _DUMMY_HASH, create_access_token, verify_password
from app.features.auth.repository import get_password_hash
from app.features.auth.schemas import TokenResponse


def _rate_limit_key(username: str, client_ip: str) -> str:
    # Scoped to (client_ip, username), not username alone: a username-only counter lets
    # anyone who knows (or guesses) a real username lock that account out for everyone by
    # deliberately sending wrong passwords from anywhere - a denial-of-service on the
    # legitimate user, not a thing brute-force throttling should cause. Scoping to the caller's
    # own IP means an attacker can only ever exhaust their own attempt budget; a legitimate
    # user signing in from their own IP is unaffected by that attacker's failed attempts.
    return f"login_attempts:{client_ip}:{username}"


def login(username: str, password: str, redis_client: redis.Redis, client_ip: str = "unknown") -> TokenResponse:
    attempts_key = _rate_limit_key(username, client_ip)
    attempts = int(redis_client.get(attempts_key) or 0)
    if attempts >= settings.login_rate_limit_attempts:
        raise TooManyLoginAttempts(username)

    password_hash = get_password_hash(username)
    # Always run verify_password, even for an unknown username (against a dummy hash) -
    # otherwise an unknown username returns immediately while a known one takes a full bcrypt
    # verify, letting response timing be used to enumerate valid usernames.
    is_valid = verify_password(password, password_hash or _DUMMY_HASH)
    if password_hash is None or not is_valid:
        pipe = redis_client.pipeline()
        pipe.incr(attempts_key)
        pipe.expire(attempts_key, settings.login_rate_limit_window_seconds)
        pipe.execute()
        raise InvalidCredentials()

    redis_client.delete(attempts_key)
    token = create_access_token(subject=username)
    return TokenResponse(access_token=token)
