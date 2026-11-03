"""Written UNRUN metadata controls; no stand-in supplies a phase or mesh owner."""

import ast
import os
from contextlib import contextmanager
from threading import get_ident
from types import FunctionType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_voronoi_mesh as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_voronoi_mesh_software as software

_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Source preparation only; no blocked-software release")
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


def test_preparation_literal_and_exact_constructor_stop_are_source_bound():
    plan = stage.source_plan()
    assert plan["mode"] == stage.MODE
    assert plan["allowed_caller_stores"] == ("mesh",)
    assert plan["stop_before"] == ("init_mesh", "clip_and_refine")
    assert plan["source_pin"] is plan["parent_pin"] is plan["parent_review"] is None
    assert plan["parent_hook_adoption"] is False
    assert plan["source_lifecycle_operator_or_scientific_release"] is False
    assert plan["constructor_helpers"] == ("__init__", "make_single_cell_points")


def test_preparation_exact_eight_paths_and_no_lifecycle_or_caller_tail():
    assert len(software.OWNED) == len(set(software.OWNED)) == 8
    tree = ast.parse((software.ROOT / software.LITERAL).read_bytes())
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef))
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef))
    calls = [n for n in ast.walk(method) if isinstance(n, ast.Call)]
    assert len(calls) == 3 and all(
        isinstance(n.func, ast.Name) and n.func.id == "DECMesh" for n in calls
    )
    text = ast.unparse(method)
    assert "self.mesh = DECMesh" in text
    assert "phase.p.cell_radius" in text and "seed_points=self.clust_xy" in text
    assert "init_mesh" not in text and "clip_and_refine" not in text and "cell_index" not in text
    assert "RandomState" not in text and "SimpleNamespace" not in text


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_preparation_unadopted_hooks_refuse_before_foreign_owner_or_parameter_read(
    monkeypatch, entry
):
    class Unavailable:
        def __getattribute__(self, name):
            raise AssertionError("Unadopted owner/descriptor cannot be inspected")

    monkeypatch.setenv(stage.RELEASE, "1")
    with pytest.raises(stage.MeshConstructionRejected) as caught:
        if entry == "request":
            stage.from_image(Unavailable(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Unavailable(), enabled=True)
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._ISSUED and not stage._MESHES


@pytest.mark.parametrize("entry", ["constructor", "unissued", "literal"])
def test_preparation_no_plain_object_or_literal_grants_live_constructor_authority(entry):
    if entry == "constructor":
        with pytest.raises(TypeError):
            stage.MeshConstructorOwner()
    elif entry == "unissued":
        with pytest.raises(stage.MeshConstructionRejected) as caught:
            stage._authority(object())
        assert caught.value.stage == "owner"
    else:
        with pytest.raises(ValueError, match="Pinned constructor-prefix"):
            stage._literal_code()


def _entry_context():
    return NS(
        work=[],
        invalid=False,
        active=True,
        thread=get_ident(),
        stage="metadata",
        request=None,
        trial=None,
        entry_error=None,
        observation_error=None,
        admitted={},
        body_codes={},
        mesh=object(),
        constructor_claimed=False,
        points_claimed=False,
        constructor_dispatch_frame=object(),
        constructor_frame=object(),
    )


@pytest.mark.parametrize(
    "name", ["init_mesh", "clip_and_refine", "create_core_operators", "make_single_cell_points"]
)
def test_entry_inactive_raw_mesh_surface_refuses_before_any_delegate(name):
    context = _entry_context()
    context.active = False
    calls = []
    with pytest.raises(stage.MeshConstructionRejected):
        stage._invoke_mesh(
            context, name, lambda *a: calls.append(name), context.mesh, (), {}, object()
        )
    assert calls == [] and context.invalid and len(context.work) == 2
    assert context.work[-1]["state"] == "rejected"
    assert context.entry_error is not None


@pytest.mark.parametrize("method", ["__init__", "make_single_cell_points"])
def test_entry_same_method_reentry_has_sticky_claim_and_no_body_calls(method):
    context = _entry_context()
    code = object()
    context.body_codes[code] = "mesh_method_wrapper"
    parent = (
        context.constructor_dispatch_frame if method == "__init__" else context.constructor_frame
    )
    first = NS(f_code=code, f_back=parent, f_locals={"name": method, "actual": context.mesh})
    second = NS(f_code=code, f_back=parent, f_locals={"name": method, "actual": context.mesh})
    stage._ACTIVE.append(context)
    try:
        stage._admit(context, first)
        assert context.work[0]["state"] == "admitted" and not context.work[0]["body_started"]
        with pytest.raises(stage.MeshConstructionRejected) as caught:
            stage._admit(context, second)
        assert caught.value is context.entry_error
        assert context.invalid and context.work[-1]["state"] == "rejected"
        with pytest.raises(stage.MeshConstructionRejected) as sticky:
            stage._guard(context)
        assert sticky.value is caught.value
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("label", ["forbidden_native_mesh_method", "global_MT_random_wrapper"])
def test_entry_direct_or_next_helper_attempt_is_recorded_before_refusal(label):
    context = _entry_context()
    code = object()
    context.body_codes[code] = label
    context.points_frame, context.draw_claims = object(), 0
    context.numpy_view = NS(random=object())
    frame = NS(f_code=code, f_back=None, f_locals={"self": context.numpy_view.random})
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.MeshConstructionRejected):
            stage._admit(context, frame)
        assert context.work[0]["frame"] is frame and context.work[0]["state"] == "rejected"
        assert context.draw_claims == 0 and context.invalid
    finally:
        stage._ACTIVE.pop()


