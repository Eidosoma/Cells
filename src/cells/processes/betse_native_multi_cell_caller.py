"""Fresh non-SVG multi-cell caller/image/mesh ownership through cell_index.

Retained initial/clip/lifecycle trials authenticate separate source replays.
None of their cached objects populate or attach to the actual continuing
caller. Parameters are a selected normalized source projection, not full
Parameters/YAML/phase authority. All actual execution requires coordinated
release; source ownership alone grants no numerical or physical admission.
"""

import ast
import hashlib
import json
import sys
import warnings
from collections.abc import Mapping
from contextlib import contextmanager
from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
from cells.processes import betse_native_multi_cell_caller_source as source
from cells.processes import betse_native_single_cell_caller_completion as accounting
from cells.processes import betse_native_single_cell_grid_alias as atoms
from cells.processes import betse_native_single_cell_image_mask as images
from cells.processes import betse_native_single_cell_initial_geometry as captures

callers, core, clipped, initial = images.callers, images.core, lifecycle.clipped, lifecycle.initial
LAW_ID = "betse_owned_non_SVG_multi_cell_caller@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
_CELL_INIT = callers.source.CellsKernel.__init__
_LATTICE = callers.source.CellsKernel._make_cell_lattice
_STORES = source.ParameterStores.initialize_source_stores
_VORONOI = source.CellsMulti.make_voronoi_non_svg
_INDEX = source.CellsMulti.cell_index
_PIPELINE = source.MeshPipeline.clip_and_refine
_NATIVE = {
    name: getattr(lifecycle._Runtime, name)
    for base in lifecycle._Runtime.__mro__
    if base is not object
    for name, method in vars(base).items()
    if callable(method) and name != "__reduce_ex__"
}
_TOOL_METHODS = {
    name: getattr(clipped._Tools, name)
    for base in clipped._Tools.__mro__
    if base is not object
    for name, method in vars(base).items()
    if callable(method)
}
_ACTIVE, _ISSUED = WeakKeyDictionary(), WeakKeyDictionary()
_LOCK = RLock()


@dataclass(frozen=True, slots=True)
class Request:
    lifecycle_request: lifecycle.Request
    lifecycle_state: lifecycle.State
    configuration_json: str
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identities: tuple
    parameter_cache: object
    caller_cache: object
    mesh_cache: object
    lattice_audit: object
    image_audit: object
    stages: tuple
    events: tuple
    ordering: tuple
    point_ids: tuple
    stream_before: object
    stream_after: object
    warnings: tuple
    work: tuple
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class MultiCellRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial
        self.source_error, self.capture_error = source_error, capture_error


def _parents(request):
    lr = request.lifecycle_request
    return (
        lr.clip_request.initial_request,
        lr.clip_request.initial_state,
        lr.clip_request,
        lr.clip_state,
    )


def _precheck(request):
    if type(request) is not Request or type(request.lifecycle_request) is not lifecycle.Request:
        raise MultiCellRejected(
            "Typed retained multi-cell source chain required",
            stage="upstream_owner",
            request=request,
        )
    lr, ls = request.lifecycle_request, request.lifecycle_state
    if (
        type(ls) is not lifecycle.State
        or type(lr.clip_request) is not clipped.Request
        or type(lr.clip_state) is not clipped.State
        or lr.origin != "owned_make_voronoi_lifecycle"
    ):
        raise MultiCellRejected(
            "Original non-SVG lifecycle authority required", stage="upstream_owner", request=request
        )
    ir, state, cr, cs = _parents(request)
    if (
        type(ir) is not initial.Request
        or type(state) is not initial.State
        or ir.origin != "owned_image_prelude"
    ):
        raise MultiCellRejected(
            "Original owned image/initial trial required", stage="upstream_owner", request=request
        )
    binding, seed, prelude = ir.upstream
    if (
        type(binding) is not initial.image_stage.lattice.Binding
        or type(seed) is not initial.image_stage.lattice.SeedState
        or type(prelude) is not initial.image_stage.Prelude
    ):
        raise MultiCellRejected(
            "Typed seed/image provenance unavailable", stage="upstream_owner", request=request
        )
    controls = json.loads(prelude.controls_json)
    conf = json.loads(request.configuration_json)
    if type(conf) is not dict or type(conf.get("world options")) is not dict:
        raise MultiCellRejected(
            "Normalized world-options mapping required", stage="configuration", request=request
        )
    if (
        controls["single_cell"] is not False
        or controls["svg_override"] is not False
        or prelude.next_method != "clip_and_refine"
        or ir.constructor_kwargs["seed_points"] is None
        or type(conf) is not dict
        or conf["world options"].get("import from svg") is not None
    ):
        raise MultiCellRejected(
            "Only the genuine non-SVG multi-cell branch is implemented",
            stage="branch",
            request=request,
        )
    if (
        state.status != "source_completed_unqualified"
        or not state.constructor_completed
        or not state.pre_mesh_completed
        or cs.status != "source_clipped_rebuilt_unqualified"
        or ls.status != "source_lifecycle_completed_unqualified"
        or state.request_identity != ir.identity
        or cs.request_identity != cr.identity
        or ls.request_identity != lr.identity
    ):
        raise MultiCellRejected(
            "Missing/failed source parent cannot grant a live caller",
            stage="incomplete_upstream",
            request=request,
            partial=dict(initial_trial=state, clip_trial=cs, lifecycle_trial=ls),
        )


