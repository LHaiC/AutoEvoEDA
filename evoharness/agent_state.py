from __future__ import annotations

from pathlib import Path
from typing import Any
from datetime import datetime, timezone
import json


def agent_dir(repo: Path, agent_id: str) -> Path:
    return repo / ".evo" / "agents" / agent_id


def read_agent_memory(repo: Path, agent_id: str) -> str:
    path = agent_dir(repo, agent_id) / "memory.md"
    return path.read_text().strip() if path.exists() else ""


def write_agent_exchange(repo: Path, agent_id: str, prompt: str, stdout: str, stderr: str, ok: bool) -> None:
    directory = agent_dir(repo, agent_id)
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "last_prompt.md").write_text(prompt)
    (directory / "last_response.md").write_text(stdout)
    transcript = directory / "transcript.jsonl"
    record: dict[str, Any] = {
        "time": datetime.now(timezone.utc).isoformat(),
        "ok": ok,
        "prompt_path": "last_prompt.md",
        "response_path": "last_response.md",
        "stderr": stderr,
    }
    with transcript.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    memory = directory / "memory.md"
    if not memory.exists():
        memory.write_text(f"# Agent Memory: {agent_id}\n\nAdd durable role-specific notes here.\n")
