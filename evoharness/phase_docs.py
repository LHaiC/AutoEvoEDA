from __future__ import annotations

from pathlib import Path
from typing import Any

from evoharness.config import EvoConfig
from evoharness.events import run_dir
from evoharness.pipeline.runner import CommandResult
from evoharness.workspace.git import Candidate, changed_files, git
from evoharness.workspace.guard import GuardResult


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_context_doc(repo: Path, run_id_value: str, config_path: Path, cfg: EvoConfig, candidate: Candidate) -> None:
    _write(
        run_dir(repo, run_id_value) / "00_context.md",
        "\n".join(
            [
                f"# Context: {run_id_value}",
                "",
                f"- Config: `{config_path}`",
                f"- Branch: `{candidate.branch}`",
                f"- Candidate worktree: `{candidate.path}`",
                f"- Champion branch: `{cfg.project.champion_branch}`",
                "",
                "## Allowed paths",
                *[f"- {path}" for path in cfg.guards.allowed_paths],
                "",
                "## Forbidden paths",
                *[f"- {path}" for path in cfg.guards.forbidden_paths],
                "",
            ]
        ),
    )


def write_propose_doc(repo: Path, run_id_value: str, prompt: str) -> None:
    _write(run_dir(repo, run_id_value) / "01_propose.md", "# Proposal Prompt\n\n```text\n" + prompt + "\n```\n")


def write_implement_doc(repo: Path, run_id_value: str, candidate: Candidate, guard: GuardResult) -> None:
    patch_path = run_dir(repo, run_id_value) / "patch.diff"
    _write(patch_path, git(["diff"], cwd=candidate.path) + "\n")
    files = changed_files(candidate.path)
    lines = [
        f"# Implementation: {run_id_value}",
        "",
        f"- Guard: `{guard.reason}`",
        f"- Changed files: {guard.changed_files}",
        f"- Changed lines: {guard.changed_lines}",
        f"- Patch: `patch.diff`",
        "",
        "## Files",
        *[f"- `{path}`" for path in files],
        "",
    ]
    _write(run_dir(repo, run_id_value) / "02_implement.md", "\n".join(lines))


def write_benchmark_doc(repo: Path, run_id_value: str, results: list[CommandResult]) -> None:
    lines = [f"# Benchmark: {run_id_value}", ""]
    for result in results:
        lines.extend(
            [
                f"## {result.name}",
                "",
                f"- Return code: {result.returncode}",
                f"- Passed: {result.ok}",
                f"- Stdout: `.evo/runs/{run_id_value}/{result.name}.stdout`",
                f"- Stderr: `.evo/runs/{run_id_value}/{result.name}.stderr`",
                "",
            ]
        )
    _write(run_dir(repo, run_id_value) / "03_benchmark.md", "\n".join(lines))


def write_decision_doc(repo: Path, run_id_value: str, record: dict[str, Any]) -> None:
    lines = [
        f"# Decision: {run_id_value}",
        "",
        f"- Decision: `{record['decision']}`",
        f"- Reason: `{record['reason']}`",
        f"- Branch: `{record['branch']}`",
        f"- Candidate: `{record['candidate']}`",
    ]
    if record.get("human_comment"):
        lines.extend([f"- Human comment: {record['human_comment']}"])
    if record.get("next_hint"):
        lines.extend([f"- Next hint: {record['next_hint']}"])
    evaluator_results = record.get("evaluator_results", {})
    if isinstance(evaluator_results, dict) and evaluator_results:
        lines.extend(["", "## Evaluator Results", ""])
        lines.extend([f"- `{name}`" for name in sorted(evaluator_results)])
    lines.append("")
    _write(run_dir(repo, run_id_value) / "04_decision.md", "\n".join(lines))
