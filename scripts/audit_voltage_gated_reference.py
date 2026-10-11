"""Read-only NUM-007 frozen-source, trajectory replay and verdict audit.

No ODE solve or numerical-dynamics import. The earlier independently written
dense-basis replay is reused unchanged with the larger numeric state extent.
"""

import argparse
import ast
import copy
import hashlib
import json
import math
import sys
import zipfile
from dataclasses import asdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.audit_multispecies_reference import replay  # noqa: E402
from tests import reference_voltage_gated_channel as spec  # noqa: E402
from tests import voltage_gated_numerical_checks as checks  # noqa: E402

PROTOCOL_SOURCE = "configs/reference/voltage_gated_trajectories_v1.json"
PANEL_SHA256 = "aa07cd7c200a2a93c9484d7b45d5a47a28a766e3958db1511bd230af4a5bd9e0"


def sha(payload):
    return hashlib.sha256(payload).hexdigest()


def load(path):
    return spec.ionic.load_json(path)


def expected_case(declared, plan, physical):
    definition = copy.deepcopy(
        next(c["definition"] for c in physical["cases"] if c["id"] == declared["assembly"])
    )
    preparation = declared["preparation"]
    if preparation is not None:
        definition["channel"]["initial_gate"] = preparation["initial_gate"]
        if "initial_voltage_V" in preparation:
            for name in ("initial_voltage_V", "fixed_charge_equivalent_fmol"):
                definition["assembly"]["cell"][name] = preparation[name]
    resolved = spec.resolve(definition)
    profile = plan["profiles"][declared["profile"]]
    controls = [
        {
            "time_s": c["time_s"],
            "leak": [
                0.0 if s in c["blocked_species"] else c["leak"]
                for s in resolved.assembly.species_ids
            ],
            "pump": c["pump"],
            "availability": c["availability"],
        }
        for c in profile["controls"]
    ]
    return json.loads(
        json.dumps(
            {
                "id": declared["id"],
                "parameters": asdict(resolved.assembly),
                "channel": asdict(resolved.channel),
                "horizon_s": profile["horizon_s"],
                "controls": controls,
            }
        )
    )


def safe_member(root, name):
    checks.require(
        isinstance(name, str) and name and not Path(name).is_absolute(), "Invalid artifact path"
    )
    path = root / name
    checks.require(
        ".." not in Path(name).parts
        and path.resolve().is_relative_to(root.resolve())
        and path.is_file()
        and not path.is_symlink(),
        "Unsafe or missing artifact path",
    )
    return path


