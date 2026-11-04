"""Held continuous INIT source mode on a fresh real ElectricalOwner.

The existing first-step endpoint is never recycled. Parent integration and the
actual molecular iteration issuer are intentionally unbound until reviewed.
Literal numerical bodies are borrowed unchanged; this module owns only the
bounded loop epoch, callback accounting and publication/observation lifecycle.
"""

import hashlib
import os
import struct
from contextlib import contextmanager
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from threading import RLock
from types import FunctionType, MappingProxyType
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_first_step as base
from cells.processes import betse_native_init_short_history_diagnostics as diagnostics

LAW_ID = "betse_actual_contiguous_bounded_FULL_INIT_history@1"
SELECTION = "contiguous_original_INIT_iterations_before_next_advance"
RELEASE = "CELLS_NATIVE_INIT_SHORT_HISTORY_RELEASED"
MAX_ITERATIONS = 64
BASE_SOURCE_SHA256 = "adaf98d4ef08e9c04c36f18dc1d7b89e17d585ab6460443246fc808425614043"
PARENT_SOURCE_SHA256 = PARENT_REVIEW_SHA256 = None
PARENT_CLAIM = PARENT_CHECK = None
PROPOSED_PARENT_CLAIM = "_claim_for_short_init"
PROPOSED_PARENT_CHECK = "_check_short_init_authority"
# Proposed names only. No accepted Key API is inferred from these strings.
RUNTIME_SOURCE_SHA256 = RUNTIME_REVIEW_SHA256 = RUNTIME_CONTRACT = None
RUNTIME_BEGIN = RUNTIME_END = None
PROPOSED_RUNTIME_BEGIN = "begin_iteration"
PROPOSED_RUNTIME_END = "finish_iteration"
_REQUESTS, _CONSUMED, _RETIRED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_ACTIVE, _FAILED, _LOCK = [], [], RLock()


class ShortHistoryRejected(base.FirstStepRejected):
    pass


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    electrical_owner: object
    parent_identity: str
    source_identity: str
    selection: str
    operator_mode: str
    iterations: int
    identity: str


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
    selected_stop: bool
    initial_diagnostics: object
    identity: str


def _count(value):
    if type(value) is not int or not 1 <= value <= MAX_ITERATIONS:
        raise ValueError("Explicit short-history integer count in [1,64] required")
    return value


def source_plan():
    return dict(
        law=LAW_ID,
        selection=SELECTION,
        max_iterations=MAX_ITERATIONS,
        original=base.source_plan(),
        base_source=BASE_SOURCE_SHA256,
        one_fresh_parent_one_original_loop=True,
        original_calendar_dt_sampled_set_and_objects_unchanged=True,
        completed_first_step_owner_is_not_a_parent=True,
        no_storage_reset_or_parameter_retrofit_between_iterations=True,
        required_parent=(PARENT_SOURCE_SHA256, PARENT_REVIEW_SHA256, PARENT_CLAIM, PARENT_CHECK),
        required_runtime=(RUNTIME_SOURCE_SHA256, RUNTIME_REVIEW_SHA256, RUNTIME_CONTRACT),
        runtime_entry_names_unadopted=(RUNTIME_BEGIN, RUNTIME_END),
        physical_checkpoint_full_INIT_or_scientific_admission=False,
    )


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        source=value.source_identity,
        selection=value.selection,
        operator_mode=value.operator_mode,
        iterations=_count(value.iterations),
    )


