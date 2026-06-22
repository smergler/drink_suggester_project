"""FastAPI app — drink suggester with Supabase-backed persistence.

Run locally:
    .venv/bin/uvicorn app.main:app --reload

POST /recommend          → Recommendation  (auth required; uses real inventory)
GET  /inventory          → list[Bottle]    (auth required)
... + /companions, /sessions, /session-drinks
"""

from __future__ import annotations

import os
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
)

load_dotenv()

limiter = Limiter(key_func=get_remote_address, default_limits=["20/minute"])

app = FastAPI(title="Drink Suggester")
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

    llm = AnthropicClient()
    result = recommend(req, inventory_bottles, llm)

    # Create or reuse the active session. Reusing intentionally allows multiple
    # recommend calls per session — each adds a new batch of suggestions.
    session = db.get_active_session()
    if session is None:
        session = db.create_session(
            occasion=req.occasion,
            mood=req.mood,
            companion_ids=[],  # companion names only in v1; IDs come in P6.10 frontend
        )
    session_id: str | None = session.get("id")
    if session_id is None:
        raise HTTPException(status_code=500, detail="Failed to create session")

    # Save suggested drinks as session_drinks
    drinks_payload = [
        {
            "name": s.name,
            "ingredients": [i.model_dump() for i in s.ingredients],
            "steps": s.steps,
            "why": s.why,
        }
        for s in result.suggestions
    ]
    db.create_session_drinks(session_id, drinks_payload)

    response = JSONResponse(
        content=result.model_dump(),
        headers={"X-Session-Id": session_id},
    )
    return response


# Use absolute path so the app works regardless of cwd.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
