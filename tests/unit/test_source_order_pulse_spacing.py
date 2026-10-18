"""Qualify a calibration-only pulse change with the established windowed harness."""

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
from tests.unit import test_source_order_observation_design as geometry_checks
from tests.unit import test_source_order_selected as support_checks
from tests.unit import test_source_order_spanning as history
from validation.assays import source_order_pulse_spacing as assay
from validation.assays import two_task

RULE, SOURCE, ROWS = assay.protocol(), assay.SOURCE, assay.cases()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
PREFIX = "source-order-pulse-spacing"
evidence = reference.common.evidence
compare_historical_window = history.compare_historical_window


@pytest.fixture(scope="module", autouse=True)
def configured_harness():
    assert shared.POLICY.window_steps == RULE["window_steps"]
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, history, support_checks):
            for key, value in dict(
                RULE=RULE, ROWS=ROWS, BASE=BASE, PREFIX=PREFIX, assay=assay, evidence=evidence
            ).items():
                patch.setattr(module, key, value)
        patch.setattr(support_checks, "SOURCE", SOURCE)
        patch.setattr(shared, "compare_historical_window", compare_historical_window)
        yield


panel = shared.panel
test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = shared.test_host_source_order_long_archive_boundaries
test_host_support = support_checks.test_host_support


def test_host_design_and_resources():
    plan = assay.validate_plan(RULE)
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 60
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in assay.SOURCE_ROWS)
    assert {r["split"] for r in ROWS} == {"calibration"}
    assert Counter(r["arm"] for r in ROWS) == dict.fromkeys(plan["design"]["arms"], 12)
    original = copy.deepcopy(BASE)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == i - 1 for i in RULE["source_cell_ids"]]
    ref_area = min(area[m].sum() for m in masks)
    plans, doses, mapping, archive_estimate = [], [], [], 0
    saved = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            old, duration = assay.historical_source(row)
            before = assay.previous.definition(BASE, old, level, BACKEND, SOURCE)
            record = json.loads(
                (saved / (assay.world_name(level, old["world_id"]) + ".json")).read_text()
            )
            assert record["status"] == "passed" and record["input"] == before
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            assert raw["model"] == before["model"] == BASE["model"]
            assert raw["execution"] == before["execution"]
            assert {k: v for k, v in raw["experiment"].items() if k != "changes"} == {
                k: v for k, v in before["experiment"].items() if k != "changes"
            }
            if not assay.ordered(row):
                assert raw == before
            spec = parse_spec(raw)
            grid = np.asarray(list(checked_grid(spec)))
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            assert len(spec.experiment.observation_times) == 12
            assert min(assay.times(RULE, RULE["primary_panel"])) > 120e-6
            controls = control_values(spec, grid[:-1])
            old_controls = control_values(parse_spec(before), grid[:-1])
            stop = round(duration / dt)
            for new, previous in zip(controls, old_controls, strict=True):
                np.testing.assert_array_equal(new[:stop], previous[:stop])
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
                pulse = (
                    [16, 24]
                    if row["arm"] == "location_only"
                    else ([8, 16] if i == row["timing"] else [112, 120])
                )
                start, end = [round(t * 1e-6 / dt) for t in pulse]
                expected[start:end, mask] = (
                    1 - row["amplitude"] * weight * ref_area / area[mask].sum()
                )
            np.testing.assert_allclose(controls.channel, expected, rtol=0, atol=4e-16)
            assert np.all((controls.channel >= 0) & (controls.channel <= 1))
            amount = [float(np.sum((1 - controls.channel[:, m]) @ area[m]) * dt) for m in masks]
            old_amount = [
                float(np.sum((1 - old_controls.channel[:, m]) @ area[m]) * dt) for m in masks
            ]
            np.testing.assert_allclose(amount, old_amount, rtol=2e-14, atol=1e-30)
            np.testing.assert_allclose(
                amount,
                [row["amplitude"] * w * ref_area * 8e-6 for w in weights],
                rtol=2e-14,
                atol=1e-30,
            )
            doses.append(dict(level=level, world_id=row["world_id"], source_doses_m2_s=amount))
            mapping.append(
                dict(
                    level=level,
                    world_id=row["world_id"],
                    source_world_id=old["world_id"],
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
            bounded = plan_batch_windows(
                assay.batch(BASE, ROWS[start : start + 4], level, BACKEND, RULE), shared.POLICY
            )
            plans.append(
                dict(
                    level=level,
                    world_ids=[r["world_id"] for r in ROWS[start : start + 4]],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * len(RULE["observation_panels"]) * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 4 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 45
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    assert Counter(r["duration_s"] for r in mapping) == {512e-6: 72, 104e-6: 108}
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
            work=RULE["work"],
            uncompressed_archive_estimate_bytes=archive_estimate,
            retained_array_estimate_bytes=retained,
            no_response_simulation_during_preflight=True,
            calibration_only=True,
            changed_only_second_pulse_times=True,
        ),
    )


def test_host_history_boundaries(tmp_path, monkeypatch):
    root = tmp_path / "evidence" / BACKEND
    root.mkdir(parents=True)
    row = next(r for r in ROWS if r["arm"] == "joint")
    old, duration = assay.historical_source(row)
    dt, stop = RULE["dt_s"][0], 416
    assert duration == 104e-6 and round(duration / dt) == stop
    name = assay.world_name(0, old["world_id"])
    observed = np.asarray([40, 48, 64, 80, 96]) * 1e-6
    arrays = dict(
        state__voltage=np.arange(421, dtype=float)[:, None] * 1e-9,
        junction__open=np.ones((421, 1)),
        observed__voltage=np.ones((5, 1)),
    )
    np.savez_compressed(root / (name + ".npz"), **arrays)
    (root / (name + ".json")).write_text(
        json.dumps(
            dict(
                status="passed",
                windows=[
                    dict(
                        file=name + ".npz",
                        start_step=0,
                        stop_step=420,
                        observation_times=observed.tolist(),
                    )
                ],
            )
        )
    )
    monkeypatch.setitem(RULE, "prior_binding", {"root": str(tmp_path)})
    actual = {k: v.copy() for k, v in arrays.items()}
    actual["state__voltage"][stop + 1 :] += 999
    monkeypatch.setattr(reference, "arrays", lambda _: actual)
    value = SimpleNamespace(
        start_step=0,
        final=SimpleNamespace(
            step_index=420, layout=SimpleNamespace(tissue_membrane_area=np.ones(1))
        ),
        observations=SimpleNamespace(times=observed),
    )
    answer = compare_historical_window(value, row, 0)
    assert answer["bitwise"] and answer["stop_step"] == stop
    for key in actual:
        changed = stop if key.startswith("state__") else 0
        actual[key][changed] += 1
        with pytest.raises(AssertionError):
            compare_historical_window(value, row, 0)
        actual[key] = arrays[key].copy()
    value.start_step = stop
    assert compare_historical_window(value, row, 0) is None
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            shared_prefix_through_us=104,
            later_changed_response_ignored=True,
            corrupt_state_and_observation_prefix_rejected=True,
        ),
    )


