"""Pinned maintained-pool Na/K pump before the active normal source join.

The cached sodium-rate proxy is distinct from applied flux and ATP cycles.
All original source clock, stale-state and nonconservative conventions remain.
"""

import math
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_voltage as voltage

LAW_ID = "betse_normal_maintained_nak_join_v1_5_0@1"
SOURCE_REVISION = ions.SOURCE_REVISION


class Kernel(NamedTuple):
    sodium: int
    potassium: int
    atp_mM: float
    adp_mM: float
    pi_mM: float
    km_na_mM: float
    km_k_mM: float
    km_atp_mM: float
    delta_g_J_mol: float


@dataclass(frozen=True, slots=True)
class Binding:
    gated_binding: gated.Binding
    definition: object
    kernel: Kernel
    identity: str


@dataclass(frozen=True, slots=True)
class State:
    binding_identity: str
    gated: gated.State
    rate_proxy_mol_m2_s: object
    identity: str


class Packet(NamedTuple):
    alpha_NaK: float
    block: object
    rho_pump: object
    met_concs: object


class Arithmetic(NamedTuple):
    quotient_numerator: object
    quotient_denominator_raw: object
    quotient_denominator_used: object
    zero_denominator_indices: object
    quotient: object
    equilibrium: object
    saturation_numerator: object
    saturation_denominator: object
    saturation: object
    raw_sodium_flux_mol_m2_s: object
    raw_potassium_flux_mol_m2_s: object
    raw_rate_proxy_mol_m2_s: object


@dataclass(frozen=True, slots=True)
class Phase:
    incoming_material_identity: str
    packet: Packet
    sodium_at_mem_mM: object
    potassium_at_mem_mM: object
    sodium_bath_mM: object
    potassium_bath_mM: object
    voltage_before_nonce_V: object
    runtime_temperature_K: float
    arithmetic: object
    scaled_sodium_flux_mol_m2_s: object
    scaled_potassium_flux_mol_m2_s: object
    applied_sodium_flux_mol_m2_s: object
    applied_potassium_flux_mol_m2_s: object
    storage_before_mol_m2_s: object
    storage_after_mol_m2_s: object
    rate_proxy_before_mol_m2_s: object
    rate_proxy_after_mol_m2_s: object
    diagnostics: object
    identity: str


@dataclass(frozen=True, slots=True)
class MaterialTrial:
    parent: State
    pump: Phase
    gated: gated.MaterialTrial
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


class PumpJoinRejected(NumericalError):
    def __init__(
        self, reason, *, stage, parent, material=None, phase=None, readout=None, voltage_trial=None
    ):
        super().__init__(
            "Native maintained-pool pump join refused at " + stage + ": " + str(reason)
        )
        self.stage, self.parent, self.material, self.phase = stage, parent, material, phase
        self.readout, self.voltage_trial = readout, voltage_trial


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=SOURCE_REVISION,
        active_join=binding.gated_binding.identity,
        definition=binding.definition,
        kernel=binding.kernel,
    )


def bind(gated_binding, raw):
    if (
        type(gated_binding) is not gated.Binding
        or type(raw) is not dict
        or set(raw) != {"kind", "provenance", "sodium_id", "potassium_id", "maintained", "kinetics"}
        or raw["kind"] != "cells.betse_normal_pump_join_inputs@1"
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
        or set(raw["maintained"]) != {"cATP", "cADP", "cPi"}
        or set(raw["kinetics"]) != {"KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP"}
    ):
        raise ValueError("Require complete maintained-pool pump definition and source roles")
    ib = gated_binding.material_binding
    na, potassium = raw["sodium_id"], raw["potassium_id"]
    if na == potassium or na not in ib.ion_ids or potassium not in ib.ion_ids:
        raise ValueError("Require distinct original Na/K ion roles")
    indices = ib.ion_ids.index(na), ib.ion_ids.index(potassium)
    if any(ib.kernel.valence[i] != 1 for i in indices):
        raise ValueError("Require explicitly declared +1 Na/K roles")
    constants = {}
    for key, value in (raw["maintained"] | raw["kinetics"]).items():
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("Require complete finite scalar pump parameter: " + key)
        if key != "deltaGATP" and (value < 0 or key.startswith("Km") and value == 0):
            raise ValueError("Invalid maintained substrate/Km parameter: " + key)
        constants[key] = float(value)
    k = Kernel(
        *indices,
        *(
            constants[key]
            for key in ("cATP", "cADP", "cPi", "KmNK_Na", "KmNK_K", "KmNK_ATP", "deltaGATP")
        ),
    )
    result = Binding(gated_binding, ions.freeze(raw), k, "")
    return replace(result, identity=ions.digest(binding_record(result)))


