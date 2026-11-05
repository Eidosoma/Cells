"""Held actual INIT -> fresh SIM constructor, with one retained-store change.

Fresh native import provenance must be observed before acquiring INIT. No
receipt, decoded cache or supplied phase can replace the two actual owners.
The endpoint is before sim_info_report/run_sim_core, not a SIM iteration.
"""

import ast
import dis
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import ProxyTypes, WeakKeyDictionary

from cells.processes import betse_native_init_molecule_wrapper_authority as wrappers
from cells.processes import betse_native_init_sim_assembly_source as source
from cells.processes import betse_native_init_sim_preparation as preparation
from cells.processes import betse_native_init_terminal as terminal

timing = preparation.timing
LAW_ID = "actual_completed_INIT_retained_sim_cells_fresh_SIM_constructor@1"
RELEASE = "CELLS_NATIVE_INIT_SIM_ASSEMBLY_RELEASED"
PREPARATION_SHA256 = TERMINAL_SHA256 = TIMING_SHA256 = None
PREPARATION_REVIEW_SHA256 = TERMINAL_REVIEW_SHA256 = TIMING_REVIEW_SHA256 = None
WRAPPER_SHA256 = "504ceb66c9be9b4b9f963e4cc95abbafe285a90e1b837fbf3d62b81dc654d56f"
MAX_WORK = 100000
MAX_IMPORT_FACTORIES = 512
_LOCK, _ACTIVE, _FAILED = RLock(), [], []
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_IMPORTS, _IMPORT_ACTIVE, _IMPORT_FAILED = WeakKeyDictionary(), [], []
_IMPORT_API = None
_RUN_RESERVATIONS, _RUN_RETIRED = WeakKeyDictionary(), WeakKeyDictionary()
RUN_RESERVATION_LAW = "actual_SIM_constructor_one_shot_original_run_retirement@1"
RUN_RESERVATION_RELEASE = "CELLS_NATIVE_SIM_RUN_RETIREMENT_RELEASED"


class AssemblyRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None):
        super().__init__(reason)
        self.stage, self.partial = stage, partial


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    preparation_owner: object
    preparation_identity: str
    terminal_identity: str
    parameters_identity: str
    source_identity: str
    metadata_work: tuple

    def __reduce_ex__(self, protocol):
        raise TypeError("Live SIM assembly requests cannot be hydrated")


@dataclass(frozen=True, slots=True)
class Trial:
    source_identity: str
    preparation_identity: str
    terminal_identity: str
    parameters_identity: str
    phase_parameter_record: object
    bindings: tuple
    work: tuple
    metadata_work: tuple
    rng_before: tuple
    rng_after: tuple
    constructor_completed: bool
    endpoint: str
    identity: str
    constructor_state: object


def _digest(value):
    return preparation._digest(value)


def source_plan():
    return dict(
        law=LAW_ID,
        original=source.source_plan(),
        max_work=MAX_WORK,
        max_import_factories=MAX_IMPORT_FACTORIES,
        producers=(PREPARATION_SHA256, TERMINAL_SHA256, TIMING_SHA256),
        reviews=(PREPARATION_REVIEW_SHA256, TERMINAL_REVIEW_SHA256, TIMING_REVIEW_SHA256),
        input="actual successful SimPreparationOwner; genuine completed INIT and fresh current p",
        sole_retained_mutation="sim.dyna -> actual returned fresh SIM TissueHandler",
        one_shot_terminal_retirement=True,
        endpoint="after_SIM_constructor_before_sim_info_report_and_run_sim_core",
        SIM_iterations_or_checkpoint_continuity=False,
        native_pickle_loadSim_or_autoInit_admission=False,
        numerical_execution_held=True,
    )


def _ready():
    for module, pin, review in (
        (preparation, PREPARATION_SHA256, PREPARATION_REVIEW_SHA256),
        (terminal, TERMINAL_SHA256, TERMINAL_REVIEW_SHA256),
        (timing, TIMING_SHA256, TIMING_REVIEW_SHA256),
    ):
        if not preparation._pin(pin) or not preparation._pin(review):
            raise AssemblyRejected(
                "Exact reviewed constructor/terminal producers held", stage="producer_review_held"
            )
        path = Path(module.__file__)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != pin:
            raise AssemblyRejected("Current exact producer required", stage="producer")
    return True


