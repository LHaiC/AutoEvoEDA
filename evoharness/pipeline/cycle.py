from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from evoharness.agents.codex import CodexBackend
from evoharness.config import EvoConfig, load_config
from evoharness.human import review_candidate
from evoharness.memory import append_lesson, render_prompt, render_repair_prompt
from evoharness.pipeline.runner import CommandResult, run_cmd
from evoharness.reports import write_cycle_summary
from evoharness.state import append_history
from evoharness.workspace.git import Candidate, commit_candidate, create_candidate_worktree
from evoharness.workspace.guard import GuardResult, check_patch_scope


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _cycle_dir(repo: Path, cycle: int, candidate_index: int, pool_size: int) -> Path:
    suffix = f"cycle-{cycle:03d}" if pool_size == 1 else f"cycle-{cycle:03d}-cand-{candidate_index:03d}"
    return repo / ".evo" / suffix


def _record_decision(
    repo: Path,
    cycle: int,
    candidate: Candidate,
    decision: str,
    reason: str,
    guard: GuardResult | None,
    cfg: EvoConfig,
) -> dict[str, object]:
    record = {
        "cycle": cycle,
        "candidate_index": candidate.index,
        "candidate": str(candidate.path),
        "branch": candidate.branch,
        "decision": decision,
        "reason": reason,
        "changed_files": guard.changed_files if guard else 0,
        "changed_lines": guard.changed_lines if guard else 0,
    }
    append_history(repo, record)
    append_lesson(repo, cfg, record)
    write_cycle_summary(repo, record)
    return record


def _write_command_result(cycle_dir: Path, result: CommandResult) -> None:
    _write_text(cycle_dir / f"{result.name}.stdout", result.stdout)
    _write_text(cycle_dir / f"{result.name}.stderr", result.stderr)
    _write_text(cycle_dir / f"{result.name}.returncode", f"{result.returncode}\n")


def _check_guard(candidate: Candidate, cfg: EvoConfig, cycle_dir: Path) -> GuardResult:
    guard = check_patch_scope(
        repo=candidate.path,
        allowed_paths=cfg.guards.allowed_paths,
        forbidden_paths=cfg.guards.forbidden_paths,
        max_changed_files=cfg.guards.max_changed_files,
        max_changed_lines=cfg.guards.max_changed_lines,
    )
    _write_text(cycle_dir / "guard.json", json.dumps(asdict(guard), indent=2, sort_keys=True))
    return guard


def _run_pipeline(candidate: Candidate, cfg: EvoConfig, cycle_dir: Path) -> tuple[bool, str, CommandResult | None]:
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
            return False, f"{name}_failed", result
    return True, "all_gates_passed", None


def _repair_prompt(repo: Path, cfg: EvoConfig, failed_gate: str, result: CommandResult) -> str:
    base_prompt = (repo / cfg.repair.prompt_file).read_text()
    return render_repair_prompt(render_prompt(base_prompt, repo, cfg), failed_gate, result.stdout, result.stderr)


def run_one_cycle(
    config_path: Path,
    cfg: EvoConfig,
    cycle: int,
    candidate_index: int = 1,
    pool_size: int = 1,
    human_review: bool = False,
) -> dict[str, object]:
    repo = (config_path.parent / cfg.project.repo).resolve()
    base_prompt = (repo / cfg.agent.prompt_file).read_text()
    prompt = render_prompt(base_prompt, repo, cfg)
    candidate = create_candidate_worktree(
        repo=repo,
        champion_branch=cfg.project.champion_branch,
        worktree_root=(config_path.parent / cfg.workspace.worktree_root).resolve(),
        project_name=cfg.project.name,
        cycle=cycle,
        candidate_index=candidate_index,
        pool_size=pool_size,
    )
    cycle_dir = _cycle_dir(repo, cycle, candidate_index, pool_size)
    agent = CodexBackend(sandbox=cfg.agent.sandbox)

    agent_result = agent.run(prompt=prompt, cwd=candidate.path, timeout_s=cfg.agent.timeout_s)
    _write_text(cycle_dir / "codex.stdout", agent_result.stdout)
    _write_text(cycle_dir / "codex.stderr", agent_result.stderr)
    if not agent_result.ok:
        return _record_decision(repo, cycle, candidate, "reject", "agent_failed", None, cfg)

    guard = _check_guard(candidate, cfg, cycle_dir)
    if not guard.ok:
        return _record_decision(repo, cycle, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg)

    commit_candidate(candidate.path, cycle)
    passed, reason, failed_result = _run_pipeline(candidate, cfg, cycle_dir)

    repair_attempt = 0
    while not passed and cfg.repair.enabled and failed_result and repair_attempt < cfg.repair.max_attempts:
        repair_attempt += 1
        repair = agent.run(_repair_prompt(repo, cfg, reason, failed_result), candidate.path, cfg.agent.timeout_s)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stdout", repair.stdout)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stderr", repair.stderr)
        if not repair.ok:
            return _record_decision(repo, cycle, candidate, "reject", "repair_agent_failed", guard, cfg)
        guard = _check_guard(candidate, cfg, cycle_dir)
        if not guard.ok:
            return _record_decision(repo, cycle, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg)
        commit_candidate(candidate.path, cycle)
        passed, reason, failed_result = _run_pipeline(candidate, cfg, cycle_dir)

    if not passed:
        return _record_decision(repo, cycle, candidate, "reject", reason, guard, cfg)

    if human_review or cfg.human.review_on_accept:
        human_decision = review_candidate(candidate, guard)
        return _record_decision(repo, cycle, candidate, human_decision.decision, human_decision.reason, guard, cfg)

    return _record_decision(repo, cycle, candidate, "accept", "all_gates_passed", guard, cfg)


def run_cycles(config_path: Path, cycles: int, human_review: bool = False) -> None:
    consecutive_rejects = 0
    scheduled_candidates = 0
    cfg = load_config(config_path)
    pool_size = cfg.pool.size if cfg.pool.enabled else 1
    max_cycles = cfg.budget.max_cycles if cfg.budget.max_cycles > 0 else cycles
    stop_cycles = min(cycles, max_cycles)
    for cycle in range(1, stop_cycles + 1):
        for candidate_index in range(1, pool_size + 1):
            if cfg.budget.max_candidates > 0 and scheduled_candidates >= cfg.budget.max_candidates:
                return
            scheduled_candidates += 1
            record = run_one_cycle(config_path, cfg, cycle, candidate_index, pool_size, human_review)
            if record["decision"] == "reject":
                consecutive_rejects += 1
            else:
                consecutive_rejects = 0
            if cfg.human.stop_after_consecutive_rejects > 0 and consecutive_rejects >= cfg.human.stop_after_consecutive_rejects:
                return
