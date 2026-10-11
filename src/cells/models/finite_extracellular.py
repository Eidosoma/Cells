"""Finite shared extracellular inventory, sparse junctions and local membrane laws.

State owns increments from immutable amount anchors. Voltage is derived directly
from those increments. One membrane transfer updates its two owners; junctions
never touch the outside. No reference imports, private baths or conservation repair.
"""

import math
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core.errors import NumericalError
from cells.core.schedule import PhysicalIonicGraphControl, control_values
from cells.core.specs import ConfigError
from cells.core.state import FiniteExtracellularLayout, FiniteExtracellularState
from cells.coupling.selective import gate_target, selective_flux
from cells.models import multispecies_membrane as ionic
from cells.models import physical_ionic_graph as graph
from cells.models import voltage_gated_membrane as gated
from cells.observers import hermite_bounds, sample_hermite_history
from cells.processes.electrochemistry import (
    CHARGE_PER_FMOL,
    MOL_PER_FMOL,
    F,
    R,
    electrochemical_potential,
    ghk_leak,
    reversible_pump,
)
from cells.processes.voltage_gates import TEMPERATURE_K, VOLTAGE_DOMAIN_V, kinetics

STATE_TYPE = FiniteExtracellularState
LAYOUT_TYPE = FiniteExtracellularLayout
OBSERVER_ID = "finite_extracellular_physical_readouts@1"
OBSERVATION_SAMPLING = ionic.OBSERVATION_SAMPLING
STAGE_DOMAIN_ID = "positive_finite_compartments_unit_gates_all_valence_domains_countercharge@1"
MAX_STEP = 0.001
MAX_ABS_X = 50.0
CHARGE_TOLERANCE_C = 1e-20
BATCH_CAPACITIES = ("channel_capacity", "extracellular_capacity")
STATE_AXES = {
    "amount_increment": ["species", "cell_slot"],
    **{k: v for k, v in graph.STATE_AXES.items() if k != "amount"},
    "extracellular_amount_increment": ["species", "extracellular_slot"],
}
batch_signature = ionic.batch_signature
parameters = ionic.parameters


def working_size(spec):
    """Conservative array-buffer reservation; not compiler/OS memory or a speed claim."""
    return (
        graph.working_size(spec)
        + (64 * len(spec.model.species_ids) + 160) * spec.execution.extracellular_capacity
    )


def initial_countercharge(model):
    c = model.extracellular
    outside = CHARGE_PER_FMOL * math.fsum(
        (
            c.fixed_charge_equivalent_fmol,
            *(z * n for z, n in zip(model.valence, c.initial_amount_fmol, strict=True)),
        )
    )
    return math.fsum(
        (
            outside,
            *(
                p.area_m2 * p.specific_capacitance_F_per_m2 * p.initial_voltage_V
                for p in model.membranes
            ),
        )
    )


def check_definition(model, *, junction_check=None, outside_compartments=None):
    """Derived finite-float64 and charge checks before capacity-sized allocations."""

    def positive_finite(value):
        if not math.isfinite(value) or value <= 0:
            raise ConfigError("Derived positive physical coefficient exceeds finite float64")
        return value

    def finite(value):
        if not math.isfinite(value):
            raise ConfigError("Derived physical coefficient exceeds finite float64")
        return value

    rt = positive_finite(R * model.temperature_K)
    positive_finite(2 * rt)
    outsides = (model.extracellular,) if outside_compartments is None else outside_compartments
    charges = []
    for c in (*model.cells, *outsides):
        positive_finite(1 / c.volume_pL)
        for n in c.initial_amount_fmol:
            positive_finite(n / c.volume_pL)
        charges.append(
            finite(
                CHARGE_PER_FMOL
                * math.fsum(
                    (
                        c.fixed_charge_equivalent_fmol,
                        *(z * n for z, n in zip(model.valence, c.initial_amount_fmol, strict=True)),
                    )
                )
            )
        )
    ids = [c.id for c in model.cells]
    mids = [p.id for p in model.membranes]
    for i, p in enumerate(model.membranes):
        cap = positive_finite(p.area_m2 * p.specific_capacitance_F_per_m2)
        positive_finite(CHARGE_PER_FMOL / cap)
        if abs(finite(charges[i] / cap) - p.initial_voltage_V) > 1e-10:
            raise ConfigError("Cell charge and declared voltage anchor disagree")
        for z in model.valence:
            if abs(finite(z * F * p.initial_voltage_V / rt)) > MAX_ABS_X:
                raise ConfigError("Initial membrane voltage exceeds all-valence domain")
        for permeability in p.permeability_m_per_s:
            finite(p.area_m2 * permeability / MOL_PER_FMOL)
    for c in model.channels:
        p = model.membranes[mids.index(c.membrane_id)]
        if (
            model.temperature_K != TEMPERATURE_K
            or not VOLTAGE_DOMAIN_V[0] <= p.initial_voltage_V <= VOLTAGE_DOMAIN_V[1]
        ):
            raise ConfigError("Channel requires 298.15 K and voltage in [-0.120, 0.060] V")
        finite(c.max_permeability_m_per_s * c.abundance)
        finite(p.area_m2 * c.max_permeability_m_per_s * c.abundance / MOL_PER_FMOL)
    for e in model.junctions:
        a, b = (model.membranes[ids.index(k)] for k in (e.from_cell, e.to_cell))
        for z in model.valence:
            if abs(finite(z * F * (a.initial_voltage_V - b.initial_voltage_V) / rt)) > MAX_ABS_X:
                raise ConfigError("Initial junction voltage exceeds all-valence domain")
        for p in e.permeability_m_per_s:
            finite(e.area_m2 * p / MOL_PER_FMOL)
        if junction_check is None:
            positive_finite(1 / e.tau_s)
            finite(e.sensitivity_per_V * (MAX_ABS_X * rt / F + e.half_voltage_V))
        else:
            junction_check(e, a.initial_voltage_V - b.initial_voltage_V)
    if outside_compartments is not None:
        for outside, charge in zip(outsides, charges[len(model.cells) :], strict=True):
            residual = math.fsum(
                (
                    charge,
                    *(
                        p.area_m2 * p.specific_capacitance_F_per_m2 * p.initial_voltage_V
                        for p in model.membranes
                        if p.outside == outside.id
                    ),
                )
            )
            if abs(residual) > CHARGE_TOLERANCE_C:
                raise ConfigError("Each outside charge must oppose its own membrane capacitors")
    elif (
        abs(initial_countercharge(model)) > CHARGE_TOLERANCE_C
        or abs(math.fsum(charges)) > CHARGE_TOLERANCE_C
    ):
        raise ConfigError(
            "Finite outside charge must oppose the membrane capacitors; no neutralization repair"
        )


