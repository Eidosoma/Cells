"""Bounded independent NUM-003 study/qualification; no Cells implementation imports.

Freeze inputs and archive reference code before integrating. Preserve inaccurate
trials and source/runtime identities. Use new output directories only.
"""

import argparse
import hashlib
import json
import os
import platform
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import reference_bioelectric_pair as ref  # noqa: E402

RETAINED = (
    "tests/__init__.py",
    "tests/reference_bioelectric.py",
    "tests/reference_bioelectric_pair.py",
    "tests/unit/test_bioelectric_pair_reference.py",
    "scripts/verify_bioelectric_pair_reference.py",
    "configs/reference/bioelectric_pair_panel_v1.json",
    "docs/SELECTIVE_CONTACT_SPEC.md",
    "requirements-lock.txt",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def write_arrays(path, **arrays):
    with path.open("xb") as handle:
        np.savez_compressed(handle, **arrays)


def within(errors, targets, factor=1.0):
    return all(
        np.isfinite(value) and value <= targets[name] * factor for name, value in errors.items()
    )


def references(case, output, settings):
    output.mkdir()
    write_json(output / "case.json", case.definition())
    result = {}
    for name, method, rtol, atol in (
        ("radau", "Radau", settings["rtol"], settings["atol"]),
        ("bdf", "BDF", settings["rtol"], settings["atol"]),
        ("refined", "Radau", settings["refined_rtol"], settings["refined_atol"]),
    ):
        result[name] = ref.integrate_reference(
            case, method=method, rtol=rtol, atol=atol, max_step=settings["max_step_s"]
        )
        write_json(output / f"{name}-solver.json", result[name].stats)
        # Preserve native accepted increments as well as later comparison samples.
        write_arrays(
            output / f"{name}-accepted.npz",
            **{
                key: value
                for i, segment in enumerate(result[name].segments)
                for key, value in (
                    (f"segment_{i}_times_s", segment.t),
                    (f"segment_{i}_increment_state", segment.y.T),
                )
            },
        )
    return result


def inspect_controls(case, times, values):
    checks = 0
    for i, control in enumerate(case.controls):
        end = case.controls[i + 1].time if i + 1 < len(case.controls) else case.horizon
        selected = values[(times >= control.time) & (times <= end)]
        columns = [6 + s * 2 + c for s in range(3) for c in range(2) if control.leak[s][c] == 0]
        columns += [12 + c for c in range(2) if control.pump[c] == 0]
        if control.contact == 0:
            columns += list(range(14, 17))
        if columns:
            actual = selected[:, columns]
            np.testing.assert_array_equal(actual, np.broadcast_to(actual[0], actual.shape))
            checks += len(columns)
    return {"exact_constant_ledger_checks": checks}


def inspect_physics(case, samples, values):
    # Domain, accounting and monotonicity cover every sample. Instantaneous
    # dissipation rates additionally use this explicitly reported bounded subset.
    indices = np.unique(np.linspace(0, len(samples) - 1, min(257, len(samples))).astype(int))
    minimum_rate = np.full(3, np.inf)
    for i in indices:
        slope = ref.derivative(
            case.parameters, case.control_at(samples[i]), values[i], increments=False
        )
        minimum_rate = np.minimum(minimum_rate, slope[ref.DISSIPATION])
    minimum_change = np.min(np.diff(values[:, ref.DISSIPATION], axis=0), axis=0)
    return {
        "instantaneous_samples": len(indices),
        "minimum_dissipation_rate_pJ_per_s": minimum_rate.tolist(),
        "minimum_quadrature_increment_pJ": minimum_change.tolist(),
        "pass": bool(np.all(minimum_rate >= -1e-12) and np.all(minimum_change >= -1e-10)),
    }


def probe_case(case, references_, output, dt, protocol):
    output.mkdir()
    print(f"  {case.id}: RK4 {dt:g} s", flush=True)
    try:
        times, values, stats = ref.integrate_rk4_probe(case, dt)
    except ref.ProbeFailure as error:
        write_arrays(
            output / "rejected-prefix.npz",
            accepted_times_s=error.times,
            accepted_state=error.values,
        )
        record = {"status": "invalid_trial", "dt_s": dt, "error": str(error), "trial": error.trial}
        write_json(output / "result.json", record)
        return record
    write_arrays(output / "accepted.npz", accepted_times_s=times, rk4_accepted=values)
    samples = ref.observation_grid(times)
    coefficients = ref.hermite_coefficients(case, times, values)
    observed = ref.sample_probe(case, times, values, samples, coefficients=coefficients)
    linear = ref.sample_probe(case, times, values, samples, method="linear")
    source = {name: value.sample(samples) for name, value in references_.items()}
    write_arrays(
        output / "comparison.npz",
        sample_times_s=samples,
        rk4_hermite=observed,
        rk4_linear=linear,
        **source,
    )
    expected = source["refined"]
    reference_errors = {
        name: ref.trajectory_errors(case.parameters, source[name], expected)
        for name in ("radau", "bdf")
    }
    accepted_errors = ref.trajectory_errors(
        case.parameters, values, references_["refined"].sample(times)
    )
    hermite_errors = ref.trajectory_errors(case.parameters, observed, expected)
    linear_errors = ref.trajectory_errors(case.parameters, linear, expected)
    accounting = {
        name: ref.balances(case.parameters, value)
        for name, value in (source | {"rk4_accepted": values, "rk4_hermite": observed}).items()
    }
    cubic_domain = ref.interpolant_domain(case.parameters, values, coefficients)
    domains = {
        name: ref.domain_summary(case.parameters, value)
        for name, value in (source | {"rk4_accepted": values, "rk4_hermite": observed}).items()
    }
    physics = inspect_physics(case, samples, observed)
    controls = inspect_controls(case, times, values)
    targets = protocol["targets"]
    checks = {
        "reference_agreement": all(
            within(error, targets, protocol["reference_factor"])
            for error in reference_errors.values()
        ),
        "accepted_accuracy": within(accepted_errors, targets),
        "hermite_accuracy": within(hermite_errors, targets),
        "accounting": all(
            within(error, protocol["balance_targets"]) for error in accounting.values()
        ),
        "sampled_dissipation": physics["pass"],
    }
    result = {
        "status": "pass" if all(checks.values()) else "accuracy_failure",
        "dt_s": dt,
        "checks": checks,
        "reference_errors": reference_errors,
        "accepted_errors": accepted_errors,
        "hermite_errors": hermite_errors,
        "linear_errors": linear_errors,
        "linear_meets_targets": within(linear_errors, targets),
        "accounting": accounting,
        "sampled_domain": domains,
        "cubic_interior_domain": cubic_domain,
        "sampled_physics": physics,
        "controls": controls,
        "solver_stats": {name: value.stats for name, value in references_.items()},
        "probe_stats": stats,
        "samples_compared": len(samples),
        "final_amount_fmol": values[-1, ref.AMOUNT].reshape(3, 2).tolist(),
        "final_voltage_V": case.parameters.voltage(values[-1, ref.AMOUNT].reshape(3, 2)).tolist(),
        "final_gate": float(values[-1, ref.GATE]),
        "final_transfer_fmol": values[-1, ref.TRANSFER].tolist(),
        "initial_spectrum": ref.local_spectrum(case),
    }
    write_json(output / "result.json", result)
    print(
        f"  {case.id}: {result['status']}; gate error {hermite_errors['gate_fraction']:.3g}, "
        f"voltage error {hermite_errors['voltage_V']:.3g}",
        flush=True,
    )
    return result


def structural_checks(cases, output, dt, protocol):
    checks = {}

    def arrays(slot):
        path = output / cases[slot].id / "candidate" / "comparison.npz"
        with np.load(path, allow_pickle=False) as data:
            return data["sample_times_s"].copy(), data["refined"].copy()

    t0, y0 = arrays(0)
    t6, y6 = arrays(6)
    np.testing.assert_array_equal(t0, t6)
    y6[:, ref.TRANSFER] *= -1
    errors = ref.trajectory_errors(cases[0].parameters, y6, y0)
    checks["reversed_edge"] = {
        "errors": errors,
        "pass": within(errors, protocol["targets"], protocol["reference_factor"]),
    }

    times, pair = arrays(1)
    one = [
        ref.cell.integrate_reference(ref.cell_case(cases[1], i), rtol=1e-12, atol=1e-14)
        for i in range(2)
    ]
    isolated = [value.sample(times) for value in one]
    expected = pair.copy()
    for i, value in enumerate(isolated):
        expected[:, np.arange(3) * 2 + i] = value[:, :3]
        expected[:, 6 + np.arange(3) * 2 + i] = value[:, 3:6]
        expected[:, 12 + i] = value[:, 6]
    errors = ref.trajectory_errors(cases[1].parameters, pair, expected)
    dissipation_error = float(
        np.max(np.abs(pair[:, ref.DISSIPATION].sum(axis=1) - isolated[0][:, 7] - isolated[1][:, 7]))
    )
    checks["blocked_independent_cells"] = {
        "errors": errors,
        "summed_dissipation_error_pJ": dissipation_error,
        "pass": within(errors, protocol["targets"], protocol["reference_factor"])
        and dissipation_error <= 1e-7,
        "solver_stats": [value.stats for value in one],
    }
    write_arrays(
        output / "blocked-independent-cells.npz",
        sample_times_s=times,
        cell_A=isolated[0],
        cell_B=isolated[1],
    )

    times, values = arrays(3)
    p = cases[3].parameters
    target = p.junction.target(p.initial_voltage[0] - p.initial_voltage[1])
    exact = target + (p.junction.initial_gate - target) * np.exp(-times / p.junction.tau_s)
    gate_error = float(np.max(np.abs(values[:, ref.GATE] - exact)))
    unchanged = [i for i in range(ref.SIZE) if i != ref.GATE]
    np.testing.assert_array_equal(
        values[:, unchanged], np.broadcast_to(values[0, unchanged], values[:, unchanged].shape)
    )
    checks["gate_only_analytic"] = {"maximum_gate_error": gate_error, "pass": gate_error <= 1e-8}

    _, values = arrays(2)
    amount = values[:, ref.AMOUNT].reshape(-1, 3, 2)
    total_error = float(np.max(np.abs(amount.sum(axis=2) - amount[0].sum(axis=1))))
    checks["isolated_species_totals"] = {
        "amount_error_fmol": total_error,
        "pass": total_error <= 1e-8,
    }
    _, values = arrays(4)
    symmetry = float(
        np.max(
            np.abs(
                values[:, ref.AMOUNT].reshape(-1, 3, 2)[:, :, 0]
                - values[:, ref.AMOUNT].reshape(-1, 3, 2)[:, :, 1]
            )
        )
    )
    transfer = float(np.max(np.abs(values[:, ref.TRANSFER])))
    checks["identical_cell_symmetry"] = {
        "amount_error_fmol": symmetry,
        "transfer_fmol": transfer,
        "pass": max(symmetry, transfer) <= 1e-10,
    }
    _, values = arrays(14)
    np.testing.assert_array_equal(values[:, 15], np.zeros(len(values)))
    checks["potassium_impermeant"] = {"pass": True}
    return checks


def inspect_study(path, dt, protocol):
    report = json.loads((path / "verification.json").read_text())
    if report["status"] != "study_complete" or set(report["cases"]) != {"Q03", "Q09", "Q11"}:
        raise ValueError("Incomplete or unexpected timestep study")
    for name, digest in report["files_sha256"].items():
        if sha(path / name) != digest:
            raise ValueError(f"Study payload mismatch: {name}")
    for name in (
        "tests/reference_bioelectric.py",
        "tests/reference_bioelectric_pair.py",
        "configs/reference/bioelectric_pair_panel_v1.json",
    ):
        if sha(ROOT / name) != report["reference_source_hashes"][name]:
            raise ValueError(f"Study used a different reference/input: {name}")
    if (
        report["targets"] != protocol["targets"]
        or report["balance_targets"] != protocol["balance_targets"]
    ):
        raise ValueError("Study and qualification targets differ")
    if any(rows[f"{dt:g}"]["status"] != "pass" for rows in report["cases"].values()):
        raise ValueError("Candidate timestep did not pass all study cases")
    ratios = {}
    for name in ("Q03", "Q09"):
        rows = report["cases"][name]
        ratios[name] = [
            rows[a]["accepted_errors"]["gate_fraction"]
            / rows[b]["accepted_errors"]["gate_fraction"]
            for a, b in (("0.01", "0.005"), ("0.005", "0.0025"))
        ]
        if not all(12 <= value <= 25 for value in ratios[name]):
            raise ValueError("Fourth-order gate refinement not demonstrated")
    if (
        report["cases"]["Q09"]["0.005"]["hermite_errors"]["gate_fraction"]
        <= protocol["targets"]["gate_fraction"]
    ):
        raise ValueError("Missing inherited-timestep negative control")
    return {
        "path": str(path.resolve()),
        "receipt_sha256": sha(path / "verification.json"),
        "gate_refinement_ratios": ratios,
        "all_selected_step_cases_pass": True,
        "inherited_5ms_gate_error": report["cases"]["Q09"]["0.005"]["hermite_errors"][
            "gate_fraction"
        ],
    }


def verify(output, *, mode, dt, study=None):
    if output.exists():
        raise FileExistsError("Choose a new output directory; retained runs are not overwritten")
    if mode not in ("study", "qualification"):
        raise ValueError("Unknown qualification mode")
    protocol, cases = ref.load_panel()
    if dt not in protocol["candidate_steps_s"]:
        raise ValueError("Timestep was not included in the frozen candidate list")
    if mode == "qualification" and study is None:
        raise ValueError("Qualification requires an identified --study directory")
    study_evidence = inspect_study(study, dt, protocol) if mode == "qualification" else None
    output.mkdir(parents=True, exist_ok=False)
    identities = {name: sha(ROOT / name) for name in RETAINED}
    production = {
        str(path.relative_to(ROOT)): sha(path)
        for path in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as archive:
        for name in RETAINED:
            archive.write(ROOT / name, arcname=name)
    write_json(
        output / "frozen-panel.json",
        {
            "source_sha256": sha(ref.PANEL_PATH),
            "protocol": protocol,
            "resolved_cases": [case.definition() for case in cases],
        },
    )
    results = {}
    try:
        selected = [cases[i] for i in (3, 9, 11)] if mode == "study" else cases
        for case in selected:
            print(f"{mode}: {case.id} {case.name}", flush=True)
            references_ = references(case, output / case.id, protocol["reference_settings"])
            steps = protocol["candidate_steps_s"] if mode == "study" else [dt]
            results[case.id] = {
                f"{step:g}": probe_case(
                    case,
                    references_,
                    output / case.id / (f"dt-{step:g}" if mode == "study" else "candidate"),
                    step,
                    protocol,
                )
                for step in steps
            }
        structural = (
            structural_checks(cases, output, dt, protocol) if mode == "qualification" else {}
        )
        if any(sha(ROOT / name) != digest for name, digest in identities.items()):
            raise ValueError("Frozen reference sources changed during execution")
        if any(sha(ROOT / name) != digest for name, digest in production.items()):
            raise ValueError("Production source changed during reference-only qualification")
        payloads = {
            str(path.relative_to(output)): sha(path) for path in output.rglob("*") if path.is_file()
        }
        success = mode == "study" or (
            all(row[f"{dt:g}"]["status"] == "pass" for row in results.values())
            and all(row["pass"] for row in structural.values())
        )
        report = {
            "schema_version": 1,
            "status": "study_complete" if mode == "study" else ("pass" if success else "failed"),
            "scope": (
                "NUM-003 independent CPU reference and method probe; "
                "no production/JAX/source-assay parity"
            ),
            "verified_utc": datetime.now(timezone.utc).isoformat(),
            "mode": mode,
            "runtime": {
                "python": platform.python_version(),
                "numpy": np.__version__,
                "scipy": scipy.__version__,
            },
            "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "reference_source_hashes": identities,
            "production_source_hashes_unchanged": production,
            "files_sha256": payloads,
            "state_columns": ref.STATE_COLUMNS,
            "targets": protocol["targets"],
            "balance_targets": protocol["balance_targets"],
            "reference_factor": protocol["reference_factor"],
            "candidate": {
                "method": "RK4",
                "maximum_step_s": dt if mode == "qualification" else None,
                "observations": "interval_held_control_cubic_Hermite",
                "scope": "frozen cases only, not a parameter-box or arbitrary-horizon guarantee",
            },
            "cases": results,
            "structural_checks": structural,
            "timestep_study": study_evidence,
        }
        write_json(output / "verification.json", report)
        print(f"{report['status']}: {len(results)} cases, {output}", flush=True)
        return report
    except Exception as error:
        write_json(
            output / "failure.json",
            {"status": "failed", "error": str(error), "completed_cases": list(results)},
        )
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mode", choices=("study", "qualification"), default="qualification")
    parser.add_argument("--dt", type=float, default=0.001)
    parser.add_argument("--study", type=Path)
    args = parser.parse_args()
    report = verify(args.output, mode=args.mode, dt=args.dt, study=args.study)
    return 0 if report["status"] in ("pass", "study_complete") else 1


if __name__ == "__main__":
    raise SystemExit(main())
