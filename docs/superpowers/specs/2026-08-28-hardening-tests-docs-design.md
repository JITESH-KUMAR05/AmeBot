# Design — AmeBot Hardening, Test Suite, Docs & Interview Prep

**Date:** 2026-08-28
**Branch:** `fix/hardening-and-tests` (off `main` @ `fe60afe`)
**Author:** Jitesh Kumar (with Claude Code)

---

## 1. Context

AmeBot is a FastAPI Retrieval-Augmented-Generation (RAG) customer-support bot
built as a recruitment assignment for Amenify. It is deployed live on Azure App
Service. The pipeline: query rewrite -> FAISS semantic search -> similarity
threshold gate -> Azure OpenAI GPT answering from retrieved context only ->
structured response with source citations.

Current state:

- Works end-to-end in production.
- **Zero automated tests.**
- Several latent bugs (query-rewrite fails on trailing punctuation, blank-message
  crash path, misleading fail-fast label, unbounded session dict, fragile static
  mount placement, broken `startup.sh`, divide-by-zero risk, dead/dup code).
- Documentation has drifted from the implementation (chunking described as
  token-based when it is word-based; wrong character threshold).

Goal: make the project demonstrably solid for a portfolio / resume and for
interview discussion, **without any risk to the live Azure deployment**.

---

## 2. Goals

1. Fix every functional bug found in code review (B1–B10 below).
2. Add four scoped, resume-relevant features: per-IP rate limiting, a real
   `/clear` session endpoint, `.env.example` + `Dockerfile`, structured request
   logging.
3. A full **offline** pytest suite (no network, no API key, deterministic) plus
   an **opt-in live smoke suite** that exercises real Azure when credentials are
   present.
4. Adopt `uv` for local development and testing only. Leave the Azure deploy
   path (`Backend/requirements.txt` + root redirect + GitHub workflow) untouched.
5. Update `README.md` and add a maintained `CLAUDE.md`.
6. Produce an interview-preparation deep-dive + Q&A set in a **sibling folder
   outside the repository** so it is never pushed.
7. All code work on one branch, as small commits whose messages read
   *problem -> fix*. No `git push`, no PR — the author pushes manually.

---

## 3. Non-goals

- No Redis / horizontal-scale / managed-vector-store work. These are documented,
  intentional trade-offs for an assignment-scoped project.
- No SSE / streaming responses. Large frontend change, out of scope.
- No changes to `Backend/requirements.txt`, the root `requirements.txt` redirect,
  or `.github/workflows/main_amenify-support-bot.yml` (the deploy pipeline).
- No `git push`, no pull request. The author integrates the branch.

---

## 4. Bugs to fix

