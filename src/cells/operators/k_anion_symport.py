"""Operator cells.operator.k_anion_symport_mass_action@1: KCC-type K+/anion symport routes.

The law's membrane process and its booking, moved here unchanged from
cells.model.resolved_pump_water@2 (models/surface_pump_water_v2.py, now a thin composition;
laws/routes/k_anion_symport.py, docs/PUMP_WATER_MODEL.md): outward cycles
J = k a f(V) (K_i A_i - K_o A_o), one potassium and one anion per cycle, no
current, heat 1e-3 J RT ln(K_i A_i / (K_o A_o)) >= 0, with the cell's current
volume in f(V).

Contract (operators/contract.py):
* owned state: the symport cycles (outward, K and anion each) and their heat;
* entity writes: cell and outside amounts of the two roles, inside @3's step; the
  applied transfer (@3's tableau weights) is booked in the cycle counter and
  enters @3's material ledgers as membrane transfers;
* parts: an in-step membrane process through @3's opt-in hook (one more explicit
  membrane term at every @3 stage, in readouts and in the RK4 right-hand side);
  @3 returns the applied transfer and the trapezoid heat of each IMEX step; with
  no route declared the operator is statically idle in the step (its fields pass
  through), and its process still enters the readouts as exact zeros;
* requires the water operator before it: the route's step bound reads the
  declared maximum volume;
* refusal: the route's explicit rate at the maximum volume above the family's
  bound (its cell's and, at a finite outside node, that node's concentrations and
  volume, each with the summed rate of its routes; route_rate), an availability
  outside [0, 1] and the law's own domain.
"""

from bisect import bisect_right
from dataclasses import asdict

import jax.numpy as jnp
import numpy as np

from cells.definitions import surface_pump_spec as first_spec
from cells.definitions import surface_pump_water_v2_spec as symport_spec
from cells.definitions.specs import ConfigError
from cells.laws.routes import k_anion_symport as law
from cells.models import surface_pump_v3 as ionic
from cells.numerics.extracellular_field import scatter
from cells.numerics.species_sums import entity_sum
from cells.operators.contract import Operator
from cells.operators.osmotic_water import LAW_ID as WATER_LAW_ID

LAW_ID = law.LAW_ID

# ------------------------------------------------------------------ the route law
SYMPORT_STATE_AXES = {
    "symport_cycles_fmol": ["membrane_slot"],  # Outward: K and anion each, 1:1.
    "symport_dissipated_energy_pJ": ["membrane_slot"],
}


SYMPORT_LAYOUT_FIELDS = (
    "symport_route",  # [membrane] bool
    "symport_capacity_fmol_s_mM2",
    "symport_set_volume_pL",
    "symport_steepness",
    "symport_potassium_species",  # int
    "symport_anion_species",  # int
    "symport_present",  # one element with a route, none without: the static branch
)


def symport_parameters(p):
    return law.Parameters(
        p.symport_capacity_fmol_s_mM2, p.symport_set_volume_pL, p.symport_steepness
    )


def symport_rates(ci, co, volume, availability, p, *, xp=jnp):
    """The law at the patches: (rates, valid); membranes without a route give zeros."""
    k, a = p.symport_potassium_species, p.symport_anion_species
    route = p.symport_route & p.membrane_active
    args = (
        xp.where(route, ci[k], 1.0),
        xp.where(route, ci[a], 1.0),
        xp.where(route, co[k], 1.0),
        xp.where(route, co[a], 1.0),
        xp.where(route, volume, 1.0),
    )
    q = symport_parameters(p)
    open_ = xp.where(route, availability, 0.0)
    r = law.rates(*args, p.temperature, q, open_, xp=xp)
    valid = xp.all(xp.where(route, law.domain_valid(*args, q, open_, xp=xp), True))
    valid &= xp.all(xp.isfinite(availability) & (availability >= 0) & (availability <= 1))
    valid &= xp.all(xp.where(p.membrane_active, True, availability == 0))
    zero = xp.zeros_like(r.cycles_fmol_s)
    return r._replace(
        cycles_fmol_s=xp.where(route, r.cycles_fmol_s, zero),
        dissipation_pJ_s=xp.where(route, r.dissipation_pJ_s, zero),
    ), valid


