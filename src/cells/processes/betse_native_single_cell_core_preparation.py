"""Owned single-cell pre_mesh -> native core-operator source prerequisite.

Only the real owned-image single-cell init_mesh branch is supported. Replay the
original constructor/RNG and require the retained pre_mesh state exactly before
calling the unchanged native core-operator body. Typed evidence is not a mutable
executable DEC parent or physical geometry admission. Initial19/22 and stable0/9
limitations remain unchanged; no post-cut continuation owner is cleared here.
"""

import hashlib
import json
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_mesh_lifecycle_preparation as lifecycle
from cells.processes import betse_normal_current as records

LAW_ID = "betse_owned_single_cell_pre_mesh_core_prerequisite@1"
MAX_CONSTRUCTOR_OCCURRENCES = 7
HELD_UNQUALIFIED_SOURCE_STAGE = True
SOURCE_PINS = {
    "betse_initial_mesh_preparation": (
        "ef33e60ea5cd741d3618bccaaba494ac472664b02f4c82d08942b3e2c52c89b0"
    ),
    "betse_initial_mesh_preparation_kernel": (
        "7102de6bae1f5da0ecb5c99064ffa03b26e20b2b7b8855b72f5066fd20a0089c"
    ),
    "betse_initial_mesh_preparation_cache": (
        "f77c0a5a09d92dbf0746ac7c89ca564ea6bebc726e27ae5b40d3e90f4bffb69a"
    ),
    "betse_mesh_lifecycle_preparation": (
        "ece37d274047d9d1826a74703a68fcaca2d16385c6a20e18dc0174a58cb57381"
    ),
    "betse_mesh_lifecycle_preparation_kernel": (
        "7f3599c3eeb002d1f9a0e721e2b15b8a2932922a863ea3084cb39e5d2767e7fd"
    ),
    "betse_image_mask_prelude": (
        "e8e14819df8a80692c2c3990189aaccb2e375a6c984c2cd8dc727ce80e2ce03b"
    ),
    "betse_perturbations": ("75fbb75e84d23ab3095230117cd23fef3bf04fecb71e09ba5cb256aea64fbc56"),
    "betse_geometry_initialization": (
        "9035c4dba445292010821eb871970cbb3348fdfedd0d597459ccfe6adb1234de"
    ),
    "betse_normal_current": ("294a4d3e267e9d75caccd50eaaacc462931a8597d5eadd88ea94f9dc3856add7"),
}
INVALIDATED_OWNERS = (
    "DEC_mesh_and_operators",
    "cell_membrane_geometry_and_measures",
    "environment_maps_volumes_and_operators",
    "cell_graph_and_gap_junctions",
    "source_diffusion_and_wound_TJ",
    "tissue_profile_and_callback_epochs",
    "RNG_and_schedule_epochs",
    "molecule_transporter_channel_reinitialization",
    "current_voltage_and_initializer_caches",
    "material_and_voltage_component_bindings",
    "complete_post_cut_checkpoint",
)
REQUIRED_PRE_MESH_FIELDS = (
    "tri_verts",
    "tri_edges",
    "tri_cells",
    "tcell_verts",
    "tri_ccents",
    "tri_rcircs",
    "tri_cents",
    "tri_sa",
    "tri_mids",
    "tri_edge_i",
    "tri_edge_len",
    "tri_tang",
    "_tverts_to_tcell",
    "tverts_to_tedges",
    "tcell_to_tedges",
    "tedges_to_tcell",
    "n_tverts",
    "n_tedges",
    "n_tcell",
    "vor_verts",
    "vor_cells",
    "vcell_verts",
    "vor_cents",
    "vor_sa",
    "vor_edge_len",
    "make_all_operators",
    "single_cell",
)


@dataclass(frozen=True, slots=True)
class Request:
    initial_request: initial.Request
    initial_state: initial.State
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    request_identity: str
    constructed_cache: caches.Cache
    before_cache: caches.Cache
    cache: caches.Cache
    events: tuple
    point_ids: tuple
    stream_before: object
    stream_after: object
    source_owner_ids_json: str
    warnings: tuple
    core_source_completed: bool
    status: str
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class CorePrerequisiteRejected(ValueError):
    def __init__(
        self,
        reason,
        *,
        stage,
        parent_request=None,
        parent_state=None,
        trial=None,
        upstream_trial=None,
        partial=None,
        source_error=None,
        capture_error=None,
        source_stage=None,
        capture_stage=None,
    ):
        super().__init__(reason + " at " + stage)
        self.stage = stage
        self.parent_request, self.parent_state = parent_request, parent_state
        self.trial, self.upstream_trial, self.partial = trial, upstream_trial, partial
        # Preserve exception objects and their original tracebacks/causes. No
        # formatting or serialization is attempted in this error carrier.
        self.source_error, self.capture_error = source_error, capture_error
        self.source_stage, self.capture_stage = source_stage, capture_stage


