"""Owned native clip-to-curve continuation; source trials remain unqualified.

Initial-mesh accuracy qualification is still open. This boundary admits only
an owned successful source trial and its original image, without promoting the
topology or the rebuilt polygons into physical geometry.
"""

import inspect
import warnings
from dataclasses import dataclass, replace

import numpy as np
from scipy.interpolate import RectBivariateSpline

from cells.core.errors import NumericalError
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_mesh_clip_preparation_kernel as source
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

LAW_ID = "betse_owned_clip_to_curve_preparation_v1_5_0@1"
OBSERVED_TOOLS = (
    "clip_counterclockwise",
    "orient_counterclockwise",
    "is_left_of_vector",
    "intersect_lines",
)


@dataclass(frozen=True, slots=True)
class Request:
    initial_request: initial.Request
    initial_state: initial.State
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    request_identity: str
    initial_cache: caches.Cache
    cache: caches.Cache
    events: tuple
    parent_point_ids: tuple
    derived_point_ids_before_rebuild: tuple
    retained_point_ids: tuple
    stream_after_initial: streams.NativeStream
    stream_after: streams.NativeStream
    warnings: tuple
    status: str
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class ClipRejected(NumericalError):
    def __init__(self, error, *, stage, trial=None):
        super().__init__("Native clipping refused at " + stage + ": " + str(error))
        self.stage, self.trial = stage, trial


def request_record(request):
    return dict(
        law=LAW_ID,
        initial_request_identity=request.initial_request.identity,
        initial_state_identity=request.initial_state.identity,
        image_prelude_identity=request.initial_request.upstream[2].identity,
        upstream_qualification="initial_mesh_accuracy_qualification_open",
        topology_qualified=False,
        downstream_geometry_admitted=False,
    )


def from_initial_mesh(request, state):
    initial.validate_request(request)
    if request.origin != "owned_image_prelude" or request.constructor_kwargs["seed_points"] is None:
        raise ValueError("Only the non-SVG multi-cell caller continues into image clipping")
    initial.validate_state(request, state)
    if state.status != "source_completed_unqualified" or not state.cache.all_finite:
        raise ValueError("Require a complete finite owned initial source trial")
    result = Request(request, state, "")
    return replace(result, identity=records._digest(request_record(result)))


def validate_request(request):
    if type(request) is not Request:
        raise ValueError("Require the owned initial trial and its original image")
    expected = from_initial_mesh(request.initial_request, request.initial_state)
    if request.identity != expected.identity or request_record(request) != request_record(expected):
        raise ValueError("Changed initial source state or image provenance")
    return request


def mask_record(request):
    prelude = request.initial_request.upstream[2]
    fields = prelude.values
    return dict(
        kind="owned_image_prelude_mask_token",
        identity=prelude.identity,
        image_identity=prelude.image.identity,
        xpts_m=fields.xpts_m,
        ypts_m=fields.ypts_m,
        clipping_matrix=fields.clipping_matrix,
        clipcurve_m=fields.clipcurve_m,
    )


def numeric_locals(frame):
    return {
        key: value
        for key, value in frame.items()
        if key not in ("self", "imagemask", "nparray") and not key.startswith("_cells_")
    }


class _Observer(initial._Observer):
    def __init__(self, ids):
        super().__init__(ids)
        self.stage = "initial_source_replay"
        self.parent_ids, self.derived_ids, self.selected = (), (), []
        self.current_cell, self.query_count = None, 0

    def cell_enter(self, ii, poly_ind, cell_poly, vor_cent):
        self.current_cell, self.query_count = int(ii), 0
        self.add(
            "clip_cell_enter",
            dict(
                source_cell_index=ii,
                parent_id=self.parent_ids[ii],
                poly_ind=poly_ind,
                cell_poly=cell_poly,
                vor_cent=vor_cent,
            ),
        )

    def cell_exit(self, frame):
        locals_ = numeric_locals(frame)
        ii = int(frame["ii"])
        count = len(frame["clip_vor_cents"])
        if count != len(self.selected):
            if count != len(self.selected) + 1:
                raise ValueError("Source emitted more than one centroid for a parent cell")
            parent = self.parent_ids[ii]
            point_id = parent + "/native-clip-centroid"
            branch = (
                "all_vertices_nonzero"
                if frame["point_check"].sum() == len(frame["cell_poly"])
                else "partial_with_nonzero_centre"
            )
            self.selected.append(point_id)
            self.add(
                "clip_centroid_emitted",
                dict(
                    source_cell_index=ii,
                    parent_id=parent,
                    point_id=point_id,
                    branch=branch,
                    centroid=frame["clip_vor_cents"][-1],
                    polygon=frame["clip_vor_verts"][-1],
                ),
            )
        self.add("clip_cell_exit", dict(source_cell_index=ii, locals=locals_))
        self.current_cell = None

    def centroids_replaced(self, polygons, centroids):
        self.derived_ids = tuple(self.selected)
        if len(centroids) != len(self.derived_ids):
            raise ValueError("Lost source centroid emission order")
        self.add(
            "clip_seed_replacement",
            dict(
                parent_point_ids=self.parent_ids,
                derived_point_ids=self.derived_ids,
                clipped_polygons=polygons,
                centroid_seed_points=centroids,
                note="Polygons are source locals; the following mesh is rebuilt from centroids",
            ),
        )
        self.ids = self.derived_ids
        self.current_cell = None
        self.query_count = 0
        self.stage = "masked_pre_mesh_rebuild"


