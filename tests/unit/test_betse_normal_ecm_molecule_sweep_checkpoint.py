"""Sweep authority software controls; no factory/callback/law/model is executed."""

import copy
import io
import json
import sys
from dataclasses import replace
from types import CellType, CodeType, FunctionType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_event_join_source as literal
from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_event_owner as bridge
from cells.processes import betse_normal_ecm_molecule_events as events
from cells.processes import betse_normal_ecm_molecule_lifecycle as lifecycle
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from cells.processes import betse_normal_ecm_molecule_sweep_authority as authority
from cells.processes import betse_time_modulation as time_laws
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import (
    no_actual_execution as no_actual_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_event_checkpoint import plain_record
from tests.unit.test_betse_normal_ecm_molecule_event_owner import explicit_inputs, graph
from tests.unit.test_betse_normal_ecm_molecule_membrane_event_checkpoint import sim_template
from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation
from validation.betse import betse_normal_ecm_molecule_sweep_checkpoint as sweep
from validation.betse.betse_normal_ecm_event_join_fixtures import finalize_fields


@pytest.fixture(autouse=True)
def forbid_sweep_execution(no_actual_execution, monkeypatch):
    codes = {
        authority.FACTORY_CODE,
        authority.FINALIZER_CODE,
        authority.callback_code(),
        time_laws.sweep_program.__code__,
        time_laws.periodic_program.__code__,
        time_laws.evaluate.__code__,
        literal.prepared_callback.__code__,
    }
    codes.update(c for c in literal.prepared_callback.__code__.co_consts if type(c) is CodeType)
    previous = sys.getprofile()

    def blocked(frame, event, arg):
        if event == "call" and frame.f_code in codes:
            no_actual_execution.append("factory/finalizer/callback/time-law")
            raise AssertionError("Actual sweep execution forbidden")

    sys.setprofile(blocked)
    try:
        yield codes
    finally:
        sys.setprofile(previous)


def inputs(scenario="sweep_combined"):
    raw = sim_template()
    raw["source_setup"] = dict(
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None}
    )
    return sweep.configure_sim(raw, scenario)


def manufactured_factory(scenario="sweep_combined", explicit=False):
    """Manufactured frames/closures, never a source finalizer return or parent."""
    configured = inputs(scenario)
    initial = copy.deepcopy(configured["source_setup"]["frequency_sweep"])
    if explicit:
        initial["f slope"] = -125.0
    p = SimpleNamespace(
        _run_sim=True,
        sim_time_total=3.25,
        f_scan_properties=copy.deepcopy(initial),
        scheduled_options=configured["sim_phase"]["setup"]["scheduled_options"],
    )
    phase = SimpleNamespace(p=p, cells=object())
    maps = configured["sim_phase"]["setup"]["maps"]
    fields = finalize_fields(
        configured["sim_phase"]["setup"]["global_options"], p.scheduled_options, maps, 4
    )
    owner = SimpleNamespace(**fields, **maps)
    trace = authority.FactoryObservation(owner, phase, initial)
    return SimpleNamespace(
        configured=configured, initial=initial, p=p, phase=phase, owner=owner, trace=trace
    )


def frame(value, suffix):
    caller = SimpleNamespace(
        f_code=authority.FINALIZER_CODE,
        f_globals=vars(authority.source),
        f_locals=dict(self=value.owner, phase=value.phase),
    )
    return SimpleNamespace(
        f_code=authority.FACTORY_CODE,
        f_globals=vars(authority.source),
        f_back=caller,
        f_locals=dict(
            p=value.p, cells=value.phase.cells, pc=getattr(value.owner, "targets_" + suffix)
        ),
    )


def callback(value, slope=None, parameters=None):
    return FunctionType(
        authority.callback_code(),
        vars(authority.source),
        closure=(
            CellType(value.p.f_scan_properties["f slope"] if slope is None else slope),
            CellType(value.p if parameters is None else parameters),
        ),
    )


def fabricate_returns(value):
    for _, suffix in value.trace.selected:
        call = frame(value, suffix)
        value.trace.observe(call, "call", None)
        if value.p.f_scan_properties["f slope"] is None:
            # A manufactured observation, not evaluation of the slope formula.
            value.p.f_scan_properties["f slope"] = 125.0
        function = callback(value)
        setattr(value.owner, "dyna_" + suffix, function)
        setattr(value.owner, "scalar_" + suffix, 1)
        call.f_locals["f_slope"] = value.p.f_scan_properties["f slope"]
        value.trace.observe(call, "return", (1, function))
    value.trace.finish()
    return value


