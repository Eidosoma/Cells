"""Selected first ordinary INIT iteration on a genuine ElectricalOwner.

The original calendar is neither replaced nor shortened. A guarded stop at
the loop's second FOR_ITER completes one selected iteration before advancing
its iterator again. That stop is recovered inside dispatch, with both outer
observers restored before the original caller/context continues. This grants
no complete-loop, serialization, numerical or physical authority.
"""

import ast
import copy
import dis
import hashlib
import logging
import logging.handlers
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_electrical as previous
from cells.processes import betse_native_init_first_step_source as source

LAW_ID = "betse_actual_INIT_FULL_original_calendar_first_complete_iteration@1"
RELEASE = "CELLS_NATIVE_INIT_FIRST_STEP_RELEASED"
PARENT_SOURCE_SHA256 = PARENT_REVIEW_SHA256 = None
PARENT_CLAIM = "_claim_for_first_step"
PARENT_CHECK = "_check_first_step_authority"
SELECTION = "original_full_calendar_guarded_before_second_FOR_ITER@1"
NATIVE = previous.NATIVE
LOG_SOURCE = "betse/util/io/log/logs.py"
LOG_SHA256 = "73195e9d13a76ad5982be04e13847d2abc76819079d1caddc6122a23d89920f2"
CALLBACK_SOURCE_PINS = {
    "betse/science/phase/phasecallbacks.py": (
        "5938685e17f94e1066c938ae080800e22e918e5457d6406820e37d847540ac2b"
    ),
    "betse/util/type/call/callbacks.py": (
        "3d1bfd3a77c4f84dbad8392757edbb254f8f79e95bd1e528d0d5a40cf3693f83"
    ),
}
LOG_SUPPORT_PINS = {
    "betse/util/io/log/logfilter.py": (
        "0252faf8367486f7554aef1f1c7fb6c7dc3550f70b6006836b419ff2f396019f"
    ),
    "betse/util/io/log/conf/logconfhandle.py": (
        "b04f7fcb07dbe64b056acf4c58c2ac2e9226ca254f8e778ea12353aaa16f2042"
    ),
    "betse/util/io/log/conf/logconfformat.py": (
        "4c2fb0e558416240627c01eb074180f59b248be1c43134b47b678b8c0bc18613"
    ),
    "betse/util/io/log/conf/logconf.py": (
        "23ea0cc8122eee4903b11bb1a501e3f0f4115cf3edbd47872ce2803748afa5f0"
    ),
    "betse/util/io/log/conf/logconfcls.py": (
        "5f92d67b906ef1f9a2f5490c51d042997367164ed8d327df1d0a76ae8cb3411e"
    ),
    "betse/util/io/stderrs.py": "be56e74d81754e980c40e6845e6273225ba23f9b22a1fd2b3649d1d10dfff38a",
}
MAX_WORK = previous.MAX_WORK
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
SIM_METHODS = tuple(row[0] for row in source.ROSTER if row[2] == "Simulator") + ("update_V",)
OPTIONAL_BRANCHES = ("osmotic_P", "getFlow", "getDeformation", "timeDeform")


class FirstStepRejected(ValueError):
    def __init__(self, reason, *, stage, request=None, trial=None, partial=None):
        super().__init__(reason)
        self.stage, self.request, self.trial, self.partial = stage, request, trial, partial


class _SelectedStop(BaseException):
    """An owned iteration boundary, never a native/source error."""


class _ObservationStop(FirstStepRejected):
    """Observation failure, distinct from an exception raised by a source body."""


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    electrical_owner: object
    parent_identity: str
    source_identity: str
    selection: str
    operator_mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A source-owner request cannot be supplied or hydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    calendar: object
    sampled: object
    source_time_label: object
    configured_dt: object
    loop_index: int
    iteration_complete: bool
    loop_returned: bool
    selected_stop: bool
    work: tuple
    helper_calls: tuple
    stores: tuple
    raw_returns: tuple
    callback_calls: tuple
    stream_before: tuple
    stream_after: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class _ParentBinding:
    module: object
    claim: object
    check: object
    atoms: tuple


@dataclass(frozen=True, slots=True)
class _LoggingMethod:
    role: str
    receiver: object
    owner: object
    method: str
    chain: tuple


def _digest(value):
    return previous._digest(value)


def _same(actual, retained):
    if len(actual) != len(retained) or any(
        a is not b for a, b in zip(actual, retained, strict=True)
    ):
        raise ValueError("Original source/registry/callable reference changed")


def _definitions():
    """Authenticate literal bodies and compile original modules, without execution."""
    definitions = dict(previous._definitions())
    literal = ast.parse(Path(source.__file__).read_bytes())
    classes = {"Simulator": "FirstStepKernel", "Gap_Junction": "GapJunctionKernel"}
    compiled, trees = {}, {}
    for relative, pin in source.SOURCE_PINS.items():
        path = NATIVE / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Original first-step source changed: " + relative)
        raw = path.read_bytes()
        trees[relative] = ast.parse(raw)
        compiled[relative] = compile(raw, str(path), "exec", dont_inherit=True)
    for name, relative, cls, first, last in source.ROSTER:
        tree, code = trees[relative], compiled[relative]
        local = literal
        if cls is not None:
            tree = next(
                node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == cls
            )
            code = next(
                item for item in code.co_consts if type(item) is CodeType and item.co_name == cls
            )
            local = next(
                node
                for node in local.body
                if isinstance(node, ast.ClassDef) and node.name == classes[cls]
            )
        node = next(
            item for item in tree.body if isinstance(item, ast.FunctionDef) and item.name == name
        )
        retained = next(
            item for item in local.body if isinstance(item, ast.FunctionDef) and item.name == name
        )
        if (node.lineno, node.end_lineno) != (first, last) or ast.dump(
            ast.Module(body=node.body, type_ignores=[])
        ) != ast.dump(ast.Module(body=retained.body, type_ignores=[])):
            raise ValueError("Entire original first-step body changed: " + name)
        member = next(
            item for item in code.co_consts if type(item) is CodeType and item.co_name == name
        )
        definitions["gj_run" if cls == "Gap_Junction" else name] = node, member
    native_sim = trees["betse/science/sim.py"]
    simulator = next(
        node
        for node in native_sim.body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    )
    caller = next(
        node
        for node in simulator.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_sim_core"
    )
    body = [copy.deepcopy(node) for node in caller.body if 1049 <= node.lineno < 1121]
    if [(node.lineno, node.end_lineno) for node in body] != [
        (1049, 1049),
        (1055, 1055),
        (1059, 1059),
        (1062, 1114),
    ]:
        raise ValueError("Original post-electrical caller boundary changed")
    local = next(
        node
        for node in literal.body
        if isinstance(node, ast.ClassDef) and node.name == "SetupKernel"
    )
    selected = next(node for node in local.body if isinstance(node, ast.FunctionDef))
    if ast.dump(ast.Module(body=body, type_ignores=[])) != ast.dump(
        ast.Module(body=selected.body, type_ignores=[])
    ):
        raise ValueError("Literal post-electrical caller statements changed")
    method = ast.FunctionDef(
        name="_post_electrical_setup",
        args=ast.arguments(
            posonlyargs=[],
            args=[ast.arg(arg="self"), ast.arg(arg="phase")],
            kwonlyargs=[],
            kw_defaults=[],
            defaults=[],
        ),
        body=body,
        decorator_list=[],
        type_params=[],
    )
    ast.fix_missing_locations(method)
    module = compile(
        ast.Module(body=[method], type_ignores=[]),
        str(NATIVE / "betse/science/sim.py"),
        "exec",
        dont_inherit=True,
    )
    definitions["setup"] = method, next(item for item in module.co_consts if type(item) is CodeType)
    return definitions


def _root_attribute(node):
    while isinstance(node, ast.Subscript):
        node = node.value
    if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
        return node.value.id, node.attr
    return None


def _effects(nodes, receiver):
    """Declared original stores, subscript writes, and mutable-list/buffer calls."""
    result = set()
    for node in nodes:
        for item in ast.walk(node):
            if isinstance(item, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = item.targets if isinstance(item, ast.Assign) else (item.target,)
                for target in targets:
                    root = _root_attribute(target)
                    if root is not None and root[0] == receiver:
                        result.add(root[1])
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and item.func.attr in ("fill", "append", "extend", "clear")
            ):
                root = _root_attribute(item.func.value)
                if root is not None and root[0] == receiver:
                    result.add(root[1])
    return frozenset(result)


def source_plan():
    definitions = _definitions()
    sim = _effects([definitions[name][0] for name in SIM_METHODS], "self")
    # get_current writes its actual sim argument; that is the same Simulator.
    sim |= _effects([definitions["get_current"][0], definitions["gj_run"][0]], "sim")
    return dict(
        law=LAW_ID,
        source=dict(previous.source.SOURCE_PINS, **source.SOURCE_PINS),
        roster=source.ROSTER,
        simulator_fields=tuple(sorted(sim)),
        selection=SELECTION,
        full_calendar_and_sampled_set_retained=True,
        first_label_is_not_relabelled_as_dt=True,
        native_dt_and_sampling_unchanged=True,
        stop="before second original FOR_ITER; body did not return if selected stop is used",
        solver="actual native SolverType.FULL and INIT only",
        animation=(
            "genuine false native animation configuration before parameter/phase birth; "
            "true refuses without retrofit"
        ),
        transport="original NaK/Ca pumps, membrane/GJ/ECM, concentration and electrical closures",
        logging_source={LOG_SOURCE: LOG_SHA256},
        configured_logging_source=LOG_SUPPORT_PINS,
        logging_transport="original issued function/wrapper/body chain; no replacement logger",
        callback_source=CALLBACK_SOURCE_PINS,
        callback_transport=(
            "Actual issued callback class lookup and original wrapper/delegate/frame chain; "
            "one entry per original source call site, exact receiver/argument/return identity. "
            "Native callback execution and the whole issued parent path remain unqualified."
        ),
        operator="actual original value inverse; original-or-None flux inverse retained unchanged",
        unavailable=(
            "FAST",
            "SIM",
            "animation construction",
            "unselected callback methods/descriptors and foreign wrapper/delegate frames",
            "unowned enabled ER/network/force branches",
            "pickle/full-loop",
        ),
        parent_source=PARENT_SOURCE_SHA256,
        parent_review=PARENT_REVIEW_SHA256,
        actual_source_RNG_operator_reference_or_scientific_release=False,
    )


