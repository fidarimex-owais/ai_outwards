from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.features.auth.schemas import TokenResponse
from app.features.auth.service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login_route(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    # OAuth2PasswordRequestForm (not a plain JSON body) so the /docs "Authorize" button works.
    return login(form_data.username, form_data.password)
