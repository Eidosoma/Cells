"""One fresh world-ready parameter claim spanning phase birth through SEED.

This module creates no phase, Cells, simulator, cache, handler, RNG or callback.
Only a reviewed consumer's actual source chain can confer those authorities.
A closed claim records parameter preservation and the sole SEED flag write.
Old SevenOwner/Lease/d9/47 objects are never accepted or reopened here.
"""

import hashlib
import os
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import Lock, get_ident
from types import SimpleNamespace
from weakref import WeakKeyDictionary

from cells.processes import betse_native_parameter_load_remainder as parameters

WORLD_CONSTRUCTION_LAW = "betse_fresh_world_ready_pre_phase_seed_construction@1"
RELEASE = "CELLS_NATIVE_PARAMETER_WORLD_CONSTRUCTION_RELEASED"
_LOCK, _ACTIVE = Lock(), []
_ISSUED = WeakKeyDictionary()
claims, prefix = parameters.claims, parameters.prefix


class WorldConstructionRejected(ValueError):
    def __init__(self, reason, *, stage, claim=None, partial=None, capture_errors=()):
        super().__init__(reason)
        self.stage, self.world_construction_claim, self.partial = stage, claim, partial
        self.capture_errors = tuple(capture_errors)


@dataclass(frozen=True, slots=True)
class ClosedSeedRecord:
    law: str
    source_identity: str | None
    parameter_load_identity: str
    before_identity: str
    after_identity: str | None
    work: tuple
    succeeded: bool
    primary_error_present: bool
    secondary_error_stages: tuple
    seed_flag_created: bool
    identity: str


class WorldConstructionClaim:
    """One active interval; only validate_closed_seed authenticates success.

    parameters/check are active-only, including after the permitted SEED flag
    creation. record is closure-only and can describe a failed attempt. The
    consumer must finish its fallible phase sealing inside this same interval.
    """

    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use construction from the actual world-ready owner")

    def __reduce_ex__(self, protocol):
        raise TypeError("Live pre-phase construction authority cannot be serialized")

    @property
    def parameters(self):
        return _checked(self).p

    def check(self):
        _checked(self)

    @property
    def record(self):
        context = _context(self)
        if context.active or context.record is None:
            raise WorldConstructionRejected("No record before closure", stage="active", claim=self)
        if (
            context.record is not context.original_record
            or _digest(record_document(context.record)) != context.record.identity
        ):
            raise WorldConstructionRejected(
                "Closed parameter record changed", stage="record", claim=self
            )
        return context.record


def _digest(value):
    return parameters._digest(value)


def source_plan():
    return dict(
        law=WORLD_CONSTRUCTION_LAW,
        parameter_producer=(
            "src/cells/processes/betse_native_parameter_load_remainder.py",
            hashlib.sha256(Path(parameters.__file__).read_bytes()).hexdigest(),
        ),
        parameters=parameters.source_plan(),
        input="actual completed WorldReadyParametersOwner only",
        mode="fresh phase birth through SEED closure; not a continuation of an earlier phase",
        allowed_parameter_mutation="Create _run_sim once, exact bool False, at the original SEED tail",
        no_temporal_stores_or_other_parameter_changes=True,
        original_Seven_d9_47_API_changed=False,
        phase_constructor_or_handler_or_world_admitted=False,
        consumer_must_authenticate=(
            "actual source phase/cells/sim/cache/dyna/callback chain",
            "exact same issued claim and original owner before first phase/Cells entry",
        ),
        release_requires_root_and_genuine_load_handoff=True,
    )


def record_document(value):
    return dict(
        law=value.law,
        source=value.source_identity,
        parameters=value.parameter_load_identity,
        before=value.before_identity,
        after=value.after_identity,
        work=value.work,
        succeeded=value.succeeded,
        primary_error_present=value.primary_error_present,
        secondary_error_stages=value.secondary_error_stages,
        seed_flag_created=value.seed_flag_created,
        phase_admitted=False,
        cells_admitted=False,
        handler_admitted=False,
        material_admitted=False,
        biological_cases=0,
    )


