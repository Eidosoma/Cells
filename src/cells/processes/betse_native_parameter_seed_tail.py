"""One fresh SEED-tail parameter mutation from an actual closed dyna claim.

The consumer executes/authenticates the native phase tail. This module grants
only the absent -> exact False _run_sim boundary on the same retained p; it
executes no native method and certifies no phase/handler admission.
"""

import ast
import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_dyna_construction as previous

SEED_TAIL_LAW = "betse_same_parameter_seed_tail_mutation@1"
PREVIOUS_SHA256 = "d9b444ae8991140f7b92f084d1c929a9a01cdc816b4cb7fa725798e495111f8d"
PHASE_SHA256 = "e7c129aca1930fcb31884f32d4f2ebbb46d31113a66887a39c85ba0009b78ea8"
RELEASE = "CELLS_NATIVE_PARAMETER_SEED_TAIL_RELEASED"
leases, parameters = previous.previous, previous.parameters
prefix = parameters.paths.prefix
_LOCK, _ACTIVE = Lock(), []
_ISSUED, _CONSUMED, _OWNERS = (WeakKeyDictionary() for _ in range(3))


class SeedTailRejected(ValueError):
    def __init__(self, reason, *, stage, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.partial, self.capture_errors = stage, partial, tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class SeedTailRecord:
    law: str
    parent_trial_identity: str
    dyna_record: previous.ContinuationRecord
    original_record: leases.LeaseRecord
    before_graph_identity: str | None
    after_graph_identity: str | None
    work: tuple
    succeeded: bool
    source_error_present: bool
    secondary_error_stages: tuple
    parameter_field: str = "_run_sim"
    parameter_value: bool = False
    phase_handler_admitted: bool = False
    biological_cases: int = 0


class SeedTailClaim:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use seed_tail from the actual closed dyna claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live SEED-tail claims cannot be serialized")

    @property
    def parameters(self):
        return _active(self).p

    def check(self):
        _active(self)

    @property
    def record(self):
        context = _context(self)
        if context.active or context.record is None:
            raise SeedTailRejected("No complete SEED-tail record", stage="record", partial=context)
        value = context.record.value
        if value is not context.record_value or context.record.identity != _digest(
            record_document(value)
        ):
            raise SeedTailRejected("SEED-tail record changed", stage="record", partial=context)
        return value


def _digest(value):
    return previous._digest(value)


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact accepted dyna continuation producer required")
    plan = previous.source_plan()
    path = prefix.parameters.inherited.tissue.aliases.NATIVE / "betse/science/phase/phasecls.py"
    if hashlib.sha256(path.read_bytes()).hexdigest() != PHASE_SHA256:
        raise ValueError("Exact original SimPhase SEED-tail source required")
    cls = prefix.parameters.inherited._class(ast.parse(path.read_bytes()), "SimPhase")
    method = prefix.parameters.inherited._method
    kludge = method(cls, "_init_kludge").body[1:]
    if [ast.unparse(n) for n in kludge] != [
        "self.sim.dyna = self.dyna",
        "self.p._run_sim = self.kind is SimPhaseKind.SIM",
        "self._init_kludge_time()",
    ]:
        raise ValueError("Original phase tail order changed")
    time = method(cls, "_init_kludge_time").body[1]
    if ast.unparse(time) != "if self.kind is SimPhaseKind.SEED:\n    return":
        raise ValueError("Original SEED time early return changed")
    export = method(cls, "__init__").body[-1]
    if (
        ast.unparse(export.test) != "kind is SimPhaseKind.SEED"
        or ast.unparse(export.body[0]) != "self.export_dirname = p.init_export_dirname"
    ):
        raise ValueError("Original SEED export association changed")
    return dict(
        law=SEED_TAIL_LAW,
        predecessor=PREVIOUS_SHA256,
        native_pins=plan["native_pins"],
        phase_source=dict(path=str(path), sha256=PHASE_SHA256),
        parameter_transition="absent _run_sim -> exact bool False appended once",
        kludge_ast=_digest(ast.dump(ast.Module(body=kludge, type_ignores=[]))),
        seed_time_return_ast=_digest(ast.dump(time)),
        seed_export_ast=_digest(ast.dump(export.body[0])),
        no_native_execution=True,
        no_temporal_stores_or_directories=True,
        phase_handler_or_INIT_admitted=False,
    )


def _parent_refs(parent):
    return tuple(
        getattr(parent, n)
        for n in (
            "p",
            "config",
            "trial",
            "graph",
            "authority",
            "birth",
            "capture_view",
            "runtime_types",
            "runtime_files",
            "runtime_namespaces",
            "runtime_classes",
            "bindings",
            "native_bindings",
            "request",
            "parent",
            "stable",
            "stable_names",
            "before_names",
            "owner",
            "guard",
        )
    )


def _field_graph(context):
    return prefix.graphs.capture(
        {n: vars(context.p)[n] for n in context.before_names},
        yaml_base=context.parent.birth.source.yaml,
        runtime_types=context.parent.runtime_types,
    )


def _full_graph(context):
    return prefix._capture(context.parent.capture_view)


def _source(context):
    dyna, base, parent = context.dyna_context, context.base_context, context.parent
    if (
        previous._ISSUED.get(context.dyna_claim) is not dyna
        or leases._ISSUED.get(context.original_lease) is not base
        or previous._CONSUMED.get(context.original_lease) is not dyna
        or previous._OWNERS.get(context.owner) is not dyna
        or dyna.claim is not context.dyna_claim
        or dyna.lease is not context.original_lease
        or dyna.source is not base
        or dyna.owner is not context.owner
        or dyna.parent is not parent
        or dyna.p is not context.p
        or dyna.active is not False
        or dyna.guard.active is not False
        or dyna.invalid is not context.retired
        or dyna.guard.invalid is not context.retired
        or dyna.retired is not context.retired
        or dyna.source_error is not None
        or dyna.capture_errors
        or dyna.closed_check_active
        or context.dyna_claim.record is not context.dyna_record
        or context.original_lease.record is not context.original_record
        or dyna.original_record is not context.original_record
        or base.parent is not parent
        or base.owner is not context.owner
        or base.active is not False
        or base.invalid
        or base.guard.active is not False
        or base.guard.invalid
        or base.source_error is not None
        or base.capture_errors
        or parent.invalid is not context.retired
        or parent.active
        or parent.guard.invalid
        or parameters._ISSUED.get(context.owner) is not parent
        or leases._CONSTRUCTED.get(context.owner) is not True
        or any(a is not b for a, b in zip(_parent_refs(parent), context.parent_refs, strict=True))
        or parent.trial.identity != context.parent_trial_identity
        or _digest(parameters.trial_record(parent.trial)) != context.parent_trial_identity
        or _digest(parent.graph[1]) != context.parent_graph_identity
    ):
        raise ValueError("Original dyna/Lease/owner/p/retirement association changed")
    # Historical Lease metadata remains current; this checks no pre-mutation p graph.
    previous._source(dyna)
    leases._associations(base)
    previous._source_record(base)
    prefix.parameters.inherited._same(previous._bindings(), dyna.bindings)
    prefix.parameters.inherited._same(leases._bindings(), base.bindings)
    prefix.parameters.inherited._same(parameters._bindings(), parent.bindings)
    prefix.parameters.inherited._same(parameters._native_bindings(parent), parent.native_bindings)
    parameters._loaded(parent)
    parameters.paths._computed(parent.parent)
    kinds, files, namespaces = prefix._runtime_types(parent.capture_view)
    if kinds != parent.runtime_types or files != parent.runtime_files:
        raise ValueError("SEED-tail unowned runtime introduced")
    prefix.parameters.inherited._same(namespaces, parent.runtime_namespaces)
    prefix.parameters.inherited._same(prefix._class_bindings(kinds), parent.runtime_classes)
    caches = prefix.parameters.inherited.tissue.core.caches
    caches.validate(parent.trial.cache)
    if caches.snapshot(parent.graph[1]).identity != parent.trial.cache.identity:
        raise ValueError("Historical parameter evidence changed")
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("SEED-tail source regime changed")


def _state(context, *, complete):
    fields = vars(context.p)
    keys = tuple(fields)
    if keys != context.before_names and keys != (*context.before_names, "_run_sim"):
        raise ValueError("SEED-tail changed parameter layout outside _run_sim")
    if "_run_sim" in fields:
        if fields["_run_sim"] is not False:
            raise ValueError("SEED-tail requires exact bool False")
    elif complete:
        raise ValueError("Original SEED _run_sim assignment was not reached")
    prefix.parameters.inherited._same_graph(_field_graph(context), context.before_graph)


def _stacks(context):
    return (
        (_ACTIVE, context),
        (previous._ACTIVE, context),
        (leases._ACTIVE, context),
        (parameters._ACTIVE, context),
        (parameters.paths._ACTIVE, context.guard),
    )


def _poison(context):
    context.invalid = context.guard.invalid = True
    context.parent.invalid = True


def _reserve(dyna_claim, original_lease):
    if type(dyna_claim) is not previous.DynaConstructionClaim or dyna_claim not in previous._ISSUED:
        raise SeedTailRejected("Actual issued closed dyna claim required", stage="dyna_claim")
    dyna = previous._ISSUED[dyna_claim]
    if dyna.active or original_lease is not dyna.lease:
        raise SeedTailRejected("Exact closed dyna/original Lease required", stage="original_lease")
    if not _LOCK.acquire(blocking=False):
        raise SeedTailRejected("SEED-tail reservation busy", stage="reservation")
    try:
        if _ACTIVE:
            _poison(_ACTIVE[-1])
            raise SeedTailRejected(
                "Reentrant SEED-tail refused", stage="conflict", partial=_ACTIVE[-1]
            )
        if dyna_claim in _CONSUMED or dyna.owner in _OWNERS:
            raise SeedTailRejected("SEED-tail attempt consumed", stage="consumed")
        context = SimpleNamespace(
            dyna_claim=dyna_claim,
            original_lease=original_lease,
            dyna_context=dyna,
            base_context=dyna.source,
            owner=dyna.owner,
            parent=dyna.parent,
            p=dyna.p,
            dyna_record=dyna_claim.record,
            original_record=original_lease.record,
            thread=get_ident(),
            active=True,
            invalid=False,
            retired=False,
            registered=False,
            stage="prevalidation",
            work=[],
            source_error=None,
            capture_errors=(),
            before_graph=None,
            after_graph=None,
            partial_graph=None,
            record=None,
            record_value=None,
            validating=False,
            validations=[],
            guard=SimpleNamespace(
                thread=get_ident(),
                active=True,
                invalid=False,
                directory_depth=0,
                directory_calls=0,
                directory_targets=(),
                filesystem=[],
                audit_ready=False,
            ),
        )
        claim = object.__new__(SeedTailClaim)
        context.claim = claim
        _CONSUMED[dyna_claim] = _OWNERS[dyna.owner] = context
        _ISSUED[claim] = context
        _ACTIVE.append(context)
        return context, claim
    finally:
        _LOCK.release()


def _enter(context):
    context.bindings = _bindings()
    context.source_identity = _digest(source_plan())
    context.work.append(("dyna_current_verification", "attempted"))
    record = previous.validate_closed(context.dyna_claim, original_lease=context.original_lease)
    if record is not context.dyna_record or record.succeeded is not True:
        raise ValueError("Actual successful original dyna closure required")
    context.work.append(("dyna_current_verification", "completed"))
    if "_run_sim" in vars(context.p):
        raise ValueError("SEED-tail _run_sim must be genuinely absent")
    context.before_names = tuple(vars(context.p))
    context.parent_refs = _parent_refs(context.parent)
    context.parent_trial_identity = context.parent.trial.identity
    context.parent_graph_identity = _digest(context.parent.graph[1])
    context.before_graph = _field_graph(context)
    if any(value is context.p for value in context.before_graph[0]):
        raise ValueError("SEED-tail exposed Parameters back-reference graph unsupported")
    context.stage = "registration"
    with leases._registry(context.owner):
        if previous._ACTIVE or leases._ACTIVE or parameters._ACTIVE or parameters.paths._ACTIVE:
            leases._busy(context.owner, "seed_tail_conflict")
        for stack, value in _stacks(context)[1:]:
            stack.append(value)
        context.registered = True
        parameters.paths._install_audit(context.guard)
        _check(context, complete=False)
        context.dyna_context.retired = True
        context.dyna_context.invalid = context.dyna_context.guard.invalid = True
        context.parent.invalid = context.retired = True
        context.work.append(("old_authority_retirement", "completed"))
    context.stage = "body"
    _check(context, complete=False)


def _check(context, *, complete):
    if (
        context.invalid
        or context.guard.invalid
        or context.thread != get_ident()
        or context.active is not context.guard.active
        or not context.guard.audit_ready
        or _ISSUED.get(context.claim) is not context
        or _CONSUMED.get(context.dyna_claim) is not context
        or _OWNERS.get(context.owner) is not context
    ):
        raise SeedTailRejected(
            "Closed/poisoned/foreign SEED-tail claim", stage="claim_state", partial=context
        )
    if context.active and any(
        not stack or stack[-1] is not value for stack, value in _stacks(context)
    ):
        raise ValueError("SEED-tail shared activity changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)
    _source(context)
    _state(context, complete=complete)


def _context(claim):
    if type(claim) is not SeedTailClaim or claim not in _ISSUED:
        raise SeedTailRejected("Actual issued SEED-tail claim required", stage="claim")
    return _ISSUED[claim]


def _active(claim):
    context = _context(claim)
    if not context.active:
        raise SeedTailRejected("SEED-tail claim is closed", stage="active")
    try:
        _check(context, complete=False)
        return context
    except BaseException:
        _poison(context)
        raise


def record_document(value):
    original = value.original_record
    return dict(
        law=value.law,
        parent=value.parent_trial_identity,
        dyna_record=previous.record_document(value.dyna_record),
        original_record=dict(
            law=original.law,
            parent=original.parent_trial_identity,
            purpose=original.purpose,
            work=original.work,
            retired=original.retired,
            succeeded=original.succeeded,
            source_error_present=original.source_error_present,
            secondary_error_stages=original.secondary_error_stages,
            biological_cases=original.biological_cases,
        ),
        before=value.before_graph_identity,
        after=value.after_graph_identity,
        work=value.work,
        succeeded=value.succeeded,
        source_error_present=value.source_error_present,
        secondary_error_stages=value.secondary_error_stages,
        parameter_field=value.parameter_field,
        parameter_value=value.parameter_value,
        phase_handler_admitted=value.phase_handler_admitted,
        biological_cases=value.biological_cases,
    )


def _finish(context):
    try:
        context.stage = "exit_validation"
        if not context.retired:
            raise ValueError("SEED-tail never acquired mutation authority")
        _check(context, complete=True)
        context.after_graph = _full_graph(context)
        context.work.append(("seed_flag_and_remaining_graph_verification", "completed"))
    except BaseException as error:
        context.capture_errors += (("exit_validation", error),)
    try:
        context.partial_graph = _full_graph(context)
    except BaseException as error:
        context.capture_errors += (("partial_capture", error),)
    try:
        with leases._registry(context.owner):
            if context.registered:
                for stack, value in reversed(_stacks(context)[1:]):
                    if not stack or stack[-1] is not value:
                        raise ValueError("SEED-tail registry changed at closure")
                    stack.pop()
    except BaseException as error:
        context.capture_errors += (("claim_release", error),)
    if _ACTIVE and _ACTIVE[-1] is context:
        _ACTIVE.pop()
    else:
        context.capture_errors += (("own_release", ValueError("SEED-tail reservation changed")),)
    context.active = context.guard.active = False
    failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
    if failed:
        _poison(context)
    try:
        value = SeedTailRecord(
            SEED_TAIL_LAW,
            getattr(
                context, "parent_trial_identity", context.original_record.parent_trial_identity
            ),
            context.dyna_record,
            context.original_record,
            None if context.before_graph is None else _digest(context.before_graph[1]),
            None if context.after_graph is None else _digest(context.after_graph[1]),
            tuple(context.work),
            not failed,
            context.source_error is not None,
            tuple(stage for stage, _ in context.capture_errors),
        )
        context.record = SimpleNamespace(value=value, identity=_digest(record_document(value)))
        context.record_value = value
    except BaseException as error:
        context.capture_errors += (("closure_record", error),)
        _poison(context)
        failed = True
    return failed


@contextmanager
def seed_tail(dyna_claim, *, original_lease, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(name) != "1"
        for name in (RELEASE, previous.RELEASE, leases.RELEASE, parameters.RELEASE)
    ):
        raise SeedTailRejected("Actual SEED-tail mutation remains held", stage="release")
    if type(law_id) is not str or law_id != SEED_TAIL_LAW:
        raise SeedTailRejected("Explicit SEED-tail mutation law required", stage="law")
    context, claim = _reserve(dyna_claim, original_lease)
    try:
        _enter(context)
        yield claim
    except BaseException as primary:
        context.source_error = primary
        raise
    finally:
        try:
            failed = _finish(context)
        except BaseException as error:
            context.capture_errors += (("claim_completion", error),)
            context.active = context.guard.active = False
            _poison(context)
            failed = True
        if context.source_error is not None:
            try:
                context.source_error.seed_tail_claim = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            cause = context.capture_errors[0][1] if context.capture_errors else None
            raise SeedTailRejected(
                "SEED-tail issued no success",
                stage=context.stage,
                partial=context,
                capture_errors=context.capture_errors,
            ) from cause


def validate_closed(claim, *, dyna_claim, original_lease):
    """Authenticate the new state without any pre-mutation state validator."""
    context = _context(claim)
    if dyna_claim is not context.dyna_claim or original_lease is not context.original_lease:
        raise SeedTailRejected("Exact SEED-tail ancestry required", stage="closed_association")
    if context.active or context.validating or _ACTIVE:
        raise SeedTailRejected("SEED-tail closed validation overlap", stage="closed_state")
    context.validating = True
    attempt = SimpleNamespace(
        source_error=None,
        capture_errors=(),
        succeeded=False,
        owner=context.owner,
        parent=context.parent,
        active=True,
        invalid=False,
        work=[],
        stage="closed_validation",
        guard=SimpleNamespace(
            thread=get_ident(),
            active=True,
            invalid=False,
            directory_depth=0,
            directory_calls=0,
            directory_targets=(),
            filesystem=[],
            audit_ready=False,
        ),
    )
    context.validations.append(attempt)
    registered = False
    try:
        with leases._registry(context.owner):
            if previous._ACTIVE or leases._ACTIVE or parameters._ACTIVE or parameters.paths._ACTIVE:
                leases._busy(context.owner, "seed_tail_validation_conflict")
            for stack, value in _stacks(attempt):
                stack.append(value)
            registered = True
        parameters.paths._install_audit(attempt.guard)
        # Only the separate metadata guard is active; no constructor or source
        # state is reopened and no pre-mutation state validator is called.
        _check(context, complete=True)
        value = claim.record
        if (
            value.law != SEED_TAIL_LAW
            or value.succeeded is not True
            or value.dyna_record is not context.dyna_record
            or value.original_record is not context.original_record
            or not context.retired
            or value.source_error_present
            or value.secondary_error_stages
            or value.work != tuple(context.work)
            or value.parameter_field != "_run_sim"
            or value.parameter_value is not False
            or value.phase_handler_admitted is not False
            or type(value.biological_cases) is not int
            or value.biological_cases != 0
            or value.before_graph_identity != _digest(context.before_graph[1])
            or value.after_graph_identity != _digest(context.after_graph[1])
        ):
            raise ValueError("Successful SEED-tail closure required")
        prefix.parameters.inherited._same_graph(_full_graph(context), context.after_graph)
        if attempt.invalid or attempt.guard.invalid:
            raise ValueError("SEED-tail closed inspection poisoned")
        attempt.succeeded = True
        return value
    except BaseException as error:
        attempt.source_error = error
        _poison(context)
        try:
            error.seed_tail_validation = attempt
        except BaseException as capture:
            attempt.capture_errors += (("exception_evidence", capture),)
        raise
    finally:
        try:
            with leases._registry(context.owner):
                if registered:
                    for stack, value in reversed(_stacks(attempt)):
                        if not stack or stack[-1] is not value:
                            raise ValueError("SEED-tail validation registry changed")
                        stack.pop()
        except BaseException as error:
            attempt.capture_errors += (("claim_release", error),)
            attempt.succeeded = False
            _poison(context)
        finally:
            attempt.active = attempt.guard.active = False
            context.validating = False
        if attempt.source_error is None and attempt.capture_errors:
            raise SeedTailRejected(
                "SEED-tail inspection issued no authority",
                stage="closed_release",
                partial=attempt,
                capture_errors=attempt.capture_errors,
            ) from attempt.capture_errors[0][1]


def _bindings():
    functions = (
        _digest,
        source_plan,
        _parent_refs,
        _field_graph,
        _full_graph,
        _source,
        _state,
        _stacks,
        _poison,
        _reserve,
        _enter,
        _check,
        _context,
        _active,
        record_document,
        _finish,
        seed_tail,
        seed_tail.__wrapped__,
        validate_closed,
        _bindings,
        SeedTailClaim.__init__,
        SeedTailClaim.__reduce_ex__,
        SeedTailClaim.parameters.fget,
        SeedTailClaim.check,
        SeedTailClaim.record.fget,
    )
    return (
        (),
        (
            SEED_TAIL_LAW,
            PREVIOUS_SHA256,
            PHASE_SHA256,
            RELEASE,
            _LOCK,
            _ACTIVE,
            _ISSUED,
            _CONSUMED,
            _OWNERS,
            SeedTailClaim,
            SeedTailRecord,
            SeedTailRejected,
            get_ident,
            *previous._bindings()[1],
            *(
                atom
                for fn in functions
                for atom in prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )
