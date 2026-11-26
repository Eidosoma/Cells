#!/bin/bash
# The weekly tier 3 (D390: the user's "tier 3 runs weekly on idle cores", 26 November 2026). Started by
# cells-weekly-tier3.service (scripts/gates/systemd/, installed by the lead) on Sundays at 04:00 UTC, after
# the nightly (02:30, about 45 minutes). Modelled on nightly_tiers.sh.
#   1. Freezes main from a clean detached worktree (freeze_snapshot.py, scope full) into WEEKLY/DATE/snapshot,
#      then runs on from the snapshot's own copy of this script, so a run never changes under it.
#   2. Takes whichever lane's lock is free first, as the nightly does: flock's command form without waiting,
#      tried every POLL seconds, so a gate already queued for a lane goes first; after WAIT_FREE seconds it
#      queues for lane A's lock. Holding the lock, it checks the lane (lane_busy.py): while a unit computes
#      there without the lock it lets the lock go and tries again, and the last try (lane A, queued) records
#      a busy lane as not run. Until it holds a lock, the freeze included, it stays on the pre-lock CPU.
#   3. Under the lock: tier 3 of the snapshot's record (scripts/test_tiers.py run --tier 3) at CAP, the cap
#      tier 3's record was frozen with, one file per CPU on the lane's four physical cores; their hyperthread
#      siblings stay idle, which the lock guarantees. Then the cold check (gate_steps.py jax-entries) and
#      the run's test IDs collected from the snapshot (scripts/test_tiers.py collect). run's own exit is 1
#      by design (tier 3's rows in test_tiers.json hold no outcome); the verdict is the diff's.
#   4. Tier 3's record (the snapshot's tests/tier3_record.json, or RECORD) read through the ID move's
#      table: each test ID through scripts/id_moves.py's map by its ids rule (Map.test_id), so a record
#      frozen before a rename compares in today's spelling; the IDs it re-spelled are listed. Then
#      scripts/test_tiers.py diff --require-complete against it.
#   5. WEEKLY/DATE/verdict.json for the lead: passed (no blocking entry, every record file run at the
#      record's cap, the run cold), the blocking entries, what is only reported, the record files not
#      run. Nothing else changes: tier 3 gates no landing, so its failure turns nothing off.
# Environment: REPO (default $HOME/Cells), REF (default main; a rehearsal names its own branch, since main
#   need not hold this script yet), WEEKLY (default /mnt/workspaces/Cells/weekly), PY, HOSTPY, PRE_CPU
#   (default 23), POLL (default 60), WAIT_FREE (default 10800), CAP (default 1800), LOCK_A, CPUS_A,
#   LOCK_B, CPUS_B, and TIERS and RECORD (a reduced tier record, whose verdict is then incomplete, and
#   another record of tier 3; tests and rehearsals only).
# Usage: weekly_tier3.sh              the unit's command: freeze REF, then run the frozen copy
#        weekly_tier3.sh --run OUT    the frozen copy, from OUT/snapshot
#        weekly_tier3.sh --judge OUT  steps 4 and 5 again on a finished run, into OUT/judged-TIME (RECORD:
#                                     another record, such as one frozen since)
#   OUT/done holds 0 (passed), 1 (failed or incomplete) or 2 (not run).
set -u
REPO=${REPO:-$HOME/Cells}
REF=${REF:-main}
WEEKLY=${WEEKLY:-/mnt/workspaces/Cells/weekly}
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
HOSTPY=${HOSTPY:-python3}
PRE_CPU=${PRE_CPU:-23}; POLL=${POLL:-60}; WAIT_FREE=${WAIT_FREE:-10800}; CAP=${CAP:-1800}
LOCK_A=${LOCK_A:-/mnt/workspaces/Cells/locks/gate-cores-0-3.lock}; CPUS_A=${CPUS_A:-0,1,2,3}; LANE_A=${LANE_A:-0-3,16-19}
LOCK_B=${LOCK_B:-/mnt/workspaces/Cells/locks/gate-cores-8-11.lock}; CPUS_B=${CPUS_B:-8,9,10,11}; LANE_B=${LANE_B:-8-11,24-27}
BUSY=76  # The locked part's exit when the lane was busy: the lock is let go and taken again later.
G=$(cd "$(dirname "$0")" && pwd)
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
# Cold (D321 R2), as the record's run was: tier 3's seconds are only reported, but a cache would make
# them another measurement than the record's.
export JAX_ENABLE_COMPILATION_CACHE=false
unset JAX_COMPILATION_CACHE_DIR CELLS_JAX_CACHE
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/weekly.log"; }
finish() { log "done status $1"; echo "$1" > "$OUT/done"; exit "$1"; }

