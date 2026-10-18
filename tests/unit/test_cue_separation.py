"""Fixed-dose late-pulse separation with unchanged readers and physical tolerances."""

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
from tests.unit import test_betse_junction_runtime as reference
from tests.unit import test_long_observation as inherited_checks
from validation.assays import cue_separation as assay
from validation.assays import distributed_timing, long_observation, two_task
from validation.assays import unstimulated_readout as previous

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases()
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence
POLICY = WindowPolicy(RULE["window_steps"], "full")
PREFIX = "cue-separation"


def test_host_cue_separation_design_and_resources():
    assert len(ROWS) == len({row["world_id"] for row in ROWS}) == 140
    assert ROWS == previous.cases(previous.protocol())
    assert RULE["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["duration_s"] == 256e-6 and not RULE["automatic_followup"]
    assert RULE["score_stability"] == distributed_timing.protocol()["reader_check"]["criteria"]
    assert RULE["cue_timing"]["onset_separation_us"] == 96
    assert sum(assay.shifted(row) for row in ROWS) == 42
    assert np.all(assay.times(RULE, "long256") > 112 * OLD["dt_s"])
    for panel in RULE["observation_panels"]:
        np.testing.assert_allclose(
            assay.times(RULE, panel) * 1e6, RULE["observation_times_us"][panel], atol=1e-12, rtol=0
        )
    original = copy.deepcopy(BASE)
    plans, doses, archive_estimate = [], [], 0
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    source_masks = [owner == identity - 1 for identity in OLD["source_cell_ids"]]
    ref_area = min(area[mask].sum() for mask in source_masks)
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            source = long_observation.definition(
                BASE, row, level, BACKEND, long_observation.protocol()
            )
            assert raw["model"] == source["model"] == BASE["model"]
            assert raw["execution"] == source["execution"]
            assert {k: v for k, v in raw["experiment"].items() if k != "changes"} == {
                k: v for k, v in source["experiment"].items() if k != "changes"
            }
            if not assay.shifted(row):
                assert raw == source
            else:
                assert len(raw["experiment"]["changes"]) == 7
            spec = parse_spec(raw)
            grid = np.asarray(list(checked_grid(spec)))
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            assert len(spec.experiment.observation_times) == 9
            controls = control_values(spec, grid[:-1])
            assert np.all((controls.channel >= 0) & (controls.channel <= 1))
            np.testing.assert_array_equal(controls.pump, 1)
            np.testing.assert_array_equal(
                controls.junction, 0 if row["arm"] == "disconnected" else 1
            )
            np.testing.assert_array_equal(
                controls.channel[:, ~(source_masks[0] | source_masks[1])], 1
            )
            # Independently construct the entire expected control grid, including
            # both event boundaries and each source's area-normalized dose.
            cue = RULE["cue_timing"]
            pulse = (
                cue["location_only_pulse_us"]
                if row["arm"] == "location_only"
                else cue["late_pulse_us"]
                if row["timing"]
                else cue["early_pulse_us"]
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
            expected_controls = np.ones_like(controls.channel)
            start, stop = [round(t * OLD["dt_s"] / dt) for t in pulse]
            for weight, mask in zip(weights, source_masks, strict=True):
                expected_controls[start:stop, mask] = (
                    1 - row["amplitude"] * weight * ref_area / area[mask].sum()
                )
            np.testing.assert_allclose(controls.channel, expected_controls, rtol=0, atol=4e-16)
            np.testing.assert_array_equal(controls.channel[grid[:-1] >= 112 * OLD["dt_s"]], 1)
            amounts = [
                float(np.sum((1 - controls.channel[:, mask]) @ area[mask]) * dt)
                for mask in source_masks
            ]
            original_controls = control_values(parse_spec(source), grid[:-1])
            original_amounts = [
                float(np.sum((1 - original_controls.channel[:, mask]) @ area[mask]) * dt)
                for mask in source_masks
            ]
            np.testing.assert_allclose(amounts, original_amounts, rtol=2e-14, atol=1e-30)
            expected = 0 if row["arm"] == "no_cue" else row["amplitude"] * ref_area * 8e-6
            assert sum(amounts) == pytest.approx(expected, rel=2e-14, abs=1e-30)
            doses.append(dict(level=level, world_id=row["world_id"], source_doses_m2_s=amounts))
        flat, layout = reference.model.initial_values(spec)
        per_state = sum(np.asarray(v).nbytes for v in flat)
        p = reference.model.parameters(spec, layout)
        fields = reference.kernel.passive.field(
            reference.model.unflatten(flat).active.tissue, p.active.tissue, xp=np
        )
        field_bytes = sum(np.asarray(v).nbytes for v in fields)
        windows = steps // RULE["window_steps"]
        # Both backends; every window includes its shared endpoint.
        archive_estimate += 2 * len(ROWS) * (per_state * (steps + windows) + field_bytes * 9)
        for start in range(0, len(ROWS), RULE["batch_worlds"]):
            plan = assay.batch(
                BASE, ROWS[start : start + RULE["batch_worlds"]], level, BACKEND, RULE
            )
            bounded = plan_batch_windows(plan, POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in plan.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    assert BASE == original
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 9)
    retained += len(ROWS) * 3 * 3 * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 4 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 105 and max(p["estimated_working_bytes"] for p in plans) < 4 * 1024**3
    for bad in (-1, 3, True):
        with pytest.raises(ValueError, match="Unregistered timestep"):
            assay.definition(BASE, ROWS[0], bad, BACKEND, RULE)
    invalid = copy.deepcopy(RULE)
    invalid["cue_timing"]["late_pulse_us"] = [104, 113]
    with pytest.raises(ValueError, match="registered fixed-dose"):
        assay.definition(BASE, next(r for r in ROWS if assay.shifted(r)), 2, BACKEND, invalid)
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            cases=ROWS,
            plans=plans,
            integrated_doses=doses,
            dt_s=RULE["dt_s"],
            observations_us=RULE["observation_times_us"],
            new_worlds_per_backend=420,
            world_steps_per_backend=1003520,
            steps_per_arm=200704,
            retained_array_estimate_bytes=retained,
            uncompressed_arrays_both_backends_bytes=archive_estimate,
            unchanged_sources_and_per_source_doses=True,
            changed_late_cue_cases=42,
            unchanged_case_inputs=98,
            late_pulse_us=RULE["cue_timing"]["late_pulse_us"],
            primary_observations_follow_both_cues=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_cue_separation_support():
    inherited_checks.test_host_long_observation_support()
    evidence(f"{PREFIX}-support", dict(status="passed", reused_unchanged_support_check=True))


def test_host_cue_separation_reader_isolation():
    inherited_checks.test_host_long_observation_reader_isolation()
    evidence(f"{PREFIX}-reader-isolation", dict(status="passed", reused_known_answers=True))


def test_host_cue_separation_archive_boundaries(tmp_path):
    inherited_checks.test_host_long_observation_archive_boundaries(tmp_path)
    evidence(f"{PREFIX}-archive", dict(status="passed", reused_archive_boundary_check=True))


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_cue_separation_prerequisite(prior):
    evidence(f"{PREFIX}-prerequisite", prior)


def compare_historical_window(value, row, level):
    """Unchanged worlds retain full comparisons; changed worlds retain their prefix."""
    changed = assay.shifted(row)
    if changed and value.start_step != 0:
        return None
    stop = round(24 * OLD["dt_s"] / RULE["dt_s"][level]) - 1 if changed else value.final.step_index
    observed = [] if changed else value.observations.times
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    saved = long_observation.archived_segment(
        root, level, row["world_id"], value.start_step, stop, observed
    )
    actual = reference.arrays(value)
    if changed:
        actual = {
            name: a[:0] if name.startswith("observed__") else a[: stop + 1]
            for name, a in actual.items()
        }
    count = reference.compare(actual, saved, value.final.layout.tissue_membrane_area)
    return dict(
        level=level,
        world_id=row["world_id"],
        kind="common_prefix" if changed else "unchanged_input",
        start_step=value.start_step,
        stop_step=stop,
        compared_scalars=count,
        bitwise=all(np.array_equal(actual[k], saved[k]) for k in actual),
    )


def test_host_cue_separation_history_boundaries(tmp_path, monkeypatch):
    """A late response may differ; its common prefix and unchanged controls may not."""
    root = tmp_path / "evidence" / BACKEND
    root.mkdir(parents=True)
    observed = np.array([40, 48, 64]) * OLD["dt_s"]
    saved = dict(
        state__voltage=np.arange(1025, dtype=float)[:, None] * 1e-9,
        junction__open=np.ones((1025, 1)),
        observed__voltage=np.arange(3, dtype=float)[:, None] * 1e-9,
    )
    rows = [ROWS[0], next(r for r in ROWS if assay.shifted(r))]
    for row in rows:
        name = assay.world_name(2, row["world_id"])
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
    monkeypatch.setitem(RULE, "prior_binding", {"root": str(tmp_path)})
    arrays = {k: v.copy() for k, v in saved.items()}
    monkeypatch.setattr(reference, "arrays", lambda _: arrays)
    value = SimpleNamespace(
        start_step=0,
        final=SimpleNamespace(
            step_index=1024,
            layout=SimpleNamespace(tissue_membrane_area=np.ones(1)),
        ),
        observations=SimpleNamespace(times=observed),
    )
    unchanged = compare_historical_window(value, rows[0], 2)
    assert unchanged["bitwise"] and unchanged["stop_step"] == 1024
    arrays["state__voltage"][384:] += 1
    arrays["observed__voltage"] += 1
    prefix = compare_historical_window(value, rows[1], 2)
    assert prefix["bitwise"] and prefix["stop_step"] == 383
    assert prefix["compared_scalars"] == 768
    with pytest.raises(AssertionError):
        compare_historical_window(value, rows[0], 2)
    arrays["state__voltage"][0] += 1
    with pytest.raises(AssertionError):
        compare_historical_window(value, rows[1], 2)
    value.start_step = 1024
    assert compare_historical_window(value, rows[1], 2) is None
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            synthetic_known_answers=True,
            shifted_post_prefix_changes_allowed=True,
            unchanged_and_common_prefix_corruption_rejected=True,
            empty_observations_and_later_windows_checked=True,
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


def test_cue_separation_panel(panel):
    assert len(panel["batches"]) == 105
    assert sum(b["resources"]["executed_world_steps"] for b in panel["batches"]) == 1003520
    for arm in OLD["arms"]:
        assert (
            sum(b["resources"]["executed_world_steps"] for b in panel["batches"] if b["arm"] == arm)
            == 200704
        )
    assert all(len(values) == 140 for modes in panel["maps"].values() for values in modes.values())
    assert panel["max_material_error_over_budget"] <= 1
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=420,
            world_steps=1003520,
            batches=panel["batches"],
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_world_histories=0,
        ),
    )


