"""Prepared same-instance SEED make_world prefix; real prerequisites stay closed.

Only the actual closed fresh-world coordinator child can supply this route;
a legacy PhaseTailOwner is never cast into it. Constructor/review pins stay
unbound until a separate adoption. The coordinator binds all helper bytes
except these two separately checked back-reference literals, avoiding a
reciprocal whole-file hash. Prepared dispatch retains the original
phase/Cells/classes/wrappers and never attaches a standalone lattice or mesh.
"""

import ast
import hashlib
import inspect
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, MappingProxyType, MethodType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_phase_tail as previous
from cells.processes import betse_native_seed_world_prefix_source as source

literal, aliases, core = previous.literal, previous.aliases, previous.core
LAW_ID = "betse_same_seed_phase_make_world_through_lattice@1"
RELEASE = "CELLS_NATIVE_SEED_WORLD_PREFIX_RELEASED"
PARENT_SHA256 = "1bc45a82b78ba239ba7c39fd5340b1fa273cd9373012d88711a401f9eabc78aa"
WORLD_MODE = "fresh_world_ready_prephase_single_claim_seed_constructor"
# Only these two literal values are omitted from the coordinator's exact byte
# template. Each actual value is checked against the full constructor/review;
# all complete source files remain bound by the immutable external snapshot.
CONSTRUCTION_SOURCE_SHA256 = None
CONSTRUCTION_REVIEW_SHA256 = None
CELLS, PHASE = "betse/science/cells.py", "betse/science/phase/phasecls.py"
NATIVE_PINS = {
    CELLS: "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2",
    PHASE: "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8",
}
METHODS = (
    "Cells.make_world",
    "SimPhase.die_unless_kind_seed",
    "SimPhase._die_unless_kind",
    "Cells._make_cell_lattice",
)
CALLBACK = "callbacks.progress_stated"
CALLBACK_STATUS = "Creating pseudo-random cell cluster..."
CHILDREN = {
    METHODS[0]: (CALLBACK, METHODS[1], METHODS[3]),
    METHODS[1]: (METHODS[2],),
    METHODS[2]: (),
    METHODS[3]: (),
}
RETURN_ORDER = (CALLBACK, METHODS[2], METHODS[1], METHODS[3], METHODS[0])
STORES = ("xmin", "xmax", "ymin", "ymax", "centre", "clust_xy", "bbox", "xyaxis")
PARAMETER_READS = (
    "ac",
    "cell_lattice_disorder",
    "cell_lattice_type",
    "cell_radius",
    "d_cell",
    "nx",
    "ny",
    "svg_override",
    "wsx",
    "wsy",
)
NUMPY_HELPERS = ("linspace", "meshgrid", "vstack", "asarray", "sqrt", "hstack", "min", "max")
PARENT_HOOKS = ("_claim_for_seed_world", "_check_world_authority", "_dispatch_seed_world")
_BODIES = {
    METHODS[0]: source.WorldPrefix.make_world,
    METHODS[1]: source.PhaseKind.die_unless_kind_seed,
    METHODS[2]: source.PhaseKind._die_unless_kind,
    METHODS[3]: source.LATTICE,
}
MAX_WORK = 100000
_REQUESTS, _CONSUMED, _ISSUED = (WeakKeyDictionary() for _ in range(3))
_LOCK, _ACTIVE = RLock(), []


class WorldPrefixRejected(ValueError):
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
    phase_owner: object
    parent_identity: str
    source_identity: str
    identity: str
    mode: str = WORLD_MODE

    def __reduce_ex__(self, protocol):
        raise TypeError("An actual fresh phase/parameter lineage is required")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    parent_identity: str
    before: object
    cache: object
    rng_before: object
    rng_after: object
    stages: tuple
    work: tuple
    source_completed: bool
    failure_stage: str | None
    identity: str


def _digest(value):
    return core.records._digest(value)


def _node(tree, cls, name):
    owner = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls)
    return next(n for n in owner.body if isinstance(n, ast.FunctionDef) and n.name == name)


def _body(node):
    return previous._body(node)


def _ast(nodes):
    return ast.dump(ast.Module(body=nodes, type_ignores=[]))


def source_plan(*, mode=None):
    """Read exact source only; no parameter/phase validation or replay."""
    if mode is not None and (type(mode) is not str or mode != WORLD_MODE):
        raise ValueError("Exact explicit fresh-world source mode required")
    if (
        mode is None
        and hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SHA256
    ):
        raise ValueError("Explicit current phase-tail producer required")
    trees = {}
    for name, expected in NATIVE_PINS.items():
        path = aliases.NATIVE / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("Pinned original SEED source changed: " + name)
        trees[name] = ast.parse(path.read_bytes())
    copied = ast.parse(Path(source.__file__).read_bytes())
    world = _body(_node(trees[CELLS], "Cells", "make_world"))
    selected = world[:3]
    if (
        len(selected) != 3
        or not isinstance(selected[-1], ast.If)
        or ast.unparse(world[3]) != "self.make_voronoi(phase)"
        or _ast(selected) != _ast(_body(_node(copied, "WorldPrefix", "make_world")))
    ):
        raise ValueError("Literal callback/SEED/branch prefix changed")
    for name in ("die_unless_kind_seed", "_die_unless_kind"):
        if _ast(_body(_node(trees[PHASE], "SimPhase", name))) != _ast(
            _body(_node(copied, "PhaseKind", name))
        ):
            raise ValueError("Original phase-kind helper changed: " + name)
    lattice_tree = ast.parse(Path(source.lattice.__file__).read_bytes())
    native_lattice = _node(trees[CELLS], "Cells", "_make_cell_lattice")
    if _ast(_body(native_lattice)) != _ast(
        _body(_node(lattice_tree, "CellsKernel", "_make_cell_lattice"))
    ):
        raise ValueError("Read-only original lattice body changed")
    fields = tuple(
        dict.fromkeys(
            n.targets[0].attr
            for n in ast.walk(native_lattice)
            if isinstance(n, ast.Assign)
            and isinstance(n.targets[0], ast.Attribute)
            and isinstance(n.targets[0].value, ast.Name)
            and n.targets[0].value.id == "self"
        )
    )
    if fields != STORES:
        raise ValueError("Original lattice field roster changed")
    return dict(
        law=LAW_ID,
        parent_producer=None if mode is not None else PARENT_SHA256,
        native_pins=NATIVE_PINS,
        literal_sha256=hashlib.sha256(Path(source.__file__).read_bytes()).hexdigest(),
        reused_lattice_sha256=hashlib.sha256(
            Path(source.lattice.__file__).read_bytes()
        ).hexdigest(),
        prefix_lines=(selected[0].lineno, selected[-1].end_lineno),
        lattice_lines=(native_lattice.lineno, native_lattice.end_lineno),
        order=(CALLBACK, "genuine SEED guard", "same Cells non-SVG lattice"),
        caller_fields=STORES,
        required_native_parameter_reads=PARAMETER_READS,
        world_ready_parameter_parent_bound=False,
        accepted_key_api=None,
        dispatch_hooks=PARENT_HOOKS,
        next_method="make_voronoi",
        progress_ranged_before_phase_birth_outside_boundary=True,
        no_supplied_world_parameter_or_stream=True,
        no_rng_reset_or_new_stream=True,
        phase_native_source_physical_checkpoint_admission=False,
    )


