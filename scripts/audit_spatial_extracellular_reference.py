#!/usr/bin/env python3
"""Read-only NUM-010 replay: no ODE, JAX or production imports and no output writes."""

import argparse
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402

from scripts import spatial_extracellular_artifacts as evidence  # noqa: E402
from tests import spatial_extracellular_fields as fields  # noqa: E402
from tests import spatial_extracellular_numerical_checks as checks  # noqa: E402
from tests import spatial_extracellular_numerical_data as data  # noqa: E402

require = checks.require


def audit_rejection(case, arrays, stats):
    """Re-evaluate only the saved offending stage, with its incoming held control."""
    if stats["status"] != "rejected":
        require(stats["rejected_rhs_calls"] == 0, "Unexpected rejected-call count")
        return
    trial = stats["rejected_trial"]
    grid = data.candidate_grid(case, stats["dt_s"])
    left = arrays["native_times_s"][-1]
    at = len(arrays["native_times_s"]) - 1
    right = grid[at + 1]
    require(
        trial["interval_left_s"] == left and trial["interval_right_s"] == right,
        "Rejected trial interval changed",
    )
    control = case.control_at(float(left))
    require(
        trial["control_time_s"] == control.time_s
        and trial["availability"] == list(control.availability),
        "Rejected trial used the wrong held control",
    )
    stages = {"k1": (left, 1), "k2": (left + (right - left) / 2, 2)}
    stages |= {"k3": (stages["k2"][0], 3), "k4": (right, 4), "endpoint": (right, 5)}
    require(trial["stage"] in stages, "Unknown rejected stage")
    time, calls = stages[trial["stage"]]
    require(
        trial["time_s"] == time and stats["rejected_rhs_calls"] == calls,
        "Rejected trial time or stage-call count changed",
    )
    value = np.asarray(trial["state"], dtype=float)
    require(value.shape == (case.size,), "Incomplete rejected trial state")
    try:
        fields.candidate(case, control, value)
    except fields.DomainViolation as exc:
        require(str(exc) == trial["reason"], "Rejected trial reason does not replay")
    else:
        raise ValueError("Saved rejected trial is actually admissible")


def audit_case(root, case, plan):
    records, stats = {}, {}
    definition = json.loads((Path(root) / f"cases/{case.id}/definition.json").read_text())
    require(definition == case.definition(), "Case definition changed")
    for setting in evidence.attempts(plan):
        name = setting["id"]
        arrays, info = evidence.load_record(root, case.id, name)
        require(all(info.get(k) == v for k, v in setting.items()), "Attempt settings changed")
        counters = (
            "rhs_calls",
            "accepted_steps",
            "jacobian_evaluations",
            "jacobian_rhs_calls",
            "central_columns",
            "one_sided_columns",
            "zero_tangent_columns",
        )
        require(
            all(type(info[k]) is int and info[k] >= 0 for k in counters),
            "Invalid attempt counters",
        )
        require(
            info["rhs_calls"] <= plan["resources"]["max_rhs_calls_per_attempt"]
            and info["accepted_steps"] <= plan["resources"]["max_steps_per_attempt"]
            and math.isfinite(info["seconds"])
            and info["seconds"] >= 0,
            "Attempt resource accounting exceeded",
        )
        require(
            info["minimum_trial_amount_fmol"] > 0
            and 0 <= info["maximum_trial_abs_x"] <= 50
            and 0 <= info["maximum_current_normalized"] <= 1
            and 0 <= info["maximum_charge_C"] <= plan["accounting_limits"]["charge_C"]
            and info["maximum_current_residual_A"] >= 0,
            "Invalid actual-trial domain summary",
        )
        if setting["method"] == "RK4":
            require(
                all(info[k] == 0 for k in counters[2:]),
                "Candidate unexpectedly reports Jacobian probes",
            )
            audit_rejection(case, arrays, info)
        else:
            require(info["status"] == "complete", "A reference did not finish")
            require(info["njev"] == info["jacobian_evaluations"], "Jacobian count mismatch")
        records[name], stats[name] = arrays, info
    analysis = checks.analyze_case(case, records, stats, plan)
    saved = json.loads((Path(root) / f"cases/{case.id}/analysis.json").read_text())
    require(analysis == saved, "Saved case verdict does not replay")
    require(analysis["references_pass"], "A reference or analytic comparison failed")
    return analysis, records, stats


def restart_check(case, original, resumed, stats, midpoint):
    require(
        type(midpoint) is int and 0 < midpoint < len(original["native_times_s"]) - 1,
        "Invalid restart checkpoint index",
    )
    start = float(original["native_times_s"][midpoint])
    checks.validate_record(case, resumed, stats, start=start)
    require(stats["status"] == "complete", "Restart did not finish")
    comparisons = {}
    for key, value in original.items():
        at = (
            np.searchsorted(original["sample_times_s"], start)
            if key.startswith("sample_")
            else midpoint
        )
        expected = value[at:]
        comparisons[key] = (
            expected.shape == resumed[key].shape
            and expected.dtype == resumed[key].dtype
            and expected.tobytes() == resumed[key].tobytes()
        )
    require(all(comparisons.values()), "Complete restart suffix is not bitwise equal")
    return {
        "pass": True,
        "midpoint_index": midpoint,
        "time_s": start,
        "fields": list(case.layout.shapes),
        "suffix_arrays": comparisons,
        "accepted_steps": stats["accepted_steps"],
    }


