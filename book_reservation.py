import os
import re
from datetime import datetime, timedelta
from pathlib import Path

from playwright.sync_api import Page, sync_playwright


def env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


CONFIG = {
    "url": env(
        "BOOKING_URL",
        "https://www.tablecheck.com/en/pizza-4ps-in-indiranagar/reserve/message",
    ),
    "guests": int(env("GUESTS", "2")),
    "time_text": env("TIME_TEXT", "8:00 PM"),
    "fallback_start": env("FALLBACK_START", "8:00 PM"),
    "fallback_end": env("FALLBACK_END", "10:00 PM"),
    "slot_interval_minutes": int(env("SLOT_INTERVAL_MINUTES", "15")),
    "headless": env("HEADLESS", "true").lower() == "true",
    "timezone": env("TIMEZONE", "Asia/Kolkata"),
    "guest_name": env("GUEST_NAME", "Tanay Gupta"),
    "guest_email": env("GUEST_EMAIL", "tanaygupta2000@gmail.com"),
    "guest_phone": env("GUEST_PHONE", "+91 9057222901"),
    "special_request": env("SPECIAL_REQUEST", ""),
    "auto_confirm": env("AUTO_CONFIRM", "true").lower() == "true",
    "save_debug_pages": env("SAVE_DEBUG_PAGES", "true").lower() == "true",
    "debug_dir": env("DEBUG_DIR", "debug-pages"),
}


def next_week_same_weekday(now: datetime | None = None) -> datetime:
    base = now or datetime.now()
    return base + timedelta(days=7)


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def dump_debug_page(page: Page, stage: str) -> None:
    if not CONFIG["save_debug_pages"]:
        return
    out = Path(CONFIG["debug_dir"])
    out.mkdir(parents=True, exist_ok=True)
    prefix = slug(stage)
    html_path = out / f"{prefix}.html"
    png_path = out / f"{prefix}.png"
    meta_path = out / f"{prefix}.txt"
    try:
        html_path.write_text(page.content(), encoding="utf-8")
        page.screenshot(path=str(png_path), full_page=True)
        # Capture visible interactive text to debug dynamic UI states
        visible_controls = []
        for sel in ["[data-testid]", "button", "a", "[role='button']", "[role='option']"]:
            loc = page.locator(sel)
            total = min(loc.count(), 220)
            for i in range(total):
                el = loc.nth(i)
                try:
                    if not el.is_visible(timeout=80):
                        continue
                    txt = (el.inner_text() or "").strip().replace("\n", " ")
                    tid = el.get_attribute("data-testid") or ""
                    if txt or tid:
                        visible_controls.append(f"{sel} | testid={tid} | text={txt[:100]}")
                except Exception:
                    pass
        unique_controls = []
        for line in visible_controls:
            if line not in unique_controls:
                unique_controls.append(line)

        meta = [f"URL: {page.url}", f"Title: {page.title()}", ""]
        meta.append("Visible controls:")
        meta.extend(unique_controls[:200])
        meta_path.write_text("\n".join(meta) + "\n", encoding="utf-8")
    except Exception:
        pass


def fmt_iso(d: datetime) -> str:
    return d.strftime("%Y-%m-%d")


def fmt_us(d: datetime) -> str:
    return d.strftime("%m/%d/%Y")


def click_first_visible(candidates) -> bool:
    for locator in candidates:
        try:
            if locator.first.is_visible(timeout=500):
                try:
                    locator.first.click(timeout=1500)
                    return True
                except Exception:
                    locator.first.click(timeout=1500, force=True)
                    return True
        except Exception:
            pass
    return False


def fill_first_visible(candidates, value: str) -> bool:
    if not value:
        return False
    for locator in candidates:
        try:
            if locator.first.is_visible(timeout=500):
                locator.first.fill(value)
                return True
        except Exception:
            pass
    return False


def split_full_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in full_name.strip().split() if p]
    if not parts:
        return "", ""
    if len(parts) == 1:
        return parts[0], ""
    return parts[0], " ".join(parts[1:])


