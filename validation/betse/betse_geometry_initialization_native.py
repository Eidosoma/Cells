"""Authenticated original DECMesh constructor/point-generator seed capture.

The mesh/topology evidence is reused from B09. This executes only constructor
seed preparation with a local original NumPy RandomState; no full make_world.
"""

import ast
import copy
import hashlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from scipy.spatial import cKDTree

PROTOCOL = Path(__file__).with_name("betse_geometry_initialization_protocol.json")


def state_record(rng):
    state = rng.get_state()
    return [state[0], state[1].tolist(), int(state[2]), int(state[3]), float(state[4])]


def capture():
    native = json.loads(PROTOCOL.read_text())["native_source"]
    root, installed = Path(native["checkout"]), Path(native["installed_package"]).parent
    frozen = Path(os.environ.get("CELLS_BETSE_SOURCE", str(root)))
    trees = {}
    for name, expected in native["source_sha256"].items():
        raw = (frozen / name).read_bytes()
        for path in (frozen / name, root / name, installed / name):
            if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise ValueError("Pinned geometry initialization source changed: " + str(path))
        trees[name] = ast.parse(raw, filename=str(root / name))
    tree = trees["betse/science/math/mesh.py"]
    if (
        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        != native["revision"]
    ):
        raise ValueError("Pinned native geometry revision changed")
    cls = next(
        node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "DECMesh"
    )
    functions = [
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef)
        and node.name in ("__init__", "make_single_cell_points")
    ]
    assert len(functions) == 2
    sites = {
        node.name: dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            ast_sha256=hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest(),
        )
        for node in functions
    }
    return functions, sites, native


def evaluate(recipe, before):
    functions, sites, native = capture()
    data = recipe["native_input"]
    rng = np.random.RandomState(0)
    rng.set_state(
        (before[0], np.asarray(before[1], dtype=np.uint32), before[2], before[3], before[4])
    )
    draws = []

    class RecordedRandom:
        def random(self, size):
            value = rng.random(size)
            draws.append(np.array(value, copy=True))
            return value

    class NumpyNamespace:
        random = RecordedRandom()

        def __getattr__(self, key):
            return getattr(np, key)

    namespace = dict(
        np=NumpyNamespace(), cKDTree=cKDTree, logs=SimpleNamespace(log_info=lambda *args: None)
    )
    module = ast.Module(body=copy.deepcopy(functions), type_ignores=[])
    exec(
        compile(
            ast.fix_missing_locations(module), "<pinned native geometry initialization>", "exec"
        ),
        namespace,
    )
    cls = type(
        "CapturedDECMesh",
        (),
        {name: namespace[name] for name in ("__init__", "make_single_cell_points")},
    )
    global_before = np.random.get_state()
    mesh = cls(
        seed_points=None
        if data["seed_points_m"] is None
        else np.asarray(data["seed_points_m"], dtype=np.float64),
        **data["mesh"],
    )
    global_after = np.random.get_state()
    unchanged = (
        global_before[0] == global_after[0]
        and np.array_equal(global_before[1], global_after[1])
        and global_before[2:] == global_after[2:]
    )
    return dict(
        points_m=np.array(mesh.tri_verts, copy=True),
        rng_before=before,
        rng_after=state_record(rng),
        x_uniforms=draws[0] if draws else np.empty(0),
        y_uniforms=draws[1] if draws else np.empty(0),
        source_sites=sites,
        native_source_sha256=native["source_sha256"],
        original_global_rng_unchanged=bool(unchanged),
        mesh_topology_reused_B09=True,
        full_make_world=False,
        biological_geometry=False,
    )