def synthetic_calibration():
    saved = geometry_checks.CalibrationArraysOnly()
    for level in range(3):
        for name in assay.PANELS:
            for row in assay.SOURCE_ROWS:
                vector = (
                    np.pad(
                        [100 * row["amplitude"], 10 * row["location"], 6 * row["timing"]], (0, 12)
                    )
                    * 1e-9
                )
                if row["arm"] in ("no_cue", "disconnected"):
                    vector[:] = 0
                saved[f"{level}__{name}__voltage__{row['world_id']}"] = vector
    return saved


def test_host_calibration_isolation():
    saved = synthetic_calibration()
    maps, loaded = assay.load_reference(saved, ROWS)
    assert len(loaded) == len(set(loaded)) == 540
    expected = assay.calibration_geometry(ROWS, maps, RULE)
    poisoned_rows = list(reversed(ROWS)) + [geometry_checks.NoHeldoutMetadata()]
    saved["heldout_poison"] = object()
    other, keys = assay.load_reference(saved, poisoned_rows)
    assert keys == loaded
    for values in other.values():
        values["voltage"][-1] = object()
    assert assay.calibration_geometry(poisoned_rows, other, RULE) == expected
    for rows in (ROWS[:-1], ROWS + [ROWS[0]]):
        with pytest.raises(ValueError, match="calibration grid"):
            assay.load_reference(saved, rows)
    key, original = loaded[0], saved[loaded[0]].copy()
    for invalid in (np.zeros(14), np.full(15, np.nan)):
        saved[key] = invalid
        with pytest.raises(ValueError, match="Invalid calibration feature"):
            assay.load_reference(saved, ROWS)
    saved[key] = original
    evidence(
        f"{PREFIX}-calibration-isolation",
        dict(
            status="passed",
            named_calibration_arrays=540,
            archive_enumeration_forbidden=True,
            heldout_metadata_and_arrays_unread=True,
            permutation_invariant=True,
            incomplete_duplicate_and_invalid_calibration_rejected=True,
        ),
    )


