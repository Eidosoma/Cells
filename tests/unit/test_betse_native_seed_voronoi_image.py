"""Written UNRUN image-prefix metadata controls; no synthetic owner authority."""

import ast
import os
import sys
from contextlib import contextmanager
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_voronoi_image as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_voronoi_image_software as software

SOFTWARE_RELEASE = "BETSE_NATIVE_SEED_VORONOI_IMAGE_SOFTWARE_RELEASED"
_BLOCKADE_FAILURES = ()
_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; separate metadata software release required")
    # Accepted original cleanup/one-receipt fixture with this stricter source
    # roster. This is a private metadata namespace, not a fabricated parent.
    adapter = NS(**dict(vars(software), reuse=software.reuse.reuse))
    namespace = dict(vars(controls), software=adapter, stage=stage, _BLOCKADE_FAILURES=())
    original = controls._blockade.__wrapped__
    fn = FunctionType(original.__code__, namespace, original.__name__)
    try:
        with contextmanager(fn)(request, tmp_path):
            yield
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARD_SCOPES.append(namespace)


def test_preparation_literal_boundary_and_every_new_execution_pin_stay_closed():
    plan = stage.source_plan()
    assert plan["source_pin"] is plan["image_literal_pin"] is plan["image_helpers_pin"] is None
    assert plan["caller_stores_permitted"] == ()
    assert plan["actual_global_rng_may_advance"] is False
    assert plan["no_prelude_or_supplied_image_arguments"] is True
    assert plan["preserves_flipud_negative_view_and_array_base"] is True
    assert plan["stop_before"] == "lattice_to_mesh_type/DECMesh"
    assert plan["source_or_scientific_release"] is False
    api = stage.prefix.previous._world_api()
    assert api.VORONOI_IMAGE_SOURCE_SHA256 is api.VORONOI_IMAGE_REVIEW_SHA256 is None


def test_preparation_exact_seven_file_scope_and_literal_cannot_start_mesh():
    assert len(software.OWNED) == 7 and len(set(software.OWNED)) == 7
    tree = ast.parse((software.ROOT / software.LITERAL).read_bytes())
    cls = next(node for node in tree.body if isinstance(node, ast.ClassDef))
    method = next(node for node in cls.body if isinstance(node, ast.FunctionDef))
    assert len(method.body) == 4
    text = ast.unparse(method)
    assert "phase.p.tissue_default.picker_image_filename" in text
    assert "phase.p.conf_dirname" in text and "cells=self" in text
    assert "DECMesh" not in text and "lattice_to_mesh_type" not in text
    assert "prelude" not in text.lower() and "RandomState" not in text


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_preparation_unbound_contract_precedes_any_foreign_owner_or_descriptor_read(
    monkeypatch, entry
):
    class Unavailable:
        def __getattribute__(self, name):
            raise AssertionError("Unadopted owner/descriptor must not be inspected")

    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(ValueError) as caught:
        if entry == "request":
            stage.from_prefix(Unavailable(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Unavailable(), enabled=True)
    assert caught.value.stage in (
        "unbound_contract",
        "unbound_voronoi_image_contract",
        "unbound_image_helpers",
    )
    assert not stage._ACTIVE and not stage._ISSUED


def _rejected_frame_context():
    # Guard/admission metadata only. There is no phase, p, Request, claim,
    # native runtime, issued parent or source-body delegate in this fixture.
    return NS(
        request=None,
        active=True,
        invalid=False,
        thread=stage.get_ident(),
        entry_error=None,
        observation_error=None,
        observation_errors=(),
        capture_failures=(),
        capture_reporting_errors=(),
        work=[],
        admitted={},
        body_codes={},
        root_claimed=False,
        root_body=None,
        body_parent_frame=None,
        driver_frame=sys._getframe(),
        getter_body=None,
        core_claimed=set(),
        forbidden_image_methods=set(),
    )


@pytest.mark.parametrize(
    "name", [stage.WRAPPER_METHOD, stage.ROOT_METHOD, *stage.CORE_METHODS, "image_helper"]
)
def test_entry_raw_same_next_and_helper_frames_record_refusal_before_any_delegate(name):
    context = _rejected_frame_context()
    code, foreign = object(), object()
    frame = NS(f_code=code, f_back=foreign, f_locals={})
    context.body_codes[code] = name
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.VoronoiImageRejected) as caught:
            stage._admit(context, frame)
        assert context.invalid and context.entry_error is caught.value
        assert len(context.work) == 1 and context.work[0]["frame"] is frame
        assert context.work[0]["state"] == "rejected_before_body"
        assert context.work[0]["body_started"] is False
        with pytest.raises(stage.VoronoiImageRejected) as again:
            stage._guard(context)
        assert again.value is caught.value
    finally:
        assert stage._ACTIVE[-1] is context
        stage._ACTIVE.pop()


