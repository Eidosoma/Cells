"""Native square/HEX lattice seed occurrences before mesh/image preparation.

The native scalar world recipe fixes drawing gap and parameter-store order.
Complete MT state is explicit, including zero-disorder draws and Gaussian cache.
No filtering, merging, triangulation, image clipping or biological model runs.
"""

import json
import math
from dataclasses import dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import digest
from cells.processes import betse_environment_field as arrays
from cells.processes import betse_geometry_initialization as prior_geometry
from cells.processes import betse_normal_current as records
from cells.processes import betse_perturbations as streams

LAW_ID = "betse_lattice_seed_generation_v1_5_0@1"
KIND = "cells.betse_lattice_seed_recipe@1"
STATE_KIND = "cells.betse_lattice_seed_state@1"
DRAWING_GAP_M = 1e-6
MAX_LATTICE_POINTS = 128
MAX_AXIS_COUNT = 128
SIDES = ("BL", "BR", "TR", "TL")


class Parameters(NamedTuple):
    requested_world_len_m: float
    cell_radius_m: float
    diameter_m: float
    drawing_gap_m: float
    nx: int
    ny: int
    expanded_width_m: float
    expanded_height_m: float
    disorder: float
    square_shape: tuple
    blue_shape: tuple
    red_shape: tuple
    lattice_count: int


class Values(NamedTuple):
    base_points_m: object
    blue_points_m: object
    red_points_m: object
    x_uniforms: object
    y_uniforms: object
    x_displacement_m: object
    y_displacement_m: object
    lattice_points_m: object
    bbox_seed_points_m: object
    all_seed_points_m: object
    expanded_bbox_m: object
    centre_m: object
    axis_bounds_m: object


@dataclass(frozen=True, slots=True)
class Binding:
    definition_json: str
    parameters: Parameters
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)


@dataclass(frozen=True, slots=True)
class SeedState:
    binding_identity: str
    stream_before: streams.NativeStream
    stream_after: streams.NativeStream
    values: Values
    occurrence_ids: tuple
    roles: tuple
    draw_order: tuple
    duplicate_groups: tuple
    identity: str


class LatticeSeedRejected(NumericalError):
    def __init__(self, reason, *, stage, source, stream_before=None, trial=None):
        super().__init__("Native lattice seeds refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.stream_before, self.trial = (
            stage,
            source,
            stream_before,
            trial,
        )


def _hex_counts(width, height, diameter):
    r = diameter / 2
    a, b = np.sqrt(3) * r, 3 * r
    blue = (int(((width - a / 2) - a / 2) / a), int(height / b))
    red = (int(width / a), int(((height - b / 2) - b / 2) / b))
    return blue, red


def binding_record(binding):
    return dict(
        law=LAW_ID,
        definition=binding.definition,
        parameters=binding.parameters,
        prior_geometry_adapter=prior_geometry.LAW_ID,
        source_stage="before_make_voronoi",
    )


