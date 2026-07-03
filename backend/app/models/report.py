from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    interview_id: Mapped[int] = mapped_column(ForeignKey("interviews.id"), index=True)
    report_text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
