"""One Claude call: turn an Intent + a retrieved RequirementChunk into a TestCase.

Must only use what's in chunk.text — this is the constraint check_grounding's
FaithfulnessMetric later verifies. intent guides structure (what to test for),
chunk.text is the sole source of factual content.
"""
from __future__ import annotations

import anthropic

from core.config import ANTHROPIC_MODEL, get_anthropic_api_key
from core.schema import Intent, RequirementChunk, TestCase

_TOOL = {
    "name": "record_test_case",
    "description": "Record a structured QA test case.",
    "input_schema": {
        "type": "object",
        "properties": {
            "preconditions": {"type": "array", "items": {"type": "string"}},
            "steps": {"type": "array", "items": {"type": "string"}},
            "expected_result": {"type": "string"},
        },
        "required": ["preconditions", "steps", "expected_result"],
    },
}

_SYSTEM = (
    "You are a QA test case writer. You will be given the intent behind a "
    "requirement and the exact requirement text (context). Write a test case "
    "using ONLY facts stated in the requirement text — do not invent behavior, "
    "fields, error messages, or rules the text doesn't state. Use the intent's "
    "`expected` and `not_expected` items as a guide for what to check, but only "
    "assert what the requirement text actually supports. If the text doesn't "
    "describe a negative/failure condition, don't invent one for it. Call "
    "record_test_case exactly once."
)


def generate_test_case(intent: Intent, chunk: RequirementChunk) -> TestCase:
    client = anthropic.Anthropic(api_key=get_anthropic_api_key())
    user_content = (
        f"Intent:\n"
        f"goal: {intent.goal}\n"
        f"actor: {intent.actor}\n"
        f"action: {intent.action}\n"
        f"expected: {intent.expected}\n"
        f"not_expected: {intent.not_expected}\n\n"
        f"Requirement text (the only source of facts, from {chunk.source_file}"
        f"{' / ' + chunk.section_title if chunk.section_title else ''}):\n\n"
        f"{chunk.text}"
    )
    resp = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=1024,
        system=_SYSTEM,
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "record_test_case"},
        messages=[{"role": "user", "content": user_content}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_test_case":
            return TestCase(**block.input, source_chunk=chunk)
    raise RuntimeError("model did not call record_test_case")
