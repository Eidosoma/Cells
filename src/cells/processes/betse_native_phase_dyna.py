"""Genuine same-phase dyna consumer preparation, gated on Key's public claim.

No prior HandlerOwner is attached. Only a fresh selected TissueHandler
constructor can produce phase.dyna, on the actual p retained by the issued
phase-cache child. The Key interface and cache retirement hooks must be bound
before any source attempt; neither inspection nor a serialized record suffices.
"""

import ast
import builtins
import hashlib
import importlib
import os
import sys
from collections import OrderedDict
from contextlib import contextmanager
from dataclasses import asdict, dataclass, is_dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakSet

from cells.processes import betse_native_phase_caches as caches
from cells.processes import betse_native_phase_dyna_source as source
from cells.processes import betse_native_tissue_handler_attachment as handler

literal, aliases, core = handler.literal, handler.aliases, handler.core
LAW_ID = "betse_same_issued_phase_selected_dyna_attachment@1"
RELEASE = "CELLS_NATIVE_PHASE_DYNA_RELEASED"
CACHE_SHA256 = "cbc1a5000a2674dae15937308414701e76671c32461d1ece7f1c81446b9a72b4"
HANDLER_SHA256 = "c0d9b1f5375620464167c13bc07815c996284e1d78eb753942c560f80a15470b"
KEY_MODULE = "cells.processes.betse_native_parameter_dyna_construction"
KEY_FILE = "src/cells/processes/betse_native_parameter_dyna_construction.py"
# Public names and producer match Key's reviewed source/software handoff.
# There is no provider argument, synthetic claim or inspection fallback.
KEY_SHA256 = "d9b444ae8991140f7b92f084d1c929a9a01cdc816b4cb7fa725798e495111f8d"
KEY_REVIEW_SHA256 = "ea85b6abbc761932359380cdf952213ed58428f42897ecdbe057222ef33a4695"
KEY_FACTORY = "continuation"
KEY_CLOSED_CHECK = "validate_closed"
KEY_CLAIM_TYPE = "DynaConstructionClaim"
KEY_LAW_ID = "betse_same_parameter_phase_dyna_construction_continuation@1"
CACHE_HOOKS = ("_claim_for_dyna", "_check_runtime_authority", "_cache_relationships")
METHODS = handler.METHODS
RETURN_ORDER = ("_init_tissues", "_init_cuts", "_init_events_global", "_init_events", "__init__")
BODY_CHILDREN = {
    "__init__": ("_init_tissues", "_init_cuts", "_init_events"),
    "_init_tissues": (),
    "_init_cuts": (),
    "_init_events": ("_init_events_global",),
    "_init_events_global": (),
}
_NATIVE = dict(handler._NATIVE)
_ATTACH = source.PhaseDynaContinuation.attach
_REQUESTS, _CONSUMED, _ISSUED, _OBJECTS = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []
_DESCRIPTOR_TYPES = WeakSet()


class DynaRejected(ValueError):
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
    cache_owner: caches.PhaseCachesOwner
    parent_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Dyna requests require the actual issued phase-cache child")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    stages: tuple
    events: tuple
    work: tuple
    method_entries: tuple
    constructor_claim: object
    completed: bool
    failure_stage: str | None
    identity: str


def _digest(value):
    return caches.previous.previous._digest(value)


def source_plan():
    for module, expected in ((caches, CACHE_SHA256), (handler, HANDLER_SHA256)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise ValueError("Explicit dyna source prerequisite changed")
    parent, leaf = caches.source_plan(), handler.source_plan()
    tree = ast.parse((aliases.NATIVE / caches.previous.PHASE).read_bytes())
    cls = caches.previous.callbacks.simulator._class(tree, "SimPhase")
    ctor = caches.previous.callbacks.simulator._method(cls, "__init__")
    store = next(
        node
        for node in caches.previous._body(ctor)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "dyna" for target in node.targets
        )
    )
    own = caches._method(
        ast.parse(Path(source.__file__).read_bytes()), "PhaseDynaContinuation", "attach"
    )
    if caches._statements([store]) != caches._statements(caches.previous._body(own)):
        raise ValueError("Literal TissueHandler constructor/phase.dyna assignment changed")
    return dict(
        law=LAW_ID,
        native_pins=parent["native_pins"],
        parent_producer=CACHE_SHA256,
        handler_producer=HANDLER_SHA256,
        handler_source=leaf,
        literal_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        phase_store_lines=(store.lineno, store.end_lineno),
        handler_methods=METHODS,
        entry_policy=(
            "one claim per method; exact active source-body caller and ordered child slots"
        ),
        key_producer=KEY_SHA256,
        key_dependency_review_sha256=KEY_REVIEW_SHA256,
        key_contract_bound=all(
            type(value) is str and value
            for value in (
                KEY_SHA256,
                KEY_FACTORY,
                KEY_CLOSED_CHECK,
                KEY_CLAIM_TYPE,
                KEY_LAW_ID,
            )
        ),
        required_cache_hooks=CACHE_HOOKS,
        parameters="same actual seven-load p; no added stores or changed configuration",
        original_missing_event_stores_are_failures=True,
        stopped_before=("_init_kludge", "init_profiles", "redo_gj", "init_core"),
        full_phase_parameters_world_or_physical_or_checkpoint_admitted=False,
    )


