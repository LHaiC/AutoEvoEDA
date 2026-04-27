#!/usr/bin/env bash
set -euo pipefail
root="$AUTOEVO_CANDIDATE_ROOT/ghypart"
results="$AUTOEVO_CANDIDATE_ROOT/results"
mkdir -p "$results"
"$root/build/gHyPart" > "$results/startup.txt" 2>&1
grep -F "Run the code by typing" "$results/startup.txt" >/dev/null
python - <<'PY'
import json
import os
from pathlib import Path
root = Path(os.environ["AUTOEVO_CANDIDATE_ROOT"])
(root / "results" / "correctness.json").write_text(json.dumps({"startup_smoke": True}, indent=2) + "\n")
PY
