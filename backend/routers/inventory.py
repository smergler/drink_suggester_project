"""Inventory (bottles) endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from backend.auth import bearer_scheme, get_current_user
from backend.db import DB

router = APIRouter(prefix="/inventory", tags=["inventory"])


class BottleIn(BaseModel):
    name: str = Field(..., max_length=200)
    category: str = Field(..., max_length=100)
    subcategory: str | None = Field(None, max_length=100)


def _db(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: str = Depends(get_current_user),
) -> DB:
    return DB(creds.credentials)


@router.get("")
def list_bottles(
    include_inactive: bool = False,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: DB = Depends(_db),
) -> list[dict]:
    return db.list_bottles(include_inactive=include_inactive, limit=limit, offset=offset)


@router.post("", status_code=201)
def create_bottle(body: BottleIn, db: DB = Depends(_db)) -> dict:
    try:
        return db.create_bottle(body.name, body.category, body.subcategory)
    except Exception as e:
        if "unique" in str(e).lower():
            raise HTTPException(status_code=409, detail=f"Bottle '{body.name}' already exists")
        raise HTTPException(status_code=500, detail="Database error")


@router.put("/{bottle_id}")
def update_bottle(bottle_id: str, body: BottleIn, db: DB = Depends(_db)) -> dict:
    row = db.update_bottle(
        bottle_id,
        name=body.name,
        category=body.category,
        subcategory=body.subcategory,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Bottle not found")
    return row


@router.delete("/{bottle_id}", status_code=204)
def delete_bottle(bottle_id: str, db: DB = Depends(_db)) -> None:
    found = db.delete_bottle(bottle_id)
    if not found:
        raise HTTPException(status_code=404, detail="Bottle not found")