@pytest.fixture(scope="module")
def readouts(panel):
    return assay.reader_reports(ROWS, panel["maps"], RULE)


def test_cue_separation_historical_reproduction(panel, readouts):
    histories = panel["prefixes"]
    full = [r for r in histories if r["kind"] == "unchanged_input"]
    common = [r for r in histories if r["kind"] == "common_prefix"]
    assert len(full) == 686 and len(common) == 126
    assert len({(r["level"], r["world_id"]) for r in full}) == 294
    assert len({(r["level"], r["world_id"]) for r in common}) == 126
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
            assert windows[-1]["stop_step"] == (
                round(24 * OLD["dt_s"] / dt) - 1
                if assay.shifted(row)
                else round(RULE["duration_s"] / dt)
            )
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    old = json.loads((root / "long-observation-readouts.json").read_text())
    tol = reference.PROTOCOL["tolerances"]
    unchanged = {r["world_id"] for r in ROWS if not assay.shifted(r)}
    feature_count, exact_features = 0, True
    with np.load(root / "long-observation-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for mode, vectors in modes.items():
                for identity in unchanged:
                    value, expected = (
                        vectors[identity],
                        saved[f"{level}__{name}__{mode}__{identity}"],
                    )
                    np.testing.assert_allclose(
                        value, expected, atol=tol["voltage_atol_V"], rtol=tol["cpu_gpu_rtol"]
                    )
                    feature_count += value.size
                    exact_features &= np.array_equal(value, expected)
    reader_checks = []
    for name, reports in readouts.items():
        for level, matched in enumerate(reports["resolution_matched"]):
            before = old["panels"][name]["resolution_matched"][level]["outcomes"]
            for mode, report in matched["outcomes"].items():
                for arm in ("location_only", "no_cue"):
                    reader_checks.append(
                        dict(
                            panel=name,
                            level=level,
                            mode=mode,
                            arm=arm,
                            reports_exact=report["arms"][arm] == before[mode]["arms"][arm],
                        )
                    )
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            unchanged_full_worlds=294,
            changed_world_common_prefixes=126,
            history_comparisons=histories,
            bitwise_history_comparisons=sum(r["bitwise"] for r in histories),
            unchanged_feature_scalars=feature_count,
            unchanged_features_exact=exact_features,
            unchanged_arm_readers=reader_checks,
            unchanged_arm_readers_exact=all(r["reports_exact"] for r in reader_checks),
            changed_timing_response_not_compared_as_if_unchanged=True,
            archived_scientific_evidence_untouched=True,
        ),
    )


