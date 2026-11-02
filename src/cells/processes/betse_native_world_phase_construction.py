"""Prepared fresh WorldReady -> same-claim SEED constructor coordination.

Every producer and stage hook is intentionally unbound. The proposed route
creates its phase only inside one genuine parameter-construction claim, seals
phase evidence before that claim exits, and publishes only after successful
closed validation. Existing seven-load/d9/47 owners are never cast or reopened.
"""

import hashlib
import importlib
import json
import os
import sys
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, MethodType, SimpleNamespace
from contextlib import contextmanager
from weakref import WeakKeyDictionary

LAW_ID = "betse_fresh_world_ready_same_claim_seed_phase_construction@1"
MODE = "fresh_world_ready_prephase_single_claim_seed_constructor"
RELEASE = "CELLS_NATIVE_WORLD_PHASE_CONSTRUCTION_RELEASED"
KEY_MODULE = "cells.processes.betse_native_parameter_world_construction"
PARAMETER_MODULE = "cells.processes.betse_native_parameter_load_remainder"
KEY_SOURCE_SHA256 = None
KEY_REVIEW_SHA256 = None
PARAMETER_SOURCE_SHA256 = None
PARAMETER_REVIEW_SHA256 = None
# Names/signatures below are a source proposal, not an adopted producer API.
KEY_LAW = "betse_fresh_world_ready_pre_phase_seed_construction@1"
KEY_ERROR_ATTRIBUTE = "world_construction_claim"
STAGES = ("phase_prefix", "caches", "dyna", "seed_tail")
STAGE_MODULES = (
    "cells.processes.betse_native_phase_assembly",
    "cells.processes.betse_native_phase_caches",
    "cells.processes.betse_native_phase_dyna",
    "cells.processes.betse_native_phase_tail",
)
STAGE_SOURCE_SHA256 = (None, None, None, None)
STAGE_REVIEW_SHA256 = (None, None, None, None)
CONSTRUCT_HOOK = "_world_phase_construct"
CHECK_HOOK = "_world_phase_check"
SEAL_HOOK = "_world_phase_seal"
CHECK_SEAL_HOOK = "_world_phase_check_seal"
HELPER_MODULE = "cells.processes.betse_native_seed_world_prefix"
HELPER_SHA256 = "fee5e9fc72c19882fab27c479d8ae718762ed9697cc1082e6896d146009e83e0"
CALLBACK_MODULE = "cells.processes.betse_native_phase_callbacks"
CALLBACK_SHA256 = "4fa19547caac95257162e6678092c3e55ce4fe43b05b2d16f7908f9196740f2d"
BASE_FIELDS = ("callbacks", "cells", "kind", "p", "sim")
MAX_WORK = 128
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []
_VALIDATION = SimpleNamespace(current=None)


class WorldPhaseRejected(ValueError):
    def __init__(
        self, reason, *, stage, request=None, trial=None, partial=None,
        source_error=None, capture_error=None,
    ):
        super().__init__(reason)
        self.stage, self.request, self.trial = stage, request, trial
        self.partial, self.source_error, self.capture_error = partial, source_error, capture_error


@dataclass(frozen=True, slots=True, weakref_slot=True, eq=False)
class Request:
    world_parameters: object
    callbacks: object
    parameter_identity: str
    callback_identity: str
    source_identity: str
    mode: str
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Only genuine process-local WorldReady ancestry may be used")


@dataclass(frozen=True, slots=True, eq=False)
class StageEvidence:
    """Transport only; the exact stage issuer must authenticate every use.

    Constructing this record conveys no authority. ``authority`` is the actual
    stage's registered context, not an inspection dictionary or a saved owner.
    No field claims that the still-active parameter claim has closed.
    """

    stage: str
    authority: object
    phase: object
    parameters: object
    cells: object
    sim: object
    callbacks: object
    kind: object
    cache: object
    handler: object
    trial: object
    work: object
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("Live stage evidence is not a hydration format")


@dataclass(frozen=True, slots=True, eq=False)
class PhaseSeal:
    """Whole-phase source capture produced and checked inside the claim."""

    evidence: StageEvidence
    phase: object
    parameters: object
    stages: tuple
    cache: object
    graph: object
    bindings: object
    identity: str

    def __reduce_ex__(self, protocol):
        raise TypeError("A phase seal cannot reconstruct executable ownership")


