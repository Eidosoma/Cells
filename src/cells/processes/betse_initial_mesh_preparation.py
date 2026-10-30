"""Owned constructor and initial pre_mesh trial before clipping/operators.

Static implementation pending qualification. A completed trial is not admitted
by the existing fixed-B09 geometry adapter and carries no biological claim.
"""

import inspect
import json
import warnings
from dataclasses import dataclass, replace
from types import MappingProxyType

import numpy as np
from scipy.spatial import Delaunay, cKDTree

from cells.core.errors import NumericalError
from cells.processes import betse_geometry_initialization as reused
from cells.processes import betse_image_mask_prelude as image_stage
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_initial_mesh_preparation_kernel as source
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

LAW_ID = "betse_initial_constructor_pre_mesh_v1_5_0@1"
MAX_SEED_OCCURRENCES = 132
OBSERVED_METHODS = (
    "__init__",
    "make_single_cell_points",
    "pre_mesh",
    "create_tri_mesh",
    "trimesh_core_calcs",
    "sanity_check",
    "merge_tri_mesh",
    "create_tri_map",
    "process_primary_edges",
    "create_mappings",
    "define_vorverts",
    "process_voredges",
    "area",
    "poly_centroid",
    "circumc",
    "quad_circumc",
    "cc_sort_inds",
)
PRIMITIVES = {"area", "poly_centroid", "circumc", "quad_circumc", "cc_sort_inds"}


@dataclass(frozen=True, slots=True)
class Request:
    origin: str
    upstream: tuple
    constructor_kwargs: object
    source_occurrence_ids: tuple
    constructor_point_ids: tuple
    stream_before: streams.NativeStream
    next_action: str
    identity: str


@dataclass(frozen=True, slots=True)
class Event:
    sequence: int
    kind: str
    method: str
    depth: int
    payload: caches.Cache


@dataclass(frozen=True, slots=True)
class State:
    request_identity: str
    constructed_cache: caches.Cache
    cache: caches.Cache
    events: tuple
    retained_point_ids: tuple
    stream_before: streams.NativeStream
    stream_after_constructor: streams.NativeStream
    stream_after: streams.NativeStream
    warnings: tuple
    constructor_completed: bool
    pre_mesh_completed: bool
    status: str
    failure_stage: str | None
    failure_type: str | None
    failure_message: str | None
    identity: str


class InitialMeshRejected(NumericalError):
    def __init__(self, reason, *, stage, trial=None):
        super().__init__("Initial native mesh refused at " + stage + ": " + str(reason))
        self.stage, self.trial = stage, trial


def _own_layout(value):
    array = np.asarray(value)
    order = "F" if array.flags.f_contiguous and not array.flags.c_contiguous else "C"
    return np.frombuffer(array.tobytes(order=order), dtype=array.dtype).reshape(
        array.shape, order=order
    )


def _source_lattice_points(state):
    # The qualified snapshot owns values in C order. Recreate the original
    # vstack-transpose and subsequent vstack, without drawing or perturbing.
    points = np.vstack((state.values.lattice_points_m[:, 0], state.values.lattice_points_m[:, 1])).T
    bbox = np.array(state.values.bbox_seed_points_m, copy=True, order="C")
    combined = np.vstack((points, bbox))
    if not np.array_equal(combined, state.values.all_seed_points_m):
        raise ValueError("Changed complete source lattice occurrences")
    return _own_layout(combined)


def request_record(request):
    return dict(
        law=LAW_ID,
        origin=request.origin,
        upstream_identities=[value.identity for value in request.upstream],
        constructor_kwargs=request.constructor_kwargs,
        constructor_layouts={
            key: caches.layout(value)
            for key, value in request.constructor_kwargs.items()
            if isinstance(value, np.ndarray)
        },
        source_occurrence_ids=request.source_occurrence_ids,
        constructor_point_ids=request.constructor_point_ids,
        stream_before=streams.native_stream_manifest(request.stream_before),
        next_action=request.next_action,
    )


