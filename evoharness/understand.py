from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re

from evoharness.agents.codex import CodexBackend, run_codex_role
from evoharness.artifacts import append_event, read_agent_memory, write_agent_exchange, write_project_indexes
from evoharness.config import EvoConfig, load_config
from evoharness.workspace.git import git


def _safe_name(path: str) -> str:
    name = path.strip("/") or "root"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _memory_dir(repo: Path) -> Path:
    path = repo / ".evo" / "memory" / "code"
    path.mkdir(parents=True, exist_ok=True)
    for name in ["modules", "workflows", "bootstrap"]:
        (path / name).mkdir(exist_ok=True)
    return path


def _tracked_files(repo: Path, prefix: str, changed_only: bool = False) -> list[str]:
    args = ["ls-files", "--modified", "--others", "--exclude-standard", prefix] if changed_only else ["ls-files", prefix]
    out = git(args, cwd=repo)
    return out.splitlines() if out else []


def _all_tracked_files(repo: Path) -> list[str]:
    out = git(["ls-files"], cwd=repo)
    return out.splitlines() if out else []


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _bootstrap_docs(cfg: EvoConfig, files: list[str]) -> dict[str, str]:
    domains = cfg.domain_agents
    domain_lines = [f"- `{agent.name}`: `{agent.prompt_file}`, paths: {', '.join(agent.allowed_paths)}" for agent in domains]
    return {
        "repo_profile.md": "\n".join([
            "# Cycle-0 Repository Profile", "", f"Project: `{cfg.project.name}`", f"Champion branch: `{cfg.project.champion_branch}`", f"Tracked files: {len(files)}", "", "## Top-Level Entries", "", *[f"- `{path}`" for path in sorted({item.split('/', 1)[0] for item in files})], "",
        ]),
        "build_conventions.md": "\n".join([
            "# Build Conventions", "", "## Configured Commands", "", f"- Build: `{cfg.pipeline.build}`", f"- Regression: `{cfg.pipeline.regression}`", f"- Compare: `{cfg.pipeline.compare_regression}`", f"- Performance: `{cfg.pipeline.perf}`", f"- Reward: `{cfg.pipeline.reward}`", "", "Adapter scripts own project-specific build conventions and must keep outputs deterministic.", "",
        ]),
        "command_interfaces.md": "\n".join([
            "# Command Interfaces", "", "Document project command registration, new function patterns, build-file updates, and API invariants here before long autonomous runs.", "", "For ABC-style adapters, this is where command registration and module.make conventions belong.", "",
        ]),
        "subsystem_map.md": "\n".join([
            "# Subsystem Map", "", "## Global Allowed Paths", "", *[f"- `{path}`" for path in cfg.guards.allowed_paths], "", "## Domain Agents", "", *(domain_lines or ["No domain agents configured."]), "",
        ]),
        "safe_edit_protocol.md": "\n".join([
            "# Safe Edit Protocol", "", "- Do not edit forbidden paths, evaluator scripts, benchmark data, golden outputs, or reward logic unless the adapter explicitly allows it.", "- Domain agents must stay inside their configured allowed paths.", "- Domain-agent responses must include hypothesis, target_files, expected_metric_impact, and rollback_risk.", "- Build, regression, compare, performance, and reward scripts decide acceptance.", "",
        ]),
        "prior_studies.md": "\n".join([
            "# External Prior-Study Memory", "", "Record external algorithms, papers, repositories, and integration notes here as structured guidance.", "", "Do not copy incompatible implementations into the project; use prior work to identify safe hypotheses and injection points.", "",
        ]),
        "abc_tutorial.md": "\n".join([
            "# Adapter Tutorial Memory", "", "Project adapters should fill this file with project-specific tutorials for adding commands, functions, build entries, and safe API usage.", "", "For ABC-style adapters, include module.make, command registration, CEC expectations, and synthesis-flow conventions.", "",
        ]),
    }


def _module_doc(repo: Path, prefix: str, changed_only: bool) -> str:
    files = _tracked_files(repo, prefix, changed_only)
    sample = files[:30]
    return "\n".join(
        [
            f"# Module: {prefix}",
            "",
            f"Updated at: {datetime.now(timezone.utc).isoformat()}",
            "",
            "## Responsibility",
            "",
            "Summarize this module before enabling autonomous edits.",
            "",
            "## File Count",
            "",
            str(len(files)),
            "",
            "## Key Files",
            "",
            *[f"- `{path}`" for path in sample],
            "",
            "## Safe Edit Areas",
            "",
            f"- `{prefix}` is allowed by the current adapter guard.",
            "",
            "## Risky Areas",
            "",
            "- Build scripts, evaluator scripts, benchmark data, and golden outputs remain forbidden unless the adapter says otherwise.",
            "",
            "## Open Questions",
            "",
            "- Which functions are core extension points?",
            "- Which invariants must not change?",
            "",
        ]
    )


def _understanding_prompt(memory: Path) -> str:
    parts = ["You are the code-understanding agent. Enrich the deterministic repository memory below."]
    for rel in [
        "index.md",
        "architecture.md",
        "build_system.md",
        "invariants.md",
        "extension_points.md",
        "workflows/build.md",
        "workflows/regression.md",
        "workflows/benchmark.md",
        "bootstrap/repo_profile.md",
        "bootstrap/subsystem_map.md",
        "bootstrap/safe_edit_protocol.md",
        "bootstrap/prior_studies.md",
        "bootstrap/abc_tutorial.md",
    ]:
        path = memory / rel
        if path.exists():
            parts.extend(["", f"# {rel}", path.read_text()])
    return "\n".join(parts).rstrip() + "\n"


