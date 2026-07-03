import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any


def _b64encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("utf-8").rstrip("=")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def create_signed_token(payload: dict[str, Any], secret_key: str, minutes: int) -> str:
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    token_payload = {**payload, "exp": int(expires_at.timestamp())}
    body = _b64encode(json.dumps(token_payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def verify_signed_token(token: str, secret_key: str) -> dict[str, Any] | None:
    try:
        body, signature = token.split(".", 1)
        expected = hmac.new(secret_key.encode("utf-8"), body.encode("utf-8"), hashlib.sha256).digest()
        if not hmac.compare_digest(_b64decode(signature), expected):
            return None

        payload = json.loads(_b64decode(body))
        if int(payload.get("exp", 0)) < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except Exception:
        return None


def generate_candidate_token() -> str:
    return f"cand_{secrets.token_urlsafe(32)}"


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt}${digest.hex()}"


def verify_password(password: str, stored_password: str) -> bool:
    if stored_password.startswith("pbkdf2_sha256$"):
        try:
            _, salt, digest = stored_password.split("$", 2)
            candidate = hashlib.pbkdf2_hmac(
                "sha256",
                password.encode("utf-8"),
                salt.encode("utf-8"),
                120_000,
            ).hex()
            return hmac.compare_digest(candidate, digest)
        except ValueError:
            return False

    return hmac.compare_digest(password, stored_password)
