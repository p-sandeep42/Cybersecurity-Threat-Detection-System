(() => {
  "use strict";
  const area = document.querySelector("[data-refresh-area]");
  const toggle = document.getElementById("auto-refresh");
  const status = document.getElementById("refresh-status");
  if (!area || !toggle || !status) return;
  let pending = false;
  let expired = false;
  async function refresh() {
    if (pending || expired || document.hidden || !toggle.checked) return;
    if (area.contains(document.activeElement) || area.querySelector("details[open]")) return;
    if (window.getSelection()?.toString()) return;
    pending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    area.setAttribute("aria-busy", "true");
    try {
      const response = await fetch(window.location.href, {
        credentials: "same-origin", signal: controller.signal,
        headers: { "X-Requested-With": "ThreatWatch-refresh" }
      });
      if (response.redirected || response.status === 401) {
        expired = true;
        toggle.checked = false;
        status.textContent = "Session expired. Sign in again to resume updates.";
        return;
      }
      if (!response.ok) throw new Error("Refresh failed");
      const page = new DOMParser().parseFromString(await response.text(), "text/html");
      const updated = page.querySelector("[data-refresh-area]");
      if (!updated) throw new Error("Missing refresh content");
      // Same-origin, server-rendered escaped templates; filter forms stay untouched.
      area.replaceChildren(...updated.childNodes);
      const range = document.querySelector("[data-time-range]");
      const updatedRange = page.querySelector("[data-time-range]");
      if (range && updatedRange) range.textContent = updatedRange.textContent;
      status.textContent = "Updated " + new Date().toISOString();
    } catch { status.textContent = "Update failed. Showing previous results; retrying in five seconds."; }
    finally { clearTimeout(timeout); area.removeAttribute("aria-busy"); pending = false; }
  }
  toggle.addEventListener("change", () => {
    status.textContent = toggle.checked ? "Automatic updates enabled." : "Automatic updates paused.";
    if (toggle.checked) refresh();
  });
  setInterval(refresh, 5000);
})();
