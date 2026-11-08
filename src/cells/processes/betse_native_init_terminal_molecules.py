"""Held molecular runtime for a natural, full-calendar INIT terminal.

This is a separate pre-source claimant. A selected short-history owner never
enters this domain. Existing numerical/observer bodies remain in their actual
source producers; only metadata accounting and natural closure are added here.
The future terminal consumer and ancestor hooks require explicit adoption.
"""

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from threading import RLock, get_ident
from types import FrameType, FunctionType, ModuleType, SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_init_molecule_short_runtime as previous

base, channels, interfaces = previous.base, previous.channels, previous.interfaces
struct = previous.struct  # Reused clock body resolves this exact metadata module.
LAW_ID = "actual_original_INIT_natural_calendar_terminal_molecules@1"
MAX_ITERATIONS, MAX_WORK = 512, previous.MAX_WORK
PREVIOUS_SOURCE_SHA256 = '597671ce890a609e3a1584362646c73370429be850c65c2cc091dcc3d4ca7476'
BASE_INTERFACE_SHA256 = 'dd77276a16c4e3aeb118bf5bb84eecc6bf9ce748a3ed76d98ee5739c44d039c9'
BASE_REVIEW_SHA256 = '060c601d58a511985dc87b9d68b1d88c5a8c8f2173c28140a9e0167e0a8bd5df'
CONSUMER_MODULE = "cells.processes.betse_native_init_terminal"
CONSUMER_INTERFACE_SHA256 = 'ac752826a48ae30a032c1e04fd4e9a2e146147d1496865eedab833511f179fa8'
CONSUMER_REVIEW_SHA256 = 'b7efb6935e042ad8e325c1dc5da35294345af509f2dd2ef24be7dceb057a0056'
CONSUMER_BINDING_KIND = "exact_INIT_natural_terminal_except_four_parent_runtime_backrefs@1"
CONSUMER_BACK_REFERENCE_SLOTS = previous.CONSUMER_BACK_REFERENCE_SLOTS
ANCESTOR_CLAIM = "_claim_terminal_init_ancestor"
ANCESTOR_ROUTE = "_terminal_init_route"
ANCESTOR_REGISTRY = "_TERMINAL_INIT_DESCENDANTS"
ANCESTOR_ATTRIBUTE = "terminal_init_descendant"
# This selects the unchanged per-iteration observer's continuous INIT shape.
# It is not an owner/disposition: the new claim/law and natural terminal record
# below carry authority. No old claim or registry entry is reused or relabelled.
OBSERVER_MODE = "short_history"
_RUNTIME, _BOUND = WeakKeyDictionary(), WeakKeyDictionary()
_FAILED, _LOCK = [], RLock()
CaptureStop, MoleculeNetworkRejected = previous.CaptureStop, previous.MoleculeNetworkRejected
_capture, _runtime_error = previous._capture, previous._runtime_error
_runtime_expressions, _runtime_mappings = previous._runtime_expressions, previous._runtime_mappings
_runtime_resolution = previous._runtime_resolution
IterationEvidence = previous.IterationEvidence


class TerminalRuntimeRejected(base.MoleculeNetworkRejected):
    pass


class TerminalMoleculeRuntimeClaim:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Only the actual fresh terminal ancestor transfer may issue this claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("A native terminal claim is process-local, never checkpoint input")


MoleculeRuntimeClaim = TerminalMoleculeRuntimeClaim


@dataclass(frozen=True, slots=True)
class TerminalEvidence:
    law: str
    session: object
    child: object
    calendar: object
    sampled: object
    solver_context: object
    records: tuple
    loop_return: tuple
    context_return: tuple
    selected_stop: bool
    natural_loop_returned: bool
    context_exited_normally: bool
    before_native_pickle: bool
    identity: str


def _terminal_count(value):
    if type(value) is not int or not 1 <= value <= MAX_ITERATIONS:
        raise ValueError("Exact full-calendar terminal integer bound in [1,512] required")
    return value


class _TerminalIterations(previous._Iterations):
    """Separate pure metadata bound; reuse unchanged pairing, never an old owner."""

    def __init__(self, count):
        self.bound, self.current, self.invalid = _terminal_count(count), None, False
        self.records, self.keys = [], []


