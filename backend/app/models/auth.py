from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CandidateAccessToken(Base):
    __tablename__ = "candidate_access_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    candidate_id: Mapped[int] = mapped_column(ForeignKey("candidates.id"), index=True)
    token_hash: Mapped[str] = mapped_column(Text, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, index=True)
