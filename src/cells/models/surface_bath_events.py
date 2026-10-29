"""Shared physical controller for passive and complete ionic ideal reservoirs.

Saved parent arrays are TRANSPORT contributions against immutable original
anchors. The prescribed controller contribution is a deterministic function of
the saved clock. ``physical_state`` adds its explicitly reported dose, charge
and work, including the nonzero preparation at t=0. No finite compartment is
clamped and no history/background charge is reset.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core import surface_bath_events_binding as binding
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError, digest
from cells.models import surface_tissue as passive
from cells.numerics import surface_field
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

EXTRA_AXES = {
    "reservoir_chemical_work_pJ": ["extracellular_slot"],
    "phase_clock_s": ["phase_clock"],
}
EXTRA_OBSERVATIONS = (
    *EXTRA_AXES,
    "bath_pulse",
    "bath_dose_fmol",
    "bath_dose_rate_fmol_s",
    "bath_charge_C",
    "bath_chemical_work_pJ",
    "bath_electrochemical_work_pJ",
    "bath_electrode_work_pJ",
    "physical_extracellular_amount_increment",
    "physical_reservoir_supplied",
    "physical_electrode_charge_transferred_C",
    "physical_reservoir_work_pJ",
    "physical_electrode_work_pJ",
    "physical_reservoir_chemical_work_pJ",
    "maintenance_reservoir_supply_fmol_s",
    "maintenance_electrode_current_A",
    "maintenance_reservoir_power_pJ_s",
    "maintenance_electrode_power_pJ_s",
)


class Signal(NamedTuple):
    pulse: object
    dose_fmol: object
    dose_rate_fmol_s: object
    charge_C: object
    charge_rate_A: object
    chemical_work_pJ: object
    chemical_power_pJ_s: object
    electrochemical_work_pJ: object
    electrochemical_power_pJ_s: object
    electrode_work_pJ: object
    electrode_power_pJ_s: object
    valid: object


def signal_values(state, p, *, xp=jnp):
    time = state.phase_clock_s[0]
    gain = 10 / p.bath_change_s
    left = xp.exp(-xp.logaddexp(0.0, -gain * (time - p.bath_on_s)))
    right = xp.exp(-xp.logaddexp(0.0, -gain * (time - p.bath_off_s)))
    pulse = xp.where(p.bath_event_active, left - right, 0.0)
    # sigmoid(x)*(1-sigmoid(x)) loses tail precision when sigmoid(x)
    # rounds close to one. Its equivalent even form never subtracts from one;
    # the prescribed native pulse/concentration above remains unchanged.
    left_tail = xp.exp(-xp.abs(gain * (time - p.bath_on_s)))
    right_tail = xp.exp(-xp.abs(gain * (time - p.bath_off_s)))
    speed = xp.where(
        p.bath_event_active,
        gain * (left_tail / (1 + left_tail) ** 2 - right_tail / (1 + right_tail) ** 2),
        0.0,
    )
    dose = xp.sum(p.bath_amount_coefficient_fmol * pulse[:, None, None], axis=0)
    rate = xp.sum(p.bath_amount_coefficient_fmol * speed[:, None, None], axis=0)
    charge = CHARGE_PER_FMOL * xp.sum(p.valence * dose, axis=0)
    current = CHARGE_PER_FMOL * xp.sum(p.valence * rate, axis=0)
    anchor = xp.where(p.outside_active, p.extracellular_amount_reference, 1.0)
    concentration = (anchor + dose) / p.extracellular_volume
    chemical = (
        1e-3
        * R
        * p.temperature
        * xp.sum(
            dose * (xp.log(anchor / p.extracellular_volume) - 1)
            + (anchor + dose) * xp.log1p(dose / anchor),
            axis=0,
        )
    )
    chemical_rate = 1e-3 * R * p.temperature * xp.sum(xp.log(concentration) * rate, axis=0)
    electric = 1e12 * p.boundary_V * charge
    electric_rate = 1e12 * p.boundary_V * current
    values = (
        pulse,
        dose,
        rate,
        charge,
        current,
        chemical,
        chemical_rate,
        chemical + electric,
        chemical_rate + electric_rate,
        -electric,
        -electric_rate,
    )
    valid = xp.all(xp.isfinite(time) & (time >= 0) & (time <= p.phase_end_s + p.phase_clock_atol_s))
    for value in values:
        valid &= xp.all(xp.isfinite(value))
    valid &= xp.all(concentration > 0)
    return Signal(*values, valid)


class Values(NamedTuple):
    field: object
    derivative: object
    signal: object
    parent: object
    valid: object


class Adapter:
    """Exact parent delegation with explicit additive external controllers."""

    def __init__(self, base, schema, name, *, active):
        self.base, self.schema, self.active = base, schema, active
        self.STATE_AXES = base.STATE_AXES | EXTRA_AXES
        self.STATE_TYPE = NamedTuple(name + "State", [(k, object) for k in self.STATE_AXES])
        self.LAYOUT_TYPE = NamedTuple(
            name + "Layout",
            [(k, object) for k in (*base.LAYOUT_TYPE._fields, *binding.EXTRA_LAYOUT)],
        )
        self.OBSERVATION_FIELDS = (*base.OBSERVATION_FIELDS, *EXTRA_OBSERVATIONS)
        self.Observations = make_dataclass(
            name + "Observations", [(k, np.ndarray) for k in self.OBSERVATION_FIELDS], frozen=True
        )

    def parent_state(self, state):
        return self.base.STATE_TYPE(*(getattr(state, k) for k in self.base.STATE_TYPE._fields))

    def parent_layout(self, p):
        return self.base.LAYOUT_TYPE(*(getattr(p, k) for k in self.base.LAYOUT_TYPE._fields))

    def initial_values(self, spec):
        state, parent = self.base.initial_values(self.schema.owner_spec(spec))
        extra, _ = binding.native_parameters(spec, parent)
        return (
            self.STATE_TYPE(*state, np.zeros_like(parent.boundary_V), np.zeros(1)),
            self.LAYOUT_TYPE(**(parent._asdict() | extra)),
        )

    def initial_operation(self, spec):
        state, p = self.initial_values(spec)
        signal = signal_values(state, p, xp=np)
        _, source_identities = binding.native_parameters(spec, self.parent_layout(p))
        record = dict(
            kind=binding.PREPARATION_KIND,
            time_s=0.0,
            original_parent_definition_digest=digest(
                self.schema.parent.to_dict(self.schema.owner_spec(spec))
            ),
            native_bath_binding_identities=list(source_identities),
            bath_site_ids=list(spec.model.bath_site_ids),
            dose_fmol=signal.dose_fmol.tolist(),
            charge_C=signal.charge_C.tolist(),
            chemical_work_pJ=signal.chemical_work_pJ.tolist(),
            electrochemical_work_pJ=signal.electrochemical_work_pJ.tolist(),
            electrode_charge_C=(-signal.charge_C).tolist(),
            electrode_work_pJ=signal.electrode_work_pJ.tolist(),
            accounting="additive initial controller operation against unchanged original anchors",
        )
        record["identity"] = digest(record)
        return record

    def stage_layout(self, p, signal):
        # This read-only argument view supplies ACTUAL current reservoir amounts
        # and material charge to the exact parent's field solve. It is never a
        # checkpoint, background charge, new accounting anchor or state rebase.
        return self.parent_layout(p)._replace(
            extracellular_amount_reference=p.extracellular_amount_reference + signal.dose_fmol,
            initial_outside_charge_C=p.initial_outside_charge_C + signal.charge_C,
        )

    def physical_state(self, state, p, *, xp=jnp):
        value = self.parent_state(state)
        s = signal_values(state, p, xp=xp)
        return value._replace(
            extracellular_amount_increment=value.extracellular_amount_increment + s.dose_fmol,
            reservoir_supplied=value.reservoir_supplied + s.dose_fmol,
            electrode_charge_transferred_C=value.electrode_charge_transferred_C - s.charge_C,
            reservoir_work_pJ=value.reservoir_work_pJ + s.electrochemical_work_pJ,
            electrode_work_pJ=value.electrode_work_pJ + s.electrode_work_pJ,
        )

    def physical_amounts(self, state, p):
        xp = np if isinstance(state.phase_clock_s, np.ndarray) else jnp
        return self.base.physical_amounts(
            self.physical_state(state, p, xp=xp), self.parent_layout(p)
        )

    def domain_valid(self, state, p, active, *, xp=jnp):
        if (
            state.phase_clock_s.shape != (1,)
            or state.reservoir_chemical_work_pJ.shape != p.reservoir.shape
        ):
            return xp.asarray(False)
        s = signal_values(state, p, xp=xp)
        work = state.reservoir_chemical_work_pJ
        return (
            s.valid
            & self.base.domain_valid(
                self.parent_state(state), self.stage_layout(p, s), active, xp=xp
            )
            & xp.all(xp.isfinite(work))
            & xp.all(xp.where(p.reservoir, True, work == 0))
        )

    def readouts(self, state, control, p, *, xp=jnp):
        s = signal_values(state, p, xp=xp)
        current = self.stage_layout(p, s)
        value = self.parent_state(state)
        if self.active:
            parent = self.base.readouts(value, control, current, xp=xp)
            field, derivative, valid = parent.field, parent.derivative, parent.valid
        else:
            field = self.base.field_values(value, control, current, xp=xp)
            derivative = self.base.derivative_from_field(field, current, xp=xp)
            parent, valid = field, field.converged
        valid &= self.domain_valid(state, p, p.active, xp=xp)
        co = xp.where(
            p.outside_active, current.extracellular_amount_reference / p.extracellular_volume, 1.0
        )
        chemical = (
            1e-3
            * R
            * p.temperature
            * xp.sum(xp.log(co) * field.rates.reservoir_supply_fmol_s, axis=0)
        )
        result = self.STATE_TYPE(*derivative, chemical, xp.ones_like(state.phase_clock_s))
        rates = field.rates._replace(
            outside_rate_fmol_s=field.rates.outside_rate_fmol_s + s.dose_rate_fmol_s,
            reservoir_supply_fmol_s=field.rates.reservoir_supply_fmol_s + s.dose_rate_fmol_s,
            valid=valid,
        )
        physical = field._replace(
            rates=rates,
            electrode_current_A=field.electrode_current_A - s.charge_rate_A,
            reservoir_supply_charge_A=field.reservoir_supply_charge_A + s.charge_rate_A,
            chemical_energy_rate_pJ_s=field.chemical_energy_rate_pJ_s
            + xp.sum(s.chemical_power_pJ_s),
            reservoir_power_pJ_s=field.reservoir_power_pJ_s + xp.sum(s.electrochemical_power_pJ_s),
            electrode_power_pJ_s=field.electrode_power_pJ_s + xp.sum(s.electrode_power_pJ_s),
            converged=valid,
        )
        return Values(physical, result, s, parent, valid)

    def field_values(self, state, control, p, *, xp=jnp):
        return self.readouts(state, control, p, xp=xp).field

    def rhs(self, state, control, p, active, *, xp=jnp):
        value = self.readouts(state, control, p, xp=xp)
        return self.STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))

    def control_domain_valid(self, state, control, p, active, *, xp=jnp):
        valid = self.domain_valid(state, p, active, xp=xp)
        if xp is np:
            if not valid:
                return np.asarray(False)
            try:
                return self.readouts(state, control, p, xp=np).valid
            except np.linalg.LinAlgError:
                return np.asarray(False)
        return jax.lax.cond(
            valid, lambda: self.readouts(state, control, p).valid, lambda: jnp.asarray(False)
        )

    def check_definition(self, spec):
        from cells.core.schedule import control_values

        state, p = self.initial_values(spec)
        clocks = {0.0, spec.experiment.end_time, *(v.time for v in spec.experiment.changes)}
        for event in spec.model.bath_events:
            clocks.update((event.on_s, (event.on_s + event.off_s) / 2, event.off_s))
        controls = control_values(self.schema.owner_spec(spec), sorted(clocks))
        for i, time in enumerate(sorted(clocks)):
            row = state._replace(phase_clock_s=np.asarray([time]))
            u = type(controls)(*(v[i] for v in controls))
            if not self.control_domain_valid(row, u, p, p.active, xp=np):
                raise ConfigError(
                    "Bath stage/control violates its exact parent or controller domain"
                )

    def check_steps(self, spec, steps, controls):
        binding.check_ramp_steps(spec, steps)
        self.base.check_steps(self.schema.owner_spec(spec), steps, controls)

    def balances(self, state, p):
        s = signal_values(state, p, xp=np)
        physical = self.physical_state(state, p, xp=np)
        result = self.base.balances(physical, self.parent_layout(p))
        # A reservoir may now carry explicitly injected ionic charge. Its held
        # electrode supplies the opposite charge, in addition to capacitor work.
        result["electrode"] += s.charge_C
        supplied_charge = CHARGE_PER_FMOL * np.sum(p.valence * physical.reservoir_supplied, axis=0)
        result["reservoir_work"] = (
            physical.reservoir_work_pJ
            - state.reservoir_chemical_work_pJ
            - s.chemical_work_pJ
            - 1e12 * p.boundary_V * supplied_charge
        )
        return result

    def check_values(self, state, spec):
        _, p = self.initial_values(spec)
        if state.phase_clock_s.ndim not in (1, 2) or state.phase_clock_s.shape[-1:] != (1,):
            raise NumericalError("Bath clock has incompatible shape")
        rows = (
            [state]
            if state.phase_clock_s.ndim == 1
            else [self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.phase_clock_s))]
        )
        names = (
            "balance_error_fmol",
            "extracellular_balance_error_fmol",
            "global_balance_error_fmol",
            "capacitor_charge_error_C",
            "electrode_charge_error_C",
            "global_charge_error_C",
            "energy_balance_error_pJ",
            "reservoir_work_error_pJ",
            "electrode_work_error_pJ",
        )
        if self.active:
            names += ("metabolic_work_error_pJ",)
        diagnostics = {"max_" + k: 0.0 for k in names}
        tol = np.asarray(spec.execution.material_balance_atol_fmol)
        for row in rows:
            if not self.domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Invalid bath state, physical owner, ledger or clock; no repair"
                )
            physical = self.physical_state(row, p, xp=np)
            q = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(physical, p, xp=np)
            limits = (
                tol[:, None],
                tol[:, None],
                tol,
                surface_field.CHARGE_ATOL_C + surface_field.CHARGE_RTOL * np.abs(q),
                surface_field.CHARGE_ATOL_C
                + surface_field.CHARGE_RTOL * np.abs(physical.electrode_charge_transferred_C),
                3e-25,
                passive.ENERGY_ATOL_PJ,
                3e-12,
                3e-12,
            )
            if self.active:
                limits += (3e-12,)
            for (name, value), key, bound in zip(
                self.balances(row, p).items(), diagnostics, limits, strict=True
            ):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError("Bath physical accounting failed: " + name)
                diagnostics[key] = max(diagnostics[key], float(np.max(np.abs(value), initial=0)))
        for name in (k for k in self.base.STATE_AXES if k.endswith("_dissipated_energy_pJ")):
            value = np.asarray(getattr(state, name))
            if np.min(value, initial=0) < -1e-12 or (
                state.phase_clock_s.ndim == 2 and np.min(np.diff(value, axis=0), initial=0) < -1e-12
            ):
                raise NumericalError("Bath parent dissipation cannot be negative or decrease")
        if (
            state.phase_clock_s.ndim == 2
            and np.min(np.diff(state.phase_clock_s[:, 0]), initial=0) < -p.phase_clock_atol_s
        ):
            raise NumericalError("Bath clock cannot decrease")
        return diagnostics

    def check_checkpoint(self, spec, checkpoint):
        clock = np.asarray(checkpoint.state.phase_clock_s)
        atol = 64 * np.finfo(float).eps * max(spec.experiment.end_time, spec.execution.dt)
        if (
            clock.shape != (1,)
            or not np.isfinite(clock).all()
            or abs(clock[0] - checkpoint.time) > atol
        ):
            raise ConfigError("Bath phase clock differs from accepted checkpoint time")

    def observe_history(self, times, history, layout, requested, spec):
        self.check_values(history, spec)
        p = self.LAYOUT_TYPE(*(np.asarray(v) for v in layout))
        records = []
        for time in requested:
            indices = np.flatnonzero(np.asarray(times) == time)
            if len(indices) != 1:
                raise ConfigError("Bath observations require accepted boundaries")
            i = int(indices[0])
            state = self.STATE_TYPE(*(np.asarray(v[i]) for v in history))
            if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
                raise ConfigError("Observed bath clock differs from accepted time")
            signal = signal_values(state, p, xp=np)
            observed = self.base.observe_history(
                np.asarray([time]),
                self.base.STATE_TYPE(*(v[None] for v in self.parent_state(state))),
                self.stage_layout(p, signal),
                [time],
                self.schema.owner_spec(spec),
            )
            values = {k: getattr(observed, k)[0] for k in self.base.OBSERVATION_FIELDS}
            values.update(
                maintenance_reservoir_supply_fmol_s=values["reservoir_supply_fmol_s"],
                maintenance_electrode_current_A=values["electrode_current_A"],
                maintenance_reservoir_power_pJ_s=values["reservoir_power_pJ_s"],
                maintenance_electrode_power_pJ_s=values["electrode_power_pJ_s"],
            )
            values["reservoir_supply_fmol_s"] = (
                values["reservoir_supply_fmol_s"] + signal.dose_rate_fmol_s
            )
            values["electrode_current_A"] = values["electrode_current_A"] - signal.charge_rate_A
            values["reservoir_power_pJ_s"] = values["reservoir_power_pJ_s"] + np.sum(
                signal.electrochemical_power_pJ_s
            )
            values["electrode_power_pJ_s"] = values["electrode_power_pJ_s"] + np.sum(
                signal.electrode_power_pJ_s
            )
            physical = self.physical_state(state, p, xp=np)
            values.update(
                reservoir_chemical_work_pJ=state.reservoir_chemical_work_pJ,
                phase_clock_s=state.phase_clock_s,
                bath_pulse=signal.pulse,
                bath_dose_fmol=signal.dose_fmol,
                bath_dose_rate_fmol_s=signal.dose_rate_fmol_s,
                bath_charge_C=signal.charge_C,
                bath_chemical_work_pJ=signal.chemical_work_pJ,
                bath_electrochemical_work_pJ=signal.electrochemical_work_pJ,
                bath_electrode_work_pJ=signal.electrode_work_pJ,
                physical_reservoir_chemical_work_pJ=state.reservoir_chemical_work_pJ
                + signal.chemical_work_pJ,
            )
            for name in (
                "extracellular_amount_increment",
                "reservoir_supplied",
                "electrode_charge_transferred_C",
                "reservoir_work_pJ",
                "electrode_work_pJ",
            ):
                values["physical_" + name] = getattr(physical, name)
            records.append(tuple(values[k] for k in self.OBSERVATION_FIELDS))
        if records:
            return self.Observations(*(np.stack(v) for v in zip(*records, strict=True)))
        sample = self.observe_history(
            np.asarray(times)[:1],
            self.STATE_TYPE(*(v[:1] for v in history)),
            p,
            np.asarray(times)[:1],
            spec,
        )
        return self.Observations(
            *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
        )

    def ensemble_voltage(self, state, layout, spec, time):
        from cells.core.schedule import control_values

        controls = control_values(self.schema.owner_spec(spec), [time])
        control = type(controls)(*(v[0] for v in controls))
        value = self.readouts(state, control, layout, xp=np)
        if not value.valid:
            raise NumericalError("Bath endpoint field invalid")
        return value.field.rates.membrane_voltage_V[layout.membrane_active]

    def batch_signature(self, model):
        return (
            self.base.batch_signature(model),
            model.bath_site_ids,
            tuple(v.kind for v in model.bath_events),
        )

    def working_size(self, spec):
        return (
            self.base.working_size(self.schema.owner_spec(spec))
            + (128 * len(spec.model.species_ids) + 512) * spec.execution.extracellular_capacity
        )

    def summarize(self, history, diagnostics, spec):
        return self.base.summarize(
            self.parent_state(history), diagnostics, self.schema.owner_spec(spec)
        ) | dict(
            model=self.schema.MODEL_ID,
            boundary="explicit concentration and fixed-voltage ideal-reservoir controllers",
            state_fields=list(self.STATE_TYPE._fields),
            parent_state_semantics=(
                "transport contributions; physical_* readouts add programmed dose/work"
            ),
            initial_controller_operation=self.initial_operation(spec),
            reservoir_work_law="integrated variable chemical work plus electrical supply work",
        )
