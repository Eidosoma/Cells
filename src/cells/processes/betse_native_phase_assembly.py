"""Fresh native phase/Cells/Simulator prefix with an issued callback input.

Only the explicit prepared-callback route is owned. No old Simulator, handler,
world, serialized cache or inspection container becomes a phase. The original
phase constructor remains incomplete: cache/dyna/kludge/time/export and all
phase use, world or physical admission are unavailable.
"""

import ast
import builtins
import hashlib
import importlib
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakSet

from cells.processes import betse_native_phase_assembly_source as source
from cells.processes import betse_native_phase_callbacks as callbacks
from cells.processes import betse_native_tissue_handler_attachment as inherited

claims, previous, literal = inherited.claims, inherited.previous, inherited.literal
aliases, core = inherited.aliases, inherited.core
LAW_ID = "betse_genuine_phase_empty_objects_prepared_callbacks_prefix@1"
MODE = "prepared_callback_seven_load_seed_prefix"
RELEASE = "CELLS_NATIVE_PHASE_ASSEMBLY_RELEASED"
PRODUCERS = {
    "betse_native_tissue_handler_attachment": (
        "c0d9b1f5375620464167c13bc07815c996284e1d78eb753942c560f80a15470b"
    ),
    "betse_native_phase_callbacks": (
        "4fa19547caac95257162e6678092c3e55ce4fe43b05b2d16f7908f9196740f2d"
    ),
}
PHASE = "betse/science/phase/phasecls.py"
IMPORTS = {
    "betse.science.cells": ("Cells",),
    "betse.science.math.cache.cacheabc": ("SimPhaseCaches",),
    "betse.science.sim": ("Simulator",),
    "betse.science.tissue.tishandler": ("TissueHandler",),
}
FIELDS = ("callbacks", "cells", "kind", "p", "sim")
_PREFIX = source.PhaseConstructorPrefix.construct
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED, _OBJECTS = (WeakKeyDictionary() for _ in range(5))
_LOCK, _ACTIVE = RLock(), []
_DESCRIPTORS = WeakSet()


class AssemblyRejected(ValueError):
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
        self.stage, self.request, self.trial = stage, request, trial
        self.partial, self.source_error, self.capture_error = partial, source_error, capture_error


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parameters: previous.SubconfigurationsOwner
    callbacks: callbacks.CallbackOwner
    parameter_identity: str
    callback_identity: str
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Phase prefix requests are process-local source authority")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    events: tuple
    work: tuple
    constructor_attempts: tuple
    constructor_returns: tuple
    parameter_claim: object
    prefix_completed: bool
    failure_stage: str | None
    identity: str


def _body(node):
    body = list(node.body)
    if (
        body
        and isinstance(body[0], ast.Expr)
        and isinstance(body[0].value, ast.Constant)
        and isinstance(body[0].value.value, str)
    ):
        body.pop(0)
    return body


def source_plan():
    for module in (inherited, callbacks):
        if (
            hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()
            != PRODUCERS[module.__name__.rsplit(".", 1)[-1]]
        ):
            raise ValueError("Explicit phase-prefix dependency changed")
    parent = inherited.source_plan()
    callbacks.source_plan()
    path = aliases.NATIVE / PHASE
    cls = callbacks.simulator._class(ast.parse(path.read_bytes()), "SimPhase")
    ctor = callbacks.simulator._method(cls, "__init__")
    body = _body(ctor)
    end = next(
        i
        for i, n in enumerate(body)
        if isinstance(n, ast.Assign)
        and any(isinstance(t, ast.Attribute) and t.attr == "sim" for t in n.targets)
    )
    selected = body[: end + 1]
    own = callbacks.simulator._method(
        callbacks.simulator._class(
            ast.parse(Path(source.__file__).read_bytes()), "PhaseConstructorPrefix"
        ),
        "construct",
    )
    if ast.dump(ast.Module(body=selected, type_ignores=[])) != ast.dump(
        ast.Module(body=_body(own), type_ignores=[])
    ):
        raise ValueError("Original phase constructor prefix/import/store order changed")
    return dict(
        law=LAW_ID,
        mode=MODE,
        native_pins=parent["native_pins"],
        literal_source=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        source_lines=[selected[0].lineno, selected[-1].end_lineno],
        fields=FIELDS,
        constructor_order=("Cells(p)", "Simulator()"),
        callback_route="actual issued prepared input; not default factory order",
        parameters="actual fresh seven-load owner; not numeric/event-complete",
        stopped_before=("SimPhaseCaches", "TissueHandler", "_init_kludge"),
        complete_phase_or_world_or_physical_or_checkpoint_admitted=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID,
        mode=value.mode,
        parameters=value.parameter_identity,
        callbacks=value.callback_identity,
        source=value.source_identity,
        supplied_cells_or_sim=False,
        kind="native SimPhaseKind.SEED",
    )


