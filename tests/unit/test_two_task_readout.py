"""Assay integrity, ordinary runtime execution, replay and CPU/L4 agreement."""

import copy
import json
from dataclasses import replace
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.assays.readout import CentroidReader, VoltageReadout, score_predictions
from cells.core.batch import plan_batch, run_batch
from cells.core.batch_windows import iter_batch_windows, plan_batch_windows
from cells.core.runner import control_values, run
from cells.core.specs import parse_spec
from cells.core.windows import WindowPolicy
from cells.io import load_snapshot, write_snapshot
from tests.unit import test_betse_junction_runtime as reference
from validation.assays import two_task as assay

RULE = assay.protocol()
BASE = json.loads((assay.ROOT / RULE["template"]).read_text())
ROWS = assay.cases(RULE)
BACKEND, EVIDENCE = reference.BACKEND, reference.EVIDENCE
evidence = reference.common.evidence


def test_host_voltage_reader_has_restricted_support():
    reader = VoltageReadout((9, 4), (1.0, 2.0))
    times = np.array([0.0, 1.0, 2.0])
    voltage = np.array([[0.0, 0.0, 0.0], [2.0, 4.0, 8.0], [3.0, 8.0, 12.0]])
    kwargs = dict(
        cell_ids=np.array([4, 9]),
        cell_owner=np.array([0, 1, 1]),
        membrane_area=np.array([2.0, 1.0, 3.0]),
    )
    before = voltage.copy()
    actual = reader.observe(times, voltage, **kwargs)
    np.testing.assert_array_equal(actual, [7.0, 2.0, 11.0, 3.0])
    np.testing.assert_array_equal(voltage, before)
    assert not actual.flags.writeable
    # Unread samples cannot influence the result; IDs are physical cells, not row positions.
    voltage[0] = 900
    np.testing.assert_array_equal(reader.observe(times, voltage, **kwargs), actual)
    present = VoltageReadout((9, 4), (1.0,))
    current = present.observe(times, voltage, **kwargs)
    voltage[2] = -900
    np.testing.assert_array_equal(present.observe(times, voltage, **kwargs), current)
    with pytest.raises(TypeError):
        reader.observe(times, voltage, labels=[0, 1], **kwargs)
    with pytest.raises(ValueError, match="exact accepted"):
        VoltageReadout((4,), (1.5,)).observe(times, voltage, **kwargs)
    with pytest.raises(ValueError, match="absent"):
        VoltageReadout((10,), (1.0,)).observe(times, voltage, **kwargs)
    with pytest.raises(ValueError):
        reader.observe(times, voltage, **(kwargs | {"cell_owner": np.array([0.0, 1.0, 1.0])}))


@pytest.mark.parametrize(
    "ids,times",
    [
        ((1, 1), (1.0,)),
        ((True,), (1.0,)),
        ((1,), (1.0, 1.0)),
        ((1,), (float("nan"),)),
        ((1,), (-1.0,)),
    ],
)
def test_host_invalid_voltage_contract(ids, times):
    with pytest.raises(ValueError):
        VoltageReadout(ids, times)


def test_host_reader_calibration_and_unresolved_predictions():
    reader = CentroidReader.fit([[0, 0], [2, 0], [0, 2], [2, 2]], [0, 0, 1, 1], minimum_margin=0.1)
    values = reader.read([[10, 0], [10, 1], [10, 2]])
    np.testing.assert_array_equal(values["score"], [-1, 0, 1])
    np.testing.assert_array_equal(values["prediction"], [0, 0, 1])
    np.testing.assert_array_equal(values["resolved"], [True, False, True])
    report = score_predictions([0, 1, 1], values["prediction"], values["resolved"])
    assert report["forced_accuracy"] == report["resolved_correct_fraction_of_all_cases"] == 2 / 3
    assert report["accuracy_on_resolved"] == 1 and report["cases"] == 3
    with pytest.raises(ValueError):
        reader.centers[0, 0] = 10
    with pytest.raises(ValueError):
        reader.read([[1]])
    with pytest.raises(ValueError):
        CentroidReader.fit([[1], [2]], [0, 0], minimum_margin=0.1)
    null = CentroidReader.fit(np.zeros((4, 2)), [0, 1, 0, 1], minimum_margin=0.1).read([[0, 0]])
    assert not null["resolved"].any() and null["separation"] == 0


