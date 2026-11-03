"""Written UNRUN metadata controls for genuine post-lifecycle preparation."""

import ast
import os
from contextlib import contextmanager
from threading import get_ident
from types import FunctionType, ModuleType
from types import SimpleNamespace as NS

import numpy as np
import pytest

from cells.processes import betse_native_seed_world_geometry as stage
from tests.unit import test_betse_native_world_phase_construction as controls
from validation.betse import betse_native_seed_world_geometry_software as software

_RAW_GUARD_SCOPES = []


@pytest.fixture(autouse=True)
def blocked(request, tmp_path):
    if os.environ.get(software.SOFTWARE_RELEASE) != "1":
        pytest.skip("Source/static preparation only; blocked software not released")
    request.config.option.maxfail = 1
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


def test_preparation_literal_body_order_stops_before_any_Poisson_callback():
    plan = stage.source_plan()
    assert plan["methods"] == stage.METHODS
    assert plan["stages"] == stage.STAGES
    assert plan["stop_before"] == ("first Poisson callback", "makeLaplacian")
    assert plan["source_pin"] is plan["parent_pin"] is plan["parent_review"] is None
    assert plan["no_late_parameter_or_plot_store"] is True
    assert plan["plot_grid_size_original"] == 50
    assert plan["genuine_preborn_grid_descriptor"] is True
    assert plan["source_native_reference_or_scientific_release"] is False
    assert len(software.OWNED) == len(set(software.OWNED)) == 8
    assert plan["invalidated_owners"] == 11 and plan["held_postcut_cases"] == 12


@pytest.mark.parametrize("entry", ["request", "prepare"])
def test_preparation_pins_refuse_before_any_foreign_owner_or_parameter_read(entry):
    class Foreign:
        def __getattribute__(self, name):
            raise AssertionError("Foreign owner read")

    with pytest.raises(stage.GeometryRejected) as caught:
        if entry == "request":
            stage.from_lifecycle(Foreign(), law_id=stage.LAW_ID)
        else:
            stage.prepare(Foreign(), enabled=True)
    assert caught.value.stage == "unbound_contract"
    assert not stage._ACTIVE and not stage._ISSUED and not stage._GRIDS


@pytest.mark.parametrize("entry", ["constructor", "unissued", "checkpoint"])
def test_preparation_plain_object_or_serialization_is_never_source_authority(entry):
    if entry == "constructor":
        with pytest.raises(TypeError):
            stage.GeometryOwner()
    elif entry == "unissued":
        with pytest.raises(stage.GeometryRejected):
            stage._authority(NS())
    else:
        # A raw allocation cannot even serialize as an executable checkpoint.
        value = object.__new__(stage.GeometryOwner)
        with pytest.raises(TypeError):
            value.__reduce_ex__(4)


def _functions():
    tree = ast.parse((software.ROOT / software.SOURCE).read_bytes())
    return {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef)}


def test_preparation_original_CodeTypes_and_class_surface_are_retained():
    functions = _functions()
    text = ast.unparse(functions["_namespace"])
    assert "FunctionType(fn.__code__" in text
    assert "_source_function(fn, 'betse/science/cells.py'" in text
    assert "_source_function(fn, 'betse/science/math/finitediff.py'" in text
    assert "context.assembly.factories['Cells']" in text
    assert "context.grid_original_type" in text
    invoked = {
        n.func.id if isinstance(n.func, ast.Name) else n.func.attr
        for n in ast.walk(functions["prepare"])
        if isinstance(n, ast.Call) and isinstance(n.func, (ast.Name, ast.Attribute))
    }
    assert not {"setattr", "RandomState", "set_state", "from_lifecycle_ordinary"} & invoked


def test_preparation_actual_constructor_completion_assignment_cell_grid_order():
    functions = _functions()
    factory = ast.unparse(functions["_grid_factory"])
    assert factory.index("context.descriptor_succeeded") < factory.index("object.__new__")
    assert factory.index("grid.__init__()") < factory.index("return grid")
    call = ast.unparse(functions["_grid_call"])
    assert "context.cells.grid_obj is not actual" in call
    assert "context.grid_constructed" in call
    assert call.index("context.raw_grid_results.append") < call.index(
        "_guard(context)", call.index("context.raw_grid_results.append")
    )


