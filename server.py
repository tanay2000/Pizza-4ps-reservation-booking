from datetime import datetime

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from db import Base, SessionLocal, engine
from models import BookingRequest


Base.metadata.create_all(bind=engine)

app = FastAPI(title="Pizza 4P Booking Scheduler")


def layout(content: str) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width,initial-scale=1"/>
  <title>Booking Scheduler</title>
  <style>
    body{{font-family:ui-sans-serif,system-ui,-apple-system,Segoe UI,Roboto;max-width:980px;margin:24px auto;padding:0 16px;}}
    h1{{margin:0 0 8px 0;}}
    .card{{border:1px solid #ddd;border-radius:10px;padding:16px;margin:14px 0;}}
    .grid{{display:grid;grid-template-columns:1fr 1fr;gap:10px;}}
    label{{display:block;font-size:13px;color:#444;margin-bottom:4px;}}
    input,textarea{{width:100%;padding:10px;border:1px solid #bbb;border-radius:8px;box-sizing:border-box;}}
    button{{padding:10px 14px;border:0;border-radius:8px;background:#0f4c81;color:white;cursor:pointer;}}
    table{{width:100%;border-collapse:collapse;}}
    th,td{{text-align:left;padding:8px;border-bottom:1px solid #eee;font-size:13px;vertical-align:top;}}
    .muted{{color:#666;font-size:13px;}}
  </style>
</head>
<body>{content}</body>
</html>"""


@app.get("/", response_class=HTMLResponse)
def home(request: Request) -> HTMLResponse:
    with SessionLocal() as db:
        rows = db.query(BookingRequest).order_by(BookingRequest.id.desc()).limit(200).all()

    table_rows = []
    for r in rows:
        table_rows.append(
            f"<tr>"
            f"<td>{r.id}</td>"
            f"<td>{r.guest_name}<br/><span class='muted'>{r.guest_email}<br/>{r.guest_phone}</span></td>"
            f"<td>{r.guests} guest(s)<br/>{r.fallback_start} - {r.fallback_end}</td>"
            f"<td>{'ACTIVE' if r.active else 'PAUSED'}</td>"
            f"<td>{r.last_run_date or '-'}</td>"
            f"<td>{r.last_status or '-'}<br/><span class='muted'>{(r.last_error or '')[:120]}</span></td>"
            f"<td>"
            f"<form method='post' action='/toggle/{r.id}'>"
            f"<button type='submit'>{'Pause' if r.active else 'Activate'}</button>"
            f"</form>"
            f"</td>"
            f"</tr>"
        )

    content = f"""
    <h1>Pizza 4P Booking Scheduler</h1>
    <p class="muted">Users submit once; daily worker runs all active requests at 10:00 AM.</p>
    <div class="card">
      <form method="post" action="/submit">
        <div class="grid">
          <div><label>Guest name</label><input name="guest_name" required /></div>
          <div><label>Guest email</label><input type="email" name="guest_email" required /></div>
          <div><label>Guest phone</label><input name="guest_phone" required /></div>
          <div><label>Guests</label><input name="guests" value="2" required /></div>
          <div><label>Preferred time</label><input name="time_text" value="8:00 PM" required /></div>
          <div><label>Fallback start</label><input name="fallback_start" value="8:00 PM" required /></div>
          <div><label>Fallback end</label><input name="fallback_end" value="10:00 PM" required /></div>
          <div><label>Interval minutes</label><input name="slot_interval_minutes" value="15" required /></div>
          <div><label>Timezone</label><input name="timezone" value="Asia/Kolkata" required /></div>
          <div><label>Auto confirm</label><input name="auto_confirm" value="true" required /></div>
          <div><label>Headless</label><input name="headless" value="true" required /></div>
          <div style="grid-column:1/3"><label>Special request</label><textarea name="special_request"></textarea></div>
        </div>
        <input type="hidden" name="booking_url" value="https://www.tablecheck.com/en/pizza-4ps-in-indiranagar/reserve/message"/>
        <p><button type="submit">Submit booking request</button></p>
      </form>
    </div>
    <div class="card">
      <h3>Stored Requests</h3>
      <table>
        <thead><tr><th>ID</th><th>User</th><th>Pref</th><th>Status</th><th>Last Run</th><th>Result</th><th>Action</th></tr></thead>
        <tbody>{''.join(table_rows) if table_rows else '<tr><td colspan="7">No requests yet</td></tr>'}</tbody>
      </table>
    </div>
    <div class="muted">Server time: {datetime.now().isoformat(sep=' ', timespec='seconds')}</div>
    """
    return HTMLResponse(layout(content))


@app.post("/submit")
def submit(
    guest_name: str = Form(...),
    guest_email: str = Form(...),
    guest_phone: str = Form(...),
    special_request: str = Form(""),
    booking_url: str = Form("https://www.tablecheck.com/en/pizza-4ps-in-indiranagar/reserve/message"),
    guests: int = Form(2),
    time_text: str = Form("8:00 PM"),
    fallback_start: str = Form("8:00 PM"),
    fallback_end: str = Form("10:00 PM"),
    slot_interval_minutes: int = Form(15),
    timezone: str = Form("Asia/Kolkata"),
    auto_confirm: str = Form("true"),
    headless: str = Form("true"),
) -> RedirectResponse:
    with SessionLocal() as db:
        req = BookingRequest(
            guest_name=guest_name,
            guest_email=guest_email,
            guest_phone=guest_phone,
            special_request=special_request or "",
            booking_url=booking_url,
            guests=guests,
            time_text=time_text,
            fallback_start=fallback_start,
            fallback_end=fallback_end,
            slot_interval_minutes=slot_interval_minutes,
            timezone=timezone,
            auto_confirm=auto_confirm.lower() == "true",
            headless=headless.lower() == "true",
        )
        db.add(req)
        db.commit()
    return RedirectResponse(url="/", status_code=303)


@app.post("/toggle/{request_id}")
def toggle(request_id: int) -> RedirectResponse:
    with SessionLocal() as db:
        row = db.query(BookingRequest).filter(BookingRequest.id == request_id).first()
        if row:
            row.active = not row.active
            db.commit()
    return RedirectResponse(url="/", status_code=303)
