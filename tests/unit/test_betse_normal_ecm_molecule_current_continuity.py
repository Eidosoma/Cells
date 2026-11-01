"""Source/metadata controls; no actual INIT, SIM, formatter, reference or RNG.

All typed records here are deliberately unowned structural controls. Their
preflight success is not admission; the existing numeric verifier stays blocked.
"""

import copy
import json
import sys
from dataclasses import replace
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import numpy as np
import pytest

from cells.processes import betse_normal_ecm_molecule_formatter as formatter
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
from validation.betse import betse_normal_ecm_molecule_current_continuity as route


@pytest.fixture(autouse=True)
def no_formatter_execution(tmp_path):
    previous, attempted = sys.getprofile(), []

    def guard(frame, event, arg):
        if event == "call" and frame.f_code is formatter._FORMATTER_CODE:
            attempted.append(frame.f_code.co_name)
            raise AssertionError("Actual formatter body forbidden in current-route software")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(guard)
    yield attempted
    sys.setprofile(previous)
    (tmp_path / "formatter-no-call.json").write_text(json.dumps(dict(attempted=attempted)))
    assert attempted == []


def parents(count=1):
    calendar = plain_record(route.run.calendars.NativePhaseCalendar, phase="INIT", step_count=count)
    owner = plain_record(
        route.lifecycle.init.Binding, identity="INIT-component", calendar=calendar, call_limit=count
    )
    binding = route.run.Binding(owner, None, "actual-identity-required-not-supplied-by-this-test")
    active = plain_record(
        route.lifecycle.init.State,
        binding_identity=owner.identity,
        clock=plain_record(route.lifecycle.init.Clock, call_index=count),
        status="exhausted",
    )
    parent = plain_record(
        route.run.RunState,
        binding_identity=binding.identity,
        active=active,
        status="exhausted",
        identity="synthetic-retained-parent",
    )
    return binding, parent


def declaration():
    return dict(
        kind=route.lifecycle.INPUT_KIND,
        expected_init_binding_identity="INIT-component",
        sim_phase=dict(time_profile=dict(phase="SIM"), flags=dict(phase="SIM", _run_sim=True)),
    )


def expected(binding, parent):
    return dict(binding_identity=binding.identity, parent_identity=parent.identity)


def keep(path, payload):
    route.retention.archives.write_archive(
        path,
        dict(
            payload,
            synthetic_only=True,
            scientific_acceptance=False,
            actual_source_entries=0,
            independent_biological_cases=0,
        ),
    )


@pytest.mark.parametrize("count", [0, 1, 3])
def test_typed_structural_parent_and_explicit_inputs_never_attest_admission(count, tmp_path):
    binding, parent = parents(count)
    value = route.preflight(binding, parent, declaration(), expected=expected(binding, parent))
    assert value["cursor"] == count and value["numeric_admission"] is False
    assert value["fixture_fallback"] is False and "actual run.verify" in value["required_next"]
    keep(tmp_path / "structural-control", value)


@pytest.mark.parametrize(
    "fault",
    [
        "absent-binding",
        "absent-parent",
        "dictionary-parent",
        "SIM-parent",
        "boolean-clock",
        "paused",
        "failed",
        "capped",
        "incomplete",
        "cap",
        "foreign-binding",
        "foreign-parent",
        "foreign-active",
        "missing-declaration",
        "foreign-declaration",
        "wrong-phase",
        "wrong-run-flag",
        "kinetic-selection",
        "supplied-event-selection",
    ],
)
def test_missing_foreign_or_incomplete_authority_refuses_before_actual_work(fault, tmp_path):
    binding, parent = parents()
    wanted, raw = expected(binding, parent), declaration()
    if fault == "absent-binding":
        binding = None
    elif fault == "absent-parent":
        parent = None
    elif fault == "dictionary-parent":
        parent = dict(status="exhausted")
    elif fault == "SIM-parent":
        binding = replace(
            binding,
            composition=replace(
                binding.composition, calendar=replace(binding.composition.calendar, phase="SIM")
            ),
        )
    elif fault == "boolean-clock":
        parent = replace(
            parent,
            active=replace(parent.active, clock=replace(parent.active.clock, call_index=True)),
        )
    elif fault in {"paused", "failed", "capped"}:
        parent = replace(parent, status=fault)
    elif fault == "incomplete":
        parent = replace(
            parent, active=replace(parent.active, clock=replace(parent.active.clock, call_index=0))
        )
    elif fault == "cap":
        binding = replace(binding, composition=replace(binding.composition, call_limit=0))
    elif fault == "foreign-binding":
        wanted["binding_identity"] = "foreign"
    elif fault == "foreign-parent":
        wanted["parent_identity"] = "foreign"
    elif fault == "foreign-active":
        parent = replace(parent, active=replace(parent.active, binding_identity="foreign"))
    elif fault == "missing-declaration":
        raw = None
    elif fault == "foreign-declaration":
        raw["expected_init_binding_identity"] = "foreign"
    elif fault == "wrong-phase":
        raw["sim_phase"]["time_profile"]["phase"] = "INIT"
    elif fault == "wrong-run-flag":
        raw["sim_phase"]["flags"]["_run_sim"] = 1
    elif fault == "kinetic-selection":
        raw["kinetic_reload"] = {}
    else:
        raw["event_owner_inputs"] = {}
    with pytest.raises(ValueError) as caught:
        route.preflight(binding, parent, raw, expected=wanted)
    keep(tmp_path / "preflight-refusal", dict(fault=fault, primary=str(caught.value)))


