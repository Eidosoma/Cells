"""Synthetic adversarial evidence for the single-channel policy exception.

No physical integration runs; original comparator/lineage tests are retained.
"""

import json
from copy import deepcopy
from pathlib import Path

import numpy as np
import pytest

from validation.tissue import open_calcium_bath_identity_compare as revised
from validation.tissue import open_calcium_bath_trajectory_common as artifact
from validation.tissue import open_calcium_bath_trajectory_compare as original
from validation.tissue import test_open_calcium_bath_trajectory_compare as previous_tests

phase = previous_tests.phase


def write_log(path, rows):
    path.write_text("".join(json.dumps(artifact.json_values(row)) + "\n" for row in rows))


@pytest.fixture
def evidence(phase):
    protocol = phase["protocol"]
    protocol["tolerances"].update(
        rate_energy_atol_pJ_s=1e-4,
        material_atol_fmol=3e-14,
        pool_material_atol_fmol=2e-12,
        charge_atol_C=3e-25,
        energy_atol_pJ=1e-10,
    )
    plan, sources, bundle = phase["plan"], phase["sources"], phase["bundle"]
    proof = dict.fromkeys(revised.INVARIANTS, 0.0)
    for name, source in sources.items():
        job = plan["jobs"][name]
        job["observer_fields"].append("energy_balance_pJ_s")
        raw = artifact.read_json(bundle / job.get("definition", "dt1.json"))
        source["record"].update(artifact.identity(bundle, protocol, job, raw, name))
        source["record"]["observer_fields"] = job["observer_fields"]
        folder = Path(source["data"])
        if job["role"] == "projection":
            source["record"]["independent_physical_observer_max_errors"] = dict(marker=0.0)
            logs = []
            for variant in ("standard", "tight"):
                rows = artifact.read_chunks(folder / variant)
                rows[revised.IDENTITY] = np.zeros((len(rows["times"]), 1))
                previous_tests.chunks(folder / variant, rows)
                logs.extend(
                    dict(
                        variant=variant,
                        sample_index=i,
                        physical_time_s=t,
                        independent_observer_errors=dict(marker=0.0),
                        independent_invariants=proof,
                    )
                    for i, t in enumerate(rows["times"])
                )
            write_log(folder / "progress.jsonl", logs)
            continue
        rows = artifact.read_chunks(folder)
        times = rows["times"]
        source["record"]["max_rate_energy_error_pJ_s"] = 1e-7
        if job["role"] == "oracle":
            artifact.write_json(folder / "invariants.json", [proof] * len(times))
            continue
        rows[revised.IDENTITY] = np.zeros((len(times), 1))
        rows[revised.IDENTITY][-1, 0] = {1: 4e-8, 2: 2e-8, 4: 0.0}[job["dt_divisor"]]
        previous_tests.chunks(folder, rows)
        logs = []
        for i, t in enumerate(times):
            logs.append(
                dict(
                    stage="accepted_state",
                    sample_index=i,
                    physical_time_s=t,
                    total_rk_stages=4 * i,
                    independent_invariants=proof,
                    max_rate_energy_error_pJ_s=1e-7,
                )
            )
            if i + 1 == len(times):
                continue
            step = times[i + 1] - t
            logs.extend(
                dict(
                    step=i,
                    rk_stage=k + 1,
                    step_left_s=t,
                    step_right_s=times[i + 1],
                    step_s=step,
                    held_control_time_s=t,
                    physical_time_s=t + fraction * step,
                    rate_energy_error_pJ_s=1e-8,
                )
                for k, fraction in enumerate((0.0, 0.5, 0.5, 1.0))
            )
        write_log(folder / "progress.jsonl", logs)
    return phase


def assess(evidence):
    record, loaded, _ = original.phase_comparison(**evidence)
    physical = revised.physical_evidence(
        evidence["dataset"], evidence["protocol"], evidence["plan"], evidence["sources"], loaded
    )
    return record, revised.decision(record, evidence["protocol"]), physical


def late(evidence, name, channel, value, variant=None):
    path = Path(evidence["sources"][name]["data"])
    if variant:
        path /= variant
    previous_tests.rewrite_chunk(path, 1, lambda row: row[channel].__setitem__((-1, 0), value))


