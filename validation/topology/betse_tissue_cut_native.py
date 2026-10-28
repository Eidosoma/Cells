"""Execute authenticated native cut and rebuild bodies on small polygons.

Native Voronoi seeding, profiles, mechanics and whole simulations are excluded.
The profile callback is recorded; geometry/contact/field/diffusion/DEC bodies
execute directly. No production Cells or JAX modules are imported by this child.
"""

import argparse
import ast
import copy
import hashlib
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Tuple

import numpy as np
from scipy import interpolate as interp
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from validation.topology.betse_tissue_cut_fixtures import cases, geometry

PROTOCOL = Path(__file__).with_name("betse_tissue_cut_protocol.json")


def serial(value):
    if isinstance(value, np.ndarray):
        return serial(value.tolist())
    if isinstance(value, (list, tuple)):
        return [serial(v) for v in value]
    if isinstance(value, dict):
        return {k: serial(v) for k, v in value.items()}
    if isinstance(value, np.generic):
        return serial(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def write(path, record):
    path.write_text(json.dumps(serial(record), indent=2, allow_nan=False) + "\n")


def load_class(path, original_name, methods, namespace, trace, prefix):
    tree = ast.parse(path.read_text())
    original = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == original_name)
    body = [
        copy.deepcopy(n)
        for n in original.body
        if isinstance(n, ast.FunctionDef) and n.name in methods
    ]
    assert {n.name for n in body} == set(methods)
    lines = {}
    for method in body:
        method.decorator_list = []
        lines[method.name] = dict(first_line=method.lineno, last_line=method.end_lineno)
    cls = ast.ClassDef(
        name="Captured" + original_name, bases=[], keywords=[], body=body, decorator_list=[]
    )
    module = ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[]))
    exec(compile(module, str(path), "exec"), namespace)
    captured = namespace[cls.name]

    def recorded(fn, label):
        def invoke(self, *args, **kwargs):
            trace.append(label)
            return fn(self, *args, **kwargs)

        return invoke

    for name in methods:
        setattr(captured, name, recorded(getattr(captured, name), prefix + "." + name))
    return captured, lines


def topology(cells, ids):
    membrane_ids, counts = [], dict.fromkeys(ids, 0)
    for owner in cells.mem_to_cells:
        cell = ids[int(owner)]
        membrane_ids.append(f"{cell}:m{counts[cell]}")
        counts[cell] += 1
    pairs = [(i, int(j)) for i, j in enumerate(cells.nn_i) if i < j]
    edge_ids = [f"contact:{membrane_ids[i]}|{membrane_ids[j]}" for i, j in pairs]
    edge_cells = [[int(cells.mem_to_cells[i]), int(cells.mem_to_cells[j])] for i, j in pairs]
    edge_membranes = [list(pair) for pair in pairs]
    contact = [True] * len(pairs)
    for a, b in cells.mesh.tri_edges:
        edge_ids.append(f"field:{ids[int(a)]}>{ids[int(b)]}")
        edge_cells.append([int(a), int(b)])
        edge_membranes.append([-1, -1])
        contact.append(False)
    return dict(
        cell_ids=list(ids),
        membrane_ids=membrane_ids,
        edge_ids=edge_ids,
        environment_ids=[f"env:{i}" for i in range(len(cells.xypts))],
        membrane_cell=cells.mem_to_cells,
        membrane_environment=cells.map_mem2ecm,
        edge_cells=np.asarray(edge_cells, int).reshape(-1, 2),
        edge_membranes=np.asarray(edge_membranes, int).reshape(-1, 2),
        edge_is_contact=np.array(contact, bool),
    )


def snapshot(cells, sim, ids=None):
    cfields = (
        "cell_centres",
        "cell_vol",
        "cell_sa",
        "mem_to_cells",
        "mem_mids_flat",
        "mem_edges_flat",
        "mem_sa",
        "nn_i",
        "cell_nn_i",
        "true_ecm_vol",
        "map_cell2ecm",
        "map_mem2ecm",
        "M_sum_mems",
        "M_divmap_mem2ecm",
        "lapGJ",
        "lapGJinv",
        "gj_default_weights",
    )
    sfields = (
        "cc_cells",
        "cc_env",
        "Dm_cells",
        "vm",
        "mem_gate",
        "hurt_mask",
        "D_env",
        "D_env_weight",
        "conc_J_x",
        "conc_J_y",
        "TJ_modulator",
        "global_marker",
        "witness_list",
        "equal_length_global",
        "unknown_nested",
    )
    result = dict(
        cells={k: getattr(cells, k).copy() for k in cfields if hasattr(cells, k)},
        sim={k: copy.deepcopy(getattr(sim, k)) for k in sfields if hasattr(sim, k)},
        mesh={
            k: copy.deepcopy(getattr(cells.mesh, k))
            for k in ("tri_verts", "tri_edges", "tri_cells", "tri_mids", "delta_tri_0")
            if hasattr(cells.mesh, k)
        },
    )
    if ids is not None:
        result["topology"] = topology(cells, ids)
    return result


