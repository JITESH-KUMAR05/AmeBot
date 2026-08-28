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
