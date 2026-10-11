"""Read-only registered CORE-010 production artifacts; no trajectory solver calls."""

import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cells.batch_io import load_batch_snapshot  # noqa: E402
from cells.core.batch import load_batch  # noqa: E402
from cells.core.specs import load_spec, read_json  # noqa: E402
from cells.io import _sha256 as sha  # noqa: E402
from cells.io import load_snapshot, runtime_identity, source_hashes  # noqa: E402
from cells.models import spatial_extracellular as model  # noqa: E402
from scripts import spatial_extracellular_acceptance_plan as plan  # noqa: E402
from scripts.spatial_extracellular_acceptance_resources import (  # noqa: E402
    authenticate_prior_stop,
    from_registration,
    get_resources,
)
from scripts.spatial_extracellular_production_audit import (  # noqa: E402
    ARRAY_FIELDS,
    LAYOUT_FIELDS,
    OBS_FIELDS,
    STATE_FIELDS,
    audit_run,
    authenticate,
    evidence_path,
    inspect_arrays,
    numeric_archive,
    require,
    state_values,
)
from scripts.test_spatial_extracellular_build import implementation_hashes  # noqa: E402
from scripts.verify_batch_windows_build import audit_cohort, suffix  # noqa: E402
from scripts.verify_windows_build import audit_windows  # noqa: E402
from tests import spatial_extracellular_numerical_checks as checks  # noqa: E402
from tests.spatial_extracellular_fixtures import REFERENCE, REFERENCE_SHA, load_cases  # noqa: E402


def implementation(resources=None):
    resources = resources or get_resources()
    return implementation_hashes() | {
        str(path.relative_to(ROOT)): sha(path) for path in resources.capture_paths
    }


def compare(case, first, second, limits, *, exact=False):
    require(set(first) == set(second) == ARRAY_FIELDS, "Comparison coverage differs")
    for key in (*LAYOUT_FIELDS, "accepted_times", "observation_times"):
        np.testing.assert_array_equal(first[key], second[key], err_msg=key)
    if exact:
        for key in ARRAY_FIELDS:
            np.testing.assert_array_equal(first[key], second[key], err_msg=key)
            require(
                first[key].dtype == second[key].dtype
                and first[key].shape == second[key].shape
                and first[key].tobytes() == second[key].tobytes(),
                f"Byte-exact array differs: {key}",
            )
        return {"exact_arrays": len(first)}
    results = {}
    for label, times, prefix in (
        ("native", "accepted_times", ""),
        ("observed", "observation_times", "observed_"),
    ):
        a, b = state_values(case, first, prefix), state_values(case, second, prefix)
        phi_a = checks.potential_values(case, first[times], a)[0]
        phi_b = checks.potential_values(case, second[times], b)[0]
        results[label] = checks.errors(case, a, b, phi_a, phi_b, limits, factor=0.001)
        require(results[label]["pass"], "Execution-path comparison failed")
    return results | {"comparison_factor": 0.001, "bitwise_required": False}


