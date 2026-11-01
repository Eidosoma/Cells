"""Blocked extended-domain contract controls; no fourth numerical state exists."""

import copy
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_material_domain as domain
from tests.unit.test_betse_normal_ecm_molecule_current_continuity import (
    no_formatter_execution as no_formatter_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_checkpoint import (
    no_warm_source_calls as no_warm_source_calls,
)
from tests.unit.test_betse_normal_ecm_molecule_kinetic_reload_reference import (
    no_original_execution as no_original_execution,
)
from validation.betse import betse_normal_current_native as archives
from validation.betse import betse_normal_ecm_molecule_material_domain as validation


@pytest.fixture(autouse=True)
def no_material_bodies(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Legacy numerical body/verifier forbidden in extended contract controls"
        )

    for module, names in (
        (domain.dispatch, ("bind", "initialize", "advance", "verify", "state")),
        (domain.transport, ("bind", "initialize", "advance", "verify", "state")),
        (domain.dispatch.material, ("bind", "state", "step", "drive", "validate_binding")),
        (domain.dispatch.calcium, ("bind", "initialize", "advance", "_material_step", "calcium")),
        (domain.dispatch.full, ("bind", "initialize", "advance", "reconstruct")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbidden)


def budget_values():
    return dict(
        source_calls=4,
        max_material_attempts=4,
        max_owner_verifications=10,
        max_nested_source_invocations=1000,
        max_retained_bytes=2**20,
        wall_seconds=480.0,
        provenance="Synthetic control; no extended numerical authority",
    )


def pair(kind="transport", cursor=0):
    """Unowned typed metadata, never passed to a legacy numerical verifier."""
    owner = domain.transport if kind == "transport" else domain.dispatch
    a = owner.ions.freeze(np.array([[1.0, 2.0]], np.float64))
    component = plain_record(
        owner.calcium.Binding, inputs=dict(synthetic=True), identity="synthetic-component"
    )
    binding = owner.Binding(component, owner.ions.freeze(dict(synthetic=True)), "")
    binding = replace(binding, identity=owner.ions.digest(owner.binding_record(binding)))
    material = owner.material.State(
        "synthetic-material",
        cursor,
        owner.material.Values(*(a for _ in owner.material.Values._fields)),
        "synthetic-material-state",
    )
    field = owner.full.FieldStage(
        component.identity, dict(full_material=a), None, None, None, "synthetic-field"
    )
    shared = dict(complete_text="retain every synthetic owner field", array=a)
    parent = owner.State(
        binding.identity,
        material,
        field,
        dict(molecules=shared, grn=shared),
        dict(gj_block=a, NaKATP_block=a),
        owner.calcium.RateCache(False, None),
        owner.calcium.Clock(owner.ions.freeze(np.array([0.0, 1.5, 3.0])), cursor, float(cursor)),
        "",
    )
    return binding, replace(parent, identity=owner.ions.digest(owner.state_record(parent)))


def calendar(count=4):
    return domain.calendars.bind(
        phase="SIM",
        step_count=count,
        dt_s=1.0,
        sample_stride=1.0,
        requested_duration_s=count + 0.25,
        provenance="Synthetic declared original calendar, not trajectory authority",
    )


def retained(kind="transport"):
    return domain.retain(domain.budget(**budget_values()), calendar(), *pair(kind))


def keep(path, value):
    archives.write_archive(
        path,
        domain.ions.data(
            dict(
                value,
                synthetic_only=True,
                numerical_owner_admission=False,
                independent_biological_cases=0,
                numerical_entries=0,
                historical_credit=False,
            )
        ),
    )


def test_reached_caps_and_required_shared_source_seams_are_bound_without_execution(tmp_path):
    plan = validation.source_plan(Path(domain.__file__).resolve().parents[3])
    assert len(plan["reached_caps"]) >= 20
    assert plan["numeric_calls"] == 0 and plan["metadata_contract_only"] is True
    assert (
        "material.state_and_step_explicit_domain_preserving_absolute_index"
        in plan["required_seams"]
    )
    assert any(row["function"] == "validate_cached_channels" for row in plan["reached_caps"])
    keep(tmp_path / "source-cap-trace", plan)


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_calls", 3),
        ("source_calls", True),
        ("source_calls", 4.0),
        ("source_calls", 1_000_001),
        ("max_material_attempts", 3),
        ("max_material_attempts", True),
        ("max_material_attempts", float("inf")),
        ("max_owner_verifications", 0),
        ("max_owner_verifications", False),
        ("max_nested_source_invocations", 0),
        ("max_nested_source_invocations", 4),
        ("max_nested_source_invocations", float("nan")),
        ("max_retained_bytes", 0),
        ("max_retained_bytes", 2**30),
        ("wall_seconds", 0.0),
        ("wall_seconds", float("inf")),
        ("wall_seconds", float("nan")),
        ("wall_seconds", 480),
        ("provenance", ""),
    ],
)
def test_budget_is_explicit_finite_typed_and_separate_from_the_legacy_domain(field, value):
    raw = budget_values()
    raw[field] = value
    with pytest.raises(ValueError):
        domain.budget(**raw)


