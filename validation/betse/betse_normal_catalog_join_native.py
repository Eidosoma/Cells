"""Actual maintained-pool pump blocks before active native ion/gate/voltage."""

import argparse
import ast
import builtins
import copy
import hashlib
import importlib.abc
import json
import sys
import traceback
import warnings
from pathlib import Path
from types import MethodType, SimpleNamespace

import numpy as np

from validation.betse import betse_normal_catalog_join_native_helpers as channel_helpers
from validation.betse import betse_normal_gated_join_native as gated_native
from validation.betse import betse_normal_ion_join_native as material_native
from validation.betse import betse_normal_voltage_native as voltage_native
from validation.betse.betse_normal_channel_join_runtime import inventory as runtime_inventory

PROTOCOL = Path(__file__).with_name("betse_normal_catalog_join_protocol.json")
write_archive = voltage_native.write_archive


def pump_material_source():
    source, sites, pins = material_native.capture()
    root = Path(pins["checkout"])
    simulator = ast.parse((root / "betse/science/sim.py").read_bytes())
    toolbox = ast.parse((root / "betse/science/sim_toolbox.py").read_bytes())
    pump = next(
        n for n in toolbox.body if isinstance(n, ast.FunctionDef) and n.name == "pumpNaKATP"
    )
    sites["pumpNaKATP"] = dict(
        first_line=pump.lineno,
        last_line=pump.end_lineno,
        AST_sha256=hashlib.sha256(ast.dump(pump, include_attributes=False).encode()).hexdigest(),
    )
    fields = dict(
        Qnumo="quotient_numerator",
        Qdenomo="quotient_denominator_raw",
        Q="quotient",
        Keq="equilibrium",
        numo_E="saturation_numerator",
        denomo_E="saturation_denominator",
        fwd_co="saturation",
        f_Na="raw_sodium_flux_mol_m2_s",
        f_K="raw_potassium_flux_mol_m2_s",
    )

    def observe(name, expression):
        return ast.parse("_pump_local('" + name + "'," + expression + ")").body

    class PumpObserve(ast.NodeTransformer):
        def visit_Assign(self, node):
            target = ast.unparse(node.targets[0])
            if target in fields:
                return [node, *observe(fields[target], target)]
            if target == "inds_Z":
                return [node, *observe("zero_denominator_indices", "inds_Z[0]")]
            if target == "Qdenomo[inds_Z]":
                return [node, *observe("quotient_denominator_used", "Qdenomo")]
            return node

    pump = PumpObserve().visit(copy.deepcopy(pump))
    arguments = {
        "sodium_at_mem_mM": "cNai",
        "potassium_at_mem_mM": "cKi",
        "sodium_bath_mM": "cNao",
        "potassium_bath_mM": "cKo",
        "voltage_before_nonce_V": "Vm",
        "runtime_temperature_K": "T",
    }
    argument_copies = []
    for name, argument in arguments.items():
        argument_copies.extend(observe(name, argument))
    pump.body[1:1] = argument_copies
    loop = next(
        n
        for n in ast.walk(simulator)
        if isinstance(n, ast.FunctionDef) and n.name == "_run_sim_core_loop"
    )
    resets = sorted(
        (
            n
            for n in ast.walk(loop)
            if isinstance(n, ast.Expr)
            and ast.unparse(n) in ("self.fluxes_mem.fill(0)", "self.fluxes_gj.fill(0)")
        ),
        key=lambda n: n.lineno,
    )
    guards = sorted(
        (
            n
            for n in ast.walk(loop)
            if isinstance(n, ast.If)
            and ast.unparse(n.test) in ("p.alpha_NaK == 0.0", "p.alpha_NaK > 0.0")
        ),
        key=lambda n: n.lineno,
    )
    moving = [
        n
        for n in ast.walk(loop)
        if isinstance(n, ast.For) and ast.unparse(n.iter) == "self.movingIons"
    ]
    commit = [
        n
        for n in ast.walk(loop)
        if isinstance(n, ast.Expr) and ast.unparse(n) == "self.update_all_concs(cells, p)"
    ]
    if (len(resets), len(guards), len(moving), len(commit)) != (2, 2, 1, 1):
        raise ValueError("Source pump/normal-loop selection changed")
    sites["pump_guards"] = dict(
        selected_lines=[n.lineno for n in guards],
        AST_sha256=hashlib.sha256(
            ast.dump(ast.Module(body=guards, type_ignores=[]), include_attributes=False).encode()
        ).hexdigest(),
    )

    class LoopObserve(ast.NodeTransformer):
        def visit_Assign(self, node):
            node = self.generic_visit(node)
            target = ast.unparse(node.targets[0])
            if isinstance(node.targets[0], ast.Tuple) and "self.rate_NaKATP" in target:
                return [node, *observe("raw_rate_proxy_mol_m2_s", "self.rate_NaKATP")]
            if target == "fNa_NaK":
                return [node, *observe("scaled_sodium_flux_mol_m2_s", "fNa_NaK")]
            if target == "fK_NaK":
                return [node, *observe("scaled_potassium_flux_mol_m2_s", "fK_NaK")]
            return node

        def visit_AugAssign(self, node):
            target = ast.unparse(node.target)
            if target == "self.fluxes_mem[self.iNa]":
                return [node, *observe("applied_sodium_flux_mol_m2_s", "fNa_NaK")]
            if target == "self.fluxes_mem[self.iK]":
                return [node, *observe("applied_potassium_flux_mol_m2_s", "fK_NaK")]
            if target == "self.fluxes_mem[i]":
                return [node, *ast.parse("_observe('membrane_flux',i,self)").body]
            return node

        def visit_Expr(self, node):
            calls = {
                "self.update_gj(cells, p, t, i)": "junction_flux",
                "self.update_intra(cells, p, i)": "refresh_at_mem",
            }
            if ast.unparse(node) in calls:
                return [
                    node,
                    *ast.parse("_observe('" + calls[ast.unparse(node)] + "',i,self)").body,
                ]
            return node

    guards = [LoopObserve().visit(copy.deepcopy(n)) for n in guards]
    moving = LoopObserve().visit(copy.deepcopy(moving[0]))
    body = copy.deepcopy(resets) + ast.parse("_observe('reset_flux',None,self)").body + guards
    body += (
        ast.parse("_observe('pump_accumulated',None,self)").body
        + [moving]
        + ast.parse("_late(self,cells,p,t)").body
        + copy.deepcopy(commit)
    )
    scoped = material_native.wrapper("scoped_step", "self,cells,p,t", body)
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[pump, scoped], type_ignores=[])),
            "<pinned native pump/active normal source join>",
            "exec",
        ),
        source,
    )
    source["stb"].pumpNaKATP = source["pumpNaKATP"]
    return source, sites, pins


