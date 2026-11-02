"""Local, beginner-friendly execution artifacts for CrewAI runs."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from time import perf_counter
from typing import Any, Iterable


class TraceLevel(str, Enum):
    """Choose how much CrewAI execution detail a run produces."""

    OFF = "off"
    SUMMARY = "summary"
    FULL = "full"

    def __str__(self) -> str:
        return self.value


def timestamped_directory(base_directory: Path, ticker: str) -> Path:
    """Return a unique UTC trace directory path for one ticker run."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return base_directory / f"{ticker}_{timestamp}"


@dataclass
class TraceContext:
    """Own trace paths and application logging for a single crew kickoff."""

    level: TraceLevel
    ticker: str
    directory: Path | None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at_counter: float = field(default_factory=perf_counter)
    logger: logging.Logger = field(init=False)

    def __post_init__(self) -> None:
        self.logger = logging.getLogger(f"scratch_project.run.{id(self)}")
        self.logger.setLevel(logging.DEBUG)
        self.logger.propagate = False
        self.logger.handlers.clear()

        if self.level is TraceLevel.OFF:
            self.logger.addHandler(logging.NullHandler())
            return

        assert self.directory is not None
        self.directory.mkdir(parents=True, exist_ok=True)
        formatter = logging.Formatter(
            "%(asctime)sZ %(levelname)s %(name)s: %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        file_handler = logging.FileHandler(
            self.directory / "learning.log", encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)

    @property
    def crew_log_path(self) -> Path | None:
        """Return the file CrewAI should use for its native full event log."""
        if self.level is not TraceLevel.FULL or self.directory is None:
            return None
        return self.directory / "crewai-events.json"

    @property
    def elapsed_seconds(self) -> float:
        """Return elapsed wall-clock time for the current run."""
        return perf_counter() - self.started_at_counter

    def save_task_outputs(self, task_outputs: Iterable[Any]) -> list[Path]:
        """Persist raw task results in execution order for side-by-side study."""
        if self.level is TraceLevel.OFF or self.directory is None:
            return []

        task_directory = self.directory / "task-outputs"
        task_directory.mkdir(exist_ok=True)
        paths: list[Path] = []
        for index, output in enumerate(task_outputs, start=1):
            description = str(getattr(output, "description", "Unnamed task"))
            agent = str(getattr(output, "agent", "Unknown agent"))
            raw = str(getattr(output, "raw", output))
            filename = f"{index:02d}-{slugify(description)}.md"
            task_path = task_directory / filename
            task_path.write_text(
                f"# Task {index}: {description}\n\n"
                f"Agent: {agent}\n\n"
                "## Raw output\n\n"
                f"{raw.rstrip()}\n",
                encoding="utf-8",
            )
            paths.append(task_path)
        return paths

    def save_summary(self, **details: Any) -> Path | None:
        """Save concise, structured metadata without prompts or credentials."""
        if self.level is TraceLevel.OFF or self.directory is None:
            return None
        summary_path = self.directory / "run-summary.json"
        summary = {
            "ticker": self.ticker,
            "trace_level": self.level.value,
            "started_at": self.started_at.isoformat(),
            "elapsed_seconds": round(self.elapsed_seconds, 3),
            **details,
        }
        summary_path.write_text(
            json.dumps(summary, indent=2, default=str) + "\n", encoding="utf-8"
        )
        return summary_path


def create_trace_context(
    level: TraceLevel, ticker: str, traces_directory: Path
) -> TraceContext:
    """Create a trace context without writes when tracing is off."""
    directory = (
        timestamped_directory(traces_directory, ticker)
        if level is not TraceLevel.OFF
        else None
    )
    return TraceContext(level=level, ticker=ticker, directory=directory)


def slugify(value: str) -> str:
    """Produce a stable, readable filename component from task metadata."""
    characters = [
        character.lower() if character.isalnum() else "-" for character in value
    ]
    slug = "".join(characters).strip("-")
    return slug[:60] or "unnamed-task"
