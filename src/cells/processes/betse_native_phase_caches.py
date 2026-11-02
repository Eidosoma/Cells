"""Live same-phase cache construction, stopping before TissueHandler/dyna.

Only selected constructor bodies are owned. Lazy cache properties, complete
phase use and physical/checkpoint admission remain unavailable. This module
never recreates a phase or cache from inspection records.
"""

import ast
import builtins
import hashlib
import importlib
import os
import sys
import weakref
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_phase_assembly as previous
from cells.processes import betse_native_phase_cache_source as source

literal, captures = previous.literal, previous.inherited.captures
aliases, core = previous.aliases, previous.core
LAW_ID = "betse_same_live_phase_cache_constructors@1"
MODE = "prepared_callback_seven_load_phase_cache_prefix"
RELEASE = "CELLS_NATIVE_PHASE_CACHES_RELEASED"
PARENT_SHA256 = "dd43316e55ff4d7f39aad4cb7bee87512c969633a513f1df95020a14f1a6e140"
MODULES = {
    "SimPhaseCaches": "betse.science.math.cache.cacheabc",
    "SimPhaseCacheABC": "betse.science.math.cache.cacheabc",
    "SimPhaseCacheUpscaled": "betse.science.math.cache.cacheupscaled",
    "SimPhaseCacheVectorCells": "betse.science.math.cache.cachevec",
    "SimPhaseCacheLayerCellsVector": "betse.science.math.cache.cachelyrvec",
    "SimPhaseCacheVectorFieldCells": "betse.science.math.cache.cachevecfld",
}
IMPORTS = {
    MODULES[name]: (name,)
    for name in (
        "SimPhaseCacheUpscaled",
        "SimPhaseCacheVectorCells",
        "SimPhaseCacheVectorFieldCells",
        "SimPhaseCacheLayerCellsVector",
    )
}
ROLES = tuple(name for name in MODULES if name != "SimPhaseCacheABC")
_METHODS = dict(
    attach=source.PhaseCacheContinuation.attach,
    top=source.CacheConstructor.__init__,
    abc=source.CacheABCConstructor.__init__,
    vector=source.CacheVectorConstructor.__init__,
    proxy=source.proxy_weak,
)
_REQUESTS, _CONSUMED, _ISSUED, _OBJECTS = (WeakKeyDictionary() for _ in range(4))
_FORWARDED = WeakKeyDictionary()
_LOCK, _ACTIVE = RLock(), []


class CacheConstructionRejected(ValueError):
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
    phase_owner: previous.AssemblyOwner
    parent_identity: str
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Phase-cache requests require their live issued parent")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    events: tuple
    work: tuple
    factory_attempts: tuple
    factory_returns: tuple
    body_attempts: tuple
    body_returns: tuple
    proxy_attempts: int
    proxy_returns: int
    completed: bool
    failure_stage: str | None
    identity: str


def _method(tree, cls, method):
    return previous.callbacks.simulator._method(
        previous.callbacks.simulator._class(tree, cls), method
    )


def _statements(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]))


def _method_code(relative, cls):
    """Compile metadata within a class so zero-argument super keeps its cell.

    The compiled class/module is never executed. Compiling the vector method
    as a module-level function would lose __class__ and reject genuine code.
    """
    node = _method(ast.parse((aliases.NATIVE / relative).read_bytes()), cls, "__init__")
    node.decorator_list = []
    shell = ast.ClassDef(
        name=cls, bases=[], keywords=[], body=[node], decorator_list=[], type_params=[]
    )
    module = ast.fix_missing_locations(ast.Module(body=[shell], type_ignores=[]))
    code = compile(module, str(aliases.NATIVE / relative), "exec", dont_inherit=True)
    body = next(
        value for value in code.co_consts if type(value) is CodeType and value.co_name == cls
    )
    return next(
        value for value in body.co_consts if type(value) is CodeType and value.co_name == "__init__"
    )