def collect_stream(path, *, cohort=False):
    """Assemble audit-only arrays. Production still records bounded non-overlapping chunks."""
    path = Path(path)
    if cohort:
        spec = load_batch(path / "resolved_batch.json")
        specs = {w.world_id: w.simulation for w in spec.worlds}
    else:
        spec = load_spec(path / "resolved_config.json")
        specs = {0: spec}
    manifest = read_json(evidence_path(path, "manifest.json"))
    common = {
        "schema_version",
        "kind",
        "status",
        "definition_sha256",
        "runtime",
        "source_hashes",
        "device",
        "policy",
        "index",
        "files_sha256",
        "observer",
        "numerics",
        "resources",
        "timings",
        "timing_scope",
        "provenance",
    }
    require(
        set(manifest)
        == common | ({"mapping", "checkpoint_every_windows", "worlds"} if cohort else set()),
        "Stream manifest schema differs",
    )
    require(
        type(manifest["schema_version"]) is int
        and manifest["schema_version"] == 1
        and manifest["index"] == "windows.jsonl",
        "Stream schema/index differs",
    )
    require(manifest["definition_sha256"] == spec.fingerprint, "Stream definition identity differs")
    require(
        manifest["observer"] == {"id": model.OBSERVER_ID, "sampling": model.OBSERVATION_SAMPLING},
        "Stream observer differs",
    )
    require(
        manifest["numerics"]
        == {
            "grid": "independent_zero_anchored_event_split"
            if cohort
            else "zero_anchored_event_split",
            "jit": next(iter(specs.values())).execution.jit,
            "stage_domain": model.STAGE_DOMAIN_ID,
        },
        "Stream numerical identity differs",
    )

    def snapshot_files(relative):
        return (
            {
                f"{relative}/manifest.json",
                *(
                    f"{relative}/world-{i}/{name}"
                    for i in specs
                    for name in ("manifest.json", "state.npz")
                ),
            }
            if cohort
            else {f"{relative}/{name}" for name in ("manifest.json", "state.npz")}
        )

    fixed = (
        {
            "resolved_batch.json" if cohort else "resolved_config.json",
            "summary.json",
            "windows.jsonl",
        }
        | snapshot_files("checkpoint_initial")
        | snapshot_files("checkpoint_final")
    )
    require(set(manifest["files_sha256"]) == fixed, "Fixed stream inventory differs")
    file_hashes = dict(manifest["files_sha256"])
    parts = {i: {} for i in specs}
    with evidence_path(path, "windows.jsonl").open() as handle:
        for line in handle:
            record = json.loads(line)
            if record["kind"] in ("checkpoint", "cohort_checkpoint"):
                expected_path = (
                    f"snapshots/round-{record['completed_rounds']:010d}"
                    if cohort
                    else f"snapshots/step-{record['step_index']:010d}"
                )
                require(record["path"] == expected_path, "Stream checkpoint path differs")
                for name in snapshot_files(expected_path):
                    require(name not in file_hashes, "Duplicate stream checkpoint")
                    file_hashes[name] = sha(evidence_path(path, name))
                continue
            require(
                record["kind"] == ("world_window" if cohort else "window"),
                "Unexpected stream record",
            )
            identity = record["world_id"] if cohort else 0
            require(identity in parts, "Unexpected stream world")
            keys = {"accepted_times", *STATE_FIELDS}
            if record["observation_records"]:
                keys |= {"observation_times", *OBS_FIELDS}
            expected_path = (
                f"worlds/world-{identity}/" if cohort else ""
            ) + f"chunks/window-{record['index']:08d}.npz"
            require(record["path"] == expected_path, "Stream chunk path differs")
            target = evidence_path(path, record["path"])
            require(sha(target) == record["sha256"], "Stream chunk hash differs")
            require(record["path"] not in file_hashes, "Duplicate stream chunk")
            file_hashes[record["path"]] = record["sha256"]
            for key, value in numeric_archive(target, keys).items():
                parts[identity].setdefault(key, []).append(value)
    authenticate(path, file_hashes, extra=("manifest.json",))
    result = {}
    for i, s in specs.items():
        _, layout = model.initial_values(s)
        result[i] = {k: np.concatenate(v) for k, v in parts[i].items()}
        result[i].update(zip(LAYOUT_FIELDS, layout, strict=True))
    # Check zip member uniqueness for EVERY scalar state in nested cohort snapshots.
    for saved in path.rglob("state.npz"):
        numeric_archive(
            evidence_path(path, str(saved.relative_to(path))),
            {*STATE_FIELDS, *model.LAYOUT_TYPE._fields},
        )
    return spec, result


def audit_stream(path, cases, protocol, *, group=None, expected_spec=None):
    spec, arrays = collect_stream(path, cohort=group is not None)
    if expected_spec is not None:
        require(spec == expected_spec, "Registered stream definition differs")
    if group is None:
        physical = {"0": inspect_arrays(cases, spec, arrays[0], protocol)}
        structural = audit_windows(Path(path), arrays[0])
    else:
        available = {c.id: c for c in cases}
        names = plan.GROUPS[group]
        require(len(spec.worlds) == len(names), "Cohort world count differs")
        physical = {
            str(w.world_id): inspect_arrays(
                available[name], w.simulation, arrays[w.world_id], protocol
            )
            for w, name in zip(spec.worlds, names, strict=True)
        }
        structural = audit_cohort(Path(path), arrays)
    return arrays, {"structure": structural, "physics": physical}