def seed(classes, tb, raw, trace):
    cells, mesh, sim, handler = (
        classes[name]() for name in ("Cells", "DECMesh", "Simulator", "TissueHandler")
    )
    g = raw["geometry"]
    p = SimpleNamespace(
        **{k: g[k] for k in ("scale_cell", "cell_space", "cell_radius", "cell_height", "tm")},
        is_ecm=True,
        Ca_dyn=False,
        v_sensitive_gj=False,
        molecules_enabled=False,
        grn_enabled=False,
        fluid_flow=False,
        deformation=False,
        break_TJ=False,
        solver_type=object(),
        plot_grid_size=8,
        er=80.0,
        D_adh=0.5,
        D_tj=0.1,
    )
    cells.cell_centres = np.asarray(g["centres_m"], float)
    cells.ecm_verts = np.asarray([np.asarray(v, float) for v in g["polygons_m"]], dtype=object)
    cells.ecm_verts_unique = np.unique(np.vstack(list(cells.ecm_verts)), axis=0)
    for name in (
        "cellVerts",
        "cellMatrices",
        "intra_updater",
        "cell_vols",
        "mem_processing",
        "near_neigh",
        "calc_gj_vects",
    ):
        getattr(cells, name)(p)
    mesh.tri_verts = cells.cell_centres.copy()
    mesh.tri_edges = np.array([[0, 1], [1, 2], [2, 0]], int)
    mesh.tri_cells = np.array([[0, 1, 2]], dtype=object)
    mesh.tcell_verts = mesh.tri_verts[np.array([[0, 1, 2]])]
    mesh.tri_mids = mesh.tri_verts[mesh.tri_edges].mean(axis=1)
    mesh.tri_edge_len = np.linalg.norm(
        np.diff(mesh.tri_verts[mesh.tri_edges], axis=1)[:, 0], axis=1
    )
    mesh.tri_tang = (
        np.diff(mesh.tri_verts[mesh.tri_edges], axis=1)[:, 0] / mesh.tri_edge_len[:, None]
    )
    mesh.tri_ccents = np.array([mesh.tri_verts.mean(axis=0)])
    mesh.tri_cents = mesh.tri_ccents.copy()
    mesh.tri_rcircs = np.ones(1) * g["cell_radius"]
    mesh.tri_sa = np.array([tb.area(mesh.tri_verts)])
    mesh.vor_sa = np.array([tb.area(poly) for poly in cells.ecm_verts])
    mesh.vor_edge_len = np.ones(3) * g["cell_radius"]
    mesh.n_tverts, mesh.n_tedges, mesh.n_tcell = 3, 3, 1
    mesh.tri_edge_i, mesh.tri_vert_i, mesh.tri_cell_i = np.arange(3), np.arange(3), np.arange(1)
    mesh.create_tri_map()
    mesh.create_mappings(ignoreb=True)
    mesh.create_core_operators()
    cells.mesh = mesh
    axis = np.linspace(g["grid_min_m"], g["grid_max_m"], g["grid_count"])
    cells.X, cells.Y = np.meshgrid(axis, axis)
    cells.xypts = np.column_stack((cells.X.ravel(), cells.Y.ravel()))
    cells.delta = axis[1] - axis[0]
    cells.xmin = cells.ymin = g["grid_min_m"]
    cells.xmax = cells.ymax = g["grid_max_m"]
    cells.environment(p)
    cells.make_maskM(p)
    cells.graphLaplacian(p)
    handler.tissue_name_to_profile = {}
    handler.init_profiles = lambda phase: trace.append("hook.init_profiles")
    phase = SimpleNamespace(cells=cells, sim=sim, p=p, dyna=handler)
    cells.redo_gj(phase)
    sim.cdl, sim.mdl, sim.edl = 3, len(cells.mem_i), len(cells.xypts)
    sim.cc_cells = np.array([[10.0, 20.0, 30.0], [40.0, 50.0, 60.0]])
    sim.cc_env = np.ones((2, sim.edl)) * np.array([[2.0], [3.0]])
    sim.Dm_cells = np.arange(2 * sim.mdl, dtype=float).reshape(2, sim.mdl) * 1e-20
    sim.vm, sim.mem_gate = np.array([0.01, 0.02, 0.03]), np.linspace(0.2, 0.8, sim.mdl)
    sim.D_free, sim.Dtj_rel, sim.iNa = np.array([1e-9, 2e-9]), np.array([1.0, 0.75]), 0
    sim.D_env = np.zeros((2, sim.edl))
    sim.initDenv(cells, p)
    sim.D_env_weight *= 0.3
    sim.conc_J_x, sim.conc_J_y = np.ones(sim.edl) * 7, np.ones(sim.edl) * -8
    sim.global_marker, sim.endo_retic, sim.gj_funk = (
        np.array([101.0, 102.0, 103.0, 104.0]),
        None,
        None,
    )
    trace.clear()
    return phase


