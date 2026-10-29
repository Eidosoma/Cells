"""Literal native extracellular paths and a distinct conservative face law.

Source collocated derivative/boundary/smoothing defects are preserved. The
Bernoulli-fitted face operator has explicit owners, bath ledgers and a monotone
Euler domain; it is not called native discretization or whole-tissue parity.
"""

import hashlib
import json
from dataclasses import dataclass
from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import bernoulli

SOURCE_LAW_ID = "betse_environment_transport_source_v1_5_0@1"
FACE_LAW_ID = "bernoulli_fitted_environment_faces@1"
MAX_SITES = 1024
MAX_SPECIES = 32
SIDES = ("N", "S", "E", "W")
SIDE_NORMALS = {"N": (0.0, 1.0), "S": (0.0, -1.0), "E": (1.0, 0.0), "W": (-1.0, 0.0)}


def _freeze(value, dtype=None):
    result = np.array(value, dtype=dtype, copy=True)
    result.setflags(write=False)
    return result


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _number(value):
    return (
        isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)
    )


def _ids(values, limit):
    if (
        not isinstance(values, (tuple, list))
        or not 0 < len(values) <= limit
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require bounded unique nonempty stable owner IDs")
    return tuple(values)


def _field(value, tail, *, xp):
    array = xp.asarray(value)
    if array.ndim < len(tail) or array.shape[-len(tail) :] != tail or array.dtype.kind not in "fiu":
        raise ValueError("Field requires explicit species/vector/site owner axes")
    return array


def _scalar(value, *, xp):
    array = xp.asarray(value)
    if array.dtype.kind not in "fiu":
        raise ValueError("Require a numeric world-scalar control")
    return array


@dataclass(frozen=True)
class GridSpec:
    site_ids: tuple
    species_ids: tuple
    valence: object
    shape: tuple
    coordinates_m: object
    delta_m: float
    height_m: float
    internal_face_ids: tuple
    internal_face_sites: tuple
    boundary_face_ids: tuple
    boundary_face_sites: tuple
    boundary_face_sides: tuple
    provenance: dict


class GridKernel(NamedTuple):
    valence: object
    volume_m3: object
    perimeter: object
    senders: object
    receivers: object
    internal_normal: object
    internal_area_m2: object
    internal_distance_m: object
    boundary_owner: object
    boundary_normal: object
    boundary_area_m2: object
    boundary_distance_m: object


@dataclass(frozen=True)
class GridBinding:
    site_ids: tuple
    species_ids: tuple
    shape: tuple
    coordinates_m: object
    delta_m: float
    height_m: float
    internal_face_ids: tuple
    boundary_face_ids: tuple
    boundary_face_sides: tuple
    kernel: GridKernel
    provenance_json: str
    identity: str


def bind_grid(spec):
    sites, species = _ids(spec.site_ids, MAX_SITES), _ids(spec.species_ids, MAX_SPECIES)
    shape = tuple(spec.shape)
    if (
        len(shape) != 2
        or any(type(v) is not int or v < 2 for v in shape)
        or np.prod(shape) != len(sites)
    ):
        raise ValueError("Explicit ny,nx>=2 and C-order site axis are required")
    if (
        not _number(spec.delta_m)
        or not _number(spec.height_m)
        or min(spec.delta_m, spec.height_m) <= 0
    ):
        raise ValueError("Require positive spacing/height in metres")
    ny, nx = shape
    h = float(spec.delta_m)
    coords = _field(spec.coordinates_m, (len(sites), 2), xp=np)
    if not np.isfinite(coords).all():
        raise ValueError("Finite explicit site coordinates required")
    expected = np.array([coords[0] + (j * h, i * h) for i in range(ny) for j in range(nx)])
    tolerance = 64 * np.finfo(float).eps * max(float(np.max(np.abs(coords))), h)
    if not np.allclose(coords, expected, rtol=0, atol=tolerance):
        raise ValueError("Coordinates must match declared uniform C-order grid")
    z = _field(spec.valence, (len(species),), xp=np)
    if not np.isfinite(z).all():
        raise ValueError("Finite explicit dimensionless valences required")
    face_ids = _ids(spec.internal_face_ids, 2 * MAX_SITES)
    pairs = tuple(tuple(v) for v in spec.internal_face_sites)
    if len(pairs) != len(face_ids) or any(
        len(v) != 2 or v[0] == v[1] or any(at not in sites for at in v) for v in pairs
    ):
        raise ValueError("Every internal face needs two explicit distinct site owners")
    edges = np.asarray([[sites.index(a), sites.index(b)] for a, b in pairs], int)
    undirected = {tuple(sorted(v)) for v in edges}
    expected_pairs = set()
    for i in range(ny):
        for j in range(nx):
            at = i * nx + j
            if j + 1 < nx:
                expected_pairs.add((at, at + 1))
            if i + 1 < ny:
                expected_pairs.add((at, at + nx))
    if len(undirected) != len(edges) or undirected != expected_pairs:
        raise ValueError("Internal faces must declare every nearest grid contact exactly once")
    vector = coords[edges[:, 1]] - coords[edges[:, 0]]
    length = np.linalg.norm(vector, axis=-1)
    normal = vector / length[:, None]
    b_ids = _ids(spec.boundary_face_ids, 4 * MAX_SITES)
    b_sites, b_sides = tuple(spec.boundary_face_sites), tuple(spec.boundary_face_sides)
    if (
        len(b_sites) != len(b_ids)
        or len(b_sides) != len(b_ids)
        or any(v not in sites for v in b_sites)
        or any(v not in SIDES for v in b_sides)
    ):
        raise ValueError("Explicit boundary face IDs, site owners and N/S/E/W sides required")
    b_index = np.asarray([sites.index(v) for v in b_sites], int)
    expected_boundary = set()
    for i in range(ny):
        for j in range(nx):
            at = i * nx + j
            if i == 0:
                expected_boundary.add((at, "S"))
            if i == ny - 1:
                expected_boundary.add((at, "N"))
            if j == 0:
                expected_boundary.add((at, "W"))
            if j == nx - 1:
                expected_boundary.add((at, "E"))
    supplied = list(zip(b_index, b_sides, strict=True))
    if len(set(supplied)) != len(supplied) or set(supplied) != expected_boundary:
        raise ValueError("Declare each physical perimeter face once; corners have two faces")
    perimeter = np.zeros(len(sites), bool)
    perimeter[b_index] = True
    kernel = GridKernel(
        *(
            _freeze(v)
            for v in (
                z,
                np.full(len(sites), h * h * spec.height_m),
                perimeter,
                edges[:, 0],
                edges[:, 1],
                normal,
                np.full(len(edges), h * spec.height_m),
                length,
                b_index,
                [SIDE_NORMALS[v] for v in b_sides],
                np.full(len(b_ids), h * spec.height_m),
                np.full(len(b_ids), h / 2),
            )
        )
    )
    if not isinstance(spec.provenance, dict) or not spec.provenance:
        raise ValueError("Geometry/source provenance is required")
    provenance = json.dumps(spec.provenance, sort_keys=True, separators=(",", ":"), allow_nan=False)
    payload = dict(
        site_ids=sites,
        species_ids=species,
        shape=shape,
        coordinates_m=coords.tolist(),
        delta_m=h,
        height_m=spec.height_m,
        internal_face_ids=face_ids,
        boundary_face_ids=b_ids,
        boundary_sides=b_sides,
        kernel={k: v.tolist() for k, v in kernel._asdict().items()},
        provenance=json.loads(provenance),
    )
    return GridBinding(
        sites,
        species,
        shape,
        _freeze(coords),
        h,
        float(spec.height_m),
        face_ids,
        b_ids,
        b_sides,
        kernel,
        provenance,
        _hash(payload),
    )


def owner_to_grid(values, grid, *, xp=jnp):
    value = _field(values, (len(grid.species_ids), len(grid.site_ids)), xp=xp)
    return value.reshape(value.shape[:-1] + grid.shape)


def grid_to_owner(values, grid, *, xp=jnp):
    value = _field(values, (len(grid.species_ids), *grid.shape), xp=xp)
    return value.reshape(value.shape[:-2] + (len(grid.site_ids),))


@dataclass(frozen=True)
class Regions:
    cluster_sites: tuple
    boundary_membrane_sites: tuple
    neighbor_membrane_sites: tuple
    boundary_cell_sites: tuple


@dataclass(frozen=True)
class Barriers:
    grid_identity: str
    diffusion_m2_s: object
    sodium_weight: object
    initial_TJ_modulator: object
    target_site_ids: tuple
    target_indices: object
    free_diffusion_m2_s: object
    relative_TJ: object
    identity: str


def _region_indices(values, grid):
    if not isinstance(values, (tuple, list)) or any(v not in grid.site_ids for v in values):
        raise ValueError("Region occurrences must name explicit grid owners")
    return np.asarray([grid.site_ids.index(v) for v in values], int)


def init_barriers(grid, regions, free_diffusion_m2_s, relative_TJ, adherens_factor, tight_factor):
    s, e = len(grid.species_ids), len(grid.site_ids)
    free = _field(free_diffusion_m2_s, (s,), xp=np)
    relative = _field(relative_TJ, (s,), xp=np)
    if (
        free.ndim != 1
        or relative.ndim != 1
        or any(not np.isfinite(v).all() or np.any(v < 0) for v in (free, relative))
        or not all(_number(v) and v >= 0 for v in (adherens_factor, tight_factor))
    ):
        raise ValueError("Require finite nonnegative species diffusion and barrier factors")
    if "Na" not in grid.species_ids:
        raise ValueError("Native normalized barrier map requires sodium")
    names = tuple(
        v
        for field in ("boundary_membrane_sites", "neighbor_membrane_sites", "boundary_cell_sites")
        for v in getattr(regions, field)
    )
    cluster = _region_indices(regions.cluster_sites, grid)
    targets = _region_indices(names, grid)
    diffusion = np.broadcast_to(free[:, None], (s, e)).copy()
    diffusion[:, cluster] = free[:, None] * adherens_factor
    diffusion[:, targets] = (free * tight_factor * relative)[:, None]
    row = diffusion[grid.species_ids.index("Na")]
    maximum = np.max(row)
    if not maximum > 0:
        raise ValueError(
            "Zero sodium normalization is a retained native failure, not a weight floor"
        )
    weight = row / maximum
    payload = dict(
        grid_identity=grid.identity,
        regions={k: list(v) for k, v in vars(regions).items()},
        free=free.tolist(),
        relative=relative.tolist(),
        adherens=adherens_factor,
        tight=tight_factor,
    )
    return Barriers(
        grid.identity,
        _freeze(diffusion),
        _freeze(weight),
        _freeze(np.ones_like(diffusion)),
        names,
        _freeze(targets),
        _freeze(free),
        _freeze(relative),
        _hash(payload),
    )


def reflect_gaussian(values, grid, *, sigma, xp=jnp):
    if sigma not in (1.0, 2.0):
        raise ValueError("Pinned Gaussian support is sigma 1 or 2, truncate 4, reflect")
    value = _field(values, (len(grid.site_ids),), xp=xp)
    image = value.reshape(value.shape[:-1] + grid.shape)
    radius = int(4 * sigma + 0.5)
    weights = np.exp(-(np.arange(-radius, radius + 1, dtype=float) ** 2) / (2 * sigma * sigma))
    weights /= weights.sum()
    result = image
    for axis, size in ((-2, grid.shape[0]), (-1, grid.shape[1])):
        part = xp.zeros_like(result)
        for offset, weight in zip(range(-radius, radius + 1), weights, strict=True):
            index = (np.arange(size) + offset) % (2 * size)
            index = np.where(index < size, index, 2 * size - index - 1)
            part = part + weight * xp.take(result, xp.asarray(index), axis=axis)
        result = part
    return result.reshape(result.shape[:-2] + (len(grid.site_ids),))


def legacy_non_ecm_weight(grid, regions, tight_factor, *, xp=jnp):
    if not _number(tight_factor) or tight_factor < 0:
        raise ValueError("Require nonnegative source tight factor")
    targets = _region_indices(
        tuple(
            v
            for field in (
                "boundary_membrane_sites",
                "neighbor_membrane_sites",
                "boundary_cell_sites",
            )
            for v in getattr(regions, field)
        ),
        grid,
    )
    mask = np.zeros(len(grid.site_ids), bool)
    mask[targets] = True
    return reflect_gaussian(xp.where(xp.asarray(mask), tight_factor, 1.0), grid, sigma=1.0, xp=xp)


def wound_barriers(barriers, grid, target_site_ids, factor, *, xp=jnp):
    if barriers.grid_identity != grid.identity or not _number(factor) or factor < 0:
        raise ValueError("Explicit matching barrier grid and nonnegative wound factor required")
    targets = _region_indices(target_site_ids, grid)
    mask = np.zeros(len(grid.site_ids), bool)
    mask[targets] = True
    values = xp.asarray(barriers.free_diffusion_m2_s * barriers.relative_TJ * factor)[:, None]
    return (
        xp.where(xp.asarray(mask), values, xp.asarray(barriers.diffusion_m2_s)),
        xp.where(xp.asarray(mask), factor, xp.asarray(barriers.sodium_weight)),
    )


def molecule_diffusivity(
    grid, weight, target_site_ids, diffusion_m2_s, relative_TJ, *, ignore_TJ, xp=jnp
):
    if type(ignore_TJ) is not bool:
        raise ValueError("Explicit boolean TJ bypass required")
    w = _field(weight, (len(grid.site_ids),), xp=xp)
    if ignore_TJ:
        return xp.ones_like(w) * _scalar(diffusion_m2_s, xp=xp)[..., None]
    targets = _region_indices(target_site_ids, grid)
    mask = np.zeros(len(grid.site_ids), bool)
    mask[targets] = True
    # Native fancy assignment multiplies duplicated targets once, not repeatedly.
    factor = xp.where(xp.asarray(mask), _scalar(relative_TJ, xp=xp)[..., None], 1.0)
    return w * factor * _scalar(diffusion_m2_s, xp=xp)[..., None]


class Thermal(NamedTuple):
    temperature_K: object
    elementary_charge_C: object
    boltzmann_J_K: object
    faraday_C_mol: object


class Fields(NamedTuple):
    electric_V_m: object  # [...,2,site].
    velocity_m_s: object


def _fields(fields, grid, *, xp):
    return Fields(*(_field(v, (2, len(grid.site_ids)), xp=xp) for v in fields))


def _thermal(thermal, *, xp):
    return Thermal(*(_scalar(v, xp=xp) for v in thermal))


def source_gradient(values, h, *, negative_boundary=False, xp=jnp):
    value = xp.asarray(values)
    if value.ndim < 2 or min(value.shape[-2:]) < 2 or value.dtype.kind not in "fiu":
        raise ValueError("Native derivatives require two explicit spatial axes of length >=2")
    sign = -1.0 if negative_boundary else 1.0
    gx = xp.concatenate(
        (
            sign * (value[..., :, 1:2] - value[..., :, 0:1]) / h,
            (value[..., :, 2:] - value[..., :, :-2]) / (2 * h),
            sign * (value[..., :, -1:] - value[..., :, -2:-1]) / h,
        ),
        axis=-1,
    )
    gy = xp.concatenate(
        (
            sign * (value[..., 1:2, :] - value[..., 0:1, :]) / h,
            (value[..., 2:, :] - value[..., :-2, :]) / (2 * h),
            sign * (value[..., -1:, :] - value[..., -2:-1, :]) / h,
        ),
        axis=-2,
    )
    return gx, gy


def source_integrator(values, sharpness, *, xp=jnp):
    image = xp.asarray(values)
    sides = (1 - sharpness) / 4
    if image.ndim < 2 or min(image.shape[-2:]) < 2:
        raise ValueError("Explicit spatial grid axes required")
    interior = sharpness * image[..., 1:-1, 1:-1] + sides * (
        image[..., :-2, 1:-1] + image[..., 2:, 1:-1] + image[..., 1:-1, :-2] + image[..., 1:-1, 2:]
    )
    middle = xp.concatenate((image[..., 1:-1, 0:1], interior, image[..., 1:-1, -1:]), axis=-1)
    return xp.concatenate((image[..., 0:1, :], middle, image[..., -1:, :]), axis=-2)


class SourceResult(NamedTuple):
    concentration_mol_m3: object
    clamped_mol_m3: object
    after_euler_mol_m3: object
    flux_x_mol_m2_s: object
    flux_y_mol_m2_s: object
    clamp_change_mol: object
    collocated_change_mol: object
    smoothing_change_mol: object


def source_step(
    concentration,
    diffusion,
    bath,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    sharpness=1.0,
    fluid_flow=False,
    extra_mobility=0.0,
    time_dilation=1.0,
    xp=jnp,
):
    if type(fluid_flow) is not bool or not _number(sharpness):
        raise ValueError("Source smoothing and flow guards are explicit scalar controls")
    c = owner_to_grid(concentration, grid, xp=xp)
    d = owner_to_grid(diffusion, grid, xp=xp)
    field = _fields(fields, grid, xp=xp)
    temp = _thermal(thermal, xp=xp)
    b = _field(bath, (len(grid.species_ids),), xp=xp)
    perimeter = xp.asarray(grid.kernel.perimeter).reshape(grid.shape)
    clamped = xp.where(perimeter, b[..., :, None, None], c)
    gx, gy = source_gradient(clamped, grid.delta_m, xp=xp)
    electric = field.electric_V_m.reshape(field.electric_V_m.shape[:-1] + grid.shape)
    velocity = field.velocity_m_s.reshape(field.velocity_m_s.shape[:-1] + grid.shape)
    beta = (temp.elementary_charge_C / (temp.boltzmann_J_K * temp.temperature_K))[
        ..., None, None, None
    ]
    z = xp.asarray(grid.kernel.valence)[:, None, None]
    mobility = _scalar(extra_mobility, xp=xp)[..., None, None, None]
    alpha = d * z * beta + mobility
    ux = velocity[..., 0, None, :, :] if fluid_flow else 0.0
    uy = velocity[..., 1, None, :, :] if fluid_flow else 0.0
    fx = -d * gx + alpha * electric[..., 0, None, :, :] * clamped + ux * clamped
    fy = -d * gy + alpha * electric[..., 1, None, :, :] * clamped + uy * clamped
    dx, _ = source_gradient(-fx, grid.delta_m, negative_boundary=True, xp=xp)
    _, dy = source_gradient(-fy, grid.delta_m, negative_boundary=True, xp=xp)
    step = (_scalar(dt_s, xp=xp) * _scalar(time_dilation, xp=xp))[..., None, None, None]
    euler = clamped + (dx + dy) * step
    updated = source_integrator(euler, sharpness, xp=xp) if sharpness < 1 else euler

    def amount_delta(a, b):
        return xp.sum(
            (grid_to_owner(a, grid, xp=xp) - grid_to_owner(b, grid, xp=xp))
            * xp.asarray(grid.kernel.volume_m3),
            axis=-1,
        )

    return SourceResult(
        grid_to_owner(updated, grid, xp=xp),
        grid_to_owner(clamped, grid, xp=xp),
        grid_to_owner(euler, grid, xp=xp),
        grid_to_owner(fx, grid, xp=xp),
        grid_to_owner(fy, grid, xp=xp),
        amount_delta(clamped, c),
        amount_delta(euler, clamped),
        amount_delta(updated, euler),
    )


def source_domain_valid(
    concentration,
    diffusion,
    bath,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    sharpness=1.0,
    fluid_flow=False,
    extra_mobility=0.0,
    time_dilation=1.0,
    xp=jnp,
):
    try:
        result = source_step(
            concentration,
            diffusion,
            bath,
            fields,
            thermal,
            dt_s,
            grid,
            sharpness=sharpness,
            fluid_flow=fluid_flow,
            extra_mobility=extra_mobility,
            time_dilation=time_dilation,
            xp=xp,
        )
        values = (
            *result,
            concentration,
            diffusion,
            bath,
            *fields,
            *thermal,
            dt_s,
            extra_mobility,
            time_dilation,
        )
        valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in values]))
        valid &= (
            xp.all(xp.asarray(concentration) >= 0)
            & xp.all(xp.asarray(diffusion) >= 0)
            & xp.all(xp.asarray(bath) >= 0)
            & xp.all(result.concentration_mol_m3 >= 0)
        )
        valid &= (
            xp.all(xp.asarray(dt_s) > 0)
            & xp.all(xp.asarray(time_dilation) >= 0)
            & xp.asarray(0 <= sharpness <= 1)
        )
        valid &= xp.all(xp.stack([xp.all(xp.asarray(v) > 0) for v in thermal]))
        return valid
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


