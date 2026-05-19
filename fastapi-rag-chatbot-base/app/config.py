import os
from dotenv import load_dotenv

# ─── Load environment ────────────────────────────────────────────────────────
load_dotenv()

# ─── LLM & Embedding ─────────────────────────────────────────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Add or remove models as needed for your project
LLM_MODELS = [
    "gpt-4o-mini",   # default (fast, cheap)
    "gpt-4o",
    "gpt-4.1",
    "gpt-4.1-mini",
]

EMBEDDING_MODELS = [
    "all-MiniLM-L6-v2",          # default (local, free)
    "text-embedding-3-small",    # OpenAI (better quality, costs $)
    "text-embedding-3-large",
]

MAX_TOKENS = 1000

# ─── Vector DB ───────────────────────────────────────────────────────────────
CHROMA_DB_DIR = "chroma_db"

# TODO: Rename this to something meaningful for your project
COLLECTION_NAME = "project_docs"

# ─── SQL Database ────────────────────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./chat_history.db")

# ─── Auth ────────────────────────────────────────────────────────────────────
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

# ─── System Prompt ───────────────────────────────────────────────────────────
# TODO: Customize this for your project's persona and domain
SYSTEM_PROMPT = (
    "You are a helpful AI assistant.\n"
    "Answer questions clearly and concisely based on the provided context.\n"
    "If a question is outside the provided context and your knowledge, say so honestly.\n"
    "Do not fabricate information.\n"
)