@pytest.mark.parametrize("explicit", [True, False])
def test_existing_preparer_forwards_exact_declaration_and_nested_stage_recorder(
    monkeypatch, tmp_path, explicit
):
    binding, parent = parents()
    raw, completed, component = declaration(), object(), object()
    outer, state = object(), object()
    calls, stages, seen, attempts = SimpleNamespace(stage=None), [], {}, []

    def retain(_directory, _attempts):
        assert _attempts is attempts

        def take(name, operation, **readers):
            stages.append((name, calls.stage))
            return operation()

        return take

    def complete(actual_binding, actual_parent):
        assert actual_binding is binding and actual_parent is parent
        return SimpleNamespace(complete_init=completed)

    def fixture(case, actual_completed):
        assert not explicit and actual_completed is completed
        seen["fixture"] = case
        return raw

    def bind(actual):
        assert actual is raw
        seen["bind"] = actual
        return component

    def contract(case, actual):
        assert actual is component
        return dict(case=case)

    def transition(actual_binding, actual_parent, actual_component, declared, **kwargs):
        assert (
            actual_binding is binding and actual_parent is parent and actual_component is component
        )
        assert declared == dict(case="continuous")
        seen["transition"] = True
        return outer, state

    monkeypatch.setattr(route.preparation, "_retainer", retain)
    monkeypatch.setattr(route.run, "complete_INIT", complete)
    monkeypatch.setattr(route.preparation.fixtures, "sim_inputs", fixture)
    monkeypatch.setattr(route.lifecycle, "bind", bind)
    monkeypatch.setattr(route.preparation.fixtures, "declaration", contract)
    monkeypatch.setattr(route.run, "transition", transition)
    result = route.preparation.prepare_SIM(
        tmp_path / "SIM",
        binding,
        parent,
        attempts,
        case="continuous",
        sim_inputs=raw if explicit else None,
        calls=calls,
    )
    assert result == (outer, state) and seen["bind"] is raw and seen["transition"]
    assert ("fixture" not in seen) is explicit
    assert all(name == stage for name, stage in stages)
    assert [name for name, _ in stages] == [
        "actual-complete-INIT",
        "declared-SIM-inputs" if explicit else "SIM-fixture",
        "SIM-component-binding",
        "SIM-run-inputs",
        "actual-INIT-to-SIM",
    ]
    keep(tmp_path / "forwarding-control", dict(stages=stages, explicit=explicit))


def full_graph():
    shared = dict(text="\\frac{native complete text}{not normalized}", data=[2.0, -0.0])
    return dict(binding="synthetic-binding"), dict(
        material=np.array([[1.0, 2.0], [3.0, 4.0]], np.float64),
        gate=dict(epoch=3, values=[0.2, 0.4]),
        network=dict(molecules=shared, grn=shared),
        events=dict(epoch="original-finalizer", actual_trace=["global", "tissue", "changes"]),
        clock=dict(source=[0.0, 1.5, 3.0], elapsed=[1.0, 2.0, 3.0], cursor=3),
        calendar=dict(phase="SIM", sampling=[0, 1, 2]),
        RNG=dict(numpy="retained", python="retained"),
        status="exhausted",
    )


