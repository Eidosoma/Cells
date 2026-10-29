"""Pinned native tissue selectors, explicit stable owners and intervention maps.

Host bindings retain ordered duplicate target occurrences and source ALL aliases
without mutating the authoritative layout. Percentage permutations are explicit
inputs; physical geometry, RNG streams, cutting and solver/checkpoint state are
caller-owned. Numerical kernels operate only on declared owner axes.
"""

import hashlib
import json
from dataclasses import dataclass
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

LAW_ID = "betse_tissue_profiles_source_v1_5_0@1"
IONS = ("Na", "K", "Cl", "Ca", "M", "P")
EVENT_ORDER = ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")
MEMBRANE_EVENT, PRESSURE_EVENT, ECM_EVENT = 1, 2, 3
DOMAINS = ("cell", "membrane", "environment")


def _frozen(value, dtype=None):
    array = np.array(value, dtype=dtype, copy=True)
    array.setflags(write=False)
    return array


def _ids(values):
    if (
        not isinstance(values, (tuple, list))
        or any(not isinstance(v, str) or not v for v in values)
        or len(set(values)) != len(values)
    ):
        raise ValueError("Require unique nonempty stable string owner IDs")
    return tuple(values)


def _number(value):
    return (
        isinstance(value, Real) and not isinstance(value, (bool, np.bool_)) and np.isfinite(value)
    )


def _hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class Layout:
    cell_ids: tuple
    membrane_ids: tuple
    environment_ids: tuple
    membrane_cell_ids: tuple
    membrane_environment_ids: tuple  # None explicitly means unbound.
    cell_membrane_ids: tuple  # Explicit per-cell membrane order, not inferred.
    cell_centres_m: object
    bounds_m: tuple  # xmin,xmax,ymin,ymax, as used by native image picker.
    seed_fills: tuple | None = None


@dataclass(frozen=True)
class Bitmap:
    grayscale_F: object  # Native PIL F pixels; threshold precedes interpolation.


@dataclass(frozen=True)
class Selector:
    kind: str
    value: object = None
    expected_layout_identity: str | None = None  # Required for native indices.
    permutation_cell_ids: tuple | None = None  # Complete explicit percent order.


@dataclass(frozen=True)
class Profile:
    name: str
    selector: Selector
    diffusivity_m2_s: tuple  # Native IONS order.
    is_gj_insular: bool = False


@dataclass(frozen=True)
class Target:
    domain: str
    ids: tuple
    indices: object
    owner_count: int
    layout_identity: str


@dataclass(frozen=True)
class ProfileTargets:
    cells: Target  # Final native ALL alias order, if ALL.
    membranes: Target  # Pick-time flattened sequence.
    environments: Target
    environment_declared: bool  # Native omits empty/non-ECM environment keys.
    picked_cell_ids: tuple


class ProfileKernel(NamedTuple):
    cells: object
    membranes: object
    environments: object
    diffusivity_m2_s: object  # [ion,profile].
    ion_enabled: object
    insular: object


@dataclass(frozen=True)
class Binding:
    layout: Layout
    layout_identity: str
    names: tuple
    targets: object
    kernel: ProfileKernel
    final_cell_order: tuple
    is_ecm: bool


@dataclass(frozen=True)
class Sampled:
    values: object
    axis: str  # "occurrence" or an explicitly named owner domain.


@dataclass(frozen=True)
class Intervention:
    name: str
    kind: str
    profiles: tuple
    on_s: float
    off_s: float
    change_s: float
    amplitude: float
    spatial: Sampled | None = None
    source_function: str = "None"  # Other callbacks require explicit samples.


class InterventionKernel(NamedTuple):
    cell_slots: object
    membrane_slots: object
    environment_slots: object
    kind: object
    ion: object
    guard: object
    targets: object
    selected: object
    on_s: object
    off_s: object
    change_s: object
    amplitude: object
    spatial: object
    default_diffusivity_m2_s: object


@dataclass(frozen=True)
class InterventionBinding:
    profiles_identity: str
    names: tuple
    targets: tuple
    kernel: InterventionKernel


