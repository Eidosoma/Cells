"""Bounded native normal ECM material chronology with explicit external seams.

Old field/flow, channel multiplier and accumulated pump flux are supplied inputs.
Source boundary reset, collocated transport, duplicate-last fast exchange, stale
membrane buffers and clipping remain literal, with separate amount ledgers.
"""

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_environment_field as geometry_source
from cells.processes import betse_normal_current as current

LAW_ID = "betse_ecm_transport_material_source_v1_5_0@1"
INPUT_KIND = "cells.betse_ecm_transport_inputs@1"
NONCE = 1e-25
MAX_STEPS = 3


def freeze(value):
    if isinstance(value, np.ndarray):
        return geometry_source.frozen(value)
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


def plain(value):
    return geometry_source.plain(value)


class Kernel(NamedTuple):
    partner: object
    boundary: object
    gap_length_m: object
    gap_weights: object
    moving: tuple
    membrane_diffusion_m2_s: object
    gap_diffusion_m2_s: object
    environment_diffusion_m2_s: object
    tight_junction_modulator: object
    R_J_mol_K: float
    membrane_thickness_m: float
    gap_surface_fraction: float
    cluster_open: bool
    fast_update_ecm: bool
    sharpness: float
    fluid_flow: bool


@dataclass(frozen=True, slots=True)
class Binding:
    definition_json: str
    geometry_binding: geometry_source.Binding
    kernel: Kernel
    identity: str

    @property
    def definition(self):
        return json.loads(self.definition_json)


class Values(NamedTuple):
    cell_mol_m3: object
    membrane_mol_m3: object
    environment_mol_m3: object
    voltage_V: object
    membrane_flux_mol_m2_s: object
    junction_flux_mol_m2_s: object
    environment_flux_x_mol_m2_s: object
    environment_flux_y_mol_m2_s: object
    junction_voltage_V: object
    junction_field_source: object
    junction_field_xy_source: object
    gap_open: object


@dataclass(frozen=True, slots=True)
class State:
    binding_identity: str
    step_index: int
    values: Values
    identity: str


class Drive(NamedTuple):
    dt_s: float
    runtime_temperature_K: float
    junction_block: object
    channel_multiplier: object
    supplied_pump_membrane_flux_mol_m2_s: object
    supplied_late_membrane_flux_mol_m2_s: object
    electric_x_source: object
    electric_y_source: object
    velocity_x_m_s: object
    velocity_y_m_s: object
    boundary_mol_m3: object


class Frame(NamedTuple):
    stage: str
    ion_id: object
    values: Values


class ECMRecord(NamedTuple):
    ion_id: str
    before_mol_m3: object
    clamped_mol_m3: object
    gradient_x: object
    gradient_y: object
    effective_diffusion_m2_s: object
    alpha: object
    flux_x_mol_m2_s: object
    flux_y_mol_m2_s: object
    divergence_mol_m3_s: object
    euler_mol_m3: object
    smoothed_mol_m3: object


@dataclass(frozen=True, slots=True)
class Trial:
    binding_identity: str
    parent_identity: str
    drive: Drive
    frames: tuple
    environment_records: tuple
    candidate: State
    diagnostics: object
    identity: str


class ECMTransportRejected(NumericalError):
    def __init__(self, reason, *, stage, parent=None, drive=None, trial=None):
        super().__init__("Native ECM material refused at " + stage + ": " + str(reason))
        self.stage, self.parent, self.drive, self.trial = stage, parent, drive, trial


def binding_record(binding):
    return dict(
        law=LAW_ID,
        definition=binding.definition,
        geometry_binding=geometry_source.binding_record(binding.geometry_binding),
        geometry_identity=binding.geometry_binding.identity,
        kernel=binding.kernel,
    )


def state_record(value):
    return dict(
        binding_identity=value.binding_identity, step_index=value.step_index, values=value.values
    )


def trial_record(value):
    return dict(
        binding_identity=value.binding_identity,
        parent_identity=value.parent_identity,
        drive=value.drive,
        frames=value.frames,
        environment_records=value.environment_records,
        candidate=state_record(value.candidate),
        diagnostics=value.diagnostics,
    )


