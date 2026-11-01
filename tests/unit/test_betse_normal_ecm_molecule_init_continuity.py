"""Native/model/RNG-blocked in-process bridge controls; no admitted owner.

Typed records and replacement producers are explicitly synthetic software
controls. No positive INIT/SIM result is produced or accepted as authority.
"""

import copy
import json
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from tests.unit.test_betse_normal_ecm_molecule_current_continuity import (
    declaration as SIM_declaration,
)
from tests.unit.test_betse_normal_ecm_molecule_current_continuity import (
    no_formatter_execution as no_formatter_execution,
)
from tests.unit.test_betse_normal_ecm_molecule_current_continuity import (
    parents as structural_parents,
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
from validation.betse import betse_normal_ecm_molecule_init_continuity as bridge


def declaration(count=1):
    return plain_record(
        bridge.phase.Declaration,
        inputs=dict(
            kind=bridge.phase.INPUT_KIND,
            time_profile=dict(phase="INIT"),
            flags=dict(phase="INIT", _run_sim=False),
            stop_after_calls=count,
        ),
        calendar=plain_record(
            bridge.run.calendars.NativePhaseCalendar, phase="INIT", step_count=count
        ),
        identity="unowned-synthetic-declaration",
    )


def contract():
    return dict(
        kind=bridge.run.INPUT_KIND,
        case_id="explicit-Root-case",
        run_id="explicit-Root-run",
        component_binding_identity=None,
        time_profile=dict(phase="INIT"),
        entry_mode="supplied_molecule54_phase_entry",
        observation_mode="headless_only_native_display_refused",
        stop_policy="accepted_call_boundaries_only",
        persistence="none",
    )


def keep(path, payload):
    bridge.retention.archives.write_archive(
        path,
        bridge.run.ions.data(
            dict(
                payload,
                synthetic_only=True,
                scientific_acceptance=False,
                parent_admission=False,
                actual_source_entries=0,
                independent_biological_cases=0,
            )
        ),
    )


def gates(monkeypatch):
    for name in bridge.RELEASES:
        monkeypatch.setenv(name, "1")


def inputs(tmp_path):
    return dict(
        repository=str(tmp_path / "repo"),
        native_root=str(tmp_path / "native"),
        provenance="synthetic control only, not original/native authority",
        input_evidence=[dict(synthetic=True)],
        input_producer=dict(synthetic=True),
        expected_producer=dict(synthetic=True),
        INIT_inputs={},
        snapshot=dict(synthetic=True),
        retained_evidence=[],
        source_selection=dict(synthetic=True),
        formatter_reference_source_plan=dict(synthetic=True),
    )


def observation(path):
    return bridge.continuity.read_typed_observation(
        path, manifest_sha256=bridge.snapshot.digest(path / "manifest.json")
    )


@pytest.mark.parametrize("count", [0, 1, 3])
def test_original_declaration_bounds_never_attest_owner_admission(count, tmp_path):
    value = bridge.preflight_declaration(declaration(count))
    assert value["original_calls"] == count and value["owner_admission"] is False
    keep(tmp_path / "declaration-control", value)


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "dictionary",
        "SIM",
        "boolean-count",
        "long-calendar",
        "capped",
        "wrong-flags",
        "wrong-profile",
        "boolean-cap",
    ],
)
def test_missing_foreign_and_prefix_declarations_refuse_before_setup(fault, tmp_path):
    value = declaration()
    if fault == "missing":
        value = None
    elif fault == "dictionary":
        value = dict(status="exhausted")
    elif fault in {"SIM", "boolean-count", "long-calendar"}:
        value = replace(
            value,
            calendar=replace(
                value.calendar,
                **(
                    {"phase": "SIM"}
                    if fault == "SIM"
                    else {"step_count": True if fault == "boolean-count" else 4}
                ),
            ),
        )
    else:
        value = copy.deepcopy(value)
        if fault == "capped":
            value.inputs["stop_after_calls"] = 0
        elif fault == "boolean-cap":
            value.inputs["stop_after_calls"] = True
        elif fault == "wrong-flags":
            value.inputs["flags"]["_run_sim"] = True
        else:
            value.inputs["time_profile"]["phase"] = "SIM"
    with pytest.raises(ValueError) as caught:
        bridge.preflight_declaration(value)
    keep(tmp_path / "declaration-refusal", dict(fault=fault, primary=str(caught.value)))