def initial_values(spec):
    state, values = bind_geometry(spec)
    for i, p in enumerate(spec.model.membranes):
        values["stoichiometry"][:, i] = p.stoichiometry
        values["pump_capacity"][i] = p.capacity_fmol_per_s
        values["pump_drive"][i] = p.drive_J_per_mol
    return state, LAYOUT_TYPE(**values)


def bind_geometry(spec, *, bind_junction=None):
    """Common finite inventory layout; the composing model binds its own pump."""
    m, x = spec.model, spec.execution
    s, n, k, e = len(m.species_ids), len(m.cells), len(m.channels), len(m.junctions)
    nc, nm, nk, ne, no = (
        x.capacity,
        x.membrane_capacity,
        x.channel_capacity,
        x.edge_capacity,
        x.extracellular_capacity,
    )
    values = {}
    for name, capacity in (
        ("active", nc),
        ("membrane_active", nm),
        ("channel_active", nk),
        ("junction_active", ne),
        ("extracellular_active", no),
    ):
        count = {
            "active": n,
            "membrane_active": n,
            "channel_active": k,
            "junction_active": e,
            "extracellular_active": 1,
        }[name]
        values[name] = np.arange(capacity) < count
    for key, active in (
        ("ids", "active"),
        ("membrane_ids", "membrane_active"),
        ("channel_ids", "channel_active"),
        ("junction_ids", "junction_active"),
        ("extracellular_ids", "extracellular_active"),
    ):
        mask = values[active]
        values[key] = np.where(mask, np.arange(len(mask)) + 1, -1).astype(np.int64)
    values.update(
        species_codes=np.arange(1, s + 1, dtype=np.int64),
        valence=np.asarray(m.valence, dtype=np.int64)[:, None],
        stoichiometry=np.zeros((s, nm), dtype=np.int64),
        amount_reference=np.zeros((s, nc)),
        permeability=np.zeros((s, nm)),
        temperature=np.full(no, m.temperature_K),
        extracellular_amount_reference=np.zeros((s, no)),
        junction_permeability=np.zeros((s, ne)),
        initial_countercharge_C=np.asarray(initial_countercharge(m)),
    )
    for name, size in (
        ("owners", nm),
        ("outside_owners", nm),
        ("cell_membranes", nc),
        ("channel_membranes", nk),
        ("channel_species", nk),
        ("senders", ne),
        ("receivers", ne),
    ):
        values[name] = np.zeros(size, dtype=np.int64)
    values["channel_laws"] = np.where(values["channel_active"], 1, -1).astype(np.int64)
    for name, size, fill in (
        ("volume", nc, 1),
        ("voltage_reference", nc, 0),
        ("fixed_charge_equivalent", nc, 0),
        ("area", nm, 1),
        ("specific_capacitance", nm, 1),
        ("capacitance", nm, 1),
        ("pump_capacity", nm, 0),
        ("pump_drive", nm, 0),
        ("channel_permeability", nk, 0),
        ("channel_abundance", nk, 0),
        ("junction_area", ne, 1),
        ("extracellular_volume", no, 1),
        ("extracellular_fixed_charge_equivalent", no, 0),
    ):
        values[name] = np.full(size, fill, dtype=np.float64)
    if bind_junction is None:
        values.update(
            junction_residual=np.zeros((s, ne)),
            junction_sensitivity=np.ones(ne),
            junction_half_voltage=np.zeros(ne),
            junction_tau=np.ones(ne),
        )
    for i, (cell, p) in enumerate(zip(m.cells, m.membranes, strict=True)):
        values["amount_reference"][:, i] = cell.initial_amount_fmol
        values["permeability"][:, i] = p.permeability_m_per_s
        for name, value in (
            ("volume", cell.volume_pL),
            ("fixed_charge_equivalent", cell.fixed_charge_equivalent_fmol),
            ("voltage_reference", p.initial_voltage_V),
            ("owners", i),
            ("cell_membranes", i),
            ("area", p.area_m2),
            ("specific_capacitance", p.specific_capacitance_F_per_m2),
            ("capacitance", p.area_m2 * p.specific_capacitance_F_per_m2),
        ):
            values[name][i] = value
    outside = m.extracellular
    values["extracellular_amount_reference"][:, 0] = outside.initial_amount_fmol
    values["extracellular_volume"][0] = outside.volume_pL
    values["extracellular_fixed_charge_equivalent"][0] = outside.fixed_charge_equivalent_fmol
    gate, junction_gate = np.zeros((2, nk)), np.zeros(ne)
    mids, cids = [p.id for p in m.membranes], [c.id for c in m.cells]
    for i, c in enumerate(m.channels):
        values["channel_membranes"][i] = mids.index(c.membrane_id)
        values["channel_species"][i] = m.species_ids.index(c.species_id)
        values["channel_permeability"][i], values["channel_abundance"][i] = (
            c.max_permeability_m_per_s,
            c.abundance,
        )
        gate[:, i] = c.initial_gate
    for i, p in enumerate(m.junctions):
        for key, value in (
            ("senders", cids.index(p.from_cell)),
            ("receivers", cids.index(p.to_cell)),
            ("junction_area", p.area_m2),
        ):
            values[key][i] = value
        values["junction_permeability"][:, i] = p.permeability_m_per_s
        if bind_junction is None:
            values["junction_residual"][:, i] = p.residual_fraction
            values["junction_sensitivity"][i] = p.sensitivity_per_V
            values["junction_half_voltage"][i] = p.half_voltage_V
            values["junction_tau"][i] = p.tau_s
        junction_gate[i] = p.initial_gate
    if bind_junction is not None:
        bind_junction(spec, values)
    return STATE_TYPE(
        np.zeros((s, nc)),
        np.zeros((s, nm)),
        np.zeros(nm),
        np.zeros(nm),
        gate,
        np.zeros(nk),
        junction_gate,
        np.zeros((s, ne)),
        np.zeros(ne),
        np.zeros((s, no)),
    ), values


