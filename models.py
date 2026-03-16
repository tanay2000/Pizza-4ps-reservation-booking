from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from db import Base


class BookingRequest(Base):
    __tablename__ = "booking_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    guest_name: Mapped[str] = mapped_column(String(200), nullable=False)
    guest_email: Mapped[str] = mapped_column(String(300), nullable=False)
    guest_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    special_request: Mapped[str] = mapped_column(Text, default="", nullable=False)

    booking_url: Mapped[str] = mapped_column(String(600), nullable=False)
    guests: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    time_text: Mapped[str] = mapped_column(String(40), default="8:00 PM", nullable=False)
    fallback_start: Mapped[str] = mapped_column(String(40), default="8:00 PM", nullable=False)
    fallback_end: Mapped[str] = mapped_column(String(40), default="10:00 PM", nullable=False)
    slot_interval_minutes: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    timezone: Mapped[str] = mapped_column(String(80), default="Asia/Kolkata", nullable=False)
    auto_confirm: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    headless: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    last_run_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(50), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class BookingRun(Base):
    __tablename__ = "booking_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    booking_request_id: Mapped[int] = mapped_column(Integer, nullable=False)
    run_date: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
