"""Blocked software controls for explicit global preparation from Publication."""

import copy
import json
import sys
from dataclasses import replace
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_events as events
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import observation, plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import (
    explicit_inputs,
    graph,
)
from tests.unit.test_betse_normal_ecm_molecule_event_owner import (
    forbid_original_source_finalizers as forbid_original_source_finalizers,
)
from tests.unit.test_betse_normal_ecm_molecule_global_event_checkpoint import (
    stores_observation,
    template,
)
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation
from validation.betse import betse_normal_ecm_molecule_global_event_checkpoint as global_events
from validation.betse import betse_normal_ecm_molecule_membrane_event_checkpoint as membrane
from validation.betse import betse_normal_ecm_molecule_published_global_checkpoint as route
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields

LABELS = (0.0, 1.5, 3.0)


def source_graph(mixed=False):
    owner = None
    if mixed:
        maps = dict(tissue_target_inds=dict(region0=[2, 0], all=[0, 1, 2, 3]))
        options = dict.fromkeys(events.event42.GLOBAL_KEYS, 0)
        scheduled = dict.fromkeys(events.event42.TISSUE_KEYS, 0)
        scheduled["Na_mem"] = [0.5, 2.0, 0.7, 0.15, ["region0", "region0", "all"], "None"]
        owner = dict(
            global_options=options,
            scheduled_options=scheduled,
            callbacks=dict(
                Namem=dict(
                    source_function="None",
                    source_scalar=1,
                    dynamic=dict(kind="constant"),
                    provenance="Synthetic conditional callback metadata",
                )
            ),
            handler_fields=finalize_fields(options, scheduled, maps, 4),
        )
    value = graph(owner)
    object.__setattr__(value.phase.calendar, "dt_s", 1.0)
    clock = plain_record(
        lifecycle.init.Clock, source_times_s=run.ions.freeze(np.array(LABELS)), call_index=0
    )
    object.__setattr__(value.entry, "active", plain_record(lifecycle.init.State, clock=clock))
    object.__setattr__(value.entry, "identity", "unowned-synthetic-SIM-entry")
    return value


def event_component(value, scenario):
    raw, spec = route.declaration(
        value.source, value.entry, scenario=scenario, labels=LABELS, dt=1.0
    )
    component = events.Binding(value.source, value.entry, raw, "unowned synthetic event binding")
    return component, spec


@pytest.mark.parametrize("scenario", route.SCENARIOS)
def test_declared_global_intervention_uses_complete_publication_without_changing_source(scenario):
    value = source_graph(scenario == route.MIXED)
    before = checkpoint.codec.fingerprint((value.source, value.pub, value.early))
    raw, spec = route.declaration(
        value.source, value.entry, scenario=scenario, labels=LABELS, dt=1.0
    )
    for name in route.SOURCE_FIELDS:
        assert bridge.same(raw["event_owner"][name], value.pub.owner[name])
    assert bridge.same(
        raw["event_owner"]["scheduled_options"], value.pub.owner["scheduled_options"]
    )
    assert bridge.same(raw["event_owner"]["callbacks"], value.pub.owner["callbacks"])
    assert spec["source_publication_identity"] == value.pub.identity
    assert spec["source_event_finalized_identity"] == value.pub.event_finalized_identity
    assert spec["source_inputs_provenance"] == explicit_inputs().provenance
    assert "conditional" in spec["provenance"]
    assert raw["event_owner"]["provenance"] == value.pub.owner["provenance"]
    assert spec["identity"] in raw["provenance"] and value.pub.identity in raw["provenance"]
    assert checkpoint.codec.fingerprint((value.source, value.pub, value.early)) == before
    assert bridge.resolve(value.source, value.entry) is value.pub
    if scenario == "no_events":
        assert all(v == 0 for v in raw["event_owner"]["global_options"].values())
    if scenario in global_events.SCENARIOS:
        expected = global_events.program(template(), scenario, LABELS)
        assert raw["event_owner"]["global_options"] == expected["event_owner"]["global_options"]
    if scenario == route.MIXED:
        assert raw["event_owner"]["handler_fields"]["targets_Namem"] == [2, 0, 2, 0, 0, 1, 2, 3]
    assert (
        route.association(events.Binding(value.source, value.entry, raw, "synthetic"), spec)[
            "source_publication"
        ]
        == value.pub.identity
    )


