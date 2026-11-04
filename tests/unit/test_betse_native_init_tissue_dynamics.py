"""Written source/authority controls; actual native helper and RNG entry blocked."""

import ast
import os
import sys
from contextlib import contextmanager
from types import CodeType, FunctionType
from types import SimpleNamespace as NS

import pytest

from cells.processes import betse_native_init_tissue_dynamics as stage
from tests.unit import test_betse_native_init_retained_world as retained_guards
from validation.betse import betse_native_init_tissue_dynamics_software as software


@pytest.fixture(autouse=True)
def blocked(request, tmp_path, monkeypatch):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Source-only preparation; native-blocked software release required")
    namespace = dict(vars(retained_guards), software=software, _RAW_GUARDS=[])
    fn = FunctionType(retained_guards.blocked.__wrapped__.__code__, namespace)
    with contextmanager(fn)(request, tmp_path, monkeypatch):
        yield


def test_original_tissue_method_bodies_and_module_compile_context_are_exact_without_calls():
    plan, methods, codes = stage.source_plan(), stage._source_nodes(), stage._codes()
    assert plan["methods"]["init_profiles"] == (363, 443)
    assert plan["methods"]["init_events"] == (454, 465)
    assert tuple(methods) == tuple(codes) == stage.METHODS
    assert all(
        type(value) is CodeType and value.co_filename == str(stage.NATIVE / stage.HANDLER)
        for value in codes.values()
    )
    assert (
        stage.source.InitTissueDynamics.init_profiles
        is stage.profiles.source.SeedProfiles.init_profiles
    )
    assert plan["native_reference_RNG_operator_or_scientific_release"] is False


@pytest.mark.parametrize("name", stage.METHODS)
def test_all_original_handler_branches_are_catalogued_as_unexecuted_CodeTypes(name):
    value = stage._codes()[name]
    assert value.co_name == name and value.co_qualname == "TissueHandler." + name
    assert value.co_filename == str(stage.NATIVE / stage.HANDLER)


@pytest.mark.parametrize("name", stage.MODULATORS)
def test_original_modulators_are_whole_module_compiled_without_evaluation(name):
    value = stage._modulator_codes()[name]
    assert type(value) is CodeType and value.co_name == name
    assert value.co_filename == str(stage.NATIVE / stage.MODULATE)


def test_original_gj_shuffle_copy_is_retained_without_repairing_target_selection():
    node = stage._source_nodes()["_finalize_events_global"]
    source = ast.unparse(node)
    assert source.index("mem_i_copy = np.copy(cells.mem_i[:])") < source.index(
        "shuffle(mem_i_copy)"
    )
    assert source.index("shuffle(mem_i_copy)") < source.index("cells.mem_i[x]")
    assert "mem_i_copy[x]" not in source
    assert "numo = 100" in source and "numo = 1" in source


def test_original_targeted_event_modulator_names_and_quirks_are_not_normalized():
    nodes = stage._source_nodes()
    source = ast.unparse(nodes["_finalize_events_tissue"])
    assert "getattr(mod, self.function_Namem)" in source
    assert "getattr(mod, self.function_P)" in source
    assert "self.targets_ecmJ" in source
    assert "lambda t: 1" in source


def test_completion_contract_none_refuses_before_foreign_phase_or_claim_inspection(monkeypatch):
    monkeypatch.setattr(stage.importlib, "import_module", lambda *a: pytest.fail("No import"))
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._ready()
    assert caught.value.stage == "completion_held"
    assert stage.COMPLETION_CONTRACT is None


def test_raw_session_is_not_supplied_or_restorable_phase_authority():
    with pytest.raises(TypeError):
        stage.TissueSession()
    with pytest.raises(TypeError):
        stage.TissueSession.__reduce_ex__(object.__new__(stage.TissueSession), 4)


