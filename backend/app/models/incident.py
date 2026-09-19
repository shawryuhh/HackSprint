from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, func
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.db.base import Base
from app.models.enums import IncidentStatus, Severity


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    location: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Free-text, intentionally not an enum/CHECK constraint — see
    # app.core.domain_values for why.
    type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    severity: Mapped[Severity] = mapped_column(
        SAEnum(Severity, name="severity_enum"), nullable=False
    )
    priority_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    people_affected: Mapped[int | None] = mapped_column(Integer, nullable=True)
    needs: Mapped[list[str]] = mapped_column(
        ARRAY(String), nullable=False, default=list
    )

    status: Mapped[IncidentStatus] = mapped_column(
        SAEnum(IncidentStatus, name="incident_status_enum"),
        nullable=False,
        default=IncidentStatus.UNASSIGNED,
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