def panel_results(path):
    """Recompute the complete registered panel, before or after receipt publication."""
    path = Path(path)
    protocol, cases = load_cases()
    available = {c.id: c for c in cases}
    names = {f"{m}/{c.id}" for m in plan.SCALAR_MODES for c in cases} | {
        "branch/membrane_block_release"
    }
    arrays, records = {}, {}
    for name in sorted(names):
        mode, case_id = name.split("/")
        case = available[case_id]
        arrays[name], records[name] = audit_run(
            path / name, case, protocol, expected_spec=plan.registered_spec(case, mode)
        )
    comparisons = {}
    for c in cases:
        original, restarted = arrays[f"jit/{c.id}"], arrays[f"resumed/{c.id}"]
        spec = plan.registered_spec(c)
        parent = path / "jit" / c.id
        snapshot = read_json(parent / "manifest.json")["snapshots"][0]
        cp = load_snapshot(parent / snapshot).checkpoint
        comparisons[f"resumed/{c.id}"] = compare(
            c, suffix(original, cp, model), restarted, protocol["trajectory_limits"], exact=True
        )
        comparisons[f"eager/{c.id}"] = compare(
            c, original, arrays[f"eager/{c.id}"], protocol["trajectory_limits"]
        )
        require(spec.experiment.end_time == c.horizon_s, "Case horizon changed")
    branch_name = "branch/membrane_block_release"
    parent = load_snapshot(path / "branch-parent")
    target = plan.registered_spec(available["membrane_block_release"])
    require(
        parent.checkpoint.time == parent.spec.experiment.end_time == 0.0713,
        "Branch boundary differs",
    )
    require(
        parent.spec.model == target.model and parent.spec.execution == target.execution,
        "Branch physical identity differs",
    )
    require(
        parent.spec.experiment.membranes[0][-1].availability == 1
        and target.experiment.membranes[0][1].availability == 0,
        "Branch control change differs",
    )
    require(
        np.any(parent.checkpoint.state.membrane_transferred != 0)
        and np.any(parent.checkpoint.state.membrane_dissipated_energy_pJ != 0),
        "Branch lost nonzero history",
    )
    for key, value in zip(STATE_FIELDS, parent.checkpoint.state, strict=True):
        np.testing.assert_array_equal(arrays[branch_name][key][0], value)
    comparisons[branch_name] = compare(
        available["membrane_block_release"],
        suffix(arrays["jit/membrane_block_release"], parent.checkpoint, model),
        arrays[branch_name],
        protocol["trajectory_limits"],
        exact=True,
    )
    streams = {}
    for group, names in plan.GROUPS.items():
        name = plan.WINDOW_CASES[group]
        result, streams[f"windows/{group}"] = audit_stream(
            path / "windows" / group,
            available[name],
            protocol,
            expected_spec=plan.registered_spec(available[name]),
        )
        comparisons[f"windows/{group}"] = compare(
            available[name], arrays[f"jit/{name}"], result[0], protocol["trajectory_limits"]
        )
        batch = plan.cohort(group, cases)
        result, streams[f"cohorts/{group}"] = audit_stream(
            path / "cohorts" / group, cases, protocol, group=group, expected_spec=batch
        )
        for i, name in enumerate(names, 1):
            comparisons[f"cohorts/{group}/{i}"] = compare(
                available[name], arrays[f"jit/{name}"], result[i], protocol["trajectory_limits"]
            )
        saved = load_batch_snapshot(path / "cohorts" / group / "snapshots/round-0000000004")
        resumed, streams[f"cohort-resumed/{group}"] = audit_stream(
            path / "cohort-resumed" / group, cases, protocol, group=group, expected_spec=batch
        )
        for i, name in enumerate(names, 1):
            comparisons[f"cohort-resumed/{group}/{i}"] = compare(
                available[name],
                suffix(result[i], saved.checkpoints[i], model),
                resumed[i],
                protocol["trajectory_limits"],
            )
    return {"runs": records, "streams": streams, "comparisons": comparisons}