def _source_method(cls, relative):
    method = previous.callbacks.simulator._chain(cls.__init__)[-1]
    module = sys.modules.get(relative[:-3].replace("/", "."))
    expected = _method_code(relative, cls.__name__)
    if (
        module is None
        or method.__globals__ is not vars(module)
        or method.__code__.co_filename != str(aliases.NATIVE / relative)
        or previous.callbacks.simulator._code(method.__code__)
        != previous.callbacks.simulator._code(expected)
    ):
        raise ValueError("Original cache constructor executable changed: " + cls.__name__)
    if method.__code__.co_freevars and (
        method.__code__.co_freevars != ("__class__",)
        or len(method.__closure__) != 1
        or method.__closure__[0].cell_contents is not cls
    ):
        raise ValueError("Original vector constructor class cell changed")
    return method


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SHA256:
        raise ValueError("Explicit phase-prefix producer changed")
    parent = previous.source_plan()
    owned = ast.parse(Path(source.__file__).read_bytes())
    phase = ast.parse((aliases.NATIVE / previous.PHASE).read_bytes())
    assignment = next(
        node
        for node in previous._body(_method(phase, "SimPhase", "__init__"))
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Attribute) and target.attr == "cache" for target in node.targets
        )
    )
    if _statements([assignment]) != _statements(
        previous._body(_method(owned, "PhaseCacheContinuation", "attach"))
    ):
        raise ValueError("Literal self.cache construction/assignment changed")
    selections = (
        ("betse/science/math/cache/cacheabc.py", "SimPhaseCaches", "CacheConstructor"),
        ("betse/science/math/cache/cacheabc.py", "SimPhaseCacheABC", "CacheABCConstructor"),
        (
            "betse/science/math/cache/cachevec.py",
            "SimPhaseCacheVectorCells",
            "CacheVectorConstructor",
        ),
    )
    lines = {}
    for path, native_class, owned_class in selections:
        method = _method(ast.parse((aliases.NATIVE / path).read_bytes()), native_class, "__init__")
        body = previous._body(method)
        if _statements(body) != _statements(
            previous._body(_method(owned, owned_class, "__init__"))
        ):
            raise ValueError("Original cache constructor body changed: " + native_class)
        lines[native_class] = [body[0].lineno, body[-1].end_lineno]
    native_proxy = next(
        n
        for n in ast.parse((aliases.NATIVE / "betse/util/py/pyref.py").read_bytes()).body
        if isinstance(n, ast.FunctionDef) and n.name == "proxy_weak"
    )
    owned_proxy = next(
        n for n in owned.body if isinstance(n, ast.FunctionDef) and n.name == "proxy_weak"
    )
    if _statements(previous._body(native_proxy)) != _statements(previous._body(owned_proxy)):
        raise ValueError("Original weak-proxy/idempotence body changed")
    return dict(
        law=LAW_ID,
        mode=MODE,
        native_pins=parent["native_pins"],
        parent_producer_sha256=PARENT_SHA256,
        literal_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        phase_store_lines=[assignment.lineno, assignment.end_lineno],
        constructor_lines=lines,
        factory_order=ROLES,
        required_phase_hook="_claim_for_caches(owner, expected=parent, transition=context)",
        weak_phase_links="four actual proxies; vector.layer preserves existing proxy",
        parameter_reads_or_stores=(),
        work_accounting="factory/body/proxy views are non-additive work; no biological cases",
        stopped_before=("self.dyna", "_init_kludge", "lazy cache properties"),
        full_phase_or_world_or_physical_or_checkpoint_admitted=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID, mode=value.mode, parent=value.parent_identity, source=value.source_identity
    )


def from_phase(owner, *, law_id, mode):
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise CacheConstructionRejected("Explicit cache-prefix law/mode required", stage="law")
    plan = source_plan()
    parent = previous._validate(owner)
    value = Request(owner, parent.trial.identity, previous.previous._digest(plan), mode, "")
    value = replace(value, identity=previous.previous._digest(request_record(value)))
    _REQUESTS[value] = parent
    return value


def _bindings():
    functions = (
        _method,
        _method_code,
        _source_method,
        _statements,
        source_plan,
        request_record,
        from_phase,
        _bindings,
        _guard,
        _check,
        _check_runtime_authority,
        _cache_relationships,
        _acquire,
        _native_bindings,
        _runtime_type,
        _make,
        _body_call,
        _proxy,
        _import_native,
        _imports,
        _namespace,
        _scope_bindings,
        _associations,
        _old_snapshot,
        _snapshot,
        _old_graph,
        _graph,
        _validate,
        _validate_completed,
        _claim_for_dyna,
        prepare,
        trial_record,
        require_phase,
        _account,
        _account.__wrapped__,
        previous._check,
        previous._bindings,
        previous._surface,
        previous.inherited._event,
        previous.inherited._stop,
        *(_METHODS.values()),
    )
    hook = getattr(previous, "_claim_for_caches", None)
    return (
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _OBJECTS,
        _FORWARDED,
        _LOCK,
        _ACTIVE,
        LAW_ID,
        MODE,
        RELEASE,
        PARENT_SHA256,
        MODULES,
        IMPORTS,
        ROLES,
        getattr(previous, "_FORWARDED", None),
        *(atom for fn in (*functions, hook) for atom in aliases._atoms(fn)),
        *(atom for name, path in MODULES.items() for atom in (name, path)),
        *(atom for name, items in IMPORTS.items() for atom in (name, *items)),
        *aliases._atoms(builtins.__import__),
    )


