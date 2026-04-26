from __future__ import annotations

from pathlib import Path
from typing import Any
import json


def append_history(repo: Path, record: dict[str, Any]) -> Path:
    evo_dir = repo / ".evo"
    evo_dir.mkdir(parents=True, exist_ok=True)
    history = evo_dir / "history.jsonl"
    with history.open("a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    return history