def _ready():
    if not all(
        previous.storage.previous._pin(value)
        for value in (PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256)
    ):
        raise FirstStepRejected("Reviewed electrical continuation remains held", stage="held")
    path = Path(previous.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != PARENT_SOURCE_SHA256:
        raise FirstStepRejected(
            "Original electrical continuation producer changed", stage="producer"
        )
    functions = []
    for name in (PARENT_CLAIM, PARENT_CHECK):
        function = vars(previous).get(name)
        if type(function) is not FunctionType:
            raise FirstStepRejected("Actual electrical continuation hook missing", stage="hook")
        previous.interfaces._source_interface(previous, path.read_bytes(), path, (name,))
        functions.append(function)
    previous._ready()
    return _ParentBinding(
        previous, *functions, tuple(previous._parent_atoms(fn) for fn in functions)
    )


def _check_parent(binding):
    if type(binding) is not _ParentBinding or binding.module is not previous:
        raise ValueError("Actual authenticated electrical parent required")
    for name, function, retained in zip(
        (PARENT_CLAIM, PARENT_CHECK), (binding.claim, binding.check), binding.atoms, strict=True
    ):
        if vars(previous).get(name) is not function:
            raise ValueError("Authenticated parent hook replaced")
        _same(previous._parent_atoms(function), retained)


def request_record(request):
    return dict(
        law=LAW_ID,
        parent=request.parent_identity,
        source=request.source_identity,
        selection=request.selection,
        operator_mode=request.operator_mode,
    )


def _operator_mode(cells):
    # Read only after real parent authentication. This describes a retained
    # already-constructed mode; it never constructs or accepts an operator.
    return (
        "original_value_only_flux_omitted"
        if cells.lapENV_P_inv is None
        else "original_value_and_flux"
    )


def from_electrical(owner, *, law_id):
    if type(law_id) is not str or law_id != LAW_ID:
        raise FirstStepRejected("Explicit selected first-step law required", stage="law")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant first-step declaration")
        if type(owner) is not previous.ElectricalOwner or owner in _RETIRED:
            raise FirstStepRejected("Actual unconsumed ElectricalOwner required", stage="owner")
        parent = previous._authority(owner)
        request = Request(
            owner,
            parent.trial.identity,
            _digest(source_plan()),
            SELECTION,
            _operator_mode(parent.cells),
            "",
        )
        request = replace(request, identity=_digest(request_record(request)))
        _REQUESTS[request] = (
            parent,
            parent.trial,
            previous._snapshot(parent),
            previous._graph(parent),
        )
        return request


def _reject(context, reason):
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = FirstStepRejected(
            reason, stage=context.stage, request=context.request, partial=context
        )
    if getattr(context, "first_failure", None) is None:
        context.first_failure = ("admission", context.entry_error)
    if context.first_failure[0] == "source":
        raise context.first_failure[1]
    raise context.entry_error


def _capture(context, origin, error, raw):
    context.last_capture = (origin, error, raw)
    if context.capture_error is None:
        context.capture_error = error
    try:
        context.capture_errors += (context.last_capture,)
    except BaseException as secondary:
        context.capture_append_error = (secondary, error, raw)


def _is_observer_error(context, error):
    return (
        error is getattr(context, "entry_error", None)
        or error is context.capture_error
        or error is getattr(context, "capture_stop", None)
        or isinstance(error, _ObservationStop)
        or any(error is value for value in getattr(context, "observer_errors", ()))
    )


def _source_error(context, frame, error):
    if error is context.selected_stop or _is_observer_error(context, error):
        return
    # Record raw identity and chain BEFORE pending/local/journal writes.
    context.last_raw_source_error = (frame, error)
    if getattr(context, "source_error", None) is None:
        original = getattr(context, "exception_origins", {}).get(id(error))
        if original is None or original[1] is not error:
            original = (
                frame,
                error,
                (
                    error,
                    BaseException.__getattribute__(error, "__cause__"),
                    BaseException.__getattribute__(error, "__context__"),
                    BaseException.__getattribute__(error, "__suppress_context__"),
                ),
            )
        context.source_origin = (original[0], error)
        context.source_error = error
        context.source_chain = original[2]
    if getattr(context, "first_failure", None) is None:
        context.first_failure = ("source", error)
    if context.first_failure[0] == "source":
        context.primary = context.first_failure[1]


def _pending_exception(context, frame, error):
    """Raw source observation is not yet an escaping-operation failure."""
    chain = (
        error,
        BaseException.__getattribute__(error, "__cause__"),
        BaseException.__getattribute__(error, "__context__"),
        BaseException.__getattribute__(error, "__suppress_context__"),
    )
    context.last_raw_source_exception = (frame, error, chain)
    try:
        context.exception_origins.setdefault(id(error), context.last_raw_source_exception)
        context.exception_events.append(context.last_raw_source_exception)
        if not _is_observer_error(context, error):
            context.pending[id(frame)] = error
        else:
            context.last_observer_exception_delivery = context.last_raw_source_exception
    except BaseException as capture:
        # Observation failure aborts handling. The pending original must win
        # over the secondary recorder failure, including falsey exceptions.
        _source_error(context, frame, error)
        _capture(context, "source_exception_record", capture, (frame, error, chain))


def _pending_observer_abort(context, frame, event, prior_failure):
    current = frame
    for _ in range(64):
        if current is None:
            return
        row = context.frames.get(id(current))
        if row is not None and row["frame"] is current:
            error = context.pending.get(id(current))
            if error is None:
                error = row.get("unwound_error")
            applicable = (
                event == "exception"
                or event == "call"
                and current is not frame
                or event == "return"
                and not previous.storage.previous.previous.previous._normal_return(current)
            )
            if (
                applicable
                and error is not None
                and error is not context.selected_stop
                and not _is_observer_error(context, error)
            ):
                if prior_failure is None and getattr(context, "first_failure", None) is not None:
                    context.secondary_observer_admission = context.first_failure
                    context.first_failure = ("source", error)
                _source_error(context, current, error)
                return
        current = current.f_back


def _primary(context):
    first = getattr(context, "first_failure", None)
    if first is not None:
        return first[1]
    return context.entry_error if context.entry_error is not None else context.primary


def _admission_error(context, error, raw):
    context.last_admission_error = (error, raw)
    context.invalid = True
    if context.entry_error is None:
        context.entry_error = error
    if getattr(context, "first_failure", None) is None:
        context.first_failure = ("admission", context.entry_error)


def _guard(context):
    first = getattr(context, "first_failure", None)
    if first is not None and first[0] == "source":
        raise first[1]
    if context.entry_error is not None:
        raise context.entry_error
    if context.capture_error is not None:
        if getattr(context, "capture_stop", None) is None:
            context.capture_stop = _ObservationStop(
                "Observation incomplete; no later delegate", stage="capture", partial=context
            )
        raise context.capture_stop from context.capture_error
    if (
        context.inherited
        or not context.active
        or context.invalid
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, "Exclusive genuine first-step epoch required")
    if (sys.setprofile, sys.settrace, sys.getprofile, sys.gettrace, sys.call_tracing) != (
        *context.setters,
        *context.getters,
        context.call_tracing,
    ):
        _reject(context, "Original observer controls changed")
    if context.observing and (
        context.getters[0]() is not context.observers[0]
        or context.getters[1]() is not context.observers[1]
    ):
        _reject(context, "Both inherited/source observers required")
    if context.observing:
        for function, code, namespace, closure in context.observer_code_binding:
            if (
                function.__code__ is not code
                or function.__globals__ is not namespace
                or function.__closure__ is not closure
            ):
                _reject(context, "Actual installed observer code/closure changed")


def _bootstrap(context):
    function, code, namespace = context.checker
    if (
        context.atoms is not function
        or function.__code__ is not code
        or function.__globals__ is not namespace
    ):
        raise ValueError("Independent first-step checker changed")
    for name, function, retained in context.metadata:
        if globals().get(name) is not function:
            raise ValueError("First-step metadata helper replaced: " + name)
        _same(previous._callable_atoms(context, function), retained)
    for path, pin in context.source_files.items():
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Retained reached native source changed")


def _snapshot(context, *, stable=False):
    objects = previous.storage.previous._objects(context.parent)
    projector = SimpleNamespace(objects=[*context.parent.init_parent.objects, *objects])
    project = previous.storage.previous.previous.previous.core._LITERAL._project
    values = []
    for role, actual in context.objects:
        holder = vars(actual)
        ignored = (
            next((fields for value, fields in context.permissions if value is actual), frozenset())
            if stable
            else frozenset()
        )
        fields = {key: value for key, value in holder.items() if key not in ignored}
        if getattr(context, "molecule_claim", None) is not None:
            fields = context.molecule.project_state(context.parent.molecule_session, fields)
        values.append((role, project(projector, fields)))
    return previous.storage.previous._scope(context.parent).snapshot(tuple(values))


def _graph(context, *, stable=False):
    if len(context.graph_fields) != len(context.objects):
        raise ValueError("Original retained graph projection roster changed")
    for (_, actual), target in zip(context.objects, context.graph_fields, strict=True):
        ignored = (
            next((fields for owner, fields in context.permissions if owner is actual), frozenset())
            if stable
            else frozenset()
        )
        target.clear()
        target.update((key, value) for key, value in vars(actual).items() if key not in ignored)
    return previous.storage.previous._scope(context.parent).graph(
        context.graph_view, context.graph_view, context.graph_tape
    )


def _epoch(context):
    graph = _graph(context)
    references, values = _local_state(context)
    log_references = _logging_epoch(context)
    return (
        _snapshot(context).identity,
        (graph[0] + references + log_references, (graph[1], values)),
        tuple(value.identity for value in previous.storage.previous._streams(context.parent)),
    )


def _local_state(context):
    """Protect paused source locals/temporary buffers across inherited observers.

    This is evidence only. Unknown objects are retained by actual identity;
    nothing here can issue a parent or hydrate an executable object.
    """
    references, rows, seen = [], [], set()
    scope = previous.storage.previous._scope(context.parent)
    owned = tuple(actual for _, actual in context.objects)

    def value(item):
        if len(references) >= MAX_WORK:
            raise ValueError("Bounded paused-source local witness exhausted")
        references.append(item)
        kind = type(item)
        if any(item is actual for actual in owned):
            return ("owned", kind.__name__)
        if kind in (str, bytes, int, float, bool, type(None)):
            return ("scalar", scope.snapshot(item).identity)
        if isinstance(item, (context.numpy.ndarray, context.numpy.generic)):
            return ("array_or_scalar", scope.snapshot(item).identity)
        if id(item) in seen:
            return ("reference", id(item))
        seen.add(id(item))
        if kind in (tuple, list, set, frozenset):
            return (kind.__name__, tuple(value(member) for member in item))
        if kind is dict:
            return ("dict", tuple((value(key), value(member)) for key, member in item.items()))
        return ("opaque_reference", kind.__module__, kind.__qualname__)

    frames = list(context.transport_frames)
    frames.extend(row["frame"] for row in context.work)
    frames.extend(row["frame"] for row in context.wrapper_claims.values())
    ordered, observed = [], set()
    for frame in frames:
        if id(frame) not in observed:
            ordered.append(frame)
            observed.add(id(frame))
    for frame in ordered:
        references.append(frame)
        rows.append(tuple((name, value(item)) for name, item in frame.f_locals.items()))
    return tuple(references), tuple(rows)


def _helper(context, name):
    def wrapper(*args, **kwargs):
        if context.wrappers.get(name) is not wrapper:
            _reject(context, "Original first-step helper wrapper changed")
        return _operation(context, name, args, kwargs, sys._getframe(1))

    return wrapper


def _source_members(function):
    result = list(previous._builtin_bindings(function))
    for code in previous._nested_codes(function.__code__):
        for name in code.co_names:
            if name in function.__globals__:
                result.append((function.__globals__, name, function.__globals__[name]))
    return result


def _logger_methods(context, originals):
    """Retain the actual canonical logger and its exact wrapper/body chain."""
    callbacks = previous.storage.previous.previous.previous.caches.previous.callbacks
    path = NATIVE / LOG_SOURCE
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != LOG_SHA256:
        raise ValueError("Original reached logger source changed")
    logs = originals["setup"].__globals__["logs"]
    if sys.modules.get("betse.util.io.log.logs") is not logs:
        raise ValueError("Actual original logging module required")
    chains = {}
    for name in ("log_info", "log_error"):
        function = vars(logs)[name]
        body = callbacks._source_function(function, LOG_SOURCE, name)
        chain = callbacks.simulator._chain(function)
        if chain[-1] is not body:
            raise ValueError("Original logging wrapper/body lineage changed")
        chains[name] = chain
        context.original_members.append((vars(logs), name, function))
        for member in chain:
            context.original_members.extend(_source_members(member))
        logging = body.__globals__["logging"]
        delegate = name.removeprefix("log_")
        context.original_members.append((vars(logging), delegate, vars(logging)[delegate]))
    context.source_files[path] = LOG_SHA256
    return chains


def _logging_configuration(context, originals):
    callbacks = previous.storage.previous.previous.previous.caches.previous.callbacks
    callbacks.simulator.tissue.aliases._check_modules()
    modules = {}
    for relative, pin in LOG_SUPPORT_PINS.items():
        path = NATIVE / relative
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Pinned configured logging source changed")
        module = sys.modules.get(relative[:-3].replace("/", "."))
        if module is None or Path(module.__file__).resolve() != path:
            raise ValueError("Actual issued configured logging module unavailable")
        modules[relative] = module
        context.source_files[path] = pin
    config_module = modules["betse/util/io/log/conf/logconf.py"]
    config = vars(config_module)["_log_conf"]
    config_type = vars(modules["betse/util/io/log/conf/logconfcls.py"])["LogConf"]
    if (
        type(config) is not config_type
        or originals["setup"].__globals__["logs"].logging is not logging
    ):
        raise ValueError("Actual original configured logging singleton required")
    root = vars(config).get("_logger_root")
    if root is not logging.root:
        raise ValueError("Original LogConf/root logger relationship changed")
    handlers = tuple(
        (name, vars(config)["_logger_root_handler_" + name])
        for name in ("stdout", "stderr", "file")
    )
    if len(root.handlers) != len(handlers) or any(
        a is not b for a, (_, b) in zip(root.handlers, handlers, strict=True)
    ):
        raise ValueError("Original configured handler order required")
    context.log_configuration = (
        config_module,
        config,
        config_type,
        root,
        root.handlers,
        root.filters,
        handlers,
        modules,
    )
    support = []
    native_filter = modules["betse/util/io/log/logfilter.py"]
    native_handler = modules["betse/util/io/log/conf/logconfhandle.py"]
    formatter_type = vars(modules["betse/util/io/log/conf/logconfformat.py"])["LogFormatterWrap"]
    for role, handler in handlers:
        expected = (
            native_handler.LogHandlerFileRotateSafe if role == "file" else logging.StreamHandler
        )
        if type(handler) is not expected or type(handler.formatter) is not formatter_type:
            raise ValueError("Actual configured handler/formatter classes required")
        for index, actual in enumerate(handler.filters):
            owner = type(actual)
            if owner not in (
                native_filter.LogFilterMoreThanInfo,
                native_filter.LogFilterThirdPartyDebug,
            ):
                raise ValueError("Unbound configured logging filter")
            support.append(
                _LoggingMethod(
                    role + ".filter" + str(index),
                    actual,
                    owner,
                    "filter",
                    callbacks.simulator._chain(vars(owner)["filter"]),
                )
            )
        if role == "file":
            for name in ("emit", "_emit_safely"):
                support.append(
                    _LoggingMethod(
                        role,
                        handler,
                        expected,
                        name,
                        callbacks.simulator._chain(vars(expected)[name]),
                    )
                )
    stderr = modules["betse/util/io/stderrs.py"]
    support.append(
        _LoggingMethod(
            "race_stderr", None, stderr, "output", callbacks.simulator._chain(stderr.output)
        )
    )
    for entry in support:
        body = entry.chain[-1]
        relative = str(Path(body.__code__.co_filename).relative_to(NATIVE))
        owner_name = None if entry.receiver is None else entry.owner.__name__
        if (
            callbacks._source_function(entry.chain[0], relative, entry.method, owner_name)
            is not body
        ):
            raise ValueError("Original configured logging body required")
        for member in entry.chain:
            context.original_members.extend(_source_members(member))
            for name in member.__code__.co_names:
                namespace = member.__globals__.get(name)
                if type(namespace) is type(logging):
                    context.original_members.extend(
                        (vars(namespace), key, vars(namespace)[key])
                        for key in member.__code__.co_names
                        if key in vars(namespace)
                    )
            for name in ("DEBUG", "INFO"):
                level = member.__globals__.get("LogLevel")
                if level is not None and name in vars(level):
                    context.original_members.append((vars(level), name, vars(level)[name]))
    context.log_support = tuple(support)
    context.log_protocol = tuple(
        (owner, name, vars(owner)[name])
        for owner, names in (
            (
                logging.Logger,
                ("info", "error", "_log", "handle", "callHandlers", "isEnabledFor", "makeRecord"),
            ),
            (logging.Filterer, ("filter",)),
            (logging.Handler, ("handle", "format", "handleError", "acquire", "release")),
            (logging.StreamHandler, ("emit", "flush")),
            (logging.FileHandler, ("emit", "_open")),
            (logging.handlers.RotatingFileHandler, ("shouldRollover", "doRollover")),
            (logging.handlers.BaseRotatingHandler, ("emit", "rotation_filename", "rotate")),
        )
        for name in names
    )
    context.log_module_members = tuple(
        (name, vars(logging)[name])
        for name in (
            "root",
            "Logger",
            "Filterer",
            "Handler",
            "LogRecord",
            "_logRecordFactory",
            "_lock",
            "raiseExceptions",
            "lastResort",
        )
    )
    classes = (
        type(root),
        config_type,
        *(type(value) for _, value in handlers),
        *(type(actual) for _, value in handlers for actual in value.filters),
        *(type(value.formatter) for _, value in handlers),
        *(type(vars(value.formatter).get("_style")) for _, value in handlers),
    )
    context.log_surfaces = tuple(
        (cls, previous.storage.previous.previous.previous._surface(cls))
        for cls in dict.fromkeys(classes)
    )
    context.log_configuration_binding = _logging_policy(context)


def _logging_policy(context):
    if context.log_configuration is None:
        return ()
    module, config, cls, root, handler_list, root_filters, handlers, modules = (
        context.log_configuration
    )
    if (
        vars(module).get("_log_conf") is not config
        or type(config) is not cls
        or vars(config).get("_logger_root") is not root
        or logging.root is not root
        or root.handlers is not handler_list
        or root.filters is not root_filters
        or len(handler_list) != len(handlers)
        or any(a is not b for a, (_, b) in zip(handler_list, handlers, strict=True))
    ):
        raise ValueError("Actual configured logging relationships changed")
    result = [
        module,
        config,
        cls,
        root,
        handler_list,
        root_filters,
        *root_filters,
        root.manager,
        root.manager.disable,
    ]
    for name in ("name", "level", "disabled", "propagate", "parent"):
        result.append(vars(root).get(name))
    for role, handler in handlers:
        if vars(config).get("_logger_root_handler_" + role) is not handler:
            raise ValueError("Original LogConf handler alias changed")
        result.extend(
            (
                handler,
                type(handler),
                type(handler).__mro__,
                handler.filters,
                *handler.filters,
                handler.formatter,
                type(handler.formatter),
                vars(handler.formatter).get("_style"),
            )
        )
        for name in (
            "level",
            "lock",
            "baseFilename",
            "mode",
            "encoding",
            "errors",
            "delay",
            "maxBytes",
            "backupCount",
            "namer",
            "rotator",
        ):
            result.append(vars(handler).get(name))
        for name, value in vars(handler.formatter).items():
            result.extend((name, value))
        style = vars(handler.formatter).get("_style")
        if style is not None:
            for name, value in vars(style).items():
                result.extend((name, value))
        for actual in (handler, *handler.filters):
            for name, value in vars(actual).items():
                result.append(name)
                if name != "stream":
                    result.append(value)
    for name, value in vars(root).items():
        result.extend((name, value))
    return tuple(result)


def _logging_epoch(context):
    if context.log_configuration is None:
        return ()
    root = context.log_configuration[3]
    cache = vars(root).get("_cache", {})
    return (
        _logging_policy(context)
        + tuple(vars(handler).get("stream") for _, handler in context.log_configuration[6])
        + tuple(value for pair in cache.items() for value in pair)
    )


def _logging_bindings(context):
    if context.log_configuration is None:
        return (
            context.log_configuration,
            context.log_support,
            context.log_protocol,
            context.log_module_members,
        )
    _same(_logging_policy(context), context.log_configuration_binding)
    result = [
        context.log_configuration,
        context.log_configuration_binding,
        context.log_support,
        context.log_protocol,
        context.log_module_members,
    ]
    for name, retained in context.log_module_members:
        if vars(logging).get(name) is not retained:
            raise ValueError("Original stdlib logging dispatch/factory changed")
        result.extend((name, retained))
    for owner, name, function in context.log_protocol:
        if vars(owner).get(name) is not function:
            raise ValueError("Original logging protocol method changed")
        result.extend(previous._callable_atoms(context, function))
    for owner, surface in context.log_surfaces:
        _same(previous.storage.previous.previous.previous._surface(owner), surface)
    for entry in context.log_support:
        if vars(entry.owner).get(entry.method) is not entry.chain[0]:
            raise ValueError("Actual native logging class/helper delegate changed")
        result.extend((entry, entry.receiver, entry.owner, entry.chain))
        for function in entry.chain:
            previous._builtin_bindings(function)
            result.extend(previous._callable_atoms(context, function))
    if context.log_closed_epoch is not None:
        _same(_logging_epoch(context), context.log_closed_epoch)
    return tuple(result)


def _logging_entry(context, row):
    frame, operation = row["frame"], context.operation
    choices = context.log_support_codes.get(frame.f_code, ())
    selected = []
    for entry, index in choices:
        function = entry.chain[index]
        if frame.f_globals is not function.__globals__:
            continue
        receiver = frame.f_locals.get("self")
        args = frame.f_locals.get("args", ())
        if receiver is None and type(args) is tuple and args:
            receiver = args[0]
        if entry.receiver is None or receiver is entry.receiver:
            selected.append((entry, index))
    if (
        len(selected) != 1
        or operation is None
        or operation["name"] not in ("log_info", "log_error")
    ):
        _reject(context, "Actual configured logging operation/receiver required")
    entry, index = selected[0]
    parent = _source_row(context, frame.f_back)
    if index:
        if (
            parent is None
            or parent.get("log_support") is not entry
            or parent.get("log_index") != index - 1
        ):
            _reject(context, "Exact native logging wrapper/delegate frame required")
    elif entry.receiver is None:
        if (
            parent is None
            or parent.get("log_support") is None
            or parent["log_support"].method != "_emit_safely"
        ):
            _reject(context, "Logging race helper detached from original retry")
    elif entry.method == "filter":
        if (
            frame.f_back.f_code is not logging.Filterer.filter.__code__
            or not any(
                frame.f_back.f_locals.get("self") is value
                for value in (
                    context.log_configuration[3],
                    *(item for _, item in context.log_configuration[6]),
                )
            )
            or not any(item is entry.receiver for item in frame.f_back.f_locals["self"].filters)
        ):
            _reject(context, "Native filter detached from actual Filterer/handler")
    elif entry.method == "emit":
        if (
            frame.f_back.f_code is not logging.Handler.handle.__code__
            or frame.f_back.f_locals.get("self") is not entry.receiver
        ):
            _reject(context, "Native emit detached from actual Handler.handle")
    elif (
        parent is None
        or parent.get("log_support") is None
        or parent["log_support"].receiver is not entry.receiver
        or parent["log_support"].method != "emit"
    ):
        _reject(context, "Native retry detached from original emit")
    row.update(log_support=entry, log_index=index)
    if entry.receiver is not None:
        values = _callback_arguments(
            context, entry.chain[index], frame, entry.chain[-1], entry.receiver
        )
        record = values[1][1]
        if index and record is not parent["log_record"]:
            _reject(context, "Native logging record identity changed across wrapper")
        caller, source_seen = frame.f_back, False
        for _ in range(64):
            if caller is None or caller is operation["frame"]:
                break
            if caller.f_code is logging.Logger._log.__code__:
                if (
                    caller.f_locals.get("self") is not context.log_configuration[3]
                    or caller.f_locals.get("record") is not record
                ):
                    _reject(context, "LogRecord not owned by the original root dispatch")
                source_seen = True
            caller = caller.f_back
        if not source_seen:
            _reject(context, "Native logging requires the actual root LogRecord frame")
        row["log_record"] = record


def _logging_frame(context, row):
    entry = row.get("log_support")
    if entry is None:
        return
    frame, index = row["frame"], row["log_index"]
    if (
        frame.f_code is not entry.chain[index].__code__
        or frame.f_globals is not entry.chain[index].__globals__
    ):
        _reject(context, "Actual native logging frame binding changed")
    if entry.receiver is not None:
        values = _callback_arguments(
            context, entry.chain[index], frame, entry.chain[-1], entry.receiver
        )
        if values[1][1] is not row["log_record"]:
            _reject(context, "Actual configured LogRecord argument changed")


def _callback_methods(context):
    callbacks = context.phase.callbacks
    if callbacks is not context.initial.callback:
        raise FirstStepRejected("Original issued callback identity required", stage="callback")
    context.callback_owner, context.callback_type = callbacks, type(callbacks)
    context.callback_mro = type(callbacks).__mro__
    selected, queue = {}, ["progress_ranged", "progressed_next"]
    while queue:
        name = queue.pop()
        if name in selected:
            continue
        owner = next((cls for cls in type(callbacks).__mro__ if name in vars(cls)), None)
        member = None if owner is None else vars(owner)[name]
        if type(member) is not FunctionType:
            raise FirstStepRejected("Actual native callback method unavailable", stage="callback")
        chain = (
            previous.storage.previous.previous.previous.caches.previous.callbacks.simulator._chain(
                member
            )
        )
        function = chain[-1]
        path = Path(function.__code__.co_filename)
        if not path.is_relative_to(NATIVE) or path.is_symlink():
            raise ValueError("Actual issued native callback source required")
        relative = str(path.relative_to(NATIVE))
        if CALLBACK_SOURCE_PINS.get(relative) != hashlib.sha256(path.read_bytes()).hexdigest():
            raise ValueError("Pinned original callback body required")
        original = (
            previous.storage.previous.previous.previous.caches.previous.callbacks._source_function(
                member, relative, name, owner.__name__
            )
        )
        selected[name] = original
        if original is not chain[-1] or any(
            member.__code__.co_flags & (0x20 | 0x80 | 0x200) for member in chain
        ):
            raise ValueError("Original synchronous callback wrapper/body chain required")
        previous._native_defaults(
            original,
            next(
                item
                for node in ast.parse(path.read_bytes()).body
                if isinstance(node, ast.ClassDef) and node.name == owner.__name__
                for item in node.body
                if isinstance(item, ast.FunctionDef) and item.name == name
            ),
        )
        context.callback_chains[name] = chain
        context.callback_lookups[name] = owner, member
        context.source_files[path] = CALLBACK_SOURCE_PINS[relative]
        scope = ast.parse(path.read_bytes())
        cls_node = next(
            node
            for node in scope.body
            if isinstance(node, ast.ClassDef) and node.name == owner.__name__
        )
        node = next(
            node
            for node in cls_node.body
            if isinstance(node, ast.FunctionDef) and node.name == name
        )
        context.callback_nodes[name] = node
        for item in ast.walk(node):
            if (
                isinstance(item, ast.Call)
                and isinstance(item.func, ast.Attribute)
                and isinstance(item.func.value, ast.Name)
                and item.func.value.id == "self"
            ):
                queue.append(item.func.attr)
    return selected


def _callback_sites(node, prefix):
    result = {}
    for call in ast.walk(node):
        if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Attribute):
            continue
        parts, value = [], call.func
        while isinstance(value, ast.Attribute):
            parts.append(value.attr)
            value = value.value
        if not isinstance(value, ast.Name):
            continue
        path = (value.id, *reversed(parts))
        if path[:-1] != prefix:
            continue
        result.setdefault(path[-1], []).append(
            (call.lineno, call.end_lineno, call.col_offset, call.end_col_offset)
        )
    return {name: tuple(sites) for name, sites in result.items()}