@dataclass(frozen=True, slots=True)
class Trial:
    request_identity: str
    mode: str
    phase_identity: str
    stage_identities: tuple
    stage_trials: tuple
    stage_work: tuple
    coordinator_work: tuple
    identity: str


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def source_plan():
    """Pure declaration; no import, parameter check, constructor or replay."""
    return dict(
        law=LAW_ID, mode=MODE,
        key_source=KEY_SOURCE_SHA256, key_review=KEY_REVIEW_SHA256,
        parameter_source=PARAMETER_SOURCE_SHA256, parameter_review=PARAMETER_REVIEW_SHA256,
        stage_sources=STAGE_SOURCE_SHA256, stage_reviews=STAGE_REVIEW_SHA256,
        stages=STAGES,
        construction_before_any_phase_allocation=True,
        one_active_claim_through_all_stages=True,
        stage_hooks_require_exact_claimed_coordinator_frame=True,
        phase_sealing_inside_claim=True,
        public_closed_records_between_stages=False,
        publication_after_exact_closed_owner_claim_parameter_validation=True,
        proposed_hooks=dict(
            construct=(
                "_world_phase_construct(transition, *, world_owner, construction_claim, "
                "callback_owner, predecessor) -> StageEvidence"
            ),
            check=(
                "_world_phase_check(evidence, *, transition, world_owner, "
                "construction_claim, predecessor, closed_record) -> same StageEvidence"
            ),
            seal=(
                "_world_phase_seal(evidence, *, transition, world_owner, "
                "construction_claim, stages) -> PhaseSeal; tail only, active claim"
            ),
            check_seal=(
                "_world_phase_check_seal(seal, *, transition, world_owner, "
                "construction_claim, closed_record) -> same PhaseSeal; tail only"
            ),
        ),
        proposed_key_api=(
            "construction(world_owner, law_id=WORLD_CONSTRUCTION_LAW, enabled=True)",
            "active claim.parameters and claim.check()",
            "validate_closed_seed(claim, original_owner=world_owner) -> exact claim.record",
        ),
        allowed_parameter_transition="native absent _run_sim -> exact False at SEED tail only",
        default_callback_factory_owned=False,
        existing_legacy_apis_changed=False,
        make_world_lattice_or_init_core_or_phase_use_admitted=False,
        source_native_scientific_release=False,
        postcut_owners_invalidated=11, postcut_scientific_cases_held=12,
    )


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ready():
    pins = (
        KEY_SOURCE_SHA256, KEY_REVIEW_SHA256,
        PARAMETER_SOURCE_SHA256, PARAMETER_REVIEW_SHA256,
        *STAGE_SOURCE_SHA256, *STAGE_REVIEW_SHA256,
    )
    if not all(_pin(value) for value in pins):
        raise WorldPhaseRejected(
            "Actual reviewed WorldReady producer and same-claim stage hooks remain unbound",
            stage="unbound_contract",
        )


def _module_file(name):
    return Path(__file__).resolve().parents[3] / ("src/" + name.replace(".", "/") + ".py")


def _import_bound(name, expected):
    path = _module_file(name)
    if path.is_symlink() or not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("Exact reviewed consumer dependency unavailable: " + name)
    module = importlib.import_module(name)
    if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
        raise ValueError("Actual canonical producer module required: " + name)
    return module


def _dependencies():
    _ready()  # Refuse before even importing an unsealed Key or stage producer.
    helpers = _import_bound(HELPER_MODULE, HELPER_SHA256)
    key = _import_bound(KEY_MODULE, KEY_SOURCE_SHA256)
    parameters = _import_bound(PARAMETER_MODULE, PARAMETER_SOURCE_SHA256)
    callbacks = _import_bound(CALLBACK_MODULE, CALLBACK_SHA256)
    stages = tuple(
        _import_bound(name, pin)
        for name, pin in zip(STAGE_MODULES, STAGE_SOURCE_SHA256, strict=True)
    )
    if key.WORLD_CONSTRUCTION_LAW != KEY_LAW:
        raise ValueError("Explicitly reviewed fresh-world construction law required")
    functions = [
        (key, "construction"), (key, "validate_closed_seed"),
        (parameters, "validate_completed_history"),
    ]
    functions.extend((module, name) for module in stages for name in (CONSTRUCT_HOOK, CHECK_HOOK))
    functions.extend((stages[-1], name) for name in (SEAL_HOOK, CHECK_SEAL_HOOK))
    for module, name in functions:
        fn = getattr(module, name, None)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(module):
            raise ValueError("Missing actual same-claim source hook: " + name)
    return SimpleNamespace(
        helpers=helpers, key=key, parameters=parameters, callbacks=callbacks, stages=stages,
    )


