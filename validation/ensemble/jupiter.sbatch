#!/usr/bin/env bash
# Prepared template. Supply account and scratch stdout/stderr paths to sbatch.
#SBATCH --job-name=cells-ensemble-pilot
#SBATCH --partition=booster
#SBATCH --nodes=1
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=288
#SBATCH --gpus-per-node=4
#SBATCH --time=00:30:00
#SBATCH --signal=B:USR1@90

set -euo pipefail
: "${SLURM_JOB_ID:?Run this template through sbatch}"
: "${CELLS_PYTHON:?Set the path to the site-qualified Arm CUDA JAX Python}"
: "${CELLS_SOURCE:?Set the path to the Cells src directory}"
: "${CELLS_OUTPUT_ROOT:?Set the dedicated Cells scratch root}"
if [[ $# -ne 2 ]]; then
    echo 'Usage: sbatch [site options] jupiter.sbatch definition.json new-output-directory' >&2
    exit 2
fi
export PYTHONPATH="${CELLS_SOURCE}${PYTHONPATH:+:${PYTHONPATH}}"
export PYTHONDONTWRITEBYTECODE=1
# exec keeps the batch process as the signal recipient. No local --detach.
exec "${CELLS_PYTHON}" -B -m cells.ensemble run "$1" --output "$2" \
    --devices all --allocated-gpus 4
