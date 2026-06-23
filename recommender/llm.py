from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class LLMClient(Protocol):
    def generate(self, system: str, user: str) -> str:
        """Return the model's raw text response (expected to be JSON)."""
        ...


@dataclass
class UsageStats:
    input_tokens: int
    output_tokens: int


class MockClient:
    """Returns canned responses keyed by scenario id. Lets the full pipeline +
    eval run offline with zero token spend."""

    def __init__(self, responses: dict[str, str], key: str):
        self._responses = responses
        self._key = key

    def generate(self, system: str, user: str) -> str:  # noqa: ARG002
        if self._key not in self._responses:
            raise KeyError(f"No mock response for scenario {self._key!r}")
        return self._responses[self._key]


# Models that rejected the `temperature` parameter (Opus 4.6+ family, Fable).
_MODELS_WITHOUT_TEMPERATURE = frozenset({
    "claude-opus-4-6", "claude-opus-4-7", "claude-opus-4-8",
    "claude-fable-5", "claude-mythos-5",
})


class AnthropicClient:
    """Live client that calls the Anthropic Messages API."""

    DEFAULT_MODEL = "claude-haiku-4-5-20251001"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.3,
    ):
        self._api_key = api_key
        self._model = model or self.DEFAULT_MODEL
        self._max_tokens = max_tokens
        self._temperature = temperature
        self.last_usage: UsageStats | None = None

    def _base_params(self) -> dict[str, Any]:
        params: dict[str, Any] = {"model": self._model, "max_tokens": self._max_tokens}
        if self._model not in _MODELS_WITHOUT_TEMPERATURE:
            params["temperature"] = self._temperature
        return params

    def generate(self, system: str, user: str) -> str:
        from anthropic import Anthropic  # lazy import; optional dependency

        client = Anthropic(api_key=self._api_key)
        msg = client.messages.create(
            **self._base_params(),
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        self.last_usage = UsageStats(
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )
        return msg.content[0].text

    def generate_structured(self, system: str, user: str, schema: dict[str, Any]) -> str:
        """Generate with output_config.format for guaranteed-valid JSON matching schema."""
        from anthropic import Anthropic  # lazy import; optional dependency

        client = Anthropic(api_key=self._api_key)
        msg = client.messages.create(
            **self._base_params(),
            system=system,
            messages=[{"role": "user", "content": user}],
            output_config={"format": {"type": "json_schema", "schema": schema}},
        )
        self.last_usage = UsageStats(
            input_tokens=msg.usage.input_tokens,
            output_tokens=msg.usage.output_tokens,
        )
        return msg.content[0].text
