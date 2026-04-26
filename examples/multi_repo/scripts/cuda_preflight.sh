#!/usr/bin/env bash
set -euo pipefail

require_cuda() {
  echo "[cuda-preflight] PATH=$PATH"
  echo "[cuda-preflight] LD_LIBRARY_PATH=${LD_LIBRARY_PATH:-}"
  echo "[cuda-preflight] CUDA_VISIBLE_DEVICES=${CUDA_VISIBLE_DEVICES:-unset}"
  command -v nvidia-smi >/dev/null || {
    echo "[cuda-preflight] ERROR: nvidia-smi not found"
    exit 20
  }
  nvidia-smi >/tmp/autoevo-nvidia-smi.log 2>&1 || {
    cat /tmp/autoevo-nvidia-smi.log
    echo "[cuda-preflight] ERROR: nvidia-smi failed; check driver, sandbox, or device visibility"
    exit 21
  }
  test -e /dev/nvidiactl || {
    echo "[cuda-preflight] ERROR: /dev/nvidiactl missing"
    exit 22
  }
  test -e /dev/nvidia0 || {
    echo "[cuda-preflight] ERROR: /dev/nvidia0 missing"
    exit 23
  }

  if command -v ldconfig >/dev/null; then
    ldconfig -p | grep -E 'libcuda|libcudart' >/dev/null || {
      echo "[cuda-preflight] ERROR: libcuda/libcudart not found in ldconfig cache"
      exit 24
    }
  elif ! find /usr/local/cuda/lib64 -maxdepth 1 \( -name 'libcuda*' -o -name 'libcudart*' \) 2>/dev/null | grep -q .; then
    echo "[cuda-preflight] ERROR: CUDA libraries not found"
    exit 24
  fi
  echo "[cuda-preflight] OK"
}

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  require_cuda
fi
