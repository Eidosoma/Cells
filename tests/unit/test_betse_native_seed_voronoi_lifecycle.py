"""Written UNRUN native-blocked lifecycle controls; no supplied parent authority."""

import ast
import os
import sys
from contextlib import contextmanager
from dataclasses import replace
from threading import get_ident
from types import CodeType, FunctionType, MappingProxyType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_voronoi_lifecycle as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_voronoi_lifecycle_software as software

_RAW_GUARD_SCOPES = []
_PROTOCOL_CONTEXTS = []
_RAW_PROTOCOL_CAPTURE_ERRORS = []
_RAW_PROTOCOL_JOURNALS = []


def _write_protocol_journal(contexts, path, nodeid, *, required, primary=None, writer=None):
    """Forensic metadata after independent restoration; never a source permit."""
    errors, states = [], []
    setters, getters = (sys.setprofile, sys.settrace), (sys.getprofile, sys.gettrace)

    def restore(label):
        for index in (1, 0):
            try:
                setters[index](required[index])
            except BaseException as error:
                errors.append((label + "_restore", index, error))
        current = []
        for index in (0, 1):
            try:
                current.append(getters[index]())
            except BaseException as error:
                errors.append((label + "_state", index, error))
                current.append(error)
        states.append((label, tuple(current)))
        return all(current[index] is required[index] for index in (0, 1))

    data = None
    try:
        if not restore("before_writer"):
            raise RuntimeError("Journal continuation held: inherited hooks unavailable")
        data = dict(
            nodeid=nodeid,
            primary_id=None if primary is None else id(primary),
            primary_type=None if primary is None else type(primary).__qualname__,
            primary_cause_id=(
                None if primary is None or primary.__cause__ is None else id(primary.__cause__)
            ),
            contexts=[
                dict(
                    history=getattr(context, "protocol_history", []),
                    total=getattr(context, "protocol_total", 0),
                    dropped=getattr(context, "protocol_dropped", 0),
                    entry_error_id=(
                        None if context.entry_error is None else id(context.entry_error)
                    ),
                    interruptions=len(context.generator_interruptions),
                )
                for context in contexts
            ],
            full_owner_graph_serialized=False,
        )
        (software.snapshot.write_json if writer is None else writer)(path, data)
    except BaseException as error:
        errors.append(("journal", None, error))
    finally:
        if not restore("after_writer"):
            errors.append(("journal_final_hooks", None, RuntimeError("Hooks not restored")))
        _RAW_PROTOCOL_JOURNALS.append((contexts, primary, data, tuple(states), tuple(errors)))
        if errors:
            _RAW_PROTOCOL_CAPTURE_ERRORS.append((tuple(errors), contexts, primary, nodeid))
    return tuple(errors)


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Source-only preparation; lifecycle software release held")
    request.config.option.maxfail = 1  # This one released metadata suite stops on failure.
    first_context = len(_PROTOCOL_CONTEXTS)
    required = (sys.getprofile(), sys.gettrace())
    restore = (sys.setprofile, sys.settrace)
    primary = None
    adapter = NS(**dict(vars(software), reuse=software.reuse.reuse))
    namespace = dict(vars(controls), software=adapter, stage=stage, _BLOCKADE_FAILURES=())
    original = controls._blockade.__wrapped__
    function = FunctionType(original.__code__, namespace, original.__name__)
    try:
        with contextmanager(function)(request, tmp_path):
            yield
    except BaseException as error:
        primary = error
        raise
    finally:
        if namespace["_BLOCKADE_FAILURES"]:
            _RAW_GUARD_SCOPES.append(namespace)
        contexts = _PROTOCOL_CONTEXTS[first_context:]
        if contexts:
            try:
                errors = _write_protocol_journal(
                    contexts,
                    tmp_path / "protocol-history.json",
                    request.node.nodeid,
                    required=required,
                    primary=primary,
                )
            except BaseException as error:
                errors = (("journal_call_boundary", None, error),)
                _RAW_PROTOCOL_CAPTURE_ERRORS.append(
                    (errors, contexts, primary, request.node.nodeid)
                )
                for index in (1, 0):
                    try:
                        restore[index](required[index])
                    except BaseException as secondary:
                        errors += (("journal_boundary_restore", index, secondary),)
            if errors:
                # Pytest keeps the original CALL report; this distinct teardown
                # error refuses acceptance if diagnostic capture itself fails.
                error = AssertionError("Protocol-history capture failed")
                error.source_error = primary
                raise error from errors[0][2]


