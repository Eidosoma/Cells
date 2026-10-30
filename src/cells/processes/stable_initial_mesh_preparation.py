"""Explicit candidate bridge from stable primitives to the initial mesh.

Only three primitive callees change arithmetic. All constructor, ordering,
topology and cache operations still use the frozen initial-mesh kernel. This
separate law has no physical-adapter authority.
"""

import hashlib
import warnings
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_geometry_initialization as physical
from cells.processes import betse_initial_mesh_preparation as initial
from cells.processes import betse_initial_mesh_preparation_cache as caches
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams
from cells.processes import stable_geometry_primitives as primitives

LAW_ID = "cells_stable_initial_constructor_pre_mesh@1"
REQUEST_KIND = "cells.stable_initial_mesh_request@1"
STATE_KIND = "cells.stable_initial_mesh_trial@1"
MAX_SEED_OCCURRENCES = 64
REPAIRED_METHODS = ("area", "poly_centroid", "circumc")
PRIMITIVES_BUNDLE_SHA256 = "71add3636c486e9a2ec2f6690ed1b48a51c4011f6ded3d3da4e49e8f1dbb55b8"
SOURCE_PINS = (
    (
        "stable_geometry_primitives",
        "c9fab4f34aa9166711431844f2af72eb6b8fe4873154bfe01dfce3f656326958",
    ),
    (
        "betse_initial_mesh_preparation",
        "ef33e60ea5cd741d3618bccaaba494ac472664b02f4c82d08942b3e2c52c89b0",
    ),
    (
        "betse_initial_mesh_preparation_kernel",
        "7102de6bae1f5da0ecb5c99064ffa03b26e20b2b7b8855b72f5066fd20a0089c",
    ),
    (
        "betse_geometry_initialization",
        "9035c4dba445292010821eb871970cbb3348fdfedd0d597459ccfe6adb1234de",
    ),
)


@dataclass(frozen=True, slots=True)
class Request:
    native_request: initial.Request
    opted_in_law: str
    identity: str


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


class StableMeshRejected(NumericalError):
    def __init__(self, reason, *, stage, trial=None):
        super().__init__("Stable initial mesh refused at " + stage + ": " + str(reason))
        self.stage, self.trial = stage, trial


def _verify_sources():
    modules = (primitives, initial, initial.source, physical)
    for (name, expected), module in zip(SOURCE_PINS, modules, strict=True):
        if module.__name__.rsplit(".", 1)[-1] != name:
            raise ValueError("Changed bridge source ownership: " + name)
        if hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest() != expected:
            raise ValueError("Changed frozen bridge dependency: " + name)
    if primitives.LAW_ID != "cells_stable_binary64_geometry_primitives@1":
        raise ValueError("Changed primitive law")


def request_record(request):
    return dict(
        kind=REQUEST_KIND,
        law=LAW_ID,
        opted_in_law=request.opted_in_law,
        native_request_identity=request.native_request.identity,
        native_request=initial.request_record(request.native_request),
        primitive_law=primitives.LAW_ID,
        primitive_bundle_sha256=PRIMITIVES_BUNDLE_SHA256,
        dependency_source_sha256=dict(SOURCE_PINS),
        repaired_methods=REPAIRED_METHODS,
        maximum_seed_occurrences=MAX_SEED_OCCURRENCES,
        exact_native_arithmetic_equivalence=False,
        physical_geometry_admitted=False,
    )


def opt_in(native_request, *, law_id):
    """Require an explicit law token and the original authenticated admission."""
    if type(law_id) is not str or law_id != LAW_ID:
        raise ValueError("Explicit stable initial-mesh law opt-in required")
    _verify_sources()
    initial.validate_request(native_request)
    if len(native_request.constructor_point_ids) > MAX_SEED_OCCURRENCES:
        raise ValueError("Stable initial bridge exceeds 64 seed occurrences")
    value = Request(native_request, law_id, "")
    return replace(value, identity=records._digest(request_record(value)))


def validate_request(request):
    if type(request) is not Request:
        raise ValueError("Require a distinct opted-in stable initial-mesh request")
    expected = opt_in(request.native_request, law_id=request.opted_in_law)
    if request.identity != expected.identity or records.record(
        request_record(request)
    ) != records.record(request_record(expected)):
        raise ValueError("Changed stable initial-mesh request")
    return request


def _repair(kernel, method, parameters):
    observer = kernel._cells_observer
    observer.add("primitive_repair_input", dict(method=method, call_parameters=parameters))
    primitive_request = None
    try:
        points = (
            parameters["p"]
            if method != "circumc"
            else np.asarray([parameters[k] for k in ("A", "B", "C")])
        )
        if (
            not isinstance(points, np.ndarray)
            or points.dtype != np.dtype("float64")
            or points.ndim != 2
            or points.shape[1] != 2
        ):
            raise ValueError("Repair boundary requires the original binary64 point array")
        primitive_request = primitives.make_request(
            "triangle" if method == "circumc" else "polygon",
            tuple(tuple(float(value) for value in row) for row in points),
        )
        result = primitives.prepare(primitive_request)
        values = result.values
        names = {
            "area": ("signed_area_m2",),
            "poly_centroid": ("centroid_x_m", "centroid_y_m"),
            "circumc": ("circumcenter_x_m", "circumcenter_y_m", "circumradius_m", "inradius_m"),
        }[method]
        # The native methods return NumPy float64 scalars, including tuple members.
        output = tuple(np.float64(values[name]) for name in names)
        output = output[0] if method == "area" else output
    except Exception as error:
        observer.add(
            "primitive_repair_failure",
            dict(
                method=method,
                request=None
                if primitive_request is None
                else primitives.request_record(primitive_request),
                failure_type=type(error).__name__,
                reason=str(error),
                code=getattr(error, "code", None),
                stage=getattr(error, "stage", None),
                trial=getattr(error, "trial", None),
            ),
        )
        raise
    observer.add(
        "primitive_repair_result",
        dict(
            method=method,
            request=primitives.request_record(primitive_request),
            request_identity=primitive_request.identity,
            result=primitives.result_record(result),
            result_identity=result.identity,
            adapter_output=output,
        ),
    )
    return output


