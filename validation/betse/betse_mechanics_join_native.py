"""Authenticated ordinary mechanics blocks with complete raw stage witnesses.

Seed/cut provenance is audited separately; only graphLaplacian on the supplied
DEC declaration executes. Flow and timeDeform bodies remain dormant here.
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
from types import SimpleNamespace

import numpy as np
from scipy.interpolate import SmoothBivariateSpline

PROTOCOL = Path(__file__).with_name("betse_mechanics_join_protocol.json")


def capture():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    root = Path(os.environ.get("CELLS_BETSE_SOURCE", pins["checkout"]))
    trees = {}
    for name, pin in pins["source_sha256"].items():
        for base in (root, Path(pins["checkout"]), Path(pins["installed_package"]).parent):
            if hashlib.sha256((base / name).read_bytes()).hexdigest() != pin:
                raise ValueError("Changed native mechanics source: " + str(base / name))
        if name.endswith(".py"):
            trees[name] = ast.parse((root / name).read_text())

    def executable(node):
        node = copy.deepcopy(node)
        for item in ast.walk(node):
            if isinstance(item, ast.FunctionDef):
                item.decorator_list, item.returns = [], None
                for arg in (*item.args.posonlyargs, *item.args.args, *item.args.kwonlyargs):
                    arg.annotation = None
        return node

    selected, sites = [], {}
    for path, names in (
        (
            "betse/science/physics/deform.py",
            ("getDeformation", "timeDeform", "implement_deform_timestep"),
        ),
        ("betse/science/physics/flow.py", ("getFlow",)),
        ("betse/science/physics/pressures.py", ("osmotic_P",)),
        ("betse/science/sim_toolbox.py", ("check_v",)),
    ):
        for name in names:
            node = next(
                node
                for node in trees[path].body
                if isinstance(node, ast.FunctionDef) and node.name == name
            )
            selected.append(executable(node))
            sites[name] = dict(
                source=path,
                first_line=node.lineno,
                last_line=node.end_lineno,
                ast_sha256=hashlib.sha256(
                    ast.dump(node, include_attributes=False).encode()
                ).hexdigest(),
            )
    cls = next(
        node
        for node in trees["betse/science/cells.py"].body
        if isinstance(node, ast.ClassDef) and node.name == "Cells"
    )
    methods = [
        executable(node)
        for node in cls.body
        if isinstance(node, ast.FunctionDef) and node.name in ("graphLaplacian", "curl", "HH_cells")
    ]
    selected.append(
        ast.ClassDef(name="CapturedCells", bases=[], keywords=[], decorator_list=[], body=methods)
    )
    namespace = dict(
        np=np,
        copy=copy,
        BetseSimConfException=ValueError,
        BetseSimUnstableException=ValueError,
        logs=SimpleNamespace(log_info=lambda *_: None, log_debug=lambda *_: None),
        SmoothBivariateSpline=SmoothBivariateSpline,
    )
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=selected, type_ignores=[])),
            "<pinned ordinary mechanics>",
            "exec",
        ),
        namespace,
    )
    namespace["stb"] = SimpleNamespace(check_v=namespace["check_v"])
    simulator = next(
        node
        for node in trees["betse/science/sim.py"].body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    )
    loop = next(
        node
        for node in simulator.body
        if isinstance(node, ast.FunctionDef) and node.name == "_run_sim_core_loop"
    )
    timed = next(node for node in loop.body if isinstance(node, ast.For))
    blocks = [
        next(
            node
            for node in timed.body
            if isinstance(node, ast.If) and ast.unparse(node.test) == test
        )
        for test in ("p.deform_osmo", "p.fluid_flow", "p.deformation")
    ]
    callers = []
    for index, node in enumerate(blocks):
        wrapper = ast.parse("def block_" + str(index) + "(self,cells,t,p):\n pass").body[0]
        wrapper.body = [copy.deepcopy(node)]
        callers.append(wrapper)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=callers, type_ignores=[])),
            "<unchanged ordinary mechanics guards>",
            "exec",
        ),
        namespace,
    )
    return namespace, pins, sites


def evaluate(inputs):
    namespace, pins, sites = capture()
    raw = inputs["definition"]
    geometry, policy, parameters = (raw[key] for key in ("geometry", "policy", "parameters"))
    if policy["fluid_flow"] or policy["td_deform"] or policy["solver"] != "FULL":
        raise ValueError("No forced enabled flow/dynamic branch in ordinary capture")
    mesh = geometry["layout"]
    p = SimpleNamespace(
        deform_osmo=policy["deform_osmo"],
        fluid_flow=False,
        td_deform=False,
        deformation=policy["deformation"],
        is_ecm=policy["is_ecm"],
        molecules_enabled=policy["molecules_enabled"],
        grn_enabled=policy["grn_enabled"],
        fixed_cluster_bound=parameters["fixed_boundary"],
        lame_mu=parameters["young_modulus_Pa"] / (2 * (1 + 0.49)),
        galvanotropism=parameters["galvanotropism_m2_V"],
        dt=parameters["dt_s"],
        R=parameters["gas_constant_J_mol_K"],
        aquaporins=parameters["aquaporin_fraction"],
        mu_water=0.01,
        tm=parameters["membrane_thickness_m"],
        rho=parameters["density_kg_m3"],
        cell_height=mesh["cell_height_m"],
    )
    cells = namespace["CapturedCells"]()
    cells.cell_nn_i = np.asarray(mesh["neighbors"], int)
    cells.nn_len = np.asarray(mesh["lengths_m"])
    cells.nn_tx, cells.nn_ty = np.asarray(mesh["force_directions"]).T
    cells.cell_nn_tx, cells.cell_nn_ty = np.asarray(mesh["curl_directions"]).T
    cells.M_sum_mems = np.asarray(mesh["sum_membranes"], dtype=float)
    cells.num_mems = cells.M_sum_mems.sum(axis=1)
    cells.mem_vects_flat = np.column_stack(
        (np.zeros((len(cells.nn_len), 2)), np.asarray(mesh["force_directions"]))
    )
    cells.mem_sa, cells.mem_vol = (
        np.asarray(mesh[key]) for key in ("membrane_area_m2", "membrane_volume_m3")
    )
    cells.cell_sa, cells.cell_vol = (
        np.asarray(mesh[key]) for key in ("cell_area_m2", "cell_volume_m3")
    )
    cells.mesh = SimpleNamespace(
        vor_edge_len=np.asarray(mesh["dual_edge_m"]),
        tri_edge_len=np.asarray(mesh["primal_edge_m"]),
        delta_tri_0=np.asarray(mesh["incidence"], dtype=float),
        delta_tri_0_inv=np.asarray(mesh["incidence_inverse"], dtype=float),
        vor_sa=np.asarray(mesh["dual_area_m2"]),
    )
    cells.graphLaplacian(p)
    cells.map_cell2ecm = np.asarray(geometry["cell_to_environment"], int)
    cells.cell_centres, cells.mem_verts = (
        np.asarray(mesh[key]) for key in ("centers_m", "vertices_m")
    )
    cells.cell_to_mems = [np.flatnonzero(row).tolist() for row in cells.M_sum_mems]
    cells.mem_to_cells = np.argmax(cells.M_sum_mems, axis=0)
    cells.cell_verts = np.asarray(
        [cells.mem_verts[indices] for indices in cells.cell_to_mems], dtype=object
    )
    sim = SimpleNamespace(
        **{
            key: np.array(value, dtype=float)
            for key, value in inputs["initial"].items()
            if not key.startswith("display_")
        },
        cdl=len(geometry["cell_ids"]),
        mdl=len(cells.nn_len),
        edl=len(geometry["environment_ids"]),
        cellso=copy.deepcopy(cells),
        cell_centres_time=[],
        cell_verts_time=[],
    )
    sim.cellso.cell_centres = np.asarray(inputs["initial"]["display_centres_m"])
    imported_vertices = np.asarray(inputs["initial"]["display_vertices_m"], dtype=float)
    # Imported display state is distinct from the original source mem_verts
    # used as interpolation targets and additive coordinates at every sample.
    sim.cellso.cell_verts = np.asarray(
        [imported_vertices[indices].copy() for indices in cells.cell_to_mems], dtype=object
    )
    history, raw_calls, spline_calls = [], [], []
    rng_before = copy.deepcopy(np.random.get_state())
    latest, hh = {}, []
    codes = {
        namespace[name].__code__: name
        for name in ("getDeformation", "osmotic_P", "implement_deform_timestep")
    }
    codes[namespace["CapturedCells"].HH_cells.__code__] = "HH_cells"

    def trace(frame, event, arg):
        if event == "return" and frame.f_code in codes:
            name = codes[frame.f_code]
            observed = {
                key: np.array(value, copy=True) if isinstance(value, np.ndarray) else value
                for key, value in frame.f_locals.items()
                if isinstance(value, (np.ndarray, float, int, bool))
            }
            latest[name] = observed
            raw_calls.append(dict(function=name, locals=observed, returned=copy.deepcopy(arg)))
            if name == "HH_cells":
                hh.append(copy.deepcopy(arg))
        return trace

    def spline(*args, **kwargs):
        result = SmoothBivariateSpline(*args, **kwargs)
        spline_calls.append(
            dict(
                inputs=[np.array(value, copy=True) for value in args],
                options=kwargs,
                knots=result.get_knots(),
                coefficients=result.get_coeffs(),
                residual=result.get_residual(),
            )
        )
        return result

    namespace["SmoothBivariateSpline"] = spline

    def display_vertices():
        values = np.empty_like(cells.mem_verts, dtype=float)
        for indices, vertices in zip(cells.cell_to_mems, sim.cellso.cell_verts, strict=True):
            values[indices] = np.asarray(vertices, dtype=float)
        return values

    def cache():
        return {
            key: np.array(getattr(sim, key), copy=True)
            for key in inputs["initial"]
            if not key.startswith("display_")
        } | dict(
            display_centres_m=sim.cellso.cell_centres.copy(),
            display_vertices_m=display_vertices(),
        )

    failure = None
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        for step, packet in enumerate(inputs["steps"]):
            frames, auxiliary = [], {"flow": None}
            stage = "initial"

            def observe(label, frames=frames):
                frames.append(dict(stage=label, cache=cache()))

            try:
                sim.T = packet["temperature_K"]
                sim.P_cells = np.asarray(packet["pressure_Pa"])
                sim.cc_cells, sim.cc_env = (
                    np.asarray(packet[key]) for key in ("primary_cell_mM", "primary_env_mM")
                )
                for group, enabled in (("molecule", p.molecules_enabled), ("grn", p.grn_enabled)):
                    if enabled:
                        molecules = {
                            str(i): SimpleNamespace(c_cells=np.asarray(a), c_env=np.asarray(b))
                            for i, (a, b) in enumerate(
                                zip(
                                    packet[group + "_cell_mM"],
                                    packet[group + "_env_mM"],
                                    strict=True,
                                )
                            )
                        }
                        setattr(
                            sim,
                            "molecules" if group == "molecule" else "grn",
                            SimpleNamespace(core=SimpleNamespace(molecules=molecules)),
                        )
                if "electric_field_V_m" in packet:
                    sim.E_cell_x, sim.E_cell_y = np.asarray(packet["electric_field_V_m"])
                else:
                    for name in ("E_cell_x", "E_cell_y"):
                        if hasattr(sim, name):
                            delattr(sim, name)
                observe("initial")
                previous_trace = sys.gettrace()
                sys.settrace(trace)
                try:
                    stage = "osmotic_pressure"
                    namespace["block_0"](sim, cells, packet["clock_s"], p)
                    if p.deform_osmo:
                        auxiliary["osmotic"] = dict(
                            zip(
                                (
                                    "cell_osmotic_pressure_Pa",
                                    "environment_osmotic_pressure_Pa",
                                    "delta_pressure_Pa",
                                    "water_velocity_m_s",
                                    "divergence_per_s",
                                    "PP_native",
                                ),
                                (
                                    getattr(sim, key).copy()
                                    for key in (
                                        "osmo_P_cell",
                                        "osmo_P_env",
                                        "osmo_P_delta",
                                        "u_osmo",
                                        "div_u_osmo",
                                        "PP",
                                    )
                                ),
                                strict=True,
                            )
                        )
                        observe("osmotic_pressure")
                    stage = "disabled_flow_gate"
                    namespace["block_1"](sim, cells, packet["clock_s"], p)
                    observe("disabled_flow_gate")
                    stage = "steady_deformation"
                    namespace["block_2"](sim, cells, packet["clock_s"], p)
                    if p.deformation:
                        local = latest["getDeformation"]
                        potential, rotated_x, rotated_y, *_ = hh[-1]
                        _, _, divergence = cells.curl(-sim.d_cells_y, sim.d_cells_x, 0)
                        auxiliary["steady"] = dict(
                            displacement_m=np.stack((sim.d_cells_x, sim.d_cells_y)),
                            pressure_gradient_Pa_m=np.stack((sim.gPxc, sim.gPyc)),
                            unprojected_elastic_m=np.stack((local["dxo"], local["dyo"])),
                            rotational_m=np.stack((rotated_x, rotated_y)),
                            rotation_potential=potential,
                            osmotic_addition_native=np.stack((local["dxco"], local["dyco"]))
                            if p.deform_osmo
                            else np.zeros((2, sim.cdl)),
                            electric_addition_m=np.stack((sim.E_cell_x, sim.E_cell_y))
                            * p.galvanotropism,
                            divergence_numeric=divergence,
                        )
                        observe("steady_deformation")
                    candidate = cache()
                    sample = None
                    if packet["sample"]:
                        stage = "conditional_sample_after_supplied_material_voltage_barrier"
                        namespace["implement_deform_timestep"](
                            sim, sim.cellso, packet["clock_s"], p
                        )
                        sample = dict(
                            vertices_m=display_vertices(),
                            cell_centres_m=sim.cellso.cell_centres.copy(),
                        )
                    history.append(
                        dict(
                            frames=frames,
                            auxiliaries=auxiliary,
                            candidate=candidate,
                            sample=sample,
                            carried_cache=cache(),
                        )
                    )
                finally:
                    sys.settrace(previous_trace)
            except Exception as error:
                failure = dict(
                    stage=stage,
                    step=step,
                    type=type(error).__name__,
                    reason=str(error),
                    traceback=traceback.format_exc(),
                )
                history.append(
                    dict(
                        frames=frames,
                        auxiliaries=auxiliary,
                        candidate=cache(),
                        sample=None,
                        carried_cache=cache(),
                    )
                )
                break
    rng_after = np.random.get_state()
    unchanged = (
        rng_before[0] == rng_after[0]
        and np.array_equal(rng_before[1], rng_after[1])
        and rng_before[2:] == rng_after[2:]
    )
    return dict(
        history=history,
        failure=failure,
        warnings=[str(item.message) for item in caught],
        raw_calls=raw_calls,
        spline_calls=spline_calls,
        complete_native_objects=dict(sim=sim, physical_cells=cells, parameters=p),
        final_cache=cache(),
        physical_geometry=dict(
            centres_m=cells.cell_centres,
            vertices_m=cells.mem_verts,
            cell_area_m2=cells.cell_sa,
            cell_volume_m3=cells.cell_vol,
            laplacian=cells.lapGJ,
            laplacian_inverse=cells.lapGJinv,
        ),
        graph_provenance=raw["provenance"],
        native_source_sha256=pins["source_sha256"],
        source_sites=sites,
        RNG_before=rng_before,
        RNG_after=rng_after,
        RNG_unchanged=bool(unchanged),
        flow_forced_on=False,
        timeDeform_executed=False,
        physical_world_rebuilt=False,
        full_native_seed_or_solver_executed=False,
        only_supplied_display_barrier=True,
    )