class InterventionState(NamedTuple):
    membrane_base_m2_s: object  # [...,ion,membrane].
    membrane_scheduled_m2_s: object
    pressure_base_Pa: object  # [...,cell].
    pressure_mod_Pa: object
    environment_base_m2_s: object  # [...,ion,environment].
    environment_current_m2_s: object
    environment_free_m2_s: object  # [...,ion].
    environment_weight_base: object  # [...,environment], explicitly flat.
    environment_weight_current: object


class InterventionResult(NamedTuple):
    state: InterventionState
    membrane_total_m2_s: object
    pressure_total_Pa: object
    pulse: object


def validate_layout(layout):
    cells, membranes, environments = (_ids(getattr(layout, key + "_ids")) for key in DOMAINS)
    owners, outside = tuple(layout.membrane_cell_ids), tuple(layout.membrane_environment_ids)
    groups = tuple(tuple(group) for group in layout.cell_membrane_ids)
    centres, bounds = np.asarray(layout.cell_centres_m), np.asarray(layout.bounds_m)
    if centres.size == 0 and not cells:
        centres = np.empty((0, 2))
    if (
        len(owners) != len(membranes)
        or len(outside) != len(membranes)
        or len(groups) != len(cells)
        or any(v not in cells for v in owners)
        or any(v is not None and v not in environments for v in outside)
    ):
        raise ValueError("Invalid explicit stable membrane owners")
    flattened = [v for group in groups for v in group]
    if (
        len(flattened) != len(membranes)
        or set(flattened) != set(membranes)
        or len(set(flattened)) != len(flattened)
        or any(
            owners[membranes.index(v)] != cell
            for cell, group in zip(cells, groups, strict=True)
            for v in group
        )
    ):
        raise ValueError("Per-cell membrane order must partition declared owned membranes")
    if (
        centres.shape != (len(cells), 2)
        or centres.dtype.kind not in "fiu"
        or not np.isfinite(centres).all()
        or bounds.shape != (4,)
        or bounds.dtype.kind not in "fiu"
        or not np.isfinite(bounds).all()
        or bounds[0] >= bounds[1]
        or bounds[2] >= bounds[3]
    ):
        raise ValueError("Require explicit finite centres and nondegenerate image bounds")
    fills = None if layout.seed_fills is None else tuple(layout.seed_fills)
    if fills is not None and (
        len(fills) != len(cells) or any(not isinstance(v, str) for v in fills)
    ):
        raise ValueError("SVG fill tags require an explicit cell axis")
    return Layout(
        cells,
        membranes,
        environments,
        owners,
        outside,
        groups,
        _frozen(centres, float),
        tuple(float(v) for v in bounds),
        fills,
    )


def layout_identity(layout):
    t = validate_layout(layout)
    return _hash(
        dict(
            law_id=LAW_ID,
            **{
                key: (value.tolist() if isinstance(value, np.ndarray) else value)
                for key, value in vars(t).items()
            },
        )
    )


def bitmap_data(bitmap, bounds_m):
    gray = np.asarray(bitmap.grayscale_F, dtype=np.float32)
    if (
        gray.ndim != 2
        or gray.shape[0] != gray.shape[1]
        or not 4 <= gray.shape[0] <= 1024
        or not np.isfinite(gray).all()
    ):
        raise ValueError("Native masks require finite square F pixels, size4..1024")
    points = np.argwhere(gray != 255.0)
    edge = points[1] - points[0] if len(points) >= 2 else np.zeros(2, int)
    rest = points[2:] - points[0] if len(points) else np.empty((0, 2), int)
    if len(points) < 3 or not np.any(edge[0] * rest[:, 1] - edge[1] * rest[:, 0]):
        raise ValueError("Native mask ConvexHull requires noncollinear non-white pixels")
    xmin, xmax, ymin, ymax = bounds_m
    return (
        _frozen(np.flipud(gray != 255.0), float),
        _frozen(np.linspace(xmin, xmax, len(gray))),
        _frozen(np.linspace(ymin, ymax, len(gray))),
    )