@dataclass(frozen=True)
class BathEvent:
    kind: str
    on_s: float
    off_s: float
    change_s: float
    amplitude: float


@dataclass(frozen=True)
class BathBinding:
    grid_identity: str
    events: tuple
    baseline_mol_m3: object
    is_ecm: bool
    enabled_Cl: bool
    identity: str


def compile_baths(grid, events, baseline_mol_m3, *, is_ecm=True, enabled_Cl=True):
    order = ("K_env", "Cl_env", "Na_env")
    rows = tuple(events)
    if (
        type(is_ecm) is not bool
        or type(enabled_Cl) is not bool
        or len({v.kind for v in rows}) != len(rows)
        or any(v.kind not in order for v in rows)
    ):
        raise ValueError("Require unique bath families and explicit source guards")
    rows = tuple(sorted(rows, key=lambda v: order.index(v.kind)))
    base = _field(baseline_mol_m3, (len(grid.species_ids),), xp=np)
    if base.ndim != 1 or not np.isfinite(base).all() or np.any(base < 0):
        raise ValueError("Require finite nonnegative per-species source bath baselines")
    for event in rows:
        if (
            not all(_number(v) for v in (event.on_s, event.off_s, event.change_s, event.amplitude))
            or event.change_s <= 0
        ):
            raise ValueError("Require finite bath timing/amplitude and positive transition")
        if event.kind == "Cl_env" and not enabled_Cl:
            continue
        ion = event.kind.split("_")[0]
        other = "Na" if ion == "Cl" else "M"
        if ion not in grid.species_ids or is_ecm and other not in grid.species_ids:
            raise ValueError("Native bath event requires declared ion and counterion owners")
    payload = dict(
        grid=grid.identity,
        events=[vars(v) for v in rows],
        baseline=base.tolist(),
        is_ecm=is_ecm,
        enabled_Cl=enabled_Cl,
    )
    return BathBinding(grid.identity, rows, _freeze(base), is_ecm, enabled_Cl, _hash(payload))


