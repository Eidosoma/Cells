"""Fresh strengths and fixed spanning observations, using the qualified harness."""

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
from validation.assays import source_order_long_diagnostic as diagnostic
from validation.assays import source_order_spanning as assay
from validation.assays import template_readout, two_task

RULE, SOURCE, ROWS = assay.protocol(), assay.SOURCE, assay.cases()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
PREFIX = "source-order-spanning"
evidence = reference.common.evidence


def inherited_evidence(name, record, arrays=None):
    # The inherited CPU/GPU checker iterates the bound cohort, but its report
    # contains the former literal world count. Adapt that metadata only.
    if name == f"{PREFIX}-cpu-gpu":
        assert record["worlds"] == 420
        record = record | {"worlds": RULE["work"]["worlds_per_backend"]}
    evidence(name, record, arrays)


@pytest.fixture(scope="module", autouse=True)
def configured_harness():
    """Bind reusable fixture/check globals for this module, then restore them.

    Frozen source files remain unchanged. Other collected modules receive the
    original parameters after teardown; no production function is replaced.
    """
    assert shared.POLICY.window_steps == RULE["window_steps"]
    with pytest.MonkeyPatch.context() as patch:
        for name, value in dict(
            RULE=RULE,
            ROWS=ROWS,
            BASE=BASE,
            PREFIX=PREFIX,
            assay=assay,
            compare_historical_window=compare_historical_window,
            evidence=inherited_evidence,
        ).items():
            patch.setattr(shared, name, value)
        yield


