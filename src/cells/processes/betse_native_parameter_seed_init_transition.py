"""One actual same-p SEED-to-new-INIT parameter transition, separately held.

The original successful WorldConstructionClaim and complete-load owner stay
historical. Their reservation is never reset or replaced. This sibling consumes
that actual closed claim once, shares all construction/parameter exclusion,
and observes the original INIT constructor/timing bodies on the SAME p.

The consumer separately retires/authenticates the actual SEED/world endpoint
and its existing Cells/callbacks. This contract provides no pickle/loadWorld
parity, phase/material ownership, init_core result or completed initialization.
"""

import ast
import dis
import hashlib
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import FunctionType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_phase_construction as timing

shared, parameters, claims, prefix = timing.shared, timing.parameters, timing.claims, timing.prefix
SEED_INIT_LAW = "betse_same_world_ready_closed_seed_new_init_parameters@1"
RELEASE = "CELLS_NATIVE_PARAMETER_SEED_INIT_RELEASED"
TIMING_SHA256 = "29e87c5adbb6126c04041371542fa600bd1312de09c82f329ea1c08fc452fa19"
SEED_SHA256 = "bda0ab87e293af18eb30ff38a0cb356162bc74269fbeb0cd1d41aa8d52176b73"
RUNNER_SHA256 = "6a9389f106d717dc83ea1a594a64aa5bde278cef9a17b2a8ff01251b08d7be8a"
_LOCK, _ACTIVE, _FAILED = Lock(), [], []
_ISSUED, _CONSUMED = WeakKeyDictionary(), WeakKeyDictionary()
_PATHS = parameters.previous.previous.mod.subconfigs.paths
_MONITOR = sys.monitoring
_MONITOR_NAME = "Cells same-p INIT flag WRITE"
_MONITOR_NAMES = (
    "use_tool_id",
    "free_tool_id",
    "get_tool",
    "get_local_events",
    "set_local_events",
    "register_callback",
    "get_events",
    "set_events",
)
_MONITOR_APIS = tuple(getattr(_MONITOR, name) for name in _MONITOR_NAMES)
CONSUMER_MODULE = "cells.processes.betse_native_init_retained_world"
CONSUMER_INTERFACE_SHA256 = CONSUMER_REVIEW_SHA256 = None
CONSUMER_KEY_REVIEW_SHA256 = None


