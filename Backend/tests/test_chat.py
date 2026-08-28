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
