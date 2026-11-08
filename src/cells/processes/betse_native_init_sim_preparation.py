"""Held genuine retained-INIT/current-Parameters runner preparation prefix.

This issues only read-only, source-checked preparation inputs. A fresh SIM
phase is deliberately unavailable until an actual terminal forwarding contract
can authorize sim.dyna and the later material/event/setup stores. It neither
relabels the INIT phase nor reuses a supplied component lifecycle as authority.
"""

import ast
import hashlib
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from functools import wraps
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, MethodType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_molecule_wrapper_authority as imported_wrappers
from cells.processes import betse_native_init_sim_preparation_source as source
from cells.processes import betse_native_init_terminal as previous
from cells.processes import betse_native_parameter_phase_construction as timing
from cells.processes import betse_native_simulator_construction as observation

parameters, claims = timing.parameters, timing.claims
LAW_ID = "betse_retained_complete_INIT_fresh_current_parameters_SIM_runner_prefix@1"
RELEASE = "CELLS_NATIVE_INIT_SIM_PREPARATION_RELEASED"
PARENT_SHA256 = 'f95a89b39b355e9617f8ab144bbfa10d4e12f123ab85d4add1ccbc5942c2f58c'
PARAMETERS_SHA256 = '31a44e9863c44801f887afad41981868a46e6f01d4d505a44302a7532e78404e'
OBSERVER_SHA256 = '6f94d0cf79191c952a7055a63865080ffe1693c8798c6ee73aa24ad24c8d5884'
CALLBACKS_SHA256 = '63ecf075fd2b781c84156c732366def11729349124ae3652ae72506c4c467698'
WRAPPER_OBSERVER_SHA256 = '976ffccd878721ba88b7d6d92bb3eb7518bf42c07c0868cb404fa6b28d9074bf'
PARENT_REVIEW_SHA256 = 'b7efb6935e042ad8e325c1dc5da35294345af509f2dd2ef24be7dceb057a0056'
PARAMETERS_REVIEW_SHA256 = 'db0d3976f3da0f51afa1a3fef572415b5299d2680b9caa75ba21e0a512651403'
MAX_WORK = 10000
_REQUESTS, _CONSUMED, _ISSUED, _PAIRS = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_ENTRY, _DECLARATION_FAILURES = [], []
_WRAPPER_API = None
_WRAPPER_ISSUED, _WRAPPER_FAILED = WeakKeyDictionary(), []
_WRAPPER_ACTIVE, _WRAPPER_LOCK = [], RLock()
WRAPPER_IMPORT_LAW = "fresh_original_SimRunner_imported_wrapper_provenance@1"
_SELECTED = (("runner_constructor", "__init__"), ("compatibility", "_die_if_seed_differs"))


class PreparationRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    init_owner: object
    current_parameters_owner: object
    init_identity: str
    parameters_identity: str
    source_identity: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live INIT/SIM input authority cannot be serialized or supplied")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    init_identity: str
    parameters_identity: str
    work: tuple
    observations: tuple
    metadata_work: tuple
    source_completed: bool
    identity: str


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ready():
    if not all(_pin(value) for value in (PARENT_REVIEW_SHA256, PARAMETERS_REVIEW_SHA256)):
        raise PreparationRejected(
            "Reviewed genuine INIT/current-parameter producers remain held",
            stage="producer_review_held",
        )
    for module, pin in (
        (previous, PARENT_SHA256),
        (parameters, PARAMETERS_SHA256),
        (observation, OBSERVER_SHA256),
        (timing.callbacks, CALLBACKS_SHA256),
        (imported_wrappers, WRAPPER_OBSERVER_SHA256),
    ):
        path = Path(module.__file__)
        raw = path.read_bytes()
        if path.is_symlink() or hashlib.sha256(raw).hexdigest() != pin:
            raise PreparationRejected("Exact current parent producer required", stage="producer")
        definitions = tuple(n for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef))
        names = tuple(n.name for n in definitions)
        managers = tuple(
            n.name
            for n in definitions
            if any(isinstance(d, ast.Name) and d.id == "contextmanager" for d in n.decorator_list)
        )
        previous.base.previous.interfaces._source_interface(
            module, raw, path, names, contextmanagers=managers
        )


