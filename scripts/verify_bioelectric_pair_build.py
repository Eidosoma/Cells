"""MODEL-004 acceptance against frozen NUM-003, with complete replay and audit.

New output directories only. The panel, oracle, targets and reference artifacts
predate production. No upstream checkout or external experiment jobs are used.
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
from cells.models import bioelectric_pair as model  # noqa: E402
from scripts.audit_bioelectric_pair_reference import audit, native_balances  # noqa: E402
from tests import reference_bioelectric_pair as ref  # noqa: E402
from tests.bioelectric_pair_fixtures import (  # noqa: E402
    assert_targets,
    case_for,
    physical_values,
    spec_for,
)

REFERENCE_SHA256 = "7c69c33f76dc6658b10b2cd874d9787ef03f1ae817050827c04d9c3596c1df2a"
PANEL_SHA256 = "642c92c6dba5f1f06c1639fbe37c0f69ef962e7018f2003d88c1c34d5ae14d46"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def verify_reference(path):
    require(sha(path / "verification.json") == REFERENCE_SHA256, "NUM-003 receipt differs")
    require(sha(ref.PANEL_PATH) == PANEL_SHA256, "Live panel changed after freeze")
    result = audit(path)  # Checks all payloads/capsule hashes AND native-state accounting.
    with zipfile.ZipFile(path / "reference_sources.zip") as archive:
        for name in (
            "tests/reference_bioelectric.py",
            "tests/reference_bioelectric_pair.py",
            "requirements-lock.txt",
        ):
            require(
                archive.read(name) == (ROOT / name).read_bytes(),
                f"Frozen oracle/runtime changed: {name}",
            )
    return result


def audit_run(path):
    manifest = json.loads((path / "manifest.json").read_text())
    require(manifest["runtime"] == runtime_identity(), "Runtime changed")
    require(manifest["source_hashes"] == source_hashes(), "Production source changed")
    require(manifest["observer"]["sampling"] == model.OBSERVATION_SAMPLING, "Wrong sampling policy")
    require(
        manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID, "Missing trial-domain policy"
    )
    for name, digest in manifest["files_sha256"].items():
        payload = (path / name).resolve()
        require(
            payload.is_relative_to(path.resolve()) and sha(payload) == digest,
            f"Run payload differs: {name}",
        )
    spec = load_spec(path / "resolved_config.json")
    require(spec.fingerprint == manifest["definition_sha256"], "Resolved definition differs")
    with np.load(path / "trajectory.npz", allow_pickle=False) as archive:
        data = {name: archive[name] for name in archive.files}
    for name in manifest["snapshots"]:
        snapshot = load_snapshot(path / name)
        at = int(np.flatnonzero(data["accepted_times"] == snapshot.checkpoint.time)[0])
        for field in model.STATE_TYPE._fields:
            np.testing.assert_array_equal(
                data[field][at], getattr(snapshot.checkpoint.state, field)
            )
        for field, value in zip(
            snapshot.checkpoint.layout._fields, snapshot.checkpoint.layout, strict=True
        ):
            np.testing.assert_array_equal(data["cell_ids" if field == "ids" else field], value)
    case = case_for(spec)
    balances = {}
    for kind, prefix in (("accepted", ""), ("observed", "observed_")):
        state = model.STATE_TYPE(*(data[prefix + name] for name in model.STATE_TYPE._fields))
        values = physical_values(state)
        values[:, :6] -= case.parameters.initial_amount.ravel()
        balances[kind] = native_balances(case.definition(), values)
        for name, value in balances[kind].items():
            require(
                value <= ref.load_panel()[0]["balance_targets"][name],
                f"Independent {kind} {name} balance failed",
            )
    # Derived voltages/currents/work are observations, never a second inventory.
    p = case.parameters
    voltage = p.voltage(data["observed_amount"][:, :, :2])
    np.testing.assert_array_equal(data["observed_voltage_V"][:, :2], voltage)
    np.testing.assert_allclose(
        data["observed_junction_current_A"],
        ref.QF * np.einsum("s,tse->te", ref.Z, data["observed_junction_flux_fmol_per_s"]),
        atol=1e-26,
        rtol=2e-14,
    )
    np.testing.assert_array_equal(
        data["observed_chemical_work_J"],
        -1e-15 * p.cells[0].atp_free_energy_J_per_mol * data["observed_pump_cycles"],
    )
    # Independently express instantaneous flux/gate/dissipation on a declared
    # bounded subset; trajectories/accounting above cover ALL saved states.
    indices = np.unique(np.linspace(0, len(voltage) - 1, min(257, len(voltage)), dtype=int))
    maximum_readout_error = 0.0
    for i in indices:
        expected = ref.rates(
            p,
            data["observed_amount"][i, :, :2],
            voltage[i],
            data["observed_gate"][i, 0],
            case.control_at(data["observation_times"][i]),
        )
        got = (
            data["observed_leak_flux_fmol_per_s"][i, :, :2],
            data["observed_pump_rate_fmol_per_s"][i, :2],
            data["observed_junction_flux_fmol_per_s"][i, :, 0],
            data["observed_gate_rate_per_s"][i, 0],
            data["observed_dissipation_rate_pJ_per_s"][i],
        )
        for a, b in zip(got, expected, strict=True):
            maximum_readout_error = max(maximum_readout_error, float(np.max(np.abs(a - b))))
            np.testing.assert_allclose(a, b, atol=2e-13, rtol=2e-12)
    return {
        "manifest_sha256": sha(path / "manifest.json"),
        "definition_sha256": spec.fingerprint,
        "payloads_checked": len(manifest["files_sha256"]),
        "snapshots_checked": len(manifest["snapshots"]),
        "independent_balances": balances,
        "independent_instantaneous_readout_samples": len(indices),
        "maximum_mixed_unit_readout_error": maximum_readout_error,
        "accepted_states": len(data["accepted_times"]),
        "observed_states": len(data["observation_times"]),
        "final_gate": float(data["gate"][-1, 0]),
        "final_voltage_V": p.voltage(data["amount"][-1, :, :2]).tolist(),
        "timings": manifest["timings"],
    }


def verify(output, reference):
    require(not output.exists(), "Output already exists; choose a new directory")
    reference_audit = verify_reference(reference)
    initial_sources, initial_runtime = source_hashes(), runtime_identity()
    output.mkdir(parents=True, exist_ok=False)
    sources = [ROOT / "src/cells" / name for name in initial_sources] + [
        Path(__file__),
        ROOT / "tests/__init__.py",
        ROOT / "scripts/audit_bioelectric_pair_reference.py",
        ROOT / "tests/bioelectric_pair_fixtures.py",
        ROOT / "tests/reference_bioelectric.py",
        ROOT / "tests/reference_bioelectric_pair.py",
        ROOT / "tests/unit/test_bioelectric_pair.py",
        ref.PANEL_PATH,
        ROOT / "requirements-lock.txt",
        ROOT / "pyproject.toml",
        *(
            ROOT / f"configs/bioelectric_pair_{name}.json"
            for name in ("baseline", "controls", "branch")
        ),
    ]
    capsule_hashes = {str(p.relative_to(ROOT)): sha(p) for p in sources}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", zipfile.ZIP_DEFLATED
    ) as archive:
        for path in sources:
            archive.write(path, path.relative_to(ROOT))
    records, baseline = {}, None
    panel, cases = ref.load_panel()
    for case in cases:
        print(f"Verifying physical JAX pair: {case.id} {case.name}", flush=True)
        require(
            json.loads((reference / case.id / "case.json").read_text())
            == json.loads(json.dumps(case.definition())),
            "Resolved panel changed",
        )
        with np.load(reference / case.id / "candidate/comparison.npz", allow_pickle=False) as a:
            samples, expected = a["sample_times_s"], a["refined"]
        with np.load(reference / case.id / "candidate/accepted.npz", allow_pickle=False) as a:
            grid = a["accepted_times_s"]
        result = run(spec_for(case, samples=samples))
        np.testing.assert_array_equal(result.times, grid)
        accepted = assert_targets(
            case.parameters,
            physical_values(result.history),
            expected[np.searchsorted(samples, grid)],
        )
        observed = assert_targets(case.parameters, physical_values(result.observations), expected)
        checkpoints = {0.0, case.horizon / 2, *(c.time for c in case.controls)}
        if case.id == "Q00":
            baseline = result
            checkpoints.add(6.0)
        write_run(output / case.id, result, checkpoint_times=tuple(checkpoints))
        records[case.id] = {
            **audit_run(output / case.id),
            "accepted_errors": accepted,
            "observed_errors": observed,
        }
    require(baseline is not None, "Missing baseline")
    snapshot = load_snapshot(output / "Q00/snapshots/step-006000")
    resumed = run(snapshot.spec, snapshot.checkpoint)
    for a, b in zip(baseline.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[6000:], b)
    for name, value in vars(baseline.observations).items():
        np.testing.assert_array_equal(
            value[baseline.observations.times >= 6], getattr(resumed.observations, name)
        )
    provenance = {"parent_snapshot_sha256": snapshot.fingerprint, "branch_time": 6.0}
    write_run(output / "resumed", resumed, provenance={"operation": "resume", **provenance})
    records["resumed"] = audit_run(output / "resumed")
    changed = load_spec(ROOT / "configs/bioelectric_pair_branch.json")
    branch = run(changed, branch_checkpoint(snapshot.spec, snapshot.checkpoint, changed))
    for a, b in zip(snapshot.checkpoint.state, branch.history, strict=True):
        np.testing.assert_array_equal(a, b[0])
    for a, b in zip(snapshot.checkpoint.layout, branch.final.layout, strict=True):
        np.testing.assert_array_equal(a, b)
    branch_case = case_for(changed, "future_branch")
    oracle = ref.integrate_reference(branch_case, rtol=1e-12, atol=1e-14)
    expected_accepted = oracle.sample(branch.times)
    expected_observed = oracle.sample(branch.observations.times)
    accepted = assert_targets(
        branch_case.parameters, physical_values(branch.history), expected_accepted
    )
    observed = assert_targets(
        branch_case.parameters, physical_values(branch.observations), expected_observed
    )
    write_run(output / "branched", branch, provenance={"operation": "branch", **provenance})
    records["branched"] = {
        **audit_run(output / "branched"),
        "accepted_errors": accepted,
        "observed_errors": observed,
    }
    write_json(
        output / "branch-reference.json", {"case": branch_case.definition(), "solver": oracle.stats}
    )
    np.savez(
        output / "branch-reference.npz",
        accepted_times_s=branch.times,
        observed_times_s=branch.observations.times,
        accepted_reference=expected_accepted,
        observed_reference=expected_observed,
        **{
            f"segment_{i}_{key}": value
            for i, s in enumerate(oracle.segments)
            for key, value in (("times_s", s.t), ("increment_state", s.y.T))
        },
    )
    short = replace(cases[9], horizon=0.01)
    compiled, eager = run(spec_for(short)), run(spec_for(short, jit=False))
    eager_error = float(
        np.max(np.abs(physical_values(compiled.history) - physical_values(eager.history)))
    )
    require(eager_error <= 3e-13, "Bounded eager/JIT difference")
    require(
        source_hashes() == initial_sources and runtime_identity() == initial_runtime,
        "Source/runtime changed during acceptance",
    )
    require(
        all(sha(ROOT / name) == value for name, value in capsule_hashes.items()),
        "Capsule sources changed during acceptance",
    )
    receipt = {
        "status": "pass",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "MODEL-004 synthetic physical engineering; not source-assay parity, "
            "calibrated biology, organs or GPU performance"
        ),
        "runtime": initial_runtime,
        "source_hashes": initial_sources,
        "reference_receipt_sha256": REFERENCE_SHA256,
        "reference_path": str(reference.resolve()),
        "reference_audit": reference_audit,
        "targets": panel["targets"],
        "balance_targets": panel["balance_targets"],
        "implementation_source_hashes": capsule_hashes,
        "eager_jit_max_absolute_state_difference": eager_error,
        "exact_unchanged_restart_and_observations": True,
        "runs": records,
        "files_sha256": {
            str(p.relative_to(output)): sha(p) for p in sorted(output.rglob("*")) if p.is_file()
        },
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
        "--reference", type=Path, default=ROOT / "runs/num-003-2026-09-08/qualification"
    )
    args = parser.parse_args()
    verify(args.output, args.reference)