def cell_voltage(increment, layout, *, xp=jnp):
    cap = layout.capacitance[layout.cell_membranes]
    return xp.where(
        layout.active,
        layout.voltage_reference
        + CHARGE_PER_FMOL / cap * xp.sum(layout.valence * increment, axis=-2),
        0.0,
    )


def membrane_voltage(increment, layout, *, xp=jnp):
    return xp.where(
        layout.membrane_active, cell_voltage(increment, layout, xp=xp)[..., layout.owners], 0.0
    )


def physical_amounts(state, layout):
    return (
        # Composed intracellular chemistry owns free cytosolic amounts. Its
        # spatial amount_increment is a whole-cell transport ledger used for
        # capacitor charge, not a second free-ion inventory.
        layout.cytosol_amount
        if hasattr(layout, "cytosol_amount")
        else layout.amount_reference + state.amount_increment,
        layout.extracellular_amount_reference + state.extracellular_amount_increment,
    )


def readouts(state, control, layout, *, xp=jnp):
    ci, co, voltage, temp, leak, mu = passive_readouts(state, control, layout, xp=xp)
    cycles, affinity = reversible_pump(
        mu,
        layout.stoichiometry,
        layout.pump_drive,
        temp,
        layout.pump_capacity,
        control[..., -1, :],
        xp=xp,
    )
    return tuple(
        xp.where(layout.membrane_active, v, 0.0) for v in (voltage, leak, cycles, mu, affinity)
    )


def membrane_inputs(state, layout, *, xp=jnp):
    amount, outside = physical_amounts(state, layout)
    active, owners, out = layout.membrane_active, layout.owners, layout.outside_owners
    ci = xp.where(active, amount[..., :, owners], 1.0) / xp.where(
        active, layout.volume[owners], 1.0
    )
    co = xp.where(active, outside[..., :, out], 1.0) / xp.where(
        active, layout.extracellular_volume[out], 1.0
    )
    voltage = membrane_voltage(state.amount_increment, layout, xp=xp)
    temp = layout.temperature[out]
    return ci, co, voltage, temp