def membrane_process(availability, p):
    """The routes as @3's membrane process (outward flux [species, membrane], heat)."""

    def process(ci, co, volume, voltage, *, xp):
        r, valid = symport_rates(ci, co, volume, availability, p, xp=xp)
        species = xp.arange(ci.shape[0])[:, None]
        role = (species == p.symport_potassium_species) | (species == p.symport_anion_species)
        flux = xp.where(role, r.cycles_fmol_s[None, :], 0.0)
        return ionic.MembraneProcess(flux, r.dissipation_pJ_s, valid)

    return process


def transfer(cycles, p, *, xp=jnp):
    """Symport cycles as outward species transfers [species, membrane]."""
    species = xp.arange(p.valence.shape[0])[:, None]
    role = (species == p.symport_potassium_species) | (species == p.symport_anion_species)
    return xp.where(role, cycles[None, :], 0.0)


SYMPORT_READOUTS = (
    "symport_cycle_rate_fmol_s",
    "symport_dissipation_pJ_s",
    "symport_volume_factor",
    "symport_availability",
)


def bind(spec, declaration):
    """The symport state (zero) and layout fields: routes, roles and the static branch."""
    m, nm = spec.model, spec.execution.membrane_capacity
    mids = [q.id for q in m.membranes]
    route = np.zeros(nm, dtype=bool)
    capacity, set_volume, steepness = np.zeros(nm), np.ones(nm), np.ones(nm)
    for r in declaration.routes:
        i = mids.index(r.membrane_id)
        route[i] = True
        capacity[i], set_volume[i], steepness[i] = (
            r.capacity_fmol_s_mM2,
            r.set_volume_pL,
            r.steepness,
        )
    layout = (
        route,
        capacity,
        set_volume,
        steepness,
        np.int64(m.species_ids.index(declaration.potassium)),
        np.int64(m.species_ids.index(declaration.anion)),
        np.zeros(int(bool(declaration.routes))),
    )
    return (
        dict(zip(SYMPORT_STATE_AXES, (np.zeros(nm), np.zeros(nm)), strict=True)),
        dict(zip(SYMPORT_LAYOUT_FIELDS, layout, strict=True)),
    )


# ------------------------------------------------------------------ the operator


def outside_term(state, p, k, a):
    """[membrane] (K_o + A_o) / V_o (mM/pL) of each patch's outside node at the declared state, or
    zero where that node is a held bath (its concentrations are held) or inactive."""
    finite = np.asarray(p.outside_active & ~p.reservoir)
    volume = np.where(finite, p.extracellular_volume, 1.0)
    co = (p.extracellular_amount_reference + state.extracellular_amount_increment) / volume
    term = np.where(finite, (co[k] + co[a]) / volume, 0.0)
    return term[np.asarray(p.membrane_outside)]


def node_sums(scale, p):
    """([membrane], [membrane]) the summed k f of the routes on each patch's cell and on its
    outside node (scale: each route's k f, zero off the routes)."""
    cells, outside = np.asarray(p.membrane_cell), np.asarray(p.membrane_outside)
    on_cell = scatter(scale, np.zeros(np.shape(p.volume)), (cells,), xp=np)
    on_node = scatter(scale, np.zeros(np.shape(p.extracellular_volume)), (outside,), xp=np)
    return on_cell[cells], on_node[outside]


def route_rate(spec, model):
    """The largest route relaxation rate at the declared state, with the volume factor at the
    declared maximum volume (the symport's step bound, read once).

    A route's outward extent q (fmol) moves its product difference D = K_i A_i - K_o A_o at the
    linear rate (K_i + A_i) / V_i + (K_o + A_o) / V_o per fmol, each volume its own (the independent
    Lean project's finite_volume_drive, lean/CellsProofs/Transport/PotassiumAnionSymport.lean), and
    above h x rate = 2 the explicit ARS(2,2,2) stages book a step against D (its explicit_step and
    step_points_inward). A held bath keeps its concentrations: its term is zero. Every route on a
    cell or an outside node moves that node's concentrations, so a route's rate is
    W_cell (K_i + A_i) / V_i + W_node (K_o + A_o) / V_o, with W the summed k f of the node's routes
    (node_sums): the column sums of the routes' Jacobian, which bound its spectral radius. With one
    route per node it is the proof's k f [(K_i + A_i) / V_i + (K_o + A_o) / V_o], and with a held
    bath k f (K_i + A_i) / V_i bit for bit, the bound before 20 November 2026.

    Its limits. The rate is the linear one: with unequal volumes, finite_volume_drive's quadratic
    term raises the rate along a step's own transfer, so a step far from stall into a small finite
    node can outrun it within the step (in the case measured, the energy ledger then refused the
    step at run time). And it is read once, at the declared state, so concentrations and volumes
    that move during a run can outgrow it. A check at each explicit stage would cover both."""
    state, p = model.initial_values(spec)
    cells = np.asarray(p.membrane_cell)
    k, a = int(p.symport_potassium_species), int(p.symport_anion_species)
    ci = (p.amount_reference + state.amount_increment) / p.volume
    vmax = p.water_maximum_volume_pL[cells]
    factor = np.exp(
        (vmax - p.symport_set_volume_pL) / (p.symport_steepness * p.symport_set_volume_pL)
    )
    route = p.symport_route & p.membrane_active
    on_cell, on_node = node_sums(np.where(route, p.symport_capacity_fmol_s_mM2 * factor, 0.0), p)
    rate = on_cell * (ci[k, cells] + ci[a, cells]) / p.volume[cells]
    rate = rate + on_node * outside_term(state, p, k, a)
    return np.max(np.where(route, rate, 0.0), initial=0.0)


