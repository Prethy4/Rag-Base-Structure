# Checklist — After Cloning This Template

Work through this list top-to-bottom before writing any project-specific code.

---

## 1. Environment setup

- [ ] Copy `.env.example` to `.env`
- [ ] Set `OPENAI_API_KEY` (or your LLM provider key)
- [ ] Set `DATABASE_URL` — PostgreSQL for prod, SQLite for local dev:
  - Local SQLite: `sqlite:///./chat_history.db`
  - Neon/Postgres: `postgresql://user:pass@host/db?sslmode=require`
- [ ] Set `JWT_SECRET_KEY` — must match the key used by your main backend
- [ ] Set `JWT_ALGORITHM` (default: `HS256`)
- [ ] Install dependencies: `pip install -r requirements.txt`

---

## 2. Config customization (`app/config.py`)

- [ ] Update `COLLECTION_NAME` — name your ChromaDB collection for this project (e.g. `"project_docs"`)
- [ ] Update `SYSTEM_PROMPT` — write the persona/instructions for this chatbot
- [ ] Update `LLM_MODELS` list — remove models you don't want to expose
- [ ] Update `EMBEDDING_MODELS` list — pick what's appropriate
- [ ] Set `MAX_TOKENS` appropriately for your use case

---

## 3. Database

- [ ] Confirm `DATABASE_URL` is correct
- [ ] Run the server once — `on_startup()` will create tables automatically
- [ ] If connecting to a shared DB from the main backend, confirm the `account_userauth` table exists and has `user_id`, `is_superuser`, `is_subscribed` columns
- [ ] If you don't have a `UserAuth` table (standalone project), update `is_superuser()` and the subscription check in `services/rag.py`

---

## 4. Auth

- [ ] Confirm `JWT_SECRET_KEY` matches your main backend exactly (copy-paste, no extra spaces)
- [ ] Test with a real token: run `app/a.py` (the debug decode script) with a token from your main backend
- [ ] If your token uses a different field than `user_id`, update `auth.py` → `decode_access_token()`

---

## 5. CORS

- [ ] In `main.py`, replace `allow_origins=["*"]` with your actual frontend URL before deploying

---

## 6. Rename / rebrand

- [ ] Update `FastAPI(title=..., description=...)` in `main.py` with your project name
- [ ] Update `COLLECTION_NAME` in `config.py`
- [ ] Delete `app/a.py` (it's a debug token decoder — not needed in production)

---

## 7. Project-specific additions

- [ ] Add domain-specific routes in `app/routes/`
- [ ] Add domain-specific service functions in `app/services/`
- [ ] Add any new DB tables in `app/models/` and register them in `database.py`
- [ ] Add new Pydantic schemas in `app/schemas.py`

---

## 8. Before going live

- [ ] Change `allow_origins=["*"]` to actual domain(s)
- [ ] Remove or disable all `print(f"Debug: ...")` lines (or replace with proper logging)
- [ ] Confirm API keys are NOT committed to git (`.env` is in `.gitignore`)
- [ ] Test `/health` endpoint returns `{"status": "server running"}`
- [ ] Test upload → chat flow end-to-end with a real document