def test_only_identity_order_is_exempt_and_raw_failure_is_retained(evidence):
    v1, v2, proof = assess(evidence)
    assert len(v1["violations"]) == 1 and not v1["refinement"][revised.IDENTITY]["passed"]
    before = deepcopy(v1)
    assert v2["passed"] and not v2["original_v1_passed"]
    assert v2["temporal_order_exempt_channels"] == [revised.IDENTITY]
    assert revised.decision(v1, evidence["protocol"]) == v2 and before == v1
    assert v2["identity_refinement_diagnostic"] == v1["refinement"][revised.IDENTITY]
    assert proof["production4"]["accepted_proofs"] == 9
    assert proof["production4"]["rk_stage_proofs"] == 32
    saved = artifact.read_json(evidence["output"] / "synthetic-comparison.json")
    assert saved == v1 and saved["violations"]


@pytest.mark.parametrize(
    "defect",
    [
        "empty_accuracy",
        "empty_uncertainty",
        "missing_identity",
        "missing_divisor",
        "nan_accuracy",
        "negative_uncertainty",
        "hidden_violation",
        "changed_refinement",
    ],
)
def test_decision_itself_refuses_incomplete_or_invalid_metrics(evidence, defect):
    v1, _, _ = original.phase_comparison(**evidence)
    if defect == "empty_accuracy":
        v1["accuracy"] = {}
    elif defect == "empty_uncertainty":
        v1["oracle_uncertainty_fraction"] = {}
    elif defect == "missing_identity":
        v1["accuracy"]["4"].pop(revised.IDENTITY)
    elif defect == "missing_divisor":
        v1["accuracy"].pop("4")
    elif defect == "nan_accuracy":
        v1["accuracy"]["4"][revised.IDENTITY] = float("nan")
    elif defect == "negative_uncertainty":
        v1["oracle_uncertainty_fraction"][revised.IDENTITY] = -1.0
    elif defect == "hidden_violation":
        v1["violations"] = []
    else:
        v1["refinement"][revised.IDENTITY]["passed"] = True
    with pytest.raises(ValueError):
        revised.decision(v1, evidence["protocol"])


@pytest.mark.parametrize("same_bias", [False, True])
def test_late_identity_accuracy_failure_is_never_exempt(evidence, same_bias):
    for name in ("production1", "production2", "production4") if same_bias else ("production4",):
        late(evidence, name, revised.IDENTITY, 2e-6)
    _, v2, _ = assess(evidence)
    assert not v2["passed"] and not v2["gates"]["all_channel_accuracy"]


def test_identity_reference_tightening_still_has_its_own_budget(evidence):
    late(evidence, "projection", revised.IDENTITY, 2e-7, "standard")
    _, v2, _ = assess(evidence)
    assert v2["gates"]["all_channel_accuracy"]
    assert not v2["passed"] and not v2["gates"]["reference_uncertainty"]


def test_other_accurate_but_nonconverging_observer_still_fails(evidence):
    for name, offset in (("production1", 4e-8), ("production2", 2e-8)):
        late(evidence, name, "observer__marker", 1.0 + offset)
    _, v2, _ = assess(evidence)
    assert v2["gates"]["all_channel_accuracy"]
    assert not v2["passed"] and not v2["gates"]["other_channel_temporal_refinement"]


def test_shared_reference_and_production_bias_cannot_hide_absolute_failure(evidence):
    for name in ("production1", "production2", "production4"):
        late(evidence, name, revised.IDENTITY, 2e-4)
    for variant in ("standard", "tight"):
        late(evidence, "projection", revised.IDENTITY, 2e-4, variant)
    v1, _, _ = original.phase_comparison(**evidence)
    assert v1["violations"] == []  # Every relative comparison agrees.
    with pytest.raises(ValueError, match="absolute identity"):
        assess(evidence)


@pytest.mark.parametrize("source", ["production4", "oracle-tight", "projection"])
@pytest.mark.parametrize(
    "key,value",
    [
        ("energy_residual_pJ", 2e-10),
        ("program_energy_pJ", 2e-10),
        ("local_material_fmol", 4e-14),
        ("capacitor_charge_C", 4e-25),
        ("pool_material_fmol", 3e-12),
    ],
)
def test_independent_physical_failures_are_not_exempt(evidence, source, key, value):
    folder = Path(evidence["sources"][source]["data"])
    if source.startswith("oracle"):
        proofs = artifact.read_json(folder / "invariants.json")
        proofs[-1][key] = value
        artifact.write_json(folder / "invariants.json", proofs)
    else:
        path = folder / "progress.jsonl"
        rows = list(revised.log_rows(path))
        rows[-1]["independent_invariants"][key] = value
        write_log(path, rows)
    with pytest.raises(ValueError, match="invariant|work identity"):
        assess(evidence)


