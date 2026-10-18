"""Fresh-strength confirmation using the qualified windowed CPU/L4 checks."""

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from tests.unit import test_source_order_long as shared
from tests.unit import test_source_order_selected as selected
from tests.unit import test_source_order_spanning as history
from validation.assays import source_order_pulse_confirmation as assay
from validation.assays import source_order_pulse_spacing as spacing
from validation.assays import template_readout, two_task

RULE, SOURCE, ROWS = assay.protocol(), assay.SOURCE, assay.cases()
BASE = json.loads((two_task.ROOT / RULE["template"]).read_text())
BACKEND, EVIDENCE, reference = shared.BACKEND, shared.EVIDENCE, shared.reference
PREFIX = "source-order-pulse-confirmation"
evidence = reference.common.evidence
compare_historical_window = history.compare_historical_window


@pytest.fixture(scope="module", autouse=True)
def configured_harness():
    """Bind existing checks to this frozen cohort without changing their source."""
    assert shared.POLICY.window_steps == RULE["window_steps"]
    with pytest.MonkeyPatch.context() as patch:
        for module in (shared, selected, history):
            for key, value in dict(
                RULE=RULE, ROWS=ROWS, BASE=BASE, PREFIX=PREFIX, assay=assay, evidence=evidence
            ).items():
                patch.setattr(module, key, value)
        patch.setattr(selected, "SOURCE", SOURCE)
        patch.setattr(history, "SOURCE", SOURCE)
        patch.setattr(shared, "compare_historical_window", compare_historical_window)
        patch.setattr(shared, "evidence", history.inherited_evidence)
        yield


panel = shared.panel
readouts = shared.readouts
transfers = shared.transfers
test_host_reader_isolation = shared.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = shared.test_host_source_order_long_archive_boundaries
test_host_reference_answers = shared.test_host_source_order_long_reference_known_answers
test_host_history_boundaries = history.test_host_history_boundaries
test_host_design_and_resources = selected.test_host_design_and_resources
test_host_support = selected.test_host_support
test_host_paired_known_answers = selected.test_host_paired_known_answers
test_prerequisite = shared.test_source_order_long_prerequisite
test_replay = shared.test_source_order_long_replay
test_panel = history.test_panel
test_readouts = selected.test_readouts
test_controls = history.test_controls
test_contrasts = selected.test_contrasts
test_baseline_transfer = shared.test_source_order_long_baseline_transfer
test_cpu_gpu = shared.test_source_order_long_cpu_gpu


@pytest.fixture(scope="module")
def prior():
    return assay.baseline(RULE)


def test_host_selection_binding(tmp_path):
    report = assay.selected_design(RULE)
    assert report["selected_onset_separation_us"] == 104
    strengths = RULE["evaluation_design"]["strengths"]
    assert strengths == [
        0.403125,
        0.453125,
        0.503125,
        0.553125,
        0.646875,
        0.696875,
        0.746875,
        0.796875,
    ]
    np.testing.assert_allclose(np.array(strengths) + strengths[::-1], 1.2, rtol=0, atol=3e-16)
    np.testing.assert_allclose(np.diff(strengths[:4]), 0.05, rtol=0, atol=1e-16)
    assert min(assay.times(RULE, "selected320")) > 120e-6
    for section, key, value in (
        ("cue_timing", "late_pulse_us", [104, 112]),
        ("cue_timing", "early_pulse_us", [8, 20]),
        ("observation_times_us", "selected320", [128, 192, 320]),
        ("reader", "voltage_margin_V", 1e-9),
        ("readout", "cell_ids", [1, 2, 3, 4, 5]),
        ("evaluation_design", "strengths", SOURCE["preparations"]),
        ("selection_binding", "sha256", "corrupt"),
        ("work", "worlds_per_backend", 180),
    ):
        changed = copy.deepcopy(RULE)
        changed[section][key] = value
        with pytest.raises(AssertionError):
            assay.selected_design(changed)
    for change in (
        dict(primary_panel="long512"),
        dict(paired_comparator_panels=["long512"]),
        dict(preparations=SOURCE["preparations"]),
        dict(automatic_followup=True),
    ):
        with pytest.raises(AssertionError):
            assay.selected_design(RULE | change)
    # Integrity must fail before accepting a forged selection, even if a caller
    # changes the direct binding to match the forged document.
    original = Path(RULE["prior_binding"]["root"])
    fake = tmp_path / "selection"
    fake.mkdir()
    for name in ("registration.json", "completion.json", "result.json", "component-protocol.json"):
        (fake / name).write_bytes((original / name).read_bytes())
    relative = RULE["selection_binding"]["relative_path"]
    destination = fake / relative
    destination.parent.mkdir(parents=True)
    destination.write_text('{"status":"invented"}\n')
    changed = copy.deepcopy(RULE)
    changed["prior_binding"]["root"] = str(fake)
    changed["selection_binding"]["sha256"] = assay.digest(destination)
    with pytest.raises(AssertionError):
        assay.selected_design(changed)
    evidence(
        f"{PREFIX}-selection-binding",
        report
        | dict(
            changed_pulses_schedule_margin_support_cohort_and_selection_rejected=True,
            selection_bound_to_completed_manifest=True,
            new_strengths_fixed_before_simulation=True,
            previous_confirmation_is_a_different_cohort=True,
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
            before, duration = assay.historical_source(row)
            assert windows[0]["start_step"] == 0 and all(r["bitwise"] for r in windows)
            assert all(r["source_world_id"] == before["world_id"] for r in windows)
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(duration / dt)
    root = Path(RULE["prior_binding"]["root"]) / "evidence" / BACKEND
    count, old_features = 0, {}
    with np.load(root / "source-order-pulse-spacing-calibration.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            for row in ROWS:
                old, duration = assay.historical_source(row)
                if duration != 512e-6:
                    continue
                for mode, values in modes.items():
                    expected = saved[f"{level}__{name}__{mode}__{old['world_id']}"]
                    np.testing.assert_array_equal(values[row["world_id"]], expected)
                    count += expected.size
                    if row["split"] == "calibration" and mode == "voltage":
                        old_features[level, name, row["world_id"]] = expected.copy()
    curve_count = 0
    for name, group in readouts.items():
        for level, report in enumerate(group["resolution_matched"]):
            for arm, value in report["outcomes"]["voltage"]["arms"].items():
                tasks, training, _ = template_readout.split(ROWS, arm)
                expected = template_readout.TemplateReader.fit(
                    np.stack([old_features[level, name, r["world_id"]] for r in training]),
                    np.array([[r[t] for t in tasks] for r in training]),
                    [r["amplitude"] for r in training],
                    minimum_margin=RULE["reader"]["voltage_margin_V"],
                ).to_dict()
                assert value["calibration"]["template_reader"] == expected
                curve_count += 1
    old_geometry = json.loads((root / "source-order-pulse-spacing-calibration.json").read_text())[
        "candidate"
    ]
    assert spacing.calibration_geometry(ROWS, panel["maps"], RULE) == old_geometry
    assert count == 117576 and curve_count == 90
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
            frozen_calibration_geometry_reproduced=True,
            new_evaluation_responses_not_required_to_match_old_strengths=True,
        ),
    )
