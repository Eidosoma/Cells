"""Paired timing self-refinement, preserved inputs and complete CPU/L4 replay."""

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
from validation.assays import timing_refinement as temporal
from validation.assays import two_task as assay

RULE, OLD = temporal.protocol(), assay.protocol()
BASE = json.loads((assay.ROOT / RULE["template"]).read_text())
ROWS = assay.cases(OLD)
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence


def test_host_timing_design_and_resources():
    assert RULE["dt_s"] == [1e-6, 0.5e-6, 0.25e-6]
    assert RULE["duration_s"] == OLD["steps"] * OLD["dt_s"] == 64e-6
    np.testing.assert_allclose(
        RULE["readout_times_s"],
        np.array(OLD["readout_steps"]) * OLD["dt_s"],
        rtol=0,
        atol=1e-20,
    )
    criteria = RULE["contrast"]
    assert criteria["absolute_change_limit_l2_V"] == OLD["reader"]["voltage_margin_V"]
    assert criteria["resolved_signal_min_l2_V"] == 2 * OLD["reader"]["voltage_margin_V"]
    assert criteria["relative_change_limit"] == 0.1
    assert criteria["voltage_atol_V"] == reference.PROTOCOL["tolerances"]["voltage_atol_V"]
    assert criteria["voltage_rtol"] == reference.PROTOCOL["tolerances"]["cpu_gpu_rtol"]
    assert criteria["performance_is_not_an_acceptance_gate"]
    assert not RULE["automatic_followup"]
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    retained, plans, doses = 0, [], []
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            expected = assay.definition(BASE, row, BACKEND, OLD)
            raw = temporal.definition(BASE, row, level, BACKEND, RULE)
            expected["execution"]["dt"] = dt
            assert raw == expected
            spec = parse_spec(raw)
            steps = round(RULE["duration_s"] / dt)
            grid = timeline(spec)
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            controls = control_values(spec, grid[:-1])
            dose = float(np.sum((1 - controls.channel) @ area) * dt)
            coarse = parse_spec(assay.definition(BASE, row, BACKEND, OLD))
            old_control = control_values(coarse, timeline(coarse)[:-1])
            expected_dose = float(np.sum((1 - old_control.channel) @ area) * OLD["dt_s"])
            assert dose == pytest.approx(expected_dose, rel=2e-14, abs=1e-30)
            np.testing.assert_array_equal(controls.pump, 1)
            np.testing.assert_array_equal(
                controls.junction, 0 if row["arm"] == "disconnected" else 1
            )
            # The fixed geometry also blocks exterior patches; only binary
            # stored-opening masks admit the same intervention under refinement.
            assert set(spec.model.junction_block) <= {0.0, 1.0}
            doses.append(
                dict(level=level, world_id=row["world_id"], integrated_inhibition_m2_s=dose)
            )
            # The shared working estimate also counts dense solve buffers at
            # each step. Count the actually retained state/observation/layout
            # arrays separately, with a factor of two for copies/temporaries.
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
                state_bytes * (steps + 1 + observations + 2)
                + field_bytes * observations
                + layout_bytes
                + 8 * (steps + 1 + observations)
            )
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            selected = ROWS[start : start + RULE["batch_worlds"]]
            full = temporal.batch(BASE, selected, level, BACKEND, RULE)
            plan = plan_batch(full)
            plans.append(
                dict(
                    level=level,
                    world_ids=[r["world_id"] for r in selected],
                    estimated_working_bytes=plan.estimated_working_bytes,
                )
            )
    fine = temporal.batch(BASE, ROWS[32:36], 2, BACKEND, RULE)
    window_plan = plan_batch_windows(fine, WindowPolicy(31))
    assert window_plan.estimated_working_bytes < fine.max_working_bytes
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    evidence(
        "timing-design",
        dict(
            status="passed",
            original_cases=ROWS,
            dt_s=RULE["dt_s"],
            worlds_per_backend=240,
            world_steps_per_backend=35840,
            steps_per_arm=7168,
            retained_array_estimate_bytes=retained,
            allocation_plans=plans,
            fine_window_estimated_working_bytes=window_plan.estimated_working_bytes,
            integrated_doses=doses,
            unchanged_model_initial_conditions_events_and_tolerances=True,
        ),
    )


