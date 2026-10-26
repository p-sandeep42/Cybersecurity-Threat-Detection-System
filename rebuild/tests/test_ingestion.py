from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from platform_app.database import get_db
from platform_app.models import Alert, Event
from tests.helpers import send_event


def test_accept_duplicate_and_conflict(client, event_factory, app):
    event = event_factory()
    assert send_event(client, event).status_code == 201
    assert send_event(client, event).json["status"] == "duplicate"
    assert send_event(client, {**event, "outcome": "success"}).status_code == 409
    with app.app_context():
        assert get_db().scalar(select(func.count()).select_from(Event)) == 1


@pytest.mark.parametrize(
    "changes",
    [
        {"schema_version": True},
        {"schema_version": "1"},
        {"subject_id": "   "},
        {"source_ip": "not-an-ip"},
        {"occurred_at": "2026-01-01T10:00:00"},
        {"response_duration_ms": -1},
        {"response_duration_ms": "12"},
        {"response_duration_ms": float("inf")},
        {"event_id": "invalid"},
        {"app_id": "forged"},
        {"interaction": {"consent": False}},
    ],
)
def test_invalid_fields_rejected(client, event_factory, changes):
    assert send_event(client, event_factory(**changes)).status_code == 422


def test_auth_body_and_time_errors(client, event_factory):
    assert send_event(client, event_factory(), key="wrong").status_code == 401
    assert client.post("/api/v1/events", json=event_factory()).status_code == 401
    headers = {"Authorization": "Bearer test-key"}
    assert client.post("/api/v1/events", data="bad", headers=headers).status_code == 415
    assert (
        client.post(
            "/api/v1/events", data="{", content_type="application/json", headers=headers
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/v1/events", data=" " * 17000, content_type="application/json", headers=headers
        ).status_code
        == 413
    )
    for delta in (timedelta(days=-2), timedelta(minutes=5)):
        timestamp = (datetime.now(UTC) + delta).isoformat()
        assert send_event(client, event_factory(occurred_at=timestamp)).status_code == 422


def test_atomic_rollback_allows_retry(client, event_factory, app, monkeypatch):
    import platform_app.ingestion as ingestion

    event = event_factory()
    original = ingestion.reconcile

    def fail(*args):
        raise RuntimeError("simulated rule failure")

    monkeypatch.setattr(ingestion, "reconcile", fail)
    assert send_event(client, event).status_code == 503
    with app.app_context():
        assert get_db().scalar(select(func.count()).select_from(Event)) == 0
    monkeypatch.setattr(ingestion, "reconcile", original)
    assert send_event(client, event).status_code == 201


def test_tenant_detection_isolation(client, event_factory, app):
    for index in range(4):
        assert send_event(client, event_factory(seconds=index)).status_code == 201
    assert send_event(client, event_factory(seconds=5), key="other-key").status_code == 201
    with app.app_context():
        assert get_db().scalar(select(func.count()).select_from(Alert)) == 0
