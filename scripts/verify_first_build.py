"""Read-only verification of the three saved M1a examples; optional new receipt.

Run from the repository with its installed environment:
  .venv/bin/python scripts/verify_first_build.py runs/m1a-2026-09-08
"""

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from cells.core.specs import load_spec, read_json
from cells.io import load_snapshot, source_hashes


def require(condition, message):
    if not condition:
        raise ValueError(message)


def reference(spec, times):
    """Superpose exact responses to each constant source interval.

    This oracle is independent of RK4 and of the stepwise oracle in the tests.
    """
    k = spec.model.decay_rate
    amounts = spec.model.initial_amount * np.exp(-k * times)
    for index, change in enumerate(spec.experiment.source):
        stop = (
            spec.experiment.source[index + 1].time
            if index + 1 < len(spec.experiment.source)
            else spec.experiment.end_time
        )
        duration = np.maximum(0.0, np.minimum(times, stop) - change.time)
        decay_after = np.maximum(0.0, times - stop)
        if k == 0:
            amounts += change.rate * duration
        else:
            amounts += change.rate * (-np.expm1(-k * duration)) / k * np.exp(-k * decay_after)
    return amounts


def inspect_run(path):
    manifest = read_json(path / "manifest.json")
    require(manifest["status"] == "complete", f"Incomplete run: {path}")
    require(manifest["source_hashes"] == source_hashes(), f"Source changed: {path}")
    for name, checksum in manifest["files_sha256"].items():
        target = (path / name).resolve()
        require(target.is_relative_to(path.resolve()), "Artifact path escapes its run directory")
        require(hashlib.sha256(target.read_bytes()).hexdigest() == checksum, f"Checksum: {target}")
    spec = load_spec(path / "resolved_config.json")
    require(spec.fingerprint == manifest["definition_sha256"], "Definition mismatch")
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        data = {key: archive[key] for key in archive.files}
    final = load_snapshot(path / "checkpoint_final")
    for field in ("amount", "supplied", "degraded"):
        require(np.array_equal(data[field][-1], getattr(final.checkpoint.state, field)), field)
    error = float(np.max(np.abs(data["amount"][:, 0] - reference(spec, data["accepted_times"]))))
    require(error < 2e-8, f"Analytic trajectory error exceeds 2e-8 fmol: {path}")
    summary = read_json(path / "summary.json")
    require(summary["max_balance_error_fmol"] < 1e-12, f"Accounting error: {path}")
    return (
        data,
        manifest,
        {
            "max_analytic_error_fmol": error,
            "max_balance_error_fmol": summary["max_balance_error_fmol"],
            "final_amount_fmol": summary["final_amount_fmol"],
            "executed_steps": summary["executed_steps"],
            "definition_sha256": spec.fingerprint,
            "manifest_sha256": hashlib.sha256((path / "manifest.json").read_bytes()).hexdigest(),
            "timings": manifest["timings"],
        },
    )


def verify(root):
    runs = {name: inspect_run(root / name) for name in ("pulse", "resumed", "rechallenged")}
    pulse, resumed, changed = (runs[name][0] for name in ("pulse", "resumed", "rechallenged"))
    suffix = pulse["accepted_times"] >= 6.0
    require(
        np.array_equal(pulse["accepted_times"][suffix], resumed["accepted_times"]),
        "Replay time grid",
    )
    for field in ("amount", "supplied", "degraded"):
        require(np.array_equal(pulse[field][suffix], resumed[field]), f"Replay differs: {field}")
        require(
            np.array_equal(resumed[field][0], changed[field][0]), f"Branch initial state: {field}"
        )
    require(
        changed["amount"][-1, 0] > resumed["amount"][-1, 0], "Rechallenge did not change outcome"
    )
    parent = load_snapshot(root / "pulse" / "snapshots" / "step-000122")
    for name in ("resumed", "rechallenged"):
        require(
            runs[name][1]["provenance"]["parent_snapshot_sha256"] == parent.fingerprint,
            f"Parent provenance: {name}",
        )
    return {
        "status": "pass",
        "scope": "M1a synthetic engineering fixture, not biological heredity",
        "verified_utc": datetime.now(timezone.utc).isoformat(),
        "replay_suffix_byte_equal": True,
        "branch_initial_state_equal": True,
        "all_artifact_hashes_valid": True,
        "analytic_tolerance_fmol": 2e-8,
        "runs": {name: value[2] for name, value in runs.items()},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--output", type=Path, help="optional new JSON receipt, never overwritten")
    args = parser.parse_args()
    report = verify(args.root)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
