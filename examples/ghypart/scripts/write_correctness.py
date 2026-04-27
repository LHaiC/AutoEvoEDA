from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

results = Path(sys.argv[1])
weighted_input = Path(sys.argv[2])
weighted = (results / "weighted.stdout").read_text()
unweighted = (results / "unweighted.stdout").read_text()
summary = subprocess.check_output([sys.executable, str(Path(__file__).with_name("hgr_weight_summary.py")), str(weighted_input)], text=True).strip()
payload = {
    "startup_smoke": (results / "startup.txt").exists(),
    "unweighted_finished": "finish all." in unweighted,
    "weighted_finished": "finish all." in weighted,
    "weighted_summary": summary in weighted,
    "expected_weighted_summary": summary,
}
(results / "correctness.json").write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
if not all(payload[key] for key in ["startup_smoke", "unweighted_finished", "weighted_finished", "weighted_summary"]):
    raise SystemExit("weighted regression failed")
