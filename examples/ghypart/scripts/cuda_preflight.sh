#!/usr/bin/env bash
set -euo pipefail

echo "[cuda-preflight] PATH=$PATH"
echo "[cuda-preflight] LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
echo "[cuda-preflight] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"

command -v nvidia-smi >/dev/null || { echo "[cuda-preflight] ERROR: nvidia-smi not found"; exit 20; }
nvidia-smi >/tmp/autoevo-ghypart-nvidia-smi.log 2>&1 || { cat /tmp/autoevo-ghypart-nvidia-smi.log; echo "[cuda-preflight] ERROR: nvidia-smi failed"; exit 21; }
test -e /dev/nvidiactl || { echo "[cuda-preflight] ERROR: /dev/nvidiactl missing"; exit 22; }
test -e /dev/nvidia0 || { echo "[cuda-preflight] ERROR: /dev/nvidia0 missing"; exit 23; }
ldconfig -p | grep -E 'libcuda|libcudart' >/dev/null || { echo "[cuda-preflight] ERROR: CUDA driver/runtime library not visible"; exit 24; }

echo "[cuda-preflight] OK"