def bind(raw):
    if (
        type(raw) is not dict
        or set(raw)
        != {
            "kind",
            "provenance",
            "environment_geometry_definition",
            "junction_geometry",
            "ions",
            "parameters",
        }
        or raw["kind"] != INPUT_KIND
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError("Require the separate complete ECM material declaration")
    gb = geometry_source.bind(raw["environment_geometry_definition"])
    if gb.definition["is_ecm"] is not True:
        raise ValueError("Require the native ECM branch")
    cb, g = gb.current_binding, gb.geometry
    s, m = len(cb.ion_ids), len(cb.membrane_ids)
    j, ions, p = raw["junction_geometry"], raw["ions"], raw["parameters"]
    if (
        set(j) != {"partner", "boundary", "gap_length_m", "gap_weights"}
        or set(ions)
        != {
            "moving_ids",
            "membrane_diffusion_m2_s",
            "gap_diffusion_m2_s",
            "environment_diffusion_m2_s",
            "tight_junction_modulator",
        }
        or set(p)
        != {
            "R_J_mol_K",
            "membrane_thickness_m",
            "gap_surface_fraction",
            "cluster_open",
            "fast_update_ecm",
            "sharpness",
            "fluid_flow",
            "v_sensitive_gj",
        }
    ):
        raise ValueError(
            "Declare all original fixed junction, species transport and source controls"
        )
    if p["v_sensitive_gj"] is not False or any(
        type(p[key]) is not bool for key in ("cluster_open", "fast_update_ecm", "fluid_flow")
    ):
        raise ValueError(
            "This component requires explicit fixed-gap and scalar source branch guards"
        )
    partner, boundary = np.asarray(j["partner"]), np.asarray(j["boundary"])
    if (
        partner.shape != (m,)
        or partner.dtype.kind not in "iu"
        or np.any(partner < 0)
        or np.any(partner >= m)
    ):
        raise ValueError("Declare original membrane partner indices")
    if boundary.shape != (m,) or boundary.dtype != np.bool_:
        raise ValueError("Declare the original boolean outer membrane mask")
    moving = ions["moving_ids"]
    if (
        not isinstance(moving, (tuple, list))
        or len(set(moving)) != len(moving)
        or any(name not in cb.ion_ids for name in moving)
    ):
        raise ValueError("Require the unique ordered native moving-ion subset")
    constants = {
        key: geometry_source._scalar(p[key], key) for key in ("R_J_mol_K", "membrane_thickness_m")
    }
    fraction = geometry_source._scalar(
        p["gap_surface_fraction"], "gap_surface_fraction", positive=False
    )
    sharpness = geometry_source._scalar(p["sharpness"], "sharpness", positive=False)
    if fraction < 0 or not 0 <= sharpness <= 1:
        raise ValueError("Require nonnegative gap fraction and bounded source smoothing")
    e = math.prod(g.shape)
    kernel = Kernel(
        geometry_source.frozen(partner, np.int64),
        geometry_source.frozen(boundary),
        current._array(j["gap_length_m"], (m,), "source gap lengths", positive=True),
        current._array(j["gap_weights"], (m,), "fixed gap weights", nonnegative=True),
        tuple(cb.ion_ids.index(name) for name in moving),
        current._array(
            ions["membrane_diffusion_m2_s"], (s, m), "membrane diffusion", nonnegative=True
        ),
        current._array(ions["gap_diffusion_m2_s"], (s, m), "gap diffusion", nonnegative=True),
        current._array(
            ions["environment_diffusion_m2_s"], (s, e), "environment diffusion", nonnegative=True
        ),
        current._array(
            ions["tight_junction_modulator"], (s, e), "source TJ modulator", nonnegative=True
        ),
        constants["R_J_mol_K"],
        constants["membrane_thickness_m"],
        fraction,
        p["cluster_open"],
        p["fast_update_ecm"],
        sharpness,
        p["fluid_flow"],
    )
    definition = json.dumps(plain(raw), sort_keys=True, separators=(",", ":"), allow_nan=False)
    binding = Binding(definition, gb, kernel, "")
    return replace(binding, identity=current._digest(binding_record(binding)))


def validate_binding(binding):
    if type(binding) is not Binding:
        raise ValueError("Require the original ECM transport binding")
    expected = bind(binding.definition)
    if binding.identity != expected.identity or current.record(
        binding_record(binding)
    ) != current.record(binding_record(expected)):
        raise ValueError("Resealed ECM geometry, source constants or transport operators changed")
    return binding


def _shapes(binding):
    cb = binding.geometry_binding.current_binding
    s, n, m, e = (
        len(cb.ion_ids),
        len(cb.cell_ids),
        len(cb.membrane_ids),
        math.prod(binding.geometry_binding.geometry.shape),
    )
    return ((s, n), (s, m), (s, e), (m,), (s, m), (s, m), (s, e), (s, e), (m,), (m,), (m, 2), (m,))


def state(binding, raw, *, step_index=0):
    if (
        set(raw) != set(Values._fields)
        or type(step_index) is not int
        or not 0 <= step_index <= MAX_STEPS
    ):
        raise ValueError("Declare every source state buffer and bounded step index [0,3]")
    values = Values(
        *(
            current._array(raw[key], shape, key)
            for key, shape in zip(Values._fields, _shapes(binding), strict=True)
        )
    )
    value = State(binding.identity, step_index, values, "")
    return replace(value, identity=current._digest(state_record(value)))


def drive(binding, raw):
    if type(raw) is not dict or set(raw) != set(Drive._fields):
        raise ValueError(
            "Declare all held pump/channel/field/flow/bath seams and source dt/temperature"
        )
    cb, g = binding.geometry_binding.current_binding, binding.geometry_binding.geometry
    s, m = len(cb.ion_ids), len(cb.membrane_ids)
    values = [geometry_source._scalar(raw[key], key) for key in ("dt_s", "runtime_temperature_K")]
    shapes = ((m,), (m,), (s, m), (s, m), g.shape, g.shape, g.shape, g.shape, (s,))
    values.extend(
        current._array(raw[key], shape, key)
        for key, shape in zip(Drive._fields[2:], shapes, strict=True)
    )
    result = Drive(*values)
    if not binding.kernel.cluster_open and any(
        np.any(value[:, binding.kernel.boundary] != 0)
        for value in (
            result.supplied_pump_membrane_flux_mol_m2_s,
            result.supplied_late_membrane_flux_mol_m2_s,
        )
    ):
        raise ValueError(
            "Closed-cluster external flux seams must already carry the native boundary mask"
        )
    return result


def _electroflux(ca, cb, diffusion, distance, valence, voltage, temperature, F, R, rho):
    voltage += NONCE
    valence += NONCE
    alpha = (valence * voltage * F) / (R * temperature)
    return (
        -((diffusion * alpha) / distance) * ((cb - ca * np.exp(-alpha)) / -np.expm1(-alpha)) * rho
    )


def _smooth(a, sharpness):
    out = np.zeros(a.shape)
    sides = (1 - sharpness) / 4
    out[:, :] = sharpness * a
    out[:-1, :] += sides * a[1:, :]
    out[1:, :] += sides * a[:-1, :]
    out[:, :-1] += sides * a[:, 1:]
    out[:, 1:] += sides * a[:, :-1]
    out[:, 0], out[:, -1] = a[:, 0], a[:, -1]
    out[0, :], out[-1, :] = a[0, :], a[-1, :]
    return out


@np.errstate(all="ignore")
def step(binding, parent, forcing):
    trial = None
    try:
        validate_binding(binding)
        if (
            type(parent) is not State
            or parent.binding_identity != binding.identity
            or parent.step_index >= MAX_STEPS
        ):
            raise ValueError(
                "Require the bound original parent within the qualified three-call cap"
            )
        checked = state(binding, parent.values._asdict(), step_index=parent.step_index)
        if (
            checked.identity != parent.identity
            or current.record(checked.values) != current.record(parent.values)
            or any(v.flags.writeable for v in parent.values)
        ):
            raise ValueError("Changed source state or mutable/non-float64 buffers")
        if (
            type(forcing) is not Drive
            or current.record(drive(binding, forcing._asdict())) != current.record(forcing)
            or any(isinstance(v, np.ndarray) and v.flags.writeable for v in forcing)
        ):
            raise ValueError("Require complete immutable typed ECM source drive")
        gb, k = binding.geometry_binding, binding.kernel
        cb, g = gb.current_binding, gb.geometry
        ck, p = cb.kernel, gb.definition["parameters"]
        s, m = len(cb.ion_ids), len(cb.membrane_ids)
        a = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, env, vm, fm, fg, fx_all, fy_all, vgj, egj, exy, opening = a.values()
        frames, environment_records = [], []
        delta, volume = g.delta_m, p["cell_height_m"] * g.delta_m**2
        cell_volume = np.asarray(gb.definition["geometry"]["cell_volume_m3"])
        clip = np.zeros(s)
        clamp, collocated, smoothing = np.zeros(s), np.zeros(s), np.zeros(s)
        environment_exchange = np.zeros(s)
        requested_gap_outward_increment = np.zeros_like(cell)

        def observe(stage, i=None):
            frames.append(
                Frame(
                    stage,
                    None if i is None else cb.ion_ids[i],
                    Values(
                        *(
                            freeze(value)
                            for value in (
                                cell,
                                membrane,
                                env,
                                vm,
                                fm,
                                fg,
                                fx_all,
                                fy_all,
                                vgj,
                                egj,
                                exy,
                                opening,
                            )
                        )
                    ),
                )
            )

        observe("initial")
        fm.fill(0)
        fg.fill(0)
        fx_all, fy_all = np.zeros((s, math.prod(g.shape))), np.zeros((s, math.prod(g.shape)))
        observe("reset_flux")
        fm += forcing.supplied_pump_membrane_flux_mol_m2_s
        observe("supplied_pump_flux")
        failure = None
        with np.errstate(all="ignore"):
            for i in k.moving:
                ones = np.ones(m)
                leak = _electroflux(
                    env[i][g.membrane_to_grid],
                    membrane[i],
                    k.membrane_diffusion_m2_s[i],
                    ones * k.membrane_thickness_m,
                    ck.valence[i] * ones,
                    vm,
                    forcing.runtime_temperature_K,
                    ck.F_C_mol,
                    k.R_J_mol_K,
                    forcing.channel_multiplier,
                )
                if not k.cluster_open:
                    leak[k.boundary] = 0
                fm[i] += leak
                observe("membrane_flux", i)
                vgj = vm[k.partner] - vm[np.arange(m)]
                egj = -vgj / k.gap_length_m
                exy = np.column_stack((egj * ck.normal_xy[:, 0], egj * ck.normal_xy[:, 1]))
                opening = forcing.junction_block * np.ones(m) * k.gap_weights
                gap = _electroflux(
                    membrane[i][np.arange(m)],
                    membrane[i][k.partner],
                    k.gap_diffusion_m2_s[i] * k.gap_surface_fraction * opening,
                    k.gap_length_m * np.ones(m),
                    ck.valence[i] * np.ones(m),
                    vgj,
                    p["configured_temperature_K"],
                    ck.F_C_mol,
                    k.R_J_mol_K,
                    1,
                )
                gap[k.boundary] = 0
                fg[i] = fg[i] + gap
                observe("junction_flux", i)
                before = env[i].copy()
                image = env[i].reshape(g.shape)
                image[:, 0] = forcing.boundary_mol_m3[i]
                image[:, -1] = forcing.boundary_mol_m3[i]
                image[0, :] = forcing.boundary_mol_m3[i]
                image[-1, :] = forcing.boundary_mol_m3[i]
                clamped = image.copy()
                observe("ecm_clamp", i)
                gx, gy = geometry_source.gradient(image, delta)
                ux = forcing.velocity_x_m_s if k.fluid_flow else np.zeros(g.shape)
                uy = forcing.velocity_y_m_s if k.fluid_flow else np.zeros(g.shape)
                diffusion = k.environment_diffusion_m2_s[i].reshape(
                    g.shape
                ) * k.tight_junction_modulator[i].reshape(g.shape)
                alpha = (diffusion * ck.valence[i] * p["q_C"]) / (
                    p["kb_J_K"] * forcing.runtime_temperature_K
                )
                fx = (
                    -diffusion * gx
                    - alpha * -forcing.electric_x_source * image
                    + ux * image
                    - 0.0 * image * -forcing.electric_x_source
                )
                fy = (
                    -diffusion * gy
                    - alpha * -forcing.electric_y_source * image
                    + uy * image
                    - 0.0 * image * -forcing.electric_y_source
                )
                fx_all[i], fy_all[i] = fx.ravel(), fy.ravel()
                div = geometry_source.source_diff(-fx, delta, 0) + geometry_source.source_diff(
                    -fy, delta, 1
                )
                euler = image + div * forcing.dt_s
                result = _smooth(euler, k.sharpness) if k.sharpness < 1 else euler
                environment_records.append(
                    ECMRecord(
                        cb.ion_ids[i],
                        *(
                            freeze(value)
                            for value in (
                                before,
                                clamped,
                                gx,
                                gy,
                                diffusion,
                                alpha,
                                fx,
                                fy,
                                div,
                                euler,
                                result,
                            )
                        ),
                    )
                )
                clamp[i] = np.sum((clamped.ravel() - before) * volume)
                collocated[i] = np.sum((euler - clamped) * volume)
                smoothing[i] = np.sum((result - euler) * volume)
                env[i] = result.ravel()
                observe("ecm_commit", i)
                membrane[i] = cell[i][ck.owner] * 1
                observe("refresh_at_mem", i)
            fm += forcing.supplied_late_membrane_flux_mol_m2_s
            observe("supplied_late_flux")
            for i in k.moving:
                dc = np.dot(ck.owner_sum, fm[i] * ck.membrane_area_m2) / cell_volume
                cell[i] = cell[i] + dc * forcing.dt_s
                membrane[i] = cell[i][ck.owner]
                if k.fast_update_ecm:
                    last_flux = np.zeros(math.prod(g.shape))
                    last_flux[g.membrane_to_grid] = -fm[i]
                    de = (last_flux * g.membrane_area_per_site_m2) / volume
                else:
                    de = np.dot(g.membrane_divergence_map_m2, -fm[i]) / (
                        p["cell_height_m"] * delta**2
                    )
                env[i] = env[i] + de * forcing.dt_s
                environment_exchange[i] = np.sum(de * forcing.dt_s * volume)
                observe("membrane_commit", i)
                dg = np.dot(ck.owner_sum, -fg[i] * ck.membrane_area_m2) / cell_volume
                requested_gap_outward_increment[i] = -(forcing.dt_s * dg)
                cell[i] += forcing.dt_s * dg
                observe("junction_commit", i)
                negative, nan = cell[i] < 0, np.isnan(cell[i])
                clip[i] = np.sum(np.where(negative, -cell[i], 0) * cell_volume)
                cell[i][negative] = 0
                if np.any(nan):
                    observe("clip_bulk_failure", i)
                    failure = "Native no_negs sees NaN after negative-value clipping"
                    break
                observe("clip_bulk", i)
        candidate = State(binding.identity, parent.step_index + 1, frames[-1].values, "")
        candidate = replace(candidate, identity=current._digest(state_record(candidate)))
        membrane_transfer = forcing.dt_s * np.sum(fm * ck.membrane_area_m2, axis=1)
        gap_transfer = forcing.dt_s * np.sum(fg * ck.membrane_area_m2, axis=1)
        cell_change = np.sum((cell - parent.values.cell_mol_m3) * cell_volume, axis=1)
        env_change = np.sum((env - parent.values.environment_mol_m3) * volume, axis=1)
        committed = np.zeros(s, dtype=bool)
        for frame in frames:
            if frame.stage in ("clip_bulk", "clip_bulk_failure"):
                committed[cb.ion_ids.index(frame.ion_id)] = True
        expected_cell = np.where(committed, membrane_transfer - gap_transfer + clip, 0)
        diagnostics = freeze(
            dict(
                finite=bool(
                    all(np.isfinite(v).all() for frame in frames for v in frame.values)
                    and all(np.isfinite(v).all() for row in environment_records for v in row[1:])
                ),
                boundary_clamp_change_mol=clamp,
                collocated_transport_change_mol=collocated,
                smoothing_change_mol=smoothing,
                membrane_transfer_mol=membrane_transfer,
                native_environment_exchange_mol=environment_exchange,
                conservative_environment_exchange_mol=-np.where(committed, membrane_transfer, 0),
                fast_exchange_defect_mol=environment_exchange
                + np.where(committed, membrane_transfer, 0),
                gap_net_outward_mol=gap_transfer,
                clipping_added_mol=clip,
                cell_change_mol=cell_change,
                environment_change_mol=env_change,
                cell_accounting_residual_mol=cell_change - expected_cell,
                environment_accounting_residual_mol=env_change
                - (clamp + collocated + smoothing + environment_exchange),
                membrane_bulk_difference_mol_m3=membrane - cell[:, ck.owner],
                junction_requested_outward_increment_mol_m3=requested_gap_outward_increment,
                source_voltage_nonce_delta_V=vm - parent.values.voltage_V,
                negative_environment_retained=bool(np.any(env < 0)),
                negative_membrane_retained=bool(np.any(membrane < 0)),
                committed_moving_ions=committed,
                geometry_derived=True,
                pump_gate_field_seams_supplied=True,
                field_or_voltage_feedback=False,
                physical_material_or_energy_parity=False,
            )
        )
        diagnostics = freeze(
            dict(diagnostics)
            | dict(
                finite=diagnostics["finite"]
                and all(
                    np.isfinite(value).all()
                    for value in diagnostics.values()
                    if isinstance(value, np.ndarray)
                )
            )
        )
        trial = Trial(
            binding.identity,
            parent.identity,
            forcing,
            tuple(frames),
            tuple(environment_records),
            candidate,
            diagnostics,
            "",
        )
        trial = replace(trial, identity=current._digest(trial_record(trial)))
        if failure or not diagnostics["finite"]:
            raise ValueError(failure or "Nonfinite literal native ECM material trial")
        return trial
    except Exception as error:
        raise ECMTransportRejected(
            error,
            stage="material_trial" if trial is not None else "source",
            parent=parent,
            drive=forcing,
            trial=trial,
        ) from error
