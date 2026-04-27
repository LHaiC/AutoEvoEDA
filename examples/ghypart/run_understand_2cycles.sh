#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
adapter="$repo_root/examples/ghypart"
source_repo="$adapter/source/gHyPart_TACO"
config="$adapter/evo.yaml"
project_name="ghypart.public"
understand_phase="${AUTOEVO_UNDERSTAND_PHASE:-scaffold}"

cd "$repo_root"

echo "[ghypart-smoke] repo_root=$repo_root"
echo "[ghypart-smoke] adapter=$adapter"
echo "[ghypart-smoke] understand_phase=$understand_phase"

echo "[ghypart-smoke] installing latest local AutoEvoEDA"
python3 -m pip install -e "$repo_root"

echo "[ghypart-smoke] updating gHyPart submodule"
git submodule update --init --recursive examples/ghypart/source/gHyPart_TACO

if git -C "$source_repo" rev-parse --is-inside-work-tree >/dev/null; then
  echo "[ghypart-smoke] removing old AutoEvoEDA gHyPart worktrees"
  git -C "$source_repo" worktree list --porcelain \
    | awk '/^worktree / {print substr($0, 10)}' \
    | while IFS= read -r worktree_path; do
        case "$worktree_path" in
          "$adapter/.evo-worktrees/"*)
            echo "[ghypart-smoke] remove worktree $worktree_path"
            git -C "$source_repo" worktree remove --force "$worktree_path"
            ;;
        esac
      done
  git -C "$source_repo" worktree prune
fi

echo "[ghypart-smoke] cleaning adapter run state"
rm -rf "$adapter/.evo" "$adapter/.evo-worktrees" "/tmp/autoevo-$project_name"

export PYTHONPATH="$repo_root${PYTHONPATH:+:$PYTHONPATH}"

echo "[ghypart-smoke] validating config"
python3 -m autoevoeda.cli config validate --config "$config"

echo "[ghypart-smoke] running understand phase"
python3 -m autoevoeda.cli understand --config "$config" --phase "$understand_phase"

echo "[ghypart-smoke] running two evolution cycles"
python3 -m autoevoeda.cli run --config "$config" --cycles 2

echo "[ghypart-smoke] writing reports"
python3 -m autoevoeda.cli report --config "$config"
python3 -m autoevoeda.cli compare --config "$config" --cycle 1
python3 -m autoevoeda.cli compare --config "$config" --cycle 2

echo "[ghypart-smoke] done"
echo "[ghypart-smoke] history: $adapter/.evo/history.jsonl"
echo "[ghypart-smoke] runs: $adapter/.evo/runs"
