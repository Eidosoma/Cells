"""Prepared fresh WorldReady -> same-claim SEED constructor coordination.

Every new producer/stage pin is intentionally unbound. The prepared route
creates its phase only inside one genuine parameter-construction claim, seals
phase evidence before that claim exits, and publishes only after successful
closed validation. Existing seven-load/d9/47 owners are never cast or reopened.
"""

import ast
import hashlib
import importlib
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path
from threading import RLock, get_ident
from types import FunctionType, MethodType, SimpleNamespace
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
# Stable public preparation interface; no producer/review adoption is implied.
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
HELPER_INTERFACE_SHA256 = None  # Separate reviewed adoption remains required.
HELPER_CONSTRUCTION_REVIEW_SHA256 = None
HELPER_BINDING_KIND = "exact_helper_bytes_except_two_validated_backref_literals@1"
HELPER_BACK_REFERENCE_SLOTS = ("CONSTRUCTION_SOURCE_SHA256", "CONSTRUCTION_REVIEW_SHA256")
VORONOI_IMAGE_MODULE = "cells.processes.betse_native_seed_voronoi_image"
VORONOI_IMAGE_MODE = "fresh_world_seed_lattice_make_voronoi_image_prefix"
VORONOI_IMAGE_SOURCE_SHA256 = None
VORONOI_IMAGE_REVIEW_SHA256 = None
VORONOI_MESH_MODULE = "cells.processes.betse_native_seed_voronoi_mesh"
VORONOI_MESH_MODE = "fresh_world_seed_voronoi_mesh_constructor_assignment"
VORONOI_MESH_SOURCE_SHA256 = None
VORONOI_MESH_REVIEW_SHA256 = None
CALLBACK_MODULE = "cells.processes.betse_native_phase_callbacks"
CALLBACK_SHA256 = "4fa19547caac95257162e6678092c3e55ce4fe43b05b2d16f7908f9196740f2d"
BASE_FIELDS = ("callbacks", "cells", "kind", "p", "sim")
MAX_WORK = 128
_REQUESTS, _CONSUMED, _CLAIMED, _ISSUED = (WeakKeyDictionary() for _ in range(4))
_LOCK, _ACTIVE = RLock(), []
_VALIDATION = SimpleNamespace(current=None)
_FORWARDED = WeakKeyDictionary()


class WorldPhaseRejected(ValueError):
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


@dataclass(frozen=True, slots=True)
class SourceStageTrial:
    mode: str
    stage: str
    cache: object
    events: tuple
    work: tuple
    identity: str


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def source_plan():
    """Pure declaration; no import, parameter check, constructor or replay."""
    return dict(
        law=LAW_ID,
        mode=MODE,
        key_source=KEY_SOURCE_SHA256,
        key_review=KEY_REVIEW_SHA256,
        parameter_source=PARAMETER_SOURCE_SHA256,
        parameter_review=PARAMETER_REVIEW_SHA256,
        stage_sources=STAGE_SOURCE_SHA256,
        stage_reviews=STAGE_REVIEW_SHA256,
        helper_source=None,  # Complete source bytes belong to the external snapshot.
        helper_interface=HELPER_INTERFACE_SHA256,
        helper_constructor_review=HELPER_CONSTRUCTION_REVIEW_SHA256,
        helper_binding_kind=HELPER_BINDING_KIND,
        helper_back_reference_slots=HELPER_BACK_REFERENCE_SLOTS,
        helper_non_back_reference_bytes_exact=True,
        helper_back_references_checked_against_full_constructor_bytes=True,
        voronoi_image=dict(
            module=VORONOI_IMAGE_MODULE,
            mode=VORONOI_IMAGE_MODE,
            source=VORONOI_IMAGE_SOURCE_SHA256,
            review=VORONOI_IMAGE_REVIEW_SHA256,
            binding="one-way full image-module source from this coordinator",
            boundary="before lattice_to_mesh_type/DECMesh",
            released=False,
        ),
        voronoi_mesh=dict(
            module=VORONOI_MESH_MODULE,
            mode=VORONOI_MESH_MODE,
            source=VORONOI_MESH_SOURCE_SHA256,
            review=VORONOI_MESH_REVIEW_SHA256,
            boundary="constructor completion -> caller.mesh assignment; before lifecycle",
            released=False,
        ),
        binding_adoption_order=(
            "review helper byte template with only two back-reference literals normalized",
            "bind that template and the independent producer/stage pins in the constructor",
            "bind final full constructor bytes and review in the helper back-references",
            "freeze and authenticate both complete source files externally",
        ),
        stages=STAGES,
        construction_before_any_phase_allocation=True,
        one_active_claim_through_all_stages=True,
        stage_hooks_require_exact_claimed_coordinator_frame=True,
        checker_helpers_authenticated_independently_before_use=True,
        closed_owner_validation_reserved_through_key_and_stage_checks=True,
        phase_sealing_inside_claim=True,
        public_closed_records_between_stages=False,
        private_same_claim_stage_hooks_implemented=True,
        exact_same_instance_seed_and_world_dispatch_prepared=True,
        legacy_seven_d9_47_claims_not_used_by_world_mode=True,
        legacy_file_pins_unchanged_pending_separate_successor_adoption=True,
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
        postcut_owners_invalidated=11,
        postcut_scientific_cases_held=12,
    )


def _pin(value):
    return type(value) is str and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _ready():
    pins = (
        KEY_SOURCE_SHA256,
        KEY_REVIEW_SHA256,
        PARAMETER_SOURCE_SHA256,
        PARAMETER_REVIEW_SHA256,
        *STAGE_SOURCE_SHA256,
        *STAGE_REVIEW_SHA256,
        HELPER_INTERFACE_SHA256,
        HELPER_CONSTRUCTION_REVIEW_SHA256,
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
    if (
        path.is_symlink()
        or not path.is_file()
        or hashlib.sha256(path.read_bytes()).hexdigest() != expected
    ):
        raise ValueError("Exact reviewed consumer dependency unavailable: " + name)
    module = importlib.import_module(name)
    if sys.modules.get(name) is not module or Path(module.__file__).resolve() != path:
        raise ValueError("Actual canonical producer module required: " + name)
    return module


def _helper_binding(payload):
    """Exact bytes except two top-level literal values; never execute the image.

    Unlike an AST fingerprint, this retains comments, whitespace and every
    other source byte. The two omitted values are separately authenticated
    against the complete constructor image and its explicit review pin.
    """
    if type(payload) is not bytes:
        raise ValueError("Actual helper source bytes required")
    tree = ast.parse(payload.decode("utf-8"), type_comments=True)
    slots, spans = {}, []
    lines = payload.splitlines(keepends=True)
    offsets, offset = [], 0
    for line in lines:
        offsets.append(offset)
        offset += len(line)
    for name in HELPER_BACK_REFERENCE_SLOTS:
        writes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store) and node.id == name
        ]
        assignments = [
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and len(node.targets) == 1
            and isinstance(node.targets[0], ast.Name)
            and node.targets[0].id == name
        ]
        if len(writes) != 1 or len(assignments) != 1:
            raise ValueError("One original top-level helper back-reference required: " + name)
        value = assignments[0].value
        if (
            not isinstance(value, ast.Constant)
            or (value.value is not None and not _pin(value.value))
            or value.lineno != value.end_lineno
        ):
            raise ValueError("Canonical None or SHA256 back-reference literal required: " + name)
        start = offsets[value.lineno - 1] + value.col_offset
        end = offsets[value.end_lineno - 1] + value.end_col_offset
        literal = payload[start:end]
        permitted = (
            (b"None",)
            if value.value is None
            else (
                repr(value.value).encode(),
                json.dumps(value.value).encode(),
            )
        )
        if literal not in permitted:
            raise ValueError("Plain canonical helper back-reference literal required: " + name)
        slots[name] = value.value
        spans.append((start, end))
    normalized, cursor = [], 0
    for start, end in sorted(spans):
        normalized.extend((payload[cursor:start], b"None"))
        cursor = end
    normalized.append(payload[cursor:])
    identity = hashlib.sha256(
        HELPER_BINDING_KIND.encode() + b"\0" + b"".join(normalized)
    ).hexdigest()
    return identity, tuple((name, slots[name]) for name in HELPER_BACK_REFERENCE_SLOTS)


def _check_helper_backrefs(backrefs, constructor_source, expected_review):
    """Pure binding comparison, not producer adoption or owner authentication."""
    if (
        type(backrefs) is not tuple
        or len(backrefs) != len(HELPER_BACK_REFERENCE_SLOTS)
        or any(
            type(item) is not tuple or len(item) != 2 or type(item[0]) is not str
            for item in backrefs
        )
        or tuple(item[0] for item in backrefs) != HELPER_BACK_REFERENCE_SLOTS
        or type(constructor_source) is not bytes
    ):
        raise ValueError("Exact helper back-reference roster and constructor bytes required")
    source, review = (item[1] for item in backrefs)
    if (
        not _pin(source)
        or not _pin(review)
        or not _pin(expected_review)
        or review != expected_review
        or source != hashlib.sha256(constructor_source).hexdigest()
    ):
        raise ValueError("Exact full constructor source/review back-reference required")