def _ready():
    path = Path(base.__file__)
    if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != BASE_SOURCE_SHA256:
        raise ShortHistoryRejected("Reviewed original source engine changed", stage="base_source")
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
        or RUNTIME_CONTRACT is None
    ):
        raise ShortHistoryRejected(
            "Actual parent and per-iteration molecular contracts remain unadopted",
            stage="integration_held",
        )
    parent = base.previous
    raw = Path(parent.__file__).read_bytes()
    if hashlib.sha256(raw).hexdigest() != PARENT_SOURCE_SHA256:
        raise ShortHistoryRejected("Electrical producer changed", stage="producer")
    parent.interfaces._source_interface(
        parent, raw, Path(parent.__file__), (PARENT_CLAIM, PARENT_CHECK)
    )
    claim, check = vars(parent).get(PARENT_CLAIM), vars(parent).get(PARENT_CHECK)
    if any(
        type(fn) is not FunctionType or fn.__globals__ is not vars(parent) for fn in (claim, check)
    ):
        raise ShortHistoryRejected("Actual parent hook functions unavailable", stage="hook")
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


def from_electrical(owner, *, iterations, law_id):
    count = _count(iterations)
    if law_id != LAW_ID or type(law_id) is not str:
        raise ShortHistoryRejected("Explicit short-history law required", stage="law")
    binding = _ready()
    with _LOCK:
        if _ACTIVE or type(owner) is not base.previous.ElectricalOwner or owner in _RETIRED:
            raise ShortHistoryRejected(
                "Fresh actual unconsumed ElectricalOwner required", stage="owner"
            )
        parent = binding.module._authority(owner)
        value = Request(
            owner,
            parent.trial.identity,
            base._digest(source_plan()),
            SELECTION,
            base._operator_mode(parent.cells),
            count,
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
            self.invalid
            or self.current is not None
            or self.completed >= self.target
            or type(sampled) is not bool
        ):
            self.invalid = True
            raise ValueError("Out-of-order, repeated or over-bound iteration entry")
        self.current = (self.completed, source_time, sampled)
        return self.current

    def end(self, record):
        if self.invalid or self.current is None or type(record) is not Iteration:
            self.invalid = True
            raise ValueError("Original active iteration record required")
        ordinal, label, sampled = self.current
        if (
            record.ordinal != ordinal
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
                id(self.current[1]),
                struct.pack("!d", self.current[1]),
                self.current[2],
            )
        )
        rows = tuple(
            (
                id(row),
                row.ordinal,
                id(row.source_time),
                struct.pack("!d", row.source_time),
                row.sampled,
                row.after.identity,
                row.work_end,
                row.callbacks_end,
                id(row.molecular_record),
            )
            for row in self.records
        )
        return self.target, self.completed, current, rows, self.invalid


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
        raise ValueError("Original short-history engine/ledger replaced")
    if context.request.iterations != context.timeline.target:
        raise ValueError("Bound request count changed")
    if (
        _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
    ):
        raise ValueError("Actual short-history request/consumption links changed")
    if _RETIRED.get(context.request.electrical_owner) is not context:
        raise ValueError("Original electrical retirement link changed")
    if context.request.identity != base._digest(request_record(context.request)):
        raise ValueError("Original short-history request identity changed")
    if (
        context.callback_claimed_sites is not context.callback_claims_record
        or context.callback_roots is not context.callback_roots_record
        or context.callback_claimed_sites.timeline is not context.timeline
        or context.callback_roots.timeline is not context.timeline
    ):
        raise ValueError("Original callback epoch ledgers replaced")
    for name, function, atoms in context.local_functions:
        if globals().get(name) is not function:
            raise ValueError("Short-history local function replaced: " + name)
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
    api, claim = context.molecule, context.molecule_claim
    if api is not context.parent.molecule or claim is None:
        raise ValueError("Actual enabled molecular runtime claimant required")
    if hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest() != RUNTIME_SOURCE_SHA256:
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
    after = context.runtime["_snapshot"](context)
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
    if context.timeline.completed == context.request.iterations:
        context.source_time_label = frame.f_locals.get("t")
        context.stop_frame, context.stopping = frame, True
        raise context.selected_stop
    if context.loop_visits != context.timeline.completed + 1:
        context.runtime["_reject"](context, "Original contiguous loop boundary changed")


