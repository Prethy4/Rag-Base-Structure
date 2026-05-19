"""
Document ingestion service.
Handles: file parsing → text chunking → embedding → ChromaDB storage → SQL metadata.
"""
import io
import chromadb
from sentence_transformers import SentenceTransformer
from langchain_text_splitters import RecursiveCharacterTextSplitter
from pypdf import PdfReader
from datetime import datetime
from sqlalchemy.orm import Session
from typing import Optional

try:
    from ..config import CHROMA_DB_DIR, COLLECTION_NAME, EMBEDDING_MODELS
    from .. import database
except ImportError:
    from config import CHROMA_DB_DIR, COLLECTION_NAME, EMBEDDING_MODELS
    import database

# ─── ChromaDB client (initialized once) ──────────────────────────────────────
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)

# ─── Embedding model cache ────────────────────────────────────────────────────
_embedding_cache: dict = {}


def get_embedding_model(model_name: str) -> SentenceTransformer:
    """Loads and caches a SentenceTransformer model by name."""
    if model_name not in _embedding_cache:
        _embedding_cache[model_name] = SentenceTransformer(model_name)
    return _embedding_cache[model_name]


# Pre-load the default model at startup
get_embedding_model(EMBEDDING_MODELS[0])


# ─── Text extraction ──────────────────────────────────────────────────────────

def extract_text_from_file(file_contents: bytes, filename: str) -> str:
    """
    Extracts raw text from an uploaded file.

    Supported: .pdf
    TODO: Add .docx and .txt support as needed for your project.
    """
    ext = filename.rsplit(".", 1)[-1].lower()

    try:
        if ext == "pdf":
            reader = PdfReader(io.BytesIO(file_contents))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n".join(pages)

        # TODO: Uncomment to add DOCX support
        # elif ext == "docx":
        #     from docx import Document
        #     doc = Document(io.BytesIO(file_contents))
        #     return "\n".join(p.text for p in doc.paragraphs)

        # TODO: Uncomment to add plain text support
        # elif ext == "txt":
        #     return file_contents.decode("utf-8", errors="ignore")

        else:
            raise ValueError(f"Unsupported file type: .{ext}")

    except Exception as e:
        print(f"Error extracting text from {filename}: {e}")
        return ""


# ─── Chunking & storage ───────────────────────────────────────────────────────

def process_and_store_document(text: str, filename: str, embedding_model_name: Optional[str] = None) -> int:
    """
    Splits text into chunks, embeds them, and stores in ChromaDB.
    Deletes any existing chunks for the same filename before inserting.

    Returns the number of chunks stored.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )
    chunks = splitter.split_text(text)
    if not chunks:
        return 0

    model_name = embedding_model_name or EMBEDDING_MODELS[0]
    model = get_embedding_model(model_name)
    embeddings = model.encode(chunks).tolist()

    ids = [f"{filename}_{i}" for i in range(len(chunks))]
    metadatas = [{"source": filename, "chunk_index": i} for i in range(len(chunks))]

    # Replace existing chunks for this filename
    try:
        collection.delete(where={"source": filename})
    except Exception:
        pass

    collection.add(documents=chunks, embeddings=embeddings, metadatas=metadatas, ids=ids)
    print(f"Stored {len(chunks)} chunks for {filename}")
    return len(chunks)


def retrieve_relevant_chunks(query: str, n_results: int = 3, embedding_model_name: Optional[str] = None) -> list[str]:
    """Embeds the query and returns the top-n most relevant document chunks."""
    model_name = embedding_model_name or EMBEDDING_MODELS[0]
    model = get_embedding_model(model_name)
    query_embedding = model.encode([query]).tolist()
    results = collection.query(query_embeddings=query_embedding, n_results=n_results)
    return results["documents"][0] if results["documents"] else []


# ─── SQL metadata ─────────────────────────────────────────────────────────────

def save_document_info(db: Session, filename: str) -> database.UploadedDocument:
    """Upserts document metadata in SQL (for listing/search)."""
    doc = db.query(database.UploadedDocument).filter_by(filename=filename).first()
    if not doc:
        doc = database.UploadedDocument(filename=filename)
        db.add(doc)
    else:
        doc.upload_timestamp = datetime.utcnow()
    db.commit()
    db.refresh(doc)
    return doc


def get_all_documents(db: Session):
    return db.query(database.UploadedDocument).order_by(
        database.UploadedDocument.upload_timestamp.desc()
    ).all()


def search_documents(db: Session, query: str):
    return db.query(database.UploadedDocument).filter(
        database.UploadedDocument.filename.ilike(f"%{query}%")
    ).all()


def delete_document(db: Session, document_id: int):
    """Deletes document from SQL and removes its chunks from ChromaDB."""
    doc = db.query(database.UploadedDocument).filter_by(id=document_id).first()
    if not doc:
        return None, None

    filename = doc.filename
    try:
        collection.delete(where={"source": filename})
    except Exception as e:
        print(f"Error deleting from ChromaDB: {e}")

    db.delete(doc)
    db.commit()
    return filename, document_id
