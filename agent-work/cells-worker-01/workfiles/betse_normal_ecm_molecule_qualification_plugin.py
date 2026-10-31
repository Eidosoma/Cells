"""Future pytest child provenance only; no scientific implementation or fixtures."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

REPORTS = []
CHILDREN = []
ORIGINAL_POPEN = subprocess.Popen


def append(name, value):
    folder = Path(os.environ["CELLS_MOLECULE_RUNNER_PROVENANCE"])
    with (folder / name).open("a") as stream:
        stream.write(json.dumps(value, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


class ObservedPopen(ORIGINAL_POPEN):
    def __init__(self, *args, **kwargs):
        command = args[0] if args else kwargs.get("args")
        incoming = None
        if isinstance(command, (list, tuple)) and "--inputs" in command:
            path = Path(command[command.index("--inputs") + 1])
            if not path.is_file() or path.is_symlink() or path.stat().st_size > 64 * 2**20:
                raise ValueError("Bounded actual child input required")
            incoming = dict(
                path=str(path.resolve()), sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
        super().__init__(*args, **kwargs)
        self.runner_child_id = len(CHILDREN)
        self.runner_recorded = False
        record = dict(
            child_id=self.runner_child_id,
            pid=self.pid,
            command=self.args,
            input_record=incoming,
            start_ticks=int(
                Path(f"/proc/{self.pid}/stat").read_text().rsplit(")", 1)[1].split()[19]
            ),
            cpu_affinity=sorted(os.sched_getaffinity(self.pid)),
        )
        CHILDREN.append(record)
        append("subprocess-start.jsonl", record)

    def wait(self, *args, **kwargs):
        code = super().wait(*args, **kwargs)
        if hasattr(self, "runner_recorded") and not self.runner_recorded:
            self.runner_recorded = True
            append(
                "subprocess-finish.jsonl",
                dict(child_id=self.runner_child_id, pid=self.pid, returncode=code),
            )
        return code


def write(name, value):
    folder = Path(os.environ["CELLS_MOLECULE_RUNNER_PROVENANCE"])
    with (folder / name).open("x") as stream:
        json.dump(value, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def identity():
    return dict(
        pid=os.getpid(),
        start_ticks=int(Path("/proc/self/stat").read_text().rsplit(")", 1)[1].split()[19]),
        cpu_affinity=sorted(os.sched_getaffinity(0)),
        executable=str(Path(sys.executable).resolve()),
        executable_sha256=hashlib.sha256(Path(sys.executable).resolve().read_bytes()).hexdigest(),
        optimize=sys.flags.optimize,
    )


def pytest_sessionstart(session):
    write("pytest-start.json", dict(identity(), started_ns=time.time_ns()))
    subprocess.Popen = ObservedPopen


def pytest_runtest_logreport(report):
    row = dict(
        nodeid=report.nodeid,
        when=report.when,
        outcome=report.outcome,
        wasxfail=hasattr(report, "wasxfail"),
        longrepr=str(report.longrepr) if report.failed or report.skipped else None,
    )
    REPORTS.append(row)
    folder = Path(os.environ["CELLS_MOLECULE_RUNNER_PROVENANCE"])
    with (folder / "pytest-reports.jsonl").open("a") as stream:
        stream.write(json.dumps(row, allow_nan=False) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def pytest_sessionfinish(session, exitstatus):
    subprocess.Popen = ORIGINAL_POPEN
    from validation.betse.betse_normal_channel_join_runtime import inventory

    write(
        "pytest-finish.json",
        dict(
            identity(),
            exitstatus=int(exitstatus),
            testscollected=session.testscollected,
            reports=REPORTS,
            runtime=inventory(),
        ),
    )
