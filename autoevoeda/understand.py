from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re

from autoevoeda.agents.codex import AgentResult, CodexBackend, run_codex_role
from autoevoeda.artifacts import append_event, handoff_error, write_agent_exchange, write_project_indexes
from autoevoeda.config import EvoConfig, WorkspaceRepoConfig, load_config
from autoevoeda.workspace.git import git

PHASES = ["scaffold", "profile", "relationships", "guidance", "role_memory", "review"]
PROFILE_SECTIONS = ["Purpose", "Entry Points", "Key Data Structures", "Cross-Repo Contracts", "ECO/Incremental Relevance", "Risks", "Recommended Edit Targets", "Do Not Touch"]


def _log(message: str) -> None:
    print(f"[evo-understand] {message}", flush=True)


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def _tail(path: Path, count: int = 10) -> list[str]:
    return path.read_text().splitlines()[-count:] if path.exists() else []


def _safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "root")


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    out = git(args, cwd=repo)
    return out.splitlines() if out else []


def _source_root(config_path: Path, cfg: EvoConfig) -> Path:
    root = Path(cfg.workspace.source_root)
    return (config_path.parent / root).resolve() if not root.is_absolute() else root.resolve()


def _is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def _memory_dir(repo: Path) -> Path:
    path = repo / ".evo" / "memory" / "code"
    for directory in [path, path / "raw_index", path / "profile", path / "modules", path / "relationships", path / "review", repo / ".evo" / "memory" / "guidance"]:
        directory.mkdir(parents=True, exist_ok=True)
    return path


def _repo_for_prefix(cfg: EvoConfig, prefix: str) -> WorkspaceRepoConfig | None:
    head = prefix.strip("/").split("/", 1)[0]
    for repo_cfg in cfg.workspace.repos:
        if head in {repo_cfg.name, repo_cfg.path}:
            return repo_cfg
    return None


def _filesystem_files(root: Path, prefix: str) -> list[str]:
    base = root / prefix
    if not base.exists():
        return []
    ignored_suffixes = {".a", ".o", ".so", ".rlib", ".rmeta", ".pyc"}
    ignored_dirs = {"target", "results", "build", "CMakeFiles", "__pycache__"}
    rows = []
    for item in sorted(base.rglob("*")):
        if item.is_file() and item.suffix not in ignored_suffixes and not any(part in ignored_dirs for part in item.relative_to(root).parts):
            rows.append(str(item.relative_to(root)))
    return rows


def _module_files(config_path: Path, cfg: EvoConfig, repo: Path, prefix: str, changed_only: bool) -> list[str]:
    if cfg.workspace.mode != "multi_repo":
        args = ["ls-files", "--modified", "--others", "--exclude-standard", prefix] if changed_only else ["ls-files", prefix]
        return _git_lines(repo, args)
    source_root = _source_root(config_path, cfg)
    head, sep, tail = prefix.partition("/")
    repo_cfg = _repo_for_prefix(cfg, prefix)
    if repo_cfg:
        source = source_root / repo_cfg.path
        rel = tail if sep else ""
        if _is_git_repo(source):
            args = ["ls-files", "--modified", "--others", "--exclude-standard", rel] if changed_only else ["ls-files", rel]
            return [f"{head}/{row}" for row in _git_lines(source, args)]
        return [f"{head}/{row}" for row in _filesystem_files(source, rel)]
    return [] if changed_only else _filesystem_files(source_root, prefix)


def _default_modules(config_path: Path, cfg: EvoConfig, repo: Path) -> list[str]:
    if cfg.workspace.mode != "multi_repo":
        return cfg.guards.allowed_paths
    repo_heads = {repo_cfg.name for repo_cfg in cfg.workspace.repos} | {repo_cfg.path for repo_cfg in cfg.workspace.repos}
    modules = [f"{repo_cfg.name}/{path.strip('/')}/" for repo_cfg in cfg.workspace.repos for path in repo_cfg.allowed_paths]
    for path in [*cfg.guards.allowed_paths, *cfg.workspace.materialize.copy, *cfg.workspace.materialize.symlink]:
        if path.strip("/").split("/", 1)[0] not in repo_heads:
            modules.append(path)
    return list(dict.fromkeys(modules))


def _all_files(config_path: Path, cfg: EvoConfig, repo: Path, modules: list[str], changed_only: bool) -> dict[str, list[str]]:
    return {module: _module_files(config_path, cfg, repo, module, changed_only) for module in modules}


def _module_commit(config_path: Path, cfg: EvoConfig, repo: Path, module: str) -> str:
    if cfg.workspace.mode != "multi_repo":
        return git(["rev-parse", "HEAD"], cwd=repo)
    repo_cfg = _repo_for_prefix(cfg, module)
    source = _source_root(config_path, cfg) / repo_cfg.path if repo_cfg else _source_root(config_path, cfg)
    return git(["rev-parse", "HEAD"], cwd=source) if _is_git_repo(source) else ""


