"""Owned image mask and make_voronoi call preparation, before any mesh call.

Static implementation pending qualification. The file bytes, decoded pixels,
lattice bounds and native branch arguments remain distinct provenance records.
"""

import hashlib
import io
import json
import math
import os
from dataclasses import dataclass, replace
from importlib import metadata
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

import numpy as np
from PIL import Image
from scipy.interpolate import RectBivariateSpline
from scipy.spatial import ConvexHull

from cells.core.errors import NumericalError
from cells.processes import betse_environment_field as arrays
from cells.processes import betse_lattice_seed_generation as lattice
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

LAW_ID = "betse_image_mask_make_voronoi_prelude_v1_5_0@1"
IMAGE_KIND = "cells.betse_image_mask_source@1"
CONTROLS_KIND = "cells.betse_make_voronoi_controls@1"
MAX_IMAGE_BYTES = 2**20
MAX_IMAGE_SIDE = 32
MAX_QUERY_POINTS = 128


@dataclass(frozen=True, slots=True)
class ImageSource:
    definition_json: str
    native_filename: str
    resolved_filename: str
    file_bytes: bytes
    file_sha256: str
    input_mode: str
    bitmap: object
    pillow_version: str
    identity: str


class MaskValues(NamedTuple):
    bitmap: object
    clipping_matrix: object
    xpts_m: object
    ypts_m: object
    active_grid_indices: object
    active_points_m: object
    hull_indices: object
    clipcurve_m: object
    linear_knots_x_m: object
    linear_knots_y_m: object
    linear_coefficients: object
    fast_knots_x_m: object
    fast_knots_y_m: object
    fast_coefficients: object


@dataclass(frozen=True, slots=True)
class Prelude:
    lattice_binding_identity: str
    lattice_state_identity: str
    image: ImageSource
    controls_json: str
    stream: streams.NativeStream
    values: MaskValues
    active_file_pixel_ids: tuple
    constructor_kwargs: object
    next_method: str
    next_kwargs: object
    identity: str


class ImagePreludeRejected(NumericalError):
    def __init__(self, reason, *, stage, trial=None):
        super().__init__("Native image prelude refused at " + stage + ": " + str(reason))
        self.stage, self.trial = stage, trial


def _decode(data):
    with Image.open(io.BytesIO(data)) as image:
        if max(image.size) > MAX_IMAGE_SIDE:
            raise ValueError("Image exceeds the bounded pixel admission")
        original_mode = image.mode
        # Native compares an enum with a string, so the requested F conversion
        # is performed even when the input image is already F.
        bitmap = np.array(image.convert("F"))
    return original_mode, bitmap


def image_record(image):
    return dict(
        definition=json.loads(image.definition_json),
        native_filename=image.native_filename,
        resolved_filename=image.resolved_filename,
        file_sha256=image.file_sha256,
        byte_count=len(image.file_bytes),
        input_mode=image.input_mode,
        output_mode="F",
        bitmap=image.bitmap,
        pillow_version=image.pillow_version,
    )


def capture_image(raw):
    """Read a declared file once, then own and decode its authenticated bytes."""
    trial = None
    try:
        if (
            type(raw) is not dict
            or set(raw) != {"kind", "filename", "conf_dirname", "image_sha256"}
            or raw["kind"] != IMAGE_KIND
            or any(
                type(raw[key]) is not str for key in ("filename", "conf_dirname", "image_sha256")
            )
            or not raw["filename"]
            or len(raw["image_sha256"]) != 64
        ):
            raise ValueError("Require an explicit image file and content digest")
        filename = raw["filename"]
        if not os.path.isabs(filename):
            if not os.path.isabs(raw["conf_dirname"]):
                raise ValueError("Relative image names require an absolute configuration directory")
            filename = os.path.join(raw["conf_dirname"], filename)
        path = Path(filename)
        if not path.is_file():
            raise ValueError("Native image path is not an existing file")
        with path.open("rb") as handle:
            data = handle.read(MAX_IMAGE_BYTES + 1)
        if len(data) > MAX_IMAGE_BYTES:
            raise ValueError("Image exceeds the bounded file-byte admission")
        digest = hashlib.sha256(data).hexdigest()
        if digest != raw["image_sha256"]:
            raise ValueError("Image bytes differ from the declared content digest")
        trial = dict(native_filename=filename, file_sha256=digest, file_bytes=data)
        mode, bitmap = _decode(data)
        trial |= dict(input_mode=mode, bitmap=bitmap)
        if bitmap.ndim != 2 or not np.isfinite(bitmap).all():
            raise ValueError("Require a finite decoded grayscale matrix")
        image = ImageSource(
            json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False),
            filename,
            str(path.resolve(strict=True)),
            data,
            digest,
            mode,
            arrays.frozen(bitmap),
            metadata.version("pillow"),
            "",
        )
        return replace(image, identity=records._digest(image_record(image)))
    except Exception as error:
        raise ImagePreludeRejected(error, stage="image_capture", trial=trial) from error