def _graph_context():
    a, b = np.zeros((2, 2)), np.zeros((2, 2))
    caller = NS(first=a, second=b, edge=a)
    objects = (("caller", caller),)
    fields = [{}]
    return NS(
        cells=caller,
        objects=objects,
        stable_fields=fields,
        stable_view=NS(objects=objects, fields=fields),
        stable_tape=NS(rng=object(), events=(), draws=(), locals={}),
        locals={},
        events=[],
        work=[],
    )


def test_graph_equal_already_retained_array_edge_retarget_is_nonvacuously_visible():
    context = _graph_context()
    old = stage._graph(context)
    context.cells.edge = context.cells.second
    new = stage._graph(context)
    assert np.array_equal(context.cells.first, context.cells.second)
    assert len(old[0]) == len(new[0]) and all(a is b for a, b in zip(old[0], new[0], strict=True))
    assert old[1] != new[1]


def test_graph_observation_growth_does_not_change_stable_inherited_baseline():
    context = _graph_context()
    old = stage._graph(context)
    context.events.append(("return", object()))
    context.locals["frame"] = object()
    context.work.append({"state": "returned"})
    new = stage._graph(context)
    assert old[1] == new[1]
    assert all(a is b for a, b in zip(old[0], new[0], strict=True))


@pytest.mark.parametrize("boundary", ["constructor", "root"])
def test_graph_private_helper_namespace_retarget_changes_binding_without_body_execution(boundary):
    calls = []

    def unused():
        calls.append("body")

    tree = FunctionType(unused.__code__, {"calls": calls}, closure=unused.__closure__)
    constructor_scope = {"np": object(), "cKDTree": tree}
    root_scope = {"DECMesh": tree}
    context = NS(
        mesh_bodies={
            "__init__": FunctionType(unused.__code__, constructor_scope, closure=unused.__closure__)
        },
        method=FunctionType(unused.__code__, root_scope, closure=unused.__closure__),
    )
    before = stage._namespace_bindings(context)
    if boundary == "constructor":
        constructor_scope["np"] = object()
    else:
        root_scope["DECMesh"] = object()
    after = stage._namespace_bindings(context)
    assert calls == [] and len(before) == len(after)
    assert any(a is not b for a, b in zip(before, after, strict=True))


@pytest.mark.parametrize("boundary", ["complete", "constructor_unreturned", "assignment_retarget"])
def test_retention_assignment_marker_requires_original_completed_constructor_and_reference(
    boundary,
):
    def unexecuted():
        raise AssertionError("Metadata code object must never execute")

    code, mesh, parent = unexecuted.__code__, object(), object()
    caller = NS(mesh=mesh if boundary != "assignment_retarget" else object())
    frame = NS(f_code=code, f_locals={"self": caller}, f_back=parent)
    row = {"frame": frame, "state": "admitted"}
    context = NS(
        body_codes={code: stage.ROOT},
        admitted={id(frame): row},
        locals={},
        constructor_returned=boundary != "constructor_unreturned",
        mesh=mesh,
        cells=caller,
        assignment_completed=False,
        order=[],
    )
    if boundary == "complete":
        stage._capture(context, frame, "return")
        assert context.assignment_completed and context.order == ["exact_caller_mesh_assigned"]
    else:
        with pytest.raises(ValueError, match="completion/assignment"):
            stage._capture(context, frame, "return")
        assert not context.assignment_completed and context.order == []
    assert context.last_frame is frame and context.last_raw_locals["self"] is caller