def test_full_graph_comparison_keeps_shared_alias_and_all_text_without_projection(tmp_path):
    binding, parent = full_graph()
    other_binding, other = copy.deepcopy((binding, parent))
    seal = route.same_graph(binding, parent, other_binding, other)
    assert other["network"]["molecules"] is other["network"]["grn"]
    keep(tmp_path / "complete-graph", dict(seal=seal, complete_graph=parent))


@pytest.mark.parametrize(
    "fault",
    [
        "material",
        "dtype",
        "layout",
        "gate",
        "text",
        "aliases",
        "event-epoch",
        "event-duplicate",
        "event-omitted",
        "source-clock",
        "elapsed-clock",
        "sampling",
        "phase",
        "RNG",
        "failed",
    ],
)
def test_complete_graph_comparison_rejects_each_unprojected_drift(fault, tmp_path):
    binding, parent = full_graph()
    other_binding, other = copy.deepcopy((binding, parent))
    if fault == "material":
        other["material"][0, 0] += 1
    elif fault == "dtype":
        other["material"] = other["material"].astype(np.float32)
    elif fault == "layout":
        other["material"] = np.asfortranarray(other["material"])
    elif fault == "gate":
        other["gate"]["epoch"] += 1
    elif fault == "text":
        other["network"]["molecules"]["text"] = "equal rates do not excuse changed text"
    elif fault == "aliases":
        other["network"]["grn"] = copy.deepcopy(other["network"]["molecules"])
    elif fault == "event-epoch":
        other["events"]["epoch"] = "foreign"
    elif fault == "event-duplicate":
        other["events"]["actual_trace"].append("changes")
    elif fault == "event-omitted":
        other["events"]["actual_trace"].pop()
    elif fault == "source-clock":
        other["clock"]["source"][-1] += 1
    elif fault == "elapsed-clock":
        other["clock"]["elapsed"][-1] += 1
    elif fault == "sampling":
        other["calendar"]["sampling"].pop()
    elif fault == "phase":
        other["calendar"]["phase"] = "INIT"
    elif fault == "RNG":
        other["RNG"]["numpy"] = "foreign"
    else:
        other["status"] = "failed"
    with pytest.raises(ValueError, match="Complete ordinary continuity graph differs") as caught:
        route.same_graph(binding, parent, other_binding, other)
    keep(tmp_path / "full-graph-refusal", dict(fault=fault, primary=str(caught.value)))


@pytest.mark.parametrize("states", [("0", "0"), ("1", "0"), ("0", "1")])
def test_both_gates_precede_packet_read_and_output_creation(monkeypatch, tmp_path, states):
    for name, state in zip(route.RELEASES, states, strict=True):
        monkeypatch.setenv(name, state)
    with pytest.raises(ValueError, match="Both existing releases"):
        route.actual_continuity(tmp_path / "held", packet=tmp_path / "absent", packet_sha256="none")
    assert not (tmp_path / "held").exists()


@pytest.mark.parametrize("mediated", [False, True])
def test_inside_packet_output_refuses_before_any_directory_or_failure_write(
    monkeypatch, tmp_path, mediated
):
    packet = tmp_path / "packet"
    packet.mkdir()
    parent = packet
    if mediated:
        parent = tmp_path / "link"
        parent.symlink_to(packet, target_is_directory=True)
    for name in route.RELEASES:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(
        route,
        "verify_packet",
        lambda *args: dict(repository=str(tmp_path / "repo"), native_root=str(tmp_path / "native")),
    )
    before = list(packet.iterdir())
    with pytest.raises(ValueError, match="Output must be separate"):
        route.actual_continuity(parent / "output", packet=packet, packet_sha256="synthetic")
    assert list(packet.iterdir()) == before and not (parent / "output").exists()


def metadata_inputs(tmp_path):
    binding, parent = parents()
    return dict(
        repository=str(tmp_path / "repo"),
        native_root=str(tmp_path / "native"),
        expected_INIT=expected(binding, parent),
        positive_INIT_evidence=[dict(synthetic=True)],
    )


def typed_observation(path):
    return route.read_typed_observation(
        path, manifest_sha256=route.snapshot.digest(path / "manifest.json")
    )


