"""Two-sided coupling transfer using the qualified windowed CPU/L4 harness."""

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.batch_windows import plan_batch_windows
from cells.core.specs import parse_spec
from tests.unit import test_source_order_long as shared
from tests.unit import test_source_order_selected as selected
from tests.unit import test_source_order_spanning as history
from validation.assays import source_order_coupling_transfer as assay
from validation.assays import template_readout, two_task

ROOT_RULE = assay.protocol()
RULE, ROWS, PREFIX = ROOT_RULE, [], "source-order-coupling"
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
evidence = reference.common.evidence


def inherited_evidence(name, record, arrays=None):
    if name == f"{PREFIX}-cpu-gpu":
        assert record["worlds"] == 420
        record = record | dict(worlds=RULE["work"]["worlds_per_backend"])
    if name == f"{PREFIX}-readouts":
        record = record | dict(
            fresh_evaluation_strengths=False,
            role="within_condition_recalibration_diagnostic",
            primary_transfer_report=f"{PREFIX}-frozen-transfer.json",
        )
        record["recalibrated_joint_target_met"] = record.pop("primary_joint_target_met")
    if name == f"{PREFIX}-baseline-transfer":
        record = record | dict(role="within_condition_timestep_reference_diagnostic")
    evidence(name, record | dict(coupling_condition=RULE["condition"]), arrays)


def compare_historical_window(value, row, level):
    if row["arm"] == "disconnected":
        return history.compare_historical_window(value, row, level)
    if value.start_step != 0:
        return None
    old = assay.source_row(row)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    saved = assay.archived_segment(root, level, old["world_id"], 0, 0, [])
    actual = reference.arrays(value)
    count = 0
    assert actual.keys() == saved.keys()
    for name, expected in saved.items():
        if not name.startswith("observed__"):
            np.testing.assert_array_equal(actual[name][:1], expected)
            count += expected.size
    return dict(
        level=level,
        world_id=row["world_id"],
        source_world_id=old["world_id"],
        start_step=0,
        stop_step=0,
        compared_scalars=count,
        bitwise=True,
        initial_states_only=True,
    )


@pytest.fixture(scope="module", params=["lower", "higher"], autouse=True)
def configured_harness(request):
    rule = assay.condition_rule(ROOT_RULE, request.param)
    rows, prefix = assay.cases(rule), f"source-order-coupling-{request.param}"
    with pytest.MonkeyPatch.context() as patch:
        for module in (sys.modules[__name__], shared, selected, history):
            for key, value in dict(RULE=rule, ROWS=rows, PREFIX=prefix).items():
                patch.setattr(module, key, value)
        for module in (shared, selected, history):
            patch.setattr(module, "assay", assay)
            patch.setattr(module, "BASE", BASE)
            patch.setattr(module, "evidence", inherited_evidence)
        patch.setattr(selected, "SOURCE", assay.SOURCE)
        patch.setattr(history, "SOURCE", assay.SOURCE)
        patch.setattr(shared, "compare_historical_window", compare_historical_window)
        yield rule


@pytest.fixture(scope="module")
def authenticated_source():
    return assay.baseline(ROOT_RULE)


@pytest.fixture(scope="module")
def prior(configured_harness, authenticated_source):
    return authenticated_source | dict(condition=configured_harness["condition"])


@pytest.fixture(scope="module")
def panel(configured_harness, prior, tmp_path_factory):
    return shared.panel.__wrapped__(prior, tmp_path_factory)


@pytest.fixture(scope="module")
def readouts(panel):
    return shared.readouts.__wrapped__(panel)


@pytest.fixture(scope="module")
def transfers(panel, readouts):
    return shared.transfers.__wrapped__(panel, readouts)


@pytest.fixture(scope="module")
def source_data(configured_harness):
    return assay.load_source(configured_harness, ROWS)


@pytest.fixture(scope="module")
def coupling(panel, source_data):
    return assay.coupling_reports(ROWS, panel["maps"], RULE, source_data)