def _definitions(relative):
    tree = ast.parse((software.ROOT / relative).read_bytes())
    return tree, {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_preparation_exact_six_paths_original_statements_and_all_pins_held():
    plan = stage.source_plan()
    assert len(software.OWNED) == len(set(software.OWNED)) == 6
    assert plan["branches"] == ("single", "multi_nonSVG")
    assert plan["source_pin"] is plan["parent_pin"] is plan["parent_review"] is None
    assert plan["stop_before"] == ("ecm_verts", "cluster_mask", "msize", "ecm_verts_unique")
    assert plan["caller_descriptors_repeated"] is False
    assert plan["original_CodeTypes_and_actual_mesh"] is True
    assert plan["new_mesh_or_standalone_runtime"] is False
    assert plan["source_native_reference_scientific_release"] is False
    assert plan["invalidated_owners"] == 11 and plan["held_postcut_cases"] == 12
    assert "pre_mesh" in plan["static_self_edges"]["refine_mesh"]
    _, methods = _definitions(software.SOURCE)
    namespace = ast.unparse(methods["_namespace"])
    assert "FunctionType(fn.__code__" in namespace
    assert "original_type" in namespace and "_source_function" in namespace
    assert "_MODULE_AUTH" in namespace and "_check_modules" in namespace


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_preparation_unadopted_route_refuses_before_any_owner_or_descriptor_read(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Unadopted foreign authority must not be inspected")

    with pytest.raises(stage.LifecycleRejected) as caught:
        if entry == "request":
            stage.from_constructor(Foreign(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._ISSUED


@pytest.mark.parametrize("entry", ["owner", "unissued", "literal"])
def test_preparation_no_plain_or_serialized_object_grants_native_authority(entry):
    if entry == "owner":
        with pytest.raises(TypeError):
            stage.LifecycleOwner()
    elif entry == "unissued":
        with pytest.raises(stage.LifecycleRejected) as caught:
            stage._authority(NS())
        assert caught.value.stage == "owner"
    else:
        with pytest.raises(ValueError, match="Pinned lifecycle literal"):
            stage._literal_code("single")


def _callsite_probe(monkeypatch, tmp_path, branch):
    # METADATA-ONLY stand-in with identical arguments in all three branches.
    # Compile CodeTypes, never execute a labelled native/literal module body.
    text = """class Metadata:
    def probe(self, phase):
        lattice = {}
        if phase.p.single_cell:
            self.mesh = DECMesh(argument=1)
        else:
            if phase.p.svg_override:
                self.mesh = DECMesh(argument=1)
            else:
                self.mesh = DECMesh(argument=1)
"""
    path = tmp_path / "metadata_callsite.py"
    path.write_text(text)
    outer = compile(text, str(path), "exec")
    cls = next(v for v in outer.co_consts if type(v) is CodeType)
    code = next(v for v in cls.co_consts if type(v) is CodeType)
    monkeypatch.setattr(stage.previous, "_LITERAL_FILE", path)
    catalog = stage.previous._call_sites(code)
    request = stage.previous.Request(
        None, "parent", "source", stage.previous.MODE, "metadata-request", stage._digest(catalog)
    )
    calls, reads = [], []

    class Parameters:
        @property
        def single_cell(self):
            reads.append("single_cell")
            return branch == "single"

        @property
        def svg_override(self):
            reads.append("svg_override")
            return branch == "svg"

    context = NS(request=request, call_witness=None, root_frame=None, method=None)

    def factory(**kwargs):
        root = sys._getframe(1)
        context.root_frame = root
        stage.previous._claim_callsite(context, root)
        calls.append(dict(kwargs))
        return object()

    context.method = FunctionType(code, dict(globals(), DECMesh=factory))
    actual, phase = NS(), NS(p=Parameters())
    context.method(actual, phase)
    return context, actual, phase, calls, reads


@pytest.mark.parametrize("branch", ["single", "svg", "multi_nonSVG"])
def test_witness_actual_suspended_call_and_store_distinguish_equal_arguments(
    monkeypatch, tmp_path, branch
):
    context, actual, _, calls, reads = _callsite_probe(monkeypatch, tmp_path, branch)
    witness = context.call_witness
    assert witness.branch == branch
    assert calls == [{"argument": 1}] and actual.mesh is not None
    assert reads == (["single_cell"] if branch == "single" else ["single_cell", "svg_override"])
    assert context.callsite_link[2] is context.root_frame
    assert context.callsite_link[3] is context.method.__code__
    assert stage.previous._WITNESSES[context.request] is context.callsite_link
    stage.previous._check_callsite(context)
    assert witness.catalog_identity == context.request.callsite_identity
    assert witness.identity == stage._digest(stage.previous.witness_record(witness))


@pytest.mark.parametrize("drift", ["equal_tuple", "code", "witness", "offset"])
def test_witness_private_frame_code_and_issuance_retarget_refuse(monkeypatch, tmp_path, drift):
    context, _, _, calls, _ = _callsite_probe(monkeypatch, tmp_path, "multi_nonSVG")
    original = context.callsite_link
    if drift == "equal_tuple":
        stage.previous._WITNESSES[context.request] = tuple(list(original))
        assert stage.previous._WITNESSES[context.request] == original
        assert stage.previous._WITNESSES[context.request] is not original
    elif drift == "code":
        context.method = FunctionType(context.method.__code__.replace(), context.method.__globals__)
    elif drift == "witness":
        context.call_witness = replace(context.call_witness)
    else:
        value = replace(context.call_witness, offset=-1, identity="")
        value = replace(value, identity=stage._digest(stage.previous.witness_record(value)))
        context.call_witness = value
        context.callsite_link = (context, value, original[2], original[3])
        stage.previous._WITNESSES[context.request] = context.callsite_link
    with pytest.raises(ValueError, match="CALL|witness"):
        stage.previous._check_callsite(context)
    assert calls == [{"argument": 1}]


def test_witness_claim_precedes_either_inherited_observer_and_constructor_work():
    _, functions = _definitions("src/cells/processes/betse_native_seed_voronoi_mesh.py")
    admit = ast.unparse(functions["_admit"])
    assert admit.index("_claim_callsite(context, parent)") < admit.index(
        "context.factory_claimed, context.factory_frame ="
    )
    body = ast.unparse(functions["_construct"])
    assert body.index("_check_callsite(context)") < body.index(
        "object.__new__(context.runtime_type)"
    )
    _, functions = _definitions("src/cells/processes/betse_native_seed_world_prefix.py")
    account = ast.unparse(functions["_account"])
    assert "before(frame, event)" in account and "_admit(context, frame)" in account
    literal = ast.parse((software.ROOT / software.LITERAL).read_bytes())
    reads = {n.attr for n in ast.walk(literal) if isinstance(n, ast.Attribute)}
    assert "single_cell" not in reads and "svg_override" not in reads
    assert {"refine_mesh", "maximum_voronoi_steps", "voronoi_convergence"} <= reads


def _entry_context():
    return NS(
        work=[],
        events=[],
        locals={},
        helper_results=[],
        invalid=False,
        active=True,
        thread=get_ident(),
        stage="metadata",
        request=None,
        trial=None,
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        capture_reporting_errors=(),
        helper_views=[],
        admitted={},
        body_codes={},
        root_frame=None,
        root_claimed=False,
        method_claimed=False,
        wrapper_claimed=False,
        wrapper_frame=None,
        mesh=object(),
        delegate_frames={},
        helper_active=False,
        pending_source_error=None,
        generator_sites={},
        generator_suspensions={},
        generator_results=[],
        generator_views=[],
        generator_interruptions=[],
        generator_observations=[],
    )


@pytest.mark.parametrize(
    "name",
    ["init_mesh", "clip_and_refine", "pre_mesh", "make_single_cell_points", "create_aux_operators"],
)
def test_entry_inactive_or_failed_raw_mesh_refuses_before_delegate(name):
    context = _entry_context()
    context.active = False
    calls = []
    with pytest.raises(stage.LifecycleRejected) as caught:
        stage._mesh_call(
            context,
            object(),
            name,
            lambda *args: calls.append(name),
            context.mesh,
            (),
            {},
            object(),
        )
    assert caught.value is context.entry_error and context.invalid
    assert calls == [] and context.work[-1]["state"] == "rejected"
    assert not context.work[-1]["body_started"]


@pytest.mark.parametrize("method", ["init_mesh", "clip_and_refine", "pre_mesh"])
def test_entry_same_or_next_method_from_observer_is_sticky_and_has_zero_body_calls(method):
    context = _entry_context()
    code = object()
    context.body_codes[code] = "mesh_method_wrapper"
    frame = NS(f_code=code, f_back=NS(f_code=object()), f_locals={"name": method})
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.LifecycleRejected) as caught:
            stage._admit(context, frame)
        assert caught.value is context.entry_error and context.invalid
        assert context.work[-1]["state"] == "rejected" and not context.work[-1]["body_started"]
        with pytest.raises(stage.LifecycleRejected) as repeated:
            stage._guard(context)
        assert repeated.value is caught.value
    finally:
        stage._ACTIVE.pop()


def test_entry_native_nested_pre_mesh_is_claimed_once_before_observers():
    context = _entry_context()
    body_code, wrapper_code = object(), object()
    context.body_codes = {body_code: "DECMesh.refine_mesh", wrapper_code: "mesh_method_wrapper"}
    parent = NS(f_code=body_code)
    context.admitted[id(parent)] = dict(frame=parent, state="admitted", body_started=True)

    def delegate(*args):
        return None

    context.parent = NS(original_type=NS(pre_mesh=delegate))
    context.mesh_bodies = {"pre_mesh": object()}
    context.edges = {"refine_mesh": ("pre_mesh",)}
    frame = NS(
        f_code=wrapper_code,
        f_back=parent,
        f_locals=dict(
            name="pre_mesh", actual=context.mesh, context=context.parent, delegate=delegate
        ),
    )
    stage._ACTIVE.append(context)
    try:
        stage._admit(context, frame)
        first = context.admitted[id(frame)]
        assert first["state"] == "admitted" and first["body_started"] is False
        stage._admit(context, frame)  # trace/profile share ONE frame claim.
        assert len(context.work) == 1 and context.admitted[id(frame)] is first
    finally:
        stage._ACTIVE.pop()


def test_entry_unknown_native_helper_gate_precedes_inherited_callbacks(monkeypatch):
    context = _entry_context()
    context.native_root, context.body_codes = "/exact/native/", {}
    observer = stage._ObserverSystem(context)
    frame = NS(f_code=NS(co_filename="/exact/native/unbound.py"))

    # A real code object is hashable; this stand-in isolates only the path gate.
    class Code:
        co_filename = "/exact/native/unbound.py"

    frame.f_code = Code()
    with pytest.raises(stage.LifecycleRejected) as caught:
        observer._gate(frame, "call")
    assert caught.value is context.entry_error and context.invalid
    assert context.work[-1]["body_started"] is False


@pytest.mark.parametrize("unwind", [False, True])
@pytest.mark.parametrize("capture_fails", [False, True])
def test_retention_mask_query_return_keeps_raw_array_and_native_unwind(
    monkeypatch, unwind, capture_fails
):
    context = _entry_context()
    primary, capture = ValueError("native spline failure"), OSError("query view")
    primary.__cause__ = KeyError("original cause")
    code = object()
    frame = NS(f_code=code)
    context.mask_codes = {code}
    context.query_results, context.query_views = [], []
    context.admitted[id(frame)] = dict(frame=frame, source_error=primary if unwind else None)
    result = None if unwind else np.array([1.0])

    def view(actual, value):
        if capture_fails:
            raise capture
        return value

    monkeypatch.setattr(stage, "_helper_value", view)
    observer = stage._ObserverSystem(context)
    stage._ACTIVE.append(context)
    try:
        if capture_fails and not unwind:
            with pytest.raises(stage.previous.image.prefix.literal._CaptureStop):
                observer._result(frame, "return", result)
        else:
            observer._result(frame, "return", result)
        assert context.query_results[0][0] is frame
        assert context.query_results[0][1] is result
        assert context.query_results[0][2] is (primary if unwind else None)
        if capture_fails:
            assert context.observation_error is capture and context.capture_errors
        else:
            assert context.query_views[0] is result
        assert primary.__cause__.args == ("original cause",)
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("boundary", ["enter", "return"])
def test_retention_helper_observer_failure_stops_delegate_or_preserves_raw_result(
    monkeypatch, boundary
):
    context = _entry_context()
    output, calls, capture = np.array([1.0, -0.0]), [], OSError("observation")
    monkeypatch.setattr(stage, "_check", lambda actual: None)
    monkeypatch.setattr(stage, "_helper_value", lambda actual, result: result)

    def observe(actual, name, raw):
        if name.endswith("_" + boundary):
            raise capture

    monkeypatch.setattr(stage, "_observe", observe)

    def delegate():
        calls.append("delegate")
        return output

    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.previous.image.prefix.literal._CaptureStop) as caught:
            stage._helper(context, "synthetic", delegate, (), {})
        assert caught.value.__cause__ is capture
        assert calls == ([] if boundary == "enter" else ["delegate"])
        assert context.observation_error is capture and context.capture_errors
        if boundary == "return":
            assert context.last_helper_result[0] == "synthetic"
            assert context.last_helper_result[1] is output
            assert context.helper_results[0][1] is output
        else:
            assert not context.helper_results
        assert context.helper_active is False
    finally:
        stage._ACTIVE.pop()


def test_retention_recorded_entry_rejection_precedes_secondary_capture(monkeypatch):
    context = _entry_context()
    cause, primary, secondary = KeyError("cause"), ValueError("entry"), OSError("capture")
    primary.__cause__ = cause
    context.entry_error = primary

    def observe(*args):
        raise secondary

    monkeypatch.setattr(stage, "_observe", observe)
    with pytest.raises(ValueError) as caught:
        stage._record(context, "metadata_enter", context)
    assert caught.value is primary and primary.__cause__ is cause
    assert context.observation_error is secondary and context.capture_errors[0][1] is secondary


def test_retention_native_helper_error_remains_original_and_has_no_invented_result(monkeypatch):
    context = _entry_context()
    primary = ValueError("literal helper failure")
    primary.__cause__ = KeyError("literal cause")
    monkeypatch.setattr(stage, "_check", lambda actual: None)
    monkeypatch.setattr(stage, "_record", lambda *args: None)

    def fail():
        raise primary

    stage._ACTIVE.append(context)
    try:
        with pytest.raises(ValueError) as caught:
            stage._helper(context, "synthetic", fail, (), {})
        assert caught.value is primary and caught.value.__cause__ is primary.__cause__
        assert context.work[0]["source_error"] is primary
        assert not context.helper_results and context.helper_active is False
    finally:
        stage._ACTIVE.pop()


def test_graph_actual_reference_edges_detect_equal_already_present_array_retarget():
    a, b = np.array([1.0]), np.array([1.0])
    caller = NS(a=a, b=b, alias=a)
    objects, fields = (("caller", caller),), [{}]
    context = NS(
        cells=caller,
        objects=objects,
        stable_fields=fields,
        stable_view=NS(fields=fields, objects=objects),
        stable_tape=NS(rng=object(), events=(), draws=(), locals={}),
    )
    first = stage._graph(context)
    caller.alias = b
    second = stage._graph(context)
    assert np.array_equal(a, b)
    assert len(first[0]) == len(second[0]) and all(
        a is b for a, b in zip(first[0], second[0], strict=True)
    )
    assert first[1] != second[1]


def test_graph_growing_observations_are_separate_from_immutable_inherited_baseline():
    caller, fields = NS(), [{}]
    context = NS(
        cells=caller,
        objects=(("caller", caller),),
        stable_fields=fields,
        stable_view=NS(fields=fields),
        stable_tape=NS(rng=object(), events=(), draws=(), locals={}),
        events=[],
        locals={},
        work=[],
    )
    before = stage._graph(context)
    context.events.append(("return", object()))
    context.locals["body"] = {"raw": object()}
    context.work.append({"state": "returned"})
    after = stage._graph(context)
    assert before[1] == after[1]
    stage._same(before[0], after[0])


@pytest.mark.parametrize("drift", ["code", "helper", "module_slot"])
def test_graph_original_helper_scope_and_code_retargets_are_bound_without_body_execution(drift):
    calls = []

    def helper(*args):
        calls.append("forbidden")

    def other(*args):
        calls.append("foreign")

    module = ModuleType("metadata_only")
    module.helper = helper
    before = stage._module_bindings(module)
    if drift == "code":
        helper.__code__ = other.__code__
    elif drift == "helper":
        module.helper = other
    else:
        module.equal_slot = object()
    after = stage._module_bindings(module)
    assert calls == []
    with pytest.raises(ValueError, match="identity"):
        stage._same(after, before)


@pytest.mark.parametrize("secondary", ["partial", "exception"])
def test_retention_primary_identity_cause_and_raw_context_survive_capture_failure(
    monkeypatch, secondary
):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    primary, capture = Falsey("source"), OSError("capture")
    cause = KeyError("source cause")
    primary.__cause__ = cause
    context = NS(invalid=False, stage="lifecycle", request=None, trial=None, capture_errors=())

    def fail(*args, **kwargs):
        raise capture

    scope = dict(vars(stage), _partial=fail)
    if secondary == "exception":
        scope["LifecycleRejected"] = fail
    function = FunctionType(stage._failure.__code__, scope)
    with pytest.raises(stage.LifecycleRejected if secondary == "partial" else Falsey) as caught:
        function(context, primary, None)
    if secondary == "partial":
        assert caught.value.source_error is primary and caught.value.capture_error is capture
        assert caught.value.partial is context and caught.value.__cause__ is primary
    else:
        assert caught.value is primary
    assert primary.__cause__ is cause and context.invalid


def test_integration_irreversible_marker_and_current_authority_avoid_old_numeric_validator():
    _, parent = _definitions("src/cells/processes/betse_native_seed_voronoi_mesh.py")
    claim = ast.unparse(parent["_claim_for_voronoi_lifecycle"])
    assert claim.index("parent.lifecycle = transition") < claim.index("_FORWARDED[owner]")
    assert claim.index("_FORWARDED[owner]") < claim.index("_check(parent)")
    public = ast.unparse(parent["_authority"])
    assert public.index("owner in _FORWARDED") < public.index("_check(context)")
    inherited = ast.unparse(parent["_check_lifecycle_authority"])
    invoked = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(parent["_check_lifecycle_authority"])
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
    }
    assert "_authority" not in invoked and "_values" not in invoked and "_epoch" not in invoked
    assert "_check(parent)" in inherited and "trial.call_witness" in inherited
    for name in ("_invoke_mesh", "_wrapper_guard", "_dispatch"):
        body = ast.unparse(parent[name])
        assert body.index("_lifecycle_route(context)") < body.index("_guard(context)")


def test_integration_new_loader_is_one_way_and_all_provider_pins_remain_none():
    tree, functions = _definitions("src/cells/processes/betse_native_world_phase_construction.py")
    slots = {
        target.id: n.value
        for n in tree.body
        if isinstance(n, ast.Assign)
        for target in n.targets
        if isinstance(target, ast.Name)
    }
    for name in ("VORONOI_LIFECYCLE_SOURCE_SHA256", "VORONOI_LIFECYCLE_REVIEW_SHA256"):
        assert isinstance(slots[name], ast.Constant) and slots[name].value is None
    loader = ast.unparse(functions["_world_voronoi_lifecycle_api"])
    assert "_world_voronoi_mesh_api()" in loader and "_import_bound" in loader
    assert "module.PARENT_MODULE != VORONOI_MESH_MODULE" in loader
    _, parent = _definitions("src/cells/processes/betse_native_seed_voronoi_mesh.py")
    route = ast.unparse(parent["_lifecycle_route"])
    assert "_world_voronoi_lifecycle_api()" in route
    assert "_MESHES" not in ast.unparse(functions["_world_voronoi_lifecycle_api"])


def test_integration_original_runtime_wrappers_and_MT_epoch_survive_without_replacement():
    _, methods = _definitions(software.SOURCE)
    invoked = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(methods["prepare"])
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
    }
    assert not {"RandomState", "set_state"} & invoked
    assert "setattr" not in invoked
    text = ast.unparse(methods["_check"])
    assert "context.cells.mesh is not context.mesh" in text
    assert "context.refs[1].stream_after.identity" in text
    assert "context.mesh.make_all_operators is not False" in text
    mesh_call = ast.unparse(methods["_mesh_call"])
    assert "previous._MESHES.get(actual) is not original" in mesh_call
    assert "context.mesh_bodies[name](actual, *args, **kwargs)" in mesh_call


