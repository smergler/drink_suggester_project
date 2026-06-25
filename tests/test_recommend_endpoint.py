"""Tests for POST /recommend endpoint (mocked DB + LLM)."""

from __future__ import annotations

import contextlib
import os
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from backend.auth import get_current_user
from recommender.schemas import Ingredient, IngredientSource, Recommendation, Suggestion

client = TestClient(app, raise_server_exceptions=False)
AUTH_HEADER = {"Authorization": "Bearer fake-jwt"}

MOCK_SUGGESTION = Suggestion(
    name="Boulevardier",
    description="A bourbon-based Negroni variant.",
    ingredients=[
        Ingredient(name="Four Roses Bourbon", quantity="1.5 oz", source=IngredientSource.inventory),
    ],
    steps=["Stir with ice", "Strain into coupe"],
    why="Spirit-forward and warming.",
)
MOCK_RESULT = Recommendation(suggestions=[MOCK_SUGGESTION])

BOTTLE = {
    "id": "bot1", "name": "Four Roses Bourbon", "category": "bourbon",
    "subcategory": None, "is_active": True,
    "created_at": "2026-01-01T00:00:00+00:00", "updated_at": "2026-01-01T00:00:00+00:00",
}
SESSION = {"id": "s1", "occasion": "movie night", "mood": None,
           "session_companions": [], "created_at": "2026-01-01T00:00:00+00:00", "ended_at": None}


@contextlib.contextmanager
def _mocked(bottles=None, active_session=None):
    """Override auth and DB for recommend endpoint tests."""
    mock_db = MagicMock()
    mock_db.list_bottles.return_value = bottles if bottles is not None else [BOTTLE]
    mock_db.get_active_session.return_value = active_session
    mock_db.create_session.return_value = SESSION
    mock_db.create_session_drinks.return_value = []

    app.dependency_overrides[get_current_user] = lambda: "user-1"
    with patch("app.main.DB", return_value=mock_db), \
         patch("app.main.recommend", return_value=MOCK_RESULT), \
         patch.dict(os.environ, {"ANTHROPIC_API_KEY": "fake-key-for-tests"}):
        try:
            yield mock_db
        finally:
            app.dependency_overrides.clear()


def test_recommend_requires_auth():
    resp = client.post("/recommend", json={"occasion": "movie night"})
    assert resp.status_code in (401, 403)


def test_recommend_empty_inventory_returns_400():
    with _mocked(bottles=[]):
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 400


def test_recommend_creates_session_when_none_active():
    with _mocked(active_session=None) as db:
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.create_session.assert_called_once_with(
        occasion="movie night", mood=None, companion_ids=[]
    )


def test_recommend_reuses_active_session():
    with _mocked(active_session=SESSION) as db:
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.create_session.assert_not_called()


def test_recommend_returns_session_id_header():
    with _mocked(active_session=None):
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.headers.get("x-session-id") == "s1"


def test_recommend_saves_drinks_to_session():
    with _mocked(active_session=None) as db:
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.create_session_drinks.assert_called_once()
    session_id_arg, drinks_arg = db.create_session_drinks.call_args.args
    assert session_id_arg == "s1"
    assert drinks_arg[0]["name"] == "Boulevardier"
    assert "suited_for" in drinks_arg[0]
    assert drinks_arg[0]["suited_for"] == []


def test_recommend_writes_telemetry_when_usage_present():
    """When llm.last_usage is set, update_session_telemetry is called."""
    from recommender.llm import UsageStats
    mock_llm = MagicMock()
    mock_llm.last_usage = UsageStats(input_tokens=500, output_tokens=200)

    with _mocked(active_session=None) as db, \
         patch("app.main.AnthropicClient", return_value=mock_llm):
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.update_session_telemetry.assert_called_once()
    kwargs = db.update_session_telemetry.call_args.kwargs
    assert kwargs["input_tokens"] == 500
    assert kwargs["output_tokens"] == 200


def test_recommend_telemetry_failure_is_nonfatal():
    """If update_session_telemetry raises, the 200 response still returns."""
    from recommender.llm import UsageStats
    mock_llm = MagicMock()
    mock_llm.last_usage = UsageStats(input_tokens=100, output_tokens=50)

    with _mocked(active_session=None) as db, \
         patch("app.main.AnthropicClient", return_value=mock_llm):
        db.update_session_telemetry.side_effect = Exception("DB exploded")
        resp = client.post("/recommend", json={"occasion": "movie night"}, headers=AUTH_HEADER)
    assert resp.status_code == 200
