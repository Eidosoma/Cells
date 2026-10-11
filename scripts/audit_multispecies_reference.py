"""Read-only NUM-006 source/payload, dense replay and recomputed-verdict audit.

No solver is run. Analysis identities are shared with the qualification checker;
dense replay is separately expressed here and imports no solver/RHS module.
"""

import argparse
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests import multispecies_numerical_checks as checks  # noqa: E402

AUDIT_REVISION = 2
AUDITOR_SOURCE = "scripts/audit_multispecies_reference.py"
PROTOCOL_SOURCE = "configs/reference/multispecies_trajectories_v1.json"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def replay(case, arrays, kind):
    """Reconstruct common-grid samples from native states and the recorded basis."""
    queries, mesh = arrays["sample_times_s"], arrays["native_times_s"]
    result = np.empty_like(arrays["sample_state"])
    bins = np.minimum(np.searchsorted(mesh, queries, side="right") - 1, len(mesh) - 2)
    for index in np.unique(bins):
        positions = np.flatnonzero(bins == index)
        t = queries[positions]
        c = arrays["coefficients"][index]
        degree = int(arrays["degree"][index])
        if kind == "BDF":
            factors = (t - arrays["shift"][index, :degree, None]) / arrays["denominator"][
                index, :degree, None
            ]
            result[positions] = (
                c[:, 1 : degree + 1] @ np.cumprod(factors, axis=0) + c[:, 0, None]
            ).T
        else:
            theta = (t - mesh[index]) / (mesh[index + 1] - mesh[index])
            if kind == "Radau":
                powers = np.cumprod(np.tile(theta, (degree, 1)), axis=0)
                values = c[:, 1 : degree + 1] @ powers
                values += c[:, 0, None]
            elif kind == "RK4":
                values = c[:, 0, None] + theta * (
                    c[:, 1, None] + theta * (c[:, 2, None] + theta * c[:, 3, None])
                )
            else:
                raise ValueError("Unknown dense replay method")
            result[positions] = values.T
    nodes = np.searchsorted(mesh, queries)
    exact = mesh[nodes] == queries
    result[exact] = arrays["native_state"][nodes[exact]]
    if kind == "RK4":
        result[:, : len(case["parameters"]["species_ids"])] -= case["parameters"][
            "initial_amount_fmol"
        ]
    return result


