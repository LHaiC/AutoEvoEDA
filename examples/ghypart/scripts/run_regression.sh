#!/usr/bin/env bash
set -euo pipefail

root="$AUTOEVO_CANDIDATE_ROOT/ghypart"
bench="$AUTOEVO_ADAPTER_ROOT/benchmarks"
results="$AUTOEVO_CANDIDATE_ROOT/results"
mkdir -p "$results"

"$root/build/gHyPart" > "$results/startup.txt" 2>&1
grep -F "Run the code by typing" "$results/startup.txt" >/dev/null

timeout 120 "$root/build/gHyPart" "$bench/unweighted_smoke.hgr" -useuvm 0 -r 1 > "$results/unweighted.stdout" 2> "$results/unweighted.stderr"
grep -F "finish all." "$results/unweighted.stdout" >/dev/null

timeout 120 "$root/build/gHyPart" "$bench/weighted_smoke.hgr" -useuvm 0 -r 1 > "$results/weighted.stdout" 2> "$results/weighted.stderr"
grep -F "finish all." "$results/weighted.stdout" >/dev/null

python "$AUTOEVO_ADAPTER_ROOT/scripts/write_correctness.py" "$results" "$bench/weighted_smoke.hgr"
