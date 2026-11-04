"""Exclusive same-p construction/advance claims; never native derivation.

Specialist interface: ``with construction(owner, law_id=LAW_ID, enabled=True)
 as lease: p = lease.parameters``. The caller retains its constructor work and
failures. Clean construction leaves the original owner unchanged; all failure,
mutation, runtime drift and overlap refuse without rearming a retired parent.
No callback is accepted, serialized, recreated or invoked by this module.
"""

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from threading import Lock, get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_subconfigurations as previous

LAW_ID = "betse_same_parameter_construction_lease@1"
PARENT_SHA256 = "3c0c6ba9b3e677acebe2d35f7d008eeca447165537d4870ec28884ff96f0e192"
RELEASE = "CELLS_NATIVE_PARAMETER_CONSTRUCTION_LEASE_RELEASED"
_MUTEX, _ACTIVE = Lock(), []
_ISSUED, _CONSTRUCTED = WeakKeyDictionary(), WeakKeyDictionary()


class ConstructionRejected(ValueError):
    def __init__(self, reason, *, stage, owner=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.owner, self.partial = stage, owner, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class LeaseRecord:
    law: str
    parent_trial_identity: str
    purpose: str
    work: tuple
    retired: bool
    succeeded: bool
    source_error_present: bool
    secondary_error_stages: tuple
    biological_cases: int = 0


class Lease:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the issued construction or numeric claim")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live construction claims cannot be serialized")

    @property
    def parameters(self):
        return _parent(self).p

    def check(self):
        _parent(self)

    @property
    def record(self):
        context = _context(self)
        if context.active:
            raise ConstructionRejected("No success record before claim closure", stage="active")
        if context.record is None:
            raise ConstructionRejected("Claim record is incomplete", stage="evidence")
        return context.record


def source_plan():
    if hashlib.sha256(Path(previous.__file__).read_bytes()).hexdigest() != PARENT_SHA256:
        raise ValueError("Exact repaired subconfiguration producer required")
    return dict(
        law=LAW_ID,
        predecessor_sha256=PARENT_SHA256,
        native_pins=previous.source_plan()["native_pins"],
        construction="read-only selected handler leaf; not SimPhase.dyna",
        runtime_refresh=False,
        native_release=False,
    )


def _event(context, kind, stage, status):
    context.work.append((len(context.work), kind, stage, status))


def _poison(context):
    context.invalid = True
    context.guard.invalid = True
    context.parent.invalid = True


def _busy(owner, stage):
    context = _ACTIVE[-1] if _ACTIVE else None
    if context is not None:
        _poison(context)
        _event(context, "conflict", stage, "refused")
    elif previous._ACTIVE:
        previous._ACTIVE[-1].invalid = True
    elif previous.paths._ACTIVE:
        previous.paths._ACTIVE[-1].invalid = True
    raise ConstructionRejected(
        "Another parameter claim is active", stage=stage, owner=owner, partial=context
    )


@contextmanager
def _registry(owner):
    # All three acquisitions are nonblocking. No registry/predecessor lock is
    # held during validation or caller work, avoiding lock inversion at hooks.
    acquired = []
    try:
        for lock in (_MUTEX, previous._LOCK, previous.paths._LOCK):
            if not lock.acquire(blocking=False):
                _busy(owner, "registry_busy")
            acquired.append(lock)
        yield
    finally:
        for lock in reversed(acquired):
            lock.release()


def _context(lease):
    if type(lease) is not Lease or lease not in _ISSUED:
        raise ConstructionRejected("Issued opaque claim required", stage="claim")
    return _ISSUED[lease]


def _associations(context):
    parent = context.parent
    current = (
        parent.p,
        parent.config,
        parent.trial,
        parent.graph,
        parent.authority,
        parent.birth,
        parent.capture_view,
    )
    if any(a is not b for a, b in zip(current, context.before, strict=True)):
        raise ValueError("Original parent/configuration/graph/trial association changed")
    if previous._ISSUED.get(context.owner) is not parent or parent.owner is not context.owner:
        raise ValueError("Original issued parent association changed")


