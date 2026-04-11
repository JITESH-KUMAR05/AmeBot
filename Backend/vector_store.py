# the main aim of this is to convert those chunks into embeddings
# text chunks -> embeddings
# chunks (text) -> Azure OpenAI Embedding Model -> numpy array -> FAISS index -> saved to disk

import shutil
import os
import json
import numpy as np
import faiss
from openai import AzureOpenAI
from config import (
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_VERSION,
    AZURE_EMBEDDING_MODEL,
    FAISS_INDEX_PATH
)

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    azure_endpoint=AZURE_OPENAI_ENDPOINT,
    api_version=AZURE_OPENAI_API_VERSION
)

## get embeddings

def get_embedding(text:str) -> list[float]:
    """
    this calls the model text-embeddings-ada-002 and converts the piece of text into vector (list of 1536 floats)
    """

    clean_text = text.replace("\n", " ").strip()

    response = client.embeddings.create(
        input=clean_text,
        model=AZURE_EMBEDDING_MODEL
    )

    return response.data[0].embedding

def embed_chunks(chunks: list[dict]) -> tuple[list[dict], np.ndarray]:
    """
    Embed all chunks and return the list of chunks with embeddings and the FAISS index
    """
    print(f"Embedding {len(chunks)} chunks via Azure OpenAI...")
    
    embeddings = []

    for i,chunk in enumerate(chunks):
        embedding = get_embedding(chunk["text"])
        embeddings.append(embedding)

        if (i+1) % 5 == 0 or  (i+1) == len(chunks):
            print(f"Embedded {i+1}/{len(chunks)} chunks")

    embeddings_matrix = np.array(embeddings, dtype=np.float32)

    print(f"Embedding matrix shape : {embeddings_matrix.shape}")

    return chunks, embeddings_matrix

## Build FAISS Index

def build_faiss_index(embeddings_matrix: np.ndarray) -> faiss.Index:
    """
    Build a FAISS index from the embeddings matrix
    """
    dimension = embeddings_matrix.shape[1]
    print(f"Building Faiss index of dimension {dimension}")
    index = faiss.IndexFlatIP(dimension)
    # normalize vectors to unit length
    faiss.normalize_L2(embeddings_matrix)
    index.add(embeddings_matrix)
    print(f"FAISS index built successfully with {index.ntotal} vectors")
    return index

## Save and Load

def save_index(index: faiss.Index, chunks: list[dict]) -> None :
    """
    save the Faiss index and chunks to disk
    """
    
    os.makedirs(FAISS_INDEX_PATH, exist_ok=True)

    index_file = os.path.join(FAISS_INDEX_PATH, "faiss_index.bin")
    chunks_file = os.path.join(FAISS_INDEX_PATH, "chunks.json")

    faiss.write_index(index, index_file)

    # Save chunks metadata as JSON
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)
    
    print(f"Saved FAISS index -> {index_file}")
    print(f"Saved chunks json -> {chunks_file}")

def load_index() -> tuple[faiss.Index, list[dict]] | tuple[None, None]:
    """
    Load the Faiss index and chunks from the disk
    """
    index_file  = os.path.join(FAISS_INDEX_PATH, "faiss_index.bin")
    chunks_file = os.path.join(FAISS_INDEX_PATH, "chunks.json")

    if not os.path.exists(index_file) or not os.path.exists(chunks_file):
        print("No saved FAISS index found. Will build from scratch.")
        return None, None
    
    try:
        index = faiss.read_index(index_file)
        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)
        print(f"Loaded FAISS index with {index.ntotal} vectors and {len(chunks)} chunks")
        return index, chunks
    except Exception as e:
        print(f"Failed to load FAISS index: {e}")
        return None, None

# build or load

def get_or_build_index(chunks: list[dict]) -> tuple[faiss.Index, list[dict]]:
    """
    Try to load existing index, otherwise build from scratch
    """
    index, loaded_chunks = load_index()
    if index is not None and loaded_chunks is not None:
        return index, loaded_chunks
    
    # build from scratch
    chunks, embeddings_matrix = embed_chunks(chunks)
    index = build_faiss_index(embeddings_matrix)
    save_index(index, chunks)
    return index, chunks

## testing directly here
if __name__ == "__main__":
    from ingestion import run_ingestion

    # 1 get the chunks
    chunks = run_ingestion()

    # 2 check rebuild
    import shutil
    if os.path.exists(FAISS_INDEX_PATH):
        shutil.rmtree(FAISS_INDEX_PATH)
        print("cleared old index")
    
    # 3 build index
    index, final_chunks = get_or_build_index(chunks)

    # 4 test search
    print("\nTesting search...")
    query = "What cleaning services does Amenify offer?"
    query_embedding = np.array([get_embedding(query)], dtype=np.float32)
    faiss.normalize_L2(query_embedding)

    # search top 3
    source, indices = index.search(query_embedding, k=3)
    
    print(f"\nQuery: '{query}' \n")
    for rank, (score, idx) in enumerate(zip(source[0], indices[0])):
        print(f"Rank : {rank+1} | Score: {score:.4f} | Source : {final_chunks[idx]['source']}")
        print(f"-> {final_chunks[idx]['text'][:150]}...")
        print()