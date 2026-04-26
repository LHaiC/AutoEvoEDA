from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json

from evoharness.config import load_config
from evoharness.events import append_event


def _repo(config_path: Path) -> Path:
    cfg = load_config(config_path)
    return (config_path.parent / cfg.project.repo).resolve()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def session_dir(repo: Path) -> Path:
    return repo / ".evo" / "session"


def state_path(repo: Path) -> Path:
    return session_dir(repo) / "state.json"


def inbox_path(repo: Path) -> Path:
    return session_dir(repo) / "inbox.jsonl"


def read_state(repo: Path) -> dict[str, Any]:
    path = state_path(repo)
    if path.exists():
        return json.loads(path.read_text())
    return {"status": "running", "updated_at": _now()}


def write_state(repo: Path, state: dict[str, Any]) -> None:
    path = state_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    state["updated_at"] = _now()
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def ensure_session(repo: Path) -> dict[str, Any]:
    state = read_state(repo)
    write_state(repo, state)
    return state


def session_status(config_path: Path) -> dict[str, Any]:
    return ensure_session(_repo(config_path))


def set_session_status(config_path: Path, status: str) -> dict[str, Any]:
    repo = _repo(config_path)
    state = read_state(repo)
    state["status"] = status
    write_state(repo, state)
    append_event(repo, "session", f"session_{status}", 0, 0, "", {"status": status})
    return state


def add_session_comment(config_path: Path, text: str) -> dict[str, Any]:
    repo = _repo(config_path)
    ensure_session(repo)
    entry = {"time": _now(), "type": "human_comment", "text": text}
    path = inbox_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    append_event(repo, "session", "human_comment", 0, 0, "", {"text": text})
    return entry


def recent_inbox(repo: Path, count: int = 5) -> list[dict[str, Any]]:
    path = inbox_path(repo)
    if not path.exists():
        return []
    lines = [line for line in path.read_text().splitlines() if line.strip()]
    return [json.loads(line) for line in lines[-count:]]


def assert_not_paused(config_path: Path) -> None:
    repo = _repo(config_path)
    state = read_state(repo)
    if state.get("status") == "paused":
        raise RuntimeError("session is paused; run `evo session resume` before scheduling candidates")