class _FullCalendar:
    """Pure bounded metadata; this ledger cannot issue a native parent."""

    def __init__(self, configured_count, maximum):
        _terminal_count(maximum)
        if type(configured_count) is not int or not 1 <= configured_count <= maximum:
            raise ValueError("Complete configured INIT calendar exceeds the declared bound")
        self.configured_count, self.maximum = configured_count, maximum
        self.iterations = _TerminalIterations(configured_count)
        self.calendar = self.sampled = self.solver_context = None
        self.raw_calendar = None
        self.loop_return = self.context_return = None
        self.invalid = False

    def bind_calendar(self, raw, *, calendar, sampled, solver_context):
        if (
            self.invalid
            or self.raw_calendar is not None
            or type(raw) is not tuple
            or len(raw) != 3
            or raw[0] is not calendar
            or raw[1] is not sampled
            or raw[2] is not solver_context
            or len(calendar) != self.configured_count
            or type(sampled) is not set
        ):
            self.invalid = True
            raise ValueError("Actual complete unsliced calendar/sampling/context return required")
        self.raw_calendar = raw
        self.calendar, self.sampled, self.solver_context = raw

    def natural_loop_end(self, frame, returned, *, normal, selected_stop):
        if (
            self.invalid
            or self.raw_calendar is None
            or self.loop_return is not None
            or type(normal) is not bool
            or normal is not True
            or selected_stop is not False
            or self.iterations.invalid
            or self.iterations.current is not None
            or len(self.iterations.records) != self.configured_count
        ):
            self.invalid = True
            raise ValueError("Natural complete original loop return required; no selected prefix")
        self.loop_return = (frame, returned)

    def normal_context_end(self, frame, returned, *, normal, exception_arguments):
        if (
            self.invalid
            or self.loop_return is None
            or self.context_return is not None
            or normal is not True
            or type(exception_arguments) is not tuple
            or len(exception_arguments) != 3
            or any(value is not None for value in exception_arguments)
        ):
            self.invalid = True
            raise ValueError("Original solver context must exit normally after natural loop end")
        self.context_return = (frame, returned)

    def complete(self):
        if (
            self.invalid
            or self.loop_return is None
            or self.context_return is None
            or self.iterations.invalid
            or self.iterations.current is not None
            or self.iterations.bound != self.configured_count
            or len(self.iterations.records) != self.configured_count
            or len(self.iterations.keys) != self.configured_count
        ):
            raise ValueError("Incomplete actual natural terminal protocol")
        return self


def source_plan():
    return dict(
        law=LAW_ID,
        max_iterations=MAX_ITERATIONS,
        max_total_work=MAX_WORK,
        previous_source=PREVIOUS_SOURCE_SHA256,
        base_interface=(BASE_INTERFACE_SHA256, BASE_REVIEW_SHA256),
        consumer=(CONSUMER_MODULE, CONSUMER_INTERFACE_SHA256, CONSUMER_REVIEW_SHA256),
        consumer_binding=(CONSUMER_BINDING_KIND, CONSUMER_BACK_REFERENCE_SLOTS),
        required_ancestor=(ANCESTOR_CLAIM, ANCESTOR_ROUTE, ANCESTOR_REGISTRY),
        internal_observer_shape=OBSERVER_MODE,
        natural_complete_calendar_not_selected_stop=True,
        requires_original_normal_solver_context_exit=True,
        before_native_pickle=True,
        native_pickle_whole_phase_or_SIM_admission=False,
        old_short_first_owners_or_claims_reused=False,
        numerical_bodies_reused_not_copied=True,
        full_native_or_scientific_release=False,
    )


def consumer_binding(payload):
    return FunctionType(
        interfaces._helper_binding.__code__,
        dict(
            vars(interfaces),
            HELPER_BINDING_KIND=CONSUMER_BINDING_KIND,
            HELPER_BACK_REFERENCE_SLOTS=CONSUMER_BACK_REFERENCE_SLOTS,
        ),
    )(payload)


