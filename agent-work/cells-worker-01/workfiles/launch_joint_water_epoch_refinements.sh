# Run only after the Chief's launch-gate review. This command launches detached.
taskset -c 4 /mnt/workspaces/Cells/venv-cpu/bin/python -B \
  /mnt/workspaces/Cells/joint-water-epoch-refinement-preparation-20261029-02/runner.py \
  --launch \
  --bundle /mnt/workspaces/Cells/joint-water-epoch-refinement-preparation-20261029-02 \
  --output /mnt/workspaces/Cells/joint-water-epoch-refinements-20261029-01 \
  --contract-review /mnt/workspaces/Cells/joint-water-phase-development-20261029-05/root-review-01/REVIEW.json \
  --contract-review-sha256 1a2aa05bc5503930de1af0d465c1195ef65c4368ccfc5bd5eacdbf1a0ef2a6b1 \
  --completed-pilot /mnt/workspaces/Cells/joint-water-epoch-refinement-pilot-20261029-01