def _callback_bindings(context):
    result = [
        context.callback_owner,
        context.callback_methods,
        context.callback_chains,
        context.callback_lookups,
        context.callback_sites,
    ]
    if not context.callback_methods:
        if (
            context.callback_owner is not None
            or context.callback_chains
            or context.callback_lookups
        ):
            raise ValueError("Incomplete original callback authority")
        return tuple(result)
    actual = context.callback_owner
    if (
        context.phase.callbacks is not actual
        or context.initial.callback is not actual
        or type(actual) is not context.callback_type
        or type(actual).__mro__ is not context.callback_mro
        or tuple(context.callback_methods) != tuple(context.callback_chains)
        or tuple(context.callback_methods) != tuple(context.callback_lookups)
    ):
        raise ValueError("Actual callback instance/type/source roster changed")
    result.extend((context.callback_type, context.callback_mro))
    for name, chain in context.callback_chains.items():
        owner = next((base for base in type(actual).__mro__ if name in vars(base)), None)
        retained_owner, member = context.callback_lookups[name]
        if (
            owner is not retained_owner
            or vars(owner).get(name) is not member
            or member is not chain[0]
            or context.callback_methods[name] is not chain[-1]
        ):
            raise ValueError("Original callback class method/delegate lookup changed")
        result.extend((name, owner, member, chain))
        for function in chain:
            previous._builtin_bindings(function)
            result.extend(previous._callable_atoms(context, function))
    for key, sites in context.callback_sites.items():
        result.extend((key, sites))
    return tuple(result)


