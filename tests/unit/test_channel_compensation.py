"""Three compensation conditions using the established CPU/L4 windowed harness."""

import copy
import json
import sys
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from cells.core.batch_windows import plan_batch_windows
from cells.core.specs import parse_spec
from tests.unit import test_source_order_long as shared
from tests.unit import test_source_order_pulse_spacing as spacing_checks
from tests.unit import test_source_order_selected as support_checks
from validation.assays import channel_compensation as assay
from validation.assays import distributed_timing, two_task

ROOT_RULE = assay.protocol()
RULE, ROWS, PREFIX = ROOT_RULE, [], "channel-compensation"
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
evidence = reference.common.evidence


def compare_historical_window(value, row, level):
    full = RULE["condition"]["id"] == "sham"
    if not full and value.start_step != 0:
        return None
    old = assay.source_row(row)
    start, stop = (value.start_step, value.final.step_index) if full else (0, 0)
    observed = value.observations.times if full else []
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    saved = assay.archived_segment(root, level, old["world_id"], start, stop, observed)
    actual = reference.arrays(value)
    assert actual.keys() == saved.keys()
    count = 0
    for name, expected in saved.items():
        if full or not name.startswith("observed__"):
            np.testing.assert_array_equal(actual[name] if full else actual[name][:1], expected)
            count += expected.size
    return dict(
        level=level,
        world_id=row["world_id"],
        source_world_id=old["world_id"],
        start_step=start,
        stop_step=stop,
        compared_scalars=count,
        bitwise=True,
        initial_states_only=not full,
    )


@pytest.fixture(scope="module", params=[c["id"] for c in assay.CONDITIONS], autouse=True)
def configured_harness(request):
    rule = assay.condition_rule(ROOT_RULE, request.param)
    rows, prefix = assay.cases(rule), f"channel-compensation-{request.param}"
    with pytest.MonkeyPatch.context() as patch:
        for module in (sys.modules[__name__], shared, spacing_checks, support_checks):
            for key, value in dict(RULE=rule, ROWS=rows, PREFIX=prefix).items():
                patch.setattr(module, key, value)
        for module in (shared, spacing_checks, support_checks):
            for key, value in dict(assay=assay, BASE=BASE, evidence=evidence).items():
                patch.setattr(module, key, value)
        patch.setattr(support_checks, "SOURCE", assay.SOURCE)
        patch.setattr(shared, "compare_historical_window", compare_historical_window)
        yield rule


@pytest.fixture(scope="module")
def authenticated_source():
    return assay.baseline(ROOT_RULE)


@pytest.fixture(scope="module")
def prior(configured_harness, authenticated_source):
    return authenticated_source | dict(condition=configured_harness["condition"])


@pytest.fixture(scope="module")
def panel(configured_harness, prior, tmp_path_factory):
    return shared.panel.__wrapped__(prior, tmp_path_factory)


test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive = shared.test_host_source_order_long_archive_boundaries
test_host_support = support_checks.test_host_support
test_host_calibration_isolation = spacing_checks.test_host_calibration_isolation
test_host_geometry = spacing_checks.test_host_geometry_known_answers
test_prerequisite = shared.test_source_order_long_prerequisite
test_panel = spacing_checks.test_panel
test_controls = spacing_checks.test_controls
test_contrasts = spacing_checks.test_contrasts
test_replay = shared.test_source_order_long_replay


