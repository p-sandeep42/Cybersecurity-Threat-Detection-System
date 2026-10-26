from sqlalchemy import select

from platform_app.database import get_db, migrate_database
from platform_app.models import Alert, Note
from tests.helpers import csrf_token, send_event, sign_in


def test_login_and_csrf(client):
    assert client.get("/applications").status_code == 302
    assert (
        client.post("/login", data={"login": "owner", "password": "test-password-123"}).status_code
        == 400
    )
    token = csrf_token(client.get("/login"))
    failed = client.post(
        "/login", data={"csrf_token": token, "login": "owner", "password": "wrong"}
    )
    assert b"Invalid login or password" in failed.data
    sign_in(client)
    assert client.get("/applications").status_code == 200


def test_owned_pages_and_cross_owner_denial(client, app):
    sign_in(client)
    owned = app.config["TEST_APP_ID"]
    other = app.config["OTHER_APP_ID"]
    for suffix in ("setup", "events", "alerts", "metrics"):
        assert client.get(f"/applications/{owned}/{suffix}").status_code == 200
        assert client.get(f"/applications/{other}/{suffix}").status_code == 404
    token = csrf_token(client.get(f"/applications/{owned}/setup"))
    for suffix in ("keys/rotate", "keys/revoke", "delete"):
        assert (
            client.post(
                f"/applications/{other}/{suffix}",
                data={
                    "csrf_token": token,
                    "confirm": "yes",
                    "confirm_name": "Private project",
                },
            ).status_code
            == 404
        )


def test_status_notes_reopen_and_duplicate_preservation(client, event_factory, app):
    events = [event_factory(seconds=index) for index in range(5)]
    for event in events:
        assert send_event(client, event).status_code == 201
    with app.app_context():
        alert_id = get_db().scalar(select(Alert.id))
    sign_in(client)
    url = f"/applications/{app.config['TEST_APP_ID']}/alerts/{alert_id}"
    page = client.get(url)
    assert page.status_code == 200
    token = csrf_token(page)
    assert (
        client.post(
            url,
            data={
                "csrf_token": token,
                "action": "note",
                "body": "<script>alert(1)</script>",
            },
        ).status_code
        == 302
    )
    assert b"&lt;script&gt;" in client.get(url).data
    assert (
        client.post(
            url,
            data={
                "csrf_token": token,
                "action": "status",
                "status": "Resolved",
            },
        ).status_code
        == 302
    )
    assert send_event(client, events[-1]).status_code == 200
    with app.app_context():
        assert get_db().get(Alert, alert_id).status == "Resolved"
    assert send_event(client, event_factory(seconds=6)).status_code == 201
    with app.app_context():
        assert get_db().get(Alert, alert_id).status == "Open"
        assert get_db().scalar(select(Note)).body == "<script>alert(1)</script>"
    stranger = app.test_client()
    sign_in(stranger, "stranger", "other-password-123")
    assert stranger.get(url).status_code == 404
    stranger_token = csrf_token(stranger.get("/applications"))
    assert (
        stranger.post(
            url,
            data={
                "csrf_token": stranger_token,
                "action": "status",
                "status": "Resolved",
            },
        ).status_code
        == 404
    )


def test_rotation_revocation_and_application_delete(client, app, event_factory):
    sign_in(client)
    app_id = app.config["TEST_APP_ID"]
    token = csrf_token(client.get(f"/applications/{app_id}/setup"))
    response = client.post(
        f"/applications/{app_id}/keys/rotate",
        data={
            "csrf_token": token,
            "confirm": "yes",
        },
    )
    assert response.status_code == 200
    assert b"Save your ingestion key" in response.data
    assert response.headers["Cache-Control"] == "no-store"
    assert send_event(client, event_factory()).status_code == 401
    assert (
        client.post(
            f"/applications/{app_id}/delete",
            data={
                "csrf_token": token,
                "confirm_name": "wrong",
            },
        ).status_code
        == 400
    )
    assert (
        client.post(
            f"/applications/{app_id}/delete",
            data={
                "csrf_token": token,
                "confirm_name": "Bookstore",
            },
        ).status_code
        == 302
    )
    assert client.get(f"/applications/{app_id}/setup").status_code == 404


def test_filters_and_migrations_preserve_data(client, app, event_factory):
    assert send_event(client, event_factory()).status_code == 201
    with app.app_context():
        migrate_database()
    sign_in(client)
    url = f"/applications/{app.config['TEST_APP_ID']}/events"
    assert b"account-1" in client.get(url).data
    assert b"No matching events" in client.get(url + "?subject=unknown").data
    assert client.get(url + "?page=0").status_code == 400
    assert client.get(url + "?from=invalid").status_code == 400
    assert client.get(url + "?from=&to=&subject=").status_code == 200


def test_owner_cli(app):
    result = app.test_cli_runner().invoke(
        args=[
            "create-owner",
            "--login",
            "new-owner",
        ],
        input="long-test-password\nlong-test-password\n",
    )
    assert result.exit_code == 0, result.output