def _callback_arguments(context, function, frame, body, receiver):
    """Project the real call without invoking descriptors/signature machinery."""
    if frame.f_code is not function.__code__ or frame.f_globals is not function.__globals__:
        _reject(context, "Original callback executable/global namespace required")
    code, local = function.__code__, frame.f_locals
    count, kwcount = code.co_argcount, code.co_kwonlyargcount
    positional = tuple(local[name] for name in code.co_varnames[:count])
    keywords = {}
    defaults = function.__kwdefaults__ or {}
    formal = body.__code__.co_varnames[
        : body.__code__.co_argcount + body.__code__.co_kwonlyargcount
    ]
    for name in code.co_varnames[count : count + kwcount]:
        if name in formal:
            keywords[name] = local[name]
        elif (
            not name.startswith("__beartype_")
            or name not in defaults
            or local[name] is not defaults[name]
        ):
            _reject(context, "Unbound callback decorator keyword/default")
    index = count + kwcount
    if code.co_flags & 4:
        tail = local[code.co_varnames[index]]
        if type(tail) is not tuple:
            _reject(context, "Actual callback positional tuple required")
        positional += tail
        index += 1
    if code.co_flags & 8:
        extra = local[code.co_varnames[index]]
        if type(extra) is not dict or any(type(name) is not str for name in extra):
            _reject(context, "Actual callback keyword dictionary required")
        if keywords.keys() & extra.keys():
            _reject(context, "Duplicate callback keyword forwarding")
        keywords.update(extra)
    native = body.__code__
    if native.co_flags & (4 | 8) or len(positional) > native.co_argcount:
        _reject(context, "Selected fixed original callback signature required")
    names = native.co_varnames[: native.co_argcount + native.co_kwonlyargcount]
    values = dict(zip(names, positional, strict=False))
    for name, value in keywords.items():
        if name not in names or name in values or name in names[: native.co_posonlyargcount]:
            _reject(context, "Original callback argument forwarding changed")
        values[name] = value
    inherited = body.__defaults__ or ()
    for name, value in zip(
        names[native.co_argcount - len(inherited) : native.co_argcount], inherited, strict=True
    ):
        values.setdefault(name, value)
    for name, value in (body.__kwdefaults__ or {}).items():
        values.setdefault(name, value)
    if (
        tuple(name for name in names if name in values) != names
        or values.get("self") is not receiver
    ):
        _reject(context, "Actual callback receiver and complete native arguments required")
    return tuple((name, values[name]) for name in names)


def _callback_enter(context, row):
    frame = row["frame"]
    _, method, value = row["name"].split(":")
    index = int(value)
    chain = context.callback_chains[method]
    function, body = chain[index], chain[-1]
    arguments = _callback_arguments(context, function, frame, body, context.callback_owner)
    parent = _source_row(context, frame.f_back)
    if index == 0:
        if parent is None:
            _reject(context, "Callback has no actual admitted source caller")
        parent_claim = parent.get("callback_claim")
        parent_name = parent["name"]
        if parent_claim is not None:
            if parent["callback_index"] != len(parent_claim["chain"]) - 1:
                _reject(context, "A callback wrapper cannot seize the next method")
            parent_name = "callback:" + parent_claim["name"]
        locations = context.callback_sites.get((parent_name, method), ())
        position = next(
            (
                item.positions
                for item in dis.get_instructions(frame.f_back.f_code, show_caches=True)
                if item.offset == frame.f_back.f_lasti
            ),
            None,
        )
        location = (
            None
            if position is None
            else (
                position.lineno,
                position.end_lineno,
                position.col_offset,
                position.end_col_offset,
            )
        )
        if location not in locations:
            _reject(context, "Exact original callback call site required")
        site = (id(frame.f_back), method, location)
        if site in context.callback_claimed_sites:
            _reject(context, "Original callback call site already attempted")
        if parent_name in ("setup", "_run_sim_core_loop"):
            expected = "progress_ranged" if parent_name == "setup" else "progressed_next"
            if method != expected or method in context.callback_roots:
                _reject(context, "Once-only declared source callback required")
            context.callback_roots.add(method)
        claim = dict(
            name=method,
            chain=chain,
            parent=frame.f_back,
            site=site,
            arguments=arguments,
            frames=[],
            return_order=[],
            complete=False,
            error=None,
        )
        context.last_callback_claim = claim
        context.callback_claimed_sites.add(site)
        context.callback_calls.append(claim)
    else:
        claim = None if parent is None else parent.get("callback_claim")
        if (
            claim is None
            or claim["name"] != method
            or claim["chain"] is not chain
            or parent["callback_index"] != index - 1
            or len(claim["frames"]) != index
            or frame.f_back is not claim["frames"][-1]["frame"]
        ):
            _reject(context, "Original callback delegate has no exact once-only wrapper parent")
    retained = claim["arguments"]
    if tuple(name for name, _ in arguments) != tuple(name for name, _ in retained):
        _reject(context, "Original callback parameter roster changed")
    _same(tuple(value for _, value in arguments), tuple(value for _, value in retained))
    row.update(
        callback_claim=claim,
        callback_index=index,
        callback_arguments=arguments,
        callback_call_layers=set(),
        callback_return_layers=set(),
        callback_raw_seen=False,
    )
    claim["frames"].append(row)


def _callback_frame(context, row):
    claim = row.get("callback_claim")
    if claim is None:
        return
    index = row["callback_index"]
    if (
        context.callback_chains.get(claim["name"]) is not claim["chain"]
        or claim["frames"][index] is not row
        or row["frame"].f_back
        is not (claim["parent"] if index == 0 else claim["frames"][index - 1]["frame"])
    ):
        _reject(context, "Retained callback frame/claim lineage changed")
    values = _callback_arguments(
        context, claim["chain"][index], row["frame"], claim["chain"][-1], context.callback_owner
    )
    _same(tuple(value for _, value in values), tuple(value for _, value in claim["arguments"]))


def _callback_event(context, row, event, arg, layer):
    if row is None or "callback_claim" not in row:
        return
    claim, index = row["callback_claim"], row["callback_index"]
    if event == "return":
        # Retain the real return before any argument validation or ledger work.
        if not row["callback_raw_seen"]:
            row["callback_last_raw"] = (row["frame"], arg)
            row["callback_result"], row["callback_raw_seen"] = arg, True
        elif row["callback_result"] is not arg:
            row["callback_secondary_raw"] = (row["frame"], layer, arg)
            if context.capture_error is not None or _primary(context) is not None:
                # A rejected trace-return observation makes CPython deliver an
                # unwind None to profile. Preserve the completed real return;
                # that secondary delivery cannot replace the earlier failure.
                claim["observation_failed"] = True
                return
            _reject(context, "Actual callback trace/profile return identity changed")
    _callback_frame(context, row)
    if event == "call":
        if layer in row["callback_call_layers"]:
            _reject(context, "Duplicate callback observer entry")
        row["callback_call_layers"].add(layer)
    elif event == "return":
        row["callback_return_layers"].add(layer)
        error = context.pending.get(id(row["frame"]))
        if error is not None and not previous.storage.previous.previous.previous._normal_return(
            row["frame"]
        ):
            claim["error"] = error
        if row["callback_return_layers"] == {"trace", "profile"}:
            if claim["error"] is None and _primary(context) is None:
                if len(claim["frames"]) != len(claim["chain"]) or index != len(
                    claim["chain"]
                ) - 1 - len(claim["return_order"]):
                    _reject(context, "Original full callback chain must return in order")
                if (
                    index < len(claim["chain"]) - 1
                    and arg is not claim["frames"][index + 1]["callback_result"]
                ):
                    _reject(context, "Callback decorator replaced the original return")
            claim["return_order"].append(index)
            if index == 0 and claim["error"] is None and _primary(context) is None:
                claim["complete"] = True


def _callbacks_complete(context):
    if "progress_ranged" not in context.callback_roots:
        _reject(context, "Original calendar callback never completed")
    for claim in context.callback_calls:
        if (
            not claim["complete"]
            or claim["error"] is not None
            or claim["return_order"] != list(reversed(range(len(claim["chain"]))))
        ):
            _reject(context, "Incomplete original callback transport")
        for row in claim["frames"]:
            _callback_frame(context, row)
            if row["callback_call_layers"] != {"trace", "profile"} or row[
                "callback_return_layers"
            ] != {"trace", "profile"}:
                _reject(context, "Both callback observer layers required")


