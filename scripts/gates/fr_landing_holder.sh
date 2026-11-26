#!/bin/bash
# FR's bitwise landing set on lane B: the holder, run under flock on lane B's lock by
# fr_landing_set.sh. Supersedes
# /mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/judged-20261117/landing-laneB-holder.sh,
# which is kept byte for byte since recorded runs cite it.
#
# The one change of behaviour is the lane check (scripts/gates/lane_busy.py, D222's first fault).
# A unit only waiting for the lock no longer refuses the set; a unit computing on lane B without
# the lock still does, charged by each process's own affinity (so a child pinned onto lane B is
# seen). The holder's own unit is left out by the check itself.
# Unchanged in effect:
# - the launcher is the checkout's scripts/run_detached.sh (the frozen copy beside the old holder is
#   byte-identical to it);
# - the queue is scripts/gates/fr_landing_queue.sh;
# - the snapshot is frozen by scripts/gates/freeze_snapshot.py --scope guards, the old freeze
#   helper's scope;
# - the baselines are FR's frozen quick dry runs, renewed for D305's fix (D307): the parts whose
#   max_global_charge_bound_ratio fell, from FR's set at 605331c2; the rest linked to the dry runs
#   (RENEWAL.json beside them). Renewed again for the law-ID move (D345): every part's
#   definition_sha256 is the landed definition's (legacy-cleanup-landed-2026-11-26, 805c48a4), and
#   nothing else changed (that folder's RENEWAL.json).
#
# Steps:
#   1. freeze the snapshot from the clean worktree, then remove the worktree;
#   2. refuse, launching nothing, unless the snapshot is clean and no other unit computes on lane B
#      without its lock (OUT/lane-check.json);
#   3. launch the four queues on CPUs 8, 9, 10 and 11, leaving their siblings 24-27 idle, and hold
#      the lock until they end. Each queue runs with JAX's persistent compilation cache disabled
#      (D321 R2), passed explicitly so it holds whichever run_detached.sh launches it.
#
# Usage: fr_landing_holder.sh WORKTREE SNAPSHOT_DEST START OUT
set -u
WT=$1 S=$2 START=$3 O=$4
G=$(cd "$(dirname "$0")" && pwd)
RD=$G/../run_detached.sh
Q=$G/fr_landing_queue.sh
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
LOCK=${LANE_LOCK:-/mnt/workspaces/Cells/locks/gate-cores-8-11.lock}
P=/mnt/workspaces/Cells/final-gate-20261126/fr-baselines-805c48a4
F4=$P/fr4-quick F5=$P/fr5
log() { echo "$(date -u +%FT%TZ) holder $*" >> "$O/run.log"; }
log "the lock is held"
REPO=$(git -C "$WT" rev-parse --path-format=absolute --git-common-dir 2>/dev/null)
REPO=${REPO%/.git}
"$PY" -B "$G/freeze_snapshot.py" "$WT" "$S" --scope guards >> "$O/freeze.log" 2>&1
code=$?
git -C "$REPO" worktree remove "$WT" >> "$O/freeze.log" 2>&1
clean=$(python3 -c "
import hashlib, json, sys
s = json.load(open(sys.argv[1]))
print('yes' if s.get('status') == 'complete' and s.get('patch_sha256') == hashlib.sha256(b'').hexdigest() else 'no')" "$S/SNAPSHOT.json" 2>/dev/null || echo no)
log "froze $S: exit $code, clean $clean"
if [ "$clean" != yes ]; then log "refused: no clean snapshot (nothing launched)"; exit 1; fi
python3 -I "$G/lane_busy.py" --cpus 8-11,24-27 --lock "$LOCK" --json "$O/lane-check.json" \
  > /dev/null 2>> "$O/run.log"
busy=$?
if [ $busy -ne 0 ]; then
  log "refused: units compute on lane B without its lock: $(python3 -c 'import json,sys; print([b["unit"] for b in json.load(open(sys.argv[1]))["busy"]])' "$O/lane-check.json" 2>&1) (nothing launched; lane-check.json)"
  exit 1
fi
log "lane check: $(python3 -c 'import json,sys; d=json.load(open(sys.argv[1])); print({k: [r["unit"] for r in d[k]] for k in ("waiters", "idle")})' "$O/lane-check.json" 2>&1)"
q() { echo "quick|$1|$2|$3/$2/results.json|${4:-}"; }
launch() {  # CPU TASK...
  local cpu=$1; shift
  "$RD" "fr45-landingB-q$cpu" 3G --cpus "$cpu" --oom-first --runtime-max 3600 --dir "$S" \
    --env "PYTHONPATH=$S/src:$S" --env JAX_ENABLE_X64=1 --env JAX_PLATFORMS=cpu \
    --env CUDA_VISIBLE_DEVICES= --env PYTHONDONTWRITEBYTECODE=1 \
    --env JAX_ENABLE_COMPILATION_CACHE=false -- \
    bash "$Q" "$O" "$START" "$cpu" "$@" >> "$O/launch.log" 2>&1
}
launch 8 "$(q fr4 rung_1ms $F4)" "$(q fr4 control_k1 $F4)" "$(q fr5 T_control $F5 $F5/start/start.json)"
launch 9 "$(q fr4 control_k2 $F4)" "$(q fr4 control_k3 $F4)" "$(q fr5 R_control $F5 $F5/start/start.json)"
launch 10 "$(q fr5 start $F5)" "$(q fr5 R_rung_0p5ms $F5 $F5/start/start.json)" "windowed|T"
launch 11 "$(q fr5 T_rung_0p5ms $F5 $F5/start/start.json)" "windowed|R"
log "launched cells-fr45-landingB-q{8,9,10,11}; holding the lock until they end"
sleep 10
for cpu in 8 9 10 11; do
  while systemctl --user is-active --quiet "cells-fr45-landingB-q$cpu"; do sleep 20; done
done
log "the queues have ended: releasing the lock"
