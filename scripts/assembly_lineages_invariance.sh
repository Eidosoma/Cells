#!/bin/bash
# The invariance gate of the assembly-lineage families (docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md
# §0.2c rule 16, §0.2e rule 8), for the committed head of TREE (a clean worktree), writing into
# OUT. It runs on the light CPUs at nice 10 (CPUS, default 6,7; the lead's ruling of 19 November
# 2026) and takes no lane lock:
#   1. @1's freeze test (tests/unit/test_assembly_lineages_freeze.py);
#   2. @1's twelve part-1 reference runs against reference-96643762 (0 differences);
#   3. @1's probe driver frozen from TREE, run on G2's registered inputs, and compared with the
#      final set probes-c6dd5956, by the frozen tool and by the checkout's
#      validation/assembly_lineages/compare_probes.py, whose exempted paths must be the frozen
#      tool's;
#   4. G2's ten rows on the regenerated set;
#   5. OL1's probe driver frozen from TREE, run on OL1's registered inputs, and compared with OL1's
#      landing set probes-3e39bcc5 by the checkout's tool (arrays bitwise, JSON leaf by leaf but
#      for provenance, other files byte for byte).
# Steps 1-4 are D188 move 2's invariance_m2.sh, on these CPUs. The frozen evidence stays under
# /mnt/workspaces/Cells; EVIDENCE overrides its root.
# Usage (a run_detached unit's command): scripts/assembly_lineages_invariance.sh TREE OUT
set -u
TREE=${1:?tree}; OUT=${2:?out}
E=${EVIDENCE:-/mnt/workspaces/Cells}
PY=${PY:-$E/venv-cpu/bin/python}
CPUS=${CPUS:-6,7}
CPU1=${CPUS%%,*}
P2=$E/gard-g1-part2-20261117
FROZEN=$E/ol1-laws-20261117/tools/compare_probes.py
TOOL=$TREE/validation/assembly_lineages/compare_probes.py
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
mkdir -p "$OUT"
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/gate.log"; }
fail() { log "$1"; echo 1 > "$OUT/done"; exit 1; }
run() { taskset -c "$1" nice -n 10 "${@:2}"; }
log "tree $TREE at $(git -C "$TREE" rev-parse HEAD); CPUs $CPUS at nice 10"
[ -z "$(git -C "$TREE" status --short)" ] || { log "refused: the tree is not clean"; echo 2 > "$OUT/done"; exit 2; }

(cd "$TREE" && PYTHONPATH="$TREE/src:$TREE" run "$CPUS" "$PY" -B -m pytest -q -p no:cacheprovider \
  tests/unit/test_assembly_lineages_freeze.py > "$OUT/1-freeze.log" 2>&1)
rc=$?; log "1 freeze test exit $rc: $(tail -n 1 "$OUT/1-freeze.log")"
[ $rc -eq 0 ] || fail "1 failed"

(cd "$TREE" && PYTHONPATH="$TREE/src:$TREE" run "$CPU1" "$PY" -B \
  "$E/d188-m2-move-20261118/tools/reference_runs_m2.py" compare "$P2/reference-96643762" \
  "$OUT/2-reference-compare.json" > "$OUT/2-references.log" 2>&1)
rc=$?; log "2 part-1 references exit $rc: $(tail -n 1 "$OUT/2-references.log")"
[ $rc -eq 0 ] || fail "2 failed"

(cd "$TREE" && PYTHONPATH="$TREE" "$PY" -B -m validation.assembly_lineages.probes freeze "$OUT/3-probes" \
  > "$OUT/3-probes-freeze.log" 2>&1) || fail "3 freeze failed"
(cd "$OUT/3-probes/source" && PYTHONPATH="$OUT/3-probes/source/src:$OUT/3-probes/source" run "$CPUS" \
  "$PY" -B -m validation.assembly_lineages.probes run "$P2/probes-in-94e3ca4b" "$OUT/3-probes/probes" \
  > "$OUT/3-probes-run.log" 2>&1)
rc=$?; log "3 @1's probe driver exit $rc"
[ $rc -eq 0 ] || fail "3 failed"
"$PY" -I "$FROZEN" "$P2/probes-c6dd5956/probes" "$OUT/3-probes/probes" "$OUT/3-compare-frozen.json" \
  > "$OUT/3-compare-frozen.log" 2>&1
rc=$?; log "3 @1's set, the frozen tool, exit $rc: $(tail -n 1 "$OUT/3-compare-frozen.log")"
[ $rc -eq 0 ] || fail "3 failed"
"$PY" -I "$TOOL" "$P2/probes-c6dd5956/probes" "$OUT/3-probes/probes" "$OUT/3-compare-checkout.json" \
  > "$OUT/3-compare-checkout.log" 2>&1
rc=$?
"$PY" -I -c "import json,sys; a=json.load(open(sys.argv[1])); b=json.load(open(sys.argv[2])); sys.exit(0 if a['exempted_paths']==b['exempted_paths'] else 1)" \
  "$OUT/3-compare-frozen.json" "$OUT/3-compare-checkout.json"
same=$?
log "3 @1's set, the checkout's tool, exit $rc, exemptions as the frozen tool's: $([ $same -eq 0 ] && echo yes || echo NO): $(tail -n 1 "$OUT/3-compare-checkout.log")"
[ $rc -eq 0 ] && [ $same -eq 0 ] || fail "3 failed"

"$PY" -I -c "import json,sys; d=json.load(open(sys.argv[1])); json.dump(d['roles'], open(sys.argv[2],'w'), indent=1, sort_keys=True)" \
  "$OUT/3-probes/probes/roles.json" "$OUT/4-roles.json"
(cd "$TREE" && PYTHONPATH="$TREE/src:$TREE" run "$CPU1" "$PY" -B -m validation.gard.references.harness run \
  --roles "$OUT/4-roles.json" --out "$OUT/4-g2-report.json" > "$OUT/4-g2.log" 2>&1)
rc=$?; log "4 G2's ten rows exit $rc: $(grep -c ' PASS ' "$OUT/4-g2.log") PASS"
[ $rc -eq 0 ] || fail "4 failed"

mkdir -p "$OUT/ol1"
(cd "$TREE" && PYTHONPATH="$TREE" "$PY" -B -m validation.assembly_lineages_v2.probes freeze "$OUT/ol1" \
  > "$OUT/ol1/freeze.log" 2>&1) || fail "5 OL1 freeze failed"
(cd "$OUT/ol1/source" && PYTHONPATH="$OUT/ol1/source/src:$OUT/ol1/source" run "$CPUS" "$PY" -B \
  -m validation.assembly_lineages_v2.probes run "$E/ol1-laws-20261117/inputs-ab3dd700" \
  "$OUT/ol1/probes" > "$OUT/ol1/run.log" 2>&1)
rc=$?; log "5 OL1's probe driver exit $rc"
[ $rc -eq 0 ] || fail "5 failed"
"$PY" -I "$TOOL" "$E/ol1-laws-20261117/probes-3e39bcc5/probes" "$OUT/ol1/probes" \
  "$OUT/ol1/compare-vs-3e39bcc5.json" > "$OUT/ol1/compare.log" 2>&1
rc=$?; log "5 OL1 compare with probes-3e39bcc5 exit $rc: $(tail -n 1 "$OUT/ol1/compare.log")"
echo $rc > "$OUT/done"
log "done $rc"
exit $rc