def _verify_sources():
    modules = (
        initial,
        initial.source,
        caches,
        lifecycle,
        lifecycle.source,
        initial.image_stage,
        initial.streams,
        initial.reused,
        records,
    )
    for module in modules:
        name = module.__name__.rsplit(".", 1)[-1]
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != SOURCE_PINS[name]:
            raise ValueError("Changed frozen source dependency: " + name)


def _precheck(parent_request, parent_state):
    def refuse(reason, stage):
        raise CorePrerequisiteRejected(
            reason, stage=stage, parent_request=parent_request, parent_state=parent_state
        )

    if parent_request is None or parent_state is None:
        refuse("Native constructor parent unavailable", "upstream_unavailable")
    if type(parent_request) is not initial.Request or type(parent_state) is not initial.State:
        refuse(
            "Require native typed constructor request/state; no supplied or stable substitute",
            "upstream_owner_type",
        )
    if parent_request.origin != "owned_image_prelude":
        refuse("Fixed B09 probes do not own this native caller branch", "upstream_origin")
    if (
        parent_state.constructor_completed is not True
        or parent_state.pre_mesh_completed is not True
        or parent_state.status != "source_completed_unqualified"
        or parent_state.failure_stage is not None
        or parent_state.failure_type is not None
        or parent_state.failure_message is not None
    ):
        refuse("Upstream constructor/pre_mesh incomplete or failed", "upstream_incomplete")
    if parent_state.request_identity != parent_request.identity:
        refuse("Constructor state belongs to a different request", "upstream_identity")
    kwargs = parent_request.constructor_kwargs
    if (
        len(parent_request.upstream) != 3
        or kwargs.get("seed_points") is not None
        or kwargs.get("make_all_operators") is not False
        or kwargs.get("single_cell_sides") != 6
        or len(parent_request.constructor_point_ids) != MAX_CONSTRUCTOR_OCCURRENCES
        or parent_request.upstream[2].next_method != "init_mesh"
    ):
        refuse("Only the actual single-cell init_mesh branch is owned here", "caller_branch")
    caches.validate(parent_state.constructed_cache)
    caches.validate(parent_state.cache)
    if not parent_state.constructed_cache.all_finite or not parent_state.cache.all_finite:
        refuse("Incomplete finite native parent; retain original failed caches", "upstream_finite")


def request_record(request):
    return dict(
        law=LAW_ID,
        initial_request_identity=request.initial_request.identity,
        initial_state_identity=request.initial_state.identity,
        initial_request=initial.request_record(request.initial_request),
        initial_state=initial.state_record(request.initial_state),
        dependency_source_sha256=SOURCE_PINS,
        branch="owned_make_voronoi_single_cell_init_mesh@1",
        exact_continuation="pre_mesh -> create_core_operators; stop before caller cell_index",
        native_initial_qualification="19/22 accuracy qualification open",
        stable_independent_geometry="0/9 retained; never an upstream substitute",
        physical_geometry_admitted=False,
        executable_DEC_parent_admitted=False,
    )


def from_initial(parent_request, parent_state, *, law_id):
    try:
        if type(law_id) is not str or law_id != LAW_ID:
            raise CorePrerequisiteRejected(
                "Explicit native source law opt-in required",
                stage="opt_in",
                parent_request=parent_request,
                parent_state=parent_state,
            )
        _precheck(parent_request, parent_state)
        _verify_sources()
        # This authenticates the real construction chain by replay, not by
        # relabeling hashes or decoding a supplied cache. initial.validate_state
        # calls initial.prepare: constructor/pre_mesh work here is numerical,
        # including when reached through from_initial or validate_request. A
        # released qualification must count and resource-bound every such call.
        initial.validate_state(parent_request, parent_state)
        value = Request(parent_request, parent_state, "")
        return replace(value, identity=records._digest(request_record(value)))
    except CorePrerequisiteRejected:
        raise
    except Exception as error:
        raise CorePrerequisiteRejected(
            "Native upstream authentication refused",
            stage="upstream_validation",
            parent_request=parent_request,
            parent_state=parent_state,
            upstream_trial=getattr(error, "trial", None),
        ) from error