def source_plan():
    return dict(
        law=LAW_ID,
        original=source.source_plan(),
        parent_source=PARENT_SHA256,
        current_parameters=PARAMETERS_SHA256,
        reused_observer=OBSERVER_SHA256,
        callback_correspondence=CALLBACKS_SHA256,
        wrapper_observer_source=WRAPPER_OBSERVER_SHA256,
        wrapper_import_law=WRAPPER_IMPORT_LAW,
        wrapper_authority="fresh actual observed import/factory/make/code/closure provenance only",
        reviews=(PARENT_REVIEW_SHA256, PARAMETERS_REVIEW_SHA256),
        max_work=MAX_WORK,
        parent="actual successful full InitTerminalOwner; failed/short/supplied refused",
        parameters="distinct genuine fresh complete-load owner, before phase birth",
        ordinary_supplied_lifecycle_is_not_native_authority=True,
        accounting=(
            "actual ownership/history verification attempts plus separately observed native work"
        ),
        same_p_SIM_mutation_not_implemented=True,
        phase_construction_held=True,
        native_pickle_full_caller_or_scientific_admission=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID,
        init=value.init_identity,
        parameters=value.parameters_identity,
        source=value.source_identity,
    )


def _types(init_owner, current_owner):
    # No property or foreign attribute is inspected before exact issuance.
    if type(init_owner) is not previous.InitTerminalOwner or init_owner not in previous._ISSUED:
        raise PreparationRejected("Actual successful full INIT required", stage="init_owner")
    if (
        type(current_owner) is not parameters.WorldReadyParametersOwner
        or current_owner not in parameters._ISSUED
    ):
        raise PreparationRejected(
            "Actual fresh current Parameters required", stage="parameters_owner"
        )


def _entry_guard(function):
    """Exclude recursive admission before metadata hooks or source can run."""

    @wraps(function)
    def guarded(*args, **kwargs):
        with _LOCK:
            if _ENTRY:
                _ENTRY[-1].invalid = True
                if _ACTIVE:
                    _ACTIVE[-1].invalid = True
                raise PreparationRejected("Reentrant preparation entry", stage="reentrant")
            entry = SimpleNamespace(invalid=False, function=function)
            _ENTRY.append(entry)
            primary = result = None
            try:
                result = function(*args, **kwargs)
                if entry.invalid:
                    if type(result) is SimPreparationOwner and result in _ISSUED:
                        _ISSUED[result].invalid = True
                    raise PreparationRejected("Preparation entry was poisoned", stage="reentrant")
                return result
            except BaseException as error:
                primary = error
                raise
            finally:
                if _ENTRY and _ENTRY[-1] is entry:
                    _ENTRY.pop()
                elif primary is None:
                    raise PreparationRejected("Original entry exclusion changed", stage="closure")

    return guarded


def _metadata_call(work, label, function, *args):
    row = dict(sequence=len(work), call=label, status="entered")
    work.append(row)
    try:
        result = function(*args)
    except BaseException:
        row["status"] = "failed"
        raise
    row["status"] = "returned"
    return result


def _inputs(init_owner, current_owner, work):
    _types(init_owner, current_owner)
    parent = _metadata_call(
        work, "actual_full_INIT_ownership_verification", previous._authority, init_owner
    )
    current = _metadata_call(
        work, "actual_fresh_parameter_ownership_verification", parameters._validate, current_owner
    )
    if (
        parent.trial.source_completed is not True
        or parent.trial.selected_stop is not False
        or parent.trial.loop_returned is not True
        or parent.trial.context_returned is not True
    ):
        raise PreparationRejected("Full natural INIT completion required", stage="init_completion")
    if (
        current.p is parent.p
        or "_run_sim" in vars(current.p)
        or current_owner in parameters._CONSTRUCTED
    ):
        raise PreparationRejected(
            "Fresh distinct current p before SIM phase birth required", stage="current_parameters"
        )
    return parent, current


@_entry_guard
def from_init(init_owner, *, current_parameters_owner, law_id):
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise PreparationRejected("Reentrant SIM preparation declaration", stage="reentrant")
        if type(law_id) is not str or law_id != LAW_ID:
            raise PreparationRejected("Exact retained INIT/SIM source law required", stage="law")
        _ready()
        work = []
        try:
            parent, current = _inputs(init_owner, current_parameters_owner, work)
        except BaseException as error:
            _DECLARATION_FAILURES.append((init_owner, current_parameters_owner, tuple(work), error))
            raise
        if current_parameters_owner in _PAIRS.get(init_owner, ()):
            raise PreparationRejected(
                "This live input pair was already attempted", stage="consumed"
            )
        value = Request(
            init_owner,
            current_parameters_owner,
            parent.trial.identity,
            current.record.identity,
            _digest(source_plan()),
            "",
        )
        value = replace(value, identity=_digest(request_record(value)))
        _REQUESTS[value] = (parent, parent.trial, current, current.record, tuple(work))
        return value


