from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

# ─── Chat ─────────────────────────────────────────────────────────────────────

class Message(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    message: str
    user_id: str
    id: Optional[str] = None          # conversation_id (None = start new)

class ChatResponse(BaseModel):
    reply: str
    ts: str
    id: Optional[str] = None          # conversation_id

# ─── History ──────────────────────────────────────────────────────────────────

class ConversationInfo(BaseModel):
    id: str
    created_at: datetime
    title: str
    text_messages: Optional[str] = None   # preview of first message

class HistoryResponse(BaseModel):
    conversations: List[ConversationInfo]

class ConversationDetail(BaseModel):
    id: str
    title: str
    created_at: datetime
    messages: List[Message]

# ─── Documents ────────────────────────────────────────────────────────────────

class UploadResponse(BaseModel):
    message: str
    filename: str
    chunks_added: int

class DocumentInfo(BaseModel):
    id: int
    filename: str
    upload_timestamp: datetime

class DocumentListResponse(BaseModel):
    total: int
    documents: List[DocumentInfo]

# ─── Settings ─────────────────────────────────────────────────────────────────

class ChatSettingsRequest(BaseModel):
    user_id: str
    system_prompt: str
    llm_model_name: str
    max_tokens: int

class APISettingsRequest(BaseModel):
    user_id: str
    provider: str = "OpenAI"
    llm_api_key: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_model_name: str

class SettingsResponse(BaseModel):
    message: str

class ConfigOptionsResponse(BaseModel):
    llm_models: List[str]
    embedding_models: List[str]

# ─── Analytics ────────────────────────────────────────────────────────────────

class UserStatsResponse(BaseModel):
    user_id: str
    average_response_time: float

class SystemStatsResponse(BaseModel):
    average_response_time: float
    today_count: int
    percent_change: str
    trend: str