@pytest.mark.parametrize(
    "operation",
    [
        "actual-current-declaration-validation",
        "actual-INIT-setup",
        "actual-run-binding",
        "actual-entry-receipt",
        "actual-run-begin",
        "original-full-INIT-window",
        "actual-complete-INIT",
        "actual-INIT-verification",
        "pause",
        "resume",
    ],
)
def test_typed_API_observations_forward_exact_original_records_without_reconstruction(
    operation, tmp_path
):
    binding, parent = parents()
    a = np.array([1.0, -0.0], dtype="<f8")
    state = replace(parent.active, stores=MappingProxyType(dict(first=a, alias=a)))
    declared = plain_record(
        route.lifecycle.init.Declaration,
        inputs=MappingProxyType(dict(synthetic_only=True, array=a)),
        calendar=binding.composition.calendar,
        identity="unowned-declaration",
    )
    component = replace(binding.composition, declaration=declared)
    receipt = MappingProxyType(dict(previous_phase=None, synthetic_only=True))
    parent = replace(
        parent, entry=state, active=state, entry_receipt=receipt, history=(), observations=()
    )
    binding = replace(binding, composition=component)
    completed = plain_record(
        route.run.CompletedInitRun,
        binding=binding,
        run=parent,
        complete_init=None,
        identity="unowned-complete",
    )
    values = {
        "actual-current-declaration-validation": declared,
        "actual-INIT-setup": (component, state),
        "actual-run-binding": binding,
        "actual-entry-receipt": receipt,
        "actual-run-begin": parent,
        "original-full-INIT-window": (parent, (dict(parent=parent),)),
        "actual-complete-INIT": completed,
        "actual-INIT-verification": parent,
        "pause": replace(parent, status="paused"),
        "resume": replace(parent, status="ready"),
    }
    value, attempts = values[operation], []
    actual = route.typed_take(
        tmp_path,
        operation,
        lambda: value,
        attempts=attempts,
        work="synthetic typed shapes only",
        readers={"same": lambda: value},
    )
    assert actual is value  # Evidence decoding must never supply the next API.
    saved = typed_observation(tmp_path / operation)
    assert type(saved["returned"]) is type(value)
    assert saved["returned"] is saved["available"]["same"]
    assert route.checkpoint.codec.fingerprint(
        saved["returned"]
    ) == route.checkpoint.codec.fingerprint(value)
    assert attempts[0]["evidence_complete"] and attempts[0]["durability"] == "fsynced"
    assert not (tmp_path / operation / "data.json").exists()


def test_operational_path_observation_is_explicit_metadata_and_returns_original_Path(tmp_path):
    value = tmp_path / "acquisition.json"
    result = route.typed_take(
        tmp_path, "pinned-acquisition-file", lambda: value, attempts=[], work="metadata", readers={}
    )
    assert result is value
    assert typed_observation(tmp_path / "pinned-acquisition-file")["returned"] == dict(
        kind="operational_evidence_path", path=str(value), owner_admission=False
    )


@pytest.mark.parametrize("fault", ["wrong-record", "unknown-reader", "reader-throws"])
def test_successful_source_cannot_advance_with_wrong_schema_or_incomplete_capture(
    fault, monkeypatch, tmp_path
):
    _, parent = parents()
    value = dict(equal_projection="not a RunState") if fault == "wrong-record" else parent
    calls, attempts = [], []

    def never_callback():
        pytest.fail("Unknown callback must never be evaluated for evidence")

    evidence_error = OSError("reader failed independently of source")

    def bad_reader():
        raise evidence_error

    readers = {"good": lambda: parent, "bad": lambda: never_callback}
    if fault == "wrong-record":
        readers = {"good": lambda: parent}
    elif fault == "reader-throws":
        readers["bad"] = bad_reader
    with pytest.raises(route.EvidenceRejected) as caught:
        route.typed_take(
            tmp_path,
            "pause",
            lambda: calls.append("source") or value,
            attempts=attempts,
            work="stub only",
            readers=readers,
        )
    assert calls == ["source"] and caught.value.returned is value
    assert caught.value.partial["returned"] is value
    assert caught.value.__cause__ is caught.value.primary
    assert not attempts[0]["evidence_complete"]
    assert (
        attempts[0]["operation_status"] == "returned"
        and attempts[0]["failure_origin"] == "evidence"
    )
    manifest = json.loads((tmp_path / "pause/manifest.json").read_text())
    assert not manifest["complete"]
    if fault == "unknown-reader":
        assert not manifest["graph"]["capture_complete"]
        assert any(
            row["section"] == "available.good" and row["complete"]
            for row in manifest["incomplete_sections"]
        )
        partial = json.loads((tmp_path / "pause/graph/state.json").read_text())
        assert partial["kind"] == "incomplete_typed_observation" and None in partial["nodes"]
    if fault == "reader-throws":
        assert caught.value.primary is evidence_error
    with pytest.raises(ValueError, match="Incomplete typed observation"):
        typed_observation(tmp_path / "pause")