def published_graph(scenario="sweep_combined", explicit=False):
    value = fabricate_returns(manufactured_factory(scenario, explicit))
    configured = value.configured["sim_phase"]["setup"]
    owner = dict(
        global_options=configured["global_options"],
        scheduled_options=value.p.scheduled_options,
        handler_fields=finalize_fields(
            configured["global_options"], value.p.scheduled_options, configured["maps"], 4
        ),
        callbacks={
            suffix: dict(
                source_function=row[5],
                source_scalar=1,
                dynamic=dict(
                    kind="sweep",
                    start=value.p.f_scan_properties["f start"],
                    slope=value.p.f_scan_properties["f slope"],
                    provenance="Manufactured unowned coefficients",
                )
                if row[5] == "f_sweep"
                else dict(kind="constant"),
                provenance="Manufactured metadata, no actual finalizer admission",
            )
            for key, suffix in authority.MEMBRANE_KEYS.items()
            if (row := value.p.scheduled_options[key]) != 0
        },
    )
    g = graph(owner)
    original = run.ions.data(g.source.inputs)
    original["source_setup"]["frequency_sweep"] = value.initial
    original["sim_phase"]["time_profile"] = dict(sim_total_s=value.p.sim_time_total)
    g.source = replace(g.source, inputs=run.ions.freeze(original))
    g.source = replace(g.source, identity=run.ions.digest(lifecycle.binding_record(g.source)))
    early = run.ions.data(g.early)
    early.update(
        sweep_callback_authority=value.trace.records,
        frequency_sweep_after=value.p.f_scan_properties,
    )
    constants = {
        suffix: lifecycle.setup.constant_callback_record(suffix)
        for suffix, row in owner["callbacks"].items()
        if row["source_function"] == "None"
    }
    if constants:
        early["constant_callback_authority"] = constants
    g.factory = value
    reseal(g, early)
    return g


def reseal(g, early):
    """Synchronized manufactured metadata; no numerical admission verifier."""
    g.early = run.ions.freeze(early)
    g.pub = bridge.publish(g.source, g.completed, g.early, g.final, g.mechanical, g.profiles)
    g.receipt["event_finalization"].update(source_fields=g.early, owner_publication=g.pub)
    g.receipt["source_setup"].update(event_finalized=g.early, event_owner_published=g.pub)
    object.__setattr__(g.entry, "binding_identity", g.source.identity)
    g.component = events.Binding(
        g.source,
        g.entry,
        dict(event_owner=run.ions.data(g.pub.owner)),
        "unowned synthetic event binding",
    )


@pytest.mark.parametrize("scenario", sweep.SCENARIOS)
def test_sweep_configuration_precedes_real_finalization_and_preserves_source_inputs(scenario):
    raw = sim_template()
    raw["source_setup"] = dict(
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None}
    )
    before = copy.deepcopy(raw)
    value = sweep.configure_sim(raw, scenario)
    assert raw == before
    assert value["source_setup"] == before["source_setup"]
    assert value["sim_phase"]["unchanged"] == before["sim_phase"]["unchanged"]
    assert value["sim_phase"]["setup"]["maps"] == before["sim_phase"]["setup"]["maps"]
    assert all(v == 0 for v in value["sim_phase"]["setup"]["global_options"].values())
    assert "callbacks" not in value["sim_phase"]["setup"]


@pytest.mark.parametrize("explicit", [False, True])
def test_observed_factory_order_retains_mutation_closure_source_and_no_executable_data(
    tmp_path, explicit
):
    value = fabricate_returns(manufactured_factory(explicit=explicit))
    data = value.trace.data()
    assert data["complete"] and data["factory_entry_attempts"] == data["factory_returns"] == 4
    assert list(data["records"]) == list(authority.MEMBRANE_KEYS.values())
    rows = list(data["records"].values())
    assert rows[0]["before"]["f slope"] == (-125.0 if explicit else None)
    assert all(r["before"]["f slope"] == value.p.f_scan_properties["f slope"] for r in rows[1:])
    assert all(r["evaluated"] is False and r["callable_instance_persisted"] is False for r in rows)
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(data)
    encoder.write(tmp_path, tree)
    decoded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert checkpoint.codec.fingerprint(decoded) == checkpoint.codec.fingerprint(data)


