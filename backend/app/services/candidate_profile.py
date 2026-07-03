import json
from typing import Any

from app.models.candidate import Candidate


PROFILE_LIST_FIELDS = ("skills", "projects", "experience", "education", "technologies")


def _load_list(value: str | None) -> list[str]:
    if not value:
        return []
    try:
        loaded = json.loads(value)
    except json.JSONDecodeError:
        loaded = [item.strip() for item in value.split(",")]

    if not isinstance(loaded, list):
        return []

    return [str(item).strip() for item in loaded if str(item).strip()]


def candidate_profile_payload(candidate: Candidate) -> dict[str, Any]:
    return {
        "candidate_name": candidate.name,
        "email": candidate.email,
        "skills": _load_list(candidate.skills),
        "projects": _load_list(candidate.projects),
        "experience": _load_list(candidate.experience),
        "education": _load_list(candidate.education),
        "technologies": _load_list(candidate.technologies),
    }
