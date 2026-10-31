"""Held route/parent/reader controls; no scientific or reference entry allowed."""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import explicit_inputs, graph
from tests.unit.test_betse_normal_ecm_molecule_periodic_checkpoint import (
    forbid_actual_periodic as forbid_actual_periodic,
)
from tests.unit.test_betse_normal_ecm_molecule_temporal_config_checkpoint import configuration
from tests.unit.test_betse_normal_ecm_molecule_temporal_reference import (
    forbid_reference_execution as forbid_reference_execution,
)
from validation.betse import betse_normal_ecm_molecule_temporal_continuity as route
from validation.betse import betse_normal_ecm_molecule_temporal_reference as reference


def parent_pair(count=0):
    """Structural unowned records only, never submitted to run.verify."""
    g = graph()
    calendar = plain_record(route.run.calendars.NativePhaseCalendar, phase="INIT", step_count=count)
    owner = replace(g.completed.binding, calendar=calendar, call_limit=count)
    clock = plain_record(
        route.lifecycle.init.Clock, call_index=count, source_times_s=np.array([], np.float64)
    )
    active = plain_record(
        route.lifecycle.init.State, binding_identity=owner.identity, clock=clock, status="exhausted"
    )
    binding = route.run.Binding(owner, None, "outer-INIT")
    parent = plain_record(
        route.run.RunState,
        binding_identity=binding.identity,
        active=active,
        identity="retained-parent",
        status="exhausted",
    )
    return binding, parent, explicit_inputs()


def preflight(binding, parent, inputs):
    return route.preflight(
        binding,
        parent,
        inputs,
        expected_binding_identity="outer-INIT",
        expected_parent_identity="retained-parent",
    )


@pytest.mark.parametrize("count", [0, 1, 3])
def test_structural_exhausted_parent_preflight_is_explicitly_not_admission(count):
    result = preflight(*parent_pair(count))
    assert result["cursor"] == count and result["numeric_admission"] is False
    assert "ownership validation" in result["required_next"]


@pytest.mark.parametrize(
    "fault",
    [
        "binding-missing",
        "parent-missing",
        "dictionary",
        "SIM",
        "calendar-bool",
        "failed",
        "paused",
        "capped",
        "incomplete",
        "limit",
        "active-failed",
        "binding-id",
        "parent-id",
        "active-owner",
        "inputs-missing",
        "inputs-dictionary",
        "foreign-INIT",
        "foreign-geometry",
    ],
)
def test_parent_refusals_precede_any_actual_work(fault):
    binding, parent, inputs = parent_pair(1)
    if fault == "binding-missing":
        binding = None
    elif fault == "parent-missing":
        parent = None
    elif fault == "dictionary":
        parent = {"status": "exhausted"}
    elif fault == "SIM":
        binding = replace(
            binding,
            composition=replace(
                binding.composition, calendar=replace(binding.composition.calendar, phase="SIM")
            ),
        )
    elif fault == "calendar-bool":
        binding = replace(
            binding,
            composition=replace(
                binding.composition, calendar=replace(binding.composition.calendar, step_count=True)
            ),
        )
    elif fault in ("failed", "paused", "capped"):
        parent = replace(parent, status=fault)
    elif fault == "incomplete":
        parent = replace(
            parent, active=replace(parent.active, clock=replace(parent.active.clock, call_index=0))
        )
    elif fault == "limit":
        binding = replace(binding, composition=replace(binding.composition, call_limit=0))
    elif fault == "active-failed":
        parent = replace(parent, active=replace(parent.active, status="failed"))
    elif fault == "binding-id":
        binding = replace(binding, identity="foreign")
    elif fault == "parent-id":
        parent = replace(parent, identity="foreign")
    elif fault == "active-owner":
        parent = replace(parent, active=replace(parent.active, binding_identity="foreign"))
    elif fault == "inputs-missing":
        inputs = None
    elif fault == "inputs-dictionary":
        inputs = route.run.ions.data(inputs)
    elif fault == "foreign-INIT":
        inputs = replace(inputs, source_INIT_binding_identity="foreign")
    else:
        inputs = replace(inputs, source_geometry_binding_identity="foreign")
    with pytest.raises(ValueError):
        preflight(binding, parent, inputs)


@pytest.mark.parametrize("scenario", route.selected.SCENARIOS)
@pytest.mark.parametrize("cut", [1, 2])
def test_exact_existing_selected_scenarios_and_cuts_remain_controls(scenario, cut):
    family = "periodic" if scenario.startswith("periodic_") else "f_sweep"
    result = route.request(configuration(family), scenario, cut)
    assert result["scenario"] == scenario and result["cut"] == cut
    assert result["configuration"]["projection"] == configuration(family)["projection"]


