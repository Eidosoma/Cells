"""Bounded temporal audit of the 75/25 panel, using qualified runtime checks."""

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
from validation.assays import distributed_cue, timing_refinement, two_task
from validation.assays import distributed_timing as temporal

RULE, CUE, OLD = temporal.protocol(), distributed_cue.protocol(), two_task.protocol()
ROWS = temporal.cases()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence
PREFIX = "distributed-timing"


def world_name(level, identity):
    return f"{PREFIX}-world-{level}-{identity}"


def test_host_distributed_timing_design_and_resources():
    assert RULE["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["simulated_levels"] == [1, 2]
    assert RULE["duration_s"] == CUE["duration_s"] == 64e-6
    assert len(ROWS) == 140 and ROWS == distributed_cue.cases(CUE)
    assert not RULE["automatic_followup"]
    assert RULE["contrast"] == timing_refinement.protocol()["contrast"] | {
        "stable_at_finest_steps": RULE["contrast"]["stable_at_finest_steps"]
    }
    assert RULE["reader_check"]["criteria"] == {
        "absolute_score_change_limit_V": CUE["reader"]["voltage_margin_V"],
        "relative_score_change_limit": 0.1,
    }
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == i - 1 for i in CUE["cue"]["source_cell_ids"]]
    plans, doses, retained_per_world = [], [], []
    original_base = copy.deepcopy(BASE)
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            expected = distributed_cue.definition(BASE, row, BACKEND, CUE)
            coarse = parse_spec(expected)
            old_control = control_values(coarse, timeline(coarse)[:-1])
            raw = temporal.definition(BASE, row, level, BACKEND, RULE)
            expected["execution"]["dt"] = dt
            assert raw == expected
            spec = parse_spec(raw)
            grid = timeline(spec)
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            np.testing.assert_allclose(
                spec.experiment.observation_times, RULE["readout_times_s"], atol=1e-20, rtol=0
            )
            controls = control_values(spec, grid[:-1])
            for field in ("pump", "channel", "junction"):
                np.testing.assert_array_equal(
                    getattr(controls, field),
                    np.repeat(getattr(old_control, field), 2**level, axis=0),
                )
            source_doses = []
            for mask in masks:
                actual = float(np.sum((1 - controls.channel[:, mask]) @ area[mask]) * dt)
                previous = float(
                    np.sum((1 - old_control.channel[:, mask]) @ area[mask]) * CUE["dt_s"]
                )
                assert actual == pytest.approx(previous, rel=2e-14, abs=1e-30)
                source_doses.append(actual)
            assert set(spec.model.junction_block) <= {0.0, 1.0}
            doses.append(
                dict(level=level, world_id=row["world_id"], source_doses_m2_s=source_doses)
            )
        # Geometry/array axes do not change between cases. Count each finest
        # world with two copies, then allow sixteen simultaneous equivalents
        # for a batch, retained replay references and comparison temporaries.
        flat, layout = reference.model.initial_values(spec)
        parameters = reference.model.parameters(spec, layout)
        fields = reference.kernel.passive.field(
            reference.model.unflatten(flat).active.tissue, parameters.active.tissue, xp=np
        )
        state_bytes = sum(np.asarray(v).nbytes for v in flat)
        field_bytes = sum(np.asarray(v).nbytes for v in fields)
        layout_bytes = sum(np.asarray(v).nbytes for v in layout)
        observations = len(spec.experiment.observation_times)
        retained_per_world.append(
            2
            * (
                state_bytes * (steps + 1 + observations + 2)
                + field_bytes * observations
                + layout_bytes
                + 8 * (steps + 1 + observations)
            )
        )
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            selected = ROWS[start : start + RULE["batch_worlds"]]
            plan = temporal.batch(BASE, selected, level, BACKEND, RULE)
            planned = plan_batch(plan)
            plans.append(
                dict(
                    level=level,
                    world_ids=[r["world_id"] for r in selected],
                    estimated_working_bytes=planned.estimated_working_bytes,
                )
            )
    assert BASE == original_base
    for bad in (-1, 3, True):
        with pytest.raises(ValueError, match="Unregistered refinement"):
            temporal.definition(BASE, ROWS[0], bad, BACKEND, RULE)
    retained = 16 * max(retained_per_world) + len(ROWS) * 3 * 21 * 8
    archive_estimate = len(ROWS) * sum(retained_per_world[i] for i in RULE["simulated_levels"])
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    fine = temporal.batch(BASE, ROWS[:4], 2, BACKEND, RULE)
    windows = plan_batch_windows(fine, WindowPolicy(127))
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            cases=ROWS,
            dt_s=RULE["dt_s"],
            allocation_plans=plans,
            archived_worlds_per_backend=140,
            new_worlds_per_backend=280,
            new_world_steps_per_backend=215040,
            new_steps_per_arm=43008,
            retained_array_estimate_bytes=retained,
            uncompressed_array_estimate_both_backends_bytes=archive_estimate,
            fine_window_estimated_working_bytes=windows.estimated_working_bytes,
            integrated_doses=doses,
            physical_inputs_reader_and_tolerances_unchanged=True,
            no_simulation_during_preflight=True,
        ),
    )


