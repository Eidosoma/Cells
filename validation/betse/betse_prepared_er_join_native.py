"""Original native updates consuming the same complete supplied ER packet.

No native constructor or restart equivalence follows from this capture.
"""

import argparse
import builtins
import copy
import importlib.abc
import json
import sys
import traceback
import warnings
from pathlib import Path
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_er_join_native_er as er_native
from validation.betse.betse_normal_er_join_native import (
    channel_helpers,
    gated_native,
    material_capture,
    runtime_inventory,
    voltage_native,
)

write_archive = voltage_native.write_archive


def restore_supplied_fields(raw):
    """Restore the original float64 array/scalar types at the JSON boundary."""
    if set(raw) != set(er_native.FIELDS):
        raise ValueError("Require every supplied ER field")
    return {
        name: float(raw[name])
        if name == "cm_er"
        else np.asarray(raw[name], dtype=np.float64).copy()
        for name in er_native.FIELDS
    }


def _whole_join(inputs):
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
    calcium_rate_cache = copy.deepcopy(inputs["initial_calcium_rate_proxy_mol_m2_s"])
    channel_caches = None
    channel_calls = None
    all_warnings = []
    er_state_cache = restore_supplied_fields(inputs["prepared_er_input"]["fields"])
    channel_initialization_failure = None
    for index, forcing in enumerate(inputs["drives"]):
        try:
            material = material_capture(
                dict(
                    definition=inputs["ion_definition"],
                    initial=state,
                    steps=[forcing["material"]],
                    er_cell_area_m2=inputs["current_definition"]["geometry"]["cell_area_m2"],
                    er_capacitance_F_m2=inputs["voltage_definition"]["parameters"][
                        "capacitance_F_m2"
                    ],
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
                calcium_rate_cache,
                forcing["calcium"],
                forcing["er_context"],
                er_state_cache,
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
        er_state_cache = copy.deepcopy(material["channel_capture"]["endoretic"]["after"])
        pump_rate_cache = material["rate_proxy_after"]
        if inputs["channel_definition"]["calcium_handler"] is not None:
            calcium_rate_cache = copy.deepcopy(material["raw_simulator_state"]["rate_CaATP"])
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
        kind="cells.native_prepared_er_join_capture@1",
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


def _er_only(inputs):
    rng_before = copy.deepcopy(np.random.get_state())
    before = inputs["pre_er"]
    names = before["er_state"]["ion_ids"]
    sim = SimpleNamespace(
        cc_cells=np.asarray(before["cytosol_mM"], np.float64).copy(),
        cdl=len(before["cell_volume_m3"]),
        iCa=names.index("Ca"),
        zs=np.asarray(before["valence"], np.float64).copy(),
        movingIons=list(before["moving_indices"]),
        T=before["runtime_temperature_K"],
        get_ion=lambda name: names.index(name),
    )
    cells = SimpleNamespace(cell_vol=np.asarray(before["cell_volume_m3"], np.float64).copy())
    parameters = SimpleNamespace(**copy.deepcopy(before["parameters"]))
    parameters.ions_dict = dict.fromkeys(names, True)
    keys = (
        "serca_max",
        "max_er",
        "act_Km_Ca",
        "act_n_Ca",
        "inh_Km_Ca",
        "inh_n_Ca",
        "act_Km_IP3",
        "act_n_IP3",
    )
    trace = er_native.setup(
        sim,
        cells,
        parameters,
        dict(endoretic={k: before["parameters"][k] for k in keys}),
        before["owner_context"],
        restore_supplied_fields(before["er_state"]["fields"]),
    )
    failure = None
    with np.errstate(all="ignore"):
        try:
            sim.endo_retic.update(sim, cells, parameters)
        except Exception as error:
            failure = dict(
                type=type(error).__name__, message=str(error), traceback=traceback.format_exc()
            )
    rng_after = np.random.get_state()
    finite = (
        failure is None
        and np.isfinite(sim.cc_cells).all()
        and all(np.isfinite(value).all() for value in trace["after"].values())
        and all(np.isfinite(value).all() for value in trace["arithmetic"].values())
    )
    return dict(
        kind="cells.native_prepared_ER_only_capture@1",
        inputs=inputs,
        status="source_completed" if finite else "source_refused",
        source_completed=failure is None,
        finite=bool(finite),
        failure=failure,
        endoretic=trace,
        cytosol_after_mM=sim.cc_cells.copy(),
        RNG_before=rng_before,
        RNG_after=rng_after,
        RNG_unchanged=rng_before[0] == rng_after[0]
        and np.array_equal(rng_before[1], rng_after[1])
        and rng_before[2:] == rng_after[2:],
        runtime=runtime_inventory() | dict(numpy=np.__version__),
    )


def evaluate(inputs):
    if inputs.get("kind") == "cells.prepared_owned_ER_only_probe@1":
        result = _er_only(inputs)
    else:
        supplied = inputs["prepared_er_input"]
        if supplied["mode"] != "prepared_owned_ER_before_outer_call_channels_primed_v1" or set(
            supplied["fields"]
        ) != set(er_native.FIELDS):
            raise ValueError("Require the full explicitly supplied prepared state")
        result = _whole_join(inputs)
    result.update(
        supplied_prepared_state=True,
        native_initialization_executed=False,
        native_restart_parity=False,
    )
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    blocked = {"cells", "betse", "jax", "jaxlib"}
    original = builtins.__import__

    def guarded(name, *rest, **kwargs):
        if name.split(".")[0] in blocked:
            raise ImportError("Supplied-state native import denied: " + name)
        return original(name, *rest, **kwargs)

    class Guard(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname.split(".")[0] in blocked:
                raise ImportError("Supplied-state native import denied: " + fullname)

    builtins.__import__ = guarded
    sys.meta_path.insert(0, Guard())
    result = evaluate(json.loads(args.inputs.read_text()))
    loaded = [name for name in sys.modules if name.split(".")[0] in blocked]
    if loaded:
        raise ValueError("Native capture loaded a production module")
    result.update(production_imports_denied=True, loaded_production_modules=loaded)
    write_archive(args.output, result)


if __name__ == "__main__":
    main()
