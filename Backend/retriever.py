## takes user message
## query -> embed -> normalize -> search

import os
import json
import numpy as np
import faiss
from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_DEPLOYMENT_NAME,
    AZURE_OPENAI_API_VERSION,
    AZURE_EMBEDDING_MODEL,
    TOP_K,
    MIN_SIMILARITY_SCORE,
    FAISS_INDEX_PATH
)

_index : faiss.Index | None = None
_chunks: list[dict] = []

_embed_client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION,
)

def load_index() -> None:
    """
    loads the faiss index and chunks from disk
    """
    global _index, _chunks
    index_file = os.path.join(FAISS_INDEX_PATH, "faiss_index.bin")
    chunks_file = os.path.join(FAISS_INDEX_PATH, "chunks.json")

    if not os.path.exists(index_file) or not os.path.exists(chunks_file):
        raise FileNotFoundError("Faiss index or chunks file not found")
    
    _index = faiss.read_index(index_file)
    with open(chunks_file, "r",encoding="utf-8") as f:
        _chunks = json.load(f)
    
    print(f"Retriever ready → {_index.ntotal} vectors | {len(_chunks)} chunks loaded")

def is_loaded() -> bool:
    """
    True if the index is in memory and ready to serve queries
    """
    return _index is not None and len(_chunks) > 0


def get_total_chunks() -> int:
    """
    Returns the number of chunks loaded in memory
    """
    return len(_chunks)

def _embed_query(query: str) -> np.ndarray:
    """
    embed a single text string using Azure OpenAI
    """
    clean = query.replace("\n", " ").strip()
    response = _embed_client.embeddings.create(
        input=[clean],
        model=AZURE_EMBEDDING_MODEL,
    )
    vec = np.array(response.data[0].embedding, dtype=np.float32)
    vec = vec / np.linalg.norm(vec)  # normalize the vector
    return vec.reshape(1, -1)

def retrieve(query: str) -> list[dict]:
    """
    embeds the query and searches the FAISS index
    returns a list of top_k chunks with similarity scores
    """
    if _index is None:
        raise RuntimeError(
            "Retriever index not loaded"
            "load_index() should be called at the startup definetly"
        )
    
    # 1 embed and normalize    
    query_vec = _embed_query(query)
    query_vec = query_vec.reshape(1,-1)

    # 2 search
    scores, indices = _index.search(query_vec, TOP_K)

    # 3 filter and build result list
    result = []
    for score, idx in zip(scores[0], indices[0]):
        if idx==-1: 
            continue
            
        if float(score) < MIN_SIMILARITY_SCORE:
            continue

        chunk = _chunks[idx]
        result.append({
            "text": chunk["text"],
            "source": chunk["source"],
            "url": chunk.get("url",""),
            "score": float(score),
        })
    return result