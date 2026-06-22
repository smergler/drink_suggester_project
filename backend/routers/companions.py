"""Companions + preferences endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.auth import bearer_scheme, get_current_user
from backend.db import DB

router = APIRouter(prefix="/companions", tags=["companions"])


class CompanionIn(BaseModel):
    name: str = Field(..., max_length=200)


class PreferenceIn(BaseModel):
    type: str = Field(..., pattern="^(like|dislike)$")
    value: str = Field(..., max_length=100)


def _db(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: str = Depends(get_current_user),
) -> DB:
    return DB(creds.credentials)


@router.get("")
def list_companions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DB = Depends(_db),
) -> list[dict]:
    return db.list_companions(limit=limit, offset=offset)


@router.post("", status_code=201)
def create_companion(body: CompanionIn, db: DB = Depends(_db)) -> dict:
    try:
        return db.create_companion(body.name)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Companion '{body.name}' already exists")
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/{companion_id}")
def update_companion(companion_id: str, body: CompanionIn, db: DB = Depends(_db)) -> dict:
    row = db.update_companion(companion_id, body.name)
    if row is None:
        raise HTTPException(status_code=404, detail="Companion not found")
    return row


@router.delete("/{companion_id}", status_code=204)
def delete_companion(companion_id: str, db: DB = Depends(_db)) -> None:
    found = db.delete_companion(companion_id)
    if not found:
        raise HTTPException(status_code=404, detail="Companion not found")


@router.get("/{companion_id}/preferences")
def list_preferences(companion_id: str, db: DB = Depends(_db)) -> list[dict]:
    return db.list_preferences(companion_id)


@router.post("/{companion_id}/preferences", status_code=201)
def create_preference(companion_id: str, body: PreferenceIn, db: DB = Depends(_db)) -> dict:
    try:
        return db.create_preference(companion_id, body.type, body.value)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Preference for '{body.value}' already exists")
        raise HTTPException(status_code=500, detail="Database error")


@router.delete("/{companion_id}/preferences/{preference_id}", status_code=204)
def delete_preference(companion_id: str, preference_id: str, db: DB = Depends(_db)) -> None:
    found = db.delete_preference(preference_id)
    if not found:
        raise HTTPException(status_code=404, detail="Preference not found")