def test_preparation_source_roster_has_no_lattice_field_retrofit():
    plan = stage.source_plan()
    assert {"ecm_verts", "cluster_mask", "msize", "ecm_verts_unique", "grid_len"} <= set(
        plan["caller_fields"]
    )
    assert {"mesh", "clust_xy", "xmin", "xmax", "ymin", "ymax"}.isdisjoint(plan["caller_fields"])
    assert set(plan["parameter_reads"]) == {
        "cell_height",
        "cell_space",
        "cell_radius",
        "scale_cell",
        "tm",
        "grid_size",
        "plot_grid_size",
    }
    assert "intra_updater" not in plan["methods"] and "calc_gj_vects" not in plan["methods"]


def test_preparation_core_projection_uses_live_original_fields_not_reconstructed_values():
    functions = _functions()
    source = ast.unparse(functions["_core_values"])
    assert "vars(actual).items()" in source and "k in context.original_names" in source
    assert "context.original_values" not in source and "before.restore" not in source
    checked = ast.unparse(functions["_check_core"])
    assert "vars(obj) is not old" in checked
    assert "_core_values(context).identity != context.core_cache.identity" in checked
    assert "_same(graph[0], context.core_edges[0])" in checked


def test_preparation_native_callbacks_self_only_grid_len_and_mask_bounds_unchanged():
    literal = ast.parse((software.ROOT / software.LITERAL).read_bytes())
    cls = next(n for n in literal.body if isinstance(n, ast.ClassDef))
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "continue_world")
    assert ast.unparse(fn.body[-2]) == "self.grid_len = len(self.xypts)"
    assert ast.unparse(fn.body[-1]) == "self.make_maskM(phase.p)"
    progress = [
        n
        for n in ast.walk(fn)
        if isinstance(n, ast.Call)
        and isinstance(n.func, ast.Attribute)
        and n.func.attr == "progressed_next"
    ]
    assert len(progress) == 3
    assert tuple(n.keywords[0].value.value for n in progress) == stage.CALLBACK_STATUSES


def test_preparation_one_shot_before_any_source_namespace_and_no_child_before_seal():
    functions = _functions()
    text = ast.unparse(functions["prepare"])
    assert text.index(
        "_CONSUMED[request] = _RETIRED[request.lifecycle_owner] = context"
    ) < text.index("_namespace(context)")
    assert text.index("context.parent_claim(") < text.index("context.literal_methods[0](")
    assert text.index("context.trial = replace") < text.index("object.__new__(GeometryOwner)")
    assert "context.pending_source_error" in text and "context.entry_error" in text


def test_preparation_grid_and_tree_roots_are_registered_before_observation():
    functions = _functions()
    grid = ast.unparse(functions["_grid_factory"])
    assert grid.index(
        "context.projector.objects.append(('issued_source_grid', grid))"
    ) < grid.index("grid.__init__()")
    operation = ast.unparse(functions["_operation"])
    assert "context.projector.objects.append(('issued_source_tree', result))" in operation
    assert operation.index("context.issued_trees.append(result)") < operation.index(
        "_record(context, name + '_return', result)"
    )
    graph = ast.unparse(functions["_graph"])
    assert "context.graph_view.issued_roots = context.projector.objects" in graph
    assert "context.graph_view.helper_buffers = context.helper_views" in graph


def test_preparation_geometry_resume_uses_own_guard_without_LC_active_stack():
    functions = _functions()
    admit = ast.unparse(functions["_admit"])
    assert "_resume(context, frame, old)" in admit
    assert "previous._resume(context, frame, old)" not in admit
    namespace = ast.unparse(functions["_namespace"])
    protocol = ast.unparse(functions["_bind_generator_protocol"])
    assert (
        "original_resume.__globals__, _guard=_guard, _reject=_reject, _attempt=_attempt" in protocol
    )
    assert "_bind_generator_protocol(context)" in namespace
    assert "function = FunctionType(" in protocol
    assert "_helper_value=_generator_value" in protocol
    assert "previous._ACTIVE.append" not in namespace
    binding = ast.unparse(functions["_binding"])
    assert "context.resume_delegate.__globals__" in binding


