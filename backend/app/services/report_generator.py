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
    strongest_answers = sorted(
        [answer for answer in answers if answer.score is not None],
        key=lambda answer: answer.score or 0,
        reverse=True,
    )
    weakest_answers = list(reversed(strongest_answers))
    strongest = strongest_answers[0] if strongest_answers else None
    weakest = weakest_answers[0] if weakest_answers else None
    answered_areas = ", ".join(dict.fromkeys(answer.skill_area for answer in answers)) or "the interview"

    return {
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "role_applied": candidate.role_applied,
            "profile": candidate_profile_payload(candidate),
        },
        "summary": (
            f"{candidate.name} completed a {candidate.role_applied} screening covering {answered_areas}. "
            f"The strongest evidence came from {strongest.skill_area if strongest else 'the recorded answers'}, "
            f"where the evaluator noted: {strongest.feedback if strongest and strongest.feedback else 'no detailed evaluator note was recorded'}. "
            f"The weakest signal came from {weakest.skill_area if weakest else 'the recorded answers'}, "
            f"where the evaluator noted: {weakest.feedback if weakest and weakest.feedback else 'no detailed evaluator note was recorded'}."
        ),
        "overall_score": overall_score,
        "recommendation": interview.recommendation or recommendation_for_score(overall_score),
        "recommendation_reason": (
            f"The recommendation is tied to an overall score of {overall_score}. "
            f"Highest-scored area: {strongest.skill_area if strongest else 'not available'} "
            f"({strongest.score if strongest else 'n/a'}/5). "
            f"Lowest-scored area: {weakest.skill_area if weakest else 'not available'} "
            f"({weakest.score if weakest else 'n/a'}/5)."
        ),
        "strengths": [
            (
                f"{strongest.skill_area}: {strongest.feedback}"
                if strongest and strongest.feedback
                else "Provided enough information for answer-level scoring."
            ),
        ],
        "weaknesses": [
            (
                f"{weakest.skill_area}: {weakest.feedback}"
                if weakest and weakest.feedback
                else "Some responses did not contain enough detail for a confident evaluation."
            ),
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
You are writing an admin-facing technical screening report for a recruiter or hiring manager.
Your job is to turn the transcript and evaluator feedback into a specific, evidence-backed report.

Return ONLY valid JSON with this schema:
{{
  "summary": "5-7 sentence paragraph with concrete evidence from the candidate's answers",
  "overall_score": 3.4,
  "recommendation": "Hire / Proceed",
  "recommendation_reason": "3-5 sentence explanation tied to score and answer evidence",
  "strengths": ["specific strength with transcript evidence"],
  "weaknesses": ["specific gap with transcript evidence"],
  "skill_scores": [
    {{"skill_area": "Technical Depth", "score": 3.5, "notes": "specific evidence-backed note"}}
  ],
  "transcript_summary": [
    {{"skill_area": "Resume", "score": 3, "feedback": "what the candidate said and how well it answered the prompt"}}
  ]
}}

Report quality rules:
- Be concrete. Reference the candidate's actual projects, technologies, role target, answer details, scores, and evaluator feedback when available.
- Do NOT write generic phrases like "completed the interview", "showed good skills", "needs deeper review", or "based on average scored answer quality".
- If an answer is vague or too short, say exactly which topic was weak and what evidence was missing.
- Do not invent details that are not in the profile, answer data, scores, or feedback.
- Summary must explain the candidate's performance pattern across the interview, not just restate that they interviewed.
- Recommendation reason must explicitly explain why the final recommendation follows from the strongest and weakest evidence.
- Strengths and weaknesses must be actionable hiring notes, each grounded in at least one question, answer, score, or feedback item.
- Skill score notes must mention the evidence behind the score.
- Transcript summary must summarize each answer's substance, not merely repeat the evaluator feedback.
- Keep the tone professional, direct, and useful for an admin deciding next steps.

Candidate:
Name: {candidate.name}
Email: {candidate.email or "unknown"}
Role: {candidate.role_applied}
Overall score: {interview.overall_score}
Recommendation: {interview.recommendation}
Structured profile:
{json.dumps(profile, ensure_ascii=False, indent=2)}

Answer data:
{json.dumps(answer_payload, ensure_ascii=False, indent=2)}
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