def source_pulse(time_s, on, off, change, *, xp=jnp):
    time = _scalar(time_s, xp=xp)
    g = 10 / change
    return xp.exp(-xp.logaddexp(0.0, -g * (time - on))) - xp.exp(
        -xp.logaddexp(0.0, -g * (time - off))
    )


class BathResult(NamedTuple):
    boundary_mol_m3: object
    field_mol_m3: object
    boundary_charge_density_change_C_m3: object


def apply_baths(time_s, boundary, field, baths, grid, thermal, *, xp=jnp):
    if baths.grid_identity != grid.identity:
        raise ValueError("Bath event targets belong to another grid/species binding")
    bound = _field(boundary, (len(grid.species_ids),), xp=xp)
    concentration = _field(field, (len(grid.species_ids), len(grid.site_ids)), xp=xp)
    before = bound
    base = xp.asarray(baths.baseline_mol_m3)
    for event in baths.events:
        if event.kind == "Cl_env" and not baths.enabled_Cl:
            continue
        ion = event.kind.split("_")[0]
        at = grid.species_ids.index(ion)
        delta = (
            event.amplitude
            * source_pulse(time_s, event.on_s, event.off_s, event.change_s, xp=xp)
            * base[at]
        )
        if baths.is_ecm:
            other = grid.species_ids.index("Na" if ion == "Cl" else "M")
            mask = (xp.arange(len(grid.species_ids)) == at) | (
                xp.arange(len(grid.species_ids)) == other
            )
            bound = xp.where(mask, base + delta[..., None], bound)
        else:
            mask = xp.arange(len(grid.species_ids)) == at
            concentration = xp.where(
                mask[:, None], (base[at] + delta)[..., None, None], concentration
            )
    charge = _scalar(thermal.faraday_C_mol, xp=xp) * xp.sum(
        (bound - before) * xp.asarray(grid.kernel.valence), axis=-1
    )
    return BathResult(bound, concentration, charge)


