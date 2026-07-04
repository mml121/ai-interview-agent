import json
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import generate_candidate_token, hash_token
from app.db.session import get_db
from app.models.auth import CandidateAccessToken
from app.models.candidate import Candidate
from app.services.profile_extractor import extract_candidate_profile, profile_to_json
from app.services.resume_parser import extract_resume_text

router = APIRouter(prefix="/api/resume", tags=["resume"])

SUPPORTED_EXTENSIONS = {".pdf", ".txt", ".docx"}
MAX_FORM_FIELD_CHARS = 120


def clean_required_field(value: str, field_name: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if len(cleaned) > MAX_FORM_FIELD_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"{field_name} must be {MAX_FORM_FIELD_CHARS} characters or less",
        )
    return cleaned


def upload_directory() -> Path:
    settings = get_settings()
    configured_dir = Path(settings.upload_dir)
    if not configured_dir.is_absolute():
        configured_dir = Path(__file__).resolve().parents[3] / configured_dir

    resolved_dir = configured_dir.resolve()
    resolved_dir.mkdir(parents=True, exist_ok=True)
    return resolved_dir


async def save_upload_with_limit(file: UploadFile, saved_path: Path, max_bytes: int) -> None:
    total_bytes = 0

    with saved_path.open("wb") as output:
        while chunk := await file.read(1024 * 1024):
            total_bytes += len(chunk)
            if total_bytes > max_bytes:
                raise HTTPException(status_code=413, detail="Resume file is too large")
            output.write(chunk)


@router.post("/upload")
async def upload_resume(
    name: str = Form(...),
    role_applied: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    candidate_name = clean_required_field(name, "Candidate name")
    target_role = clean_required_field(role_applied, "Role applied for")
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT resumes are supported")

    upload_dir = upload_directory()
    saved_path = upload_dir / f"{uuid4()}{suffix}"

    try:
        await save_upload_with_limit(file, saved_path, settings.max_resume_upload_bytes)
        resume_text = extract_resume_text(str(saved_path))
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Could not parse resume: {exc}") from exc
    finally:
        if saved_path.exists():
            saved_path.unlink()

    if not resume_text:
        raise HTTPException(status_code=400, detail="No text could be extracted from the resume")

    profile = extract_candidate_profile(resume_text, candidate_name)
    candidate = Candidate(
        name=profile.candidate_name or candidate_name,
        email=profile.email,
        role_applied=target_role,
        difficulty="medium",
        resume_text=resume_text,
        skills=json.dumps(profile.skills),
        projects=json.dumps(profile.projects),
        experience=json.dumps(profile.experience),
        education=json.dumps(profile.education),
        technologies=json.dumps(profile.technologies),
    )

    db.add(candidate)
    db.flush()

    access_token = generate_candidate_token()
    db.add(
        CandidateAccessToken(
            candidate_id=candidate.id,
            token_hash=hash_token(access_token),
            expires_at=datetime.utcnow() + timedelta(hours=settings.candidate_token_hours),
        )
    )
    db.commit()
    db.refresh(candidate)

    return {
        "candidate_id": candidate.id,
        "name": candidate.name,
        "role_applied": candidate.role_applied,
        "resume_preview": candidate.resume_text[:1000],
        "profile": profile_to_json(profile),
        "candidate_access_token": access_token,
    }