def _protocol_context(monkeypatch, functions):
    """Actual Python generator frames, isolated from all native/owner APIs.

    Only the independent observer protocol is exercised. No issued world,
    constructor, mask, mesh or caller is manufactured by this metadata fixture.
    """
    context = _entry_context()
    api = controls.stage
    context.api = api
    context.checker = (
        api._independent_atoms,
        api._independent_atoms.__code__,
        api._independent_atoms.__globals__,
    )
    context.metadata_helpers = ()
    context.body_codes = {function.__code__: "native_helper_body" for function in functions}
    context.generator_sites = MappingProxyType(
        {
            function.__code__: stage._generator_sites(function.__code__)
            for function in functions
            if function.__code__.co_flags & stage.CO_GENERATOR
        }
    )
    context.mask_codes = frozenset()
    context.native_root = "/unavailable-native-protocol-only/"
    context.rand, context.callback = object(), object()
    context.callback_codes = context.forbidden_callback_codes = frozenset()
    context.draw_active = False
    context.query_results, context.query_views = [], []
    context.cleanup_errors = ()
    context.required_hooks = (sys.getprofile(), sys.gettrace())
    context.restore_setters = (sys.setprofile, sys.settrace)
    context.restore_getters = (sys.getprofile, sys.gettrace)
    # These replacements isolate the observer state machine; they never issue
    # a parent or run native validation. The real guard/admission/account remain.
    monkeypatch.setattr(stage, "_check", lambda actual: None)
    monkeypatch.setattr(stage, "_helper_value", lambda actual, result: result)
    monkeypatch.setattr(stage, "_epoch", lambda actual: ("same", ((), None), "same-MT"))
    _PROTOCOL_CONTEXTS.append(context)
    return context


