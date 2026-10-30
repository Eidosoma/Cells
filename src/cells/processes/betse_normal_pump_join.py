"""Pinned maintained-pool Na/K pump before the active normal source join.

The cached sodium-rate proxy is distinct from applied flux and ATP cycles.
All original source clock, stale-state and nonconservative conventions remain.
"""

import math
from dataclasses import dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_gated_join as gated
from cells.processes import betse_normal_ion_join as ions
from cells.processes import betse_normal_voltage as voltage

LAW_ID = "betse_normal_maintained_nak_join_v1_5_0@1"
SOURCE_REVISION = ions.SOURCE_REVISION

def _pumped_material_step(binding, parent, forcing, gate_callback, pump_callback):
    trial = None
    try:
        if type(binding) is not ions.Binding or binding.identity != ions.digest(ions.binding_record(binding)):
            raise ValueError('Changed binding')
        fresh = ions.bind(ions.data(binding.definition))
        if ions.record(ions.data(ions.binding_record(fresh))) != ions.record(ions.data(ions.binding_record(binding))):
            raise ValueError('Resealed derived source operators changed')
        if type(parent) is not ions.State or parent.binding_identity != binding.identity:
            raise ValueError('Wrong state/binding association')
        checked = ions.state(binding, parent.values._asdict(), step_index=parent.step_index)
        if checked.identity != parent.identity or ions.record(checked.values) != ions.record(parent.values) or any((v.flags.writeable for v in parent.values)):
            raise ValueError('Changed state, dtype or mutable source buffer')
        if type(forcing) is not ions.Drive:
            raise ValueError('Require complete typed source drive')
        normalized = ions.drive(binding, **forcing._asdict())
        if ions.record(normalized) != ions.record(forcing) or forcing.junction_block.flags.writeable:
            raise ValueError('Changed drive dtype or mutable buffer')
        k = binding.kernel
        arrays = {key: value.copy() for key, value in parent.values._asdict().items()}
        cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening = arrays.values()
        frames = []
        clipped_mol = np.zeros(len(binding.ion_ids))

        def observe(stage, ion=None):
            frames.append(ions.Frame(stage, None if ion is None else binding.ion_ids[ion], ions.Values(*(ions.freeze(value) for value in (cell, membrane, bath, vm, fm, fg, vgj, egj, exy, opening)))))
        observe('initial')
        fm.fill(0)
        fg.fill(0)
        observe('reset_flux')
        pump_callback(membrane, bath, vm, fm)
        observe('pump_accumulated')
        failure = None
        with np.errstate(all='ignore'):
            for i in k.moving:
                ones = np.ones(len(binding.membrane_ids))
                leak = ions._electroflux(bath[i], membrane[i], k.membrane_diffusion_m2_s[i], ones * k.membrane_thickness_m, k.valence[i] * ones, vm, forcing.runtime_temperature_K, k)
                if not k.cluster_open:
                    leak[k.boundary] = 0
                fm[i] += leak
                observe('membrane_flux', i)
                vgj = vm[k.partner] - vm[np.arange(len(vm))]
                egj = -vgj / k.gap_length_m
                exy = np.column_stack((egj * k.normal_xy[:, 0], egj * k.normal_xy[:, 1]))
                opening = gate_callback(i, vgj, opening)
                gap = ions._electroflux(membrane[i][np.arange(len(vm))], membrane[i][k.partner], k.gap_diffusion_m2_s[i] * k.junction_surface_fraction * opening, k.gap_length_m * np.ones(len(vm)), k.valence[i] * np.ones(len(vm)), vgj, k.configured_temperature_K, k)
                gap[k.boundary] = 0
                fg[i] = fg[i] + gap
                observe('junction_flux', i)
                membrane[i] = cell[i][k.owner] * 1
                observe('refresh_at_mem', i)
            for i in k.moving:
                delta = np.dot(k.owner_sum, fm[i] * k.area_m2) / k.cell_volume_m3
                cell[i] = cell[i] + delta * forcing.dt_s
                membrane[i] = cell[i][k.owner]
                bath[i] = (bath[i] + -fm[i] * (k.area_m2 / k.bath_volume_m3) * forcing.dt_s).mean()
                observe('membrane_commit', i)
                delta_gap = np.dot(k.owner_sum, -fg[i] * k.area_m2) / k.cell_volume_m3
                cell[i] += forcing.dt_s * delta_gap
                observe('junction_commit', i)
                negative, nan = (cell[i] < 0, np.isnan(cell[i]))
                clipped_mol[i] = np.sum(np.where(negative, -cell[i], 0) * k.cell_volume_m3)
                cell[i][negative] = 0
                if np.any(nan):
                    observe('clip_bulk_failure', i)
                    failure = 'Native no_negs sees NaN after its negative-value clipping'
                    break
                observe('clip_bulk', i)
            final = frames[-1].values
            candidate = ions.State(binding.identity, parent.step_index + 1, final, '')
            candidate = replace(candidate, identity=ions.digest((binding.identity, candidate.step_index, final)))
            cell_change = np.sum((cell - parent.values.cell_mol_m3) * k.cell_volume_m3, axis=1)
            bath_change = (bath - parent.values.bath_mol_m3) * k.bath_volume_m3
            membrane_transfer = forcing.dt_s * np.sum(fm * k.area_m2, axis=1)
            junction_transfer = forcing.dt_s * np.sum(fg * k.area_m2, axis=1)
            diagnostics = ions.freeze(dict(finite=bool(all((np.isfinite(value).all() for frame in frames for value in frame.values))), moving_ids=tuple((binding.ion_ids[i] for i in k.moving)), cell_change_mol=cell_change, bath_change_mol=bath_change, membrane_transfer_mol=membrane_transfer, junction_transfer_mol=junction_transfer, clipping_added_mol=clipped_mol, cell_accounting_residual_mol=cell_change - (membrane_transfer - junction_transfer + clipped_mol), source_mixed_bath_residual_mol=bath_change + membrane_transfer / len(vm), total_cell_bath_change_mol=cell_change + bath_change, final_membrane_bulk_difference_mol_m3=membrane - cell[:, k.owner], negative_bath_retained=bool(np.any(bath < 0)), negative_membrane_retained=bool(np.any(membrane < 0)), source_voltage_nonce_delta_V=vm - parent.values.voltage_V, field_feedback_computed=False, material_conservation_inferred=False))
        trial = ions.Trial(parent, forcing, tuple(frames), candidate, diagnostics, '')
        trial = replace(trial, identity=ions.digest(trial))
        if failure or not diagnostics['finite']:
            raise ValueError(failure or 'Nonfinite literal source intermediate/output')
        return trial
    except Exception as error:
        raise ions.IonJoinRejected(error, stage='ion_trial' if trial is not None else 'source', parent=parent, drive=forcing, trial=trial) from error