def request_record(value):
    return dict(
        law=LAW_ID, mode=value.mode, parameters=value.parameter_identity,
        callbacks=value.callback_identity, source=value.source_identity,
        fresh_phase_required=True, legacy_owner_cast=False,
    )


def from_world_ready(owner, callback_owner, *, law_id, mode):
    _construction_entry("from_world_ready")
    if type(law_id) is not str or law_id != LAW_ID or type(mode) is not str or mode != MODE:
        raise WorldPhaseRejected("Exact fresh-world law and source mode required", stage="law")
    api = _dependencies()
    if type(owner) is not api.parameters.WorldReadyParametersOwner:
        raise WorldPhaseRejected("Actual fresh WorldReady owner required", stage="parameters")
    record = api.parameters.validate_completed_history(owner)
    p = owner.parameters  # Pre-claim access only; never called after _run_sim mutation.
    callback = api.callbacks._validate(callback_owner)
    if callback.callback is None or not callback.trial.factory_completed:
        raise WorldPhaseRejected("Actual prepared callback required", stage="callback")
    value = Request(owner, callback_owner, record.identity, callback.trial.identity,
                    _digest(source_plan()), mode, "")
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (record, p, callback, callback.callback, callback.trial)
    return value


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.primary is not None:
        raise context.primary
    if context.capture_error is not None:
        raise WorldPhaseRejected("Retained phase observation/sealing failure", stage=context.stage,
                                 capture_error=context.capture_error)
    if (context.invalid or not context.active or context.thread != get_ident()
            or not _ACTIVE or _ACTIVE[-1] is not context):
        raise WorldPhaseRejected("Unavailable world-construction epoch", stage="entry")


def _attempt(context, name, state):
    row = dict(sequence=len(context.work), stage=name, state=state, layer="coordinator",
               source_call_count_is_not_case_count=True)
    if len(context.work) >= MAX_WORK:
        context.overflow_attempt = row
        raise WorldPhaseRejected("Bounded coordinator work exhausted", stage="work")
    context.work.append(row)
    return row


def _independent_atoms(function):
    """Bootstrap metadata only; never call the helper being authenticated."""
    result, seen, pending = [], set(), [function]
    while pending:
        value = pending.pop()
        if value is None or id(value) in seen:
            continue
        if len(seen) >= 64:
            raise ValueError("Bounded checker helper chain exhausted")
        seen.add(id(value))
        result.append(value)
        if type(value) is MethodType:
            result.extend((value.__self__, value.__func__))
            pending.append(value.__func__)
        elif type(value) is FunctionType:
            result.extend((value.__code__, value.__globals__, value.__defaults__, value.__closure__))
            for item in value.__defaults__ or ():
                result.append(item)
                if type(item) in (FunctionType, MethodType):
                    pending.append(item)
            defaults = value.__kwdefaults__
            result.append(defaults)
            if defaults is not None:
                if type(defaults) is not dict or len(defaults) > 64:
                    raise ValueError("Bounded actual checker keyword defaults required")
                for key, item in defaults.items():
                    result.extend((key, item))
                    if type(item) in (FunctionType, MethodType):
                        pending.append(item)
            for cell in value.__closure__ or ():
                result.append(cell)
                item = cell.cell_contents
                result.append(item)
                if type(item) in (FunctionType, MethodType):
                    pending.append(item)
            for name in ("__wrapped__", "_implementation"):
                item = vars(value).get(name)
                result.extend((name, item))
                if type(item) in (FunctionType, MethodType):
                    pending.append(item)
    return tuple(result)


def _helper_authority(api):
    helpers, literal = api.helpers, api.helpers.literal
    return (
        helpers, literal,
        *_independent_atoms(helpers._atoms),
        *_independent_atoms(literal._surface),
        *_independent_atoms(literal._same),
    )


def _check_helpers(context):
    actual, retained = _helper_authority(context.api), context.helper_authority
    if len(actual) != len(retained) or any(a is not b for a, b in zip(actual, retained, strict=True)):
        raise ValueError("Original checker/atom/surface helper identity or code changed")


