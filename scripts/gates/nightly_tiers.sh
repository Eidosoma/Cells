#!/bin/bash
# The nightly full tiers 1+2 and the scope map (the testing plan of 19 November 2026, item E, §10.5;
# D229 rule 3). Started by cells-nightly-tiers.service (scripts/gates/systemd/, installed by the
# lead) at 02:30 UTC.
#   1. Freezes main from a clean detached worktree (freeze_snapshot.py, scope full) into
#      NIGHTLY/DATE/snapshot, then runs on from the snapshot's own copy of this script, so a run never
#      changes under it.
#   2. Takes whichever lane's lock is free first, like a gate: flock's command form without waiting,
#      tried every POLL seconds, so a gate already queued for a lane goes first; after WAIT_FREE
#      seconds it queues for lane A's lock. Until it holds one, the freeze included, it stays on the
#      pre-lock CPU (PRE_CPU).
#   3. Under the lock: tiers 1+2 of the snapshot in full on the lane's eight CPUs, cap 300 s, with the
#      scope map's recorder on (scripts/test_tiers.py run --scope-map) and strace as the check on it
#      (--trace; D358). Where strace cannot trace, or with TRACE=0, the run goes on without it: the
#      map's entries are then not traced, so selection keeps D229's readers rule for them.
#   4. Builds the scope map (scope.py build) and writes NIGHTLY/DATE/verdict.json, with what the
#      trace found. An entry the trace shows to lack a file is incomplete, so its test always runs;
#      that fails nothing here. The traces that found nothing are removed.
#   5. A passing run's map replaces GATE_CACHE/scope-map.json, renamed into place whole. A failure (a
#      file that changed against its row, a run or map that did not complete, or the lock never held)
#      writes GATE_CACHE/selection-stopped, which turns selection off until the lead removes it with
#      the explanation; the last passing map is kept.
# Environment: REPO (default $HOME/Cells), NIGHTLY (default /mnt/workspaces/Cells/nightly),
#   GATE_CACHE (default /mnt/workspaces/Cells/gate-cache), PY, HOSTPY, PRE_CPU (default 23), POLL
#   (default 60), WAIT_FREE (default 10800), TRACE (default 1), and LOCK_A, CPUS_A, LOCK_B, CPUS_B and
#   TIERS (a reduced tier record, whose map then fails as incomplete; tests and rehearsals only).
# Usage: nightly_tiers.sh              the unit's command: freeze main, then run the frozen copy
#        nightly_tiers.sh --run OUT    the frozen copy, from OUT/snapshot
#   OUT/done holds 0 (passed), 1 (failed) or 2 (not run).
set -u
REPO=${REPO:-$HOME/Cells}
NIGHTLY=${NIGHTLY:-/mnt/workspaces/Cells/nightly}
GATE_CACHE=${GATE_CACHE:-/mnt/workspaces/Cells/gate-cache}
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
HOSTPY=${HOSTPY:-python3}
PRE_CPU=${PRE_CPU:-23}; POLL=${POLL:-60}; WAIT_FREE=${WAIT_FREE:-10800}
LOCK_A=${LOCK_A:-/mnt/workspaces/Cells/locks/gate-cores-0-3.lock}; CPUS_A=${CPUS_A:-0,1,2,3,16,17,18,19}
LOCK_B=${LOCK_B:-/mnt/workspaces/Cells/locks/gate-cores-8-11.lock}; CPUS_B=${CPUS_B:-8,9,10,11,24,25,26,27}
G=$(cd "$(dirname "$0")" && pwd)
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
# Cold (D321 R2): the nightly full run is the control for gates that use a cache, so it never does.
export JAX_ENABLE_COMPILATION_CACHE=false
unset JAX_COMPILATION_CACHE_DIR CELLS_JAX_CACHE
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/nightly.log"; }
stop_selection() {  # WHY: selection off until the lead explains the failure.
  mkdir -p "$GATE_CACHE"
  printf '%s\n' "$(date -u +%FT%TZ) the nightly run $OUT: $1" "Remove this file with the explanation." \
    > "$GATE_CACHE/.selection-stopped.$$" && mv "$GATE_CACHE/.selection-stopped.$$" "$GATE_CACHE/selection-stopped"
  log "selection stopped: $1"
}
finish() { log "done status $1"; echo "$1" > "$OUT/done"; exit "$1"; }

# Until it holds a lane's lock, everything here (the freeze too) stays on the pre-lock CPU: the
# unit may run on both lanes' CPUs, and nothing computes there without the lane's lock.
if [ "${1:-}" != --locked ]; then
  taskset -cp "$PRE_CPU" $$ > /dev/null || { echo "could not pin to CPU $PRE_CPU" >&2; exit 2; }
fi