def test_host_timing_known_first_order_and_small_changes():
    early = np.zeros((3, 2))
    late = np.array([3e-6, 4e-6]) + np.array([[1e-7, 0], [0.5e-7, 0], [0.25e-7, 0]])
    report = temporal.contrast_report(early, late, RULE["contrast"])
    assert report["first_order_resolved"] and report["order_comparison_resolved"]
    assert report["successive_change_ratio"] == pytest.approx(2)
    assert report["outcome"] == "step_sensitive"
    small = np.array([1e-7, 0]) + np.array([[4e-10, 0], [2e-10, 0], [1e-10, 0]])
    stable = temporal.contrast_report(early, small, RULE["contrast"])
    assert stable["outcome"] == "stable_at_finest_tested_steps"
    assert stable["original_dt_within_stability_limits"]
    assert stable["first_order_resolved"] is None  # Below the inherited comparison allowance.
    np.testing.assert_allclose(stable["successive_changes_l2_V"], [2e-10, 1e-10])


def test_host_timing_null_and_weak_signal_are_not_positive_results():
    background = np.full((3, 2), 0.02)
    null = temporal.contrast_report(background, background, RULE["contrast"])
    assert null["outcome"] == "zero_timing_contrast"
    assert not null["finest_signal_above_declared_floor"]
    assert null["coarse_fine_direction_cosine"] is null["first_order_resolved"] is None
    weak = temporal.contrast_report(background, background + 1e-10, RULE["contrast"])
    assert weak["finest_steps_within_stability_limits"]
    assert weak["outcome"] == "below_declared_reader_scale"


def test_host_timing_relative_error_and_sign_reversal_are_visible():
    background = np.full((3, 2), 0.02)
    # Below the absolute limit is insufficient if the signal changes by >10%.
    response = np.array([[7e-9, 0], [6e-9, 0], [5e-9, 0]])
    report = temporal.contrast_report(background, background + response, RULE["contrast"])
    assert report["successive_changes_l2_V"][1] < RULE["contrast"]["absolute_change_limit_l2_V"]
    assert report["outcome"] == "step_sensitive"
    reversed_response = np.array([[1e-7, 0], [1e-7, 0], [-1e-7, 0]])
    changed = temporal.contrast_report(background, background + reversed_response, RULE["contrast"])
    assert changed["coarse_fine_direction_cosine"] == pytest.approx(-1)
    assert changed["outcome"] == "step_sensitive"


@pytest.mark.parametrize("fault", ["shape", "levels", "nan", "empty"])
def test_host_timing_invalid_contrasts(fault):
    early, late = np.zeros((3, 2)), np.zeros((3, 2))
    if fault == "shape":
        late = np.zeros((3, 3))
    elif fault == "levels":
        early = late = np.zeros((2, 2))
    elif fault == "nan":
        late[0, 0] = np.nan
    else:
        early = late = np.zeros((3, 0))
    with pytest.raises(ValueError, match="paired voltage"):
        temporal.contrast_report(early, late, RULE["contrast"])


@pytest.fixture(scope="module")
def prior():
    return temporal.baseline(RULE)


def test_timing_prerequisite(prior):
    evidence("timing-prerequisite", prior)


@pytest.fixture(scope="module")
def panel(prior):
    assert prior["status"] == "passed"
    jax.config.update("jax_enable_x64", True)
    results, voltages, batches = {}, {}, []
    for level, dt in enumerate(RULE["dt_s"]):
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            selected = ROWS[start : start + RULE["batch_worlds"]]
            plan = temporal.batch(BASE, selected, level, BACKEND, RULE)
            actual = run_batch(plan)
            batches.append(
                dict(
                    level=level,
                    dt_s=dt,
                    arm=selected[0]["arm"],
                    world_ids=[r["world_id"] for r in selected],
                    timings=actual.timings,
                    resources=actual.resources,
                )
            )
            for row in selected:
                identity = row["world_id"]
                result = actual.worlds[identity]
                assert all(v.device.platform == BACKEND for v in result.final.state)
                assert len(result.history) == 14
                assert result.diagnostics["max_material_error_over_budget"] <= 1
                results[level, identity] = result
                voltages[level, identity] = assay.voltage_features(result, OLD)
                evidence(
                    f"timing-world-{level}-{identity}",
                    dict(
                        status="passed",
                        level=level,
                        case=row,
                        input=result.spec.to_dict(),
                        diagnostics=result.diagnostics,
                    ),
                    reference.arrays(result),
                )
    return results, voltages, batches