def _runner_import_code(cls, method):
    role = next((role for role, name in _SELECTED if cls == "SimRunner" and method == name), None)
    if role is None:
        raise ValueError("Unknown original SimRunner import target")
    return source.code(role)


def _wrapper_api():
    """Scoped reuse of the existing observer; never patch its global targets.

    The unchanged observer watches the caller's actual fresh native import.
    It neither generates nor decorates a replacement function. The private
    registry records actual factory returns, so a copied/extra wrapper cannot
    become authoritative by being the first object inspected.
    """
    global _WRAPPER_API
    if _WRAPPER_API is None:
        path = Path(imported_wrappers.__file__)
        raw = path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != WRAPPER_OBSERVER_SHA256:
            raise PreparationRejected("Pinned wrapper observer required", stage="wrapper_producer")
        names = tuple(n.name for n in ast.parse(raw).body if isinstance(n, ast.FunctionDef))
        previous.base.previous.interfaces._source_interface(
            imported_wrappers, raw, path, names, contextmanagers=("observing_native_imports",)
        )
        targets = {("SimRunner", name): source.RUNNER for _, name in _SELECTED}
        namespace = dict(
            vars(imported_wrappers),
            network=SimpleNamespace(
                NATIVE=source.NATIVE,
                SITES=targets,
                PINS={source.RUNNER: source.PINS[source.RUNNER]},
                code=_runner_import_code,
            ),
            channels=SimpleNamespace(SITES={}, PINS={}),
            LAW=WRAPPER_IMPORT_LAW,
            RELEASE=RELEASE,
            _ISSUED=_WRAPPER_ISSUED,
            _FAILED=_WRAPPER_FAILED,
            _ACTIVE=_WRAPPER_ACTIVE,
            _LOCK=_WRAPPER_LOCK,
            MAX_FACTORIES=2,
        )
        originals = []
        for name, fn in vars(imported_wrappers).items():
            if type(fn) is FunctionType and fn.__globals__ is vars(imported_wrappers):
                copied = FunctionType(
                    fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__
                )
                copied.__kwdefaults__ = fn.__kwdefaults__
                namespace[name] = copied
                originals.append((name, copied, fn))
        body = imported_wrappers.observing_native_imports.__wrapped__
        watched = FunctionType(
            body.__code__, namespace, body.__name__, body.__defaults__, body.__closure__
        )
        watched.__kwdefaults__ = body.__kwdefaults__
        namespace["observing_native_imports"] = contextmanager(watched)
        _WRAPPER_API = SimpleNamespace(
            namespace=namespace,
            functions=tuple(originals),
            watched=watched,
            watched_original=body,
            entries=tuple(namespace.items()),
        )
    api = _WRAPPER_API
    if (
        api.namespace["_ACTIVE"] is not _WRAPPER_ACTIVE
        or api.namespace["_LOCK"] is not _WRAPPER_LOCK
        or api.namespace["_ISSUED"] is not _WRAPPER_ISSUED
        or api.namespace["_FAILED"] is not _WRAPPER_FAILED
        or _WRAPPER_ACTIVE is imported_wrappers._ACTIVE
        or _WRAPPER_LOCK is imported_wrappers._LOCK
        or _WRAPPER_ISSUED is imported_wrappers._ISSUED
        or _WRAPPER_FAILED is imported_wrappers._FAILED
    ):
        raise ValueError("Independent runner import observation state required")
    if tuple(api.namespace) != tuple(key for key, _ in api.entries) or any(
        api.namespace[key] is not value for key, value in api.entries
    ):
        raise ValueError("Original private wrapper observer namespace changed")
    net, channel = api.namespace["network"], api.namespace["channels"]
    if (
        type(net) is not SimpleNamespace
        or type(channel) is not SimpleNamespace
        or tuple(vars(net)) != ("NATIVE", "SITES", "PINS", "code")
        or tuple(vars(channel)) != ("SITES", "PINS")
        or net.NATIVE is not source.NATIVE
        or net.code is not _runner_import_code
        or net.SITES != {("SimRunner", name): source.RUNNER for _, name in _SELECTED}
        or net.PINS != {source.RUNNER: source.PINS[source.RUNNER]}
        or channel.SITES != {}
        or channel.PINS != {}
    ):
        raise ValueError("Original private wrapper observer targets changed")
    for name, copied, original in api.functions:
        if (
            vars(imported_wrappers).get(name) is not original
            or copied.__code__ is not original.__code__
            or copied.__globals__ is not api.namespace
            or copied.__defaults__ is not original.__defaults__
            or copied.__kwdefaults__ is not original.__kwdefaults__
            or copied.__closure__ is not original.__closure__
            or copied.__builtins__ is not original.__builtins__
        ):
            raise ValueError("Original scoped observer function changed")
    if (
        api.watched.__code__ is not api.watched_original.__code__
        or api.watched.__globals__ is not api.namespace
        or api.watched.__defaults__ is not api.watched_original.__defaults__
        or api.watched.__kwdefaults__ is not api.watched_original.__kwdefaults__
        or api.watched.__closure__ is not api.watched_original.__closure__
        or api.watched.__builtins__ is not api.watched_original.__builtins__
        or imported_wrappers.observing_native_imports.__wrapped__ is not api.watched_original
    ):
        raise ValueError("Original import observer construction changed")
    return api.namespace


