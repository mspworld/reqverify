"""Pydantic models shared by every stage of the closed loop."""
from __future__ import annotations

from pydantic import BaseModel


class RequirementChunk(BaseModel):
    source_file: str
    section_title: str | None = None
    text: str


class Intent(BaseModel):
    goal: str
    actor: str
    action: str
    expected: list[str]
    # not optional: negative/should-not-happen conditions matter as much as
    # positive ones, or check_coverage silently misses one-sided test generation.
    not_expected: list[str]
    keywords: list[str]


class TestCase(BaseModel):
    __test__ = False  # not a pytest test class despite the name

    preconditions: list[str]
    steps: list[str]
    expected_result: str
    source_chunk: RequirementChunk

    def render(self) -> str:
        lines = ["Preconditions:"]
        lines += [f"- {p}" for p in self.preconditions]
        lines.append("Steps:")
        lines += [f"{i}. {s}" for i, s in enumerate(self.steps, 1)]
        lines.append(f"Expected result: {self.expected_result}")
        return "\n".join(lines)


class CheckResult(BaseModel):
    name: str
    passed: bool
    score: float | None = None
    reason: str


class IntentGroundingItem(BaseModel):
    """One claim drawn from Intent.expected/not_expected, judged against the
    raw requirement text. Not a CheckResult on purpose — see
    core/intent.py::annotate_intent_grounding for why this doesn't gate
    anything.
    """

    claim: str
    supported: bool
    reason: str