def _namespace(context):
    definitions = _definitions()
    factory = context.initial.factories["Simulator"]
    originals = dict(context.electrical_parent.originals)
    for name in SIM_METHODS:
        originals[name] = previous._native_member(getattr(factory, name), *definitions[name])
    caller_node = next(
        node
        for node in ast.parse((NATIVE / "betse/science/sim.py").read_bytes()).body
        if isinstance(node, ast.ClassDef) and node.name == "Simulator"
    )
    caller_node = next(
        node
        for node in caller_node.body
        if isinstance(node, ast.FunctionDef) and node.name == "run_sim_core"
    )
    caller_code = compile(
        (NATIVE / "betse/science/sim.py").read_bytes(),
        str(NATIVE / "betse/science/sim.py"),
        "exec",
        dont_inherit=True,
    )
    owner_code = next(
        code
        for code in caller_code.co_consts
        if type(code) is CodeType and code.co_name == "Simulator"
    )
    native_code = next(
        code
        for code in owner_code.co_consts
        if type(code) is CodeType and code.co_name == "run_sim_core"
    )
    originals["setup"] = previous._native_member(factory.run_sim_core, caller_node, native_code)
    root = originals["update_V"]
    numpy = root.__globals__["np"]
    toolbox, finite = (
        originals["get_current"].__globals__["stb"],
        originals["get_current"].__globals__["fd"],
    )
    for name, (_, _, cls, _, _) in ((row[0], row) for row in source.ROSTER):
        if cls is None and name != "noop_context":
            module = finite if name == "integrator" else toolbox
            originals[name] = previous._native_member(vars(module)[name], *definitions[name])
    gap = vars(context.sim).get("gj_funk")
    if context.p.v_sensitive_gj is True:
        if gap is None or gap is not context.initial.dynamics_transition.gap:
            raise FirstStepRejected("Actual issued native GJ object required", stage="gap")
        originals["gj_run"] = previous._native_member(type(gap).run, *definitions["gj_run"])
    context.originals, context.numpy, context.gap = originals, numpy, gap
    context.sim_wrappers = {name: vars(type(context.sim))[name] for name in SIM_METHODS}
    context.callback_methods = _callback_methods(context)
    context.callback_sites = {
        (name, method): positions
        for name in ("setup", "_run_sim_core_loop")
        for method, positions in _callback_sites(
            definitions[name][0], ("phase", "callbacks")
        ).items()
    }
    context.callback_sites.update(
        {
            ("callback:" + name, method): positions
            for name, node in context.callback_nodes.items()
            for method, positions in _callback_sites(node, ("self",)).items()
        }
    )
    context.class_surfaces = tuple(
        (cls, previous.storage.previous.previous.previous._surface(cls))
        for cls in dict.fromkeys(
            (
                type(context.phase),
                type(context.sim),
                type(context.p),
                type(context.phase.callbacks),
                type(context.gap),
            )
        )
        if cls is not type(None)
    )
    context.original_members = []
    for original in (
        *originals.values(),
        *(member for chain in context.callback_chains.values() for member in chain),
    ):
        context.original_members.extend(_source_members(original))
    enum = originals["setup"].__globals__["SimPhaseKind"]
    solver = originals["setup"].__globals__["SolverType"]
    context.original_members.extend(
        (vars(enum), name, vars(enum)[name]) for name in ("INIT", "SIM")
    )
    context.original_members.extend(
        (vars(solver), name, vars(solver)[name]) for name in ("FULL", "FAST")
    )
    np_names = set()
    for node, _ in definitions.values():
        for item in ast.walk(node):
            if (
                isinstance(item, ast.Attribute)
                and isinstance(item.value, ast.Name)
                and item.value.id == "np"
                and item.attr != "random"
            ):
                np_names.add(item.attr)
    context.external = {"np." + name: vars(numpy)[name] for name in sorted(np_names)}
    for name in ("gaussian_filter",):
        context.external[name] = originals["get_current"].__globals__[name]
    # Context creation uses the ORIGINAL decorated noop factory and generator,
    # not a fake context or a replacement of the configured animation branch.
    noop = originals["_plot_loop"].__globals__["noop_context"]
    generator = previous._native_member(noop, *definitions["noop_context"])
    context.external["noop_context"] = noop
    context.noop_generator = generator
    context.noop_type = noop.__globals__["_GeneratorContextManager"]
    context.noop_methods = (context.noop_type.__enter__, context.noop_type.__exit__)
    context.class_surfaces += (
        (
            context.noop_type,
            previous.storage.previous.previous.previous._surface(context.noop_type),
        ),
    )
    context.external["log_info"] = originals["setup"].__globals__["logs"].log_info
    context.external["log_error"] = originals["setup"].__globals__["logs"].log_error
    context.logger_chains = _logger_methods(context, originals)
    _logging_configuration(context, originals)
    context.external["time"] = originals["_run_sim_core_loop"].__globals__["time"].time
    context.original_members += [
        (vars(numpy), name, vars(numpy)[name]) for name in sorted(np_names)
    ]
    context.original_members += [(originals["_plot_loop"].__globals__, "noop_context", noop)]
    context.original_members.append(
        (noop.__globals__, "_GeneratorContextManager", context.noop_type)
    )
    context.external["animation_factory"] = None
    context.wrappers = {
        name: _helper(context, name) for name in (*originals, *context.external, *OPTIONAL_BRANCHES)
    }
    np_view = SimpleNamespace(**{name: context.wrappers["np." + name] for name in sorted(np_names)})
    stb_view = SimpleNamespace(
        **{name: context.wrappers[name] for name in originals if name in vars(toolbox)}
    )
    fd_view = SimpleNamespace(
        **{name: context.wrappers[name] for name in originals if name in vars(finite)}
    )
    log_view = SimpleNamespace(
        log_info=context.wrappers["log_info"], log_error=context.wrappers["log_error"]
    )
    time_view = SimpleNamespace(time=context.wrappers["time"])
    context.methods, context.namespaces = {}, []
    for name, original in originals.items():
        namespace = dict(original.__globals__)
        namespace.update(
            np=np_view,
            stb=stb_view,
            fd=fd_view,
            logs=log_view,
            time=time_view,
            get_current=context.wrappers["get_current"],
            HH_Decomp=context.wrappers["HH_Decomp"],
            diff=context.wrappers["diff"],
            div_env=context.wrappers["div_env"],
            no_negs=context.wrappers["no_negs"],
            gaussian_filter=context.wrappers["gaussian_filter"],
            noop_context=context.wrappers["noop_context"],
            SimPhase=context.wrappers["animation_factory"],
            AnimCellsWhileSolving=context.wrappers["animation_factory"],
            **{key: context.wrappers[key] for key in OPTIONAL_BRANCHES},
        )
        if name == "setup":
            # isinstance needs the real unchanged class; only construction is
            # unavailable. No animation object is fabricated for this test.
            namespace["AnimCellsWhileSolving"] = original.__globals__["AnimCellsWhileSolving"]
        code = definitions[name][1]
        function = FunctionType(
            code, namespace, code.co_name, original.__defaults__, original.__closure__
        )
        if name == "gj_run":
            # This pre-existing object's method is called by the actual native
            # update_gj body. Preserve its real function/globals and receiver;
            # never replace its class or install an instance method.
            function = original
        function.__kwdefaults__ = original.__kwdefaults__
        previous._builtin_bindings(function)
        context.methods[name] = function
        context.namespaces.append((namespace, tuple(namespace.items())))
    context.facades = tuple(
        (facade, tuple(vars(facade).items()))
        for facade in (np_view, stb_view, fd_view, log_view, time_view)
    )
    context.allowed_codes = (
        frozenset(
            code
            for function in context.methods.values()
            for code in previous._nested_codes(function.__code__)
        )
        | frozenset(
            function.__code__ for chain in context.callback_chains.values() for function in chain
        )
        | frozenset((generator.__code__,))
    )
    context.body_names = {function.__code__: name for name, function in context.methods.items()}
    for name, chain in context.callback_chains.items():
        for index, function in enumerate(chain):
            if function.__code__ in context.body_names:
                raise ValueError("Distinct original callback method/wrapper code required")
            context.body_names[function.__code__] = "callback:" + name + ":" + str(index)
    context.body_names[generator.__code__] = "noop_context_generator"
    for name, chain in context.logger_chains.items():
        for index, function in enumerate(chain):
            label = "logger:" + name + ":" + str(index)
            if function.__code__ in context.body_names:
                raise ValueError("Distinct original logger entry/code required")
            context.allowed_codes |= frozenset((function.__code__,))
            context.body_names[function.__code__] = label
    support_codes = {}
    for entry in context.log_support:
        for index, function in enumerate(entry.chain):
            support_codes.setdefault(function.__code__, []).append((entry, index))
            context.allowed_codes |= frozenset((function.__code__,))
            context.body_names[function.__code__] = "logging_support"
    context.log_support_codes = MappingProxyType(
        {code: tuple(values) for code, values in support_codes.items()}
    )
    for label, function in zip(
        ("solver_context_enter", "solver_context_exit"), context.noop_methods, strict=True
    ):
        context.allowed_codes |= frozenset((function.__code__,))
        context.body_names[function.__code__] = label
    context.loop_code = context.methods["_run_sim_core_loop"].__code__
    outer = next(
        node for node in definitions["_run_sim_core_loop"][0].body if isinstance(node, ast.For)
    )
    loops = [
        instruction
        for instruction in dis.get_instructions(context.loop_code)
        if instruction.opname == "FOR_ITER" and instruction.positions.lineno == outer.lineno
    ]
    if len(loops) != 1:
        raise ValueError("Exact outer original iteration boundary required")
    context.loop_offset = loops[0].offset
    context.permissions = _mutation_contract(context)
    objects = list(previous.storage.previous._objects(context.parent))
    for role, value in (
        ("parameters", context.p),
        ("cells", context.cells),
        ("callback", context.phase.callbacks),
        ("gap", gap),
    ):
        if value is not None and not any(actual is value for _, actual in objects):
            objects.append((role, value))
    context.objects = tuple(objects)
    for role, actual in context.initial.seed_lease.objects:
        if not any(value is actual for _, value in context.objects):
            context.objects += (("historical:" + role, actual),)
    context.graph_fields = [{} for _ in context.objects]
    context.graph_view = SimpleNamespace(objects=context.objects, fields=context.graph_fields)
    context.source_files = MappingProxyType(dict(context.source_files))


def _mutation_contract(context):
    definitions = _definitions()
    sim = _effects([definitions[name][0] for name in SIM_METHODS], "self")
    sim |= _effects([definitions["get_current"][0], definitions["gj_run"][0]], "sim")
    result = [(context.sim, sim)]
    if context.gap is not None:
        result.append((context.gap, _effects([definitions["gj_run"][0]], "self")))
    result.append((context.phase.callbacks, _effects(context.callback_nodes.values(), "self")))
    return tuple(result)


def _domain(context):
    namespace = context.originals["setup"].__globals__
    if (
        context.phase.kind is not namespace["SimPhaseKind"].INIT
        or context.p.solver_type is not namespace["SolverType"].FULL
        or context.p.is_ecm is not True
    ):
        raise FirstStepRejected(
            "Actual ordinary INIT FULL ECM source is required", stage="domain", partial=context
        )
    if context.p.anim.is_while_sim:
        raise FirstStepRejected(
            "Actual animation requires an unowned constructor; fresh headless input "
            "must precede parameter/phase birth",
            stage="animation_prerequisite",
            partial=context,
        )
    if _operator_mode(context.cells) != context.request.operator_mode:
        raise ValueError("Actual retained operator mode changed")


def _binding(context):
    _bootstrap(context)
    # A return observer can change a cloned global after the construction-time
    # check. Authenticate builtin resolution afresh before every source use.
    for function in (
        *context.methods.values(),
        *context.originals.values(),
        *(member for chain in context.logger_chains.values() for member in chain),
    ):
        previous._builtin_bindings(function)
    result = [
        context.parent_binding,
        context.electrical_parent,
        context.electrical_parent.trial,
        context.phase,
        context.sim,
        context.cells,
        context.p,
        context.handler,
        context.cache,
        context.entries,
        _REQUESTS,
        _CONSUMED,
        _RETIRED,
        _ISSUED,
        context.source_files,
    ]
    result.extend(_callback_bindings(context))
    result.extend(_logging_bindings(context))
    result.extend(previous.storage._molecule_runtime_bindings(context))
    result.extend(
        (*context.setters, *context.getters, context.call_tracing, *context.required_hooks)
    )
    result.extend(previous._callable_atoms(context, _account))
    for name, function in context.observer_refs:
        if context.observer_namespace.get(name) is not function:
            raise ValueError("Original observer helper namespace changed")
        result.extend(previous._callable_atoms(context, function))
    for function in (
        *context.methods.values(),
        *context.originals.values(),
        *context.sim_wrappers.values(),
        *context.callback_methods.values(),
        *(member for chain in context.logger_chains.values() for member in chain),
        *context.wrappers.values(),
        *(value for value in context.external.values() if value is not None),
    ):
        result.extend(previous._callable_atoms(context, function))
    for namespace, name, value in context.original_members:
        if namespace.get(name) is not value:
            raise ValueError("Original first-step global/helper changed: " + name)
        result.append(value)
    for namespace, retained in context.namespaces:
        if tuple(namespace) != tuple(name for name, _ in retained) or any(
            namespace[name] is not value for name, value in retained
        ):
            raise ValueError("Copied selected first-step globals changed")
        result.extend(value for _, value in retained)
    for facade, retained in context.facades:
        if tuple(vars(facade)) != tuple(name for name, _ in retained) or any(
            vars(facade)[name] is not value for name, value in retained
        ):
            raise ValueError("Reached original helper facade changed")
    for name, wrapper in context.sim_wrappers.items():
        if vars(type(context.sim)).get(name) is not wrapper:
            raise ValueError("Actual issued Simulator method wrapper changed")
    for cls, retained in context.class_surfaces:
        _same(previous.storage.previous.previous.previous._surface(cls), retained)
    if context.noop_object is not None:
        manager, cls, generator, enter, exit_, code = context.noop_object
        if (
            context.solver_context is not manager
            or type(manager) is not cls
            or vars(manager).get("gen") is not generator
            or generator.gi_code is not code
            or cls.__enter__ is not enter
            or cls.__exit__ is not exit_
        ):
            raise ValueError("Original solver context/generator links changed")
    for function in context.noop_methods:
        result.extend(previous._callable_atoms(context, function))
    return tuple(result)