def fake_reports(scores, target=1):
    return [
        dict(
            arms={
                "joint": dict(
                    tasks={
                        "timing": dict(
                            predictions=[
                                dict(
                                    world_id=1,
                                    target=target,
                                    score=score,
                                    prediction=int(score > 0),
                                    resolved=abs(score) > 2e-9,
                                )
                            ]
                        )
                    }
                )
            }
        )
        for score in scores
    ]


def test_host_distributed_timing_score_drift_and_decision_changes():
    criteria = RULE["reader_check"]["criteria"]
    stable = temporal.score_changes(fake_reports([10.6e-9, 10.2e-9, 10e-9]), criteria)["cases"][0]
    assert stable["finest_steps_within_score_limits"] and stable["original_dt_within_score_limits"]
    assert stable["all_levels_correct_and_resolved"] and stable["finest_decisions_agree"]
    relative = temporal.score_changes(fake_reports([10e-9, 12e-9, 10e-9]), criteria)["cases"][0]
    assert relative["finest_decisions_agree"] and not relative["finest_steps_within_score_limits"]
    flipped = temporal.score_changes(fake_reports([3e-9, -3e-9, 3e-9]), criteria)["cases"][0]
    assert not flipped["finest_decisions_agree"] and not flipped["all_levels_correct_and_resolved"]
    assert flipped["successive_score_changes_V"] == pytest.approx([6e-9, 6e-9])


def test_host_distributed_timing_nulls_and_invalid_reports():
    criteria = RULE["reader_check"]["criteria"]
    null = temporal.score_changes(fake_reports([0, 0, 0]), criteria)["cases"][0]
    assert null["finest_steps_within_score_limits"] and null["stability_limit_V"] == 0
    assert not null["all_levels_correct_and_resolved"]
    invalid = fake_reports([0, 0, np.nan])
    with pytest.raises(ValueError, match="Finite"):
        temporal.score_changes(invalid, criteria)
    invalid = fake_reports([0, 0, 0])
    invalid[1]["arms"]["joint"]["tasks"]["timing"]["predictions"][0]["target"] = 0
    with pytest.raises(ValueError, match="targets changed"):
        temporal.score_changes(invalid, criteria)
    with pytest.raises(ValueError, match="Three"):
        temporal.score_changes(fake_reports([0, 0]), criteria)


def test_host_distributed_timing_frozen_reader_exposes_shared_shift():
    rows = [r for r in ROWS if r["arm"] == "joint"]
    voltages = []
    for level in range(3):
        features = {}
        for row in rows:
            value = np.zeros(21)
            value[-7:-4] = [
                10e-6 * row["location"],
                2e-6 * row["timing"] + level * 1.5e-6,
                1e-6 * row["amplitude"],
            ]
            features[row["world_id"]] = value
        voltages.append(features)
    actual = temporal.reader_reports(rows, voltages, RULE)
    for mode in RULE["reader_check"]["observation_modes"]:
        matched, frozen = (actual[name][mode] for name in ("resolution_matched", "frozen_coarse"))
        assert all(r["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"] for r in matched)
        assert frozen[0] == matched[0]
        assert frozen[2]["arms"]["joint"]["tasks"]["timing"]["metrics"]["forced_accuracy"] == 0.5
        assert all(
            r["arms"]["joint"]["calibration"] == frozen[0]["arms"]["joint"]["calibration"]
            for r in frozen
        )