def _generator_row(context, code):
    rows = [row for row in context.admitted.values() if row["frame"].f_code is code]
    assert len(rows) == 1  # Exactly ONE body claim across suspension/resumption.
    return rows[0]


def test_entry_generator_two_yields_reach_helper_on_each_resume_in_original_order(monkeypatch):
    calls = []

    def selected_helper(value):
        calls.append(value)
        return True

    def produce():
        for value in (1, 2):
            yield selected_helper(value)

    def consume():
        return all(produce())

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        with stage._account(context):
            result = stage._helper(context, "metadata_consumer", consume, (), {})
        row = _generator_row(context, produce.__code__)
        assert result is True and calls == [1, 2]
        assert row["state"] == "returned" and row["returned"] is True
        assert row["activation"] == 2 and row["source_errors"] == []
        assert not context.generator_suspensions
        assert [item[2] for item in context.generator_results] == ["yield", "yield", "terminal"]
        assert [item[3] for item in context.generator_results] == [True, True, None]
        for activation in range(3):
            observed = [
                entry
                for entry in context.generator_observations
                if entry["observation"][3] == activation
            ]
            assert {entry["observation"][0] for entry in observed} == {"trace", "profile"}
            assert sum(entry["decision"] == "logical_exit" for entry in observed) == 1
            assert sum(entry["decision"] == "companion" for entry in observed) == 1
        assert [r["activation"] for r in context.work if r["layer"] == "generator_yield"] == [0, 1]
        assert [r["activation"] for r in context.work if r["layer"] == "generator_resume"] == [1, 2]
        helper_entries = [
            r for r in context.admitted.values() if r["frame"].f_code is selected_helper.__code__
        ]
        assert len(helper_entries) == 2 and all(r["body_started"] for r in helper_entries)
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
        assert not context.invalid and context.entry_error is None
    finally:
        stage._ACTIVE.pop()


