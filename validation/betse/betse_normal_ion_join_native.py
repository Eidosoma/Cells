"""Authenticate and execute the actual no-ECM normal ion/material source join.

The selected loop statements and complete called functions are unchanged
numerically. Read-only observations copy the actual simulator state. Disabled
pump/event/network/field blocks are excluded explicitly, not simulated here.
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
import subprocess
import sys
import traceback
import warnings
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse.betse_normal_current_native import write_archive

PROTOCOL = Path(__file__).with_name("betse_normal_ion_join_protocol.json")


class NativeUnstable(ValueError):
    pass


def wrapper(name, args, body):
    node = ast.parse("def " + name + "(" + args + "):\n pass\n").body[0]
    node.body = copy.deepcopy(body)
    return node


def observation(stage, ion="i"):
    return ast.parse("_observe('" + stage + "'," + ion + ",self)").body


def capture():
    native = json.loads(PROTOCOL.read_text())["native_source"]
    base = Path(native["checkout"])
    installed = Path(native["installed_package"]).parent
    trees = {}
    for name, expected in native["source_sha256"].items():
        raw = (base / name).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != expected
            or hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Pinned normal-ion source changed: " + name)
        trees[name] = ast.parse(raw, filename=str(base / name))
    if (
        subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip()
        != native["revision"]
    ):
        raise ValueError("Pinned native revision changed")
    sim_cls = next(
        node
        for node in trees["betse/science/sim.py"].body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    )
    methods = {node.name: node for node in sim_cls.body if isinstance(node, ast.FunctionDef)}
    toolbox = {
        node.name: node
        for node in trees["betse/science/sim_toolbox.py"].body
        if isinstance(node, ast.FunctionDef)
    }
    functions = [
        copy.deepcopy(methods[name]) for name in ("update_gj", "update_intra", "update_all_concs")
    ]
    functions.extend(
        copy.deepcopy(toolbox[name]) for name in ("electroflux", "update_Co", "no_negs")
    )
    sites = {
        node.name: dict(
            first_line=node.lineno,
            last_line=node.end_lineno,
            AST_sha256=hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest(),
        )
        for node in functions
    }
    loop = methods["_run_sim_core_loop"]
    moving = [
        node
        for node in ast.walk(loop)
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "self.movingIons"
    ]
    resets = sorted(
        (
            node
            for node in ast.walk(loop)
            if isinstance(node, ast.Expr)
            and ast.unparse(node) in ("self.fluxes_mem.fill(0)", "self.fluxes_gj.fill(0)")
        ),
        key=lambda node: node.lineno,
    )
    commit = [
        node
        for node in ast.walk(loop)
        if isinstance(node, ast.Expr) and ast.unparse(node) == "self.update_all_concs(cells, p)"
    ]
    if len(moving) != 1 or len(resets) != 2 or len(commit) != 1:
        raise ValueError("Native normal-loop selector changed")
    selected = resets + moving + commit
    sites["scoped_step"] = dict(
        selected_lines=[node.lineno for node in selected],
        AST_sha256=hashlib.sha256(
            ast.dump(ast.Module(body=selected, type_ignores=[]), include_attributes=False).encode()
        ).hexdigest(),
    )
    scoped = wrapper("scoped_step", "self,cells,p,t", selected)
    scoped.body[2:2] = observation("reset_flux", "None")
    moving_copy = next(node for node in scoped.body if isinstance(node, ast.For))
    traced = []
    for node in moving_copy.body:
        traced.append(node)
        if isinstance(node, ast.AugAssign) and ast.unparse(node.target) == "self.fluxes_mem[i]":
            traced.extend(observation("membrane_flux"))
        if isinstance(node, ast.Expr) and ast.unparse(node) == "self.update_gj(cells, p, t, i)":
            traced.extend(observation("junction_flux"))
        if isinstance(node, ast.Expr) and ast.unparse(node) == "self.update_intra(cells, p, i)":
            traced.extend(observation("refresh_at_mem"))
    moving_copy.body = traced
    update = next(node for node in functions if node.name == "update_all_concs")
    commit_loop = next(node for node in update.body if isinstance(node, ast.For))
    traced = []
    for node in commit_loop.body:
        traced.append(node)
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Tuple):
            traced.extend(observation("membrane_commit"))
        if isinstance(node, ast.AugAssign) and ast.unparse(node.target) == "self.cc_cells[i]":
            traced.extend(observation("junction_commit"))
        if isinstance(node, ast.Expr) and ast.unparse(node) == "stb.no_negs(self.cc_cells[i])":
            traced.extend(observation("clip_bulk"))
    commit_loop.body = traced
    cls = next(
        node
        for node in trees["betse/science/cells.py"].body
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    matrix = next(
        node
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name == "cellMatrices"
    )
    start = next(
        i
        for i, node in enumerate(matrix.body)
        if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "self.M_sum_mems"
    )
    stop = next(
        i
        for i, node in enumerate(matrix.body)
        if isinstance(node, ast.Assign)
        and ast.unparse(node.targets[0]) == "self.num_mems"
        and isinstance(node.value, ast.Call)
        and ast.unparse(node.value.func) == "np.asarray"
    )
    owner = matrix.body[start : stop + 1]
    sites["owner_matrices"] = dict(first_line=owner[0].lineno, last_line=owner[-1].end_lineno)
    functions += [scoped, wrapper("owner_matrices", "self", owner)]
    namespace = {"np": np, "BetseSimUnstableException": NativeUnstable}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=functions, type_ignores=[])),
            "<pinned native no-ECM normal ion join>",
            "exec",
        ),
        namespace,
    )
    namespace["stb"] = SimpleNamespace(
        **{name: namespace[name] for name in ("electroflux", "update_Co", "no_negs")}
    )
    return namespace, sites, native


def values(sim):
    return dict(
        cell_mol_m3=sim.cc_cells.copy(),
        membrane_mol_m3=sim.cc_at_mem.copy(),
        bath_mol_m3=sim.cc_env.copy(),
        voltage_V=sim.vm.copy(),
        membrane_flux_mol_m2_s=sim.fluxes_mem.copy(),
        junction_flux_mol_m2_s=sim.fluxes_gj.copy(),
        junction_voltage_V=sim.vgj.copy(),
        junction_field_V_m=sim.Egj.copy(),
        junction_field_xy_V_m=np.column_stack((sim.E_gj_x, sim.E_gj_y)),
        gap_open=sim.gjopen.copy(),
    )


def evaluate(inputs):
    source, sites, pins = capture()
    raw, initial = inputs["definition"], inputs["initial"]
    g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
    n, m, count = len(g["cell_ids"]), len(g["owner"]), len(ions["ids"])
    if (
        not 1 <= n <= 16
        or not 1 <= m <= 128
        or not 1 <= count <= 32
        or not 1 <= len(inputs["steps"]) <= 32
    ):
        raise ValueError("Refuse unbounded native ion/material microcase")
    if p["is_ecm"] is not False or p["v_sensitive_gj"] is not False:
        raise ValueError("Capture scope requires no ECM and disabled voltage-sensitive callbacks")
    owner = np.asarray(g["owner"], np.int64)
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=owner,
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        nn_i=np.asarray(g["partner"], np.int64),
        bflags_mems=np.asarray(g["boundary"], bool),
        mem_sa=np.asarray(g["membrane_area_m2"], np.float64),
        cell_vol=np.asarray(g["cell_volume_m3"], np.float64),
        gj_len=np.asarray(g["gap_length_m"], np.float64),
        gj_default_weights=np.asarray(g["gap_weights"], np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), g["normal_xy"])),
    )
    source["owner_matrices"](cells)
    sim = SimpleNamespace(
        mdl=m,
        movingIons=[ions["ids"].index(name) for name in ions["moving_ids"]],
        zs=np.asarray(ions["valence"], np.float64),
        Dm_cells=np.asarray(ions["membrane_diffusion_m2_s"], np.float64),
        D_gj=np.asarray(ions["gap_diffusion_m2_s"], np.float64),
        rho_channel=np.ones(m),
    )
    for key, attr in (
        ("cell_mol_m3", "cc_cells"),
        ("membrane_mol_m3", "cc_at_mem"),
        ("bath_mol_m3", "cc_env"),
        ("voltage_V", "vm"),
        ("membrane_flux_mol_m2_s", "fluxes_mem"),
        ("junction_flux_mol_m2_s", "fluxes_gj"),
        ("junction_voltage_V", "vgj"),
        ("junction_field_V_m", "Egj"),
        ("gap_open", "gjopen"),
    ):
        setattr(sim, attr, np.asarray(initial[key], np.float64).copy())
    sim.E_gj_x, sim.E_gj_y = (
        np.asarray(initial["junction_field_xy_V_m"], np.float64)[:, i].copy() for i in (0, 1)
    )
    for name in ("update_gj", "update_intra", "update_all_concs"):
        setattr(sim, name, MethodType(source[name], sim))
    parameters = SimpleNamespace(
        F=p["F_C_mol"],
        R=p["R_J_mol_K"],
        T=p["configured_temperature_K"],
        tm=p["membrane_thickness_m"],
        gj_surface=p["junction_surface_fraction"],
        vol_env=p["bath_volume_m3"],
        cluster_open=p["cluster_open"],
        is_ecm=False,
        v_sensitive_gj=False,
    )
    before = copy.deepcopy(np.random.get_state())
    frames = []
    source["_observe"] = lambda stage, i, actual: frames.append(
        dict(stage=stage, ion_id=None if i is None else ions["ids"][i], values=values(actual))
    )
    history = []
    failure = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for index, forcing in enumerate(inputs["steps"]):
            parameters.dt = forcing["dt_s"]
            sim.T = forcing["runtime_temperature_K"]
            sim.gj_block = np.asarray(forcing["junction_block"], np.float64)
            frames.clear()
            source["_observe"]("initial", None, sim)
            try:
                source["scoped_step"](sim, cells, parameters, float(index))
            except Exception as error:
                failure = dict(
                    type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                    step_index=index + 1,
                )
            history.append(
                dict(
                    step_index=index + 1,
                    drive=forcing,
                    frames=copy.deepcopy(frames),
                    final_state=values(sim),
                    failure=failure,
                )
            )
            if failure:
                break
    after = np.random.get_state()
    return dict(
        kind="cells.native_normal_ion_join_capture@1",
        status="source_refused" if failure else "source_completed",
        inputs=inputs,
        history=history,
        final_state=values(sim),
        raw_simulator_state=copy.deepcopy(
            {key: value for key, value in vars(sim).items() if not callable(value)}
        ),
        source_parameters=vars(parameters),
        source_geometry=vars(cells),
        failure=failure,
        warnings=[str(w.message) for w in caught],
        native_source=pins,
        source_sites=sites,
        RNG_before=before,
        RNG_after=after,
        RNG_unchanged=before[0] == after[0]
        and np.array_equal(before[1], after[1])
        and before[2:] == after[2:],
        runtime=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
        ),
        scope=(
            "Actual normal moving-ion loop and final material commit only; "
            "no ECM/pumps/events/networks/voltage feedback"
        ),
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *values, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Native ion capture import denied: " + name)
        return original(name, *values, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Native import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Native capture loaded production modules")
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    write_archive(args.output, result)
    print(json.dumps(dict(status=result["status"], carried_calls=len(result["history"]))))


if __name__ == "__main__":
    main()