def passive_readouts(state, control, layout, *, xp=jnp):
    ci, co, voltage, temp = membrane_inputs(state, layout, xp=xp)
    leak = ghk_leak(
        ci,
        co,
        voltage[..., None, :],
        layout.valence,
        temp,
        layout.area,
        layout.permeability,
        control[..., :-1, :],
        xp=xp,
    )
    mu = electrochemical_potential(ci, co, voltage[..., None, :], layout.valence, temp, xp=xp)
    return ci, co, voltage, temp, leak, mu


def channel_readouts(state, availability, layout, *, xp=jnp):
    active, membranes, species = (
        layout.channel_active,
        layout.channel_membranes,
        layout.channel_species,
    )
    owners, out = layout.owners[membranes], layout.outside_owners[membranes]
    amount, outside = physical_amounts(state, layout)
    voltage = xp.where(
        active, membrane_voltage(state.amount_increment, layout, xp=xp)[..., membranes], 0.0
    )
    ci = xp.where(active, amount[..., species, owners], 1.0) / xp.where(
        active, layout.volume[owners], 1.0
    )
    co = xp.where(active, outside[..., species, out], 1.0) / xp.where(
        active, layout.extracellular_volume[out], 1.0
    )
    targets, tau = kinetics(voltage, xp=xp)
    gate = xp.where(active, state.gate, 0.0)
    rate, opened = (targets - gate) / tau, gate[..., 0, :] * gate[..., 1, :]
    permeability = layout.channel_permeability * layout.channel_abundance * availability * opened
    valence, temperature = layout.valence[species, 0], layout.temperature[out]
    flux = ghk_leak(
        ci, co, voltage, valence, temperature, layout.area[membranes], permeability, 1.0, xp=xp
    )
    mu = electrochemical_potential(ci, co, voltage, valence, temperature, xp=xp)
    return gated.ChannelReadouts(
        *(
            xp.where(active, v, 0.0)
            for v in (targets, tau, rate, opened, permeability, flux, mu, -1e-3 * flux * mu)
        )
    )


def junction_readouts(state, availability, layout, *, xp=jnp, gate_kinetics=None):
    active, src, dst = layout.junction_active, layout.senders, layout.receivers
    amount, _ = physical_amounts(state, layout)
    voltage = cell_voltage(state.amount_increment, layout, xp=xp)
    dv = xp.where(active, voltage[..., src] - voltage[..., dst], 0.0)
    ca = xp.where(active, amount[..., :, src], 1.0) / xp.where(active, layout.volume[src], 1.0)
    cb = xp.where(active, amount[..., :, dst], 1.0) / xp.where(active, layout.volume[dst], 1.0)
    gate = xp.where(active, state.junction_gate, 0.0)
    if gate_kinetics is None:
        target = gate_target(dv, layout.junction_sensitivity, layout.junction_half_voltage, xp=xp)
        rate = (target - gate) / layout.junction_tau
        residual = layout.junction_residual
    else:
        target, rate, residual = gate_kinetics(gate, dv, layout, xp=xp)
    opened = residual + (1 - residual) * gate[..., None, :]
    effective = layout.junction_permeability * availability[..., None, :] * opened
    flux = selective_flux(
        ca,
        cb,
        dv[..., None, :],
        layout.valence,
        layout.temperature[0],
        layout.junction_area,
        layout.junction_permeability,
        residual,
        gate[..., None, :],
        availability[..., None, :],
        xp=xp,
    )
    mu = (
        R * layout.temperature[0] * (xp.log(cb) - xp.log(ca))
        - layout.valence * F * dv[..., None, :]
    )
    return graph.JunctionReadouts(
        *(
            xp.where(active, v, 0.0)
            for v in (
                dv,
                target,
                rate,
                opened,
                effective,
                flux,
                mu,
                CHARGE_PER_FMOL * xp.sum(layout.valence * flux, axis=-2),
                -1e-3 * xp.sum(flux * mu, axis=-2),
            )
        )
    )


def rhs(state, control, layout, active, *, xp=jnp):
    _, leak, cycles, mu, affinity = readouts(state, control.membrane, layout, xp=xp)
    channel = channel_readouts(state, control.channel, layout, xp=xp)
    edge = junction_readouts(state, control.junction, layout, xp=xp)
    return assemble_rhs(state, layout, active, leak, cycles, mu, affinity, channel, edge, xp=xp)


