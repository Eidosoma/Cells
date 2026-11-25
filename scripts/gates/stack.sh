#!/bin/bash
# Stacked gates (the testing plan of 19 November 2026, item C, §10.4; D229 rule 2): two or three
# queued heads merged in order onto main and gated once, as the tree that lands.
#
#   1. The declaration (JSON, below) is checked: 1 to 3 heads, and a head that declares crossrev
#      differences rides alone (gate_steps.py stack-plan). A head's own pre-lock pass (gate.sh with
#      PRELOCK_ONLY=1) is checked when the head names it ("prelock"; its revision must be the
#      head's) and recorded per head; without it, the top's own pre-lock steps stand for the heads'.
#   2. The trial merges, main + H1, then + H2, then + H3, are made in a detached worktree as the
#      lead lands them: the previous trial's tier record, the head's measured rows folded with the
#      trial's own scripts/test_tiers.py, and the head's message with the line "Stack gate: OUT".
#      A conflict refuses the stack and lists its paths; a head may instead name its own merge
#      commit, a resolution made by hand (stack-build). The top is kept as refs/stacks/TOP.
#   3. The top and main are frozen (freeze_snapshot.py, scope full), and gate.sh gates the top
#      against main once, with the union of the heads' declarations.
#   4. On a refusal, only the failing check runs again: the failing test files, crossrev sets or G1
#      worlds, or the IDs check or preflight, on the intermediate trees nearest first (M_{n-1} down
#      to M_1, then main). The first tree where an item passes blames the head above it. A check
#      that ran under the lock reruns under the same lane's lock; a pre-lock check on the pre-lock
#      CPU. An item failing on main too, or a rerun that timed out, blames nobody.
#   5. With RESTACK=1 (the default) the stack is re-gated without its blamed heads, into
#      OUT/restack (this script again).
# OUT/stack.json names the heads, the trial merges, the gate's OUT and its verdict, the bisect and
# the restack. Each trial's message already names the stack's gate; the line is also printed, for
# the lead's own merges, which assert_landing_tree.py checks against each trial.
#
# The declaration: {"main": REV, "heads": [{"name": ..., "rev": ..., "additions_from": [FILE...],
#   "removed_ok": [ID...], "removed_ok_file": FILE, "measured": [MEASURED_JSON...],
#   "message": "the merge message", "resolve": {PATH: REV or FILE}, "merge": REV (a merge made by
#   hand), "prelock": OUT (the head's own PRELOCK_ONLY=1 gate)}, ...]}, all but name and rev optional.
# Environment: gate.sh's (LANE, GATE_LOCK, GATE_CPUS, PRELOCK_CPU, PRELOCK_NICE, TIERS, GATE_CACHE,
#   C1, BASELINE, REC, CROSSREV_SETS, PY, HOSTPY ...), and REPO (the checkout; default $HOME/Cells),
#   BASE_S (main's snapshot, else frozen here), FREEZE (a command freezing CHECKOUT into DEST; tests
#   only), RESTACK.
# Run it from a frozen copy of the tools (for example main's snapshot), so it never changes under a
# queued stack. Usage (a run_detached unit's command): stack.sh DECLARATION OUT
#   OUT/done holds 0 (passed), 1 (refused) or 2 (not run: a bad declaration, a conflict, or the lock
#   never held).
set -u
if [ "${1:-}" = --bisect-locked ]; then BISECT_LOCKED=1; shift; else BISECT_LOCKED=0; fi
DECL=${1:?stack declaration}; OUT=${2:?out}
G=$(cd "$(dirname "$0")" && pwd)
STEPS=$G/gate_steps.py
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
HOSTPY=${HOSTPY:-python3}
REPO=${REPO:-$HOME/Cells}
RESTACK=${RESTACK:-1}
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
# Cold, as gate.sh (D321 R2): the stack's gate and its bisect's reruns never use a compilation cache.
export JAX_ENABLE_COMPILATION_CACHE=false
unset JAX_COMPILATION_CACHE_DIR CELLS_JAX_CACHE
steps() { "$HOSTPY" -I "$STEPS" "$@"; }
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/stack.log"; }
short() { tr -d '\n' < "$1" | cut -c1-400; }
# A tree's own table of renamed IDs (D345), where it has one: what was saved under an old spelling is
# read through it (validation/id_table.py), so a tree before the rename is asked for nothing.
id_map() { local t=$1/src/cells/registry/renamed_ids.py; [ ! -f "$t" ] || printf '%s\n' --map "$t"; }
field() { "$HOSTPY" -I -c "import json,sys; d=json.load(open(sys.argv[1])); v=d.get(sys.argv[2]); \
print('\n'.join(map(str, v)) if isinstance(v, list) else ('' if v is None else v))" "$1" "$2"; }
to_nice() { local now; now=$(nice); if [ "$1" -gt "$now" ]; then echo $(( $1 - now )); else echo 0; fi; }

