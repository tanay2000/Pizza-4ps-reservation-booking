(function () {
  const statusEl = document.getElementById("status");
  const form = document.getElementById("booking-form");

  function setStatus(msg, ok) {
    statusEl.textContent = msg;
    statusEl.className = ok ? "ok" : "err";
  }

  if (!window.SUPABASE_URL || !window.SUPABASE_ANON_KEY) {
    setStatus("Missing Supabase config. Set SUPABASE_URL and SUPABASE_ANON_KEY in public/config.js", false);
    return;
  }

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    setStatus("Submitting...", true);

    const data = new FormData(form);
    const payload = {
      guest_name: data.get("guest_name"),
      guest_email: data.get("guest_email"),
      guest_phone: data.get("guest_phone"),
      special_request: data.get("special_request") || "",
      booking_url: data.get("booking_url"),
      guests: Number(data.get("guests") || 2),
      time_text: data.get("time_text"),
      fallback_start: data.get("fallback_start"),
      fallback_end: data.get("fallback_end"),
      slot_interval_minutes: Number(data.get("slot_interval_minutes") || 15),
      timezone: data.get("timezone"),
      auto_confirm: String(data.get("auto_confirm")).toLowerCase() === "true",
      headless: String(data.get("headless")).toLowerCase() === "true"
    };

    try {
      const res = await fetch(window.SUPABASE_URL + "/rest/v1/booking_requests", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "apikey": window.SUPABASE_ANON_KEY,
          "Authorization": "Bearer " + window.SUPABASE_ANON_KEY,
          "Prefer": "return=minimal"
        },
        body: JSON.stringify(payload)
      });
      if (!res.ok) {
        const t = await res.text();
        throw new Error(t || ("HTTP " + res.status));
      }
      form.reset();
      setStatus("Request submitted. It will run in the next daily cycle.", true);
    } catch (err) {
      setStatus("Submit failed: " + err.message, false);
    }
  });
})();
