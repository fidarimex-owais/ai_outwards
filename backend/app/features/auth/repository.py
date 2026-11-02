from app.core.config import settings


def _parse_operators(raw: str) -> dict[str, str]:
    operators = {}
    for pair in raw.split(";"):
        pair = pair.strip()
        if not pair:
            continue
        username, _, password_hash = pair.partition(":")
        if username and password_hash:
            operators[username.strip()] = password_hash.strip()
    return operators


def get_password_hash(username: str) -> str | None:
    """Looks up the bcrypt hash for a username from the static OPERATOR_CREDENTIALS config
    value. Re-parses on every call (cheap, a handful of entries) so a changed .env takes
    effect on restart without extra caching logic to invalidate."""
    operators = _parse_operators(settings.operator_credentials)
    return operators.get(username)
