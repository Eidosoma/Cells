"""Live single-cell DEC source transport, without geometry or parent admission.

Only a fresh owned constructor/pre_mesh/core execution can create this handle.
It retains that exact kernel and its object graph; caches are evidence, never
instructions for constructing a replacement mesh. The surrounding native Cells,
simulation and picker owners are still unavailable for the full post-cut caller.
"""

import copy
import hashlib
import struct
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from threading import get_ident
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_native_single_cell_core_preparation as core
from cells.processes import betse_post_cut_mesh_contact_source as source

LAW_ID = "betse_owned_single_cell_live_DEC_source_transport@1"
HELD_UNQUALIFIED_SOURCE_STAGE = True
SOURCE_SHA256 = "432e2453c4b5e0a4d46eb46c79bb1440093a042caa44ac2d00e09d20130de4b7"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
_AUTHORITIES = WeakKeyDictionary()
_RUNTIME_TOKENS = WeakKeyDictionary()
_ACTIVE_RUNTIMES = WeakKeyDictionary()
_METHODS = ("cut_mesh", "create_tri_map", "create_mappings", "create_core_operators")
_NATIVE_CUT = source.MeshKernel.cut_mesh
_NATIVE_METHODS = {name: getattr(core._Runtime, name) for name in _METHODS[1:]}


class _Runtime(core._Runtime):
    # Guards add no native calculations. During the actual source driver,
    # mapping/core calls retain their original observed methods and events.
    def cut_mesh(self, targets):
        return _cut_authority(_runtime_authority(self), targets)

    def __reduce_ex__(self, protocol):
        raise TypeError("A live native mesh cannot be serialized as source authority")

    def create_tri_map(self, *args, **kwargs):
        return _call_native_method(self, "create_tri_map", args, kwargs)

    def create_mappings(self, *args, **kwargs):
        return _call_native_method(self, "create_mappings", args, kwargs)

    def create_core_operators(self, *args, **kwargs):
        return _call_native_method(self, "create_core_operators", args, kwargs)


@dataclass(frozen=True, slots=True)
class MeshAliases:
    """Only the two literal mesh aliases after make_voronoi's mesh branch.

    This is an alias carrier, not a native Cells owner. In particular it does
    not synthesize cell_index, cell geometry, environment maps or simulation.
    Aliases retain their original references even when cutting rebinds fields.
    """

    mesh: object
    ecm_verts: object
    ecm_verts_unique: object


@dataclass(slots=True)
class SourceCallAttempt:
    """Raw source return/failure on the live object, including partial mutation."""

    runtime: core._LiveCoreTrial
    aliases: MeshAliases
    method: str
    args: tuple
    kwargs: dict
    returned: object = None
    source_error: BaseException | None = None
    warning_records: tuple = ()
    finished: bool = False
    source_completed: bool = False

    @property
    def targets(self):
        return self.args[0] if self.method == "cut_mesh" else None


@dataclass(slots=True)
class _Authority:
    runtime: core._LiveCoreTrial
    aliases: MeshAliases
    request_signature: str
    state_signature: str
    graph_objects: tuple
    graph_record: object
    producers: object
    methods: tuple
    status: str = "ready_source_trial"
    attempt: SourceCallAttempt | None = None
    active_thread: int | None = None
    token: object = field(default_factory=object)


class NativeParentRejected(ValueError):
    def __init__(self, reason, *, stage, runtime=None, partial=None):
        super().__init__(reason)
        self.stage, self.runtime, self.partial = stage, runtime, partial


