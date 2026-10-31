"""Model/RNG/native-blocked event checkpoint transport and observation controls."""

import copy
import importlib.abc
import json
import sys
from dataclasses import fields
from types import SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_checkpoint as checkpoint
from cells.processes import betse_normal_ecm_molecule_checkpoint_records as records
from cells.processes import betse_normal_ecm_molecule_events as events
from cells.processes import betse_normal_ecm_molecule_run_lifecycle as run
from validation.betse import betse_normal_ecm_molecule_event_checkpoint as validation

component = run.composition


def plain_record(cls, **values):
    """Unowned synthetic record; never submit it to a model/admission API."""
    result = object.__new__(cls)
    for field in fields(cls):
        object.__setattr__(result, field.name, values.get(field.name))
    return result


@pytest.fixture(autouse=True)
def no_actual_execution(monkeypatch, tmp_path):
    attempted = []

    def forbid(label):
        def refused(*args, **kwargs):
            attempted.append(label)
            raise AssertionError("Actual model/native/RNG execution forbidden: " + label)

        return refused

    class NoNative(importlib.abc.MetaPathFinder):
        def find_spec(self, fullname, path=None, target=None):
            if fullname == "betse" or fullname.startswith("betse."):
                attempted.append(fullname)
                raise AssertionError("Native execution/import forbidden")
            return None

    guard = NoNative()
    sys.meta_path.insert(0, guard)
    for module, names in (
        (events, ("bind", "begin", "verify_binding", "verify", "advance", "prepare_events")),
        (events.events, ("fire", "fire_events_guarded", "pulse", "noise", "reset_fluxes")),
        (
            component.phase,
            ("bind", "initialize", "verify_binding", "verify", "advance", "owner_context"),
        ),
        (
            component.lifecycle,
            ("bind", "validate_binding", "check_complete", "transition", "verify", "advance"),
        ),
        (component.lifecycle.setup, ("prepare", "numpy_restore")),
        (component.lifecycle.setup.init_setup, ("python_restore",)),
        (
            run,
            (
                "bind",
                "verify",
                "advance",
                "pause",
                "resume",
                "begin",
                "complete_INIT",
                "transition",
            ),
        ),
        (checkpoint, ("save_checkpoint", "load_checkpoint", "_rng_identity")),
        (np.random, ("get_state", "set_state", "RandomState", "default_rng")),
    ):
        for name in names:
            monkeypatch.setattr(module, name, forbid(module.__name__ + "." + name))
    for name in validation.RELEASES:
        monkeypatch.delenv(name, raising=False)
    yield attempted
    sys.meta_path.remove(guard)
    (tmp_path / "software-control.json").write_text(
        json.dumps(
            dict(
                actual_model_native_RNG_entry_attempts=attempted,
                synthetic_only=True,
                parent_admission=False,
                scientific_acceptance=False,
            )
        )
    )
    assert attempted == []


def owner():
    return dict(
        global_options=dict(
            T_change=[0.5, 2.0, 0.7, 0.01], K_env=0, Cl_env=0, Na_env=0, gj_block=0, NaKATP_block=0
        ),
        scheduled_options=dict(Na_mem=0, K_mem=0, Cl_mem=0, Ca_mem=0, ecmJ=0, pressure=0),
        callbacks={},
        voltage=None,
        handler_fields=dict(tonT=0.5, toffT=2.0, trampT=0.7, multT=0.01),
    )


def synthetic_owner():
    flags = {
        key: False
        for key in (
            "fluid_flow",
            "td_deform",
            "sim_eosmosis",
            "physical_initialization",
            "cut_requested",
            "Ca_dyn",
        )
    }
    flags.update(solver="FULL", is_ecm=True)
    receipt = dict(
        numpy_rng_after={"owned": "numpy-supplied"},
        event_finalization=dict(python_rng_after={"owned": "python-supplied"}),
    )
    base = plain_record(
        component.phase.Binding,
        identity="phase",
        call_limit=3,
        calendar=SimpleNamespace(phase="SIM"),
        inputs_raw=dict(
            time_profile={"phase": "SIM"},
            flags=flags,
            setup=dict(channel_noise_level=0, dynamic_noise=dict(enabled=False, level=0.0)),
        ),
        setup_receipt=receipt,
    )
    complete = plain_record(component.lifecycle.CompleteInit, identity="complete-INIT")
    entry = plain_record(component.lifecycle.SimPhase, phase_binding=base, source_init=complete)
    binding = events.Binding(
        "synthetic-source", entry, {"event_owner": owner()}, "synthetic-event-binding"
    )
    state = plain_record(
        events.State, binding_identity=binding.identity, clock=SimpleNamespace(call_index=1)
    )
    return binding, state


