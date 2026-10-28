"""Manufactured reversible electroneutral symport, without geometry or stepping.

Positive cycles move all declared species from outside to inside. Concentrations
are [..., species, compartment]; route parameters/controls are [..., route].
Temperature is [..., 1], common to every route within an independent world.
Unchecked kernels require validated topology and domain_valid at every stage.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R

LAW_ID = "electroneutral_symport_reversible_tanh@1"
KCC_LAW_ID = "kcc_reversible_tanh@1"
NKCC_LAW_ID = "nkcc_reversible_tanh@1"
TEMPERATURE_DOMAIN_K = (200.0, 400.0)


class Topology(NamedTuple):
    species_valence: object  # [species], nonzero integer charges.
    compartment_active: object  # [compartment], explicit boolean mask.
    inside: object  # [route], safe indices also for padding.
    outside: object
    stoichiometry: object  # [species, route], nonnegative inward coefficients.
    active: object  # [route], padding has zero stoichiometry.


class Parameters(NamedTuple):
    capacity_fmol_s: object  # Nonnegative, broadcastable to [..., route].
    temperature_K: object  # Scalar or [..., 1], never a varying route temperature.


class Rates(NamedTuple):
    cycle_fmol_s: object
    affinity_J_mol: object
    reaction_free_energy_J_mol: object
    transported_fmol_s: object  # [..., species, route], signed inward transfer.
    dissipated_power_pJ_s: object
    chemical_power_pJ_s: object
    direct_charge_C_s: object


class ExchangeRates(NamedTuple):
    amount_fmol_s: object  # [..., species, compartment].
    transported_fmol_s: object


class MaterialBalances(NamedTuple):
    amount_residual_fmol: object
    species_total_residual_fmol: object
    compartment_charge_residual_C: object


def _numeric(value):
    return value.dtype.kind in "fiu"


def named_stoichiometry(species_ids, species_valence, law_id):
    """Host-only named role binding; unused species retain zero coefficients."""
    ids, z = tuple(species_ids), np.asarray(species_valence)
    if (
        not ids
        or any(not isinstance(s, str) or not s for s in ids)
        or len(set(ids)) != len(ids)
        or z.shape != (len(ids),)
        or z.dtype.kind not in "iu"
    ):
        raise ValueError("Named cotransport requires unique species IDs and integer valences")
    if law_id == KCC_LAW_ID:
        roles = {"K": (1, 1), "Cl": (-1, 1)}
    elif law_id == NKCC_LAW_ID:
        roles = {"Na": (1, 1), "K": (1, 1), "Cl": (-1, 2)}
    else:
        raise ValueError("Unknown named cotransport law")
    nu = np.zeros(len(ids), dtype=np.int64)
    for name, (valence, coefficient) in roles.items():
        if name not in ids or z[ids.index(name)] != valence:
            raise ValueError("Missing cotransport role or incorrect actual species valence")
        nu[ids.index(name)] = coefficient
    return nu


def _topology_arrays(topology, *, xp):
    z, compartments, inside, outside, nu, active = (xp.asarray(v) for v in topology)
    if (
        z.ndim != 1
        or not z.size
        or z.dtype.kind not in "iu"
        or compartments.ndim != 1
        or not compartments.size
        or compartments.dtype.kind != "b"
        or inside.ndim != 1
        or inside.dtype.kind not in "iu"
        or outside.shape != inside.shape
        or outside.dtype.kind not in "iu"
        or active.shape != inside.shape
        or active.dtype.kind != "b"
        or nu.shape != (z.size, inside.size)
        or nu.dtype.kind not in "iu"
    ):
        raise ValueError("Cotransport requires explicit species, compartment and route axes")
    return Topology(z, compartments, inside, outside, nu, active)


def _topology_domain(topology, *, xp):
    t = _topology_arrays(topology, xp=xp)
    z, compartments, inside, outside, nu, active = t
    count = compartments.size
    owners_ok = (inside >= 0) & (inside < count) & (outside >= 0) & (outside < count)
    safe_in, safe_out = xp.clip(inside, 0, count - 1), xp.clip(outside, 0, count - 1)
    valid = xp.all((z != 0) & (z >= -8) & (z <= 8))
    valid &= xp.all((nu >= 0) & (nu <= 2)) & xp.all(owners_ok)
    valid &= xp.all(xp.where(active, compartments[safe_in] & compartments[safe_out], True))
    valid &= xp.all(xp.where(active, inside != outside, True))
    valid &= xp.all(xp.where(active, xp.sum(nu, axis=0) > 0, xp.all(nu == 0, axis=0)))
    valid &= xp.all(xp.sum(z[:, None] * nu, axis=0) == 0)
    return valid, t._replace(inside=safe_in, outside=safe_out)


def validate_topology(topology):
    """Host validation; empty routes and wholly inactive padding are supported."""
    valid, t = _topology_domain(topology, xp=np)
    if not valid:
        raise ValueError("Invalid cotransport ownership, electroneutral stoichiometry or padding")
    return Topology(
        t.species_valence.astype(np.int64),
        t.compartment_active,
        t.inside.astype(np.int64),
        t.outside.astype(np.int64),
        t.stoichiometry.astype(np.int64),
        t.active,
    )


def _parameter_arrays(parameters, *, xp):
    capacity, temperature = (xp.asarray(v) for v in parameters)
    if not all(_numeric(v) for v in (capacity, temperature)):
        raise ValueError("Cotransport parameters must be real numeric arrays without booleans")
    if not temperature.ndim:
        temperature = temperature.reshape((1,))
    if temperature.shape[-1] != 1:
        raise ValueError("Cotransport temperature requires a singleton final axis")
    return capacity, temperature


def validate_parameters(parameters, topology):
    t = validate_topology(topology)
    capacity, temperature = _parameter_arrays(parameters, xp=np)
    shape = np.broadcast_shapes((t.active.size,), capacity.shape, temperature.shape)
    if shape[-1] != t.active.size:
        raise ValueError("Cotransport parameter route axis mismatch")
    cap = np.broadcast_to(capacity, shape)
    if (
        not np.isfinite(capacity).all()
        or np.any(capacity < 0)
        or not np.isfinite(temperature).all()
        or np.any((temperature < 200) | (temperature > 400))
        or np.any(cap[..., ~t.active] != 0)
    ):
        raise ValueError("Invalid cotransport capacity, temperature or neutral route padding")
    # Preserve singleton temperature axis, including for an empty route axis.
    return Parameters(cap.astype(float), temperature.astype(float))


def _broadcast(concentration_mM, topology, parameters, availability, *, xp):
    c = xp.asarray(concentration_mM)
    if c.ndim < 2 or c.shape[-2:] != (
        topology.species_valence.size,
        topology.compartment_active.size,
    ):
        raise ValueError("Cotransport concentrations require [..., species, compartment]")
    capacity, temperature = _parameter_arrays(parameters, xp=xp)
    a = xp.asarray(availability)
    if not all(_numeric(v) for v in (c, a)):
        raise ValueError("Cotransport concentrations and controls require real numeric arrays")
    shape = xp.broadcast_shapes(
        c.shape[:-2] + (topology.active.size,), capacity.shape, temperature.shape, a.shape
    )
    if shape[-1] != topology.active.size:
        raise ValueError("Cotransport route axis mismatch")
    return (
        xp.broadcast_to(c, shape[:-1] + c.shape[-2:]),
        *(xp.broadcast_to(v, shape) for v in (capacity, temperature, a)),
    )


def rates(concentration_mM, topology, parameters, availability, *, xp=jnp):
    """Unchecked manufactured law, J=C*a*tanh(A/(2RT)); no active-state repair."""
    t = topology
    c, capacity, temperature, opening = _broadcast(
        concentration_mM, t, parameters, availability, xp=xp
    )
    c = xp.where(t.compartment_active, c, 1.0)
    log_ratio = xp.log(c[..., t.outside]) - xp.log(c[..., t.inside])
    reduced_affinity = xp.sum(t.stoichiometry * log_ratio, axis=-2)
    affinity = xp.where(t.active, R * temperature * reduced_affinity, 0.0)
    cycles = xp.where(t.active, capacity * opening * xp.tanh(0.5 * reduced_affinity), 0.0)
    transport = t.stoichiometry * cycles[..., None, :]
    heat = 1e-3 * cycles * affinity
    charge = CHARGE_PER_FMOL * xp.sum(t.species_valence[:, None] * t.stoichiometry, axis=0)
    return Rates(cycles, affinity, -affinity, transport, heat, -heat, charge * cycles)


def exchange_rates(signed_cycles, topology, *, xp=jnp):
    """Scatter each signed cycle once to each material owner; units follow input."""
    t, cycles = topology, xp.asarray(signed_cycles)
    if cycles.ndim < 1 or cycles.shape[-1] != t.active.size:
        raise ValueError("Cotransport cycles require an explicit final route axis")
    cycles = xp.where(t.active, cycles, 0.0)
    transported = t.stoichiometry * cycles[..., None, :]
    target = xp.zeros(
        cycles.shape[:-1] + (t.species_valence.size, t.compartment_active.size),
        dtype=transported.dtype,
    )
    inward = ordered_scatter(transported, target, (t.inside,), xp=xp)
    outward = ordered_scatter(transported, target, (t.outside,), xp=xp)
    return ExchangeRates(inward - outward, transported)


def domain_valid(concentration_mM, topology, parameters, availability, *, xp=jnp):
    """Global trial predicate, including blocked substrates and finite outputs.

    Neutral values below exist only while evaluating the predicate on a rejected
    trial. The physical rates kernel never replaces active concentrations.
    """
    try:
        valid, t = _topology_domain(topology, xp=xp)
        c, cap, temp, opening = _broadcast(concentration_mM, t, parameters, availability, xp=xp)
        raw_cap, raw_temp = _parameter_arrays(parameters, xp=xp)
        raw_opening = xp.asarray(availability)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    positive = xp.isfinite(c) & (c > 0)
    valid &= xp.all(xp.where(t.compartment_active, positive, c == 0))
    for value in (raw_cap, raw_temp, raw_opening):
        valid &= xp.all(xp.isfinite(value))
    valid &= xp.all(raw_cap >= 0) & xp.all((raw_temp >= 200) & (raw_temp <= 400))
    valid &= xp.all((raw_opening >= 0) & (raw_opening <= 1))
    valid &= xp.all(xp.where(t.active, True, (cap == 0) & (opening == 0)))
    safe_c = xp.where(t.compartment_active, xp.where(positive, c, 1.0), 0.0)
    safe_p = Parameters(
        xp.where(xp.isfinite(cap) & (cap >= 0), cap, 0.0),
        xp.where(xp.isfinite(raw_temp) & (raw_temp >= 200) & (raw_temp <= 400), raw_temp, 298.15),
    )
    values = rates(safe_c, t, safe_p, xp.where(xp.isfinite(opening), opening, 0.0), xp=xp)
    for value in (*values, *exchange_rates(values.cycle_fmol_s, t, xp=xp)):
        valid &= xp.all(xp.isfinite(value))
    return valid & xp.all(values.dissipated_power_pJ_s >= 0)


def exchange_domain_valid(signed_cycles, topology, *, xp=jnp):
    """Validate supplied signed rates or accumulated extents, including padding."""
    try:
        valid, t = _topology_domain(topology, xp=xp)
        cycles = xp.asarray(signed_cycles)
        if cycles.ndim < 1 or cycles.shape[-1] != t.active.size or not _numeric(cycles):
            return xp.asarray(False)
        valid &= xp.all(xp.isfinite(cycles)) & xp.all(xp.where(t.active, True, cycles == 0))
        for value in exchange_rates(cycles, t, xp=xp):
            valid &= xp.all(xp.isfinite(value))
        return valid
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)


def material_balances(initial, current, signed_cycle_integrals, topology, *, xp=jnp):
    """Reconstruct finite amount changes from retained signed cycle integrals."""
    before, after = xp.asarray(initial), xp.asarray(current)
    expected_shape = (topology.species_valence.size, topology.compartment_active.size)
    if any(v.ndim < 2 or v.shape[-2:] != expected_shape for v in (before, after)):
        raise ValueError("Cotransport amounts require [..., species, compartment]")
    delta = after - before
    exchange = exchange_rates(signed_cycle_integrals, topology, xp=xp).amount_fmol_s
    return MaterialBalances(
        delta - exchange,
        xp.sum(delta, axis=-1),
        CHARGE_PER_FMOL * xp.sum(topology.species_valence[:, None] * delta, axis=-2),
    )
