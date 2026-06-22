import pytest

from evals.judge import (
    JudgeError,
    JudgeVerdict,
    build_judge_prompt,
    judge_suggestion,
    summarize,
)
from recommender.schemas import (
    CompanionProfile,
    Ingredient,
    IngredientSource,
    RecommendRequest,
    Suggestion,
)

REQ = RecommendRequest(
    occasion="aperitivo",
    mood="bitter",
    constraints=["nothing too sweet"],
    companions=[CompanionProfile(name="wife", dislikes=["tropical"])],
)
SUGG = Suggestion(
    name="Boulevardier",
    description="Bitter and stirred",
    ingredients=[Ingredient(name="Campari", quantity="1 oz", source=IngredientSource.inventory)],
    steps=["Stir", "Strain"],
)

PASS = '{"constraints_respected": true, "occasion_fit": 5, "recipe_plausibility": 4, "notes": "great"}'
FAIL = '{"constraints_respected": false, "occasion_fit": 2, "recipe_plausibility": 3, "notes": "too sweet"}'


class SequenceClient:
    def __init__(self, *responses):
        self._responses = list(responses)
        self.calls = 0

    def generate(self, system, user):  # noqa: ARG002
        self.calls += 1
        return self._responses.pop(0)


def test_prompt_includes_constraints_and_dislikes():
    p = build_judge_prompt(SUGG, REQ)
    assert "nothing too sweet" in p
    assert "tropical" in p
    assert "Boulevardier" in p


def test_parses_pass_verdict():
    v = judge_suggestion(SUGG, REQ, SequenceClient(PASS))
    assert v.constraints_respected
    assert v.occasion_fit == 5


def test_parses_fail_verdict_with_fence():
    fenced = "```json\n" + FAIL + "\n```"
    v = judge_suggestion(SUGG, REQ, SequenceClient(fenced))
    assert not v.constraints_respected


def test_retries_then_raises_on_garbage():
    client = SequenceClient("garbage", "still garbage")
    with pytest.raises(JudgeError):
        judge_suggestion(SUGG, REQ, client)
    assert client.calls == 2


def test_out_of_range_score_is_rejected_then_retried():
    bad = '{"constraints_respected": true, "occasion_fit": 9, "recipe_plausibility": 4, "notes": "x"}'
    client = SequenceClient(bad, PASS)
    v = judge_suggestion(SUGG, REQ, client)
    assert v.occasion_fit == 5
    assert client.calls == 2


def test_summary_aggregates():
    s = summarize([
        JudgeVerdict(constraints_respected=True, occasion_fit=4, recipe_plausibility=5),
        JudgeVerdict(constraints_respected=False, occasion_fit=2, recipe_plausibility=3),
    ])
    assert s.n == 2
    assert s.constraint_pass_rate == 0.5
    assert s.avg_occasion_fit == 3.0
    assert s.avg_recipe_plausibility == 4.0