@pytest.fixture(scope="module")
def prior():
    return temporal.baseline(RULE)


def test_distributed_timing_prerequisite(prior):
    evidence(f"{PREFIX}-prerequisite", prior)


@pytest.fixture(scope="module")
def panel(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    jax.config.update("jax_enable_x64", True)
    archive = Path(EVIDENCE) / BACKEND if EVIDENCE else tmp_path_factory.mktemp(PREFIX)
    archive.mkdir(parents=True, exist_ok=True)
    previous = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    voltages = {}
    with np.load(previous / "distributed-readouts.npz", allow_pickle=False) as saved:
        for row in ROWS:
            voltages[0, row["world_id"]] = saved[f"voltage__{row['world_id']}"].copy()
    replay_ids = {row["world_id"] for row in ROWS if row["arm"] == "joint"}
    replay_ids = set(sorted(replay_ids)[:4])
    replay, batches = {}, []
    maximum, no_cue_comparisons, duplicate_pairs, disconnected = 0.0, 0, 0, 0
    for level in RULE["simulated_levels"]:
        no_cue_reference = None
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            selected = ROWS[start : start + RULE["batch_worlds"]]
            plan = temporal.batch(BASE, selected, level, BACKEND, RULE)
            actual = run_batch(plan)
            batches.append(
                dict(
                    level=level,
                    dt_s=RULE["dt_s"][level],
                    arm=selected[0]["arm"],
                    world_ids=[r["world_id"] for r in selected],
                    timings=actual.timings,
                    resources=actual.resources,
                )
            )
            arm = selected[0]["arm"]
            assert len(selected) == 4 and all(r["arm"] == arm for r in selected)
            if arm in ("location_only", "timing_only"):
                pairs = [(0, 1), (2, 3)] if arm == "location_only" else [(0, 2), (1, 3)]
                for a, b in pairs:
                    original.assert_history_same(
                        actual.worlds[selected[a]["world_id"]].history,
                        actual.worlds[selected[b]["world_id"]].history,
                    )
                    duplicate_pairs += 1
            for row in selected:
                identity = row["world_id"]
                result = actual.worlds[identity]
                assert all(v.device.platform == BACKEND for v in result.final.state)
                assert len(result.history) == 14
                error = result.diagnostics["max_material_error_over_budget"]
                assert error <= 1
                maximum = max(maximum, error)
                np.testing.assert_allclose(
                    two_task.input_features(result.spec, OLD["readout_steps"], OLD),
                    1,
                    rtol=0,
                    atol=4 * np.finfo(float).eps,
                )
                if arm == "disconnected":
                    np.testing.assert_array_equal(result.history.junction_open[1:], 0)
                    np.testing.assert_array_equal(result.history.junction_outward_fmol, 0)
                    disconnected += 1
                values = reference.arrays(result)
                if arm == "no_cue":
                    if no_cue_reference is None:
                        no_cue_reference = archive / (world_name(level, identity) + ".npz")
                    else:
                        with np.load(no_cue_reference, allow_pickle=False) as saved:
                            assert set(saved) == set(values)
                            for name, value in values.items():
                                np.testing.assert_array_equal(value, saved[name])
                        no_cue_comparisons += 1
                name = world_name(level, identity)
                (archive / (name + ".json")).write_text(
                    json.dumps(
                        dict(
                            status="passed",
                            level=level,
                            dt_s=RULE["dt_s"][level],
                            case=row,
                            input=result.spec.to_dict(),
                            diagnostics=result.diagnostics,
                        ),
                        indent=2,
                        allow_nan=False,
                    )
                    + "\n"
                )
                np.savez_compressed(archive / (name + ".npz"), **values)
                voltages[level, identity] = two_task.voltage_features(result, OLD).copy()
                if level == 2 and identity in replay_ids:
                    replay[identity] = result
                del values, result
            del actual  # Full histories stay on disk except four replay references.
    return dict(
        archive=archive,
        voltages=voltages,
        replay=replay,
        batches=batches,
        max_material_error_over_budget=maximum,
        no_cue_comparisons=no_cue_comparisons,
        duplicate_pairs=duplicate_pairs,
        disconnected_worlds=disconnected,
    )


def test_distributed_timing_panel(panel):
    assert len(panel["voltages"]) == 420 and len(panel["replay"]) == 4
    batches = panel["batches"]
    assert len(batches) == 70
    assert sum(b["resources"]["executed_world_steps"] for b in batches) == 215040
    assert all(
        sum(b["resources"]["executed_world_steps"] for b in batches if b["arm"] == arm) == 43008
        for arm in OLD["arms"]
    )
    assert all(v.shape == (21,) and np.isfinite(v).all() for v in panel["voltages"].values())
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            archived_worlds=140,
            new_worlds=280,
            batches=batches,
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_history_worlds=len(panel["replay"]),
        ),
        {
            f"voltage__{level}__{identity}": value
            for (level, identity), value in panel["voltages"].items()
        },
    )


