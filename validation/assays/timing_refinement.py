"""Fixed-time refinement of the original cue panel, without changing readers."""

import json
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec
from cells.core.specs import parse_spec
from validation.assays import two_task as assay
from validation.betse.spatial_active.refinement import digest

PROTOCOL_PATH = Path(__file__).with_name("timing_refinement_protocol.json")


def protocol():
    return json.loads(PROTOCOL_PATH.read_text())


def baseline(rule):
    result = assay.baseline(rule)
    assert digest(assay.ROOT / rule["source_protocol"]) == rule["source_protocol_sha256"]
    saved = json.loads((Path(rule["prior_binding"]["root"]) / "registration.json").read_text())
    assert saved["component_protocol"] == assay.protocol()
    return result | dict(unchanged_assay_protocol=True)


def definition(base, row, level, backend, rule):
    if type(level) is not int or not 0 <= level < len(rule["dt_s"]):
        raise ValueError("Unregistered refinement level")
    # Generate controls using the original physical clock before changing dt.
    raw = assay.definition(base, row, backend, assay.protocol())
    raw["execution"]["dt"] = rule["dt_s"][level]
    return raw


def batch(base, rows, level, backend, rule):
    return BatchSpec(
        tuple(
            WorldSpec(r["world_id"], parse_spec(definition(base, r, level, backend, rule)))
            for r in rows
        ),
        max_worlds=rule["batch_worlds"],
        max_padded_steps=rule["batch_worlds"]
        * (
            round(rule["duration_s"] / rule["dt_s"][level]) + len(assay.protocol()["control_steps"])
        ),
        max_working_bytes=rule["resources"]["max_batch_working_bytes"],
    )


def contrast_report(early, late, criteria):
    """Compare the paired RESPONSE, not merely the large background voltages.

    Classification is descriptive. A failed stability/resolution criterion must
    remain a result, rather than failing or retuning an otherwise valid run.
    """
    early, late = np.asarray(early), np.asarray(late)
    if (
        early.ndim != 2
        or early.shape != late.shape
        or early.shape[0] != 3
        or not early.shape[1]
        or not np.isfinite(early).all()
        or not np.isfinite(late).all()
    ):
        raise ValueError("Expected three finite paired voltage vectors of equal shape")
    delta = late - early
    norms = np.linalg.norm(delta, axis=1)
    changes = np.asarray([np.linalg.norm(delta[0] - delta[1]), np.linalg.norm(delta[1] - delta[2])])
    coarse_fine = float(np.linalg.norm(delta[0] - delta[2]))
    allowance = 4 * criteria["voltage_atol_V"] + 2 * criteria["voltage_rtol"] * (
        np.max(np.abs(early), axis=0) + np.max(np.abs(late), axis=0)
    )
    allowance_l2 = float(np.linalg.norm(allowance))
    ratio = float(changes[0] / changes[1]) if changes[1] else None
    order_resolved = bool(np.min(changes) > criteria["resolved_error_multiple"] * allowance_l2)
    limit = min(
        criteria["absolute_change_limit_l2_V"], criteria["relative_change_limit"] * norms[2]
    )
    signal_resolved = bool(norms[2] > criteria["resolved_signal_min_l2_V"])
    fine_stable = bool(changes[1] <= limit)
    null = not np.any(delta)
    return dict(
        timing_contrast_V=delta.tolist(),
        contrast_l2_V=norms.tolist(),
        contrast_max_abs_V=np.max(np.abs(delta), axis=1).tolist(),
        successive_changes_l2_V=changes.tolist(),
        coarse_to_fine_change_l2_V=coarse_fine,
        middle_to_fine_relative_change=float(changes[1] / norms[2]) if norms[2] else None,
        stability_limit_l2_V=float(limit),
        comparison_allowance_l2_V=allowance_l2,
        successive_change_ratio=ratio,
        first_order_resolved=(
            bool(criteria["ratio_min"] <= ratio <= criteria["ratio_max"])
            if order_resolved
            else None
        ),
        order_comparison_resolved=order_resolved,
        finest_signal_above_declared_floor=signal_resolved,
        finest_steps_within_stability_limits=fine_stable,
        original_dt_within_stability_limits=bool(coarse_fine <= limit),
        coarse_fine_direction_cosine=(
            float(delta[0] @ delta[2] / (norms[0] * norms[2])) if norms[0] and norms[2] else None
        ),
        outcome=(
            "zero_timing_contrast"
            if null
            else "below_declared_reader_scale"
            if not signal_resolved
            else "stable_at_finest_tested_steps"
            if fine_stable
            else "step_sensitive"
        ),
    )


def paired_reports(rows, voltages, rule):
    """All strengths and locations; omit the timing-only unused location label."""
    reports = []
    for early in rows:
        if early["timing"] or (early["arm"] == "timing_only" and early["location"]):
            continue
        late = next(
            r
            for r in rows
            if r["timing"] == 1
            and all(r[k] == early[k] for k in ("arm", "preparation", "location"))
        )
        reports.append(
            dict(
                arm=early["arm"],
                location=early["location"],
                amplitude=early["amplitude"],
                preparation=early["preparation"],
                world_ids=[early["world_id"], late["world_id"]],
                null_control=early["arm"] in ("no_cue", "location_only"),
                independent_biological_replicates=0,
                **contrast_report(
                    [voltages[level, early["world_id"]] for level in range(3)],
                    [voltages[level, late["world_id"]] for level in range(3)],
                    rule["contrast"],
                ),
            )
        )
    return reports
