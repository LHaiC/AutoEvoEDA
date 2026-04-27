from __future__ import annotations

import json
import os
from pathlib import Path

data = json.loads((Path(os.environ["AUTOEVO_CANDIDATE_ROOT"]) / "results" / "correctness.json").read_text())
if data != {"startup_smoke": True}:
    raise SystemExit("startup smoke failed")
