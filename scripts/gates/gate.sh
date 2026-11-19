#!/bin/bash
# The landing gate, failing fast (the testing plan of 19 November 2026, items A and B; D223, D224).
# One script for every owner. It is lane-aware like the owners' gate-laneA.sh copies, which it
# supersedes for new gates; those copies stay byte for byte, since recorded runs cite them.
#
# Before the lock: one light CPU (PRELOCK_CPU, default 23) at nice PRELOCK_NICE (default 19, below
# the owners' pre-gates at 10). PRELOCK=lane runs the same steps as the lane's first stage instead,
# when the light CPUs are full. About two CPU-minutes, plus the head's changed test files:
#   0. preflight: both snapshots complete and clean; crossrev's record holds exactly the runner's
#      sets; c1's save, the baseline, the tier record, the declared files and the guard set exist;
#   1. IDs: the head's collected test IDs against the base's (cached per main revision), with the
#      additions (ADDITIONS_FROM) and the removals (REMOVED_OK_FILE) declared before the gate;
#   2. the guard set and every test file the head changed against the base, through the tier
#      runner, each against its row (scripts/gates/gate_steps.py select).
# Under the lane's lock (flock's command form: a flock killed while it waits runs nothing), the
# cheapest stage first, stopping at the first failure:
#   3. crossrev: the head's sets against the base's, set by set on the lane's CPUs (one CPU per set).
#      The base side is cached per main revision; on a miss it runs on half the lane, beside the
#      head. A difference passes only where CROSSREV_EXPECTED declares it (SET/FILE lines, an
#      exact list), for a by-design program change whose record is not renewed yet;
#   4. tiers 1+2 of the head against TIERS (default its tests/test_tiers.json), cap 300 s;
#   5. G1: the 113 worlds as eight one-CPU shards, planned from the last passing G1's world seconds
#      (GATE_CACHE/g1-seconds.json, else the baseline's), merged and compared bitwise with c1's
#      merged save.
# FR's bitwise set and R1 stay their own units (fr_landing_set.sh; fingerprints_landing.sh, which
# caches R1's base record per main revision in the same GATE_CACHE).
#
# Run the copy in the gate's own frozen base snapshot (BASE_S/scripts/gates/gate.sh), so a queued
# gate's script never changes under it.
# Environment: LANE (A or B; "custom" with GATE_LOCK and GATE_CPUS, for tests and replays only),
# TIERS, ADDITIONS_FROM, REMOVED_OK_FILE, CROSSREV_EXPECTED, CROSSREV_SETS (default every set),
# PRELOCK, PRELOCK_CPU, PRELOCK_NICE, PRELOCK_ONLY (1: stop after the pre-lock steps, for an owner's
# check before queueing), GATE_CACHE (default /mnt/workspaces/Cells/gate-cache; empty turns the
# cache off), PY and HOSTPY.
# Usage (a run_detached unit's command): gate.sh HEAD_S BASE_S OUT
#   OUT/done holds 0 (pass), 1 (refused) or 2 (not run: bad arguments, or the lock never held).
set -u
if [ "${1:-}" = --locked ]; then LOCKED=1; shift; else LOCKED=0; fi
S=${1:?head snapshot}; B=${2:?base snapshot}; OUT=${3:?out}
G=$(cd "$(dirname "$0")" && pwd)
STEPS=$G/gate_steps.py
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
HOSTPY=${HOSTPY:-python3}
C1=${C1:-/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/c1-3c10b833/g1/merged}
BASELINE=${BASELINE:-/mnt/workspaces/Cells/d172-restructure-20261115-01/acceptance/baseline-44227075}
REC=${REC:-/mnt/workspaces/Cells/core-fixes-20261116/record-cda5dc82}
TIERS=${TIERS:-tests/test_tiers.json}
GATE_CACHE=${GATE_CACHE-/mnt/workspaces/Cells/gate-cache}
PRELOCK=${PRELOCK:-light}; PRELOCK_CPU=${PRELOCK_CPU:-23}; PRELOCK_NICE=${PRELOCK_NICE:-19}
case "${LANE:-A}" in
  A) LOCK=/mnt/workspaces/Cells/locks/gate-cores-0-3.lock; CPUS=0,1,2,3,16,17,18,19 ;;
  B) LOCK=/mnt/workspaces/Cells/locks/gate-cores-8-11.lock; CPUS=8,9,10,11,24,25,26,27 ;;
  custom) LOCK=${GATE_LOCK:?LANE=custom needs GATE_LOCK}; CPUS=${GATE_CPUS:?LANE=custom needs GATE_CPUS} ;;
  *) echo "LANE must be A, B or custom" >&2; exit 2 ;;
