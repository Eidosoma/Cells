"""Authenticated normal ECM CaATP/GRN/full fields with source-disabled ER.

The initial update_V has no source check_v call. Normal calls retain the actual
post-commit update_V then check_v order. No supplied old-field array is consumed.
"""

import argparse
import ast
import builtins
import copy
import hashlib
import importlib.abc
import json
import os
import sys
import traceback
import warnings
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse import betse_ecm_grn_native_network as network
from validation.betse import betse_ecm_transport_native as previous
from validation.betse import betse_environment_field_native as field_native
from validation.betse import betse_normal_grn_join_native as archives


def field_nodes(root):
    sim_tree = ast.parse((root / "betse/science/sim.py").read_bytes())
    tb_tree = ast.parse((root / "betse/science/sim_toolbox.py").read_bytes())
    cells_tree = ast.parse((root / "betse/science/cells.py").read_bytes())
    cls = next(n for n in sim_tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    update = methods["update_V"]
    check = next(n for n in tb_tree.body if isinstance(n, ast.FunctionDef) and n.name == "check_v")
    loop = next(n for n in methods["_run_sim_core_loop"].body if isinstance(n, ast.For))
    nodes = [
        n
        for n in loop.body
        if isinstance(n, ast.Expr)
        and ast.unparse(n) in ("self.update_V(cells, p)", "stb.check_v(self.vm)")
    ]
    assert [ast.unparse(n) for n in nodes] == ["self.update_V(cells, p)", "stb.check_v(self.vm)"]
    bootstrap = [
        n
        for n in methods["run_sim_core"].body
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.update_V(phase.cells, phase.p)"
    ]
    assert len(bootstrap) == 1
    diviterm = [
        n
        for n in ast.walk(cells_tree)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.diviterm"
    ]
    assert len(diviterm) == 1
    blocks = dict(normal_field=nodes, bootstrap_field=bootstrap, diviterm=diviterm)
    functions = [
        field_native.wrapper(name, args, blocks[name])
        for name, args in (
            ("normal_field", "self,cells,p"),
            ("bootstrap_field", "self,phase"),
            ("diviterm", "self"),
        )
    ]
    sites = {}
    for name, nodes in dict(blocks, update_V=[update], check_v=[check]).items():
        sites[name] = dict(
            lines=[[n.lineno, n.end_lineno] for n in nodes],
            ast_sha256=hashlib.sha256(
                ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False).encode()
            ).hexdigest(),
        )
    return copy.deepcopy([update, check]) + functions, sites


def calcium_nodes(root):
    sim_tree = ast.parse((root / "betse/science/sim.py").read_bytes())
    cls = next(n for n in sim_tree.body if isinstance(n, ast.ClassDef) and n.name == "Simulator")
    methods = {n.name: n for n in cls.body if isinstance(n, ast.FunctionDef)}
    tb = ast.parse((root / "betse/science/sim_toolbox.py").read_bytes())
    functions = {n.name: n for n in tb.body if isinstance(n, ast.FunctionDef)}
    parameters = ast.parse((root / "betse/science/parameters.py").read_bytes())
    needed = {
        "Ca_dyn",
        "alpha_Ca",
        "cATP",
        "cADP",
        "cPi",
        "KmCa_Ca",
        "KmCa_ATP",
        "deltaGATP",
        "F",
        "R",
    }
    defaults = [
        n
        for n in ast.walk(parameters)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in {"self." + k for k in needed}
    ]
    assert len(defaults) == len(needed)
    init = methods["init_dynamics"]
    cold = [
        n
        for n in methods["init_core"].body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.met_concs"
    ]
    cold += [
        n
        for n in init.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.CaATP_block"
    ]
    cold += [
        n
        for n in init.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "p.ions_dict['Ca'] == 1 and p.Ca_dyn"
    ]
    cold_after = [
        n
        for n in init.body
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "self.rho_pump"
    ]
    assert len(cold) == 3 and len(cold_after) == 1
    plot = methods["_plot_loop"]
    phase_guard = next(
        n
        for n in plot.body
        if isinstance(n, ast.If) and ast.unparse(n.test) == "phase.kind is SimPhaseKind.INIT"
    )
    # This boundary is the normal SIM phase; capture its actual source else
    # branch without inventing an enum object in the isolated namespace.
    clock = list(phase_guard.orelse)
    clock += [
        n
        for n in plot.body
        if isinstance(n, ast.Assign)
        and ast.unparse(n.targets[0]) in ("phase_time_len", "time_steps")
    ]
    assert len(clock) == 5
    built = [
        field_native.wrapper("calcium_defaults", "self,iu", defaults),
        field_native.wrapper("calcium_cold", "self,cells,p", cold),
        field_native.wrapper("calcium_cold_after", "self,cells,p", cold_after),
        field_native.wrapper("source_clock", "phase", clock + ast.parse("return time_steps").body),
    ]
    originals = [methods["ca_handler"], functions["pumpCaATP"], functions["no_negs"]]
    sites = {
        name: dict(
            lines=[[n.lineno, n.end_lineno] for n in nodes],
            ast_sha256=hashlib.sha256(
                ast.dump(ast.Module(body=nodes, type_ignores=[]), include_attributes=False).encode()
            ).hexdigest(),
        )
        for name, nodes in dict(
            calcium_defaults=defaults,
            calcium_cold=cold,
            calcium_cold_after=cold_after,
            source_clock=clock,
            ca_handler=[methods["ca_handler"]],
            pumpCaATP=[functions["pumpCaATP"]],
            Ca_no_negs=[functions["no_negs"]],
        ).items()
    }
    return copy.deepcopy(originals) + built, sites


