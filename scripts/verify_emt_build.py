"""M1b acceptance: source slopes, independent solvers, refinement, and replay.

CPU only. Source capture is an explicit input; no downloads or upstream jobs.
Outputs go to a new directory and include full Cells runs and a compact receipt.
"""

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

from cells.core.runner import run
from cells.core.specs import load_spec, read_json
from cells.core.state import EMTState, cpu_device
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run
from cells.models import emt_mirna

ROOT = Path(__file__).resolve().parents[1]
TOLERANCES = {
    "source_rhs_absolute": 1e-11,
    "source_complex_absolute": 1e-11,
    "jax_vs_radau_absolute": 1e-6,
    "bdf_vs_radau_absolute": 1e-7,
    "source_default_euler_vs_radau_absolute": 0.1,
    "refinement_ratio_min": 12,
    "refinement_ratio_max": 20,
}
PINNED_SOURCE_HASHES = {
    "README.md": "3e84ba97ec15abcb7f2ab4aa1fc2908fca40c34c784b62f01265d1591c68906b",
    "cancer_GJ_sims/GRN_miRNA.py": (
        "9b290b6d2cd9c195aa439e2776a841f8cb2a9a64c4c0deff636788430f4e2a42"
    ),
    "edebug.py": "a71b04d20444d343a623eaa1761bd879802e64aaf8460304318da4015da96ee0",
    "eplot.py": "6167186c73408df56c03f3464e1de3fc34aeae444e9abebdb4bc1185e2a4a5bd",
    "sim.py": "b5ad4ac5e13db437b1e087369c592bf9139346a46c46cc320a01a9aaa4061e87",
    "sim_toolbox.py": "53b2fafaf11f6915d8e11aef201ad5499a3ce174016ad246364dbf490e5abe8c",
}


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def check_payloads(directory):
    manifest = read_json(directory / "manifest.json")
    require(manifest["source_hashes"] == source_hashes(), "Run source changed")
    require(manifest["runtime"] == runtime_identity(), "Run runtime changed")
    for name, digest in manifest["files_sha256"].items():
        actual = hashlib.sha256((directory / name).read_bytes()).hexdigest()
        require(actual == digest, f"Artifact checksum mismatch: {name}")


