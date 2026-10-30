"""Native environment current/field reconstruction with derived grid operators.

This joins the original intracellular current prefix to the literal environment
branches. Source HH/Gaussian arrays are diagnostic source outputs, not a
conservative physical field, energy closure or an advancing ionic solver.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from numbers import Real
from types import MappingProxyType
from typing import NamedTuple

import numpy as np
from scipy.ndimage import gaussian_filter
from scipy.spatial import cKDTree

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current

LAW_ID = "betse_environment_field_source_v1_5_0@1"
INPUT_KIND = "cells.betse_environment_field_inputs@1"
REVISION = current.SOURCE_REVISION
MAX_GRID_POINTS = 49
OPERATOR_RESIDUAL_LIMIT = 1e-10
NEAREST_SEPARATION_ULPS = 64


def plain(value):
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, np.generic):
        return value.item()
    if hasattr(value, "_asdict"):
        return {key: plain(item) for key, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [plain(item) for item in value]
    return value


def frozen(value, dtype=None):
    a = np.asarray(value, dtype=dtype)
    return np.frombuffer(a.tobytes(), dtype=a.dtype).reshape(a.shape)


def _scalar(value, name, *, positive=True):
    if (
        isinstance(value, (bool, np.bool_))
        or not isinstance(value, Real)
        or not math.isfinite(value)
        or positive
        and value <= 0
    ):
        raise ValueError("Require explicit finite source scalar: " + name)
    return float(value)


class Geometry(NamedTuple):
    shape: tuple
    delta_m: float
    X_m: object
    Y_m: object
    grid_points_m: object
    index_ij: object
    cell_to_grid: object
    membrane_to_grid: object
    membrane_area_per_site_m2: object
    membranes_per_site: object
    true_environment_volume_m3: object
    membrane_divergence_map_m2: object
    cell_to_environment_correction: object
    dirichlet_laplacian_per_m2: object
    dirichlet_inverse_m2: object
    neumann_laplacian_per_m2: object
    neumann_inverse_m2: object
    diagnostics: object


class Cache(NamedTuple):
    sigma_S_m: object
    ko_environment_per_m: object


class HodgeValues(NamedTuple):
    input_x: object
    input_y: object
    rotated_x: object
    rotated_y: object
    rotated_divergence: object
    AA: object
    solenoidal_x: object
    solenoidal_y: object
    divergence: object
    BB: object
    gradient_x: object
    gradient_y: object


class FieldValues(NamedTuple):
    raw_environment_current_x: object
    raw_environment_current_y: object
    local_voltage_assignment: object
    local_voltage_smoothed: object
    surface_charge_C_m2: object
    surface_voltage_V: object
    environment_charge_C_m3: object
    screened_voltage_source: object
    screen: object
    boundary_rhs: object
    boundary_potential_V: object
    environment_voltage_V: object
    electric_x_source: object
    electric_y_source: object
    normal_electric_source: object
    environment_current_x: object
    environment_current_y: object
    total_current_x_source: object
    total_current_y_source: object
    magnetic_field_source: object


@dataclass(frozen=True, slots=True)
class Binding:
    definition_json: str
    current_binding: current.CurrentBinding
    geometry: Geometry
    cache: Cache
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)


@dataclass(frozen=True, slots=True)
class Readout:
    binding_identity: str
    source_current: current.CurrentReadout
    packet: object
    values: FieldValues
    smoothing_hodge: HodgeValues | None
    current_hodge: HodgeValues
    diagnostics: object
    identity: str


class EnvironmentFieldRejected(NumericalError):
    def __init__(self, reason, *, stage, source, trial=None):
        super().__init__("Native environment field refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.trial = stage, source, trial


def _laplacian(shape, delta, *, flux):
    ny, nx = shape
    a = np.zeros((ny * nx, ny * nx))
    for i in range(ny):
        for j in range(nx):
            k = i * nx + j
            if not flux and (i in (0, ny - 1) or j in (0, nx - 1)):
                a[k, k] = 1
                continue
            neighbors = [
                (r, c)
                for r, c in ((i - 1, j), (i + 1, j), (i, j - 1), (i, j + 1))
                if 0 <= r < ny and 0 <= c < nx
            ]
            for r, c in neighbors:
                a[k, r * nx + c] = 1
            a[k, k] = -len(neighbors)
    return a / delta**2


def _nearest(points, requested, delta, label):
    tree = cKDTree(points)
    distance, index = tree.query(requested, k=2)
    scale = np.maximum(np.maximum(distance[:, 1], delta), np.finfo(np.float64).tiny)
    unique = (distance[:, 1] - distance[:, 0]) > (
        NEAREST_SEPARATION_ULPS * np.finfo(np.float64).eps * scale
    )
    if not np.all(unique):
        raise EnvironmentFieldRejected(
            "Ambiguous nearest grid point is outside this narrower component admission",
            stage="nearest_mapping",
            source=label,
            trial=MappingProxyType(
                dict(
                    grid_points=frozen(points),
                    query_points=frozen(requested),
                    delta_m=delta,
                    distances=frozen(distance),
                    indices=frozen(index),
                    native_single_nearest=frozen(tree.query(requested, k=1)[1]),
                    unique=frozen(unique),
                    native_tie_equivalence=False,
                )
            ),
        )
    return frozen(index[:, 0], np.int64)


def _geometry(raw, cb, parameters):
    world, supplied = raw["world"], raw["geometry"]
    if set(world) != {"xmin_m", "xmax_m", "ymin_m", "ymax_m", "grid_size"}:
        raise ValueError("Require explicit original Cartesian world bounds and source grid_size")
    if type(world["grid_size"]) is not int or not 2 <= world["grid_size"] <= 7:
        raise ValueError("Source environment grid_size is bounded to [2,7]")
    xmin, xmax, ymin, ymax = (
        _scalar(world[key], key, positive=False) for key in ("xmin_m", "xmax_m", "ymin_m", "ymax_m")
    )
    if xmax <= xmin or ymax <= ymin:
        raise ValueError("Require increasing finite source world bounds")
    delta = (xmax - xmin) / world["grid_size"]
    if not math.isfinite(delta) or delta <= 0 or not math.isfinite(delta**2) or delta**2 <= 0:
        raise ValueError("Source grid step or squared step is unrepresentable")
    nx, ny = int((xmax - xmin) / delta), int((ymax - ymin) / delta)
    if min(nx, ny) < 2 or nx * ny > MAX_GRID_POINTS:
        raise ValueError("Source-truncated environment grid exceeds the bounded 2D domain")
    xv, yv = np.linspace(xmin, xmax, nx + 1), np.linspace(ymin, ymax, ny + 1)
    vx, vy = np.meshgrid(xv, yv)
    x = (vx[:-1, :-1] + vx[:-1, 1:]) / 2
    y = (vy[:-1, :-1] + vy[1:, :-1]) / 2
    points = np.column_stack((x.ravel(), y.ravel()))
    if not np.isfinite(points).all() or len(np.unique(points, axis=0)) != nx * ny:
        raise ValueError("Native grid coordinates collapsed or became nonfinite")
    n, m = len(cb.cell_ids), len(cb.membrane_ids)
    if set(supplied) != {"cell_centres_m", "membrane_midpoints_m", "cell_volume_m3"}:
        raise ValueError("Declare original cell centres, membrane midpoints and cell volumes")
    centres = current._array(supplied["cell_centres_m"], (n, 2), "source cell centres")
    midpoints = current._array(
        supplied["membrane_midpoints_m"], (m, 2), "source membrane midpoints"
    )
    volume = current._array(supplied["cell_volume_m3"], (n,), "source cell volumes", positive=True)
    cell_map = _nearest(points, centres, delta, "cell_centres")
    membrane_map = _nearest(points, midpoints, delta, "membrane_midpoints")
    e = nx * ny
    area, counts = np.zeros(e), np.zeros(e)
    faces_by_site = [[] for _ in range(e)]
    divergence_map = np.zeros((e, m))
    for face, site in enumerate(membrane_map):
        faces_by_site[site].append(face)
        divergence_map[site, face] += cb.kernel.membrane_area_m2[face]
    for site, faces in enumerate(faces_by_site):
        if faces:
            area[site] = np.sum(cb.kernel.membrane_area_m2[faces])
            counts[site] = len(faces)
    ecm_volume = parameters["cell_height_m"] * delta**2
    true_volume = np.ones(e) * ecm_volume
    occupied = counts > 0
    true_volume[occupied] = area[occupied] * parameters["cell_space_m"] * (1 / 2)
    ecm_area = 4 * delta * parameters["cell_height_m"]
    with np.errstate(all="ignore"):
        correction = (volume / true_volume[cell_map]) * (ecm_area / cb.kernel.cell_area_m2)
    if (
        not np.isfinite(correction).all()
        or not np.isfinite(true_volume).all()
        or not np.all(true_volume > 0)
    ):
        raise EnvironmentFieldRejected(
            "Unrepresentable actual source geometry volume/correction",
            stage="geometry_volumes",
            source=raw,
            trial=dict(true_volume=frozen(true_volume), correction=frozen(correction)),
        )
    with np.errstate(all="ignore"):
        ad = _laplacian((ny, nx), delta, flux=False)
        an = _laplacian((ny, nx), delta, flux=True)
    if not np.isfinite(ad).all() or not np.isfinite(an).all():
        raise EnvironmentFieldRejected(
            "Nonfinite source Laplacian",
            stage="operators",
            source=raw,
            trial=dict(dirichlet=frozen(ad), neumann=frozen(an)),
        )
    invd, invn = np.linalg.pinv(ad), np.linalg.pinv(an)

    def norm(a):
        return float(np.linalg.norm(a, ord=np.inf))

    diagnostics = dict(
        dirichlet_inverse_residual=norm(ad @ invd - np.eye(e)),
        neumann_penrose_operator_residual=norm(an @ invn @ an - an) / norm(an),
        neumann_penrose_inverse_residual=norm(invn @ an @ invn - invn) / norm(invn),
        neumann_projection_symmetry=norm(an @ invn - (an @ invn).T),
        neumann_zero_mean_gauge=norm((invn @ np.ones(e))[:, None]) / norm(invn),
        HH_uses_dirichlet_inverse=True,
        nearest_ties_admitted=False,
        source_pinv_default_rcond=1e-15,
    )
    if any(
        not math.isfinite(diagnostics[key]) or diagnostics[key] > OPERATOR_RESIDUAL_LIMIT
        for key in diagnostics
        if key.endswith(("residual", "symmetry", "gauge"))
    ):
        raise EnvironmentFieldRejected(
            "Source pseudoinverse/gauge residual exceeds fixed limit",
            stage="operators",
            source=raw,
            trial=diagnostics,
        )
    return Geometry(
        (ny, nx),
        delta,
        frozen(x),
        frozen(y),
        frozen(points),
        frozen(np.asarray([(i, j) for i in range(ny) for j in range(nx)], dtype=np.int64)),
        cell_map,
        membrane_map,
        frozen(area),
        frozen(counts),
        frozen(true_volume),
        frozen(divergence_map),
        frozen(correction),
        frozen(ad),
        frozen(invd),
        frozen(an),
        frozen(invn),
        MappingProxyType(diagnostics),
    )


PARAMETERS = (
    "q_C",
    "kb_J_K",
    "NAv_per_mol",
    "relative_permittivity",
    "vacuum_permittivity_F_m",
    "configured_temperature_K",
    "cell_height_m",
    "cell_space_m",
    "cell_radius_m",
    "true_cell_size_m",
    "magnetic_permeability_H_m",
)


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=REVISION,
        definition=binding.definition,
        current_binding=current.binding_record(binding.current_binding),
        geometry=binding.geometry,
        cache=binding.cache,
        gauge_policy="native_value_rows_and_flux_Moore_Penrose_zero_mean@1",
        supplied_geometry="Original centres/midpoints/measures; no Voronoi seeding",
    )


def bind(raw):
    stage, trial = "source_declaration", None
    try:
        if (
            type(raw) is not dict
            or set(raw)
            != {
                "kind",
                "provenance",
                "is_ecm",
                "current_definition",
                "world",
                "geometry",
                "parameters",
                "cache_initial_state",
            }
            or raw["kind"] != INPUT_KIND
        ):
            raise ValueError("Require the complete separate environment-field declaration")
        if type(raw["provenance"]) is not str or not raw["provenance"].strip():
            raise ValueError("Require explicit source geometry/cache provenance")
        if type(raw["is_ecm"]) is not bool or set(raw["parameters"]) != set(PARAMETERS):
            raise ValueError("Declare native environment branch and every original cache parameter")
        parameters = {key: _scalar(raw["parameters"][key], key) for key in PARAMETERS}
        cb = current.bind(raw["current_definition"])
        stage = "geometry_preparation"
        geometry = _geometry(raw, cb, parameters)
        initial = raw["cache_initial_state"]
        if type(initial) is not dict or set(initial) != {
            "cell_mol_m3",
            "environment_mol_m3",
            "free_diffusion_m2_s",
        }:
            raise ValueError("Declare original configured-temperature initializer cache inputs")
        s, n, m = len(cb.ion_ids), len(cb.cell_ids), len(cb.membrane_ids)
        e = math.prod(geometry.shape) if raw["is_ecm"] else m
        ci = current._array(initial["cell_mol_m3"], (s, n), "initial cells", nonnegative=True)
        co = current._array(
            initial["environment_mol_m3"], (s, e), "initial environment", nonnegative=True
        )
        diffusion = current._array(
            initial["free_diffusion_m2_s"], (s,), "free diffusion", nonnegative=True
        )
        p, z = parameters, cb.kernel.valence
        stage = "initializer_cache"
        with np.errstate(all="ignore"):
            sigma = (
                np.asarray(
                    [
                        ((zz**2) * p["q_C"] * cb.kernel.F_C_mol * c * dd)
                        / (p["kb_J_K"] * p["configured_temperature_K"])
                        for zz, c, dd in zip(z, ci, diffusion, strict=True)
                    ]
                )
                .sum(axis=0)
                .mean()
            )
            ko = np.sqrt(
                np.dot(
                    (p["NAv_per_mol"] * p["q_C"] ** 2 * z**2)
                    / (
                        p["relative_permittivity"]
                        * p["vacuum_permittivity_F_m"]
                        * p["kb_J_K"]
                        * p["configured_temperature_K"]
                    ),
                    co,
                )
            ).mean()
        trial = Cache(frozen(sigma), frozen(ko))
        if not all(np.isfinite(value).all() for value in trial):
            raise ValueError("Nonfinite actual source initializer coefficient cache")
        declaration = json.dumps(plain(raw), sort_keys=True, separators=(",", ":"), allow_nan=False)
        binding = Binding(declaration, cb, geometry, trial, "")
        return replace(binding, identity=current._digest(binding_record(binding)))
    except EnvironmentFieldRejected:
        raise
    except Exception as error:
        raise EnvironmentFieldRejected(error, stage=stage, source=raw, trial=trial) from error


def validate_binding(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the original complete environment-field binding")
    expected = bind(binding.definition)
    if (
        binding.identity != expected.identity
        or current.record(binding_record(binding)) != current.record(binding_record(expected))
        or current._digest(binding_record(binding)) != expected.identity
    ):
        raise ValueError("Derived geometry/operators/gauge/cache differ from original inputs")
    return binding


def gradient(field, delta):
    x, y = np.zeros(field.shape), np.zeros(field.shape)
    x[:, 1:-1] = -(field[:, :-2] - field[:, 2:]) / (2 * delta)
    y[1:-1, :] = -(field[:-2, :] - field[2:, :]) / (2 * delta)
    x[:, 0], x[:, -1] = (field[:, 1] - field[:, 0]) / delta, (field[:, -1] - field[:, -2]) / delta
    y[0, :], y[-1, :] = (field[1, :] - field[0, :]) / delta, (field[-1, :] - field[-2, :]) / delta
    return x, y


def source_diff(field, delta, axis):
    result = np.zeros(field.shape)
    if axis == 0:
        result[:, 1:-1] = -(field[:, :-2] - field[:, 2:]) / (2 * delta)
        result[:, 0] = (field[:, 0] - field[:, 1]) / delta
        result[:, -1] = (field[:, -2] - field[:, -1]) / delta
    else:
        result[1:-1, :] = -(field[:-2, :] - field[2:, :]) / (2 * delta)
        result[0, :] = -(field[1, :] - field[0, :]) / delta
        result[-1, :] = -(field[-1, :] - field[-2, :]) / delta
    return result


def _hodge(x, y, geometry, boundary=None):
    delta, inverse = geometry.delta_m, geometry.dirichlet_inverse_m2
    xr, yr = -y.reshape(geometry.shape), x.reshape(geometry.shape)
    dr = source_diff(xr, delta, 0) + source_diff(yr, delta, 1)
    dr[:, 0] = dr[:, -1] = 0.0
    dr[0, :] = dr[-1, :] = 0.0
    aa = np.dot(inverse, -dr.ravel())
    ax, ay = gradient(aa.reshape(geometry.shape), delta)
    div = source_diff(x.reshape(geometry.shape) / 1.0, delta, 0) + source_diff(
        y.reshape(geometry.shape) / 1.0, delta, 1
    )
    b = dict.fromkeys(("L", "R", "B", "T"), 0.0) if boundary is None else boundary
    div[:, 0], div[:, -1] = -b["L"] * (1 / delta**2), -b["R"] * (1 / delta**2)
    div[0, :], div[-1, :] = -b["B"] * (1 / delta**2), -b["T"] * (1 / delta**2)
    bb = np.dot(inverse, div.ravel())
    gx, gy = gradient(bb.reshape(geometry.shape), delta)
    return HodgeValues(
        *(
            frozen(value)
            for value in (
                x,
                y,
                xr,
                yr,
                dr,
                aa,
                -ay,
                ax,
                div,
                bb,
                gx,
                gy,
            )
        )
    )


def _packet(binding, raw):
    mode = binding.definition["is_ecm"]
    keys = {"old_voltage_V", "boundary_V"} | (
        {
            "environment_mol_m3",
            "environment_flux_x",
            "environment_flux_y",
            "extra_environment_current_xy",
            "extra_environment_charge_C_m3",
        }
        if mode
        else {"environment_weight"}
    )
    if type(raw) is not dict or set(raw) != keys or set(raw["boundary_V"]) != {"R", "L", "T", "B"}:
        raise ValueError("Require the complete branch-specific environment source packet")
    result = dict(
        old_voltage_V=current._array(
            raw["old_voltage_V"], (len(binding.current_binding.membrane_ids),), "old vm"
        ),
        boundary_V=MappingProxyType(
            {
                key: _scalar(raw["boundary_V"][key], key, positive=False)
                for key in ("R", "L", "T", "B")
            }
        ),
    )
    e, s = math.prod(binding.geometry.shape), len(binding.current_binding.ion_ids)
    if mode:
        for key, shape in (
            ("environment_mol_m3", (s, e)),
            ("environment_flux_x", (s, e)),
            ("environment_flux_y", (s, e)),
            ("extra_environment_current_xy", (e, 2)),
            ("extra_environment_charge_C_m3", (e,)),
        ):
            result[key] = current._array(raw[key], shape, key)
    else:
        result["environment_weight"] = current._array(
            raw["environment_weight"],
            binding.geometry.shape,
            "source B08 environment weight",
            nonnegative=True,
        )
    return MappingProxyType(result)


def readout_record(readout):
    return dict(
        law=LAW_ID,
        binding_identity=readout.binding_identity,
        source_current=readout_current_record(readout.source_current),
        packet=readout.packet,
        values=readout.values,
        smoothing_hodge=readout.smoothing_hodge,
        current_hodge=readout.current_hodge,
        diagnostics=readout.diagnostics,
    )


def evaluate(binding, source_current, raw):
    stage, trial = "source_association", None
    try:
        validate_binding(binding)
        if (
            type(source_current) is not current.CurrentReadout
            or source_current.binding_identity != binding.current_binding.identity
        ):
            raise ValueError("Environment source current differs from its original binding")
        fresh = current.evaluate(binding.current_binding, source_current.source)
        if current._digest(readout_current_record(fresh)) != current._digest(
            readout_current_record(source_current)
        ):
            raise ValueError("Resealed current buffers differ from the actual source prefix")
        packet = _packet(binding, raw)
        geometry, cache, definition = binding.geometry, binding.cache, binding.definition
        p, k = definition["parameters"], binding.current_binding.kernel
        delta, mapping = geometry.delta_m, geometry.membrane_to_grid
        stage = "environment_field_trial"
        with np.errstate(all="ignore"):
            rhs = np.zeros(geometry.shape)
            rhs[:, -1] = -packet["boundary_V"]["R"] / delta**2
            rhs[:, 0] = -packet["boundary_V"]["L"] / delta**2
            rhs[-1, :] = -packet["boundary_V"]["T"] / delta**2
            rhs[0, :] = -packet["boundary_V"]["B"] / delta**2
            phi_b = np.dot(geometry.dirichlet_inverse_m2, -rhs.ravel())
            smoothing, local, local_smoothed, surface, surface_voltage, charge, screen, screened = (
                None,
                None,
                None,
                None,
                None,
                None,
                None,
                None,
            )
            if definition["is_ecm"]:
                jx = (
                    np.dot(k.F_C_mol * k.valence, packet["environment_flux_x"])
                    + packet["extra_environment_current_xy"][:, 0]
                ).reshape(geometry.shape)
                jy = (
                    np.dot(k.F_C_mol * k.valence, packet["environment_flux_y"])
                    + packet["extra_environment_current_xy"][:, 1]
                ).reshape(geometry.shape)
                hodge = _hodge(jx, jy, geometry, packet["boundary_V"])
                charge = (
                    np.dot(k.valence * k.F_C_mol, packet["environment_mol_m3"])
                    + packet["extra_environment_charge_C_m3"]
                )
                surface = np.zeros(math.prod(geometry.shape))
                surface[mapping] = (
                    charge[mapping]
                    * (p["cell_height_m"] * delta**2)
                    / (geometry.membrane_area_per_site_m2[mapping].mean())
                )
                surface_voltage = surface / (
                    cache.ko_environment_per_m
                    * p["vacuum_permittivity_F_m"]
                    * p["relative_permittivity"]
                )
                screen = (2 / (cache.ko_environment_per_m * delta)) * (
                    p["cell_radius_m"] / p["true_cell_size_m"]
                )
                voltage = (
                    gaussian_filter(
                        surface_voltage.reshape(geometry.shape), 1, mode="constant", cval=0.0
                    ).ravel()
                    + phi_b
                )
                screened = screen * voltage.reshape(geometry.shape)
                gx, gy = gradient(screened, delta)
            else:
                vc = packet["old_voltage_V"] / 2
                local = np.zeros(math.prod(geometry.shape))
                local[mapping] = vc[k.owner]
                local_smoothed = gaussian_filter(-local.reshape(geometry.shape), 1)
                gx, gy = gradient(delta * local_smoothed.reshape(geometry.shape), delta)
                smoothing = _hodge(gx, gy, geometry)
                gx = smoothing.solenoidal_x + smoothing.gradient_x
                gy = smoothing.solenoidal_y + smoothing.gradient_y
                jx = cache.sigma_S_m * -gx * packet["environment_weight"]
                jy = cache.sigma_S_m * -gy * packet["environment_weight"]
                hodge = _hodge(jx, jy, geometry)
                voltage = local_smoothed.ravel()
            ex, ey = -gx, -gy
            normal = (
                ex.ravel()[mapping] * k.normal_xy[:, 0] + ey.ravel()[mapping] * k.normal_xy[:, 1]
            )
            values = FieldValues(
                *(
                    None if value is None else frozen(value)
                    for value in (
                        jx,
                        jy,
                        local,
                        local_smoothed,
                        surface,
                        surface_voltage,
                        charge,
                        screened,
                        screen,
                        rhs,
                        phi_b,
                        voltage,
                        ex,
                        ey,
                        normal,
                        hodge.solenoidal_x,
                        hodge.solenoidal_y,
                        hodge.solenoidal_x + hodge.gradient_x,
                        hodge.solenoidal_y + hodge.gradient_y,
                        hodge.AA * p["magnetic_permeability_H_m"],
                    )
                )
            )
        finite = all(np.isfinite(value).all() for value in values if value is not None)
        finite &= all(np.isfinite(value).all() for value in hodge)
        if smoothing is not None:
            finite &= all(np.isfinite(value).all() for value in smoothing)
        diagnostics = MappingProxyType(
            dict(
                finite=bool(finite),
                current_prefix_revalidated=True,
                geometry_and_inverse_derived=True,
                HH_uses_dirichlet_inverse=True,
                neumann_pseudoinverse_prepared_but_unused=True,
                boundary_assignment_order=("R", "L", "T", "B"),
                HH_boundary_order=("L", "R", "B", "T"),
                gaussian_mode="constant" if definition["is_ecm"] else "reflect",
                gaussian_sigma=1.0,
                source_diff_boundary_sign_retained=True,
                no_ecm_vm_uses_owner_index_into_membrane_buffer=not definition["is_ecm"],
                physical_projection_or_energy_parity=False,
                source_inputs_advanced=False,
            )
        )
        trial = Readout(
            binding.identity, source_current, packet, values, smoothing, hodge, diagnostics, ""
        )
        trial = replace(trial, identity=current._digest(readout_record(trial)))
        if not finite:
            raise ValueError("Nonfinite actual native environment field buffers")
        return trial
    except Exception as error:
        raise EnvironmentFieldRejected(
            error, stage=stage, source=(source_current, raw), trial=trial
        ) from error


def readout_current_record(readout):
    return dict(
        binding_identity=readout.binding_identity,
        source_identity=readout.source_identity,
        source=readout.source,
        values=readout.values,
        diagnostics=readout.diagnostics,
        identity=readout.identity,
    )


def voltage_dependencies(binding):
    """Explicit derived data for a later B25 adapter; no voltage call is performed."""
    validate_binding(binding)
    g = binding.geometry
    return dict(
        shape=g.shape,
        delta_m=g.delta_m,
        membrane_to_grid=g.membrane_to_grid,
        inverse_m2=g.dirichlet_inverse_m2,
        operator_provenance=json.dumps(
            dict(
                binding_identity=binding.identity,
                law=LAW_ID,
                gauge="source all-value rows; no additional gauge pin",
            ),
            sort_keys=True,
        ),
    )