@pytest.mark.parametrize("fault", [None, "missing", "profile", "native", "label", "owner"])
def test_run_contract_only_associates_the_actual_returned_owner(fault, tmp_path):
    value = contract()
    owner = SimpleNamespace(identity="actual-owner-ID-required-at-runtime")
    if fault == "missing":
        value.pop("run_id")
    elif fault == "profile":
        value["time_profile"]["phase"] = "SIM"
    elif fault == "native":
        value["persistence"] = "native_pickle"
    elif fault == "label":
        value["run_id"] = ""
    elif fault == "owner":
        value["component_binding_identity"] = "foreign"
    before = copy.deepcopy(value)
    if fault is None:
        actual = bridge.run_contract(value, owner)
        assert actual["component_binding_identity"] == owner.identity and value == before
        assert {key for key in actual if actual[key] != value[key]} == {
            "component_binding_identity"
        }
        keep(tmp_path / "actual-owner-association", dict(input=value, returned=actual))
    else:
        with pytest.raises(ValueError):
            bridge.run_contract(value, owner)


@pytest.mark.parametrize("kind", ["declaration", "plain-owner-data"])
def test_closed_transport_decodes_only_input_data_without_setup_or_a_positive_parent(
    kind, tmp_path
):
    value = dict(declaration=declaration(), run_inputs=contract())
    if kind == "plain-owner-data":
        value = dict(owners=["explicit supplied data"], positive_run=None)
    row = bridge.write_graph(tmp_path / "input", value)
    restored = bridge.read_graph(tmp_path / "input", row)
    assert bridge.checkpoint.codec.fingerprint(restored) == bridge.checkpoint.codec.fingerprint(
        value
    )
    assert not isinstance(restored, bridge.run.RunState)
    keep(tmp_path / "closed-input-transport", dict(input=value, restored=restored))


@pytest.mark.parametrize("states", [("0", "0"), ("1", "0"), ("0", "1")])
@pytest.mark.parametrize("entry", ["acquire", "continue"])
def test_existing_gates_precede_packet_and_output_access(monkeypatch, tmp_path, states, entry):
    for name, state in zip(bridge.RELEASES, states, strict=True):
        monkeypatch.setenv(name, state)
    with pytest.raises(ValueError, match="Both existing Root releases"):
        if entry == "acquire":
            bridge.acquire_INIT(
                tmp_path / "output", packet=tmp_path / "absent", packet_sha256="none"
            )
        else:
            bridge.continue_INIT(
                tmp_path / "output",
                packet=tmp_path / "absent",
                packet_sha256="none",
                completed=None,
                acquisition_result=tmp_path / "absent",
                acquisition_result_sha256="none",
                sim_declaration=None,
            )
    assert not (tmp_path / "output").exists()


@pytest.mark.parametrize("mediated", [False, True])
def test_inside_packet_refusal_cannot_write_failure_or_output(monkeypatch, tmp_path, mediated):
    gates(monkeypatch)
    packet = tmp_path / "packet"
    packet.mkdir()
    target = packet / "output"
    if mediated:
        link = tmp_path / "link"
        link.symlink_to(packet, target_is_directory=True)
        target = link / "output"
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: inputs(tmp_path))
    with pytest.raises(ValueError, match="Output must be separate"):
        bridge.acquire_INIT(target, packet=packet, packet_sha256="synthetic")
    assert list(packet.iterdir()) == []


def test_missing_actual_input_is_retained_without_any_SETUP_or_SIM_entry(monkeypatch, tmp_path):
    gates(monkeypatch)
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: inputs(tmp_path))
    monkeypatch.setattr(bridge, "read_graph", lambda *args: dict(declaration=None, run_inputs=None))
    target = tmp_path / "output"
    with pytest.raises(ValueError, match="Explicit typed pre-setup INIT declaration"):
        bridge.acquire_INIT(target, packet=tmp_path / "packet", packet_sha256="synthetic")
    assert not (target / "result.json").exists() and not (target / "invocations.jsonl").exists()
    assert (target / "source-failure/manifest.json").is_file()
    saved = json.loads((target / "attempts.json").read_text())
    assert [row["operation"] for row in saved["attempts"]] == [
        "closed-INIT-inputs",
        "typed-current-INIT-declaration",
    ]


