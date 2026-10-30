"""Unchanged native ECM moving-ion/material statements with read-only tracing.

Pump and late flux arrays are explicit adapter input seams applied outside the
captured native statements. Pump/gate/handler/field/voltage callbacks do not run.
"""

import ast
import copy
import hashlib
import json
import os
import sys
import traceback
import warnings
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse import betse_environment_field_native as geometry_native

PROTOCOL = Path(__file__).with_name("betse_ecm_transport_protocol.json")


class NativeUnstable(ValueError):
    pass


def capture():
    geometry_code, geometry_sites, pins = geometry_native.capture()
    declared = json.loads(PROTOCOL.read_text())["native_source"]
    assert declared == pins
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", pins["checkout"]))
    sim_tree = ast.parse((root / "betse/science/sim.py").read_bytes())
    tb_tree = ast.parse((root / "betse/science/sim_toolbox.py").read_bytes())
    fd_tree = ast.parse((root / "betse/science/math/finitediff.py").read_bytes())
    cls = next(
        node
        for node in sim_tree.body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    )
    methods = {node.name: node for node in cls.body if isinstance(node, ast.FunctionDef)}
    toolbox = {node.name: node for node in tb_tree.body if isinstance(node, ast.FunctionDef)}
    fd = {node.name: node for node in fd_tree.body if isinstance(node, ast.FunctionDef)}
    time_loop = next(
        node for node in methods["_run_sim_core_loop"].body if isinstance(node, ast.For)
    )
    moving = [
        node
        for node in time_loop.body
        if isinstance(node, ast.For) and ast.unparse(node.iter) == "self.movingIons"
    ]
    resets = [
        node
        for node in time_loop.body
        if isinstance(node, ast.Expr)
        and ast.unparse(node) in ("self.fluxes_mem.fill(0)", "self.fluxes_gj.fill(0)")
    ]
    ecm_reset = [
        node
        for node in time_loop.body
        if isinstance(node, ast.If) and ast.unparse(node.test) == "p.is_ecm"
    ]
    assert len(moving) == 1 and len(resets) == 2 and len(ecm_reset) == 1
    assert [ast.unparse(node.targets[0]) for node in ecm_reset[0].body] == [
        "self.fluxes_env_x",
        "self.fluxes_env_y",
    ]
    blocks = dict(resets=resets + ecm_reset, ordered=moving)
    functions = [
        geometry_native.wrapper(name, "self,cells,p,t", nodes) for name, nodes in blocks.items()
    ]
    originals = [
        methods[name] for name in ("update_gj", "update_ecm", "update_intra", "update_all_concs")
    ]
    originals += [
        toolbox[name]
        for name in ("electroflux", "nernst_planck_flux", "update_Co", "div_env", "no_negs")
    ]
    originals += [fd[name] for name in ("gradient", "diff", "divergence", "integrator")]
    namespace = dict(np=np, BetseSimUnstableException=NativeUnstable)
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=functions + copy.deepcopy(originals), type_ignores=[])
            ),
            "<pinned native ECM material>",
            "exec",
        ),
        namespace,
    )
    namespace["fd"] = SimpleNamespace(
        **{name: namespace[name] for name in ("gradient", "diff", "divergence", "integrator")}
    )
    namespace["stb"] = SimpleNamespace(
        **{
            name: namespace[name]
            for name in ("electroflux", "nernst_planck_flux", "update_Co", "div_env", "no_negs")
        }
    )
    sites = {
        node.name: dict(
            lines=[[node.lineno, node.end_lineno]],
            ast_sha256=hashlib.sha256(
                ast.dump(node, include_attributes=False).encode()
            ).hexdigest(),
        )
        for node in originals
    }
    sites.update(
        {
            name: dict(
                lines=[[node.lineno, node.end_lineno] for node in nodes],
                ast_sha256=hashlib.sha256(
                    ast.dump(
                        ast.Module(body=nodes, type_ignores=[]), include_attributes=False
                    ).encode()
                ).hexdigest(),
            )
            for name, nodes in blocks.items()
        }
    )
    material_loop = next(
        node for node in methods["update_all_concs"].body if isinstance(node, ast.For)
    )
    lines = dict(
        membrane_flux=next(
            node.lineno
            for node in moving[0].body
            if isinstance(node, ast.Expr) and ast.unparse(node) == "self.update_gj(cells, p, t, i)"
        ),
        membrane_commit=next(
            node.lineno
            for node in material_loop.body
            if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) == "delta_cgj"
        ),
        junction_commit=next(
            node.lineno
            for node in material_loop.body
            if isinstance(node, ast.Expr) and ast.unparse(node) == "stb.no_negs(self.cc_cells[i])"
        ),
    )
    return namespace, geometry_code, sites, geometry_sites, pins, lines


