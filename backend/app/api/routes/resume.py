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
SUPPORTED_DIFFICULTIES = {"easy", "medium", "hard"}


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
    difficulty: str = Form("medium"),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    suffix = Path(file.filename or "").suffix.lower()
    normalized_difficulty = difficulty.strip().lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT resumes are supported")

    if normalized_difficulty not in SUPPORTED_DIFFICULTIES:
        raise HTTPException(status_code=400, detail="Difficulty must be easy, medium, or hard")

    if len(name.strip()) > 120 or len(role_applied.strip()) > 120:
        raise HTTPException(status_code=400, detail="Candidate name and role must be 120 characters or less")

    upload_dir = Path(settings.upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
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

    profile = extract_candidate_profile(resume_text, name.strip())
    candidate = Candidate(
        name=profile.candidate_name or name.strip(),
        email=profile.email,
        role_applied=role_applied.strip(),
        difficulty=normalized_difficulty,
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
        "difficulty": candidate.difficulty,
        "resume_preview": candidate.resume_text[:1000],
        "profile": profile_to_json(profile),
        "candidate_access_token": access_token,
    }
