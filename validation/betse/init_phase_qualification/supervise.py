"""Explicit later launch only; retain failures before output ownership."""

import hashlib
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LAUNCH = ROOT / "launch-01"


def sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    path = Path(path)
    if path.stat().st_size > 16 * 2**20:
        raise ValueError("Supervisor metadata exceeds 16 MiB")
    return json.loads(path.read_text())


def write(path, value):
    path = Path(path)
    temporary = Path(str(path) + ".pending")
    with temporary.open("x") as stream:
        json.dump(value, stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def utc():
    return datetime.now(timezone.utc).isoformat()


def available():
    return next(
        int(line.split()[1]) * 1024
        for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemAvailable:")
    )


def verify_plan():
    # Import the controller only inside an owned startup/worker exception path.
    seal = read(ROOT / "seal.json")
    if sha(ROOT / "controller.py") != seal["files"]["controller.py"]:
        raise ValueError("Controller source changed")
    from common import verify_release as verify

    return verify()


def worker():
    try:
        plan = verify_plan()
        os.sched_setaffinity(0, {plan["cpu"]})
        result = subprocess.run(
            [plan["python"], "-B", str(ROOT / "controller.py"), "worker"],
            cwd=ROOT,
            stdin=subprocess.DEVNULL,
            check=False,
        )
        target = Path(plan["output"]) / "result.json"
        terminal = read(target) if target.exists() else None
        passed = (
            result.returncode == 0
            and terminal is not None
            and terminal.get("status") == "numerical_phases_completed_pending_review"
            and terminal.get("checks") == 62
            and terminal.get("newly_executed_checks") == 62
            and terminal.get("retained_checks") == 0
            and terminal.get("accepted_calls") == 61
            and terminal.get("fresh_conditional_reference_forms") == 986
            and terminal.get("native_captures") == 29
        )
        write(
            LAUNCH / "controller-exit.json",
            dict(
                status="passed_pending_review" if passed else "failed",
                returncode=result.returncode,
                runner_result=str(target) if target.exists() else None,
                runner_result_sha256=sha(target) if target.exists() else None,
                automatic_retry=False,
                automatic_followup=False,
                utc=utc(),
            ),
        )
        if not passed:
            raise RuntimeError("Frozen INIT03 controller did not finish all 62 fresh checks")
    except BaseException as error:
        write(
            LAUNCH / "failure.json",
            dict(
                status="failed",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                runner_evidence_untouched=True,
                automatic_retry=False,
                automatic_followup=False,
                utc=utc(),
            ),
        )
        raise


def launch():
    # Never alter an earlier launch or qualification output.
    LAUNCH.mkdir(exist_ok=False)
    child = None
    try:
        plan = verify_plan()
        if Path(plan["output"]).exists():
            raise FileExistsError("Qualification output already exists")
        if plan["cpu"] not in os.sched_getaffinity(0):
            raise ValueError("Requested coordinated CPU is unavailable")
        if available() < plan["launch_min_available_bytes"]:
            raise RuntimeError("Host memory below the declared launch gate")
        os.sched_setaffinity(0, {plan["cpu"]})
        with (
            (LAUNCH / "stdout.log").open("x") as stdout,
            (LAUNCH / "stderr.log").open("x") as stderr,
        ):
            child = subprocess.Popen(
                [plan["python"], "-B", str(ROOT / "supervise.py"), "worker"],
                cwd=ROOT,
                stdout=stdout,
                stderr=stderr,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        identity = int(Path(f"/proc/{child.pid}/stat").read_text().rsplit(")", 1)[1].split()[19])
        receipt = dict(
            status="launched",
            pid=child.pid,
            process_start_ticks=identity,
            utc=utc(),
            cpu=plan["cpu"],
            detached=True,
            output=plan["output"],
            plan_sha256=sha(ROOT / "plan.json"),
            release_sha256=sha(ROOT / "release.json"),
            automatic_polling=False,
            automatic_retry=False,
            automatic_followup=False,
        )
        write(LAUNCH / "launch.json", receipt)
        print(json.dumps(receipt), flush=True)
    except BaseException as error:
        write(
            LAUNCH / "launch-failure.json",
            dict(
                status="launch_failed",
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                child_pid=None if child is None else child.pid,
                worker_evidence_untouched=True,
                automatic_retry=False,
                utc=utc(),
            ),
        )
        raise


if __name__ == "__main__":
    if sys.argv[1:] == ["launch"]:
        launch()
    elif sys.argv[1:] == ["worker"]:
        worker()
    else:
        raise SystemExit("Use launch only after a new instruction and explicit release")
