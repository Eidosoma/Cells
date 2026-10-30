"""Read-only hashes of the actual loaded Python and extension module files."""

import hashlib
import os
import platform
import sys
from pathlib import Path


def inventory():
    files, no_file = {}, []
    for name, module in sorted(tuple(sys.modules.items())):
        value = getattr(module, "__file__", None)
        if value is None:
            no_file.append(name)
            continue
        path = Path(value).resolve()
        if not path.is_file():
            files[name] = dict(path=str(path), unavailable=True)
            continue
        files[name] = dict(path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest())
    executable = Path(sys.executable).resolve()
    return dict(
        python=platform.python_version(),
        measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
        executable=dict(
            path=str(executable), sha256=hashlib.sha256(executable.read_bytes()).hexdigest()
        ),
        loaded_files=files,
        modules_without_files=no_file,
    )
