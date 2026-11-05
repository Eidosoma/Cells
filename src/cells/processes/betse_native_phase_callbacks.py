"""Native default callback preparation with observed application ancestry.

This is an explicit prepared-input route for a future SimPhase. It preserves
existing native testing caches; it supplies neither phase nor INIT authority.
No application singleton, callback, or live owner is reconstructed from data.
"""

import ast
import builtins
import dis
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_simulator_construction as simulator

LAW_ID = "betse_observed_application_native_phase_callbacks@1"
SIMULATOR_SHA256 = "6f94d0cf79191c952a7055a63865080ffe1693c8798c6ee73aa24ad24c8d5884"
CALLBACKS = "betse/science/phase/phasecallbacks.py"
BASE = "betse/util/type/call/callbacks.py"
APP = "betse/util/app/meta/appmetaabc.py"
TESTING = "betse/util/test/tsttest.py"
MEMO = "betse/util/type/decorator/decmemo.py"
CACHE = "_betse_cached__function_value"
MODULES = (
    "betse.science.phase.phasecallbacks",
    "betse.util.type.call.callbacks",
    "betse.util.app.meta.appmetaone",
    "betse.appmeta",
    "betse.util.test.tsttest",
    "betse.util.type.decorator.decmemo",
    "betse.util.io.log.logs",
)
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []


class CallbackRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        request=None,
        partial=None,
        trial=None,
        source_error=None,
        capture_errors=(),
    ):
        super().__init__(reason)
        self.stage, self.request, self.partial, self.trial = stage, request, partial, trial
        self.source_error, self.capture_errors = source_error, tuple(capture_errors)


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    parent: simulator.SimulatorOwner
    parent_trial_identity: str
    cache_before: tuple
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live callback requests cannot be serialized")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    cache: object
    work: tuple
    observations: tuple
    factory_completed: bool
    identity: str


def source_plan():
    if hashlib.sha256(Path(simulator.__file__).read_bytes()).hexdigest() != SIMULATOR_SHA256:
        raise ValueError("Explicit reviewed Simulator producer required")
    plan = simulator.source_plan()
    return dict(
        law=LAW_ID,
        simulator_sha256=SIMULATOR_SHA256,
        native_pins=plan["native_pins"],
        application_constructor_capture=(APP, "AppMetaABC.__init__"),
        default_factory=(CALLBACKS, "make_default"),
        testing_cache=(MEMO, CACHE),
        mode=(
            "explicit prepared native callback input; not default SimPhase caller-order equivalence"
        ),
        phase_prerequisites=plan["phase_prerequisites"][1:],
        full_application_or_phase_or_INIT_or_checkpoint_authority=False,
    )


def _code_from_node(node, filename):
    node = ast.FunctionDef(
        name=node.name,
        args=node.args,
        body=node.body,
        decorator_list=[],
        returns=node.returns,
        type_comment=node.type_comment,
        type_params=node.type_params,
    )
    ast.fix_missing_locations(node)
    code = compile(ast.Module(body=[node], type_ignores=[]), filename, "exec", dont_inherit=True)
    return next(c for c in code.co_consts if type(c) is CodeType)


def _source_function(function, relative, name, cls=None):
    filename = str(simulator.tissue.aliases.NATIVE / relative)
    tree = ast.parse(Path(filename).read_bytes())
    # Imported-module lookups affect Python's call bytecode. Compile the complete
    # original scope without executing it; an isolated FunctionDef is not the
    # executable produced when Python imports this module.
    scope = compile(tree, filename, "exec", dont_inherit=True)
    if cls is not None:
        scope = next(c for c in scope.co_consts if type(c) is CodeType and c.co_name == cls)
    expected = next(c for c in scope.co_consts if type(c) is CodeType and c.co_name == name)
    original = simulator._chain(function)[-1]
    module_name = relative[:-3].replace("/", ".")
    module = sys.modules.get(module_name)
    if (
        module is None
        or original.__globals__ is not vars(module)
        or original.__code__.co_filename != filename
        or simulator._code(original.__code__) != simulator._code(expected)
    ):
        raise ValueError("Original callback dependency executable changed: " + name)
    return original


