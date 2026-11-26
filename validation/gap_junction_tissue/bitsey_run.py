"""Run BITSEY unmodified, out of process, for the gap-junction replication's reference (D219).

BITSEY (gitlab.com/grodstein/bitsey) is the preprint's simulator. It is a reference only
(AGENTS.md): this file never imports it and copies none of its code. It starts BITSEY's own
command line, `python zombie.py FUNCTION X Y Z NR [MIN MAX]` (cancer_GJ_sims/zombie.py's main), in
BITSEY's own environment, in a clean checkout of one pinned revision, and saves what BITSEY
prints. Only argv,
the environment and stdin are chosen here, and the process may be stopped once the searches asked
for have printed their result. Nothing in BITSEY's checkout is written: bytecode is off, and the
tree is checked clean before and after.

What is recorded beside the log (run.json):
- the checkout's revision and `git status --porcelain` before and after (both must be empty);
- the licence check: every tracked file whose name says licence or copying (none at b2cb370), and
  how many tracked files point to a LICENSE ("See LICENSE");
- BITSEY's interpreter, its version and `pip freeze`;
- the command, the environment set here, the start and end times, the exit status and why the
  process stopped;
- the log's sha256.

The environment: MPLBACKEND=Agg (zombie.py imports pyplot), one BLAS and OpenMP thread, no
bytecode, stdin from /dev/null (sim.py calls pdb.set_trace() on a negative concentration; with no
input the debugger quits).

Usage (stdlib only; any Python 3.11+ runs it):
    python3 -I validation/gap_junction_tissue/bitsey_run.py --checkout DIR --revision HASH \\
        --python /mnt/workspaces/Cells/venv-bitsey/bin/python --out OUT \\
        --function zombie_tumor_isolate --field 1,1,25 --nr 0 [--range 0,1] [--stop-after 1]
The saved log is read by validation/gap_junction_tissue/bitsey_log.py.
"""

import argparse
import datetime
import hashlib
import json
import os
import platform
import re
import signal
import subprocess
import sys
import time
from pathlib import Path

SEARCH_DONE = re.compile(r"^Binary search for .* returning \(")
LICENCE_NAME = re.compile(r"(licen[cs]e|copying)", re.IGNORECASE)
ENVIRONMENT = {
    "MPLBACKEND": "Agg",
    "OMP_NUM_THREADS": "1",
    "OPENBLAS_NUM_THREADS": "1",
    "MKL_NUM_THREADS": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PYTHONHASHSEED": "0",
}


def utc():
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def git(checkout, *args):
    return subprocess.run(
        ["git", "-C", str(checkout), *args], capture_output=True, text=True, check=True, timeout=120
    ).stdout


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def licence_check(checkout):
    """The tracked files whose names say licence or copying, and the tracked Python files whose
    header points to a LICENSE file."""
    tracked = [name for name in git(checkout, "ls-files", "-z").split("\0") if name]
    named = sorted(name for name in tracked if LICENCE_NAME.search(Path(name).name))
    pointing = []
    for name in tracked:
        if name.endswith(".py"):
            head = (Path(checkout) / name).read_text(errors="replace").splitlines()[:5]
            if any("LICENSE" in line for line in head):
                pointing.append(name)
    return dict(
        licence_files=named,
        files_pointing_to_a_licence=sorted(pointing),
        tracked_files=len(tracked),
        found=bool(named),
    )


