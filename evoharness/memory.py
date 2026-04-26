from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from evoharness.config import EvoConfig


def _read_if_present(path: Path) -> str:
    if path.exists():
        return path.read_text().strip()
    return ""


def _tail_lines(path: Path, count: int) -> list[str]:
    if not path.exists() or count <= 0:
        return []
    lines = path.read_text().splitlines()
    return lines[-count:]


def render_prompt(base_prompt: str, repo: Path, cfg: EvoConfig) -> str:
    if not cfg.memory.enabled:
        return base_prompt

    sections = [base_prompt.rstrip(), "", "# evo-harness context"]

    project_memory = _read_if_present(repo / cfg.memory.project_memory)
    if project_memory:
        sections.extend(["", "## Project memory", project_memory])

    accepted_patterns = _read_if_present(repo / cfg.memory.accepted_patterns)
    if accepted_patterns:
        sections.extend(["", "## Accepted patterns", accepted_patterns])

    rejected_ideas = _tail_lines(repo / cfg.memory.rejected_ideas, cfg.memory.inject_recent_cycles)
    if rejected_ideas:
        sections.extend(["", "## Recent rejected ideas", *rejected_ideas])

    lessons = _tail_lines(repo / cfg.memory.lessons, cfg.memory.inject_recent_cycles)
    if lessons:
        sections.extend(["", "## Recent lessons", *lessons])

    sections.extend(
        [
            "",
            "## Patch scope",
            "Allowed paths:",
            *[f"- {path}" for path in cfg.guards.allowed_paths],
            "Forbidden paths:",
            *[f"- {path}" for path in cfg.guards.forbidden_paths],
        ]
    )
    return "\n".join(sections).rstrip() + "\n"


def append_lesson(repo: Path, cfg: EvoConfig, record: dict[str, Any]) -> None:
    if not cfg.memory.enabled:
        return
    path = repo / cfg.memory.lessons
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
