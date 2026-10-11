"""Read-only audit of a stopped NUM-009 reference-gate attempt.

Authenticate and replay the completed prefix without inventing unrun cases or
using a complete-session receipt. This auditor imports no ODE/RHS module.
"""

import argparse
import ast
import hashlib
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_finite_extracellular_reference import (  # noqa: E402
    load,
    read_arrays,
    replay,
    safe_member,
    sha,
)
from tests import finite_extracellular_numerical_checks as checks  # noqa: E402
from tests import finite_extracellular_numerical_data as data  # noqa: E402


def audit(path):
    path = Path(path)
    failure, session, plan, cases = (
        load(path / name)
        for name in ("failure.json", "session.json", "protocol.json", "cases.json")
    )
    checks.require(
        failure["status"] == "stopped" and not (path / "verification.json").exists(),
        "Require a stopped, unqualified attempt",
    )
    checks.require(
        failure["error_type"] == "ValueError"
        and failure["reason"] == "Reference qualification failed; stop without extending the plan",
        "Unsupported stopped-attempt reason",
    )
    current, resolved = data.load_panel()
    checks.require(
        plan == current and cases == [c.definition() for c in resolved],
        "Resolved inputs differ from frozen cases",
    )
    checks.require(
        sha(path / "protocol.json") == session["protocol_sha256"] == data.PANEL_SHA256,
        "Frozen protocol identity mismatch",
    )
    checks.require(
        session["resources"] == plan["resources"]
        and session["coordinate_contract"] == plan["coordinate_contract"],
        "Scope/resource or coordinate mismatch",
    )
    runtime = session["runtime"]
    checks.require(
        (runtime["python"], runtime["numpy"], runtime["scipy"]) == ("3.13.5", "2.5.3", "1.18.1")
        and len(runtime["cpu_affinity"]) == 1
        and runtime["thread_environment"]
        == dict.fromkeys(
            ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"),
            "1",
        ),
        "Unqualified reference runtime",
    )
    declarations = [
        n
        for n in ast.parse(
            (ROOT / "scripts/qualify_finite_extracellular_reference.py").read_text()
        ).body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SOURCE_FILES" for t in n.targets)
    ]
    checks.require(
        len(declarations) == 1
        and set(ast.literal_eval(declarations[0].value)) == set(session["source_sha256"]),
        "Source inventory mismatch",
    )
    with zipfile.ZipFile(path / "sources.zip") as archive:
        checks.require(
            len(archive.namelist()) == len(set(archive.namelist()))
            and set(archive.namelist()) == set(session["source_sha256"]),
            "Source capsule membership mismatch",
        )
        for name, digest in session["source_sha256"].items():
            checks.require(
                hashlib.sha256(archive.read(name)).hexdigest()
                == digest
                == sha(safe_member(ROOT, name)),
                "Source identity mismatch: " + name,
            )
        checks.require(
            archive.read(str(data.PANEL.relative_to(ROOT)))
            == (path / "protocol.json").read_bytes(),
            "Protocol differs from capsule",
        )
    files = failure["files_sha256"]
    actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
    checks.require(actual == set(files) | {"failure.json"}, "Missing/unexpected attempt files")
    for name, digest in files.items():
        checks.require(sha(safe_member(path, name)) == digest, "Payload hash mismatch: " + name)
    size = (
        sum(safe_member(path, n).stat().st_size for n in files)
        + (path / "failure.json").stat().st_size
    )
    checks.require(
        size <= plan["resources"]["artifact_bytes"]
        and math.isfinite(failure["seconds"])
        and 0 <= failure["seconds"] < plan["resources"]["session_wall_seconds"]
        and failure["production_change"] is False,
        "Attempt resource/scope mismatch",
    )
    ids = failure["completed_cases"]
    checks.require(
        ids
        and ids == [c["id"] for c in cases[: len(ids)]]
        and failure["case"] == ids[-1]
        and len(ids) < len(cases),
        "Invalid stopped case prefix",
    )
    attempts = [(s["id"], s) for s in plan["references"]] + [
        (f"rk4_{dt:g}", {"method": "RK4", "dt_s": dt}) for dt in plan["candidate"]["steps_s"]
    ]
    checks.require(
        failure["attempt"] == attempts[-1][0], "Stop is not after the complete case ladder"
    )
    expected_files = {"sources.zip", "protocol.json", "cases.json", "session.json"}
    analyses, diagnostics, rows, replayed = {}, {}, 0, 0
    completed_candidates, failed_candidates, rejected_candidates = 0, 0, 0
    for case in cases[: len(ids)]:
        records, stats = {}, {}
        for name, setting in attempts:
            stem = f"{case['id']}/{name}"
            expected_files.update((stem + ".npz", stem + ".json"))
            arrays, item = (
                read_arrays(path / (stem + ".npz"), plan["resources"]["artifact_bytes"]),
                load(path / (stem + ".json")),
            )
            records[name], stats[name] = arrays, item
            kind, complete = setting["method"], item["status"] == "complete"
            checks.validate_record(case, arrays, kind, complete=complete)
            checks.require(all(item[k] == v for k, v in setting.items()), "Attempt settings differ")
            if kind == "RK4":
                if complete:
                    checks.require(
                        np.array_equal(
                            checks.native_mesh(case, item["dt_s"]), arrays["native_times_s"]
                        )
                        and item["rhs_calls"] == 5 * item["accepted_steps"]
                        and item["rejected_trial"] is None,
                        "Candidate mesh/call mismatch",
                    )
                    completed_candidates += 1
                else:
                    checks.rejection_check(case, arrays, item)
                    rejected_candidates += 1
            else:
                checks.require(
                    complete
                    and np.max(np.diff(arrays["native_times_s"]))
                    <= setting["max_step_s"] * (1 + 1e-12),
                    "Reference maximum step/completion mismatch",
                )
            checks.require(
                item["accepted_steps"] == len(arrays["native_times_s"]) - 1
                and 0 < item["rhs_calls"] <= plan["resources"]["max_rhs_calls_per_attempt"]
                and item["minimum_trial_amount_fmol"] > 0
                and item["minimum_trial_outside_amount_fmol"] > 0
                and item["max_trial_countercharge_C"] <= 1e-20
                and item["max_trial_abs_x"] <= 50
                and item["max_trial_edge_abs_x"] <= 50
                and 0 <= item["trial_gate_range"][0] <= item["trial_gate_range"][1] <= 1
                and all(math.isfinite(x) for x in item["trial_voltage_range_V"])
                and math.isfinite(item["seconds"])
                and item["seconds"] >= 0,
                "Invalid trial/resource summary",
            )
            channel_range = item["trial_channel_voltage_range_V"]
            checks.require(
                -0.120 <= channel_range[0] <= channel_range[1] <= 0.060
                if case["world"]["channels"]
                else channel_range is None,
                "Invalid channel domain summary",
            )
            if complete:
                checks.require(
                    np.array_equal(replay(case, arrays, kind), arrays["sample_state"]),
                    "Dense replay differs from saved observations",
                )
                replayed += 1
                rows += len(arrays["sample_times_s"])
        analysis = checks.analyze_case(case, records, stats, plan)
        analyses[case["id"]] = analysis
        checks.require(
            analysis == load(path / case["id"] / "analysis.json"), "Recomputed analysis differs"
        )
        expected_files.add(case["id"] + "/analysis.json")
        failed_candidates += sum(
            not analysis["attempts"][n]["pass"] and stats[n]["status"] == "complete"
            for n, _ in attempts
            if n.startswith("rk4_")
        )
        if not analysis["references_pass"]:
            diagnostic = {}
            for name in ("radau", "bdf", "refined"):
                arrays = records[name]
                inside = data.layout(case).split(arrays["native_state"])["amount"]
                outside = data.layout(case).split(arrays["native_state"])["extracellular_amount"]
                observed = data.layout(case).split(arrays["sample_state"])["extracellular_amount"]
                initial = checks.geometry(case)["outside_initial"]
                physical = observed + initial
                diagnostic[name] = {
                    "maximum_native_outside_increment_fmol": checks.maximum(outside),
                    "maximum_observed_outside_increment_fmol": checks.maximum(observed),
                    "native_outside_is_negative_inside_sum_exact": bool(
                        np.array_equal(outside, -np.sum(inside, axis=1))
                    ),
                    "reconstructed_observed_outside_amounts_constant": bool(
                        np.array_equal(physical, np.broadcast_to(physical[0], physical.shape))
                    ),
                    "native_accounting_pass": analysis["attempts"][name]["native_accounting"][
                        "pass"
                    ],
                    "observed_accounting_pass": analysis["attempts"][name]["sampled_accounting"][
                        "pass"
                    ],
                    "controls": analysis["attempts"][name]["controls"],
                }
            diagnostics[case["id"]] = diagnostic
    checks.require(set(files) == expected_files, "Completed-prefix payload inventory mismatch")
    checks.require(
        all(analyses[n]["references_pass"] for n in ids[:-1])
        and not analyses[ids[-1]]["references_pass"],
        "Stop does not match first failed reference gate",
    )
    return {
        "schema": "cells.num009_stopped_attempt_audit@1",
        "status": "pass",
        "qualification_status": "stopped_not_qualified",
        "selected_dt_s": None,
        "completed_case_ladders": len(ids),
        "reference_passing_cases": len(ids) - 1,
        "unrun_cases": [c["id"] for c in cases[len(ids) :]],
        "attempts": len(ids) * len(attempts),
        "replayed_arrays": replayed,
        "replayed_sample_rows": rows,
        "payloads": len(files),
        "source_files": len(session["source_sha256"]),
        "completed_candidates": completed_candidates,
        "failed_completed_candidates": failed_candidates,
        "rejected_candidates": rejected_candidates,
        "stopped_case": failure["case"],
        "diagnosis": diagnostics,
        "seconds": failure["seconds"],
        "artifact_bytes": size,
        "failure_receipt_sha256": sha(path / "failure.json"),
        "auditor_sha256": sha(Path(__file__)),
        "solver_rerun": False,
        "production_change": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("path", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.output is not None:
        checks.require(
            not args.output.exists()
            and not args.output.resolve().is_relative_to(args.path.resolve()),
            "Audit output must be new and outside input session",
        )
    result = audit(args.path)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
