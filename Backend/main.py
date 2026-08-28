# main entry point

from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import os

# slowapi powers per-IP rate limiting. It is an OPTIONAL dependency: it is in
# the local dev/test env (pyproject.toml) but NOT in Backend/requirements.txt,
# the Azure Oryx deploy lockfile. Where it is absent, rate limiting is a no-op
# and the app runs exactly as before. To enable it in production, add
# `slowapi` to Backend/requirements.txt and redeploy.
try:
    from slowapi import Limiter
    from slowapi.errors import RateLimitExceeded
    from slowapi.util import get_remote_address
    _SLOWAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - exercised only in the slim deploy env
    _SLOWAPI_AVAILABLE = False

from models import chatResponse,chatRequest, HealthResponse
from chat import chat as process_chat
from retriever import load_index, is_loaded, get_total_chunks
from session import clear_session
from config import ALLOWED_ORIGINS, RATE_LIMIT, LOG_LEVEL
from logging_config import configure_logging, get_logger

configure_logging(LOG_LEVEL)
log = get_logger("amebot")


# we will use lifespan instead of @app.on_event("startup") to load the index
@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    log.info("starting Amenify Support Bot")
    try:
        load_index()
        log.info("faiss index loaded", extra={"n_chunks": get_total_chunks()})
    except FileNotFoundError:
        log.warning("faiss index not found — building from scratch")
        try:
            from ingestion import run_ingestion
            from vector_store import get_or_build_index
            chunks = run_ingestion()
            get_or_build_index(chunks)
            load_index()
            log.info("faiss index built and loaded", extra={"n_chunks": get_total_chunks()})
        except Exception:
            log.exception("FATAL: could not build faiss index")
            raise

    log.info("Amenify Support Bot ready to serve")
    yield
    log.info("shutting down Amenify Support Bot")


# app creation
app = FastAPI(
    title="Amenify Support Bot",
    description=(
        "AI-powered customer support bot for Amenify. "
        "Answers questions using Amenify's knowledge base via RAG "
        "(Retrieval Augmented Generation) with Azure OpenAI."
    ),
    version="1.0.0",
    lifespan=lifespan
)


# rate limiting — per client IP on /chat.
# Azure App Service runs the app behind a reverse proxy, so request.client.host
# is the proxy; key on the first X-Forwarded-For hop instead when present.
_effective_rate_limit = RATE_LIMIT.strip() or "1000000/minute"

if _SLOWAPI_AVAILABLE:
    def _client_ip(request: Request) -> str:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return get_remote_address(request)

    limiter = Limiter(key_func=_client_ip, enabled=RATE_LIMIT.strip() != "")
    app.state.limiter = limiter

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_exceeded(request: Request, exc: RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Please slow down and try again shortly."},
        )
else:  # pragma: no cover - slim deploy env only
    limiter = None


def _rate_limited(func):
    """Apply the slowapi limit to a route, or return it unchanged when slowapi
    is not installed (the Azure deploy env)."""
    if _SLOWAPI_AVAILABLE:
        return limiter.limit(_effective_rate_limit)(func)
    return func


# cors — origins from ALLOWED_ORIGINS ("*" default, so no behaviour change
# on the live site; set a comma-separated list to lock it down)
_allow_origins = ["*"] if ALLOWED_ORIGINS.strip() == "*" else [
    o.strip() for o in ALLOWED_ORIGINS.split(",") if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=False,
)


# get /health for health check
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """
    health check endpoint to check if the server is running and index is loaded
    """
    loaded = is_loaded()
    return HealthResponse(
        status="ok" if loaded else "degraded",
        index_loaded=loaded,
        total_chunks=get_total_chunks() if loaded else 0
    )

@app.post("/chat", response_model=chatResponse)
@_rate_limited
async def chat_endpoint(request: Request, body: chatRequest):

    if not is_loaded():
        raise HTTPException(status_code=503, detail="Index not loaded yet. Please try again later.")
    try:
        result = process_chat(
            message=body.message,
            session_id=body.session_id,
        )

        return chatResponse(
            answer=result["answer"],
            session_id=result["session_id"],
            sources=result["sources"],
            found_in_kb=result["found_in_kb"]
        )
    except Exception:
        log.exception("chat endpoint failed")
        raise HTTPException(status_code=500, detail="An error occurred while processing the chat.")


@app.delete("/session/{session_id}", status_code=204)
async def delete_session(session_id: str):
    """Drop a session's in-memory history. Idempotent — unknown ids also 204."""
    clear_session(session_id)
    return Response(status_code=204)


# Mount static frontend LAST — after all API routes are registered, but
# still at module scope (NOT after the __main__ guard, where it only ran
# by luck of uvicorn re-importing "main:app"). StaticFiles handles GET/HEAD
# only; mounting at "/" before the API routes would shadow POST /chat.
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend")
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")


# entry point
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )