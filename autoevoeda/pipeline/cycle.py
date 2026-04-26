from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
import json

from autoevoeda.agents.codex import CodexBackend, run_codex_role
from autoevoeda.artifacts import (
    EvaluatorSnapshot,
    CommandResult,
    active_run,
    append_event,
    append_history,
    clear_active_run,
    collect_evaluator_results,
    read_agent_memory,
    read_history,
    run_dir,
    run_id,
    write_benchmark_doc,
    write_context_doc,
    write_cycle_summary,
    write_decision_doc,
    write_evaluator_results,
    write_implement_doc,
    write_project_indexes,
    write_propose_doc,
    write_run_state,
    run_cmd,
    write_agent_exchange,
    assert_not_paused,
    ensure_session,
)
from autoevoeda.config import DomainAgentConfig, EvoConfig, load_config
from autoevoeda.human import review_candidate
from autoevoeda.memory import append_lesson, render_prompt, render_repair_prompt
from autoevoeda.workspace.git import Candidate, commit_candidate, create_candidate_workspace, create_candidate_worktree, git
from autoevoeda.workspace.guard import GuardResult, check_candidate_scope


def _pipeline_env(repo: Path, candidate: Candidate) -> dict[str, str]:
    return {
        "AUTOEVO_ADAPTER_ROOT": str(repo),
        "AUTOEVO_CANDIDATE_ROOT": str(candidate.path),
    }


def _candidate_head(candidate: Candidate) -> str:
    if candidate.repos:
        return ""
    return git(["rev-parse", "HEAD"], cwd=candidate.path)


def _candidate_diff(candidate: Candidate) -> str:
    if not candidate.repos:
        return git(["diff"], cwd=candidate.path)
    parts = []
    for repo in candidate.repos:
        diff = git(["diff"], cwd=repo.path)
        if diff:
            parts.extend([f"# repo: {repo.name}", diff])
    return "\n".join(parts)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


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
    agent: str = "",
) -> dict[str, object]:
    record = {
        "cycle": candidate.cycle,
        "candidate_index": candidate.index,
        "run_id": run_id_value,
        "candidate": str(candidate.path),
        "branch": candidate.branch,
        "candidate_repos": {item.name: {"source": str(item.source), "path": str(item.path), "branch": item.branch, "champion_branch": item.champion_branch} for item in candidate.repos},
        "decision": decision,
        "reason": reason,
        "changed_files": guard.changed_files if guard else 0,
        "changed_lines": guard.changed_lines if guard else 0,
        "human_comment": human_comment,
        "next_hint": next_hint,
        "evaluator_results": evaluator_results or {},
        "agent": agent,
    }
    append_history(repo, record)
    append_lesson(repo, cfg, record)
    write_cycle_summary(repo, record)
    write_decision_doc(repo, run_id_value, record)
    _event(repo, run_id_value, "decision_recorded", candidate, {"decision": decision, "reason": reason})
    write_run_state(repo, run_id_value, "decision_recorded", candidate.cycle, candidate.index, candidate.branch, str(candidate.path))
    clear_active_run(repo)
    return record


def _write_command_result(cycle_dir: Path, result: CommandResult) -> None:
    _write_text(cycle_dir / f"{result.name}.stdout", result.stdout)
    _write_text(cycle_dir / f"{result.name}.stderr", result.stderr)
    _write_text(cycle_dir / f"{result.name}.returncode", f"{result.returncode}\n")


def _checkpoint(repo: Path, run_id_value: str, phase: str, candidate: Candidate) -> None:
    write_run_state(repo, run_id_value, phase, candidate.cycle, candidate.index, candidate.branch, str(candidate.path))


