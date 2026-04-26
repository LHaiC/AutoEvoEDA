from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
import json
import subprocess

from evoharness.config import EvoConfig, ResultFilesConfig, load_config
from evoharness.workspace.git import Candidate, changed_files, git
from evoharness.workspace.guard import GuardResult


def project_repo(config_path: Path) -> Path:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve()


def run_id(cycle: int, candidate_index: int, pool_size: int) -> str:
    return f"cycle-{cycle:03d}" if pool_size == 1 else f"cycle-{cycle:03d}-cand-{candidate_index:03d}"


def run_dir(repo: Path, value: str) -> Path:
    return repo / ".evo" / "runs" / value


def agent_dir(repo: Path, agent_id: str) -> Path:
    return repo / ".evo" / "agents" / agent_id


def read_agent_memory(repo: Path, agent_id: str) -> str:
    path = agent_dir(repo, agent_id) / "memory.md"
    return path.read_text().strip() if path.exists() else ""


def _codex_session_path(repo: Path, agent_id: str, session_file: str) -> Path:
    return repo / session_file if session_file else agent_dir(repo, agent_id) / "codex_session.txt"


def read_codex_session(repo: Path, agent_id: str, session_file: str) -> str:
    path = _codex_session_path(repo, agent_id, session_file)
    return path.read_text().strip() if path.exists() else ""


def write_codex_session_event(repo: Path, agent_id: str, event: str, payload: dict[str, Any]) -> None:
    directory = agent_dir(repo, agent_id)
    directory.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(), "event": event, **payload}
    with (directory / "codex_session_events.jsonl").open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def write_agent_exchange(repo: Path, agent_id: str, prompt: str, stdout: str, stderr: str, ok: bool) -> None:
    directory = agent_dir(repo, agent_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "last_prompt.md").write_text(prompt)
    (directory / "last_response.md").write_text(stdout)
    record = {
        "time": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "prompt_path": "last_prompt.md",
        "response_path": "last_response.md",
        "stderr": stderr,
    }
    with (directory / "transcript.jsonl").open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    memory = directory / "memory.md"
    if not memory.exists():
        memory.write_text(f"# Agent Memory: {agent_id}\n\nAdd durable role-specific notes here.\n")


def session_dir(repo: Path) -> Path:
    return repo / ".evo" / "session"


def _state_path(repo: Path) -> Path:
    return session_dir(repo) / "state.json"


def _inbox_path(repo: Path) -> Path:
    return session_dir(repo) / "inbox.jsonl"


def read_state(repo: Path) -> dict[str, Any]:
    path = _state_path(repo)
    return json.loads(path.read_text()) if path.exists() else {"status": "running", "updated_at": datetime.now(timezone.utc).isoformat()}


def write_state(repo: Path, state: dict[str, Any]) -> None:
    path = _state_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def ensure_session(repo: Path) -> dict[str, Any]:
    state = read_state(repo)
    write_state(repo, state)
    return state


def session_status(config_path: Path) -> dict[str, Any]:
    return ensure_session(project_repo(config_path))


def set_session_status(config_path: Path, status: str) -> dict[str, Any]:
    repo = project_repo(config_path)
    state = read_state(repo)
    state["status"] = status
    write_state(repo, state)
    append_event(repo, "session", f"session_{status}", 0, 0, "", {"status": status})
    return state


def add_session_comment(config_path: Path, text: str) -> dict[str, Any]:
    repo = project_repo(config_path)
    ensure_session(repo)
    entry = {"time": datetime.now(timezone.utc).isoformat(), "type": "human_comment", "text": text}
    path = _inbox_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    append_event(repo, "session", "human_comment", 0, 0, "", {"text": text})
    return entry


def recent_inbox(repo: Path, count: int = 5) -> list[dict[str, Any]]:
    path = _inbox_path(repo)
    lines = path.read_text().splitlines()[-count:] if path.exists() and count > 0 else []
    return [json.loads(line) for line in lines if line.strip()]


