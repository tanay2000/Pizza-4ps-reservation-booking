import os
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import requests


SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
RUN_TIMEZONE = os.getenv("RUN_TIMEZONE", "Asia/Kolkata")


def required_env(name: str, value: str) -> str:
    if not value:
        raise RuntimeError(f"Missing required env var: {name}")
    return value


def client_headers() -> dict[str, str]:
    key = required_env("SUPABASE_SERVICE_ROLE_KEY", SUPABASE_SERVICE_ROLE_KEY)
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def supabase_get(path: str, params: dict[str, str]) -> list[dict]:
    url = f"{required_env('SUPABASE_URL', SUPABASE_URL)}/rest/v1/{path}"
    resp = requests.get(url, headers=client_headers(), params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def supabase_patch(path: str, params: dict[str, str], payload: dict) -> list[dict]:
    url = f"{required_env('SUPABASE_URL', SUPABASE_URL)}/rest/v1/{path}"
    resp = requests.patch(url, headers=client_headers(), params=params, json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def supabase_insert(path: str, payload: dict) -> list[dict]:
    url = f"{required_env('SUPABASE_URL', SUPABASE_URL)}/rest/v1/{path}"
    resp = requests.post(url, headers=client_headers(), json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def run_one(row: dict) -> tuple[str, str]:
    env = os.environ.copy()
    env.update(
        {
            "BOOKING_URL": row["booking_url"],
            "GUEST_NAME": row["guest_name"],
            "GUEST_EMAIL": row["guest_email"],
            "GUEST_PHONE": row["guest_phone"],
            "SPECIAL_REQUEST": row.get("special_request") or "",
            "GUESTS": str(row.get("guests", 2)),
            "TIME_TEXT": row.get("time_text", "8:00 PM"),
            "FALLBACK_START": row.get("fallback_start", "8:00 PM"),
            "FALLBACK_END": row.get("fallback_end", "10:00 PM"),
            "SLOT_INTERVAL_MINUTES": str(row.get("slot_interval_minutes", 15)),
            "TIMEZONE": row.get("timezone", RUN_TIMEZONE),
            "AUTO_CONFIRM": "true" if row.get("auto_confirm", True) else "false",
            "HEADLESS": "true" if row.get("headless", True) else "false",
            "SAVE_DEBUG_PAGES": "true",
            "DEBUG_DIR": f"debug-pages/user-{row['id']}",
        }
    )

    proc = subprocess.run(
        [sys.executable, "book_reservation.py"],
        env=env,
        capture_output=True,
        text=True,
        timeout=360,
    )
    output = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    message = output[:4000]
    if proc.returncode == 0:
        return "success", message
    return "failed", message


def main() -> None:
    now = datetime.now(ZoneInfo(RUN_TIMEZONE))
    today = now.date().isoformat()

    rows = supabase_get("booking_requests", {"select": "*", "active": "eq.true", "order": "id.asc"})

    for row in rows:
        if row.get("last_run_date") == today:
            continue

        status, message = run_one(row)
        supabase_patch(
            "booking_requests",
            {"id": f"eq.{row['id']}"},
            {
                "last_run_date": today,
                "last_status": status,
                "last_error": "" if status == "success" else message,
                "updated_at": now.isoformat(),
            },
        )
        supabase_insert(
            "booking_runs",
            {
                "booking_request_id": row["id"],
                "run_date": today,
                "status": status,
                "message": message,
            },
        )
        print(f"[{row['id']}] {status}")


if __name__ == "__main__":
    main()
