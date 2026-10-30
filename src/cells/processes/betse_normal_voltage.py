"""Pinned normal boundary/voltage reconstruction, with explicit source joins.

The supplied inverse/gauge is caller owned. Environment HH/Gaussian readouts
and inverse construction are outside this component's dependency boundary.
"""

import math
from dataclasses import dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core.errors import NumericalError
from cells.processes import betse_normal_current as current
from cells.processes import betse_normal_ion_join as ions

LAW_ID = "betse_normal_boundary_voltage_v1_5_0@1"
INPUT_KIND = "cells.betse_normal_voltage_inputs@1"
SOURCE_REVISION = ions.SOURCE_REVISION


class Kernel(NamedTuple):
    shape: tuple
    delta_m: float
    membrane_to_grid: object
    inverse_m2: object
    diviterm_m: object
    radius_m: object
    free_diffusion_m2_s: object
    capacitance_F_m2: float
    R_J_mol_K: float
    configured_temperature_K: float
    polarizability: float
    true_cell_size_m: float
    cell_radius_m: float


@dataclass(frozen=True, slots=True)
class Binding:
    current_binding: current.CurrentBinding
    definition: object
    kernel: Kernel
    identity: str


class Values(NamedTuple):
    boundary_rhs_V_m2: object
    boundary_potential_V: object
    conductivity_S_m: object
    surface_charge_C_m2: object
    voltage_V: object
    mean_voltage_V: object
    cell_field_xy_V_m: object
    normal_cell_field_V_m: object
    derivative_V_s: object


@dataclass(frozen=True, slots=True)
class Readout:
    binding_identity: str
    source_current: current.CurrentReadout
    old_voltage_V: object
    dt_s: float
    boundary_V: object
    values: Values
    diagnostics: object
    identity: str


class VoltageRejected(NumericalError):
    def __init__(self, reason, *, stage, source, trial=None):
        super().__init__("Native normal voltage refused at " + stage + ": " + str(reason))
        self.stage, self.source, self.trial = stage, source, trial


@dataclass(frozen=True, slots=True)
class CoupledTrial:
    parent: ions.State
    clock: object
    material: ions.Trial
    current: current.CurrentReadout
    voltage: Readout
    candidate: ions.State
    identity: str


class CouplingRejected(NumericalError):
    def __init__(self, reason, *, parent, material, readout, voltage_trial):
        super().__init__("Scoped normal voltage join refused: " + str(reason))
        self.parent, self.material, self.readout, self.voltage_trial = (
            parent,
            material,
            readout,
            voltage_trial,
        )


def binding_record(binding):
    return dict(
        law=LAW_ID,
        revision=SOURCE_REVISION,
        current=binding.current_binding.identity,
        definition=binding.definition,
        kernel=binding.kernel,
    )


def bind(current_binding, raw):
    if (
        type(current_binding) is not current.CurrentBinding
        or type(raw) is not dict
        or set(raw) != {"kind", "provenance", "grid", "geometry", "ions", "parameters"}
        or raw["kind"] != INPUT_KIND
        or type(raw["provenance"]) is not str
        or not raw["provenance"].strip()
    ):
        raise ValueError("Require separate source voltage definition and current association")
    grid, geometry, species, p = raw["grid"], raw["geometry"], raw["ions"], raw["parameters"]
    if (
        set(grid) != {"shape", "delta_m", "membrane_to_grid", "inverse_m2", "operator_provenance"}
        or set(geometry) != {"diviterm_m", "radius_m"}
        or set(species) != {"free_diffusion_m2_s"}
        or set(p)
        != {
            "capacitance_F_m2",
            "R_J_mol_K",
            "configured_temperature_K",
            "polarizability",
            "true_cell_size_m",
            "cell_radius_m",
        }
        or type(grid["operator_provenance"]) is not str
        or not grid["operator_provenance"].strip()
    ):
        raise ValueError("Declare complete source operators, gauge provenance and parameters")
    shape = tuple(grid["shape"])
    if len(shape) != 2 or any(type(x) is not int or not 2 <= x <= 16 for x in shape):
        raise ValueError("Require bounded original row/column grid axes")
    n, m, count = (
        len(current_binding.cell_ids),
        len(current_binding.membrane_ids),
        len(current_binding.ion_ids),
    )
    mapping = np.asarray(grid["membrane_to_grid"])
    if (
        mapping.shape != (m,)
        or mapping.dtype.kind not in "iu"
        or np.any(mapping < 0)
        or np.any(mapping >= math.prod(shape))
    ):
        raise ValueError("Require complete original membrane-to-ravel-grid mapping")
    values = {}
    for key, value in dict(delta_m=grid["delta_m"], **p).items():
        if (
            isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.floating))
            or not math.isfinite(value)
            or value < 0
            or key != "polarizability"
            and value == 0
        ):
            raise ValueError("Require finite positive voltage parameter: " + key)
        values[key] = float(value)
    kernel = Kernel(
        shape,
        values["delta_m"],
        ions.freeze(mapping.astype(np.int64)),
        current._array(grid["inverse_m2"], (math.prod(shape), math.prod(shape)), "caller inverse"),
        current._array(geometry["diviterm_m"], (n,), "source diviterm", positive=True),
        current._array(geometry["radius_m"], (m,), "source radii", positive=True),
        current._array(
            species["free_diffusion_m2_s"], (count,), "free diffusion", nonnegative=True
        ),
        *(
            values[key]
            for key in (
                "capacitance_F_m2",
                "R_J_mol_K",
                "configured_temperature_K",
                "polarizability",
                "true_cell_size_m",
                "cell_radius_m",
            )
        ),
    )
    result = Binding(current_binding, ions.freeze(raw), kernel, "")
    return replace(result, identity=ions.digest(binding_record(result)))


