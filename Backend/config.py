# from typing import override
import os
from dotenv import load_dotenv

# Anchor everything to the Backend/ directory so the app works regardless of the
# current working directory (pytest runs from the repo root; some deploy start
# commands do too). Without this, the relative data paths below silently miss
# and ingestion falls back to live-scraping the website.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Set AMEBOT_SKIP_DOTENV=1 to ignore Backend/.env entirely (CI, containers, and
# the offline test suite, which must not pick up real credentials).
if os.getenv("AMEBOT_SKIP_DOTENV", "").lower() not in ("1", "true", "yes"):
    load_dotenv(os.path.join(_BASE_DIR, ".env"), override=True)

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
# Retrieval gate. text-embedding-ada-002 has a HIGH similarity floor: unrelated
# query/chunk pairs still score ~0.69-0.73 cosine, genuinely relevant ones
# ~0.80-0.94 (measured on this KB). 0.70 sat below the noise floor and filtered
# almost nothing; 0.75 sits in the empty gap between the two clusters.
MIN_SIMILARITY_SCORE = 0.75

# API behaviour
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*")  # "*" or comma-separated origins
RATE_LIMIT = os.getenv("RATE_LIMIT", "20/minute")  # per client IP on /chat; "" disables

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
LOG_QUERY_TEXT = os.getenv("LOG_QUERY_TEXT", "false").lower() == "true"  # off = no PII in logs

# Session history setting
MAX_HISTORY = 10  # max number of messages to keep in history
MAX_SESSIONS = 5000  # soft cap on in-memory sessions; least-recently-used evicted first

# Data paths (absolute — anchored to Backend/, see _BASE_DIR above)
MANUAL_DATA_PATH = os.path.join(_BASE_DIR, "data", "amenify_manual.json")
SCRAPED_DATA_PATH = os.path.join(_BASE_DIR, "data", "amenify_scraped.json")
FAISS_INDEX_PATH = os.path.join(_BASE_DIR, "data", "faiss_index")  ## faiss saves as folder

# if the required data and api is not there or missing then crash it

_required = {
    "AZURE_OPENAI_API_KEY": AZURE_OPENAI_API_KEY,
    "AZURE_OPENAI_ENDPOINT": AZURE_OPENAI_ENDPOINT,
    "AZURE_OPENAI_DEPLOYMENT_NAME": AZURE_OPENAI_DEPLOYMENT_NAME,
    "AZURE_OPENAI_API_VERSION": AZURE_OPENAI_API_VERSION,
    "AZURE_EMBEDDING_MODEL": AZURE_EMBEDDING_MODEL
}

# if anything goes wrong ie the required data and api is not there or missing then crash it so we are failing fast instead of failing after first message is sent
for name,value in _required.items():
    if not value:
        raise EnvironmentError(f"Missing required environment variable: {name}")