@pytest.mark.parametrize("source_fails", [False, True])
def test_capture_and_recovery_IO_failures_keep_primary_cause_return_and_partial_bytes(
    source_fails, monkeypatch, tmp_path
):
    _, parent = parents()
    source = ValueError("original source refusal")
    cause = TypeError("original source cause")
    source.__cause__ = cause
    source.partial = dict(accepted=parent, failed_trial=np.array([2.0, -0.0]))
    evidence_error, writes = OSError("first observation I/O failed"), []

    def broken_write(encoder, directory, tree):
        # Simulate an exclusive writer failing after visible partial bytes.
        (directory / "state.json").write_bytes(b'{"partial":')
        writes.append(str(directory))
        raise evidence_error if len(writes) == 1 else OSError("secondary fallback I/O failed")

    monkeypatch.setattr(route.checkpoint.codec.Encoder, "write", broken_write)
    attempts = []

    def action():
        if source_fails:
            raise source
        return parent

    with pytest.raises(ValueError) as caught:
        route.typed_take(
            tmp_path,
            "actual-INIT-verification",
            action,
            attempts=attempts,
            work="synthetic source",
            readers={"parent": lambda: parent},
        )
    if source_fails:
        assert caught.value is source and source.__cause__ is cause
        assert source.partial["accepted"] is parent and source.typed_evidence_complete is False
    else:
        assert type(caught.value) is route.EvidenceRejected
        assert caught.value.returned is parent and caught.value.primary is evidence_error
        assert caught.value.__cause__ is evidence_error
    assert len(writes) > 1 and not attempts[0]["evidence_complete"]
    assert (tmp_path / "actual-INIT-verification/graph/state.json").read_bytes() == b'{"partial":'
    manifest = json.loads((tmp_path / "actual-INIT-verification/manifest.json").read_text())
    assert not manifest["complete"] and len(manifest["capture_errors"]) > 1


def test_source_failure_with_typed_partial_preserves_cross_root_alias_and_cause(tmp_path):
    _, parent = parents()
    source, cause = ValueError("retained source"), TypeError("retained cause")
    source.__cause__ = cause
    source.stage = "actual-INIT-verification"
    source.partial = dict(accepted=parent, trial=np.array([3.0, -0.0]))
    attempts = []

    def action():
        raise source

    with pytest.raises(ValueError) as caught:
        route.typed_take(
            tmp_path,
            source.stage,
            action,
            attempts=attempts,
            work="stub only",
            readers={"parent": lambda: parent},
        )
    assert caught.value is source and source.__cause__ is cause
    saved = typed_observation(tmp_path / source.stage)
    assert (
        saved["exception_chain"][0]["attributes"]["partial"]["accepted"]
        is saved["available"]["parent"]
    )
    assert [item["message"] for item in saved["exception_chain"]] == [
        "retained source",
        "retained cause",
    ]
    assert attempts[0]["evidence_complete"] and attempts[0]["operation_status"] == "failed"


def test_failure_manifest_and_second_recovery_error_cannot_mask_source_exception(
    monkeypatch, tmp_path
):
    _, parent = parents()
    primary, cause = ValueError("original failed source"), TypeError("original cause")
    primary.__cause__ = cause
    primary.partial = dict(accepted=parent, trial=np.array([2.0]))
    real_write = route.snapshot.write_json

    def broken(path, value):
        if path.name == "manifest.json":
            path.write_bytes(b'{"partial manifest":')
            raise OSError("primary diagnostic write error")
        if path.name == "recovery.json":
            raise OSError("second diagnostic recovery error")
        real_write(path, value)

    def action():
        raise primary

    monkeypatch.setattr(route.snapshot, "write_json", broken)
    attempts = []
    with pytest.raises(ValueError) as caught:
        route.typed_take(
            tmp_path,
            "actual-INIT-verification",
            action,
            attempts=attempts,
            work="stub",
            readers={"parent": lambda: parent},
        )
    assert caught.value is primary and primary.__cause__ is cause
    assert primary.partial["accepted"] is parent
    row = attempts[0]
    assert row["manifest_visible"] and not row["evidence_complete"]
    assert row["durability"] == "uncertain"
    assert [e["stage"] for e in row["capture_errors"]] == [
        "evidence-publication",
        "recovery-publication",
    ]
    assert (tmp_path / "actual-INIT-verification/graph/state.json").stat().st_size > 0
    assert (tmp_path / "actual-INIT-verification/graph/arrays.npz").stat().st_size > 0


