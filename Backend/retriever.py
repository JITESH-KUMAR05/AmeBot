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
    