def test_host_assay_splits_and_equal_physical_cue_budget():
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 80
    assert not RULE["automatic_followup"] and RULE["steps"] * RULE["dt_s"] == 64e-6
    assert len(RULE["readout_steps"]) == len(RULE["input_history_steps"]) == 3
    assert min(RULE["readout_steps"]) > max(p[1] for p in RULE["timing_pulses_steps"])
    budgets = []
    for arm in RULE["arms"]:
        rows = [r for r in ROWS if r["arm"] == arm]
        tested = []
        for _, training, testing in assay.folds(rows, arm):
            assert {r["world_id"] for r in training}.isdisjoint(r["world_id"] for r in testing)
            assert {r["preparation"] for r in training}.isdisjoint(
                r["preparation"] for r in testing
            )
            assert {r["amplitude"] for r in training}.isdisjoint(r["amplitude"] for r in testing)
            if arm not in ("location_only", "timing_only"):
                assert {(r["location"], r["timing"]) for r in training}.isdisjoint(
                    (r["location"], r["timing"]) for r in testing
                )
            tested.extend(r["world_id"] for r in testing)
        assert len(tested) == len(set(tested)) == (4 if arm.endswith("only") else 8)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    expected_area = min(area[owner == identity - 1].sum() for identity in RULE["source_cell_ids"])
    for row in ROWS:
        raw = assay.definition(BASE, row, "cpu", RULE)
        assert raw["model"] == BASE["model"]  # Only declared execution/controls/readout change.
        spec = parse_spec(raw)
        controls = control_values(spec, np.arange(64) * RULE["dt_s"])
        dose = float(np.sum((1 - controls.channel) @ area) * RULE["dt_s"])
        expected = 0 if row["arm"] == "no_cue" else row["amplitude"] * expected_area * 8e-6
        assert dose == pytest.approx(expected, rel=2e-14, abs=1e-30)
        np.testing.assert_array_equal(controls.pump, 1)
        np.testing.assert_array_equal(controls.junction, 0 if row["arm"] == "disconnected" else 1)
        assert np.all((controls.channel >= 0) & (controls.channel <= 1))
        assert np.all(controls.channel[32:] == 1)
        assert {"world_id", "location", "timing", "preparation", "split"}.isdisjoint(raw)
        budgets.append(dict(world_id=row["world_id"], blocked_area_time_m2_s=dose))
    # Exercise the real allocation guards before any accepted simulation. A
    # single-world numerical smoke does not establish that four worlds fit.
    plans = []
    for start in range(0, len(ROWS), RULE["batch_worlds"]):
        rows = ROWS[start : start + RULE["batch_worlds"]]
        batch = assay.batch(BASE, rows, BACKEND, RULE)
        full = plan_batch(batch)
        windowed = plan_batch_windows(batch, WindowPolicy(window_steps=17, recording="full"))
        assert batch.max_working_bytes <= RULE["resources"]["max_worker_rss_bytes"] // 16
        plans.append(
            dict(
                world_ids=[r["world_id"] for r in rows],
                estimated_batch_working_bytes=full.estimated_working_bytes,
                estimated_window_working_bytes=windowed.estimated_working_bytes,
                batch_budget_bytes=batch.max_working_bytes,
            )
        )
    evidence(
        "assay-design",
        dict(
            status="passed",
            cases=ROWS,
            cue_budgets=budgets,
            allocation_plans=plans,
            unique_evaluation_cases_per_task_single=4,
            unique_evaluation_cases_per_task_joint=8,
            steps_per_arm=16 * 64,
            independent_biological_replicates=0,
        ),
    )


