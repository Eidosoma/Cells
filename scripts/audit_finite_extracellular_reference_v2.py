"""Read-only NUM-009 v2 source, saved trajectory, reduction and verdict audit.

No numerical-dynamics import or ODE solve. Reuse independently written frozen
dense-basis replay with an explicit flat-coordinate adapter.
"""

import argparse
import ast
import json
import math
import sys
import zipfile
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_multispecies_reference import replay as old_replay  # noqa: E402
from tests import finite_extracellular_numerical_checks as checks  # noqa: E402
from tests import finite_extracellular_numerical_data_v2 as data  # noqa: E402

load = data.spec.ion.load_json
sha = data.sha


def replay(case, arrays, kind):
    view = {"parameters": {"species_ids": [], "initial_amount_fmol": np.empty(0)}}
    return old_replay(view, arrays, kind)


def safe_member(root, name):
    checks.require(
        isinstance(name, str) and name and not Path(name).is_absolute(), "Invalid artifact path"
    )
    path = root / name
    checks.require(
        ".." not in Path(name).parts
        and path.resolve().is_relative_to(root.resolve())
        and path.is_file()
        and not any(p.is_symlink() for p in (path, *path.parents) if p.is_relative_to(root)),
        "Unsafe or missing artifact path",
    )
    return path


def read_arrays(path, limit):
    with zipfile.ZipFile(path) as archive:
        checks.require(
            sum(i.file_size for i in archive.infolist()) <= limit
            and len(archive.namelist()) == len(set(archive.namelist())),
            "Oversized/duplicate array payload",
        )
    with np.load(path, allow_pickle=False) as arrays:
        return {key: arrays[key] for key in arrays.files}


