from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from evoharness.agents.codex import CodexBackend
from evoharness.config import load_config
from evoharness.pipeline.runner import CommandResult, run_cmd
from evoharness.state import append_history
from evoharness.workspace.git import Candidate, create_candidate_worktree
from evoharness.workspace.guard import GuardResult, check_patch_scope


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _record_decision(
    repo: Path,
    cycle: int,
    candidate: Candidate,
    decision: str,
    reason: str,
    guard: GuardResult | None,
) -> None:
    append_history(
        repo,
        {
            "cycle": cycle,
            "candidate": str(candidate.path),
            "branch": candidate.branch,
            "decision": decision,
            "reason": reason,
            "changed_files": guard.changed_files if guard else 0,
            "changed_lines": guard.changed_lines if guard else 0,
        },
    )


def _write_command_result(cycle_dir: Path, result: CommandResult) -> None:
    _write_text(cycle_dir / f"{result.name}.stdout", result.stdout)
    _write_text(cycle_dir / f"{result.name}.stderr", result.stderr)
    _write_text(cycle_dir / f"{result.name}.returncode", f"{result.returncode}\n")


def run_one_cycle(config_path: Path, cycle: int) -> None:
    cfg = load_config(config_path)
    repo = (config_path.parent / cfg.project.repo).resolve()
    prompt = (repo / cfg.agent.prompt_file).read_text()
    candidate = create_candidate_worktree(
        repo=repo,
        champion_branch=cfg.project.champion_branch,
        worktree_root=(config_path.parent / cfg.workspace.worktree_root).resolve(),
        project_name=cfg.project.name,
        cycle=cycle,
    )
    cycle_dir = repo / ".evo" / f"cycle-{cycle:03d}"

    agent_result = CodexBackend(sandbox=cfg.agent.sandbox).run(
        prompt=prompt,
        cwd=candidate.path,
        timeout_s=cfg.agent.timeout_s,
    )
    _write_text(cycle_dir / "codex.stdout", agent_result.stdout)
    _write_text(cycle_dir / "codex.stderr", agent_result.stderr)
    if not agent_result.ok:
        _record_decision(repo, cycle, candidate, "reject", "agent_failed", None)
        return

    guard = check_patch_scope(
        repo=candidate.path,
        allowed_paths=cfg.guards.allowed_paths,
        forbidden_paths=cfg.guards.forbidden_paths,
        max_changed_files=cfg.guards.max_changed_files,
        max_changed_lines=cfg.guards.max_changed_lines,
    )
    _write_text(cycle_dir / "guard.json", json.dumps(asdict(guard), indent=2, sort_keys=True))
    if not guard.ok:
        _record_decision(repo, cycle, candidate, "reject", f"guard_failed:{guard.reason}", guard)
        return

    for name, cmd in [
        ("build", cfg.pipeline.build),
        ("regression", cfg.pipeline.regression),
        ("compare_regression", cfg.pipeline.compare_regression),
        ("perf", cfg.pipeline.perf),
        ("reward", cfg.pipeline.reward),
    ]:
        result = run_cmd(name=name, cmd=cmd, cwd=candidate.path)
        _write_command_result(cycle_dir, result)
        if not result.ok:
            _record_decision(repo, cycle, candidate, "reject", f"{name}_failed", guard)
            return

    _record_decision(repo, cycle, candidate, "accept", "all_gates_passed", guard)


def run_cycles(config_path: Path, cycles: int) -> None:
    for cycle in range(1, cycles + 1):
        run_one_cycle(config_path=config_path, cycle=cycle)