def test_entry_generator_foreign_resumer_cannot_seize_retained_yield_slot(monkeypatch):
    calls = []

    def selected_helper(value):
        calls.append(value)
        return True

    def produce():
        yield selected_helper(1)
        yield selected_helper(2)

    generator = produce()  # Creation does not enter its body.

    def first_consumer():
        return next(generator)

    def foreign_consumer():
        return next(generator)

    context = _protocol_context(
        monkeypatch, (selected_helper, produce, first_consumer, foreign_consumer)
    )
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.LifecycleRejected) as caught:
            with stage._account(context):
                assert stage._helper(context, "first", first_consumer, (), {}) is True
                stage._helper(context, "foreign", foreign_consumer, (), {})
        assert caught.value is context.entry_error and context.invalid
        assert calls == [1]  # No second helper/body work after the stolen resume.
        assert context.generator_results[0][2:4] == ("yield", True)
        attempts = [r for r in context.work if r["layer"] == "generator_resume"]
        assert len(attempts) == 1 and attempts[0]["state"] == "rejected"
        assert attempts[0]["body_started"] is False
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        stage._ACTIVE.pop()
        generator.close()  # After the original hooks are restored; metadata only.


def test_entry_nested_caught_generator_reentry_is_sticky_with_no_extra_body(monkeypatch):
    calls, rejections, holder = [], [], {}

    def selected_helper(value):
        calls.append(value)
        row = _generator_row(holder["context"], produce.__code__)
        try:
            # A callback cannot imitate the account's actual before/profile/trace
            # chain, even with the genuine active generator FrameType in hand.
            stage._admit(holder["context"], row["frame"])
        except stage.LifecycleRejected as error:
            rejections.append(error)
        return True

    def produce():
        yield selected_helper(1)
        yield selected_helper(2)

    def consume():
        return all(produce())

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    holder["context"] = context
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.LifecycleRejected) as caught:
            with stage._account(context):
                stage._helper(context, "metadata_consumer", consume, (), {})
        assert len(rejections) == 1 and caught.value is rejections[0] is context.entry_error
        assert context.invalid and calls == [1]
        assert not context.generator_results  # Refuses before the first source yield.
        assert context.work[-1]["body_started"] is False
    finally:
        stage._ACTIVE.pop()


