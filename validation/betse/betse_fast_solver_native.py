"""Authenticated isolated fast initializer/loop capture, without Cells imports.

Complete source numerical bodies execute under normalized phase/storage/logging
interfaces. Networks and voltage-sensitive junction hooks stay disabled. Initial
voltage and post-event packets are explicit inputs; full update_V is not run.
"""

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
import time
import traceback
import warnings
from enum import Enum
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

PROTOCOL = Path(__file__).with_name("betse_fast_solver_protocol.json")


class Phase(Enum):
    INIT = 1
    SIM = 2


class NativeUnstable(ValueError):
    pass


def _executable(node):
    node = copy.deepcopy(node)
    for item in ast.walk(node):
        if isinstance(item, ast.FunctionDef):
            item.decorator_list, item.returns = [], None
            for arg in (*item.args.posonlyargs, *item.args.args, *item.args.kwonlyargs):
                arg.annotation = None
    return node


def _wrapper(name, args, body):
    function = ast.parse("def " + name + "(" + args + "):\n pass\n").body[0]
    function.body = copy.deepcopy(body)
    return function


def capture(protocol=None):
    plan = json.loads(PROTOCOL.read_text()) if protocol is None else protocol
    native = plan["native_source"]
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", native["checkout"]))
    installed = Path(native["installed_package"]).parent
    trees = {}
    for name, expected in native["source_sha256"].items():
        raw = (root / name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError("Pinned checkout source changed: " + name)
        if hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned installed source changed: " + name)
        trees[name] = ast.parse(raw, filename=str(root / name))
    revision = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
    ).strip()
    if revision != native["revision"]:
        raise ValueError("Pinned source revision changed")

    def methods(path, class_name):
        cls = next(
            node
            for node in trees[path].body
            if isinstance(node, ast.ClassDef) and node.name == class_name
        )
        return {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}

    sim = methods("betse/science/sim.py", "Simulator")
    cells = methods("betse/science/cells.py", "Cells")
    toolbox = {
        node.name: node
        for node in trees["betse/science/sim_toolbox.py"].body
        if isinstance(node, ast.FunctionDef)
    }
    functions = [
        _executable(sim[name]) for name in ("fast_sim_init", "_run_fast_sim_core_loop", "get_ion")
    ]
    functions += [_executable(cells[name]) for name in ("div", "single_cell_div_free")]
    functions += [_executable(toolbox[name]) for name in ("ghk_calculator", "check_v")]
    source_sites = {
        node.name: dict(first_line=node.lineno, last_line=node.end_lineno) for node in functions
    }
    for name, method in (
        ("sigma_initial", sim["init_dynamics"]),
        ("sigma_after_update_V", sim["update_V"]),
    ):
        statements = [
            node
            for node in method.body
            if isinstance(node, ast.Assign)
            and any(ast.unparse(target) == "self.sigma_cell" for target in node.targets)
        ]
        if len(statements) != 1:
            raise ValueError("Conductivity overwrite source contract changed")
        functions.append(_wrapper(name, "self,p", statements))
        source_sites[name] = dict(
            first_line=statements[0].lineno, last_line=statements[0].end_lineno
        )
    matrix_method = next(
        node
        for node in cells.values()
        if any(
            isinstance(item, ast.Assign)
            and any(ast.unparse(target) == "self.M_sum_mems" for target in item.targets)
            for item in node.body
        )
    )
    first = next(
        i
        for i, node in enumerate(matrix_method.body)
        if isinstance(node, ast.Assign)
        and any(ast.unparse(target) == "self.M_sum_mems" for target in node.targets)
    )
    last = next(
        i
        for i, node in enumerate(matrix_method.body)
        if isinstance(node, ast.Assign)
        and any(
            ast.unparse(target) == "self.num_mems"
            and isinstance(node.value, ast.Call)
            and ast.unparse(node.value.func) == "np.asarray"
            for target in node.targets
        )
    )
    matrix = matrix_method.body[first : last + 1]
    functions.append(_wrapper("owner_matrices", "self", matrix))
    source_sites["owner_matrices"] = dict(
        first_line=matrix[0].lineno, last_line=matrix[-1].end_lineno
    )
    plot = sim["_plot_loop"]
    first = next(i for i, node in enumerate(plot.body) if isinstance(node, ast.If))
    last = next(i for i, node in enumerate(plot.body) if isinstance(node, ast.While))
    calendar = plot.body[first : last + 1]
    functions.append(
        _wrapper(
            "calendar", "phase", calendar + ast.parse("return time_steps,time_steps_sampled").body
        )
    )
    source_sites["calendar"] = dict(
        first_line=calendar[0].lineno, last_line=calendar[-1].end_lineno
    )
    counts = [
        node
        for node in ast.walk(trees["betse/science/parameters.py"])
        if isinstance(node, ast.Assign)
        and any(
            ast.unparse(target) in ("self.init_tsteps", "self.sim_tsteps")
            for target in node.targets
        )
    ]
    if len(counts) != 2:
        raise ValueError("Original phase count source changed")
    functions.append(_wrapper("duration_counts", "self", counts))
    source_sites["duration_counts"] = [
        dict(first_line=node.lineno, last_line=node.end_lineno) for node in counts
    ]
    namespace = dict(
        np=np,
        time=time,
        SimPhaseKind=Phase,
        BetseSimUnstableException=NativeUnstable,
        logs=SimpleNamespace(warning=lambda message: warnings.warn(message, stacklevel=2)),
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<authenticated BETSE fast solver sites>",
            "exec",
        ),
        namespace,
    )
    namespace["stb"] = SimpleNamespace(
        ghk_calculator=namespace["ghk_calculator"], check_v=namespace["check_v"]
    )
    return namespace, source_sites, native


