"""Bounded NUM-004 independent coupled study/qualification; no production imports."""

import argparse
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path

import numpy as np
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tests import reference_source_pair_numerics as ref  # noqa: E402

SOURCES = (
    "tests/reference_emt.py",
    "tests/reference_source_pair.py",
    "tests/reference_source_pair_numerics.py",
    "tests/unit/test_source_pair_numerics.py",
    "scripts/verify_source_pair_numerics.py",
    "configs/reference/source_emt_pair_panel_v1.json",
    "configs/reference/source_emt_pair_numerics_v1.json",
    "requirements-lock.txt",
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def write_arrays(path, **values):
    with path.open("xb") as handle:
        np.savez_compressed(handle, **values)


def references(model, output):
    solutions = {}
    for name, method, refinement in (
        ("radau", "Radau", 1.0),
        ("bdf", "BDF", 1.0),
        ("refined", "Radau", 0.1),
    ):
        solution = ref.integrate_reference(model, method=method, refinement=refinement)
        solutions[name] = solution
        entries = {
            k: v
            for i, sol in enumerate(solution.segments)
            for k, v in ((f"segment_{i}_times", sol.t), (f"segment_{i}_increment_state", sol.y.T))
        }
        polys = list(ref.native_polynomials(solution))
        minima = [ref.check_polynomial(model, c) for _, _, c in polys]
        # Verify the coefficient adapter against SciPy's own output, independently of extrema.
        for a, b, c in polys:
            theta = np.array([0.0, 0.127, 0.5, 0.913, 1.0])
            numeric = np.polynomial.polynomial.polyval(theta, c).T
            np.testing.assert_allclose(
                numeric, solution.sample(a + (b - a) * theta), atol=1e-11, rtol=1e-12
            )
        entries["polynomial_times"] = np.array([(a, b) for a, b, _ in polys])
        # Pad only polynomial degree for portable storage, never add numerical state.
        entries["polynomial_coefficients"] = np.array(
            [np.pad(c, ((0, 6 - len(c)), (0, 0))) for _, _, c in polys]
        )
        write_arrays(output / f"{name}-accepted.npz", **entries)
        write_json(
            output / f"{name}-solver.json",
            solution.stats
            | {
                "polynomial_intervals_checked": len(polys),
                "minimum_interpolated_regulation": min(minima),
            },
        )
    return solutions


def probe(model, dt, solutions, output):
    output.mkdir()
    print(f"  {model.case['id']} RK4 {dt:g}", flush=True)
    try:
        times, values, slopes, stats = ref.integrate_rk4(model, dt)
        coefficients = ref.cubic_coefficients(times, values, slopes)
        minima = [ref.check_polynomial(model, c) for c in coefficients]
        samples = ref.comparison_grid(model, times)
        observed = ref.sample_cubic(times, values, coefficients, samples)
        ref.domain(model, observed)
        expected = {k: s.sample(samples) for k, s in solutions.items()}
        errors = ref.scores(model, samples, observed, expected["refined"])
        reference_errors = {
            name: ref.scores(model, samples, value, expected["refined"])
            for name, value in expected.items()
            if name != "refined"
        }
        accounts = {
            "rk4": ref.accounting(model, observed),
            **{name: ref.accounting(model, value) for name, value in expected.items()},
        }
        for value in expected.values():
            ref.domain(model, value)
        controls_checked = 0
        for i, start in enumerate(model.starts):
            mask = (times >= start) & (times <= model.ends[i])
            control = model.held[i]["controls"]
            columns = [
                12 + s * 2 + c for s in range(3) for c in range(2) if control["leak"][s][c] == 0
            ]
            columns += [18 + c for c in range(2) if control["pump"][c] == 0]
            if control["ion_contact"] == 0:
                columns += list(range(20, 23))
            if control["mirna_contact"] == 0:
                columns += [29]
            if columns:
                actual = values[mask][:, columns]
                np.testing.assert_array_equal(actual, np.broadcast_to(actual[0], actual.shape))
                controls_checked += len(columns)
        status = (
            "pass"
            if (
                max(errors.values()) <= 1
                and all(max(v.values()) <= 0.1 for v in reference_errors.values())
                and max(v for group in accounts.values() for v in group.values())
                <= ref.protocol()["accounting_atol"]
            )
            else "accuracy_failure"
        )
        report = {
            "status": status,
            "stats": stats,
            "scores": errors,
            "reference_scores": reference_errors,
            "accounting": accounts,
            "domain": ref.domain(model, observed),
            "minimum_cubic_regulation": min(minima),
            "comparison_points": len(samples),
            "constant_control_ledgers": controls_checked,
        }
        write_arrays(
            output / "trajectory.npz",
            accepted_times=times,
            accepted_state=values,
            endpoint_slopes=slopes,
            coefficients=coefficients,
            sample_times=samples,
            observed=observed,
            **expected,
        )
    except ref.ProbeFailure as error:
        report = {"status": "invalid_trial", "error": str(error), "dt": dt}
        write_arrays(
            output / "rejected-prefix.npz",
            times=error.times,
            values=error.values,
            trial=error.trial,
        )
    write_json(output / "result.json", report)
    return report


def verify(output, mode, study=None):
    if output.exists():
        raise ValueError("Output must be new")
    panel, protocol = ref.eq.load_panel(), ref.protocol()
    if sha(ref.eq.PANEL) != protocol["panel_sha256"]:
        raise ValueError("Frozen panel changed")
    output.mkdir(parents=True)
    identities = {name: sha(ROOT / name) for name in SOURCES}
    with zipfile.ZipFile(
        output / "reference_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as capsule:
        for name in SOURCES:
            capsule.write(ROOT / name, name)
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p) for p in (ROOT / "src/cells").rglob("*.py")
    }
    if (
        production
        != json.loads(
            (ROOT / "runs/model-004-2026-09-08/acceptance/verification.json").read_text()
        )["source_hashes"]
    ):
        raise ValueError("Production source changed")
    candidates = panel["future_numerical_gate"]["candidate_rk4_steps"]
    selected = None
    if mode == "qualification":
        if study is None:
            raise ValueError("Qualification requires retained study")
        study_data = json.loads((study / "verification.json").read_text())
        if study_data["source_hashes"] != identities:
            raise ValueError("Study source identity differs")
        selected = study_data["selected_dt"]
        if selected is None:
            raise ValueError("Study has no passing method")
        candidates = [selected, selected / 2]
    cases = [
        c for c in panel["cases"] if mode == "qualification" or c["id"] in protocol["study_cases"]
    ]
    records = {}
    for case in cases:
        print(case["id"], case["name"], flush=True)
        directory = output / case["id"]
        directory.mkdir()
        model = ref.Model(panel, case)
        write_json(directory / "case.json", case)
        try:
            solved = references(model, directory)
            records[case["id"]] = {
                str(dt): probe(model, dt, solved, directory / f"rk4-{dt:g}") for dt in candidates
            }
        except (ValueError, AssertionError, FloatingPointError) as error:
            records[case["id"]] = {"reference_failure": str(error)}
            write_json(directory / "failure.json", records[case["id"]])
    if mode == "study":
        selected = next(
            (
                dt
                for dt in candidates
                if all(r.get(str(dt), {}).get("status") == "pass" for r in records.values())
            ),
            None,
        )
    passed = (
        selected is not None
        and all(all(v.get("status") == "pass" for v in r.values()) for r in records.values())
        if mode == "qualification"
        else selected is not None
    )
    hashes = {str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()}
    result = {
        "status": "pass" if passed else "qualification_incomplete",
        "scope": "independent source-coordinate paths; native and production checks separate",
        "mode": mode,
        "selected_dt": selected,
        "cases": records,
        "source_hashes": identities,
        "production_source_hashes_unchanged": production,
        "payload_hashes": hashes,
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }
    write_json(output / "verification.json", result)
    print(f"{mode}: {result['status']}; selected dt={selected}", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--mode", choices=("study", "qualification"), required=True)
    parser.add_argument("--study", type=Path)
    args = parser.parse_args()
    result = verify(args.output, args.mode, args.study)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