def request_record(request):
    ir, state, cr, cs = _parents(request)
    return dict(
        law=LAW_ID,
        initial_request=ir.identity,
        initial_state=state.identity,
        clip_request=cr.identity,
        clip_state=cs.identity,
        lifecycle_request=request.lifecycle_request.identity,
        lifecycle_state=request.lifecycle_state.identity,
        configuration_json=request.configuration_json,
        selected_parameter_store_lines=source.STORE_LINES,
        selected_parameter_AST=source.STORES_AST_SHA256,
        caller_AST=source.CALLER_AST_SHA256,
        normalized_parameter_projection_only=True,
        boundary="after cell_index, before cellVerts",
        invalidated_owners=INVALIDATED_OWNERS,
        full_Parameters_YAML_phase_physical_checkpoint_admitted=False,
    )


def from_lifecycle(request, state, configuration, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise MultiCellRejected("Explicit multi-cell source law required", stage="opt_in")
    if type(configuration) is not dict:
        raise MultiCellRejected("Explicit normalized configuration required", stage="configuration")
    text = json.dumps(configuration, allow_nan=False, sort_keys=True, separators=(",", ":"))
    if len(text.encode()) > 65536:
        raise MultiCellRejected(
            "Normalized configuration exceeds bounded source projection", stage="configuration"
        )
    value = Request(request, state, text, "")
    _precheck(value)  # Refusal/identity checks only; no authentication replay here.
    return replace(value, identity=core.records._digest(request_record(value)))


def _verify_sources():
    pins = images._verify_sources()
    for module in (
        initial,
        initial.source,
        clipped,
        clipped.source,
        lifecycle,
        lifecycle.source,
        source,
        sys.modules[__name__],
        accounting,
    ):
        path = Path(module.__file__).resolve()
        pins[str(path)] = hashlib.sha256(path.read_bytes()).hexdigest()
    for relative, expected in source.NATIVE_PINS.items():
        path = callers.NATIVE_ROOT / "betse/science" / relative
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Original multi-cell source changed")
    parsed = ast.parse(Path(source.__file__).read_text())
    classes = {n.name: n for n in parsed.body if isinstance(n, ast.ClassDef)}
    for name, method, expected in (
        ("ParameterStores", "initialize_source_stores", source.STORES_AST_SHA256),
        ("CellsMulti", "make_voronoi_non_svg", source.CALLER_AST_SHA256),
    ):
        body = next(
            n for n in classes[name].body if isinstance(n, ast.FunctionDef) and n.name == method
        ).body
        if (
            hashlib.sha256(ast.dump(ast.Module(body=body, type_ignores=[])).encode()).hexdigest()
            != expected
        ):
            raise ValueError("Selected multi-cell source projection changed")
    native = ast.parse((callers.NATIVE_ROOT / "betse/science/math/mesh.py").read_text())
    cls = next(n for n in native.body if isinstance(n, ast.ClassDef) and n.name == "DECMesh")
    original = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "clip_and_refine"
    )
    copied = next(n for n in classes["MeshPipeline"].body if isinstance(n, ast.FunctionDef))
    if ast.dump(original) != ast.dump(copied):
        raise ValueError("Literal clip_and_refine signature/body changed")
    native_cells = ast.parse((callers.NATIVE_ROOT / "betse/science/cells.py").read_text())
    cells_class = next(
        n for n in native_cells.body if isinstance(n, ast.ClassDef) and n.name == "Cells"
    )
    left = next(
        n for n in cells_class.body if isinstance(n, ast.FunctionDef) and n.name == "cell_index"
    )
    right = next(
        n
        for n in classes["CellsMulti"].body
        if isinstance(n, ast.FunctionDef) and n.name == "cell_index"
    )
    if ast.dump(left) != ast.dump(right):
        raise ValueError("Literal cell_index signature/body changed")
    return pins


def _context(obj):
    context = _ACTIVE.get(obj)
    if context is None or not context.active or context.thread != get_ident():
        raise MultiCellRejected(
            "Native entry lacks active issued multi-cell driver", stage="source_call_unavailable"
        )
    return context


def _observe(context, kind, raw):
    try:
        context.events.append((kind, raw))
    except Exception as capture:
        captures._remember_observation_error(context, capture, origin=kind, raw=raw)


class _CaptureStop(Exception):
    pass


def _stop(context):
    if context.observation_error is not None:
        raise _CaptureStop()


class _Parameters(source.ParameterStores):
    def __init__(self, recipe, configuration):
        context = _context(self)
        context.parameter_running = True
        try:
            self._conf = configuration
            self.world_len = float(recipe["world_len_m"])
            self.cell_radius = float(recipe["cell_radius_m"])
            self.cell_lattice_disorder = float(recipe["lattice_disorder"])
            self.cell_lattice_type = callers.source.CellLatticeType[recipe["lattice_type"]]
            self.initialize_source_stores()
        finally:
            context.parameter_running = False

    def initialize_source_stores(self):
        _context(self)
        return _STORES(self)

    def __setattr__(self, name, value):
        context = _ACTIVE.get(self)
        object.__setattr__(self, name, value)
        if context is not None and context.parameter_running:
            _observe(context, "parameter_store", (name, value))
            _stop(context)

    def __reduce_ex__(self, protocol):
        raise TypeError("Live normalized parameter authority cannot be serialized")


