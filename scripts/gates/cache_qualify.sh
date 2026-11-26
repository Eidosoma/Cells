#!/bin/bash
# The qualification of JAX's persistent compilation cache on CPU: its bits, its memory and whether it
# engaged (the testing plan of 19 November 2026, section 5.3; D229). It turns the cache on in no
# gate: every cache folder here is the run's own (OUT/cache-A, OUT/cache-B).
#
# Trees: the head bf4e47e0 (it passed lane A on 19 November at 09:28 UTC) and its base e4f84d4a;
# G3's controls of 18 November: the unplanted tree e16e26bb, C1's planted tree (selective_flux
# x (1 + 1e-9)) and C2' (crossrev-base/symport's K+ x (1 + 1e-9)). Engine models: G1's worlds
# (cells.model.resolved_pump_composite@1, cells.model.resolved_pump_replacement@1, cells.model.resolved_pump_water@1 and @2,
# cells.model.resolved_pump_tissue@3), FR-4's and FR-5's compartment-pH worlds on the resolved pump @3 path, and
# the tier suite.
#
# The arms, in this order, on the lane's CPUs under its lock:
#   off       the reference, with the cache off (JAX_ENABLE_COMPILATION_CACHE=false): G1 by one shared
#             plan, FR's set and the tier-3 stage's files (TIER3_FILES, cap 600 s), with each G1
#             group's and FR process's peak RSS. Tiers 1+2 come per test ID from bf4e47e0's own gate
#             run (GATE_RUN, cap 300 s, which must hold no cache entry), or run here if it is empty;
#   cold      an empty cache A, every compile written (minimum compile time 0), cache errors raised:
#             tiers 1+2 at eight concurrent files (writes racing reads), G1 in one-CPU shards, FR's
#             four queues on the lane's cores beside the tier-3 files on their siblings, crossrev's
#             sets against the record (crossrev compiles a little: 2% of its CPU), and the lead's
#             replication check (55 files);
#   warm      the same with cache A as cold left it; warm2 again (stable reads);
#   xrev      cache B written by the base (tiers 1+2, G1), then read by the head (xrev-head): bits
#             across revisions, and the hit rate a landing would see;
#   negative  cache A on G3's three controls; each must equal, bit for bit, its own run of
#             18 November without the cache, so no planted change is masked by a stale executable.
# Then caches A and B, two independent compiles of most programs, are compared program by program
# offline (cache_compare.py), as information. JAX's byte check (jax_compilation_cache_check_contents)
# is not used: on XLA:CPU it fails by construction (the rehearsal of 19 November 2026; the testing
# plan's section 10.6). Executables hold their kernels in a varying order and embed paths, and three
# threefry kernels compiled to different machine code depending on the compiling process's history
# or tree, with bitwise-identical results. The pass criterion is the results, in every arm.
# The L4 failure's own test (tests/integration/test_integrated_ensemble_gpu.py: a pause in one
# process, a resume in another) runs only on a GPU, so that exact pairing is not reproduced here.
# What stands in: every warm executable crossed processes through the cache (cold's processes
# compiled it); FR's windowed arms continue from a saved start; and the tier-3 stage has
# window-replay, checkpoint and subprocess bitwise tests.
# The engine's CLIs (cells.execution.output_paths.configure_caches) give their child processes a
# cache folder under CELLS_OUTPUT_ROOT, which the tier runner sets per test file. Under the tier
# runner those children use that per-file folder, new in every arm, never cache A. The verdict
# counts them; this harness leaves that engine behaviour (src/) as it is.
#
# After every stage it records (OUT/stages.jsonl) the seconds, the cache's new entries, the unit's
# largest anonymous memory (sampled every 5 s) and its out-of-memory kills. The verdict
# (gate_steps.py cache-verdict, into OUT/verdict.json) lists every criterion; the qualification
# passes only when all hold. About four lane-hours.
#
# Usage (a run_detached unit's command): cache_qualify.sh OUT
#   LANE: A or B, or custom with GATE_LOCK and GATE_CPUS (a rehearsal). GO: the go-file (default
#   OUT/GO), checked every 60 s before the lock is taken, in flock's command form. Every input below
#   may be overridden for a rehearsal on reduced inputs (FR_SET=smoke runs one quick part).
#   OUT/done: the verdict's exit (0 pass, 1 fail), or 2 (not run).
set -u
if [ "${1:-}" = --locked ]; then LOCKED=1; shift; else LOCKED=0; fi
OUT=${1:?out}
G=$(cd "$(dirname "$0")" && pwd)
TT=$(cd "$G/.." && pwd)/test_tiers.py
STEPS=$G/gate_steps.py
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
HOSTPY=${HOSTPY:-python3}
W=/mnt/workspaces/Cells
O3=$W/core-pass-operators-3-20261119 D172=$W/d172-restructure-20261115-01 T3=$W/tier3-final-20261118
HEAD_S=${HEAD_S:-$O3/snapshot-head-bf4e47e0}
BASE_S=${BASE_S:-$O3/snapshot-base-e4f84d4a}
GATE_RUN=${GATE_RUN-$O3/gate-bf4e47e0/laneA/tiers-1+2}
TIERS_JSON=${TIERS_JSON:-tests/test_tiers.json}  # relative: each tree's own record
C1=${C1:-/mnt/workspaces/Cells/global-charge-bound-20261122/c1-605331c2/merged}  # Renewed for D305's fix (D307), as gate.sh's.
BASELINE=${BASELINE:-$D172/acceptance/baseline-44227075}
REC=${REC:-$W/core-fixes-20261116/record-cda5dc82}
CROSSREV_SETS=${CROSSREV_SETS:-}
REPL_CHECK=${REPL_CHECK:-$W/core-pass-kickoff-20261118/tools/replication_check.sh}
UNPLANTED_S=${UNPLANTED_S:-$T3/snapshot-e16e26bb}
PLANTED_S=${PLANTED_S:-$T3/g3/c1-tree}
UNPLANTED_REF=${UNPLANTED_REF:-$T3/g3/unplanted/merged}
PLANTED_REF=${PLANTED_REF:-$T3/g3/c1/merged}
C2P_ORIGIN=${C2P_ORIGIN:-$T3/g3/c2prime-origin}
C2P_REF=${C2P_REF:-$T3/g3/c2prime-part}
FR=$D172/fr45
FRR=/mnt/workspaces/Cells/fr-baselines/805c48a4-20261126  # FR's baselines renewed for D307 and the ID move (D345), as fr_landing_holder.sh's (D392's copy).
F4=${F4:-$FRR/fr4-quick} F5=${F5:-$FRR/fr5}
FR_START=${FR_START:-$FR/rehearsal-20261117/run-e79b4232/fr5/start/start.json}
FR_BEFORE=${FR_BEFORE:-$FRR/windowed}
FR_SET=${FR_SET:-full}
TIER3_FILES=${TIER3_FILES:-"tests/unit/test_integrated_ensemble.py tests/unit/test_vector_windows_bitwise.py"}
DEFAULT_CACHE=${DEFAULT_CACHE:-$W/cache/jax}
GO=${GO:-$OUT/GO}
case "${LANE:-B}" in
  A) LOCK=$W/locks/gate-cores-0-3.lock; CPUS=0,1,2,3,16,17,18,19 ;;
  B) LOCK=$W/locks/gate-cores-8-11.lock; CPUS=8,9,10,11,24,25,26,27 ;;
  custom) LOCK=${GATE_LOCK:?LANE=custom needs GATE_LOCK}; CPUS=${GATE_CPUS:?LANE=custom needs GATE_CPUS} ;;
  *) echo "LANE must be A, B or custom" >&2; exit 2 ;;
