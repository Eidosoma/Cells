"""Distributed-cue dose, controls, replay and CPU/L4 agreement.

Reuse the qualified reader and numerical comparison helpers; old source and
evidence stay frozen. No evaluation simulation occurs in host preflight.
"""

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
from validation.assays import distributed_cue as assay
from validation.assays import template_readout as reader
from validation.assays import two_task

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases(RULE)
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence


def test_host_distributed_design_dose_splits_and_resources():
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 140
    previous = reader.protocol()
    inspected = two_task.cases(OLD) + reader.cases(previous)
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in inspected)
    fresh = {r["amplitude"] for r in ROWS if r["split"] == "heldout"}
    assert fresh == {0.425, 0.575, 0.625, 0.775}
    assert fresh.isdisjoint(r["amplitude"] for r in inspected)
    assert RULE["dt_s"] == 0.25e-6 and RULE["duration_s"] == 64e-6
    assert RULE["reader"] == previous["reader"]
    assert RULE["cue"]["source_cell_ids"] == OLD["source_cell_ids"] == [1, 4]
    assert RULE["cue"]["location_weights"] == [[0.75, 0.25], [0.25, 0.75]]
    assert RULE["cue"]["location_coded_arms"] == ["location_only", "joint", "disconnected"]
    assert RULE["cue"]["timing_only_weights"] == [0.5, 0.5]
    assert RULE["cue"]["no_cue_weights"] == [0, 0]
    assert not RULE["automatic_followup"]
    for arm in OLD["arms"]:
        tasks, training, testing = reader.split(ROWS, arm)
        assert len(training) == (6 if len(tasks) == 1 else 12)
        assert len(testing) == (8 if len(tasks) == 1 else 16)
        assert {r["amplitude"] for r in training} == {0.4, 0.6, 0.8}
        assert {tuple(r[t] for t in tasks) for r in training} == {
            tuple(r[t] for t in tasks) for r in testing
        }
        assert {r["world_id"] for r in training}.isdisjoint(r["world_id"] for r in testing)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == i - 1 for i in OLD["source_cell_ids"]]
    source_area = min(area[mask].sum() for mask in masks)
    original_base = copy.deepcopy(BASE)
    retained, doses = 0, []
    for row in ROWS:
        raw = assay.definition(BASE, row, BACKEND, RULE)
        assert raw["model"] == BASE["model"]
        assert {"world_id", "location", "timing", "amplitude", "preparation", "split"}.isdisjoint(
            raw
        )
        previous_raw = reader.definition(BASE, row, BACKEND, RULE)
        restored = copy.deepcopy(raw)
        for change, previous_change in zip(
            restored["experiment"]["changes"], previous_raw["experiment"]["changes"], strict=True
        ):
            change["channel"] = previous_change["channel"]
        assert restored == previous_raw  # Only channel allocation may change.
        if row["arm"] in ("timing_only", "no_cue"):
            assert raw == previous_raw
        else:
            assert raw != previous_raw
        spec = parse_spec(raw)
        grid = timeline(spec)
        assert len(grid) == 257 and grid[-1] == RULE["duration_s"]
        controls = control_values(spec, grid[:-1])
        assert np.all((controls.channel >= 0) & (controls.channel <= 1))
        if row["arm"] == "no_cue":
            shares = np.zeros(2)
        elif row["arm"] == "timing_only":
            shares = np.full(2, 0.5)
        else:
            shares = np.array([0.75, 0.25] if row["location"] == 0 else [0.25, 0.75])
        # Independent physical-time and per-source dose calculation. Normalizing
        # each source by the reference area exposes accidental equal fractions
        # on unequal source surfaces, incorrect label swaps and timing drift.
        begin, end = (
            (16e-6, 24e-6)
            if row["arm"] == "location_only"
            else ((8e-6, 16e-6) if row["timing"] == 0 else (24e-6, 32e-6))
        )
        active = (grid[:-1] >= begin) & (grid[:-1] < end)
        source_doses = []
        for share, mask in zip(shares, masks, strict=True):
            amount = (1 - controls.channel[:, mask]) @ area[mask]
            np.testing.assert_allclose(
                amount / source_area, row["amplitude"] * share * active, rtol=2e-14, atol=1e-15
            )
            source_doses.append(float(amount.sum() * RULE["dt_s"]))
        np.testing.assert_array_equal(controls.channel[:, ~(masks[0] | masks[1])], 1)
        dose = float(np.sum((1 - controls.channel) @ area) * RULE["dt_s"])
        expected = 0 if row["arm"] == "no_cue" else row["amplitude"] * source_area * 8e-6
        assert dose == pytest.approx(expected, rel=2e-14, abs=1e-30)
        assert sum(source_doses) == pytest.approx(dose, rel=2e-14, abs=1e-30)
        np.testing.assert_array_equal(controls.pump, 1)
        np.testing.assert_array_equal(controls.junction, 0 if row["arm"] == "disconnected" else 1)
        assert set(spec.model.junction_block) <= {0.0, 1.0}
        doses.append(
            dict(
                world_id=row["world_id"],
                integrated_inhibition_m2_s=dose,
                source_integrated_inhibition_m2_s=source_doses,
                source_shares=shares.tolist(),
            )
        )
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
    assert BASE == original_base
    with pytest.raises(ValueError, match="Unregistered"):
        assay.definition(BASE, ROWS[0] | {"amplitude": 0.99}, BACKEND, RULE)
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
        "distributed-design",
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
            reader_and_margins_unchanged=True,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_distributed_prerequisite(prior):
    evidence("distributed-prerequisite", prior)


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
                f"distributed-world-{row['world_id']}",
                dict(
                    status="passed",
                    case=row,
                    input=result.spec.to_dict(),
                    diagnostics=result.diagnostics,
                ),
                reference.arrays(result),
            )
    return results, batches