def bitmap_values(points_m, mask, x_nodes, y_nodes, *, xp=jnp):
    """Literal transposed native linear-spline values with rectangular clamping."""
    points, z, x, y = (xp.asarray(v) for v in (points_m, mask, x_nodes, y_nodes))
    if (
        points.ndim < 2
        or points.shape[-1] != 2
        or x.ndim != 1
        or y.ndim != 1
        or z.shape != (y.size, x.size)
        or min(x.size, y.size) < 2
    ):
        raise ValueError("Explicit point/grid axes required")
    xx, yy = xp.clip(points[..., 0], x[0], x[-1]), xp.clip(points[..., 1], y[0], y[-1])
    ix = xp.clip(xp.searchsorted(x, xx, side="right") - 1, 0, x.size - 2)
    iy = xp.clip(xp.searchsorted(y, yy, side="right") - 1, 0, y.size - 2)
    wx, wy = (xx - x[ix]) / (x[ix + 1] - x[ix]), (yy - y[iy]) / (y[iy + 1] - y[iy])
    return (1 - wy) * ((1 - wx) * z[iy, ix] + wx * z[iy, ix + 1]) + wy * (
        (1 - wx) * z[iy + 1, ix] + wx * z[iy + 1, ix + 1]
    )


def _target(layout, domain, ids):
    owners = getattr(layout, domain + "_ids")
    if any(value not in owners for value in ids):
        raise ValueError("Unknown target stable owner ID")
    return Target(
        domain,
        tuple(ids),
        _frozen([owners.index(v) for v in ids], np.int64),
        len(owners),
        layout_identity(layout),
    )


def targets_for_cell_ids(layout, cell_ids, *, is_ecm=True):
    t = validate_layout(layout)
    if not isinstance(cell_ids, (list, tuple)) or type(is_ecm) is not bool:
        raise ValueError("Require an explicit stable cell-ID sequence and ECM flag")
    ids = tuple(cell_ids)
    if any(v not in t.cell_ids for v in ids):
        raise ValueError("Unknown selected stable cell ID")
    membranes = tuple(v for cell in ids for v in t.cell_membrane_ids[t.cell_ids.index(cell)])
    declared = bool(ids) and is_ecm
    outside = (
        tuple(t.membrane_environment_ids[t.membrane_ids.index(v)] for v in membranes)
        if declared
        else ()
    )
    if any(v is None for v in outside):
        raise ValueError("Selected native ECM membrane has no explicit environment owner")
    return ProfileTargets(
        _target(t, "cell", ids),
        _target(t, "membrane", membranes),
        _target(t, "environment", outside),
        declared,
        ids,
    )


