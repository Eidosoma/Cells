"""Execute pinned BETSE periodic/f_sweep functions, retaining setup mutation."""

import ast
import copy
import hashlib
import os
from functools import lru_cache
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PINNED = {
    "betse/science/math/modulate.py": (
        "c29f4ae27930f00780736e075183e61f44263dd0caa9d7c2f9a30971f616bff7"
    )
}


@lru_cache(maxsize=1)
def capture():
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", "/mnt/workspaces/Cells/betse-v1.5.0"))
    name, expected = next(iter(PINNED.items()))
    data = (root / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError("Pinned modulation source changed")
    functions = [
        copy.deepcopy(node)
        for node in ast.parse(data).body
        if isinstance(node, ast.FunctionDef) and node.name in ("periodic", "f_sweep")
    ]
    assert len(functions) == 2
    namespace = {"np": np}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<pinned BETSE time modulators>",
            "exec",
        ),
        namespace,
    )
    return namespace


def prepare(program):
    """Return the actual captured source callback and its resolved setup values."""
    source = capture()
    if program["kind"] == "periodic":
        parameters = SimpleNamespace(
            periodic_properties={
                "frequency": program["frequency_Hz"],
                "phase": program["phase_rad"],
            }
        )
        scalar, dynamic = source["periodic"](None, None, parameters)
        slope = None
    elif program["kind"] == "sweep":
        parameters = SimpleNamespace(
            _run_sim=program["automatic_slope"],
            sim_time_total=program["original_duration_s"],
            f_scan_properties={
                "f start": program["frequency_Hz"],
                "f stop": program["requested_stop_Hz"],
                "f slope": None if program["automatic_slope"] else program["slope_Hz_s"],
            },
        )
        scalar, dynamic = source["f_sweep"](None, None, parameters)
        slope = parameters.f_scan_properties["f slope"]
    else:
        raise ValueError("Unknown native time-modulation function")
    return scalar, dynamic, slope


def evaluate(program, times):
    scalar, dynamic, slope = prepare(program)
    values = dynamic(np.asarray(times, dtype=np.float64))
    return dict(
        factor=values, scalar=scalar, resolved_slope_Hz_s=slope, native_source_sha256=dict(PINNED)
    )
