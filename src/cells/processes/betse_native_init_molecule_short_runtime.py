"""One genuine pre-source claim for continuous original INIT network work.

This owns observation/iteration accounting only. Original session/projection
authority remains in molecule_network; numerical bodies are never copied.
Reviewed parent/consumer/source gates deliberately start unbound.
"""

import hashlib
import struct
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident
from types import FrameType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_molecule_channels as channels
from cells.processes import betse_native_init_molecule_network as base
from cells.processes import betse_native_world_phase_construction as interfaces

LAW_ID = "actual_original_INIT_network_single_continuous_bounded_runtime@1"
MAX_ITERATIONS = 64
MAX_WORK = base.MAX_WORK
BASE_MODULE = "cells.processes.betse_native_init_molecule_network"
BASE_INTERFACE_SHA256 = 'dd77276a16c4e3aeb118bf5bb84eecc6bf9ce748a3ed76d98ee5739c44d039c9'
BASE_REVIEW_SHA256 = '060c601d58a511985dc87b9d68b1d88c5a8c8f2173c28140a9e0167e0a8bd5df'
BASE_BINDING_KIND = "exact_INIT_molecule_bytes_except_two_validated_completion_backrefs@1"
BASE_BACK_REFERENCE_SLOTS = ("COMPLETION_SOURCE_SHA256", "COMPLETION_REVIEW_SHA256")
CONSUMER_MODULE = "cells.processes.betse_native_init_short_history"
CONSUMER_INTERFACE_SHA256 = '95bd87a06ff4b9bee91d95c166c6543103cca4e7e2df908f0e2d7b146076a8f5'
CONSUMER_REVIEW_SHA256 = '4325b04c3c425d0a0d9b0ef60c22859cdf524d13920c4b9c7eadb29e5caaafee'
CONSUMER_BINDING_KIND = "exact_INIT_short_history_except_four_electrical_runtime_backrefs@1"
CONSUMER_BACK_REFERENCE_SLOTS = (
    "PARENT_SOURCE_SHA256",
    "PARENT_REVIEW_SHA256",
    "RUNTIME_SOURCE_SHA256",
    "RUNTIME_REVIEW_SHA256",
)
_RUNTIME, _BOUND = WeakKeyDictionary(), WeakKeyDictionary()
_FAILED, _LOCK = [], RLock()
CaptureStop = base.CaptureStop
MoleculeNetworkRejected = base.MoleculeNetworkRejected
_capture, _runtime_error = base._capture, base._runtime_error
_runtime_expressions, _runtime_mappings = base._runtime_expressions, base._runtime_mappings
_runtime_resolution = base._runtime_resolution


class ShortRuntimeRejected(base.MoleculeNetworkRejected):
    pass


class ShortMoleculeRuntimeClaim:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only the actual pre-source Completion transfer may issue this claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Continuous runtime authority is process-local and cannot be decoded")


# The reused observer's lookup is local to this new namespace. It does not
# register a claim in the old one-step provider or alter that provider's class.
MoleculeRuntimeClaim = ShortMoleculeRuntimeClaim


@dataclass(frozen=True, slots=True)
class IterationEvidence:
    ordinal: int
    source_time: object
    source_frame: object
    sampled: bool
    top_calls: tuple
    work: tuple
    c_calls: tuple
    raw_returns: tuple
    identity: str


@dataclass(frozen=True, slots=True)
class HistoryEvidence:
    law: str
    iterations: int
    session: object
    child: object
    records: tuple
    source_completed: bool
    identity: str


def _count(value):
    if type(value) is not int or not 1 <= value <= MAX_ITERATIONS:
        raise ValueError("Explicit continuous runtime integer bound in [1,64] required")
    return value


def source_plan():
    return dict(
        law=LAW_ID,
        max_iterations=MAX_ITERATIONS,
        max_total_work=MAX_WORK,
        base=(BASE_INTERFACE_SHA256, BASE_REVIEW_SHA256),
        base_binding=(BASE_BINDING_KIND, BASE_BACK_REFERENCE_SLOTS),
        consumer=(CONSUMER_INTERFACE_SHA256, CONSUMER_REVIEW_SHA256),
        consumer_binding=(CONSUMER_BINDING_KIND, CONSUMER_BACK_REFERENCE_SLOTS),
        numerical_bodies_reused_not_copied=True,
        original_session_provider=base.__name__,
        no_first_step_owner_rebinding_or_claim_reset=True,
        full_native_scientific_release=False,
    )