@contextmanager
def observing_runner_import(*, enabled=False):
    """Observe the existing fresh import; do not import or construct a runner."""
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise PreparationRejected("Original runner import remains held", stage="release")
    _ready()
    api = _wrapper_api()
    with api["observing_native_imports"](enabled=True) as context:
        yield context


def _class_dispatch(cls):
    if type(cls) is not type or cls.__bases__ != (object,) or cls.__mro__ != (cls, object):
        raise ValueError("Exact original SimRunner metaclass/bases required")
    fields = vars(cls)
    forbidden = (
        "__new__",
        "__getattribute__",
        "__getattr__",
        "__setattr__",
        "__delattr__",
        "__slots__",
        "_callbacks",
        "_p",
    )
    if any(name in fields for name in forbidden):
        raise ValueError("Original runner read/assignment/descriptor dispatch changed")
    return tuple((name, fields.get(name)) for _, name in _SELECTED)


def _native():
    # No imports/factories here: only an explicitly prepared original runtime.
    source.nodes()
    module = sys.modules.get("betse.science.simrunner")
    module_file = vars(module).get("__file__") if type(module) is ModuleType else None
    if (
        type(module) is not ModuleType
        or type(module_file) is not str
        or Path(module_file).resolve() != source.NATIVE / source.RUNNER
    ):
        raise PreparationRejected("Original SimRunner runtime not loaded", stage="runtime_held")
    cls = vars(module).get("SimRunner")
    _class_dispatch(cls)
    if vars(cls).get("__module__") != vars(module).get("__name__"):
        raise PreparationRejected("Actual native SimRunner class required", stage="runtime")
    methods, outer, members = {}, {}, []
    authority = _wrapper_api()
    for role, name in _SELECTED:
        function = vars(cls)[name]
        body = timing.callbacks._source_function(function, source.RUNNER, name, "SimRunner")
        if observation._code(body.__code__) != observation._code(source.code(role)):
            raise ValueError("Original runner executable body changed")
        if authority["validate"](function, body, owner=cls, attribute=name) is not body:
            raise ValueError("Original observed imported wrapper required")
        methods[role] = body
        outer[role] = function
        for fn in observation._chain(function):
            if fn.__builtins__ is not body.__builtins__:
                raise ValueError("Original cached builtins changed")
            members.extend(previous.base.previous._parent_atoms(fn))
    return SimpleNamespace(
        module=module,
        cls=cls,
        methods=methods,
        outer=outer,
        bindings=tuple(members),
        selected_slots=_class_dispatch(cls),
    )


def _selected_dispatch(native, role):
    slots = _class_dispatch(native.cls)
    if any(
        a[0] != b[0] or a[1] is not b[1] for a, b in zip(slots, native.selected_slots, strict=True)
    ):
        raise ValueError("Original selected runner slot changed before delegation")
    name = dict(_SELECTED)[role]
    function, body = native.outer[role], native.methods[role]
    if vars(native.cls).get(name) is not function:
        raise ValueError("Actual original selected runner callable required")
    if _wrapper_api()["validate"](function, body, owner=native.cls, attribute=name) is not body:
        raise ValueError("Original wrapper/delegate association changed")
    return function


