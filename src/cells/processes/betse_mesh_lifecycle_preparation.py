"""Owned post-clipping lifecycle; source fidelity is not geometry admission."""

import inspect
import json
import math
import warnings
from dataclasses import dataclass, replace

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_mesh_clip_preparation as clipped
from cells.processes import betse_mesh_lifecycle_preparation_kernel as source
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

LAW_ID = "betse_owned_post_clip_lifecycle_v1_5_0@1"
OPTION_KIND = "cells.manufactured_native_mesh_lifecycle_options@1"
MAX_POINTS = 32
MAX_STEPS = 25
METHODS = (
    "init_mesh",
    "create_core_operators",
    "create_aux_operators",
    "mesh_quality_calc",
    "refine_mesh",
    "laplacian_smoothing",
    "after_clip_lifecycle",
)


@dataclass(frozen=True, slots=True)
class Request:
    clip_request: clipped.Request
    clip_state: clipped.State
    origin: str
    options_json: str
    identity: str

    @property
    def options(self):
        return json.loads(self.options_json)


@dataclass(frozen=True, slots=True)
class State:
    request_identity: str
    before_cache: caches.Cache
    cache: caches.Cache
    events: tuple
    point_ids_before: tuple
    point_ids_after: tuple
    stream_before: streams.NativeStream
    stream_after: streams.NativeStream
    termination_json: str
    warnings: tuple
    status: str
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class LifecycleRejected(NumericalError):
    def __init__(self, error, *, stage, trial=None):
        super().__init__("Native lifecycle refused at " + stage + ": " + str(error))
        self.stage, self.trial = stage, trial


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _parameters(values, radius):
    expected = {"smoothing", "refinement", "max_steps", "convergence", "fix_bounds"}
    if not isinstance(values, dict) or set(values) != expected:
        raise ValueError("Declare exactly the native lifecycle parameters")
    for key in ("refinement", "fix_bounds"):
        if type(values[key]) is not bool:
            raise ValueError("Lifecycle switches must be literal booleans")
    if type(values["max_steps"]) is not int or not 0 <= values["max_steps"] <= MAX_STEPS:
        raise ValueError("Lifecycle step count exceeds the declared bounded source domain")
    if (
        type(values["convergence"]) not in (int, float)
        or not math.isfinite(values["convergence"])
        or values["convergence"] <= 0
    ):
        raise ValueError("Declare a finite positive convergence threshold")
    step = values["smoothing"]
    if step is not None and (
        type(step) not in (int, float) or not math.isfinite(step) or abs(step) > 4 * radius**2
    ):
        raise ValueError("Native option trials bound absolute smoothing to 4 * radius**2")
    return dict(values)


def _input(request, state):
    clipped.validate_state(request, state)
    fields = caches.plain(state.cache)
    n = len(state.retained_point_ids)
    if (
        not 1 <= n <= MAX_POINTS
        or np.asarray(fields["tri_verts"]).shape != (n, 2)
        or np.asarray(fields["vor_cents"]).shape != (n, 2)
        or fields["n_tverts"] != n
        or fields["make_all_operators"] is not False
    ):
        raise ValueError(
            "Require <=32 owned caller points, matching axes and the original false auxiliary flag"
        )
    if not state.cache.all_finite or state.status != "source_clipped_rebuilt_unqualified":
        raise ValueError("Require a complete finite unqualified clipping source trial")
    return fields


def request_record(request):
    return dict(
        law=LAW_ID,
        clip_request_identity=request.clip_request.identity,
        clip_state_identity=request.clip_state.identity,
        origin=request.origin,
        options=request.options,
        upstream_initial_qualification="19/22 accuracy qualification open",
        topology_qualified=False,
        physical_geometry_admitted=False,
    )


def from_clipped(request, state):
    fields = _input(request, state)
    prelude = request.initial_request.upstream[2]
    if prelude.next_method != "clip_and_refine":
        raise ValueError("Require the original non-SVG multi-cell lifecycle caller")
    options = _parameters(dict(prelude.next_kwargs), fields["cell_radius"])
    value = Request(request, state, "owned_make_voronoi_lifecycle", _canonical(options), "")
    return replace(value, identity=records._digest(request_record(value)))


