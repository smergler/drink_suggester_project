import pytest

from recommender.recommender import RecommendationError, _parse, recommend
from recommender.schemas import Bottle, RecommendRequest

INV = [Bottle(id="1", name="Four Roses Small Batch", category="bourbon")]
REQ = RecommendRequest(occasion="nightcap", count=1)

VALID = (
    '{"suggestions":[{"name":"Old Fashioned","description":"d",'
    '"ingredients":[{"name":"Four Roses Small Batch","quantity":"2 oz","source":"inventory"}],'
    '"steps":["stir"],"why":"w"}]}'
)


class SequenceClient:
    """Returns queued responses in order; records how many times it was called."""

    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, system, user):  # noqa: ARG002
        self.calls += 1
        return self._responses.pop(0)


def test_parses_plain_json():
    rec = recommend(REQ, INV, SequenceClient(VALID))
    assert rec.suggestions[0].name == "Old Fashioned"


def test_strips_json_code_fence():
    fenced = "```json\n" + VALID + "\n```"
    assert _parse(fenced).suggestions[0].name == "Old Fashioned"


def test_retries_once_on_bad_json_then_succeeds():
    client = SequenceClient("not json at all", VALID)
    rec = recommend(REQ, INV, client)
    assert rec.suggestions[0].name == "Old Fashioned"
    assert client.calls == 2


def test_raises_after_two_failures():
    client = SequenceClient("nope", "still nope")
    with pytest.raises(RecommendationError):
        recommend(REQ, INV, client)
    assert client.calls == 2
