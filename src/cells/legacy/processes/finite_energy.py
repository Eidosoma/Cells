"""Finite transformed ATP/ADP/Pi pools and an explicitly driven synthesis port.

Amounts use [..., species, owner], with species ATP, ADP, Pi; volume is pL.
Pure laws do not advance state. Composing models own amounts, route-cycle and
work/heat integrals, and must reject invalid trials rather than clip substrates.
Buffered pH/Mg and solvent activity are declared; these are not ionic charges.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import R

LAW_ID = "finite_atp_adp_pi_transformed@1"
REGENERATION_LAW_ID = "driven_atp_regeneration_tanh@1"
SPECIES = ("ATP", "ADP", "Pi")
HYDROLYSIS_STOICHIOMETRY = (-1, 1, 1)
STANDARD_STATE_mM = pump.STANDARD_STATE_mM
TEMPERATURE_DOMAIN_K = pump.TEMPERATURE_DOMAIN_K
MAX_ABS_AFFINITY_OVER_RT = pump.MAX_ABS_AFFINITY_OVER_RT


class Parameters(NamedTuple):
    temperature_K: object  # Broadcastable to [..., owner].
    delta_g0_J_mol: object
    active: object  # Explicit one-dimensional owner mask.


class Routes(NamedTuple):
    owner: object  # Safe one-dimensional integer indices, also for inactive slots.
    active: object


class RegenerationParameters(NamedTuple):
    capacity_fmol_s: object  # Nonnegative; broadcastable to [..., route].
    supplied_energy_J_mol: object  # Nonnegative forward supply; reverse exports work.


class Thermodynamics(NamedTuple):
    concentration_mM: object
    chemical_potential_J_mol: object
    hydrolysis_free_energy_J_mol: object
    free_energy_pJ: object
    osmolyte_amount_fmol: object
    volume_derivative_pJ_per_pL: object


class Invariants(NamedTuple):
    adenylate_fmol: object
    phosphorus_fmol: object


class ExchangeRates(NamedTuple):
    amount_fmol_s: object
    pump_hydrolysis_fmol_s: object  # Signed owner totals, from existing pump cycles once.
    regeneration_synthesis_fmol_s: object  # Signed owner totals.
    gross_hydrolysis_fmol_s: object
    gross_synthesis_fmol_s: object


class MaterialBalances(NamedTuple):
    amount_residual_fmol: object
    adenylate_residual_fmol: object
    phosphorus_residual_fmol: object


class RegenerationRates(NamedTuple):
    synthesis_fmol_s: object
    reaction_free_energy_J_mol: object
    supplied_power_pJ_s: object
    dissipated_power_pJ_s: object
    pool_chemical_power_pJ_s: object


def _numeric(value):
    return hasattr(value, "dtype") and value.dtype.kind in "fiu"


def _broadcast(amount, volume, p, *, xp):
    a, v, t, d = (
        xp.asarray(value)
        for value in (
            amount,
            volume,
            p.temperature_K,
            p.delta_g0_J_mol,
        )
    )
    if a.ndim < 2 or a.shape[-2:] != (3, p.active.size):
        raise ValueError("Energy amounts require [..., 3, owner] axes")
    shape = xp.broadcast_shapes(a.shape[:-2] + (p.active.size,), v.shape, t.shape, d.shape)
    if shape[-1] != p.active.size:
        raise ValueError("Energy volume/parameters require the declared owner axis")
    return (
        xp.broadcast_to(a, shape[:-1] + (3, p.active.size)),
        *(xp.broadcast_to(value, shape) for value in (v, t, d)),
    )


def validate_parameters(parameters):
    """Host validation; inactive owners use T=298.15 K and deltaG0=0."""
    active = np.asarray(parameters.active)
    if active.ndim != 1 or not active.size or active.dtype != np.bool_:
        raise ValueError("Energy owners require a nonempty one-dimensional boolean mask")
    fields = [np.asarray(v) for v in parameters[:2]]
    if not all(_numeric(v) for v in fields):
        raise ValueError("Energy parameters require numeric arrays, without booleans")
    shape = np.broadcast_shapes((active.size,), *(v.shape for v in fields))
    if shape[-1] != active.size:
        raise ValueError("Energy parameter owner axis mismatch")
    t, d = (np.broadcast_to(v, shape).astype(float) for v in fields)
    if (
        not np.isfinite(t).all()
        or not np.isfinite(d).all()
        or np.any((t < TEMPERATURE_DOMAIN_K[0]) | (t > TEMPERATURE_DOMAIN_K[1]))
        or np.any(t[..., ~active] != 298.15)
        or np.any(d[..., ~active] != 0)
    ):
        raise ValueError("Invalid energy temperature, standard potential or neutral padding")
    return Parameters(t, d, active)


def validate_routes(routes, parameters):
    """Host ownership validation; an empty explicit route axis is supported."""
    owner, active = np.asarray(routes.owner), np.asarray(routes.active)
    if (
        owner.ndim != 1
        or owner.dtype.kind not in "iu"
        or active.shape != owner.shape
        or active.dtype != np.bool_
        or np.any((owner < 0) | (owner >= len(parameters.active)))
    ):
        raise ValueError("Energy routes require safe integer owners and boolean masks")
    if np.any(active & ~np.asarray(parameters.active)[owner]):
        raise ValueError("An active energy route requires an active pool owner")
    return Routes(owner.astype(np.int64), active)


def thermodynamics(amount_fmol, volume_pL, parameters, *, xp=jnp):
    """Finite free energy in the gauge mu0_ATP=-deltaG0, mu0_ADP=mu0_Pi=0.

    This unchecked kernel requires domain_valid. Only inactive slots receive
    neutral logarithm arguments; active concentrations are never floored.
    Volume derivatives and osmolyte counts are readouts, not implicit coupling.
    """
    p = parameters
    amount, volume, temperature, delta = _broadcast(amount_fmol, volume_pL, p, xp=xp)
    active = xp.asarray(p.active)
    n = xp.where(active, amount, 1.0)
    v = xp.where(active, volume, 1.0)
    log_c = xp.log(n) - xp.log(v)[..., None, :]
    log_activity = log_c - xp.log(STANDARD_STATE_mM)
    rt = R * temperature
    standard = xp.stack((-delta, xp.zeros_like(delta), xp.zeros_like(delta)), axis=-2)
    mu = standard + rt[..., None, :] * log_activity
    g = delta + rt * (
        log_c[..., 1, :] + log_c[..., 2, :] - log_c[..., 0, :] - xp.log(STANDARD_STATE_mM)
    )
    free = 1e-3 * xp.sum(n * (standard + rt[..., None, :] * (log_activity - 1)), axis=-2)
    particles = xp.sum(amount, axis=-2)
    return Thermodynamics(
        xp.where(active, amount / v[..., None, :], 0.0),
        xp.where(active, mu, 0.0),
        xp.where(active, g, 0.0),
        xp.where(active, free, 0.0),
        xp.where(active, particles, 0.0),
        xp.where(active, -1e-3 * rt * particles / v, 0.0),
    )


def _domain_valid(amount_fmol, volume_pL, p, *, xp):
    active = xp.asarray(p.active)
    if active.ndim != 1 or not active.size or active.dtype.kind != "b":
        return xp.asarray(False)
    try:
        amount, volume, temperature, delta = _broadcast(amount_fmol, volume_pL, p, xp=xp)
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)
    if not all(_numeric(v) for v in (amount, volume, temperature, delta)):
        return xp.asarray(False)
    positive = xp.isfinite(amount) & (amount > 0)
    volume_ok = xp.isfinite(volume) & (volume > 0)
    temperature_ok = (
        xp.isfinite(temperature)
        & (temperature >= TEMPERATURE_DOMAIN_K[0])
        & (temperature <= TEMPERATURE_DOMAIN_K[1])
    )
    valid = xp.all(xp.where(active, positive, amount == 0))
    valid &= xp.all(xp.where(active, volume_ok, volume == 1.0))
    valid &= xp.all(temperature_ok) & xp.all(xp.isfinite(delta))
    valid &= xp.all(xp.where(active, True, (temperature == 298.15) & (delta == 0)))
    # Predicate-only neutral arguments do not repair or replace a physical trial.
    safe = Parameters(
        xp.where(temperature_ok, temperature, 298.15),
        xp.where(xp.isfinite(delta), delta, 0.0),
        active,
    )
    values = thermodynamics(
        xp.where(active, xp.where(positive, amount, 1.0), 0.0),
        xp.where(active, xp.where(volume_ok, volume, 1.0), 1.0),
        safe,
        xp=xp,
    )
    for value in values:
        valid &= xp.all(xp.isfinite(value))
    valid &= xp.all(xp.where(active, values.concentration_mM > 0, True))
    return valid


def domain_valid(amount_fmol, volume_pL, parameters, *, xp=jnp):
    """Strict positive interior; exhaustion rejects even when every route is off."""
    if xp is np:
        with np.errstate(all="ignore"):
            return _domain_valid(amount_fmol, volume_pL, parameters, xp=np)
    return _domain_valid(amount_fmol, volume_pL, parameters, xp=xp)


def invariants(amount_fmol, *, xp=jnp):
    amount = xp.asarray(amount_fmol)
    return Invariants(
        amount[..., 0, :] + amount[..., 1, :],
        3 * amount[..., 0, :] + 2 * amount[..., 1, :] + amount[..., 2, :],
    )


def chemical_power_pJ_s(amount_rate_fmol_s, values, *, xp=jnp):
    """Fixed-volume pool power; add the explicit volume derivative separately."""
    return 1e-3 * xp.sum(values.chemical_potential_J_mol * amount_rate_fmol_s, axis=-2)


def _route_domain(values, routes, parameters, *, xp):
    owner, active, values = (xp.asarray(v) for v in (routes.owner, routes.active, values))
    if (
        owner.ndim != 1
        or owner.dtype.kind not in "iu"
        or active.shape != owner.shape
        or active.dtype.kind != "b"
        or not values.ndim
        or values.shape[-1] != owner.size
        or not _numeric(values)
    ):
        return xp.asarray(False)
    ok = (owner >= 0) & (owner < parameters.active.size)
    safe_owner = xp.where(ok, owner, 0)
    return (
        xp.all(ok)
        & xp.all(~active | xp.asarray(parameters.active)[safe_owner])
        & xp.all(xp.isfinite(values))
        & xp.all(xp.where(active, True, values == 0))
    )


def exchange_domain_valid(
    pump_cycles, pump_routes, synthesis_cycles, synthesis_routes, p, *, xp=jnp
):
    return _route_domain(pump_cycles, pump_routes, p, xp=xp) & _route_domain(
        synthesis_cycles, synthesis_routes, p, xp=xp
    )


def _sum_routes(values, routes, parameters, *, xp):
    values = xp.where(xp.asarray(routes.active), xp.asarray(values), 0.0)
    target = xp.zeros(values.shape[:-1] + (parameters.active.size,), dtype=values.dtype)
    return ordered_scatter(values, target, (xp.asarray(routes.owner),), xp=xp)


def exchange_rates(pump_cycles, pump_routes, synthesis_cycles, synthesis_routes, p, *, xp=jnp):
    """Accumulate each supplied signed route cycle once, in declared route order.

    Retain the existing pump's signed cycle integrals and the synthesis port's
    signed integrals. Gross directional rates are additional readouts/ledgers,
    not extra physical reactions. Pump kinetics is never evaluated here.
    """
    demand = _sum_routes(pump_cycles, pump_routes, p, xp=xp)
    supply = _sum_routes(synthesis_cycles, synthesis_routes, p, xp=xp)
    demand, supply = xp.broadcast_arrays(demand, supply)
    net = demand - supply
    hydrolysis = _sum_routes(xp.maximum(pump_cycles, 0), pump_routes, p, xp=xp) + _sum_routes(
        xp.maximum(-xp.asarray(synthesis_cycles), 0), synthesis_routes, p, xp=xp
    )
    synthesis = _sum_routes(
        xp.maximum(-xp.asarray(pump_cycles), 0), pump_routes, p, xp=xp
    ) + _sum_routes(xp.maximum(synthesis_cycles, 0), synthesis_routes, p, xp=xp)
    return ExchangeRates(xp.stack((-net, net, net), axis=-2), demand, supply, hydrolysis, synthesis)


def material_balances(
    initial,
    current,
    pump_integrals,
    pump_routes,
    synthesis_integrals,
    synthesis_routes,
    p,
    *,
    xp=jnp,
):
    """Residuals from retained route extents in fmol; no conservation repair."""
    net = _sum_routes(pump_integrals, pump_routes, p, xp=xp) - _sum_routes(
        synthesis_integrals, synthesis_routes, p, xp=xp
    )
    delta = xp.asarray(current) - xp.asarray(initial)
    before, after = invariants(initial, xp=xp), invariants(current, xp=xp)
    return MaterialBalances(
        delta - xp.stack((-net, net, net), axis=-2),
        after.adenylate_fmol - before.adenylate_fmol,
        after.phosphorus_fmol - before.phosphorus_fmol,
    )


def pump_parameters(amount_fmol, volume_pL, p, routes, template, *, xp=jnp):
    """Stage-local bridge; existing immutable maintained-pool inputs stay intact.

    Gather one current owner for each present pump. Inactive routes receive the
    existing pump's neutral positive arguments and zero capacity. A blocked but
    present route retains its real finite pools and domain requirements.
    """
    concentrations = thermodynamics(amount_fmol, volume_pL, p, xp=xp).concentration_mM
    active, owner = xp.asarray(routes.active), xp.asarray(routes.owner)
    delta = _broadcast(amount_fmol, volume_pL, p, xp=xp)[3]
    return template._replace(
        capacity_fmol_s=xp.where(active, template.capacity_fmol_s, 0.0),
        atp_mM=xp.where(active, concentrations[..., 0, owner], 1.0),
        adp_mM=xp.where(active, concentrations[..., 1, owner], 1.0),
        pi_mM=xp.where(active, concentrations[..., 2, owner], 1000.0),
        km_na_mM=xp.where(active, template.km_na_mM, 1.0),
        km_k_mM=xp.where(active, template.km_k_mM, 1.0),
        km_atp_mM=xp.where(active, template.km_atp_mM, 1.0),
        delta_g0_J_mol=xp.where(active, delta[..., owner], 0.0),
    )


def regeneration_rates(amount_fmol, volume_pL, p, routes, supply, availability, *, xp=jnp):
    """Synthetic reversible supply port, J=C*a*tanh((g+w)/(2RT)).

    Positive J synthesizes ATP; negative J hydrolyses it and exports signed work.
    The declared transformed reaction energy is -g-w. This is not respiration.
    """
    g = thermodynamics(amount_fmol, volume_pL, p, xp=xp).hydrolysis_free_energy_J_mol[
        ..., routes.owner
    ]
    temperature = _broadcast(amount_fmol, volume_pL, p, xp=xp)[2][..., routes.owner]
    drive = g + supply.supplied_energy_J_mol
    enabled = xp.asarray(routes.active)
    cycles = xp.where(
        enabled,
        supply.capacity_fmol_s * availability * xp.tanh(drive / (2 * R * temperature)),
        0.0,
    )
    return RegenerationRates(
        cycles,
        xp.where(enabled, -drive, 0.0),
        1e-3 * cycles * supply.supplied_energy_J_mol,
        1e-3 * cycles * drive,
        -1e-3 * cycles * g,
    )


def _regeneration_domain_valid(amount, volume, p, routes, supply, availability, *, xp):
    if not domain_valid(amount, volume, p, xp=xp):
        # This host short circuit is replaced by predicate arithmetic below for JAX.
        return xp.asarray(False)
    return _regeneration_domain_arrays(amount, volume, p, routes, supply, availability, xp=xp)


def _regeneration_domain_arrays(amount, volume, p, routes, supply, availability, *, xp):
    capacity, work, opening = (xp.asarray(v) for v in (*supply, availability))
    if not all(_numeric(v) for v in (capacity, work, opening)):
        return xp.asarray(False)
    try:
        g = thermodynamics(amount, volume, p, xp=xp).hydrolysis_free_energy_J_mol
        temperature = _broadcast(amount, volume, p, xp=xp)[2]
        owner = xp.asarray(routes.owner)
        if owner.ndim != 1 or owner.dtype.kind not in "iu":
            return xp.asarray(False)
        ok = (owner >= 0) & (owner < p.active.size)
        safe_owner = xp.where(ok, owner, 0)
        shape = xp.broadcast_shapes(
            g[..., safe_owner].shape, capacity.shape, work.shape, opening.shape
        )
        if shape[-1] != owner.size:
            return xp.asarray(False)
        zero = xp.zeros(shape)
        valid = _route_domain(zero, routes, p, xp=xp)
        valid &= xp.all(xp.isfinite(capacity) & (capacity >= 0))
        valid &= xp.all(xp.isfinite(work) & (work >= 0))
        valid &= xp.all(xp.isfinite(opening) & (opening >= 0) & (opening <= 1))
        inactive = ~xp.asarray(routes.active)
        valid &= xp.all(xp.where(inactive, (capacity == 0) & (work == 0) & (opening == 0), True))
        affinity = (-g[..., safe_owner] - work) / (R * temperature[..., safe_owner])
        valid &= xp.all(xp.isfinite(affinity) & (xp.abs(affinity) <= MAX_ABS_AFFINITY_OVER_RT))
        safe_routes = Routes(safe_owner, routes.active)
        rates = regeneration_rates(amount, volume, p, safe_routes, supply, opening, xp=xp)
        for value in rates:
            valid &= xp.all(xp.isfinite(value))
        return valid
    except (ValueError, TypeError, AttributeError):
        return xp.asarray(False)


def regeneration_domain_valid(amount, volume, p, routes, supply, availability, *, xp=jnp):
    if xp is np:
        with np.errstate(all="ignore"):
            return _regeneration_domain_valid(
                amount, volume, p, routes, supply, availability, xp=np
            )
    return domain_valid(amount, volume, p, xp=xp) & _regeneration_domain_arrays(
        amount, volume, p, routes, supply, availability, xp=xp
    )
