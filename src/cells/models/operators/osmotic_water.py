"""Operator ideal_osmosis_linear_compliance_water@1: osmotic water and compliant volumes.

The law, its Heun half-steps at frozen amounts and its ledgers are those of
resolved_pump_water@1 (models/surface_pump_water.py, docs/PUMP_WATER_MODEL.md),
called, never copied: Q = 1e15 A Lp a (psi_cell - psi_outside) on every membrane
patch, psi = P - Pi with ideal van 't Hoff Pi and a linear compliance P; a held
bath keeps its volume and composition and books the water it exchanges as supply
with its work.

Contract (models/operators/contract.py):
* owned state: the volume increments, water transfers, water heat, bath supply and
  bath water work (resolved_pump_water@1's water fields);
* view: the current cell and outside volumes as @3's ``volume`` and
  ``extracellular_volume``; the view follows the split, so @3's domain is evaluated
  at the current volumes and re-checked at the step end;
* parts: a split process (Heun half-steps, heun_frozen_amount_water@1); under RK4
  its rates join the coupled right-hand side;
* ledgers: its four water ledgers (cell, outside and total water, bath work) with
  their floors and rounding allowances, and the dilution, elastic, heat and bath
  work terms of the energy ledger;
* refusal: a volume at its bound at any water stage or step end, dt x the water
  relaxation rate above 0.05, a water availability outside [0, 1], and @3's
  explicit bounds at the declared minimum volumes.
"""

from bisect import bisect_right
from dataclasses import asdict, replace

import numpy as np

from cells.core import surface_pump_spec as first_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core import surface_pump_water_spec as water_spec
from cells.core.specs import ConfigError
from cells.models import surface_pump as first
from cells.models import surface_pump_v2 as second
from cells.models import surface_pump_water as w1
from cells.models.operators.contract import Operator
from cells.numerics import osmotic_water as law

LAW_ID = law.LAW_ID


def frozen_spec(spec, declaration, schedule):
    """The resolved_pump_water@1 definition of this operator on the inner model."""
    m, e = spec.model, spec.experiment
    model = water_spec.SurfacePumpWaterModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        water=declaration,
    )
    experiment = water_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        water=schedule,
    )
    return replace(spec, model=model, experiment=experiment)