def any_visible(candidates) -> bool:
    for locator in candidates:
        try:
            if locator.first.is_visible(timeout=500):
                return True
        except Exception:
            pass
    return False


def parse_time_to_minutes(text: str) -> int | None:
    m12 = re.search(r"(\d{1,2}):(\d{2})\s*([AaPp][Mm])", text)
    if m12:
        hour = int(m12.group(1)) % 12
        minute = int(m12.group(2))
        meridiem = m12.group(3).upper()
        if meridiem == "PM":
            hour += 12
        return hour * 60 + minute

    m24 = re.search(r"\b([01]?\d|2[0-3]):([0-5]\d)\b", text)
    if m24:
        return int(m24.group(1)) * 60 + int(m24.group(2))
    return None


def find_available_slot(page: Page, start_text: str, end_text: str, step_minutes: int) -> str | None:
    start_mins = parse_time_to_minutes(start_text)
    end_mins = parse_time_to_minutes(end_text)
    if start_mins is None or end_mins is None:
        return None

    candidates = []
    items = page.locator("button, [role='button'], a")
    total = min(items.count(), 250)
    for i in range(total):
        item = items.nth(i)
        try:
            if not item.is_visible(timeout=250):
                continue
            text = (item.inner_text() or "").strip()
            mins = parse_time_to_minutes(text)
            if mins is None:
                continue
            if start_mins <= mins <= end_mins and ((mins - start_mins) % step_minutes == 0):
                candidates.append((mins, text))
        except Exception:
            continue

    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])
    return candidates[0][1]


def set_guests(page: Page, guests: int) -> None:
    # TableCheck popup flow: click "Guests" button, adjust adults with +/- and confirm.
    opened_popup = click_first_visible(
        [
            page.get_by_role("button", name=re.compile(r"guests?", re.I)),
            page.get_by_text(re.compile(r"\d+\s*Guests?", re.I)),
        ]
    )
    if opened_popup:
        page.wait_for_timeout(250)
        confirm_btn = page.get_by_role("button", name=re.compile(r"^confirm$", re.I)).first
        try:
            if confirm_btn.is_visible(timeout=700):
                minus_btn = page.locator("button:has-text('-'), button:has-text('−')").first
                plus_btn = page.locator("button:has-text('+')").first

                # Normalize adults count to 1, then increment to target.
                for _ in range(8):
                    try:
                        if minus_btn.is_visible(timeout=300):
                            minus_btn.click(timeout=1000)
                            page.wait_for_timeout(60)
                    except Exception:
                        break

                for _ in range(max(guests - 1, 0)):
                    try:
                        if plus_btn.is_visible(timeout=300):
                            plus_btn.click(timeout=1000)
                            page.wait_for_timeout(60)
                    except Exception:
                        break

                confirm_btn.click(timeout=1500)
                page.wait_for_timeout(300)
                return
        except Exception:
            pass

    adults_combo = page.get_by_role("combobox", name=re.compile(r"adults?", re.I)).first
    try:
        if adults_combo.is_visible(timeout=500):
            adults_combo.select_option(str(guests))
            return
    except Exception:
        pass

    click_first_visible(
        [
            page.get_by_role("option", name=str(guests), exact=True),
            page.get_by_text(re.compile(rf"^\s*{guests}\s*$")),
        ]
    )


