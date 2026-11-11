"""resolved_pump_water@2: resolved_pump_water@1 plus KCC-type K+/anion symport routes.

Each route (core/surface_pump_water_v2_spec.py) is the law
processes/k_anion_symport.LAW_ID on its membrane patch: outward cycles
J = k a f(V) (K_i A_i - K_o A_o), one potassium and one anion per cycle, so it
carries no current, with heat 1e-3 J A >= 0 and the cell's current volume in
f(V). It is passed to resolved_pump_tissue@3's opt-in membrane-process hook
(models/surface_pump_v3.py), so it is one more explicit membrane term at every
@3 stage, in readouts and in rhs; @3 returns the tableau-applied transfer and
the trapezoid heat of each step, which this model books in its own ledgers
(symport_cycles_fmol, symport_dissipated_energy_pJ). Everything else, water
included, is resolved_pump_water@1 (models/surface_pump_water.py): the same
Strang splitting, with @3's step behind the same optimization barrier.

With no route declared the identity is resolved_pump_water@1: the step is that
model's step (a static branch on the route layout's shape). Fixed points stay
exact: the symport moves amounts inside @3's step, and water acts only on
volumes at frozen amounts, so a zero of the full right-hand side is a fixed
point of each split piece.

Ledgers: the material ledgers include the symport transfers (K and anion);
the energy ledger adds the symport heat; dissipation includes it.
"""

from dataclasses import make_dataclass
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ConfigError
from cells.core.surface_pump_water_spec import Control as WaterControl
from cells.core.surface_pump_water_v2_spec import MODEL_ID, Control, projection
from cells.models import surface_pump as first
from cells.models import surface_pump_v3 as ionic
from cells.models import surface_pump_water as w1
from cells.numerics.extracellular_field import scatter
from cells.numerics.fixed_step import rk4_checked_step
from cells.processes import k_anion_symport as law

OBSERVER_ID = "resolved_pump_regulated_water_accepted_grid_readouts@1"
OBSERVATION_SAMPLING = w1.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_resolved_inventory_gates_atp_bounded_volumes_symport@1"
BATCH_CAPACITIES = w1.BATCH_CAPACITIES
SYMPORT_STATE_AXES = {
    "symport_cycles_fmol": ["membrane_slot"],  # Outward: K and anion each, 1:1.
    "symport_dissipated_energy_pJ": ["membrane_slot"],
}
STATE_AXES = w1.STATE_AXES | SYMPORT_STATE_AXES
STATE_TYPE = NamedTuple("SurfacePumpRegulatedWaterState", [(k, object) for k in STATE_AXES])
SYMPORT_LAYOUT_FIELDS = (
    "symport_route",  # [membrane] bool
    "symport_capacity_fmol_s_mM2",
    "symport_set_volume_pL",
    "symport_steepness",
    "symport_potassium_species",  # int
    "symport_anion_species",  # int
    "symport_present",  # one element with a route, none without: the static branch
)
LAYOUT_TYPE = NamedTuple(
    "SurfacePumpRegulatedWaterLayout",
    [(k, object) for k in (*w1.LAYOUT_TYPE._fields, *SYMPORT_LAYOUT_FIELDS)],
)
FLOOR_LAYOUT_TYPE = NamedTuple(
    "SurfacePumpRegulatedWaterFloorLayout",
    [(k, object) for k in (*w1.FLOOR_LAYOUT_TYPE._fields, *SYMPORT_LAYOUT_FIELDS)],
)
WATER_FIELDS = w1.STATE_TYPE._fields
ENERGY_RTOL = w1.ENERGY_RTOL
parameters = w1.parameters
physical_amounts = w1.physical_amounts
rebind = w1.rebind


def batch_signature(model):
    routes = tuple(r.membrane_id for r in model.symport.routes)
    return (*w1.batch_signature(model), model.symport.law, routes)


def working_size(spec):
    return w1.working_size(projection(spec)) + 4 * spec.execution.membrane_capacity


def water_state(state):
    return w1.STATE_TYPE(*(getattr(state, k) for k in WATER_FIELDS))


def water_layout(p):
    kind = w1.FLOOR_LAYOUT_TYPE if hasattr(p, "field_current_floor") else w1.LAYOUT_TYPE
    return kind(*(getattr(p, k) for k in kind._fields))


def water_control(control):
    return WaterControl(*control[: len(WaterControl._fields)])