def material_capture(
    inputs,
    gate_definition,
    gate_cache=None,
    initial_block=None,
    pump_definition=None,
    pump_packet=None,
    pump_rate_cache=None,
    channel_definition=None,
    channel_live=None,
    channel_caches=None,
    channel_calls=None,
    incoming_extra_charge=None,
    incoming_extra_current=None,
    incoming_calcium_rate_cache=None,
):
    source, sites, pins = pump_material_source()
    gate_class, gate_pins = gated_native.authenticated_gate()
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
    if p["is_ecm"] is not False:
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
        v_sensitive_gj=True,
        gj_vthresh=gate_definition["threshold_mV"],
        gj_min=gate_definition["minimum"],
    )
    for key, value in (pump_definition["maintained"] | pump_definition["kinetics"]).items():
        setattr(parameters, key, value)
    parameters.alpha_NaK = pump_packet["alpha_NaK"]
    sim.iNa = ions["ids"].index(pump_definition["sodium_id"])
    sim.iK = ions["ids"].index(pump_definition["potassium_id"])
    sim.NaKATP_block = np.asarray(pump_packet["block"], np.float64)
    sim.rho_pump = np.asarray(pump_packet["rho_pump"], np.float64)
    sim.met_concs = (
        None
        if pump_packet["met_concs"] is None
        else {key: np.asarray(value, np.float64) for key, value in pump_packet["met_concs"].items()}
    )
    sim.rate_NaKATP = np.asarray(pump_rate_cache, np.float64).copy()
    incoming_proxy = sim.rate_NaKATP.copy()
    pump_observations = {}
    source["_pump_local"] = lambda name, value: pump_observations.__setitem__(
        name, np.array(value, copy=True)
    )
    gate_updates = []
    gate_index = [0]

    class ObservedGate(gate_class):
        def run(self, actual, geometry, parameters):
            opening = actual.gjopen.copy()
            pre_voltage = actual.vgj.copy()
            observed = {}
            gate_class.run.__globals__["_gate_local"] = lambda name, value: observed.__setitem__(
                name, np.array(value, copy=True)
            )
            gate_class.run(self, actual, geometry, parameters)
            gate_index[0] += 1
            dt_ms = parameters.dt * 1e3
            raw_beta = observed["raw_beta_per_ms"]
            unblocked = observed["opening_unblocked"]
            gate_updates.append(
                dict(
                    ion_id=ions["ids"][active_ion[0]],
                    update_index=gate_index[0],
                    voltage_before_nonce_V=pre_voltage,
                    opening_before=opening,
                    alpha_per_ms=self.alpha.copy(),
                    raw_beta_per_ms=raw_beta,
                    beta_per_ms=self.beta.copy(),
                    opening_unblocked=unblocked,
                    opening_stored=actual.gjopen.copy(),
                    dt_s=parameters.dt,
                    dt_ms=dt_ms,
                    actual_class_cache=copy.deepcopy(vars(self)),
                )
            )

    sim.gj_block = np.asarray(
        initial_block if initial_block is not None else inputs["steps"][0]["junction_block"],
        np.float64,
    )
    initialization = None
    initialization_observed = {}
    gate_class.init.__globals__["_gate_local"] = lambda name, value: (
        initialization_observed.__setitem__(name, np.array(value, copy=True))
    )
    with warnings.catch_warnings(record=True) as initialization_warnings:
        warnings.simplefilter("always")
        if gate_cache is None:
            before_open = sim.gjopen.copy()
            sim.gj_funk = ObservedGate(sim, cells, parameters)
            initialization = dict(
                cached_voltage_V=sim.vgj.copy(),
                block=sim.gj_block.copy(),
                sim_open_before=before_open,
                sim_open_after=sim.gjopen.copy(),
                raw_beta_per_ms=initialization_observed["raw_beta_per_ms"],
                actual_class_cache=copy.deepcopy(vars(sim.gj_funk)),
            )
        else:
            sim.gj_funk = object.__new__(ObservedGate)
            vars(sim.gj_funk).update(copy.deepcopy(gate_cache["attributes"]))
            gate_index[0] = gate_cache["updates"]
    active_ion = [None]
    before = copy.deepcopy(np.random.get_state())
    frames = []

    def observe(stage, i, actual):
        if i is not None:
            active_ion[0] = i
        frames.append(
            dict(
                stage=stage,
                ion_id=None if i is None else ions["ids"][i],
                values=material_native.values(actual),
            )
        )

    if channel_definition["calcium_handler"] is not None:
        sim.rate_CaATP = np.asarray(incoming_calcium_rate_cache, np.float64).copy()
    source["_observe"] = observe
    sim.extra_rho_cells = np.asarray(incoming_extra_charge, np.float64).copy()
    sim.extra_J_mem = np.asarray(incoming_extra_current, np.float64).copy()
    source["_late"], channel_capture = channel_helpers.setup(
        sim,
        cells,
        parameters,
        channel_definition,
        channel_live,
        channel_caches,
        channel_calls,
        source,
        observe,
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
                    final_state=material_native.values(sim),
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
        final_state=material_native.values(sim),
        raw_simulator_state=copy.deepcopy(
            {
                key: value
                for key, value in vars(sim).items()
                if not callable(value) and key not in {"gj_funk", "dyna"}
            }
        ),
        source_parameters=vars(parameters),
        source_geometry=vars(cells),
        failure=failure,
        warnings=[str(w.message) for w in caught]
        + [str(w.message) for w in initialization_warnings],
        gate_initialization=initialization,
        gate_updates=gate_updates,
        gate_cache=dict(attributes=copy.deepcopy(vars(sim.gj_funk)), updates=gate_index[0]),
        gate_source=gate_pins,
        channel_capture={key: value for key, value in channel_capture.items() if key != "caches"},
        channel_caches=channel_capture["caches"](),
        pump_observations=pump_observations,
        rate_proxy_before=incoming_proxy,
        rate_proxy_after=sim.rate_NaKATP.copy(),
        native_source=pins,
        source_sites=sites,
        RNG_before=before,
        RNG_after=after,
        RNG_unchanged=before[0] == after[0]
        and np.array_equal(before[1], after[1])
        and before[2:] == after[2:],
        runtime=runtime_inventory() | dict(numpy=np.__version__),
        scope=(
            "Actual normal moving-ion loop and final material commit only; "
            "Maintained NaK pump and late empty-molecule channel network included; "
            "no ECM/events/other handlers/voltage in this nested stage"
        ),
    )


