from fastapi import APIRouter, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm
from redis import Redis

from app.core.redis import get_redis
from app.features.auth.schemas import TokenResponse
from app.features.auth.service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), redis_client: Redis = Depends(get_redis)
) -> TokenResponse:
    # OAuth2PasswordRequestForm (not a plain JSON body) so the /docs "Authorize" button works.
    # request.client.host, not an X-Forwarded-For header: this app has no documented reverse
    # proxy in front of it, and trusting a client-supplied header for rate-limit scoping would
    # let an attacker simply forge a different IP on every request, defeating the limiter
    # entirely. If this is ever deployed behind a trusted proxy, that proxy's IP would become
    # the only "client" the limiter sees - a deployment detail to revisit then, not a code bug.
    client_ip = request.client.host if request.client else "unknown"
    return login(form_data.username, form_data.password, redis_client, client_ip)