def bath_domain_valid(
    time_s, boundary, field, baths, grid, thermal, *, require_neutral_pair=False, xp=jnp
):
    try:
        if type(require_neutral_pair) is not bool:
            return xp.asarray(False)
        result = apply_baths(time_s, boundary, field, baths, grid, thermal, xp=xp)
        valid = xp.all(xp.isfinite(time_s)) & xp.all(
            xp.stack([xp.all(xp.isfinite(v)) for v in result])
        )
        valid &= (
            xp.all(result.boundary_mol_m3 >= 0)
            & xp.all(result.field_mol_m3 >= 0)
            & xp.all(xp.asarray(thermal.faraday_C_mol) > 0)
        )
        if require_neutral_pair:
            scale = _scalar(thermal.faraday_C_mol, xp=xp) * xp.sum(
                xp.abs(
                    (result.boundary_mol_m3 - xp.asarray(boundary))
                    * xp.asarray(grid.kernel.valence)
                ),
                axis=-1,
            )
            valid &= xp.all(xp.abs(result.boundary_charge_density_change_C_m3) <= 3e-13 * scale)
        return valid
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


class FaceCoefficients(NamedTuple):
    left_m_s: object
    right_m_s: object
    peclet: object


def _face_coefficients(
    diffusion, electric, velocity, length, normal, valence, thermal, mobility, *, xp
):
    e = xp.sum(electric * xp.asarray(normal).T, axis=-2)
    u = xp.sum(velocity * xp.asarray(normal).T, axis=-2)
    beta = (thermal.elementary_charge_C / (thermal.boltzmann_J_K * thermal.temperature_K))[
        ..., None, None
    ]
    z = xp.asarray(valence)[:, None]
    w = (diffusion * z * beta + mobility[..., :, None]) * e[..., None, :] + u[..., None, :]
    positive = diffusion > 0
    distance = xp.asarray(length)
    pe = xp.where(positive, w * distance / xp.where(positive, diffusion, 1.0), 0.0)
    left = xp.where(positive, diffusion / distance * bernoulli(-pe, xp=xp), xp.maximum(w, 0.0))
    right = xp.where(positive, diffusion / distance * bernoulli(pe, xp=xp), xp.maximum(-w, 0.0))
    return FaceCoefficients(left, right, pe)