def _context(claim):
    if type(claim) is not WorldConstructionClaim or claim not in _ISSUED:
        raise WorldConstructionRejected(
            "Actual issued world-construction claim required", stage="claim"
        )
    context = _ISSUED[claim]
    if context.claim is not claim:
        raise WorldConstructionRejected("Replaced claim registry edge", stage="claim", claim=claim)
    return context


def failed_context(claim):
    """Return the actual retained closed failure context for evidence only.

    Use exception.world_construction_claim after a reserved attempt fails,
    including an error before the context manager yields. No claim exists for
    release/law refusal or an attempt refused before reservation. This accessor
    does not invoke a stale parent validator, reopen construction, authenticate
    a success record, or confer parameter/phase authority. A later invalidated
    claim can retain its original successful record as historical evidence.
    """
    context = _context(claim)
    if context.active or not (
        context.invalid or context.source_error is not None or context.capture_errors
    ):
        raise WorldConstructionRejected(
            "Closed failed claim context required",
            stage="failed_context",
            claim=claim,
        )
    return context


def _stacks(context):
    return ((_ACTIVE, context), *parameters._stacks(context))


def _source(context):
    source = parameters._context(context.owner)
    if (
        source is not context.source
        or source.p is not context.p
        or source.parent_owner is not context.parent_owner
        or source.parent is not context.parent
        or source.record is not context.parameter_record
        or source.original_record is not context.parameter_record
        or source.loaded is not context.loaded
        or source.after_graph is not context.before_graph
        or source.after_cm is not context.before_cm
        or source.work is not context.source_work
        or source.bindings is not context.source_bindings
        or parameters._CONSTRUCTED.get(context.owner) is not context.claim
        or parameters._CONSUMED.get(context.parent_owner) is not source
        or context.loaded.owner in claims._CONSTRUCTED
    ):
        raise ValueError("Actual fresh complete-load/owner/p/claim association changed")
    if parameters.validate_completed_history(context.owner) is not context.parameter_record:
        raise ValueError("Original immutable complete-load history changed")
    if _digest(source_plan()) != context.source_identity:
        raise ValueError("World-construction producer changed")
    prefix.parameters.inherited._same(_bindings(), context.bindings)


def _bytes(context, *, complete):
    fields = vars(context.p)
    present = "_run_sim" in fields
    expected = (*context.before_names, "_run_sim") if present else context.before_names
    if tuple(fields) != expected:
        raise ValueError("Constructor changed parameter layout outside the sole SEED flag")
    if present and (type(fields["_run_sim"]) is not bool or fields["_run_sim"] is not False):
        raise ValueError("Only original SEED _run_sim exact bool False may be created")
    if complete and not present:
        raise ValueError("Original SEED flag write was not retained")
    prefix.parameters.inherited._same_graph(
        parameters._capture(context.source, names=context.before_names), context.before_graph
    )
    parameters.previous._same_cm(parameters._colormaps(context.source), context.before_cm)
    if present:
        context.seed_flag_observed = True
    return present


def _checked(claim):
    context = _context(claim)
    if (
        not context.active
        or context.invalid
        or context.thread != get_ident()
        or context.guard.invalid
        or not context.guard.active
        or not context.guard.audit_ready
        or any(not stack or stack[-1] is not value for stack, value in _stacks(context))
    ):
        raise WorldConstructionRejected(
            "Closed/foreign/poisoned active constructor claim",
            stage="claim_state",
            claim=claim,
            partial=context,
        )
    try:
        context.work.append((len(context.work), "active_check", "attempted"))
        _source(context)
        _bytes(context, complete=False)
        context.work.append((len(context.work), "active_check", "completed"))
        return context
    except BaseException:
        context.invalid = context.guard.invalid = True
        raise


