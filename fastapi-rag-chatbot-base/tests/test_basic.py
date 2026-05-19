"""
Basic smoke tests for the RAG chatbot base template.
Run with: pytest tests/
"""
from fastapi.testclient import TestClient

# Adjust import path as needed
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.main import app

client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "server running"}


def test_send_requires_auth():
    response = client.post("/api/send", data={"message": "hello"})
    assert response.status_code == 401


def test_history_requires_auth():
    response = client.get("/api/history")
    assert response.status_code == 401


def test_upload_requires_auth():
    response = client.post("/api/upload")
    assert response.status_code == 401


# TODO: Add integration tests with a real (test) DB and mocked OpenAI client