def test_host_plan_binding():
    report = assay.validate_plan(ROOT_RULE)
    pending = copy.deepcopy(ROOT_RULE)
    pending["prior_binding"]["completion_sha256"] = None
    with pytest.raises(ValueError, match="before simulation"):
        assay.baseline(pending)
    for section, key, value in (
        ("reader", "voltage_margin_V", 1e-9),
        ("readout", "cell_ids", [1, 2, 3, 4, 5]),
        ("cue_timing", "late_pulse_us", [104, 112]),
        ("work", "worlds_per_backend", 660),
    ):
        changed = copy.deepcopy(ROOT_RULE)
        changed[section][key] = value
        with pytest.raises(AssertionError):
            assay.validate_plan(changed)
    changed = copy.deepcopy(ROOT_RULE)
    changed["conditions"][1]["channel_scale"] = 0.8
    with pytest.raises(AssertionError):
        assay.validate_plan(changed)
    with pytest.raises(ValueError):
        assay.condition_rule(changed, "channel_lower")
    with pytest.raises(ValueError):
        assay.condition_rule(ROOT_RULE, "unregistered")
    evidence(f"{PREFIX}-binding", report)


def test_host_design_and_resources():
    assert len(ROWS) == len({r["world_id"] for r in ROWS}) == 60
    assert {r["split"] for r in ROWS} == {"calibration"}
    assert Counter(r["arm"] for r in ROWS) == dict.fromkeys(assay.geometry.ARMS, 12)
    original = copy.deepcopy(BASE)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    plans, mapping, archive_estimate = [], [], 0
    scale = RULE["condition"]["channel_scale"]
    for level, dt in enumerate(RULE["dt_s"]):
        steps = round(RULE["duration_s"] / dt)
        for row in ROWS:
            old = assay.source_row(row)
            saved = json.loads(
                (root / (assay.world_name(level, old["world_id"]) + ".json")).read_text()
            )
            assert saved["status"] == "passed" and saved["case"] == old
            raw = assay.definition(BASE, row, level, BACKEND, RULE)
            owner = np.asarray(saved["input"]["model"]["tissue"]["cell_owner"])
            expected = np.asarray(saved["input"]["model"]["channel_permeability"]).copy()
            expected[(owner != 0) & (owner != 3)] *= scale
            np.testing.assert_array_equal(raw["model"]["channel_permeability"], expected)
            restored = copy.deepcopy(raw)
            restored["model"]["channel_permeability"] = saved["input"]["model"][
                "channel_permeability"
            ]
            assert restored == saved["input"]
            spec = parse_spec(raw)
            mapping.append(
                dict(level=level, world_id=row["world_id"], source_world_id=old["world_id"])
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
        for start in range(0, len(ROWS), 4):
            batch = assay.batch(BASE, ROWS[start : start + 4], level, BACKEND, RULE)
            bounded = plan_batch_windows(batch, shared.POLICY)
            plans.append(
                dict(
                    level=level,
                    world_ids=[w.world_id for w in batch.worlds],
                    estimated_working_bytes=bounded.estimated_working_bytes,
                )
            )
    assert BASE == original
    retained = 16 * (2 * per_state * (RULE["window_steps"] + 1) + field_bytes * 12)
    retained += len(ROWS) * 3 * 6 * (15 + 5 + 21 + 15 + 15) * 8
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert 3 * archive_estimate + 8 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert len(plans) == 45
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            condition=RULE["condition"],
            cases=ROWS,
            plans=plans,
            paired_source_mapping=mapping,
            work=RULE["work"],
            uncompressed_archive_estimate_all_conditions_bytes=3 * archive_estimate,
            retained_array_estimate_bytes=retained,
            only_remote_channel_permeability_changed=True,
            all_other_inputs_exact=True,
            calibration_only=True,
            new_evaluation_responses=0,
        ),
    )