@pytest.mark.parametrize("reporting_fails", [False, True])
def test_retention_sticky_entry_primary_precedes_capture_and_failed_reporting(
    monkeypatch, reporting_fails
):
    class FalseFailure(ValueError):
        def __bool__(self):
            return False

    original, cause, capture = FalseFailure("entry"), KeyError("cause"), OSError("capture")
    try:
        raise original from cause
    except FalseFailure:
        pass
    context = _rejected_frame_context()
    context.entry_error = original
    reporting = RuntimeError("reporter entry")

    def remember(*args, **kwargs):
        if reporting_fails:
            raise reporting

    monkeypatch.setattr(stage.prefix, "_remember", remember)
    stage._capture_failure(context, capture, "synthetic_observation", context)
    with pytest.raises(FalseFailure) as caught:
        stage._guard(context)
    assert caught.value is original and original.__cause__ is cause
    assert context.observation_error is capture and context.capture_failures[-1][1] is capture
    if reporting_fails:
        assert context.capture_reporting_errors[-1][1] is reporting


@pytest.mark.parametrize("boundary", ["enter", "return", "unwind"])
def test_observer_helper_boundary_retains_actual_return_or_primary_without_extra_delegate(
    monkeypatch, boundary
):
    context = _rejected_frame_context()
    context.operation_active, context.events = False, []
    context.last_operation_result = None
    calls, capture = [], OSError("synthetic capture")
    original, cause, returned = ValueError("native helper stand-in"), KeyError("cause"), object()

    def observe(actual, name, raw):
        if name.endswith("_" + boundary):
            stage._capture_failure(actual, capture, name, raw)

    def delegate():
        calls.append("delegate")
        if boundary == "unwind":
            stage._capture_failure(context, capture, "synthetic_unwind", returned)
            raise original from cause
        return returned

    def invoke():
        return stage._operation(context, "synthetic_helper", delegate)

    # Isolate the operation adapter's source-blocked seam. No owner or phase
    # validator is replaced with a fake successful public construction.
    monkeypatch.setattr(stage, "_check", lambda actual: None)
    monkeypatch.setattr(stage, "_observe", observe)
    monkeypatch.setattr(stage.prefix, "_remember", lambda *args, **kwargs: None)
    context.operation_wrappers = {invoke.__code__}
    caller = sys._getframe()
    context.admitted[id(caller)] = dict(frame=caller, body_started=True)
    stage._ACTIVE.append(context)
    try:
        expected = ValueError if boundary == "unwind" else stage.prefix.literal._CaptureStop
        with pytest.raises(expected) as caught:
            invoke()
        assert context.observation_error is capture
        if boundary == "enter":
            assert calls == [] and context.last_operation_result is None
        elif boundary == "return":
            assert calls == ["delegate"] and context.last_operation_result[1] is returned
            assert "source_error" not in context.work[-1]
        else:
            assert calls == ["delegate"] and caught.value is original
            assert original.__cause__ is cause and context.work[-1]["source_error"] is original
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("name", stage.NUMPY_HELPERS)
def test_bindings_equal_looking_reached_numpy_helper_retarget_is_visible(name):
    def first(*args):
        return None

    def second(*args):
        return None

    numpy = NS(**{key: first for key in stage.NUMPY_HELPERS})
    namespace = {"np": numpy, "__builtins__": {"__import__": first}, "DTYPE_UNSIGNED_TO_SIGNED": {}}
    for module_name in stage.HELPER_MODULES:
        namespace[module_name] = ModuleType("synthetic." + module_name)
    graph = FunctionType(first.__code__, {"vars": vars})
    literal_binding = _image_repair_literal_binding()
    context = NS(
        image_namespace=namespace,
        literal_namespace=literal_binding[3],
        literal_binding=literal_binding,
        root_scope={"__builtins__": {}},
        import_view=NS(TissuePickerImage=object()),
        body_codes={},
        operation_wrappers=set(),
        forbidden_image_methods=set(),
        imports=first,
        method=first,
        partial_graph=graph,
    )
    before = stage._namespace_bindings(context)
    assert stage._namespace_bindings(context) == before
    setattr(numpy, name, second)
    after = stage._namespace_bindings(context)
    assert len(after) == len(before) and any(a is not b for a, b in zip(after, before, strict=True))


