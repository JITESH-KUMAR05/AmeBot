import importlib

import pytest


def test_health_ok_when_index_loaded(client):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["index_loaded"] is True
    assert body["total_chunks"] == 5


def test_root_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Amenify Support" in r.text


def test_chat_happy_path(client):
    r = client.post("/chat", json={"message": "who founded Amenify", "session_id": None})
    assert r.status_code == 200
    body = r.json()
    assert body["found_in_kb"] is True
    assert body["session_id"]
    assert "About Amenify" in body["sources"]


def test_chat_rejects_empty_message_with_422(client):
    r = client.post("/chat", json={"message": "", "session_id": None})
    assert r.status_code == 422


def test_chat_whitespace_message_returns_fallback(client):
    r = client.post("/chat", json={"message": "   ", "session_id": None})
    assert r.status_code == 200
    assert r.json()["found_in_kb"] is False


def test_delete_session_clears_history(client):
    import session
    r1 = client.post("/chat", json={"message": "who founded Amenify", "session_id": None})
    sid = r1.json()["session_id"]
    assert session.session_exists(sid) is True

    r2 = client.delete(f"/session/{sid}")
    assert r2.status_code == 204
    assert session.session_exists(sid) is False


def test_delete_unknown_session_is_204(client):
    assert client.delete("/session/does-not-exist").status_code == 204


def test_health_degraded_when_index_missing(monkeypatch):
    import main
    import retriever
    from starlette.testclient import TestClient

    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(retriever, "_index", None)
    monkeypatch.setattr(retriever, "_chunks", [])
    with TestClient(main.app) as c:
        body = c.get("/health").json()
    assert body["status"] == "degraded"
    assert body["index_loaded"] is False


@pytest.fixture
def rate_limited_client(monkeypatch, fake_index, mock_azure, low_threshold):
    """A TestClient whose app was (re)configured with a 2/minute limit."""
    monkeypatch.setenv("RATE_LIMIT", "2/minute")
    import config
    import main
    importlib.reload(config)
    importlib.reload(main)
    from starlette.testclient import TestClient

    monkeypatch.setattr(main, "load_index", lambda: None)
    with TestClient(main.app) as c:
        yield c
    # undo the reload so other tests see the default (disabled) module state
    monkeypatch.setenv("RATE_LIMIT", "")
    importlib.reload(config)
    importlib.reload(main)


def test_chat_rate_limited_after_threshold(rate_limited_client):
    payload = {"message": "who founded Amenify", "session_id": None}
    assert rate_limited_client.post("/chat", json=payload).status_code == 200
    assert rate_limited_client.post("/chat", json=payload).status_code == 200
    r = rate_limited_client.post("/chat", json=payload)
    assert r.status_code == 429
    assert "detail" in r.json()


def test_rate_limit_disabled_by_default(client):
    payload = {"message": "who founded Amenify", "session_id": None}
    for _ in range(6):
        assert client.post("/chat", json=payload).status_code == 200


def test_chat_503_when_index_not_loaded(monkeypatch, mock_azure):
    import main
    import retriever
    from starlette.testclient import TestClient

    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(retriever, "_index", None)
    monkeypatch.setattr(retriever, "_chunks", [])
    with TestClient(main.app) as c:
        r = c.post("/chat", json={"message": "hi", "session_id": None})
    assert r.status_code == 503


def test_chat_message_too_long_is_422(client):
    r = client.post("/chat", json={"message": "x" * 1001, "session_id": None})
    assert r.status_code == 422
