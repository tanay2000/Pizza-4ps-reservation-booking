# Reservation Booking Script

## Free Deployment (GitHub Pages + Supabase + GitHub Actions)

This supports a free-style deployment where:
1. Users submit from a static homepage.
2. Requests are stored in Supabase.
3. GitHub Actions cron runs daily at 10:00 AM (Asia/Kolkata) and processes all active requests one by one.

### Files Added For This

- `public/index.html`: public booking form
- `public/main.js`: submits form to Supabase REST
- `public/config.js`: Supabase URL + anon key
- `supabase/schema.sql`: tables + RLS policies
- `.github/workflows/daily-booking.yml`: daily worker schedule
- `run_daily_bookings_supabase.py`: worker that reads DB and executes bookings

### Setup Steps

1. Create a Supabase project.
2. Run SQL from `supabase/schema.sql` in Supabase SQL editor.
3. Update `public/config.js`:
   - `SUPABASE_URL`
   - `SUPABASE_ANON_KEY`
4. In GitHub repo settings -> Secrets and variables -> Actions, add:
   - `SUPABASE_URL`
   - `SUPABASE_SERVICE_ROLE_KEY`
5. Enable GitHub Pages for `/public` (or publish `public` folder via your static host).
6. Keep `.github/workflows/daily-booking.yml` enabled.

### Manual Worker Run

You can trigger immediately from GitHub Actions via `workflow_dispatch`, or run locally:

```bash
SUPABASE_URL="https://<project>.supabase.co" \
SUPABASE_SERVICE_ROLE_KEY="<service-role-key>" \
.venv/bin/python run_daily_bookings_supabase.py
```

Automates this flow:
1. Open reservation homepage.
2. Click **Confirm and continue**.
3. Select **2 guests**.
4. Select date = **same weekday of next week**.
5. Start search at **8:00 PM** and click **Find availability**.
6. If needed, select first visible slot from **8:00 PM to 10:00 PM** (15-min steps).
7. Fill guest details.
8. Auto-click **Confirm booking**.

## Multi-User Hosted Mode (Web + Daily Worker)

This repo now includes:
- `server.py`: homepage/form where many users submit booking requests.
- `run_daily_bookings.py`: daily worker that runs all active requests one-by-one.
- `data/bookings.db`: SQLite storage for user requests and run history.

## Setup (Isolated Python Environment)

```bash
cd /Users/tanaygupta/Documents/Playground
python3 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install playwright
.venv/bin/python -m playwright install chromium
```

Start web app:

```bash
.venv/bin/uvicorn server:app --host 0.0.0.0 --port 8000
```

Then open:
- `http://localhost:8000`

## Run (Python)

```bash
.venv/bin/python book_reservation.py
```

For your TableCheck page (defaults already set):

```bash
.venv/bin/python book_reservation.py
```

Run headless:

```bash
HEADLESS="true" .venv/bin/python book_reservation.py
```

Override guest details / fallback window:

```bash
GUEST_NAME="Tanay Gupta" \
GUEST_EMAIL="tanaygupta2000@gmail.com" \
GUEST_PHONE="+91 9057222901" \
SPECIAL_REQUEST="" \
FALLBACK_START="8:00 PM" \
FALLBACK_END="10:00 PM" \
SLOT_INTERVAL_MINUTES="15" \
AUTO_CONFIRM="true" \
.venv/bin/python book_reservation.py
```

## One-Time Interactive Setup (Recommended for cron)

This asks for your details once and stores them in `.booking.env`:

```bash
.venv/bin/python setup_booking_config.py
```

After this, normal run uses those saved values automatically:

```bash
.venv/bin/python book_reservation.py
```

## Config

- `BOOKING_URL` (required): reservation page URL.
- Default is `https://www.tablecheck.com/en/pizza-4ps-in-indiranagar/reserve/message`.
- `GUESTS` (optional, default `2`): party size.
- `TIME_TEXT` (optional, default `8:00 PM`): initial time for availability search.
- `FALLBACK_START` / `FALLBACK_END` (defaults `8:00 PM` / `10:00 PM`): slot selection range.
- `SLOT_INTERVAL_MINUTES` (default `15`): required slot spacing.
- `GUEST_NAME` / `GUEST_EMAIL` / `GUEST_PHONE`: guest form details.
- `SPECIAL_REQUEST` (optional): leave empty for none.
- `AUTO_CONFIRM` (default `true`): click final confirm booking.
- `HEADLESS` (optional, default `true`): set `false` to watch browser.
- `TIMEZONE` (optional, default `Asia/Kolkata`): browser timezone.
- `SAVE_DEBUG_PAGES` (default `true`): saves HTML + PNG per step.
- `DEBUG_DIR` (default `debug-pages`): output folder for captures.
- `BOOKING_CONFIG_FILE` (optional): path to env file; default is `.booking.env`.

## Notes

- The script uses resilient text/label selectors and should work on many booking UIs.
- This script includes TableCheck-specific selectors for the provided Pizza 4P's page.

## Run At 10:00 AM Every Day (cron)

Edit crontab:

```bash
crontab -e
```

Add:

```cron
0 10 * * * cd /Users/tanaygupta/Documents/Playground && /Users/tanaygupta/Documents/Playground/.venv/bin/python /Users/tanaygupta/Documents/Playground/run_daily_bookings.py >> /Users/tanaygupta/Documents/Playground/booking-worker.log 2>&1
```

This runs daily at 10:00 AM local machine time.
