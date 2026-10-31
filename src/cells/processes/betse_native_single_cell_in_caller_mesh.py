"""Constructor -> caller.mesh assignment -> literal init_mesh on one live RNG.

Parent epochs are retired before attempted authentication/work. Only a sealed
successful child is usable; raw failed construction/assignment/init state and
the original parent trials remain inspectable. No standalone object is attached,
no stream is reconstructed/reset, and no cache/phase/height is supplied.
"""

import hashlib
import sys
import warnings
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

import numpy as np

from cells.processes import betse_native_single_cell_image_mask as images

core, callers = images.core, images.callers
LAW_ID = "betse_owned_single_cell_in_caller_mesh_init@1"
INVALIDATED_OWNERS = core.INVALIDATED_OWNERS
HELD_UNQUALIFIED_SOURCE_STAGE = True
_ACTIVE, _ISSUED = WeakKeyDictionary(), WeakKeyDictionary()
_FORWARDED = WeakKeyDictionary()
# Bound at module load and retained again per attempt; no numerical body edit.
_CONSTRUCTOR = core._Runtime.__init__
_PRE_MESH = core._Runtime.pre_mesh
_CORE = core._Runtime.create_core_operators
_INIT_MESH = core.lifecycle.source.LifecycleKernel.init_mesh
_TRI_MAP = core._Runtime.create_tri_map
_MAPPINGS = core._Runtime.create_mappings
_EXPLICIT_METHODS = (
    "__init__",
    "init_mesh",
    "pre_mesh",
    "create_tri_map",
    "create_mappings",
    "create_core_operators",
)
# Resolve the entire inherited native/helper surface once, retaining the
# original observed bodies. Object's infrastructure is not native mesh work.
_INHERITED_NATIVE = {
    name: getattr(core._Runtime, name)
    for base in core._Runtime.__mro__
    if base is not object
    for name, method in vars(base).items()
    if callable(method) and name not in _EXPLICIT_METHODS
}
GUARDED_NATIVE_METHODS = (*_EXPLICIT_METHODS, *_INHERITED_NATIVE)
DEPENDENCIES = {
    "betse_native_single_cell_caller_lattice": (
        "da9b3104796c1fee36c29a4ef13149b26792ea9ad0b0ba9519567296776ee644"
    ),
    "betse_native_single_cell_image_mask": (
        "11927f53f029f444f47e7d0283dbcf36887e287d58293f9ac5eaa7d8b41bc334"
    ),
    "betse_native_single_cell_core_preparation": (
        "b1db6df0c74f92d4526b9854c7d01838552e2ec044858e64e43c93f7ce8b068a"
    ),
}


@dataclass(frozen=True, slots=True)
class Request:
    image_owner: images.ImageOwner
    identity: str


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    caller_parent_identity: str
    image_parent_identity: str
    constructor_cache: object
    pre_mesh_cache: object
    final_cache: object
    occurrence_ids: tuple
    events: tuple
    ordering: tuple
    stream_before: object
    stream_after: object
    warnings: tuple
    work: tuple
    source_completed: bool
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class ContinuationRejected(ValueError):
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


def _context(mesh):
    value = _ACTIVE.get(mesh)
    if value is None or value.thread != get_ident():
        raise ContinuationRejected(
            "Native mesh call lacks active in-caller driver authority",
            stage="source_call_unavailable",
        )
    return value


def _enter_step(context, name):
    if name in context.steps:
        raise ValueError("Repeated/reentrant source step: " + name)
    context.steps[name] = "started"
    context.stage = name
    context.order.append(name + "_enter")


