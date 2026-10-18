"""Windowed long observations with fixed cues, readers and physical tolerances."""

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
from tests.unit import test_distributed_timing as timing_checks
from tests.unit import test_unstimulated_readout as previous_checks
from validation.assays import distributed_timing, two_task
from validation.assays import long_observation as assay
from validation.assays import unstimulated_readout as previous

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases()
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence
POLICY = WindowPolicy(RULE["window_steps"], "full")
PREFIX = "long-observation"


def test_host_long_observation_design_and_resources():
    assert len(ROWS) == len({row["world_id"] for row in ROWS}) == 140
    assert ROWS == previous.cases(previous.protocol())
    assert RULE["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["duration_s"] == 256e-6 and not RULE["automatic_followup"]
    assert RULE["score_stability"] == distributed_timing.protocol()["reader_check"]["criteria"]
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
            source = previous.definition(BASE, row, BACKEND, previous.protocol())
            assert raw["model"] == source["model"] == BASE["model"]
            assert raw["experiment"]["changes"] == source["experiment"]["changes"]
            assert raw["execution"] == source["execution"] | {"dt": dt}
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
            np.testing.assert_array_equal(controls.channel[grid[:-1] >= 32 * OLD["dt_s"]], 1)
            amounts = [
                float(np.sum((1 - controls.channel[:, mask]) @ area[mask]) * dt)
                for mask in source_masks
            ]
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
            unchanged_cues_and_sources=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_long_observation_support():
    ids = np.array([4, 7, 2, 1, 5, 3, 6])
    owner, area = np.repeat(np.arange(7), 2), np.arange(1, 15, dtype=float)
    times = np.sort(
        np.concatenate([assay.times(RULE, panel) for panel in RULE["observation_panels"]])
    )
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
    voltage[:3] += 456
    for panel in ("middle128", "long256"):
        np.testing.assert_array_equal(
            assay.features(result, RULE, panel)["voltage"], saved[panel]["voltage"]
        )
    with pytest.raises(TypeError):
        assay.features(result, RULE, "long256", labels=[0, 1])
    evidence(
        f"{PREFIX}-support",
        dict(
            status="passed",
            panels=3,
            primary_features_each=15,
            unequal_area_weighting=True,
            physical_ids=True,
            source_and_unsampled_voltages_excluded=True,
        ),
    )


def test_host_long_observation_reader_isolation():
    previous_checks.test_host_unstimulated_reader_isolation()
    timing_checks.test_host_distributed_timing_score_drift_and_decision_changes()
    timing_checks.test_host_distributed_timing_nulls_and_invalid_reports()
    rows = [r for r in ROWS if r["arm"] == "joint"]
    maps = {}
    for level in range(3):
        for panel in RULE["observation_panels"]:
            v = {
                r["world_id"]: np.tile(
                    [
                        10e-6 * r["location"],
                        2e-6 * r["timing"] + level * 1.5e-6,
                        1e-6 * r["amplitude"],
                        0,
                        0,
                    ],
                    3,
                )
                for r in rows
            }
            maps[level, panel] = dict(
                voltage=v,
                final_voltage={k: a[-5:] for k, a in v.items()},
                all_cell_voltage={k: np.pad(a, (0, 6)) for k, a in v.items()},
                input_at_readout={k: np.ones(15) for k in v},
                input_history={k: np.ones(15) for k in v},
            )
    reports = assay.reader_reports(rows, maps, RULE)
    for panel in reports.values():
        assert all(
            r["outcomes"]["voltage"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
            for r in panel["resolution_matched"]
        )
        frozen = panel["frozen_coarse"]["voltage"]
        assert frozen[0] == panel["resolution_matched"][0]["outcomes"]["voltage"]
        assert frozen[2]["arms"]["joint"]["tasks"]["timing"]["metrics"]["forced_accuracy"] == 0.5
    evidence(
        f"{PREFIX}-reader-isolation",
        dict(
            status="passed",
            synthetic_known_answers=True,
            inherited_metadata_isolation=True,
            frozen_calibration_exposes_common_shift=True,
            scientific_stability_failure_is_reported=True,
        ),
    )


def test_host_long_observation_archive_boundaries(tmp_path):
    record = dict(status="passed", windows=[])
    for start, obs in ((0, [2, 4]), (4, [6, 8])):
        name = f"chunk-{start}.npz"
        np.savez_compressed(
            tmp_path / name,
            state__x=np.arange(start, start + 5)[:, None],
            observed__vm=np.asarray(obs)[:, None] * 10,
        )
        record["windows"].append(
            dict(file=name, start_step=start, stop_step=start + 4, observation_times=obs)
        )
    (tmp_path / (assay.world_name(2, 1) + ".json")).write_text(json.dumps(record))
    for start, stop, obs in ((3, 7, [4, 6]), (4, 4, [4]), (5, 8, [6, 8]), (0, 1, [])):
        actual = assay.archived_segment(tmp_path, 2, 1, start, stop, obs)
        np.testing.assert_array_equal(actual["state__x"], np.arange(start, stop + 1)[:, None])
        np.testing.assert_array_equal(actual["observed__vm"], np.asarray(obs)[:, None] * 10)
    with pytest.raises(AssertionError):
        assay.archived_segment(tmp_path, 2, 1, 3, 7, [3.5])
    evidence(
        f"{PREFIX}-archive",
        dict(
            status="passed",
            shared_endpoints_counted_once=True,
            arbitrary_cuts_and_empty_observations=True,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_long_observation_prerequisite(prior):
    evidence(f"{PREFIX}-prerequisite", prior)


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
                    if level == 2 and window.index == 0:
                        old = (
                            Path(RULE["historical_binding"]["root"])
                            / "evidence"
                            / BACKEND
                            / f"unstimulated-world-{identity}.npz"
                        )
                        assert value.final.step_index == 1024
                        with np.load(old, allow_pickle=False) as saved:
                            compared = reference.compare(
                                arrays, saved, value.final.layout.tissue_membrane_area
                            )
                            exact = all(np.array_equal(arrays[k], saved[k]) for k in arrays)
                        prefixes.append(
                            dict(world_id=identity, compared_scalars=compared, bitwise=exact)
                        )
                    if level == 2 and identity == replay_rows[0]["world_id"] and window.index == 1:
                        write_snapshot(
                            snapshot, value.spec, value.checkpoint_at(float(value.times[-2]))
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


def test_long_observation_panel(panel):
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


def test_long_observation_historical_reproduction(panel, readouts):
    assert len(panel["prefixes"]) == 140
    root = Path(RULE["historical_binding"]["root"]) / "evidence" / BACKEND
    old = json.loads((root / "unstimulated-readouts.json").read_text())
    actual = readouts["short64"]["resolution_matched"][2]
    differences = assay.compare_reader_predictions(actual["outcomes"], old["outcomes"])
    tol = reference.PROTOCOL["tolerances"]
    with np.load(root / "unstimulated-readouts.npz", allow_pickle=False) as saved:
        for mode, vectors in panel["maps"][2, "short64"].items():
            for identity, value in vectors.items():
                np.testing.assert_allclose(
                    value,
                    saved[f"{mode}__{identity}"],
                    atol=tol["voltage_atol_V"],
                    rtol=tol["cpu_gpu_rtol"],
                )
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            worlds=140,
            prefixes=panel["prefixes"],
            bitwise_worlds=sum(r["bitwise"] for r in panel["prefixes"]),
            reader_comparisons=differences,
            all_readout_reports_exact=actual["outcomes"] == old["outcomes"],
            all_shuffles_exact=actual["shuffles"] == old["shuffles"],
            archived_scientific_evidence_untouched=True,
        ),
    )


def test_long_observation_readouts(panel, readouts):
    primary = readouts["long256"]["resolution_matched"][2]["outcomes"]["voltage"]
    joint = primary["arms"]["joint"]["joint"]
    assert primary["feature_count"] == 15 and joint["cases"] == 16
    drift = readouts["long256"]["score_stability"]["voltage"]["resolution_matched"]["cases"]
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
            scientific_outcome_is_not_an_acceptance_gate=True,
        ),
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, vectors in modes.items()
            for identity, value in vectors.items()
        },
    )


def test_long_observation_contrasts(panel):
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


def test_long_observation_controls(panel, readouts):
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


def test_long_observation_replay(panel):
    plan = assay.batch(BASE, panel["replay_rows"], 2, BACKEND, RULE)
    for worlds in (tuple(reversed(plan.worlds)), plan.worlds[:2], plan.worlds[2:]):
        for window in iter_batch_windows(replace(plan, worlds=worlds), POLICY):
            for identity, value in window.worlds.items():
                compare_replayed(value, panel, identity)
    first = panel["replay_rows"][0]["world_id"]
    restored = load_snapshot(panel["snapshot"])
    assert restored.checkpoint.step_index == 2047
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
            snapshot_step=2047,
            snapshot_time_s=restored.checkpoint.time,
            long_history_and_observations=True,
        ),
    )


def test_long_observation_cpu_gpu(panel, readouts):
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
