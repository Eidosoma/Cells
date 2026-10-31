"""Prospective first-interval checks; require previously qualified initial inputs.

No fixture generator is provided. These sources are not collected or run during
preparation. The external index must bind actual retained qualification files.
"""

import json
import os
from pathlib import Path

import pytest

from cells.processes import stable_seed_partition_advance as advance

CASES = (
    "uniform-two-species",
    "unequal-clefts-readback-defects",
    "two-cell-four-species",
    "four-cell-reordered-gradient",
)


def declaration():
    return dict(
        kind=advance.INPUT_KIND,
        opted_in_law=advance.LAW_ID,
        initial_preparation_identity="0" * 64,
        step_policy="first_original_EventGrid_interval_no_subdivision@1",
        requested_end_time_s=None,
        provided_checkpoint_state_or_operators=None,
        caller="prospective-metadata-control",
    )


def approved_input(case):
    """Load existing qualified artifacts; never create scientific case inputs."""
    path = Path(os.environ["CELLS_STABLE_SEED_PARTITION_ADVANCE_INITIAL_INDEX"])
    index = json.loads(path.read_text())
    assert index["kind"] == "qualified_existing_initial_partition_inputs@1"
    entry = index["cases"][case]

    def original(name):
        return Path(entry[name]).read_text()

    qualification = advance.InitialQualification(
        original("source_review"),
        original("numerical_qualification"),
        original("manifest"),
        original("input"),
        original("report"),
        entry["first_interval_acceptance"],
    )
    advance._qualification_gate(qualification)
    from cells.core import finite_ecm_polygon_preparation as physical
    from cells.processes import finite_ecm_polygon_geometry as finite
    from cells.processes import stable_seed_explicit_ecm_partition as constructor
    from cells.processes import stable_seed_partition_physiology_bridge as initial

    incoming = json.loads(original("input"))
    assert incoming["case_id"] == case and set(incoming) == {"case_id", "request", "preparation"}
    raw, prepared = incoming["request"], incoming["preparation"]
    c = raw["constructor_candidate"]
    original_request = constructor.Request(
        constructor.freeze(raw["constructor_request"]["declaration"]),
        raw["constructor_request"]["identity"],
    )
    candidate = constructor.Candidate(
        c["request_identity"],
        finite.Request(**c["partition_request"]),
        finite.Binding(**c["partition_binding"]),
        constructor.freeze(c["construction"]),
        constructor.freeze(c["owner_maps"]),
        constructor.freeze(c["conservation"]),
        constructor.freeze(c["provenance"]),
        c["identity"],
    )
    proof = raw["geometry_evidence"]
    geometry_evidence = initial.GeometryEvidence(
        proof["source_review_json"],
        proof["prepared_manifest_json"],
        proof["input_json"],
        proof["report_json"],
        constructor.freeze(proof["caller_acceptance"]),
    )
    initial_request = initial.Request(
        original_request,
        candidate,
        geometry_evidence,
        constructor.freeze(raw["declaration"]),
        raw["identity"],
    )
    preparation = initial.Preparation(
        prepared["request_identity"],
        physical.Preparation(**prepared["physical_preparation"]),
        constructor.freeze(prepared["conversions"]),
        constructor.freeze(prepared["initial_snapshot"]),
        constructor.freeze(prepared["provenance"]),
        prepared["identity"],
    )
    return advance.bind(
        initial_request, preparation, qualification, entry["first_interval_declaration"]
    )


