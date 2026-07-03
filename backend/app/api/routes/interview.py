import json

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.auth import require_candidate
from app.db.session import get_db
from app.models.auth import CandidateAccessToken
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewAnswer
from app.models.report import Report
from app.services.candidate_profile import candidate_profile_payload
from app.services.interview_ai import (
    evaluate_answer,
    generate_interview_questions,
    recommendation_for_score,
)
from app.services.report_generator import generate_final_report

router = APIRouter(prefix="/api/interview", tags=["interview"])
reports_router = APIRouter(prefix="/api/reports", tags=["reports"])
MAX_ANSWER_CHARS = 5000


class InterviewPlanRequest(BaseModel):
    candidate_id: int


class InterviewStartRequest(BaseModel):
    candidate_id: int


class InterviewAnswerRequest(BaseModel):
    interview_id: int
    answer: str
    question: str | None = None
    question_index: int | None = None
    skill_area: str | None = None


class InterviewEndRequest(BaseModel):
    interview_id: int


def parse_report_text(report: Report) -> dict:
    try:
        payload = json.loads(report.report_text)
    except json.JSONDecodeError:
        payload = {"summary": report.report_text}
    return payload if isinstance(payload, dict) else {"summary": str(payload)}


def serialize_report(report: Report, interview: Interview, candidate: Candidate, answers: list[InterviewAnswer]) -> dict:
    return {
        "report_id": report.id,
        "interview_id": interview.id,
        "candidate_id": candidate.id,
        "candidate": {
            "id": candidate.id,
            "name": candidate.name,
            "email": candidate.email,
            "role_applied": candidate.role_applied,
            "difficulty": candidate.difficulty,
            "profile": candidate_profile_payload(candidate),
        },
        "status": interview.status,
        "overall_score": interview.overall_score,
        "recommendation": interview.recommendation,
        "created_at": report.created_at.isoformat(),
        "report": parse_report_text(report),
        "answers": [
            {
                "id": answer.id,
                "question_index": answer.question_index,
                "skill_area": answer.skill_area,
                "question": answer.question,
                "answer": answer.answer,
                "score": answer.score,
                "feedback": answer.feedback,
                "created_at": answer.created_at.isoformat(),
            }
            for answer in answers
        ],
    }


def serialize_question(question: dict, index: int, total: int) -> dict:
    return {
        "question_index": index,
        "question_number": index + 1,
        "total_questions": total,
        "skill_area": question["skill_area"],
        "question": question["question"],
        "is_follow_up": question.get("is_follow_up", False),
    }


def build_follow_up_question(question: dict, follow_up_question: str) -> dict:
    return {
        "id": question["id"],
        "skill_area": question["skill_area"],
        "is_follow_up": True,
        "question": follow_up_question,
    }


def complete_interview_if_needed(interview: Interview, db: Session) -> Report | None:
    answers = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.interview_id == interview.id)
        .order_by(InterviewAnswer.created_at.asc())
        .all()
    )
    scored_answers = [answer for answer in answers if answer.score is not None]

    if scored_answers:
        interview.overall_score = round(
            sum(answer.score or 0 for answer in scored_answers) / len(scored_answers),
            2,
        )
        interview.recommendation = recommendation_for_score(interview.overall_score)

    existing_report = (
        db.query(Report)
        .filter(Report.interview_id == interview.id)
        .first()
    )

    if existing_report is None:
        candidate = db.get(Candidate, interview.candidate_id)
        if candidate is not None:
            report_payload = generate_final_report(candidate, interview, answers)
            existing_report = Report(
                interview_id=interview.id,
                report_text=json.dumps(report_payload),
            )
            db.add(existing_report)
            db.flush()

    return existing_report