def test_host_heldout_features_do_not_fit_the_reader():
    # A synthetic decoder oracle exercises the actual four-fold analysis path.
    rows = [r for r in ROWS if r["arm"] == "joint"]
    features = {
        r["world_id"]: np.array([2 * r["location"] - 1, 2 * r["timing"] - 1], float) for r in rows
    }
    result = assay.evaluate(rows, features, margin=0.01)
    assert result["arms"]["joint"]["joint"]["forced_accuracy"] == 1
    altered = copy.deepcopy(features)
    for row in rows:
        if row["split"] == "heldout":
            altered[row["world_id"]] *= -100
    other = assay.evaluate(rows, altered, margin=0.01)
    for task in ("location", "timing"):
        assert (
            result["arms"]["joint"]["tasks"][task]["calibration"]
            == other["arms"]["joint"]["tasks"][task]["calibration"]
        )
    shuffled = assay.evaluate(rows, features, margin=0.01, shuffle_seed=4100)
    assert shuffled == assay.evaluate(list(rows), features, margin=0.01, shuffle_seed=4100)
    assert shuffled["arms"]["joint"]["joint"]["forced_accuracy"] < 1


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_assay_prerequisite(prior):
    evidence("assay-prerequisite", prior)


@pytest.fixture(scope="module")
def panel(prior):
    jax.config.update("jax_enable_x64", True)
    results, batches = {}, []
    for start in range(0, len(ROWS), RULE["batch_worlds"]):
        rows = ROWS[start : start + RULE["batch_worlds"]]
        plan = assay.batch(BASE, rows, BACKEND, RULE)
        actual = run_batch(plan)
        batches.append(
            dict(
                world_ids=[r["world_id"] for r in rows],
                arm=rows[0]["arm"],
                timings=actual.timings,
                resources=actual.resources,
            )
        )
        for row in rows:
            result = actual.worlds[row["world_id"]]
            assert all(v.device.platform == BACKEND for v in result.final.state)
            results[row["world_id"]] = result
            evidence(
                f"assay-world-{row['world_id']}",
                dict(
                    status="passed",
                    case=row,
                    input=plan.worlds[
                        [w.world_id for w in plan.worlds].index(row["world_id"])
                    ].simulation.to_dict(),
                    diagnostics=result.diagnostics,
                ),
                reference.arrays(result),
            )
    return results, batches


def test_assay_panel(panel):
    results, batches = panel
    assert len(results) == 80
    assert all(b["resources"]["executed_world_steps"] == 256 for b in batches)
    assert all(len(r.history) == 14 for r in results.values())
    assert all(r.diagnostics["max_material_error_over_budget"] <= 1 for r in results.values())
    evidence(
        "assay-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=80,
            total_world_steps=5120,
            batches=batches,
            no_new_native_parity_claim=True,
        ),
    )