def test_finalized_owner_requires_its_live_observed_factory_without_hydrating_callbacks():
    value = fabricate_returns(manufactured_factory("sweep_Na_mem"))
    template = {
        k: value.configured["sim_phase"]["setup"][k]
        for k in ("global_options", "scheduled_options")
    }
    with pytest.raises(ValueError, match="Missing actual source sweep"):
        lifecycle.setup.finalized_owner(template, value.owner, value.p)
    with pytest.raises(ValueError, match="Missing actual source sweep"):
        lifecycle.setup.finalized_owner(
            template, value.owner, value.p, sweep_observation=SimpleNamespace(complete=True)
        )
    owner = lifecycle.setup.finalized_owner(
        template, value.owner, value.p, sweep_observation=value.trace
    )
    assert owner["callbacks"]["Namem"]["dynamic"]["slope"] == value.p.f_scan_properties["f slope"]
    assert owner["handler_fields"]["targets_Namem"] == value.owner.targets_Namem


@pytest.mark.parametrize(
    "fault",
    ["code", "globals", "p", "slope", "scalar-array", "scalar-float", "defaults", "kwdefaults"],
)
def test_missing_foreign_or_changed_live_closure_authority_refuses_without_evaluation(fault):
    v = fabricate_returns(manufactured_factory("sweep_Na_mem"))
    function = v.owner.dyna_Namem
    scalar = 1
    if fault == "code":

        def function(t):
            return 1
    elif fault == "globals":
        function = FunctionType(authority.callback_code(), {}, closure=function.__closure__)
    elif fault == "p":
        function = callback(v, parameters=copy.copy(v.p))
    elif fault == "slope":
        function = callback(v, slope=-1.0)
    elif fault == "scalar-array":
        scalar = np.array(1)
    elif fault == "scalar-float":
        scalar = 1.0
    elif fault == "defaults":
        function.__defaults__ = (1,)
    else:
        function.__kwdefaults__ = {"t": 1}
    with pytest.raises(ValueError):
        authority.inspect_callback(function, scalar, v.p)


@pytest.mark.parametrize(
    "fault",
    [
        "pc",
        "p",
        "cells",
        "caller",
        "phase",
        "globals",
        "duplicate",
        "omission",
        "failed-return",
        "replacement",
        "duration",
    ],
)
def test_factory_observations_refuse_wrong_association_order_and_failed_prefixes(fault):
    v = manufactured_factory("sweep_Na_mem")
    call = frame(v, "Namem")
    if fault in ("pc", "p", "cells"):
        call.f_locals[fault] = object()
    elif fault == "caller":
        call.f_back.f_code = (lambda: None).__code__
    elif fault == "phase":
        call.f_back.f_locals["phase"] = object()
    elif fault == "globals":
        call.f_globals = {}
    elif fault == "duration":
        v.p.sim_time_total += 1
    if fault in ("pc", "p", "cells", "caller", "phase", "globals", "duration"):
        with pytest.raises(ValueError):
            v.trace.observe(call, "call", None)
    elif fault == "replacement":
        fabricate_returns(v)
        v.owner.dyna_Namem = lambda t: 1
        with pytest.raises(ValueError):
            v.trace.finish()
    else:
        v.trace.observe(call, "call", None)
        with pytest.raises(ValueError):
            if fault == "duplicate":
                v.trace.observe(call, "call", None)
            elif fault == "omission":
                v.trace.finish()
            else:
                v.trace.observe(call, "return", None)
    assert v.trace.data()["complete"] is False


def test_observer_forwards_work_profile_and_restores_it_on_error():
    v = manufactured_factory("sweep_Na_mem")
    before = sys.getprofile()
    calls = []

    def prior(frame, event, arg):
        calls.append(event)
        if before is not None:
            before(frame, event, arg)

    sys.setprofile(prior)
    primary = RuntimeError("synthetic finalizer failure")
    try:
        with pytest.raises(RuntimeError) as caught:
            with v.trace:
                raise primary
        assert caught.value is primary and sys.getprofile() is prior and calls
    finally:
        sys.setprofile(before)
    assert not v.trace.data()["complete"]