def compile_profiles(
    layout, default, profiles, *, ion_enabled=(True,) * 6, is_ecm=True, enabled=True
):
    t = validate_layout(layout)
    identity = layout_identity(t)
    if type(is_ecm) is not bool or type(enabled) is not bool:
        raise ValueError("Explicit profile/ECM booleans required")
    flags = np.asarray(ion_enabled)
    if flags.shape != (6,) or flags.dtype.kind != "b":
        raise ValueError("Require explicit native IONS enable flags")
    rows = [default, *profiles] if enabled else []
    names = [row.name for row in rows]
    if len(set(names)) != len(names) or any(
        not isinstance(name, str) or not name for name in names
    ):
        raise ValueError("Duplicate or empty profile name")
    current_order = list(t.cell_ids)
    targets, all_aliases, diffusivity, insular = {}, [], [], []
    for index, row in enumerate(rows):
        dm = np.asarray(row.diffusivity_m2_s)
        if (
            dm.shape != (6,)
            or dm.dtype.kind not in "fiu"
            or not np.isfinite(dm).all()
            or np.any(dm < 0)
            or type(row.is_gj_insular) is not bool
        ):
            raise ValueError(
                "Native profile Dm requires six nonnegative coefficients and an insular flag"
            )
        selector = Selector("all") if index == 0 else row.selector
        kind, value = selector.kind, selector.value
        if kind == "all":
            selected = list(current_order)
            all_aliases.append(row.name)
        elif kind == "ids":
            if not isinstance(value, (tuple, list)) or any(v not in t.cell_ids for v in value):
                raise ValueError("Stable selectors require explicit known cell IDs")
            selected = list(value)
        elif kind == "indices":
            indices = np.asarray(value)
            if indices.size == 0 and indices.shape == (0,):
                indices = np.empty(0, int)
            if (
                selector.expected_layout_identity != identity
                or indices.ndim != 1
                or indices.dtype.kind not in "iu"
                or np.any((indices < 0) | (indices >= len(t.cell_ids)))
            ):
                raise ValueError(
                    "Native positional indices require matching layout identity "
                    "and explicit integer cell axis"
                )
            selected = [t.cell_ids[int(i)] for i in indices]
        elif kind == "color":
            if t.seed_fills is None or not isinstance(value, str):
                raise ValueError("Color picker requires explicit SVG fill tags and exact string")
            selected = [
                cell for cell, fill in zip(t.cell_ids, t.seed_fills, strict=True) if fill == value
            ]
        elif kind == "percent":
            order = selector.permutation_cell_ids
            if (
                not _number(value)
                or not 0 <= value <= 100
                or order is None
                or len(order) != len(t.cell_ids)
                or set(order) != set(t.cell_ids)
                or len(set(order)) != len(order)
            ):
                raise ValueError(
                    "Percent picker requires valid percentage "
                    "and explicit full stable-ID permutation"
                )
            current_order = list(order)
            selected = current_order[: int((float(value) / 100) * len(t.cell_ids))]
        elif kind == "image":
            if not isinstance(value, Bitmap):
                raise ValueError("Image picker requires native decoded F bitmap")
            data = bitmap_data(value, t.bounds_m)
            values = bitmap_values(t.cell_centres_m, *data, xp=np)
            selected = [cell for cell, v in zip(t.cell_ids, values, strict=True) if v != 0.0]
        else:
            raise ValueError("Unsupported native selector kind")
        targets[row.name] = targets_for_cell_ids(t, selected, is_ecm=is_ecm)
        diffusivity.append(dm)
        insular.append(True if index == 0 else row.is_gj_insular)
    # Native ALL returns the live cell_i array; later percentage shuffles alter
    # those stored cell arrays but not already-materialized membrane targets.
    for name in all_aliases:
        old = targets[name]
        targets[name] = ProfileTargets(
            _target(t, "cell", current_order),
            old.membranes,
            old.environments,
            old.environment_declared,
            old.picked_cell_ids,
        )
    masks = []
    for domain in DOMAINS:
        owner_ids = getattr(t, domain + "_ids")
        selected_field = {"cell": "cells", "membrane": "membranes", "environment": "environments"}[
            domain
        ]
        masks.append(
            _frozen(
                [
                    [value in getattr(targets[name], selected_field).ids for value in owner_ids]
                    for name in names
                ],
                bool,
            ).reshape(len(names), len(owner_ids))
        )
    matrix = _frozen(np.asarray(diffusivity, float).reshape(len(rows), 6).T)
    kernel = ProfileKernel(*masks, matrix, _frozen(flags), _frozen(insular, bool))
    return Binding(
        t, identity, tuple(names), MappingProxyType(targets), kernel, tuple(current_order), is_ecm
    )


def binding_manifest(binding):
    b = binding
    targets = {
        name: dict(
            cells=t.cells.ids,
            membranes=t.membranes.ids,
            environments=t.environments.ids,
            environment_declared=t.environment_declared,
            picked_cells=t.picked_cell_ids,
        )
        for name, t in b.targets.items()
    }
    record = dict(
        law_id=LAW_ID,
        layout_identity=b.layout_identity,
        names=b.names,
        targets=targets,
        final_cell_order=b.final_cell_order,
        is_ecm=b.is_ecm,
        kernel={key: value.tolist() for key, value in b.kernel._asdict().items()},
    )
    return dict(record, identity=_hash(record))


def validate_binding_manifest(manifest, binding):
    expected = binding_manifest(binding)
    if manifest != json.loads(json.dumps(expected)) and manifest != expected:
        raise ValueError("Stale profile layout, selection, order or parameter identity")
    return expected


def bind_targets(binding, profile_names, *, domain):
    if (
        domain not in DOMAINS
        or not isinstance(profile_names, (tuple, list))
        or any(name not in binding.targets for name in profile_names)
    ):
        raise ValueError("Require ordered profile names and an explicit owner domain")
    fields = {"cell": "cells", "membrane": "membranes", "environment": "environments"}
    rows = [binding.targets[name] for name in profile_names]
    if domain == "environment" and any(not row.environment_declared for row in rows):
        raise ValueError("Native environment targets absent for empty/non-ECM profile")
    ids = tuple(value for row in rows for value in getattr(row, fields[domain]).ids)
    return _target(binding.layout, domain, ids)


