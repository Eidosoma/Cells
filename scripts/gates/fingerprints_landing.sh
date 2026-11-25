#!/bin/bash
# R1's definition fingerprints for a landing after a move (scripts/gates/fingerprints.py; both
# trees in the moved layout): main's snapshot against the branch's head, every definition both
# hold. With a pre-move record (the move's gate's base record), the head is also compared with it,
# through the map. Each snapshot is identity-checked against its own recorded revision in the
# repository.
# Supersedes /mnt/workspaces/Cells/d188-m2-move-20261118/tools/fingerprints-landing.sh, kept byte
# for byte since recorded runs cite it. Unchanged but for these:
# - the repository is this script's (REPO overrides it), not a fixed path;
# - the map defaults to the head's scripts/moves/move2.json (MAP overrides it);
# - the base's identity and record are cached per main revision (the testing plan's item B, 19
#   November 2026), in GATE_CACHE (default /mnt/workspaces/Cells/gate-cache; empty turns it off)
#   through gate_steps.py. The key holds the base's revision, the map's and this fingerprints.py's
#   digests (computed here at run time), the G1 save and the interpreter's identity. A base whose
#   identity or record failed is never published.
# Across the ID rename (D345): each tree reads the definitions through its own table of renamed IDs,
# where it has one; and where the head's table holds IDs that the base's does not, both sides'
# results are read through the head's (fingerprints.py record, --inputs and --outputs), and that
# table is in the cache's key. Two trees with one table compare the engine's own fingerprints, as
# before. DECLARED names a file of the worlds whose difference is declared before the run, an exact
# list.
# Usage: fingerprints_landing.sh OUT HEAD_SNAPSHOT BASE_SNAPSHOT [PREMOVE_BASE_RECORD_DIR]
set -uo pipefail
O=${1:?out}; H=${2:?head snapshot}; B=${3:?base snapshot}; P=${4:-}
G=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(git -C "$G" rev-parse --path-format=absolute --git-common-dir)}
REPO=${REPO%/.git}
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
T=$G/fingerprints.py
MAP=${MAP:-$H/scripts/moves/move2.json}
G1=${G1:-/mnt/workspaces/Cells/global-charge-bound-20261122/c1-605331c2/merged}  # C1 renewed for D305's fix (D307), as gate.sh's.
GATE_CACHE=${GATE_CACHE-/mnt/workspaces/Cells/gate-cache}
TABLE=src/cells/registry/renamed_ids.py
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
mkdir -p "$O"
OUTPUTS=
if grep -qs '@' "$H/$TABLE" && ! cmp -s "$B/$TABLE" "$H/$TABLE"; then OUTPUTS=$H/$TABLE; fi
through() {  # TREE: its record's options for the renamed IDs.
  [ ! -f "$1/$TABLE" ] || printf '%s\n' --inputs "$1/$TABLE"
  [ -z "$OUTPUTS" ] || printf '%s\n' --outputs "$OUTPUTS"
}
log() { echo "$(date -u +%FT%TZ) $*" >> "$O/run.log"; }
rev() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['git_revision'][:8])" "$1/SNAPSHOT.json"; }
log "affinity $(taskset -pc $$ | sed 's/.*: //'); base $B ($(rev "$B")), head $H ($(rev "$H")); map $MAP; \
results read through ${OUTPUTS:-no table of renamed IDs}"
status=0
items=()
cached=
if [ -n "$GATE_CACHE" ] && [ -f "$MAP" ]; then
  items=("map=$(sha256sum "$MAP" | cut -c1-64)" "tool=$(sha256sum "$T" | cut -c1-64)" "g1=$G1" "layout=moved")
  [ -z "$OUTPUTS" ] || items+=("renamed=$(sha256sum "$OUTPUTS" | cut -c1-64)")
  cached=$(python3 -I "$G/gate_steps.py" cache-find "$GATE_CACHE" r1 "$B" "${items[@]}" --python "$PY" 2> /dev/null)
fi
for side in base head; do
  if [ $side = base ]; then tree=$B; else tree=$H; fi
  if [ $side = base ] && [ -n "$cached" ]; then
    cp -r "$cached/base" "$O/base" && cp "$cached/identity-base.json" "$cached/record-base.log" "$O/" \
      || { status=1; log "the cached base $cached could not be copied"; }
    log "identity base, from the cache $cached: $(cat "$O/identity-base.json")"
    log "record base, from the cache: $(tail -1 "$O/record-base.log")"
    continue
  fi
  side_status=0
  "$PY" -B -I "$T" identity "$tree" "$(rev "$tree")" "$REPO" > "$O/identity-$side.json" 2>> "$O/run.log" || side_status=1
  log "identity $side: $(cat "$O/identity-$side.json")"
  mapfile -t ids < <(through "$tree")
  "$PY" -B -I "$T" record "$tree" "$O/$side" --layout moved --map "$MAP" \
    --defs "$tree/configs" "$tree/examples" "$tree/validation" --g1 "$G1" "${ids[@]}" \
    > "$O/record-$side.log" 2>&1 || { side_status=1; log "record $side failed (record-$side.log)"; }
  log "record $side: $(tail -1 "$O/record-$side.log")"
  [ $side_status -eq 0 ] || status=1
  if [ $side = base ] && [ $side_status -eq 0 ] && [ ${#items[@]} -gt 0 ]; then
    mkdir -p "$O/base-publish" && cp -r "$O/base" "$O/base-publish/base" \
      && cp "$O/identity-base.json" "$O/record-base.log" "$O/base-publish/" \
      && log "base published: $(python3 -I "$G/gate_steps.py" cache-publish "$GATE_CACHE" r1 "$B" \
        "$O/base-publish" "${items[@]}" --python "$PY" 2>&1 | tail -n 1)"
    rm -rf "$O/base-publish"
  fi
done
"$PY" -B -I "$T" compare "$O/base" "$O/head" "$MAP" "$O/compare.json" ${DECLARED:+--declared "$DECLARED"} \
  > "$O/compare.log" 2>&1 || status=1
log "compare base / head: $(python3 -c "import json; print(json.load(open('$O/compare.json'))['verdict'])" 2>&1)"
if [ -n "$P" ]; then
  "$PY" -B -I "$T" compare "$P" "$O/head" "$MAP" "$O/compare-vs-premove.json" > "$O/compare-vs-premove.log" 2>&1
  log "compare premove record $P / head exit $?: $(python3 -c "
import json; d = json.load(open('$O/compare-vs-premove.json'))
print(d['verdict'], '| same keys', d['same_keys'], '| R1 keys missing', len(d['r1_keys']['r1_not_here']), '| fingerprints differ', d['fingerprints']['differ'])" 2>&1)"
fi
log "status $status"
echo $status > "$O/done"
exit $status
