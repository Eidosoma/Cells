"""One read-only dyna-constructor claim from an actual closed source Lease.

This module executes no constructor or callback. The phase/dyna caller must
validate its cache-to-original-Lease ancestry and count its own source work.
A successful record certifies parameter-claim closure, never TissueHandler,
phase, INIT, physical or checkpoint admission.
"""

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_construction_lease as previous

PHASE_DYNA_CONSTRUCTION_LAW = "betse_same_parameter_phase_dyna_construction_continuation@1"
PREVIOUS_SHA256 = "5e942391adc112382e6bc38dcf252f5f615d22ef2f98dbdaa6c00484cdb89ff4"
RELEASE = "CELLS_NATIVE_PARAMETER_DYNA_CONSTRUCTION_RELEASED"
parameters = previous.previous
_LOCK, _ACTIVE = Lock(), []
_ISSUED, _CONSUMED, _OWNERS = (WeakKeyDictionary() for _ in range(3))


class ContinuationRejected(ValueError):
    def __init__(self, reason, *, stage, lease=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.lease, self.partial = stage, lease, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class ContinuationRecord:
    law: str
    parent_trial_identity: str
    original_record: previous.LeaseRecord
    work: tuple
    succeeded: bool
    source_error_present: bool
    secondary_error_stages: tuple
    parameter_advanced: bool = False
    tissue_handler_admitted: bool = False
    biological_cases: int = 0


class DynaConstructionClaim:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use continuation from the actual closed Lease")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live dyna constructor claims cannot be serialized")

    @property
    def parameters(self):
        return _checked(self).p

    def check(self):
        _checked(self)

    @property
    def record(self):
        context = _context(self)
        if context.active or context.record is None:
            raise ContinuationRejected(
                "No continuation record before closure", stage="active", lease=context.lease
            )
        if context.record.value is not context.record_value or context.record.identity != _digest(
            record_document(context.record.value)
        ):
            raise ContinuationRejected(
                "Continuation closure record changed",
                stage="record",
                lease=context.lease,
                partial=context,
            )
        return context.record.value


def _digest(value):
    return parameters._digest(value)


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PREVIOUS_SHA256:
        raise ValueError("Exact accepted closed-Lease producer required")
    parent = previous.source_plan()
    return dict(
        law=PHASE_DYNA_CONSTRUCTION_LAW,
        predecessor=PREVIOUS_SHA256,
        parameter_producer=previous.PARENT_SHA256,
        native_pins=parent["native_pins"],
        input="actual issued successfully closed construction Lease only",
        successor="one read-only dyna constructor-continuation claim",
        closed_validation=(
            "validate_closed(claim, original_lease=actual_original_lease); metadata inspection "
            "only, never reopens either constructor claim"
        ),
        source_constructor_or_numeric_execution=False,
        construction_marker_rearmed=False,
        successful_claim_is_TissueHandler_or_phase_or_INIT_admission=False,
        caller_requires=(
            "actual cache-to-original-Lease ancestry, source/body attempts and failures"
        ),
    )


def _source_record(source):
    record = source.record
    if (
        type(record) is not previous.LeaseRecord
        or record.law != previous.LAW_ID
        or record.purpose != "construction"
        or record.parent_trial_identity != source.before[2].identity
        or record.work != tuple(source.work)
        or record.succeeded is not True
        or record.retired is not False
        or record.source_error_present is not False
        or record.secondary_error_stages != ()
        or type(record.biological_cases) is not int
        or record.biological_cases != 0
    ):
        raise ValueError("Original successful closed construction record required")
    return record


def _source(context):
    source = previous._context(context.lease)
    if (
        source is not context.source
        or source.owner is not context.owner
        or source.parent is not context.parent
        or source.record is not context.original_record
        or context.lease.record is not context.original_record
        or source.purpose != "construction"
        or source.retired is not False
        or source.active is not False
        or source.invalid
        or source.guard is not context.source_guard
        or source.guard.active is not False
        or source.guard.invalid
        or not source.guard.audit_ready
        or source.source_error is not None
        or source.capture_errors
        or source.thread != context.thread
        or source.guard.thread != context.thread
        or previous._CONSTRUCTED.get(context.owner) is not True
        or parameters._ISSUED.get(context.owner) is not context.parent
        or context.parent.p is not context.p
        or source.before is not context.source_before
        or source.work is not context.source_work
        or source.bindings is not context.source_bindings
    ):
        raise ValueError("Actual closed Lease/owner/p/marker/record association changed")
    _source_record(source)
    parameters.paths.prefix.parameters.inherited._same(previous._bindings(), source.bindings)
    previous._associations(source)
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("Dyna continuation producer changed")
    return source


