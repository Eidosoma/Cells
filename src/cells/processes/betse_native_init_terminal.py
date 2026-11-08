"""Held natural INIT terminal on a fresh real ElectricalOwner.

The existing first-step endpoint is never recycled. Parent integration and the
actual molecular iteration issuer are intentionally unbound until reviewed.
Literal numerical bodies are borrowed unchanged; this module owns only the
complete calendar epoch, normal return witnesses and publication lifecycle.
The whole configured calendar must fit the declared bound; no selected stop,
time shortening, prior-owner reuse or native pickle is admitted.
"""

import dis
import hashlib
import os
import struct
import sys
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import CodeType, FrameType, FunctionType, MappingProxyType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary, WeakValueDictionary

from cells.processes import betse_initial_mesh_preparation_cache as retained_cache
from cells.processes import betse_native_init_first_step as base
from cells.processes import betse_native_init_short_history_diagnostics as diagnostics

LAW_ID = "betse_actual_natural_complete_FULL_INIT_before_pickle@1"
SELECTION = "complete_original_INIT_calendar_normal_return_before_pickle"
RELEASE = "CELLS_NATIVE_INIT_TERMINAL_RELEASED"
# The retained demo config has 500 INIT steps. This is only a declaration
# capacity: the entire original calendar must fit, and execution resource
# limits remain independent. The selected short-history endpoint stays at 64.
MAX_ITERATIONS = 512
BASE_SOURCE_SHA256 = "adaf98d4ef08e9c04c36f18dc1d7b89e17d585ab6460443246fc808425614043"
PARENT_SOURCE_SHA256 = 'd48a096de688764b950a56acdf80a94b2a63fb954fe8304b57d36677c1ec49b6'
PARENT_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
PARENT_CLAIM = '_claim_for_terminal_init'
PARENT_CHECK = '_check_terminal_init_authority'
PROPOSED_PARENT_CLAIM = "_claim_for_terminal_init"
PROPOSED_PARENT_CHECK = "_check_terminal_init_authority"
# Proposed names only. No accepted Key API is inferred from these strings.
RUNTIME_SOURCE_SHA256 = '6f0e0432a07076a02f88b997d89ab6fae2e9bc9588da36d3dbca8cf582532412'
RUNTIME_REVIEW_SHA256 = '9fbcbe55bb36523f3025dec86c5c9f1e36360e20a33bfaf6a01eb728065b8e52'
RUNTIME_CONTRACT = 'actual_original_INIT_natural_calendar_terminal_molecules@1'
RUNTIME_MODULE = "cells.processes.betse_native_init_terminal_molecules"
RUNTIME_BEGIN = 'begin_iteration'
RUNTIME_END = 'finish_iteration'
PROPOSED_RUNTIME_BEGIN = "begin_iteration"
PROPOSED_RUNTIME_END = "finish_iteration"
PROPOSED_RUNTIME_CONTRACT = "actual_original_INIT_natural_calendar_terminal_molecules@1"
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()
_SIM_RESERVATIONS, _SIM_RETIRED = WeakKeyDictionary(), WeakKeyDictionary()
_SIM_PENDING, _SIM_FAILURES = WeakKeyDictionary(), []
SIM_RESERVATION_LAW = "completed_natural_INIT_one_shot_SIM_retirement@1"
SIM_RESERVATION_RELEASE = "CELLS_NATIVE_INIT_SIM_RETIREMENT_RELEASED"


