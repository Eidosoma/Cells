"""Deferred supplied-owner specimens; no genuine seed/init/load claim.

Construction is a future test action. The full additional owner inventory is
explicitly hydrated from the existing manufactured component declarations.
Existing cold code is used only to create specimen GRN owners before admission;
the handoff itself is then required to make zero cold/dynamics calls.
"""

import traceback
from copy import deepcopy
from types import SimpleNamespace

import numpy as np

from cells.processes import betse_ecm_grn_join as network
from cells.processes import betse_ecm_grn_source as source
from cells.processes import betse_ecm_transport as material
from cells.processes import betse_normal_ecm_calcium_join as calcium
from cells.processes import betse_normal_ecm_field_join as field
from cells.processes import betse_normal_ecm_initialization as handoff
from cells.processes import betse_normal_ecm_mechanics_join as mechanical
from cells.processes import betse_normal_ion_join as ions
from validation.betse import betse_normal_ecm_calcium_join_fixtures as calcium_fixtures
from validation.betse import betse_normal_ecm_field_join_fixtures as field_fixtures
from validation.betse import betse_normal_ecm_mechanics_join_fixtures as mechanical_fixtures

CASES = ("field", "polarized", "calcium", "mechanics", "warm-owner")
REFUSALS = (
    "missing-Egj",
    "missing-mechanical-PP",
    "scalar-flow-store",
    "foreign-centres",
    "foreign-inverse",
    "wrong-fixed-sigma",
    "wrong-cache-boundary-epoch",
    "wrong-control",
    "scalar-control",
    "wrong-publication",
    "missing-GRN-cache",
    "unsupported-channels",
    "persisted-CaATP-rate",
    "wrong-calcium-clock",
    "missing-calcium-policy",
    "wrong-molecular-axis",
    "wrong-stage",
    "native-chain-claim",
    "changed-seal",
    "integer-primary-dtype",
    "wrong-ion-order",
    "nonzero-declared-zero-pressure",
    "namespace-is-not-native",
)


def declaration(case):
    return dict(
        kind=handoff.DECLARATION_KIND,
        stage=handoff.STAGE,
        geometry_classification="supplied_layout",
        upstream_evidence=[
            dict(
                path="deferred-manufactured-owner-specimen/" + case,
                sha256=ions.digest(("supplied-owner-specimen", case)),
            )
        ],
    )


def failure_record(error):
    """Retain the original exception chain and every available numeric partial."""
    rows, seen = [], set()
    current = error
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        rows.append(
            dict(
                type=type(current).__name__,
                message=str(current),
                traceback="".join(traceback.format_exception(current)),
                available={
                    name: getattr(current, name)
                    for name in ("stage", "boundary", "partial", "trial", "source")
                    if hasattr(current, name)
                },
            )
        )
        current = current.__cause__ or current.__context__
    return dict(exceptions=rows, exception_cycle_detected=current is not None)


def _notify(callback, name, value):
    if callback is not None:
        callback(name, value)


def _construction_state(progress):
    result = {key: value for key, value in progress.items() if key != "ctx"}
    ctx = progress.get("ctx")
    if ctx is not None:
        try:
            result["available_owner"] = network._failure_snapshot(ctx, progress.get("cache"))
        except BaseException as capture_error:
            result["owner_capture_failure"] = failure_record(capture_error)
    return result


def specimen(case="field", *, on_capture=None):
    """Optional evidence observer; construction equations and owner order are unchanged."""
    progress = dict(requested_case=case)
    _notify(on_capture, "construction-request", progress.copy())
    try:
        result = _specimen(case, on_capture, progress)
    except BaseException as error:
        # An observer failure must never replace the original construction error.
        try:
            if on_capture is not None:
                _notify(
                    on_capture,
                    "construction-failure",
                    dict(previous=_construction_state(progress), **failure_record(error)),
                )
        except BaseException as capture_error:
            error.add_note("Construction failure capture also failed: " + repr(capture_error))
        raise
    if on_capture is not None:
        _notify(on_capture, "construction-return", _construction_state(progress))
    return result


