"""Fresh selected handler on an issued original same-parameter YAML prefix.

No Parameters object, configuration wrapper, world or phase is reconstructed.
The selected constructor takes only p. SimPhase.dyna attachment and all profile
mapping/init_core authority remain unavailable. Actual native work is held.
"""

import builtins
import hashlib
import importlib
import os
import sys
import warnings
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakSet

from cells.processes import betse_native_parameter_construction_lease as claims
from cells.processes import betse_native_parameter_subconfigurations as previous
from cells.processes import betse_native_tissue_configuration as literal

LAW_ID = "betse_actual_same_parameter_selected_tissue_handler@1"
RELEASE = "CELLS_NATIVE_TISSUE_HANDLER_ATTACHMENT_RELEASED"
PARENT_SHA256 = "3e49f8ebfd3cad35df7d642643fee8ebfd72115c34354c761194f7176102e7fb"
SEALED_PARENT_SHA256 = "397c453df7fb4fc397cbd23c7e785c1c4fe7e5a5c46b02f156819958610be0ee"
CLAIMS_SHA256 = "af3f3459745edb32719966833ff75959e60dfd733cb0a9c3882c08e9aed6be00"
LITERAL_SHA256 = "e9f8c93b7bfe856532f68f7406c07e5666b2ebb60d8e71c19a69bb765d4bb99e"
METHODS = literal.METHODS
_NATIVE = dict(literal._NATIVE)
core, captures, aliases = literal.core, literal.captures, literal.aliases
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED, _FACTORY_OBJECTS = (WeakKeyDictionary() for _ in range(5))
_LOCK, _ACTIVE = RLock(), []
_DESCRIPTOR_TYPES = WeakSet()
INVALIDATED_OWNERS = literal.INVALIDATED_OWNERS


class AttachmentRejected(ValueError):
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
    parent: previous.SubconfigurationsOwner
    before_trial_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live same-parameter attachment requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    cache: object
    stages: tuple
    events: tuple
    work: tuple
    warnings: tuple
    parameter_claim: object
    source_completed: bool
    failure_stage: str | None
    identity: str


def source_plan():
    for module, expected in (
        (previous, PARENT_SHA256),
        (literal, LITERAL_SHA256),
        (claims, CLAIMS_SHA256),
    ):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise ValueError("Explicit retained same-p/handler producer changed")
    parent = previous.source_plan()
    literal._verify_sources()
    return dict(
        law=LAW_ID,
        parent_source=previous._digest(parent),
        parent_producer=PARENT_SHA256,
        retained_prior_parent_producer=SEALED_PARENT_SHA256,
        construction_lease_producer=CLAIMS_SHA256,
        construction_lease_source=previous._digest(claims.source_plan()),
        parameter_access=("Lease.parameters", "Lease.check", "Lease.record"),
        handler_methods=METHODS,
        handler_lines=literal.source.HANDLER_LINES,
        native_pins=parent["native_pins"],
        selected_handler_bodies=True,
        actual_same_parameter=True,
        parameter_or_wrapper_reconstruction=False,
        phase_dyna_assignment=False,
        init_profiles_redo_gj_core_or_world_admitted=False,
        missing_numeric_stores_are_original_failures=True,
    )


def request_record(request):
    return dict(
        law=LAW_ID,
        parent=request.before_trial_identity,
        source=request.source_identity,
        fresh_handler=True,
        same_actual_parameter=True,
        phase_or_world_attachment=False,
    )


