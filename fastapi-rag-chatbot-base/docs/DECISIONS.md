# Decisions — FastAPI RAG Chatbot Base

This file records *why* things are done a certain way, so you don't re-debate them.

---

## D1 — Auth is decode-only, no token issuance

**Decision**: This service only validates JWTs. It never creates them.

**Why**: This is a microservice that plugs into a larger platform (e.g. a Django backend that handles users, subscriptions, login). Having two services that issue tokens would mean managing two secrets and two token lifetimes. Sharing the secret and decode-only is simpler.

**Trade-off**: This service cannot work standalone — it needs the main backend running and sharing the same `JWT_SECRET_KEY`.

**If you need standalone auth**: Add a `/token` endpoint using `python-jose` + `passlib`, issue tokens here, and remove the `UserAuth` table dependency.

---

## D2 — ChromaDB is local-persistent, not cloud

**Decision**: ChromaDB runs as a persistent local folder (`chroma_db/`).

**Why**: Zero additional infrastructure cost. Works out of the box. Fast for single-instance deployments.

**Trade-off**: Cannot scale horizontally — if you run multiple instances of this service, each has its own ChromaDB and they diverge.

**When to change**: The moment you need more than one instance (load balancer, multiple workers with shared state). Switch to Pinecone, Weaviate, or Qdrant. Change only `services/document.py` and `services/rag.py`.

---

## D3 — Embedding model loaded once at startup, cached

**Decision**: `SentenceTransformer` is instantiated once in `services/rag.py` at module load time, stored in a dict cache.

**Why**: SentenceTransformer models are large (100MB+). Loading per-request would be catastrophically slow (5–30s per call).

**Trade-off**: Memory usage is higher. First startup is slower.

**If you need multiple models at runtime**: The `embedding_model_cache` dict handles this — the first call with a new model name loads and caches it.

---

## D4 — Question condensation before RAG retrieval

**Decision**: Follow-up questions are condensed into standalone questions before embedding.

**Why**: "Tell me more about that" has no vector meaning without the previous context. Condensing it first ("Tell me more about managing anxiety") gives ChromaDB something to search on.

**Trade-off**: One extra LLM call per message (cheap — uses a nano/mini model). Adds ~0.5–1s latency.

**When to skip**: If your chatbot is unlikely to have conversational follow-ups (e.g. single-turn Q&A), remove the `question_with_history()` call to save the extra call.

---

## D5 — System prompt assembled per-request, not cached

**Decision**: The full system prompt (base + coaching style + history + context) is built fresh each time in `query_rag_chat()`.

**Why**: Coaching style comes from onboarding data that can change. History grows per conversation. Context changes per query. All three are dynamic.

**Trade-off**: Slightly more string manipulation per request. Negligible performance impact.

---

## D6 — SQL migrations are inline at startup, not Alembic

**Decision**: `on_startup()` in `database.py` runs `ALTER TABLE IF NOT EXISTS` statements directly.

**Why**: The original project was evolved rapidly and columns were added one by one. Inline migrations are simpler for a small schema.

**Trade-off**: No migration history. Not reversible. No rollback.

**When to change**: If the schema becomes complex or you work with a team. Switch to Alembic. Remove the `on_startup()` migration block and run `alembic init` + `alembic revision --autogenerate`.

---

## D7 — Settings fallback: user DB → global .env

**Decision**: Per-user settings (model name, API key, system prompt) are stored in the DB. If missing, `.env` defaults apply.

**Why**: Allows the admin to customize per deployment without changing code. Also lets power users (admins) override the global settings for testing.

**Trade-off**: Two places to look when debugging "why is it using the wrong model".

---

## D8 — CORS allows all origins in development

**Decision**: `allow_origins=["*"]` in `main.py`.

**Why**: During development it's convenient. The template ships with this.

**Before going to production**: Replace `["*"]` with your actual frontend domain(s). e.g. `["https://yourapp.com", "https://admin.yourapp.com"]`.