def _phase_import_api():
    """Reuse the actual observer in a private, explicitly scoped namespace."""
    global _IMPORT_API
    if _IMPORT_API is None:
        path = Path(wrappers.__file__)
        payload = path.read_bytes()
        if hashlib.sha256(payload).hexdigest() != WRAPPER_SHA256:
            raise AssemblyRejected("Exact import observer required", stage="import_producer")
        names = tuple(n.name for n in ast.parse(payload).body if isinstance(n, ast.FunctionDef))
        terminal.base.previous.interfaces._source_interface(
            wrappers, payload, path, names, contextmanagers=("observing_native_imports",)
        )
        sites = source.import_sites()
        pins = {path: source.PINS[path] for path in set(sites.values())}
        base_api = preparation._wrapper_api()
        namespace = dict(
            base_api,
            network=SimpleNamespace(
                NATIVE=source.NATIVE, SITES=sites, PINS=pins, code=source.import_code
            ),
            channels=SimpleNamespace(SITES={}, PINS={}),
            _ISSUED=_IMPORTS,
            _ACTIVE=_IMPORT_ACTIVE,
            _FAILED=_IMPORT_FAILED,
            LAW=LAW_ID + ":fresh_phase_import",
            RELEASE=RELEASE,
            MAX_FACTORIES=MAX_IMPORT_FACTORIES,
        )
        functions = []
        for name, function in base_api.items():
            if type(function) is FunctionType and function.__globals__ is base_api:
                copied = FunctionType(
                    function.__code__,
                    namespace,
                    function.__name__,
                    function.__defaults__,
                    function.__closure__,
                )
                copied.__kwdefaults__ = function.__kwdefaults__
                namespace[name] = copied
                functions.append((name, copied, function))
        body = base_api["observing_native_imports"].__wrapped__
        copied = FunctionType(
            body.__code__, namespace, body.__name__, body.__defaults__, body.__closure__
        )
        copied.__kwdefaults__ = body.__kwdefaults__
        namespace["observing_native_imports"] = contextmanager(copied)
        _IMPORT_API = (
            namespace,
            tuple(namespace.items()),
            sites,
            tuple(pins.items()),
            tuple(functions),
            copied,
            body,
        )
    namespace, items, sites, pins, functions, watched, original = _IMPORT_API
    base_api = preparation._wrapper_api()
    if (
        tuple(namespace) != tuple(k for k, _ in items)
        or any(namespace[k] is not v for k, v in items)
        or namespace["network"].SITES != source.import_sites()
        or tuple(namespace["network"].PINS.items()) != pins
        or namespace["network"].code is not source.import_code
        or watched.__code__ is not original.__code__
        or watched.__globals__ is not namespace
        or base_api["observing_native_imports"].__wrapped__ is not original
    ):
        raise AssemblyRejected("Original scoped import namespace changed", stage="import_producer")
    for name, copied, original in functions:
        if (
            base_api[name] is not original
            or copied.__code__ is not original.__code__
            or copied.__globals__ is not namespace
            or copied.__defaults__ is not original.__defaults__
            or copied.__kwdefaults__ is not original.__kwdefaults__
            or copied.__closure__ is not original.__closure__
            or copied.__builtins__ is not original.__builtins__
        ):
            raise AssemblyRejected(
                "Original scoped import observer function changed", stage="import_producer"
            )
    return namespace


@contextmanager
def observing_phase_import(*, enabled=False):
    """Wrap existing original import before INIT acquisition; never replay it."""
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise AssemblyRejected("Actual native import work held", stage="release")
    _ready()
    with _phase_import_api()["observing_native_imports"](enabled=True) as proof:
        yield proof


def _native():
    native = timing._native()
    fields = vars(native.cls)
    if any(
        n in fields
        for n in (
            "__getattribute__",
            "__getattr__",
            "__setattr__",
            "__delattr__",
            "p",
            "sim",
            "cells",
            "kind",
            "dyna",
            "cache",
            "callbacks",
            "export_dirname",
        )
    ):
        raise AssemblyRejected("Original phase assignment surface required", stage="runtime")
    api = _phase_import_api()
    for role, name in (
        ("phase", "__init__"),
        ("phase_kludge", "_init_kludge"),
        ("phase_time", "_init_kludge_time"),
    ):
        original = native.methods[name]
        if preparation.observation._code(original.__code__) != preparation.observation._code(
            source.code(role)
        ):
            raise AssemblyRejected("Original complete phase body required", stage="runtime")
        api["validate"](vars(native.cls)[name], original, owner=native.cls, attribute=name)
    return native


def from_preparation(owner, *, law_id):
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise AssemblyRejected("Concurrent assembly declaration", stage="reentrant")
        if type(law_id) is not str or law_id != LAW_ID:
            raise AssemblyRejected("Exact SIM assembly law required", stage="law")
        _ready()
        if type(owner) is not preparation.SimPreparationOwner or owner not in preparation._ISSUED:
            raise AssemblyRejected(
                "Actual successful runner preparation required", stage="preparation"
            )
        metadata = SimpleNamespace(metadata_work=[])
        parent = _metadata(
            metadata,
            "actual_runner_INIT_and_current_parameters_verification",
            preparation._authority,
            owner,
        )
        value = Request(
            owner,
            parent.trial.identity,
            parent.parent.trial.identity,
            parent.current.record.identity,
            _digest(source_plan()),
            tuple(metadata.metadata_work),
        )
        _REQUESTS[value] = (parent, parent.trial, parent.parent.trial, parent.current.record)
        return value