def from_native_option_trial(request, state, recipe):
    fields = _input(request, state)
    if not isinstance(recipe, dict) or set(recipe) != {
        "kind",
        "classification",
        "provenance",
        "parameters",
    }:
        raise ValueError("Native API option trials require an explicit separate declaration")
    if (
        recipe["kind"] != OPTION_KIND
        or recipe["classification"] != "manufactured_native_api_options"
        or type(recipe["provenance"]) is not str
        or not recipe["provenance"]
    ):
        raise ValueError("Do not relabel smoothing/outer-bound changes as the make_voronoi caller")
    _parameters(recipe["parameters"], fields["cell_radius"])
    value = Request(request, state, "manufactured_native_api_options", _canonical(recipe), "")
    return replace(value, identity=records._digest(request_record(value)))


def parameters(request):
    value = request.options
    return value["parameters"] if request.origin == "manufactured_native_api_options" else value


def validate_request(request):
    if type(request) is not Request:
        raise ValueError("Require the owned clipping state and lifecycle declaration")
    if request.origin == "owned_make_voronoi_lifecycle":
        expected = from_clipped(request.clip_request, request.clip_state)
    elif request.origin == "manufactured_native_api_options":
        expected = from_native_option_trial(
            request.clip_request, request.clip_state, request.options
        )
    else:
        raise ValueError("Unknown lifecycle provenance")
    if request.identity != expected.identity or request_record(request) != request_record(expected):
        raise ValueError("Changed lifecycle options, clipping input or source authority")
    return request


def numeric_locals(frame):
    result = clipped.numeric_locals(frame)
    for key in ("tedge_tree", "vedge_tree"):
        if key in result:
            result[key] = dict(kind="native_kd_tree_input_token", data=result[key].data)
    return result


class _Observer(clipped._Observer):
    def __init__(self, ids):
        super().__init__(ids)
        self.lifecycle_active = False
        self.before_ids = ()
        self.pending_move = None
        self.first_failure = None
        self.rebuild_count = 0
        self.iterations_started = 0
        self.iterations_completed = 0
        self.converged = False