@pytest.fixture(scope="module")
def readouts(panel):
    results, _ = panel
    voltages = {
        identity: assay.voltage_features(result, RULE) for identity, result in results.items()
    }
    modes = dict(
        voltage=voltages,
        final_voltage={k: v[-7:] for k, v in voltages.items()},
        input_at_readout={
            k: assay.input_features(v.spec, RULE["readout_steps"], RULE) for k, v in results.items()
        },
        input_history={
            k: assay.input_features(v.spec, RULE["input_history_steps"], RULE)
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
        ROWS, voltages, margin=RULE["reader"]["coarse_voltage_margin_V"]
    )
    joint = [r for r in ROWS if r["arm"] == "joint"]
    shuffled = []
    for seed in RULE["reader"]["shuffle_seeds"]:
        report = assay.evaluate(
            joint, voltages, margin=RULE["reader"]["voltage_margin_V"], shuffle_seed=seed
        )
        arm = report["arms"]["joint"]
        shuffled.append(
            dict(
                seed=seed,
                joint=arm["joint"],
                tasks={t: r["metrics"] for t, r in arm["tasks"].items()},
            )
        )
    return modes, reports, shuffled


def test_assay_readouts(readouts):
    modes, reports, shuffled = readouts
    assert reports["voltage"]["feature_count"] == reports["input_history"]["feature_count"] == 21
    assert reports["final_voltage"]["feature_count"] == 7
    assert len(shuffled) == 32
    for report in reports.values():
        for arm in report["arms"].values():
            for task in arm["tasks"].values():
                assert 0 <= task["metrics"]["forced_accuracy"] <= 1
                assert task["metrics"]["cases"] in (4, 8)
    evidence(
        "assay-readouts",
        dict(
            status="passed",
            numerical_verification_only=True,
            biological_or_causal_use_demonstrated=False,
            outcomes=reports,
            shuffled_calibration=shuffled,
        ),
        {
            f"{name}__{identity}": values
            for name, rows in modes.items()
            for identity, values in rows.items()
        },
    )


def assert_history_same(actual, expected):
    for x, y in zip(actual, expected, strict=True):
        assert x.dtype == y.dtype and x.shape == y.shape
        np.testing.assert_array_equal(x, y)


def test_assay_replay_and_passive_observers(panel, tmp_path):
    results, _ = panel
    rows = [r for r in ROWS if r["arm"] == "joint"][:4]
    plan = assay.batch(BASE, rows, BACKEND, RULE)
    reverse = run_batch(replace(plan, worlds=tuple(reversed(plan.worlds))))
    for identity, result in reverse.worlds.items():
        assert_history_same(result.history, results[identity].history)
    for part in (plan.worlds[:2], plan.worlds[2:]):
        partition = run_batch(replace(plan, worlds=part))
        for identity, result in partition.worlds.items():
            assert_history_same(result.history, results[identity].history)
    windows = list(iter_batch_windows(plan, WindowPolicy(window_steps=17, recording="full")))
    # Existing window interface keeps complete RunResults per world.
    for identity in results.keys() & {w.world_id for w in plan.worlds}:
        parts = [window.worlds[identity] for window in windows]
        history = type(results[identity].history)(
            *(
                np.concatenate(
                    [
                        getattr(part.history, name)[0 if i == 0 else 1 :]
                        for i, part in enumerate(parts)
                    ]
                )
                for name in results[identity].history._fields
            )
        )
        assert_history_same(history, results[identity].history)
    original = results[rows[0]["world_id"]]
    before = tuple(v.copy() for v in original.history)
    for steps in ([64], [40, 48, 64], [48]):
        assay.voltage_features(original, RULE | {"readout_steps": steps})
    assert_history_same(original.history, before)
    # Change observer cadence without changing the trajectory.
    raw = original.spec.to_dict()
    raw["experiment"]["observation_times"] = [i * RULE["dt_s"] for i in range(65)]
    dense = run(parse_spec(raw))
    assert_history_same(dense.history, original.history)
    np.testing.assert_array_equal(
        assay.voltage_features(dense, RULE), assay.voltage_features(original, RULE)
    )
    # Complete disk checkpoint immediately before cue onset; no reader state needed.
    snapshot = tmp_path / "cue-checkpoint"
    write_snapshot(snapshot, original.spec, original.checkpoint_at(original.times[7]))
    restored = load_snapshot(snapshot)
    resumed = run(restored.spec, restored.checkpoint)
    assert_history_same(resumed.history, type(original.history)(*(v[7:] for v in original.history)))
    np.testing.assert_array_equal(
        assay.voltage_features(resumed, RULE), assay.voltage_features(original, RULE)
    )
    evidence(
        "assay-replay",
        dict(
            status="passed",
            reordered_worlds=4,
            partition_sizes=[2, 2],
            window_steps=17,
            snapshot_step=7,
            history_fields=14,
            observer_cadence_and_call_order="bitwise",
            snapshot_readout="bitwise",
        ),
    )


def test_assay_controls(panel, readouts):
    results, _ = panel
    modes, reports, _ = readouts
    # At readout the physical cue is absent in every arm.
    for values in modes["input_at_readout"].values():
        np.testing.assert_allclose(values, 1, rtol=0, atol=4 * np.finfo(float).eps)
    no_cue = [r for r in ROWS if r["arm"] == "no_cue"]
    first = results[no_cue[0]["world_id"]]
    for row in no_cue[1:]:
        assert_history_same(results[row["world_id"]].history, first.history)
    for task in reports["voltage"]["arms"]["no_cue"]["tasks"].values():
        assert task["metrics"]["resolved_fraction"] == 0
    for row in ROWS:
        if row["arm"] == "disconnected":
            result = results[row["world_id"]]
            np.testing.assert_array_equal(result.history.junction_open[1:], 0)
            np.testing.assert_array_equal(result.history.junction_outward_fmol, 0)
    # Absent labels in single-task arms cannot alter their physical trajectories.
    duplicates = 0
    for arm, ignored in (("location_only", "timing"), ("timing_only", "location")):
        selected = [r for r in ROWS if r["arm"] == arm]
        for row in selected:
            if row[ignored] == 0:
                paired = next(
                    r
                    for r in selected
                    if r[ignored] == 1
                    and all(
                        r[k] == row[k]
                        for k in ("preparation", "location", "timing")
                        if k != ignored
                    )
                )
                assert_history_same(
                    results[row["world_id"]].history, results[paired["world_id"]].history
                )
                duplicates += 1
    evidence(
        "assay-controls",
        dict(
            status="passed",
            no_cue_identical_worlds=16,
            single_task_duplicate_pairs_excluded_from_scoring=duplicates,
            disconnected_transport="zero",
            cue_absent_at_readout=True,
            disconnected_chance_accuracy_required=False,
        ),
    )


def test_assay_cpu_gpu(panel, readouts):
    if BACKEND == "cpu":
        pytest.skip("Requires following L4 phase and saved CPU trajectories")
    assert EVIDENCE
    results, _ = panel
    count = 0
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    for identity, result in results.items():
        with np.load(
            Path(EVIDENCE) / f"cpu/assay-world-{identity}.npz", allow_pickle=False
        ) as saved:
            count += reference.compare(reference.arrays(result), saved, area)
    modes, reports, _ = readouts
    with np.load(Path(EVIDENCE) / "cpu/assay-readouts.npz", allow_pickle=False) as saved:
        for name, rows in modes.items():
            for identity, values in rows.items():
                np.testing.assert_allclose(
                    values, saved[f"{name}__{identity}"], atol=2e-10, rtol=3e-10
                )
    cpu = json.loads((Path(EVIDENCE) / "cpu/assay-readouts.json").read_text())["outcomes"]
    decisions = []
    # Compare fitted centers in physical units. Unresolved/tied decisions may
    # differ by rounding; retain both outcomes rather than claiming agreement.
    for mode, report in reports.items():
        for arm, row in report["arms"].items():
            for task, detail in row["tasks"].items():
                prior = cpu[mode]["arms"][arm]["tasks"][task]
                for x, y in zip(detail["calibration"], prior["calibration"], strict=True):
                    np.testing.assert_allclose(
                        x["reader"]["centers"], y["reader"]["centers"], atol=2e-10, rtol=3e-10
                    )
                differences = [
                    x["world_id"]
                    for x, y in zip(detail["predictions"], prior["predictions"], strict=True)
                    if x["prediction"] != y["prediction"] or x["resolved"] != y["resolved"]
                ]
                decisions.append(
                    dict(
                        mode=mode,
                        arm=arm,
                        task=task,
                        differing_decision_world_ids=differences,
                        cpu_metrics=prior["metrics"],
                        gpu_metrics=detail["metrics"],
                    )
                )
    evidence(
        "assay-cpu-gpu",
        dict(
            status="passed",
            worlds=80,
            compared_state_and_field_values=count,
            physical_tolerances_unchanged=True,
            decisions=decisions,
            exact_decision_agreement=not any(r["differing_decision_world_ids"] for r in decisions),
        ),
    )