class _Caller(callers.source.CellsKernel):
    def __init__(self, p):
        context = _context(self)
        if p is not context.p:
            raise ValueError("Actual caller parameter identity changed")
        return _CELL_INIT(self, p)

    def _make_cell_lattice(self, p):
        context = _context(self)
        if p is not context.p or context.lattice_started or context.stage != "Cells_lattice":
            raise ValueError("Actual lattice parameter identity changed")
        context.lattice_started = True
        return context.lattice_method(self, p)

    def make_voronoi(self, phase):
        raise MultiCellRejected(
            "Full phase/package make_voronoi remains unavailable", stage="phase_held"
        )

    def cell_index(self, p):
        context = _context(self)
        if not context.mesh_completed or p is not context.p or context.index_started:
            raise ValueError("cell_index lacks the actual completed multi-cell mesh/parameters")
        context.index_started = True
        previous_stage = context.stage
        context.stage = context.work_context.stage = "cell_index"
        value = _INDEX(self, p)
        context.index_completed = True
        _stage_snapshot(context, "cell_index", caller=True)
        _stop(context)
        context.stage = context.work_context.stage = previous_stage
        return value

    def __setattr__(self, name, value):
        context = _ACTIVE.get(self)
        if name == "mesh" and context is not None and context.active:
            if not context.constructor_completed or value is not context.kernel:
                raise ValueError("Constructor must complete before assigning that exact mesh")
            object.__setattr__(self, name, value)
            context.mesh_assigned = True
            _observe(context, "caller_mesh_assignment", value)
            _stop(context)
        else:
            object.__setattr__(self, name, value)

    def __reduce_ex__(self, protocol):
        raise TypeError("Live multi-cell caller authority cannot be serialized")


def _mask_record(context):
    prelude = context.prelude
    local = context.image_tape.locals["TissuePickerImageMask.__init__"]
    mask = context.mask
    return dict(
        kind="owned_image_prelude_mask_token",
        identity=prelude.identity,
        image_identity=prelude.image.identity,
        xpts_m=local["xpts"],
        ypts_m=local["ypts"],
        clipping_matrix=mask.clipping_matrix,
        clipcurve_m=mask.clipcurve,
    )


def _project(context, value, memo=None):
    """Evidence-only projection; the actual mask is never replaced in source."""
    if value is context.mask and context.mask is not None:
        return _mask_record(context)
    memo = {} if memo is None else memo
    if isinstance(value, (dict, list, tuple)):
        if id(value) in memo:
            return memo[id(value)]
        if isinstance(value, dict):
            result = {}
            memo[id(value)] = result
            result.update((key, _project(context, item, memo)) for key, item in value.items())
        else:
            result = [_project(context, item, memo) for item in value]
            result = tuple(result) if isinstance(value, tuple) else result
            memo[id(value)] = result
        return result
    return value


class _Observer(lifecycle._Observer):
    def __init__(self, ids, context):
        super().__init__(ids)
        self.context = context

    def add(self, kind, payload):
        try:
            return super().add(kind, _project(self.context, payload))
        except Exception as capture:
            captures._remember_observation_error(
                self.context, capture, origin="mesh:" + kind, raw=payload
            )


class _Tools(clipped._Tools):
    pass


class _Runtime(lifecycle._Runtime):
    def __reduce_ex__(self, protocol):
        raise TypeError("Live multi-cell mesh authority cannot be serialized")

    def clip_and_refine(self, imagemask, *args, **kwargs):
        context = _context(self)
        frame = sys._getframe(1)
        if (
            context.kernel is not self
            or context.caller.mesh is not self
            or not context.mesh_assigned
            or imagemask is not context.mask
            or context.pipeline_started
            or frame.f_code is not context.caller_method.__code__
            or frame.f_locals.get("self") is not context.caller
        ):
            raise MultiCellRejected(
                "Original constructor/assignment/actual-mask order unavailable",
                stage="source_call_unavailable",
            )
        context.pipeline_started = True
        previous_stage = context.stage
        context.stage = context.work_context.stage = "clip_and_refine"
        _observe(context, "clip_and_refine_enter", imagemask)
        _stop(context)
        result = context.pipeline(self, imagemask, *args, **kwargs)
        _stop(context)
        context.mesh_completed = True
        _observe(context, "clip_and_refine_return", self)
        _stop(context)
        context.stage = context.work_context.stage = previous_stage
        return result


def _mesh_cache(context):
    return core.caches.snapshot(_project(context, initial._public_cache(context.kernel)))


def _stage_snapshot(context, name, *, caller=False, cache=None):
    try:
        value = (
            cache
            if cache is not None
            else _public_cache(context)
            if caller
            else _mesh_cache(context)
        )
        context.stages.append((name, value))
    except Exception as capture:
        captures._remember_observation_error(
            context,
            capture,
            origin="stage:" + name,
            raw=context.caller if caller else context.kernel,
        )