def _specimen(case, on_capture, progress):
    if case not in CASES:
        raise ValueError("Undeclared supplied-owner specimen")
    if case == "calcium":
        raw = calcium_fixtures.fixture("active")
        progress["raw"] = raw
        _notify(on_capture, "raw-declaration", dict(raw=deepcopy(raw)))
        outer = calcium.bind(raw)
        binding = outer
    elif case == "mechanics":
        raw = mechanical_fixtures.fixture("coupled-osmotic")
        progress["raw"] = raw
        _notify(on_capture, "raw-declaration", dict(raw=deepcopy(raw)))
        outer = mechanical.bind(raw)
        binding = outer.field
    else:
        raw = field_fixtures.fixture("polarized" if case == "polarized" else "coupled")
        progress["raw"] = raw
        _notify(on_capture, "raw-declaration", dict(raw=deepcopy(raw)))
        outer = binding = field.bind(raw)
    progress.update(binding=binding, outer=outer)
    mb = binding.material_binding
    gb, k, vb = mb.geometry_binding, mb.kernel, binding.voltage_binding
    cb, g = gb.current_binding, gb.geometry
    ep = gb.definition["parameters"]
    initial = material.state(mb, ions.data(binding.inputs["initial"]))
    work = material.Values(*(np.array(value, copy=True) for value in initial.values))
    ctx = network.make_context(binding, work, ions.data(binding.inputs["network"]))
    progress["ctx"] = ctx
    if case == "calcium":
        calcium.native_policy(ctx, binding)
    if on_capture is not None:
        _notify(on_capture, "before-cold", _construction_state(progress))
    source.cold(ctx)
    if case == "warm-owner":
        # A declared warm gene store. It must survive handoff verbatim.
        ctx.sim.grn.core.molecules["X"].c_cells += np.array([0.125, 0.25, 0.5])
    sim, cells, p = ctx.sim, ctx.cells, ctx.p
    n, m, e = len(cb.cell_ids), len(cb.membrane_ids), len(g.grid_points_m)
    sim.D_free = np.asarray(gb.definition["cache_initial_state"]["free_diffusion_m2_s"], float)
    sim.sigma, sim.ko_env = float(gb.cache.sigma_S_m), float(gb.cache.ko_environment_per_m)
    sim.zs, sim.movingIons = cb.kernel.valence.copy(), list(k.moving)
    sim.smooth_weight_mem, sim.smooth_weight_o = cb.kernel.membrane_weight, cb.kernel.other_weight
    sim.cdl, sim.mdl, sim.edl = n, m, e
    sim.bound_V = ions.data(binding.inputs["bootstrap"]["boundary_V"])
    cells.mem_vects_flat = np.column_stack((np.zeros((m, 2)), cb.kernel.normal_xy))
    cells.gj_default_weights, cells.num_mems = k.gap_weights, cb.kernel.owner_sum.sum(axis=1)
    cells.R_rads, cells.diviterm = vb.kernel.radius_m, vb.kernel.diviterm_m
    for native, bound in dict(
        X="X_m",
        Y="Y_m",
        xypts="grid_points_m",
        map_ij2k="index_ij",
        map_cell2ecm="cell_to_grid",
        map_mem2ecm="membrane_to_grid",
        memSa_per_envSquare="membrane_area_per_site_m2",
        mems_per_envSquare="membranes_per_site",
        true_ecm_vol="true_environment_volume_m3",
        M_divmap_mem2ecm="membrane_divergence_map_m2",
        cell2env_corrF="cell_to_environment_correction",
        lapENVinv="dirichlet_inverse_m2",
        lapENV_P_inv="neumann_inverse_m2",
    ).items():
        setattr(cells, native, getattr(g, bound))
    for key in ("xmin", "xmax", "ymin", "ymax"):
        setattr(cells, key, float(gb.definition["world"][key + "_m"]))
    p.solver_type, p.td_deform, p.v_sensitive_gj, p.Ca_dyn = "FULL", False, False, False
    p.sim_tsteps = 3
    for key, value in dict(
        NAv=ep["NAv_per_mol"],
        er=ep["relative_permittivity"],
        eo=ep["vacuum_permittivity_F_m"],
        mu=ep["magnetic_permeability_H_m"],
        cell_space=ep["cell_space_m"],
        cell_radius=ep["cell_radius_m"],
        true_cell_size=ep["true_cell_size_m"],
        gj_surface=k.gap_surface_fraction,
        smooth_cells=cb.kernel.source_smooth_cells,
        cm=binding.inputs["field_parameters"]["capacitance_F_m2"],
        cell_polarizability=binding.inputs["field_parameters"]["polarizability"],
        dt=binding.inputs["bootstrap"]["dt_s"],
    ).items():
        setattr(p, key, value)
    mesh, display = {}, {}
    if case == "mechanics":
        definition = outer.mechanics.definition
        layout, params = definition["geometry"]["layout"], definition["parameters"]
        cells.cell_nn_i = np.asarray(layout["neighbors"], int)
        cells.nn_len = np.asarray(layout["lengths_m"], float)
        cells.nn_tx, cells.nn_ty = np.asarray(layout["force_directions"], float).T
        cells.cell_nn_tx, cells.cell_nn_ty = np.asarray(layout["curl_directions"], float).T
        cells.mem_vol, cells.mem_verts = (
            np.asarray(layout["membrane_volume_m3"], float),
            np.asarray(layout["vertices_m"], float),
        )
        cells.lapGJ, cells.lapGJinv = (
            outer.mechanics.operators.laplacian,
            outer.mechanics.operators.laplacian_inverse,
        )
        mesh = {
            native: np.asarray(layout[key], float)
            for native, key in dict(
                vor_edge_len="dual_edge_m",
                tri_edge_len="primal_edge_m",
                delta_tri_0="incidence",
                delta_tri_0_inv="incidence_inverse",
                vor_sa="dual_area_m2",
            ).items()
        }
        held = ions.data(outer.inputs["mechanics_initial"])
        for key, value in held.items():
            if not key.startswith("display_"):
                setattr(sim, key, np.asarray(value, float) if isinstance(value, list) else value)
        owner = cb.kernel.owner
        vertices = np.asarray(held["display_vertices_m"], float)
        display = dict(
            cell_centres=np.asarray(held["display_centres_m"], float),
            cell_verts=[vertices[owner == i] for i in range(n)],
            mem_verts=cells.mem_verts,
        )
        p.deformation, p.deform_osmo = (
            definition["policy"]["deformation"],
            definition["policy"]["deform_osmo"],
        )
        p.lame_mu = params["young_modulus_Pa"] / (2 * (1 + 0.49))
        p.galvanotropism, p.aquaporins = params["galvanotropism_m2_V"], params["aquaporin_fraction"]
        p.mu_water, p.rho, p.fixed_cluster_bound = (
            params["water_viscosity_Pa_s"],
            params["density_kg_m3"],
            params["fixed_boundary"],
        )
        sim.P_cells, sim.P_base, sim.P_mod = np.zeros(n), np.zeros(n), np.zeros(n)
    owners = dict(sim=sim, cells=cells, parameters=p, mesh=mesh, display=display)
    cached = source.cache(ctx)
    progress["cache"] = cached
    excluded = dict.fromkeys(handoff.EXCLUDED, False)
    return dict(
        raw=deepcopy(raw),
        binding=binding,
        outer=outer,
        owners=owners,
        network_cache=cached,
        excluded=excluded,
        declaration=declaration(case),
        ctx=ctx,
    )