@pytest.mark.parametrize("source_fails", [False, True])
def test_manifest_status_IO_failure_is_secondary_to_the_retained_source_or_return(
    source_fails, monkeypatch, tmp_path
):
    _, parent = parents()
    primary, cause = ValueError("original source"), TypeError("original cause")
    primary.__cause__ = cause
    visibility_error = OSError("manifest visibility cannot be determined")
    original = Path.exists

    def exists(path):
        if path == tmp_path / "pause/manifest.json":
            raise visibility_error
        return original(path)

    def action():
        if source_fails:
            raise primary
        return parent

    monkeypatch.setattr(Path, "exists", exists)
    attempts = []
    with pytest.raises(ValueError) as caught:
        route.typed_take(tmp_path, "pause", action, attempts=attempts, work="stub", readers={})
    if source_fails:
        assert caught.value is primary and primary.__cause__ is cause
        assert primary.typed_evidence_complete is False
    else:
        assert caught.value.returned is parent and caught.value.__cause__ is visibility_error
    assert not attempts[0]["evidence_complete"] and attempts[0]["manifest_visible"] is None
    assert attempts[0]["capture_errors"][-1]["stage"] == "manifest-visibility"


def test_archive_collision_refuses_before_source_entry_and_preserves_parent_bytes(tmp_path):
    target = tmp_path / "pause"
    target.mkdir()
    (target / "manifest.json").write_bytes(b"frozen parent bytes")
    attempts, calls = [], []
    with pytest.raises(FileExistsError):
        route.typed_take(
            tmp_path,
            "pause",
            lambda: calls.append("forbidden"),
            attempts=attempts,
            work="metadata",
            readers={},
        )
    assert not calls and (target / "manifest.json").read_bytes() == b"frozen parent bytes"
    assert attempts[0]["operation_status"] == "not_entered"


@pytest.mark.parametrize("fails_at", ["manifest", "directory-fsync"])
def test_post_publication_IO_failure_reports_visible_marker_and_uncertain_durability(
    fails_at, monkeypatch, tmp_path
):
    _, parent = parents()
    real_write, real_sync = route.snapshot.write_json, route.checkpoint.codec._sync_directory
    error = OSError("publication durability unknown")

    def write(path, payload):
        real_write(path, payload)
        if fails_at == "manifest" and path.name == "manifest.json":
            raise error

    def sync(path):
        if fails_at == "directory-fsync" and path.name == "pause":
            raise error
        real_sync(path)

    monkeypatch.setattr(route.snapshot, "write_json", write)
    monkeypatch.setattr(route.checkpoint.codec, "_sync_directory", sync)
    attempts = []
    with pytest.raises(route.EvidenceRejected) as caught:
        route.typed_take(
            tmp_path, "pause", lambda: parent, attempts=attempts, work="stub", readers={}
        )
    assert caught.value.primary is error and caught.value.returned is parent
    assert attempts[0]["manifest_visible"] and attempts[0]["durability"] == "uncertain"
    assert not attempts[0]["evidence_complete"]
    recovery = json.loads((tmp_path / "pause/recovery.json").read_text())
    assert not recovery["evidence_complete"]


@pytest.mark.parametrize("fault", ["wrong-pin", "corrupt", "truncated", "symlink"])
def test_typed_observation_reader_refuses_changed_or_foreign_payload(fault, tmp_path):
    _, parent = parents()
    route.typed_take(tmp_path, "pause", lambda: parent, attempts=[], work="stub", readers={})
    target = tmp_path / "pause"
    pin = route.snapshot.digest(target / "manifest.json")
    if fault == "wrong-pin":
        pin = "0" * 64
    elif fault in {"corrupt", "truncated"}:
        path = target / "graph/arrays.npz"
        data = path.read_bytes()
        path.write_bytes(b"different" if fault == "corrupt" else data[:-1])
    else:
        path = target / "graph/state.json"
        foreign = tmp_path / "foreign.json"
        foreign.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(foreign)
    with pytest.raises((ValueError, OSError)):
        route.read_typed_observation(target, manifest_sha256=pin)