@pytest.mark.parametrize("fault", ["factory", "factory-code", "factory-lookup", "numpy"])
def test_source_identity_refuses_live_factory_or_global_replacement(monkeypatch, fault):
    def foreign(pc, cells, p):
        raise AssertionError("Never execute substituted source")

    if fault == "factory":
        monkeypatch.setattr(authority.source, "f_sweep", foreign)
    elif fault == "factory-code":
        monkeypatch.setattr(authority.FACTORY, "__code__", foreign.__code__)
    elif fault == "factory-lookup":
        monkeypatch.setattr(authority.source.mod, "f_sweep", foreign)
    else:
        monkeypatch.setattr(authority.source, "np", object())
    with pytest.raises(ValueError, match="Foreign sweep factory"):
        authority.source_identity()


def test_closed_factory_observation_refuses_later_live_parameter_mutation():
    value = fabricate_returns(manufactured_factory("sweep_Na_mem"))
    value.p.f_scan_properties["f start"] += 1
    with pytest.raises(ValueError, match="Changed retained parameters"):
        value.trace.finish()
    assert value.trace.data()["complete"] is False


@pytest.mark.parametrize("scenario", sweep.SCENARIOS)
def test_scoped_admission_uses_both_actual_epochs_and_retains_complete_owner(scenario):
    g = published_graph(scenario)
    run.composition.event_scope(g.component)
    before = checkpoint.codec.fingerprint((g.source, g.early, g.pub))
    raw = sweep.declaration(g.source, g.entry, scenario)
    assert bridge.same(raw["event_owner"], g.pub.owner)
    assert checkpoint.codec.fingerprint((g.source, g.early, g.pub)) == before
    assert g.pub.event_finalized is g.early


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "source",
        "closure",
        "sequence",
        "before",
        "targets",
        "scalar",
        "phase",
        "duration",
        "extra",
        "dynamic",
    ],
)
def test_resealed_callback_authority_drift_cannot_admit_a_sweep(fault):
    g = published_graph()
    early = run.ions.data(g.early)
    records = early["sweep_callback_authority"]
    if fault == "missing":
        del early["sweep_callback_authority"]
    elif fault == "extra":
        records["P"] = copy.deepcopy(records["Namem"])
    elif fault == "dynamic":
        g.component.raw["event_owner"]["callbacks"]["Namem"]["dynamic"]["slope"] = -1.0
    else:
        row = records["Kmem"]
        if fault == "source":
            row["source"]["source_sha256"] = "0" * 64
        elif fault == "closure":
            row["closure"]["parameters"]["f start"] += 1
        elif fault == "sequence":
            row["sequence"] = 0
        elif fault == "before":
            row["before"]["f slope"] = None
        elif fault == "targets":
            row["targets"].reverse()
        elif fault == "scalar":
            row["source_scalar"] = 1.0
        elif fault == "phase":
            row["legacy_run_sim"] = 1
        else:
            row["source_configuration"]["sim_total_s"] += 1
        row["identity"] = run.ions.digest({k: v for k, v in row.items() if k != "identity"})
    if fault != "dynamic":
        reseal(g, early)
    with pytest.raises(ValueError):
        run.composition.event_scope(g.component)


@pytest.mark.parametrize(
    "scenario", ["sweep_Na_mem", "sweep_mixed_constant", "sweep_duplicate_targets"]
)
def test_closed_checkpoint_graph_preserves_both_epochs_callbacks_and_parent_aliases(
    tmp_path, scenario
):
    g = published_graph(scenario)
    payload = dict(
        component=g.component, publication=g.pub, early=g.early, inputs=g.source.event_owner_inputs
    )
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(payload)
    encoder.write(tmp_path, tree)
    loaded = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert checkpoint.codec.fingerprint(loaded) == checkpoint.codec.fingerprint(payload)
    assert (
        loaded["component"].source_binding.event_owner_inputs
        is loaded["inputs"]
        is loaded["publication"].inputs
    )
    assert loaded["publication"].event_finalized is loaded["early"]
    assert (
        loaded["component"].base.setup_receipt["event_finalization"]["owner_publication"]
        is loaded["publication"]
    )
    run.composition.event_scope(loaded["component"])