def _compare_bindings(context):
    _check_helpers(context)
    actual = _bindings(context)
    _check_helpers(context)
    context.api.helpers.literal._same(actual, context.bindings)


def _bindings(context):
    _check_helpers(context)  # Independently BEFORE the first helper invocation.
    api = context.api
    functions = [
        _digest, source_plan, _pin, _ready, _module_file, _import_bound, _dependencies,
        request_record, from_world_ready, _retain_failure,
        _guard, _attempt, _independent_atoms, _helper_authority, _check_helpers,
        _compare_bindings, _bindings, _check_bindings, _same_dependencies,
        _construction_entry, _reject_validation, _reserve_validation,
        _validation_check, _release_validation, _validation_scope,
        _active_claim, _check_evidence,
        _step, _trial_record, _seal_active, _coordinate, _closed, _partial, _validate, prepare,
        api.key.construction, api.key.validate_closed_seed,
        api.parameters.validate_completed_history,
        api.key.WorldConstructionClaim.parameters.fget, api.key.WorldConstructionClaim.check,
        api.key.WorldConstructionClaim.record.fget,
        api.callbacks._validate,
    ]
    functions.extend(getattr(module, name) for module in api.stages
                     for name in (CONSTRUCT_HOOK, CHECK_HOOK))
    functions.extend(getattr(api.stages[-1], name) for name in (SEAL_HOOK, CHECK_SEAL_HOOK))
    return (
        _REQUESTS, _CONSUMED, _CLAIMED, _ISSUED, _ACTIVE, _LOCK, _VALIDATION,
        LAW_ID, MODE, RELEASE, STAGES, STAGE_MODULES, BASE_FIELDS, MAX_WORK,
        KEY_MODULE, KEY_LAW, KEY_ERROR_ATTRIBUTE, PARAMETER_MODULE,
        KEY_SOURCE_SHA256, KEY_REVIEW_SHA256, PARAMETER_SOURCE_SHA256, PARAMETER_REVIEW_SHA256,
        STAGE_SOURCE_SHA256, STAGE_REVIEW_SHA256,
        CONSTRUCT_HOOK, CHECK_HOOK, SEAL_HOOK, CHECK_SEAL_HOOK,
        api.helpers, api.key, api.parameters, api.callbacks, *api.stages,
        api.key.WorldConstructionClaim, api.key.ClosedSeedRecord,
        api.parameters.WorldReadyParametersOwner,
        *(atom for cls in (Request, StageEvidence, PhaseSeal, Trial, WorldPhaseOwner)
          for atom in api.helpers.literal._surface(cls)),
        *(atom for fn in functions for atom in api.helpers._atoms(fn)),
    )


def _check_bindings(context):
    _guard(context)
    _same_dependencies(context)
    _compare_bindings(context)
    callback = context.api.callbacks._validate(context.request.callbacks)
    if (callback is not context.parents[2] or callback.callback is not context.parents[3]
            or callback.trial is not context.parents[4]):
        raise ValueError("Original issued prepared callback changed")
    if (_REQUESTS.get(context.request) is not context.parents
            or _CONSUMED.get(context.request) is not context
            or _CLAIMED.get(context.request.world_parameters) is not context
            or _digest(source_plan()) != context.request.source_identity
            or _digest(request_record(context.request)) != context.request.identity):
        raise ValueError("Original request/source/one-shot ancestry changed")


def _same_dependencies(context):
    actual = _dependencies()
    if (any(getattr(actual, name) is not getattr(context.api, name)
            for name in ("helpers", "key", "parameters", "callbacks"))
            or len(actual.stages) != len(context.api.stages)
            or any(a is not b for a, b in zip(actual.stages, context.api.stages, strict=True))):
        raise ValueError("Actual reviewed producer/module identity changed")


def _active_claim(context):
    _check_bindings(context)
    if type(context.claim) is not context.api.key.WorldConstructionClaim:
        raise ValueError("Actual same active WorldConstructionClaim required")
    context.claim.check()
    if context.claim.parameters is not context.p or context.p is not context.parents[1]:
        raise ValueError("Original world-ready claim/p association changed")


