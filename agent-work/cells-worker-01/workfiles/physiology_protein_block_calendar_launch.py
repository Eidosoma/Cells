"""Launch after explicit CPU coordination; detached, durable, no watcher."""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--cpu-released", action="store_true")
    args = parser.parse_args()
    if not args.cpu_released:
        parser.error("Chief must coordinate the declared CPU for full execution first")
    directory = args.directory.resolve()
    inputs = json.loads((directory / "inputs.json").read_text())
    if (
        inputs["status"] != "prepared_not_executed"
        or not inputs["execution_requires_explicit_cpu_release"]
    ):
        raise ValueError("Require the frozen deferred preparation")
    for name in (
        "launch.json",
        "result.json",
        "failure.json",
        "supervisor.stdout.log",
        "supervisor.stderr.log",
    ):
        if (directory / name).exists():
            raise FileExistsError(directory / name)
    for name, expected in inputs["helper_sha256"].items():
        if hashlib.sha256((directory / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Frozen validation helper changed: " + name)
    command = [
        sys.executable,
        "-B",
        str(directory / "driver.py"),
        "run",
        str(directory),
        "--cpu-released",
    ]
    with (directory / "supervisor.stdout.log").open("xb") as stdout:
        with (directory / "supervisor.stderr.log").open("xb") as stderr:
            child = subprocess.Popen(
                command,
                cwd=directory / "source",
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
                close_fds=True,
            )
    launch = dict(
        status="launched_detached",
        pid=child.pid,
        process_group=child.pid,
        launched_utc=datetime.now(timezone.utc).isoformat(),
        command=command,
        inputs=str(directory / "inputs.json"),
        source_snapshot=inputs["source_snapshot"],
        resource_limits=inputs["resource_limits"],
        expected_checks=inputs["expected_checks"],
        stdout=str(directory / "supervisor.stdout.log"),
        stderr=str(directory / "supervisor.stderr.log"),
        result=str(directory / "result.json"),
        failure=str(directory / "failure.json"),
        automatic_watcher=False,
        automatic_polling=False,
        automatic_followup=False,
    )
    with (directory / "launch.json").open("x") as handle:
        json.dump(launch, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    fd = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)
    print(json.dumps(launch))


if __name__ == "__main__":
    main()
