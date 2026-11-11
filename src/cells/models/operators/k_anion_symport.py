"""Operator k_anion_symport_mass_action@1: KCC-type K+/anion symport routes.

The law and its booking are those of resolved_pump_water@2
(models/surface_pump_water_v2.py, processes/k_anion_symport.py,
docs/PUMP_WATER_MODEL.md), called, never copied: outward cycles
J = k a f(V) (K_i A_i - K_o A_o), one potassium and one anion per cycle, no
current, heat 1e-3 J RT ln(K_i A_i / (K_o A_o)) >= 0, with the cell's current
volume in f(V).

Contract (models/operators/contract.py):
* owned state: the symport cycles (outward, K and anion each) and their heat;
* entity writes: cell and outside amounts of the two roles, inside @3's step; the
  applied transfer (@3's tableau weights) is booked in the cycle counter and
  enters @3's material ledgers as membrane transfers;
* parts: an in-step membrane process through @3's opt-in hook (one more explicit
  membrane term at every @3 stage, in readouts and in the RK4 right-hand side);
  @3 returns the applied transfer and the trapezoid heat of each IMEX step;
  with no route declared the process is statically absent;
* requires the water operator before it: the route's step bound reads the
  declared maximum volume (as resolved_pump_water@2 does);
* refusal: the route's explicit rate at the maximum volume above the family's
  bound, an availability outside [0, 1] and the law's own domain.
"""

from bisect import bisect_right
from dataclasses import asdict, replace

import numpy as np

from cells.core import surface_pump_spec as first_spec
from cells.core import surface_pump_v3_spec as ionic_spec
from cells.core import surface_pump_water_v2_spec as symport_spec
from cells.core.specs import ConfigError
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_pump_water_v2 as w2
from cells.models.operators.contract import Operator
from cells.models.operators.osmotic_water import LAW_ID as WATER_LAW_ID
from cells.numerics.extracellular_field import scatter
from cells.processes import k_anion_symport as law


def frozen_spec(spec, water, water_schedule, declaration, schedule):
    """The resolved_pump_water@2 definition of the water and symport operators."""
    m, e = spec.model, spec.experiment
    model = symport_spec.SurfacePumpRegulatedWaterModel(
        **{k: getattr(m, k) for k in ionic_spec.SurfacePumpChannelModel.__dataclass_fields__},
        water=water,
        symport=declaration,
    )
    experiment = symport_spec.Experiment(
        **{k: getattr(e, k) for k in ionic_spec.Experiment.__dataclass_fields__},
        water=water_schedule,
        symport=schedule,
    )
    return replace(spec, model=model, experiment=experiment)


def water_entry(spec):
    """(declaration, schedule) of the composition's water operator."""
    for d, s in zip(spec.model.operators, spec.experiment.operators, strict=True):
        if d.law == WATER_LAW_ID:
            return d, s.data
    raise ConfigError(f"{law.LAW_ID} requires {WATER_LAW_ID}")


