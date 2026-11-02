#!/usr/bin/env python
"""Command-line entry point for generating one stock brief."""

from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from scratch_project.crew import ScratchProject
from scratch_project.observability import TraceLevel, create_trace_context

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PREFERENCES_PATH = PROJECT_ROOT / "knowledge" / "user_preference.txt"
REPORTS_DIRECTORY = PROJECT_ROOT / "reports"
TRACES_DIRECTORY = PROJECT_ROOT / "traces"


def configure_provider_credentials() -> None:
    """Configure provider-specific credentials required by LiteLLM."""
    model_name = (
        os.getenv("MODEL")
        or os.getenv("MODEL_NAME")
        or os.getenv("OPENAI_MODEL_NAME", "")
    )
    if model_name.startswith("minimax/") and not os.getenv("MINIMAX_API_KEY"):
        openai_api_key = os.getenv("OPENAI_API_KEY")
        if openai_api_key:
            os.environ["MINIMAX_API_KEY"] = openai_api_key


def normalize_ticker(value: str) -> str:
    """Return a normalized ticker or raise ValueError for invalid input."""
    ticker = value.strip().upper()
    if not ticker or len(ticker) > 15:
        raise ValueError("Ticker must contain between 1 and 15 characters.")
    is_valid = all(character.isalnum() or character in ".-" for character in ticker)
    if not is_valid:
        raise ValueError(
            "Ticker may contain only letters, numbers, periods, and hyphens."
        )
    return ticker


def load_user_preferences(path: Path | None = None) -> str:
    """Load optional report preferences without requiring a preference file."""
    path = PREFERENCES_PATH if path is None else path
    if not path.is_file():
        return "Keep the report concise, clear, and beginner-friendly."
    return path.read_text(encoding="utf-8").strip()


def save_report(
    report: str,
    ticker: str,
    reports_directory: Path = REPORTS_DIRECTORY,
) -> Path:
    """Persist the final brief as a timestamped Markdown file."""
    reports_directory.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = reports_directory / f"{ticker}_{timestamp}.md"
    report_path.write_text(report.rstrip() + "\n", encoding="utf-8")
    return report_path


def selected_model_name() -> str:
    """Return the configured model identifier without exposing credentials."""
    return (
        os.getenv("MODEL")
        or os.getenv("MODEL_NAME")
        or os.getenv("OPENAI_MODEL_NAME")
        or "provider default"
    )


def run(
    ticker: str,
    trace_level: TraceLevel = TraceLevel.FULL,
    traces_directory: Path = TRACES_DIRECTORY,
) -> tuple[str, Path]:
    """Run the crew for one ticker and save the final brief."""
    trace = create_trace_context(trace_level, ticker, traces_directory)
    inputs = {
        "ticker": ticker,
        "user_preferences": load_user_preferences(),
    }
    trace.logger.info(
        "Starting CrewAI run for ticker=%s model=%s trace=%s",
        ticker,
        selected_model_name(),
        trace_level.value,
    )
    project = ScratchProject()
    project.trace_level = trace_level
    project.crew_log_path = trace.crew_log_path
    try:
        result = project.crew().kickoff(inputs=inputs)
    except Exception:
        trace.logger.exception("CrewAI run failed for ticker=%s", ticker)
        trace.save_summary(status="failed")
        raise

    report = str(result)
    task_outputs = getattr(result, "tasks_output", [])
    task_paths = trace.save_task_outputs(task_outputs)
    report_path = save_report(report, ticker, REPORTS_DIRECTORY)
    trace.save_summary(
        status="completed",
        model=selected_model_name(),
        report_path=str(report_path),
        report_characters=len(report),
        task_count=len(task_paths),
        token_usage=getattr(result, "token_usage", None),
    )
    trace.logger.info(
        "Completed CrewAI run for ticker=%s in %.2fs; report=%s; tasks=%d",
        ticker,
        trace.elapsed_seconds,
        report_path,
        len(task_paths),
    )
    return report, report_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an evidence-aware stock brief with CrewAI."
    )
    parser.add_argument("ticker", help="Stock ticker, for example NVDA or BRK-B.")
    parser.add_argument(
        "--trace",
        choices=list(TraceLevel),
        default=TraceLevel.FULL,
        type=TraceLevel,
        help=(
            "Save CrewAI learning artifacts: off, summary, or full " "(default: full)."
        ),
    )
    parser.add_argument(
        "--trace-dir",
        type=Path,
        default=TRACES_DIRECTORY,
        help="Directory for local learning traces (default: traces).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    load_dotenv(PROJECT_ROOT / ".env")
    configure_provider_credentials()
    arguments = build_parser().parse_args(argv)

    try:
        ticker = normalize_ticker(arguments.ticker)
    except ValueError as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2

    try:
        report, report_path = run(
            ticker,
            trace_level=arguments.trace,
            traces_directory=arguments.trace_dir,
        )
    except OSError as error:
        print(f"File error: {error}", file=sys.stderr)
        return 1
    except Exception as error:
        print(f"Unable to generate report: {error}", file=sys.stderr)
        return 1

    print(report)
    print(f"\nSaved report: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