def _reserve(owner):
    source = parameters._context(owner)
    with _LOCK:
        if _ACTIVE:
            _ACTIVE[-1].invalid = _ACTIVE[-1].guard.invalid = True
            raise WorldConstructionRejected(
                "Reentrant world-construction attempt", stage="reentrant"
            )
        with parameters._LOCK:
            if owner in parameters._CONSTRUCTED:
                raise WorldConstructionRejected(
                    "World constructor attempt consumed", stage="consumed"
                )
            claim = object.__new__(WorldConstructionClaim)
            context = SimpleNamespace(
                claim=claim,
                owner=owner,
                source=source,
                p=source.p,
                parent_owner=source.parent_owner,
                parent=source.parent,
                loaded=source.loaded,
                parameter_record=source.record,
                before_graph=source.after_graph,
                before_cm=source.after_cm,
                before_names=tuple(vars(source.p)),
                source_work=source.work,
                source_bindings=source.bindings,
                thread=get_ident(),
                active=True,
                invalid=False,
                registered=False,
                validating=False,
                record=None,
                original_record=None,
                source_error=None,
                capture_errors=(),
                source_identity=None,
                bindings=None,
                work=[],
                seed_flag_observed=False,
                failed_capture=None,
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
            )
            # Consume before validation/callback-observable work. Never rearm.
            parameters._CONSTRUCTED[owner] = claim
            _ISSUED[claim] = context
            _ACTIVE.append(context)
            return context, claim


def _finish(context):
    primary = context.source_error
    complete = False
    if primary is None:
        try:
            _checked(context.claim)
            _bytes(context, complete=True)
            complete = True
        except BaseException as error:
            context.capture_errors += (("closed_state_check", error),)
    try:
        context.final_capture = parameters._capture(context.source)
    except BaseException as error:
        context.capture_errors += (("final_capture", error),)
    if context.registered:
        try:
            with claims._registry(context.loaded.owner):
                for stack, value in reversed(_stacks(context)[1:]):
                    if not stack or stack[-1] is not value:
                        raise ValueError("Shared constructor registry changed at closure")
                    stack.pop()
        except BaseException as error:
            context.capture_errors += (("claim_release", error),)
    context.active = context.guard.active = False
    with _LOCK:
        if _ACTIVE and _ACTIVE[-1] is context:
            _ACTIVE.pop()
        else:
            context.capture_errors += (("own_release", ValueError("World reservation changed")),)
    failed = (
        primary is not None
        or context.invalid
        or context.guard.invalid
        or bool(context.capture_errors)
        or not complete
    )
    if failed:
        context.invalid = context.guard.invalid = context.source.invalid = True
    try:
        value = ClosedSeedRecord(
            WORLD_CONSTRUCTION_LAW,
            context.source_identity,
            context.parameter_record.identity,
            _digest(context.before_graph[1]),
            _digest(context.final_capture[1]) if hasattr(context, "final_capture") else None,
            tuple(context.work),
            not failed,
            primary is not None,
            tuple(stage for stage, _ in context.capture_errors),
            context.seed_flag_observed,
            "",
        )
        context.record = replace(value, identity=_digest(record_document(value)))
        context.original_record = context.record
    except BaseException as error:
        context.capture_errors += (("closure_record", error),)
        context.invalid = context.source.invalid = True
        failed = True
    return failed


@contextmanager
def construction(owner, *, law_id, enabled=False):
    if enabled is not True or any(
        os.environ.get(gate) != "1"
        for gate in (RELEASE, parameters.RELEASE, parameters.previous.RELEASE)
    ):
        raise WorldConstructionRejected("Fresh pre-phase constructor remains held", stage="release")
    if type(law_id) is not str or law_id != WORLD_CONSTRUCTION_LAW:
        raise WorldConstructionRejected("Exact fresh SEED construction law required", stage="law")
    context, claim = _reserve(owner)
    primary = None
    try:
        if "_run_sim" in vars(context.p) or context.loaded.owner in claims._CONSTRUCTED:
            raise ValueError("A prior phase/constructor cannot be adopted")
        context.source_identity = _digest(source_plan())
        context.bindings = _bindings()
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in _stacks(context)[1:]):
                claims._busy(context.loaded.owner, "world_construction_conflict")
            for stack, value in _stacks(context)[1:]:
                stack.append(value)
            context.registered = True
            parameters.previous.previous.mod.subconfigs.paths._install_audit(context.guard)
        _checked(claim)
        yield claim
    except BaseException as error:
        primary = context.source_error = error
        raise
    finally:
        failed = _finish(context)
        if primary is not None:
            try:
                primary.world_construction_claim = claim
            except BaseException as error:
                context.capture_errors += (("exception_attachment", error),)
        elif failed:
            raise WorldConstructionRejected(
                "Fresh SEED constructor claim issued no success",
                stage="closure",
                claim=claim,
                partial=context,
                capture_errors=context.capture_errors,
            )


