from __future__ import annotations

import json
import re
import sys
from pathlib import Path

results = Path(sys.argv[1])
text = (results / "weighted.stdout").read_text()
match = re.search(r"Total (?:k-way partition |execution )time(?: \(s\))?:\s*([0-9.]+)", text)
if not match:
    raise SystemExit("missing weighted total execution time")
(results / "perf.json").write_text(json.dumps({"weighted_total_s": float(match.group(1))}, indent=2, sort_keys=True) + "\n")