def test_distributed_panel(panel):
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
        "distributed-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=140,
            batches=batches,
            max_material_error_over_budget=maximum,
        ),
    )


def test_distributed_calibration_reproduction(panel):
    results, _ = panel
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    old_rows = reader.cases(reader.protocol())
    selection = RULE["historical_reproduction"]
    compared, exact, checked = 0, 0, []
    for row in ROWS:
        if row["split"] != "calibration" or row["arm"] not in selection["arms"]:
            continue
        assert row["amplitude"] in selection["strengths"]
        old = next(
            r
            for r in old_rows
            if all(r[k] == row[k] for k in ("arm", "amplitude", "location", "timing"))
        )
        actual = reference.arrays(results[row["world_id"]])
        with np.load(root / f"templates-world-{old['world_id']}.npz", allow_pickle=False) as saved:
            compared += reference.compare(actual, saved, area)
            assert all(v.dtype == saved[name].dtype for name, v in actual.items())
            identical = all(np.array_equal(v, saved[name]) for name, v in actual.items())
            exact += int(identical)
        checked.append(
            dict(
                world_id=row["world_id"],
                prior_world_id=old["world_id"],
                arm=row["arm"],
                bitwise=identical,
            )
        )
    assert len(checked) == selection["worlds"] == 24
    evidence(
        "distributed-calibration-reproduction",
        dict(
            status="passed",
            worlds=len(checked),
            cases=checked,
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
        name: reader.evaluate(
            ROWS,
            values,
            margin=RULE["reader"][
                "input_margin" if name.startswith("input") else "voltage_margin_V"
            ],
        )
        for name, values in modes.items()
    }
    reports["voltage_1uV_margin"] = reader.evaluate(
        ROWS, voltage, margin=RULE["reader"]["coarse_voltage_margin_V"]
    )
    reports["balanced_centroid_voltage"] = reader.evaluate(
        ROWS, voltage, margin=RULE["reader"]["voltage_margin_V"], centroid=True
    )
    joint_rows = [r for r in ROWS if r["arm"] == "joint"]
    shuffles = [
        reader.evaluate(
            joint_rows, voltage, margin=RULE["reader"]["voltage_margin_V"], shuffle_seed=seed
        )
        for seed in RULE["reader"]["shuffle_seeds"]
    ]
    return modes, reports, shuffles


def test_distributed_readouts(panel, readouts):
    modes, reports, shuffles = readouts
    assert set(reports) == set(RULE["reader"]["modes"])
    assert len(shuffles) == 32
    for report in reports.values():
        for arm, row in report["arms"].items():
            tasks, training, testing = reader.split(ROWS, arm)
            assert row["calibration"]["world_ids"] == [r["world_id"] for r in training]
            for task in tasks:
                assert [r["world_id"] for r in row["tasks"][task]["predictions"]] == [
                    r["world_id"] for r in testing
                ]
    joint = reports["voltage"]["arms"]["joint"]["joint"]
    evidence(
        "distributed-readouts",
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


def test_distributed_controls(panel, readouts):
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
        "distributed-controls",
        dict(
            status="passed",
            no_cue_identical_worlds=28,
            excluded_single_task_duplicate_pairs=duplicates,
            disconnected_flux="zero",
            cue_absent_at_readout=True,
            input_at_readout_unresolved=True,
        ),
    )


def test_distributed_replay(panel, tmp_path):
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
    trained = reader.TemplateReader(
        np.stack([[vector, vector], [vector + 1e-7, vector + 1e-7]]),
        np.array([[0], [1]]),
        RULE["reader"]["voltage_margin_V"],
    )
    trained.read([vector])
    original.assert_history_same(expected.history, before)
    write_snapshot(
        tmp_path / "distributed-cue-cut", expected.spec, expected.checkpoint_at(expected.times[63])
    )
    restored = load_snapshot(tmp_path / "distributed-cue-cut")
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
        "distributed-replay",
        dict(
            status="passed",
            history_fields=14,
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=31,
            snapshot_step=63,
            replay="bitwise",
            passive_reader_neutrality=True,
            serialized_reader_covered_by_authenticated_prior=True,
        ),
    )


def test_distributed_cpu_gpu(panel, readouts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    results, _ = panel
    modes, reports, shuffles = readouts
    root = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count = 0
    for identity, result in results.items():
        with np.load(root / f"distributed-world-{identity}.npz", allow_pickle=False) as saved:
            count += reference.compare(reference.arrays(result), saved, area)
    atol = reference.PROTOCOL["tolerances"]["voltage_atol_V"]
    rtol = reference.PROTOCOL["tolerances"]["cpu_gpu_rtol"]
    with np.load(root / "distributed-readouts.npz", allow_pickle=False) as saved:
        for mode, values in modes.items():
            for identity, value in values.items():
                if mode.startswith("input"):
                    np.testing.assert_array_equal(value, saved[f"{mode}__{identity}"])
                else:
                    np.testing.assert_allclose(
                        value, saved[f"{mode}__{identity}"], atol=atol, rtol=rtol
                    )
    cpu = json.loads((root / "distributed-readouts.json").read_text())
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
        "distributed-cpu-gpu",
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
