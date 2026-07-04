import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.auth import require_admin
from app.db.session import get_db
from app.models.candidate import Candidate
from app.models.interview import Interview, InterviewAnswer
from app.models.report import Report
from app.services.candidate_profile import candidate_profile_payload

router = APIRouter(prefix="/api/admin", tags=["admin"])


def serialize_interview_summary(interview: Interview, candidate: Candidate) -> dict:
    return {
        "interview_id": interview.id,
        "candidate_id": candidate.id,
        "candidate_name": candidate.name,
        "candidate_email": candidate.email,
        "candidate_profile": candidate_profile_payload(candidate),
        "role_applied": candidate.role_applied,
        "status": interview.status,
        "overall_score": interview.overall_score,
        "recommendation": interview.recommendation,
        "created_at": interview.created_at.isoformat(),
    }


@router.get("/interviews")
def list_completed_interviews(
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    rows = (
        db.query(Interview, Candidate)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .filter(Interview.status == "completed")
        .order_by(Interview.created_at.desc())
        .all()
    )

    return {
        "interviews": [
            serialize_interview_summary(interview, candidate)
            for interview, candidate in rows
        ]
    }


@router.get("/interviews/{interview_id}")
def get_interview_detail(
    interview_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    row = (
        db.query(Interview, Candidate)
        .join(Candidate, Candidate.id == Interview.candidate_id)
        .filter(Interview.id == interview_id)
        .first()
    )

    if row is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    interview, candidate = row
    answers = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.interview_id == interview.id)
        .order_by(InterviewAnswer.created_at.asc())
        .all()
    )
    report = (
        db.query(Report)
        .filter(Report.interview_id == interview.id)
        .order_by(Report.created_at.desc())
        .first()
    )
    report_payload = None

    if report is not None:
        try:
            report_payload = json.loads(report.report_text)
        except json.JSONDecodeError:
            report_payload = {"summary": report.report_text}

    return {
        **serialize_interview_summary(interview, candidate),
        "report": report_payload,
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


@router.delete("/interviews/{interview_id}")
def delete_interview_report(
    interview_id: int,
    db: Session = Depends(get_db),
    _: dict = Depends(require_admin),
):
    interview = db.get(Interview, interview_id)

    if interview is None:
        raise HTTPException(status_code=404, detail="Interview not found")

    db.query(Report).filter(Report.interview_id == interview.id).delete(
        synchronize_session=False
    )
    db.query(InterviewAnswer).filter(InterviewAnswer.interview_id == interview.id).delete(
        synchronize_session=False
    )
    db.delete(interview)
    db.commit()

    return {"deleted_interview_id": interview_id}
