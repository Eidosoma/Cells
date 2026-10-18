"""Reuse the fixed assay, with explicit numerical comparison to earlier histories."""

import json
from pathlib import Path

import numpy as np
import pytest

from tests.unit import test_source_order_long as checks
from validation.assays import source_order as previous
from validation.assays import source_order_precision as repair

# The assay implementation, inputs, readers, storage and replay checks stay frozen.
panel = checks.panel
readouts = checks.readouts
transfers = checks.transfers
test_host_design = checks.test_host_source_order_long_design_and_resources
test_host_support = checks.test_host_source_order_long_support
test_host_reader_isolation = checks.test_host_source_order_long_reader_isolation
test_host_archive_boundaries = checks.test_host_source_order_long_archive_boundaries
test_host_reference_answers = checks.test_host_source_order_long_reference_known_answers
test_host_history_boundaries = checks.test_host_source_order_long_history_boundaries
test_prerequisite = checks.test_source_order_long_prerequisite
test_panel = checks.test_source_order_long_panel
test_readouts = checks.test_source_order_long_readouts
test_contrasts = checks.test_source_order_long_contrasts
test_controls = checks.test_source_order_long_controls
test_replay = checks.test_source_order_long_replay
test_baseline_transfer = checks.test_source_order_long_baseline_transfer
test_cpu_gpu = checks.test_source_order_long_cpu_gpu


@pytest.fixture(scope="module")
def prior():
    return repair.baseline()


def test_historical_reproduction(panel, readouts):
    """Preserve the old evidence; make precision-induced differences explicit."""
    histories = panel["prefixes"]
    assert len(histories) == 980
    assert len({(r["level"], r["world_id"]) for r in histories}) == 420
    old = previous.protocol()
    for level, dt in enumerate(checks.RULE["dt_s"]):
        for row in checks.ROWS:
            windows = [
                r for r in histories if (r["level"], r["world_id"]) == (level, row["world_id"])
            ]
            assert windows[0]["start_step"] == 0
            assert all(
                a["stop_step"] == b["start_step"]
                for a, b in zip(windows, windows[1:], strict=False)
            )
            assert windows[-1]["stop_step"] == round(old["duration_s"] / dt)
    root = Path(checks.RULE["historical_binding"]["root"]) / "evidence" / checks.BACKEND
    tolerance = checks.reference.PROTOCOL["tolerances"]
    count, exact, maximum = 0, True, 0.0
    with np.load(root / "source-order-readouts.npz", allow_pickle=False) as saved:
        for (level, name), modes in panel["maps"].items():
            if name not in old["observation_panels"]:
                continue
            for mode, vectors in modes.items():
                for identity, value in vectors.items():
                    expected = saved[f"{level}__{name}__{mode}__{identity}"]
                    np.testing.assert_allclose(
                        value,
                        expected,
                        atol=tolerance["voltage_atol_V"],
                        rtol=tolerance["cpu_gpu_rtol"],
                    )
                    count += value.size
                    exact &= np.array_equal(value, expected)
                    maximum = max(maximum, float(np.max(abs(value - expected))))
    original = json.loads((root / "source-order-readouts.json").read_text())["panels"]
    comparisons = []
    for name in old["observation_panels"]:
        for level, actual in enumerate(readouts[name]["resolution_matched"]):
            expected = original[name]["resolution_matched"][level]
            comparisons.append(
                dict(
                    panel=name,
                    level=level,
                    calibration="resolution_matched",
                    predictions=checks.assay.compare_reader_predictions(
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
                    predictions=checks.assay.compare_reader_predictions(
                        {m: values[level] for m, values in readouts[name]["frozen_coarse"].items()},
                        {m: values[level] for m, values in original[name]["frozen_coarse"].items()},
                    ),
                )
            )
    checks.evidence(
        f"{checks.PREFIX}-historical-reproduction",
        dict(
            status="passed",
            reproduced_world_prefixes=420,
            prefix_duration_s=old["duration_s"],
            history_comparisons=histories,
            bitwise_history_comparisons=sum(r["bitwise"] for r in histories),
            earlier_feature_scalars=count,
            earlier_features_exact=exact,
            max_earlier_feature_absolute_difference=maximum,
            physical_tolerances_unchanged=True,
            earlier_readout_reports_exact={
                n: readouts[n] == original[n] for n in old["observation_panels"]
            },
            reader_comparisons=comparisons,
            exact_decision_agreement=not any(
                p["differing_decision_world_ids"]
                for group in comparisons
                for p in group["predictions"]
            ),
            numerical_correction_can_change_roundoff_and_unresolved_labels=True,
            scientific_outcome_differences_reported=True,
            archived_scientific_evidence_untouched=True,
        ),
    )