def from_image_prelude(binding, seed_state, prelude):
    image_stage.validate_prelude(binding, seed_state, prelude)
    kwargs = dict(prelude.constructor_kwargs)
    if kwargs["image_mask"] is not None:
        raise ValueError("The initial native constructor receives no image mask")
    single = json.loads(prelude.controls_json)["single_cell"]
    if single:
        count = kwargs["single_cell_sides"] + 1
        point_ids = tuple(f"{prelude.identity[:16]}-ring-and-centre-{i}" for i in range(count))
    else:
        kwargs["seed_points"] = _source_lattice_points(seed_state)
        point_ids = seed_state.occurrence_ids
    kwargs = {
        key: _own_layout(value) if isinstance(value, np.ndarray) else value
        for key, value in kwargs.items()
    }
    value = Request(
        "owned_image_prelude",
        (binding, seed_state, prelude),
        MappingProxyType(kwargs),
        seed_state.occurrence_ids,
        point_ids,
        prelude.stream,
        "create_core_operators" if single else "clip_to_curve(owned_image_mask)",
        "",
    )
    return replace(value, identity=records._digest(request_record(value)))


def from_reused_B09(initialization):
    """Reuse fixed reviewed input/evidence, without new B09 coverage credit."""
    reused.validate_initialization(initialization)
    raw = json.loads(initialization.recipe_json)["native_input"]
    kwargs = dict(raw["mesh"])
    kwargs["seed_points"] = (
        None
        if raw["seed_points_m"] is None
        else _own_layout(np.asarray(raw["seed_points_m"], dtype=np.float64))
    )
    value = Request(
        "reused_fixed_B09",
        (initialization,),
        MappingProxyType(kwargs),
        initialization.seed_state.seed_ids,
        initialization.seed_state.seed_ids,
        initialization.seed_state.stream_before,
        "create_core_operators",
        "",
    )
    return replace(value, identity=records._digest(request_record(value)))


def validate_request(request):
    if type(request) is not Request:
        raise ValueError("Require an authenticated initial-mesh request")
    if request.origin == "owned_image_prelude":
        expected = from_image_prelude(*request.upstream)
    elif request.origin == "reused_fixed_B09":
        expected = from_reused_B09(*request.upstream)
    else:
        raise ValueError("Unknown initial-mesh input provenance")
    if (
        records.record(request_record(request)) != records.record(request_record(expected))
        or request.identity != expected.identity
    ):
        raise ValueError("Changed constructor input, occurrence order, layout or RNG state")
    if not 1 <= len(request.constructor_point_ids) <= MAX_SEED_OCCURRENCES:
        raise ValueError("Constructor exceeds the bounded occurrence axis")
    if len(set(request.constructor_point_ids)) != len(request.constructor_point_ids):
        raise ValueError("Constructor occurrence IDs must remain distinct")
    return request


def _rng_stream(rng):
    saved = rng.get_state()
    return streams._native_stream(
        [saved[0], saved[1].tolist(), int(saved[2]), int(saved[3]), float(saved[4])],
        np.__version__,
    )


def _public_cache(kernel):
    return {key: value for key, value in vars(kernel).items() if not key.startswith("_cells_")}


class _Observer:
    def __init__(self, ids):
        self.ids, self.events, self.stack = tuple(ids), [], []

    def add(self, kind, payload):
        self.events.append(
            Event(
                len(self.events),
                kind,
                self.stack[-1] if self.stack else "driver",
                len(self.stack),
                caches.snapshot(payload),
            )
        )


class _Random:
    def __init__(self, rng, observer):
        self.rng, self.observer = rng, observer

    def random(self, size):
        before = streams.native_stream_manifest(_rng_stream(self.rng))["state"]
        values = self.rng.random(size)
        self.observer.add(
            "uniform_draw",
            dict(
                size=size,
                values=values,
                rng_before=before,
                rng_after=streams.native_stream_manifest(_rng_stream(self.rng))["state"],
            ),
        )
        return values