| ID  | Location | Problem | Fix |
|-----|----------|---------|-----|
| B1  | `Backend/chat.py` `_rewrite_query` | Follow-up detection tokenises with `message.lower().split()`, so `"who founded it?"` yields `"it?"`, which is not in `FOLLOW_UP_WORDS`. Query rewrite — a headline feature — silently fails whenever the user's follow-up ends in punctuation. | Normalise each token (`strip(string.punctuation)`) before the set intersection. |
| B2  | `Backend/chat.py` `chat()` + `Backend/models.py` | `chatRequest.message` enforces `min_length=1` on the raw string, so `"   "` is accepted. `chat()` then does `message.strip()` -> `""`, which is embedded. Azure returns 400 or the retrieval is meaningless. | After `strip()`, if empty -> return `NO_ANSWER_RESPONSE` immediately (no embed, no LLM). |
| B3  | `Backend/config.py` `_required` | Dict key label is `"AZURE_OPENAI_KEY"` but the actual environment variable is `AZURE_OPENAI_API_KEY`. The fail-fast `EnvironmentError` names a variable that does not exist. | Rename the label to `AZURE_OPENAI_API_KEY`. |
| B4  | `Backend/session.py` | `_sessions` is a `defaultdict(list)`; `get_history` does `_sessions[session_id]`, which **creates** an entry for any id passed in. A client sending random/invalid `session_id`s grows memory without bound, and `session_exists` returns `True` after a mere read. | Use a plain `dict`; `get_history` returns `_sessions.get(session_id, [])`. Add a soft cap of `MAX_SESSIONS = 5000` total sessions (`OrderedDict`, evict oldest on insert) so the documented "in-memory sessions" limitation is not trivially abusable. |
| B5  | `Backend/main.py` (bottom) | `app.mount("/", StaticFiles(...))` is module-level code placed **after** the `if __name__ == "__main__": uvicorn.run(...)` block. It executes only because uvicorn re-imports the module via the `"main:app"` import string. Fragile and confusing. | Move the mount to run immediately after the route declarations, before the `__main__` guard. |
| B6  | `Backend/main.py` `health_check` | Returns `status="discarded"` when the index is not loaded. Meaningless token; README and API contract imply `"ok"` / a degraded state. | Return `"degraded"`. |
| B7  | `Backend/startup.sh` | `cd /Backend` is an absolute path; it fails everywhere. | `cd "$(dirname "$0")"` then run uvicorn. |
| B8  | `Backend/retriever.py` `_embed_query` | `vec = vec / np.linalg.norm(vec)` divides by zero -> `NaN` vector if the embedding is all-zeros (degenerate input, upstream error). | Guard: if norm is `0`, raise a clear `ValueError` (paired with B2, this path becomes unreachable in normal use but is now safe). |
| B9  | `Backend/vector_store.py`, `Backend/retriever.py` | Dead / duplicate code: `import shutil` appears twice in `vector_store.py`; `query_vec.reshape(1, -1)` is called twice in `retriever.retrieve` (`_embed_query` already reshapes); `tiktoken` is pinned in `requirements.txt` but never imported. | Remove the duplicate import and redundant reshape. Leave `tiktoken` pinned (transitive-safe) but note in README that chunking is word-based, not token-based. |
| B10 | `README.md`, `Backend/ingestion.py` | README says "~500 token chunks with 50-token overlap" and "Filter out short lines (< 25 chars)". Code chunks by **words** (`text.split()`, `start + CHUNK_SIZE`) and filters lines with `len(line.strip()) > 30`. | Correct README wording to "~500-word chunks / 50-word overlap" and "lines shorter than 30 characters"; add a clarifying comment in `chunk_text`. |
| B11 | `Backend/main.py` CORS | `allow_origins=["*"]` is unnecessary (the frontend is served same-origin) though not a security hole here (no auth, `allow_credentials=False`). | Make origins configurable via `ALLOWED_ORIGINS` env; **default stays `["*"]`** to guarantee no behaviour change on the live site. Low priority. |

---

## 5. Features

### F1 — Per-IP rate limiting (`slowapi`)

- Add `slowapi` to dev deps and to `Backend/requirements.txt` regen notes.
- `Limiter` with a custom `key_func` that reads the first `X-Forwarded-For` hop
  (Azure App Service runs behind a reverse proxy; `request.client.host` is the
  proxy) and falls back to `get_remote_address`.
- `@limiter.limit(RATE_LIMIT)` on `POST /chat`. `RATE_LIMIT` env, default
  `"20/minute"`. Empty string disables the limiter entirely — required for
  deterministic tests.
- Custom 429 handler returns JSON `{"detail": "Rate limit exceeded. Try again shortly."}`.

### F2 — `DELETE /session/{session_id}`

- New route -> `session.clear_session(session_id)` (function already exists,
  currently unused) -> `204 No Content`. Idempotent: unknown id also returns 204.
- No new Pydantic model.
- Frontend `clearChat()` in `frontend/app.js`: before setting `session_id = null`,
  if a `session_id` exists, fire `fetch(DELETE ...)` (best-effort, errors ignored).

### F3 — `.env.example` + `Dockerfile`

- `.env.example` at repo root **and** `Backend/.env.example` (Backend is the app
  root when run locally). All five Azure vars plus `RATE_LIMIT`,
  `ALLOWED_ORIGINS`, `LOG_LEVEL`, `LOG_QUERY_TEXT`, with placeholder values and
  one-line comments.
