import json
from collections import defaultdict
from typing import Any

from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewAnswer
from app.services.candidate_profile import candidate_profile_payload
from app.services.interview_ai import recommendation_for_score
from app.services.llm_client import call_llm, extract_json_object


def fallback_report(
    candidate: Candidate,
    interview: Interview,
    answers: list[InterviewAnswer],
) -> dict[str, Any]:
    skill_scores: dict[str, list[int]] = defaultdict(list)

    for answer in answers:
        if answer.score is not None:
            skill_scores[answer.skill_area].append(answer.score)

    skill_summary = [
        {
            "skill_area": skill,
            "score": round(sum(scores) / len(scores), 2),
        }
        for skill, scores in skill_scores.items()
        if scores
    ]
    overall_score = interview.overall_score or 0

    return {
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "role_applied": candidate.role_applied,
            "profile": candidate_profile_payload(candidate),
        },
        "summary": (
            f"{candidate.name} completed a screening interview for {candidate.role_applied}. "
            "The report was generated from answer scores and evaluator feedback."
        ),
        "overall_score": overall_score,
        "recommendation": interview.recommendation or recommendation_for_score(overall_score),
        "recommendation_reason": "Recommendation is based on the average scored answer quality.",
        "strengths": [
            "Completed the full interview flow.",
            "Provided enough information for answer-level scoring.",
        ],
        "weaknesses": [
            "Some responses may need deeper review by a human interviewer.",
        ],
        "skill_scores": skill_summary,
        "transcript_summary": [
            {
                "skill_area": answer.skill_area,
                "score": answer.score,
                "feedback": answer.feedback or "No feedback recorded.",
            }
            for answer in answers
        ],
    }


def generate_final_report(
    candidate: Candidate,
    interview: Interview,
    answers: list[InterviewAnswer],
) -> dict[str, Any]:
    answer_payload = [
        {
            "skill_area": answer.skill_area,
            "question": answer.question,
            "answer": answer.answer,
            "score": answer.score,
            "feedback": answer.feedback,
        }
        for answer in answers
    ]
    profile = candidate_profile_payload(candidate)
    prompt = f"""
You are writing an admin-facing technical screening report.

Return ONLY valid JSON with this schema:
{{
  "summary": "short paragraph",
  "overall_score": 3.4,
  "recommendation": "Hire / Proceed",
  "recommendation_reason": "short explanation",
  "strengths": ["item"],
  "weaknesses": ["item"],
  "skill_scores": [
    {{"skill_area": "Technical Depth", "score": 3.5, "notes": "short note"}}
  ],
  "transcript_summary": [
    {{"skill_area": "Resume", "score": 3, "feedback": "short feedback"}}
  ]
}}

Candidate:
Name: {candidate.name}
Email: {candidate.email or "unknown"}
Role: {candidate.role_applied}
Overall score: {interview.overall_score}
Recommendation: {interview.recommendation}
Structured profile:
{json.dumps(profile, ensure_ascii=False)}

Answer data:
{json.dumps(answer_payload, ensure_ascii=False)}
""".strip()

    try:
        text = call_llm([{"role": "user", "content": prompt}])
        report = extract_json_object(text)

        if not isinstance(report.get("strengths"), list):
            raise ValueError("Report strengths missing")
        if not isinstance(report.get("weaknesses"), list):
            raise ValueError("Report weaknesses missing")

        report["overall_score"] = report.get("overall_score", interview.overall_score)
        report["recommendation"] = report.get("recommendation", interview.recommendation)
        report["candidate"] = {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "role_applied": candidate.role_applied,
            "profile": profile,
        }
        return report
    except Exception:
        return fallback_report(candidate, interview, answers)