def test_existing_event_binding_delegates_without_regenerating_owner(monkeypatch):
    binding, state = synthetic_owner()
    observed = []
    monkeypatch.setattr(events, "verify_binding", lambda value: observed.append(("binding", value)))
    monkeypatch.setattr(events, "verify", lambda b, p: observed.append(("parent", b, p)))

    def advanced(b, p, **kwargs):
        observed.append(("advance", b, p, kwargs))
        return "synthetic-return", "synthetic-context"

    monkeypatch.setattr(events, "advance", advanced)
    assert component.kind(binding) == "SIM"
    assert component.calendar(binding) is binding.base.calendar
    assert component.call_limit(binding) == 3
    assert component.profile(binding) is binding.base.inputs_raw["time_profile"]
    assert component.phase_state(state) is state and component.cursor(state) == 1
    callback = object()
    assert component.advance(binding, state, phase_observer=callback) == (
        "synthetic-return",
        "synthetic-context",
    )
    assert observed[-1] == ("advance", binding, state, dict(observer=callback))
    assert component.phase_binding(binding, state) is binding.base
    assert component.source_init(binding, state) is binding.source_entry.source_init
    assert binding.source_entry.phase_binding is binding.base


@pytest.mark.parametrize(
    "fault", ["temperature-zero", "pressure", "salt", "voltage", "callback", "membrane"]
)
def test_run_event_scope_allows_temperature_zero_but_refuses_other_mechanisms(fault):
    binding, _ = synthetic_owner()
    raw = binding.raw["event_owner"]
    if fault == "temperature-zero":
        raw["global_options"]["T_change"] = 0
    elif fault == "pressure":
        raw["scheduled_options"]["pressure"] = [0, 1, 1, 1, [], None]
    elif fault == "salt":
        raw["global_options"]["K_env"] = [0, 1, 1, 1]
    elif fault == "voltage":
        raw["voltage"] = {"peak": 1}
    elif fault == "callback":
        raw["callbacks"]["P"] = {"kind": "unowned"}
    else:
        raw["scheduled_options"]["Na_mem"] = [0, 1, 1, 1, [], None]
    if fault in ("temperature-zero", "salt"):
        component.event_scope(binding)
    else:
        with pytest.raises(ValueError, match="deterministic global|finalized constant"):
            component.event_scope(binding)


def test_foreign_event_state_cannot_supply_an_INIT_association():
    binding, state = synthetic_owner()
    object.__setattr__(state, "binding_identity", "foreign-event-binding")
    with pytest.raises(ValueError, match="Foreign event state"):
        component.source_init(binding, state)
    with pytest.raises(ValueError, match="Foreign event state"):
        component.phase_binding(binding, state)


@pytest.mark.parametrize("kind", ["dictionary", "namespace", "binding-subclass"])
def test_generic_or_foreign_binding_cannot_select_typed_owners(kind):
    binding, state = synthetic_owner()
    data = vars(binding)
    if kind == "dictionary":
        supplied = dict(data)
    elif kind == "namespace":
        supplied = SimpleNamespace(**data)
    else:

        class ForeignBinding(events.Binding):
            pass

        supplied = ForeignBinding(**data)
    for check in (component.kind, component.verify_binding, component.calendar):
        with pytest.raises(ValueError):
            check(supplied)
    for check in (component.phase_binding, component.source_init):
        with pytest.raises(ValueError):
            check(supplied, state)


@pytest.mark.parametrize("kind", ["dictionary", "namespace"])
def test_generic_state_cannot_select_an_event_phase_or_INIT(kind):
    binding, state = synthetic_owner()
    supplied = dict(vars(state)) if kind == "dictionary" else SimpleNamespace(**vars(state))
    for check in (component.phase_binding, component.source_init):
        with pytest.raises(ValueError):
            check(binding, supplied)
    with pytest.raises(ValueError):
        component.phase_state(supplied)


def test_native_sampling_stays_closed_for_event_state(monkeypatch):
    binding, state = synthetic_owner()
    observed = []
    monkeypatch.setattr(events, "verify", lambda *args: observed.append(args))
    with pytest.raises(ValueError, match="Native storage/display remains unsupported"):
        component.sample(binding, state)
    assert observed == [(binding, state)]