def test_raw_return_root_precedes_fallible_history_capture():
    original = object()

    class RejectAppend:
        def append(self, value):
            raise OSError("history refused")

    context = NS(returns=RejectAppend(), capture_error=None, capture_errors=())
    stage._raw_return(context, "metadata_helper", original)
    assert context.last_raw_return[1] is original
    assert type(context.capture_error) is OSError
    assert context.capture_errors[0][2][1] is original


@pytest.mark.parametrize(
    "name",
    (
        "validate_active",
        "validate_closed",
        "source_members",
        "state_roots",
        "wrapper_guard",
        "dispatch",
        "observe",
        "finish",
        "validate_rng_call",
    ),
)
def test_foreign_session_cannot_enter_the_real_participation_api(name):
    arguments = {
        "validate_active": dict(completion_claim=object()),
        "validate_closed": dict(completion_claim=object()),
        "source_members": {},
        "state_roots": {},
        "wrapper_guard": dict(completion_claim=object(), original=None, frame=None),
        "dispatch": dict(
            completion_claim=object(),
            original=None,
            label="TissueHandler.init_profiles",
            delegate=None,
            actual=None,
            args=(),
            kwargs={},
            frame=None,
        ),
        "observe": dict(completion_claim=object(), frame=None, event="call", arg=None),
        "finish": dict(completion_claim=object()),
        "validate_rng_call": dict(
            completion_claim=object(),
            library="numpy",
            operation="shuffle",
            delegate=None,
            args=(),
            kwargs={},
            source_frame=None,
        ),
    }
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        getattr(stage, name)(object(), **arguments[name])
    assert caught.value.stage == "session"


def test_completion_binding_gate_precedes_foreign_claim_inspection(monkeypatch):
    class Foreign:
        def __getattribute__(self, name):
            pytest.fail("Unavailable producer must refuse before looking at a foreign claim")

    monkeypatch.setattr(stage.importlib, "import_module", lambda *a: pytest.fail("No import"))
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage.bind_completion(Foreign(), original_owner=Foreign())
    assert caught.value.stage == "completion_held"


def test_rng_witness_is_data_and_cannot_decode_live_source_authority():
    witness = stage.RngWitness(object(), object(), "shuffle", object())
    assert witness not in stage._WITNESSES
    with pytest.raises(TypeError):
        witness.__reduce_ex__(4)


def test_equal_values_are_not_original_reference_authority():
    first, second = [1, 2], [1, 2]
    assert first == second and first is not second
    stage._same_refs((first,), (first,))
    with pytest.raises(ValueError):
        stage._same_refs((first,), (second,))


def test_metadata_attempt_is_retained_before_entry_guard_and_zero_body(monkeypatch):
    # A private observer metadata probe is deliberately NOT an issued session,
    # phase or owner. Its actual frame is never labelled native or executed as
    # an original tissue body.
    frame = sys._getframe()
    context = NS(
        source_codes={frame.f_code},
        work=[],
        last_attempt=None,
        mask_wrapper_code=None,
        mask_factory=NS(__code__=None),
    )
    primary = RuntimeError("entry refused")

    def refuse(actual):
        assert actual is context
        raise primary

    monkeypatch.setattr(stage, "_guard", refuse)
    with pytest.raises(RuntimeError) as caught:
        stage._observe(context, frame, "call", None)
    assert caught.value is primary
    assert len(context.work) == 1
    row = context.work[0]
    assert row is context.last_attempt and row["frame"] is frame
    assert row["body_started"] is row["returned"] is False