def _guard(context):
    previous.inherited._stop(context)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise CacheConstructionRejected("Native cache entry unavailable", stage="source_entry")


def _check_runtime_authority(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _REQUESTS.get(context.request) is not context.parent
        or _CONSUMED.get(context.request) is not context
        or previous._ISSUED.get(context.request.phase_owner) is not context.parent
        or getattr(previous, "_FORWARDED", {}).get(context.request.phase_owner) is not context
        or getattr(context.parent, "cache_transition", None) is not context
    ):
        raise ValueError("Original phase-cache issuance/irreversible claim changed")
    # This retains original constructor/callback/parameter/closed-Lease checks.
    # The consumed prefix cache validator is deliberately not reopened.
    previous._check_runtime_authority(context.parent)
    if "cache" in vars(context.phase) and (
        not context.factory_returns
        or context.factory_returns[-1] != "SimPhaseCaches"
        or context.phase.cache is not context.constructed.get("SimPhaseCaches")
    ):
        raise ValueError("Phase.cache assignment preceded its actual completed constructor")
    if (
        context.parent.phase is not context.phase
        or context.parent.trial is not context.parent_trial
        or context.parent.trial.identity != context.request.parent_identity
        or previous.previous._digest(request_record(context.request)) != context.request.identity
        or previous.previous._digest(source_plan()) != context.request.source_identity
    ):
        raise ValueError("Original phase/source/trial association changed")
    literal._same(_bindings(), context.bindings)
    if hasattr(context, "native_bindings"):
        literal._same(_native_bindings(context), context.native_bindings)
    if hasattr(context, "scope_bindings"):
        literal._same(_scope_bindings(context), context.scope_bindings)
    for role, cls in context.runtime_types.items():
        literal._same(previous._surface(cls), context.runtime_bindings[role])
    for index, (role, obj) in enumerate(context.objects):
        issued = _OBJECTS.get(obj)
        if (
            type(issued) is not tuple
            or len(issued) != 2
            or issued[0] is not context
            or issued[1] != role
        ):
            raise ValueError("Raw cache constructor object issuance changed")
        if hasattr(context, "object_issuance") and (
            index >= len(context.object_issuance) or issued is not context.object_issuance[index]
        ):
            raise ValueError("Original cache issuance tuple reference changed")
    if hasattr(context, "object_issuance") and len(context.objects) != len(context.object_issuance):
        raise ValueError("Original cache raw object roster changed")
    if hasattr(context, "modules"):
        aliases._check_modules()
        now = aliases._module_records()
        for name, record in context.modules.items():
            actual = now.get(name)
            if type(actual) is not tuple or actual[0] is not record[0] or actual[1:] != record[1:]:
                raise ValueError("Original cache import identity changed")


def _check(context):
    _check_runtime_authority(context)
    previous._check(context.parent)
    if _old_snapshot(context).identity != context.before.identity:
        raise ValueError("A field outside the single cache assignment changed")
    current = _old_graph(context)
    literal._same(current[0], context.old_graph[0])
    if current[1] != context.old_graph[1]:
        raise ValueError("Original prefix reference edges changed")


def _acquire(context):
    with aliases.issuing_native_imports(literal.source.SOURCE_PINS):
        imported = {name: importlib.import_module(name) for name in dict.fromkeys(MODULES.values())}
        pyref = importlib.import_module("betse.util.py.pyref")
    context.factories = {name: getattr(imported[path], name) for name, path in MODULES.items()}
    for name, cls in context.factories.items():
        expected = (
            (object,)
            if name in ("SimPhaseCaches", "SimPhaseCacheABC")
            else (context.factories["SimPhaseCacheABC"],)
        )
        if cls.__bases__ != expected or cls.__new__ is not object.__new__:
            raise ValueError("Actual original cache class required: " + name)
    for name in ("SimPhaseCaches", "SimPhaseCacheABC", "SimPhaseCacheVectorCells"):
        _source_method(context.factories[name], MODULES[name].replace(".", "/") + ".py")
    previous.callbacks._source_function(pyref.proxy_weak, "betse/util/py/pyref.py", "proxy_weak")
    context.pyref = pyref
    context.import_modules = imported
    context.modules = aliases._module_records()


