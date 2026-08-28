import numpy as np
import pytest

import retriever


def test_retrieve_filters_below_threshold(fake_index, mock_azure, monkeypatch):
    # Lower the bar so the bag-of-words overlap clears it for an on-topic query.
    # (Fake hash embeddings are too collision-noisy for exact-rank assertions —
    # asserting exact order would test the fake, not retrieve(). Assert instead
    # that the relevant doc is in the top-k and every hit clears the gate.)
    monkeypatch.setattr(retriever, "MIN_SIMILARITY_SCORE", 0.05)
    hits = retriever.retrieve("who founded Amenify in 2017")
    assert hits
    assert all(h["score"] >= 0.05 for h in hits)
    assert "About Amenify" in {h["source"] for h in hits}
    assert set(hits[0]) == {"text", "source", "url", "score"}
    # scores come back sorted high -> low
    assert [h["score"] for h in hits] == sorted((h["score"] for h in hits), reverse=True)


def test_retrieve_returns_empty_for_off_topic(fake_index, mock_azure):
    # default MIN_SIMILARITY_SCORE (0.70); unrelated query shares no tokens
    assert retriever.retrieve("quantum chromodynamics lecture notes") == []


def test_embed_query_raises_on_zero_norm(fake_index, monkeypatch):
    class _Item:
        embedding = [0.0] * 1536

    class _Resp:
        data = [_Item()]

    monkeypatch.setattr(retriever._embed_client.embeddings, "create",
                        lambda **kw: _Resp())
    with pytest.raises(ValueError):
        retriever._embed_query("anything")


def test_embed_query_shape_is_1_by_dim(fake_index, mock_azure):
    vec = retriever._embed_query("hello world")
    assert vec.shape == (1, 1536)
