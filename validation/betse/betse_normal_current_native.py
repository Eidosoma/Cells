"""Authenticated current/smoothing prefix; no ECM or voltage source execution."""

import argparse
import ast
import builtins
import copy
import hashlib
import importlib.abc
import json
import os
import platform
import struct
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_normal_current_protocol.json")


def wrapper(name, args, body):
    function = ast.parse("def " + name + "(" + args + "):\n pass\n").body[0]
    function.body = copy.deepcopy(body)
    return function


def capture():
    protocol = json.loads(PROTOCOL.read_text())
    native = protocol["native_source"]
    root = Path(native["checkout"])
    installed = Path(native["installed_package"]).parent
    trees = {}
    for name, expected in native["source_sha256"].items():
        raw = (root / name).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != expected
            or hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Pinned current source/installed bytes changed: " + name)
        trees[name] = ast.parse(raw, filename=str(root / name))
    if (
        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        != native["revision"]
    ):
        raise ValueError("Pinned native revision changed")
    current = next(
        n
        for n in trees["betse/science/physics/ion_current.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "get_current"
    )
    stop = next(i for i, n in enumerate(current.body) if isinstance(n, ast.If))
    prefix = current.body[:stop]
    assert isinstance(prefix[-1], ast.Assign) and ast.unparse(prefix[-1].targets[0]) == "sim.Jc"
    assert ast.unparse(current.body[stop].test) == "p.is_ecm is True"
    sim_cls = next(
        n
        for n in trees["betse/science/sim.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Simulator"
    )
    dynamics = next(
        n for n in sim_cls.body if isinstance(n, ast.FunctionDef) and n.name == "init_dynamics"
    )
    first = next(
        i
        for i, n in enumerate(dynamics.body)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "nfrac" for t in n.targets)
    )
    last = next(
        i
        for i, n in enumerate(dynamics.body)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.smooth_weight_o" for t in n.targets)
    )
    weights = dynamics.body[first : last + 1]
    sharpness = [
        n
        for n in ast.walk(trees["betse/science/parameters.py"])
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.smooth_cells" for t in n.targets)
    ]
    assert len(sharpness) == 1
    cls = next(
        n
        for n in trees["betse/science/cells.py"].body
        if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    matrices = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "cellMatrices"
    )
    a = next(
        i
        for i, n in enumerate(matrices.body)
        if isinstance(n, ast.Assign) and any(ast.unparse(t) == "self.M_sum_mems" for t in n.targets)
    )
    b = next(
        i
        for i, n in enumerate(matrices.body)
        if isinstance(n, ast.Assign)
        and any(ast.unparse(t) == "self.num_mems" for t in n.targets)
        and isinstance(n.value, ast.Call)
        and ast.unparse(n.value.func) == "np.asarray"
    )
    blocks = dict(
        current=prefix,
        weights=weights,
        sharpness=sharpness,
        owner_matrices=matrices.body[a : b + 1],
    )
    args = dict(
        current="sim,cells,p", weights="self,cells,p", sharpness="self,iu", owner_matrices="self"
    )
    functions = [wrapper(name, args[name], body) for name, body in blocks.items()]
    observed = []
    for node in functions[0].body:
        observed.append(node)
        if isinstance(node, ast.Assign):
            target = ast.unparse(node.targets[0])
            if target == "sim.Jn" and ast.unparse(node.value) == "sim.Jmem + sim.Jgj":
                observed.extend(ast.parse("_observe('raw_normal_current_A_m2',sim.Jn)").body)
            if target == "Jn_ave":
                observed.extend(ast.parse("_observe('average_normal_current_A_m2',Jn_ave)").body)
    functions[0].body = observed
    namespace = {"np": np}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<pinned native current prefix>",
            "exec",
        ),
        namespace,
    )
    sites = {
        name: dict(first_line=body[0].lineno, last_line=body[-1].end_lineno)
        for name, body in blocks.items()
    }
    return namespace, sites, native