class _Tree:
    def __init__(self, data, observer):
        self.tree, self.data, self.observer = cKDTree(data), data, observer

    def query(self, points, *args, **kwargs):
        try:
            result = self.tree.query(points, *args, **kwargs)
        except Exception as error:
            self.observer.add(
                "nearest_failure",
                dict(
                    data=self.data,
                    points=points,
                    args=args,
                    kwargs=kwargs,
                    failure_type=type(error).__name__,
                    reason=str(error),
                ),
            )
            raise
        self.observer.add(
            "nearest_query",
            dict(
                data=self.data,
                native_tree_data=self.tree.data,
                points=points,
                args=args,
                kwargs=kwargs,
                result=result,
            ),
        )
        return result


class _Runtime(source.Kernel):
    def _cells_log(self, level, *args):
        self._cells_observer.add("native_log", dict(level=level, args=args))

    def _cells_tree(self, data):
        observer = self._cells_observer
        observer.add("tree_input", dict(data=data))
        try:
            value = _Tree(data, observer)
        except Exception as error:
            observer.add("tree_failure", dict(failure_type=type(error).__name__, reason=str(error)))
            raise
        observer.add("tree_created", dict(native_tree_data=value.tree.data))
        return value

    def _cells_delaunay(self, points):
        observer = self._cells_observer
        observer.add("delaunay_input", dict(points=points, point_ids=observer.ids))
        try:
            value = Delaunay(points)
        except Exception as error:
            observer.add(
                "delaunay_failure", dict(failure_type=type(error).__name__, reason=str(error))
            )
            raise
        observer.add(
            "delaunay_output",
            dict(
                points=value.points,
                simplices=value.simplices,
                neighbors=value.neighbors,
                coplanar=value.coplanar,
                convex_hull=value.convex_hull,
                point_ids=observer.ids,
            ),
        )
        return value

    def _cells_delete_seed_rows(self, indices, *, axis, cause):
        observer = self._cells_observer
        old = observer.ids
        result = np.delete(self.tri_verts, indices, axis=axis)
        if axis != 0 or len(old) != len(self.tri_verts):
            raise ValueError("Source deletion lost its occurrence axis")
        retained = np.delete(np.arange(len(old)), indices, axis=0)
        new = tuple(old[int(i)] for i in retained)
        observer.add(
            "source_row_deletion",
            dict(
                cause=cause,
                indices=indices,
                input_points=self.tri_verts,
                output_points=result,
                point_ids_before=old,
                point_ids_after=new,
                removed_ids=tuple(name for i, name in enumerate(old) if i not in retained),
            ),
        )
        observer.ids = new
        return result


def _observe(name, method):
    def invoke(self, *args, **kwargs):
        observer = self._cells_observer
        observer.stack.append(name)
        primitive = name in PRIMITIVES
        try:
            parameters = inspect.signature(method).bind(self, *args, **kwargs)
            parameters.apply_defaults()
            call = {key: value for key, value in parameters.arguments.items() if key != "self"}
            observer.add(
                "method_enter",
                dict(call_parameters=call)
                if primitive
                else dict(cache=_public_cache(self), point_ids=observer.ids, call_parameters=call),
            )
            value = method(self, *args, **kwargs)
        except Exception as error:
            observer.add(
                "method_failure",
                dict(
                    failure_type=type(error).__name__,
                    reason=str(error),
                    cache=_public_cache(self),
                    point_ids=observer.ids,
                ),
            )
            raise
        else:
            observer.add(
                "method_return",
                dict(result=value)
                if primitive
                else dict(cache=_public_cache(self), point_ids=observer.ids),
            )
            return value
        finally:
            observer.stack.pop()

    return invoke


for _method in OBSERVED_METHODS:
    setattr(_Runtime, _method, _observe(_method, getattr(source.Kernel, _method)))


