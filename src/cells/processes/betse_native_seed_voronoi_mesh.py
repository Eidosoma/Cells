"""Prepared same-phase native mesh constructor and caller assignment.

Only a future explicitly adopted image continuation can enter this driver.
Fresh mesh objects derive from the actual imported DECMesh class; their native
constructor/helper CodeTypes are retained unchanged in private helper scopes.
The actual caller and continuing global MT are never reconstructed. Lifecycle,
core operators, caller tail, phase/package and physical admission remain held.
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
from types import CodeType, FrameType, FunctionType, MappingProxyType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_seed_voronoi_image as image
from cells.processes import betse_native_seed_voronoi_mesh_source as source

MODE = "fresh_world_seed_voronoi_mesh_constructor_assignment"
LAW_ID = "betse_same_seed_phase_actual_mesh_constructor_assignment@1"
RELEASE = "CELLS_NATIVE_SEED_VORONOI_MESH_RELEASED"
SOURCE_SHA256 = None
PARENT_SOURCE_SHA256 = None
PARENT_REVIEW_SHA256 = None
PARENT_MODULE = "cells.processes.betse_native_seed_voronoi_image"
PROPOSED_PARENT_CLAIM = "_claim_for_voronoi_mesh"
PROPOSED_PARENT_CHECK = "_check_mesh_authority"
PROPOSED_ROUTER = "_world_voronoi_mesh_api"
ROOT = "Cells.make_voronoi.constructor_prefix"
DISPATCH_LABEL = "Cells.make_voronoi"
WRAPPER = "original_Cells.make_voronoi_wrapper"
CONSTRUCTOR = "DECMesh.__init__"
POINTS = "DECMesh.make_single_cell_points"
NUMPY_HELPERS = ("mean", "cos", "sin", "hstack", "column_stack")
MAX_WORK = image.MAX_WORK
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED, _MESHES = (WeakKeyDictionary() for _ in range(5))
_ACTIVE, _LOCK = [], RLock()
_LITERAL_CLASS = source.VoronoiMeshPrefix
_LITERAL_FUNCTION = _LITERAL_CLASS.make_voronoi
_LITERAL_CODE = _LITERAL_FUNCTION.__code__
_LITERAL_FILE, _PARENT_FILE = Path(source.__file__), Path(image.__file__)
_NATIVE_PINS = tuple(source.NATIVE_PINS.items())


class MeshConstructionRejected(ValueError):
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


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    image_owner: object
    parent_identity: str
    source_identity: str
    mode: str
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    image_trial_identity: str
    before: object
    constructor: object
    cache: object
    stream_before: object
    stream_after: object
    ordering: tuple
    work: tuple
    warnings: tuple
    source_completed: bool
    failure_stage: str | None
    source_failure_type: str | None
    capture_failure_type: str | None
    identity: str


def _digest(value):
    return image._digest(value)


def _body(node):
    items = node.body
    if items and isinstance(items[0], ast.Expr) and isinstance(items[0].value, ast.Constant):
        if isinstance(items[0].value.value, str):
            return items[1:]
    return items


def _selected(nodes):
    """Select original branch expressions and each first constructor store."""
    mapping, branch = nodes[4:6]
    if not isinstance(mapping, ast.Assign) or not isinstance(branch, ast.If):
        raise ValueError("Original make_voronoi branch boundary changed")
    alternate = branch.orelse[0]
    if not isinstance(alternate, ast.If):
        raise ValueError("Original non-single-cell constructor selection changed")
    return [
        mapping,
        ast.If(
            test=branch.test,
            body=[branch.body[0]],
            orelse=[
                ast.If(test=alternate.test, body=[alternate.body[0]], orelse=[alternate.orelse[0]])
            ],
        ),
    ]


def source_plan():
    native = image.prefix.aliases.NATIVE
    if tuple(source.NATIVE_PINS.items()) != _NATIVE_PINS:
        raise ValueError("Original native source pin roster changed")
    for name, expected in _NATIVE_PINS:
        path = native / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Exact original mesh-constructor source required: " + name)
    original = ast.parse((native / "betse/science/cells.py").read_bytes())
    cls = next(n for n in original.body if isinstance(n, ast.ClassDef) and n.name == "Cells")
    method = next(
        n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "make_voronoi"
    )
    copied = ast.parse(Path(source.__file__).read_bytes())
    selected_cls = next(n for n in copied.body if isinstance(n, ast.ClassDef))
    selected_method = next(n for n in selected_cls.body if isinstance(n, ast.FunctionDef))

    def dump(items):
        return ast.dump(ast.Module(body=items, type_ignores=[]), include_attributes=False)

    if dump(_selected(_body(method))) != dump(_body(selected_method)):
        raise ValueError("Literal constructor arguments, branches or assignment changed")
    return dict(
        law=LAW_ID,
        mode=MODE,
        parent=PARENT_MODULE,
        source_pin=SOURCE_SHA256,
        parent_pin=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        native_source=dict(source.NATIVE_PINS),
        constructor_helpers=("__init__", "make_single_cell_points"),
        numpy_helpers=NUMPY_HELPERS,
        native_single_cell_random_draws=2,
        constructor_class="actual imported DECMesh base, fresh guarded runtime",
        constructor_body="unchanged actual CodeType; private transparent helper bindings",
        RNG="same numpy.random.mtrand._rand; original numpy.random.random bound owner",
        allowed_caller_stores=("mesh",),
        order=(
            "original lattice map/branch",
            "constructor completes",
            "exact caller.mesh assignment",
        ),
        stop_before=("init_mesh", "clip_and_refine"),
        prepared_unadopted_parent_hooks={
            PROPOSED_PARENT_CLAIM: (
                "(owner, *, expected, transition, entries) -> exact image context"
            ),
            PROPOSED_PARENT_CHECK: (
                "(transition) -> exact image context; factored immutable ancestry"
            ),
            PROPOSED_ROUTER: "() -> exact current mesh module; same original Cells wrapper",
        },
        parent_hook_adoption=False,
        source_lifecycle_operator_or_scientific_release=False,
        SVG_parent_authority=False,
        work="ordered body/wrapper/helper/authentication/MT-read layers are non-additive",
        invalidated_owners=11,
        held_postcut_cases=12,
    )


def _ready():
    # No owner, descriptor, native import, helper or RNG inspection before pins.
    if not all(
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
        for value in (SOURCE_SHA256, PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise MeshConstructionRejected(
            "Mesh/image producer hooks remain unadopted", stage="unbound_contract"
        )
    for module, expected, original_path in (
        (source, SOURCE_SHA256, _LITERAL_FILE),
        (image, PARENT_SOURCE_SHA256, _PARENT_FILE),
    ):
        path = Path(module.__file__)
        if (
            path != original_path
            or path.is_symlink()
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise MeshConstructionRejected("Reviewed producer changed", stage="producer")
    if tuple(source.NATIVE_PINS.items()) != _NATIVE_PINS:
        raise MeshConstructionRejected("Original native source roster changed", stage="producer")
    for relative, expected in _NATIVE_PINS:
        path = image.prefix.aliases.NATIVE / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise MeshConstructionRejected("Original native source changed", stage="producer")
    api = image.prefix.previous._world_api()
    factory = getattr(api, PROPOSED_ROUTER, None)
    if factory is None or factory() is not sys.modules.get(__name__):
        raise MeshConstructionRejected(
            "Genuine same-instance mesh route unavailable", stage="dispatch_held"
        )
    if not all(
        callable(getattr(image, name, None))
        for name in (
            PROPOSED_PARENT_CLAIM,
            PROPOSED_PARENT_CHECK,
        )
    ):
        raise MeshConstructionRejected(
            "Actual irreversible image hooks unavailable", stage="parent_hooks_held"
        )
    return api


def request_record(request):
    return dict(
        law=LAW_ID,
        mode=request.mode,
        parent=request.parent_identity,
        source=request.source_identity,
        stop_before="mesh lifecycle",
    )


def from_image(owner, *, law_id, mode=MODE):
    _ready()
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise MeshConstructionRejected("Exact explicit constructor mode required", stage="law")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant mesh request")
    if owner in _RETIRED:
        raise MeshConstructionRejected("Image constructor epoch consumed", stage="consumed")
    parent = image._authority(owner)
    if "mesh" in vars(parent.cells):
        raise MeshConstructionRejected(
            "Fresh caller must not already contain mesh", stage="preflight"
        )
    # This authenticates the genuine parent once; it is work, not another case.
    epoch = image._epoch(parent)
    plan = source_plan()
    value = Request(owner, parent.trial.identity, _digest(plan), mode, "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (
        parent,
        parent.trial,
        parent.phase,
        parent.p,
        parent.cells,
        parent.parent.rng,
        parent.tape.mask,
        parent.tape.picker,
        epoch,
        plan,
    )
    return value


def _attempt(context, name, frame, layer):
    row = dict(
        sequence=len(context.work),
        name=name,
        frame=frame,
        layer=layer,
        state="attempted",
        body_started=False,
    )
    if len(context.work) >= MAX_WORK:
        context.overflow_attempt = row
        context.invalid = True
        raise MeshConstructionRejected(
            "Original bounded constructor work ledger exhausted",
            stage=context.stage,
            request=context.request,
            partial=context,
        )
    context.work.append(row)
    context.last_attempt = row
    return row


def _reject(context, row, reason):
    context.invalid = True
    if row is None:
        try:
            row = _attempt(
                context, "unclaimed_constructor_entry", sys._getframe(1), "raw_entry_attempt"
            )
        except BaseException as error:
            context.raw_rejection_capture = (reason, error, sys._getframe(1))
    if row is not None:
        row["state"] = "rejected"
    if context.entry_error is None:
        context.entry_error = MeshConstructionRejected(
            reason,
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=context,
        )
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise image.prefix.literal._CaptureStop() from context.observation_error
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, None, "Constructor lacks its active original thread/epoch")


def _capture_failure(context, error, origin, raw):
    if context.observation_error is None:
        context.observation_error = error
    context.capture_errors += ((origin, error, raw),)


def _rng(context):
    row = _attempt(context, "actual_MT_state_read", sys._getframe(), "metadata")
    value = image.prefix._rng_state(context)
    row["state"] = "returned"
    return value


def _graph(context, *, final=False):
    # Persistent view dictionaries preserve real edges without incorporating
    # growing observation lists into the immutable inherited baseline.
    fields = context.final_fields if final else context.stable_fields
    for target, (_, actual) in zip(fields, context.objects, strict=True):
        target.clear()
        target.update(
            {
                k: v
                for k, v in vars(actual).items()
                if final or actual is not context.cells or k != "mesh"
            }
        )
    view = context.final_view if final else context.stable_view
    if final:
        context.mesh_fields.clear()
        if context.mesh is not None:
            context.mesh_fields.update(vars(context.mesh))
        view.mesh = context.mesh
        view.mesh_attributes = None if context.mesh is None else vars(context.mesh)
    return image.prefix.literal.callers._graph(view, view, context.stable_tape)


def _values(context):
    projector = context.parent.parent.projector
    project = image.prefix.literal._project
    return dict(
        inherited=[
            dict(
                role=role,
                fields=project(
                    projector,
                    {
                        key: value
                        for key, value in vars(actual).items()
                        if actual is not context.cells or key != "mesh"
                    },
                ),
            )
            for role, actual in context.objects
        ],
        mesh=None if context.mesh is None else project(projector, vars(context.mesh)),
        assigned=getattr(context.cells, "mesh", None) is context.mesh and context.mesh is not None,
        image=image._values(context.parent),
    )


def _epoch(context):
    return (
        image.images.core.caches.snapshot(_values(context)).identity,
        _graph(context, final=True),
        _rng(context).identity,
    )


def _same_epoch(context, expected):
    value = _epoch(context)
    _same(value[1][0], expected[1][0])
    if value[0] != expected[0] or value[1][1] != expected[1][1] or value[2] != expected[2]:
        raise ValueError("Observer changed caller/mesh/image/reference/RNG state")


def _same(actual, expected):
    if len(actual) != len(expected) or any(
        a is not b for a, b in zip(actual, expected, strict=True)
    ):
        raise ValueError("Actual callable/object identity changed")


def _bootstrap(context):
    fn, code, namespace = context.checker
    if (
        context.api._independent_atoms is not fn
        or fn.__code__ is not code
        or fn.__globals__ is not namespace
    ):
        raise ValueError("Original independent binding checker changed")
    for name, helper, retained in context.metadata_helpers:
        if globals()[name] is not helper:
            raise ValueError("Constructor metadata helper was replaced: " + name)
        current = fn(helper)
        if len(current) != len(retained) or any(
            a is not b for a, b in zip(current, retained, strict=True)
        ):
            raise ValueError("Constructor metadata helper code/delegate changed: " + name)


def _atoms(function):
    return image._call_atoms(function)


def _helper_bindings(context):
    namespace = context.original_constructor.__globals__
    numpy = namespace["np"]
    return (
        namespace,
        numpy,
        numpy.random,
        numpy.random.mtrand,
        numpy.random.mtrand._rand,
        numpy.pi,
        type(numpy.pi),
        *_atoms(numpy.random.random),
        *(atom for name in NUMPY_HELPERS for atom in _atoms(getattr(numpy, name))),
        namespace["logs"],
        *_atoms(namespace["logs"].log_info),
        namespace["cKDTree"],
        namespace["cKDTree"].query,
        namespace["cKDTree"].__new__,
        namespace["cKDTree"].__init__,
        *(atom for pair in namespace.items() for atom in pair),
    )


def _namespace_bindings(context):
    result = []
    for fn in (*context.mesh_bodies.values(), context.method):
        namespace = fn.__globals__
        result.extend((namespace, *(atom for pair in namespace.items() for atom in pair)))
    tree = context.mesh_bodies["__init__"].__globals__["cKDTree"]
    result.extend(_atoms(tree))
    return tuple(result)


def _bindings(context):
    _bootstrap(context)
    return (
        MODE,
        LAW_ID,
        DISPATCH_LABEL,
        SOURCE_SHA256,
        PARENT_SOURCE_SHA256,
        PARENT_REVIEW_SHA256,
        MAX_WORK,
        NUMPY_HELPERS,
        source.NATIVE_PINS,
        _NATIVE_PINS,
        *(atom for pair in source.NATIVE_PINS.items() for atom in pair),
        PROPOSED_PARENT_CLAIM,
        PROPOSED_PARENT_CHECK,
        PROPOSED_ROUTER,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        _MESHES,
        _ACTIVE,
        _LOCK,
        context.parent_claim,
        context.parent_check,
        context.entries,
        _LITERAL_CLASS,
        _LITERAL_FUNCTION,
        _LITERAL_CODE,
        _LITERAL_FILE,
        _PARENT_FILE,
        source.VoronoiMeshPrefix,
        *_atoms(_LITERAL_FUNCTION),
        *_atoms(context.parent_claim),
        *_atoms(context.parent_check),
        *_atoms(context.original_constructor),
        *_atoms(context.original_points),
        context.original_type,
        *image.prefix.literal._surface(context.original_type),
        context.native_caller_namespace,
        context.native_caller_namespace["DECMesh"],
        context.native_caller_namespace["CellLatticeType"],
        context.native_caller_namespace["CellLatticeType"].HEX,
        context.native_caller_namespace["CellLatticeType"].SQUARE,
        context.runtime_type,
        *image.prefix.literal._surface(context.runtime_type),
        context.numpy_view,
        context.numpy_view.module,
        context.numpy_view.random,
        context.numpy_view.random.context,
        context.logs,
        context.logs.context,
        *_helper_bindings(context),
        *_namespace_bindings(context),
        *(atom for fn in context.mesh_bodies.values() for atom in _atoms(fn)),
        *(
            atom
            for fn in (
                context.method,
                context.factory,
                context.native_wrapper,
                context.native_method,
                image._restore_required_hooks,
            )
            for atom in _atoms(fn)
        ),
        *(atom for cls in (_Numpy, _Random, _Logs) for atom in image.prefix.literal._surface(cls)),
        *(
            atom
            for cls in (Request, Trial, MeshConstructionRejected, MeshConstructorOwner)
            for atom in image.prefix.literal._surface(cls)
        ),
    )


def _check(context):
    if context.active:
        _guard(context)
    _bootstrap(context)
    if (
        _ready() is not context.api
        or context.parent_check(context) is not context.parent
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.image_owner) is not context
        or image._ISSUED.get(context.request.image_owner) is not context.parent
        or getattr(image, "_FORWARDED", {}).get(context.request.image_owner) is not context
        or context.phase is not context.refs[2]
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.p is not context.refs[3]
        or context.cells is not context.refs[4]
        or context.rng is not context.refs[5]
        or context.parent.tape.mask is not context.refs[6]
        or context.parent.tape.picker is not context.refs[7]
    ):
        raise ValueError("Actual image/phase/p/caller/global-MT lineage changed")
    if (
        _digest(request_record(context.request)) != context.request.identity
        or context.request.parent_identity != context.parent.trial.identity
        or context.request.source_identity != _digest(context.refs[9])
    ):
        raise ValueError("Original typed request or parent trial changed")
    _same(_bindings(context), context.bindings)
    # These are the immutable IMAGE-only cache/edges. They contain neither the
    # newly assigned caller.mesh nor a pre-constructor caller/RNG validator.
    image_graph = image.images._graph(context.parent.tape)
    _same(image_graph[0], context.parent.graph[0])
    if (
        image_graph[1] != context.parent.graph[1]
        or image.images.core.caches.snapshot(image._values(context.parent)).identity
        != context.parent.trial.cache.identity
    ):
        raise ValueError("Original image-only values or reference edges changed")
    graph = _graph(context)
    _same(graph[0], context.inherited_graph[0])
    if graph[1] != context.inherited_graph[1]:
        raise ValueError("Inherited reference edges outside mesh assignment changed")
    if not context.draw_active and _rng(context).identity != context.expected_rng.identity:
        raise ValueError("Continuing global MT advanced outside the owned constructor draw")
    if context.mesh is not None and _MESHES.get(context.mesh) is not context:
        raise ValueError("Fresh mesh issuance/context association changed")
    if context.mesh is not None and vars(context.mesh) is not context.mesh_dict:
        raise ValueError("Actual native mesh attribute dictionary was replaced")
    fields = tuple(vars(context.cells))
    if fields not in (context.caller_names, (*context.caller_names, "mesh")):
        raise ValueError("Constructor changed an unrelated caller store")
    if "mesh" in vars(context.cells) and vars(context.cells)["mesh"] is not context.mesh:
        raise ValueError("Original caller.mesh assignment was retargeted")


def _observer_bindings(context=None):
    context = _ACTIVE[-1] if context is None else context
    _bootstrap(context)
    return (
        context.observer_scope,
        context.observer_function,
        *(atom for pair in context.observer_scope.items() for atom in pair),
        *(
            atom
            for fn in (
                _admit,
                _capture,
                _capture_failure,
                _guard,
                _check,
                _epoch,
                _same_epoch,
                _reject,
            )
            for atom in _atoms(fn)
        ),
    )


def _admit(context, frame):
    old = context.admitted.get(id(frame))
    if old is not None and old["frame"] is frame:
        return
    name = context.body_codes[frame.f_code]
    row = _attempt(context, name, frame, "wrapper" if "wrapper" in name else "native_body")
    context.admitted[id(frame)] = row
    _guard(context)
    parent = frame.f_back
    valid = False
    if name == WRAPPER:
        valid = (
            parent is context.driver_frame
            and not context.wrapper_claimed
            and frame.f_locals.get("actual") is context.cells
            and frame.f_locals.get("delegate") is context.native_method
            and frame.f_locals.get("context") is context.parent.parent.prefix
            and frame.f_locals.get("method") == "make_voronoi"
        )
        if valid:
            context.wrapper_claimed, context.wrapper_frame = True, frame
    elif name == ROOT:
        valid = (
            parent is context.body_parent_frame
            and context.root_claimed
            and context.root_frame is None
            and frame.f_locals.get("self") is context.cells
            and frame.f_locals.get("phase") is context.phase
        )
        if valid:
            context.root_frame = frame
    elif name == "constructor_factory_wrapper":
        valid = parent is context.root_frame and not context.factory_claimed
        if valid:
            context.factory_claimed, context.factory_frame = True, frame
    elif name == "mesh_method_wrapper":
        method = frame.f_locals.get("name")
        actual = frame.f_locals.get("actual")
        if method == "__init__":
            valid = parent is context.constructor_dispatch_frame and not context.constructor_claimed
            if valid:
                context.constructor_claimed = True
        elif method == "make_single_cell_points":
            valid = parent is context.constructor_frame and not context.points_claimed
            if valid:
                context.points_claimed = True
        valid = valid and actual is context.mesh
    elif name in (CONSTRUCTOR, POINTS):
        method = "__init__" if name == CONSTRUCTOR else "make_single_cell_points"
        valid = (
            parent is context.delegate_frames.get(method)
            and frame.f_locals.get("self") is context.mesh
        )
        if valid:
            if name == CONSTRUCTOR:
                context.constructor_frame = frame
            else:
                context.points_frame = frame
    elif name == "global_MT_random_wrapper":
        valid = (
            parent is context.points_frame
            and context.draw_claims < 2
            and frame.f_locals.get("self") is context.numpy_view.random
        )
        if valid:
            context.draw_claims += 1
    elif name == "constructor_log_wrapper":
        valid = parent is context.points_frame and not context.log_claimed
        if valid:
            context.log_claimed = True
    elif name == "constructor_tree_wrapper":
        valid = parent is context.constructor_frame and not context.tree_claimed
        if valid:
            context.tree_claimed = True
    elif name == "constructor_list_comprehension":
        valid = parent is context.points_frame
    if not valid:
        _reject(context, row, "Unclaimed/reentrant/raw constructor entry: " + name)
    row["state"] = "admitted"


def _capture(context, frame, event):
    raw = dict(frame.f_locals)
    context.locals[(frame.f_code.co_qualname, event)] = raw
    context.last_frame, context.last_raw_locals = frame, raw
    row = context.admitted.get(id(frame))
    if row is None or row["frame"] is not frame:
        return
    if event == "exception":
        row["source_error"] = context.pending_source_error
    if event == "return" and not row.get("returned", False):
        row["returned"] = True
        row["state"] = "unwound" if row.get("source_error") is not None else "returned"
        if row["state"] == "returned":
            name = context.body_codes[frame.f_code]
            if name == CONSTRUCTOR:
                context.constructor_returned = True
                context.order.append("constructor_body_returned")
            elif name == ROOT:
                if (
                    not context.constructor_returned
                    or getattr(context.cells, "mesh", None) is not context.mesh
                ):
                    raise ValueError("Original constructor completion/assignment order changed")
                context.assignment_completed = True
                context.order.append("exact_caller_mesh_assigned")


def _observe(context, name, raw):
    _guard(context)
    retained = None
    try:
        retained = _epoch(context)
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    if retained is not None:
        try:
            _same_epoch(context, retained)
        except BaseException as error:
            _capture_failure(context, error, name + "_state", raw)


def _operation(context, name, delegate, args, kwargs):
    row = _attempt(context, name, sys._getframe(1), "helper_delegate")
    _guard(context)
    if context.operation_active:
        _reject(context, row, "Reentrant constructor helper delegate")
    _check(context)
    context.operation_active = True
    try:
        try:
            _observe(context, name + "_enter", (args, kwargs))
        except BaseException as error:
            if context.observation_error is None:
                context.observation_error = error
            context.capture_errors += ((name + "_enter_call", error, (args, kwargs)),)
        _guard(context)
        try:
            result = delegate(*args, **kwargs)
        except BaseException as error:
            row["source_error"] = context.last_source_error = error
            raise
        context.last_operation_result = (name, result)
        row["state"] = "returned"
        try:
            _observe(context, name + "_return", result)
        except BaseException as error:
            if context.observation_error is None:
                context.observation_error = error
            context.capture_errors += ((name + "_return_call", error, result),)
        _guard(context)
        _check(context)
        return result
    finally:
        context.operation_active = False


class _Random:
    def __init__(self, context):
        self.context = context

    def rand(self, *args, **kwargs):
        context = self.context
        _guard(context)
        if sys._getframe(1) is not context.points_frame or context.draw_active:
            _reject(context, None, "Global MT draw lacks the actual constructor helper frame")
        context.draw_active = True
        primary = None
        try:
            row = _attempt(context, "numpy.random.random", sys._getframe(), "native_helper")
            result = context.rand(*args, **kwargs)
            context.last_draw_result = result
            row["state"] = "returned"
            context.expected_rng = _rng(context)
            _observe(context, "actual_global_MT_draw_return", result)
            _guard(context)
            return result
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                context.expected_rng = _rng(context)
            except BaseException as error:
                try:
                    _capture_failure(context, error, "MT_after_draw", primary)
                except BaseException as secondary:
                    context.capture_reporting_errors += (
                        ("MT_after_draw", secondary, error, primary),
                    )
                    if context.observation_error is None:
                        context.observation_error = error
            context.draw_active = False

    random = rand


class _Numpy:
    def __init__(self, module, context):
        self.module, self.random = module, _Random(context)

    def __getattr__(self, name):
        return getattr(self.module, name)


class _Logs:
    def __init__(self, context):
        self.context = context

    def log_info(self, *args, **kwargs):
        return _operation(
            self.context, "native_constructor_log", self.context.native_logs.log_info, args, kwargs
        )


def _literal_code():
    payload = Path(source.__file__).read_bytes()
    if hashlib.sha256(payload).hexdigest() != SOURCE_SHA256:
        raise ValueError("Pinned constructor-prefix literal required")
    compiled = compile(payload, str(Path(source.__file__)), "exec", dont_inherit=True)
    cls_code = next(
        v for v in compiled.co_consts if type(v) is CodeType and v.co_name == "VoronoiMeshPrefix"
    )
    code = next(
        v for v in cls_code.co_consts if type(v) is CodeType and v.co_name == "make_voronoi"
    )
    function = vars(source.VoronoiMeshPrefix).get("make_voronoi")
    if (
        source.VoronoiMeshPrefix is not _LITERAL_CLASS
        or function is not _LITERAL_FUNCTION
        or function.__code__ is not _LITERAL_CODE
        or function.__code__ != code
        or function.__code__.co_filename != str(_LITERAL_FILE)
        or Path(source.__file__) != _LITERAL_FILE
        or function.__globals__ is not vars(source)
        or function.__defaults__ is not None
        or function.__kwdefaults__ is not None
        or function.__closure__ is not None
        or function.__dict__
        or function.__annotations__
    ):
        raise ValueError("Loaded constructor-prefix code/signature changed before cloning")
    return function.__code__


def _invoke_mesh(context, name, delegate, actual, args, kwargs, wrapper):
    row = _attempt(context, name + "_dispatch", wrapper, "wrapper_dispatch")
    _guard(context)
    if (
        actual is not context.mesh
        or _MESHES.get(actual) is not context
        or name not in context.mesh_bodies
        or delegate is not context.mesh_bodies[name]
    ):
        _reject(context, row, "Unselected raw mesh method or foreign mesh")
    if id(wrapper) not in context.admitted or not context.admitted[id(wrapper)]["body_started"]:
        _reject(context, row, "Mesh wrapper lacks its claimed source entry")
    _check(context)
    context.delegate_frames[name] = sys._getframe()
    try:
        result = delegate(actual, *args, **kwargs)
        row["state"] = "returned"
        _guard(context)
        return result
    except BaseException as error:
        row["source_error"] = error
        raise


def _construct(context, kwargs, factory_frame):
    _guard(context)
    _check(context)
    if context.mesh is not None or factory_frame is not context.factory_frame:
        _reject(context, None, "Repeated/foreign mesh constructor factory")
    context.constructor_kwargs = kwargs
    context.stage = "native_constructor"
    context.constructor_dispatch_frame = sys._getframe()
    actual = object.__new__(context.runtime_type)
    context.mesh = actual
    context.mesh_dict = vars(actual)
    _MESHES[actual] = context
    actual.__init__(**kwargs)
    _guard(context)
    if not context.constructor_returned:
        raise ValueError("Original constructor has not completed")
    try:
        context.constructor_cache = image.images.core.caches.snapshot(vars(actual))
    except BaseException as error:
        context.capture_errors += (("completed_constructor_cache", error, actual),)
        if context.observation_error is None:
            context.observation_error = error
        _guard(context)
    context.order.append("constructor_factory_returned")
    return actual


def _namespace(context):
    caller_body = context.parent.parent.chain(context.parent.native_method)[-1]
    namespace = caller_body.__globals__
    context.native_caller_namespace = namespace
    original = namespace["DECMesh"]
    if (
        type(original) is not type
        or original.__bases__ != (object,)
        or original.__new__ is not object.__new__
        or sys.modules.get(original.__module__) is None
        or vars(sys.modules[original.__module__]).get("DECMesh") is not original
    ):
        raise ValueError("Actual imported original DECMesh class required")
    callbacks = image.prefix.previous.previous.caches.previous.callbacks
    methods = {name: getattr(original, name) for name in ("__init__", "make_single_cell_points")}
    for name, fn in methods.items():
        callbacks._source_function(fn, "betse/science/math/mesh.py", name, "DECMesh")
    native_tree = ast.parse(
        (image.prefix.aliases.NATIVE / "betse/science/math/mesh.py").read_bytes()
    )
    cls_node = next(
        n for n in native_tree.body if isinstance(n, ast.ClassDef) and n.name == "DECMesh"
    )
    for name, fn in methods.items():
        node = next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == name)
        expected = tuple(ast.literal_eval(n) for n in node.args.defaults)
        actual = () if fn.__defaults__ is None else fn.__defaults__
        if (
            fn.__kwdefaults__ is not None
            or fn.__closure__ is not None
            or fn.__dict__
            or fn.__annotations__
            or fn.__name__ != name
            or fn.__qualname__ != "DECMesh." + name
            or image.images.core.caches.snapshot(actual).identity
            != image.images.core.caches.snapshot(expected).identity
        ):
            raise ValueError("Native constructor/helper signature or hidden delegate changed")
    authenticated = tuple(
        (name, fn, context.api._independent_atoms(fn)) for name, fn in methods.items()
    )
    context.original_type = original
    context.original_constructor, context.original_points = methods.values()
    context.native_numpy = context.original_constructor.__globals__["np"]
    if context.native_numpy is not context.parent.parent.native_numpy:
        raise ValueError("Constructor must use the actual retained NumPy module")
    context.rand = context.native_numpy.random.random
    if (
        context.native_numpy.random.mtrand._rand is not context.rng
        or context.rand.__self__ is not context.rng
    ):
        raise ValueError("Original global random lost its actual MT owner")
    context.native_logs = context.original_constructor.__globals__["logs"]
    context.numpy_view, context.logs = _Numpy(context.native_numpy, context), _Logs(context)

    def tree(*args, **kwargs):
        value = _operation(context, "native_constructor_cKDTree", context.native_tree, args, kwargs)
        context.last_tree = value
        return value

    context.native_tree = context.original_constructor.__globals__["cKDTree"]
    scope = dict(
        context.original_constructor.__globals__,
        np=context.numpy_view,
        logs=context.logs,
        cKDTree=tree,
    )
    for name, fn, retained in authenticated:
        if getattr(original, name) is not fn:
            raise ValueError("Native constructor/helper replaced during namespace preparation")
        _same(context.api._independent_atoms(fn), retained)
    context.mesh_bodies = {
        name: FunctionType(fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__)
        for name, fn in methods.items()
    }

    def wrapper(name, delegate):
        def invoke(actual, *args, **kwargs):
            return _invoke_mesh(context, name, delegate, actual, args, kwargs, sys._getframe())

        return invoke

    surface = {
        name: wrapper(name, context.mesh_bodies.get(name, fn))
        for name, fn in vars(original).items()
        if type(fn) is FunctionType
    }
    context.runtime_type = type(
        "OwnedSeedConstructorMesh", (original,), dict(surface, __module__=__name__, __slots__=())
    )

    def factory(**kwargs):
        return _construct(context, kwargs, sys._getframe())

    context.factory = factory
    code = _literal_code()
    context.method = FunctionType(
        code, dict(source.__dict__, DECMesh=factory, CellLatticeType=namespace["CellLatticeType"])
    )
    context.body_codes = {
        code: ROOT,
        context.native_wrapper.__code__: WRAPPER,
        factory.__code__: "constructor_factory_wrapper",
        next(iter(surface.values())).__code__: "mesh_method_wrapper",
        context.mesh_bodies["__init__"].__code__: CONSTRUCTOR,
        context.mesh_bodies["make_single_cell_points"].__code__: POINTS,
        _Random.rand.__code__: "global_MT_random_wrapper",
        _Logs.log_info.__code__: "constructor_log_wrapper",
        tree.__code__: "constructor_tree_wrapper",
    }
    for fn in methods.values():
        for code in fn.__code__.co_consts:
            if type(code) is CodeType:
                context.body_codes[code] = "constructor_list_comprehension"
    for fn in vars(original).values():
        if type(fn) is FunctionType and fn not in methods.values():
            context.body_codes[fn.__code__] = "forbidden_native_mesh_method"


def _wrapper_guard(context, original, wrapper):
    row = _attempt(context, DISPATCH_LABEL, wrapper, "original_wrapper_guard")
    _guard(context)
    if (
        not context.source_ready
        or type(wrapper) is not FrameType
        or original is not context.parent.parent.prefix
        or not context.wrapper_claimed
        or wrapper is not context.wrapper_frame
        or wrapper.f_back is not context.driver_frame
        or wrapper.f_code is not context.native_wrapper.__code__
        or wrapper.f_locals.get("context") is not original
        or wrapper.f_locals.get("name") != "Cells"
        or wrapper.f_locals.get("method") != "make_voronoi"
        or wrapper.f_locals.get("actual") is not context.cells
        or wrapper.f_locals.get("delegate") is not context.native_method
    ):
        _reject(context, row, "Only the claimed original Cells.make_voronoi wrapper may enter")
    _check(context)
    row["state"] = "returned"


def _dispatch(context, original, label, delegate, actual, args, kwargs, dispatch_frame):
    row = _attempt(context, label, dispatch_frame, "original_native_wrapper_dispatch")
    _guard(context)
    caller = sys._getframe(1)
    native = None if type(dispatch_frame) is not FrameType else dispatch_frame.f_back
    wrapper = None if native is None else native.f_back
    if (
        not context.source_ready
        or type(dispatch_frame) is not FrameType
        or caller is not dispatch_frame
        or caller.f_code is not image.prefix.previous._dispatch_seed_world.__code__
        or native is None
        or native.f_code is not context.parent.parent.native_call_code
        or native.f_locals.get("context") is not original
        or wrapper is None
        or wrapper is not context.wrapper_frame
        or wrapper.f_code is not context.native_wrapper.__code__
        or wrapper.f_back is not context.driver_frame
        or not context.wrapper_claimed
        or context.root_claimed
        or type(label) is not str
        or label != DISPATCH_LABEL
        or original is not context.parent.parent.prefix
        or actual is not context.cells
        or delegate is not context.native_method
        or type(args) is not tuple
        or len(args) != 1
        or args[0] is not context.phase
        or type(kwargs) is not dict
        or kwargs
    ):
        _reject(context, row, "Only original full-frame same-instance Voronoi dispatch may enter")
    context.root_claimed = True
    context.body_parent_frame = sys._getframe()
    _check(context)
    try:
        _observe(context, "constructor_prefix_enter", (actual, context.phase))
    except BaseException as error:
        if context.observation_error is None:
            context.observation_error = error
        context.capture_errors += (("constructor_prefix_enter_call", error, context),)
    _guard(context)
    result = context.method(actual, context.phase)
    context.raw_root_result = result
    row["state"] = "returned"
    try:
        _observe(context, "constructor_prefix_return", result)
    except BaseException as error:
        if context.observation_error is None:
            context.observation_error = error
        context.capture_errors += (("constructor_prefix_return_call", error, result),)
    _guard(context)
    return result


@contextmanager
def _account(context):
    scope = dict(image.prefix.__dict__)
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
                "_Random",
            )
        }
    )
    original = image.prefix._account.__wrapped__
    fn = FunctionType(
        original.__code__, scope, original.__name__, original.__defaults__, original.__closure__
    )
    context.observer_scope, context.observer_function = scope, fn
    context.observer_bindings = _observer_bindings(context)
    with contextmanager(fn)(context):
        yield


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        image_trial=trial.image_trial_identity,
        before=None if trial.before is None else trial.before.identity,
        constructor=None if trial.constructor is None else trial.constructor.identity,
        cache=None if trial.cache is None else trial.cache.identity,
        stream_before=None if trial.stream_before is None else trial.stream_before.identity,
        stream_after=None if trial.stream_after is None else trial.stream_after.identity,
        ordering=trial.ordering,
        work=trial.work,
        warnings=trial.warnings,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        source_failure=trial.source_failure_type,
        capture_failure=trial.capture_failure_type,
    )


def _recover(context):
    try:
        image._restore_required_hooks(context)
    except BaseException as error:
        context.cleanup_errors += (("restore_entry_or_return", error, None),)
    # These independent caller-boundary attempts also cover helper entry or
    # return rejection; no observer/serializer follows without BOTH identities.
    for index in (1, 0):
        try:
            context.restore_setters[index](context.required_hooks[index])
        except BaseException as error:
            context.cleanup_errors += (("required_restore", error, index),)
    samples = []
    for order in ((0, 1), (1, 0)):
        pair = [None, None]
        for index in order:
            try:
                pair[index] = context.restore_getters[index]()
            except BaseException as error:
                pair[index] = error
                context.cleanup_errors += (("required_sample", error, index),)
        samples.append(tuple(pair))
    context.final_hook_samples = tuple(samples)
    healthy = all(
        pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
        for pair in samples
    )
    if context.cleanup_errors and context.observation_error is None:
        context.observation_error = context.cleanup_errors[0][1]
    return healthy


def _partial(context):
    return dict(
        context=context,
        request=context.request,
        image_parent=context.parent,
        image_trial=context.refs[1],
        phase=context.phase,
        parameters=context.p,
        caller=context.cells,
        actual_image_mask=context.refs[6],
        mesh=context.mesh,
        constructor_kwargs=getattr(context, "constructor_kwargs", None),
        raw_locals=context.locals,
        work=context.work,
        events=context.events,
        warnings=context.caught,
        last_draw=getattr(context, "last_draw_result", None),
        last_tree=getattr(context, "last_tree", None),
        primary=context.primary,
        capture_errors=context.capture_errors,
        cleanup_errors=context.cleanup_errors,
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
    try:
        value = MeshConstructionRejected(
            "Same-phase constructor/assignment failed",
            stage=context.stage,
            request=context.request,
            trial=context.trial,
            partial=partial,
            source_error=primary,
            capture_error=capture,
        )
    except BaseException as error:
        context.capture_errors += (("failure_exception", error, partial),)
        if primary is not None:
            raise primary  # noqa: B904 - preserve original identity/cause
        if capture is not None:
            raise capture  # noqa: B904 - preserve original capture identity/cause
        raise
    raise value from primary


def prepare(request, *, enabled=False):
    api = _ready()
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise MeshConstructionRejected("Actual constructor work remains held", stage="release")
    if _ACTIVE:
        _reject(_ACTIVE[-1], None, "Reentrant constructor continuation")
    if type(request) is not Request or request not in _REQUESTS:
        raise MeshConstructionRejected("Actual issued image request required", stage="request")
    with _LOCK:
        if request in _CONSUMED or request.image_owner in _RETIRED:
            raise MeshConstructionRejected(
                "Constructor epoch consumed", stage="consumed", request=request
            )
        refs = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=refs[0],
            phase=refs[2],
            p=refs[3],
            cells=refs[4],
            rng=refs[5],
            api=api,
            thread=get_ident(),
            active=True,
            invalid=False,
            validating=False,
            stage="parent_retirement",
            work=[],
            events=[],
            locals={},
            admitted={},
            order=[],
            caught=[],
            entry_error=None,
            observation_error=None,
            capture_errors=(),
            capture_reporting_errors=(),
            cleanup_errors=(),
            primary=None,
            pending_source_error=None,
            trial=None,
            before=None,
            mesh=None,
            mesh_dict=None,
            source_ready=False,
            constructor_cache=None,
            stream_before=None,
            expected_rng=None,
            wrapper_claimed=False,
            root_claimed=False,
            factory_claimed=False,
            constructor_claimed=False,
            constructor_returned=False,
            assignment_completed=False,
            points_claimed=False,
            draw_claims=0,
            log_claimed=False,
            tree_claimed=False,
            wrapper_frame=None,
            root_frame=None,
            factory_frame=None,
            constructor_frame=None,
            points_frame=None,
            constructor_dispatch_frame=None,
            body_parent_frame=None,
            delegate_frames={},
            draw_active=False,
            operation_active=False,
            callback_codes=frozenset(),
            callback=refs[0].parent.callback,
            forbidden_callback_codes=refs[0].forbidden_callback_codes,
            required_hooks=(sys.getprofile(), sys.gettrace()),
            restore_setters=(sys.setprofile, sys.settrace),
            restore_getters=(sys.getprofile, sys.gettrace),
            observer_scope={},
            observer_function=None,
            driver_frame=sys._getframe(),
        )
        _CONSUMED[request] = _RETIRED[request.image_owner] = context
        _ACTIVE.append(context)
        primary = capture = None
        healthy = False
        try:
            context.parent_claim = getattr(image, PROPOSED_PARENT_CLAIM)
            context.parent_check = getattr(image, PROPOSED_PARENT_CHECK)

            context.entries = MappingProxyType({DISPATCH_LABEL: _dispatch})
            claim = _attempt(context, "actual_image_retirement", sys._getframe(), "authentication")
            if (
                context.parent_claim(
                    request.image_owner,
                    expected=context.parent,
                    transition=context,
                    entries=context.entries,
                )
                is not context.parent
            ):
                raise ValueError("Different image owner retired")
            claim["state"] = "returned"
            image._same_epoch(context.parent, refs[8])
            context.checker = (
                api._independent_atoms,
                api._independent_atoms.__code__,
                api._independent_atoms.__globals__,
            )
            names = (
                "_same",
                "_atoms",
                "_bootstrap",
                "_bindings",
                "_helper_bindings",
                "_graph",
                "_namespace_bindings",
                "_ready",
                "source_plan",
                "_digest",
                "request_record",
                "from_image",
                "prepare",
                "trial_record",
                "_authority",
                "require_lifecycle",
                "_values",
                "_rng",
                "_check",
                "_epoch",
                "_same_epoch",
                "_admit",
                "_capture",
                "_capture_failure",
                "_guard",
                "_reject",
                "_attempt",
                "_namespace",
                "_construct",
                "_invoke_mesh",
                "_dispatch",
                "_wrapper_guard",
                "_literal_code",
                "_operation",
                "_observe",
                "_observer_bindings",
                "_account",
                "_recover",
                "_partial",
                "_failure",
            )
            context.metadata_helpers = tuple(
                (name, globals()[name], api._independent_atoms(globals()[name])) for name in names
            )
            context.native_method = context.parent.native_method
            context.native_wrapper = context.parent.native_wrapper
            context.objects = tuple(context.parent.parent.objects)
            context.caller_names = tuple(vars(context.cells))
            context.stable_fields = [dict() for _ in context.objects]
            context.final_fields = [dict() for _ in context.objects]
            context.stable_view = SimpleNamespace(
                objects=context.objects, fields=context.stable_fields
            )
            context.mesh_fields = {}
            context.final_view = SimpleNamespace(
                objects=context.objects,
                fields=context.final_fields,
                mesh=None,
                mesh_fields=context.mesh_fields,
                mesh_attributes=None,
            )
            context.stable_tape = SimpleNamespace(rng=context.rng, events=(), draws=(), locals={})
            context.inherited_graph = _graph(context)
            context.before = image.images.core.caches.snapshot(_values(context))
            context.stream_before = context.expected_rng = _rng(context)
            context.stage = "constructor_namespace"
            _namespace(context)
            context.bindings = _bindings(context)
            context.source_ready = True
            _check(context)
            context.stage = "literal_constructor_assignment"
            with warnings.catch_warnings(record=True) as caught:
                context.caught = caught
                with _account(context):
                    context.cells.make_voronoi(context.phase)
                    _guard(context)
                    _check(context)
            if (
                not context.assignment_completed
                or not context.constructor_returned
                or context.mesh is None
                or context.cells.mesh is not context.mesh
            ):
                raise ValueError("Original constructor/assignment boundary did not complete")
        except BaseException as error:
            primary = (
                context.entry_error
                if context.entry_error is not None
                else (
                    context.pending_source_error
                    if isinstance(error, image.prefix.literal._CaptureStop)
                    else error
                )
            )
            context.primary = primary
        finally:
            try:
                healthy = _recover(context)
            except BaseException as error:
                context.capture_errors += (("recovery_entry_or_return", error, context),)
                if context.observation_error is None:
                    context.observation_error = error
                for index in (1, 0):
                    try:
                        context.restore_setters[index](context.required_hooks[index])
                    except BaseException as secondary:
                        context.cleanup_errors += (("emergency_restore", secondary, index),)
                pairs = []
                for order in ((0, 1), (1, 0)):
                    pair = [None, None]
                    for index in order:
                        try:
                            pair[index] = context.restore_getters[index]()
                        except BaseException as secondary:
                            pair[index] = secondary
                            context.cleanup_errors += (("emergency_sample", secondary, index),)
                    pairs.append(tuple(pair))
                healthy = all(
                    pair[0] is context.required_hooks[0] and pair[1] is context.required_hooks[1]
                    for pair in pairs
                )
        capture = context.observation_error
        if healthy and context.before is not None:
            try:
                cache = image.images.core.caches.snapshot(_values(context))
                stream_after = _rng(context)
                value = Trial(
                    request.identity,
                    request.parent_identity,
                    context.before,
                    context.constructor_cache,
                    cache,
                    context.stream_before,
                    stream_after,
                    tuple(context.order),
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
                    primary is None and capture is None and context.assignment_completed,
                    context.stage if primary is not None or capture is not None else None,
                    None if primary is None else type(primary).__qualname__,
                    None if capture is None else type(capture).__qualname__,
                    "",
                )
                context.trial = replace(value, identity=_digest(trial_record(value)))
                if primary is None and capture is None:
                    _check(context)
                    context.graph = _graph(context, final=True)
            except BaseException as error:
                context.capture_errors += (("final_sealing", error, context),)
                if capture is None:
                    capture = error
        try:
            healthy = _recover(context) and healthy
        except BaseException as error:
            context.capture_errors += (("post_sealing_recovery", error, context),)
            if capture is None:
                capture = error
            for index in (1, 0):
                try:
                    context.restore_setters[index](context.required_hooks[index])
                except BaseException as secondary:
                    context.cleanup_errors += (
                        ("post_sealing_emergency_restore", secondary, index),
                    )
            healthy = False
        if context.observation_error is not None and capture is None:
            capture = context.observation_error
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
                context.invalid = True
                if primary is not None:
                    raise primary
                if capture is not None:
                    raise capture
                raise RuntimeError("Inherited hooks unavailable; raw constructor context retained")
            _failure(context, primary, capture)
        try:
            owner = object.__new__(MeshConstructorOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            context.capture_errors += (("owner_issuance", error, context),)
            _failure(context, error, capture)


class MeshConstructorOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the actual same-phase image-to-constructor continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No mesh/phase hydration or ordinary checkpoint")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not MeshConstructorOwner or owner not in _ISSUED:
        raise MeshConstructionRejected("Actually issued constructor child required", stage="owner")
    context = _ISSUED[owner]
    if context.active or context.validating or context.invalid:
        _reject(context, None, "Unavailable/reentrant constructor child")
    context.validating = True
    try:
        _check(context)
        if (
            not context.trial.source_completed
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.cache.identity
            != image.images.core.caches.snapshot(_values(context)).identity
        ):
            raise ValueError("Sealed constructor/caller state changed")
        graph = _graph(context, final=True)
        _same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Actual constructor/caller/image reference edges changed")
    except BaseException as error:
        context.invalid = True
        _failure(context, error, context.observation_error)
    finally:
        context.validating = False
    return context


def require_lifecycle(owner):
    context = _authority(owner)
    raise MeshConstructionRejected(
        "Native init_mesh/clip_and_refine remain unadmitted",
        stage="lifecycle_held",
        request=context.request,
        trial=context.trial,
    )
