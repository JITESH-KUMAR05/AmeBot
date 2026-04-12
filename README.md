# AmeBot — Amenify Customer Support Bot

An AI-powered customer support chatbot built for the Amenify.

**Live Demo:** https://amenify-support-bot-faagfdfwdhbggae7.canadacentral-01.azurewebsites.net

---

## What it does

AmeBot answers questions about Amenify's services using a RAG (Retrieval-Augmented Generation) pipeline. It only answers from a curated knowledge base — if it doesn't know, it says so.

---

## Architecture

```
User message
    ↓
Query Rewriter        — handles follow-ups like "who founded it?"
    ↓
FAISS Vector Search   — semantic search over 19 KB chunks
    ↓
Similarity Threshold  — score < 0.70 → "I don't know" (no LLM call)
    ↓
Azure OpenAI GPT      — answers from retrieved context only
    ↓
Response              — answer + source citations + session_id
```

**Stack:**

| Layer | Tech |
|---|---|
| Backend | FastAPI (Python 3.11+) |
| LLM | Azure OpenAI GPT-4 |
| Embeddings | Azure text-embedding-ada-002 |
| Vector Store | FAISS IndexFlatIP |
| Sessions | In-memory dict |
| Frontend | HTML / CSS / Vanilla JS |
| Hosting | Azure App Service (Linux B1) |

---

## Project Structure

```
AmeBot/
├── Backend/
│   ├── main.py          # FastAPI app, routes, lifespan
│   ├── config.py        # Env variable loading and validation
│   ├── ingestion.py     # Data loader + BeautifulSoup scraper + chunker
│   ├── vector_store.py  # Embedding pipeline + FAISS index builder
│   ├── retriever.py     # Semantic search (query → top-k chunks)
│   ├── chat.py          # RAG pipeline (retrieve → prompt → LLM)
│   ├── session.py       # Chat history manager (per session)
│   ├── models.py        # Pydantic request/response models
│   └── data/
│       ├── amenify_manual.json   # Hand-curated KB (19 documents)
│       └── amenify_scraped.json  # Scraped fallback cache
├── frontend/
│   ├── index.html
│   ├── style.css
│   ├── app.js
│   └── amenify-theme.css
├── requirements.txt
└── README.md
```

---

## Local Setup

**Prerequisites:** Python 3.11+, Azure OpenAI resource (GPT-4 + text-embedding-ada-002 deployments)

### 1. Clone and install

```bash
git clone https://github.com/JITESH-KUMAR05/AmeBot.git
cd AmeBot/Backend
pip install -r requirements.txt
```

### 2. Set up environment

Create `Backend/.env`:

```env
AZURE_OPENAI_API_KEY=your_key
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=your_gpt_deployment
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_EMBEDDING_MODEL=text-embedding-ada-002
```

### 3. Build the FAISS index

```bash
python vector_store.py
```

This embeds the knowledge base and saves the FAISS index to `data/faiss_index/`. On first run in production, `main.py` does this automatically at startup.

### 4. Run locally

```bash
python main.py
```

- Chat UI: http://localhost:8000
- API docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

---

## API

### POST /chat

```json
// Request
{
  "message": "What services does Amenify offer?",
  "session_id": null
}

// Response
{
  "answer": "Amenify offers house cleaning, handyman services, dog walking...",
  "session_id": "abc-123",
  "sources": ["Amenify Services Overview"],
  "found_in_kb": true
}
```

Pass `session_id` back on subsequent requests to maintain conversation history.

### GET /health

```json
{ "status": "ok", "index_loaded": true, "total_chunks": 19 }
```

---

## Section 3: Reasoning & Design

### 1. How did I ingest and structure the data?

I used a two-source approach:

- **Primary:** A hand-curated JSON file (`amenify_manual.json`) with 19 verified documents covering services, pricing, coverage, FAQs, etc. This is the main source because scraped content tends to be noisy.
- **Fallback:** A BeautifulSoup scraper that fetches 8 key pages from amenify.com and caches results to `amenify_scraped.json`.