def _check_evidence(context, evidence, index, *, closed_record=None):
    if type(evidence) is not StageEvidence or evidence.stage != STAGES[index]:
        raise ValueError("Actual exact stage evidence required")
    predecessor = None if index == 0 else context.evidence[index - 1]
    module = context.api.stages[index]
    actual = getattr(module, CHECK_HOOK)(
        evidence, transition=context, world_owner=context.request.world_parameters,
        construction_claim=context.claim, predecessor=predecessor, closed_record=closed_record,
    )
    if actual is not evidence or evidence.parameters is not context.p:
        raise ValueError("Original stage issuer/p/evidence reference changed")
    phase = evidence.phase
    fields = vars(phase)
    # Old stage witnesses retain their original objects, not a stale field
    # roster. After SEED closure, every witness sees the completed phase.
    reached = index if closed_record is None else len(STAGES) - 1
    names = (*BASE_FIELDS, *(("cache",) if reached >= 1 else ()),
             *(("dyna",) if reached >= 2 else ()),
             *(("export_dirname",) if reached == 3 else ()))
    if tuple(fields) != names:
        raise ValueError("Original constructor stage field order changed")
    pairs = (
        (fields["p"], context.p), (fields["callbacks"], context.parents[3]),
        (fields["cells"], evidence.cells), (fields["sim"], evidence.sim),
        (evidence.callbacks, context.parents[3]),
        (fields["kind"], evidence.kind),
    )
    if any(a is not b for a, b in pairs):
        raise ValueError("Actual same-phase constructor aliases changed")
    if index:
        first = context.evidence[0]
        if (phase is not first.phase or evidence.cells is not first.cells
                or evidence.sim is not first.sim or evidence.kind is not first.kind):
            raise ValueError("Stage substituted an already constructed phase/Cells/Simulator")
    if index >= 1 and fields["cache"] is not evidence.cache:
        raise ValueError("Actual phase-cache assignment changed")
    if index >= 2 and fields["dyna"] is not evidence.handler:
        raise ValueError("Actual fresh same-parameter handler assignment changed")
    if index > 1 and evidence.cache is not context.evidence[1].cache:
        raise ValueError("Original actual cache object was replaced")
    if index > 2 and evidence.handler is not context.evidence[2].handler:
        raise ValueError("Original actual TissueHandler was replaced")
    if index == 3:
        if (vars(context.p).get("_run_sim") is not False
                or vars(evidence.sim).get("dyna") is not evidence.handler
                or fields["export_dirname"] is not vars(context.p)["init_export_dirname"]):
            raise ValueError("Original SEED constructor-tail stores changed")
    elif closed_record is None and "_run_sim" in vars(context.p):
        raise ValueError("SEED flag appeared before its literal tail")
    return evidence


def _step(context, index):
    caller = sys._getframe(1)
    ticket = context.dispatch_ticket
    valid = (
        ticket is not None and ticket[0] == index and ticket[1] is caller
        and caller is context.driver_frame and context.executing is None
        and index == len(context.evidence) and not context.invalid
    )
    if not valid:
        context.invalid = True
        if context.entry_error is None:
            context.entry_error = WorldPhaseRejected("Repeated/reentrant/out-of-order stage", stage="entry")
        try:
            row = _attempt(context, STAGES[index], "rejected")
        except BaseException as capture:
            context.capture_errors = (
                *context.capture_errors, ("rejected_stage_attempt", capture, context.entry_error),
            )
            if context.capture_error is None:
                context.capture_error = capture
        raise context.entry_error
    # Consume the caller's ticket before reporters/checkers can seize a slot.
    context.dispatch_ticket = None
    context.executing = index
    context.stage = STAGES[index]
    row = None
    try:
        context.step_frame = sys._getframe()
        row = _attempt(context, STAGES[index], "attempted")
        _active_claim(context)
        if "_run_sim" in vars(context.p):
            raise ValueError("SEED flag must be absent before the tail's actual source entry")
        predecessor = None if index == 0 else context.evidence[-1]
        value = getattr(context.api.stages[index], CONSTRUCT_HOOK)(
            context, world_owner=context.request.world_parameters,
            construction_claim=context.claim, callback_owner=context.request.callbacks,
            predecessor=predecessor,
        )
        context.last_returned = value  # Retain raw result before any observation/check.
        _active_claim(context)
        _check_evidence(context, value, index)
        context.evidence.append(value)
        row["state"] = "returned"
        return value
    except BaseException as error:
        if row is not None:
            row["state"] = "failed"
            row["error"] = error
        raise
    finally:
        context.executing = None
        context.step_frame = None