def set_date(page: Page, target: datetime) -> None:
    iso = fmt_iso(target)
    us = fmt_us(target)
    day = str(target.day)

    for inp in [
        page.get_by_label(re.compile(r"date", re.I)).first,
        page.locator("input[type='date']").first,
        page.locator("input[name*='date' i], input[id*='date' i]").first,
    ]:
        try:
            if inp.is_visible(timeout=500):
                try:
                    inp.fill(iso)
                except Exception:
                    inp.fill(us)
                return
        except Exception:
            pass

    # TableCheck popup flow: open date picker and click target day (+7 same weekday).
    click_first_visible(
        [
            page.locator("[data-testid='Landing Date Panel Opener Button']"),
            page.get_by_role("button", name=re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)\b", re.I)),
            page.get_by_role("link", name=re.compile(r"\b(mon|tue|wed|thu|fri|sat|sun)\b", re.I)),
            page.get_by_role("button", name=re.compile(r"select a date|date", re.I)),
        ]
    )
    page.wait_for_timeout(250)
    dump_debug_page(page, "04a_date_panel_opened")

    panel = page.locator("[data-testid='Bottom Panel']").first
    title = page.locator("[data-testid='Bottom Panel Title']").first
    try:
        if panel.is_visible(timeout=700) and title.is_visible(timeout=700):
            if not re.search(r"select a date", (title.inner_text() or "").strip(), re.I):
                return

            # Wait for skeleton to resolve into day buttons.
            for _ in range(40):
                if panel.locator("[data-testid='day']").count() > 0:
                    break
                page.wait_for_timeout(100)
            dump_debug_page(page, "04b_date_panel_loaded")

            month_label = target.strftime("%b %Y")
            # Move month view until target month/year is visible.
            for _ in range(12):
                if panel.get_by_text(re.compile(rf"^{re.escape(month_label)}$", re.I)).first.is_visible(
                    timeout=250
                ):
                    break
                if not click_first_visible(
                    [
                        panel.locator("[data-testid='Calendar Next Month Button']"),
                        panel.get_by_role("button", name=re.compile(r"next|>|›", re.I)),
                    ]
                ):
                    break
                page.wait_for_timeout(120)

            day_btns = panel.locator("[data-testid='day']").filter(
                has_text=re.compile(rf"^{target.day}$")
            )
            count = day_btns.count()
            for i in range(count):
                btn = day_btns.nth(i)
                try:
                    aria = (btn.get_attribute("aria-label") or "").strip()
                    if btn.is_visible(timeout=200) and not btn.is_disabled(timeout=200):
                        if target.strftime("%A").lower() not in aria.lower():
                            continue
                        btn.click(timeout=1200)
                        page.wait_for_timeout(200)
                        return
                except Exception:
                    pass
    except Exception:
        pass

    opened = click_first_visible(
        [
            page.get_by_role("button", name=re.compile(r"date|calendar|today", re.I)),
            page.get_by_role("link", name=re.compile(r"date|calendar|today", re.I)),
            page.get_by_label(re.compile(r"date|calendar", re.I)),
        ]
    )
    if not opened:
        return

    click_first_visible(
        [
            page.get_by_role("gridcell", name=re.compile(rf"\b{day}\b")),
            page.get_by_role("button", name=re.compile(rf"\b{day}\b")),
            page.get_by_role("link", name=re.compile(rf"\b{day}\b")),
            page.locator(f"[aria-label*='{iso}']"),
            page.locator(f"[aria-label*='{us}']"),
        ]
    )