@pytest.mark.parametrize(
    "scenario,cut",
    [
        ("sweep_combined", 1),
        ("periodic_combined", True),
        ("periodic_combined", 0),
        ("periodic_combined", 3),
        ("unknown", 1),
    ],
)
def test_request_does_not_rebase_roster_or_cut(scenario, cut):
    with pytest.raises(ValueError):
        route.request(configuration(), scenario, cut)


@pytest.mark.parametrize("gates", [("0", "0"), ("1", "0"), ("0", "1")])
def test_both_existing_gates_first_before_parent_or_output(monkeypatch, tmp_path, gates):
    for name, state in zip(reference.RELEASES, gates, strict=True):
        monkeypatch.setenv(name, state)
    destination = tmp_path / "held"
    with pytest.raises(ValueError, match="both releases"):
        route.actual_continuity(
            destination, configuration=configuration(), scenario="periodic_combined", cut=1
        )
    assert not destination.exists()


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_missing_actual_INIT_is_retained_and_no_fixture_or_reference_is_entered(
    monkeypatch, tmp_path, family
):
    for name in reference.RELEASES:
        monkeypatch.setenv(name, "1")
    destination = tmp_path / "missing-INIT"
    with pytest.raises(ValueError, match="Missing actual retained INIT binding") as caught:
        route.actual_continuity(
            destination,
            configuration=configuration(family),
            scenario="periodic_combined" if family == "periodic" else "sweep_combined",
            cut=1,
        )
    assert caught.value.checkpoint_retention["complete"] is True
    assert (destination / "failure/manifest.json").is_file()
    assert not (destination / "SIM").exists() and not (destination / "invocations.jsonl").exists()
    attempts = json.loads((destination / "attempts.json").read_bytes())["attempts"]
    assert [a["operation"] for a in attempts] == ["required-actual-INIT-parent"]
    assert not (destination / "result.json").exists()


def test_malformed_result_ABI_refusal_precedes_setup_even_with_structural_parent(
    monkeypatch, tmp_path
):
    for name in reference.RELEASES:
        monkeypatch.setenv(name, "1")
    binding, parent, inputs = parent_pair()
    # Retain the original malformed source as an explicit refusal control;
    # do not change the live callback, create an alias, or admit this parent.
    malformed = Path(
        "/mnt/workspaces/Cells/molecule-temporal-paired-continuity-preparation-20261031-01/source-final-02/src/cells/processes/betse_normal_ecm_event_join_source.py"
    )
    monkeypatch.setattr(reference, "literal", SimpleNamespace(__file__=str(malformed)))
    destination = tmp_path / "ABI-held"
    with pytest.raises(ValueError, match="ABI prerequisite"):
        route.actual_continuity(
            destination,
            init_binding=binding,
            init_parent=parent,
            event_owner_inputs=inputs,
            expected_binding_identity=binding.identity,
            expected_parent_identity=parent.identity,
            configuration=configuration(),
            scenario="periodic_combined",
            cut=1,
        )
    attempts = json.loads((destination / "attempts.json").read_bytes())["attempts"]
    assert len(attempts) == 2 and attempts[-1]["operation"] == "required-callback-result-ABI"
    assert not (destination / "SIM").exists() and not (destination / "original-source").exists()


def dispatches(family="periodic"):
    labels = [0.0, 1.5, 3.0]
    rows = [
        dict(
            key=key,
            samples=[
                dict(label=t, candidate=dict(hex=number.hex(), shape=[], dtype="<f8"))
                for t, number in zip(labels, [0.25, 0.5, 0.75], strict=True)
            ],
        )
        for key in ("Na_mem", "K_mem")
    ]
    groups = []
    for index in range(6):
        groups.append(
            dict(
                label=labels[index % 3],
                events=[
                    dict(
                        operation="callback",
                        kind=family,
                        key=key,
                        returned=True,
                        value=[0.25, 0.5, 0.75][index % 3],
                        value_shape=[],
                        value_dtype="<f8",
                    )
                    for key in ("Na_mem", "K_mem")
                ],
            )
        )
    return {(family if family == "periodic" else "sweep") + "_dispatches": groups}, dict(
        family=family, labels=labels, rows=rows
    )


@pytest.mark.parametrize("family", ["periodic", "f_sweep"])
def test_actual_dispatch_reader_pairs_each_value_without_extra_case_credit(family):
    accounting, paired = dispatches(family)
    value = route.compare_dispatches(accounting, paired)
    assert value["actual_callback_returns_matched"] == 12 and value["independent_cases"] == 0


