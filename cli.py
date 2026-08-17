# closed loop: requirement -> intent -> context -> generate -> check -> report
from __future__ import annotations

import sys
from pathlib import Path

import click

from core.checks import check_coverage, check_grounding, check_injection_resistance
from core.context import chunk_file, load_context, retrieve
from core.generate import generate_test_case
from core.intent import extract_intent
from core.report import Report, render_console, write_report
from core.schema import Intent, RequirementChunk, TestCase

CONTEXT_DIRS = ["requirements", "context"]


def _select_target_text(requirement_file: str, task: str | None) -> str:
    """Default: whole file, or its first ## section if it has any (Section 3).
    --task <substring> picks a specific section by title instead.
    """
    chunks = chunk_file(Path(requirement_file))
    if not chunks:
        return Path(requirement_file).read_text()
    if task:
        for c in chunks:
            if c.section_title and task.lower() in c.section_title.lower():
                return c.text
        raise click.ClickException(f"no section matching --task {task!r} found in {requirement_file}")
    return chunks[0].text


def _run_intent(requirement_file: str, task: str | None) -> Intent:
    return extract_intent(_select_target_text(requirement_file, task))


def _run_context(intent: Intent) -> list[RequirementChunk]:
    retriever = load_context(CONTEXT_DIRS)
    return retrieve(retriever, " ".join(intent.keywords), k=3)


def _run_generate(intent: Intent, chunk: RequirementChunk) -> TestCase:
    return generate_test_case(intent, chunk)


def _finish(report: Report, report_out: str | None, gate_on_checks: bool) -> None:
    click.echo(render_console(report))
    if report_out:
        write_report(report, report_out)
        click.echo(f"\nWrote {report_out}.json, {report_out}.md, and {report_out}.html")
    sys.exit((0 if report.passed else 1) if gate_on_checks else 0)


_task_option = click.option("--task", default=None, help="Match a specific ## section by title.")
_report_out_option = click.option(
    "--report-out", default=None,
    help="Write <path>.json, <path>.md, and <path>.html (open the .html in any browser).",
)


@click.group()
def main() -> None:
    pass


@main.command()
@click.argument("requirement_file")
@_task_option
def intent(requirement_file: str, task: str | None) -> None:
    result = _run_intent(requirement_file, task)
    report = Report(requirement_file=requirement_file, intent=result)
    _finish(report, None, gate_on_checks=False)


@main.command()
@click.argument("requirement_file")
@_task_option
@_report_out_option
def coverage(requirement_file: str, task: str | None, report_out: str | None) -> None:
    the_intent = _run_intent(requirement_file, task)
    chunks = _run_context(the_intent)
    test_case = _run_generate(the_intent, chunks[0])
    result = check_coverage(test_case, the_intent, chunks[0])
    report = Report(
        requirement_file=requirement_file, intent=the_intent, chunks=chunks,
        test_case=test_case, coverage=result,
    )
    _finish(report, report_out, gate_on_checks=True)


@main.command()
@click.argument("requirement_file")
@_task_option
@_report_out_option
def grounding(requirement_file: str, task: str | None, report_out: str | None) -> None:
    the_intent = _run_intent(requirement_file, task)
    chunks = _run_context(the_intent)
    test_case = _run_generate(the_intent, chunks[0])
    results = check_grounding(test_case, " ".join(the_intent.keywords), chunks)
    report = Report(
        requirement_file=requirement_file, intent=the_intent, chunks=chunks,
        test_case=test_case, grounding=results,
    )
    _finish(report, report_out, gate_on_checks=True)


@main.command()
@click.argument("requirement_file")
@_task_option
@_report_out_option
def injection(requirement_file: str, task: str | None, report_out: str | None) -> None:
    the_intent = _run_intent(requirement_file, task)
    chunks = _run_context(the_intent)
    test_case = _run_generate(the_intent, chunks[0])
    result = check_injection_resistance(test_case, chunks[0])
    report = Report(
        requirement_file=requirement_file, intent=the_intent, chunks=chunks,
        test_case=test_case, injection=result,
    )
    _finish(report, report_out, gate_on_checks=True)


@main.command()
@click.argument("requirement_file")
@_task_option
@_report_out_option
def evaluate(requirement_file: str, task: str | None, report_out: str | None) -> None:
    the_intent = _run_intent(requirement_file, task)
    chunks = _run_context(the_intent)
    test_case = _run_generate(the_intent, chunks[0])
    cov = check_coverage(test_case, the_intent, chunks[0])
    ground = check_grounding(test_case, " ".join(the_intent.keywords), chunks)
    inj = check_injection_resistance(test_case, chunks[0])
    report = Report(
        requirement_file=requirement_file, intent=the_intent, chunks=chunks,
        test_case=test_case, coverage=cov, grounding=ground, injection=inj,
    )
    _finish(report, report_out, gate_on_checks=True)


if __name__ == "__main__":
    main()
