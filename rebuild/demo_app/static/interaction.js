/* Summaries only. Never read input values, keys, target fields or coordinates. */
(() => {
  "use strict";
  const form = document.getElementById("login-form");
  if (!form) return;
  const output = document.getElementById("interaction-summary");
  const status = document.getElementById("consent-status");
  const enableButton = document.getElementById("enable-interaction");
  const disableButton = document.getElementById("disable-interaction");
  const storageKey = "papertrail-interaction-consent";
  let controller = null;
  let state = null;

  function remember(enabled) {
    try { sessionStorage.setItem(storageKey, enabled ? "enabled" : "disabled"); }
    catch { /* Storage restrictions never prevent login. */ }
  }

  function disable() {
    if (controller) controller.abort();
    controller = null;
    state = null;
    output.value = "";
    remember(false);
    status.textContent = "Optional collection is off. Login still reports security events.";
    enableButton.disabled = false;
    disableButton.textContent = "Continue without measurements";
  }

  function enable() {
    if (controller) controller.abort();
    controller = new AbortController();
    state = {
      started: performance.now(), first: null, lastMove: -Infinity,
      moves: 0, downs: 0, types: new Set(), interrupted: document.hidden
    };
    const options = { signal: controller.signal, passive: true };
    const visible = () => state && !document.hidden;
    const firstInteraction = () => {
      if (visible() && state.first === null) state.first = performance.now() - state.started;
    };
    const pointerType = (event) => {
      if (["mouse", "touch", "pen"].includes(event.pointerType)) state.types.add(event.pointerType);
    };
    document.addEventListener("pointermove", (event) => {
      if (!visible()) return;
      const now = performance.now();
      if (now - state.lastMove < 100) return;
      state.lastMove = now;
      state.moves = Math.min(100000, state.moves + 1);
      pointerType(event);
    }, options);
    document.addEventListener("pointerdown", (event) => {
      if (!visible()) return;
      state.downs = Math.min(100000, state.downs + 1);
      pointerType(event);
      firstInteraction();
    }, options);
    document.addEventListener("keydown", firstInteraction, options);
    document.addEventListener("visibilitychange", () => { state.interrupted = true; }, options);
    remember(true);
    status.textContent = "Optional collection is on for this tab session. You can disable it anytime.";
    enableButton.disabled = true;
    disableButton.textContent = "Disable measurements";
  }

  enableButton.addEventListener("click", enable);
  disableButton.addEventListener("click", disable);
  form.addEventListener("submit", () => {
    output.value = "";
    if (!state) return;
    const elapsed = performance.now() - state.started;
    if (elapsed > 1800000) return;
    const rounded = (milliseconds) => Math.round(milliseconds / 10) * 10;
    output.value = JSON.stringify({
      version: 1, consent: true,
      pointer_type: state.types.size > 1 ? "mixed" : [...state.types][0] || "unknown",
      pointer_move_count: state.moves, pointer_down_count: state.downs,
      first_interaction_ms: state.first === null ? null : rounded(state.first),
      submit_elapsed_ms: rounded(elapsed), visibility_interrupted: state.interrupted
    });
  });
  // Back/forward cache must not restore a stale hidden payload or timing interval.
  window.addEventListener("pageshow", (event) => {
    output.value = "";
    if (!event.persisted) return;
    try {
      if (sessionStorage.getItem(storageKey) === "enabled") enable();
      else disable();
    } catch { disable(); }
  });
  try { if (sessionStorage.getItem(storageKey) === "enabled") enable(); }
  catch { /* Default remains off. */ }
})();
