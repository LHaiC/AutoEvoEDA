#!/usr/bin/env bash
set -euo pipefail
results="$AUTOEVO_CANDIDATE_ROOT/results"
mkdir -p "$results"
cat > "$results/perf.json" <<'JSON'
{
  "configured": false,
  "note": "No public benchmark/reward metric is configured for this example adapter."
}
JSON
