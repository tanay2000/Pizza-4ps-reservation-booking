import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from db import Base, SessionLocal, engine
from models import BookingRequest, BookingRun


def run_one(row: BookingRequest) -> tuple[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "BOOKING_URL": row.booking_url,
            "GUEST_NAME": row.guest_name,
            "GUEST_EMAIL": row.guest_email,
            "GUEST_PHONE": row.guest_phone,
            "SPECIAL_REQUEST": row.special_request or "",
            "GUESTS": str(row.guests),
            "TIME_TEXT": row.time_text,
            "FALLBACK_START": row.fallback_start,
            "FALLBACK_END": row.fallback_end,
            "SLOT_INTERVAL_MINUTES": str(row.slot_interval_minutes),
            "TIMEZONE": row.timezone,
            "AUTO_CONFIRM": "true" if row.auto_confirm else "false",
            "HEADLESS": "true" if row.headless else "false",
            "SAVE_DEBUG_PAGES": "true",
            "DEBUG_DIR": f"debug-pages/user-{row.id}",
        }
    )

    proc = subprocess.run(
        [sys.executable, "book_reservation.py"],
        env=env,
        capture_output=True,
        text=True,
        timeout=300,
    )
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    message = output.strip()[:4000]
    if proc.returncode == 0:
        return "success", message
    return "failed", message


def main() -> None:
    Base.metadata.create_all(bind=engine)
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    today = now.date()

    with SessionLocal() as db:
        rows = (
            db.query(BookingRequest)
            .filter(BookingRequest.active.is_(True))
            .order_by(BookingRequest.id.asc())
            .all()
        )

        for row in rows:
            if row.last_run_date == today:
                continue

            status, message = run_one(row)
            row.last_run_date = today
            row.last_status = status
            row.last_error = "" if status == "success" else message

            db.add(
                BookingRun(
                    booking_request_id=row.id,
                    run_date=today,
                    status=status,
                    message=message,
                )
            )
            db.commit()
            print(f"[{row.id}] {status}")


if __name__ == "__main__":
    main()