def _native_bindings(context):
    return (
        *(
            atom
            for name, cls in context.factories.items()
            for atom in (name, *previous._surface(cls))
        ),
        context.pyref,
        *aliases._atoms(context.pyref.proxy_weak),
        *(
            atom
            for cls in context.factories.values()
            for function in previous.callbacks.simulator._chain(cls.__init__)
            for atom in (function.__globals__, function.__builtins__, *aliases._atoms(function))
        ),
        context.pyref.WeakRefProxyTypes,
        *context.pyref.WeakRefProxyTypes,
        context.pyref.weakref,
        *aliases._atoms(context.pyref.weakref.proxy),
        *aliases._atoms(weakref.getweakrefs),
    )


def _runtime_type(context, role):
    _guard(context)
    if role in context.runtime_types:
        return context.runtime_types[role]
    native = context.factories[role]

    def unavailable(*args, **kwargs):
        _guard(context)
        raise CacheConstructionRejected(
            "Lazy/full cache surface unavailable", stage="cache_boundary"
        )

    namespace = {}
    # Shadow all inherited Python callables and descriptors before body access.
    for base in reversed(native.__mro__):
        for name, member in vars(base).items():
            if isinstance(member, FunctionType):
                namespace[name] = unavailable
            elif isinstance(member, staticmethod):
                namespace[name] = staticmethod(unavailable)
            elif isinstance(member, classmethod):
                namespace[name] = classmethod(unavailable)
            elif isinstance(member, property) or (
                not isinstance(member, type)
                and hasattr(type(member), "__get__")
                and not name.startswith("__")
            ):
                namespace[name] = property(unavailable, unavailable, unavailable)
    key = {
        "SimPhaseCaches": "top",
        "SimPhaseCacheABC": "abc",
        "SimPhaseCacheVectorCells": "vector",
    }.get(role)
    if key is not None:

        def init(actual, *args, **kwargs):
            return _body_call(context, role, context.methods[key], actual, *args, **kwargs)

        namespace["__init__"] = init
    else:
        namespace.pop("__init__", None)
    namespace["__reduce_ex__"] = unavailable
    bases = (
        (native,)
        if role in ("SimPhaseCaches", "SimPhaseCacheABC")
        else (
            native,
            _runtime_type(context, "SimPhaseCacheABC"),
        )
    )
    cls = type("Owned" + role, bases, namespace)
    context.runtime_types[role] = cls
    context.runtime_bindings[role] = previous._surface(cls)
    return cls


def _make(context, role, /, *args, **kwargs):
    _guard(context)
    _check(context)
    if (
        role not in ROLES
        or tuple(context.factory_attempts) != ROLES[: len(context.factory_attempts)]
    ):
        raise ValueError("Original cache factory order changed")
    if len(context.factory_attempts) >= len(ROLES) or role != ROLES[len(context.factory_attempts)]:
        raise ValueError("Unexpected/repeated native cache constructor")
    context.factory_attempts.append(role)
    cls = _runtime_type(context, role)
    actual = object.__new__(cls)
    issued = (context, role)
    _OBJECTS[actual] = issued
    context.objects.append((role, actual))
    context.object_issuance.append(issued)
    context.constructed[role] = actual
    context.work.append(
        dict(
            sequence=len(context.work),
            phase=context.stage,
            layer="native_factory_allocation",
            method=role,
            entry_is_case=False,
        )
    )
    cls.__init__(actual, *args, **kwargs)
    context.factory_returns.append(role)
    return actual


def _body_call(context, role, delegate, actual, *args, **kwargs):
    _guard(context)
    _check(context)
    issued = _OBJECTS.get(actual)
    if issued is None or issued[0] is not context:
        raise ValueError("Unissued raw cache constructor object")
    if kwargs:
        if role != "SimPhaseCaches" or args or tuple(kwargs) != ("phase",):
            raise ValueError("Original cache constructor argument layout changed")
        phase = kwargs["phase"]
    elif len(args) == 1:
        phase = args[0]
    else:
        raise ValueError("Original one-phase cache constructor argument required")
    expected = context.phase
    if issued[1] == "SimPhaseCacheLayerCellsVector":
        expected = context.constructed["SimPhaseCacheVectorCells"]._phase
    if phase is not expected:
        raise ValueError("Cache constructor lost the actual phase/proxy argument")
    label = role + ".__init__"
    context.body_attempts.append((role, issued[1]))
    previous.inherited._event(context, label + "_enter", actual)
    _guard(context)
    _check(context)
    try:
        value = delegate(actual, *args, **kwargs)
    except BaseException:
        previous.inherited._event(context, label + "_unwind", actual)
        raise
    context.last_completed = (label, actual, value)
    context.body_returns.append((role, issued[1]))
    previous.inherited._event(context, label + "_return", actual)
    previous.inherited._stop(context)
    _check(context)
    return value


