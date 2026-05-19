# Setup Guide

## Prerequisites

- Python 3.10+
- PostgreSQL (or use SQLite for local dev)
- A main backend that issues JWT tokens with `user_id` in the payload

## Local development (SQLite)

```bash
# 1. Clone and enter
git clone <your-template-repo>
cd fastapi-rag-chatbot-base

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment
cp .env.example .env
# Edit .env with your keys

# 5. Run the server
uvicorn app.main:app --reload --port 8080

# 6. View API docs
open http://localhost:8080/docs
```

## Production (PostgreSQL)

```bash
# Same steps 1-4, but set DATABASE_URL to your PostgreSQL connection string in .env

# Run with multiple workers
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 4
```

## Docker (optional)

```bash
docker-compose up --build
```

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `OPENAI_API_KEY` | Yes | Default LLM API key (can be overridden per-user in DB) |
| `DATABASE_URL` | Yes | PostgreSQL or SQLite connection string |
| `JWT_SECRET_KEY` | Yes | Shared with your main backend |
| `JWT_ALGORITHM` | No | Default: `HS256` |

## API endpoints at a glance

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | Server health check | None |
| POST | `/api/upload` | Upload a PDF document | Admin |
| GET | `/api/documents` | List all documents | Admin |
| DELETE | `/api/documents` | Delete a document | Admin |
| GET | `/api/documents/search` | Search documents by name | Admin |
| POST | `/api/send` | Send a chat message | User |
| GET | `/api/history` | Get all user conversations | User |
| GET | `/api/history/{id}` | Get specific conversation | User |
| DELETE | `/api/delete` | Delete a conversation | User |
| POST | `/api/settings/chat` | Update chat settings | Admin |
| GET | `/api/settings/chat` | Get current chat settings | Admin |
| POST | `/api/settings/api` | Update API key settings | Admin |
| GET | `/api/settings/api` | Get API key settings | Admin |
| GET | `/api/stats/response` | Get system analytics | Admin |
| POST | `/api/stats/response` | Recalculate system analytics | Admin |