def test_ordinary_INIT_and_SIM_owner_selection_is_unchanged():
    initial = plain_record(component.phase.Binding, calendar=SimpleNamespace(phase="INIT"))
    sim = plain_record(component.lifecycle.Binding)
    source = object()
    phase = object()
    entry = plain_record(component.lifecycle.SimPhase, source_init=source, phase_binding=phase)
    assert component.kind(initial) == "INIT" and component.kind(sim) == "SIM"
    assert component.phase_binding(initial, None) is initial
    assert component.phase_binding(sim, entry) is phase
    assert component.source_init(sim, entry) is source


def test_event_entry_receipt_retains_actual_prior_INIT_link(monkeypatch):
    binding, state = synthetic_owner()
    root = SimpleNamespace(composition=binding, calendar=SimpleNamespace(identity="calendar"))
    previous = SimpleNamespace(complete_init=binding.source_entry.source_init)
    observed = []
    monkeypatch.setattr(run, "_binding", lambda b: observed.append("binding-check-mock"))
    monkeypatch.setattr(run, "verify_completed_INIT", lambda p: observed.append("INIT-check-mock"))
    value = run.entry_receipt(
        root, state, provenance="Synthetic association control only", previous_phase=previous
    )
    assert (
        value["previous_phase"] is previous
        and value["composition_state_identity"] == state.identity
    )
    assert value["declaration_is_initialization_attestation"] is False
    assert observed == ["binding-check-mock", "INIT-check-mock"]


def test_checkpoint_scope_reads_retained_event_phase_and_owned_manifests(monkeypatch):
    binding, state = synthetic_owner()
    observed = []
    monkeypatch.setattr(
        component.lifecycle.setup,
        "numpy_restore",
        lambda value: observed.append(("numpy-parser-mock", value)),
    )
    monkeypatch.setattr(
        component.lifecycle.setup.init_setup,
        "python_restore",
        lambda value: observed.append(("python-parser-mock", value)),
    )
    root = SimpleNamespace(composition=binding)
    parent = SimpleNamespace(
        active=state,
        cursor=1,
        entry_receipt=dict(native_load_called=False, physical_seed_claim=False),
    )
    checkpoint._scope(root, parent)
    assert [name for name, _ in observed] == ["numpy-parser-mock", "python-parser-mock"]
    assert observed[0][1] == binding.base.setup_receipt["numpy_rng_after"]
    assert observed[1][1] == binding.base.setup_receipt["event_finalization"]["python_rng_after"]


def test_closed_codec_preserves_event_records_runtime_state_and_aliases(tmp_path):
    complete = plain_record(
        component.lifecycle.CompleteInit, identity="synthetic-unowned-INIT", scope="software only"
    )
    source = plain_record(
        component.lifecycle.SimPhase,
        identity="source",
        source_init=complete,
        phase_binding={"phase": "SIM"},
    )
    declaration = events.Binding(
        "unowned source binding", source, {"event_owner": owner()}, "event"
    )
    arrays = np.array([[1.0, 2.0]], dtype=np.float64)
    stores = {"T": 310.0, "event_epoch": 1, "owned_RNG": {"source_manifest": "retained metadata"}}
    state = plain_record(
        events.State,
        binding_identity="event",
        stores=stores,
        clock={"call_index": 1},
        runtime_material_binding={"material_epoch": 1, "values": arrays},
        runtime_definition={"event_owner": "event"},
        entry_receipt={"source_entry_identity": "source"},
        identity="synthetic unowned state",
    )
    graph = {"binding": declaration, "state": state, "stores": stores, "INIT": complete}
    encoder = checkpoint.codec.Encoder()
    tree = encoder.capture(graph)
    encoder.write(tmp_path, tree)
    restored = checkpoint.codec.decode(tree, (tmp_path / "arrays.npz").read_bytes())
    assert type(restored["binding"]) is events.Binding and type(restored["state"]) is events.State
    assert restored["state"].stores is restored["stores"]
    assert restored["binding"].source_entry.source_init is restored["INIT"]
    assert restored["state"].runtime_material_binding["values"].dtype == arrays.dtype
    assert checkpoint.codec.fingerprint(restored) == checkpoint.codec.fingerprint(graph)
    assert {"Binding", "State"} == set(records.RECORDS[events.__name__])
    # Structural codec transport does not admit this synthetic graph as a run parent.
    assert not isinstance(restored["state"], run.RunState)


def test_producer_binds_lazy_event_code_before_a_first_event(tmp_path):
    identity = checkpoint.producer_identity()
    for name in ("events", "events_step", "events_material", "events_pump", "events_source"):
        assert "processes/betse_normal_ecm_molecule_" + name + ".py" in identity["source_hashes"]
    (tmp_path / "producer-identity.json").write_text(json.dumps(identity, sort_keys=True))