def evaluate(inputs):
    source, sites, pins = capture()
    raw = inputs["definition"]
    g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
    owner = np.asarray(g["owner"], np.int64)
    n, m = len(g["cell_ids"]), len(owner)
    if (
        not 1 <= n <= 16
        or not 1 <= m <= 128
        or not 1 <= len(inputs["snapshots"]) <= 64
        or len(ions["ids"]) > 32
    ):
        raise ValueError("Refuse unbounded native current microcase")
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        mem_to_cells=owner,
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_sa=np.asarray(g["cell_area_m2"], np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
    )
    source["owner_matrices"](cells)
    parameters = SimpleNamespace(F=p["F_C_mol"])
    sim = SimpleNamespace(zs=np.asarray(ions["valence"], np.float64))
    before = copy.deepcopy(np.random.get_state())
    intermediates = {}
    source["_observe"] = lambda name, value: intermediates.__setitem__(
        name, np.array(value, copy=True)
    )
    history = []
    failure = None
    status = "not_started"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            source["sharpness"](parameters, {"sharpness cell": p["sharpness_cell"]})
            source["weights"](sim, cells, parameters)
            for index, snapshot in enumerate(inputs["snapshots"]):
                intermediates.clear()
                for key, name in (
                    ("cell_mol_m3", "cc_cells"),
                    ("membrane_flux_mol_m2_s", "fluxes_mem"),
                    ("junction_flux_mol_m2_s", "fluxes_gj"),
                    ("extra_charge_C_m3", "extra_rho_cells"),
                    ("extra_current_A_m2", "extra_J_mem"),
                ):
                    setattr(sim, name, np.asarray(snapshot[key], np.float64).copy())
                source["current"](sim, cells, parameters)
                history.append(
                    dict(
                        index=index,
                        state=copy.deepcopy(vars(sim)),
                        intermediates=copy.deepcopy(intermediates),
                    )
                )
            status = "source_completed"
        except Exception as error:
            status = "source_refused"
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    after = np.random.get_state()
    unchanged = (
        before[0] == after[0] and np.array_equal(before[1], after[1]) and before[2:] == after[2:]
    )
    return dict(
        kind="cells.native_normal_current_capture@1",
        status=status,
        inputs=inputs,
        history=history,
        final_state=copy.deepcopy(vars(sim)),
        source_parameters=vars(parameters),
        failure=failure,
        warnings=[str(w.message) for w in caught],
        native_source=pins,
        source_sites=sites,
        RNG_before=before,
        RNG_after=after,
        RNG_unchanged=unchanged,
        runtime=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
        ),
        scope=(
            "Actual sharpness, owner matrix, source smoothing and intracellular current "
            "prefix; read-only intermediate copies; no ECM/voltage/initializer"
        ),
    )


def write_archive(directory, payload):
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    arrays = {}

    def encode(value):
        if isinstance(value, (np.ndarray, np.generic)):
            a = np.asarray(value)
            if a.dtype.kind not in "biuf":
                raise ValueError("Unsupported numeric archive dtype")
            key = "a" + str(len(arrays))
            arrays[key] = np.array(a, copy=True)
            return dict(array=key, dtype=a.dtype.str, shape=list(a.shape))
        if isinstance(value, dict):
            return dict(mapping=[[key, encode(item)] for key, item in value.items()])
        if isinstance(value, (list, tuple)):
            return dict(sequence=[encode(item) for item in value])
        if type(value) is float:
            return dict(float64_bits=struct.pack("<d", value).hex())
        if value is None or type(value) in (str, int, bool):
            return value
        raise ValueError("Unsupported raw current evidence: " + type(value).__name__)

    with (path / "data.json").open("x") as stream:
        json.dump(encode(payload), stream, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    with (path / "arrays.npz").open("xb") as stream:
        np.savez(stream, **arrays)
        stream.flush()
        os.fsync(stream.fileno())
    files = {
        name: hashlib.sha256((path / name).read_bytes()).hexdigest()
        for name in ("data.json", "arrays.npz")
    }
    with (path / "manifest.json").open("x") as stream:
        json.dump(
            dict(kind="cells.betse_normal_current_raw_evidence@1", complete=True, files=files),
            stream,
            indent=2,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    for directory in (path, path.parent):
        descriptor = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Native current capture import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Native current import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Native capture loaded production/native packages")
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    write_archive(args.output, result)
    print(json.dumps(dict(status=result["status"], snapshots=len(result["history"]))))


if __name__ == "__main__":
    main()