def test_preparation_grid_len_store_has_own_exact_stage_and_terminal_check(monkeypatch):
    frame = object()
    context = NS(
        grid_len_recorded=False,
        cells=NS(grid_len=2, xypts=(1, 2)),
        world_frame=frame,
        completed=list(stage.METHODS[:-1]),
        stages=[],
    )
    cache = NS(identity="metadata-only-cache")
    monkeypatch.setattr(stage, "_snapshot", lambda actual: cache)
    stage._grid_len_boundary(context, frame)
    stage._grid_len_boundary(context, frame)
    assert context.raw_grid_len == 2 and context.grid_len_recorded is True
    assert context.stages == [("grid_len", cache)]
    prepare = ast.unparse(_functions()["prepare"])
    assert "tuple((name for name, _ in context.stages)) != STAGES" in prepare


def test_preparation_actual_literal_grid_methods_and_key_associations_are_bound():
    functions = _functions()
    binding = ast.unparse(functions["_binding"])
    for name in (
        "context.literal_methods",
        "context.grid_bodies",
        "context.grid_namespace",
        "context.methods",
    ):
        assert name in binding
    assert "for key, fn in context.grid_bodies.items()" in binding
    assert "_view_bindings(view)" in binding
    assert "for key, fn in view.wrappers.items()" in ast.unparse(functions["_view_bindings"])
    literal = ast.unparse(functions["_literal_methods"])
    assert "compile(payload" in literal and "fn.__code__ != code" in literal
    assert "fn.__globals__ is not vars(source)" in literal
    assert "fn.__kwdefaults__ is not None" in literal


def test_preparation_blockade_includes_both_actual_literal_modules():
    assert "cells.processes.betse_native_seed_world_geometry_source" in software.FORBIDDEN_MODULES
    assert (
        "cells.processes.betse_native_seed_voronoi_lifecycle_source" in software.FORBIDDEN_MODULES
    )


def test_projection_actual_issued_tree_role_and_full_buffers_survive_metadata_observation(
    monkeypatch,
):
    """Projector-only synthetic value; no owner/phase/grid/source is issued."""

    class MetadataTree:
        def __init__(self):
            self.data = np.array([[1.0, -0.0]])
            self.indices = np.array([0], dtype=np.int64)
            self.mins, self.maxes = self.data[0], self.data[0]

    actual = MetadataTree()
    context = NS(
        active=True,
        invalid=False,
        thread=get_ident(),
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        stage="projection_only",
        request=None,
        trial=None,
        work=[],
        helper_active=False,
        helper_results=[],
        helper_views=[],
        native_namespace={"cKDTree": MetadataTree},
        cells=NS(),
        grid=None,
        issued_trees=[],
        projector=NS(objects=[]),
        graph_view=NS(),
        stable_tape=NS(rng=object(), events=(), draws=(), locals={}),
    )
    monkeypatch.setattr(stage, "_check", lambda value: None)
    monkeypatch.setattr(stage, "_record", lambda *args: None)
    stage._ACTIVE.append(context)
    try:
        assert stage._operation(context, "cKDTree", lambda: actual, (), {}) is actual
        context.cells.points_tree = actual
        cache = stage._snapshot(context)
        graph = stage._graph(context)
        assert cache.identity and any(value is actual for value in graph[0])
        assert context.projector.objects == [("issued_source_tree", actual)]
        assert context.issued_trees == [actual]
        retained = context.helper_views[0][1]
        assert retained["data"] is actual.data and retained["indices"] is actual.indices
        assert retained["data"].tobytes() == actual.data.tobytes()
        assert retained["data"].view(np.uint64)[0, 1] == 1 << 63
        assert retained["mins"].base is actual.data
    finally:
        stage._ACTIVE.pop()