def test_absent_actual_INIT_is_preserved_without_fixture_or_verification(monkeypatch, tmp_path):
    for name in route.RELEASES:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(route, "verify_packet", lambda *args: metadata_inputs(tmp_path))
    target = tmp_path / "output"
    with pytest.raises(ValueError, match="Missing actual retained INIT binding") as caught:
        route.actual_continuity(target, packet=tmp_path / "packet", packet_sha256="synthetic")
    saved = json.loads((target / "attempts.json").read_text())
    assert [row["operation"] for row in saved["attempts"]] == ["required-genuine-INIT"]
    assert saved["attempts"][0]["operation_status"] == "failed"
    assert (target / "continuity-failure/manifest.json").is_file()
    assert not (target / "SIM").exists() and not (target / "result.json").exists()
    assert not (target / "invocations.jsonl").exists()
    assert caught.value.typed_evidence_operation == "required-genuine-INIT"
    assert caught.value.typed_evidence_complete is True


@pytest.mark.parametrize("secondary", [False, True])
def test_verification_failure_keeps_primary_cause_partial_and_accounting(
    monkeypatch, tmp_path, secondary
):
    for name in route.RELEASES:
        monkeypatch.setenv(name, "1")
    monkeypatch.setattr(route, "verify_packet", lambda *args: metadata_inputs(tmp_path))
    monkeypatch.setattr(route, "read_declaration", lambda *args: declaration())
    monkeypatch.setattr(route, "running_source", lambda *args: None)
    binding, parent = parents()
    primary, cause = ValueError("synthetic verifier refusal"), TypeError("retained cause")
    primary.__cause__ = cause
    primary.partial = dict(accepted="synthetic-unowned-parent", trial="retained-failed-trial")
    seen = []

    class Observer:
        def __init__(self, stream):
            self.stage = None

        def start(self):
            seen.append("start")

        def stop(self):
            seen.append("stop")
            return dict(
                synthetic=True,
                counts={},
                phase_counts={},
                profile_intact=True,
                active_invocations=0,
                durable_major_entries=0,
            )

    def refuse(*args):
        seen.append("verify")
        raise primary

    original = route.snapshot.write_json

    def write(path, payload):
        if secondary and path.name == "attempts.json":
            raise OSError("synthetic accounting fsync failure")
        return original(path, payload)

    monkeypatch.setattr(route, "Calls", Observer)
    monkeypatch.setattr(route.run, "verify", refuse)
    monkeypatch.setattr(route.snapshot, "write_json", write)
    target = tmp_path / "output"
    with pytest.raises(ValueError) as caught:
        route.actual_continuity(
            target,
            packet=tmp_path / "packet",
            packet_sha256="synthetic",
            init_binding=binding,
            init_parent=parent,
        )
    assert caught.value is primary and caught.value.__cause__ is cause
    assert caught.value.partial["trial"] == "retained-failed-trial"
    assert seen == ["start", "verify", "stop"]
    assert not (target / "SIM").exists() and not (target / "result.json").exists()
    assert (target / "continuity-failure/manifest.json").is_file()
    if secondary:
        assert any("accounting fsync failure" in note for note in primary.__notes__)
    else:
        saved = json.loads((target / "attempts.json").read_text())
        assert saved["attempts"][-1]["operation"] == "actual-INIT-verification"


def accounting():
    return dict(
        profile_intact=True,
        active_invocations=0,
        counts={
            route.checkpoint.__name__ + ".save_checkpoint": 1,
            route.checkpoint.__name__ + ".load_checkpoint": 1,
            route.checkpoint.__name__ + "._verify": 2,
            route.run.__name__ + ".transition": 1,
            route.run.__name__ + ".verify": 9,
        },
        phase_counts={route.lifecycle.init.__name__ + ".advance:SIM": 6},
    )