def raw_program():
    return dict(event_owner=owner(), provenance="Existing source-law declaration")


@pytest.mark.parametrize("scenario", validation.TEMPERATURE_SCENARIOS)
def test_original_program_or_explicit_boundary_control_changes_only_declared_times(scenario):
    raw = raw_program()
    if scenario == "no_events":
        raw["event_owner"]["global_options"]["T_change"] = 0
    before = copy.deepcopy(raw)
    result = validation.program(raw, scenario, [0.0, 1.5, 3.0])
    assert raw == before
    if scenario == "temperature_boundaries":
        assert result["event_owner"]["global_options"]["T_change"] == [1.5, 3.0, 0.7, 0.01]
        assert result["event_owner"]["handler_fields"] == dict(
            tonT=1.5, toffT=3.0, trampT=0.7, multT=0.01
        )
    else:
        assert result == raw


def observation():
    anchor = dict(
        scenario="temperature",
        phase="SIM",
        event_binding="binding",
        source_binding="source",
        source_entry="entry",
        source_INIT="INIT",
        calendar="calendar",
        event_owner="owner",
        owned_RNG="rng",
        entry_state="state-0",
        entry_T="T0",
        labels=[0.0, 1.5, 3.0],
        samples=[1],
    )
    rows = [
        dict(
            call_index=i,
            label=anchor["labels"][i],
            event_owner="owner",
            phase="SIM",
            legacy_run_sim=True,
            event_fire_calls=1,
            flux_resets=1,
            noise_calls=0,
            stages=list(validation.STAGES),
            source_completed=True,
            before_state="state-" + str(i),
            after_state="state-" + str(i + 1),
            T_before="T" + str(i),
            T_after="T" + str(i + 1),
        )
        for i in range(3)
    ]
    value = {
        key: anchor[key]
        for key in (
            "phase",
            "event_binding",
            "source_binding",
            "source_entry",
            "source_INIT",
            "calendar",
            "event_owner",
            "owned_RNG",
        )
    }
    value.update(cursor=3, rows=rows, samples=[1], active_state="state-3")
    return value, anchor


def test_observations_bind_full_prefix_sampling_and_event_epoch():
    value, anchor = observation()
    assert validation.check_observation(value, anchor) is value
    prefix = copy.deepcopy(value)
    prefix.update(cursor=1, rows=prefix["rows"][:1], samples=[], active_state="state-1")
    assert validation.check_observation(prefix, anchor) is prefix


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate",
        "omit",
        "count",
        "phase",
        "owner",
        "clock",
        "stage",
        "sampling",
        "RNG",
        "INIT",
        "chain",
        "effect",
        "uncommitted",
        "noise",
    ],
)
def test_duplicate_omitted_event_or_changed_phase_owner_state_is_refused(fault):
    value, anchor = observation()
    if fault == "duplicate":
        value["rows"][1] = copy.deepcopy(value["rows"][0])
    elif fault == "omit":
        value["rows"].pop()
    elif fault == "count":
        value["rows"][1]["event_fire_calls"] = 2
    elif fault == "phase":
        value["rows"][1]["phase"] = "INIT"
    elif fault == "owner":
        value["event_owner"] = "foreign"
    elif fault == "clock":
        value["rows"][1]["label"] = 1.6
    elif fault == "stage":
        value["rows"][1]["stages"].append("makeAllChanges")
    elif fault == "sampling":
        value["samples"] = [1, 1]
    elif fault == "RNG":
        value["owned_RNG"] = "foreign"
    elif fault == "INIT":
        value["source_INIT"] = "foreign"
    elif fault == "chain":
        value["rows"][1]["before_state"] = "state-0"
    elif fault == "effect":
        for row in value["rows"]:
            row["T_after"] = "T0"
    elif fault == "uncommitted":
        value["active_state"] = "unrecorded-state"
    else:
        value["rows"][1]["noise_calls"] = 1
    with pytest.raises(ValueError):
        validation.check_observation(value, anchor)


def test_zero_event_control_requires_unchanged_temperature_but_still_counts_dispatches():
    value, anchor = observation()
    anchor["scenario"] = "no_events"
    for row in value["rows"]:
        row.update(T_before="T0", T_after="T0")
    validation.check_observation(value, anchor)
    value["rows"][1]["T_after"] = "changed"
    with pytest.raises(ValueError, match="Zero-event"):
        validation.check_observation(value, anchor)