@pytest.mark.parametrize("stage_name", ["constructor", "caller_assignment"])
def test_retention_failed_prefix_partial_retains_original_parents_and_actual_raw_mesh(stage_name):
    raw_parent, raw_trial, phase, p, caller, mesh, mask = (object() for _ in range(7))
    refs = (raw_parent, raw_trial, phase, p, caller, object(), mask)
    primary = ValueError("original " + stage_name)
    context = NS(
        request=None,
        parent=raw_parent,
        refs=refs,
        phase=phase,
        p=p,
        cells=caller,
        mesh=mesh,
        locals={},
        work=[],
        events=[],
        caught=[],
        primary=primary,
        capture_errors=(),
        cleanup_errors=(),
        trial=None,
    )
    partial = stage._partial(context)
    assert partial["image_parent"] is raw_parent and partial["image_trial"] is raw_trial
    assert partial["phase"] is phase and partial["parameters"] is p
    assert partial["caller"] is caller and partial["mesh"] is mesh
    assert partial["actual_image_mask"] is mask and partial["primary"] is primary
    assert partial["trial"] is None and not stage._ISSUED


@pytest.mark.parametrize("failed", [None, 0, 1])
def test_retention_cleanup_attempts_both_required_hooks_without_real_installation(failed):
    required, actual, calls = (object(), object()), [None, None], []
    original = OSError("restore")

    def setter(index):
        def set_value(value):
            calls.append(index)
            if index == failed:
                raise original
            actual[index] = value

        return set_value

    context = NS(
        required_hooks=required,
        restore_setters=(setter(0), setter(1)),
        restore_getters=(lambda: actual[0], lambda: actual[1]),
        cleanup_errors=(),
        observation_error=None,
    )
    assert stage._recover(context) is (failed is None)
    assert calls == [1, 0, 1, 0]
    if failed is not None:
        assert context.observation_error is original


@pytest.mark.parametrize("secondary", ["partial", "exception"])
def test_retention_falsey_primary_and_cause_survive_failed_failure_capture(secondary):
    class Falsey(ValueError):
        def __bool__(self):
            return False

    cause, primary, capture = KeyError("cause"), Falsey("native"), OSError("capture")
    primary.__cause__ = cause
    context = NS(invalid=False, stage="constructor", request=None, trial=None, capture_errors=())

    def fail(*args, **kwargs):
        raise capture

    scope = dict(stage.__dict__)
    scope["_partial"] = fail
    if secondary == "exception":
        scope["MeshConstructionRejected"] = fail
    failure = FunctionType(stage._failure.__code__, scope)
    expected = stage.MeshConstructionRejected if secondary == "partial" else Falsey
    with pytest.raises(expected) as caught:
        failure(context, primary, None)
    if secondary == "partial":
        assert caught.value.source_error is primary and caught.value.capture_error is capture
        assert caught.value.__cause__ is primary and caught.value.partial is context
    else:
        assert caught.value is primary
    assert primary.__cause__ is cause and context.invalid and context.capture_errors


def _integration_functions(relative):
    tree = ast.parse((software.ROOT / relative).read_bytes())
    return tree, {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_integration_mesh_provider_and_all_adoption_pins_stay_closed():
    relative = "src/cells/processes/betse_native_world_phase_construction.py"
    tree, functions = _integration_functions(relative)
    for name in ("VORONOI_MESH_SOURCE_SHA256", "VORONOI_MESH_REVIEW_SHA256"):
        value = next(
            n.value
            for n in tree.body
            if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == name for t in n.targets)
        )
        assert isinstance(value, ast.Constant) and value.value is None
    provider = ast.unparse(functions["_world_voronoi_mesh_api"])
    assert "_world_voronoi_api()" in provider
    assert "module.DISPATCH_LABEL != 'Cells.make_voronoi'" in provider
    assert "_wrapper_guard" in provider and "_dispatch" in provider
    assert stage.SOURCE_SHA256 is stage.PARENT_SOURCE_SHA256 is stage.PARENT_REVIEW_SHA256 is None