def _check_guard(candidate: Candidate, cfg: EvoConfig, cycle_dir: Path, domain_agent: DomainAgentConfig | None = None) -> GuardResult:
    allowed_paths = domain_agent.allowed_paths if domain_agent else cfg.guards.allowed_paths
    forbidden_paths = [*cfg.guards.forbidden_paths, *(domain_agent.forbidden_paths if domain_agent else [])]
    guard = check_candidate_scope(
        candidate=candidate,
        workspace=cfg.workspace,
        allowed_paths=allowed_paths,
        forbidden_paths=forbidden_paths,
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
        result = run_cmd(name=name, cmd=cmd, cwd=candidate.path, env=_pipeline_env(repo, candidate))
        _checkpoint(repo, run_id_value, f"{name}_finished", candidate)
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


def _role_prompt(repo: Path, cfg: EvoConfig, path: str) -> str:
    return render_prompt((repo / path).read_text(), repo, cfg) if path else ""


def _planner_context(repo: Path, cfg: EvoConfig) -> str:
    lines = ["", "# Planner Context", "", "## Recent Outcomes"]
    for record in read_history(repo)[-10:]:
        reward = record.get("evaluator_results", {}).get("reward", {})
        score = reward.get("score", "") if isinstance(reward, dict) else ""
        lines.append(f"- cycle {record.get('cycle')}: {record.get('decision')} / {record.get('reason')} / agent={record.get('agent', '')} / score={score}")
    if cfg.domain_agents:
        lines.extend(["", "## Available Domain Agents"])
        lines.extend(f"- {agent.name}: {', '.join(agent.allowed_paths)}" for agent in cfg.domain_agents)
    return "\n".join(lines) + "\n"


def _select_domain_agent(cfg: EvoConfig, planner_stdout: str) -> DomainAgentConfig | None:
    if not cfg.domain_agents:
        return None
    selected = [line.split(":", 1)[1].strip() for line in planner_stdout.splitlines() if line.lower().startswith("agent:")]
    if len(selected) != 1:
        raise ValueError("planner must emit exactly one line: agent: <domain-agent-name>")
    matches = [agent for agent in cfg.domain_agents if agent.name == selected[0]]
    if not matches:
        raise ValueError(f"unknown domain agent selected by planner: {selected[0]}")
    return matches[0]


def _proposal(stdout: str) -> dict[str, str]:
    keys = ["hypothesis", "target_files", "expected_metric_impact", "rollback_risk"]
    values: dict[str, str] = {}
    for line in stdout.splitlines():
        name, sep, value = line.partition(":")
        if sep and name.strip().lower() in keys:
            values[name.strip().lower()] = value.strip()
    missing = [key for key in keys if not values.get(key)]
    if missing:
        raise ValueError("agent proposal missing fields: " + ", ".join(missing))
    return values


def _write_agent_proposal(cycle_dir: Path, agent_name: str, proposal: dict[str, str]) -> None:
    _write_text(cycle_dir / "agent_proposal.json", json.dumps({"agent": agent_name, **proposal}, indent=2, sort_keys=True) + "\n")
    _write_text(
        cycle_dir / "agent_proposal.md",
        "\n".join([f"# Agent Proposal: {agent_name}", "", *[f"- {key}: {proposal[key]}" for key in sorted(proposal)], ""]),
    )


def _write_reproducibility(cycle_dir: Path, config_path: Path, repo: Path, candidate: Candidate, cfg: EvoConfig) -> None:
    data = {
        "config": str(config_path),
        "project": cfg.project.name,
        "champion_branch": cfg.project.champion_branch,
        "project_head": git(["rev-parse", "HEAD"], cwd=repo),
        "candidate_branch": candidate.branch,
        "candidate_head": _candidate_head(candidate),
        "candidate_repos": {repo.name: {"branch": repo.branch, "head": git(["rev-parse", "HEAD"], cwd=repo.path)} for repo in candidate.repos},
    }
    _write_text(cycle_dir / "reproducibility.json", json.dumps(data, indent=2, sort_keys=True) + "\n")


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
    if cfg.workspace.mode == "multi_repo":
        candidate = create_candidate_workspace(
            adapter_repo=repo,
            cfg_workspace=cfg.workspace,
            project_name=cfg.project.name,
            cycle=cycle,
            candidate_index=candidate_index,
            pool_size=pool_size,
        )
    else:
        candidate = create_candidate_worktree(
            repo=repo,
            champion_branch=cfg.project.champion_branch,
            worktree_root=(config_path.parent / cfg.workspace.worktree_root).resolve(),
            project_name=cfg.project.name,
            cycle=cycle,
            candidate_index=candidate_index,
            pool_size=pool_size,
        )
    cycle_dir = run_dir(repo, run_id_value)
    cycle_dir.mkdir(parents=True, exist_ok=True)
    _checkpoint(repo, run_id_value, "candidate_created", candidate)
    write_context_doc(repo, run_id_value, config_path, cfg, candidate)
    _event(repo, run_id_value, "candidate_created", candidate, {"candidate": str(candidate.path)})
    agent = CodexBackend(sandbox=cfg.agent.sandbox)

    planner_notes = ""
    domain_agent = None
    if cfg.multi_agent.planner and cfg.roles.planner_prompt:
        planner_prompt = _role_prompt(repo, cfg, cfg.roles.planner_prompt)
        planner_prompt += _planner_context(repo, cfg)
        if cfg.domain_agents:
            planner_prompt += "\n# Domain agent selection\nEmit exactly one line in this form:\nagent: <name>\nAvailable agents:\n"
            planner_prompt += "\n".join(f"- {agent.name}" for agent in cfg.domain_agents) + "\n"
        planner = run_codex_role(repo, cfg.agents.planner, agent, planner_prompt, candidate.path, cfg.agent.timeout_s)
        _checkpoint(repo, run_id_value, "planner_finished", candidate)
        _write_text(cycle_dir / "planner.stdout", planner.stdout)
        _write_text(cycle_dir / "planner.stderr", planner.stderr)
        write_agent_exchange(repo, cfg.agents.planner.session_id, planner_prompt, planner.stdout, planner.stderr, planner.ok)
        _event(repo, run_id_value, "planner_finished", candidate, {"ok": planner.ok})
        if not planner.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", "planner_failed", None, cfg)
        planner_notes = planner.stdout.strip()
        try:
            domain_agent = _select_domain_agent(cfg, planner.stdout)
        except ValueError as exc:
            return _record_decision(repo, run_id_value, candidate, "reject", f"planner_selection_failed:{exc}", None, cfg)

    base_prompt = (repo / (domain_agent.prompt_file if domain_agent else cfg.agent.prompt_file)).read_text()
    prompt = render_prompt(base_prompt, repo, cfg)
    if domain_agent:
        prompt += "\n# Domain Agent\n"
        prompt += f"name: {domain_agent.name}\n"
        prompt += "allowed_paths:\n" + "\n".join(f"- {path}" for path in domain_agent.allowed_paths) + "\n"
        prompt += "forbidden_paths:\n" + "\n".join(f"- {path}" for path in [*cfg.guards.forbidden_paths, *domain_agent.forbidden_paths]) + "\n"
        agent_memory = read_agent_memory(repo, domain_agent.session_id)
        if agent_memory:
            prompt += "\n# Domain Agent Memory\n" + agent_memory + "\n"
        prompt += "Before finishing, include these exact response fields:\n"
        prompt += "hypothesis:\ntarget_files:\nexpected_metric_impact:\nrollback_risk:\n"
    if cfg.workspace.mode == "multi_repo":
        prompt += "\n# Candidate Workspace\n"
        prompt += f"AUTOEVO_ADAPTER_ROOT={repo}\n"
        prompt += f"AUTOEVO_CANDIDATE_ROOT={candidate.path}\n"
        prompt += "Repos:\n" + "\n".join(f"- {item.name}: {item.path}" for item in candidate.repos) + "\n"
    if planner_notes:
        prompt += "\n# Planner Notes\n" + planner_notes + "\n"
    write_propose_doc(repo, run_id_value, prompt)

    coder_role = domain_agent or cfg.agents.coder
    agent_name = domain_agent.name if domain_agent else cfg.agents.coder.session_id
    agent_result = run_codex_role(repo, coder_role, agent, prompt, candidate.path, cfg.agent.timeout_s)
    _checkpoint(repo, run_id_value, "agent_finished", candidate)
    _write_text(cycle_dir / "codex.stdout", agent_result.stdout)
    _write_text(cycle_dir / "codex.stderr", agent_result.stderr)
    write_agent_exchange(repo, coder_role.session_id, prompt, agent_result.stdout, agent_result.stderr, agent_result.ok)
    _event(repo, run_id_value, "agent_finished", candidate, {"agent_id": coder_role.session_id, "agent": agent_name, "ok": agent_result.ok})
    if not agent_result.ok:
        return _record_decision(repo, run_id_value, candidate, "reject", "agent_failed", None, cfg, agent=agent_name)
    if domain_agent:
        try:
            _write_agent_proposal(cycle_dir, agent_name, _proposal(agent_result.stdout))
        except ValueError as exc:
            return _record_decision(repo, run_id_value, candidate, "reject", f"agent_proposal_failed:{exc}", None, cfg, agent=agent_name)

    guard = _check_guard(candidate, cfg, cycle_dir, domain_agent)
    _checkpoint(repo, run_id_value, "guard_finished", candidate)
    write_implement_doc(repo, run_id_value, candidate, guard)
    _event(repo, run_id_value, "guard_finished", candidate, asdict(guard))
    if not guard.ok:
        return _record_decision(repo, run_id_value, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg, agent=agent_name)

    if cfg.multi_agent.reviewer and cfg.roles.reviewer_prompt:
        review_prompt = _role_prompt(repo, cfg, cfg.roles.reviewer_prompt)
        review_prompt += "\n# Patch\n" + _candidate_diff(candidate)
        review = run_codex_role(repo, cfg.agents.reviewer, agent, review_prompt, candidate.path, cfg.agent.timeout_s)
        _checkpoint(repo, run_id_value, "reviewer_finished", candidate)
        _write_text(cycle_dir / "reviewer.stdout", review.stdout)
        _write_text(cycle_dir / "reviewer.stderr", review.stderr)
        write_agent_exchange(repo, cfg.agents.reviewer.session_id, review_prompt, review.stdout, review.stderr, review.ok)
        _event(repo, run_id_value, "reviewer_finished", candidate, {"ok": review.ok})
        if not review.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", "reviewer_failed", guard, cfg, agent=agent_name)

    commit_candidate(candidate, cycle)
    _checkpoint(repo, run_id_value, "committed", candidate)
    _write_reproducibility(cycle_dir, config_path, repo, candidate, cfg)
    passed, reason, failed_result, _results = _run_pipeline(candidate, cfg, cycle_dir, repo, run_id_value)

    repair_attempt = 0
    while not passed and cfg.repair.enabled and failed_result and repair_attempt < cfg.repair.max_attempts:
        repair_attempt += 1
        repair_prompt = _repair_prompt(repo, cfg, reason, failed_result)
        repair = run_codex_role(repo, cfg.agents.repair, agent, repair_prompt, candidate.path, cfg.agent.timeout_s)
        _checkpoint(repo, run_id_value, f"repair_{repair_attempt}_finished", candidate)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stdout", repair.stdout)
        _write_text(cycle_dir / f"repair-{repair_attempt}.stderr", repair.stderr)
        write_agent_exchange(repo, cfg.agents.repair.session_id, repair_prompt, repair.stdout, repair.stderr, repair.ok)
        _event(repo, run_id_value, "agent_finished", candidate, {"agent_id": cfg.agents.repair.session_id, "repair_attempt": repair_attempt, "ok": repair.ok})
        if not repair.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", "repair_agent_failed", guard, cfg, agent=agent_name)
        guard = _check_guard(candidate, cfg, cycle_dir, domain_agent)
        _checkpoint(repo, run_id_value, f"repair_{repair_attempt}_guard_finished", candidate)
        write_implement_doc(repo, run_id_value, candidate, guard)
        _event(repo, run_id_value, "guard_finished", candidate, asdict(guard))
        if not guard.ok:
            return _record_decision(repo, run_id_value, candidate, "reject", f"guard_failed:{guard.reason}", guard, cfg, agent=agent_name)
        commit_candidate(candidate, cycle)
        _checkpoint(repo, run_id_value, f"repair_{repair_attempt}_committed", candidate)
        _write_reproducibility(cycle_dir, config_path, repo, candidate, cfg)
        passed, reason, failed_result, _results = _run_pipeline(candidate, cfg, cycle_dir, repo, run_id_value)

    if not passed:
        return _record_decision(repo, run_id_value, candidate, "reject", reason, guard, cfg, agent=agent_name)

    evaluator_snapshot = _collect_evaluator_snapshot(candidate, cfg, repo, run_id_value)
    _checkpoint(repo, run_id_value, "evaluator_results_collected", candidate)
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
            agent=agent_name,
        )
    reward = evaluator_snapshot.data.get("reward", {})
    reward_decision = reward.get("decision") if isinstance(reward, dict) else None
    if reward_decision:
        if reward_decision not in {"accept", "keep", "reject"}:
            return _record_decision(repo, run_id_value, candidate, "reject", f"evaluator_results_failed:reward_decision_invalid:{reward_decision}", guard, cfg, evaluator_results=evaluator_snapshot.data, agent=agent_name)
        if reward_decision != "accept":
            reason = str(reward.get("reason", f"reward_{reward_decision}"))
            return _record_decision(repo, run_id_value, candidate, reward_decision, reason, guard, cfg, evaluator_results=evaluator_snapshot.data, agent=agent_name)

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
            agent=agent_name,
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
        agent=agent_name,
    )