@pytest.mark.parametrize("fault", ["provenance", "evidence", "producer", "run-contract", "profile"])
def test_missing_input_authority_or_run_contract_refuses_before_numeric_work(
    monkeypatch, tmp_path, fault
):
    gates(monkeypatch)
    config, declared, template = inputs(tmp_path), declaration(), contract()
    if fault == "provenance":
        config["provenance"] = ""
    elif fault == "evidence":
        config["input_evidence"] = []
    elif fault == "producer":
        config["input_producer"] = dict(foreign=True)
    elif fault == "run-contract":
        template = None
    else:
        template["time_profile"]["phase"] = "SIM"
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: config)
    monkeypatch.setattr(
        bridge, "read_graph", lambda *args: dict(declaration=declared, run_inputs=template)
    )
    # This baseline is deliberately typed. A refusal gets credit only after
    # that same shape has been fully serialized by the real evidence adapter.
    baseline = tmp_path / "baseline"
    baseline.mkdir()
    graph = dict(declaration=declared, run_inputs=contract())
    assert (
        bridge.continuity.typed_take(
            baseline,
            "closed-INIT-inputs",
            lambda: graph,
            attempts=[],
            work="synthetic baseline",
            readers={},
        )
        is graph
    )
    assert (
        type(observation(baseline / "closed-INIT-inputs")["returned"]["declaration"])
        is bridge.phase.Declaration
    )
    forbidden = []

    def denied(*args, **kwargs):
        forbidden.append("downstream")
        pytest.fail("No source/observer/setup after the intended preflight refusal")

    for module, name in (
        (bridge.continuity, "running_source"),
        (bridge.phase, "bind"),
        (bridge.phase, "initialize"),
        (bridge.run, "begin"),
        (bridge, "Calls"),
    ):
        monkeypatch.setattr(module, name, denied)
    reason = (
        "Explicit existing headless run contract required"
        if fault == "run-contract"
        else "Original INIT clock/headless/native-persistence scope required"
        if fault == "profile"
        else "Missing current input authority/provenance/source-work evidence"
    )
    stage = (
        "explicit-INIT-run-contract"
        if fault in {"run-contract", "profile"}
        else "explicit-current-input-authority"
    )
    with pytest.raises(ValueError, match=reason) as caught:
        bridge.acquire_INIT(
            tmp_path / "output", packet=tmp_path / "packet", packet_sha256="synthetic"
        )
    target = tmp_path / "output"
    assert forbidden == [] and not (target / "invocations.jsonl").exists()
    saved = json.loads((target / "attempts.json").read_text())
    expected_stages = [
        "closed-INIT-inputs",
        "typed-current-INIT-declaration",
        "explicit-INIT-run-contract",
    ]
    if stage == "explicit-current-input-authority":
        expected_stages.append(stage)
    assert [row["operation"] for row in saved["attempts"]] == expected_stages
    assert all(row["evidence_complete"] for row in saved["attempts"])
    assert saved["attempts"][-1]["operation_status"] == "failed"
    assert caught.value.typed_evidence_operation == stage
    assert observation(target / stage)["failure"]["message"] == reason
    failed = observation(target / "source-failure")
    assert failed["failure"]["message"] == reason
    assert type(failed["available"]["available"]["declaration"]) is bridge.phase.Declaration
    assert not (target / "result.json").exists()