def verify(reference_path, output):
    # The independent oracle is test/support code, never called by the model.
    sys.path.insert(0, str(ROOT))
    from tests.reference_emt import reference_solution

    reference = read_json(reference_path)
    require(reference["revision"] == emt_mirna.UPSTREAM_REVISION, "Wrong source revision")
    require(reference["source_hashes"] == PINNED_SOURCE_HASHES, "Wrong source file hashes")
    expected_harness = hashlib.sha256(
        (ROOT / "scripts/capture_emt_reference.py").read_bytes()
    ).hexdigest()
    require(reference["harness_sha256"] == expected_harness, "Source capture harness differs")
    points = reference["cases"]["probes"]["points"]
    require(len(points) == 36, "Incomplete source derivative panel")
    require(
        reference["cases"]["probes"]["full_isolated_slopes_equal_gate"], "Gate isolation failed"
    )
    cpu_device()
    errors, bound_errors = [], []
    for point in points:
        state = EMTState(*(np.array([v], dtype=np.float64) for v in point["state"]))
        derivative = emt_mirna.rhs(state, 0, point["snail"], np.array([True]))
        errors.append(float(np.max(np.abs(np.array(derivative)[:, 0] - point["rhs"]))))
        bound = emt_mirna.complexes(state.mir200_total, state.zeb_mrna_total, xp=np)[0]
        bound_errors.append(float(np.max(np.abs(bound - point["bound_complexes"]))))
        require(point["mir200_free_proxy"] == point["state"][0], "Source binding variant changed")
    require(max(errors) < TOLERANCES["source_rhs_absolute"], "Source RHS mismatch")
    require(max(bound_errors) < TOLERANCES["source_complex_absolute"], "Source complexes mismatch")

    output.mkdir(parents=True, exist_ok=False)
    cases = {}
    for name in ("e", "m"):
        print(f"Verifying isolated {name.upper()}: 10000 units, refinement and restart", flush=True)
        original = reference["cases"][name]
        spec = load_spec(ROOT / f"configs/emt_isolated_{name}.json")
        endpoint = max(spec.experiment.end_time, original["accepted_time"])
        radau = reference_solution(original["initial"], endpoint)
        bdf = reference_solution(original["initial"], endpoint, method="BDF")
        result = run(spec)
        write_run(output / name, result, checkpoint_times=(5000.0,))
        expected = radau.sol(result.times)
        values = np.stack(result.history)[:, :, 0]
        error = float(np.max(np.abs(values - expected)))
        bdf_error = float(np.max(np.abs(bdf.sol(result.times) - expected)))
        require(
            error < TOLERANCES["jax_vs_radau_absolute"], f"{name}: independent integration mismatch"
        )
        require(bdf_error < TOLERANCES["bdf_vs_radau_absolute"], f"{name}: references disagree")
        refinement_errors = []
        for dt in (0.2, 0.1, 0.05):
            refined = (
                result
                if dt == 0.1
                else run(replace(spec, execution=replace(spec.execution, dt=dt)))
            )
            difference = np.stack(refined.history)[:, :, 0] - radau.sol(refined.times)
            refinement_errors.append(float(np.max(np.abs(difference))))
        ratios = [a / b for a, b in zip(refinement_errors, refinement_errors[1:], strict=False)]
        require(
            all(
                TOLERANCES["refinement_ratio_min"] < r < TOLERANCES["refinement_ratio_max"]
                for r in ratios
            ),
            f"{name}: refinement not fourth-order in this panel",
        )

        snapshot = load_snapshot(output / name / "snapshots/step-050000")
        replay = run(snapshot.spec, snapshot.checkpoint)
        write_run(
            output / f"{name}-resumed",
            replay,
            provenance={
                "operation": "resume",
                "parent_snapshot_sha256": snapshot.fingerprint,
                "parent_definition_sha256": spec.fingerprint,
                "branch_time": 5000.0,
            },
        )
        for whole, suffix in zip(result.history, replay.history, strict=True):
            np.testing.assert_array_equal(whole[50000:], suffix)
        sampled_times = np.array(original["snapshot_times"])
        source_values = np.array(original["snapshot_primary"]).T
        native_error = float(np.max(np.abs(source_values - radau.sol(sampled_times))))
        require(
            native_error < TOLERANCES["source_default_euler_vs_radau_absolute"],
            f"{name}: default-source trajectory outside declared comparison tolerance",
        )
        require(
            original["all_sampled_full_state_finite"]
            and original["minimum_sampled_full_state"] >= 0,
            f"{name}: invalid sampled source state",
        )
        require(
            np.isfinite(list(original["accepted_full_state"].values())).all()
            and min(original["accepted_full_state"].values()) >= 0,
            f"{name}: invalid source endpoint",
        )
        require(
            result.observations.label[-1, 0] == original["accepted_label"] == name.upper(),
            f"{name}: endpoint label mismatch",
        )
        check_payloads(output / name)
        check_payloads(output / f"{name}-resumed")
        cases[name] = {
            "cells_final_time": result.final.time,
            "cells_final_primary": values[:, -1].tolist(),
            "cells_definition_sha256": spec.fingerprint,
            "radau_rhs_evaluations": radau.nfev,
            "bdf_rhs_evaluations": bdf.nfev,
            "max_jax_vs_radau_abs": error,
            "max_bdf_vs_radau_abs": bdf_error,
            "refinement_dt": [0.2, 0.1, 0.05],
            "refinement_max_abs": refinement_errors,
            "refinement_ratios": ratios,
            "exact_replay_suffix": True,
            "source_default_max_sampled_error_vs_radau": native_error,
            "source_last_sample_time": original["last_sample_time"],
            "source_accepted_time": original["accepted_time"],
            "source_last_sample_primary": original["last_sample_primary"],
            "source_accepted_primary": original["accepted_primary"],
            "source_accepted_error_vs_radau": float(
                np.max(np.abs(original["accepted_primary"] - radau.sol(original["accepted_time"])))
            ),
            "final_label": original["accepted_label"],
            "diagnostics": result.diagnostics,
            "timings": result.timings,
        }
    receipt = {
        "status": "pass",
        "scope": "isolated regulatory source comparison, not full BITSEY or paper tables",
        "runtime": runtime_identity(),
        "source_hashes": source_hashes(),
        "reference_sha256": hashlib.sha256(reference_path.read_bytes()).hexdigest(),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "independent_math_sha256": hashlib.sha256(
            (ROOT / "tests/reference_emt.py").read_bytes()
        ).hexdigest(),
        "tolerances": TOLERANCES,
        "source_probe_count": len(points),
        "source_rhs_max_abs": max(errors),
        "source_complex_max_abs": max(bound_errors),
        "all_payload_hashes_valid": True,
        "cases": cases,
    }
    with (output / "verification.json").open("x") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("reference", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("Output exists; choose a new directory")
    receipt = verify(args.reference, args.output)
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