@pytest.mark.parametrize("flag", [None, *validation.RELEASES])
def test_sweep_route_requires_both_existing_gates_before_outputs_or_setup(
    tmp_path, monkeypatch, flag
):
    if flag:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="both existing Root releases"):
        validation.actual_continuity(
            tmp_path / "held",
            scenario="sweep_Na_mem",
            cut=1,
            preparation_route=sweep.ROUTE,
            event_owner_inputs=explicit_inputs(),
        )
    assert not (tmp_path / "held").exists()


@pytest.mark.parametrize("route", ["legacy", "published_global"])
def test_sweep_cannot_silently_enter_constant_or_published_global_route(
    tmp_path, monkeypatch, route
):
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError):
        validation.actual_continuity(
            tmp_path / "refused",
            scenario="sweep_Na_mem",
            cut=1,
            preparation_route=route,
            event_owner_inputs=explicit_inputs(),
        )
    assert not (tmp_path / "refused").exists()


@pytest.mark.parametrize("fault", ["missing", "dictionary", "INIT", "geometry"])
def test_supplied_authority_refuses_before_complete_INIT_with_complete_failed_input(
    tmp_path, fault
):
    g = graph()
    supplied = explicit_inputs()
    if fault == "missing":
        supplied = None
    elif fault == "dictionary":
        supplied = run.ions.data(supplied)
    elif fault == "INIT":
        supplied = replace(supplied, source_INIT_binding_identity="foreign")
    else:
        supplied = replace(supplied, source_geometry_binding_identity="foreign")
    attempts = []
    with pytest.raises(ValueError):
        sweep.prepare_sim(
            tmp_path / "SIM",
            plain_record(run.Binding, composition=g.completed.binding),
            "unowned INIT",
            attempts,
            scenario="sweep_Na_mem",
            event_owner_inputs=supplied,
        )
    assert [row["operation"] for row in attempts] == ["typed-event-owner-inputs"]
    assert attempts[0]["status"] == "refused"
    assert (tmp_path / "SIM/typed-event-owner-inputs/manifest.json").is_file()


def test_preparer_keeps_supplied_instance_configuration_and_transition_failure_evidence(
    tmp_path, monkeypatch
):
    g = graph()
    supplied = explicit_inputs()
    original = sim_template()
    original["source_setup"] = dict(
        frequency_sweep={"f start": 500.0, "f stop": 1500.0, "f slope": None}
    )
    before = copy.deepcopy(original)
    seen = []
    monkeypatch.setattr(
        run,
        "complete_INIT",
        lambda *a: plain_record(run.CompletedInitRun, complete_init="unowned complete INIT"),
    )
    monkeypatch.setattr(preparation.fixtures, "sim_inputs", lambda *a: original)

    def bound(raw, **kwargs):
        assert kwargs["event_owner_inputs"] is supplied
        seen.append(raw)
        return lifecycle.Binding(
            run.ions.freeze(raw), "INIT-binding", None, "unowned component", supplied
        )

    monkeypatch.setattr(lifecycle, "bind", bound)
    monkeypatch.setattr(
        preparation.fixtures, "declaration", lambda *a: dict(unowned="synthetic run declaration")
    )
    primary = RuntimeError("synthetic pre-transition stop")
    cause = ValueError("retained synthetic cause")
    primary.__cause__ = cause

    def refused(*args, **kwargs):
        assert args[2].event_owner_inputs is supplied
        raise primary

    monkeypatch.setattr(run, "transition", refused)
    attempts = []
    with pytest.raises(RuntimeError) as caught:
        sweep.prepare_sim(
            tmp_path / "SIM",
            plain_record(run.Binding, composition=g.completed.binding),
            "unowned INIT",
            attempts,
            scenario="sweep_Na_mem",
            event_owner_inputs=supplied,
        )
    assert caught.value is primary and caught.value.__cause__ is cause
    assert original == before and seen[0]["source_setup"] == original["source_setup"]
    assert seen[0]["sim_phase"]["setup"]["scheduled_options"]["Na_mem"][5] == "f_sweep"
    assert (tmp_path / "SIM/actual-INIT-to-SIM/manifest.json").is_file()
    assert attempts[-1]["status"] == "refused"