def test_host_history_boundaries(monkeypatch):
    row = next(r for r in ROWS if r["arm"] == "joint")
    arrays = dict(state__voltage=np.arange(3)[:, None] * 1e-9, observed__voltage=np.ones((1, 1)))
    actual = {k: v.copy() for k, v in arrays.items()}
    full = RULE["condition"]["id"] == "sham"

    def saved(root, level, identity, start, stop, times):
        assert stop == (2 if full else 0)
        return {
            k: v.copy() if full else v[:0] if k.startswith("observed__") else v[:1]
            for k, v in arrays.items()
        }

    monkeypatch.setattr(assay, "archived_segment", saved)
    monkeypatch.setattr(reference, "arrays", lambda _: actual)
    value = SimpleNamespace(
        start_step=0,
        final=SimpleNamespace(step_index=2),
        observations=SimpleNamespace(times=np.array([1e-6])),
    )
    assert compare_historical_window(value, row, 0)["bitwise"]
    actual["state__voltage"][1:] += 999
    if full:
        with pytest.raises(AssertionError):
            compare_historical_window(value, row, 0)
    else:
        assert compare_historical_window(value, row, 0)["stop_step"] == 0
    actual["state__voltage"][0] += 1
    with pytest.raises(AssertionError):
        compare_historical_window(value, row, 0)
    if not full:
        value.start_step = 1
        assert compare_historical_window(value, row, 0) is None
    evidence(
        f"{PREFIX}-history-boundaries",
        dict(
            status="passed",
            full_sham_checked=full,
            candidate_evolution_allowed=not full,
            corrupt_initial_state_rejected=True,
        ),
    )


def test_host_decision_known_answers():
    def report(score):
        return dict(
            panels={
                p: dict(
                    score_V=score,
                    calibration_null_controls=[
                        dict(
                            arm=arm,
                            level=level,
                            tasks={t: dict(resolved_cases=0) for t in ("location", "timing")},
                        )
                        for arm in ("no_cue", "disconnected")
                        for level in range(3)
                    ],
                )
                for p in assay.PANELS
            }
        )

    good = dict(sham=report(1.9e-9), channel_lower=report(1.8e-9), channel_higher=report(2.1e-9))
    answer = assay.combined_selection(dict(cpu=good, gpu=good))
    assert answer["selected_condition"] == "channel_higher"
    for change in (1.8e-9, 1.9e-9, 1.9e-9 + 0.5e-15, 2e-9):
        rows = good | dict(channel_higher=report(change))
        assert assay.combined_selection(dict(cpu=rows, gpu=rows))["selected_condition"] == "sham"
    tied = good | dict(channel_lower=report(2.1e-9))
    assert assay.combined_selection(dict(cpu=tied, gpu=tied))["selected_condition"] == "sham"
    other = good | dict(channel_lower=report(2.2e-9))
    assert assay.combined_selection(dict(cpu=good, gpu=other))["selected_condition"] == "sham"
    different = good | dict(channel_higher=report(2.1e-9 + 2e-15))
    assert assay.combined_selection(dict(cpu=good, gpu=different))["selected_condition"] == "sham"
    bad_null = copy.deepcopy(good)
    bad_null["channel_higher"]["panels"]["selected320"]["calibration_null_controls"][0]["tasks"][
        "timing"
    ]["resolved_cases"] = 1
    assert (
        assay.combined_selection(dict(cpu=bad_null, gpu=bad_null))["selected_condition"] == "sham"
    )
    for invalid in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            assay.combined_selection(dict(cpu=good, gpu=good | dict(sham=report(invalid))))
    with pytest.raises(ValueError):
        assay.combined_selection(dict(cpu=good))
    missing_null = copy.deepcopy(good)
    missing_null["channel_higher"]["panels"]["selected320"]["calibration_null_controls"] = []
    with pytest.raises(ValueError, match="null controls"):
        assay.combined_selection(dict(cpu=good, gpu=missing_null))
    changed = copy.deepcopy(good)
    for r in changed.values():
        r["panels"]["long512"]["score_V"] = 999
    assert assay.combined_selection(dict(cpu=changed, gpu=changed)) == answer
    evidence(
        f"{PREFIX}-decision-known-answers",
        dict(
            status="passed",
            ties_backend_disagreement_and_null_failures_keep_sham=True,
            only_primary_ranks=True,
            invalid_and_incomplete_scores_rejected=True,
        ),
    )