def from_owners(parameters, callback_owner, *, law_id, mode):
    if law_id != LAW_ID or type(law_id) is not str or mode != MODE or type(mode) is not str:
        raise AssemblyRejected("Exact prepared-callback prefix law/mode required", stage="law")
    plan = source_plan()
    with claims.inspection(parameters) as lease:
        p = lease.parameters
        parent = previous._validate(parameters)
        if p is not parent.p:
            raise ValueError("Original parameter inspection association changed")
    callback = callbacks._validate(callback_owner)
    if callback.callback is None or not callback.trial.factory_completed:
        raise AssemblyRejected("Actual prepared callback unavailable", stage="callback")
    value = Request(
        parameters,
        callback_owner,
        parent.trial.identity,
        callback.trial.identity,
        previous._digest(plan),
        mode,
        "",
    )
    value = replace(value, identity=previous._digest(request_record(value)))
    _REQUESTS[value] = (
        parent,
        parent.p,
        parent.trial,
        parent.graph,
        callback,
        callback.callback,
        callback.trial,
    )
    return value


def _bindings():
    functions = (
        source_plan,
        request_record,
        from_owners,
        _bindings,
        _acquire,
        _native_bindings,
        _guard,
        _check,
        _native_call,
        _import_native,
        _namespace,
        _surface,
        _scope_bindings,
        _associations,
        _snapshot,
        _graph,
        _validate,
        trial_record,
        prepare,
        require_phase,
        _PREFIX,
        inherited._account.__wrapped__,
        inherited._stop,
        inherited._event,
        literal._runtime_type,
        literal._make,
        literal._surface,
        literal._project,
        callbacks._validate,
        callbacks._bindings,
    )
    return (
        _REQUESTS,
        _CONSUMED,
        _CLAIMED,
        _ISSUED,
        _OBJECTS,
        _LOCK,
        _ACTIVE,
        LAW_ID,
        MODE,
        RELEASE,
        _DESCRIPTORS,
        IMPORTS,
        FIELDS,
        *(atom for name, items in IMPORTS.items() for atom in (name, *items)),
        *claims._bindings()[1],
        *(atom for fn in functions for atom in aliases._atoms(fn)),
    )


def _acquire(context):
    with aliases.issuing_native_imports(literal.source.SOURCE_PINS):
        modules = {
            name: importlib.import_module(name)
            for name in ("betse.science.phase.phasecls", *IMPORTS, "betse.science.enum.enumphase")
        }
    classes = dict(
        SimPhase=modules["betse.science.phase.phasecls"].SimPhase,
        Cells=modules["betse.science.cells"].Cells,
        Simulator=modules["betse.science.sim"].Simulator,
    )
    for name, cls in classes.items():
        module = modules[cls.__module__]
        if (
            getattr(module, name) is not cls
            or type(cls) is not type
            or cls.__bases__ != (object,)
            or cls.__new__ is not object.__new__
        ):
            raise ValueError("Actual original native constructor class required: " + name)
        relative = str(Path(module.__file__).resolve().relative_to(aliases.NATIVE))
        callbacks._source_function(cls.__init__, relative, "__init__", name)
    context.factories = classes
    context.import_modules = {name: modules[name] for name in IMPORTS}
    context.kind = modules["betse.science.enum.enumphase"].SimPhaseKind.SEED
    context.modules = aliases._module_records()


def _native_bindings(context):
    return (
        context.kind,
        *(
            atom
            for name, cls in context.factories.items()
            for atom in (name, cls, *literal._surface(cls))
        ),
    )