judge() {  # 4 and 5 into folder D: the record through the move's table, the diff, the verdict. 0: passed.
  local D=$1 run_rc=${2:-} cold_rc=${3:-} collect_rc=${4:-} S=$OUT/snapshot
  local record=${RECORD:-$S/tests/tier3_record.json}
  "$HOSTPY" -I - "$S" "$record" "$D/record-through-the-move.json" > "$D/through-the-move.log" 2>&1 <<'EOF'
import json, sys
from pathlib import Path
snapshot, record, out = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
sys.path.insert(0, str(snapshot / "scripts"))
import id_moves  # The ID move's tool (D345), host only.
table = id_moves.load_map(snapshot / id_moves.MAP)
doc = json.loads(record.read_text())
respelled = []
for name, entry in doc["files"].items():
    for row in entry["tests"]:
        new = table.test_id(f"{name}::{row[0]}").split("::", 1)[1]
        if new != row[0]:
            respelled.append([f"{name}::{row[0]}", f"{name}::{new}"])
            row[0] = new
doc["through_the_move"] = {"record": str(record), "map": id_moves.MAP, "respelled": respelled}
out.write_text(json.dumps(doc, indent=1) + "\n")
print(json.dumps({"tests": sum(len(e["tests"]) for e in doc["files"].values()), "respelled": len(respelled)}))
EOF
  local moved=$?
  log "the record through the move's table, exit $moved: $(tail -n 1 "$D/through-the-move.log")"
  local diffed=2
  if [ $moved -eq 0 ]; then
    (cd "$S" && "$PY" -B scripts/test_tiers.py diff --record "$D/record-through-the-move.json" \
      --run "$OUT/tier3" --out "$D/diff.json" --require-complete > "$D/diff.log" 2>&1)
    diffed=$?
    log "diff exit $diffed: $(head -n 1 "$D/diff.log")"
  fi
  "$HOSTPY" -I - "$OUT" "$D" "$record" "$moved" "$diffed" "$run_rc" "$cold_rc" "$collect_rc" "${LANE:-}" \
    "${CPUS:-}" > "$D/verdict.log" 2>&1 <<'EOF'
import json, sys
from pathlib import Path
out, d, record = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
moved, diffed = int(sys.argv[4]), int(sys.argv[5])
run_rc, cold_rc, collect_rc, lane, cpus = (sys.argv[6:11] + [""] * 5)[:5]
read = lambda p: json.loads(p.read_text()) if p.is_file() else None  # noqa: E731
diff, through = read(d / "diff.json"), read(d / "record-through-the-move.json")
run = read(out / "tier3" / "run.json")
cold = None if cold_rc == "" else cold_rc == "0"
verdict = {
    "kind": "cells.weekly_tier3@1",
    "revision": json.loads((out / "snapshot" / "SNAPSHOT.json").read_text())["git_revision"],
    "record": record, "lane": lane or None, "cpus": cpus or None,
    "cap_seconds": run and run.get("cap_seconds"), "files_run": run and len(run["files"]),
    "run_exit": run_rc or None, "collect_exit": collect_rc or None, "cold": cold,
    "through_the_move": {"exit": moved, "respelled": through and len(through["through_the_move"]["respelled"])},
    "diff_exit": diffed,
}
if diff:
    verdict.update({k: diff[k] for k in ("files_read", "files_unchanged", "counts", "caps_differ",
                                         "record_files_not_in_runs", "blocking")})
    verdict["reported"] = {e["kind"]: verdict["counts"][e["kind"]] for e in diff["reported"]}
verdict["passed"] = moved == 0 and diffed == 0 and collect_rc in ("", "0") and cold is not False
verdict["read"] = ("diff.json holds every entry; the record's file seconds came from its own run, so a "
                   "'time' entry is a hint, not a fault")
(d / "verdict.json").write_text(json.dumps(verdict, indent=1) + "\n")
print(json.dumps({k: verdict.get(k) for k in ("passed", "counts", "diff_exit")}))
sys.exit(0 if verdict["passed"] else 1)
EOF
  local judged=$?
  log "verdict exit $judged: $(tail -n 1 "$D/verdict.log")"
  return $judged
}

# Until it holds a lane's lock, everything here (the freeze too) stays on the pre-lock CPU: the
# unit may run on both lanes' CPUs, and nothing computes there without the lane's lock.
if [ "${1:-}" != --locked ]; then
  taskset -cp "$PRE_CPU" $$ > /dev/null || { echo "could not pin to CPU $PRE_CPU" >&2; exit 2; }
fi

