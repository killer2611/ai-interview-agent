"""Phase 6 frontend integration and static asset tests."""

from __future__ import annotations

from fastapi.testclient import TestClient
from src.main import app


def test_frontend_routes_and_candidates():
    """Verify frontend static assets and candidate selection endpoint."""
    with TestClient(app) as client:
        # Test GET /api/candidates
        cand_res = client.get("/api/candidates")
        assert cand_res.status_code == 200
        cands = cand_res.json()["candidates"]
        assert len(cands) == 20
        assert cands[0]["member"]["name"] == "Sarah Johnson"

        # Test GET / (frontend index.html)
        index_res = client.get("/")
        assert index_res.status_code == 200
        assert "The Interview Agent" in index_res.text
        assert "app-container" in index_res.text

        # Test GET /static/style.css
        css_res = client.get("/static/style.css")
        assert css_res.status_code == 200
        assert "--bg-primary" in css_res.text

        # Test GET /static/app.js
        js_res = client.get("/static/app.js")
        assert js_res.status_code == 200
        assert "startInterview" in js_res.text
