"""Tests for sessions endpoints. DB is mocked."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.routers.sessions import _db, router

app = FastAPI()
app.include_router(router)
client = TestClient(app, raise_server_exceptions=False)

AUTH_HEADER = {"Authorization": "Bearer fake-jwt"}

SESSION = {
    "id": "s1",
    "occasion": "movie night",
    "mood": "cozy",
    "created_at": "2026-01-01T00:00:00+00:00",
    "ended_at": None,
    "session_companions": [{"companion_id": "c1"}],
}
ENDED_SESSION = {**SESSION, "ended_at": "2026-01-02T00:00:00+00:00"}
DRINK = {
    "id": "d1",
    "session_id": "s1",
    "name": "Boulevardier",
    "ingredients": [],
    "steps": [],
    "why": "Classic.",
    "verdict": None,
    "created_at": "2026-01-01T00:00:00+00:00",
}


STATS = {
    "total_sessions": 3,
    "total_input_tokens": 1500,
    "total_output_tokens": 600,
    "avg_latency_ms": 1200,
    "avg_bottle_count": 8,
}


def _mock_db(session=None, session_list=None, drink_list=None, stats=None):
    db = MagicMock()
    db.get_session.return_value = session
    db.get_active_session.return_value = session
    db.list_sessions.return_value = session_list or []
    db.end_session.return_value = session
    db.list_session_drinks.return_value = drink_list or []
    db.get_session_stats.return_value = stats or STATS
    return db


@contextlib.contextmanager
def _db_override(db):
    app.dependency_overrides[_db] = lambda: db
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_list_requires_auth():
    resp = client.get("/sessions")
    assert resp.status_code in (401, 403)


def test_list_sessions():
    db = _mock_db(session_list=[SESSION])
    with _db_override(db):
        resp = client.get("/sessions", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json() == [SESSION]
    db.list_sessions.assert_called_once_with(limit=20, offset=0)


def test_get_active_session():
    db = _mock_db(session=SESSION)
    with _db_override(db):
        resp = client.get("/sessions/active", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["id"] == "s1"


def test_get_active_session_not_found():
    db = _mock_db(session=None)
    db.get_active_session.return_value = None
    with _db_override(db):
        resp = client.get("/sessions/active", headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_active_not_matched_as_uuid():
    """GET /sessions/active must not be routed to get_session({id}='active')."""
    db = _mock_db(session=SESSION)
    with _db_override(db):
        resp = client.get("/sessions/active", headers=AUTH_HEADER)
    # get_active_session was called, not get_session
    db.get_active_session.assert_called_once()
    db.get_session.assert_not_called()


def test_get_session():
    db = _mock_db(session=SESSION)
    with _db_override(db):
        resp = client.get("/sessions/s1", headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.get_session.assert_called_once_with("s1")


def test_get_session_not_found():
    db = _mock_db(session=None)
    with _db_override(db):
        resp = client.get("/sessions/bad-id", headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_end_session():
    db = _mock_db(session=ENDED_SESSION)
    db.end_session.return_value = ENDED_SESSION
    with _db_override(db):
        resp = client.post("/sessions/s1/end", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["ended_at"] is not None
    db.end_session.assert_called_once_with("s1")


def test_end_session_not_found():
    db = _mock_db(session=None)
    db.end_session.return_value = None
    with _db_override(db):
        resp = client.post("/sessions/bad-id/end", headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_list_session_drinks():
    db = _mock_db(session=SESSION, drink_list=[DRINK])
    with _db_override(db):
        resp = client.get("/sessions/s1/drinks", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json() == [DRINK]
    db.list_session_drinks.assert_called_once_with("s1")


def test_list_session_drinks_session_not_found():
    db = _mock_db(session=None, drink_list=[DRINK])
    with _db_override(db):
        resp = client.get("/sessions/foreign-id/drinks", headers=AUTH_HEADER)
    assert resp.status_code == 404
    db.list_session_drinks.assert_not_called()


def test_get_stats_returns_aggregates():
    db = _mock_db(stats=STATS)
    with _db_override(db):
        resp = client.get("/sessions/stats", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sessions"] == 3
    assert data["total_input_tokens"] == 1500
    assert data["avg_latency_ms"] == 1200
    db.get_session_stats.assert_called_once()


def test_stats_not_matched_as_session_id():
    """GET /sessions/stats must not route to get_session({id}='stats')."""
    db = _mock_db(stats=STATS)
    with _db_override(db):
        resp = client.get("/sessions/stats", headers=AUTH_HEADER)
    assert resp.status_code == 200
    db.get_session_stats.assert_called_once()
    db.get_session.assert_not_called()