@pytest.mark.parametrize(
    "fault",
    [
        None,
        "profile",
        "active",
        "extra-INIT-step",
        "INIT-setup",
        "omitted-SIM-step",
        "extra-SIM-step",
        "save",
        "load",
        "nested-verification",
        "transition",
        "verification",
    ],
)
def test_nested_work_and_duplicate_or_omitted_source_requests_cannot_be_cases(fault):
    value = accounting()
    if fault == "profile":
        value["profile_intact"] = False
    elif fault == "active":
        value["active_invocations"] = 1
    elif fault == "extra-INIT-step":
        value["phase_counts"][route.lifecycle.init.__name__ + ".advance:INIT"] = 1
    elif fault == "INIT-setup":
        value["counts"][route.lifecycle.init.__name__ + ".initialize"] = 1
    elif fault in {"omitted-SIM-step", "extra-SIM-step"}:
        value["phase_counts"][route.lifecycle.init.__name__ + ".advance:SIM"] += (
            1 if fault == "extra-SIM-step" else -1
        )
    elif fault in {"save", "load", "nested-verification"}:
        name = {
            "save": "save_checkpoint",
            "load": "load_checkpoint",
            "nested-verification": "_verify",
        }[fault]
        value["counts"][route.checkpoint.__name__ + "." + name] -= 1
    elif fault in {"transition", "verification"}:
        value["counts"][
            route.run.__name__ + (".verify" if fault == "verification" else ".transition")
        ] = 0
    if fault is None:
        route.check_accounting(value)
    else:
        with pytest.raises(ValueError):
            route.check_accounting(value)


def test_declared_SIM_graph_uses_closed_codec_and_preserves_order_axes_bits_aliases(tmp_path):
    value = declaration()
    array = np.array([1.0, -0.0], np.float64)
    value["ordered_targets"] = [2, 0, 2]
    value["owner-A"] = value["owner-B"] = dict(values=array)
    encoder = route.checkpoint.codec.Encoder()
    tree = encoder.capture(value)
    target = tmp_path / "SIM-declaration"
    target.mkdir()
    encoder.write(target, tree)
    row = dict(
        fingerprint=encoder.seal(tree),
        state=route.ref(target / "state.json"),
        arrays=route.ref(target / "arrays.npz"),
    )
    result = route.read_declaration(tmp_path, dict(SIM_declaration=row))
    assert list(result) == list(value) and result["ordered_targets"] == [2, 0, 2]
    assert result["owner-A"] is result["owner-B"]
    assert result["owner-A"]["values"].dtype == np.dtype(np.float64)
    assert result["owner-A"]["values"][1].tobytes() == array[1].tobytes()
    keep(tmp_path / "declaration-control", dict(input=value, restored=result))


@pytest.mark.parametrize("fault", ["missing", "changed-payload", "foreign-file", "wrong-seal"])
def test_declaration_does_not_hydrate_missing_or_foreign_inputs(fault, tmp_path):
    target = tmp_path / "SIM-declaration"
    target.mkdir()
    encoder = route.checkpoint.codec.Encoder()
    tree = encoder.capture(declaration())
    encoder.write(target, tree)
    row = dict(
        fingerprint=encoder.seal(tree),
        state=route.ref(target / "state.json"),
        arrays=route.ref(target / "arrays.npz"),
    )
    if fault == "missing":
        row = None
    elif fault == "changed-payload":
        (target / "state.json").write_text("{}")
    elif fault == "foreign-file":
        foreign = tmp_path / "foreign.json"
        foreign.write_bytes((target / "state.json").read_bytes())
        row["state"] = route.ref(foreign)
    else:
        row["fingerprint"] = "foreign"
    with pytest.raises(ValueError):
        route.read_declaration(tmp_path, dict(SIM_declaration=row))


def test_running_checkout_is_refused_when_a_frozen_source_regime_is_required(tmp_path):
    with pytest.raises(ValueError, match="Run from the prepared source snapshot"):
        route.running_source(tmp_path / "packet", {})


def test_new_route_contains_no_INIT_constructor_or_kinetic_reference_replay():
    import ast

    tree = ast.parse(Path(route.__file__).read_bytes())
    forbidden = {
        "prepare_INIT",
        "init_inputs",
        "sim_inputs",
        "actual_comparison",
        "compile_original",
    }
    actual = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "actual_continuity"
    )
    assert (
        not {
            node.func.attr
            for node in ast.walk(actual)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        }
        & forbidden
    )
    assert route.SPEC["branch_calls"] == dict(uninterrupted=3, prefix=1, continued=2)