def test_host_geometry_known_answers():
    for points, expected in (
        ([[-1, 0], [1, 0], [0, -1], [0, 1]], 0),
        ([[0, 0], [2, 0], [1, 1], [3, 1]], 1),
        ([[0, 0], [0, 0], [3, 4], [3, 4]], 5),
        ([[-1, 0, 0], [1, 0, 0], [0, -1, 2], [0, 1, 2]], 2),
    ):
        geometry_checks.test_closed_segment_ground_truth_and_orientation(points, expected)
    geometry_checks.test_distance_preserves_metric_under_scale_offset_and_rotation(
        2.0**-30, [0.03125, -0.0625, 0.125]
    )
    geometry_checks.test_opposite_label_separation_includes_interiors_not_just_vertices()
    geometry_checks.test_opposite_label_comparison_includes_different_other_task_labels()
    maps, _ = assay.load_reference(synthetic_calibration(), ROWS)
    report = assay.calibration_geometry(ROWS, maps, RULE)
    for group in report["panels"].values():
        assert group["score_V"] == pytest.approx(3e-9, rel=2e-14, abs=0)
        assert len(group["task_groups"]) == 12
        for item in group["task_groups"]:
            assert item["half_distance_V"] == pytest.approx(
                5e-9 if item["task"] == "location" else 3e-9, rel=2e-14, abs=0
            )
        assert len(group["calibration_null_controls"]) == 6
        assert all(
            t["resolved_cases"] == 0
            for n in group["calibration_null_controls"]
            for t in n["tasks"].values()
        )
    evidence(
        f"{PREFIX}-geometry-known-answers",
        dict(
            status="passed",
            analytic_minimum_V=3e-9,
            opposite_other_task_labels_included=True,
            closed_segment_interiors_endpoints_and_degeneracies_checked=True,
            metric_preserved_at_nanovolt_scale=True,
            nulls_excluded_from_objective=True,
        ),
    )


def test_host_decision_known_answers():
    def scores(primary, comparator=0):
        return dict(
            panels={
                name: dict(score_V=primary if name == "selected320" else comparator)
                for name in assay.PANELS
            }
        )

    baseline, candidate = scores(1.9e-9), scores(2.1e-9)
    improved = assay.protocol_comparison(baseline, candidate)
    assert improved["selected_onset_separation_us"] == 104
    assert improved["candidate_fitted_minimum_above_margin"]
    assert assay.protocol_comparison(scores(1.9e-9, 999), scores(2.1e-9, 1e-99)) == improved
    for value in (1.8e-9, 1.9e-9, 1.9e-9 + 0.5e-15):
        assert (
            assay.protocol_comparison(baseline, scores(value))["selected_onset_separation_us"] == 96
        )
    worse = assay.protocol_comparison(baseline, scores(1.8e-9))
    assert assay.combined_selection(improved, worse)["selected_onset_separation_us"] == 96
    assert assay.combined_selection(improved, improved)["selected_onset_separation_us"] == 104
    different = assay.protocol_comparison(baseline, scores(2.1e-9 + 2e-15))
    assert assay.combined_selection(improved, different)["selected_onset_separation_us"] == 96
    with pytest.raises(ValueError, match="choice"):
        assay.combined_selection(improved, improved | dict(selected_onset_separation_us=96))
    for invalid in (-1, np.inf, np.nan):
        with pytest.raises(ValueError):
            assay.protocol_comparison(baseline, scores(invalid))
    evidence(
        f"{PREFIX}-decision-known-answers",
        dict(
            status="passed",
            only_fixed_primary_enters_selection=True,
            baseline_preferred_for_ties=True,
            backend_disagreement_or_nonreproducible_scores_keep_baseline=True,
            invalid_scores_and_inconsistent_votes_rejected=True,
            automatic_followup=False,
        ),
    )