esac
read -r -a CPU <<< "${CPUS//,/ }"
I0=${CPU[0]}
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
mkdir -p "$OUT"
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/qualify.log"; }
steps() { "$HOSTPY" -I "$STEPS" "$@"; }
default_cache() {  # FILE: the shared default cache folder's file count and newest change
  "$HOSTPY" -I -c 'import json, os, sys
d = sys.argv[1]
names = os.listdir(d) if os.path.isdir(d) else []
newest = max((os.stat(os.path.join(d, n)).st_mtime_ns for n in names), default=0)
json.dump({"folder": d, "files": len(names), "newest_mtime_ns": newest}, open(sys.argv[2], "w"))' \
    "$DEFAULT_CACHE" "$1"
}

if [ $LOCKED -eq 0 ]; then
  [ ! -e "$OUT/done" ] || { echo "Refused: $OUT was used before (it holds done)" >&2; exit 2; }
  refuse() { log "refused before the lock: $*"; echo 2 > "$OUT/done"; exit 2; }
  for s in "$HEAD_S" "$BASE_S" "$UNPLANTED_S" "$PLANTED_S"; do
    [ -f "$s/SNAPSHOT.json" ] || refuse "no snapshot $s"
  done
  for m in "$C1" "$BASELINE" "$UNPLANTED_REF" "$PLANTED_REF" "$C2P_REF"; do
    [ -f "$m/manifest.json" ] || refuse "no saved worlds at $m"
  done
  for f in "$REC" "$C2P_ORIGIN" "$F4" "$F5" "$FR_START" "$FR_BEFORE" "$REPL_CHECK" "$PY" /usr/bin/time; do
    [ -e "$f" ] || refuse "missing $f"
  done
  "$PY" -B "$TT" diff --help > /dev/null 2>&1 || refuse "$TT has no diff step"
  if [ -n "$GATE_RUN" ]; then
    got=$("$HOSTPY" -I -c 'import json, sys
d = json.load(open(sys.argv[1]))
print(d["provenance"]["root"], d.get("cap_seconds"))' "$GATE_RUN/run.json" 2>/dev/null)
    [ "$got" = "$HEAD_S 300.0" ] || refuse "GATE_RUN $GATE_RUN is not a run at cap 300 s on $HEAD_S ($got)"
  fi
  tiers_json=$TIERS_JSON; [[ $tiers_json = /* ]] || tiers_json=$HEAD_S/$tiers_json
  # shellcheck disable=SC2086
  steps qualify-subsets "$tiers_json" "$OUT" --tier3 $TIER3_FILES \
    >> "$OUT/qualify.log" 2>&1 || refuse "the tier subsets (qualify-subsets)"
  steps g1-plan "$BASELINE" "${#CPU[@]}" "$OUT/g1-plan.json" >> "$OUT/qualify.log" 2>&1 || refuse "G1's plan"
  log "cache qualification: head $HEAD_S, base $BASE_S; lane ${LANE:-B} ($CPUS); tool $G; OFF's tiers \
from ${GATE_RUN:-a run here}; waiting for $GO"
  until [ -e "$GO" ]; do sleep 60; done
  log "the go-file is present; waiting for $LOCK"
  rm -f "$OUT/locked.done"
  /usr/bin/flock "$LOCK" bash "$0" --locked "$OUT"
  rc=$?
  [ -f "$OUT/locked.done" ] || { log "the lock was never held (flock exit $rc)"; echo 2 > "$OUT/done"; exit 2; }
  log "done status $(cat "$OUT/locked.done")"
  cp "$OUT/locked.done" "$OUT/done"
  exit "$(cat "$OUT/done")"
fi

# ----------------------------------------------------------------------------- under the lock
taskset -cp "$CPUS" $$ > /dev/null || { echo 2 > "$OUT/locked.done"; exit 2; }
log "lock held; affinity $(taskset -pc $$ | sed 's/.*: //')"
CG=/sys/fs/cgroup$(cut -d: -f3 /proc/self/cgroup | head -n 1)
half=$(( ${#CPU[@]} / 2 )); [ $half -ge 1 ] || half=1
CORES=("${CPU[@]:0:$half}"); SIBS=("${CPU[@]:$half}"); [ ${#SIBS[@]} -gt 0 ] || SIBS=("${CORES[@]}")
SIBLINGS=$(IFS=,; echo "${SIBS[*]}")
A=$OUT/cache-A B=$OUT/cache-B NONE=$OUT/no-cache
mkdir -p "$A" "$B" "$OUT/bin"
cat > "$OUT/bin/python-rss" <<EOF
#!/bin/bash
# Written by cache_qualify.sh: the interpreter, appending its own peak RSS to RSS_LOG.
exec /usr/bin/time -a -o "\${RSS_LOG:?}" -f '%M %e %x %C' "$PY" "\$@"
EOF
chmod +x "$OUT/bin/python-rss"
default_cache "$OUT/default-cache-before.json"
E=()  # The current arm's environment.
TCACHE=  # The current arm's cache folder, for a tier runner that takes --jax-cache (empty: off).
with_cache() {  # CACHE. Enabled explicitly: run_detached.sh units default to it off (D321).
  E=(JAX_ENABLE_COMPILATION_CACHE=true JAX_COMPILATION_CACHE_DIR="$1" JAX_PERSISTENT_CACHE_MIN_COMPILE_TIME_SECS=0
     JAX_PERSISTENT_CACHE_MIN_ENTRY_SIZE_BYTES=0 JAX_RAISE_PERSISTENT_CACHE_ERRORS=true)
  TCACHE=$1
}
entries() { if [ -d "$1" ]; then find "$1" -maxdepth 1 -name '*-cache' | wc -l; else echo 0; fi; }
anon() { awk '$1 == "anon" {print $2}' "$CG/memory.stat" 2>/dev/null || echo 0; }
ooms() { awk '$1 == "oom_kill" {print $2}' "$CG/memory.events" 2>/dev/null || echo 0; }
stage() {  # ARM NAME CACHE FUNCTION ARGS...: one stage, recorded in OUT/stages.jsonl
  local arm=$1 name=$2 cache=$3; shift 3
  local d=$OUT/$arm t0 e0 k0 rc sampler
  mkdir -p "$d"
  e0=$(entries "$cache"); k0=$(ooms); t0=$(date +%s)
  (cd "$cache" 2> /dev/null && LC_ALL=C ls) > "$d/.$name.before"
  echo 0 > "$d/.$name.anon"
  (m=0; while :; do a=$(anon); if [ "${a:-0}" -gt "$m" ]; then m=$a; echo "$m" > "$d/.$name.anon"; fi
   sleep 5; done) &
  sampler=$!
  "$@"; rc=$?
  kill "$sampler" 2> /dev/null; wait "$sampler" 2> /dev/null
  (cd "$cache" 2> /dev/null && LC_ALL=C ls) | LC_ALL=C comm -13 "$d/.$name.before" - > "$d/$name-new-entries.txt"
  printf '{"arm": "%s", "stage": "%s", "exit": %d, "seconds": %d, "entries_before": %d, "entries_after": %d, "anon_peak": %d, "oom_kills": %d, "utc": "%s"}\n' \
    "$arm" "$name" "$rc" "$(( $(date +%s) - t0 ))" "$e0" "$(entries "$cache")" "$(cat "$d/.$name.anon")" \
    "$(( $(ooms) - k0 ))" "$(date -u +%FT%TZ)" >> "$OUT/stages.jsonl"
  rm -f "$d/.$name.before" "$d/.$name.anon"
  log "$arm $name: $(tail -n 1 "$OUT/stages.jsonl")"
}
tiers_run() {  # TREE DIR TIERS WHICH CPUS CAP: one tier run in the arm's environment
  local tree=$1 d=$2 tiers=$3 which=$4 cpus=$5 cap=$6 cache=()
  # A tree whose runner disables the cache unless told (D321 R1) is given the arm's folder; an older
  # tree's runner takes it from the environment, as before.
  if [ -n "$TCACHE" ] && grep -q -- '--jax-cache' "$tree/scripts/test_tiers.py"; then cache=(--jax-cache "$TCACHE"); fi
  # shellcheck disable=SC2086
  (cd "$tree" && env -u JAX_COMPILATION_CACHE_DIR PYTHONPATH="$tree/src:$tree" "${E[@]}" "$PY" -B \
    scripts/test_tiers.py run --tiers "$tiers" --tier $which --out "$d" --cpus "$cpus" --cap "$cap" \
    "${cache[@]}" > "$d.log" 2>&1)
  log "tiers $d: $(tail -n 1 "$d.log" | cut -c1-200)"
}
per_id() {  # RUN RECORD LISTING...: the run read per test ID against OFF's record (test_tiers.py diff)
  local d=$1 record=$2; shift 2
  "$PY" -B "$TT" diff --record "$record" --run "$d" --collected "$@" --out "$d/diff.json" > "$d/diff.log" 2>&1
  log "per ID $d: $(head -n 1 "$d/diff.log" | cut -c1-200)"
}
freeze() {  # RUN RECORD LISTING: OFF's record of a run, from the IDs collected on its own tree
  "$PY" -B "$TT" collect --run "$1" --out "$3" --cpu "$I0" > "$3.log" 2>&1
  "$PY" -B "$TT" freeze --run "$1" --collected "$3" --out "$2" > "$2.log" 2>&1
  log "OFF's record $2: $(tail -n 1 "$2.log" | cut -c1-200)"
}
# A tree's own table of renamed IDs (D345), where it has one: what was saved under an old spelling is
# read through it (validation/id_table.py), so a tree before the rename is asked for nothing.
id_map() { local t=$1/src/cells/registry/renamed_ids.py; [ ! -f "$t" ] || printf '%s\n' --map "$t"; }
g1() {  # TREE DIR REF [FROM]: G1's worlds by the shared plan, one shard per CPU, each group's peak
        # RSS; merged and compared bit for bit with REF
  local tree=$1 d=$2 ref=$3 from=${4:-$BASELINE} k=0 cpu
  local -a pids=() ids=()
  mkdir -p "$d/parts"
  mapfile -t ids < <(id_map "$tree")
  for cpu in "${CPU[@]}"; do
    (taskset -cp "$cpu" $BASHPID > /dev/null; nproc > "$d/shard-$k.cpus"; j=0
     while IFS=$'\t' read -r set worlds; do
       # shellcheck disable=SC2086
       (cd "$tree" && env -u JAX_COMPILATION_CACHE_DIR PYTHONPATH="$tree/src:$tree" "${E[@]}" /usr/bin/time \
         -f '%M %e' -o "$d/rss-$k-$j.txt" "$PY" -B validation/results_baseline.py save "$d/parts/part-$k-$j" \
         --sets "$set" --worlds $worlds --from "$from" "${ids[@]}") < /dev/null >> "$d/shard-$k.log" 2>&1
       echo "$(date -u +%FT%TZ) shard $k group $j $set exit $?" >> "$d/g1.log"
       j=$((j + 1))
     done < <(steps g1-groups "$OUT/g1-plan.json" "$k")) &
    pids+=($!); k=$((k + 1))
  done
  wait "${pids[@]}"
  steps g1-merge "$d/parts" "$d/merged" >> "$d/g1.log" 2>&1
  (cd "$tree" && PYTHONPATH="$tree/src:$tree" taskset -c "$I0" "$PY" -B validation/results_baseline.py compare \
    "$ref" "$d/merged" "${ids[@]}" --output "$d/compare.json" > "$d/compare.log" 2>&1)
  log "G1 $d: compare exit $?: $(tail -n 1 "$d/compare.log" | cut -c1-160)"
}
c2prime() {  # G3's C2' (crossrev-base/symport from its planted definitions) by the unplanted tree, one CPU
  local d=$OUT/negative/c2prime
  local -a ids=()
  mkdir -p "$d"
  mapfile -t ids < <(id_map "$UNPLANTED_S")
  (cd "$UNPLANTED_S" && env -u JAX_COMPILATION_CACHE_DIR PYTHONPATH="$UNPLANTED_S/src:$UNPLANTED_S" "${E[@]}" \
    taskset -c "$I0" /usr/bin/time -f '%M %e' -o "$d/rss-c2prime.txt" "$PY" -B validation/results_baseline.py \
    save "$d/part" --sets crossrev-base --worlds symport --from "$C2P_ORIGIN" "${ids[@]}") > "$d/save.log" 2>&1
  (cd "$UNPLANTED_S" && PYTHONPATH="$UNPLANTED_S/src:$UNPLANTED_S" taskset -c "$I0" "$PY" -B \
    validation/results_baseline.py compare "$C2P_REF" "$d/part" "${ids[@]}" --output "$d/compare.json" \
    > "$d/compare.log" 2>&1)
  log "C2' $d: compare exit $?: $(tail -n 1 "$d/compare.log" | cut -c1-160)"
}
fr() {  # TREE DIR: FR's four queues (fr_landing_holder.sh's task lists) on the lane's cores, each
        # process's peak RSS through the interpreter wrapper, then FR's verdict on its frozen dry runs
  local tree=$1 d=$2
  local -a pids=()
  mkdir -p "$d"
  q() { echo "quick|$1|$2|$3/$2/results.json|${4:-}"; }
  queue() {  # N TASK...: queue N on core N (modulo the cores)
    local cpu=${CORES[$(( $1 % ${#CORES[@]} ))]}; shift
    (cd "$tree" && env -u JAX_COMPILATION_CACHE_DIR PYTHONPATH="$tree/src:$tree" "${E[@]}" \
      PY="$OUT/bin/python-rss" RSS_LOG="$d/rss-q$cpu.log" taskset -c "$cpu" \
      bash "$G/fr_landing_queue.sh" "$d" "$FR_START" "$cpu" "$@") >> "$d/queues.log" 2>&1 &
    pids+=($!)
  }
  if [ "$FR_SET" = smoke ]; then
    queue 0 "$(q fr4 control_k3 "$F4")"
  else
    queue 0 "$(q fr4 rung_1ms "$F4")" "$(q fr4 control_k1 "$F4")" "$(q fr5 T_control "$F5" "$F5/start/start.json")"
    queue 1 "$(q fr4 control_k2 "$F4")" "$(q fr4 control_k3 "$F4")" "$(q fr5 R_control "$F5" "$F5/start/start.json")"
    queue 2 "$(q fr5 start "$F5")" "$(q fr5 R_rung_0p5ms "$F5" "$F5/start/start.json")" "windowed|T"
    queue 3 "$(q fr5 T_rung_0p5ms "$F5" "$F5/start/start.json")" "windowed|R"
  fi
  wait "${pids[@]}"
  "$PY" -I "$G/fr_landing_verdict.py" "$tree" "$d" "$FR_BEFORE" "$d/verdict.json" > "$d/verdict.stdout" 2>&1
  log "FR $d: verdict exit $?: $(tr -d '\n' < "$d/verdict.stdout" | cut -c1-200)"
}
light() {  # TREE ARM: FR's set on the lane's cores beside the tier-3 stage's files on their siblings
  local tree=$1 a=$2 p1 p2
  fr "$tree" "$a/fr" & p1=$!
  tiers_run "$tree" "$a/tier3" "$OUT/tier3-tiers.json" 3 "$SIBLINGS" 600 & p2=$!
  wait "$p1" "$p2"
}
crossrev() {  # TREE DIR: crossrev's sets (one CPU per set), each compared with the record, then the
              # lead's replication check on the replication set (its compare-only mode)
  local tree=$1 d=$2 set
  local -a sets
  read -r -a sets <<< "${CROSSREV_SETS:-$(steps crossrev-sets)}"
  env -u JAX_COMPILATION_CACHE_DIR "${E[@]}" "$HOSTPY" -I "$STEPS" crossrev-run "$tree" "$d" --cpus "$CPUS" \
    --sets "${sets[@]}" --python "$PY" > "$d.log" 2>&1
  mkdir -p "$d/vs-record"
  for set in "${sets[@]}"; do
    (cd "$tree" && PYTHONPATH="$tree/src:$tree" taskset -c "$I0" "$PY" -B -m validation.tissue.composite_crossrev \
      compare "$REC/$set" "$d/$set" > "$d/vs-record/compare-$set.txt" 2>&1)
  done
  steps crossrev-verdict "$REC" "$d" "$d/vs-record" "$d/verdict.json" --sets "${sets[@]}" > "$d/verdict.log" 2>&1
  GEN="$d/replication" SNAPDIR="$tree" bash "$REPL_CHECK" - "$(dirname "$d")/replication" "$I0" > /dev/null 2>&1
  log "crossrev $d: $(tail -n 1 "$d/verdict.log" | cut -c1-160); replication done \
$(cat "$(dirname "$d")/replication/done" 2> /dev/null)"
}

# off: the reference, with the cache off.
E=(JAX_ENABLE_COMPILATION_CACHE=false); TCACHE=
mkdir -p "$OUT/off"
if [ -n "$GATE_RUN" ]; then
  freeze "$GATE_RUN" "$OUT/off/record.json" "$OUT/off/collected.json"
  n=$(find "$GATE_RUN/outputs" -path '*/cache/jax/*-cache' 2> /dev/null | wc -l)
  echo "{\"run\": \"$GATE_RUN\", \"cache_entries\": $n}" > "$OUT/off/reuse.json"
else
  stage off tiers "$NONE" tiers_run "$HEAD_S" "$OUT/off/tiers" "$TIERS_JSON" "1 2" "$CPUS" 300
  freeze "$OUT/off/tiers" "$OUT/off/record.json" "$OUT/off/collected.json"
  n=$(find "$OUT/off/tiers/outputs" -path '*/cache/jax/*-cache' 2> /dev/null | wc -l)
  echo "{\"run\": \"$OUT/off/tiers\", \"cache_entries\": $n}" > "$OUT/off/reuse.json"
fi
stage off g1 "$NONE" g1 "$HEAD_S" "$OUT/off/g1" "$C1"
stage off fr+tier3 "$NONE" light "$HEAD_S" "$OUT/off"
freeze "$OUT/off/tier3" "$OUT/off/tier3-record.json" "$OUT/off/tier3-collected.json"
L12=$OUT/off/collected.json L3=$OUT/off/tier3-collected.json

# cold, warm and warm2: cache A.
with_cache "$A"
for arm in cold warm warm2; do
  stage "$arm" tiers "$A" tiers_run "$HEAD_S" "$OUT/$arm/tiers" "$TIERS_JSON" "1 2" "$CPUS" 300
  per_id "$OUT/$arm/tiers" "$OUT/off/record.json" "$L12"
  stage "$arm" g1 "$A" g1 "$HEAD_S" "$OUT/$arm/g1" "$C1"
  stage "$arm" fr+tier3 "$A" light "$HEAD_S" "$OUT/$arm"
  per_id "$OUT/$arm/tier3" "$OUT/off/tier3-record.json" "$L3"
  stage "$arm" crossrev "$A" crossrev "$HEAD_S" "$OUT/$arm/crossrev"
done

# xrev: cache B, written by the base, read by the head.
with_cache "$B"
stage xrev-base tiers "$B" tiers_run "$BASE_S" "$OUT/xrev-base/tiers" "$TIERS_JSON" "1 2" "$CPUS" 300
stage xrev-base g1 "$B" g1 "$BASE_S" "$OUT/xrev-base/g1" "$C1"
stage xrev-head tiers "$B" tiers_run "$HEAD_S" "$OUT/xrev-head/tiers" "$TIERS_JSON" "1 2" "$CPUS" 300
per_id "$OUT/xrev-head/tiers" "$OUT/off/record.json" "$L12"
stage xrev-head g1 "$B" g1 "$HEAD_S" "$OUT/xrev-head/g1" "$C1"

# negative: G3's controls with cache A, each against its own run without the cache.
with_cache "$A"
stage negative unplanted "$A" g1 "$UNPLANTED_S" "$OUT/negative/unplanted" "$UNPLANTED_REF"
stage negative planted "$A" g1 "$PLANTED_S" "$OUT/negative/planted" "$PLANTED_REF"
stage negative c2prime "$A" c2prime

# Caches A and B, program by program (information; the base's tree path written as the head's).
taskset -c "$I0" "$PY" -B "$G/cache_compare.py" "$A" "$B" "$OUT/cache-compare.json" \
  --same "$HEAD_S=$BASE_S" > "$OUT/cache-compare.log" 2>&1
log "caches A and B: exit $?: $(tail -n 1 "$OUT/cache-compare.log" | cut -c1-300)"
default_cache "$OUT/default-cache-after.json"
steps cache-verdict "$OUT" > "$OUT/verdict.log" 2>&1
rc=$?
log "verdict exit $rc: $(tail -n 1 "$OUT/verdict.log" | cut -c1-400)"
echo "$rc" > "$OUT/locked.done"
exit $rc
