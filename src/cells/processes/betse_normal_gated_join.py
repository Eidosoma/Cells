"""Literal native active gate/material join; separate from physical-time gate law.

Frozen B24 layout/preparation and B23/B25 readouts are reused, not modified.
The active material numerical body is copied with one explicit gate callback.
"""

import math
from dataclasses import dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_voltage as voltage

LAW_ID = "betse_normal_active_gap_join_v1_5_0@1"
SOURCE_REVISION = ions.SOURCE_REVISION


@dataclass(frozen=True, slots=True)
class Binding:
    material_binding: ions.Binding
    voltage_binding: voltage.Binding
    definition: object
    threshold_mV: float
    minimum: float
    identity: str


class Memory(NamedTuple):
    alpha_per_ms: object
    raw_beta_per_ms: object
    beta_per_ms: object
    class_open: object
    updates: int


@dataclass(frozen=True, slots=True)
class Initialization:
    parent: ions.State
    cached_voltage_V: object
    block: object
    memory: Memory
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    binding_identity: str
    material: ions.State
    memory: Memory
    initialization: Initialization
    identity: str


class GateFrame(NamedTuple):
    ion_id: str
    update_index: int
    voltage_before_nonce_V: object
    opening_before: object
    alpha_per_ms: object
    raw_beta_per_ms: object
    beta_per_ms: object
    opening_unblocked: object
    opening_stored: object
    dt_s: float
    dt_ms: float


@dataclass(frozen=True, slots=True)
class MaterialTrial:
    parent: State
    material: ions.Trial
    gate_updates: tuple
    candidate: State
    identity: str


@dataclass(frozen=True, slots=True)
class CoupledTrial:
    parent: State
    material: MaterialTrial
    current: current.CurrentReadout
    voltage: voltage.Readout
    candidate: State
    clock: object
    identity: str


class GatedJoinRejected(NumericalError):
    def __init__(
        self,
        reason,
        *,
        stage,
        parent,
        initialization=None,
        material=None,
        readout=None,
        voltage_trial=None,
    ):
        super().__init__("Native active gap join refused at " + stage + ": " + str(reason))
        self.stage, self.parent, self.initialization = stage, parent, initialization
        self.material, self.readout, self.voltage_trial = material, readout, voltage_trial


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=SOURCE_REVISION,
        material=binding.material_binding.identity,
        voltage=binding.voltage_binding.identity,
        definition=binding.definition,
        threshold_mV=binding.threshold_mV,
        minimum=binding.minimum,
        native_class_constants=dict(lamb=0.0013, A1=0.077, A2=0.14, Ao=0.217),
    )