class _Runtime(initial._Runtime):
    def area(self, p):
        return _repair(self, "area", dict(p=p))

    def poly_centroid(self, p):
        return _repair(self, "poly_centroid", dict(p=p))

    def circumc(self, A, B, C):
        return _repair(self, "circumc", dict(A=A, B=B, C=C))


for _name in REPAIRED_METHODS:
    setattr(_Runtime, _name, initial._observe(_name, getattr(_Runtime, _name)))


def state_record(state):
    # Reuse the complete original cache/event/RNG ledger, changing its law.
    value = initial.state_record(state)
    return dict(
        value,
        kind=STATE_KIND,
        law=LAW_ID,
        primitive_law=primitives.LAW_ID,
        primitive_bundle_sha256=PRIMITIVES_BUNDLE_SHA256,
        dependency_source_sha256=dict(SOURCE_PINS),
        exact_native_arithmetic_equivalence=False,
        conditional_source_replay_required=True,
        independent_whole_mesh_checks_required=True,
        physical_geometry_admitted=False,
    )


def prepare(request):
    validate_request(request)
    native_request = request.native_request
    saved = streams.native_stream_manifest(native_request.stream_before)["state"]
    rng = np.random.RandomState(0)
    rng.set_state((saved[0], np.asarray(saved[1], dtype=np.uint32), saved[2], saved[3], saved[4]))
    observer = initial._Observer(native_request.constructor_point_ids)
    kernel = object.__new__(_Runtime)
    kernel._cells_observer, kernel._cells_rng = observer, initial._Random(rng, observer)
    kwargs = {
        key: np.array(value, copy=True, order="K") if isinstance(value, np.ndarray) else value
        for key, value in native_request.constructor_kwargs.items()
    }
    stage, failure = "constructor", None
    constructor_completed = pre_mesh_completed = False
    constructed = caches.snapshot({})
    after_constructor = native_request.stream_before
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        try:
            kernel.__init__(**kwargs)
            constructor_completed = True
            constructed = caches.snapshot(initial._public_cache(kernel))
            after_constructor = initial._rng_stream(rng)
            if len(kernel.tri_verts) != len(observer.ids):
                raise ValueError("Constructor changed its declared occurrence count")
            if not constructed.all_finite:
                stage = "constructor_finite_admission"
                raise ValueError("Nonfinite stable constructor trial")
            stage = "pre_mesh"
            kernel.pre_mesh()
            pre_mesh_completed = True
            if not caches.snapshot(initial._public_cache(kernel)).all_finite:
                stage = "pre_mesh_finite_admission"
                raise ValueError("Nonfinite stable initial mesh trial")
        except Exception as error:
            if not constructor_completed:
                constructed = caches.snapshot(initial._public_cache(kernel))
                after_constructor = initial._rng_stream(rng)
            failure = error
    value = State(
        request.identity,
        constructed,
        caches.snapshot(initial._public_cache(kernel)),
        tuple(observer.events),
        observer.ids,
        native_request.stream_before,
        after_constructor,
        initial._rng_stream(rng),
        tuple(str(w.message) for w in caught),
        constructor_completed,
        pre_mesh_completed,
        "stable_mesh_completed_unqualified" if failure is None else "retained_stable_mesh_failure",
        stage if failure is not None else None,
        type(failure).__name__ if failure is not None else None,
        str(failure) if failure is not None else None,
        "",
    )
    value = replace(value, identity=records._digest(state_record(value)))
    if failure is not None:
        raise StableMeshRejected(failure, stage=stage, trial=value) from failure
    return value


def validate_state(request, value):
    validate_request(request)
    if type(value) is not State or value.request_identity != request.identity:
        raise ValueError("Require an owned stable initial-mesh state")
    for cache in (value.constructed_cache, value.cache, *(e.payload for e in value.events)):
        caches.validate(cache)
    expected = prepare(request)
    if value.identity != expected.identity or state_record(value) != state_record(expected):
        raise ValueError("Changed stable mesh caches, primitive certificates or occurrence ledger")
    return value


def export_trial(request, value):
    validate_state(request, value)
    return dict(
        kind=STATE_KIND,
        law_id=LAW_ID,
        request=request_record(request),
        state=state_record(value),
        identity=value.identity,
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
        classification="unqualified_stable_arithmetic_initial_mesh",
        topology_qualified=False,
        downstream_geometry_admitted=False,
        image_clip_executed=False,
        operators_created=False,
        biological_geometry=False,
        original_failed_campaign_reclassified=False,
    )
