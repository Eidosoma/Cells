"""Common-stage free-state Na/K regulation; all 38 physical fields are inherited.

Regulator concentrations are read views of the existing ion/store/fuel amounts.
Ordered source factors replace one another at an explicitly named pump; the
final factor multiplies its scheduled availability once. No inventory, work,
delay state or energetic supply is introduced by dimensionless regulation.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ChannelChange, ConfigError
from cells.core.surface_calcium_energy_regulated_spec import (
    COMPOSITION,
    MODEL_ID,
    TIMING,
    base_spec,
    bind_rule,
    control_values,
)
from cells.models import surface_calcium_energy as base
from cells.processes import betse_network_modulation as modulation
from cells.processes import betse_network_reactions as regulator
from cells.processes import finite_energy as energy

STATE_AXES = base.STATE_AXES
STATE_TYPE = base.STATE_TYPE
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "regulation_capacity")
OBSERVER_ID = "resolved_calcium_energy_regulated_accepted_grid@1"
STAGE_DOMAIN_ID = "free_state_bounded_nak_regulation_common_stage@1"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
TOPOLOGY_FIELDS = (
    *modulation.Topology._fields[:9],
    *("influencer_" + key for key in regulator.Influencers._fields),
    *modulation.Topology._fields[10:],
)
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyRegulatedLayout",
    [
        (k, object)
        for k in (
            *base.HCN_EXTRA_LAYOUT_TYPE._fields,
            *("regulation_" + k for k in TOPOLOGY_FIELDS),
            *("regulation_" + k for k in modulation.Parameters._fields),
            "regulation_active",
            "regulation_membrane",
            "regulation_cell",
            "regulation_outside",
            "regulation_pool_owner",
        )
    ],
)
READOUTS = (
    "nak_regulation_factor",
    "nak_effective_availability",
    "nak_scheduled_availability",
    "network_regulation_factors",
    "regulator_samples_mM",
)
OBSERVATION_FIELDS = (*base.OBSERVATION_FIELDS, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyRegulatedObservations",
    [(k, np.ndarray) for k in OBSERVATION_FIELDS],
    frozen=True,
)
parameters = base.parameters
cytosol_amount = base.cytosol_amount
physical_amounts = base.physical_amounts
store_state, store_layout, er = base.store_state, base.store_layout, base.er
ip3_readouts = base.ip3_readouts
energy_amounts = base.energy_amounts
pump_cycles, pump_routes = base.pump_cycles, base.pump_routes


class RegulationValues(NamedTuple):
    rule_factors: object
    pump_factor: object
    samples_mM: object
    valid: object


class Values(NamedTuple):
    field: object
    derivative: object
    kinetic: object
    energy: object
    regeneration: object
    exchange: object
    regulation: RegulationValues
    effective_control: object
    valid: object


def base_layout(p):
    return base.HCN_EXTRA_LAYOUT_TYPE(*(getattr(p, k) for k in base.HCN_EXTRA_LAYOUT_TYPE._fields))


def _flat_topology(t):
    return dict(zip(TOPOLOGY_FIELDS, (*t[:9], *t.influencers, *t[10:]), strict=True))


def topology(p):
    return modulation.Topology(
        *(getattr(p, "regulation_" + k) for k in modulation.Topology._fields[:9]),
        regulator.Influencers(
            *(getattr(p, "regulation_influencer_" + k) for k in regulator.Influencers._fields)
        ),
        *(getattr(p, "regulation_" + k) for k in modulation.Topology._fields[10:]),
    )


def regulation_parameters(p):
    return modulation.Parameters(
        *(getattr(p, "regulation_" + k) for k in modulation.Parameters._fields)
    )


def initial_values(spec):
    state, p = base.initial_values(base_spec(spec))
    rules = spec.model.network_regulators
    capacity = spec.execution.regulation_capacity
    ids = (*spec.model.species_ids, *energy.SPECIES)
    empty = modulation.bind(
        [],
        [],
        ids,
        (*spec.model.valence, 0, 0, 0),
        np.asarray([0], int),
        1,
        spec.model.species_ids,
        tj_targets=np.asarray([False]),
        rule_capacity=1,
        temperature_K=spec.model.temperature_K,
    )
    bound = [bind_rule(rule.configuration, spec.model) for rule in rules]
    terms = max((t.influencers.mode.shape[0] for t, _ in bound), default=0)
    bound.extend([empty] * (capacity - len(rules)))
    prototypes = _flat_topology(empty[0])
    tops = []
    for t, _ in bound:
        data = _flat_topology(t)
        for key in (
            *("influencer_" + k for k in regulator.Influencers._fields),
            "voltage_coefficient",
            "inhibitor_maximum",
        ):
            default = 1 if key in ("influencer_km_mM", "influencer_exponent") else 0
            data[key] = np.pad(
                data[key], ((0, terms - data[key].shape[0]), (0, 0)), constant_values=default
            )
        tops.append(data)
    values = p._asdict()
    for key, prototype in prototypes.items():
        shape = (
            (terms, 1)
            if key.startswith("influencer_") or key in ("voltage_coefficient", "inhibitor_maximum")
            else prototype.shape
        )
        values["regulation_" + key] = (
            np.stack([d[key] for d in tops])
            if capacity
            else np.empty((0, *shape), dtype=prototype.dtype)
        )
    for key in modulation.Parameters._fields:
        values["regulation_" + key] = (
            np.stack([getattr(q, key) for _, q in bound])
            if capacity
            else np.empty((0, *getattr(empty[1], key).shape))
        )
    values["regulation_active"] = np.arange(capacity) < len(rules)
    for key in ("membrane", "cell", "outside", "pool_owner"):
        values["regulation_" + key] = np.zeros(capacity, dtype=np.int64)
    by_pump = {
        patch.pump.id: i for i, patch in enumerate(spec.model.membranes) if patch.pump is not None
    }
    by_cell = {cell.id: i for i, cell in enumerate(spec.model.cells)}
    pools = {pool.id: by_cell[pool.cell_id] for pool in spec.model.energy_pools}
    for r, rule in enumerate(rules):
        m = by_pump[rule.pump_id]
        values["regulation_membrane"][r] = m
        values["regulation_cell"][r] = p.membrane_cell[m]
        values["regulation_outside"][r] = p.membrane_outside[m]
        values["regulation_pool_owner"][r] = pools[rule.fuel_pool_id]
    return state, LAYOUT_TYPE(**values)


def sample_concentrations(state, p, *, xp=jnp):
    """Ephemeral [rule,ionic+fuel species,cell/environment] views, never state."""
    bp = base_layout(p)
    inside = base.cytosol_amount(state, bp, xp=xp) / p.volume
    outside = (
        p.extracellular_amount_reference + state.extracellular_amount_increment
    ) / p.extracellular_volume
    fuel = base.energy_amounts(state, bp) / p.volume
    ci = xp.concatenate(
        (inside[:, p.regulation_cell].T, fuel[:, p.regulation_pool_owner].T), axis=-1
    )
    co = xp.concatenate(
        (outside[:, p.regulation_outside].T, xp.zeros((p.regulation_active.size, 3))), axis=-1
    )
    return xp.where(p.regulation_active[:, None, None], xp.stack((ci, co), axis=-1), 0.0)


def regulation_values(state, p, *, xp=jnp):
    samples = sample_concentrations(state, p, xp=xp)
    t, q = topology(p), regulation_parameters(p)
    capacity = p.regulation_active.size

    def evaluate(c, t, q):
        vm = xp.zeros(1)
        controls = modulation.Controls(
            xp.ones(1), xp.ones(1), xp.ones((p.valence.shape[0], 1)), xp.zeros((1, 1))
        )
        factor = modulation.evaluate(c, vm, t, q, xp=xp).value[0, 0]
        valid = modulation.domain_valid(c, vm, controls, t, q, xp=xp)
        return factor, valid

    if not capacity:
        factors, domains = xp.zeros(0), xp.ones(0, dtype=bool)
    elif xp is np:
        rows = [
            evaluate(
                samples[i],
                jax.tree.map(lambda v, i=i: v[i], t),
                jax.tree.map(lambda v, i=i: v[i], q),
            )
            for i in range(capacity)
        ]
        factors, domains = (np.asarray(v) for v in zip(*rows, strict=True))
    else:
        factors, domains = jax.vmap(evaluate)(samples, t, q)
    supported = xp.isfinite(factors) & (factors >= 0) & (factors <= 1)
    valid = xp.all(domains) & xp.all(xp.where(p.regulation_active, supported, factors == 0))
    valid &= xp.all(
        xp.where(p.regulation_active, p.regulation_pool_owner == p.regulation_cell, True)
    )
    multiplier = xp.where(p.pump_present, 1.0, 0.0)
    for i in range(capacity):
        target = p.regulation_active[i] & (
            xp.arange(p.membrane_active.size) == p.regulation_membrane[i]
        )
        multiplier = xp.where(target, factors[i], multiplier)
    return RegulationValues(factors, multiplier, samples, valid)


def effective_control(control, value):
    return control._replace(pump=control.pump * value.pump_factor)


def readouts(state, control, p, *, xp=jnp):
    value = regulation_values(state, p, xp=xp)
    held = effective_control(control, value)
    result = base.readouts(state, held, base_layout(p), xp=xp)
    scheduled = xp.asarray(control.pump)
    valid = (
        result.valid
        & value.valid
        & xp.all(xp.isfinite(scheduled) & (scheduled >= 0) & (scheduled <= 1))
    )
    field = result.field._replace(converged=valid, rates=result.field.rates._replace(valid=valid))
    return Values(
        field,
        result.derivative,
        result.kinetic,
        result.energy,
        result.regeneration,
        result.exchange,
        value,
        held,
        valid,
    )


def rhs(state, control, p, active, *, xp=jnp):
    value = readouts(state, control, p, xp=xp)
    return STATE_TYPE(*(xp.where(value.valid, v, xp.nan) for v in value.derivative))


def field_values(state, control, p, *, xp=jnp):
    return readouts(state, control, p, xp=xp).field


def domain_valid(state, p, active, *, xp=jnp):
    physical = base.domain_valid(state, base_layout(p), active, xp=xp)
    if xp is np:
        return np.asarray(bool(physical) and bool(regulation_values(state, p, xp=np).valid))
    return jax.lax.cond(
        physical, lambda: regulation_values(state, p).valid, lambda: jnp.asarray(False)
    )


def control_domain_valid(state, control, p, active, *, xp=jnp):
    valid = domain_valid(state, p, active, xp=xp)
    if xp is np:
        return np.asarray(bool(valid) and bool(readouts(state, control, p, xp=np).valid))
    return jax.lax.cond(
        valid, lambda: readouts(state, control, p).valid, lambda: jnp.asarray(False)
    )


domain_valid.with_control = control_domain_valid


def batch_signature(model):
    structure = tuple(
        (
            r.id,
            r.pump_id,
            r.fuel_pool_id,
            len(r.configuration.get("activators") or []),
            len(r.configuration.get("inhibitors") or []),
        )
        for r in model.network_regulators
    )
    return (*base.batch_signature(model), structure)


def working_size(spec):
    return base.working_size(base_spec(spec)) + 4096 * spec.execution.regulation_capacity


def check_definition(spec):
    state, p = initial_values(spec)
    table = control_values(spec, [c.time for c in spec.experiment.changes])
    with np.errstate(all="ignore"):
        for i in range(len(spec.experiment.changes)):
            held = type(table)(*(v[i] for v in table))
            if not control_domain_valid(state, held, p, p.active, xp=np):
                raise ConfigError(
                    "Initial state/native factor/scheduled pump outside supported domain"
                )


def check_steps(spec, steps, controls):
    # Scheduled availability bounds dominate every supported factor in [0,1].
    base.check_steps(base_spec(spec), steps, controls)
    check_definition(spec)


def balances(state, p):
    return base.balances(state, base_layout(p))


def check_values(state, spec):
    result = base.check_values(state, base_spec(spec))
    _, p = initial_values(spec)
    rows = (
        [state]
        if state.amount_increment.ndim == 2
        else [STATE_TYPE(*(v[i] for v in state)) for i in range(len(state.amount_increment))]
    )
    for row in rows:
        if not regulation_values(row, p, xp=np).valid:
            raise NumericalError(
                "State-dependent native pump factor outside [0,1] or invalid owner samples"
            )
    return result


def observe_history(times, history, layout, requested, spec):
    p = LAYOUT_TYPE(*(np.asarray(v) for v in layout))
    requested = np.asarray(requested, dtype=float)
    if any(t not in times for t in requested):
        raise ConfigError("Regulated observations require accepted integration boundaries")
    table = control_values(spec, requested)
    records = []
    bs = base_spec(spec)
    for j, time in enumerate(requested):
        i = int(np.flatnonzero(times == time)[0])
        state = STATE_TYPE(*(v[i] for v in history))
        held = type(table)(*(v[j] for v in table))
        value = readouts(state, held, p, xp=np)
        if not value.valid:
            raise NumericalError("Regulated observation factor/state/control outside domain")
        # Ask the unchanged observer to evaluate all inherited physical readouts
        # with this state's effective pump level; the temporary spec owns no state.
        stage_spec = replace(
            bs,
            experiment=replace(
                bs.experiment,
                pumps=tuple(
                    (ChannelChange(0.0, float(a)),)
                    for a in value.effective_control.pump[: len(bs.model.membranes)]
                ),
            ),
        )
        observed = base.observe_history(
            np.asarray([time]),
            STATE_TYPE(*(np.asarray([v]) for v in state)),
            base_layout(p),
            np.asarray([time]),
            stage_spec,
        )
        row = {k: v[0] for k, v in vars(observed).items()}
        row.update(
            nak_regulation_factor=value.regulation.pump_factor,
            nak_effective_availability=value.effective_control.pump,
            nak_scheduled_availability=held.pump,
            network_regulation_factors=value.regulation.rule_factors,
            regulator_samples_mM=value.regulation.samples_mM,
        )
        records.append(row)
    if records:
        return Observations(*(np.stack([row[k] for row in records]) for k in OBSERVATION_FIELDS))
    sample = observe_history(times[:1], STATE_TYPE(*(v[:1] for v in history)), p, times[:1], spec)
    return Observations(
        *(np.empty((0, *v.shape[1:]), dtype=v.dtype) for v in vars(sample).values())
    )


def ensemble_voltage(state, layout, spec, time):
    table = control_values(spec, [time])
    held = type(table)(*(v[0] for v in table))
    value = readouts(state, held, layout, xp=np)
    if not value.valid:
        raise NumericalError("Regulated ensemble endpoint outside domain")
    return value.field.rates.membrane_voltage_V[layout.membrane_active]


def summarize(history, diagnostics, spec):
    return base.summarize(history, diagnostics, base_spec(spec)) | dict(
        model=MODEL_ID,
        state_fields=list(STATE_TYPE._fields),
        network_regulation_law=modulation.LAW_ID,
        network_regulation_timing=TIMING,
        network_regulation_composition=COMPOSITION,
        network_regulator_ids=[r.id for r in spec.model.network_regulators],
        regulator_sample_species=[*spec.model.species_ids, *energy.SPECIES],
        regulator_inventory_role=(
            "Ephemeral concentration reads of existing "
            "free cytosol/exterior and explicitly owned fuel"
        ),
        native_timing_scope=(
            "Source factor equations/ordered replacement only; "
            "Cells common stages differ from native SIM lag/order"
        ),
    )
