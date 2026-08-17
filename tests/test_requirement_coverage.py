"""Pytest wrapper around core.checks.check_coverage — the exact function the
CLI calls, no reimplemented logic here.
"""
from unittest.mock import patch

from core.checks import check_coverage
from core.schema import Intent, RequirementChunk, TestCase

CHUNK = RequirementChunk(
    source_file="coupon.md",
    section_title="Apply coupon",
    text=(
        "When a user is on the checkout page, they can enter a coupon code "
        "and click Apply. If valid, the discount is subtracted from the "
        "order total and the updated total is shown."
    ),
)

INTENT = Intent(
    goal="Apply a valid coupon during checkout.",
    actor="user",
    action="enters a coupon code and clicks Apply",
    expected=["discount subtracted from order total", "updated total is shown"],
    not_expected=["discount applied when coupon is invalid"],
    keywords=["coupon", "checkout", "discount"],
)


def test_stage_one_failure_stops_before_any_geval_call():
    incomplete = TestCase(
        preconditions=["user is on checkout page"],
        steps=["user enters a coupon code", "user clicks Apply"],
        expected_result="the coupon field accepts input",  # never mentions the discount or total
        source_chunk=CHUNK,
    )

    with patch("core.checks.run_coverage_geval") as mock_geval:
        result = check_coverage(incomplete, INTENT, CHUNK)

    mock_geval.assert_not_called()
    assert result.passed is False
    assert "missing expected item" in result.reason


def test_stage_one_pass_proceeds_to_geval():
    complete = TestCase(
        preconditions=["user is on checkout page"],
        steps=["user enters a coupon code", "user clicks Apply"],
        expected_result="the discount is subtracted from order total and the updated total is shown",
        source_chunk=CHUNK,
    )

    with patch("core.checks.run_coverage_geval") as mock_geval:
        mock_geval.return_value.passed = True
        check_coverage(complete, INTENT, CHUNK)

    mock_geval.assert_called_once()
    args, _ = mock_geval.call_args
    assert args[0] == CHUNK.text


def test_not_expected_silence_is_not_flagged_as_wrongly_asserted():
    """A test that never mentions invalid coupons at all shouldn't trip the
    not_expected deterministic guard — silence is a semantic-stage question,
    not this stage's job (see core/checks.py's docstring on the heuristic).
    """
    happy_path_only = TestCase(
        preconditions=["user is on checkout page"],
        steps=["user enters a coupon code", "user clicks Apply"],
        expected_result="the discount is subtracted from order total and the updated total is shown",
        source_chunk=CHUNK,
    )

    with patch("core.checks.run_coverage_geval") as mock_geval:
        mock_geval.return_value.passed = True
        check_coverage(happy_path_only, INTENT, CHUNK)

    mock_geval.assert_called_once()  # stage 1 passed clean, no wrongly_asserted items
