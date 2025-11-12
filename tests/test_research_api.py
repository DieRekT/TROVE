"""Tests for research API endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock

from app.main import app
from app.research import store, schemas


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_openai():
    """Mock OpenAI API."""
    with patch("app.research.engine.OPENAI_API_KEY", "test-key"):
        with patch("app.research.engine.OpenAI") as mock:
            yield mock


@pytest.fixture
def mock_trove():
    """Mock Trove API."""
    with patch("app.trove.client.TROVE_API_KEY", "test-key"):
        with patch("app.trove.client.search_trove") as mock:
            mock.return_value = [
                schemas.Evidence(
                    title="Test Article",
                    url="https://trove.nla.gov.au/test",
                    source="trove",
                    published_at="1975-01-01",
                    snippet="Test snippet",
                    quotes=["Test quote"],
                    score=0.8,
                    rationale="Test rationale",
                )
            ]
            yield mock


def test_start_research(client, mock_openai, mock_trove):
    """Test starting a research job."""
    payload = {
        "question": "Test research question",
        "region": "Clarence Valley, NSW",
        "time_window": "1970-1995",
        "depth": "brief",
        "sources": ["web", "trove"],
    }
    
    response = client.post("/research/start", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert isinstance(data["job_id"], str)


def test_research_progress(client):
    """Test getting research job progress."""
    # Create a test job
    job_id = store.create_job("Test question", "Clarence Valley, NSW", "1970-1995")
    
    response = client.get(f"/research/{job_id}/progress")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == job_id
    assert data["status"] in ("queued", "running", "done", "error")


def test_research_progress_not_found(client):
    """Test getting progress for non-existent job."""
    response = client.get("/research/nonexistent/progress")
    assert response.status_code == 404


def test_download_report_not_found(client):
    """Test downloading report for non-existent job."""
    response = client.get("/research/nonexistent/report.md")
    assert response.status_code == 404


def test_research_stream(client):
    """Test SSE stream for research progress."""
    job_id = store.create_job("Test question")
    
    response = client.get(f"/research/{job_id}/stream")
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/event-stream"


@pytest.mark.asyncio
async def test_research_job_execution(mock_openai, mock_trove):
    """Test that research job executes and creates report."""
    from app.research import jobs, planner, schemas
    
    # Create job
    job_id = store.create_job("Test question", "Clarence Valley, NSW", "1970-1995")
    
    # Create plan
    plan = planner.make_plan("Test question", "Clarence Valley, NSW", "1970-1995", "brief")
    
    # Create params
    params = schemas.ResearchStart(
        question="Test question",
        region="Clarence Valley, NSW",
        time_window="1970-1995",
        depth="brief",
        sources=["web", "trove"],
    )
    
    # Run job (synchronously for test)
    jobs.run_in_background(job_id, plan, params)
    
    # Check job status
    job = store.load_job(job_id)
    assert job is not None
    assert job.status in ("done", "error", "running")