def _invoke_selected(context, role, receiver=None):
    """Check the actual selected call after inherited hooks and before stores.

    Initial wrapper authority comes from the observed import, never this
    guard. Per-opcode checks also cover an inherited line hook changing a
    class descriptor between call entry and the original STORE_ATTR.
    """
    native = context.native
    if role not in dict(_SELECTED):
        raise ValueError("Exact selected runner operation required")
    if role == "compatibility" and receiver is not context.instance:
        raise ValueError("Original constructed runner receiver required")
    function = _selected_dispatch(native, role)
    body = native.methods[role]
    functions = {fn.__code__: fn for fn in observation._chain(function)}
    if len(functions) != len(observation._chain(function)):
        raise ValueError("Unique original wrapper/delegate code required")
    expected_receiver = receiver
    hooks = sys.getprofile(), sys.gettrace()
    traces, local_flags, primary, first_error = {}, {}, None, None
    active = True
    capture_start = len(context.capture_errors)
    observer_failure = None

    def check(frame=None, event=None):
        nonlocal expected_receiver, first_error
        try:
            if first_error is not None:
                raise first_error
            if sys.getprofile() is not profile or sys.gettrace() is not trace:
                raise ValueError("Selected runner guard hooks changed")
            if _selected_dispatch(native, role) is not function:
                raise ValueError("Original selected callable changed")
            if frame is None or frame.f_code not in functions:
                return
            if observer_failure is not None and (
                event == "call" or (event == "line" and functions[frame.f_code] is body)
            ):
                raise PreparationRejected(
                    "Selected source observation is incomplete", stage="capture", partial=context
                ) from observer_failure
            actual = functions[frame.f_code]
            if frame.f_globals is not actual.__globals__ or frame.f_code is not actual.__code__:
                raise ValueError("Actual selected wrapper/delegate frame changed")
            raw = frame.f_locals
            if actual is body:
                candidate = raw.get("self")
            else:
                args = raw.get("args")
                if type(args) is not tuple or not args:
                    raise ValueError("Original wrapper positional receiver required")
                candidate = args[0]
                defaults = actual.__kwdefaults__ or {}
                if any(raw.get(key) is not value for key, value in defaults.items()):
                    raise ValueError("Actual wrapper delegate/default argument changed")
            if type(candidate) is not native.cls:
                raise ValueError("Actual original runner receiver required")
            if expected_receiver is None:
                expected_receiver = candidate
            if candidate is not expected_receiver:
                raise ValueError("Selected wrapper/delegate receiver changed")
            if actual is body and event == "call":
                expected = (
                    (("p", context.current.p), ("callbacks", context.parent.phase.callbacks))
                    if role == "runner_constructor"
                    else (("p_old", context.parent.p), ("p_new", context.current.p))
                )
                if any(raw.get(key) is not value for key, value in expected):
                    raise ValueError(
                        "Actual selected original parameter/callback arguments changed"
                    )
        except BaseException as error:
            if first_error is None:
                first_error = error
                context.capture_errors.append(("runner_dispatch", error))
            raise

    def profile(frame, event, arg):
        nonlocal observer_failure
        # The reused observation profile already defers return-hook errors
        # and preserves the exact source exception/cause on unwind.
        if hooks[0] is not None:
            if event in ("return", "c_return", "c_exception"):
                try:
                    hooks[0](frame, event, arg)
                except BaseException as error:
                    observer_failure = error if observer_failure is None else observer_failure
                    context.capture_errors.append(("runner_inherited_return", error))
                    context.raw_locals.append(("runner_inherited_return", frame, arg))
            else:
                hooks[0](frame, event, arg)
        if not active:
            return
        if event == "call":
            # After a rejection, unrelated exception/contextmanager cleanup
            # must still enter. Re-raising on __exit__ would prevent the
            # generator's finally from restoring either hook.
            if first_error is None or frame.f_code in functions:
                check(frame, event)
        elif event in ("return", "c_return", "c_exception"):
            try:
                check()
            except BaseException:
                # No exception raised from return(None) may replace a
                # source unwind. The next entry/opcode/boundary refuses.
                pass

    def trace(frame, event, arg):
        nonlocal observer_failure
        prior = hooks[1] if event == "call" else traces.get(id(frame))
        result = None
        if prior is not None:
            if event in ("exception", "return"):
                context.raw_locals.append(("runner_inherited_trace_" + event, frame, arg))
                try:
                    result = prior(frame, event, arg)
                except BaseException as error:
                    # Retain the direct witness before any interpretation.
                    # A return(None) can be the original exception unwind.
                    observer_failure = error if observer_failure is None else observer_failure
                    context.capture_errors.append(("runner_inherited_trace_" + event, error))
            else:
                result = prior(frame, event, arg)
            if result is not None:
                traces[id(frame)] = result
        if not active:
            return result
        if event == "return":
            traces.pop(id(frame), None)
            return trace
        if first_error is not None and (event == "exception" or frame.f_code not in functions):
            return trace if id(frame) in traces else None
        check(frame, event)
        if frame.f_code in functions:
            local_flags.setdefault(id(frame), (frame, frame.f_trace_opcodes, frame.f_trace_lines))
            frame.f_trace_opcodes = True
            return trace
        # Continue inherited local tracing, without enabling per-opcode
        # instrumentation for unrelated native/library/helper bodies.
        return trace if id(frame) in traces else None

    try:
        sys.settrace(trace)
        sys.setprofile(profile)
        check()
        try:
            if role == "runner_constructor":
                result = native.cls(p=context.current.p, callbacks=context.parent.phase.callbacks)
                context.raw_runner = result
            else:
                method = getattr(receiver, dict(_SELECTED)[role])
                if (
                    type(method) is not MethodType
                    or method.__self__ is not receiver
                    or method.__func__ is not function
                ):
                    raise ValueError("Actual selected bound runner method changed")
                result = method(context.parent.p, context.current.p)
                context.raw_compatibility = result
        except BaseException as error:
            # This frame owns the native call AND its finally. No fallible
            # __exit__ entry can run before its direct primary is retained.
            context.source_error = error
            raise
        check()
        if len(context.capture_errors) != capture_start:
            raise PreparationRejected(
                "Incomplete selected runner capture", stage="capture", partial=context
            )
        return result
    except BaseException as error:
        primary = error
        raise
    finally:
        active = False
        # Restore both independently even if an inherited callback rejects
        # one recovery. Never replace a previously retained primary error.
        errors = []
        for frame, opcodes, lines in local_flags.values():
            try:
                frame.f_trace_opcodes, frame.f_trace_lines = opcodes, lines
            except BaseException as error:
                errors.append(("runner_local_trace_recovery", error))
        for getter, setter, original in (
            (sys.getprofile, sys.setprofile, hooks[0]),
            (sys.gettrace, sys.settrace, hooks[1]),
        ):
            try:
                setter(original)
            except BaseException as error:
                errors.append(("runner_hook_recovery", error))
            try:
                if getter() is not original:
                    errors.append(
                        ("runner_hook_identity", ValueError("Original runner guard not restored"))
                    )
            except BaseException as error:
                errors.append(("runner_hook_sample", error))
        context.capture_errors.extend(errors)
        if primary is None and errors:
            raise errors[0][1]