def _seal_active(context):
    context.stage = "phase_sealing_inside_claim"
    row = _attempt(context, context.stage, "attempted")
    _active_claim(context)
    tail = context.evidence[-1]
    seal = getattr(context.api.stages[-1], SEAL_HOOK)(
        tail, transition=context, world_owner=context.request.world_parameters,
        construction_claim=context.claim, stages=tuple(context.evidence),
    )
    context.raw_seal = seal
    if (type(seal) is not PhaseSeal or seal.evidence is not tail
            or seal.phase is not tail.phase or seal.parameters is not context.p
            or len(seal.stages) != len(context.evidence)
            or any(a is not b for a, b in zip(seal.stages, context.evidence, strict=True))):
        raise ValueError("Actual full-phase source seal required")
    actual = getattr(context.api.stages[-1], CHECK_SEAL_HOOK)(
        seal, transition=context, world_owner=context.request.world_parameters,
        construction_claim=context.claim, closed_record=None,
    )
    if actual is not seal:
        raise ValueError("Actual in-claim phase seal reference changed")
    context.seal = seal
    row["state"] = "phase_capture_returned"
    # All fallible capture/digest/Trial creation is inside the ACTIVE claim.
    trial = Trial(
        context.request.identity, MODE, seal.identity,
        tuple(value.identity for value in context.evidence),
        tuple(value.trial for value in context.evidence),
        tuple(value.work for value in context.evidence),
        tuple((item["sequence"], item["stage"], item["state"], item["layer"])
              for item in context.work), "",
    )
    identity = _digest(_trial_record(trial))
    context.trial = replace(trial, identity=identity)
    _active_claim(context)


def _trial_record(value):
    return dict(
        request=value.request_identity, mode=value.mode, phase=value.phase_identity,
        stages=value.stage_identities, coordinator_work=value.coordinator_work,
        stage_work_is_separate_nonadditive_source_evidence=True,
        successful_closed_parameter_record_is_not_invented_inside_claim=True,
    )


def _closed(context, *, validation=None):
    # No old owner.parameters, old Lease.check(), d9 or47 validation is used.
    if validation is not None:
        _validation_check(validation)
    record = context.api.key.validate_closed_seed(
        context.claim, original_owner=context.request.world_parameters
    )
    if validation is not None:
        _validation_check(validation)
    if (type(record) is not context.api.key.ClosedSeedRecord
            or context.claim.record is not record or record is not context.parameter_record
            or record.succeeded is not True or record.primary_error_present is not False
            or record.seed_flag_created is not True
            or record.parameter_load_identity != context.parents[0].identity
            or record.secondary_error_stages):
        raise ValueError("Exact successful closed WorldReady owner/claim/record required")
    if validation is not None:
        _validation_check(validation)
    for index, evidence in enumerate(context.evidence):
        _check_evidence(context, evidence, index, closed_record=record)
        if validation is not None:
            _validation_check(validation)
    if getattr(context.api.stages[-1], CHECK_SEAL_HOOK)(
        context.seal, transition=context, world_owner=context.request.world_parameters,
        construction_claim=context.claim, closed_record=record,
    ) is not context.seal:
        raise ValueError("Retained whole-phase source seal changed")
    if validation is not None:
        _validation_check(validation)
    trial = context.trial
    if (type(trial) is not Trial or trial.request_identity != context.request.identity
            or trial.mode != MODE or trial.phase_identity != context.seal.identity
            or trial.stage_identities != tuple(value.identity for value in context.evidence)
            or _digest(_trial_record(trial)) != trial.identity
            or len(trial.stage_trials) != len(context.evidence)
            or any(a is not b.trial for a, b in zip(
                trial.stage_trials, context.evidence, strict=True
            ))
            or any(a is not b.work for a, b in zip(
                trial.stage_work, context.evidence, strict=True
            ))):
        raise ValueError("Original in-claim phase Trial/stage evidence changed")
    return record