- `Dockerfile` (build context = repo root, app = `Backend/`): `python:3.11-slim`,
  install `Backend/requirements.txt`, copy `Backend/` and `frontend/`,
  `CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]`,
  `WORKDIR /app/Backend`.
- `.dockerignore` (tests, `.venv`, `__pycache__`, `data/faiss_index`, `.git`).
- README: `docker build` / `docker run` instructions. **Azure pipeline unchanged.**

### F4 — Structured request logging

- `Backend/logging_config.py`: a hand-rolled `JsonFormatter` (stdlib `logging`
  only, no new dependency) + `configure_logging()` reading `LOG_LEVEL`
  (default `INFO`).
- `chat()` emits exactly one INFO record per request with fields: `session_id`,
  `message_len`, `rewritten` (bool), `top_score` (float or null), `n_chunks`,
  `found_in_kb`, `latency_ms`. The raw message text is included **only** when
  `LOG_QUERY_TEXT=true` (default false — PII).
- Replace ad-hoc `print()` in `chat.py` / `retriever.py` / `main.py` lifespan
  with logger calls. `ingestion.py` / `vector_store.py` keep `print()` — they are
  operator-run CLI scripts.

---

## 6. Testing

### Layout

```
Backend/
  tests/
    __init__.py
    conftest.py          # fixtures (below)
    test_ingestion.py    # fallback chain, chunk_text edges (empty, short tail, overlap)
    test_session.py      # trim to MAX_HISTORY, isolation, clear, B4 no-autocreate, size cap
    test_retriever.py    # threshold filter, idx == -1 skip, B8 zero-norm, score -> dict shape
    test_rewrite.py      # B1 "who founded it?" fires; no history; no follow-up word; multi-turn
    test_chat.py         # mocked LLM + retrieve: kb hit, kb miss, LLM error -> fallback, B2 blank
    test_api.py          # TestClient: /health, POST /chat (200/422/503), DELETE /session, 429
    test_live.py         # @pytest.mark.live — real Azure, auto-skip without AZURE_* env
pytest.ini               # markers = live; testpaths = Backend/tests; filterwarnings
```

### Fixtures (`conftest.py`)

- **`fake_embedding(text) -> np.ndarray`** — deterministic: seed a
  `numpy.random.default_rng` from `hashlib.sha256(text)` -> 1536 float32,
  L2-normalised. Same text always yields the same vector, so retrieval in tests
  is semantically meaningful (identical query and chunk text -> score ~1.0).
- **`fake_index`** — build a genuine `faiss.IndexFlatIP(1536)` from ~5 canned
  chunks embedded via `fake_embedding`; monkeypatch `retriever._index`,
  `retriever._chunks`.
- **`mock_azure`** — monkeypatch `chat._client.chat.completions.create` to return
  a minimal object shaped like `ChatCompletion` (canned answer echoing context);
  monkeypatch every `embeddings.create` call site
  (`retriever._embed_client`, `vector_store.client`) to `fake_embedding`.
- **`client`** — `TestClient(app)` (triggers lifespan with the fake index);
  `RATE_LIMIT=""`.
- **autouse `_env`** — `monkeypatch.setenv` fake `AZURE_*` values so importing
  `config.py` does not raise.

### Method

- Test-driven for the bugs: for each of B1–B10 write a test that reproduces the
  defect (red), then apply the fix (green). Follows the systematic-debugging and
  test-driven-development skills.
- Offline suite target: no network, no key, deterministic, < 5 s total.
- `test_live.py`: 2–3 tests — real embed of `"who founded Amenify"` returns the
  `About Amenify` source; real chat answers from supplied context; an
  out-of-domain query returns the fallback string. Run with `pytest -m live`.

### CI

- **New** file `.github/workflows/tests.yml`: on `push` / `pull_request`, set up
  Python 3.11, `pip install -r Backend/requirements.txt pytest pytest-cov`,
  `pytest -m "not live"`. No Azure secrets referenced. Additive — the existing
  deploy workflow is not edited.

---

## 7. `uv` adoption (dev / test only)