class _Mask(dict):
    def __init__(self, values, observer):
        super().__init__(values)
        self._observer = observer
        self.clipcurve = values["clipcurve_m"]
        self._function = RectBivariateSpline(
            values["xpts_m"], values["ypts_m"], values["clipping_matrix"].T, kx=1, ky=1
        )

    def clipping_function(self, x, y):
        value = self._function(x, y).T
        observer = self._observer
        role = (
            ("centre" if observer.query_count == 0 else "vertex")
            if observer.current_cell is not None
            else "rebuild_circumcentre"
        )
        observer.add(
            "mask_query",
            dict(
                x=x,
                y=y,
                result=value,
                role=role,
                source_cell_index=observer.current_cell,
                cell_query_index=observer.query_count,
                within_closed_window=bool(
                    self["xpts_m"][0] <= x <= self["xpts_m"][-1]
                    and self["ypts_m"][0] <= y <= self["ypts_m"][-1]
                ),
            ),
        )
        observer.query_count += 1
        return value


class _Tools(source.Tools):
    def __init__(self, observer):
        self._cells_observer = observer

    def _cells_edge(self, frame):
        self._cells_observer.add("clip_half_plane", dict(locals=numeric_locals(frame)))

    def _cells_partial(self, frame):
        self._cells_observer.add("clip_partial_locals", dict(locals=numeric_locals(frame)))

    def _cells_return_locals(self, frame):
        self._cells_observer.add("geometry_return_locals", dict(locals=numeric_locals(frame)))


class _Runtime(source.ClipKernel, initial._Runtime):
    def _cells_cell_enter(self, *args):
        self._cells_observer.cell_enter(*args)

    def _cells_cell_exit(self, frame):
        self._cells_observer.cell_exit(frame)

    def _cells_centroids_replaced(self, polygons, centroids):
        self._cells_observer.centroids_replaced(polygons, centroids)

    def _cells_partial(self, frame):
        self._cells_observer.add("clip_partial_locals", dict(locals=numeric_locals(frame)))

    def _cells_return_locals(self, frame):
        self._cells_observer.add("geometry_return_locals", dict(locals=numeric_locals(frame)))


def _observe(name, method):
    def invoke(self, *args, **kwargs):
        observer = self._cells_observer
        observer.stack.append(name)
        parameters = inspect.signature(method).bind(self, *args, **kwargs)
        parameters.apply_defaults()
        call = {key: value for key, value in parameters.arguments.items() if key != "self"}
        observer.add("method_enter", dict(call_parameters=call))
        try:
            value = method(self, *args, **kwargs)
        except Exception as error:
            observer.add(
                "method_failure",
                dict(failure_type=type(error).__name__, reason=str(error), call_parameters=call),
            )
            raise
        else:
            observer.add("method_return", dict(result=value))
            return value
        finally:
            observer.stack.pop()

    return invoke


for _name in OBSERVED_TOOLS:
    setattr(_Tools, _name, _observe(_name, getattr(source.Tools, _name)))
for _name in ("clip_to_curve", "search_point_cloud"):
    setattr(_Runtime, _name, _observe(_name, getattr(source.ClipKernel, _name)))