def _import_helper_bound(expected):
    path = _module_file(HELPER_MODULE)
    if not _pin(expected) or path.is_symlink() or not path.is_file():
        raise ValueError("Reviewed canonical helper byte binding required")
    payload = path.read_bytes()
    identity, backrefs = _helper_binding(payload)
    if identity != expected:
        raise ValueError("Exact helper source bytes outside back-reference literals changed")
    _check_helper_backrefs(backrefs, Path(__file__).read_bytes(), HELPER_CONSTRUCTION_REVIEW_SHA256)
    module = importlib.import_module(HELPER_MODULE)
    if (
        sys.modules.get(HELPER_MODULE) is not module
        or Path(module.__file__).resolve() != path
        or path.read_bytes() != payload
        or any(
            type(getattr(module, name)) is not str or getattr(module, name) != value
            for name, value in backrefs
        )
    ):
        raise ValueError("Actual helper module/back-reference or source epoch changed")
    return module


def _dependencies():
    _ready()  # Refuse before even importing an unsealed Key or stage producer.
    helpers = _import_helper_bound(HELPER_INTERFACE_SHA256)
    key = _import_bound(KEY_MODULE, KEY_SOURCE_SHA256)
    parameters = _import_bound(PARAMETER_MODULE, PARAMETER_SOURCE_SHA256)
    callbacks = _import_bound(CALLBACK_MODULE, CALLBACK_SHA256)
    stages = tuple(
        _import_bound(name, pin)
        for name, pin in zip(STAGE_MODULES, STAGE_SOURCE_SHA256, strict=True)
    )
    if key.WORLD_CONSTRUCTION_LAW != KEY_LAW:
        raise ValueError("Explicitly reviewed fresh-world construction law required")
    if any(module.WORLD_MODE != MODE for module in stages):
        raise ValueError("Exact fresh-world mode must match every original source stage")
    functions = [
        (key, "construction"),
        (key, "validate_closed_seed"),
        (parameters, "validate_completed_history"),
    ]
    functions.extend((module, name) for module in stages for name in (CONSTRUCT_HOOK, CHECK_HOOK))
    functions.extend((stages[-1], name) for name in (SEAL_HOOK, CHECK_SEAL_HOOK))
    for module, name in functions:
        fn = getattr(module, name, None)
        if type(fn) is not FunctionType or fn.__globals__ is not vars(module):
            raise ValueError("Missing actual same-claim source hook: " + name)
    return SimpleNamespace(
        helpers=helpers,
        key=key,
        parameters=parameters,
        callbacks=callbacks,
        stages=stages,
    )