def set_time(page: Page, time_text: str) -> bool:
    time_combo = page.get_by_role("combobox", name=re.compile(r"time", re.I)).first
    try:
        if time_combo.is_visible(timeout=500):
            try:
                time_combo.select_option(label=time_text)
                return True
            except Exception:
                time_combo.click()
                page.get_by_role("option", name=re.compile(re.escape(time_text), re.I)).first.click()
                return True
    except Exception:
        pass

    if click_first_visible(
        [
            page.get_by_role("option", name=re.compile(re.escape(time_text), re.I)),
            page.get_by_role("button", name=re.compile(re.escape(time_text), re.I)),
            page.get_by_role("link", name=re.compile(re.escape(time_text), re.I)),
            page.get_by_text(re.compile(rf"^\s*{re.escape(time_text)}\s*$", re.I)),
        ]
    ):
        return True

    # TableCheck-style popup flow ("Select a time" modal with 15-min buttons).
    click_first_visible(
        [
            page.locator("[data-testid='Landing Time Panel Opener Button']"),
            page.get_by_role("button", name=re.compile(r"select a time|time", re.I)),
            page.get_by_role("link", name=re.compile(r"select a time|time", re.I)),
        ]
    )
    page.wait_for_timeout(250)
    dump_debug_page(page, "05a_time_panel_opened")
    panel = page.locator("[data-testid='Bottom Panel']").first
    title = page.locator("[data-testid='Bottom Panel Title']").first
    in_time_panel = False
    try:
        in_time_panel = panel.is_visible(timeout=500) and title.is_visible(timeout=500) and re.search(
            r"select a time", (title.inner_text() or "").strip(), re.I
        )
    except Exception:
        in_time_panel = False
    scope = panel if in_time_panel else page

    if in_time_panel:
        # Wait for skeleton to resolve into slot buttons.
        for _ in range(40):
            if panel.locator("[data-testid='Landing Time Button']").count() > 0:
                break
            page.wait_for_timeout(100)
        dump_debug_page(page, "05b_time_panel_loaded")

    if click_first_visible(
        [
            scope.locator("[data-testid='Landing Time Button']").filter(
                has_text=re.compile(rf"^\s*{re.escape(time_text)}\s*$", re.I)
            ),
            scope.get_by_role("button", name=re.compile(rf"^\s*{re.escape(time_text)}\s*$", re.I)),
            scope.get_by_role("link", name=re.compile(rf"^\s*{re.escape(time_text)}\s*$", re.I)),
            scope.get_by_text(re.compile(rf"^\s*{re.escape(time_text)}\s*$", re.I)),
        ]
    ):
        return True

    start_mins = parse_time_to_minutes(CONFIG["fallback_start"])
    end_mins = parse_time_to_minutes(CONFIG["fallback_end"])
    if start_mins is None or end_mins is None:
        return False

    slot_candidates = []
    items = scope.locator("[data-testid='Landing Time Button'], button, a, [role='button']")
    total = min(items.count(), 260)
    for i in range(total):
        item = items.nth(i)
        try:
            if not item.is_visible(timeout=150):
                continue
            txt = (item.inner_text() or "").strip()
            mins = parse_time_to_minutes(txt)
            if mins is None:
                continue
            if start_mins <= mins <= end_mins and ((mins - start_mins) % CONFIG["slot_interval_minutes"] == 0):
                slot_candidates.append((mins, txt))
        except Exception:
            continue

    if not slot_candidates:
        return False

    slot_candidates.sort(key=lambda x: x[0])
    chosen = slot_candidates[0][1]
    return click_first_visible(
        [
            scope.get_by_role("button", name=re.compile(rf"^\s*{re.escape(chosen)}\s*$", re.I)),
            scope.get_by_role("link", name=re.compile(rf"^\s*{re.escape(chosen)}\s*$", re.I)),
            scope.get_by_text(re.compile(rf"^\s*{re.escape(chosen)}\s*$", re.I)),
        ]
    )


def select_availability(page: Page) -> None:
    page.wait_for_timeout(1200)

    # If already on details form, no slot click is needed.
    details_ready = any_visible(
        [
            page.get_by_label(re.compile(r"full name|name", re.I)),
            page.get_by_label(re.compile(r"e-?mail", re.I)),
            page.get_by_label(re.compile(r"phone|mobile|tel", re.I)),
        ]
    )
    if details_ready:
        return

    slot_text = find_available_slot(
        page,
        CONFIG["fallback_start"],
        CONFIG["fallback_end"],
        CONFIG["slot_interval_minutes"],
    )
    if not slot_text:
        # TableCheck availability page sometimes shows explicit no-availability state.
        if any_visible(
            [
                page.get_by_text(re.compile(r"there is no availability for your chosen time", re.I)),
                page.get_by_text(re.compile(r"no other availability found", re.I)),
                page.get_by_text(re.compile(r"other dates with availability", re.I)),
                page.locator("[data-testid='Availability Page']"),
            ]
        ):
            raise RuntimeError(
                "Reached /reserve/availability but no slot is available in the requested window."
            )

        if any_visible(
            [
                page.get_by_label(re.compile(r"full name|name", re.I)),
                page.get_by_label(re.compile(r"e-?mail", re.I)),
                page.get_by_label(re.compile(r"phone|mobile|tel", re.I)),
            ]
        ):
            return
        raise RuntimeError(
            f"No visible slot found between {CONFIG['fallback_start']} and {CONFIG['fallback_end']}."
        )

    clicked = click_first_visible(
        [
            page.get_by_role("button", name=re.compile(rf"^\s*{re.escape(slot_text)}\s*$", re.I)),
            page.get_by_role("link", name=re.compile(rf"^\s*{re.escape(slot_text)}\s*$", re.I)),
            page.get_by_text(re.compile(rf"^\s*{re.escape(slot_text)}\s*$", re.I)),
        ]
    )
    if not clicked:
        raise RuntimeError(f"Could not click slot: {slot_text}")
    print(f"Selected availability slot: {slot_text}")

    click_first_visible(
        [
            page.get_by_role("button", name=re.compile(r"next|continue", re.I)),
            page.get_by_role("button", name=re.compile(r"enter your details", re.I)),
            page.get_by_text(re.compile(r"next|continue", re.I)),
        ]
    )
    page.wait_for_timeout(1000)


