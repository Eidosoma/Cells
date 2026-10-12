"""Fresh fixed-support readout, streamed trajectories and inherited checks."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

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
from validation.assays import distributed_cue, distributed_timing, template_readout, two_task
from validation.assays import unstimulated_readout as assay

RULE, OLD = assay.protocol(), two_task.protocol()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
ROWS = assay.cases(RULE)
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence
PREFIX = "unstimulated"


def world_name(identity):
    return f"{PREFIX}-world-{identity}"


def test_host_unstimulated_design_and_resources():
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 140
    inspected = (
        two_task.cases(OLD)
        + template_readout.cases(template_readout.protocol())
        + distributed_cue.cases(distributed_cue.protocol())
    )
    fresh = {r["amplitude"] for r in ROWS if r["split"] == "heldout"}
    assert fresh == {0.4375, 0.5625, 0.6375, 0.7625}
    assert fresh.isdisjoint(r["amplitude"] for r in inspected)
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in inspected)
    assert RULE["dt_s"] == 0.0625e-6 and RULE["duration_s"] == 64e-6
    assert RULE["cue"] == distributed_cue.protocol()["cue"]
    assert RULE["readout"]["cell_ids"] == [2, 3, 5, 6, 7]
    assert RULE["readout"]["excluded_source_cell_ids"] == OLD["source_cell_ids"] == [1, 4]
    assert RULE["readout"]["all_cell_ids"] == OLD["readout_cell_ids"] == list(range(1, 8))
    assert not RULE["automatic_followup"]
    for arm in OLD["arms"]:
        tasks, training, testing = template_readout.split(ROWS, arm)
        assert len(training) == (6 if len(tasks) == 1 else 12)
        assert len(testing) == (8 if len(tasks) == 1 else 16)
        assert {r["amplitude"] for r in training} == {0.4, 0.6, 0.8}
        assert {tuple(r[t] for t in tasks) for r in training} == {
            tuple(r[t] for t in tasks) for r in testing
        }
    tissue = BASE["model"]["tissue"]
    area, owner = map(np.asarray, (tissue["membrane_area"], tissue["cell_owner"]))
    masks = [owner == i - 1 for i in OLD["source_cell_ids"]]
    reference_area = min(area[mask].sum() for mask in masks)
    original_base = copy.deepcopy(BASE)
    doses = []
    for row in ROWS:
        raw = assay.definition(BASE, row, BACKEND, RULE)
        assert raw["model"] == BASE["model"]
        assert {"world_id", "location", "timing", "amplitude", "preparation", "split"}.isdisjoint(
            raw
        )
        spec = parse_spec(raw)
        grid = timeline(spec)
        assert len(grid) == 1025 and grid[-1] == RULE["duration_s"]
        np.testing.assert_allclose(
            spec.experiment.observation_times, RULE["readout"]["times_s"], rtol=0, atol=1e-20
        )
        controls = control_values(spec, grid[:-1])
        assert np.all((controls.channel >= 0) & (controls.channel <= 1))
        shares = (
            [0, 0]
            if row["arm"] == "no_cue"
            else [0.5, 0.5]
            if row["arm"] == "timing_only"
            else [0.75, 0.25]
            if row["location"] == 0
            else [0.25, 0.75]
        )
        begin, end = (
            (16e-6, 24e-6)
            if row["arm"] == "location_only"
            else (8e-6, 16e-6)
            if row["timing"] == 0
            else (24e-6, 32e-6)
        )
        active = (grid[:-1] >= begin) & (grid[:-1] < end)
        source_doses = []
        for share, mask in zip(shares, masks, strict=True):
            amount = (1 - controls.channel[:, mask]) @ area[mask]
            np.testing.assert_allclose(
                amount / reference_area, row["amplitude"] * share * active, atol=1e-15, rtol=2e-14
            )
            source_doses.append(float(amount.sum() * RULE["dt_s"]))
        expected = 0 if row["arm"] == "no_cue" else row["amplitude"] * reference_area * 8e-6
        assert sum(source_doses) == pytest.approx(expected, rel=2e-14, abs=1e-30)
        np.testing.assert_array_equal(controls.channel[:, ~(masks[0] | masks[1])], 1)
        np.testing.assert_array_equal(controls.pump, 1)
        np.testing.assert_array_equal(controls.junction, 0 if row["arm"] == "disconnected" else 1)
        for steps in (OLD["readout_steps"], OLD["input_history_steps"]):
            np.testing.assert_allclose(
                two_task.input_features(spec, steps, assay.observation_rule(RULE)),
                1,
                atol=4 * np.finfo(float).eps,
                rtol=0,
            )
        doses.append(dict(world_id=row["world_id"], source_doses_m2_s=source_doses))
    assert BASE == original_base
    with pytest.raises(ValueError, match="Unregistered"):
        assay.definition(BASE, ROWS[0] | {"amplitude": 0.99}, BACKEND, RULE)
    # Fixed geometry and length: bound batch, retained replay and temporaries
    # by sixteen world equivalents with two copies of every state/field array.
    flat, layout = reference.model.initial_values(spec)
    parameters = reference.model.parameters(spec, layout)
    fields = reference.kernel.passive.field(
        reference.model.unflatten(flat).active.tissue, parameters.active.tissue, xp=np
    )
    observations = len(spec.experiment.observation_times)
    per_world = 2 * (
        sum(np.asarray(v).nbytes for v in flat) * (1025 + observations + 2)
        + sum(np.asarray(v).nbytes for v in fields) * observations
        + sum(np.asarray(v).nbytes for v in layout)
        + 8 * (1025 + observations)
    )
    retained = 16 * per_world + 140 * (15 + 5 + 21 + 15 + 15) * 8
    archive_estimate = 140 * per_world
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
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
    windows = plan_batch_windows(plan, WindowPolicy(127))
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            cases=ROWS,
            worlds_per_backend=140,
            calibration_strengths=[0.4, 0.6, 0.8],
            fresh_evaluation_strengths=sorted(fresh),
            dt_s=RULE["dt_s"],
            steps_per_arm=28672,
            total_world_steps=143360,
            allocation_plans=plans,
            integrated_doses=doses,
            retained_array_estimate_bytes=retained,
            uncompressed_array_estimate_both_backends_bytes=archive_estimate,
            window_estimated_working_bytes=windows.estimated_working_bytes,
            source_cells_excluded=True,
            reader_inputs_unstimulated_throughout=True,
            no_simulation_during_preflight=True,
            independent_biological_replicates=0,
        ),
    )


def test_host_unstimulated_observation_support():
    # Nontrivial storage order, unequal membrane areas and extra times expose
    # accidental positional selection, unweighted means and history leakage.
    ids = np.array([4, 7, 2, 1, 5, 3, 6])
    owner = np.repeat(np.arange(7), 2)
    area = np.arange(1, 15, dtype=float)
    times = np.array([0.0] + [step * OLD["dt_s"] for step in OLD["readout_steps"]])
    voltage = np.arange(len(times) * len(owner), dtype=float).reshape(len(times), -1) * 1e-6
    layout = SimpleNamespace(ids=ids, tissue_cell_owner=owner, tissue_membrane_area=area)
    result = SimpleNamespace(
        final=SimpleNamespace(layout=layout),
        observations=SimpleNamespace(times=times, membrane_voltage_V=voltage),
    )
    before = voltage.copy()
    actual = assay.voltage_features(result, RULE)
    expected = []
    for time in range(1, 4):
        for identity in RULE["readout"]["cell_ids"]:
            columns = np.flatnonzero(ids[owner] == identity)
            expected.append(sum(voltage[time, c] * area[c] for c in columns) / area[columns].sum())
    np.testing.assert_allclose(actual, expected, atol=1e-20, rtol=0)
    np.testing.assert_array_equal(voltage, before)
    all_cells = assay.voltage_features(result, RULE, all_cells=True)
    np.testing.assert_array_equal(actual, all_cells.reshape(3, 7)[:, [1, 2, 4, 5, 6]].reshape(-1))
    assert actual.shape == (15,) and not actual.flags.writeable
    voltage[:, np.isin(ids[owner], [1, 4])] += 123.0
    voltage[0] -= 456.0
    np.testing.assert_array_equal(assay.voltage_features(result, RULE), actual)
    assert not np.array_equal(assay.voltage_features(result, RULE, all_cells=True), all_cells)
    voltage[1, np.flatnonzero(ids[owner] == 2)[0]] += 1.0
    assert not np.array_equal(assay.voltage_features(result, RULE), actual)
    with pytest.raises(TypeError):
        assay.voltage_features(result, RULE, labels=[0, 1])
    evidence(
        f"{PREFIX}-observation-support",
        dict(
            status="passed",
            cell_ids=RULE["readout"]["cell_ids"],
            features=15,
            source_voltage_changes_invisible=True,
            unsampled_times_invisible=True,
            unequal_area_weighting=True,
            nonpositional_physical_ids=True,
            selected_voltage_changes_visible=True,
            metadata_argument_rejected=True,
        ),
    )


def test_host_unstimulated_reader_isolation():
    rows = [r for r in ROWS if r["arm"] == "joint"]
    voltage = {
        r["world_id"]: np.tile(
            [2e-6 * r["location"], 1e-6 * r["timing"], 1e-6 * r["amplitude"], 0, 0], 3
        )
        for r in rows
    }
    modes = dict(
        voltage=voltage,
        final_voltage={k: v[-5:] for k, v in voltage.items()},
        all_cell_voltage={k: np.pad(v, (0, 6)) for k, v in voltage.items()},
        input_at_readout={k: np.ones(15) for k in voltage},
        input_history={k: np.ones(15) for k in voltage},
    )
    reports, shuffles = assay.reader_reports(rows, modes, RULE)
    assert reports["voltage"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    changed_comparator = modes | {"all_cell_voltage": {k: np.zeros(21) for k in voltage}}
    other, other_shuffles = assay.reader_reports(rows, changed_comparator, RULE)
    assert reports["voltage"] == other["voltage"] and shuffles == other_shuffles
    assert not other["all_cell_voltage"]["arms"]["joint"]["joint"]["all_cases_correct_and_resolved"]
    changed = [
        r
        if r["split"] == "calibration"
        else r
        | {
            "location": 1 - r["location"],
            "timing": 1 - r["timing"],
            "amplitude": 0.49,
            "preparation": "irrelevant-metadata",
            "world_id": r["world_id"] + 900000,
        }
        for r in rows
    ]
    renamed = {
        new["world_id"]: voltage[old["world_id"]] for old, new in zip(rows, changed, strict=True)
    }
    relabelled = template_readout.evaluate(
        changed, renamed, margin=RULE["reader"]["voltage_margin_V"]
    )
    before, after = (r["arms"]["joint"] for r in (reports["voltage"], relabelled))
    assert before["calibration"] == after["calibration"]
    for task in ("location", "timing"):
        for first, second in zip(
            before["tasks"][task]["predictions"], after["tasks"][task]["predictions"], strict=True
        ):
            assert all(first[k] == second[k] for k in ("score", "prediction", "resolved"))
            assert first["target"] != second["target"]
    evidence(
        f"{PREFIX}-reader-isolation",
        dict(
            status="passed",
            synthetic_known_answers=True,
            all_cell_comparator_cannot_change_primary=True,
            changed_evaluation_labels_strengths_ids_cannot_change_predictions=True,
            scientific_responses_inspected=False,
        ),
    )


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_unstimulated_prerequisite(prior):
    evidence(f"{PREFIX}-prerequisite", prior)


@pytest.fixture(scope="module")
def panel(prior, tmp_path_factory):
    assert prior["status"] == "passed"
    jax.config.update("jax_enable_x64", True)
    archive = Path(EVIDENCE) / BACKEND if EVIDENCE else tmp_path_factory.mktemp(PREFIX)
    archive.mkdir(parents=True, exist_ok=True)
    replay_ids = {
        row["world_id"]
        for row in ROWS
        if row["arm"] == "joint" and row["preparation"] == "calibration_low"
    }
    modes, replay, batches = {}, {}, []
    maximum, no_cue_comparisons, duplicate_pairs, disconnected = 0.0, 0, 0, 0
    no_cue_reference = None
    for start in range(0, len(ROWS), RULE["batch_worlds"]):
        selected = ROWS[start : start + RULE["batch_worlds"]]
        actual = run_batch(assay.batch(BASE, selected, BACKEND, RULE))
        arm = selected[0]["arm"]
        assert len(selected) == 4 and all(r["arm"] == arm for r in selected)
        batches.append(
            dict(
                arm=arm,
                world_ids=[r["world_id"] for r in selected],
                timings=actual.timings,
                resources=actual.resources,
            )
        )
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
            if arm == "disconnected":
                np.testing.assert_array_equal(result.history.junction_open[1:], 0)
                np.testing.assert_array_equal(result.history.junction_outward_fmol, 0)
                disconnected += 1
            values = reference.arrays(result)
            if arm == "no_cue":
                if no_cue_reference is None:
                    no_cue_reference = archive / (world_name(identity) + ".npz")
                else:
                    with np.load(no_cue_reference, allow_pickle=False) as saved:
                        assert set(saved) == set(values)
                        for name, value in values.items():
                            np.testing.assert_array_equal(value, saved[name])
                    no_cue_comparisons += 1
            name = world_name(identity)
            (archive / (name + ".json")).write_text(
                json.dumps(
                    dict(
                        status="passed",
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
            for mode, vector in assay.features(result, RULE).items():
                modes.setdefault(mode, {})[identity] = vector.copy()
            if identity in replay_ids:
                replay[identity] = result
            del values, result
        del actual
    return dict(
        archive=archive,
        modes=modes,
        replay=replay,
        batches=batches,
        max_material_error_over_budget=maximum,
        no_cue_comparisons=no_cue_comparisons,
        duplicate_pairs=duplicate_pairs,
        disconnected_worlds=disconnected,
    )


def test_unstimulated_panel(panel):
    assert len(panel["replay"]) == 4
    for mode, vectors in panel["modes"].items():
        size = 21 if mode == "all_cell_voltage" else 5 if mode == "final_voltage" else 15
        assert len(vectors) == 140
        assert all(v.shape == (size,) and np.isfinite(v).all() for v in vectors.values())
    batches = panel["batches"]
    assert len(batches) == 35
    assert all(b["resources"]["executed_world_steps"] == 4096 for b in batches)
    assert sum(b["resources"]["executed_world_steps"] for b in batches) == 143360
    assert all(
        sum(b["resources"]["executed_world_steps"] for b in batches if b["arm"] == arm) == 28672
        for arm in OLD["arms"]
    )
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=140,
            batches=batches,
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_history_worlds=4,
        ),
    )


def test_unstimulated_calibration_reproduction(panel):
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    checked, compared, exact = [], 0, 0
    for row in ROWS:
        if row["split"] != "calibration":
            continue
        old = next(
            r
            for r in distributed_timing.cases()
            if all(r[k] == row[k] for k in ("arm", "amplitude", "location", "timing", "split"))
        )
        name = f"distributed-timing-world-2-{old['world_id']}"
        current_name = world_name(row["world_id"])
        historical = json.loads((root / (name + ".json")).read_text())
        current = json.loads((panel["archive"] / (current_name + ".json")).read_text())
        assert current["input"] == historical["input"]
        with (
            np.load(panel["archive"] / (current_name + ".npz"), allow_pickle=False) as actual,
            np.load(root / (name + ".npz"), allow_pickle=False) as saved,
        ):
            compared += reference.compare(actual, saved, area)
            identical = all(np.array_equal(actual[k], saved[k]) for k in actual)
            exact += int(identical)
        checked.append(
            dict(world_id=row["world_id"], prior_world_id=old["world_id"], bitwise=identical)
        )
    assert len(checked) == RULE["historical_reproduction"]["worlds"] == 60
    evidence(
        f"{PREFIX}-calibration-reproduction",
        dict(
            status="passed",
            worlds=60,
            cases=checked,
            compared_values=compared,
            bitwise_worlds=exact,
            physical_inputs_match=True,
            physical_tolerances_unchanged=True,
        ),
    )


@pytest.fixture(scope="module")
def readouts(panel):
    return assay.reader_reports(ROWS, panel["modes"], RULE)


def test_unstimulated_readouts(panel, readouts):
    reports, shuffles = readouts
    assert set(reports) == set(RULE["reader"]["modes"]) and len(shuffles) == 32
    for report in reports.values():
        for arm, detail in report["arms"].items():
            tasks, training, testing = template_readout.split(ROWS, arm)
            assert detail["calibration"]["world_ids"] == [r["world_id"] for r in training]
            for task in tasks:
                assert [r["world_id"] for r in detail["tasks"][task]["predictions"]] == [
                    r["world_id"] for r in testing
                ]
    primary = reports["voltage"]["arms"]["joint"]["joint"]
    assert primary["cases"] == 16 and reports["voltage"]["feature_count"] == 15
    evidence(
        f"{PREFIX}-readouts",
        dict(
            status="passed",
            outcomes=reports,
            shuffles=shuffles,
            dt_s=RULE["dt_s"],
            primary_cell_ids=RULE["readout"]["cell_ids"],
            primary_joint_target_met=primary["all_cases_correct_and_resolved"],
            scientific_success_is_not_an_acceptance_gate=True,
            independent_biological_replicates=0,
        ),
        {
            f"{mode}__{identity}": value
            for mode, values in panel["modes"].items()
            for identity, value in values.items()
        },
    )


def test_unstimulated_controls(panel, readouts):
    assert panel["no_cue_comparisons"] == 27
    assert panel["duplicate_pairs"] == panel["disconnected_worlds"] == 28
    for mode in ("input_at_readout", "input_history"):
        for value in panel["modes"][mode].values():
            np.testing.assert_allclose(value, 1, atol=4 * np.finfo(float).eps, rtol=0)
        for arm in readouts[0][mode]["arms"].values():
            assert all(t["metrics"]["resolved_fraction"] == 0 for t in arm["tasks"].values())
    for report in readouts[0].values():
        assert all(
            t["metrics"]["resolved_fraction"] == 0
            for t in report["arms"]["no_cue"]["tasks"].values()
        )
    for identity, restricted in panel["modes"]["voltage"].items():
        all_cells = panel["modes"]["all_cell_voltage"][identity]
        np.testing.assert_array_equal(
            restricted, all_cells.reshape(3, 7)[:, [1, 2, 4, 5, 6]].reshape(-1)
        )
    evidence(
        f"{PREFIX}-controls",
        dict(
            status="passed",
            no_cue_bitwise_comparisons=27,
            unused_label_bitwise_pairs=28,
            disconnected_zero_flux_worlds=28,
            no_cue_readers_unresolved=True,
            restricted_input_current_and_history_unresolved=True,
            restricted_features_match_selected_cells=True,
        ),
    )


def test_unstimulated_replay(panel, tmp_path):
    expected = panel["replay"]
    selected = [r for r in ROWS if r["world_id"] in expected]
    plan = assay.batch(BASE, selected, BACKEND, RULE)
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
            history = expected[identity].history
            original.assert_history_same(
                value.history,
                type(history)(*(v[offset : offset + len(value.times)] for v in history)),
            )
        offset += len(next(iter(window.worlds.values())).times) - 1
    assert offset == 1024
    reference_world = expected[selected[0]["world_id"]]
    before = tuple(v.copy() for v in reference_world.history)
    vector = assay.voltage_features(reference_world, RULE)
    trained = template_readout.TemplateReader(
        np.stack([[vector, vector], [vector + 1e-7, vector + 1e-7]]),
        np.array([[0], [1]]),
        RULE["reader"]["voltage_margin_V"],
    )
    trained.read([vector])
    original.assert_history_same(reference_world.history, before)
    cut = round(16e-6 / RULE["dt_s"]) - 1
    assert cut == 255
    write_snapshot(
        tmp_path / "unstimulated-cut",
        reference_world.spec,
        reference_world.checkpoint_at(reference_world.times[cut]),
    )
    restored = load_snapshot(tmp_path / "unstimulated-cut")
    resumed = run(restored.spec, restored.checkpoint)
    original.assert_history_same(
        resumed.history, type(reference_world.history)(*(v[cut:] for v in reference_world.history))
    )
    np.testing.assert_array_equal(assay.voltage_features(resumed, RULE), vector)
    np.testing.assert_array_equal(
        trained.read([assay.voltage_features(resumed, RULE)])["score"],
        trained.read([vector])["score"],
    )
    evidence(
        f"{PREFIX}-replay",
        dict(
            status="passed",
            dt_s=RULE["dt_s"],
            history_fields=14,
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=127,
            window_comparison_streamed=True,
            snapshot_step=cut,
            replay="bitwise",
            passive_reader_neutrality=True,
        ),
    )


def test_unstimulated_cpu_gpu(panel, readouts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    modes = panel["modes"]
    reports, shuffles = readouts
    root = Path(EVIDENCE) / "cpu"
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    count = 0
    for row in ROWS:
        name = world_name(row["world_id"]) + ".npz"
        with (
            np.load(panel["archive"] / name, allow_pickle=False) as actual,
            np.load(root / name, allow_pickle=False) as saved,
        ):
            count += reference.compare(actual, saved, area)
    atol = reference.PROTOCOL["tolerances"]["voltage_atol_V"]
    rtol = reference.PROTOCOL["tolerances"]["cpu_gpu_rtol"]
    with np.load(root / "unstimulated-readouts.npz", allow_pickle=False) as saved:
        for mode, values in modes.items():
            for identity, value in values.items():
                if mode.startswith("input"):
                    np.testing.assert_array_equal(value, saved[f"{mode}__{identity}"])
                else:
                    np.testing.assert_allclose(
                        value, saved[f"{mode}__{identity}"], atol=atol, rtol=rtol
                    )
    cpu = json.loads((root / "unstimulated-readouts.json").read_text())
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
        "unstimulated-cpu-gpu",
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
