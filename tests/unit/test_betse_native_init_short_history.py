"""Private protocol/metadata controls only; no issued parent/native body."""

import os
import sys
from contextlib import contextmanager
from types import FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_short_history as stage
from tests.unit import test_betse_native_init_retained_world as guard_model
from tests.unit import test_betse_native_init_short_history_diagnostics as diagnostic_controls
from validation.betse import betse_native_init_short_history_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Explicit immutable native-blocked software release required")
    namespace = dict(vars(guard_model), software=software, _RAW_GUARDS=[])
    fn = FunctionType(guard_model.blocked.__wrapped__.__code__, namespace)
    with contextmanager(fn)(request, tmp_path, monkeypatch):
        yield


@pytest.mark.parametrize("count", (True, False, 0, -1, 65, 1.0, "2", None))
def test_short_history_count_is_explicit_bounded_and_not_bool(count):
    with pytest.raises(ValueError):
        stage._count(count)


@pytest.mark.parametrize("count", (1, 2, 5, 64))
def test_short_history_private_timeline_is_contiguous_and_retains_each_actual_label(count):
    ledger = stage._Timeline(count)
    labels = [float(index) / 3 for index in range(count)]
    for ordinal, label in enumerate(labels):
        assert ledger.begin(label, ordinal % 2 == 0) == (ordinal, label, ordinal % 2 == 0)
        record = stage.Iteration(
            ordinal,
            label,
            ordinal % 2 == 0,
            NS(identity=str(ordinal)),
            ordinal + 1,
            ordinal + 1,
            object(),
        )
        ledger.end(record)
        assert ledger.records[-1] is record and ledger.current is None
    assert ledger.completed == count
    assert all(row.source_time is label for row, label in zip(ledger.records, labels, strict=True))
    with pytest.raises(ValueError):
        ledger.begin(99.0, False)
    assert ledger.invalid and ledger.completed == count


@pytest.mark.parametrize(
    "fault", ("reentry", "wrong_ordinal", "equal_time", "wrong_sample", "end_first")
)
def test_short_history_private_timeline_refusal_is_sticky_and_keeps_partial(fault):
    ledger = stage._Timeline(2)
    label = float("0.3141592653589793")
    if fault != "end_first":
        ledger.begin(label, True)
    if fault == "reentry":
        with pytest.raises(ValueError):
            ledger.begin(label, True)
    else:
        actual = float(str(label)) if fault == "equal_time" else label
        assert fault != "equal_time" or actual is not label
        row = stage.Iteration(
            1 if fault == "wrong_ordinal" else 0,
            actual,
            fault != "wrong_sample",
            NS(identity="partial"),
            0,
            0,
            object(),
        )
        with pytest.raises(ValueError):
            ledger.end(row)
    assert ledger.invalid and ledger.completed == 0 and ledger.records == []
    with pytest.raises(ValueError):
        ledger.begin(label, True)


def test_short_history_protocol_token_records_value_changes_not_only_same_object_refs():
    ledger = stage._Timeline(2)
    label = float("0.00125")
    ledger.begin(label, True)
    row = stage.Iteration(0, label, True, NS(identity="before"), 3, 1, object())
    ledger.end(row)
    token = ledger.token()
    row.after.identity = "after"
    assert ledger.token() != token
    assert ledger.records[0] is row


@pytest.mark.parametrize("roots", (False, True))
def test_short_history_callback_claims_are_per_iteration_and_never_clear_prior_claims(roots):
    ledger = stage._Timeline(2)
    claims = stage._CallbackClaims(ledger, roots=roots)
    item = "progressed_next" if roots else (123, "progressed_next", (17, 17, 2, 24))
    ranged = "progress_ranged" if roots else (456, "progress_ranged", (3, 3, 2, 20))
    claims.add(ranged)
    for ordinal in range(2):
        label = float(ordinal)
        ledger.begin(label, True)
        assert item not in claims
        claims.add(item)
        assert item in claims
        with pytest.raises(ValueError):
            claims.add(item)
        ledger.end(stage.Iteration(ordinal, label, True, NS(identity=str(ordinal)), 0, 0, object()))
    assert len(claims.data) == 3 and ranged in claims
    with pytest.raises(ValueError):
        claims.add(item)


@pytest.mark.parametrize("operation", ("construct", "hydrate", "phase", "trial"))
def test_short_history_owner_cannot_be_supplied_decoded_or_recycled(operation):
    owner = object.__new__(stage.ShortHistoryOwner)
    with pytest.raises((TypeError, stage.ShortHistoryRejected)):
        if operation == "construct":
            stage.ShortHistoryOwner()
        elif operation == "hydrate":
            owner.__reduce_ex__(4)
        else:
            getattr(owner, operation)


def test_short_history_missing_real_contracts_refuse_before_foreign_parent_inspection(monkeypatch):
    monkeypatch.setattr(
        stage.base.previous, "_authority", lambda value: pytest.fail("No parent entry")
    )
    with pytest.raises(stage.ShortHistoryRejected) as caught:
        stage.from_electrical(object(), iterations=2, law_id=stage.LAW_ID)
    assert caught.value.stage == "integration_held"
    assert (
        stage.PARENT_CLAIM is stage.PARENT_CHECK is stage.RUNTIME_BEGIN is stage.RUNTIME_END is None
    )
    assert not stage._CONSUMED and not stage._RETIRED


def test_short_history_release_and_bad_count_refuse_before_any_engine_or_provider(monkeypatch):
    monkeypatch.setattr(stage, "_ready", lambda: pytest.fail("No readiness entry"))
    with pytest.raises(stage.ShortHistoryRejected, match="held"):
        stage.prepare(object())
    with pytest.raises(ValueError):
        stage.from_electrical(object(), iterations=True, law_id=stage.LAW_ID)


def test_short_history_source_mode_preserves_literal_body_calendar_and_default_first_step():
    assert stage.base.SELECTION != stage.SELECTION
    plan = stage.source_plan()
    assert plan["one_fresh_parent_one_original_loop"]
    assert plan["original_calendar_dt_sampled_set_and_objects_unchanged"]
    assert plan["completed_first_step_owner_is_not_a_parent"]
    assert not plan["physical_checkpoint_full_INIT_or_scientific_admission"]
    assert plan["runtime_entry_names_unadopted"] == (None, None)
    assert software._cpu(4) == 4 and software._cpu(6) == 6
    for unavailable in (True, False, 0, 2, 4.0, "4", None):
        with pytest.raises(ValueError):
            software._cpu(unavailable)


@pytest.mark.parametrize("visits", (0, 1))
def test_short_history_observer_waits_for_real_outer_iteration_before_begin(visits, monkeypatch):
    frame = sys._getframe()
    calls = []
    context = NS(
        runtime={},
        molecule_codes=frozenset(),
        frames={id(frame): {"returned": False}},
        timeline=stage._Timeline(2),
        loop_frame=frame,
        loop_visits=visits,
        setup_frame=None,
    )
    monkeypatch.setattr(stage, "_guard", lambda value: None)
    monkeypatch.setattr(
        stage, "_begin", lambda actual, actual_frame: calls.append((actual, actual_frame))
    )
    stage._observe(context, frame, "line", None)
    assert calls == ([(context, frame)] if visits else [])


# One collection module gives every plain diagnostic the same per-case native
# and operator/RNG blockade. Their real producer remains the paired test file.
for _name, _function in vars(diagnostic_controls).items():
    if _name.startswith("test_") and type(_function) is FunctionType:
        globals()[_name] = _function