freeze() {  # CHECKOUT DEST: a full, clean snapshot.
  if [ -n "${FREEZE:-}" ]; then read -r -a cmd <<< "$FREEZE"; "${cmd[@]}" "$1" "$2"
  else "$PY" -B "$G/freeze_snapshot.py" "$1" "$2" --scope full --require-clean; fi
}

collect() {  # TREE PREFIX: as gate.sh's collect, every test ID under tests/.
  local tree=$1 prefix=$2 rc
  mkdir -p "$prefix-scratch"
  (cd "$tree" && PYTHONPATH="$tree/src" CELLS_OUTPUT_ROOT="$prefix-scratch/outputs" \
    CELLS_COMPONENT_EVIDENCE="$prefix-scratch/evidence" $RUN "$PY" -B -m pytest -q \
    -p no:cacheprovider --continue-on-collection-errors --collect-only tests) > "$prefix.log" 2>&1
  rc=$?
  grep "::" "$prefix.log" | sort > "$prefix.ids"
  echo "{\"exit\": $rc, \"ids\": $(wc -l < "$prefix.ids")}" > "$prefix.json"
}

from_log() {  # WORDS: the path the gate's log gives after "WORDS, " (a cache entry it used).
  grep -o "$1, [^ ]*" "$OUT/gate/gate.log" | tail -n 1 | sed "s/^$1, //"
}

rerun() {  # STAGE K SNAP DIR ITEM...: the failing check alone on one tree.
  local stage=$1 k=$2 snap=$3 dir=$4 adds= removed= base_ids base_x set j ids
  shift 4
  mkdir -p "$dir"
  if [ "$k" -gt 0 ]; then adds=$(cat "$OUT/decl-$k/additions.txt"); removed=$OUT/decl-$k/removed-ok.txt; fi
  case $stage in
    preflight)
      ADDITIONS_FROM=$adds REMOVED_OK_FILE=$removed steps preflight "$snap" "$BASE_S" "$dir/preflight.json" \
        > "$dir/check.log" 2>&1
      echo $? > "$dir/rc" ;;
    ids)
      base_ids=$OUT/gate/prelock/ids/collect-base
      [ -f "$base_ids.ids" ] || base_ids=$(from_log "prelock ids: base listing from the cache")/collect-base
      collect "$snap" "$dir/collect-head"
      ADDITIONS_FROM=$adds REMOVED_OK_FILE=$removed steps ids "$base_ids" "$dir/collect-head" "$dir/ids.json" \
        > "$dir/check.log" 2>&1
      echo $? > "$dir/rc" ;;
    prelock-tests|tiers)
      steps stack-subset "$snap" "$TIERS" "$dir/subset.json" "$@" > "$dir/subset.log" 2>&1
      (cd "$snap" && PYTHONPATH="$snap/src:$snap" $RUN "$PY" -B scripts/test_tiers.py run --tiers \
        "$dir/subset.json" --tier 1 2 9 --out "$dir/run" --cpus "$RCPUS" --cap 300 > "$dir/run.log" 2>&1) ;;
    crossrev)
      base_x=$OUT/gate/crossrev/base
      [ -d "$base_x" ] || base_x=$(from_log "crossrev base from the cache")/sides
      steps crossrev-run "$snap" "$dir/head" --cpus "$RCPUS" --sets "$@" --python "$PY" > "$dir/head.log" 2>&1
      mkdir -p "$dir/compare"
      for set in "$@"; do
        (cd "$snap" && PYTHONPATH="$snap/src:$snap" $RUN "$PY" -B -m validation.tissue.composite_crossrev \
          compare "$base_x/$set" "$dir/head/$set" > "$dir/compare/compare-$set.txt" 2>&1)
      done
      steps crossrev-verdict "$base_x" "$dir/head" "$dir/compare" "$dir/verdict.json" --sets "$@" \
        > "$dir/verdict.log" 2>&1 ;;
    g1)
      j=0; mapfile -t ids < <(id_map "$snap")
      while IFS=$'\t' read -r set worlds; do
        # shellcheck disable=SC2086
        (cd "$snap" && PYTHONPATH="$snap/src:$snap" $RUN "$PY" -B validation/results_baseline.py save \
          "$dir/parts/part-$j" --sets "$set" --worlds $worlds --from "$BASELINE" "${ids[@]}") \
          < /dev/null >> "$dir/save.log" 2>&1
        j=$((j + 1))
      done < <("$HOSTPY" -I -c "import sys, collections
groups = collections.defaultdict(list)
for w in sys.argv[1:]:
    groups[w.split('/', 1)[0]].append(w.split('/', 1)[1])
for s, names in groups.items():
    print(s + '\t' + ' '.join(names))" "$@")
      steps g1-merge "$dir/parts" "$dir/merged" >> "$dir/save.log" 2>&1
      steps g1-view "$C1" "$dir/c1" "$@" >> "$dir/save.log" 2>&1
      (cd "$snap" && PYTHONPATH="$snap/src:$snap" $RUN "$PY" -B validation/results_baseline.py compare \
        "$dir/c1" "$dir/merged" "${ids[@]}" --output "$dir/compare.json" > "$dir/compare.log" 2>&1) ;;
  esac
}