def _stacks(context):
    return (
        (_ACTIVE, context),
        (previous._ACTIVE, context),
        (parameters._ACTIVE, context),
        (parameters.paths._ACTIVE, context.guard),
    )


def _poison(context):
    context.invalid = context.guard.invalid = True
    context.parent.invalid = True


def _event(context, kind, status):
    context.work.append((len(context.work), kind, context.stage, status))


def _reserve(lease):
    if type(lease) is not previous.Lease or lease not in previous._ISSUED:
        raise ContinuationRejected(
            "Actual issued closed construction Lease required", stage="lease", lease=lease
        )
    source = previous._ISSUED[lease]
    if (
        source.active is not False
        or source.purpose != "construction"
        or type(source.record) is not previous.LeaseRecord
    ):
        raise ContinuationRejected(
            "Construction Lease is not closed", stage="predecessor", lease=lease
        )
    if not _LOCK.acquire(blocking=False):
        if _ACTIVE:
            _poison(_ACTIVE[-1])
        raise ContinuationRejected(
            "Continuation reservation is busy", stage="reservation", lease=lease
        )
    try:
        if _ACTIVE:
            _poison(_ACTIVE[-1])
            raise ContinuationRejected(
                "Reentrant dyna continuation refused",
                stage="conflict",
                lease=lease,
                partial=_ACTIVE[-1],
            )
        if lease in _CONSUMED or source.owner in _OWNERS:
            raise ContinuationRejected(
                "Dyna successor attempt consumed", stage="consumed", lease=lease
            )
        context = SimpleNamespace(
            lease=lease,
            source=source,
            owner=source.owner,
            parent=source.parent,
            p=source.parent.p,
            original_record=source.record,
            source_guard=source.guard,
            source_before=source.before,
            source_work=source.work,
            source_bindings=source.bindings,
            thread=get_ident(),
            active=True,
            invalid=False,
            retired=False,
            purpose="dyna_constructor_continuation",
            stage="reservation",
            work=[],
            source_error=None,
            capture_errors=(),
            shared_registered=False,
            record=None,
            record_value=None,
            closed_check_active=False,
            closed_checks=[],
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
        claim = object.__new__(DynaConstructionClaim)
        context.claim = claim
        _CONSUMED[lease] = _OWNERS[source.owner] = context
        _ISSUED[claim] = context
        _ACTIVE.append(context)
        return context, claim
    finally:
        _LOCK.release()


def _enter(context):
    context.bindings = _bindings()
    context.source_identity = _digest(source_plan())
    context.stage = "registration"
    with previous._registry(context.owner):
        if previous._ACTIVE or parameters._ACTIVE or parameters.paths._ACTIVE:
            previous._busy(context.owner, "dyna_continuation_conflict")
        for stack, value in _stacks(context)[1:]:
            stack.append(value)
        context.shared_registered = True
    parameters.paths._install_audit(context.guard)
    context.stage = "predecessor_validation"
    _check(context)
    context.stage = "body"


def _check(context):
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or not context.guard.active
        or not context.guard.audit_ready
        or not context.shared_registered
        or _ISSUED.get(context.claim) is not context
        or _CONSUMED.get(context.lease) is not context
        or _OWNERS.get(context.owner) is not context
        or any(not stack or stack[-1] is not value for stack, value in _stacks(context))
    ):
        raise ContinuationRejected(
            "Closed/poisoned/foreign dyna claim refused",
            stage="claim_state",
            lease=context.lease,
            partial=context,
        )
    parameters.paths.prefix.parameters.inherited._same(_bindings(), context.bindings)
    _source(context)
    _event(context, "parent_validation", "attempted")
    if parameters._validate(context.owner) is not context.parent:
        raise ValueError("Foreign same-parameter validation result")
    _event(context, "parent_validation", "completed")
    _source(context)
    if context.invalid or context.guard.invalid or context.parent.invalid:
        raise ValueError("Dyna parent changed during validation")