def test_host_reader_views():
    maps, _ = assay.load_reference(spacing_checks.synthetic_calibration(), ROWS)
    original = maps[0, "selected320"]["voltage"]
    target = {k: v + np.pad([0, 50e-6], (0, 13)) for k, v in original.items()}
    report = assay.calibration_views(ROWS, original, target, 2e-9)
    assert (
        report["views"]["raw_frozen_source"]["arms"]["joint"]["joint"]["correct_and_resolved"] < 12
    )
    assert (
        report["views"]["reference_assisted"]["arms"]["joint"]["joint"]["correct_and_resolved"]
        == 12
    )
    assert (
        report["views"]["condition_calibrated"]["arms"]["joint"]["joint"]["correct_and_resolved"]
        == 12
    )
    altered = {k: v.copy() for k, v in target.items()}
    for row in ROWS:
        if row["arm"] == "joint":
            altered[row["world_id"]][1] += 30e-6
    after = assay.calibration_views(ROWS, original, altered, 2e-9)
    assert (
        after["views"]["reference_assisted"]["arms"]["joint"]["joint"]["correct_and_resolved"] < 12
    )
    for mode in ("raw_frozen_source", "reference_assisted"):
        for arm in assay.geometry.ARMS:
            assert (
                report["views"][mode]["arms"][arm]["calibration"]
                == after["views"][mode]["arms"][arm]["calibration"]
            )
    assert report["heldout_cases"] == 0 and report["fitting_points_are_not_confirmation"]
    evidence(
        f"{PREFIX}-reader-views-known-answers",
        dict(
            status="passed",
            source_curves_fixed=True,
            shared_offset_removed_only_by_reference_assistance=True,
            changed_cue_response_visible=True,
            calibration_points_not_misreported_as_holdouts=True,
        ),
    )


def test_historical_reproduction(panel):
    histories = panel["prefixes"]
    full = RULE["condition"]["id"] == "sham"
    assert len(histories) == (840 if full else 180)
    for level, dt in enumerate(RULE["dt_s"]):
        for row in ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            assert windows[-1]["stop_step"] == (round(RULE["duration_s"] / dt) if full else 0)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert all(r["source_world_id"] == assay.source_row(row)["world_id"] for r in windows)
    evidence(
        f"{PREFIX}-historical-reproduction",
        dict(
            status="passed",
            history_comparisons=histories,
            full_sham_worlds=180 if full else 0,
            initial_state_only_worlds=0 if full else 180,
        ),
    )


@pytest.fixture(scope="module")
def calibration(panel):
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    with np.load(root / "source-order-coupling-lower-readouts.npz", allow_pickle=False) as saved:
        impaired, loaded = assay.load_reference(saved, ROWS)
    original_root = Path(assay.SOURCE_ROOT["prior_binding"]["root"]) / "evidence" / "cpu"
    original_rows = [r for r in assay.coupling.SOURCE_ROWS if r["split"] == "calibration"]
    with np.load(
        original_root / "source-order-pulse-confirmation-readouts.npz", allow_pickle=False
    ) as saved:
        original, original_loaded = assay.load_reference(saved, ROWS, original_rows)
    target = assay.calibration_geometry(ROWS, panel["maps"], RULE)
    background_views = {
        name: [
            assay.calibration_views(
                ROWS,
                original[level, name]["voltage"],
                panel["maps"][level, name]["voltage"],
                RULE["reader"]["voltage_margin_V"],
            )
            for level in range(3)
        ]
        for name in assay.PANELS
    }
    if RULE["condition"]["id"] == "sham":
        for key, values in impaired.items():
            for identity, expected in values["voltage"].items():
                np.testing.assert_array_equal(panel["maps"][key]["voltage"][identity], expected)
    return dict(
        status="passed",
        geometry=target,
        impaired_reference_geometry=assay.calibration_geometry(ROWS, impaired, RULE),
        original_reference_geometry=assay.calibration_geometry(ROWS, original, RULE),
        reader_views=background_views,
        score_stability={
            name: {
                mode: distributed_timing.score_changes(
                    [entry["views"][mode] for entry in levels], RULE["score_stability"]
                )
                for mode in levels[0]["views"]
            }
            for name, levels in background_views.items()
        },
        impaired_calibration_arrays_loaded=loaded,
        original_cpu_calibration_arrays_loaded=original_loaded,
        null_controls_unresolved=assay.nulls_unresolved(target),
        heldout_arrays_loaded=0,
        heldout_cases_evaluated=0,
        scientific_outcome_is_not_an_acceptance_gate=True,
    )


