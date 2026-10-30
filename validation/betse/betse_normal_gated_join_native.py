"""Actual active Gap_Junction class and normal-loop captures; no Cells imports."""

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

from validation.betse import betse_normal_ion_join_native as material_native
from validation.betse import betse_normal_voltage_native as voltage_native

PROTOCOL = Path(__file__).with_name("betse_normal_gated_join_protocol.json")
write_archive = voltage_native.write_archive


def authenticated_gate():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    base = Path(pins["checkout"])
    installed = Path(pins["installed_package"]).parent
    name = "betse/science/channels/gap_junction.py"
    raw = (base / name).read_bytes()
    expected = pins["source_sha256"][name]
    if (
        hashlib.sha256(raw).hexdigest() != expected
        or hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected
    ):
        raise ValueError("Pinned gate source changed")
    if (
        subprocess.check_output(["git", "-C", str(base), "rev-parse", "HEAD"], text=True).strip()
        != pins["revision"]
    ):
        raise ValueError("Pinned revision changed")
    node = next(
        n for n in ast.parse(raw).body if isinstance(n, ast.ClassDef) and n.name == "Gap_Junction"
    )

    class Observe(ast.NodeTransformer):
        def visit_Assign(self, assignment):
            target = ast.unparse(assignment.targets[0])
            if target == "beta":
                return [assignment, *ast.parse("_gate_local('raw_beta_per_ms',beta)").body]
            if (
                target == "sim.gjopen"
                and isinstance(assignment.value, ast.BinOp)
                and isinstance(assignment.value.op, ast.Div)
            ):
                return [assignment, *ast.parse("_gate_local('opening_unblocked',sim.gjopen)").body]
            return assignment

    node = Observe().visit(copy.deepcopy(node))
    namespace = {"np": np, "_gate_local": lambda name, value: None}
    exec(
        compile(
            ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
            "<pinned native Gap_Junction class>",
            "exec",
        ),
        namespace,
    )
    return namespace["Gap_Junction"], dict(
        file=name, sha256=expected, first_line=node.lineno, last_line=node.end_lineno
    )


def material_capture(inputs, gate_definition, gate_cache=None, initial_block=None):
    source, sites, pins = material_native.capture()
    gate_class, gate_pins = authenticated_gate()
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

    source["_observe"] = observe
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
                if not callable(value) and key != "gj_funk"
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
    all_warnings = []
    for index, forcing in enumerate(inputs["drives"]):
        material = material_capture(
            dict(definition=inputs["ion_definition"], initial=state, steps=[forcing["material"]]),
            inputs["gate_definition"],
            gate_cache,
            inputs["initial_gate_block"],
        )
        gate_cache = material["gate_cache"]
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
        sim.extra_rho_cells = np.asarray(forcing["extra_charge_C_m3"], np.float64)
        sim.extra_J_mem = np.asarray(forcing["extra_current_A_m2"], np.float64)
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
        kind="cells.native_normal_gated_join_capture@1",
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
        runtime=dict(
            python=platform.python_version(),
            numpy=np.__version__,
            measured_cpu_affinity=sorted(os.sched_getaffinity(0)),
        ),
        dependency_adapter=(
            "Actual B23 current prefix plus boundary block; "
            "environment HH/Gaussian readouts omitted"
        ),
        inverse_preparation_executed=False,
        gate_enabled=True,
        gate_source=captures[0]["gate_source"],
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
            raise ImportError("Native gated join import denied: " + name)
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