def _metadata(context, label, function, *args, **kwargs):
    row = dict(sequence=len(context.metadata_work), call=label, status="entered")
    context.metadata_work.append(row)
    try:
        result = function(*args, **kwargs)
    except BaseException:
        row["status"] = "failed"
        raise
    row["status"] = "returned"
    return result


def _retained_view(parent):
    # Observation facade only: the original live p, phase, sim, cells and
    # participant roots remain identical. Only sim.dyna is separately proved.
    view = SimpleNamespace(**vars(parent))
    view.permissions = ((parent.sim, frozenset(("dyna",))),)
    view.graph_fields = [{} for _ in parent.objects]
    view.graph_view = SimpleNamespace(objects=parent.objects, fields=view.graph_fields)
    return view


def _retained_state(context):
    parent, trial = terminal._sim_reservation(context.reservation)
    if parent is not context.parent or trial is not context.refs[2]:
        raise ValueError("Original completed INIT reservation changed")
    parent.runtime["_bootstrap"](parent)
    terminal._closed_protocol(parent, trial)
    value = terminal._snapshot(context.retained_view, stable=True)
    graph = parent.runtime["_graph"](context.retained_view, stable=True)
    streams = terminal.base.previous.storage.previous._streams(parent.parent)
    return value, graph, streams


def _check_retained(context):
    actual = _metadata(
        context, "actual_retained_state_alias_calendar_RNG_verification", _retained_state, context
    )
    if actual[0].identity != context.retained_before[0].identity:
        raise ValueError("Retained material/clock/field/network state changed outside sim.dyna")
    terminal.base._same(actual[1][0], context.retained_before[1][0])
    if actual[1][1] != context.retained_before[1][1] or tuple(
        v.identity for v in actual[2]
    ) != tuple(v.identity for v in context.retained_before[2]):
        raise ValueError("Retained aliases/layout/full RNG changed")
    return actual


def _check(context):
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
        or _REQUESTS.get(context.request) is not context.refs
        or context.refs[0] is not context.prepared
        or context.prepared.parent is not context.parent
        or context.prepared.current is not context.current
        or context.prepared.trial is not context.refs[1]
        or context.parent.trial is not context.refs[2]
        or context.current.record is not context.refs[3]
        or context.request.preparation_identity != context.refs[1].identity
        or context.request.terminal_identity != context.refs[2].identity
        or context.request.parameters_identity != context.refs[3].identity
        or context.request.source_identity != _digest(source_plan())
    ):
        raise ValueError("Original assembly epoch/source changed")
    _check_retained(context)
    if context.parent.sim.dyna is not context.original_handler:
        phase = context.phase
        if (
            phase is None
            or type(phase) is not context.native.cls
            or phase.p is not context.current.p
            or phase.sim is not context.parent.sim
            or phase.cells is not context.parent.cells
            or phase.kind is not context.native.enum.SIM
            or phase.callbacks is not context.parent.phase.callbacks
            or phase.dyna is not context.parent.sim.dyna
        ):
            raise ValueError("Only the original fresh SIM handler can replace sim.dyna")
        if context.handler_write is None:
            raise ValueError("Actual native sim.dyna source write witness required")


def _metadata_guard(context):
    """Source/exclusion guards inside a constructor, not cached state admission.

    Full live value/layout/alias/RNG verification occurs at semantic entry,
    return and later public use. Source instruction checks permit only the
    actual retained-store assignment; they never replace those fresh checks.
    """
    if (
        context.invalid
        or context.thread != get_ident()
        or _CONSUMED.get(context.request) is not context
    ):
        raise ValueError("Original active constructor epoch required")
    if sys.modules.get(context.native.module.__name__) is not context.native.module:
        raise ValueError("Original native phase module changed")
    for cls in (context.native.cls, type(context.parent.sim)):
        if (
            type(cls) is not type
            or cls.__bases__ != (object,)
            or any(
                name in vars(cls)
                for name in (
                    "__new__",
                    "__getattribute__",
                    "__getattr__",
                    "__setattr__",
                    "__delattr__",
                    "__slots__",
                    "dyna",
                )
            )
        ):
            raise ValueError("Original phase/retained Simulator attribute dispatch required")
    if any(name in vars(context.native.cls) for name in timing.PHASE_FIELDS):
        raise ValueError("Original native phase field descriptor surface required")
    api = _phase_import_api()
    for name, original in context.native.methods.items():
        api["validate"](
            vars(context.native.cls)[name], original, owner=context.native.cls, attribute=name
        )
    terminal._sim_reservation(context.reservation)