panel = shared.panel
readouts = shared.readouts
transfers = shared.transfers
test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = shared.test_host_source_order_long_archive_boundaries
test_host_reference_answers = shared.test_host_source_order_long_reference_known_answers
test_prerequisite = shared.test_source_order_long_prerequisite
test_replay = shared.test_source_order_long_replay
test_baseline_transfer = shared.test_source_order_long_baseline_transfer
test_cpu_gpu = shared.test_source_order_long_cpu_gpu


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_host_design_and_resources():
    plan = json.loads((two_task.ROOT / RULE["design_plan"]).read_text())
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 220
    assert {r["world_id"] for r in ROWS}.isdisjoint(r["world_id"] for r in assay.SOURCE_ROWS)
    assert Counter(r["arm"] for r in ROWS) == dict.fromkeys(plan["arms"], 44)
    new = {r["amplitude"] for r in ROWS if r["split"] == "heldout"}
    assert new == set(plan["evaluation_strengths"]) and len(new) == 8
    earlier_strengths = set()
    for path in (two_task.ROOT / "validation/assays").rglob("*protocol.json"):
        if path != assay.PROTOCOL_PATH:
            earlier_strengths.update(
                p["amplitude"] for p in json.loads(path.read_text()).get("preparations", [])
            )
    assert new.isdisjoint(earlier_strengths)
    assert RULE["preparations"][:3] == SOURCE["preparations"][:3]
    assert RULE["duration_s"] == SOURCE["duration_s"] == 512e-6
    assert RULE["dt_s"] == SOURCE["dt_s"] == [0.25e-6, 0.125e-6, 0.0625e-6]
    assert RULE["reader"] == SOURCE["reader"] and RULE["primary_panel"] == "spanning512"
    assert not RULE["automatic_followup"]
    for name in RULE["observation_panels"]:
        np.testing.assert_allclose(
            assay.times(RULE, name) * 1e6, RULE["observation_times_us"][name], atol=1e-12, rtol=0
        )
    assert all(assay.times(RULE, "spanning512") > 112 * two_task.protocol()["dt_s"])
    original = copy.deepcopy(BASE)
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    owner = np.asarray(BASE["model"]["tissue"]["cell_owner"])
    masks = [owner == i - 1 for i in RULE["source_cell_ids"]]
    ref_area = min(area[m].sum() for m in masks)
    plans, doses, mapping, archive_estimate = [], [], [], 0
    history = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            before, duration = assay.historical_source(row)
            record = json.loads(
                (history / (assay.world_name(level, before["world_id"]) + ".json")).read_text()
            )
            assert record["status"] == "passed" and record["case"] == before
            assert raw["model"] == record["input"]["model"] == BASE["model"]
            assert raw["execution"] == record["input"]["execution"]
            assert {k: v for k, v in raw["experiment"].items() if k != "changes"} == {
                k: v for k, v in record["input"]["experiment"].items() if k != "changes"
            }
            if duration == RULE["duration_s"]:
                assert raw == record["input"]
            spec = parse_spec(raw)
            grid = np.asarray(list(checked_grid(spec)))
            assert len(grid) == steps + 1 and grid[-1] == RULE["duration_s"]
            assert len(spec.experiment.observation_times) == 12
            controls = control_values(spec, grid[:-1])
            old_controls = control_values(parse_spec(record["input"]), grid[:-1])
            stop = round(duration / dt)
            for actual, old in zip(controls, old_controls, strict=True):
                np.testing.assert_array_equal(actual[:stop], old[:stop])
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
                pulse = RULE["cue_timing"][
                    "location_only_pulse_us"
                    if row["arm"] == "location_only"
                    else "early_pulse_us"
                    if i == row["timing"]
                    else "late_pulse_us"
                ]
                start, end = [round(t * 1e-6 / dt) for t in pulse]
                expected[start:end, mask] = (
                    1 - row["amplitude"] * weight * ref_area / area[mask].sum()
                )
            np.testing.assert_allclose(controls.channel, expected, rtol=0, atol=4e-16)
            assert np.all((controls.channel >= 0) & (controls.channel <= 1))
            amounts = [float(np.sum((1 - controls.channel[:, m]) @ area[m]) * dt) for m in masks]
            np.testing.assert_allclose(
                amounts,
                [row["amplitude"] * w * ref_area * 8e-6 for w in weights],
                rtol=2e-14,
                atol=1e-30,
            )
            doses.append(dict(level=level, world_id=row["world_id"], source_doses_m2_s=amounts))
            mapping.append(
                dict(
                    level=level,
                    world_id=row["world_id"],
                    source_world_id=before["world_id"],
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
            batch = assay.batch(
                BASE, ROWS[start : start + RULE["batch_worlds"]], level, BACKEND, RULE
            )
            bounded = plan_batch_windows(batch, shared.POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in batch.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * 5 * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert archive_estimate + 4 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 165
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    assert Counter(r["duration_s"] for r in mapping) == {512e-6: 276, 8e-6: 384}
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
            primary_panel=RULE["primary_panel"],
            observation_times_us=RULE["observation_times_us"],
            work=RULE["work"],
            retained_array_estimate_bytes=retained,
            uncompressed_archive_estimate_bytes=archive_estimate,
            new_strengths_disjoint_from_prior_protocols=True,
            no_response_simulation_during_preflight=True,
        ),
    )


def test_host_support():
    ids = np.array([4, 7, 2, 1, 5, 3, 6])
    owner, area = np.repeat(np.arange(7), 2), np.arange(1, 15, dtype=float)
    times = np.array(sorted({t for p in RULE["observation_panels"] for t in assay.times(RULE, p)}))
    assert len(times) == 12
    voltage = np.arange(len(times) * len(owner), dtype=float).reshape(len(times), -1) * 1e-6
    proxy = SimpleNamespace(
        spec=parse_spec(assay.definition(BASE, ROWS[0], 2, BACKEND, RULE)),
        final=SimpleNamespace(
            layout=SimpleNamespace(
                ids=ids,
                tissue_cell_owner=owner,
                tissue_membrane_area=area,
            )
        ),
        observations=SimpleNamespace(times=times, membrane_voltage_V=voltage),
    )
    saved = {}
    for panel_name in RULE["observation_panels"]:
        actual = assay.features(proxy, RULE, panel_name)
        selected = [int(np.flatnonzero(times == t)[0]) for t in assay.times(RULE, panel_name)]
        expected = [
            sum(voltage[i, c] * area[c] for c in np.flatnonzero(ids[owner] == cell))
            / area[ids[owner] == cell].sum()
            for i in selected
            for cell in RULE["readout"]["cell_ids"]
        ]
        np.testing.assert_allclose(actual["voltage"], expected, atol=1e-19, rtol=0)
        assert actual["voltage"].shape == (15,) and actual["all_cell_voltage"].shape == (21,)
        saved[panel_name] = actual
    maps = {(0, p): {"voltage": {1: saved[p]["voltage"]}} for p in assay.SPANNING_PANELS}
    np.testing.assert_array_equal(
        diagnostic.spanning_features([{"world_id": 1}], maps, 0, RULE)[1],
        saved["spanning512"]["voltage"],
    )
    voltage[:, np.isin(ids[owner], [1, 4])] += 123
    for p in saved:
        np.testing.assert_array_equal(
            assay.features(proxy, RULE, p)["voltage"], saved[p]["voltage"]
        )
    voltage[~np.isin(times, assay.times(RULE, "spanning512"))] += 456
    np.testing.assert_array_equal(
        assay.features(proxy, RULE, "spanning512")["voltage"], saved["spanning512"]["voltage"]
    )
    with pytest.raises(TypeError):
        assay.features(proxy, RULE, "spanning512", labels=[0, 1])
    evidence(
        f"{PREFIX}-support",
        dict(
            status="passed",
            primary_features=15,
            observations=12,
            unequal_area_weighting=True,
            source_cells_and_unselected_times_excluded=True,
            exact_diagnostic_feature_extractor=True,
        ),
    )


def compare_historical_window(value, row, level):
    before, duration = assay.historical_source(row)
    limit = round(duration / RULE["dt_s"][level])
    if value.start_step >= limit:
        return None
    stop = min(value.final.step_index, limit)
    mask = value.observations.times <= limit * RULE["dt_s"][level]
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    saved = assay.archived_segment(
        root, level, before["world_id"], value.start_step, stop, value.observations.times[mask]
    )
    actual = {
        name: a[mask] if name.startswith("observed__") else a[: stop - value.start_step + 1]
        for name, a in reference.arrays(value).items()
    }
    count = reference.compare(actual, saved, value.final.layout.tissue_membrane_area)
    for name, a in actual.items():
        np.testing.assert_array_equal(a, saved[name], err_msg=name)
    return dict(
        level=level,
        world_id=row["world_id"],
        source_world_id=before["world_id"],
        start_step=value.start_step,
        stop_step=stop,
        compared_scalars=count,
        reproduced_duration_s=duration,
        bitwise=True,
    )


def test_host_history_boundaries(tmp_path, monkeypatch):
    root = tmp_path / "evidence" / BACKEND
    root.mkdir(parents=True)
    row = next(r for r in ROWS if r["arm"] == "joint" and r["split"] == "heldout")
    old, duration = assay.historical_source(row)
    dt = RULE["dt_s"][0]
    assert duration == 8e-6 and old["world_id"] != row["world_id"]
    stop = round(duration / dt)
    name = assay.world_name(0, old["world_id"])
    data = dict(
        state__voltage=np.arange(41, dtype=float)[:, None] * 1e-9,
        junction__open=np.ones((41, 1)),
        observed__voltage=np.empty((0, 1)),
    )
    np.savez_compressed(root / (name + ".npz"), **data)
    (root / (name + ".json")).write_text(
        json.dumps(
            dict(
                status="passed",
                windows=[
                    dict(
                        file=name + ".npz",
                        start_step=0,
                        stop_step=40,
                        observation_times=[],
                    )
                ],
            )
        )
    )
    monkeypatch.setitem(RULE, "prior_binding", {"root": str(tmp_path)})
    actual = {k: v.copy() for k, v in data.items()}
    actual["state__voltage"][stop + 1 :] += 999
    monkeypatch.setattr(reference, "arrays", lambda _: actual)
    value = SimpleNamespace(
        start_step=0,
        final=SimpleNamespace(
            step_index=40,
            layout=SimpleNamespace(tissue_membrane_area=np.ones(1)),
        ),
        observations=SimpleNamespace(times=np.array([])),
    )
    result = compare_historical_window(value, row, 0)
    assert result["bitwise"] and result["stop_step"] == stop
    assert result["compared_scalars"] == 2 * (stop + 1)
    actual["state__voltage"][stop] += 1
    with pytest.raises(AssertionError):
        compare_historical_window(value, row, 0)
    value.start_step = stop
    assert compare_historical_window(value, row, 0) is None
    full = [r for r in ROWS if assay.historical_source(r)[1] == 512e-6]
    assert len(full) == 92
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            new_identity_mapping=True,
            precue_boundary_clipped=True,
            later_changed_response_ignored=True,
            corrupt_shared_prefix_rejected=True,
            unchanged_calibration_and_null_rows=92,
        ),
    )