def execute_cut(phase, raw, ids):
    selected = np.array([ids.index(name) for name in raw["remove_cell_ids"]], int)
    membranes = np.flatnonzero(np.isin(phase.cells.mem_to_cells, selected))
    picker = SimpleNamespace(pick_cells_and_mems=lambda **_: (selected, membranes))
    phase.dyna._cut_cells(phase=phase, tissue_picker=picker)
    return [name for name in ids if name not in raw["remove_cell_ids"]]


def capture(output):
    output.mkdir(parents=True, exist_ok=False)
    protocol = json.loads(PROTOCOL.read_text())
    source = protocol["native_source"]
    installed, checkout = Path(source["installed_package"]).parent, Path(source["checkout"])
    manifest = dict(
        status="capturing",
        files={},
        methods={},
        cases=[],
        limits=[],
        recorded_hooks=["init_profiles"],
        scope=source["scope"],
        native_simulation=False,
    )
    write(output / "source-manifest.json", manifest)
    revision = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    assert revision == source["revision"]
    manifest["revision"] = revision
    for relative, expected in source["source_sha256"].items():
        data = (installed / relative).read_bytes()
        dest = output / "upstream" / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(installed / relative, dest)
        actual = hashlib.sha256(data).hexdigest()
        manifest["files"][relative] = dict(
            sha256=actual, checkout_match=data == (checkout / relative).read_bytes()
        )
        write(output / "source-manifest.json", manifest)
        assert actual == expected and manifest["files"][relative]["checkout_match"]
    metadata = ast.parse((installed / "betse/metadata.py").read_text())
    manifest["version"] = next(
        ast.literal_eval(n.value)
        for n in metadata.body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "VERSION" for t in n.targets)
    )
    assert manifest["version"] == source["version"]
    trace = []
    logs = SimpleNamespace(log_info=lambda *_: None, log_debug=lambda *_: None)
    tools_tree = ast.parse((installed / "betse/science/math/toolbox.py").read_text())
    tools_methods = [
        copy.deepcopy(n)
        for n in tools_tree.body
        if isinstance(n, ast.FunctionDef) and n.name in ("flatten", "area")
    ]
    for n in tools_methods:
        n.decorator_list = []
    tools_ns = dict(np=np, math=math, copy=copy, SequenceTypes=object)
    exec(
        compile(
            ast.Module(body=tools_methods, type_ignores=[]),
            str(installed / "betse/science/math/toolbox.py"),
            "exec",
        ),
        tools_ns,
    )
    tb = SimpleNamespace(**{n.name: tools_ns[n.name] for n in tools_methods})
    common = dict(
        np=np,
        array=np.array,
        ndarray=np.ndarray,
        Tuple=Tuple,
        math=math,
        copy=copy,
        tb=tb,
        cKDTree=cKDTree,
        logs=logs,
        interp=interp,
        gaussian_filter=gaussian_filter,
        SimPhase=object,
        TissuePickerABC=object,
        SolverType=SimpleNamespace(FAST=object()),
    )
    selections = {
        "Cells": (
            "betse/science/cells.py",
            [
                "cellVerts",
                "cellMatrices",
                "intra_updater",
                "cell_vols",
                "mem_processing",
                "near_neigh",
                "calc_gj_vects",
                "environment",
                "make_maskM",
                "graphLaplacian",
                "redo_gj",
            ],
        ),
        "DECMesh": (
            "betse/science/math/mesh.py",
            ["cut_mesh", "create_tri_map", "create_mappings", "create_core_operators"],
        ),
        "TissueHandler": ("betse/science/tissue/tishandler.py", ["_cut_cells"]),
        "Simulator": ("betse/science/sim.py", ["initDenv"]),
    }
    classes = {}
    for name, (relative, methods) in selections.items():
        cls, lines = load_class(installed / relative, name, methods, common.copy(), trace, name)
        classes[name] = cls
        manifest["methods"][relative] = lines
    for raw in cases():
        phase = seed(classes, tb, raw, trace)
        ids = raw["geometry"]["cell_ids"]
        before = snapshot(phase.cells, phase.sim, ids)
        path = output / (raw["name"] + ".json")
        record = dict(status="prepared", input=raw, before=before)
        write(path, record)
        remaining = execute_cut(phase, raw, ids)
        after = snapshot(phase.cells, phase.sim, remaining)
        record.update(
            status="passed",
            after=after,
            call_trace=list(trace),
            targets_dec_edges=phase.dyna.targets_dec_edges,
            targets_dec_tcells=phase.dyna.targets_dec_tcells,
            targets_wound_membranes=phase.dyna.targets_vgWound,
        )
        write(path, record)
        assert phase.sim.cdl == 2
        assert np.all(phase.sim.conc_J_x == 0) and np.all(phase.sim.conc_J_y == 0)
        assert (
            "Cells.environment" in trace
            and "Simulator.initDenv" in trace
            and "DECMesh.cut_mesh" in trace
        )
        manifest["cases"].append(dict(name=raw["name"], path=str(path), status="passed"))
    limits = [
        ("empty-selection", []),
        ("complete-removal", ["A", "B", "C"]),
        ("single-survivor", ["A", "B"]),
        ("list-middle-tail", ["B"]),
        ("list-last-index", ["C"]),
        ("equal-length-global", ["B"]),
        ("unknown-nested-owner", ["B"]),
    ]
    for label, removed in limits:
        raw = dict(name=label, geometry=geometry(), remove_cell_ids=removed)
        phase = seed(classes, tb, raw, trace)
        if label.startswith("list-"):
            phase.sim.witness_list = [10.0, 20.0, 30.0]
        if label == "equal-length-global":
            phase.sim.equal_length_global = np.array([111.0, 222.0, 333.0])
        if label == "unknown-nested-owner":
            phase.sim.unknown_nested = np.arange(6.0, dtype=float).reshape(2, 3)
        before = snapshot(phase.cells, phase.sim)
        failure = None
        try:
            execute_cut(phase, raw, raw["geometry"]["cell_ids"])
        except (ValueError, IndexError, TypeError, ZeroDivisionError) as error:
            failure = dict(type=type(error).__name__, message=str(error))
        if label in ("empty-selection", "complete-removal", "single-survivor", "list-last-index"):
            assert failure is not None
        elif label == "list-middle-tail":
            assert phase.sim.witness_list == [30.0]
        elif label == "equal-length-global":
            np.testing.assert_array_equal(phase.sim.equal_length_global, [111.0, 333.0])
        elif label == "unknown-nested-owner":
            assert phase.sim.unknown_nested.shape == (2, 3) and phase.sim.cdl == 2
        record = dict(
            status="observed_native_limit",
            input=raw,
            before=before,
            after=snapshot(phase.cells, phase.sim),
            failure=failure,
            call_trace=list(trace),
        )
        write(output / (label + ".json"), record)
        manifest["limits"].append(label)
    assert not any(
        name == "cells" or name.startswith("cells.") or name == "jax" or name.startswith("jax.")
        for name in sys.modules
    )
    manifest.update(
        status="passed",
        no_production_or_jax_imports=True,
        successful_cases=len(manifest["cases"]),
        observed_native_limits=len(manifest["limits"]),
    )
    write(output / "source-manifest.json", manifest)
    print(
        json.dumps(
            dict(
                status="passed",
                native_cases=manifest["successful_cases"],
                native_limits=manifest["observed_native_limits"],
            )
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        capture(args.output)
    except Exception as error:
        if args.output.is_dir():
            write(args.output / "failure.json", dict(type=type(error).__name__, message=str(error)))
        raise
