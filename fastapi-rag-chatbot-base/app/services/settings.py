"""
Settings service.
Handles: saving/retrieving chat settings and API key settings per user.
"""
import openai
from sqlalchemy.orm import Session

try:
    from ..config import SYSTEM_PROMPT, LLM_MODELS, MAX_TOKENS, EMBEDDING_MODELS, OPENAI_API_KEY
    from .. import database, schemas
except ImportError:
    from config import SYSTEM_PROMPT, LLM_MODELS, MAX_TOKENS, EMBEDDING_MODELS, OPENAI_API_KEY
    import database, schemas


def save_chat_settings(db: Session, settings: "schemas.ChatSettingsRequest") -> database.ChatSettings:
    s = db.query(database.ChatSettings).filter_by(user_id=settings.user_id).first()
    if not s:
        s = database.ChatSettings(
            user_id=settings.user_id,
            system_prompt=settings.system_prompt,
            llm_model_name=settings.llm_model_name,
            max_tokens=settings.max_tokens,
        )
        db.add(s)
    else:
        s.system_prompt = settings.system_prompt
        s.llm_model_name = settings.llm_model_name
        s.max_tokens = settings.max_tokens
    db.commit()
    db.refresh(s)
    return s


def get_chat_settings_response(db: Session, user_id: str) -> "schemas.ChatSettingsRequest":
    from .rag import get_effective_chat_settings
    settings = get_effective_chat_settings(db, user_id)
    return schemas.ChatSettingsRequest(user_id=user_id, **settings)


def validate_and_save_api_settings(db: Session, settings: "schemas.APISettingsRequest") -> database.APISettings:
    """Validates the LLM API key before saving."""
    if settings.llm_api_key:
        try:
            client = openai.OpenAI(api_key=settings.llm_api_key)
            client.models.list()
        except Exception as e:
            raise ValueError(f"Invalid LLM API key: {e}")

    s = db.query(database.APISettings).filter_by(user_id=settings.user_id).first()
    if not s:
        s = database.APISettings(
            user_id=settings.user_id,
            provider=settings.provider,
            llm_api_key=settings.llm_api_key,
            embedding_api_key=settings.embedding_api_key,
            embedding_model_name=settings.embedding_model_name,
        )
        db.add(s)
    else:
        s.provider = settings.provider
        s.llm_api_key = settings.llm_api_key
        s.embedding_api_key = settings.embedding_api_key
        s.embedding_model_name = settings.embedding_model_name
    db.commit()
    db.refresh(s)
    return s


def get_api_settings_response(db: Session, user_id: str) -> "schemas.APISettingsRequest":
    from .rag import get_effective_api_settings
    s = get_effective_api_settings(db, user_id)
    return schemas.APISettingsRequest(
        user_id=user_id,
        provider=s.provider,
        llm_api_key=s.llm_api_key or "",
        embedding_api_key=s.embedding_api_key,
        embedding_model_name=s.embedding_model_name,
    )