def _same_graph(actual, retained):
    timing.prefix.parameters.inherited._same_graph(actual, retained)


def _proof(context, *, public=True):
    _ready()
    if (
        context.thread != get_ident()
        or context.invalid
        or _CONSUMED.get(context.request) is not context
        or context.request.current_parameters_owner
        not in _PAIRS.get(context.request.init_owner, ())
        or _REQUESTS.get(context.request) is not context.refs
        or context.request.identity != _digest(request_record(context.request))
        or context.request.source_identity != _digest(source_plan())
    ):
        raise ValueError("Original preparation epoch/inputs/source changed")
    if public:
        parent, current = _inputs(
            context.request.init_owner,
            context.request.current_parameters_owner,
            context.metadata_work,
        )
        if parent is not context.parent or current is not context.current:
            raise ValueError("Original issued input identities changed")
    else:
        if (
            _metadata_call(
                context.metadata_work,
                "actual_current_parameter_history_verification",
                parameters.validate_completed_history,
                context.current.owner,
            )
            is not context.current.record
        ):
            raise ValueError("Original current parameter history changed")
    if context.parent.trial is not context.refs[1] or context.current.record is not context.refs[3]:
        raise ValueError("Original input trials changed")
    scope = context.parent.runtime
    if scope["_snapshot"](context.parent).identity != context.parent.trial.after.identity:
        raise ValueError("INIT material/state values changed during runner preparation")
    graph = scope["_graph"](context.parent)
    previous.base._same(graph[0], context.parent.after_graph[0])
    if graph[1] != context.parent.after_graph[1]:
        raise ValueError("INIT material/state alias/layout graph changed")
    _same_graph(parameters._capture(context.current), context.current.after_graph)
    parameters.previous._same_cm(parameters._colormaps(context.current), context.current.after_cm)