class FaceResult(NamedTuple):
    concentration_mol_m3: object
    amount_mol: object
    amount_change_mol: object
    internal_flux_mol_m2_s: object
    boundary_outward_flux_mol_m2_s: object
    bath_amount_change_mol: object  # [...,species,boundary_face].
    balance_residual_mol: object  # [...,species].
    charge_balance_residual_C: object
    maximum_courant: object
    maximum_abs_peclet: object


def face_step(
    concentration,
    diffusion,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    boundary_open,
    bath_mol_m3,
    mobility_m2_V_s=None,
    xp=jnp,
):
    s, e = len(grid.species_ids), len(grid.site_ids)
    k = grid.kernel
    c = _field(concentration, (s, e), xp=xp)
    d = _field(diffusion, (s, e), xp=xp)
    field = _fields(fields, grid, xp=xp)
    temp = _thermal(thermal, xp=xp)
    dt = _scalar(dt_s, xp=xp)
    opened = xp.asarray(boundary_open)
    if (
        opened.ndim < 1
        or opened.shape[-1] != len(grid.boundary_face_ids)
        or opened.dtype.kind != "b"
    ):
        raise ValueError("Explicit boolean boundary face policies required")
    bath = _field(bath_mol_m3, (s, len(grid.boundary_face_ids)), xp=xp)
    mobility = xp.zeros(s) if mobility_m2_V_s is None else _field(mobility_m2_V_s, (s,), xp=xp)
    a, b = xp.asarray(k.senders), xp.asarray(k.receivers)
    da, db = xp.take(d, a, axis=-1), xp.take(d, b, axis=-1)
    low, high = xp.minimum(da, db), xp.maximum(da, db)
    harmonic = low / (0.5 + 0.5 * low / xp.where(high > 0, high, 1.0))
    electric = (
        xp.take(field.electric_V_m, a, axis=-1) + xp.take(field.electric_V_m, b, axis=-1)
    ) / 2
    velocity = (
        xp.take(field.velocity_m_s, a, axis=-1) + xp.take(field.velocity_m_s, b, axis=-1)
    ) / 2
    internal = _face_coefficients(
        harmonic,
        electric,
        velocity,
        k.internal_distance_m,
        k.internal_normal,
        k.valence,
        temp,
        mobility,
        xp=xp,
    )
    flux = internal.left_m_s * xp.take(c, a, axis=-1) - internal.right_m_s * xp.take(c, b, axis=-1)
    owner = xp.asarray(k.boundary_owner)
    exterior = _face_coefficients(
        xp.take(d, owner, axis=-1),
        xp.take(field.electric_V_m, owner, axis=-1),
        xp.take(field.velocity_m_s, owner, axis=-1),
        k.boundary_distance_m,
        k.boundary_normal,
        k.valence,
        temp,
        mobility,
        xp=xp,
    )
    bflux = xp.where(
        opened[..., None, :],
        exterior.left_m_s * xp.take(c, owner, axis=-1) - exterior.right_m_s * bath,
        0.0,
    )
    rate = flux * xp.asarray(k.internal_area_m2)
    brate = bflux * xp.asarray(k.boundary_area_m2)
    leading = np.broadcast_shapes(c.shape[:-2], rate.shape[:-2], brate.shape[:-2], dt.shape)
    zeros = xp.zeros(leading + (s, e))
    net = (
        ordered_scatter(-rate, zeros, (a,), xp=xp)
        + ordered_scatter(rate, zeros, (b,), xp=xp)
        - ordered_scatter(brate, zeros, (owner,), xp=xp)
    )
    delta = net * dt[..., None, None]
    amount = c * xp.asarray(k.volume_m3) + delta
    bath_delta = brate * dt[..., None, None]
    residual = xp.sum(delta, axis=-1) + xp.sum(bath_delta, axis=-1)
    outgoing = ordered_scatter(
        internal.left_m_s * xp.asarray(k.internal_area_m2), zeros, (a,), xp=xp
    ) + ordered_scatter(internal.right_m_s * xp.asarray(k.internal_area_m2), zeros, (b,), xp=xp)
    outgoing += ordered_scatter(
        xp.where(opened[..., None, :], exterior.left_m_s * xp.asarray(k.boundary_area_m2), 0.0),
        zeros,
        (owner,),
        xp=xp,
    )
    courant = xp.max(outgoing / xp.asarray(k.volume_m3) * dt[..., None, None], axis=(-2, -1))
    pe = xp.maximum(
        xp.max(xp.abs(internal.peclet), axis=(-2, -1)),
        xp.max(xp.abs(exterior.peclet), axis=(-2, -1)),
    )
    charge = temp.faraday_C_mol * xp.sum(residual * xp.asarray(k.valence), axis=-1)
    return FaceResult(
        amount / xp.asarray(k.volume_m3),
        amount,
        delta,
        flux,
        bflux,
        bath_delta,
        residual,
        charge,
        courant,
        pe,
    )