def gather_owner_field(values, target, *, domain, axis, xp=jnp):
    value = xp.asarray(values)
    if (
        domain != target.domain
        or type(axis) is not int
        or not -value.ndim <= axis < value.ndim
        or value.shape[axis] != target.owner_count
    ):
        raise ValueError("Declared field axis/domain does not match target ownership")
    return xp.take(value, xp.asarray(target.indices), axis=axis)


def carry_cell_targets(binding, new_layout, *, missing="reject"):
    """Explicit Cells carry policy; native post-cut code instead reruns selectors."""
    t = validate_layout(new_layout)
    if missing not in ("reject", "drop"):
        raise ValueError("Choose explicit missing-ID policy reject/drop")
    result = {}
    for name, old in binding.targets.items():
        ids = old.cells.ids
        if missing == "reject" and any(v not in t.cell_ids for v in ids):
            raise ValueError("Removed selected owner requires explicit drop policy")
        result[name] = targets_for_cell_ids(
            t, [v for v in ids if v in t.cell_ids], is_ecm=binding.is_ecm
        )
    return MappingProxyType(result)


def apply_profile_diffusion(initial_m2_s, kernel, *, xp=jnp):
    value = xp.asarray(initial_m2_s)
    if (
        value.ndim < 2
        or value.shape[-2:] != (6, kernel.membranes.shape[-1])
        or value.dtype.kind not in "fiu"
    ):
        raise ValueError("Profile diffusion requires [...,native ion,membrane] axes")
    result = value
    for i in range(kernel.membranes.shape[0]):
        selected = kernel.ion_enabled[:, None] & kernel.membranes[i]
        result = xp.where(selected, kernel.diffusivity_m2_s[:, i, None], result)
    return result


def insular_membrane_weights(binding, partner_membrane, original_cell_neighbors, *, xp=jnp):
    """Native region-crossing blockers; returns weights, does not rebuild graph."""
    b, partner, neighbors = (
        binding,
        xp.asarray(partner_membrane),
        xp.asarray(original_cell_neighbors),
    )
    m, n = len(b.layout.membrane_ids), len(b.layout.cell_ids)
    if (
        partner.shape != (m,)
        or partner.dtype.kind not in "iu"
        or neighbors.shape != (n, n)
        or neighbors.dtype.kind != "b"
    ):
        raise ValueError("Explicit membrane partners and cell-neighbor axes required")
    if xp is np and (
        np.any((partner < 0) | (partner >= m)) or not np.array_equal(partner[partner], np.arange(m))
    ):
        raise ValueError("Membrane partners must be valid reciprocal owner indices")
    owner = xp.asarray([b.layout.cell_ids.index(v) for v in b.layout.membrane_cell_ids], dtype=int)
    other = owner[partner]
    blocked = xp.zeros(m, bool)
    for i in range(len(b.names)):
        membership = xp.asarray(b.kernel.cells[i])
        blocked |= b.kernel.insular[i] & (membership[owner] != membership[other])
    return xp.where((partner != xp.arange(m)) & (blocked | ~neighbors[owner, other]), 0.0, 1.0)


def global_gj_prefix_targets(layout, requested_percent):
    """Native global GJ target bug: shuffled copy is unused; actual prefix wins."""
    t = validate_layout(layout)
    if not _number(requested_percent):
        raise ValueError("Require finite numeric global GJ percentage")
    percent = min(100, max(1, int(requested_percent)))
    return _target(t, "membrane", t.membrane_ids[: int((percent / 100) * len(t.membrane_ids))])