def test_retention_generator_exception_keeps_primary_cause_and_prior_yield(monkeypatch):
    calls = []
    primary = ValueError("synthetic generator source failure")
    primary.__cause__ = KeyError("source cause")

    def selected_helper(value):
        calls.append(value)
        return True

    def produce():
        yield selected_helper(1)
        raise primary

    def consume():
        return all(produce())

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(ValueError) as caught:
            with stage._account(context):
                stage._helper(context, "metadata_consumer", consume, (), {})
        assert caught.value is primary and primary.__cause__.args == ("source cause",)
        assert calls == [1]
        row = _generator_row(context, produce.__code__)
        assert row["state"] == "unwound" and row["returned"] is True
        assert row["source_error"] is primary
        assert any(record[1] is primary for record in row["source_errors"])
        assert context.generator_results[0][2:4] == ("yield", True)
        assert context.generator_results[-1][2] == "terminal"
        assert context.generator_results[-1][4] is primary
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("attempt", ["resume", "helper_after_terminal"])
def test_entry_true_final_generator_or_helper_cannot_reopen_finished_frame(monkeypatch, attempt):
    calls = []

    def selected_helper(value):
        calls.append(value)
        return True

    def produce():
        yield selected_helper(1)
        yield selected_helper(2)

    def consume():
        return all(produce())

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    stage._ACTIVE.append(context)
    try:
        with stage._account(context):
            assert stage._helper(context, "metadata_consumer", consume, (), {}) is True
        row = _generator_row(context, produce.__code__)
        with pytest.raises(stage.LifecycleRejected) as caught:
            if attempt == "resume":
                stage._resume(context, row["frame"], row)
            else:
                # Isolated predicate probe; it cannot create an actual source
                # frame or issue any owner. The completed parent must refuse.
                fake = NS(f_code=selected_helper.__code__, f_back=row["frame"], f_locals={})
                stage._admit(context, fake)
        assert caught.value is context.entry_error and context.invalid
        assert calls == [1, 2]
        assert context.work[-1]["body_started"] is False
        assert context.work[-1]["state"] == "rejected"
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize(
    "drift", [None, "same_code_replacement", "code_identity", "keyword_delegate", "closure_cell"]
)
def test_graph_reached_math_atan2_on_unchanged_module_refuses_before_delegate(drift):
    calls = []

    def original_delegate(x, y):
        calls.append("original")
        return True

    def foreign_delegate(x, y):
        calls.append("foreign")
        return True

    def factory(delegate):
        def atan2(x, y, *, hidden=delegate):
            return hidden(x, y) and delegate(x, y)

        return atan2

    atan2 = factory(original_delegate)
    atan2.__wrapped__ = original_delegate
    maths = ModuleType("metadata_math")
    maths.atan2 = atan2
    geopoly = ModuleType("betse.util.math.geometry.polygon.geopoly")
    geopoly.math = maths
    context = NS(helper_modules=(geopoly,))
    before = stage._math_bindings(context)
    old_code, old_defaults = atan2.__code__, atan2.__kwdefaults__
    old_cell = atan2.__closure__[0].cell_contents
    try:
        if drift == "same_code_replacement":
            replacement = FunctionType(
                old_code, atan2.__globals__, atan2.__name__, atan2.__defaults__, atan2.__closure__
            )
            replacement.__kwdefaults__ = dict(old_defaults)
            replacement.__wrapped__ = atan2.__wrapped__
            maths.atan2 = replacement
            assert replacement.__code__ is old_code  # Value/code-equivalent export.
        elif drift == "code_identity":
            atan2.__code__ = old_code.replace()
            assert atan2.__code__ == old_code and atan2.__code__ is not old_code
        elif drift == "keyword_delegate":
            atan2.__kwdefaults__ = dict(hidden=foreign_delegate)
            assert atan2.__wrapped__ is original_delegate
        elif drift == "closure_cell":
            atan2.__closure__[0].cell_contents = foreign_delegate
            assert atan2.__wrapped__ is original_delegate
        assert geopoly.math is maths  # Outer module/namespace identity never changes.
        if drift is None:
            stage._same(stage._math_bindings(context), before)
            assert maths.atan2(1, 2) is True
            assert calls == ["original", "original"]
        else:
            with pytest.raises(ValueError, match="identity"):
                stage._same(stage._math_bindings(context), before)
                maths.atan2(1, 2)
            assert calls == []  # Neither the original nor the foreign delegate ran.
    finally:
        maths.atan2 = atan2
        atan2.__code__, atan2.__kwdefaults__ = old_code, old_defaults
        atan2.__closure__[0].cell_contents = old_cell


def test_integration_generator_and_math_checks_stay_inside_original_helper_entry_guard():
    _, methods = _definitions(software.SOURCE)
    text = ast.unparse(methods["_original_bindings"])
    assert "*_math_bindings(context)" in text
    assert "_same(_bindings(context), context.bindings)" in ast.unparse(methods["_check"])
    origin = ast.unparse(methods["_generator_origin"])
    assert "before.f_code is codes['before']" in origin
    assert "before.f_globals is context.observer_scope" in origin
    assert "observer.f_locals.get('frame') is frame" in origin
    resume = ast.unparse(methods["_resume"])
    assert resume.index("del context.generator_suspensions[id(frame)]") < resume.index(
        "row['state'] = 'admitted'"
    )
    capture = ast.unparse(methods["_capture"])
    assert "_generator_return(context, frame, row)" in capture
    assert "source_errors" in capture
    assert stage.MATH_HELPERS == ("math.atan2",)


def test_retention_generator_early_all_false_closes_without_spurious_resume_refusal(monkeypatch):
    calls = []

    def selected_helper(value):
        calls.append(value)
        return False

    def produce():
        yield selected_helper(1)
        yield selected_helper(2)

    iterator = produce()  # Retain it: all(False) does not certify a close event.

    def consume():
        return all(iterator)

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    stage._ACTIVE.append(context)
    try:
        with stage._account(context):
            result = stage._helper(context, "metadata_consumer", consume, (), {})
        assert result is False and calls == [1]
        assert context.generator_results[0][2:4] == ("yield", False)
        row = _generator_row(context, produce.__code__)
        assert row["state"] == "suspended" and not row.get("returned", False)
        assert row["source_errors"] == []
        token = row["suspension"]
        assert context.generator_suspensions[id(row["frame"])] is token
        assert token[4] == token[6][0] and token[5] in token[6][1]
        assert row["activation"] == 0 and len(context.generator_results) == 1
        assert context.entry_error is None and not context.invalid
    finally:
        stage._ACTIVE.pop()
        iterator.close()  # Metadata-only cleanup after the inherited hooks were restored.


def test_retention_explicit_generator_close_inside_admitted_consumer_records_actual_unwind(
    monkeypatch,
):
    calls, cleanup = [], []

    def selected_helper(value):
        calls.append(value)
        return False

    def produce():
        try:
            yield selected_helper(1)
            yield selected_helper(2)
        finally:
            cleanup.append("observed-finally")

    iterator = produce()

    def consume():
        result = all(iterator)
        iterator.close()  # The same admitted original consumer performs the close.
        return result

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        with stage._account(context):
            result = stage._helper(context, "metadata_consumer", consume, (), {})
        assert result is False and calls == [1] and cleanup == ["observed-finally"]
        row = _generator_row(context, produce.__code__)
        assert row["returned"] is True and row["state"] == "unwound"
        assert any(isinstance(record[1], GeneratorExit) for record in row["source_errors"])
        assert row["activation"] == 1 and not context.generator_suspensions
        assert [record[2] for record in context.generator_results] == ["yield", "terminal"]
        assert context.generator_results[0][3] is False
        assert isinstance(context.generator_results[-1][4], GeneratorExit)
        assert context.entry_error is context.observation_error is None and not context.invalid
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        stage._ACTIVE.pop()
        iterator.close()