def test_cue_separation_readouts(panel, readouts):
    primary = readouts["long256"]["resolution_matched"][2]["outcomes"]["voltage"]
    joint = primary["arms"]["joint"]["joint"]
    assert primary["feature_count"] == 15 and joint["cases"] == 16
    drift = readouts["long256"]["score_stability"]["voltage"]["resolution_matched"]["cases"]
    joint_drift = [r for r in drift if r["arm"] == "joint"]
    assert len(joint_drift) == 32
    prior_path = (
        Path(RULE["prior_binding"]["root"])
        / "evidence"
        / BACKEND
        / "long-observation-readouts.json"
    )
    prior_joint = json.loads(prior_path.read_text())["panels"]["long256"]["resolution_matched"][2][
        "outcomes"
    ]["voltage"]["arms"]["joint"]
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
            prior_primary_joint_metrics=prior_joint["joint"],
            prior_primary_task_metrics={k: v["metrics"] for k, v in prior_joint["tasks"].items()},
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


def test_cue_separation_contrasts(panel):
    contrasts = assay.paired_contrasts(ROWS, panel["maps"], RULE)
    assert len(contrasts) == 420
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


def test_cue_separation_controls(panel, readouts):
    assert panel["counts"] == dict(no_cue=189, unused_label_pairs=196, disconnected_windows=196)
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


def test_cue_separation_replay(panel):
    plan = assay.batch(BASE, panel["replay_rows"], 2, BACKEND, RULE)
    for worlds in (tuple(reversed(plan.worlds)), plan.worlds[:2], plan.worlds[2:]):
        for window in iter_batch_windows(replace(plan, worlds=worlds), POLICY):
            for identity, value in window.worlds.items():
                compare_replayed(value, panel, identity)
    first = panel["replay_rows"][1]["world_id"]
    assert assay.shifted(panel["replay_rows"][1])
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
            crosses_delayed_on_and_off_events=True,
            long_history_and_observations=True,
        ),
    )


def test_cue_separation_cpu_gpu(panel, readouts):
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
    evidence(
        f"{PREFIX}-cpu-gpu",
        dict(
            status="passed",
            worlds=420,
            compared_scalars=count,
            max_paired_contrast_error_over_budget=max_contrast_fraction,
            paired_contrast_outcome_differences=contrast_differences,
            comparisons=comparisons,
            exact_decision_agreement=not any(
                p["differing_decision_world_ids"]
                for group in comparisons
                for p in group["predictions"]
            ),
            scientific_outcome_disagreements_are_reported=True,
            physical_tolerances_unchanged=True,
        ),
    )