@pytest.fixture(scope="module")
def readouts(panel):
    voltages = [
        {row["world_id"]: panel["voltages"][level, row["world_id"]] for row in ROWS}
        for level in range(3)
    ]
    reports = temporal.reader_reports(ROWS, voltages, RULE)
    changes = {
        calibration: {
            mode: temporal.score_changes(levels, RULE["reader_check"]["criteria"])
            for mode, levels in modes.items()
        }
        for calibration, modes in reports.items()
    }
    return reports, changes


def test_distributed_timing_baseline_reproduction(panel, readouts):
    previous = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    old_reports = json.loads((previous / "distributed-readouts.json").read_text())["outcomes"]
    reports, _ = readouts
    for modes in reports.values():
        for mode, levels in modes.items():
            assert levels[0] == old_reports[mode]
    for row in ROWS:
        saved = json.loads((previous / f"distributed-world-{row['world_id']}.json").read_text())
        expected = parse_spec(temporal.definition(BASE, row, 0, BACKEND, RULE)).to_dict()
        assert saved["case"] == row and saved["input"] == expected
    evidence(
        f"{PREFIX}-baseline-reproduction",
        dict(
            status="passed",
            worlds=140,
            source=str(previous),
            exact_voltage_reader_modes=2,
            stored_physical_inputs_match=True,
            trajectories_resimulated=False,
            previous_full_trajectories_authenticated=True,
        ),
    )


@pytest.fixture(scope="module")
def contrasts(panel):
    return timing_refinement.paired_reports(ROWS, panel["voltages"], RULE)


def test_distributed_timing_contrasts(contrasts):
    assert len(contrasts) == 63
    assert all(np.asarray(row["timing_contrast_V"]).shape == (3, 21) for row in contrasts)
    assert sum(row["null_control"] for row in contrasts) == 28
    evidence(
        f"{PREFIX}-contrasts",
        dict(
            status="passed",
            criteria=RULE["contrast"],
            pairs=contrasts,
            scientific_outcome_is_not_an_acceptance_gate=True,
            fresh_validation_cases=0,
        ),
    )


def test_distributed_timing_readouts(readouts):
    reports, changes = readouts
    for modes in reports.values():
        for levels in modes.values():
            assert len(levels) == 3
            for report in levels:
                assert report["arms"]["joint"]["joint"]["cases"] == 16
    primary = reports["resolution_matched"]["voltage"]
    joint_changes = [
        r for r in changes["resolution_matched"]["voltage"]["cases"] if r["arm"] == "joint"
    ]
    assert len(joint_changes) == 32
    evidence(
        f"{PREFIX}-readouts",
        dict(
            status="passed",
            dt_s=RULE["dt_s"],
            reports=reports,
            score_changes=changes,
            primary_joint_correct_and_resolved_each_level=[
                r["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"] for r in primary
            ],
            primary_joint_finest_score_stability=all(
                r["finest_steps_within_score_limits"] for r in joint_changes
            ),
            primary_joint_finest_decisions_agree=all(
                r["finest_decisions_agree"] for r in joint_changes
            ),
            scientific_outcome_is_not_an_acceptance_gate=True,
        ),
    )


