"""Exercise the actual Requests → Waitress path, beyond Flask's test client."""

from threading import Thread

import requests
from waitress import create_server

from demo_app.transport import post_json


def test_event_over_real_http(app, event_factory):
    server = create_server(app, host="127.0.0.1", port=0)
    worker = Thread(target=server.run, daemon=True)
    worker.start()
    try:
        response = requests.post(
            f"http://127.0.0.1:{server.effective_port}/api/v1/events",
            json=event_factory(),
            headers={"Authorization": "Bearer test-key"},
            timeout=5,
        )
        assert response.status_code == 201, response.text
    finally:
        server.task_dispatcher.shutdown()
        server.close()
        worker.join(timeout=2)


def test_local_delivery_bypasses_environment_proxy(app, event_factory, monkeypatch):
    server = create_server(app, host="127.0.0.1", port=0)
    worker = Thread(target=server.run, daemon=True)
    worker.start()
    try:
        # A broken proxy must not intercept the local monitoring connection.
        for variable in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "all_proxy"):
            monkeypatch.setenv(variable, "http://127.0.0.1:1")
        monkeypatch.setenv("NO_PROXY", "")
        monkeypatch.setenv("no_proxy", "")
        response = post_json(
            f"http://127.0.0.1:{server.effective_port}/api/v1/events",
            json=event_factory(),
            headers={"Authorization": "Bearer test-key"},
            timeout=5,
            allow_redirects=False,
        )
        assert response.status_code == 201, response.text
    finally:
        server.task_dispatcher.shutdown()
        server.close()
        worker.join(timeout=2)