def _active_has_decision(repo: Path, active: dict[str, object]) -> bool:
    return any(record.get("run_id") == active.get("run_id") and "decision" in record for record in read_history(repo))


def abandon_active(config_path: Path) -> dict[str, object]:
    cfg = load_config(config_path)
    repo = (config_path.parent / cfg.project.repo).resolve()
    active = active_run(repo)
    if not active:
        raise RuntimeError("no active interrupted run to abandon")
    if _active_has_decision(repo, active):
        clear_active_run(repo)
        raise RuntimeError("active run already has a decision; cleared stale active marker")
    candidate = Candidate(
        cycle=int(active["cycle"]),
        index=int(active.get("candidate_index", 1)),
        branch=str(active["branch"]),
        path=Path(str(active["candidate"])),
    )
    return _record_decision(repo, str(active["run_id"]), candidate, "reject", "abandoned_interrupted_run", None, cfg)


def assert_no_interrupted_run(repo: Path) -> None:
    active = active_run(repo)
    if active and not _active_has_decision(repo, active):
        raise RuntimeError(f"interrupted run exists: {active['run_id']}; inspect .evo/runs/{active['run_id']} then run `evo run --abandon-active --cycles 0`")
    if active:
        clear_active_run(repo)


def run_cycles(config_path: Path, cycles: int, human_review: bool = False, abandon_active_run: bool = False) -> None:
    assert_not_paused(config_path)
    consecutive_rejects = 0
    scheduled_candidates = 0
    cfg = load_config(config_path)
    repo = (config_path.parent / cfg.project.repo).resolve()
    ensure_session(repo)
    if abandon_active_run:
        abandon_active(config_path)
    assert_no_interrupted_run(repo)
    write_project_indexes(repo)
    history = [record for record in read_history(repo) if "decision" in record and "cycle" in record]
    completed_cycles = max([int(record["cycle"]) for record in history], default=0)
    completed_candidates = len(history)
    pool_size = cfg.pool.size if cfg.pool.enabled else 1
    remaining_cycles = cfg.budget.max_cycles - completed_cycles if cfg.budget.max_cycles > 0 else cycles
    stop_cycles = min(cycles, max(0, remaining_cycles))
    for cycle in range(completed_cycles + 1, completed_cycles + stop_cycles + 1):
        for candidate_index in range(1, pool_size + 1):
            if cfg.budget.max_candidates > 0 and completed_candidates + scheduled_candidates >= cfg.budget.max_candidates:
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
