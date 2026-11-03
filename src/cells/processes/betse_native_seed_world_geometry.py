"""Prepared actual SEED caller aliases, ordinary geometry, grid and mask.

Only an actually issued native lifecycle child may continue. All producer and
hook adoption remains closed. No normalized multi/single owner, supplied phase,
grid, parameter projection or saved cache is an executable parent. The source
boundary stops before the first Poisson callback/construction.
"""

import ast
import hashlib
import os
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_seed_voronoi_lifecycle as previous
from cells.processes import betse_native_seed_world_geometry_source as source

MODE = "fresh_seed_same_caller_geometry_grid_mask"
LAW_ID = "betse_same_seed_native_caller_through_make_maskM@1"
RELEASE = "CELLS_NATIVE_SEED_WORLD_GEOMETRY_RELEASED"
SOURCE_SHA256 = "178af651cd36274ddaae81d36ae8ff70cb8a585b5abe747a35d659a8eb983abc"
PARENT_SOURCE_SHA256 = "2ad275b33cd123f0cf266d262dcee5609924b72a91c6c8b86328bed1116eac1e"
PARENT_REVIEW_SHA256 = "aa5cddf4c36998d3a99bcc576af94ba6fb4993c020de402bdd6ae8b134613f6e"
PARENT_MODULE = "cells.processes.betse_native_seed_voronoi_lifecycle"
METHODS = (
    "cell_index",
    "cellVerts",
    "cellMatrices",
    "cell_vols",
    "mem_processing",
    "near_neigh",
    "makeECM",
    "environment",
    "make_maskM",
)
STAGES = (
    "four_aliases",
    "cell_index",
    "cellVerts",
    "cellMatrices",
    "cell_vols",
    "mem_processing",
    "near_neigh",
    "makeECM",
    "environment",
    "grid_len",
    "make_maskM",
)
PARAMETERS = (
    "cell_height",
    "cell_space",
    "cell_radius",
    "scale_cell",
    "tm",
    "grid_size",
    "plot_grid_size",
)
CALLBACK_STATUSES = (
    "Calculating geometric cell properties...",
    "Calculating geometric cell volumes...",
    "Creating extracellular matrix (ECM) grid...",
)
GLOBAL_HELPERS = ("cKDTree", "gaussian_filter")
PROPOSED_CLAIM = "_claim_for_world_geometry"
PROPOSED_CHECK = "_check_world_geometry_authority"
PROPOSED_ROUTER = "_world_seed_geometry_api"
MAX_WORK = previous.MAX_WORK
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED, _GRIDS = (WeakKeyDictionary() for _ in range(5))
_FORWARDED = WeakKeyDictionary()
_ACTIVE, _LOCK = [], RLock()
_LITERAL_FILE, _PARENT_FILE = Path(source.__file__), Path(previous.__file__)
_LITERAL_CLASS = source.SeedWorldGeometry
_LITERAL_FUNCTIONS = tuple(vars(_LITERAL_CLASS)[n] for n in ("finish_voronoi", "continue_world"))
_BASE = previous.previous  # Constructor driver, read-only shared metadata/observer infrastructure.


