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
from core.schema import CheckResult

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
