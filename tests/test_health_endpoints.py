"""
Tests for the health-check endpoints defined in backend/main.py.

Covers:
  - GET  /        → 200 {"status": "ok"}
  - HEAD /        → 200, empty body
  - GET  /health  → 200 {"status": "ok"}
  - HEAD /health  → 200, empty body
"""

from __future__ import annotations

import sys
import os

_REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client():
    """Return a TestClient for the FastAPI app."""
    os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")
    os.environ.setdefault("WEBAPP_URL", "http://localhost")
    os.environ.setdefault("GOOGLE_SERVICE_ACCOUNT_JSON", "{}")
    os.environ.setdefault("GOOGLE_SHEETS_SPREADSHEET_ID", "test")

    from backend.main import app
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


class TestGetRoot:
    def test_status_200(self, client):
        response = client.get("/")
        assert response.status_code == 200

    def test_body_is_status_ok(self, client):
        response = client.get("/")
        assert response.json() == {"status": "ok"}


class TestHeadRoot:
    def test_status_200(self, client):
        response = client.head("/")
        assert response.status_code == 200

    def test_body_is_empty(self, client):
        response = client.head("/")
        assert response.content == b""


class TestGetHealth:
    def test_status_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_body_is_status_ok(self, client):
        response = client.get("/health")
        assert response.json() == {"status": "ok"}


class TestHeadHealth:
    def test_status_200(self, client):
        response = client.head("/health")
        assert response.status_code == 200

    def test_body_is_empty(self, client):
        response = client.head("/health")
        assert response.content == b""
