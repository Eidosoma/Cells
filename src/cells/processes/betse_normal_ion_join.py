"""Literal no-ECM normal ion/material join, with complete intermediate states.

Pumps, events, networks, ECM and voltage feedback are outside this law. The
source electroflux nonce still mutates the supplied voltage copy per ion.
Legacy bulk clipping, stale membrane buffers and mixed bath are retained.
"""

import math
from collections.abc import Mapping
from dataclasses import dataclass, fields, is_dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes.betse_normal_current import _array, _digest, _ids, record

LAW_ID = "betse_normal_no_ecm_ion_join_v1_5_0@1"
SOURCE_REVISION = "5269a714aa2593ed2a6708c4516289977d8ae1a2"
INPUT_KIND = "cells.betse_normal_ion_join_inputs@1"
NONCE = 1e-25


def data(value):
    if is_dataclass(value):
        return {f.name: data(getattr(value, f.name)) for f in fields(value)}
    if hasattr(value, "_asdict"):
        return {key: data(item) for key, item in value._asdict().items()}
    if isinstance(value, Mapping):
        return {key: data(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [data(item) for item in value]
    return value


def digest(value):
    return _digest(data(value))


def freeze(value):
    if isinstance(value, np.ndarray):
        return np.frombuffer(value.tobytes(), dtype=value.dtype).reshape(value.shape)
    if isinstance(value, Mapping):
        return MappingProxyType({key: freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(freeze(item) for item in value)
    return value


class Kernel(NamedTuple):
    owner: object
    partner: object
    boundary: object
    owner_sum: object
    area_m2: object
    cell_volume_m3: object
    gap_length_m: object
    normal_xy: object
    gap_weights: object
    valence: object
    moving: tuple
    membrane_diffusion_m2_s: object
    gap_diffusion_m2_s: object
    F_C_mol: float
    R_J_mol_K: float
    configured_temperature_K: float
    membrane_thickness_m: float
    junction_surface_fraction: float
    bath_volume_m3: float
    cluster_open: bool


@dataclass(frozen=True, slots=True)
class Binding:
    definition: object
    cell_ids: tuple
    membrane_ids: tuple
    ion_ids: tuple
    kernel: Kernel
    identity: str


class Values(NamedTuple):
    cell_mol_m3: object
    membrane_mol_m3: object
    bath_mol_m3: object
    voltage_V: object
    membrane_flux_mol_m2_s: object
    junction_flux_mol_m2_s: object
    junction_voltage_V: object
    junction_field_V_m: object
    junction_field_xy_V_m: object
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


class Frame(NamedTuple):
    stage: str
    ion_id: object
    values: Values


@dataclass(frozen=True, slots=True)
class Trial:
    parent: State
    drive: Drive
    frames: tuple
    candidate: State
    diagnostics: object
    identity: str


class IonJoinRejected(NumericalError):
    def __init__(self, reason, *, stage, parent, drive, trial=None):
        super().__init__("Native normal ion join refused at " + stage + ": " + str(reason))
        self.stage, self.parent, self.drive, self.trial = stage, parent, drive, trial


def binding_record(binding):
    return dict(
        law=LAW_ID,
        native_revision=SOURCE_REVISION,
        definition=binding.definition,
        cell_ids=binding.cell_ids,
        membrane_ids=binding.membrane_ids,
        ion_ids=binding.ion_ids,
        kernel=binding.kernel,
    )


def bind(raw):
    if (
        type(raw) is not dict
        or set(raw) != {"kind", "provenance", "geometry", "ions", "parameters"}
        or raw["kind"] != INPUT_KIND
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError("Require complete separate no-ECM join definition/provenance")
    g, ions, p = raw["geometry"], raw["ions"], raw["parameters"]
    if (
        set(g)
        != {
            "cell_ids",
            "membrane_ids",
            "owner",
            "partner",
            "boundary",
            "membrane_area_m2",
            "cell_volume_m3",
            "gap_length_m",
            "normal_xy",
            "gap_weights",
        }
        or set(ions)
        != {"ids", "valence", "moving_ids", "membrane_diffusion_m2_s", "gap_diffusion_m2_s"}
        or set(p)
        != {
            "F_C_mol",
            "R_J_mol_K",
            "configured_temperature_K",
            "membrane_thickness_m",
            "junction_surface_fraction",
            "bath_volume_m3",
            "cluster_open",
            "is_ecm",
            "v_sensitive_gj",
        }
        or p["is_ecm"] is not False
        or p["v_sensitive_gj"] is not False
        or type(p["cluster_open"]) is not bool
    ):
        raise ValueError("Require explicit no-ECM/fixed-gap scope and complete axes/parameters")
    cells, membranes, names = (
        _ids(g["cell_ids"], 256),
        _ids(g["membrane_ids"], 1536),
        _ids(ions["ids"], 32),
    )
    n, m, count = len(cells), len(membranes), len(names)
    owner, partner = np.asarray(g["owner"]), np.asarray(g["partner"])
    if (
        owner.shape != (m,)
        or owner.dtype.kind not in "iu"
        or np.any(owner < 0)
        or np.any(owner >= n)
        or set(owner.tolist()) != set(range(n))
        or partner.shape != (m,)
        or partner.dtype.kind not in "iu"
        or np.any(partner < 0)
        or np.any(partner >= m)
    ):
        raise ValueError("Incomplete original owner/partner axes")
    owner, partner = freeze(owner.astype(np.int64)), freeze(partner.astype(np.int64))
    boundary = np.asarray(g["boundary"])
    if boundary.shape != (m,) or boundary.dtype != np.bool_:
        raise ValueError("Require explicit boolean source boundary mask")
    boundary = freeze(boundary)
    area = _array(g["membrane_area_m2"], (m,), "membrane areas", positive=True)
    volume = _array(g["cell_volume_m3"], (n,), "cell volumes", positive=True)
    length = _array(g["gap_length_m"], (m,), "gap lengths", positive=True)
    normal = _array(g["normal_xy"], (m, 2), "normals")
    if np.any(abs(np.sum(normal**2, axis=1) - 1) > 3e-14):
        raise ValueError("Require unit source normals")
    weights = _array(g["gap_weights"], (m,), "fixed gap weights", nonnegative=True)
    valence = _array(ions["valence"], (count,), "valence")
    if np.any(valence != np.trunc(valence)):
        raise ValueError("Require integer valences, including explicit neutral rows")
    moving_ids = ions["moving_ids"]
    if (
        not isinstance(moving_ids, (list, tuple))
        or len(moving_ids) > count
        or len(set(moving_ids)) != len(moving_ids)
        or any(x not in names for x in moving_ids)
    ):
        raise ValueError("Require explicit unique ordered moving-ion subset")
    dm = _array(ions["membrane_diffusion_m2_s"], (count, m), "membrane diffusion", nonnegative=True)
    dg = _array(ions["gap_diffusion_m2_s"], (count, m), "gap diffusion", nonnegative=True)
    constants = {}
    for key in (
        "F_C_mol",
        "R_J_mol_K",
        "configured_temperature_K",
        "membrane_thickness_m",
        "junction_surface_fraction",
        "bath_volume_m3",
    ):
        value = p[key]
        if (
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.floating))
            or not math.isfinite(value)
            or value < 0
            or key != "junction_surface_fraction"
            and value == 0
        ):
            raise ValueError("Require finite positive source parameter: " + key)
        constants[key] = float(value)
    kernel = Kernel(
        owner,
        partner,
        boundary,
        freeze(np.asarray(owner[None, :] == np.arange(n)[:, None], np.float64)),
        area,
        volume,
        length,
        normal,
        weights,
        valence,
        tuple(names.index(name) for name in moving_ids),
        dm,
        dg,
        *(
            constants[key]
            for key in (
                "F_C_mol",
                "R_J_mol_K",
                "configured_temperature_K",
                "membrane_thickness_m",
                "junction_surface_fraction",
                "bath_volume_m3",
            )
        ),
        p["cluster_open"],
    )
    result = Binding(freeze(raw), cells, membranes, names, kernel, "")
    return replace(result, identity=digest(binding_record(result)))


def state(binding, raw, *, step_index=0):
    if set(raw) != set(Values._fields) or type(step_index) is not int or step_index < 0:
        raise ValueError("Require all original numeric state fields and a nonnegative step index")
    i, n, m = len(binding.ion_ids), len(binding.cell_ids), len(binding.membrane_ids)
    shapes = ((i, n), (i, m), (i,), (m,), (i, m), (i, m), (m,), (m,), (m, 2), (m,))
    values = Values(
        *(
            _array(raw[key], shape, key, nonnegative=key in {"cell_mol_m3", "gap_open"})
            for key, shape in zip(Values._fields, shapes, strict=True)
        )
    )
    result = State(binding.identity, step_index, values, "")
    return replace(result, identity=digest((result.binding_identity, step_index, values)))


def drive(binding, *, dt_s, runtime_temperature_K, junction_block):
    for value in (dt_s, runtime_temperature_K):
        if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
            raise ValueError("Require explicit finite positive dt and runtime temperature")
    return Drive(
        float(dt_s),
        float(runtime_temperature_K),
        _array(junction_block, (len(binding.membrane_ids),), "junction block", nonnegative=True),
    )


def _electroflux(ca, cb, diffusion, distance, valence, voltage, temperature, kernel, rho=1):
    # Preserve the source's in-place argument regularization and grouping.
    voltage += NONCE
    valence += NONCE
    alpha = (valence * voltage * kernel.F_C_mol) / (kernel.R_J_mol_K * temperature)
    exponential = np.exp(-alpha)
    denominator = -np.expm1(-alpha)
    return -((diffusion * alpha) / distance) * ((cb - ca * exponential) / denominator) * rho


def step(binding, parent, forcing):
    trial = None
    try:
        if type(binding) is not Binding or binding.identity != digest(binding_record(binding)):
            raise ValueError("Changed binding")
        fresh = bind(data(binding.definition))
        if record(data(binding_record(fresh))) != record(data(binding_record(binding))):
            raise ValueError("Resealed derived source operators changed")
        if type(parent) is not State or parent.binding_identity != binding.identity:
            raise ValueError("Wrong state/binding association")
        checked = state(binding, parent.values._asdict(), step_index=parent.step_index)
        if (
            checked.identity != parent.identity
            or record(checked.values) != record(parent.values)
            or any(v.flags.writeable for v in parent.values)
        ):
            raise ValueError("Changed state, dtype or mutable source buffer")
        if type(forcing) is not Drive:
            raise ValueError("Require complete typed source drive")
        normalized = drive(binding, **forcing._asdict())
        if record(normalized) != record(forcing) or forcing.junction_block.flags.writeable:
            raise ValueError("Changed drive dtype or mutable buffer")
        k = binding.kernel
        arrays = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays.values()
        frames = []
        clipped_mol = np.zeros(len(binding.ion_ids))

        def observe(stage, ion=None):
            frames.append(
                Frame(
                    stage,
                    None if ion is None else binding.ion_ids[ion],
                    Values(
                        *(
                            freeze(value)
                            for value in (cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening)
                        )
                    ),
                )
            )

        observe("initial")
        fm.fill(0)
        fg.fill(0)
        observe("reset_flux")
        failure = None
        with np.errstate(all="ignore"):
            for i in k.moving:
                ones = np.ones(len(binding.membrane_ids))
                leak = _electroflux(
                    bath[i],
                    membrane[i],
                    k.membrane_diffusion_m2_s[i],
                    ones * k.membrane_thickness_m,
                    k.valence[i] * ones,
                    vm,
                    forcing.runtime_temperature_K,
                    k,
                )
                if not k.cluster_open:
                    leak[k.boundary] = 0
                fm[i] += leak
                observe("membrane_flux", i)
                vgj = vm[k.partner] - vm[np.arange(len(vm))]
                egj = -vgj / k.gap_length_m
                exy = np.column_stack((egj * k.normal_xy[:, 0], egj * k.normal_xy[:, 1]))
                opening = forcing.junction_block * np.ones(len(vm)) * k.gap_weights
                gap = _electroflux(
                    membrane[i][np.arange(len(vm))],
                    membrane[i][k.partner],
                    k.gap_diffusion_m2_s[i] * k.junction_surface_fraction * opening,
                    k.gap_length_m * np.ones(len(vm)),
                    k.valence[i] * np.ones(len(vm)),
                    vgj,
                    k.configured_temperature_K,
                    k,
                )
                gap[k.boundary] = 0
                fg[i] = fg[i] + gap
                observe("junction_flux", i)
                membrane[i] = cell[i][k.owner] * 1
                observe("refresh_at_mem", i)
            for i in k.moving:
                delta = np.dot(k.owner_sum, fm[i] * k.area_m2) / k.cell_volume_m3
                cell[i] = cell[i] + delta * forcing.dt_s
                membrane[i] = cell[i][k.owner]
                bath[i] = (
                    bath[i] + (-fm[i] * (k.area_m2 / k.bath_volume_m3)) * forcing.dt_s
                ).mean()
                observe("membrane_commit", i)
                delta_gap = np.dot(k.owner_sum, -fg[i] * k.area_m2) / k.cell_volume_m3
                cell[i] += forcing.dt_s * delta_gap
                observe("junction_commit", i)
                negative, nan = cell[i] < 0, np.isnan(cell[i])
                clipped_mol[i] = np.sum(np.where(negative, -cell[i], 0) * k.cell_volume_m3)
                cell[i][negative] = 0
                if np.any(nan):
                    observe("clip_bulk_failure", i)
                    failure = "Native no_negs sees NaN after its negative-value clipping"
                    break
                observe("clip_bulk", i)
            final = frames[-1].values
            candidate = State(binding.identity, parent.step_index + 1, final, "")
            candidate = replace(
                candidate, identity=digest((binding.identity, candidate.step_index, final))
            )
            cell_change = np.sum((cell - parent.values.cell_mol_m3) * k.cell_volume_m3, axis=1)
            bath_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3
            membrane_transfer = forcing.dt_s * np.sum(fm * k.area_m2, axis=1)
            junction_transfer = forcing.dt_s * np.sum(fg * k.area_m2, axis=1)
            diagnostics = freeze(
                dict(
                    finite=bool(
                        all(np.isfinite(value).all() for frame in frames for value in frame.values)
                    ),
                    moving_ids=tuple(binding.ion_ids[i] for i in k.moving),
                    cell_change_mol=cell_change,
                    bath_change_mol=bath_change,
                    membrane_transfer_mol=membrane_transfer,
                    junction_transfer_mol=junction_transfer,
                    clipping_added_mol=clipped_mol,
                    cell_accounting_residual_mol=cell_change
                    - (membrane_transfer - junction_transfer + clipped_mol),
                    source_mixed_bath_residual_mol=bath_change + membrane_transfer / len(vm),
                    total_cell_bath_change_mol=cell_change + bath_change,
                    final_membrane_bulk_difference_mol_m3=membrane - cell[:, k.owner],
                    negative_bath_retained=bool(np.any(bath < 0)),
                    negative_membrane_retained=bool(np.any(membrane < 0)),
                    source_voltage_nonce_delta_V=vm - parent.values.voltage_V,
                    field_feedback_computed=False,
                    material_conservation_inferred=False,
                )
            )
        trial = Trial(parent, forcing, tuple(frames), candidate, diagnostics, "")
        trial = replace(trial, identity=digest(trial))
        if failure or not diagnostics["finite"]:
            raise ValueError(failure or "Nonfinite literal source intermediate/output")
        return trial
    except Exception as error:
        raise IonJoinRejected(
            error,
            stage="ion_trial" if trial is not None else "source",
            parent=parent,
            drive=forcing,
            trial=trial,
        ) from error