class _Runtime(core._Runtime):
    def __init__(self, **kwargs):
        context = _context(self)
        _enter_step(context, "constructor")
        context.work.append(dict(kind="continuing_constructor", phase="continuation", started=True))
        _CONSTRUCTOR(self, **kwargs)
        context.constructor_completed = True
        context.steps["constructor"] = "completed"

    def init_mesh(self):
        context = _context(self)
        if context.caller.mesh is not self or not context.constructor_completed:
            raise ValueError(
                "Actual constructor must finish and caller.mesh must be assigned before init_mesh"
            )
        _enter_step(context, "init_mesh")
        context.work.append(dict(kind="init_mesh", phase="continuation", started=True))
        value = _INIT_MESH(self)
        context.steps["init_mesh"] = "completed"
        return value

    def pre_mesh(self):
        context = _context(self)
        if context.steps.get("init_mesh") != "started":
            raise ValueError("pre_mesh requires the actual active init_mesh")
        _enter_step(context, "pre_mesh")
        context.work.append(dict(kind="pre_mesh", phase="continuation", started=True))
        _PRE_MESH(self)
        context.before = core.caches.snapshot(core.initial._public_cache(self))
        parent = context.core_request.initial_state
        if (
            context.before.identity != parent.cache.identity
            or self._cells_observer.ids != parent.retained_point_ids
            or core.initial._rng_stream(context.rng).identity != parent.stream_after.identity
            or tuple(str(w.message) for w in context.caught) != parent.warnings
        ):
            raise ValueError(
                "Actual in-caller pre_mesh cache/IDs/RNG/warnings differ from retained source"
            )

        def signature(events):
            return tuple(
                (e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in events
            )

        if signature(self._cells_observer.events) != signature(parent.events):
            raise ValueError("Actual in-caller constructor/pre_mesh event prefix differs")
        attributes = core.initial._public_cache(self)
        if (
            set(core.REQUIRED_PRE_MESH_FIELDS) - set(attributes)
            or self.make_all_operators is not False
            or self.single_cell is not True
            or self.n_tverts != len(self._cells_observer.ids)
        ):
            raise ValueError("Actual native single-cell fields/flags/axes differ")
        context.order.append("pre_mesh_return")
        context.steps["pre_mesh"] = "completed"

    def create_core_operators(self):
        context = _context(self)
        if context.before is None or context.steps.get("pre_mesh") != "completed":
            raise ValueError("Core operators require the actual completed pre_mesh")
        _enter_step(context, "core_operators")
        context.work.append(dict(kind="core_operators", phase="continuation", started=True))
        attributes = core.initial._public_cache(self)
        self._cells_observer.add(
            "owned_single_cell_core_start",
            dict(cache=attributes, point_ids=self._cells_observer.ids),
        )
        _CORE(self)
        after = core.initial._public_cache(self)
        keys = core._cache_keys(context.before)
        if (
            core.caches.snapshot({key: after[key] for key in keys}).identity
            != context.before.identity
            or set(after) - set(keys) != {"delta_tri_0", "delta_tri_0_inv"}
            or np.shape(self.delta_tri_0) != (self.n_tedges, self.n_tverts)
            or np.shape(self.delta_tri_0_inv) != (self.n_tverts, self.n_tedges)
            or not core.caches.snapshot(after).all_finite
            or core.initial._rng_stream(context.rng).identity
            != context.core_request.initial_state.stream_after.identity
        ):
            raise ValueError(
                "Actual core source result changed source axes/cache/RNG or is nonfinite"
            )
        context.core_completed = True
        context.order.append("core_return")
        context.steps["core_operators"] = "completed"
        context.stage = "init_mesh_tail"

    def create_tri_map(self):
        _context(self)
        return _TRI_MAP(self)

    def create_mappings(self, ignoreb=False):
        _context(self)
        return _MAPPINGS(self, ignoreb=ignoreb)

    def __reduce_ex__(self, protocol):
        raise TypeError("A live in-caller mesh cannot be serialized as authority")


def _guard_inherited(name):
    def guarded(self, *args, **kwargs):
        # This must precede even initial._observe's stack/event/cache work.
        # Legitimate nested calls keep the same actual runtime and RNG.
        _context(self)
        return _INHERITED_NATIVE[name](self, *args, **kwargs)

    # Do not expose an unguarded delegate through a __wrapped__ attribute.
    guarded.__name__ = name
    return guarded


for _native_name in _INHERITED_NATIVE:
    setattr(_Runtime, _native_name, _guard_inherited(_native_name))


def _verify_sources():
    pins = images._verify_sources()
    for module in (core, core.lifecycle, core.lifecycle.source, images, callers):
        digest = hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
        expected = DEPENDENCIES.get(module.__name__.rsplit(".", 1)[-1])
        if expected is not None and digest != expected:
            raise ValueError("Changed in-caller source prerequisite: " + module.__name__)
        pins[str(Path(module.__file__).resolve())] = digest
    pins[str(Path(__file__).resolve())] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    return pins


def _bindings():
    methods = (
        _CONSTRUCTOR,
        _PRE_MESH,
        _CORE,
        _INIT_MESH,
        _TRI_MAP,
        _MAPPINGS,
        _Runtime.__init__,
        _Runtime.init_mesh,
        _Runtime.pre_mesh,
        _Runtime.create_core_operators,
        _Runtime.create_tri_map,
        _Runtime.create_mappings,
        core.initial._Observer.add,
        core.initial._Random.random,
        *_INHERITED_NATIVE.values(),
        *(getattr(_Runtime, name) for name in _INHERITED_NATIVE),
    )
    return tuple(
        part
        for method in methods
        for part in (
            method,
            method.__code__,
            *(c.cell_contents for c in (method.__closure__ or ())),
        )
    )


@contextmanager
def _account_work(context):
    """Observe actual nested source entries; they are work, never extra cases.

    This does not replace the resource runner's profile-based native blockade.
    No source call, RNG allocation or replay is introduced for accounting.
    """
    previous = sys.gettrace()
    if previous is not None:
        raise ValueError("An existing trace prevents complete source-work accounting")
    modules = {
        m.__name__
        for m in (core, core.initial, core.initial.image_stage, core.initial.image_stage.lattice)
    }
    kernels = {core.initial.source.__name__, core.lifecycle.source.__name__}
    entries = {
        "prepare",
        "generate",
        "from_initial",
        "from_image_prelude",
        "validate_request",
        "validate_state",
        "validate_prelude",
        "random",
    }

    def trace(frame, event, arg):
        if event == "call":
            module = frame.f_globals.get("__name__", "")
            name = frame.f_code.co_name
            if module in kernels or module in modules and (name in entries or name == "invoke"):
                if len(context.work) >= 100_000:
                    raise ValueError("Source-work accounting bound exceeded")
                context.work.append(
                    dict(
                        kind="python_source_entry",
                        phase=context.phase,
                        module=module,
                        method=frame.f_code.co_qualname,
                        observed_method=frame.f_locals.get("name") if name == "invoke" else None,
                        line=frame.f_code.co_firstlineno,
                    )
                )
        return None

    sys.settrace(trace)
    try:
        yield
    finally:
        sys.settrace(previous)


def _parents(owner, *, validate):
    image = images._validate_owner(owner) if validate else images._authority(owner)
    caller_owner = image["request"].caller
    caller = callers._validate_owner(caller_owner) if validate else callers._authority(caller_owner)
    if image["caller"] is not caller["caller"] or image["rng"] is not caller["tape"].rng:
        raise ContinuationRejected(
            "Original shared image/caller ownership unavailable", stage="parent_identity"
        )
    return image, caller


def request_record(request):
    image, caller = _parents(request.image_owner, validate=False)
    return dict(
        law=LAW_ID,
        image_trial=image["trial"].identity,
        caller_trial=caller["trial"].identity,
        core_request=caller["request"].core_request.identity,
        source_law="single_cell895-906",
        no_phase_or_height_authority=True,
    )


def from_image(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise ContinuationRejected("Explicit in-caller source-law opt-in required", stage="opt_in")
    image, caller = _parents(owner, validate=True)
    if "mesh" in vars(caller["caller"]):
        raise ContinuationRejected(
            "Caller already has a mesh; no supplied/completed object accepted",
            stage="caller_mesh_exists",
        )
    value = Request(owner, "")
    return replace(value, identity=core.records._digest(request_record(value)))


def _authenticate(context):
    # Numerical authentication: retained constructor/pre_mesh and nested
    # seed/image replays execute here on isolated streams, never on caller RNG.
    core.validate_request(context.core_request)


@contextmanager
def _isolated_authentication(context):
    """Reject calls on the continuing RNG before they execute; keep outer guards.

    The genuine typed core request drives its own isolated numerical replays.
    No retired owner is re-armed, and no inspection cache becomes authority.
    """
    previous = sys.getprofile()

    def profile(frame, event, arg):
        continuing = (
            event == "c_call"
            and getattr(arg, "__self__", None) is context.rng
            or event == "call"
            and frame.f_locals.get("self") is context.rng
        )
        if continuing:
            context.work.append(
                dict(
                    kind="forbidden_continuing_rng_authentication_call",
                    phase="authentication",
                    method=frame.f_code.co_name if event == "call" else arg.__name__,
                )
            )
            raise ValueError("Authentication must not call/advance/reset the continuing caller RNG")
        if previous is not None:
            previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)


def _same_graphs(actual, retained):
    for (objects, edges), (old_objects, old_edges) in zip(actual, retained, strict=True):
        if (
            edges != old_edges
            or len(objects) != len(old_objects)
            or any(a is not b for a, b in zip(objects, old_objects, strict=True))
        ):
            raise ValueError("Changed original source objects or reference edges")


def _parent_graphs(context):
    return (
        callers._graph(
            context.caller, context.parent_caller["parameters"], context.parent_caller["tape"]
        ),
        images._graph(context.parent_image["tape"]),
    )


def _before_claim(context):
    # Called only after both actual owner validators and their relationship
    # checks succeed, inside the pair's retirement/reentrancy guard.
    if (
        core.records._digest(request_record(context.request)) != context.request.identity
        or "mesh" in vars(context.caller)
        or _verify_sources() != context.producers
    ):
        raise ValueError("Changed/preassigned caller request at retirement preflight")
    context.parent_evidence = _parent_evidence(context.parent_image, context.parent_caller)
    context.parent_graphs = _parent_graphs(context)
    context.stream_before = core.initial._rng_stream(context.rng)
    context.order.append("parents_preflight_return")
    context.stage = "retirement"


def _validate_transition(context):
    """Check actual retired live owners against the authenticated preflight.

    These comparisons cannot hydrate an owner. The subsequent authentication
    still calls core.validate_request with its original retained typed object.
    """
    image, caller = _parents(context.request.image_owner, validate=False)
    if (
        image is not context.parent_image
        or caller is not context.parent_caller
        or callers._retirement_token(context.caller_owner) is not context.retirement
        or image["request"] is not context.image_request
        or image["request"].caller is not context.caller_owner
        or caller["request"] is not context.caller_request
        or caller["request"].core_request is not context.core_request
        or caller["trial"] is not context.caller_trial
        or image["trial"] is not context.image_trial
        or caller["caller"] is not context.caller
        or caller["tape"] is not context.caller_tape
        or image["tape"] is not context.image_tape
        or image["rng"] is not context.rng
        or caller["tape"].rng is not context.rng
        or caller["invalid"]
        or image["invalid"]
        or "mesh" in vars(context.caller)
        or callers._bindings(context.caller) != caller["bindings"]
        or _verify_sources() != context.producers
    ):
        raise ValueError("Retired source owners changed before continuing construction")
    if (
        core.initial._rng_stream(context.rng).identity != context.stream_before.identity
        or _parent_evidence(image, caller).identity != context.parent_evidence.identity
    ):
        raise ValueError("Authentication changed original source evidence or continuing RNG epoch")
    _same_graphs(_parent_graphs(context), context.parent_graphs)


def _kwargs(context):
    p, cells = context.parent_caller["parameters"], context.caller
    lattice = callers.source.CellLatticeType
    mapping = {lattice.HEX: "tri", lattice.SQUARE: "rect"}
    if p.cell_lattice_type not in mapping:
        raise ValueError("Unsupported original lattice enum")
    value = dict(
        cell_radius=p.cell_radius,
        seed_points=None,
        use_alpha_shape=False,
        allow_merging=False,
        single_cell_noise=0.1,
        single_cell_sides=6,
        image_mask=None,
        make_all_operators=False,
        mesh_type=mapping[p.cell_lattice_type],
        center=cells.centre,
    )
    if (
        core.caches.snapshot(value).identity
        != core.caches.snapshot(
            context.core_request.initial_request.constructor_kwargs.copy()
        ).identity
    ):
        raise ValueError("Actual caller constructor arguments differ from retained source")
    return value


def _parent_evidence(image, caller):
    callers._validate_parameter_source(caller)
    tape = caller["tape"]
    prelude = caller["request"].core_request.initial_request.upstream[2]
    images._file_bytes(prelude.image)
    draws = [
        dict(
            shape=d["shape"],
            values=d["values"],
            before=core.initial.streams.native_stream_manifest(d["before"]),
            after=core.initial.streams.native_stream_manifest(d["after"]),
            locals=images._event_record(d["before_locals"]),
        )
        for d in tape.draws
    ]
    return core.caches.snapshot(
        dict(
            caller_events=tape.events,
            caller_draws=draws,
            caller_locals=images._event_record(tape.locals),
            parameters=callers._parameters(caller["parameters"]),
            # Request records include frozen MappingProxyType declarations.
            # Use the same canonical projector as their existing identity;
            # this is evidence only, never a replacement for the typed parent.
            caller_request=core.records.record(callers.request_record(caller["request"])),
            caller_trial=callers.trial_record(caller["trial"]),
            image_trial=images.trial_record(image["trial"]),
            image_audit=images._audit(image["tape"], prelude).identity,
            image_events=[images._event_record(e) for e in image["tape"].events],
        )
    )


def _caller_without_mesh(caller):
    return {k: v for k, v in callers._public(caller).items() if k != "mesh"}


def _snapshot(context):
    return core.caches.snapshot(
        dict(
            caller=_caller_without_mesh(context.caller),
            mesh=core.initial._public_cache(context.kernel),
        )
    )


def _graphs(context):
    # The third tape is a graph view, not a supplied native object/phase.
    return (
        callers._graph(
            context.caller, context.parent_caller["parameters"], context.parent_caller["tape"]
        ),
        images._graph(context.parent_image["tape"]),
        callers._graph(context.kernel, context.observer, context.graph_tape),
    )


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        caller_parent=trial.caller_parent_identity,
        image_parent=trial.image_parent_identity,
        constructor=None if trial.constructor_cache is None else trial.constructor_cache.identity,
        pre_mesh=None if trial.pre_mesh_cache is None else trial.pre_mesh_cache.identity,
        final=trial.final_cache.identity,
        occurrence_ids=trial.occurrence_ids,
        events=[e.payload.identity for e in trial.events],
        event_axes=[(e.sequence, e.kind, e.method, e.depth) for e in trial.events],
        ordering=trial.ordering,
        stream_before=trial.stream_before.identity,
        stream_after=trial.stream_after.identity,
        warnings=trial.warnings,
        work=trial.work,
        source_completed=trial.source_completed,
        failure_stage=trial.failure_stage,
        failure_type=trial.failure_type,
        failure_message=trial.failure_message,
        height_phase_physical_checkpoint_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


class MeshOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use prepare with issued image/caller parents")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live in-caller child authority cannot be serialized")

    @property
    def cells(self):
        return _validate_owner(self).caller

    @property
    def mesh(self):
        return _validate_owner(self).kernel

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not MeshOwner or owner not in _ISSUED:
        raise ContinuationRejected(
            "Issued in-caller child authority unavailable", stage="child_authority_unavailable"
        )
    return _ISSUED[owner]