def assemble_rhs(state, layout, active, leak, cycles, mu, affinity, channel, edge, *, xp=jnp):
    """One conservative membrane scatter and separate internal-junction ownership."""
    membrane_flux = (
        leak
        + layout.stoichiometry * cycles[..., None, :]
        + gated.channel_species(channel.flux_fmol_per_s, leak, layout, xp=xp)
    )
    amount = gated.scatter(
        membrane_flux, state.amount_increment, (layout.owners,), xp=xp
    ) + graph.scatter_edges(edge.flux_fmol_per_s, state.amount_increment, layout, xp=xp)
    # Ownership, not a subtraction of all intracellular changes: internal edges
    # have no outside contribution, including at floating-point precision.
    outside = gated.scatter(
        -membrane_flux, state.extracellular_amount_increment, (layout.outside_owners,), xp=xp
    )
    dissipation = ionic.dissipation_rate(leak, cycles, mu, affinity, xp=xp) + gated.scatter(
        channel.dissipation_rate_pJ_per_s,
        state.dissipated_energy_pJ,
        (layout.channel_membranes,),
        xp=xp,
    )
    return STATE_TYPE(
        xp.where(active, amount, 0.0),
        leak,
        cycles,
        dissipation,
        channel.gate_rate_per_s,
        channel.flux_fmol_per_s,
        edge.gate_rate_per_s,
        edge.flux_fmol_per_s,
        edge.dissipation_rate_pJ_per_s,
        outside,
    )


def countercharge(state, layout, *, xp=np, derivative=False):
    charge = CHARGE_PER_FMOL * xp.sum(
        layout.valence[:, 0]
        * (
            xp.sum(state.amount_increment, axis=-1)
            + xp.sum(state.extracellular_amount_increment, axis=-1)
        ),
        axis=-1,
    )
    return charge if derivative else charge + layout.initial_countercharge_C


def domain_valid(state, layout, active, *, xp=jnp):
    valid = xp.asarray(True)
    masks = (
        active,
        layout.membrane_active,
        layout.membrane_active,
        layout.membrane_active,
        layout.channel_active,
        layout.channel_active,
        layout.junction_active,
        layout.junction_active,
        layout.junction_active,
        layout.extracellular_active,
    )
    for value, mask in zip(state, masks, strict=True):
        valid = valid & xp.all(xp.isfinite(value)) & xp.all(xp.where(mask, True, value == 0))
    for amount, mask, volume in zip(
        physical_amounts(state, layout),
        (active, layout.extracellular_active),
        (layout.volume, layout.extracellular_volume),
        strict=True,
    ):
        concentration = amount / volume
        valid = (
            valid
            & xp.all(xp.isfinite(concentration))
            & xp.all(xp.where(mask, (amount > 0) & (concentration > 0), amount == 0))
        )
    for gate in (state.gate, state.junction_gate):
        valid = valid & xp.all((gate >= 0) & (gate <= 1))
    for possible, history in (
        (layout.permeability != 0, state.leak_transferred),
        (layout.pump_capacity != 0, state.pump_cycles),
        (
            (layout.channel_permeability != 0) & (layout.channel_abundance != 0),
            state.channel_transferred,
        ),
        (layout.junction_permeability != 0, state.junction_transferred),
    ):
        valid = valid & xp.all(xp.where(possible, True, history == 0))
    channel_possible = (
        gated.scatter(
            xp.where(
                (layout.channel_permeability != 0) & (layout.channel_abundance != 0), 1.0, 0.0
            ),
            layout.pump_capacity,
            (layout.channel_membranes,),
            xp=xp,
        )
        != 0
    )
    for possible, history in (
        (
            xp.any(layout.permeability != 0, axis=-2)
            | (layout.pump_capacity != 0)
            | channel_possible,
            state.dissipated_energy_pJ,
        ),
        (xp.any(layout.junction_permeability != 0, axis=-2), state.junction_dissipated_energy_pJ),
    ):
        valid = valid & xp.all(xp.where(possible, True, history == 0))
    voltage = cell_voltage(state.amount_increment, layout, xp=xp)
    for v in (voltage, voltage[..., layout.senders] - voltage[..., layout.receivers]):
        x = layout.valence * F * v[..., None, :] / (R * layout.temperature[0])
        valid = valid & xp.all(xp.isfinite(x) & (xp.abs(x) <= MAX_ABS_X))
    v = voltage[..., layout.owners[layout.channel_membranes]]
    valid = valid & xp.all(
        xp.where(
            layout.channel_active, (v >= VOLTAGE_DOMAIN_V[0]) & (v <= VOLTAGE_DOMAIN_V[1]), True
        )
    )
    q = countercharge(state, layout, xp=xp)
    return valid & xp.all(xp.isfinite(q) & (xp.abs(q) <= CHARGE_TOLERANCE_C))


def check_steps(spec, steps, controls):
    if np.max(steps, initial=0) > MAX_STEP + 16 * np.finfo(float).eps:
        raise ConfigError(
            "Finite extracellular model requires actual RK4 steps <= 0.001 s; "
            "new regimes need qualification"
        )
    state, layout = initial_values(spec)
    held = control_values(spec, [p.time for p in spec.experiment.changes])
    with np.errstate(over="ignore", invalid="ignore", divide="ignore", under="ignore"):
        for i in range(len(held.membrane)):
            c = PhysicalIonicGraphControl(*(v[i] for v in held))
            slope = rhs(state, c, layout, layout.active, xp=np)
            values = (
                *readouts(state, c.membrane, layout, xp=np),
                *channel_readouts(state, c.channel, layout, xp=np),
                *junction_readouts(state, c.junction, layout, xp=np),
            )
            if not domain_valid(state, layout, layout.active, xp=np) or not all(
                np.isfinite(v).all() for v in (*slope, *values)
            ):
                raise ConfigError(
                    "Initial finite-compartment state/rates/readouts violate physical domains"
                )