def audit(path):
    path = Path(path)
    receipt = load(path / "verification.json")
    session, plan, cases = (
        load(path / name) for name in ("session.json", "protocol.json", "cases.json")
    )
    checks.require(receipt["status"] in ("pass", "not_qualified"), "Session is not complete")
    checks.require(
        sha((path / "protocol.json").read_bytes())
        == receipt["protocol_sha256"]
        == session["protocol_sha256"]
        == PANEL_SHA256,
        "Frozen protocol identity mismatch",
    )
    checks.require(receipt["source_sha256"] == session["source_sha256"], "Source lists disagree")
    qualifier = ROOT / "scripts/qualify_voltage_gated_reference.py"
    declarations = [
        node
        for node in ast.parse(qualifier.read_text()).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "SOURCE_FILES" for target in node.targets
        )
    ]
    checks.require(
        len(declarations) == 1
        and set(ast.literal_eval(declarations[0].value)) == set(session["source_sha256"]),
        "Source inventory differs from the declared capsule",
    )
    actual = {str(p.relative_to(path)) for p in path.rglob("*") if p.is_file()}
    checks.require(
        actual == set(receipt["files_sha256"]) | {"verification.json"},
        "Missing or unexpected session files",
    )
    for name, digest in receipt["files_sha256"].items():
        checks.require(
            sha(safe_member(path, name).read_bytes()) == digest, f"Payload hash mismatch: {name}"
        )
    checks.require(
        sum((path / name).stat().st_size for name in actual) <= plan["resources"]["artifact_bytes"],
        "Artifact quota exceeded",
    )
    checks.require(
        sum((path / name).stat().st_size for name in receipt["files_sha256"])
        == receipt["artifact_bytes_before_receipt"],
        "Artifact size summary mismatch",
    )
    with zipfile.ZipFile(path / "sources.zip") as capsule:
        checks.require(
            len(capsule.namelist()) == len(set(capsule.namelist()))
            and set(capsule.namelist()) == set(session["source_sha256"]),
            "Invalid source capsule membership",
        )
        for name, digest in session["source_sha256"].items():
            checks.require(
                sha(capsule.read(name)) == digest
                and sha(safe_member(ROOT, name).read_bytes()) == digest,
                f"Archived/current source identity mismatch: {name}",
            )
        checks.require(
            capsule.read(PROTOCOL_SOURCE) == (path / "protocol.json").read_bytes(),
            "Session protocol differs from frozen source capsule",
        )
        physical_bytes = capsule.read(plan["physical_panel"])
        checks.require(
            sha(physical_bytes) == plan["physical_panel_sha256"],
            "Frozen physical identity mismatch",
        )
        physical = json.loads(physical_bytes)
    checks.require(
        len(cases) == len(plan["cases"]) == 14
        and [c["id"] for c in cases] == receipt["completed_cases"],
        "Incomplete case panel",
    )
    checks.require(
        session["resources"] == plan["resources"]
        and receipt["scope"] == plan["scope"]
        and receipt["production_change"] is False,
        "Session scope/resource mismatch",
    )
    analyses, replayed, rows, rejected = {}, 0, 0, 0
    attempts = [(s["id"], s["method"]) for s in plan["references"]] + [
        (f"rk4_{dt:g}", "RK4") for dt in plan["candidate"]["steps_s"]
    ]
    for case, declared in zip(cases, plan["cases"], strict=True):
        checks.require(
            case == expected_case(declared, plan, physical),
            "Resolved case differs from frozen preparation",
        )
        records, stats = {}, {}
        for name, kind in attempts:
            payload = path / case["id"] / f"{name}.npz"
            with zipfile.ZipFile(payload) as archive:
                checks.require(
                    sum(i.file_size for i in archive.infolist())
                    <= plan["resources"]["artifact_bytes"]
                    and len(archive.namelist()) == len(set(archive.namelist())),
                    "Oversized/duplicate array payload",
                )
            with np.load(payload, allow_pickle=False) as data:
                records[name] = {key: data[key] for key in data.files}
            arrays, item = records[name], load(path / case["id"] / f"{name}.json")
            stats[name] = item
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
                    mesh = np.unique(
                        np.r_[
                            np.arange(math.ceil(case["horizon_s"] / dt)) * dt,
                            [c["time_s"] for c in case["controls"]],
                            case["horizon_s"],
                        ]
                    )
                    checks.require(
                        np.array_equal(mesh, arrays["native_times_s"])
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
            checks.require(
                item["accepted_steps"] == len(arrays["native_times_s"]) - 1
                and item["rhs_calls"] <= plan["resources"]["max_rhs_calls_per_attempt"]
                and item["minimum_trial_amount_fmol"] > 0
                and item["max_trial_abs_x"] <= 50
                and 0 <= item["trial_gate_range"][0] <= item["trial_gate_range"][1] <= 1
                and -0.120
                <= item["trial_voltage_range_V"][0]
                <= item["trial_voltage_range_V"][1]
                <= 0.060
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
        analyses[case["id"]] = checks.analyze_case(case, records, stats, plan)
        checks.require(
            analyses[case["id"]] == load(path / case["id"] / "analysis.json"),
            "Recomputed analysis differs",
        )
        final, n = records["refined"]["sample_state"][-1], len(case["parameters"]["species_ids"])
        summary = receipt["cases"][case["id"]]
        expected = {
            "samples": len(records["refined"]["sample_times_s"]),
            "final_amount_fmol": (
                np.asarray(case["parameters"]["initial_amount_fmol"]) + final[:n]
            ).tolist(),
            "final_voltage_V": float(checks.voltage(case, final[:n])),
            "final_pump_cycles_fmol": float(final[2 * n]),
            "final_dissipation_pJ": float(final[2 * n + 1]),
            "final_gate": final[2 * n + 2 : 2 * n + 4].tolist(),
            "final_channel_fmol": float(final[-1]),
            "attempts": stats,
        }
        checks.require(summary == expected, "Final summary mismatch")
    selection = checks.select_candidate(analyses, plan)
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
        "payloads": len(receipt["files_sha256"]),
        "source_files": len(session["source_sha256"]),
        "verification_sha256": sha((path / "verification.json").read_bytes()),
        "auditor_sha256": sha(Path(__file__).read_bytes()),
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
            "Audit output must be new and outside its input session",
        )
    result = audit(args.path)
    payload = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if args.output is not None:
        with args.output.open("x") as handle:
            handle.write(payload)
    print(payload, end="")


if __name__ == "__main__":
    main()
