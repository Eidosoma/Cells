#!/bin/bash
# The captures of section 8 of the legacy port plan, in shards, from a frozen snapshot.
#
#   capture.sh SNAPSHOT ORIGIN OUT [--set science|check|windows|extra] [--cap-bytes N]
#     [--job-seconds S]
#
# ORIGIN is capture_worlds.py write's folder; OUT must not exist. One shard runs per CPU of this
# process's own affinity (a unit's --cpus, or taskset's), each pinned to its CPU, and the shards
# claim the jobs in turn, so a failed or refused job stops no other. Each job is one process with
# its own log, time limit and record. No job starts once OUT holds --cap-bytes (1 GiB by default) or
# the disk has less than 50 GiB free, and no single file may grow past the cap.
#
# OUT holds started.json, logs/, jobs/ (one record per job), runs/ (the outputs), tool/ (this
# tool's files), MANIFEST.json (every file's sha256, both revisions, the environment, the commands
# and the timings) and EXIT: "0" when every job is ok, "1" when any failed, was refused or was not
# run, "2" when this script stopped before its end.
#
# The `science` set is the plan's. The `check` set is the first steps of each captured world: run it
# with the captures, and again at a later snapshot into another OUT, and compare the two
# (capture_worlds.py compare). The `windows` set is the bitwise windows of the kept core, which
# depend on the route: it is written here so that it can be run later from the same snapshot. The
# `extra` set (capture_worlds.py write-extra) holds used worlds the science set left out.
set -u
here=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd) || exit 2
python=${CELLS_PYTHON:-/mnt/workspaces/Cells/venv-cpu/bin/python}
snapshot=${1:?snapshot} origin=${2:?origin} out=${3:?output folder}
shift 3
set_name=science cap=$((1024 ** 3)) seconds=3600
while [ $# -gt 0 ]; do
  case "$1" in
    --set) set_name=$2; shift 2 ;;
    --cap-bytes) cap=$2; shift 2 ;;
    --job-seconds) seconds=$2; shift 2 ;;
    *) echo "capture.sh: unknown option $1" >&2; exit 2 ;;
  esac
done
case "$set_name" in science | check | windows | extra) ;; *) echo "capture.sh: bad set $set_name" >&2; exit 2 ;; esac
snapshot=$(realpath "$snapshot") && origin=$(realpath "$origin") || exit 2
[ -f "$snapshot/SNAPSHOT.json" ] && [ -f "$origin/jobs-$set_name.json" ] || {
  echo "capture.sh: no snapshot or no job list" >&2; exit 2; }
mkdir "$out" || { echo "capture.sh: refused: $out exists or cannot be made" >&2; exit 2; }
out=$(realpath "$out")
trap '[ -f "$out/EXIT" ] || echo "2 $(date -u +%FT%TZ) capture.sh stopped before its end" > "$out/EXIT"' EXIT

# The environment of every job: the snapshot's source, one thread, the CPU, cold compilation.
unset XLA_FLAGS JAX_DISABLE_JIT PYTHONHOME PYTHONSTARTUP
export PYTHONPATH="$snapshot/src:$snapshot" PYTHONDONTWRITEBYTECODE=1
export JAX_PLATFORMS=cpu JAX_ENABLE_X64=1 JAX_ENABLE_COMPILATION_CACHE=false CUDA_VISIBLE_DEVICES=
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1
export CELLS_OUTPUT_ROOT="$out" TMPDIR="$out/tmp"
ulimit -f $((cap / 1024)) || exit 2
mkdir "$out/jobs" "$out/logs" "$out/runs" "$out/tmp" "$out/tool"
cp "$here/capture.sh" "$here/capture_worlds.py" "$out/tool/"

# The snapshot is immutable, complete and unchanged (every file's hash), or nothing runs.
"$python" -B -c 'import sys
from validation.source_snapshot import verify
v = verify(sys.argv[1])
print("snapshot", v["git_revision"], len(v["files"]), "files")' "$snapshot" \
  > "$out/logs/snapshot.log" 2>&1 || { echo "capture.sh: the snapshot does not verify" >&2; exit 2; }

mapfile -t cpus < <("$python" -B -c 'import os; print(*sorted(os.sched_getaffinity(0)), sep="\n")')
[ ${#cpus[@]} -gt 0 ] || exit 2
"$python" -B - "$out" "$set_name" "$cap" "$seconds" "${cpus[@]}" <<'EOF' || exit 2
import json, os, platform, sys
from datetime import UTC, datetime

out, set_name, cap, seconds, *cpus = sys.argv[1:]
names = ("PYTHONPATH", "JAX_PLATFORMS", "JAX_ENABLE_X64", "JAX_ENABLE_COMPILATION_CACHE",
         "CUDA_VISIBLE_DEVICES", "OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS",
         "PYTHONDONTWRITEBYTECODE", "CELLS_OUTPUT_ROOT", "XLA_FLAGS", "JAX_DISABLE_JIT", "TMPDIR")
model = [x.split(":")[1].strip() for x in open("/proc/cpuinfo") if x.startswith("model name")]
json.dump(dict(utc=datetime.now(UTC).isoformat(timespec="seconds"), set=set_name,
               cap_bytes=int(cap), job_seconds=int(seconds), cpus=[int(c) for c in cpus],
               python=sys.version, machine=platform.machine(), cpu_model=model[0],
               environment={n: os.environ.get(n) for n in names}),
          open(os.path.join(out, "started.json"), "x"), indent=1)
EOF

echo "$(date -u +%FT%TZ) $set_name: ${#cpus[@]} shards on CPUs ${cpus[*]}" | tee "$out/logs/capture.log"
for cpu in "${cpus[@]}"; do
  taskset -c "$cpu" "$python" -B "$here/capture_worlds.py" shard "$snapshot" "$origin" "$out" \
    "$set_name" --cap-bytes "$cap" --job-seconds "$seconds" > "$out/logs/shard-$cpu.log" 2>&1 &
done
wait
"$python" -B "$here/capture_worlds.py" finish "$snapshot" "$origin" "$out" "$set_name" \
  > "$out/logs/finish.log" 2>&1
code=$?
echo "$(date -u +%FT%TZ) done: $(cat "$out/EXIT" 2>/dev/null)" >> "$out/logs/capture.log"
exit "$code"
