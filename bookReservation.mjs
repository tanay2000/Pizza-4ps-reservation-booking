import { chromium } from "playwright";

const config = {
  url:
    process.env.BOOKING_URL ||
    "https://www.tablecheck.com/en/pizza-4ps-in-indiranagar/reserve/message",
  guests: Number(process.env.GUESTS || "2"),
  // Reservation time target.
  timeText: process.env.TIME_TEXT || "8:00 PM",
  headless: (process.env.HEADLESS || "false").toLowerCase() === "true",
  timezoneId: process.env.TIMEZONE || "Asia/Kolkata",
};

if (!config.url) {
  throw new Error(
    "Missing BOOKING_URL. Example: BOOKING_URL='https://example.com/reservations' npm run book"
  );
}

function nextWeekSameWeekdayDate(now = new Date()) {
  const d = new Date(now);
  d.setDate(d.getDate() + 7);
  return d;
}

function formatAsIsoDate(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function formatAsUsDate(date) {
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  const y = date.getFullYear();
  return `${m}/${d}/${y}`;
}

async function clickFirstVisible(page, candidates) {
  for (const locator of candidates) {
    if (await locator.first().isVisible().catch(() => false)) {
      await locator.first().click();
      return true;
    }
  }
  return false;
}

async function setGuests(page, guests) {
  // TableCheck commonly uses "Adults" as the party-size field.
  const adultsCombo = page.getByRole("combobox", { name: /adults?/i }).first();
  if (await adultsCombo.isVisible().catch(() => false)) {
    try {
      await adultsCombo.selectOption(String(guests));
      return;
    } catch {
      await adultsCombo.click();
      await page.getByRole("option", { name: String(guests), exact: true }).first().click();
      return;
    }
  }

  const directGuestOption = page.getByRole("option", { name: String(guests), exact: true });
  if (await directGuestOption.first().isVisible().catch(() => false)) {
    await directGuestOption.first().click();
    return;
  }

  const guestsCombo = page
    .getByRole("combobox", { name: /guest/i })
    .or(page.locator("select[name*='guest' i], select[id*='guest' i]"))
    .first();
  if (await guestsCombo.isVisible().catch(() => false)) {
    try {
      await guestsCombo.selectOption(String(guests));
    } catch {
      await guestsCombo.click();
      await page.getByRole("option", { name: String(guests), exact: true }).first().click();
    }
    return;
  }

  // Fallback: buttons like + / - for party size.
  const plusButton = page.getByRole("button", { name: /increase|plus|\+/i }).first();
  const guestsText = page.getByText(new RegExp(`\\b${guests}\\s*guest`, "i")).first();
  if (await plusButton.isVisible().catch(() => false)) {
    for (let i = 0; i < 6; i += 1) {
      if (await guestsText.isVisible().catch(() => false)) return;
      await plusButton.click();
      await page.waitForTimeout(150);
    }
  }
}

async function setDate(page, dateObj) {
  const iso = formatAsIsoDate(dateObj);
  const us = formatAsUsDate(dateObj);
  const day = String(dateObj.getDate());
  const longFmt = dateObj.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const dateInputCandidates = [
    page.getByLabel(/date/i).first(),
    page.locator("input[type='date']").first(),
    page.locator("input[name*='date' i], input[id*='date' i]").first(),
  ];

  for (const input of dateInputCandidates) {
    if (await input.isVisible().catch(() => false)) {
      try {
        await input.fill(iso);
      } catch {
        await input.click();
        await input.fill(us);
      }
      return;
    }
  }

  // Date picker fallback.
  const opened = await clickFirstVisible(page, [
    page.getByRole("button", { name: /date|calendar|select date|today/i }),
    page.getByRole("link", { name: /date|calendar|select date|today/i }),
    page.getByLabel(/date|calendar/i),
  ]);

  if (!opened) return;

  await clickFirstVisible(page, [
    page.getByRole("gridcell", { name: new RegExp(`\\b${day}\\b`) }),
    page.getByRole("button", { name: new RegExp(`\\b${day}\\b`) }),
    page.getByRole("link", { name: new RegExp(`\\b${day}\\b`) }),
    page.locator(`[aria-label*='${iso}']`),
    page.locator(`[aria-label*='${us}']`),
    page.locator(`[aria-label*='${longFmt}']`),
  ]);
}

async function setTime(page, timeText) {
  const timeCombo = page.getByRole("combobox", { name: /time/i }).first();
  if (await timeCombo.isVisible().catch(() => false)) {
    try {
      await timeCombo.selectOption({ label: timeText });
      return;
    } catch {
      await timeCombo.click();
      await page.getByRole("option", { name: new RegExp(timeText, "i") }).first().click();
      return;
    }
  }

  const timeInputCandidates = [
    page.getByLabel(/time/i).first(),
    page.locator("input[type='time']").first(),
    page.locator("input[name*='time' i], input[id*='time' i]").first(),
  ];

  for (const input of timeInputCandidates) {
    if (await input.isVisible().catch(() => false)) {
      await input.click();
      await input.fill(timeText);
      return;
    }
  }

  await clickFirstVisible(page, [
    page.getByRole("option", { name: new RegExp(timeText, "i") }),
    page.getByRole("button", { name: new RegExp(timeText, "i") }),
    page.getByText(new RegExp(`^\\s*${timeText}\\s*$`, "i")),
  ]);
}

async function run() {
  const nextWeekDate = nextWeekSameWeekdayDate();
  console.log(
    `Booking for ${nextWeekDate.toDateString()} at ${config.timeText} (timezone: ${config.timezoneId})`
  );

  const browser = await chromium.launch({ headless: config.headless });
  const context = await browser.newContext({ timezoneId: config.timezoneId });
  const page = await context.newPage();

  try {
    await page.goto(config.url, { waitUntil: "domcontentloaded", timeout: 60_000 });

    // TableCheck message confirmation checkbox.
    await clickFirstVisible(page, [
      page.getByRole("checkbox", { name: /i confirm i've read the message from venue above/i }),
      page.getByLabel(/i confirm i've read the message from venue above/i),
    ]);

    // Page 1: Confirm and continue
    await clickFirstVisible(page, [
      page.getByRole("button", { name: /confirm and continue/i }),
      page.getByRole("button", { name: /continue/i }),
      page.getByRole("button", { name: /^next$/i }),
      page.getByText(/confirm and continue/i),
    ]);

    await page.waitForLoadState("domcontentloaded");
    await page.waitForTimeout(500);

    // Page 2: Guests, date, time, then find availability
    await setGuests(page, config.guests);
    await setDate(page, nextWeekDate);
    await setTime(page, config.timeText);

    const clicked = await clickFirstVisible(page, [
      page.getByRole("button", { name: /find availability/i }),
      page.getByRole("button", { name: /^availability$/i }),
      page.getByText(/find availability/i),
      page.getByText(/^availability$/i),
    ]);

    if (!clicked) {
      throw new Error("Could not find a 'Find availability' button/link.");
    }

    await page.waitForLoadState("domcontentloaded");
    console.log("Successfully submitted availability search.");
  } finally {
    if (process.env.KEEP_OPEN !== "true") {
      await browser.close();
    } else {
      console.log("KEEP_OPEN=true, leaving browser open.");
    }
  }
}

run().catch((err) => {
  console.error(err);
  process.exit(1);
});
