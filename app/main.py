"""FastAPI app — drink suggester with Supabase-backed persistence.

Run locally:
    .venv/bin/uvicorn app.main:app --reload

POST /recommend          → Recommendation  (auth required; uses real inventory)
GET  /inventory          → list[Bottle]    (auth required)
... + /companions, /sessions, /session-drinks
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from backend.auth import bearer_scheme, get_current_user
from backend.db import DB
from backend.routers import companions, inventory, session_drinks, sessions
from recommender.llm import AnthropicClient
from recommender.recommender import RecommendationError, recommend
from recommender.schemas import (
    Bottle,
    CompanionProfile,
    Recommendation,
    RecommendRequest,
    SessionDrinkFeedback,
)

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])

app = FastAPI(title="BarBack")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(inventory.router)
app.include_router(companions.router)
app.include_router(sessions.router)
app.include_router(session_drinks.router)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/config")
def get_config() -> dict:
    """Public config for the frontend — safe (anon/public keys only)."""
    return {
        "supabase_url": os.environ.get("SUPABASE_PROJECT_URL", ""),
        "supabase_anon_key": os.environ.get("SUPABASE_ANON_KEY", ""),
    }


@app.exception_handler(RecommendationError)
async def recommendation_error_handler(request: Request, exc: RecommendationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.post("/recommend", response_model=Recommendation)
@limiter.limit("10/minute")
def recommend_drinks(
    req: RecommendRequest,
    request: Request,
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    user_id: str = Depends(get_current_user),
) -> JSONResponse:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")

    db = DB(creds.credentials)

    # Validate companion ownership if profiles were provided by name
    # (Future: accept companion_ids; for now trust CompanionProfile names from request)

    # Fetch real inventory from DB
    db_bottles = db.list_bottles(include_inactive=False, limit=1000, offset=0)
    if not db_bottles:
        raise HTTPException(status_code=400, detail="No bottles in inventory; add some first")

    inventory_bottles = [
        Bottle(id=b["id"], name=b["name"], category=b["category"], subcategory=b.get("subcategory"))
        for b in db_bottles
    ]

    # Get or create the active session before recommend() so we can fetch
    # prior drinks and pass them as context (deduplication + in-session feedback).
    session = db.get_active_session()
    if session is None:
        session = db.create_session(
            occasion=req.occasion,
            mood=req.mood,
            companion_ids=req.companion_ids,
        )
    session_id: str | None = session.get("id")
    if session_id is None:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Populate in-session memory so the LLM won't repeat drinks or ignore verdicts.
    prior_drinks = db.list_session_drinks(session_id)
    req.already_suggested = [d["name"] for d in prior_drinks]
    req.session_feedback = [
        SessionDrinkFeedback(name=d["name"], verdict=d["verdict"])
        for d in prior_drinks
        if d.get("verdict") and d["verdict"] != "neutral"
    ]

    llm = AnthropicClient()
    t0 = time.perf_counter()
    result = recommend(req, inventory_bottles, llm)
    latency_ms = round((time.perf_counter() - t0) * 1000)

    # Save suggested drinks as session_drinks
    drinks_payload = [
        {
            "name": s.name,
            "ingredients": [i.model_dump() for i in s.ingredients],
            "steps": s.steps,
            "why": s.why,
            "suited_for": s.suited_for,
        }
        for s in result.suggestions
    ]
    db.create_session_drinks(session_id, drinks_payload)

    # Write telemetry — non-fatal if it fails (e.g. DB unavailable).
    if llm.last_usage is not None:
        try:
            db.update_session_telemetry(
                session_id,
                bottle_count=len(inventory_bottles),
                input_tokens=llm.last_usage.input_tokens,
                output_tokens=llm.last_usage.output_tokens,
                latency_ms=latency_ms,
            )
        except Exception:
            logging.exception("Failed to write session telemetry (non-fatal)")

    response = JSONResponse(
        content=result.model_dump(),
        headers={"X-Session-Id": session_id},
    )
    return response


# Use absolute path so the app works regardless of cwd.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