**Processing pipeline:**
1. Fetch pages with `requests`, parse with `BeautifulSoup`
2. Strip noise tags (`<script>`, `<nav>`, `<footer>`)
3. Filter out short lines (< 25 chars) — removes nav links, button text
4. Split into ~500 token chunks with 50-token overlap
5. Tag each chunk with `{text, source, url}`
6. Embed with `text-embedding-ada-002` → store in FAISS `IndexFlatIP`
7. Normalize vectors to unit length so inner product equals cosine similarity

---

### 2. How did I reduce hallucinations?

Three independent layers:

**Layer 1 — Similarity threshold (retrieval gate)**

```python
MIN_SIMILARITY_SCORE = 0.70
# Score below this → return "I don't know" immediately, no LLM call
```

The LLM is never called if the question doesn't match something in the knowledge base. This alone eliminates most hallucinations.

**Layer 2 — Strict system prompt**

```
Answer ONLY using the CONTEXT section below.
Do NOT use any outside knowledge or training data.
Never fabricate prices, phone numbers, dates, or URLs.
If context doesn't contain the answer → return the fallback message exactly.
```

**Layer 3 — Temperature = 0**

```python
temperature=0  # deterministic output, no creative fabrication
```

---

### 3. What are the limitations?

| Limitation | Notes |
|---|---|
| In-memory sessions | Chat history lost on server restart |
| Static knowledge base | Doesn't reflect new Amenify updates automatically |
| Single FAISS instance | Can't scale horizontally — instances don't share the index |
| No pricing data | Amenify doesn't publish fixed prices, so the bot can't answer pricing questions |
| Scraper fragility | If Amenify redesigns their site, the scraper needs updating |
| No rate limiting | Any user can hit the API without limits |
| Fixed chunk size | Answers spanning multiple chunks may be partially missed |

---

### 4. How would I scale this?

**Sessions → Redis**

Replace the Python dict in `session.py` with Redis. One file change, everything else stays the same. Sessions persist across restarts and are shared across instances.

**Vector store → Managed cloud search**

Replace FAISS with Azure Cognitive Search (vector search) or Pinecone. Cloud-hosted, shared across all instances, supports live updates.

**Horizontal scaling**

```
Load Balancer
├── FastAPI instance 1 ──┐
├── FastAPI instance 2 ──┤── Azure Cognitive Search (shared)
└── FastAPI instance 3 ──┘── Redis (shared sessions)
```

Deploy on Azure Container Apps with auto-scaling.

**Automated KB updates**

A scheduled Azure Function runs nightly, scrapes amenify.com for changes, re-embeds new/updated content, and hot-swaps the index with zero downtime.

---

### 5. What would I improve for production?

**Retrieval quality**
- Hybrid retrieval: BM25 (keyword) + FAISS (semantic) combined. Better for exact queries like "cancellation policy"
- Cross-encoder re-ranking: re-rank top-10 results, return top-3

**UX**
- Streaming responses via Server-Sent Events — token-by-token output, much better feel

**Observability**
- Log every query, retrieved chunks, latency, and LLM response to Azure Monitor
- Thumbs up/down feedback on each reply → use to tune the similarity threshold
- Dashboard showing top unanswered questions → find knowledge base gaps

**Security**
- Rate limiting per IP (e.g., `slowapi`)
- Input sanitization to block prompt injection attempts
- JWT auth if embedded in a resident portal

---

## Example Queries

**"What services does Amenify offer?"**
```
Amenify offers AI-powered home services including house cleaning, handyman
work, grocery delivery, dog walking, pool cleaning, lawn care, move-out
cleaning, and more, available through their mobile app.

Sources: [Amenify Services Overview, Cleaning Services]
```

**"What is the Resident Protection Plan?"**
```
The Amenify Resident Protection Plan is an optional subscription that covers
accidental everyday damages: up to $1,000/year for accidental damage, $50
for key/fob replacement, $50 for lockouts, $50 for missed maintenance, and
$200 for hotel stays if displaced.

Sources: [Resident Protection Plan Details]
```

**"Who is the CEO of Apple?"**
```
I don't have information about that. For further help, please contact
Amenify support at +1-719-767-1963 or visit amenify.com/contact-us

Sources: []
```

---

## Author

**Jitesh Kumar**
- LinkedIn: [linkedin.com/in/jitesh-kumar05](https://linkedin.com/in/jitesh-kumar05)
- GitHub: [github.com/JITESH-KUMAR05](https://github.com/JITESH-KUMAR05)