def face_domain_valid(
    concentration,
    diffusion,
    fields,
    thermal,
    dt_s,
    grid,
    *,
    boundary_open,
    bath_mol_m3,
    mobility_m2_V_s=None,
    xp=jnp,
):
    try:
        result = face_step(
            concentration,
            diffusion,
            fields,
            thermal,
            dt_s,
            grid,
            boundary_open=boundary_open,
            bath_mol_m3=bath_mol_m3,
            mobility_m2_V_s=mobility_m2_V_s,
            xp=xp,
        )
        values = (*result, concentration, diffusion, *fields, *thermal, dt_s, bath_mol_m3)
        if mobility_m2_V_s is not None:
            values = (*values, mobility_m2_V_s)
        valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in values]))
        valid &= (
            xp.all(xp.asarray(concentration) >= 0)
            & xp.all(xp.asarray(diffusion) >= 0)
            & xp.all(xp.asarray(bath_mol_m3) >= 0)
            & xp.all(result.amount_mol >= 0)
        )
        valid &= xp.all(xp.asarray(dt_s) > 0) & xp.all(
            xp.stack([xp.all(xp.asarray(v) > 0) for v in thermal])
        )
        valid &= xp.all(result.maximum_courant <= 1) & xp.all(result.maximum_abs_peclet <= 500)
        scale = xp.sum(xp.abs(result.amount_change_mol), axis=-1) + xp.sum(
            xp.abs(result.bath_amount_change_mol), axis=-1
        )
        valid &= xp.all(xp.abs(result.balance_residual_mol) <= 3e-13 * scale)
        return valid
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)


def grid_manifest(grid):
    return dict(
        source_law_id=SOURCE_LAW_ID,
        face_law_id=FACE_LAW_ID,
        identity=grid.identity,
        site_ids=grid.site_ids,
        species_ids=grid.species_ids,
        shape=grid.shape,
        delta_m=grid.delta_m,
        height_m=grid.height_m,
        internal_face_ids=grid.internal_face_ids,
        boundary_face_ids=grid.boundary_face_ids,
        boundary_sides=grid.boundary_face_sides,
        provenance=json.loads(grid.provenance_json),
    )


def validate_grid_manifest(manifest, grid):
    expected = grid_manifest(grid)
    if manifest != expected and manifest != json.loads(json.dumps(expected)):
        raise ValueError("Stale grid/site/species/face/measure identity")
    return expected