case "${1:-}" in
  "")  # 1. Freeze main, then run the frozen copy.
    OUT=$NIGHTLY/$(date -u +%Y%m%d)
    [ ! -e "$OUT" ] || OUT=$OUT-$(date -u +%H%M%S)
    mkdir -p "$OUT"
    REV=$(git -C "$REPO" rev-parse --verify main^{commit}) || { log "no main in $REPO"; stop_selection "main unreadable"; finish 2; }
    log "nightly of main $REV from $REPO into $OUT"
    git -C "$REPO" worktree add --quiet --detach "$OUT/tree" "$REV" >> "$OUT/nightly.log" 2>&1 \
      && "$PY" -B "$G/freeze_snapshot.py" "$OUT/tree" "$OUT/snapshot" --scope full --require-clean >> "$OUT/nightly.log" 2>&1
    rc=$?
    git -C "$REPO" worktree remove --force "$OUT/tree" >> "$OUT/nightly.log" 2>&1
    [ $rc -eq 0 ] && [ -f "$OUT/snapshot/scripts/gates/nightly_tiers.sh" ] \
      || { log "freezing main failed (exit $rc)"; stop_selection "main could not be frozen"; finish 2; }
    exec bash "$OUT/snapshot/scripts/gates/nightly_tiers.sh" --run "$OUT" ;;
  --run)
    OUT=${2:?out}
    log "the frozen copy $G on CPU $(taskset -pc $$ | sed 's/.*: //'); waiting for a free lane (lane A after $WAIT_FREE s)"
    rm -f "$OUT/locked.done"
    start=$(date +%s)
    while :; do
      for lane in A B; do
        lock=LOCK_$lane
        /usr/bin/flock -n -E 75 "${!lock}" bash "$0" --locked "$lane" "$OUT"
        rc=$?
        [ $rc -eq 75 ] || break 2
      done
      if [ $(( $(date +%s) - start )) -ge "$WAIT_FREE" ]; then
        log "no lane free for $WAIT_FREE s: queueing for lane A"
        /usr/bin/flock "$LOCK_A" bash "$0" --locked A "$OUT"
        break
      fi
      sleep "$POLL"
    done
    [ -f "$OUT/locked.done" ] || { log "no lock was held: nothing ran"; stop_selection "the lock was never held"; finish 2; }
    finish "$(cat "$OUT/locked.done")" ;;
  --locked)
    LANE=${2:?lane}; OUT=${3:?out}
    cpus=CPUS_$LANE; CPUS=${!cpus}
    S=$OUT/snapshot
    done_locked() { echo "$1" > "$OUT/locked.done"; exit "$1"; }
    taskset -cp "$CPUS" $$ > /dev/null || { log "could not pin to lane $LANE's CPUs $CPUS"; done_locked 2; }
    log "lane $LANE, lock held; affinity $(taskset -pc $$ | sed 's/.*: //')"
    log "JAX's persistent compilation cache disabled in every process (JAX_ENABLE_COMPILATION_CACHE=false, \
no cache folder; D321 R2)"
    start=$(date +%s)
    TRACED=()
    [ "${TRACE:-1}" = 0 ] || TRACED=(--trace "$OUT/tiers-1+2/trace")
    (cd "$S" && PYTHONPATH="$S/src:$S" "$PY" -B scripts/test_tiers.py run --tiers "${TIERS:-tests/test_tiers.json}" \
      --tier 1 2 --out "$OUT/tiers-1+2" --cpus "$CPUS" --cap 300 --scope-map "$OUT/tiers-1+2/scope" \
      "${TRACED[@]}" > "$OUT/tiers-1+2.log" 2>&1)
    tiers=$?
    log "tiers 1+2 exit $tiers seconds $(( $(date +%s) - start )): $(tail -n 1 "$OUT/tiers-1+2.log")"
    if why=$("$HOSTPY" -I "$S/scripts/gates/gate_steps.py" jax-entries "$OUT/tiers-1+2" 2>&1); then
      log "cold check after the tiers: $why"
    else
      log "stopped: JAX compilation cache entries appeared after the tiers (the cold check): $why"
      stop_selection "the cold check failed: $why"
      done_locked 1
    fi
    taskset -c "${CPUS%%,*}" "$HOSTPY" -I "$S/scripts/gates/scope.py" build "$OUT/tiers-1+2" "$S" \
      "$OUT/scope-map.json" --python "$PY" --prune-traces > "$OUT/scope-build.log" 2>&1
    built=$?
    log "scope map exit $built: $(tail -n 1 "$OUT/scope-build.log")"
    "$HOSTPY" -I - "$OUT" "$tiers" "$built" <<'EOF'
import json, sys
from pathlib import Path
out, tiers, built = Path(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
summary = json.loads((out / "tiers-1+2" / "summary.json").read_text()) if (out / "tiers-1+2" / "summary.json").is_file() else None
doc = json.loads((out / "scope-map.json").read_text()) if built == 0 else None
verdict = {"revision": json.loads((out / "snapshot" / "SNAPSHOT.json").read_text())["git_revision"],
           "tiers_exit": tiers, "map_exit": built,
           "changed": [e["file"] for e in summary["changed_vs_record"]] if summary else None,
           "map_verdict": doc and doc["verdict"],
           "incomplete": doc and sorted(f for f, e in doc["files"].items() if not e["complete"]),
           "unmapped": doc and sorted(f for f, e in doc["files"].items() if e["children_unmapped"]),
           "trace": doc and doc["trace"]}
verdict["passed"] = tiers == 0 and built == 0 and verdict["map_verdict"] == "passed"
(out / "verdict.json").write_text(json.dumps(verdict, indent=1) + "\n")
print(json.dumps({k: verdict[k] for k in ("passed", "tiers_exit", "map_exit", "map_verdict")}))
sys.exit(0 if verdict["passed"] else 1)
EOF
    if [ $? -eq 0 ]; then
      mkdir -p "$GATE_CACHE" && cp "$OUT/scope-map.json" "$GATE_CACHE/.scope-map.json.$$" \
        && mv "$GATE_CACHE/.scope-map.json.$$" "$GATE_CACHE/scope-map.json"
      log "passed: the map published to $GATE_CACHE/scope-map.json"
      done_locked 0
    fi
    stop_selection "failed ($(tr -d '\n' < "$OUT/verdict.json" 2>/dev/null | cut -c1-300))"
    done_locked 1 ;;
  *) echo "usage: nightly_tiers.sh [--run OUT]" >&2; exit 2 ;;
esac