class SingleCellDECSourceParent:
    """Process-local callable source capability; no pickle/checkpoint transport."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare with an owned core Request")

    def __reduce_ex__(self, protocol):
        raise TypeError("A live DEC source capability cannot be serialized as a parent")

    @property
    def mesh(self):
        return _validate(self).runtime.kernel

    @property
    def aliases(self):
        return _validate(self).aliases

    @property
    def state(self):
        return _authority(self).runtime.state

    @property
    def last_attempt(self):
        # Failure inspection must not require the pre-cut cache to survive.
        return _authority(self).attempt

    def cut_mesh(self, targets):
        return cut_mesh(self, targets)


def _verify_sources():
    core._verify_sources()
    if hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("Changed literal native post-cut source")
    return {
        str(Path(module.__file__).resolve()): hashlib.sha256(
            Path(module.__file__).read_bytes()
        ).hexdigest()
        for module in (core, source)
    } | {str(Path(__file__).resolve()): hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}


def _check_request(request):
    if type(request) is not core.Request:
        raise NativeParentRejected(
            "Actual typed owned single-cell core Request required; no cache or polygon substitute",
            stage="upstream_request_owner",
        )
    core._precheck(request.initial_request, request.initial_state)


def _request_signature(request):
    signature = core.records._digest(core.request_record(request))
    if signature != request.identity:
        raise ValueError("Changed owned source request identity")
    return signature


def _state_signature(state):
    if (
        type(state) is not core.State
        or state.core_source_completed is not True
        or state.status != "source_core_operators_completed_unqualified"
        or any(
            v is not None for v in (state.failure_stage, state.failure_type, state.failure_message)
        )
    ):
        raise ValueError("A successful sealed source core trial is required")
    for cache in (
        state.constructed_cache,
        state.before_cache,
        state.cache,
        *(event.payload for event in state.events),
    ):
        core.caches.validate(cache)
    signature = core.records._digest(core.state_record(state))
    if signature != state.identity:
        raise ValueError("Changed core source trial identity")
    return signature


def _events(events):
    return tuple((e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in events)


def _graph(runtime, aliases):
    """Retain references plus a bounded graph, including ndarray views and cycles.

    Cache hashes alone cannot detect replacement by equal arrays or broken
    aliases. Object references stay local; the record uses traversal tokens.
    No scalar geometry, native constructor, RNG draw or evidence decoder runs.
    """
    objects, nodes, seen = [], [], {}

    def visit(value, depth=0):
        if depth > 48 or len(nodes) > core.caches.MAX_TREE_NODES:
            raise ValueError("Live source object graph exceeds its evidence bound")
        if value is None or type(value) in (str, int, bool):
            return (type(value).__name__, value)
        if type(value) is float:
            return ("float", struct.pack(">d", value).hex())
        if isinstance(value, np.generic):
            return ("numpy_scalar", value.dtype.str, value.tobytes().hex())
        if isinstance(value, bytes):
            return ("bytes", hashlib.sha256(value).hexdigest())
        key = id(value)
        if key in seen:
            return ("ref", seen[key])
        token = len(objects)
        seen[key] = token
        objects.append(value)
        node = dict(token=token, type=type(value).__module__ + "." + type(value).__qualname__)
        nodes.append(node)
        if isinstance(value, np.ndarray):
            if value.size > core.caches.MAX_ARRAY_ELEMENTS:
                raise ValueError("Live array exceeds the bounded source axis")
            children = [value.base]
            if value.dtype.hasobject:
                children.extend(value.flat)
        elif isinstance(value, dict):
            children = [part for pair in value.items() for part in pair]
        elif isinstance(value, (list, tuple, set, frozenset)):
            children = list(value)
        elif value is aliases:
            children = [value.mesh, value.ecm_verts, value.ecm_verts_unique]
        elif (
            value is runtime.kernel
            or value is runtime.observer
            or value is runtime.kernel._cells_rng
        ):
            children = [vars(value)]
        else:
            # RNG objects and immutable event records retain exact identity.
            children = []
        node["children"] = [visit(child, depth + 1) for child in children]
        return ("ref", token)

    roots = [visit(value) for value in (runtime.kernel, aliases, runtime.observer, runtime.rng)]
    return tuple(objects), dict(roots=roots, nodes=nodes)


def _authority(parent):
    if type(parent) is not SingleCellDECSourceParent or parent not in _AUTHORITIES:
        raise NativeParentRejected(
            "Fresh process-local native execution authority unavailable",
            stage="live_authority_unavailable",
        )
    return _AUTHORITIES[parent]


def _runtime_authority(mesh):
    authority = getattr(mesh, "_cells_dec_source_authority", None)
    if (
        type(mesh) is not _Runtime
        or type(authority) is not _Authority
        or authority.runtime.kernel is not mesh
        or _RUNTIME_TOKENS.get(mesh) is not authority.token
    ):
        raise NativeParentRejected(
            "Callable mesh lacks its original process-local source authority",
            stage="live_authority_unavailable",
        )
    return authority


def _check_runtime(runtime, aliases):
    if type(runtime) is not core._LiveCoreTrial or type(runtime.kernel) is not _Runtime:
        raise ValueError("Require the actual owned callable runtime, not an inspection object")
    mesh, observer, state = runtime.kernel, runtime.observer, runtime.state
    if (
        mesh._cells_observer is not observer
        or mesh._cells_rng.rng is not runtime.rng
        or mesh._cells_rng.observer is not observer
        or observer.stack
        or observer.ids != state.point_ids
        or _events(observer.events) != _events(state.events)
        or tuple(str(w.message) for w in runtime.warning_records) != state.warnings
    ):
        raise ValueError("Changed actual observer, event, occurrence or RNG ownership")
    if runtime.request.identity != state.request_identity:
        raise ValueError("Live runtime belongs to a different source request")
    if (
        aliases.mesh is not mesh
        or aliases.ecm_verts is not mesh.vcell_verts
        or aliases.ecm_verts_unique is not mesh.vor_verts
    ):
        raise ValueError("Lost original make_voronoi mesh aliases")
    if core.caches.snapshot(core.initial._public_cache(mesh)).identity != state.cache.identity:
        raise ValueError("Changed actual core cache")
    if core.initial._rng_stream(runtime.rng).identity != state.stream_after.identity:
        raise ValueError("Changed actual source RNG epoch")


def _validate_authority(authority):
    if authority.status != "ready_source_trial":
        raise NativeParentRejected(
            "Live source parent was consumed or invalidated; retain its original attempt",
            stage="live_authority_consumed",
            runtime=authority.runtime,
        )
    try:
        if (
            _RUNTIME_TOKENS.get(authority.runtime.kernel) is not authority.token
            or authority.active_thread is not None
            or _ACTIVE_RUNTIMES.get(authority.runtime.kernel) is not None
        ):
            raise ValueError("Changed process-local constructor or execution authority")
        if _verify_sources() != authority.producers:
            raise ValueError("Source producer changed since live execution")
        if _request_signature(authority.runtime.request) != authority.request_signature:
            raise ValueError("Changed request")
        if _state_signature(authority.runtime.state) != authority.state_signature:
            raise ValueError("Changed sealed source trial")
        _check_runtime(authority.runtime, authority.aliases)
        if _method_bindings() != authority.methods:
            raise ValueError("Changed callable native method binding")
        objects, record = _graph(authority.runtime, authority.aliases)
        if (
            record != authority.graph_record
            or len(objects) != len(authority.graph_objects)
            or any(
                actual is not retained
                for actual, retained in zip(objects, authority.graph_objects, strict=True)
            )
        ):
            raise ValueError("Changed live source object identities or alias relationships")
    except Exception as error:
        authority.status = "invalidated_source_drift"
        raise NativeParentRejected(
            "Live source authority changed; no replay or reconstruction attempted",
            stage="live_authority_drift",
            runtime=authority.runtime,
            partial=dict(original_error=error, aliases=authority.aliases),
        ) from error
    return authority


def _validate(parent):
    return _validate_authority(_authority(parent))


def _method_bindings():
    return (
        *tuple(getattr(_Runtime, name) for name in _METHODS),
        _NATIVE_CUT,
        *tuple(_NATIVE_METHODS[name] for name in _METHODS[1:]),
    )


def _call_native_method(mesh, name, args, kwargs):
    if core._preparing_runtime(mesh):
        return _NATIVE_METHODS[name](mesh, *args, **kwargs)
    authority = _runtime_authority(mesh)
    if _ACTIVE_RUNTIMES.get(mesh) == get_ident():
        # cut_mesh mutates the object before calling these native methods.
        # Only that guarded call's dynamic extent may use the intermediate
        # state; it neither revalidates an obsolete cache nor mints a parent.
        return _NATIVE_METHODS[name](mesh, *args, **kwargs)
    return _invoke_authority(authority, name, args, kwargs)


def prepare(request, *, law_id):
    """Numerical source work when released: existing replay plus one actual core run.

    This adds no authentication replay. It retains the very kernel that the
    core prerequisite authenticates and seals; positive execution is held.
    Original CorePrerequisiteRejected errors and failed/partial diagnostics
    pass through without a live carrier or usable parent handle.
    """
    if type(law_id) is not str or law_id != LAW_ID:
        raise NativeParentRejected("Explicit source transport law required", stage="opt_in")
    _check_request(request)
    producers = _verify_sources()
    runtime = core.prepare(request, _runtime_type=_Runtime)
    authority = None
    try:
        aliases = MeshAliases(runtime.kernel, runtime.kernel.vcell_verts, runtime.kernel.vor_verts)
        _check_runtime(runtime, aliases)
        request_signature = _request_signature(request)
        state_signature = _state_signature(runtime.state)
        authority = _Authority(
            runtime,
            aliases,
            request_signature,
            state_signature,
            (),
            None,
            producers,
            _method_bindings(),
            status="building_source_transport",
        )
        # Native callers receive this exact kernel. Its observational wrapper
        # must retain attempts too, even when called without the outer handle.
        # The private field is excluded from native public-cache/event capture.
        runtime.kernel._cells_dec_source_authority = authority
        authority.graph_objects, authority.graph_record = _graph(runtime, aliases)
        if _verify_sources() != producers:
            raise ValueError("Source producer changed during execution")
        authority.status = "ready_source_trial"
        parent = object.__new__(SingleCellDECSourceParent)
        _RUNTIME_TOKENS[runtime.kernel] = authority.token
        _AUTHORITIES[parent] = authority
        return parent
    except Exception as error:
        if authority is not None:
            authority.status = "invalidated_transport_capture"
            _RUNTIME_TOKENS.pop(runtime.kernel, None)
        raise NativeParentRejected(
            "Live transport sealing failed after source core; retain that exact trial/runtime",
            stage="live_transport_capture",
            runtime=runtime,
        ) from error


def cut_mesh(parent, targets):
    """One source call on the original object; return/raise the native result unchanged.

    No selection coercion, sorting, graph reconstruction, array copy, or state
    restore occurs. A failed call consumes the handle and keeps partial mutation
    and the original exception chain. A complete native result grants no owner
    rebuild, physical, general-parent or checkpoint admission.
    """
    return _cut_authority(_authority(parent), targets)


def _cut_authority(authority, targets):
    return _invoke_authority(authority, "cut_mesh", (targets,), {})


def _invoke_authority(authority, name, args, kwargs):
    authority = _validate_authority(authority)
    if name == "cut_mesh":
        targets = args[0]
        if not isinstance(targets, np.ndarray) or targets.ndim != 1 or targets.size > 7:
            raise NativeParentRejected(
                "Bounded original picker array required", stage="selection_axis"
            )
    attempt = SourceCallAttempt(authority.runtime, authority.aliases, name, args, kwargs)
    authority.attempt, authority.status = attempt, "consumed_source_method_attempt"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        authority.active_thread = get_ident()
        _ACTIVE_RUNTIMES[authority.runtime.kernel] = authority.active_thread
        try:
            method = _NATIVE_CUT if name == "cut_mesh" else _NATIVE_METHODS[name]
            returned = method(authority.runtime.kernel, *args, **kwargs)
            attempt.returned, attempt.source_completed = returned, True
            return returned
        except BaseException as error:
            attempt.source_error = error
            raise
        finally:
            # Reference retention only: a serializer cannot erase source failure.
            _ACTIVE_RUNTIMES.pop(authority.runtime.kernel, None)
            authority.active_thread = None
            attempt.warning_records, attempt.finished = tuple(caught), True


def source_record(parent):
    """Inspection of source authority and holds, never a parent decoder."""
    authority = _authority(parent)
    return dict(
        law=LAW_ID,
        status=authority.status,
        core_request_identity=authority.runtime.request.identity,
        core_state_identity=authority.runtime.state.identity,
        source_producers=dict(authority.producers),
        live_graph=copy.deepcopy(authority.graph_record),
        callable_methods=list(_METHODS),
        native_method_qualification={name: "unrun" for name in _METHODS},
        aliases=["ecm_verts is mesh.vcell_verts", "ecm_verts_unique is mesh.vor_verts"],
        cells_owner_available=False,
        native_initial_qualification="19/22 accuracy qualification open",
        stable_independent_geometry="0/9 unchanged",
        independent_geometry_qualified=False,
        executable_DEC_parent_admitted=False,
        physical_geometry_admitted=False,
        ordinary_continuation_admitted=False,
        checkpoint_admitted=False,
        invalidated_owners=list(INVALIDATED_OWNERS),
    )


def require_post_cut_parent(parent, *, declarations=None):
    authority = _validate(parent)
    raise NativeParentRejected(
        "Callable DEC source mesh lacks the later native Cells/sim/picker owner chain",
        stage="post_cut_owner_authority_unavailable",
        runtime=authority.runtime,
        partial=dict(
            source=source_record(parent),
            supplied_declarations=declarations,
            required_authority=(
                "remaining make_voronoi image-mask ownership",
                "cell_index and cell/membrane construction",
                "environment and cell graph mappings",
                "native simulation, tissue handler and picker owners",
            ),
        ),
    )