def test_bindings_negative_view_base_and_already_retained_equal_alias_edges_are_preserved():
    # Raw graph/array fixtures only: not supplied geometry or native authority.
    first_base, second_base = np.zeros((3, 3)), np.zeros((3, 3))
    first, second = first_base[::-1], second_base[::-1]
    mask = NS(first=first, second=second, clipping_matrix=first)
    tape = NS(
        mask=mask, picker=NS(filename="synthetic"), splines=[], hull=None, locals={}, events=[]
    )
    cache = stage.images.core.caches.snapshot(stage.images._event_record(vars(mask)))
    before = stage.images._graph(tape)
    assert any(value is first_base for value in before[0])
    assert any(value is second_base for value in before[0])
    assert first.strides[0] < 0 and first.base is first_base
    mask.clipping_matrix = second
    after = stage.images._graph(tape)
    assert (
        stage.images.core.caches.snapshot(stage.images._event_record(vars(mask))).identity
        == cache.identity
    )
    assert len(before[0]) == len(after[0])
    assert all(a is b for a, b in zip(before[0], after[0], strict=True))
    assert before[1] != after[1]


@pytest.mark.parametrize("entry", ["constructor", "unissued"])
def test_preparation_no_public_inspection_object_conveys_live_image_authority(entry):
    if entry == "constructor":
        with pytest.raises(TypeError):
            stage.VoronoiImageOwner()
    else:
        raw = object.__new__(stage.VoronoiImageOwner)
        with pytest.raises(stage.VoronoiImageRejected):
            stage._authority(raw)


def test_preparation_one_way_binding_does_not_add_a_reciprocal_prefix_hash():
    coordinator = ast.parse(
        (
            software.ROOT / "src/cells/processes/betse_native_world_phase_construction.py"
        ).read_bytes()
    )
    prefix_tree = ast.parse(
        (software.ROOT / "src/cells/processes/betse_native_seed_world_prefix.py").read_bytes()
    )
    assignments = {
        node.targets[0].id: node.value
        for node in coordinator.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }
    assert ast.literal_eval(assignments["VORONOI_IMAGE_SOURCE_SHA256"]) is None
    assert ast.literal_eval(assignments["VORONOI_IMAGE_REVIEW_SHA256"]) is None
    assert ast.literal_eval(assignments["HELPER_BACK_REFERENCE_SLOTS"]) == (
        "CONSTRUCTION_SOURCE_SHA256",
        "CONSTRUCTION_REVIEW_SHA256",
    )
    text = ast.unparse(prefix_tree)
    assert "VORONOI_IMAGE_SOURCE_SHA256 =" not in text
    assert "VORONOI_IMAGE_REVIEW_SHA256 =" not in text