def membrane_exchange(state, layout):
    return (
        state.leak_transferred
        + layout.stoichiometry * state.pump_cycles[..., None, :]
        + gated.channel_species(state.channel_transferred, state.leak_transferred, layout)
    )


def balances(state, layout):
    local = membrane_exchange(state, layout)
    delta, outside_delta = state.amount_increment, state.extracellular_amount_increment
    material = (
        delta
        - gated.scatter(local, delta, (layout.owners,), xp=np)
        - graph.scatter_edges(state.junction_transferred, delta, layout)
    )
    outside_material = outside_delta + gated.scatter(
        local, outside_delta, (layout.outside_owners,), xp=np
    )
    global_material = np.sum(delta, axis=-1) + np.sum(outside_delta, axis=-1)
    cap = layout.capacitance[layout.cell_membranes]
    charge = np.where(
        layout.active, CHARGE_PER_FMOL / cap * np.sum(layout.valence * material, axis=-2), 0.0
    )
    dv = np.where(
        layout.active, CHARGE_PER_FMOL / cap * np.sum(layout.valence * delta, axis=-2), 0.0
    )
    chemical = 0.0
    # Both finite chemical inventories; no time-varying maintained-bath grand potential.
    for increment, reference, volume, mask in (
        (delta, layout.amount_reference, layout.volume, layout.active),
        (
            outside_delta,
            layout.extracellular_amount_reference,
            layout.extracellular_volume,
            layout.extracellular_active,
        ),
    ):
        n0 = np.where(mask, reference, 1.0)
        n = n0 + increment
        chemical = chemical + 1e-3 * R * layout.temperature[0] * np.sum(
            increment * (np.log(n0 / volume) - 1) + n * np.log1p(increment / n0), axis=(-2, -1)
        )
    electric = 0.5e12 * np.sum(cap * dv * (2 * layout.voltage_reference + dv), axis=-1)
    work = -1e-3 * np.sum(layout.pump_drive * state.pump_cycles, axis=-1)
    energy = (
        chemical
        + electric
        + np.sum(state.dissipated_energy_pJ, axis=-1)
        + np.sum(state.junction_dissipated_energy_pJ, axis=-1)
        - work
    )
    return material, outside_material, charge, energy, global_material, countercharge(state, layout)


def check_values(state, spec):
    _, layout = initial_values(spec)
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        valid = domain_valid(state, layout, layout.active, xp=np)
    return check_accounting(state, spec, layout, valid)


def check_accounting(
    state,
    spec,
    layout,
    valid,
    *,
    balances=balances,
    dissipation_fields=("dissipated_energy_pJ", "junction_dissipated_energy_pJ"),
):
    with np.errstate(over="ignore", invalid="ignore", divide="ignore"):
        if not valid:
            raise NumericalError(
                "Invalid finite-compartment state/domain; no clipping or inventory repair"
            )
        material, outside, charge, energy, global_material, q = balances(state, layout)
        tol = np.asarray(spec.execution.material_balance_atol_fmol)
        failed = (
            np.any(np.abs(material) > tol[:, None])
            or np.any(np.abs(outside) > tol[:, None])
            or np.any(np.abs(global_material) > tol)
        )
        maxima = [
            float(np.max(np.abs(v), initial=0))
            for v in (material, outside, charge, energy, global_material, q)
        ]
    if (
        failed
        or not np.isfinite(maxima).all()
        or maxima[2] > 1e-8
        or maxima[3] > 1e-6
        or maxima[5] > CHARGE_TOLERANCE_C
    ):
        raise NumericalError(
            "Finite local/outside/global material, charge or resolved-energy accounting failed"
        )
    for name in dissipation_fields:
        d = getattr(state, name)
        if np.min(d, initial=0) < -1e-10 or (
            d.ndim > 1 and np.min(np.diff(d, axis=0), initial=0) < -1e-10
        ):
            raise NumericalError("Membrane/junction diagnostic dissipation must not decrease")
    return dict(
        zip(
            (
                "max_balance_error_fmol",
                "max_extracellular_balance_error_fmol",
                "max_charge_balance_error_V",
                "max_energy_balance_error_pJ",
                "max_global_balance_error_fmol",
                "max_countercharge_error_C",
            ),
            maxima,
            strict=True,
        )
    )