def _validate_owner(owner):
    context = _authority(owner)
    if owner in _FORWARDED:
        raise ContinuationRejected(
            "Mesh epoch was consumed by a caller-tail attempt",
            stage="mesh_epoch_consumed",
            request=context.request,
            trial=context.trial,
        )
    try:
        if (
            context.invalid
            or context.thread != get_ident()
            or _verify_sources() != context.producers
        ):
            raise ValueError("Changed child source producer")
        bindings = _bindings()
        if len(bindings) != len(context.bindings) or any(
            a is not b for a, b in zip(bindings, context.bindings, strict=True)
        ):
            raise ValueError("Changed child runtime/source method binding")
        if not context.parent_caller.get("continuation_consumed") or not context.parent_image.get(
            "continuation_consumed"
        ):
            raise ValueError("Consumed parent epochs were re-armed")
        if (
            callers._retirement_token(context.caller_owner) is not context.retirement
            or context.parent_caller["invalid"]
            or context.parent_image["invalid"]
        ):
            raise ValueError("Lost irreversible retirement or invalidated source parent")
        image, caller = _parents(context.request.image_owner, validate=False)
        if image is not context.parent_image or caller is not context.parent_caller:
            raise ValueError("Original issued parent registry identity changed")
        if core.records._digest(request_record(context.request)) != context.request.identity:
            raise ValueError("Original requested parent evidence changed")
        if callers._bindings(context.caller) != context.parent_caller["bindings"]:
            raise ValueError("Original caller source method binding changed")
        if (
            type(context.kernel) is not _Runtime
            or context.caller.mesh is not context.kernel
            or context.kernel._cells_rng.rng is not context.rng
        ):
            raise ValueError("Actual caller mesh/RNG identities changed")
        if (
            context.kernel._cells_observer is not context.observer
            or context.kernel._cells_rng.observer is not context.observer
        ):
            raise ValueError("Actual mesh observer/RNG wrapper changed")
        if context.observer.stack or context.observer.ids != context.trial.occurrence_ids:
            raise ValueError("Actual observer stack/occurrence identity changed")
        if core.initial._rng_stream(context.rng).identity != context.trial.stream_after.identity:
            raise ValueError("Changed shared continuing RNG epoch")
        if _snapshot(context).identity != context.trial.final_cache.identity:
            raise ValueError("Changed actual caller/mesh cache")
        if (
            _parent_evidence(context.parent_image, context.parent_caller).identity
            != context.parent_evidence.identity
        ):
            raise ValueError("Changed retained parent source evidence")
        if core.records._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Changed sealed child trial")
        for cache in (
            context.trial.constructor_cache,
            context.trial.pre_mesh_cache,
            context.trial.final_cache,
            *(e.payload for e in context.trial.events),
        ):
            core.caches.validate(cache)
        if len(context.observer.events) != len(context.trial.events) or any(
            a is not b for a, b in zip(context.observer.events, context.trial.events, strict=True)
        ):
            raise ValueError("Changed actual mesh event sequence")
        for (objects, edges), (old_objects, old_edges) in zip(
            _graphs(context), context.graphs, strict=True
        ):
            if (
                edges != old_edges
                or len(objects) != len(old_objects)
                or any(a is not b for a, b in zip(objects, old_objects, strict=True))
            ):
                raise ValueError("Changed child or parent object/alias edges")
    except Exception as error:
        context.invalid = True
        raise ContinuationRejected(
            "Stale in-caller child refused",
            stage="child_authority_drift",
            request=context.request,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _claim_for_caller_tail(owner, *, expected, transition):
    context = _validate_owner(owner)
    if context is not expected or transition is None:
        raise ContinuationRejected("Caller-tail mesh issuance changed", stage="mesh_identity")
    _FORWARDED[owner] = transition
    return context


def _execute(context):
    """Observed equivalent of the original single-cell caller895-906 ordering."""
    _validate_transition(context)
    if (
        context.stream_before.identity
        != context.core_request.initial_request.stream_before.identity
    ):
        raise ValueError("Actual continuing caller RNG is at a different constructor epoch")
    authentication = dict(
        kind="core.validate_request_and_nested_replays",
        phase="authentication",
        started=True,
        continuing_rng_before=context.stream_before.identity,
    )
    context.work.append(authentication)
    with _isolated_authentication(context):
        _authenticate(context)
    _validate_transition(context)
    authentication["continuing_rng_after"] = core.initial._rng_stream(context.rng).identity
    authentication["completed"] = True
    context.phase = "continuation"
    kwargs = _kwargs(context)
    context.observer = core.initial._Observer(
        context.core_request.initial_request.constructor_point_ids
    )
    context.observer.first_failure = None
    context.kernel = object.__new__(_Runtime)
    context.kernel._cells_observer = context.observer
    context.kernel._cells_rng = core.initial._Random(context.rng, context.observer)
    with warnings.catch_warnings(record=True) as caught:
        context.caught = caught
        warnings.simplefilter("always")
        _ACTIVE[context.kernel] = context
        try:
            context.stage = "constructor"
            context.kernel.__init__(**kwargs)
            context.order.append("constructor_return")
            context.stage = "caller_mesh_assignment"
            context.order.append("caller_mesh_assignment_enter")
            context.caller.mesh = context.kernel
            context.order.append("caller_mesh_assigned")
            context.stage = "constructor_authentication"
            context.constructor = core.caches.snapshot(core.initial._public_cache(context.kernel))
            parent = context.core_request.initial_state
            if (
                context.constructor.identity != parent.constructed_cache.identity
                or core.initial._rng_stream(context.rng).identity
                != parent.stream_after_constructor.identity
            ):
                raise ValueError(
                    "Actual continuing constructor cache/RNG differs from retained source"
                )
            context.stage = "init_mesh"
            context.kernel.init_mesh()
            context.init_completed = True
            context.order.append("init_mesh_return")
        finally:
            _ACTIVE.pop(context.kernel, None)
    context.stage = "final_source_checks"
    if (
        not context.core_completed
        or not context.init_completed
        or context.observer.stack
        or context.observer.ids != context.core_request.initial_state.retained_point_ids
        or _verify_sources() != context.producers
    ):
        raise ValueError("Incomplete initialization or source drift")
    if (
        core.caches.snapshot(_caller_without_mesh(context.caller)).identity
        != context.parent_caller["trial"].cache.identity
    ):
        raise ValueError("Initialization changed unrelated original caller attributes")


def prepare(request):
    if type(request) is not Request:
        raise ContinuationRejected(
            "Typed in-caller request required", stage="request_owner", request=request
        )
    producers = _verify_sources()
    # Registry lookup is not authentication. Both actual validators run inside
    # the paired retirement guard before either epoch can be mutated.
    image = images._authority(request.image_owner)
    caller = callers._authority(image["request"].caller)
    context = SimpleNamespace(
        request=request,
        parent_image=image,
        parent_caller=caller,
        caller_owner=image["request"].caller,
        image_request=image["request"],
        caller_request=caller["request"],
        caller_trial=caller["trial"],
        image_trial=image["trial"],
        caller_tape=caller["tape"],
        image_tape=image["tape"],
        retirement=object(),
        caller=caller["caller"],
        rng=caller["tape"].rng,
        core_request=caller["request"].core_request,
        kernel=None,
        observer=None,
        constructor=None,
        before=None,
        constructor_completed=False,
        core_completed=False,
        init_completed=False,
        order=[],
        work=[],
        invalid=False,
        thread=get_ident(),
        stage="retirement_preflight",
        phase="retirement",
        caught=(),
        producers=producers,
        bindings=_bindings(),
        steps={},
    )
    error = None
    try:
        retirement = dict(kind="paired_parent_retirement", phase="retirement", started=True)
        context.work.append(retirement)
        images._consume_epoch(
            request.image_owner,
            expected_image=image,
            expected_caller=caller,
            transition=context.retirement,
            before_claim=lambda: _before_claim(context),
        )
        retirement["completed"] = True
        context.order.append("parents_retired")
        context.stage = context.phase = "authentication"
        with _account_work(context):
            _execute(context)
    except Exception as failure:
        error = failure
    retirement["committed"] = callers._retirement_token(context.caller_owner) is context.retirement
    partial = dict(
        context=context,
        parent_caller_trial=caller["trial"],
        parent_image_trial=image["trial"],
        parent_initial_request=context.core_request.initial_request,
        parent_initial_state=context.core_request.initial_state,
        caller=context.caller,
        kernel=context.kernel,
        rng=context.rng,
        observer=context.observer,
        last_snapshots=dict(constructor=context.constructor, pre_mesh=context.before),
        work=context.work,
        ordering=context.order,
        source_stage=context.stage,
        parent_epochs_consumed=callers._epoch_consumed(context.caller_owner),
        this_attempt_retired_parents=retirement["committed"],
        source_steps=context.steps,
        usable_live_child_available=False,
    )
    try:
        if context.kernel is None or context.observer is None:
            raise ValueError("Attempt failed before a complete mesh trial")
        final = _snapshot(context)
        trial = Trial(
            request.identity,
            caller["trial"].identity,
            image["trial"].identity,
            context.constructor,
            context.before,
            final,
            tuple(context.observer.ids),
            tuple(context.observer.events),
            tuple(context.order),
            context.stream_before,
            core.initial._rng_stream(context.rng),
            tuple(str(w.message) for w in context.caught),
            tuple(dict(w) for w in context.work),
            error is None,
            None if error is None else context.stage,
            None if error is None else type(error).__name__,
            None if error is None else str(error),
            "",
        )
        trial = replace(trial, identity=core.records._digest(trial_record(trial)))
    except Exception as capture_error:
        raise ContinuationRejected(
            "In-caller trial sealing failed",
            stage="capture",
            request=request,
            partial=partial,
            source_error=error,
            capture_error=capture_error,
        ) from (error if error is not None else capture_error)
    if error is not None:
        raise ContinuationRejected(
            "Actual in-caller attempt refused",
            stage=context.stage,
            request=request,
            trial=trial,
            partial=partial,
            source_error=error,
        ) from error
    try:
        context.trial = trial
        # Persistent graph roots retain original wrappers, source-parent tapes
        # and mutable attribute dictionaries; no native object is supplied here.
        context.graph_tape = SimpleNamespace(
            rng=context.rng,
            events=context.observer.events,
            draws=[],
            locals=dict(rng_wrapper=vars(context.kernel._cells_rng)),
        )
        context.graphs = _graphs(context)
        owner = object.__new__(MeshOwner)
        _ISSUED[owner] = context
        return owner
    except Exception as capture_error:
        context.invalid = True
        raise ContinuationRejected(
            "In-caller child issuance failed",
            stage="issuance",
            request=request,
            trial=trial,
            partial=partial,
            capture_error=capture_error,
        ) from capture_error


def require_later_continuation(owner, *, parameters=None):
    context = _validate_owner(owner)
    raise ContinuationRejected(
        "Owned cell_height/full parameter/caller continuation is unavailable",
        stage="later_caller_authority_unavailable",
        request=context.request,
        trial=context.trial,
        partial=dict(
            supplied_parameters=parameters,
            invalidated_owners=INVALIDATED_OWNERS,
            physical_checkpoint_multicell_cutting_admitted=False,
        ),
    )
