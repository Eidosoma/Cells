#!/usr/bin/env bash
set -euo pipefail

# One authorized bounded group only. Invoke through the normal approval flow.
# This script never starts the next group automatically.
case "${1:-}" in
  guard) selection='strong_background'; count=2; run=02 ;;
  chemical-stage-baseline) selection='full_stage and chemical_owner and False and not joint'; count=8; run=03 ;;
  chemical-stage-changed) selection='full_stage and chemical_owner and True'; count=9; run=04 ;;
  fuel-stage-baseline) selection='full_stage and fuel_owner and False and not joint'; count=8; run=05 ;;
  fuel-stage-changed) selection='full_stage and fuel_owner and True'; count=9; run=06 ;;
  chemical-contracts) selection='chemical_owner and not full_stage and not complete_parent and not strong_background'; count=25; run=07 ;;
  fuel-contracts) selection='fuel_owner and not full_stage and not complete_parent and not strong_background'; count=25; run=08 ;;
  *) printf 'Choose guard, chemical-stage-baseline, chemical-stage-changed, fuel-stage-baseline, fuel-stage-changed, chemical-contracts or fuel-contracts.\n' >&2; exit 2 ;;
esac

exec taskset -c 6 env \
  PYTHONPATH=/mnt/workspaces/Cells/active-profile-barriers-development-20261029-03/workspace/src:/mnt/workspaces/Cells/active-profile-barriers-development-20261029-03/workspace \
  PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true JAX_DISABLE_JIT=true \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  /home/robert/Cells/agent-work/cells-worker-01/workfiles/check_owned_calcium_profile_barriers.py \
  --output "/mnt/workspaces/Cells/owned-calcium-profile-barriers-development-20261029-${run}" \
  --selection "$selection" --expected-tests "$count" --timeout 480