def evaluate(inputs):
    if not 1 <= len(inputs["drives"]) <= 16:
        raise ValueError("Refuse unbounded coupled voltage capture")
    rng_before = copy.deepcopy(np.random.get_state())
    namespace, current_source, sites, pins = voltage_native.capture()
    cd, vd = (inputs["current_definition"], inputs["voltage_definition"])
    state = copy.deepcopy(inputs["initial"])
    history = []
    failure = None
    captures = []
    gate_cache = None
    pump_rate_cache = copy.deepcopy(inputs["initial_rate_proxy_mol_m2_s"])
    channel_caches = None
    channel_calls = None
    all_warnings = []
    channel_initialization_failure = None
    for index, forcing in enumerate(inputs["drives"]):
        try:
            material = material_capture(
                dict(
                    definition=inputs["ion_definition"], initial=state, steps=[forcing["material"]]
                ),
                inputs["gate_definition"],
                gate_cache,
                inputs["initial_gate_block"],
                inputs["pump_definition"],
                forcing["pump"],
                pump_rate_cache,
                inputs["channel_definition"]
                | dict(ion_ids=inputs["ion_definition"]["ions"]["ids"]),
                forcing["channels"],
                channel_caches,
                channel_calls,
                forcing["extra_charge_C_m3"],
                forcing["extra_current_A_m2"],
                inputs["initial_calcium_rate_proxy_mol_m2_s"],
            )
        except channel_helpers.NativeChannelInitializationRefused as error:
            channel_initialization_failure = error.partial
            failure = dict(
                type=error.partial["source_exception"],
                message=str(error),
                traceback=traceback.format_exc(),
                call_index=index + 1,
                stage="channel_initialization",
            )
            history.append(
                dict(
                    call_index=index + 1,
                    material=None,
                    failure=failure,
                    voltage=None,
                    final_state=copy.deepcopy(state),
                )
            )
            break
        pump_rate_cache = material["rate_proxy_after"]
        gate_cache = material["gate_cache"]
        channel_caches = material["channel_caches"]
        channel_calls = material["channel_capture"]["calls"]
        captures.append(material)
        if material["status"] != "source_completed":
            failure = dict(
                type="MaterialDependencyRefused",
                call_index=index + 1,
                source_failure=material["failure"],
                message="Actual material stage refused before current/voltage",
            )
            history.append(
                dict(
                    call_index=index + 1,
                    material=material,
                    failure=failure,
                    voltage=None,
                    final_state=material["final_state"],
                )
            )
            break
        sim = SimpleNamespace(**copy.deepcopy(material["raw_simulator_state"]))
        cells = SimpleNamespace(**copy.deepcopy(material["source_geometry"]))
        cells.cell_sa = np.asarray(cd["geometry"]["cell_area_m2"], np.float64)
        cells.diviterm = np.asarray(vd["geometry"]["diviterm_m"], np.float64)
        cells.R_rads = np.asarray(vd["geometry"]["radius_m"], np.float64)
        cells.X = np.zeros(vd["grid"]["shape"])
        cells.delta = vd["grid"]["delta_m"]
        cells.map_mem2ecm = np.asarray(vd["grid"]["membrane_to_grid"], np.int64)
        cells.lapENVinv = np.asarray(vd["grid"]["inverse_m2"], np.float64)
        p = vd["parameters"]
        parameters = SimpleNamespace(
            F=cd["parameters"]["F_C_mol"],
            R=p["R_J_mol_K"],
            T=p["configured_temperature_K"],
            cm=p["capacitance_F_m2"],
            dt=forcing["material"]["dt_s"],
            cell_polarizability=p["polarizability"],
            true_cell_size=p["true_cell_size_m"],
            cell_radius=p["cell_radius_m"],
        )
        current_source["sharpness"](
            parameters, {"sharpness cell": cd["parameters"]["sharpness_cell"]}
        )
        current_source["weights"](sim, cells, parameters)
        sim.D_free = np.asarray(vd["ions"]["free_diffusion_m2_s"], np.float64)
        sim.bound_V = copy.deepcopy(forcing["boundary_V"])
        sim.extra_rho_cells = np.asarray(
            material["raw_simulator_state"]["extra_rho_cells"], np.float64
        )
        sim.extra_J_mem = np.asarray(material["raw_simulator_state"]["extra_J_mem"], np.float64)
        observations, current_observations = ({}, {})
        namespace["_observe_voltage"] = lambda name, value, actual=observations: actual.__setitem__(
            name, np.array(value, copy=True)
        )
        current_source["_observe"] = lambda name, value, actual=current_observations: (
            actual.__setitem__(name, np.array(value, copy=True))
        )
        old = sim.vm.copy()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                namespace["update_V"](sim, cells, parameters)
                namespace["check_v"](sim.vm)
            except Exception as error:
                failure = dict(
                    type=type(error).__name__,
                    message=str(error),
                    traceback=traceback.format_exc(),
                    call_index=index + 1,
                )
        all_warnings.extend((str(w.message) for w in caught))
        voltage = dict(
            boundary_rhs_V_m2=observations["boundary_rhs_V_m2"],
            boundary_potential_V=sim.Phi_b.copy(),
            conductivity_S_m=sim.sigma_cell.copy(),
            surface_charge_C_m2=observations["surface_charge_C_m2"],
            voltage_V=sim.vm.copy(),
            mean_voltage_V=sim.vm_ave.copy(),
            cell_field_xy_V_m=np.column_stack((sim.E_cell_x, sim.E_cell_y)),
            normal_cell_field_V_m=sim.Emc.copy(),
            derivative_V_s=sim.dvm.copy(),
        )
        state = copy.deepcopy(material["final_state"])
        state["voltage_V"] = sim.vm.copy()
        history.append(
            dict(
                call_index=index + 1,
                material=material,
                current=voltage_native.current_values(sim, current_observations),
                old_voltage_V=old,
                voltage=voltage,
                final_state=state,
                failure=failure,
                raw_simulator_state=vars(sim),
                source_parameters=vars(parameters),
            )
        )
        if failure:
            break
    rng_after = np.random.get_state()
    return dict(
        kind="cells.native_normal_catalog_join_capture@1",
        inputs=inputs,
        status="source_refused" if failure else "source_completed",
        history=history,
        failure=failure,
        warnings=all_warnings,
        native_source=pins,
        source_sites=sites,
        RNG_before=rng_before,
        RNG_after=rng_after,
        RNG_unchanged=all((record["RNG_unchanged"] for record in captures))
        and rng_before[0] == rng_after[0]
        and np.array_equal(rng_before[1], rng_after[1])
        and (rng_before[2:] == rng_after[2:]),
        runtime=runtime_inventory() | dict(numpy=np.__version__),
        dependency_adapter=(
            "Actual B23 current prefix plus boundary block; "
            "environment HH/Gaussian readouts omitted"
        ),
        inverse_preparation_executed=False,
        gate_enabled=True,
        gate_source=captures[0]["gate_source"]
        if captures
        else gated_native.authenticated_gate()[1],
        channel_initialization_failure=channel_initialization_failure,
        full_native_solver_correspondence=False,
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
            raise ImportError("Native pump join import denied: " + name)
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