def test_distributed_timing_controls(panel, contrasts, readouts):
    assert panel["no_cue_comparisons"] == 54
    assert panel["duplicate_pairs"] == panel["disconnected_worlds"] == 56
    nulls = [r for r in contrasts if r["null_control"]]
    assert len(nulls) == 28
    for row in nulls:
        assert row["outcome"] == "zero_timing_contrast"
        np.testing.assert_array_equal(row["timing_contrast_V"], 0)
    for modes in readouts[0].values():
        for levels in modes.values():
            for report in levels:
                assert all(
                    t["metrics"]["resolved_fraction"] == 0
                    for t in report["arms"]["no_cue"]["tasks"].values()
                )
    evidence(
        f"{PREFIX}-controls",
        dict(
            status="passed",
            null_pairs=28,
            no_cue_bitwise_comparisons=54,
            unused_label_bitwise_pairs=56,
            disconnected_zero_flux_worlds=56,
            no_cue_readers_unresolved=True,
            cue_absent_at_readout=True,
            coarse_controls_authenticated=True,
        ),
    )


def test_distributed_timing_fine_replay(panel, tmp_path):
    expected = panel["replay"]
    selected = [r for r in ROWS if r["world_id"] in expected]
    plan = temporal.batch(BASE, selected, 2, BACKEND, RULE)
    reverse = run_batch(replace(plan, worlds=tuple(reversed(plan.worlds))))
    for identity, value in reverse.worlds.items():
        original.assert_history_same(value.history, expected[identity].history)
    del reverse
    for worlds in (plan.worlds[:2], plan.worlds[2:]):
        part = run_batch(replace(plan, worlds=worlds))
        for identity, value in part.worlds.items():
            original.assert_history_same(value.history, expected[identity].history)
        del part
    offset = 0
    for window in iter_batch_windows(plan, WindowPolicy(window_steps=127, recording="full")):
        for identity, value in window.worlds.items():
            reference_history = expected[identity].history
            original.assert_history_same(
                value.history,
                type(reference_history)(
                    *(v[offset : offset + len(value.times)] for v in reference_history)
                ),
            )
        offset += len(next(iter(window.worlds.values())).times) - 1
    assert offset == 1024
    reference_world = expected[selected[0]["world_id"]]
    cut = round(16e-6 / RULE["dt_s"][2]) - 1
    assert cut == 255
    write_snapshot(
        tmp_path / "distributed-fine-cut",
        reference_world.spec,
        reference_world.checkpoint_at(reference_world.times[cut]),
    )
    restored = load_snapshot(tmp_path / "distributed-fine-cut")
    resumed = run(restored.spec, restored.checkpoint)
    original.assert_history_same(
        resumed.history, type(reference_world.history)(*(v[cut:] for v in reference_world.history))
    )
    np.testing.assert_array_equal(
        two_task.voltage_features(resumed, OLD), two_task.voltage_features(reference_world, OLD)
    )
    evidence(
        f"{PREFIX}-fine-replay",
        dict(
            status="passed",
            level=2,
            dt_s=RULE["dt_s"][2],
            history_fields=14,
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=127,
            window_comparison_streamed=True,
            snapshot_step=cut,
            replay="bitwise",
        ),
    )