def audit(path):
    path = Path(path).absolute()
    receipt = read_json(evidence_path(path, "verification.json"))
    require(
        receipt["schema"] == "cells.core010_production_acceptance@1"
        and receipt["status"] == "pass",
        "Incomplete CORE-010 receipt",
    )
    require(not (path / "failure.json").exists(), "Stopped session cannot pass")
    authenticate(path, receipt["files_sha256"], extra=("verification.json",))
    registration = read_json(path / "registration.json")
    resources = from_registration(registration)
    prior_stop = authenticate_prior_stop(resources)
    if prior_stop is not None:
        require(
            read_json(path / "prior-stopped-audit.json") == prior_stop,
            "Prior stopped-evidence audit differs",
        )
    require(
        registration["source_hashes"] == receipt["source_hashes"] == source_hashes(),
        "Registered production differs",
    )
    require(
        registration["runtime"] == receipt["runtime"] == runtime_identity(),
        "Registered runtime differs",
    )
    require(
        registration["implementation_files_sha256"]
        == receipt["implementation_files_sha256"]
        == implementation(resources),
        "Registered implementation differs",
    )
    require(
        registration["protocol_sha256"] == sha(resources.protocol), "Registered protocol differs"
    )
    require(
        registration["max_seconds"] == resources.max_seconds
        and registration["max_artifact_bytes"] == plan.MAX_BYTES,
        "Registered budget differs",
    )
    require(
        registration["cpu_affinity"] == [0, 1, 2, 3]
        and registration["thread_environment"] == dict.fromkeys(plan.THREADS, "1"),
        "Registered CPU resources differ",
    )
    require(
        registration["reference_solver_rerun"] is False
        and registration["scientific_inputs_changed"] is False,
        "Reference scope changed",
    )
    require(0 <= receipt["seconds"] <= resources.max_seconds, "Acceptance wall budget exceeded")
    require(
        sum(p.stat().st_size for p in path.rglob("*") if p.is_file()) <= plan.MAX_BYTES,
        "Acceptance artifact budget exceeded",
    )
    with zipfile.ZipFile(path / "implementation_sources.zip") as archive:
        require(
            len(archive.namelist()) == len(set(archive.namelist()))
            and set(archive.namelist()) == set(implementation(resources)),
            "Implementation capsule coverage changed",
        )
        for name, expected in implementation(resources).items():
            require(
                hashlib.sha256(archive.read(name)).hexdigest() == expected,
                "Captured implementation differs",
            )
    require(
        sha(REFERENCE / "verification.json") == REFERENCE_SHA, "Accepted reference identity differs"
    )
    reference_receipt = read_json(REFERENCE / "verification.json")
    authenticate(REFERENCE, reference_receipt["files_sha256"], extra=("verification.json",))
    protocol, cases = load_cases()
    require(
        registration["eager_schedule"] == plan.eager_schedule(cases), "Eager panel coverage differs"
    )
    require(
        registration["definitions"]
        == {
            f"{mode}/{c.id}": plan.registered_spec(c, mode).to_dict()
            for mode in ("jit", "eager", "refined")
            for c in cases
        },
        "Registered definitions differ",
    )
    require(
        set(receipt["runs"])
        == {f"{m}/{c.id}" for m in plan.SCALAR_MODES for c in cases}
        | {"branch/membrane_block_release"},
        "Scalar panel coverage changed",
    )
    actual = panel_results(path)
    records, streams, comparisons = (actual[k] for k in ("runs", "streams", "comparisons"))
    require(records == receipt["runs"], "Replayed scalar verdicts differ")
    require(
        streams == receipt["streams"] and comparisons == receipt["comparisons"],
        "Replayed stream or path verdicts differ",
    )
    require(
        receipt["fresh_process_restart"] == {"status": "pass", "exact_restarts": 14},
        "Missing fresh-process scalar execution",
    )
    require(
        receipt["fresh_process_cohort_restart"] == {"status": "pass", "cohort_restarts": 4},
        "Missing fresh-process cohort execution",
    )
    reference = read_json(path / "reference-audit.json")
    require(
        reference == receipt["reference"]
        and reference["status"] == "verified"
        and reference["ode_calls"] == 0
        and not reference["production_imported"],
        "Preserved reference audit differs",
    )
    archived = read_json(path / "archived-014-audit.json")
    require(
        archived == receipt["archive"]
        and archived["status"] == "pass"
        and archived["scalar_snapshots"] == 235
        and archived["cohort_snapshots"] == 21
        and archived["exact_source_pair_replay"]
        and archived["current_refuses_migration"],
        "Preserved production audit differs",
    )
    require(
        sha(plan.PREVIOUS / "verification.json") == plan.PREVIOUS_SHA
        and sha(plan.RELEASE) == plan.RELEASE_SHA,
        "Accepted production identity differs",
    )
    old_receipt = read_json(plan.PREVIOUS / "verification.json")
    authenticate(plan.PREVIOUS, old_receipt["files_sha256"], extra=("verification.json",))
    old = read_json(path / "old-model-regression.json")
    later = read_json(path / "later-family-regression.json")
    require(
        old == receipt["old_model_regression"] and old["status"] == "pass",
        "Missing old-family replay",
    )
    require(
        later == receipt["later_family_regression"]
        and later["status"] == "pass"
        and len(later["exact_arrays"]) == 54,
        "Missing later-family replay",
    )
    return {
        "status": "pass",
        "reference_cases": len(cases),
        "scalar_runs": len(records),
        "window_runs": 4,
        "cohort_runs": 8,
        "payload_hashes": len(receipt["files_sha256"]),
        "production_sources": len(source_hashes()),
        "implementation_sources": len(implementation(resources)),
        "resource_plan": resources.name,
        "prior_stopped_evidence": prior_stop,
        "maximum_observed_normalized_error": max(
            v["observed"]["errors"]["maximum_normalized_error"] for v in records.values()
        ),
        "verification_sha256": sha(path / "verification.json"),
        "trajectory_solver_calls": 0,
        "production_dynamics_as_oracle": False,
        "stable_release_accepted": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.session), indent=2, sort_keys=True, allow_nan=False))
