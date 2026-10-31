"""Reporting contracts: never promote source/raw evidence into physical success."""

import copy
import hashlib
import json

import pytest

from validation.geometry import stable_initial_mesh_summary as summary


def panel():
    checks = [
        dict(
            unit="check-" + str(i),
            pytest_id=dict(classname="mesh", name="case-" + str(i)),
            case=case,
            role=role,
            passed=role != "mesh",
        )
        for i, (case, role) in enumerate(
            (("shape", "mesh"), ("empty", "raw"), ("guard", "request"))
        )
    ]
    replays = [
        dict(
            unit="replay-" + str(i * 2 + j),
            case=row["case"],
            lane=lane,
            passed=lane == "conditional-source" or row["role"] == "raw",
            failure=None,
        )
        for i, row in enumerate(checks[:2])
        for j, lane in enumerate(("conditional-source", "geometry"))
    ]
    plan = dict(
        check_units=[{k: v for k, v in r.items() if k != "passed"} for r in checks],
        expected_pytest_ids=[r["pytest_id"] for r in checks],
        mesh_cases=["shape"],
        raw_cases=["empty"],
        replay_units=[
            dict(
                unit=r["unit"],
                case=r["case"],
                lane=r["lane"],
                source_check="check-0" if r["case"] == "shape" else "check-1",
            )
            for r in replays
        ],
    )
    result = dict(
        status="candidate_checks_failed",
        all_declared_units_audited=True,
        checks=checks,
        replay_cases=replays,
        metadata_errors=[],
        passed_checks=2,
        passed_conditional_source_records=2,
        passed_independent_geometry_records=1,
        **{key: False for key in summary.SCOPE_FLAGS},
    )
    finalization = dict(
        status="completed",
        failure=None,
        result=result,
        production_imports_denied=True,
        **{key: False for key in summary.SCOPE_FLAGS},
    )
    return finalization, plan


def test_conditional_source_and_raw_passes_do_not_promote_failed_geometry():
    record, plan = panel()
    before = copy.deepcopy((record, plan))
    value = summary.summarize(record, plan)
    assert value["scientific_status"] == "candidate_checks_failed"
    assert value["counts"]["geometry"]["mesh"] == dict(total=1, passed=0, failed=1)
    assert value["counts"]["geometry"]["raw"] == dict(total=1, passed=1, failed=0)
    assert value["counts"]["conditional-source"]["mesh"]["passed"] == 1
    assert not value["job_reclassified"] and not value["numerical_results_recomputed"]
    assert before == (record, plan)


@pytest.mark.parametrize(
    "damage",
    (
        "promote",
        "count",
        "duplicate",
        "missing",
        "role",
        "source",
        "lane",
        "boolean",
        "scope",
        "partial",
    ),
)
def test_inconsistent_or_incomplete_verdicts_are_refused(damage):
    record, plan = panel()
    result = record["result"]
    if damage == "promote":
        result["status"] = "passed"
    elif damage == "count":
        result["passed_independent_geometry_records"] = 2
    elif damage == "duplicate":
        result["checks"].append(copy.deepcopy(result["checks"][0]))
    elif damage == "missing":
        result["replay_cases"].pop()
    elif damage == "role":
        result["checks"][0]["role"] = "raw"
    elif damage == "source":
        plan["replay_units"][0]["source_check"] = "check-1"
    elif damage == "lane":
        result["replay_cases"][0]["lane"] = "geometry"
    elif damage == "boolean":
        result["checks"][0]["passed"] = 0
    elif damage == "scope":
        result["physical_geometry_admitted"] = True
    else:
        result["all_declared_units_audited"] = False
    with pytest.raises(ValueError):
        summary.summarize(record, plan)


def saved(tmp_path, record, plan):
    artifacts = {}
    for name, value in ((summary.DETAIL, record), (summary.PLAN, plan)):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        data = json.dumps(value).encode()
        path.write_bytes(data)
        artifacts[name] = hashlib.sha256(data).hexdigest()
    (tmp_path / "result.json").write_text(
        json.dumps(
            dict(
                kind="cells.stable_initial_mesh_qualification@1",
                status="failed",
                artifacts=artifacts,
            )
        )
    )


def test_large_bound_details_stay_external_and_failed_job_stays_failed(tmp_path):
    record, plan = panel()
    record["retained_metric_tree"] = "x" * (summary.METADATA_LIMIT + 1)
    saved(tmp_path, record, plan)
    original = (tmp_path / "result.json").read_bytes()
    value, encoded = summary.summarize_saved_run(tmp_path)
    assert len(encoded) < summary.SUMMARY_LIMIT
    assert value["evidence"]["full_finalization"]["bytes"] > summary.METADATA_LIMIT
    assert value["original_run_status"] == "failed"
    assert value["scientific_status"] == "candidate_checks_failed"
    assert (tmp_path / "result.json").read_bytes() == original


@pytest.mark.parametrize("damage", ("digest", "oversize", "duplicate-json", "nonfinite"))
def test_saved_record_integrity_and_bounds(tmp_path, damage, monkeypatch):
    record, plan = panel()
    saved(tmp_path, record, plan)
    path = tmp_path / summary.DETAIL
    if damage == "digest":
        path.write_text(path.read_text() + " ")
    elif damage == "oversize":
        monkeypatch.setattr(summary, "DETAIL_LIMIT", path.stat().st_size - 1)
    elif damage == "duplicate-json":
        path.write_text('{"status":"completed","status":"failed"}')
    else:
        path.write_text('{"value":NaN}')
    with pytest.raises(ValueError):
        summary.summarize_saved_run(tmp_path)
