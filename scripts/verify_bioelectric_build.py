"""Verify production JAX against the pinned NUM-002 trajectories; new outputs only.

The independent oracle and captured arrays predate production. No reference
tolerance, physics, or candidate target is adjusted by this verifier.
"""

import argparse
import hashlib
import json
import sys
import zipfile
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import load_spec  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run  # noqa: E402
from cells.models import bioelectric_cell as model  # noqa: E402
from tests.bioelectric_fixtures import (  # noqa: E402
    TARGETS,
    assert_targets,
    case_for,
    errors,
    physical_values,
    spec_for,
)
from tests.reference_bioelectric import (  # noqa: E402
    CHARGE_PER_FMOL,
    NU,
    Case,
    Z,
    integrate_reference,
    panel,
)

REFERENCE_SHA256 = "8cf0f7a6d33867f5a1172b6eff949c887bf47bf8c0c93d616477e72d4c27d94d"


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def verify_reference(path):
    receipt = path / "verification.json"
    require(sha256(receipt) == REFERENCE_SHA256, "NUM-002 receipt identity differs")
    manifest = json.loads(receipt.read_text())
    for name, digest in manifest["files_sha256"].items():
        file = (path / name).resolve()
        require(file.is_relative_to(path.resolve()), "Reference payload escaped its directory")
        require(sha256(file) == digest, f"Reference payload changed: {name}")
    with zipfile.ZipFile(path / "reference_sources.zip") as archive:
        for name in ("tests/reference_bioelectric.py", "requirements-lock.txt"):
            require(
                archive.read(name) == (ROOT / name).read_bytes(),
                f"Pinned reference source changed: {name}",
            )
    return len(manifest["files_sha256"])


def audit_run(path):
    manifest = json.loads((path / "manifest.json").read_text())
    require(manifest["source_hashes"] == source_hashes(), "Production source changed")
    require(manifest["runtime"] == runtime_identity(), "Runtime changed")
    require(
        manifest["observer"]["sampling"] == model.OBSERVATION_SAMPLING, "Wrong observation policy"
    )
    for name, digest in manifest["files_sha256"].items():
        file = (path / name).resolve()
        require(
            file.is_relative_to(path.resolve()) and sha256(file) == digest,
            f"Run payload mismatch: {name}",
        )
    spec = load_spec(path / "resolved_config.json")
    require(spec.fingerprint == manifest["definition_sha256"], "Definition mismatch")
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    for name in manifest["snapshots"]:
        snapshot = load_snapshot(path / name)
        index = int(np.flatnonzero(data["accepted_times"] == snapshot.checkpoint.time)[0])
        for field in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(
                data[field][index], getattr(snapshot.checkpoint.state, field)
            )
        for field, value in zip(
            snapshot.checkpoint.layout._fields, snapshot.checkpoint.layout, strict=True
        ):
            np.testing.assert_array_equal(data["cell_ids" if field == "ids" else field], value)
    p = case_for(spec).parameters
    exchange = data["leak_transferred"][:, :, 0] + NU * data["pump_cycles"][:, :1]
    residual = data["amount"][:, :, 0] - p.initial_amount - exchange
    material = float(np.max(np.abs(residual)))
    charge = float(np.max(np.abs(residual @ Z))) * CHARGE_PER_FMOL / p.capacitance
    require(material <= 1e-10 and charge <= 1e-8, "Independent species/charge accounting failed")
    require(np.min(data["amount"][:, :, 0]) > 0, "Nonpositive physical amount")
    # Voltage and chemical work are derived independently, never extra ODE states.
    np.testing.assert_array_equal(
        data["observed_voltage_V"][:, 0], p.voltage(data["observed_amount"][:, :, 0])
    )
    np.testing.assert_array_equal(
        data["observed_chemical_work_J"],
        -1e-15 * p.atp_free_energy_J_per_mol * data["observed_pump_cycles"],
    )
    return data, {
        "manifest_sha256": sha256(path / "manifest.json"),
        "definition_sha256": spec.fingerprint,
        "payloads_checked": len(manifest["files_sha256"]),
        "snapshots_checked": len(manifest["snapshots"]),
        "max_balance_error_fmol": material,
        "max_charge_balance_error_V": charge,
        "final_amounts_fmol": data["amount"][-1, :, 0].tolist(),
        "final_voltage_V": float(p.voltage(data["amount"][-1, :, 0])),
        "final_pump_cycles_fmol": float(data["pump_cycles"][-1, 0]),
        "executed_steps": len(data["accepted_times"]) - 1,
        "timings": manifest["timings"],
    }


