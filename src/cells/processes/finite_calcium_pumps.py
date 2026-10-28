"""Live finite-energy adapters for the unchanged positive-domain calcium laws.

One signed formal cycle transfers one Ca and hydrolyses one ATP. Negative
cycles synthesize ATP. ER here is the source's formal one-Ca law, without a
physiological two-Ca SERCA or proton claim. Pure kernels require domain_valid.
"""

from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.processes import er_calcium, finite_energy, plasma_calcium
from cells.processes.electrochemistry import F, R

PMCA_LAW = "finite_atp_pmca_betse_positive@1"
ER_LAW = "finite_atp_er_1ca_betse_positive@1"
POOL_LAW = finite_energy.LAW_ID
Routes = finite_energy.Routes
MAX_AFFINITY_RT = er_calcium.MAX_AFFINITY_RT
MAX_ABS_VOLTAGE_V = plasma_calcium.MAX_VOLTAGE
CALCIUM_PER_CYCLE = ATP_PER_CYCLE = 1


class PumpParameters(NamedTuple):
    capacity_fmol_per_s: object
    km_ca_mM: object
    km_atp_mM: object


class Rates(NamedTuple):
    cycles_fmol_s: object
    reaction_free_energy_J_mol: object
    hydrolysis_free_energy_J_mol: object
    transport_free_energy_J_mol: object
    dissipated_power_pJ_s: object
    pool_chemical_power_pJ_s: object
    transport_power_pJ_s: object


def _numeric(value):
    return hasattr(value, "dtype") and value.dtype.kind in "fiu"


def legacy_standard_energy(delta_g0_1M_J_mol, temperature_K, *, xp=jnp):
    """Convert standard energy only; finite pools retain their 1-M convention."""
    return xp.asarray(delta_g0_1M_J_mol) - R * xp.asarray(temperature_K) * xp.log(1000.0)


def _pool_inputs(amount, volume, p, routes, *, xp):
    values = finite_energy.thermodynamics(amount, volume, p, xp=xp)
    shape = values.concentration_mM.shape[:-2] + (p.active.size,)
    temperature = xp.broadcast_to(xp.asarray(p.temperature_K), shape)[..., routes.owner]
    delta = xp.broadcast_to(xp.asarray(p.delta_g0_J_mol), shape)[..., routes.owner]
    return values.concentration_mM[..., :, routes.owner], temperature, delta


def pump_parameters(amount, volume, p, routes, pump, *, xp=jnp):
    """Gather current owner substrates and convert the standard energy explicitly.

    Returns the existing er_calcium.PumpParameters (also used by PMCA). Absent
    routes get neutral source-law inputs; blocked present routes keep real pools.
    Temperature belongs to the referenced finite owner, not to this adapter.
    """
    c, temperature, delta = _pool_inputs(amount, volume, p, routes, xp=xp)
    active = xp.asarray(routes.active)
    return er_calcium.PumpParameters(
        xp.where(active, pump.capacity_fmol_per_s, 0.0),
        xp.where(active, pump.km_ca_mM, 1.0),
        xp.where(active, pump.km_atp_mM, 1.0),
        xp.where(active, c[..., 0, :], 1.0),
        xp.where(active, c[..., 1, :], 1.0),
        xp.where(active, c[..., 2, :], 1.0),
        xp.where(active, legacy_standard_energy(delta, temperature, xp=xp), 0.0),
    )


def _rates(source, destination, voltage, amount, volume, p, routes, pump, availability, law, *, xp):
    native = pump_parameters(amount, volume, p, routes, pump, xp=xp)
    _, temperature, _ = _pool_inputs(amount, volume, p, routes, xp=xp)
    active = xp.asarray(routes.active)
    source, destination = (xp.where(active, value, 1.0) for value in (source, destination))
    voltage = xp.where(active, voltage, 0.0)
    temperature = xp.where(active, temperature, 298.15)
    opening = xp.where(active, availability, 0.0)
    # The accepted NumPy source law uses an in-place saturation subtraction.
    # Expand all independent world axes before entering that unchanged kernel.
    source, destination, voltage, temperature, opening, *fields = xp.broadcast_arrays(
        source, destination, voltage, temperature, opening, *native
    )
    native = er_calcium.PumpParameters(*fields)
    cycles, reaction, hydrolysis = law(
        source, destination, voltage, temperature, native, opening, xp=xp
    )
    sign = -1 if law is plasma_calcium.pump_rates else 1
    transport = R * temperature * (xp.log(destination) - xp.log(source)) + 2 * F * sign * voltage
    return Rates(
        xp.where(active, cycles, 0.0),
        xp.where(active, reaction, 0.0),
        xp.where(active, hydrolysis, 0.0),
        xp.where(active, transport, 0.0),
        xp.where(active, -1e-3 * cycles * reaction, 0.0),
        xp.where(active, 1e-3 * cycles * hydrolysis, 0.0),
        xp.where(active, 1e-3 * cycles * transport, 0.0),
    )


def pmca_rates(
    source, destination, voltage, amount, volume, p, routes, pump, availability, *, xp=jnp
):
    """Positive cycles extrude one Ca; voltage is source minus destination (Vm)."""
    return _rates(
        source,
        destination,
        voltage,
        amount,
        volume,
        p,
        routes,
        pump,
        availability,
        plasma_calcium.pump_rates,
        xp=xp,
    )


def er_rates(
    source, destination, voltage, amount, volume, p, routes, pump, availability, *, xp=jnp
):
    """Positive cycles move one Ca into ER; voltage is destination minus source."""
    return _rates(
        source,
        destination,
        voltage,
        amount,
        volume,
        p,
        routes,
        pump,
        availability,
        er_calcium.pump_rates,
        xp=xp,
    )