def bind(material_binding, voltage_binding, raw):
    if (
        type(material_binding) is not ions.Binding
        or type(voltage_binding) is not voltage.Binding
        or type(raw) is not dict
        or set(raw) != {"kind", "provenance", "threshold_mV", "minimum"}
        or raw["kind"] != "cells.betse_normal_gated_join_inputs@1"
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError(
            "Require explicit separate active-gate definition and prepared source layouts"
        )
    for key in ("threshold_mV", "minimum"):
        if type(raw[key]) not in (float, int) or not math.isfinite(raw[key]) or raw[key] < 0:
            raise ValueError("Require finite nonnegative native gate parameter: " + key)
    if raw["minimum"] > 1:
        raise ValueError("Require explicit minimum in [0,1]")
    cb, k = voltage_binding.current_binding, material_binding.kernel
    if (
        cb.cell_ids != material_binding.cell_ids
        or cb.membrane_ids != material_binding.membrane_ids
        or cb.ion_ids != material_binding.ion_ids
        or cb.kernel.F_C_mol != k.F_C_mol
        or voltage_binding.kernel.R_J_mol_K != k.R_J_mol_K
        or voltage_binding.kernel.configured_temperature_K != k.configured_temperature_K
        or any(
            not np.array_equal(a, b)
            for a, b in (
                (cb.kernel.owner, k.owner),
                (cb.kernel.valence, k.valence),
                (cb.kernel.membrane_area_m2, k.area_m2),
                (cb.kernel.normal_xy, k.normal_xy),
            )
        )
    ):
        raise ValueError("Active material/current/voltage source axes/constants differ")
    result = Binding(
        material_binding,
        voltage_binding,
        ions.freeze(raw),
        float(raw["threshold_mV"]),
        float(raw["minimum"]),
        "",
    )
    return replace(result, identity=ions.digest(binding_record(result)))


def _rates(voltage_V, threshold_mV):
    v1 = 1.0e3 * np.abs(voltage_V)
    alpha = 0.0013 * np.exp(-0.077 * (v1 - threshold_mV))
    raw_beta = 0.0013 * np.exp(0.14 * (v1 - threshold_mV))
    beta = raw_beta / (1 + 50 * raw_beta)
    return alpha, raw_beta, beta


def _state(binding, material, memory, initialization):
    result = State(binding.identity, material, memory, initialization, "")
    return replace(
        result, identity=ions.digest((binding.identity, material, memory, initialization))
    )


def initialize(binding, parent, *, initial_block):
    initialization = None
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError("Changed gate binding")
        normalized = bind(
            binding.material_binding, binding.voltage_binding, ions.data(binding.definition)
        )
        if ions.digest(binding_record(normalized)) != ions.digest(binding_record(binding)):
            raise ValueError("Resealed gate parameters differ from definition")
        checked = ions.state(
            binding.material_binding, parent.values._asdict(), step_index=parent.step_index
        )
        if (
            parent.identity != checked.identity
            or ions.record(checked.values) != ions.record(parent.values)
            or any(v.flags.writeable for v in parent.values)
        ):
            raise ValueError("Changed or mutable explicit initial material state")
        block = current._array(
            initial_block, (len(parent.values.voltage_V),), "initial gate block", nonnegative=True
        )
        cached = parent.values.junction_voltage_V
        with np.errstate(all="ignore"):
            alpha, raw_beta, beta = _rates(cached, binding.threshold_mV)
            class_open = block * ((alpha / (alpha + beta)) + binding.minimum)
        memory = Memory(*(ions.freeze(v) for v in (alpha, raw_beta, beta, class_open)), 0)
        initialization = Initialization(parent, cached, block, memory, "")
        initialization = replace(initialization, identity=ions.digest(initialization))
        if not all(np.isfinite(v).all() for v in memory[:4]):
            raise ValueError("Nonfinite literal class initialization")
        return _state(binding, parent, memory, initialization)
    except Exception as error:
        raise GatedJoinRejected(
            error, stage="initialization", parent=parent, initialization=initialization
        ) from error


def material_step(binding, parent, forcing):
    material = None
    updates = []
    candidate = None
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError("Changed active-gate binding")
        checked_binding = bind(
            binding.material_binding, binding.voltage_binding, ions.data(binding.definition)
        )
        if ions.digest(binding_record(checked_binding)) != ions.digest(binding_record(binding)):
            raise ValueError("Resealed gate definition")
        if (
            type(parent) is not State
            or parent.binding_identity != binding.identity
            or parent.identity
            != _state(binding, parent.material, parent.memory, parent.initialization).identity
        ):
            raise ValueError("Changed active gate/material association")
        if type(parent.memory.updates) is not int or parent.memory.updates < 0:
            raise ValueError("Invalid source gate invocation count")
        expected_updates = (
            parent.material.step_index - parent.initialization.parent.step_index
        ) * len(binding.material_binding.kernel.moving)
        if parent.memory.updates != expected_updates:
            raise ValueError("Gate invocation count differs from the ordered material-call lineage")
        for value in parent.memory[:4]:
            if (
                not isinstance(value, np.ndarray)
                or value.dtype != np.float64
                or value.shape != (len(binding.material_binding.membrane_ids),)
                or value.flags.writeable
                or not np.isfinite(value).all()
            ):
                raise ValueError("Require immutable complete gate cache")
        last = [
            parent.memory.alpha_per_ms,
            parent.memory.raw_beta_per_ms,
            parent.memory.beta_per_ms,
        ]

        def gate_callback(i, vgj, opening):
            with np.errstate(all="ignore"):
                alpha, raw_beta, beta = _rates(vgj, binding.threshold_mV)
                dt_ms = forcing.dt_s * 1e3
                unblocked = (opening + dt_ms * (alpha + beta * binding.minimum)) / (
                    1 + alpha * dt_ms + beta * dt_ms
                )
                stored = forcing.junction_block * unblocked
            updates.append(
                GateFrame(
                    binding.material_binding.ion_ids[i],
                    parent.memory.updates + len(updates) + 1,
                    *(
                        ions.freeze(v)
                        for v in (vgj, opening, alpha, raw_beta, beta, unblocked, stored)
                    ),
                    forcing.dt_s,
                    dt_ms,
                )
            )
            last[:] = alpha, raw_beta, beta
            return stored

        failure = None
        try:
            material = _material_step(
                binding.material_binding, parent.material, forcing, gate_callback
            )
        except ions.IonJoinRejected as error:
            material, failure = error.trial, error
        if material is None:
            raise failure
        memory = Memory(
            *(ions.freeze(v) for v in last),
            parent.memory.class_open,
            parent.memory.updates + len(updates),
        )
        candidate = _state(binding, material.candidate, memory, parent.initialization)
        trial = MaterialTrial(parent, material, tuple(updates), candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure:
            raise GatedJoinRejected(failure, stage="material_trial", parent=parent, material=trial)
        return trial
    except GatedJoinRejected:
        raise
    except Exception as error:
        raise GatedJoinRejected(error, stage="source", parent=parent) from error


def advance(
    binding, parent, forcing, *, boundary_V, extra_charge_C_m3, extra_current_A_m2, elapsed_s
):
    material = readout = voltage_trial = None
    try:
        if (
            type(elapsed_s) not in (int, float)
            or not math.isfinite(elapsed_s)
            or elapsed_s < 0
            or not math.isfinite(elapsed_s + forcing.dt_s)
        ):
            raise ValueError("Require explicit finite outer-call elapsed clock")
        try:
            material = material_step(binding, parent, forcing)
        except GatedJoinRejected as error:
            material = error.material
            raise
        source = material.candidate.material.values
        cb = binding.voltage_binding.current_binding
        readout = current.evaluate(
            cb,
            current.inputs(
                cb,
                cell_mol_m3=source.cell_mol_m3,
                membrane_flux_mol_m2_s=source.membrane_flux_mol_m2_s,
                junction_flux_mol_m2_s=source.junction_flux_mol_m2_s,
                extra_charge_C_m3=extra_charge_C_m3,
                extra_current_A_m2=extra_current_A_m2,
            ),
        )
        try:
            voltage_trial = voltage.evaluate(
                binding.voltage_binding,
                readout,
                old_voltage_V=source.voltage_V,
                dt_s=forcing.dt_s,
                boundary_V=boundary_V,
            )
        except voltage.VoltageRejected as error:
            voltage_trial = error.trial
            raise
        final = ions.state(
            binding.material_binding,
            source._replace(voltage_V=voltage_trial.values.voltage_V)._asdict(),
            step_index=material.candidate.material.step_index,
        )
        candidate = _state(binding, final, material.candidate.memory, parent.initialization)
        clock = ions.freeze(
            dict(
                call_index=final.step_index,
                elapsed_start_s=float(elapsed_s),
                elapsed_end_s=elapsed_s + forcing.dt_s,
                dt_s=forcing.dt_s,
                native_gate_calls=len(material.gate_updates),
                native_gate_dt_consumed_s=len(material.gate_updates) * forcing.dt_s,
                event_calendar_claim=False,
            )
        )
        trial = CoupledTrial(parent, material, readout, voltage_trial, candidate, clock, "")
        return replace(trial, identity=ions.digest(trial))
    except Exception as error:
        raise GatedJoinRejected(
            error,
            stage="coupled_trial",
            parent=parent,
            material=material,
            readout=readout,
            voltage_trial=voltage_trial,
        ) from error


def _material_step(binding, parent, forcing, gate_callback):
    trial = None
    try:
        if type(binding) is not ions.Binding or binding.identity != ions.digest(
            ions.binding_record(binding)
        ):
            raise ValueError("Changed binding")
        fresh = ions.bind(ions.data(binding.definition))
        if ions.record(ions.data(ions.binding_record(fresh))) != ions.record(
            ions.data(ions.binding_record(binding))
        ):
            raise ValueError("Resealed derived source operators changed")
        if type(parent) is not ions.State or parent.binding_identity != binding.identity:
            raise ValueError("Wrong state/binding association")
        checked = ions.state(binding, parent.values._asdict(), step_index=parent.step_index)
        if (
            checked.identity != parent.identity
            or ions.record(checked.values) != ions.record(parent.values)
            or any((v.flags.writeable for v in parent.values))
        ):
            raise ValueError("Changed state, dtype or mutable source buffer")
        if type(forcing) is not ions.Drive:
            raise ValueError("Require complete typed source drive")
        normalized = ions.drive(binding, **forcing._asdict())
        if (
            ions.record(normalized) != ions.record(forcing)
            or forcing.junction_block.flags.writeable
        ):
            raise ValueError("Changed drive dtype or mutable buffer")
        k = binding.kernel
        arrays = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays.values()
        frames = []
        clipped_mol = np.zeros(len(binding.ion_ids))

        def observe(stage, ion=None):
            frames.append(
                ions.Frame(
                    stage,
                    None if ion is None else binding.ion_ids[ion],
                    ions.Values(
                        *(
                            ions.freeze(value)
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
                leak = ions._electroflux(
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
                opening = gate_callback(i, vgj, opening)
                gap = ions._electroflux(
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
                bath[i] = (bath[i] + -fm[i] * (k.area_m2 / k.bath_volume_m3) * forcing.dt_s).mean()
                observe("membrane_commit", i)
                delta_gap = np.dot(k.owner_sum, -fg[i] * k.area_m2) / k.cell_volume_m3
                cell[i] += forcing.dt_s * delta_gap
                observe("junction_commit", i)
                negative, nan = (cell[i] < 0, np.isnan(cell[i]))
                clipped_mol[i] = np.sum(np.where(negative, -cell[i], 0) * k.cell_volume_m3)
                cell[i][negative] = 0
                if np.any(nan):
                    observe("clip_bulk_failure", i)
                    failure = "Native no_negs sees NaN after its negative-value clipping"
                    break
                observe("clip_bulk", i)
            final = frames[-1].values
            candidate = ions.State(binding.identity, parent.step_index + 1, final, "")
            candidate = replace(
                candidate, identity=ions.digest((binding.identity, candidate.step_index, final))
            )
            cell_change = np.sum((cell - parent.values.cell_mol_m3) * k.cell_volume_m3, axis=1)
            bath_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3
            membrane_transfer = forcing.dt_s * np.sum(fm * k.area_m2, axis=1)
            junction_transfer = forcing.dt_s * np.sum(fg * k.area_m2, axis=1)
            diagnostics = ions.freeze(
                dict(
                    finite=bool(
                        all(
                            (np.isfinite(value).all() for frame in frames for value in frame.values)
                        )
                    ),
                    moving_ids=tuple((binding.ion_ids[i] for i in k.moving)),
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
        trial = ions.Trial(parent, forcing, tuple(frames), candidate, diagnostics, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure or not diagnostics["finite"]:
            raise ValueError(failure or "Nonfinite literal source intermediate/output")
        return trial
    except Exception as error:
        raise ions.IonJoinRejected(
            error,
            stage="ion_trial" if trial is not None else "source",
            parent=parent,
            drive=forcing,
            trial=trial,
        ) from error