def _coordinate(context):
    try:
        context.driver_frame = sys._getframe()
        with context.api.key.construction(
            context.request.world_parameters, law_id=KEY_LAW, enabled=True
        ) as claim:
            context.claim = claim
            try:
                _active_claim(context)  # Before any phase allocation.
                for index in range(len(STAGES)):
                    context.dispatch_ticket = (index, context.driver_frame)
                    _step(context, index)
                try:
                    _seal_active(context)
                except BaseException as error:
                    # Raw retention precedes any fallible reporter call.
                    context.invalid = True
                    if context.capture_error is None:
                        context.capture_error = error
                    context.capture_errors = (
                        *context.capture_errors,
                        ("phase_sealing_inside_claim", error, context.raw_seal),
                    )
                    raise
            except BaseException as error:
                if context.entry_error is not None:
                    context.primary = context.entry_error
                elif context.primary is None and error is not context.capture_error:
                    context.primary = error
                try:
                    _retain_failure(context, error, context.stage)
                except BaseException as capture:
                    context.invalid = True
                    if context.capture_error is None:
                        context.capture_error = capture
                    context.capture_errors = (
                        *context.capture_errors, ("stage_failure_recording", capture, error),
                    )
                raise
    except BaseException as error:
        if context.primary is None and context.capture_error is None:
            context.primary = error
            try:
                _retain_failure(context, error, "parameter_claim")
            except BaseException as capture:
                context.invalid = True
                if context.capture_error is None:
                    context.capture_error = capture
                context.capture_errors = (
                    *context.capture_errors, ("claim_failure_recording", capture, error),
                )
        elif error is not context.primary and error is not context.capture_error:
            context.claim_errors = (*context.claim_errors, error)
        try:
            context.failed_claim = getattr(error, KEY_ERROR_ATTRIBUTE, None)
            context.failed_claim_partial = getattr(error, "partial", None)
        except BaseException as capture:
            context.invalid = True
            if context.capture_error is None:
                context.capture_error = capture
            context.capture_errors = (
                *context.capture_errors, ("parameter_claim_failure_evidence", capture, error),
            )
    finally:
        if context.claim is not None:
            try:
                context.parameter_record = context.claim.record
            except BaseException as capture:
                context.invalid = True
                if context.capture_error is None:
                    context.capture_error = capture
                context.capture_errors = (
                    *context.capture_errors, ("closed_parameter_record", capture, context.claim),
                )
    if context.primary is None and context.capture_error is None:
        try:
            context.stage = "closed_owner_claim_parameter_authentication"
            _check_bindings(context)
            _closed(context)
        except BaseException as error:
            context.primary = error


def _retain_failure(context, error, origin):
    context.failed_stages = (*context.failed_stages, (origin, error))
    if context.entry_error is not None:
        context.primary = context.entry_error
    try:
        partial = getattr(error, "partial", None)
        primary = getattr(error, "source_error", None)
        capture = getattr(error, "capture_error", None)
        context.stage_partials = (*context.stage_partials, (origin, partial))
    except BaseException as observation:
        context.capture_errors = (
            *context.capture_errors, ("stage_error_attributes", observation, error),
        )
        context.invalid = True
        if context.capture_error is None:
            context.capture_error = observation
        if context.primary is None:
            context.primary = error
        return
    if primary is not None and (context.primary is None or context.primary is error):
        context.primary = primary
    if capture is not None:
        if primary is None and context.primary is error:
            context.primary = None
        context.capture_errors = (*context.capture_errors, (origin, capture, partial))
        context.invalid = True
        if context.capture_error is None:
            context.capture_error = capture
    if (context.primary is None and primary is None and capture is None
            and error is not context.capture_error):
        context.primary = error


def _partial(context):
    return dict(
        context=context, request=context.request, original_world_owner=context.request.world_parameters,
        original_parameter_record=context.parents[0], parameters=context.p,
        actual_claim=context.claim, closed_parameter_record=context.parameter_record,
        retained_stage_evidence=context.evidence, last_raw_stage_return=context.last_returned,
        raw_phase_seal=context.raw_seal, phase_seal=context.seal, trial=context.trial,
        coordinator_work=context.work, primary=context.primary, entry_error=context.entry_error,
        driver_frame=context.driver_frame, current_step_frame=context.step_frame,
        pending_dispatch_ticket=context.dispatch_ticket,
        capture_errors=context.capture_errors, claim_errors=context.claim_errors,
        failed_stages=context.failed_stages, stage_partials=context.stage_partials,
        failed_claim=context.failed_claim, failed_claim_partial=context.failed_claim_partial,
        usable_child_available=False, complete_raw_serialization_claimed=False,
        last_validation=getattr(context, "last_validation", None),
        validation_failures=getattr(context, "validation_failures", ()),
    )


