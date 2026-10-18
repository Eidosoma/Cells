"""Five local-channel conditions using the established windowed qualification."""

import copy
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

from cells.core.batch_windows import plan_batch_windows
from cells.core.specs import parse_spec
from tests.unit import test_channel_compensation as inherited
from tests.unit import test_source_order_long as shared
from tests.unit import test_source_order_pulse_spacing as spacing_checks
from tests.unit import test_source_order_selected as support_checks
from validation.assays import distributed_timing, two_task
from validation.assays import local_channel as assay

ROOT_RULE = assay.protocol()
RULE, ROWS, PREFIX = ROOT_RULE, [], "local-channel"
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
evidence = reference.common.evidence
compare_historical_window = inherited.compare_historical_window


@pytest.fixture(scope="module", params=[c["id"] for c in assay.CONDITIONS], autouse=True)
def configured_harness(request):
    rule = assay.condition_rule(ROOT_RULE, request.param)
    rows, prefix = assay.cases(rule), f"local-channel-{request.param}"
    assert shared.POLICY.window_steps == rule["window_steps"]
    with pytest.MonkeyPatch.context() as patch:
        for module in (sys.modules[__name__], inherited, shared, spacing_checks, support_checks):
            for key, value in dict(RULE=rule, ROWS=rows, PREFIX=prefix).items():
                patch.setattr(module, key, value)
        for module in (inherited, shared, spacing_checks, support_checks):
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
test_host_history_boundaries = inherited.test_host_history_boundaries
test_host_reader_views = inherited.test_host_reader_views
test_prerequisite = shared.test_source_order_long_prerequisite
test_panel = spacing_checks.test_panel
test_controls = spacing_checks.test_controls
test_contrasts = spacing_checks.test_contrasts
test_replay = shared.test_source_order_long_replay
test_historical_reproduction = inherited.test_historical_reproduction
test_calibration = inherited.test_calibration


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
        ("work", "worlds_per_backend", 540),
        ("original_reader_binding", "completion_sha256", "0" * 64),
    ):
        changed = copy.deepcopy(ROOT_RULE)
        changed[section][key] = value
        with pytest.raises(AssertionError):
            assay.validate_plan(changed)
    for key, value in (("channel_scale", 0.8), ("cell_ids", [1, 2, 6])):
        changed = copy.deepcopy(ROOT_RULE)
        changed["conditions"][1][key] = value
        with pytest.raises(AssertionError):
            assay.validate_plan(changed)
        with pytest.raises(ValueError):
            assay.condition_rule(changed, "source1_flank_lower")
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
    condition = RULE["condition"]
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
            mask = np.isin(owner + 1, condition["cell_ids"])
            assert not np.any(mask & np.isin(owner + 1, [1, 4, 7]))
            expected[mask] *= condition["channel_scale"]
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
    total_estimate = len(assay.CONDITIONS) * archive_estimate
    assert retained < RULE["resources"]["max_retained_array_estimate_bytes"]
    assert total_estimate + 8 * 1024**3 < RULE["resources"]["artifact_and_cache_bytes"]
    assert total_estimate == assay.PLAN["execution"]["estimated_uncompressed_archive_bytes"]
    assert len(plans) == 45
    assert (
        max(p["estimated_working_bytes"] for p in plans)
        < RULE["resources"]["max_batch_working_bytes"]
    )
    area = np.asarray(BASE["model"]["tissue"]["membrane_area"])
    capacity = area * np.asarray(BASE["model"]["channel_permeability"])
    evidence(
        f"{PREFIX}-design",
        dict(
            status="passed",
            condition=condition,
            cases=ROWS,
            plans=plans,
            paired_source_mapping=mapping,
            work=RULE["work"],
            uncompressed_archive_estimate_all_conditions_bytes=total_estimate,
            retained_array_estimate_bytes=retained,
            only_selected_flank_channels_changed=True,
            all_other_inputs_exact=True,
            calibration_only=True,
            new_evaluation_responses=0,
            selected_membrane_area_m2=float(area[mask].sum()),
            relative_total_area_weighted_permeability_change=float(
                capacity[mask].sum() / capacity.sum() * (condition["channel_scale"] - 1)
            ),
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

    names = [c["id"] for c in assay.CONDITIONS]
    for winner in names[1:]:
        good = {
            n: report(1.9e-9 if n == "sham" else 2.1e-9 if n == winner else 1.8e-9) for n in names
        }
        answer = assay.combined_selection(dict(cpu=good, gpu=good))
        assert answer["selected_condition"] == winner
        for score in (1.8e-9, 1.9e-9, 1.9e-9 + 0.5e-15, 2e-9):
            altered = good | {winner: report(score)}
            assert (
                assay.combined_selection(dict(cpu=altered, gpu=altered))["selected_condition"]
                == "sham"
            )
        alternate = next(n for n in names[1:] if n != winner)
        tied = good | {alternate: report(2.1e-9)}
        assert assay.combined_selection(dict(cpu=tied, gpu=tied))["selected_condition"] == "sham"
        disagree = good | {alternate: report(2.2e-9)}
        assert (
            assay.combined_selection(dict(cpu=good, gpu=disagree))["selected_condition"] == "sham"
        )
        mismatch = good | {winner: report(2.1e-9 + 2e-15)}
        assert (
            assay.combined_selection(dict(cpu=good, gpu=mismatch))["selected_condition"] == "sham"
        )
        bad = copy.deepcopy(good)
        bad[winner]["panels"]["selected320"]["calibration_null_controls"][0]["tasks"]["timing"][
            "resolved_cases"
        ] = 1
        assert assay.combined_selection(dict(cpu=bad, gpu=bad))["selected_condition"] == "sham"
    for invalid in (-1, float("nan"), float("inf")):
        with pytest.raises(ValueError):
            assay.combined_selection(dict(cpu=good, gpu=good | dict(sham=report(invalid))))
    with pytest.raises(ValueError):
        assay.combined_selection(dict(cpu=good))
    for missing in names:
        with pytest.raises(ValueError):
            assay.combined_selection(
                dict(cpu=good, gpu={n: v for n, v in good.items() if n != missing})
            )
    bad = copy.deepcopy(good)
    bad[winner]["panels"]["selected320"]["calibration_null_controls"] = []
    with pytest.raises(ValueError, match="null controls"):
        assay.combined_selection(dict(cpu=good, gpu=bad))
    changed = copy.deepcopy(good)
    for value in changed.values():
        value["panels"]["long512"]["score_V"] = 999
    assert assay.combined_selection(dict(cpu=changed, gpu=changed)) == answer
    maps, _ = assay.load_reference(spacing_checks.synthetic_calibration(), ROWS)
    original = assay.calibration_geometry(ROWS, maps, RULE)
    larger = {
        k: dict(voltage={i: v * 2 for i, v in mode["voltage"].items()}) for k, mode in maps.items()
    }
    paired = assay.paired_geometry(assay.calibration_geometry(ROWS, larger, RULE), original)
    for p in paired.values():
        assert len(p["task_groups"]) == 12
        for group in p["task_groups"]:
            assert group["half_distance_change_V"] == pytest.approx(
                group["original"]["half_distance_V"], rel=1e-13, abs=0
            )
    evidence(
        f"{PREFIX}-decision-known-answers",
        dict(
            status="passed",
            all_four_candidates_can_win=True,
            ties_backend_disagreement_and_null_failures_keep_sham=True,
            only_primary_ranks=True,
            invalid_and_incomplete_scores_rejected=True,
            per_timestep_paired_geometry_known_answer=True,
        ),
    )


@pytest.fixture(scope="module")
def calibration(panel):
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    with np.load(root / "channel-compensation-sham-calibration.npz", allow_pickle=False) as saved:
        impaired, loaded = assay.load_reference(saved, ROWS)
    original_root = Path(assay.ORIGINAL_BINDING["root"]) / "evidence" / "cpu"
    with np.load(
        original_root / "source-order-pulse-confirmation-readouts.npz", allow_pickle=False
    ) as saved:
        original, original_loaded = assay.load_reference(saved, ROWS, assay.ORIGINAL_ROWS)
    target = assay.calibration_geometry(ROWS, panel["maps"], RULE)
    impaired_geometry = assay.calibration_geometry(ROWS, impaired, RULE)
    archived = json.loads((root / "channel-compensation-sham-calibration.json").read_text())
    assert impaired_geometry == archived["geometry"]
    views = {
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
        for key, modes in impaired.items():
            for identity, expected in modes["voltage"].items():
                np.testing.assert_array_equal(panel["maps"][key]["voltage"][identity], expected)
    return dict(
        status="passed",
        geometry=target,
        impaired_reference_geometry=impaired_geometry,
        original_reference_geometry=assay.calibration_geometry(ROWS, original, RULE),
        paired_geometry_change=assay.paired_geometry(target, impaired_geometry),
        reader_views=views,
        score_stability={
            name: {
                mode: distributed_timing.score_changes(
                    [entry["views"][mode] for entry in levels], RULE["score_stability"]
                )
                for mode in levels[0]["views"]
            }
            for name, levels in views.items()
        },
        impaired_calibration_arrays_loaded=loaded,
        original_cpu_calibration_arrays_loaded=original_loaded,
        null_controls_unresolved=assay.nulls_unresolved(target),
        heldout_arrays_loaded=0,
        heldout_cases_evaluated=0,
        scientific_outcome_is_not_an_acceptance_gate=True,
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
                        Path(EVIDENCE) / backend / f"local-channel-{c['id']}-calibration.json"
                    ).read_text()
                )["geometry"]
                for c in assay.CONDITIONS
            }
            for backend in ("cpu", "gpu")
        }
        # All condition tests above have completed; final runner acceptance is still required.
        evidence(
            "local-channel-selection",
            dict(
                status="passed",
                selection=assay.combined_selection(reports),
                source_binding=RULE["prior_binding"],
                design_plan_sha256=RULE["design_plan_sha256"],
                protocol_sha256=assay.digest(assay.PROTOCOL_PATH),
                automatic_followup=False,
            ),
        )
