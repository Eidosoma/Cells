"""Execute unmodified x/y/r functions from the pinned BETSE source capture."""

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
        raise ValueError("Pinned spatial modulator source changed")
    functions = [
        copy.deepcopy(node)
        for node in ast.parse(data).body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("gradient_x", "gradient_y", "gradient_r")
    ]
    assert len(functions) == 3
    namespace = {"np": np}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<pinned BETSE spatial modulators>",
            "exec",
        ),
        namespace,
    )
    return namespace


def evaluate(saved):
    cell_ids, membrane_ids = saved["cell_ids"], saved["membrane_ids"]
    owners = cell_ids if saved["target_domain"] == "cells" else membrane_ids
    cells = SimpleNamespace(
        cell_i=np.arange(len(cell_ids)),
        mem_i=np.arange(len(membrane_ids)),
        cell_centres=np.asarray(saved["cell_centres_m"], dtype=np.float64),
        mem_mids_flat=np.asarray(saved["membrane_midpoints_m"], dtype=np.float64),
        centre=np.asarray(saved["centre_m"], dtype=np.float64),
    )
    properties = dict(exponent=saved["exponent"], slope=saved["slope"])
    properties.update({"x-offset": saved["x_offset"], "z-offset": saved["z_offset"]})
    parameters = SimpleNamespace(**{saved["kind"] + "_properties": properties})
    targets = np.asarray([owners.index(name) for name in saved["target_ids"]], dtype=np.int64)
    values, dynamic = capture()[saved["kind"]](targets, cells, parameters)
    return dict(factor=values, dynamic=[dynamic(t) for t in (0.0, 1.0, -1.0)], source_sha256=PINNED)