def test_observation_append_failure_keeps_raw_attempt_before_guard(monkeypatch):
    frame = sys._getframe()
    failure = OSError("metadata append refused")

    class RejectAppend:
        def __len__(self):
            return 0

        def append(self, value):
            raise failure

    context = NS(
        source_codes={frame.f_code},
        work=RejectAppend(),
        last_attempt=None,
        capture_error=None,
        capture_errors=(),
        mask_wrapper_code=None,
        mask_factory=NS(__code__=None),
    )
    sentinel = RuntimeError("capture boundary stopped")

    def stop(actual):
        assert actual.capture_error is failure
        raise sentinel

    monkeypatch.setattr(stage, "_guard", stop)
    with pytest.raises(RuntimeError) as caught:
        stage._observe(context, frame, "call", None)
    assert caught.value is sentinel
    assert context.last_attempt["frame"] is frame
    assert context.last_capture[0] == "attempt_record"
    assert context.last_capture[2] is context.last_attempt
    assert context.last_attempt["body_started"] is False


def test_private_rng_bridge_has_no_direct_rng_delegate_execution():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    bridge = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_rng_bridge"
    )
    calls = [n.func for n in ast.walk(bridge) if isinstance(n, ast.Call)]
    assert any(isinstance(n, ast.Attribute) and n.attr == "rng_call" for n in calls)
    assert not any(isinstance(n, ast.Name) and n.id == "delegate" for n in calls)


def test_source_dispatch_keeps_original_classes_and_uses_private_CodeType_globals_only():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    namespace = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_private_namespaces"
    )
    calls = [n.func for n in ast.walk(namespace) if isinstance(n, ast.Call)]
    assert any(isinstance(n, ast.Name) and n.id == "FunctionType" for n in calls)
    assert not any(isinstance(n, ast.Name) and n.id in ("setattr", "exec", "eval") for n in calls)


def test_retained_INIT_producer_has_no_edits_hidden_in_this_participation_scope():
    assert software.OWNED == (software.SOURCE, software.LITERAL, software.TEST, software.FILE)
    assert all("retained_world" not in name for name in software.OWNED)
    assert stage.COMPLETION_SOURCE_SHA256 is stage.COMPLETION_REVIEW_SHA256 is None


def test_capture_stop_preserves_secondary_identity_and_does_not_invent_a_primary():
    capture = OSError("metadata capture refused")
    context = NS(entry_error=None, capture_error=capture, capture_stop=None, primary=None)
    for _ in range(2):
        with pytest.raises(stage.CaptureStop) as caught:
            stage._guard(context)
        assert caught.value is context.capture_stop
        assert caught.value.__cause__ is capture
        assert caught.value.partial is context
        assert context.primary is None


def test_entry_rejection_keeps_precedence_over_secondary_capture():
    primary = stage.TissueDynamicsRejected("entry refused", stage="metadata")
    primary.__cause__ = ValueError("actual earlier cause")
    context = NS(entry_error=primary, capture_error=OSError("capture refused"))
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._guard(context)
    assert caught.value is primary and caught.value.__cause__ is primary.__cause__


def test_runner_requires_declared_overlay_before_inspecting_loaded_modules(monkeypatch):
    monkeypatch.setattr(software.snapshot, "digest", lambda *a: pytest.fail("No input hash yet"))
    with pytest.raises(ValueError, match="declared before freeze"):
        software._external_producers({"external_runtime_pins": {}}, loaded=True)


@pytest.mark.parametrize(
    "name",
    (
        "cells.processes.betse_native_init_tissue_dynamics_source",
        "cells.processes.betse_native_seed_init_profiles_source",
        "cells.processes.betse_native_init_dynamics_completion_source",
        "cells.processes.betse_native_init_dynamics_prelude_source",
    ),
)
def test_fresh_and_read_only_literal_bodies_are_still_software_forbidden(name):
    frame = NS(f_globals={"__name__": name})
    assert software.is_forbidden_frame(frame) is True


