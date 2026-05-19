from sqlalchemy import (
    create_engine, Column, Integer, String, ForeignKey,
    Text, DateTime, Boolean, BigInteger, Float, text
)
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import uuid

try:
    from .config import DATABASE_URL
except ImportError:
    from config import DATABASE_URL

# ─── Engine & Session ─────────────────────────────────────────────────────────

# SQLite (dev): needs check_same_thread=False
# PostgreSQL (prod): needs pool_pre_ping=True
if "sqlite" in DATABASE_URL:
    engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
else:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ─── Models ───────────────────────────────────────────────────────────────────

class Conversation(Base):
    __tablename__ = "conversations"
    id           = Column(String, primary_key=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id      = Column(BigInteger, index=True)
    title        = Column(String, default="New Chat")
    created_at   = Column(DateTime, default=datetime.utcnow)
    updated_at   = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages     = relationship("ChatMessage", back_populates="conversation", cascade="all, delete-orphan")


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    id              = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, ForeignKey("conversations.id"))
    role            = Column(String)        # "user" or "assistant"
    content         = Column(Text)
    timestamp       = Column(DateTime, default=datetime.utcnow)
    response_time   = Column(Float)         # seconds; None for user messages
    conversation    = relationship("Conversation", back_populates="messages")


class UploadedDocument(Base):
    __tablename__ = "uploaded_documents"
    id               = Column(Integer, primary_key=True, index=True)
    filename         = Column(String, unique=True, index=True)
    upload_timestamp = Column(DateTime, default=datetime.utcnow)


class ChatSettings(Base):
    __tablename__ = "chat_settings"
    user_id               = Column(BigInteger, primary_key=True, index=True)
    system_prompt         = Column(Text)
    llm_model_name        = Column(String)
    max_tokens            = Column(Integer)
    average_response_time = Column(Float, default=0.0)


class APISettings(Base):
    __tablename__ = "api_settings"
    user_id              = Column(BigInteger, primary_key=True, index=True)
    provider             = Column(String, default="OpenAI")
    llm_api_key          = Column(String)
    embedding_api_key    = Column(String, nullable=True)
    embedding_model_name = Column(String)


# TODO: This table is owned by the main backend — read-only from here.
# If running standalone (no main backend), remove this table and update
# is_superuser() and the subscription check in services/rag.py.
class UserAuth(Base):
    __tablename__ = "account_userauth"
    user_id       = Column(BigInteger, primary_key=True)
    is_superuser  = Column(Boolean)
    is_subscribed = Column(Boolean)


# TODO: Add project-specific tables below this line
# class YourNewTable(Base):
#     __tablename__ = "your_table"
#     ...


# ─── DB Dependency ───────────────────────────────────────────────────────────

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── Startup Migrations ──────────────────────────────────────────────────────

def on_startup():
    """Creates tables and applies any incremental column additions."""
    Base.metadata.create_all(bind=engine)

    # Skip raw SQL migrations for SQLite (it doesn't support IF NOT EXISTS ALTER)
    if "sqlite" in str(engine.url):
        return

    with engine.connect() as conn:
        migrations = [
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS title VARCHAR DEFAULT 'New Chat'",
            "ALTER TABLE conversations ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP",
            "ALTER TABLE chat_messages ADD COLUMN IF NOT EXISTS response_time FLOAT",
            "ALTER TABLE chat_settings ADD COLUMN IF NOT EXISTS average_response_time FLOAT DEFAULT 0.0",
        ]
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception as e:
                print(f"Migration skipped (already applied or error): {e}")
