"""Compact an existing mesh verdict without rerunning or reclassifying its job.

Large metric/trace trees stay in their original hash-bound artifact. This reader
checks reported identities and counts; it does not recompute geometric accuracy.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path

KIND = "cells.stable_initial_mesh_saved_summary@1"
DETAIL_LIMIT = 64 * 2**20
METADATA_LIMIT = 16 * 2**20
SUMMARY_LIMIT = 64 * 2**10
PLAN = "bundle/source/agent-work/cells-specialist/stable_initial_mesh_preparation_plan.json"
DETAIL = "evidence/finalize/finalization.json"
SCOPE_FLAGS = (
    "physical_geometry_admitted",
    "exact_native_arithmetic_equivalence",
    "topology_qualified",
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def _boolean(value):
    require(type(value) is bool, "Verdict flags require exact booleans")
    return value


def _indexed(rows, label):
    require(type(rows) is list and len(rows) <= 128, "Bounded " + label + " list required")
    result = {}
    for row in rows:
        require(type(row) is dict and type(row.get("unit")) is str, "Invalid " + label + " row")
        require(row["unit"] not in result, "Duplicate " + label + " unit")
        result[row["unit"]] = row
    return result


def summarize(finalization, plan):
    """Check the complete reported panel and separate numeric and raw records."""
    require(
        finalization["status"] == "completed" and finalization["failure"] is None,
        "Require completed finalization; retain incomplete failures separately",
    )
    result = finalization["result"]
    require(result["all_declared_units_audited"] is True, "Incomplete mesh panel")
    require(finalization["production_imports_denied"] is True, "Missing denied-import evidence")
    for key in SCOPE_FLAGS:
        require(finalization[key] is False and result[key] is False, "Unexpected scope promotion")
    expected = _indexed(plan["check_units"], "planned checks")
    checks = _indexed(result["checks"], "checks")
    replay_plan = _indexed(plan["replay_units"], "planned replays")
    replays = _indexed(result["replay_cases"], "replays")
    require(set(expected) == set(checks), "Check identities differ from declared panel")
    require(set(replay_plan) == set(replays), "Replay identities differ from declared panel")
    require(not (set(checks) & set(replays)), "Check and replay units overlap")
    declared_ids = [(r["classname"], r["name"]) for r in plan["expected_pytest_ids"]]
    actual_ids, compact_checks, sources = [], [], {}
    for unit, row in checks.items():
        for key in ("pytest_id", "role", "case"):
            require(row[key] == expected[unit][key], "Changed check identity/role: " + unit)
        identifier = row["pytest_id"]
        actual_ids.append((identifier["classname"], identifier["name"]))
        if row["role"] in ("mesh", "raw"):
            require(row["case"] not in sources, "Duplicate mesh/raw case")
            sources[row["case"]] = (unit, row["role"])
        compact_checks.append(
            dict(
                unit=unit,
                pytest_id=identifier,
                role=row["role"],
                case=row["case"],
                passed=_boolean(row["passed"]),
            )
        )
    require(
        len(set(actual_ids)) == len(actual_ids) == len(declared_ids)
        and set(actual_ids) == set(declared_ids),
        "Missing or repeated pytest identity",
    )
    require(
        {name for name, (_, role) in sources.items() if role == "mesh"} == set(plan["mesh_cases"]),
        "Changed complete-mesh case set",
    )
    require(
        {name for name, (_, role) in sources.items() if role == "raw"} == set(plan["raw_cases"]),
        "Changed raw-failure case set",
    )
    compact_replays, pairs = [], set()
    for unit, row in replays.items():
        declared = replay_plan[unit]
        require(
            row["case"] == declared["case"] and row["lane"] == declared["lane"],
            "Changed replay case/lane: " + unit,
        )
        require(row["case"] in sources, "Replay lacks its declared source case")
        source_unit, role = sources[row["case"]]
        require(source_unit == declared["source_check"], "Changed replay source owner")
        pair = (row["case"], row["lane"])
        require(
            pair not in pairs and row["lane"] in ("conditional-source", "geometry"),
            "Duplicate or unsupported replay lane",
        )
        pairs.add(pair)
        compact_replays.append(
            dict(
                unit=unit,
                case=row["case"],
                lane=row["lane"],
                role=role,
                passed=_boolean(row["passed"]),
            )
        )
    require(
        pairs == {(case, lane) for case in sources for lane in ("conditional-source", "geometry")},
        "Incomplete case/lane grid",
    )

    def count(rows):
        rows = list(rows)
        passed = sum(row["passed"] for row in rows)
        return dict(total=len(rows), passed=passed, failed=len(rows) - passed)

    counts = dict(checks=count(compact_checks))
    for lane in ("conditional-source", "geometry"):
        counts[lane] = {
            role: count(
                row for row in compact_replays if row["lane"] == lane and row["role"] == role
            )
            for role in ("mesh", "raw")
        }
    reported = dict(
        passed_checks=counts["checks"]["passed"],
        passed_conditional_source_records=sum(
            v["passed"] for v in counts["conditional-source"].values()
        ),
        passed_independent_geometry_records=sum(v["passed"] for v in counts["geometry"].values()),
    )
    for key, value in reported.items():
        require(
            type(result[key]) is int and result[key] == value, "Inconsistent reported count: " + key
        )
    require(type(result["metadata_errors"]) is list, "Missing metadata-error records")
    passing = not result["metadata_errors"] and all(
        row["passed"] for row in compact_checks + compact_replays
    )
    status = "passed" if passing else "candidate_checks_failed"
    require(result["status"] == status, "Reported status disagrees with its complete verdicts")
    return dict(
        kind=KIND,
        scientific_status=status,
        counts=counts,
        checks=compact_checks,
        replay_cases=compact_replays,
        metadata_error_count=len(result["metadata_errors"]),
        full_panel_reported=True,
        source_correspondence_is_conditional=True,
        raw_failure_records_are_numeric_geometry_cases=False,
        numerical_results_recomputed=False,
        job_reclassified=False,
        **{key: False for key in SCOPE_FLAGS},
    )


def _pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "Duplicate JSON key: " + key)
        result[key] = value
    return result


def _read(path, limit):
    require(not path.is_symlink(), "Summary inputs must be original regular artifacts")
    require(path.stat().st_size <= limit, "Artifact exceeds its declared read bound")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    require(len(raw) <= limit, "Artifact grew past its declared read bound")

    def nonfinite(value):
        raise ValueError("Nonfinite JSON value: " + value)

    data = json.loads(raw, object_pairs_hook=_pairs, parse_constant=nonfinite)
    return data, dict(path=str(path), sha256=hashlib.sha256(raw).hexdigest(), bytes=len(raw))


def summarize_saved_run(directory):
    """Bind full details and plan to the untouched original terminal inventory."""
    directory = Path(directory).resolve()
    terminal, terminal_pin = _read(directory / "result.json", METADATA_LIMIT)
    require(
        terminal["kind"] == "cells.stable_initial_mesh_qualification@1", "Wrong qualification kind"
    )
    require(terminal["status"] in ("passed", "failed"), "Require an original terminal run")
    finalization, details_pin = _read(directory / DETAIL, DETAIL_LIMIT)
    plan, plan_pin = _read(directory / PLAN, METADATA_LIMIT)
    for name, pin in ((DETAIL, details_pin), (PLAN, plan_pin)):
        require(
            terminal["artifacts"].get(name) == pin["sha256"],
            "Original artifact digest mismatch: " + name,
        )
    summary = summarize(finalization, plan)
    summary.update(
        original_run_status=terminal["status"],
        evidence=dict(terminal=terminal_pin, full_finalization=details_pin, frozen_plan=plan_pin),
        limits=dict(
            metadata_bytes=METADATA_LIMIT, detail_bytes=DETAIL_LIMIT, summary_bytes=SUMMARY_LIMIT
        ),
    )
    encoded = (json.dumps(summary, indent=2, allow_nan=False) + "\n").encode()
    require(len(encoded) <= SUMMARY_LIMIT, "Compact summary exceeds declared output bound")
    return summary, encoded


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    summary, encoded = summarize_saved_run(args.run)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as stream:
        stream.write(encoded)
        stream.flush()
        os.fsync(stream.fileno())
    print(
        json.dumps(
            dict(
                output=str(args.output),
                bytes=len(encoded),
                original_run_status=summary["original_run_status"],
                scientific_status=summary["scientific_status"],
                counts=summary["counts"],
            )
        )
    )


if __name__ == "__main__":
    main()
