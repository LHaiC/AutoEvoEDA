#!/usr/bin/env bash
set -euo pipefail
root="$AUTOEVO_CANDIDATE_ROOT/ghypart"
cmake -S "$root" -B "$root/build" -DCMAKE_BUILD_TYPE=Release
cmake --build "$root/build" -j "${AUTOEVO_JOBS:-$(nproc)}"
