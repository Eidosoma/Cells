"""Fresh confirmation of a frozen calibration-selected schedule."""

import copy
import json
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.batch_windows import plan_batch_windows
from cells.core.grid import checked_grid
from cells.core.runner import control_values
from cells.core.specs import parse_spec
from tests.unit import test_source_order_long as shared
from tests.unit import test_source_order_spanning as previous
from validation.assays import source_order_observation_design as design
from validation.assays import source_order_selected as assay
from validation.assays import template_readout, two_task

RULE, SOURCE, ROWS = assay.protocol(), assay.SOURCE, assay.cases()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
PREFIX = "source-order-selected"
evidence = reference.common.evidence
compare_historical_window = previous.compare_historical_window


@pytest.fixture(scope="module", autouse=True)
def configured_harness():
    """Reuse qualified storage/replay checks; restore both modules afterwards."""
    assert shared.POLICY.window_steps == RULE["window_steps"]
    with pytest.MonkeyPatch.context() as patch:
        bindings = dict(RULE=RULE, ROWS=ROWS, BASE=BASE, PREFIX=PREFIX, assay=assay)
        for module in (shared, previous):
            for name, value in bindings.items():
                patch.setattr(module, name, value)
        patch.setattr(previous, "SOURCE", SOURCE)
        patch.setattr(shared, "compare_historical_window", compare_historical_window)
        patch.setattr(shared, "evidence", previous.inherited_evidence)
        yield