def _source_status(config_path: Path, cfg: EvoConfig, repo: Path) -> dict[str, str]:
    if cfg.workspace.mode != "multi_repo":
        return {"root": git(["status", "--porcelain", "--", ":!.evo"], cwd=repo)}
    source_root = _source_root(config_path, cfg)
    return {repo_cfg.name: git(["status", "--porcelain"], cwd=source_root / repo_cfg.path) for repo_cfg in cfg.workspace.repos if _is_git_repo(source_root / repo_cfg.path)}


def _target_docs(repo: Path, cfg: EvoConfig, phase: str) -> list[Path]:
    code = repo / ".evo" / "memory" / "code"
    guidance = repo / ".evo" / "memory" / "guidance"
    role_files = [repo / ".evo" / "agents" / agent.session_id / "memory.md" for agent in [cfg.agents.planner, cfg.agents.coder, cfg.agents.reviewer, cfg.agents.code_understanding]]
    module_docs = [code / "modules" / path.name for path in sorted((code / "raw_index").glob("*.md"))]
    targets = {
        "profile": [repo / path for path in cfg.understanding.profile_docs] + module_docs,
        "relationships": [repo / path for path in cfg.understanding.relationship_docs],
        "guidance": [repo / path for path in cfg.understanding.guidance_docs],
        "role_memory": [repo / path for path in cfg.understanding.mutable_files] + role_files,
        "review": [repo / path for path in cfg.understanding.review_docs],
    }
    default_targets = {
        "profile": [code / "profile" / "repository.md", *module_docs],
        "relationships": [code / "relationships" / name for name in ["callgraph.md", "dataflow.md", "interfaces.md", "validation_loop.md"]],
        "guidance": [guidance / name for name in ["programming_guidance.md", "forbidden_rules.md", "validation.md"]],
        "role_memory": [repo / ".evo" / "roadmap.md", repo / cfg.memory.project_memory, repo / cfg.memory.accepted_patterns, repo / cfg.rulebase_path] + role_files,
        "review": [code / "review" / "understanding_review.md", code / "review" / "coverage.json"],
    }
    return targets.get(phase) or default_targets[phase]


def _write_scaffold(config_path: Path, repo: Path, cfg: EvoConfig, files: dict[str, list[str]]) -> None:
    memory = _memory_dir(repo)
    _write(memory / "manifest.json", json.dumps({"project": cfg.project.name, "modules": {k: len(v) for k, v in files.items()}, "generated_at": datetime.now(timezone.utc).isoformat()}, indent=2, sort_keys=True))
    _write(memory / "index.md", "\n".join(["# Code Understanding Index", "", "## Raw Index", *[f"- `{module}` -> `raw_index/{_safe_name(module)}.md` ({len(rows)} files)" for module, rows in files.items()], "", "## Agent-Owned Outputs", "- `profile/` and `modules/`", "- `relationships/`", "- `.evo/memory/guidance/`", "- role memories under `.evo/agents/`", "- `review/`"]))
    coverage = {
        module: {
            "files": len(rows),
            "sample_files": rows[:20],
            "last_reviewed_commit": _module_commit(config_path, cfg, repo, module),
            "confidence": "raw-index-only",
            "stale_reason": "agent profile not reviewed",
            "token_budget": min(6000, max(600, len(rows) * 80)),
        }
        for module, rows in files.items()
    }
    _write(memory / "coverage.json", json.dumps(coverage, indent=2, sort_keys=True))
    for module, rows in files.items():
        _write(memory / "raw_index" / f"{_safe_name(module)}.md", "\n".join([f"# Raw Index: {module}", "", f"Files: {len(rows)}", "", *[f"- `{row}`" for row in rows]]))
    targets = {phase: [str(path.relative_to(repo)) for path in _target_docs(repo, cfg, phase)] for phase in PHASES[1:]}
    _write(memory / "understanding_targets.json", json.dumps(targets, indent=2, sort_keys=True))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() and path.is_file() else ""


def _snapshot(paths: list[Path]) -> dict[Path, str]:
    return {path: _hash(path) for path in paths}


def _changed(before: dict[Path, str]) -> list[Path]:
    return [path for path, digest in before.items() if _hash(path) != digest]