def _observe(context, frame, event, arg):
    native_frame = frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep)
    role = context.roles.get(frame.f_code)
    if not native_frame and role is None and frame.f_code not in context.wrapper_codes:
        return
    if event == "call":
        frame.f_trace_opcodes = True
        _nested_entry(context, frame)
        if context.admitted.get(id(frame)) is frame:
            return
        context.admitted[id(frame)] = frame
    if (native_frame or frame.f_code in context.wrapper_codes) and event == "call":
        if len(context.work) >= MAX_WORK:
            raise AssemblyRejected(
                "Declared actual constructor work exhausted", stage="work", partial=context
            )
        context.work.append((frame, frame.f_code, frame.f_globals))
        if frame.f_code is source.code("simulator") or frame.f_code.co_qualname in (
            "Simulator.__init__",
            "Cells.__init__",
            "Simulator.run_sim_core",
        ):
            raise AssemblyRejected(
                "Retained owners cannot be reconstructed or advanced",
                stage="source_boundary",
                partial=context,
            )
    if event in ("line", "opcode"):
        _nested_entry(context, frame)
    if role is None:
        return
    if event == "call":
        context.raw_calls.append((role, frame))
        actual = frame.f_locals.get("self")
        if role == "__init__":
            if (
                type(actual) is not context.native.cls
                or context.phase is not None
                or frame.f_locals.get("sim") is not context.parent.sim
                or frame.f_locals.get("cells") is not context.parent.cells
                or frame.f_locals.get("p") is not context.current.p
                or frame.f_locals.get("callbacks") is not context.parent.phase.callbacks
                or frame.f_locals.get("kind") is not context.native.enum.SIM
            ):
                raise ValueError(
                    "Exact new native SIM phase and actual constructor inputs required"
                )
            context.phase = actual
        elif actual is not context.phase:
            raise ValueError("Actual same native phase helper required")
    if role == "__init__" and event in ("call", "line", "opcode"):
        fields = frame.f_locals
        expected = dict(
            p=context.current.p,
            cells=context.parent.cells,
            sim=context.parent.sim,
            kind=context.native.enum.SIM,
            callbacks=context.parent.phase.callbacks,
        )
        if any(fields.get(name) is not value for name, value in expected.items()):
            raise ValueError("Retained actual constructor arguments changed before source")
    if role == "_init_kludge" and event in ("line", "opcode", "return"):
        if event == "opcode" and frame.f_lasti == context.handler_store_offset:
            if (
                context.parent.sim.dyna is not context.original_handler
                or context.handler_write is not None
            ):
                raise ValueError("Native handler store must start with original retained owner")
            context.pending_handler_store = (frame, frame.f_lasti, context.phase.dyna)
        elif context.pending_handler_store is not None:
            pending = context.pending_handler_store
            if (
                pending[0] is not frame
                or context.parent.sim.dyna is not pending[2]
                or context.phase.dyna is not pending[2]
            ):
                raise ValueError("Actual immediately preceding native handler store required")
            context.handler_write, context.pending_handler_store = pending, None
    if event in ("call", "line", "opcode"):
        frame.f_trace_opcodes = True
        _metadata_guard(context)
    if event == "return":
        context.raw_returns.append((role, frame, arg))


def _nested_entry(context, frame):
    """Authenticate actual nested constructor/helper dispatch before its body."""
    path = Path(frame.f_code.co_filename)
    api = _phase_import_api()
    matches = []
    for function, (_issuance, row) in _IMPORTS.items():
        original = row.original
        if frame.f_code not in (function.__code__, original.__code__) or frame.f_globals is not (
            function.__globals__ if frame.f_code is function.__code__ else original.__globals__
        ):
            continue
        owner = row.module if row.target[0][0] is None else row.stack[0]
        name = row.target[0][1]
        api["validate"](function, original, owner=owner, attribute=name)
        if frame.f_code is function.__code__:
            for key, value in (function.__kwdefaults__ or {}).items():
                if key.startswith("__beartype_") and frame.f_locals.get(key) is not value:
                    raise ValueError("Actual nested wrapper hidden delegate/default changed")
        actual = frame.f_locals.get("self")
        if isinstance(owner, type) and actual is not None:
            if owner not in type(actual).__mro__ or name in vars(actual):
                raise ValueError("Actual nested constructor receiver/dispatch required")
            dispatch = next(c for c in type(actual).__mro__ if name in vars(c))
            if dispatch is not owner or vars(dispatch)[name] is not function:
                # A source-declared super().__init__ enters a base body even
                # though normal attribute lookup resolves the subclass. Bind
                # that original caller rather than rejecting real cache ABCs.
                caller, inherited = frame.f_back, False
                for _ in range(3):
                    if caller is None:
                        break
                    for _outer, (_context, source_row) in _IMPORTS.items():
                        body = source_row.original
                        if (
                            name == "__init__"
                            and caller.f_code is body.__code__
                            and caller.f_globals is body.__globals__
                            and "super" in body.__code__.co_names
                            and caller.f_locals.get("self") is actual
                        ):
                            inherited = True
                    caller = caller.f_back
                if not inherited:
                    raise ValueError("Original nested class method dispatch changed")
        matches.append((function, original, owner, name))
    selected = (
        path.is_relative_to(source.NATIVE) and str(path.relative_to(source.NATIVE)) in source.PINS
    )
    if selected and not matches:
        raise AssemblyRejected(
            "Actual import-issued nested native entry required",
            stage="nested_source",
            partial=context,
        )
    if frame.f_code in context.wrapper_codes and not matches:
        raise AssemblyRejected(
            "Actual nested wrapper association required", stage="nested_source", partial=context
        )
    return tuple(matches)