@pytest.mark.parametrize("termination", ["exhausted", "failed", "paused", "capped", "incomplete"])
def test_acquisition_forwards_actual_api_returns_and_original_stop_without_fixture(
    monkeypatch, tmp_path, termination
):
    gates(monkeypatch)
    config, declared, template = inputs(tmp_path), declaration(3), contract()
    outer, terminal = structural_parents(3)
    declared = replace(
        declared,
        calendar=replace(
            declared.calendar,
            dt_s=0.25,
            sample_stride=1.0,
            provenance="unowned synthetic metadata",
            requested_duration_s=0.75,
        ),
    )
    a = np.array([[1.0, -0.0], [3.0, 4.0]], dtype="<f8")
    material_values = bridge.phase.material.Values(
        *[a for _ in bridge.phase.material.Values._fields]
    )
    material = bridge.phase.material.State(
        "synthetic-material", 3, material_values, "synthetic-material-state"
    )
    network = bridge.phase.network.NetworkState(
        "synthetic-network",
        material,
        MappingProxyType(dict(text="full native text \\frac{a}{b}", data=a)),
        MappingProxyType(dict(sample_epoch=3)),
        "synthetic-network-state",
    )
    entry = replace(
        terminal.active,
        network=network,
        rate_cache=bridge.phase.RateCache(True, np.float64(-0.0)),
        nak_rate=bridge.phase.RateCache(False, None),
        stores=MappingProxyType(dict(material=material_values, network=network)),
        clock=bridge.phase.Clock(np.array([0.0, 0.375, 0.75]), 0, 0.0),
        history=(),
        observations=(),
        status="ready",
        identity="synthetic-entry",
    )
    component = replace(
        outer.composition,
        declaration=declared,
        calendar=declared.calendar,
        inputs=declared.inputs,
        inputs_raw=declared.inputs,
        setup_receipt=MappingProxyType(dict(owner_admission=False, synthetic_only=True)),
    )
    outer = replace(outer, composition=component, inputs=contract())
    receipt_value = MappingProxyType(
        dict(
            phase="INIT",
            previous_phase=None,
            composition_state_identity=entry.identity,
            synthetic_only=True,
            owner_admission=False,
        )
    )
    initial = replace(
        terminal,
        entry=entry,
        active=entry,
        entry_receipt=receipt_value,
        history=(),
        observations=(),
        status="ready",
        identity="synthetic-initial",
    )
    active = replace(
        entry,
        clock=replace(entry.clock, call_index=3, material_dt_sum_s=0.75),
        status="exhausted",
        identity="synthetic-terminal-active",
    )
    journal = bridge.run.CallReceipt(
        2, 0.75, 0.5, 0.75, 0.25, entry.identity, active.identity, True
    )
    terminal = replace(
        terminal,
        entry=entry,
        active=active,
        entry_receipt=receipt_value,
        history=(journal,),
        observations=(bridge.run.Observation(2, 0.75, 0.75, active),),
    )
    if termination in {"failed", "paused", "capped"}:
        terminal = replace(terminal, status=termination)
    elif termination == "incomplete":
        terminal = replace(
            terminal,
            active=replace(terminal.active, clock=replace(terminal.active.clock, call_index=2)),
        )
    complete = plain_record(
        bridge.run.CompletedInitRun,
        binding=outer,
        run=terminal,
        complete_init=plain_record(
            bridge.continuity.lifecycle.CompleteInit,
            binding=component,
            parent=terminal.active,
            scope="unowned software",
            identity="synthetic-complete",
        ),
        identity="synthetic-only",
    )
    observed = []
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: config)
    monkeypatch.setattr(
        bridge, "read_graph", lambda *args: dict(declaration=declared, run_inputs=template)
    )
    monkeypatch.setattr(bridge.continuity, "running_source", lambda *args: None)
    monkeypatch.setattr(bridge.checkpoint, "_rng_identity", lambda: "synthetic-RNG-no-draw")

    def validate(raw):
        assert raw is declared.inputs
        observed.append("validate-current-declaration")
        return declared

    def setup(actual):
        assert actual is declared
        observed.append("initialize")
        return component, entry

    def bind(raw, actual):
        assert actual is component and raw["component_binding_identity"] == component.identity
        observed.append("bind")
        return outer

    def receipt(actual_binding, actual_entry, **kwargs):
        assert actual_binding is outer and actual_entry is entry
        observed.append("receipt")
        return receipt_value

    def begin(actual_binding, actual_entry, actual_receipt):
        assert actual_binding is outer and actual_entry is entry and actual_receipt is receipt_value
        observed.append("begin")
        return initial

    def window(actual_binding, actual_parent, *, stop):
        assert actual_binding is outer and actual_parent is initial and stop == 3
        observed.append("original-window")
        return terminal, ()

    def completion(actual_binding, actual_terminal):
        assert actual_binding is outer and actual_terminal is terminal
        observed.append("complete")
        return complete

    class Observer:
        def __init__(self, stream):
            self.stage = None

        def start(self):
            observed.append("observer-start")

        def stop(self):
            return dict(
                synthetic_only=True,
                profile_intact=True,
                active_invocations=0,
                actual_source_entries=0,
                stub_API_entries=list(observed),
            )

    def synthetic_accounting(accounting, count):
        assert accounting["synthetic_only"] and count == 3
        assert accounting["actual_source_entries"] == 0

    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "acquisition-inputs.json").write_text("{}")

    monkeypatch.setattr(bridge.phase, "initialize", setup)
    monkeypatch.setattr(bridge.phase, "bind", validate)
    monkeypatch.setattr(bridge.run, "bind", bind)
    monkeypatch.setattr(bridge.run, "entry_receipt", receipt)
    monkeypatch.setattr(bridge.run, "begin", begin)
    monkeypatch.setattr(bridge.run, "run_window", window)
    monkeypatch.setattr(bridge.run, "complete_INIT", completion)

    def forbidden_calendar(actual_component):
        pytest.fail("Publication may not invoke the validating calendar property after observation")

    monkeypatch.setattr(bridge.run.composition, "calendar", forbidden_calendar)
    monkeypatch.setattr(bridge, "Calls", Observer)
    monkeypatch.setattr(bridge, "check_acquisition_accounting", synthetic_accounting)
    monkeypatch.setattr(
        bridge.continuity.reader, "bind_calls", lambda *args: dict(synthetic_only=True)
    )
    if termination != "exhausted":
        with pytest.raises(ValueError) as caught:
            bridge.acquire_INIT(
                tmp_path / "output",
                packet=tmp_path / "packet",
                packet_sha256="synthetic",
                declaration=declared,
            )
        assert observed[-1] == "original-window" and "complete" not in observed
        assert (
            observation(tmp_path / "output/original-full-INIT-window")["returned"][0].status
            == terminal.status
        )
        assert caught.value.typed_evidence_operation == "exhausted-original-INIT"
        assert caught.value.typed_evidence_complete is True
        keep(
            tmp_path / "bad-termination-control",
            dict(
                termination=termination,
                primary=str(caught.value),
                stages=observed,
                successful_owner_published=False,
            ),
        )
        return
    returned = bridge.acquire_INIT(
        tmp_path / "output",
        packet=tmp_path / "packet",
        packet_sha256="synthetic",
        declaration=declared,
    )
    assert returned is complete and observed == [
        "observer-start",
        "validate-current-declaration",
        "initialize",
        "bind",
        "receipt",
        "begin",
        "original-window",
        "complete",
    ]
    target = tmp_path / "output"
    saved = observation(target / "actual-complete-INIT")["returned"]
    assert type(saved) is bridge.run.CompletedInitRun
    assert saved.binding.composition is saved.complete_init.binding
    assert saved.run.active is saved.complete_init.parent
    assert saved.run.entry is not saved.run.active
    assert saved.run.entry.stores is saved.run.active.stores
    assert saved.run.active.network.material.values is saved.run.active.stores["material"]
    assert (
        saved.run.active.network.network_cache["data"]
        is saved.run.active.stores["material"].cell_mol_m3
    )
    assert saved.run.history[0].dt_s == 0.25
    assert saved.run.observations[0].state is saved.run.active
    rows = json.loads((target / "attempts.json").read_text())["attempts"]
    assert all(row["evidence_complete"] for row in rows)
    assert json.loads((target / "result.json").read_text())["accounting"]["synthetic_only"]
    keep(
        tmp_path / "API-forwarding-control",
        dict(observed=observed, successful_owner_published=False, typed_observations=len(rows)),
    )