def test_host_plan_binding():
    assay.validate_plan(RULE)
    mutations = [
        ("cue_timing", "late_pulse_us", [104, 112]),
        ("reader", "voltage_margin_V", 1e-9),
        ("readout", "cell_ids", [1, 2, 3, 4, 5]),
        ("work", "worlds_per_backend", 660),
        ("observation_times_us", "selected320", [128, 192, 320]),
    ]
    changed_rules = []
    for section, key, value in mutations:
        changed = copy.deepcopy(RULE)
        changed[section][key] = value
        changed_rules.append(changed)
    changed_rules += [
        RULE | dict(preparations=SOURCE["preparations"]),
        RULE | dict(primary_panel="long512"),
        RULE | dict(dt_s=[1e-6]),
        RULE | dict(automatic_followup=True),
        RULE | dict(design_plan_sha256="bad"),
    ]
    for changed in changed_rules:
        with pytest.raises(AssertionError):
            assay.validate_plan(changed)
    evidence(
        f"{PREFIX}-plan-binding",
        dict(
            status="passed",
            source_plan_sha256=RULE["design_plan_sha256"],
            rejected_mutations=len(changed_rules),
            fixed_support_margin_inputs_and_calibration_split=True,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


test_prerequisite = shared.test_source_order_long_prerequisite
test_replay = shared.test_source_order_long_replay


def test_panel(panel):
    assert len(panel["batches"]) == 45
    assert sum(b["resources"]["executed_world_steps"] for b in panel["batches"]) == 860160
    for arm in assay.geometry.ARMS:
        assert (
            sum(b["resources"]["executed_world_steps"] for b in panel["batches"] if b["arm"] == arm)
            == 172032
        )
    assert all(len(values) == 60 for modes in panel["maps"].values() for values in modes.values())
    assert panel["max_material_error_over_budget"] <= 1
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=180,
            world_steps=860160,
            batches=panel["batches"],
            calibration_only=True,
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_world_histories=0,
        ),
    )


def test_controls(panel):
    assert panel["counts"] == dict(no_cue=154, unused_label_pairs=168, disconnected_windows=168)
    for (_level, name), modes in panel["maps"].items():
        for row in ROWS:
            if name in assay.PANELS or row["arm"] == "no_cue":
                np.testing.assert_allclose(
                    modes["input_at_readout"][row["world_id"]],
                    1,
                    rtol=0,
                    atol=4 * np.finfo(float).eps,
                )
            if row["arm"] == "no_cue":
                np.testing.assert_allclose(
                    modes["input_history"][row["world_id"]], 1, rtol=0, atol=4 * np.finfo(float).eps
                )
    evidence(
        f"{PREFIX}-controls",
        dict(
            status="passed",
            **panel["counts"],
            primary_inputs_off_before_every_observation=True,
            no_cue_inputs_constant=True,
            no_cue_and_unused_label_histories_bitwise_equal=True,
            disconnected_current_zero=True,
        ),
    )


def test_historical_reproduction(panel):
    histories = panel["prefixes"]
    assert len(histories) == 480
    assert len({(r["level"], r["world_id"]) for r in histories}) == 180
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            old, duration = assay.historical_source(row)
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(duration / dt)
            assert all(r["source_world_id"] == old["world_id"] for r in windows)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    count = 0
    with np.load(root / "source-order-selected-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for row in ROWS:
                old, duration = assay.historical_source(row)
                if max(assay.times(RULE, name)) > duration:
                    continue
                for mode, values in modes.items():
                    before = saved[f"{level}__{name}__{mode}__{old['world_id']}"]
                    np.testing.assert_array_equal(values[row["world_id"]], before)
                    count += before.size
    assert count == 38340
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            world_prefixes=180,
            full_512us_worlds=72,
            shared_104us_worlds=108,
            history_comparisons=histories,
            bitwise_history_comparisons=len(histories),
            exact_feature_scalars=count,
            heldout_responses_loaded=0,
        ),
    )


@pytest.fixture(scope="module")
def calibration(panel):
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    with np.load(root / "source-order-selected-readouts.npz", allow_pickle=False) as saved:
        baseline_maps, loaded = assay.load_reference(saved, ROWS)
    baseline = assay.calibration_geometry(ROWS, baseline_maps, RULE)
    candidate = assay.calibration_geometry(ROWS, panel["maps"], RULE)
    return dict(
        status="passed",
        baseline=baseline,
        candidate=candidate,
        comparison=assay.protocol_comparison(baseline, candidate),
        baseline_calibration_arrays_loaded=loaded,
        heldout_arrays_loaded=0,
        heldout_cases_evaluated=0,
        calibration_only=True,
        primary_panel="selected320",
        scientific_outcome_is_not_an_acceptance_gate=True,
        fitted_curve_geometry_is_not_a_continuum_or_noise_bound=True,
    )


def test_calibration(panel, calibration):
    assert len(calibration["baseline_calibration_arrays_loaded"]) == 540
    for name in assay.PANELS:
        for report in (calibration["baseline"], calibration["candidate"]):
            for null in report["panels"][name]["calibration_null_controls"]:
                if null["arm"] == "no_cue":
                    assert all(t["resolved_cases"] == 0 for t in null["tasks"].values())
    evidence(
        f"{PREFIX}-calibration",
        calibration,
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, vectors in modes.items()
            for identity, value in vectors.items()
        },
    )