bisect() {  # The failing check on M_{n-1} .. M_1, then main, nearest first, until every item is placed.
  local stage n k snap left items
  stage=$(field "$OUT/failure.json" stage); n=$(field "$OUT/plan.json" n)
  mapfile -t items < <(field "$OUT/failure.json" items)
  mkdir -p "$OUT/bisect"
  for (( k = n - 1; k >= 0; k-- )); do
    mapfile -t left < <(steps stack-remaining "$OUT/bisect" "$n" "${items[@]}")
    [ ${#left[@]} -gt 0 ] || break
    snap=$OUT/snap-m$k; [ "$k" -gt 0 ] || snap=$BASE_S
    log "bisect: $stage on M$k ($snap), only ${left[*]}"
    rerun "$stage" "$k" "$snap" "$OUT/bisect/m$k" "${left[@]}"
    log "bisect: M$k $(steps stack-results "$stage" "$OUT/bisect/m$k" "${left[@]}")"
  done
}

if [ $BISECT_LOCKED -eq 1 ]; then  # Under the lane's lock: the rerun of a check that ran under it.
  set -a; source "$OUT/gate/config.env"; set +a  # shellcheck disable=SC1091
  BASE_S=$(cat "$OUT/base-snapshot")
  RUN=; RCPUS=$CPUS
  taskset -cp "$CPUS" $$ > /dev/null || { log "could not pin to the lane's CPUs $CPUS"; exit 2; }
  log "bisect: lane $LANE, lock held; affinity $(taskset -pc $$ | sed 's/.*: //')"
  bisect
  echo 0 > "$OUT/bisect.done"
  exit 0
fi

finish() {
  local line
  [ ! -d "$OUT/tree" ] || git -C "$REPO" worktree remove --force "$OUT/tree" >> "$OUT/stack.log" 2>&1
  line=$(steps stack-record "$OUT" 2>> "$OUT/stack.log")
  log "record: $line"
  echo "$line" > "$OUT/merge-line.txt"
  echo "$line"
  log "done status $1"; echo "$1" > "$OUT/done"; exit "$1"
}

[ ! -e "$OUT/done" ] || { echo "Refused: $OUT was used before (it holds done)" >&2; exit 2; }
mkdir -p "$OUT"
PRE_CPU=${PRELOCK_CPU:-23}
# Until a lock is held, this script and all it starts stay on the pre-lock CPU (as gate.sh).
taskset -cp "$PRE_CPU" $$ > /dev/null || { log "could not pin to CPU $PRE_CPU"; echo 2 > "$OUT/done"; exit 2; }
log "stack $DECL into $OUT; repo $REPO; tool $G; restack $RESTACK"
log "JAX's persistent compilation cache disabled in every process (JAX_ENABLE_COMPILATION_CACHE=false, \
no cache folder; D321 R2)"
steps stack-plan "$DECL" "$OUT" > "$OUT/plan.log" 2>&1 || { log "declaration refused: $(short "$OUT/plan.log")"; finish 2; }
steps stack-build "$OUT" --repo "$REPO" --python "$PY" > "$OUT/build.log" 2>&1
rc=$?; log "trial merges exit $rc: $(short "$OUT/build.log")"
[ $rc -eq 0 ] || finish 2
N=$(field "$OUT/plan.json" n); TOP=$(field "$OUT/trials.json" top); MAIN=$(field "$OUT/trials.json" main)
git -C "$REPO" update-ref "refs/stacks/${TOP:0:12}" "$TOP" 0000000000000000000000000000000000000000 \
  && echo "refs/stacks/${TOP:0:12}" > "$OUT/ref"
freeze "$OUT/tree" "$OUT/snap-m$N" > "$OUT/freeze.log" 2>&1 || { log "freezing the top failed"; finish 2; }
if [ -n "${BASE_S:-}" ]; then
  [ "$("$HOSTPY" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['git_revision'])" \
    "$BASE_S/SNAPSHOT.json")" = "$MAIN" ] || { log "BASE_S $BASE_S is not main $MAIN"; finish 2; }
else
  BASE_S=$OUT/snap-main
  git -C "$OUT/tree" checkout --quiet --detach "$MAIN" && freeze "$OUT/tree" "$BASE_S" >> "$OUT/freeze.log" 2>&1 \
    || { log "freezing main failed"; finish 2; }
fi
echo "$BASE_S" > "$OUT/base-snapshot"
log "gate of the top ${TOP:0:12} ($OUT/snap-m$N) against main ${MAIN:0:12} ($BASE_S), $N heads"
env -u CROSSREV_EXPECTED ADDITIONS_FROM="$(cat "$OUT/decl-$N/additions.txt")" \
  REMOVED_OK_FILE="$OUT/decl-$N/removed-ok.txt" bash "$G/gate.sh" "$OUT/snap-m$N" "$BASE_S" "$OUT/gate" \
  > "$OUT/gate.out" 2>&1
GD=$(cat "$OUT/gate/done" 2>/dev/null)
log "gate done ${GD:-none}: $(grep -E 'stopped at|done status' "$OUT/gate/gate.log" 2>/dev/null | tail -n 2 | tr '\n' ' ')"
[ "$GD" = 0 ] && finish 0
[ "$GD" = 1 ] || finish 2

# A refusal: the failing check alone, on the intermediate trees.
steps stack-failure "$OUT/gate" "$OUT/failure.json" > "$OUT/failure.log" 2>&1 \
  || { log "the gate stopped outside a check ($(short "$OUT/failure.log")): not bisected"; finish 1; }
log "failure: $(short "$OUT/failure.log")"
for (( k = N - 1; k >= 1; k-- )); do
  C=$("$HOSTPY" -I -c "import json,sys; print(json.load(open(sys.argv[1]))['trials'][int(sys.argv[2]) - 1]['commit'])" \
    "$OUT/trials.json" "$k")
  git -C "$OUT/tree" checkout --quiet --detach "$C" && freeze "$OUT/tree" "$OUT/snap-m$k" >> "$OUT/freeze.log" 2>&1 \
    || { log "freezing M$k failed"; finish 1; }
done
set -a; source "$OUT/gate/config.env"; set +a  # shellcheck disable=SC1091
if [ "$(field "$OUT/failure.json" under_lock)" = True ]; then
  log "bisect waits for $LOCK"
  /usr/bin/flock "$LOCK" bash "$0" --bisect-locked "$DECL" "$OUT"
  [ -f "$OUT/bisect.done" ] || { log "the lock was never held: no bisect"; finish 1; }
else
  RUN="taskset -c $PRELOCK_CPU nice -n $(to_nice "$PRELOCK_NICE")"; RCPUS=$PRELOCK_CPU
  bisect
fi
if why=$(steps jax-entries "$OUT/bisect" 2>&1); then log "cold check after the bisect: $why"
else log "stopped: JAX compilation cache entries appeared in the bisect's reruns (the cold check): $why"
  finish 1; fi
steps stack-blame "$OUT/bisect" "$N" "$OUT/blame.json" > "$OUT/blame.log" 2>&1
log "blame: $(short "$OUT/blame.log")"
if [ "$RESTACK" = 1 ]; then
  if why=$(steps stack-restack "$OUT" 2>&1); then
    log "$why"
    BASE_S=$BASE_S bash "$0" "$OUT/restack.json" "$OUT/restack" > "$OUT/restack.out" 2>&1
    log "restack done $(cat "$OUT/restack/done" 2>/dev/null): $(cat "$OUT/restack/merge-line.txt" 2>/dev/null)"
  else
    log "$why"
  fi
fi
finish 1