class _Runtime(source.LifecycleKernel, clipped._Runtime):
    def _cells_lifecycle_partial(self, frame):
        self._cells_observer.add(
            "lifecycle_partial_locals",
            dict(
                locals=numeric_locals(frame),
                cache=initial._public_cache(self),
                point_ids=self._cells_observer.ids,
            ),
        )

    def _cells_lifecycle_return(self, frame):
        self._cells_observer.add(
            "lifecycle_return_locals",
            dict(
                locals=numeric_locals(frame),
                cache=initial._public_cache(self),
                point_ids=self._cells_observer.ids,
            ),
        )

    def _cells_iteration_start(self, frame):
        observer = self._cells_observer
        observer.iterations_started += 1
        observer.add(
            "refinement_iteration_start",
            dict(
                locals=numeric_locals(frame),
                cache=initial._public_cache(self),
                point_ids=observer.ids,
            ),
        )

    def _cells_iteration_end(self, frame, *, termination):
        observer = self._cells_observer
        observer.iterations_completed += 1
        observer.converged = termination == "converged"
        observer.add(
            "refinement_iteration_end",
            dict(
                termination=termination,
                locals=numeric_locals(frame),
                cache=initial._public_cache(self),
                point_ids=observer.ids,
            ),
        )

    def _cells_move_before(self, policy, *, axis, indices):
        observer = self._cells_observer
        observer.pending_move = dict(policy=policy, axis=axis, indices=indices)
        observer.add(
            "coordinate_update_before",
            dict(
                policy=policy,
                axis=axis,
                indices=indices,
                points=self.tri_verts,
                vor_cents=self.vor_cents if hasattr(self, "vor_cents") else None,
                point_ids=observer.ids,
            ),
        )

    def _cells_move_after(self):
        observer = self._cells_observer
        observer.add(
            "coordinate_update_after",
            dict(
                **observer.pending_move,
                points=self.tri_verts,
                point_ids=observer.ids,
                point_count_preserved=len(self.tri_verts) == len(observer.ids),
            ),
        )
        observer.pending_move = None

    def _cells_pinv(self, matrix, *args, _cells_label, **kwargs):
        observer = self._cells_observer
        observer.add(
            "pinv_input", dict(label=_cells_label, matrix=matrix, args=args, kwargs=kwargs)
        )
        try:
            result = np.linalg.pinv(matrix, *args, **kwargs)
        except Exception as error:
            observer.first_failure = observer.first_failure or "pinv:" + _cells_label
            observer.add(
                "pinv_failure",
                dict(label=_cells_label, failure_type=type(error).__name__, reason=str(error)),
            )
            raise
        observer.add("pinv_output", dict(label=_cells_label, matrix=matrix, result=result))
        return result

    def _cells_dot(self, left, right, *args, _cells_label, **kwargs):
        observer = self._cells_observer
        observer.add(
            "dot_input", dict(label=_cells_label, left=left, right=right, args=args, kwargs=kwargs)
        )
        try:
            result = np.dot(left, right, *args, **kwargs)
        except Exception as error:
            observer.first_failure = observer.first_failure or "dot:" + _cells_label
            observer.add(
                "dot_failure",
                dict(label=_cells_label, failure_type=type(error).__name__, reason=str(error)),
            )
            raise
        observer.add("dot_output", dict(label=_cells_label, left=left, right=right, result=result))
        return result

    def pre_mesh(self):
        observer = self._cells_observer
        if not observer.lifecycle_active:
            return super().pre_mesh()
        observer.rebuild_count += 1
        epoch = observer.rebuild_count
        observer.add(
            "lifecycle_rebuild_enter",
            dict(epoch=epoch, cache=initial._public_cache(self), point_ids=observer.ids),
        )
        try:
            result = super().pre_mesh()
        except Exception as error:
            observer.first_failure = observer.first_failure or "pre_mesh"
            observer.add(
                "lifecycle_rebuild_failure",
                dict(
                    epoch=epoch,
                    cache=initial._public_cache(self),
                    point_ids=observer.ids,
                    failure_type=type(error).__name__,
                    reason=str(error),
                ),
            )
            raise
        observer.add(
            "lifecycle_rebuild_return",
            dict(epoch=epoch, cache=initial._public_cache(self), point_ids=observer.ids),
        )
        return result


def _observe(name, method):
    def invoke(self, *args, **kwargs):
        observer = self._cells_observer
        observer.stack.append(name)
        try:
            bound = inspect.signature(method).bind(self, *args, **kwargs)
            bound.apply_defaults()
            call = {k: v for k, v in bound.arguments.items() if k != "self"}
            observer.add(
                "method_enter",
                dict(
                    call_parameters=call, cache=initial._public_cache(self), point_ids=observer.ids
                ),
            )
            result = method(self, *args, **kwargs)
        except Exception as error:
            observer.first_failure = observer.first_failure or name
            observer.add(
                "method_failure",
                dict(
                    failure_type=type(error).__name__,
                    reason=str(error),
                    cache=initial._public_cache(self),
                    point_ids=observer.ids,
                ),
            )
            raise
        else:
            observer.add(
                "method_return",
                dict(result=result, cache=initial._public_cache(self), point_ids=observer.ids),
            )
            return result
        finally:
            observer.stack.pop()

    return invoke


for _name in METHODS:
    setattr(_Runtime, _name, _observe(_name, getattr(source.LifecycleKernel, _name)))


def state_record(state):
    return dict(
        law=LAW_ID,
        request_identity=state.request_identity,
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
        point_ids_before=state.point_ids_before,
        point_ids_after=state.point_ids_after,
        stream_before=streams.native_stream_manifest(state.stream_before),
        stream_after=streams.native_stream_manifest(state.stream_after),
        termination=json.loads(state.termination_json),
        warnings=state.warnings,
        status=state.status,
        failure_stage=state.failure_stage,
        failure_type=state.failure_type,
        failure_message=state.failure_message,
        topology_qualified=False,
        physical_geometry_admitted=False,
        upstream_initial_qualification="19/22 accuracy qualification open",
    )


