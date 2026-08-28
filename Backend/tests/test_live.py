"""Opt-in tests that call the real Azure OpenAI API.

Run with:  uv run pytest -m live

Double-guarded: the collection hook in conftest skips these unless `-m live`
is passed, and the skipif below skips them when real credentials are absent
(e.g. only the conftest stub values are set)."""
import os

import pytest

_STUB = {
    "test-key",
    "https://test.openai.azure.com/",
    "test-gpt",
    "text-embedding-ada-002",  # conftest stub value for the embedding model
}
_REQUIRED = [
    "AZURE_OPENAI_API_KEY", "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_DEPLOYMENT_NAME", "AZURE_OPENAI_API_VERSION",
    "AZURE_EMBEDDING_MODEL",
]
_have_creds = all(os.getenv(k) and os.getenv(k) not in _STUB for k in _REQUIRED)

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
