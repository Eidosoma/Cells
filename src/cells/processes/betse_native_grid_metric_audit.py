"""Read-only diagnostics for native MAC coordinates and a declared scalar delta.

Inputs are immutable observations, not native owners or executable grids. This
module neither constructs coordinates/operators nor modifies a retained grid.
Its uniform-grid predicate mirrors the inspected Cells gate, without calling
that binder or granting source, physical, phase or checkpoint admission.
"""

import hashlib
import json
import math
import struct
import sys
from dataclasses import dataclass
from fractions import Fraction

LAW_ID = "cells.native_MAC_grid_metric_observation@1"
MAX_OBSERVED_POINTS = 1024  # This new metadata helper's bound; no existing cap changes.
UNIFORM_RTOL = 2e-14
COORDINATE_EPS_MULTIPLIER = 64
TARGET_MAX_GRID_CELLS = 1024
SOURCE_PINS = (
    (
        "betse/science/math/finitediff.py",
        "8186bc5c013db8aec224f6ed9b0892e944b2ddd4247f135ff19caf7419478350",
    ),
    ("betse/science/cells.py", "be38678a4f0bd084044fe7d952d74a4550003ce9701f5d073d1f124ba6daeaf2"),
)
SIDES = ("N", "S", "E", "W")


@dataclass(frozen=True, slots=True)
class GridObservation:
    """Exact decoded binary64 values; tuples prevent accidental input writes.

    Axis vertices are observed slices, not replacements for the original full
    grid or its layout evidence. The caller retains that evidence separately.
    This record attests no live object, source execution or owner provenance.
    """

    shape: tuple  # ny, nx
    bounds_m: tuple  # xmin, xmax, ymin, ymax
    delta_m: float
    coordinates_m: tuple  # actual xy_cents, in retained order
    map_ij2k: tuple  # actual map_ij2k_cents, in retained order
    vertices_x_m: tuple  # actual first row of verts_X
    vertices_y_m: tuple  # actual first column of verts_Y
    source_receipt: str = ""


@dataclass(frozen=True, slots=True)
class MetricAudit:
    observation: GridObservation
    boundaries: tuple
    record_json: str
    identity: str

    @property
    def record(self):
        return json.loads(self.record_json)


class MetricInputRejected(ValueError):
    def __init__(self, message, *, observation=None, audit=None):
        super().__init__(message)
        self.observation, self.audit = observation, audit