def run_understand(
    config_path: Path,
    use_agent: bool = False,
    modules: list[str] | None = None,
    changed_only: bool = False,
) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    memory = _memory_dir(repo)

    files = _all_tracked_files(repo)
    for name, content in _bootstrap_docs(cfg, files).items():
        _write(memory / "bootstrap" / name, content)

    module_paths = modules or cfg.guards.allowed_paths
    module_links = []
    for prefix in module_paths:
        name = _safe_name(prefix) + ".md"
        module_links.append((prefix, name))
        _write(memory / "modules" / name, _module_doc(repo, prefix, changed_only))

    understanding_memory = read_agent_memory(repo, cfg.agents.code_understanding.session_id)
    _write(
        memory / "index.md",
        "\n".join(
            [
                "# Code Understanding Index",
                "",
                "## Modules",
                "",
                *[f"- `{prefix}` -> `modules/{name}`" for prefix, name in module_links],
                "",
                "## Workflows",
                "",
                "- `workflows/build.md`",
                "- `workflows/regression.md`",
                "- `workflows/benchmark.md`",
                "",
                "## Core Docs",
                "",
                "- `architecture.md`",
                "- `build_system.md`",
                "- `invariants.md`",
                "- `extension_points.md`",
                "",
                "## Bootstrap Docs",
                "",
                "- `bootstrap/repo_profile.md`",
                "- `bootstrap/build_conventions.md`",
                "- `bootstrap/command_interfaces.md`",
                "- `bootstrap/subsystem_map.md`",
                "- `bootstrap/safe_edit_protocol.md`",
                "- `bootstrap/prior_studies.md`",
                "- `bootstrap/abc_tutorial.md`",
                "",
                "## Understanding Agent Memory",
                "",
                understanding_memory or "No framework-level understanding agent memory yet.",
                "",
            ]
        ),
    )

    _write(
        memory / "architecture.md",
        "\n".join(
            [
                "# Architecture Memory",
                "",
                f"Project: `{cfg.project.name}`",
                f"Champion branch: `{cfg.project.champion_branch}`",
                "",
                "## Allowed Subsystems",
                "",
                *[f"- `{path}`" for path in cfg.guards.allowed_paths],
                "",
                "## Forbidden Areas",
                "",
                *[f"- `{path}`" for path in cfg.guards.forbidden_paths],
                "",
                "## Notes",
                "",
                "This deterministic memory is the seed for later agent-written code understanding summaries.",
                "",
            ]
        ),
    )

    _write(
        memory / "build_system.md",
        "\n".join(
            [
                "# Build System Memory",
                "",
                "## Configured Build Command",
                "",
                f"```bash\n{cfg.pipeline.build}\n```",
                "",
                "## Important Files To Inspect",
                "",
                "- `Makefile`",
                "- `CMakeLists.txt`",
                "- `module.make`",
                "- `pyproject.toml`",
                "",
            ]
        ),
    )

    _write(
        memory / "invariants.md",
        "\n".join(
            [
                "# Invariants",
                "",
                "- Build, regression, benchmark, and reward scripts define acceptance.",
                "- Candidate patches must not weaken evaluator scripts or golden data.",
                "- Correctness gates run before reward is considered.",
                "",
            ]
        ),
    )

    _write(
        memory / "extension_points.md",
        "\n".join(
            [
                "# Extension Points",
                "",
                "## Allowed Edit Roots",
                "",
                *[f"- `{path}`" for path in cfg.guards.allowed_paths],
                "",
                "## Adapter-Owned Logic",
                "",
                *[f"- `{path}`" for path in cfg.guards.forbidden_paths],
                "",
            ]
        ),
    )

    _write(memory / "workflows" / "build.md", f"# Build Workflow\n\n```bash\n{cfg.pipeline.build}\n```\n")
    _write(
        memory / "workflows" / "regression.md",
        "\n".join(
            [
                "# Regression Workflow",
                "",
                f"```bash\n{cfg.pipeline.regression}\n```",
                "",
                "## Compare Step",
                "",
                f"```bash\n{cfg.pipeline.compare_regression}\n```",
                "",
            ]
        ),
    )
    _write(
        memory / "workflows" / "benchmark.md",
        "\n".join(
            [
                "# Benchmark Workflow",
                "",
                f"```bash\n{cfg.pipeline.perf}\n```",
                "",
                "## Reward Step",
                "",
                f"```bash\n{cfg.pipeline.reward}\n```",
                "",
            ]
        ),
    )

    append_event(
        repo,
        "understand",
        "code_understanding_written",
        0,
        0,
        "",
        {"modules": len(module_links), "agent_requested": use_agent},
    )

    if use_agent:
        agent_id = cfg.agents.code_understanding.session_id
        prompt = _understanding_prompt(memory)
        agent = CodexBackend(sandbox=cfg.agent.sandbox)
        result = run_codex_role(repo, cfg.agents.code_understanding, agent, prompt, repo, cfg.agent.timeout_s)
        write_agent_exchange(repo, agent_id, prompt, result.stdout, result.stderr, result.ok)
        _write(memory / "agent_notes.md", result.stdout)
        append_event(
            repo,
            "understand",
            "code_understanding_agent_finished",
            0,
            0,
            "",
            {"agent_id": agent_id, "ok": result.ok},
        )
        if not result.ok:
            raise RuntimeError(f"code understanding agent failed; see .evo/agents/{agent_id}/last_response.md")

    write_project_indexes(repo)