def prepare(request):
    validate_request(request)
    base = request.clip_request.initial_request
    saved = streams.native_stream_manifest(base.stream_before)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = _Observer(base.constructor_point_ids)
    kernel = object.__new__(_Runtime)
    kernel._cells_observer, kernel._cells_rng = observer, initial._Random(rng, observer)
    kernel._cells_tools = clipped._Tools(observer)
    kwargs = {
        k: np.array(v, copy=True, order="K") if isinstance(v, np.ndarray) else v
        for k, v in base.constructor_kwargs.items()
    }
    before_cache = caches.snapshot({})
    failure = None
    stage = "upstream_source_replay"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            kernel.__init__(**kwargs)
            kernel.pre_mesh()
            observer.parent_ids = observer.ids
            observer.stage = "clip_to_curve"
            observer.add(
                "clip_continuation_start",
                dict(
                    initial_cache=initial._public_cache(kernel),
                    parent_point_ids=observer.parent_ids,
                ),
            )
            kernel.clip_to_curve(clipped._Mask(clipped.mask_record(request.clip_request), observer))
            before_cache = caches.snapshot(initial._public_cache(kernel))
            stage = "upstream_cache_and_stream_admission"
            if (
                before_cache.identity != request.clip_state.cache.identity
                or observer.ids != request.clip_state.retained_point_ids
                or initial._rng_stream(rng).identity != request.clip_state.stream_after.identity
            ):
                raise ValueError("Replayed clipping cache, occurrence lineage or RNG differs")
            observer.lifecycle_active = True
            observer.before_ids = observer.ids
            observer.stage = stage = "after_clip_lifecycle"
            observer.add(
                "lifecycle_continuation_start",
                dict(
                    cache=initial._public_cache(kernel),
                    point_ids=observer.ids,
                    parameters=parameters(request),
                    origin=request.origin,
                ),
            )
            kernel.after_clip_lifecycle(**parameters(request))
            stage = "lifecycle_finite_and_owner_admission"
            final = caches.snapshot(initial._public_cache(kernel))
            if not final.all_finite or len(kernel.tri_verts) != len(observer.ids):
                raise ValueError("Nonfinite lifecycle result or lost point occurrence axis")
        except Exception as error:
            failure = error
    options = parameters(request)
    termination = dict(
        refinement_requested=options["refinement"],
        smoothing_requested=options["smoothing"],
        iterations_started=observer.iterations_started,
        iterations_completed=observer.iterations_completed,
        source_converged=observer.converged,
        max_steps=options["max_steps"],
        rebuilds=observer.rebuild_count,
        mesh_qual_present=hasattr(kernel, "mesh_qual"),
        no_convergence_claim_from_max_step_completion=True,
    )
    status = (
        "source_lifecycle_completed_unqualified"
        if failure is None
        else "retained_component_admission"
        if stage.endswith("admission")
        else "retained_source_failure"
    )
    result = State(
        request.identity,
        before_cache,
        caches.snapshot(initial._public_cache(kernel)),
        tuple(observer.events),
        observer.before_ids,
        observer.ids,
        request.clip_state.stream_after,
        initial._rng_stream(rng),
        _canonical(termination),
        tuple(str(w.message) for w in caught),
        status,
        (observer.first_failure or stage) if failure is not None else None,
        type(failure).__name__ if failure is not None else None,
        str(failure) if failure is not None else None,
        "",
    )
    result = replace(result, identity=records._digest(state_record(result)))
    if failure is not None:
        raise LifecycleRejected(failure, stage=result.failure_stage, trial=result) from failure
    return result


def validate_state(request, state):
    if type(state) is not State:
        raise ValueError("Require a complete owned lifecycle trial")
    caches.validate(state.before_cache)
    caches.validate(state.cache)
    for event in state.events:
        caches.validate(event.payload)
    expected = prepare(request)
    if state.identity != expected.identity or state_record(state) != state_record(expected):
        raise ValueError("Changed lifecycle operators, source cache age, RNG or point lineage")
    return state


def export_trial(request, state):
    validate_state(request, state)
    return dict(
        kind="cells.native_post_clip_lifecycle_trial@1",
        request=request_record(request),
        state=state_record(state),
        cache=state.cache.descriptor,
        classification="unqualified_native_lifecycle_with_operators",
        topology_qualified=False,
        physical_geometry_admitted=False,
        biological_geometry=False,
        stable_geometry_path=False,
        existing_native_exact_primitives_changed=False,
    )