class KAnionSymport(Operator):
    LAW_ID = law.LAW_ID
    PROCESS = True
    STATE_AXES = w2.SYMPORT_STATE_AXES
    HEAT_FIELDS = ("symport_dissipated_energy_pJ",)
    LAYOUT_FIELDS = w2.SYMPORT_LAYOUT_FIELDS
    CONTROL_FIELDS = ("symport",)
    EXPERIMENT_KEYS = ("symport_controls",)
    ENTITY_WRITES = {
        "amount_increment": ("symport_cycles_fmol",),
        "extracellular_amount_increment": ("symport_cycles_fmol",),
    }
    READOUT = "symport"
    READOUT_COLUMNS = w2.SYMPORT_READOUTS
    FINITE_RATES = True
    REQUIRES = (WATER_LAW_ID,)

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return symport_spec.parse_symport(raw, base)

    def to_dict(self, declaration, base):
        y = declaration
        if type(y) is not symport_spec.Symport or any(
            type(r) is not symport_spec.SymportRoute for r in y.routes
        ):
            raise ConfigError("Require explicit immutable symport declaration types")
        return dict(
            law=y.law,
            volume_factor=y.volume_factor,
            roles=dict(potassium=y.potassium, anion=y.anion),
            routes=[asdict(r) for r in y.routes],
        )

    def parse_schedule(self, raw, base, declaration):
        ids = [r.membrane_id for r in declaration.routes]
        schedules = first_spec._schedules(
            raw["symport_controls"], "membrane", ids, base.experiment.end_time
        )
        return tuple(schedules[i] for i in ids)

    def schedule_to_dict(self, schedule, base, declaration):
        return dict(
            symport_controls=[
                dict(membrane_id=r.membrane_id, schedule=[asdict(c) for c in g])
                for r, g in zip(declaration.routes, schedule, strict=True)
            ]
        )

    def schedule_times(self, schedule):
        return tuple(c.time for g in schedule for c in g)

    def value_at(self, schedule, time):
        return tuple(g[bisect_right([p.time for p in g], time) - 1].availability for g in schedule)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        padded = np.zeros((len(times), spec.execution.membrane_capacity))
        if declaration.routes:
            values = np.asarray(records, dtype=np.float64)[indices]
            mids = [p.id for p in spec.model.membranes]
            for k, route in enumerate(declaration.routes):
                padded[:, mids.index(route.membrane_id)] = values[:, k]
        return (padded,)

    def check_steps(self, spec, declaration, schedule, steps, controls, model):
        """resolved_pump_water@2's route bound (models/surface_pump_water_v2.check_steps)."""
        if not declaration.routes:
            return
        water, water_schedule = water_entry(spec)
        state, p = w2.initial_values(
            frozen_spec(spec, water, water_schedule, declaration, schedule)
        )
        cells = np.asarray(p.membrane_cell)
        k, a = int(p.symport_potassium_species), int(p.symport_anion_species)
        ci = (p.amount_reference + state.amount_increment) / p.volume
        vmax = p.water_maximum_volume_pL[cells]
        factor = np.exp(
            (vmax - p.symport_set_volume_pL) / (p.symport_steepness * p.symport_set_volume_pL)
        )
        rate = (
            p.symport_capacity_fmol_s_mM2 * factor * (ci[k, cells] + ci[a, cells]) / p.volume[cells]
        )
        rate = np.max(np.where(p.symport_route & p.membrane_active, rate, 0.0), initial=0.0)
        if np.max(steps, initial=0) * rate > ionic.EXPLICIT_STEP_BOUND:
            raise ConfigError("Symport rate exceeds the explicit-rate bound at maximum volume")

    def batch_signature(self, declaration):
        return (declaration.law, tuple(r.membrane_id for r in declaration.routes))

    def working_size(self, spec):
        return 4 * spec.execution.membrane_capacity

    def summary(self, spec, declaration, schedule, history):
        y = declaration
        return {
            "symport_law": y.law,
            "symport_volume_factor": y.volume_factor,
            "symport_roles": dict(potassium=y.potassium, anion=y.anion),
            "symport_routes": [r.membrane_id for r in y.routes],
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        water, water_schedule = water_entry(spec)
        state, p = w2.initial_values(
            frozen_spec(spec, water, water_schedule, declaration, schedule)
        )
        return (
            {k: getattr(state, k) for k in self.STATE_AXES},
            {k: getattr(p, k) for k in self.LAYOUT_FIELDS},
        )

    # ------------------------------------------------------------ step parts

    def idle_process(self, p):
        return not p.symport_present.shape[0]

    def statically_idle(self, p):
        return self.idle_process(p)  # No route declared: the step is water's alone.

    def process(self, control, p):
        return w2.membrane_process(control.symport, p)

    def book_process(self, state, start, applied, heat, p):
        k = p.symport_potassium_species
        return state._replace(
            symport_cycles_fmol=start.symport_cycles_fmol + applied[k],
            symport_dissipated_energy_pJ=start.symport_dissipated_energy_pJ + heat,
        )

    def rates(self, state, control, p, view, *, xp):
        ci, co = ionic.physical_amounts(state, view)
        ci = xp.where(view.active, ci / view.volume, 1.0)
        co = xp.where(view.outside_active, co / view.extracellular_volume, 1.0)
        s, ok = w2.symport_rates(
            ci[:, p.membrane_cell],
            co[:, p.membrane_outside],
            view.volume[p.membrane_cell],
            control.symport,
            p,
            xp=xp,
        )
        rates = dict(
            symport_cycles_fmol=s.cycles_fmol_s, symport_dissipated_energy_pJ=s.dissipation_pJ_s
        )
        return rates, ok, None, s

    def domain_valid(self, state, p, valid, *, xp):
        route = p.symport_route & p.membrane_active
        for name in self.STATE_AXES:
            value = getattr(state, name)
            own = xp.all(xp.isfinite(value)) & xp.all(xp.where(route, True, value == 0))
            valid = own if valid is None else valid & own
        return valid

    # ------------------------------------------------------------ ledgers

    def adjust_inner(self, row, p, *, xp):
        return row._replace(
            membrane_transferred=row.membrane_transferred
            + w2.transfer(row.symport_cycles_fmol, p, xp=xp)
        )

    def balance_terms(self, result, row, p, *, xp):
        result["energy"] += xp.sum(row.symport_dissipated_energy_pJ)
        return result

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        moved = xp.abs(w2.transfer(row.symport_cycles_fmol, p, xp=xp))
        magnitudes[0] = magnitudes[0] + scatter(
            moved, row.amount_increment, (p.membrane_cell,), xp=xp
        )
        magnitudes[1] = magnitudes[1] + scatter(
            moved, row.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        )
        return magnitudes

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        from cells.core.errors import NumericalError

        v = model.readouts(state, control, p, xp=np)
        if not v.valid:
            raise NumericalError("Composite symport observation domain invalid")
        return dict(
            symport_cycles_fmol=state.symport_cycles_fmol,
            symport_dissipated_energy_pJ=state.symport_dissipated_energy_pJ,
            symport_cycle_rate_fmol_s=v.symport.cycles_fmol_s,
            symport_dissipation_pJ_s=v.symport.dissipation_pJ_s,
            symport_volume_factor=np.where(p.symport_route, v.symport.volume_factor, 0.0),
            symport_availability=control.symport,
            energy_balance_pJ=np.atleast_1d(model.balances(state, p)["energy"]),
            energy_balance_pJ_s=np.atleast_1d(v.field.energy_balance_pJ_s),
        )