@router.post("/plan")
def create_interview_plan(
    request: InterviewPlanRequest,
    db: Session = Depends(get_db),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    if access_token.candidate_id != request.candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access required")

    candidate = db.get(Candidate, request.candidate_id)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    questions = generate_interview_questions(candidate)

    return {
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "candidate_profile": candidate_profile_payload(candidate),
        "role_applied": candidate.role_applied,
        "difficulty": candidate.difficulty,
        "questions": questions,
    }


@router.post("/start")
def start_interview(
    request: InterviewStartRequest,
    db: Session = Depends(get_db),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    if access_token.candidate_id != request.candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access required")

    candidate = db.get(Candidate, request.candidate_id)

    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    questions = generate_interview_questions(candidate)
    interview = Interview(
        candidate_id=candidate.id,
        questions_json=json.dumps(questions),
        current_question_index=0,
    )

    db.add(interview)
    db.commit()
    db.refresh(interview)

    return {
        "interview_id": interview.id,
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "candidate_profile": candidate_profile_payload(candidate),
        "role_applied": candidate.role_applied,
        "status": interview.status,
        "current_question": serialize_question(questions[0], 0, len(questions)),
    }


@router.post("/answer")
def submit_answer(
    request: InterviewAnswerRequest,
    db: Session = Depends(get_db),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    interview = db.get(Interview, request.interview_id)

    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    if access_token.candidate_id != interview.candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access required")

    if interview.status == "completed":
        raise HTTPException(status_code=400, detail="Interview is already completed")

    answer_text = request.answer.strip()

    if not answer_text:
        raise HTTPException(status_code=400, detail="Answer cannot be empty")
    if len(answer_text) > MAX_ANSWER_CHARS:
        raise HTTPException(status_code=400, detail="Answer must be 5000 characters or less")

    questions = json.loads(interview.questions_json)
    current_index = interview.current_question_index

    if current_index >= len(questions):
        interview.status = "completed"
        report = complete_interview_if_needed(interview, db)
        db.commit()
        return {
            "interview_id": interview.id,
            "status": interview.status,
            "is_complete": True,
            "current_question": None,
            "report_id": report.id if report else None,
        }

    current_question = questions[current_index]
    asked_question_index = request.question_index

    if asked_question_index is None:
        asked_question_index = current_index
    if asked_question_index != current_index:
        raise HTTPException(status_code=400, detail="Question index does not match the active question")

    previous_answers_for_question = (
        db.query(InterviewAnswer)
        .filter(
            InterviewAnswer.interview_id == interview.id,
            InterviewAnswer.question_index == current_index,
        )
        .count()
    )
    asked_question = current_question["question"]
    if previous_answers_for_question > 0 and request.question:
        asked_question = request.question.strip()[:1000] or asked_question
    asked_skill_area = current_question["skill_area"]

    saved_answer = InterviewAnswer(
        interview_id=interview.id,
        question_index=asked_question_index,
        question=asked_question,
        answer=answer_text,
        skill_area=asked_skill_area,
    )

    evaluation = evaluate_answer(
        question=asked_question,
        answer=answer_text,
        skill_area=asked_skill_area,
        previous_answers_for_question=previous_answers_for_question,
    )
    saved_answer.score = evaluation.score
    saved_answer.feedback = evaluation.feedback
    db.add(saved_answer)
    db.flush()
    report = None

    if evaluation.needs_follow_up and evaluation.follow_up_question:
        next_question = serialize_question(
            build_follow_up_question(current_question, evaluation.follow_up_question),
            current_index,
            len(questions),
        )
    else:
        interview.current_question_index = current_index + 1

    if interview.current_question_index >= len(questions):
        interview.status = "completed"
        report = complete_interview_if_needed(interview, db)
        next_question = None
    elif not evaluation.needs_follow_up:
        next_question = serialize_question(
            questions[interview.current_question_index],
            interview.current_question_index,
            len(questions),
        )

    db.commit()
    db.refresh(interview)

    return {
        "interview_id": interview.id,
        "status": interview.status,
        "is_complete": interview.status == "completed",
        "saved_answer_id": saved_answer.id,
        "score": saved_answer.score,
        "feedback": saved_answer.feedback,
        "overall_score": interview.overall_score,
        "recommendation": interview.recommendation,
        "report_id": report.id if interview.status == "completed" and report else None,
        "current_question": next_question,
    }


@router.post("/end")
def end_interview(
    request: InterviewEndRequest,
    db: Session = Depends(get_db),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    interview = db.get(Interview, request.interview_id)

    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    if access_token.candidate_id != interview.candidate_id:
        raise HTTPException(status_code=403, detail="Candidate access required")

    interview.status = "completed"
    report = complete_interview_if_needed(interview, db)
    db.commit()

    if report is None:
        raise HTTPException(status_code=400, detail="Could not generate a report for this interview")

    db.refresh(interview)
    db.refresh(report)
    candidate = db.get(Candidate, interview.candidate_id)
    answers = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.interview_id == interview.id)
        .order_by(InterviewAnswer.created_at.asc())
        .all()
    )

    if candidate is None:
        raise HTTPException(status_code=404, detail="Candidate not found")

    return serialize_report(report, interview, candidate, answers)


@reports_router.get("/{report_id}")
def get_report(
    report_id: int,
    db: Session = Depends(get_db),
    access_token: CandidateAccessToken = Depends(require_candidate),
):
    row = (
        db.query(Report, Interview, Candidate)
        .join(Interview, Interview.id == Report.interview_id)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .filter(Report.id == report_id)
        .first()
    )

    if row is None:
        raise HTTPException(status_code=404, detail="Report not found")

    report, interview, candidate = row
    if access_token.candidate_id != candidate.id:
        raise HTTPException(status_code=403, detail="Candidate access required")

    answers = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.interview_id == interview.id)
        .order_by(InterviewAnswer.created_at.asc())
        .all()
    )

    return serialize_report(report, interview, candidate, answers)
