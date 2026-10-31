"""Synthetic continuing-history and sealing contracts, with native work blocked."""

import hashlib
import os
from dataclasses import replace
from pathlib import Path

import pytest

from validation.betse.betse_native_single_cell_core_synthetic import (
    SyntheticCaptureFailure,
    SyntheticRecoveryFailure,
    core,
    event_signature,
    exercise,
    harness,
    inject_capture,
    save,
)


@pytest.fixture
def evidence(request, tmp_path):
    folder = os.environ.get("CELLS_DEC_PREREQUISITE_EVIDENCE")
    root = Path(folder) if folder else tmp_path
    root.mkdir(parents=True, exist_ok=True)
    path = root / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:20]
    path.mkdir(exist_ok=False)
    save(
        path, "case", dict(nodeid=request.node.nodeid, synthetic_only=True, scientific_credit=False)
    )
    return path


def assert_no_native(h):
    assert h.calls["native_attempts"] == []
    assert h.calls["real_rng_attempts"] == []


@pytest.mark.parametrize(
    "case",
    [
        "exact",
        "exact-warning",
        "sequence",
        "kind",
        "method",
        "depth",
        "payload",
        "order",
        "missing-event",
        "warning-text",
        "warning-missing",
        "warning-extra",
    ],
)
def test_software_actual_prefix_and_warnings(case, monkeypatch, evidence):
    warning = (
        "synthetic parent warning"
        if case in {"exact-warning", "warning-text", "warning-missing", "warning-extra"}
        else None
    )
    h = harness(monkeypatch, warning=warning)
    expected = list(h.parent.events)
    if case in {"sequence", "kind", "method", "depth"}:
        key = case
        value = 19 if case in {"sequence", "depth"} else "corrupt-" + case
        expected[0] = replace(expected[0], **{key: value})
    elif case == "payload":
        expected[0] = replace(expected[0], payload=h.original_snapshot(dict(marker="corrupt")))
    elif case == "order":
        expected.reverse()
    elif case == "missing-event":
        expected.pop()
    elif case == "warning-text":
        h.parent.warnings = ("different parent warning",)
    elif case == "warning-missing":
        h.parent.warnings = ()
    elif case == "warning-extra":
        h.parent.warnings += ("unemitted parent warning",)
    h.parent.events = tuple(expected)
    before = (
        event_signature(h.parent.events),
        h.parent.warnings,
        h.parent.constructed_cache.identity,
        h.parent.cache.identity,
    )
    save(evidence, "input", dict(case=case, request=h.request))
    if case in {"exact", "exact-warning"}:
        result = exercise(h, evidence)
        assert result.core_source_completed is True
        assert result.status == "source_core_operators_completed_unqualified"
        assert h.calls["synthetic_core"] == 1
        assert event_signature(result.events[:2]) == event_signature(h.parent.events)
        assert result.warnings == h.parent.warnings
        assert not core.state_record(result)["executable_DEC_parent_admitted"]
        save(
            evidence,
            "outcome",
            dict(result=result, calls=h.calls, native_execution=False, synthetic_only=True),
        )
    else:
        with pytest.raises(core.CorePrerequisiteRejected) as caught:
            exercise(h, evidence)
        error = caught.value
        assert error.parent_request is h.base and error.parent_state is h.parent
        assert error.stage == error.source_stage == "pre_mesh_event_replay"
        assert error.capture_error is None and isinstance(error.source_error, ValueError)
        assert error.__cause__ is error.source_error
        assert error.trial is not None and not error.trial.core_source_completed
        assert error.trial.before_cache.identity == h.parent.cache.identity
        assert error.trial.stream_after.identity == h.parent.stream_after.identity
        assert error.trial.point_ids == h.parent.retained_point_ids
        assert not any(e.kind == "owned_single_cell_core_start" for e in error.trial.events)
        assert h.calls["synthetic_core"] == 0
        save(
            evidence,
            "outcome",
            dict(
                error=error,
                trial=error.trial,
                calls=h.calls,
                native_execution=False,
                synthetic_only=True,
            ),
        )
    assert before == (
        event_signature(h.parent.events),
        h.parent.warnings,
        h.parent.constructed_cache.identity,
        h.parent.cache.identity,
    )
    assert_no_native(h)