def _key_api():
    if not all(
        type(value) is str and value
        for value in (
            KEY_SHA256,
            KEY_FACTORY,
            KEY_CLOSED_CHECK,
            KEY_CLAIM_TYPE,
            KEY_LAW_ID,
        )
    ):
        raise DynaRejected("Key's actual public constructor API is not bound", stage="key_contract")
    root = Path(__file__).resolve().parents[3]
    path = root / KEY_FILE
    if (
        path.is_symlink()
        or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != KEY_SHA256
    ):
        raise DynaRejected("Exact Key constructor producer is unavailable", stage="key_producer")
    api = importlib.import_module(KEY_MODULE)
    if (
        sys.modules.get(KEY_MODULE) is not api
        or Path(api.__file__).resolve() != path
        or getattr(api, "PHASE_DYNA_CONSTRUCTION_LAW", None) != KEY_LAW_ID
        or not callable(getattr(api, KEY_FACTORY, None))
        or not callable(getattr(api, KEY_CLOSED_CHECK, None))
        or not isinstance(getattr(api, KEY_CLAIM_TYPE, None), type)
    ):
        raise DynaRejected("Real public Key API surface is unavailable", stage="key_contract")
    return api


def _cache_api():
    if any(not callable(getattr(caches, name, None)) for name in CACHE_HOOKS):
        raise DynaRejected(
            "Reviewed cache continuation hooks are unavailable", stage="cache_contract"
        )


def request_record(request):
    return dict(
        law=LAW_ID,
        parent=request.parent_identity,
        source=request.source_identity,
        new_handler=True,
        supplied_phase_or_handler=False,
    )