def _state(sim):
    return copy.deepcopy({key: value for key, value in vars(sim).items() if not callable(value)})


def evaluate(inputs):
    source, sites, pins = capture()
    raw, calendar = inputs["definition"], inputs["calendar"]
    g, ions, constants = (raw[key] for key in ("geometry", "ions", "parameters"))
    owner, neighbor = np.asarray(g["owner"], np.int64), np.asarray(g["neighbor"], np.int64)
    n, m = len(g["cell_ids"]), len(owner)
    if (
        type(calendar["step_count"]) is not int
        or not 0 <= calendar["step_count"] <= 64
        or not 1 <= n <= 16
        or not 1 <= m <= 128
        or len(ions["ids"]) > 7
        or not np.isfinite(calendar["dt_s"])
        or calendar["dt_s"] <= 0
        or not np.isfinite(calendar["sample_stride"])
        or calendar["sample_stride"] < 1
    ):
        raise ValueError("Refuse unbounded/nonterminating isolated native microcase")
    p = SimpleNamespace(
        R=constants["R_J_mol_K"],
        F=constants["F_C_mol"],
        q=constants["q_C"],
        kb=constants["kb_J_K"],
        T=constants["configured_temperature_K"],
        cm=constants["capacitance_F_m2"],
        tm=constants["membrane_thickness_m"],
        cell_space=constants["gap_length_m"],
        gj_surface=constants["junction_surface_fraction"],
        is_ecm=constants["is_ecm"],
        molecules_enabled=False,
        grn_enabled=False,
        v_sensitive_gj=False,
        dt=calendar["dt_s"],
        ions_dict={name: 1 for name in ions["ids"]},
        init_tsteps=calendar["step_count"],
        sim_tsteps=calendar["step_count"],
        t_resample=calendar["sample_stride"],
    )
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        mem_to_cells=owner,
        cell_nn_i=np.column_stack((owner, neighbor)),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_sa=np.asarray(g["cell_area_m2"], np.float64),
        cell_vol=np.asarray(g["cell_volume_m3"], np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
        map_mem2ecm=np.asarray(g["environment_index"], np.int64),
        bflags_mems=np.flatnonzero(owner == neighbor),
        gj_default_weights=np.asarray(g["junction_weights"], np.float64),
    )
    source["owner_matrices"](cells)
    cells.div = MethodType(source["div"], cells)
    cells.single_cell_div_free = MethodType(source["single_cell_div_free"], cells)
    initial_drive = inputs["initial_drive"]
    sim = SimpleNamespace(
        cc_cells=np.asarray(ions["cell_mol_m3"], np.float64),
        cc_env=np.asarray(ions["environment_mol_m3"], np.float64),
        zs=np.asarray(ions["valence"], np.float64),
        D_free=np.asarray(ions["free_diffusion_m2_s"], np.float64),
        Dm_cells=np.asarray(ions["membrane_diffusion_m2_s"], np.float64),
        T=constants["temperature_K"],
        mdl=m,
        cdl=n,
        vm_ave=np.asarray(inputs["initial_voltage_V"], np.float64),
        extra_J_mem=np.asarray(initial_drive["extra_current_A_m2"], np.float64),
        gj_block=np.asarray(initial_drive["junction_block"], np.float64),
        fluxes_mem=np.ones((len(ions["ids"]), m)),
        fluxes_gj=np.ones((len(ions["ids"]), m)),
    )
    sim.vm = sim.vm_ave[owner].copy()
    for name in ("Na", "K", "Cl", "Ca", "M", "H", "P"):
        setattr(sim, "i" + name, ions["ids"].index(name) if name in ions["ids"] else [])
    sim.get_ion = MethodType(source["get_ion"], sim)
    for name in (
        "vm_time",
        "dd_time",
        "I_cell_x_time",
        "I_cell_y_time",
        "efield_gj_x_time",
        "efield_gj_y_time",
        "gjopen_time",
        "time",
        "vm_ave_time",
    ):
        setattr(sim, name, [])
    callbacks, events, history = [], [], []
    sim._log_solver_time_estimate = lambda **kwargs: callbacks.append("first_step_estimate")

    def fire_events(*, phase, t):
        packet = inputs["drives"][len(events)]
        events.append(float(t))
        sim.extra_J_mem = np.asarray(packet["extra_current_A_m2"], np.float64).copy()
        sim.gj_block = np.asarray(packet["junction_block"], np.float64).copy()
        if "permeability_m2_s" in packet:
            sim.Dm_cells = np.asarray(packet["permeability_m2_s"], np.float64).copy()
        if "temperature_K" in packet:
            sim.T = packet["temperature_K"]

    phase = SimpleNamespace(
        sim=sim,
        p=p,
        cells=cells,
        kind=Phase[calendar["phase"]],
        dyna=SimpleNamespace(fire_events=fire_events),
        callbacks=SimpleNamespace(progressed_next=lambda: callbacks.append("sample")),
    )
    requested = calendar.get("requested_duration_s")
    if requested is not None:
        p.init_time_total = p.sim_time_total = requested
        p.init_time_step = p.sim_time_step = p.dt
        source["duration_counts"](p)
        if p.init_tsteps != calendar["step_count"] or p.sim_tsteps != calendar["step_count"]:
            raise ValueError("Declared phase count differs from actual source duration truncation")
    labels, sampled = source["calendar"](phase)
    original_check = source["check_v"]

    def observed_check(voltage):
        index = len(history)
        history.append(
            dict(
                call_index=index,
                event_label_s=float(labels[index]),
                start_s=index * p.dt,
                end_s=(index + 1) * p.dt,
                state=_state(sim),
                corrected_divergence=cells.div(sim.Emx, sim.Emy, cbound=False),
            )
        )
        return original_check(voltage)

    source["stb"].check_v = observed_check
    before_rng = copy.deepcopy(np.random.get_state())
    status, failure, initial = "not_started", None, None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            source["sigma_initial"](sim, p)
            init_sigma = sim.sigma_cell.copy()
            source["fast_sim_init"](sim, cells, p)
            source["sigma_after_update_V"](sim, p)
            initial = _state(sim) | dict(init_dynamics_sigma=init_sigma)
            source["_run_fast_sim_core_loop"](sim, phase, labels, sampled, None)
            status = "source_completed"
        except Exception as error:
            status = "source_refused"
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    after_rng = np.random.get_state()
    rng_unchanged = (
        before_rng[0] == after_rng[0]
        and np.array_equal(before_rng[1], after_rng[1])
        and before_rng[2:] == after_rng[2:]
    )
    return dict(
        status=status,
        inputs=inputs,
        initial=initial,
        history=history,
        final_state=_state(sim),
        failure=failure,
        warnings=[str(warning.message) for warning in caught],
        source_sites=sites,
        native_source=pins,
        source_revision=pins["revision"],
        labels_s=labels,
        sampled_s=sorted(sampled),
        event_call_labels_s=events,
        callbacks=callbacks,
        RNG_before=before_rng,
        RNG_after=after_rng,
        RNG_unchanged=rng_unchanged,
        runtime=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
        ),
        scope=(
            "Authenticated circuit/initializer sites; normalized lifecycle and supplied "
            "voltage/current; networks and gate callbacks disabled"
        ),
    )


