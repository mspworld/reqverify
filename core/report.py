"""Report assembly and rendering: console (Section 6 format), JSON, markdown."""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from core.schema import CheckResult, Intent, RequirementChunk, TestCase


class Report(BaseModel):
    requirement_file: str
    intent: Intent | None = None
    chunks: list[RequirementChunk] = []
    test_case: TestCase | None = None
    coverage: CheckResult | None = None
    grounding: list[CheckResult] = []
    injection: CheckResult | None = None

    @property
    def checks(self) -> list[CheckResult]:
        out: list[CheckResult] = []
        if self.coverage is not None:
            out.append(self.coverage)
        out.extend(self.grounding)
        if self.injection is not None:
            out.append(self.injection)
        return out

    @property
    def passed(self) -> bool:
        checks = self.checks
        return bool(checks) and all(c.passed for c in checks)


def build_report(
    requirement_file: str,
    intent: Intent | None = None,
    chunks: list[RequirementChunk] | None = None,
    test_case: TestCase | None = None,
    coverage: CheckResult | None = None,
    grounding: list[CheckResult] | None = None,
    injection: CheckResult | None = None,
) -> Report:
    return Report(
        requirement_file=requirement_file,
        intent=intent,
        chunks=chunks or [],
        test_case=test_case,
        coverage=coverage,
        grounding=grounding or [],
        injection=injection,
    )


def _mark(passed: bool) -> str:
    return "[✓]" if passed else "[✗]"


def _score_str(score: float | None, threshold: float | None = None) -> str:
    if score is None:
        return ""
    return f" {score:.2f} / {threshold:.2f}" if threshold is not None else f" {score:.2f}"


def render_console(report: Report) -> str:
    steps: list[tuple[str, list[str]]] = []

    if report.intent:
        steps.append((
            "Intent",
            [
                f"goal: {report.intent.goal}",
                f"expected: {'; '.join(report.intent.expected)}",
            ],
        ))
    if report.chunks:
        sources = ", ".join(sorted({c.source_file for c in report.chunks}))
        steps.append(("Context", [f"{len(report.chunks)} relevant chunk(s) found ({sources})"]))
    if report.test_case:
        steps.append(("Generate", [f"test case generated ({len(report.test_case.steps)} steps)"]))
    if report.coverage:
        c = report.coverage
        steps.append(("Coverage", [f"{_mark(c.passed)} {c.name}{_score_str(c.score)} — {c.reason}"]))
    if report.grounding:
        steps.append((
            "Grounding",
            [f"{_mark(g.passed)} {g.name}{_score_str(g.score)} — {g.reason}" for g in report.grounding],
        ))
    if report.injection:
        i = report.injection
        steps.append(("Injection", [f"{_mark(i.passed)} {i.reason}"]))

    total = len(steps)
    label_width = 12
    lines = []
    for idx, (label, detail_lines) in enumerate(steps, 1):
        prefix = f"[{idx}/{total}] {label}".ljust(label_width + 8)
        lines.append(f"{prefix}{detail_lines[0]}")
        for extra in detail_lines[1:]:
            lines.append(" " * len(prefix) + extra)

    if report.checks:
        lines.append("")
        lines.append("FINAL: VERIFIED" if report.passed else "FINAL: FAILED")
    return "\n".join(lines)


def render_json(report: Report) -> str:
    return report.model_dump_json(indent=2)


def render_markdown(report: Report) -> str:
    lines = [f"# Report: {report.requirement_file}", ""]
    lines.append(f"**Result: {'VERIFIED' if report.passed else 'FAILED'}**")
    lines.append("")
    if report.intent:
        lines.append("## Intent")
        lines.append(f"- goal: {report.intent.goal}")
        lines.append(f"- actor: {report.intent.actor}")
        lines.append(f"- action: {report.intent.action}")
        lines.append(f"- expected: {report.intent.expected}")
        lines.append(f"- not_expected: {report.intent.not_expected}")
        lines.append("")
    if report.chunks:
        lines.append("## Context")
        for c in report.chunks:
            label = f"{c.source_file}" + (f" / {c.section_title}" if c.section_title else "")
            lines.append(f"- {label}")
        lines.append("")
    if report.test_case:
        lines.append("## Generated test case")
        lines.append("```")
        lines.append(report.test_case.render())
        lines.append("```")
        lines.append("")
    if report.checks:
        lines.append("## Checks")
        for c in report.checks:
            score = f" (score {c.score:.2f})" if c.score is not None else ""
            lines.append(f"### {c.name} — {'PASS' if c.passed else 'FAIL'}{score}")
            lines.append(c.reason)
            lines.append("")
    return "\n".join(lines)


def write_report(report: Report, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(render_json(report))
    path.with_suffix(".md").write_text(render_markdown(report))