def _check(context):
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or not context.guard.active
        or not context.guard.audit_ready
        or not _ACTIVE
        or _ACTIVE[-1] is not context
        or not previous._ACTIVE
        or previous._ACTIVE[-1] is not context
        or not previous.paths._ACTIVE
        or previous.paths._ACTIVE[-1] is not context.guard
    ):
        raise ConstructionRejected(
            "Closed, poisoned or foreign-thread claim", stage="claim_state", partial=context
        )
    previous.paths.prefix.parameters.inherited._same(_bindings(), context.bindings)
    _associations(context)
    _event(context, "producer_check", context.stage, "attempted")
    source_plan()
    _event(context, "producer_check", context.stage, "completed")


def _parent(lease):
    context = _context(lease)
    try:
        _check(context)
        if context.retired:
            raise ConstructionRejected(
                "Retired parent cannot be read as authority", stage="retired"
            )
        _event(context, "parent_validation", context.stage, "attempted")
        parent = previous._validate(context.owner)
        if parent is not context.parent:
            raise ValueError("Foreign parent validation result")
        _event(context, "parent_validation", context.stage, "completed")
        _check(context)
        return parent
    except BaseException:
        if context.active:
            _poison(context)
        raise


def retire(lease, parent):
    context = _context(lease)
    if context.purpose != "numeric_advance" or context.retired:
        _poison(context)
        raise ConstructionRejected("Only the numeric advance may retire once", stage="retirement")
    context.stage = "retirement"
    if _parent(lease) is not parent:
        _poison(context)
        raise ConstructionRejected("Foreign retirement parent", stage="retirement")
    with _registry(context.owner):
        if (
            context.invalid
            or context.guard.invalid
            or not context.active
            or not _ACTIVE
            or _ACTIVE[-1] is not context
            or previous._ISSUED.get(context.owner) is not parent
            or context.parent is not parent
            or parent.invalid
        ):
            _poison(context)
            raise ConstructionRejected("Retirement epoch changed", stage="retirement")
        parent.invalid = True
        context.retired = True
        _event(context, "parent_retirement", context.stage, "completed")
    return context.guard


def _begin(owner, purpose):
    if type(purpose) is not str or purpose not in {"construction", "inspection", "numeric_advance"}:
        raise ConstructionRejected("Unknown claim purpose", stage="purpose", owner=owner)
    if type(owner) is not previous.SubconfigurationsOwner or owner not in previous._ISSUED:
        previous._validate(owner)  # Preserve the original unsupported-owner refusal.
        raise AssertionError("Unissued owner validator returned")
    parent = previous._ISSUED[owner]
    guard = SimpleNamespace(
        thread=get_ident(),
        active=True,
        invalid=False,
        directory_depth=0,
        directory_calls=0,
        directory_targets=(),
        filesystem=[],
        audit_ready=False,
    )
    context = SimpleNamespace(
        owner=owner,
        parent=parent,
        purpose=purpose,
        thread=get_ident(),
        active=True,
        invalid=False,
        retired=False,
        stage="entry",
        work=[],
        source_error=None,
        capture_errors=(),
        guard=guard,
        record=None,
        before=(
            parent.p,
            parent.config,
            parent.trial,
            parent.graph,
            parent.authority,
            parent.birth,
            parent.capture_view,
        ),
    )
    lease = object.__new__(Lease)
    with _registry(owner):
        if _ACTIVE or previous._ACTIVE or previous.paths._ACTIVE:
            _busy(owner, "claim_conflict")
        if purpose == "construction" and owner in _CONSTRUCTED:
            raise ConstructionRejected(
                "Construction attempt consumed", stage="consumed", owner=owner
            )
        _ACTIVE.append(context)
        previous._ACTIVE.append(context)
        previous.paths._ACTIVE.append(guard)
        _ISSUED[lease] = context
        if purpose == "construction":
            _CONSTRUCTED[owner] = True
    return context, lease