@pytest.mark.parametrize("failed_index", [None, 0, 1])
def test_retention_finalization_restore_attempts_both_hooks_and_proves_exact_pair(failed_index):
    # Metadata setter/getter model only: never install a real hook or owner.
    expected = (object(), object())
    actual, calls, error = [None, None], [], OSError("restore")

    def setter(index):
        def invoke(value):
            calls.append(index)
            if index == failed_index:
                raise error
            actual[index] = value

        return invoke

    context = NS(
        required_hooks=expected,
        restore_setters=(setter(0), setter(1)),
        restore_getters=(lambda: actual[0], lambda: actual[1]),
        cleanup_errors=(),
    )
    restored = stage._restore_required_hooks(context)
    assert calls == [1, 0]
    assert len(context.finalization_hook_samples) == 2
    assert restored is (failed_index is None)
    if failed_index is not None:
        assert context.cleanup_errors[0][1] is error


def test_retention_return_rejected_descriptor_cannot_be_closed_twice(monkeypatch):
    error, closes = OSError("input observation"), []

    def finish():
        raise error

    tape = NS(finish_inputs=finish, descriptors=[111111, 222222])
    context = NS(
        tape=tape,
        observation_error=None,
        capture_failures=(),
        input_cleanup_errors=(),
        closed_descriptors=set(),
        cleanup_errors=(),
        required_hooks=(None, None),
        restore_setters=(lambda value: None, lambda value: None),
        restore_getters=(lambda: None, lambda: None),
    )
    with monkeypatch.context() as patch:
        patch.setattr(stage.os, "close", closes.append)
        stage._retire_inputs(context)
        stage._retire_inputs(context)
    assert closes == [111111, 222222]
    assert context.observation_error is error
    assert context.closed_descriptors == {111111, 222222}


def _image_repair_literal():
    """Build definitions from CodeType only; never execute a source module/body."""
    payload = (
        b"class VoronoiImagePrefix:\n    def make_voronoi(self, phase):\n        return None\n"
    )
    filename = str(software.ROOT / "_metadata_literal_not_executed.py")
    module_code = compile(payload, filename, "exec", dont_inherit=True)
    cls_code = next(
        value for value in module_code.co_consts if isinstance(value, type(module_code))
    )
    method_code = next(
        value for value in cls_code.co_consts if isinstance(value, type(module_code))
    )
    namespace = {"__name__": "synthetic_literal_metadata"}
    function = FunctionType(method_code, namespace)
    cls = type(
        "VoronoiImagePrefix", (), {"__module__": namespace["__name__"], "make_voronoi": function}
    )
    namespace["VoronoiImagePrefix"] = cls
    return payload, filename, namespace, cls, function


def _image_repair_literal_binding():
    payload, filename, namespace, cls, function = _image_repair_literal()
    return stage._literal_callable(
        payload,
        filename,
        namespace,
        expected_class=cls,
        expected_function=function,
        with_binding=True,
    )


def _image_repair_namespace():
    calls = []

    def ordinary(*args):
        return None

    def hidden(value=None, *, sink=calls):
        return None

    def helper(value=None, *, sink=calls, delegate=hidden):
        return None

    def foreign(value=None, *, sink=calls, delegate=hidden):
        sink.append("foreign body must not execute")

    namespace = {
        "np": NS(**{name: ordinary for name in stage.NUMPY_HELPERS}),
        "__builtins__": {"__import__": ordinary},
        "DTYPE_UNSIGNED_TO_SIGNED": {},
        "interp2d_linear": helper,
    }
    for name in stage.HELPER_MODULES:
        namespace[name] = ModuleType("synthetic." + name)
    literal_binding = _image_repair_literal_binding()
    context = NS(
        image_namespace=namespace,
        literal_namespace=literal_binding[3],
        literal_binding=literal_binding,
        root_scope={"__builtins__": {}},
        import_view=NS(TissuePickerImage=object()),
        body_codes={helper.__code__: "interp2d_linear"},
        operation_wrappers=set(),
        forbidden_image_methods=set(),
        imports=ordinary,
        method=ordinary,
        partial_graph=FunctionType(ordinary.__code__, {"vars": vars}),
    )
    return context, helper, hidden, foreign, calls


