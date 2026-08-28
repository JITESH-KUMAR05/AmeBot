# CLAUDE.md — AmeBot

Guidance for Claude Code (and humans) working in this repo.

## What this is

AmeBot: a FastAPI RAG customer-support bot built as an Amenify recruitment
assignment. Pipeline: follow-up query rewrite → FAISS semantic search → 0.70
similarity gate (below it, answer "I don't know" with **no** LLM call) → Azure
OpenAI GPT answering only from retrieved context → structured JSON reply with
source citations. Deployed on Azure App Service.

## Layout

| Path | Role |
|---|---|
| `Backend/main.py` | FastAPI app, routes, lifespan, CORS, rate limiter, static mount |
| `Backend/config.py` | env loading + fail-fast validation; every tunable constant |
| `Backend/ingestion.py` | KB loader (manual JSON → scraped cache → live scrape) + **word-based** chunker |
| `Backend/vector_store.py` | embed chunks → build/save FAISS `IndexFlatIP` (operator CLI script) |
| `Backend/retriever.py` | load index; embed query; top-k search with the similarity gate |
| `Backend/chat.py` | RAG orchestration; `_rewrite_query`; one structured log record per request |
| `Backend/session.py` | in-memory history — `OrderedDict`, `MAX_HISTORY`=10/session, `MAX_SESSIONS`=5000 LRU |
| `Backend/logging_config.py` | stdlib JSON logging (`JsonFormatter`, `configure_logging`) |
| `Backend/models.py` | Pydantic request/response models |
| `frontend/` | static vanilla-JS chat UI, served by the app at `/` |
| `Backend/tests/` | pytest suite — offline by default, `-m live` hits real Azure |
| `docs/superpowers/` | design spec + task-by-task implementation plan |

## Running

```bash
# app (needs Backend/.env — copy from Backend/.env.example)
cd Backend && python -m uvicorn main:app --reload

# tests
uv run pytest              # offline, no keys, deterministic
uv run pytest -m live      # real Azure (needs AZURE_OPENAI_* set to real values)
uv run pytest --cov=Backend

# docker (portable runtime; not the Azure path)
docker build -t amebot . && docker run --rm -p 8000:8000 --env-file Backend/.env amebot
```

## Endpoints

`POST /chat` · `GET /health` · `DELETE /session/{session_id}` · `GET /` (frontend).

## Conventions

- **Python package manager: `uv`.** `pyproject.toml` + `uv.lock` drive local
  dev/test. `Backend/requirements.txt` + the root `requirements.txt` redirect are
  the Azure Oryx deploy lockfile — **do not delete or restructure them**; keep
  them roughly in sync when runtime deps change
  (`uv export --no-hashes --no-dev`).
- `slowapi` (rate limiting) is an **optional** import in `main.py`: present in
  `pyproject.toml`, absent from `Backend/requirements.txt`. Where it is not
  installed the limiter is a no-op. To turn it on in production, add `slowapi`
  to `Backend/requirements.txt` and redeploy.
- Backend modules import each other by **bare name** (`import config`). Tests
  rely on `pythonpath = ["Backend"]` in `pyproject.toml` — do **not** convert
  `Backend/` into a package.
- Tests are **offline and deterministic**: mock every Azure call, use the
  in-memory FAISS fixture (`fake_index`), calibrate the score gate with
  `low_threshold`. Network/key-dependent checks go under `@pytest.mark.live`
  (double-guarded: collection hook + `skipif`).
- **Never edit** `.github/workflows/main_amenify-support-bot.yml` (deploy). Test
  CI lives in `.github/workflows/tests.yml`.
- `*.sh` is pinned to LF via `.gitattributes` (runs on Linux).
- Commits: small, one logical change, message states the problem then the fix.
- **Do not `git push` or open PRs** — the author integrates branches.

## Known limitations (intentional for an assignment)

In-memory sessions (no Redis), single FAISS instance (no horizontal scale),
static KB, no streaming, word-based chunking. Documented trade-offs, not bugs —
see `README.md` "Section 3: Reasoning & Design" and `docs/superpowers/specs/`.

## Design docs

- Spec: `docs/superpowers/specs/2026-08-28-hardening-tests-docs-design.md`
- Plan: `docs/superpowers/plans/2026-08-28-hardening-tests-docs.md`
