"""Pytest wrapper around core.checks.check_grounding — same pattern as
test_requirement_coverage.py: the real orchestration function, with the
DeepEval judge calls mocked so the suite stays fast and free. The judge
functions themselves were exercised for real via the CLI (see README).
"""
from unittest.mock import patch

from core.checks import check_grounding
from core.schema import CheckResult, RequirementChunk, TestCase

CHUNK_A = RequirementChunk(source_file="coupon.md", section_title="Apply coupon", text="Coupon text.")
CHUNK_B = RequirementChunk(source_file="checkout.md", section_title="Layout", text="Checkout layout text.")

TEST_CASE = TestCase(
    preconditions=["user is on checkout page"],
    steps=["user enters a coupon code", "user clicks Apply"],
    expected_result="the discount is subtracted from order total",
    source_chunk=CHUNK_A,
)


def test_check_grounding_returns_two_distinct_results():
    fake_faithfulness = CheckResult(name="faithfulness", passed=True, score=1.0, reason="ok")
    fake_relevancy = CheckResult(name="contextual_relevancy", passed=True, score=0.9, reason="ok")

    with patch("core.checks.run_faithfulness", return_value=fake_faithfulness) as mock_f, \
         patch("core.checks.run_contextual_relevancy", return_value=fake_relevancy) as mock_r:
        results = check_grounding(TEST_CASE, "coupon discount", [CHUNK_A, CHUNK_B])

    assert [r.name for r in results] == ["faithfulness", "contextual_relevancy"]
    mock_f.assert_called_once()
    mock_r.assert_called_once()

    # both metrics see the same retrieval_context: every retrieved chunk's text
    faithfulness_context = mock_f.call_args[0][1]
    relevancy_context = mock_r.call_args[0][1]
    assert faithfulness_context == [CHUNK_A.text, CHUNK_B.text]
    assert relevancy_context == [CHUNK_A.text, CHUNK_B.text]


def test_check_grounding_falls_back_to_source_chunk_if_retrieval_list_empty():
    fake_result = CheckResult(name="x", passed=True, score=1.0, reason="ok")
    with patch("core.checks.run_faithfulness", return_value=fake_result) as mock_f, \
         patch("core.checks.run_contextual_relevancy", return_value=fake_result):
        check_grounding(TEST_CASE, "query", [])

    context = mock_f.call_args[0][1]
    assert context == [TEST_CASE.source_chunk.text]
