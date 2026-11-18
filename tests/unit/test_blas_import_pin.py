"""The import pin reaches every module through `import cells` (D190; D198; D188 move 2's R6').

The pin's one home is cells/__init__.py again: no held law pins that file's bytes since D198's
retire batch, and importing any module of the package runs the package file first. So a path that
imports only execution (the assembly, pool and ensemble command lines import only the output-path
policy), only the registries, or only the run records still passes the pin, before and after move 2
splits core/ (the probes' names are dotted module paths, which the move rewrites).

Each probe is a fresh process with OPENBLAS_NUM_THREADS preset to 2: it imports one module and reads
the variable back. The pin sets it to 1 before any BLAS loads, so a lost pin shows on any number of
CPUs. With two or more CPUs the probe also reads every loaded BLAS's thread count back
(threadpoolctl), the direct observation, which one CPU cannot show. The planted package computes (it
imports numpy) but carries no pin: it must be caught.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PROBES = {
    "cells": "the package file, the pin's home",
    "cells.definitions.specs": "parse: the definitions' vocabulary",
    "cells.execution.runner": "runs",
    "cells.registry.kind_registry": "the kinds' registry",
    "cells.execution.output_paths": "the only core module the assembly, pool and ensemble lines import",
    "cells.registry.laws": "the law registry",
    "cells.records.observers": "imports only core's errors",
    "cells.records.io": "run records and checkpoints",
    "cells.execution.continuity": "checkpoint continuity, which imports no numpy",
    "cells.models.surface_pump_v3": "models",
}
PROBE = """
import importlib, json, os, sys
importlib.import_module(sys.argv[1])
env = os.environ.get("OPENBLAS_NUM_THREADS")
numpy_by_import = "numpy" in sys.modules
import numpy, scipy.linalg.cython_lapack, threadpoolctl
threads = sorted({i["num_threads"] for i in threadpoolctl.threadpool_info()
                  if i.get("user_api") == "blas"})
print(json.dumps(dict(env=env, threads=threads, cpus=len(os.sched_getaffinity(0)),
                      numpy_by_import=numpy_by_import)))
"""
THREAD_VARIABLES = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "GOTO_NUM_THREADS",
)


def probe(module, path):
    """Import `module` in a fresh process (sys.path from `path`): (pinned, what was read)."""
    env = {k: v for k, v in os.environ.items() if k not in THREAD_VARIABLES}
    env.update(PYTHONPATH=os.pathsep.join(map(str, path)), OPENBLAS_NUM_THREADS="2")
    proc = subprocess.run(
        [sys.executable, "-B", "-c", PROBE, module],
        env=env,
        cwd=path[0],
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert proc.returncode == 0, proc.stderr[-2000:]
    read = json.loads(proc.stdout.strip().splitlines()[-1])
    pinned = read["env"] == "1" and (read["cpus"] < 2 or read["threads"] == [1])
    return pinned, read


@pytest.mark.parametrize("module", PROBES)
def test_each_module_is_pinned_through_the_package_file(module):
    pinned, read = probe(module, [ROOT / "src"])
    assert pinned, (module, PROBES[module], read)


def test_checkpoint_continuity_still_imports_no_numpy():
    _, read = probe("cells.execution.continuity", [ROOT / "src"])
    assert read["numpy_by_import"] is False, read


def test_a_computing_package_without_the_pin_is_caught(tmp_path):
    package = tmp_path / "planted_computing"
    package.mkdir()
    (package / "__init__.py").write_text('"""A computing package whose pin call is lost."""\n')
    (package / "kernel.py").write_text("import numpy as np\n\nSOLVE = np.linalg.solve\n")
    pinned, read = probe("planted_computing.kernel", [tmp_path, ROOT / "src"])
    assert not pinned and read["env"] == "2", read
    if read["cpus"] >= 2:  # The direct observation: OpenBLAS kept its own thread count.
        assert read["threads"] != [1], read