def _check(context, *, closed=False):
    _bootstrap(context)
    if not closed:
        _guard(context)
    _check_parent(context.parent_binding)
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.electrical_owner) is not context
        or context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.sim
        or context.phase.dyna is not context.handler
        or context.phase.cache is not context.cache
        or context.parent_binding.check(context) is not context.electrical_parent
        or context.request.selection != SELECTION
        or context.request.identity != _digest(request_record(context.request))
    ):
        raise ValueError("Actual first-step owner/caller ancestry changed")
    _same(_binding(context), context.bindings)
    if _snapshot(context, stable=True).identity != context.stable.identity:
        raise ValueError("First-step work changed an unowned object/value")
    graph = _graph(context, stable=True)
    _same(graph[0], context.stable_graph[0])
    if graph[1] != context.stable_graph[1]:
        raise ValueError("First-step work changed an unowned alias/layout")
    if (
        tuple(value.identity for value in previous.storage.previous._streams(context.parent))
        != context.stream_ids
    ):
        raise ValueError("Ordinary INIT source or observer advanced original RNG")


def _source_row(context, frame):
    row = context.frames.get(id(frame)) if type(frame) is FrameType else None
    return row if row is not None and row["frame"] is frame and not row["returned"] else None


def _claim_wrapper(context, original, frame):
    """Claim before either an enter callback or actual dispatch can run."""
    context.last_wrapper_attempt = (frame, dict(frame.f_locals))
    context.wrapper_attempts.append(context.last_wrapper_attempt)
    _check(context)
    name = frame.f_locals.get("method")
    wrapper = context.sim_wrappers.get(name) if type(name) is str else None
    parent = _source_row(context, frame.f_back)
    expected = {
        "_plot_loop": ("setup",),
        "_run_sim_core_loop": ("setup",),
        "update_gj": ("_run_sim_core_loop",),
        "update_ecm": ("_run_sim_core_loop",),
        "update_intra": ("_run_sim_core_loop",),
        "ca_handler": ("_run_sim_core_loop",),
        "update_all_concs": ("_run_sim_core_loop",),
        "update_V": ("_run_sim_core_loop",),
        "write2storage": ("_run_sim_core_loop",),
        "_log_solver_time_estimate": ("_run_sim_core_loop",),
    }
    if (
        original is not context.initial
        or wrapper is None
        or frame.f_code is not wrapper.__code__
        or frame.f_globals is not wrapper.__globals__
        or parent is None
        or parent["name"] not in expected.get(name, ())
        or frame.f_locals.get("context") is not original
        or frame.f_locals.get("name") != "Simulator"
        or frame.f_locals.get("actual") is not context.sim
        or frame.f_locals.get("delegate")
        is not getattr(context.initial.factories["Simulator"], name)
        or id(frame) in context.wrapper_claims
    ):
        _reject(context, "Actual original same-Simulator body nesting required")
    for free, cell in zip(wrapper.__code__.co_freevars, wrapper.__closure__ or (), strict=True):
        if frame.f_locals.get(free) is not cell.cell_contents:
            _reject(context, "Original wrapper closure/frame changed")
    args, kwargs = frame.f_locals.get("args"), frame.f_locals.get("kwargs")
    if type(args) is not tuple or type(kwargs) is not dict:
        _reject(context, "Original wrapper argument holders required")
    context.wrapper_claims[id(frame)] = dict(
        frame=frame,
        name=name,
        parent=parent,
        args=args,
        kwargs=kwargs,
        refs=tuple(args),
        keywords=tuple(kwargs.items()),
        dispatched=False,
    )


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    _check(context)
    initial = previous.storage.previous.previous.previous
    wrapper = frame.f_back
    claim = context.wrapper_claims.get(id(wrapper))
    name = label.removeprefix("Simulator.")
    if (
        claim is None
        or claim["frame"] is not wrapper
        or claim["dispatched"]
        or name != claim["name"]
        or actual is not context.sim
        or original is not context.initial
        or frame.f_code is not initial._invoke.__code__
        or frame.f_globals is not vars(initial)
        or delegate is not getattr(original.factories["Simulator"], name)
        or wrapper.f_locals.get("args") is not claim["args"]
        or wrapper.f_locals.get("kwargs") is not claim["kwargs"]
        or len(args) != len(claim["refs"])
        or any(a is not b for a, b in zip(args, claim["refs"], strict=True))
        or tuple(kwargs.items()) != claim["keywords"]
    ):
        _reject(context, "Actual once-claimed first-step runtime dispatch required")
    claim["dispatched"] = True
    invocation = dict(
        name=name, frame=sys._getframe(), body=None, actual=actual, args=args, kwargs=kwargs
    )
    context.transport_frames.extend((frame, sys._getframe()))
    context.invocations.append(invocation)
    try:
        try:
            value = context.methods[name](actual, *args, **kwargs)
        except BaseException as error:
            if (
                error is not context.selected_stop
                or name != "_run_sim_core_loop"
                or context.stop_frame is not context.loop_frame
                or context.loop_visits != 2
                or context.entry_error is not None
            ):
                _source_error(context, invocation["body"], error)
                raise
            context.selected_stopped = context.iteration_complete = True
            context.last_loop_partial = (
                context.loop_frame,
                dict(context.loop_frame.f_locals),
                error,
            )
            # Raising from a trace removes that trace. Recovery is inline in
            # this already-entered boundary before any later source/callback.
            for index in (1, 0):
                try:
                    context.setters[index](context.observers[index])
                except BaseException as capture:
                    context.last_cleanup_error = ("selected_stop_restore", capture, index)
                    context.cleanup_errors += (context.last_cleanup_error,)
                    context.invalid = True
            safe = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as capture:
                        context.last_cleanup_error = ("selected_stop_sample", capture, index)
                        context.cleanup_errors += (context.last_cleanup_error,)
                        context.invalid = True
                safe.append(tuple(pair))
            context.stop_recovery = tuple(safe)
            if context.invalid or not all(
                a is context.observers[0] and b is context.observers[1] for a, b in safe
            ):
                _reject(context, "Required observers could not recover after selected stop")
            value = None
        context.last_method_return = (name, value)
        if name == "_plot_loop":
            context.calendar_raw = value  # Retain BEFORE any observation/check.
        if name == "_run_sim_core_loop" and not context.selected_stopped:
            context.loop_returned = True
        _check(context)
        return value
    finally:
        if context.invocations and context.invocations[-1] is invocation:
            context.invocations.pop()
        else:
            context.invalid = True


def _operation(context, name, args, kwargs, source_frame):
    _check(context)
    row = dict(
        name=name,
        source_frame=source_frame,
        args=args,
        kwargs=kwargs,
        frame=sys._getframe(),
        entered=False,
        returned=False,
        raw=None,
    )
    context.transport_frames.append(sys._getframe())
    context.last_helper = row
    context.helper_calls.append(row)
    caller = _source_row(context, source_frame)
    if caller is None or len(context.work) + len(context.helper_calls) > MAX_WORK:
        _reject(context, "Helper requires its actually admitted source frame")
    wrapper = sys._getframe(1)
    function = context.wrappers.get(name)
    if (
        function is None
        or wrapper.f_code is not function.__code__
        or wrapper.f_globals is not function.__globals__
        or wrapper.f_back is not source_frame
        or wrapper.f_locals.get("context") is not context
        or wrapper.f_locals.get("name") != name
        or wrapper.f_locals.get("args") is not args
        or wrapper.f_locals.get("kwargs") is not kwargs
    ):
        _reject(context, "Original helper wrapper frame/arguments required")
    if name in OPTIONAL_BRANCHES or name in ("animation_factory", "smooth_flux"):
        _reject(context, "Reached source branch requires unavailable native owner: " + name)
    delegate = context.methods.get(name, context.external.get(name))
    if delegate is None:
        _reject(context, "Unknown original helper")
    old = context.operation
    row["entered"], context.operation = True, row
    try:
        try:
            value = delegate(*args, **kwargs)
            context.last_helper_return = (row, value)
            row["raw"], row["returned"] = value, True
            if name == "noop_context":
                if type(value) is not context.noop_type:
                    _reject(context, "Original noop factory must return its actual context type")
                context.solver_context = value
                context.noop_frame = value.gen.gi_frame
                context.noop_object = (
                    value,
                    type(value),
                    value.gen,
                    type(value).__enter__,
                    type(value).__exit__,
                    value.gen.gi_code,
                )
                if value.gen.gi_code is not context.noop_generator.__code__:
                    _reject(context, "Actual original noop generator required")
        except BaseException as error:
            _source_error(context, source_frame, error)
            raise
    finally:
        context.operation = old
    _check(context)
    return value


def _admit(context, frame):
    old = context.frames.get(id(frame))
    if old is not None and old["frame"] is frame and not old["returned"]:
        return old
    name = context.body_names.get(frame.f_code)
    if frame.f_code in getattr(context, "molecule_codes", ()):
        name = "molecule_runtime"
    row = dict(
        frame=frame,
        code=frame.f_code,
        globals=frame.f_globals,
        name=name,
        body_started=False,
        returned=False,
        suspended=False,
    )
    context.last_attempt = row
    context.work.append(row)
    if (
        len(context.work) + len(context.helper_calls) > MAX_WORK
        or frame.f_code not in context.allowed_codes
    ):
        _reject(context, "Unselected original/raw source entry")
    _guard(context)
    if name == "setup":
        if (
            context.setup_frame is not None
            or frame.f_back is not context.driver_frame
            or frame.f_locals.get("self") is not context.sim
            or frame.f_locals.get("phase") is not context.phase
        ):
            _reject(context, "Once-only actual post-electrical caller slice required")
        context.setup_frame = frame
    elif name in SIM_METHODS:
        invocation = context.invocations[-1] if context.invocations else None
        if (
            invocation is None
            or invocation["name"] != name
            or invocation["body"] is not None
            or frame.f_back is not invocation["frame"]
            or frame.f_locals.get("self") is not context.sim
        ):
            _reject(context, "Native body has no exact runtime wrapper claim")
        invocation["body"] = frame
        if name == "_run_sim_core_loop":
            if context.loop_frame is not None:
                _reject(context, "Exactly one original loop invocation is permitted")
            context.loop_frame = frame
            context.time_steps = frame.f_locals.get("time_steps")
            context.sampled = frame.f_locals.get("time_steps_sampled")
            if (
                context.calendar_raw is None
                or context.time_steps is not context.calendar_raw[0]
                or context.sampled is not context.calendar_raw[1]
            ):
                _reject(context, "Original whole calendar/set must reach the native loop unchanged")
    elif name == "gj_run":
        caller = _source_row(context, frame.f_back)
        if (
            caller is None
            or caller["name"] != "update_gj"
            or frame.f_locals.get("self") is not context.gap
            or frame.f_locals.get("sim") is not context.sim
            or frame.f_locals.get("cells") is not context.cells
            or frame.f_locals.get("p") is not context.p
        ):
            _reject(context, "Actual issued GJ must run within original update_gj")
    elif name is not None and name.startswith("logger:"):
        _, method, position = name.split(":")
        position = int(position)
        chain = context.logger_chains[method]
        function = chain[position]
        operation = context.operation
        if (
            operation is None
            or operation["name"] != method
            or context.external.get(method) is not chain[0]
            or frame.f_code is not function.__code__
            or frame.f_globals is not function.__globals__
        ):
            _reject(context, "Actual original logging operation/callable required")
        if position == 0:
            if frame.f_back is not operation["frame"]:
                _reject(context, "Original logger wrapper detached from its helper operation")
        else:
            parent = _source_row(context, frame.f_back)
            if parent is None or parent["name"] != "logger:" + method + ":" + str(position - 1):
                _reject(context, "Original logger delegate has no exact wrapper parent")
        if position == len(chain) - 1:
            args, kwargs = operation["args"], operation["kwargs"]
            message = args[0] if args else kwargs.get("message")
            if frame.f_locals.get("message") is not message:
                _reject(context, "Original logger message/argument identity changed")
    elif name is not None and name.startswith("callback:"):
        _callback_enter(context, row)
    elif name == "logging_support":
        _logging_entry(context, row)
    elif name in ("solver_context_enter", "solver_context_exit"):
        parent = _source_row(context, frame.f_back)
        if (
            frame.f_locals.get("self") is not context.solver_context
            or parent is None
            or parent["name"] != "setup"
        ):
            _reject(context, "Original solver context belongs to the admitted caller only")
    elif name == "noop_context_generator":
        if frame is not context.noop_frame or context.noop_entries >= 2:
            _reject(context, "Actual original solver context generator required")
        caller = frame.f_back
        import contextlib

        expected = (
            contextlib._GeneratorContextManager.__enter__
            if context.noop_entries == 0
            else contextlib._GeneratorContextManager.__exit__
        )
        if (
            caller is None
            or caller.f_code is not expected.__code__
            or caller.f_globals is not expected.__globals__
            or caller.f_locals.get("self") is not context.solver_context
        ):
            _reject(context, "Original context enter/exit must own the generator resume")
        context.noop_entries += 1
    elif name == "molecule_runtime":
        # The actual child observer performs Key's source/owner admission
        # before either inherited hook can run. The later call delivery is
        # idempotent for this exact frame, not another runtime-body claim.
        context.observer_namespace["_observe"](context, frame, "call", None)
    elif name is not None:
        operation = context.operation
        if operation is None or operation["name"] != name or frame.f_back is not operation["frame"]:
            _reject(context, "Original source helper is detached from its claimed operation")
    elif _source_row(context, frame.f_back) is None:
        _reject(context, "Original nested comprehension has no admitted source parent")
    if (
        name is not None
        and name in context.methods
        and frame.f_globals is not context.methods[name].__globals__
    ):
        _reject(context, "Original selected source namespace changed")
    context.frames[id(frame)] = row
    row["body_started"] = True
    frame.f_trace_opcodes = True
    return row