@pytest.mark.parametrize("scenario", route.SCENARIOS)
def test_explicit_preparation_passes_supplied_typed_inputs_unchanged_to_existing_runner(
    tmp_path, monkeypatch, scenario
):
    supplied = explicit_inputs()
    seen = []

    def prepared(*args, **kwargs):
        seen.append((args, kwargs))
        return "synthetic binding", "synthetic parent"

    monkeypatch.setattr(preparation, "prepare_SIM", prepared)
    monkeypatch.setattr(membrane, "prepare_sim", prepared)
    assert route.prepare_sim(
        tmp_path / "unused",
        SimpleNamespace(composition=source_graph().completed.binding),
        "unowned INIT parent",
        [],
        scenario=scenario,
        event_owner_inputs=supplied,
    ) == ("synthetic binding", "synthetic parent")
    assert seen[0][1]["event_owner_inputs"] is supplied
    assert ("scenario" in seen[0][1]) == (scenario == route.MIXED)
    assert not (tmp_path / "unused").exists()


def stub_retainer(directory, attempts):
    def take(name, operation, **readers):
        row = dict(operation=name, status="attempted", synthetic_only=True)
        attempts.append(row)
        try:
            result = operation()
        except BaseException:
            row["status"] = "refused"
            raise
        row["status"] = "returned"
        return result

    return take


@pytest.mark.parametrize("with_inputs", [False, True])
def test_common_sim_preparer_binds_same_source_configuration_and_typed_input(
    tmp_path, monkeypatch, with_inputs
):
    value = source_graph()
    initial_binding = SimpleNamespace(composition=value.completed.binding)
    inputs = explicit_inputs() if with_inputs else None
    original = dict(original_source_configuration="unchanged", global_options={"T_change": 0})
    before = copy.deepcopy(original)
    seen = []
    monkeypatch.setattr(preparation, "_retainer", stub_retainer)
    monkeypatch.setattr(
        run, "complete_INIT", lambda *args: SimpleNamespace(complete_init="synthetic complete")
    )
    monkeypatch.setattr(preparation.fixtures, "sim_inputs", lambda *args: original)

    def bound(raw, **kwargs):
        assert raw is original
        seen.append(kwargs)
        return "synthetic component"

    monkeypatch.setattr(lifecycle, "bind", bound)
    monkeypatch.setattr(preparation.fixtures, "declaration", lambda *args: "synthetic declaration")
    monkeypatch.setattr(
        run, "transition", lambda *args, **kwargs: ("synthetic outer", "synthetic parent")
    )
    attempts = []
    assert preparation.prepare_SIM(
        tmp_path / "SIM", initial_binding, "synthetic init", attempts, event_owner_inputs=inputs
    ) == ("synthetic outer", "synthetic parent")
    assert seen == [dict(event_owner_inputs=inputs) if with_inputs else {}]
    if with_inputs:
        assert seen[0]["event_owner_inputs"] is inputs
    assert original == before
    assert attempts[0]["operation"] == (
        "typed-event-owner-inputs" if with_inputs else "actual-complete-INIT"
    )


@pytest.mark.parametrize("scenario", ["global_combined", route.MIXED])
@pytest.mark.parametrize("fault", ["foreign-INIT", "foreign-geometry", "dictionary", "missing"])
def test_missing_or_foreign_authority_refuses_before_any_continuation(
    tmp_path, monkeypatch, fault, scenario
):
    value = source_graph()
    supplied = explicit_inputs()
    if fault == "foreign-INIT":
        supplied = replace(supplied, source_INIT_binding_identity="foreign")
    elif fault == "foreign-geometry":
        supplied = replace(supplied, source_geometry_binding_identity="foreign")
    elif fault == "dictionary":
        supplied = run.ions.data(supplied)
    else:
        with pytest.raises(ValueError, match="explicit typed"):
            route.prepare_sim(
                tmp_path / "unused",
                SimpleNamespace(composition=value.completed.binding),
                None,
                [],
                scenario=scenario,
                event_owner_inputs=None,
            )
        return
    monkeypatch.setattr(preparation, "_retainer", stub_retainer)
    attempts = []
    with pytest.raises(ValueError):
        route.prepare_sim(
            tmp_path / "SIM",
            SimpleNamespace(composition=value.completed.binding),
            "unowned",
            attempts,
            scenario=scenario,
            event_owner_inputs=supplied,
        )
    assert attempts == [] and not (tmp_path / "SIM").exists()


