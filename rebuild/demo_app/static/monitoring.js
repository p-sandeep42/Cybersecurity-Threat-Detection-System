(() => {
  "use strict";
  let pending = false;
  async function refresh() {
    if (document.hidden || pending) return;
    pending = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 8000);
    const status = document.getElementById("refresh-status");
    try {
      const response = await fetch("/monitoring/status", {
        credentials: "same-origin", signal: controller.signal
      });
      if (response.status === 403) {
        clearInterval(timer);
        status.textContent = "Session expired. Sign in to the demo again.";
        return;
      }
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();
      document.querySelectorAll("[data-counter]").forEach((element) => {
        element.textContent = data.counters[element.dataset.counter];
      });
      document.getElementById("queue-size").textContent = data.queue_size;
      document.getElementById("worker-status").textContent = data.worker_alive ? "Running" : "Stopped";
      status.textContent = "Updated " + new Date().toISOString();
    } catch { status.textContent = "Update failed. Retrying in five seconds."; }
    finally { clearTimeout(timeout); pending = false; }
  }
  const timer = setInterval(refresh, 5000);
})();