def compile_interventions(binding, interventions, *, event_capacity=None, target_capacity=None):
    rows = list(interventions)
    if (
        len({r.kind for r in rows}) != len(rows)
        or len({r.name for r in rows}) != len(rows)
        or any(r.kind not in EVENT_ORDER or not isinstance(r.name, str) or not r.name for r in rows)
    ):
        raise ValueError("Native supports one intervention per kind and unique names")
    rows.sort(key=lambda row: EVENT_ORDER.index(row.kind))
    capacity = len(rows) if event_capacity is None else event_capacity
    if type(capacity) is not int or capacity < len(rows) or not binding.names and rows:
        raise ValueError("Enabled events require profiles and adequate capacity")
    targets, parsed = [], []
    for row in rows:
        if (
            not all(_number(v) for v in (row.on_s, row.off_s, row.change_s, row.amplitude))
            or row.change_s <= 0
            or not isinstance(row.source_function, str)
        ):
            raise ValueError("Require finite source timing/amplitude and positive transition time")
        if row.kind == "ecmJ" and not binding.is_ecm:
            raise ValueError("Native ECM-disabled junction intervention is uninitialized")
        if row.kind == "ecmJ" and (row.spatial is not None or row.source_function != "None"):
            raise ValueError("Native ECM junction intervention has no spatial callback")
        domain = (
            "cell"
            if row.kind == "pressure"
            else "environment"
            if row.kind == "ecmJ"
            else "membrane"
        )
        target = bind_targets(binding, row.profiles, domain=domain)
        if row.source_function != "None" and row.spatial is None:
            raise ValueError("Named source callback requires explicit sampled ownership")
        if row.spatial is None:
            samples = np.ones(len(target.ids))
        else:
            a = np.asarray(row.spatial.values)
            if a.dtype.kind not in "fiu" or not np.isfinite(a).all():
                raise ValueError("Invalid finite spatial callback samples")
            if row.spatial.axis == "occurrence":
                if a.shape not in ((), (len(target.ids),)):
                    raise ValueError("Spatial occurrence samples must match ordered targets")
                samples = np.broadcast_to(a, (len(target.ids),))
            elif row.spatial.axis in DOMAINS:
                samples = gather_owner_field(a, target, domain=row.spatial.axis, axis=-1, xp=np)
                if samples.ndim != 1:
                    raise ValueError("Bound spatial owner samples require one value per owner")
            else:
                raise ValueError("Declare spatial occurrence or explicit owner axis")
        targets.append(target)
        parsed.append(samples)
    target_count = max((len(t.ids) for t in targets), default=0)
    tc = target_count if target_capacity is None else target_capacity
    if type(tc) is not int or tc < target_count:
        raise ValueError("Target capacity must hold duplicate occurrences")
    arrays = dict(
        kind=np.zeros(capacity, int),
        ion=np.zeros(capacity, int),
        guard=np.zeros(capacity, bool),
        targets=np.zeros((capacity, tc), int),
        selected=np.zeros((capacity, tc), bool),
        on_s=np.zeros(capacity),
        off_s=np.zeros(capacity),
        change_s=np.ones(capacity),
        amplitude=np.zeros(capacity),
        spatial=np.zeros((capacity, tc)),
    )
    for i, (row, target, samples) in enumerate(zip(rows, targets, parsed, strict=True)):
        kind = (
            PRESSURE_EVENT
            if row.kind == "pressure"
            else ECM_EVENT
            if row.kind == "ecmJ"
            else MEMBRANE_EVENT
        )
        ion = IONS.index(row.kind.split("_")[0]) if kind == MEMBRANE_EVENT else 0
        arrays["kind"][i], arrays["ion"][i] = kind, ion
        arrays["guard"][i] = (
            bool(binding.kernel.ion_enabled[ion]) if row.kind in ("Cl_mem", "Ca_mem") else True
        )
        for key in ("on_s", "off_s", "change_s", "amplitude"):
            arrays[key][i] = getattr(row, key)
        count = len(target.ids)
        (
            arrays["targets"][i, :count],
            arrays["selected"][i, :count],
            arrays["spatial"][i, :count],
        ) = target.indices, True, samples
    counts = [len(getattr(binding.layout, key + "_ids")) for key in DOMAINS]
    kernel = InterventionKernel(
        *(_frozen(np.ones(v, bool)) for v in counts),
        *(
            _frozen(arrays[key])
            for key in (
                "kind",
                "ion",
                "guard",
                "targets",
                "selected",
                "on_s",
                "off_s",
                "change_s",
                "amplitude",
                "spatial",
            )
        ),
        _frozen(binding.kernel.diffusivity_m2_s[:, 0] if binding.names else np.zeros(6)),
    )
    return InterventionBinding(
        binding_manifest(binding)["identity"],
        tuple(row.name for row in rows),
        tuple(targets),
        kernel,
    )


