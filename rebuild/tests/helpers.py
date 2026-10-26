import re


def csrf_token(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, response.get_data(as_text=True)
    return match.group(1)


def sign_in(client, login="owner", password="test-password-123"):
    token = csrf_token(client.get("/login"))
    response = client.post(
        "/login",
        data={
            "csrf_token": token,
            "login": login,
            "password": password,
        },
    )
    assert response.status_code == 302


def send_event(client, event, key="test-key"):
    return client.post("/api/v1/events", json=event, headers={"Authorization": f"Bearer {key}"})