def validate_closed_seed(claim, *, original_owner):
    """Authenticate the actual closed claim without reopening construction.

    The returned record and claim.record are the same immutable object. This
    surface checks parameter history/state only. It cannot replace the actual
    Specialist phase-source owner or admit make_world/init_core/init_profiles.
    """
    context = _context(claim)
    if (
        original_owner is not context.owner
        or context.active
        or context.invalid
        or context.validating
        or context.source_error is not None
        or context.capture_errors
        or context.thread != get_ident()
        or context.guard.thread != context.thread
        or context.record is None
        or context.record.succeeded is not True
    ):
        raise WorldConstructionRejected(
            "Actual successful closed SEED claim required",
            stage="closed",
            claim=claim,
            partial=context,
        )
    context.validating = True
    validation = SimpleNamespace(
        invalid=False,
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
    )
    registered = False
    primary = release_error = None
    try:
        with claims._registry(context.loaded.owner):
            if any(stack for stack, _ in _stacks(context)):
                claims._busy(context.loaded.owner, "closed_world_claim_conflict")
            for stack, _ in _stacks(context):
                stack.append(
                    validation.guard
                    if stack is parameters.previous.previous.mod.subconfigs.paths._ACTIVE
                    else validation
                )
            registered = True
            parameters.previous.previous.mod.subconfigs.paths._install_audit(validation.guard)
        _source(context)
        _bytes(context, complete=True)
        if (
            claim.record is not context.original_record
            or context.record.work != tuple(context.work)
            or validation.invalid
            or validation.guard.invalid
        ):
            raise ValueError("Original closed SEED record/exclusion changed")
        return context.original_record
    except BaseException as error:
        primary = error
        context.invalid = True
        raise WorldConstructionRejected(
            "Closed SEED parameter lineage is stale",
            stage="closed_drift",
            claim=claim,
            partial=context,
        ) from error
    finally:
        if registered:
            try:
                with claims._registry(context.loaded.owner):
                    for stack, _ in reversed(_stacks(context)):
                        expected = (
                            validation.guard
                            if stack is parameters.previous.previous.mod.subconfigs.paths._ACTIVE
                            else validation
                        )
                        if not stack or stack[-1] is not expected:
                            raise ValueError("Closed validation registry changed")
                        stack.pop()
            except BaseException as error:
                release_error = error
                context.invalid = True
                context.capture_errors += (("closed_validation_release", error),)
        validation.guard.active = False
        context.validating = False
        if primary is None and release_error is not None:
            raise WorldConstructionRejected(
                "Closed validation release failed",
                stage="closed_release",
                claim=claim,
                partial=context,
            ) from release_error


def _bindings():
    functions = (
        _digest,
        source_plan,
        record_document,
        _context,
        failed_context,
        _stacks,
        _source,
        _bytes,
        _checked,
        _reserve,
        _finish,
        construction,
        construction.__wrapped__,
        validate_closed_seed,
        _bindings,
        WorldConstructionClaim.parameters.fget,
        WorldConstructionClaim.check,
        WorldConstructionClaim.record.fget,
    )
    return (), (
        WORLD_CONSTRUCTION_LAW,
        RELEASE,
        _LOCK,
        _ACTIVE,
        _ISSUED,
        WorldConstructionClaim,
        WorldConstructionRejected,
        ClosedSeedRecord,
        get_ident,
        *parameters._bindings()[1],
        *(
            atom
            for function in functions
            for atom in prefix.parameters.inherited.tissue.aliases._atoms(function)
        ),
    )