def capture(spec):
    return handoff.capture_supplied(
        spec["owners"], spec["network_cache"], spec["excluded"], spec["declaration"]
    )


def refusal(name, *, on_capture=None):
    if name not in REFUSALS:
        raise ValueError("Undeclared owner-handoff refusal")
    case = (
        "calcium"
        if name in ("persisted-CaATP-rate", "wrong-calcium-clock", "missing-calcium-policy")
        else (
            "mechanics"
            if name
            in ("missing-mechanical-PP", "scalar-flow-store", "nonzero-declared-zero-pressure")
            else "field"
        )
    )
    spec = specimen(case, on_capture=on_capture)
    sim, cells, p = (spec["owners"][key] for key in ("sim", "cells", "parameters"))
    if name == "missing-Egj":
        del sim.Egj
    elif name == "missing-mechanical-PP":
        del sim.PP
    elif name == "scalar-flow-store":
        sim.u_env_x = 0.0
    elif name == "foreign-centres":
        cells.cell_centres = cells.cell_centres.copy()
        cells.cell_centres[0, 0] += 0.125
    elif name == "foreign-inverse":
        cells.lapENVinv = cells.lapENVinv.copy()
        cells.lapENVinv[0, 0] += 1.0
    elif name == "wrong-fixed-sigma":
        sim.sigma *= 2.0
    elif name == "wrong-cache-boundary-epoch":
        spec["network_cache"]["wire"]["ion_boundary_state"][0] += 0.25
    elif name == "wrong-control":
        sim.gj_block[0] += 0.125
    elif name == "scalar-control":
        sim.gj_block = 1
    elif name == "wrong-publication":
        sim.extra_J_mem[0] += 0.125
    elif name == "missing-GRN-cache":
        spec["network_cache"] = None
    elif name == "unsupported-channels":
        spec["excluded"]["channels"] = True
    elif name == "persisted-CaATP-rate":
        sim.rate_CaATP = np.full(sim.mdl, 0.125)
    elif name == "wrong-calcium-clock":
        p.sim_tsteps = 4
    elif name == "missing-calcium-policy":
        del sim.CaATP_block
    elif name == "wrong-molecular-axis":
        spec["network_cache"]["wire"]["molecule_fields"]["X"]["c_cells"] = np.zeros(2)
    elif name == "wrong-stage":
        spec["declaration"]["stage"] = "after_bootstrap"
    elif name == "native-chain-claim":
        spec["declaration"]["native_initialization_complete"] = True
    elif name == "integer-primary-dtype":
        sim.cc_cells = sim.cc_cells.astype(np.int64)
    elif name == "wrong-ion-order":
        p.ions_dict = dict(reversed(list(p.ions_dict.items())))
    elif name == "nonzero-declared-zero-pressure":
        sim.P_base[0] = 0.25
    return spec, case


def namespace_phase(spec):
    return SimpleNamespace(
        sim=spec["owners"]["sim"],
        cells=spec["owners"]["cells"],
        p=spec["owners"]["parameters"],
        kind=SimpleNamespace(name="SIM"),
    )