def _capture_boundary(context, frame, event):
    relevant = frame.f_code.co_filename.startswith(str(source.NATIVE) + os.sep) or (
        frame.f_code in context.wrapper_codes
    )
    if relevant and event in ("call", "line", "opcode") and context.capture_errors:
        error = AssemblyRejected(
            "Incomplete constructor observation stops further source work",
            stage="capture",
            partial=context,
        )
        raise error from context.capture_errors[0][1]


def _run_observed(context):
    """One already-entered frame owns the source call and hook cleanup."""
    prior = sys.getprofile(), sys.gettrace()
    local_traces, primary = {}, None
    observing = True

    def inherited(function, frame, event, arg, label):
        if function is None:
            return None
        try:
            return function(frame, event, arg)
        except BaseException as error:
            context.raw_returns.append((label, frame, arg))
            context.capture_errors.append((label, error))
            if event not in ("exception", "return", "c_return", "c_exception"):
                raise
            return None

    def profile(frame, event, arg):
        if not observing:
            return
        if event in ("return", "c_return", "c_exception"):
            context.raw_returns.append(("direct_profile_" + event, frame, arg))
        inherited(prior[0], frame, event, arg, "inherited_profile_" + event)
        if event == "call":
            _capture_boundary(context, frame, event)
            _metadata_guard(context)
            _observe(context, frame, event, arg)

    def trace(frame, event, arg):
        if not observing:
            return None
        if event in ("exception", "return"):
            if event == "exception" and frame.f_code.co_filename.startswith(
                str(source.NATIVE) + os.sep
            ):
                context.pending_source_error = (frame, arg[1])
            elif event == "return" and timing._normal_return(frame):
                pending = getattr(context, "pending_source_error", None)
                if pending is not None and pending[0] is frame:
                    context.pending_source_error = None
            context.last_raw = ("direct_trace_" + event, frame, arg)
            context.raw_returns.append(context.last_raw)
        function = prior[1] if event == "call" else local_traces.get(id(frame))
        value = inherited(function, frame, event, arg, "inherited_trace_" + event)
        if value is not None:
            local_traces[id(frame)] = value
        try:
            _capture_boundary(context, frame, event)
            _metadata_guard(context)
            _observe(context, frame, event, arg)
        except BaseException as error:
            if event in ("exception", "return"):
                context.raw_returns.append(("capture_" + event, frame, arg))
                context.capture_errors.append(("capture_" + event, error))
            else:
                raise
        if event == "return":
            local_traces.pop(id(frame), None)
        return trace

    try:
        sys.setprofile(profile)
        sys.settrace(trace)
        _construct(context)
    except BaseException as error:
        pending = getattr(context, "pending_source_error", None)
        primary = (
            context.source_error
            if context.source_error is not None
            else (pending[1] if pending is not None and context.capture_errors else error)
        )
        if error is not primary:
            context.capture_errors.append(("claim_closure", error))
        raise primary from primary.__cause__
    finally:
        observing = False
        failures = []
        manager = context.parameter_manager
        if manager is not None:
            for setter in (sys.setprofile, sys.settrace):
                for _attempt in range(2):
                    try:
                        setter(None)
                        break
                    except BaseException as secondary:
                        failures.append(("claim_cleanup_hook_suspend", secondary))
            try:
                generator = vars(manager).get("gen")
                if generator is not None and generator.gi_frame is not None:
                    if primary is not None:
                        generator.throw(primary)
                    else:
                        generator.close()
            except BaseException as secondary:
                if secondary is not primary:
                    failures.append(("pending_parameter_claim_closure", secondary))
        for getter, setter, original in (
            (sys.gettrace, sys.settrace, prior[1]),
            (sys.getprofile, sys.setprofile, prior[0]),
        ):
            for attempt in range(2):
                try:
                    setter(original)
                    if getter() is original:
                        break
                except BaseException as error:
                    failures.append(("hook_recovery_" + str(attempt), error))
        context.capture_errors.extend(failures)
        if primary is None and failures:
            raise failures[0][1]