def _context(claim):
    if type(claim) is not DynaConstructionClaim or claim not in _ISSUED:
        raise ContinuationRejected("Issued dyna continuation claim required", stage="claim")
    return _ISSUED[claim]


def _checked(claim):
    context = _context(claim)
    try:
        _check(context)
        return context
    except BaseException:
        if context.active:
            _poison(context)
        raise


def _closed(context):
    if (
        context.active is not False
        or context.invalid
        or context.guard.active is not False
        or context.guard.invalid
        or context.thread != get_ident()
        or context.source_error is not None
        or context.capture_errors
        or _ISSUED.get(context.claim) is not context
        or _CONSUMED.get(context.lease) is not context
        or _OWNERS.get(context.owner) is not context
    ):
        raise ContinuationRejected(
            "Successful current closed dyna claim required",
            stage="closed_state",
            lease=context.lease,
            partial=context,
        )
    record = context.claim.record
    if (
        type(record) is not ContinuationRecord
        or record.original_record is not context.original_record
        or record.law != PHASE_DYNA_CONSTRUCTION_LAW
        or record.parent_trial_identity != context.original_record.parent_trial_identity
        or record.work != tuple(context.work)
        or record.succeeded is not True
        or record.source_error_present is not False
        or record.secondary_error_stages != ()
        or record.parameter_advanced is not False
        or record.tissue_handler_admitted is not False
        or type(record.biological_cases) is not int
        or record.biological_cases != 0
    ):
        raise ValueError("Original successful dyna closure record changed")
    parameters.paths.prefix.parameters.inherited._same(_bindings(), context.bindings)
    _source(context)
    return record


def validate_closed(claim, *, original_lease):
    """Revalidate current same-p authority; return the exact historical record.

    The caller supplies its retained cache-to-original-Lease identity. A fresh
    existing read-only inspection protects metadata validation; neither old nor
    successor construction is reopened. This issues no constructor permission
    or p object. Validation attempts and their inspection leases/records/errors
    remain in the issued context's ``closed_checks`` ledger. No native work is
    performed; actual child construction still requires the original active
    continuation and its own separately retained work and result.
    """
    context = _context(claim)
    if original_lease is not context.lease:
        raise ContinuationRejected(
            "Exact retained original construction Lease required",
            stage="closed_association",
            lease=original_lease,
        )
    if not _LOCK.acquire(blocking=False):
        raise ContinuationRejected("Closed validation reservation busy", stage="closed_busy")
    try:
        if context.closed_check_active or _ACTIVE:
            _poison(context)
            if _ACTIVE:
                _poison(_ACTIVE[-1])
            raise ContinuationRejected("Overlapping closed validation refused", stage="closed_busy")
        context.closed_check_active = True
        attempt = SimpleNamespace(
            lease=None, record=None, partial=None, source_error=None, capture_errors=()
        )
        context.closed_checks.append(attempt)
    finally:
        _LOCK.release()
    try:
        record = _closed(context)
        with previous.inspection(context.owner) as audit:
            attempt.lease = audit
            if audit.parameters is not context.p:
                raise ValueError("Closed dyna parameter identity changed")
            if _closed(context) is not record:
                raise ValueError("Closed dyna record identity changed during validation")
        attempt.record = audit.record
        if (
            type(attempt.record) is not previous.LeaseRecord
            or attempt.record.purpose != "inspection"
            or attempt.record.succeeded is not True
            or attempt.record.retired is not False
            or attempt.record.source_error_present is not False
            or attempt.record.secondary_error_stages != ()
        ):
            raise ValueError("Closed dyna read-only inspection did not complete")
        if _closed(context) is not record:
            raise ValueError("Closed dyna record changed after inspection")
        return record
    except BaseException as error:
        attempt.source_error = error
        _poison(context)
        try:
            attempt.partial = getattr(error, "construction_lease", None)
            if attempt.lease is None and attempt.partial is not None:
                attempt.record = getattr(attempt.partial, "record", None)
        except BaseException as capture:
            attempt.capture_errors += (("inspection_partial", capture),)
        try:
            error.dyna_closed_validation = attempt
        except BaseException as capture:
            attempt.capture_errors += (("exception_evidence", capture),)
        raise
    finally:
        if attempt.lease is not None and attempt.record is None:
            try:
                attempt.record = attempt.lease.record
            except BaseException as error:
                attempt.capture_errors += (("inspection_record", error),)
        context.closed_check_active = False