@pytest.mark.parametrize("kind", ["dispatch", "transport"])
def test_retention_keeps_all_actual_objects_clock_buffers_aliases_and_zero_admission(
    kind, tmp_path
):
    binding, parent = pair(kind)
    planned = calendar()
    control = domain.retain(domain.budget(**budget_values()), planned, binding, parent)
    domain.verify_retained(control)
    assert (
        control.binding is binding
        and control.parent is parent
        and control.requested_calendar is planned
    )
    assert control.parent.clock.source_times_s.shape == (3,) and planned.step_count == 4
    assert control.parent.owners["molecules"] is control.parent.owners["grn"]
    assert control.numerical_owner_admission is False and control.cursor == 0
    assert control.status == "awaiting_shared_material_domain"
    keep(
        tmp_path / "retained-owner-control",
        dict(contract=domain.record(control), roots=domain._roots(binding, parent)),
    )


@pytest.mark.parametrize("cursor", [1, 3, 4])
def test_evolved_and_three_call_prefixes_cannot_be_rebased_or_cycled(cursor, tmp_path):
    with pytest.raises(ValueError, match="Evolved, cycled or rebased") as caught:
        domain.retain(domain.budget(**budget_values()), calendar(), *pair(cursor=cursor))
    keep(tmp_path / "prefix-refusal", dict(cursor=cursor, primary=str(caught.value)))


@pytest.mark.parametrize(
    "fault",
    [
        "dictionary",
        "mismatched-pair",
        "missing-field",
        "missing-rates",
        "missing-controls",
        "changed-record",
        "wrong-calendar",
        "bytes",
    ],
)
def test_missing_unowned_foreign_or_unbudgeted_graphs_refuse(fault):
    binding, parent = pair()
    limits, planned = domain.budget(**budget_values()), calendar()
    if fault == "dictionary":
        parent = dict(identity=parent.identity)
    elif fault == "mismatched-pair":
        binding, _ = pair("dispatch")
    elif fault == "missing-field":
        parent = replace(parent, field=None)
    elif fault == "missing-rates":
        parent = replace(parent, rate_cache=None)
    elif fault == "missing-controls":
        parent = replace(parent, controls=None)
    elif fault == "changed-record":
        parent = replace(parent, identity="changed")
    elif fault == "wrong-calendar":
        planned = calendar(5)
    else:
        raw = budget_values()
        raw["max_retained_bytes"] = 1
        limits = domain.budget(**raw)
    with pytest.raises(ValueError):
        domain.retain(limits, planned, binding, parent)