def test_integration_only_authenticated_downstream_projection_omits_mesh():
    _, functions = _integration_functions(
        "src/cells/processes/betse_native_world_phase_construction.py"
    )
    selector = ast.unparse(functions["_world_cells_omissions"])
    assert "_world_forwarded(transition)" in selector and "_mesh_route(parent)" in selector
    assert "prefix.cells is not cells" in selector and "route.cells is not cells" in selector
    assert selector.index("_mesh_route(parent)") < selector.index("omitted += ('mesh',)")
    _, prefix = _integration_functions("src/cells/processes/betse_native_seed_world_prefix.py")
    stable = ast.unparse(prefix["_check_mesh_ancestry"])
    assert "_check_ancestry(parent)" in stable and "holder_dicts" in stable
    assert (
        "_mesh_ancestry_values(evidence)" in stable and "_mesh_ancestry_graph(evidence)" in stable
    )
    assert "_check_sealed(" not in stable and "_validate(" not in stable
    assert "_rng_state(" not in stable and "expected_rng" not in stable
    legacy = ast.unparse(prefix["_check"])
    assert "_rng_state(context).identity != context.expected_rng.identity" in legacy
    assert "STORES[:len(added)]" in legacy


def test_integration_image_retirement_marker_precedes_capture_and_public_owner_refuses():
    _, functions = _integration_functions("src/cells/processes/betse_native_seed_voronoi_image.py")
    claim = ast.unparse(functions["_claim_for_voronoi_mesh"])
    assert claim.index("parent.voronoi_mesh = transition") < claim.index("_FORWARDED[owner]")
    assert claim.index("_FORWARDED[owner]") < claim.index(
        "_capture_mesh_ancestry(parent, transition)"
    )
    assert "_CONSUMED.get(transition.request) is not transition" in claim
    assert "_RETIRED.get(owner) is not transition" in claim
    public = ast.unparse(functions["_authority"])
    assert "owner in _FORWARDED or hasattr(context, 'voronoi_mesh')" in public
    ancestry = ast.unparse(functions["_check_mesh_authority"])
    assert "_check_mesh_ancestry(parent, transition)" in ancestry
    assert "_check_image_bindings(parent)" in ancestry and "_check_image_seal(parent)" in ancestry
    invoked = {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(functions["_check_mesh_authority"])
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }
    assert "_authority" not in invoked and "_check_voronoi_authority" not in invoked


def test_integration_full_dispatch_abi_and_original_frame_guards_match_existing_tail():
    tree = ast.parse((software.ROOT / software.SOURCE).read_bytes())
    functions = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}
    assert [a.arg for a in functions["_dispatch"].args.args] == [
        "context",
        "original",
        "label",
        "delegate",
        "actual",
        "args",
        "kwargs",
        "dispatch_frame",
    ]
    text = ast.unparse(functions["_dispatch"])
    assert "caller is not dispatch_frame" in text and "_dispatch_seed_world.__code__" in text
    assert "native_call_code" in text and "wrapper.f_back is not context.driver_frame" in text
    assert "delegate is not context.native_method" in text and "label != DISPATCH_LABEL" in text
    assert text.index("context.root_claimed = True") < text.index(
        "context.method(actual, context.phase)"
    )
    assert text.index("context.raw_root_result = result") < text.index(
        "'constructor_prefix_return'"
    )
    _, tail = _integration_functions("src/cells/processes/betse_native_phase_tail.py")
    route = ast.unparse(tail["_dispatch_seed_world"])
    assert "_mesh_route(context)" in route and "_world_voronoi_mesh_api()._dispatch(" in route


@pytest.mark.parametrize(
    "entry", ["guard_unready", "guard_raw", "dispatch_unready", "dispatch_raw"]
)
def test_integration_unready_or_raw_wrapper_dispatch_refuses_without_body(entry):
    context = _entry_context()
    context.source_ready = entry.endswith("raw")
    stage._ACTIVE.append(context)
    try:
        with pytest.raises(stage.MeshConstructionRejected):
            if entry.startswith("guard"):
                stage._wrapper_guard(context, object(), object())
            else:
                stage._dispatch(
                    context, object(), stage.DISPATCH_LABEL, object(), object(), (), {}, object()
                )
        assert context.invalid and context.entry_error is not None
        assert context.work[-1]["state"] == "rejected"
        assert not stage._MESHES and not stage._ISSUED
    finally:
        stage._ACTIVE.pop()