def test_image_repair_unchanged_namespace_function_authority_passes_metadata_check():
    context, _, _, _, calls = _image_repair_namespace()
    context.namespace_bindings = stage._namespace_bindings(context)
    stage._check_namespace_bindings(context)
    assert calls == []


@pytest.mark.parametrize(
    "mutation", ["code", "defaults", "keyword_delegate", "wrapped_code", "implementation_code"]
)
def test_image_repair_same_object_namespace_mutation_refuses_before_helper_body(mutation):
    context, helper, hidden, foreign, calls = _image_repair_namespace()
    if mutation == "wrapped_code":
        helper.__kwdefaults__["delegate"] = None
        helper.__wrapped__ = hidden
    if mutation == "implementation_code":
        helper.__kwdefaults__["delegate"] = None
        helper._implementation = hidden
    context.namespace_bindings = stage._namespace_bindings(context)
    original = context.image_namespace["interp2d_linear"]
    namespace_objects = tuple(context.image_namespace.items())
    numpy_objects = tuple(vars(context.image_namespace["np"]).items())
    if mutation == "code":
        helper.__code__ = foreign.__code__
        assert helper.__code__ not in context.body_codes
    elif mutation == "defaults":
        helper.__defaults__ = (object(),)
    elif mutation == "keyword_delegate":
        helper.__kwdefaults__["delegate"] = foreign
    else:
        hidden.__code__ = foreign.__code__
    assert context.image_namespace["interp2d_linear"] is original is helper
    assert all(
        a is b
        for (_, a), (_, b) in zip(namespace_objects, context.image_namespace.items(), strict=True)
    )
    assert all(
        a is b
        for (_, a), (_, b) in zip(
            numpy_objects, vars(context.image_namespace["np"]).items(), strict=True
        )
    )
    with pytest.raises(ValueError):
        stage._check_namespace_bindings(context)
    assert calls == []


def test_image_repair_loaded_literal_matches_compiled_bytes_without_body_execution():
    payload, filename, namespace, cls, function = _image_repair_literal()
    assert (
        stage._literal_callable(
            payload, filename, namespace, expected_class=cls, expected_function=function
        )
        is function
    )


@pytest.mark.parametrize(
    "mutation", ["code", "function", "defaults", "keyword_defaults", "globals", "delegate"]
)
def test_image_repair_pre_namespace_literal_replacement_refuses_before_factory(
    monkeypatch, mutation
):
    payload, filename, namespace, cls, function = _image_repair_literal()
    expected = function

    def foreign(self, phase):
        return 42

    if mutation == "code":
        function.__code__ = foreign.__code__
    elif mutation == "function":
        cls.make_voronoi = FunctionType(function.__code__, namespace)
    elif mutation == "defaults":
        function.__defaults__ = (None,)
    elif mutation == "keyword_defaults":
        function.__kwdefaults__ = {"unexpected": None}
    elif mutation == "globals":
        expected = FunctionType(function.__code__, dict(namespace))
        cls.make_voronoi = expected
    else:
        function.__wrapped__ = foreign
    calls = []

    def root():
        return stage._literal_callable(
            payload, filename, namespace, expected_class=cls, expected_function=expected
        )

    def factory(*args):
        calls.append("helper factory must not execute")
        raise AssertionError("factory")

    monkeypatch.setattr(stage, "_root_literal", root)
    monkeypatch.setattr(stage.images, "_namespace", factory)
    with pytest.raises(ValueError):
        stage._namespace(NS(tape=object()))
    assert calls == []


