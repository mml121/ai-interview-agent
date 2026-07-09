import json
import re
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
MAX_JD_PREVIEW_CHARS = 1200


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


def clean_optional_field(value: str | None) -> str:
    cleaned = (value or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) > MAX_FORM_FIELD_CHARS:
        raise HTTPException(
            status_code=400,
            detail=f"Role applied for must be {MAX_FORM_FIELD_CHARS} characters or less",
        )
    return cleaned


def normalized_field_value(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def infer_role_from_job_description(job_description: str) -> str:
    for line in job_description.splitlines()[:24]:
        cleaned = re.sub(r"\s+", " ", line).strip(" -:\t")
        if not cleaned:
            continue

        label_match = re.match(
            r"(?i)^(?:job\s*title|title|role|position|opening)\s*[:\-]\s*(.+)$",
            cleaned,
        )
        if label_match:
            return label_match.group(1).strip()[:MAX_FORM_FIELD_CHARS]

        if (
            len(cleaned) <= MAX_FORM_FIELD_CHARS
            and len(cleaned.split()) <= 10
            and not re.search(r"(?i)\b(job description|about us|responsibilities|requirements)\b", cleaned)
        ):
            return cleaned

    return "Role from uploaded job description"


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


async def extract_uploaded_text(file: UploadFile, max_bytes: int, too_large_message: str) -> str:
    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Only PDF, DOCX, and TXT files are supported")

    upload_dir = upload_directory()
    saved_path = upload_dir / f"{uuid4()}{suffix}"

    try:
        try:
            await save_upload_with_limit(file, saved_path, max_bytes)
        except HTTPException as exc:
            if exc.status_code == 413:
                raise HTTPException(status_code=413, detail=too_large_message) from exc
            raise
        return extract_resume_text(str(saved_path))
    finally:
        if saved_path.exists():
            saved_path.unlink()


@router.post("/upload")
async def upload_resume(
    name: str = Form(...),
    role_applied: str | None = Form(None),
    file: UploadFile = File(...),
    jd_file: UploadFile | None = File(None),
    db: Session = Depends(get_db),
):
    settings = get_settings()
    candidate_name = clean_required_field(name, "Candidate name")
    manual_role = clean_optional_field(role_applied)

    try:
        resume_text = await extract_uploaded_text(
            file,
            settings.max_resume_upload_bytes,
            "Resume file is too large",
        )
    except Exception as exc:
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=400, detail=f"Could not parse resume: {exc}") from exc

    if not resume_text:
        raise HTTPException(status_code=400, detail="No text could be extracted from the resume")

    job_description = ""
    if jd_file is not None and jd_file.filename:
        try:
            job_description = await extract_uploaded_text(
                jd_file,
                settings.max_resume_upload_bytes,
                "Job description file is too large",
            )
        except Exception as exc:
            if isinstance(exc, HTTPException):
                raise
            raise HTTPException(status_code=400, detail=f"Could not parse job description: {exc}") from exc

        if not job_description:
            raise HTTPException(
                status_code=400,
                detail="No text could be extracted from the job description",
            )

    if not manual_role and not job_description:
        raise HTTPException(
            status_code=400,
            detail="Enter a role or upload a job description",
        )

    if manual_role and normalized_field_value(manual_role) == normalized_field_value(candidate_name):
        if job_description:
            manual_role = ""
        else:
            raise HTTPException(
                status_code=400,
                detail="Role applied for cannot be the same as the candidate name. Enter the position title or upload a job description.",
            )

    target_role = manual_role or infer_role_from_job_description(job_description)

    profile = extract_candidate_profile(resume_text, candidate_name)
    candidate = Candidate(
        name=profile.candidate_name or candidate_name,
        email=profile.email,
        role_applied=target_role,
        job_description=job_description or None,
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
        "job_description_preview": (candidate.job_description or "")[:MAX_JD_PREVIEW_CHARS],
        "resume_preview": candidate.resume_text[:1000],
        "profile": profile_to_json(profile),
        "candidate_access_token": access_token,
    }
