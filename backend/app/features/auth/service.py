from app.core.exceptions import InvalidCredentials
from app.core.security import create_access_token, verify_password
from app.features.auth.repository import get_password_hash
from app.features.auth.schemas import TokenResponse


def login(username: str, password: str) -> TokenResponse:
    password_hash = get_password_hash(username)
    if password_hash is None or not verify_password(password, password_hash):
        raise InvalidCredentials()

    token = create_access_token(subject=username)
    return TokenResponse(access_token=token)
