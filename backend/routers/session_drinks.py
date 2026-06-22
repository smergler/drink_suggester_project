"""Session drinks — verdict endpoint with companion feedback."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.auth import bearer_scheme, get_current_user
from backend.db import DB
from recommender.inventory_match import match_bottle
from recommender.schemas import Bottle

router = APIRouter(prefix="/session-drinks", tags=["session-drinks"])


class VerdictIn(BaseModel):
    verdict: Literal["liked", "disliked", "neutral"]


def _db(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    _: str = Depends(get_current_user),
) -> DB:
    return DB(creds.credentials)


@router.patch("/{drink_id}/verdict")
def set_verdict(drink_id: str, body: VerdictIn, db: DB = Depends(_db)) -> dict:
    row = db.set_verdict(drink_id, body.verdict)
    if row is None:
        raise HTTPException(status_code=404, detail="Drink not found")
    if body.verdict in ("liked", "disliked"):
        _apply_feedback(db, row, body.verdict)
    return row


def _apply_feedback(db: DB, drink_row: dict, verdict: str) -> None:
    """Propagate drink verdict to companion preferences."""
    session = db.get_session(drink_row["session_id"])
    if not session:
        return

    companion_ids = [sc["companion_id"] for sc in session.get("session_companions", [])]
    if not companion_ids:
        return

    inventory_ings = [
        ing for ing in drink_row.get("ingredients", [])
        if ing.get("source") == "inventory"
    ]
    if not inventory_ings:
        return

    db_bottles = db.list_bottles(include_inactive=False, limit=1000, offset=0)
    schema_bottles = [
        Bottle(id=b["id"], name=b["name"], category=b["category"], subcategory=b.get("subcategory"))
        for b in db_bottles
    ]

    categories: set[str] = set()
    for ing in inventory_ings:
        matched = match_bottle(ing["name"], schema_bottles)
        if matched:
            categories.add(matched.category)

    upsert = db.upsert_companion_like if verdict == "liked" else db.upsert_companion_dislike
    for companion_id in companion_ids:
        for category in sorted(categories):
            upsert(companion_id, category)