@contextmanager
def _reading_current(context):
    """Reuse the complete-load owner's shared read-only/exclusion machinery."""
    guard = SimpleNamespace(
        thread=get_ident(),
        active=True,
        invalid=False,
        audit_ready=False,
        directory_depth=0,
        directory_calls=0,
        directory_targets=(),
        filesystem=[],
    )
    audit = SimpleNamespace(invalid=False, guard=guard)
    rows, registered, primary = parameters._stacks(audit), False, None
    paths = parameters.previous.previous.mod.subconfigs.paths
    try:
        with claims._registry(context.current.loaded.owner):
            if any(stack for stack, _ in rows):
                claims._busy(context.current.loaded.owner, "SIM_preparation_read_conflict")
            for stack, item in rows:
                stack.append(item)
            registered = True
            paths._install_audit(guard)
        yield
        if audit.invalid or guard.invalid:
            raise ValueError("Current parameter read-only lease poisoned")
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if registered:
                try:
                    with claims._registry(context.current.loaded.owner):
                        for stack, item in reversed(rows):
                            if not stack or stack[-1] is not item:
                                raise ValueError("Current parameter read-only exclusion changed")
                            stack.pop()
                except BaseException as capture:
                    context.capture_errors.append(("current_read_lease_closure", capture))
                    context.invalid = True
                    if primary is None:
                        raise
        finally:
            guard.active = False


def _run_prefix(context):
    before = sys.getprofile(), sys.gettrace()
    primary = None
    read_context = observer_context = None
    try:
        if observation.MAX_WORK != MAX_WORK:
            raise ValueError("Exact reused constructor observer work bound required")
        context.native = _native()
        context.constructor_codes = frozenset(fn.__code__ for fn in context.native.methods.values())
        read_context = _reading_current(context)
        with read_context:
            _proof(context, public=False)
            observer_context = observation._observe(context)
            with observer_context:
                context.stage = "original_SimRunner_constructor"
                context.instance = _invoke_selected(context, "runner_constructor")
                context.raw_runner = context.instance
                context.stage = "original_configuration_compatibility"
                context.raw_compatibility = _invoke_selected(
                    context, "compatibility", context.instance
                )
            if context.capture_errors:
                raise PreparationRejected(
                    "Incomplete original runner observation", stage="capture", partial=context
                )
            _proof(context, public=False)
        _runner_check(context)
    except BaseException as error:
        primary = context.source_error if context.source_error is not None else error
        if error is not primary:
            context.capture_errors.append(("observer_or_read_lease_closure", error))
        raise primary from primary.__cause__
    finally:
        # A profile call guard may prevent a contextmanager __exit__ from
        # entering at all. This already-entered caller owns independent final
        # recovery; neither hook depends on generator finalization or GC.
        errors = []
        for manager in (observer_context, read_context):
            if manager is None:
                continue
            # Entry refusal can leave a generator pending. Close it now,
            # with no source operation in flight, so a later collection
            # cannot restore stale hooks over the caller's current guards.
            for setter in (sys.setprofile, sys.settrace):
                for attempt in range(2):
                    try:
                        setter(None)
                        break
                    except BaseException as secondary:
                        errors.append(("outer_cleanup_hook_suspend_" + str(attempt), secondary))
            try:
                generator = vars(manager).get("gen")
                if generator is not None:
                    if primary is not None and generator.gi_frame is not None:
                        generator.throw(primary)
                    else:
                        generator.close()
            except BaseException as secondary:
                if secondary is not primary:
                    errors.append(("outer_pending_context_close", secondary))
        for getter, setter, original in (
            (sys.gettrace, sys.settrace, before[1]),
            (sys.getprofile, sys.setprofile, before[0]),
        ):
            for attempt in range(2):
                try:
                    setter(original)
                    if getter() is original:
                        break
                except BaseException as secondary:
                    errors.append(("outer_hook_recovery_" + str(attempt), secondary))
        context.capture_errors.extend(errors)
        if primary is None and errors:
            raise errors[0][1]