def _proxy(context, value):
    _guard(context)
    _check(context)
    context.proxy_attempts.append(value)
    previous.inherited._event(context, "proxy_weak_enter", value)
    _guard(context)
    _check(context)
    try:
        result = context.methods["proxy"](value)
    except BaseException:
        previous.inherited._event(context, "proxy_weak_unwind", value)
        raise
    # Retain the actual weak result before an observer can reject its return.
    context.proxy_returns.append((value, result))
    context.last_completed = ("proxy_weak", value, result)
    previous.inherited._event(context, "proxy_weak_return", result)
    previous.inherited._stop(context)
    return result


def _import_native(name, globals, locals, fromlist, level):
    return builtins.__import__(name, globals, locals, fromlist, level)


def _imports(context, name, globals=None, locals=None, fromlist=(), level=0):
    _guard(context)
    _check(context)
    if level or name not in IMPORTS or tuple(fromlist) != IMPORTS[name]:
        raise ValueError("Unexpected original cache constructor import")
    actual = _import_native(name, globals, locals, fromlist, level)
    if actual is not context.import_modules[name]:
        raise ValueError("Original cache constructor module changed")
    context.import_order.append(name)
    if tuple(context.import_order) != tuple(IMPORTS)[: len(context.import_order)]:
        raise ValueError("Original cache import order changed")
    role = IMPORTS[name][0]
    return SimpleNamespace(**{role: lambda *args, **kwargs: _make(context, role, *args, **kwargs)})


def _namespace(context):
    private = dict(vars(builtins), __import__=lambda *a, **kw: _imports(context, *a, **kw))
    proxy_scope = dict(
        vars(source),
        __builtins__=private,
        WeakRefProxyTypes=context.pyref.WeakRefProxyTypes,
        weakref=context.pyref.weakref,
    )
    context.methods = {}
    for key, original in _METHODS.items():
        scope = dict(vars(source), __builtins__=private)
        scope["SimPhaseCaches"] = lambda *a, **kw: _make(context, "SimPhaseCaches", *a, **kw)
        scope["pyref"] = SimpleNamespace(proxy_weak=lambda value: _proxy(context, value))
        if key == "proxy":
            scope = proxy_scope
        closure = original.__closure__
        if key == "vector":
            native = previous.callbacks.simulator._chain(
                context.factories["SimPhaseCacheVectorCells"].__init__
            )[-1]
            if native.__code__.co_freevars != original.__code__.co_freevars:
                raise ValueError("Original vector superclass class cell changed")
            closure = native.__closure__
        context.methods[key] = FunctionType(
            original.__code__, scope, original.__name__, original.__defaults__, closure
        )
    context.scope_bindings = _scope_bindings(context)


def _scope_bindings(context):
    result = []
    for key, method in context.methods.items():
        scope = method.__globals__
        result.extend((key, method, scope, method.__builtins__, *aliases._atoms(method)))
        result.extend(aliases._atoms(method.__builtins__["__import__"]))
        if key == "vector":
            result.extend(aliases._atoms(method.__builtins__["super"]))
        if key == "proxy":
            result.extend(
                (scope["WeakRefProxyTypes"], *scope["WeakRefProxyTypes"], scope["weakref"])
            )
            result.extend(aliases._atoms(scope["weakref"].proxy))
            result.extend(aliases._atoms(method.__builtins__["isinstance"]))
        else:
            result.extend(aliases._atoms(scope["SimPhaseCaches"]))
            result.extend((scope["pyref"], *aliases._atoms(scope["pyref"].proxy_weak)))
    return tuple(result)


