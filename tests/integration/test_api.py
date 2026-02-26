"""Integration tests for API endpoints.

These tests use the FastAPI test client and mock the database.
"""

import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_endpoint(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@patch("backend.api.router.SessionLocal")
def test_reference_year_levels(mock_session_cls, client):
    """Test year levels endpoint returns data."""
    from backend.db.models import YearLevel

    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [
        MagicMock(code="MATMATY5", title="Year 5", band="primary"),
    ]

    with patch("backend.api.router.get_db", return_value=iter([mock_db])):
        response = client.get("/api/reference/year-levels")
    assert response.status_code == 200


@patch("backend.api.router.SessionLocal")
def test_reference_strands(mock_session_cls, client):
    """Test strands endpoint returns data."""
    mock_db = MagicMock()
    mock_query = MagicMock()
    mock_db.query.return_value = mock_query
    mock_query.order_by.return_value = mock_query
    mock_query.all.return_value = [
        MagicMock(code="NUM", title="Number"),
    ]

    with patch("backend.api.router.get_db", return_value=iter([mock_db])):
        response = client.get("/api/reference/strands")
    assert response.status_code == 200


def test_debug_endpoint_not_found(client):
    """Test debug endpoint returns 404 for missing generation."""
    with patch("backend.api.router.get_db") as mock_get_db:
        mock_db = MagicMock()
        mock_db.query.return_value.filter_by.return_value.first.return_value = None
        mock_get_db.return_value = iter([mock_db])
        response = client.get("/api/debug/nonexistent-id")
    assert response.status_code == 404


def test_generate_endpoint_accepts_form_data(client):
    """Test that the generate endpoint accepts form data (SSE response)."""
    with patch("backend.api.router._run_generation") as mock_gen:
        async def mock_events(params):
            yield '{"type": "generation_started", "generation_id": "test-123"}'
            yield '{"type": "generation_completed", "generation_id": "test-123", "total_duration_ms": 100}'

        mock_gen.return_value = mock_events({})

        response = client.post(
            "/api/generate",
            data={
                "topic": "fractions",
                "year_level": "Year 5",
                "strand": "Number",
                "teaching_focus": "explicit_instruction",
                "resource_type": "worked_example_study",
            },
        )
        assert response.status_code == 200
        assert "text/event-stream" in response.headers.get("content-type", "")