class UniformMetricRejected(MetricInputRejected):
    pass


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _digest(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _bits(value):
    return struct.pack(">d", value).hex()


def _number(value):
    if value is None:
        return None
    return dict(binary64_bits=_bits(value), display=repr(value))


def _ratio(value):
    return dict(numerator=str(value.numerator), denominator=str(value.denominator))


def _schema(observation, boundaries):
    def require(condition, message):
        if not condition:
            raise MetricInputRejected(message, observation=observation)

    require(type(observation) is GridObservation, "Exact observation record required")
    require(
        type(observation.shape) is tuple and len(observation.shape) == 2,
        "Declare the retained (ny,nx) shape",
    )
    require(
        all(type(n) is int and n.bit_length() <= 31 for n in observation.shape),
        "Bounded exact integer shape required",
    )
    require(
        type(observation.bounds_m) is tuple and len(observation.bounds_m) == 4,
        "Declare all four original bounds",
    )
    require(type(observation.delta_m) is float, "Decode delta as binary64 without casting")
    require(
        all(type(v) is float for v in observation.bounds_m),
        "Decode bounds as binary64 without casting",
    )
    require(type(observation.source_receipt) is str, "Evidence link must be text")
    for name, width, kind in (("coordinates_m", 2, float), ("map_ij2k", 2, int)):
        values = getattr(observation, name)
        require(
            type(values) is tuple and len(values) <= MAX_OBSERVED_POINTS,
            "Bounded immutable observed rows required: " + name,
        )
        require(
            all(
                type(row) is tuple
                and len(row) == width
                and all(type(v) is kind and (kind is not int or v.bit_length() <= 31) for v in row)
                for row in values
            ),
            "Exact decoded row types required: " + name,
        )
    for name in ("vertices_x_m", "vertices_y_m"):
        values = getattr(observation, name)
        require(
            type(values) is tuple
            and len(values) <= MAX_OBSERVED_POINTS + 1
            and all(type(v) is float for v in values),
            "Bounded immutable binary64 vertex axis required: " + name,
        )
    require(
        type(boundaries) is tuple
        and all(
            type(row) is tuple and len(row) == 2 and all(type(v) is str for v in row)
            for row in boundaries
        ),
        "Declare ordered boundary label pairs without coercion",
    )
    require(len(boundaries) <= 8, "Boundary metadata limit")


def _input_record(observation, boundaries):
    return dict(
        shape=observation.shape,
        bounds_binary64_bits=tuple(_bits(v) for v in observation.bounds_m),
        delta_binary64_bits=_bits(observation.delta_m),
        coordinates_binary64_bits=tuple(
            tuple(_bits(v) for v in row) for row in observation.coordinates_m
        ),
        map_ij2k=observation.map_ij2k,
        vertices_x_binary64_bits=tuple(_bits(v) for v in observation.vertices_x_m),
        vertices_y_binary64_bits=tuple(_bits(v) for v in observation.vertices_y_m),
        boundaries=boundaries,
        source_receipt=observation.source_receipt,
    )


def _close_to_delta(value, delta):
    # Same asymmetric reference and zero absolute tolerance as np.allclose(...,
    # delta, rtol=2e-14, atol=0), for finite scalar observations only.
    return (
        math.isfinite(value)
        and math.isfinite(delta)
        and abs(value - delta) <= UNIFORM_RTOL * abs(delta)
    )


def _axis(low, high, count, vertices, delta):
    finite = all(math.isfinite(v) for v in (low, high, delta, *vertices))
    span = high - low if math.isfinite(low) and math.isfinite(high) else None
    quotient = (
        span / delta
        if span is not None and math.isfinite(span) and math.isfinite(delta) and delta != 0
        else None
    )
    native_count = int(quotient) if quotient is not None and math.isfinite(quotient) else None
    step = span / count if span is not None and math.isfinite(span) and count > 0 else None
    differences = tuple(b - a for a, b in zip(vertices, vertices[1:], strict=False))
    spacing_ratio = (
        step / delta
        if step is not None and math.isfinite(step) and math.isfinite(delta) and delta != 0
        else None
    )
    observed_matches_delta = bool(differences) and all(
        _close_to_delta(v, delta) for v in differences
    )
    endpoints = len(vertices) >= 2 and vertices[0] == low and vertices[-1] == high
    return dict(
        bounds=(_number(low), _number(high)),
        span=_number(span),
        rounded_native_span_over_delta=_number(quotient),
        rounded_native_int_count=native_count,
        native_count_available=native_count is not None,
        observed_count=count,
        source_count_matches=native_count == count,
        count_rule="int of rounded binary64 span/delta; truncation toward zero",
        exact_ratio_of_rounded_span_and_delta=(
            _ratio(Fraction(span) / Fraction(delta))
            if span is not None and math.isfinite(span) and math.isfinite(delta) and delta != 0
            else None
        ),
        effective_span_per_count_m=_number(step),
        effective_spacing_to_delta_ratio=_number(spacing_ratio),
        finite=finite,
        endpoints_match_bounds=endpoints,
        endpoint_bits_match_bounds=(
            len(vertices) >= 2
            and _bits(vertices[0]) == _bits(low)
            and _bits(vertices[-1]) == _bits(high)
        ),
        vertex_count_matches=len(vertices) == count + 1,
        increasing_vertices=bool(differences) and all(v > 0 for v in differences),
        observed_steps_match_span_per_count=(
            step is not None
            and bool(differences)
            and all(_close_to_delta(v, step) for v in differences)
        ),
        observed_steps_match_delta=observed_matches_delta,
        span_per_count_matches_delta=step is not None and _close_to_delta(step, delta),
        observed_steps_binary64_bits=tuple(_bits(v) for v in differences),
    )


def _selected_side(i, j, ny, nx):
    # Exact source branch order, including the deliberately asymmetric corners.
    if i not in (0, ny - 1) and j not in (0, nx - 1):
        return None
    if i == 0 and j not in (0, nx - 1):
        return "S"
    if i == ny - 1 and j not in (0, nx - 1):
        return "N"
    if j == 0 and i not in (0, ny - 1):
        return "W"
    if j == nx - 1 and i not in (0, ny - 1):
        return "E"
    if i == 0 and j == 0:
        return "S"
    if i == ny - 1 and j == 0:
        return "N"
    return "E"


def _boundary_records(observation, labels):
    ny, nx = observation.shape
    if ny < 2 or nx < 2 or len(observation.coordinates_m) != ny * nx:
        return ()
    xmin, xmax, ymin, ymax = observation.bounds_m
    records = []
    for k, (i, j) in enumerate(observation.map_ij2k):
        if k >= len(observation.coordinates_m) or not (0 <= i < ny and 0 <= j < nx):
            continue
        side = _selected_side(i, j, ny, nx)
        if side is None:
            continue
        x, y = observation.coordinates_m[k]
        distances = dict(S=y - ymin, N=ymax - y, W=x - xmin, E=xmax - x)
        geometric_sides = tuple(
            s
            for s, reached in (("S", i == 0), ("N", i == ny - 1), ("W", j == 0), ("E", j == nx - 1))
            if reached
        )
        records.append(
            dict(
                k=k,
                ij=(i, j),
                geometric_sides=geometric_sides,
                source_selected_side=side,
                declared_label=labels.get(side),
                other_corner_labels={s: labels.get(s) for s in geometric_sides if s != side},
                native_label_branch=(
                    "missing selected key"
                    if side not in labels
                    else "flux"
                    if labels[side] == "flux"
                    else "value identity"
                    if labels[side] == "value" or len(geometric_sides) == 2
                    else "neither branch matched; source row remains zero"
                ),
                distance_to_geometric_bounds_m={s: _number(distances[s]) for s in geometric_sides},
                value_label_semantics=(
                    "identity divided by scalar delta**2; not boundary potential data"
                ),
                flux_label_semantics="retained-neighbour row divided by scalar delta**2",
            )
        )
    return tuple(records)


def audit(observation, *, boundaries):
    """Return diagnostics, including failure flags; never mutate or bind a grid."""
    _schema(observation, boundaries)
    ny, nx = observation.shape
    xmin, xmax, ymin, ymax = observation.bounds_m
    delta = observation.delta_m
    axes = dict(
        x=_axis(xmin, xmax, nx, observation.vertices_x_m, delta),
        y=_axis(ymin, ymax, ny, observation.vertices_y_m, delta),
    )
    bounded_shape = ny > 0 and nx > 0 and ny * nx <= MAX_OBSERVED_POINTS
    count = ny * nx
    finite = all(
        math.isfinite(v)
        for v in (
            *observation.bounds_m,
            delta,
            *observation.vertices_x_m,
            *observation.vertices_y_m,
        )
    ) and all(math.isfinite(v) for row in observation.coordinates_m for v in row)
    coordinate_shape = bounded_shape and len(observation.coordinates_m) == count
    map_order = (
        bounded_shape
        and len(observation.map_ij2k) == count
        and all(ij == divmod(k, nx) for k, ij in enumerate(observation.map_ij2k))
    )
    tolerance = (
        COORDINATE_EPS_MULTIPLIER
        * sys.float_info.epsilon
        * max(*(abs(v) for v in observation.bounds_m), delta)
        if finite and delta > 0
        else None
    )
    coordinate_errors, failures = [], []
    midpoints = (
        coordinate_shape
        and finite
        and len(observation.vertices_x_m) == nx + 1
        and len(observation.vertices_y_m) == ny + 1
    )
    midpoint_matches = False
    if coordinate_shape and finite and tolerance is not None:
        midpoint_matches = midpoints
        for k, (x, y) in enumerate(observation.coordinates_m):
            i, j = divmod(k, nx)
            expected = (xmin + (j + 0.5) * delta, ymin + (i + 0.5) * delta)
            errors = (abs(x - expected[0]), abs(y - expected[1]))
            coordinate_errors.extend(errors)
            if not all(math.isfinite(v) and v <= tolerance for v in errors):
                if len(failures) < 32:
                    failures.append(
                        dict(k=k, ij=(i, j), errors_m=tuple(_number(v) for v in errors))
                    )
            if midpoints:
                mx = (observation.vertices_x_m[j] + observation.vertices_x_m[j + 1]) / 2
                my = (observation.vertices_y_m[i] + observation.vertices_y_m[i + 1]) / 2
                midpoint_matches = midpoint_matches and (_bits(x), _bits(y)) == (
                    _bits(mx),
                    _bits(my),
                )
    coordinate_passed = (
        coordinate_shape
        and finite
        and tolerance is not None
        and bool(coordinate_errors)
        and all(math.isfinite(v) and v <= tolerance for v in coordinate_errors)
    )
    labels = dict(boundaries)
    boundary_passed = (
        len(boundaries) == 4
        and len(labels) == 4
        and set(labels) == set(SIDES)
        and all(v in ("flux", "value") for v in labels.values())
    )
    checks = dict(
        finite=finite,
        strictly_positive_delta=math.isfinite(delta) and delta > 0,
        increasing_bounds=all(math.isfinite(v) for v in observation.bounds_m)
        and xmin < xmax
        and ymin < ymax,
        shape_at_least_two=bounded_shape and ny >= 2 and nx >= 2,
        existing_target_point_limit=bounded_shape and count <= TARGET_MAX_GRID_CELLS,
        coordinate_count=coordinate_shape,
        native_C_order_map=map_order,
        native_truncated_counts=all(a["source_count_matches"] for a in axes.values()),
        observed_axis_lengths=all(a["vertex_count_matches"] for a in axes.values()),
        observed_axis_endpoints=all(a["endpoints_match_bounds"] for a in axes.values()),
        increasing_observed_vertices=all(a["increasing_vertices"] for a in axes.values()),
        observed_axis_steps_match_spans=all(
            a["observed_steps_match_span_per_count"] for a in axes.values()
        ),
        observed_axis_steps_match_scalar_delta=all(
            a["observed_steps_match_delta"] for a in axes.values()
        ),
        spans_per_count_match_scalar_delta=all(
            a["span_per_count_matches_delta"] for a in axes.values()
        ),
        centres_match_retained_vertex_midpoints=bool(midpoint_matches),
        existing_uniform_coordinate_gate=coordinate_passed,
        four_declared_boundary_labels=boundary_passed,
    )
    target_checks = (
        "finite",
        "strictly_positive_delta",
        "increasing_bounds",
        "shape_at_least_two",
        "existing_target_point_limit",
        "coordinate_count",
        "spans_per_count_match_scalar_delta",
        "existing_uniform_coordinate_gate",
        "four_declared_boundary_labels",
    )
    source_checks = (
        "native_C_order_map",
        "native_truncated_counts",
        "observed_axis_lengths",
        "observed_axis_endpoints",
        "increasing_observed_vertices",
        "observed_axis_steps_match_spans",
        "centres_match_retained_vertex_midpoints",
    )
    record = dict(
        kind=LAW_ID,
        input=_input_record(observation, boundaries),
        axes=axes,
        checks=checks,
        uniform_metric_passed=all(checks[name] for name in target_checks),
        selected_native_observation_checks_passed=all(checks[name] for name in source_checks),
        all_observation_checks_passed=all(checks.values()),
        refusal_reasons=tuple(name for name, passed in checks.items() if not passed),
        coordinate_gate=dict(
            relative_tolerance=0,
            absolute_tolerance_m=_number(tolerance),
            maximum_error_m=_number(max(coordinate_errors)) if coordinate_errors else None,
            first_failures=failures,
            failure_examples_limit=32,
        ),
        source_semantics=dict(
            pins=SOURCE_PINS,
            cell_grid_lines=(158, 250),
            makeLaplacian_lines=(252, 431),
            coordinates=(
                "endpoint-inclusive vertices; adjacent-vertex midpoints; row-major xy_cents"
            ),
            scalar_spacing="original grid_delta retained; counts use int(span/grid_delta)",
            staggered_shapes=dict(
                centres=(ny, nx), vertices=(ny + 1, nx + 1), u=(ny, nx + 1), v=(ny + 1, nx)
            ),
            staggered_shapes_are_source_description_not_observed_array_certification=True,
            operator_metric="all source stencil entries use scalar delta**2, not measured dx/dy",
            corners=dict(SW="S", NW="N", SE="E", NE="E"),
            boundary_rows="centres, not physical rectangle vertices",
            selected_observation_checks_are_necessary_diagnostics_not_source_authentication=True,
        ),
        boundary_sites=_boundary_records(observation, labels),
        uniform_policy=dict(
            rtol=UNIFORM_RTOL,
            atol=0,
            coordinate_epsilon_multiplier=COORDINATE_EPS_MULTIPLIER,
            target_max_grid_cells=TARGET_MAX_GRID_CELLS,
        ),
        source_correspondence_verified=False,
        native_or_operator_execution=False,
        grid_binding_constructed=False,
        metric_repair_supplied=False,
        operator_rank_conditioning_volumes_and_materials_assessed=False,
        physical_phase_checkpoint_admitted=False,
        all11_owners_invalid=True,
        all12_postcut_scientific_cases_held=True,
    )
    text = _json(record)
    return MetricAudit(observation, boundaries, text, _digest(text))


def validate(report):
    if type(report) is not MetricAudit:
        raise MetricInputRejected("Exact metric audit required", audit=report)
    expected = audit(report.observation, boundaries=report.boundaries)
    if expected.record_json != report.record_json or expected.identity != report.identity:
        raise MetricInputRejected("Changed metric report or original observations", audit=report)
    return report


def require_uniform_metric(report):
    """Refuse incompatibility; a pass returns diagnostic data, never authority."""
    validate(report)
    if not report.record["all_observation_checks_passed"]:
        raise UniformMetricRejected(
            "Retained native grid does not satisfy the declared uniform metric; no repair supplied",
            observation=report.observation,
            audit=report,
        )
    return report