def _cache_relationships(context):
    phase, made = context.phase, context.constructed
    body_order = (
        ("SimPhaseCaches", "SimPhaseCaches"),
        ("SimPhaseCacheABC", "SimPhaseCacheUpscaled"),
        ("SimPhaseCacheVectorCells", "SimPhaseCacheVectorCells"),
        ("SimPhaseCacheABC", "SimPhaseCacheVectorCells"),
        ("SimPhaseCacheABC", "SimPhaseCacheLayerCellsVector"),
        ("SimPhaseCacheABC", "SimPhaseCacheVectorFieldCells"),
    )
    if (
        tuple(vars(phase))[: len(previous.FIELDS) + 1] != (*previous.FIELDS, "cache")
        or phase.cache is not made.get("SimPhaseCaches")
        or tuple(context.factory_attempts) != ROLES
        or tuple(context.factory_returns)
        != (
            "SimPhaseCacheUpscaled",
            "SimPhaseCacheLayerCellsVector",
            "SimPhaseCacheVectorCells",
            "SimPhaseCacheVectorFieldCells",
            "SimPhaseCaches",
        )
        or tuple(context.body_attempts) != body_order
        or tuple(context.body_returns)
        != (
            body_order[1],
            body_order[3],
            body_order[4],
            body_order[2],
            body_order[5],
            body_order[0],
        )
        or len(context.proxy_returns) != 4
    ):
        raise ValueError("Original phase-cache construction/assignment incomplete")
    extra = tuple(vars(phase))[len(previous.FIELDS) + 1 :]
    if extra:
        dyna = getattr(context, "dyna_transition", None)
        if (
            dyna is None
            or _FORWARDED.get(context.owner) is not dyna
            or (
                dyna.phase is not phase
                or not dyna.constructor_completed
                or phase.dyna is not dyna.handler
                or extra not in (("dyna",), ("dyna", "export_dirname"))
            )
        ):
            raise ValueError("Unowned phase extension after cache construction")
        if len(extra) == 2:
            previous._tail_route(context.parent)
    top, vector = phase.cache, made["SimPhaseCacheVectorCells"]
    if tuple(vars(top)) != ("upscaled", "vector", "vector_field") or (
        top.upscaled is not made["SimPhaseCacheUpscaled"]
        or top.vector is not vector
        or top.vector_field is not made["SimPhaseCacheVectorFieldCells"]
        or vector.layer is not made["SimPhaseCacheLayerCellsVector"]
    ):
        raise ValueError("Native ordered subcache aliases changed")
    for role, obj in context.objects:
        if type(obj) is not context.runtime_types[role]:
            raise ValueError("Actual cache runtime class changed")
        if role == "SimPhaseCaches":
            continue
        if tuple(vars(obj)) != (("_phase", "layer") if obj is vector else ("_phase",)):
            raise ValueError("Unexpected cache/lazy fields appeared")
        proxy = obj._phase
        if type(proxy) not in context.pyref.WeakRefProxyTypes or not any(
            proxy is candidate for candidate in weakref.getweakrefs(phase)
        ):
            raise ValueError("Subcache no longer holds a real weak proxy to this phase")
    if vector.layer._phase is not vector._phase:
        raise ValueError("Existing vector proxy was not preserved by layer construction")


def _associations(context):
    if tuple(vars(context.phase)) != (*previous.FIELDS, "cache"):
        raise ValueError("Default cache phase fields changed")
    _cache_relationships(context)


def _old_snapshot(context):
    projection = SimpleNamespace(
        objects=[
            ("parameters", context.parent.p),
            ("callback", context.parent.callback),
            *(("inherited", value) for value in context.parent.parents[0].graph[0]),
            *context.parent.objects,
        ]
    )
    return core.caches.snapshot(
        [
            dict(
                role=role,
                fields=literal._project(
                    projection,
                    {
                        key: value
                        for key, value in vars(obj).items()
                        if obj is not context.phase or key != "cache"
                    },
                ),
            )
            for role, obj in context.parent.objects
        ]
    )


def _snapshot(context):
    references = [
        ("parameters", context.parent.p),
        ("callback", context.parent.callback),
        *(("inherited", value) for value in context.parent.parents[0].graph[0]),
        *context.parent.objects,
        *context.objects,
        *(("weak_phase_proxy", proxy) for _, proxy in context.proxy_returns),
    ]
    projection = SimpleNamespace(objects=references)
    return core.caches.snapshot(
        dict(
            parent=context.parent_trial.identity,
            phase=literal._project(projection, vars(context.phase)),
            objects=[
                dict(role=role, fields=literal._project(projection, vars(obj)))
                for role, obj in context.objects
            ],
            imports=context.import_order,
            attempts=context.factory_attempts,
            returns=context.factory_returns,
            weak_proxies=[
                literal._project(projection, (value, result))
                for value, result in context.proxy_returns
            ],
        )
    )


