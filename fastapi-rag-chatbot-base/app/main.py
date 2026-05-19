from typing import Optional, Literal
from fastapi import FastAPI, File, Form, Depends, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

try:
    from . import schemas, database, config, auth
    from .services import document as doc_service
    from .services import rag as rag_service
    from .services import settings as settings_service
except ImportError:
    import schemas, database, config, auth
    from services import document as doc_service
    from services import rag as rag_service
    from services import settings as settings_service

# ─── App ──────────────────────────────────────────────────────────────────────

# TODO: Update title and description for your project
app = FastAPI(
    title="FastAPI RAG Chatbot",
    description="RAG-based chatbot with document ingestion and per-user conversation history.",
)

app.add_middleware(
    CORSMiddleware,
    # TODO: Replace ["*"] with your frontend domain(s) before deploying to production
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    database.on_startup()


# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "server running"}


# ─── Documents ────────────────────────────────────────────────────────────────

@app.post("/api/upload", response_model=schemas.UploadResponse)
async def upload_document(
    user_id: str = Depends(auth.get_current_user),
    file: UploadFile = File(..., description="PDF document to add to the knowledge base"),
    db: Session = Depends(database.get_db),
):
    """Upload a PDF to the knowledge base (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")

    filename = file.filename.lower()
    if not filename.endswith(".pdf"):
        return schemas.UploadResponse(message="Only PDF files are supported.", filename=file.filename, chunks_added=0)

    try:
        contents = await file.read()
        text = doc_service.extract_text_from_file(contents, file.filename)
        if not text.strip():
            return schemas.UploadResponse(message="Could not extract text from file.", filename=file.filename, chunks_added=0)

        count = doc_service.process_and_store_document(text, file.filename)
        doc_service.save_document_info(db, file.filename)
        return schemas.UploadResponse(message="Uploaded and indexed successfully.", filename=file.filename, chunks_added=count)
    except Exception as e:
        return schemas.UploadResponse(message=f"Upload failed: {e}", filename=file.filename, chunks_added=0)


@app.get("/api/documents", response_model=schemas.DocumentListResponse)
async def list_documents(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """List all uploaded documents (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")
    docs = doc_service.get_all_documents(db)
    return schemas.DocumentListResponse(
        total=len(docs),
        documents=[schemas.DocumentInfo(id=d.id, filename=d.filename, upload_timestamp=d.upload_timestamp) for d in docs],
    )


@app.delete("/api/documents")
async def delete_document(
    document_id: int,
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Delete a document by ID (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")
    filename, doc_id = doc_service.delete_document(db, document_id)
    if not filename:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": f"Document {doc_id}: '{filename}' deleted."}


@app.get("/api/documents/search", response_model=schemas.DocumentListResponse)
async def search_documents(
    query: str,
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Search documents by filename (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")
    docs = doc_service.search_documents(db, query)
    return schemas.DocumentListResponse(
        total=len(docs),
        documents=[schemas.DocumentInfo(id=d.id, filename=d.filename, upload_timestamp=d.upload_timestamp) for d in docs],
    )


# ─── Chat ─────────────────────────────────────────────────────────────────────

@app.post("/api/send", response_model=schemas.ChatResponse)
async def send_message(
    message: str = Form(..., description="User message"),
    user_id: str = Depends(auth.get_current_user),
    id: Optional[str] = Form(None, description="Conversation ID (omit to start a new conversation)"),
    db: Session = Depends(database.get_db),
):
    """Send a message and receive an AI response."""
    return rag_service.query_rag_chat(db, user_id.strip(), message, id)


# ─── History ──────────────────────────────────────────────────────────────────

@app.get("/api/history", response_model=schemas.HistoryResponse)
async def get_chat_history(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get all conversations for the current user."""
    conversations = rag_service.get_all_user_conversations(db, user_id)
    return schemas.HistoryResponse(
        conversations=[
            schemas.ConversationInfo(
                id=str(c.id),
                created_at=c.created_at,
                title=c.title or "New Chat",
                text_messages=c.messages[0].content if c.messages else None,
            )
            for c in conversations
        ]
    )


@app.get("/api/history/{id}", response_model=schemas.ConversationDetail)
async def get_conversation(
    id: str,
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get full message history for a specific conversation."""
    detail = rag_service.get_conversation_details(db, user_id, id)
    if not detail:
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return detail


@app.delete("/api/delete")
async def delete_conversation(
    conversation_id: str,
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Delete a conversation."""
    if not rag_service.delete_conversation_by_id(db, user_id, conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found.")
    return {"message": "Conversation deleted."}


# ─── Settings ─────────────────────────────────────────────────────────────────

@app.post("/api/settings/chat", response_model=schemas.SettingsResponse)
async def update_chat_settings(
    user_id: str = Depends(auth.get_current_user),
    system_prompt: str = Form(default=config.SYSTEM_PROMPT),
    llm_model_name: str = Form(default=config.LLM_MODELS[0]),
    max_tokens: int = Form(default=config.MAX_TOKENS),
    db: Session = Depends(database.get_db),
):
    """Update chatbot settings (admin only)."""
    if not rag_service.is_superuser(db, user_id.strip()):
        raise HTTPException(status_code=403, detail="Admin access required.")
    settings_service.save_chat_settings(db, schemas.ChatSettingsRequest(
        user_id=user_id.strip(),
        system_prompt=system_prompt,
        llm_model_name=llm_model_name,
        max_tokens=max_tokens,
    ))
    return {"message": "Chat settings updated."}


@app.get("/api/settings/chat", response_model=schemas.ChatSettingsRequest)
async def get_chat_settings(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get current chat settings (admin only)."""
    if not rag_service.is_superuser(db, user_id.strip()):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return settings_service.get_chat_settings_response(db, user_id.strip())


@app.post("/api/settings/api", response_model=schemas.SettingsResponse)
async def update_api_settings(
    user_id: str = Depends(auth.get_current_user),
    provider: str = Form("OpenAI"),
    llm_api_key: Optional[str] = Form(None),
    embedding_api_key: Optional[str] = Form(None),
    embedding_model_name: str = Form(default=config.EMBEDDING_MODELS[0]),
    db: Session = Depends(database.get_db),
):
    """Update API key settings (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")
    try:
        settings_service.validate_and_save_api_settings(db, schemas.APISettingsRequest(
            user_id=user_id,
            provider=provider,
            llm_api_key=llm_api_key,
            embedding_api_key=embedding_api_key,
            embedding_model_name=embedding_model_name,
        ))
        return {"message": "API settings updated."}
    except ValueError as e:
        return {"message": f"Validation error: {e}"}


@app.get("/api/settings/api", response_model=schemas.APISettingsRequest)
async def get_api_settings(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get API settings (admin only)."""
    if not rag_service.is_superuser(db, user_id):
        raise HTTPException(status_code=403, detail="Admin access required.")
    return settings_service.get_api_settings_response(db, user_id)


# ─── Analytics ────────────────────────────────────────────────────────────────

@app.get("/api/stats/response", response_model=schemas.SystemStatsResponse)
async def get_system_stats(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Get system-wide analytics (admin only)."""
    if not rag_service.is_superuser(db, user_id.strip()):
        raise HTTPException(status_code=403, detail="Admin access required.")
    avg = rag_service.get_system_average_response_time(db)
    daily = rag_service.get_daily_chat_stats(db)
    return schemas.SystemStatsResponse(average_response_time=avg, **daily)


@app.post("/api/stats/response", response_model=schemas.SystemStatsResponse)
async def recalculate_system_stats(
    user_id: str = Depends(auth.get_current_user),
    db: Session = Depends(database.get_db),
):
    """Recalculate and refresh system analytics (admin only)."""
    if not rag_service.is_superuser(db, user_id.strip()):
        raise HTTPException(status_code=403, detail="Admin access required.")
    avg = rag_service.recalculate_system_stats(db)
    daily = rag_service.get_daily_chat_stats(db)
    return schemas.SystemStatsResponse(average_response_time=avg, **daily)


# ─── Run ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8080, reload=True)