def test_unrelated_helper_before_body_is_sticky_refused_without_delegate(monkeypatch):
    frame = sys._getframe()
    sentinel = object()
    context = NS(
        mask_wrapper_code=None,
        mask_factory=NS(__code__=None),
        source_codes={frame.f_code},
        work=[],
        last_attempt=None,
        frames={},
        source_frames=set(),
        source_functions={},
        stack=[dict(role="metadata", name="original", body=None)],
        methods={("metadata", "original"): NS(__code__=sentinel)},
        entry_error=None,
        invalid=False,
        stage="metadata",
    )
    monkeypatch.setattr(stage, "_guard", lambda value: None)
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._observe(context, frame, "call", None)
    assert caught.value is context.entry_error
    assert context.invalid and not context.work[0]["body_started"]
    assert not context.frames and not context.source_frames


def test_added_dynamic_modulator_export_is_refused_before_any_callable():
    calls = []

    def existing():
        calls.append("existing")

    def added():
        calls.append("foreign")

    facade = NS(periodic=existing)
    original = NS(periodic=existing)
    keys = tuple(vars(facade))
    stage._facade_atoms(facade, original, keys, lambda value: (value,))
    facade.configured_extra = added
    # Scalar values and every retained original export remain unchanged.
    assert facade.periodic is original.periodic
    with pytest.raises(ValueError, match="roster"):
        stage._facade_atoms(
            facade, original, keys, lambda value: pytest.fail("No sampler after roster drift")
        )
    assert calls == []


@pytest.mark.parametrize("action", ("remove", "replace", "wrong_context", "wrong_picker"))
def test_new_mask_registry_edge_drift_is_not_value_authority(monkeypatch, action):
    # Isolated registry algorithm, not an issued TissueSession/phase chain.
    class MetadataMask:
        pass

    mask, picker = MetadataMask(), object()
    context = NS(
        finished=False,
        mask_objects=[],
        mask_runtime=MetadataMask,
        profiles=(("metadata", NS(picker=picker)),),
        invalid=False,
        entry_error=None,
        stage="metadata",
    )
    token = (context, picker, object())
    context.mask_objects.append((mask, token))
    registry = {mask: token}
    monkeypatch.setattr(stage, "_MASKS", registry)
    stage._check_masks(context)
    if action == "remove":
        registry.pop(mask)
    elif action == "replace":
        registry[mask] = tuple([*token])
        assert registry[mask] == token and registry[mask] is not token
    elif action == "wrong_context":
        registry[mask] = (object(), picker, token[2])
    else:
        registry[mask] = (context, object(), token[2])
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._check_masks(context)
    assert caught.value is context.entry_error and context.invalid


def test_mask_factory_refuses_without_real_picker_body_before_allocation(monkeypatch):
    context = NS(
        stack=[],
        mask_pending=None,
        mask_factory_frames={},
        invalid=False,
        entry_error=None,
        stage="metadata",
    )
    monkeypatch.setattr(stage, "_guard", lambda value: None)
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._make_mask(context, (), {}, sys._getframe())
    assert caught.value is context.entry_error
    assert not hasattr(context, "last_raw_mask")


@pytest.mark.parametrize("filename", (None, 1, "undeclared.png"))
def test_image_file_bytes_alone_do_not_supply_an_issued_file_lease(filename):
    context = NS(file_inputs=(), invalid=False, entry_error=None, stage="metadata")
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._file_for_source(context, filename)
    assert caught.value is context.entry_error


def test_constructor_retains_raw_mask_before_registry_and_partial_capture():
    tree = ast.parse(stage.Path(stage.__file__).read_bytes())
    method = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "_make_mask")
    text = ast.unparse(method)
    assert text.index("context.last_raw_mask = actual") < text.index("_MASKS[actual] = token")
    assert text.index("_MASKS[actual] = token") < text.index("context.mask_pending =")
    assert text.index("context.mask_pending =") < text.index("context.mask_wrappers['__init__']")