def _old_graph(context):
    for fields, (_, obj) in zip(context.old_fields, context.parent.objects, strict=True):
        fields.clear()
        fields.update(
            {
                key: value
                for key, value in vars(obj).items()
                if obj is not context.phase or key != "cache"
            }
        )
    return literal.callers._graph(context.old_view, context.old_view, context.parent.tape)


def _graph(context):
    context.graph_fields.clear()
    context.graph_fields.extend(vars(obj) for _, obj in context.objects)
    vars(context.graph_view).clear()
    vars(context.graph_view).update(
        phase=context.phase,
        phase_fields=vars(context.phase),
        objects=context.objects,
        fields=context.graph_fields,
        proxies=context.proxy_returns,
    )
    return literal.callers._graph(context.graph_view, context.graph_view, context.tape)


@contextmanager
def _account(context):
    scope = dict(
        vars(previous.inherited), _NATIVE=_METHODS, _acquire=_acquire, _namespace=_namespace
    )
    observer = contextmanager(FunctionType(previous.inherited._account.__wrapped__.__code__, scope))
    with observer(context):
        yield


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        cache=trial.cache.identity,
        events=trial.events,
        work=trial.work,
        factory_attempts=trial.factory_attempts,
        factory_returns=trial.factory_returns,
        body_attempts=trial.body_attempts,
        body_returns=trial.body_returns,
        proxy_attempts=trial.proxy_attempts,
        proxy_returns=trial.proxy_returns,
        completed=trial.completed,
        failure_stage=trial.failure_stage,
        complete_phase_or_native_or_physical_or_checkpoint_admitted=False,
    )


class PhaseCachesOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the live issued phase-cache continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No phase-cache hydration or checkpoint admission")

    @property
    def partial_phase(self):
        return _validate(self).phase

    @property
    def cache_namespace(self):
        return _validate(self).phase.cache

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not PhaseCachesOwner or owner not in _ISSUED:
        raise CacheConstructionRejected("Actual issued cache owner required", stage="owner")
    context = _ISSUED[owner]
    if owner in _FORWARDED or hasattr(context, "dyna_transition"):
        raise CacheConstructionRejected(
            "Cache epoch consumed by dyna continuation",
            stage="forwarded",
            request=context.request,
            trial=context.trial,
            partial=context,
        )
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active/replaced cache owner")
        _validate_completed(context)
    except BaseException as error:
        context.invalid = True
        raise CacheConstructionRejected(
            "Stale cache constructor owner",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def _validate_completed(context):
    _check(context)
    _associations(context)
    if _snapshot(context).identity != context.trial.cache.identity or (
        previous.previous._digest(trial_record(context.trial)) != context.trial.identity
    ):
        raise ValueError("Cache constructor trial changed")
    graph = _graph(context)
    literal._same(graph[0], context.graph[0])
    if graph[1] != context.graph[1]:
        raise ValueError("Cache reference edges changed")


def _claim_for_dyna(owner, *, expected, transition):
    with _LOCK:
        context = _ISSUED.get(owner) if type(owner) is PhaseCachesOwner else None
        if context is None or context is not expected or context.active or context.invalid:
            raise CacheConstructionRejected(
                "Actual closed cache owner required", stage="cache_owner"
            )
        if owner in _FORWARDED or hasattr(context, "dyna_transition"):
            raise CacheConstructionRejected("Cache dyna attempt consumed", stage="forwarded")
        module = sys.modules.get("cells.processes.betse_native_phase_dyna")
        if (
            module is None
            or type(transition.request) is not module.Request
            or (
                module._CONSUMED.get(transition.request) is not transition
                or module._REQUESTS.get(transition.request) is not transition.refs
                or transition.parent is not context
                or transition.request.cache_owner is not owner
                or transition.thread != get_ident()
            )
        ):
            raise CacheConstructionRejected(
                "Actual issued dyna attempt required", stage="dyna_owner"
            )
        context.dyna_transition = transition
        _FORWARDED[owner] = transition
        # Still pre-dyna/pre-SEED-mutation authentication. Failure keeps both
        # irreversible markers rather than reopening the old owner.
        _validate_completed(context)
        if transition.invalid:
            raise CacheConstructionRejected(
                "Dyna attempt poisoned during authentication", stage="dyna_owner"
            )
        return context


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise CacheConstructionRejected(
            "Native cache construction remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise CacheConstructionRejected(
                "Reentrant cache continuation", stage="reentrant", request=request
            )
        if type(request) is not Request or request not in _REQUESTS:
            raise CacheConstructionRejected(
                "Issued phase-cache request required", stage="request", request=request
            )
        if request in _CONSUMED:
            raise CacheConstructionRejected(
                "Cache continuation attempt consumed", stage="consumed", request=request
            )
        claim = getattr(previous, "_claim_for_caches", None)
        if not callable(claim):
            raise CacheConstructionRejected(
                "Reviewed phase-prefix retirement hook is not available",
                stage="phase_hook",
                request=request,
            )
        parent = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            parent=parent,
            parent_trial=parent.trial,
            phase=parent.phase,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="parent_preflight",
            objects=[],
            object_issuance=[],
            constructed={},
            runtime_types={},
            runtime_bindings={},
            methods={},
            factory_attempts=[],
            factory_returns=[],
            body_attempts=[],
            body_returns=[],
            proxy_attempts=[],
            proxy_returns=[],
            import_order=[],
            events=[],
            work=[],
            locals={},
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            graph_view=SimpleNamespace(),
            graph_fields=[],
            completed=False,
            old_fields=[{} for _ in parent.objects],
        )
        context.old_view = SimpleNamespace(
            objects=parent.objects,
            fields=context.old_fields,
            parameters=parent.p,
            callback=parent.callback,
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        primary = None
        try:
            if previous._validate(request.phase_owner) is not parent:
                raise ValueError("Original phase-prefix association changed")
            context.before = _old_snapshot(context)
            context.old_graph = _old_graph(context)
            context.bindings = _bindings()
            context.stage = "phase_retirement"
            if claim(request.phase_owner, expected=parent, transition=context) is not parent:
                raise ValueError("Original phase-prefix retirement returned a foreign parent")
            _check(context)
            with _account(context):
                context.stage = "cache_class_acquisition"
                _acquire(context)
                context.native_bindings = _native_bindings(context)
                _namespace(context)
                context.stage = "phase_cache_constructor_assignment"
                context.methods["attach"](context.phase)
                previous.inherited._stop(context)
                _check(context)
                _associations(context)
                context.completed = True
        except BaseException as error:
            if not isinstance(error, literal._CaptureStop) or context.observation_error is None:
                primary = error
        finally:
            context.active = False
            _ACTIVE.pop()
        partial = dict(
            context=context,
            parent=parent,
            parent_trial=context.parent_trial,
            phase=context.phase,
            objects=context.objects,
            proxies=context.proxy_returns,
            attempts=context.factory_attempts,
            returns=context.factory_returns,
            body_attempts=context.body_attempts,
            body_returns=context.body_returns,
            imports=context.import_order,
            raw_locals=context.locals,
            events=context.events,
            work=context.work,
            last_completed=getattr(context, "last_completed", None),
            usable_child_available=False,
        )
        capture = context.observation_error
        trial = None
        try:
            if hasattr(context, "before"):
                value = Trial(
                    request.identity,
                    parent.trial.identity,
                    context.before,
                    _snapshot(context),
                    tuple(name for name, _ in context.events),
                    tuple(context.work),
                    tuple(context.factory_attempts),
                    tuple(context.factory_returns),
                    tuple(context.body_attempts),
                    tuple(context.body_returns),
                    len(context.proxy_attempts),
                    len(context.proxy_returns),
                    context.completed and primary is None and capture is None,
                    None if primary is None and capture is None else context.stage,
                    "",
                )
                trial = replace(value, identity=previous.previous._digest(trial_record(value)))
                context.trial = trial
        except BaseException as error:
            raise CacheConstructionRejected(
                "Cache trial sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None or capture is not None or trial is None:
            raise CacheConstructionRejected(
                "Original cache constructor attempt refused",
                stage=context.stage,
                request=request,
                trial=trial,
                partial=partial,
                source_error=primary,
                capture_error=capture,
            ) from (primary if primary is not None else capture)
        try:
            _check(context)
            _associations(context)
            context.graph = _graph(context)
            context.object_issuance = tuple(context.object_issuance)
            context.owner = object.__new__(PhaseCachesOwner)
            _ISSUED[context.owner] = context
            return context.owner
        except BaseException as error:
            context.invalid = True
            raise CacheConstructionRejected(
                "Cache child sealing failed",
                stage="capture",
                request=request,
                trial=trial,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from error


def require_phase(owner):
    context = _validate(owner)
    raise CacheConstructionRejected(
        "TissueHandler/dyna, real remaining parameters and phase initialization are unavailable",
        stage="phase_incomplete",
        request=context.request,
        trial=context.trial,
        partial=context,
    )