def _cache_target(function):
    chain = simulator._chain(function)
    candidates = [
        (fn, fn.__kwdefaults__["__callable_cached"])
        for fn in chain
        if type(fn.__kwdefaults__) is dict and "__callable_cached" in fn.__kwdefaults__
    ]
    if len(candidates) != 1:
        raise ValueError("Exact native func_cached wrapper required")
    wrapper, target = candidates[0]
    if not any(target is item for item in chain[1:]):
        raise ValueError("Foreign cached-function target")
    tree = ast.parse((simulator.tissue.aliases.NATIVE / MEMO).read_bytes())
    factory = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "func_cached"
    )
    assignment = next(
        n
        for n in factory.body
        if isinstance(n, ast.Assign)
        and any(isinstance(v, ast.Name) and v.id == "func_body" for v in n.targets)
    )
    template = assignment.value.func.value.value
    text = template.format(callable_var_name=CACHE)
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef))
    if simulator._code(wrapper.__code__) != simulator._code(_code_from_node(node, "<string>")):
        raise ValueError("Native func_cached executable/template changed")
    return target


def _cache(target):
    if CACHE not in vars(target):
        return (False, None)
    value = vars(target)[CACHE]
    if type(value) is not bool:
        raise ValueError("Native testing cache must contain an actual bool")
    return (True, value)


def _application(parent):
    """Use original observation identity, never a supplied singleton receipt."""
    context = simulator._validate(parent)
    tissue = context.parent
    filename = str(simulator.tissue.aliases.NATIVE / APP)
    key = (filename, "AppMetaABC.__init__")
    raw = tissue.locals.get(key)
    calls = [
        row
        for row in tissue.work
        if row.get("source_file") == filename and row.get("method") == key[1]
    ]
    if (
        tissue.trial.source_completed is not True
        or type(raw) is not dict
        or "self" not in raw
        or len(calls) != 1
        or calls[0].get("phase") != "native_factory_descriptor_setup"
    ):
        raise CallbackRejected(
            "Actual application constructor observation unavailable",
            stage="application_observation",
        )
    return context, raw["self"]


def _acquire(parent):
    context, app = _application(parent)
    simulator.tissue.aliases._check_modules()
    modules = {}
    for name in MODULES:
        module = sys.modules.get(name)
        record = simulator.tissue.aliases._MODULE_AUTH.get(name)
        if module is None or record is None or record[0][0] is not module:
            raise CallbackRejected(
                "Previously issued original callback dependency missing",
                stage="native_module_authority",
            )
        modules[name] = module
    callbacks, base, one, appmod, testing, memo, logs = (modules[n] for n in MODULES)
    if (
        type(app) is not appmod.BetseAppMeta
        or vars(one).get("_app_meta") is not app
        or vars(app).get("_is_libs_initted") is not True
    ):
        raise CallbackRejected(
            "Observed application singleton/initialization changed", stage="application_association"
        )
    if callbacks.tsttest is not testing or callbacks.logs is not logs:
        raise ValueError("Original callback factory module dependencies changed")
    _source_function(callbacks.make_default, CALLBACKS, "make_default")
    _source_function(testing.is_testing, TESTING, "is_testing")
    _source_function(memo.func_cached, MEMO, "func_cached")
    _source_function(base.CallbacksBC.__init__, BASE, "__init__", "CallbacksBC")
    _source_function(base.CallbacksBC._clear_progress, BASE, "_clear_progress", "CallbacksBC")
    if callbacks.SimCallbacksBC.__bases__ != (
        base.CallbacksBC,
    ) or callbacks.SimCallbacksNoop.__bases__ != (callbacks.SimCallbacksBC,):
        raise ValueError("Native callback class hierarchy changed")
    target = _cache_target(testing.is_testing)
    return SimpleNamespace(
        parent=context,
        app=app,
        modules=modules,
        callbacks=callbacks,
        base=base,
        testing=testing,
        target=target,
        cache=_cache(target),
    )


def request_record(request):
    return dict(
        law=LAW_ID,
        parent_trial=request.parent_trial_identity,
        cache_before=request.cache_before,
        source_application_observation_required=True,
        metadata_scope="observed application identity and selected current testing cache only",
        phase_or_full_application_or_INIT_authority=False,
    )