@pytest.mark.parametrize(
    "fault",
    [
        "budget",
        "calendar",
        "status",
        "admission",
        "text",
        "alias",
        "dtype",
        "component-data",
        "attempt-bool",
    ],
)
def test_complete_retained_state_and_control_cannot_drift(fault, tmp_path):
    control = retained()
    if fault == "budget":
        control = replace(control, budget=replace(control.budget, max_material_attempts=5))
    elif fault == "calendar":
        control = replace(control, requested_calendar=calendar(5))
    elif fault == "status":
        control = replace(control, status="completed")
    elif fault == "admission":
        control = replace(control, numerical_owner_admission=True)
    elif fault == "text":
        control.parent.owners["molecules"]["complete_text"] = "changed"
    elif fault == "alias":
        control.parent.owners["grn"] = copy.deepcopy(control.parent.owners["molecules"])
    elif fault == "dtype":
        control.parent.controls["gj_block"] = np.array([[1.0, 2.0]], np.float32)
    elif fault == "component-data":
        control = replace(
            control,
            binding=replace(
                control.binding,
                component=replace(control.binding.component, inputs=dict(changed=True)),
            ),
        )
    else:
        with pytest.raises(domain.MaterialDomainRefused) as caught:
            domain.request_advance(control, None)
        control = caught.value.retained
        attempt = replace(control.attempts[0], numerical_entries=False)
        control = replace(control, attempts=(attempt,), identity="")
        control = replace(control, identity=domain.ions.digest(domain.record(control)))
    with pytest.raises(ValueError) as caught:
        domain.verify_retained(control)
    keep(tmp_path / "state-drift-refusal", dict(fault=fault, primary=str(caught.value)))


def test_missing_numerical_seam_preserves_owner_and_counts_every_recorded_request(tmp_path):
    original = current = retained()
    before = original.owner_fingerprint
    for index in range(4):
        with pytest.raises(domain.MaterialDomainRefused) as caught:
            domain.request_advance(current, None)
        error = caught.value
        assert error.before is current and error.retained.parent is original.parent
        current = error.retained
        assert error.requested_attempt == index + 1 and error.numerical_entries == 0
        assert len(current.attempts) == index + 1 and current.cursor == 0
        assert current.owner_fingerprint == before
        domain.verify_retained(current)
    with pytest.raises(domain.MaterialDomainRefused, match="budget exhausted") as caught:
        domain.request_advance(current, None)
    assert caught.value.retained is current and caught.value.requested_attempt == 5
    assert original.attempts == () and current.parent is original.parent
    keep(
        tmp_path / "blocked-work-budget",
        dict(
            record=domain.record(current),
            exhausted_attempt=5,
            required_seams=caught.value.required_seams,
            actual_material_calls=0,
        ),
    )


def test_distinct_declared_drives_have_distinct_refused_request_identities(tmp_path):
    control = retained()
    first = domain.dispatch.material.Drive(1.0, 300.0, *([None] * 9))
    second = first._replace(runtime_temperature_K=310.0)
    errors = []
    for value in (first, second):
        with pytest.raises(domain.MaterialDomainRefused) as caught:
            domain.request_advance(control, value)
        errors.append(caught.value)
    assert errors[0].retained.identity != errors[1].retained.identity
    assert errors[0].retained.parent is errors[1].retained.parent is control.parent
    assert all(e.retained.attempts[0].numerical_entries == 0 for e in errors)
    keep(
        tmp_path / "drive-association",
        dict(identities=[error.retained.identity for error in errors], cases=0),
    )


def test_control_record_is_not_silently_added_to_ordinary_checkpoint_vocabulary():
    with pytest.raises(ValueError, match="Missing ownership/codec for runtime type:.*Retained"):
        domain.codec.fingerprint(retained())


def test_input_capture_failure_preserves_cause_and_debits_the_refused_entry(tmp_path):
    control = retained()
    forcing = domain.dispatch.material.Drive(1.0, 300.0, *([None] * 8), object())
    with pytest.raises(domain.MaterialDomainRefused) as caught:
        domain.request_advance(control, forcing)
    error = caught.value
    assert isinstance(error.__cause__, ValueError)
    assert error.retained.attempts[0].reason == "forcing_capture_incomplete"
    assert error.retained.attempts[0].forcing_fingerprint is None
    assert error.retained.parent is control.parent and error.numerical_entries == 0
    domain.verify_retained(error.retained)
    keep(
        tmp_path / "input-capture-failure",
        dict(
            reason=error.retained.attempts[0].reason,
            cause_type=type(error.__cause__).__name__,
            cause_message=str(error.__cause__),
            attempt=1,
        ),
    )
