"""Read-only audit of saved passive-contact examples, with an optional new receipt.

Uses a two-by-two matrix exponential, separate from both the JAX coupler and
tests' scalar closed-form oracle. Requires active/blocked/resumed/released/pulse.
"""

import argparse
import hashlib
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.linalg import expm

from cells.core.runner import run
from cells.core.specs import PassivePairSpec, load_spec, read_json
from cells.io import load_snapshot, runtime_identity, source_hashes

AMOUNT_TOLERANCE = 3e-8
ACCOUNTING_TOLERANCE = 1e-12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference(spec, times):
    # n' = L n. A common scalar control multiplies L, so all intervals commute.
    va, vb = spec.model.volumes
    matrix = spec.model.permeability * np.array([[-1 / va, 1 / vb], [1 / va, -1 / vb]])
    opening = np.zeros(len(times), dtype=np.float64)
    for index, change in enumerate(spec.experiment.contact):
        stop = (
            spec.experiment.contact[index + 1].time
            if index + 1 < len(spec.experiment.contact)
            else spec.experiment.end_time
        )
        opening += change.open_fraction * np.maximum(0, np.minimum(times, stop) - change.time)
    initial = np.array(spec.model.initial_amounts)
    amounts = np.stack([expm(matrix * elapsed) @ initial for elapsed in opening])
    receiver = spec.model.cell_ids.index(spec.model.to_cell_id)
    transferred = amounts[:, receiver] - initial[receiver]
    return amounts, transferred


def inspect_run(path):
    manifest = read_json(path / "manifest.json")
    require(manifest["status"] == "complete", f"Incomplete: {path}")
    require(manifest["source_hashes"] == source_hashes(), f"Source changed: {path}")
    require(manifest["runtime"] == runtime_identity(), f"Runtime changed: {path}")
    for name, digest in manifest["files_sha256"].items():
        file = (path / name).resolve()
        require(file.is_relative_to(path.resolve()), "Artifact path escapes the run directory")
        require(
            hashlib.sha256(file.read_bytes()).hexdigest() == digest, f"Corrupt artifact: {file}"
        )
    spec = load_spec(path / "resolved_config.json")
    require(isinstance(spec.model, PassivePairSpec), "Not a passive-pair run")
    require(spec.fingerprint == manifest["definition_sha256"], "Definition checksum mismatch")
    final = load_snapshot(path / "checkpoint_final")
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    for name in ("amount", "transferred"):
        np.testing.assert_array_equal(data[name][-1], getattr(final.checkpoint.state, name))
    expected_amount, expected_transfer = reference(spec, data["accepted_times"])
    amount_error = float(np.max(np.abs(data["amount"][:, :2] - expected_amount)))
    transfer_error = float(np.max(np.abs(data["transferred"][:, 0] - expected_transfer)))
    require(max(amount_error, transfer_error) < AMOUNT_TOLERANCE, f"Analytical mismatch: {path}")
    total_error = float(
        np.max(np.abs(data["amount"].sum(axis=1) - sum(spec.model.initial_amounts)))
    )
    sender, receiver = (
        spec.model.cell_ids.index(v) for v in (spec.model.from_cell_id, spec.model.to_cell_id)
    )
    change = data["amount"][:, :2] - spec.model.initial_amounts
    account_error = float(
        max(
            np.max(np.abs(change[:, sender] + data["transferred"][:, 0])),
            np.max(np.abs(change[:, receiver] - data["transferred"][:, 0])),
        )
    )
    require(max(total_error, account_error) < ACCOUNTING_TOLERANCE, f"Accounting failed: {path}")
    return (
        spec,
        data,
        manifest,
        {
            "max_matrix_reference_error_fmol": amount_error,
            "max_transfer_reference_error_fmol": transfer_error,
            "max_total_amount_error_fmol": total_error,
            "max_cell_transfer_accounting_error_fmol": account_error,
            "final_amounts_fmol": data["amount"][-1, :2].tolist(),
            "final_transferred_fmol": float(data["transferred"][-1, 0]),
            "steps": len(data["accepted_times"]) - 1,
            "definition_sha256": spec.fingerprint,
            "manifest_sha256": hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
            "timings": manifest["timings"],
        },
    )


def verify(root):
    runs = {
        name: inspect_run(root / name)
        for name in ("active", "blocked", "resumed", "released", "pulse")
    }
    active, blocked, resumed, released = (
        runs[name][1] for name in ("active", "blocked", "resumed", "released")
    )
    parent = load_snapshot(root / "active/snapshots/step-000120")
    require(parent.checkpoint.time == 6.0, "Unexpected checkpoint boundary")
    suffix = active["accepted_times"] >= 6
    np.testing.assert_array_equal(active["accepted_times"][suffix], resumed["accepted_times"])
    for name in ("amount", "transferred"):
        np.testing.assert_array_equal(active[name][suffix], resumed[name])
        np.testing.assert_array_equal(
            released[name], np.broadcast_to(resumed[name][0], released[name].shape)
        )
    require(
        released["transferred"][-1, 0] < resumed["transferred"][-1, 0],
        "Release did not stop further transfer",
    )
    np.testing.assert_array_equal(
        blocked["amount"], np.broadcast_to([8, 0], blocked["amount"].shape)
    )
    require(np.all(blocked["transferred"] == 0), "Blocked edge transferred material")
    for field in (
        "volume",
        "cell_ids",
        "contact_ids",
        "senders",
        "receivers",
        "contact_active",
        "permeability",
    ):
        np.testing.assert_array_equal(active[field], blocked[field])
    for name in ("resumed", "released"):
        require(
            runs[name][2]["provenance"]["parent_snapshot_sha256"] == parent.fingerprint,
            f"Wrong branch provenance: {name}",
        )
    require(
        {2.03, 5.07}.issubset(set(runs["pulse"][1]["accepted_times"])), "Pulse boundaries missing"
    )
    baseline = runs["active"][0]
    short = replace(
        baseline, experiment=replace(baseline.experiment, end_time=2, observation_times=(0, 2))
    )
    errors = []
    for dt in (0.4, 0.2, 0.1):
        result = run(replace(short, execution=replace(short.execution, dt=dt)))
        expected, _ = reference(short, result.times)
        errors.append(float(np.max(np.abs(result.amount[:, :2] - expected))))
    ratios = [a / b for a, b in zip(errors, errors[1:], strict=False)]
    require(
        all(14 < ratio < 20 for ratio in ratios), "Refinement outside declared fourth-order range"
    )
    return {
        "status": "pass",
        "scope": "M1c-a passive transport fixture, not selective bioelectric coupling",
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "runtime": runtime_identity(),
        "source_hashes": source_hashes(),
        "verifier_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "amount_tolerance_fmol": AMOUNT_TOLERANCE,
        "accounting_tolerance_fmol": ACCOUNTING_TOLERANCE,
        "refinement_steps": [0.4, 0.2, 0.1],
        "refinement_max_errors_fmol": errors,
        "refinement_ratios": ratios,
        "all_artifact_hashes_valid": True,
        "replay_exact_suffix": True,
        "released_branch_frozen": True,
        "blocked_contact_still_present": True,
        "runs": {name: value[3] for name, value in runs.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, help="optional new receipt; never overwritten")
    args = parser.parse_args()
    if args.output is not None and args.output.exists():
        parser.error("Receipt already exists; choose a new path")
    report = verify(args.root)
    if args.output is not None:
        with args.output.open("x") as handle:
            json.dump(report, handle, indent=2, sort_keys=True, allow_nan=False)
            handle.write("\n")
    print(json.dumps(report, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