def initial_values(spec):
    state, p = w1.initial_values(projection(spec))
    m, nm = spec.model, spec.execution.membrane_capacity
    mids = [q.id for q in m.membranes]
    route = np.zeros(nm, dtype=bool)
    capacity, set_volume, steepness = np.zeros(nm), np.ones(nm), np.ones(nm)
    for r in m.symport.routes:
        i = mids.index(r.membrane_id)
        route[i] = True
        capacity[i], set_volume[i], steepness[i] = (
            r.capacity_fmol_s_mM2,
            r.set_volume_pL,
            r.steepness,
        )
    kind = FLOOR_LAYOUT_TYPE if type(p) is w1.FLOOR_LAYOUT_TYPE else LAYOUT_TYPE
    layout = kind(
        *p,
        route,
        capacity,
        set_volume,
        steepness,
        np.int64(m.species_ids.index(m.symport.potassium)),
        np.int64(m.species_ids.index(m.symport.anion)),
        np.zeros(int(bool(m.symport.routes))),
    )
    return STATE_TYPE(*state, np.zeros(nm), np.zeros(nm)), layout


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


def imex_step(state, dt, control, p, *, xp=jnp):
    """resolved_pump_water@1's split step with the routes in @3's step (static skip)."""
    if not p.symport_present.shape[0]:  # No route: resolved_pump_water@1's step exactly.
        moved, valid = w1.imex_step(water_state(state), dt, water_control(control), p, xp=xp)
        return STATE_TYPE(
            *moved, state.symport_cycles_fmol, state.symport_dissipated_energy_pJ
        ), valid
    h = 0.5 * dt
    first_half, valid = w1.water_step(water_state(state), h, control.water, p, xp=xp)
    valid &= w1.water_control_valid(control.water, p, xp=xp)
    current = w1.ionic_layout(p, first_half)
    process = membrane_process(control.symport, p)
    inputs = (w1.ionic_state(first_half), w1.ionic_control(control), current)
    if xp is jnp:
        inputs = jax.lax.optimization_barrier(inputs)
    moved, ok, (applied, heat) = ionic.imex_step(
        inputs[0], dt, inputs[1], inputs[2], xp=xp, membrane_process=process
    )
    if xp is jnp:
        moved, ok, applied, heat = jax.lax.optimization_barrier((moved, ok, applied, heat))
    middle = first_half._replace(**moved._asdict())
    final, last = w1.water_step(middle, h, control.water, p, xp=xp)
    k = p.symport_potassium_species
    new = STATE_TYPE(
        *final,
        state.symport_cycles_fmol + applied[k],
        state.symport_dissipated_energy_pJ + heat,
    )
    valid = valid & ok & last & domain_valid(new, p, p.active, xp=xp)
    return jax.tree.map(lambda old, n: xp.where(valid, n, old), state, new), valid


def checked_step(state, dt, control, p, active):
    """RK4 of the coupled right-hand side for an empty tableau; otherwise the split step."""
    if p.imex_explicit.shape[0] == 0:
        return rk4_checked_step(rhs, domain_valid, state, dt, control, p, active)
    return imex_step(state, dt, control, p)


class Values(NamedTuple):
    field: object
    derivative: object
    ionic: object
    water: object
    symport: object
    valid: object


def readouts(state, control, p, *, xp=jnp):
    current = w1.ionic_layout(p, state)
    process = membrane_process(control.symport, p)
    v = ionic.readouts(
        w1.ionic_state(state),
        w1.ionic_control(control),
        current,
        xp=xp,
        membrane_process=process,
    )
    w = w1.water_rates(state, control.water, p, xp=xp)
    ci, co = physical_amounts(state, current)
    ci = xp.where(current.active, ci / current.volume, 1.0)
    co = xp.where(current.outside_active, co / current.extracellular_volume, 1.0)
    s, ok = symport_rates(
        ci[:, p.membrane_cell],
        co[:, p.membrane_outside],
        current.volume[p.membrane_cell],
        control.symport,
        p,
        xp=xp,
    )
    derivative = STATE_TYPE(
        *v.derivative,
        w.cell,
        w.outside,
        w.flow,
        w.heat,
        w.supply,
        w.work,
        s.cycles_fmol_s,
        s.dissipation_pJ_s,
    )
    valid = v.valid & ok & w1.water_domain_valid(water_state(state), p, xp=xp)
    valid &= w1.water_control_valid(control.water, p, xp=xp)
    for value in derivative[len(w1.IONIC_FIELDS) :]:
        valid &= xp.all(xp.isfinite(value))
    field = v.field._replace(
        energy_balance_pJ_s=v.field.energy_balance_pJ_s + w1.water_energy_rate(w, p, xp=xp),
        converged=valid,
    )
    return Values(field, derivative, v, w, s, valid)


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def rhs(state, control, p, active, *, xp=jnp):
    values = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(values.valid, v, xp.nan) for v in values.derivative))