@pytest.mark.parametrize(
    "boundary",
    ["healthy", "unrestorable", "restore_entry", "restore_return", "finish_entry", "finish_return"],
)
def test_image_repair_input_hook_proof_precedes_observation_and_closes_are_independent(
    monkeypatch, boundary
):
    expected, state, calls = (object(), object()), [None, None], []
    primary, cause = ValueError("retained source primary"), KeyError("cause")
    try:
        raise primary from cause
    except ValueError:
        pass
    capture = OSError("observation")

    def setter(index):
        def invoke(value):
            calls.append(("restore", index))
            if boundary == "unrestorable":
                raise capture
            state[index] = value

        return invoke

    def finish():
        assert state[0] is expected[0] and state[1] is expected[1]
        calls.append(("finish",))
        if boundary in ("finish_entry", "finish_return"):
            state[:] = [None, None]
            raise capture

    context = NS(
        tape=NS(finish_inputs=finish, descriptors=[111111, 222222]),
        required_hooks=expected,
        restore_setters=(setter(0), setter(1)),
        restore_getters=(lambda: state[0], lambda: state[1]),
        cleanup_errors=(),
        observation_error=None,
        capture_failures=(),
        input_cleanup_errors=(),
        closed_descriptors=set(),
        primary=primary,
    )
    original = stage._restore_required_hooks
    if boundary in ("restore_entry", "restore_return"):

        def rejected(actual):
            if boundary == "restore_return":
                assert original(actual)
                state[:] = [None, None]
            raise capture

        monkeypatch.setattr(stage, "_restore_required_hooks", rejected)
    with monkeypatch.context() as patch:
        patch.setattr(stage.os, "close", lambda fd: calls.append(("close", fd)))
        stage._retire_inputs(context)
    assert ("finish",) in calls if boundary != "unrestorable" else ("finish",) not in calls
    assert [row for row in calls if row[0] == "close"] == [("close", 111111), ("close", 222222)]
    assert context.primary is primary and primary.__cause__ is cause
    if boundary != "healthy":
        assert context.observation_error is capture or context.input_observation_skipped


@pytest.mark.parametrize("failure", ["partial", "exception_seal"])
def test_image_repair_issuance_failure_retains_primary_cause_and_secondary_capture(
    monkeypatch, failure
):
    class FalseFailure(MemoryError):
        def __bool__(self):
            return False

    primary, cause, secondary = FalseFailure("issuance"), KeyError("cause"), OSError("capture")
    try:
        raise primary from cause
    except FalseFailure:
        pass
    context = NS(invalid=False, request=None, capture_reporting_errors=())
    trial = object()  # Metadata witness only; no actual Trial/owner is issued.

    def partial(actual):
        if failure == "partial":
            raise secondary
        return actual

    monkeypatch.setattr(stage, "_partial", partial)
    rejected_type = stage.VoronoiImageRejected
    if failure == "exception_seal":

        def rejected(*args, **kwargs):
            raise secondary

        monkeypatch.setattr(stage, "VoronoiImageRejected", rejected)
    with pytest.raises(rejected_type if failure == "partial" else FalseFailure) as caught:
        stage._raise_issuance_failure(context, primary, trial)
    if failure == "partial":
        assert caught.value.capture_error is primary and caught.value.__cause__ is primary
        assert caught.value.partial is context and caught.value.source_error is None
    else:
        assert caught.value is primary
    assert context.invalid and context.issuance_error is primary
    assert primary.__cause__ is cause and context.capture_reporting_errors[-1][1] is secondary


def test_image_repair_helper_factory_cannot_replace_previously_authenticated_root(monkeypatch):
    binding = _image_repair_literal_binding()
    calls = []

    def changed(self, phase):
        return 42

    def factory(*args):
        calls.append("metadata factory")
        binding[1].__code__ = changed.__code__
        return {}

    monkeypatch.setattr(stage, "_root_literal", lambda: binding)
    monkeypatch.setattr(stage.images, "_namespace", factory)
    context = NS(tape=object())
    with pytest.raises(ValueError, match="root literal changed"):
        stage._namespace(context)
    assert calls == ["metadata factory"] and not hasattr(context, "method")
