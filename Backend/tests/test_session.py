import config
import session


def test_get_history_unknown_id_returns_empty_and_does_not_create():
    assert session.get_history("nope") == []
    assert session.session_exists("nope") is False
    assert len(session._sessions) == 0


def test_add_message_creates_and_returns_history():
    sid = session.create_session()
    session.add_message(sid, "user", "hi")
    session.add_message(sid, "assistant", "hello")
    assert session.get_history(sid) == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]


def test_history_trims_to_max_history():
    sid = session.create_session()
    for i in range(config.MAX_HISTORY + 6):
        session.add_message(sid, "user", f"m{i}")
    hist = session.get_history(sid)
    assert len(hist) == config.MAX_HISTORY
    assert hist[-1]["content"] == f"m{config.MAX_HISTORY + 5}"


def test_get_history_returns_a_copy():
    sid = session.create_session()
    session.add_message(sid, "user", "hi")
    session.get_history(sid).append({"role": "user", "content": "mutated"})
    assert len(session.get_history(sid)) == 1


def test_size_cap_evicts_oldest(monkeypatch):
    monkeypatch.setattr(config, "MAX_SESSIONS", 3)
    monkeypatch.setattr(session, "MAX_SESSIONS", 3)
    for i in range(3):
        session.add_message(f"s{i}", "user", "x")
    session.add_message("s3", "user", "x")           # over cap -> evict s0
    assert session.session_exists("s0") is False
    assert session.session_exists("s3") is True
    assert len(session._sessions) == 3


def test_clear_session_removes_history():
    sid = session.create_session()
    session.add_message(sid, "user", "hi")
    session.clear_session(sid)
    assert session.session_exists(sid) is False
    session.clear_session(sid)  # idempotent