class SeedInitRejected(ValueError):
    def __init__(self, reason, *, stage, claim=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.seed_init_claim, self.partial = stage, claim, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class SeedInitRecord(timing.PhaseParameterRecord):
    original_seed_record_identity: str = ""
    seed_parameter_graph_identity: str = ""
    flag_instruction_events: tuple = ()


class SeedInitClaim:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use seed_to_init with the actual successful closed SEED claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live same-p SEED-to-INIT permission cannot be reconstructed")

    @property
    def parameters(self):
        return _checked(self).p

    def check(self):
        _checked(self)

    @property
    def record(self):
        context = _context(self)
        if context.active or context.record is None:
            raise SeedInitRejected(
                "Closed record unavailable", stage="record", claim=self, partial=context
            )
        if (
            context.record is not context.original_record
            or _digest(record_document(context.record)) != context.record.identity
            or (context.record.succeeded and (context.invalid or context.capture_errors))
        ):
            raise SeedInitRejected("Original transition record changed", stage="record", claim=self)
        return context.record


def _digest(value):
    return timing._digest(value)


def _dependency():
    for module, expected in ((timing, TIMING_SHA256), (shared, SEED_SHA256)):
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise SeedInitRejected(
                "Exact reviewed transition dependency required", stage="producer"
            )


def source_plan():
    _dependency()
    native = timing.NATIVE / "betse/science/simrunner.py"
    if hashlib.sha256(native.read_bytes()).hexdigest() != RUNNER_SHA256:
        raise ValueError("Original SEED/INIT caller source required")
    cls = timing.callbacks.simulator._class(ast.parse(native.read_bytes()), "SimRunner")
    method = timing.callbacks.simulator._method(cls, "init")
    calls = tuple(node for node in ast.walk(method) if isinstance(node, ast.Call))
    constructor = next(
        node for node in calls if isinstance(node.func, ast.Name) and node.func.id == "SimPhase"
    )
    if tuple(key.arg for key in constructor.keywords) != ("kind", "cells", "p", "callbacks"):
        raise ValueError("Original INIT optional-input constructor boundary changed")
    return dict(
        law=SEED_INIT_LAW,
        timing_source=TIMING_SHA256,
        original_seed_source=SEED_SHA256,
        original_timing=timing.source_plan(),
        original_caller=dict(
            path=str(native),
            sha256=RUNNER_SHA256,
            lines=(method.lineno, method.end_lineno),
            constructor_line=constructor.lineno,
            original_optional_inputs=tuple(key.arg for key in constructor.keywords),
        ),
        input="actual successful closed WorldConstructionClaim + exact original WorldReady owner",
        original_seed_edge="Keep parameters._CONSTRUCTED[owner] is original_seed_claim forever",
        new_edge="One irreversible successor _CONSUMED[original_seed_claim] is actual INIT context",
        store_order=timing.STORES,
        flag_witness="Actual original STORE_ATTR event writes the existing exact bool False again",
        clock_aliases=timing.TIMING_INPUTS["INIT"],
        ratio="Actual original native result only; metadata never performs division/replay",
        private_consumer=dict(
            module=CONSUMER_MODULE,
            interface=CONSUMER_INTERFACE_SHA256,
            review=CONSUMER_REVIEW_SHA256,
            key_review=CONSUMER_KEY_REVIEW_SHA256,
        ),
        consumer_obligations=(
            "Authenticate and retire actual retained SEED/world endpoint before this claim",
            "Pass actual existing Cells/callbacks through original optional constructor args",
            "Omit sim to create a NEW Simulator; retain old SEED phase/simulator historically",
            "Seal the new constructor/consumer source stages before closing this same claim",
            "Use factored endpoint authority; never call stale SEED snapshot validators afterward",
        ),
        literal_native_boundary=(
            "SimPhase INIT optional existing Cells; before init_core/run_sim_core"
        ),
        saved_loader_or_full_SimRunner_init_equivalence=False,
        existing_SEED_or_fresh_timing_API_changed=False,
        native_phase_material_completed_INIT_or_scientific_admission=False,
        held=True,
    )


def record_document(value):
    return dict(
        **timing.record_document(value),
        original_seed_record=value.original_seed_record_identity,
        seed_parameter_graph=value.seed_parameter_graph_identity,
        flag_instruction_events=value.flag_instruction_events,
        same_actual_p=True,
        saved_loader_or_SEED_completion_claim=False,
    )


def _context(claim):
    if type(claim) is not SeedInitClaim or claim not in _ISSUED:
        raise SeedInitRejected("Actual issued same-p transition claim required", stage="claim")
    context = _ISSUED[claim]
    if context.claim is not claim:
        raise SeedInitRejected(
            "Original transition registry edge changed", stage="claim", claim=claim
        )
    return context


def failed_context(claim):
    """Retained failure roots only, never permission or a successful parent."""
    context = _context(claim)
    if context.active or not (
        context.invalid
        or context.source_error is not None
        or context.capture_errors
        or context.raw_errors
    ):
        raise SeedInitRejected("Closed failed transition required", stage="failed", claim=claim)
    return context


def _stacks(context):
    return (
        (_ACTIVE, context),
        (timing._ACTIVE, context),
        (shared._ACTIVE, context),
        *parameters._stacks(context),
    )


def _seed_metadata(context):
    seed = shared._context(context.seed_claim)
    if (
        seed is not context.seed_context
        or seed.owner is not context.owner
        or seed.p is not context.p
        or seed.source is not context.source
        or seed.record is not context.seed_record
        or seed.original_record is not context.seed_record
        or seed.active
        or seed.invalid
        or seed.validating
        or seed.source_error is not None
        or seed.capture_errors
        or seed.thread != context.thread
        or seed.guard is not context.seed_guard
        or seed.guard.active
        or seed.guard.invalid
        or seed.guard.thread != context.thread
        or not seed.guard.audit_ready
        or seed.before_graph is not context.before_graph
        or seed.before_names is not context.before_names
        or seed.before_cm is not context.before_cm
        or seed.final_capture is not context.seed_after_graph
        or seed.work is not context.seed_work
        or tuple(seed.work) != context.seed_record.work
        or seed.bindings is not context.seed_bindings
        or _CONSUMED.get(context.seed_claim) is not context
        or parameters._CONSTRUCTED.get(context.owner) is not context.seed_claim
        or context.seed_claim.record is not context.seed_record
        or _digest(shared.record_document(context.seed_record)) != context.seed_record.identity
        or _digest(context.seed_after_graph[1]) != context.seed_record.after_identity
    ):
        raise ValueError("Original successful closed SEED/owner/p/record/guard association changed")
    # Historical source associations only; deliberately no old _bytes or
    # validate_closed_seed call after INIT adds its real temporal stores.
    shared._source(seed)


def _source(context):
    _dependency()
    if context.guard is not context.original_guard or context.guard.thread != context.thread:
        raise ValueError("Original transition guard/thread changed")
    _seed_metadata(context)
    if context.source_identity != _digest(source_plan()):
        raise ValueError("Same-p transition source changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    prefix.parameters.inherited._same(
        timing._native_bindings(context.original_native), context.native_bindings
    )
    if context.consumer is not None:
        _bind_consumer(context, first=False)


def _checked(claim):
    context = _context(claim)
    if (
        not context.active
        or context.invalid
        or context.validating
        or context.thread != get_ident()
        or context.guard is not context.original_guard
        or not context.original_guard.active
        or context.original_guard.invalid
        or not context.original_guard.audit_ready
        or any(not stack or stack[-1] is not value for stack, value in context.exclusion)
    ):
        raise SeedInitRejected(
            "Active exclusive same-p INIT claim required",
            stage="active",
            claim=claim,
            partial=context,
        )
    try:
        if any(
            getattr(_MONITOR, name) is not saved
            for name, saved in zip(_MONITOR_NAMES, _MONITOR_APIS, strict=True)
        ):
            raise ValueError("Original source-monitor API binding changed")
        if context.monitoring and (
            _MONITOR.get_tool(context.monitor_tool) != _MONITOR_NAME
            or _MONITOR.get_local_events(
                context.monitor_tool, context.native.methods["_init_kludge"].__code__
            )
            != (_MONITOR.events.INSTRUCTION | _MONITOR.events.LINE)
            or _MONITOR.get_events(context.monitor_tool)
            != (_MONITOR.events.PY_START | _MONITOR.events.PY_RETURN | _MONITOR.events.PY_UNWIND)
        ):
            raise ValueError("Actual local flag instruction observer was changed")
        context.work.append((len(context.work), "active_check", "attempted"))
        _source(context)
        _bytes(context, complete=False)
        context.work.append((len(context.work), "active_check", "completed"))
        return context
    except BaseException:
        context.invalid = context.original_guard.invalid = True
        raise


def _bytes(context, *, complete):
    if not context.assignments:
        if tuple(vars(context.p)) != (*context.before_names, "_run_sim"):
            raise ValueError("Unobserved INIT clocks or changed existing SEED flag layout")
        if vars(context.p)["_run_sim"] is not False:
            raise ValueError("Same actual existing SEED flag must remain exact bool False")
        prefix.parameters.inherited._same_graph(
            parameters._capture(context.source), context.seed_after_graph
        )
        if complete:
            raise ValueError("Native INIT flag WRITE was not observed; equal False is not evidence")
        return ()
    return _TIMING_BYTES(context, complete=complete)


def _stores(context, frame, event):
    if not context.assignments:
        _bytes(context, complete=False)
        if event == "line":
            context.lines[id(frame)] = frame.f_lineno
        return
    _TIMING_STORES(context, frame, event)


def _observe(context, frame, event, arg):
    role = context.roles.get(frame.f_code)
    if (
        role == "__init__"
        and event == "call"
        and frame.f_globals is not context.native.methods[role].__globals__
    ):
        _bind_consumer(context, first=True)
    if role == "_init_kludge" and event == "opcode":
        pending = context.flag_write_pending
        if pending is not None:
            # This event is AFTER the exact native STORE_ATTR completed. A
            # failing setter's exception/unwind never confirms its pending row.
            if pending[0] is not frame or context.assignments:
                _RUNTIME["_reject"](context, "Duplicate/foreign native INIT flag store")
            if vars(context.p).get("_run_sim") is not False:
                _RUNTIME["_reject"](context, "Native INIT flag assignment changed value/type")
            context.last_assignment = (
                "_run_sim",
                False,
                frame,
                context.store_lines[("INIT", "_run_sim")],
            )
            context.assignments.append(context.last_assignment)
            context.flag_write_pending = None
            context.flag_write_events.append(pending)
            context.timing_graph = parameters._capture(context.source, names=("_run_sim",))
        if frame.f_lasti in context.flag_offsets:
            _RUNTIME["_source_guard"](context)
            if context.assignments or context.flag_write_pending is not None:
                _RUNTIME["_reject"](context, "Repeated original INIT flag WRITE")
            context.flag_write_pending = (frame, frame.f_lasti, frame.f_lineno)
        return
    _TIMING_OBSERVE(context, frame, event, arg)
    if role == "__init__" and event == "call":
        # Source ordering requires a live Cells input, prepared callbacks and a
        # fresh Simulator. The actual endpoint authority is the consumer's.
        if (
            frame.f_locals.get("cells") is None
            or frame.f_locals.get("sim") is not None
            or frame.f_locals.get("callbacks") is None
        ):
            _RUNTIME["_reject"](
                context, "Existing Cells/callback and omitted fresh Simulator required"
            )


def _phase(context):
    _TIMING_PHASE(context)
    inputs = dict(context.optional_inputs)
    if (
        inputs.get("cells") is None
        or inputs.get("sim") is not None
        or inputs.get("callbacks") is None
    ):
        raise ValueError("Original retained-world INIT optional argument route changed")
    if len(context.flag_write_events) != 1 or context.flag_write_pending is not None:
        raise ValueError("Exactly one completed actual native flag WRITE event required")
    frame, offset, line = context.flag_write_events[0]
    if (
        frame is not context.frames["_init_kludge"]
        or offset not in context.flag_offsets
        or line != context.store_lines[("INIT", "_run_sim")]
    ):
        raise ValueError("Original flag instruction/frame/line witness changed")


def _caller(context, role, frame):
    if context.consumer is None:
        return _TIMING_CALLER(context, role, frame)
    c, module = context.consumer, context.consumer_module
    invocation = frame.f_back
    actual = frame.f_locals.get("self")
    if (
        invocation is None
        or invocation.f_code is not module._invoke.__code__
        or invocation.f_locals.get("context") is not c
        or invocation.f_locals.get("label") != "SimPhase." + role
        or invocation.f_locals.get("selected") is not c.methods[("SimPhase", role)]
        or invocation.f_locals.get("actual") is not actual
    ):
        raise ValueError("Actual private source invocation/receiver chain required")
    if role == "__init__":
        return invocation
    wrapper = invocation.f_back
    parent = None if wrapper is None else wrapper.f_back
    expected = context.frames["__init__" if role == "_init_kludge" else "_init_kludge"]
    if parent is not expected:
        raise ValueError("Actual private wrapper and original parent frame required")
    return parent


def consumer_interface(payload):
    """Existing exact-byte two-reference binding; no source body is evaluated."""
    from cells.processes import betse_native_world_phase_construction as forms

    function = FunctionType(
        forms._helper_binding.__code__,
        dict(vars(forms), HELPER_BACK_REFERENCE_SLOTS=("KEY_SOURCE_SHA256", "KEY_REVIEW_SHA256")),
    )
    return function(payload)


def _private_bindings(context, consumer, module):
    result = [consumer, module, consumer.methods, consumer.runtime_types]
    allowed = tuple(module._code_tree(module._namespace.__code__))
    for name in timing.METHODS:
        fn = consumer.methods[("SimPhase", name)]
        original = context.original_native.methods[name]
        if fn.__code__ is not original.__code__ or fn.__globals__ is original.__globals__:
            raise ValueError("Exact original code in its authentic private namespace required")
        namespace, native = fn.__globals__, original.__globals__
        if tuple(namespace) != tuple(native):
            raise ValueError("Private source namespace keys/order changed")
        for key, value in namespace.items():
            if key == "__builtins__":
                if value is not fn.__builtins__ or type(value) is not dict:
                    raise ValueError("Private source cached builtins changed")
                if tuple(value) != tuple(original.__builtins__):
                    raise ValueError("Private source builtin lookup keys/order changed")
                for builtin_name, builtin_value in value.items():
                    if builtin_name == "__import__":
                        wrapper = builtin_value
                    elif builtin_value is not original.__builtins__[builtin_name]:
                        raise ValueError("Private source builtin shadowed: " + builtin_name)
                result.extend((value, *value.values()))
            elif key in consumer.factory_names:
                wrapper = value
            elif value is not native[key]:
                raise ValueError("Original reached/global binding changed: " + key)
            else:
                result.append(value)
                continue
            if (
                type(wrapper) is not FunctionType
                or wrapper.__globals__ is not vars(module)
                or wrapper.__code__ not in allowed
            ):
                raise ValueError("Actual pinned consumer factory/import wrapper required")
            closed = dict(
                zip(
                    wrapper.__code__.co_freevars,
                    (cell.cell_contents for cell in wrapper.__closure__ or ()),
                    strict=True,
                )
            )
            if closed.get("context") is not consumer:
                raise ValueError("Private factory/import wrapper context changed")
            result.extend(prefix.parameters.inherited.tissue.aliases._atoms(wrapper))
        result.extend((fn, fn.__code__, namespace, fn.__builtins__))
    return tuple(result)


def _bind_consumer(context, *, first):
    if not all(
        type(value) is str and len(value) == 64
        for value in (
            CONSUMER_INTERFACE_SHA256,
            CONSUMER_REVIEW_SHA256,
            CONSUMER_KEY_REVIEW_SHA256,
        )
    ):
        raise SeedInitRejected(
            "Reviewed private INIT namespace remains unbound",
            stage="consumer_unbound",
            claim=context.claim,
            partial=context,
        )
    module = sys.modules.get(CONSUMER_MODULE)
    if module is None:
        raise ValueError("Actual loaded private INIT consumer required")
    path = Path(__file__).parents[3] / ("src/" + CONSUMER_MODULE.replace(".", "/") + ".py")
    if Path(module.__file__).resolve() != path or path.is_symlink():
        raise ValueError("Actual same-image private consumer required")
    identity, backrefs = consumer_interface(path.read_bytes())
    if identity != CONSUMER_INTERFACE_SHA256 or backrefs != (
        ("KEY_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("KEY_REVIEW_SHA256", CONSUMER_KEY_REVIEW_SHA256),
    ):
        raise ValueError("Actual private consumer source/back-reference regime changed")
    c = (module._ACTIVE[-1] if module._ACTIVE else None) if first else context.consumer
    if (
        c is None
        or c.key is not sys.modules[__name__]
        or c.claim is not context.claim
        or c.seed_claim is not context.seed_claim
        or c.seed_owner is not context.owner
        or c.p is not context.p
        or (context.active and not c.active)
        or c.invalid
        or c.thread != context.thread
        or module._CONSUMED.get(c.request) is not c
        or module._REQUESTS.get(c.request) is not c.refs
        or module._RETIRED.get(c.request.seed_owner) is not c
        or c.parent is not c.refs[0]
        or c.refs[5] is not context.seed_claim
        or c.refs[7] is not context.owner
        or c.refs[8] is not context.p
        or c.cells is not c.refs[9]
        or c.callback is not c.refs[10]
        or module._ready() is not sys.modules[__name__]
    ):
        raise ValueError("Actual retired endpoint and same-p consumer ancestry required")
    if first:
        if context.consumer is not None:
            raise ValueError("Private source namespace cannot be rebound")
        context.consumer, context.consumer_module = c, module
        methods = {name: c.methods[("SimPhase", name)] for name in timing.METHODS}
        if c.factories["SimPhase"] is not context.original_native.cls or c.runtime_types[
            "SimPhase"
        ].__bases__ != (context.original_native.cls,):
            raise ValueError("Actual consumer native/runtime phase class association required")
        context.native = SimpleNamespace(
            cls=c.runtime_types["SimPhase"],
            enum=context.original_native.enum,
            methods=methods,
            chains={name: (fn,) for name, fn in methods.items()},
        )
        context.consumer_bindings = _private_bindings(context, c, module)
        context.consumer_roster = tuple(module._binding(c))
    elif context.consumer is not c or context.consumer_module is not module:
        raise ValueError("Original private consumer context changed")
    for actual, saved in (
        (_private_bindings(context, c, module), context.consumer_bindings),
        (tuple(module._binding(c)), context.consumer_roster),
    ):
        if len(actual) != len(saved) or any(a is not b for a, b in zip(actual, saved, strict=True)):
            raise ValueError("Actual private source/factory/runtime namespace changed")


@contextmanager
def _monitor_flag(context):
    """Independent actual-source monitoring, compatible with consumer hooks.

    Only this free monitoring-tool slot is changed. Real source instruction
    events establish the equal-valued flag write; no replay or fake scalar
    callback stands in for the actual STORE_ATTR.
    """
    context.monitor_before = tuple(_MONITOR.get_tool(index) for index in range(6))
    available = [index for index, value in enumerate(context.monitor_before) if value is None]
    if not available:
        raise SeedInitRejected(
            "No free instruction/source observer tool",
            stage="monitoring",
            claim=context.claim,
            partial=context,
        )
    tool = context.monitor_tool = available[-1]
    primary, reserved = None, False
    codes = tuple(fn.__code__ for fn in context.native.methods.values())
    flag_code = context.native.methods["_init_kludge"].__code__

    def instruction(code, offset):
        frame = sys._getframe(1)
        if code is not flag_code or frame.f_code is not code or frame.f_lasti != offset:
            _RUNTIME["_reject"](context, "Exact actual flag instruction frame required")
        _observe(context, frame, "opcode", None)

    def start(code, offset):
        if code in context.roles or code.co_filename.startswith(str(timing.NATIVE) + os.sep):
            frame = sys._getframe(1)
            context.last_call = (code.co_filename, code.co_qualname, frame)
            context.actual_work.append(context.last_call)
            if len(context.actual_work) > timing.MAX_SOURCE_CALLS:
                _RUNTIME["_reject"](context, "Declared actual source call limit exhausted")
            _observe(context, frame, "call", None)

    def line(code, number):
        if code in context.roles:
            _observe(context, sys._getframe(1), "line", None)

    def returned(code, offset, value):
        if code in context.roles or code.co_filename.startswith(str(timing.NATIVE) + os.sep):
            _observe(context, sys._getframe(1), "return", value)

    def unwind(code, offset, error):
        if code in context.roles or code.co_filename.startswith(str(timing.NATIVE) + os.sep):
            frame = sys._getframe(1)
            if context.primary is None:
                context.primary = error
            # Exact original error and live return roots precede all fallible
            # observation. Keep both observation failures independently; the
            # second event must still be attempted after the first fails.
            context.last_raw = (code.co_qualname, frame, None)
            for event, value in (
                ("exception", (type(error), error, error.__traceback__)),
                ("return", None),
            ):
                witness = (frame, event, value)
                try:
                    _observe(context, frame, event, value)
                except BaseException as secondary:
                    row = ("unwind_" + event, secondary, witness)
                    context.last_error = row
                    context.raw_errors = (*context.raw_errors[-63:], row)
                    context.capture_errors = (*context.capture_errors[-63:], row)
                    if context.observation_error is None:
                        context.observation_error = secondary
                    context.invalid = context.original_guard.invalid = True

    callbacks = (
        (_MONITOR.events.INSTRUCTION, instruction),
        (_MONITOR.events.PY_START, start),
        (_MONITOR.events.LINE, line),
        (_MONITOR.events.PY_RETURN, returned),
        (_MONITOR.events.PY_UNWIND, unwind),
    )
    context.monitor_callbacks = callbacks
    try:
        _MONITOR.use_tool_id(tool, _MONITOR_NAME)
        reserved = True
        for event, callback in callbacks:
            _MONITOR.register_callback(tool, event, callback)
        for code in codes:
            events = _MONITOR.events.LINE
            if code is flag_code:
                events |= _MONITOR.events.INSTRUCTION
            _MONITOR.set_local_events(tool, code, events)
        _MONITOR.set_events(
            tool, _MONITOR.events.PY_START | _MONITOR.events.PY_RETURN | _MONITOR.events.PY_UNWIND
        )
        context.monitoring = True
        _checked(context.claim)
        yield
    except BaseException as error:
        primary = context.primary if context.primary is not None else error
        context.primary = primary
        raise primary  # noqa: B904 - preserve the actual original primary/cause.
    finally:
        context.monitoring = False
        if reserved:
            for role, action, args in (
                ("events", _MONITOR.set_events, (tool, 0)),
                *(("local", _MONITOR.set_local_events, (tool, code, 0)) for code in codes),
                *(
                    ("callback", _MONITOR.register_callback, (tool, event, None))
                    for event, _ in callbacks
                ),
                ("tool", _MONITOR.free_tool_id, (tool,)),
            ):
                try:
                    action(*args)
                except BaseException as error:
                    context.last_error = ("monitor_release_" + role, error, tool)
                    context.raw_errors = (*context.raw_errors[-63:], context.last_error)
                    context.invalid = context.original_guard.invalid = True
        samples = []
        for index in range(6):
            try:
                samples.append(_MONITOR.get_tool(index))
            except BaseException as secondary:
                row = ("monitor_final_sample", secondary, index)
                context.last_error = row
                context.raw_errors = (*context.raw_errors[-63:], row)
                context.capture_errors = (*context.capture_errors[-63:], row)
                context.invalid = context.original_guard.invalid = True
                samples.append(secondary)
        context.monitor_after = tuple(samples)
        if context.monitor_after != context.monitor_before:
            context.invalid = context.original_guard.invalid = True
        if primary is None and context.invalid:
            raise context.cleanup_refusal


def _reserve(seed_claim, owner):
    seed = shared._context(seed_claim)
    if (
        owner is not seed.owner
        or seed.active
        or seed.invalid
        or seed.validating
        or seed.source_error is not None
        or seed.capture_errors
        or seed.record is None
        or seed.record is not seed.original_record
        or seed.record.succeeded is not True
        or seed.thread != get_ident()
    ):
        raise SeedInitRejected(
            "Actual closed SEED and exact original WorldReady owner required", stage="seed_owner"
        )
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = _ACTIVE[-1].original_guard.invalid = True
            raise SeedInitRejected("Reentrant same-p INIT transition", stage="reentrant")
        with parameters._LOCK:
            if seed_claim in _CONSUMED:
                raise SeedInitRejected("SEED successor already attempted", stage="consumed")
            claim = object.__new__(SeedInitClaim)
            context = SimpleNamespace(
                claim=claim,
                owner=owner,
                seed_claim=seed_claim,
                seed_context=seed,
                source=seed.source,
                p=seed.p,
                parent_owner=seed.parent_owner,
                parent=seed.parent,
                loaded=seed.loaded,
                parameter_record=seed.parameter_record,
                seed_record=seed.record,
                seed_guard=seed.guard,
                seed_work=seed.work,
                seed_bindings=seed.bindings,
                before_names=seed.before_names,
                before_graph=seed.before_graph,
                before_cm=seed.before_cm,
                seed_after_graph=seed.final_capture,
                thread=get_ident(),
                active=True,
                invalid=False,
                validating=False,
                registered=False,
                guard=SimpleNamespace(
                    thread=get_ident(),
                    active=True,
                    invalid=False,
                    audit_ready=False,
                    directory_depth=0,
                    directory_calls=0,
                    directory_targets=(),
                    filesystem=[],
                ),
                source_error=None,
                record=None,
                original_record=None,
                source_identity=None,
                work=[],
                capture_errors=(),
                raw_errors=(),
                reporting_errors=(),
                last_error=None,
                last_reporting_error=None,
                raw_error_overflow=False,
            )
            context.original_guard = context.guard
            context.exclusion = _stacks(context)
            _CONSUMED[seed_claim] = context
            _ISSUED[claim] = context
            _ACTIVE.append(context)
            return context, claim


def _record(context, succeeded):
    _TIMING_RECORD(context, succeeded)
    record = replace(
        context.record,
        original_seed_record_identity=context.seed_record.identity,
        seed_parameter_graph_identity=_digest(context.seed_after_graph[1]),
        flag_instruction_events=tuple(
            (id(frame), offset, line) for frame, offset, line in context.flag_write_events
        ),
        identity="",
    )
    context.record = replace(record, identity=_digest(record_document(record)))
    context.original_record = context.record


@contextmanager
def seed_to_init(seed_claim, *, original_owner, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(gate) != "1"
        for gate in (
            RELEASE,
            timing.RELEASE,
            parameters.RELEASE,
            parameters.previous.RELEASE,
        )
    ):
        raise SeedInitRejected(
            "Actual retained-world INIT transition remains held", stage="release"
        )
    if type(law_id) is not str or law_id != SEED_INIT_LAW:
        raise SeedInitRejected("Exact same-p SEED-to-INIT source law required", stage="law")
    _dependency()
    hooks, setters, getters = (
        (sys.getprofile(), sys.gettrace()),
        (sys.setprofile, sys.settrace),
        (
            sys.getprofile,
            sys.gettrace,
        ),
    )
    prior = _CONSUMED.get(seed_claim) if type(seed_claim) is shared.WorldConstructionClaim else None
    try:
        context, claim = _reserve(seed_claim, original_owner)
    except BaseException as error:
        actual = (
            _CONSUMED.get(seed_claim) if type(seed_claim) is shared.WorldConstructionClaim else None
        )
        if prior is None and actual is not None and actual.seed_claim is seed_claim:
            actual.source_error = error
            actual.active = actual.original_guard.active = False
            actual.invalid = actual.original_guard.invalid = True
            actual.required_hooks, actual.setters, actual.getters = hooks, setters, getters
            actual.stage = "reservation_return"
            if _ACTIVE and _ACTIVE[-1] is actual:
                _ACTIVE.pop()
            _FAILED.append(actual)
            healthy = False
            try:
                healthy = timing._recover_required(actual)
                healthy = healthy and getters[0]() is hooks[0] and getters[1]() is hooks[1]
            except BaseException as secondary:
                actual.last_error = ("reservation_recovery", secondary, error)
                actual.raw_errors = (actual.last_error,)
            if healthy:
                try:
                    error.seed_init_claim = actual.claim
                except BaseException as secondary:
                    actual.last_error = ("reservation_attachment", secondary, error)
                    actual.raw_errors = (*actual.raw_errors[-63:], actual.last_error)
            try:
                timing._recover_required(actual)
            except BaseException as secondary:
                actual.last_error = ("reservation_terminal_recovery", secondary, error)
                actual.raw_errors = (*actual.raw_errors[-63:], actual.last_error)
        raise
    primary = None
    succeeded = False
    context.required_hooks, context.setters, context.getters = hooks, setters, getters
    context.kind_name = "INIT"
    context.assignments, context.actual_work, context.raw_returns, context.returned = [], [], [], []
    context.frames, context.lines, context.pending = {}, {}, {}
    context.phase, context.phase_fields, context.optional_inputs = None, (), ()
    context.constructor_caller = None
    context.constructor_completed = False
    context.last_assignment = context.last_raw = context.last_call = context.timing_graph = None
    context.primary = context.entry_error = context.observation_error = None
    context.observing = context.inherited_active = False
    context.call_tracing = sys.call_tracing
    context.flag_write_pending, context.flag_write_events = None, []
    context.monitoring, context.monitor_tool = False, None
    context.consumer, context.consumer_module = None, None
    context.cleanup_refusal = SeedInitRejected(
        "Transition issued no success", stage="closure", claim=claim, partial=context
    )
    try:
        # This one initial full SEED validation precedes any timing mutation.
        if (
            shared.validate_closed_seed(seed_claim, original_owner=original_owner)
            is not context.seed_record
        ):
            raise ValueError("Actual successful original closed SEED record required")
        if any(name in vars(context.p) for name in timing.STORES[1:]):
            raise ValueError("No prior INIT/SIM temporal stores may be adopted")
        context.native = context.original_native = timing._native()
        context.kind = context.native.enum.INIT
        context.native_bindings = timing._native_bindings(context.native)
        context.roles = {fn.__code__: name for name, fn in context.native.methods.items()}
        context.wrapper_codes = frozenset(
            fn.__code__ for chain in context.native.chains.values() for fn in chain[:-1]
        )
        context.flag_offsets = frozenset(
            item.offset
            for item in dis.get_instructions(context.native.methods["_init_kludge"])
            if item.opname == "STORE_ATTR" and item.argval == "_run_sim"
        )
        if len(context.flag_offsets) != 1:
            raise ValueError("Single original flag STORE_ATTR required")
        context.store_lines = timing._store_lines()
        context.source_identity, context.bindings = _digest(source_plan()), _bindings()
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in context.exclusion[1:]):
                claims._busy(context.loaded.owner, "retained_world_INIT_conflict")
            for stack, value in context.exclusion[1:]:
                stack.append(value)
            context.registered = True
            _PATHS._install_audit(context.guard)
        _checked(claim)
        with _monitor_flag(context):
            yield claim
    except BaseException as error:
        primary = context.source_error = context.primary if context.primary is not None else error
        raise primary  # noqa: B904 - retain exact original source/caller exception and cause.
    finally:
        # The accepted timing boundary protocol: recover and verify BOTH hooks
        # before each fallible helper/attachment, or skip it and retire directly.
        context.cleanup_blocked, context.cleanup_skipped = False, ()
        for operation in ("finish", "release", "record", "attachment"):
            if operation == "record":
                for stack, value in reversed(context.exclusion[1:]):
                    if stack and stack[-1] is value:
                        stack.pop()
                context.registered = False
                context.active = context.original_guard.active = False
                if _ACTIVE and _ACTIVE[-1] is context:
                    _ACTIVE.pop()
                else:
                    context.invalid = True
                succeeded = bool(
                    succeeded
                    and primary is None
                    and not context.capture_errors
                    and not context.invalid
                    and not context.cleanup_blocked
                )
                if not succeeded:
                    context.invalid = context.original_guard.invalid = True
                    _FAILED.append(context)
            if operation == "attachment" and primary is None:
                continue
            healthy = False
            if not context.cleanup_blocked:
                try:
                    healthy = timing._recover_required(context)
                    healthy = healthy and getters[0]() is hooks[0] and getters[1]() is hooks[1]
                except BaseException as error:
                    context.last_error = ("recovery_" + operation, error, None)
                    context.raw_errors = (*context.raw_errors[-63:], context.last_error)
                if not healthy:
                    context.cleanup_blocked = context.invalid = context.original_guard.invalid = (
                        True
                    )
            if context.cleanup_blocked:
                context.cleanup_skipped += (operation,)
                continue
            try:
                if operation == "finish":
                    succeeded = _FINISH(context)
                elif operation == "release":
                    timing._release(context)
                elif operation == "record":
                    _record(context, succeeded)
                else:
                    primary.seed_init_claim = claim
            except BaseException as error:
                context.last_error = (operation + "_entry_or_return", error, primary)
                context.raw_errors = (*context.raw_errors[-63:], context.last_error)
                context.invalid = context.original_guard.invalid = True
                succeeded = False
        try:
            healthy = timing._recover_required(context)
            healthy = healthy and getters[0]() is hooks[0] and getters[1]() is hooks[1]
        except BaseException as error:
            context.last_error = ("terminal_recovery", error, None)
            context.raw_errors = (*context.raw_errors[-63:], context.last_error)
            healthy = False
        if not healthy:
            context.invalid = context.original_guard.invalid = True
        if primary is not None:
            raise primary
        if not succeeded or context.invalid:
            raise context.cleanup_refusal


def validate_closed_init(claim, *, seed_claim, original_owner):
    context = _context(claim)
    if seed_claim is not context.seed_claim or original_owner is not context.owner:
        raise SeedInitRejected(
            "Original actual SEED claim and WorldReady owner required",
            stage="closed_parent",
            claim=claim,
            partial=context,
        )
    record = _VALIDATE(claim, original_owner=original_owner)
    if (
        record.original_seed_record_identity != context.seed_record.identity
        or record.seed_parameter_graph_identity != _digest(context.seed_after_graph[1])
        or record.flag_instruction_events
        != tuple((id(frame), offset, line) for frame, offset, line in context.flag_write_events)
    ):
        context.invalid = True
        raise SeedInitRejected(
            "Original SEED record/graph identity changed",
            stage="closed_seed",
            claim=claim,
            partial=context,
        )
    return record


def _bindings():
    functions = tuple(
        value
        for value in globals().values()
        if type(value) is FunctionType and value.__globals__ is globals()
    )
    return (), (
        SEED_INIT_LAW,
        RELEASE,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        _CONSUMED,
        _FAILED,
        SeedInitClaim,
        SeedInitRejected,
        SeedInitRecord,
        shared,
        parameters,
        timing,
        _MONITOR,
        _MONITOR_NAME,
        *_MONITOR_APIS,
        *_seed_function_atoms(),
        *_runtime_bindings()[1],
        *shared._bindings()[1],
        *(
            atom
            for fn in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
        *(
            atom
            for fn in (
                SeedInitClaim.parameters.fget,
                SeedInitClaim.check,
                SeedInitClaim.record.fget,
            )
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
        ),
        *(
            atom
            for fn in _RUNTIME_FUNCTIONS
            for atom in (fn, fn.__code__, fn.__globals__, fn.__builtins__)
        ),
    )


def _seed_function_atoms():
    for name in ("validate_closed_seed", "_source", "_bytes", "_context"):
        yield from prefix.parameters.inherited.tissue.aliases._atoms(vars(shared)[name])


def _clone(fn):
    value = FunctionType(fn.__code__, _RUNTIME, fn.__name__, fn.__defaults__, fn.__closure__)
    value.__kwdefaults__ = fn.__kwdefaults__
    return value


def _runtime_bindings():
    values = []
    labels = []
    for original, function, expected in _REUSED:
        if (
            function.__code__ is not original.__code__
            or function.__builtins__ is not original.__builtins__
        ):
            raise ValueError("Original shared timing executable/cache changed")
        if function.__globals__ is not _RUNTIME:
            raise ValueError("Original shared timing private namespace changed")
        namespace = _RUNTIME.get("__builtins__")
        if type(namespace) is timing.ModuleType:
            namespace = vars(namespace)
        if namespace is not function.__builtins__:
            raise ValueError("Shared timing construction/cached builtins mismatch")
        for name, value, is_global in expected:
            if (name in _RUNTIME) is not is_global:
                raise ValueError("Shared timing lookup category changed: " + name)
            namespace = _RUNTIME if is_global else function.__builtins__
            if namespace.get(name) is not value:
                raise ValueError("Shared timing reached binding changed: " + name)
            labels.append((function.__name__, name, is_global))
            values.append(value)
    return tuple(labels), tuple(values)


# Literal source arithmetic is never copied/evaluated here. Reuse the accepted
# parameter graph, actual original source/frame observer and cleanup algorithms
# in a private namespace with the distinct typed claim/history/store boundary.
_RUNTIME = dict(
    vars(timing),
    _context=_context,
    _checked=_checked,
    _source=_source,
    _bytes=_bytes,
    _stores=_stores,
    _observe=_observe,
    _phase=_phase,
    _caller=_caller,
    _stacks=_stacks,
    _digest=_digest,
    record_document=record_document,
    PHASE_CONSTRUCTION_LAW=SEED_INIT_LAW,
    PhaseConstructionClaim=SeedInitClaim,
    PhaseConstructionRejected=SeedInitRejected,
    PhaseParameterRecord=SeedInitRecord,
    _ACTIVE=_ACTIVE,
)
for _name in ("_reject", "_source_guard", "_retain_error", "_capture_error"):
    _RUNTIME[_name] = _clone(vars(timing)[_name])
_TIMING_BYTES = _clone(timing._bytes)
_TIMING_STORES = _clone(timing._stores)
_TIMING_OBSERVE = _clone(timing._observe)
_TIMING_PHASE = _clone(timing._phase)
_TIMING_CALLER = _clone(timing._caller)
_TIMING_RECORD = _clone(timing._record)
_FINISH = _clone(timing._finish)
_ACCOUNT = contextmanager(_clone(timing._account.__wrapped__))
_VALIDATE = _clone(timing.validate_closed_phase)
_RUNTIME_FUNCTIONS = (
    _TIMING_BYTES,
    _TIMING_STORES,
    _TIMING_OBSERVE,
    _TIMING_PHASE,
    _TIMING_CALLER,
    _TIMING_RECORD,
    _FINISH,
    _ACCOUNT.__wrapped__,
    _VALIDATE,
    *(_RUNTIME[name] for name in ("_reject", "_source_guard", "_retain_error", "_capture_error")),
)
_REUSED = tuple(
    (
        original,
        function,
        tuple(
            (
                name,
                function.__globals__.get(name, function.__builtins__.get(name)),
                name in function.__globals__,
            )
            for name in dict.fromkeys(
                i.argval for i in dis.get_instructions(function) if i.opname == "LOAD_GLOBAL"
            )
        ),
    )
    for original, function in (
        (timing._bytes, _TIMING_BYTES),
        (timing._stores, _TIMING_STORES),
        (timing._observe, _TIMING_OBSERVE),
        (timing._phase, _TIMING_PHASE),
        (timing._caller, _TIMING_CALLER),
        (timing._record, _TIMING_RECORD),
        (timing._finish, _FINISH),
        (timing._account.__wrapped__, _ACCOUNT.__wrapped__),
        (timing.validate_closed_phase, _VALIDATE),
        *(
            (vars(timing)[name], _RUNTIME[name])
            for name in ("_reject", "_source_guard", "_retain_error", "_capture_error")
        ),
    )
)