def audit(path):
    path = Path(path)
    receipt, session, plan, cases = (
        load(path / name)
        for name in ("verification.json", "session.json", "protocol.json", "cases.json")
    )
    checks.require(receipt["status"] in ("pass", "not_qualified"), "Session is not complete")
    checks.require(
        sha(path / "protocol.json")
        == receipt["protocol_sha256"]
        == session["protocol_sha256"]
        == data.PANEL_SHA256,
        "Frozen protocol identity mismatch",
    )
    current_plan, resolved = data.load_panel()
    checks.require(
        plan == current_plan and cases == [c.definition() for c in resolved],
        "Resolved case differs from frozen inputs",
    )
    checks.require(receipt["source_sha256"] == session["source_sha256"], "Source lists disagree")
    declarations = [
        n
        for n in ast.parse(
            (ROOT / "scripts/qualify_finite_extracellular_reference_v2.py").read_text()
        ).body
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Name) and t.id == "SOURCE_FILES" for t in n.targets)
    ]
    checks.require(
        len(declarations) == 1
        and set(ast.literal_eval(declarations[0].value)) == set(session["source_sha256"]),
        "Source inventory differs from declared capsule",
    )
    actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
    checks.require(
        actual == set(receipt["files_sha256"]) | {"verification.json"},
        "Missing or unexpected session files",
    )
    for name, digest in receipt["files_sha256"].items():
        checks.require(sha(safe_member(path, name)) == digest, f"Payload hash mismatch: {name}")
    total = sum((path / name).stat().st_size for name in receipt["files_sha256"])
    checks.require(
        total == receipt["artifact_bytes_before_receipt"]
        and total + (path / "verification.json").stat().st_size
        <= plan["resources"]["artifact_bytes"],
        "Artifact quota/size summary mismatch",
    )
    with zipfile.ZipFile(path / "sources.zip") as archive:
        checks.require(
            len(archive.namelist()) == len(set(archive.namelist()))
            and set(archive.namelist()) == set(session["source_sha256"]),
            "Invalid source capsule membership",
        )
        import hashlib

        for name, digest in session["source_sha256"].items():
            checks.require(
                hashlib.sha256(archive.read(name)).hexdigest()
                == digest
                == sha(safe_member(ROOT, name)),
                f"Archived/current source identity mismatch: {name}",
            )
        checks.require(
            archive.read(str(data.PANEL.relative_to(ROOT)))
            == (path / "protocol.json").read_bytes(),
            "Protocol differs from capsule",
        )
    checks.require(
        len(cases) == 14 and [c["id"] for c in cases] == receipt["completed_cases"],
        "Incomplete case panel",
    )
    checks.require(
        session["resources"] == plan["resources"]
        and session["coordinate_contract"] == plan["coordinate_contract"]
        and receipt["scope"] == plan["scope"]
        and receipt["production_change"] is False
        and receipt["production_version"] == "0.13.0",
        "Session scope/resource mismatch",
    )
    runtime = session["runtime"]
    checks.require(
        len(runtime["cpu_affinity"]) == 1
        and set(runtime["thread_environment"])
        == {"OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"}
        and set(runtime["thread_environment"].values()) == {"1"},
        "Invalid CPU worker/thread claim",
    )
    checks.require(
        runtime["python"] == "3.13.5"
        and runtime["numpy"] == "2.5.3"
        and runtime["scipy"] == "1.18.1",
        "Unqualified dense-basis runtime",
    )
    analyses, rows, replayed, rejected, summaries = {}, 0, 0, 0, {}
    expected_files = {"sources.zip", "protocol.json", "cases.json", "session.json"}
    attempts = [(s["id"], s["method"]) for s in plan["references"]] + [
        (f"rk4_{dt:g}", "RK4") for dt in plan["candidate"]["steps_s"]
    ]
    for case in cases:
        records, stats = {}, {}
        for name, kind in attempts:
            stem = f"{case['id']}/{name}"
            expected_files.update((stem + ".npz", stem + ".json"))
            arrays = read_arrays(path / (stem + ".npz"), plan["resources"]["artifact_bytes"])
            item = load(path / (stem + ".json"))
            records[name], stats[name] = arrays, item
            checks.require(
                item == receipt["cases"][case["id"]]["attempts"][name],
                "Attempt statistics disagree",
            )
            complete = item["status"] == "complete"
            checks.validate_record(case, arrays, kind, complete=complete)
            if kind == "RK4":
                dt = next(v for v in plan["candidate"]["steps_s"] if name == f"rk4_{v:g}")
                checks.require(
                    item["method"] == "RK4" and item["dt_s"] == dt,
                    "Candidate settings differ from frozen method",
                )
                if complete:
                    checks.require(
                        np.array_equal(checks.native_mesh(case, dt), arrays["native_times_s"])
                        and item["rhs_calls"] == 5 * item["accepted_steps"]
                        and item["rejected_trial"] is None,
                        "Candidate mesh/call count mismatch",
                    )
                else:
                    checks.rejection_check(case, arrays, item)
                    rejected += 1
            else:
                settings = next(s for s in plan["references"] if s["id"] == name)
                checks.require(
                    complete and all(item[k] == v for k, v in settings.items()),
                    "Reference settings differ from frozen method",
                )
                checks.require(
                    np.max(np.diff(arrays["native_times_s"]))
                    <= settings["max_step_s"] * (1 + 1e-12),
                    "Reference maximum step exceeded",
                )
            shape = data.layout(case)
            columns = (shape.n + 1) * shape.s + 2 * shape.k + shape.e
            if kind != "RK4":
                checks.require(
                    item["jacobian_evaluations"] == item["njev"] > 0
                    and item["jacobian_rhs_calls"] == (1 + 2 * columns) * item["njev"]
                    and item["central_columns"] + item["one_sided_columns"]
                    == columns * item["njev"]
                    and item["rhs_calls"] == item["nfev"] + item["jacobian_rhs_calls"],
                    "Jacobian work accounting mismatch",
                )
            else:
                checks.require(
                    all(
                        item[k] == 0
                        for k in (
                            "jacobian_evaluations",
                            "jacobian_rhs_calls",
                            "central_columns",
                            "one_sided_columns",
                        )
                    ),
                    "Candidate must not use the reference Jacobian",
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
                and all(math.isfinite(v) for v in item["trial_voltage_range_V"])
                and math.isfinite(item["seconds"])
                and item["seconds"] >= 0,
                "Invalid trial/resource summary",
            )
            if complete:
                checks.require(
                    np.array_equal(replay(case, arrays, kind), arrays["sample_state"]),
                    "Dense replay differs from saved observations",
                )
                replayed += 1
                rows += len(arrays["sample_times_s"])
            channel_range = item["trial_channel_voltage_range_V"]
            checks.require(
                -0.120 <= channel_range[0] <= channel_range[1] <= 0.060
                if case["world"]["channels"]
                else channel_range is None,
                "Invalid trial channel-voltage summary",
            )
        analyses[case["id"]] = checks.analyze_case(case, records, stats, plan)
        expected_files.add(f"{case['id']}/analysis.json")
        checks.require(
            analyses[case["id"]] == load(path / case["id"] / "analysis.json"),
            "Recomputed analysis differs",
        )
        summaries[case["id"]] = checks.final_summary(case, records["refined"], stats)
        checks.require(
            receipt["cases"][case["id"]] == summaries[case["id"]],
            "Final summary mismatch",
        )
    selection = checks.select_candidate(analyses, plan)
    checks.require(
        set(receipt["files_sha256"]) == expected_files, "Scientific payload inventory mismatch"
    )
    witness = checks.depletion_witness(cases, summaries, plan)
    checks.require(receipt["depletion_witness"] == witness, "Depletion witness differs")
    if not witness["pass"]:
        selection["status"] = "not_qualified"
    checks.require(
        all(receipt[k] == v for k, v in selection.items())
        and receipt["rejected_candidates"] == rejected,
        "Candidate selection/rejection count differs",
    )
    checks.require(
        math.isfinite(receipt["seconds"])
        and 0 <= receipt["seconds"] < plan["resources"]["session_wall_seconds"],
        "Invalid session wall-time claim",
    )
    return {
        "status": "pass",
        "qualification_status": receipt["status"],
        "selected_dt_s": receipt["selected_dt_s"],
        "cases": len(cases),
        "replayed_arrays": replayed,
        "replayed_sample_rows": rows,
        "rejected_candidates": rejected,
        "depletion_witness": witness,
        "payloads": len(receipt["files_sha256"]),
        "source_files": len(session["source_sha256"]),
        "verification_sha256": sha(path / "verification.json"),
        "auditor_sha256": sha(Path(__file__)),
        "solver_rerun": False,
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
