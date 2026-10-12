"""Calibrated-template integrity, fresh inputs, replay and CPU/L4 agreement."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.batch import plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.runner import control_values, run, timeline
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_snapshot
from tests.unit import test_betse_junction_runtime as reference
from tests.unit import test_two_task_readout as original
from validation.assays import template_readout as assay
from validation.assays import two_task

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases(RULE)
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence


def test_host_templates_projection_clipping_ties_and_immutable_fit():
    vertices = np.array([[[0, 0], [1, 0], [1, 1]], [[0, 4], [1, 4], [1, 5]]], float)
    reader = assay.TemplateReader(vertices, np.array([[0], [1]]), 0.1)
    points = np.array([[0.25, 0], [1, 0.75], [1, 4.75], [-2, 0], [1, 2.5]])
    actual = reader.read(points)
    np.testing.assert_allclose(actual["score"][:, 0], [-2, -1.625, 1.875, 1 - np.sqrt(5), 0])
    np.testing.assert_array_equal(actual["prediction"][:, 0], [0, 0, 1, 0, 0])
    np.testing.assert_array_equal(actual["resolved"][:, 0], [True, True, True, True, False])
    np.testing.assert_array_equal(actual["closest_segments"][:3, 0], [0, 1, 1])
    np.testing.assert_allclose(actual["segment_coordinates"][:2, 0], [0.25, 0.75])
    assert actual["segment_coordinates"][3, 0] == 0  # No extrapolation.
    vertices[:] = 900
    np.testing.assert_array_equal(reader.read(points)["score"], actual["score"])
    with pytest.raises(ValueError):
        reader.vertices[0, 0] = 1
    with pytest.raises(TypeError):
        reader.read(points, strengths=[0.5] * len(points))
    restored = assay.TemplateReader(**json.loads(json.dumps(reader.to_dict())))
    np.testing.assert_array_equal(restored.read(points)["score"], actual["score"])
    perturbation = np.array([0.03, -0.04])
    changed = reader.read(points + perturbation)
    assert np.max(np.abs(changed["score"] - actual["score"])) <= 0.05 + 1e-15


def test_host_templates_degenerate_and_unresolved_curves():
    reader = assay.TemplateReader(
        np.ones((4, 3, 7)), np.array([[0, 0], [0, 1], [1, 0], [1, 1]]), 1e-9
    )
    answer = reader.read(np.array([[0] * 7, [1] * 7, [2] * 7]))
    np.testing.assert_array_equal(answer["score"], 0)
    assert not answer["resolved"].any()
    assert np.isfinite(answer["curve_distances"]).all()
    tiny = assay.TemplateReader(
        np.array([[[0], [0]], [[2e-9], [2e-9]]]), np.array([[0], [1]]), 2e-9
    )
    assert not tiny.read([[0], [2e-9]])["resolved"].any()


@pytest.mark.parametrize(
    "fault", ["nan", "labels", "incomplete", "duplicate", "strengths", "margin"]
)
def test_host_templates_reject_invalid_calibration(fault):
    x = np.arange(12, dtype=float).reshape(6, 2)
    y = np.array([[0], [0], [0], [1], [1], [1]])
    strengths = np.array([0.4, 0.6, 0.8, 0.4, 0.6, 0.8])
    margin = 0.1
    if fault == "nan":
        x[0, 0] = np.nan
    elif fault == "labels":
        y = y.astype(float)
    elif fault == "incomplete":
        x, y, strengths = x[:-1], y[:-1], strengths[:-1]
    elif fault == "duplicate":
        strengths[1] = strengths[0]
    elif fault == "strengths":
        strengths[0] = np.inf
    else:
        margin = 0
    with pytest.raises(ValueError):
        assay.TemplateReader.fit(x, y, strengths, minimum_margin=margin)


@pytest.fixture
def synthetic_panel():
    rows = [r for r in ROWS if r["arm"] == "joint"]
    # Strength changes the first coordinate by far more than the timing signal.
    # Curves preserve a small independent timing component, without using the
    # evaluation strength to select its segment position.
    values = {
        r["world_id"]: np.array(
            [100 * r["amplitude"] + 0.2 * r["timing"], 20 * r["location"], 0.01 * r["timing"]]
        )
        for r in rows
    }
    return rows, values


def test_host_templates_known_strength_confound_and_one_hot_encoding(synthetic_panel):
    rows, features = synthetic_panel
    actual = assay.evaluate(rows, features, margin=0.001)["arms"]["joint"]
    assert actual["joint"]["all_cases_correct_and_resolved"]
    comparator = assay.evaluate(rows, features, margin=0.001, centroid=True)["arms"]["joint"]
    assert comparator["tasks"]["timing"]["metrics"]["forced_accuracy"] == 0.5
    encoded = {
        r["world_id"]: np.eye(4)[2 * r["location"] + r["timing"]] * r["amplitude"] for r in rows
    }
    answer = assay.evaluate(rows, encoded, margin=1e-9)["arms"]["joint"]
    assert answer["joint"]["all_cases_correct_and_resolved"]
    assert answer["joint"]["cases"] == 16


def test_host_templates_evaluation_cannot_change_calibration(synthetic_panel):
    rows, features = synthetic_panel
    before = copy.deepcopy(features)
    initial = assay.evaluate(rows, features, margin=0.001)
    changed = copy.deepcopy(features)
    for row in rows:
        if row["split"] == "heldout":
            changed[row["world_id"]] *= -100
    another = assay.evaluate(rows, changed, margin=0.001)
    assert initial["arms"]["joint"]["calibration"] == another["arms"]["joint"]["calibration"]
    metadata = [
        r | {"amplitude": 0.51, "location": 1 - r["location"], "timing": 1 - r["timing"]}
        if r["split"] == "heldout"
        else r
        for r in rows
    ]
    relabelled = assay.evaluate(metadata, features, margin=0.001)
    for task in ("location", "timing"):
        a = initial["arms"]["joint"]["tasks"][task]["predictions"]
        b = relabelled["arms"]["joint"]["tasks"][task]["predictions"]
        for x, y in zip(a, b, strict=True):
            assert {k: v for k, v in x.items() if k != "target"} == {
                k: v for k, v in y.items() if k != "target"
            }
    for identity, value in features.items():
        np.testing.assert_array_equal(value, before[identity])
    shuffled = [
        assay.evaluate(rows, features, margin=0.001, shuffle_seed=s) for s in range(4200, 4204)
    ]
    assert shuffled[0] == assay.evaluate(rows, features, margin=0.001, shuffle_seed=4200)
    assert any(not r["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"] for r in shuffled)
    vertices = initial["arms"]["joint"]["calibration"]["template_reader"]["vertices"]
    assert all(
        r["arms"]["joint"]["calibration"]["template_reader"]["vertices"] == vertices
        for r in shuffled
    )


def test_host_templates_design_dose_splits_and_resources():
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 140
    old_rows = two_task.cases(OLD)
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in old_rows)
    fresh = {r["amplitude"] for r in ROWS if r["split"] == "heldout"}
    assert fresh == {0.45, 0.55, 0.65, 0.75}
    assert fresh.isdisjoint(r["amplitude"] for r in old_rows)
    assert RULE["dt_s"] == 0.25e-6 and RULE["duration_s"] == 64e-6
    assert not RULE["automatic_followup"]
    for arm in OLD["arms"]:
        tasks, training, testing = assay.split(ROWS, arm)
        assert len(training) == (6 if len(tasks) == 1 else 12)
        assert len(testing) == (8 if len(tasks) == 1 else 16)
        assert {tuple(r[t] for t in tasks) for r in training} == {
            tuple(r[t] for t in tasks) for r in testing
        }
        assert {r["world_id"] for r in training}.isdisjoint(r["world_id"] for r in testing)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    source_area = min(area[owner == i - 1].sum() for i in OLD["source_cell_ids"])
    retained, doses = 0, []
    for row in ROWS:
        raw = assay.definition(BASE, row, BACKEND, RULE)
        assert raw["model"] == BASE["model"]
        assert {"world_id", "location", "timing", "amplitude", "preparation", "split"}.isdisjoint(
            raw
        )
        expected = two_task.definition(
            BASE,
            row | {"world_id": row["world_id"] - RULE["world_id_offset"]},
            BACKEND,
            assay.physical_rule(RULE),
        )
        expected["execution"]["dt"] = RULE["dt_s"]
        assert raw == expected
        spec = parse_spec(raw)
        grid = timeline(spec)
        assert len(grid) == 257 and grid[-1] == RULE["duration_s"]
        controls = control_values(spec, grid[:-1])
        dose = float(np.sum((1 - controls.channel) @ area) * RULE["dt_s"])
        expected_dose = 0 if row["arm"] == "no_cue" else row["amplitude"] * source_area * 8e-6
        assert dose == pytest.approx(expected_dose, rel=2e-14, abs=1e-30)
        np.testing.assert_array_equal(controls.pump, 1)
        np.testing.assert_array_equal(controls.junction, 0 if row["arm"] == "disconnected" else 1)
        assert set(spec.model.junction_block) <= {0.0, 1.0}
        doses.append(dict(world_id=row["world_id"], integrated_inhibition_m2_s=dose))
        flat, layout = reference.model.initial_values(spec)
        state = reference.model.unflatten(flat)
        parameters = reference.model.parameters(spec, layout)
        fields = reference.kernel.passive.field(
            state.active.tissue, parameters.active.tissue, xp=np
        )
        state_bytes = sum(np.asarray(v).nbytes for v in flat)
        field_bytes = sum(np.asarray(v).nbytes for v in fields)
        layout_bytes = sum(np.asarray(v).nbytes for v in layout)
        observations = len(spec.experiment.observation_times)
        retained += 2 * (
            state_bytes * (257 + observations + 2)
            + field_bytes * observations
            + layout_bytes
            + 8 * (257 + observations)
        )
    plans = []
    for start in range(0, len(ROWS), RULE["batch_worlds"]):
        plan = assay.batch(BASE, ROWS[start : start + RULE["batch_worlds"]], BACKEND, RULE)
        planned = plan_batch(plan)
        plans.append(
            dict(
                world_ids=[w.world_id for w in plan.worlds],
                estimated_working_bytes=planned.estimated_working_bytes,
            )
        )
    windows = plan_batch_windows(plan, WindowPolicy(31))
    assert windows.estimated_working_bytes <= RULE["resources"]["max_batch_working_bytes"]
    assert retained <= RULE["resources"]["max_retained_array_estimate_bytes"]
    evidence(
        "templates-design",
        dict(
            status="passed",
            cases=ROWS,
            worlds=140,
            steps_per_arm=7168,
            total_world_steps=35840,
            calibration_strengths=[0.4, 0.6, 0.8],
            fresh_evaluation_strengths=sorted(fresh),
            allocation_plans=plans,
            retained_array_estimate_bytes=retained,
            integrated_doses=doses,
            window_estimated_working_bytes=windows.estimated_working_bytes,
            independent_biological_replicates=0,
            physics_and_tolerances_unchanged=True,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_templates_prerequisite(prior):
    evidence("templates-prerequisite", prior)


@pytest.fixture(scope="module")
def panel(prior):
    jax.config.update("jax_enable_x64", True)
    results, batches = {}, []
    for start in range(0, len(ROWS), RULE["batch_worlds"]):
        selected = ROWS[start : start + RULE["batch_worlds"]]
        plan = assay.batch(BASE, selected, BACKEND, RULE)
        actual = run_batch(plan)
        batches.append(
            dict(
                arm=selected[0]["arm"],
                world_ids=[r["world_id"] for r in selected],
                timings=actual.timings,
                resources=actual.resources,
            )
        )
        for row in selected:
            result = actual.worlds[row["world_id"]]
            assert all(v.device.platform == BACKEND for v in result.final.state)
            results[row["world_id"]] = result
            evidence(
                f"templates-world-{row['world_id']}",
                dict(
                    status="passed",
                    case=row,
                    input=result.spec.to_dict(),
                    diagnostics=result.diagnostics,
                ),
                reference.arrays(result),
            )
    return results, batches


def test_templates_panel(panel):
    results, batches = panel
    assert len(results) == 140
    assert all(len(r.history) == 14 for r in results.values())
    assert all(b["resources"]["executed_world_steps"] == 1024 for b in batches)
    assert all(
        sum(b["resources"]["executed_world_steps"] for b in batches if b["arm"] == arm) == 7168
        for arm in OLD["arms"]
    )
    maximum = max(r.diagnostics["max_material_error_over_budget"] for r in results.values())
    assert maximum <= 1
    evidence(
        "templates-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=140,
            batches=batches,
            max_material_error_over_budget=maximum,
        ),
    )


def test_templates_calibration_reproduction(panel):
    results, _ = panel
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    compared, worlds, exact = 0, 0, 0
    old_rows = two_task.cases(OLD)
    for row in ROWS:
        if row["split"] != "calibration" or row["amplitude"] not in (0.4, 0.8):
            continue
        old = next(
            r
            for r in old_rows
            if all(r[k] == row[k] for k in ("arm", "amplitude", "location", "timing"))
        )
        actual = reference.arrays(results[row["world_id"]])
        with np.load(root / f"timing-world-2-{old['world_id']}.npz", allow_pickle=False) as saved:
            compared += reference.compare(actual, saved, area)
            assert all(v.dtype == saved[name].dtype for name, v in actual.items())
            exact += int(all(np.array_equal(v, saved[name]) for name, v in actual.items()))
        worlds += 1
    assert worlds == 40
    evidence(
        "templates-calibration-reproduction",
        dict(
            status="passed",
            worlds=worlds,
            compared_values=compared,
            bitwise_worlds=exact,
            physical_tolerances_unchanged=True,
        ),
    )


@pytest.fixture(scope="module")
def readouts(panel):
    results, _ = panel
    voltage = {k: two_task.voltage_features(v, OLD) for k, v in results.items()}
    modes = dict(
        voltage=voltage,
        final_voltage={k: v[-7:] for k, v in voltage.items()},
        input_at_readout={
            k: two_task.input_features(v.spec, OLD["readout_steps"], OLD)
            for k, v in results.items()
        },
        input_history={
            k: two_task.input_features(v.spec, OLD["input_history_steps"], OLD)
            for k, v in results.items()
        },
    )
    reports = {
        name: assay.evaluate(
            ROWS,
            values,
            margin=RULE["reader"][
                "input_margin" if name.startswith("input") else "voltage_margin_V"
            ],
        )
        for name, values in modes.items()
    }
    reports["voltage_1uV_margin"] = assay.evaluate(
        ROWS, voltage, margin=RULE["reader"]["coarse_voltage_margin_V"]
    )
    reports["balanced_centroid_voltage"] = assay.evaluate(
        ROWS, voltage, margin=RULE["reader"]["voltage_margin_V"], centroid=True
    )
    joint_rows = [r for r in ROWS if r["arm"] == "joint"]
    shuffles = [
        assay.evaluate(
            joint_rows, voltage, margin=RULE["reader"]["voltage_margin_V"], shuffle_seed=seed
        )
        for seed in RULE["reader"]["shuffle_seeds"]
    ]
    return modes, reports, shuffles


def test_templates_readouts(panel, readouts):
    modes, reports, shuffles = readouts
    assert set(reports) == set(RULE["reader"]["modes"])
    assert len(shuffles) == 32
    for report in reports.values():
        for arm, row in report["arms"].items():
            tasks, training, testing = assay.split(ROWS, arm)
            assert row["calibration"]["world_ids"] == [r["world_id"] for r in training]
            for task in tasks:
                assert [r["world_id"] for r in row["tasks"][task]["predictions"]] == [
                    r["world_id"] for r in testing
                ]
    joint = reports["voltage"]["arms"]["joint"]["joint"]
    evidence(
        "templates-readouts",
        dict(
            status="passed",
            outcomes=reports,
            shuffles=shuffles,
            primary_joint_target_met=joint["all_cases_correct_and_resolved"],
            scientific_success_is_not_an_acceptance_gate=True,
            independent_biological_replicates=0,
        ),
        {
            f"{mode}__{identity}": value
            for mode, values in modes.items()
            for identity, value in values.items()
        },
    )


def test_templates_controls(panel, readouts):
    results, _ = panel
    modes, reports, _ = readouts
    for value in modes["input_at_readout"].values():
        np.testing.assert_allclose(value, 1, atol=4 * np.finfo(float).eps, rtol=0)
    no_cue = [r for r in ROWS if r["arm"] == "no_cue"]
    for row in no_cue[1:]:
        original.assert_history_same(
            results[row["world_id"]].history, results[no_cue[0]["world_id"]].history
        )
    for report in reports.values():
        for task in report["arms"]["no_cue"]["tasks"].values():
            assert task["metrics"]["resolved_fraction"] == 0
    for arm in reports["input_at_readout"]["arms"].values():
        assert all(t["metrics"]["resolved_fraction"] == 0 for t in arm["tasks"].values())
    duplicates = 0
    for row in ROWS:
        result = results[row["world_id"]]
        if row["arm"] == "disconnected":
            np.testing.assert_array_equal(result.history.junction_open[1:], 0)
            np.testing.assert_array_equal(result.history.junction_outward_fmol, 0)
        if row["arm"] in ("location_only", "timing_only"):
            ignored = "timing" if row["arm"] == "location_only" else "location"
            if row[ignored] == 0:
                paired = next(
                    r
                    for r in ROWS
                    if r[ignored] == 1
                    and all(
                        r[k] == row[k]
                        for k in ("arm", "preparation", "location", "timing")
                        if k != ignored
                    )
                )
                original.assert_history_same(result.history, results[paired["world_id"]].history)
                duplicates += 1
    assert duplicates == 28
    evidence(
        "templates-controls",
        dict(
            status="passed",
            no_cue_identical_worlds=28,
            excluded_single_task_duplicate_pairs=duplicates,
            disconnected_flux="zero",
            cue_absent_at_readout=True,
            input_at_readout_unresolved=True,
        ),
    )


def test_templates_replay(panel, tmp_path):
    results, _ = panel
    selected = [r for r in ROWS if r["arm"] == "joint"][:4]
    plan = assay.batch(BASE, selected, BACKEND, RULE)
    reverse = run_batch(replace(plan, worlds=tuple(reversed(plan.worlds))))
    for identity, value in reverse.worlds.items():
        original.assert_history_same(value.history, results[identity].history)
    for worlds in (plan.worlds[:2], plan.worlds[2:]):
        part = run_batch(replace(plan, worlds=worlds))
        for identity, value in part.worlds.items():
            original.assert_history_same(value.history, results[identity].history)
    windows = list(iter_batch_windows(plan, WindowPolicy(window_steps=31, recording="full")))
    for row in selected:
        identity = row["world_id"]
        expected = results[identity]
        history = type(expected.history)(
            *(
                np.concatenate(
                    [
                        getattr(window.worlds[identity].history, name)[0 if i == 0 else 1 :]
                        for i, window in enumerate(windows)
                    ]
                )
                for name in expected.history._fields
            )
        )
        original.assert_history_same(history, expected.history)
    expected = results[selected[0]["world_id"]]
    before = tuple(v.copy() for v in expected.history)
    vector = two_task.voltage_features(expected, OLD)
    trained = assay.TemplateReader(
        np.stack([[vector, vector], [vector + 1e-7, vector + 1e-7]]),
        np.array([[0], [1]]),
        RULE["reader"]["voltage_margin_V"],
    )
    trained.read([vector])
    original.assert_history_same(expected.history, before)
    write_snapshot(
        tmp_path / "template-cue-cut", expected.spec, expected.checkpoint_at(expected.times[63])
    )
    restored = load_snapshot(tmp_path / "template-cue-cut")
    resumed = run(restored.spec, restored.checkpoint)
    original.assert_history_same(
        resumed.history, type(expected.history)(*(v[63:] for v in expected.history))
    )
    np.testing.assert_array_equal(two_task.voltage_features(resumed, OLD), vector)
    np.testing.assert_array_equal(
        trained.read([two_task.voltage_features(resumed, OLD)])["score"],
        trained.read([vector])["score"],
    )
    evidence(
        "templates-replay",
        dict(
            status="passed",
            history_fields=14,
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=31,
            snapshot_step=63,
            replay="bitwise",
            passive_reader_neutrality=True,
            serialized_reader_checked_by_host_test=True,
        ),
    )


def test_templates_cpu_gpu(panel, readouts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    results, _ = panel
    modes, reports, shuffles = readouts
    root = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count = 0
    for identity, result in results.items():
        with np.load(root / f"templates-world-{identity}.npz", allow_pickle=False) as saved:
            count += reference.compare(reference.arrays(result), saved, area)
    atol = reference.PROTOCOL["tolerances"]["voltage_atol_V"]
    rtol = reference.PROTOCOL["tolerances"]["cpu_gpu_rtol"]
    with np.load(root / "templates-readouts.npz", allow_pickle=False) as saved:
        for mode, values in modes.items():
            for identity, value in values.items():
                if mode.startswith("input"):
                    np.testing.assert_array_equal(value, saved[f"{mode}__{identity}"])
                else:
                    np.testing.assert_allclose(
                        value, saved[f"{mode}__{identity}"], atol=atol, rtol=rtol
                    )
    cpu = json.loads((root / "templates-readouts.json").read_text())
    comparisons = []
    for mode, report in reports.items():
        for arm, detail in report["arms"].items():
            previous = cpu["outcomes"][mode]["arms"][arm]
            fitted, old_fit = detail["calibration"], previous["calibration"]
            assert fitted["world_ids"] == old_fit["world_ids"]
            if "template_reader" in fitted:
                actual = np.array(fitted["template_reader"]["vertices"])
                expected = np.array(old_fit["template_reader"]["vertices"])
                if mode.startswith("input"):
                    np.testing.assert_array_equal(actual, expected)
                else:
                    np.testing.assert_allclose(actual, expected, atol=atol, rtol=rtol)
            else:
                for x, y in zip(
                    fitted["centroid_readers"], old_fit["centroid_readers"], strict=True
                ):
                    np.testing.assert_allclose(x["centers"], y["centers"], atol=atol, rtol=rtol)
            for task, values in detail["tasks"].items():
                before = previous["tasks"][task]
                pairs = list(zip(values["predictions"], before["predictions"], strict=True))
                assert all(
                    (x["world_id"], x["target"]) == (y["world_id"], y["target"]) for x, y in pairs
                )
                differing = [
                    x["world_id"]
                    for x, y in pairs
                    if x["prediction"] != y["prediction"] or x["resolved"] != y["resolved"]
                ]
                comparisons.append(
                    dict(
                        mode=mode,
                        arm=arm,
                        task=task,
                        differing_decision_world_ids=differing,
                        maximum_score_difference=max(
                            abs(x["score"] - y["score"]) for x, y in pairs
                        ),
                        cpu_metrics=before["metrics"],
                        gpu_metrics=values["metrics"],
                    )
                )
    shuffle_agreement = [
        a["arms"]["joint"]["joint"] == b["arms"]["joint"]["joint"]
        for a, b in zip(shuffles, cpu["shuffles"], strict=True)
    ]
    evidence(
        "templates-cpu-gpu",
        dict(
            status="passed",
            worlds=140,
            compared_state_and_field_values=count,
            physical_tolerances_unchanged=True,
            comparisons=comparisons,
            exact_decision_agreement=not any(
                r["differing_decision_world_ids"] for r in comparisons
            ),
            shuffle_joint_metrics_agreement=shuffle_agreement,
            outcome_disagreements_are_reported=True,
        ),
    )