- Root `pyproject.toml`: `[project]` metadata, `requires-python = ">=3.11"`,
  `dependencies` mirroring the runtime packages (loose pins), plus
  `[dependency-groups] dev = ["pytest", "pytest-cov", "httpx", ...]`.
- Commit `uv.lock` and `.python-version` (`3.11`).
- `Backend/requirements.txt`, root `requirements.txt`: **unchanged**. They remain
  the deploy lockfile consumed by Azure Oryx. README documents the divergence and
  the regen command (`uv export --no-hashes --no-dev`).
- The system interpreter here is 3.14 (no faiss/numpy wheels); the test
  environment is created with `uv venv --python 3.11`.
- Local workflow: `uv sync`, `uv run pytest`.

---

## 8. Documentation

- **`README.md`** — correct B10 wording; new sections: *Running the tests*
  (`uv run pytest`, `-m live`), *Running with Docker*, *`DELETE /session/{id}`*,
  an environment-variable table (adds `RATE_LIMIT`, `ALLOWED_ORIGINS`,
  `LOG_LEVEL`, `LOG_QUERY_TEXT`), rate-limit behaviour. Keep the assignment-facing
  "Section 3: Reasoning & Design" Q&A; correct any now-stale claim.
- **`CLAUDE.md`** (repo root, committed on this branch) — project overview,
  architecture, directory map, run/test commands, conventions (`uv` default,
  pytest markers, **no-push rule: the author pushes**, small-commit style),
  "known limitations are intentional" list, pointers to this spec. Updated as
  each commit lands.
- **This spec** — `docs/superpowers/specs/2026-08-28-hardening-tests-docs-design.md`.

---

## 9. Interview preparation (outside the repo)

