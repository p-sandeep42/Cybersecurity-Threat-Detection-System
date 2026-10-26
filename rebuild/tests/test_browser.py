"""Real-browser acceptance checks. Run with RUN_BROWSER_TESTS=1 after npm ci."""

import json
import os
import time
from pathlib import Path
from threading import Thread

import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import select
from waitress import create_server

from demo_app import create_app as create_demo
from platform_app.database import get_db
from platform_app.models import Event
from tests.helpers import send_event

pytestmark = [
    pytest.mark.browser,
    pytest.mark.skipif(
        os.environ.get("RUN_BROWSER_TESTS") != "1",
        reason="Set RUN_BROWSER_TESTS=1 for real-browser checks",
    ),
]
ROOT = Path(__file__).parents[1]


@pytest.fixture
def browser_lab(app):
    platform_server = create_server(app, host="127.0.0.1", port=0)
    platform_worker = Thread(target=platform_server.run, daemon=True)
    platform_worker.start()
    platform_url = f"http://127.0.0.1:{platform_server.effective_port}"
    demo = create_demo(
        {
            "TESTING": True,
            "SECRET_KEY": "browser-demo-secret-" * 4,
            "DEMO_PASSWORD": "demo-password-123",
            "INGESTION_KEY": "test-key",
            "PLATFORM_URL": platform_url,
        }
    )
    demo_server = create_server(demo, host="127.0.0.1", port=0)
    demo_worker = Thread(target=demo_server.run, daemon=True)
    demo_worker.start()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(channel=os.environ.get("BROWSER_CHANNEL", "chrome"))
        context = browser.new_context(viewport={"width": 1440, "height": 1000})
        try:
            yield context, platform_url, f"http://127.0.0.1:{demo_server.effective_port}"
        finally:
            context.close()
            browser.close()
            demo.extensions["event_sender"].stop()
            for server, worker in ((demo_server, demo_worker), (platform_server, platform_worker)):
                server.task_dispatcher.shutdown()
                server.close()
                worker.join(timeout=2)


def axe_check(page):
    source = (ROOT / "node_modules/axe-core/axe.min.js").read_text(encoding="utf-8")
    page.evaluate(source)
    result = page.evaluate("""async () => await axe.run(document, {
        runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}
    })""")
    assert not result["violations"], json.dumps(result["violations"], indent=2)
    return {
        "url_path": page.url.split("/", 3)[-1],
        "violations": 0,
        "passed_rules": len(result["passes"]),
        "manual_review_items": len(result["incomplete"]),
    }


def stored_events(app, count):
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        with app.app_context():
            rows = list(get_db().scalars(select(Event).order_by(Event.received_at)))
        if len(rows) >= count:
            return rows
        time.sleep(0.1)
    raise AssertionError(f"Expected {count} delivered events")