def from_subconfigurations(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise AttachmentRejected("Explicit selected same-p handler law required", stage="law")
    plan = source_plan()
    with claims.inspection(owner) as claim:
        p = claim.parameters
        parent = previous._validate(owner)
        if parent.p is not p:
            raise ValueError("Original inspected parameter association changed")
    if tuple(parent.trial.completed) != previous.ORDER:
        raise AttachmentRejected("Complete original seven-load owner required", stage="parent")
    request = Request(owner, parent.trial.identity, previous._digest(plan), "")
    request = replace(request, identity=previous._digest(request_record(request)))
    _REQUESTS[request] = (parent, parent.p, parent.config, parent.trial, parent.graph)
    return request


def _bindings():
    functions = (
        *_NATIVE.values(),
        source_plan,
        request_record,
        from_subconfigurations,
        _bindings,
        _lease,
        _lease.__wrapped__,
        _guard,
        _stop,
        _event,
        _check,
        _account,
        _account.__wrapped__,
        _acquire,
        _native_bindings,
        _namespace,
        _namespace_bindings,
        _native_call,
        _invoke,
        _snapshot,
        _graph,
        _factory_scope,
        _surface,
        _validate,
        trial_record,
        prepare,
        require_phase,
        previous._validate,
        previous._bindings,
        previous._check,
        previous._loaded,
        literal._surface,
        literal._runtime_type,
        literal._make,
        literal._Descriptor.__get__,
        literal._Descriptor.__set__,
        literal._project,
        core.caches.snapshot,
        core.caches.validate,
        captures._remember_observation_error,
        previous._native_bindings,
        previous._digest,
        previous.paths._install_audit,
        aliases._module_records,
        aliases._check_modules,
        aliases.issuing_native_imports,
        aliases.issuing_native_imports.__wrapped__,
        literal.callers._graph,
    )
    return (
        _REQUESTS,
        _CONSUMED,
        _CLAIMED,
        _ISSUED,
        _FACTORY_OBJECTS,
        _DESCRIPTOR_TYPES,
        _LOCK,
        _ACTIVE,
        previous._LOCK,
        previous._ACTIVE,
        previous._ISSUED,
        LAW_ID,
        RELEASE,
        PARENT_SHA256,
        LITERAL_SHA256,
        CLAIMS_SHA256,
        *claims._bindings()[1],
        *(atom for fn in functions for atom in aliases._atoms(fn)),
    )


def _stop(context):
    if context.observation_error is not None:
        raise literal._CaptureStop()


def _guard(context):
    _stop(context)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise AttachmentRejected("Selected handler native entry unavailable", stage="source_entry")


def _event(context, name, raw):
    try:
        context.events.append((name, raw))
    except Exception as error:
        captures._remember_observation_error(context, error, origin=name, raw=raw)


@contextmanager
def _lease(context):
    # Reuse Key's exclusive read-only construction claim. No predecessor code,
    # parameter state, native descriptor or configuration wrapper is replaced.
    try:
        with claims.construction(
            context.request.parent, law_id=claims.LAW_ID, enabled=True
        ) as lease:
            context.lease = lease
            context.lease_context = claims._context(lease)
            context.filesystem_guard = context.lease_context.guard
            if lease.parameters is not context.p:
                raise ValueError("Original same-p construction claim changed")
            yield
    finally:
        if hasattr(context, "lease"):
            try:
                context.lease_record = context.lease.record
            except Exception as error:
                captures._remember_observation_error(
                    context, error, origin="claim_record", raw=context.lease
                )


def _acquire(context):
    # Retain the existing native Parameters descriptor; create no replacement.
    with aliases.issuing_native_imports(literal.source.SOURCE_PINS):
        enum = importlib.import_module("betse.science.enum.enumconf")
        errors = importlib.import_module("betse.exceptions")
        context.factories = {
            name: getattr(importlib.import_module(module), name)
            for name, module in literal._FACTORY_MODULES.items()
            if name not in ("TissuePickerImage", "SimEventCut", "SimEventPulseVoltage")
        }
        context.symbols = dict(
            CellsPickerType=enum.CellsPickerType,
            BetseSimTissueException=errors.BetseSimTissueException,
        )
        context.modules = aliases._module_records()


def _native_bindings(context):
    labels, refs = previous._native_bindings(context.parent)
    return (
        labels,
        (
            *refs,
            *literal._surface(type(context.p)),
            *(
                atom
                for name, cls in context.factories.items()
                for atom in (name, cls, *literal._surface(cls))
            ),
            *(atom for name, value in context.symbols.items() for atom in (name, value)),
        ),
    )


def _factory_scope(context):
    scope = dict(
        vars(literal),
        _OBJECTS=_FACTORY_OBJECTS,
        _guard=_guard,
        _native_call=_native_call,
        _event=_event,
        _stop=_stop,
        _surface=_surface,
    )
    for name in ("_runtime_type", "_make"):
        fn = getattr(literal, name)
        scope[name] = FunctionType(fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__)
    methods = {}
    for name in ("__init__", "__get__", "__set__"):
        fn = getattr(literal._Descriptor, name)
        methods[name] = FunctionType(
            fn.__code__, scope, fn.__name__, fn.__defaults__, fn.__closure__
        )
    scope["_Descriptor"] = type("SameParameterFactoryDescriptor", (), methods)
    _DESCRIPTOR_TYPES.add(scope["_Descriptor"])

    def lazy(actual, name):
        _guard(actual)
        _check(actual)
        if name not in actual.factories:
            with aliases.issuing_native_imports(literal.source.SOURCE_PINS):
                actual.factories[name] = getattr(
                    importlib.import_module(literal._FACTORY_MODULES[name]), name
                )
                actual.modules = aliases._module_records()
            actual.native_bindings = _native_bindings(actual)
        return actual.factories[name]

    scope["_lazy_factory"] = lazy
    return scope


def _surface(cls):
    result = list(literal._surface(cls))
    for base in cls.__mro__:
        for member in vars(base).values():
            if type(member) in _DESCRIPTOR_TYPES:
                result.extend((member.native, member.name))
    return tuple(result)


def _namespace(context):
    scope = context.factory_scope = _factory_scope(context)

    def factory(name):
        def make(*a, **k):
            return scope["_make"](context, name, *a, **k)

        return make

    def log(*args):
        _guard(context)
        _event(context, "log_warning", args)
        _stop(context)

    namespace = dict(
        context.symbols,
        **{name: factory(name) for name in literal._FACTORY_MODULES},
        OrderedDict=OrderedDict,
        logs=SimpleNamespace(log_warning=log),
        bool=builtins.bool,
        enumerate=builtins.enumerate,
    )
    context.methods = {
        name: FunctionType(
            fn.__code__,
            dict(fn.__globals__, **namespace),
            fn.__name__,
            fn.__defaults__,
            fn.__closure__,
        )
        for name, fn in _NATIVE.items()
    }

    def method(name):
        def entry(actual, p):
            return _invoke(context, name, actual, p)

        return entry

    runtime = type(
        "SameParameterSelectedTissueHandler",
        (literal.source.TissueConstructor,),
        {
            **{name: method(name) for name in METHODS},
            "__reduce_ex__": lambda *a: (_ for _ in ()).throw(
                TypeError("Live handlers cannot be serialized")
            ),
        },
    )
    context.handler = object.__new__(runtime)
    context.objects.append(("handler", context.handler))
    context.namespace_bindings = _namespace_bindings(context)


def _namespace_bindings(context):
    values = [*literal._surface(type(context.handler))]
    for fn in context.methods.values():
        values.extend(aliases._atoms(fn))
        for name in ("OrderedDict", "bool", "enumerate"):
            values.extend(aliases._atoms(fn.__globals__[name]))
        for name in literal._FACTORY_MODULES:
            values.extend(aliases._atoms(fn.__globals__[name]))
        values.append(fn.__globals__["logs"])
        values.extend(aliases._atoms(fn.__globals__["logs"].log_warning))
    for name in (
        "_runtime_type",
        "_make",
        "_lazy_factory",
        "_guard",
        "_native_call",
        "_event",
        "_stop",
        "_surface",
        "_OBJECTS",
        "_Descriptor",
    ):
        values.extend(aliases._atoms(context.factory_scope[name]))
    for cls in context.runtime_types.values():
        values.extend(_surface(cls))
    return tuple(values)


def _check(context):
    if context.invalid or context.thread != get_ident():
        raise ValueError("Invalid handler epoch")
    if (
        _REQUESTS.get(context.request) is not context.parent_refs
        or _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.parent) is not context
    ):
        raise ValueError("Original one-shot handler request changed")
    if previous._validate(context.request.parent) is not context.parent:
        raise ValueError("Original same-p parent changed")
    if (
        context.parent.p is not context.p
        or context.p is not context.parent_refs[1]
        or context.config is not context.parent_refs[2]
        or context.p._conf is not context.config
        or context.parent.trial is not context.parent_refs[3]
        or context.parent.graph is not context.parent_refs[4]
    ):
        raise ValueError("Actual parameter/config/wrapper association changed")
    if previous._digest(request_record(context.request)) != context.request.identity:
        raise ValueError("Handler request changed")
    if previous._digest(source_plan()) != context.request.source_identity:
        raise ValueError("Handler producer changed")
    literal._same(_bindings(), context.bindings)
    if hasattr(context, "native_bindings"):
        previous.paths.prefix.parameters.inherited._same(
            _native_bindings(context), context.native_bindings
        )
    if hasattr(context, "modules"):
        aliases._check_modules()
        current_modules = aliases._module_records()
        for name, record in context.modules.items():
            current = current_modules.get(name)
            if (
                type(current) is not tuple
                or len(current) != 3
                or current[0] is not record[0]
                or current[1:] != record[1:]
            ):
                raise ValueError("Original native factory import changed")
    if hasattr(context, "methods"):
        # Lazy factory classes are captured when first registered, but original
        # namespace methods/helpers and all earlier runtime surfaces stay exact.
        original = context.namespace_bindings
        current = _namespace_bindings(context)
        if len(current) < len(original):
            raise ValueError("Handler callable surface shrank")
        literal._same(current[: len(original)], original)
        for name, cls in context.runtime_types.items():
            literal._same(_surface(cls), context.runtime_bindings[name])
    for name, obj in context.objects:
        if name != "handler" and _FACTORY_OBJECTS.get(obj) is not context:
            raise ValueError("Original native factory issuance changed")
    if context.active:
        guard = context.filesystem_guard
        if (
            guard.invalid
            or not guard.active
            or not previous._ACTIVE
            or previous._ACTIVE[-1] is not context.lease_context
            or not previous.paths._ACTIVE
            or previous.paths._ACTIVE[-1] is not guard
        ):
            raise ValueError("Read-only parameter lease changed")
        context.lease.check()
        if context.lease.parameters is not context.p:
            raise ValueError("Foreign active same-p construction claim")
    elif hasattr(context, "lease"):
        claim = context.lease_context
        if (
            claims._context(context.lease) is not claim
            or claim.owner is not context.request.parent
            or claim.parent is not context.parent
            or claim.active
            or claim.invalid
            or claim.guard.active
            or claim.guard.invalid
            or claims._CONSTRUCTED.get(context.request.parent) is not True
            or claim.record is not context.lease_record
            or context.lease.record is not context.lease_record
            or not claim.record.succeeded
        ):
            raise ValueError("Closed same-p construction claim changed")