@pytest.mark.parametrize(
    "fault",
    [
        "omitted",
        "duplicate",
        "reorder",
        "clock",
        "value",
        "shape",
        "dtype",
        "incomplete",
        "source-duplicate",
    ],
)
def test_dispatch_reader_rejects_changed_actual_and_original_evidence(fault):
    accounting, paired = dispatches()
    group = accounting["periodic_dispatches"][1]
    if fault == "omitted":
        group["events"].pop()
    elif fault == "duplicate":
        group["events"].append(copy.deepcopy(group["events"][0]))
    elif fault == "reorder":
        group["events"].reverse()
    elif fault == "clock":
        group["label"] = 1.0
    elif fault == "value":
        group["events"][0]["value"] = 0.5000000000000001
    elif fault == "shape":
        group["events"][0]["value_shape"] = [1]
    elif fault == "dtype":
        group["events"][0]["value_dtype"] = "<f4"
    elif fault == "incomplete":
        accounting["periodic_dispatches"].pop()
    else:
        paired["rows"][0]["samples"][1]["label"] = 0.0
    with pytest.raises(ValueError):
        route.compare_dispatches(accounting, paired)


def test_checkpoint_adapter_preserves_exact_expected_parent_and_nested_receipt():
    seen = []
    receipt = plain_record(
        route.checkpoint.Receipt,
        directory=Path("/unowned/synthetic/checkpoint"),
        identity="saved",
        verification_attempts=2,
    )

    def take(name, operation, **kwargs):
        seen.append((name, operation()))

    assert route._checkpoint_call(take, "save", lambda: receipt) is receipt
    assert seen[0][1]["nested_ownership_verification_requests"] == 2
    assert seen[0][1]["nested_invocations_retained_by_profiler"] is True
    assert seen[0][1]["independent_cases"] == 0
    assert seen[0][1]["receipt"]["directory"] == "/unowned/synthetic/checkpoint"


@pytest.mark.parametrize("attempts", [0, -1, True, None])
def test_missing_or_noninteger_checkpoint_work_is_not_assumed(attempts):
    receipt = plain_record(route.checkpoint.Receipt, verification_attempts=attempts)

    def take(name, operation, **kwargs):
        return operation()

    with pytest.raises(ValueError, match="recorded ownership attempts"):
        route._checkpoint_call(take, "save", lambda: receipt)


@pytest.mark.parametrize("target", ["checkout", "selection", "symlink"])
def test_prepare_output_cannot_modify_checkout_or_frozen_selection(monkeypatch, tmp_path, target):
    repo = tmp_path / "repo"
    repo.mkdir()
    frozen = tmp_path / "frozen"
    frozen.mkdir()
    selection = frozen / "SNAPSHOT.json"
    selection.write_text("{}")
    monkeypatch.setattr(
        route.snapshot,
        "verify",
        lambda *a, **k: dict(files={"one.py": dict(checkout_path="one.py", sha256="unknown")}),
    )
    output = repo / "inside" if target == "checkout" else frozen / "inside"
    if target == "symlink":
        alias = tmp_path / "alias"
        alias.symlink_to(frozen, target_is_directory=True)
        output = alias / "inside"
    with pytest.raises(ValueError, match="outside checkout"):
        route.prepare(
            repo,
            output,
            source_selection=selection,
            configuration=configuration(),
            scenario="periodic_combined",
            cut=1,
        )
    assert not output.exists()


def test_prepare_never_imports_an_historical_source_overlay(monkeypatch, tmp_path):
    selection = tmp_path / "selection.json"
    selection.write_text("{}")
    monkeypatch.setattr(
        route.snapshot,
        "verify",
        lambda *a, **k: dict(files={"new.py": dict(checkout_path="old.py")}),
    )
    with pytest.raises(ValueError, match="overlays"):
        route.prepare(
            tmp_path,
            tmp_path / "unused",
            source_selection=selection,
            configuration=configuration(),
            scenario="periodic_combined",
            cut=1,
        )
    assert not (tmp_path / "unused").exists()


def test_prepare_failure_is_retained_without_scientific_entry(monkeypatch, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    selected = tmp_path / "prior"
    selected.mkdir()
    selection = selected / "SNAPSHOT.json"
    selection.write_text("{}")
    monkeypatch.setattr(
        route.snapshot,
        "verify",
        lambda *a, **k: dict(files={"one.py": dict(checkout_path="one.py", sha256="unknown")}),
    )
    primary = OSError("synthetic freeze failure")

    def failed(*a, **k):
        raise primary

    monkeypatch.setattr(route.snapshot, "freeze", failed)
    output = tmp_path / "failed"
    with pytest.raises(OSError) as caught:
        route.prepare(
            repo,
            output,
            source_selection=selection,
            configuration=configuration(),
            scenario="periodic_combined",
            cut=1,
        )
    assert caught.value is primary
    assert (
        json.loads((output / "failure.json").read_bytes())["failure"]["stage"]
        == "prepare-selected-temporal-continuity"
    )
    assert not (output / "inputs.json").exists()
