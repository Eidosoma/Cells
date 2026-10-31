"""Durable fresh-process controls using the unchanged scalar Decimal worker."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def save(root, name, value):
    path = Path(root) / (name + ".json")
    with path.open("x") as stream:
        json.dump(value, stream, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return path


def reference(root, label, declaration, constants, *, mode, precision, points=None):
    worker = Path(__file__).with_name("charged_surface_work_reference.py")
    request = dict(
        mode=mode, declaration=declaration, constants_binary64_hex=constants, precision=precision
    )
    if points is not None:
        request["points"] = points
    text = json.dumps(request, sort_keys=True, allow_nan=False)
    save(root, label + "_request", request)
    argv = [sys.executable, "-I", "-S", "-B", str(worker)]
    process = subprocess.Popen(
        argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    try:
        stdout, stderr = process.communicate(text, timeout=60)
    except subprocess.TimeoutExpired:
        process.kill()
        stdout, stderr = process.communicate()
        save(
            root,
            label + "_timeout",
            dict(
                argv=argv,
                pid=process.pid,
                stdout=stdout,
                stderr=stderr,
                bounded_timeout_seconds=60,
                request_sha256=hashlib.sha256(text.encode()).hexdigest(),
            ),
        )
        raise
    save(
        root,
        label + "_actual_process",
        dict(
            argv=argv,
            pid=process.pid,
            ppid=os.getpid(),
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            request_sha256=hashlib.sha256(text.encode()).hexdigest(),
            worker_sha256=hashlib.sha256(worker.read_bytes()).hexdigest(),
        ),
    )
    if process.returncode != 0:
        raise RuntimeError("Independent reference failed; actual request/stdout/stderr retained")
    result = json.loads(stdout)
    save(root, label + "_raw_return", result)
    runtime = result["independent_runtime"]
    if (
        runtime["pid"] != process.pid
        or runtime["ppid"] != os.getpid()
        or runtime["isolated"] != 1
        or runtime["no_site"] != 1
        or runtime["science_modules_loaded"] != []
    ):
        raise RuntimeError("Actual independent child/runtime contract differs")
    return result