class KAnionSymport(Operator):
    LAW_ID = LAW_ID
    PROCESS = True

    def moves_in_step(self, spec, declaration):
        """The rows its in-step process moves (core/species_registry.moved_in_step; D176): both
        roles' cell and outside rows, when it declares a route."""
        if not declaration.routes:
            return ()
        roles = (declaration.potassium, declaration.anion)
        return tuple((s, kind) for s in roles for kind in ("cell", "outside"))

    STATE_AXES = SYMPORT_STATE_AXES
    HEAT_FIELDS = ("symport_dissipated_energy_pJ",)
    LAYOUT_FIELDS = SYMPORT_LAYOUT_FIELDS
    CONTROL_FIELDS = ("symport",)
    EXPERIMENT_KEYS = ("symport_controls",)
    ENTITY_WRITES = {
        "amount_increment": ("symport_cycles_fmol",),
        "extracellular_amount_increment": ("symport_cycles_fmol",),
    }
    READOUT = "symport"
    READOUT_COLUMNS = SYMPORT_READOUTS
    REPLACES = {
        "energy_balance_pJ": "the composite's energy ledger with the symport terms",
        "energy_balance_pJ_s": "the composite readouts' energy-balance rate",
    }
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
        """The route bound: the relaxation rate of a route's product difference,
        k f [(K_i + A_i) / V_i + (K_o + A_o) / V_o] at the declared state, each node's term
        with the summed k f of its routes (the outside term zero at a held bath), with the
        volume factor at the declared maximum volume (route_rate; the routes are
        electroneutral, so they add no membrane conductance to @3's explicit-stage bound)."""
        self.bind_check_steps(spec, declaration, schedule, model)(steps)

    def bind_check_steps(self, spec, declaration, schedule, model):
        """The route bound with the declared state's rate computed once, at first use."""
        if not declaration.routes:
            return lambda steps: None
        cache = {}

        def check(steps):
            if "rate" not in cache:
                cache["rate"] = route_rate(spec, model)
            if np.max(steps, initial=0) * cache["rate"] > ionic.EXPLICIT_STEP_BOUND:
                raise ConfigError("Symport rate exceeds the explicit-rate bound at maximum volume")

        return check

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
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def idle_process(self, p):
        return not p.symport_present.shape[0]

    def statically_idle(self, p):
        return self.idle_process(p)  # No route declared: the step is water's alone.

    def process(self, control, p):
        return membrane_process(control.symport, p)

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
        s, ok = symport_rates(
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
        return rates, ok, s

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
            + transfer(row.symport_cycles_fmol, p, xp=xp)
        )

    def ledger_terms(self, result, row, p, *, xp):
        result["energy"] += entity_sum(row.symport_dissipated_energy_pJ, axis=None, xp=xp)
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        moved = xp.abs(transfer(row.symport_cycles_fmol, p, xp=xp))
        magnitudes[0] = magnitudes[0] + scatter(
            moved, row.amount_increment, (p.membrane_cell,), xp=xp
        )
        magnitudes[1] = magnitudes[1] + scatter(
            moved, row.extracellular_amount_increment, (p.membrane_outside,), xp=xp
        )
        return magnitudes

    # ------------------------------------------------------------ observations

    def observe(self, row, state, control, p, view, model, spec):
        from cells.execution.errors import NumericalError

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