def check_interpolants(times, history, f0, f1, layout):
    if len(times) < 2:
        return
    for field, anchor, mask in (
        ("amount_increment", layout.amount_reference, layout.active),
        (
            "extracellular_amount_increment",
            layout.extracellular_amount_reference,
            layout.extracellular_active,
        ),
    ):
        lo, hi = hermite_bounds(
            times, getattr(history, field), getattr(f0, field), getattr(f1, field)
        )
        if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
            (lo + anchor)[..., mask] <= 0
        ):
            raise NumericalError("Cubic interior violates positive finite inventory")
    for field, mask in (("gate", layout.channel_active), ("junction_gate", layout.junction_active)):
        lo, hi = hermite_bounds(
            times, getattr(history, field), getattr(f0, field), getattr(f1, field)
        )
        if (
            np.any(lo[..., mask] < 0)
            or np.any(hi[..., mask] > 1)
            or not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all()
        ):
            raise NumericalError("Cubic interior violates unit gate domain")
    v = cell_voltage(history.amount_increment, layout, xp=np)
    cap = layout.capacitance[layout.cell_membranes]
    slopes = [
        np.where(
            layout.active,
            CHARGE_PER_FMOL / cap * np.sum(layout.valence * f.amount_increment, axis=-2),
            0.0,
        )
        for f in (f0, f1)
    ]
    lo, hi = hermite_bounds(times, v, *slopes)
    bound = MAX_ABS_X * R * layout.temperature[0] / (F * np.max(np.abs(layout.valence)))
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > bound
    ):
        raise NumericalError("Cubic interior exceeds all-valence membrane voltage domain")
    indices = layout.owners[layout.channel_membranes[layout.channel_active]]
    if np.any(lo[..., indices] < VOLTAGE_DOMAIN_V[0]) or np.any(
        hi[..., indices] > VOLTAGE_DOMAIN_V[1]
    ):
        raise NumericalError("Cubic interior exceeds channel voltage domain")
    lo, hi = hermite_bounds(
        times,
        v[..., layout.senders] - v[..., layout.receivers],
        *(f[..., layout.senders] - f[..., layout.receivers] for f in slopes),
    )
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > bound
    ):
        raise NumericalError("Cubic interior exceeds all-valence junction voltage domain")
    lo, hi = hermite_bounds(
        times,
        countercharge(history, layout),
        *(countercharge(f, layout, derivative=True) for f in (f0, f1)),
    )
    if not np.isfinite(np.r_[lo.ravel(), hi.ravel()]).all() or np.any(
        np.maximum(np.abs(lo), np.abs(hi)) > CHARGE_TOLERANCE_C
    ):
        raise NumericalError("Cubic interior violates finite outside countercharge")


@dataclass(frozen=True)
class Observations:
    times: np.ndarray
    amount_increment: np.ndarray
    leak_transferred: np.ndarray
    pump_cycles: np.ndarray
    dissipated_energy_pJ: np.ndarray
    gate: np.ndarray
    channel_transferred: np.ndarray
    junction_gate: np.ndarray
    junction_transferred: np.ndarray
    junction_dissipated_energy_pJ: np.ndarray
    extracellular_amount_increment: np.ndarray
    amount: np.ndarray
    concentration_mM: np.ndarray
    extracellular_amount: np.ndarray
    extracellular_concentration_mM: np.ndarray
    voltage_V: np.ndarray
    leak_multiplier: np.ndarray
    pump_multiplier: np.ndarray
    leak_flux_fmol_per_s: np.ndarray
    pump_cycles_per_s: np.ndarray
    pump_flux_fmol_per_s: np.ndarray
    delta_mu_J_per_mol: np.ndarray
    pump_affinity_J_per_mol: np.ndarray
    membrane_current_A: np.ndarray
    pump_power_W: np.ndarray
    pump_work_J: np.ndarray
    dissipation_rate_pJ_per_s: np.ndarray
    extracellular_rate_fmol_per_s: np.ndarray
    species_balance_fmol: np.ndarray
    extracellular_species_balance_fmol: np.ndarray
    charge_balance_V: np.ndarray
    energy_balance_pJ: np.ndarray
    global_species_balance_fmol: np.ndarray
    countercharge_C: np.ndarray
    channel_availability: np.ndarray
    channel_gate_inf: np.ndarray
    channel_gate_tau_s: np.ndarray
    channel_gate_rate_per_s: np.ndarray
    channel_open_probability: np.ndarray
    channel_effective_permeability_m_per_s: np.ndarray
    channel_flux_fmol_per_s: np.ndarray
    channel_delta_mu_J_per_mol: np.ndarray
    channel_dissipation_rate_pJ_per_s: np.ndarray
    junction_availability: np.ndarray
    junction_delta_voltage_V: np.ndarray
    junction_gate_inf: np.ndarray
    junction_gate_rate_per_s: np.ndarray
    junction_open_fraction: np.ndarray
    junction_effective_permeability_m_per_s: np.ndarray
    junction_flux_fmol_per_s: np.ndarray
    junction_delta_mu_J_per_mol: np.ndarray
    junction_current_A: np.ndarray
    junction_dissipation_rate_pJ_per_s: np.ndarray


