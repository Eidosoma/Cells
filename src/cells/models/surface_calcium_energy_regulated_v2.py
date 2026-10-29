"""Common-stage chemical/fuel availability for existing pumps, channels and GJ.

Factors read the 38 inherited physical fields. Native factor arithmetic and
ordered replacement feed existing availability ports; intrinsic channel and
junction gate dynamics and physical inventories remain owned by the parent.
"""

from dataclasses import make_dataclass, replace
from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.specs import ChannelChange, ConfigError
from cells.core.surface_calcium_energy_regulated_v2_spec import (
    CHANNEL,
    CHANNEL_SCOPE,
    COMPOSITION,
    JUNCTION,
    JUNCTION_SCOPE,
    KINDS,
    MODEL_ID,
    NAK,
    TIMING,
    base_spec,
    bind_rule,
    control_values,
)
from cells.models import surface_calcium_energy as base
from cells.models import surface_calcium_energy_regulated as v1
from cells.processes import betse_network_modulation as modulation
from cells.processes import betse_network_reactions as regulator
from cells.processes import finite_energy as energy

STATE_AXES = base.STATE_AXES
STATE_TYPE = base.STATE_TYPE
BATCH_CAPACITIES = (*base.BATCH_CAPACITIES, "regulation_capacity")
OBSERVER_ID = "resolved_calcium_energy_regulated_accepted_grid@2"
STAGE_DOMAIN_ID = "free_state_bounded_consumer_regulation_common_stage@2"
OBSERVATION_SAMPLING = base.OBSERVATION_SAMPLING
ENERGY_ATOL_PJ = base.ENERGY_ATOL_PJ
TOPOLOGY_FIELDS = v1.TOPOLOGY_FIELDS
LAYOUT_TYPE = NamedTuple(
    "SurfaceCalciumEnergyRegulatedV2Layout",
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
            "regulation_kind",
            "regulation_target",
            "regulation_has_exterior",
        )
    ],
)
READOUTS = (
    "nak_regulation_factor",
    "nak_effective_availability",
    "nak_scheduled_availability",
    "channel_regulation_factor",
    "channel_effective_availability",
    "channel_scheduled_availability",
    "junction_regulation_factor",
    "junction_effective_availability",
    "junction_scheduled_availability",
    "network_regulation_factors",
    "regulator_samples_mM",
)
OBSERVATION_FIELDS = (*base.OBSERVATION_FIELDS, *READOUTS)
Observations = make_dataclass(
    "SurfaceCalciumEnergyRegulatedV2Observations",
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
    channel_factor: object
    junction_factor: object
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


base_layout = v1.base_layout
_flat_topology = v1._flat_topology
topology = v1.topology
regulation_parameters = v1.regulation_parameters


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
    bound = [bind_rule(rule, spec.model) for rule in rules]
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
    by_pump = {m.pump.id: i for i, m in enumerate(spec.model.membranes) if m.pump is not None}
    by_channel = {c.id: i for i, c in enumerate(spec.model.channels)}
    by_junction = {j.id: i for i, j in enumerate(spec.model.junctions)}
    by_cell = {c.id: i for i, c in enumerate(spec.model.cells)}
    by_outside = {c.id: i for i, c in enumerate(spec.model.extracellular)}
    pools = {pool.id: by_cell[pool.cell_id] for pool in spec.model.energy_pools}
    values["regulation_kind"] = np.zeros(capacity, dtype=np.int64)
    values["regulation_target"] = np.zeros(capacity, dtype=np.int64)
    values["regulation_has_exterior"] = np.zeros(capacity, dtype=bool)
    for r, rule in enumerate(rules):
        kind = KINDS[rule.kind]
        target = {NAK: by_pump, CHANNEL: by_channel, JUNCTION: by_junction}[kind][rule.target_id]
        values["regulation_kind"][r] = kind
        values["regulation_target"][r] = target
        values["regulation_cell"][r] = by_cell[rule.sample_cell_id]
        values["regulation_pool_owner"][r] = pools[rule.fuel_pool_id]
        if kind != JUNCTION:
            membrane = target if kind == NAK else p.channel_membranes[target]
            values["regulation_membrane"][r] = membrane
            values["regulation_outside"][r] = by_outside[rule.sample_exterior_id]
            values["regulation_has_exterior"][r] = True
    return state, LAYOUT_TYPE(**values)


def sample_concentrations(state, p, *, xp=jnp):
    samples = v1.sample_concentrations(state, p, xp=xp)
    # A junction has no invented membrane/exterior mapping. Its absent exterior
    # view is zero and the schema forbids selecting it in a native expression.
    mask = (xp.arange(2)[None, None, :] == 0) | p.regulation_has_exterior[:, None, None]
    return xp.where(mask, samples, 0.0)


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
    multipliers = []
    for kind, active in (
        (NAK, p.pump_present),
        (CHANNEL, p.channel_active),
        (JUNCTION, p.junction_active),
    ):
        multiplier = xp.where(active, 1.0, 0.0)
        for i in range(capacity):
            selected = (
                p.regulation_active[i]
                & (p.regulation_kind[i] == kind)
                & (xp.arange(active.size) == p.regulation_target[i])
            )
            multiplier = xp.where(selected, factors[i], multiplier)
        multipliers.append(multiplier)
    return RegulationValues(factors, *multipliers, samples, valid)


def effective_control(control, value):
    return control._replace(
        pump=control.pump * value.pump_factor,
        channel=control.channel * value.channel_factor,
        junction=control.junction * value.junction_factor,
    )


def readouts(state, control, p, *, xp=jnp):
    value = regulation_values(state, p, xp=xp)
    held = effective_control(control, value)
    result = base.readouts(state, held, base_layout(p), xp=xp)
    scheduled = xp.concatenate(
        tuple(xp.ravel(v) for v in (control.pump, control.channel, control.junction))
    )
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
            r.kind,
            r.target_id,
            r.sample_cell_id,
            r.sample_exterior_id,
            r.fuel_pool_id,
            len(
                r.configuration.get(("channel " if r.kind == "channel" else "") + "activators")
                or []
            ),
            len(
                r.configuration.get(("channel " if r.kind == "channel" else "") + "inhibitors")
                or []
            ),
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
                    "Initial state/native factor/scheduled consumer outside supported domain"
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
                "State-dependent native factor outside [0,1] or invalid owner samples"
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
        # with this state's effective consumer levels; the temporary spec owns no state.
        stage_spec = replace(
            bs,
            experiment=replace(
                bs.experiment,
                channels=tuple(
                    (ChannelChange(0.0, float(a)),)
                    for a in value.effective_control.channel[: len(bs.model.channels)]
                ),
                junctions=tuple(
                    (ChannelChange(0.0, float(a)),)
                    for a in value.effective_control.junction[: len(bs.model.junctions)]
                ),
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
            channel_regulation_factor=value.regulation.channel_factor,
            channel_effective_availability=value.effective_control.channel,
            channel_scheduled_availability=held.channel,
            junction_regulation_factor=value.regulation.junction_factor,
            junction_effective_availability=value.effective_control.junction,
            junction_scheduled_availability=held.junction,
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
        channel_scope=CHANNEL_SCOPE,
        junction_scope=JUNCTION_SCOPE,
        extra_regulation_ATP_cost_fmol=0.0,
        native_channel_equivalence=(
            "factor equations only; no native core.modulator/outer DChan double action"
        ),
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
