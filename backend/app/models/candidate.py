from datetime import datetime

from sqlalchemy import DateTime, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Candidate(Base):
    __tablename__ = "candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(Text)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    role_applied: Mapped[str] = mapped_column(Text)
    job_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    difficulty: Mapped[str] = mapped_column(Text, default="medium")
    resume_text: Mapped[str] = mapped_column(Text)
    skills: Mapped[str] = mapped_column(Text, default="")
    projects: Mapped[str] = mapped_column(Text, default="")
    experience: Mapped[str] = mapped_column(Text, default="")
    education: Mapped[str] = mapped_column(Text, default="")
    technologies: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