def evaluate(binding, readout, *, old_voltage_V, dt_s, boundary_V):
    trial = None
    source = dict(current=readout, old_voltage_V=old_voltage_V, dt_s=dt_s, boundary_V=boundary_V)
    try:
        if type(binding) is not Binding or binding.identity != ions.digest(binding_record(binding)):
            raise ValueError("Changed voltage binding")
        prepared = bind(binding.current_binding, ions.data(binding.definition))
        if current.record(ions.data(binding_record(prepared))) != current.record(
            ions.data(binding_record(binding))
        ):
            raise ValueError("Resealed voltage operators differ from original definition")
        cb, k = binding.current_binding, binding.kernel
        if type(readout) is not current.CurrentReadout or readout.binding_identity != cb.identity:
            raise ValueError("Wrong source current binding")
        fresh = current.evaluate(cb, readout.source)
        if ions.digest(fresh) != ions.digest(readout):
            raise ValueError("Changed source current readout")
        old = current._array(old_voltage_V, (len(cb.membrane_ids),), "pre-voltage state")
        if type(dt_s) not in (float, int) or not math.isfinite(dt_s) or dt_s <= 0:
            raise ValueError("Require explicit positive call dt")
        if set(boundary_V) != {"R", "L", "T", "B"}:
            raise ValueError("Require all four source boundary voltages")
        boundary = {key: float(boundary_V[key]) for key in ("R", "L", "T", "B")}
        if not all(math.isfinite(value) for value in boundary.values()):
            raise ValueError("Nonfinite boundary packet")
        with np.errstate(all="ignore"):
            rhs = np.zeros(k.shape)
            rhs[:, -1] = -boundary["R"] / k.delta_m**2
            rhs[:, 0] = -boundary["L"] / k.delta_m**2
            rhs[-1, :] = -boundary["T"] / k.delta_m**2
            rhs[0, :] = -boundary["B"] / k.delta_m**2
            phi = np.dot(k.inverse_m2, -rhs.ravel())
            ck = cb.kernel
            conductivity = np.asarray(
                [
                    ((z**2) * (ck.F_C_mol**2) * cc * diffusion * 0.1)
                    / (k.R_J_mol_K * k.configured_temperature_K)
                    for z, cc, diffusion in zip(
                        ck.valence, readout.source.cell_mol_m3, k.free_diffusion_m2_s, strict=True
                    )
                ]
            ).mean(axis=0)
            surface = readout.values.charge_density_C_m3 * k.diviterm_m
            if k.polarizability == 0:
                voltage = (1 / k.capacitance_F_m2) * surface[ck.owner] - phi[k.membrane_to_grid]
                mean = np.dot(ck.owner_sum, voltage) / np.bincount(
                    ck.owner, minlength=len(cb.cell_ids)
                )
                ex = readout.values.cell_current_xy_A_m2[:, 0] / conductivity
                ey = readout.values.cell_current_xy_A_m2[:, 1] / conductivity
            else:
                charge_voltage = (1 / k.capacitance_F_m2) * surface[ck.owner]
                voltage = (
                    old
                    - (dt_s / k.capacitance_F_m2) * readout.values.normal_current_A_m2
                    + (
                        (dt_s * conductivity[ck.owner] * charge_voltage)
                        / (k.capacitance_F_m2 * k.radius_m)
                    )
                ) / (1 + ((dt_s * conductivity[ck.owner]) / (k.capacitance_F_m2 * k.radius_m)))
                mean = np.dot(ck.owner_sum, voltage) / np.bincount(
                    ck.owner, minlength=len(cb.cell_ids)
                )
                radii = k.radius_m * (k.true_cell_size_m / k.cell_radius_m)
                gradient = (voltage - mean[ck.owner]) / radii
                ex = (
                    np.dot(ck.owner_sum, (-gradient * ck.normal_xy[:, 0]) * ck.membrane_area_m2)
                    / ck.cell_area_m2
                )
                ey = (
                    np.dot(ck.owner_sum, (-gradient * ck.normal_xy[:, 1]) * ck.membrane_area_m2)
                    / ck.cell_area_m2
                )
            normal = ex[ck.owner] * ck.normal_xy[:, 0] + ey[ck.owner] * ck.normal_xy[:, 1]
            derivative = (voltage - old) / dt_s
        output = Values(
            *(
                ions.freeze(v)
                for v in (
                    rhs,
                    phi,
                    conductivity,
                    surface,
                    voltage,
                    mean,
                    np.column_stack((ex, ey)),
                    normal,
                    derivative,
                )
            )
        )
        diagnostics = ions.freeze(
            dict(
                finite=bool(all(np.isfinite(v).all() for v in output)),
                boundary_assignment_order=("R", "L", "T", "B"),
                direct_boundary_subtraction=k.polarizability == 0,
                current_before_voltage=True,
                mean_is_area_weighted=False,
                environment_HH_Gaussian_readouts_computed=False,
                inverse_prepared=False,
                physical_field_energy_parity=False,
            )
        )
        trial = Readout(
            binding.identity,
            readout,
            old,
            float(dt_s),
            ions.freeze(boundary),
            output,
            diagnostics,
            "",
        )
        trial = replace(trial, identity=ions.digest(trial))
        if not diagnostics["finite"]:
            raise ValueError("Nonfinite actual source voltage/field trial")
        return trial
    except Exception as error:
        raise VoltageRejected(
            error, stage="voltage_trial" if trial else "source", source=source, trial=trial
        ) from error