@pytest.mark.parametrize("outcome", ["success", "failure"])
@pytest.mark.parametrize(
    "point",
    [
        "final_snapshot",
        "final_stream",
        "State",
        "state_record",
        "identity_digest",
        "identity_replace",
    ],
)
def test_software_finalization_failure_keeps_both_outcomes(outcome, point, monkeypatch, evidence):
    h = harness(monkeypatch, outcome=outcome)
    save(evidence, "input", dict(request=h.request, source_outcome=outcome, capture_point=point))
    inject_capture(monkeypatch, h, point)
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.stage == "evidence_capture" and error.capture_stage == point
    assert error.parent_request is h.base and error.parent_state is h.parent
    assert error.trial is None
    assert error.capture_error is h.errors["capture"]
    assert error.capture_error.__cause__ is h.errors["capture_cause"]
    partial = error.partial
    assert partial["capture_complete"] is False and partial["complete_state_available"] is False
    assert (
        partial["last_successful_snapshots"]["constructed"].identity
        == h.parent.constructed_cache.identity
    )
    assert partial["last_successful_snapshots"]["before"].identity == h.parent.cache.identity
    if point == "final_snapshot":
        assert "final" not in partial["last_successful_snapshots"]
    else:
        assert partial["last_successful_snapshots"]["final"] is not None
    assert partial["collected_events"]
    assert event_signature(partial["collected_events"][:2]) == event_signature(h.parent.events)
    assert partial["point_ids"] == h.parent.retained_point_ids
    assert partial["raw_cache"]["synthetic_marker"] == "ready"
    assert partial["raw_rng_state"][0] == "synthetic_rng"
    assert partial["raw_warning_records"] == ()
    assert partial["recovery_errors"] == []
    assert partial["capture_exception_chain"]["nodes"][0] is h.errors["capture"]
    assert partial["capture_exception_chain"]["nodes"][1] is h.errors["capture_cause"]
    if outcome == "failure":
        assert error.source_error is h.errors["source"]
        assert error.source_error.__cause__ is h.errors["source_cause"]
        assert error.__cause__ is h.errors["source"]
        assert error.source_stage == "create_core_operators"
        assert partial["source_exception_chain"]["nodes"] == (
            h.errors["source"],
            h.errors["source_cause"],
        )
        assert not partial["core_method_returned"]
    else:
        assert error.source_error is None and error.__cause__ is h.errors["capture"]
        assert error.source_stage == "core_finite_and_source_axis_admission"
        assert partial["source_exception_chain"]["nodes"] == ()
        assert partial["core_method_returned"]
    assert h.calls["capture_attempts"] == [point]
    assert h.calls["synthetic_core"] == 1
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error, partial=partial, calls=h.calls, native_execution=False, synthetic_only=True
        ),
    )


def test_software_unprintable_source_exception_is_retained(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="bad-str")
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.trial is None and error.capture_stage == "State"
    assert error.source_error is h.errors["source"] and error.__cause__ is h.errors["source"]
    assert isinstance(error.capture_error, SyntheticCaptureFailure)
    assert error.source_error.__cause__ is h.errors["source_cause"]
    assert not error.partial["complete_state_available"]
    assert error.partial["last_successful_snapshots"]["final"] is not None
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error,
            partial=error.partial,
            calls=h.calls,
            native_execution=False,
            synthetic_only=True,
        ),
    )


def test_software_inherited_observer_capture_preserves_source_chain(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="observation-failure")
    inject_capture(monkeypatch, h, "final_snapshot")
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.source_error is h.errors["boundary"] and error.__cause__ is h.errors["boundary"]
    assert error.partial["source_exception_chain"]["nodes"] == (
        h.errors["boundary"],
        h.errors["source"],
        h.errors["source_cause"],
    )
    assert error.capture_error is h.errors["capture"]
    assert error.trial is None and not error.partial["complete_state_available"]
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error,
            partial=error.partial,
            calls=h.calls,
            native_execution=False,
            synthetic_only=True,
        ),
    )


def test_software_cyclic_source_chain_does_not_recurse(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="cycle")
    inject_capture(monkeypatch, h, "final_snapshot")
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.partial["source_exception_chain"]["cycle"]
    assert error.partial["source_exception_chain"]["nodes"] == (
        h.errors["source"],
        h.errors["source_cause"],
    )
    assert error.source_error is h.errors["source"] and error.capture_error is h.errors["capture"]
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error,
            partial=error.partial,
            calls=h.calls,
            native_execution=False,
            synthetic_only=True,
        ),
    )


def test_software_raw_recovery_failure_does_not_mask_originals(monkeypatch, evidence):
    h = harness(monkeypatch, outcome="failure")
    inject_capture(monkeypatch, h, "final_snapshot")
    # Change only the raw accessor used after failed sealing. Stream snapshots
    # in the synthetic driver deliberately do not call this method.
    rng_type = core.np.random.RandomState(0).__class__

    def fail_raw(self):
        raise SyntheticRecoveryFailure("raw RNG accessor unavailable")

    monkeypatch.setattr(rng_type, "get_state", fail_raw)
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.source_error is h.errors["source"] and error.capture_error is h.errors["capture"]
    assert error.__cause__ is h.errors["source"] and error.trial is None
    recovery = error.partial["recovery_errors"]
    assert len(recovery) == 1 and recovery[0][0] == "raw_rng_state"
    assert isinstance(recovery[0][1], SyntheticRecoveryFailure)
    assert "raw_rng_state" not in error.partial and error.partial["original_rng"] is not None
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error,
            partial=error.partial,
            calls=h.calls,
            native_execution=False,
            synthetic_only=True,
        ),
    )


def test_software_initial_capture_failure_retains_parent(monkeypatch, evidence):
    h = harness(monkeypatch)
    inject_capture(monkeypatch, h, "initial_snapshot")
    with pytest.raises(core.CorePrerequisiteRejected) as caught:
        exercise(h, evidence)
    error = caught.value
    assert error.parent_request is h.base and error.parent_state is h.parent
    assert error.capture_stage == "initial_snapshot" and error.source_error is None
    assert error.trial is None and error.__cause__ is h.errors["capture"]
    assert error.partial["last_successful_snapshots"] == dict(constructed=None, before=None)
    assert error.partial["collected_events"] == ()
    assert (
        h.calls["synthetic_constructor"]
        == h.calls["synthetic_pre_mesh"]
        == h.calls["synthetic_core"]
        == 0
    )
    assert h.calls["capture_attempts"] == ["initial_snapshot"]
    assert_no_native(h)
    save(
        evidence,
        "outcome",
        dict(
            error=error,
            partial=error.partial,
            calls=h.calls,
            native_execution=False,
            synthetic_only=True,
        ),
    )
