from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.config import get_settings
from app.core.security import create_signed_token, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class AdminLoginRequest(BaseModel):
    username: str
    password: str


@router.post("/admin/login")
def login_admin(request: AdminLoginRequest):
    settings = get_settings()
    stored_password = settings.admin_password_hash or settings.admin_password

    if not settings.admin_auth_configured or not stored_password or not settings.auth_secret_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )

    if request.username != settings.admin_username or not verify_password(
        request.password,
        stored_password,
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin credentials",
        )

    token = create_signed_token(
        {"role": "admin", "username": settings.admin_username},
        settings.auth_secret_key,
        settings.auth_token_minutes,
    )

    return {
        "role": "admin",
        "username": settings.admin_username,
        "access_token": token,
        "token_type": "bearer",
    }