def test_host_paired_known_answers():
    rows = [r for r in ROWS if r["arm"] == "joint"]
    reports = []
    for kind in ("spanning", "late"):
        features = {}
        for row in rows:
            weak = row["split"] == "heldout" and (
                row["amplitude"] >= 0.7 if kind == "spanning" else row["amplitude"] < 0.5
            )
            point = [
                10 * row["location"],
                5 if weak else 10 * row["timing"],
                100 * row["amplitude"],
            ]
            features[row["world_id"]] = np.pad(point, (0, 12))
        reports.append(template_readout.evaluate(rows, features, margin=1))
    before = copy.deepcopy(reports)
    result = assay.paired_report(*reports)
    assert result["counts"] == dict(spanning_only=8, late_only=8, both=16, neither=0)
    assert len(result["cases"]) == 32 and result["spanning_minus_late_resolved_cases"] == 0
    assert reports == before
    reports[1]["arms"]["joint"]["tasks"]["timing"]["predictions"][0]["world_id"] = -1
    with pytest.raises(AssertionError):
        assay.paired_report(*reports)
    evidence(
        f"{PREFIX}-paired-known-answers",
        dict(
            status="passed",
            improvements_and_regressions_preserved=True,
            same_case_support_required=True,
            scores_and_original_reports_unchanged=True,
        ),
    )


