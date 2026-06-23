"""Sessions endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials

from backend.auth import bearer_scheme, get_current_user
from backend.db import DB

router = APIRouter(prefix="/sessions", tags=["sessions"])


def _db(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: str = Depends(get_current_user),
) -> DB:
    return DB(creds.credentials)


# IMPORTANT: /sessions/active and /sessions/stats MUST be registered before
# /sessions/{id} so FastAPI does not match those literals as a UUID path parameter.

@router.get("/stats")
def get_session_stats(db: DB = Depends(_db)) -> dict:
    return db.get_session_stats()


@router.get("/active")
def get_active_session(db: DB = Depends(_db)) -> dict:
    session = db.get_active_session()
    if session is None:
        raise HTTPException(status_code=404, detail="No active session")
    return session


@router.get("")
def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DB = Depends(_db),
) -> list[dict]:
    return db.list_sessions(limit=limit, offset=offset)


@router.get("/{session_id}")
def get_session(session_id: str, db: DB = Depends(_db)) -> dict:
    session = db.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/{session_id}/end")
def end_session(session_id: str, db: DB = Depends(_db)) -> dict:
    session = db.end_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/{session_id}/drinks")
def list_session_drinks(session_id: str, db: DB = Depends(_db)) -> list[dict]:
    if db.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return db.list_session_drinks(session_id)