@pytest.mark.parametrize("supplied", [None, dict(ill_typed="no fixture authority")])
def test_missing_inputs_refuse_before_INIT_and_keep_complete_dispatcher_failure(
    tmp_path, monkeypatch, supplied, forbid_sweep_execution, no_actual_execution
):
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    original = Calls.observe

    def guarded(self, frame, event, arg):
        if event == "call" and frame.f_code in forbid_sweep_execution:
            no_actual_execution.append("actual sweep during dispatcher control")
            raise AssertionError("Actual sweep forbidden")
        return original(self, frame, event, arg)

    monkeypatch.setattr(Calls, "observe", guarded)
    for flag in validation.RELEASES:
        monkeypatch.setenv(flag, "1")
    previous = sys.getprofile()
    sys.setprofile(None)
    try:
        with pytest.raises(ValueError, match="explicit typed"):
            validation.actual_continuity(
                tmp_path / "refused",
                scenario="sweep_Na_mem",
                cut=1,
                preparation_route=sweep.ROUTE,
                event_owner_inputs=supplied,
            )
    finally:
        sys.setprofile(previous)
    assert (tmp_path / "refused/failure/manifest.json").is_file()
    attempts = json.loads((tmp_path / "refused/attempts.json").read_bytes())
    assert len(attempts["attempts"]) == 1 and attempts["attempts"][0]["status"] == "refused"
    assert attempts["invocation_accounting"]["profile_intact"] is True


def test_runtime_observer_reads_manufactured_qualified_closure_and_partial_return(tmp_path):
    class Base:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            return dict(counts={})

    stream = io.StringIO()
    observed = sweep.observer(Base, stream, literal.__file__, tmp_path)
    source = sweep.source_order(literal.__file__)
    program = plain_record(
        time_laws.Program,
        kind="sweep",
        frequency_Hz=500.0,
        phase_rad=0.0,
        slope_Hz_s=125.0,
        automatic_slope=False,
        requested_stop_Hz=None,
        original_duration_s=None,
        provenance="Unowned synthetic observer program",
        identity="",
    )
    object.__setattr__(program, "identity", time_laws.record(program)["identity"])
    code = next(
        c
        for c in literal.prepared_callback.__code__.co_consts
        if type(c) is CodeType and c.co_firstlineno == source["sweep_callback_line"]
    )
    function = FunctionType(code, vars(literal), closure=(CellType(program),))
    owner = SimpleNamespace(dyna_Namem=function, scalar_Namem=1, targets_Namem=[2, 0, 2, 0])
    tissue = SimpleNamespace(
        f_code=literal.TissueHandler._fire_events_tissue.__code__,
        f_globals=vars(literal),
        f_locals=dict(t=0.0, self=owner),
        f_lineno=source["branches"][0]["line"] + 1,
        f_back=None,
    )
    callback_frame = SimpleNamespace(
        f_code=code, f_globals=vars(literal), f_locals=dict(t=0.0, program=program), f_back=tissue
    )
    global_frame = SimpleNamespace(
        f_code=literal.TissueHandler._fire_events_global.__code__,
        f_globals=vars(literal),
        f_locals=dict(t=0.0),
        f_back=None,
    )
    observed.observe(global_frame, "call", None)
    observed.observe(global_frame, "return", None)
    observed.observe(tissue, "call", None)
    observed.observe(callback_frame, "call", None)
    observed.observe(callback_frame, "return", np.float64(0.4))
    observed.observe(callback_frame, "call", None)
    observed.observe(callback_frame, "return", None)
    observed.observe(tissue, "return", None)
    result = observed.stop()
    assert len(result["global_dispatches"]) == 1 and len(result["sweep_dispatches"]) == 1
    rows = result["sweep_dispatches"][0]["events"]
    assert rows[0]["returned"] and rows[0]["program"]["slope"] == 125.0
    assert rows[0]["targets"] == [2, 0, 2, 0] and rows[0]["value_dtype"] == "<f8"
    assert rows[1]["returned"] is False and result["sweep_profile_complete"]
    assert len((tmp_path / "sweep-callbacks.jsonl").read_text().splitlines()) == 4
    assert not any(e.get("scientific_acceptance", False) for e in rows)


