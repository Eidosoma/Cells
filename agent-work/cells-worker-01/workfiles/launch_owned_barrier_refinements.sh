#!/usr/bin/env bash
set -euo pipefail

# Root-reviewed supervisor successor; the original science/pilot stay frozen.
# This worker has not executed the full-suite launch.
readonly barrier_supervisor=/mnt/workspaces/Cells/owned-barrier-refinement-supervision-20261029-01/runner.py
readonly barrier_supervisor_sha=d0b8bbd75f4a6143b84b700ba2422d36dc554cc6f782c37e0b7df1ba0b273a3d
printf '%s  %s\n' "$barrier_supervisor_sha" "$barrier_supervisor" | sha256sum --check --status

exec taskset -c 3 env \
  PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true JAX_DISABLE_JIT=true \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  "$barrier_supervisor" \
  --bundle /mnt/workspaces/Cells/owned-barrier-refinement-preparation-20261029-01 \
  --output /mnt/workspaces/Cells/owned-barrier-refinements-20261029-01 \
  --completed-pilot /mnt/workspaces/Cells/owned-barrier-refinement-pilot-20261029-01 \
  --runner-sha256 "$barrier_supervisor_sha" \
  --launch