def _world_parent(owner):
    api = previous._world_api()
    if not api._pin(CONSTRUCTION_SOURCE_SHA256) or not api._pin(CONSTRUCTION_REVIEW_SHA256):
        raise WorldPrefixRejected(
            "Reviewed fresh-world constructor producer remains unbound",
            stage="world_ready_parameter_parent",
            partial=dict(phase_owner=owner),
        )
    if hashlib.sha256(Path(api.__file__).read_bytes()).hexdigest() != CONSTRUCTION_SOURCE_SHA256:
        raise WorldPrefixRejected("Exact constructor producer changed", stage="world_producer")
    api._ready()
    if type(owner) is not api.WorldPhaseOwner:
        raise WorldPrefixRejected(
            "Actual fresh-world phase child required; no old-tail cast", stage="phase_parent"
        )
    return api._world_parent(owner)


def _parent_hooks():
    for name in PARENT_HOOKS:
        function = getattr(previous, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(previous):
            raise WorldPrefixRejected(
                "Original same-instance world dispatch is unavailable",
                stage="phase_dispatch",
                partial=dict(missing=name),
            )


def request_record(value):
    return dict(
        law=LAW_ID,
        parent=value.parent_identity,
        mode=value.mode,
        source=value.source_identity,
        boundary="before make_voronoi",
        fresh_world_parameters_required=True,
        supplied_phase_cells_parameters_rng=False,
    )


def from_phase(owner, *, law_id, mode=WORLD_MODE):
    if type(law_id) is not str or law_id != LAW_ID:
        raise WorldPrefixRejected("Explicit SEED world-prefix law required", stage="law")
    if type(mode) is not str or mode != WORLD_MODE:
        raise WorldPrefixRejected("Exact fresh-world constructor mode required", stage="mode")
    parent = _world_parent(owner)
    _parent_hooks()
    value = Request(owner, parent.trial.identity, _digest(source_plan(mode=mode)), "", mode)
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (
        parent,
        parent.trial,
        parent.phase,
        parent.phase.p,
        parent.phase.cells,
        parent.phase.sim,
        parent.phase.cache,
        parent.phase.dyna,
        parent.phase.callbacks,
    )
    return value


def _atoms(function):
    """Actual code, closure, keyword-default and wrapped/delegate identities."""
    result, seen, pending = [], set(), [function]
    while pending:
        actual = pending.pop()
        if actual is None or id(actual) in seen:
            continue
        if len(seen) >= 64:
            raise ValueError("Bounded helper wrapper chain exhausted")
        seen.add(id(actual))
        if type(actual) is MethodType:
            result.extend((actual.__self__, actual.__func__))
            pending.append(actual.__func__)
        else:
            result.extend(aliases._atoms(actual))
        pending.extend(
            (getattr(actual, "__wrapped__", None), getattr(actual, "_implementation", None))
        )
        fn = actual.__func__ if type(actual) is MethodType else actual
        if type(fn) is FunctionType:
            keyword_defaults = fn.__kwdefaults__
            result.append(keyword_defaults)
            if keyword_defaults is not None:
                if type(keyword_defaults) is not dict or len(keyword_defaults) > 64:
                    raise ValueError("Bounded actual keyword-default mapping required")
                for key, value in keyword_defaults.items():
                    result.extend((key, value))
                    if callable(value):
                        pending.append(value)
            for cell in fn.__closure__ or ():
                delegate = cell.cell_contents
                if type(delegate) in (FunctionType, MethodType):
                    pending.append(delegate)
    return tuple(result)


def _bindings():
    functions = (
        source_plan,
        _world_parent,
        _parent_hooks,
        request_record,
        from_phase,
        _atoms,
        _bindings,
        _guard,
        _admit,
        _callback_values,
        _callback_receiver,
        _admit_callback,
        _callback_return,
        _remember,
        _capture_failure,
        _observer_bindings,
        _attempt,
        _reject,
        _claim_entry,
        _invoke,
        _body_call,
        _capture,
        _observe,
        _account,
        _account.__wrapped__,
        _namespace,
        _acquire,
        _native_bindings,
        _log_bindings,
        _namespace_bindings,
        _check,
        _immutable,
        _snapshot,
        _graph,
        _epoch,
        _same_epoch,
        _rng_state,
        _partial,
        trial_record,
        prepare,
        _validate,
        _failure_stage,
        *(_BODIES.values()),
    )
    return (
        WORLD_MODE,
        CONSTRUCTION_SOURCE_SHA256,
        CONSTRUCTION_REVIEW_SHA256,
        _REQUESTS,
        _CONSUMED,
        _ISSUED,
        _LOCK,
        _ACTIVE,
        LAW_ID,
        RELEASE,
        PARENT_SHA256,
        METHODS,
        CALLBACK_STATUS,
        CHILDREN,
        RETURN_ORDER,
        STORES,
        PARAMETER_READS,
        NUMPY_HELPERS,
        PARENT_HOOKS,
        _Numpy,
        _Random,
        *literal._surface(_Numpy),
        *literal._surface(_Random),
        *_observer_bindings(),
        *(atom for name in PARENT_HOOKS for atom in _atoms(getattr(previous, name, None))),
        *(
            atom
            for fn in (sys.getprofile, sys.setprofile, sys.gettrace, sys.settrace)
            for atom in _atoms(fn)
        ),
        *(atom for fn in functions for atom in _atoms(fn)),
    )


def _attempt(context, name, frame, layer):
    row = dict(
        sequence=len(context.work),
        method=name,
        frame=frame,
        layer=layer,
        admission="attempted",
        body_started=False,
        entry_is_case=False,
    )
    if len(context.work) >= MAX_WORK:
        context.overflow_attempt = row
        _reject(context, row, "World-prefix work capacity exhausted")
    context.work.append(row)
    return row


def _reject(context, row, reason):
    context.invalid = True
    if row is None:
        row = _attempt(context, "unclaimed", sys._getframe(1), "raw_entry_attempt")
    row.update(admission="rejected", reason=reason)
    context.last_rejected_attempt = row
    if context.entry_error is None:
        context.entry_error = WorldPrefixRejected(
            reason, stage="source_entry", request=context.request
        )
    raise context.entry_error


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.observation_error is not None:
        raise literal._CaptureStop()
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        _reject(context, None, "Inactive, poisoned or foreign-thread world prefix")


def _remember(context, error, origin, raw):
    previous.previous.handler.captures._remember_observation_error(
        context, error, origin=origin, raw=raw
    )


def _observer_bindings():
    return (
        inspect,
        inspect.CO_VARARGS,
        inspect.CO_VARKEYWORDS,
        *(
            atom
            for function in (
                _admit,
                _remember,
                _capture_failure,
                _capture,
                _callback_values,
                _callback_receiver,
                _admit_callback,
                _callback_return,
                previous.previous.handler.captures._remember_observation_error,
            )
            for atom in _atoms(function)
        ),
    )


def _capture_failure(context, error, origin, raw):
    # These writes precede any fallible recorder entry. They do not depend on
    # the reporter succeeding or on exception truthiness/formatting.
    context.capture_failures = (*context.capture_failures, (origin, error, raw))
    if context.observation_error is None:
        context.observation_error = error
        context.observation_origin = origin
        context.observation_raw = raw
    try:
        literal._same(_observer_bindings(), context.observer_bindings)
        _remember(context, error, origin, raw)
    except BaseException as reporting_error:
        context.capture_reporting_errors = (
            *context.capture_reporting_errors,
            (origin, reporting_error, error, raw),
        )


def _capture(context, frame, event):
    # Observations grow separately from the immutable inherited ancestry.
    raw = dict(frame.f_locals)
    context.locals[(frame.f_code.co_qualname, event)] = raw
    context.last_raw_frame = frame
    context.last_caller_fields = dict(vars(context.cells))


def _observe(context, name, raw):
    epoch = None
    try:
        epoch = _epoch(context)
        context.events.append((name, raw))
    except BaseException as error:
        _capture_failure(context, error, name, raw)
    if epoch is not None:
        try:
            _same_epoch(context, epoch)
        except BaseException as error:
            _capture_failure(context, error, name + "_state", raw)


def _claim_entry(context, name, actual, args, source_frame, invocation):
    row = _attempt(context, name, invocation, "native_wrapper_dispatch")
    _guard(context)
    parent = context.stack[-1] if context.stack else None
    if name == METHODS[0]:
        expected_frame = context.driver_frame
        expected_actual, expected_args = context.cells, (context.phase,)
        valid = parent is None and not context.root_claimed
    else:
        expected_frame = None if parent is None else parent["body"]
        expected_actual = context.cells if name.startswith("Cells.") else context.phase
        expected_args = (
            (context.p,)
            if name == METHODS[3]
            else ((context.enum.SEED,) if name == METHODS[2] else ())
        )
        children = () if parent is None else CHILDREN[parent["name"]]
        valid = (
            parent is not None
            and parent["next_child"] < len(children)
            and children[parent["next_child"]] == name
        )
    entry = invocation.f_back
    dispatch = None if entry is None else entry.f_back
    route = None if dispatch is None else dispatch.f_back
    wrapper = None if route is None else route.f_back
    member = context.wrappers.get(name)
    if (
        not valid
        or source_frame is not expected_frame
        or actual is not expected_actual
        or len(args) != len(expected_args)
        or any(a is not b for a, b in zip(args, expected_args, strict=True))
        or dispatch is None
        or dispatch.f_code is not context.dispatch_code
        or route is None
        or route.f_code is not context.native_call_code
        or wrapper is None
        or member is None
        or wrapper.f_code is not member.__code__
        or wrapper.f_back is not source_frame
    ):
        _reject(context, row, "Wrong actual object, source frame, order or original dispatch")
    if parent is None:
        context.root_claimed = True
    else:
        parent["next_child"] += 1
    record = dict(name=name, invocation=invocation, body=None, next_child=0, row=row)
    row["admission"] = "claimed"
    context.stack.append(record)
    return record


def _invoke(context, name, actual, args, source_frame):
    record = _claim_entry(context, name, actual, args, source_frame, sys._getframe())
    primary = None
    try:
        _check(context)
        _observe(context, name + "_enter", (actual, args))
        _guard(context)
        _check(context)
        value = context.methods[name](actual, *args)
        context.last_completed = (name, actual, value)
        if record["next_child"] != len(CHILDREN[name]):
            _reject(context, record["row"], "Missing original nested prefix call")
        context.stages.append(name)
        _observe(context, name + "_return", value)
        _guard(context)
        _check(context)
        return value
    except BaseException as error:
        primary = error
        _observe(context, name + "_unwind", actual)
        raise
    finally:
        try:
            if not context.stack or context.stack[-1] is not record:
                raise ValueError("World-prefix method stack changed")
            context.stack.pop()
            record["row"]["admission"] = "returned" if primary is None else "failed"
        except BaseException as error:
            _capture_failure(context, error, "entry_release", record)


def _body_call(context, name, delegate, actual, args, invocation):
    row = _attempt(context, name, invocation, "guarded_body_wrapper")
    record = context.stack[-1] if context.stack else None
    if (
        record is None
        or record["name"] != name
        or record.get("body_caller") is not None
        or invocation.f_back is not record["invocation"]
    ):
        _reject(context, row, "Body wrapper lacks its actual one-shot dispatch")
    _guard(context)
    _check(context)
    record["body_caller"] = sys._getframe()
    row["admission"] = "claimed"
    return delegate(actual, *args)


def _admit(context, frame):
    old = context.admitted.get(id(frame))
    if old is not None and old["frame"] is frame:
        return old
    name = context.body_codes.get(frame.f_code)
    row = _attempt(context, name if name is not None else CALLBACK, frame, "literal_body_attempt")
    _guard(context)
    record = context.stack[-1] if context.stack else None
    if name is not None:
        valid = (
            record is not None
            and record["name"] == name
            and record["body"] is None
            and frame.f_back is record.get("body_caller")
        )
        if not valid:
            _reject(context, row, "Unclaimed or reentrant original body")
        record["body"] = frame
    else:
        _admit_callback(context, frame, record, row)
    row["admission"] = "admitted"
    context.admitted[id(frame)] = row
    return row


def _callback_values(frame):
    """Read actual positional/variadic bindings, independent of receiver name."""
    code, local = frame.f_code, frame.f_locals
    positional = tuple(local[name] for name in code.co_varnames[: code.co_argcount])
    offset = code.co_argcount + code.co_kwonlyargcount
    if code.co_flags & inspect.CO_VARARGS:
        extra = local[code.co_varnames[offset]]
        if type(extra) is not tuple:
            raise ValueError("Actual callback *args tuple changed")
        positional += extra
        offset += 1
    keywords = {}
    if code.co_flags & inspect.CO_VARKEYWORDS:
        keywords = local[code.co_varnames[offset]]
        if type(keywords) is not dict:
            raise ValueError("Actual callback **kwargs dictionary changed")
    if not positional or len(positional) > 2:
        raise ValueError("Actual callback receiver/argument shape changed")
    if len(positional) == 2:
        if "status" in keywords:
            raise ValueError("Duplicate callback status argument")
        status = positional[1]
    elif "status" in code.co_varnames[code.co_argcount : code.co_argcount + code.co_kwonlyargcount]:
        status = local["status"]
    elif "status" in keywords:
        status = keywords["status"]
    else:
        raise ValueError("Actual callback status argument is unavailable")
    return positional[0], status


def _callback_receiver(frame):
    code = frame.f_code
    if code.co_argcount:
        return frame.f_locals[code.co_varnames[0]]
    if code.co_flags & inspect.CO_VARARGS:
        values = frame.f_locals[code.co_varnames[code.co_kwonlyargcount]]
        return values[0] if type(values) is tuple and values else None
    return None


def _admit_callback(context, frame, record, row):
    occurrence = context.callback_occurrence
    index = 0 if occurrence is None else len(occurrence["frames"])
    if index >= len(context.callback_chain):
        _reject(context, row, "Repeated or reentrant callback occurrence")
    expected = context.callback_chain[index]
    try:
        receiver, status = _callback_values(frame)
    except BaseException:
        _reject(context, row, "Callback wrapper lost actual receiver/status bindings")
    if index == 0:
        children = () if record is None else CHILDREN[record["name"]]
        valid = (
            record is not None
            and record["name"] == METHODS[0]
            and record["next_child"] < len(children)
            and children[record["next_child"]] == CALLBACK
            and frame.f_back is record["body"]
            and type(status) is str
            and status == CALLBACK_STATUS
        )
    else:
        valid = (
            record is occurrence["parent"]
            and occurrence["state"] == "entering"
            and frame.f_back is occurrence["frames"][-1]
            and status is occurrence["status"]
        )
    if not valid or frame.f_code is not expected.__code__ or receiver is not context.callback:
        _reject(context, row, "Callback must follow its actual wrapper/native-body frame chain")
    if index == 0:
        record["next_child"] += 1  # Irreversible before either inherited observer.
        occurrence = dict(
            parent=record,
            receiver=receiver,
            status=status,
            frames=[],
            returned=(),
            state="entering",
            source_error=None,
        )
        context.callback_occurrence = occurrence
    occurrence["frames"].append(frame)
    row["callback_index"] = index
    row["layer"] = (
        "native_callback_body"
        if index == len(context.callback_chain) - 1
        else "actual_callback_wrapper"
    )


def _callback_return(context, frame, source_error):
    occurrence = context.callback_occurrence
    row = context.admitted.get(id(frame))
    if occurrence is None or row is None or "callback_index" not in row:
        raise ValueError("Unclaimed callback return")
    index = row["callback_index"]
    if (
        len(occurrence["frames"]) != len(context.callback_chain)
        or index != len(context.callback_chain) - 1 - len(occurrence["returned"])
        or occurrence["frames"][index] is not frame
    ):
        raise ValueError("Callback wrapper/native-body returns are incomplete or out of order")
    occurrence["returned"] = (*occurrence["returned"], index)
    if source_error is not None and occurrence["source_error"] is None:
        occurrence["source_error"] = source_error
    if index == 0:
        if occurrence["source_error"] is None and context.entry_error is None:
            context.stages.append(CALLBACK)  # One occurrence, not one case per wrapper.
            occurrence["state"] = "returned"
        else:
            occurrence["state"] = "failed"


def _rng_state(context):
    return core.initial._rng_stream(context.rng)


class _Random:
    __slots__ = ("context", "native")

    def __init__(self, context, native):
        self.context, self.native = context, native

    def rand(self, *shape):
        context = self.context
        frame = sys._getframe(1)
        row = _attempt(context, "numpy.random.rand", frame, "original_rng_wrapper")
        _guard(context)
        record = context.stack[-1] if context.stack else None
        if (
            context.draw_active
            or record is None
            or record["name"] != METHODS[3]
            or frame is not record["body"]
        ):
            _reject(context, row, "RNG draw lacks the actual continuing lattice frame")
        _check(context)
        draw = dict(shape=shape, before=None, raw_result=None, after=None)
        context.draws.append(draw)
        try:
            draw["before"] = _rng_state(context)
        except BaseException as error:
            _capture_failure(context, error, "rng_before", draw)
            _guard(context)
        if draw["before"].identity != context.expected_rng.identity:
            _reject(context, row, "Continuing RNG changed before its owned call")
        context.draw_active = True
        try:
            result = self.native(*shape)
            draw["raw_result"] = result  # Retain before any capture or callback.
            try:
                draw["after"] = context.expected_rng = _rng_state(context)
            except BaseException as error:
                _capture_failure(context, error, "rng_after", draw)
            row["admission"] = "returned"
            _observe(context, "rng_return", draw)
            _guard(context)
            return result
        except BaseException as primary:
            row["admission"] = "failed"
            if not isinstance(primary, literal._CaptureStop):
                draw["source_error"] = primary
            if draw["after"] is None:
                try:
                    draw["after"] = context.expected_rng = _rng_state(context)
                except BaseException as error:
                    _capture_failure(context, error, "failed_rng_after", draw)
            raise
        finally:
            context.draw_active = False


class _Numpy:
    __slots__ = ("module", "random")

    def __init__(self, context, module):
        self.module = module
        self.random = _Random(context, context.rand)

    def __getattr__(self, name):
        if name not in NUMPY_HELPERS:
            raise AttributeError(name)
        context = self.random.context
        _guard(context)
        _check(context)
        return getattr(self.module, name)


def _acquire(context):
    """Authenticate retained classes/helpers; no constructor, seed or replay."""
    prefix = context.parent.refs[8]
    helper = previous.previous.caches.previous.callbacks
    context.prefix = prefix
    context.native_types = prefix.factories
    context.native_methods, context.wrappers = {}, {}
    for name in METHODS:
        role, method = name.split(".")
        native = getattr(prefix.factories[role], method)
        helper._source_function(native, CELLS if role == "Cells" else PHASE, method, role)
        wrapper = vars(type(context.cells if role == "Cells" else context.phase)).get(method)
        if type(wrapper) is not FunctionType:
            raise ValueError("Original owned runtime wrapper missing: " + name)
        closures = dict(zip(wrapper.__code__.co_freevars, wrapper.__closure__ or (), strict=True))
        if closures.get("delegate") is None or closures["delegate"].cell_contents is not native:
            raise ValueError("Original native wrapper/delegate association changed: " + name)
        context.native_methods[name], context.wrappers[name] = native, wrapper
    context.chain = helper.simulator._chain
    cells_ns = context.chain(context.native_methods[METHODS[3]])[-1].__globals__
    phase_ns = context.chain(context.native_methods[METHODS[1]])[-1].__globals__
    context.native_numpy, context.native_logs = cells_ns["np"], cells_ns["logs"]
    context.conf_exception = cells_ns["BetseSimConfException"]
    context.native_math = cells_ns.get("math")
    context.enum, context.lattice_enum = phase_ns["SimPhaseKind"], cells_ns["CellLatticeType"]
    context.exception, context.strjoin = phase_ns["BetseSimPhaseException"], phase_ns["strjoin"]
    context.rng = context.native_numpy.random.mtrand._rand
    context.rand = context.native_numpy.random.rand
    if getattr(context.rand, "__self__", None) is not context.rng:
        raise ValueError("Original NumPy global rand lost its actual MT owner")
    context.callback_method = type(context.callback).progress_stated
    context.callback_chain = tuple(context.chain(context.callback_method))
    if not context.callback_chain or any(
        type(fn) is not FunctionType for fn in context.callback_chain
    ):
        raise ValueError("Exact actual callback function chain required")
    callback_body = context.callback_chain[-1]
    callback_path = Path(callback_body.__code__.co_filename)
    if not callback_path.is_relative_to(aliases.NATIVE):
        raise ValueError("Actual original callback executable required")
    helper._source_function(
        context.callback_method,
        str(callback_path.relative_to(aliases.NATIVE)),
        "progress_stated",
        callback_body.__qualname__.split(".")[-2],
    )
    context.callback_codes = frozenset(fn.__code__ for fn in context.callback_chain)
    context.callback_occurrence = None
    context.callback_functions = tuple(
        member
        for base in type(context.callback).__mro__
        for member in vars(base).values()
        if type(member) is FunctionType
    )
    context.forbidden_callback_codes = {
        part.__code__
        for fn in context.callback_functions
        for part in context.chain(fn)
        if part.__code__ not in context.callback_codes
    }
    context.native_bindings = _native_bindings(context)


def _log_bindings(context):
    result = []
    for fn in (*context.native_methods.values(), *context.callback_chain):
        original = context.chain(fn)[-1]
        if "logs" in original.__code__.co_names and "log_info" in original.__code__.co_names:
            namespace = original.__globals__
            logs = namespace["logs"]
            result.extend((namespace, logs, *_atoms(logs.log_info)))
    return tuple(result)


def _native_bindings(context):
    numpy = context.native_numpy
    current_callback = type(context.callback).progress_stated
    literal._same(tuple(context.chain(current_callback)), context.callback_chain)
    return (
        context.prefix,
        context.native_types,
        context.rng,
        numpy,
        numpy.random,
        numpy.random.mtrand,
        numpy.random.mtrand._rand,
        numpy.random.rand,
        context.native_logs,
        context.native_math,
        context.conf_exception,
        *literal._surface(context.conf_exception),
        context.enum,
        context.enum.SEED,
        context.lattice_enum,
        context.exception,
        context.strjoin,
        context.callback_chain,
        *literal._surface(type(context.callback)),
        *_log_bindings(context),
        *(
            atom
            for fn in (
                *context.native_methods.values(),
                *context.wrappers.values(),
                *context.callback_functions,
                context.callback_method,
                *context.callback_chain,
                context.rand,
                context.native_logs.log_info,
                numpy.random.get_state,
                context.strjoin.join_as_disconjunction_double_quoted,
                *(getattr(numpy, name) for name in NUMPY_HELPERS),
            )
            for atom in _atoms(fn)
        ),
    )


def _namespace(context):
    numpy = context.numpy_view = _Numpy(context, context.native_numpy)
    lattice_namespace = dict(
        source.LATTICE.__globals__,
        np=numpy,
        logs=context.native_logs,
        CellLatticeType=context.lattice_enum,
        BetseSimConfException=context.conf_exception,
    )
    namespaces = {
        METHODS[0]: dict(source.__dict__),
        METHODS[1]: dict(source.__dict__, SimPhaseKind=context.enum),
        METHODS[2]: dict(
            source.__dict__,
            SimPhaseKind=context.enum,
            BetseSimPhaseException=context.exception,
            strjoin=context.strjoin,
        ),
        METHODS[3]: lattice_namespace,
    }
    bodies = {
        name: FunctionType(
            fn.__code__, namespaces[name], fn.__name__, fn.__defaults__, fn.__closure__
        )
        for name, fn in _BODIES.items()
    }
    context.body_codes = {fn.__code__: name for name, fn in bodies.items()}
    context.body_namespaces = namespaces

    def guarded_body(name, delegate):
        def invoke(actual, *args):
            return _body_call(context, name, delegate, actual, args, sys._getframe())

        return invoke

    context.methods = {name: guarded_body(name, fn) for name, fn in bodies.items()}

    def entry(name):
        def invoke(actual, *args, source_frame):
            return _invoke(context, name, actual, args, source_frame)

        return invoke

    context.entries = MappingProxyType({name: entry(name) for name in METHODS})
    context.namespace_bindings = _namespace_bindings(context)


def _namespace_bindings(context):
    numpy = context.numpy_view
    return (
        context.entries,
        context.methods,
        numpy,
        numpy.module,
        numpy.random,
        numpy.random.context,
        numpy.random.native,
        *(
            atom
            for fn in (*context.entries.values(), *context.methods.values())
            for atom in _atoms(fn)
        ),
        context.body_namespaces,
        *(
            atom
            for namespace in context.body_namespaces.values()
            for atom in (namespace, *namespace.values())
        ),
    )


def _immutable(context):
    ignored = set(STORES)
    for fields, (_, actual) in zip(context.stable_fields, context.objects, strict=True):
        fields.clear()
        fields.update(
            {
                name: value
                for name, value in vars(actual).items()
                if actual is not context.cells or name not in ignored
            }
        )
    return literal.callers._graph(context.stable_view, context.stable_view, context.stable_tape)


def _snapshot(context):
    return core.caches.snapshot(
        [
            dict(role=role, fields=literal._project(context.projector, vars(actual)))
            for role, actual in context.objects
        ]
    )


def _graph(context):
    context.final_fields[:] = [vars(actual) for _, actual in context.objects]
    return literal.callers._graph(context.final_view, context.final_view, context.tape)


def _epoch(context):
    # Native body stores are allowed between source events, never during an
    # inherited observer or a recording callback. Preserve reference edges as
    # well as exact values; an equal-array retarget must remain observable.
    cache = core.caches.snapshot(dict(vars(context.cells)))
    graph = literal.callers._graph(context.cells, context.p, context.stable_tape)
    return cache.identity, graph, _rng_state(context).identity


def _same_epoch(context, retained):
    current = _epoch(context)
    literal._same(current[1][0], retained[1][0])
    if current[0] != retained[0] or current[1][1] != retained[1][1] or current[2] != retained[2]:
        raise ValueError("Observer changed actual caller/reference/RNG state")


def _check(context):
    if context.active:
        _guard(context)
    if (
        context.invalid
        or context.thread != get_ident()
        or _REQUESTS.get(context.request) is not context.refs
        or _CONSUMED.get(context.request) is not context
        or getattr(previous, "_FORWARDED", {}).get(context.request.phase_owner) is not context
    ):
        raise ValueError("Original irreversible phase-to-world epoch changed")
    literal._same(_bindings(), context.bindings)
    # Future hook must authenticate actual retained ancestry without reopening
    # the consumed PhaseTailOwner's caller cache after legitimate lattice stores.
    previous._check_world_authority(context.parent)
    if (
        context.phase.p is not context.p
        or context.phase.cells is not context.cells
        or context.phase.sim is not context.refs[5]
        or context.phase.cache is not context.refs[6]
        or context.phase.dyna is not context.refs[7]
        or context.phase.callbacks is not context.callback
        or context.phase.kind is not context.enum.SEED
    ):
        raise ValueError("Same native phase/p/Cells/Simulator/cache/handler aliases changed")
    literal._same(_native_bindings(context), context.native_bindings)
    literal._same(_namespace_bindings(context), context.namespace_bindings)
    if (
        _digest(request_record(context.request)) != context.request.identity
        or context.request.mode != WORLD_MODE
        or _digest(source_plan(mode=context.request.mode)) != context.request.source_identity
    ):
        raise ValueError("Exact world-prefix request/source identity changed")
    current = _immutable(context)
    literal._same(current[0], context.inherited_graph[0])
    if current[1] != context.inherited_graph[1]:
        raise ValueError("Inherited reference edges outside native lattice stores changed")
    if not context.draw_active and _rng_state(context).identity != context.expected_rng.identity:
        raise ValueError("Actual continuing NumPy MT epoch changed outside an owned draw")
    names = tuple(vars(context.cells))
    added = names[len(context.caller_names) :]
    if names != (*context.caller_names, *STORES[: len(added)]):
        raise ValueError("Unrelated or out-of-order Cells fields changed")


@contextmanager
def _account(context):
    """One admission before either observer; independent protected cleanup."""
    get_profile, get_trace = sys.getprofile, sys.gettrace
    prior_profile, prior_trace = get_profile(), get_trace()
    set_profile, set_trace = sys.setprofile, sys.settrace
    primary, delegates, frame_errors = None, {}, {}
    context.hook_before = (prior_profile, prior_trace)
    context.hook_attempts, context.cleanup_errors = [], ()
    context.cleanup_phase = "source_body"
    selected = {*context.body_codes, *context.callback_codes}

    def capture(frame, event):
        try:
            literal._same(_observer_bindings(), context.observer_bindings)
            _capture(context, frame, event)
        except BaseException as error:
            _capture_failure(context, error, "raw_locals_" + event, frame)

    def before(frame, event):
        if event == "call" and frame.f_code in selected:
            literal._same(_observer_bindings(), context.observer_bindings)
            _admit(context, frame)  # Claim before trace/profile callbacks.
            _check(context)

    def after(frame, event):
        if frame.f_code in selected:
            _guard(context)
            _check(context)

    def inherited(function, frame, event, arg, *, entry, protect):
        epoch = None
        if protect:
            try:
                epoch = _epoch(context)
            except BaseException as error:
                _capture_failure(context, error, "inherited_before_" + event, frame)
        try:
            return function(frame, event, arg)
        except BaseException as error:
            if entry:
                raise
            _capture_failure(context, error, "inherited_" + event, frame)
        finally:
            if epoch is not None:
                try:
                    _same_epoch(context, epoch)
                except BaseException as error:
                    _capture_failure(context, error, "inherited_after_" + event, frame)

    def profile(frame, event, arg):
        before(frame, event)
        if (
            event == "call"
            and frame.f_code in context.forbidden_callback_codes
            and _callback_receiver(frame) is context.callback
        ):
            _reject(context, None, "Unselected native callback entry")
        if (
            event == "c_call"
            and arg is context.rand
            and (not context.draw_active or frame.f_code is not _Random.rand.__code__)
        ):
            _reject(context, None, "Unowned direct native RNG entry")
        if frame.f_code in selected and event in ("call", "return"):
            capture(frame, event)
        if prior_profile is not None:
            inherited(
                prior_profile,
                frame,
                event,
                arg,
                entry=event not in ("return", "c_return", "c_exception"),
                protect=frame.f_code in selected or arg is context.rand,
            )
        if event == "call":
            after(frame, event)
            row = context.admitted.get(id(frame))
            if row is not None and row["frame"] is frame:
                row["body_started"] = True

    def trace(frame, event, arg):
        reached = frame.f_code in selected
        before(frame, event)
        if reached:
            if event == "exception":
                frame_errors[id(frame)] = arg[1]
                if not isinstance(arg[1], literal._CaptureStop):
                    context.pending_source_error = arg[1]
            if event in ("call", "line", "return", "exception"):
                capture(frame, event)
        delegate = prior_trace if event == "call" else delegates.get(id(frame))
        if delegate is not None:
            try:
                next_delegate = inherited(
                    delegate, frame, event, arg, entry=event == "call", protect=reached
                )
                if next_delegate is not None or event == "call":
                    delegates[id(frame)] = next_delegate
            except BaseException as error:
                if event == "call":
                    raise
                _capture_failure(context, error, "inherited_trace_" + event, frame)
        if reached and event != "return":
            after(frame, event)
        if event == "return":
            delegates.pop(id(frame), None)
            row = context.admitted.get(id(frame))
            if reached and row is not None and "callback_index" in row:
                try:
                    literal._same(_observer_bindings(), context.observer_bindings)
                    _callback_return(context, frame, frame_errors.get(id(frame)))
                except BaseException as error:
                    _capture_failure(context, error, "callback_return", frame)
        return trace if reached or delegates.get(id(frame)) is not None else None

    try:
        context.hook_attempts.append("profile_install")
        set_profile(profile)
        context.hook_attempts.append("trace_install")
        set_trace(trace)
        yield
    except BaseException as error:
        primary = context.entry_error if context.entry_error is not None else error
        context.hook_primary = primary
        if primary is not error:
            raise primary  # noqa: B904 - keep the original rejection's exact cause
        raise
    finally:
        context.cleanup_phase = "restore"
        # Retain raw errors without calling any reporter until BOTH original
        # hooks have had independent restoration and identity-check attempts.
        for name, setter, getter, old in (
            ("trace", set_trace, get_trace, prior_trace),
            ("profile", set_profile, get_profile, prior_profile),
        ):
            try:
                context.hook_attempts.append(name + "_restore")
            except BaseException as error:
                context.cleanup_errors = (
                    *context.cleanup_errors,
                    (name + "_restore_attempt", error, old),
                )
            try:
                setter(old)
            except BaseException as error:
                context.cleanup_errors = (
                    *context.cleanup_errors,
                    (name + "_restore", error, old),
                )
            needs_recovery = True
            try:
                needs_recovery = getter() is not old
            except BaseException as error:
                context.cleanup_errors = (
                    *context.cleanup_errors,
                    (name + "_state", error, old),
                )
            if needs_recovery:
                try:
                    context.hook_attempts.append(name + "_recovery")
                except BaseException as error:
                    context.cleanup_errors = (
                        *context.cleanup_errors,
                        (name + "_recovery_attempt", error, old),
                    )
                try:
                    setter(old)
                except BaseException as error:
                    context.cleanup_errors = (
                        *context.cleanup_errors,
                        (name + "_recovery", error, old),
                    )
        actual = []
        for name, getter in (("profile", get_profile), ("trace", get_trace)):
            try:
                actual.append(getter())
            except BaseException as error:
                actual.append(error)
                context.cleanup_errors = (
                    *context.cleanup_errors,
                    (name + "_final_state", error, None),
                )
        context.hook_after = tuple(actual)
        context.hook_after_restore = context.hook_after
        context.hook_identities_restored = (
            context.hook_after[0] is prior_profile and context.hook_after[1] is prior_trace
        )
        if context.hook_identities_restored is not True:
            context.invalid = True
            mismatch = ValueError("Original profile/trace identities were not restored")
            context.cleanup_errors = (
                *context.cleanup_errors,
                ("hook_identity_mismatch", mismatch, (context.hook_before, context.hook_after)),
            )
        context.cleanup_phase = "report"
        for origin, error, raw in context.cleanup_errors:
            if context.observation_error is None:
                context.observation_error = error
                context.observation_origin, context.observation_raw = origin, raw
            try:
                _capture_failure(context, error, origin, raw)
            except BaseException as reporting_error:
                # Even rejection at the recorder's entry cannot mask the
                # source primary, discard raw cleanup, or re-arm this epoch.
                context.capture_reporting_errors = (
                    *context.capture_reporting_errors,
                    (origin, reporting_error, error, raw),
                )
        # A recorder entry can itself be rejected by the inherited profiler,
        # which Python may then disable. Recheck after reporting; do not call
        # another reporter after this final independent restoration pass.
        context.cleanup_phase = "post_record_restore"
        for name, setter, getter, old in (
            ("profile", set_profile, get_profile, prior_profile),
            ("trace", set_trace, get_trace, prior_trace),
        ):
            changed = True
            try:
                changed = getter() is not old
            except BaseException as error:
                context.cleanup_errors = (
                    *context.cleanup_errors,
                    (name + "_post_report_read", error, old),
                )
            if changed:
                try:
                    context.hook_attempts.append(name + "_post_report_restore")
                except BaseException as error:
                    context.cleanup_errors = (
                        *context.cleanup_errors,
                        (name + "_post_report_attempt", error, old),
                    )
                try:
                    setter(old)
                except BaseException as error:
                    context.cleanup_errors = (
                        *context.cleanup_errors,
                        (name + "_post_report_restore", error, old),
                    )
        # No restoration occurs after these samples. A second pair in reverse
        # read order also detects a getter invalidating the other saved value.
        context.cleanup_phase = "final_sample"
        first, second = [None, None], [None, None]
        for final, order in ((first, (0, 1)), (second, (1, 0))):
            for index in order:
                name = ("profile", "trace")[index]
                getter = (get_profile, get_trace)[index]
                try:
                    final[index] = getter()
                except BaseException as error:
                    final[index] = error
                    context.cleanup_errors = (
                        *context.cleanup_errors,
                        (name + "_post_report_final", error, None),
                    )
        context.hook_samples = ((first[0], first[1]), (second[0], second[1]))
        context.hook_after = context.hook_samples[-1]
        context.hook_identities_restored = (
            first[0] is prior_profile
            and first[1] is prior_trace
            and second[0] is prior_profile
            and second[1] is prior_trace
        )
        if context.hook_identities_restored is not True:
            context.invalid = True
            mismatch = ValueError("Final profile/trace identities remain different")
            context.cleanup_errors = (
                *context.cleanup_errors,
                ("final_hook_identity_mismatch", mismatch, context.hook_after),
            )
            if context.observation_error is None:
                context.observation_error = mismatch
                context.observation_origin = "final_hook_identity_mismatch"
                context.observation_raw = context.hook_after
        # Late read, restoration or bookkeeping failure remains a failure
        # even when recovery subsequently restored both actual identities.
        if context.cleanup_errors or context.capture_reporting_errors:
            context.invalid = True
            if context.observation_error is None:
                if context.cleanup_errors:
                    origin, error, raw = context.cleanup_errors[0]
                else:
                    origin, error, _, raw = context.capture_reporting_errors[0]
                context.observation_error = error
                context.observation_origin, context.observation_raw = origin, raw
        if primary is None:
            _guard(context)


def _partial(context):
    return dict(
        context=context,
        parent=context.parent,
        parent_trial=context.refs[1],
        phase=context.phase,
        parameters=context.p,
        caller=context.cells,
        sim=context.refs[5],
        caches=context.refs[6],
        handler=context.refs[7],
        callbacks=context.callback,
        raw_locals=context.locals,
        events=context.events,
        draws=context.draws,
        work=context.work,
        stages=context.stages,
        last_completed=getattr(context, "last_completed", None),
        last_caller_fields=getattr(context, "last_caller_fields", None),
        last_raw_frame=getattr(context, "last_raw_frame", None),
        rng=getattr(context, "rng", None),
        rng_before=getattr(context, "rng_before", None),
        expected_rng=getattr(context, "expected_rng", None),
        entry_error=context.entry_error,
        capture_errors=context.observation_errors,
        raw_capture_failures=context.capture_failures,
        capture_reporting_errors=context.capture_reporting_errors,
        callback_occurrence=getattr(context, "callback_occurrence", None),
        hook_before=getattr(context, "hook_before", None),
        hook_after=getattr(context, "hook_after", None),
        hook_after_restore=getattr(context, "hook_after_restore", None),
        hook_samples=getattr(context, "hook_samples", ()),
        cleanup_phase=getattr(context, "cleanup_phase", None),
        hook_identities_restored=getattr(context, "hook_identities_restored", None),
        cleanup_errors=getattr(context, "cleanup_errors", ()),
        usable_child=False,
    )


def trial_record(value):
    return dict(
        law=LAW_ID,
        request=value.request_identity,
        parent=value.parent_identity,
        before=value.before.identity,
        cache=value.cache.identity,
        rng_before=value.rng_before.identity,
        rng_after=value.rng_after.identity,
        stages=value.stages,
        work=value.work,
        source_completed=value.source_completed,
        failure_stage=value.failure_stage,
        work_layers_are_non_additive=True,
        independent_cases=0,
        next_method="make_voronoi",
        full_world_admitted=False,
    )


def _failure_stage(context, primary, capture):
    return context.stage if primary is not None or capture is not None else None


def prepare(request, *, enabled=False):
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise WorldPrefixRejected(
            "Actual world-prefix execution stays held", stage="release", request=request
        )
    _parent_hooks()
    if type(request) is not Request or request not in _REQUESTS:
        raise WorldPrefixRejected(
            "Actual issued world-prefix request required", stage="request", request=request
        )
    # Even an old typed phase cannot be retrofitted or promoted via its cache.
    _world_parent(request.phase_owner)
    with _LOCK:
        if _ACTIVE:
            _reject(_ACTIVE[-1], None, "Reentrant world-prefix preparation")
        if request in _CONSUMED:
            raise WorldPrefixRejected(
                "World-prefix attempt consumed", stage="consumed", request=request
            )
        refs = _REQUESTS[request]
        context = SimpleNamespace(
            request=request,
            refs=refs,
            parent=refs[0],
            phase=refs[2],
            p=refs[3],
            cells=refs[4],
            callback=refs[8],
            thread=get_ident(),
            active=True,
            invalid=False,
            stage="preflight",
            root_claimed=False,
            entry_error=None,
            observation_error=None,
            observation_errors=(),
            capture_failures=(),
            capture_reporting_errors=(),
            observer_bindings=_observer_bindings(),
            pending_source_error=None,
            work=[],
            stages=[],
            events=[],
            locals={},
            draws=[],
            stack=[],
            admitted={},
            draw_active=False,
            driver_frame=sys._getframe(),
        )
        _CONSUMED[request] = context
        _ACTIVE.append(context)
        primary, capture, trial = None, None, None
        try:
            _acquire(context)
            if context.phase.kind is not context.enum.SEED or context.p.svg_override is True:
                raise ValueError("Only the genuine non-SVG SEED path is selected")
            context.caller_names = tuple(vars(context.cells))
            if set(context.caller_names) & set(STORES):
                raise ValueError("Native lattice fields already exist; no world retrofit")
            # Projector roots also include YAML containers and weak proxies.
            # They remain references, not fabricated objects with vars().
            context.objects = list(context.parent.objects)
            context.projector = previous._projector(context.parent)
            context.stable_fields = [{} for _ in context.objects]
            context.stable_view = SimpleNamespace(
                objects=context.objects, fields=context.stable_fields
            )
            context.stable_tape = SimpleNamespace(rng=context.rng, events=(), draws=(), locals=())
            context.final_fields = []
            context.final_view = SimpleNamespace(
                objects=context.objects, fields=context.final_fields
            )
            context.tape = SimpleNamespace(
                rng=context.rng, events=context.events, draws=context.draws, locals=context.locals
            )
            context.before = _snapshot(context)
            context.inherited_graph = _immutable(context)
            context.rng_before = context.expected_rng = _rng_state(context)
            context.bindings = _bindings()
            _namespace(context)
            context.dispatch_code = previous._dispatch_seed_world.__code__
            context.native_call_code = previous.previous.caches.previous._native_call.__code__
            context.stage = "irreversible_world_claim"
            if (
                previous._claim_for_seed_world(
                    request.phase_owner,
                    expected=context.parent,
                    transition=context,
                    entries=context.entries,
                )
                is not context.parent
            ):
                raise ValueError("World retirement returned a different actual parent")
            context.stage = "literal_world_prefix"
            with _account(context):
                context.phase.cells.make_world(context.phase)
                _guard(context)
                _check(context)
            if tuple(context.stages) != RETURN_ORDER:
                raise ValueError("Original callback/guard/lattice return order changed")
            if (
                context.callback_occurrence is None
                or context.callback_occurrence["state"] != "returned"
            ):
                raise ValueError("Actual callback wrapper/native-body occurrence is incomplete")
        except BaseException as error:
            primary = context.entry_error
            if primary is None:
                primary = (
                    context.pending_source_error
                    if isinstance(error, literal._CaptureStop)
                    and context.observation_error is not None
                    else error
                )
        finally:
            context.active = False
            _ACTIVE.pop()
        partial = _partial(context)
        capture = context.observation_error
        try:
            if hasattr(context, "before"):
                work = tuple(
                    {key: value for key, value in row.items() if key != "frame"}
                    for row in context.work
                )
                value = Trial(
                    request.identity,
                    refs[1].identity,
                    context.before,
                    _snapshot(context),
                    context.rng_before,
                    _rng_state(context),
                    tuple(context.stages),
                    work,
                    primary is None and capture is None,
                    _failure_stage(context, primary, capture),
                    "",
                )
                trial = replace(value, identity=_digest(trial_record(value)))
                context.trial = trial
        except BaseException as error:
            raise WorldPrefixRejected(
                "World-prefix sealing failed",
                stage="capture",
                request=request,
                partial=partial,
                source_error=primary,
                capture_error=error,
            ) from (primary if primary is not None else error)
        if primary is not None or capture is not None or trial is None:
            raise WorldPrefixRejected(
                "Original world prefix refused",
                stage=context.stage,
                request=request,
                trial=trial,
                partial=partial,
                source_error=primary,
                capture_error=capture,
            ) from (primary if primary is not None else capture)
        try:
            _check(context)
            context.graph = _graph(context)
            owner = object.__new__(SeedWorldPrefixOwner)
            context.owner = owner
            _ISSUED[owner] = context
            return owner
        except BaseException as error:
            raise WorldPrefixRejected(
                "World-prefix child issuance failed",
                stage="issuance",
                request=request,
                trial=trial,
                partial=partial,
                capture_error=error,
            ) from error


class SeedWorldPrefixOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine same-phase world-prefix continuation")

    def __reduce_ex__(self, protocol):
        raise TypeError("No saved world/phase hydration or ordinary checkpoint")

    @property
    def phase(self):
        return _validate(self).phase

    @property
    def trial(self):
        return _validate(self).trial


def _validate(owner):
    if type(owner) is not SeedWorldPrefixOwner or owner not in _ISSUED:
        raise WorldPrefixRejected("Actual issued world-prefix owner required", stage="owner")
    context = _ISSUED[owner]
    try:
        if context.active or context.owner is not owner:
            raise ValueError("Active or replaced world-prefix owner")
        _check(context)
        if (
            not context.trial.source_completed
            or context.stack
            or tuple(context.stages) != RETURN_ORDER
            or not context.root_claimed
            or _snapshot(context).identity != context.trial.cache.identity
            or _digest(trial_record(context.trial)) != context.trial.identity
        ):
            raise ValueError("Sealed world-prefix state changed")
        graph = _graph(context)
        literal._same(graph[0], context.graph[0])
        if graph[1] != context.graph[1]:
            raise ValueError("Sealed world-prefix reference edges changed")
    except BaseException as error:
        context.invalid = True
        raise WorldPrefixRejected(
            "Stale world-prefix child",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=context,
            source_error=error,
        ) from error
    return context


def require_voronoi(owner):
    context = _validate(owner)
    raise WorldPrefixRejected(
        "Image/mask/mesh continuation is a separate actual-owner boundary",
        stage="make_voronoi_held",
        trial=context.trial,
    )