@pytest.mark.parametrize("attempt", ("init_profiles", "init_events"))
def test_top_slot_is_consumed_before_same_or_next_callback_attempt(attempt):
    # Entry-order metadata only: no claim, handler or phase is fabricated.
    parent, first = object(), object()
    context = NS(
        stack=[],
        pending_top=None,
        completion=NS(body_frame=parent),
        top_entered=[],
        invalid=False,
        entry_error=None,
        stage="metadata",
    )
    stage._claim_top_slot(context, "init_profiles", parent, first)
    assert context.pending_top is first and context.top_entered == ["init_profiles"]
    with pytest.raises(stage.TissueDynamicsRejected) as caught:
        stage._claim_top_slot(context, attempt, parent, object())
    assert caught.value is context.entry_error and context.invalid
    assert context.pending_top is first and context.top_entered == ["init_profiles"]
    with pytest.raises(stage.TissueDynamicsRejected) as sticky:
        stage._guard(context)
    assert sticky.value is caught.value


def test_top_slot_metadata_order_does_not_issue_live_authority():
    parent, first, second = object(), object(), object()
    context = NS(
        stack=[],
        pending_top=None,
        completion=NS(body_frame=parent),
        top_entered=[],
        invalid=False,
        entry_error=None,
        stage="metadata",
    )
    stage._claim_top_slot(context, "init_profiles", parent, first)
    # Model a finished slot; this is not a real issued handle or retirement.
    context.pending_top = None
    stage._claim_top_slot(context, "init_events", parent, second)
    assert context.top_entered == ["init_profiles", "init_events"]
    assert context.pending_top is second
    assert context not in stage._SESSIONS.values()


def test_an_admitted_body_allows_its_actual_metadata_descendant_frame(monkeypatch):
    body = sys._getframe()
    context = NS(
        mask_wrapper_code=None,
        mask_factory=NS(__code__=None),
        source_codes=set(),
        work=[],
        frames={},
        source_frames=set(),
        source_functions={},
        entry_error=None,
        invalid=False,
        stage="metadata",
        stack=[dict(role="metadata", name="original", body=body)],
        methods={("metadata", "original"): NS(__code__=object())},
    )
    monkeypatch.setattr(stage, "_guard", lambda value: None)

    def descendant():
        frame = sys._getframe()
        context.source_codes.add(frame.f_code)
        context.source_functions[frame.f_code] = descendant
        stage._observe(context, frame, "call", None)
        return frame

    frame = descendant()
    assert context.frames[id(frame)]["body_started"] is True
    assert frame in context.source_frames
    assert context.entry_error is None and not context.invalid
    assert all(value is not context for value in stage._SESSIONS.values())


def test_forged_file_record_does_not_replace_actual_public_file_issuance():
    value = stage.profiles.files.FileInput(
        "/mnt/workspaces/Cells/unissued.png", "0" * 64, "metadata", (), "unissued"
    )
    context = NS(file_inputs=(value,), invalid=False, entry_error=None, stage="metadata")
    with pytest.raises(stage.profiles.files.YamlPrefixRejected) as caught:
        stage._file_for_source(context, value.filename)
    assert caught.value.stage == "file_authority"
    assert value not in stage.profiles.files._FILES


def test_source_global_stdlib_rng_is_distinct_from_framework_private_naming_rng():
    module = software.sys.modules["random"]
    frame = NS(
        f_globals={"__name__": "random"},
        f_code=NS(co_name="shuffle", co_filename=module.__file__),
        f_locals={"self": module._inst},
    )
    assert software.is_forbidden_frame(frame) is True
    frame.f_locals["self"] = object()  # No actual RNG is constructed or drawn.
    assert software.is_forbidden_frame(frame) is False


def test_reused_worker_has_its_real_global_namespace_and_owned_overrides():
    namespace = software._child_scope()
    for name in ("reuse", "_scope", "_integration_policy", "snapshot", "importlib", "json"):
        assert name in namespace
    assert namespace["reuse"] is software.inherited.reuse
    assert namespace["_scope"] is software._scope
    assert namespace["SOURCE"] == software.SOURCE
    assert namespace["TEST"] == software.TEST
    assert namespace["is_forbidden_frame"] is software.is_forbidden_frame