def test_consent_refresh_and_accessibility(browser_lab, app, client, event_factory):
    context, platform_url, demo_url = browser_lab
    screenshots = ROOT / "reports" / "screenshots"
    screenshots.mkdir(parents=True, exist_ok=True)
    audits, errors = [], []
    owner = context.new_page()
    owner.on("pageerror", lambda error: errors.append(str(error)))
    owner.goto(platform_url + "/login")
    owner.keyboard.press("Tab")
    expect(owner.get_by_role("link", name="Skip to content")).to_be_focused()
    audits.append(axe_check(owner))
    owner.get_by_label("Login", exact=True).fill("owner")
    owner.get_by_label("Password", exact=True).fill("test-password-123")
    owner.get_by_role("button", name="Sign in", exact=True).click()
    owner.goto(f"{platform_url}/applications/{app.config['TEST_APP_ID']}/metrics")
    audits.append(axe_check(owner))

    visitor = context.new_page()
    visitor.on("pageerror", lambda error: errors.append(str(error)))
    visitor.goto(demo_url + "/login")
    audits.append(axe_check(visitor))
    visitor.screenshot(path=str(screenshots / "demo-consent-desktop.png"), full_page=True)
    visitor.get_by_label("Username", exact=True).fill("reader")
    visitor.get_by_label("Password", exact=True).fill("wrong-password")
    visitor.get_by_role("button", name="Sign in", exact=True).click()
    assert stored_events(app, 1)[0].payload["interaction"] is None

    visitor.get_by_role("button", name="Enable measurements").click()
    visitor.mouse.move(100, 150)
    visitor.keyboard.press("Tab")
    visitor.get_by_label("Username", exact=True).fill("reader")
    visitor.get_by_label("Password", exact=True).fill("wrong-password")
    visitor.get_by_role("button", name="Sign in", exact=True).click()
    summary = stored_events(app, 2)[1].payload["interaction"]
    assert summary["consent"] is True
    assert summary["pointer_move_count"] >= 1
    assert summary["first_interaction_ms"] is not None
    assert set(summary) == {
        "version",
        "consent",
        "pointer_type",
        "pointer_move_count",
        "pointer_down_count",
        "first_interaction_ms",
        "submit_elapsed_ms",
        "visibility_interrupted",
    }
    expect(visitor.get_by_role("button", name="Disable measurements")).to_be_visible()
    visitor.get_by_role("button", name="Disable measurements").click()
    visitor.get_by_label("Username", exact=True).fill("reader")
    visitor.get_by_label("Password", exact=True).fill("wrong-password")
    visitor.get_by_role("button", name="Sign in", exact=True).click()
    assert stored_events(app, 3)[2].payload["interaction"] is None

    # Refresh updates the data region while preserving unsaved filter input.
    owner.bring_to_front()
    owner.get_by_label("Exact account ID").fill("unsaved-filter")
    expect(owner.locator("#refresh-status")).to_contain_text("Updated", timeout=12000)
    expect(owner.get_by_label("Exact account ID")).to_have_value("unsaved-filter")
    owner.get_by_label("Auto-refresh every five seconds").uncheck()
    expect(owner.locator("#refresh-status")).to_contain_text("paused")
    audits.append(axe_check(owner))
    owner.screenshot(path=str(screenshots / "overview-desktop.png"), full_page=True)

    for index in range(5):
        assert send_event(client, event_factory(seconds=index)).status_code == 201
    owner.goto(f"{platform_url}/applications/{app.config['TEST_APP_ID']}/alerts")
    audits.append(axe_check(owner))
    owner.get_by_role("link", name="Repeated login failures").first.click()
    audits.append(axe_check(owner))
    owner.screenshot(path=str(screenshots / "investigation-desktop.png"), full_page=True)

    owner.set_viewport_size({"width": 390, "height": 844})
    owner.goto(f"{platform_url}/applications/{app.config['TEST_APP_ID']}/metrics")
    assert owner.evaluate("document.documentElement.scrollWidth <= innerWidth")
    audits.append(axe_check(owner))
    owner.screenshot(path=str(screenshots / "overview-mobile.png"), full_page=True)
    visitor.set_viewport_size({"width": 390, "height": 844})
    visitor.screenshot(path=str(screenshots / "demo-mobile.png"), full_page=True)
    assert visitor.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errors
    (ROOT / "reports" / "browser-checks.json").write_text(
        json.dumps(
            {
                "browser": "Chromium / " + os.environ.get("BROWSER_CHANNEL", "chrome"),
                "audits": audits,
                "javascript_errors": errors,
                "checks": [
                    "No summary before consent",
                    "Opt-in submits only allowed aggregates",
                    "Opt-out clears collection",
                    "Consent survives same-tab navigation",
                    "Keyboard skip link",
                    "Refresh preserves filter edits",
                    "Refresh can be paused",
                    "390px layout has no page-level horizontal overflow",
                ],
                "limits": "These automated checks are not a full accessibility certification.",
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def test_keyboard_touch_visibility_and_expired_refresh(browser_lab, app):
    context, platform_url, demo_url = browser_lab
    keyboard = context.new_page()
    keyboard.goto(demo_url + "/login")
    keyboard.get_by_role("button", name="Enable measurements").focus()
    keyboard.keyboard.press("Enter")
    keyboard.get_by_label("Username", exact=True).focus()
    keyboard.keyboard.type("reader")
    keyboard.keyboard.press("Tab")
    keyboard.keyboard.type("wrong-password")
    keyboard.keyboard.press("Enter")
    first = stored_events(app, 1)[0].payload["interaction"]
    assert first["pointer_type"] == "unknown" and first["pointer_move_count"] == 0
    assert first["first_interaction_ms"] is not None

    # Model a visibility transition and confirm hidden pointer events are ignored.
    keyboard.evaluate("""() => {
        Object.defineProperty(document, 'hidden', {configurable: true, value: true});
        document.dispatchEvent(new Event('visibilitychange'));
        document.dispatchEvent(new PointerEvent('pointermove', {pointerType: 'mouse'}));
        Object.defineProperty(document, 'hidden', {configurable: true, value: false});
        document.dispatchEvent(new Event('visibilitychange'));
    }""")
    keyboard.get_by_label("Username", exact=True).fill("reader")
    keyboard.get_by_label("Password", exact=True).fill("wrong-password")
    keyboard.get_by_label("Password", exact=True).press("Enter")
    second = stored_events(app, 2)[1].payload["interaction"]
    assert second["visibility_interrupted"] and second["pointer_move_count"] == 0

    # A restored cached page must honor a more recent opt-out.
    keyboard.evaluate("""() => {
        sessionStorage.setItem('papertrail-interaction-consent', 'disabled');
        window.dispatchEvent(new PageTransitionEvent('pageshow', {persisted: true}));
    }""")
    expect(keyboard.locator("#consent-status")).to_contain_text("off")

    touch_context = context.browser.new_context(
        viewport={"width": 390, "height": 844},
        has_touch=True,
        is_mobile=True,
    )
    try:
        touch = touch_context.new_page()
        touch.goto(demo_url + "/login")
        touch.get_by_role("button", name="Enable measurements").tap()
        touch.get_by_label("Username", exact=True).fill("reader")
        touch.get_by_label("Password", exact=True).fill("wrong-password")
        touch.get_by_role("button", name="Sign in", exact=True).tap()
        third = stored_events(app, 3)[2].payload["interaction"]
        assert third["pointer_type"] == "touch"
        assert third["pointer_down_count"] >= 1
        axe_check(touch)
    finally:
        touch_context.close()

    owner = context.new_page()
    owner.goto(platform_url + "/login")
    owner.get_by_label("Login", exact=True).fill("owner")
    owner.get_by_label("Password", exact=True).fill("test-password-123")
    owner.get_by_role("button", name="Sign in", exact=True).click()
    owner.goto(f"{platform_url}/applications/{app.config['TEST_APP_ID']}/metrics")
    requests_seen = []
    owner.on("request", lambda request: requests_seen.append(request.url))
    owner.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: true})")
    owner.wait_for_timeout(5500)
    assert not requests_seen
    owner.evaluate("Object.defineProperty(document, 'hidden', {configurable: true, value: false})")
    context.clear_cookies(name="threatwatch_owner")
    expect(owner.locator("#refresh-status")).to_contain_text("Session expired", timeout=12000)
    assert not owner.get_by_label("Auto-refresh every five seconds").is_checked()
    (ROOT / "reports" / "browser-edge-checks.json").write_text(
        json.dumps(
            {
                "checks": [
                    "Keyboard-only summary",
                    "Touch summary",
                    "Hidden events ignored",
                    "Visibility-interrupted interval labeled",
                    "Cached-page opt-out preserved",
                    "Refresh paused when hidden",
                    "Expired-session refresh stops",
                ],
                "result": "passed",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
