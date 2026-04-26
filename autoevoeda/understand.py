from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from autoevoeda.agents.codex import CodexBackend, run_codex_role
from autoevoeda.artifacts import append_event, read_agent_memory, write_agent_exchange, write_project_indexes
from autoevoeda.config import EvoConfig, load_config
from autoevoeda.workspace.git import git


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n")


def _safe_name(path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", path.strip("/") or "root")


def _git_lines(repo: Path, args: list[str]) -> list[str]:
    out = git(args, cwd=repo)
    return out.splitlines() if out else []


def _memory_dir(repo: Path) -> Path:
    path = repo / ".evo" / "memory" / "code"
    for rel in [".", "modules", "workflows", "bootstrap"]:
        (path / rel).mkdir(parents=True, exist_ok=True)
    return path


def _tracked_files(repo: Path, prefix: str, changed_only: bool) -> list[str]:
    args = ["ls-files", "--modified", "--others", "--exclude-standard", prefix] if changed_only else ["ls-files", prefix]
    return _git_lines(repo, args)


def _module_doc(repo: Path, prefix: str, changed_only: bool) -> str:
    files = _tracked_files(repo, prefix, changed_only)
    return "\n".join([
        f"# Module: {prefix}",
        "",
        f"Updated: {datetime.now(timezone.utc).isoformat()}",
        f"Files: {len(files)}",
        "",
        "## Key Files",
        *[f"- `{path}`" for path in files[:40]],
    ])


def _write_seed_memory(memory: Path, cfg: EvoConfig, repo: Path, modules: list[str], changed_only: bool) -> list[tuple[str, str]]:
    files = _git_lines(repo, ["ls-files"])
    domains = [f"- `{agent.name}`: {', '.join(agent.allowed_paths)}" for agent in cfg.domain_agents]
    _write(memory / "bootstrap" / "repo_profile.md", "\n".join([
        "# Repository Profile", "", f"Project: `{cfg.project.name}`", f"Tracked files: {len(files)}", "", "## Top-Level Entries", *[f"- `{p}`" for p in sorted({f.split('/', 1)[0] for f in files})],
    ]))
    _write(memory / "bootstrap" / "safe_edit_protocol.md", "\n".join([
        "# Safe Edit Protocol", "", "## Allowed Paths", *[f"- `{p}`" for p in cfg.guards.allowed_paths], "", "## Forbidden Paths", *[f"- `{p}`" for p in cfg.guards.forbidden_paths], "", "## Domain Agents", *(domains or ["No domain agents configured."]),
    ]))
    links = []
    for prefix in modules:
        name = _safe_name(prefix) + ".md"
        links.append((prefix, name))
        _write(memory / "modules" / name, _module_doc(repo, prefix, changed_only))
    return links


def _write_index(memory: Path, repo: Path, cfg: EvoConfig, links: list[tuple[str, str]]) -> None:
    _write(memory / "index.md", "\n".join([
        "# Code Understanding Index", "", "## Modules", *[f"- `{prefix}` -> `modules/{name}`" for prefix, name in links], "", "## Core", "- `architecture.md`", "- `invariants.md`", "- `workflows/build.md`", "- `workflows/regression.md`", "- `workflows/benchmark.md`", "", "## Understanding Agent Memory", read_agent_memory(repo, cfg.agents.code_understanding.session_id) or "No notes yet.",
    ]))


def _write_core_docs(memory: Path, cfg: EvoConfig) -> None:
    _write(memory / "architecture.md", "\n".join(["# Architecture", "", "## Allowed Subsystems", *[f"- `{p}`" for p in cfg.guards.allowed_paths]]))
    _write(memory / "invariants.md", "\n".join(["# Invariants", "", "- Adapter scripts decide correctness, performance, and reward.", "- Candidates must not edit forbidden paths or weaken evaluator logic.", "- Correctness gates run before reward."]))
    _write(memory / "workflows" / "build.md", f"# Build Workflow\n\n```bash\n{cfg.pipeline.build}\n```")
    _write(memory / "workflows" / "regression.md", f"# Regression Workflow\n\n```bash\n{cfg.pipeline.regression}\n{cfg.pipeline.compare_regression}\n```")
    _write(memory / "workflows" / "benchmark.md", f"# Benchmark Workflow\n\n```bash\n{cfg.pipeline.perf}\n{cfg.pipeline.reward}\n```")


def _understanding_prompt(memory: Path) -> str:
    parts = ["You are the code-understanding agent. Improve these repository-memory files without editing source code."]
    for rel in ["index.md", "architecture.md", "invariants.md", "bootstrap/repo_profile.md", "bootstrap/safe_edit_protocol.md"]:
        path = memory / rel
        parts.extend(["", f"# {rel}", path.read_text()])
    return "\n".join(parts).rstrip() + "\n"


def run_understand(config_path: Path, use_agent: bool = False, modules: list[str] | None = None, changed_only: bool = False) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    memory = _memory_dir(repo)
    links = _write_seed_memory(memory, cfg, repo, modules or cfg.guards.allowed_paths, changed_only)
    _write_core_docs(memory, cfg)
    _write_index(memory, repo, cfg, links)
    append_event(repo, "understand", "code_understanding_written", 0, 0, "", {"modules": len(links), "agent_requested": use_agent})

    if use_agent:
        agent_id = cfg.agents.code_understanding.session_id
        agent = CodexBackend(sandbox=cfg.agent.sandbox, model=cfg.agent.model, profile=cfg.agent.profile, config=cfg.agent.config)
        prompt = _understanding_prompt(memory)
        result = run_codex_role(repo, cfg.agents.code_understanding, agent, prompt, repo, cfg.agent.timeout_s)
        write_agent_exchange(repo, agent_id, prompt, result.stdout, result.stderr, result.ok)
        _write(memory / "agent_notes.md", result.stdout)
        append_event(repo, "understand", "code_understanding_agent_finished", 0, 0, "", {"agent_id": agent_id, "ok": result.ok})
        if not result.ok:
            raise RuntimeError(f"code understanding agent failed; see .evo/agents/{agent_id}/last_response.md")

    write_project_indexes(repo)
