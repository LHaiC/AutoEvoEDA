from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
import json

from evoharness.config import ResultFilesConfig


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
