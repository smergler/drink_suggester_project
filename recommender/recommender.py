from __future__ import annotations

import json

from pydantic import ValidationError

from .context import SYSTEM_PROMPT, build_context
from .llm import LLMClient
from .schemas import Bottle, Recommendation, RecommendRequest

# JSON schema for structured output — must stay in sync with schemas.Recommendation.
# All object nodes need additionalProperties:false; min/max constraints are stripped.
RECOMMENDATION_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "suggestions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "description": {"type": "string"},
                    "ingredients": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string"},
                                "quantity": {
                                    "anyOf": [{"type": "string"}, {"type": "null"}]
                                },
                                "source": {
                                    "type": "string",
                                    "enum": ["inventory", "pantry", "perishable", "missing"],
                                },
                            },
                            "required": ["name", "source"],
                            "additionalProperties": False,
                        },
                    },
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "why": {"type": "string"},
                    "suited_for": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "description", "ingredients"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["suggestions"],
    "additionalProperties": False,
}


class RecommendationError(Exception):
    pass


def recommend(
    req: RecommendRequest,
    inventory: list[Bottle],
    llm: LLMClient,
    use_retrieval: bool = False,
) -> Recommendation:
    user_msg = build_context(req, inventory, use_retrieval=use_retrieval)

    # Use structured outputs when available (AnthropicClient) — API guarantees valid JSON.
    if hasattr(llm, "generate_structured"):
        raw = llm.generate_structured(SYSTEM_PROMPT, user_msg, RECOMMENDATION_SCHEMA)
        try:
            return _parse(raw)
        except (json.JSONDecodeError, ValidationError) as e:
            raise RecommendationError(f"Structured output parse failed: {e}") from e

    # Legacy path for MockClient and other LLMClient implementations.
    raw = llm.generate(SYSTEM_PROMPT, user_msg)
    try:
        return _parse(raw)
    except (json.JSONDecodeError, ValidationError):
        # one corrective retry before giving up
        retry_msg = (
            user_msg
            + "\n\nYour previous reply was not valid JSON. Respond with ONLY the JSON object."
        )
        raw = llm.generate(SYSTEM_PROMPT, retry_msg)
        try:
            return _parse(raw)
        except (json.JSONDecodeError, ValidationError) as e:
            raise RecommendationError(f"Model did not return valid JSON: {e}") from e


def _parse(raw: str) -> Recommendation:
    raw = raw.strip()
    if raw.startswith("```"):  # tolerate ```json fences
        raw = raw.split("```", 2)[1]
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    data = json.loads(raw)
    return Recommendation.model_validate(data)
