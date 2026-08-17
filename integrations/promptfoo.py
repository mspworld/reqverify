"""Promptfoo custom provider: wraps core.generate.generate_test_case directly
so every adversarial variant Promptfoo's red-team engine produces runs
against the real generation pipeline — never a stub. Same mechanism as
core.checks.check_injection_resistance's in-loop attack, just automated
across many attack phrasings instead of one fixed file.
"""
from __future__ import annotations

from core.generate import generate_test_case
from core.schema import Intent, RequirementChunk

# Fixed across every adversarial variant on purpose: the attack surface is
# the requirement *text* (chunk.text below), not the intent. Holding intent
# constant isolates whether injected content in the retrieved chunk alone
# can hijack generation.
BASE_INTENT = Intent(
    goal="Reset a forgotten or compromised password via an emailed link.",
    actor="user",
    action="requests a password reset and follows the emailed link",
    expected=[
        "user receives a reset link via email",
        "new password is saved",
        "old password stops working after reset",
    ],
    not_expected=[
        "reset link works after the password has already been changed",
        "old password still works after reset",
    ],
    keywords=["password reset", "email link", "authentication"],
)


def call_api(prompt: str, options: dict, context: dict) -> dict:
    """Promptfoo's Python provider contract: given the (possibly adversarial)
    prompt text, return {"output": <string Promptfoo will grade>}.
    """
    chunk = RequirementChunk(
        source_file="promptfoo_variant.md",
        section_title="Reset password via email link",
        text=prompt,
    )
    test_case = generate_test_case(BASE_INTENT, chunk)
    return {"output": test_case.render()}