esac
read -r -a CPU <<< "${CPUS//,/ }"
I0=${CPU[0]}
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
export REC C1 BASELINE TIERS
mkdir -p "$OUT"
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/gate.log"; }
finish() { log "done status $1"; echo "$1" > "$OUT/done"; exit "$1"; }
steps() { "$HOSTPY" -I "$STEPS" "$@"; }
short() { tr -d '\n' < "$1" | cut -c1-400; }

if [ "$PRELOCK" = lane ]; then PRE_CPUS=$CPUS; light() { "$@"; }
else PRE_CPUS=$PRELOCK_CPU; light() { taskset -c "$PRELOCK_CPU" nice -n "$PRELOCK_NICE" "$@"; }; fi

collect() {  # TREE PREFIX: every test ID under tests/, in the tier runner's environment.
  local tree=$1 prefix=$2 rc
  mkdir -p "$prefix-scratch"
  (cd "$tree" && PYTHONPATH="$tree/src" CELLS_OUTPUT_ROOT="$prefix-scratch/outputs" \
    CELLS_COMPONENT_EVIDENCE="$prefix-scratch/evidence" light "$PY" -B -m pytest -q \
    -p no:cacheprovider --continue-on-collection-errors --collect-only tests) > "$prefix.log" 2>&1
  rc=$?
  grep "::" "$prefix.log" | sort > "$prefix.ids"
  echo "{\"exit\": $rc, \"ids\": $(wc -l < "$prefix.ids")}" > "$prefix.json"
}

prelock() {  # Steps 0-2; returns 1 at the first refusal.
  local P=$OUT/prelock base_ids found rc start
  mkdir -p "$P/ids"
  start=$(date +%s)
  steps preflight "$S" "$B" "$P/preflight.json" > "$P/preflight.log" 2>&1
  rc=$?; log "prelock preflight exit $rc: $(short "$P/preflight.log")"
  [ $rc -eq 0 ] || { log "stopped at preflight"; return 1; }
  collect "$S" "$P/ids/collect-head"
  found=
  if [ -n "$GATE_CACHE" ]; then
    found=$(steps cache-find "$GATE_CACHE" ids "$B" --python "$PY" 2> /dev/null)
  fi
  if [ -n "$found" ]; then
    base_ids=$found/collect-base; log "prelock ids: base listing from the cache, $found"
  else
    collect "$B" "$P/ids/collect-base"; base_ids=$P/ids/collect-base
    if [ -n "$GATE_CACHE" ] && [ "$(wc -l < "$base_ids.ids")" -gt 0 ]; then
      mkdir -p "$P/ids/publish" && cp "$base_ids".{ids,log,json} "$P/ids/publish/"
      log "prelock ids: base listing published, $(steps cache-publish "$GATE_CACHE" ids "$B" \
        "$P/ids/publish" --python "$PY" 2>&1 | tail -n 1)"
    fi
  fi
  steps ids "$base_ids" "$P/ids/collect-head" "$P/ids/verdict.json" > "$P/ids/verdict.log" 2>&1
  rc=$?; log "ids, additions only, exit $rc: $(short "$P/ids/verdict.log")"
  [ $rc -eq 0 ] || { log "stopped at ids"; return 1; }
  steps select "$S" "$B" "$TIERS" "$P/subset.json" > "$P/select.log" 2>&1 \
    || { log "prelock select failed: $(short "$P/select.log")"; return 1; }
  (cd "$S" && PYTHONPATH="$S/src:$S" light "$PY" -B scripts/test_tiers.py run --tiers "$P/subset.json" \
    --tier 1 2 9 --out "$P/tests" --cpus "$PRE_CPUS" --cap 300 > "$P/tests.log" 2>&1)
  steps prelock-verdict "$P/subset.json" "$P/tests" "$P/tests-verdict.json" > "$P/tests-verdict.log" 2>&1
  rc=$?; log "prelock tests exit $rc ($(short "$P/select.log")): $(short "$P/tests-verdict.log")"
  [ $rc -eq 0 ] || { log "stopped at the pre-lock tests"; return 1; }
  log "prelock passed, seconds $(( $(date +%s) - start ))"
}

