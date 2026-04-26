from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from evoharness.agent_state import write_agent_exchange
from evoharness.agents.codex import CodexBackend
from evoharness.config import EvoConfig, load_config
from evoharness.events import append_event, run_dir, run_id
from evoharness.evaluator_results import (
    EvaluatorSnapshot,
    collect_evaluator_results,
    write_evaluator_results,
)
from evoharness.human import review_candidate
from evoharness.memory import append_lesson, render_prompt, render_repair_prompt
from evoharness.phase_docs import write_benchmark_doc, write_context_doc, write_decision_doc, write_implement_doc, write_propose_doc
from evoharness.pipeline.runner import CommandResult, run_cmd
from evoharness.reports import write_cycle_summary, write_project_indexes
from evoharness.session import assert_not_paused, ensure_session
from evoharness.state import append_history
from evoharness.workspace.git import Candidate, commit_candidate, create_candidate_worktree
from evoharness.workspace.guard import GuardResult, check_patch_scope


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _cycle_dir(repo: Path, run_id_value: str) -> Path:
    return repo / ".evo" / run_id_value


def _event(repo: Path, run_id_value: str, event_type: str, candidate: Candidate, payload: dict[str, object]) -> None:
    append_event(repo, run_id_value, event_type, candidate.cycle, candidate.index, candidate.branch, payload)


def _record_decision(
    repo: Path,
    run_id_value: str,
    candidate: Candidate,
    decision: str,
    reason: str,
    guard: GuardResult | None,
    cfg: EvoConfig,
    human_comment: str = "",
    next_hint: str = "",
    evaluator_results: dict[str, object] | None = None,
) -> dict[str, object]:
    record = {
        "cycle": candidate.cycle,
        "candidate_index": candidate.index,
        "run_id": run_id_value,
        "candidate": str(candidate.path),
        "branch": candidate.branch,
        "decision": decision,
        "reason": reason,
        "changed_files": guard.changed_files if guard else 0,
        "changed_lines": guard.changed_lines if guard else 0,
        "human_comment": human_comment,
        "next_hint": next_hint,
        "evaluator_results": evaluator_results or {},
    }
    append_history(repo, record)
    append_lesson(repo, cfg, record)
    write_cycle_summary(repo, record)
    write_decision_doc(repo, run_id_value, record)
    _event(repo, run_id_value, "decision_recorded", candidate, {"decision": decision, "reason": reason})
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


def _run_pipeline(candidate: Candidate, cfg: EvoConfig, cycle_dir: Path, repo: Path, run_id_value: str) -> tuple[bool, str, CommandResult | None, list[CommandResult]]:
    results = []
    for name, cmd in [
        ("build", cfg.pipeline.build),
        ("regression", cfg.pipeline.regression),
        ("compare_regression", cfg.pipeline.compare_regression),
        ("perf", cfg.pipeline.perf),
        ("reward", cfg.pipeline.reward),
    ]:
        result = run_cmd(name=name, cmd=cmd, cwd=candidate.path)
        results.append(result)
        _write_command_result(cycle_dir, result)
        _event(repo, run_id_value, "gate_finished", candidate, {"gate": name, "ok": result.ok, "returncode": result.returncode})
        if not result.ok:
            write_benchmark_doc(repo, run_id_value, results)
            return False, f"{name}_failed", result, results
    write_benchmark_doc(repo, run_id_value, results)
    return True, "all_gates_passed", None, results


