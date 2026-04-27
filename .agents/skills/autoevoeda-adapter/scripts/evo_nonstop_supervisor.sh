#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ADAPTER_ROOT="${AUTOEVO_ADAPTER_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
PROJECT_ROOT="${AUTOEVO_PROJECT_ROOT:-$ADAPTER_ROOT}"
CONFIG="${AUTOEVO_CONFIG:-$ADAPTER_ROOT/evo.yaml}"
LOG_DIR="${AUTOEVO_LOG_DIR:-$ADAPTER_ROOT/logs/nonstop}"
SLEEP_S="${AUTOEVO_SLEEP_S:-60}"
MAX_RESTARTS="${AUTOEVO_MAX_RESTARTS:-3}"
UNDERSTAND_PHASES="${AUTOEVO_UNDERSTAND_PHASES:-scaffold profile relationships guidance role_memory review}"
UNDERSTAND_STAMP="$ADAPTER_ROOT/.evo/memory/code/.supervisor_understand_done"
CUDA_PREFLIGHT="${AUTOEVO_CUDA_PREFLIGHT:-$ADAPTER_ROOT/scripts/cuda_preflight.sh}"
SOURCE_ROOT="${AUTOEVO_SOURCE_ROOT:-$PROJECT_ROOT}"

mkdir -p "$LOG_DIR"

log() {
  printf '[%s] %s\n' "$(date -Is)" "$*" | tee -a "$LOG_DIR/supervisor.log"
}

run_logged() {
  local name="$1"
  shift
  log "running $name"
  "$@" 2>&1 | tee -a "$LOG_DIR/$name.log"
  local rc=${PIPESTATUS[0]}
  if (( rc != 0 )); then
    log "ERROR: $name failed with rc=$rc"
    exit "$rc"
  fi
}

ensure_evo() {
  if [[ "${AUTOEVO_INSTALL:-0}" == "1" ]]; then
    run_logged install python3 -m pip install -e "${AUTOEVO_FRAMEWORK_ROOT:-$PROJECT_ROOT/evo-harness}"
  fi
  command -v evo >/dev/null || {
    log "ERROR: evo CLI not found; install AutoEvoEDA or set AUTOEVO_INSTALL=1"
    exit 2
  }
}

run_preflight() {
  run_logged config_validate evo config validate --config "$CONFIG"
  if [[ "${AUTOEVO_REQUIRE_CUDA:-0}" == "1" ]]; then
    run_logged cuda_preflight env \
      AUTOEVO_ADAPTER_ROOT="$ADAPTER_ROOT" \
      AUTOEVO_CANDIDATE_ROOT="$SOURCE_ROOT" \
      bash "$CUDA_PREFLIGHT"
  fi
}

run_understand_once() {
  if [[ "${AUTOEVO_SKIP_UNDERSTAND:-0}" == "1" ]]; then
    log "skipping evo understand because AUTOEVO_SKIP_UNDERSTAND=1"
    return
  fi
  if [[ -e "$UNDERSTAND_STAMP" && "${AUTOEVO_FORCE_UNDERSTAND:-0}" != "1" ]]; then
    log "understanding already completed; set AUTOEVO_FORCE_UNDERSTAND=1 to refresh"
    return
  fi
  for phase in $UNDERSTAND_PHASES; do
    run_logged "understand_${phase}" evo understand --config "$CONFIG" --phase "$phase"
  done
  mkdir -p "$(dirname "$UNDERSTAND_STAMP")"
  date -Is > "$UNDERSTAND_STAMP"
}

run_daemon_loop() {
  local restart=0
  while true; do
    log "starting evo daemon --non-stop --sleep-s $SLEEP_S"
    set +e
    evo daemon --config "$CONFIG" --non-stop --sleep-s "$SLEEP_S" 2>&1 | tee -a "$LOG_DIR/daemon.log"
    local rc=${PIPESTATUS[0]}
    set -e

    if (( rc == 0 )); then
      log "evo daemon exited cleanly"
      return 0
    fi

    restart=$((restart + 1))
    log "evo daemon exited with rc=$rc restart=$restart/$MAX_RESTARTS"
    if (( restart >= MAX_RESTARTS )); then
      log "ERROR: restart limit reached; inspect $LOG_DIR and $ADAPTER_ROOT/.evo/runs"
      return "$rc"
    fi
    sleep "$SLEEP_S"
  done
}

main() {
  cd "$PROJECT_ROOT"
  log "project_root=$PROJECT_ROOT"
  log "adapter_root=$ADAPTER_ROOT"
  log "config=$CONFIG"
  ensure_evo
  run_preflight
  run_understand_once
  run_daemon_loop
}

main "$@"
