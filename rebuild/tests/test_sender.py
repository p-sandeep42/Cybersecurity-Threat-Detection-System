from unittest.mock import Mock

import pytest
import requests

from demo_app import create_app
from demo_app.sender import EventSender
from tests.helpers import csrf_token


def test_invalid_key_is_rejected_before_background_delivery():
    with pytest.raises(ValueError, match="Invalid ingestion key format"):
        EventSender("http://127.0.0.1:5000", "private\x16test-key")


def test_queue_overflow_is_nonblocking():
    sender = EventSender("http://127.0.0.1:5000", "key", capacity=1)
    assert sender.enqueue({"event_id": "first"})
    assert not sender.enqueue({"event_id": "second"})
    assert sender.snapshot()["dropped"] == 1


def test_retry_uses_same_event_and_drops_after_four_attempts(monkeypatch):
    sender = EventSender("http://127.0.0.1:5000", "key")
    sender.stopped.wait = Mock(return_value=False)
    post = Mock(side_effect=requests.ConnectionError())
    monkeypatch.setattr("demo_app.sender.post_json", post)
    event = {"event_id": "unchanged"}
    assert not sender.deliver(event)
    assert post.call_count == 4
    assert all(call.kwargs["json"] is event for call in post.call_args_list)
    assert sender.snapshot() == {"queued": 0, "sent": 0, "retried": 3, "dropped": 1}


def test_permanent_error_not_retried_and_retry_after_honored(monkeypatch):
    sender = EventSender("http://127.0.0.1:5000", "key")
    response = Mock(status_code=422, headers={})
    post = Mock(return_value=response)
    monkeypatch.setattr("demo_app.sender.post_json", post)
    assert not sender.deliver({"event_id": "bad"})
    assert post.call_count == 1
    response.headers = {"Retry-After": "60"}
    assert sender.retry_delay(response, 0) == 60


def test_rejected_key_logs_actionable_message_without_credentials(monkeypatch, caplog):
    sender = EventSender("http://127.0.0.1:5000", " secret-key ")
    response = Mock(status_code=401, headers={})
    post = Mock(return_value=response)
    monkeypatch.setattr("demo_app.sender.post_json", post)
    assert not sender.deliver({"event_id": "example"})
    assert post.call_count == 1
    assert post.call_args.kwargs["headers"]["Authorization"] == "Bearer secret-key"
    assert "HTTP 401" in caplog.text
    assert "active application key" in caplog.text
    assert "secret-key" not in caplog.text


def test_demo_login_enqueues_server_derived_event_without_network(monkeypatch):
    application = create_app(
        {
            "TESTING": True,
            "SECRET_KEY": "demo-test-secret-" * 4,
            "DEMO_PASSWORD": "demo-password-123",
            "INGESTION_KEY": "test-key",
            "START_SENDER": False,
        }
    )
    post = Mock(side_effect=AssertionError("Login must not make a network call"))
    monkeypatch.setattr("demo_app.sender.post_json", post)
    client = application.test_client()
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={
            "csrf_token": token,
            "username": "reader",
            "password": "demo-password-123",
            "outcome": "failure",
            "source_ip": "1.2.3.4",
        },
    )
    assert response.status_code == 302
    event = application.extensions["event_sender"].queue.get_nowait()
    assert event["outcome"] == "success"
    assert event["source_ip"] == "127.0.0.1"
    assert event["subject_id"] != "reader"
    assert "password" not in str(event)
    assert event["interaction"] is None
    post.assert_not_called()