class OsmoticWater(Operator):
    LAW_ID = LAW_ID
    STEP_ID = w1.WATER_STEP_ID
    SPLIT = True
    RK4 = "coupled"
    STATE_AXES = w1.WATER_STATE_AXES
    HEAT_FIELDS = ("water_dissipated_energy_pJ",)
    WORK_FIELDS = ("bath_water_work_pJ",)
    LAYOUT_FIELDS = w1.WATER_LAYOUT_FIELDS
    CONTROL_FIELDS = ("water",)
    EXPERIMENT_KEYS = ("water_controls",)
    VIEW_FIELDS = ("volume", "extracellular_volume")
    VIEW_FOLLOWS_SPLIT = True
    LEDGERS = w1.WATER_LEDGERS
    LEDGER_DIAGNOSTICS = w1.WATER_DIAGNOSTICS
    LEDGER_MESSAGE = w1.WATER_LEDGER_MESSAGE
    READOUT = "water"
    READOUT_COLUMNS = w1.WATER_READOUTS
    FINITE_RATES = True

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return water_spec.parse_water(raw, base)

    def to_dict(self, declaration, base):
        w = declaration
        if (
            type(w) is not water_spec.Water
            or any(type(p) is not water_spec.WaterCompartment for p in w.compartments)
            or any(type(p) is not water_spec.WaterBath for p in w.baths)
            or any(type(p) is not water_spec.WaterMembrane for p in w.membranes)
        ):
            raise ConfigError("Require explicit immutable water declaration types")
        return dict(
            law=w.law,
            compartments=[asdict(p) for p in w.compartments],
            baths=[asdict(p) for p in w.baths],
            membranes=[asdict(p) for p in w.membranes],
        )

    def parse_schedule(self, raw, base, declaration):
        ids = [p.id for p in base.model.membranes]
        schedules = first_spec._schedules(
            raw["water_controls"], "membrane", ids, base.experiment.end_time
        )
        return tuple(schedules[i] for i in ids)

    def schedule_to_dict(self, schedule, base, declaration):
        return dict(
            water_controls=[
                dict(membrane_id=p.id, schedule=[asdict(c) for c in g])
                for p, g in zip(base.model.membranes, schedule, strict=True)
            ]
        )

    def schedule_times(self, schedule):
        return tuple(c.time for g in schedule for c in g)

    def value_at(self, schedule, time):
        return tuple(g[bisect_right([p.time for p in g], time) - 1].availability for g in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        values = np.asarray(records, dtype=np.float64).reshape(len(records), -1)
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        padded[:, : values.shape[-1]] = values[indices]
        return (padded,)

    def inner_check_spec(self, check_spec, spec, declaration, schedule):
        return check_spec

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        """resolved_pump_water@1's water bounds (models/surface_pump_water.check_steps)."""
        frozen = frozen_spec(spec, declaration, schedule)
        step = np.max(steps, initial=0)
        if spec.execution.solver != "rk4":
            low = ionic_spec.projection(w1.minimum_volume_spec(frozen))
            if step * first.explicit_rate_bound(low) > w1.EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the explicit-rate bound at minimum volumes")
            if step * second.calcium_rate_bound(low) > w1.EXPLICIT_STEP_BOUND:
                raise ConfigError("IMEX step exceeds the calcium pump bound at minimum volumes")
        state, p = w1.initial_values(frozen)
        rate = w1.water_rate(state, p.membrane_active.astype(float), p, xp=np)
        if not np.isfinite(rate) or step * rate > w1.MAX_WATER_RELAXATION_PER_STEP * (
            1 + 16 * np.finfo(float).eps
        ):
            raise ConfigError("Water relaxation requires a smaller step (dt x rate exceeds 0.05)")

    def batch_signature(self, declaration):
        w = declaration
        return (
            w.law,
            tuple(p.compartment_id for p in w.compartments),
            tuple(p.compartment_id for p in w.baths),
        )

    def working_size(self, spec):
        x = spec.execution
        return 2 * (x.capacity + 3 * x.extracellular_capacity + 2 * x.membrane_capacity)

    def summary(self, spec, declaration, schedule, history):
        solver = spec.execution.solver
        return {
            "water_law": declaration.law,
            "water_step": None if solver == "rk4" else self.STEP_ID,
            "water_rk4": "coupled rhs (rk4)",
            "volume_owner_ids": [c.compartment_id for c in declaration.compartments],
            "water_bath_ids": [c.compartment_id for c in declaration.baths],
            "water_routes": "membranes only; no junction or extracellular-face water",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        state, p = w1.initial_values(frozen_spec(spec, declaration, schedule))
        return (
            {k: getattr(state, k) for k in self.STATE_AXES},
            {k: getattr(p, k) for k in self.LAYOUT_FIELDS},
        )

    # ------------------------------------------------------------ step parts

    def view(self, state, p, q, *, xp):
        return dict(
            volume=p.volume + state.volume_increment_pL,
            extracellular_volume=p.extracellular_volume + state.extracellular_volume_increment_pL,
        )

    def half_step(self, state, h, control, p, *, xp):
        return w1.water_step(state, h, control.water, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        return w1.water_control_valid(control.water, p, xp=xp)

    def rates(self, state, control, p, view, *, xp):
        w = w1.water_rates(state, control.water, p, xp=xp)
        rates = dict(
            volume_increment_pL=w.cell,
            extracellular_volume_increment_pL=w.outside,
            water_transferred_pL=w.flow,
            water_dissipated_energy_pJ=w.heat,
            bath_water_supplied_pL=w.supply,
            bath_water_work_pJ=w.work,
        )
        valid = w1.water_domain_valid(state, p, xp=xp)
        valid &= w1.water_control_valid(control.water, p, xp=xp)
        return rates, valid, w1.water_energy_rate(w, p, xp=xp), w

    def domain_valid(self, state, p, valid, *, xp):
        own = w1.water_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def balance_terms(self, result, row, p, *, xp):
        result["energy"] += w1.water_ledgers(row, p, xp=xp)[0]
        return result

    def own_ledgers(self, row, p, *, xp):
        return w1.water_ledgers(row, p, xp=xp)[1]

    def own_magnitudes(self, row, p, *, xp):
        return w1.water_magnitudes(row, p, xp=xp)

    def own_bounds(self, magnitudes, steps):
        return w1.water_bounds(magnitudes, steps)

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        n = p.active.size
        w = w1.water_rates(state, control.water, p, xp=np)
        volume = w1.volumes(state, p, xp=np)
        ci, co = w1.physical_amounts(state, p)
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        columns.update(
            cell_volume_pL=volume[:n],
            extracellular_volume_pL=volume[n:],
            cell_concentration_mM=np.where(p.active, ci / volume[:n], 0.0),
            extracellular_concentration_mM=np.where(p.outside_active, co / volume[n:], 0.0),
            osmotic_pressure_Pa=w.edges.osmotic_pressure_Pa,
            hydrostatic_pressure_Pa=w.edges.hydrostatic_pressure_Pa,
            water_potential_Pa=w.edges.water_potential_Pa,
            water_flow_pL_s=w.flow,
            water_dissipation_pJ_s=w.heat,
            bath_water_supply_pL_s=w.supply,
            water_availability=control.water,
            energy_balance_pJ=np.atleast_1d(model.balances(state, p)["energy"]),
            energy_balance_pJ_s=row["energy_balance_pJ_s"] + w1.water_energy_rate(w, p, xp=np),
        )
        return columns
