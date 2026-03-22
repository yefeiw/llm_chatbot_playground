import json

from app.api.routes import handle_request


def test_healthz() -> None:
    status_code, headers, payload = handle_request("GET", "/healthz", {}, b"")

    assert status_code == 200
    assert payload == {"status": "ok", "service": "agent-api"}
    assert dict(headers)["X-Request-ID"]


def test_chat_returns_mock_reply() -> None:
    body = json.dumps({"message": "hello", "session_id": "session-1"}).encode("utf-8")
    status_code, headers, payload = handle_request(
        "POST",
        "/chat",
        {"X-REQUEST-ID": "req-123"},
        body,
    )

    assert status_code == 200
    assert dict(headers)["X-Request-ID"] == "req-123"
    assert payload["request_id"] == "req-123"
    assert payload["model"] == "claude-sonnet-4-20250514"
    assert payload["reply"].startswith("[mock:claude-sonnet-4-20250514]")
    assert payload["used_search"] is False
