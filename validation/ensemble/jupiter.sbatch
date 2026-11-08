#!/usr/bin/env bash
# One JUPITER Booster node (4x GH200) for the Cells ensemble runner and platform checks.
#
#   sbatch -A BUDGET [--reservation=develbooster] [--time=HH:MM:SS] \
#       --output=LOGDIR/%x-%j.out --error=LOGDIR/%x-%j.err \
#       validation/ensemble/jupiter.sbatch MODE ARGUMENTS
#
#   run DEFINITION.json NEW_OUTPUT   register and run an ensemble on this node
#   resume OLD_OUTPUT NEW_OUTPUT     continue a paused run with OLD_OUTPUT's frozen source
#   check NEW_RECORD.json            jupiter_check.py check on every allocated GPU
#   smoke NEW_OUTPUT                 jupiter_check.py smoke (run, pause, resume, status)
#
# Required: CELLS_PYTHON (venv python from jupiter_env_setup.sh), CELLS_CHECKOUT (Cells git
# checkout) and CELLS_OUTPUT_ROOT (scratch root; outputs and caches must lie below it).
# CELLS_MODULES defaults to the setup script's "Stages/2026 GCC Python"; "none" keeps the
# submission environment. The node is charged whole. The runner owns exactly one node, so
# N nodes are N separate jobs or a job array; "%a" in arguments becomes the array index
# (docs/JUPITER_RUNBOOK.md).
#SBATCH --job-name=cells-ensemble
#SBATCH --partition=booster
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=288
#SBATCH --gres=gpu:4
#SBATCH --time=00:30:00
#SBATCH --signal=B:USR1@240

set -euo pipefail
: "${SLURM_JOB_ID:?Submit this script with sbatch}"
: "${CELLS_PYTHON:?Set CELLS_PYTHON to the venv python from jupiter_env_setup.sh}"
: "${CELLS_OUTPUT_ROOT:?Set CELLS_OUTPUT_ROOT to the Cells scratch root}"
if [[ -z "${CELLS_CHECKOUT:-}" && -n "${CELLS_SOURCE:-}" ]]; then
    CELLS_CHECKOUT="$(dirname "$CELLS_SOURCE")" # Earlier form: CELLS_SOURCE=<checkout>/src
fi
: "${CELLS_CHECKOUT:?Set CELLS_CHECKOUT to the Cells git checkout}"

usage() {
    sed -n '8,11p' "$0" >&2
    exit 2
}
if [[ -n "${SLURM_ARRAY_TASK_ID:-}" ]]; then
    set -- "${@//%a/$SLURM_ARRAY_TASK_ID}" # Job arrays: %a in arguments is the array index.
fi
mode="${1:-}"
if [[ "$mode" == *.json && $# -eq 2 ]]; then
    set -- run "$@" # Earlier form: jupiter.sbatch definition.json new-output
    mode=run
fi
case "$mode:$#" in
    run:3 | resume:3 | check:2 | smoke:2) ;;
    *) usage ;;
esac

modules="${CELLS_MODULES:-Stages/2026 GCC Python}"
if [[ "$modules" != none ]]; then
    set +u
    if ! type module > /dev/null 2>&1; then
        # shellcheck disable=SC1091
        source "${LMOD_PKG:-/usr/share/lmod/lmod}/init/bash"
    fi
    module --force purge
    # shellcheck disable=SC2086
    module load $modules
    set -u
fi

# JSC: a single-task job may otherwise see one GPU. Expose every GPU of this allocation.
mapfile -t gpus < <(nvidia-smi --query-gpu=uuid --format=csv,noheader)
[[ ${#gpus[@]} -gt 0 ]] || { echo "nvidia-smi lists no GPUs" >&2; exit 1; }
CUDA_VISIBLE_DEVICES="$(IFS=,; echo "${gpus[*]}")"
export CUDA_VISIBLE_DEVICES PYTHONDONTWRITEBYTECODE=1
export XLA_PYTHON_CLIENT_PREALLOCATE=false
unset JAX_PLATFORMS

echo "cells job=$SLURM_JOB_ID node=$(hostname) mode=$mode gpus=${#gpus[@]} modules=$modules"
echo "cells checkout=$CELLS_CHECKOUT revision=$(git -C "$CELLS_CHECKOUT" rev-parse HEAD)" \
    "dirty=$([[ -n "$(git -C "$CELLS_CHECKOUT" status --porcelain)" ]] && echo yes || echo no)"
nvidia-smi --query-gpu=index,uuid,name,driver_version,memory.total --format=csv,noheader

# exec keeps Python as the batch process, so --signal=B:USR1 reaches the runner, which
# checkpoints at the next window boundary. Never --detach inside Slurm.
check="$CELLS_CHECKOUT/validation/ensemble/jupiter_check.py"
case "$mode" in
    run)
        export PYTHONPATH="$CELLS_CHECKOUT/src"
        exec "$CELLS_PYTHON" -B -m cells.ensemble run "$2" --output "$3" \
            --devices all --allocated-gpus "${#gpus[@]}"
        ;;
    resume)
        export PYTHONPATH="$2/source" # Frozen at registration; the checkout may have moved on.
        exec "$CELLS_PYTHON" -B -m cells.ensemble resume "$2" --output "$3" \
            --devices all --allocated-gpus "${#gpus[@]}"
        ;;
    check)
        exec "$CELLS_PYTHON" -B "$check" check --output "$2" --expect-gpus "${#gpus[@]}"
        ;;
    smoke)
        exec "$CELLS_PYTHON" -B "$check" smoke --output "$2" --allocated-gpus "${#gpus[@]}"
        ;;
esac