def evaluate(inputs):
    source, geometry_code, sites, geometry_sites, pins, lines = capture()
    raw = inputs["definition"]
    external, jg, ions, supplied = (
        raw[key]
        for key in ("environment_geometry_definition", "junction_geometry", "ions", "parameters")
    )
    cg, cd, p = (
        external["current_definition"]["geometry"],
        external["current_definition"],
        external["parameters"],
    )
    names = cd["ions"]["ids"]
    n, m, s = len(cg["cell_ids"]), len(cg["membrane_ids"]), len(names)
    if (
        not 1 <= n <= 16
        or not 1 <= m <= 128
        or not 1 <= s <= 32
        or not 1 <= len(inputs["steps"]) <= 3
    ):
        raise ValueError("Refuse unbounded native ECM material inputs")
    owner = np.asarray(cg["owner"], dtype=np.int64)
    cells = SimpleNamespace(
        cell_i=np.arange(n),
        mem_i=np.arange(m),
        mem_to_cells=owner,
        cell_to_mems=[np.flatnonzero(owner == i).tolist() for i in range(n)],
        nn_i=np.asarray(jg["partner"], dtype=np.int64),
        bflags_mems=np.asarray(jg["boundary"], dtype=bool),
        gj_len=np.asarray(jg["gap_length_m"], dtype=np.float64),
        gj_default_weights=np.asarray(jg["gap_weights"], dtype=np.float64),
        mem_sa=np.asarray(cg["membrane_area_m2"], dtype=np.float64),
        cell_sa=np.asarray(cg["cell_area_m2"], dtype=np.float64),
        cell_vol=np.asarray(external["geometry"]["cell_volume_m3"], dtype=np.float64),
        cell_centres=np.asarray(external["geometry"]["cell_centres_m"], dtype=np.float64),
        mem_mids_flat=np.asarray(external["geometry"]["membrane_midpoints_m"], dtype=np.float64),
        mem_vects_flat=np.column_stack((np.zeros((m, 2)), cg["normal_xy"])),
        **{key: external["world"][key + "_m"] for key in ("xmin", "xmax", "ymin", "ymax")},
    )
    parameters = SimpleNamespace(
        is_ecm=True,
        v_sensitive_gj=False,
        grid_size=external["world"]["grid_size"],
        F=cd["parameters"]["F_C_mol"],
        R=supplied["R_J_mol_K"],
        T=p["configured_temperature_K"],
        q=p["q_C"],
        kb=p["kb_J_K"],
        cell_height=p["cell_height_m"],
        cell_space=p["cell_space_m"],
        tm=supplied["membrane_thickness_m"],
        gj_surface=supplied["gap_surface_fraction"],
        cluster_open=supplied["cluster_open"],
        fast_update_ecm=supplied["fast_update_ecm"],
        sharpness=supplied["sharpness"],
        fluid_flow=supplied["fluid_flow"],
    )
    before_rng = copy.deepcopy(np.random.get_state())
    geometry_code["grid"](cells, parameters)
    if min(cells.X.shape) < 2 or cells.X.size > 49:
        raise ValueError("Native ECM grid exceeds declared bounded domain")
    geometry_code["owner_matrices"](cells)
    geometry_code["environment"](cells, parameters)
    pairs = (
        ("cell_mol_m3", "cc_cells"),
        ("membrane_mol_m3", "cc_at_mem"),
        ("environment_mol_m3", "cc_env"),
        ("voltage_V", "vm"),
        ("membrane_flux_mol_m2_s", "fluxes_mem"),
        ("junction_flux_mol_m2_s", "fluxes_gj"),
        ("environment_flux_x_mol_m2_s", "fluxes_env_x"),
        ("environment_flux_y_mol_m2_s", "fluxes_env_y"),
        ("junction_voltage_V", "vgj"),
        ("junction_field_source", "Egj"),
        ("gap_open", "gjopen"),
    )
    sim = SimpleNamespace(
        **{
            native: np.asarray(inputs["initial"][key], dtype=np.float64).copy()
            for key, native in pairs
        }
    )
    sim.E_gj_x, sim.E_gj_y = np.asarray(
        inputs["initial"]["junction_field_xy_source"], dtype=np.float64
    ).T.copy()
    sim.mdl, sim.edl = m, cells.X.size
    sim.movingIons = [names.index(name) for name in ions["moving_ids"]]
    sim.zs = np.asarray(cd["ions"]["valence"], dtype=np.float64)
    for key, native in (
        ("membrane_diffusion_m2_s", "Dm_cells"),
        ("gap_diffusion_m2_s", "D_gj"),
        ("environment_diffusion_m2_s", "D_env"),
        ("tight_junction_modulator", "TJ_modulator"),
    ):
        setattr(sim, native, np.asarray(ions[key], dtype=np.float64).copy())
    for name in ("update_gj", "update_ecm", "update_intra", "update_all_concs"):
        setattr(sim, name, MethodType(source[name], sim))
    history, frames, environment_records, intermediate = [], [], [], {}
    active_commit = None

    def values():
        return {key: np.array(getattr(sim, native), copy=True) for key, native in pairs} | {
            "junction_field_xy_source": np.column_stack((sim.E_gj_x, sim.E_gj_y))
        }

    def observe(stage, i=None):
        ion_id, snapshot = None if i is None else names[i], values()
        # CPython can emit the first line of a multiline assignment repeatedly.
        # Coalesce only consecutive identical state copies at the same hook.
        if frames and (frames[-1]["stage"], frames[-1]["ion_id"]) == (stage, ion_id):
            if all(
                np.array_equal(value, frames[-1]["values"][key], equal_nan=True)
                for key, value in snapshot.items()
            ):
                return
        frames.append(dict(stage=stage, ion_id=ion_id, values=snapshot))

    codes = {
        name: source[name].__code__
        for name in (
            "ordered",
            "update_gj",
            "update_ecm",
            "update_intra",
            "update_all_concs",
            "gradient",
            "integrator",
            "nernst_planck_flux",
            "no_negs",
        )
    }

    def trace(frame, event, arg):
        nonlocal active_commit
        name = next((key for key, code in codes.items() if frame.f_code is code), None)
        if name is None:
            return None
        local = frame.f_locals
        if event == "line":
            if name == "ordered" and frame.f_lineno == lines["membrane_flux"]:
                observe("membrane_flux", local["i"])
            elif name == "update_all_concs":
                active_commit = local.get("i", active_commit)
                if frame.f_lineno == lines["membrane_commit"]:
                    observe("membrane_commit", active_commit)
                elif frame.f_lineno == lines["junction_commit"]:
                    observe("junction_commit", active_commit)
        elif event == "call":
            if name == "update_ecm":
                intermediate.clear()
                intermediate["before_mol_m3"] = sim.cc_env[local["i"]].copy()
            elif name == "gradient" and frame.f_back.f_code is codes["update_ecm"]:
                intermediate["clamped_mol_m3"] = local["F"].copy()
                observe("ecm_clamp", frame.f_back.f_locals["i"])
            elif name == "integrator":
                intermediate["euler_mol_m3"] = local["P"].copy()
        elif event == "return":
            if name in ("update_gj", "update_intra"):
                observe("junction_flux" if name == "update_gj" else "refresh_at_mem", local["i"])
            elif name == "nernst_planck_flux":
                intermediate["alpha"] = local["alpha"].copy()
            elif name == "update_ecm":
                row = dict(ion_id=names[local["i"]], **intermediate)
                row.update(
                    {
                        key: np.array(local[native], copy=True)
                        for key, native in (
                            ("gradient_x", "gcx"),
                            ("gradient_y", "gcy"),
                            ("effective_diffusion_m2_s", "denv"),
                            ("flux_x_mol_m2_s", "fx"),
                            ("flux_y_mol_m2_s", "fy"),
                            ("divergence_mol_m3_s", "div_fa"),
                            ("smoothed_mol_m3", "cenv"),
                        )
                    }
                )
                if "euler_mol_m3" not in row:
                    row["euler_mol_m3"] = local["cenv"].copy()
                environment_records.append(row)
                observe("ecm_commit", local["i"])
            elif name == "no_negs" and arg is not None:
                observe("clip_bulk", active_commit)
        elif event == "exception" and name == "no_negs":
            observe("clip_bulk_failure", active_commit)
        return trace

    previous = sys.gettrace()
    failure = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            for index, packet in enumerate(inputs["steps"]):
                frames.clear()
                environment_records.clear()
                sim.T, parameters.dt = packet["runtime_temperature_K"], packet["dt_s"]
                for key, native in (
                    ("junction_block", "gj_block"),
                    ("channel_multiplier", "rho_channel"),
                    ("electric_x_source", "E_env_x"),
                    ("electric_y_source", "E_env_y"),
                    ("velocity_x_m_s", "u_env_x"),
                    ("velocity_y_m_s", "u_env_y"),
                    ("boundary_mol_m3", "c_env_bound"),
                ):
                    setattr(sim, native, np.asarray(packet[key], dtype=np.float64).copy())
                observe("initial")
                source["resets"](sim, cells, parameters, float(index))
                observe("reset_flux")
                sim.fluxes_mem += np.asarray(
                    packet["supplied_pump_membrane_flux_mol_m2_s"], dtype=np.float64
                )
                observe("supplied_pump_flux")
                source["ordered"](sim, cells, parameters, float(index))
                sim.fluxes_mem += np.asarray(
                    packet["supplied_late_membrane_flux_mol_m2_s"], dtype=np.float64
                )
                observe("supplied_late_flux")
                sim.update_all_concs(cells, parameters)
                history.append(
                    copy.deepcopy(
                        dict(
                            frames=frames,
                            environment_records=environment_records,
                            candidate=values(),
                            source_completed=True,
                        )
                    )
                )
        except Exception as error:
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
            history.append(
                copy.deepcopy(
                    dict(
                        frames=frames,
                        environment_records=environment_records,
                        candidate=values(),
                        source_completed=False,
                    )
                )
            )
        finally:
            sys.settrace(previous)
    after_rng = np.random.get_state()
    unchanged = (
        before_rng[0] == after_rng[0]
        and np.array_equal(before_rng[1], after_rng[1])
        and before_rng[2:] == after_rng[2:]
    )
    native_geometry = dict(
        shape=cells.X.shape,
        delta_m=cells.delta,
        grid_points_m=cells.xypts,
        cell_to_grid=cells.map_cell2ecm,
        membrane_to_grid=cells.map_mem2ecm,
        membrane_area_per_site_m2=cells.memSa_per_envSquare,
        membrane_divergence_map_m2=cells.M_divmap_mem2ecm,
        true_environment_volume_m3=cells.true_ecm_vol,
        cell_to_environment_correction=cells.cell2env_corrF,
    )
    return dict(
        geometry=native_geometry,
        history=history,
        native_source_sha256=pins["source_sha256"],
        source_sites=sites,
        geometry_source_sites=geometry_sites,
        failure=failure,
        warnings=[str(w.message) for w in caught],
        RNG_unchanged=bool(unchanged),
        seams=(
            "Supplied pump before ion loop; supplied late flux after ion loop; "
            "fixed-gap source branch; held field/flow/bath"
        ),
        physical_material_or_energy_parity=False,
    )