def is_details_page(page: Page) -> bool:
    if "/reserve/review" in page.url:
        return True
    return any_visible(
        [
            page.get_by_label(re.compile(r"first name", re.I)),
            page.get_by_label(re.compile(r"last name|surname|family name", re.I)),
            page.get_by_label(re.compile(r"e-?mail", re.I)),
            page.get_by_label(re.compile(r"phone|mobile|tel", re.I)),
        ]
    )


def fill_guest_details(page: Page) -> None:
    first_name, last_name = split_full_name(CONFIG["guest_name"])

    first_name_visible = any_visible(
        [
            page.get_by_label(re.compile(r"first name", re.I)),
            page.locator("input[name*='first' i], input[id*='first' i]"),
        ]
    )
    last_name_visible = any_visible(
        [
            page.get_by_label(re.compile(r"last name|surname|family name", re.I)),
            page.locator("input[name*='last' i], input[id*='last' i], input[name*='family' i]"),
        ]
    )

    ok_name = True
    if first_name_visible or last_name_visible:
        ok_first = fill_first_visible(
            [
                page.get_by_label(re.compile(r"first name", re.I)),
                page.locator("input[name*='first' i], input[id*='first' i]"),
            ],
            first_name or CONFIG["guest_name"],
        )
        ok_last = fill_first_visible(
            [
                page.get_by_label(re.compile(r"last name|surname|family name", re.I)),
                page.locator("input[name*='last' i], input[id*='last' i], input[name*='family' i]"),
            ],
            last_name or "Guest",
        )
        ok_name = ok_first and ok_last
    else:
        ok_name = fill_first_visible(
            [
                page.get_by_label(re.compile(r"full name|name", re.I)),
                page.locator("input[name*='name' i], input[id*='name' i]"),
            ],
            CONFIG["guest_name"],
        )

    ok_email = fill_first_visible(
        [
            page.get_by_label(re.compile(r"e-?mail", re.I)),
            page.locator("input[type='email'], input[name*='email' i], input[id*='email' i]"),
        ],
        CONFIG["guest_email"],
    )

    ok_phone = fill_first_visible(
        [
            page.get_by_label(re.compile(r"phone|mobile|tel", re.I)),
            page.locator("input[type='tel'], input[name*='phone' i], input[id*='phone' i]"),
        ],
        CONFIG["guest_phone"],
    )

    fill_first_visible(
        [
            page.get_by_label(re.compile(r"special request|request|note|message", re.I)),
            page.locator("textarea"),
        ],
        CONFIG["special_request"],
    )

    if not (ok_name and ok_email and ok_phone):
        raise RuntimeError("Could not fill one or more required guest fields (name/email/phone).")

    click_first_visible(
        [
            page.get_by_role("button", name=re.compile(r"next|continue|review", re.I)),
            page.get_by_role("button", name=re.compile(r"continue to book", re.I)),
            page.get_by_text(re.compile(r"next|continue|review", re.I)),
        ]
    )
    page.wait_for_timeout(1200)