def _dependency():
    path = Path(__file__).with_name("betse_native_init_molecule_short_runtime.py")
    if (
        sys.modules.get("cells.processes.betse_native_init_molecule_short_runtime") is not previous
        or path.is_symlink()
        or Path(previous.__file__).resolve() != path.resolve()
        or hashlib.sha256(path.read_bytes()).hexdigest() != PREVIOUS_SOURCE_SHA256
    ):
        raise TerminalRuntimeRejected("Exact reviewed metadata provider required", stage="producer")
    for name, function, state in _REUSED_SPECS:
        if vars(previous).get(name) is not function:
            raise TerminalRuntimeRejected(
                "Original metadata helper alias changed", stage="producer"
            )
        base.wrapper_authority._same(base._function_bindings(function), state)
    if (
        previous._Iterations is not _PREVIOUS_LEDGER
        or _TerminalIterations.__bases__ != (_PREVIOUS_LEDGER,)
        or _TerminalIterations.begin is not _PREVIOUS_LEDGER.begin
        or _TerminalIterations.end is not _PREVIOUS_LEDGER.end
    ):
        raise TerminalRuntimeRejected("Original bounded metadata ledger changed", stage="producer")
    for name, function, state in _LEDGER_SPECS:
        if vars(_PREVIOUS_LEDGER).get(name) is not function:
            raise TerminalRuntimeRejected("Original metadata ledger body changed", stage="producer")
        base.wrapper_authority._same(base._function_bindings(function), state)
    for (
        owner,
        name,
        function,
        code,
        namespace,
        defaults,
        keywords,
        closure,
        cached,
    ) in _LOCAL_SIGNATURES:
        if (
            (globals() if owner is None else vars(owner)).get(name) is not function
            or function.__code__ is not code
            or function.__globals__ is not namespace
            or function.__defaults__ is not defaults
            or function.__kwdefaults__ is not keywords
            or function.__closure__ is not closure
            or function.__builtins__ is not cached
        ):
            raise TerminalRuntimeRejected(
                "Original terminal metadata body changed", stage="producer"
            )
        base.wrapper_authority._same(base._function_bindings(function), _LOCAL_EFFECTIVE[function])