if [ $LOCKED -eq 0 ]; then
  for s in "$S" "$B"; do [ -f "$s/SNAPSHOT.json" ] || { log "no snapshot $s"; finish 2; }; done
  log "gate of head $S base $B; lane ${LANE:-A}, CPUs $CPUS; pre-lock $PRELOCK on $PRE_CPUS; \
tiers $TIERS; additions from ${ADDITIONS_FROM:-none}; removals listed in ${REMOVED_OK_FILE:-none}; \
crossrev differences declared in ${CROSSREV_EXPECTED:-none}; cache ${GATE_CACHE:-off}; tool $G"
  if [ "$PRELOCK" != lane ]; then prelock || finish 1; fi
  if [ "${PRELOCK_ONLY:-0}" = 1 ]; then log "pre-lock only (PRELOCK_ONLY=1): not queued"; finish 0; fi
  log "waiting for $LOCK"
  /usr/bin/flock "$LOCK" bash "$0" --locked "$S" "$B" "$OUT"
  rc=$?
  [ -f "$OUT/locked.done" ] || { log "the lock was never held (flock exit $rc): nothing ran under it"; finish 2; }
  finish "$(cat "$OUT/locked.done")"
fi

# ----------------------------------------------------------------------------- under the lock
done_locked() { echo "$1" > "$OUT/locked.done"; exit "$1"; }
log "lane ${LANE:-A}, lock held; affinity $(taskset -pc $$ | sed 's/.*: //')"
if [ "$PRELOCK" = lane ]; then prelock || done_locked 1; fi

# 3. crossrev
start=$(date +%s)
SETS=${CROSSREV_SETS:-$(steps crossrev-sets)}
read -r -a SET <<< "$SETS"
X=$OUT/crossrev; mkdir -p "$X/head-vs-base"
found=
if [ -n "$GATE_CACHE" ]; then
  found=$(steps cache-find "$GATE_CACHE" crossrev "$B" "record=$REC" "sets=$SETS" --python "$PY" 2> /dev/null)
fi
if [ -n "$found" ]; then
  BASE_X=$found/sides; log "crossrev base from the cache, $found"
  steps crossrev-run "$S" "$X/head" --cpus "$CPUS" --sets "${SET[@]}" --python "$PY" > "$X/head.log" 2>&1
  head_rc=$?; base_rc=0
else
  half=$(( ${#CPU[@]} / 2 )); [ $half -ge 1 ] || half=1
  BCPUS=$(IFS=,; echo "${CPU[*]:0:$half}"); HCPUS=$(IFS=,; echo "${CPU[*]:$half}")
  [ -n "$HCPUS" ] || HCPUS=$BCPUS
  BASE_X=$X/base
  steps crossrev-run "$B" "$BASE_X" --cpus "$BCPUS" --sets "${SET[@]}" --python "$PY" > "$X/base.log" 2>&1 &
  bpid=$!
  steps crossrev-run "$S" "$X/head" --cpus "$HCPUS" --sets "${SET[@]}" --python "$PY" > "$X/head.log" 2>&1
  head_rc=$?; wait $bpid; base_rc=$?
  if [ $base_rc -eq 0 ] && [ -n "$GATE_CACHE" ]; then
    mkdir -p "$X/publish" && ln -s "$BASE_X" "$X/publish/sides"
    log "crossrev base published, $(steps cache-publish "$GATE_CACHE" crossrev "$B" "$X/publish" \
      "record=$REC" "sets=$SETS" --python "$PY" 2>&1 | tail -n 1)"
  fi
fi
log "crossrev actions: base exit $base_rc, head exit $head_rc"
for set in "${SET[@]}"; do
  (cd "$S" && PYTHONPATH="$S/src:$S" taskset -c "$I0" "$PY" -B -m validation.tissue.composite_crossrev \
    compare "$BASE_X/$set" "$X/head/$set" > "$X/head-vs-base/compare-$set.txt" 2>&1)
  (cd "$S" && PYTHONPATH="$S/src:$S" taskset -c "$I0" "$PY" -B -m validation.tissue.composite_crossrev \
    compare "$REC/$set" "$X/head/$set" > "$X/head-vs-record-$set.txt" 2>&1)
  log "crossrev head vs base $set: $(tail -n 1 "$X/head-vs-base/compare-$set.txt"); head vs the record \
(information): $(tail -n 1 "$X/head-vs-record-$set.txt")"
done
steps crossrev-verdict "$BASE_X" "$X/head" "$X/head-vs-base" "$X/verdict.json" --sets "${SET[@]}" \
  ${CROSSREV_EXPECTED:+--expected "$CROSSREV_EXPECTED"} > "$X/verdict.log" 2>&1
rc=$?
[ $head_rc -eq 0 ] && [ $base_rc -eq 0 ] || rc=1
n=$("$HOSTPY" -I -c "import json,sys; d=json.load(open(sys.argv[1])); print(d['identical'], 'of', d['sets'], \
'sets identical,', d['as_declared'], 'as declared')" "$X/verdict.json" 2>/dev/null || echo "no verdict")
log "crossrev head vs base: $n, seconds $(( $(date +%s) - start )), exit $rc"
[ $rc -eq 0 ] || { log "stopped at crossrev"; done_locked 1; }

# 4. tiers 1+2
start=$(date +%s)
(cd "$S" && PYTHONPATH="$S/src:$S" "$PY" -B scripts/test_tiers.py run --tiers "$TIERS" \
  --tier 1 2 --out "$OUT/tiers-1+2" --cpus "$CPUS" --cap 300 > "$OUT/tiers-1+2.log" 2>&1)
rc=$?
log "tiers 1+2 exit $rc seconds $(( $(date +%s) - start )): $(tail -n 1 "$OUT/tiers-1+2.log")"
[ $rc -eq 0 ] || { log "stopped at tiers"; done_locked 1; }

# 5. G1
start=$(date +%s)
G1=$OUT/g1; mkdir -p "$G1/parts"
steps g1-plan "$BASELINE" "${#CPU[@]}" "$G1/plan.json" ${GATE_CACHE:+--seconds "$GATE_CACHE/g1-seconds.json"} \
  >> "$G1/g1.log" 2>&1 || { log "G1 plan failed"; done_locked 1; }
log "G1 plan: $(tail -n 1 "$G1/g1.log")"
shard() {  # K CPU: the shard's groups in turn, one process each, on one CPU.
  local k=$1 code=0 j=0 set worlds
  echo "$(date -u +%FT%TZ) shard $k cpus $(nproc) affinity $(taskset -pc $BASHPID | sed 's/.*: //')" >> "$G1/g1.log"
  nproc > "$G1/shard-$k.cpus"
  while IFS=$'\t' read -r set worlds; do
    # shellcheck disable=SC2086
    (cd "$S" && PYTHONPATH="$S/src:$S" "$PY" -B validation/results_baseline.py save "$G1/parts/part-$k-$j" \
      --sets "$set" --worlds $worlds --from "$BASELINE") >> "$G1/shard-$k.log" 2>&1 || code=1
    echo "$(date -u +%FT%TZ) shard $k group $j $set exit $code" >> "$G1/g1.log"
    j=$((j + 1))
  done < <(steps g1-groups "$G1/plan.json" "$k")
  return $code
}
k=0
for cpu in "${CPU[@]}"; do (taskset -cp "$cpu" $BASHPID > /dev/null && shard "$k" "$cpu") & k=$((k + 1)); done
wait
counts=$(cat "$G1"/shard-*.cpus 2>/dev/null | sort -u | tr "\n" " ")
if [ "$counts" != "1 " ]; then log "G1 not compared: shard CPU counts '$counts' (c1: 1)"; done_locked 1; fi
steps g1-merge "$G1/parts" "$G1/merged" >> "$G1/g1.log" 2>&1 || { log "G1 merge failed"; done_locked 1; }
(cd "$S" && PYTHONPATH="$S/src:$S" taskset -c "$I0" "$PY" -B validation/results_baseline.py compare \
  "$C1" "$G1/merged" --output "$G1/compare-vs-c1.json" > "$G1/compare-vs-c1.log" 2>&1)
rc=$?
log "G1 compare exit $rc seconds $(( $(date +%s) - start )): $(tail -n 1 "$G1/compare-vs-c1.log")"
[ $rc -eq 0 ] || { log "stopped at G1"; done_locked 1; }
if [ -n "$GATE_CACHE" ]; then
  log "G1 seconds for the next plan: $(steps g1-seconds "$G1/merged" "$GATE_CACHE/g1-seconds.json" 2>&1 | tail -n 1)"
fi
done_locked 0
