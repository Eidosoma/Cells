"""Actual update_V with explicit current-prefix/BVP dependency adapter.

Environment HH/Gaussian readouts and inverse construction are not executed.
Carried material calls reuse the qualified isolated literal native join.
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
from types import SimpleNamespace

import numpy as np

from validation.betse import betse_normal_current_native as current_native
from validation.betse import betse_normal_ion_join_native as material_native

PROTOCOL = Path(__file__).with_name("betse_normal_voltage_protocol.json")
write_archive = current_native.write_archive


def capture():
    pins = json.loads(PROTOCOL.read_text())["native_source"]
    root = Path(pins["checkout"])
    installed = Path(pins["installed_package"]).parent
    trees = {}
    for name, expected in pins["source_sha256"].items():
        raw = (root / name).read_bytes()
        if (
            hashlib.sha256(raw).hexdigest() != expected
            or hashlib.sha256((installed / name).read_bytes()).hexdigest() != expected
        ):
            raise ValueError("Pinned voltage source changed: " + name)
        trees[name] = ast.parse(raw, filename=str(root / name))
    if (
        subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
        != pins["revision"]
    ):
        raise ValueError("Pinned source revision changed")
    update = next(
        n
        for n in ast.walk(trees["betse/science/sim.py"])
        if isinstance(n, ast.FunctionDef) and n.name == "update_V"
    )
    get_current = next(
        n
        for n in trees["betse/science/physics/ion_current.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "get_current"
    )
    branch = next(n for n in get_current.body if isinstance(n, ast.If))
    start = next(
        i
        for i, n in enumerate(branch.orelse)
        if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) == "div_Jb"
    )
    boundary = copy.deepcopy(branch.orelse[start:])
    assert ast.unparse(boundary[-1].targets[0]) == "sim.Phi_b" and len(boundary) == 7
    check = next(
        n
        for n in trees["betse/science/sim_toolbox.py"].body
        if isinstance(n, ast.FunctionDef) and n.name == "check_v"
    )
    sites = {
        n.name: dict(
            first_line=n.lineno,
            last_line=n.end_lineno,
            AST_sha256=hashlib.sha256(ast.dump(n, include_attributes=False).encode()).hexdigest(),
        )
        for n in (update, get_current, check)
    }
    sites["boundary_block"] = dict(first_line=boundary[0].lineno, last_line=boundary[-1].end_lineno)

    class Observe(ast.NodeTransformer):
        def visit_Assign(self, node):
            if ast.unparse(node.targets[0]) == "rho_surf":
                return [node, *ast.parse("_observe_voltage('surface_charge_C_m2',rho_surf)").body]
            return node

    observed = Observe().visit(copy.deepcopy(update))
    bvp = material_native.wrapper(
        "boundary",
        "sim,cells",
        boundary + ast.parse("_observe_voltage('boundary_rhs_V_m2',div_Jb)").body,
    )
    namespace = {"np": np, "BetseSimUnstableException": material_native.NativeUnstable}
    exec(
        compile(
            ast.fix_missing_locations(
                ast.Module(body=[observed, bvp, copy.deepcopy(check)], type_ignores=[])
            ),
            "<pinned update_V/current-BVP adapter>",
            "exec",
        ),
        namespace,
    )
    current_source, current_sites, _ = current_native.capture()

    def dependency(sim, cells, parameters):
        current_source["current"](sim, cells, parameters)
        namespace["boundary"](sim, cells)

    namespace["get_current"] = dependency
    return namespace, current_source, sites | {"current_prefix": current_sites["current"]}, pins


def current_values(sim, observed):
    return dict(
        charge_density_C_m3=sim.rho_cells.copy(),
        membrane_current_A_m2=sim.Jmem.copy(),
        junction_current_A_m2=sim.Jgj.copy(),
        raw_normal_current_A_m2=observed["raw_normal_current_A_m2"],
        average_normal_current_A_m2=observed["average_normal_current_A_m2"],
        normal_current_A_m2=sim.Jn.copy(),
        inward_membrane_current_A=sim.I_mem.copy(),
        cell_current_xy_A_m2=np.column_stack((sim.J_cell_x, sim.J_cell_y)),
        projected_cell_current_A_m2=sim.Jc.copy(),
    )


def evaluate(inputs):
    if not 1 <= len(inputs["drives"]) <= 16:
        raise ValueError("Refuse unbounded coupled voltage capture")
    rng_before = copy.deepcopy(np.random.get_state())
    namespace, current_source, sites, pins = capture()
    cd, vd = inputs["current_definition"], inputs["voltage_definition"]
    state = copy.deepcopy(inputs["initial"])
    history = []
    failure = None
    captures = []
    all_warnings = []
    for index, forcing in enumerate(inputs["drives"]):
        material = material_native.evaluate(
            dict(definition=inputs["ion_definition"], initial=state, steps=[forcing["material"]])
        )
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
        observations, current_observations = {}, {}
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
        all_warnings.extend(str(w.message) for w in caught)
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
                current=current_values(sim, current_observations),
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
        kind="cells.native_normal_voltage_capture@1",
        inputs=inputs,
        status="source_refused" if failure else "source_completed",
        history=history,
        failure=failure,
        warnings=all_warnings,
        native_source=pins,
        source_sites=sites,
        RNG_before=rng_before,
        RNG_after=rng_after,
        RNG_unchanged=(
            all(record["RNG_unchanged"] for record in captures)
            and rng_before[0] == rng_after[0]
            and np.array_equal(rng_before[1], rng_after[1])
            and rng_before[2:] == rng_after[2:]
        ),
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
            raise ImportError("Native voltage import denied: " + name)
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
