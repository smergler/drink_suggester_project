"""FastAPI app — thin vertical slice, hardcoded inventory for v1.

Run locally:
    .venv/bin/uvicorn app.main:app --reload

POST /recommend   → Recommendation
GET  /inventory   → list[Bottle]
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from evals.fixtures import INVENTORY
from recommender.llm import AnthropicClient
from recommender.recommender import RecommendationError, recommend
from recommender.schemas import Bottle, Recommendation, RecommendRequest

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


@app.exception_handler(RecommendationError)
async def recommendation_error_handler(request: Request, exc: RecommendationError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": str(exc)})


@app.post("/recommend", response_model=Recommendation)
@limiter.limit("10/minute")
def recommend_drinks(req: RecommendRequest, request: Request) -> Recommendation:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="ANTHROPIC_API_KEY not configured")
    llm = AnthropicClient()
    return recommend(req, INVENTORY, llm)


@app.get("/inventory", response_model=list[Bottle])
def get_inventory() -> list[Bottle]:
    return INVENTORY


# Use absolute path so the app works regardless of cwd.
_STATIC_DIR = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=_STATIC_DIR, html=True), name="static")