class GeometryRejected(previous.LifecycleRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    lifecycle_owner: object
    parent_identity: str
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A real process-local lifecycle owner is required")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stage_caches: tuple
    stream_before: object
    stream_after: object
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    source_failure: str | None
    capture_failure: str | None
    identity: str


def _digest(value):
    return previous._digest(value)


def _same(actual, expected):
    previous._same(actual, expected)


def _atoms(value):
    return previous._atoms(value)


def _bootstrap(context):
    fn, code, namespace = context.checker
    if (
        context.api._independent_atoms is not fn
        or fn.__code__ is not code
        or fn.__globals__ is not namespace
    ):
        raise ValueError("Original independent geometry binding checker changed")
    for name, helper, retained in context.metadata_helpers:
        if globals()[name] is not helper:
            raise ValueError("Geometry metadata helper was replaced: " + name)
        _same(fn(helper), retained)


def _source_methods():
    root = _BASE.image.prefix.aliases.NATIVE
    cells, grid = root / "betse/science/cells.py", root / "betse/science/math/finitediff.py"
    for path, pin in ((cells, source.CELLS_SHA256), (grid, source.GRID_SHA256)):
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Original geometry/grid source changed")
    return previous._nodes(cells, "Cells"), previous._nodes(grid, "FiniteDiffSolver")


def _field_names(node):
    return tuple(
        dict.fromkeys(
            n.attr
            for n in ast.walk(node)
            if isinstance(n, ast.Attribute)
            and isinstance(n.ctx, ast.Store)
            and isinstance(n.value, ast.Name)
            and n.value.id == "self"
        )
    )


def source_plan():
    cells, grid = _source_methods()
    aliases = previous.previous._body(cells["make_voronoi"])[6:]
    # The exact four stores are source statements after the constructor branch.
    aliases = [n for n in aliases if isinstance(n, ast.Assign)]
    copied = previous._nodes(_LITERAL_FILE, "SeedWorldGeometry")
    ordinary = previous.previous._body(cells["make_world"])[4:17]
    for name, expected in (("finish_voronoi", aliases), ("continue_world", ordinary)):
        if ast.dump(
            ast.Module(body=expected, type_ignores=[]), include_attributes=False
        ) != ast.dump(
            ast.Module(body=previous.previous._body(copied[name]), type_ignores=[]),
            include_attributes=False,
        ):
            raise ValueError("Original post-lifecycle source order changed: " + name)
    fields = tuple(
        dict.fromkeys(
            (
                "ecm_verts",
                "cluster_mask",
                "msize",
                "ecm_verts_unique",
                *(f for name in METHODS for f in _field_names(cells[name])),
                "grid_len",
            )
        )
    )
    lattice = set(_field_names(cells["_make_cell_lattice"]))
    if lattice.intersection(fields):
        raise ValueError("An existing lattice field needs a separate explicit mutation proof")
    return dict(
        law=LAW_ID,
        mode=MODE,
        source_pin=SOURCE_SHA256,
        parent_pin=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        parent=PARENT_MODULE,
        original_cells=source.CELLS_SHA256,
        original_grid=source.GRID_SHA256,
        methods=METHODS,
        stages=STAGES,
        caller_fields=fields,
        native_store_rosters={name: _field_names(cells[name]) for name in METHODS},
        grid_methods=("__init__", "cell_grid"),
        grid_stores=_field_names(grid["cell_grid"]),
        parameter_reads=PARAMETERS,
        genuine_preborn_grid_descriptor=True,
        no_late_parameter_or_plot_store=True,
        plot_grid_size_original=50,
        callbacks=CALLBACK_STATUSES,
        actual_same_objects=True,
        ancestor_projection="original captured caller-name subset; no substituted old values",
        parent_hooks={
            PROPOSED_CLAIM: "(owner, expected, transition, entries)",
            PROPOSED_CHECK: "(transition) -> actual parent; factored immutable ancestry",
        },
        caller_field_projection_requires_actual_typed_retirement=True,
        stop_before=("first Poisson callback", "makeLaplacian"),
        normalized_owner_or_checkpoint_or_physical_admission=False,
        source_native_reference_or_scientific_release=False,
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _ready():
    if not all(
        type(v) is str and len(v) == 64 and all(c in "0123456789abcdef" for c in v)
        for v in (SOURCE_SHA256, PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise GeometryRejected(
            "Geometry/lifecycle producer adoption held", stage="unbound_contract"
        )
    for module, path, pin in (
        (source, _LITERAL_FILE, SOURCE_SHA256),
        (previous, _PARENT_FILE, PARENT_SOURCE_SHA256),
    ):
        if (
            Path(module.__file__) != path
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != pin
        ):
            raise GeometryRejected("Exact reviewed source producer required", stage="producer")
    api = previous._ready()
    loader = getattr(api, PROPOSED_ROUTER, None)
    if loader is None or loader() is not sys.modules.get(__name__):
        raise GeometryRejected(
            "Original same-instance geometry dispatch is unavailable", stage="dispatch_held"
        )
    if any(
        type(getattr(previous, n, None)) is not FunctionType
        for n in (PROPOSED_CLAIM, PROPOSED_CHECK)
    ):
        raise GeometryRejected(
            "Actual lifecycle retirement/factored hooks unavailable", stage="parent_hooks_held"
        )
    return api


def request_record(value):
    return dict(
        law=LAW_ID, mode=value.mode, parent=value.parent_identity, source=value.source_identity
    )


def from_lifecycle(owner, *, law_id, mode=MODE):
    _ready()
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise GeometryRejected("Exact fresh same-caller geometry mode required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant geometry request")
    if owner in _RETIRED:
        raise GeometryRejected("Lifecycle geometry epoch consumed", stage="consumed")
    parent = previous._authority(owner)
    value = Request(owner, parent.trial.identity, _digest(source_plan()), mode, "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (parent, parent.trial, previous._epoch(parent))
    return value


def _attempt(context, name, frame, layer):
    return previous._attempt(context, name, frame, layer)


def _reject(context, row, reason):
    return previous._reject(context, row, reason)


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise _BASE.image.prefix.literal._CaptureStop() from context.observation_error
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, None, "Same-caller geometry requires its actual active epoch")


def _capture_failure(context, error, origin, raw):
    return previous._capture_failure(context, error, origin, raw)


def _rng(context):
    return previous._rng(context)


def _project(context, value):
    return _BASE.image.prefix.literal._project(context.projector, value)


def _values(context):
    return dict(
        caller=_project(context, vars(context.cells)),
        grid=None if context.grid is None else _project(context, vars(context.grid)),
    )


def _snapshot(context):
    return _BASE.image.images.core.caches.snapshot(_values(context))


def _graph(context):
    context.graph_view.caller = vars(context.cells)
    context.graph_view.grid = None if context.grid is None else vars(context.grid)
    context.graph_view.issued_roots = context.projector.objects
    context.graph_view.helper_buffers = context.helper_views
    return _BASE.image.prefix.literal.callers._graph(
        context.graph_view, context.graph_view, context.stable_tape
    )


def _epoch(context):
    helpers = _BASE.image.images.core.caches.snapshot(context.helper_views)
    return (_snapshot(context).identity, helpers.identity), _graph(context), _rng(context).identity


def _same_epoch(context, expected):
    current = _epoch(context)
    _same(current[1][0], expected[1][0])
    if current[0] != expected[0] or current[1][1] != expected[1][1] or current[2] != expected[2]:
        raise ValueError("Observer changed original caller/grid/reference/global-MT state")


def _check_fields(context):
    """Registry-only field permission, usable by factored ancestors without recursion."""
    _bootstrap(context)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.lifecycle_owner) is not context
        or context.invalid
        or context.cells is not context.parent.cells
        or context.phase.cells is not context.cells
    ):
        raise ValueError("Actual geometry retirement/Cells link changed")
    fields = tuple(vars(context.cells))
    if hasattr(context, "poisson"):
        child, module = _poisson_route(context)
        module._check_fields(child)
        return fields
    old = context.original_names
    if fields[: len(old)] != old or any(
        name not in context.plan["caller_fields"] for name in fields[len(old) :]
    ):
        raise ValueError("Source caller fields escaped their exact original store roster")
    return fields


def _core_values(context):
    return _BASE.image.images.core.caches.snapshot(
        [
            dict(
                role=role,
                fields=_project(
                    context,
                    {
                        k: v
                        for k, v in context.api._world_sim_fields(context, actual).items()
                        if actual is not context.cells or k in context.original_names
                    },
                ),
            )
            for role, actual in context.objects
        ]
    )


def _core_graph(context):
    for target, (_, actual) in zip(context.core_fields, context.objects, strict=True):
        target.clear()
        target.update(
            {
                k: v
                for k, v in context.api._world_sim_fields(context, actual).items()
                if actual is not context.cells or k in context.original_names
            }
        )
    return _BASE.image.prefix.literal.callers._graph(
        context.core_view, context.core_view, context.stable_tape
    )


def _check_core(context):
    _check_fields(context)
    if any(
        vars(obj) is not old for (_, obj), old in zip(context.objects, context.holders, strict=True)
    ):
        raise ValueError("Original holder dictionary replaced")
    if _core_values(context).identity != context.core_cache.identity:
        raise ValueError("Unchanged original caller/phase/p fields drifted")
    graph = _core_graph(context)
    _same(graph[0], context.core_edges[0])
    if graph[1] != context.core_edges[1]:
        raise ValueError("Original inherited reference edges changed")


def _binding(context):
    _bootstrap(context)
    return tuple(
        atom
        for fn in (
            *context.original_methods.values(),
            *context.methods.values(),
            context.grid_init,
            context.grid_method,
            context.grid_factory,
            context.callback,
            context.descriptor_getter,
        )
        for atom in _atoms(fn)
    ) + (
        MODE,
        LAW_ID,
        RELEASE,
        SOURCE_SHA256,
        PARENT_SOURCE_SHA256,
        PARENT_REVIEW_SHA256,
        METHODS,
        STAGES,
        PARAMETERS,
        CALLBACK_STATUSES,
        GLOBAL_HELPERS,
        MAX_WORK,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _FORWARDED,
        _GRIDS,
        _ACTIVE,
        _LOCK,
        context.parent_claim,
        *_atoms(context.parent_claim),
        context.parent_check,
        *_atoms(context.parent_check),
        context.entries,
        *(atom for pair in context.entries.items() for atom in pair),
        context.original_cells_type,
        *_BASE.image.prefix.literal._surface(context.original_cells_type),
        context.grid_original_type,
        *_BASE.image.prefix.literal._surface(context.grid_original_type),
        context.grid_runtime_type,
        *_BASE.image.prefix.literal._surface(context.grid_runtime_type),
        context.descriptor,
        type(context.p),
        *_BASE.image.prefix.literal._surface(type(context.p)),
        context.namespace,
        *(atom for pair in context.namespace.items() for atom in pair),
        *_global_wrapper_bindings(context.namespace),
        context.namespace["fd"],
        vars(context.namespace["fd"]),
        *(atom for pair in vars(context.namespace["fd"]).items() for atom in pair),
        context.grid_namespace,
        *(atom for pair in context.grid_namespace.items() for atom in pair),
        context.literal_methods,
        *(atom for fn in context.literal_methods for atom in _atoms(fn)),
        context.methods,
        *(atom for key, fn in context.methods.items() for atom in (key, *_atoms(fn))),
        context.grid_bodies,
        *(atom for key, fn in context.grid_bodies.items() for atom in (key, *_atoms(fn))),
        context.resume_delegate,
        *_atoms(context.resume_delegate),
        context.resume_delegate.__globals__,
        *(atom for pair in context.resume_delegate.__globals__.items() for atom in pair),
        context.generator_return_delegate,
        *_atoms(context.generator_return_delegate),
        context.generator_result_delegate,
        *_atoms(context.generator_result_delegate),
        context.protocol_scope,
        *(atom for pair in context.protocol_scope.items() for atom in pair),
        *(atom for module in context.modules for atom in previous._module_bindings(module)),
        context.body_codes,
        *(atom for pair in context.body_codes.items() for atom in pair),
        *(atom for view in context.module_views for atom in _view_bindings(view)),
        *(
            atom
            for cls in (_ModuleView, _NumpyView, _ObserverSystem)
            for atom in _BASE.image.prefix.literal._surface(cls)
        ),
    )


def _check(context):
    _bootstrap(context)
    if context.active:
        _guard(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or context.refs[1] is not context.parent.trial
        or context.request.parent_identity != context.parent.trial.identity
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(context.plan) != context.request.source_identity
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.cells.mesh is not context.mesh
        or context.rng is not context.parent.rng
        or _rng(context).identity != context.refs[1].stream_after.identity
    ):
        raise ValueError("Original phase/p/caller/mesh/global-MT lineage changed")
    _check_core(context)
    _same(_binding(context), context.bindings)
    if context.grid is not None and _GRIDS.get(context.grid) is not context:
        raise ValueError("Actual source grid/context association changed")


def _observe(context, name, raw):
    _guard(context)
    old = _epoch(context)
    try:
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    try:
        _same_epoch(context, old)
    except BaseException as error:
        _capture_failure(context, error, name + "_state", raw)


def _record(context, name, raw):
    try:
        _observe(context, name, raw)
    except BaseException as error:
        if context.observation_error is None:
            context.observation_error = error
        context.capture_errors += ((name + "_call", error, raw),)
    _guard(context)


def _operation(context, name, delegate, args, kwargs):
    row = _attempt(context, name, sys._getframe(1), "helper_delegate")
    _guard(context)
    _check(context)
    if context.helper_active:
        _reject(context, row, "Reentrant geometry helper")
    context.helper_active = True
    try:
        _record(context, name + "_enter", (args, kwargs))
        try:
            row["body_started"] = True
            result = delegate(*args, **kwargs)
        except BaseException as error:
            row["source_error"] = context.last_source_error = error
            raise
        context.helper_results.append((name, result))
        context.last_helper_result = (name, result)
        row["state"] = "returned"
        try:
            if isinstance(result, context.native_namespace["cKDTree"]):
                if not any(result is actual for _, actual in context.projector.objects):
                    context.projector.objects.append(("issued_source_tree", result))
                    context.issued_trees.append(result)
                observed = dict(
                    data=result.data, indices=result.indices, mins=result.mins, maxes=result.maxes
                )
            else:
                observed = _project(context, result)
            context.helper_views.append((name, observed))
        except BaseException as error:
            _capture_failure(context, error, name + "_view", result)
        _guard(context)
        _record(context, name + "_return", result)
        return result
    finally:
        context.helper_active = False


def _helper_wrapper(context, name, delegate):
    def call(*args, **kwargs):
        return _operation(context, name, delegate, args, kwargs)

    return call


def _global_wrapper_bindings(namespace):
    return tuple(
        atom
        for name in GLOBAL_HELPERS
        if name in namespace
        for atom in (name, *_atoms(namespace[name]))
    )


class _ModuleView:
    def __init__(self, context, module, name, allowed):
        self.context, self.module, self.name, self.allowed = context, module, name, allowed
        self.wrappers = {
            key: _helper_wrapper(context, name + "." + key, getattr(module, key)) for key in allowed
        }

    def __getattr__(self, name):
        if name in self.wrappers:
            return self.wrappers[name]
        value = vars(self.module).get(name)
        if isinstance(value, type) or name in ("pi", "newaxis", "nan", "inf"):
            return value
        _reject(self.context, None, "Unselected module/helper attribute: " + self.name + "." + name)


class _NumpyView(_ModuleView):
    def __init__(self, context, module, names):
        super().__init__(context, module, "np", tuple(n for n in names if "." not in n))
        self.linalg = _ModuleView(
            context,
            module.linalg,
            "np.linalg",
            tuple(n.split(".", 1)[1] for n in names if n.startswith("linalg.")),
        )


def _view_bindings(view):
    return (
        view,
        view.context,
        view.module,
        view.name,
        view.allowed,
        view.wrappers,
        *(atom for name in view.allowed for atom in _atoms(vars(view.module)[name])),
        *(atom for key, fn in view.wrappers.items() for atom in (key, *_atoms(fn))),
    )


def _native_helper_functions(functions):
    """Bounded actual callable closure; no helper or source body executes."""
    pending = list(functions)
    seen = set()
    result = []
    while pending:
        fn = pending.pop()
        if type(fn) is not FunctionType or id(fn) in seen:
            continue
        if len(seen) >= 512:
            raise ValueError("Bounded reached helper closure exhausted")
        seen.add(id(fn))
        result.append(fn)
        for attribute in ("__wrapped__", "_implementation"):
            pending.append(vars(fn).get(attribute))
        for cell in fn.__closure__ or ():
            if type(cell.cell_contents) is FunctionType:
                pending.append(cell.cell_contents)
        for value in (fn.__kwdefaults__ or {}).values():
            if type(value) is FunctionType:
                pending.append(value)
        for name in fn.__code__.co_names:
            value = fn.__globals__.get(name)
            if type(value) is FunctionType:
                pending.append(value)
            elif type(value) is ModuleType:
                pending.extend(vars(value).get(member) for member in fn.__code__.co_names)
    return tuple(result)


def _literal_methods():
    payload = _LITERAL_FILE.read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Exact selected geometry literal required")
    compiled = compile(payload, str(_LITERAL_FILE), "exec", dont_inherit=True)
    cls = next(
        c for c in compiled.co_consts if type(c) is CodeType and c.co_name == "SeedWorldGeometry"
    )
    result = []
    if source.SeedWorldGeometry is not _LITERAL_CLASS:
        raise ValueError("Original selected geometry class changed")
    for name, original in zip(
        ("finish_voronoi", "continue_world"), _LITERAL_FUNCTIONS, strict=True
    ):
        fn = vars(source.SeedWorldGeometry)[name]
        code = next(c for c in cls.co_consts if type(c) is CodeType and c.co_name == name)
        if (
            fn is not original
            or fn.__code__ != code
            or fn.__globals__ is not vars(source)
            or fn.__code__.co_filename != str(_LITERAL_FILE)
            or fn.__defaults__ is not None
            or fn.__kwdefaults__ is not None
            or fn.__closure__ is not None
            or fn.__annotations__
            or fn.__dict__
        ):
            raise ValueError("Executed selected geometry code/default/delegate changed")
        result.append(FunctionType(fn.__code__, vars(source), fn.__name__))
    return tuple(result)


def _resume(context, frame, row):
    # The reused metadata protocol has a private globals dictionary whose
    # guard/reject/attempt are THIS geometry lane. Never enter LC._ACTIVE or
    # reopen the consumed lifecycle validator to resume a helper generator.
    return context.resume_delegate(context, frame, row)


def _generator_return(context, frame, row):
    return context.generator_return_delegate(context, frame, row)


def _generator_value(context, result):
    """Cells-owned result projection; no mesh-module globals are invented."""
    if isinstance(result, context.native_namespace["cKDTree"]):
        return dict(
            kind="cKDTree",
            data=result.data,
            indices=result.indices,
            mins=result.mins,
            maxes=result.maxes,
        )
    return _project(context, result)


def _bind_generator_protocol(context):
    original_resume = previous._resume
    scope = dict(
        original_resume.__globals__,
        _guard=_guard,
        _reject=_reject,
        _attempt=_attempt,
        _generator_caller=_generator_caller,
        _helper_value=_generator_value,
    )
    context.protocol_scope = scope
    for attribute, original in (
        ("resume_delegate", original_resume),
        ("generator_return_delegate", previous._generator_return),
        ("generator_result_delegate", previous._generator_result),
    ):
        function = FunctionType(
            original.__code__, scope, original.__name__, original.__defaults__, original.__closure__
        )
        setattr(context, attribute, function)
    scope["_generator_return"] = context.generator_return_delegate


def _generator_caller(context, frame):
    row = context.admitted.get(id(frame))
    if row is not None and row["frame"] is frame:
        return row["state"] == "admitted" and row["body_started"] is True
    return (
        frame is not None
        and frame.f_code is _operation.__code__
        and frame.f_locals.get("context") is context
        and context.helper_active
    )


def _grid_len_boundary(context, frame):
    if context.grid_len_recorded or "grid_len" not in vars(context.cells):
        return
    if (
        frame is not context.world_frame
        or tuple(context.completed) != METHODS[:-1]
        or type(context.cells.grid_len) is not int
        or context.cells.grid_len != len(context.cells.xypts)
    ):
        _reject(context, None, "grid_len must follow environment and precede make_maskM")
    context.raw_grid_len = context.cells.grid_len
    context.grid_len_recorded = True
    context.stages.append(("grid_len", _snapshot(context)))


def _namespace(context):
    callbacks = _BASE.image.prefix.previous.previous.caches.previous.callbacks
    context.original_cells_type = context.assembly.factories["Cells"]
    original = {name: getattr(context.original_cells_type, name) for name in METHODS}
    for name, fn in original.items():
        callbacks._source_function(fn, "betse/science/cells.py", name, "Cells")
    native = original["makeECM"].__globals__
    context.native_namespace = native
    fd = native["fd"]
    context.grid_original_type = fd.FiniteDiffSolver
    if context.grid_original_type.__new__ is not object.__new__:
        raise ValueError("Original FiniteDiffSolver allocation unavailable")
    context.grid_init, context.grid_method = (
        getattr(context.grid_original_type, n) for n in ("__init__", "cell_grid")
    )
    for name, fn in (("__init__", context.grid_init), ("cell_grid", context.grid_method)):
        callbacks._source_function(fn, "betse/science/math/finitediff.py", name, "FiniteDiffSolver")
    context.original_methods = original
    descriptor = next(
        vars(cls)["grid_size"] for cls in type(context.p).__mro__ if "grid_size" in vars(cls)
    )
    context.descriptor = descriptor
    context.descriptor_getter = type(descriptor).__get__
    if type(context.descriptor_getter) is not FunctionType:
        raise ValueError("Actual original Python grid_size descriptor getter is required")
    context.callback = context.phase.callbacks.progressed_next
    callback_functions = _native_helper_functions((context.callback.__func__,))
    selected = [
        *original.values(),
        context.grid_init,
        context.grid_method,
        context.descriptor_getter,
        *callback_functions,
    ]
    context.reached_helpers = _native_helper_functions(selected)
    numpy_names = set()
    for fn in (*original.values(), context.grid_init, context.grid_method):
        for name in fn.__code__.co_names:
            value = vars(native["np"]).get(name)
            if callable(value):
                numpy_names.add(name)
    numpy_names.add("linalg.norm")
    context.numpy = _NumpyView(context, native["np"], tuple(sorted(numpy_names)))
    logs = _ModuleView(context, native["logs"], "logs", ("log_info", "log_warning"))
    context.module_views = [context.numpy, context.numpy.linalg, logs]
    namespace = dict(native, np=context.numpy, logs=logs)
    for name in GLOBAL_HELPERS:
        if name in native:
            namespace[name] = _helper_wrapper(context, name, native[name])
    for name, attrs in (("tb", ("flatten",)), ("interp", ("griddata",))):
        if name in native:
            namespace[name] = _ModuleView(context, native[name], name, attrs)
            context.module_views.append(namespace[name])
    grid_namespace = dict(context.grid_init.__globals__, np=context.numpy)
    context.grid_namespace = grid_namespace
    context.methods = {
        name: FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)
        for name, fn in original.items()
    }
    context.namespace = namespace
    context.grid_bodies = {
        name: FunctionType(
            fn.__code__, grid_namespace, fn.__name__, fn.__defaults__, fn.__closure__
        )
        for name, fn in (("__init__", context.grid_init), ("cell_grid", context.grid_method))
    }

    def wrap(name, delegate):
        def call(actual, *args, **kwargs):
            return _grid_call(context, name, delegate, actual, args, kwargs, sys._getframe())

        return call

    surface = {
        name: wrap(name, fn)
        for name, fn in vars(context.grid_original_type).items()
        if type(fn) is FunctionType
    }
    context.grid_runtime_type = type(
        "OwnedSeedWorldGrid",
        (context.grid_original_type,),
        dict(surface, __module__=__name__, __slots__=()),
    )

    def factory():
        return _grid_factory(context, sys._getframe())

    context.grid_factory = factory
    namespace["fd"] = SimpleNamespace(FiniteDiffSolver=factory)
    context.literal_methods = _literal_methods()
    _bind_generator_protocol(context)
    # Original wrapper and delegate closures/classes remain untouched.
    cell_wrapper = vars(type(context.cells))["cell_index"]
    context.body_codes = {fn.__code__: "Cells." + name for name, fn in original.items()}
    context.body_codes.update(
        {
            cell_wrapper.__code__: "Cells_wrapper",
            context.literal_methods[0].__code__: "aliases_body",
            context.literal_methods[1].__code__: "ordinary_body",
            factory.__code__: "grid_factory_wrapper",
            next(iter(surface.values())).__code__: "grid_method_wrapper",
            context.grid_init.__code__: "Grid.__init__",
            context.grid_method.__code__: "Grid.cell_grid",
            context.descriptor_getter.__code__: "grid_descriptor_get",
        }
    )
    for fn in context.reached_helpers:
        for code in previous._code_tree(fn.__code__):
            context.body_codes.setdefault(code, "reached_helper_body")
    for fn in original.values():
        for code in previous._code_tree(fn.__code__):
            context.body_codes.setdefault(code, "native_inner")
    context.generator_sites = MappingProxyType(
        {
            code: previous._generator_sites(code)
            for code in context.body_codes
            if code.co_flags & previous.CO_GENERATOR
        }
    )
    context.modules = tuple(
        dict.fromkeys(
            sys.modules[fn.__module__]
            for fn in context.reached_helpers
            if fn.__module__ in sys.modules and fn.__module__.startswith("betse.")
        )
    )
    context.descriptor_codes = frozenset(
        atom for atom in _atoms(context.descriptor_getter) if type(atom) is CodeType
    )


def _grid_factory(context, frame):
    _guard(context)
    _check(context)
    caller = frame.f_back
    if (
        caller is not context.native_frames.get("makeECM")
        or context.grid is not None
        or not context.descriptor_entered
        or not context.descriptor_returned
        or not context.descriptor_succeeded
    ):
        _reject(
            context, None, "Actual completed same-p descriptor read must precede grid construction"
        )
    grid = object.__new__(context.grid_runtime_type)
    context.grid = grid
    _GRIDS[grid] = context
    context.projector.objects.append(("issued_source_grid", grid))
    context.grid_factory_frame = sys._getframe()
    grid.__init__()
    _guard(context)
    if not context.grid_constructed:
        raise ValueError("Grid constructor did not return")
    return grid  # Literal makeECM performs the exact caller.grid_obj assignment next.


def _grid_call(context, name, delegate, actual, args, kwargs, wrapper):
    if hasattr(context, "poisson"):
        child, module = _poisson_route(context)
        if name != "makeLaplacian" or actual is not context.grid:
            module._reject(child, None, "Grid method outside actual Poisson continuation")
        return child.entries["Grid.makeLaplacian"](child, delegate, actual, args, kwargs, wrapper)
    row = _attempt(context, "Grid." + name, wrapper, "wrapper_dispatch")
    _guard(context)
    if (
        actual is not context.grid
        or _GRIDS.get(actual) is not context
        or name not in context.grid_bodies
        or delegate is not getattr(context.grid_original_type, name)
    ):
        _reject(context, row, "Raw/foreign/unselected grid method")
    claimed = context.admitted.get(id(wrapper))
    if claimed is None or claimed["frame"] is not wrapper or not claimed["body_started"]:
        _reject(context, row, "Grid method lacks original source wrapper entry")
    if name == "cell_grid" and (
        not context.grid_constructed or context.cells.grid_obj is not actual
    ):
        _reject(
            context,
            row,
            "Grid constructor completion -> actual assignment -> cell_grid order required",
        )
    _check(context)
    context.grid_delegate_frames[name] = sys._getframe()
    try:
        result = context.grid_bodies[name](actual, *args, **kwargs)
        context.raw_grid_results.append((name, result))
        row["state"] = "returned"
        _guard(context)
        if name == "__init__":
            context.grid_constructed = True
        else:
            context.grid_initialized = True
        return result
    except BaseException as error:
        row["source_error"] = error
        raise
    finally:
        context.grid_delegate_frames.pop(name, None)


def _admit(context, frame):
    old = context.admitted.get(id(frame))
    if old is not None and old["frame"] is frame:
        _guard(context)
        if frame.f_code in context.generator_sites:
            if not previous._generator_origin(context, frame):
                _reject(context, None, "Foreign generator observer entry")
            if old["state"] == "suspended":
                _resume(context, frame, old)
            elif old["state"] != "admitted":
                _reject(context, None, "Completed generator entry")
            elif old.get("pending_return", False):
                _reject(context, None, "Unresolved geometry generator return cannot resume")
        elif old["state"] != "admitted":
            _reject(context, None, "Completed source entry")
        return
    name = context.body_codes[frame.f_code]
    row = _attempt(context, name, frame, "native_body")
    context.admitted[id(frame)] = row
    _guard(context)
    parent = frame.f_back
    valid = False
    parent_row = None if parent is None else context.admitted.get(id(parent))
    if frame.f_code in context.generator_sites:
        if not previous._generator_origin(context, frame):
            _reject(context, row, "Unowned generator observer entry")
        row.update(
            activation=0,
            origin_parent=parent,
            suspension=None,
            source_errors=[],
            exception_witnesses=[],
            exception_unwind_pending=False,
            return_claim=None,
            return_observations=[],
            pending_return=False,
        )
    if name in ("aliases_body", "ordinary_body"):
        valid = parent is context.driver_frame and name not in context.literal_claims
        if valid:
            context.literal_claims.add(name)
            if name == "ordinary_body":
                context.world_frame = frame
    elif name == "Cells_wrapper":
        method = frame.f_locals.get("method")
        valid = (
            parent is context.world_frame
            and context.method_cursor < len(METHODS)
            and method == METHODS[context.method_cursor]
            and frame.f_locals.get("actual") is context.cells
            and frame.f_locals.get("delegate") is context.original_methods[method]
        )
        if valid:
            context.wrapper_claims[id(frame)] = (frame, method)
            context.method_cursor += 1
    elif name.startswith("Cells."):
        method = name.split(".", 1)[1]
        valid = (
            parent is context.delegate_frames.get(method)
            and frame.f_locals.get("self") is context.cells
            and frame.f_locals.get("p") is context.p
        )
        if valid:
            context.native_frames[method] = frame
    elif name == "grid_factory_wrapper":
        valid = parent is context.native_frames.get("makeECM")
    elif name == "grid_method_wrapper":
        method = frame.f_locals.get("name")
        valid = frame.f_locals.get("actual") is context.grid and (
            (method == "__init__" and parent is context.grid_factory_frame)
            or (method == "cell_grid" and parent is context.native_frames.get("makeECM"))
        )
    elif name in ("Grid.__init__", "Grid.cell_grid"):
        method = name.split(".", 1)[1]
        valid = (
            parent is context.grid_delegate_frames.get(method)
            and frame.f_locals.get("self") is context.grid
        )
    elif name == "grid_descriptor_get":
        arguments = frame.f_code.co_varnames[: frame.f_code.co_argcount]
        valid = (
            not context.descriptor_entered
            and parent is context.native_frames.get("makeECM")
            and len(arguments) >= 2
            and frame.f_locals.get(arguments[0]) is context.descriptor
            and frame.f_locals.get(arguments[1]) is context.p
        )
        if valid:
            context.descriptor_entered = True
            context.descriptor_frame = frame
    else:
        valid = (
            parent_row is not None
            and parent_row["frame"] is parent
            and parent_row["state"] == "admitted"
            and parent_row["body_started"]
        )
        if parent is not None and parent.f_code is _operation.__code__:
            valid = context.helper_active and parent.f_locals.get("context") is context
    if not valid:
        _reject(context, row, "Unclaimed/reentrant same-caller geometry entry: " + name)
    row["state"] = "admitted"


def _capture(context, frame, event):
    raw = dict(frame.f_locals)
    context.locals[(frame.f_code.co_qualname, event)] = raw
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        return
    if frame is context.world_frame and event in ("line", "return"):
        _grid_len_boundary(context, frame)
    if event == "exception":
        row["source_error"] = context.pending_source_error
        if frame.f_code in context.generator_sites:
            previous._record_generator_exception(context, frame, row)
    elif event == "line" and frame.f_code in context.generator_sites:
        row["exception_unwind_pending"] = False
    if event == "return":
        if frame.f_code in context.generator_sites:
            _generator_return(context, frame, row)
            return
        if not row.get("returned", False):
            row["returned"] = True
            row["state"] = "unwound" if row.get("source_error") is not None else "returned"
            name = context.body_codes[frame.f_code]
            if name.startswith("Cells.") and row["state"] == "returned":
                method = name.split(".", 1)[1]
                context.completed.append(method)
                context.stages.append((method, _snapshot(context)))
            if name == "grid_descriptor_get":
                context.descriptor_returned = True
                context.descriptor_succeeded = row["state"] == "returned"


def _wrapper_guard(context, original, wrapper):
    _guard(context)
    claim = context.wrapper_claims.get(id(wrapper))
    if (
        claim is None
        or claim[0] is not wrapper
        or original is not context.assembly
        or wrapper.f_locals.get("actual") is not context.cells
    ):
        _reject(context, None, "Only the original claimed Cells wrapper may enter geometry")
    _check(context)


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    row = _attempt(context, label, dispatch_frame, "original_native_wrapper_dispatch")
    _guard(context)
    native = None if type(dispatch_frame) is not FrameType else dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    claim = None if wrapper is None else context.wrapper_claims.get(id(wrapper))
    method = None if claim is None else claim[1]
    if (
        claim is None
        or claim[0] is not wrapper
        or original is not context.assembly
        or actual is not context.cells
        or label != "Cells." + method
        or delegate is not context.original_methods[method]
        or type(args) is not tuple
        or len(args) != 1
        or args[0] is not context.p
        or kwargs
        or native.f_code is not context.prefix.native_call_code
    ):
        _reject(context, row, "Original same-instance Cells geometry dispatch required")
    _check(context)
    context.delegate_frames[method] = sys._getframe()
    _record(context, method + "_enter", (actual, context.p))
    try:
        result = context.methods[method](actual, *args, **kwargs)
        context.raw_method_results.append((method, result))
        row["state"] = "returned"
        _record(context, method + "_return", result)
        return result
    except BaseException as error:
        row["source_error"] = error
        raise
    finally:
        context.delegate_frames.pop(method, None)


class _ObserverSystem(previous._ObserverSystem):
    def _gate(self, frame, event):
        if (
            event == "call"
            and frame.f_code not in self.context.body_codes
            and frame.f_code.co_filename.startswith(self.context.native_root)
        ):
            _reject(self.context, None, "Unbound native helper/import body")

    def _result(self, frame, event, result):
        if event == "return" and frame.f_code in self.context.generator_sites:
            try:
                self.context.generator_result_delegate(self.context, frame, result)
            except BaseException as error:
                _capture_failure(self.context, error, "generator_return", (frame, result))
        if event == "return" and frame is self.context.descriptor_frame:
            self.context.raw_descriptor_return = result


def _observer_bindings(context=None):
    context = _ACTIVE[-1] if context is None else context
    _bootstrap(context)
    return (
        context.observer_scope,
        context.observer_function,
        context.observer_system,
        context.observer_system.codes,
        *(atom for pair in context.observer_scope.items() for atom in pair),
        *(
            atom
            for fn in (_admit, _capture, _guard, _check, _epoch, _same_epoch, _capture_failure)
            for atom in _atoms(fn)
        ),
    )


@contextmanager
def _account(context):
    scope = dict(_BASE.image.prefix.__dict__)
    scope.update(
        {
            name: globals()[name]
            for name in (
                "_observer_bindings",
                "_admit",
                "_capture",
                "_capture_failure",
                "_guard",
                "_check",
                "_epoch",
                "_same_epoch",
                "_reject",
            )
        }
    )
    scope["_Random"] = _BASE._Random
    context.observer_system = _ObserverSystem(context)
    scope["sys"] = context.observer_system
    original = _BASE.image.prefix._account.__wrapped__
    fn = FunctionType(
        original.__code__, scope, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_scope, context.observer_function = scope, fn
    context.observer_bindings = _observer_bindings(context)
    with contextmanager(fn)(context):
        yield


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=None if value.before is None else value.before.identity,
        cache=None if value.cache is None else value.cache.identity,
        stages=tuple((name, cache.identity) for name, cache in value.stage_caches),
        before_MT=None if value.stream_before is None else value.stream_before.identity,
        after_MT=None if value.stream_after is None else value.stream_after.identity,
        work=value.work,
        warnings=value.warnings,
        completed=value.source_completed,
        stage=value.failure_stage,
        source_error=value.source_failure,
        capture_error=value.capture_failure,
    )


def _partial(context):
    return dict(
        context=context,
        parent=context.parent,
        parent_trial=context.refs[1],
        request=context.request,
        phase=context.phase,
        p=context.p,
        caller=context.cells,
        mesh=context.mesh,
        mask=context.mask,
        grid=context.grid,
        stages=context.stages,
        work=context.work,
        locals=context.locals,
        events=context.events,
        raw_helpers=context.helper_results,
        raw_grid_results=context.raw_grid_results,
        raw_method_results=context.raw_method_results,
        raw_descriptor_return=getattr(context, "raw_descriptor_return", None),
        generator_results=context.generator_results,
        generator_interruptions=context.generator_interruptions,
        generator_observations=context.generator_observations,
        protocol_history=getattr(context, "protocol_history", ()),
        protocol_dropped=getattr(context, "protocol_dropped", 0),
        primary=context.primary,
        capture_errors=context.capture_errors,
        trial=context.trial,
    )


def _failure(context, primary, capture):
    context.invalid = True
    partial = context
    try:
        partial = _partial(context)
    except BaseException as error:
        context.capture_errors += (("failure_partial", error, context),)
        if capture is None:
            capture = error
    raise GeometryRejected(
        "Actual same-caller geometry/grid/mask failed",
        stage=context.stage,
        request=context.request,
        trial=context.trial,
        partial=partial,
        source_error=primary,
        capture_error=capture,
    ) from primary


def prepare(request, *, enabled=False):
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise GeometryRejected("Actual geometry/grid/mask execution remains held", stage="release")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant geometry continuation")
    if type(request) is not Request or request not in _REQUESTS:
        raise GeometryRejected("Actual issued lifecycle request required", stage="request")
    with _LOCK:
        if request in _CONSUMED or request.lifecycle_owner in _RETIRED:
            raise GeometryRejected("Geometry epoch consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        parent = refs[0]
        ctor = parent.parent
        prefix = ctor.parent.parent
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=parent,
            api=api,
            phase=parent.phase,
            p=parent.p,
            cells=parent.cells,
            mesh=parent.mesh,
            mask=parent.mask,
            rng=parent.rng,
            ctor=ctor,
            prefix=prefix,
            assembly=prefix.prefix,
            rand=parent.rand,
            draw_active=False,
            thread=get_ident(),
            active=True,
            invalid=False,
            validating=False,
            stage="lifecycle_retirement",
            driver_frame=sys._getframe(),
            trial=None,
            before=None,
            work=[],
            events=[],
            locals={},
            stages=[],
            completed=[],
            admitted={},
            entry_error=None,
            observation_error=None,
            pending_source_error=None,
            capture_errors=(),
            capture_reporting_errors=(),
            cleanup_errors=(),
            primary=None,
            caught=[],
            helper_active=False,
            helper_results=[],
            helper_views=[],
            query_views=[],
            generator_views=[],
            generator_results=[],
            generator_interruptions=[],
            generator_observations=[],
            generator_suspensions={},
            descriptor_entered=False,
            descriptor_returned=False,
            descriptor_succeeded=False,
            descriptor_frame=None,
            grid=None,
            grid_constructed=False,
            grid_initialized=False,
            grid_len_recorded=False,
            issued_trees=[],
            grid_factory_frame=None,
            grid_delegate_frames={},
            raw_grid_results=[],
            raw_method_results=[],
            wrapper_claims={},
            delegate_frames={},
            native_frames={},
            method_cursor=0,
            literal_claims=set(),
            world_frame=None,
            callback=parent.callback,
            callback_codes=frozenset(),
            forbidden_callback_codes=parent.forbidden_callback_codes,
            required_hooks=(sys.getprofile(), sys.gettrace()),
            restore_setters=(sys.setprofile, sys.settrace),
            restore_getters=(sys.getprofile, sys.gettrace),
        )
        _CONSUMED[request] = _RETIRED[request.lifecycle_owner] = context
        _ACTIVE.append(context)
        primary = capture = None
        healthy = False
        try:
            context.checker = (
                api._independent_atoms,
                api._independent_atoms.__code__,
                api._independent_atoms.__globals__,
            )
            context.metadata_helpers = tuple(
                (name, fn, api._independent_atoms(fn))
                for name, fn in globals().items()
                if type(fn) is FunctionType and fn.__globals__ is globals()
            )
            context.plan = source_plan()
            context.original_names = tuple(vars(context.cells))
            context.objects = tuple(parent.objects)
            context.holders = tuple(vars(obj) for _, obj in context.objects)
            context.projector = SimpleNamespace(
                objects=[*parent.projector.objects, ("geometry_context", context)]
            )
            context.core_fields = [{} for _ in context.objects]
            context.core_view = SimpleNamespace(objects=context.objects, fields=context.core_fields)
            context.graph_view = SimpleNamespace(caller=None, grid=None)
            context.stable_tape = SimpleNamespace(rng=context.rng, events=(), draws=(), locals={})
            context.core_cache = _core_values(context)
            context.core_edges = _core_graph(context)
            context.parent_claim = getattr(previous, PROPOSED_CLAIM)
            context.parent_check = getattr(previous, PROPOSED_CHECK)
            context.entries = MappingProxyType({"Cells." + name: _dispatch for name in METHODS})
            if (
                context.parent_claim(
                    request.lifecycle_owner,
                    expected=parent,
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different lifecycle owner retired")
            previous._same_epoch(parent, refs[2])
            context.before = _snapshot(context)
            context.stream_before = _rng(context)
            context.stage = "native_geometry_namespace"
            _namespace(context)
            context.bindings = _binding(context)
            _check(context)
            context.stage = "same_caller_geometry_grid_mask"
            with warnings.catch_warnings(record=True) as caught:
                context.caught = caught
                with _account(context):
                    context.literal_methods[0](context.cells, context.mask)
                    _guard(context)
                    context.stages.append(("four_aliases", _snapshot(context)))
                    context.literal_methods[1](context.cells, context.phase)
                    _guard(context)
                    _check(context)
            if (
                tuple(context.completed) != METHODS
                or not context.grid_initialized
                or not context.descriptor_succeeded
                or not context.grid_len_recorded
                or tuple(name for name, _ in context.stages) != STAGES
                or any(row.get("pending_return", False) for row in context.admitted.values())
            ):
                raise ValueError("Source method/grid/descriptor sequence incomplete")
        except BaseException as error:
            primary = (
                context.entry_error
                if context.entry_error is not None
                else (
                    context.pending_source_error
                    if isinstance(error, _BASE.image.prefix.literal._CaptureStop)
                    else error
                )
            )
            context.primary = primary
        finally:
            try:
                healthy = _BASE._recover(context)
            except BaseException as error:
                context.capture_errors += (("recovery_boundary", error, context),)
                if context.observation_error is None:
                    context.observation_error = error
                for i in (1, 0):
                    try:
                        context.restore_setters[i](context.required_hooks[i])
                    except BaseException as secondary:
                        context.cleanup_errors += (("emergency_restore", secondary, i),)
        capture = context.observation_error
        if healthy and context.before is not None:
            try:
                context.stream_after = _rng(context)
                value = Trial(
                    request.identity,
                    request.parent_identity,
                    context.before,
                    _snapshot(context),
                    tuple(context.stages),
                    context.stream_before,
                    context.stream_after,
                    tuple((r["sequence"], r["name"], r["layer"], r["state"]) for r in context.work),
                    tuple(
                        (
                            w.category.__module__,
                            w.category.__qualname__,
                            str(w.message),
                            w.filename,
                            w.lineno,
                        )
                        for w in context.caught
                    ),
                    primary is None
                    and capture is None
                    and tuple(context.completed) == METHODS
                    and tuple(name for name, _ in context.stages) == STAGES,
                    context.stage if primary is not None or capture is not None else None,
                    None if primary is None else type(primary).__qualname__,
                    None if capture is None else type(capture).__qualname__,
                    "",
                )
                context.trial = replace(value, identity=_digest(trial_record(value)))
                if primary is None and capture is None:
                    _check(context)
                    context.graph = _graph(context)
            except BaseException as error:
                context.capture_errors += (("final_sealing", error, context),)
                if capture is None:
                    capture = error
        try:
            healthy = _BASE._recover(context) and healthy
        except BaseException as error:
            context.capture_errors += (("post_sealing_recovery", error, context),)
            if capture is None:
                capture = error
            healthy = False
        context.active = False
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.invalid = True
        if (
            primary is not None
            or capture is not None
            or context.trial is None
            or not healthy
            or context.invalid
        ):
            if not healthy:
                if primary is not None:
                    raise primary
                if capture is not None:
                    raise capture
                raise RuntimeError("Inherited hooks unavailable; raw geometry context retained")
            _failure(context, primary, capture)
        try:
            owner = object.__new__(GeometryOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            _failure(context, error, capture)


class GeometryOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual lifecycle-to-geometry continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No supplied cache or ordinary checkpoint")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not GeometryOwner or owner not in _ISSUED:
        raise GeometryRejected("Actually issued geometry child required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or hasattr(context, "poisson"):
        raise GeometryRejected(
            "Geometry epoch was irreversibly consumed",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
    if context.active or context.validating or context.invalid:
        _reject(context, None, "Unavailable geometry child")
    context.validating = True
    try:
        _check(context)
        if (
            context.trial.source_completed is not True
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity != _snapshot(context).identity
        ):
            raise ValueError("Completed same-caller geometry trial/cache changed")
        graph = _graph(context)
        _same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Completed actual caller/grid aliases changed")
    except BaseException as error:
        _failure(context, error, context.observation_error)
    finally:
        context.validating = False
    return context


def _claim_for_world_poisson(owner, *, expected, transition, entries):
    module = _ready()._world_seed_poisson_api()
    caller = sys._getframe(1)
    with _LOCK:
        if (
            caller.f_code is not module.prepare.__code__
            or not module._ACTIVE
            or module._ACTIVE[-1] is not transition
            or type(owner) is not GeometryOwner
            or _ISSUED.get(owner) is not expected
        ):
            raise GeometryRejected("Actual active Poisson issuer required", stage="entry")
        parent = expected
        if owner in _FORWARDED or hasattr(parent, "poisson"):
            raise GeometryRejected("Geometry Poisson epoch consumed", stage="consumed")
        if (
            parent.active
            or parent.invalid
            or parent.validating
            or parent.owner is not owner
            or transition.driver_frame is not caller
            or transition.parent is not parent
            or type(transition.request) is not module.Request
            or module._REQUESTS.get(transition.request) is not transition.refs
            or module._CONSUMED.get(transition.request) is not transition
            or module._RETIRED.get(owner) is not transition
            or transition.request.geometry_owner is not owner
            or transition.refs[0] is not parent
            or transition.refs[1] is not parent.trial
            or any(
                getattr(transition, name) is not getattr(parent, name)
                for name in ("phase", "p", "cells", "mesh", "mask", "rng", "grid")
            )
            or transition.thread != parent.thread
            or transition.thread != get_ident()
            or entries is not transition.entries
            or tuple(entries) != ("Grid.makeLaplacian",)
            or entries["Grid.makeLaplacian"] is not module._grid_call
        ):
            parent.invalid = transition.invalid = True
            raise ValueError("Original same-caller geometry/Poisson claim required")
        parent.poisson = transition
        try:
            _FORWARDED[owner] = transition
            _check(parent)
            if (
                parent.trial.source_completed is not True
                or parent.trial.identity != _digest(trial_record(parent.trial))
                or parent.trial.cache.identity != _snapshot(parent).identity
            ):
                raise ValueError("Original geometry seal changed before Poisson")
            graph = _graph(parent)
            _same(graph[0], parent.graph[0])
            if graph[1] != parent.graph[1] or _poisson_route(parent)[0] is not transition:
                raise ValueError("Original geometry graph/retirement changed")
        except BaseException:
            parent.invalid = transition.invalid = True
            raise
        return parent


def _poisson_route(parent):
    module = _ready()._world_seed_poisson_api()
    child, owner = getattr(parent, "poisson", None), getattr(parent, "owner", None)
    if (
        child is None
        or owner is None
        or _ISSUED.get(owner) is not parent
        or _FORWARDED.get(owner) is not child
        or parent.active
        or parent.invalid
        or child.invalid
        or child.parent is not parent
        or type(child.request) is not module.Request
        or child.request.geometry_owner is not owner
        or module._REQUESTS.get(child.request) is not child.refs
        or module._CONSUMED.get(child.request) is not child
        or module._RETIRED.get(owner) is not child
        or child.refs[0] is not parent
        or child.refs[1] is not parent.trial
        or any(
            getattr(child, name) is not getattr(parent, name)
            for name in ("phase", "p", "cells", "mesh", "mask", "rng", "grid")
        )
        or child.thread != parent.thread
        or child.thread != get_ident()
        or tuple(child.entries) != ("Grid.makeLaplacian",)
        or child.entries["Grid.makeLaplacian"] is not module._grid_call
    ):
        raise ValueError("Actual geometry/Poisson issuance or retirement changed")
    return child, module


def _check_world_poisson_authority(transition):
    parent = transition.parent
    if _poisson_route(parent)[0] is not transition:
        raise ValueError("Different actual Poisson transition")
    _check(parent)
    if parent.trial is not transition.refs[1] or not parent.trial.source_completed:
        raise ValueError("Retained actual geometry trial changed")
    return parent


def require_Poisson(owner):
    context = _authority(owner)
    raise GeometryRejected(
        "Poisson mode/release is Root-owned and remains unavailable",
        stage="Poisson_held",
        request=context.request,
        trial=context.trial,
    )
