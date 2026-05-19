# fastapi-rag-chatbot-base

Base template for FastAPI services with RAG (Retrieval-Augmented Generation).

## What this includes

- Document upload (PDF) → chunk → embed → ChromaDB
- RAG chat endpoint with conversation history
- Per-user settings (system prompt, LLM model, API key)
- JWT auth (decode-only — token issued by your main backend)
- Admin-only routes for document management and analytics
- PostgreSQL via SQLAlchemy (SQLite for local dev)
- Docker-ready

## Quick start

```bash
cp .env.example .env
# fill in your keys

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8080

# API docs
open http://localhost:8080/docs
```

## Docs

| File | Purpose |
|---|---|
| `docs/BRIEF.md` | When to use this template vs others |
| `docs/ARCHITECTURE.md` | System design and request flows |
| `docs/DECISIONS.md` | Why things are built the way they are |
| `docs/CHECKLIST.md` | Step-by-step setup after cloning |
| `docs/SETUP.md` | Installation and endpoint reference |

## Project structure

```
app/
├── main.py           — FastAPI app, routes (thin layer)
├── config.py         — Env vars, model lists, system prompt
├── auth.py           — JWT decode dependency
├── database.py       — ORM models, session, startup migrations
├── schemas.py        — Pydantic request/response models
└── services/
    ├── document.py   — File parsing, chunking, ChromaDB
    ├── rag.py        — Chat logic, history, LLM calls
    └── settings.py   — Chat & API settings management
docs/
tests/
```

## Built from

MindRise AI chatbot section — refactored into a reusable base.
