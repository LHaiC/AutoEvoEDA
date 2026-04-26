from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from evoharness.config import EvoConfig
from evoharness.artifacts import read_agent_memory, recent_inbox


def _read_if_present(path: Path) -> str:
    if path.exists():
        return path.read_text().strip()
    return ""


def _tail_lines(path: Path, count: int) -> list[str]:
    if not path.exists() or count <= 0:
        return []
    lines = path.read_text().splitlines()
    return lines[-count:]


def _role_section(repo: Path, title: str, path: str, base_prompt: str) -> list[str]:
    if not path:
        return []
    content = _read_if_present(repo / path)
    if content and content != base_prompt.strip():
        return ["", f"## {title}", content]
    return []


def render_prompt(base_prompt: str, repo: Path, cfg: EvoConfig) -> str:
    sections = [base_prompt.rstrip()]
    sections.extend(_role_section(repo, "Planning role guidance", cfg.roles.planner_prompt, base_prompt))
    sections.extend(_role_section(repo, "Coding role guidance", cfg.roles.coder_prompt, base_prompt))
    sections.extend(_role_section(repo, "Reviewer advisory guidance", cfg.roles.reviewer_prompt, base_prompt))

    if cfg.memory.enabled:
        sections.extend(["", "# evo-harness context"])
        for title, path in [
            ("Project memory", cfg.memory.project_memory),
            ("Rulebase", cfg.rulebase.path),
            ("Accepted patterns", cfg.memory.accepted_patterns),
        ]:
            content = _read_if_present(repo / path)
            if content:
                sections.extend(["", f"## {title}", content])

        rejected_ideas = _tail_lines(repo / cfg.memory.rejected_ideas, cfg.memory.inject_recent_cycles)
        if rejected_ideas:
            sections.extend(["", "## Recent rejected ideas", *rejected_ideas])

        lessons = _tail_lines(repo / cfg.memory.lessons, cfg.memory.inject_recent_cycles)
        if lessons:
            sections.extend(["", "## Recent lessons", *lessons])

        inbox = recent_inbox(repo, cfg.memory.inject_recent_cycles)
        if inbox:
            sections.extend(["", "## Recent human session comments", *[item["text"] for item in inbox]])

        roadmap = _read_if_present(repo / ".evo" / "roadmap.md")
        if roadmap:
            sections.extend(["", "## Evolution roadmap", roadmap])

        code_index = _read_if_present(repo / ".evo" / "memory" / "code" / "index.md")
        if code_index:
            sections.extend(["", "## Code understanding index", code_index])

        for title, agent_id in [
            ("Planner agent memory", cfg.agents.planner.session_id),
            ("Coder agent memory", cfg.agents.coder.session_id),
            ("Reviewer agent memory", cfg.agents.reviewer.session_id),
        ]:
            agent_memory = read_agent_memory(repo, agent_id)
            if agent_memory:
                sections.extend(["", f"## {title}", agent_memory])

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


def render_repair_prompt(base_prompt: str, failed_gate: str, stdout: str, stderr: str) -> str:
    return "\n".join(
        [
            base_prompt.rstrip(),
            "",
            "# Repair task",
            f"The previous candidate failed gate: {failed_gate}",
            "Repair the candidate without weakening guards, scripts, or correctness checks.",
            "",
            "## Failed gate stdout",
            stdout.rstrip(),
            "",
            "## Failed gate stderr",
            stderr.rstrip(),
            "",
        ]
    )


def append_lesson(repo: Path, cfg: EvoConfig, record: dict[str, Any]) -> None:
    if not cfg.memory.enabled:
        return
    path = repo / cfg.memory.lessons
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