def test_contrasts(panel):
    contrasts = assay.paired_contrasts(ROWS, panel["maps"], RULE)
    assert len(contrasts) == 360
    for row in contrasts:
        if row["arm"] == "no_cue":
            np.testing.assert_array_equal(row["contrast_V"], 0)
    evidence(
        f"{PREFIX}-contrasts",
        dict(
            status="passed",
            pairs=contrasts,
            calibration_only=True,
            outcomes_are_descriptive=True,
            continuum_error_bound=False,
        ),
    )


def test_cpu_gpu(panel, calibration):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU windows")
    assert EVIDENCE
    cpu = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count, feature_count = 0, 0
    for level in range(3):
        for row in ROWS:
            name = assay.world_name(level, row["world_id"])
            record = json.loads((panel["archive"] / (name + ".json")).read_text())
            before = json.loads((cpu / (name + ".json")).read_text())
            assert record["windows"] == before["windows"]
            for chunk in record["windows"]:
                with (
                    np.load(panel["archive"] / chunk["file"], allow_pickle=False) as actual,
                    np.load(cpu / chunk["file"], allow_pickle=False) as expected,
                ):
                    count += reference.compare(actual, expected, area)
    assert count == 2182733040
    tol = reference.PROTOCOL["tolerances"]
    cpu_voltages = {}
    with np.load(cpu / f"{PREFIX}-calibration.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for mode, vectors in modes.items():
                for identity, value in vectors.items():
                    expected = saved[f"{level}__{name}__{mode}__{identity}"]
                    np.testing.assert_allclose(
                        value, expected, atol=tol["voltage_atol_V"], rtol=tol["cpu_gpu_rtol"]
                    )
                    feature_count += value.size
                    if mode == "voltage":
                        cpu_voltages[level, name, identity] = expected.copy()
    cpu_contrasts = json.loads((cpu / f"{PREFIX}-contrasts.json").read_text())["pairs"]
    differences, maximum = [], 0.0
    for actual, expected in zip(
        assay.paired_contrasts(ROWS, panel["maps"], RULE), cpu_contrasts, strict=True
    ):
        assert all(actual[k] == expected[k] for k in ("panel", "task", "world_ids"))
        a, b = actual["world_ids"]
        name = actual["panel"]
        budget = np.asarray(
            [
                2 * tol["voltage_atol_V"]
                + tol["cpu_gpu_rtol"]
                * (abs(cpu_voltages[level, name, a]) + abs(cpu_voltages[level, name, b]))
                for level in range(3)
            ]
        )
        fraction = float(
            np.max(abs(np.asarray(actual["contrast_V"]) - expected["contrast_V"]) / budget)
        )
        assert fraction <= 1
        maximum = max(maximum, fraction)
        fields = [
            key
            for key in (
                "outcome",
                "first_order_resolved",
                "finest_signal_above_declared_floor",
                "finest_steps_within_stability_limits",
            )
            if actual[key] != expected[key]
        ]
        if fields:
            differences.append(
                dict(panel=name, task=actual["task"], world_ids=[a, b], differing_fields=fields)
            )
    previous = json.loads((cpu / f"{PREFIX}-calibration.json").read_text())
    decision = assay.combined_selection(previous["comparison"], calibration["comparison"])
    evidence(
        f"{PREFIX}-cpu-gpu",
        dict(
            status="passed",
            worlds=180,
            compared_scalars=count,
            compared_feature_scalars=feature_count,
            max_paired_contrast_error_over_budget=maximum,
            paired_contrast_outcome_differences=differences,
            physical_tolerances_unchanged=True,
            calibration_only=True,
            maximum_primary_geometry_score_difference_V=decision["maximum_score_difference_V"],
            geometry_winner_disagreement_is_reported_with_baseline_fallback=True,
        ),
    )
    evidence(
        f"{PREFIX}-selection",
        dict(
            status="passed",
            selection=decision,
            comparisons=dict(cpu=previous["comparison"], gpu=calibration["comparison"]),
            protocol_sha256=assay.digest(assay.PROTOCOL_PATH),
            design_plan_sha256=RULE["design_plan_sha256"],
            source_binding=RULE["prior_binding"],
            diagnostic_binding=RULE["diagnostic_binding"],
            primary_times_us=RULE["observation_times_us"]["selected320"],
            reader_margin_V=RULE["reader"]["voltage_margin_V"],
            heldout_cases_evaluated=0,
            prior_confirmation_result_unchanged=True,
            automatic_followup=False,
        ),
    )
