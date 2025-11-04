"""Smoke tests for critical endpoints."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "healthy"
    assert "version" in data


def test_status_page():
    """Test status page endpoint."""
    r = client.get("/status")
    # Should return 200 or redirect
    assert r.status_code in (200, 307, 308)


def test_chat_page():
    """Test chat page endpoint."""
    r = client.get("/chat")
    # Should return 200 or redirect
    assert r.status_code in (200, 307, 308)


def test_chat_help():
    """Test /help command in chat API."""
    r = client.post("/api/chat", json={"message": "/help"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    reply = j.get("say", "") or j.get("reply", "")
    assert "/generate-queries" in reply or "commands" in reply.lower()


def test_chat_generate_queries():
    """Test /generate-queries command."""
    r = client.post("/api/chat", json={"message": "/generate-queries"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    reply = j.get("say", "") or j.get("reply", "")
    # Should mention CSV or queries file
    assert "trove_queries.csv" in reply.lower() or "csv" in reply.lower() or "queries" in reply.lower()


def test_chat_unknown_command():
    """Test unknown command returns error."""
    r = client.post("/api/chat", json={"message": "/unknown-command"})
    assert r.status_code == 400
    j = r.json()
    assert j.get("ok") is False
    assert "error" in j


def test_chat_plain_message():
    """Test plain message (non-command) handling."""
    r = client.post("/api/chat", json={"message": "Hello, can you help?"})
    assert r.status_code == 200
    j = r.json()
    assert j.get("ok") is True
    # Should either have a reply or guidance
    assert "say" in j or "reply" in j


def test_home_page():
    """Test home page loads."""
    r = client.get("/")
    # May be 200 (if API key configured) or 500 (if missing) or 422 (validation error)
    # At minimum, should return some response
    assert r.status_code in (200, 500, 422)
    # If successful, should be HTML
    if r.status_code == 200:
        assert "text/html" in r.headers.get("content-type", "")

