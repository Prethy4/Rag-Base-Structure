"""
RAG chat service.
Handles: conversation management, history retrieval, question condensation,
         LLM call with context injection, response storage, title generation.
"""
import time
import openai
from typing import List, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func, cast, Date
from datetime import datetime, timedelta

try:
    from ..config import OPENAI_API_KEY, LLM_MODELS, MAX_TOKENS, SYSTEM_PROMPT, EMBEDDING_MODELS
    from .. import database, schemas
    from .document import retrieve_relevant_chunks, get_embedding_model
except ImportError:
    from config import OPENAI_API_KEY, LLM_MODELS, MAX_TOKENS, SYSTEM_PROMPT, EMBEDDING_MODELS
    import database, schemas
    from services.document import retrieve_relevant_chunks, get_embedding_model


# ─── OpenAI client ───────────────────────────────────────────────────────────

def get_openai_client(api_key: Optional[str] = None) -> Optional[openai.OpenAI]:
    key = api_key or OPENAI_API_KEY
    if not key:
        return None
    return openai.OpenAI(api_key=key)


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def is_superuser(db: Session, user_id: str) -> bool:
    """
    Checks if user_id belongs to a superuser.

    TODO: If running standalone (no main backend / no UserAuth table),
    replace this with your own admin check logic, e.g.:
        return user_id in ADMIN_USER_IDS
    """
    if not str(user_id).isdigit():
        return False
    user = db.query(database.UserAuth).filter_by(user_id=user_id).first()
    return bool(user and user.is_superuser)


def is_subscribed(db: Session, user_id: str) -> bool:
    """
    Checks if user has an active subscription.

    TODO: If running standalone, remove this check or replace with your own logic.
    """
    user = db.query(database.UserAuth).filter_by(user_id=user_id).first()
    return bool(user and (user.is_subscribed or user.is_superuser))


# ─── Settings helpers ─────────────────────────────────────────────────────────

def get_effective_chat_settings(db: Session, user_id: str) -> dict:
    """Returns per-user settings or global defaults."""
    settings = db.query(database.ChatSettings).filter_by(user_id=user_id).first()
    if settings:
        return {
            "system_prompt": settings.system_prompt,
            "llm_model_name": settings.llm_model_name,
            "max_tokens": settings.max_tokens,
        }
    return {
        "system_prompt": SYSTEM_PROMPT,
        "llm_model_name": LLM_MODELS[0],
        "max_tokens": MAX_TOKENS,
    }


def get_effective_api_settings(db: Session, user_id: str):
    """Returns per-user API settings or env-based defaults."""
    settings = db.query(database.APISettings).filter_by(user_id=user_id).first()
    if settings and settings.llm_api_key:
        return settings

    class _Defaults:
        provider = "OpenAI"
        llm_api_key = OPENAI_API_KEY
        embedding_api_key = None
        embedding_model_name = EMBEDDING_MODELS[0]

    return _Defaults()


# ─── Conversation helpers ─────────────────────────────────────────────────────

def get_conversation_history(db: Session, conversation_id: str) -> List[Dict[str, str]]:
    messages = (
        db.query(database.ChatMessage)
        .filter_by(conversation_id=str(conversation_id))
        .order_by(database.ChatMessage.timestamp)
        .all()
    )
    return [{"role": m.role, "content": m.content} for m in messages]


