from unittest.mock import Mock

from scripts.check_connection import check_connection


def test_probe_authenticates_without_sending_an_event(monkeypatch, capsys):
    monkeypatch.setenv("THREATWATCH_INGESTION_KEY", "private-test-key")
    monkeypatch.setenv("THREATWATCH_URL", "http://127.0.0.1:5000")
    response = Mock(status_code=422)
    response.json.return_value = {"error": {"code": "validation"}}
    post = Mock(return_value=response)
    monkeypatch.setattr("scripts.check_connection.post_json", post)
    assert check_connection() == 0
    assert post.call_args.kwargs["json"] == {}
    output = capsys.readouterr().out
    assert "Connection OK" in output
    assert "private-test-key" not in output


def test_probe_explains_csrf_without_printing_response(monkeypatch, capsys):
    monkeypatch.setenv("THREATWATCH_INGESTION_KEY", "private-test-key")
    response = Mock(status_code=400)
    response.json.return_value = {"error": {"message": "The CSRF token is missing."}}
    monkeypatch.setattr("scripts.check_connection.post_json", Mock(return_value=response))
    assert check_connection() == 1
    assert "CSRF" in capsys.readouterr().out


def test_hidden_paste_character_is_detected_without_network_or_key_disclosure(monkeypatch, capsys):
    key = "private\x16test-key"
    monkeypatch.setenv("THREATWATCH_INGESTION_KEY", key)
    post = Mock()
    monkeypatch.setattr("scripts.check_connection.post_json", post)
    assert check_connection() == 1
    post.assert_not_called()
    output = capsys.readouterr().out
    assert "Invalid ingestion key format" in output
    assert key not in output