def _active_material_step(binding, parent, forcing, pump_callback):
    material = None
    updates = []
    candidate = None
    try:
        if type(binding) is not gated.Binding or binding.identity != ions.digest(gated.binding_record(binding)):
            raise ValueError('Changed active-gate binding')
        checked_binding = gated.bind(binding.material_binding, binding.voltage_binding, ions.data(binding.definition))
        if ions.digest(gated.binding_record(checked_binding)) != ions.digest(gated.binding_record(binding)):
            raise ValueError('Resealed gate definition')
        if type(parent) is not gated.State or parent.binding_identity != binding.identity or parent.identity != gated._state(binding, parent.material, parent.memory, parent.initialization).identity:
            raise ValueError('Changed active gate/material association')
        if type(parent.memory.updates) is not int or parent.memory.updates < 0:
            raise ValueError('Invalid source gate invocation count')
        expected_updates = (parent.material.step_index - parent.initialization.parent.step_index) * len(binding.material_binding.kernel.moving)
        if parent.memory.updates != expected_updates:
            raise ValueError('Gate invocation count differs from the ordered material-call lineage')
        for value in parent.memory[:4]:
            if not isinstance(value, np.ndarray) or value.dtype != np.float64 or value.shape != (len(binding.material_binding.membrane_ids),) or value.flags.writeable or (not np.isfinite(value).all()):
                raise ValueError('Require immutable complete gate cache')
        last = [parent.memory.alpha_per_ms, parent.memory.raw_beta_per_ms, parent.memory.beta_per_ms]

        def gate_callback(i, vgj, opening):
            with np.errstate(all='ignore'):
                alpha, raw_beta, beta = gated._rates(vgj, binding.threshold_mV)
                dt_ms = forcing.dt_s * 1000.0
                unblocked = (opening + dt_ms * (alpha + beta * binding.minimum)) / (1 + alpha * dt_ms + beta * dt_ms)
                stored = forcing.junction_block * unblocked
            updates.append(gated.GateFrame(binding.material_binding.ion_ids[i], parent.memory.updates + len(updates) + 1, *(ions.freeze(v) for v in (vgj, opening, alpha, raw_beta, beta, unblocked, stored)), forcing.dt_s, dt_ms))
            last[:] = (alpha, raw_beta, beta)
            return stored
        failure = None
        try:
            material = _pumped_material_step(binding.material_binding, parent.material, forcing, gate_callback, pump_callback)
        except ions.IonJoinRejected as error:
            material, failure = (error.trial, error)
        if material is None:
            raise failure
        memory = gated.Memory(*(ions.freeze(v) for v in last), parent.memory.class_open, parent.memory.updates + len(updates))
        candidate = gated._state(binding, material.candidate, memory, parent.initialization)
        trial = gated.MaterialTrial(parent, material, tuple(updates), candidate, '')
        trial = replace(trial, identity=ions.digest(trial))
        if failure:
            raise gated.GatedJoinRejected(failure, stage='material_trial', parent=parent, material=trial)
        return trial
    except gated.GatedJoinRejected:
        raise
    except Exception as error:
        raise gated.GatedJoinRejected(error, stage='source', parent=parent) from error
