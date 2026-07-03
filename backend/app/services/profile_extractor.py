import json
import re
from dataclasses import dataclass, asdict
from typing import Any

from app.services.llm_client import LLMClientError, call_llm, extract_json_object


COMMON_TECHNOLOGIES = [
    "Python",
    "JavaScript",
    "TypeScript",
    "React",
    "Node.js",
    "FastAPI",
    "Django",
    "Flask",
    "SQL",
    "PostgreSQL",
    "MySQL",
    "SQLite",
    "MongoDB",
    "Docker",
    "Kubernetes",
    "AWS",
    "Azure",
    "GCP",
    "Git",
    "REST",
    "GraphQL",
    "HTML",
    "CSS",
    "Tailwind",
    "Java",
    "C++",
    "C#",
    "Go",
    "Rust",
    "Machine Learning",
    "TensorFlow",
    "PyTorch",
]


SECTION_HEADERS = {
    "skills": {"skills", "technical skills", "core skills", "competencies"},
    "projects": {"projects", "project experience", "selected projects"},
    "experience": {"experience", "work experience", "employment", "professional experience"},
    "education": {"education", "academic background"},
}


@dataclass
class CandidateProfile:
    candidate_name: str | None
    email: str | None
    skills: list[str]
    projects: list[str]
    experience: list[str]
    education: list[str]
    technologies: list[str]


def profile_to_json(profile: CandidateProfile) -> dict[str, Any]:
    return asdict(profile)


def _clean_items(items: list[Any], limit: int = 12) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        text = re.sub(r"\s+", " ", str(item)).strip(" -:;,\t\r\n")
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text[:220])
        if len(cleaned) >= limit:
            break
    return cleaned


def _extract_email(text: str) -> str | None:
    match = re.search(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+", text)
    return match.group(0) if match else None


def _extract_candidate_name(text: str) -> str | None:
    for line in text.splitlines()[:8]:
        stripped = re.sub(r"\s+", " ", line).strip()
        if not stripped or "@" in stripped or re.search(r"\d", stripped):
            continue
        if len(stripped.split()) <= 5 and len(stripped) <= 80:
            return stripped
    return None


def _section_lines(text: str) -> dict[str, list[str]]:
    sections = {key: [] for key in SECTION_HEADERS}
    active: str | None = None

    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue

        normalized = line.lower().strip(":")
        matched_header = next(
            (key for key, headers in SECTION_HEADERS.items() if normalized in headers),
            None,
        )
        if matched_header:
            active = matched_header
            continue

        if active:
            sections[active].append(line)

    return sections


def _split_skill_text(lines: list[str]) -> list[str]:
    items: list[str] = []
    for line in lines[:12]:
        parts = re.split(r"[,|;/]|\s{2,}", line)
        items.extend(parts)
    return _clean_items(items, limit=20)


def fallback_extract_profile(resume_text: str, provided_name: str | None = None) -> CandidateProfile:
    sections = _section_lines(resume_text)
    technologies = [
        tech
        for tech in COMMON_TECHNOLOGIES
        if re.search(rf"(?<![A-Za-z0-9+#.]){re.escape(tech)}(?![A-Za-z0-9+#.])", resume_text, re.IGNORECASE)
    ]
    skills = _split_skill_text(sections["skills"])
    if not skills:
        skills = _clean_items(technologies, limit=12)

    return CandidateProfile(
        candidate_name=provided_name or _extract_candidate_name(resume_text),
        email=_extract_email(resume_text),
        skills=skills,
        projects=_clean_items(sections["projects"], limit=8),
        experience=_clean_items(sections["experience"], limit=8),
        education=_clean_items(sections["education"], limit=6),
        technologies=_clean_items(technologies, limit=20),
    )


def _normalize_profile_payload(data: dict[str, Any], fallback: CandidateProfile) -> CandidateProfile:
    return CandidateProfile(
        candidate_name=str(data.get("candidate_name") or data.get("name") or fallback.candidate_name or "").strip() or None,
        email=str(data.get("email") or fallback.email or "").strip() or None,
        skills=_clean_items(data.get("skills") if isinstance(data.get("skills"), list) else fallback.skills, 20),
        projects=_clean_items(data.get("projects") if isinstance(data.get("projects"), list) else fallback.projects, 8),
        experience=_clean_items(data.get("experience") if isinstance(data.get("experience"), list) else fallback.experience, 8),
        education=_clean_items(data.get("education") if isinstance(data.get("education"), list) else fallback.education, 6),
        technologies=_clean_items(
            data.get("technologies") if isinstance(data.get("technologies"), list) else fallback.technologies,
            20,
        ),
    )


def extract_candidate_profile(resume_text: str, provided_name: str | None = None) -> CandidateProfile:
    fallback = fallback_extract_profile(resume_text, provided_name)
    prompt = f"""
Extract a structured candidate profile from this resume.

Return ONLY valid JSON with this schema:
{{
  "candidate_name": "name or null",
  "email": "email or null",
  "skills": ["skill"],
  "projects": ["project summary"],
  "experience": ["experience summary"],
  "education": ["education summary"],
  "technologies": ["technology"]
}}

Use concise list items. Do not invent details.

Resume:
{resume_text[:7000]}
""".strip()

    try:
        text = call_llm([{"role": "user", "content": prompt}])
        data = extract_json_object(text)
        return _normalize_profile_payload(data, fallback)
    except (LLMClientError, json.JSONDecodeError, ValueError, TypeError):
        return fallback