def test_distributed_timing_cpu_gpu(panel, contrasts, readouts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    cpu_root = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    compared = 0
    for level in RULE["simulated_levels"]:
        for row in ROWS:
            name = world_name(level, row["world_id"]) + ".npz"
            with (
                np.load(panel["archive"] / name, allow_pickle=False) as actual,
                np.load(cpu_root / name, allow_pickle=False) as saved,
            ):
                compared += reference.compare(actual, saved, area)
    with np.load(cpu_root / f"{PREFIX}-panel.npz", allow_pickle=False) as saved:
        cpu_voltages = {}
        for key, value in panel["voltages"].items():
            level, identity = key
            cpu_voltages[key] = saved[f"voltage__{level}__{identity}"].copy()
            np.testing.assert_allclose(
                value,
                cpu_voltages[key],
                atol=RULE["contrast"]["voltage_atol_V"],
                rtol=RULE["contrast"]["voltage_rtol"],
            )
    cpu_contrasts = json.loads((cpu_root / f"{PREFIX}-contrasts.json").read_text())["pairs"]
    contrast_differences, max_contrast_fraction = [], 0.0
    for actual, saved in zip(contrasts, cpu_contrasts, strict=True):
        assert actual["world_ids"] == saved["world_ids"]
        early, late = saved["world_ids"]
        budget = np.array(
            [
                2 * RULE["contrast"]["voltage_atol_V"]
                + RULE["contrast"]["voltage_rtol"]
                * (np.abs(cpu_voltages[level, early]) + np.abs(cpu_voltages[level, late]))
                for level in range(3)
            ]
        )
        difference = np.abs(np.asarray(actual["timing_contrast_V"]) - saved["timing_contrast_V"])
        fraction = float(np.max(difference / budget))
        assert fraction <= 1
        max_contrast_fraction = max(max_contrast_fraction, fraction)
        for field in (
            "outcome",
            "first_order_resolved",
            "finest_signal_above_declared_floor",
            "finest_steps_within_stability_limits",
            "original_dt_within_stability_limits",
        ):
            if actual[field] != saved[field]:
                contrast_differences.append(
                    dict(
                        world_ids=actual["world_ids"],
                        field=field,
                        cpu=saved[field],
                        gpu=actual[field],
                    )
                )
    cpu_readouts = json.loads((cpu_root / f"{PREFIX}-readouts.json").read_text())
    comparisons, stability_differences = [], []
    reports, changes = readouts
    for calibration, modes in reports.items():
        for mode, levels in modes.items():
            for level, report in enumerate(levels):
                previous = cpu_readouts["reports"][calibration][mode][level]
                for arm, detail in report["arms"].items():
                    other = previous["arms"][arm]
                    assert detail["calibration"]["world_ids"] == other["calibration"]["world_ids"]
                    fitted, old_fit = (r["calibration"]["template_reader"] for r in (detail, other))
                    assert fitted["labels"] == old_fit["labels"]
                    np.testing.assert_allclose(
                        fitted["vertices"],
                        old_fit["vertices"],
                        atol=RULE["contrast"]["voltage_atol_V"],
                        rtol=RULE["contrast"]["voltage_rtol"],
                    )
                    for task, data in detail["tasks"].items():
                        pairs = list(
                            zip(
                                data["predictions"],
                                other["tasks"][task]["predictions"],
                                strict=True,
                            )
                        )
                        assert all(
                            (a["world_id"], a["target"]) == (b["world_id"], b["target"])
                            for a, b in pairs
                        )
                        comparisons.append(
                            dict(
                                calibration=calibration,
                                mode=mode,
                                level=level,
                                arm=arm,
                                task=task,
                                differing_decision_world_ids=[
                                    a["world_id"]
                                    for a, b in pairs
                                    if (a["prediction"], a["resolved"])
                                    != (b["prediction"], b["resolved"])
                                ],
                                maximum_score_difference=max(
                                    abs(a["score"] - b["score"]) for a, b in pairs
                                ),
                                cpu_metrics=other["tasks"][task]["metrics"],
                                gpu_metrics=data["metrics"],
                            )
                        )
            actual_changes = changes[calibration][mode]["cases"]
            saved_changes = cpu_readouts["score_changes"][calibration][mode]["cases"]
            for actual, saved in zip(actual_changes, saved_changes, strict=True):
                assert all(actual[k] == saved[k] for k in ("arm", "task", "world_id", "target"))
                for field in (
                    "finest_steps_within_score_limits",
                    "original_dt_within_score_limits",
                    "finest_decisions_agree",
                    "original_decision_agrees",
                    "all_levels_correct_and_resolved",
                ):
                    if actual[field] != saved[field]:
                        stability_differences.append(
                            dict(
                                calibration=calibration,
                                mode=mode,
                                world_id=actual["world_id"],
                                arm=actual["arm"],
                                task=actual["task"],
                                field=field,
                                cpu=saved[field],
                                gpu=actual[field],
                            )
                        )
    evidence(
        f"{PREFIX}-cpu-gpu",
        dict(
            status="passed",
            new_worlds=280,
            authenticated_coarse_worlds=140,
            compared_state_and_field_values=compared,
            physical_tolerances_unchanged=True,
            maximum_paired_contrast_error_over_budget=max_contrast_fraction,
            contrast_classification_differences=contrast_differences,
            reader_stability_differences=stability_differences,
            comparisons=comparisons,
            exact_decision_agreement=not any(
                r["differing_decision_world_ids"] for r in comparisons
            ),
            scientific_outcome_differences_are_reported=True,
        ),
    )