def bind(raw):
    trial = None
    try:
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "kind",
                "provenance",
                "lattice_type",
                "world_len_m",
                "cell_radius_m",
                "lattice_disorder",
            }
            or raw["kind"] != KIND
        ):
            raise ValueError(
                "Require native scalar world controls without prepared count/gap/size overrides"
            )
        if (
            raw["lattice_type"] not in ("SQUARE", "HEX")
            or type(raw["provenance"]) is not str
            or not raw["provenance"].strip()
        ):
            raise ValueError("Declare square/HEX native lattice branch and provenance")
        length = arrays._scalar(raw["world_len_m"], "world_len_m")
        radius = arrays._scalar(raw["cell_radius_m"], "cell_radius_m")
        disorder = arrays._scalar(raw["lattice_disorder"], "lattice_disorder", positive=False)
        if not 0 <= disorder <= 1:
            raise ValueError("Native disorder is admitted in [0,1] without clipping")
        diameter = radius * 2
        if not math.isfinite(diameter) or diameter <= 0:
            raise ValueError("Unrepresentable source diameter")
        nx = int(length / diameter)
        ny = int(length / diameter)
        expanded_width = length + 5 * disorder * diameter
        expanded_height = length + 5 * disorder * diameter
        trial = dict(
            diameter_m=diameter,
            nx=nx,
            ny=ny,
            expanded_width_m=expanded_width,
            expanded_height_m=expanded_height,
            drawing_gap_m=DRAWING_GAP_M,
        )
        if not math.isfinite(expanded_width) or not math.isfinite(expanded_height):
            raise ValueError("Unrepresentable source expanded world")
        if raw["lattice_type"] == "SQUARE":
            square, blue, red = (ny, nx), (), ()
            count = nx * ny
            axes = square
        else:
            blue, red = _hex_counts(expanded_width, expanded_height, diameter)
            square = ()
            count = math.prod(blue) + math.prod(red)
            axes = blue + red
        trial |= dict(square_shape=square, blue_shape=blue, red_shape=red, lattice_count=count)
        if (
            count < 1
            or count > MAX_LATTICE_POINTS
            or any(v < 0 or v > MAX_AXIS_COUNT for v in axes)
        ):
            raise ValueError("Source lattice is empty or exceeds the bounded point/count admission")
        params = Parameters(
            length,
            radius,
            diameter,
            DRAWING_GAP_M,
            nx,
            ny,
            expanded_width,
            expanded_height,
            disorder,
            square,
            blue,
            red,
            count,
        )
        encoded = json.dumps(
            arrays.plain(raw), sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        binding = Binding(encoded, params, "")
        return replace(binding, identity=records._digest(binding_record(binding)))
    except Exception as error:
        raise LatticeSeedRejected(error, stage="declaration", source=raw, trial=trial) from error


def validate_binding(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the complete native lattice binding")
    expected = bind(binding.definition)
    if expected.identity != binding.identity or records.record(
        binding_record(expected)
    ) != records.record(binding_record(binding)):
        raise ValueError("Changed source parameter store, count or native recipe")
    return binding


def state_record(state):
    return dict(
        law=LAW_ID,
        binding_identity=state.binding_identity,
        values=state.values,
        occurrence_ids=state.occurrence_ids,
        roles=state.roles,
        draw_order=state.draw_order,
        duplicate_groups=state.duplicate_groups,
        stream_before=streams.native_stream_manifest(state.stream_before),
        stream_after=streams.native_stream_manifest(state.stream_after),
    )


def _occurrences(binding):
    p = binding.parameters
    prefix = binding.identity[:16]
    if binding.definition["lattice_type"] == "SQUARE":
        ids = [f"{prefix}-square-r{i}-c{j}" for i in range(p.ny) for j in range(p.nx)]
        roles = ["square_lattice"] * len(ids)
    else:
        ids, roles = [], []
        for color, shape in (("blue", p.blue_shape), ("red", p.red_shape)):
            group = [
                f"{prefix}-{color}-r{i}-c{j}" for i in range(shape[0]) for j in range(shape[1])
            ]
            ids.extend(group)
            roles.extend([color + "_lattice"] * len(group))
    ids.extend(f"{prefix}-bbox-{side}" for side in SIDES)
    roles.extend("bbox_" + side for side in SIDES)
    return tuple(ids), tuple(roles)


@np.errstate(all="ignore")
def generate(binding, stream_before):
    trial = None
    try:
        validate_binding(binding)
        manifest = streams.native_stream_manifest(stream_before)
        rng = np.random.RandomState(0)
        saved = manifest["state"]
        rng.set_state((saved[0], np.asarray(saved[1], np.uint32), saved[2], saved[3], saved[4]))
        p = binding.parameters
        blue = red = None
        if binding.definition["lattice_type"] == "SQUARE":
            xv = np.linspace(0, (p.nx - 1) * (p.diameter_m + p.drawing_gap_m), p.nx)
            yv = np.linspace(0, (p.ny - 1) * (p.diameter_m + p.drawing_gap_m), p.ny)
            x, y = np.meshgrid(xv, yv)
            shape = p.square_shape
        else:
            r = p.diameter_m / 2
            a, b = np.sqrt(3) * r, 3 * r
            xb = np.linspace(0, p.expanded_height_m, p.blue_shape[1])
            yb = np.linspace(a / 2, p.expanded_width_m - a / 2, p.blue_shape[0])
            xr = np.linspace(b / 2, p.expanded_height_m - b / 2, p.red_shape[1])
            yr = np.linspace(0, p.expanded_width_m, p.red_shape[0])
            bx, by = np.meshgrid(xb, yb)
            rx, ry = np.meshgrid(xr, yr)
            blue, red = (
                np.column_stack((bx.ravel(), by.ravel())),
                np.column_stack((rx.ravel(), ry.ravel())),
            )
            x, y = np.hstack((bx.ravel(), rx.ravel())), np.hstack((by.ravel(), ry.ravel()))
            shape = (p.lattice_count,)
        base = np.column_stack((x.ravel(), y.ravel()))
        ux = rng.rand(*shape)
        uy = rng.rand(*shape)
        dx = p.disorder * p.diameter_m * (ux - 0.5)
        dy = p.disorder * p.diameter_m * (uy - 0.5)
        x, y = x + dx, y + dy
        points = np.vstack((x.ravel(), y.ravel())).T
        xmin, xmax, ymin, ymax = (
            np.min(points[:, 0]),
            np.max(points[:, 0]),
            np.min(points[:, 1]),
            np.max(points[:, 1]),
        )
        bbox = np.asarray([[xmin, ymin], [xmax, ymin], [xmax, ymax], [xmin, ymax]])
        centre = points.mean(axis=0)
        all_points = np.vstack((points, bbox))
        expanded_bbox = np.asarray(
            [
                [xmin - p.cell_radius_m, ymin - p.cell_radius_m],
                [xmax + p.cell_radius_m, ymin - p.cell_radius_m],
                [xmax + p.cell_radius_m, ymax + p.cell_radius_m],
                [xmin - p.cell_radius_m, ymax + p.cell_radius_m],
            ]
        )
        bounds = np.asarray(
            [
                xmin - p.cell_radius_m,
                xmax + p.cell_radius_m,
                ymin - p.cell_radius_m,
                ymax + p.cell_radius_m,
            ]
        )
        after = rng.get_state()
        stream_after = streams._native_stream(
            [after[0], after[1].tolist(), int(after[2]), int(after[3]), float(after[4])],
            np.__version__,
        )
        values = Values(
            *(
                None if value is None else arrays.frozen(value)
                for value in (
                    base,
                    blue,
                    red,
                    ux,
                    uy,
                    dx,
                    dy,
                    points,
                    bbox,
                    all_points,
                    expanded_bbox,
                    centre,
                    bounds,
                )
            )
        )
        ids, roles = _occurrences(binding)
        groups = {}
        for occurrence, point in zip(ids, all_points, strict=True):
            groups.setdefault(tuple(point), []).append(occurrence)
        duplicates = tuple(tuple(group) for group in groups.values() if len(group) > 1)
        order = (("x", shape, p.lattice_count), ("y", shape, p.lattice_count))
        trial = SeedState(
            binding.identity, stream_before, stream_after, values, ids, roles, order, duplicates, ""
        )
        trial = replace(trial, identity=records._digest(state_record(trial)))
        if not all(np.isfinite(value).all() for value in values if value is not None):
            raise ValueError("Nonfinite actual source lattice buffers")
        return trial
    except Exception as error:
        raise LatticeSeedRejected(
            error,
            stage="seed_trial" if trial is not None else "source",
            source=binding,
            stream_before=stream_before,
            trial=trial,
        ) from error


def validate_state(binding, value):
    if type(value) is not SeedState or value.binding_identity != binding.identity:
        raise ValueError("Require the original bound lattice seed state")
    expected = generate(binding, value.stream_before)
    if (
        value.identity != expected.identity
        or records.record(state_record(value)) != records.record(state_record(expected))
        or any(a.flags.writeable for a in value.values if a is not None)
    ):
        raise ValueError(
            "Changed seed coordinates, draw ordering, occurrences or complete RNG state"
        )
    return value


def export_seed_stage(binding, value):
    """Portable seed-stage handoff; no conversion into manufactured B09 geometry."""
    validate_state(binding, value)
    return dict(
        kind=STATE_KIND,
        law_id=LAW_ID,
        recipe=binding.definition,
        parameters=arrays.plain(binding.parameters._asdict()),
        binding_identity=binding.identity,
        state=arrays.plain(state_record(value)),
        identity=value.identity,
        classification="native_lattice_seed_occurrences",
        stage="before_make_voronoi_image_prelude",
        downstream_geometry_adapter=prior_geometry.LAW_ID,
        downstream_geometry_admitted=False,
        topology_generated=False,
        biological_geometry=False,
        B09_and_MT_coverage_reused=True,
    )


def restore_seed_stage(binding, record):
    if type(record) is not dict or record.get("kind") != STATE_KIND:
        raise ValueError("Require the complete native lattice seed-stage record")
    before = streams.native_stream_from_manifest(record["state"]["stream_before"])
    value = generate(binding, before)
    if digest(record) != digest(export_seed_stage(binding, value)):
        raise ValueError("Serialized lattice seed-stage record differs from original recipe/draws")
    return value