@pytest.mark.parametrize("secondary", [False, True])
def test_stage_keeps_original_cause_failed_prefix_and_profiler_on_accounting_failure(
    monkeypatch, tmp_path, secondary
):
    primary, cause, seen = ValueError("synthetic INIT failure"), TypeError("source cause"), []
    primary.__cause__ = cause
    primary.partial = dict(status="failed", accepted_prefix="retained", trial="failed-trial")

    class Observer:
        def __init__(self, stream):
            pass

        def start(self):
            seen.append("start")

        def stop(self):
            seen.append("stop")
            return dict(profile_intact=True, active_invocations=0, counts={}, phase_counts={})

    def operation(take, values, start):
        values["failed_prefix"] = primary.partial
        start()

        def fail():
            raise primary

        return take("actual-current-declaration-validation", fail)

    original = bridge.snapshot.write_json

    def write(path, value):
        if secondary and path.name == "attempts.json":
            raise OSError("secondary accounting write failed")
        return original(path, value)

    monkeypatch.setattr(bridge, "Calls", Observer)
    monkeypatch.setattr(bridge.snapshot, "write_json", write)
    with pytest.raises(ValueError) as caught:
        bridge._stage(
            tmp_path / "stage",
            {},
            operation,
            lambda *args: pytest.fail("No success after failed INIT"),
        )
    assert (
        caught.value is primary
        and primary.__cause__ is cause
        and primary.partial["status"] == "failed"
    )
    assert seen == ["start", "stop"] and not (tmp_path / "stage/result.json").exists()
    assert (tmp_path / "stage/source-failure/manifest.json").is_file()
    if secondary:
        assert any("secondary accounting write failed" in note for note in primary.__notes__)