def _compare_mesh(context, state, *, initial_stage=False):
    expected_ids = (
        state.retained_point_ids
        if initial_stage or isinstance(state, clipped.State)
        else state.point_ids_after
    )
    if (
        _mesh_cache(context).identity != state.cache.identity
        or context.observer.ids != expected_ids
        or initial._rng_stream(context.rng).identity != state.stream_after.identity
    ):
        raise ValueError(
            "Actual continuing mesh cache/occurrence lineage/RNG differs from source trial"
        )
    if initial_stage or isinstance(state, clipped.State):

        def signature(events):
            return tuple(
                (e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in events
            )

        if signature(context.observer.events) != signature(state.events):
            raise ValueError("Actual initial/clip event prefix differs from retained source")
    warnings_seen = tuple(str(w.message) for w in context.caught[context.mesh_warning_offset :])
    if warnings_seen != state.warnings:
        raise ValueError("Actual continuing mesh warning prefix differs from retained source")


def _guard(name, delegate, *, tool=False):
    def invoke(self, *args, **kwargs):
        context = _context(self)
        cleanup = name in {"_cells_partial", "_cells_lifecycle_partial", "_cells_cell_exit"}
        if cleanup and sys.exception() is not None:
            try:
                return delegate(self, *args, **kwargs)
            except Exception as capture:
                captures._remember_observation_error(
                    context, capture, origin="unwind:" + name, raw=args
                )
                return None
        _stop(context)
        if not context.executing:
            raise MultiCellRejected(
                "Native method lacks actual caller execution", stage="source_call_unavailable"
            )
        if sys._getframe(1).f_code not in context.native_entry_codes:
            raise MultiCellRejected(
                "Direct/reentrant native method is not a source caller edge",
                stage="source_call_unavailable",
            )
        previous_stage = context.stage
        context.stage = context.work_context.stage = name
        _observe(context, "native_enter:" + name, self)
        _stop(context)
        try:
            result = delegate(self, *args, **kwargs)
        except Exception:
            _observe(context, "native_unwind:" + name, self)
            raise
        _stop(context)
        if not tool and name == "__init__":
            context.constructor_completed = True
            if self.tri_verts is not context.seed_reference or self.single_cell is not False:
                raise ValueError("Original constructor lost actual caller seed alias/branch")
        if not tool and name == "pre_mesh" and not context.initial_checked:
            _compare_mesh(context, context.initial_state, initial_stage=True)
            context.initial_checked = True
            context.observer.parent_ids = context.observer.ids
            context.observer.stage = "clip_to_curve"
            context.observer.add(
                "clip_continuation_start",
                dict(
                    initial_cache=initial._public_cache(self),
                    parent_point_ids=context.observer.parent_ids,
                ),
            )
        if not tool and name == "clip_to_curve":
            _compare_mesh(context, context.clip_state)
            context.observer.before_ids = context.observer.ids
            context.observer.lifecycle_active = True
            context.observer.stage = "after_clip_lifecycle"
        if not tool and name in {"__init__", "pre_mesh", "clip_to_curve", "create_core_operators"}:
            _stage_snapshot(context, name)
        _observe(context, "native_return:" + name, result)
        _stop(context)
        context.stage = context.work_context.stage = previous_stage
        return result

    return invoke


for _name, _method in _NATIVE.items():
    setattr(_Runtime, _name, _guard(_name, _method))
for _name, _method in _TOOL_METHODS.items():
    setattr(_Tools, _name, _guard(_name, _method, tool=True))


def _bindings():
    functions = (
        _CELL_INIT,
        _LATTICE,
        _STORES,
        _VORONOI,
        _INDEX,
        _PIPELINE,
        images._construct,
        images._audit,
        images._namespace,
        callers._audit,
        callers._body,
        _mesh_factory,
        _mask_record,
        _project,
        _guard,
        _stage_snapshot,
        _image_state,
        _context,
        _stop,
        _observe,
        _lineage,
        _helper_bindings,
        _entry_codes,
        _compare_mesh,
        _verify_sources,
        _Runtime.clip_and_refine,
        _Caller.__init__,
        _Caller._make_cell_lattice,
        _Caller.cell_index,
        _Caller.__setattr__,
        _Parameters.__init__,
        _Parameters.__setattr__,
        _Parameters.initialize_source_stores,
        _Observer.__init__,
        _Observer.add,
        *[getattr(_Runtime, name) for name in _NATIVE],
        *[getattr(_Tools, name) for name in _TOOL_METHODS],
        callers._Tape.rand,
        callers._Tape.trace,
        images._Tape.trace,
        images._Tape.open,
        images._Tape.spline,
        images._Tape.convex_hull,
        images._Tape.finish_inputs,
    )
    classes = (
        _Runtime,
        _Caller,
        _Parameters,
        _Tools,
        _Observer,
        callers._Tape,
        images._Tape,
        initial._Random,
        initial._Tree,
    )
    return (
        *[atom for cls in classes for atom in atoms._dispatch_bindings(cls)],
        *[atom for fn in functions for atom in atoms._atoms(fn)],
        *[
            atom
            for cls in classes
            for base in cls.__mro__
            for fn in vars(base).values()
            if isinstance(fn, FunctionType)
            for atom in atoms._atoms(fn)
        ],
        *_helper_bindings(),
    )


def _mesh_factory(context, **kwargs):
    _stop(context)
    _check(context)
    if context.kernel is not None or not context.active or not context.executing:
        raise ValueError("Fresh same-caller native constructor already attempted/unavailable")
    if kwargs.get("seed_points") is not context.caller.clust_xy:
        raise ValueError("Native seed_points must be the actual caller.clust_xy object")
    context.seed_reference = context.caller.clust_xy
    context.stage = context.work_context.stage = "mesh_constructor"
    context.mesh_warning_offset = len(context.caught)
    kernel = object.__new__(_Runtime)
    context.kernel = kernel
    _ACTIVE[kernel] = context
    observer = _Observer(context.initial_request.constructor_point_ids, context)
    context.observer = observer
    kernel._cells_observer, kernel._cells_rng = observer, initial._Random(context.rng, observer)
    tools = object.__new__(_Tools)
    _ACTIVE[tools] = context
    tools.__init__(observer)
    kernel._cells_tools = tools
    kernel.__init__(**kwargs)
    _stop(context)
    return kernel


def _namespaces(context):
    def constructor(**kwargs):
        return _mesh_factory(context, **kwargs)

    def log_info(*args):
        _observe(context, "mesh_log", args)

    pipeline = FunctionType(
        _PIPELINE.__code__,
        dict(source.__dict__, logs=SimpleNamespace(log_info=log_info)),
        _PIPELINE.__name__,
        _PIPELINE.__defaults__,
    )
    caller_method = FunctionType(
        _VORONOI.__code__,
        dict(source.__dict__, DECMesh=constructor),
        _VORONOI.__name__,
        _VORONOI.__defaults__,
    )
    return caller_method, pipeline


def _namespace_bindings(context):
    return tuple(
        atom
        for fn in (
            context.lattice_method,
            context.caller_method,
            context.pipeline,
            context.caller_method.__globals__["DECMesh"],
            context.pipeline.__globals__["logs"].log_info,
        )
        for atom in atoms._atoms(fn)
    )


def _lineage(request):
    """Read-only proof of retained typed evidence; never replay or hydration."""
    seen, retained = {}, []

    def visit(value):
        if value is None or type(value) in (str, bool, int, float):
            return value
        if type(value) is bytes:
            return dict(bytes_sha256=hashlib.sha256(value).hexdigest(), length=len(value))
        if id(value) in seen:
            return dict(ref=seen[id(value)])
        token = len(retained)
        seen[id(value)] = token
        retained.append(value)
        if isinstance(value, core.caches.Cache):
            core.caches.validate(value)
            result = dict(cache=value.identity)
        elif isinstance(value, (np.ndarray, np.generic)):
            result = dict(array=core.caches.snapshot(value).identity)
        elif isinstance(value, Mapping):
            result = dict(items=[(visit(key), visit(item)) for key, item in value.items()])
        elif isinstance(value, (tuple, list)):
            result = dict(items=[visit(item) for item in value])
        elif is_dataclass(value) and not isinstance(value, type):
            result = dict(
                type=type(value).__module__ + "." + type(value).__qualname__,
                fields={field.name: visit(getattr(value, field.name)) for field in fields(value)},
            )
        else:
            raise ValueError("Unsupported retained upstream authority object")
        return dict(token=token, **result)

    record = visit(request)
    return tuple(retained), core.records._digest(record)


def _entry_codes(context):
    functions = [_mesh_factory, context.caller_method, context.pipeline]
    for cls in (_Runtime, _Tools):
        for base in cls.__mro__:
            functions.extend(
                value for value in vars(base).values() if isinstance(value, FunctionType)
            )
    return {atom for fn in functions for atom in atoms._atoms(fn) if type(atom) is CodeType}


def _helper_paths():
    paths = []
    for module in (
        callers.source,
        initial,
        initial.source,
        clipped,
        clipped.source,
        lifecycle,
        lifecycle.source,
        images.source,
    ):
        found = set()
        for node in ast.walk(ast.parse(Path(module.__file__).read_text())):
            if not isinstance(node, ast.Attribute):
                continue
            chain, root = [], node
            while isinstance(root, ast.Attribute):
                chain.append(root.attr)
                root = root.value
            if isinstance(root, ast.Name) and root.id in {"np", "math", "copy"}:
                found.add((root.id, *reversed(chain)))
        paths.extend((module, chain) for chain in sorted(found))
    return tuple(paths)


def _helper_bindings():
    result = []
    for module, path in _HELPER_PATHS:
        value = vars(module).get(path[0])
        result.append(value)
        for name in path[1:]:
            value = getattr(value, name, None)
            result.extend(atoms._atoms(value))
    for value in (
        images.RectBivariateSpline,
        images.ConvexHull,
        images.Image.open,
        initial.Delaunay,
        initial.cKDTree,
    ):
        result.extend(atoms._atoms(value))
    return tuple(result)


def _check(context):
    if _verify_sources() != context.producers:
        raise ValueError("Multi-cell source producer changed")
    accounting._check_binding_identity(_bindings(), context.bindings)
    retained, signature = _lineage(context.request)
    if (
        signature != context.parent_signature
        or len(retained) != len(context.parent_references)
        or any(a is not b for a, b in zip(retained, context.parent_references, strict=True))
    ):
        raise ValueError("Original typed upstream source evidence changed")
    if hasattr(context, "caller_method"):
        accounting._check_binding_identity(_namespace_bindings(context), context.namespace_bindings)
    if context.kernel is not None:
        if (
            context.kernel._cells_observer is not context.observer
            or context.kernel._cells_rng.observer is not context.observer
            or context.kernel._cells_rng.rng is not context.rng
            or _ACTIVE.get(context.kernel) is not context
        ):
            raise ValueError("Actual mesh/observer/continuing RNG relationship changed")
    if context.finished:
        caller, mesh = context.caller, context.kernel
        if (
            not context.constructor_completed
            or not context.mesh_assigned
            or not context.mesh_completed
            or not context.index_completed
            or caller.mesh is not mesh
            or mesh.image_mask is not context.mask
            or caller.ecm_verts is not mesh.vcell_verts
            or caller.ecm_verts_unique is not mesh.vor_verts
            or caller.cluster_mask is not context.mask.clipping_matrix
            or caller.cell_centres is not mesh.vor_cents
        ):
            raise ValueError("Original multi-cell alias/mesh/mask completion changed")


def _public_cache(context):
    caller = {k: v for k, v in callers._public(context.caller).items() if k != "mesh"}
    return core.caches.snapshot(_project(context, caller))


def _image_state(context):
    images._file_bytes(context.prelude.image)
    return images._audit(context.image_tape, context.prelude)


def _graphs(context):
    return (
        callers._graph(context.caller, context.p, context.tape),
        callers._graph(context.kernel, context.p, context.tape),
        images._graph(context.image_tape),
    )


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parents=trial.parent_identities,
        parameters=trial.parameter_cache.identity,
        caller=trial.caller_cache.identity,
        mesh=trial.mesh_cache.identity,
        lattice_audit=trial.lattice_audit.identity,
        image_audit=trial.image_audit.identity,
        stages=[(name, cache.identity) for name, cache in trial.stages],
        events=[
            (event.sequence, event.kind, event.method, event.depth, event.payload.identity)
            for event in trial.events
        ],
        ordering=trial.ordering,
        point_ids=trial.point_ids,
        before=trial.stream_before.identity,
        after=trial.stream_after.identity,
        warnings=trial.warnings,
        work=trial.work,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        invalidated_owners=INVALIDATED_OWNERS,
        normalized_parameters_only=True,
        physical_checkpoint_DEC_admitted=False,
    )


class MultiCellOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the fresh owned non-SVG multi-cell source entry")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live multi-cell authority cannot be serialized")

    @property
    def cells(self):
        return _validate(self).caller

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not MultiCellOwner or owner not in _ISSUED:
        raise MultiCellRejected("Issued multi-cell owner unavailable", stage="caller_owner")
    return _ISSUED[owner]


def _validate(owner):
    context = _authority(owner)
    try:
        if context.invalid or context.active or context.thread != get_ident():
            raise ValueError("Stale or active multi-cell owner")
        _check(context)
        if (
            _public_cache(context).identity != context.trial.caller_cache.identity
            or _mesh_cache(context).identity != context.trial.mesh_cache.identity
            or core.caches.snapshot(callers._parameters(context.p)).identity
            != context.trial.parameter_cache.identity
            or initial._rng_stream(context.rng).identity != context.trial.stream_after.identity
            or _image_state(context).identity != context.trial.image_audit.identity
            or core.records._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Multi-cell source cache/parameters/RNG/sealed trial changed")
        if (
            tuple(context.observer.events) != context.trial.events
            or tuple(name for name, _ in context.events) != context.trial.ordering
        ):
            raise ValueError("Original mesh/driver event sequence changed")
        captures.meshes._same_graphs(_graphs(context), context.graphs)
        for cache in (
            context.trial.parameter_cache,
            context.trial.caller_cache,
            context.trial.mesh_cache,
            context.trial.lattice_audit,
            context.trial.image_audit,
            *(cache for _, cache in context.trial.stages),
            *(event.payload for event in context.trial.events),
        ):
            core.caches.validate(cache)
    except Exception as error:
        context.invalid = True
        raise MultiCellRejected(
            "Stale multi-cell caller refused",
            stage="caller_drift",
            trial=context.trial,
            request=context.request,
            source_error=error,
        ) from error
    return context


def _authenticate(request):
    # This may execute nested constructor/pre_mesh/clipping/lifecycle replays.
    # It is numerical work, never an extra independent case or the live parent.
    lifecycle.validate_state(request.lifecycle_request, request.lifecycle_state)


def _controls(context):
    p = context.p
    expected = json.loads(context.prelude.controls_json)
    for name in (
        "single_cell",
        "svg_override",
        "alpha_shape",
        "use_centroids",
        "refine_mesh",
        "maximum_voronoi_steps",
        "voronoi_convergence",
    ):
        value = getattr(p, name)
        if type(value) is not type(expected[name]) or value != expected[name]:
            raise ValueError("Fresh native parameter branch control differs: " + name)
    if p.plot_grid_size != 50:
        raise ValueError("Original plot50 projection changed")


@contextmanager
def _capture(context):
    previous = sys.gettrace()

    def trace(frame, event, arg):
        try:
            if frame.f_code in context.tape.codes:
                context.tape.trace(frame, event, arg)
            context.image_tape.trace(frame, event, arg)
            if event in ("return", "exception") and frame.f_code in context.local_codes:
                context.locals[frame.f_code.co_qualname] = dict(frame.f_locals)
            observer = context.observer
            predicate = None if context.mask is None else context.mask.clipping_function
            if (
                observer is not None
                and event == "return"
                and isinstance(predicate, FunctionType)
                and frame.f_code is predicate.__code__
            ):
                names = frame.f_code.co_varnames[:2]
                x, y = (frame.f_locals[name] for name in names)
                role = (
                    ("centre" if observer.query_count == 0 else "vertex")
                    if observer.current_cell is not None
                    else "rebuild_circumcentre"
                )
                record = _mask_record(context)
                observer.add(
                    "mask_query",
                    dict(
                        x=x,
                        y=y,
                        result=arg,
                        role=role,
                        source_cell_index=observer.current_cell,
                        cell_query_index=observer.query_count,
                        within_closed_window=bool(
                            record["xpts_m"][0] <= x <= record["xpts_m"][-1]
                            and record["ypts_m"][0] <= y <= record["ypts_m"][-1]
                        ),
                    ),
                )
                observer.query_count += 1
        except Exception as capture:
            captures._remember_observation_error(
                context, capture, origin="source_locals", raw=frame
            )
        if previous is not None:
            previous(frame, event, arg)
        return trace

    sys.settrace(trace)
    try:
        yield
    finally:
        sys.settrace(previous)


@contextmanager
def _work(context):
    with accounting._account_prefix(
        context,
        _source_modules=(
            initial.source,
            clipped.source,
            lifecycle.source,
            source,
            images.source,
            callers.source,
        ),
        _entry_names=(
            "__init__",
            "make_voronoi_non_svg",
            "clip_and_refine",
            "cell_index",
            "_make_cell_lattice",
            *initial.OBSERVED_METHODS,
            *lifecycle.METHODS,
        ),
    ):
        previous = sys.getprofile()

        def profile(frame, event, arg):
            if (
                event == "call"
                and frame.f_globals.get("__name__") == __name__
                and frame.f_code.co_name
                in {
                    "invoke",
                    "_mesh_factory",
                    "clip_and_refine",
                    "__init__",
                    "_authenticate",
                    "_execute",
                    "cell_index",
                }
            ):
                if len(context.work) >= 100000:
                    raise ValueError("Bounded prefix work ledger exhausted")
                context.work.append(
                    dict(
                        sequence=len(context.work),
                        phase=frame.f_locals.get("name", context.stage)
                        if frame.f_code.co_name == "invoke"
                        else context.stage,
                        execution="authentication"
                        if context.stage == "isolated_authentication"
                        else "source",
                        layer="wrapper",
                        module=__name__,
                        method=frame.f_code.co_qualname,
                        entry_method=frame.f_locals.get("name", frame.f_code.co_name),
                        source_file=frame.f_code.co_filename,
                        status="entered_not_success_credit",
                    )
                )
            if previous is not None:
                previous(frame, event, arg)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(previous)


def _execute(context):
    request = context.request
    ir, context.initial_state, _, context.clip_state = _parents(request)
    context.initial_request = ir
    binding, seed, context.prelude = ir.upstream
    context.stage = context.work_context.stage = "isolated_authentication"
    _authenticate(request)
    _stop(context)
    context.stage = context.work_context.stage = "fresh_parameters"
    p = object.__new__(_Parameters)
    context.p = p
    _ACTIVE[p] = context
    p.__init__(binding.definition, json.loads(request.configuration_json))
    _controls(context)
    context.parameter_cache = core.caches.snapshot(callers._parameters(p))
    _stage_snapshot(context, "fresh_parameters", cache=context.parameter_cache)
    _stop(context)
    saved = initial.streams.native_stream_manifest(seed.stream_before)["state"]
    context.stage = context.work_context.stage = "continuing_RNG_constructor"
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], np.uint32), saved[2], saved[3], saved[4]))
    context.rng = rng
    tape = context.tape = callers._Tape(rng)
    context.lattice_method = callers._body(tape)
    tape.codes = {_CELL_INIT.__code__, context.lattice_method.__code__}
    context.image_tape = images._Tape(context.prelude.image)
    context.caller_method, context.pipeline = _namespaces(context)
    context.namespace_bindings = _namespace_bindings(context)
    context.native_entry_codes = _entry_codes(context)
    context.local_codes = {
        context.lattice_method.__code__,
        context.caller_method.__code__,
        context.pipeline.__code__,
        *[fn.__code__ for fn in _NATIVE.values()],
    }
    caller = object.__new__(_Caller)
    context.caller = caller
    _ACTIVE[caller] = context
    with _capture(context):
        context.stage = context.work_context.stage = "Cells_constructor"
        caller.__init__(p)
        _stop(context)
        _stage_snapshot(context, "Cells_constructor", caller=True)
        _stop(context)
        context.stage = context.work_context.stage = "Cells_lattice"
        caller._make_cell_lattice(p)
        _stop(context)
        context.lattice_audit = callers._audit(caller, p, tape, seed, binding)
        _stage_snapshot(context, "Cells_lattice", caller=True)
        _stop(context)
        context.stage = context.work_context.stage = "actual_image_picker_mask"
        try:
            _, context.mask = images._construct(context.image_tape, context.prelude, caller)
        finally:
            try:
                context.image_tape.finish_inputs()
            except Exception as capture:
                captures._remember_observation_error(
                    context, capture, origin="image_file_retention", raw=context.image_tape
                )
        _stop(context)
        context.image_audit = _image_state(context)
        _stage_snapshot(context, "actual_image_picker_mask", cache=context.image_audit)
        _stop(context)
        if initial._rng_stream(rng).identity != ir.stream_before.identity:
            raise ValueError("Actual caller/image prefix did not retain the constructor RNG epoch")
        context.stage = context.work_context.stage = "actual_non_SVG_mesh"
        _check(context)
        context.executing = True
        try:
            context.caller_method(caller, p, context.mask)
            _stop(context)
            _stage_snapshot(context, "Voronoi_tail", caller=True)
            _stop(context)
            _compare_mesh(context, request.lifecycle_state)
            context.stage = context.work_context.stage = "cell_index"
            caller.cell_index(p)
            _stop(context)
        finally:
            context.executing = False
    context.finished = True
    _check(context)