@pytest.mark.parametrize("unwind", [False, True])
def test_retention_dual_hooks_record_each_mask_return_once_with_raw_bits_and_primary(
    monkeypatch, unwind
):
    calls = []
    primary = ValueError("synthetic mask source failure")
    cause = KeyError("original mask cause")
    primary.__cause__ = cause
    output = np.array([1.0, -0.0])

    def mask(x_new, y_new):
        calls.append((x_new, y_new))
        if unwind:
            raise primary
        return output

    def consume():
        return mask(1, 2)

    context = _protocol_context(monkeypatch, (mask, consume))
    context.mask_codes = frozenset((mask.__code__,))
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        if unwind:
            with pytest.raises(ValueError) as caught:
                with stage._account(context):
                    stage._helper(context, "metadata_mask", consume, (), {})
            assert caught.value is primary and primary.__cause__ is cause
        else:
            with stage._account(context):
                result = stage._helper(context, "metadata_mask", consume, (), {})
            assert result is output
        assert calls == [(1, 2)]
        assert len(context.query_results) == len(context.query_views) == 1
        frame, value, source_error = context.query_results[0]
        assert frame.f_code is mask.__code__
        assert value is (None if unwind else output)
        assert source_error is (primary if unwind else None)
        assert context.query_views[0] is value
        if not unwind:
            assert value.dtype == output.dtype and value.shape == output.shape
            assert value.tobytes() == output.tobytes()
            assert value.view(np.uint64)[1] == 1 << 63
        assert context.entry_error is None
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("first", ["unknown", "yield", "terminal"])
def test_generator_return_reducer_requires_bound_exit_and_companion_is_nonadditive(
    monkeypatch, first
):
    """Isolated reducer metadata; no native frame/owner/body is issued."""
    calls = []

    def produce():
        calls.append("forbidden-body")
        yield True

    context = _entry_context()
    code = produce.__code__
    sites = stage._generator_sites(code)
    yield_offset, terminal_offset = sites[0][0][0], sites[1][0]
    unknown = next(
        instruction.offset
        for instruction in stage.dis.get_instructions(code)
        if instruction.offset not in (yield_offset, *sites[1])
    )
    frame = NS(
        f_code=code,
        f_lasti=unknown
        if first == "unknown"
        else (yield_offset if first == "yield" else terminal_offset),
    )
    row = dict(
        frame=frame,
        activation=0,
        origin_parent=object(),
        body_started=True,
        state="admitted",
        suspension=None,
        source_errors=[],
        exception_unwind_pending=False,
    )
    context.admitted[id(frame)] = row
    context.generator_sites = {code: sites}
    hook = ["trace"]
    monkeypatch.setattr(stage, "_generator_observation", lambda *args: hook[0])
    monkeypatch.setattr(stage, "_helper_value", lambda actual, value: value)
    result = object()
    stage._generator_result(context, frame, result)
    if first == "unknown":
        assert row["state"] == "admitted" and row["pending_return"] is True
        assert not row.get("returned", False) and not context.generator_results
        assert not context.generator_suspensions  # An unknown PC cannot grant resume.
        frame.f_lasti = yield_offset
    else:
        assert len(context.generator_results) == 1
        frame.f_lasti = sites[0][0][1][-1] if first == "yield" else terminal_offset
    hook[0] = "profile"
    if first == "unknown":
        with pytest.raises(stage.LifecycleRejected, match="Unpaired generator observations"):
            stage._generator_result(context, frame, result)
        assert calls == [] and not context.generator_results and not context.generator_suspensions
        assert context.entry_error is not None and context.invalid
        return
    stage._generator_result(context, frame, result)
    token = row.get("suspension")
    for _ in range(2):
        stage._generator_return(context, frame, row)
    assert calls == [] and len(context.generator_results) == 1
    assert len(context.generator_observations) == 2
    assert len(row["return_observations"]) == 2
    assert row["return_claim"]["result"] is result and row.get("suspension") is token
    assert row["state"] == ("returned" if first == "terminal" else "suspended")


def test_generator_interrupted_return_keeps_primary_cause_without_second_logical_exit(monkeypatch):
    context = _entry_context()
    primary = stage.LifecycleRejected("entry", stage="metadata")
    primary.__cause__ = KeyError("original entry cause")

    def produce():
        yield True

    frame = NS(f_code=produce.__code__, f_lasti=0, f_back=None)
    context.generator_sites = {frame.f_code: stage._generator_sites(frame.f_code)}
    row = dict(frame=frame, activation=2, state="admitted", source_error=primary)
    context.admitted[id(frame)] = row
    context.entry_error, context.invalid = primary, True
    monkeypatch.setattr(stage, "_generator_observation", lambda *args: "profile")
    stage._generator_result(context, frame, None)
    assert context.generator_interruptions[0][1] is primary
    assert context.generator_interruptions[0][3] is primary
    assert context.entry_error is primary and primary.__cause__.args == ("original entry cause",)
    assert row["state"] == "admitted" and not context.generator_results


