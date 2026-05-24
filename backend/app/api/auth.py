from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.auth import auth_enabled, create_token, get_current_user, verify_credentials

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    token: str
    username: str


class StatusResponse(BaseModel):
    enabled: bool


@router.get("/status", response_model=StatusResponse)
async def auth_status() -> StatusResponse:
    """Public — UI uses this to decide whether to show the login page at all."""
    return StatusResponse(enabled=auth_enabled())


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest) -> LoginResponse:
    if not auth_enabled():
        # If auth is disabled, hand back a token tied to the anonymous user so the
        # frontend code path stays uniform.
        return LoginResponse(token="local-dev", username="anonymous")
    if not verify_credentials(payload.username, payload.password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return LoginResponse(token=create_token(payload.username), username=payload.username)


@router.get("/me")
async def me(user: str = Depends(get_current_user)) -> dict:
    return {"username": user}