def _finish(context, lease):
    try:
        context.stage = "exit"
        _check(context)
        if context.retired:
            if not context.parent.invalid:
                raise ValueError("Retired parent was rearmed")
        else:
            _parent(lease)
    except BaseException as error:
        context.capture_errors += (("exit_validation", error),)
    try:
        with _registry(context.owner):
            if (
                not _ACTIVE
                or _ACTIVE[-1] is not context
                or not previous._ACTIVE
                or previous._ACTIVE[-1] is not context
                or not previous.paths._ACTIVE
                or previous.paths._ACTIVE[-1] is not context.guard
            ):
                raise ValueError("Claim registry changed before release")
            previous.paths._ACTIVE.pop()
            previous._ACTIVE.pop()
            _ACTIVE.pop()
    except BaseException as error:
        context.capture_errors += (("claim_release", error),)
    failed = context.source_error is not None or context.invalid or bool(context.capture_errors)
    context.active = context.guard.active = False
    if failed:
        _poison(context)
    context.record = LeaseRecord(
        LAW_ID,
        context.before[2].identity,
        context.purpose,
        tuple(context.work),
        context.retired,
        not failed,
        context.source_error is not None,
        tuple(stage for stage, _ in context.capture_errors),
    )
    return failed


@contextmanager
def _claim(owner, purpose):
    context, lease = _begin(owner, purpose)
    try:
        context.bindings = _bindings()
        previous.paths._install_audit(context.guard)
        _parent(lease)
        context.stage = "body"
        yield lease
    except BaseException as error:
        context.source_error = error
        raise
    finally:
        try:
            failed = _finish(context, lease)
        except BaseException as error:
            context.capture_errors += (("claim_completion", error),)
            context.active = context.guard.active = False
            _poison(context)
            failed = True
        if context.source_error is not None:
            # Never replace an original constructor/numeric exception or cause.
            try:
                context.source_error.construction_lease = context
            except BaseException as error:
                context.capture_errors += (("exception_evidence", error),)
        elif failed:
            cause = context.capture_errors[0][1] if context.capture_errors else None
            raise ConstructionRejected(
                "Construction/advance claim issued no success",
                stage=context.stage,
                owner=owner,
                partial=context,
                capture_errors=context.capture_errors,
            ) from cause


@contextmanager
def construction(owner, *, law_id, enabled=False):
    if (
        enabled is not True
        or os.environ.get(RELEASE) != "1"
        or os.environ.get(previous.RELEASE) != "1"
    ):
        raise ConstructionRejected(
            "Actual construction lease remains held", stage="release", owner=owner
        )
    if type(law_id) is not str or law_id != LAW_ID:
        raise ConstructionRejected(
            "Explicit construction lease law required", stage="law", owner=owner
        )
    with _claim(owner, "construction") as lease:
        yield lease


@contextmanager
def inspection(owner):
    """Metadata request association only; no constructor or advance permission."""
    with _claim(owner, "inspection") as lease:
        yield lease


@contextmanager
def _advance(owner):
    with _claim(owner, "numeric_advance") as lease:
        yield lease


def _bindings():
    functions = (
        source_plan,
        _event,
        _poison,
        _busy,
        _registry,
        _registry.__wrapped__,
        _context,
        _associations,
        _check,
        _parent,
        retire,
        _begin,
        _finish,
        _claim,
        _claim.__wrapped__,
        construction,
        construction.__wrapped__,
        inspection,
        inspection.__wrapped__,
        _advance,
        _advance.__wrapped__,
        _bindings,
        Lease.__init__,
        Lease.__reduce_ex__,
        Lease.parameters.fget,
        Lease.check,
        Lease.record.fget,
    )
    return (
        (),
        (
            LAW_ID,
            PARENT_SHA256,
            RELEASE,
            _MUTEX,
            _ACTIVE,
            _ISSUED,
            _CONSTRUCTED,
            Lease,
            LeaseRecord,
            ConstructionRejected,
            get_ident,
            previous._LOCK,
            previous._ACTIVE,
            previous.paths._LOCK,
            previous.paths._ACTIVE,
            *(
                atom
                for fn in functions
                for atom in previous.paths.prefix.parameters.inherited.tissue.aliases._atoms(fn)
            ),
        ),
    )