def _phase_prompt(repo: Path, cfg: EvoConfig, phase: str, targets: list[Path]) -> str:
    rel_targets = [str(path.relative_to(repo)) for path in targets]
    raw_index = (repo / ".evo" / "memory" / "code" / "index.md").read_text()
    return "\n".join([
        f"You are the code-understanding agent for phase `{phase}`.",
        "",
        "You must create or edit the target memory files directly. Do not only respond in stdout.",
        "Do not edit source repos, evaluator scripts, golden data, prompts, history, events, or run artifacts.",
        "Use source code and configured read-only context only as evidence.",
        "Avoid generic summaries; write code-level facts with file/function evidence.",
        "",
        "## Target Files",
        *[f"- `{path}`" for path in rel_targets],
        "",
        "## Required Module Profile Sections",
        *[f"- {section}" for section in PROFILE_SECTIONS],
        "",
        "## Raw Index",
        raw_index,
        "",
        "## Agent-Readable Workflow Files",
        "- `.evo/history.jsonl`",
        "- `.evo/memory/lessons.jsonl`",
        "- `.evo/brief.md`",
        "- `.evo/roadmap.md`",
        "- `.evo/agents/interactions.jsonl`",
        "",
        "## Recent History",
        *(_tail(repo / ".evo" / "history.jsonl") or ["No prior decisions."]),
        "",
        "## Recent Lessons",
        *(_tail(repo / ".evo" / "memory" / "lessons.jsonl") or ["No prior lessons."]),
        "",
        "## Recent Agent Interactions",
        *(_tail(repo / ".evo" / "agents" / "interactions.jsonl") or ["No prior agent interactions."]),
        "",
        "Final response: list edited memory files and any source files inspected.",
        "End with two single-line fields:",
        "handoff_summary: <one concise sentence about what you did>",
        "lesson_learned: <one concise reusable lesson, or \"none\">",
    ])


def _validate_phase(repo: Path, phase: str, changed: list[Path], targets: list[Path]) -> None:
    missing = [path for path in targets if not path.exists()]
    if missing:
        raise RuntimeError("understanding phase missing target files: " + ", ".join(str(path.relative_to(repo)) for path in missing))
    unchanged = [path for path in targets if path not in changed]
    if unchanged:
        raise RuntimeError("understanding phase did not update target files: " + ", ".join(str(path.relative_to(repo)) for path in unchanged))
    for path in targets:
        if path.suffix != ".md":
            continue
        text = path.read_text()
        if len(text.strip()) < 400 or "placeholder" in text.lower():
            raise RuntimeError(f"understanding output is too shallow: {path.relative_to(repo)}")
        if "/modules/" in str(path):
            missing_sections = [section for section in PROFILE_SECTIONS if f"## {section}" not in text]
            if missing_sections:
                raise RuntimeError(f"understanding output missing sections in {path.relative_to(repo)}: {', '.join(missing_sections)}")


def _run_agent_phase(config_path: Path, cfg: EvoConfig, repo: Path, phase: str) -> None:
    targets = _target_docs(repo, cfg, phase)
    before = _snapshot(targets)
    source_before = _source_status(config_path, cfg, repo)
    source_dirs = [str(_source_root(config_path, cfg))] if cfg.workspace.mode == "multi_repo" else [str(repo)]
    source_dirs.extend(str((config_path.parent / path).resolve()) for path in cfg.understanding.read_only_context)
    agent_config = {**cfg.agent.config, "add_dirs": [*cfg.agent.config.get("add_dirs", []), *source_dirs]}
    agent = CodexBackend(sandbox=cfg.agent.sandbox, model=cfg.agent.model, profile=cfg.agent.profile, config=agent_config)
    prompt = _phase_prompt(repo, cfg, phase, targets)
    result = run_codex_role(repo, cfg.agents.code_understanding, agent, prompt, repo, cfg.agent.timeout_s)
    error = handoff_error(result.ok, result.stdout)
    if error:
        result = AgentResult(False, result.stdout, error, result.session_mode)
    write_agent_exchange(repo, cfg.agents.code_understanding.session_id, prompt, result.stdout, result.stderr, result.ok, "understand", phase, cfg.memory.lessons if cfg.memory.enabled else "")
    append_event(repo, "understand", "understanding_phase_finished", 0, 0, "", {"phase": phase, "ok": result.ok})
    if not result.ok:
        raise RuntimeError(f"understanding phase failed: {phase}; see .evo/agents/{cfg.agents.code_understanding.session_id}/last_response.md")
    if _source_status(config_path, cfg, repo) != source_before:
        raise RuntimeError(f"understanding phase modified source workspace: {phase}")
    _validate_phase(repo, phase, _changed(before), targets)


def run_understand(config_path: Path, phase: str = "all", modules: list[str] | None = None, changed_only: bool = False) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    selected = cfg.understanding.phases if phase == "all" else [phase]
    unknown = [item for item in selected if item not in PHASES]
    if unknown:
        raise ValueError("unknown understanding phase: " + ", ".join(unknown))
    module_files = _all_files(config_path, cfg, repo, modules or _default_modules(config_path, cfg, repo), changed_only)
    if "scaffold" in selected:
        _log(f"phase=scaffold modules={len(module_files)}")
        _write_scaffold(config_path, repo, cfg, module_files)
        append_event(repo, "understand", "understanding_scaffold_written", 0, 0, "", {"modules": len(module_files)})
    for item in selected:
        if item != "scaffold":
            _log(f"phase={item} agent_start")
            _run_agent_phase(config_path, cfg, repo, item)
            _log(f"phase={item} agent_done")
    write_project_indexes(repo)
    _log("done")