def _ready():
    if not all(
        base._pin(value)
        for value in (
            BASE_INTERFACE_SHA256,
            BASE_REVIEW_SHA256,
            CONSUMER_INTERFACE_SHA256,
            CONSUMER_REVIEW_SHA256,
        )
    ):
        raise TerminalRuntimeRejected(
            "Natural terminal source/ancestor adoption held", stage="held"
        )
    _dependency()
    path = Path(base.__file__)
    identity, backrefs = previous.base_binding(path.read_bytes())
    completion = base._ready()
    if (
        identity != BASE_INTERFACE_SHA256
        or completion.MOLECULE_REVIEW_SHA256 != BASE_REVIEW_SHA256
        or completion.TERMINAL_RUNTIME_MODULE != __name__
        or completion.TERMINAL_RUNTIME_SHA256
        != hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
        or not base._pin(completion.TERMINAL_RUNTIME_REVIEW_SHA256)
    ):
        raise TerminalRuntimeRejected("Original network interface changed", stage="producer")
    previous._check_base_backrefs(
        backrefs,
        Path(completion.__file__).read_bytes(),
        completion.previous.COMPLETION_REVIEW_SHA256,
    )
    consumer = sys.modules.get(CONSUMER_MODULE)
    path = Path(__file__).with_name("betse_native_init_terminal.py")
    if (
        type(consumer) is not ModuleType
        or path.is_symlink()
        or Path(consumer.__file__).resolve() != path.resolve()
    ):
        raise TerminalRuntimeRejected(
            "Actual terminal consumer namespace required", stage="consumer"
        )
    identity, backrefs = consumer_binding(path.read_bytes())
    expected = (
        (
            "PARENT_SOURCE_SHA256",
            hashlib.sha256(Path(consumer.base.previous.__file__).read_bytes()).hexdigest(),
        ),
        ("PARENT_REVIEW_SHA256", consumer.base.previous.TERMINAL_INIT_PARENT_REVIEW_SHA256),
        ("RUNTIME_SOURCE_SHA256", hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
        ("RUNTIME_REVIEW_SHA256", completion.TERMINAL_RUNTIME_REVIEW_SHA256),
    )
    if (
        identity != CONSUMER_INTERFACE_SHA256
        or backrefs != expected
        or any(
            not base._pin(value) or vars(consumer).get(name) != value for name, value in backrefs
        )
        or consumer.RUNTIME_CONTRACT != LAW_ID
        or consumer.base.previous.TERMINAL_INIT_REVIEW_SHA256 != CONSUMER_REVIEW_SHA256
    ):
        raise TerminalRuntimeRejected("Original terminal source/backrefs changed", stage="consumer")
    names = ("_ready", "_begin", "_end", "_observe", "prepare", "_terminal_runtime_status")
    interfaces._source_interface(consumer, path.read_bytes(), path, names)
    consumer._ready()
    return consumer


def _route(runtime):
    consumer = _ready()
    original, c, child, lease = runtime.original, runtime.completion, runtime.child, runtime.lease
    registry = vars(original.api).get(ANCESTOR_REGISTRY)
    owner = child.request.electrical_owner
    issued = consumer.base.previous._ISSUED.get(owner)
    if (
        runtime.invalid
        or original.invalid
        or c.invalid
        or child.invalid
        or runtime.full.invalid
        or runtime.ledger.invalid
        or runtime.thread != get_ident()
        or type(runtime.kind) is not str
        or runtime.kind != OBSERVER_MODE
        or original.p.init_tsteps != runtime.full.configured_count
        or type(original.p.init_tsteps) is not int
        or child.request.maximum != runtime.full.maximum
        or runtime.ledger is not runtime.full.iterations
        or _RUNTIME.get(runtime.claim) is not runtime
        or _BOUND.get(original.session) is not runtime
        or base._SESSIONS.get(original.session) is not original
        or base._CLAIMED.get(c.claim) is not original
        or original.completion is not c
        or c.molecule is not base
        or c.molecule_session is not original.session
        or original.api._CLAIMS.get(c.claim) is not c
        or type(registry) is not WeakKeyDictionary
        or registry.get(c.owner) is not lease
        or vars(c).get(ANCESTOR_ATTRIBUTE) is not lease
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
        or child.phase is not original.phase
        or child.p is not original.p
        or child.sim is not original.sim
        or child.cells is not original.cells
        or child.thread != runtime.thread
        or type(child.request) is not consumer.Request
        or consumer._REQUESTS.get(child.request) is not child.refs
        or consumer._CONSUMED.get(child.request) is not child
        or consumer._RETIRED.get(child.request.electrical_owner) is not child
        or type(owner) is not consumer.base.previous.ElectricalOwner
        or owner is not runtime.electrical.owner
        or type(issued) is not tuple
        or len(issued) != 2
        or issued[0] is not runtime.electrical
        or issued[1] is not runtime.electrical.trial
        or original.session in base._STEP_RUNTIME
        or original.session in previous._BOUND
        or hasattr(c, "first_step_descendant")
        or hasattr(c, "short_init_descendant")
    ):
        raise TerminalRuntimeRejected(
            "Actual fresh terminal ancestry/epoch changed", stage="ancestry", partial=runtime
        )
    original.initial.core.previous._same(base._bindings(original), runtime.source_bindings)
    for name, original_fn, body, before, local in runtime.reused_bindings:
        if vars(base).get(name) is not original_fn or _BODIES.get(name) is not body:
            raise ValueError("Original reused source observer changed")
        base.wrapper_authority._same(base._function_bindings(original_fn), before)
        base.wrapper_authority._same(base._function_bindings(body), local)
    base._dynamic_associations(original)
    _runtime_expressions(runtime)
    _runtime_mappings(runtime)
    return runtime


def _runtime_context(claim):
    if type(claim) is not TerminalMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise TerminalRuntimeRejected("Actual issued terminal runtime required", stage="claim")
    return _route(_RUNTIME[claim])


def _runtime_route(runtime):
    return _route(runtime)


def bind_terminal(session, *, completion, storage, electrical, child, maximum):
    consumer, frame = _ready(), sys._getframe(1)
    c, api = completion, sys.modules.get(base.COMPLETION_MODULE)
    entry = vars(api).get(ANCESTOR_CLAIM) if type(api) is ModuleType else None
    if (
        type(entry) is not FunctionType
        or frame.f_code is not entry.__code__
        or frame.f_globals is not vars(api)
        or frame.f_locals.get("context") is not c
        or frame.f_locals.get("storage") is not storage
        or frame.f_locals.get("electrical") is not electrical
        or frame.f_locals.get("transition") is not child
    ):
        raise TerminalRuntimeRejected(
            "Actual fresh Completion terminal transfer required", stage="entry"
        )
    original = base._context(session, c.claim)
    count = original.p.init_tsteps
    full = _FullCalendar(count, maximum)
    lease = vars(c).get(ANCESTOR_ATTRIBUTE)
    with _LOCK:
        if (
            session in _BOUND
            or session in previous._BOUND
            or session in base._STEP_RUNTIME
            or hasattr(c, "first_step_descendant")
            or hasattr(c, "short_init_descendant")
            or not child.active
            or child.claimed
            or child.setup_frame is not None
            or child.loop_frame is not None
            or child.request.maximum != maximum
            or lease.child is not child
            or lease.status != "reserved"
            or lease.iterations != count
            or consumer._CONSUMED.get(child.request) is not child
        ):
            raise TerminalRuntimeRejected(
                "Fresh bounded full-calendar transfer required", stage="consumed"
            )
        claim = object.__new__(TerminalMoleculeRuntimeClaim)
        runtime = SimpleNamespace(
            claim=claim,
            original=original,
            completion=c,
            storage=storage,
            electrical=electrical,
            child=child,
            lease=lease,
            kind=OBSERVER_MODE,
            full=full,
            ledger=full.iterations,
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
            terminal_status=None,
            record=None,
        )
        _RUNTIME[claim] = _BOUND[session] = runtime
        lease.molecule_claim = claim
        try:
            route = vars(api).get(ANCESTOR_ROUTE)
            if type(route) is not FunctionType or route.__globals__ is not vars(api):
                raise ValueError("Actual terminal parent route unavailable")
            route(c, storage, electrical, child)
            old = base._STORAGE_RUNTIME.get(session)
            if old is None or old.child is not storage or old.record is None or old.invalid:
                raise ValueError("Actual completed molecular storage required")
            if (
                original.core.mit_enabled is not False
                or original.core.transporters
                or original.core.modulators
            ):
                raise ValueError("Unowned mitochondrial/transporter/modulator work")
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
                    raise ValueError("Unowned molecule pumping/gating/boundary/clamp work")
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
                    raise ValueError("Actual initialized original expression text required")
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
            if len({id(obj) for obj, _ in permissions}) != len(permissions):
                raise ValueError("Each actual terminal runtime holder must be unique")
            runtime.permissions = tuple(permissions)
            path = Path(base.__file__)
            original.api.previous.previous.previous._ready()._source_interface(
                base, path.read_bytes(), path, tuple(_BODIES)
            )
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
                error.molecule_terminal_partial = runtime
            except BaseException as secondary:
                _capture(runtime, "failure_attachment", secondary, error)
            raise


def session_of(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child:
        _runtime_error(runtime, "Different actual terminal child")
    return runtime.original.session


def session_provider(claim, *, child):
    session_of(claim, child=child)
    return base


def begin_iteration(claim, *, child, ordinal, source_time, source_frame):
    runtime = _runtime_context(claim)
    current = _boundary(runtime, child, ordinal, source_time, source_frame, "_begin")
    if runtime.full.raw_calendar is None:
        raw = child.calendar_raw
        if (
            ordinal != 0
            or type(raw) is not tuple
            or len(raw) != 3
            or type(raw[0]) is not runtime.completion.numpy.ndarray
            or raw[0].ndim != 1
            or raw[0].dtype != runtime.completion.numpy.dtype("float64")
        ):
            _runtime_error(runtime, "Actual original full calendar ndarray required")
        runtime.full.bind_calendar(
            raw, calendar=child.time_steps, sampled=child.sampled, solver_context=raw[2]
        )
    if (
        source_frame.f_locals.get("t") is not source_time
        or source_frame.f_locals.get("time_steps") is not runtime.full.calendar
        or source_frame.f_locals.get("time_steps_sampled") is not runtime.full.sampled
        or _time_key(runtime, source_time) != _time_key(runtime, runtime.full.calendar[ordinal])
    ):
        _runtime_error(runtime, "Original full calendar/source label association changed")
    runtime.ledger.begin(
        ordinal,
        source_time,
        _time_key(runtime, source_time),
        source_frame,
        current[2],
        (len(runtime.work), len(runtime.c_calls), len(runtime.raw_returns)),
    )
    runtime.top_calls = []
    return claim


def finish_iteration(claim, *, child, ordinal, source_time, source_frame):
    runtime = _runtime_context(claim)
    current = _boundary(runtime, child, ordinal, source_time, source_frame, "_end")
    pending = runtime.ledger.current
    if (
        pending is None
        or pending[0] != ordinal
        or pending[1] is not source_time
        or pending[2] != _time_key(runtime, source_time)
        or pending[3] is not source_frame
        or pending[4] is not current[2]
    ):
        _runtime_error(runtime, "Original full-calendar begin/end pairing changed")
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
        _runtime_error(runtime, "Incomplete actual terminal molecular iteration")
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
    return _VALIDATE_ITERATION(claim, record, child=child, ordinal=ordinal, source_time=source_time)


def _terminal_data(runtime):
    return dict(
        law=LAW_ID,
        session=id(runtime.original.session),
        child=id(runtime.child),
        calendar=id(runtime.full.calendar),
        sampled=id(runtime.full.sampled),
        solver_context=id(runtime.full.solver_context),
        raw_calendar=id(runtime.full.raw_calendar),
        terminal_status=id(runtime.terminal_status),
        complete_configured_count=runtime.full.configured_count,
        maximum=runtime.full.maximum,
        records=tuple((id(row), row.identity) for row in runtime.ledger.records),
        loop=tuple(id(value) for value in runtime.full.loop_return),
        context=tuple(id(value) for value in runtime.full.context_return),
        source=base._runtime_record_data(runtime),
    )


def _natural_status(runtime, consumer):
    """Check actual retained source returns; a status copy is not a witness."""
    child, full = runtime.child, runtime.full
    status = consumer._terminal_runtime_status(child)
    if (
        type(status) is not consumer.NaturalTerminalStatus
        or status is not child.terminal_status
        or status.child is not child
        or status.calendar_raw is not full.raw_calendar
        or child.calendar_raw is not full.raw_calendar
        or child.time_steps is not full.calendar
        or child.sampled is not full.sampled
        or child.solver_context is not full.solver_context
        or status.selected_stop is not False
        or status.before_native_pickle is not True
        or type(status.loop_raw) is not tuple
        or len(status.loop_raw) != 2
        or type(status.context_raw) is not tuple
        or len(status.context_raw) != 2
        or status.loop_frame is not child.loop_frame
        or type(status.loop_frame) is not FrameType
        or type(status.context_frame) is not FrameType
        or status.loop_raw[0] is not status.loop_frame
        or status.context_raw[0] is not status.context_frame
        or status.loop_frame.f_code is not child.loop_code
        or status.loop_frame.f_locals.get("self") is not runtime.original.sim
        or status.loop_frame.f_locals.get("phase") is not runtime.original.phase
        or status.loop_frame.f_locals.get("time_steps") is not full.calendar
        or status.loop_frame.f_locals.get("time_steps_sampled") is not full.sampled
        or status.context_frame.f_code is not child.noop_methods[1].__code__
        or status.context_frame.f_globals is not child.noop_methods[1].__globals__
        or status.context_frame.f_locals.get("self") is not full.solver_context
        or type(status.exception_arguments) is not tuple
        or len(status.exception_arguments) != 3
        or any(value is not None for value in status.exception_arguments)
        or any(
            name not in status.context_frame.f_locals
            or status.context_frame.f_locals[name] is not None
            for name in ("typ", "value", "traceback")
        )
    ):
        _runtime_error(runtime, "Actual complete calendar/normal source return required")
    for role, raw in (
        ("_run_sim_core_loop", status.loop_raw),
        ("solver_context_exit", status.context_raw),
    ):
        frame = raw[0]
        row = child.frames.get(id(frame))
        if (
            type(row) is not dict
            or row.get("frame") is not frame
            or row.get("code") is not frame.f_code
            or row.get("globals") is not frame.f_globals
            or row.get("name") != role
            or row.get("returned") is not True
            or row.get("suspended") is not False
            or not any(value is raw for value in child.raw_returns)
            or not runtime.original.initial._normal_return(frame)
        ):
            _runtime_error(runtime, "Actual admitted normal source return witness required")
    return status


def _finish_runtime(claim, *, child):
    runtime, consumer = _runtime_context(claim), _ready()
    caller = sys._getframe(2)
    if (
        caller.f_code is not consumer.prepare.__code__
        or caller.f_globals is not vars(consumer)
        or caller.f_locals.get("context") is not child
        or child is not runtime.child
        or not runtime.active
        or runtime.record is not None
        or child.observing
        or child.primary is not None
        or child.capture_error is not None
        or runtime.primary is not None
        or runtime.capture_error is not None
    ):
        _runtime_error(runtime, "Actual natural terminal caller/clean epoch required")
    status = _natural_status(runtime, consumer)
    runtime.terminal_status = status
    runtime.full.natural_loop_end(
        status.loop_frame,
        status.loop_raw[1],
        normal=runtime.original.initial._normal_return(status.loop_frame),
        selected_stop=status.selected_stop,
    )
    runtime.full.normal_context_end(
        status.context_frame,
        status.context_raw[1],
        normal=runtime.original.initial._normal_return(status.context_frame),
        exception_arguments=status.exception_arguments,
    )
    runtime.full.complete()
    for row in runtime.ledger.records:
        validate_iteration(
            claim, row, child=child, ordinal=row.ordinal, source_time=row.source_time
        )
    record = TerminalEvidence(
        LAW_ID,
        runtime.original.session,
        child,
        runtime.full.calendar,
        runtime.full.sampled,
        runtime.full.solver_context,
        tuple(runtime.ledger.records),
        runtime.full.loop_return,
        runtime.full.context_return,
        False,
        True,
        True,
        True,
        runtime.original.api._digest(_terminal_data(runtime)),
    )
    runtime.record, runtime.active = record, False
    return record


def finish_runtime(claim, *, child):
    if type(claim) is not TerminalMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise TerminalRuntimeRejected("Actual terminal runtime required", stage="claim")
    runtime = _RUNTIME[claim]
    if runtime.invalid:
        if runtime.primary is not None:
            raise runtime.primary
        raise TerminalRuntimeRejected(
            "Terminal closure already refused", stage="failure", partial=runtime
        )
    try:
        return _finish_runtime(claim, child=child)
    except BaseException as error:
        runtime.invalid = True
        if runtime.primary is None:
            runtime.primary, runtime.primary_origin = error, "closure"
        elif runtime.primary is not error:
            _capture(runtime, "terminal_closure", error, (child, runtime.last_raw))
        try:
            _FAILED.append(runtime)
        except BaseException as secondary:
            _capture(runtime, "failure_registry", secondary, error)
        try:
            error.molecule_terminal_partial = runtime
        except BaseException as secondary:
            _capture(runtime, "failure_attachment", secondary, error)
        if runtime.primary_origin == "source" and runtime.primary is not error:
            # Keep the original source cause; secondary closure evidence is
            # retained above rather than installed as a replacement cause.
            raise runtime.primary.with_traceback(runtime.primary.__traceback__)  # noqa: B904
        raise


def validate_runtime_active(claim, *, child):
    runtime = _runtime_context(claim)
    if child is not runtime.child or not runtime.active or runtime.record is not None:
        _runtime_error(runtime, "Actual active natural terminal runtime required")
    return claim


def validate_runtime(claim, *, child):
    runtime = _runtime_context(claim)
    consumer = _ready()
    record = runtime.record
    if (
        child is not runtime.child
        or runtime.active
        or type(record) is not TerminalEvidence
        or record.law != LAW_ID
        or record.session is not runtime.original.session
        or record.child is not child
        or record.calendar is not runtime.full.calendar
        or record.sampled is not runtime.full.sampled
        or record.solver_context is not runtime.full.solver_context
        or record.loop_return is not runtime.full.loop_return
        or record.context_return is not runtime.full.context_return
        or record.selected_stop is not False
        or record.natural_loop_returned is not True
        or record.context_exited_normally is not True
        or record.before_native_pickle is not True
        or len(record.records) != len(runtime.ledger.records)
        or any(a is not b for a, b in zip(record.records, runtime.ledger.records, strict=True))
        or record.identity != runtime.original.api._digest(_terminal_data(runtime))
    ):
        _runtime_error(runtime, "Actual unchanged natural terminal record required")
    status = _natural_status(runtime, consumer)
    if (
        status is not runtime.terminal_status
        or any(a is not b for a, b in zip(status.loop_raw, record.loop_return, strict=True))
        or any(a is not b for a, b in zip(status.context_raw, record.context_return, strict=True))
    ):
        _runtime_error(runtime, "Actual terminal consumer evidence changed after closure")
    runtime.full.complete()
    for row in record.records:
        validate_iteration(
            claim, row, child=child, ordinal=row.ordinal, source_time=row.source_time
        )
    return record


def runtime_failed_context(claim):
    if type(claim) is not TerminalMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise TerminalRuntimeRejected("Actual terminal runtime required", stage="claim")
    runtime = _RUNTIME[claim]
    if runtime.record is not None or not (
        runtime.invalid or runtime.primary is not None or runtime.capture_error is not None
    ):
        raise TerminalRuntimeRejected("No failed actual terminal prefix", stage="failure")
    return runtime


_REUSED = (
    "_count",
    "_time_key",
    "_boundary",
    "_runtime_entry",
    "_iteration_data",
    "begin_iteration",
    "finish_iteration",
    "validate_iteration",
    "observe_runtime",
    "_runtime_observer",
    "_checked_body",
)
_REUSED_SPECS = tuple(
    (name, vars(previous)[name], base._function_bindings(vars(previous)[name])) for name in _REUSED
)
_PREVIOUS_LEDGER = previous._Iterations
_LEDGER_SPECS = tuple(
    (name, function, base._function_bindings(function))
    for name, function in vars(_PREVIOUS_LEDGER).items()
    if type(function) is FunctionType
)

# Reuse only metadata observer/clock bodies. Their actual imported owner code
# and effective global/builtin bindings are authenticated by _dependency().
_time_key = FunctionType(previous._time_key.__code__, globals())
_boundary = FunctionType(previous._boundary.__code__, globals())
_runtime_entry = FunctionType(previous._runtime_entry.__code__, globals())
_iteration_data = previous._iteration_data
_VALIDATE_ITERATION = FunctionType(previous.validate_iteration.__code__, globals())
_runtime_observer = FunctionType(previous._runtime_observer.__code__, globals())
ShortMoleculeRuntimeClaim, ShortRuntimeRejected = (
    TerminalMoleculeRuntimeClaim,
    TerminalRuntimeRejected,
)
_BODIES = {
    name: FunctionType(vars(base)[name].__code__, globals(), argdefs=vars(base)[name].__defaults__)
    for name in previous._BODIES
}


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


def observe_runtime(claim, *, child, frame, event, arg):
    if type(claim) is not TerminalMoleculeRuntimeClaim or claim not in _RUNTIME:
        raise TerminalRuntimeRejected("Actual issued terminal runtime required", stage="claim")
    runtime = _RUNTIME[claim]
    if event == "return":
        runtime.last_raw = (frame, arg)
        if runtime.primary_origin != "source" and not runtime.original.initial._normal_return(
            frame
        ):
            source_primary = runtime.pending.get(id(frame))
            if source_primary is not None:
                runtime.primary, runtime.primary_origin = source_primary, "source"
    elif event == "exception":
        runtime.last_source_error = (frame, arg[1])
    if getattr(runtime, "report", None) is not None:
        _runtime_error(runtime, "Overlapping terminal observer report")
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
                "Terminal observer delegate changed", stage="runtime_capture", partial=runtime
            ) from error
        returned = body(claim, child=child, frame=frame, event=event, arg=arg)
        if (
            runtime.capture_error is not None
            and runtime.primary_origin != "source"
            and event not in ("exception", "c_exception")
        ):
            raise CaptureStop(
                "Incomplete terminal observer", stage="runtime_capture", partial=runtime
            ) from runtime.capture_error
        return returned
    finally:
        runtime.report = None


_checked_body = FunctionType(previous._checked_body.__code__, globals())
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
_LOCAL_SIGNATURES = tuple(
    (
        owner,
        name,
        function,
        function.__code__,
        function.__globals__,
        function.__defaults__,
        function.__kwdefaults__,
        function.__closure__,
        function.__builtins__,
    )
    for owner in (None, TerminalMoleculeRuntimeClaim, _TerminalIterations, _FullCalendar)
    for name, function in tuple((globals() if owner is None else vars(owner)).items())
    if type(function) is FunctionType and function.__globals__ is globals()
)
# Populate after all signature/export tables exist. Effective bindings include
# the live table identity; no self-referential tuple is rebuilt on validation.
_LOCAL_EFFECTIVE = {}
for _row in _LOCAL_SIGNATURES:
    _LOCAL_EFFECTIVE[_row[2]] = base._function_bindings(_row[2])
del _row
