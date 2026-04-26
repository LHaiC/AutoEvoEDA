from __future__ import annotations

from pathlib import Path
import json
import time

from evoharness.config import EvoConfig, load_config
from evoharness.events import append_event
from evoharness.pipeline.cycle import run_one_cycle
from evoharness.reports import write_project_indexes
from evoharness.session import ensure_session, read_state


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _next_cycle(repo: Path) -> int:
    history = repo / ".evo" / "history.jsonl"
    if not history.exists():
        return 1
    cycles = []
    for line in history.read_text().splitlines():
        if line.strip():
            record = json.loads(line)
            if "decision" in record and "cycle" in record:
                cycles.append(int(record["cycle"]))
    return max(cycles, default=0) + 1


def run_daemon(config_path: Path, max_cycles: int = 0, sleep_s: float = 60.0, human_review: bool = False) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    ensure_session(repo)
    append_event(repo, "daemon", "daemon_started", 0, 0, "", {"max_cycles": max_cycles, "sleep_s": sleep_s})

    completed_cycles = 0
    while max_cycles <= 0 or completed_cycles < max_cycles:
        cfg = load_config(config_path)
        repo = _repo(config_path, cfg)
        state = read_state(repo)
        if state.get("status") == "paused":
            append_event(repo, "daemon", "daemon_paused", 0, 0, "", {"completed_cycles": completed_cycles})
            write_project_indexes(repo)
            return

        cycle = _next_cycle(repo)
        pool_size = cfg.pool.size if cfg.pool.enabled else 1
        for candidate_index in range(1, pool_size + 1):
            state = read_state(repo)
            if state.get("status") == "paused":
                append_event(repo, "daemon", "daemon_paused", 0, 0, "", {"completed_cycles": completed_cycles})
                write_project_indexes(repo)
                return
            run_one_cycle(config_path, cfg, cycle, candidate_index, pool_size, human_review)

        completed_cycles += 1
        append_event(repo, "daemon", "daemon_cycle_finished", cycle, 0, "", {"completed_cycles": completed_cycles})
        write_project_indexes(repo)
        if max_cycles <= 0 or completed_cycles < max_cycles:
            time.sleep(max(0.0, sleep_s))

    append_event(repo, "daemon", "daemon_stopped", 0, 0, "", {"completed_cycles": completed_cycles})