def advance(
    ion_binding,
    voltage_binding,
    parent,
    drive,
    *,
    boundary_V,
    extra_charge_C_m3,
    extra_current_A_m2,
    elapsed_s,
):
    material = readout = voltage_trial = None
    try:
        cb = voltage_binding.current_binding
        ck, ik = cb.kernel, ion_binding.kernel
        if (
            cb.cell_ids != ion_binding.cell_ids
            or cb.membrane_ids != ion_binding.membrane_ids
            or cb.ion_ids != ion_binding.ion_ids
            or ck.F_C_mol != ik.F_C_mol
            or voltage_binding.kernel.R_J_mol_K != ik.R_J_mol_K
            or voltage_binding.kernel.configured_temperature_K != ik.configured_temperature_K
            or any(
                not np.array_equal(a, b)
                for a, b in (
                    (ck.owner, ik.owner),
                    (ck.valence, ik.valence),
                    (ck.membrane_area_m2, ik.area_m2),
                    (ck.normal_xy, ik.normal_xy),
                )
            )
        ):
            raise ValueError("Material/current/voltage source axes or constants differ")
        if (
            type(elapsed_s) not in (int, float)
            or not math.isfinite(elapsed_s)
            or elapsed_s < 0
            or not math.isfinite(elapsed_s + drive.dt_s)
        ):
            raise ValueError("Declare explicit elapsed call boundary")
        material = ions.step(ion_binding, parent, drive)
        state = material.candidate.values
        readout = current.evaluate(
            cb,
            current.inputs(
                cb,
                cell_mol_m3=state.cell_mol_m3,
                membrane_flux_mol_m2_s=state.membrane_flux_mol_m2_s,
                junction_flux_mol_m2_s=state.junction_flux_mol_m2_s,
                extra_charge_C_m3=extra_charge_C_m3,
                extra_current_A_m2=extra_current_A_m2,
            ),
        )
        try:
            voltage_trial = evaluate(
                voltage_binding,
                readout,
                old_voltage_V=state.voltage_V,
                dt_s=drive.dt_s,
                boundary_V=boundary_V,
            )
        except VoltageRejected as error:
            voltage_trial = error.trial
            raise
        final = ions.state(
            ion_binding,
            state._replace(voltage_V=voltage_trial.values.voltage_V)._asdict(),
            step_index=material.candidate.step_index,
        )
        clock = ions.freeze(
            dict(
                call_index=final.step_index,
                elapsed_start_s=float(elapsed_s),
                dt_s=drive.dt_s,
                elapsed_end_s=elapsed_s + drive.dt_s,
                event_calendar_claim=False,
            )
        )
        result = CoupledTrial(parent, clock, material, readout, voltage_trial, final, "")
        return replace(result, identity=ions.digest(result))
    except Exception as error:
        raise CouplingRejected(
            error, parent=parent, material=material, readout=readout, voltage_trial=voltage_trial
        ) from error