@pytest.mark.parametrize("source", ["production4", "oracle-tight"])
def test_independent_rate_limit_retained(evidence, source):
    evidence["sources"][source]["record"]["max_rate_energy_error_pJ_s"] = 2e-4
    with pytest.raises(ValueError, match="physical check"):
        assess(evidence)


@pytest.mark.parametrize(
    "defect", ["missing_proof", "missing_stage", "shifted_stage", "bad_metric"]
)
def test_partial_or_invalid_physical_logs_refused(evidence, defect):
    name = "projection" if defect == "bad_metric" else "production4"
    path = Path(evidence["sources"][name]["data"]) / "progress.jsonl"
    rows = list(revised.log_rows(path))
    if defect == "missing_proof":
        rows.pop()
    elif defect == "missing_stage":
        rows.pop(1)
    elif defect == "shifted_stage":
        rows[1]["held_control_time_s"] = 1e-9
    else:
        rows[-1]["independent_observer_errors"]["marker"] = 2.0
    write_log(path, rows)
    with pytest.raises(ValueError):
        assess(evidence)


@pytest.mark.parametrize("defect", ["missing", "extra", "nonfinite", "source", "clock"])
def test_original_complete_evidence_admission_retained(evidence, defect):
    source = evidence["sources"]["production4"]
    if defect == "source":
        source["record"]["definition_sha256"] = "changed"
    else:

        def change(rows):
            if defect == "missing":
                rows.pop(revised.IDENTITY)
            elif defect == "extra":
                rows["observer__extra"] = rows[revised.IDENTITY]
            elif defect == "nonfinite":
                rows[revised.IDENTITY][-1, 0] = np.nan
            else:
                rows["times"][-1] += 1e-9

        previous_tests.rewrite_chunk(Path(source["data"]), 1, change)
    with pytest.raises(ValueError):
        assess(evidence)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1.0, True, [], "0"])
def test_invalid_saved_physical_maximum_rejected(value):
    with pytest.raises(ValueError):
        revised.bounded(value, 1.0, "synthetic")


def test_pins_refuse_self_consistent_rewritten_source(tmp_path):
    path = tmp_path / "result.json"
    artifact.write_json(path, dict(status="passed", invented=False))
    checksum = artifact.sha(path)
    artifact.write_json(path, dict(status="passed", invented=True))
    with pytest.raises(ValueError, match="Pinned original"):
        revised.pinned_json(path, checksum)


def test_policy_has_no_extra_exemption_or_fitted_tolerance(tmp_path):
    path = Path(revised.__file__).with_name("open_calcium_bath_identity_policy.json")
    policy = artifact.read_json(path)
    assert policy["temporal_order_exempt_channels"] == [revised.IDENTITY]
    assert policy["new_numerical_tolerances"] == {}
    altered = deepcopy(policy)
    altered["temporal_order_exempt_channels"].append("observer__marker")
    artifact.write_json(tmp_path / "policy.json", altered)
    with pytest.raises(ValueError, match="policy"):
        revised.load_policy(tmp_path / "policy.json", {})


@pytest.mark.parametrize("defect", [None, "campaign", "comparison", "violations"])
def test_original_failure_artifacts_are_explicitly_pinned(tmp_path, defect):
    campaign = tmp_path / "failure.json"
    folder = tmp_path / "ordinary" / "data"
    folder.mkdir(parents=True)
    failed = folder.parent / "failure.json"
    comparison = folder / "comparison.json"
    artifact.write_json(campaign, dict(status="failed", source="campaign"))
    artifact.write_json(failed, dict(status="failed", source="ordinary"))
    artifact.write_json(comparison, dict(violations=["original refinement failure"]))
    pin = dict(
        comparison_path=str(comparison),
        comparison_sha256=artifact.sha(comparison),
        violations=["original refinement failure"],
        failure_sha256=artifact.sha(failed),
    )
    summary = dict(
        original_campaign_failure_sha256=artifact.sha(campaign),
        original_campaign_status="failed",
        comparisons=dict(ordinary=pin),
    )
    if defect in ("campaign", "comparison"):
        artifact.write_json(campaign if defect == "campaign" else failed, dict(status="passed"))
    elif defect == "violations":
        pin["violations"] = []
    if defect:
        with pytest.raises(ValueError, match="changed"):
            revised.original_comparisons(summary, campaign)
    else:
        old, failures = revised.original_comparisons(summary, campaign)
        assert old["ordinary"]["violations"] and set(failures) == {"campaign", "ordinary"}