def verify(output, reference):
    require(not output.exists(), "Output already exists; choose a new directory")
    reference_payloads = verify_reference(reference)
    output.mkdir(parents=True, exist_ok=False)
    records, baseline = {}, None
    for case in panel():
        print(f"Verifying physical JAX cell: {case.name}", flush=True)
        require(
            json.loads((reference / case.name / "case.json").read_text())
            == json.loads(json.dumps(case.definition())),
            "Panel definition changed",
        )
        with np.load(reference / case.name / "trajectories.npz", allow_pickle=False) as archive:
            samples = archive["sample_times_s"].copy()
            grid = archive["accepted_times_s"].copy()
            expected = archive["radau_refined"].copy()
        spec = spec_for(case, samples=samples)
        result = run(spec)
        np.testing.assert_array_equal(result.times, grid)
        indices = np.searchsorted(samples, grid)
        accepted = errors(case.parameters, physical_values(result.history), expected[indices])
        observed = errors(case.parameters, physical_values(result.observations), expected)
        assert_targets(accepted)
        assert_targets(observed)
        checkpoints = (0.0, case.horizon / 2)
        if case.name == "baseline_10s":
            baseline = result
            checkpoints = (*checkpoints, 6.0)
        write_run(output / case.name, result, checkpoint_times=checkpoints)
        _, record = audit_run(output / case.name)
        records[case.name] = {**record, "accepted_errors": accepted, "observed_errors": observed}
    require(baseline is not None, "Missing baseline case")
    # Unchanged restart, retaining anchors AND accumulated exchange ledgers.
    path = output / "baseline_10s/snapshots/step-001200"
    snapshot = load_snapshot(path)
    resumed = run(snapshot.spec, snapshot.checkpoint)
    offset = snapshot.checkpoint.step_index
    for a, b in zip(baseline.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[offset:], b)
    provenance = {"parent_snapshot_sha256": snapshot.fingerprint, "branch_time": 6.0}
    write_run(output / "resumed", resumed, provenance={"operation": "resume", **provenance})
    _, records["resumed"] = audit_run(output / "resumed")
    # The shipped branch has genuinely independent future leak/pump schedules.
    changed = load_spec(ROOT / "configs/bioelectric_branch.json")
    # Observation cadence is permitted to change; pinned baseline may have denser observations.
    branch = run(changed, branch_checkpoint(snapshot.spec, snapshot.checkpoint, changed))
    case = case_for(changed, "future_branch")
    oracle = integrate_reference(case, rtol=1e-12, atol=1e-14)
    accepted = errors(case.parameters, physical_values(branch.history), oracle.sample(branch.times))
    observed = errors(
        case.parameters,
        physical_values(branch.observations),
        oracle.sample(branch.observations.times),
    )
    assert_targets(accepted)
    assert_targets(observed)
    write_run(output / "branched", branch, provenance={"operation": "branch", **provenance})
    _, records["branched"] = audit_run(output / "branched")
    records["branched"].update(accepted_errors=accepted, observed_errors=observed)
    # Separate, bounded eager/JIT comparison. No long eager or GPU benchmark.
    short = spec_for(Case("eager", horizon=0.05))
    compiled = run(short)
    eager = run(replace(short, execution=replace(short.execution, jit=False)))
    eager_difference = float(
        np.max(np.abs(physical_values(compiled.history) - physical_values(eager.history)))
    )
    require(eager_difference <= 3e-13, "Eager/JIT comparison failed")
    receipt = {
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "claim_scope": (
            "MODEL-003 physical engineering; "
            "not source assays, calibrated biology, organs, or GPU performance"
        ),
        "runtime": runtime_identity(),
        "source_hashes": source_hashes(),
        "reference_receipt_sha256": REFERENCE_SHA256,
        "reference_path": str(reference.resolve()),
        "reference_payloads_checked": reference_payloads,
        "trajectory_targets": TARGETS,
        "material_target_fmol": 1e-10,
        "charge_target_V": 1e-8,
        "verifier_sha256": sha256(Path(__file__)),
        "adapter_sha256": sha256(ROOT / "tests/bioelectric_fixtures.py"),
        "independent_oracle_sha256": sha256(ROOT / "tests/reference_bioelectric.py"),
        "eager_jit_max_absolute_state_difference": eager_difference,
        "exact_unchanged_restart": True,
        "runs": records,
    }
    write_json(output / "verification.json", receipt)
    print(
        json.dumps(
            {"status": "pass", "runs": len(records), "receipt": str(output / "verification.json")},
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, default=ROOT / "runs/num-002-2026-09-08/qualification"
    )
    args = parser.parse_args()
    verify(args.output, args.reference)