def packet(binding, *, alpha_NaK, block, rho_pump, met_concs):
    if type(alpha_NaK) not in (int, float) or not math.isfinite(alpha_NaK):
        raise ValueError("Require explicit finite signed source alpha_NaK")
    m = len(binding.gated_binding.material_binding.membrane_ids)
    block = current._array(block, (m,), "live NaK block", nonnegative=True)
    rho = current._array(rho_pump, (m,), "live pump redistribution", nonnegative=True)
    if met_concs is not None:
        if set(met_concs) != {"cATP", "cADP", "cPi"}:
            raise ValueError("Retain complete explicit ignored metabolic argument or None")
        met_concs = ions.freeze(
            {
                key: current._array(value, (m,), "ignored met argument")
                for key, value in met_concs.items()
            }
        )
    return Packet(float(alpha_NaK), block, rho, met_concs)


def _state(binding, active_state, proxy):
    result = State(binding.identity, active_state, ions.freeze(proxy), "")
    return replace(result, identity=ions.digest((binding.identity, active_state, proxy)))


def initialize(binding, parent, *, initial_gate_block, initial_rate_proxy_mol_m2_s):
    proxy = current._array(
        initial_rate_proxy_mol_m2_s,
        (len(parent.values.voltage_V),),
        "explicit incoming NaK diagnostic",
    )
    return _state(
        binding,
        gated.initialize(binding.gated_binding, parent, initial_block=initial_gate_block),
        proxy,
    )


def _arithmetic(binding, nai, nao, ki, ko, vm, temperature, live):
    p = binding.kernel
    k = binding.gated_binding.material_binding.kernel
    qnum = (p.adp_mM * 1e-3) * (p.pi_mM * 1e-3) * ((nao * 1e-3) ** 3) * ((ki * 1e-3) ** 2)
    qden = (p.atp_mM * 1e-3) * ((nai * 1e-3) ** 3) * ((ko * 1e-3) ** 2)
    qden_raw = qden.copy()
    zero_indices = (qden == 0).nonzero()
    qden[zero_indices] = 1e-15
    quotient = qnum / qden
    equilibrium = np.exp(
        -(
            p.delta_g_J_mol / (k.R_J_mol_K * temperature)
            - (k.F_C_mol * vm) / (k.R_J_mol_K * temperature)
        )
    )
    numerator = ((nai / p.km_na_mM) ** 3) * ((ko / p.km_k_mM) ** 2) * (p.atp_mM / p.km_atp_mM)
    denominator = (
        (1 + (nai / p.km_na_mM) ** 3) * (1 + (ko / p.km_k_mM) ** 2) * (1 + p.atp_mM / p.km_atp_mM)
    )
    saturation = numerator / denominator
    sodium = -3 * live.block * live.alpha_NaK * saturation * (1 - quotient / equilibrium)
    potassium = -(2 / 3) * sodium
    return Arithmetic(
        *(
            ions.freeze(value)
            for value in (
                qnum,
                qden_raw,
                qden,
                zero_indices[0],
                quotient,
                equilibrium,
                numerator,
                denominator,
                saturation,
                sodium,
                potassium,
                -sodium,
            )
        )
    )


