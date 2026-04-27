from __future__ import annotations

import json
import os
from pathlib import Path

results = Path(os.environ["AUTOEVO_CANDIDATE_ROOT"]) / "results"
correctness = json.loads((results / "correctness.json").read_text())
perf = json.loads((results / "perf.json").read_text())
accepted = correctness["weighted_summary"] and perf["weighted_total_s"] > 0
(results / "reward.json").write_text(json.dumps({"accepted": accepted, "score": 1.0 / perf["weighted_total_s"]}, indent=2, sort_keys=True) + "\n")
if not accepted:
    raise SystemExit("weighted support reward rejected")