@pytest.mark.parametrize("writer_fails", [False, True])
def test_protocol_journal_writer_runs_under_restored_hooks_and_preserves_primary(
    tmp_path, writer_fails
):
    required = (object(), object())
    actual = [object(), object()]
    operations = []

    def setter(index, value):
        operations.append(index)
        actual[index] = value

    system = NS(
        setprofile=lambda value: setter(0, value),
        settrace=lambda value: setter(1, value),
        getprofile=lambda: actual[0],
        gettrace=lambda: actual[1],
    )
    primary, capture = ValueError("source primary"), OSError("journal writer")
    primary.__cause__ = KeyError("source cause")
    context = _entry_context()
    context.protocol_history = [dict(hook="trace", event="return", activation=0)]
    writes = []

    def writer(path, value):
        assert actual[0] is required[0] and actual[1] is required[1]
        writes.append(value)
        if writer_fails:
            actual[0] = None  # Model the interpreter disabling a rejecting hook.
            raise capture

    scope = dict(globals(), sys=system)
    function = FunctionType(_write_protocol_journal.__code__, scope)
    errors = function(
        [context],
        tmp_path / "isolated-journal.json",
        "isolated-journal",
        required=required,
        primary=primary,
        writer=writer,
    )
    assert len(writes) == 1 and writes[0]["primary_id"] == id(primary)
    assert writes[0]["primary_cause_id"] == id(primary.__cause__)
    assert actual[0] is required[0] and actual[1] is required[1]
    assert operations == [1, 0, 1, 0]
    assert primary.__cause__.args == ("source cause",)
    if writer_fails:
        assert errors[0][2] is capture and _RAW_PROTOCOL_CAPTURE_ERRORS[-1][2] is primary
    else:
        assert errors == ()


def _pair_reducer(monkeypatch):
    """Private metadata reducer, never a supplied native frame/owner issuer."""
    calls = []

    def produce():
        calls.append("forbidden-body")
        yield True
        yield True

    code = produce.__code__
    sites = stage._generator_sites(code)
    assert len(sites[0]) == 2 and len(sites[0][0][1]) == 2
    frame = NS(f_code=code, f_lasti=sites[0][0][0], f_back=None)
    row = dict(
        frame=frame,
        activation=0,
        origin_parent=object(),
        body_started=True,
        state="admitted",
        suspension=None,
        source_errors=[],
        exception_unwind_pending=False,
    )
    context = _entry_context()
    context.admitted[id(frame)] = row
    context.generator_sites = {code: sites}
    hook = ["trace"]
    monkeypatch.setattr(stage, "_generator_observation", lambda *args: hook[0])
    monkeypatch.setattr(stage, "_helper_value", lambda actual, value: value)
    return context, frame, row, hook, calls


@pytest.mark.parametrize("outcome", ["reraised", "suppressed_return", "handled_then_yield"])
def test_generator_exception_exit_sites_distinguish_unwind_from_normal_progress(
    monkeypatch, outcome
):
    calls, cleanup = [], []
    original_error = ValueError("handled source error")

    def selected_helper(value):
        calls.append(value)
        return True

    def produce():
        if outcome == "handled_then_yield":
            try:
                raise original_error
            except ValueError:
                yield selected_helper(1)
            yield selected_helper(2)
            return
        try:
            yield selected_helper(1)
            yield selected_helper(2)
        finally:
            cleanup.append("finally")
            if outcome == "suppressed_return":
                return  # noqa: B012 - this control deliberately tests source suppression.

    iterator = produce()

    def consume():
        if outcome == "handled_then_yield":
            return all(iterator)
        result = next(iterator)
        iterator.close()
        return result

    context = _protocol_context(monkeypatch, (selected_helper, produce, consume))
    required = context.required_hooks
    stage._ACTIVE.append(context)
    try:
        with stage._account(context):
            result = stage._helper(context, "metadata_consumer", consume, (), {})
        assert result is True and context.entry_error is context.observation_error is None
        row = _generator_row(context, produce.__code__)
        assert row["returned"] is True
        assert calls == ([1, 2] if outcome == "handled_then_yield" else [1])
        if outcome == "reraised":
            assert row["state"] == "unwound" and cleanup == ["finally"]
            claim = row["return_claim"]
            assert claim["raise_site"][1] == "RERAISE"
            assert claim["exception_witness"][0] is row["frame"]
            assert claim["exception_witness"][1] is produce.__code__
            assert isinstance(context.generator_results[-1][4], GeneratorExit)
        else:
            assert row["state"] == "returned"
            assert context.generator_results[-1][4] is None
            assert row["return_claim"]["exception_witness"] is None
            assert row["source_errors"]  # Historical exceptions stay retained.
        assert sys.getprofile() is required[0] and sys.gettrace() is required[1]
    finally:
        stage._ACTIVE.pop()
        iterator.close()


@pytest.mark.parametrize("first_site,second_site", [(0, 0), (0, 1), (1, 0), (1, 1)])
def test_generator_bound_yield_resume_pair_has_one_canonical_token_and_two_raw_observations(
    monkeypatch, first_site, second_site
):
    context, frame, row, hook, calls = _pair_reducer(monkeypatch)
    pair = context.generator_sites[frame.f_code][0][0]
    value = object()
    frame.f_lasti = pair[1][first_site]
    stage._generator_result(context, frame, value)
    token = row["suspension"]
    assert len(token) == 7 and token[4] == pair[0]
    assert token[5] == pair[1][first_site] and token[6] is pair
    frame.f_lasti = pair[1][second_site]
    hook[0] = "profile"
    stage._generator_result(context, frame, value)
    stage._generator_return(context, frame, row)
    assert row["suspension"] is token and row["return_claim"]["yield_pair"] is pair
    assert [record[4] for record in row["return_observations"]] == [
        pair[1][first_site],
        pair[1][second_site],
    ]
    assert [entry["decision"] for entry in context.generator_observations] == [
        "logical_exit",
        "companion",
    ]
    assert len(context.generator_results) == 1 and row["state"] == "suspended" and calls == []


@pytest.mark.parametrize(
    "drift",
    [
        "different_pair",
        "different_result",
        "different_frame",
        "different_code",
        "different_activation",
    ],
)
def test_generator_companion_cannot_retarget_canonical_pair_or_claim_identity(monkeypatch, drift):
    context, frame, row, hook, calls = _pair_reducer(monkeypatch)
    pair = context.generator_sites[frame.f_code][0][0]
    result = object()
    stage._generator_result(context, frame, result)
    token = row["suspension"]
    actual, value = frame, result
    if drift == "different_pair":
        actual.f_lasti = context.generator_sites[frame.f_code][0][1][1][-1]
    elif drift == "different_result":
        value = object()
    elif drift == "different_frame":
        actual = NS(f_code=frame.f_code, f_lasti=pair[1][-1], f_back=None)
        context.admitted[id(actual)] = row
    elif drift == "different_code":
        actual.f_code = frame.f_code.replace()
    elif drift == "different_activation":
        row["activation"] += 1
    hook[0] = "profile"
    with pytest.raises(stage.LifecycleRejected) as caught:
        stage._generator_result(context, actual, value)
    assert caught.value is context.entry_error and context.invalid
    assert calls == [] and row["suspension"] is token
    assert len(context.generator_results) == 1