def state_record(state):
    return dict(
        law=LAW_ID,
        request_identity=state.request_identity,
        initial_cache=state.initial_cache.identity,
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
        parent_point_ids=state.parent_point_ids,
        derived_point_ids_before_rebuild=state.derived_point_ids_before_rebuild,
        retained_point_ids=state.retained_point_ids,
        stream_after_initial=streams.native_stream_manifest(state.stream_after_initial),
        stream_after=streams.native_stream_manifest(state.stream_after),
        warnings=state.warnings,
        status=state.status,
        failure_stage=state.failure_stage,
        failure_type=state.failure_type,
        failure_message=state.failure_message,
        topology_qualified=False,
        downstream_geometry_admitted=False,
    )


def prepare(request):
    validate_request(request)
    upstream = request.initial_request
    saved = streams.native_stream_manifest(upstream.stream_before)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = _Observer(upstream.constructor_point_ids)
    kernel = object.__new__(_Runtime)
    kernel._cells_observer, kernel._cells_rng = observer, initial._Random(rng, observer)
    kernel._cells_tools = _Tools(observer)
    kwargs = {
        key: np.array(value, copy=True, order="K") if isinstance(value, np.ndarray) else value
        for key, value in upstream.constructor_kwargs.items()
    }
    initial_cache = caches.snapshot({})
    after_initial, failure = upstream.stream_before, None
    stage = "initial_source_replay"
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            kernel.__init__(**kwargs)
            kernel.pre_mesh()
            initial_cache = caches.snapshot(initial._public_cache(kernel))
            after_initial = initial._rng_stream(rng)
            stage = "upstream_cache_and_stream_admission"
            if (
                initial_cache.identity != request.initial_state.cache.identity
                or after_initial.identity != request.initial_state.stream_after.identity
                or observer.ids != request.initial_state.retained_point_ids
            ):
                raise ValueError("Replayed initial source cache, identity ledger or RNG differs")
            observer.parent_ids = observer.ids
            observer.stage = stage = "clip_to_curve"
            observer.add(
                "clip_continuation_start",
                dict(
                    initial_cache=initial._public_cache(kernel),
                    parent_point_ids=observer.parent_ids,
                ),
            )
            kernel.clip_to_curve(_Mask(mask_record(request), observer))
            stage = "clipped_rebuild_finite_admission"
            if not caches.snapshot(initial._public_cache(kernel)).all_finite:
                raise ValueError("Nonfinite source clipped-rebuild trial")
        except Exception as error:
            failure = error
            if stage == "clip_to_curve":
                stage = observer.stage
    result = State(
        request.identity,
        initial_cache,
        caches.snapshot(initial._public_cache(kernel)),
        tuple(observer.events),
        observer.parent_ids,
        observer.derived_ids,
        observer.ids,
        after_initial,
        initial._rng_stream(rng),
        tuple(str(w.message) for w in caught),
        "source_clipped_rebuilt_unqualified"
        if failure is None
        else "retained_component_finite_admission"
        if stage.endswith("finite_admission")
        else "retained_component_upstream_admission"
        if stage == "upstream_cache_and_stream_admission"
        else "retained_source_failure",
        stage if failure else None,
        type(failure).__name__ if failure else None,
        str(failure) if failure else None,
        "",
    )
    result = replace(result, identity=records._digest(state_record(result)))
    if failure is not None:
        raise ClipRejected(failure, stage=stage, trial=result) from failure
    return result


def validate_state(request, state):
    if type(state) is not State:
        raise ValueError("Require a complete owned clipped-rebuild trial")
    caches.validate(state.initial_cache)
    caches.validate(state.cache)
    for event in state.events:
        caches.validate(event.payload)
    expected = prepare(request)
    if state.identity != expected.identity or state_record(state) != state_record(expected):
        raise ValueError("Changed source clipping traces, cache or centroid lineage")
    return state


def export_trial(request, state):
    validate_state(request, state)
    return dict(
        kind="cells.native_clipped_rebuild_trial@1",
        request=request_record(request),
        state=state_record(state),
        cache=state.cache.descriptor,
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=e.payload.descriptor,
            )
            for e in state.events
        ],
        classification="unqualified_source_clipped_centroid_rebuild",
        topology_qualified=False,
        downstream_geometry_admitted=False,
        final_polygons_are_exact_clipped_polygons=False,
        operators_created=False,
        refinement_executed=False,
        biological_geometry=False,
    )
