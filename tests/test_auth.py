"""Tests for the JWT auth dependency."""

from __future__ import annotations

import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

TEST_SECRET = "test-jwt-secret-32-chars-minimum!!"
TEST_USER_ID = "00000000-0000-0000-0000-000000000001"


def _make_token(
    secret: str = TEST_SECRET,
    user_id: str = TEST_USER_ID,
    audience: str = "authenticated",
    role: str = "authenticated",
    exp_offset: int = 3600,
) -> str:
    payload = {
        "sub": user_id,
        "aud": audience,
        "role": role,
        "iat": int(time.time()),
        "exp": int(time.time()) + exp_offset,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def _call(token: str, monkeypatch) -> str:
    monkeypatch.setenv("SUPABASE_JWT_TOKEN", TEST_SECRET)
    from backend.auth import get_current_user

    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    return get_current_user(creds)


def test_valid_token_returns_user_id(monkeypatch):
    token = _make_token()
    user_id = _call(token, monkeypatch)
    assert user_id == TEST_USER_ID


def test_expired_token_raises_401(monkeypatch):
    token = _make_token(exp_offset=-3600)
    with pytest.raises(HTTPException) as exc:
        _call(token, monkeypatch)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


def test_wrong_secret_raises_401(monkeypatch):
    token = _make_token(secret="wrong-secret-that-does-not-match!!")
    with pytest.raises(HTTPException) as exc:
        _call(token, monkeypatch)
    assert exc.value.status_code == 401


def test_wrong_audience_raises_401(monkeypatch):
    token = _make_token(audience="anon")
    with pytest.raises(HTTPException) as exc:
        _call(token, monkeypatch)
    assert exc.value.status_code == 401


def test_service_role_token_rejected(monkeypatch):
    token = _make_token(role="service_role")
    with pytest.raises(HTTPException) as exc:
        _call(token, monkeypatch)
    assert exc.value.status_code == 401
    assert "role" in exc.value.detail.lower()


def test_missing_env_var_raises_503(monkeypatch):
    monkeypatch.delenv("SUPABASE_JWT_TOKEN", raising=False)
    monkeypatch.delenv("SUPABASE_PROJECT_URL", raising=False)
    token = _make_token()  # valid HS256 token; env var absent → 503
    from backend.auth import get_current_user
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(creds)
    assert exc.value.status_code == 503


def test_missing_sub_raises_401(monkeypatch):
    monkeypatch.setenv("SUPABASE_JWT_TOKEN", TEST_SECRET)
    payload = {"aud": "authenticated", "iat": int(time.time()), "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, TEST_SECRET, algorithm="HS256")
    from backend.auth import get_current_user
    creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
    with pytest.raises(HTTPException) as exc:
        get_current_user(creds)
    assert exc.value.status_code == 401