def add_chat_message(
    db: Session,
    conversation_id: str,
    role: str,
    content: str,
    response_time: Optional[float] = None,
):
    """Persists a single message and updates the user's average response time."""
    msg = database.ChatMessage(
        conversation_id=str(conversation_id),
        role=role,
        content=content,
        response_time=response_time,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    # Update cached average response time for this user
    if role == "assistant" and response_time is not None:
        conv = db.query(database.Conversation).filter_by(id=str(conversation_id)).first()
        if conv:
            avg = (
                db.query(func.avg(database.ChatMessage.response_time))
                .join(database.Conversation, database.Conversation.id == database.ChatMessage.conversation_id)
                .filter(database.Conversation.user_id == conv.user_id)
                .filter(database.ChatMessage.role == "assistant")
                .scalar()
            ) or 0.0
            s = db.query(database.ChatSettings).filter_by(user_id=conv.user_id).first()
            if s:
                s.average_response_time = avg
                db.commit()


# ─── Question condensation ────────────────────────────────────────────────────

def _is_greeting(query: str) -> bool:
    normalized = "".join(c for c in query.lower() if c.isalnum() or c.isspace()).strip()
    return normalized in {"hello", "hi", "hey"}


def condense_question(client: openai.OpenAI, history: List[Dict[str, str]], query: str) -> str:
    """
    Rewrites a follow-up question into a standalone question using recent history.
    Skips condensation for greetings or when there's no history.
    """
    if not history or _is_greeting(query):
        return query

    history_str = "\n".join(f"{m['role']}: {m['content']}" for m in history[-4:])
    prompt = (
        "Given the conversation below and a follow-up question, rewrite the follow-up "
        "as a standalone question that can be understood without the conversation. "
        "If it's already standalone, return it unchanged.\n\n"
        f"Conversation:\n{history_str}\n\nFollow-up: {query}\n\nStandalone question:"
    )
    try:
        completion = client.chat.completions.create(
            model=LLM_MODELS[-1],   # use cheapest/fastest model for this step
            messages=[{"role": "system", "content": prompt}],
            temperature=0.0,
        )
        return completion.choices[0].message.content.strip().strip('"')
    except Exception as e:
        print(f"Condensation error (using original): {e}")
        return query


# ─── Title generation ─────────────────────────────────────────────────────────

def generate_title(db: Session, client: openai.OpenAI, conversation_id: str, first_query: str):
    """Generates a 4-5 word title for a new conversation based on the first user query."""
    conv = db.query(database.Conversation).filter_by(id=str(conversation_id)).first()
    if not conv or conv.title != "New Chat":
        return
    if _is_greeting(first_query):
        return

    try:
        prompt = (
            f"Summarize this user query into a 4-5 word title. "
            f"Return only the title, no quotes, no punctuation.\n\nQuery: {first_query}"
        )
        completion = client.chat.completions.create(
            model=LLM_MODELS[-1],
            messages=[{"role": "system", "content": prompt}],
            temperature=0.5,
        )
        title = completion.choices[0].message.content.strip().replace('"', "")
        if title:
            conv.title = title
            db.commit()
    except Exception as e:
        print(f"Title generation error: {e}")
        words = first_query.split()[:5]
        if words and conv:
            conv.title = " ".join(words)
            db.commit()


# ─── Main RAG chat function ───────────────────────────────────────────────────

def query_rag_chat(
    db: Session,
    user_id: str,
    query: str,
    conversation_id: Optional[str] = None,
) -> "schemas.ChatResponse":
    """
    Full RAG chat pipeline:
      1. Validate user (auth + subscription)
      2. Resolve or create conversation
      3. Condense follow-up into standalone question
      4. Retrieve relevant doc chunks from ChromaDB
      5. Build system prompt with history + context
      6. Call LLM
      7. Persist messages + generate title
    """
    ts_now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not str(user_id).isdigit():
        return schemas.ChatResponse(reply="Invalid user ID.", ts=ts_now, id=conversation_id)

    # Normalize empty/null conversation_id
    if conversation_id and conversation_id.strip() in ("", "null"):
        conversation_id = None

    # Subscription gate — TODO: remove if standalone
    if not is_subscribed(db, user_id):
        return schemas.ChatResponse(
            reply="Access restricted. Please subscribe to use this feature.",
            ts=ts_now,
            id=conversation_id,
        )

    # API settings
    api_settings = get_effective_api_settings(db, user_id)
    client = get_openai_client(api_settings.llm_api_key)
    if not client:
        return schemas.ChatResponse(reply="LLM API key not configured.", ts=ts_now, id=conversation_id)

    # Resolve conversation
    if not conversation_id:
        conv = database.Conversation(user_id=user_id, title="New Chat")
        db.add(conv)
        db.commit()
        db.refresh(conv)
        conversation_id = conv.id
        raw_history = []
    else:
        conv = db.query(database.Conversation).filter_by(
            id=str(conversation_id), user_id=user_id
        ).first()
        if not conv:
            return schemas.ChatResponse(reply="Conversation not found.", ts=ts_now, id=conversation_id)
        raw_history = get_conversation_history(db, conversation_id)

    # Condense follow-up → standalone question for retrieval
    standalone_query = condense_question(client, raw_history, query)

    # Retrieve relevant context chunks
    try:
        chunks = retrieve_relevant_chunks(
            standalone_query,
            n_results=3,
            embedding_model_name=api_settings.embedding_model_name,
        )
    except Exception as e:
        print(f"Embedding error: {e}")
        return schemas.ChatResponse(reply="Error processing your query.", ts=ts_now, id=conversation_id)

    context_str = "\n".join(chunks) if chunks else "No relevant documents found."

    # Build system prompt
    chat_settings = get_effective_chat_settings(db, user_id)
    base_prompt = chat_settings["system_prompt"]

    history_summary = "No previous context."
    if len(raw_history) > 1:
        past = raw_history[:-1][-5:]
        history_summary = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in past)

    # TODO: Customize how context is injected into the system prompt
    system_prompt = (
        f"{base_prompt}\n\n"
        f"--- PREVIOUS CONVERSATION ---\n{history_summary}\n\n"
        f"--- RETRIEVED KNOWLEDGE ---\n{context_str}\n\n"
        f"--- INSTRUCTION ---\n"
        f"Answer the user's question using the retrieved knowledge when relevant. "
        f"For follow-up questions about the conversation, use the previous conversation section."
    )

    # Save user message
    add_chat_message(db, conversation_id, "user", query)

    # Call LLM
    messages = [{"role": "system", "content": system_prompt}]
    messages.extend(get_conversation_history(db, conversation_id))

    try:
        start = time.time()
        completion = client.chat.completions.create(
            model=chat_settings["llm_model_name"],
            messages=messages,
            max_tokens=chat_settings["max_tokens"],
        )
        elapsed = time.time() - start
        reply = completion.choices[0].message.content

        add_chat_message(db, conversation_id, "assistant", reply, response_time=elapsed)
        generate_title(db, client, conversation_id, query)

        return schemas.ChatResponse(reply=reply, ts=ts_now, id=conversation_id)

    except Exception as e:
        err = str(e).lower()
        if "quota" in err or "429" in err:
            msg = "API quota exceeded. Please try again later."
        elif "api_key" in err or "invalid" in err:
            msg = "LLM API key issue. Please check your configuration."
        elif "rate_limit" in err:
            msg = "Too many requests. Please wait and try again."
        elif "timeout" in err:
            msg = "Request timed out. Please try again."
        else:
            msg = "An error occurred. Please try again."
        print(f"LLM error: {e}")
        add_chat_message(db, conversation_id, "assistant", msg)
        return schemas.ChatResponse(reply=msg, ts=ts_now, id=conversation_id)