def state_record(state):
    return dict(
        law=LAW_ID,
        request_identity=state.request_identity,
        constructed_cache=state.constructed_cache.identity,
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
        retained_point_ids=state.retained_point_ids,
        stream_before=streams.native_stream_manifest(state.stream_before),
        stream_after_constructor=streams.native_stream_manifest(state.stream_after_constructor),
        stream_after=streams.native_stream_manifest(state.stream_after),
        warnings=state.warnings,
        status=state.status,
        constructor_completed=state.constructor_completed,
        pre_mesh_completed=state.pre_mesh_completed,
        failure_stage=state.failure_stage,
        failure_type=state.failure_type,
        failure_message=state.failure_message,
    )


def prepare(request):
    validate_request(request)
    saved = streams.native_stream_manifest(request.stream_before)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = _Observer(request.constructor_point_ids)
    kernel = object.__new__(_Runtime)
    kernel._cells_observer, kernel._cells_rng = observer, _Random(rng, observer)
    kwargs = {
        key: np.array(value, copy=True, order="K") if isinstance(value, np.ndarray) else value
        for key, value in request.constructor_kwargs.items()
    }
    stage, failure = "constructor", None
    constructor_completed = pre_mesh_completed = False
    constructed = caches.snapshot({})
    after_constructor = request.stream_before
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            kernel.__init__(**kwargs)
            constructor_completed = True
            constructed = caches.snapshot(_public_cache(kernel))
            after_constructor = _rng_stream(rng)
            if len(kernel.tri_verts) != len(observer.ids):
                raise ValueError("Constructor changed its declared occurrence count")
            if not constructed.all_finite:
                stage = "constructor_finite_admission"
                raise ValueError("Nonfinite native constructor trial")
            stage = "pre_mesh"
            kernel.pre_mesh()
            pre_mesh_completed = True
            if not caches.snapshot(_public_cache(kernel)).all_finite:
                stage = "pre_mesh_finite_admission"
                raise ValueError("Nonfinite initial native mesh trial")
        except Exception as error:
            if not constructor_completed:
                constructed = caches.snapshot(_public_cache(kernel))
                after_constructor = _rng_stream(rng)
            failure = error
    value = State(
        request.identity,
        constructed,
        caches.snapshot(_public_cache(kernel)),
        tuple(observer.events),
        observer.ids,
        request.stream_before,
        after_constructor,
        _rng_stream(rng),
        tuple(str(w.message) for w in caught),
        constructor_completed,
        pre_mesh_completed,
        "source_completed_unqualified"
        if failure is None
        else (
            "retained_component_finite_admission"
            if stage.endswith("finite_admission")
            else "retained_source_failure"
        ),
        stage if failure is not None else None,
        type(failure).__name__ if failure is not None else None,
        str(failure) if failure is not None else None,
        "",
    )
    value = replace(value, identity=records._digest(state_record(value)))
    if failure is not None:
        raise InitialMeshRejected(failure, stage=stage, trial=value) from failure
    return value


def validate_state(request, value):
    if type(value) is not State:
        raise ValueError("Require complete owned initial-mesh state")
    caches.validate(value.constructed_cache)
    caches.validate(value.cache)
    for event in value.events:
        caches.validate(event.payload)
    expected = prepare(request)
    if value.identity != expected.identity or state_record(value) != state_record(expected):
        raise ValueError("Changed source caches, topology, occurrence ledger or RNG continuation")
    return value


def export_trial(request, value):
    """Typed cache manifest; no conversion into the fixed-B09 geometry adapter."""
    validate_state(request, value)
    return dict(
        kind="cells.betse_initial_pre_mesh_trial@1",
        law_id=LAW_ID,
        request=request_record(request),
        state=state_record(value),
        constructed_cache=value.constructed_cache.descriptor,
        cache=value.cache.descriptor,
        events=[
            dict(
                sequence=e.sequence,
                kind=e.kind,
                method=e.method,
                depth=e.depth,
                payload=e.payload.descriptor,
            )
            for e in value.events
        ],
        identity=value.identity,
        classification="unqualified_native_initial_mesh_buffers",
        topology_qualified=False,
        downstream_geometry_admitted=False,
        image_clip_executed=False,
        operators_created=False,
        biological_geometry=False,
        B09_coverage_reused=request.origin == "reused_fixed_B09",
    )
