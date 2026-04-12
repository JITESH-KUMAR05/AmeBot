# from typing import override
import os
from dotenv import load_dotenv

load_dotenv(override=True)

# Azure OpenAI
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION")
AZURE_EMBEDDING_MODEL = os.getenv("AZURE_EMBEDDING_MODEL")

# Retrieval settings
CHUNK_SIZE = 500  # max token per chunk
CHUNK_OVERLAP = 50  # max token overlap between chunks
TOP_K = 4  # number of chunks to retrieve
MIN_SIMILARITY_SCORE = 0.70  # minimum similarity score to consider a chunk relevant otherwise response I don't know

# Session history setting
MAX_HISTORY = 10  # max number of messages to keep in history

# Data paths
MANUAL_DATA_PATH = "data/amenify_manual.json"
SCRAPED_DATA_PATH = "data/amenify_scraped.json"
FAISS_INDEX_PATH = "data/faiss_index"  ## faiss saves as folder

# if the required data and api is not there or missing then crash it

_required = {
    "AZURE_OPENAI_KEY": AZURE_OPENAI_API_KEY,
    "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
    "AZURE_OPENAI_DEPLOYMENT_NAME": AZURE_OPENAI_DEPLOYMENT_NAME,
    "AZURE_OPENAI_API_VERSION": AZURE_OPENAI_API_VERSION,
    "AZURE_EMBEDDING_MODEL": AZURE_EMBEDDING_MODEL
}

# if anything goes wrong ie the required data and api is not there or missing then crash it so we are failing fast instead of failing after first message is sent
for name,value in _required.items():
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")
    
print("Config loaded successfully")

