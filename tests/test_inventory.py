"""Tests for inventory endpoints. DB is mocked — no live Supabase."""

from __future__ import annotations

import contextlib
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from backend.routers.inventory import _db, router
from fastapi import FastAPI

# Minimal app with just the inventory router
app = FastAPI()
app.include_router(router)
client = TestClient(app, raise_server_exceptions=False)

BOTTLE = {
    "id": "aaaa",
    "name": "Four Roses Bourbon",
    "category": "bourbon",
    "subcategory": None,
    "is_active": True,
    "created_at": "2026-01-01T00:00:00+00:00",
    "updated_at": "2026-01-01T00:00:00+00:00",
}

AUTH_HEADER = {"Authorization": "Bearer fake-jwt"}


def _mock_db(return_list=None, return_one=None, create_return=None):
    """Build a mock DB with canned responses."""
    db = MagicMock()
    db.list_bottles.return_value = return_list or []
    db.get_bottle.return_value = return_one
    db.create_bottle.return_value = create_return or BOTTLE
    db.update_bottle.return_value = return_one
    db.delete_bottle.return_value = bool(return_one)
    return db


@contextlib.contextmanager
def _db_override(db):
    """Override the _db dependency for the duration of a test."""
    app.dependency_overrides[_db] = lambda: db
    try:
        yield
    finally:
        app.dependency_overrides.clear()


def test_list_requires_auth():
    resp = client.get("/inventory")
    assert resp.status_code in (401, 403)


def test_list_bottles():
    db = _mock_db(return_list=[BOTTLE])
    with _db_override(db):
        resp = client.get("/inventory", headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json() == [BOTTLE]
    db.list_bottles.assert_called_once_with(include_inactive=False, limit=20, offset=0)


def test_create_bottle():
    db = _mock_db(create_return=BOTTLE)
    with _db_override(db):
        resp = client.post("/inventory", json={"name": "Four Roses Bourbon", "category": "bourbon"},
                           headers=AUTH_HEADER)
    assert resp.status_code == 201
    assert resp.json()["name"] == "Four Roses Bourbon"


def test_create_bottle_conflict():
    db = _mock_db()
    db.create_bottle.side_effect = Exception("unique constraint violated")
    with _db_override(db):
        resp = client.post("/inventory", json={"name": "Four Roses Bourbon", "category": "bourbon"},
                           headers=AUTH_HEADER)
    assert resp.status_code == 409


def test_update_bottle_success():
    updated = {**BOTTLE, "name": "Knob Creek Bourbon"}
    db = _mock_db(return_one=updated)
    with _db_override(db):
        resp = client.put(f"/inventory/{BOTTLE['id']}",
                          json={"name": "Knob Creek Bourbon", "category": "bourbon"},
                          headers=AUTH_HEADER)
    assert resp.status_code == 200
    assert resp.json()["name"] == "Knob Creek Bourbon"


def test_update_bottle_not_found():
    db = _mock_db(return_one=None)
    with _db_override(db):
        resp = client.put("/inventory/bad-id",
                          json={"name": "X", "category": "bourbon"},
                          headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_delete_bottle_not_found():
    db = _mock_db(return_one=None)
    with _db_override(db):
        resp = client.delete("/inventory/bad-id", headers=AUTH_HEADER)
    assert resp.status_code == 404


def test_delete_bottle_success():
    db = _mock_db(return_one=BOTTLE)
    with _db_override(db):
        resp = client.delete(f"/inventory/{BOTTLE['id']}", headers=AUTH_HEADER)
    assert resp.status_code == 204