def observe_history(times, history, layout, requested, spec):
    return observe_composed_history(
        times,
        history,
        LAYOUT_TYPE(*(np.asarray(v) for v in layout)),
        requested,
        spec,
        rhs=rhs,
        readouts=readouts,
        check_values=check_values,
        check_interpolants=check_interpolants,
    )


def observe_composed_history(
    times,
    history,
    layout,
    requested,
    spec,
    *,
    rhs,
    readouts,
    check_values,
    check_interpolants,
    junction_readouts=junction_readouts,
    state_type=STATE_TYPE,
    balances=balances,
    observation_type=Observations,
    extra_observations=None,
):
    """Interval-local controls and physical observations with explicit law callbacks."""
    requested = np.asarray(requested, dtype=np.float64)
    control = control_values(spec, times[:-1])
    f0, f1 = (
        rhs(state_type(*(v[part] for v in history)), control, layout, layout.active, xp=np)
        for part in (slice(None, -1), slice(1, None))
    )
    check_interpolants(times, history, f0, f1, layout)
    sampled = state_type(
        *(
            sample_hermite_history(times, v, requested, a, b)
            for v, a, b in zip(history, f0, f1, strict=True)
        )
    )
    check_values(sampled, spec)
    control = control_values(spec, requested)
    voltage, leak, cycles, mu, affinity = readouts(sampled, control.membrane, layout, xp=np)
    channel = channel_readouts(sampled, control.channel, layout, xp=np)
    edge = junction_readouts(sampled, control.junction, layout, xp=np)
    pump_flux = layout.stoichiometry * cycles[..., None, :]
    membrane_flux = leak + pump_flux + gated.channel_species(channel.flux_fmol_per_s, leak, layout)
    amount, outside = physical_amounts(sampled, layout)
    material, outside_balance, charge, energy, global_material, q = balances(sampled, layout)
    dissipation = ionic.dissipation_rate(leak, cycles, mu, affinity, xp=np) + gated.scatter(
        channel.dissipation_rate_pJ_per_s, cycles, (layout.channel_membranes,), xp=np
    )
    result = observation_type(
        requested,
        *(getattr(sampled, name) for name in STATE_TYPE._fields),
        amount,
        amount / layout.volume,
        outside,
        outside / layout.extracellular_volume,
        voltage,
        control.membrane[..., :-1, :],
        control.membrane[..., -1, :],
        leak,
        cycles,
        pump_flux,
        mu,
        affinity,
        CHARGE_PER_FMOL * np.sum(layout.valence * membrane_flux, axis=-2),
        -MOL_PER_FMOL * layout.pump_drive * cycles,
        -MOL_PER_FMOL * layout.pump_drive * sampled.pump_cycles,
        dissipation,
        gated.scatter(-membrane_flux, outside, (layout.outside_owners,), xp=np),
        material,
        outside_balance,
        charge,
        energy,
        global_material,
        q,
        control.channel,
        *channel,
        control.junction,
        *edge,
        *(extra_observations(sampled, control, layout) if extra_observations is not None else ()),
    )
    if not all(np.isfinite(v).all() for v in vars(result).values()):
        raise NumericalError("Nonfinite finite-compartment observation")
    return result


def summarize(history, diagnostics, spec):
    _, layout = initial_values(spec)
    return summarize_geometry(history, diagnostics, spec, layout, "finite_extracellular@1")


def summarize_geometry(history, diagnostics, spec, layout, model_id):
    m, x = spec.model, spec.execution
    return {
        "model": model_id,
        "species_ids": list(m.species_ids),
        "cell_ids": [c.id for c in m.cells],
        "extracellular_id": m.extracellular.id,
        "capacities": {
            k: getattr(x, k)
            for k in (
                "capacity",
                "membrane_capacity",
                "channel_capacity",
                "edge_capacity",
                "extracellular_capacity",
            )
        },
        "boundary": (
            "one finite shared extracellular inventory; zero potential is a gauge, not a bath clamp"
        ),
        "state_coordinates": (
            "inside and outside amount increments from immutable initial inventories"
        ),
        "energy_scope": (
            "both finite ideal chemical inventories and each capacitor once; "
            "pump work; no metabolism or gating energy"
        ),
        "external_support": ["temperature", "fixed volumes/geometries", "pump chemical drive"],
        "final_amounts_fmol": (layout.amount_reference + history.amount_increment[-1])[
            :, : len(m.cells)
        ].tolist(),
        "final_extracellular_amounts_fmol": (
            layout.extracellular_amount_reference + history.extracellular_amount_increment[-1]
        )[:, :1].tolist(),
        "final_voltage_V": cell_voltage(history.amount_increment[-1], layout, xp=np)[
            : len(m.cells)
        ].tolist(),
        **diagnostics,
    }
