#!/bin/bash
# The invariance gate of the assembly-lineage families (OL2's; docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md
# §0.2c rule 16), for the committed head of TREE (a clean worktree), writing into OUT:
#   1. @1's gate (D188 move 2's invariance_m2.sh): the freeze test, the part-1 references, @1's
#      probe set against probes-c6dd5956, and G2's ten rows;
#   2. OL1's probe driver frozen from TREE, run on OL1's registered inputs, and compared with OL1's
#      landing set probes-3e39bcc5 by the checkout's validation/assembly_lineages/compare_probes.py
#      (arrays bitwise, JSON leaf by leaf but for provenance, other files byte for byte).
# The frozen evidence stays under /mnt/workspaces/Cells; EVIDENCE overrides its root.
# Usage (a run_detached unit's command): scripts/assembly_lineages_invariance.sh TREE OUT
set -u
TREE=${1:?tree}; OUT=${2:?out}
E=${EVIDENCE:-/mnt/workspaces/Cells}
PY=${PY:-$E/venv-cpu/bin/python}
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
mkdir -p "$OUT"
log() { echo "$(date -u +%FT%TZ) $*" >> "$OUT/gate.log"; }
log "tree $TREE at $(git -C "$TREE" rev-parse HEAD)"
[ -z "$(git -C "$TREE" status --short)" ] || { log "refused: the tree is not clean"; echo 2 > "$OUT/done"; exit 2; }
bash "$E/d188-m2-move-20261118/tools/invariance_m2.sh" "$TREE" "$OUT/at1"
rc=$?; log "1 @1's gate exit $rc: $(tail -n 1 "$OUT/at1/invariance.log")"
[ $rc -eq 0 ] || { echo 1 > "$OUT/done"; exit 1; }
mkdir -p "$OUT/ol1"
(cd "$TREE" && PYTHONPATH="$TREE" "$PY" -B -m validation.assembly_lineages_v2.probes freeze "$OUT/ol1" \
  > "$OUT/ol1/freeze.log" 2>&1) || { log "2 OL1 freeze failed"; echo 1 > "$OUT/done"; exit 1; }
(cd "$OUT/ol1/source" && PYTHONPATH="$OUT/ol1/source/src:$OUT/ol1/source" taskset -c 6,7 nice -n 10 \
  "$PY" -B -m validation.assembly_lineages_v2.probes run "$E/ol1-laws-20261117/inputs-ab3dd700" \
  "$OUT/ol1/probes" > "$OUT/ol1/run.log" 2>&1)
rc=$?; log "2 OL1's probe driver exit $rc"
[ $rc -eq 0 ] || { echo 1 > "$OUT/done"; exit 1; }
"$PY" -I "$TREE/validation/assembly_lineages/compare_probes.py" "$E/ol1-laws-20261117/probes-3e39bcc5/probes" \
  "$OUT/ol1/probes" "$OUT/ol1/compare-vs-3e39bcc5.json" > "$OUT/ol1/compare.log" 2>&1
rc=$?; log "2 OL1 compare with probes-3e39bcc5 exit $rc: $(tail -n 1 "$OUT/ol1/compare.log")"
echo $rc > "$OUT/done"
log "done $rc"
exit $rc