def validate_request(request):
    if type(request) is not Request:
        raise CorePrerequisiteRejected(
            "Complete typed source continuation request required",
            stage="request_owner",
            parent_request=request,
        )
    expected = from_initial(request.initial_request, request.initial_state, law_id=LAW_ID)
    if expected.identity != request.identity or records.record(
        request_record(expected)
    ) != records.record(request_record(request)):
        raise CorePrerequisiteRejected(
            "Changed source continuation request",
            stage="request_identity",
            parent_request=request.initial_request,
            parent_state=request.initial_state,
        )
    return request


class _Runtime(initial._Runtime):
    # All numerical work delegates to the existing literal native kernels. Only
    # the previously missing owned single-cell continuation driver is added.
    create_core_operators = initial._observe(
        "create_core_operators", lifecycle.source.LifecycleKernel.create_core_operators
    )
    _cells_pinv = lifecycle._Runtime._cells_pinv
    _cells_lifecycle_partial = lifecycle._Runtime._cells_lifecycle_partial
    _cells_lifecycle_return = lifecycle._Runtime._cells_lifecycle_return


def _cache_keys(cache):
    descriptor = cache.descriptor
    if descriptor["kind"] != "dict":
        raise ValueError("Native mesh cache must own the complete attribute mapping")
    keys = []
    for key, _ in descriptor["items"]:
        if key["kind"] != "str":
            raise ValueError("Native mesh attributes must have string names")
        keys.append(key["value"])
    return keys


def _source_owners(request, kernel):
    epoch = request.initial_state.cache.identity
    # These are source row-occurrence identities in this construction epoch,
    # not canonical geometric IDs or admitted physical cell/material owners.
    return dict(
        kind="cells.native_DEC_source_occurrence_axes@1",
        source_cache_identity=epoch,
        tri_vertex_ids=list(request.initial_state.retained_point_ids),
        tri_edge_ids=[epoch + "/tri-edge/" + str(i) for i in range(kernel.n_tedges)],
        tri_face_ids=[epoch + "/tri-face/" + str(i) for i in range(kernel.n_tcell)],
        physical_material_owner_binding=False,
        coordinate_invariance_claim=False,
    )


def state_record(state):
    return dict(
        law=LAW_ID,
        request_identity=state.request_identity,
        constructed_cache=state.constructed_cache.identity,
        before_cache=state.before_cache.identity,
        cache=state.cache.identity,
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=e.payload.identity,
            )
            for e in state.events
        ],
        point_ids=state.point_ids,
        stream_before=initial.streams.native_stream_manifest(state.stream_before),
        stream_after=initial.streams.native_stream_manifest(state.stream_after),
        source_owner_ids=json.loads(state.source_owner_ids_json),
        warnings=state.warnings,
        core_source_completed=state.core_source_completed,
        status=state.status,
        failure_stage=state.failure_stage,
        failure_type=state.failure_type,
        failure_message=state.failure_message,
        native_initial_qualification="19/22 accuracy qualification open",
        stable_independent_geometry="0/9 unchanged",
        topology_qualified=False,
        independent_geometry_qualified=False,
        executable_DEC_parent_admitted=False,
        physical_geometry_admitted=False,
        ordinary_continuation_admitted=False,
        invalidated_owners=list(INVALIDATED_OWNERS),
    )


def _exception_chain(error):
    """Original explicit-cause/unsuppressed-context objects, with cycle marker."""
    nodes, seen = [], set()
    while error is not None and id(error) not in seen:
        seen.add(id(error))
        nodes.append(error)
        error = (
            error.__cause__
            if error.__cause__ is not None
            else None
            if error.__suppress_context__
            else error.__context__
        )
    return dict(nodes=tuple(nodes), cycle=error is not None)


