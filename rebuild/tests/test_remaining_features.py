"""Acceptance tests for telemetry, experimental detection, counters and retention."""

import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, select

from demo_app import create_app as create_demo
from platform_app.database import get_db
from platform_app.detection import evaluate
from platform_app.models import Alert, AlertEvent, AuditEntry, Event, IngestionReceipt, Note
from platform_app.schemas import Interaction
from tests.helpers import csrf_token, send_event, sign_in


def summary(**changes):
    result = {
        "version": 1,
        "consent": True,
        "pointer_type": "unknown",
        "pointer_move_count": 0,
        "pointer_down_count": 0,
        "first_interaction_ms": None,
        "submit_elapsed_ms": 300,
        "visibility_interrupted": False,
    }
    result.update(changes)
    return result


def bot_alerts(events):
    return [episode for episode in evaluate(events) if episode.rule_id == "BOT-001"]


def test_bot_threshold_percent_boundary_and_no_pointer_dependency(event_factory):
    session_id = str(uuid4())
    events = [
        event_factory(
            seconds=index,
            session_id=session_id,
            outcome="success",
            interaction=summary(submit_elapsed_ms=500 if index < 8 else 600),
        )
        for index in range(10)
    ]
    assert not bot_alerts(events[:9])
    assert len(bot_alerts(events)) == 1
    events[0]["interaction"]["submit_elapsed_ms"] = 510
    assert not bot_alerts(events)


@pytest.mark.parametrize(
    "interaction", [None, summary(visibility_interrupted=True), summary(submit_elapsed_ms=2000)]
)
def test_missing_interrupted_or_slow_summaries_are_not_bot_evidence(event_factory, interaction):
    session_id = str(uuid4())
    events = [
        event_factory(
            seconds=index, session_id=session_id, outcome="success", interaction=interaction
        )
        for index in range(12)
    ]
    assert not bot_alerts(events)


def test_bot_window_and_independent_sessions(event_factory):
    session_id = str(uuid4())
    events = [
        event_factory(
            seconds=index, session_id=session_id, outcome="success", interaction=summary()
        )
        for index in range(9)
    ]
    last = event_factory(
        seconds=60, session_id=session_id, outcome="success", interaction=summary()
    )
    assert len(bot_alerts([*events, last])) == 1
    assert not bot_alerts(
        [
            *events,
            event_factory(
                seconds=60.001, session_id=session_id, outcome="success", interaction=summary()
            ),
        ]
    )
    last["session_id"] = str(uuid4())
    assert not bot_alerts([*events, last])


@pytest.mark.parametrize(
    "changes",
    [
        {"consent": 1},
        {"consent": False},
        {"version": True},
        {"first_interaction_ms": 400, "submit_elapsed_ms": 300},
        {"pointer_move_count": -1},
        {"pointer_down_count": "1"},
        {"coordinates": [12, 33]},
        {"submit_elapsed_ms": float("nan")},
    ],
)
def test_strict_summary_validation(changes):
    with pytest.raises(ValidationError):
        Interaction.model_validate(summary(**changes))


def test_bot_incident_persists_across_ip_changes(client, app, event_factory):
    session_id = str(uuid4())
    for index in reversed(range(10)):
        response = send_event(
            client,
            event_factory(
                seconds=index,
                session_id=session_id,
                outcome="success",
                subject_id=f"user-{index}",
                source_ip=f"203.0.113.{index + 1}",
                interaction=summary(),
            ),
        )
        assert response.status_code == 201
    with app.app_context():
        alert = get_db().scalar(select(Alert).where(Alert.rule_id == "BOT-001"))
        assert alert.entity_key == session_id
        assert alert.score == 40
        assert get_db().scalar(select(func.count()).select_from(AlertEvent)) == 10


def test_success_does_not_shrink_existing_spray_evidence(client, app, event_factory):
    for index in range(10):
        assert (
            send_event(client, event_factory(seconds=index, subject_id=f"user-{index}")).status_code
            == 201
        )
    with app.app_context():
        alert_id = get_db().scalar(select(Alert.id).where(Alert.rule_id == "AUTH-002"))
    assert (
        send_event(
            client, event_factory(seconds=20, subject_id="user-0", outcome="success")
        ).status_code
        == 201
    )
    with app.app_context():
        assert (
            get_db().scalar(
                select(func.count())
                .select_from(AlertEvent)
                .where(
                    AlertEvent.alert_id == alert_id,
                )
            )
            == 10
        )


def test_receipts_count_only_attributable_outcomes(client, app, event_factory):
    event = event_factory()
    assert send_event(client, event).status_code == 201
    assert send_event(client, event).status_code == 200
    assert send_event(client, {**event, "outcome": "success"}).status_code == 409
    assert send_event(client, event_factory(subject_id="")).status_code == 422
    assert send_event(client, event_factory(), key="unrecognized").status_code == 401
    with app.app_context():
        outcomes = list(get_db().scalars(select(IngestionReceipt.outcome)))
        assert outcomes.count("accepted") == 1
        assert outcomes.count("duplicate") == 1
        assert outcomes.count("rejected") == 2
    sign_in(client)
    page = client.get(f"/applications/{app.config['TEST_APP_ID']}/metrics")
    assert b"Event delivery" in page.data
    assert b"Visitor interaction timing" in page.data