def validate_image(image):
    if type(image) is not ImageSource or type(image.file_bytes) is not bytes:
        raise ValueError("Require owned immutable image bytes")
    if len(image.file_bytes) > MAX_IMAGE_BYTES:
        raise ValueError("Owned image bytes exceed the declared bound")
    raw = json.loads(image.definition_json)
    mode, bitmap = _decode(image.file_bytes)
    if (
        hashlib.sha256(image.file_bytes).hexdigest() != image.file_sha256
        or image.file_sha256 != raw["image_sha256"]
        or image.input_mode != mode
        or image.bitmap.flags.writeable
        or records.record(image.bitmap) != records.record(bitmap)
        or records._digest(image_record(image)) != image.identity
    ):
        raise ValueError("Changed owned image source or decoded pixels")
    return image


def _controls(raw):
    keys = {
        "kind",
        "single_cell",
        "svg_override",
        "alpha_shape",
        "use_centroids",
        "refine_mesh",
        "maximum_voronoi_steps",
        "voronoi_convergence",
    }
    if type(raw) is not dict or set(raw) != keys or raw["kind"] != CONTROLS_KIND:
        raise ValueError("Require the normalized make_voronoi branch controls")
    for key in ("single_cell", "svg_override", "use_centroids", "refine_mesh"):
        if type(raw[key]) is not bool:
            raise ValueError("Require an explicit native boolean: " + key)
    if raw["svg_override"]:
        raise ValueError("SVG seed provenance requires a separate implemented stage")
    for key in ("alpha_shape", "voronoi_convergence"):
        value = raw[key]
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Require the finite positive branch scalar: " + key)
    count = raw["maximum_voronoi_steps"]
    if type(count) is not int or not 0 <= count <= 100:
        raise ValueError("Require a bounded nonnegative refinement-step declaration")
    return json.dumps(raw, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _calls(binding, state, controls):
    mesh_type = "tri" if binding.definition["lattice_type"] == "HEX" else "rect"
    kwargs = dict(
        cell_radius=binding.parameters.cell_radius_m,
        seed_points=None if controls["single_cell"] else state.values.all_seed_points_m,
        use_alpha_shape=not controls["single_cell"],
        allow_merging=not controls["single_cell"],
        single_cell_noise=0.1 if controls["single_cell"] else 0.5,
        single_cell_sides=6,
        image_mask=None,
        make_all_operators=False,
        mesh_type=mesh_type,
    )
    if controls["single_cell"]:
        kwargs["center"] = state.values.centre_m
        return MappingProxyType(kwargs), "init_mesh", MappingProxyType({})
    kwargs.update(
        alpha_shape=controls["alpha_shape"],
        use_centroids=controls["use_centroids"],
        merge_thresh=0.1,
        close_thresh=0.1,
    )
    after = dict(
        smoothing=None,
        refinement=controls["refine_mesh"],
        max_steps=controls["maximum_voronoi_steps"],
        convergence=controls["voronoi_convergence"],
        fix_bounds=True,
    )
    return MappingProxyType(kwargs), "clip_and_refine", MappingProxyType(after)


def prelude_record(value):
    return dict(
        law=LAW_ID,
        lattice_binding_identity=value.lattice_binding_identity,
        lattice_state_identity=value.lattice_state_identity,
        image_identity=value.image.identity,
        controls=json.loads(value.controls_json),
        stream=streams.native_stream_manifest(value.stream),
        values=value.values,
        active_file_pixel_ids=value.active_file_pixel_ids,
        constructor_kwargs=value.constructor_kwargs,
        next_method=value.next_method,
        next_kwargs=value.next_kwargs,
    )


def prepare(binding, state, image, controls):
    """Build the image before selecting a mesh branch; never call DECMesh."""
    trial, stage = {}, "input_boundary"
    try:
        lattice.validate_state(binding, state)
        validate_image(image)
        controls_json = _controls(controls)
        bitmap = image.bitmap
        stage = "native_image_mask"
        trial.update(bitmap=bitmap, bounds_m=state.values.axis_bounds_m)
        if bitmap.shape[0] != bitmap.shape[1]:
            raise ValueError("Native image dimensions are non-square")
        m = bitmap.shape[0]
        mask = np.zeros((m, m))
        mask[(bitmap != 255).nonzero()] = 1.0
        mask = np.flipud(mask)
        xmin, xmax, ymin, ymax = state.values.axis_bounds_m
        x, y = np.linspace(xmin, xmax, m), np.linspace(ymin, ymax, m)
        trial.update(clipping_matrix=mask, xpts_m=x, ypts_m=y)
        # Keep the distinct native transpose/degree conventions.
        linear = RectBivariateSpline(x, y, mask.T, kx=1, ky=1)
        stage = "native_fast_spline"
        fast = RectBivariateSpline(x, y, mask)
        stage = "native_active_pixel_hull"
        gx, gy = np.meshgrid(x, y)
        indices = (mask == 1.0).nonzero()
        points = np.column_stack((gx[indices].ravel(), gy[indices].ravel()))
        trial.update(active_points_m=points, active_grid_indices=np.column_stack(indices))
        hull = ConvexHull(points)
        values = MaskValues(
            *(
                arrays.frozen(v)
                for v in (
                    bitmap,
                    mask,
                    x,
                    y,
                    np.column_stack(indices),
                    points,
                    np.asarray(hull.vertices),
                    points[hull.vertices],
                    *linear.get_knots(),
                    linear.get_coeffs(),
                    *fast.get_knots(),
                    fast.get_coeffs(),
                )
            )
        )
        pixel_ids = tuple(f"file-r{m - 1 - i}-c{j}" for i, j in zip(*indices, strict=True))
        kwargs, method, after = _calls(binding, state, controls)
        result = Prelude(
            binding.identity,
            state.identity,
            image,
            controls_json,
            state.stream_after,
            values,
            pixel_ids,
            kwargs,
            method,
            after,
            "",
        )
        return replace(result, identity=records._digest(prelude_record(result)))
    except Exception as error:
        raise ImagePreludeRejected(error, stage=stage, trial=trial) from error


def validate_prelude(binding, state, value):
    if type(value) is not Prelude:
        raise ValueError("Require the complete owned image prelude")
    expected = prepare(binding, state, value.image, json.loads(value.controls_json))
    if (
        records.record(prelude_record(value)) != records.record(prelude_record(expected))
        or value.identity != expected.identity
        or any(v.flags.writeable for v in value.values)
    ):
        raise ValueError("Changed image mask, source bounds, RNG continuation or mesh arguments")
    return value


def _paired_query(binding, state, value, points_x, points_y):
    validate_prelude(binding, state, value)
    x, y = np.asarray(points_x, dtype=np.float64), np.asarray(points_y, dtype=np.float64)
    if (
        x.ndim != 1
        or y.ndim != 1
        or max(x.size, y.size) > MAX_QUERY_POINTS
        or not np.isfinite(x).all()
        or not np.isfinite(y).all()
    ):
        raise ValueError("Require bounded finite one-dimensional point sequences")
    fields = value.values
    function = RectBivariateSpline(
        fields.xpts_m,
        fields.ypts_m,
        fields.clipping_matrix.T,
        kx=1,
        ky=1,
    )
    return function, x, y


def paired_linear_values(binding, state, value, points_x, points_y):
    function, x, y = _paired_query(binding, state, value, points_x, points_y)
    return arrays.frozen(
        np.asarray(
            [function(qx, qy).T.item() for qx, qy in zip(x, y, strict=False)], dtype=np.float64
        )
    )


def clipped_points_index(binding, state, value, points_x, points_y):
    """Preserve native paired zip order and its unequal-length truncation."""
    function, x, y = _paired_query(binding, state, value, points_x, points_y)
    selected = []
    for index, (qx, qy) in enumerate(zip(x, y, strict=False)):
        if function(qx, qy).T != 0.0:
            selected.append(index)
    return arrays.frozen(np.asarray(selected, dtype=int))


def export_prelude(binding, state, value):
    validate_prelude(binding, state, value)
    return dict(
        kind="cells.betse_image_mask_prelude_state@1",
        law_id=LAW_ID,
        identity=value.identity,
        image=arrays.plain(image_record(value.image) | dict(identity=value.image.identity)),
        state=arrays.plain(prelude_record(value)),
        stage="before_DECMesh_constructor",
        next_call_image_mask_argument="owned_image_mask"
        if value.next_method == "clip_and_refine"
        else None,
        downstream_mesh_admitted=False,
        mesh_constructor_executed=False,
        topology_generated=False,
        biological_geometry=False,
    )
