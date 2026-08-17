"""Report assembly and rendering: console, JSON, markdown, and HTML."""
from __future__ import annotations

import html
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


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _stage_box(number: int, label: str, ran: bool, ok: bool | None) -> str:
    """One box in the pipeline strip at the top of the HTML report.
    ok=None means the stage ran but has no pass/fail of its own (Intent,
    Context, Generate); ok=True/False means it's a check with a verdict.
    """
    state = "pending" if not ran else ("neutral" if ok is None else ("pass" if ok else "fail"))
    mark = {"pending": "…", "neutral": "●", "pass": "✓", "fail": "✗"}[state]
    return (
        f'<div class="stage stage-{state}">'
        f'<div class="stage-num">{number}</div>'
        f'<div class="stage-mark">{mark}</div>'
        f'<div class="stage-label">{_esc(label)}</div>'
        f"</div>"
    )


def render_html(report: Report) -> str:
    """A single self-contained HTML page (no external CSS/JS) showing the
    same requirement -> intent -> context -> generate -> check pipeline the
    console output shows, laid out so the whole run is readable at a glance.
    """
    verified = report.passed
    has_checks = bool(report.checks)

    stages = [
        _stage_box(1, "Requirement", True, None),
        _stage_box(2, "Intent", report.intent is not None, None),
        _stage_box(3, "Context", bool(report.chunks), None),
        _stage_box(4, "Generate", report.test_case is not None, None),
        _stage_box(5, "Coverage", report.coverage is not None, report.coverage.passed if report.coverage else None),
        _stage_box(
            6, "Grounding", bool(report.grounding),
            all(g.passed for g in report.grounding) if report.grounding else None,
        ),
        _stage_box(7, "Injection", report.injection is not None, report.injection.passed if report.injection else None),
    ]

    sections = []

    if report.intent:
        i = report.intent
        sections.append(f"""
        <section class="card">
          <h2>2 &middot; Intent</h2>
          <p class="muted">What the model understood the requirement to be asking for.</p>
          <dl>
            <dt>Goal</dt><dd>{_esc(i.goal)}</dd>
            <dt>Actor</dt><dd>{_esc(i.actor)}</dd>
            <dt>Action</dt><dd>{_esc(i.action)}</dd>
          </dl>
          <div class="two-col">
            <div>
              <h3>Expected</h3>
              <ul class="chips chips-pos">{"".join(f"<li>{_esc(e)}</li>" for e in i.expected)}</ul>
            </div>
            <div>
              <h3>Must NOT happen</h3>
              <ul class="chips chips-neg">{"".join(f"<li>{_esc(e)}</li>" for e in i.not_expected)}</ul>
            </div>
          </div>
        </section>""")

    if report.chunks:
        rows = "".join(
            f"<li><code>{_esc(c.source_file)}</code>"
            + (f" &middot; {_esc(c.section_title)}" if c.section_title else "")
            + "</li>"
            for c in report.chunks
        )
        sections.append(f"""
        <section class="card">
          <h2>3 &middot; Context</h2>
          <p class="muted">Chunks retrieved from requirements/ and context/ for this intent's keywords.</p>
          <ul class="plain-list">{rows}</ul>
        </section>""")

    if report.test_case:
        tc = report.test_case
        steps = "".join(f"<li>{_esc(s)}</li>" for s in tc.steps)
        pre = "".join(f"<li>{_esc(p)}</li>" for p in tc.preconditions)
        sections.append(f"""
        <section class="card">
          <h2>4 &middot; Generated test case</h2>
          <p class="muted">Written using only the retrieved context above — nothing else.</p>
          <h3>Preconditions</h3>
          <ul class="plain-list">{pre}</ul>
          <h3>Steps</h3>
          <ol class="plain-list">{steps}</ol>
          <h3>Expected result</h3>
          <p>{_esc(tc.expected_result)}</p>
        </section>""")

    def check_card(c: CheckResult, step_no: str) -> str:
        badge = "pass" if c.passed else "fail"
        score = f'<span class="score">{c.score:.2f}</span>' if c.score is not None else ""
        return f"""
          <div class="check check-{badge}">
            <div class="check-head">
              <span class="badge badge-{badge}">{"PASS" if c.passed else "FAIL"}</span>
              <strong>{_esc(c.name)}</strong>
              {score}
            </div>
            <p class="reason">{_esc(c.reason)}</p>
          </div>"""

    if has_checks:
        check_html = []
        if report.coverage:
            check_html.append(check_card(report.coverage, "5"))
        for g in report.grounding:
            check_html.append(check_card(g, "6"))
        if report.injection:
            check_html.append(check_card(report.injection, "7"))
        sections.append(f"""
        <section class="card">
          <h2>5&ndash;7 &middot; Checks</h2>
          <p class="muted">Coverage (did it test what was asked), grounding (did it invent anything), injection resistance (did it obey embedded instructions instead of describing them).</p>
          {"".join(check_html)}
        </section>""")

    verdict_class = "pass" if verified else "fail"
    verdict_text = "VERIFIED" if verified else "FAILED"

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>reqverify report — {_esc(report.requirement_file)}</title>
<style>
  :root {{
    --bg: #0f1117; --panel: #171a24; --border: #2a2e3d; --text: #e6e8ef; --muted: #8b90a3;
    --pass: #35d07f; --fail: #ff5d6c; --accent: #8a63d2;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 20px 60px; background: var(--bg); color: var(--text);
    font: 15px/1.55 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 880px; margin: 0 auto; }}
  header {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 8px; }}
  h1 {{ font-size: 20px; margin: 0; }}
  h1 code {{ color: var(--accent); }}
  .verdict {{ font-weight: 700; letter-spacing: 0.04em; padding: 6px 16px; border-radius: 999px; font-size: 13px; }}
  .verdict.pass {{ background: rgba(53,208,127,0.15); color: var(--pass); border: 1px solid var(--pass); }}
  .verdict.fail {{ background: rgba(255,93,108,0.15); color: var(--fail); border: 1px solid var(--fail); }}
  .pipeline {{ display: flex; gap: 6px; margin: 28px 0 36px; overflow-x: auto; }}
  .stage {{ flex: 1; min-width: 90px; text-align: center; padding: 10px 6px; border-radius: 10px; border: 1px solid var(--border); background: var(--panel); }}
  .stage-num {{ font-size: 11px; color: var(--muted); }}
  .stage-mark {{ font-size: 20px; margin: 4px 0; }}
  .stage-label {{ font-size: 12px; color: var(--muted); }}
  .stage-pass {{ border-color: var(--pass); }} .stage-pass .stage-mark {{ color: var(--pass); }}
  .stage-fail {{ border-color: var(--fail); }} .stage-fail .stage-mark {{ color: var(--fail); }}
  .stage-neutral .stage-mark {{ color: var(--accent); }}
  .stage-pending {{ opacity: 0.4; }}
  .card {{ background: var(--panel); border: 1px solid var(--border); border-radius: 12px; padding: 20px 24px; margin-bottom: 18px; }}
  .card h2 {{ margin: 0 0 4px; font-size: 15px; }}
  .card h3 {{ font-size: 13px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.04em; margin: 16px 0 6px; }}
  .muted {{ color: var(--muted); margin: 0 0 12px; font-size: 13px; }}
  dl {{ display: grid; grid-template-columns: 90px 1fr; gap: 6px 12px; margin: 0; }}
  dt {{ color: var(--muted); font-size: 13px; }} dd {{ margin: 0; }}
  .two-col {{ display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-top: 10px; }}
  .chips {{ list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }}
  .chips li {{ padding: 6px 10px; border-radius: 6px; font-size: 13px; }}
  .chips-pos li {{ background: rgba(53,208,127,0.10); border-left: 3px solid var(--pass); }}
  .chips-neg li {{ background: rgba(255,93,108,0.10); border-left: 3px solid var(--fail); }}
  .plain-list {{ margin: 0; padding-left: 20px; }}
  .plain-list li {{ margin-bottom: 4px; }}
  .check {{ border-radius: 8px; padding: 12px 14px; margin-top: 10px; border: 1px solid var(--border); }}
  .check-head {{ display: flex; align-items: center; gap: 10px; }}
  .badge {{ font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 999px; }}
  .badge-pass {{ background: rgba(53,208,127,0.18); color: var(--pass); }}
  .badge-fail {{ background: rgba(255,93,108,0.18); color: var(--fail); }}
  .score {{ margin-left: auto; color: var(--muted); font-variant-numeric: tabular-nums; }}
  .reason {{ margin: 8px 0 0; color: var(--muted); font-size: 13.5px; }}
  code {{ background: rgba(255,255,255,0.06); padding: 1px 6px; border-radius: 4px; font-size: 13px; }}
  footer {{ text-align: center; color: var(--muted); font-size: 12px; margin-top: 30px; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <h1>reqverify report &middot; <code>{_esc(report.requirement_file)}</code></h1>
      {f'<span class="verdict {verdict_class}">FINAL: {verdict_text}</span>' if has_checks else ''}
    </header>
    <div class="pipeline">{"".join(stages)}</div>
    {"".join(sections)}
    <footer>Generated by reqverify &mdash; requirement in, intent, context, generated test case, checks, report.</footer>
  </div>
</body>
</html>
"""


def write_report(report: Report, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.with_suffix(".json").write_text(render_json(report))
    path.with_suffix(".md").write_text(render_markdown(report))
    path.with_suffix(".html").write_text(render_html(report))