def _runner_check(context):
    current = _native()
    if current.module is not context.native.module or current.cls is not context.native.cls:
        raise ValueError("Original runner runtime changed")
    previous.base._same(current.bindings, context.native.bindings)
    for role, _ in _SELECTED:
        if _selected_dispatch(context.native, role) is not current.outer[role]:
            raise ValueError("Original issued runner dispatch changed")
    if (
        type(context.instance) is not current.cls
        or context.partial_instance is not context.instance
        or context.instance is not context.raw_runner
        or tuple(vars(context.instance)) != ("_callbacks", "_p")
        or context.instance._callbacks is not context.parent.phase.callbacks
        or context.instance._p is not context.current.p
        or context.raw_compatibility is not None
    ):
        raise ValueError("Original runner result/current p/callback association changed")


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        init=value.init_identity,
        parameters=value.parameters_identity,
        work=value.work,
        observations=value.observations,
        metadata_work=value.metadata_work,
        source_completed=value.source_completed,
        phase_or_SIM_execution_admitted=False,
    )


@_entry_guard
def prepare(request, *, enabled=False):
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise PreparationRejected("Reentrant SIM preparation", stage="reentrant")
        if enabled is not True or os.environ.get(RELEASE) != "1":
            raise PreparationRejected("Native INIT/SIM preparation remains held", stage="release")
        _ready()
        if type(request) is not Request or request not in _REQUESTS:
            raise PreparationRejected("Actual issued input request required", stage="request")
        if request in _CONSUMED or request.current_parameters_owner in _PAIRS.get(
            request.init_owner, ()
        ):
            raise PreparationRejected("Input pair already attempted", stage="consumed")
        refs = _REQUESTS[request]
        metadata_work = list(refs[4])
        parent, current = _inputs(
            request.init_owner, request.current_parameters_owner, metadata_work
        )
        if parent is not refs[0] or current is not refs[2]:
            raise PreparationRejected("Original live inputs changed", stage="association")
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=parent,
            current=current,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="input_proof",
            work=[],
            metadata_work=metadata_work,
            observations=[],
            raw_locals=[],
            capture_errors=[],
            partial_instance=None,
            instance=None,
            raw_runner=None,
            raw_compatibility=None,
            source_error=None,
            primary=None,
            trial=None,
        )
        _CONSUMED[request] = context
        _PAIRS.setdefault(request.init_owner, []).append(request.current_parameters_owner)
        _ACTIVE.append(context)
        try:
            _proof(context)
            _run_prefix(context)
            _proof(context)
            value = Trial(
                request.identity,
                parent.trial.identity,
                current.record.identity,
                tuple(context.work),
                tuple(context.observations),
                tuple(dict(row) for row in context.metadata_work),
                True,
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
        except BaseException as error:
            context.invalid, context.primary = True, error
            _FAILED.append(context)
            raise PreparationRejected(
                "Original INIT/SIM preparation failed", stage=context.stage, partial=context
            ) from error
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
        if context.invalid or context.capture_errors or context.trial is None:
            raise PreparationRejected(
                "Preparation closure incomplete", stage="closure", partial=context
            )
        owner = object.__new__(SimPreparationOwner)
        context.owner = owner
        _ISSUED[owner] = context
        return owner


class SimPreparationOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only successful original runner preparation issues this owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live INIT/SIM preparation cannot be serialized or hydrated")

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not SimPreparationOwner or owner not in _ISSUED:
        raise PreparationRejected("Actual issued preparation required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.invalid or context.owner is not owner:
            raise ValueError("Active or changed preparation owner")
        _proof(context)
        _runner_check(context)
        if (
            context.trial.source_completed is not True
            or context.capture_errors
            or context.trial.identity != _digest(trial_record(context.trial))
            or context.trial.work != tuple(context.work)
            or context.trial.observations != tuple(context.observations)
            or context.trial.metadata_work
            != tuple(context.metadata_work[: len(context.trial.metadata_work)])
        ):
            raise ValueError("Original preparation trial changed")
    except BaseException:
        context.invalid = True
        raise
    return context


def construct_sim(owner, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise PreparationRejected("SIM phase construction remains held", stage="release")
    _authority(owner)
    raise PreparationRejected(
        "Actual terminal-to-SIM forwarding claim is absent: fresh phase/cache/handler and "
        "retained sim.dyna mutation require their own typed owner transport before any constructor",
        stage="SIM_parent_forwarding_prerequisite",
    )