def capture():
    source, geometry, sites, geometry_sites, pins, lines = previous.capture()
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", pins["checkout"]))
    nodes, field_sites = field_nodes(root)
    geometry["BetseSimUnstableException"] = network.science()["BetseSimUnstableException"]
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])),
            "<complete original normal ECM voltage suffix>",
            "exec",
        ),
        geometry,
    )
    geometry["stb"].check_v = geometry["check_v"]
    geometry_sites.update(field_sites)
    ca_nodes, ca_sites = calcium_nodes(root)
    api = dict(
        np=np,
        BetseSimUnstableException=network.science()["BetseSimUnstableException"],
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=ca_nodes, type_ignores=[])),
            "<complete original ECM calcium caller>",
            "exec",
        ),
        api,
    )
    api["stb"] = SimpleNamespace(pumpCaATP=api["pumpCaATP"])
    geometry["ca_api"] = api
    geometry_sites.update(ca_sites)
    return source, geometry, sites, geometry_sites, pins, lines


def run_dispatch(ctx, material_declaration, publication, source_time_s, observer=None):
    ctx.p.substances_affect_charge = publication
    ctx.phase.kind = "SIM"
    ctx.net = ctx.sim.grn.core
    network.attach(ctx, material_declaration, observer)
    try:
        network.science()["dispatch"](ctx.sim, source_time_s, ctx.phase, ctx.cells, ctx.p)
        ctx.trace["source_completed"] = True
    finally:
        ctx.trace.update(
            cache_after=network.cache(ctx),
            values_after=network.material_values(ctx.sim),
            controls_after=dict(
                gj_block=network.clone(ctx.sim.gj_block),
                NaKATP_block=network.clone(ctx.sim.NaKATP_block),
            ),
            owner_after=network.owner_evidence(ctx),
            completed_transports=sum(
                (row["stage"] == "transport_after" for row in ctx.trace["molecule_frames"])
            ),
        )
    return ctx.trace