def test_panel(panel):
    assert len(panel["batches"]) == 165
    assert sum(b["resources"]["executed_world_steps"] for b in panel["batches"]) == 3153920
    for arm in two_task.protocol()["arms"]:
        assert (
            sum(b["resources"]["executed_world_steps"] for b in panel["batches"] if b["arm"] == arm)
            == 630784
        )
    assert all(len(v) == 220 for modes in panel["maps"].values() for v in modes.values())
    assert panel["max_material_error_over_budget"] <= 1
    evidence(
        f"{PREFIX}-panel",
        dict(
            status="passed",
            backend=BACKEND,
            worlds=660,
            world_steps=3153920,
            batches=panel["batches"],
            max_material_error_over_budget=panel["max_material_error_over_budget"],
            retained_full_world_histories=0,
        ),
    )


def test_historical_reproduction(panel, readouts):
    histories = panel["prefixes"]
    assert len(histories) == 1672
    assert len({(r["level"], r["world_id"]) for r in histories}) == 660
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(assay.historical_source(row)[1] / dt)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    count = 0
    with np.load(root / "source-order-long-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for row in ROWS:
                old, duration = assay.historical_source(row)
                if duration != 512e-6:
                    continue
                for mode, values in modes.items():

                    def get(p, m=mode, current_level=level, identity=old["world_id"]):
                        return saved[f"{current_level}__{p}__{m}__{identity}"]

                    if name != "spanning512":
                        expected = get(name)
                    elif mode in ("voltage", "all_cell_voltage", "input_at_readout"):
                        width = 7 if mode == "all_cell_voltage" else 5
                        expected = np.concatenate([get(p)[-width:] for p in assay.SPANNING_PANELS])
                    else:
                        expected = get("long512")
                    np.testing.assert_array_equal(values[row["world_id"]], expected)
                    count += expected.size
    old_reports = json.loads((root / "source-order-long-readouts.json").read_text())["panels"]
    diagnosis = json.loads((Path(RULE["diagnostic_binding"]["root"]) / "result.json").read_text())
    curve_count = 0
    for name, group in readouts.items():
        for level, actual in enumerate(group["resolution_matched"]):
            expected = (
                diagnosis["backends"][BACKEND]["spanning_comparator"]["matched_reports"][level]
                if name == "spanning512"
                else old_reports[name]["resolution_matched"][level]["outcomes"]["voltage"]
            )
            for arm, value in actual["outcomes"]["voltage"]["arms"].items():
                assert (
                    value["calibration"]["template_reader"]
                    == expected["arms"][arm]["calibration"]["template_reader"]
                )
                curve_count += 1
    assert count == 97980 and curve_count == 75
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            world_prefixes=660,
            full_512us_worlds=276,
            precue_only_worlds=384,
            history_comparisons=histories,
            bitwise_history_comparisons=len(histories),
            exact_feature_scalars=count,
            unchanged_calibration_readers=curve_count,
            new_evaluation_responses_not_required_to_match_old_strengths=True,
        ),
    )


def test_readouts(panel, readouts):
    matched = readouts[RULE["primary_panel"]]["resolution_matched"]
    late = readouts[RULE["paired_comparator_panel"]]["resolution_matched"]
    paired = [
        assay.paired_report(a["outcomes"]["voltage"], b["outcomes"]["voltage"]) | dict(level=i)
        for i, (a, b) in enumerate(zip(matched, late, strict=True))
    ]
    primary = matched[2]["outcomes"]["voltage"]
    joint = primary["arms"]["joint"]["joint"]
    assert primary["feature_count"] == 15 and joint["cases"] == 32
    drift = readouts[RULE["primary_panel"]]["score_stability"]["voltage"]["resolution_matched"][
        "cases"
    ]
    drift = [r for r in drift if r["arm"] == "joint"]
    assert len(drift) == 64
    evidence(
        f"{PREFIX}-readouts",
        dict(
            status="passed",
            panels=readouts,
            paired_primary_and_late=paired,
            primary_joint_target_met=joint["all_cases_correct_and_resolved"],
            primary_joint_finest_score_stability=all(
                r["finest_steps_within_score_limits"] for r in drift
            ),
            primary_joint_finest_decisions_agree=all(r["finest_decisions_agree"] for r in drift),
            primary_panel=RULE["primary_panel"],
            comparator_panel=RULE["paired_comparator_panel"],
            preparations=RULE["preparations"],
            task_meanings=RULE["task_meanings"],
            primary_observations_after_both_cues=True,
            fresh_evaluation_strengths=True,
            scientific_outcome_is_not_an_acceptance_gate=True,
        ),
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, vectors in modes.items()
            for identity, value in vectors.items()
        },
    )


def test_contrasts(panel):
    contrasts = assay.paired_contrasts(ROWS, panel["maps"], RULE)
    assert len(contrasts) == 1100
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


def test_controls(panel, readouts):
    assert panel["counts"] == dict(no_cue=602, unused_label_pairs=616, disconnected_windows=616)
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
                    for a in arms
                    for t in a["tasks"].values()
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