def pool_exchange(cycles, routes, p, *, xp=jnp):
    """Scatter each supplied signed calcium cycle once, without recomputing it.

    Combine PMCA/ER (and other ATP-consuming) route arrays before one existing
    finite_energy.exchange_rates call when composing a shared complete model.
    This convenience supplies an explicitly empty regeneration axis. Its output
    must not be counted again in a second pool exchange. NCX is not an ATP route.
    """
    cycles = xp.asarray(cycles)
    empty = Routes(xp.zeros((0,), dtype=xp.int64), xp.zeros((0,), dtype=bool))
    supply = xp.zeros(cycles.shape[:-1] + (0,), dtype=cycles.dtype)
    return finite_energy.exchange_rates(cycles, routes, supply, empty, p, xp=xp)


def _domain_valid(
    source, destination, voltage, amount, volume, p, routes, pump, availability, law, *, xp
):
    owner, active = xp.asarray(routes.owner), xp.asarray(routes.active)
    pool_active = xp.asarray(p.active)
    if (
        pool_active.ndim != 1
        or not pool_active.size
        or pool_active.dtype.kind != "b"
        or owner.ndim != 1
        or owner.dtype.kind not in "iu"
        or active.shape != owner.shape
        or active.dtype.kind != "b"
    ):
        return xp.asarray(False)
    fields = [xp.asarray(v) for v in (source, destination, voltage, *pump, availability)]
    if not all(_numeric(v) for v in fields):
        return xp.asarray(False)
    try:
        # Preserve each declared owner and route axis even with leading worlds.
        pool_shape = xp.broadcast_shapes(
            xp.shape(amount)[:-2] + (pool_active.size,),
            xp.shape(volume),
            xp.shape(p.temperature_K),
            xp.shape(p.delta_g0_J_mol),
        )
        shape = xp.broadcast_shapes(pool_shape[:-1] + (owner.size,), *(v.shape for v in fields))
        if shape[-1] != owner.size:
            return xp.asarray(False)
        source, destination, voltage, capacity, km_ca, km_atp, opening = (
            xp.broadcast_to(v, shape) for v in fields
        )
    except (ValueError, TypeError, IndexError):
        return xp.asarray(False)
    safe_index = (owner >= 0) & (owner < pool_active.size)
    safe_owner = xp.where(safe_index, owner, 0)
    valid = finite_energy.domain_valid(amount, volume, p, xp=xp)
    valid &= xp.all(safe_index) & xp.all(~active | pool_active[safe_owner])
    # Raw checks retain scalar-control rejection even for an empty route axis.
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in fields]))
    for v in (fields[0], fields[1], fields[4], fields[5]):
        valid &= xp.all(v > 0)
    valid &= xp.all(fields[3] >= 0)
    valid &= xp.all((fields[6] >= 0) & (fields[6] <= 1))
    valid &= xp.all(xp.abs(fields[2]) <= MAX_ABS_VOLTAGE_V)
    valid &= xp.all(xp.where(active, True, (source == 1) & (destination == 1) & (voltage == 0)))
    valid &= xp.all(
        xp.where(active, True, (capacity == 0) & (km_ca == 1) & (km_atp == 1) & (opening == 0))
    )
    if xp.shape(amount)[-2:] != (3, pool_active.size) or pool_shape[-1] != pool_active.size:
        return xp.asarray(False)
    # Predicate-only safe ownership prevents indexing an invalid declaration.
    # Other invalid physical fields are not repaired; finite/affinity checks reject.
    safe_routes = Routes(safe_owner, active)
    try:
        result = law(
            source,
            destination,
            voltage,
            amount,
            volume,
            p,
            safe_routes,
            PumpParameters(capacity, km_ca, km_atp),
            opening,
            xp=xp,
        )
        _, temperature, _ = _pool_inputs(amount, volume, p, safe_routes, xp=xp)
    except (ValueError, TypeError, IndexError, AttributeError):
        return xp.asarray(False)
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in result]))
    valid &= xp.all(
        xp.where(
            active,
            xp.abs(result.reaction_free_energy_J_mol / (R * temperature)) <= MAX_AFFINITY_RT,
            True,
        )
    )
    valid &= xp.all(result.dissipated_power_pJ_s >= 0)
    valid &= finite_energy.exchange_domain_valid(
        result.cycles_fmol_s,
        safe_routes,
        xp.zeros((0,)),
        Routes(xp.zeros((0,), dtype=xp.int64), xp.zeros((0,), dtype=bool)),
        p,
        xp=xp,
    )
    return valid


def domain_valid(
    source, destination, voltage, amount, volume, p, routes, pump, availability, *, kind, xp=jnp
):
    """Strict complete pool/route trial predicate; present blocked routes stay strict.

    ``kind`` is the static string 'pmca' or 'er', and selects the native voltage
    convention. Inactive routes require Ca=Km=1, V=C=availability=0 and safe
    owner indices. Owners obey the unchanged finite_energy positive interior.
    """
    if kind not in ("pmca", "er"):
        return xp.asarray(False)
    law = pmca_rates if kind == "pmca" else er_rates
    if xp is np:
        with np.errstate(all="ignore"):
            return _domain_valid(
                source,
                destination,
                voltage,
                amount,
                volume,
                p,
                routes,
                pump,
                availability,
                law,
                xp=np,
            )
    return _domain_valid(
        source, destination, voltage, amount, volume, p, routes, pump, availability, law, xp=xp
    )