def prepare(request):
    _precheck(request)
    if core.records._digest(request_record(request)) != request.identity:
        raise MultiCellRejected(
            "Changed owned multi-cell request", stage="request_identity", request=request
        )
    context = SimpleNamespace(
        request=request,
        stage="preflight",
        thread=get_ident(),
        active=True,
        invalid=False,
        executing=False,
        parameter_running=False,
        constructor_completed=False,
        mesh_assigned=False,
        mesh_completed=False,
        pipeline_started=False,
        initial_checked=False,
        finished=False,
        lattice_started=False,
        index_started=False,
        index_completed=False,
        caller=None,
        kernel=None,
        p=None,
        rng=None,
        tape=None,
        image_tape=None,
        mask=None,
        observer=None,
        locals={},
        events=[],
        stages=[],
        observation_error=None,
        observation_errors=(),
        observation_raw=None,
        observation_origin=None,
        parameter_cache=None,
        lattice_audit=None,
        image_audit=None,
    )
    work = context.work_context = SimpleNamespace(stage="preflight", work=[])
    error = None
    context.producers, context.bindings = _verify_sources(), _bindings()
    context.parent_references, context.parent_signature = _lineage(request)
    with _LOCK, warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        context.caught = caught
        try:
            with _work(work):
                _execute(context)
        except Exception as failure:
            if not isinstance(failure, _CaptureStop):
                error = failure
        finally:
            context.active = context.executing = False
    partial = dict(
        context=context,
        caller=context.caller,
        kernel=context.kernel,
        parameters=context.p,
        rng=context.rng,
        image_tape=context.image_tape,
        mask=context.mask,
        observer=context.observer,
        events=context.events,
        raw_locals=context.locals,
        last_successful_snapshots=context.stages,
        stage=context.stage,
        work=work.work,
        parent_trials=(
            request.lifecycle_request.clip_request.initial_state,
            request.lifecycle_request.clip_state,
            request.lifecycle_state,
        ),
        observation_errors=context.observation_errors,
        observation_raw=context.observation_raw,
        usable_multi_cell_child_available=False,
    )
    if context.observation_error is not None:
        raise MultiCellRejected(
            "Multi-cell observation failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=context.observation_error,
        ) from (error if error is not None else context.observation_error)
    try:
        ir = request.lifecycle_request.clip_request.initial_request
        empty = core.caches.snapshot({})
        trial = Trial(
            request.identity,
            tuple(state.identity for state in partial["parent_trials"]),
            context.parameter_cache if context.parameter_cache is not None else empty,
            empty if context.caller is None else _public_cache(context),
            empty if context.kernel is None else _mesh_cache(context),
            context.lattice_audit if context.lattice_audit is not None else empty,
            context.image_audit if context.image_audit is not None else empty,
            tuple(context.stages),
            tuple(context.observer.events) if context.observer is not None else (),
            tuple(name for name, _ in context.events),
            tuple(context.observer.ids) if context.observer is not None else (),
            ir.upstream[1].stream_before,
            ir.upstream[1].stream_before
            if context.rng is None
            else initial._rng_stream(context.rng),
            tuple(str(w.message) for w in caught),
            tuple(dict(e) for e in work.work),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture:
        raise MultiCellRejected(
            "Multi-cell trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture,
        ) from (error if error is not None else capture)
    if error is not None:
        raise MultiCellRejected(
            "Original multi-cell source failed",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        _check(context)
        context.graphs = _graphs(context)
        child = object.__new__(MultiCellOwner)
        _ISSUED[child] = context
        return child
    except Exception as capture:
        raise MultiCellRejected(
            "Multi-cell child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture,
        ) from capture


def require_initial_geometry(owner, *, phase=None):
    context = _validate(owner)
    raise MultiCellRejected(
        "Multi-cell cellVerts/phase/geometry continuation remains held",
        stage="initial_geometry_held",
        trial=context.trial,
        partial=dict(
            invalidated_owners=INVALIDATED_OWNERS,
            supplied_phase=phase,
            physical_checkpoint_admitted=False,
        ),
    )


_HELPER_PATHS = _helper_paths()