test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = shared.test_host_source_order_long_archive_boundaries
test_host_reference_answers = shared.test_host_source_order_long_reference_known_answers
test_host_support = selected.test_host_support
test_host_paired_known_answers = selected.test_host_paired_known_answers
test_prerequisite = shared.test_source_order_long_prerequisite
test_replay = shared.test_source_order_long_replay
test_panel = history.test_panel
test_readouts = selected.test_readouts
test_controls = history.test_controls
test_contrasts = selected.test_contrasts
test_baseline_transfer = shared.test_source_order_long_baseline_transfer


def test_host_binding():
    report = assay.validate_design(ROOT_RULE)
    for section, key, value in (
        ("reader", "voltage_margin_V", 1e-9),
        ("cue_timing", "late_pulse_us", [104, 112]),
        ("readout", "cell_ids", [1, 2, 3, 4, 5]),
        ("frozen_reader_source", "backend", "gpu"),
        ("work", "worlds_per_backend", 660),
    ):
        changed = copy.deepcopy(ROOT_RULE)
        changed[section][key] = value
        with pytest.raises(AssertionError):
            assay.validate_design(changed)
    changed = copy.deepcopy(ROOT_RULE)
    changed["coupling_conditions"][0]["permeability_scale"] = 0.95
    with pytest.raises(AssertionError):
        assay.validate_design(changed)
    with pytest.raises(ValueError):
        assay.condition_rule(changed, "lower")
    with pytest.raises(ValueError):
        assay.condition_rule(ROOT_RULE, "unregistered")
    evidence("source-order-coupling-binding", report)


