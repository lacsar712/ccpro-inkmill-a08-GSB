from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

PROCESS_CARD_STATUSES = ("draft", "published", "obsolete")


class ProcessCard(Base):
    __tablename__ = "process_cards"
    __table_args__ = (
        UniqueConstraint("mill_id", "version_no", name="uq_process_card_mill_version"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mill_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mills.id", ondelete="CASCADE"), nullable=False
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.current_timestamp()
    )

    mill: Mapped["Mill"] = relationship("Mill", back_populates="process_cards")