def evaluate(declared):
    inputs = declared["field"]
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
    sim = field_native.Observed(
        observations={},
        **{
            native: np.asarray(inputs["initial"][key], dtype=np.float64).copy()
            for key, native in pairs
        },
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
    parameters.NAv, parameters.er, parameters.eo = (
        p["NAv_per_mol"],
        p["relative_permittivity"],
        p["vacuum_permittivity_F_m"],
    )
    parameters.cell_radius, parameters.true_cell_size, parameters.mu = (
        p["cell_radius_m"],
        p["true_cell_size_m"],
        p["magnetic_permeability_H_m"],
    )
    parameters.cm = inputs["field_parameters"]["capacitance_F_m2"]
    parameters.cell_polarizability = inputs["field_parameters"]["polarizability"]
    geometry_code["inverses"](cells)
    geometry_code["sharpness"](parameters, {"sharpness cell": cd["parameters"]["sharpness_cell"]})
    geometry_code["weights"](sim, cells, parameters)
    geometry_code["diviterm"](cells)
    initial_cache = external["cache_initial_state"]
    sim.D_free = np.asarray(initial_cache["free_diffusion_m2_s"], np.float64).copy()
    live_cells, live_env = sim.cc_cells, sim.cc_env
    sim.cc_cells, sim.cc_env = (
        np.asarray(initial_cache[key], np.float64).copy()
        for key in ("cell_mol_m3", "environment_mol_m3")
    )
    geometry_code["caches"](sim, parameters)
    sim.cc_cells, sim.cc_env = live_cells, live_env
    sim.update_V = MethodType(geometry_code["update_V"], sim)
    initializer_cache = dict(
        sigma_S_m=np.asarray(sim.sigma), ko_environment_per_m=np.asarray(sim.ko_env)
    )
    history, frames, environment_records, intermediate = [], [], [], {}
    field_rows, hodge, current_locals, voltage_locals = [], [], {}, {}
    field_codes = {
        name: geometry_code[name].__code__ for name in ("get_current", "update_V", "HH_Decomp")
    }
    field_phase, material_candidate, post_material_cache = None, None, None
    ca_api = geometry_code["ca_api"]
    calcium_rows, calcium_arithmetic, calcium_local, calcium_pump_local = [], {}, {}, {}
    calcium_codes = {name: ca_api[name].__code__ for name in ("ca_handler", "pumpCaATP", "no_negs")}
    calcium_error, helper_returned = False, False
    helper_return_reference = None
    source_times = None
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
        nonlocal calcium_error, helper_returned, helper_return_reference
        local = frame.f_locals
        calcium_name = next(
            (key for key, code in calcium_codes.items() if frame.f_code is code), None
        )
        if calcium_name is not None:
            if (
                calcium_name == "no_negs"
                and frame.f_back is not None
                and frame.f_back.f_code is calcium_codes["pumpCaATP"]
            ):
                owner = frame.f_back.f_locals
                label = "membrane" if local["data"] is owner["cCai"] else "bath"
                if event in ("call", "return"):
                    calcium_arithmetic[
                        ("before" if event == "call" else "after") + "_no_negs_" + label
                    ] = np.array(local["data"], copy=True)
            if (
                event == "line"
                and calcium_name == "pumpCaATP"
                and "Qdenomo" in local
                and "inds_Z" not in local
            ):
                calcium_arithmetic.setdefault(
                    "quotient_denominator_raw", np.array(local["Qdenomo"], copy=True)
                )
            if event == "exception":
                calcium_error = True
            if event == "return":
                if calcium_name == "pumpCaATP":
                    calcium_pump_local.update(
                        {
                            key: np.array(value, copy=True)
                            for key, value in local.items()
                            if isinstance(value, (np.ndarray, np.generic))
                        }
                    )
                    helper_returned = arg is not None
                    helper_return_reference = arg
                    if arg is not None:
                        calcium_arithmetic["raw_flux_mol_m2_s"] = np.array(arg, copy=True)
                    arithmetic_names = dict(
                        Qnumo="quotient_numerator",
                        Qdenomo="quotient_denominator_used",
                        Q="quotient",
                        Keq="equilibrium",
                        numo_E="forward_numerator",
                        denomo_E="forward_denominator",
                        frwd="forward",
                        numo_Eb="backward_numerator_unused",
                        denomo_Eb="backward_denominator_unused",
                        bkwrd="backward_unused",
                    )
                    calcium_arithmetic.update(
                        {
                            key: np.array(local[native], copy=True)
                            for native, key in arithmetic_names.items()
                            if native in local
                        }
                    )
                    if "inds_Z" in local:
                        calcium_arithmetic["zero_denominator_indices"] = np.array(
                            local["inds_Z"][0], copy=True
                        )
                elif calcium_name == "ca_handler":
                    calcium_local.update(
                        {
                            key: np.array(value, copy=True)
                            for key, value in local.items()
                            if isinstance(value, (np.ndarray, np.generic))
                        }
                    )
                    calcium_local["rate_aliases_handler_flux"] = (
                        hasattr(sim, "rate_CaATP") and local.get("f_CaATP") is sim.rate_CaATP
                    )
                    calcium_local["rate_aliases_helper_flux"] = (
                        hasattr(sim, "rate_CaATP") and sim.rate_CaATP is helper_return_reference
                    )
            return trace
        field_name = next((key for key, code in field_codes.items() if frame.f_code is code), None)
        if field_name is not None:
            if event == "return":
                if field_name == "HH_Decomp" and arg is not None:
                    hodge.append(
                        {
                            key: np.array(local[native], copy=True)
                            for key, native in zip(
                                (
                                    "input_x",
                                    "input_y",
                                    "rotated_x",
                                    "rotated_y",
                                    "rotated_divergence",
                                    "AA",
                                    "solenoidal_x",
                                    "solenoidal_y",
                                    "divergence",
                                    "BB",
                                    "gradient_x",
                                    "gradient_y",
                                ),
                                (
                                    "JJx",
                                    "JJy",
                                    "Jxr",
                                    "Jyr",
                                    "divJr",
                                    "AA",
                                    "Fx",
                                    "Fy",
                                    "divJd",
                                    "BB",
                                    "Gx",
                                    "Gy",
                                ),
                                strict=True,
                            )
                        }
                    )
                elif field_name in ("get_current", "update_V"):
                    target = current_locals if field_name == "get_current" else voltage_locals
                    target.update(
                        {
                            key: np.array(value, copy=True)
                            for key, value in local.items()
                            if isinstance(value, (np.ndarray, np.generic))
                        }
                    )
            return trace
        if name is None:
            return None
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

    def field_input(phase):
        return dict(
            mode="field",
            phase=phase,
            definition=network.clone(raw),
            field_parameters=network.clone(inputs["field_parameters"]),
            dt_s=parameters.dt,
            current=dict(
                cell_mol_m3=sim.cc_cells,
                membrane_flux_mol_m2_s=sim.fluxes_mem,
                junction_flux_mol_m2_s=sim.fluxes_gj,
                extra_charge_C_m3=sim.extra_rho_cells,
                extra_current_A_m2=sim.extra_J_mem,
            ),
            environment=dict(
                old_voltage_V=sim.vm,
                boundary_V=sim.bound_V,
                environment_mol_m3=sim.cc_env,
                environment_flux_x=sim.fluxes_env_x,
                environment_flux_y=sim.fluxes_env_y,
                extra_environment_current_xy=np.column_stack((sim.extra_Jenv_x, sim.extra_Jenv_y)),
                extra_environment_charge_C_m3=sim.extra_rho_env,
            ),
        )

    def field_call(phase):
        nonlocal field_phase
        field_phase = phase
        hodge.clear()
        current_locals.clear()
        voltage_locals.clear()
        sim.observations.clear()
        # Retain the actual pre-field inputs before any source field arithmetic.
        record = dict(before=copy.deepcopy(field_input(phase)), source_completed=False)
        field_rows.append(record)
        try:
            if phase == "bootstrap":
                geometry_code["bootstrap_field"](sim, ctx.phase)
            else:
                geometry_code["normal_field"](sim, cells, parameters)
            record["source_completed"] = True
        finally:
            record.update(
                current_locals=copy.deepcopy(current_locals),
                voltage_locals=copy.deepcopy(voltage_locals),
                hodge=copy.deepcopy(hodge),
                observations=copy.deepcopy(sim.observations),
                available_simulator_fields={
                    key: network.clone(getattr(sim, key))
                    for key in (
                        "rho_cells",
                        "Jmem",
                        "Jgj",
                        "Jn",
                        "I_mem",
                        "J_cell_x",
                        "J_cell_y",
                        "Jc",
                        "rho_env",
                        "rho_env_surf",
                        "v_env",
                        "Phi_b",
                        "E_env_x",
                        "E_env_y",
                        "Eme",
                        "J_env_x",
                        "J_env_y",
                        "Jtx",
                        "Jty",
                        "B_field",
                        "sigma_cell",
                        "vm",
                        "vm_ave",
                        "E_cell_x",
                        "E_cell_y",
                        "Emc",
                        "dvm",
                    )
                    if hasattr(sim, key)
                },
            )
        current_values = dict(
            charge_density_C_m3=sim.rho_cells,
            membrane_current_A_m2=sim.Jmem,
            junction_current_A_m2=sim.Jgj,
            raw_normal_current_A_m2=sim.observations["Jn"][0],
            average_normal_current_A_m2=current_locals["Jn_ave"],
            normal_current_A_m2=sim.Jn,
            inward_membrane_current_A=sim.I_mem,
            cell_current_xy_A_m2=np.column_stack((sim.J_cell_x, sim.J_cell_y)),
            projected_cell_current_A_m2=sim.Jc,
        )
        field_values = dict(
            raw_environment_current_x=hodge[-1]["input_x"],
            raw_environment_current_y=hodge[-1]["input_y"],
            local_voltage_assignment=None,
            local_voltage_smoothed=None,
            surface_charge_C_m2=sim.rho_env_surf,
            surface_voltage_V=sim.observations["v_env"][0],
            environment_charge_C_m3=sim.rho_env,
            screened_voltage_source=current_locals["screen"] * sim.v_env.reshape(cells.X.shape),
            screen=np.asarray(current_locals["screen"]),
            boundary_rhs=current_locals["div_Jb"],
            boundary_potential_V=sim.Phi_b,
            environment_voltage_V=sim.v_env,
            electric_x_source=sim.E_env_x,
            electric_y_source=sim.E_env_y,
            normal_electric_source=sim.Eme,
            environment_current_x=sim.J_env_x,
            environment_current_y=sim.J_env_y,
            total_current_x_source=sim.Jtx,
            total_current_y_source=sim.Jty,
            magnetic_field_source=sim.B_field,
        )
        voltage_values = dict(
            boundary_rhs_V_m2=current_locals["div_Jb"],
            boundary_potential_V=sim.Phi_b,
            conductivity_S_m=sim.sigma_cell,
            surface_charge_C_m2=voltage_locals["rho_surf"],
            voltage_V=sim.vm,
            mean_voltage_V=sim.vm_ave,
            cell_field_xy_V_m=np.column_stack((sim.E_cell_x, sim.E_cell_y)),
            normal_cell_field_V_m=sim.Emc,
            derivative_V_s=sim.dvm,
        )
        record.update(
            current=dict(values=copy.deepcopy(current_values)),
            environment=dict(
                values=copy.deepcopy(field_values),
                current_hodge=copy.deepcopy(hodge[-1]),
                smoothing_hodge=None,
            ),
            voltage=dict(values=copy.deepcopy(voltage_values)),
            candidate=values(),
            initializer_cache=copy.deepcopy(initializer_cache),
            all_fields_finite=all(
                np.isfinite(value).all()
                for group in (current_values, field_values, voltage_values)
                for value in group.values()
                if value is not None
            ),
        )
        return copy.deepcopy(record)

    def rate_cache():
        return dict(
            present=hasattr(sim, "rate_CaATP"),
            value=network.clone(sim.rate_CaATP) if hasattr(sim, "rate_CaATP") else None,
        )

    def clock(index):
        return dict(
            source_times_s=source_times.copy(),
            call_index=index,
            material_dt_sum_s=index * inputs["bootstrap"]["dt_s"],
        )

    def calcium_call(index):
        nonlocal calcium_error, helper_returned, field_phase, helper_return_reference
        field_phase = "calcium"
        calcium_arithmetic.clear()
        calcium_local.clear()
        calcium_pump_local.clear()
        calcium_error, helper_returned = False, False
        helper_return_reference = None
        before = dict(
            mode="calcium",
            definition=network.clone(raw),
            values_before=values(),
            parameters={
                k: getattr(parameters, k)
                for k in (
                    "cATP",
                    "cADP",
                    "cPi",
                    "KmCa_Ca",
                    "KmCa_ATP",
                    "deltaGATP",
                    "alpha_Ca",
                    "F",
                    "R",
                )
            },
            alpha_Ca=parameters.alpha_Ca,
            rate_cache_before=rate_cache(),
            clock=clock(index),
            dt_s=parameters.dt,
            runtime_temperature_K=sim.T,
            block_unused=sim.CaATP_block.copy(),
            rho_pump=sim.rho_pump,
            met_unused=sim.met_concs,
            Ca_dyn=parameters.Ca_dyn,
            ER_executed=False,
        )
        record = dict(before=copy.deepcopy(before), source_completed=False)
        calcium_rows.append(record)
        try:
            sim.ca_handler(cells, parameters)
            record["source_completed"] = True
        finally:
            record.update(
                arithmetic=copy.deepcopy(calcium_arithmetic),
                handler_locals=copy.deepcopy(calcium_local),
                helper_locals=copy.deepcopy(calcium_pump_local),
                helper_returned=helper_returned,
                rate_cache_after=rate_cache(),
                values_after=values(),
                source_exception_observed=calcium_error,
            )
            if parameters.alpha_Ca > 0:
                record["helper"] = dict(
                    incoming_membrane_mM=before["values_before"]["membrane_mol_m3"][sim.iCa],
                    incoming_bath_mM=before["values_before"]["environment_mol_m3"][sim.iCa][
                        cells.map_mem2ecm
                    ],
                    membrane_after_mM=calcium_pump_local.get("cCai"),
                    bath_after_mM=calcium_pump_local.get("cCao"),
                    voltage_V=before["values_before"]["voltage_V"],
                    runtime_temperature_K=sim.T,
                    parameters=before["parameters"],
                    block_unused=before["block_unused"],
                    met_unused=before["met_unused"],
                    arithmetic=copy.deepcopy(calcium_arithmetic),
                    flux_mol_m2_s=calcium_arithmetic.get("raw_flux_mol_m2_s"),
                    source_completed=helper_returned,
                    finite=all(
                        np.isfinite(value).all()
                        for value in (
                            calcium_pump_local.get("cCai", np.nan),
                            calcium_pump_local.get("cCao", np.nan),
                            sim.vm,
                            *calcium_arithmetic.values(),
                        )
                    ),
                    failure=None,
                )
            else:
                record["helper"] = None
        observe("calcium_handler")
        return copy.deepcopy(record)

    definition = inputs["network"]
    network.validate_definition(definition, names, n, m, cells.X.size)
    sim.T, parameters.dt = parameters.T, 0.0
    sim.rho_channel = np.ones(m)
    sim.gj_block = np.asarray(definition["initial_controls"]["gj_block"], np.float64).copy()
    sim.NaKATP_block = np.asarray(definition["initial_controls"]["NaKATP_block"], np.float64).copy()
    sim.c_env_bound = np.asarray(definition["initial_ion_boundary"], np.float64).copy()
    sim.E_env_x, sim.E_env_y = np.zeros(cells.X.shape), np.zeros(cells.X.shape)
    for key, size in (
        ("extra_rho_cells", n),
        ("extra_rho_env", cells.X.size),
        ("extra_J_mem", m),
        ("extra_Jenv_x", cells.X.size),
        ("extra_Jenv_y", cells.X.size),
    ):
        setattr(sim, key, np.zeros(size))
    ctx = network.augment(sim, cells, parameters, definition, names)
    ca_api["calcium_defaults"](parameters, {"alpha_Ca": declared["calcium"]["alpha_Ca"]})
    ca_api["calcium_cold"](sim, cells, parameters)
    sim.ca_handler = MethodType(ca_api["ca_handler"], sim)
    sim.iCa = names.index("Ca")
    try:
        cold_cache = network.cold(ctx)
    except Exception as error:
        return dict(
            status="source_refused",
            cold_failure=network.cache(ctx),
            history=[],
            failure=dict(
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                stage="cold",
            ),
            RNG_unchanged=all(
                np.array_equal(a, b) for a, b in zip(before_rng, np.random.get_state(), strict=True)
            ),
        )
    ca_api["calcium_cold_after"](sim, cells, parameters)
    cold_policy = dict(
        Ca_dyn=parameters.Ca_dyn,
        CaATP_block=sim.CaATP_block.copy(),
        rho_pump=sim.rho_pump,
        met_concs=sim.met_concs,
        endo_retic=sim.endo_retic,
        rate_CaATP_present=hasattr(sim, "rate_CaATP"),
        parameters={
            k: getattr(parameters, k)
            for k in (
                "cATP",
                "cADP",
                "cPi",
                "KmCa_Ca",
                "KmCa_ATP",
                "deltaGATP",
                "alpha_Ca",
                "F",
                "R",
            )
        },
    )
    cold_material = values()
    parameters.sim_tsteps = 3
    parameters.dt = inputs["bootstrap"]["dt_s"]
    ctx.phase.kind = "SIM"
    source_times = ca_api["source_clock"](ctx.phase)
    controls = network.clone(definition["initial_controls"])

    previous = sys.gettrace()
    failure = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            sys.settrace(trace)
            parameters.dt = inputs["bootstrap"]["dt_s"]
            sim.bound_V = dict(inputs["bootstrap"]["boundary_V"])
            field_call("bootstrap")
            for index, call in enumerate(inputs["steps"]):
                packet = dict(
                    call["material"],
                    electric_x_source=sim.E_env_x.copy(),
                    electric_y_source=sim.E_env_y.copy(),
                )
                material_candidate, post_material_cache = None, None
                field_phase = "material_network"
                selected = (
                    controls if call["scheduled_controls"] is None else call["scheduled_controls"]
                )
                packet["junction_block"] = selected["gj_block"]
                material_before = dict(
                    mode="material",
                    definition=network.clone(raw),
                    initial=values(),
                    steps=[network.clone(packet)],
                    calcium=network.clone(declared["calcium"]),
                    rate_cache_before=rate_cache(),
                    clock=clock(index),
                )
                sim.NaKATP_block = np.asarray(selected["NaKATP_block"], np.float64).copy()
                ctx.trace = network.new_trace()
                frames.clear()
                environment_records.clear()
                sim.T, parameters.dt = packet["runtime_temperature_K"], packet["dt_s"]
                for key, native in (
                    ("junction_block", "gj_block"),
                    ("channel_multiplier", "rho_channel"),
                    ("velocity_x_m_s", "u_env_x"),
                    ("velocity_y_m_s", "u_env_y"),
                    ("boundary_mol_m3", "c_env_bound"),
                ):
                    setattr(sim, native, np.asarray(packet[key], dtype=np.float64).copy())
                observe("initial")
                source["resets"](sim, cells, parameters, float(source_times[index]))
                observe("reset_flux")
                sim.fluxes_mem += np.asarray(
                    packet["supplied_pump_membrane_flux_mol_m2_s"], dtype=np.float64
                )
                observe("supplied_pump_flux")
                source["ordered"](sim, cells, parameters, float(source_times[index]))
                calcium_result = calcium_call(index)
                field_phase = "material_network"
                sim.fluxes_mem += np.asarray(
                    packet["supplied_late_membrane_flux_mol_m2_s"], dtype=np.float64
                )
                observe("supplied_late_flux")
                run_dispatch(ctx, raw, call["publication"], float(source_times[index]))
                controls = network.clone(ctx.trace["controls_after"])
                observe("ecm_grn_dispatch")
                sim.update_all_concs(cells, parameters)
                material_candidate, post_material_cache = values(), network.cache(ctx)
                sim.bound_V = dict(call["boundary_V"])
                field_result = field_call("field")
                history.append(
                    copy.deepcopy(
                        dict(
                            frames=frames,
                            environment_records=environment_records,
                            candidate=values(),
                            material_before=material_before,
                            material_candidate=material_candidate,
                            post_material_cache=post_material_cache,
                            field=field_result,
                            calcium=calcium_result,
                            clock_before=clock(index),
                            clock_after=clock(index + 1),
                            rate_cache_after=rate_cache(),
                            source_completed=True,
                            network=network.clone(ctx.trace),
                        )
                    )
                )
        except Exception as error:
            failure = dict(
                type=type(error).__name__,
                message=str(error),
                traceback=traceback.format_exc(),
                stage=field_phase,
            )
            history.append(
                copy.deepcopy(
                    dict(
                        frames=frames,
                        environment_records=environment_records,
                        candidate=values(),
                        material_before=locals().get("material_before"),
                        calcium=copy.deepcopy(calcium_rows[-1]) if calcium_rows else None,
                        material_candidate=material_candidate,
                        post_material_cache=post_material_cache,
                        field=copy.deepcopy(field_rows[-1])
                        if field_rows and field_phase in ("bootstrap", "field")
                        else None,
                        source_completed=False,
                        network=network.clone(ctx.trace),
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
        status="source_refused" if failure else "source_completed",
        cold_cache=cold_cache,
        cold_policy=cold_policy,
        source_times_s=source_times,
        calcium_rows=calcium_rows,
        cold_material=cold_material,
        initializer_cache=initializer_cache,
        bootstrap=copy.deepcopy(field_rows[0]) if field_rows else None,
        field_rows=field_rows,
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
            "fixed-gap source branch; source reconstructed field feedback; "
            "explicit external flow/bath/boundary"
        ),
        physical_material_or_energy_parity=False,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("ECM native production import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("ECM native production import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [n for n in sys.modules if n.split(".")[0] in blocked]
    assert not loaded
    result.update(
        production_imports_denied=True,
        loaded_production_modules=loaded,
        runtime=archives.runtime_inventory(),
    )
    archives.write_archive(args.output, result)


if __name__ == "__main__":
    main()