def audit(path):
    path = Path(path)
    receipt = json.loads((path / "verification.json").read_text())
    checks.require(receipt["status"] in ("pass", "not_qualified"), "Session is not complete")
    session = json.loads((path / "session.json").read_text())
    plan = json.loads((path / "protocol.json").read_text())
    cases = json.loads((path / "cases.json").read_text())
    checks.require(
        sha((path / "protocol.json").read_bytes())
        == receipt["protocol_sha256"]
        == session["protocol_sha256"],
        "Protocol identity mismatch",
    )
    checks.require(receipt["source_sha256"] == session["source_sha256"], "Source lists disagree")
    actual_files = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
    checks.require(
        actual_files == set(receipt["files_sha256"]) | {"verification.json"},
        "Missing/unexpected session files",
    )
    for name, digest in receipt["files_sha256"].items():
        checks.require(sha((path / name).read_bytes()) == digest, f"Payload hash mismatch: {name}")
    checks.require(
        sum((path / name).stat().st_size for name in actual_files)
        <= plan["resources"]["artifact_bytes"],
        "Artifact quota exceeded",
    )
    with zipfile.ZipFile(path / "sources.zip") as capsule:
        checks.require(
            set(capsule.namelist()) == set(receipt["source_sha256"]),
            "Unexpected source capsule members",
        )
        for name, digest in receipt["source_sha256"].items():
            checks.require(
                sha(capsule.read(name)) == digest,
                f"Archived source identity mismatch: {name}",
            )
            # An independently versioned read-only auditor may be strengthened
            # after a run. Every archived byte remains checked; solver, numerical
            # checker, original tests, protocol and dependencies must stay current.
            if name != AUDITOR_SOURCE:
                checks.require(
                    sha((ROOT / name).read_bytes()) == digest,
                    f"Current numerical source identity mismatch: {name}",
                )
        checks.require(
            capsule.read(PROTOCOL_SOURCE) == (path / "protocol.json").read_bytes(),
            "Session protocol differs from the frozen source capsule",
        )
        physical = json.loads(capsule.read(plan["physical_panel"]))
        checks.require(
            sha(capsule.read(plan["physical_panel"])) == plan["physical_panel_sha256"],
            "Physical panel changed",
        )
    # Resolve frozen case bindings again without running or importing a trajectory solver.
    from tests import reference_multispecies as spec

    source_cases = {c["id"]: c["assembly"] for c in physical["cases"]}
    checks.require(
        len(cases) == len(plan["cases"]) == 14
        and [c["id"] for c in cases] == receipt["completed_cases"],
        "Case panel is incomplete",
    )
    analyses, sample_rows, replayed_arrays = {}, 0, 0
    for case, declared in zip(cases, plan["cases"], strict=True):
        from dataclasses import asdict

        p = spec.resolve(source_cases[declared["assembly"]])
        profile = plan["profiles"][declared["profile"]]
        expected_controls = [
            {
                "time_s": c["time_s"],
                "pump": c["pump"],
                "leak": [0.0 if s in c["blocked_species"] else c["leak"] for s in p.species_ids],
            }
            for c in profile["controls"]
        ]
        normalized = json.loads(json.dumps(asdict(p)))
        checks.require(
            case
            == {
                "id": declared["id"],
                "parameters": normalized,
                "horizon_s": profile["horizon_s"],
                "controls": expected_controls,
            },
            "Resolved case differs from frozen physical/profile inputs",
        )
        records = {}
        attempts = [(s["id"], s["method"]) for s in plan["references"]]
        attempts.extend((f"rk4_{dt:g}", "RK4") for dt in plan["candidate"]["steps_s"])
        for name, kind in attempts:
            payload = path / case["id"] / f"{name}.npz"
            with zipfile.ZipFile(payload) as archive:
                checks.require(
                    sum(i.file_size for i in archive.infolist())
                    <= plan["resources"]["artifact_bytes"],
                    "Oversized decompressed attempt",
                )
            with np.load(payload, allow_pickle=False) as data:
                records[name] = {key: data[key] for key in data.files}
            arrays = records[name]
            checks.validate_record(case, arrays, kind)
            checks.require(
                np.array_equal(replay(case, arrays, kind), arrays["sample_state"]),
                f"Dense replay mismatch: {case['id']}/{name}",
            )
            stats = json.loads((path / case["id"] / f"{name}.json").read_text())
            checks.require(
                stats == receipt["cases"][case["id"]]["attempts"][name], "Attempt stats disagree"
            )
            if kind == "RK4":
                step = next(dt for dt in plan["candidate"]["steps_s"] if name == f"rk4_{dt:g}")
                expected_mesh = np.unique(
                    np.r_[
                        np.arange(math.ceil(case["horizon_s"] / step)) * step,
                        [c["time_s"] for c in case["controls"]],
                        case["horizon_s"],
                    ]
                )
                checks.require(
                    stats["method"] == "RK4"
                    and stats["dt_s"] == step
                    and np.array_equal(arrays["native_times_s"], expected_mesh)
                    and stats["rhs_calls"] == 5 * stats["accepted_steps"],
                    "Candidate settings/grid/call count differ from the frozen method",
                )
            else:
                settings = next(s for s in plan["references"] if s["id"] == name)
                checks.require(
                    all(stats[key] == value for key, value in settings.items()),
                    "Reference settings differ from the frozen method",
                )
                checks.require(
                    np.max(np.diff(arrays["native_times_s"]))
                    <= settings["max_step_s"] * (1 + 1e-12),
                    "Reference native step exceeds the frozen maximum",
                )
            checks.require(
                stats["rhs_calls"] <= plan["resources"]["max_rhs_calls_per_attempt"]
                and stats["accepted_steps"] == len(arrays["native_times_s"]) - 1
                and 0 < stats["minimum_trial_amount_fmol"]
                and stats["max_trial_abs_x"] <= 50,
                "Invalid stage/resource summary",
            )
            sample_rows += len(arrays["sample_times_s"])
            replayed_arrays += 1
        analyses[case["id"]] = checks.analyze_case(case, records, plan)
        checks.require(
            analyses[case["id"]] == json.loads((path / case["id"] / "analysis.json").read_text()),
            "Recomputed numerical/accounting verdict differs",
        )
        final = records["refined"]["sample_state"][-1]
        count = len(p.species_ids)
        summary = receipt["cases"][case["id"]]
        checks.require(
            summary["samples"] == len(records["refined"]["sample_times_s"])
            and summary["final_amount_fmol"]
            == (np.asarray(p.initial_amount_fmol) + final[:count]).tolist()
            and summary["final_voltage_V"] == float(checks.voltage(case, final[:count]))
            and summary["final_pump_cycles_fmol"] == float(final[-2])
            and summary["final_dissipation_pJ"] == float(final[-1]),
            "Final summary mismatch",
        )
    selection = checks.select_candidate(analyses, plan)
    checks.require(
        all(receipt[key] == value for key, value in selection.items()),
        "Candidate selection was not reproduced",
    )
    checks.require(
        math.isfinite(receipt["seconds"])
        and receipt["seconds"] < plan["resources"]["session_wall_seconds"],
        "Invalid session wall-time claim",
    )
    return {
        "status": "pass",
        "audit_revision": AUDIT_REVISION,
        "qualification_status": receipt["status"],
        "selected_dt_s": receipt["selected_dt_s"],
        "cases": len(cases),
        "replayed_arrays": replayed_arrays,
        "replayed_sample_rows": sample_rows,
        "source_files": len(receipt["source_sha256"]),
        "payloads": len(receipt["files_sha256"]),
        "verification_sha256": sha((path / "verification.json").read_bytes()),
        "audit_sha256": sha(Path(__file__).read_bytes()),
        "archived_auditor_sha256": receipt["source_sha256"][AUDITOR_SOURCE],
        "audit_tests_sha256": sha(
            (ROOT / "tests/unit/test_multispecies_artifact_audit.py").read_bytes()
        ),
        "solver_rerun": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument(
        "--output", type=Path, help="Optional new audit JSON outside the session directory"
    )
    args = parser.parse_args()
    if args.output is not None:
        checks.require(not args.output.exists(), "Audit output already exists")
        checks.require(
            not args.output.resolve().is_relative_to(args.path.resolve()),
            "Audit must not mutate its input session",
        )
    report = audit(args.path)
    payload = json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
