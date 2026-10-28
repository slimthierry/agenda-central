from sqlalchemy import Column, ForeignKey, Index, Integer, String, Table
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base

doctor_establishments = Table(
    "doctor_establishments",
    Base.metadata,
    Column("doctor_id", String(64), ForeignKey("doctors.id", ondelete="CASCADE"), primary_key=True),
    Column(
        "establishment_id",
        String(64),
        ForeignKey("establishments.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


class Doctor(Base):
    __tablename__ = "doctors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(255), unique=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True)
    api_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[str] = mapped_column(String(40))


class Establishment(Base):
    __tablename__ = "establishments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(255))
    address: Mapped[str | None] = mapped_column(String(255))
    color: Mapped[str] = mapped_column(String(20), server_default="#179F4E")
    connector_key: Mapped[str] = mapped_column(String(64), unique=True)
    created_at: Mapped[str] = mapped_column(String(40))


class AvailabilityRule(Base):
    __tablename__ = "availability_rules"
    __table_args__ = (Index("idx_avail_doctor", "doctor_id"),)

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(64), ForeignKey("doctors.id", ondelete="CASCADE"))
    establishment_id: Mapped[str | None] = mapped_column(
        String(64), ForeignKey("establishments.id", ondelete="SET NULL")
    )
    weekday: Mapped[int] = mapped_column(Integer)
    start_at: Mapped[str] = mapped_column(String(5))
    end_at: Mapped[str] = mapped_column(String(5))


class Appointment(Base):
    __tablename__ = "appointments"
    __table_args__ = (
        Index("idx_appt_doctor_date", "doctor_id", "date"),
        Index("idx_appt_updated", "doctor_id", "updated_at"),
    )

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    doctor_id: Mapped[str] = mapped_column(String(64), ForeignKey("doctors.id", ondelete="CASCADE"))
    establishment_id: Mapped[str] = mapped_column(String(64))
    patient_name: Mapped[str] = mapped_column(String(120))
    patient_phone: Mapped[str | None] = mapped_column(String(40))
    date: Mapped[str] = mapped_column(String(10))
    time: Mapped[str] = mapped_column(String(5))
    duration_min: Mapped[int] = mapped_column(Integer)
    reason: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(16), server_default="draft")
    source: Mapped[str] = mapped_column(String(16), server_default="app")
    created_at: Mapped[str] = mapped_column(String(40))
    updated_at: Mapped[str] = mapped_column(String(40))
    series_id: Mapped[str | None] = mapped_column(String(64))
    reminder_sent_at: Mapped[str | None] = mapped_column(String(40))