# ─── History helpers ──────────────────────────────────────────────────────────

def get_all_user_conversations(db: Session, user_id: str):
    return (
        db.query(database.Conversation)
        .filter_by(user_id=user_id)
        .order_by(database.Conversation.created_at.desc())
        .all()
    )


def get_conversation_details(db: Session, user_id: str, conversation_id: str):
    conv = db.query(database.Conversation).filter_by(
        id=str(conversation_id), user_id=user_id
    ).first()
    if not conv:
        return None
    return {
        "id": str(conv.id),
        "title": conv.title or "New Chat",
        "created_at": conv.created_at,
        "messages": get_conversation_history(db, conversation_id),
    }


def delete_conversation_by_id(db: Session, user_id: str, conversation_id: str) -> bool:
    conv = db.query(database.Conversation).filter_by(
        id=str(conversation_id), user_id=user_id
    ).first()
    if not conv:
        return False
    db.delete(conv)
    db.commit()
    return True


# ─── Analytics ───────────────────────────────────────────────────────────────

def get_system_average_response_time(db: Session) -> float:
    result = (
        db.query(func.avg(database.ChatSettings.average_response_time))
        .filter(database.ChatSettings.average_response_time > 0)
        .scalar()
    )
    return round(result, 2) if result else 0.0


def recalculate_system_stats(db: Session) -> float:
    """Recalculates and caches per-user average response times."""
    rows = (
        db.query(
            database.Conversation.user_id,
            func.avg(database.ChatMessage.response_time).label("avg"),
        )
        .join(database.ChatMessage, database.Conversation.id == database.ChatMessage.conversation_id)
        .filter(database.ChatMessage.role == "assistant")
        .filter(database.ChatMessage.response_time.isnot(None))
        .group_by(database.Conversation.user_id)
        .all()
    )
    for uid, avg in rows:
        s = db.query(database.ChatSettings).filter_by(user_id=uid).first()
        if s:
            s.average_response_time = avg
        else:
            s = database.ChatSettings(
                user_id=uid,
                system_prompt=SYSTEM_PROMPT,
                llm_model_name=LLM_MODELS[0],
                max_tokens=MAX_TOKENS,
                average_response_time=avg,
            )
            db.add(s)
    db.commit()
    return get_system_average_response_time(db)


def get_daily_chat_stats(db: Session) -> dict:
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)

    today_count = db.query(database.ChatMessage).filter(
        cast(database.ChatMessage.timestamp, Date) == today
    ).count()
    yesterday_count = db.query(database.ChatMessage).filter(
        cast(database.ChatMessage.timestamp, Date) == yesterday
    ).count()

    if yesterday_count > 0:
        pct = max(0.0, min((today_count / yesterday_count) * 100, 100.0))
    else:
        pct = 0.0

    trend = "⬆" if today_count > yesterday_count else ("⬇" if today_count < yesterday_count else "-")
    return {"today_count": today_count, "percent_change": f"{int(pct)}%", "trend": trend}
