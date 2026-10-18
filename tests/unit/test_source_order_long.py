"""Paired 512-us observations with unchanged source-order cues and readers."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import jax
import numpy as np
import pytest

from cells.core.batch_windows import iter_batch_windows, plan_batch_windows, run_batch_windowed
from cells.core.grid import checked_grid
from cells.core.runner import control_values
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy, iter_windows
from cells.io import load_snapshot, write_snapshot
from tests.unit import test_baseline_transfer_diagnostic as reference_checks
from tests.unit import test_betse_junction_runtime as reference
from tests.unit import test_long_observation as inherited_checks
from validation.assays import distributed_timing, two_task
from validation.assays import source_order as predecessor
from validation.assays import source_order_long as assay

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases()
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence
POLICY = WindowPolicy(RULE["window_steps"], "full")
PREFIX = "source-order-long"


def test_host_source_order_long_design_and_resources():
    old = predecessor.protocol()
    assert ROWS == predecessor.cases() and len(ROWS) == 140
    assert RULE["duration_s"] == 2 * old["duration_s"] == 512e-6
    assert RULE["max_steps"] == 8192 and not RULE["automatic_followup"]
    assert RULE["dt_s"] == old["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["primary_panel"] == "long512"
    for key in ("preparations", "reader", "readout", "cue_timing", "task_meanings", "replay"):
        assert RULE[key] == old[key], key
    assert RULE["score_stability"] == distributed_timing.protocol()["reader_check"]["criteria"]
    for name in RULE["observation_panels"]:
        np.testing.assert_allclose(
            assay.times(RULE, name) * 1e6, RULE["observation_times_us"][name], atol=1e-12, rtol=0
        )
    np.testing.assert_allclose(
        assay.times(RULE, "long512") * 1e6, [320, 384, 512], atol=1e-12, rtol=0
    )
    original = copy.deepcopy(BASE)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == identity - 1 for identity in RULE["source_cell_ids"]]
    plans, doses, archive_estimate = [], [], 0
    history = Path(RULE["historical_binding"]["root"]) / "evidence" / BACKEND
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            before = predecessor.definition(BASE, row, level, BACKEND, old)
            recorded = json.loads(
                (history / (assay.world_name(level, row["world_id"]) + ".json")).read_text()
            )
            assert recorded["status"] == "passed" and recorded["case"] == row
            assert before == recorded["input"]
            # Exact preceding physical inputs, with only the registered execution
            # ceiling, horizon and observation list extended.
            stripped = copy.deepcopy(raw)
            stripped["execution"]["max_steps"] = before["execution"]["max_steps"]
            for key in ("end_time", "observation_times"):
                stripped["experiment"][key] = before["experiment"][key]
            assert stripped == before
            spec = parse_spec(raw)
            grid = np.asarray(list(checked_grid(spec)))
            assert len(grid) == steps + 1 and grid[-1] == 512e-6
            assert len(spec.experiment.observation_times) == 12
            controls = control_values(spec, grid[:-1])
            previous_steps = round(old["duration_s"] / dt)
            original_controls = control_values(parse_spec(before), grid[:previous_steps])
            for actual, expected in zip(controls, original_controls, strict=True):
                np.testing.assert_array_equal(actual[:previous_steps], expected)
            np.testing.assert_array_equal(controls.pump, 1)
            np.testing.assert_array_equal(
                controls.junction, 0 if row["arm"] == "disconnected" else 1
            )
            np.testing.assert_array_equal(controls.channel[grid[:-1] >= 112 * OLD["dt_s"]], 1)
            np.testing.assert_array_equal(controls.channel[:, ~(masks[0] | masks[1])], 1)
            amounts = [
                float(np.sum((1 - controls.channel[:, mask]) @ area[mask]) * dt) for mask in masks
            ]
            old_amounts = [
                float(np.sum((1 - original_controls.channel[:, mask]) @ area[mask]) * dt)
                for mask in masks
            ]
            np.testing.assert_allclose(amounts, old_amounts, rtol=2e-14, atol=1e-30)
            doses.append(dict(level=level, world_id=row["world_id"], source_doses_m2_s=amounts))
        flat, layout = reference.model.initial_values(spec)
        per_state = sum(np.asarray(v).nbytes for v in flat)
        parameters = reference.model.parameters(spec, layout)
        fields = reference.kernel.passive.field(
            reference.model.unflatten(flat).active.tissue, parameters.active.tissue, xp=np
        )
        field_bytes = sum(np.asarray(v).nbytes for v in fields)
        windows = steps // RULE["window_steps"]
        archive_estimate += 2 * len(ROWS) * (per_state * (steps + windows) + field_bytes * 12)
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            batch = assay.batch(
                BASE, ROWS[start : start + RULE["batch_worlds"]], level, BACKEND, RULE
            )
            bounded = plan_batch_windows(batch, POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in batch.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    assert BASE == original
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * 4 * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 4 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 105 and max(p["estimated_working_bytes"] for p in plans) < 4 * 1024**3
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
            dt_s=RULE["dt_s"],
            observations_us=RULE["observation_times_us"],
            primary_panel=RULE["primary_panel"],
            new_worlds_per_backend=420,
            world_steps_per_backend=2007040,
            steps_per_arm=401408,
            retained_array_estimate_bytes=retained,
            uncompressed_arrays_both_backends_bytes=archive_estimate,
            exact_predecessor_physical_inputs=420,
            unchanged_sources_and_per_source_doses=True,
            reused_evaluation_cases_are_not_fresh_holdouts=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_source_order_long_support():
    ids = np.array([4, 7, 2, 1, 5, 3, 6])
    owner, area = np.repeat(np.arange(7), 2), np.arange(1, 15, dtype=float)
    times = np.sort(np.concatenate([assay.times(RULE, p) for p in RULE["observation_panels"]]))
    voltage = np.arange(len(times) * len(owner), dtype=float).reshape(len(times), -1) * 1e-6
    result = SimpleNamespace(
        spec=parse_spec(assay.definition(BASE, ROWS[0], 2, BACKEND, RULE)),
        final=SimpleNamespace(
            layout=SimpleNamespace(ids=ids, tissue_cell_owner=owner, tissue_membrane_area=area)
        ),
        observations=SimpleNamespace(times=times, membrane_voltage_V=voltage),
    )
    saved = {}
    for panel in RULE["observation_panels"]:
        actual = assay.features(result, RULE, panel)
        selected = [int(np.flatnonzero(times == t)[0]) for t in assay.times(RULE, panel)]
        expected = [
            sum(voltage[i, c] * area[c] for c in np.flatnonzero(ids[owner] == identity))
            / area[ids[owner] == identity].sum()
            for i in selected
            for identity in RULE["readout"]["cell_ids"]
        ]
        np.testing.assert_allclose(actual["voltage"], expected, rtol=0, atol=1e-19)
        assert actual["voltage"].shape == (15,) and actual["all_cell_voltage"].shape == (21,)
        saved[panel] = actual
    voltage[:, np.isin(ids[owner], [1, 4])] += 123
    for panel in saved:
        np.testing.assert_array_equal(
            assay.features(result, RULE, panel)["voltage"], saved[panel]["voltage"]
        )
    voltage[times <= 256 * OLD["dt_s"]] += 456
    np.testing.assert_array_equal(
        assay.features(result, RULE, "long512")["voltage"], saved["long512"]["voltage"]
    )
    with pytest.raises(TypeError):
        assay.features(result, RULE, "long512", labels=[0, 1])
    evidence(
        f"{PREFIX}-support",
        dict(
            status="passed",
            panels=4,
            primary_features_each=15,
            unequal_area_weighting=True,
            source_and_earlier_voltages_excluded_from_later_panel=True,
        ),
    )


def test_host_source_order_long_reader_isolation():
    inherited_checks.test_host_long_observation_reader_isolation()
    evidence(f"{PREFIX}-reader-isolation", dict(status="passed", reused_known_answers=True))


def test_host_source_order_long_archive_boundaries(tmp_path):
    inherited_checks.test_host_long_observation_archive_boundaries(tmp_path)
    evidence(f"{PREFIX}-archive", dict(status="passed", reused_archive_boundary_check=True))


def test_host_source_order_long_reference_known_answers():
    reference_checks.test_shared_background_translation_restores_transfer_without_refitting_responses()
    reference_checks.test_background_reference_cannot_hide_cue_dependent_drift()
    for split in ("calibration", "heldout"):
        reference_checks.test_inconsistent_duplicate_controls_are_rejected(split)
    reference_checks.test_reference_does_not_depend_on_stimulated_labels_strengths_or_responses()
    reference_checks.test_translation_checks_reject_changed_scores_and_decisions()
    reference_checks.test_zero_drift_has_no_spurious_relative_fraction()
    maps = {}
    for level in range(3):
        values = {}
        for row in ROWS:
            response = np.array(
                [row["location"] * 10e-6, row["timing"] * 2e-6, row["amplitude"] * 1e-6, 0, 0]
            )
            if row["arm"] in ("no_cue", "disconnected"):
                response[:] = 0
            elif row["arm"] == "location_only":
                response[1] = 0
            elif row["arm"] == "timing_only":
                response[0] = 0
            response += np.array([0, level * 1.5e-6, 0, 0, 0])
            values[row["world_id"]] = np.tile(response, 3)
        for name in RULE["observation_panels"]:
            vectors = (
                values
                if name == RULE["primary_panel"]
                else {k: np.zeros_like(v) for k, v in values.items()}
            )
            maps[level, name] = dict(
                voltage=vectors,
                final_voltage={k: v[-5:] for k, v in vectors.items()},
                all_cell_voltage={k: np.pad(v, (0, 6)) for k, v in vectors.items()},
                input_at_readout={k: np.ones(15) for k in values},
                input_history={k: np.ones(15) for k in values},
            )
    reports = assay.reader_reports(ROWS, maps, RULE)
    original = copy.deepcopy(reports)
    result = assay.reference_reports(ROWS, maps, reports, RULE)
    assert reports == original
    assert {(r["source_level"], r["target_level"]) for r in result["transfers"]} == {
        (a, b) for a in range(3) for b in range(3)
    }
    assert all(
        r["outcomes"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
        for r in result["transfers"]
    )
    assert len(result["matched_translation_checks"]) == 3
    frozen = reports[RULE["primary_panel"]]["frozen_coarse"]["voltage"][2]
    assert frozen["arms"]["joint"]["tasks"]["timing"]["metrics"]["forced_accuracy"] == 0.5
    evidence(
        f"{PREFIX}-reference-known-answers",
        dict(
            status="passed",
            synthetic_fixed_later_panel=True,
            earlier_uninformative_panel_cannot_replace_primary=True,
            all_nine_transfers_restore_known_shared_shift=True,
            matched_scores_and_original_reports_preserved=True,
            cue_dependent_drift_and_corrupted_controls_rejected=True,
            inherited_known_answers=7,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_source_order_long_prerequisite(prior):
    evidence(f"{PREFIX}-prerequisite", prior)


def compare_historical_window(value, row, level):
    """Compare every shared state and sampled field up to the old 256-us endpoint."""
    limit = round(predecessor.protocol()["duration_s"] / RULE["dt_s"][level])
    if value.start_step >= limit:
        return None
    stop = min(value.final.step_index, limit)
    old_times = value.observations.times <= limit * RULE["dt_s"][level]
    root = Path(RULE["historical_binding"]["root"]) / "evidence" / BACKEND
    saved = assay.archived_segment(
        root, level, row["world_id"], value.start_step, stop, value.observations.times[old_times]
    )
    actual = {
        name: a[old_times] if name.startswith("observed__") else a[: stop - value.start_step + 1]
        for name, a in reference.arrays(value).items()
    }
    count = reference.compare(actual, saved, value.final.layout.tissue_membrane_area)
    return dict(
        level=level,
        world_id=row["world_id"],
        start_step=value.start_step,
        stop_step=stop,
        compared_scalars=count,
        bitwise=all(np.array_equal(actual[k], saved[k]) for k in actual),
    )


def test_host_source_order_long_history_boundaries(tmp_path, monkeypatch):
    root = tmp_path / "evidence" / BACKEND
    root.mkdir(parents=True)
    row = ROWS[0]
    name = assay.world_name(0, row["world_id"])
    dt = RULE["dt_s"][0]
    observed = np.array([1020, 1024]) * dt
    saved = dict(
        state__voltage=np.arange(1025, dtype=float)[:, None] * 1e-9,
        junction__open=np.ones((1025, 1)),
        observed__voltage=np.array([[1e-9], [2e-9]]),
    )
    np.savez_compressed(root / (name + ".npz"), **saved)
    (root / (name + ".json")).write_text(
        json.dumps(
            dict(
                status="passed",
                windows=[
                    dict(
                        file=name + ".npz",
                        start_step=0,
                        stop_step=1024,
                        observation_times=observed.tolist(),
                    )
                ],
            )
        )
    )
    monkeypatch.setitem(RULE, "historical_binding", {"root": str(tmp_path)})
    arrays = dict(
        state__voltage=np.arange(1020, 1029, dtype=float)[:, None] * 1e-9,
        junction__open=np.ones((9, 1)),
        observed__voltage=np.array([[1e-9], [2e-9], [999.0]]),
    )
    monkeypatch.setattr(reference, "arrays", lambda _: arrays)
    value = SimpleNamespace(
        start_step=1020,
        final=SimpleNamespace(
            step_index=1028, layout=SimpleNamespace(tissue_membrane_area=np.ones(1))
        ),
        observations=SimpleNamespace(times=np.array([1020, 1024, 1028]) * dt),
    )
    arrays["state__voltage"][5:] += 999
    result = compare_historical_window(value, row, 0)
    assert result["bitwise"] and result["stop_step"] == 1024 and result["compared_scalars"] == 12
    for key in ("state__voltage", "junction__open", "observed__voltage"):
        original = arrays[key].copy()
        arrays[key][0] += 1
        with pytest.raises(AssertionError):
            compare_historical_window(value, row, 0)
        arrays[key] = original
        assert compare_historical_window(value, row, 0)["bitwise"]
    value.start_step = 1024
    assert compare_historical_window(value, row, 0) is None
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            synthetic_known_answers=True,
            crossing_old_endpoint_clipped=True,
            shared_prefix_corruption_rejected=True,
            later_states_and_observations_not_compared_as_old=True,
        ),
    )


@pytest.fixture(scope="module")
def panel(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    jax.config.update("jax_enable_x64", True)
    assert jax.devices(BACKEND)
    archive = Path(EVIDENCE) / BACKEND if EVIDENCE else tmp_path_factory.mktemp(PREFIX)
    archive.mkdir(parents=True, exist_ok=True)
    maps = {(level, name): {} for level in range(3) for name in RULE["observation_panels"]}
    batches, prefixes, no_cue_refs = [], [], {}
    counts = dict(no_cue=0, unused_label_pairs=0, disconnected_windows=0)
    replay_rows = [r for r in ROWS if r["arm"] == "joint" and r["preparation"] == "calibration_low"]
    snapshot = archive / f"{PREFIX}-snapshot"
    maximum = 0.0
    for level in range(3):
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            selected = ROWS[start : start + RULE["batch_worlds"]]
            plan = assay.batch(BASE, selected, level, BACKEND, RULE)
            arm = selected[0]["arm"]
            assert len(selected) == 4 and all(r["arm"] == arm for r in selected)
            records = {
                w.world_id: dict(
                    status="running", case=row, input=w.simulation.to_dict(), windows=[]
                )
                for w, row in zip(plan.worlds, selected, strict=True)
            }
            observed = {row["world_id"]: [] for row in selected}
            for identity, record in records.items():
                (archive / (assay.world_name(level, identity) + ".json")).write_text(
                    json.dumps(record)
                )

            def sink(
                window,
                *,
                arm=arm,
                selected=selected,
                level=level,
                records=records,
                observed=observed,
            ):
                if arm in ("location_only", "timing_only"):
                    pairs = [(0, 1), (2, 3)] if arm == "location_only" else [(0, 2), (1, 3)]
                    for a, b in pairs:
                        reference.common.bits(
                            window.worlds[selected[a]["world_id"]].history,
                            window.worlds[selected[b]["world_id"]].history,
                        )
                        counts["unused_label_pairs"] += 1
                for identity, value in window.worlds.items():
                    assert len(value.history) == 14
                    arrays = reference.arrays(value)
                    if arm == "disconnected":
                        np.testing.assert_array_equal(value.history.junction_open[1:], 0)
                        np.testing.assert_array_equal(value.history.junction_outward_fmol, 0)
                        counts["disconnected_windows"] += 1
                    filename = f"{assay.world_name(level, identity)}-window-{window.index}.npz"
                    np.savez_compressed(archive / filename, **arrays)
                    records[identity]["windows"].append(
                        dict(
                            file=filename,
                            start_step=value.start_step,
                            stop_step=value.final.step_index,
                            observation_times=value.observations.times.tolist(),
                        )
                    )
                    observed[identity].append(
                        (
                            value.observations.times.copy(),
                            value.observations.membrane_voltage_V.copy(),
                        )
                    )
                    if arm == "no_cue":
                        key = level, window.index
                        if key in no_cue_refs:
                            with np.load(no_cue_refs[key], allow_pickle=False) as saved:
                                for k, actual in arrays.items():
                                    np.testing.assert_array_equal(actual, saved[k])
                            counts["no_cue"] += 1
                        else:
                            no_cue_refs[key] = archive / filename
                    historical = compare_historical_window(value, records[identity]["case"], level)
                    if historical is not None:
                        prefixes.append(historical)
                    if level == 2 and identity == replay_rows[1]["world_id"] and window.index == 1:
                        index = RULE["replay"]["snapshot_step"] - value.start_step
                        write_snapshot(
                            snapshot, value.spec, value.checkpoint_at(float(value.times[index]))
                        )
                    (archive / (assay.world_name(level, identity) + ".json")).write_text(
                        json.dumps(records[identity])
                    )

            actual = run_batch_windowed(plan, POLICY, sink=sink)
            batches.append(
                dict(
                    level=level,
                    arm=arm,
                    world_ids=[r["world_id"] for r in selected],
                    timings=actual.timings,
                    resources=actual.resources,
                )
            )
            for identity, result in actual.worlds.items():
                maximum = max(maximum, result.diagnostics["max_material_error_over_budget"])
                record = records[identity]
                record.update(status="passed", diagnostics=result.diagnostics)
                (archive / (assay.world_name(level, identity) + ".json")).write_text(
                    json.dumps(record)
                )
                observation = SimpleNamespace(
                    times=np.concatenate([v[0] for v in observed[identity]]),
                    membrane_voltage_V=np.concatenate([v[1] for v in observed[identity]]),
                )
                proxy = SimpleNamespace(
                    spec=result.spec, final=result.final, observations=observation
                )
                for name in RULE["observation_panels"]:
                    for mode, vector in assay.features(proxy, RULE, name).items():
                        maps[level, name].setdefault(mode, {})[identity] = vector.copy()
            del actual
    return dict(
        archive=archive,
        maps=maps,
        batches=batches,
        prefixes=prefixes,
        counts=counts,
        snapshot=snapshot,
        replay_rows=replay_rows,
        max_material_error_over_budget=maximum,
    )


def test_source_order_long_panel(panel):
    assert len(panel["batches"]) == 105
    assert sum(b["resources"]["executed_world_steps"] for b in panel["batches"]) == 2007040
    for arm in OLD["arms"]:
        assert (
            sum(b["resources"]["executed_world_steps"] for b in panel["batches"] if b["arm"] == arm)
            == 401408
        )
    assert all(len(values) == 140 for modes in panel["maps"].values() for values in modes.values())
    assert panel["max_material_error_over_budget"] <= 1
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=420,
            world_steps=2007040,
            batches=panel["batches"],
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_world_histories=0,
        ),
    )


@pytest.fixture(scope="module")
def readouts(panel):
    return assay.reader_reports(ROWS, panel["maps"], RULE)


def test_source_order_long_historical_reproduction(panel, readouts):
    histories = panel["prefixes"]
    assert len(histories) == 980
    assert len({(r["level"], r["world_id"]) for r in histories}) == 420
    old = predecessor.protocol()
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(old["duration_s"] / dt)
    root = Path(RULE["historical_binding"]["root"]) / "evidence" / BACKEND
    tol = reference.PROTOCOL["tolerances"]
    feature_count, exact_features = 0, True
    with np.load(root / "source-order-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            if name not in old["observation_panels"]:
                continue
            for mode, vectors in modes.items():
                for identity, value in vectors.items():
                    expected = saved[f"{level}__{name}__{mode}__{identity}"]
                    np.testing.assert_allclose(
                        value, expected, atol=tol["voltage_atol_V"], rtol=tol["cpu_gpu_rtol"]
                    )
                    feature_count += value.size
                    exact_features &= np.array_equal(value, expected)
    earlier = json.loads((root / "source-order-readouts.json").read_text())["panels"]
    # Exact feature reproduction entails exact replay of the unchanged deterministic
    # reader, its shuffles, cross-timestep scores and scientific decisions.
    assert exact_features
    assert {name: readouts[name] for name in old["observation_panels"]} == earlier
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            reproduced_world_prefixes=420,
            prefix_duration_s=old["duration_s"],
            history_comparisons=histories,
            bitwise_history_comparisons=sum(r["bitwise"] for r in histories),
            unchanged_feature_scalars=feature_count,
            unchanged_features_exact=exact_features,
            earlier_readout_reports_and_decisions_exact=True,
            archived_scientific_evidence_untouched=True,
        ),
    )


def test_source_order_long_readouts(panel, readouts):
    primary = readouts[RULE["primary_panel"]]["resolution_matched"][2]["outcomes"]["voltage"]
    joint = primary["arms"]["joint"]["joint"]
    assert primary["feature_count"] == 15 and joint["cases"] == 16
    drift = readouts[RULE["primary_panel"]]["score_stability"]["voltage"]["resolution_matched"][
        "cases"
    ]
    joint_drift = [r for r in drift if r["arm"] == "joint"]
    assert len(joint_drift) == 32
    evidence(
        f"{PREFIX}-readouts",
        dict(
            status="passed",
            panels=readouts,
            primary_joint_target_met=joint["all_cases_correct_and_resolved"],
            primary_joint_finest_score_stability=all(
                r["finest_steps_within_score_limits"] for r in joint_drift
            ),
            primary_joint_finest_decisions_agree=all(
                r["finest_decisions_agree"] for r in joint_drift
            ),
            task_meanings=RULE["task_meanings"],
            new_temporal_task=False,
            observation_only_followup=True,
            primary_panel=RULE["primary_panel"],
            preparations=RULE["preparations"],
            late_pulse_us=RULE["cue_timing"]["late_pulse_us"],
            primary_observations_after_both_cues=True,
            earlier_panels_may_precede_late_cue=True,
            scientific_outcome_is_not_an_acceptance_gate=True,
        ),
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, vectors in modes.items()
            for identity, value in vectors.items()
        },
    )


def test_source_order_long_contrasts(panel):
    contrasts = assay.paired_contrasts(ROWS, panel["maps"], RULE)
    assert len(contrasts) == 560
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


def test_source_order_long_controls(panel, readouts):
    assert panel["counts"] == dict(no_cue=378, unused_label_pairs=392, disconnected_windows=392)
    for modes in panel["maps"].values():
        for name in ("input_at_readout", "input_history"):
            for vector in modes[name].values():
                np.testing.assert_allclose(vector, 1, rtol=0, atol=4 * np.finfo(float).eps)
    for group in readouts.values():
        for level in group["resolution_matched"]:
            for mode, report in level["outcomes"].items():
                arms = (
                    report["arms"].values()
                    if mode.startswith("input")
                    else [report["arms"]["no_cue"]]
                )
                assert all(
                    t["metrics"]["resolved_fraction"] == 0
                    for arm in arms
                    for t in arm["tasks"].values()
                )
    evidence(
        f"{PREFIX}-controls",
        dict(
            status="passed",
            **panel["counts"],
            input_and_no_cue_readers_unresolved=True,
            disconnected_outcomes_not_forced=True,
        ),
    )


def compare_replayed(value, panel, identity):
    expected = assay.archived_segment(
        panel["archive"],
        2,
        identity,
        value.start_step,
        value.final.step_index,
        value.observations.times,
    )
    actual = reference.arrays(value)
    assert actual.keys() == expected.keys()
    for name, values in actual.items():
        np.testing.assert_array_equal(values, expected[name], err_msg=name)


def test_source_order_long_replay(panel):
    plan = assay.batch(BASE, panel["replay_rows"], 2, BACKEND, RULE)
    for worlds in (tuple(reversed(plan.worlds)), plan.worlds[:2], plan.worlds[2:]):
        for window in iter_batch_windows(replace(plan, worlds=worlds), POLICY):
            for identity, value in window.worlds.items():
                compare_replayed(value, panel, identity)
    first = panel["replay_rows"][1]["world_id"]
    assert assay.ordered(panel["replay_rows"][1])
    restored = load_snapshot(panel["snapshot"])
    assert restored.checkpoint.step_index == RULE["replay"]["snapshot_step"] == 1663
    assert restored.checkpoint.time * 1e6 == pytest.approx(103.9375, rel=0, abs=1e-12)
    for value in iter_windows(restored.spec, WindowPolicy(257, "full"), restored.checkpoint):
        compare_replayed(value, panel, first)
    evidence(
        f"{PREFIX}-replay",
        dict(
            status="passed",
            state_arrays=14,
            comparison="bitwise",
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=[1024, 257],
            snapshot_step=1663,
            snapshot_time_s=restored.checkpoint.time,
            crosses_second_source_on_and_off_events=True,
            long_history_and_observations=True,
        ),
    )


@pytest.fixture(scope="module")
def transfers(panel, readouts):
    return assay.reference_reports(ROWS, panel["maps"], readouts, RULE)


def test_source_order_long_baseline_transfer(transfers):
    evidence(f"{PREFIX}-baseline-transfer", transfers)


def test_source_order_long_cpu_gpu(panel, readouts, transfers):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU windows")
    assert EVIDENCE
    cpu = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count = 0
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
    tol = reference.PROTOCOL["tolerances"]
    cpu_voltages = {}
    with np.load(cpu / f"{PREFIX}-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for mode, vectors in modes.items():
                for identity, value in vectors.items():
                    np.testing.assert_allclose(
                        value,
                        saved[f"{level}__{name}__{mode}__{identity}"],
                        atol=tol["voltage_atol_V"],
                        rtol=tol["cpu_gpu_rtol"],
                    )
                    if mode == "voltage":
                        cpu_voltages[level, name, identity] = saved[
                            f"{level}__{name}__{mode}__{identity}"
                        ].copy()
    cpu_contrasts = json.loads((cpu / f"{PREFIX}-contrasts.json").read_text())["pairs"]
    contrast_differences, max_contrast_fraction = [], 0.0
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
        max_contrast_fraction = max(max_contrast_fraction, fraction)
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
            contrast_differences.append(
                dict(panel=name, task=actual["task"], world_ids=[a, b], differing_fields=fields)
            )
    previous_reports = json.loads((cpu / f"{PREFIX}-readouts.json").read_text())["panels"]
    comparisons = []
    for name, report in readouts.items():
        for level, actual in enumerate(report["resolution_matched"]):
            expected = previous_reports[name]["resolution_matched"][level]
            comparisons.append(
                dict(
                    panel=name,
                    level=level,
                    calibration="resolution_matched",
                    predictions=assay.compare_reader_predictions(
                        actual["outcomes"], expected["outcomes"]
                    ),
                    shuffle_joint_metrics_agreement=[
                        a["arms"]["joint"]["joint"] == b["arms"]["joint"]["joint"]
                        for a, b in zip(actual["shuffles"], expected["shuffles"], strict=True)
                    ],
                )
            )
        for level in range(3):
            comparisons.append(
                dict(
                    panel=name,
                    level=level,
                    calibration="frozen_coarse",
                    predictions=assay.compare_reader_predictions(
                        {m: values[level] for m, values in report["frozen_coarse"].items()},
                        {
                            m: values[level]
                            for m, values in previous_reports[name]["frozen_coarse"].items()
                        },
                    ),
                )
            )
    cpu_transfers = json.loads((cpu / f"{PREFIX}-baseline-transfer.json").read_text())
    reference_comparisons = []
    for actual, expected in zip(transfers["transfers"], cpu_transfers["transfers"], strict=True):
        assert (actual["source_level"], actual["target_level"]) == (
            expected["source_level"],
            expected["target_level"],
        )
        reference_comparisons.append(
            dict(
                source_level=actual["source_level"],
                target_level=actual["target_level"],
                predictions=assay.compare_reader_predictions(
                    {"voltage": actual["outcomes"]}, {"voltage": expected["outcomes"]}
                ),
            )
        )
    evidence(
        f"{PREFIX}-cpu-gpu",
        dict(
            status="passed",
            worlds=420,
            compared_scalars=count,
            max_paired_contrast_error_over_budget=max_contrast_fraction,
            paired_contrast_outcome_differences=contrast_differences,
            comparisons=comparisons,
            reference_assisted_comparisons=reference_comparisons,
            exact_decision_agreement=not any(
                p["differing_decision_world_ids"]
                for group in comparisons + reference_comparisons
                for p in group["predictions"]
            ),
            scientific_outcome_disagreements_are_reported=True,
            physical_tolerances_unchanged=True,
        ),
    )