def test_timing_panel(panel):
    results, voltages, batches = panel
    assert len(results) == len(voltages) == 240
    assert sum(b["resources"]["executed_world_steps"] for b in batches) == 35840
    assert all(
        sum(b["resources"]["executed_world_steps"] for b in batches if b["arm"] == arm) == 7168
        for arm in OLD["arms"]
    )
    evidence(
        "timing-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=240,
            batches=batches,
            max_material_error_over_budget=max(
                r.diagnostics["max_material_error_over_budget"] for r in results.values()
            ),
        ),
        {f"voltage__{level}__{identity}": values for (level, identity), values in voltages.items()},
    )


def test_timing_coarse_reproduces_frozen_assay(panel):
    results, voltages, _ = panel
    prior = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    compared, readouts_bitwise, differences = 0, 0, []
    with np.load(prior / "assay-readouts.npz", allow_pickle=False) as readouts:
        for row in ROWS:
            identity = row["world_id"]
            actual_voltage, saved_voltage = voltages[0, identity], readouts[f"voltage__{identity}"]
            np.testing.assert_allclose(
                actual_voltage,
                saved_voltage,
                atol=RULE["contrast"]["voltage_atol_V"],
                rtol=RULE["contrast"]["voltage_rtol"],
            )
            readouts_bitwise += int(np.array_equal(actual_voltage, saved_voltage))
            with np.load(prior / f"assay-world-{identity}.npz", allow_pickle=False) as saved:
                actual = reference.arrays(results[0, identity])
                # A historical execution may differ in floating-point rounding.
                # Reuse the qualified field-specific physical tolerances; exact
                # within-run restart/window/partition checks remain below.
                compared += reference.compare(actual, saved, area)
                for name, values in actual.items():
                    assert values.dtype == saved[name].dtype
                    if not np.array_equal(values, saved[name]):
                        differences.append(
                            dict(
                                world_id=identity,
                                field=name,
                                differing_values=int(np.sum(values != saved[name])),
                                max_absolute_difference=float(np.max(np.abs(values - saved[name]))),
                            )
                        )
    evidence(
        "timing-coarse-reproduction",
        dict(
            status="passed",
            worlds=80,
            compared_values=compared,
            historical_comparison="existing_field_specific_physical_tolerances",
            physical_tolerances_unchanged=True,
            exact_voltage_readout_worlds=readouts_bitwise,
            full_history_bitwise=not differences,
            nonidentical_fields=differences,
            within_run_replay_requirement="bitwise",
        ),
    )


@pytest.fixture(scope="module")
def contrasts(panel):
    return temporal.paired_reports(ROWS, panel[1], RULE)


def test_timing_contrasts(panel, contrasts):
    assert len(contrasts) == 36
    assert all(len(r["timing_contrast_V"]) == 3 for r in contrasts)
    assert all(len(r["timing_contrast_V"][0]) == 21 for r in contrasts)
    # Signal stability is an outcome. The suite does not require a positive score.
    evidence(
        "timing-contrasts",
        dict(
            status="passed",
            criteria=RULE["contrast"],
            pairs=contrasts,
            scientific_outcome_is_not_an_acceptance_gate=True,
            aggregate_positive_scientific_claim=False,
            independently_prepared_biological_replicates=0,
        ),
    )


def test_timing_controls(panel, contrasts):
    results, _, _ = panel
    null_count = 0
    for level in range(3):
        no_cue = [r for r in ROWS if r["arm"] == "no_cue"]
        for row in no_cue[1:]:
            original.assert_history_same(
                results[level, row["world_id"]].history,
                results[level, no_cue[0]["world_id"]].history,
            )
        for row in ROWS:
            result = results[level, row["world_id"]]
            np.testing.assert_allclose(
                assay.input_features(result.spec, OLD["readout_steps"], OLD),
                1,
                rtol=0,
                atol=4 * np.finfo(float).eps,
            )
            if row["arm"] == "disconnected":
                np.testing.assert_array_equal(result.history.junction_open[1:], 0)
                np.testing.assert_array_equal(result.history.junction_outward_fmol, 0)
            ignored = "timing" if row["arm"] == "location_only" else "location"
            if row["arm"] in ("location_only", "timing_only") and row[ignored] == 0:
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
                original.assert_history_same(
                    result.history, results[level, paired["world_id"]].history
                )
    for row in contrasts:
        if row["null_control"]:
            assert row["outcome"] == "zero_timing_contrast"
            np.testing.assert_array_equal(row["timing_contrast_V"], 0)
            null_count += 1
    assert null_count == 16
    evidence(
        "timing-controls",
        dict(
            status="passed",
            null_pairs=null_count,
            no_cue_and_unused_label_histories="bitwise",
            disconnected_flux="zero",
            cue_absent_at_readout=True,
            all_three_resolutions_checked=True,
        ),
    )