def write_archive(directory, payload):
    """Complete typed arrays, including refused NaNs/infinities and scalar bits."""
    path = Path(directory)
    path.mkdir(parents=True, exist_ok=False)
    arrays = {}

    def encode(value):
        if isinstance(value, (np.ndarray, np.generic)):
            a = np.asarray(value)
            if a.dtype.kind not in "biuf":
                raise ValueError("Refuse object/opaque numeric evidence")
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
        raise ValueError("Unsupported raw native evidence: " + type(value).__name__)

    tree = encode(payload)
    with (path / "data.json").open("x") as handle:
        json.dump(tree, handle, indent=2, allow_nan=False)
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
    with (path / "arrays.npz").open("xb") as handle:
        np.savez(handle, **arrays)
        handle.flush()
        os.fsync(handle.fileno())
    files = {
        name: hashlib.sha256((path / name).read_bytes()).hexdigest()
        for name in ("data.json", "arrays.npz")
    }
    with (path / "manifest.json").open("x") as handle:
        json.dump(
            dict(kind="cells.betse_fast_solver_raw_evidence@1", complete=True, files=files),
            handle,
            indent=2,
        )
        handle.write("\n")
        handle.flush()
        os.fsync(handle.fileno())
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
    blocked = {"cells", "jax", "jaxlib", "betse"}
    original_import = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Production/native package import denied: " + name)
        return original_import(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Isolated native import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    record = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Isolated source capture loaded production/native packages")
    record["production_imports_denied"] = True
    record["loaded_production_modules"] = loaded
    write_archive(args.output, record)
    print(
        json.dumps(
            dict(status=record["status"], archive=str(args.output), steps=len(record["history"]))
        )
    )


if __name__ == "__main__":
    main()