def material_step(binding, parent, forcing, live):
    phase = active = None
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError("Changed pump binding")
        checked = bind(binding.gated_binding, ions.data(binding.definition))
        if ions.digest(binding_record(checked)) != ions.digest(binding_record(binding)):
            raise ValueError("Resealed pump coefficients differ from definition")
        if (
            type(parent) is not State
            or parent.binding_identity != binding.identity
            or parent.identity != _state(binding, parent.gated, parent.rate_proxy_mol_m2_s).identity
            or parent.rate_proxy_mol_m2_s.dtype != np.float64
            or parent.rate_proxy_mol_m2_s.flags.writeable
            or parent.rate_proxy_mol_m2_s.shape
            != (len(binding.gated_binding.material_binding.membrane_ids),)
            or not np.isfinite(parent.rate_proxy_mol_m2_s).all()
        ):
            raise ValueError("Require complete immutable pump/gate parent and rate cache")
        if type(live) is not Packet:
            raise ValueError("Require typed complete live pump packet")
        normalized = packet(binding, **live._asdict())
        if ions.record(normalized) != ions.record(live) or any(
            value.flags.writeable for value in (live.block, live.rho_pump)
        ):
            raise ValueError("Changed live packet dtype or mutable controls")
        if live.met_concs is not None and (
            not isinstance(live.met_concs, MappingProxyType)
            or any(value.flags.writeable for value in live.met_concs.values())
        ):
            raise ValueError("Ignored metabolic argument must retain immutable full provenance")
        k, ib = binding.kernel, binding.gated_binding.material_binding

        def pump_callback(membrane, bath, vm, storage):
            nonlocal phase
            old_proxy = parent.rate_proxy_mol_m2_s
            before = storage.copy()
            arithmetic = None
            scaled_na = scaled_k = applied_na = applied_k = np.zeros(len(vm))
            proxy = old_proxy
            with np.errstate(all="ignore"):
                if live.alpha_NaK == 0:
                    proxy = np.zeros(len(vm))
                if live.alpha_NaK > 0:
                    arithmetic = _arithmetic(
                        binding,
                        membrane[k.sodium],
                        bath[k.sodium],
                        membrane[k.potassium],
                        bath[k.potassium],
                        vm,
                        forcing.runtime_temperature_K,
                        live,
                    )
                    proxy = arithmetic.raw_rate_proxy_mol_m2_s
                    scaled_na = live.rho_pump * arithmetic.raw_sodium_flux_mol_m2_s
                    scaled_k = live.rho_pump * arithmetic.raw_potassium_flux_mol_m2_s
                    applied_na, applied_k = scaled_na.copy(), scaled_k.copy()
                    if not ib.kernel.cluster_open:
                        applied_na[ib.kernel.boundary] = 0
                        applied_k[ib.kernel.boundary] = 0
                    storage[k.sodium] += applied_na
                    storage[k.potassium] += applied_k
            finite = all(
                np.isfinite(value).all()
                for value in (scaled_na, scaled_k, applied_na, applied_k, storage, proxy)
            )
            if arithmetic is not None:
                finite = finite and all(np.isfinite(value).all() for value in arithmetic)
            phase = Phase(
                parent.gated.material.identity,
                live,
                *(
                    ions.freeze(value)
                    for value in (
                        membrane[k.sodium],
                        membrane[k.potassium],
                        np.asarray(bath[k.sodium]),
                        np.asarray(bath[k.potassium]),
                        vm,
                    )
                ),
                forcing.runtime_temperature_K,
                arithmetic,
                *(
                    ions.freeze(value)
                    for value in (
                        scaled_na,
                        scaled_k,
                        applied_na,
                        applied_k,
                        before,
                        storage,
                        old_proxy,
                        proxy,
                    )
                ),
                ions.freeze(
                    dict(
                        finite=bool(finite),
                        helper_called=live.alpha_NaK > 0,
                        proxy_cleared=live.alpha_NaK == 0,
                        proxy_retained=live.alpha_NaK < 0,
                        maintained_parameters_used=True,
                        metabolic_argument_used=False,
                        proxy_is_cycle_flux=False,
                        source_concentrations_committed=False,
                    )
                ),
                "",
            )
            phase = replace(phase, identity=ions.digest(phase))

        failure = None
        try:
            active = _active_material_step(
                binding.gated_binding, parent.gated, forcing, pump_callback
            )
        except gated.GatedJoinRejected as error:
            active, failure = error.material, error
        if active is None:
            raise failure
        candidate = _state(binding, active.candidate, phase.rate_proxy_after_mol_m2_s)
        trial = MaterialTrial(parent, phase, active, candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure or not phase.diagnostics["finite"]:
            raise PumpJoinRejected(
                failure or "Nonfinite published pump arithmetic/cache",
                stage="material_trial",
                parent=parent,
                material=trial,
                phase=phase,
            )
        return trial
    except PumpJoinRejected:
        raise
    except Exception as error:
        raise PumpJoinRejected(error, stage="source", parent=parent, phase=phase) from error


def advance(
    binding, parent, forcing, live, *, boundary_V, extra_charge_C_m3, extra_current_A_m2, elapsed_s
):
    material = readout = voltage_trial = None
    try:
        if (
            type(elapsed_s) not in (int, float)
            or not math.isfinite(elapsed_s)
            or elapsed_s < 0
            or not math.isfinite(elapsed_s + forcing.dt_s)
        ):
            raise ValueError("Require explicit finite outer-call clock")
        try:
            material = material_step(binding, parent, forcing, live)
        except PumpJoinRejected as error:
            material = error.material
            raise
        values = material.candidate.gated.material.values
        vb = binding.gated_binding.voltage_binding
        cb = vb.current_binding
        readout = current.evaluate(
            cb,
            current.inputs(
                cb,
                cell_mol_m3=values.cell_mol_m3,
                membrane_flux_mol_m2_s=values.membrane_flux_mol_m2_s,
                junction_flux_mol_m2_s=values.junction_flux_mol_m2_s,
                extra_charge_C_m3=extra_charge_C_m3,
                extra_current_A_m2=extra_current_A_m2,
            ),
        )
        try:
            voltage_trial = voltage.evaluate(
                vb,
                readout,
                old_voltage_V=values.voltage_V,
                dt_s=forcing.dt_s,
                boundary_V=boundary_V,
            )
        except voltage.VoltageRejected as error:
            voltage_trial = error.trial
            raise
        final = ions.state(
            binding.gated_binding.material_binding,
            values._replace(voltage_V=voltage_trial.values.voltage_V)._asdict(),
            step_index=material.candidate.gated.material.step_index,
        )
        active = gated._state(
            binding.gated_binding,
            final,
            material.candidate.gated.memory,
            parent.gated.initialization,
        )
        candidate = _state(binding, active, material.candidate.rate_proxy_mol_m2_s)
        clock = ions.freeze(
            dict(
                call_index=final.step_index,
                elapsed_start_s=float(elapsed_s),
                elapsed_end_s=elapsed_s + forcing.dt_s,
                dt_s=forcing.dt_s,
                native_gate_calls=len(material.gated.gate_updates),
                native_gate_dt_consumed_s=len(material.gated.gate_updates) * forcing.dt_s,
                pump_before_membrane_nonce=True,
                maintained_metabolic_pools=True,
                endogenous_metabolic_consumption=False,
                event_calendar_claim=False,
            )
        )
        result = CoupledTrial(parent, material, readout, voltage_trial, candidate, clock, "")
        return replace(result, identity=ions.digest(result))
    except Exception as error:
        raise PumpJoinRejected(
            error,
            stage="coupled_trial",
            parent=parent,
            material=material,
            phase=material.pump if material else None,
            readout=readout,
            voltage_trial=voltage_trial,
        ) from error


def _pumped_material_step(binding, parent, forcing, gate_callback, pump_callback):
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
        pump_callback(membrane, bath, vm, fm)
        observe("pump_accumulated")
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


def _active_material_step(binding, parent, forcing, pump_callback):
    material = None
    updates = []
    candidate = None
    try:
        if type(binding) is not gated.Binding or binding.identity != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Changed active-gate binding")
        checked_binding = gated.bind(
            binding.material_binding, binding.voltage_binding, ions.data(binding.definition)
        )
        if ions.digest(gated.binding_record(checked_binding)) != ions.digest(
            gated.binding_record(binding)
        ):
            raise ValueError("Resealed gate definition")
        if (
            type(parent) is not gated.State
            or parent.binding_identity != binding.identity
            or parent.identity
            != gated._state(binding, parent.material, parent.memory, parent.initialization).identity
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
                or (not np.isfinite(value).all())
            ):
                raise ValueError("Require immutable complete gate cache")
        last = [
            parent.memory.alpha_per_ms,
            parent.memory.raw_beta_per_ms,
            parent.memory.beta_per_ms,
        ]

        def gate_callback(i, vgj, opening):
            with np.errstate(all="ignore"):
                alpha, raw_beta, beta = gated._rates(vgj, binding.threshold_mV)
                dt_ms = forcing.dt_s * 1000.0
                unblocked = (opening + dt_ms * (alpha + beta * binding.minimum)) / (
                    1 + alpha * dt_ms + beta * dt_ms
                )
                stored = forcing.junction_block * unblocked
            updates.append(
                gated.GateFrame(
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
            last[:] = (alpha, raw_beta, beta)
            return stored

        failure = None
        try:
            material = _pumped_material_step(
                binding.material_binding, parent.material, forcing, gate_callback, pump_callback
            )
        except ions.IonJoinRejected as error:
            material, failure = (error.trial, error)
        if material is None:
            raise failure
        memory = gated.Memory(
            *(ions.freeze(v) for v in last),
            parent.memory.class_open,
            parent.memory.updates + len(updates),
        )
        candidate = gated._state(binding, material.candidate, memory, parent.initialization)
        trial = gated.MaterialTrial(parent, material, tuple(updates), candidate, "")
        trial = replace(trial, identity=ions.digest(trial))
        if failure:
            raise gated.GatedJoinRejected(
                failure, stage="material_trial", parent=parent, material=trial
            )
        return trial
    except gated.GatedJoinRejected:
        raise
    except Exception as error:
        raise gated.GatedJoinRejected(error, stage="source", parent=parent) from error
