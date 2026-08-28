import json
import logging

import chat
from logging_config import JsonFormatter


def test_json_formatter_includes_extras():
    rec = logging.LogRecord("t", logging.INFO, __file__, 1, "hi", None, None)
    rec.event = "chat_request"
    rec.session_id = "abc"
    rec.latency_ms = 12.3
    out = json.loads(JsonFormatter().format(rec))
    assert out["event"] == "chat_request"
    assert out["session_id"] == "abc"
    assert out["latency_ms"] == 12.3
    assert out["level"] == "INFO"


def test_chat_emits_one_structured_record(fake_index, mock_azure, low_threshold, caplog):
    with caplog.at_level(logging.INFO, logger="amebot.chat"):
        chat.chat("who founded Amenify", None)
    recs = [r for r in caplog.records if getattr(r, "event", None) == "chat_request"]
    assert len(recs) == 1
    r = recs[0]
    assert r.found_in_kb is True
    assert r.n_chunks >= 1
    assert isinstance(r.latency_ms, float)
    assert r.rewritten is False


def test_chat_log_omits_query_text_by_default(fake_index, mock_azure, low_threshold, caplog):
    with caplog.at_level(logging.INFO, logger="amebot.chat"):
        chat.chat("who founded Amenify", None)
    r = [x for x in caplog.records if getattr(x, "event", None) == "chat_request"][0]
    assert not hasattr(r, "query")