def from_simulator(parent, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise CallbackRejected("Explicit native callback preparation law required", stage="law")
    source_plan()
    retained = _acquire(parent)
    request = Request(parent, retained.parent.trial.identity, retained.cache, "")
    request = replace(
        request, identity=simulator.tissue.core.records._digest(request_record(request))
    )
    _REQUESTS[request] = retained
    return request


def _parent(request, *, after=False):
    if type(request) is not Request or request not in _REQUESTS:
        raise CallbackRejected("Issued live callback request required", stage="request")
    old, actual = _REQUESTS[request], _acquire(request.parent)
    if (
        actual.parent is not old.parent
        or actual.app is not old.app
        or actual.target is not old.target
        or actual.parent.trial.identity != request.parent_trial_identity
        or simulator.tissue.core.records._digest(request_record(request)) != request.identity
        or any(actual.modules[n] is not old.modules[n] for n in MODULES)
    ):
        raise CallbackRejected(
            "Original callback/application/parameter ancestry changed",
            stage="parent_association",
            request=request,
        )
    if not after and actual.cache != request.cache_before:
        raise CallbackRejected(
            "Original current testing cache changed before factory",
            stage="cache_epoch",
            request=request,
        )
    return actual


def _runtime(retained):
    labels, objects = [], [retained.app, vars(retained.app), retained.target]
    for name, module in retained.modules.items():
        labels.append(name)
        objects.extend((module, vars(module)))
    for cls in (
        type(retained.app),
        retained.callbacks.SimCallbacksBC,
        retained.callbacks.SimCallbacksNoop,
        retained.base.CallbacksBC,
    ):
        objects.extend(simulator.tissue._surface(cls))
    for fn in (
        retained.callbacks.make_default,
        retained.testing.is_testing,
        retained.base.CallbacksBC.__init__,
        retained.base.CallbacksBC._clear_progress,
    ):
        for function in simulator._chain(fn):
            objects.extend(
                (function, function.__code__, function.__globals__, function.__builtins__)
            )
            namespace = function.__globals__.get("__builtins__")
            namespace = vars(namespace) if type(namespace) is type(builtins) else namespace
            if namespace is not function.__builtins__ or namespace is not vars(builtins):
                raise ValueError("Native callback cached builtins association changed")
            for label, value in (
                ("defaults", function.__defaults__),
                ("kwdefaults", function.__kwdefaults__),
                ("annotations", function.__annotations__),
            ):
                labels.append((label, type(value).__name__))
                objects.append(value)
                if value is not None:
                    for key, item in value.items() if type(value) is dict else enumerate(value):
                        labels.append((label, key))
                        objects.extend(simulator.tissue.aliases._atoms(item))
            for cell in function.__closure__ or ():
                objects.extend((cell, cell.cell_contents))
            for instruction in dis.get_instructions(function):
                if instruction.opname == "LOAD_GLOBAL":
                    name = instruction.argval
                    local = name in function.__globals__
                    labels.append(("global", name, local))
                    objects.append(
                        function.__globals__[name] if local else function.__builtins__[name]
                    )
    return tuple(labels), tuple(objects)


def _copy_locals(frame):
    return simulator._copy_locals(frame)


@contextmanager
def _observe(context):
    previous, trace = sys.getprofile(), sys.gettrace()

    def profile(frame, event, arg):
        selected = frame.f_code in context.roles
        if event == "call" and (
            selected
            or frame.f_code.co_filename.startswith(str(simulator.tissue.aliases.NATIVE) + "/")
        ):
            if len(context.work) >= simulator.MAX_WORK:
                raise ValueError("Callback work ledger exhausted")
            context.work.append(
                dict(
                    sequence=len(context.work),
                    source_file=frame.f_code.co_filename,
                    method=frame.f_code.co_qualname,
                    role=context.roles.get(frame.f_code, "native_descendant"),
                )
            )
        if selected and event in ("call", "return"):
            try:
                raw = _copy_locals(frame)
                context.raw_locals.append((event, frame.f_code.co_qualname, raw))
                if "self" in raw and type(raw["self"]) in context.callback_types:
                    context.partial_callback = raw["self"]
                context.observations.append(
                    dict(
                        event=event,
                        role=context.roles[frame.f_code],
                        classification="entry" if event == "call" else "return_or_unwind",
                        bool_return=arg if event == "return" and type(arg) is bool else None,
                    )
                )
            except BaseException as error:
                context.capture_errors.append(("callback_locals", error))
        if previous is not None:
            if event in {"return", "c_return", "c_exception"}:
                try:
                    previous(frame, event, arg)
                except BaseException as error:
                    # A return(None) may be a source exception unwind. Keep
                    # secondary observation failure from replacing its primary.
                    label = "inherited_profile_" + context.stage + "_" + event
                    context.capture_errors.append((label, error))
                    try:
                        context.raw_locals.append(
                            (label, frame.f_code.co_qualname, _copy_locals(frame))
                        )
                    except BaseException as capture:
                        context.capture_errors.append((label + "_locals", capture))
            else:
                # Entry guards continue to reject before source execution.
                previous(frame, event, arg)

    sys.setprofile(profile)
    try:
        yield
    finally:
        sys.setprofile(previous)
        sys.settrace(trace)


def _snapshot(context):
    return simulator.tissue.core.caches.snapshot(
        dict(
            parent_trial=context.request.parent_trial_identity,
            cache_before=context.request.cache_before,
            cache_after=context.after.cache,
            callback_fields=vars(context.callback),
            retained_parameter_ancestry=True,
            retained_application_constructor=True,
            source_application_projection_only=True,
        )
    )


def _graph(context):
    return simulator.tissue.callers._graph(context.view, context.source.parent.p, context.tape)


def trial_record(trial):
    return dict(
        law=LAW_ID,
        request=trial.request_identity,
        cache=trial.cache.identity,
        work=trial.work,
        observations=trial.observations,
        factory_completed=trial.factory_completed,
        no_phase_or_INIT_authority=True,
    )


class CallbackOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use source-backed callback preparation")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live callback owners cannot be serialized")

    @property
    def callback(self):
        return _validate(self).callback

    @property
    def trial(self):
        return _validate(self).trial


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.parent) is not context
    ):
        raise ValueError("Original callback occurrence changed or failed")
    simulator._same(_bindings(), context.bindings)
    actual = _parent(context.request, after=True)
    simulator._same(_runtime(actual), context.runtime)
    if actual.cache != context.after.cache:
        raise ValueError("Post-factory testing cache changed")
    expected = (
        actual.callbacks.SimCallbacksBC if actual.cache[1] else actual.callbacks.SimCallbacksNoop
    )
    if (
        actual.cache[0] is not True
        or type(context.callback) is not expected
        or context.partial_callback is not context.callback
        or vars(context.callback)
        != dict(_progress_min=None, _progress_max=None, _progress_next=None)
    ):
        raise ValueError("Actual callback branch/allocated instance/progress stores changed")
    if source_plan() != context.plan:
        raise ValueError("Callback source producer changed")


