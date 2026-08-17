"""DeepEval-specific wiring: GEval rubric, FaithfulnessMetric,
ContextualRelevancyMetric, AnthropicModel judge config.

core/checks.py calls into this module and only ever sees CheckResult back —
DeepEval's own types (LLMTestCase, GEval, metric objects) never leak into
core/.
"""
from __future__ import annotations

from functools import lru_cache

from deepeval.metrics import ContextualRelevancyMetric, FaithfulnessMetric, GEval
from deepeval.models import AnthropicModel
from deepeval.test_case import LLMTestCase, SingleTurnParams

from core.config import ANTHROPIC_MODEL, get_anthropic_api_key
from core.schema import CheckResult, IntentGroundingItem

COVERAGE_THRESHOLD = 0.7
FAITHFULNESS_THRESHOLD = 0.7
CONTEXTUAL_RELEVANCY_THRESHOLD = 0.5

# Two-sided rubric: one-sided evaluation produces one-sided test generation.
# A test can look complete while silently never checking that a failure
# condition correctly doesn't occur — this rubric grades both directions.
COVERAGE_EVALUATION_STEPS = [
    "'input' is the requirement text; 'actual_output' is a generated QA test case.",
    "Check that the test case's steps and expected result verify every positive "
    "condition the requirement text implies (the happy path it actually describes).",
    "Check that the test case does not invent any condition, field, rule, or "
    "behavior the requirement text never states.",
    "Check whether the test case verifies negative/failure conditions implied by "
    "the requirement (e.g. an invalid or expired input being correctly rejected). "
    "If the requirement text itself never describes such a case, the test case "
    "correctly not inventing one is NOT a failure — only penalize missing negative "
    "coverage the requirement text actually supports.",
    "Penalize the test case if it asserts a negative condition as succeeding "
    "(e.g. treats an invalid case as if it were accepted).",
]


@lru_cache(maxsize=1)
def _judge() -> AnthropicModel:
    return AnthropicModel(model=ANTHROPIC_MODEL, api_key=get_anthropic_api_key())


def run_coverage_geval(chunk_text: str, rendered_test_case: str) -> CheckResult:
    metric = GEval(
        name="Requirement Coverage",
        evaluation_steps=COVERAGE_EVALUATION_STEPS,
        evaluation_params=[SingleTurnParams.INPUT, SingleTurnParams.ACTUAL_OUTPUT],
        model=_judge(),
        threshold=COVERAGE_THRESHOLD,
    )
    test_case = LLMTestCase(input=chunk_text, actual_output=rendered_test_case)
    metric.measure(test_case)
    return CheckResult(
        name="coverage_semantic",
        passed=metric.score >= COVERAGE_THRESHOLD,
        score=metric.score,
        reason=metric.reason,
    )


def run_faithfulness(rendered_test_case: str, retrieval_context: list[str]) -> CheckResult:
    metric = FaithfulnessMetric(model=_judge(), threshold=FAITHFULNESS_THRESHOLD)
    test_case = LLMTestCase(
        input="\n\n".join(retrieval_context),
        actual_output=rendered_test_case,
        retrieval_context=retrieval_context,
    )
    metric.measure(test_case)
    return CheckResult(
        name="faithfulness",
        passed=metric.score >= FAITHFULNESS_THRESHOLD,
        score=metric.score,
        reason=metric.reason,
    )


def run_contextual_relevancy(query: str, retrieval_context: list[str]) -> CheckResult:
    metric = ContextualRelevancyMetric(model=_judge(), threshold=CONTEXTUAL_RELEVANCY_THRESHOLD)
    test_case = LLMTestCase(input=query, retrieval_context=retrieval_context)
    metric.measure(test_case)
    return CheckResult(
        name="contextual_relevancy",
        passed=metric.score >= CONTEXTUAL_RELEVANCY_THRESHOLD,
        score=metric.score,
        reason=metric.reason,
    )


def run_intent_grounding(
    expected: list[str], not_expected: list[str], raw_requirement_text: str
) -> list[IntentGroundingItem]:
    """Same FaithfulnessMetric used in run_faithfulness, pointed at intent
    extraction's own output instead of the generated test case — is what
    Intent.expected/not_expected claims are themselves supported by the raw
    requirement text, or did extraction infer beyond it? This is a
    transparency annotation, not a gate: see core/intent.py's
    annotate_intent_grounding for why nothing here produces a CheckResult.

    FaithfulnessMetric normally extracts its own claims from actual_output;
    here each claim is already one atomic Intent.expected/not_expected
    string, so claims are supplied directly and only the verification step
    runs — one Claude call instead of two, and an exact 1:1 correspondence
    between input claims and returned items instead of a hoped-for one.

    Polarity matters here and is easy to get backwards: FaithfulnessMetric's
    "yes"/"no" always means "is this claim's literal text supported by the
    context". For an `expected` claim that's the intuitive reading — "yes"
    is grounded. For a `not_expected` claim, the claim text itself describes
    a bad outcome, so the well-grounded case is the text explicitly ruling
    it out — verdict "no" (contradicted) — not "yes". "idk" (context is
    silent either way) is the real "inferred beyond the text" case for
    both, and a `not_expected` claim the context actually confirms ("yes")
    is flagged as ungrounded too, since that would mean the text describes
    the bad outcome happening.
    """
    claims = expected + not_expected
    if not claims:
        return []
    metric = FaithfulnessMetric(model=_judge(), threshold=FAITHFULNESS_THRESHOLD)
    metric.claims = claims
    metric.truths = metric._generate_truths([raw_requirement_text], multimodal=False)
    metric.verdicts = metric._generate_verdicts(multimodal=False)
    _fallback_reason = {
        "yes": "supported by the requirement text",
        "no": "contradicted by the requirement text",
        "idk": "the requirement text doesn't address this either way",
    }

    items = []
    for idx, (claim, verdict) in enumerate(zip(claims, metric.verdicts)):
        is_not_expected = idx >= len(expected)
        v = verdict.verdict.strip().lower()
        grounded = (v == "no") if is_not_expected else (v == "yes")
        reason = verdict.reason or _fallback_reason.get(v, "unclear")
        if is_not_expected and v == "yes":
            reason = "the requirement text appears to support this happening, which contradicts it being listed as something that must NOT happen — " + reason
        items.append(IntentGroundingItem(claim=claim, supported=grounded, reason=reason))
    return items
