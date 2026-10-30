"""Pinned BETSE x/y/r gradients with explicit geometry and source-axis binding.

Pure float64 kernels preserve source arithmetic, including nonfinite failures.
Factors are not clipped or interpreted as permeability, pressure or physical work.
The immutable host program records the full owner geometry and native selection.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, replace
from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_spatial_modulation_source_v1_5_0@1"


class Values(NamedTuple):
    factor: object
    normalization_m: object
    finite: object


@dataclass(frozen=True, slots=True)
class Program:
    kind: str
    target_domain: str
    target_ids: tuple
    cell_ids: tuple
    membrane_ids: tuple
    cell_centres_m: tuple
    membrane_midpoints_m: tuple
    centre_m: tuple
    x_offset: float
    exponent: float | None
    slope: float
    z_offset: float
    provenance: str
    identity: str


def _real(value):
    if (
        not isinstance(value, Real)
        or isinstance(value, (bool, np.bool_))
        or not math.isfinite(value)
    ):
        raise ValueError("Require explicit finite real geometry and coefficients")
    return float(value)


def _ids(values, *, unique):
    if not isinstance(values, (tuple, list)) or any(
        type(v) is not str or not v.strip() for v in values
    ):
        raise ValueError("Require ordered nonempty owner names")
    result = tuple(values)
    if unique and (not result or len(set(result)) != len(result)):
        raise ValueError("Require distinct complete geometry owners")
    return result


def _points(values, count):
    try:
        result = tuple(tuple(_real(x) for x in row) for row in values)
    except TypeError as error:
        raise ValueError("Require complete two-dimensional coordinates in metres") from error
    if len(result) != count or any(len(row) != 2 for row in result):
        raise ValueError("Coordinates must match every declared owner")
    return result


def record(program):
    if type(program) is not Program:
        raise ValueError("Require a typed spatial modulation program")
    payload = asdict(program)
    payload.pop("identity")
    payload = json.loads(json.dumps(dict(law=LAW_ID, **payload), allow_nan=False))
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()
    return payload | dict(identity=digest)


def bind(
    *,
    kind,
    target_domain,
    target_ids,
    cell_ids,
    membrane_ids,
    cell_centres_m,
    membrane_midpoints_m,
    centre_m,
    x_offset,
    slope,
    z_offset,
    exponent=None,
    provenance,
):
    """Bind literal source selection; x/y use target count, r uses membrane indices.

    For x/y, membrane count wins a count tie in BETSE. Refuse a declared cell
    selection that would silently choose membranes, and refuse unbound lengths.
    x_offset is dimensionless for x/y and metres for r, where it shifts both axes.
    """
    if kind not in ("gradient_x", "gradient_y", "gradient_r"):
        raise ValueError("Unknown spatial modulation law")
    if type(provenance) is not str or not provenance.strip():
        raise ValueError("Declare the source of geometry and modulation coefficients")
    cells, membranes = _ids(cell_ids, unique=True), _ids(membrane_ids, unique=True)
    targets = _ids(target_ids, unique=False)
    if target_domain not in ("cells", "membranes"):
        raise ValueError("Declare the target domain explicitly")
    owners = cells if target_domain == "cells" else membranes
    if any(name not in owners for name in targets):
        raise ValueError("Target is absent from its declared geometry")
    if kind == "gradient_r":
        if target_domain != "membranes" or exponent is not None:
            raise ValueError("Native radial modulation uses membranes and no exponent")
    else:
        selected = (
            "membranes"
            if len(targets) == len(membranes)
            else "cells"
            if len(targets) == len(cells)
            else None
        )
        if selected != target_domain:
            raise ValueError("Native target-count branch does not select the declared domain")
        exponent = _real(exponent)
    centre = _points((centre_m,), 1)[0]
    program = Program(
        kind,
        target_domain,
        targets,
        cells,
        membranes,
        _points(cell_centres_m, len(cells)),
        _points(membrane_midpoints_m, len(membranes)),
        centre,
        _real(x_offset),
        exponent,
        _real(slope),
        _real(z_offset),
        provenance,
        "",
    )
    return replace(program, identity=record(program)["identity"])


def validate(program):
    if type(program) is not Program:
        raise ValueError("Require a typed spatial modulation program")
    payload = asdict(program)
    payload.pop("identity")
    expected = bind(**payload)
    if program != expected:
        raise ValueError("Spatial program differs from its full geometry and coefficients")
    return program


def restore(saved, *, expected_identity):
    if type(saved) is not dict or saved.get("law") != LAW_ID:
        raise ValueError("Require the complete saved spatial law")
    try:
        program = bind(**{k: v for k, v in saved.items() if k not in ("law", "identity")})
    except TypeError as error:
        raise ValueError("Incomplete or extended spatial program") from error
    if program.identity != expected_identity or record(program) != saved:
        raise ValueError("Saved spatial program differs from its original identity")
    return program


def _array(value, xp):
    array = xp.asarray(value)
    if array.dtype != xp.float64:
        raise ValueError("Spatial arrays require explicit float64 values")
    return array


def axis(coordinates_m, x_offset, exponent, slope, z_offset, *, xp=jnp):
    """Source x/y arithmetic on the final owner axis; leading axes are worlds."""
    coordinates = _array(coordinates_m, xp)
    if coordinates.ndim == 0 or coordinates.shape[-1] == 0:
        raise ValueError("Require a nonempty final coordinate axis")
    world, offset, power, scale, shift = xp.broadcast_arrays(
        coordinates[..., 0], *(_array(v, xp) for v in (x_offset, exponent, slope, z_offset))
    )
    coordinates = xp.broadcast_to(coordinates, world.shape + (coordinates.shape[-1],))
    displaced = coordinates - xp.min(coordinates, axis=-1, keepdims=True)
    span = xp.max(displaced, axis=-1)
    normalized = displaced / span[..., None]
    middle = 0.5 + offset
    base = normalized / middle[..., None]
    loading = base ** power[..., None]
    fraction = loading / (1 + loading)
    factor = fraction * scale[..., None] + shift[..., None]
    inputs_finite = (
        xp.all(xp.isfinite(coordinates), axis=-1)
        & xp.isfinite(offset)
        & xp.isfinite(power)
        & xp.isfinite(scale)
        & xp.isfinite(shift)
        & xp.isfinite(middle)
        & xp.isfinite(span)
    )
    finite = inputs_finite[..., None]
    for value in (displaced, normalized, base, loading, fraction, factor):
        finite = finite & xp.isfinite(value)
    return Values(factor, span, finite)


def radial(coordinates_m, selected, centre_m, x_offset, slope, z_offset, *, xp=jnp):
    """Source radial arithmetic, full membrane output, offset on both axes.

    Unselected membranes have zero radius before normalization and therefore the
    declared z_offset afterwards. Do not substitute hypot or omit these entries.
    """
    coordinates, centre = _array(coordinates_m, xp), _array(centre_m, xp)
    mask = xp.asarray(selected)
    if (
        coordinates.ndim < 2
        or coordinates.shape[-1] != 2
        or coordinates.shape[-2] == 0
        or centre.ndim < 1
        or centre.shape[-1] != 2
        or mask.dtype != xp.bool_
        or mask.ndim < 1
        or mask.shape[-1] != coordinates.shape[-2]
    ):
        raise ValueError("Require complete 2D membrane geometry, centre and boolean owner mask")
    world, _, _, offset, scale, shift = xp.broadcast_arrays(
        coordinates[..., 0, 0],
        centre[..., 0],
        mask[..., 0],
        *(_array(v, xp) for v in (x_offset, slope, z_offset)),
    )
    n = coordinates.shape[-2]
    coordinates = xp.broadcast_to(coordinates, world.shape + (n, 2))
    centre = xp.broadcast_to(centre, world.shape + (2,))
    mask = xp.broadcast_to(mask, world.shape + (n,))
    dx = xp.where(mask, coordinates[..., 0] - centre[..., 0, None] - offset[..., None], 0.0)
    dy = xp.where(mask, coordinates[..., 1] - centre[..., 1, None] - offset[..., None], 0.0)
    squared = dx**2 + dy**2
    radius = xp.sqrt(squared)
    span = xp.max(radius, axis=-1)
    normalized = radius / span[..., None]
    factor = normalized * scale[..., None] + shift[..., None]
    inputs_finite = (
        xp.all(xp.isfinite(coordinates), axis=(-2, -1))
        & xp.all(xp.isfinite(centre), axis=-1)
        & xp.isfinite(offset)
        & xp.isfinite(scale)
        & xp.isfinite(shift)
        & xp.isfinite(span)
    )
    finite = inputs_finite[..., None]
    for value in (dx, dy, squared, radius, normalized, factor):
        finite = finite & xp.isfinite(value)
    return Values(factor, span, finite)


def evaluate(program, *, xp=jnp):
    """Host-prepared, geometry-bound factor; consumers must check finite/domain."""
    validate(program)
    if program.kind == "gradient_r":
        selected = xp.asarray([name in program.target_ids for name in program.membrane_ids])
        return radial(
            xp.asarray(program.membrane_midpoints_m, dtype=xp.float64),
            selected,
            xp.asarray(program.centre_m, dtype=xp.float64),
            program.x_offset,
            program.slope,
            program.z_offset,
            xp=xp,
        )
    coordinates = (
        program.membrane_midpoints_m
        if program.target_domain == "membranes"
        else program.cell_centres_m
    )
    axis_index = 0 if program.kind == "gradient_x" else 1
    return axis(
        xp.asarray(coordinates, dtype=xp.float64)[..., axis_index],
        program.x_offset,
        program.exponent,
        program.slope,
        program.z_offset,
        xp=xp,
    )
