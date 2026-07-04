from typing import Annotated
from datetime import datetime

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import hash_token, verify_signed_token
from app.db.session import get_db
from app.models.auth import CandidateAccessToken


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing auth token",
        )
    return authorization.split(" ", 1)[1].strip()


def require_admin(
    authorization: Annotated[str | None, Header()] = None,
) -> dict:
    settings = get_settings()
    if not settings.admin_auth_configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin authentication is not configured",
        )

    token = _bearer_token(authorization)
    payload = verify_signed_token(token, settings.auth_secret_key)

    if payload is None or payload.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )

    return payload


def require_candidate(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> CandidateAccessToken:
    token = _bearer_token(authorization)
    access_token = (
        db.query(CandidateAccessToken)
        .filter(CandidateAccessToken.token_hash == hash_token(token))
        .first()
    )

    if access_token is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate access required",
        )

    if access_token.expires_at < datetime.utcnow():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Candidate access token expired",
        )

    return access_token