def _loop_boundary(context, frame):
    if (
        frame is not context.loop_frame
        or frame.f_code is not context.loop_code
        or frame.f_lasti != context.loop_offset
    ):
        return
    context.loop_visits += 1
    if context.loop_visits == 2:
        context.source_time_label = frame.f_locals.get("t")
        context.stop_frame = frame
        context.stopping = True
        raise context.selected_stop
    if context.loop_visits != 1:
        _reject(context, "Selected original loop was entered more than once")


def _observe(context, frame, event, arg):
    if frame.f_code in getattr(context, "molecule_codes", ()):
        admitted = context.molecule_admissions.get(id(frame))
        returned = context.molecule_returns.get(id(frame))
        if (event != "call" or admitted is not frame) and (
            event != "return" or returned is not frame
        ):
            context.molecule.observe_runtime(
                context.molecule_claim, child=context, frame=frame, event=event, arg=arg
            )
            if event == "call":
                context.molecule_admissions[id(frame)] = frame
            elif event == "return":
                context.molecule_returns[id(frame)] = frame
        if event in ("call", "c_call", "c_return", "c_exception"):
            return
    if event == "call":
        _admit(context, frame)
    row = context.frames.get(id(frame))
    if row is None:
        return
    if event in ("call", "line"):
        # Profile-call admission can precede trace-call instrumentation. Arm
        # from the trace itself as well, before any original bytecode advances.
        frame.f_trace_opcodes = True
    if event == "opcode":
        _guard(context)
        _loop_boundary(context, frame)
    if event == "exception":
        if arg[1] is not context.selected_stop:
            protocol_stop = (
                row.get("name") == "solver_context_exit" and type(arg[1]) is StopIteration
            )
            if not protocol_stop:
                _pending_exception(context, frame, arg[1])
                context.last_source_error = (frame, arg[1])
    if event == "return" and not row["returned"]:
        context.last_raw = (frame, arg)
        error = context.pending.get(id(frame))
        normal = previous.storage.previous.previous.previous._normal_return(frame)
        if not normal and error is not None and error is not context.selected_stop:
            row["unwound_error"] = error
            if frame is getattr(context, "setup_frame", None):
                _source_error(context, frame, error)
        elif normal:
            row["handled_error"] = error
            context.pending.pop(id(frame), None)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
            row["returned"], row["suspended"] = True, name_is_yield(frame)
        except BaseException as capture:
            _capture(context, "return_or_unwind", capture, context.last_raw)
    if event == "line":
        _guard(context)
        if frame is context.setup_frame and "time_steps" in frame.f_locals:
            returned = context.calendar_raw
            if (
                type(returned) is not tuple
                or len(returned) != 3
                or frame.f_locals["time_steps"] is not returned[0]
                or frame.f_locals.get("time_steps_sampled") is not returned[1]
                or frame.f_locals.get("solver_context") is not returned[2]
                or returned[2] is not context.solver_context
            ):
                _reject(context, "Original calendar/sample/context return lineage changed")


def name_is_yield(frame):
    return any(
        item.offset == frame.f_lasti and item.opname in ("YIELD_VALUE", "YIELD_FROM")
        for item in dis.get_instructions(frame.f_code)
    )


def _observer_recipe(context):
    original = previous.storage.previous.previous
    initial = previous.storage.previous.previous.previous
    namespace = dict(
        vars(original),
        previous=initial,
        DynamicsRejected=FirstStepRejected,
        _guard=_guard,
        _check=_check,
        _reject=_reject,
        _observe=_observe,
        _epoch=_epoch,
        _ACTIVE=_ACTIVE,
        MAX_WORK=MAX_WORK,
    )
    for name in (
        "_record_capture",
        "_witness",
        "_delegate",
        "_same_epoch",
        "_recover_hooks",
    ):
        function = vars(original)[name]
        namespace[name] = FunctionType(
            function.__code__, namespace, name, function.__defaults__, function.__closure__
        )
    namespace["_inherited"] = _inherited
    context.observer_namespace = namespace
    context.observer_refs = tuple(
        (name, namespace[name])
        for name in (
            "_record_capture",
            "_witness",
            "_delegate",
            "_same_epoch",
            "_inherited",
            "_recover_hooks",
        )
    )


def _inherited(context, observer, frame, event, arg):
    if observer is None:
        return None
    if context.inherited:
        _reject(context, "Reentrant inherited first-step observer")
    prior_failure = getattr(context, "first_failure", None)
    before = _epoch(context)
    context.inherited = True
    failed = None
    try:
        return context.call_tracing(
            context.observer_namespace["_delegate"], (observer, frame, event, arg)
        )
    except BaseException as error:
        failed = error
        _pending_observer_abort(context, frame, event, prior_failure)
        context.last_observer_error = (frame, event, error)
        try:
            context.observer_errors += (error,)
        except BaseException as capture:
            context.observer_error_journal_failure = (capture, error)
        try:
            _capture(context, "inherited_observer", error, (frame, event, arg))
        except BaseException as capture:
            context.capture_entry_error = (capture, error, frame, event)
            if context.capture_error is None:
                context.capture_error = error
        raise
    finally:
        context.inherited = False
        try:
            context.observer_namespace["_same_epoch"](context, before)
        except BaseException as error:
            _pending_observer_abort(context, frame, event, prior_failure)
            try:
                _capture(context, "inherited_epoch", error, (frame, event, arg))
            except BaseException as capture:
                context.epoch_capture_error = (capture, error, failed)
            if failed is None and _primary(context) is None:
                raise


@contextmanager
def _account(context):
    """Common call admission precedes BOTH inherited hook deliveries."""
    prior_profile, prior_trace = context.required_hooks
    local = {}
    inherited = context.observer_namespace["_inherited"]

    def before(frame, event):
        selected = frame.f_code in context.allowed_codes
        if (
            context.body_names.get(frame.f_code) in ("solver_context_enter", "solver_context_exit")
            and frame.f_locals.get("self") is not context.solver_context
        ):
            selected = False
        native = frame.f_code.co_filename.startswith(str(NATIVE) + os.sep)
        if context.inherited:
            if event == "call" and (selected or native):
                _reject(context, "Inherited observer attempted raw first-step source")
            return None
        if event == "call" and (selected or native):
            try:
                _admit(context, frame)
            except BaseException as error:
                if not _is_observer_error(context, error) and error is not context.primary:
                    _admission_error(context, error, (frame, event))
                primary = _primary(context)
                if primary is None or primary is error:
                    raise
                raise primary from primary.__cause__
        if event == "call" and (
            context.operation is not None or _source_row(context, frame.f_back) is not None
        ):
            try:
                _same(_binding(context), context.bindings)
            except BaseException as error:
                _admission_error(context, error, (frame, event))
                primary = _primary(context)
                if primary is error:
                    raise
                raise primary from primary.__cause__
        return selected or native

    def after(selected, event, raw):
        if selected:
            prior_failure = getattr(context, "first_failure", None)
            try:
                _guard(context)
                _same(_binding(context), context.bindings)
                row = context.frames.get(id(raw[0]))
                if row is not None:
                    _callback_frame(context, row)
                    _logging_frame(context, row)
            except BaseException as error:
                _pending_observer_abort(context, raw[0], event, prior_failure)
                if not _is_observer_error(context, error) and error is not context.primary:
                    _admission_error(context, error, raw)
                if event not in ("return", "c_return", "c_exception") or _primary(context) is None:
                    raise
                if error is _primary(context):
                    return
                try:
                    _capture(context, "post_return_authority", error, raw)
                except BaseException as capture:
                    context.deferred_capture_entry_error = (capture, error, raw)

    def profile(frame, event, arg):
        if (
            event == "return"
            and frame is context.stop_frame
            and getattr(context, "stopping", False)
        ):
            # A trace-raised selected stop clears that hook before profile
            # return delivery. Recover here, before any guard or callback.
            for index in (1, 0):
                try:
                    context.setters[index](context.observers[index])
                except BaseException as error:
                    context.last_cleanup_error = ("stop_profile_restore", error, index)
                    context.cleanup_errors += (context.last_cleanup_error,)
                    context.invalid = True
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as error:
                        context.last_cleanup_error = ("stop_profile_sample", error, index)
                        context.cleanup_errors += (context.last_cleanup_error,)
                        context.invalid = True
                samples.append(tuple(pair))
            context.stop_profile_recovery = tuple(samples)
            if context.invalid or not all(
                a is context.observers[0] and b is context.observers[1] for a, b in samples
            ):
                _reject(context, "Selected-stop observer recovery failed before profile delivery")
        selected = before(frame, event)
        if selected is None:
            return
        row = context.frames.get(id(frame))
        if event in ("c_call", "c_return", "c_exception") and row is not None:
            if frame.f_code in context.molecule_codes:
                _observe(context, frame, event, arg)
            context.last_c_call = (frame, event, arg)
            if event == "c_call":
                context.c_calls.append(context.last_c_call)
                if len(context.work) + len(context.c_calls) > MAX_WORK:
                    _reject(context, "Bounded source/C work ledger exhausted")
        if event == "return" and row is not None:
            _observe(context, frame, event, arg)
        try:
            _callback_event(context, row, event, arg, "profile")
        except BaseException as error:
            context.last_callback_observation_error = (error, frame, event, arg, "profile")
            if not _is_observer_error(context, error) and error is not _primary(context):
                _capture(context, "callback_profile_capture", error, (frame, event, arg))
            if event != "return" or _primary(context) is None:
                raise
        try:
            inherited(context, prior_profile, frame, event, arg)
        except BaseException as error:
            _capture(context, "inherited_profile", error, (frame, event, arg))
            if (
                event not in ("exception", "return", "c_return", "c_exception")
                or _primary(context) is None
            ):
                raise
        after(selected, event, (frame, event, arg))

    def trace(frame, event, arg):
        selected = before(frame, event)
        if selected is None:
            return trace
        if selected:
            try:
                _observe(context, frame, event, arg)
                _callback_event(context, context.frames.get(id(frame)), event, arg, "trace")
            except BaseException as error:
                if error is context.selected_stop:
                    raise
                if error is not context.entry_error and error is not _primary(context):
                    _capture(context, "source_observer", error, (frame, event, arg))
                if event not in ("exception", "return") or _primary(context) is None:
                    raise
        observer = prior_trace if event == "call" else local.get(id(frame))
        try:
            returned = inherited(context, observer, frame, event, arg)
            if callable(returned):
                local[id(frame)] = returned
        except BaseException as error:
            _capture(context, "inherited_trace", error, (frame, event, arg))
            if event not in ("exception", "return") or _primary(context) is None:
                raise
        finally:
            if event == "return":
                local.pop(id(frame), None)
        after(selected, event, (frame, event, arg))
        return trace

    context.observers = profile, trace
    context.observer_code_binding = tuple(
        (function, function.__code__, function.__globals__, function.__closure__)
        for function in context.observers
    )
    try:
        context.setters[0](profile)
        context.setters[1](trace)
        if context.getters[0]() is not profile or context.getters[1]() is not trace:
            raise ValueError("Both first-step observers must be installed")
        context.observing = True
        yield
    except BaseException as error:
        primary = _primary(context)
        if primary is None:
            primary = error
        context.failure_error = primary
        if error is not primary:
            context.last_secondary = (error, primary)
            raise primary from primary.__cause__
        raise
    finally:
        context.observing = False
        # Independent inline actions: no helper-entry callback can suppress a
        # second restore, final sampling, or the original source exception.
        for index in (1, 0):
            try:
                context.setters[index](context.required_hooks[index])
            except BaseException as error:
                context.last_cleanup_error = ("terminal_restore", error, index)
                try:
                    context.cleanup_errors += (context.last_cleanup_error,)
                except BaseException as capture:
                    context.cleanup_journal_error = (capture, error)
        samples = []
        for order in ((0, 1), (1, 0)):
            pair = [None, None]
            for index in order:
                try:
                    pair[index] = context.getters[index]()
                except BaseException as error:
                    context.last_cleanup_error = ("terminal_sample", error, index)
                    try:
                        context.cleanup_errors += (context.last_cleanup_error,)
                    except BaseException as capture:
                        context.cleanup_journal_error = (capture, error)
            samples.append(tuple(pair))
        context.final_hooks = tuple(samples)
        context.hooks_safe = all(
            a is context.required_hooks[0] and b is context.required_hooks[1] for a, b in samples
        )


