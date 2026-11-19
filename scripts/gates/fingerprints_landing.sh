#!/bin/bash
# R1's definition fingerprints for a landing after a move (scripts/gates/fingerprints.py; both
# trees in the moved layout): main's snapshot against the branch's head, every definition both
# hold. With a pre-move record (the move's gate's base record), the head is also compared with it,
# through the map. Each snapshot is identity-checked against its own recorded revision in the
# repository.
# Supersedes /mnt/workspaces/Cells/d188-m2-move-20261118/tools/fingerprints-landing.sh, kept byte
# for byte since recorded runs cite it. Unchanged but for these:
# - the repository is this script's (REPO overrides it), not a fixed path;
# - the map defaults to the head's scripts/moves/move2.json (MAP overrides it).
# Usage: fingerprints_landing.sh OUT HEAD_SNAPSHOT BASE_SNAPSHOT [PREMOVE_BASE_RECORD_DIR]
set -uo pipefail
O=${1:?out}; H=${2:?head snapshot}; B=${3:?base snapshot}; P=${4:-}
G=$(cd "$(dirname "$0")" && pwd)
REPO=${REPO:-$(git -C "$G" rev-parse --path-format=absolute --git-common-dir)}
REPO=${REPO%/.git}
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
T=$G/fingerprints.py
MAP=${MAP:-$H/scripts/moves/move2.json}
G1=${G1:-/mnt/workspaces/Cells/d172-restructure-20261115-01/endgame/c1-3c10b833/g1/merged}
export JAX_PLATFORMS=cpu CUDA_VISIBLE_DEVICES= PYTHONDONTWRITEBYTECODE=1 JAX_ENABLE_X64=1
mkdir -p "$O"
log() { echo "$(date -u +%FT%TZ) $*" >> "$O/run.log"; }
rev() { python3 -c "import json,sys; print(json.load(open(sys.argv[1]))['git_revision'][:8])" "$1/SNAPSHOT.json"; }
log "affinity $(taskset -pc $$ | sed 's/.*: //'); base $B ($(rev "$B")), head $H ($(rev "$H")); map $MAP"
status=0
for side in base head; do
  if [ $side = base ]; then tree=$B; else tree=$H; fi
  "$PY" -B -I "$T" identity "$tree" "$(rev "$tree")" "$REPO" > "$O/identity-$side.json" 2>> "$O/run.log" || status=1
  log "identity $side: $(cat "$O/identity-$side.json")"
  "$PY" -B -I "$T" record "$tree" "$O/$side" --layout moved --map "$MAP" \
    --defs "$tree/configs" "$tree/examples" "$tree/validation" --g1 "$G1" \
    > "$O/record-$side.log" 2>&1 || { status=1; log "record $side failed (record-$side.log)"; }
  log "record $side: $(tail -1 "$O/record-$side.log")"
done
"$PY" -B -I "$T" compare "$O/base" "$O/head" "$MAP" "$O/compare.json" > "$O/compare.log" 2>&1 || status=1
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