def confirm_booking(page: Page) -> None:
    if not CONFIG["auto_confirm"]:
        print("AUTO_CONFIRM=false, stopped before final confirmation.")
        return

    clicked = click_first_visible(
        [
            page.get_by_role("button", name=re.compile(r"confirm booking", re.I)),
            page.get_by_role("button", name=re.compile(r"make reservation", re.I)),
            page.get_by_role("button", name=re.compile(r"confirm", re.I)),
            page.get_by_text(re.compile(r"confirm booking|make reservation", re.I)),
        ]
    )
    if not clicked:
        raise RuntimeError("Could not find final confirm booking button.")

    page.wait_for_timeout(2000)
    print("Final confirm clicked.")


def run() -> None:
    target = next_week_same_weekday()
    print(
        f"Booking for {target.strftime('%a, %d %b %Y')} around "
        f"{CONFIG['fallback_start']} to {CONFIG['fallback_end']}"
    )

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=CONFIG["headless"])
        context = browser.new_context(timezone_id=CONFIG["timezone"])
        page = context.new_page()
        page.goto(CONFIG["url"], wait_until="domcontentloaded", timeout=60_000)
        dump_debug_page(page, "01_message_page")

        # Page 1: message/terms page (TableCheck)
        _ = click_first_visible(
            [
                page.locator("[data-testid='Message Page'] input[type='checkbox']"),
                page.get_by_role(
                    "checkbox",
                    name=re.compile(r"i confirm i've read the message from venue above", re.I),
                ),
                page.get_by_label(
                    re.compile(r"i confirm i've read the message from venue above", re.I)
                ),
            ]
        )

        moved_to_landing = False
        for _ in range(4):
            click_first_visible(
                [
                    page.locator("[data-testid='Footer Button']"),
                    page.get_by_role("button", name=re.compile(r"confirm and continue", re.I)),
                    page.get_by_role("button", name=re.compile(r"continue", re.I)),
                    page.get_by_role("button", name=re.compile(r"^next$", re.I)),
                ]
            )
            page.wait_for_timeout(800)
            if "/reserve/landing" in page.url:
                moved_to_landing = True
                break
        if not moved_to_landing:
            dump_debug_page(page, "01b_failed_to_reach_landing")
            browser.close()
            raise RuntimeError("Could not move from message page to landing page.")

        dump_debug_page(page, "02_after_continue")
        set_guests(page, CONFIG["guests"])
        dump_debug_page(page, "03_after_guests")
        set_date(page, target)
        dump_debug_page(page, "04_after_date")
        if not set_time(page, CONFIG["time_text"]):
            browser.close()
            raise RuntimeError(
                f"Could not set a time in range {CONFIG['fallback_start']} - {CONFIG['fallback_end']}."
            )
        dump_debug_page(page, "05_after_time")
        # Close any open popovers before submitting search.
        try:
            page.keyboard.press("Escape")
        except Exception:
            pass
        page.wait_for_timeout(250)

        ok = click_first_visible(
            [
                page.locator("[data-testid='Landing Find A Table Button']"),
                page.get_by_role("button", name=re.compile(r"find availability|find a table", re.I)),
                page.get_by_role("button", name=re.compile(r"^availability$", re.I)),
                page.get_by_role("link", name=re.compile(r"find availability|find a table", re.I)),
                page.get_by_text(re.compile(r"find availability|find a table", re.I)),
                page.get_by_text(re.compile(r"^availability$", re.I)),
            ]
        )
        if not ok:
            ok = click_first_visible(
                [
                    page.locator("button:has-text('Find availability')"),
                    page.locator("a:has-text('Find availability')"),
                    page.locator("button:has-text('Availability')"),
                    page.locator("a:has-text('Availability')"),
                ]
            )

        if not ok:
            browser.close()
            raise RuntimeError("Could not find availability button.")

        print("Submitted availability search.")
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(800)
        print(f"Post-search page: {page.url}")
        dump_debug_page(page, "06_after_find_availability")
        if is_details_page(page):
            print("Reached details page directly after availability search.")
        else:
            select_availability(page)
            dump_debug_page(page, "07_after_slot_selection")
        fill_guest_details(page)
        dump_debug_page(page, "08_after_guest_details")
        confirm_booking(page)
        dump_debug_page(page, "09_after_confirm")
        print("Booking flow completed.")
        browser.close()


if __name__ == "__main__":
    run()