def assert_not_paused(config_path: Path) -> None:
    if read_state(project_repo(config_path)).get("status") == "paused":
        raise RuntimeError("session is paused; run `evo session resume` before scheduling candidates")


@dataclass(frozen=True)
class CommandResult:
    name: str
    ok: bool
    returncode: int
    stdout: str
    stderr: str


def run_cmd(name: str, cmd: str, cwd: Path) -> CommandResult:
    proc = subprocess.run(cmd, cwd=cwd, shell=True, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return CommandResult(name, proc.returncode == 0, proc.returncode, proc.stdout, proc.stderr)


def read_history(repo: Path) -> list[dict[str, Any]]:
    path = repo / ".evo" / "history.jsonl"
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()] if path.exists() else []


def append_history(repo: Path, record: dict[str, Any]) -> Path:
    path = repo / ".evo" / "history.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return path


def append_event(
    repo: Path,
    run_id_value: str,
    event_type: str,
    cycle: int,
    candidate_index: int,
    branch: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    event = {
        "time": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        "cycle": cycle,
        "candidate_index": candidate_index,
        "run_id": run_id_value,
        "branch": branch,
        "payload": payload,
    }
    for path in [repo / ".evo" / "events.jsonl", run_dir(repo, run_id_value) / "events.jsonl"]:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as handle:
            handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return event


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def write_context_doc(repo: Path, value: str, config_path: Path, cfg: EvoConfig, candidate: Candidate) -> None:
    _write(
        run_dir(repo, value) / "00_context.md",
        "\n".join(
            [
                f"# Context: {value}",
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


def write_propose_doc(repo: Path, value: str, prompt: str) -> None:
    _write(run_dir(repo, value) / "01_propose.md", "# Proposal Prompt\n\n```text\n" + prompt + "\n```\n")


def write_implement_doc(repo: Path, value: str, candidate: Candidate, guard: GuardResult) -> None:
    _write(run_dir(repo, value) / "patch.diff", git(["diff"], cwd=candidate.path) + "\n")
    _write(
        run_dir(repo, value) / "02_implement.md",
        "\n".join(
            [
                f"# Implementation: {value}",
                "",
                f"- Guard: `{guard.reason}`",
                f"- Changed files: {guard.changed_files}",
                f"- Changed lines: {guard.changed_lines}",
                f"- Patch: `patch.diff`",
                "",
                "## Files",
                *[f"- `{path}`" for path in changed_files(candidate.path)],
                "",
            ]
        ),
    )


def write_benchmark_doc(repo: Path, value: str, results: list[CommandResult]) -> None:
    lines = [f"# Benchmark: {value}", ""]
    for result in results:
        lines.extend(
            [
                f"## {result.name}",
                "",
                f"- Return code: {result.returncode}",
                f"- Passed: {result.ok}",
                f"- Stdout: `.evo/runs/{value}/{result.name}.stdout`",
                f"- Stderr: `.evo/runs/{value}/{result.name}.stderr`",
                "",
            ]
        )
    _write(run_dir(repo, value) / "03_benchmark.md", "\n".join(lines))


def write_decision_doc(repo: Path, value: str, record: dict[str, Any]) -> None:
    lines = [
        f"# Decision: {value}",
        "",
        f"- Decision: `{record['decision']}`",
        f"- Reason: `{record['reason']}`",
        f"- Branch: `{record['branch']}`",
        f"- Candidate: `{record['candidate']}`",
    ]
    if record.get("human_comment"):
        lines.append(f"- Human comment: {record['human_comment']}")
    if record.get("next_hint"):
        lines.append(f"- Next hint: {record['next_hint']}")
    evaluator_results = record.get("evaluator_results", {})
    if isinstance(evaluator_results, dict) and evaluator_results:
        lines.extend(["", "## Evaluator Results", "", *[f"- `{name}`" for name in sorted(evaluator_results)]])
    _write(run_dir(repo, value) / "04_decision.md", "\n".join(lines) + "\n")


@dataclass(frozen=True)
class EvaluatorSnapshot:
    ok: bool
    reason: str
    data: dict[str, dict[str, Any]]


def collect_evaluator_results(repo: Path, result_files: ResultFilesConfig) -> EvaluatorSnapshot:
    data: dict[str, dict[str, Any]] = {}
    for kind, rel_path in asdict(result_files).items():
        path = repo / rel_path
        if not path.exists():
            continue
        try:
            value = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            return EvaluatorSnapshot(False, f"{kind}_json_invalid:{rel_path}:{exc.msg}", data)
        if not isinstance(value, dict):
            return EvaluatorSnapshot(False, f"{kind}_json_not_object:{rel_path}", data)
        data[kind] = value
    return EvaluatorSnapshot(True, "ok", data)


def write_evaluator_results(path: Path, snapshot: EvaluatorSnapshot) -> None:
    path.write_text(json.dumps(asdict(snapshot), ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _cycle_dir_name(record: dict[str, Any]) -> str:
    branch = str(record["branch"])
    return branch.removeprefix("evo/") if branch.startswith("evo/") else f"cycle-{int(record['cycle']):03d}"


def write_cycle_summary(repo: Path, record: dict[str, Any]) -> Path:
    name = _cycle_dir_name(record)
    path = run_dir(repo, name) / "summary.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    evaluator_results = record.get("evaluator_results", {})
    result_keys = ", ".join(sorted(evaluator_results)) if isinstance(evaluator_results, dict) and evaluator_results else "none"
    path.write_text(
        "\n".join(
            [
                f"# {name} Summary",
                "",
                f"- Branch: `{record['branch']}`",
                f"- Candidate: `{record['candidate']}`",
                f"- Decision: `{record['decision']}`",
                f"- Reason: `{record['reason']}`",
                f"- Changed files: {record['changed_files']}",
                f"- Changed lines: {record['changed_lines']}",
                f"- Evaluator results: {result_keys}",
                "",
                "## Artifacts",
                "",
                *[
                    f"- {label}: `.evo/runs/{name}/{file}`"
                    for label, file in [
                        ("Codex stdout", "codex.stdout"),
                        ("Codex stderr", "codex.stderr"),
                        ("Guard result", "guard.json"),
                        ("Build stdout", "build.stdout"),
                        ("Regression stdout", "regression.stdout"),
                        ("Performance stdout", "perf.stdout"),
                        ("Reward stdout", "reward.stdout"),
                        ("Evaluator results", "evaluator_results.json"),
                    ]
                ],
                "",
            ]
        )
    )
    return path


def write_project_indexes(repo: Path) -> None:
    evo = repo / ".evo"
    evo.mkdir(parents=True, exist_ok=True)
    records = [r for r in read_history(repo) if "branch" in r and r.get("event") != "promote"]
    lines = ["# evo-harness Index", "", "## Recent Candidates", ""]
    lines.extend(f"- `{r.get('run_id', _cycle_dir_name(r))}`: `{r['decision']}` / `{r['reason']}` on `{r['branch']}`" for r in records[-20:])
    lines.extend(["", "## Files", "", "- `history.jsonl`", "- `events.jsonl`", "- `runs/`", "- `session/`", "- `memory/`", ""])
    (evo / "index.md").write_text("\n".join(lines))
    roadmap = evo / "roadmap.md"
    if not roadmap.exists():
        roadmap.write_text("# Evolution Roadmap\n\n## Current Focus\n\nUse `evo session comment` to add steering notes for the next run.\n")
    runs = evo / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    (runs / "README.md").write_text("# Runs\n\n" + "".join(f"- `{p.name}/`\n" for p in sorted(runs.iterdir()) if p.is_dir()))


def write_reports(repo: Path) -> Path:
    reports = repo / ".evo" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    records = [r for r in read_history(repo) if "decision" in r]
    accepted = [r for r in records if r.get("decision") in {"accept", "keep", "promote"}]
    rejected = [r for r in records if r.get("decision") == "reject"]
    summary = reports / "summary.md"
    summary.write_text(
        "\n".join(
            [
                "# Evolution Summary",
                "",
                f"- Total decisions: {len(records)}",
                f"- Accepted or kept: {len(accepted)}",
                f"- Rejected: {len(rejected)}",
                "",
                "## Recent",
                "",
                *[f"- cycle {r.get('cycle')}: `{r.get('decision')}` / `{r.get('reason')}`" for r in records[-20:]],
                "",
            ]
        )
    )
    (reports / "failures.md").write_text("\n".join(f"- cycle {r.get('cycle')}: {r.get('reason')}" for r in rejected) + "\n")
    (reports / "accepted_patterns.md").write_text("\n".join(f"- cycle {r.get('cycle')}: {r.get('reason')}" for r in accepted) + "\n")
    return summary


def _score(record: dict[str, Any]) -> float | None:
    reward = record.get("evaluator_results", {}).get("reward", {})
    value = reward.get("score") if isinstance(reward, dict) else None
    return float(value) if isinstance(value, (int, float)) else None


def compare_cycle(config_path: Path, cycle: int) -> Path:
    repo = project_repo(config_path)
    rows = [r for r in read_history(repo) if r.get("cycle") == cycle and "candidate" in r]
    scored = [(r, _score(r)) for r in rows]
    best = max((item for item in scored if item[1] is not None), key=lambda item: item[1], default=None)
    report = repo / ".evo" / "reports" / f"compare-cycle-{cycle:03d}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"# Candidate Comparison: cycle {cycle:03d}", "", "| Candidate | Decision | Reason | Score | Branch |", "| --- | --- | --- | --- | --- |"]
    for record, score in scored:
        lines.append(f"| {record.get('candidate_index', 1)} | {record.get('decision')} | {record.get('reason')} | {'' if score is None else score} | `{record.get('branch')}` |")
    if best:
        lines.extend(["", f"Recommended candidate: `{best[0].get('candidate_index', 1)}` with score `{best[1]}`."])
    report.write_text("\n".join(lines) + "\n")
    return report


def _proposal_dir(repo: Path) -> Path:
    path = repo / ".evo" / "rules" / "proposals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_rule_proposals(config_path: Path) -> list[str]:
    return [path.stem for path in sorted(_proposal_dir(project_repo(config_path)).glob("*.md"))]


def propose_rules(config_path: Path) -> Path:
    repo = project_repo(config_path)
    proposal_id = datetime.now(timezone.utc).strftime("rule-%Y%m%d-%H%M%S")
    path = _proposal_dir(repo) / f"{proposal_id}.md"
    lines = [
        f"# Rule Proposal: {proposal_id}",
        "",
        "## Candidate Rule Updates",
        "",
        "- Keep evaluator scripts, benchmark data, and reward logic outside candidate edit scope.",
        "- Prefer small reversible patches tied to one measured hypothesis.",
        "",
        "## Recent Evidence",
        "",
        *[f"- cycle {r.get('cycle')}: {r.get('decision')} / {r.get('reason')}" for r in read_history(repo)[-10:]],
        "",
        "## Human Decision",
        "",
        "Accept this proposal with `evo rules accept` or reject it with a comment.",
    ]
    path.write_text("\n".join(lines) + "\n")
    append_event(repo, "rules", "rule_proposed", 0, 0, "", {"proposal": proposal_id})
    return path


def accept_rule(config_path: Path, proposal_id: str) -> Path:
    repo = project_repo(config_path)
    cfg = load_config(config_path)
    proposal = _proposal_dir(repo) / f"{proposal_id}.md"
    if not proposal.exists():
        raise ValueError(f"rule proposal not found: {proposal_id}")
    rulebase = repo / cfg.rulebase.path
    rulebase.parent.mkdir(parents=True, exist_ok=True)
    existing = rulebase.read_text() if rulebase.exists() else "# Rulebase\n"
    rulebase.write_text(existing.rstrip() + "\n\n" + proposal.read_text().rstrip() + "\n")
    append_event(repo, "rules", "rule_accepted", 0, 0, "", {"proposal": proposal_id})
    return rulebase


def reject_rule(config_path: Path, proposal_id: str, comment: str) -> Path:
    repo = project_repo(config_path)
    path = repo / ".evo" / "rules" / "rejections.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"time": datetime.now(timezone.utc).isoformat(), "proposal": proposal_id, "comment": comment}
    with path.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    append_event(repo, "rules", "rule_rejected", 0, 0, "", record)
    return path


def _find_cycle_record(records: list[dict[str, Any]], cycle: int, candidate_index: int) -> dict[str, Any]:
    for record in reversed(records):
        if (
            record.get("cycle") == cycle
            and record.get("candidate_index", 1) == candidate_index
            and record.get("decision") in {"accept", "keep", "reject"}
        ):
            return record
    raise ValueError(f"cycle not found in history: {cycle}, candidate: {candidate_index}")


def promote_cycle(config_path: Path, cycle: int, candidate_index: int = 1) -> None:
    cfg = load_config(config_path)
    repo = project_repo(config_path)
    if cfg.promotion.require_clean_champion and git(["status", "--porcelain", "--untracked-files=no"], cwd=repo):
        raise ValueError("project repo must be clean before promotion")
    record = _find_cycle_record(read_history(repo), cycle, candidate_index)
    if record["decision"] not in {"accept", "keep"}:
        raise ValueError(f"cycle {cycle} cannot be promoted from decision: {record['decision']}")

    branch = record["branch"]
    git(["rev-parse", "--verify", branch], cwd=repo)
    git(["checkout", cfg.project.champion_branch], cwd=repo)
    git(["merge", "--ff-only", branch], cwd=repo)
    promote_record = {
        "event": "promote",
        "cycle": cycle,
        "candidate_index": candidate_index,
        "branch": branch,
        "champion_branch": cfg.project.champion_branch,
        "decision": "promote",
        "reason": "explicit_promote",
    }
    append_history(repo, promote_record)
    append_event(repo, record.get("run_id", run_id(cycle, candidate_index, 1)), "promote", cycle, candidate_index, branch, promote_record)


def list_worktrees(config_path: Path) -> list[dict[str, Any]]:
    rows = []
    for record in read_history(project_repo(config_path)):
        if "candidate" not in record:
            continue
        path = Path(str(record["candidate"]))
        rows.append(
            {
                "cycle": record.get("cycle"),
                "candidate_index": record.get("candidate_index", 1),
                "decision": record.get("decision"),
                "path": str(path),
                "exists": path.exists(),
                "dirty": bool(git(["status", "--porcelain"], cwd=path)) if path.exists() else False,
            }
        )
    return rows


def cleanup_worktrees(
    config_path: Path,
    rejected: bool = False,
    older_than_days: int = 0,
    include_accepted: bool = False,
    force: bool = False,
) -> list[dict[str, Any]]:
    if not rejected and older_than_days <= 0:
        raise ValueError("select cleanup scope with --rejected or --older-than-days")
    repo = project_repo(config_path)
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days) if older_than_days > 0 else None
    removed = []
    for record in read_history(repo):
        decision = record.get("decision")
        path = Path(str(record.get("candidate", "")))
        if not path.exists():
            continue
        if rejected and decision != "reject":
            continue
        if decision in {"accept", "keep"} and not include_accepted:
            continue
        if cutoff and datetime.fromtimestamp(path.stat().st_mtime, timezone.utc) > cutoff:
            continue
        if git(["status", "--porcelain"], cwd=path) and not force:
            continue
        args = ["worktree", "remove", str(path)]
        git(args[:2] + ["--force"] + args[2:] if force else args, cwd=repo)
        item = {"cycle": record.get("cycle"), "candidate_index": record.get("candidate_index", 1), "path": str(path)}
        removed.append(item)
        append_event(repo, record.get("run_id", "worktree"), "worktree_removed", 0, 0, "", item)
    return removed