def test_timing_fine_replay(panel, tmp_path):
    results, _, _ = panel
    selected = [r for r in ROWS if r["arm"] == "joint"][:4]
    plan = temporal.batch(BASE, selected, 2, BACKEND, RULE)
    reverse = run_batch(replace(plan, worlds=tuple(reversed(plan.worlds))))
    for identity, value in reverse.worlds.items():
        original.assert_history_same(value.history, results[2, identity].history)
    for worlds in (plan.worlds[:2], plan.worlds[2:]):
        part = run_batch(replace(plan, worlds=worlds))
        for identity, value in part.worlds.items():
            original.assert_history_same(value.history, results[2, identity].history)
    windows = list(iter_batch_windows(plan, WindowPolicy(window_steps=31, recording="full")))
    for row in selected:
        identity = row["world_id"]
        expected = results[2, identity]
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
    expected = results[2, selected[0]["world_id"]]
    cut = 63  # 15.75 us, immediately before early-cue removal on the fine grid.
    write_snapshot(
        tmp_path / "fine-cue-cut", expected.spec, expected.checkpoint_at(expected.times[cut])
    )
    restored = load_snapshot(tmp_path / "fine-cue-cut")
    resumed = run(restored.spec, restored.checkpoint)
    original.assert_history_same(
        resumed.history, type(expected.history)(*(v[cut:] for v in expected.history))
    )
    np.testing.assert_array_equal(
        assay.voltage_features(resumed, OLD), assay.voltage_features(expected, OLD)
    )
    evidence(
        "timing-fine-replay",
        dict(
            status="passed",
            level=2,
            dt_s=RULE["dt_s"][2],
            history_fields=14,
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=31,
            snapshot_step=cut,
            replay="bitwise",
        ),
    )


def test_timing_cpu_gpu(panel, contrasts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    results, voltages, _ = panel
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count = 0
    for (level, identity), result in results.items():
        with np.load(
            Path(EVIDENCE) / f"cpu/timing-world-{level}-{identity}.npz", allow_pickle=False
        ) as saved:
            count += reference.compare(reference.arrays(result), saved, area)
    cpu_root = Path(EVIDENCE) / "cpu"
    with np.load(cpu_root / "timing-panel.npz", allow_pickle=False) as saved:
        for (level, identity), value in voltages.items():
            np.testing.assert_allclose(
                value,
                saved[f"voltage__{level}__{identity}"],
                atol=RULE["contrast"]["voltage_atol_V"],
                rtol=RULE["contrast"]["voltage_rtol"],
            )
        cpu_voltages = {
            (level, identity): saved[f"voltage__{level}__{identity}"]
            for level, identity in voltages
        }
    cpu_reports = json.loads((cpu_root / "timing-contrasts.json").read_text())["pairs"]
    differences, maximum = [], 0.0
    for gpu, cpu in zip(contrasts, cpu_reports, strict=True):
        assert gpu["world_ids"] == cpu["world_ids"]
        early, late = cpu["world_ids"]
        actual, expected = np.array(gpu["timing_contrast_V"]), np.array(cpu["timing_contrast_V"])
        budget = np.array(
            [
                2 * RULE["contrast"]["voltage_atol_V"]
                + RULE["contrast"]["voltage_rtol"]
                * (np.abs(cpu_voltages[level, early]) + np.abs(cpu_voltages[level, late]))
                for level in range(3)
            ]
        )
        fraction = float(np.max(np.abs(actual - expected) / budget))
        assert fraction <= 1
        maximum = max(maximum, fraction)
        for key in (
            "outcome",
            "first_order_resolved",
            "finest_signal_above_declared_floor",
            "finest_steps_within_stability_limits",
            "original_dt_within_stability_limits",
        ):
            if gpu[key] != cpu[key]:
                differences.append(
                    dict(world_ids=cpu["world_ids"], field=key, cpu=cpu[key], gpu=gpu[key])
                )
    evidence(
        "timing-cpu-gpu",
        dict(
            status="passed",
            worlds=240,
            compared_state_and_field_values=count,
            physical_tolerances_unchanged=True,
            maximum_paired_contrast_error_over_budget=maximum,
            diagnostic_classification_differences=differences,
            exact_classification_agreement=not differences,
        ),
    )