case "${1:-}" in
  "")  # 1. Freeze REF, then run the frozen copy.
    OUT=$WEEKLY/$(date -u +%Y%m%d)
    [ ! -e "$OUT" ] || OUT=$OUT-$(date -u +%H%M%S)
    mkdir -p "$OUT"
    REV=$(git -C "$REPO" rev-parse --verify "$REF^{commit}") || { log "no $REF in $REPO"; finish 2; }
    log "weekly tier 3 of $REF $REV from $REPO into $OUT"
    git -C "$REPO" worktree add --quiet --detach "$OUT/tree" "$REV" >> "$OUT/weekly.log" 2>&1 \
      && "$PY" -B "$G/freeze_snapshot.py" "$OUT/tree" "$OUT/snapshot" --scope full --require-clean >> "$OUT/weekly.log" 2>&1
    rc=$?
    git -C "$REPO" worktree remove --force "$OUT/tree" >> "$OUT/weekly.log" 2>&1
    [ $rc -eq 0 ] && [ -f "$OUT/snapshot/scripts/gates/weekly_tier3.sh" ] \
      || { log "freezing $REF failed (exit $rc)"; finish 2; }
    exec bash "$OUT/snapshot/scripts/gates/weekly_tier3.sh" --run "$OUT" ;;
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
        [ $rc -eq 75 ] || [ $rc -eq $BUSY ] || break 2
      done
      if [ $(( $(date +%s) - start )) -ge "$WAIT_FREE" ]; then
        log "no lane free for $WAIT_FREE s: queueing for lane A"
        /usr/bin/flock "$LOCK_A" bash "$0" --locked A "$OUT" last
        break
      fi
      sleep "$POLL"
    done
    [ -f "$OUT/locked.done" ] || { log "no lock was held: nothing ran"; finish 2; }
    finish "$(cat "$OUT/locked.done")" ;;
  --locked)
    LANE=${2:?lane}; OUT=${3:?out}; LAST=${4:-}
    cpus=CPUS_$LANE; CPUS=${!cpus}; span=LANE_$LANE; lock=LOCK_$LANE
    S=$OUT/snapshot
    done_locked() { echo "$1" > "$OUT/locked.done"; exit "$1"; }
    if ! "$HOSTPY" -I "$S/scripts/gates/lane_busy.py" --cpus "${!span}" --lock "${!lock}" \
        --json "$OUT/lanecheck-$LANE.json" > /dev/null 2>&1; then
      [ -n "$LAST" ] && { log "lane $LANE busy without its lock (lanecheck-$LANE.json): not run"; done_locked 2; }
      log "lane $LANE busy without its lock (lanecheck-$LANE.json): the lock let go, to try again"
      exit $BUSY
    fi
    taskset -cp "$CPUS" $$ > /dev/null || { log "could not pin to lane $LANE's CPUs $CPUS"; done_locked 2; }
    log "lane $LANE, lock held, the lane idle; affinity $(taskset -pc $$ | sed 's/.*: //')"
    log "JAX's persistent compilation cache disabled in every process (JAX_ENABLE_COMPILATION_CACHE=false, \
no cache folder; D321 R2)"
    start=$(date +%s)
    (cd "$S" && PYTHONPATH="$S/src:$S" "$PY" -B scripts/test_tiers.py run --tiers "${TIERS:-tests/test_tiers.json}" \
      --tier 3 --out "$OUT/tier3" --cpus "$CPUS" --cap "$CAP" > "$OUT/tier3.log" 2>&1)
    run_rc=$?
    log "tier 3 exit $run_rc (not the verdict: tier-3 rows hold no outcome) seconds $(( $(date +%s) - start )): $(tail -n 1 "$OUT/tier3.log")"
    "$HOSTPY" -I "$S/scripts/gates/gate_steps.py" jax-entries "$OUT/tier3" > "$OUT/cold.log" 2>&1
    cold_rc=$?
    log "cold check exit $cold_rc: $(tail -n 1 "$OUT/cold.log")"
    (cd "$S" && PYTHONPATH="$S/src:$S" "$PY" -B scripts/test_tiers.py collect --run "$OUT/tier3" \
      --cpu "${CPUS%%,*}" > "$OUT/collect.log" 2>&1)
    collect_rc=$?
    log "collect exit $collect_rc: $(tail -n 1 "$OUT/collect.log")"
    if judge "$OUT" "$run_rc" "$cold_rc" "$collect_rc"; then
      log "passed: $OUT/verdict.json"
      done_locked 0
    fi
    log "failed or incomplete: $OUT/verdict.json"
    done_locked 1 ;;
  --judge)  # Into OUT/judged-TIME, beside the run's own verdict.
    OUT=${2:?out}
    D=$OUT/judged-$(date -u +%Y%m%dT%H%M%S)
    mkdir -p "$D"
    log "judged again into $D, against ${RECORD:-$OUT/snapshot/tests/tier3_record.json}"
    judge "$D" "" "" ""
    exit $? ;;
  *) echo "usage: weekly_tier3.sh [--run OUT | --judge OUT]" >&2; exit 2 ;;
esac