def prepare(request, *, enabled=False):
    _construction_entry("prepare")
    if enabled is not True or os.environ.get(RELEASE) != "1":
        raise WorldPhaseRejected("Prepared source-only world phase remains held", stage="release")
    api = _dependencies()
    with _LOCK:
        _construction_entry("prepare_reservation")
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
            raise WorldPhaseRejected("Reentrant world-construction attempt", stage="reentrant")
        if type(request) is not Request or request not in _REQUESTS:
            raise WorldPhaseRejected("Actual issued WorldReady/callback request required", stage="request")
        if request in _CONSUMED or request.world_parameters in _CLAIMED:
            raise WorldPhaseRejected("World construction attempt consumed", stage="consumed")
        context = SimpleNamespace(
            request=request, parents=_REQUESTS[request], api=api, p=_REQUESTS[request][1],
            thread=get_ident(), active=True, invalid=False, entry_error=None,
            primary=None, capture_error=None, capture_errors=(), claim_errors=(),
            failed_stages=(), stage_partials=(),
            claim=None, parameter_record=None, failed_claim=None, failed_claim_partial=None,
            evidence=[], last_returned=None, raw_seal=None, seal=None, trial=None,
            work=[], executing=None, stage="construction_claim_before_phase_birth",
            dispatch_ticket=None, driver_frame=None, step_frame=None,
        )
        _CONSUMED[request] = _CLAIMED[request.world_parameters] = context
        _ACTIVE.append(context)
        try:
            context.helper_authority = _helper_authority(api)
            context.bindings = _bindings(context)
            _coordinate(context)
        except BaseException as error:
            if context.primary is None:
                context.primary = error
        finally:
            context.active = False
            try:
                if not _ACTIVE or _ACTIVE[-1] is not context:
                    raise ValueError("Original coordinator stack changed")
                _ACTIVE.pop()
            except BaseException as capture:
                context.invalid = True
                if context.capture_error is None:
                    context.capture_error = capture
                context.capture_errors = (
                    *context.capture_errors, ("coordinator_stack_release", capture, context),
                )
        if (context.primary is not None or context.capture_error is not None
                or context.trial is None or context.parameter_record is None or context.invalid):
            raise WorldPhaseRejected(
                "Actual world-phase construction refused", stage=context.stage, request=request,
                trial=context.trial, partial=_partial(context), source_error=context.primary,
                capture_error=context.capture_error,
            ) from (context.primary if context.primary is not None else context.capture_error)
        owner = object.__new__(WorldPhaseOwner)
        context.owner = owner
        _ISSUED[owner] = context
        return owner


class WorldPhaseOwner:
    __slots__ = ("__weakref__",)

    def __init__(self):
        raise TypeError("Use the genuine fresh WorldReady construction coordinator")

    def __reduce_ex__(self, protocol):
        raise TypeError("Executable phase ownership cannot be serialized or hydrated")

    @property
    def phase(self):
        return _validate(self).seal.phase

    @property
    def trial(self):
        return _validate(self).trial

    @property
    def parameter_record(self):
        return _validate(self).parameter_record


def _validate(owner):
    context = _ISSUED.get(owner) if type(owner) is WorldPhaseOwner else None
    if (context is None or context.owner is not owner or context.active or context.invalid
            or context.thread != get_ident()):
        raise WorldPhaseRejected("Actual successfully sealed world-phase child required", stage="owner")
    try:
        # Runtime registry/source checks remain live; no stale numeric parent
        # validator or closed claim's active .check() is reopened here.
        if (_REQUESTS.get(context.request) is not context.parents
                or _CONSUMED.get(context.request) is not context
                or _CLAIMED.get(context.request.world_parameters) is not context
                or _digest(source_plan()) != context.request.source_identity):
            raise ValueError("World phase original issuance/source changed")
        _same_dependencies(context)
        context.api.helpers.literal._same(_bindings(context), context.bindings)
        _closed(context)
    except BaseException as error:
        context.invalid = True
        raise WorldPhaseRejected("Stale world-phase owner", stage="owner_drift",
                                 request=context.request, trial=context.trial,
                                 partial=_partial(context), source_error=error) from error
    return context