Location: `C:\D\python\AmeBot-interview-prep\` — a sibling of the repo directory,
never staged or pushed.

| File | Contents |
|------|----------|
| `00-project-walkthrough.md` | End-to-end tour: every module, every function, the data flow, and the reasoning behind each decision (embedding model choice, `IndexFlatIP` vs alternatives, the 0.70 threshold, query-rewrite rationale, prompt design, session model). |
| `01-architecture-and-tradeoffs.md` | Diagrams, the scaling story, cost/latency profile, what changes at 10x / 100x. |
| `02-likely-questions.md` | Categorised Q&A: RAG fundamentals, vector-search maths (cosine vs inner product vs L2, why normalise), hallucination mitigation layers, FastAPI/async, testing strategy, "why not LangChain", "how would you evaluate this", system-design follow-ups, behavioural ("this was an Amenify assignment and you did not get the role — what would you change"). |
| `03-code-deep-dive-QA.md` | Line-level drills: "walk me through `retriever.py`", "what happens on a follow-up question", "where could this break". |
| `04-live-demo-script.md` | How to run locally during the interview, the exact queries to show, what each one demonstrates. |
| `05-gaps-and-honest-answers.md` | Known weaknesses with mature, non-defensive answers. |

---

## 10. Branch & commit plan

Branch: `fix/hardening-and-tests` from `main` @ `fe60afe`.

Commit sequence (each message states the problem, then the fix):

1. `docs: add hardening/testing design spec`
2. `build: add uv pyproject + dev deps (deploy requirements.txt untouched)`
3. `test: add pytest scaffold + offline fixtures (fake embeddings/index)`
4. `fix(chat): detect follow-ups when the query has trailing punctuation` (+ test) — B1
5. `fix(chat): guard empty/whitespace-only messages before embedding` (+ test) — B2
6. `fix(config): name the real AZURE_OPENAI_API_KEY var in the fail-fast check` — B3
7. `fix(session): stop the defaultdict auto-creating sessions on read; cap size` (+ test) — B4
8. `fix(retriever): guard zero-norm embeddings; drop the redundant reshape` (+ test) — B8, B9
9. `refactor(main): hoist the static-file mount above the __main__ guard` — B5
10. `fix(main): health reports "degraded", not "discarded", when the index is down` — B6
11. `fix(startup): use a relative path in startup.sh; remove the duplicate import; make CORS origins configurable` — B7, B9, B11
12. `feat(api): DELETE /session/{id}; wire the frontend clear button to it` (+ test) — F2
13. `feat(api): per-IP rate limiting on /chat via slowapi (configurable)` (+ test) — F1
14. `feat(obs): one structured JSON log record per chat request` — F4
15. `chore: add .env.example, Dockerfile, .dockerignore` — F3
16. `test: API integration tests (health/chat/session/429) + opt-in live smoke` 
17. `ci: add an offline test workflow (deploy pipeline untouched)`
18. `docs: update README (tests, docker, endpoints, env vars, chunking wording)` — B10
19. `docs: add CLAUDE.md`

No `git push`. No PR. End state: `git status` clean, `git log --oneline main..HEAD`
reads as a clean narrative.

Conflict avoidance: branch from current `main` HEAD; only the files named in this
spec are touched; no rebase; the author performs the merge.

---

## 11. Verification before declaring done

- `uv run pytest` -> all green; output shown.
- `uv run pytest -m live` -> collected and skipped here (no creds); shown.
- `python -m py_compile` on every changed `.py`.
- Frontend: static review of the `clearChat()` fetch change (no browser runner
  available); noted as such.
- `git status`; `git log --oneline main..HEAD`.

---

## 12. Out-of-branch side tasks

- Save standing instructions to Claude memory: no-push (author pushes), small
  commit style, interview-prep sibling location, this project's context.
- Global `~/.claude/CLAUDE.md`: default to `uv` as the package manager for all
  Python work.

---

## 13. Addendum — issues found during live verification (real Azure)

Running the suite (and a container) against a live Azure OpenAI resource
surfaced four more issues beyond B1–B11. All fixed with tests.

| ID  | Problem | Fix |
|-----|---------|-----|
| B12 | `config.py` data paths were CWD-relative (`data/...`). Run from anywhere but `Backend/` (pytest from repo root; some deploy start commands), the 19-doc manual KB is not found and `load_raw_documents()` silently falls back to **live-scraping amenify.com**. | All data paths + the `.env` load are absolute, anchored to `_BASE_DIR = dirname(abspath(__file__))`. `AMEBOT_SKIP_DOTENV=1` opts out of the `.env` file (CI / containers / offline tests). |
| B13 | `MIN_SIMILARITY_SCORE = 0.70` is below `text-embedding-ada-002`'s similarity floor. Measured on this KB: out-of-domain questions score ~0.69–0.73 cosine, in-domain 0.80–0.94. The gate filtered almost nothing; junk queries reached the LLM (the strict prompt then refused). | Raised to **0.75** (empty gap between the clusters). README Layer-1 section updated with the measured numbers. |
| B14 | `_rewrite_query` still had a debug `print(f"... '{msg}' → '{rewritten}'")` with a U+2192 arrow (missed by the Task-12 logging refactor). On a non-UTF-8 stdout (Windows cp1252) `print` raises `UnicodeEncodeError` → `/chat` returns 500 → **every follow-up question crashes**. | `log.debug` with an ASCII arrow. `_call_llm`'s `print` → `log.exception`. `JsonFormatter` now emits `ensure_ascii=True` so no log line can crash on stdout encoding. Regression test forbids `print()` in the request path. |
| —   | `pytest -m live` could not run standalone — module collection imported the app with the conftest stub creds before `test_live` loaded `.env`. | `conftest.pytest_configure` loads `Backend/.env` when the run is `-m live`, before any app import. The creds guard keys on API-key + endpoint (the embedding-model name is legitimately `text-embedding-ada-002` on real resources too). |

### Live verification performed

- `uv run pytest -m live` → **3/3 pass** against real Azure (`gpt-4o` +
  `text-embedding-ada-002`).
- Full HTTP smoke via `TestClient`: health, KB answer, follow-up rewrite
  ("who founded it?" → resolves to Amenify's founders), out-of-domain refusal,
  `DELETE /session`.
- `docker build` + `docker run` with real env: container boots, builds the
  index from the manual KB (`total_chunks: 19`, not scraped), serves `/health`
  and `/chat`, rate limiting fires (20×200 then 429), structured JSON logs emit
  one record per request.
