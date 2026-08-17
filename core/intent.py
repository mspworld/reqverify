"""One Claude call: read a requirement, extract its intent.

Intent extraction is a genuine fourth pipeline step, not a second opinion
that duplicates check_coverage. It earns its place by doing exactly two
jobs: producing `keywords` (drives retrieval) and producing `expected` /
`not_expected` (powers check_coverage's fast deterministic pre-check,
before any LLM-judged semantic check runs).
"""
from __future__ import annotations

import json

import anthropic

from core.config import ANTHROPIC_MODEL, get_anthropic_api_key
from core.schema import Intent, IntentGroundingItem
from integrations.deepeval import run_intent_grounding

_TOOL = {
    "name": "record_intent",
    "description": "Record the extracted intent of a software requirement.",
    "input_schema": {
        "type": "object",
        "properties": {
            "goal": {"type": "string", "description": "The one-sentence goal of the requirement."},
            "actor": {"type": "string", "description": "Who performs the action (e.g. 'user', 'admin')."},
            "action": {"type": "string", "description": "The action the actor takes."},
            "expected": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Conditions that MUST hold true when the requirement is satisfied.",
            },
            "not_expected": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Conditions that must NOT happen, with the same weight as `expected`. "
                    "Include failure/negative/edge conditions implied by the requirement even "
                    "if it never states them as an explicit rule (e.g. a coupon requirement "
                    "implies a discount must not apply for an invalid or expired code)."
                ),
            },
            "keywords": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Short keywords/phrases to drive keyword-based retrieval of related context.",
            },
        },
        "required": ["goal", "actor", "action", "expected", "not_expected", "keywords"],
    },
}

_SYSTEM = (
    "You are a QA requirement analyst. Given a written requirement, extract its "
    "intent precisely. Always populate `not_expected` with negative conditions "
    "the requirement implies even when it never states them outright — QA "
    "requirement analysis must weigh what should NOT happen as heavily as what "
    "should. Call record_intent exactly once."
)


def extract_intent(requirement_text: str) -> Intent:
    client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_intent"},
        messages=[{"role": "user", "content": f"Requirement:\n\n{requirement_text}"}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_intent":
            return Intent(**block.input)
    raise RuntimeError(f"model did not call record_intent: {json.dumps([b.type for b in resp.content])}")


def annotate_intent_grounding(intent: Intent, raw_requirement_text: str) -> list[IntentGroundingItem]:
    """Is intent.expected/not_expected itself grounded in the requirement
    text, or did extraction infer beyond it? extract_intent() has no ground
    truth to check itself against — the requirement text is that ground
    truth, so this checks intent's own output the same way check_grounding
    later checks the generated test case's output.

    Deliberately NOT a CheckResult and NOT wired into any pass/fail verdict:
    gating on this would just relocate check_coverage's job, not add a new
    one (see core/checks.py's two-stage design). This is surfaced in the
    report as a transparency annotation only — see core/report.py.
    """
    return run_intent_grounding(intent.expected, intent.not_expected, raw_requirement_text)