def _native_call(context, label, delegate, *args, **kwargs):
    _guard(context)
    _check(context)
    _event(context, label + "_enter", (args, kwargs))
    _stop(context)
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="native_factory_or_method_wrapper",
            method=label,
            status="entered_not_success_or_case_credit",
        )
    )
    try:
        value = delegate(*args, **kwargs)
    except BaseException:
        _event(context, label + "_unwind", (args, kwargs))
        raise
    context.last_completed = (label, value)
    _event(context, label + "_return", value)
    _stop(context)
    return value


def _invoke(context, name, actual, p):
    _guard(context)
    if actual is not context.handler or p is not context.p:
        raise ValueError("Foreign handler/parameter pair")
    _check(context)
    context.work.append(
        dict(
            sequence=len(context.work),
            layer="selected_literal_body",
            method=name,
            status="entered_not_success_or_case_credit",
        )
    )
    _event(context, name + "_enter", actual)
    _stop(context)
    try:
        value = context.methods[name](actual, p)
    except BaseException:
        _event(context, name + "_unwind", actual)
        raise
    context.last_completed = (name, value)
    _event(context, name + "_return", value)
    _stop(context)
    return value


@contextmanager
def _account(context):
    previous_profile, previous_trace = sys.getprofile(), sys.gettrace()
    selected = {fn.__code__ for fn in (*_NATIVE.values(), _acquire, _namespace)}
    root = str(aliases.NATIVE) + "/"

    def profile(frame, event, arg):
        reached = False
        if event in ("call", "return"):
            code = frame.f_code
            reached = code in selected or code.co_filename.startswith(root)
        if reached and event == "call":
            if len(context.work) >= 100000:
                raise ValueError("Bounded handler work log exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    layer="observed_native_or_literal_entry",
                    phase=context.stage,
                    method=code.co_qualname,
                    entry_is_case=False,
                )
            )
        if event in ("call", "c_call") and previous_profile is not None:
            previous_profile(frame, event, arg)
        if reached and event == "return":
            try:
                context.locals[(code.co_filename, code.co_qualname)] = dict(frame.f_locals)
            except Exception as error:
                captures._remember_observation_error(context, error, origin="raw_locals", raw=frame)
        if event not in ("call", "c_call") and previous_profile is not None:
            try:
                previous_profile(frame, event, arg)
            except Exception as error:
                captures._remember_observation_error(
                    context, error, origin="prior_profile_" + event, raw=(frame, event, arg)
                )

    sys.setprofile(profile)
    try:
        yield
        _stop(context)
    finally:
        sys.setprofile(previous_profile)
        sys.settrace(previous_trace)