def _guard(context):
    inherited._stop(context)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise AssemblyRejected("Phase-prefix native entry unavailable", stage="entry")


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _REQUESTS.get(context.request) is not context.parents
    ):
        raise ValueError("Invalid original phase prefix epoch")
    if (
        _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.parameters) is not context
    ):
        raise ValueError("Phase prefix one-shot claim changed")
    parent = previous._validate(context.request.parameters)
    callback = callbacks._validate(context.request.callbacks)
    if (
        parent is not context.parents[0]
        or parent.p is not context.p
        or parent.trial is not context.parents[2]
        or parent.graph is not context.parents[3]
        or callback is not context.parents[4]
        or callback.callback is not context.callback
        or callback.trial is not context.parents[6]
    ):
        raise ValueError("Original parameter/callback source association changed")
    if (
        previous._digest(request_record(context.request)) != context.request.identity
        or previous._digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Phase request/source changed")
    literal._same(_bindings(), context.bindings)
    if hasattr(context, "native_bindings"):
        literal._same(_native_bindings(context), context.native_bindings)
    if hasattr(context, "scope_bindings"):
        literal._same(_scope_bindings(context), context.scope_bindings)
    for name, cls in context.runtime_types.items():
        literal._same(_surface(cls), context.runtime_bindings[name])
    for _, obj in context.objects:
        if _OBJECTS.get(obj) is not context:
            raise ValueError("Original raw object issuance changed")
    if hasattr(context, "modules"):
        aliases._check_modules()
        now = aliases._module_records()
        for name, record in context.modules.items():
            actual = now.get(name)
            if type(actual) is not tuple or actual[0] is not record[0] or actual[1:] != record[1:]:
                raise ValueError("Original native import identity changed")
    if hasattr(context, "lease"):
        claim = context.lease_context
        if (
            claims._context(context.lease) is not claim
            or claim.owner is not context.request.parameters
            or claim.parent is not context.parents[0]
        ):
            raise ValueError("Original exclusive construction claim changed")
        if context.active:
            context.lease.check()
            if context.lease.parameters is not context.p:
                raise ValueError("Source lease parameter changed")
        elif (
            context.lease.record is not context.lease_record
            or not context.lease_record.succeeded
            or claim.active
            or claim.invalid
            or claim.guard.active
            or claim.guard.invalid
            or claims._CONSTRUCTED.get(context.request.parameters) is not True
        ):
            raise ValueError("Closed successful source lease changed")


def _native_call(context, label, delegate, *args, **kwargs):
    _guard(context)
    _check(context)
    if label not in ("Cells.__init__", "Simulator.__init__"):
        raise AssemblyRejected("Method outside selected constructor prefix", stage="method")
    role = label.split(".")[0]
    actual = args[0]
    if role in context.constructed or actual is not context.objects[-1][1]:
        raise ValueError("Repeated or foreign native constructor instance")
    if role == "Cells" and (
        args != (actual,) or set(kwargs) != {"p"} or kwargs["p"] is not context.p
    ):
        raise ValueError("Cells constructor must receive actual same p")
    if role == "Simulator" and (args != (actual,) or kwargs):
        raise ValueError("Original Simulator constructor takes no arguments")
    if role == "Simulator" and context.constructor_returns != ["Cells"]:
        raise ValueError("Original Cells then Simulator order required")
    context.constructed[role] = actual
    context.constructor_attempts.append(role)
    inherited._event(context, label + "_enter", actual)
    inherited._stop(context)
    try:
        value = delegate(*args, **kwargs)
    except BaseException:
        inherited._event(context, label + "_unwind", actual)
        raise
    context.last_completed = (label, actual, value)
    context.constructor_returns.append(role)
    inherited._event(context, label + "_return", actual)
    inherited._stop(context)
    return value


def _import_native(name, globals, locals, fromlist, level):
    return builtins.__import__(name, globals, locals, fromlist, level)


def _namespace(context):
    scope = dict(
        vars(literal),
        _OBJECTS=_OBJECTS,
        _guard=_guard,
        _native_call=_native_call,
        _event=inherited._event,
        _stop=inherited._stop,
        _lazy_factory=lambda actual, name: actual.factories[name],
        _surface=_surface,
    )
    methods = {}
    for name in ("__init__", "__get__", "__set__"):
        fn = getattr(literal._Descriptor, name)
        methods[name] = FunctionType(
            fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__
        )
    scope["_Descriptor"] = type("PhasePrefixDescriptor", (), methods)
    _DESCRIPTORS.add(scope["_Descriptor"])
    for name in ("_runtime_type", "_make"):
        fn = getattr(literal, name)
        scope[name] = FunctionType(fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__)
    context.factory_scope = scope
    # The original class is a real base, not an inspection container. Its full
    # constructor and all methods remain guarded; only this prefix executes.
    cls = scope["_runtime_type"](context, "SimPhase")
    context.phase = object.__new__(cls)
    _OBJECTS[context.phase] = context
    context.objects.append(("SimPhase", context.phase))

    def unavailable(*a, **k):
        raise AssemblyRejected(
            "Cache/dyna/default callback construction is outside this prefix", stage="boundary"
        )

    def imports(name, globals=None, locals=None, fromlist=(), level=0):
        _guard(context)
        _check(context)
        if level or name not in IMPORTS or tuple(fromlist) != IMPORTS[name]:
            raise ValueError("Unexpected original prefix import")
        actual = _import_native(name, globals, locals, fromlist, level)
        if actual is not context.import_modules[name]:
            raise ValueError("Native imported module changed")
        context.import_order.append(name)
        if tuple(context.import_order) != tuple(IMPORTS)[: len(context.import_order)]:
            raise ValueError("Original constructor import order changed")
        selected = IMPORTS[name][0]
        if selected in ("Cells", "Simulator"):
            return SimpleNamespace(
                **{selected: lambda **kw: scope["_make"](context, selected, **kw)}
            )
        return SimpleNamespace(**{selected: unavailable})

    private = dict(vars(builtins), __import__=imports)
    context.method = FunctionType(
        _PREFIX.__code__,
        dict(
            _PREFIX.__globals__,
            __builtins__=private,
            phasecallbacks=SimpleNamespace(make_default=unavailable),
        ),
        _PREFIX.__name__,
        _PREFIX.__defaults__,
        _PREFIX.__closure__,
    )
    context.scope_bindings = _scope_bindings(context)


def _surface(cls):
    result = list(literal._surface(cls))
    for base in cls.__mro__:
        for member in vars(base).values():
            if type(member) in _DESCRIPTORS:
                result.extend((member.native, member.name))
    return tuple(result)


def _scope_bindings(context):
    fn = context.method
    return (
        fn,
        fn.__globals__,
        fn.__builtins__,
        *aliases._atoms(fn),
        *aliases._atoms(fn.__builtins__["__import__"]),
        fn.__globals__["phasecallbacks"],
        *aliases._atoms(fn.__globals__["phasecallbacks"].make_default),
        context.factory_scope["_Descriptor"],
        context.factory_scope["_OBJECTS"],
        *(
            atom
            for name in (
                "_runtime_type",
                "_make",
                "_guard",
                "_native_call",
                "_lazy_factory",
                "_surface",
                "_event",
                "_stop",
            )
            for atom in aliases._atoms(context.factory_scope[name])
        ),
    )


def _associations(context):
    values = vars(context.phase)
    if (
        tuple(values) != FIELDS
        or context.constructor_attempts != ["Cells", "Simulator"]
        or context.constructor_returns != ["Cells", "Simulator"]
    ):
        raise ValueError("Original ordered constructor prefix incomplete")
    expected = (
        context.callback,
        context.constructed["Cells"],
        context.kind,
        context.p,
        context.constructed["Simulator"],
    )
    if any(values[name] is not value for name, value in zip(FIELDS, expected, strict=True)):
        raise ValueError("Actual assembled object/parameter alias changed")
    if context.phase.sim is context.callback_parent.source.parent.instance:
        raise ValueError("Standalone ancestor Simulator cannot become phase.sim")


def _snapshot(context):
    references = [
        ("parameters", context.p),
        ("callback", context.callback),
        *(("inherited", value) for value in context.parents[0].graph[0]),
        *context.objects,
    ]
    projector = SimpleNamespace(objects=references)
    return core.caches.snapshot(
        dict(
            parameter_parent=context.request.parameter_identity,
            callback_parent=context.request.callback_identity,
            objects=[
                dict(role=name, fields=literal._project(projector, vars(obj)))
                for name, obj in context.objects
            ],
            imports=context.import_order,
            attempts=context.constructor_attempts,
            returns=context.constructor_returns,
        )
    )


def _graph(context):
    context.graph_fields.clear()
    context.graph_fields.extend(vars(obj) for _, obj in context.objects)
    vars(context.graph_view).clear()
    vars(context.graph_view).update(
        objects=context.objects,
        fields=context.graph_fields,
        parameters=context.p,
        callback=context.callback,
    )
    return literal.callers._graph(context.graph_view, context.graph_view, context.tape)


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        cache=trial.cache.identity,
        events=trial.events,
        work=trial.work,
        attempts=trial.constructor_attempts,
        returns=trial.constructor_returns,
        parameter_claim=None if trial.parameter_claim is None else asdict(trial.parameter_claim),
        prefix_completed=trial.prefix_completed,
        failure_stage=trial.failure_stage,
        full_phase_or_world_or_checkpoint_admitted=False,
    )


class AssemblyOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the fresh original phase-prefix preparation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No phase prefix hydration or checkpoint admission")

    @property
    def partial_phase(self):
        return _validate(self).phase

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not AssemblyOwner or owner not in _ISSUED:
        raise AssemblyRejected("Issued original phase prefix owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced phase prefix owner")
        _check(context)
        _associations(context)
        if (
            _snapshot(context).identity != context.trial.cache.identity
            or previous._digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Original prefix cache/trial changed")
        actual = _graph(context)
        literal._same(actual[0], context.graph[0])
        if actual[1] != context.graph[1]:
            raise ValueError("Phase prefix reference edges changed")
    except BaseException as error:
        context.invalid = True
        raise AssemblyRejected(
            "Stale phase prefix refused",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(claims.RELEASE) != "1"
    ):
        raise AssemblyRejected(
            "Actual phase prefix construction remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise AssemblyRejected(
                "Reentrant phase prefix refused", stage="reentrant", request=request
            )
        if type(request) is not Request or request not in _REQUESTS:
            raise AssemblyRejected(
                "Actual issued parameter/callback request required",
                stage="request",
                request=request,
            )
        if request in _CONSUMED or request.parameters in _CLAIMED:
            raise AssemblyRejected(
                "Phase prefix attempt consumed", stage="consumed", request=request
            )
        parent = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            parents=parent,
            p=parent[1],
            callback_parent=parent[4],
            callback=parent[5],
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parents",
            objects=[],
            runtime_types={},
            runtime_bindings={},
            events=[],
            work=[],
            locals={},
            constructor_attempts=[],
            constructor_returns=[],
            constructed={},
            import_order=[],
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            graph_view=SimpleNamespace(),
            graph_fields=[],
            completed=False,
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        _CONSUMED[request] = _CLAIMED[request.parameters] = context
        _ACTIVE.append(context)
        primary = None
        try:
            context.bindings = _bindings()
            with claims.construction(
                request.parameters, law_id=claims.LAW_ID, enabled=True
            ) as lease:
                context.lease = lease
                context.lease_context = claims._context(lease)
                if lease.parameters is not context.p:
                    raise ValueError("Original leased parameter changed")
                _check(context)
                observer_scope = dict(
                    vars(inherited),
                    _NATIVE={"construct": _PREFIX},
                    _acquire=_acquire,
                    _namespace=_namespace,
                )
                account = contextmanager(
                    FunctionType(inherited._account.__wrapped__.__code__, observer_scope)
                )
                with account(context):
                    context.stage = "native_class_acquisition"
                    _acquire(context)
                    context.native_bindings = _native_bindings(context)
                    context.stage = "phase_allocation"
                    _namespace(context)
                    context.stage = "constructor_prefix"
                    context.method(
                        context.phase, context.kind, context.p, callbacks=context.callback
                    )
                    inherited._stop(context)
                    _associations(context)
                    context.completed = True
                    _check(context)
        except BaseException as error:
            if not isinstance(error, literal._CaptureStop) or context.observation_error is None:
                primary = error
        finally:
            context.active = False
            _ACTIVE.pop()
        if hasattr(context, "lease"):
            try:
                context.lease_record = context.lease.record
            except BaseException as error:
                inherited.captures._remember_observation_error(
                    context, error, origin="lease_record", raw=context.lease
                )
        partial = dict(
            context=context,
            parameters=context.p,
            callback=context.callback,
            objects=context.objects,
            phase=getattr(context, "phase", None),
            last_completed=getattr(context, "last_completed", None),
            imports=context.import_order,
            attempts=context.constructor_attempts,
            returns=context.constructor_returns,
            raw_locals=context.locals,
            events=context.events,
            work=context.work,
            usable_child_available=False,
        )
        capture = context.observation_error
        try:
            trial = Trial(
                request.identity,
                _snapshot(context),
                tuple(name for name, _ in context.events),
                tuple(context.work),
                tuple(context.constructor_attempts),
                tuple(context.constructor_returns),
                getattr(context, "lease_record", None),
                context.completed and primary is None and capture is None,
                None if primary is None and capture is None else context.stage,
                "",
            )
            context.trial = replace(trial, identity=previous._digest(trial_record(trial)))
        except BaseException as error:
            raise AssemblyRejected(
                "Phase prefix sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None or capture is not None:
            raise AssemblyRejected(
                "Original phase prefix attempt refused",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=partial,
                source_error=primary,
                capture_error=capture,
            ) from (primary if primary is not None else capture)
        try:
            _check(context)
            context.graph = _graph(context)
            context.owner = object.__new__(AssemblyOwner)
            _ISSUED[context.owner] = context
            return context.owner
        except BaseException as error:
            raise AssemblyRejected(
                "Phase child sealing failed",
                stage="capture",
                request=request,
                trial=context.trial,
                partial=partial,
                capture_error=error,
            ) from error


def require_phase(owner):
    context = _validate(owner)
    raise AssemblyRejected(
        "Cache/dyna/kludge/time/export and complete required parameter stores remain missing",
        stage="phase_incomplete",
        trial=context.trial,
    )