def _incomplete_capture(
    request,
    parent,
    kernel,
    observer,
    rng,
    owners,
    caught,
    source_stage,
    source_error,
    core_returned,
    capture_error,
    capture,
):
    """Retain evidence without retrying any serializer that just failed.

    Last successful snapshots stay immutable. Raw fields/objects are retained
    as live references when no complete typed capture can be made. They are
    partial diagnostics, never an executable/checkpoint contract.
    """
    partial = dict(
        capture_complete=False,
        complete_state_available=False,
        source_stage=source_stage,
        capture_stage=capture.get("stage"),
        core_method_returned=core_returned,
        last_successful_snapshots=dict(capture["snapshots"]),
        unsealed_state_candidate=capture.get("unsealed_state"),
        unsealed_state_record=capture.get("state_record"),
        unsealed_identity=capture.get("identity"),
        original_kernel=kernel,
        original_observer=observer,
        original_rng=rng,
        source_owner_ids=owners,
        source_exception=source_error,
        source_exception_chain=_exception_chain(source_error),
        capture_exception=capture_error,
        capture_exception_chain=_exception_chain(capture_error),
        recovery_errors=[],
        executable_DEC_parent_admitted=False,
        ordinary_continuation_admitted=False,
        invalidated_owners=list(INVALIDATED_OWNERS),
    )
    # These accessors copy references/state only; no snapshot, stream codec,
    # State construction, digest, exception __str__, or retry of sealing occurs.
    accessors = (
        (
            "raw_cache",
            lambda: {k: v for k, v in vars(kernel).items() if not k.startswith("_cells_")},
        ),
        ("collected_events", lambda: tuple(observer.events)),
        ("point_ids", lambda: tuple(observer.ids)),
        ("raw_rng_state", lambda: rng.get_state()),
        ("raw_warning_records", lambda: tuple(caught)),
    )
    for name, get in accessors:
        try:
            partial[name] = get()
        except Exception as error:
            partial["recovery_errors"].append((name, error))
    return CorePrerequisiteRejected(
        "Source trial evidence could not be sealed",
        stage="evidence_capture",
        parent_request=request,
        parent_state=parent,
        trial=None,
        partial=partial,
        source_error=source_error,
        capture_error=capture_error,
        source_stage=source_stage,
        capture_stage=capture.get("stage"),
    )


def _seal_trial(
    request,
    base,
    parent,
    kernel,
    observer,
    rng,
    owners,
    caught,
    constructed,
    before,
    source_error,
    source_stage,
    core_completed,
    capture,
):
    capture["stage"] = "final_snapshot"
    final_cache = caches.snapshot(initial._public_cache(kernel))
    capture["snapshots"]["final"] = final_cache
    capture["stage"] = "final_stream"
    stream_after = initial._rng_stream(rng)
    capture["stage"] = "State"
    state = State(
        request.identity,
        constructed,
        before,
        final_cache,
        tuple(observer.events),
        observer.ids,
        base.stream_before,
        stream_after,
        json.dumps(owners, sort_keys=True, separators=(",", ":")),
        tuple(str(w.message) for w in caught),
        core_completed,
        "source_core_operators_completed_unqualified"
        if source_error is None
        else "retained_source_prerequisite_failure",
        source_stage if source_error is not None else None,
        type(source_error).__name__ if source_error is not None else None,
        str(source_error) if source_error is not None else None,
        "",
    )
    capture["unsealed_state"] = state
    capture["stage"] = "state_record"
    capture["state_record"] = state_record(state)
    capture["stage"] = "identity_digest"
    capture["identity"] = records._digest(capture["state_record"])
    capture["stage"] = "identity_replace"
    state = replace(state, identity=capture["identity"])
    capture["complete"] = True
    return state