def _ancestry(context):
    initial = previous.storage.previous.previous.previous
    modules = (
        (initial, context.initial),
        (previous.storage.previous.previous, context.parent.parent),
        (previous.storage.previous, context.parent),
        (previous.storage, context.storage_parent),
        (previous, context.electrical_parent),
    )
    edges = list(context.initial.seed_lease.edges)
    edges.extend(initial._seed_edge_records(module, value) for module, value in modules)
    context.ancestor_edges = tuple(edges)
    context.ancestor_files = tuple(
        (Path(module.__file__), hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest())
        for module, _ in modules
    )
    context.ancestor_functions = tuple(
        (module, name, function, previous._callable_atoms(context, function))
        for module, _ in modules
        for name, function in vars(module).items()
        if type(function) is FunctionType and function.__globals__ is vars(module)
    )


def _check_ancestor_metadata(context):
    """New factored epoch; no pre-step numerical parent validator is called."""
    _bootstrap(context)
    if (
        context.thread != get_ident()
        or context.invalid
        or not context.claimed
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or _RETIRED.get(context.request.electrical_owner) is not context
        or previous._FORWARDED.get(context.request.electrical_owner) is not context
        or context.electrical_parent is not context.refs[0]
        or context.electrical_parent.trial is not context.refs[1]
    ):
        raise ValueError("Actual one-shot electrical/first-step ancestry changed")
    previous.storage.previous.previous.previous.core._check_profile_ancestor_edges(
        SimpleNamespace(edges=context.ancestor_edges)
    )
    for path, pin in context.ancestor_files:
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise ValueError("Original retained ancestor source changed")
    for module, name, function, retained in context.ancestor_functions:
        if vars(module).get(name) is not function:
            raise ValueError("Original retained ancestor helper replaced")
        _same(previous._callable_atoms(context, function), retained)
    _same(_binding(context), context.bindings)
    return context.electrical_parent


def _context(request, refs):
    parent = refs[0]
    context = previous._context(parent.request, parent.refs)
    context.request, context.refs, context.electrical_parent = request, refs, parent
    context.initial = context.parent.init_parent
    context.stage = "first_step_retirement"
    context.claimed = False
    context.source_error = context.source_chain = context.first_failure = None
    context.exception_origins, context.exception_events = {}, []
    context.observer_errors = ()
    context.capture_stop = None
    context.stopping = False
    context.objects, context.permissions = (), ()
    context.molecule, context.molecule_claim, context.molecule_record = None, None, None
    context.molecule_permissions, context.molecule_codes = (), frozenset()
    context.molecule_admissions = {}
    context.molecule_returns = {}
    context.source_files = {}
    context.callback_nodes = {}
    context.callback_methods = {}
    context.callback_owner = context.callback_type = context.callback_mro = None
    context.callback_chains, context.callback_lookups, context.callback_sites = {}, {}, {}
    context.callback_claimed_sites, context.callback_roots = set(), set()
    context.callback_calls = []
    context.log_configuration = None
    context.log_support, context.log_protocol, context.log_module_members, context.log_surfaces = (
        (),
        (),
        (),
        (),
    )
    context.log_support_codes = {}
    context.log_closed_epoch = None
    context.original_members, context.class_surfaces = (), ()
    context.wrapper_attempts, context.wrapper_claims = [], {}
    context.invocations = []
    context.transport_frames = []
    context.setup_frame = context.loop_frame = None
    context.loop_code = context.loop_offset = None
    context.loop_visits = 0
    context.selected_stop = _SelectedStop("selected first ordinary INIT iteration complete")
    context.stop_frame = None
    context.selected_stopped = context.iteration_complete = context.loop_returned = False
    context.calendar_raw = context.time_steps = context.sampled = None
    context.source_time_label = None
    context.solver_context = context.noop_frame = None
    context.noop_object = None
    context.noop_entries = 0
    context.stream_ids = tuple(
        value.identity for value in previous.storage.previous._streams(context.parent)
    )
    return context


def trial_record(trial):
    return dict(
        request=trial.request_identity,
        parent=trial.parent_identity,
        before=trial.before.identity,
        after=trial.after.identity,
        calendar=trial.calendar.identity,
        sampled=trial.sampled.identity,
        t=trial.source_time_label.identity,
        dt=trial.configured_dt.identity,
        index=trial.loop_index,
        complete=trial.iteration_complete,
        loop_returned=trial.loop_returned,
        selected_stop=trial.selected_stop,
        work=tuple(
            (
                row["code"].co_filename,
                row["code"].co_firstlineno,
                row["body_started"],
                row["returned"],
            )
            for row in trial.work
        ),
        helpers=tuple((row["name"], row["entered"], row["returned"]) for row in trial.helper_calls),
        callbacks=tuple(
            (
                claim["name"],
                len(claim["chain"]),
                tuple(claim["return_order"]),
                claim["complete"],
                claim["error"] is None,
            )
            for claim in trial.callback_calls
        ),
        rng_before=trial.stream_before,
        rng_after=trial.stream_after,
    )


def _run(context):
    context.driver_frame = sys._getframe()
    context.transport_frames.append(context.driver_frame)
    return context.methods["setup"](context.sim, context.phase)


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise FirstStepRejected("Actual first-step source remains held", stage="release")
    binding = _ready()
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], "Reentrant first-step preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise FirstStepRejected("Actual issued first-step Request required", stage="request")
        if request in _CONSUMED or request.electrical_owner in _RETIRED:
            raise FirstStepRejected("Electrical epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = previous._authority(request.electrical_owner)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or previous._snapshot(parent).identity != refs[2].identity
        ):
            raise FirstStepRejected(
                "Original electrical values changed before retirement", stage="parent"
            )
        graph = previous._graph(parent)
        _same(graph[0], refs[3][0])
        if graph[1] != refs[3][1] or request.source_identity != _digest(source_plan()):
            raise FirstStepRejected(
                "Original electrical/source reference graph changed", stage="parent"
            )
        context = _context(request, refs)
        context.atoms, context.checker = context.initial.atoms, context.initial.checker
        context.metadata = tuple(
            (name, function, previous._callable_atoms(context, function))
            for name, function in globals().items()
            if type(function) is FunctionType and function.__globals__ is globals()
        )
        context.parent_binding = binding
        context.entries = MappingProxyType(dict(wrapper_guard=_claim_wrapper, dispatch=_dispatch))
        _CONSUMED[request] = _RETIRED[request.electrical_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            _check_parent(binding)
            if (
                binding.claim(
                    request.electrical_owner,
                    expected=refs[1],
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different original electrical parent")
            _check_parent(binding)
            context.claimed = True
            _namespace(context)
            previous.storage._bind_molecule_runtime(context, kind="first_step")
            context.permissions = previous.storage._merge_permissions(
                context.permissions, context.molecule_permissions
            )
            _domain(context)
            _ancestry(context)
            _observer_recipe(context)
            context.bindings = _binding(context)
            context.before, context.stable = _snapshot(context), _snapshot(context, stable=True)
            context.stable_graph = _graph(context, stable=True)
            # Any proof/publication observer must leave the still-unrun full
            # electrical epoch untouched; no excluded-field rebasing occurs.
            if previous._snapshot(parent).identity != refs[2].identity:
                raise ValueError("Source state changed while first-step authority sealed")
            graph = previous._graph(parent)
            _same(graph[0], refs[3][0])
            if graph[1] != refs[3][1]:
                raise ValueError("Source aliases changed before first-step body entry")
            context.stage = "original_calendar_and_one_FULL_INIT_iteration"
            with _account(context):
                _run(context)
            _check(context)
            _callbacks_complete(context)
            if (
                not context.iteration_complete
                or context.primary is not None
                or context.capture_error is not None
            ):
                raise FirstStepRejected(
                    "Selected native iteration did not complete", stage="sealing", partial=context
                )
            if context.molecule_claim is not None:
                context.molecule_record = context.molecule.finish_runtime(
                    context.molecule_claim, child=context
                )
            if (
                context.calendar_raw is None
                or context.time_steps is not context.calendar_raw[0]
                or context.sampled is not context.calendar_raw[1]
            ):
                raise ValueError("Original returned calendar/set no longer retained")
            context.after, context.after_graph = _snapshot(context), _graph(context)
            context.log_closed_epoch = _logging_epoch(context)
            scope = previous.storage.previous._scope(context.parent)
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                scope.snapshot(context.time_steps),
                scope.snapshot(tuple(context.sampled)),
                scope.snapshot(context.source_time_label),
                scope.snapshot(context.p.dt),
                0,
                True,
                context.loop_returned,
                context.selected_stopped,
                tuple(context.work),
                tuple(context.helper_calls),
                tuple(context.stores),
                tuple(context.raw_returns),
                tuple(context.callback_calls),
                context.stream_ids,
                tuple(
                    value.identity for value in previous.storage.previous._streams(context.parent)
                ),
                "",
            )
            context.trial = replace(value, identity=_digest(trial_record(value)))
        except BaseException as error:
            primary = _primary(context)
            if primary is None:
                primary = error
            context.invalid, context.failure_error = True, primary
            try:
                _FAILED.append(context)
            except BaseException as capture:
                context.retention_error = (capture, primary, context)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
            for index in (1, 0):
                try:
                    context.setters[index](context.required_hooks[index])
                except BaseException as capture:
                    context.last_cleanup_error = ("prepare_restore", capture, index)
                    try:
                        context.cleanup_errors += (context.last_cleanup_error,)
                    except BaseException as secondary:
                        context.cleanup_journal_error = (secondary, capture)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as capture:
                        context.last_cleanup_error = ("prepare_sample", capture, index)
                        context.cleanup_errors += (context.last_cleanup_error,)
                samples.append(tuple(pair))
            context.final_hooks = tuple(samples)
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise FirstStepRejected(
                "Original selected first-step attempt failed",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=context,
            ) from primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            raise FirstStepRejected(
                "First-step closure incomplete",
                stage="closure",
                request=request,
                trial=context.trial,
                partial=context,
            )
        owner = object.__new__(FirstStepOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


class FirstStepOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only a sealed actual selected iteration issues an owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("No ordinary checkpoint or supplied-state admission")

    @property
    def phase(self):
        return _authority(self).phase

    @property
    def trial(self):
        return _authority(self).trial


def _authority(owner):
    if type(owner) is not FirstStepOwner or owner not in _ISSUED:
        raise FirstStepRejected("Actual issued first-step owner required", stage="owner")
    context, trial = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        context.invalid = True
        raise FirstStepRejected(
            "First-step epoch unavailable/reentrant", stage="owner", partial=context
        )
    context.validating = True
    try:
        _ready()
        _check(context, closed=True)
        _callbacks_complete(context)
        _same(tuple(context.callback_calls), trial.callback_calls)
        if (
            trial is not context.trial
            or trial.identity != _digest(trial_record(trial))
            or _snapshot(context).identity != trial.after.identity
        ):
            raise ValueError("Closed first-step source record/value changed")
        graph = _graph(context)
        _same(graph[0], context.after_graph[0])
        if graph[1] != context.after_graph[1]:
            raise ValueError("Closed first-step alias graph changed")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False
