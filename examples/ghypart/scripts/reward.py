from __future__ import annotations

import json
import os
from pathlib import Path

root = Path(os.environ["AUTOEVO_CANDIDATE_ROOT"])
allow_placeholder = os.environ.get("AUTOEVO_ALLOW_PLACEHOLDER_REWARD") == "1"
(root / "results" / "reward.json").write_text(json.dumps({"accepted": allow_placeholder, "placeholder": True}, indent=2) + "\n")
if not allow_placeholder:
    raise SystemExit("placeholder reward disabled; configure a real benchmark metric")