def _snapshot(context):
    # The seven-load trial already binds every original parameter/wrapper
    # value and edge. References into it stay actual references, not a second
    # reconstruction of those objects in the handler cache.
    inherited = [("inherited_reference", value) for value in context.parent.graph[0]]
    projection = SimpleNamespace(objects=[("parameters", context.p), *inherited, *context.objects])
    return core.caches.snapshot(
        dict(
            parent=context.parent.trial.identity,
            objects=[
                dict(kind=name, fields=literal._project(projection, vars(obj)))
                for name, obj in context.objects
            ],
            completed=context.completed,
        )
    )


def _graph(context):
    if not hasattr(context, "graph_view"):
        context.graph_view = SimpleNamespace()
        context.graph_fields = []
    view = context.graph_view
    context.graph_fields.clear()
    context.graph_fields.extend(vars(obj) for _, obj in context.objects)
    vars(view).clear()
    vars(view).update(
        parameters=context.p,
        objects=context.objects,
        fields=context.graph_fields,
        config=context.config,
        methods=getattr(context, "methods", {}),
        factories=getattr(context, "factories", {}),
    )
    return literal.callers._graph(view, view, context.tape)


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        parent=value.parent_identity,
        cache=value.cache.identity,
        stages=[(name, cache.identity) for name, cache in value.stages],
        events=value.events,
        work=value.work,
        warnings=value.warnings,
        parameter_claim=None if value.parameter_claim is None else asdict(value.parameter_claim),
        work_components_non_additive=True,
        source_completed=value.source_completed,
        failure_stage=value.failure_stage,
        phase_world_profiles_core_admitted=False,
        invalidated_owners=INVALIDATED_OWNERS,
    )


class HandlerOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the original same-parameter handler continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live handler owners cannot be serialized")

    @property
    def handler(self):
        return _validate(self).handler

    @property
    def parameters(self):
        return _validate(self).p

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not HandlerOwner or owner not in _ISSUED:
        raise AttachmentRejected("Issued same-p handler owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced handler owner")
        _check(context)
        core.caches.validate(context.trial.cache)
        if _snapshot(context).identity != context.trial.cache.identity:
            raise ValueError("Handler state changed")
        literal._same(_graph(context)[0], context.graph[0])
        if _graph(context)[1] != context.graph[1]:
            raise ValueError("Handler alias edges changed")
        if previous._digest(trial_record(context.trial)) != context.trial.identity:
            raise ValueError("Handler trial changed")
    except BaseException as error:
        context.invalid = True
        raise AttachmentRejected(
            "Stale same-parameter handler refused",
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
        or os.environ.get(previous.RELEASE) != "1"
    ):
        raise AttachmentRejected(
            "Actual same-p handler construction held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise AttachmentRejected(
                "Reentrant handler continuation refused", stage="reentrant", request=request
            )
        if type(request) is not Request or request not in _REQUESTS:
            raise AttachmentRejected(
                "Issued exact subconfiguration request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise AttachmentRejected("Handler attempt consumed", stage="consumed", request=request)
        context = SimpleNamespace(
            request=request,
            parent_refs=_REQUESTS[request],
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parent",
            objects=[],
            runtime_types={},
            runtime_bindings={},
            events=[],
            work=[],
            locals={},
            completed=[],
            stages=[],
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        primary = None
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            try:
                parent = previous._validate(request.parent)
                context.parent, context.p, context.config = parent, parent.p, parent.config
                context.bindings = _bindings()
                with _lease(context):
                    with _account(context):
                        context.stage = "native_factories"
                        context.work.append(
                            dict(
                                sequence=len(context.work),
                                layer="factory_import_acquisition",
                                method="_acquire",
                                status="attempted_not_success_or_case_credit",
                            )
                        )
                        _acquire(context)
                        _stop(context)
                        context.native_bindings = _native_bindings(context)
                        _namespace(context)
                        context.stage = "selected_handler_constructor"
                        _invoke(context, "__init__", context.handler, context.p)
                    _stop(context)
                    context.completed.append("__init__")
                    _check(context)
                    try:
                        context.stages.append(("__init__", _snapshot(context)))
                    except Exception as error:
                        captures._remember_observation_error(
                            context, error, origin="stage_snapshot", raw=context.handler
                        )
                    _stop(context)
            except BaseException as error:
                if not isinstance(error, literal._CaptureStop):
                    primary = error
            finally:
                context.active = False
                _ACTIVE.pop()
        partial = dict(
            context=context,
            parent=getattr(context, "parent", None),
            parent_trial=getattr(getattr(context, "parent", None), "trial", None),
            parameters=getattr(context, "p", None),
            handler=getattr(context, "handler", None),
            objects=context.objects,
            events=context.events,
            work=context.work,
            raw_locals=context.locals,
            last_completed=getattr(context, "last_completed", None),
            stages=context.stages,
            observation_errors=context.observation_errors,
            observation_raw=context.observation_raw,
            parameter_claim=getattr(context, "lease_context", None),
            parameter_claim_record=getattr(context, "lease_record", None),
            request_consumed=True,
            parameter_graph_rebased=False,
            usable_child_available=False,
        )
        if context.observation_error is not None:
            raise AttachmentRejected(
                "Handler observation failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=context.observation_error,
            ) from (primary if primary is not None else context.observation_error)
        if not hasattr(context, "parent") or not hasattr(context, "p"):
            raise AttachmentRejected(
                "Handler refused before available baseline",
                stage=context.stage,
                request=request,
                trial=None,
                partial=partial,
                source_error=primary,
            ) from primary
        try:
            trial = Trial(
                request.identity,
                request.before_trial_identity,
                _snapshot(context),
                tuple(context.stages),
                tuple(name for name, _ in context.events),
                tuple(context.work),
                tuple(str(w.message) for w in caught),
                getattr(context, "lease_record", None),
                primary is None,
                None if primary is None else context.stage,
                "",
            )
            context.trial = replace(trial, identity=previous._digest(trial_record(trial)))
        except BaseException as error:
            raise AttachmentRejected(
                "Handler sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None:
            raise AttachmentRejected(
                "Original selected handler source failed",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=partial,
                source_error=primary,
            ) from primary
        try:
            _check(context)
            context.graph = _graph(context)
            context.owner = object.__new__(HandlerOwner)
            _ISSUED[context.owner] = context
            return context.owner
        except BaseException as error:
            raise AttachmentRejected(
                "Handler child sealing failed",
                stage="capture",
                request=request,
                trial=context.trial,
                partial=partial,
                capture_error=error,
            ) from error


def require_phase(owner):
    context = _validate(owner)
    raise AttachmentRejected(
        "Actual phase caller/Cells/Simulator/cache and remaining Parameters stores required",
        stage="phase_prerequisites",
        trial=context.trial,
        partial=dict(phase_dyna_assignment=False, world_init_profiles_redo_gj_core_admitted=False),
    )
