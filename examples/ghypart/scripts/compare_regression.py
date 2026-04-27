from __future__ import annotations

import json
import os
from pathlib import Path

data = json.loads((Path(os.environ["AUTOEVO_CANDIDATE_ROOT"]) / "results" / "correctness.json").read_text())
required = ["startup_smoke", "unweighted_finished", "weighted_finished", "weighted_summary"]
if any(data.get(key) is not True for key in required):
    raise SystemExit("weighted regression failed")
