from __future__ import annotations

from pathlib import Path
import re

from evoharness.config import EvoConfig, load_config
from evoharness.events import append_event
from evoharness.reports import write_project_indexes
from evoharness.workspace.git import git


def _safe_name(path: str) -> str:
    name = path.strip("/") or "root"
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _memory_dir(repo: Path) -> Path:
    path = repo / ".evo" / "memory" / "code"
    path.mkdir(parents=True, exist_ok=True)
    (path / "modules").mkdir(exist_ok=True)
    (path / "workflows").mkdir(exist_ok=True)
    return path


def _tracked_files(repo: Path, prefix: str) -> list[str]:
    out = git(["ls-files", prefix], cwd=repo)
    return out.splitlines() if out else []


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def _module_doc(repo: Path, prefix: str) -> str:
    files = _tracked_files(repo, prefix)
    sample = files[:30]
    return "\n".join(
        [
            f"# Module: {prefix}",
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


def run_understand(config_path: Path) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    memory = _memory_dir(repo)

    module_paths = cfg.guards.allowed_paths
    module_links = []
    for prefix in module_paths:
        name = _safe_name(prefix) + ".md"
        module_links.append((prefix, name))
        _write(memory / "modules" / name, _module_doc(repo, prefix))

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

    append_event(repo, "understand", "code_understanding_written", 0, 0, "", {"modules": len(module_links)})
    write_project_indexes(repo)
