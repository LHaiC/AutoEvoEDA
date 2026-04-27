#!/usr/bin/env bash
set -euo pipefail

python "$AUTOEVO_ADAPTER_ROOT/scripts/write_perf.py" "$AUTOEVO_CANDIDATE_ROOT/results"
