#!/usr/bin/env bash
set -euo pipefail

# Start exactly one bounded group through normal approval when available.
# No automatic sequence, review retry, background job or acceptance claim.
case "${1:-}" in
  first) count=4; run=01 ;;
  guard) count=2; run=02 ;;
  water-stage-baseline) count=8; run=03 ;;
  water-stage-changed) count=9; run=04 ;;
  repair-stage-baseline) count=8; run=05 ;;
  repair-stage-changed) count=9; run=06 ;;
  water-physics) count=15; run=07 ;;
  water-refusals) count=31; run=08 ;;
  repair-physics) count=15; run=09 ;;
  repair-refusals) count=31; run=10 ;;
  oracle-source) count=1; run=11 ;;
  *) printf 'Choose first, guard, water-stage-baseline, water-stage-changed, repair-stage-baseline, repair-stage-changed, water-physics, water-refusals, repair-physics, repair-refusals or oracle-source.\n' >&2; exit 2 ;;
esac

exec taskset -c 6 env \
  PYTHONPATH=/mnt/workspaces/Cells/active-profile-barriers-development-20261029-03/workspace/src:/mnt/workspaces/Cells/active-profile-barriers-development-20261029-03/workspace \
  PYTHONDONTWRITEBYTECODE=1 \
  JAX_PLATFORMS=cpu JAX_ENABLE_X64=true JAX_DISABLE_JIT=true \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 \
  /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  /home/robert/Cells/agent-work/cells-worker-01/workfiles/check_joint_water_profile_barriers.py \
  --output "/mnt/workspaces/Cells/joint-water-profile-barriers-development-20261029-${run}" \
  --nodes-file "/home/robert/Cells/agent-work/cells-worker-01/workfiles/node_plans/joint_water_profile_barrier_${1}.json" --expected-tests "$count" --timeout 480