def _constructor_state(context):
    """Complete new-object fields, using the existing closed projection/graph.

    Weak-phase links remain actual source-returned proxy objects; they are
    retained independently in the graph and represented by owned references
    only in the value view. No proxy, config or native object is recreated.
    """
    completed, seen = [], set()
    for frame, _, _ in context.work:
        if frame.f_code.co_name != "__init__" or not timing._normal_return(frame):
            continue
        actual = frame.f_locals.get("self")
        if actual is not None and id(actual) not in seen:
            seen.add(id(actual))
            completed.append((frame.f_code.co_qualname, actual))
    if not any(obj is context.phase for _, obj in completed) or not any(
        obj is context.phase.dyna for _, obj in completed
    ):
        raise ValueError("Actual returned phase and fresh handler constructor objects required")
    initial = terminal.base.previous.storage.previous.previous.previous
    projector = initial._projector(context.parent.parent.init_parent)
    roots = [*projector.objects, *completed, ("SIM_parameters", context.current.p)]
    for _, obj in completed:
        for name, value in vars(obj).items():
            if type(value) in ProxyTypes:
                roots.append(("actual_constructor_proxy:" + name, value))
    # Same-p subconfiguration objects are existing actual returned objects;
    # their complete state/configuration remains under the public phase claim.
    for obj in context.current.loaded.constructed:
        roots.append(("current_configuration", obj))
    projector.objects = roots
    project = initial.core._LITERAL._project
    values = tuple((name, project(projector, vars(obj))) for name, obj in completed)
    scope = terminal.base.previous.storage.previous._scope(context.parent.parent)
    cache = scope.snapshot(values)
    if not hasattr(context, "new_graph_view"):
        context.new_graph_objects = tuple(completed)
        context.new_graph_fields = [{} for _ in completed]
        context.new_graph_view = SimpleNamespace(
            objects=context.new_graph_objects, fields=context.new_graph_fields
        )
    if len(completed) != len(context.new_graph_objects) or any(
        name != old_name or obj is not old_obj
        for (name, obj), (old_name, old_obj) in zip(
            completed, context.new_graph_objects, strict=True
        )
    ):
        raise ValueError("Actual completed constructor object roster changed")
    for (_, obj), fields in zip(completed, context.new_graph_fields, strict=True):
        fields.clear()
        fields.update(vars(obj))
    graph = scope.graph(context.new_graph_view, context.new_graph_view, context.parent.graph_tape)
    return cache, graph, tuple(completed), tuple(roots)


