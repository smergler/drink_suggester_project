from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class IngredientSource(str, Enum):
    """Where an ingredient comes from. The grounding metric only polices
    `inventory` and `pantry` claims — those are the ways a model can use
    something you don't have without telling you."""

    inventory = "inventory"   # a bottle the user owns
    pantry = "pantry"         # always-stocked staple (ice, water, sugar, salt)
    perishable = "perishable" # fresh staple that varies (citrus, egg white, herbs)
    missing = "missing"       # specialty item the user does NOT own — honest disclosure


class Ingredient(BaseModel):
    name: str
    quantity: str | None = None
    source: IngredientSource


class Suggestion(BaseModel):
    name: str
    description: str
    ingredients: list[Ingredient]
    steps: list[str] = Field(default_factory=list)
    why: str = ""


class Recommendation(BaseModel):
    suggestions: list[Suggestion]


class Bottle(BaseModel):
    id: str
    name: str
    category: str
    subcategory: str | None = None


class CompanionProfile(BaseModel):
    name: str
    likes: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)


class SessionDrinkFeedback(BaseModel):
    name: str
    verdict: str  # "liked" | "disliked" | "neutral"


class RecommendRequest(BaseModel):
    occasion: str = Field(..., max_length=200)
    mood: str | None = Field(None, max_length=200)
    count: int = Field(3, ge=1, le=10)
    constraints: list[str] = Field(default_factory=list)
    companions: list[CompanionProfile] = Field(default_factory=list)
    companion_ids: list[str] = Field(default_factory=list)
    # Fresh ingredients the user confirms they have on hand right now.
    available_perishables: list[str] = Field(default_factory=list)
    # Server-populated: drinks already suggested this session (LLM deduplication).
    already_suggested: list[str] = Field(default_factory=list)
    # Server-populated: non-neutral verdicts from this session.
    session_feedback: list[SessionDrinkFeedback] = Field(default_factory=list)
