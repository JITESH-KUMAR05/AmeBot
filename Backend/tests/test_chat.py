import chat


def test_blank_message_short_circuits(fake_index, mock_azure):
    called = {"embed": 0}
    orig_retrieve = chat.retrieve

    def spy_retrieve(q):
        called["embed"] += 1
        return orig_retrieve(q)

    chat.retrieve = spy_retrieve
    try:
        result = chat.chat("    ", None)
    finally:
        chat.retrieve = orig_retrieve

    assert result["found_in_kb"] is False
    assert result["sources"] == []
    assert result["answer"] == chat.NO_ANSWER_RESPONSE
    assert result["session_id"]
    assert called["embed"] == 0


def test_kb_hit_returns_answer_and_sources(fake_index, mock_azure, low_threshold):
    result = chat.chat("who founded Amenify", None)
    assert result["found_in_kb"] is True
    assert "About Amenify" in result["sources"]
    assert "Everett Lynn" in result["answer"]


def test_kb_miss_returns_fallback_without_llm(fake_index, mock_azure):
    mock_azure["text"] = "SHOULD NOT BE USED"
    result = chat.chat("what is the capital of France", None)
    assert result["found_in_kb"] is False
    assert result["answer"] == chat.NO_ANSWER_RESPONSE
    assert result["sources"] == []


def test_llm_error_falls_back(fake_index, mock_azure, low_threshold, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("azure down")

    monkeypatch.setattr(chat._client.chat.completions, "create", boom)
    result = chat.chat("who founded Amenify", None)
    assert result["answer"] == chat.NO_ANSWER_RESPONSE
    assert result["found_in_kb"] is True  # retrieval still succeeded


def test_followup_turn_does_not_use_builtin_print(fake_index, mock_azure, low_threshold, monkeypatch):
    """Regression: _rewrite_query used to print() a U+2192 arrow, which crashed
    the follow-up path on a non-UTF-8 stdout. Nothing in the request path may
    call the builtin print."""
    import builtins

    def no_print(*a, **k):
        raise AssertionError("builtin print() called in the chat request path")

    monkeypatch.setattr(builtins, "print", no_print)

    sid = chat.chat("What is Amenify?", None)["session_id"]
    out = chat.chat("who founded it?", sid)          # follow-up → triggers _rewrite_query
    assert out["found_in_kb"] is True
    assert out["session_id"] == sid