def record_document(value):
    original = value.original_record
    return dict(
        law=value.law,
        parent=value.parent_trial_identity,
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
        work=value.work,
        succeeded=value.succeeded,
        source_error_present=value.source_error_present,
        secondary_error_stages=value.secondary_error_stages,
        parameter_advanced=value.parameter_advanced,
        tissue_handler_admitted=value.tissue_handler_admitted,
        biological_cases=value.biological_cases,
    )


def _finish(context):
    try:
        context.stage = "exit_validation"
        if context.shared_registered:
            _check(context)
        else:
            raise ValueError("Continuation never acquired shared activity protection")
    except BaseException as error:
        context.capture_errors += (("exit_validation", error),)
    try:
        with previous._registry(context.owner):
            for stack, value in reversed(_stacks(context)[1:]):
                if context.shared_registered:
                    if not stack or stack[-1] is not value:
                        context.capture_errors += (
                            ("claim_release", ValueError("Shared claim registry changed")),
                        )
                        if value in stack:
                            stack.remove(value)
                    else:
                        stack.pop()
    except BaseException as error:
        context.capture_errors += (("claim_release", error),)
    try:
        if not _ACTIVE or _ACTIVE[-1] is not context:
            raise ValueError("Own continuation activity changed")
        _ACTIVE.pop()
    except BaseException as error:
        context.capture_errors += (("own_release", error),)
    context.active = context.guard.active = False
    failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
    if failed:
        _poison(context)
    try:
        value = ContinuationRecord(
            PHASE_DYNA_CONSTRUCTION_LAW,
            context.original_record.parent_trial_identity,
            context.original_record,
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
def continuation(closed_lease, *, law_id, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(previous.RELEASE) != "1"
        or os.environ.get(parameters.RELEASE) != "1"
    ):
        raise ContinuationRejected(
            "Actual dyna construction continuation remains held",
            stage="release",
            lease=closed_lease,
        )
    if type(law_id) is not str or law_id != PHASE_DYNA_CONSTRUCTION_LAW:
        raise ContinuationRejected(
            "Explicit phase.dyna continuation law required", stage="law", lease=closed_lease
        )
    context, claim = _reserve(closed_lease)
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
                context.source_error.dyna_continuation = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            cause = context.capture_errors[0][1] if context.capture_errors else None
            raise ContinuationRejected(
                "Dyna continuation issued no success",
                stage=context.stage,
                lease=closed_lease,
                partial=context,
                capture_errors=context.capture_errors,
            ) from cause


def _bindings():
    functions = (
        _digest,
        source_plan,
        _source_record,
        _source,
        _stacks,
        _poison,
        _event,
        _reserve,
        _enter,
        _check,
        _context,
        _checked,
        _closed,
        validate_closed,
        record_document,
        _finish,
        continuation,
        continuation.__wrapped__,
        _bindings,
        DynaConstructionClaim.__init__,
        DynaConstructionClaim.__reduce_ex__,
        DynaConstructionClaim.parameters.fget,
        DynaConstructionClaim.check,
        DynaConstructionClaim.record.fget,
    )
    return (
        (),
        (
            PHASE_DYNA_CONSTRUCTION_LAW,
            PREVIOUS_SHA256,
            RELEASE,
            _LOCK,
            _ACTIVE,
            _ISSUED,
            _CONSUMED,
            _OWNERS,
            DynaConstructionClaim,
            ContinuationRecord,
            ContinuationRejected,
            get_ident,
            *previous._bindings()[1],
            *(
                atom
                for fn in functions
                for atom in parameters.paths.prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )
