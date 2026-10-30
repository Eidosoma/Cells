"""Open admission and external closure around exact complete owned rate laws.

Actual reservoir flags always reach the field solve. Closed-only parsing/loss
admission is never used for an open world. No plasma, ER, fuel, gate, amount or
history is replaced by an auxiliary coefficient/maintained-state surrogate.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.models import open_calcium_admission as admission
from cells.models import open_calcium_reservoirs as closure
from cells.models import surface_calcium as calcium
from cells.models import surface_calcium_energy as fuel
from cells.processes import finite_energy as energy

EXTRA_LAYOUT = ("open_ionic_moiety_ceiling_fmol", "open_reservoir_world")
EXTRA_OBSERVATIONS = ("ionic_moiety_fmol", "ionic_moiety_ceiling_fmol", "ideal_reservoir_active")


class Values(NamedTuple):
    field: object
    derivative: object
    parent: object
    closure: object
    ionic_moiety_fmol: object
    valid: object


class Adapter:
    def __init__(self, base, schema, name, *, finite_fuel):
        self.base, self.schema, self.finite_fuel = base, schema, finite_fuel
        self.STATE_TYPE = NamedTuple(name + "State", [(k, object) for k in base.STATE_AXES])
        self.LAYOUT_TYPE = NamedTuple(
            name + "Layout", [(k, object) for k in (*base.LAYOUT_TYPE._fields, *EXTRA_LAYOUT)]
        )
        self.OBSERVATION_FIELDS = (*base.OBSERVATION_FIELDS, *EXTRA_OBSERVATIONS)
        self.Observations = make_dataclass(
            name + "Observations", [(k, np.ndarray) for k in self.OBSERVATION_FIELDS], frozen=True
        )

    def parent_state(self, state):
        return self.base.STATE_TYPE(*(getattr(state, key) for key in self.base.STATE_AXES))

    def parent_layout(self, p):
        return self.base.LAYOUT_TYPE(*(getattr(p, key) for key in self.base.LAYOUT_TYPE._fields))

    def initial_values(self, spec):
        zero, p = self.base.initial_values(self.schema.equation_spec(spec))
        ceiling = spec.model.ionic_moiety_ceiling_fmol
        extra = dict(
            open_reservoir_world=np.asarray(np.any(p.reservoir)),
            open_ionic_moiety_ceiling_fmol=np.zeros(len(spec.model.species_ids))
            if ceiling is None
            else np.asarray(ceiling, dtype=float),
        )
        return self.STATE_TYPE(*zero), self.LAYOUT_TYPE(**(p._asdict() | extra))

    def physical_amounts(self, state, p):
        return self.base.physical_amounts(self.parent_state(state), self.parent_layout(p))

    def domain_valid(self, state, p, active, *, xp=jnp):
        value = self.parent_state(state)
        valid = self.base.domain_valid(value, self.parent_layout(p), active, xp=xp)
        total = admission.ionic_moieties(value, p, xp=xp)
        valid &= xp.all(xp.isfinite(total))
        valid &= p.open_reservoir_world == xp.any(p.reservoir)
        return valid & xp.where(
            p.open_reservoir_world,
            xp.all(
                xp.isfinite(p.open_ionic_moiety_ceiling_fmol)
                & (p.open_ionic_moiety_ceiling_fmol > 0)
                & (total <= p.open_ionic_moiety_ceiling_fmol)
            ),
            True,
        )

    def readouts(self, state, control, p, *, xp=jnp):
        value, physical = self.parent_state(state), self.parent_layout(p)
        raw = self.base.readouts(value, control, physical, xp=xp)
        return self.complete_parent_readouts(state, p, raw, xp=xp)

    def complete_parent_readouts(self, state, p, raw, *, xp=jnp):
        """Close a complete parent readout without recomputing its physics."""
        if (
            type(state) is not self.STATE_TYPE
            or type(p) is not self.LAYOUT_TYPE
            or type(raw) is not (fuel.Values if self.finite_fuel else calcium.Values)
        ):
            raise ValueError(
                "Open reservoir completion requires exact family state/layout/readouts"
            )
        value, physical = self.parent_state(state), self.parent_layout(p)
        if self.finite_fuel:
            internal = xp.sum(
                energy.chemical_power_pJ_s(raw.exchange.amount_fmol_s, raw.energy, xp=xp)
            )
            external = xp.sum(raw.derivative.regeneration_supplied_work_pJ)
        else:
            internal = xp.asarray(0.0)
            external = sum(
                xp.sum(getattr(raw.derivative, key))
                for key in ("metabolic_work_pJ", "plasma_metabolic_work_pJ", "er_metabolic_work_pJ")
            )
        complete = closure.close(
            value,
            physical,
            raw,
            internal_chemical_power_pJ_s=internal,
            external_chemical_power_pJ_s=external,
            xp=xp,
        )
        valid = complete.valid & self.domain_valid(state, p, p.active, xp=xp)
        field = complete.field._replace(
            converged=valid, rates=complete.field.rates._replace(valid=valid)
        )
        return Values(
            field,
            self.STATE_TYPE(*complete.derivative),
            raw,
            complete,
            admission.ionic_moieties(value, p, xp=xp),
            valid,
        )

    def field_values(self, state, control, p, *, xp=jnp):
        return self.readouts(state, control, p, xp=xp).field

    def rhs(self, state, control, p, active, *, xp=jnp):
        value = self.readouts(state, control, p, xp=xp)
        return self.STATE_TYPE(*(xp.where(value.valid, row, xp.nan) for row in value.derivative))

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

    def loss_bound(self, spec):
        actual = self.schema.equation_spec(spec)
        ceiling = spec.model.ionic_moiety_ceiling_fmol
        if ceiling is None:
            return calcium.loss_bound(
                self.base.bounded_prior_spec(actual) if self.finite_fuel else actual
            )
        return admission.loss_bound(
            actual, ceiling, fuel_runtime=self.base if self.finite_fuel else None
        )

    def check_definition(self, spec):
        from cells.core.schedule import control_values

        actual = self.schema.equation_spec(spec)
        if not any(row.reservoir for row in spec.model.extracellular):
            return self.base.check_definition(actual)
        state, p = self.initial_values(spec)
        if not self.domain_valid(state, p, p.active, xp=np):
            raise ConfigError("Open ionic-moiety ceilings do not admit the actual initial state")
        controls = control_values(actual, [row.time for row in actual.experiment.changes])
        for i in range(len(actual.experiment.changes)):
            control = type(controls)(*(v[i] for v in controls))
            if not self.control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError(
                    "Open owned calcium/fuel violates an actual-control physical domain"
                )
        self.loss_bound(spec)

    def check_steps(self, spec, steps, controls):
        actual = self.schema.equation_spec(spec)
        if spec.model.ionic_moiety_ceiling_fmol is None:
            return self.base.check_steps(actual, steps, controls)
        steps = np.asarray(steps, dtype=float)
        if steps.ndim != 1 or not np.isfinite(steps).all() or np.any(steps < 0):
            raise ConfigError("Open calcium steps require finite nonnegative values")
        admission.check_steps(actual, steps, controls, self.loss_bound(spec))
        if self.finite_fuel:
            from cells.core.schedule import control_values

            state, p = self.initial_values(spec)
            amount = np.where(p.active, self.base.energy_amounts(state, p), 1.0)
            table = control_values(actual, [row.time for row in actual.experiment.changes])
            for i in range(len(actual.experiment.changes)):
                value = self.readouts(state, type(table)(*(v[i] for v in table)), p, xp=np)
                exchange = value.parent.exchange
                gross = exchange.gross_hydrolysis_fmol_s + exchange.gross_synthesis_fmol_s
                fraction = np.max(
                    np.where(p.active, gross / np.min(amount, axis=0), 0.0), initial=0
                )
                if (
                    not np.isfinite(fraction)
                    or np.max(steps, initial=0) * fraction > fuel.MAX_INITIAL_POOL_CHANGE_PER_STEP
                ):
                    raise ConfigError(
                        "Open finite-fuel initial gross turnover requires a smaller step"
                    )

    def balances(self, state, p):
        return self.base.balances(self.parent_state(state), self.parent_layout(p))

    def check_values(self, state, spec):
        # Static reservoirs retain the exact parent's full per-owner material,
        # ER/plasma/fuel work, capacitor, charge and chemical-ledger checks.
        diagnostics = self.base.check_values(
            self.parent_state(state), self.schema.equation_spec(spec)
        )
        _, p = self.initial_values(spec)
        rows = (
            [state]
            if state.amount_increment.ndim == 2
            else [
                self.STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))
            ]
        )
        fraction = 0.0
        for row in rows:
            if not self.domain_valid(row, p, p.active, xp=np):
                raise NumericalError(
                    "Open ionic-moiety domain exceeded; no clamping or history repair"
                )
            if p.open_reservoir_world:
                fraction = max(
                    fraction,
                    float(
                        np.max(
                            admission.ionic_moieties(row, p, xp=np)
                            / p.open_ionic_moiety_ceiling_fmol
                        )
                    ),
                )
        diagnostics["max_open_ionic_moiety_fraction"] = fraction
        return diagnostics

    def batch_signature(self, model):
        return self.base.batch_signature(model)

    def working_size(self, spec):
        return self.base.working_size(self.schema.equation_spec(spec)) + 64 * len(
            spec.model.species_ids
        )

    def observe_history(self, times, history, layout, requested, spec):
        from cells.core.schedule import control_values

        self.check_values(history, spec)
        p = self.LAYOUT_TYPE(*(np.asarray(v) for v in layout))
        actual = self.schema.equation_spec(spec)
        controls = control_values(actual, requested)
        records = []
        for j, time in enumerate(requested):
            matches = np.flatnonzero(np.asarray(times) == time)
            if len(matches) != 1:
                raise ConfigError("Open calcium observations require accepted boundaries")
            i = int(matches[0])
            state = self.STATE_TYPE(*(np.asarray(v[i]) for v in history))
            parent = self.parent_state(state)
            observed = self.base.observe_history(
                np.asarray([time]),
                self.base.STATE_TYPE(*(v[None] for v in parent)),
                self.parent_layout(p),
                [time],
                actual,
            )
            value = self.readouts(state, type(controls)(*(v[j] for v in controls)), p, xp=np)
            if not value.valid:
                raise NumericalError("Open calcium observation violates its actual physical domain")
            fields = {key: getattr(observed, key)[0] for key in self.base.OBSERVATION_FIELDS}
            fields["reservoir_supply_fmol_s"] = value.field.rates.reservoir_supply_fmol_s
            for key in ("electrode_current_A", "electrode_charge_C"):
                fields[key] = getattr(value.field, key)
            for key in ("reservoir_power_pJ_s", "electrode_power_pJ_s", "energy_balance_pJ_s"):
                fields[key] = np.atleast_1d(getattr(value.field, key))
            fields.update(
                ionic_moiety_fmol=value.ionic_moiety_fmol,
                ionic_moiety_ceiling_fmol=p.open_ionic_moiety_ceiling_fmol,
                ideal_reservoir_active=p.reservoir,
            )
            records.append(tuple(fields[key] for key in self.OBSERVATION_FIELDS))
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

        controls = control_values(self.schema.equation_spec(spec), [time])
        value = self.readouts(state, type(controls)(*(v[0] for v in controls)), layout, xp=np)
        if not value.valid:
            raise NumericalError("Open calcium endpoint violates its actual physical domain")
        return value.field.rates.membrane_voltage_V[layout.membrane_active]

    def summarize(self, history, diagnostics, spec):
        open_world = any(row.reservoir for row in spec.model.extracellular)
        return self.base.summarize(
            self.parent_state(history), diagnostics, self.schema.equation_spec(spec)
        ) | dict(
            model=self.schema.MODEL_ID,
            boundary=(
                "static ideal chemical/voltage reservoirs with complete plasma/ER/fuel accounting"
            )
            if open_world
            else "closed finite exterior; explicit empty-reservoir reduction",
            reservoir_closure_law=closure.LAW_ID,
            ionic_moiety_domain=(
                "explicit hard ceilings in fmol; not conserved open-system pools"
                if open_world
                else "original closed conservation; open ceilings inactive"
            ),
            ionic_moiety_ceiling_fmol=spec.model.ionic_moiety_ceiling_fmol,
            scope=(
                "synthetic static open-exterior coupling; no trajectory or biological parity claim"
            ),
            claim_scope=(
                "Synthetic static open-exterior electrical/chemical coupling; "
                "no whole-BETSE trajectory or biological calibration"
            ),
        )