def intervention_manifest(events, profiles):
    """Identity metadata only; caller separately checkpoints buffers/time/RNG."""
    if events.profiles_identity != binding_manifest(profiles)["identity"]:
        raise ValueError("Intervention target maps belong to a different profile binding")
    record = dict(
        law_id=LAW_ID,
        profiles_identity=events.profiles_identity,
        names=events.names,
        targets=[
            dict(domain=t.domain, ids=t.ids, layout_identity=t.layout_identity)
            for t in events.targets
        ],
        kernel={key: value.tolist() for key, value in events.kernel._asdict().items()},
    )
    return dict(record, identity=_hash(record))


def validate_intervention_manifest(manifest, events, profiles):
    expected = intervention_manifest(events, profiles)
    if manifest != expected and manifest != json.loads(json.dumps(expected)):
        raise ValueError("Stale intervention kind, timing, occurrence order or owner identity")
    return expected


def source_pulse(time_s, kernel, *, xp=jnp):
    time = xp.asarray(time_s)
    if not time.ndim:
        time = time.reshape((1,))
    if time.shape[-1] != 1 or time.dtype.kind not in "fiu":
        raise ValueError("Time requires a singleton final world axis")
    g = 10 / kernel.change_s
    first = xp.exp(-xp.logaddexp(0.0, -g * (time - kernel.on_s)))
    second = xp.exp(-xp.logaddexp(0.0, -g * (time - kernel.off_s)))
    return first - second


def _state(state, kernel, *, xp):
    n, m, e = kernel.cell_slots.size, kernel.membrane_slots.size, kernel.environment_slots.size
    tails = ((6, m), (6, m), (n,), (n,), (6, e), (6, e), (6,), (e,), (e,))
    arrays = [xp.asarray(v) for v in state]
    if any(
        v.dtype.kind not in "fiu" or v.ndim < len(tail) or v.shape[-len(tail) :] != tail
        for v, tail in zip(arrays, tails, strict=True)
    ):
        raise ValueError("Intervention buffers require explicit ion/cell/membrane/environment axes")
    return arrays, tails


def apply_interventions(time_s, state, kernel, dynamic_factor=1.0, *, xp=jnp):
    """Ordered source writes, duplicate-last assignment and final base addition.

    Spatial/dynamic callbacks are sampled explicitly. Signed source factors are
    retained; physical diffusion/current/material acceptance belongs to callers.
    """
    arrays, tails = _state(state, kernel, xp=xp)
    pulse, dynamic = source_pulse(time_s, kernel, xp=xp), xp.asarray(dynamic_factor)
    effect = pulse * dynamic * kernel.amplitude
    leading = np.broadcast_shapes(
        effect.shape[:-1], *(v.shape[: -len(tail)] for v, tail in zip(arrays, tails, strict=True))
    )
    arrays = [xp.broadcast_to(v, leading + tail) for v, tail in zip(arrays, tails, strict=True)]
    if xp is np:
        arrays = [v.copy() for v in arrays]
    current = InterventionState(*arrays)
    effect = xp.broadcast_to(effect, leading + (kernel.kind.size,))
    nt = kernel.targets.shape[-1]

    def set_value(value, key, new):
        if xp is np:
            value[key] = new
            return value
        return value.at[key].set(new)

    def update(flat, s):
        row, slot = flat // nt, flat % nt
        kind, ion, target = kernel.kind[row], kernel.ion[row], kernel.targets[row, slot]
        enabled = kernel.selected[row, slot] & kernel.guard[row]
        eff = effect[..., row]
        spatial = kernel.spatial[row, slot]
        dm, pressure, env, weight = (
            s.membrane_scheduled_m2_s,
            s.pressure_mod_Pa,
            s.environment_current_m2_s,
            s.environment_weight_current,
        )
        if dm.shape[-1]:
            at = xp.clip(target, 0, dm.shape[-1] - 1)
            key = (Ellipsis, ion, at)
            new = kernel.default_diffusivity_m2_s[ion] * eff * spatial
            dm = set_value(dm, key, xp.where(enabled & (kind == MEMBRANE_EVENT), new, dm[key]))
        if pressure.shape[-1]:
            at = xp.clip(target, 0, pressure.shape[-1] - 1)
            key = (Ellipsis, at)
            pressure = set_value(
                pressure,
                key,
                xp.where(enabled & (kind == PRESSURE_EVENT), eff * spatial, pressure[key]),
            )
        if env.shape[-1]:
            at = xp.clip(target, 0, env.shape[-1] - 1)
            key = (Ellipsis, slice(None), at)
            new = (
                s.environment_base_m2_s[key] * (1 - eff[..., None])
                + eff[..., None] * s.environment_free_m2_s
            )
            env = set_value(env, key, xp.where(enabled & (kind == ECM_EVENT), new, env[key]))
            keyw = (Ellipsis, at)
            neww = s.environment_weight_base[keyw] * (1 - eff) + eff
            weight = set_value(
                weight, keyw, xp.where(enabled & (kind == ECM_EVENT), neww, weight[keyw])
            )
        return s._replace(
            membrane_scheduled_m2_s=dm,
            pressure_mod_Pa=pressure,
            environment_current_m2_s=env,
            environment_weight_current=weight,
        )

    count = kernel.kind.size * nt
    if xp is np:
        for flat in range(count):
            current = update(flat, current)
    elif count:
        current = jax.lax.fori_loop(0, count, update, current)
    return InterventionResult(
        current,
        current.membrane_base_m2_s + current.membrane_scheduled_m2_s,
        current.pressure_base_Pa + current.pressure_mod_Pa,
        pulse,
    )


