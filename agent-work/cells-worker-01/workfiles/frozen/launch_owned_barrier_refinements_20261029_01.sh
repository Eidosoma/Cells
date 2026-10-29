#!/usr/bin/env bash
set -euo pipefail

# Prepared for the Chief Developer to launch after reviewing the frozen bundle.
# This worker has not executed the full-suite launch.
exec taskset -c 3 env \
  PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true JAX_DISABLE_JIT=true \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  /mnt/workspaces/Cells/owned-barrier-refinement-preparation-20261029-01/runner.py \
  --bundle /mnt/workspaces/Cells/owned-barrier-refinement-preparation-20261029-01 \
  --output /mnt/workspaces/Cells/owned-barrier-refinements-20261029-01 \
  --completed-pilot /mnt/workspaces/Cells/owned-barrier-refinement-pilot-20261029-01 \
  --launch
