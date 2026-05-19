# Architecture — FastAPI RAG Chatbot Base

## System overview

```
[Client App]
     │
     │  HTTP (Bearer JWT)
     ▼
[FastAPI Service]  ← This repo
     │
     ├── app/routes/        API route handlers (thin — just parse, delegate, return)
     ├── app/services/      All business logic lives here
     │     ├── rag.py       Embedding, retrieval, LLM call, history injection
     │     ├── document.py  File parsing, chunking, ChromaDB writes
     │     └── settings.py  Chat settings, API key management
     ├── app/models/        SQLAlchemy ORM models (DB tables)
     ├── app/schemas.py     Pydantic request/response models
     ├── app/auth.py        JWT decode dependency
     ├── app/config.py      Env vars + global defaults
     └── app/database.py    Engine, session, startup migrations
     │
     ├── ChromaDB (local folder: chroma_db/)
     │     └── Stores: text chunks + their embeddings, keyed by filename
     │
     └── PostgreSQL (or SQLite for dev)
           ├── conversations       (id, user_id, title, timestamps)
           ├── chat_messages       (id, conversation_id, role, content, response_time)
           ├── uploaded_documents  (id, filename, upload_timestamp)
           ├── chat_settings       (user_id, system_prompt, model, max_tokens)
           ├── api_settings        (user_id, provider, llm_api_key, embedding_model)
           └── [account_userauth]  (read-only — owned by main backend)
```

## Request flow — chat message

```
POST /api/send
  1. JWT decoded → user_id extracted
  2. Subscription check (UserAuth table)
  3. Conversation created or fetched
  4. Recent chat history loaded from DB
  5. Follow-up question condensed into standalone query (LLM call)
  6. Query embedded → ChromaDB queried → top-3 chunks retrieved
  7. System prompt assembled:
       base_prompt + coaching_style + history_summary + retrieved_context
  8. Full message list sent to LLM
  9. Response + response_time saved to DB
 10. Conversation title generated on first non-greeting message
 11. ChatResponse returned to client
```

## Request flow — document upload

```
POST /api/upload  (admin only)
  1. Superuser check
  2. File read → text extracted (pypdf / python-docx)
  3. Text split into chunks (1000 chars, 200 overlap)
  4. Chunks embedded → stored in ChromaDB (old chunks for same filename deleted first)
  5. Document metadata saved to SQL DB
```

## Auth model

This service **does not issue JWTs**. It only decodes them.
- Token is issued by the main backend (Django, Node, etc.)
- This service shares the same `JWT_SECRET_KEY`
- `user_id` is extracted from the token payload
- Superuser check reads from `account_userauth` table (owned by main backend)

## Settings hierarchy

```
Per-user settings (DB)  →  System defaults (.env / config.py)
```
If a user has no custom settings, global defaults apply.
Admin users can update settings via `/api/settings/chat` and `/api/settings/api`.

## ChromaDB collection structure

- One collection per deployment (configurable via `COLLECTION_NAME` in config)
- Documents keyed by filename — re-uploading same filename replaces old chunks
- Metadata stored per chunk: `{ source: filename, chunk_index: int }`

## Scaling notes

| Component | Current | When to upgrade |
|---|---|---|
| ChromaDB | Local folder | Switch to Pinecone / Weaviate when multiple instances needed |
| Embedding | Local SentenceTransformer | Switch to OpenAI Embeddings API for better quality |
| SQL | PostgreSQL (Neon for prod) | Fine for most loads; add read replicas if needed |
| LLM | OpenAI | Swap client in `services/rag.py` for Anthropic/Gemini/local |