def audit(path):
    root = Path(path)
    receipt = json.loads((root / "verification.json").read_text())
    require(receipt["schema"] == "cells.num010.verification@1", "Wrong receipt schema")
    require(receipt["status"] == "qualified", "Session is not qualified")
    evidence.authenticate(root, receipt)
    plan, cases = data.load_panel()
    require(json.loads((root / "panel.json").read_text()) == plan, "Saved panel changed")
    registration = json.loads((root / "registration.json").read_text())
    require(registration["schema"] == "cells.num010.registration@1", "Wrong registration schema")
    for key in (
        "runtime",
        "resources",
        "source_sha256",
        "panel_sha256",
        "protocol_sha256",
        "inherited_sha256",
        "coordinate_contract",
        "scope",
        "case_ids",
        "attempts",
    ):
        require(registration[key] == receipt[key], f"Registration binding changed: {key}")
    require(
        receipt["panel_sha256"] == data.PANEL_SHA256
        and receipt["protocol_sha256"]
        == data.file_sha(ROOT / "docs/SPATIAL_EXTRACELLULAR_NUMERICS.md")
        and receipt["inherited_sha256"] == data.INHERITED_SHA256
        and receipt["coordinate_contract"] == plan["coordinate_contract"]
        and receipt["scope"] == plan["scope"]
        and receipt["resources"] == plan["resources"]
        and receipt["case_ids"] == [c.id for c in cases]
        and receipt["attempts"] == evidence.attempts(plan),
        "Frozen qualification binding changed",
    )
    evidence.validate_runtime(receipt["runtime"])
    require(
        0 <= receipt["seconds"] <= plan["resources"]["session_wall_seconds"],
        "Session wall cap exceeded",
    )
    require(
        receipt["production_version"] == "0.14.0"
        and receipt["production_changed"] is False
        and receipt["gpu_tested"] is False
        and receipt["biology_validated"] is False,
        "Reference-only scope changed",
    )
    analyses, records, stats = {}, {}, {}
    for case in cases:
        analyses[case.id], records[case.id], stats[case.id] = audit_case(root, case, plan)
    gates = checks.spatial_and_relaxation_checks(analyses, plan)
    selection = checks.select_candidate(analyses, plan)
    require(
        gates == receipt["gates"] and all(g["pass"] for g in gates.values()),
        "Spatial or relaxation gate does not replay",
    )
    require(
        selection == receipt["selection"] and selection["status"] == "qualified",
        "Timestep selection does not replay",
    )
    selected = f"rk4_{selection['selected_dt_s']:g}"
    restarts = {}
    for case in cases:
        resumed, info = evidence.load_record(root, case.id, selected, restart=True)
        require(
            info["method"] == "RK4"
            and info["id"] == selected
            and info["dt_s"] == selection["selected_dt_s"],
            "Restart method changed",
        )
        original = records[case.id][selected]
        midpoint = len(original["native_times_s"]) // 2
        restarts[case.id] = restart_check(case, original, resumed, info, midpoint)
    require(restarts == receipt["restarts"], "Restart verdict does not replay")
    totals = {
        "main_attempts": sum(len(v) for v in stats.values()),
        "complete_attempts": sum(
            s["status"] == "complete" for v in stats.values() for s in v.values()
        ),
        "rejected_attempts": sum(
            s["status"] == "rejected" for v in stats.values() for s in v.values()
        ),
        "main_rhs_calls": sum(s["rhs_calls"] for v in stats.values() for s in v.values()),
        "main_accepted_steps": sum(s["accepted_steps"] for v in stats.values() for s in v.values()),
    }
    require(
        totals == receipt["totals"]
        and totals["main_attempts"] == plan["resources"]["main_attempts"],
        "Session attempt totals changed",
    )
    expected = {"sources.zip", "panel.json", "registration.json"}
    for case in cases:
        expected |= {f"cases/{case.id}/definition.json", f"cases/{case.id}/analysis.json"}
        for setting in evidence.attempts(plan):
            expected.update(evidence.record_names(case.id, setting["id"]))
        expected.update(evidence.record_names(case.id, selected, restart=True))
    require(expected == set(receipt["files_sha256"]), "Unexpected successful evidence topology")
    return {
        "schema": "cells.num010.readonly_audit@1",
        "status": "verified",
        "verification_sha256": evidence.file_sha(root / "verification.json"),
        "payloads": len(expected),
        "captured_sources": len(receipt["source_sha256"]),
        "case_count": len(cases),
        "selected_dt_s": selection["selected_dt_s"],
        "totals": totals,
        "restart_count": len(restarts),
        "gates": gates,
        "ode_calls": 0,
        "production_imported": False,
        "gpu_tested": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(args.directory), indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
