import ingestion


def test_chunk_text_splits_with_overlap():
    words = " ".join(f"w{i}" for i in range(1200))
    chunks = ingestion.chunk_text(words, chunk_size=500, overlap=50)
    assert len(chunks) == 3
    # overlap: last 50 words of chunk 0 reappear at the start of chunk 1
    tail = chunks[0].split()[-50:]
    assert chunks[1].split()[:50] == tail


def test_chunk_text_drops_tiny_tail():
    chunks = ingestion.chunk_text(" ".join(["word"] * 20), chunk_size=500, overlap=50)
    assert chunks == []


def test_build_chunks_tags_source_and_ids():
    docs = [{"title": "About", "url": "u", "content": " ".join(["amenify"] * 60)}]
    out = ingestion.build_chunks(docs)
    assert out[0]["source"] == "About"
    assert out[0]["url"] == "u"
    assert out[0]["chunk_id"] == 0
    assert set(out[0]) == {"text", "source", "url", "chunk_id"}


def test_load_raw_documents_prefers_manual(tmp_path, monkeypatch):
    manual = tmp_path / "manual.json"
    manual.write_text('[{"title": "M", "url": "u", "content": "hello world"}]', encoding="utf-8")
    monkeypatch.setattr(ingestion, "MANUAL_DATA_PATH", str(manual))
    docs = ingestion.load_raw_documents()
    assert docs[0]["title"] == "M"