def base_binding(payload):
    """The existing network recipe excludes only its two Completion literals."""
    return FunctionType(
        interfaces._helper_binding.__code__,
        dict(
            vars(interfaces),
            HELPER_BINDING_KIND=BASE_BINDING_KIND,
            HELPER_BACK_REFERENCE_SLOTS=BASE_BACK_REFERENCE_SLOTS,
        ),
    )(payload)


def _check_base_backrefs(backrefs, completion_source, expected_review):
    """Metadata comparison only; this neither adopts a source nor issues a parent."""
    return FunctionType(
        interfaces._check_helper_backrefs.__code__,
        dict(vars(interfaces), HELPER_BACK_REFERENCE_SLOTS=BASE_BACK_REFERENCE_SLOTS),
    )(backrefs, completion_source, expected_review)


def consumer_binding(payload):
    """Existing exact-byte recipe, with only four declared literal exclusions."""
    return FunctionType(
        interfaces._helper_binding.__code__,
        dict(
            vars(interfaces),
            HELPER_BINDING_KIND=CONSUMER_BINDING_KIND,
            HELPER_BACK_REFERENCE_SLOTS=CONSUMER_BACK_REFERENCE_SLOTS,
        ),
    )(payload)


def _ready():
    if not all(
        base._pin(pin)
        for pin in (
            BASE_INTERFACE_SHA256,
            BASE_REVIEW_SHA256,
            CONSUMER_INTERFACE_SHA256,
            CONSUMER_REVIEW_SHA256,
        )
    ):
        raise ShortRuntimeRejected(
            "Reviewed continuous runtime/source adoption remains held", stage="held"
        )
    base_path = Path(__file__).with_name("betse_native_init_molecule_network.py")
    if (
        type(base) is not ModuleType
        or sys.modules.get(BASE_MODULE) is not base
        or base.__name__ != BASE_MODULE
        or base_path.is_symlink()
        or Path(base.__file__).resolve() != base_path.resolve()
    ):
        raise ShortRuntimeRejected("Actual original network namespace required", stage="producer")
    base_identity, base_backrefs = base_binding(base_path.read_bytes())
    completion_name = "cells.processes.betse_native_init_dynamics_completion"
    completion = sys.modules.get(completion_name)
    completion_path = Path(__file__).with_name("betse_native_init_dynamics_completion.py")
    if (
        type(completion) is not ModuleType
        or base.COMPLETION_MODULE != completion_name
        or completion_path.is_symlink()
        or Path(completion.__file__).resolve() != completion_path.resolve()
        or completion.MOLECULE_MODULE != BASE_MODULE
        or completion.SHORT_RUNTIME_MODULE != __name__
        or base.CONTRACT != base.PROPOSED_CONTRACT
        or base_identity != BASE_INTERFACE_SHA256
        or base_identity != completion.MOLECULE_INTERFACE_SHA256
        or BASE_REVIEW_SHA256 != completion.MOLECULE_REVIEW_SHA256
        or any(vars(base).get(name) != value for name, value in base_backrefs)
    ):
        raise ShortRuntimeRejected(
            "Exact network interface or Completion association changed", stage="base_backrefs"
        )
    _check_base_backrefs(
        base_backrefs, completion_path.read_bytes(), completion.previous.COMPLETION_REVIEW_SHA256
    )
    # The original network also authenticates its actual Completion adapter and
    # original retained ancestor exports. No runtime or numerical body is run.
    if base._ready() is not completion:
        raise ShortRuntimeRejected(
            "Different original network Completion adapter", stage="base_backrefs"
        )
    consumer = sys.modules.get(CONSUMER_MODULE)
    path = Path(__file__).with_name("betse_native_init_short_history.py")
    if (
        type(consumer) is not ModuleType
        or path.is_symlink()
        or Path(consumer.__file__).resolve() != path.resolve()
    ):
        raise ShortRuntimeRejected(
            "Actual original short-history namespace required", stage="producer"
        )
    identity, backrefs = consumer_binding(path.read_bytes())
    expected = (
        (
            "PARENT_SOURCE_SHA256",
            hashlib.sha256(Path(consumer.base.previous.__file__).read_bytes()).hexdigest(),
        ),
        ("PARENT_REVIEW_SHA256", consumer.base.previous.SHORT_INIT_PARENT_REVIEW_SHA256),
        ("RUNTIME_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("RUNTIME_REVIEW_SHA256", getattr(completion, "SHORT_RUNTIME_REVIEW_SHA256", None)),
    )
    if (
        identity != CONSUMER_INTERFACE_SHA256
        or backrefs != expected
        or any(
            not base._pin(value) or vars(consumer).get(name) != value for name, value in backrefs
        )
        or consumer.RUNTIME_CONTRACT != LAW_ID
        or consumer.base.previous.SHORT_INIT_REVIEW_SHA256 != CONSUMER_REVIEW_SHA256
    ):
        raise ShortRuntimeRejected(
            "Exact consumer bytes or actual parent/runtime backrefs changed",
            stage="consumer_backrefs",
        )
    interfaces._source_interface(
        consumer, path.read_bytes(), path, ("_ready", "_begin", "_end", "prepare")
    )
    consumer._ready()
    return consumer


class _Iterations:
    """Pure metadata ledger; this is not a source/parent capability."""

    def __init__(self, count):
        self.bound, self.current, self.invalid = _count(count), None, False
        self.records, self.keys = [], []

    def begin(self, ordinal, source_time, key, frame, sampled, starts):
        if (
            self.invalid
            or self.current is not None
            or type(ordinal) is not int
            or ordinal != len(self.records)
            or ordinal >= self.bound
            or type(sampled) is not bool
        ):
            self.invalid = True
            raise ValueError("Duplicate, omitted or out-of-bound actual iteration entry")
        self.current = (ordinal, source_time, key, frame, sampled, starts)
        return self.current

    def end(self, record):
        if self.invalid or self.current is None or type(record) is not IterationEvidence:
            self.invalid = True
            raise ValueError("Actual active continuous iteration required")
        ordinal, label, key, frame, sampled, _ = self.current
        if (
            record.ordinal != ordinal
            or record.source_time is not label
            or type(record.ordinal) is not int
            or record.source_frame is not frame
            or record.sampled is not sampled
        ):
            self.invalid = True
            raise ValueError("Original iteration ordinal/time/frame/sample identity changed")
        self.records.append(record)
        self.keys.append(key)
        self.current = None


def _route(runtime):
    consumer = _ready()
    original, c, child = runtime.original, runtime.completion, runtime.child
    lease = c.short_init_descendant
    if (
        runtime.invalid
        or original.invalid
        or c.invalid
        or runtime.ledger.invalid
        or runtime.thread != get_ident()
        or _RUNTIME.get(runtime.claim) is not runtime
        or _BOUND.get(original.session) is not runtime
        or base._SESSIONS.get(original.session) is not original
        or base._CLAIMED.get(c.claim) is not original
        or c is not original.completion
        or c.molecule is not base
        or c.molecule_session is not original.session
        or c.short_init_descendant is not runtime.lease
    ):
        raise ShortRuntimeRejected(
            "Actual continuous runtime registry changed", stage="ancestry", partial=runtime
        )
    if (
        original.api._CLAIMS.get(c.claim) is not c
        or original.api._SHORT_INIT_DESCENDANTS.get(c.owner) is not lease
        or lease.runtime_api is not sys.modules[__name__]
        or lease.molecule_claim is not runtime.claim
        or lease.child is not child
        or lease.storage is not runtime.storage
        or lease.electrical is not runtime.electrical
        or lease.status not in ("reserved", "sealed")
        or lease.iterations != runtime.ledger.bound
        or child.parent is not c
        or child.storage_parent is not runtime.storage
        or child.electrical_parent is not runtime.electrical
        or child.invalid
        or child.phase is not original.phase
        or child.p is not original.p
        or child.sim is not original.sim
        or child.cells is not original.cells
        or child.thread != runtime.thread
        or child.request.iterations != runtime.ledger.bound
        or type(child.request) is not consumer.Request
        or consumer._REQUESTS.get(child.request) is not child.refs
        or consumer._CONSUMED.get(child.request) is not child
        or consumer._RETIRED.get(child.request.electrical_owner) is not child
    ):
        raise ShortRuntimeRejected(
            "Original continuous child/parent/budget association changed",
            stage="ancestry",
            partial=runtime,
        )
    if original.session in base._STEP_RUNTIME:
        raise ValueError("A one-step runtime cannot be reused for continuous INIT")
    original.initial.core.previous._same(base._bindings(original), runtime.source_bindings)
    for name, original_fn, body, original_bindings, body_bindings in runtime.reused_bindings:
        if vars(base).get(name) is not original_fn or _BODIES.get(name) is not body:
            raise ValueError("Actual source-bound reused runtime body changed")
        original.initial.core.previous._same(
            base._function_bindings(original_fn), original_bindings
        )
        original.initial.core.previous._same(base._function_bindings(body), body_bindings)
    base._dynamic_associations(original)
    _runtime_expressions(runtime)
    _runtime_mappings(runtime)
    return runtime


def _runtime_context(claim):
    if type(claim) is not ShortMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise ShortRuntimeRejected("Actual issued continuous runtime claim required", stage="claim")
    return _route(_RUNTIME[claim])


def _runtime_route(runtime):
    return _route(runtime)


def bind_short_history(session, *, completion, storage, electrical, child, iterations):
    consumer, frame = _ready(), sys._getframe(1)
    c, count = completion, _count(iterations)
    api = sys.modules.get(base.COMPLETION_MODULE)
    entry = vars(api).get("_claim_short_init_ancestor") if type(api) is ModuleType else None
    if (
        type(entry) is not FunctionType
        or frame.f_code is not entry.__code__
        or frame.f_globals is not vars(api)
        or frame.f_locals.get("context") is not c
        or frame.f_locals.get("storage") is not storage
        or frame.f_locals.get("electrical") is not electrical
        or frame.f_locals.get("transition") is not child
    ):
        raise ShortRuntimeRejected(
            "Actual Completion short-history transfer frame required", stage="entry"
        )
    original = base._context(session, c.claim)
    lease = c.short_init_descendant
    with _LOCK:
        if (
            session in _BOUND
            or session in base._STEP_RUNTIME
            or hasattr(c, "first_step_descendant")
            or not child.active
            or child.claimed
            or child.setup_frame is not None
            or child.loop_frame is not None
            or child.request.iterations != count
            or lease.child is not child
            or lease.status != "reserved"
            or consumer._CONSUMED.get(child.request) is not child
        ):
            raise ShortRuntimeRejected(
                "Fresh single N-bound actual transfer required", stage="consumed"
            )
        claim = object.__new__(ShortMoleculeRuntimeClaim)
        runtime = SimpleNamespace(
            claim=claim,
            original=original,
            completion=c,
            storage=storage,
            electrical=electrical,
            child=child,
            lease=lease,
            kind="short_history",
            ledger=_Iterations(count),
            thread=get_ident(),
            active=True,
            invalid=False,
            primary=None,
            primary_origin=None,
            entry_error=None,
            capture_error=None,
            capture_errors=(),
            last_raw=None,
            raw_returns=[],
            c_calls=[],
            work=[],
            frames={},
            pending={},
            top_calls=[],
            source_exceptions=[],
            expressions=(),
            expression_bindings=(),
            dynamic_maps=(),
            permissions=(),
            record=None,
        )
        _RUNTIME[claim] = _BOUND[session] = runtime
        lease.molecule_claim = claim
        try:
            original.api._short_init_route(c, storage, electrical, child)
            old = base._STORAGE_RUNTIME.get(session)
            if old is None or old.child is not storage or old.record is None or old.invalid:
                raise ValueError("Actual completed original molecular storage required")
            if (
                original.core.mit_enabled is not False
                or original.core.transporters
                or original.core.modulators
            ):
                raise ValueError(
                    "Unowned mitochondrial/transporter/modulator work remains unavailable"
                )
            runtime.dynamic_maps = old.dynamic_maps
            expressions = []
            for obj in original.core.molecules.values():
                if any(
                    getattr(obj, name)
                    for name in (
                        "active_pumping",
                        "ion_channel_gating",
                        "change_bounds",
                        "cell_clamp",
                    )
                ):
                    raise ValueError("Unowned molecule pumping/gating/boundary/clamp branch")
                expressions.append((obj, "gad_eval_string"))
            for collection in (original.core.reactions, original.core.reactions_env):
                expressions.extend((obj, "reaction_eval_string") for obj in collection.values())
            expressions.extend(
                (row["channel"], "alpha_eval_string")
                for row in original.channel_records
                if row["channel"].init_active is True
            )
            rows, bindings = [], []
            namespace = original.functions[("MasterOfNetworks", "run_loop")].__globals__
            for owner, field in expressions:
                text = vars(owner)[field]
                if type(text) is not str:
                    raise ValueError("Actual original initialized expression text required")
                code = compile(text, "<string>", "eval", dont_inherit=True)
                probe = FunctionType(code, namespace)
                rows.append((owner, field, text, code))
                bindings.append((probe, base._function_bindings(probe)))
            runtime.expressions, runtime.expression_bindings = tuple(rows), tuple(bindings)
            table = base._runtime_field_table("first_step")
            table["MasterOfNetworks"] -= frozenset(
                ("vmit_time", "reaction_rates_mit", "delta_conc_mit", "mit_concs", "mit")
            )
            table["Molecule"] -= frozenset(("c_mit_time",))
            permissions = [
                (actual, table[role]) for role, actual in original.objects if role in table
            ]
            sim_fields = table["Simulator"] | (
                frozenset(("cc_at_mem",)) if original.channel_records else frozenset()
            )
            permissions.append((original.sim, sim_fields))
            permissions.extend(channels.permission_rows(original, "first_step"))
            if len({id(actual) for actual, _ in permissions}) != len(permissions):
                raise ValueError("Each original continuous runtime holder must be unique")
            runtime.permissions = tuple(permissions)
            path = Path(base.__file__)
            original.api.previous.previous.previous._ready()._source_interface(
                base, path.read_bytes(), path, tuple(_BODIES)
            )
            if any(
                body.__code__ is not vars(base)[name].__code__
                or body.__globals__ is not globals()
                or body.__defaults__ is not vars(base)[name].__defaults__
                for name, body in _BODIES.items()
            ):
                raise ValueError("Exact pinned reused runtime bodies/defaults required")
            runtime.reused_bindings = tuple(
                (
                    name,
                    vars(base)[name],
                    body,
                    base._function_bindings(vars(base)[name]),
                    base._function_bindings(body),
                )
                for name, body in _BODIES.items()
            )
            runtime.source_bindings = base._bindings(original)
            return claim
        except BaseException as error:
            runtime.invalid, runtime.primary = True, error
            try:
                _FAILED.append(runtime)
            except BaseException as secondary:
                _capture(runtime, "failure_registry", secondary, error)
            try:
                error.molecule_runtime_partial = runtime
            except BaseException as secondary:
                _capture(runtime, "failure_attachment", secondary, error)
            raise


def session_of(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child:
        _runtime_error(runtime, "Different actual continuous child")
    return runtime.original.session


def session_provider(claim, *, child):
    session_of(claim, child=child)
    return base


def _boundary(runtime, child, ordinal, source_time, source_frame, name):
    module = _ready()
    function = vars(module).get(name)
    caller = sys._getframe(2)
    marker = getattr(
        child, "last_iteration_begin" if name == "_begin" else "last_iteration_end", None
    )
    current = child.timeline.current
    if (
        child is not runtime.child
        or not runtime.active
        or runtime.record is not None
        or type(function) is not FunctionType
        or caller.f_code is not function.__code__
        or caller.f_globals is not vars(module)
        or caller.f_locals.get("context") is not child
        or caller.f_locals.get("frame") is not source_frame
        or type(source_frame) is not FrameType
        or source_frame is not child.loop_frame
        or type(marker) is not tuple
        or marker[0] is not source_frame
        or marker[1] is not current
        or current is None
        or type(ordinal) is not int
        or current[0] != ordinal
        or current[1] is not source_time
        or type(current[2]) is not bool
    ):
        _runtime_error(runtime, "Actual paired short-history source boundary required")
    return current


def _time_key(runtime, value):
    if type(value) not in (float, runtime.completion.numpy.float64):
        _runtime_error(runtime, "Exact original calendar scalar type required")
    packed = struct.pack("!d", value)
    if (int.from_bytes(packed, "big") >> 52) & 0x7FF == 0x7FF:
        _runtime_error(runtime, "Finite original calendar scalar required")
    return type(value), packed


def begin_iteration(claim, *, child, ordinal, source_time, source_frame):
    runtime = _runtime_context(claim)
    current = _boundary(runtime, child, ordinal, source_time, source_frame, "_begin")
    if source_frame.f_locals.get("t") is not source_time:
        _runtime_error(runtime, "Actual source time object changed before entry")
    if (
        source_frame.f_locals.get("time_steps") is not child.time_steps
        or source_frame.f_locals.get("time_steps_sampled") is not child.sampled
        or _time_key(runtime, source_time) != _time_key(runtime, child.time_steps[ordinal])
    ):
        _runtime_error(runtime, "Actual unsliced calendar/ordinal/sample owner changed")
    starts = len(runtime.work), len(runtime.c_calls), len(runtime.raw_returns)
    runtime.ledger.begin(
        ordinal, source_time, _time_key(runtime, source_time), source_frame, current[2], starts
    )
    runtime.top_calls = []  # New transcript segment; no source state/owner/cache reset.
    return claim


def _runtime_entry(runtime, frame):
    if runtime.ledger.current is None or not runtime.active:
        _runtime_error(runtime, "Original molecular work outside an admitted iteration")
    return base._runtime_entry(runtime, frame)


def _iteration_data(record):
    return dict(
        ordinal=record.ordinal,
        time=id(record.source_time),
        frame=id(record.source_frame),
        sampled=record.sampled,
        calls=record.top_calls,
        work=tuple((id(row["frame"]), row["returned"]) for row in record.work),
        c_calls=tuple((id(frame), event, id(arg)) for frame, event, arg in record.c_calls),
        returns=tuple((id(frame), id(value)) for frame, value in record.raw_returns),
    )


def finish_iteration(claim, *, child, ordinal, source_time, source_frame):
    runtime = _runtime_context(claim)
    current = _boundary(runtime, child, ordinal, source_time, source_frame, "_end")
    pending = runtime.ledger.current
    if pending is None or pending[:2] != (ordinal, source_time) or pending[1] is not source_time:
        _runtime_error(runtime, "Original admitted iteration/time pairing changed")
    if (
        _time_key(runtime, source_time) != pending[2]
        or pending[3] is not source_frame
        or pending[4] is not current[2]
    ):
        _runtime_error(runtime, "Original continuous source scalar/frame/sample changed")
    expected = ["clear_run_loop"]
    if runtime.original.mom.channels:
        expected.append("run_loop_channels")
    expected.append("run_loop")
    if current[2]:
        expected.extend(("write_data", "report"))
    a, b, c = pending[5]
    work, calls, returns = (
        tuple(runtime.work[a:]),
        tuple(runtime.c_calls[b:]),
        tuple(runtime.raw_returns[c:]),
    )
    if (
        runtime.primary is not None
        or runtime.capture_error is not None
        or runtime.top_calls != expected
        or not work
        or any(not row["returned"] for row in work)
    ):
        _runtime_error(runtime, "Incomplete actual network iteration/order/returns")
    record = IterationEvidence(
        ordinal,
        source_time,
        source_frame,
        current[2],
        tuple(runtime.top_calls),
        work,
        calls,
        returns,
        "",
    )
    record = IterationEvidence(
        *tuple(getattr(record, name) for name in record.__dataclass_fields__ if name != "identity"),
        runtime.original.api._digest(_iteration_data(record)),
    )
    runtime.ledger.end(record)
    return record


def validate_iteration(claim, record, *, child, ordinal, source_time):
    runtime = _runtime_context(claim)
    if (
        child is not runtime.child
        or type(ordinal) is not int
        or not 0 <= ordinal < len(runtime.ledger.records)
        or runtime.ledger.records[ordinal] is not record
        or type(record) is not IterationEvidence
        or record.source_time is not source_time
        or record.ordinal != ordinal
        or _time_key(runtime, source_time) != runtime.ledger.keys[ordinal]
        or record.identity != runtime.original.api._digest(_iteration_data(record))
    ):
        _runtime_error(runtime, "Actual retained completed iteration record required")
    return record


def _history_data(runtime):
    return dict(
        law=LAW_ID,
        bound=runtime.ledger.bound,
        session=id(runtime.original.session),
        child=id(runtime.child),
        records=tuple((id(row), row.identity) for row in runtime.ledger.records),
        source=base._runtime_record_data(runtime),
    )


def finish_runtime(claim, *, child):
    runtime = _runtime_context(claim)
    module, caller = _ready(), sys._getframe(1)
    if (
        caller.f_code is not module.prepare.__code__
        or caller.f_globals is not vars(module)
        or caller.f_locals.get("context") is not child
        or child is not runtime.child
        or not runtime.active
        or runtime.record is not None
        or child.observing
        or child.primary is not None
        or child.capture_error is not None
        or not child.selected_stopped
        or child.loop_returned
        or runtime.ledger.current is not None
        or len(runtime.ledger.records) != runtime.ledger.bound
        or runtime.primary is not None
        or runtime.capture_error is not None
    ):
        _runtime_error(
            runtime, "Actual completed bounded source prefix required before final closure"
        )
    for row in runtime.ledger.records:
        validate_iteration(
            claim, row, child=child, ordinal=row.ordinal, source_time=row.source_time
        )
    runtime.record = HistoryEvidence(
        LAW_ID,
        runtime.ledger.bound,
        runtime.original.session,
        child,
        tuple(runtime.ledger.records),
        True,
        runtime.original.api._digest(_history_data(runtime)),
    )
    runtime.active = False
    return runtime.record


def validate_runtime_active(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child or not runtime.active or runtime.record is not None:
        _runtime_error(runtime, "Actual active continuous claim required")
    return claim


def validate_runtime(claim, *, child):
    runtime = _runtime_context(claim)
    record = runtime.record
    if (
        child is not runtime.child
        or runtime.active
        or type(record) is not HistoryEvidence
        or record.session is not runtime.original.session
        or record.child is not child
        or record.iterations != runtime.ledger.bound
        or record.source_completed is not True
        or len(record.records) != len(runtime.ledger.records)
        or any(a is not b for a, b in zip(record.records, runtime.ledger.records, strict=True))
        or record.identity != runtime.original.api._digest(_history_data(runtime))
    ):
        _runtime_error(runtime, "Actual successful continuous claim record required")
    for row in record.records:
        validate_iteration(
            claim, row, child=child, ordinal=row.ordinal, source_time=row.source_time
        )
    return record


def runtime_failed_context(claim):
    if type(claim) is not ShortMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise ShortRuntimeRejected("Actual continuous claim required", stage="claim")
    runtime = _RUNTIME[claim]
    if runtime.record is not None or not (
        runtime.invalid or runtime.primary is not None or runtime.capture_error is not None
    ):
        raise ShortRuntimeRejected("No actual failed continuous prefix", stage="failure")
    return runtime


# Reuse the reviewed source observer/member/ion metadata bodies verbatim.
# Only this provider's actual context/registry resolution is substituted.
_BODIES = {}
for _name in (
    "runtime_members",
    "runtime_codes",
    "runtime_permissions",
    "observe_runtime",
    "observes_runtime_frame",
    "runtime_wrapper_guard",
    "runtime_dispatch",
):
    _original = vars(base)[_name]
    _BODIES[_name] = FunctionType(_original.__code__, globals(), argdefs=_original.__defaults__)


def runtime_members(claim):
    return _checked_body("runtime_members")(claim)


def runtime_codes(claim):
    return _checked_body("runtime_codes")(claim)


def runtime_permissions(claim):
    return _checked_body("runtime_permissions")(claim)


def observes_runtime_frame(claim, frame):
    return _checked_body("observes_runtime_frame")(claim, frame)


def runtime_wrapper_guard(claim, *, child, original, frame):
    return _checked_body("runtime_wrapper_guard")(
        claim, child=child, original=original, frame=frame
    )


def runtime_dispatch(claim, *, child, original, label, delegate, actual, args, kwargs, frame):
    return _checked_body("runtime_dispatch")(
        claim,
        child=child,
        original=original,
        label=label,
        delegate=delegate,
        actual=actual,
        args=args,
        kwargs=kwargs,
        frame=frame,
    )


def _runtime_observer(runtime, caller, frame, event, arg):
    report = getattr(runtime, "report", None)
    if (
        report is None
        or report[0] is not caller
        or caller.f_code is not observe_runtime.__code__
        or caller.f_globals is not globals()
        or caller.f_locals.get("claim") is not runtime.claim
        or caller.f_locals.get("child") is not runtime.child
        or report[2] is not frame
        or report[3] is not event
        or report[4] is not arg
    ):
        _runtime_error(runtime, "Actual local continuous observer adapter required")
    base._runtime_observer(runtime, report[1], frame, event, arg)


def observe_runtime(claim, *, child, frame, event, arg):
    # The reused body retains raw return/source errors before fallible auditing.
    # Actual stack identities are kept here, never a supplied observer receipt.
    if type(claim) is not ShortMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise ShortRuntimeRejected("Actual issued continuous runtime claim required", stage="claim")
    runtime = _RUNTIME[claim]
    if event == "return":
        runtime.last_raw = (frame, arg)
        # A trace exception can be handled normally. Only the real abnormal
        # return promotes its exact pending exception; do this before any
        # fallible delegate authentication can replace the active unwind.
        if runtime.primary_origin != "source" and not runtime.original.initial._normal_return(
            frame
        ):
            source_primary = runtime.pending.get(id(frame))
            if source_primary is not None:
                runtime.primary, runtime.primary_origin = source_primary, "source"
    elif event == "exception":
        runtime.last_source_error = (frame, arg[1])
    if getattr(runtime, "report", None) is not None:
        _runtime_error(runtime, "Overlapping continuous observer report")
    runtime.report = (sys._getframe(), sys._getframe(1), frame, event, arg)
    try:
        try:
            body = _checked_body("observe_runtime")
        except BaseException as error:
            runtime.invalid = True
            if event == "exception":
                runtime.primary, runtime.primary_origin = arg[1], "source"
            _capture(runtime, "observer_delegate", error, (frame, event, arg))
            if event in ("exception", "c_exception") or (
                event == "return" and runtime.primary_origin == "source"
            ):
                return None
            raise CaptureStop(
                "Continuous observer delegate changed", stage="runtime_capture", partial=runtime
            ) from error
        returned = body(claim, child=child, frame=frame, event=event, arg=arg)
        if (
            runtime.capture_error is not None
            and runtime.primary_origin != "source"
            and event not in ("exception", "c_exception")
        ):
            raise CaptureStop(
                "Incomplete continuous observer admission", stage="runtime_capture", partial=runtime
            ) from runtime.capture_error
        return returned
    finally:
        runtime.report = None


def _checked_body(name):
    if _BODIES is not _BODY_TABLE or tuple(_BODIES) != tuple(row[0] for row in _BODY_SPECS):
        raise ShortRuntimeRejected(
            "Original continuous delegate table/roster changed", stage="delegate"
        )
    for key, original, body, original_state, body_state in _BODY_SPECS:
        if (
            vars(base).get(key) is not original
            or _BODIES.get(key) is not body
            or type(body) is not FunctionType
            or body.__code__ is not original.__code__
            or body.__globals__ is not globals()
            or body.__defaults__ is not original.__defaults__
        ):
            raise ShortRuntimeRejected(
                "Exact pinned continuous delegate required", stage="delegate"
            )
        base._function_bindings(body)  # Includes cached builtin/global association refusal.
        base.wrapper_authority._same(base._function_bindings(original), original_state)
        base.wrapper_authority._same(base._function_bindings(body), body_state)
    return _BODIES[name]


_BODY_TABLE = _BODIES
_BODY_SPECS = tuple(
    (
        name,
        vars(base)[name],
        body,
        base._function_bindings(vars(base)[name]),
        base._function_bindings(body),
    )
    for name, body in _BODIES.items()
)
