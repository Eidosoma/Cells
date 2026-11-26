#!/bin/bash
# FR's bitwise landing set on lane B, synchronously.
# Steps:
#   1. add a detached worktree of REV;
#   2. run the holder under lane B's lock (fr_landing_holder.sh). It freezes the worktree into
#      OUT/fr-snapshot, removes the worktree, checks the lane, runs the four queues and holds the
#      lock until they end;
#   3. judge the set with fr_landing_verdict.py against FR's frozen baselines, into
#      OUT/fr-landing/verdict.json.
#
# Supersedes these lane-B wrappers, all kept byte for byte:
# - /mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/judged-20261117/landing-checks-laneB.sh
#   (it launched the holder asynchronously);
# - the gates' own copies, for example
#   /mnt/workspaces/Cells/review-fixes-20261118/tools/gate-laneB-fr.sh.
# Run it from a unit that is not pinned to lane B (the holder's lane check ignores its own unit
# anyway). OUT/done holds the verdict's exit status, or 2 when the holder did not run to its end
# (its flock killed while waiting, or its own refusal), in which case nothing is judged.
#
# Cold (D321 R2): JAX's persistent compilation cache is disabled here and in the holder's queue units
# (fr_landing_holder.sh passes it to each), and the cold check refuses the set, before any verdict,
# if a cache entry appeared under its outputs.
#
# Usage: fr_landing_set.sh REV OUT   (REPO, the checkout, defaults to this script's repository)
set -u
export JAX_ENABLE_COMPILATION_CACHE=false
unset JAX_COMPILATION_CACHE_DIR CELLS_JAX_CACHE
REV=${1:?revision}; OUT=${2:?out}
G=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(git -C "$G" rev-parse --show-toplevel)}
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
LOCK=${LANE_LOCK:-/mnt/workspaces/Cells/locks/gate-cores-8-11.lock}
FR=/mnt/workspaces/Cells/d172-restructure-20261115-01/fr45
START=$FR/rehearsal-20261117/run-e79b4232/fr5/start/start.json
BEFORE=/mnt/workspaces/Cells/final-gate-20261126/fr-baselines-805c48a4/windowed  # Renewed for D307, then for the ID move's definition hashes (D345): RENEWAL.json beside it.
[ -e "$OUT" ] && { echo "Refused: $OUT exists" >&2; exit 1; }
mkdir -p "$OUT/fr-landing"
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/fr-landing-set.log"; }
WT=$OUT/fr-worktree FS=$OUT/fr-snapshot
git -C "$REPO" worktree add --detach "$WT" "$REV" >> "$OUT/fr-landing-set.log" 2>&1 \
  || { log "worktree failed"; echo 2 > "$OUT/done"; exit 2; }
log "the holder: $WT ($(git -C "$WT" rev-parse HEAD)) -> $FS, under $LOCK"
# The command form: the holder runs only once flock holds the lock, so a flock killed while it waits
# runs nothing. Its status is checked as well: unless the holder ran to its end (exit 0), the set
# refuses without a verdict (a killed flock, or the holder's own refusal).
/usr/bin/flock "$LOCK" bash "$G/fr_landing_holder.sh" "$WT" "$FS" "$START" "$OUT/fr-landing"
held=$?
log "the holder exit $held: $(tail -n 2 "$OUT/fr-landing/run.log" 2>/dev/null | tr '\n' ' ' | cut -c1-300)"
[ -d "$WT" ] && git -C "$REPO" worktree remove --force "$WT" >> "$OUT/fr-landing-set.log" 2>&1
if [ $held -ne 0 ]; then
  log "refused: the holder did not run to its end under the lock (exit $held); no verdict"
  echo 2 > "$OUT/done"
  exit 2
fi
log "JAX's persistent compilation cache disabled in the queues (JAX_ENABLE_COMPILATION_CACHE=false; D321 R2)"
if why=$(python3 -I "$G/gate_steps.py" jax-entries "$OUT/fr-landing" 2>&1); then
  log "cold check after the queues: $why"
else
  log "refused: JAX compilation cache entries appeared in the queues (the cold check): $why; no verdict"
  echo 1 > "$OUT/done"
  exit 1
fi
"$PY" -I "$G/fr_landing_verdict.py" "$FS" "$OUT/fr-landing" "$BEFORE" "$OUT/fr-landing/verdict.json" \
  > "$OUT/fr-landing/verdict.stdout" 2>&1
rc=$?
log "the verdict exit $rc: $(tr -d '\n' < "$OUT/fr-landing/verdict.stdout" | cut -c1-300)"
echo "$rc" > "$OUT/done"
exit $rc