@pytest.mark.parametrize(
    "fault",
    [
        "fixture-owner",
        "default",
        "profile",
        "reservoir",
        "boundary",
        "program",
        "source-id",
        "source-epoch",
        "clock",
        "dt",
    ],
)
def test_substituted_owner_or_resealed_intervention_mismatch_refuses(fault):
    value = source_graph()
    component, spec = event_component(value, "global_combined")
    spec = copy.deepcopy(spec)
    if fault == "fixture-owner":
        component.raw["event_owner"] = template()["event_owner"]
    elif fault == "default":
        component.raw["event_owner"]["tissue_default"]["Dm_Na"] *= 2
    elif fault == "profile":
        component.raw["event_owner"]["tissue_target_inds"]["region0"].reverse()
    elif fault == "reservoir":
        component.raw["event_owner"]["configured_environment"]["Na"] += 1
    elif fault == "boundary":
        component.raw["event_owner"]["owners"]["boundary_cell_occurrences"].reverse()
        component.raw["event_owner"]["owners"]["boundary_cell_occurrences"].append("cell-A")
    elif fault == "program":
        component.raw["event_owner"]["global_options"]["Na_env"][3] *= 2
    else:
        if fault == "source-id":
            spec["source_publication_identity"] = "foreign"
        elif fault == "source-epoch":
            spec["source_event_finalized_identity"] = "foreign"
        elif fault == "clock":
            spec["source_labels"][1] += 0.1
        else:
            spec["source_dt_s"] *= 2
        spec["identity"] = run.ions.digest({key: v for key, v in spec.items() if key != "identity"})
    with pytest.raises(ValueError):
        route.association(component, spec)


@pytest.mark.parametrize("scenario", ["no_events", "global_combined", route.MIXED])
def test_graph_codec_retains_original_and_later_epochs_separate_intervention_and_input_aliases(
    tmp_path, scenario
):
    value = source_graph(scenario == route.MIXED)
    component, spec = event_component(value, scenario)
    data = dict(
        component=component,
        intervention=spec,
        publication=value.pub,
        early=value.early,
        inputs=value.source.event_owner_inputs,
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(data)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(data)
    source = loaded["component"].source_binding
    assert source.event_owner_inputs is loaded["inputs"] is loaded["publication"].inputs
    receipt = loaded["component"].source_entry.phase_binding.setup_receipt
    assert receipt["event_finalization"]["source_fields"] is loaded["early"]
    assert receipt["event_finalization"]["owner_publication"] is loaded["publication"]
    assert loaded["publication"].event_finalized is loaded["early"]
    assert route.association(loaded["component"], loaded["intervention"]) == route.association(
        component, spec
    )


def test_pure_global_cannot_silently_discard_membrane_authority():
    value = source_graph(True)
    with pytest.raises(ValueError, match="cannot drop source"):
        route.declaration(
            value.source, value.entry, scenario="global_combined", labels=LABELS, dt=1.0
        )
    value = source_graph()
    with pytest.raises(ValueError, match="requires actual finalized"):
        route.declaration(value.source, value.entry, scenario=route.MIXED, labels=LABELS, dt=1.0)


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "source_publication",
        "source_configuration",
        "source_event_finalized",
        "source_publication_epoch",
        "declared_intervention",
    ],
)
def test_continuation_observations_retain_both_epochs_and_intervention(fault):
    component, spec = event_component(source_graph(), "global_combined")
    value, anchor = observation()
    stores, store_anchor = stores_observation()
    for row, store_row in zip(value["rows"], stores.pop("rows"), strict=True):
        row.update(store_row)
    value.update(stores)
    anchor.update(store_anchor, scenario="global_combined", preparation_route=route.ROUTE)
    facts = route.association(component, spec)
    anchor.update(facts)
    value.update(facts)
    if fault is None:
        assert validation.check_observation(value, anchor) is value
    else:
        value[fault] = "foreign observation"
        with pytest.raises(ValueError, match="Changed explicit global route association"):
            validation.check_observation(value, anchor)


