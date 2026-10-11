"""MODEL-005 production acceptance against frozen NUM-004, never fitted endpoints."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.core.runner import branch_checkpoint, run  # noqa: E402
from cells.core.specs import load_spec  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes, write_run  # noqa: E402
from cells.models import source_pair as model  # noqa: E402
from scripts.audit_source_pair_numerics import audit_directory, check_state  # noqa: E402
from tests import reference_source_pair_numerics as ref  # noqa: E402
from tests.source_pair_fixtures import reference_model, spec_for, values  # noqa: E402

REFERENCE_SHA = "fa8f7332bccf033f04236c1ff81dc7e838533d00828db63b17847e4613294190"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def audit_run(path):
    manifest = json.loads((path / "manifest.json").read_text())
    require(manifest["source_hashes"] == source_hashes(), "Production changed")
    require(manifest["runtime"] == runtime_identity(), "Runtime changed")
    require(
        manifest["observer"]["sampling"] == model.OBSERVATION_SAMPLING, "Wrong observation contract"
    )
    require(manifest["numerics"]["stage_domain"] == model.STAGE_DOMAIN_ID, "Missing checked domain")
    for name, digest in manifest["files_sha256"].items():
        p = (path / name).resolve()
        require(p.is_relative_to(path.resolve()) and sha(p) == digest, f"Changed payload: {name}")
    spec = load_spec(path / "resolved_config.json")
    require(spec.fingerprint == manifest["definition_sha256"], "Definition mismatch")
    oracle = reference_model(spec)
    with np.load(path / "trajectory.npz", allow_pickle=False) as data:
        arrays = dict(data)
    accounting = {}
    for prefix in ("", "observed_"):
        state = model.STATE_TYPE(*(arrays[prefix + name] for name in model.STATE_TYPE._fields))
        accounting[prefix or "accepted"] = check_state(values(state), oracle.panel, oracle.case)
    for name in manifest["snapshots"]:
        snapshot = load_snapshot(path / name)
        at = np.flatnonzero(arrays["accepted_times"] == snapshot.checkpoint.time)[0]
        for field, value in zip(
            snapshot.checkpoint.state._fields, snapshot.checkpoint.state, strict=True
        ):
            np.testing.assert_array_equal(value, arrays[field][at])
        for field, value in zip(
            snapshot.checkpoint.layout._fields, snapshot.checkpoint.layout, strict=True
        ):
            np.testing.assert_array_equal(value, arrays["cell_ids" if field == "ids" else field])
    state = model.STATE_TYPE(*(arrays["observed_" + name] for name in model.STATE_TYPE._fields))
    expected = ref.observations(oracle, arrays["observation_times"], values(state))
    flux = np.c_[
        arrays["observed_leak_flux"].reshape(-1, 6),
        (
            np.array([-3, 2, 0])[None, :, None] * arrays["observed_pump_cycle_flux"][:, None, :]
        ).reshape(-1, 6),
        arrays["observed_ionic_junction_flux"][..., 0],
        arrays["observed_mirna_junction_flux"],
    ]
    for got, want, atol in (
        (arrays["observed_voltage_V"], expected["voltage"], 1e-13),
        (arrays["observed_gate_scales"][..., 0], expected["gate_scale"], 2e-12),
        (flux, expected["membrane_and_junction_flux"], 1e-18),
        (arrays["observed_bound_complexes"], expected["packet"][:, 9:16], 2e-12),
    ):
        np.testing.assert_allclose(got, want, atol=atol, rtol=2e-11)
    np.testing.assert_array_equal(
        arrays["observed_free_mirna_proxy"], arrays["observed_regulation"][:, 0]
    )
    return {
        "manifest_sha256": sha(path / "manifest.json"),
        "payloads_checked": len(manifest["files_sha256"]),
        "snapshots_checked": len(manifest["snapshots"]),
        "independent_accounting": accounting,
        "independent_readout_samples": len(arrays["observation_times"]),
    }


def compare(oracle, times, actual, expected):
    scores = ref.scores(oracle, times, actual, expected)
    require(max(scores.values()) <= 1, f"Frozen numerical target failed: {scores}")
    return scores


def verify(output, reference):
    require(not output.exists(), "Output must be new")
    require(
        sha(reference / "verification.json") == REFERENCE_SHA, "Frozen NUM-004 identity differs"
    )
    panel = ref.eq.load_panel()
    reference_audit = audit_directory(reference, panel)
    output.mkdir(parents=True)
    initial_sources, runtime = source_hashes(), runtime_identity()
    sources = [ROOT / "src/cells" / name for name in initial_sources] + [
        Path(__file__),
        ROOT / "tests/source_pair_fixtures.py",
        ROOT / "tests/unit/test_source_pair.py",
        ROOT / "tests/integration/test_source_pair_cli.py",
        ROOT / "scripts/audit_source_pair_numerics.py",
        ROOT / "tests/reference_source_pair_numerics.py",
        ROOT / "tests/reference_source_pair.py",
        ROOT / "tests/reference_emt.py",
        ref.eq.PANEL,
        ref.PROTOCOL,
        ROOT / "requirements-lock.txt",
        ROOT / "pyproject.toml",
        *(ROOT / f"configs/source_pair_{name}.json" for name in ("baseline", "controls", "branch")),
    ]
    source_identity = {str(path.relative_to(ROOT)): sha(path) for path in sources}
    with zipfile.ZipFile(
        output / "implementation_sources.zip", "x", zipfile.ZIP_DEFLATED
    ) as capsule:
        for path in sources:
            capsule.write(path, path.relative_to(ROOT))
    records = {}
    baseline = None
    for case in panel["cases"]:
        print(f"Source-compatible JAX pair: {case['id']}", flush=True)
        with np.load(
            reference / case["id"] / "rk4-0.01/trajectory.npz", allow_pickle=False
        ) as data:
            times, expected, grid = data["sample_times"], data["refined"], data["accepted_times"]
        result = run(spec_for(case, samples=times))
        np.testing.assert_array_equal(result.times, grid)
        oracle = ref.Model(panel, case)
        accepted = compare(
            oracle, grid, values(result.history), expected[np.searchsorted(times, grid)]
        )
        observed = compare(oracle, times, values(result.observations), expected)
        checkpoints = {0.0, case["end_time"] / 2, *(e["time"] for e in case.get("events", []))}
        write_run(output / case["id"], result, checkpoint_times=tuple(checkpoints))
        records[case["id"]] = audit_run(output / case["id"]) | {
            "accepted_scores": accepted,
            "observed_scores": observed,
        }
        if case["id"] == "S01":
            baseline = result
    require(baseline is not None, "Missing baseline")
    snapshot = load_snapshot(output / "S01/snapshots/step-000500")
    resumed = run(snapshot.spec, snapshot.checkpoint)
    for a, b in zip(baseline.history, resumed.history, strict=True):
        np.testing.assert_array_equal(a[500:], b)
    for name, value in vars(baseline.observations).items():
        np.testing.assert_array_equal(
            value[baseline.observations.times >= 5], getattr(resumed.observations, name)
        )
    provenance = {"parent_snapshot_sha256": snapshot.fingerprint, "branch_time": 5.0}
    write_run(output / "resumed", resumed, provenance=provenance | {"operation": "resume"})
    records["resumed"] = audit_run(output / "resumed")
    changed = load_spec(ROOT / "configs/source_pair_branch.json")
    branch = run(changed, branch_checkpoint(snapshot.spec, snapshot.checkpoint, changed))
    oracle_model = reference_model(changed)
    oracle = ref.integrate_reference(oracle_model, refinement=0.1)
    accepted_reference, observed_reference = (
        oracle.sample(branch.times),
        oracle.sample(branch.observations.times),
    )
    accepted = compare(oracle_model, branch.times, values(branch.history), accepted_reference)
    observed = compare(
        oracle_model, branch.observations.times, values(branch.observations), observed_reference
    )
    for a, b in zip(snapshot.checkpoint.state, branch.history, strict=True):
        np.testing.assert_array_equal(a, b[0])
    write_run(output / "branched", branch, provenance=provenance | {"operation": "branch"})
    records["branched"] = audit_run(output / "branched") | {
        "accepted_scores": accepted,
        "observed_scores": observed,
    }
    write_json(
        output / "branch-reference.json",
        {"case": oracle_model.case, "panel": oracle_model.panel, "solver": oracle.stats},
    )
    np.savez_compressed(
        output / "branch-reference.npz",
        accepted_times=branch.times,
        observed_times=branch.observations.times,
        accepted_reference=accepted_reference,
        observed_reference=observed_reference,
        **{
            f"segment_{i}_{key}": value
            for i, s in enumerate(oracle.segments)
            for key, value in (("times", s.t), ("increment_state", s.y.T))
        },
    )
    require(
        source_hashes() == initial_sources and runtime_identity() == runtime,
        "Production/runtime changed during acceptance",
    )
    require(
        all(sha(ROOT / name) == digest for name, digest in source_identity.items()),
        "Acceptance sources changed",
    )
    report = {
        "status": "pass",
        "scope": "bounded nominal source model; not full assay parity or physical EMT",
        "source_hashes": initial_sources,
        "runtime": runtime,
        "reference_receipt_sha256": REFERENCE_SHA,
        "reference_audit": reference_audit,
        "implementation_source_hashes": source_identity,
        "runs": records,
        "exact_replay_state_and_observations": True,
        "files_sha256": {
            str(p.relative_to(output)): sha(p) for p in output.rglob("*") if p.is_file()
        },
    }
    write_json(output / "verification.json", report)
    print(f"pass: {len(records)} production runs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--reference", type=Path, default=ROOT / "runs/num-004-2026-09-08/qualification-01"
    )
    args = parser.parse_args()
    verify(args.output, args.reference)