def interpreter(python):
    version = subprocess.run(
        [python, "-I", "-c", "import sys; print(sys.version)"],
        capture_output=True,
        text=True,
        check=True,
        timeout=120,
    ).stdout.strip()
    freeze = subprocess.run(
        [python, "-I", "-m", "pip", "freeze"], capture_output=True, text=True, timeout=300
    ).stdout.splitlines()
    return dict(path=python, version=version, packages=freeze)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--checkout", required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--python", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--function", default="zombie_tumor_isolate")
    parser.add_argument("--field", required=True, help="X,Y,Z, e.g. 1,1,25 or 1,25,25")
    parser.add_argument("--nr", default="0")
    parser.add_argument("--range", default="", help="MIN,MAX of zombie.py's test numbers")
    parser.add_argument("--stop-after", type=int, default=0, help="searches; 0 runs to the end")
    parser.add_argument("--runtime-max", type=float, default=0.0, help="seconds; 0 for none")
    args = parser.parse_args(argv)
    checkout, out = Path(args.checkout).resolve(), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    record = dict(
        format="gap_junction_tissue.bitsey_run@1",
        reference="BITSEY, gitlab.com/grodstein/bitsey, run unmodified and out of process (D219)",
        checkout=str(checkout),
        requested_revision=args.revision,
        started_utc=utc(),
        host=platform.node(),
        runner=dict(path=str(Path(__file__).resolve()), python=sys.version),
    )
    head = git(checkout, "rev-parse", "HEAD").strip()
    status_before = git(checkout, "status", "--porcelain", "--untracked-files=all")
    record.update(revision=head, status_before=status_before.splitlines())
    if head != args.revision or status_before:
        record["refused"] = "the checkout is not the requested revision, or not clean"
        (out / "run.json").write_text(json.dumps(record, indent=1))
        return 2
    record["licence"] = licence_check(checkout)
    record["interpreter"] = interpreter(args.python)
    field = [str(int(v)) for v in args.field.split(",")]
    command = [args.python, "-B", "-u", "zombie.py", args.function, *field, args.nr]
    if args.range:
        command += args.range.split(",")
    env = {k: v for k, v in os.environ.items() if k in ("PATH", "HOME", "LANG", "LC_ALL")}
    env.update(ENVIRONMENT)
    record.update(
        command=command,
        cwd=str(checkout / "cancer_GJ_sims"),
        environment=ENVIRONMENT,
        stop_after_searches=args.stop_after or None,
        runtime_max_s=args.runtime_max or None,
    )
    (out / "run.json").write_text(json.dumps(record, indent=1))
    log, errors = out / "bitsey.log", out / "bitsey.stderr"
    started = time.monotonic()
    searches, stopped = 0, None
    with log.open("w") as stream, errors.open("w") as error_stream:
        process = subprocess.Popen(
            command,
            cwd=checkout / "cancer_GJ_sims",
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=error_stream,
            start_new_session=True,
        )
        record["pid"] = process.pid
        with log.open() as reader:
            while True:
                line = reader.readline()
                if line:
                    if SEARCH_DONE.match(line):
                        searches += 1
                        if args.stop_after and searches >= args.stop_after:
                            stopped = f"stopped after {searches} searches had printed their result"
                            break
                    continue
                if process.poll() is not None:
                    rest = reader.read()
                    searches += sum(bool(SEARCH_DONE.match(x)) for x in rest.splitlines())
                    break
                if args.runtime_max and time.monotonic() - started > args.runtime_max:
                    stopped = f"stopped at the runtime cap, {args.runtime_max:g} s"
                    break
                time.sleep(0.5)
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=60)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    status_after = git(checkout, "status", "--porcelain", "--untracked-files=all")
    record.update(
        finished_utc=utc(),
        seconds=time.monotonic() - started,
        exit_status=process.returncode,
        searches_completed=searches,
        stopped=stopped or "ran to its end",
        status_after=status_after.splitlines(),
        checkout_clean_after=not status_after,
        log=dict(path=log.name, sha256=sha256(log), bytes=log.stat().st_size),
        stderr=dict(path=errors.name, sha256=sha256(errors), bytes=errors.stat().st_size),
    )
    (out / "run.json").write_text(json.dumps(record, indent=1))
    print(json.dumps({k: record[k] for k in ("revision", "stopped", "exit_status", "seconds")}))
    return 0 if record["checkout_clean_after"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
