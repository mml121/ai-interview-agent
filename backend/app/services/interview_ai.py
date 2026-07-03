from dataclasses import dataclass

from app.models.candidate import Candidate
from app.services.candidate_profile import candidate_profile_payload
from app.services.llm_client import LLMClientError, call_llm, extract_json_object


@dataclass
class AnswerEvaluation:
    score: int
    feedback: str
    needs_follow_up: bool
    follow_up_question: str | None = None


def fallback_questions(candidate: Candidate) -> list[dict]:
    profile = candidate_profile_payload(candidate)
    skills = profile["skills"][:3] or profile["technologies"][:3]
    primary_skill = skills[0] if skills else "your strongest technical skill"
    project = profile["projects"][0] if profile["projects"] else "one project from your resume"

    return [
        {
            "id": 1,
            "skill_area": "Background",
            "question": f"Can you briefly introduce yourself and explain your interest in the {candidate.role_applied} role?",
        },
        {
            "id": 2,
            "skill_area": "Projects",
            "question": f"Walk me through {project} and explain your specific contribution.",
        },
        {
            "id": 3,
            "skill_area": "Technical Depth",
            "question": f"At a {candidate.difficulty} level, what is a technically challenging problem you solved using {primary_skill}?",
        },
        {
            "id": 4,
            "skill_area": "Problem Solving",
            "question": "How do you usually debug an issue when you do not immediately know the cause?",
        },
        {
            "id": 5,
            "skill_area": "Role Fit",
            "question": f"Which of your skills or technologies make you a strong fit for a {candidate.role_applied} position?",
        },
    ]


def generate_interview_questions(candidate: Candidate) -> list[dict]:
    resume_excerpt = candidate.resume_text[:4500]
    profile = candidate_profile_payload(candidate)
    prompt = f"""
You are designing a resume-aware technical interview.

Return ONLY valid JSON with this schema:
{{
  "questions": [
    {{
      "id": 1,
      "skill_area": "Background",
      "question": "question text"
    }}
  ]
}}

Rules:
- Generate exactly 5 questions.
- Ask one question at a time, but this output is the private interviewer plan.
- Keep questions concise and conversational.
- Base questions on the structured candidate profile first, then the resume excerpt.
- Reflect the target role, selected difficulty, skills, projects, technologies, and experience.
- Include a mix of background, project depth, technical depth, problem solving, and role fit.
- Do not include answers or scoring.

Candidate:
Name: {candidate.name}
Email: {candidate.email or "unknown"}
Role: {candidate.role_applied}
Difficulty: {candidate.difficulty}
Structured profile:
{profile}
Resume excerpt:
{resume_excerpt}
""".strip()

    try:
        text = call_llm([{"role": "user", "content": prompt}])
        data = extract_json_object(text)
        questions = data.get("questions")

        if not isinstance(questions, list) or len(questions) < 1:
            raise LLMClientError("Question payload was empty")

        normalized = []
        for index, question in enumerate(questions[:5], start=1):
            normalized.append(
                {
                    "id": index,
                    "skill_area": str(question.get("skill_area") or "General"),
                    "question": str(question.get("question") or "").strip(),
                }
            )

        if any(not item["question"] for item in normalized):
            raise LLMClientError("Question text was missing")

        return normalized
    except Exception:
        return fallback_questions(candidate)


def fallback_evaluation(answer: str, previous_answers_for_question: int) -> AnswerEvaluation:
    word_count = len(answer.split())
    vague_terms = ["not sure", "maybe", "kind of", "i guess", "don't know", "dont know"]
    is_vague = any(term in answer.lower() for term in vague_terms)
    needs_follow_up = previous_answers_for_question == 0 and (word_count < 18 or is_vague)

    if word_count >= 70:
        score = 4
        feedback = "Strong detail and clear practical explanation."
    elif word_count >= 35:
        score = 3
        feedback = "Acceptable answer with some useful detail."
    elif word_count >= 18:
        score = 2
        feedback = "Partially answered, but needs more concrete depth."
    else:
        score = 1
        feedback = "Answer is too brief to evaluate confidently."

    return AnswerEvaluation(
        score=score,
        feedback=feedback,
        needs_follow_up=needs_follow_up,
        follow_up_question=(
            "Can you expand on that with a concrete example, your specific contribution, "
            "and the tradeoff or outcome?"
            if needs_follow_up
            else None
        ),
    )


def evaluate_answer(
    question: str,
    answer: str,
    skill_area: str,
    previous_answers_for_question: int,
) -> AnswerEvaluation:
    prompt = f"""
You are evaluating a candidate's answer in a technical interview.

Return ONLY valid JSON with this schema:
{{
  "score": 1,
  "feedback": "short evaluator feedback",
  "needs_follow_up": true,
  "follow_up_question": "follow-up question or null"
}}

Scoring:
5 = excellent, technically strong, clear, practical
4 = good, mostly complete
3 = acceptable, some gaps
2 = weak or shallow
1 = insufficient or incorrect

Follow-up rules:
- Ask a follow-up only if the answer is short, vague, unclear, or misses concrete detail.
- If a follow-up has already been asked for this topic, set needs_follow_up to false.
- Follow-up must be conversational and ask for specificity.

Skill area: {skill_area}
Question: {question}
Previous answers for this topic: {previous_answers_for_question}
Candidate answer: {answer}
""".strip()

    try:
        text = call_llm([{"role": "user", "content": prompt}])
        data = extract_json_object(text)
        score = int(data.get("score", 1))
        score = min(5, max(1, score))
        needs_follow_up = bool(data.get("needs_follow_up", False))

        if previous_answers_for_question > 0:
            needs_follow_up = False

        follow_up_question = data.get("follow_up_question")
        if needs_follow_up and not follow_up_question:
            follow_up_question = fallback_evaluation(answer, 0).follow_up_question

        return AnswerEvaluation(
            score=score,
            feedback=str(data.get("feedback") or "Answer evaluated."),
            needs_follow_up=needs_follow_up,
            follow_up_question=str(follow_up_question) if follow_up_question else None,
        )
    except Exception:
        return fallback_evaluation(answer, previous_answers_for_question)


def recommendation_for_score(score: float) -> str:
    if score >= 4.0:
        return "Strong Hire"
    if score >= 3.2:
        return "Hire / Proceed"
    if score >= 2.5:
        return "Hold"
    return "No Hire"