def _observe(context, frame, event, arg):
    scope = context.runtime
    if frame.f_code in context.molecule_codes:
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
    row = context.frames.get(id(frame))
    if row is None:
        return
    if event == "opcode":
        _guard(context)
        _loop_boundary(context, frame)
    if (
        frame is context.loop_frame
        and event == "line"
        and context.timeline.current is None
        and context.loop_visits > context.timeline.completed
    ):
        _begin(context, frame)
    if event == "exception" and arg[1] is not context.selected_stop:
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
            ):
                scope["_reject"](
                    context, "Original complete calendar/sample/context lineage changed"
                )
            if len(raw[0]) < context.request.iterations:
                scope["_reject"](context, "Selected count exceeds the original unsliced calendar")


def _bind_runtime(context):
    descendant = getattr(context.parent, "short_init_descendant", None)
    if descendant is None or not hasattr(descendant, "molecule_claim"):
        raise ShortHistoryRejected(
            "Actual repeated-runtime claim unavailable", stage="runtime_held", partial=context
        )
    api, claim = context.parent.molecule, descendant.molecule_claim
    context.molecule, context.molecule_claim = api, claim
    context.molecule_record = None
    _runtime(context)
    names = (
        "validate_runtime_active",
        "validate_runtime",
        "runtime_members",
        "runtime_codes",
        "runtime_permissions",
        "observe_runtime",
        "finish_runtime",
        "project_state",
        "runtime_failed_context",
        RUNTIME_BEGIN,
        RUNTIME_END,
    )
    functions = tuple((name, vars(api).get(name)) for name in names)
    if any(type(fn) is not FunctionType or fn.__globals__ is not vars(api) for _, fn in functions):
        raise ShortHistoryRejected(
            "Actual adopted runtime functions unavailable", stage="runtime_held", partial=context
        )
    if api.validate_runtime_active(claim, child=context) is not claim:
        raise ValueError("Different actual short-history runtime claimant")
    context.molecule_functions = functions
    context.molecule_function_atoms = tuple(context.atoms(fn) for _, fn in functions)
    context.molecule_members, context.molecule_expressions = (
        api.runtime_members(claim),
        api.runtime_codes(claim),
    )
    context.molecule_permissions = api.runtime_permissions(claim)
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