def _world_voronoi_api():
    """Optional next source boundary; no reciprocal embedded source hash."""
    _ready()
    if not _pin(VORONOI_IMAGE_SOURCE_SHA256) or not _pin(VORONOI_IMAGE_REVIEW_SHA256):
        raise WorldPhaseRejected(
            "Actual reviewed same-phase Voronoi image source remains unbound",
            stage="unbound_voronoi_image_contract",
        )
    module = _import_bound(VORONOI_IMAGE_MODULE, VORONOI_IMAGE_SOURCE_SHA256)
    if module.PARENT_MODULE != HELPER_MODULE or module.MODE != VORONOI_IMAGE_MODE:
        raise ValueError("Exact same-instance Voronoi image source mode required")
    for name in ("source_plan", "prepare", "_guard", "_authority", "_wrapper_guard", "_dispatch"):
        function = getattr(module, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(module):
            raise ValueError("Original Voronoi image source interface required: " + name)
    return module


def _world_voronoi_mesh_api():
    """Optional constructor boundary; no pin grants lifecycle authority."""
    _world_voronoi_api()
    if not _pin(VORONOI_MESH_SOURCE_SHA256) or not _pin(VORONOI_MESH_REVIEW_SHA256):
        raise WorldPhaseRejected(
            "Actual reviewed same-phase constructor route remains unbound",
            stage="unbound_voronoi_mesh_contract",
        )
    module = _import_bound(VORONOI_MESH_MODULE, VORONOI_MESH_SOURCE_SHA256)
    if (
        module.PARENT_MODULE != VORONOI_IMAGE_MODULE
        or module.MODE != VORONOI_MESH_MODE
        or module.DISPATCH_LABEL != "Cells.make_voronoi"
    ):
        raise ValueError("Exact actual image-to-mesh constructor mode required")
    for name in ("source_plan", "prepare", "_guard", "_authority", "_wrapper_guard", "_dispatch"):
        function = getattr(module, name, None)
        if type(function) is not FunctionType or function.__globals__ is not vars(module):
            raise ValueError("Original constructor source interface required: " + name)
    return module


def request_record(value):
    return dict(
        law=LAW_ID,
        mode=value.mode,
        parameters=value.parameter_identity,
        callbacks=value.callback_identity,
        source=value.source_identity,
        fresh_phase_required=True,
        legacy_owner_cast=False,
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
    value = Request(
        owner,
        callback_owner,
        record.identity,
        callback.trial.identity,
        _digest(source_plan()),
        mode,
        "",
    )
    value = replace(value, identity=_digest(request_record(value)))
    _REQUESTS[value] = (record, p, callback, callback.callback, callback.trial)
    return value


def _guard(context):
    if context.entry_error is not None:
        raise context.entry_error
    if context.primary is not None:
        raise context.primary
    if context.capture_error is not None:
        raise WorldPhaseRejected(
            "Retained phase observation/sealing failure",
            stage=context.stage,
            capture_error=context.capture_error,
        )
    if (
        context.invalid
        or not context.active
        or context.thread != get_ident()
        or not _ACTIVE
        or _ACTIVE[-1] is not context
    ):
        raise WorldPhaseRejected("Unavailable world-construction epoch", stage="entry")


def _attempt(context, name, state):
    row = dict(
        sequence=len(context.work),
        stage=name,
        state=state,
        layer="coordinator",
        source_call_count_is_not_case_count=True,
    )
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
            result.extend(
                (value.__code__, value.__globals__, value.__defaults__, value.__closure__)
            )
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
    functions = (helpers._atoms, literal._surface, literal._same)
    if any(type(fn) is not FunctionType for fn in functions):
        raise ValueError("Actual Python checker helpers required before use")
    result = [helpers, literal]
    for function in functions:
        result.extend(_independent_atoms(function))
        # Both retained atom/surface helpers reach their original global
        # aliases._atoms. Authenticate that delegate without executing it.
        aliases = function.__globals__.get("aliases")
        result.append(aliases)
        if aliases is not None:
            delegate = vars(aliases).get("_atoms")
            if type(delegate) is not FunctionType:
                raise ValueError("Original aliases atom delegate required")
            result.extend(_independent_atoms(delegate))
        descriptor = function.__globals__.get("_Descriptor")
        result.append(descriptor)
        if descriptor is not None:
            result.extend((type(descriptor), descriptor.__mro__))
    comparator = literal._same
    namespace, builtins = comparator.__globals__, comparator.__builtins__
    if type(builtins) is not dict:
        raise ValueError("Actual comparator builtin namespace required")
    result.append(builtins)
    for name in ("len", "any", "zip", "ValueError"):
        origin = namespace if name in namespace else builtins
        value = origin[name]
        result.extend((name, origin, *_independent_atoms(value)))
    return tuple(result)


def _check_helpers(context):
    actual, retained = _helper_authority(context.api), context.helper_authority
    if len(actual) != len(retained) or any(
        a is not b for a, b in zip(actual, retained, strict=True)
    ):
        raise ValueError("Original checker/atom/surface helper identity or code changed")


def _compare_bindings(context):
    _check_helpers(context)
    actual = _bindings(context)
    _check_helpers(context)
    if len(actual) != len(context.bindings) or any(
        a is not b for a, b in zip(actual, context.bindings, strict=True)
    ):
        raise ValueError("Independent coordinator binding identity changed")
    context.api.helpers.literal._same(actual, context.bindings)


def _bindings(context):
    _check_helpers(context)  # Independently BEFORE the first helper invocation.
    api = context.api
    functions = [
        _digest,
        source_plan,
        _pin,
        _ready,
        _module_file,
        _import_bound,
        _helper_binding,
        _check_helper_backrefs,
        _import_helper_bound,
        _dependencies,
        _world_voronoi_api,
        _world_voronoi_mesh_api,
        request_record,
        from_world_ready,
        _retain_failure,
        _guard,
        _attempt,
        _independent_atoms,
        _helper_authority,
        _check_helpers,
        _compare_bindings,
        _bindings,
        _check_bindings,
        _same_dependencies,
        _construction_entry,
        _reject_validation,
        _reserve_validation,
        _validation_check,
        _release_validation,
        _validation_scope,
        _closed_lineage,
        _validate_reserved,
        _active_claim,
        _evidence_fields,
        _check_evidence,
        _step,
        _trial_record,
        _seal_active,
        _coordinate,
        _closed,
        _partial,
        _validate,
        prepare,
        api.key.construction,
        api.key.validate_closed_seed,
        api.parameters.validate_completed_history,
        api.key.WorldConstructionClaim.parameters.fget,
        api.key.WorldConstructionClaim.check,
        api.key.WorldConstructionClaim.record.fget,
        api.callbacks._validate,
        _world_reject,
        _world_parameter_authority,
        _world_stage_begin,
        _world_objects,
        _world_projector,
        _world_state,
        _world_cells_omissions,
        _world_live_aliases,
        _world_stage_runtime,
        _world_stage_guard,
        _world_stage_finish,
        _world_stage_check,
        _world_observation_atoms,
        _world_capture_locals,
        _world_admit_body,
        _world_body_scope,
        _world_body_scope.__wrapped__,
        _world_observer_atoms,
        _world_cache_extensions,
        _world_tail_module,
        _world_tail_route,
        _world_phase_wrapper_guard,
        _world_seal,
        _world_check_seal,
        _world_forwarded,
        _world_has_prefix_route,
        _world_prefix_route,
        _world_parent,
        _world_claim_prefix,
        _world_after_prefix_claim,
    ]
    functions.extend(
        getattr(module, name) for module in api.stages for name in (CONSTRUCT_HOOK, CHECK_HOOK)
    )
    functions.extend(getattr(api.stages[-1], name) for name in (SEAL_HOOK, CHECK_SEAL_HOOK))
    return (
        _REQUESTS,
        _CONSUMED,
        _CLAIMED,
        _ISSUED,
        _FORWARDED,
        _ACTIVE,
        _LOCK,
        _VALIDATION,
        LAW_ID,
        MODE,
        RELEASE,
        STAGES,
        STAGE_MODULES,
        BASE_FIELDS,
        MAX_WORK,
        KEY_MODULE,
        KEY_LAW,
        KEY_ERROR_ATTRIBUTE,
        PARAMETER_MODULE,
        KEY_SOURCE_SHA256,
        KEY_REVIEW_SHA256,
        PARAMETER_SOURCE_SHA256,
        PARAMETER_REVIEW_SHA256,
        STAGE_SOURCE_SHA256,
        STAGE_REVIEW_SHA256,
        HELPER_MODULE,
        HELPER_INTERFACE_SHA256,
        HELPER_CONSTRUCTION_REVIEW_SHA256,
        HELPER_BINDING_KIND,
        HELPER_BACK_REFERENCE_SLOTS,
        VORONOI_IMAGE_MODULE,
        VORONOI_IMAGE_MODE,
        VORONOI_IMAGE_SOURCE_SHA256,
        VORONOI_IMAGE_REVIEW_SHA256,
        VORONOI_MESH_MODULE,
        VORONOI_MESH_MODE,
        VORONOI_MESH_SOURCE_SHA256,
        VORONOI_MESH_REVIEW_SHA256,
        CONSTRUCT_HOOK,
        CHECK_HOOK,
        SEAL_HOOK,
        CHECK_SEAL_HOOK,
        context.helper_authority,
        api.helpers,
        api.key,
        api.parameters,
        api.callbacks,
        *api.stages,
        *(atom for module in api.stages for atom in (module.WORLD_MODE, module._WORLD)),
        api.key.WorldConstructionClaim,
        api.key.ClosedSeedRecord,
        api.parameters.WorldReadyParametersOwner,
        *(
            atom
            for cls in (Request, StageEvidence, PhaseSeal, Trial, SourceStageTrial, WorldPhaseOwner)
            for atom in api.helpers.literal._surface(cls)
        ),
        *(atom for fn in functions for atom in api.helpers._atoms(fn)),
    )


def _check_bindings(context):
    _guard(context)
    _same_dependencies(context)
    _compare_bindings(context)
    callback = context.api.callbacks._validate(context.request.callbacks)
    if (
        callback is not context.parents[2]
        or callback.callback is not context.parents[3]
        or callback.trial is not context.parents[4]
    ):
        raise ValueError("Original issued prepared callback changed")
    if (
        _REQUESTS.get(context.request) is not context.parents
        or _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.world_parameters) is not context
        or _digest(source_plan()) != context.request.source_identity
        or _digest(request_record(context.request)) != context.request.identity
    ):
        raise ValueError("Original request/source/one-shot ancestry changed")


def _same_dependencies(context):
    actual = _dependencies()
    if (
        any(
            getattr(actual, name) is not getattr(context.api, name)
            for name in ("helpers", "key", "parameters", "callbacks")
        )
        or len(actual.stages) != len(context.api.stages)
        or any(a is not b for a, b in zip(actual.stages, context.api.stages, strict=True))
    ):
        raise ValueError("Actual reviewed producer/module identity changed")


def _active_claim(context):
    _check_bindings(context)
    if type(context.claim) is not context.api.key.WorldConstructionClaim:
        raise ValueError("Actual same active WorldConstructionClaim required")
    context.claim.check()
    if context.claim.parameters is not context.p or context.p is not context.parents[1]:
        raise ValueError("Original world-ready claim/p association changed")


def _evidence_fields(index, *, final_active=False, closed=False):
    """Field epoch declaration only; flags cannot authenticate a live claim."""
    if (
        type(index) is not int
        or not 0 <= index < len(STAGES)
        or type(final_active) is not bool
        or type(closed) is not bool
        or (final_active and closed)
    ):
        raise ValueError("One exact immediate, completed-active or closed field epoch required")
    reached = len(STAGES) - 1 if final_active or closed else index
    return (
        *BASE_FIELDS,
        *(("cache",) if reached >= 1 else ()),
        *(("dyna",) if reached >= 2 else ()),
        *(("export_dirname",) if reached == 3 else ()),
    )


def _check_evidence(context, evidence, index, *, closed_record=None, final_active=False):
    names = _evidence_fields(index, final_active=final_active, closed=closed_record is not None)
    if final_active:
        caller = sys._getframe(1)
        if (
            caller.f_code is not _world_seal.__code__
            or caller.f_locals.get("transition") is not context
            or context.stage != "phase_sealing_inside_claim"
            or context.executing is not None
            or context.parameter_record is not None
            or len(context.evidence) != len(STAGES)
            or context.evidence[index] is not evidence
        ):
            raise ValueError("Completed active epoch is reserved for the actual full-phase seal")
        _active_claim(context)
        _guard(context)
    if type(evidence) is not StageEvidence or evidence.stage != STAGES[index]:
        raise ValueError("Actual exact stage evidence required")
    predecessor = None if index == 0 else context.evidence[index - 1]
    module = context.api.stages[index]
    actual = getattr(module, CHECK_HOOK)(
        evidence,
        transition=context,
        world_owner=context.request.world_parameters,
        construction_claim=context.claim,
        predecessor=predecessor,
        closed_record=closed_record,
    )
    if actual is not evidence or evidence.parameters is not context.p:
        raise ValueError("Original stage issuer/p/evidence reference changed")
    phase = evidence.phase
    fields = vars(phase)
    # Historical witnesses keep their original objects. Only the actual
    # in-claim seal or successful closed validation sees the final field epoch.
    completed = final_active or closed_record is not None
    reached = len(STAGES) - 1 if completed else index
    if tuple(fields) != names:
        raise ValueError("Original constructor stage field order changed")
    pairs = (
        (fields["p"], context.p),
        (fields["callbacks"], context.parents[3]),
        (fields["cells"], evidence.cells),
        (fields["sim"], evidence.sim),
        (evidence.callbacks, context.parents[3]),
        (fields["kind"], evidence.kind),
    )
    if any(a is not b for a, b in pairs):
        raise ValueError("Actual same-phase constructor aliases changed")
    if index:
        first = context.evidence[0]
        if (
            phase is not first.phase
            or evidence.cells is not first.cells
            or evidence.sim is not first.sim
            or evidence.kind is not first.kind
        ):
            raise ValueError("Stage substituted an already constructed phase/Cells/Simulator")
    cache = evidence.cache if index >= 1 else context.evidence[1].cache if completed else None
    handler = evidence.handler if index >= 2 else context.evidence[2].handler if completed else None
    if reached >= 1 and fields["cache"] is not cache:
        raise ValueError("Actual phase-cache assignment changed")
    if reached >= 2 and fields["dyna"] is not handler:
        raise ValueError("Actual fresh same-parameter handler assignment changed")
    if index > 1 and evidence.cache is not context.evidence[1].cache:
        raise ValueError("Original actual cache object was replaced")
    if index > 2 and evidence.handler is not context.evidence[2].handler:
        raise ValueError("Original actual TissueHandler was replaced")
    if reached == 3:
        if (
            vars(context.p).get("_run_sim") is not False
            or vars(evidence.sim).get("dyna") is not handler
            or fields["export_dirname"] is not vars(context.p)["init_export_dirname"]
        ):
            raise ValueError("Original SEED constructor-tail stores changed")
    elif "_run_sim" in vars(context.p):
        raise ValueError("SEED flag appeared before its literal tail")
    return evidence


def _step(context, index):
    caller = sys._getframe(1)
    ticket = context.dispatch_ticket
    valid = (
        ticket is not None
        and ticket[0] == index
        and ticket[1] is caller
        and caller is context.driver_frame
        and context.executing is None
        and index == len(context.evidence)
        and not context.invalid
    )
    if not valid:
        context.invalid = True
        if context.entry_error is None:
            context.entry_error = WorldPhaseRejected(
                "Repeated/reentrant/out-of-order stage", stage="entry"
            )
        try:
            row = _attempt(context, STAGES[index], "rejected")
        except BaseException as capture:
            context.capture_errors = (
                *context.capture_errors,
                ("rejected_stage_attempt", capture, context.entry_error),
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
            context,
            world_owner=context.request.world_parameters,
            construction_claim=context.claim,
            callback_owner=context.request.callbacks,
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
        tail,
        transition=context,
        world_owner=context.request.world_parameters,
        construction_claim=context.claim,
        stages=tuple(context.evidence),
    )
    context.raw_seal = seal
    if (
        type(seal) is not PhaseSeal
        or seal.evidence is not tail
        or seal.phase is not tail.phase
        or seal.parameters is not context.p
        or len(seal.stages) != len(context.evidence)
        or any(a is not b for a, b in zip(seal.stages, context.evidence, strict=True))
    ):
        raise ValueError("Actual full-phase source seal required")
    actual = getattr(context.api.stages[-1], CHECK_SEAL_HOOK)(
        seal,
        transition=context,
        world_owner=context.request.world_parameters,
        construction_claim=context.claim,
        closed_record=None,
    )
    if actual is not seal:
        raise ValueError("Actual in-claim phase seal reference changed")
    context.seal = seal
    row["state"] = "phase_capture_returned"
    # All fallible capture/digest/Trial creation is inside the ACTIVE claim.
    trial = Trial(
        context.request.identity,
        MODE,
        seal.identity,
        tuple(value.identity for value in context.evidence),
        tuple(value.trial for value in context.evidence),
        tuple(value.work for value in context.evidence),
        tuple(
            (item["sequence"], item["stage"], item["state"], item["layer"]) for item in context.work
        ),
        "",
    )
    identity = _digest(_trial_record(trial))
    context.trial = replace(trial, identity=identity)
    _active_claim(context)


def _trial_record(value):
    return dict(
        request=value.request_identity,
        mode=value.mode,
        phase=value.phase_identity,
        stages=value.stage_identities,
        coordinator_work=value.coordinator_work,
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
    if (
        type(record) is not context.api.key.ClosedSeedRecord
        or context.claim.record is not record
        or record is not context.parameter_record
        or record.succeeded is not True
        or record.primary_error_present is not False
        or record.seed_flag_created is not True
        or record.parameter_load_identity != context.parents[0].identity
        or record.secondary_error_stages
    ):
        raise ValueError("Exact successful closed WorldReady owner/claim/record required")
    if validation is not None:
        _validation_check(validation)
    for index, evidence in enumerate(context.evidence):
        _check_evidence(context, evidence, index, closed_record=record)
        if validation is not None:
            _validation_check(validation)
    if (
        getattr(context.api.stages[-1], CHECK_SEAL_HOOK)(
            context.seal,
            transition=context,
            world_owner=context.request.world_parameters,
            construction_claim=context.claim,
            closed_record=record,
        )
        is not context.seal
    ):
        raise ValueError("Retained whole-phase source seal changed")
    if validation is not None:
        _validation_check(validation)
    trial = context.trial
    if (
        type(trial) is not Trial
        or trial.request_identity != context.request.identity
        or trial.mode != MODE
        or trial.phase_identity != context.seal.identity
        or trial.stage_identities != tuple(value.identity for value in context.evidence)
        or _digest(_trial_record(trial)) != trial.identity
        or len(trial.stage_trials) != len(context.evidence)
        or any(a is not b.trial for a, b in zip(trial.stage_trials, context.evidence, strict=True))
        or any(a is not b.work for a, b in zip(trial.stage_work, context.evidence, strict=True))
    ):
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
                        *context.capture_errors,
                        ("stage_failure_recording", capture, error),
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
                    *context.capture_errors,
                    ("claim_failure_recording", capture, error),
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
                *context.capture_errors,
                ("parameter_claim_failure_evidence", capture, error),
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
                    *context.capture_errors,
                    ("closed_parameter_record", capture, context.claim),
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
            *context.capture_errors,
            ("stage_error_attributes", observation, error),
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
    if (
        context.primary is None
        and primary is None
        and capture is None
        and error is not context.capture_error
    ):
        context.primary = error


def _partial(context):
    return dict(
        context=context,
        request=context.request,
        original_world_owner=context.request.world_parameters,
        original_parameter_record=context.parents[0],
        parameters=context.p,
        actual_claim=context.claim,
        closed_parameter_record=context.parameter_record,
        retained_stage_evidence=context.evidence,
        last_raw_stage_return=context.last_returned,
        raw_phase_seal=context.raw_seal,
        phase_seal=context.seal,
        trial=context.trial,
        coordinator_work=context.work,
        primary=context.primary,
        entry_error=context.entry_error,
        driver_frame=context.driver_frame,
        current_step_frame=context.step_frame,
        pending_dispatch_ticket=context.dispatch_ticket,
        capture_errors=context.capture_errors,
        claim_errors=context.claim_errors,
        failed_stages=context.failed_stages,
        stage_partials=context.stage_partials,
        failed_claim=context.failed_claim,
        failed_claim_partial=context.failed_claim_partial,
        usable_child_available=False,
        complete_raw_serialization_claimed=False,
        last_validation=getattr(context, "last_validation", None),
        validation_failures=getattr(context, "validation_failures", ()),
    )


def _reject_validation(reservation, kind, other=None):
    reservation.invalid = True
    reservation.context.invalid = True
    row = (kind, other)
    if len(reservation.attempts) < MAX_WORK:
        reservation.attempts = (*reservation.attempts, row)
    else:
        reservation.overflow_attempt = row
    raise reservation.rejection


def _world_reject(transition, reason, context=None):
    transition.invalid = True
    if context is not None:
        context.invalid = True
    if transition.entry_error is None:
        original = None if context is None else getattr(context, "entry_error", None)
        transition.entry_error = (
            original
            if original is not None
            else WorldPhaseRejected(reason, stage="world_stage_entry", partial=context)
        )
    if context is not None and getattr(context, "entry_error", None) is None:
        context.entry_error = transition.entry_error
    raise transition.entry_error


def _world_parameter_authority(transition):
    """Use the one actual claim, never an old owner/Lease numeric validator."""
    if (
        type(transition.request) is not Request
        or type(transition.request.mode) is not str
        or transition.request.mode != MODE
    ):
        _world_reject(transition, "Original explicit fresh-world request mode changed")
    if transition.parameter_record is None:
        _active_claim(transition)
        _guard(transition)
    else:
        _same_dependencies(transition)
        _compare_bindings(transition)
        callback = transition.api.callbacks._validate(transition.request.callbacks)
        if (
            callback is not transition.parents[2]
            or callback.callback is not transition.parents[3]
            or callback.trial is not transition.parents[4]
        ):
            _world_reject(transition, "Original prepared callback ancestry changed")
        record = transition.api.key.validate_closed_seed(
            transition.claim, original_owner=transition.request.world_parameters
        )
        if (
            record is not transition.parameter_record
            or transition.claim.record is not record
            or record.succeeded is not True
            or record.primary_error_present is not False
            or record.seed_flag_created is not True
            or record.secondary_error_stages
            or record.parameter_load_identity != transition.parents[0].identity
        ):
            _world_reject(transition, "Original successful closed world claim changed")
        if transition.invalid:
            if transition.entry_error is not None:
                raise transition.entry_error
            raise WorldPhaseRejected(
                "Closed world authority was poisoned by an observer", stage="world_entry"
            )


def _world_stage_begin(
    module, index, transition, world_owner, claim, callback_owner, predecessor, frame
):
    """A private stage witness, not a new public owner or a closed claim."""
    _ready()  # Explicit refusal before any unadopted object/claim is inspected.
    if (
        type(transition.request) is not Request
        or _CONSUMED.get(transition.request) is not transition
        or _CLAIMED.get(world_owner) is not transition
        or world_owner is not transition.request.world_parameters
        or claim is not transition.claim
        or callback_owner is not transition.request.callbacks
        or transition.executing != index
        or transition.api.stages[index] is not module
        or frame.f_code is not getattr(module, CONSTRUCT_HOOK).__code__
        or frame.f_back is not transition.step_frame
        or transition.step_frame.f_code is not _step.__code__
        or predecessor is not (None if index == 0 else transition.evidence[index - 1])
    ):
        _world_reject(transition, "Unclaimed/reentrant fresh-world stage")
    _world_parameter_authority(transition)
    with module._LOCK:
        if module._ACTIVE or transition.request in module._WORLD:
            _world_reject(transition, "Fresh-world stage epoch was already attempted")
        context = SimpleNamespace(
            world_mode=MODE,
            world_transition=transition,
            world_module=module,
            world_index=index,
            world_predecessor=predecessor,
            world_ticket=(
                transition,
                world_owner,
                claim,
                callback_owner,
                transition.p,
                predecessor,
            ),
            request=transition.request,
            p=transition.p,
            thread=get_ident(),
            active=True,
            invalid=False,
            stage=STAGES[index],
            parent=None if predecessor is None else predecessor.authority,
            phase=None if predecessor is None else predecessor.phase,
            callback=transition.parents[3],
            callback_parent=transition.parents[2],
            objects=[],
            runtime_types={},
            runtime_bindings={},
            events=[],
            work=[],
            locals={},
            observation_error=None,
            observation_errors=(),
            observation_origin=None,
            observation_raw=None,
            graph_view=SimpleNamespace(),
            graph_fields=[],
            world_views={},
            world_proxy_roots={},
            completed=False,
            entry_error=None,
            primary=None,
            capture_error=None,
            trial=None,
            evidence=None,
        )
        context.tape = SimpleNamespace(
            rng=None, events=context.events, draws=(), locals=context.locals
        )
        context.world_stable_tape = SimpleNamespace(rng=None, events=(), draws=(), locals=())
        if not hasattr(transition, "world_roots"):
            transition.world_roots = [
                ("parameters", transition.p),
                ("callback", transition.parents[3]),
            ]
            transition.world_root_tokens = (transition.world_roots, tuple(transition.world_roots))
        # Publication precedes any source/observer call and is never undone.
        module._WORLD[transition.request] = context
        module._ACTIVE.append(context)
        transition.stage_partials = (*transition.stage_partials, (STAGES[index], context))
        try:
            context.world_plan = module.source_plan(mode=MODE)
            context.world_source_files = {
                str(path): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in (
                    Path(module.source.__file__),
                    transition.api.helpers.aliases.NATIVE / "betse/science/phase/phasecls.py",
                )
            }
            context.world_base_objects = _world_objects(transition, index - 1)
            context.world_before, context.world_before_graph = _world_state(context, baseline=True)
            context.bindings = module._bindings()
        except BaseException as error:
            context.capture_error = error
            context.invalid = transition.invalid = True
            context.active = False
            if module._ACTIVE and module._ACTIVE[-1] is context:
                module._ACTIVE.pop()
            raise WorldPhaseRejected(
                "Fresh-world baseline capture failed",
                stage="capture",
                partial=context,
                capture_error=error,
            ) from error
        return context


def _world_objects(transition, index):
    result, seen = [], set()
    roots, pairs = transition.world_root_tokens
    if (
        transition.world_roots is not roots
        or len(roots) != 2
        or len(pairs) != 2
        or any(a is not b for a, b in zip(roots, pairs, strict=True))
        or any(type(pair) is not tuple or len(pair) != 2 for pair in pairs)
        or pairs[0][0] != "parameters"
        or pairs[0][1] is not transition.p
        or pairs[1][0] != "callback"
        or pairs[1][1] is not transition.parents[3]
    ):
        _world_reject(transition, "Original parameter/callback root references changed")
    candidates = list(transition.world_roots)
    for module in transition.api.stages[: index + 1]:
        context = module._WORLD.get(transition.request)
        if context is not None:
            candidates.extend(context.objects)
    for pair in candidates:
        if id(pair[1]) not in seen:
            seen.add(id(pair[1]))
            result.append(pair)
    return result


def _world_projector(context):
    transition = context.world_transition
    objects = _world_objects(transition, context.world_index)
    for module in transition.api.stages[: context.world_index + 1]:
        owner = module._WORLD.get(transition.request)
        for _, proxy in getattr(owner, "proxy_returns", ()):
            context.world_proxy_roots.setdefault(id(proxy), ("weak_phase_proxy", proxy))
    return SimpleNamespace(objects=[*objects, *context.world_proxy_roots.values()])


def _world_state(context, *, baseline=False):
    """Stable holder maps exclude only the still-unreached literal stores."""
    transition, index = context.world_transition, context.world_index
    first = transition.api.stages[0]._WORLD.get(transition.request)
    phase = None if first is None else first.phase
    sim = None if phase is None else vars(phase).get("sim")
    cells = None if phase is None else vars(phase).get("cells")
    forwarded = _world_forwarded(transition)
    objects = context.world_base_objects if baseline else _world_objects(transition, index)
    view = context.world_views.setdefault(
        "baseline" if baseline else "sealed", SimpleNamespace(objects=[], fields=[])
    )
    view.objects[:] = objects
    while len(view.fields) < len(objects):
        view.fields.append({})
    if len(view.fields) != len(objects):
        raise ValueError("Original fresh-world object roster shrank")
    projector = _world_projector(context)
    rows = []
    for fields, (role, actual) in zip(view.fields, objects, strict=True):
        omitted = set()
        if actual is phase:
            omitted.update(
                name
                for at, name in ((1, "cache"), (2, "dyna"), (3, "export_dirname"))
                if at > index or (baseline and at == index)
            )
        if actual is sim and (index < 3 or baseline):
            omitted.add("dyna")
        if forwarded is not None and actual is cells:
            omitted.update(_world_cells_omissions(transition, cells))
        fields.clear()
        # Parameter bytes/edges belong to Key's actual active/closed checker.
        # The stage captures its actual parameter reference and permitted flag.
        if actual is transition.p:
            fields["parameter_identity"] = transition.request.parameter_identity
            if index == 3 and not baseline:
                fields["_run_sim"] = vars(actual).get("_run_sim")
        elif actual is transition.parents[3]:
            fields["callback_identity"] = transition.request.callback_identity
        else:
            fields.update((k, v) for k, v in vars(actual).items() if k not in omitted)
        rows.append(
            dict(role=role, fields=transition.api.helpers.literal._project(projector, fields))
        )
    cache = transition.api.helpers.core.caches.snapshot(rows)
    graph = transition.api.helpers.literal.callers._graph(view, view, context.world_stable_tape)
    return cache, graph


def _world_cells_omissions(transition, cells):
    """Only downstream stores owned by authenticated typed retirement links."""
    prefix = _world_forwarded(transition)
    if prefix is None:
        return ()
    if prefix.cells is not cells or prefix.phase.cells is not cells:
        _world_reject(transition, "Foreign caller in forwarded field projection")
    omitted = tuple(transition.api.helpers.STORES)
    if hasattr(prefix, "voronoi_image"):
        parent = transition.api.helpers._voronoi_route(prefix)
        if hasattr(parent, "voronoi_mesh"):
            route = _world_voronoi_api()._mesh_route(parent)
            if (
                route.cells is not cells
                or route.phase is not prefix.phase
                or route.p is not transition.p
            ):
                _world_reject(transition, "Foreign caller in constructor projection")
            omitted += ("mesh",)
    return omitted


def _world_live_aliases(transition):
    prefix = transition.api.stages[0]._WORLD[transition.request]
    if prefix.phase is None:
        return
    fields = vars(prefix.phase)
    expected = BASE_FIELDS + ("cache", "dyna", "export_dirname")
    if tuple(fields) != expected[: len(fields)]:
        _world_reject(transition, "Original fresh constructor field order changed", prefix)
    pairs = dict(
        callbacks=prefix.callback,
        cells=prefix.constructed.get("Cells"),
        kind=getattr(prefix, "kind", None),
        p=transition.p,
        sim=prefix.constructed.get("Simulator"),
    )
    for name, actual in pairs.items():
        if name in fields and fields[name] is not actual:
            _world_reject(transition, "Original constructor alias changed: " + name, prefix)
    if "cache" in fields:
        cache = transition.api.stages[1]._WORLD.get(transition.request)
        if (
            cache is None
            or fields["cache"] is not cache.constructed.get("SimPhaseCaches")
            or not cache.factory_returns
            or cache.factory_returns[-1] != "SimPhaseCaches"
        ):
            _world_reject(transition, "Actual completed cache assignment changed", cache)
    if "dyna" in fields:
        dyna = transition.api.stages[2]._WORLD.get(transition.request)
        if dyna is None or not dyna.constructor_completed or fields["dyna"] is not dyna.handler:
            _world_reject(transition, "Actual completed handler assignment changed", dyna)
    if "export_dirname" in fields and (
        fields["export_dirname"] is not vars(transition.p)["init_export_dirname"]
        or vars(transition.p).get("_run_sim") is not False
    ):
        _world_reject(transition, "Original literal SEED export/flag changed")
    tail = transition.api.stages[-1]._WORLD.get(transition.request)
    if (
        tail is not None
        and getattr(tail, "world_route_issued", False)
        and (
            getattr(prefix, "world_tail", None) is not tail
            or transition.api.stages[0]._TAIL_ROUTES.get(prefix.phase) is not tail
        )
    ):
        _world_reject(transition, "Original same-instance SEED route registry edge changed", tail)


def _world_stage_runtime(context):
    transition, module, index = context.world_transition, context.world_module, context.world_index
    if (
        context.world_mode != MODE
        or context.invalid
        or transition.invalid
        or context.thread != get_ident()
        or transition.thread != context.thread
        or module is not transition.api.stages[index]
        or module._WORLD.get(transition.request) is not context
        or _CONSUMED.get(transition.request) is not transition
        or _CLAIMED.get(transition.request.world_parameters) is not transition
        or context.parent is not (None if index == 0 else context.world_predecessor.authority)
        or any(
            a is not b
            for a, b in zip(
                context.world_ticket,
                (
                    transition,
                    transition.request.world_parameters,
                    transition.claim,
                    transition.request.callbacks,
                    transition.p,
                    context.world_predecessor,
                ),
                strict=True,
            )
        )
    ):
        _world_reject(transition, "Fresh-world stage/claim ancestry changed", context)
    _world_parameter_authority(transition)
    _world_live_aliases(transition)
    for filename, expected in context.world_source_files.items():
        path = Path(filename)
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            _world_reject(transition, "Literal/native source correspondence bytes changed", context)
    literal = transition.api.helpers.literal
    literal._same(module._bindings(), context.bindings)
    if context.parent is not None:
        _world_stage_runtime(context.parent)
    if hasattr(context, "native_bindings"):
        literal._same(module._native_bindings(context), context.native_bindings)
    for attribute, function in (
        ("scope_bindings", "_scope_bindings"),
        ("namespace_bindings", "_namespace_bindings"),
    ):
        if hasattr(context, attribute):
            retained = getattr(context, attribute)
            actual = getattr(module, function)(context)
            literal._same(actual[: len(retained)], retained)
    for role, cls in context.runtime_types.items():
        surface = (
            module._surface(cls)
            if hasattr(module, "_surface")
            else transition.api.stages[0]._surface(cls)
        )
        literal._same(surface, context.runtime_bindings[role])
    if index < 3:
        for position, (role, actual) in enumerate(context.objects):
            issued = module._OBJECTS.get(actual)
            if index == 1:
                if (
                    issued is not context.object_issuance[position]
                    or issued[0] is not context
                    or issued[1] != role
                ):
                    _world_reject(
                        transition, "Original cache (context, role) tuple changed", context
                    )
            elif issued is not context:
                _world_reject(transition, "Original fresh native object issuance changed", context)
    if hasattr(context, "modules"):
        aliases = transition.api.helpers.aliases
        aliases._check_modules()
        current = aliases._module_records()
        for name, old in context.modules.items():
            now = current.get(name)
            if type(now) is not tuple or now[0] is not old[0] or now[1:] != old[1:]:
                _world_reject(transition, "Original native module changed", context)
    current, graph = _world_state(context, baseline=True)
    literal._same(graph[0], context.world_before_graph[0])
    if (
        current.identity != context.world_before.identity
        or graph[1] != context.world_before_graph[1]
    ):
        _world_reject(
            transition, "Inherited fields/reference edges outside the stage changed", context
        )
    if hasattr(context, "world_observations"):
        literal._same(_world_observation_atoms(context), context.world_observations)
    if hasattr(context, "world_observer_bindings"):
        literal._same(_world_observer_atoms(context), context.world_observer_bindings)
    if context.evidence is not None and not context.active:
        sealed, graph = _world_state(context)
        literal._same(graph[0], context.world_graph[0])
        if sealed.identity != context.trial.cache.identity or graph[1] != context.world_graph[1]:
            _world_reject(transition, "Retained source stage changed before continuation", context)


def _world_stage_guard(context):
    transition, module = context.world_transition, context.world_module
    if context.entry_error is not None:
        transition.invalid = True
        if transition.entry_error is None:
            transition.entry_error = context.entry_error
        raise context.entry_error
    if (
        context.entry_error is not None
        or context.invalid
        or transition.invalid
        or not context.active
        or not module._ACTIVE
        or module._ACTIVE[-1] is not context
        or transition.executing != context.world_index
        or context.thread != get_ident()
    ):
        _world_reject(transition, "Raw fresh-world source entry is unavailable", context)
    _world_parameter_authority(transition)
    module = transition.api.stages[2].handler
    module._stop(context)


def _world_stage_finish(context, primary=None):
    transition, module = context.world_transition, context.world_module
    if context.entry_error is not None:
        primary = context.entry_error
        if transition.entry_error is None:
            transition.entry_error = primary
    context.primary = primary
    try:
        if primary is not None or context.observation_error is not None:
            raise WorldPhaseRejected(
                "Original fresh-world source stage failed",
                stage=context.stage,
                partial=context,
                source_error=primary,
                capture_error=context.observation_error,
            ) from (primary if primary is not None else context.observation_error)
        _world_stage_runtime(context)
        cache, graph = _world_state(context)
        document = dict(
            mode=MODE,
            stage=STAGES[context.world_index],
            cache=cache.identity,
            events=tuple(name for name, _ in context.events),
            work=tuple(context.work),
        )
        context.trial = SourceStageTrial(
            MODE, document["stage"], cache, document["events"], document["work"], _digest(document)
        )
        context.world_graph = graph
        context.world_observations = _world_observation_atoms(context)
        first = transition.api.stages[0]._WORLD[transition.request]
        phase = first.phase
        value = StageEvidence(
            STAGES[context.world_index],
            context,
            phase,
            context.p,
            phase.cells,
            phase.sim,
            phase.callbacks,
            phase.kind,
            vars(phase).get("cache"),
            vars(phase).get("dyna"),
            context.trial,
            context.trial.work,
            context.trial.identity,
        )
        context.evidence = value
        return value
    except BaseException as error:
        context.invalid = transition.invalid = True
        if primary is None and context.observation_error is None:
            context.capture_error = error
            raise WorldPhaseRejected(
                "Fresh-world stage sealing failed",
                stage="capture",
                partial=context,
                capture_error=error,
            ) from error
        raise
    finally:
        context.active = False
        if module._ACTIVE and module._ACTIVE[-1] is context:
            module._ACTIVE.pop()
        else:
            context.invalid = transition.invalid = True


def _world_stage_check(
    module, evidence, transition, world_owner, claim, predecessor, closed_record
):
    _ready()
    context = module._WORLD.get(transition.request)
    if (
        type(evidence) is not StageEvidence
        or context is None
        or context.evidence is not evidence
        or evidence.authority is not context
        or context.world_transition is not transition
        or context.world_predecessor is not predecessor
        or world_owner is not transition.request.world_parameters
        or claim is not transition.claim
        or closed_record is not transition.parameter_record
        or context.active
        or context.trial is not evidence.trial
    ):
        _world_reject(transition, "Unissued/replaced fresh-world stage witness", context)
    _world_stage_runtime(context)
    cache, graph = _world_state(context)
    literal = transition.api.helpers.literal
    literal._same(graph[0], context.world_graph[0])
    if (
        cache.identity != context.trial.cache.identity
        or graph[1] != context.world_graph[1]
        or evidence.identity != context.trial.identity
    ):
        _world_reject(transition, "Sealed fresh-world stage state/reference edges changed", context)
    document = dict(
        mode=MODE,
        stage=STAGES[context.world_index],
        cache=cache.identity,
        events=context.trial.events,
        work=context.trial.work,
    )
    if _digest(document) != context.trial.identity:
        _world_reject(transition, "Original fresh-world stage trial changed", context)
    return evidence


def _world_observation_atoms(context):
    """Retain completed observation containers without traversing lifecycle locals."""
    atoms = [context.events, context.locals, context.work]
    for row in context.events:
        atoms.extend((row, *row))
    for key, fields in context.locals.items():
        atoms.extend((key, fields))
        for name, value in fields.items():
            atoms.extend((name, value))
    for row in context.work:
        atoms.append(row)
        for name, value in row.items():
            atoms.extend((name, value))
    return tuple(atoms)


def _world_capture_locals(context, frame, event):
    context.locals[(frame.f_code.co_filename, frame.f_code.co_qualname)] = dict(frame.f_locals)


def _world_admit_body(context, frame):
    old = context.admitted_frames.get(id(frame))
    if old is not None and old["frame"] is frame:
        return old
    module, index = context.world_module, context.world_index
    method = next(
        (name for name, fn in context.bodies.items() if fn.__code__ is frame.f_code), None
    )
    row = dict(
        sequence=len(context.work),
        layer="fresh_world_literal_admission",
        phase=context.stage,
        method=method,
        admission="pending",
        body_started=False,
        entry_is_case=False,
    )
    attempt = dict(frame=frame, method=method, work=row, status="attempted", body_started=False)
    context.work.append(row)
    context.last_body_attempt = attempt
    parent = frame.f_back
    valid = (
        context.active
        and not context.invalid
        and method is not None
        and len(context.work) <= 100000
    )
    if method in ("prefix", "attach"):
        valid = (
            valid
            and not context.world_root_claimed
            and parent is context.driver_frame
            and frame.f_locals.get("self") is context.phase
        )
        if method == "prefix":
            valid = (
                valid
                and frame.f_locals.get("p") is context.p
                and frame.f_locals.get("callbacks") is context.callback
                and frame.f_locals.get("kind") is context.kind
            )
    elif index == 1 and method == "proxy":
        valid = (
            valid
            and parent is not None
            and parent.f_code is module._proxy.__code__
            and parent.f_locals.get("context") is context
        )
    elif index == 1:
        valid = (
            valid
            and parent is not None
            and parent.f_code is module._body_call.__code__
            and parent.f_locals.get("context") is context
            and parent.f_locals.get("delegate") is context.bodies[method]
            and parent.f_locals.get("actual") is frame.f_locals.get("self")
        )
    else:
        valid = False
    if not valid:
        row["admission"] = attempt["status"] = "rejected"
        _world_reject(
            context.world_transition, "Unclaimed/reentrant fresh-world literal body", context
        )
    if method in ("prefix", "attach"):
        context.world_root_claimed = True
    row["admission"] = attempt["status"] = "claimed"
    context.admitted_frames[id(frame)] = attempt
    return attempt


@contextmanager
def _world_body_scope(context):
    """Reuse protected dual-hook admission for the prefix/cache body roots."""
    _ready()
    tail = context.world_transition.api.stages[-1]
    context.bodies = {"prefix": context.method} if context.world_index == 0 else context.methods
    context.admitted_frames = {}
    context.pending_source_error = None
    context.world_root_claimed = False
    scope = dict(
        vars(tail),
        _guard=_world_stage_guard,
        _check=_world_stage_runtime,
        _admit_body=_world_admit_body,
        _capture_state=_world_capture_locals,
    )
    context.world_observer_scope = scope
    context.world_observer_bindings = _world_observer_atoms(context)
    observer = contextmanager(FunctionType(tail._account.__wrapped__.__code__, scope))
    with observer(context):
        yield


def _world_observer_atoms(context):
    scope = context.world_observer_scope
    result = [scope, scope["previous"], scope["literal"], scope["sys"]]
    for name in ("_guard", "_check", "_admit_body", "_capture_state"):
        result.extend((name, *_independent_atoms(scope[name])))
    for name in ("getprofile", "gettrace", "setprofile", "settrace"):
        result.extend((name, *_independent_atoms(getattr(scope["sys"], name))))
    return tuple(result)


def _world_cache_extensions(context, extra):
    transition = context.world_transition
    dyna = transition.api.stages[2]._WORLD.get(transition.request)
    if (
        dyna is None
        or not dyna.constructor_completed
        or context.phase.dyna is not dyna.handler
        or extra not in (("dyna",), ("dyna", "export_dirname"))
    ):
        _world_reject(transition, "Unowned extension of the same actual cache phase", context)
    if len(extra) == 2:
        tail = transition.api.stages[3]._WORLD.get(transition.request)
        if tail is None or getattr(dyna.parent.parent, "world_tail", None) is not tail:
            _world_reject(transition, "Original fresh-world SEED route changed", context)


def _world_tail_module(prefix):
    return prefix.world_transition.api.stages[3]


def _world_tail_route(prefix, *, active=False):
    transition = prefix.world_transition
    tail, dyna = transition.api.stages[3], transition.api.stages[2]
    context = tail._WORLD.get(transition.request)
    if (
        context is None
        or getattr(prefix, "world_tail", None) is not context
        or transition.api.stages[0]._TAIL_ROUTES.get(prefix.phase) is not context
        or context.refs[8] is not prefix
        or context.phase is not prefix.phase
        or context.claim is not transition.claim
    ):
        _world_reject(transition, "Original same-instance fresh-world tail route changed")
    if active:
        _world_stage_guard(context)
    return tail, dyna, context


def _world_phase_wrapper_guard(prefix, caller):
    transition = prefix.world_transition
    wrapper = (
        caller.f_back if caller.f_code is transition.api.stages[0]._native_call.__code__ else caller
    )
    role, method = wrapper.f_locals.get("name"), wrapper.f_locals.get("method")
    actual = wrapper.f_locals.get("actual")
    expected = prefix.phase if role == "SimPhase" else prefix.constructed.get(role)
    member = None if expected is None else vars(type(expected)).get(method)
    valid = (
        role in ("SimPhase", "Cells")
        and actual is expected
        and wrapper.f_locals.get("context") is prefix
        and type(member) is FunctionType
        and wrapper.f_code is member.__code__
        and wrapper.f_locals.get("delegate") is getattr(prefix.factories[role], method, None)
    )
    if not valid:
        _world_reject(transition, "Detached/raw original phase wrapper entry", prefix)
    if _world_has_prefix_route(prefix):
        module = transition.api.helpers
        retained = _world_forwarded(transition)
        if hasattr(retained, "voronoi_image"):
            route = module._voronoi_route(retained)
            if hasattr(route, "voronoi_mesh"):
                child = _world_voronoi_api()._mesh_route(route)
                return _world_voronoi_mesh_api()._wrapper_guard(child, prefix, wrapper)
            return _world_voronoi_api()._wrapper_guard(route, prefix, wrapper)
        route = _world_prefix_route(prefix)
        if role + "." + method not in module.METHODS:
            module._reject(route, None, "Method outside exact world-prefix dispatch")
        module._guard(route)
    else:
        tail, _, context = _world_tail_route(prefix, active=True)
        if role != "SimPhase" or method not in tail.METHODS:
            tail._reject_entry(context, None, "Method outside exact SEED helper dispatch")


def _world_seal(evidence, transition, world_owner, claim, stages):
    _ready()
    caller = sys._getframe(1)
    if (
        caller.f_code is not transition.api.stages[-1]._world_phase_seal.__code__
        or caller.f_back is None
        or caller.f_back.f_code is not _seal_active.__code__
        or caller.f_back.f_locals.get("context") is not transition
        or world_owner is not transition.request.world_parameters
        or claim is not transition.claim
        or len(stages) != 4
        or any(a is not b for a, b in zip(stages, transition.evidence, strict=True))
        or evidence is not transition.evidence[-1]
    ):
        _world_reject(transition, "Unclaimed full fresh-world phase seal")
    _world_parameter_authority(transition)
    for index, item in enumerate(stages):
        _check_evidence(transition, item, index, final_active=True)
    context = evidence.authority
    cache, graph = _world_state(context)
    document = dict(
        mode=MODE,
        request=transition.request.identity,
        stages=tuple(item.identity for item in stages),
        cache=cache.identity,
    )
    value = PhaseSeal(
        evidence,
        evidence.phase,
        transition.p,
        stages,
        cache,
        graph,
        _bindings(transition),
        _digest(document),
    )
    context.world_seal = value
    return value


def _world_check_seal(seal, transition, world_owner, claim, closed_record):
    _ready()
    context = transition.api.stages[-1]._WORLD.get(transition.request)
    if (
        type(seal) is not PhaseSeal
        or context is None
        or getattr(context, "world_seal", None) is not seal
        or seal.evidence is not context.evidence
        or world_owner is not transition.request.world_parameters
        or claim is not transition.claim
        or closed_record is not transition.parameter_record
    ):
        _world_reject(transition, "Actual fresh-world seal/claim association changed")
    _world_parameter_authority(transition)
    cache, graph = _world_state(context)
    transition.api.helpers.literal._same(_bindings(transition), seal.bindings)
    transition.api.helpers.literal._same(graph[0], seal.graph[0])
    document = dict(
        mode=MODE,
        request=transition.request.identity,
        stages=tuple(item.identity for item in seal.stages),
        cache=cache.identity,
    )
    if (
        cache.identity != seal.cache.identity
        or graph[1] != seal.graph[1]
        or _digest(document) != seal.identity
    ):
        _world_reject(transition, "Original full-phase seal changed")
    return seal


def _world_forwarded(transition):
    route = getattr(transition, "world_prefix", None)
    if route is None:
        return None
    owner = getattr(transition, "owner", None)
    helper, tail = transition.api.helpers, transition.api.stages[-1]
    if (
        owner is None
        or _ISSUED.get(owner) is not transition
        or _FORWARDED.get(owner) is not route
        or tail._FORWARDED.get(owner) is not route
        or helper._REQUESTS.get(route.request) is not route.refs
        or helper._CONSUMED.get(route.request) is not route
        or route.request.phase_owner is not owner
        or route.parent is not transition.evidence[-1].authority
        or route.phase is not transition.seal.phase
        or route.p is not transition.p
        or route.thread != transition.thread
    ):
        _world_reject(transition, "Original one-shot phase-to-world registry links changed")
    return route


def _world_has_prefix_route(prefix):
    return _world_forwarded(prefix.world_transition) is not None


def _world_prefix_route(prefix):
    transition = prefix.world_transition
    route = _world_forwarded(transition)
    if route is None or prefix is not transition.evidence[0].authority:
        _world_reject(transition, "Issued phase-to-world route unavailable")
    transition.api.helpers._guard(route)
    return route


def _world_parent(owner):
    _ready()
    context = _validate(owner)
    return context.evidence[-1].authority


def _world_claim_prefix(owner, expected, transition, entries):
    _ready()
    with _LOCK:
        world = _validate(owner)
        helper, tail = world.api.helpers, world.api.stages[-1]
        if (
            world.evidence[-1].authority is not expected
            or type(transition.request) is not helper.Request
            or helper._REQUESTS.get(transition.request) is not transition.refs
            or helper._CONSUMED.get(transition.request) is not transition
            or transition.parent is not expected
            or transition.request.phase_owner is not owner
            or transition.phase is not world.seal.phase
            or transition.p is not world.p
            or entries is not transition.entries
            or tuple(entries) != helper.METHODS
            or owner in _FORWARDED
            or owner in tail._FORWARDED
            or hasattr(world, "world_prefix")
            or world.active
            or world.invalid
            or transition.thread != get_ident()
        ):
            _world_reject(world, "Unissued/repeated phase-to-world continuation")
        # Marker first; neither failed partial registry publication nor loss
        # of a registry edge may rearm this phase epoch.
        world.world_prefix = transition
        try:
            _FORWARDED[owner] = transition
            tail._FORWARDED[owner] = transition
            _world_forwarded(world)
        except BaseException:
            world.invalid = transition.invalid = True
            raise
        return expected


def _world_after_prefix_claim(tail):
    world = tail.world_transition
    _closed_lineage(world)
    route = _world_forwarded(world)
    if route is None or tail is not world.evidence[-1].authority or world.invalid:
        _world_reject(world, "Original forwarded whole-phase history unavailable")
    # All caches/graphs below omit exactly the literal lattice fields on the
    # actual Cells object. The lattice driver checks its own fields/RNG epoch.
    # No consumed public phase owner or pre-mutation numeric parent is reopened.
    with _validation_scope(world.owner, world) as reservation:
        _closed(world, validation=reservation)
    return tail


def _construction_entry(kind):
    reservation = _VALIDATION.current
    if reservation is not None:
        _reject_validation(reservation, kind)


def _reserve_validation(owner, context, *, acquisition):
    # The lock protects publication only, never fallible external checkers.
    acquired = _LOCK.acquire(blocking=False)
    if not acquired:
        reservation = _VALIDATION.current
        if reservation is not None:
            _reject_validation(reservation, "competing_validation", owner)
        if _ACTIVE:
            _ACTIVE[-1].invalid = True
        context.invalid = True
        raise WorldPhaseRejected("Coordinator reservation busy", stage="validation_entry")
    try:
        reservation = _VALIDATION.current
        if reservation is not None:
            _reject_validation(reservation, "recursive_or_competing_owner_read", owner)
        if _ACTIVE:
            _ACTIVE[-1].invalid = context.invalid = True
            raise WorldPhaseRejected(
                "Construction overlaps closed-owner read", stage="validation_entry"
            )
        if context.invalid:
            raise WorldPhaseRejected("Invalid closed-owner epoch", stage="validation_entry")
        reservation = SimpleNamespace(
            owner=owner,
            context=context,
            acquisition=acquisition,
            thread=get_ident(),
            active=True,
            invalid=False,
            attempts=(),
            cleanup_errors=(),
            primary=None,
            rejection=WorldPhaseRejected(
                "Recursive/competing closed validation", stage="validation_entry"
            ),
        )
        context.last_validation = reservation
        _VALIDATION.current = reservation
        return reservation
    finally:
        _LOCK.release()


def _validation_check(reservation):
    if (
        not reservation.active
        or reservation.invalid
        or reservation.context.invalid
        or reservation.thread != get_ident()
        or _VALIDATION.current is not reservation
        or reservation.context.last_validation is not reservation
    ):
        _reject_validation(reservation, "poisoned_validation")


def _release_validation(reservation):
    # Exact-token retirement contains no external helper or callback. A new
    # reservation cannot publish while this token is still present.
    if _VALIDATION.current is not reservation:
        raise ValueError("Original validation reservation changed")
    _VALIDATION.current = None
    reservation.active = False


@contextmanager
def _validation_scope(owner, context):
    acquisition = object()
    reservation = None
    try:
        reservation = _reserve_validation(owner, context, acquisition=acquisition)
        yield reservation
        _validation_check(reservation)
    except BaseException as error:
        context.invalid = True
        if reservation is None:
            # An inherited return observer may reject AFTER publication and
            # BEFORE the helper's result reaches this frame. Recover only
            # this acquisition's exact owner/context token, never a neighbour.
            candidate = _VALIDATION.current
            try:
                if (
                    candidate is not None
                    and candidate.acquisition is acquisition
                    and candidate.owner is owner
                    and candidate.context is context
                    and context.last_validation is candidate
                ):
                    reservation = candidate
            except BaseException as capture:
                context.validation_acquisition_errors = (
                    *getattr(context, "validation_acquisition_errors", ()),
                    (error, capture),
                )
        if reservation is not None:
            reservation.primary = error
        raise
    finally:
        if reservation is not None:
            try:
                _release_validation(reservation)
            except BaseException as capture:
                # A rejection at cleanup entry/return cannot replace a
                # primary or strand this exact published acquisition.
                context.invalid = True
                reservation.invalid = True
                reservation.cleanup_errors = (*reservation.cleanup_errors, capture)
                if _VALIDATION.current is reservation:
                    _VALIDATION.current = None
                reservation.active = False
            poisoned = bool(reservation.attempts) or (
                (reservation.invalid or context.invalid) and not reservation.cleanup_errors
            )
            if reservation.primary is None and poisoned:
                reservation.primary = reservation.rejection
            if reservation.primary is not None or reservation.cleanup_errors:
                context.validation_failures = (
                    *getattr(context, "validation_failures", ()),
                    reservation,
                )
            if reservation.primary is reservation.rejection:
                raise reservation.rejection
            if reservation.primary is None and reservation.cleanup_errors:
                raise WorldPhaseRejected(
                    "Closed-owner reservation cleanup failed",
                    stage="validation_cleanup",
                    partial=reservation,
                    capture_error=reservation.cleanup_errors[0],
                ) from reservation.cleanup_errors[0]


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
            raise WorldPhaseRejected(
                "Actual issued WorldReady/callback request required", stage="request"
            )
        if request in _CONSUMED or request.world_parameters in _CLAIMED:
            raise WorldPhaseRejected("World construction attempt consumed", stage="consumed")
        context = SimpleNamespace(
            request=request,
            parents=_REQUESTS[request],
            api=api,
            p=_REQUESTS[request][1],
            thread=get_ident(),
            active=True,
            invalid=False,
            entry_error=None,
            primary=None,
            capture_error=None,
            capture_errors=(),
            claim_errors=(),
            failed_stages=(),
            stage_partials=(),
            claim=None,
            parameter_record=None,
            failed_claim=None,
            failed_claim_partial=None,
            evidence=[],
            last_returned=None,
            raw_seal=None,
            seal=None,
            trial=None,
            work=[],
            executing=None,
            stage="construction_claim_before_phase_birth",
            dispatch_ticket=None,
            driver_frame=None,
            step_frame=None,
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
                    *context.capture_errors,
                    ("coordinator_stack_release", capture, context),
                )
        if (
            context.primary is not None
            or context.capture_error is not None
            or context.trial is None
            or context.parameter_record is None
            or context.invalid
        ):
            raise WorldPhaseRejected(
                "Actual world-phase construction refused",
                stage=context.stage,
                request=request,
                trial=context.trial,
                partial=_partial(context),
                source_error=context.primary,
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
    if (
        context is None
        or context.owner is not owner
        or context.active
        or context.invalid
        or context.thread != get_ident()
    ):
        raise WorldPhaseRejected(
            "Actual successfully sealed world-phase child required", stage="owner"
        )
    if owner in _FORWARDED or hasattr(context, "world_prefix"):
        raise WorldPhaseRejected(
            "Phase epoch was irreversibly consumed by its world prefix",
            stage="forwarded",
            trial=context.trial,
            partial=context,
        )
    try:
        with _validation_scope(owner, context) as reservation:
            _validate_reserved(context, reservation)
    except BaseException as error:
        context.invalid = True
        raise WorldPhaseRejected(
            "Stale world-phase owner",
            stage="owner_drift",
            request=context.request,
            trial=context.trial,
            partial=_partial(context),
            source_error=error,
        ) from error
    return context


def _closed_lineage(context):
    if (
        _REQUESTS.get(context.request) is not context.parents
        or _CONSUMED.get(context.request) is not context
        or _CLAIMED.get(context.request.world_parameters) is not context
        or _digest(source_plan()) != context.request.source_identity
        or type(context.request.mode) is not str
        or context.request.mode != MODE
        or _digest(request_record(context.request)) != context.request.identity
    ):
        raise ValueError("World phase original issuance/source changed")


def _validate_reserved(context, reservation):
    # The reservation spans BOTH sides of Key validation and every later
    # stage check, without reopening old numeric owners or active claims.
    _validation_check(reservation)
    _closed_lineage(context)
    _validation_check(reservation)
    _same_dependencies(context)
    _validation_check(reservation)
    _compare_bindings(context)
    _validation_check(reservation)
    _closed(context, validation=reservation)
    _validation_check(reservation)