def test_retention_preview_and_scoped_apply(client, app, event_factory):
    for index in range(5):
        assert send_event(client, event_factory(seconds=index)).status_code == 201
    assert send_event(client, event_factory(), key="other-key").status_code == 201
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat(timespec="microseconds")
    with app.app_context():
        database = get_db()
        alert = database.scalar(select(Alert))
        event = database.scalar(select(Event).where(Event.app_id == app.config["TEST_APP_ID"]))
        event.occurred_at = old
        from platform_app.models import Application

        owner_id = database.get(Application, app.config["TEST_APP_ID"]).owner_id
        database.add(Note(alert_id=alert.id, owner_id=owner_id, body="Will expire with evidence"))
        database.add(AuditEntry(app_id=alert.app_id, target_id=alert.id, action="Test audit"))
        database.commit()
    runner = app.test_cli_runner()
    args = ["purge-data", "--application-id", app.config["TEST_APP_ID"]]
    preview = runner.invoke(args=args)
    assert preview.exit_code == 0, preview.output
    assert "events: 1" in preview.output and "notes: 1" in preview.output
    with app.app_context():
        assert get_db().scalar(select(func.count()).select_from(Alert)) == 1
    applied = runner.invoke(args=[*args, "--apply"])
    assert applied.exit_code == 0, applied.output
    with app.app_context():
        database = get_db()
        assert database.scalar(select(func.count()).select_from(Alert)) == 0
        assert database.scalar(select(func.count()).select_from(Note)) == 0
        assert database.scalar(select(func.count()).select_from(AlertEvent)) == 0
        assert database.scalar(select(func.count()).select_from(Event)) == 5
        assert database.scalar(select(func.count()).select_from(AuditEntry)) == 0


def test_purge_requires_explicit_scope_and_valid_timestamp(app):
    runner = app.test_cli_runner()
    assert runner.invoke(args=["purge-data"]).exit_code != 0
    assert (
        runner.invoke(args=["purge-data", "--all-applications", "--before", "2030-01-01"]).exit_code
        != 0
    )


def test_interaction_metrics_exclude_missing_and_interrupted_values(client, app, event_factory):
    from flask import template_rendered

    for index, interaction in enumerate(
        [
            None,
            summary(first_interaction_ms=20, submit_elapsed_ms=100),
            summary(first_interaction_ms=None, submit_elapsed_ms=300),
            summary(first_interaction_ms=500, submit_elapsed_ms=1000, visibility_interrupted=True),
        ]
    ):
        assert (
            send_event(client, event_factory(seconds=index, interaction=interaction)).status_code
            == 201
        )
    sign_in(client)
    contexts = []

    def capture(sender, template, context, **extra):
        contexts.append(context)

    template_rendered.connect(capture, app)
    try:
        assert client.get(f"/applications/{app.config['TEST_APP_ID']}/metrics").status_code == 200
    finally:
        template_rendered.disconnect(capture, app)
    stats = contexts[-1]["interaction_stats"]
    assert stats == {
        "opted_in": 3,
        "missing": 1,
        "interrupted": 1,
        "submit_samples": 2,
        "first_samples": 1,
        "submit_p50": 100,
        "submit_p95": 300,
        "first_p50": 20,
        "first_p95": 20,
    }


def test_old_receipts_and_audits_are_purged_without_deleting_recent_events(
    client, app, event_factory
):
    assert send_event(client, event_factory()).status_code == 201
    old = (datetime.now(UTC) - timedelta(days=8)).isoformat(timespec="microseconds")
    with app.app_context():
        database = get_db()
        database.scalar(select(IngestionReceipt)).received_at = old
        database.add(
            AuditEntry(
                app_id=app.config["TEST_APP_ID"],
                target_id="key-operation",
                action="Issued ingestion key",
                created_at=old,
            )
        )
        database.commit()
    result = app.test_cli_runner().invoke(args=["purge-data", "--all-applications", "--apply"])
    assert result.exit_code == 0, result.output
    assert "delivery_receipts: 1" in result.output
    with app.app_context():
        database = get_db()
        assert database.scalar(select(func.count()).select_from(Event)) == 1
        assert database.scalar(select(func.count()).select_from(IngestionReceipt)) == 0
        assert database.scalar(select(func.count()).select_from(AuditEntry)) == 0


def test_demo_summary_does_not_control_server_fields_and_operator_view_is_protected():
    demo = create_demo(
        {
            "TESTING": True,
            "SECRET_KEY": "demo-test-secret-" * 4,
            "DEMO_PASSWORD": "demo-password-123",
            "INGESTION_KEY": "test-key",
            "START_SENDER": False,
        }
    )
    client = demo.test_client()
    assert client.get("/monitoring").status_code == 403
    token = csrf_token(client.get("/login"))
    client.post(
        "/login",
        data={
            "csrf_token": token,
            "username": "reader",
            "password": "demo-password-123",
            "interaction": json.dumps(summary()),
            "outcome": "failure",
        },
    )
    event = demo.extensions["event_sender"].queue.get_nowait()
    assert event["outcome"] == "success"
    assert event["interaction"] == summary()
    assert client.get("/monitoring").status_code == 200
    assert client.get("/monitoring/status").json["counters"]["queued"] == 1
    assert (
        client.get("/monitoring", environ_overrides={"REMOTE_ADDR": "203.0.113.1"}).status_code
        == 403
    )
