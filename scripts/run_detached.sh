#!/bin/bash
# Run one long job as its own systemd user unit in cells.slice, with its own memory cap.
#
# Why (12 November 2026): a machine-wide out-of-memory kill of one job made systemd stop
# the whole terminal-session scope that contained it, and with it every detached job and
# agent in that scope (setsid and nohup do not leave the cgroup). A job started here lives
# in its own unit, outside the session: an out-of-memory kill stops that job only.
#
# Usage: scripts/run_detached.sh NAME MEMORY_MAX [options] -- COMMAND [ARGS...]
#   NAME        the unit is cells-NAME (letters, digits, '-', '_', '.')
#   MEMORY_MAX  this unit's cap, e.g. 3G (from the job's measured peak plus a margin)
#   options     --cpus LIST      CPU affinity of the unit, e.g. 5 or 4,6
#               --runtime-max S  stop the unit after S seconds (RuntimeMaxSec)
#               --oom-first      prefer this unit as the out-of-memory victim (short,
#                                restartable jobs such as guards and test runs)
#               --env K=V        extra environment variable (repeatable)
#               --dir PATH       working directory (default: the current directory)
#               --wait-headroom SIZE  start COMMAND only once the slice has SIZE (e.g. 6.5G)
#                                below its cap, counting anonymous memory (page cache is
#                                reclaimable); checked every 60 s inside the unit
#
# cells.slice (~/.config/systemd/user/cells.slice) caps all Cells units together; change
# it with `systemctl --user set-property cells.slice MemoryMax=...`. Every unit gets a
# positive OOMScoreAdjust, so a machine-wide shortage kills a Cells job before the user's
# other services or the agent session. OOMPolicy=continue: in a queue unit, an arm killed
# for memory fails alone and the queue goes on to its next item.
#
# The job keeps its own durable logs; the unit's stdout and stderr go to the journal.
#   status:   systemctl --user status cells-NAME
#   result:   journalctl --user -u cells-NAME -n 5   (result, CPU time and memory peak)
#   stop:     systemctl --user stop cells-NAME
set -euo pipefail
name=${1:?unit name}
mem=${2:?memory cap, e.g. 3G}
shift 2
cpus= runtime= adj=200 dir=$PWD headroom=
envs=()
while [ $# -gt 0 ]; do
  case "$1" in
    --cpus) cpus=$2; shift 2 ;;
    --runtime-max) runtime=$2; shift 2 ;;
    --oom-first) adj=500; shift ;;
    --env) envs+=("--setenv=$2"); shift 2 ;;
    --dir) dir=$2; shift 2 ;;
    --wait-headroom) headroom=$(LC_ALL=C numfmt --from=iec "$2"); shift 2 ;;
    --) shift; break ;;
    *) echo "run_detached.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
[ $# -gt 0 ] || { echo "run_detached.sh: no command given" >&2; exit 2; }
[[ $name =~ ^[A-Za-z0-9._-]+$ ]] || { echo "run_detached.sh: bad unit name $name" >&2; exit 2; }
if [ -n "$headroom" ]; then
  slice=/sys/fs/cgroup/user.slice/user-$(id -u).slice/user@$(id -u).service/cells.slice
  set -- bash -c 'need=$1 slice=$2; shift 2
    while :; do
      max=$(cat "$slice/memory.max"); anon=$(awk "/^anon /{print \$2}" "$slice/memory.stat")
      [ "$max" = max ] || [ $((max - anon)) -ge "$need" ] && break
      sleep 60
    done
    echo "run_detached: headroom $need bytes available at $(date -u +%FT%TZ)"
    exec "$@"' run_detached "$headroom" "$slice" "$@"
fi
props=(-p "MemoryMax=$mem" -p MemorySwapMax=0 -p OOMPolicy=continue -p "OOMScoreAdjust=$adj")
[ -z "$cpus" ] || props+=(-p "CPUAffinity=$cpus")
[ -z "$runtime" ] || props+=(-p "RuntimeMaxSec=$runtime")
exec systemd-run --user --unit="cells-$name" --slice=cells.slice --collect \
  --working-directory="$dir" "--setenv=PATH=$PATH" "${envs[@]}" "${props[@]}" -- "$@"
