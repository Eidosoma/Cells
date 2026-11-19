#!/bin/bash
# One queue of FR's bitwise landing set, run as its own unit by fr_landing_holder.sh (a script file,
# so systemd expands nothing in it). Each TASK is "quick|WHICH|PART|EARLIER_RESULTS|START_JSON_OR_EMPTY"
# or "windowed|ARM", run in turn from the unit's directory (the frozen snapshot):
# - quick: compartment_ph_qualification's dev entry on PART at the quick horizon (vector path,
#   declared world), then compartment_ph_judge compare against the earlier dry run's record;
# - windowed: FR-5's arm ARM over 10 s with the injury window at 2-6 s from START
#   (compartment_ph_engine.world_agreement).
# Supersedes /mnt/workspaces/Cells/d172-restructure-20261115-01/fr45/rehearsal-20261117/landing-queue.sh
# (kept byte for byte, since recorded runs cite it); only the interpreter's path may be overridden
# (PY).
#
# Usage: fr_landing_queue.sh OUT START Q TASK [TASK ...]
set -u
O=$1 START=$2 Q=$3
shift 3
PY=${PY:-/mnt/workspaces/Cells/venv-cpu/bin/python}
for task in "$@"; do
  IFS='|' read -r kind a b c d <<< "$task"
  t0=$(date +%s)
  if [ "$kind" = quick ]; then
    extra=()
    [ -n "$d" ] && extra=(--start "$d")
    "$PY" -B -m validation.tissue.compartment_ph_qualification dev "$a" "$O/$b" "$b" \
      "${extra[@]}" --quick --path vector --world declared > "$O/$b.log" 2>&1
    code=$?
    "$PY" -B -m validation.tissue.compartment_ph_judge compare "$c" "$O/$b/results.json" \
      "$O/compare-$b.json" >> "$O/$b.log" 2>&1
    echo "$(date -u +%FT%TZ) q$Q $a $b: exit $code, compare exit $?, $(( $(date +%s) - t0 )) s" >> "$O/run.log"
  elif [ "$kind" = windowed ]; then
    "$PY" -B -m validation.compartment_ph_engine.world_agreement "$START" "$a" "$O/windowed-$a.json" \
      --horizon 10 --window 2 6 --path vector --world declared > "$O/windowed-$a.log" 2>&1
    echo "$(date -u +%FT%TZ) q$Q windowed $a: exit $?, $(( $(date +%s) - t0 )) s" >> "$O/run.log"
  else
    echo "$(date -u +%FT%TZ) q$Q unknown task [$task]" >> "$O/run.log"
  fi
done
date -u +%FT%TZ > "$O/q$Q.done"
