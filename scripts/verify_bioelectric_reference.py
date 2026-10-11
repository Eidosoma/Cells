"""Qualify independent CPU trajectories and a method candidate for SPEC-001.

No Cells model is run or imported. Write only to a new output directory. Retain
the reference code, case definitions, numerical arrays, failures of alternative
methods, runtime, and hashes. Production/JAX acceptance remains MODEL-003.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.reference_bioelectric import (  # noqa: E402
    Case,
    Control,
    Parameters,
    balances,
    fluxes,
    integrate_reference,
    integrate_rk4_probe,
    local_spectrum,
    panel,
    passive_equilibrium,
    sample_probe,
    trajectory_errors,
)

DT = 0.005
TARGETS = {
    "amount_fmol": 1e-7,
    "leak_fmol": 1e-7,
    "pump_cycles_fmol": 1e-7,
    "voltage_V": 1e-6,
    # Independent quadrature diagnostic, not a required production state field.
    "dissipation_pJ": 1e-6,
}
BALANCE_TARGETS = {"amount_fmol": 1e-10, "charge_as_voltage_V": 1e-8, "energy_pJ": 1e-6}
REFERENCE_FACTOR = 0.1


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def check_limits(values, targets, label, factor=1.0):
    for name, value in values.items():
        require(np.isfinite(value) and value <= targets[name] * factor, f"{label}: {name}={value}")


def inspect_physics(case, times, values):
    max_passive = max_pump = -np.inf
    for time, state in zip(times, values, strict=True):
        voltage = case.parameters.voltage(state[:3])
        leak, cycles, mu, energy = fluxes(
            case.parameters, state[:3], voltage, case.control_at(time)
        )
        max_passive = max(max_passive, float(np.max(leak * mu)) * 1e-15)
        max_pump = max(max_pump, cycles * energy * 1e-15)
    require(max(max_passive, max_pump) <= 1e-24, f"{case.name}: sampled uphill transport")
    require(np.min(np.diff(values[:, 7]), initial=0) >= -1e-10, "Decreasing dissipation quadrature")
    return {
        "minimum_amount_fmol": float(np.min(values[:, :3])),
        "voltage_range_V": [
            float(f(case.parameters.voltage(values[:, :3]))) for f in (np.min, np.max)
        ],
        "max_passive_uphill_power_W": max_passive,
        "max_pump_uphill_power_W": max_pump,
    }


def inspect_controls(case, times, values):
    if case.name == "all_off":
        np.testing.assert_array_equal(values, np.broadcast_to(values[0], values.shape))
    if case.name == "simultaneous_controls":
        off = values[(times >= 2.03) & (times <= 5.07)]
        np.testing.assert_array_equal(off, np.broadcast_to(off[0], off.shape))
    if case.name == "independent_controls":
        pump_off = values[(times >= 2.03) & (times <= 5.07), 6]
        leak_off = values[(times >= 3.11) & (times <= 4.13), 3]
        np.testing.assert_array_equal(pump_off, np.full_like(pump_off, pump_off[0]))
        np.testing.assert_array_equal(leak_off, np.full_like(leak_off, leak_off[0]))
        potassium = values[(times >= 3.11) & (times <= 4.13), 4]
        require(np.ptp(potassium) > 1e-6, "Na leak block incorrectly disables K leak")
    if case.name == "short_pulse":
        require(0.203 in times and 0.207 in times, "Short pulse boundaries missing")
        require(values[-1, 6] > 1e-6, "Sub-step pump pulse disappeared")


def qualify_case(case, output):
    print(f"Qualifying bioelectric reference: {case.name}", flush=True)
    radau = integrate_reference(case)
    bdf = integrate_reference(case, method="BDF")
    refined = integrate_reference(case, rtol=1e-12, atol=1e-14)
    times, values, probe_stats = integrate_rk4_probe(case, DT)
    samples = np.unique(np.r_[times, *(times[:-1] + q * np.diff(times) for q in (0.25, 0.5, 0.75))])
    expected = refined.sample(samples)
    reference_errors = {
        "radau_vs_refined": trajectory_errors(case.parameters, radau.sample(samples), expected),
        "bdf_vs_refined": trajectory_errors(case.parameters, bdf.sample(samples), expected),
    }
    for label, error in reference_errors.items():
        check_limits(error, TARGETS, f"{case.name}/{label}", REFERENCE_FACTOR)
    accepted_errors = trajectory_errors(case.parameters, values, refined.sample(times))
    check_limits(accepted_errors, TARGETS, f"{case.name}/accepted")
    observed = sample_probe(case, times, values, samples, method="hermite")
    linear = sample_probe(case, times, values, samples, method="linear")
    observed_errors = trajectory_errors(case.parameters, observed, expected)
    linear_errors = trajectory_errors(case.parameters, linear, expected)
    check_limits(observed_errors, TARGETS, f"{case.name}/Hermite observations")
    accounting = {
        "radau": balances(case.parameters, radau.sample(samples)),
        "bdf": balances(case.parameters, bdf.sample(samples)),
        "refined": balances(case.parameters, expected),
        "rk4_accepted": balances(case.parameters, values),
        "rk4_observed": balances(case.parameters, observed),
    }
    for name, value in accounting.items():
        check_limits(value, BALANCE_TARGETS, f"{case.name}/{name} accounting")
    physics = inspect_physics(case, samples, observed)
    inspect_controls(case, times, values)
    path = output / case.name
    path.mkdir()
    write_json(path / "case.json", case.definition())
    with (path / "trajectories.npz").open("xb") as handle:
        np.savez_compressed(
            handle,
            accepted_times_s=times,
            rk4_accepted=values,
            sample_times_s=samples,
            rk4_hermite=observed,
            rk4_linear=linear,
            radau=radau.sample(samples),
            bdf=bdf.sample(samples),
            radau_refined=expected,
        )
    return {
        "reference_errors": reference_errors,
        "accepted_errors": accepted_errors,
        "hermite_errors": observed_errors,
        "linear_errors": linear_errors,
        "linear_meets_targets": all(linear_errors[key] <= limit for key, limit in TARGETS.items()),
        "accounting": accounting,
        "sampled_physics": physics,
        "initial_spectrum": local_spectrum(
            case.parameters, case.parameters.initial_amount, case.controls[0]
        ),
        "final_amount_fmol": values[-1, :3].tolist(),
        "final_voltage_V": float(case.parameters.voltage(values[-1, :3])),
        "final_pump_cycles_fmol": float(values[-1, 6]),
        "final_dissipation_pJ": float(values[-1, 7]),
        "samples_compared": len(samples),
        "solver_stats": {
            "radau": radau.stats,
            "bdf": bdf.stats,
            "refined": refined.stats,
            "rk4_probe": probe_stats,
        },
    }


def qualify_refinement():
    case = Case("transient_refinement", horizon=1.0)
    reference = integrate_reference(case, rtol=1e-12, atol=1e-14)
    dts, errors = (0.02, 0.01, 0.005), []
    for dt in dts:
        times, values, _ = integrate_rk4_probe(case, dt)
        errors.append(trajectory_errors(case.parameters, values, reference.sample(times)))
    ratios = [errors[i]["voltage_V"] / errors[i + 1]["voltage_V"] for i in (0, 1)]
    require(
        all(14 <= ratio <= 22 for ratio in ratios), "Expected fourth-order transient refinement"
    )
    times, values, _ = integrate_rk4_probe(case, 0.04)
    rejected = trajectory_errors(case.parameters, values, reference.sample(times))
    require(rejected["voltage_V"] > TARGETS["voltage_V"], "Coarse-step accuracy negative control")
    return {
        "dt_s": dts,
        "errors": errors,
        "voltage_error_ratios": ratios,
        "coarse_dt_0.04_errors": rejected,
    }


def qualify_passive_limit(output):
    print("Checking passive finite-capacitance equilibrium and slow relaxation", flush=True)
    parameters = replace(Parameters(), pump_capacity_fmol_per_s=0)
    voltage, equilibrium = passive_equilibrium(parameters)
    leak, cycles, _, _ = fluxes(parameters, equilibrium, voltage, Control(pump=0))
    require(
        np.max(np.abs(leak)) < 1e-12 and cycles == 0,
        "Analytic passive equilibrium is not stationary",
    )
    case = Case("passive_slow_relaxation", parameters, 100000, (Control(pump=0),))
    # The initial long-horizon comparison narrowly missed the unchanged 1e-8
    # fmol reference-reference target. Refine tolerances, not the physical model.
    radau = integrate_reference(case, rtol=1e-13, atol=1e-15, max_step=1000)
    bdf = integrate_reference(case, method="BDF", rtol=1e-13, atol=1e-15, max_step=1000)
    times = np.unique(np.r_[0, np.geomspace(1e-5, case.horizon, 501), 50000])
    values, alternate = radau.sample(times), bdf.sample(times)
    errors = trajectory_errors(parameters, values, alternate)
    check_limits(errors, TARGETS, "Slow reference agreement", REFERENCE_FACTOR)
    accounting = balances(parameters, values)
    check_limits(accounting, BALANCE_TARGETS, "Slow passive accounting")
    initial_error = float(np.max(np.abs(parameters.initial_amount - equilibrium)))
    halfway_error = float(np.max(np.abs(values[np.searchsorted(times, 50000), :3] - equilibrium)))
    final_error = float(np.max(np.abs(values[-1, :3] - equilibrium)))
    require(
        final_error < halfway_error < initial_error,
        "Passive reference fails to approach equilibrium",
    )
    # A horizon is not a steady-state certificate. Retain its actual residual.
    with (output / "passive_slow_relaxation.npz").open("xb") as handle:
        np.savez_compressed(
            handle, times_s=times, radau=values, bdf=alternate, equilibrium_amount_fmol=equilibrium
        )
    write_json(output / "passive_slow_case.json", case.definition())
    return {
        "analytic_equilibrium_voltage_V": voltage,
        "analytic_equilibrium_amount_fmol": equilibrium.tolist(),
        "initial_amount_distance_fmol": initial_error,
        "halfway_amount_distance_fmol": halfway_error,
        "final_amount_distance_fmol": final_error,
        "final_voltage_distance_V": abs(float(parameters.voltage(values[-1, :3]) - voltage)),
        "horizon_s": case.horizon,
        "within_equilibrium_amount_target": final_error <= TARGETS["amount_fmol"],
        "reference_errors": errors,
        "accounting": accounting,
        "solver_stats": {"radau": radau.stats, "bdf": bdf.stats},
        "scope": "stiff CPU reference only; no 100000-second RK4 or production run",
    }


def verify(output):
    if output.exists():
        raise FileExistsError("Choose a new numerical-reference output directory")
    output.mkdir(parents=True, exist_ok=False)
    try:
        return qualify(output)
    except Exception as error:
        write_json(output / "failure.json", {"status": "failed", "error": str(error)})
        raise


def qualify(output):
    retained = [
        "tests/__init__.py",
        "tests/reference_bioelectric.py",
        "tests/unit/test_bioelectric_reference.py",
        "scripts/verify_bioelectric_reference.py",
        "docs/BIOELECTRIC_CELL_SPEC.md",
        "requirements-lock.txt",
    ]
    identities = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in retained}
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in retained:
            archive.write(ROOT / name, arcname=name)
    results = {case.name: qualify_case(case, output) for case in panel()}
    refinement = qualify_refinement()
    passive = qualify_passive_limit(output)
    require(
        any(not case["linear_meets_targets"] for case in results.values()),
        "Interpolation negative control did not expose the linear-output error",
    )
    require(
        all(
            hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            for name, digest in identities.items()
        ),
        "Reference inputs changed during qualification",
    )
    payloads = {
        str(path.relative_to(output)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in output.rglob("*")
        if path.is_file()
    }
    report = {
        "schema_version": 1,
        "status": "pass",
        "scope": (
            "NUM-002 independent CPU reference and method qualification; "
            "no production/JAX/source parity"
        ),
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
        },
        "cpu_affinity": sorted(os.sched_getaffinity(0))
        if hasattr(os, "sched_getaffinity")
        else None,
        "reference_source_hashes": identities,
        "files_sha256": payloads,
        "state_columns": [
            "Na_fmol",
            "K_fmol",
            "Cl_fmol",
            "Na_leak_fmol",
            "K_leak_fmol",
            "Cl_leak_fmol",
            "pump_cycles_fmol",
            "diagnostic_dissipation_pJ",
        ],
        "targets": TARGETS,
        "balance_targets": BALANCE_TARGETS,
        "reference_factor": REFERENCE_FACTOR,
        "candidate": {
            "method": "RK4",
            "maximum_step_s": DT,
            "observations": "interval_held_control_cubic_Hermite",
            "validated_scope": (
                "specified panel and checks only; not arbitrary-parameter stability or accuracy"
            ),
        },
        "cases": results,
        "refinement": refinement,
        "passive_limit": passive,
    }
    write_json(output / "verification.json", report)
    print(
        f"PASS: {len(results)} short reference cases, refinement, and passive-limit checks",
        flush=True,
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verify(args.output)


if __name__ == "__main__":
    main()