def test_host_design_and_resources():
    original = copy.deepcopy(BASE)
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 220
    assert Counter(r["arm"] for r in ROWS) == dict.fromkeys(two_task.protocol()["arms"], 44)
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in assay.SOURCE_ROWS)
    other = "higher" if RULE["condition"]["id"] == "lower" else "lower"
    assert {r["world_id"] for r in ROWS}.isdisjoint(
        r["world_id"] for r in assay.cases(assay.condition_rule(ROOT_RULE, other))
    )
    assert RULE["preparations"] == assay.SOURCE["preparations"]
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    plans, mapping, archive_estimate = [], [], 0
    scale = RULE["condition"]["permeability_scale"]
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            old = assay.source_row(row)
            record = json.loads(
                (root / (assay.world_name(level, old["world_id"]) + ".json")).read_text()
            )
            assert record["status"] == "passed" and record["case"] == old
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            unscaled = copy.deepcopy(raw)
            unscaled["model"]["tissue"]["junction_permeability"] = record["input"]["model"][
                "tissue"
            ]["junction_permeability"]
            # Exact comparison also checks initial conditions, every event and dose,
            # geometry, gate law, integration clock and observation schedule.
            assert unscaled == record["input"]
            p = np.asarray(raw["model"]["tissue"]["junction_permeability"])
            before = np.asarray(unscaled["model"]["tissue"]["junction_permeability"])
            np.testing.assert_array_equal(p, before * scale)
            np.testing.assert_array_equal(p == 0, before == 0)
            partner = np.asarray(raw["model"]["tissue"]["partner"])
            np.testing.assert_allclose(p, p[:, partner], rtol=5e-14, atol=0)
            spec = parse_spec(raw)
            mapping.append(
                dict(level=level, world_id=row["world_id"], source_world_id=old["world_id"])
            )
        flat, layout = reference.model.initial_values(spec)
        per_state = sum(np.asarray(v).nbytes for v in flat)
        parameters = reference.model.parameters(spec, layout)
        fields = reference.kernel.passive.field(
            reference.model.unflatten(flat).active.tissue, parameters.active.tissue, xp=np
        )
        field_bytes = sum(np.asarray(v).nbytes for v in fields)
        archive_estimate += (
            2 * len(ROWS) * (per_state * (steps + steps // RULE["window_steps"]) + field_bytes * 12)
        )
        for start in range(0, len(ROWS), 4):
            batch = assay.batch(BASE, ROWS[start : start + 4], level, BACKEND, RULE)
            bounded = plan_batch_windows(batch, shared.POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in batch.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    assert BASE == original
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * 6 * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert 2 * archive_estimate + 8 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 165
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    for invalid in (-1, 3, True):
        with pytest.raises(ValueError, match="Unregistered timestep"):
            assay.definition(BASE, ROWS[0], invalid, BACKEND, RULE)
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            condition=RULE["condition"],
            cases=ROWS,
            plans=plans,
            paired_source_mapping=mapping,
            work=RULE["work"],
            retained_array_estimate_bytes=retained,
            uncompressed_archive_estimate_both_conditions_bytes=2 * archive_estimate,
            only_reciprocal_junction_permeability_changed=True,
            all_other_inputs_exact=True,
            same_strength_cohort=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_frozen_reader_known_answers(source_data):
    old_maps, old_reports = source_data
    for key, features in old_maps.items():
        replay = template_readout.evaluate(
            ROWS, features, margin=RULE["reader"]["voltage_margin_V"]
        )
        assert replay == old_reports[key]
    source = {}
    for row in ROWS:
        response = np.array(
            [10e-6 * row["location"], 20e-6 * row["timing"], row["amplitude"] * 1e-6]
        )
        if row["arm"] in ("no_cue", "disconnected"):
            response[:] = 0
        elif row["arm"] == "location_only":
            response[1] = 0
        elif row["arm"] == "timing_only":
            response[0] = 0
        source[row["world_id"]] = np.pad(response, (0, 12))
    target = {i: v + np.pad([0, 50e-6], (0, 13)) for i, v in source.items()}
    result = assay.transfer_panel(ROWS, source, target, RULE)
    assert not result["raw"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    assert result["no_cue_referenced"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    perturbed = {i: v.copy() for i, v in target.items()}
    for row in ROWS:
        if row["split"] == "calibration" and row["arm"] != "no_cue":
            perturbed[row["world_id"]] += 1000
    after = assay.transfer_panel(ROWS, source, perturbed, RULE)
    assert after["raw"] == result["raw"]
    assert after["no_cue_referenced"] == result["no_cue_referenced"]
    relabelled = [
        r | {"location": 1 - r["location"], "timing": 1 - r["timing"]}
        if r["split"] == "heldout" and r["arm"] == "joint"
        else r
        for r in ROWS
    ]
    labels_changed = assay.transfer_panel(relabelled, source, target, RULE)
    for mode in ("raw", "no_cue_referenced"):
        for task in ("location", "timing"):
            a = result[mode]["arms"]["joint"]["tasks"][task]["predictions"]
            b = labels_changed[mode]["arms"]["joint"]["tasks"][task]["predictions"]
            assert [{k: v for k, v in r.items() if k != "target"} for r in a] == [
                {k: v for k, v in r.items() if k != "target"} for r in b
            ]
    for row in ROWS:
        if row["split"] == "heldout" and row["arm"] == "joint":
            perturbed[row["world_id"]][1] += 30e-6
    altered = assay.transfer_panel(ROWS, source, perturbed, RULE)
    assert not altered["no_cue_referenced"]["arms"]["joint"]["joint"][
        "all_cases_correct_and_resolved"
    ]
    evidence(
        f"{PREFIX}-frozen-reader-known-answers",
        dict(
            status="passed",
            archived_reader_and_report_replays=90,
            shared_offset_removed_only_by_labelled_reference_diagnostic=True,
            altered_cue_response_not_hidden_by_shared_reference=True,
            target_stimulated_calibration_cannot_change_transfer=True,
            heldout_labels_cannot_change_predictions_scores_or_resolution=True,
            all_primary_reader_coefficients_bitwise_equal_to_source=True,
        ),
    )


def test_host_history_boundaries(tmp_path, monkeypatch):
    root = tmp_path / "evidence" / BACKEND
    root.mkdir(parents=True)
    row = next(r for r in ROWS if r["arm"] == "joint")
    old = assay.source_row(row)
    name = assay.world_name(0, old["world_id"])
    data = dict(
        state__voltage=np.arange(3)[:, None] * 1e-9,
        junction__open=np.ones((3, 1)),
        observed__voltage=np.empty((0, 1)),
    )
    np.savez_compressed(root / (name + ".npz"), **data)
    (root / (name + ".json")).write_text(
        json.dumps(
            dict(
                status="passed",
                windows=[dict(file=name + ".npz", start_step=0, stop_step=2, observation_times=[])],
            )
        )
    )
    rule = RULE | dict(prior_binding=dict(root=str(tmp_path)))
    monkeypatch.setitem(globals(), "RULE", rule)
    actual = {k: v.copy() for k, v in data.items()}
    actual["state__voltage"][1:] += 999
    monkeypatch.setattr(reference, "arrays", lambda _: actual)
    value = SimpleNamespace(start_step=0)
    assert compare_historical_window(value, row, 0)["stop_step"] == 0
    actual["state__voltage"][0] += 1
    with pytest.raises(AssertionError):
        compare_historical_window(value, row, 0)
    value.start_step = 1
    assert compare_historical_window(value, row, 0) is None
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            connected_initial_state_only=True,
            changed_connected_evolution_not_treated_as_historical_reproduction=True,
            corrupted_initial_state_rejected=True,
        ),
    )


def test_historical_reproduction(panel):
    histories = panel["prefixes"]
    assert len(histories) == 1144
    assert len({(r["level"], r["world_id"]) for r in histories}) == 660
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            old, duration = assay.historical_source(row)
            assert all(r["source_world_id"] == old["world_id"] for r in windows)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(duration / dt)
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            history_comparisons=histories,
            full_512us_disconnected_worlds=132,
            other_initial_state_only_worlds=528,
            changed_connected_histories_not_required_to_match=True,
        ),
    )


def test_frozen_transfer(coupling):
    assert coupling["primary"]["joint"]["cases"] == 32
    evidence(f"{PREFIX}-frozen-transfer", coupling)


def test_cpu_gpu(panel, readouts, transfers, coupling):
    # Inherited complete history/field, readout, contrast and reference checks.
    # CPU skips here only; both CPU scientific reports have already been saved.
    shared.test_source_order_long_cpu_gpu(panel, readouts, transfers)
    cpu = Path(EVIDENCE) / "cpu"
    old = json.loads((cpu / f"{PREFIX}-frozen-transfer.json").read_text())
    comparisons = []
    for name, group in coupling["panels"].items():
        for actual, expected in zip(group["levels"], old["panels"][name]["levels"], strict=True):
            assert actual["level"] == expected["level"]
            for mode in ("raw", "no_cue_referenced"):
                differences = assay.compare_reader_predictions(
                    {mode: actual[mode]}, {mode: expected[mode]}
                )
                for arm in actual[mode]["arms"]:
                    assert (
                        actual[mode]["arms"][arm]["calibration"]
                        == expected[mode]["arms"][arm]["calibration"]
                    )
                assert all(r["max_score_difference"] <= 1e-12 for r in differences)
                comparisons.append(
                    dict(panel=name, level=actual["level"], mode=mode, predictions=differences)
                )
    path = Path(EVIDENCE) / "gpu" / f"{PREFIX}-cpu-gpu.json"
    report = json.loads(path.read_text())
    report["frozen_coupling_transfer_comparisons"] = comparisons
    report["frozen_coupling_decisions_agree"] = not any(
        r["differing_decision_world_ids"] for group in comparisons for r in group["predictions"]
    )
    evidence(f"{PREFIX}-cpu-gpu", report)
