from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Interview(Base):
    __tablename__ = "interviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    status: Mapped[str] = mapped_column(Text, default="in_progress")
    questions_json: Mapped[str] = mapped_column(Text)
    current_question_index: Mapped[int] = mapped_column(Integer, default=0)
    overall_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    recommendation: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InterviewAnswer(Base):
    __tablename__ = "interview_answers"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    question_index: Mapped[int] = mapped_column(Integer)
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    skill_area: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