@pytest.mark.parametrize("transport", [False, True])
@pytest.mark.parametrize(
    "fault", [None, "extra-INIT", "extra-SIM", "setup", "verification", "transition", "checkpoint"]
)
def test_INIT_and_transport_work_cannot_inflate_the_SIM_comparison(transport, fault):
    value = dict(
        counts={
            bridge.phase.__name__ + ".initialize": 0 if transport else 1,
            bridge.run.__name__ + ".verify": 3,
        },
        phase_counts={bridge.phase.__name__ + ".advance:INIT": 0 if transport else 3},
    )
    if fault == "extra-INIT":
        value["phase_counts"][bridge.phase.__name__ + ".advance:INIT"] += 1
    elif fault == "extra-SIM":
        value["phase_counts"][bridge.phase.__name__ + ".advance:SIM"] = 1
    elif fault == "setup":
        value["counts"][bridge.phase.__name__ + ".initialize"] += 1
    elif fault == "verification":
        value["counts"][bridge.run.__name__ + ".verify"] = 0
    elif fault == "transition":
        value["counts"][bridge.run.__name__ + ".transition"] = 1
    elif fault == "checkpoint":
        value["counts"][bridge.checkpoint.__name__ + ".save_checkpoint"] = 1
    if fault is None:
        bridge.check_acquisition_accounting(value, 3, transport=transport)
    else:
        with pytest.raises(ValueError):
            bridge.check_acquisition_accounting(value, 3, transport=transport)


@pytest.mark.parametrize("value", [None, {}, "receipt", Path("retained-completed-INIT")])
def test_no_serialized_positive_parent_can_enter_SIM(monkeypatch, tmp_path, value):
    gates(monkeypatch)
    config = inputs(tmp_path)
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: config)
    evidence = tmp_path / "acquisition.json"
    evidence.write_text("{}")
    with pytest.raises(ValueError, match="Live typed CompletedInitRun"):
        bridge.continue_INIT(
            tmp_path / "output",
            packet=tmp_path / "packet",
            packet_sha256="synthetic",
            completed=value,
            acquisition_result=evidence,
            acquisition_result_sha256=bridge.snapshot.digest(evidence),
            sim_declaration={},
        )
    assert not (tmp_path / "packet/inputs.json").exists()
    assert not (tmp_path / "output/SIM-continuity").exists()
    assert (tmp_path / "output/failure/manifest.json").is_file()