def test_calibration(calibration, panel):
    assert len(calibration["impaired_calibration_arrays_loaded"]) == 540
    assert len(calibration["original_cpu_calibration_arrays_loaded"]) == 540
    evidence(
        f"{PREFIX}-calibration",
        calibration,
        {
            f"{level}__{name}__{mode}__{identity}": value
            for (level, name), modes in panel["maps"].items()
            for mode, values in modes.items()
            for identity, value in values.items()
        },
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
            for mode, values in modes.items():
                for identity, value in values.items():
                    expected = saved[f"{level}__{name}__{mode}__{identity}"]
                    np.testing.assert_allclose(
                        value, expected, atol=tol["voltage_atol_V"], rtol=tol["cpu_gpu_rtol"]
                    )
                    feature_count += value.size
                    if mode == "voltage":
                        cpu_voltages[level, name, identity] = expected.copy()
    previous = json.loads((cpu / f"{PREFIX}-calibration.json").read_text())
    comparisons = []
    for name in assay.PANELS:
        for actual, expected in zip(
            calibration["reader_views"][name], previous["reader_views"][name], strict=True
        ):
            rows = assay.compare_reader_predictions(actual["views"], expected["views"])
            assert all(r["max_score_difference"] <= 1e-12 for r in rows)
            for mode in ("raw_frozen_source", "reference_assisted"):
                for arm in assay.geometry.ARMS:
                    assert (
                        actual["views"][mode]["arms"][arm]["calibration"]
                        == expected["views"][mode]["arms"][arm]["calibration"]
                    )
            comparisons.append(dict(panel=name, comparisons=rows))
    cpu_contrasts = json.loads((cpu / f"{PREFIX}-contrasts.json").read_text())["pairs"]
    maximum, differences = 0.0, []
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
            k
            for k in (
                "outcome",
                "first_order_resolved",
                "finest_signal_above_declared_floor",
                "finest_steps_within_stability_limits",
            )
            if actual[k] != expected[k]
        ]
        if fields:
            differences.append(
                dict(panel=name, task=actual["task"], world_ids=[a, b], differing_fields=fields)
            )
    evidence(
        f"{PREFIX}-cpu-gpu",
        dict(
            status="passed",
            worlds=180,
            compared_scalars=count,
            compared_feature_scalars=feature_count,
            reader_comparisons=comparisons,
            max_paired_contrast_error_over_budget=maximum,
            paired_contrast_outcome_differences=differences,
            physical_tolerances_unchanged=True,
            heldout_cases_evaluated=0,
        ),
    )
    if RULE["condition"]["id"] == assay.CONDITIONS[-1]["id"]:
        reports = {
            backend: {
                c["id"]: json.loads(
                    (
                        Path(EVIDENCE)
                        / backend
                        / f"channel-compensation-{c['id']}-calibration.json"
                    ).read_text()
                )["geometry"]
                for c in assay.CONDITIONS
            }
            for backend in ("cpu", "gpu")
        }
        # All condition tests above have completed; final runner acceptance is still required.
        evidence(
            "channel-compensation-selection",
            dict(
                status="passed",
                selection=assay.combined_selection(reports),
                source_binding=RULE["prior_binding"],
                design_plan_sha256=RULE["design_plan_sha256"],
                protocol_sha256=assay.digest(assay.PROTOCOL_PATH),
                automatic_followup=False,
            ),
        )
