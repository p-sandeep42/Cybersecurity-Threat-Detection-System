from sqlalchemy import select

from demo_app import create_app as create_demo
from platform_app.database import get_db
from platform_app.models import Alert, Event
from tests.helpers import csrf_token, send_event


def test_demo_events_generate_evidenced_platform_alerts(app, client):
    demo = create_demo(
        {
            "TESTING": True,
            "SECRET_KEY": "separate-demo-test-secret-" * 3,
            "DEMO_PASSWORD": "synthetic-password",
            "INGESTION_KEY": "test-key",
            "START_SENDER": False,
        }
    )
    browser = demo.test_client()
    token = csrf_token(browser.get("/login"))
    sender = demo.extensions["event_sender"]
    for index in range(6):
        response = browser.post(
            "/login",
            data={
                "csrf_token": token,
                "username": "reader",
                "password": "wrong" if index < 5 else "synthetic-password",
            },
        )
        assert response.status_code == 302
        event = sender.queue.get_nowait()
        assert send_event(client, event).status_code == 201
    with app.app_context():
        database = get_db()
        assert len(database.scalars(select(Event)).all()) == 6
        alerts = database.scalars(select(Alert)).all()
        assert {alert.rule_id for alert in alerts} == {"AUTH-001", "AUTH-003"}


def test_rate_limit_has_json_error_and_retry_after(app, event_factory):
    # The rate limiter is intentionally disabled in other test fixtures.
    from platform_app import create_app

    limited = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "rate-limit-test-secret-" * 3,
            "DATABASE_URL": app.config["DATABASE_URL"],
        }
    )
    try:
        browser = limited.test_client()
        event = event_factory()
        for _ in range(120):
            assert send_event(browser, event).status_code in {200, 201}
        response = send_event(browser, event)
        assert response.status_code == 429
        assert response.json["error"]["code"] == "too_many_requests"
        assert int(response.headers["Retry-After"]) > 0
    finally:
        limited.extensions["database_engine"].dispose()