@pytest.mark.parametrize("flag", [None, *validation.RELEASES])
def test_explicit_global_route_keeps_both_existing_gates_first(tmp_path, monkeypatch, flag):
    if flag is not None:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="both existing Root releases"):
        validation.actual_continuity(
            tmp_path / "held",
            scenario="no_events",
            cut=1,
            preparation_route=route.ROUTE,
            event_owner_inputs=explicit_inputs(),
        )
    assert not (tmp_path / "held").exists()


@pytest.mark.parametrize(
    "scenario,selected_route",
    [("temperature", "legacy"), ("membrane_Na_mem", route.ROUTE), ("global_combined", "unknown")],
)
def test_wrong_route_refuses_before_setup(tmp_path, monkeypatch, scenario, selected_route):
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError):
        validation.actual_continuity(
            tmp_path / "refused",
            scenario=scenario,
            cut=1,
            preparation_route=selected_route,
            event_owner_inputs=explicit_inputs(),
        )
    assert not (tmp_path / "refused").exists()


def test_missing_input_failure_is_retained_before_explicit_route_source_setup(
    tmp_path, monkeypatch
):
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    previous = sys.getprofile()
    sys.setprofile(None)
    try:
        with pytest.raises(ValueError, match="explicit typed"):
            validation.actual_continuity(
                tmp_path / "refused", scenario="no_events", cut=1, preparation_route=route.ROUTE
            )
    finally:
        sys.setprofile(previous)
    assert (tmp_path / "refused/failure/manifest.json").is_file()
    assert not (tmp_path / "refused/result.json").exists()
    attempts = json.loads((tmp_path / "refused/attempts.json").read_bytes())["attempts"]
    assert len(attempts) == 1 and attempts[0]["status"] == "refused"


@pytest.mark.parametrize("scenario", ["no_events", "global_combined", route.MIXED])
def test_dispatcher_selects_publication_without_fixture_owner_and_retains_failure(
    tmp_path, monkeypatch, scenario
):
    """A fully stubbed preparation is not an actual setup/transition receipt."""
    value = source_graph(scenario == route.MIXED)
    supplied = value.source.event_owner_inputs
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    monkeypatch.setattr(
        preparation, "prepare_INIT", lambda *args: ("unowned INIT", "unowned parent")
    )

    def prepared(*args, **kwargs):
        assert kwargs == dict(scenario=scenario, event_owner_inputs=supplied)
        assert kwargs["event_owner_inputs"] is supplied
        return plain_record(run.Binding, composition=value.source), plain_record(
            run.RunState, active=value.entry
        )

    def no_fixture(*args, **kwargs):
        raise AssertionError("Fixture owner must not supply published global declaration")

    class StopBeforeEventModel(RuntimeError):
        pass

    failure = StopBeforeEventModel("Synthetic stop before any event model entry")
    failure.partial = dict(retained="synthetic failed event input")
    captured = []

    def refuse_event_model(raw, binding, entry):
        assert binding is value.source and entry is value.entry
        captured.append(raw)
        raise failure

    monkeypatch.setattr(route, "prepare_sim", prepared)
    monkeypatch.setattr(validation, "program", no_fixture)
    from validation.betse import betse_normal_ecm_molecule_events_fixtures

    monkeypatch.setattr(betse_normal_ecm_molecule_events_fixtures, "declaration", no_fixture)
    monkeypatch.setattr(events, "bind", refuse_event_model)
    previous = sys.getprofile()
    sys.setprofile(None)
    directory = tmp_path / "refused"
    try:
        with pytest.raises(StopBeforeEventModel) as caught:
            validation.actual_continuity(
                directory,
                scenario=scenario,
                cut=1,
                preparation_route=route.ROUTE,
                event_owner_inputs=supplied,
            )
        assert caught.value is failure
    finally:
        sys.setprofile(previous)
    assert len(captured) == 1
    assert captured[0]["event_owner"]["owners"] == run.ions.data(value.pub.owner["owners"])
    assert (directory / "failure/manifest.json").is_file()
    assert (
        directory / "operations/declared-global-intervention-on-actual-publication/manifest.json"
    ).is_file()
    assert not (directory / "result.json").exists()
    journal = json.loads((directory / "attempts.json").read_bytes())
    assert journal["attempts"][-1]["operation"] == "event-binding"
    assert journal["attempts"][-1]["status"] == "refused"
    assert journal["invocation_accounting"]["profile_intact"] is True