def from_cache(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise DynaRejected("Explicit same-phase dyna law required", stage="law")
    plan = source_plan()
    parent = caches._validate(owner)
    request = Request(owner, parent.trial.identity, _digest(plan), "")
    request = replace(request, identity=_digest(request_record(request)))
    _REQUESTS[request] = (
        parent,
        parent.trial,
        parent.phase,
        parent.parent.p,
        parent.parent.lease,
        parent.parent.lease_record,
    )
    return request


def _bindings():
    functions = (
        _digest,
        source_plan,
        _key_api,
        _cache_api,
        request_record,
        from_cache,
        _bindings,
        _key_bindings,
        _check,
        _guard,
        _closed_claim,
        _claim,
        _claim.__wrapped__,
        _acquire,
        _native_bindings,
        _surface,
        _factory_scope,
        _namespace,
        _namespace_bindings,
        _make_handler,
        _entry_rejected,
        _claim_entry,
        _admit_body,
        _release_entry,
        _entry_document,
        _invoke,
        _native_call,
        _old_snapshot,
        _old_graph,
        _snapshot,
        _graph,
        _account,
        _account.__wrapped__,
        trial_record,
        _validate,
        prepare,
        require_phase,
        _ATTACH,
        *_NATIVE.values(),
    )
    return (
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _OBJECTS,
        _LOCK,
        _ACTIVE,
        _DESCRIPTOR_TYPES,
        LAW_ID,
        RELEASE,
        CACHE_SHA256,
        HANDLER_SHA256,
        RETURN_ORDER,
        BODY_CHILDREN,
        *(atom for name, children in BODY_CHILDREN.items() for atom in (name, *children)),
        sys,
        *aliases._atoms(sys._getframe),
        KEY_MODULE,
        KEY_FILE,
        KEY_SHA256,
        KEY_REVIEW_SHA256,
        KEY_FACTORY,
        KEY_CLOSED_CHECK,
        KEY_CLAIM_TYPE,
        KEY_LAW_ID,
        *(atom for fn in functions for atom in aliases._atoms(fn)),
        *(
            atom
            for name in CACHE_HOOKS
            for atom in (name, *aliases._atoms(getattr(caches, name, None)))
        ),
    )


def _key_bindings(api):
    claim = getattr(api, KEY_CLAIM_TYPE)
    result = [api, claim, *literal._surface(claim)]
    for name in (KEY_FACTORY, KEY_CLOSED_CHECK):
        fn = getattr(api, name)
        result.extend((name, *aliases._atoms(fn)))
        if type(fn) is FunctionType:
            for member in caches.previous.callbacks.simulator._chain(fn):
                result.extend((member.__globals__, *aliases._atoms(member)))
    return tuple(result)


def _guard(context):
    # A rejected source entry is the primary failure even when its observer
    # subsequently fails to capture the event. Keep that capture separately.
    if getattr(context, "entry_error", None) is not None:
        raise context.entry_error
    handler._stop(context)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise DynaRejected("Selected dyna source entry unavailable", stage="source_entry")


def _closed_claim(context):
    # Public validation authenticates the current live ancestry and returns
    # this exact historical record; record serialization alone cannot do so.
    record = getattr(context.key, KEY_CLOSED_CHECK)(
        context.constructor_claim, original_lease=context.refs[4]
    )
    if (
        record is not context.constructor_claim_record
        or context.constructor_claim.record is not context.constructor_claim_record
    ):
        raise ValueError("Original closed dyna claim record changed")


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or caches._ISSUED.get(context.request.cache_owner) is not context.parent
        or getattr(caches, "_FORWARDED", {}).get(context.request.cache_owner) is not context
        or getattr(context.parent, "dyna_transition", None) is not context
    ):
        raise ValueError("Original irreversible dyna/cache association changed")
    caches._check_runtime_authority(context.parent)
    caches._cache_relationships(context.parent)
    if (
        context.parent.phase is not context.phase
        or context.parent.trial is not context.refs[1]
        or context.phase.p is not context.p
        or context.parent.parent.p is not context.p
        or context.parent.parent.lease is not context.refs[4]
        or context.parent.parent.lease_record is not context.refs[5]
        or _digest(request_record(context.request)) != context.request.identity
        or _digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Actual source phase/p/lease/request changed")
    prefix = context.parent.parent
    for name, actual in (
        ("SimPhase", context.phase),
        ("Cells", context.phase.cells),
        ("Simulator", context.phase.sim),
    ):
        if type(actual) is not prefix.runtime_types[name]:
            raise ValueError("Original issued phase/Cells/Simulator runtime class changed")
    literal._same(_bindings(), context.bindings)
    if _key_api() is not context.key:
        raise ValueError("Key producer identity changed")
    literal._same(_key_bindings(context.key), context.key_bindings)
    if hasattr(context, "before") and _old_snapshot(context).identity != context.before.identity:
        raise ValueError("A field outside phase.dyna changed")
    current = _old_graph(context)
    literal._same(current[0], context.old_graph[0])
    if current[1] != context.old_graph[1]:
        raise ValueError("Inherited phase/cache reference edges changed")
    if "dyna" in vars(context.phase) and (
        not context.constructor_completed or context.phase.dyna is not context.handler
    ):
        raise ValueError("Dyna assigned before its actual constructor returned")
    if hasattr(context, "native_bindings"):
        literal._same(_native_bindings(context), context.native_bindings)
    if hasattr(context, "modules"):
        aliases._check_modules()
        current_modules = aliases._module_records()
        for name, record in context.modules.items():
            actual = current_modules.get(name)
            if type(actual) is not tuple or actual[0] is not record[0] or actual[1:] != record[1:]:
                raise ValueError("Original dyna import identity changed")
    if hasattr(context, "namespace_bindings"):
        current = _namespace_bindings(context)
        literal._same(current[: len(context.namespace_bindings)], context.namespace_bindings)
    for role, actual in context.objects:
        if _OBJECTS.get(actual) is not context or type(actual) is not context.runtime_types[role]:
            raise ValueError("Original dyna/factory object issuance changed")
    for name, cls in context.runtime_types.items():
        literal._same(_surface(cls), context.runtime_bindings[name])
    if hasattr(context, "constructor_claim"):
        if context.active:
            context.constructor_claim.check()
            if context.constructor_claim.parameters is not context.p:
                raise ValueError("Foreign same-parameter constructor claim")
        else:
            _closed_claim(context)


@contextmanager
def _claim(context):
    try:
        factory = getattr(context.key, KEY_FACTORY)
        with factory(context.refs[4], law_id=KEY_LAW_ID, enabled=True) as claim:
            if type(claim) is not getattr(context.key, KEY_CLAIM_TYPE):
                raise ValueError("Actual issued public dyna claim required")
            context.constructor_claim = claim
            claim.check()
            if claim.parameters is not context.p:
                raise ValueError("Constructor claim lost the original p")
            yield
    except BaseException as error:
        context.constructor_claim_error = error
        try:
            partial = getattr(error, "dyna_continuation", None)
            if partial is None:
                partial = getattr(error, "partial", None)
            context.constructor_claim_partial = partial
        except BaseException as capture:
            handler.captures._remember_observation_error(
                context, capture, origin="dyna_claim_failure_evidence", raw=error
            )
        raise
    finally:
        if hasattr(context, "constructor_claim"):
            try:
                context.constructor_claim_record = context.constructor_claim.record
            except BaseException as error:
                handler.captures._remember_observation_error(
                    context, error, origin="dyna_claim_record", raw=context.constructor_claim
                )
        elif getattr(context, "constructor_claim_partial", None) is not None:
            # A failed __enter__ may retain an actually issued claim. Its
            # record is forensic evidence only and never becomes permission.
            try:
                failed = getattr(context.constructor_claim_partial, "claim", None)
                if type(failed) is getattr(context.key, KEY_CLAIM_TYPE):
                    context.failed_constructor_claim_record = failed.record
            except BaseException as error:
                handler.captures._remember_observation_error(
                    context,
                    error,
                    origin="failed_dyna_claim_record",
                    raw=context.constructor_claim_partial,
                )


def _acquire(context):
    handler._acquire(context)
    with aliases.issuing_native_imports(literal.source.SOURCE_PINS):
        module = importlib.import_module("betse.science.tissue.tishandler")
    native = module.TissueHandler
    if native.__bases__ != (object,) or native.__new__ is not object.__new__:
        raise ValueError("Original native TissueHandler class required")
    for name in METHODS:
        caches.previous.callbacks._source_function(
            getattr(native, name), "betse/science/tissue/tishandler.py", name, "TissueHandler"
        )
    context.native_handler = native
    context.modules = aliases._module_records()


def _native_bindings(context):
    result = [
        context.native_handler,
        *literal._surface(context.native_handler),
        *literal._surface(type(context.p)),
    ]
    for name in METHODS:
        for function in caches.previous.callbacks.simulator._chain(
            getattr(context.native_handler, name)
        ):
            result.extend((function.__globals__, *aliases._atoms(function)))
    for name, cls in context.factories.items():
        result.extend((name, cls, *literal._surface(cls)))
        if type(cls.__init__) is FunctionType:
            for function in caches.previous.callbacks.simulator._chain(cls.__init__):
                result.extend((function.__globals__, *aliases._atoms(function)))
    result.extend(atom for name, value in context.symbols.items() for atom in (name, value))
    return tuple(result)


def _surface(cls):
    values = list(literal._surface(cls))
    for base in cls.__mro__:
        for value in vars(base).values():
            if type(value) in _DESCRIPTOR_TYPES:
                values.extend((value.native, value.name))
    return tuple(values)


def _factory_scope(context):
    scope = dict(
        vars(handler),
        _FACTORY_OBJECTS=_OBJECTS,
        _guard=_guard,
        _check=_check,
        _native_call=_native_call,
        _event=handler._event,
        _stop=handler._stop,
        _surface=_surface,
        _native_bindings=_native_bindings,
        _DESCRIPTOR_TYPES=_DESCRIPTOR_TYPES,
    )
    return FunctionType(handler._factory_scope.__code__, scope)(context)


def _namespace(context):
    context.factory_scope = _factory_scope(context)

    def factory(name):
        def make(*args, **kwargs):
            return context.factory_scope["_make"](context, name, *args, **kwargs)

        return make

    def warning(*args):
        _guard(context)
        handler._event(context, "log_warning", args)
        _guard(context)

    namespace = dict(
        context.symbols,
        OrderedDict=OrderedDict,
        bool=builtins.bool,
        enumerate=builtins.enumerate,
        logs=SimpleNamespace(log_warning=warning),
        **{name: factory(name) for name in literal._FACTORY_MODULES},
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

    def unavailable(*args, **kwargs):
        _guard(context)
        raise DynaRejected(
            "Profile mapping/phase use remains unavailable", stage="handler_boundary"
        )

    fields = {}
    for base in reversed(context.native_handler.__mro__):
        for name, value in vars(base).items():
            if isinstance(value, FunctionType):
                fields[name] = unavailable
            elif isinstance(value, staticmethod):
                fields[name] = staticmethod(unavailable)
            elif isinstance(value, classmethod):
                fields[name] = classmethod(unavailable)
            elif isinstance(value, property):
                fields[name] = property(unavailable, unavailable, unavailable)

    def entry(name):
        def invoke(actual, p):
            return _invoke(context, name, actual, p)

        context.entry_wrappers[name] = invoke
        return invoke

    fields.update({name: entry(name) for name in METHODS})
    fields["__reduce_ex__"] = unavailable
    cls = type("OwnedPhaseTissueHandler", (context.native_handler,), fields)
    context.runtime_types["TissueHandler"] = cls
    context.runtime_bindings["TissueHandler"] = _surface(cls)
    context.attach = FunctionType(
        _ATTACH.__code__,
        dict(_ATTACH.__globals__, TissueHandler=lambda **kw: _make_handler(context, **kw)),
        _ATTACH.__name__,
        _ATTACH.__defaults__,
        _ATTACH.__closure__,
    )
    context.namespace_bindings = _namespace_bindings(context)


def _namespace_bindings(context):
    values = list(_surface(context.runtime_types["TissueHandler"]))
    values.append(context.entry_wrappers)
    for name, wrapper in context.entry_wrappers.items():
        values.extend((name, *aliases._atoms(wrapper)))
    for function in context.methods.values():
        values.extend((function, function.__globals__, *aliases._atoms(function)))
        for name in ("OrderedDict", "bool", "enumerate", *literal._FACTORY_MODULES):
            values.extend(aliases._atoms(function.__globals__[name]))
        values.append(function.__globals__["logs"])
        values.extend(aliases._atoms(function.__globals__["logs"].log_warning))
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
    values.extend((context.attach, context.attach.__globals__, *aliases._atoms(context.attach)))
    values.extend(aliases._atoms(context.attach.__globals__["TissueHandler"]))
    # Lazy factories append runtime surfaces at the end; original bindings
    # remain a stable prefix and every appended surface is checked separately.
    for cls in context.runtime_types.values():
        values.extend(_surface(cls))
    return tuple(values)


def _make_handler(context, *, p):
    _guard(context)
    _check(context)
    if p is not context.p or context.handler is not None:
        raise ValueError("One fresh handler on the actual p is required")
    cls = context.runtime_types["TissueHandler"]
    context.handler = object.__new__(cls)
    _OBJECTS[context.handler] = context
    context.objects.append(("TissueHandler", context.handler))
    context.work.append(
        dict(
            sequence=len(context.work),
            phase=context.stage,
            layer="new_handler_allocation",
            method="TissueHandler",
            entry_is_case=False,
        )
    )
    _invoke(context, "__init__", context.handler, p)
    return context.handler


def _entry_rejected(context, attempt, reason):
    context.invalid = True
    attempt["status"] = "rejected"
    attempt["reason"] = reason
    error = DynaRejected(reason, stage="method_entry", request=context.request, partial=context)
    if context.entry_error is None:
        context.entry_error = error
    raise context.entry_error


def _claim_entry(context, name, actual, p, invocation):
    # This reservation precedes validation, observations and delegate calls.
    # A callback cannot claim the next slot merely because a parent body is
    # somewhere on its stack: the immediate source frame and invocation must
    # both be the retained active parent.
    caller = invocation.f_back
    attempt = dict(
        sequence=len(context.entry_attempts),
        method=name,
        parent=None if not context.method_stack else context.method_stack[-1]["method"],
        caller=None if caller is None else caller.f_code.co_qualname,
        status="attempted",
    )
    context.entry_attempts.append(attempt)
    context.work.append(
        dict(
            sequence=len(context.work),
            phase=context.stage,
            layer="method_entry_attempt",
            method=name,
            entry_is_case=False,
        )
    )
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
        or actual is not context.handler
        or p is not context.p
        or name not in BODY_CHILDREN
        or name in context.method_claims
    ):
        _entry_rejected(context, attempt, "Repeated, foreign or unavailable method entry")
    parent = context.method_stack[-1] if context.method_stack else None
    if name == "__init__":
        factory = None if caller is None else caller.f_back
        body = None if factory is None else factory.f_back
        if (
            parent is not None
            or caller is None
            or caller.f_code is not _make_handler.__code__
            or caller.f_locals.get("context") is not context
            or factory is None
            or factory.f_code is not context.attach.__globals__["TissueHandler"].__code__
            or body is None
            or body.f_code is not context.attach.__code__
            or body.f_back is not context.driver_frame
            or body.f_locals.get("self") is not context.phase
            or body.f_locals.get("p") is not context.p
        ):
            _entry_rejected(
                context, attempt, "Root constructor must come from the actual phase call"
            )
    else:
        body = None if caller is None else caller.f_back
        children = () if parent is None else BODY_CHILDREN[parent["method"]]
        position = 0 if parent is None else parent["next_child"]
        wrapper = context.entry_wrappers.get(name)
        if (
            parent is None
            or parent["status"] != "calling_body"
            or position >= len(children)
            or children[position] != name
            or caller is None
            or type(wrapper) is not FunctionType
            or caller.f_code is not wrapper.__code__
            or caller.f_locals.get("context") is not context
            or caller.f_locals.get("name") != name
            or body is not parent["body_frame"]
            or body is None
            or body.f_back is not parent["invocation"]
            or body.f_code is not context.methods[parent["method"]].__code__
            or body.f_locals.get("self") is not actual
            or body.f_locals.get("p") is not p
        ):
            _entry_rejected(
                context, attempt, "Method must occupy its genuine ordered parent-body slot"
            )
        parent["next_child"] += 1
    attempt["status"] = "claimed"
    record = dict(
        method=name,
        parent=None if parent is None else parent["method"],
        invocation=invocation,
        body_frame=None,
        next_child=0,
        status="claimed",
        primary=None,
        attempt=attempt,
    )
    context.method_claims[name] = record
    context.method_stack.append(record)
    return record


def _admit_body(context, frame):
    record = context.method_stack[-1] if context.method_stack else None
    attempt = dict(
        sequence=len(context.entry_attempts),
        method=frame.f_code.co_qualname,
        parent=None if record is None else record["method"],
        status="body_attempt",
    )
    if (
        record is None
        or record["status"] != "calling_body"
        or record["body_frame"] is not None
        or frame.f_back is not record["invocation"]
        or frame.f_code is not context.methods[record["method"]].__code__
        or frame.f_locals.get("self") is not context.handler
        or frame.f_locals.get("p") is not context.p
    ):
        context.entry_attempts.append(attempt)
        _entry_rejected(context, attempt, "Unclaimed or detached source-body call")
    record["body_frame"] = frame


def _release_entry(context, record, primary):
    try:
        if not context.method_stack or context.method_stack[-1] is not record:
            raise ValueError("Method entry stack changed")
        context.method_stack.pop()
        record["primary"] = primary
        record["status"] = "returned" if primary is None else "failed"
        record["attempt"]["status"] = record["status"]
    except BaseException as error:
        context.invalid = True
        handler.captures._remember_observation_error(
            context, error, origin="method_entry_release", raw=record
        )


def _entry_document(context):
    return tuple(
        dict(
            method=record["method"],
            parent=record["parent"],
            status=record["status"],
            children_claimed=record["next_child"],
            body_entered=record["body_frame"] is not None,
        )
        for record in context.method_claims.values()
    )


def _invoke(context, name, actual, p):
    record = _claim_entry(context, name, actual, p, sys._getframe())
    primary = None
    try:
        _guard(context)
        _check(context)
        handler._event(context, name + "_enter", actual)
        _guard(context)
        _check(context)
        record["status"] = "calling_body"
        result = context.methods[name](actual, p)
        if record["next_child"] != len(BODY_CHILDREN[name]):
            _entry_rejected(context, record["attempt"], "Source body omitted a required child call")
        context.last_completed = (name, actual, result)
        context.stages.append(name)
        if name == "__init__":
            context.constructor_completed = True
        handler._event(context, name + "_return", actual)
        _guard(context)
        _check(context)
        return result
    except BaseException as error:
        primary = error
        handler._event(context, name + "_unwind", actual)
        raise
    finally:
        _release_entry(context, record, primary)


def _native_call(context, label, delegate, *args, **kwargs):
    _guard(context)
    _check(context)
    handler._event(context, label + "_enter", (args, kwargs))
    _guard(context)
    _check(context)
    try:
        result = delegate(*args, **kwargs)
    except BaseException:
        handler._event(context, label + "_unwind", (args, kwargs))
        raise
    context.last_completed = (label, result)
    handler._event(context, label + "_return", result)
    _guard(context)
    _check(context)
    return result


def _old_snapshot(context):
    projector = SimpleNamespace(
        objects=[
            ("parameters", context.p),
            ("callback", context.parent.parent.callback),
            *(("inherited", obj) for obj in context.parent.parent.parents[0].graph[0]),
            *context.parent.parent.objects,
            *context.parent.objects,
            *(("proxy", proxy) for _, proxy in context.parent.proxy_returns),
        ]
    )
    return core.caches.snapshot(
        [
            dict(
                role=role,
                fields=literal._project(
                    projector,
                    {
                        name: value
                        for name, value in vars(actual).items()
                        if actual is not context.phase or name != "dyna"
                    },
                ),
            )
            for role, actual in context.inherited_objects
        ]
    )


def _old_graph(context):
    for values, (_, actual) in zip(context.old_fields, context.inherited_objects, strict=True):
        values.clear()
        values.update(
            {
                name: value
                for name, value in vars(actual).items()
                if actual is not context.phase or name != "dyna"
            }
        )
    return literal.callers._graph(context.old_view, context.old_view, context.parent.tape)


def _snapshot(context):
    projector = SimpleNamespace(
        objects=[
            ("parameters", context.p),
            ("callback", context.parent.parent.callback),
            *(("inherited", value) for value in context.parent.parent.parents[0].graph[0]),
            *context.inherited_objects,
            *context.objects,
            *(("proxy", value) for _, value in context.parent.proxy_returns),
        ]
    )
    return core.caches.snapshot(
        dict(
            parent=context.refs[1].identity,
            phase=literal._project(projector, vars(context.phase)),
            objects=[
                dict(role=role, fields=literal._project(projector, vars(actual)))
                for role, actual in context.objects
            ],
            stages=context.stages,
        )
    )


def _graph(context):
    context.graph_fields.clear()
    context.graph_fields.extend(vars(actual) for _, actual in context.objects)
    vars(context.graph_view).clear()
    vars(context.graph_view).update(
        phase=context.phase,
        phase_fields=vars(context.phase),
        objects=context.objects,
        fields=context.graph_fields,
    )
    return literal.callers._graph(context.graph_view, context.graph_view, context.tape)


@contextmanager
def _account(context):
    scope = dict(
        vars(handler),
        _NATIVE=dict(_NATIVE, phase_attach=_ATTACH),
        _acquire=_acquire,
        _namespace=_namespace,
    )
    account = contextmanager(FunctionType(handler._account.__wrapped__.__code__, scope))
    with account(context):
        observer = sys.getprofile()
        codes = (
            {function.__code__ for function in context.methods.values()}
            if hasattr(context, "methods")
            else set()
        )

        def profile(frame, event, arg):
            selected = frame.f_code in codes or (
                hasattr(context, "methods")
                and any(frame.f_code is fn.__code__ for fn in context.methods.values())
            )
            if event == "call" and selected:
                _admit_body(context, frame)
            if event in ("call", "c_call"):
                observer(frame, event, arg)
            else:
                try:
                    observer(frame, event, arg)
                except BaseException as error:
                    handler.captures._remember_observation_error(
                        context,
                        error,
                        origin="method_prior_profile_" + event,
                        raw=(frame, event, arg),
                    )
            if event == "call" and selected:
                # An inherited callback may catch its rejected entry. The
                # poisoned attempt still stops before the original body runs.
                _guard(context)
                _check(context)

        sys.setprofile(profile)
        try:
            yield
        finally:
            sys.setprofile(observer)


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        stages=trial.stages,
        events=trial.events,
        work=trial.work,
        method_entries=trial.method_entries,
        constructor_claim=None
        if trial.constructor_claim is None
        else asdict(trial.constructor_claim),
        completed=trial.completed,
        failure_stage=trial.failure_stage,
        full_phase_profiles_core_physical_or_checkpoint_admitted=False,
    )


class PhaseDynaOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine same-phase dyna continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No phase/dyna hydration or ordinary checkpoint authority")

    @property
    def partial_phase(self):
        return _validate(self).phase

    @property
    def dyna(self):
        return _validate(self).handler

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not PhaseDynaOwner or owner not in _ISSUED:
        raise DynaRejected("Actual issued dyna child required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced dyna child")
        _check(context)
        if (
            tuple(vars(context.phase)) != (*caches.previous.FIELDS, "cache", "dyna")
            or context.phase.dyna is not context.handler
            or not context.constructor_completed
            or tuple(context.stages) != RETURN_ORDER
            or context.method_stack
            or set(context.method_claims) != set(METHODS)
            or _entry_document(context) != context.trial.method_entries
            or _snapshot(context).identity != context.trial.cache.identity
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Completed same-phase dyna state changed")
        actual = _graph(context)
        literal._same(actual[0], context.graph[0])
        if actual[1] != context.graph[1]:
            raise ValueError("Dyna reference edges changed")
    except BaseException as error:
        context.invalid = True
        raise DynaRejected(
            "Stale dyna child",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise DynaRejected("Real dyna construction remains held", stage="release", request=request)
    # Both are actual producer prerequisites, checked before retirement/work.
    key = _key_api()
    _cache_api()
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise DynaRejected("Reentrant dyna attempt", stage="reentrant", request=request)
        if type(request) is not Request or request not in _REQUESTS:
            raise DynaRejected(
                "Actual issued cache request required", stage="request", request=request
            )
        if request in _CONSUMED:
            raise DynaRejected("Dyna attempt consumed", stage="consumed", request=request)
        refs = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=refs[0],
            phase=refs[2],
            p=refs[3],
            key=key,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parent_preflight",
            objects=[],
            runtime_types={},
            runtime_bindings={},
            handler=None,
            events=[],
            work=[],
            locals={},
            stages=[],
            constructor_completed=False,
            driver_frame=sys._getframe(),
            entry_wrappers={},
            method_claims={},
            method_stack=[],
            entry_attempts=[],
            entry_error=None,
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            graph_view=SimpleNamespace(),
            graph_fields=[],
            inherited_objects=[*refs[0].parent.objects, *refs[0].objects],
        )
        context.old_fields = [{} for _ in context.inherited_objects]
        context.old_view = SimpleNamespace(
            objects=context.inherited_objects,
            fields=context.old_fields,
            parameters=context.p,
            proxies=context.parent.proxy_returns,
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        primary = None
        try:
            if caches._validate(request.cache_owner) is not context.parent:
                raise ValueError("Cache parent association changed")
            context.before, context.old_graph = _old_snapshot(context), _old_graph(context)
            context.bindings, context.key_bindings = _bindings(), _key_bindings(key)
            context.stage = "cache_retirement"
            if (
                caches._claim_for_dyna(
                    request.cache_owner, expected=context.parent, transition=context
                )
                is not context.parent
            ):
                raise ValueError("Cache retirement returned a foreign parent")
            with _claim(context):
                _check(context)
                with _account(context):
                    context.stage = "native_dyna_factories"
                    _acquire(context)
                    context.native_bindings = _native_bindings(context)
                    _namespace(context)
                    context.stage = "same_parameter_handler_constructor_assignment"
                    context.attach(context.phase, context.p)
                    _guard(context)
                    _check(context)
        except BaseException as error:
            if not isinstance(error, literal._CaptureStop) or context.observation_error is None:
                primary = error
        finally:
            context.active = False
            _ACTIVE.pop()
        partial = dict(
            context=context,
            parent=context.parent,
            parent_trial=refs[1],
            phase=context.phase,
            parameters=context.p,
            handler=context.handler,
            objects=context.objects,
            stages=context.stages,
            events=context.events,
            work=context.work,
            raw_locals=context.locals,
            method_attempts=context.entry_attempts,
            method_entries=_entry_document(context),
            entry_error=context.entry_error,
            last_completed=getattr(context, "last_completed", None),
            constructor_claim=getattr(context, "constructor_claim", None),
            constructor_claim_error=getattr(context, "constructor_claim_error", None),
            constructor_claim_partial=getattr(context, "constructor_claim_partial", None),
            constructor_claim_record=getattr(context, "constructor_claim_record", None),
            failed_constructor_claim_record=getattr(
                context, "failed_constructor_claim_record", None
            ),
            usable_child_available=False,
        )
        capture, trial = context.observation_error, None
        try:
            if hasattr(context, "before"):
                record = getattr(
                    context,
                    "constructor_claim_record",
                    getattr(context, "failed_constructor_claim_record", None),
                )
                if record is not None and not is_dataclass(record):
                    raise ValueError("Typed actual Key claim record required")
                value = Trial(
                    request.identity,
                    refs[1].identity,
                    context.before,
                    _snapshot(context),
                    tuple(context.stages),
                    tuple(name for name, _ in context.events),
                    tuple(context.work),
                    _entry_document(context),
                    record,
                    context.constructor_completed and primary is None and capture is None,
                    None if primary is None and capture is None else context.stage,
                    "",
                )
                trial = replace(value, identity=_digest(trial_record(value)))
                context.trial = trial
        except BaseException as error:
            raise DynaRejected(
                "Dyna trial sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None or capture is not None or trial is None:
            raise DynaRejected(
                "Native dyna attempt refused",
                stage=context.stage,
                request=request,
                trial=trial,
                partial=partial,
                source_error=primary,
                capture_error=capture,
            ) from (primary if primary is not None else capture)
        try:
            _check(context)
            if (
                tuple(vars(context.phase)) != (*caches.previous.FIELDS, "cache", "dyna")
                or tuple(context.stages) != RETURN_ORDER
            ):
                raise ValueError("Exact original dyna assignment order required")
            context.graph = _graph(context)
            context.owner = object.__new__(PhaseDynaOwner)
            _ISSUED[context.owner] = context
            return context.owner
        except BaseException as error:
            context.invalid = True
            raise DynaRejected(
                "Dyna child sealing failed",
                stage="capture",
                request=request,
                trial=trial,
                partial=partial,
                capture_error=error,
            ) from error


def require_phase(owner):
    context = _validate(owner)
    raise DynaRejected(
        "Kludge, complete parameter loading, profile mapping and init_core remain unavailable",
        stage="phase_incomplete",
        request=context.request,
        trial=context.trial,
        partial=context,
    )
