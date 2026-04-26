from __future__ import annotations

from pathlib import Path
import json
import os
import time

from evoharness.artifacts import append_event, ensure_session, read_history, read_state, set_session_status, write_project_indexes
from evoharness.config import EvoConfig, load_config
from evoharness.pipeline.cycle import run_one_cycle


def _repo(config_path: Path, cfg: EvoConfig) -> Path:
    return (config_path.parent / cfg.project.repo).resolve()


def _next_cycle(repo: Path) -> int:
    cycles = [int(record["cycle"]) for record in read_history(repo) if "decision" in record and "cycle" in record]
    return max(cycles, default=0) + 1


def _lock(repo: Path) -> Path:
    path = repo / ".evo" / "session" / "daemon.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        pid = int(path.read_text())
        if pid > 0 and Path(f"/proc/{pid}").exists():
            raise RuntimeError(f"daemon already running with pid {pid}")
    path.write_text(f"{os.getpid()}\n")
    return path


def _write_active(repo: Path, payload: dict[str, int]) -> None:
    path = repo / ".evo" / "session" / "active.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def run_daemon(config_path: Path, max_cycles: int = 0, sleep_s: float = 60.0, human_review: bool = False) -> None:
    cfg = load_config(config_path)
    repo = _repo(config_path, cfg)
    ensure_session(repo)
    lock = _lock(repo)
    append_event(repo, "daemon", "daemon_started", 0, 0, "", {"max_cycles": max_cycles, "sleep_s": sleep_s})

    completed_cycles = 0
    consecutive_rejects = 0
    active = repo / ".evo" / "session" / "active.json"
    try:
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
            _write_active(repo, {"cycle": cycle, "pool_size": pool_size, "completed_cycles": completed_cycles})
            append_event(repo, "daemon", "daemon_heartbeat", cycle, 0, "", {"completed_cycles": completed_cycles})
            for candidate_index in range(1, pool_size + 1):
                state = read_state(repo)
                if state.get("status") == "paused":
                    append_event(repo, "daemon", "daemon_paused", 0, 0, "", {"completed_cycles": completed_cycles})
                    write_project_indexes(repo)
                    return
                record = run_one_cycle(config_path, cfg, cycle, candidate_index, pool_size, human_review)
                consecutive_rejects = consecutive_rejects + 1 if record["decision"] == "reject" else 0
                if cfg.human.stop_after_consecutive_rejects > 0 and consecutive_rejects >= cfg.human.stop_after_consecutive_rejects:
                    set_session_status(config_path, "paused")
                    append_event(repo, "daemon", "daemon_paused_after_rejects", cycle, candidate_index, "", {"consecutive_rejects": consecutive_rejects})
                    write_project_indexes(repo)
                    return

            completed_cycles += 1
            append_event(repo, "daemon", "daemon_cycle_finished", cycle, 0, "", {"completed_cycles": completed_cycles})
            write_project_indexes(repo)
            if max_cycles <= 0 or completed_cycles < max_cycles:
                time.sleep(max(0.0, sleep_s))

        append_event(repo, "daemon", "daemon_stopped", 0, 0, "", {"completed_cycles": completed_cycles})
    finally:
        lock.unlink(missing_ok=True)
        active.unlink(missing_ok=True)
