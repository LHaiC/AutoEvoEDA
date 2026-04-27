#!/usr/bin/env bash
set -euo pipefail
root="$AUTOEVO_CANDIDATE_ROOT/ghypart"
build="${AUTOEVO_RUNNER_BUILD_ROOT:?AUTOEVO_RUNNER_BUILD_ROOT required}/ghypart"
cmake -S "$root" -B "$build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build" -j "${AUTOEVO_JOBS:-$(nproc)}"