class InitTerminalRejected(base.FirstStepRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    electrical_owner: object
    parent_identity: str
    source_identity: str
    selection: str
    operator_mode: str
    iterations: int
    maximum: int
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A natural INIT terminal request cannot be supplied or hydrated")


@dataclass(frozen=True, slots=True)
class Iteration:
    ordinal: int
    source_time: object
    sampled: bool
    after: object
    work_end: int
    callbacks_end: int
    molecular_record: object
    diagnostics: object = None


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    after: object
    calendar: object
    sampled: object
    dt: object
    iterations: tuple
    work: tuple
    helpers: tuple
    callbacks: tuple
    raw_returns: tuple
    rng_before: tuple
    rng_after: tuple
    source_completed: bool
    loop_returned: bool
    context_returned: bool
    selected_stop: bool
    initial_diagnostics: object
    identity: str
    c_calls: tuple = ()
    stores: tuple = ()


def _count(value):
    if type(value) is not int or not 1 <= value <= MAX_ITERATIONS:
        raise ValueError("Explicit natural INIT terminal integer count in [1,512] required")
    return value


def _configured_count(value, maximum):
    bound = _count(maximum)
    if type(value) is not int or not 1 <= value <= bound:
        raise ValueError("Complete original INIT count exceeds declared maximum")
    return value


@dataclass(frozen=True, slots=True)
class NaturalTerminalStatus:
    child: object
    calendar_raw: tuple
    loop_frame: object
    context_frame: object
    loop_raw: tuple
    context_raw: tuple
    exception_arguments: tuple
    selected_stop: bool
    before_native_pickle: bool


def source_plan():
    return dict(
        law=LAW_ID,
        selection=SELECTION,
        max_iterations=MAX_ITERATIONS,
        original=base.source_plan(),
        base_source=BASE_SOURCE_SHA256,
        one_fresh_parent_one_original_loop=True,
        original_calendar_dt_sampled_set_and_objects_unchanged=True,
        completed_first_step_or_short_history_owner_is_not_a_parent=True,
        no_storage_reset_or_parameter_retrofit_between_iterations=True,
        snapshot_projection="original retained parameter roots plus continuing participant roots",
        retained_columns=(
            "fresh full live snapshot/validation each time; exact immutable column bytes/layout "
            "may share terminal-local storage; descriptors and live alias checks unchanged"
        ),
        runtime_binding_adapter="one pinned metadata call binds the separate terminal provider",
        required_parent=(PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256, PARENT_CLAIM, PARENT_CHECK),
        required_runtime=(RUNTIME_SOURCE_SHA256, RUNTIME_REVIEW_SHA256, RUNTIME_CONTRACT),
        runtime_entry_names_unadopted=(RUNTIME_BEGIN, RUNTIME_END),
        natural_calendar_return_and_context_exit_required=True,
        before_native_pickle=True,
        physical_checkpoint_SIM_or_scientific_admission=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        source=value.source_identity,
        selection=value.selection,
        operator_mode=value.operator_mode,
        iterations=_configured_count(value.iterations, value.maximum),
        maximum=_count(value.maximum),
    )


def _ready():
    path = Path(base.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != BASE_SOURCE_SHA256:
        raise InitTerminalRejected("Reviewed original source engine changed", stage="base_source")
    if (
        not all(
            base.previous.storage.previous._pin(value)
            for value in (
                PARENT_SOURCE_SHA256,
                PARENT_REVIEW_SHA256,
                RUNTIME_SOURCE_SHA256,
                RUNTIME_REVIEW_SHA256,
            )
        )
        or PARENT_CLAIM != PROPOSED_PARENT_CLAIM
        or PARENT_CHECK != PROPOSED_PARENT_CHECK
        or RUNTIME_BEGIN != PROPOSED_RUNTIME_BEGIN
        or RUNTIME_END != PROPOSED_RUNTIME_END
        or RUNTIME_CONTRACT != PROPOSED_RUNTIME_CONTRACT
    ):
        raise InitTerminalRejected(
            "Actual parent and per-iteration molecular contracts remain unadopted",
            stage="integration_held",
        )
    parent = base.previous
    raw = Path(parent.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SOURCE_SHA256:
        raise InitTerminalRejected("Electrical producer changed", stage="producer")
    parent.interfaces._source_interface(
        parent, raw, Path(parent.__file__), (PARENT_CLAIM, PARENT_CHECK)
    )
    claim, check = vars(parent).get(PARENT_CLAIM), vars(parent).get(PARENT_CHECK)
    if any(
        type(fn) is not FunctionType or fn.__globals__ is not vars(parent) for fn in (claim, check)
    ):
        raise InitTerminalRejected("Actual parent hook functions unavailable", stage="hook")
    return base._ParentBinding(
        parent, claim, check, tuple(parent._parent_atoms(fn) for fn in (claim, check))
    )


def _parent(binding):
    if binding.module is not base.previous:
        raise ValueError("Actual original electrical module required")
    for name, fn, saved in zip(
        (PARENT_CLAIM, PARENT_CHECK), (binding.claim, binding.check), binding.atoms, strict=True
    ):
        if vars(binding.module).get(name) is not fn:
            raise ValueError("Adopted parent function changed")
        base._same(binding.module._parent_atoms(fn), saved)


def from_electrical(owner, *, maximum, law_id):
    with _LOCK:
        if _ACTIVE:
            base._reject(_ACTIVE[-1], "Reentrant natural INIT declaration")
    bound = _count(maximum)
    if law_id != LAW_ID or type(law_id) is not str:
        raise InitTerminalRejected("Explicit natural INIT law required", stage="law")
    binding = _ready()
    with _LOCK:
        if _ACTIVE:
            base._reject(_ACTIVE[-1], "Reentrant natural INIT declaration")
        if type(owner) is not base.previous.ElectricalOwner or owner in _RETIRED:
            raise InitTerminalRejected("Fresh actual ElectricalOwner required", stage="owner")
        parent = binding.module._authority(owner)
        count = _configured_count(parent.p.init_tsteps, bound)
        value = Request(
            owner,
            parent.trial.identity,
            base._digest(source_plan()),
            SELECTION,
            base._operator_mode(parent.cells),
            count,
            bound,
            "",
        )
        value = replace(value, identity=base._digest(request_record(value)))
        _REQUESTS[value] = (
            parent,
            parent.trial,
            binding.module._snapshot(parent),
            binding.module._graph(parent),
        )
        return value


class _Timeline:
    """Ordered metadata only; never a parent, runtime claim or frame resumer."""

    def __init__(self, count):
        self.target, self.completed, self.current = _count(count), 0, None
        self.records, self.invalid = [], False

    def begin(self, source_time, sampled):
        if (
            self.invalid is not False
            or type(self.completed) is not int
            or type(self.target) is not int
            or self.current is not None
            or self.completed >= self.target
            or type(sampled) is not bool
        ):
            self.invalid = True
            raise ValueError("Out-of-order, repeated or over-bound iteration entry")
        self.current = (self.completed, source_time, sampled)
        return self.current

    def end(self, record):
        if self.invalid is not False or self.current is None or type(record) is not Iteration:
            self.invalid = True
            raise ValueError("Original active iteration record required")
        ordinal, label, sampled = self.current
        if (
            type(record.ordinal) is not int
            or record.ordinal != ordinal
            or record.source_time is not label
            or record.sampled is not sampled
        ):
            self.invalid = True
            raise ValueError("Original ordinal/time/sample identity changed")
        self.records.append(record)
        self.completed += 1
        self.current = None

    def token(self):
        current = (
            None
            if self.current is None
            else (
                self.current[0],
                type(self.current[0]),
                id(self.current[1]),
                type(self.current[1]),
                struct.pack("!d", self.current[1]),
                self.current[2],
                type(self.current[2]),
            )
        )
        rows = tuple(
            (
                id(row),
                row.ordinal,
                type(row.ordinal),
                id(row.source_time),
                type(row.source_time),
                struct.pack("!d", row.source_time),
                row.sampled,
                type(row.sampled),
                row.after.identity,
                row.work_end,
                type(row.work_end),
                row.callbacks_end,
                type(row.callbacks_end),
                id(row.molecular_record),
            )
            for row in self.records
        )
        return (
            self.target,
            type(self.target),
            self.completed,
            type(self.completed),
            current,
            rows,
            self.invalid,
            type(self.invalid),
        )


class _CallbackClaims:
    """Per-iteration callsite keys without clearing any earlier claim."""

    def __init__(self, timeline, *, roots=False):
        self.timeline, self.roots, self.data = timeline, roots, set()

    def _key(self, item):
        method = item if self.roots else item[1]
        if method != "progressed_next":
            return ("calendar", item)
        if self.timeline.current is None:
            raise ValueError("Sampled callback outside its actual iteration")
        return (self.timeline.current[0], item)

    def __contains__(self, item):
        return self._key(item) in self.data

    def add(self, item):
        key = self._key(item)
        if key in self.data:
            raise ValueError("Original callback epoch already claimed")
        self.data.add(key)


def _local(context):
    if hashlib.sha256(Path(base.__file__).read_bytes()).hexdigest() != BASE_SOURCE_SHA256:
        raise ValueError("Original observer-engine producer changed")
    if (
        context.runtime is not context.runtime_record
        or context.timeline is not context.timeline_record
    ):
        raise ValueError("Original natural INIT terminal engine/ledger replaced")
    if context.loop_span is not None or context.loop_frame is not None:
        _checked_loop_span(context)
    if (
        context.request.iterations
        != _configured_count(context.p.init_tsteps, context.request.maximum)
        or context.selected_stopped is not False
        or context.stopping is not False
        or context.request.iterations != _count(context.timeline.target)
        or type(context.timeline.completed) is not int
        or type(context.timeline.invalid) is not bool
    ):
        raise ValueError("Bound request count changed")
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
    ):
        raise ValueError("Actual natural INIT terminal request/consumption links changed")
    if _RETIRED.get(context.request.electrical_owner) is not context:
        raise ValueError("Original electrical retirement link changed")
    if context.request.identity != base._digest(request_record(context.request)):
        raise ValueError("Original natural INIT terminal request identity changed")
    if (
        context.callback_claimed_sites is not context.callback_claims_record
        or context.callback_roots is not context.callback_roots_record
        or context.callback_claimed_sites.timeline is not context.timeline
        or context.callback_roots.timeline is not context.timeline
    ):
        raise ValueError("Original callback epoch ledgers replaced")
    for name, function, atoms in context.local_functions:
        if globals().get(name) is not function:
            raise ValueError("Natural INIT terminal local function replaced: " + name)
        base._same(context.atoms(function), atoms)


def _bootstrap(context):
    _local(context)
    return context.runtime["_base_bootstrap"](context)


def _guard(context):
    _local(context)
    return context.runtime["_base_guard"](context)


def _epoch(context):
    identity, graph, streams = context.runtime["_base_epoch"](context)
    protocol = (
        context.timeline.token(),
        frozenset(context.callback_claimed_sites.data),
        frozenset(context.callback_roots.data),
        context.loop_span,
    )
    return identity, (graph[0], (graph[1], protocol)), streams


def _callback_enter(context, row):
    frame = row["frame"]
    if frame.f_back is context.loop_frame:
        current = context.timeline.current
        if current is None or not current[2] or frame.f_back.f_locals.get("t") is not current[1]:
            context.runtime["_reject"](context, "Callback outside actual sampled source epoch")
    return context.runtime["_base_callback_enter"](context, row)


def _runtime(context):
    api, claim = context.terminal_runtime, context.molecule_claim
    if (
        type(api) is not ModuleType
        or sys.modules.get(RUNTIME_MODULE) is not api
        or context.molecule is not context.parent.molecule
        or claim is None
        or getattr(api, "LAW_ID", None) != RUNTIME_CONTRACT
    ):
        raise ValueError("Actual enabled molecular runtime claimant required")
    path = Path(api.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != RUNTIME_SOURCE_SHA256:
        raise ValueError("Actual adopted runtime producer changed")
    return api, claim


def _begin(context, frame):
    if frame is not context.loop_frame or context.timeline.current is not None:
        return
    ordinal = context.timeline.completed
    if ordinal >= context.request.iterations or "t" not in frame.f_locals:
        context.runtime["_reject"](context, "Unowned next iteration attempted entry")
    label = frame.f_locals["t"]
    if struct.pack("!d", label) != struct.pack("!d", context.time_steps[ordinal]):
        context.runtime["_reject"](context, "Original calendar ordinal/label changed")
    current = context.timeline.begin(label, label in context.sampled)
    api, claim = _runtime(context)
    context.last_iteration_begin = (frame, current)
    context.iteration_claim = getattr(api, RUNTIME_BEGIN)(
        claim, child=context, ordinal=ordinal, source_time=label, source_frame=frame
    )


def _end(context, frame):
    current = context.timeline.current
    if current is None:
        return
    api, claim = _runtime(context)
    context.last_iteration_end = (frame, current)
    evidence = getattr(api, RUNTIME_END)(
        claim, child=context, ordinal=current[0], source_time=current[1], source_frame=frame
    )
    # Retain raw completed provider output before fallible observation/sealing.
    context.last_iteration_raw = evidence
    after = _retain_snapshot(context, context.runtime["_snapshot"](context))
    try:
        summary = _diagnostics(context)
    except BaseException as capture:
        context.runtime["_capture"](
            context, "iteration_diagnostics", capture, (frame, after, evidence)
        )
        raise base._ObservationStop(
            "Iteration diagnostics incomplete", stage="capture", partial=context
        ) from capture
    context.timeline.end(
        Iteration(
            current[0],
            current[1],
            current[2],
            after,
            len(context.work),
            len(context.callback_calls),
            evidence,
            summary,
        )
    )


def _loop_boundary(context, frame):
    if (
        frame is not context.loop_frame
        or frame.f_code is not context.loop_code
        or frame.f_lasti != context.loop_offset
    ):
        return
    _guard(context)
    _end(context, frame)
    context.loop_visits += 1
    if context.loop_visits != context.timeline.completed + 1:
        context.runtime["_reject"](context, "Original natural loop boundary changed")
    if context.timeline.completed > context.request.iterations:
        context.runtime["_reject"](context, "Original complete calendar overrun")
    # The final FOR_ITER executes normally; no exception or iterator replacement.
    if context.timeline.completed == context.request.iterations:
        context.source_time_label = frame.f_locals.get("t")


def _checked_loop_span(context):
    """Exhaustion retains this same span; absence never denotes completion."""
    span = context.loop_span
    if (
        type(span) is not tuple
        or len(span) != 3
        or span is not context.loop_span_record
        or span[0] is not context.loop_code
        or type(span[1]) is not int
        or type(span[2]) is not int
        or span[1] != context.loop_offset
        or span[2] <= span[1]
    ):
        context.runtime["_reject"](context, "Actual sealed outer FOR_ITER span required")
    return span


def _observe(context, frame, event, arg):
    scope = context.runtime
    if frame.f_code in context.molecule_codes:
        admitted = context.molecule_admissions.get(id(frame))
        returned = context.molecule_returns.get(id(frame))
        if (event != "call" or admitted is not frame) and (
            event != "return" or returned is not frame
        ):
            context.terminal_runtime.observe_runtime(
                context.molecule_claim, child=context, frame=frame, event=event, arg=arg
            )
            if event == "call":
                context.molecule_admissions[id(frame)] = frame
            elif event == "return":
                context.molecule_returns[id(frame)] = frame
        if event in ("call", "c_call", "c_return", "c_exception"):
            return
    if event == "call":
        scope["_admit"](context, frame)
    row = context.frames.get(id(frame))
    if row is None:
        return
    if frame is context.loop_frame and event in ("call", "line", "opcode"):
        _checked_loop_span(context)
    if event in ("call", "line"):
        # A profile-call admission can precede trace-call delivery. Re-arm at
        # each trace boundary before original bytecode/iterator advancement.
        frame.f_trace_opcodes = True
    if event == "opcode":
        _guard(context)
        _loop_boundary(context, frame)
    if (
        frame is context.loop_frame
        and event == "line"
        and context.timeline.current is None
        and context.loop_visits > context.timeline.completed
    ):
        span = _checked_loop_span(context)
        if span[1] < frame.f_lasti < span[2]:
            _begin(context, frame)
    if event == "exception" and arg[1] is context.selected_stop:
        context.entry_error = arg[1]
        context.invalid = True
        raise arg[1]
    if event == "exception":
        protocol = row.get("name") == "solver_context_exit" and type(arg[1]) is StopIteration
        if not protocol:
            scope["_pending_exception"](context, frame, arg[1])
            context.last_source_error = (frame, arg[1])
    if event == "return" and not row["returned"]:
        context.last_raw = (frame, arg)
        error = context.pending.get(id(frame))
        normal = base.previous.storage.previous.previous.previous._normal_return(frame)
        if not normal and error is not None and error is not context.selected_stop:
            row["unwound_error"] = error
            if frame is context.setup_frame:
                scope["_source_error"](context, frame, error)
        elif normal:
            row["handled_error"] = error
            context.pending.pop(id(frame), None)
        try:
            context.raw_returns.append(context.last_raw)
            context.locals[id(frame)] = dict(frame.f_locals)
            row["returned"], row["suspended"] = True, scope["name_is_yield"](frame)
        except BaseException as capture:
            scope["_capture"](context, "return_or_unwind", capture, context.last_raw)
    if event == "line":
        _guard(context)
        if frame is context.setup_frame and "time_steps" in frame.f_locals:
            raw = context.calendar_raw
            if (
                type(raw) is not tuple
                or len(raw) != 3
                or frame.f_locals["time_steps"] is not raw[0]
                or frame.f_locals.get("time_steps_sampled") is not raw[1]
                or frame.f_locals.get("solver_context") is not raw[2]
                or raw[2] is not context.solver_context
            ):
                scope["_reject"](
                    context, "Original complete calendar/sample/context lineage changed"
                )
            if len(raw[0]) != context.request.iterations:
                scope["_reject"](context, "Complete configured calendar length changed")


def _bind_runtime(context):
    descendant = getattr(context.parent, "terminal_init_descendant", None)
    if descendant is None or not hasattr(descendant, "molecule_claim"):
        raise InitTerminalRejected(
            "Actual repeated-runtime claim unavailable", stage="runtime_held", partial=context
        )
    api, claim = sys.modules.get(RUNTIME_MODULE), descendant.molecule_claim
    context.terminal_runtime = api
    context.molecule, context.molecule_claim = context.parent.molecule, claim
    context.molecule_record = None
    _runtime(context)
    names = (
        "validate_runtime_active",
        "validate_runtime",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "runtime_wrapper_guard",
        "runtime_dispatch",
        "observes_runtime_frame",
        "observe_runtime",
        "finish_runtime",
        "runtime_failed_context",
        "session_of",
        "session_provider",
        "validate_iteration",
        RUNTIME_BEGIN,
        RUNTIME_END,
    )
    path = Path(api.__file__)
    base.previous.interfaces._source_interface(api, path.read_bytes(), path, names)
    projector_path = Path(context.molecule.__file__)
    base.previous.interfaces._source_interface(
        context.molecule, projector_path.read_bytes(), projector_path, ("project_state",)
    )
    functions = tuple((api, name, vars(api).get(name)) for name in names)
    functions += ((context.molecule, "project_state", context.molecule.project_state),)
    if any(
        type(fn) is not FunctionType or fn.__globals__ is not vars(provider)
        for provider, _, fn in functions
    ):
        raise InitTerminalRejected(
            "Actual adopted runtime functions unavailable", stage="runtime_held", partial=context
        )
    if api.validate_runtime_active(claim, child=context) is not claim:
        raise ValueError("Different actual natural INIT terminal runtime claimant")
    context.terminal_runtime_functions = functions
    context.terminal_runtime_function_atoms = tuple(context.atoms(fn) for _, _, fn in functions)
    context.terminal_runtime_source_sha256 = RUNTIME_SOURCE_SHA256
    if (
        api.session_of(claim, child=context) is not context.parent.molecule_session
        or api.session_provider(claim, child=context) is not context.molecule
    ):
        raise ValueError("Original session and separate natural-terminal provider required")
    context.molecule_members, context.molecule_expressions = (
        api.runtime_members(claim),
        api.runtime_codes(claim),
    )
    context.molecule_permissions = api.runtime_permissions(claim)
    if type(context.molecule_members) is not tuple or any(
        type(fn) is not FunctionType for fn in context.molecule_members
    ):
        raise ValueError("Actual original terminal-runtime callable roster required")
    if type(context.molecule_expressions) is not tuple or any(
        type(code) is not CodeType for code in context.molecule_expressions
    ):
        raise ValueError("Actual original terminal-runtime expression roster required")
    context.molecule_codes = frozenset(
        (
            *context.molecule_expressions,
            *(
                code
                for fn in context.molecule_members
                for code in base.previous.storage.previous.previous.previous._code_tree(fn.__code__)
            ),
        )
    )
    context.allowed_codes |= context.molecule_codes
    context.permissions = base.previous.storage._merge_permissions(
        context.permissions, context.molecule_permissions
    )


def _diagnostics(context):
    """Observation on actual issued holders; no parameter/array substitution."""

    def plain(value):
        if type(value) in (int, float):
            return value
        if type(value) in (list, tuple):
            return tuple(plain(item) for item in value)
        if type(value) is context.numpy.ndarray:
            return plain(value.tolist())
        if isinstance(value, context.numpy.generic):
            return plain(value.item())
        raise TypeError("Original numeric diagnostic field unavailable")

    return diagnostics.amounts(
        cells=plain(context.sim.cc_cells),
        environment=plain(context.sim.cc_env),
        cell_volumes=plain(context.cells.cell_vol),
        ecm_volumes=plain(context.cells.ecm_vol),
        voltage=plain(context.sim.vm),
        charges=plain(context.sim.zs),
        faraday=plain(context.p.F),
    )


def _terminal_bindings(context):
    """Bind the separate runtime without changing the original session provider."""
    api, claim = _runtime(context)
    values = [api, claim, context.molecule, context.molecule_permissions, context.molecule_codes]
    for (provider, name, function), expected in zip(
        context.terminal_runtime_functions, context.terminal_runtime_function_atoms, strict=True
    ):
        if (
            provider is not api
            and provider is not context.molecule
            or vars(provider).get(name) is not function
        ):
            raise ValueError("Actual terminal runtime/session function replaced: " + name)
        current = context.atoms(function)
        base._same(current, expected)
        values.extend((provider, name, *current))
    if (
        api.session_of(claim, child=context) is not context.parent.molecule_session
        or api.session_provider(claim, child=context) is not context.molecule
    ):
        raise ValueError("Original terminal molecular session/provider association changed")
    base._same(api.runtime_members(claim), context.molecule_members)
    base._same(api.runtime_codes(claim), context.molecule_expressions)
    if api.runtime_permissions(claim) is not context.molecule_permissions:
        raise ValueError("Original terminal runtime permission association changed")
    if context.molecule_record is None:
        if api.validate_runtime_active(claim, child=context) is not claim:
            raise ValueError("Original active terminal runtime claim changed")
    elif api.validate_runtime(claim, child=context) is not context.molecule_record:
        raise ValueError("Original closed terminal runtime record changed")
    for function in context.molecule_members:
        values.extend(context.atoms(function))
    values.extend(context.molecule_expressions)
    return tuple(values)


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    scope = context.runtime
    scope["_check"](context)
    initial = base.previous.storage.previous.previous.previous
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
        scope["_reject"](context, "Actual once-claimed terminal source dispatch required")
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
            if error is context.selected_stop:
                context.entry_error = error
                context.invalid = True
            scope["_source_error"](context, invocation["body"], error)
            raise
        context.last_method_return = (name, value)
        if name == "_plot_loop":
            context.calendar_raw = value
        if name == "_run_sim_core_loop":
            context.loop_returned = True
        scope["_check"](context)
        return value
    finally:
        if context.invocations and context.invocations[-1] is invocation:
            context.invocations.pop()
        else:
            context.invalid = True


def _claim_wrapper(context, original, frame):
    return context.runtime["_base_claim_wrapper"](context, original, frame)


def _check_ancestor_metadata(context):
    return context.runtime["_base_check_ancestor_metadata"](context)


def _mutation_contract(context):
    """Retain original stores and the actual runtime's holder permissions.

    Runtime binding authenticates the molecular tuple before source entry.
    Ancestor validation must see the same identity union as the live engine;
    this declaration itself does not issue a claim or authenticate a provider.
    """
    return base.previous.storage._merge_permissions(
        context.runtime["_base_mutation_contract"](context), context.molecule_permissions
    )


def _snapshot(context, *, stable=False):
    """Keep genuine pre-phase wrapper references in the private history view.

    The original first-step engine remains unchanged. This metadata projection
    uses the same complete root roster as Completion and storage; no parameter
    object is replaced, flattened, hydrated or granted new authority.
    """
    completion = base.previous.storage.previous
    initial = completion.previous.previous
    objects = completion._objects(context.parent)
    projector = initial._projector(context.parent.init_parent)
    projector.objects = [*projector.objects, *objects]
    project, values = initial.core._LITERAL._project, []
    for role, actual in context.objects:
        ignored = (
            next((fields for owner, fields in context.permissions if owner is actual), frozenset())
            if stable
            else frozenset()
        )
        fields = {key: value for key, value in vars(actual).items() if key not in ignored}
        if getattr(context, "molecule_claim", None) is not None:
            fields = context.molecule.project_state(context.parent.molecule_session, fields)
        values.append((role, project(projector, fields)))
    return completion._scope(context.parent).snapshot(tuple(values))


def _column_bytes(value):
    """Require a complete C-order column backed only by immutable bytes.

    A write-protected view of mutable storage is insufficient. This follows
    the existing frozen-column representation; it never freezes an unowned
    buffer or changes an array's flags, shape, layout or contents.
    """
    numpy = retained_cache.np
    if (
        type(value) is not numpy.ndarray
        or value.flags.writeable
        or not value.flags.c_contiguous
        or value.dtype.hasobject
        or value.dtype.kind not in "biufc"
    ):
        raise ValueError("Complete immutable owned cache column required")
    node, seen = value, set()
    while type(node) is numpy.ndarray:
        if (
            id(node) in seen
            or len(seen) >= 16
            or node.flags.writeable
            or not node.flags.c_contiguous
            or node.nbytes != value.nbytes
        ):
            raise ValueError("Complete immutable cache column base required")
        seen.add(id(node))
        parent = node.base
        if type(parent) is numpy.ndarray and node.ctypes.data != parent.ctypes.data:
            raise ValueError("Unshifted immutable cache column storage required")
        node = parent
    if type(node) is not bytes or len(node) != value.nbytes:
        raise ValueError("Actual whole immutable bytes backing required")
    return node


def _retain_snapshot(context, fresh):
    """Share retained storage only AFTER a fresh complete live capture.

    The weak pool cannot retain discarded snapshots. Its keys contain exact
    bytes, dtype, shape and strides, so hashes alone never establish equality.
    Shared immutable observation storage conveys no native alias or parent
    authority; all original live graph/owner validation remains independent.
    """
    context.last_retention_raw = fresh
    if (
        type(context.retained_columns) is not WeakValueDictionary
        or context.retained_columns is not context.retained_columns_record
    ):
        raise ValueError("Original terminal-local immutable column pool required")
    if (
        type(fresh) is not retained_cache.Cache
        or type(fresh.columns) is not tuple
        or any(
            type(c) is not retained_cache.CacheColumn
            or type(c.name) is not str
            or type(c.values) is not retained_cache.np.ndarray
            for c in fresh.columns
        )
    ):
        raise ValueError("Actual complete typed cache columns required")
    retained_cache.validate(fresh)
    columns, saved, allocated = [], 0, 0
    for column in fresh.columns:
        value = column.values
        raw = _column_bytes(value)
        key = (value.dtype.str, tuple(value.shape), tuple(value.strides), raw)
        previous = context.retained_columns.get(key)
        if previous is None:
            context.retained_columns[key] = value
            chosen, allocated = value, allocated + len(raw)
        else:
            old = _column_bytes(previous)
            if (
                old != raw
                or previous.dtype.str != value.dtype.str
                or previous.shape != value.shape
                or previous.strides != value.strides
            ):
                raise ValueError("Retained immutable cache column changed")
            # Share bytes only. Each observation retains its own ndarray
            # header, so changing a header's shape/dtype cannot rewrite
            # another snapshot's array metadata.
            chosen = retained_cache.np.frombuffer(old, dtype=value.dtype).reshape(value.shape)
            saved += len(raw)
        columns.append(retained_cache.CacheColumn(column.name, chosen))
    result = retained_cache.Cache(
        fresh.descriptor_json, tuple(columns), fresh.all_finite, fresh.identity
    )
    retained_cache.validate(result)
    # Plain accounting, never the raw fresh column arrays: keeping every
    # pre-sharing copy here would defeat the storage bound.
    context.retention_work.append((fresh.identity, len(columns), allocated, saved))
    return result


def _namespace(context):
    """Retain the exact outer FOR_ITER exit, without changing native code."""
    context.runtime["_base_namespace"](context)
    _bind_loop_span(context)


def _bind_loop_span(context):
    """Bind once from the actual selected code, also for declared toy inputs."""
    if (
        getattr(context, "loop_span", None) is not None
        or getattr(context, "loop_span_record", None) is not None
    ):
        raise ValueError("Original outer loop span already bound")
    if type(context.loop_code) is not CodeType or type(context.loop_offset) is not int:
        raise ValueError("Actual loop code and exact FOR_ITER offset required")
    loops = [
        instruction
        for instruction in dis.get_instructions(context.loop_code)
        if instruction.offset == context.loop_offset and instruction.opname == "FOR_ITER"
    ]
    if (
        len(loops) != 1
        or type(loops[0].argval) is not int
        or loops[0].argval <= context.loop_offset
    ):
        raise ValueError("Exact forward exit of the original outer loop required")
    context.loop_span = context.loop_span_record = (
        context.loop_code,
        context.loop_offset,
        loops[0].argval,
    )


def _engine(context):
    """Private observer namespace, not a module/owner or hydrated state."""
    raw = Path(base.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != BASE_SOURCE_SHA256:
        raise ValueError("Read-only original source engine changed")
    import ast

    tree = ast.parse(raw)
    compiled = compile(raw, str(Path(base.__file__)), "exec", dont_inherit=True)
    codes = {value.co_name: value for value in compiled.co_consts if hasattr(value, "co_name")}
    nodes = {node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)}
    scope = dict(
        vars(base),
        __name__=__name__,
        __file__=__file__,
        Request=Request,
        SELECTION=SELECTION,
        _REQUESTS=_REQUESTS,
        _CONSUMED=_CONSUMED,
        _RETIRED=_RETIRED,
        _ISSUED=_ISSUED,
        _ACTIVE=_ACTIVE,
        FirstStepRejected=InitTerminalRejected,
        source_plan=source_plan,
        request_record=request_record,
    )
    for name, fn in vars(base).items():
        if type(fn) is FunctionType and fn.__globals__ is vars(base):
            if fn.__code__ != codes.get(name) or fn.__closure__ is not None:
                raise ValueError("Original reusable observer function changed: " + name)
            base.previous._native_defaults(fn, nodes[name])
            scope[name] = FunctionType(fn.__code__, scope, name, fn.__defaults__, fn.__closure__)
            scope[name].__kwdefaults__ = fn.__kwdefaults__
    for name in (
        "_bootstrap",
        "_guard",
        "_epoch",
        "_callback_enter",
        "_observe",
        "_claim_wrapper",
        "_check_ancestor_metadata",
        "_mutation_contract",
        "_snapshot",
        "_namespace",
    ):
        scope["_base" + name] = scope[name]
        scope[name] = globals()[name]
    scope["_loop_boundary"] = _loop_boundary
    # Natural completion has its own metadata dispatcher. Scientific method
    # bodies, callback transports and inherited observation remain read-only.
    scope["_dispatch"] = _dispatch
    # Adapt exactly one metadata provider lookup. No source/numerical body or
    # existing provider module is altered or presented as the terminal issuer.
    binding_node = ast.parse(ast.unparse(nodes["_binding"])).body[0]
    matches = [
        node
        for node in ast.walk(binding_node)
        if isinstance(node, ast.Call)
        and ast.unparse(node.func) == "previous.storage._molecule_runtime_bindings"
    ]
    if len(matches) != 1:
        raise ValueError("Exactly one inherited runtime metadata binding call required")
    matches[0].func = ast.copy_location(
        ast.Name(id="_terminal_bindings", ctx=ast.Load()), matches[0].func
    )
    binding_tree = ast.fix_missing_locations(ast.Module(body=[binding_node], type_ignores=[]))
    binding_code = next(
        code
        for code in compile(binding_tree, __file__, "exec", dont_inherit=True).co_consts
        if type(code) is CodeType and code.co_name == "_binding"
    )
    scope["_terminal_bindings"] = _terminal_bindings
    scope["_binding"] = FunctionType(binding_code, scope, "_binding")
    scope["_ready"], scope["_check_parent"] = _ready, _parent
    scope["source_plan"], scope["request_record"] = source_plan, request_record
    scope["from_electrical"], scope["prepare"], scope["_authority"] = (
        from_electrical,
        prepare,
        _authority,
    )
    function = base._account.__wrapped__
    if function.__code__ != codes["_account"] or function.__globals__ is not vars(base):
        raise ValueError("Original dual-observer context body changed")
    base.previous._native_defaults(function, nodes["_account"])
    scope["_account"] = contextmanager(
        FunctionType(
            function.__code__, scope, function.__name__, function.__defaults__, function.__closure__
        )
    )
    return scope


def trial_record(value):
    return dict(
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        after=value.after.identity,
        calendar=value.calendar.identity,
        sampled=value.sampled.identity,
        dt=value.dt.identity,
        iterations=tuple(
            (
                row.ordinal,
                struct.pack("!d", row.source_time).hex(),
                row.sampled,
                row.after.identity,
                row.work_end,
                row.callbacks_end,
                id(row.molecular_record),
                None if row.diagnostics is None else asdict(row.diagnostics),
            )
            for row in value.iterations
        ),
        work=len(value.work),
        helpers=len(value.helpers),
        callbacks=len(value.callbacks),
        c_calls=len(value.c_calls),
        stores=len(value.stores),
        source_completed=value.source_completed,
        loop_returned=value.loop_returned,
        context_returned=value.context_returned,
        selected_stop=value.selected_stop,
        rng_before=value.rng_before,
        rng_after=value.rng_after,
        initial_diagnostics=asdict(value.initial_diagnostics),
    )


def _normal_witness(context, role, frame, function):
    """Find the retained return tuple of one actually admitted normal frame."""
    if (
        type(frame) is not FrameType
        or type(function) is not FunctionType
        or frame.f_code is not function.__code__
        or frame.f_globals is not function.__globals__
    ):
        raise ValueError("Actual terminal source frame/code/namespace required: " + role)
    row = context.frames.get(id(frame))
    if (
        type(row) is not dict
        or row.get("frame") is not frame
        or row.get("code") is not frame.f_code
        or row.get("globals") is not frame.f_globals
        or row.get("name") != role
        or row.get("body_started") is not True
        or row.get("returned") is not True
        or row.get("suspended") is not False
        or row.get("unwound_error") is not None
        or not any(value is row for value in context.work)
        or not base.previous.storage.previous.previous.previous._normal_return(frame)
    ):
        raise ValueError("Actual admitted normal terminal source return required: " + role)
    matches = [
        (index, raw)
        for index, raw in enumerate(context.raw_returns)
        if type(raw) is tuple and len(raw) == 2 and raw[0] is frame
    ]
    if len(matches) != 1:
        raise ValueError("Exactly one retained terminal return tuple required: " + role)
    return matches[0]


def _natural_parts(context):
    """Authenticate complete, unmodified source exhaustion and normal context exit."""
    raw = context.calendar_raw
    if (
        context.primary is not None
        or context.capture_error is not None
        or context.entry_error is not None
        or context.invalid is not False
        or context.observing is not False
        or context.selected_stopped is not False
        or context.stopping is not False
        or context.loop_returned is not True
        or context.cleanup_errors
        or getattr(context, "cleanup_journal_error", None) is not None
        or context.hooks_safe is not True
        or context.timeline.invalid is not False
        or context.timeline.current is not None
        or context.timeline.completed != context.request.iterations
        or len(context.timeline.records) != context.request.iterations
        or context.request.iterations
        != _configured_count(context.p.init_tsteps, context.request.maximum)
        or type(context.loop_visits) is not int
        or context.loop_visits != context.request.iterations + 1
        or type(raw) is not tuple
        or len(raw) != 3
        or raw[0] is not context.time_steps
        or raw[1] is not context.sampled
        or raw[2] is not context.solver_context
        or len(raw[0]) != context.request.iterations
        or type(raw[1]) is not set
        or type(context.noop_entries) is not int
        or context.noop_entries != 2
    ):
        raise ValueError("Complete clean original INIT calendar and normal exit required")
    setup = context.setup_frame
    loop = context.loop_frame
    setup_index, setup_raw = _normal_witness(context, "setup", setup, context.methods["setup"])
    loop_index, loop_raw = _normal_witness(
        context, "_run_sim_core_loop", loop, context.methods["_run_sim_core_loop"]
    )
    exits = [
        row["frame"]
        for row in context.frames.values()
        if type(row) is dict and row.get("name") == "solver_context_exit"
    ]
    enters = [
        row["frame"]
        for row in context.frames.values()
        if type(row) is dict and row.get("name") == "solver_context_enter"
    ]
    if len(exits) != 1 or len(enters) != 1:
        raise ValueError("One actual solver context enter and exit required")
    exit_frame = exits[0]
    exit_index, exit_raw = _normal_witness(
        context, "solver_context_exit", exit_frame, context.noop_methods[1]
    )
    enter_index, enter_raw = _normal_witness(
        context, "solver_context_enter", enters[0], context.noop_methods[0]
    )
    if (
        not enter_index < loop_index < exit_index < setup_index
        or loop.f_code is not context.loop_code
        or loop.f_locals.get("self") is not context.sim
        or loop.f_locals.get("phase") is not context.phase
        or loop.f_locals.get("time_steps") is not raw[0]
        or loop.f_locals.get("time_steps_sampled") is not raw[1]
        or setup.f_locals.get("self") is not context.sim
        or setup.f_locals.get("phase") is not context.phase
        or setup.f_locals.get("time_steps") is not raw[0]
        or setup.f_locals.get("time_steps_sampled") is not raw[1]
        or setup.f_locals.get("solver_context") is not raw[2]
        or "exception_instability" not in setup.f_locals
        or setup.f_locals["exception_instability"] is not None
        or exit_frame.f_back is not setup
        or enters[0].f_back is not setup
        or enters[0].f_locals.get("self") is not raw[2]
        or exit_frame.f_locals.get("self") is not raw[2]
        or any(
            name not in exit_frame.f_locals or exit_frame.f_locals[name] is not None
            for name in ("typ", "value", "traceback")
        )
        or loop_raw[1] is not None
        or setup_raw[1] is not None
        or enter_raw[1] is not None
        or exit_raw[1] is not False
    ):
        raise ValueError("Original normal loop/context/caller order and arguments changed")
    return raw, loop, exit_frame, loop_raw, exit_raw


def _natural_terminal(context):
    """Issue metadata only after the selected original caller has returned."""
    if context.terminal_status is not None or context.terminal_status_record is not None:
        raise ValueError("Natural terminal status already attempted")
    raw, loop, exit_frame, loop_raw, exit_raw = _natural_parts(context)
    return NaturalTerminalStatus(
        context, raw, loop, exit_frame, loop_raw, exit_raw, (None, None, None), False, True
    )


def _terminal_runtime_status(context):
    """Return the same sealed witness; inspection cannot construct completion."""
    status = context.terminal_status
    if (
        type(status) is not NaturalTerminalStatus
        or status is not context.terminal_status_record
        or status.child is not context
        or context.context_returned is not True
        or status.selected_stop is not False
        or status.before_native_pickle is not True
        or type(status.exception_arguments) is not tuple
        or len(status.exception_arguments) != 3
        or any(value is not None for value in status.exception_arguments)
    ):
        raise ValueError("Actual retained normal terminal status required")
    values = _natural_parts(context)
    if any(
        a is not b
        for a, b in zip(
            (
                status.calendar_raw,
                status.loop_frame,
                status.context_frame,
                status.loop_raw,
                status.context_raw,
            ),
            values,
            strict=True,
        )
    ):
        raise ValueError("Actual natural terminal return witness changed")
    return status


def _pre_source_parent_check(context, binding):
    """Seal the actual parent before source admission, retaining the raw result."""
    if (
        not context.claimed
        or context.setup_frame is not None
        or context.loop_frame is not None
        or context.work
        or context.bindings is None
        or context.before is None
        or context.stable is None
        or context.stable_graph is None
    ):
        raise ValueError("Complete before-state proofs required before source permission seal")
    _parent(binding)
    check = binding.check
    context.pre_source_parent_check_attempt = check
    returned = check(context)
    context.pre_source_parent_check_raw = returned
    _parent(binding)
    if returned is not context.electrical_parent:
        raise ValueError("Different actual electrical parent at pre-source permission seal")
    return returned


def prepare(request, *, enabled=False):
    with _LOCK:
        if _ACTIVE:
            base._reject(_ACTIVE[-1], "Reentrant natural INIT terminal preparation")
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise InitTerminalRejected("Natural INIT source remains held", stage="release")
    binding = _ready()
    with _LOCK:
        if _ACTIVE:
            base._reject(_ACTIVE[-1], "Reentrant natural INIT terminal preparation")
        if type(request) is not Request or request not in _REQUESTS:
            raise InitTerminalRejected(
                "Actual fresh issued natural INIT terminal request required", stage="request"
            )
        if request in _CONSUMED or request.electrical_owner in _RETIRED:
            raise InitTerminalRejected("Natural INIT epoch already attempted", stage="consumed")
        refs = _REQUESTS[request]
        parent = binding.module._authority(request.electrical_owner)
        if (
            parent is not refs[0]
            or parent.trial is not refs[1]
            or binding.module._snapshot(parent).identity != refs[2].identity
        ):
            raise ValueError("Actual original electrical epoch changed before retirement")
        graph = binding.module._graph(parent)
        base._same(graph[0], refs[3][0])
        if graph[1] != refs[3][1] or request.source_identity != base._digest(source_plan()):
            raise ValueError("Original electrical aliases/source mode changed")
        context = base._context(request, refs)
        context.retained_columns = context.retained_columns_record = WeakValueDictionary()
        context.retention_work = []
        context.last_retention_raw = None
        context.atoms, context.checker = context.initial.atoms, context.initial.checker
        if request.iterations != _configured_count(context.p.init_tsteps, request.maximum):
            raise ValueError("Original complete configured INIT count changed")
        context.timeline = context.timeline_record = _Timeline(request.iterations)
        context.terminal_status = context.terminal_status_record = None
        context.loop_span = context.loop_span_record = None
        context.context_returned = False
        context.callback_claimed_sites = _CallbackClaims(context.timeline)
        context.callback_roots = _CallbackClaims(context.timeline, roots=True)
        context.callback_claims_record = context.callback_claimed_sites
        context.callback_roots_record = context.callback_roots
        context.runtime = context.runtime_record = _engine(context)
        scope = context.runtime
        context.local_functions = tuple(
            (name, fn, context.atoms(fn))
            for name, fn in globals().items()
            if type(fn) is FunctionType and fn.__globals__ is globals()
        )
        context.metadata = tuple(
            (name, fn, base.previous._callable_atoms(context, fn))
            for name, fn in scope.items()
            if type(fn) is FunctionType
        )
        context.parent_binding = binding
        context.entries = MappingProxyType(
            dict(wrapper_guard=scope["_claim_wrapper"], dispatch=_dispatch)
        )
        _CONSUMED[request] = _RETIRED[request.electrical_owner] = context
        _ACTIVE.append(context)
        primary = None
        try:
            _parent(binding)
            if (
                binding.claim(
                    request.electrical_owner,
                    expected=refs[1],
                    transition=context,
                    entries=context.entries,
                )
                is not parent
            ):
                raise ValueError("Different actual electrical continuation")
            context.claimed = True
            scope["_namespace"](context)
            _bind_runtime(context)
            scope["_domain"](context)
            scope["_ancestry"](context)
            scope["_observer_recipe"](context)
            context.bindings = scope["_binding"](context)
            context.before, context.stable = (
                _retain_snapshot(context, scope["_snapshot"](context)),
                _retain_snapshot(context, scope["_snapshot"](context, stable=True)),
            )
            context.stable_graph = scope["_graph"](context, stable=True)
            context.initial_diagnostics = _diagnostics(context)
            if binding.module._snapshot(parent).identity != refs[2].identity:
                raise ValueError("Original electrical epoch changed while sealing source authority")
            graph = binding.module._graph(parent)
            base._same(graph[0], refs[3][0])
            if graph[1] != refs[3][1]:
                raise ValueError("Original aliases changed before the first iteration")
            _pre_source_parent_check(context, binding)
            context.stage = "original_natural_complete_FULL_INIT_before_pickle"
            with scope["_account"](context):
                scope["_run"](context)
            scope["_check"](context)
            scope["_callbacks_complete"](context)
            if (
                context.selected_stopped
                or not context.loop_returned
                or context.timeline.completed != request.iterations
                or context.timeline.current is not None
                or context.primary is not None
                or context.capture_error is not None
            ):
                raise InitTerminalRejected(
                    "Continuous source history incomplete", stage="sealing", partial=context
                )
            context.terminal_status = context.terminal_status_record = _natural_terminal(context)
            context.context_returned = True
            _terminal_runtime_status(context)
            context.molecule_record = context.terminal_runtime.finish_runtime(
                context.molecule_claim, child=context
            )
            context.after, context.after_graph = (
                _retain_snapshot(context, scope["_snapshot"](context)),
                scope["_graph"](context),
            )
            context.log_closed_epoch = scope["_logging_epoch"](context)
            codec = base.previous.storage.previous._scope(context.parent)
            value = Trial(
                request.identity,
                request.parent_identity,
                context.before,
                context.after,
                codec.snapshot(context.time_steps),
                codec.snapshot(tuple(context.sampled)),
                codec.snapshot(context.p.dt),
                tuple(context.timeline.records),
                tuple(context.work),
                tuple(context.helper_calls),
                tuple(context.callback_calls),
                tuple(context.raw_returns),
                context.stream_ids,
                tuple(
                    row.identity for row in base.previous.storage.previous._streams(context.parent)
                ),
                True,
                context.loop_returned,
                context.context_returned,
                context.selected_stopped,
                context.initial_diagnostics,
                "",
                c_calls=tuple(context.c_calls),
                stores=tuple(context.stores),
            )
            context.trial = replace(value, identity=base._digest(trial_record(value)))
        except BaseException as error:
            primary = base._primary(context)
            if primary is None:
                primary = error
            context.invalid, context.failure_error = True, primary
            try:
                _FAILED.append(context)
            except BaseException as capture:
                context.retention_error = (capture, primary, context)
            if error is not primary:
                context.secondary_error = (error, primary)
        finally:
            context.active = False
            if _ACTIVE and _ACTIVE[-1] is context:
                _ACTIVE.pop()
            else:
                context.invalid = True
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
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise InitTerminalRejected(
                "Original natural INIT terminal attempt failed",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=context,
            ) from primary
        if (
            context.invalid
            or context.cleanup_errors
            or not context.hooks_safe
            or getattr(context, "cleanup_journal_error", None) is not None
        ):
            raise InitTerminalRejected(
                "Natural INIT closure incomplete", stage="closure", partial=context
            )
        owner = object.__new__(InitTerminalOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


class InitTerminalOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only successful continuous source sealing may issue this owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("No checkpoint, completed-step recycling or supplied state")

    @property
    def trial(self):
        return _authority(self).trial

    @property
    def phase(self):
        return _authority(self).phase


def _authority(owner):
    if type(owner) is not InitTerminalOwner or owner not in _ISSUED:
        raise InitTerminalRejected("Actual issued continuous-history owner required", stage="owner")
    if owner in _SIM_RETIRED:
        raise InitTerminalRejected(
            "INIT owner was irreversibly reserved for SIM", stage="forwarded"
        )
    context, trial = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        context.invalid = True
        raise InitTerminalRejected(
            "Continuous history epoch unavailable", stage="owner", partial=context
        )
    context.validating = True
    try:
        _ready()
        scope = context.runtime
        scope["_check"](context, closed=True)
        scope["_callbacks_complete"](context)
        _closed_protocol(context, trial)
        graph = scope["_graph"](context)
        base._same(graph[0], context.after_graph[0])
        if (
            graph[1] != context.after_graph[1]
            or trial is not context.trial
            or trial.identity != base._digest(trial_record(trial))
            or scope["_snapshot"](context).identity != trial.after.identity
            or len(context.timeline.records) != len(trial.iterations)
            or any(
                a is not b for a, b in zip(context.timeline.records, trial.iterations, strict=True)
            )
        ):
            raise ValueError("Original continuous history values/aliases/record changed")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False


class SimReservation:
    """Retirement token only; never phase construction or mutation permission."""

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only reserve_for_sim retires a genuine completed INIT")

    def __reduce_ex__(self, protocol):
        raise TypeError("A live terminal reservation cannot be hydrated")


def reserve_for_sim(owner, *, expected_trial, law_id, enabled=False):
    """Retire once after full original authority; never reactivate an ancestor.

    The consumer must independently authenticate the fresh parameter claim,
    exact allowed source write and all retained state. This token alone
    authorizes no native call and no mutation of sim, cells or parameters.
    """
    if enabled is not True or os.environ.get(SIM_RESERVATION_RELEASE) != "1":
        raise InitTerminalRejected("Completed INIT retirement remains held", stage="release")
    if type(law_id) is not str or law_id != SIM_RESERVATION_LAW:
        raise InitTerminalRejected("Exact retirement law required", stage="law")
    with _LOCK:
        if _ACTIVE:
            base._reject(_ACTIVE[-1], "Concurrent terminal/SIM reservation")
        if type(owner) is not InitTerminalOwner or owner not in _ISSUED:
            raise InitTerminalRejected("Actual completed INIT owner required", stage="owner")
        if owner in _SIM_RETIRED:
            raise InitTerminalRejected("Completed INIT was already consumed", stage="consumed")
        if owner in _SIM_PENDING:
            pending = _SIM_PENDING[owner]
            pending.invalid = True
            raise InitTerminalRejected(
                "Reentrant completed INIT reservation", stage="reentrant", partial=pending
            )
        pending = SimpleNamespace(
            owner=owner,
            issued=_ISSUED[owner],
            expected_trial=expected_trial,
            thread=get_ident(),
            invalid=False,
            primary=None,
            token=None,
        )
        _SIM_PENDING[owner] = pending
        try:
            context = _authority(owner)
            issued = _ISSUED[owner]
            if (
                pending.invalid
                or issued is not pending.issued
                or expected_trial is not issued[1]
                or context is not issued[0]
                or context.trial is not expected_trial
                or owner in _SIM_RETIRED
            ):
                raise InitTerminalRejected(
                    "Exact unpoisoned completed INIT trial required",
                    stage="association",
                    partial=pending,
                )
            token = object.__new__(SimReservation)
            _SIM_RESERVATIONS[token] = (owner, issued, get_ident())
            _SIM_RETIRED[owner] = True
            pending.token = token
            return token
        except BaseException as error:
            pending.invalid, pending.primary = True, error
            # Presence retires the parent on failure too. Only True is a
            # successful reservation in the historical metadata validator.
            _SIM_RETIRED[owner] = False
            _SIM_FAILURES.append(pending)
            raise


def _sim_reservation(token):
    """Authenticate historical metadata only; do not call stale value checks."""
    if type(token) is not SimReservation or token not in _SIM_RESERVATIONS:
        raise InitTerminalRejected(
            "Actual issued terminal reservation required", stage="reservation"
        )
    owner, issued, thread = _SIM_RESERVATIONS[token]
    pending = _SIM_PENDING.get(owner)
    if (
        _SIM_RETIRED.get(owner) is not True
        or pending is None
        or pending.token is not token
        or pending.invalid
        or pending.primary is not None
        or pending.issued is not issued
        or pending.thread != thread
        or _ISSUED.get(owner) is not issued
        or thread != get_ident()
        or issued[0].trial is not issued[1]
        or issued[0].active
        or issued[0].invalid
    ):
        raise InitTerminalRejected(
            "Original terminal retirement links changed", stage="reservation"
        )
    return issued[0], issued[1]


def _closed_protocol(context, trial):
    """Published evidence and closed iteration epoch, not a parent issuer."""
    _terminal_runtime_status(context)
    raw = context.calendar_raw
    if (
        context.timeline.invalid is not False
        or _count(context.timeline.target) != _count(context.request.iterations)
        or type(context.timeline.completed) is not int
        or context.timeline.current is not None
        or context.timeline.completed != context.request.iterations
        or len(context.timeline.records) != context.request.iterations
        or trial.source_completed is not True
        or trial.selected_stop is not False
        or trial.loop_returned is not True
        or trial.context_returned is not True
        or trial.rng_before != context.stream_ids
        or trial.rng_after
        != tuple(v.identity for v in base.previous.storage.previous._streams(context.parent))
        or len(trial.iterations) != context.request.iterations
        or type(raw) is not tuple
        or len(raw) != 3
        or context.time_steps is not raw[0]
        or context.sampled is not raw[1]
    ):
        raise ValueError("Complete closed natural INIT terminal protocol/stream evidence required")
    codec = base.previous.storage.previous._scope(context.parent)
    if (
        codec.snapshot(context.time_steps).identity != trial.calendar.identity
        or codec.snapshot(tuple(context.sampled)).identity != trial.sampled.identity
        or codec.snapshot(context.p.dt).identity != trial.dt.identity
    ):
        raise ValueError("Original complete calendar/sampling/dt evidence changed")
    for ordinal, (saved, actual) in enumerate(
        zip(trial.iterations, context.timeline.records, strict=True)
    ):
        if (
            saved is not actual
            or type(actual.ordinal) is not int
            or actual.ordinal != ordinal
            or type(actual.sampled) is not bool
            or actual.sampled != (actual.source_time in context.sampled)
            or struct.pack("!d", actual.source_time)
            != struct.pack("!d", context.time_steps[ordinal])
        ):
            raise ValueError("Original iteration/sampling/calendar evidence changed")
    api, claim = _runtime(context)
    for row in trial.iterations:
        if (
            api.validate_iteration(
                claim,
                row.molecular_record,
                child=context,
                ordinal=row.ordinal,
                source_time=row.source_time,
            )
            is not row.molecular_record
        ):
            raise ValueError("Actual completed molecular iteration record changed")