def test_sweep_streams_close_while_preserving_accounting_failure(tmp_path):
    primary = OSError("synthetic accounting failure")

    class Broken:
        def __init__(self, stream):
            pass

        def observe(self, *args):
            pass

        def stop(self):
            raise primary

    observed = sweep.observer(Broken, io.StringIO(), literal.__file__, tmp_path)
    with pytest.raises(OSError) as caught:
        observed.stop()
    assert caught.value is primary
    assert observed.sweep_stream.closed and observed.pulse_stream.closed


def call_observations():
    g = published_graph("sweep_mixed_constant")
    owner = g.component.raw["event_owner"]
    binding = sweep.source_order(literal.__file__)
    labels = [0.0, 1.5, 3.0]
    selected = {
        k: owner["handler_fields"]["targets_" + s]
        for k, s in authority.MEMBRANE_KEYS.items()
        if owner["scheduled_options"][k] != 0
    }
    anchor = dict(
        labels=labels,
        ion_ids=["Na", "K", "Cl", "Ca"],
        targets=selected,
        scheduled_options=owner["scheduled_options"],
        callbacks=owner["callbacks"],
    )
    groups = []
    for i in range(6):
        t = labels[i % 3]
        rows = []
        for key in selected:
            configured = owner["scheduled_options"][key]
            kind = "sweep" if configured[5] == "f_sweep" else "constant"
            row = dict(
                key=key,
                operation="callback",
                returned=True,
                parameters=[t],
                kind=kind,
                scalar=1,
                targets=selected[key],
                source_sha256=binding["sha256"],
                callback_line=binding[kind + "_callback_line"],
                runtime_code_matches=True,
                value=0.4 if kind == "sweep" else 1.0,
                value_type="float64" if kind == "sweep" else "int",
                value_shape=[],
                value_dtype="<f8" if kind == "sweep" else None,
            )
            if kind == "sweep":
                dynamic = owner["callbacks"][authority.MEMBRANE_KEYS[key]]["dynamic"]
                row["program"] = dict(
                    start=dynamic["start"],
                    slope=dynamic["slope"],
                    automatic_slope=False,
                    provenance=dynamic["provenance"],
                )
            rows.extend(
                (
                    row,
                    dict(
                        key=key,
                        operation="pulse",
                        returned=True,
                        value=0.5,
                        parameters=[t, *configured[:3]],
                    ),
                )
            )
        groups.append(dict(label=t, exited=True, events=rows))
    accounting = dict(
        sweep_dispatches=groups,
        sweep_source_binding=binding,
        sweep_profile_complete=True,
        counts={
            authority.source.__name__ + ".f_sweep": 37,
            literal.__name__ + ".prepared_callback": 77,
            time_laws.__name__ + ".sweep_program": 99,
        },
    )
    return accounting, anchor


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "duplicate",
        "omission",
        "order",
        "target",
        "coefficient",
        "phase-clock",
        "unwind",
        "shape",
        "provenance",
        "factory-accounting",
    ],
)
def test_sweep_pulse_comparison_detects_duplicate_omitted_foreign_work_without_running_laws(fault):
    accounting, anchor = call_observations()
    group = accounting["sweep_dispatches"][0]
    row = group["events"][0]
    if fault == "duplicate":
        group["events"].append(copy.deepcopy(row))
    elif fault == "omission":
        group["events"].pop()
    elif fault == "order":
        group["events"].reverse()
    elif fault == "target":
        row["targets"] = [1]
    elif fault == "coefficient":
        row["program"]["slope"] = -1.0
    elif fault == "phase-clock":
        group["label"] += 0.1
    elif fault == "unwind":
        row["returned"] = False
    elif fault == "shape":
        row["value_shape"] = [1]
    elif fault == "provenance":
        row["program"]["provenance"] = "foreign"
    elif fault == "factory-accounting":
        accounting["counts"] = {}
    if fault is not None:
        with pytest.raises(ValueError):
            sweep.check_calls(accounting, anchor)
    else:
        checked = sweep.check_calls(accounting, anchor)
        assert checked["independent_cases"] == 0
        assert (
            checked["factory_recreation_and_nested_work"][authority.source.__name__ + ".f_sweep"]
            == 37
        )
