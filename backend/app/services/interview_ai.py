import json
import re
import secrets
from dataclasses import dataclass

from app.models.candidate import Candidate
from app.services.candidate_profile import candidate_profile_payload
from app.services.llm_client import LLMClientError, call_llm, extract_json_object


MAX_JD_PROMPT_CHARS = 3500


@dataclass
class AnswerEvaluation:
    score: int
    feedback: str
    needs_follow_up: bool
    follow_up_question: str | None = None


def jd_focus_area(job_description: str | None) -> str | None:
    if not job_description:
        return None

    lines = []
    for raw_line in job_description.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip(" -:\t")
        line = re.sub(
            r"(?i)\b(responsibilities|requirements|qualifications|experience|what you will do|what we're looking for)\s*[:\-]\s*",
            "",
            line,
        ).strip(" -:\t.")
        if not line:
            continue
        if re.search(
            r"(?i)\b(responsibilit|requirement|qualification|experience|build|design|develop|manage|collaborat|deploy|api|data|cloud|frontend|backend|full[- ]?stack)\b",
            line,
        ):
            lines.append(line[:120].rstrip(" .;:,"))
        if len(lines) >= 2:
            break

    if not lines:
        return None

    return "; ".join(lines)


def fallback_questions(candidate: Candidate) -> list[dict]:
    profile = candidate_profile_payload(candidate)
    skills = profile["skills"][:3] or profile["technologies"][:3]
    primary_skill = skills[0] if skills else "your strongest technical skill"
    secondary_skill = skills[1] if len(skills) > 1 else primary_skill
    project = profile["projects"][0] if profile["projects"] else "one project from your resume"
    alternate_project = profile["projects"][1] if len(profile["projects"]) > 1 else project
    jd_context = getattr(candidate, "job_description", None)
    jd_focus = jd_focus_area(jd_context)
    variant = secrets.randbelow(3)
    role_fit_prompt = (
        f"The job description for this {candidate.role_applied} role mentions a few expectations. "
        "Which parts of your background line up best, and where would you expect a ramp-up?"
        if jd_context
        else f"Which of your skills or technologies make you a strong fit for a {candidate.role_applied} position?"
    )

    return [
        {
            "id": 1,
            "skill_area": "Background",
            "question": f"To start, could you give me a quick overview of your background and what drew you to the {candidate.role_applied} role?",
        },
        {
            "id": 2,
            "skill_area": "Projects",
            "question": (
                f"I saw {alternate_project} on your resume. Could you walk me through the main technical decision you made there?"
                if variant == 1
                else f"I saw {project} on your resume. Could you walk me through what you built and what you personally owned?"
            ),
        },
        {
            "id": 3,
            "skill_area": "Technical Depth",
            "question": (
                f"The JD seems to emphasize {jd_focus}. Can you connect that to a time you used {secondary_skill} or a similar skill in real work?"
                if jd_focus
                else f"Can you tell me about a technically challenging problem you solved with {primary_skill}, including how you approached the tradeoffs?"
            ),
        },
        {
            "id": 4,
            "skill_area": "Problem Solving",
            "question": (
                f"If you joined this team and had to handle work like {jd_focus}, what risks or unknowns would you look for first?"
                if variant == 2 and jd_focus
                else f"If you joined this team and had to handle work like {jd_focus}, what would you clarify first and how would you approach delivery?"
                if jd_focus
                else "Imagine something breaks in production and the cause is not obvious yet. How would you work through it?"
            ),
        },
        {
            "id": 5,
            "skill_area": "Role Fit",
            "question": role_fit_prompt,
        },
    ]


def generate_interview_questions(candidate: Candidate) -> list[dict]:
    resume_excerpt = candidate.resume_text[:4500]
    job_description = (getattr(candidate, "job_description", None) or "").strip()
    jd_excerpt = job_description[:MAX_JD_PROMPT_CHARS] if job_description else "No job description was uploaded."
    profile = candidate_profile_payload(candidate)
    profile_json = json.dumps(profile, ensure_ascii=False, indent=2)
    interview_seed = secrets.token_hex(4)
    prompt = f"""
You are designing a resume-aware and job-description-aware phone screening interview.
The goal is not to ask generally good interview questions. The goal is to ask the five most relevant questions for THIS candidate and THIS job.
Interview generation seed: {interview_seed}

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
- Write questions the way a calm human interviewer would ask them on a phone screen.
- Keep each question concise, specific, and easy to answer aloud.
- First identify the strongest overlap between the job description and the resume: required skills, responsibilities, domain context, seniority expectations, projects, tools, and experience.
- Every question must be anchored in at least one concrete signal from the resume, the job description, or both.
- At least 4 questions must directly test a requirement or responsibility from the uploaded job description when a job description is available.
- At least 3 questions must mention a concrete candidate signal such as a project, technology, responsibility, company/domain, or achievement from the resume/profile.
- Prefer questions that validate fit gaps and evidence, not trivia. Ask how they used a skill, made a tradeoff, debugged a real issue, worked with stakeholders, or handled responsibility similar to the role.
- Prefer natural prompts like "I noticed..." or "Could you walk me through..." when grounded in the data.
- Include a mix of background, project depth, technical depth, problem solving, and role fit.
- Avoid generic trivia, quiz-style wording, multi-part checklists, and robotic phrasing.
- Do not ask broad questions like "Tell me about yourself" unless it is tied to the target role or JD.
- Do not ask about skills that are not in the resume or JD unless you are explicitly probing a visible gap.
- If the resume and JD do not overlap well, ask about the closest related experience and the expected ramp-up instead of inventing fit.
- Use the interview generation seed to vary which relevant evidence you emphasize and how you phrase the questions across separate interview runs.
- Do not reuse the same default five-question sequence if there are multiple relevant projects, skills, responsibilities, or gap areas available.
- Keep variation useful: never add randomness that makes a question less relevant to the JD or resume.
- Do not include answers or scoring.

Relevance check before returning JSON:
- For each question, silently confirm: "Which exact JD requirement or resume evidence caused me to ask this?"
- If a question could be asked of almost any candidate for this role, rewrite it to include the candidate-specific evidence.

Candidate:
Name: {candidate.name}
Email: {candidate.email or "unknown"}
Role: {candidate.role_applied}
Job description excerpt:
{jd_excerpt}
Structured profile:
{profile_json}
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
            "Could you give me a specific example from that work, including what you owned and what happened as a result?"
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
You are evaluating a candidate's answer in a conversational technical phone screen.

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
- Follow-up must sound like a human interviewer, be one sentence, and ask for specificity.
- Do not ask hostile, trick, or quiz-style follow-ups.

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