@pytest.mark.parametrize(
    "time,expected",
    [
        (0.0, "before_onset"),
        (0.5, "onset"),
        (1.0, "active"),
        (2.0, "release"),
        (3.0, "after_release"),
    ],
)
def test_boundary_time_controls_do_not_evaluate_a_pulse(time, expected):
    assert validation.boundary(time, 0.5, 2.0) == expected


@pytest.mark.parametrize("flag", [None, *validation.RELEASES])
def test_actual_continuity_is_held_before_setup_imports_or_output(tmp_path, monkeypatch, flag):
    if flag is not None:
        monkeypatch.setenv(flag, "1")
    with pytest.raises(ValueError, match="both existing Root releases"):
        validation.actual_continuity(tmp_path / "held", scenario="temperature", cut=1)
    assert not (tmp_path / "held").exists()


@pytest.mark.parametrize(
    "secondary", ["none", "failure-archive", "profile-stop", "attempt-journal"]
)
def test_stubbed_prerequisite_failure_preserves_cause_partial_and_accounting(
    tmp_path, monkeypatch, secondary
):
    """Exercise orchestration failure only; the real INIT producer is blocked."""
    from validation.betse import betse_normal_ecm_molecule_checkpoint as preparation
    from validation.betse import betse_normal_ecm_molecule_handoff as handoff
    from validation.betse.betse_normal_ecm_molecule_handoff_run_plugin import Calls

    primary = RuntimeError("synthetic owned-prerequisite refusal; no model entered")
    cause = ValueError("synthetic original cause")
    primary.__cause__ = cause
    primary.partial = {"synthetic_only": True, "actual_model_entries": 0}
    requests = []

    def prerequisite(directory, case, attempts):
        requests.append(case)
        attempts.append(
            dict(
                operation="synthetic prerequisite stub",
                status="refused",
                numerical_work_possible=False,
                synthetic_only=True,
            )
        )
        raise primary

    monkeypatch.setattr(preparation, "prepare_INIT", prerequisite)
    if secondary == "failure-archive":

        def refuse_archive(*args, **kwargs):
            raise OSError("synthetic failure-archive I/O refusal")

        monkeypatch.setattr(preparation.archives, "write_archive", refuse_archive)
    elif secondary == "profile-stop":
        original_stop = Calls.stop

        def refuse_stop(self):
            original_stop(self)  # Always remove the real observer before injecting I/O failure.
            raise OSError("synthetic profile-stop refusal")

        monkeypatch.setattr(Calls, "stop", refuse_stop)
    elif secondary == "attempt-journal":
        original_write = validation.write_json

        def refuse_journal(path, value):
            if path.name == "attempts.json":
                raise OSError("synthetic attempt-journal I/O refusal")
            return original_write(path, value)

        monkeypatch.setattr(validation, "write_json", refuse_journal)
    # Both flags apply only within this fully blocked software control. The
    # first producer is a stub; all actual model/RNG entries remain forbidden.
    for name in validation.RELEASES:
        monkeypatch.setenv(name, "1")
    output = tmp_path / "stubbed-orchestration"
    with pytest.raises(RuntimeError, match="synthetic owned-prerequisite refusal") as caught:
        validation.actual_continuity(output, scenario="temperature", cut=1)
    assert caught.value is primary and caught.value.__cause__ is cause
    assert primary.partial == {"synthetic_only": True, "actual_model_entries": 0}
    assert requests == ["zero_INIT_calls"] and not (output / "result.json").exists()
    assert sys.getprofile() is None
    if secondary != "failure-archive":
        raw = json.loads((output / "failure/data.json").read_text())
        assert handoff._get(raw, "failure", "message") == str(primary)
        assert str(cause) in handoff._get(raw, "failure", "traceback")
        partial = handoff._get(raw, "available", "partial")
        assert handoff._get(partial, "synthetic_only") is True
    if secondary != "attempt-journal":
        journal = json.loads((output / "attempts.json").read_text())
        assert journal["attempts"][0]["synthetic_only"] is True
        assert journal["attempts"][0]["status"] == "refused"
    if secondary != "none":
        assert any(secondary in note for note in primary.__notes__)
    (tmp_path / "failure-accounting-control.json").write_text(
        json.dumps(
            dict(
                synthetic_only=True,
                secondary=secondary,
                primary_and_cause_preserved=True,
                partial_preserved=True,
                success_result_absent=True,
                real_model_RNG_calls=0,
                scientific_acceptance=False,
            )
        )
    )