def _validate(owner):
    if type(owner) is not CallbackOwner or owner not in _ISSUED:
        raise CallbackRejected("Issued actual callback owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active or replaced callback owner")
        _check(context)
        if context.trial.cache.identity != _snapshot(
            context
        ).identity or context.trial.identity != simulator.tissue.core.records._digest(
            trial_record(context.trial)
        ):
            raise ValueError("Callback trial/current stores changed")
        simulator._same_graph(_graph(context), context.graph)
    except BaseException as error:
        context.invalid = True
        raise CallbackRejected(
            "Stale callback owner refused",
            stage="owner_drift",
            request=context.request,
            partial=context,
            trial=context.trial,
            source_error=error,
        ) from error
    return context


def _bindings():
    functions = (
        source_plan,
        _code_from_node,
        _source_function,
        _cache_target,
        _cache,
        _application,
        _acquire,
        request_record,
        from_simulator,
        _parent,
        _runtime,
        _copy_locals,
        _observe,
        _observe.__wrapped__,
        _snapshot,
        _graph,
        trial_record,
        _check,
        _validate,
        _bindings,
        prepare,
        require_phase,
        simulator._validate,
        simulator.tissue.aliases._check_modules,
    )
    return (
        (),
        (
            _REQUESTS,
            _CONSUMED,
            _CLAIMED,
            _ISSUED,
            _LOCK,
            _ACTIVE,
            *(atom for function in functions for atom in simulator.tissue.aliases._atoms(function)),
        ),
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(simulator.RELEASE) != "1":
        raise CallbackRejected(
            "Actual callback factory remains held", stage="release", request=request
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise CallbackRejected(
                "Reentrant callback factory refused", stage="reentrant", request=request
            )
        if type(request) is not Request or request not in _REQUESTS:
            raise CallbackRejected(
                "Issued live callback request required", stage="request", request=request
            )
        if request in _CONSUMED or request.parent in _CLAIMED:
            raise CallbackRejected(
                "Callback attempt already consumed", stage="consumed", request=request
            )
        context = SimpleNamespace(
            request=request,
            thread=get_ident(),
            active=True,
            invalid=False,
            work=[],
            observations=[],
            raw_locals=[],
            capture_errors=[],
            partial_callback=None,
            factory_completed=False,
            stage="parent",
        )
        _CONSUMED[request] = _CLAIMED[request.parent] = context
        _ACTIVE.append(context)
        error = None
        try:
            context.bindings = _bindings()
            context.source = _parent(request)
            context.plan = source_plan()
            context.runtime = _runtime(context.source)
            cb, base = context.source.callbacks, context.source.base
            context.callback_types = (cb.SimCallbacksBC, cb.SimCallbacksNoop)
            context.roles = {
                fn.__code__: role
                for role, function in (
                    ("factory", cb.make_default),
                    ("testing", context.source.testing.is_testing),
                    ("callback_init", base.CallbacksBC.__init__),
                    ("progress_stores", base.CallbacksBC._clear_progress),
                )
                for fn in simulator._chain(function)
            }
            context.stage = "native_callback_factory"
            with _observe(context):
                context.callback = cb.make_default()
            context.factory_completed = True
            context.stage = "post_factory_association"
            context.after = _parent(request, after=True)
            if request.cache_before[0] and context.after.cache != request.cache_before:
                raise ValueError("Existing native testing cache may not be reset/replaced")
            if not context.capture_errors:
                _check(context)
        except BaseException as primary:
            error = primary
        try:
            if error is None and not context.capture_errors:
                context.stage = "callback_capture"
                cache = _snapshot(context)
                trial = Trial(
                    request.identity,
                    cache,
                    tuple(context.work),
                    tuple(context.observations),
                    True,
                    "",
                )
                context.trial = replace(
                    trial, identity=simulator.tissue.core.records._digest(trial_record(trial))
                )
                context.view = SimpleNamespace(
                    parent=request.parent,
                    application=context.source.app,
                    parameters=context.source.parent.p,
                    tissue=context.source.parent.handler,
                    simulator=context.source.parent.instance,
                    callback=context.callback,
                    fields=(
                        vars(context.source.parent.p),
                        vars(context.callback),
                        vars(context.source.target),
                    ),
                )
                context.tape = SimpleNamespace(rng=None, events=context.work, draws=(), locals={})
                context.graph = _graph(context)
                _check(context)
                owner = object.__new__(CallbackOwner)
                context.owner = owner
                _ISSUED[owner] = context
                return owner
        except BaseException as capture:
            context.capture_errors.append((context.stage, capture))
        finally:
            context.active = False
            _ACTIVE.pop()
        context.invalid = True
        refusal = CallbackRejected(
            "Native callback preparation issued no owner",
            stage=context.stage,
            request=request,
            partial=context,
            source_error=error,
            capture_errors=context.capture_errors,
        )
        raise refusal from (error if error is not None else context.capture_errors[0][1])


def require_phase(owner):
    context = _validate(owner)
    raise CallbackRejected(
        "Native phase/current-parameter construction prerequisites remain open",
        stage="phase_prerequisites",
        request=context.request,
        trial=context.trial,
        partial=dict(
            missing=context.plan["phase_prerequisites"], phase_or_INIT_or_checkpoint_admitted=False
        ),
    )
