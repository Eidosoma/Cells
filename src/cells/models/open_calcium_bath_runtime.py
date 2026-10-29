"""Full calcium/fuel bath composition with original physical accounting.

The qualified bath controller supplies an analytic dose and compensated charge.
Every saved calcium/fuel field remains an actual transport/history contribution.
Physical inventories and external ledgers add the declared controller operation;
fixed background charge and all original chemical/fuel anchors stay unchanged.
"""

from itertools import product

import numpy as np

from cells.core import open_calcium_bath_binding as binding
from cells.core import surface_bath_events_binding as bath
from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import surface_bath_events as controller
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.models import surface_tissue as passive
from cells.numerics import surface_field
from cells.processes.electrochemistry import CHARGE_PER_FMOL

jnp = controller.jnp
signal_values = controller.signal_values


class Adapter(controller.Adapter):
    def __init__(self, base, schema, name, *, finite_fuel):
        super().__init__(base, schema, name, active=True)
        self.finite_fuel = finite_fuel

    def check_definition(self, spec):
        state, p = self.initial_values(spec)
        binding.check_initial_envelope(spec, self.parent_state(state), p)
        super().check_definition(spec)

    def check_steps(self, spec, steps, controls):
        bath.check_ramp_steps(spec, steps)
        self.base.check_steps(self.schema.owner_spec(spec), steps, controls)
        if not self.finite_fuel:
            return
        bound = self.initial_pool_turnover_bound(spec)
        if (
            np.max(steps, initial=0) * bound["maximum_fraction_rate_s_inv"]
            > fuel.MAX_INITIAL_POOL_CHANGE_PER_STEP
        ):
            raise ConfigError("Bath initial-pool gross turnover requires a smaller RK4 step")

    def initial_pool_turnover_bound(self, spec):
        # Retain the parent's actual-initial-pool gross-turnover test and also
        # test all independent pulse-box corners at every held control. This
        # conservative admission view changes no saved state or physical law.
        from cells.core.schedule import control_values

        if not self.finite_fuel:
            raise ConfigError("Initial pool turnover belongs to the finite-fuel bath owner")
        state, p = self.initial_values(spec)
        amount = np.where(p.active, fuel.energy_amounts(self.parent_state(state), p), 1.0)
        table = control_values(
            self.schema.owner_spec(spec), [row.time for row in spec.experiment.changes]
        )
        enabled = np.flatnonzero(np.any(p.bath_amount_coefficient_fmol != 0, axis=(1, 2)))
        worst = dict(
            maximum_fraction_rate_s_inv=0.0,
            worst_pulse_corner=[0.0] * 3,
            worst_held_control_time_s=0.0,
        )
        for bits in product((0.0, 1.0), repeat=len(enabled)):
            pulse = np.zeros(3)
            pulse[enabled] = bits
            dose = np.sum(p.bath_amount_coefficient_fmol * pulse[:, None, None], axis=0)
            charge = CHARGE_PER_FMOL * np.sum(p.valence * dose, axis=0)
            current = self.parent_layout(p)._replace(
                extracellular_amount_reference=p.extracellular_amount_reference + dose,
                initial_outside_charge_C=p.initial_outside_charge_C + charge,
            )
            for i in range(len(spec.experiment.changes)):
                u = type(table)(*(row[i] for row in table))
                value = self.base.readouts(self.parent_state(state), u, current, xp=np)
                if not value.valid:
                    raise ConfigError(
                        "Bath pulse-box corner violates the original live-fuel domain"
                    )
                exchange = value.parent.exchange
                gross = exchange.gross_hydrolysis_fmol_s + exchange.gross_synthesis_fmol_s
                fraction = np.max(
                    np.where(p.active, gross / np.min(amount, axis=0), 0.0), initial=0
                )
                if not np.isfinite(fraction):
                    raise ConfigError("Nonfinite bath initial-pool gross turnover bound")
                if fraction > worst["maximum_fraction_rate_s_inv"]:
                    worst.update(
                        maximum_fraction_rate_s_inv=float(fraction),
                        worst_pulse_corner=pulse.tolist(),
                        worst_held_control_time_s=spec.experiment.changes[i].time,
                    )
        return worst | dict(
            corners=2 ** len(enabled),
            held_control_states=len(spec.experiment.changes),
            actual_initial_amount_fmol=amount[:, p.active].tolist(),
            scope="actual-initial-pool pulse-box admission; all inherited guards remain",
        )

    def balances(self, state, p):
        """Original full owner budgets plus reversible controller identities.

        On targeted pinned nodes, dose enters outside inventory and supplied
        material equally. Its ionic charge and compensating electrode charge
        cancel in the physical charge residual. The program's mixing free
        energy equals its net external work. Form these terms separately to
        preserve tiny transport residuals beside a large programmed operation.
        """
        value = self.parent_state(state)
        result = self.base.balances(value, self.parent_layout(p))
        signal = signal_values(state, p, xp=np)
        supplied_charge = CHARGE_PER_FMOL * np.sum(p.valence * value.reservoir_supplied, axis=0)
        result["reservoir_work"] = (
            value.reservoir_work_pJ
            - state.reservoir_chemical_work_pJ
            - 1e12 * p.boundary_V * supplied_charge
        )
        program = (
            signal.chemical_work_pJ - signal.electrochemical_work_pJ - signal.electrode_work_pJ
        )
        result["energy"] += np.sum(program)
        result["program_energy"] = program
        return result

    def check_values(self, state, spec):
        _, p = self.initial_values(spec)
        if state.phase_clock_s.ndim not in (1, 2) or state.phase_clock_s.shape[-1:] != (1,):
            raise NumericalError("Owned-calcium bath clock has incompatible shape")
        rows = (
            [state]
            if state.phase_clock_s.ndim == 1
            else [self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.phase_clock_s))]
        )
        diagnostics = {}
        for row in rows:
            if not self.domain_valid(row, p, p.active, xp=np):
                raise NumericalError("Invalid complete calcium/fuel bath domain; no state repair")
            charge = np.r_[
                p.initial_cell_charge_C, p.initial_outside_charge_C
            ] + passive.charge_increment(self.parent_state(row), p, xp=np)
            tolerance = np.asarray(spec.execution.material_balance_atol_fmol)
            limits = dict(
                local=tolerance[:, None],
                outside=tolerance[:, None],
                total=tolerance,
                charge=surface_field.CHARGE_ATOL_C + surface_field.CHARGE_RTOL * np.abs(charge),
                electrode=surface_field.CHARGE_ATOL_C,
                global_charge=3e-25,
                energy=calcium.ENERGY_ATOL_PJ,
                reservoir_work=3e-12,
                electrode_work=3e-12,
                metabolic_work=3e-12,
                plasma_metabolic_work=3e-12,
                er_metabolic_work=3e-12,
                chemical_ledger=calcium.chemistry.ROUND_ATOL,
                ownership=calcium.chemistry.ROUND_ATOL,
                pool_material=fuel.POOL_MATERIAL_ATOL_FMOL,
                adenylate=fuel.POOL_MATERIAL_ATOL_FMOL,
                phosphorus=fuel.POOL_MATERIAL_ATOL_FMOL,
                pool_energy=fuel.ENERGY_ATOL_PJ,
                regeneration_work=3e-12,
                program_energy=3e-12,
            )
            for key, value in self.balances(row, p).items():
                if not np.isfinite(value).all() or np.any(np.abs(value) > limits[key]):
                    raise NumericalError("Complete calcium/fuel bath accounting failed: " + key)
                name = "max_" + key + "_error"
                diagnostics[name] = max(
                    diagnostics.get(name, 0.0), float(np.max(np.abs(value), initial=0))
                )
        for key in (
            name for name in self.base.STATE_AXES if name.endswith("_dissipated_energy_pJ")
        ):
            value = np.asarray(getattr(state, key))
            if (
                np.min(value, initial=0) < -calcium.chemistry.ROUND_ATOL
                or state.phase_clock_s.ndim == 2
                and np.min(np.diff(value, axis=0), initial=0) < -calcium.chemistry.ROUND_ATOL
            ):
                raise NumericalError(
                    "Owned-calcium bath dissipation cannot be negative or decrease"
                )
        if (
            state.phase_clock_s.ndim == 2
            and np.min(np.diff(state.phase_clock_s[:, 0]), initial=0) < -p.phase_clock_atol_s
        ):
            raise NumericalError("Owned-calcium bath clock cannot decrease")
        return diagnostics

    def observe_history(self, times, history, layout, requested, spec):
        from cells.core.schedule import control_values

        self.check_values(history, spec)
        p = self.LAYOUT_TYPE(*(np.asarray(value) for value in layout))
        owner = self.schema.owner_spec(spec)
        equation = self.schema.parent.equation_spec(owner)
        controls = control_values(owner, requested)
        records = []
        for j, time in enumerate(requested):
            indices = np.flatnonzero(np.asarray(times) == time)
            if len(indices) != 1:
                raise ConfigError("Owned-calcium bath observations require accepted boundaries")
            i = int(indices[0])
            state = self.STATE_TYPE(*(np.asarray(value[i]) for value in history))
            if abs(state.phase_clock_s[0] - time) > p.phase_clock_atol_s:
                raise ConfigError("Owned-calcium bath clock differs from observed time")
            u = type(controls)(*(value[j] for value in controls))
            value = self.readouts(state, u, p, xp=np)
            if not value.valid:
                raise NumericalError(
                    "Owned-calcium bath observer violates its complete stage domain"
                )
            signal, raw = value.signal, self.parent_state(state)
            current = self.stage_layout(p, signal)
            # Complete original Ca/ER/fuel observations are composed from the
            # actual current layout and pools. Full validation happened above;
            # no static constant-mu accounting check is misapplied to a bath.
            original = self.base.base
            observed = original.observe_history(
                np.asarray([time]),
                original.STATE_TYPE(*(v[None] for v in self.base.parent_state(raw))),
                self.base.parent_layout(current),
                [time],
                equation,
            )
            fields = {key: getattr(observed, key)[0] for key in original.OBSERVATION_FIELDS}
            fields.update(
                ionic_moiety_fmol=value.parent.ionic_moiety_fmol,
                ionic_moiety_ceiling_fmol=p.open_ionic_moiety_ceiling_fmol,
                ideal_reservoir_active=p.reservoir,
            )
            fields["reservoir_supply_fmol_s"] = value.field.rates.reservoir_supply_fmol_s
            for key in ("electrode_current_A", "electrode_charge_C"):
                fields[key] = getattr(value.field, key)
            for key in ("reservoir_power_pJ_s", "electrode_power_pJ_s", "energy_balance_pJ_s"):
                fields[key] = np.atleast_1d(getattr(value.field, key))
            fields.update(
                maintenance_reservoir_supply_fmol_s=value.parent.field.rates.reservoir_supply_fmol_s,
                maintenance_electrode_current_A=value.parent.field.electrode_current_A,
                maintenance_reservoir_power_pJ_s=np.atleast_1d(
                    value.parent.field.reservoir_power_pJ_s
                ),
                maintenance_electrode_power_pJ_s=np.atleast_1d(
                    value.parent.field.electrode_power_pJ_s
                ),
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
            physical = self.physical_state(state, p, xp=np)
            for key in (
                "extracellular_amount_increment",
                "reservoir_supplied",
                "electrode_charge_transferred_C",
                "reservoir_work_pJ",
                "electrode_work_pJ",
            ):
                fields["physical_" + key] = getattr(physical, key)
            records.append(tuple(fields[key] for key in self.OBSERVATION_FIELDS))
        if records:
            return self.Observations(*(np.stack(value) for value in zip(*records, strict=True)))
        sample = self.observe_history(
            np.asarray(times)[:1],
            self.STATE_TYPE(*(v[:1] for v in history)),
            p,
            np.asarray(times)[:1],
            spec,
        )
        return self.Observations(
            *(np.empty((0, *value.shape[1:]), dtype=value.dtype) for value in vars(sample).values())
        )

    def summarize(self, history, diagnostics, spec):
        return super().summarize(history, diagnostics, spec) | dict(
            boundary="scheduled ideal chemical baths with held voltage and full Ca/ER/fuel owners",
            exterior_policy=binding.EXTERIOR_POLICY,
            ionic_moiety_domain=(
                "actual prescribed dose plus transport; hard ceilings at every stage"
            ),
            scope=(
                "synthetic bath/full56 calcium/fuel coupling; "
                "no biological or native trajectory claim"
            ),
        )
