# BRIEF — FastAPI RAG Chatbot Base

## What this template is for

A FastAPI backend for AI chatbots that use **Retrieval-Augmented Generation (RAG)**.
Use this when your project needs:
- Document upload (PDF/DOCX/TXT) → chunk → embed → store in a vector DB
- A chat endpoint that retrieves relevant context before calling an LLM
- Per-user conversation history saved in a SQL database
- JWT-based auth (token issued by a separate backend, validated here)
- Admin-only controls: upload docs, manage settings, view analytics

## What it is NOT for

- Projects that only call an LLM directly (no documents / no vector search) → use `llm-chatbot-base` instead
- Projects that need LangChain agents or multi-step tool calls → use `agent-pipeline-base` instead
- Projects that generate images, audio, or run code → this template has none of that

## Stack

| Layer | Tech |
|---|---|
| API framework | FastAPI + Uvicorn |
| LLM | OpenAI (GPT models) |
| Embeddings | SentenceTransformers (local) or OpenAI Embeddings |
| Vector DB | ChromaDB (persistent, local folder) |
| SQL DB | PostgreSQL via SQLAlchemy (SQLite for local dev) |
| Auth | JWT decode only — token is issued by your main Django/Node backend |
| Doc parsing | pypdf, python-docx |
| Text chunking | LangChain RecursiveCharacterTextSplitter |

## Key design decisions

See `DECISIONS.md` for the full rationale. Short version:
- Auth is **decode-only** — this service never issues tokens
- ChromaDB is local-persistent, not cloud — swap to Pinecone/Weaviate when scale demands
- Embedding model is loaded **once at startup** and cached — not per-request
- Settings (system prompt, model, API key) are **per-user in the DB**, with global `.env` fallback

## When to clone this

A new project comes in that matches this checklist:
- [ ] Users upload documents the chatbot should "know about"
- [ ] Chat responses should cite or be grounded in those documents
- [ ] Each user should have their own chat history
- [ ] Auth tokens come from a separate backend