def preserve_failure(root, name, error):
    root.mkdir(parents=True, exist_ok=True)
    with (root / (name + ".json")).open("x") as stream:
        json.dump(
            dict(
                code=error.code,
                stage=error.stage,
                original=advance.plain(error.original),
                partial=advance.plain(error.partial),
            ),
            stream,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def test_pending_numerical_qualification_blocks_all_scientific_work(monkeypatch):
    monkeypatch.setattr(advance, "INITIAL_NUMERICAL_QUALIFICATION_SHA256", None)
    proof = advance.InitialQualification("{}", "{}", "{}", "{}", "{}", {})
    with pytest.raises(advance.AdvanceRejected) as caught:
        advance.bind(None, None, proof, declaration())
    assert type(caught.value) is advance.AdvanceRejected
    assert caught.value.code == "upstream_initial_numerical_qualification_pending"
    assert caught.value.stage == "initial_qualification"
    assert caught.value.partial["numerical_execution_permitted"] is False


def test_first_interval_declaration_cannot_supply_new_physics_or_cached_state():
    for name in ("temperature_K", "dt_s", "area_m2", "concentration_mM"):
        raw = declaration()
        raw[name] = 1.0
        with pytest.raises(advance.AdvanceRejected) as caught:
            advance._declaration(raw)
        assert caught.value.code == "complete_first_interval_declaration_required"
        assert caught.value.stage == "declaration"
    raw = declaration()
    raw["provided_checkpoint_state_or_operators"] = {}
    with pytest.raises(advance.AdvanceRejected) as caught:
        advance._declaration(raw)
    assert caught.value.code == "first_interval_cannot_adopt_state_or_operators"
    assert caught.value.stage == "declaration"


def test_endpoint_metadata_requires_explicit_finite_binary64():
    for invalid in (False, 0, 0.0, -1.0, float("inf"), float("nan")):
        raw = declaration()
        raw["requested_end_time_s"] = invalid
        with pytest.raises(advance.AdvanceRejected) as caught:
            advance._declaration(raw)
        assert caught.value.code == "explicit_finite_positive_endpoint_or_original_grid_required"
        assert caught.value.stage == "declaration"


def test_continuation_is_outside_first_interval_scope():
    with pytest.raises(advance.AdvanceRejected) as caught:
        advance.require_continuation(None)
    assert caught.value.code == "first_interval_candidate_does_not_admit_continuation"
    assert caught.value.stage == "scope"


@pytest.mark.parametrize("case", CASES)
def test_first_interval_preserves_units_layout_and_matches_existing_cells_driver(case):
    request = approved_input(case)
    import numpy as np

    from cells.core import surface_tissue_spec as schema
    from cells.core.runner import run

    result = advance.advance(request)
    spec = schema.parse(request.initial_preparation.physical_preparation.definition)
    # The existing four caller declarations each have one original interval.
    assert spec.experiment.end_time == spec.execution.dt == result.checkpoint.time
    ordinary = run(spec)
    assert (
        result.checkpoint.step_index == 1
        and result.checkpoint.event_index == ordinary.final.event_index
    )
    for actual, expected in zip(result.checkpoint.state, ordinary.final.state, strict=True):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray(expected))
    assert advance.digest(result.checkpoint_record["layout"]) == advance.digest(
        request.initial_preparation.initial_snapshot["layout"]
    )
    assert len(result.evidence["trials"]) == 5
    assert all(row["rhs_evaluated"] for row in result.evidence["trials"][:4])
    assert result.evidence["trials"][-1]["role"] == "unmasked_endpoint"
    assert result.provenance["parameters_or_units_changed"] is False
    assert result.provenance["automatic_refinement"] is False
    assert result.provenance["native_equivalence"] is False


def test_rejected_cells_stage_retains_unmasked_trials_without_accepting_old_state(
    monkeypatch, tmp_path
):
    request = approved_input(CASES[0])
    from cells.models import surface_tissue as model

    original_trial = advance._cells_trial
    original_guard = model.control_domain_valid

    def inject(*args, **kwargs):
        calls = [0]

        def fail_second(*values, **options):
            calls[0] += 1
            return False if calls[0] == 2 else original_guard(*values, **options)

        with monkeypatch.context() as patch:
            patch.setattr(model, "control_domain_valid", fail_second)
            return original_trial(*args, **kwargs)

    monkeypatch.setattr(advance, "_cells_trial", inject)
    with pytest.raises(advance.AdvanceRejected) as caught:
        advance.advance(request)
    preserve_failure(tmp_path, "rejected-cells-trial", caught.value)
    assert caught.value.code == "existing_cells_rk4_trial_or_endpoint_domain_failed"
    assert caught.value.stage == "cells_stage_domain"
    raw = caught.value.partial["cells_checked_kernel_return"]
    assert raw["accepted_domain"]["data_hex"] == "00"
    assert len(raw["trials"]) == 5 and raw["trials"][1]["rhs_evaluated"] is False
    assert raw["trials"][-1]["role"] == "unmasked_endpoint"
    assert caught.value.partial["accepted"] is False


def test_observer_failure_keeps_completed_field_and_rhs_before_later_work(tmp_path):
    request = approved_input(CASES[0])

    def fail(name, value):
        if name == "trial-0-rhs-return":
            raise RuntimeError("injected completed-RHS observer failure")

    with pytest.raises(advance.AdvanceRejected) as caught:
        advance.advance(request, observer=fail)
    preserve_failure(tmp_path, "completed-rhs-observer-failure", caught.value)
    assert caught.value.original["type"] == "RuntimeError"
    assert caught.value.original["reason"] == "injected completed-RHS observer failure"
    assert "trial-0-field-return" in caught.value.partial
    assert "trial-0-rhs-return" in caught.value.partial
    assert caught.value.partial["cells_trial_roster"][0]["rhs_evaluated"] is True
    assert caught.value.partial["accepted"] is False
