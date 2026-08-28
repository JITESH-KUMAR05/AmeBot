"""Opt-in tests that call the real Azure OpenAI API.

Run with:  uv run pytest -m live

Double-guarded: the collection hook in conftest skips these unless `-m live`
is passed, and the skipif below skips them when real credentials are absent
(e.g. only the conftest stub values are set)."""
import os

import pytest

# Backend/.env is loaded by conftest's pytest_configure hook when (and only when)
# the run is `pytest -m live` — early enough that app modules imported during
# collection pick up the real credentials.

# Discriminate real creds from the conftest stubs on the key + endpoint only
# (the embedding-model / api-version values are not reliably distinctive —
# "text-embedding-ada-002" is both the stub AND a common real deployment name).
_STUB_KEY = "test-key"
_STUB_ENDPOINT = "https://test.openai.azure.com/"
_have_creds = (
    bool(os.getenv("AZURE_OPENAI_API_KEY"))
    and os.getenv("AZURE_OPENAI_API_KEY") != _STUB_KEY
    and bool(os.getenv("AZURE_OPENAI_ENDPOINT"))
    and os.getenv("AZURE_OPENAI_ENDPOINT") != _STUB_ENDPOINT
)

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(not _have_creds, reason="real AZURE_OPENAI_* env vars not set"),
]


def test_real_embedding_retrieves_expected_source():
    import retriever
    import vector_store
    from ingestion import run_ingestion

    chunks = run_ingestion()
    index, final_chunks = vector_store.get_or_build_index(chunks)
    retriever._index, retriever._chunks = index, final_chunks

    hits = retriever.retrieve("who founded Amenify")
    assert hits
    assert any("about" in h["source"].lower() for h in hits)


def test_real_chat_answers_from_kb():
    import chat
    out = chat.chat("What is the Resident Protection Plan?", None)
    assert out["found_in_kb"] is True
    assert out["answer"] and "don't have information" not in out["answer"].lower()


def test_real_chat_refuses_out_of_domain():
    import chat
    out = chat.chat("Who is the CEO of Apple?", None)
    assert out["found_in_kb"] is False