panel = shared.panel
readouts = shared.readouts
transfers = shared.transfers
test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = shared.test_host_source_order_long_archive_boundaries
test_host_reference_answers = shared.test_host_source_order_long_reference_known_answers
test_host_history_boundaries = previous.test_host_history_boundaries
test_prerequisite = shared.test_source_order_long_prerequisite
test_replay = shared.test_source_order_long_replay
test_baseline_transfer = shared.test_source_order_long_baseline_transfer
test_cpu_gpu = shared.test_source_order_long_cpu_gpu
test_panel = previous.test_panel
test_controls = previous.test_controls


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_host_design_and_resources():
    plan = RULE["evaluation_design"]
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 220
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in assay.SOURCE_ROWS)
    assert Counter(r["arm"] for r in ROWS) == dict.fromkeys(two_task.protocol()["arms"], 44)
    new = {r["amplitude"] for r in ROWS if r["split"] == "heldout"}
    assert new == set(plan["strengths"]) and len(new) == 8
    earlier_strengths = set()
    for path in (two_task.ROOT / "validation/assays").rglob("*protocol.json"):
        if path != assay.PROTOCOL_PATH:
            earlier_strengths.update(
                p["amplitude"] for p in json.loads(path.read_text()).get("preparations", [])
            )
    assert new.isdisjoint(earlier_strengths)
    assert RULE["preparations"][:3] == SOURCE["preparations"][:3]
    assert RULE["duration_s"] == SOURCE["duration_s"] == 512e-6
    assert RULE["dt_s"] == SOURCE["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["reader"] == SOURCE["reader"] and RULE["primary_panel"] == "selected320"
    assert not RULE["automatic_followup"]
    for name in RULE["observation_panels"]:
        np.testing.assert_allclose(
            assay.times(RULE, name) * 1e6, RULE["observation_times_us"][name], atol=1e-12, rtol=0
        )
    assert all(assay.times(RULE, "selected320") > 112 * two_task.protocol()["dt_s"])
    original = copy.deepcopy(BASE)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == i - 1 for i in RULE["source_cell_ids"]]
    ref_area = min(area[m].sum() for m in masks)
    plans, doses, mapping, archive_estimate = [], [], [], 0
    history = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            before, duration = assay.historical_source(row)
            record = json.loads(
                (history / (assay.world_name(level, before["world_id"]) + ".json")).read_text()
            )
            assert record["status"] == "passed" and record["case"] == before
            assert raw["model"] == record["input"]["model"] == BASE["model"]
            assert raw["execution"] == record["input"]["execution"]
            assert {k: v for k, v in raw["experiment"].items() if k != "changes"} == {
                k: v for k, v in record["input"]["experiment"].items() if k != "changes"
            }
            if duration == RULE["duration_s"]:
                assert raw == record["input"]
            spec = parse_spec(raw)
            grid = np.asarray(list(checked_grid(spec)))
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            assert len(spec.experiment.observation_times) == 12
            controls = control_values(spec, grid[:-1])
            old_controls = control_values(parse_spec(record["input"]), grid[:-1])
            stop = round(duration / dt)
            for actual, old in zip(controls, old_controls, strict=True):
                np.testing.assert_array_equal(actual[:stop], old[:stop])
            np.testing.assert_array_equal(controls.pump, 1)
            np.testing.assert_array_equal(
                controls.junction, 0 if row["arm"] == "disconnected" else 1
            )
            weights = (
                [0, 0]
                if row["arm"] == "no_cue"
                else [0.5, 0.5]
                if row["arm"] == "timing_only"
                else [0.75, 0.25]
                if row["location"] == 0
                else [0.25, 0.75]
            )
            expected = np.ones_like(controls.channel)
            for i, (weight, mask) in enumerate(zip(weights, masks, strict=True)):
                pulse = RULE["cue_timing"][
                    "location_only_pulse_us"
                    if row["arm"] == "location_only"
                    else "early_pulse_us"
                    if i == row["timing"]
                    else "late_pulse_us"
                ]
                start, end = [round(t * 1e-6 / dt) for t in pulse]
                expected[start:end, mask] = (
                    1 - row["amplitude"] * weight * ref_area / area[mask].sum()
                )
            np.testing.assert_allclose(controls.channel, expected, rtol=0, atol=4e-16)
            assert np.all((controls.channel >= 0) & (controls.channel <= 1))
            amounts = [float(np.sum((1 - controls.channel[:, m]) @ area[m]) * dt) for m in masks]
            np.testing.assert_allclose(
                amounts,
                [row["amplitude"] * w * ref_area * 8e-6 for w in weights],
                rtol=2e-14,
                atol=1e-30,
            )
            doses.append(dict(level=level, world_id=row["world_id"], source_doses_m2_s=amounts))
            mapping.append(
                dict(
                    level=level,
                    world_id=row["world_id"],
                    source_world_id=before["world_id"],
                    duration_s=duration,
                )
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
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            batch = assay.batch(
                BASE, ROWS[start : start + RULE["batch_worlds"]], level, BACKEND, RULE
            )
            bounded = plan_batch_windows(batch, shared.POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in batch.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * len(RULE["observation_panels"]) * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 4 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 165
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    assert Counter(r["duration_s"] for r in mapping) == {512e-6: 276, 8e-6: 384}
    assert BASE == original
    for invalid in (-1, 3, True):
        with pytest.raises(ValueError, match="Unregistered timestep"):
            assay.definition(BASE, ROWS[0], invalid, BACKEND, RULE)
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            cases=ROWS,
            plans=plans,
            integrated_doses=doses,
            historical_identity_mapping=mapping,
            primary_panel=RULE["primary_panel"],
            observation_times_us=RULE["observation_times_us"],
            work=RULE["work"],
            retained_array_estimate_bytes=retained,
            uncompressed_archive_estimate_bytes=archive_estimate,
            new_strengths_disjoint_from_prior_protocols=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_selection_binding(tmp_path, monkeypatch):
    report = assay.selected_design(RULE)
    assert report["selected_times_us"] == [128, 160, 320]
    strengths = RULE["evaluation_design"]["strengths"]
    assert strengths == [
        0.409375,
        0.459375,
        0.509375,
        0.559375,
        0.640625,
        0.690625,
        0.740625,
        0.790625,
    ]
    np.testing.assert_allclose(np.array(strengths) + strengths[::-1], 1.2, rtol=0, atol=3e-16)
    for change in ("time", "margin", "cells", "comparator", "primary"):
        changed = copy.deepcopy(RULE)
        if change == "time":
            changed["observation_times_us"]["selected320"][1] = 192
        elif change == "margin":
            changed["reader"]["voltage_margin_V"] = 1e-9
        elif change == "cells":
            changed["readout"]["cell_ids"][0] = 1
        elif change == "comparator":
            changed["paired_comparator_panels"] = ["long512"]
        else:
            changed["primary_panel"] = "spanning512"
        with pytest.raises(AssertionError):
            assay.selected_design(changed)
    # A corrupt saved selection must fail before its content is trusted.
    fake = tmp_path / "selection"
    fake.mkdir()
    origin = Path(RULE["selection_binding"]["root"])
    for name in ("inputs.json", "result.json", "selection.json", "completion.json"):
        (fake / name).write_bytes((origin / name).read_bytes())
    (fake / "selection.json").write_text('{"status":"invented"}\n')
    changed = copy.deepcopy(RULE)
    changed["selection_binding"]["root"] = str(fake)
    with pytest.raises(AssertionError):
        assay.selected_design(changed)
    evidence(
        f"{PREFIX}-selection-binding",
        report
        | dict(
            changed_schedule_margin_support_and_selection_rejected=True,
            new_strengths_fixed_before_simulation=True,
        ),
    )


def test_host_support():
    ids = np.array([4, 7, 2, 1, 5, 3, 6])
    owner, area = np.repeat(np.arange(7), 2), np.arange(1, 15, dtype=float)
    times = np.array(sorted({t for p in RULE["observation_panels"] for t in assay.times(RULE, p)}))
    assert len(times) == 12
    voltage = np.arange(len(times) * len(owner), dtype=float).reshape(len(times), -1) * 1e-6
    proxy = SimpleNamespace(
        spec=parse_spec(assay.definition(BASE, ROWS[0], 2, BACKEND, RULE)),
        final=SimpleNamespace(
            layout=SimpleNamespace(
                ids=ids,
                tissue_cell_owner=owner,
                tissue_membrane_area=area,
            )
        ),
        observations=SimpleNamespace(times=times, membrane_voltage_V=voltage),
    )
    saved = {}
    for name in RULE["observation_panels"]:
        actual = assay.features(proxy, RULE, name)
        selected = [int(np.flatnonzero(times == t)[0]) for t in assay.times(RULE, name)]
        for mode, cells in (
            ("voltage", RULE["readout"]["cell_ids"]),
            ("all_cell_voltage", RULE["readout"]["all_cell_ids"]),
        ):
            expected = [
                sum(voltage[i, c] * area[c] for c in np.flatnonzero(ids[owner] == cell))
                / area[ids[owner] == cell].sum()
                for i in selected
                for cell in cells
            ]
            np.testing.assert_allclose(actual[mode], expected, atol=1e-19, rtol=0)
        assert actual["voltage"].shape == (15,) and actual["all_cell_voltage"].shape == (21,)
        np.testing.assert_array_equal(actual["final_voltage"], actual["voltage"][-5:])
        saved[name] = actual
    # Independently reproduce the exact ordering used during calibration selection.
    design_plan = json.loads(design.PLAN.read_text())["design"]
    old_rows = assay.SOURCE_ROWS
    arrays = {
        f"{level}__{p}__voltage__{r['world_id']}": saved[p]["voltage"]
        for r in old_rows
        if r["split"] == "calibration"
        for level in range(3)
        for p in ("middle128", "long256", "long512", "spanning512")
    }
    _, observations, _ = design.load_calibration(arrays, old_rows, SOURCE, design_plan)
    indices = [design_plan["available_postcue_times_us"].index(t) for t in (128, 160, 320)]
    for value in observations.values():
        np.testing.assert_array_equal(value[indices].reshape(-1), saved["selected320"]["voltage"])
    voltage[:, np.isin(ids[owner], [1, 4])] += 123
    np.testing.assert_array_equal(
        assay.features(proxy, RULE, "selected320")["voltage"], saved["selected320"]["voltage"]
    )
    voltage[~np.isin(times, assay.times(RULE, "selected320"))] += 456
    np.testing.assert_array_equal(
        assay.features(proxy, RULE, "selected320")["voltage"], saved["selected320"]["voltage"]
    )
    with pytest.raises(TypeError):
        assay.features(proxy, RULE, "selected320", labels=[0, 1])
    evidence(
        f"{PREFIX}-support",
        dict(
            status="passed",
            primary_features=15,
            observations=12,
            unequal_area_weighting=True,
            source_cells_and_unselected_times_excluded=True,
            exact_frozen_design_feature_extractor=True,
            final_voltage_is_320us=True,
        ),
    )


def test_host_paired_known_answers():
    rows = [r for r in ROWS if r["arm"] == "joint"]
    reports = []
    for kind in ("selected", "comparator"):
        values = {}
        for row in rows:
            weak = row["split"] == "heldout" and (
                row["amplitude"] >= 0.7 if kind == "selected" else row["amplitude"] < 0.5
            )
            point = [
                10 * row["location"],
                5 if weak else 10 * row["timing"],
                100 * row["amplitude"],
            ]
            values[row["world_id"]] = np.pad(point, (0, 12))
        reports.append(template_readout.evaluate(rows, values, margin=1))
    before = copy.deepcopy(reports)
    for comparator in RULE["paired_comparator_panels"]:
        result = assay.paired_report(
            *reports, primary_name="selected320", comparator_name=comparator
        )
        assert result["counts"] == dict(primary_only=8, comparator_only=8, both=16, neither=0)
        assert result["primary_minus_comparator_resolved_cases"] == 0
        assert len(result["cases"]) == 32
        assert result["primary_panel"] == "selected320" and result["comparator_panel"] == comparator
        assert reports == before
    reports[1]["arms"]["joint"]["tasks"]["timing"]["predictions"][0]["world_id"] = -1
    with pytest.raises(AssertionError):
        assay.paired_report(*reports, primary_name="selected320", comparator_name="spanning512")
    evidence(
        f"{PREFIX}-paired-known-answers",
        dict(
            status="passed",
            improvements_and_regressions_preserved=True,
            same_case_support_required=True,
            explicit_primary_and_comparator_names=True,
            scores_and_original_reports_unchanged=True,
        ),
    )


def test_historical_reproduction(panel, readouts):
    histories = panel["prefixes"]
    assert len(histories) == 1672
    assert len({(r["level"], r["world_id"]) for r in histories}) == 660
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(assay.historical_source(row)[1] / dt)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    count, old_features = 0, {}
    with np.load(root / "source-order-spanning-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for row in ROWS:
                old, duration = assay.historical_source(row)
                if duration != 512e-6:
                    continue
                if name == "selected320":
                    parts = {
                        p: {m: saved[f"{level}__{p}__{m}__{old['world_id']}"] for m in modes}
                        for p, _ in assay.SELECTED
                    }
                    expected = assay.selected_vectors(parts)
                else:
                    expected = {m: saved[f"{level}__{name}__{m}__{old['world_id']}"] for m in modes}
                for mode, values in modes.items():
                    np.testing.assert_array_equal(values[row["world_id"]], expected[mode])
                    count += expected[mode].size
                if row["split"] == "calibration":
                    old_features[level, name, row["world_id"]] = expected["voltage"]
    old_reports = json.loads((root / "source-order-spanning-readouts.json").read_text())["panels"]
    curve_count = 0
    for name, group in readouts.items():
        for level, report in enumerate(group["resolution_matched"]):
            for arm, value in report["outcomes"]["voltage"]["arms"].items():
                tasks, training, _ = template_readout.split(ROWS, arm)
                expected = template_readout.TemplateReader.fit(
                    np.stack([old_features[level, name, r["world_id"]] for r in training]),
                    np.array([[r[t] for t in tasks] for r in training]),
                    [r["amplitude"] for r in training],
                    minimum_margin=RULE["reader"]["voltage_margin_V"],
                ).to_dict()
                assert value["calibration"]["template_reader"] == expected
                if name != "selected320":
                    old_cal = old_reports[name]["resolution_matched"][level]["outcomes"]["voltage"][
                        "arms"
                    ][arm]["calibration"]["template_reader"]
                    assert expected == old_cal
                curve_count += 1
    assert count == 117576 and curve_count == 90
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            world_prefixes=660,
            full_512us_worlds=276,
            precue_only_worlds=384,
            history_comparisons=histories,
            bitwise_history_comparisons=len(histories),
            exact_feature_scalars=count,
            unchanged_calibration_readers=curve_count,
            selected_calibration_reproduces_archived_design_inputs=True,
            new_evaluation_responses_not_required_to_match_old_strengths=True,
        ),
    )


def test_readouts(panel, readouts):
    matched = readouts[RULE["primary_panel"]]["resolution_matched"]
    paired = {
        name: [
            assay.paired_report(
                a["outcomes"]["voltage"],
                b["outcomes"]["voltage"],
                primary_name=RULE["primary_panel"],
                comparator_name=name,
            )
            | dict(level=i)
            for i, (a, b) in enumerate(
                zip(matched, readouts[name]["resolution_matched"], strict=True)
            )
        ]
        for name in RULE["paired_comparator_panels"]
    }
    primary = matched[2]["outcomes"]["voltage"]
    joint = primary["arms"]["joint"]["joint"]
    assert primary["feature_count"] == 15 and joint["cases"] == 32
    drift = readouts[RULE["primary_panel"]]["score_stability"]["voltage"]["resolution_matched"][
        "cases"
    ]
    drift = [r for r in drift if r["arm"] == "joint"]
    assert len(drift) == 64
    evidence(
        f"{PREFIX}-readouts",
        dict(
            status="passed",
            panels=readouts,
            paired_comparisons=paired,
            primary_joint_target_met=joint["all_cases_correct_and_resolved"],
            primary_joint_finest_score_stability=all(
                r["finest_steps_within_score_limits"] for r in drift
            ),
            primary_joint_finest_decisions_agree=all(r["finest_decisions_agree"] for r in drift),
            primary_panel=RULE["primary_panel"],
            comparator_panels=RULE["paired_comparator_panels"],
            preparations=RULE["preparations"],
            task_meanings=RULE["task_meanings"],
            primary_observations_after_both_cues=True,
            fresh_evaluation_strengths=True,
            scientific_outcome_is_not_an_acceptance_gate=True,
        ),
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, vectors in modes.items()
            for identity, value in vectors.items()
        },
    )


def test_contrasts(panel):
    contrasts = assay.paired_contrasts(ROWS, panel["maps"], RULE)
    assert len(contrasts) == 1320
    for row in contrasts:
        if row["arm"] == "no_cue":
            np.testing.assert_array_equal(row["contrast_V"], 0)
    evidence(
        f"{PREFIX}-contrasts",
        dict(
            status="passed",
            pairs=contrasts,
            outcomes_are_descriptive=True,
            continuum_error_bound=False,
        ),
    )