def intervention_domain_valid(time_s, state, kernel, dynamic_factor=1.0, *, xp=jnp):
    try:
        r = kernel.kind.size
        if (
            any(v.ndim != 1 or v.dtype.kind != "b" for v in kernel[:3])
            or kernel.kind.ndim != 1
            or kernel.kind.dtype.kind not in "iu"
            or kernel.ion.shape != (r,)
            or kernel.ion.dtype.kind not in "iu"
            or kernel.guard.shape != (r,)
            or kernel.guard.dtype.kind != "b"
            or kernel.targets.ndim != 2
            or kernel.targets.shape[0] != r
            or kernel.targets.dtype.kind not in "iu"
            or kernel.selected.shape != kernel.targets.shape
            or kernel.selected.dtype.kind != "b"
            or any(v.shape != (r,) or v.dtype.kind not in "fiu" for v in kernel[8:12])
            or kernel.spatial.shape != kernel.targets.shape
            or kernel.spatial.dtype.kind not in "fiu"
            or kernel.default_diffusivity_m2_s.shape != (6,)
            or kernel.default_diffusivity_m2_s.dtype.kind not in "fiu"
        ):
            return xp.asarray(False)
        arrays, _ = _state(state, kernel, xp=xp)
        valid = xp.all(
            xp.stack(
                [
                    xp.all(xp.isfinite(v))
                    for v in (*arrays, *kernel, xp.asarray(time_s), xp.asarray(dynamic_factor))
                ]
            )
        )
        valid &= xp.all((kernel.kind >= 0) & (kernel.kind <= ECM_EVENT)) & xp.all(
            (kernel.ion >= 0) & (kernel.ion < 6)
        )
        valid &= xp.all(kernel.change_s > 0)
        valid &= xp.all(kernel.default_diffusivity_m2_s >= 0)
        valid &= xp.all(xp.stack([xp.all(v) for v in kernel[:3]]))
        bounds = xp.where(
            kernel.kind == MEMBRANE_EVENT,
            kernel.membrane_slots.size,
            xp.where(
                kernel.kind == PRESSURE_EVENT, kernel.cell_slots.size, kernel.environment_slots.size
            ),
        )
        valid &= xp.all(
            xp.where(
                kernel.selected,
                (kernel.targets >= 0) & (kernel.targets < bounds[:, None]),
                kernel.targets == 0,
            )
        )
        valid &= xp.all(
            xp.where(
                kernel.kind == 0,
                ~kernel.guard & ~xp.any(kernel.selected, axis=-1) & (kernel.amplitude == 0),
                True,
            )
        )
        valid &= xp.all(xp.where(kernel.selected, True, kernel.spatial == 0))
        dynamic = xp.asarray(dynamic_factor)
        if dynamic.dtype.kind not in "fiu":
            return xp.asarray(False)
        valid &= xp.all(xp.where(kernel.kind == ECM_EVENT, dynamic == 1, True))
        result = apply_interventions(time_s, state, kernel, dynamic_factor, xp=xp)
        return valid & xp.all(
            xp.stack([xp.all(xp.isfinite(v)) for v in (*result.state, *result[1:])])
        )
    except (ValueError, TypeError, IndexError, AttributeError):
        return xp.asarray(False)