def _construct(context):
    """Original constructor; retain its direct primary before claim closure."""
    kind = context.native.enum.SIM
    context.parameter_manager = timing.construction(
        context.current.owner, kind=kind, law_id=timing.PHASE_CONSTRUCTION_LAW, enabled=True
    )
    with context.parameter_manager as claim:
        context.parameter_claim = claim
        context.current_p = claim.parameters
        claim.check()
        try:
            context.raw_phase = context.native.cls(
                kind=kind,
                p=context.current_p,
                cells=context.parent.cells,
                sim=context.parent.sim,
                callbacks=context.parent.phase.callbacks,
            )
        except BaseException as error:
            context.source_error = error
            raise
    context.parameter_record = timing.validate_closed_phase(
        claim, original_owner=context.current.owner
    )
    if context.parameter_record is not claim.record or context.raw_phase is not context.phase:
        raise ValueError("Actual complete phase/parameter source records required")


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise AssemblyRejected("Actual SIM assembly remains held", stage="release")
    _ready()
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise AssemblyRejected("Concurrent SIM assembly", stage="reentrant")
        if type(request) is not Request or request not in _REQUESTS:
            raise AssemblyRejected("Actual issued assembly request required", stage="request")
        if request in _CONSUMED:
            raise AssemblyRejected("Assembly attempt already consumed", stage="consumed")
        refs = _REQUESTS[request]
        metadata = SimpleNamespace(metadata_work=list(request.metadata_work))
        prepared = _metadata(
            metadata,
            "actual_final_runner_and_parent_verification",
            preparation._authority,
            request.preparation_owner,
        )
        if (
            prepared is not refs[0]
            or prepared.trial is not refs[1]
            or request.source_identity != _digest(source_plan())
        ):
            raise AssemblyRejected("Original runner preparation changed", stage="association")
        context = SimpleNamespace(
            request=request,
            refs=refs,
            prepared=prepared,
            parent=prepared.parent,
            current=prepared.current,
            native=None,
            thread=get_ident(),
            invalid=False,
            active=True,
            stage="reservation",
            reservation=None,
            phase=None,
            raw_phase=None,
            handler_write=None,
            parameter_claim=None,
            parameter_manager=None,
            parameter_record=None,
            work=[],
            metadata_work=metadata.metadata_work,
            raw_calls=[],
            raw_returns=[],
            admitted={},
            capture_errors=[],
            source_error=None,
            primary=None,
            trial=None,
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        try:
            context.native = _native()
            context.roles = {fn.__code__: name for name, fn in context.native.methods.items()}
            context.wrapper_codes = frozenset(fn.__code__ for fn in _IMPORTS)
            stores = [
                i.offset
                for i in dis.get_instructions(context.native.methods["_init_kludge"])
                if i.opname == "STORE_ATTR" and i.argval == "dyna"
            ]
            if len(stores) != 1:
                raise ValueError("One exact original retained handler store required")
            context.handler_store_offset, context.pending_handler_store = stores[0], None
            context.original_handler = context.parent.sim.dyna
            context.retained_view = _retained_view(context.parent)
            context.reservation = _metadata(
                context,
                "actual_completed_INIT_irreversible_retirement",
                terminal.reserve_for_sim,
                prepared.request.init_owner,
                expected_trial=refs[2],
                law_id=terminal.SIM_RESERVATION_LAW,
                enabled=True,
            )
            context.retained_before = _metadata(
                context, "actual_retained_before_value_layout_RNG_capture", _retained_state, context
            )
            # The reusable operation observer below must run both original
            # native and inherited guards. No source/phase is evaluated here.
            _run_observed(context)
            _check(context)
            if context.capture_errors or context.handler_write is None:
                raise ValueError("Complete constructor observation and handler write required")
            after = _check_retained(context)
            context.constructor_state = _metadata(
                context,
                "actual_new_constructor_fields_and_graph_capture",
                _constructor_state,
                context,
            )
            values = Trial(
                request.source_identity,
                refs[1].identity,
                refs[2].identity,
                refs[3].identity,
                context.parameter_record,
                tuple((name, id(value)) for name, value in vars(context.phase).items()),
                tuple(context.work),
                tuple(context.metadata_work),
                tuple(context.retained_before[2]),
                tuple(after[2]),
                True,
                "after_SIM_constructor_before_sim_info_report_and_run_sim_core",
                "",
                context.constructor_state,
            )
            context.trial = replace(values, identity=_digest(record_document(values)))
        except BaseException as error:
            context.invalid = True
            context.primary = context.source_error if context.source_error is not None else error
            if error is not context.primary:
                context.capture_errors.append(("closure", error))
            _FAILED.append(context)
            raise AssemblyRejected(
                "Actual SIM constructor failed/refused", stage=context.stage, partial=context
            ) from context.primary
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
        owner = object.__new__(SimAssemblyOwner)
        context.owner = owner
        _ISSUED[owner] = context
        return owner


def record_document(value):
    return dict(
        law=LAW_ID,
        source=value.source_identity,
        preparation=value.preparation_identity,
        INIT=value.terminal_identity,
        current_parameters=value.parameters_identity,
        parameter_record=value.phase_parameter_record.identity,
        bindings=value.bindings,
        work=tuple((f.f_code.co_filename, f.f_code.co_qualname) for f, _, _ in value.work),
        metadata_work=value.metadata_work,
        rng_before=tuple(v.identity for v in value.rng_before),
        rng_after=tuple(v.identity for v in value.rng_after),
        endpoint=value.endpoint,
        constructor_completed=value.constructor_completed,
        constructor_state=value.constructor_state[0].identity,
        constructor_graph=_digest(value.constructor_state[1][1]),
        constructor_roster=tuple((name, id(obj)) for name, obj in value.constructor_state[2]),
        SIM_iterations=0,
    )


class SimAssemblyOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only genuine successful SIM construction issues this owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("A live SIM constructor owner cannot be hydrated")

    @property
    def trial(self):
        return validate_assembly(self)


def _authority(owner):
    if type(owner) is not SimAssemblyOwner or owner not in _ISSUED:
        raise AssemblyRejected("Actual issued SIM constructor owner required", stage="owner")
    if owner in _RUN_RETIRED:
        raise AssemblyRejected("SIM constructor forwarded irreversibly", stage="forwarded")
    context = _ISSUED[owner]
    if context.owner is not owner or context.active or context.invalid:
        raise AssemblyRejected(
            "Active/changed SIM constructor owner", stage="owner", partial=context
        )
    _ready()
    _check(context)
    current_state = _metadata(
        context, "actual_new_constructor_state_verification", _constructor_state, context
    )
    if current_state[0].identity != context.constructor_state[0].identity:
        raise ValueError("Actual returned constructor field values changed")
    terminal.base._same(current_state[1][0], context.constructor_state[1][0])
    if current_state[1][1] != context.constructor_state[1][1]:
        raise ValueError("Actual returned constructor graph changed")
    if (
        context.active
        or context.source_error is not None
        or context.capture_errors
        or context.trial.constructor_state is not context.constructor_state
        or context.trial.identity != _digest(record_document(context.trial))
        or timing.validate_closed_phase(
            context.parameter_claim, original_owner=context.current.owner
        )
        is not context.parameter_record
    ):
        raise AssemblyRejected(
            "Original closed SIM constructor changed", stage="owner", partial=context
        )
    return context


def validate_assembly(owner):
    """Same authenticated constructor record, never full SIM completion."""
    return _authority(owner).trial


def _targets(context):
    cls = type(context.parent.sim)
    if any(name in vars(context.parent.sim) for name in ("sim_info_report", "run_sim_core")):
        raise ValueError("Native Simulator method may not be shadowed by an instance field")
    result = []
    for name, role in (("sim_info_report", "report"), ("run_sim_core", "run_core")):
        actual = vars(cls).get(name)
        body = timing.callbacks._source_function(actual, "betse/science/sim.py", name, "Simulator")
        if preparation.observation._code(body.__code__) != preparation.observation._code(
            source.code(role)
        ):
            raise ValueError("Exact original report/run_core executable required")
        _phase_import_api()["validate"](actual, body, owner=cls, attribute=name)
        result.append((name, id(actual), id(body.__code__)))
    return tuple(result)


def run_core_boundary(owner):
    """Return observations only; no callback/executable is issued as authority."""
    context = _authority(owner)
    targets = _metadata(
        context, "actual_original_report_run_core_binding_verification", _targets, context
    )
    return dict(
        endpoint=context.trial.endpoint,
        phase=context.phase,
        sim=context.parent.sim,
        cells=context.parent.cells,
        old_p=context.parent.p,
        current_p=context.current.p,
        callbacks=context.parent.phase.callbacks,
        SIM_iterations=(),
        event_or_gate_evolution=None,
        actual_constructor_parameter_record=context.parameter_record,
        checked_original_targets=targets,
        next_original_call="sim_info_report",
        run_core_entered=False,
    )


class RunReservation:
    """Opaque one-shot retirement metadata; never executable/run authority."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only actual constructor retirement issues this token")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live constructor retirement cannot be hydrated")


def reserve_for_run(owner, *, expected_trial, law_id, enabled=False):
    if enabled is not True or os.environ.get(RUN_RESERVATION_RELEASE) != "1":
        raise AssemblyRejected("Actual SIM retirement held", stage="release")
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise AssemblyRejected("Concurrent constructor retirement", stage="reentrant")
        if type(law_id) is not str or law_id != RUN_RESERVATION_LAW:
            raise AssemblyRejected("Exact original run retirement law required", stage="law")
        # Reserve before fallible observable validation: an inherited hook may
        # not reenter this owner at the same epoch and acquire a second token.
        pending = SimpleNamespace(invalid=False)
        _ACTIVE.append(pending)
        try:
            context = _authority(owner)
            if pending.invalid or context.trial is not expected_trial:
                raise AssemblyRejected("Original valid constructor record required", stage="trial")
            if owner in _RUN_RETIRED or _ISSUED.get(owner) is not context:
                raise AssemblyRejected("Original constructor parent changed", stage="parent")
            token = object.__new__(RunReservation)
            row = (owner, context, expected_trial, get_ident())
            _RUN_RETIRED[owner] = row
            _RUN_RESERVATIONS[token] = row
            return token
        finally:
            if not _ACTIVE or _ACTIVE[-1] is not pending:
                raise AssemblyRejected("Original retirement exclusion changed", stage="exclusion")
            _ACTIVE.pop()


def _run_reservation(token):
    """Historical identities after mutation; deliberately no old value audit."""
    row = _RUN_RESERVATIONS.get(token) if type(token) is RunReservation else None
    if row is None:
        raise AssemblyRejected("Actual original run reservation required", stage="reservation")
    owner, context, trial, thread = row
    if (
        _RUN_RETIRED.get(owner) is not row
        or _ISSUED.get(owner) is not context
        or context.owner is not owner
        or context.trial is not trial
        or context.active
        or context.invalid
        or thread != get_ident()
        or context.source_error is not None
        or context.capture_errors
        or trial.identity != _digest(record_document(trial))
    ):
        raise AssemblyRejected("Original closed constructor links changed", stage="reservation")
    _ready()
    return context, trial