@pytest.mark.parametrize("drift", [None, "same_values_rekeyed", "same_code_new_identity"])
def test_view_key_and_callable_identity_drift_refuses_before_any_helper(drift):
    calls = []

    def first(*args):
        calls.append("first")

    def second(*args):
        calls.append("second")

    module = ModuleType("metadata_numpy_only")
    module.zeros, module.ones = first, second
    view = stage._ModuleView(object(), module, "np", ("zeros", "ones"))
    before = stage._view_bindings(view)
    values = tuple(view.wrappers.values())
    if drift == "same_values_rekeyed":
        view.wrappers.clear()
        view.wrappers.update(zip(("ones", "zeros"), values, strict=True))
        assert tuple(view.wrappers.values()) == values
    elif drift == "same_code_new_identity":
        first.__code__ = first.__code__.replace()
    if drift is None:
        stage._same(stage._view_bindings(view), before)
    else:
        with pytest.raises(ValueError, match="identity"):
            stage._same(stage._view_bindings(view), before)
    assert calls == []


def test_integration_geometry_retirement_is_sticky_and_never_reopens_old_numeric_owner():
    root = software.ROOT / "src/cells/processes"
    lifecycle = ast.parse((root / "betse_native_seed_voronoi_lifecycle.py").read_bytes())
    methods = {node.name: node for node in lifecycle.body if isinstance(node, ast.FunctionDef)}
    claim = ast.unparse(methods["_claim_for_world_geometry"])
    assert claim.index("parent.geometry = transition") < claim.index("_FORWARDED[owner]")
    assert claim.index("_FORWARDED[owner]") < claim.index("_check(parent)")
    route = ast.unparse(methods["_geometry_route"])
    for text in (
        "_ISSUED.get(owner) is not parent",
        "_FORWARDED.get(owner) is not child",
        "module._REQUESTS.get(child.request) is not child.refs",
        "module._CONSUMED.get(child.request) is not child",
        "module._RETIRED.get(owner) is not child",
        "child.refs[1] is not parent.trial",
    ):
        assert text in route
    inherited = ast.unparse(methods["_check_world_geometry_authority"])
    called = {
        node.func.id
        for node in ast.walk(methods["_check_world_geometry_authority"])
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    assert "_check(parent)" in inherited and "_authority" not in called
    assert "_snapshot" not in called
    public = ast.unparse(methods["_authority"])
    assert public.index("owner in _FORWARDED") < public.index("_check(context)")
    for name in ("_wrapper_guard", "_dispatch"):
        text = ast.unparse(methods[name])
        assert text.index("_geometry_route(context)") < text.index("_guard(context)")


def test_integration_original_caller_names_remain_live_and_default_route_stays_separate():
    root = software.ROOT / "src/cells/processes"
    mesh = ast.parse((root / "betse_native_seed_voronoi_mesh.py").read_bytes())
    functions = {node.name: node for node in mesh.body if isinstance(node, ast.FunctionDef)}
    assert "k in original_names" in ast.unparse(functions["_graph"])
    assert "key in context.caller_names" in ast.unparse(functions["_values"])
    check = ast.unparse(functions["_check"])
    assert "geometry is None and fields not in" in check
    assert "_check_fields(geometry)" in check
    prefix = ast.parse((root / "betse_native_seed_world_prefix.py").read_bytes())
    functions = {node.name: node for node in prefix.body if isinstance(node, ast.FunctionDef)}
    for name in ("_mesh_ancestry_values", "_mesh_ancestry_graph"):
        assert "key in evidence.caller_names" in ast.unparse(functions[name])
    assert "_check_fields(geometry)" in ast.unparse(functions["_check_mesh_ancestry"])
    coordinator = ast.parse((root / "betse_native_world_phase_construction.py").read_bytes())
    functions = {node.name: node for node in coordinator.body if isinstance(node, ast.FunctionDef)}
    assert "_geometry_route(lifecycle)" in ast.unparse(functions["_world_geometry_context"])
    loader = ast.unparse(functions["_world_seed_geometry_api"])
    assert "_world_voronoi_lifecycle_api()" in loader and "_import_bound(" in loader
    assert "geometry.plan['caller_fields']" in ast.unparse(functions["_world_cells_omissions"])


@pytest.mark.parametrize("name", ["cKDTree", "gaussian_filter"])
@pytest.mark.parametrize(
    "drift",
    [
        None,
        "wrapper_code",
        "delegate_code",
        "delegate_cell",
        "defaults",
        "keyword_defaults",
        "wrapped",
    ],
)
def test_global_namespace_wrapper_retargets_refuse_before_any_foreign_delegate(name, drift):
    calls = []

    def delegate(*args, **kwargs):
        calls.append("original")

    def foreign(*args, **kwargs):
        calls.append("foreign")

    wrapper = stage._helper_wrapper(object(), name, delegate)
    namespace = {name: wrapper}
    before = stage._global_wrapper_bindings(namespace)
    code = wrapper.__code__
    if drift == "wrapper_code":
        wrapper.__code__ = code.replace()
        assert wrapper.__code__ == code and wrapper.__code__ is not code
    elif drift == "delegate_code":
        delegate.__code__ = delegate.__code__.replace()
    elif drift == "delegate_cell":
        cell = next(cell for cell in wrapper.__closure__ if cell.cell_contents is delegate)
        cell.cell_contents = foreign
    elif drift == "defaults":
        wrapper.__defaults__ = (foreign,)
    elif drift == "keyword_defaults":
        wrapper.__kwdefaults__ = dict(hidden=foreign)
    elif drift == "wrapped":
        wrapper.__wrapped__ = foreign
    assert namespace[name] is wrapper  # Every outer namespace identity is unchanged.
    if drift is None:
        stage._same(stage._global_wrapper_bindings(namespace), before)
    else:
        with pytest.raises(ValueError, match="identity"):
            stage._same(stage._global_wrapper_bindings(namespace), before)
    assert calls == []
    binding = ast.unparse(_functions()["_binding"])
    assert "_global_wrapper_bindings(context.namespace)" in binding


@pytest.mark.parametrize("phase", ["yield", "terminal"])
@pytest.mark.parametrize("scalar", [True, 0.125, -0.0])
def test_geometry_private_protocol_projects_scalar_returns_without_mesh_globals(phase, scalar):
    """Private reducer-only metadata; no actual frame/body or owner is admitted."""
    calls = []

    class NeverConstructTree:
        def __init__(self):
            calls.append("forbidden-tree")

    def produce():
        calls.append("forbidden-body")
        yield scalar

    code = produce.__code__
    sites = stage.previous._generator_sites(code)
    offset = sites[0][0][0] if phase == "yield" else sites[1][0]
    frame = NS(f_code=code, f_lasti=offset)
    row = dict(
        frame=frame,
        state="admitted",
        body_started=True,
        activation=0,
        origin_parent=object(),
        source_errors=[],
        exception_unwind_pending=False,
    )
    namespace = {"cKDTree": NeverConstructTree}  # Actual Cells has no Delaunay export.
    context = NS(
        native_namespace=namespace,
        projector=NS(objects=[]),
        admitted={id(frame): row},
        generator_sites={code: sites},
        generator_observations=[],
        generator_interruptions=[],
        generator_results=[],
        generator_views=[],
        generator_suspensions={},
        entry_error=None,
        observation_error=None,
        capture_errors=(),
        work=[],
    )
    stage._bind_generator_protocol(context)
    # Isolate the reducer from actual admission: this stub issues no native
    # frame/epoch and the real owner/entry APIs are never called.
    context.protocol_scope["_generator_observation"] = lambda *args: "trace"
    assert context.protocol_scope["_helper_value"] is stage._generator_value
    assert context.protocol_scope["_generator_return"] is context.generator_return_delegate
    assert context.resume_delegate.__globals__ is context.protocol_scope
    assert context.generator_result_delegate.__globals__ is context.protocol_scope
    assert context.generator_return_delegate.__globals__ is context.protocol_scope
    original_projector = stage.previous._helper_value
    # Calling the real mesh projector on this context would fail even with a
    # scalar. It stays unchanged; only the private geometry scope is selected.
    context.generator_result_delegate(context, frame, scalar)
    assert calls == [] and "Delaunay" not in namespace and len(namespace) == 1
    assert context.generator_results[0][3] is scalar
    observed = context.generator_views[0]
    assert type(observed) is type(scalar) and observed == scalar
    assert np.asarray(observed).tobytes() == np.asarray(scalar).tobytes()
    assert context.generator_result_delegate.__code__ is stage.previous._generator_result.__code__
    assert context.protocol_scope["_helper_value"] is not original_projector
    assert row["state"] == ("suspended" if phase == "yield" else "returned")