def domain_valid(state, p, active, *, xp=jnp):
    valid = w1.domain_valid(water_state(state), p, active, xp=xp)
    route = p.symport_route & p.membrane_active
    for name in SYMPORT_STATE_AXES:
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(xp.where(route, True, value == 0))
    return valid


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    valid &= w1.water_control_valid(control.water, p, xp=xp)
    if xp is np:
        if not valid:
            return np.asarray(False)
        try:
            return np.asarray(readouts(state, control, p, xp=np).valid)
        except np.linalg.LinAlgError:
            return np.asarray(False)
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def check_definition(spec):
    from cells.core.surface_pump_water_v2_spec import control_values

    small = w1.compact(spec)
    state, p = initial_values(small)
    controls = control_values(small, [c.time for c in small.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(controls.membrane)):
            control = Control(*(v[i] for v in controls))
            if not control_domain_valid(state, control, p, p.active, xp=np):
                raise ConfigError("Initial resolved pump water @2 domain invalid")


def check_steps(spec, steps, controls):
    """resolved_pump_water@1's step checks on this definition's full event grid.

    The routes are electroneutral, so they add no membrane conductance to @3's
    explicit-stage bound; their own explicit rate is bounded below.
    """
    w1.check_steps(spec, steps, controls)
    state, p = initial_values(spec)
    # Relaxation rate of a route's concentration product, k f (K_i + A_i) / V at the
    # declared state with the volume factor at the declared maximum volume.
    if spec.model.symport.routes:
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


# Row checks: resolved_pump_water@1's (which call @3's own checks), with the symport
# transfers in the material ledgers, its heat in the energy ledger and its
# dissipation field.
DISSIPATION_FIELDS = (*w1.DISSIPATION_FIELDS, "symport_dissipated_energy_pJ")
LEDGER_DIAGNOSTICS = w1.LEDGER_DIAGNOSTICS
LEDGERS = w1.LEDGERS
WATER_DIAGNOSTICS = w1.WATER_DIAGNOSTICS


def adjusted(row, p, *, xp):
    """The row with the symport transfers added to @3's membrane transfers."""
    return water_state(row)._replace(
        membrane_transferred=row.membrane_transferred + transfer(row.symport_cycles_fmol, p, xp=xp)
    )


def ionic_balances(state, p):
    result = w1.ionic_balances(adjusted(state, p, xp=np), p)
    result["energy"] += np.sum(state.symport_dissipated_energy_pJ)
    return result


def balances(state, p):
    result = w1.balances(adjusted(state, p, xp=np), p)
    result["energy"] += np.sum(state.symport_dissipated_energy_pJ)
    return result


def device_balances(state, p):
    result = w1.device_balances(adjusted(state, p, xp=jnp), p)
    result["energy"] += jnp.sum(state.symport_dissipated_energy_pJ)
    return result


def ionic_magnitudes(row, p, *, xp=np):
    """@3's magnitudes with the symport transfers' own magnitudes added."""
    local, outside, total, *rest = w1.ionic_magnitudes(adjusted(row, p, xp=xp), p, xp=xp)
    moved = xp.abs(transfer(row.symport_cycles_fmol, p, xp=xp))
    local = local + scatter(moved, row.amount_increment, (p.membrane_cell,), xp=xp)
    outside = outside + scatter(
        moved, row.extracellular_amount_increment, (p.membrane_outside,), xp=xp
    )
    return (local, outside, total, *rest)


def magnitudes(row, p, *, xp=np):
    return (*ionic_magnitudes(row, p, xp=xp), *w1.water_magnitudes(row, p, xp=xp))


ledger_limits = w1.ledger_limits


def check_values(state, spec, steps=None):
    """resolved_pump_water@1's host checks with the symport ledgers (same order)."""
    _, p = initial_values(spec)
    diagnostics = first.checked_rows(
        state,
        spec,
        p,
        domain=domain_valid,
        balances=ionic_balances,
        magnitudes=ionic_magnitudes,
        dissipation=DISSIPATION_FIELDS,
        steps=steps,
    )
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    counts = [0] * len(rows) if steps is None else list(steps)
    extra = {"max_" + k: 0.0 for k in WATER_DIAGNOSTICS}
    with np.errstate(all="ignore"):
        for row, count in zip(rows, counts, strict=True):
            values = w1.water_ledgers(row, p, xp=np)[1]
            bounds = w1.water_bounds(w1.water_magnitudes(row, p, xp=np), count)
            for (name, value), key, bound in zip(
                values.items(), WATER_DIAGNOSTICS, bounds, strict=True
            ):
                if not np.isfinite(value).all() or np.any(np.abs(value) > bound):
                    raise NumericalError(w1.WATER_LEDGER_MESSAGE + name)
                key = "max_" + key
                extra[key] = max(extra[key], float(np.max(np.abs(value), initial=0)))
    return diagnostics | extra


DEVICE_CHECKS = w1.DEVICE_CHECKS
DEVICE_DIAGNOSTICS = w1.DEVICE_DIAGNOSTICS
device_check_constants = w1.device_check_constants
device_failure_message = w1.device_failure_message


def device_checks(previous, row, p, constants, steps):
    from cells.models.surface_pump_checks import row_checks

    return row_checks(
        previous,
        row,
        p,
        constants,
        steps,
        domain_valid=domain_valid,
        balances=device_balances,
        limits=ledger_limits,
        magnitudes=magnitudes,
        dissipation=DISSIPATION_FIELDS,
    )


SYMPORT_READOUTS = (
    "symport_cycle_rate_fmol_s",
    "symport_dissipation_pJ_s",
    "symport_volume_factor",
    "symport_availability",
)
OBSERVATION_FIELDS = (*w1.OBSERVATION_FIELDS, *SYMPORT_STATE_AXES, *SYMPORT_READOUTS)
Observations = make_dataclass(
    "SurfacePumpRegulatedWaterObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)


def observe_history(times, history, layout, requested, spec):
    """resolved_pump_water@1's observations (its fields at the routes' amounts), then the routes."""
    from cells.core.surface_pump_water_v2_spec import control_values

    p = type(layout)(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Resolved pump water @2 observations require accepted times")
    base = w1.observe_history(
        times,
        w1.STATE_TYPE(*(getattr(history, k) for k in WATER_FIELDS)),
        water_layout(p),
        requested,
        projection(spec),
    )
    controls, extra = control_values(spec, requested), []
    for j, t in enumerate(requested):
        i = int(np.flatnonzero(times == t)[0])
        state = STATE_TYPE(*(np.asarray(v[i]) for v in history))
        control = Control(*(v[j] for v in controls))
        v = readouts(state, control, p, xp=np)
        if not v.valid:
            raise NumericalError("Resolved pump water @2 observation domain invalid")
        extra.append(
            dict(
                symport_cycles_fmol=state.symport_cycles_fmol,
                symport_dissipated_energy_pJ=state.symport_dissipated_energy_pJ,
                symport_cycle_rate_fmol_s=v.symport.cycles_fmol_s,
                symport_dissipation_pJ_s=v.symport.dissipation_pJ_s,
                symport_volume_factor=np.where(p.symport_route, v.symport.volume_factor, 0.0),
                symport_availability=control.symport,
                energy_balance_pJ=np.atleast_1d(balances(state, p)["energy"]),
                energy_balance_pJ_s=np.atleast_1d(v.field.energy_balance_pJ_s),
            )
        )
    columns = dict(vars(base))
    nm = p.membrane_active.size
    empty = dict(
        symport_cycles_fmol=(nm,),
        symport_dissipated_energy_pJ=(nm,),
        symport_cycle_rate_fmol_s=(nm,),
        symport_dissipation_pJ_s=(nm,),
        symport_volume_factor=(nm,),
        symport_availability=(nm,),
        energy_balance_pJ=(1,),
        energy_balance_pJ_s=(1,),
    )
    for key, shape in empty.items():
        columns[key] = np.stack([e[key] for e in extra]) if extra else np.empty((0, *shape))
    return Observations(*(columns[k] for k in OBSERVATION_FIELDS))


def ensemble_voltage(state, layout, spec, time):
    from cells.core.surface_pump_water_v2_spec import control_values

    controls = control_values(spec, [time])
    control = Control(*(v[0] for v in controls))
    p = type(layout)(*(np.asarray(v) for v in layout))
    v = field_values(STATE_TYPE(*(np.asarray(v) for v in state)), control, p, xp=np)
    if not v.converged:
        raise NumericalError("Resolved pump water @2 ensemble endpoint invalid")
    return v.rates.membrane_voltage_V[p.membrane_active]


def summarize(history, diagnostics, spec):
    y = spec.model.symport
    return w1.summarize(history, diagnostics, projection(spec)) | {
        "model": MODEL_ID,
        "state_fields": list(STATE_TYPE._fields),
        "symport_law": y.law,
        "symport_volume_factor": y.volume_factor,
        "symport_roles": dict(potassium=y.potassium, anion=y.anion),
        "symport_routes": [r.membrane_id for r in y.routes],
    }