def _collect_evaluator_snapshot(
    candidate: Candidate,
    cfg: EvoConfig,
    repo: Path,
    run_id_value: str,
) -> EvaluatorSnapshot:
    snapshot = collect_evaluator_results(candidate.path, cfg.result_files)
    write_evaluator_results(run_dir(repo, run_id_value) / "evaluator_results.json", snapshot)
    _event(
        repo,
        run_id_value,
        "evaluator_results_collected",
        candidate,
        {"ok": snapshot.ok, "reason": snapshot.reason, "files": sorted(snapshot.data)},
    )
    return snapshot


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
    run_id_value = run_id(cycle, candidate_index, pool_size)
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
    cycle_dir = _cycle_dir(repo, run_id_value)
    run_dir(repo, run_id_value).mkdir(parents=True, exist_ok=True)
    write_context_doc(repo, run_id_value, config_path, cfg, candidate)
    write_propose_doc(repo, run_id_value, prompt)
    _event(repo, run_id_value, "candidate_created", candidate, {"candidate": str(candidate.path)})
    agent = CodexBackend(sandbox=cfg.agent.sandbox)

    agent_result = agent.run(prompt=prompt, cwd=candidate.path, timeout_s=cfg.agent.timeout_s)
    _write_text(cycle_dir / "codex.stdout", agent_result.stdout)
    _write_text(cycle_dir / "codex.stderr", agent_result.stderr)
    write_agent_exchange(repo, cfg.agents.coder.session_id, prompt, agent_result.stdout, agent_result.stderr, agent_result.ok)
    _event(repo, run_id_value, "agent_finished", candidate, {"agent_id": cfg.agents.coder.session_id, "ok": agent_result.ok})
    if not agent_result.ok:
        return _record_decision(repo, run_id_value, candidate, "reject", "agent_failed", None, cfg)

    guard = _check_guard(candidate, cfg, cycle_dir)
    write_implement_doc(repo, run_id_value, candidate, guard)
    _event(repo, run_id_value, "guard_finished", candidate, asdict(guard))
    if not guard.ok:
        return _record_decision(repo, run_id_value, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg)

    commit_candidate(candidate.path, cycle)
    passed, reason, failed_result, _results = _run_pipeline(candidate, cfg, cycle_dir, repo, run_id_value)

    repair_attempt = 0
    while not passed and cfg.repair.enabled and failed_result and repair_attempt < cfg.repair.max_attempts:
        repair_attempt += 1
        repair_prompt = _repair_prompt(repo, cfg, reason, failed_result)
        repair = agent.run(repair_prompt, candidate.path, cfg.agent.timeout_s)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stdout", repair.stdout)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stderr", repair.stderr)
        write_agent_exchange(repo, cfg.agents.coder.session_id, repair_prompt, repair.stdout, repair.stderr, repair.ok)
        _event(repo, run_id_value, "agent_finished", candidate, {"agent_id": cfg.agents.coder.session_id, "repair_attempt": repair_attempt, "ok": repair.ok})
        if not repair.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", "repair_agent_failed", guard, cfg)
        guard = _check_guard(candidate, cfg, cycle_dir)
        write_implement_doc(repo, run_id_value, candidate, guard)
        _event(repo, run_id_value, "guard_finished", candidate, asdict(guard))
        if not guard.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg)
        commit_candidate(candidate.path, cycle)
        passed, reason, failed_result, _results = _run_pipeline(candidate, cfg, cycle_dir, repo, run_id_value)

    if not passed:
        return _record_decision(repo, run_id_value, candidate, "reject", reason, guard, cfg)

    evaluator_snapshot = _collect_evaluator_snapshot(candidate, cfg, repo, run_id_value)
    if not evaluator_snapshot.ok:
        return _record_decision(
            repo,
            run_id_value,
            candidate,
            "reject",
            f"evaluator_results_failed:{evaluator_snapshot.reason}",
            guard,
            cfg,
            evaluator_results=evaluator_snapshot.data,
        )

    if human_review or cfg.human.review_on_accept:
        human_decision = review_candidate(candidate, guard)
        _event(
            repo,
            run_id_value,
            "human_review",
            candidate,
            {"decision": human_decision.decision, "comment": human_decision.comment, "next_hint": human_decision.next_hint},
        )
        return _record_decision(
            repo,
            run_id_value,
            candidate,
            human_decision.decision,
            human_decision.reason,
            guard,
            cfg,
            human_decision.comment,
            human_decision.next_hint,
            evaluator_snapshot.data,
        )

    return _record_decision(
        repo,
        run_id_value,
        candidate,
        "accept",
        "all_gates_passed",
        guard,
        cfg,
        evaluator_results=evaluator_snapshot.data,
    )


def run_cycles(config_path: Path, cycles: int, human_review: bool = False) -> None:
    assert_not_paused(config_path)
    consecutive_rejects = 0
    scheduled_candidates = 0
    cfg = load_config(config_path)
    repo = (config_path.parent / cfg.project.repo).resolve()
    ensure_session(repo)
    write_project_indexes(repo)
    pool_size = cfg.pool.size if cfg.pool.enabled else 1
    max_cycles = cfg.budget.max_cycles if cfg.budget.max_cycles > 0 else cycles
    stop_cycles = min(cycles, max_cycles)
    for cycle in range(1, stop_cycles + 1):
        for candidate_index in range(1, pool_size + 1):
            if cfg.budget.max_candidates > 0 and scheduled_candidates >= cfg.budget.max_candidates:
                write_project_indexes(repo)
                return
            scheduled_candidates += 1
            record = run_one_cycle(config_path, cfg, cycle, candidate_index, pool_size, human_review)
            if record["decision"] == "reject":
                consecutive_rejects += 1
            else:
                consecutive_rejects = 0
            if cfg.human.stop_after_consecutive_rejects > 0 and consecutive_rejects >= cfg.human.stop_after_consecutive_rejects:
                write_project_indexes(repo)
                return
    write_project_indexes(repo)
