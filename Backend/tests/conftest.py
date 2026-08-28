"""Shared test fixtures. This module sets fake Azure env vars at import time,
BEFORE anything imports `config` (which raises if they are missing)."""
import os

os.environ.setdefault("AZURE_OPENAI_API_KEY", "test-key")
os.environ.setdefault("AZURE_OPENAI_ENDPOINT", "https://test.openai.azure.com/")
os.environ.setdefault("AZURE_OPENAI_DEPLOYMENT_NAME", "test-gpt")
os.environ.setdefault("AZURE_OPENAI_API_VERSION", "2024-02-01")
os.environ.setdefault("AZURE_EMBEDDING_MODEL", "text-embedding-ada-002")
os.environ.setdefault("RATE_LIMIT", "")          # disable slowapi in tests
os.environ.setdefault("LOG_LEVEL", "WARNING")    # quiet logs during tests

import hashlib
import re

import numpy as np
import pytest

_DIM = 1536


def fake_embedding(text: str) -> np.ndarray:
    """Deterministic bag-of-words embedding.

    Each token is hashed to a bucket; counts are accumulated and L2-normalised.
    Two strings that share tokens get a positive inner product, so FAISS
    similarity behaves sensibly in offline tests. Deterministic across runs
    (md5, not the salted built-in hash)."""
    vec = np.zeros(_DIM, dtype=np.float32)
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        bucket = int.from_bytes(hashlib.md5(tok.encode()).digest()[:4], "little") % _DIM
        vec[bucket] += 1.0
    norm = np.linalg.norm(vec)
    if norm:
        vec /= norm
    return vec


CANNED_CHUNKS = [
    {"text": "Amenify was founded in 2017 by Everett Lynn and Danish Chopra. "
             "Everett Lynn is the Founder and CEO; Danish Chopra is Co-Founder, CTO and COO.",
     "source": "About Amenify", "url": "https://www.amenify.com/about-us", "chunk_id": 0},
    {"text": "Amenify offers house cleaning, deep cleaning and move-out cleaning "
             "for apartment residents, booked through the Amenify app.",
     "source": "Cleaning Services", "url": "https://www.amenify.com/cleaningservices1", "chunk_id": 1},
    {"text": "The Amenify Resident Protection Plan covers up to 1000 dollars per year "
             "for accidental damage, plus lockout and key replacement help.",
     "source": "Resident Protection Plan", "url": "https://www.amenify.com/resident-protection-plan", "chunk_id": 2},
    {"text": "Residents can call or text Amenify support at +1-719-767-1963 "
             "or visit amenify.com/contact-us for help.",
     "source": "Contact", "url": "https://www.amenify.com/", "chunk_id": 3},
    {"text": "Amenify provides home services including handyman work, grocery delivery, "
             "dog walking, pool cleaning and lawn care through its mobile app.",
     "source": "Services Overview", "url": "https://www.amenify.com/resident-services", "chunk_id": 4},
]


@pytest.fixture
def canned_chunks():
    # fresh copy per test
    return [dict(c) for c in CANNED_CHUNKS]


@pytest.fixture
def fake_index(monkeypatch, canned_chunks):
    """Install a real in-memory FAISS index built from CANNED_CHUNKS."""
    import faiss
    import retriever

    mat = np.array([fake_embedding(c["text"]) for c in canned_chunks], dtype=np.float32)
    faiss.normalize_L2(mat)
    index = faiss.IndexFlatIP(_DIM)
    index.add(mat)

    monkeypatch.setattr(retriever, "_index", index)
    monkeypatch.setattr(retriever, "_chunks", canned_chunks)
    return index


@pytest.fixture
def mock_azure(monkeypatch):
    """Patch every Azure call: embeddings -> fake_embedding, chat -> canned answer."""
    import chat as chat_mod
    import retriever

    class _EmbItem:
        def __init__(self, vec):
            self.embedding = list(map(float, vec))

    class _EmbResp:
        def __init__(self, texts):
            self.data = [_EmbItem(fake_embedding(t)) for t in texts]

    def _fake_embeddings_create(input, model, **kw):
        texts = input if isinstance(input, list) else [input]
        return _EmbResp(texts)

    class _Msg:
        def __init__(self, c):
            self.content = c

    class _Choice:
        def __init__(self, c):
            self.message = _Msg(c)

    class _ChatResp:
        def __init__(self, c):
            self.choices = [_Choice(c)]

    canned = {"text": "Amenify was founded in 2017 by Everett Lynn and Danish Chopra."}

    def _fake_chat_create(model, messages, **kw):
        return _ChatResp(canned["text"])

    monkeypatch.setattr(retriever._embed_client.embeddings, "create", _fake_embeddings_create)
    monkeypatch.setattr(chat_mod._client.chat.completions, "create", _fake_chat_create)
    return canned  # tests may set canned["text"] to change the answer


@pytest.fixture
def low_threshold(monkeypatch):
    """Lower MIN_SIMILARITY_SCORE for tests that assert a KB hit.

    The fake bag-of-words embeddings cannot reproduce the topical clustering
    that real ada-002 vectors have, so a realistic query/chunk pair scores
    ~0.15-0.30 cosine, not >0.70. Tests that exercise the *retrieval hit*
    path calibrate the gate down; tests that exercise the *miss* path use a
    query with zero token overlap (which scores 0.0 regardless)."""
    import retriever
    monkeypatch.setattr(retriever, "MIN_SIMILARITY_SCORE", 0.05)


@pytest.fixture
def client(fake_index, mock_azure, low_threshold, monkeypatch):
    """TestClient with the fake index; lifespan load_index() is a no-op."""
    import main
    import retriever
    from starlette.testclient import TestClient

    monkeypatch.setattr(main, "load_index", lambda: None)
    monkeypatch.setattr(main, "get_total_chunks", retriever.get_total_chunks)
    with TestClient(main.app) as c:
        yield c


@pytest.fixture(autouse=True)
def _reset_sessions():
    import session
    session._sessions.clear()
    yield
    session._sessions.clear()


def pytest_collection_modifyitems(config, items):
    """Skip @pytest.mark.live tests unless the run explicitly asks for them
    (`pytest -m live`). test_live.py also self-skips when real creds are absent."""
    markexpr = config.getoption("markexpr", default="") or ""
    if "live" in markexpr:
        return
    skip_live = pytest.mark.skip(reason="live test — run with: pytest -m live")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