def prepare(request):
    validate_request(request)
    base, parent = request.initial_request, request.initial_state
    saved = initial.streams.native_stream_manifest(base.stream_before)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = initial._Observer(base.constructor_point_ids)
    observer.first_failure = None
    kernel = object.__new__(_Runtime)
    kernel._cells_observer, kernel._cells_rng = observer, initial._Random(rng, observer)
    kwargs = {
        name: np.array(value, copy=True, order="K") if isinstance(value, np.ndarray) else value
        for name, value in base.constructor_kwargs.items()
    }
    stage, error, core_completed = "constructor_replay", None, False
    constructed = before = None
    owners = dict(kind="unavailable_incomplete_source_axes", physical_material_owner_binding=False)
    try:
        constructed = before = caches.snapshot({})
    except Exception as capture_error:
        capture = dict(
            stage="initial_snapshot",
            snapshots=dict(constructed=None, before=None),
            unsealed_state=None,
            state_record=None,
            identity=None,
            complete=False,
        )
        rejected = _incomplete_capture(
            base,
            parent,
            kernel,
            observer,
            rng,
            owners,
            (),
            stage,
            None,
            False,
            capture_error,
            capture,
        )
        raise rejected from capture_error
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            kernel.__init__(**kwargs)
            constructed = caches.snapshot(initial._public_cache(kernel))
            if (
                constructed.identity != parent.constructed_cache.identity
                or initial._rng_stream(rng).identity != parent.stream_after_constructor.identity
            ):
                raise ValueError("Actual constructor cache/RNG differs from retained native parent")
            stage = "pre_mesh_replay"
            kernel.pre_mesh()
            before = caches.snapshot(initial._public_cache(kernel))
            if (
                before.identity != parent.cache.identity
                or observer.ids != parent.retained_point_ids
                or initial._rng_stream(rng).identity != parent.stream_after.identity
            ):
                raise ValueError(
                    "Actual pre_mesh cache/occurrence/RNG differs from retained native parent"
                )
            stage = "pre_mesh_event_replay"
            actual_events = [
                (e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in observer.events
            ]
            expected_events = [
                (e.sequence, e.kind, e.method, e.depth, e.payload.identity) for e in parent.events
            ]
            if actual_events != expected_events:
                raise ValueError("Actual constructor/pre_mesh event chain differs from parent")
            if tuple(str(w.message) for w in caught) != parent.warnings:
                raise ValueError("Actual constructor/pre_mesh warnings differ from parent")
            stage = "pre_mesh_required_fields"
            attributes = initial._public_cache(kernel)
            missing = sorted(set(REQUIRED_PRE_MESH_FIELDS) - set(attributes))
            if missing:
                raise ValueError("Native parent lacks source fields: " + repr(missing))
            if kernel.make_all_operators is not False or kernel.single_cell is not True:
                raise ValueError("Retained native caller branch flags differ")
            if kernel.n_tverts != len(observer.ids):
                raise ValueError("Native DEC vertex occurrence axis lost")
            owners = _source_owners(request, kernel)
            observer.add(
                "owned_single_cell_core_start", dict(cache=attributes, point_ids=observer.ids)
            )
            stage = "create_core_operators"
            kernel.create_core_operators()
            core_completed = True
            stage = "core_finite_and_source_axis_admission"
            after = initial._public_cache(kernel)
            original_keys = _cache_keys(before)
            if (
                caches.snapshot({key: after[key] for key in original_keys}).identity
                != before.identity
            ):
                raise ValueError(
                    "Native core operator call changed the retained pre_mesh attributes"
                )
            if set(after) - set(original_keys) != {"delta_tri_0", "delta_tri_0_inv"}:
                raise ValueError("Unexpected source fields outside core operator continuation")
            if (
                np.shape(kernel.delta_tri_0) != (kernel.n_tedges, kernel.n_tverts)
                or np.shape(kernel.delta_tri_0_inv) != (kernel.n_tverts, kernel.n_tedges)
                or not caches.snapshot(after).all_finite
            ):
                raise ValueError("Native core result has invalid source axes or nonfinite caches")
            if initial._rng_stream(rng).identity != parent.stream_after.identity:
                raise ValueError("Core operator call consumed an unexpected RNG epoch")
        except Exception as failure:
            error = failure
    capture = dict(
        stage=None,
        snapshots=dict(constructed=constructed, before=before),
        unsealed_state=None,
        state_record=None,
        identity=None,
        complete=False,
    )
    try:
        state = _seal_trial(
            request,
            base,
            parent,
            kernel,
            observer,
            rng,
            owners,
            caught,
            constructed,
            before,
            error,
            stage,
            core_completed,
            capture,
        )
    except Exception as capture_error:
        rejected = _incomplete_capture(
            base,
            parent,
            kernel,
            observer,
            rng,
            owners,
            caught,
            stage,
            error,
            core_completed,
            capture_error,
            capture,
        )
        # A secondary capture error never displaces the original source failure.
        # Both original chains remain attached independently in the carrier.
        raise rejected from (error if error is not None else capture_error)
    if error is not None:
        raise CorePrerequisiteRejected(
            "Actual source continuation refused",
            stage=stage,
            parent_request=base,
            parent_state=parent,
            trial=state,
            source_error=error,
            source_stage=stage,
        ) from error
    return state


def validate_state(request, state):
    if type(state) is not State or state.request_identity != request.identity:
        raise CorePrerequisiteRejected(
            "Complete owned core source trial required",
            stage="state_owner",
            parent_request=request.initial_request,
            parent_state=request.initial_state,
            trial=state,
        )
    for cache in (
        state.constructed_cache,
        state.before_cache,
        state.cache,
        *(event.payload for event in state.events),
    ):
        caches.validate(cache)
    expected = prepare(request)
    if state.identity != expected.identity or state_record(state) != state_record(expected):
        raise CorePrerequisiteRejected(
            "Changed source core trial",
            stage="state_identity",
            parent_request=request.initial_request,
            parent_state=request.initial_state,
            trial=state,
        )
    return state


def require_executable_parent(request, state, *, declarations=None):
    raise CorePrerequisiteRejected(
        "A core-operator source trial does not admit an executable native DEC parent or checkpoint",
        stage="executable_native_DEC_parent_unavailable",
        parent_request=request,
        parent_state=state,
        partial=dict(
            metadata_cannot_admit_parent=True,
            supplied_declarations=declarations,
            independent_geometry_qualified=False,
            executable_DEC_parent_admitted=False,
            ordinary_continuation_admitted=False,
            invalidated_owners=list(INVALIDATED_OWNERS),
        ),
    )