def _dispatch(context, original, label, delegate, actual, args, kwargs, frame):
    """Reuse exact wrapper/body admission; replace only the owned stop count."""
    return context.runtime["_dispatch_impl"](
        context, original, label, delegate, actual, args, kwargs, frame
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
        FirstStepRejected=ShortHistoryRejected,
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
    for name in ("_bootstrap", "_guard", "_epoch", "_callback_enter", "_observe"):
        scope["_base" + name] = scope[name]
        scope[name] = globals()[name]
    scope["_loop_boundary"] = _loop_boundary
    # Only the metadata dispatch stop comparison differs; original native
    # kernels, signatures, operators, dt and fixtures are not transformed.
    node = nodes["_dispatch"]
    changed = 0
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Compare)
            and isinstance(item.left, ast.Attribute)
            and item.left.attr == "loop_visits"
            and len(item.comparators) == 1
            and isinstance(item.comparators[0], ast.Constant)
            and item.comparators[0].value == 2
        ):
            item.comparators[0] = ast.parse("context.request.iterations + 1", mode="eval").body
            changed += 1
    if changed != 1:
        raise ValueError("Exact original metadata stop comparator required")
    code = compile(
        ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])),
        str(Path(__file__)),
        "exec",
        dont_inherit=True,
    )
    member = next(
        value
        for value in code.co_consts
        if hasattr(value, "co_name") and value.co_name == "_dispatch"
    )
    scope["_dispatch_impl"] = FunctionType(member, scope)
    scope["_dispatch"] = _dispatch
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
        source_completed=value.source_completed,
        loop_returned=value.loop_returned,
        selected_stop=value.selected_stop,
        initial_diagnostics=asdict(value.initial_diagnostics),
    )


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise ShortHistoryRejected("Short-history source remains held", stage="release")
    binding = _ready()
    with _LOCK:
        if _ACTIVE or type(request) is not Request or request not in _REQUESTS:
            raise ShortHistoryRejected(
                "Actual fresh issued short-history request required", stage="request"
            )
        if request in _CONSUMED or request.electrical_owner in _RETIRED:
            raise ShortHistoryRejected("Short-history epoch already attempted", stage="consumed")
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
        context.atoms, context.checker = context.initial.atoms, context.initial.checker
        context.timeline = context.timeline_record = _Timeline(request.iterations)
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
                scope["_snapshot"](context),
                scope["_snapshot"](context, stable=True),
            )
            context.stable_graph = scope["_graph"](context, stable=True)
            context.initial_diagnostics = _diagnostics(context)
            if binding.module._snapshot(parent).identity != refs[2].identity:
                raise ValueError("Original electrical epoch changed while sealing source authority")
            graph = binding.module._graph(parent)
            base._same(graph[0], refs[3][0])
            if graph[1] != refs[3][1]:
                raise ValueError("Original aliases changed before the first iteration")
            context.stage = "original_contiguous_bounded_FULL_INIT_history"
            with scope["_account"](context):
                scope["_run"](context)
            scope["_check"](context)
            scope["_callbacks_complete"](context)
            if (
                not context.selected_stopped
                or context.loop_returned
                or context.timeline.completed != request.iterations
                or context.timeline.current is not None
                or context.primary is not None
                or context.capture_error is not None
            ):
                raise ShortHistoryRejected(
                    "Continuous source history incomplete", stage="sealing", partial=context
                )
            context.molecule_record = context.molecule.finish_runtime(
                context.molecule_claim, child=context
            )
            context.after, context.after_graph = (
                scope["_snapshot"](context),
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
                context.selected_stopped,
                context.initial_diagnostics,
                "",
            )
            context.trial = replace(value, identity=base._digest(trial_record(value)))
        except BaseException as error:
            primary = context.entry_error if context.entry_error is not None else context.primary
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
                    context.cleanup_errors += (("terminal_restore", error, index),)
            samples = []
            for order in ((0, 1), (1, 0)):
                pair = [None, None]
                for index in order:
                    try:
                        pair[index] = context.getters[index]()
                    except BaseException as error:
                        context.cleanup_errors += (("terminal_sample", error, index),)
                samples.append(tuple(pair))
            context.hooks_safe = all(
                a is context.required_hooks[0] and b is context.required_hooks[1]
                for a, b in samples
            )
        if primary is not None:
            raise ShortHistoryRejected(
                "Original short-history attempt failed",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=context,
            ) from primary
        if context.invalid or context.cleanup_errors or not context.hooks_safe:
            raise ShortHistoryRejected(
                "Short-history closure incomplete", stage="closure", partial=context
            )
        owner = object.__new__(ShortHistoryOwner)
        context.owner = owner
        _ISSUED[owner] = (context, context.trial)
        return owner


class ShortHistoryOwner:
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
    if type(owner) is not ShortHistoryOwner or owner not in _ISSUED:
        raise ShortHistoryRejected("Actual issued continuous-history owner required", stage="owner")
    context, trial = _ISSUED[owner]
    if context.active or context.invalid or context.validating:
        context.invalid = True
        raise ShortHistoryRejected(
            "Continuous history epoch unavailable", stage="owner", partial=context
        )
    context.validating = True
    try:
        _ready()
        scope = context.runtime
        scope["_check"](context, closed=True)
        scope["_callbacks_complete"](context)
        graph = scope["_graph"](context)
        base._same(graph[0], context.after_graph[0])
        if (
            graph[1] != context.after_graph[1]
            or trial is not context.trial
            or trial.identity != base._digest(trial_record(trial))
            or scope["_snapshot"](context).identity != trial.after.identity
            or tuple(context.timeline.records) != trial.iterations
        ):
            raise ValueError("Original continuous history values/aliases/record changed")
        return context
    except BaseException:
        context.invalid = True
        raise
    finally:
        context.validating = False