def test_handoff_passes_the_same_live_objects_after_transport_without_a_SIM_run(
    monkeypatch, tmp_path
):
    gates(monkeypatch)
    config = inputs(tmp_path)
    packet = tmp_path / "packet"
    packet.mkdir()
    (packet / "acquisition-inputs.json").write_text("{}")
    acquisition = tmp_path / "acquisition.json"
    binding, parent = structural_parents()
    completed = plain_record(
        bridge.run.CompletedInitRun,
        binding=binding,
        run=parent,
        complete_init=plain_record(
            bridge.continuity.lifecycle.CompleteInit,
            binding=binding.composition,
            parent=parent.active,
            identity="synthetic-component-completion",
        ),
        identity="synthetic-live-completion",
    )
    graph = bridge.write_graph(tmp_path / "retained-completed-INIT", completed)
    bridge.snapshot.write_json(
        acquisition,
        dict(
            status="actual_original_INIT_completed",
            synthetic_only=True,
            packet=bridge.continuity.ref(packet / "acquisition-inputs.json"),
            snapshot=config["snapshot"],
            complete_identity=completed.identity,
            binding_identity=binding.identity,
            parent_identity=parent.identity,
            retained_graph=graph,
            accounting=dict(synthetic_only=True, actual_source_entries=0),
        ),
    )
    seen = []
    monkeypatch.setattr(bridge, "verify_packet", lambda *args: config)
    monkeypatch.setattr(bridge.continuity, "running_source", lambda *args: None)

    class Observer:
        def __init__(self, stream):
            self.stage = None

        def start(self):
            seen.append("transport-observer-start")

        def stop(self):
            seen.append("transport-observer-stop")
            return dict(
                synthetic_only=True,
                actual_source_entries=0,
                profile_intact=True,
                active_invocations=0,
            )

    def verify(actual):
        assert actual is completed and seen == ["transport-observer-start"]
        seen.append("completed-verification-stub")

    def accounting(value, count, *, transport=False):
        assert value["synthetic_only"] and value["actual_source_entries"] == 0 and count == 1

    def forbidden_calendar(*args):
        pytest.fail("Transport/publication cannot perform verification outside its observer")

    monkeypatch.setattr(bridge, "Calls", Observer)
    monkeypatch.setattr(bridge.run, "verify_completed_INIT", verify)
    monkeypatch.setattr(bridge.run.composition, "calendar", forbidden_calendar)
    monkeypatch.setattr(bridge, "check_acquisition_accounting", accounting)
    monkeypatch.setattr(
        bridge.continuity.reader, "bind_calls", lambda *args: dict(synthetic_only=True)
    )

    marker = ValueError("synthetic stop before actual SIM")

    def continuation(directory, **kwargs):
        assert seen == [
            "transport-observer-start",
            "completed-verification-stub",
            "transport-observer-stop",
        ]
        assert (
            kwargs["init_binding"] is completed.binding and kwargs["init_parent"] is completed.run
        )
        assert kwargs["packet"] is packet
        written = json.loads((packet / "inputs.json").read_text())
        assert written["expected_INIT"] == dict(
            binding_identity=completed.binding.identity, parent_identity=completed.run.identity
        )
        seen.append("continuity-called-with-same-live-objects")
        raise marker

    monkeypatch.setattr(bridge.continuity, "actual_continuity", continuation)
    supplied = SIM_declaration()
    with pytest.raises(ValueError) as caught:
        bridge.continue_INIT(
            tmp_path / "output",
            packet=packet,
            packet_sha256="synthetic",
            completed=completed,
            acquisition_result=acquisition,
            acquisition_result_sha256=bridge.snapshot.digest(acquisition),
            sim_declaration=supplied,
        )
    assert caught.value is marker
    assert seen == [
        "transport-observer-start",
        "completed-verification-stub",
        "transport-observer-stop",
        "continuity-called-with-same-live-objects",
    ]
    assert not (tmp_path / "output/result.json").exists()
    assert not (tmp_path / "output/SIM-continuity").exists()
    assert (
        bridge.read_graph(
            packet / "SIM-declaration",
            json.loads((packet / "inputs.json").read_text())["SIM_declaration"],
        )
        == supplied
    )
    rows = json.loads((tmp_path / "output/transport/attempts.json").read_text())["attempts"]
    assert all(row["evidence_complete"] for row in rows)
    assert [row["operation"] for row in rows] == [
        "pinned-acquisition-file",
        "actual-acquisition-record",
        "exact-INIT-SIM-association",
        "current-frozen-source",
        "actual-completed-INIT-verification",
    ]
    failed = observation(tmp_path / "output/failure")
    assert type(failed["available"]["completed"]) is bridge.run.CompletedInitRun
    assert (
        failed["available"]["completed"].run.active
        is failed["available"]["completed"].complete_init.parent
    )
    keep(tmp_path / "in-process-identity-control", dict(stages=seen, actual_SIM_entered=False))


def test_bridge_uses_only_existing_INIT_equations_and_never_loads_positive_owners():
    import ast

    tree = ast.parse(Path(bridge.__file__).read_bytes())
    calls = {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }
    assert {
        "initialize",
        "begin",
        "run_window",
        "complete_INIT",
        "verify_completed_INIT",
        "actual_continuity",
    } <= calls
    assert (
        not {
            "init_inputs",
            "sim_inputs",
            "prepare_INIT",
            "load_checkpoint",
            "compile_original",
            "actual_comparison",
        }
        & calls
    )
