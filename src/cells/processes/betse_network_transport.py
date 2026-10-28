"""Literal BETSE 1.5.0 configurable cell-zone transporter law, versioned @1.

Concentrations use [..., species, compartment]; V/controls use [..., route].
Term axes are [term, route]. Positive extent follows configured reactants to
products. Current is outward; Vm is inside minus outside. This component owns
no stepping, physical heat, ATP demand, water or implicit reservoir behavior.

The generated source omits product saturation and applies 1e-3 outside each
concentration power in Q. Transporter regulator zones and '*' voltage requests
are not forwarded by the native generator. These semantics are intentional.
"""

from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter
from cells.processes.electrochemistry import CHARGE_PER_FMOL, MOL_PER_FMOL, F, R

LAW_ID = "betse_network_transporter_source_v1_5_0@1"
ACTIVATE, INDEPENDENT_ACTIVATE, DIRECT_ACTIVATE, INHIBIT, DIRECT_INHIBIT = range(1, 6)


class Terms(NamedTuple):
    species: object
    outside: object
    coefficient: object  # Zero is padding, positive real is an active term.
    km_mM: object  # Product Km is retained/validated but absent from the rate.


class Influencers(NamedTuple):
    species: object
    mode: object  # Zero is padding; all native transporter influencers are inside.
    km_mM: object
    exponent: object


class Topology(NamedTuple):
    species_valence: object
    compartment_active: object
    inside: object
    outside: object
    active: object
    reactants: Terms
    products: Terms
    influencers: Influencers


class Parameters(NamedTuple):
    max_flux_mol_m2_s: object
    area_m2: object
    standard_free_energy_J_mol: object  # Neutral zero when irreversible.
    reversible: object
    temperature_K: object  # Scalar or [..., 1], one temperature per world.


class Rates(NamedTuple):
    flux_density_mol_m2_s: object
    extent_fmol_s: object
    native_net_z: object
    outward_current_density_A_m2: object
    outward_current_C_s: object
    forward_saturation: object
    regulation: object
    log_source_quotient: object
    source_electrical_energy_J_mol: object
    source_reaction_energy_J_mol: object  # Diagnostic; zero for irreversible.


class MaterialBalances(NamedTuple):
    amount_residual_fmol: object
    species_total_residual_fmol: object
    compartment_charge_residual_C: object


def _numeric(value):
    return value.dtype.kind in "fiu"


def _number(value, *, positive=False, nonnegative=False):
    return (
        not isinstance(value, (bool, np.bool_))
        and isinstance(value, Real)
        and np.isfinite(value)
        and (not positive or value > 0)
        and (not nonnegative or value >= 0)
    )


def _topology_arrays(topology, *, xp):
    z, compartments, inside, outside, active = (xp.asarray(v) for v in topology[:5])
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
    ):
        raise ValueError("Require explicit species, compartment and route axes")
    groups = []
    for terms in (topology.reactants, topology.products):
        species, external, coefficient, km = (xp.asarray(v) for v in terms)
        if (
            species.ndim != 2
            or species.shape[-1] != inside.size
            or species.dtype.kind not in "iu"
            or external.shape != species.shape
            or external.dtype.kind != "b"
            or coefficient.shape != species.shape
            or km.shape != species.shape
            or not _numeric(coefficient)
            or not _numeric(km)
        ):
            raise ValueError("Substrates require matching [term, route] arrays")
        groups.append(Terms(species, external, coefficient, km))
    species, mode, km, exponent = (xp.asarray(v) for v in topology.influencers)
    if (
        species.ndim != 2
        or species.shape[-1] != inside.size
        or species.dtype.kind not in "iu"
        or mode.shape != species.shape
        or mode.dtype.kind not in "iu"
        or km.shape != species.shape
        or exponent.shape != species.shape
        or not _numeric(km)
        or not _numeric(exponent)
    ):
        raise ValueError("Influencers require matching [term, route] arrays")
    return Topology(
        z, compartments, inside, outside, active, *groups, Influencers(species, mode, km, exponent)
    )


def _topology_domain(topology, *, xp):
    t = _topology_arrays(topology, xp=xp)
    count, species_count = t.compartment_active.size, t.species_valence.size
    valid = xp.all((t.species_valence >= -8) & (t.species_valence <= 8))
    valid &= xp.all((t.inside >= 0) & (t.inside < count))
    valid &= xp.all((t.outside >= 0) & (t.outside < count))
    inside, outside = xp.clip(t.inside, 0, count - 1), xp.clip(t.outside, 0, count - 1)
    valid &= xp.all(
        xp.where(
            t.active,
            t.compartment_active[inside] & t.compartment_active[outside] & (inside != outside),
            True,
        )
    )
    groups, charge, scale = (
        [],
        xp.zeros_like(t.inside, dtype=float),
        xp.zeros_like(t.inside, dtype=float),
    )
    for sign, terms in ((-1, t.reactants), (1, t.products)):
        s, external, nu, km = terms
        valid &= xp.all((s >= 0) & (s < species_count))
        safe_s = xp.clip(s, 0, species_count - 1)
        valid &= xp.all(xp.isfinite(nu) & (nu >= 0) & xp.isfinite(km) & (km > 0))
        enabled = nu > 0
        valid &= xp.all(xp.where(t.active, xp.any(enabled, axis=0), ~xp.any(enabled, axis=0)))
        valid &= xp.all(xp.where(enabled, True, (s == 0) & ~external & (km == 1)))
        terms_charge = nu * t.species_valence[safe_s]
        charge += sign * xp.sum(terms_charge, axis=0)
        scale += xp.sum(xp.abs(terms_charge), axis=0)
        groups.append(terms._replace(species=safe_s))
    # The supported native subdomain conserves configured chemical charge.
    valid &= xp.all(
        xp.isfinite(charge) & (xp.abs(charge) <= 3e-13 + 8 * np.finfo(float).eps * scale)
    )
    s, mode, km, exponent = t.influencers
    valid &= xp.all((s >= 0) & (s < species_count) & (mode >= 0) & (mode <= DIRECT_INHIBIT))
    valid &= xp.all(xp.isfinite(km) & (km > 0) & xp.isfinite(exponent) & (exponent > 0))
    valid &= xp.all(xp.where(mode > 0, t.active, (s == 0) & (km == 1) & (exponent == 1)))
    return valid, t._replace(
        inside=inside,
        outside=outside,
        reactants=groups[0],
        products=groups[1],
        influencers=t.influencers._replace(species=xp.clip(s, 0, species_count - 1)),
    )


def validate_topology(topology):
    valid, t = _topology_domain(topology, xp=np)
    if not valid:
        raise ValueError("Invalid native transporter ownership, charge balance, terms or padding")
    return t


def _parameter_arrays(parameters, *, xp):
    maximum, area, standard, reversible, temperature = (xp.asarray(v) for v in parameters)
    if (
        not all(_numeric(v) for v in (maximum, area, standard, temperature))
        or reversible.dtype.kind != "b"
    ):
        raise ValueError("Require real parameters and explicit boolean reversible flags")
    if not temperature.ndim:
        temperature = temperature.reshape((1,))
    if temperature.shape[-1] != 1:
        raise ValueError("Temperature requires a singleton final world axis")
    return Parameters(maximum, area, standard, reversible, temperature)


def validate_parameters(parameters, topology):
    t, p = validate_topology(topology), _parameter_arrays(parameters, xp=np)
    shape = np.broadcast_shapes((t.active.size,), *(v.shape for v in p))
    if shape[-1] != t.active.size:
        raise ValueError("Parameter route axis mismatch")
    maximum, area, standard, reversible = (np.broadcast_to(v, shape) for v in p[:4])
    if (
        any(not np.isfinite(v).all() for v in (*p[:3], p.temperature_K))
        or np.any(p.max_flux_mol_m2_s < 0)
        or np.any(p.area_m2 < 0)
        or np.any(p.temperature_K <= 0)
        or np.any(np.where(reversible, False, standard != 0))
        or np.any(
            np.where(t.active, False, (maximum != 0) | (area != 0) | (standard != 0) | reversible)
        )
    ):
        raise ValueError("Invalid native transporter parameters or inactive route padding")
    return Parameters(maximum, area, standard, reversible, p.temperature_K)


def _broadcast(concentration_mM, voltage_V, topology, parameters, availability, rho, *, xp):
    c = xp.asarray(concentration_mM)
    v, opening, density = (xp.asarray(x) for x in (voltage_V, availability, rho))
    p = _parameter_arrays(parameters, xp=xp)
    if (
        c.ndim < 2
        or c.shape[-2:] != (topology.species_valence.size, topology.compartment_active.size)
        or not all(_numeric(x) for x in (c, v, opening, density))
    ):
        raise ValueError(
            "Require real concentrations [..., species, compartment] and route controls"
        )
    shape = xp.broadcast_shapes(
        c.shape[:-2] + (topology.active.size,), *(x.shape for x in (*p, v, opening, density))
    )
    if shape[-1] != topology.active.size:
        raise ValueError("State/parameter/control route axis mismatch")
    return (
        xp.broadcast_to(c, shape[:-1] + c.shape[-2:]),
        *(xp.broadcast_to(x, shape) for x in (v, opening, density)),
        Parameters(*(xp.broadcast_to(x, shape) for x in p)),
    )


def _concentrations(c, terms, t, *, xp):
    owner = xp.where(terms.outside, t.outside, t.inside)
    return xp.where(terms.coefficient > 0, c[..., terms.species, owner], 1.0)


def _regulation(c, t, *, xp):
    s, mode, km, exponent = t.influencers
    value = xp.where(mode > 0, c[..., s, t.inside], 1.0)
    log_loading = exponent * (xp.log(xp.where(value > 0, value, 1.0)) - xp.log(km))
    log_loading = xp.where(value == 0, -xp.inf, log_loading)
    exponential = xp.exp(-xp.abs(log_loading))
    activation = xp.where(log_loading >= 0, 1 / (1 + exponential), exponential / (1 + exponential))
    inhibition = xp.where(log_loading >= 0, exponential / (1 + exponential), 1 / (1 + exponential))
    regular = xp.prod(xp.where(mode == ACTIVATE, activation, 1.0), axis=-2)
    independent = xp.sum(xp.where(mode == INDEPENDENT_ACTIVATE, activation, 0.0), axis=-2)
    inhibitors = xp.prod(xp.where(mode == INHIBIT, inhibition, 1.0), axis=-2)
    direct = (mode == DIRECT_ACTIVATE) | (mode == DIRECT_INHIBIT)
    direct_sum = xp.sum(
        xp.where(mode == DIRECT_ACTIVATE, value, xp.where(mode == DIRECT_INHIBIT, -value, 0.0)),
        axis=-2,
    )
    return (regular + independent) * inhibitors * xp.where(xp.any(direct, axis=0), direct_sum, 1.0)


def native_net_z(topology, *, xp=jnp):
    t = topology
    return xp.sum(
        xp.where(
            t.products.outside, t.products.coefficient * t.species_valence[t.products.species], 0
        ),
        axis=0,
    ) - xp.sum(
        xp.where(
            t.reactants.outside, t.reactants.coefficient * t.species_valence[t.reactants.species], 0
        ),
        axis=0,
    )


def rates(concentration_mM, voltage_V, topology, parameters, availability=1.0, rho=1.0, *, xp=jnp):
    """Unchecked algebra; callers reject invalid trials via domain_valid first.

    Log-domain evaluation preserves the native finite formula without product
    saturation or a silent standard-state correction. It never floors an active
    concentration or constrains a native direct influencer's sign.
    """
    t = topology
    c, voltage, opening, density, p = _broadcast(
        concentration_mM, voltage_V, t, parameters, availability, rho, xp=xp
    )
    reactant, product = (_concentrations(c, terms, t, xp=xp) for terms in (t.reactants, t.products))
    r, s = t.reactants, t.products
    log_loading = r.coefficient * (xp.log(reactant) - xp.log(r.km_mM))
    log_forward = xp.sum(
        xp.where(r.coefficient > 0, -xp.logaddexp(0.0, -log_loading), 0.0), axis=-2
    )
    log_q = xp.sum(
        xp.where(s.coefficient > 0, np.log(1e-3) + s.coefficient * xp.log(product), 0.0), axis=-2
    ) - xp.sum(
        xp.where(r.coefficient > 0, np.log(1e-3) + r.coefficient * xp.log(reactant), 0.0), axis=-2
    )
    charge = native_net_z(t, xp=xp)
    electrical = -charge * F * voltage
    reaction_energy = p.standard_free_energy_J_mol + electrical + R * p.temperature_K * log_q
    reverse_exponent = xp.where(p.reversible, reaction_energy / (R * p.temperature_K), 0.0)
    alpha = _regulation(c, t, xp=xp)
    scale = p.max_flux_mol_m2_s * opening * density * alpha
    nonzero = scale != 0
    log_amplitude = xp.log(xp.where(nonzero, xp.abs(scale), 1.0)) + log_forward
    forward = xp.sign(scale) * xp.exp(log_amplitude)
    near = xp.abs(reverse_exponent) < 0.5
    near_flux = forward * -xp.expm1(xp.where(near, reverse_exponent, 0.0))
    far_exponent = xp.where(~near & nonzero & p.reversible, reverse_exponent, 0.0)
    far_flux = forward - xp.sign(scale) * xp.exp(log_amplitude + far_exponent)
    flux = xp.where(p.reversible, xp.where(near, near_flux, far_flux), forward)
    flux = xp.where(t.active, flux, 0.0)
    extent = flux * p.area_m2 / MOL_PER_FMOL
    current = charge * F * flux
    return Rates(
        flux,
        extent,
        xp.broadcast_to(charge, flux.shape),
        current,
        charge * CHARGE_PER_FMOL * extent,
        xp.where(t.active, xp.exp(log_forward), 0.0),
        xp.where(t.active, alpha, 0.0),
        xp.where(t.active, log_q, 0.0),
        xp.where(t.active, electrical, 0.0),
        xp.where(t.active & p.reversible, reaction_energy, 0.0),
    )


def exchange_rates(signed_extents, topology, *, xp=jnp):
    """Apply each configured reactant/product coefficient once to its owner.

    Extents may be fmol/s rates or integrated fmol. Reaction conversions are
    explicit; conservation of additional chemical moieties belongs to callers.
    """
    t, extent = topology, xp.asarray(signed_extents)
    if extent.ndim < 1 or extent.shape[-1] != t.active.size or not _numeric(extent):
        raise ValueError("Require real extents with explicit final route axis")
    extent = xp.where(t.active, extent, 0.0)
    target = xp.zeros(
        extent.shape[:-1] + (t.species_valence.size, t.compartment_active.size), dtype=extent.dtype
    )
    result = target
    for sign, terms in ((-1, t.reactants), (1, t.products)):
        values = sign * terms.coefficient * extent[..., None, :]
        owner = xp.where(terms.outside, t.outside, t.inside)
        result = result + ordered_scatter(
            values.reshape(values.shape[:-2] + (-1,)),
            target,
            (xp.asarray(terms.species).reshape(-1), owner.reshape(-1)),
            xp=xp,
        )
    return result


def domain_valid(
    concentration_mM, voltage_V, topology, parameters, availability=1.0, rho=1.0, *, xp=jnp
):
    """Complete trial predicate, including blocked substrates and padding."""
    try:
        valid, t = _topology_domain(topology, xp=xp)
        raw_p = _parameter_arrays(parameters, xp=xp)
        c, voltage, opening, density, p = _broadcast(
            concentration_mM, voltage_V, t, parameters, availability, rho, xp=xp
        )
    except (ValueError, TypeError, AttributeError, IndexError):
        return xp.asarray(False)
    valid &= xp.all(xp.where(t.compartment_active, xp.isfinite(c) & (c >= 0), c == 0))
    for terms in (t.reactants, t.products):
        substrate = _concentrations(c, terms, t, xp=xp)
        valid &= xp.all(xp.isfinite(substrate) & (substrate > 0))
    for value in (*raw_p[:3], raw_p.temperature_K, voltage_V, availability, rho):
        value = xp.asarray(value)
        valid &= xp.all(xp.isfinite(value))
    valid &= xp.all(raw_p.temperature_K > 0)
    valid &= xp.all(raw_p.max_flux_mol_m2_s >= 0) & xp.all(raw_p.area_m2 >= 0)
    valid &= xp.all((xp.asarray(availability) >= 0) & (xp.asarray(availability) <= 1))
    valid &= xp.all(xp.asarray(rho) >= 0)
    valid &= xp.all((p.max_flux_mol_m2_s >= 0) & (p.area_m2 >= 0) & (p.temperature_K > 0))
    valid &= xp.all(xp.where(p.reversible, True, p.standard_free_energy_J_mol == 0))
    valid &= xp.all((opening >= 0) & (opening <= 1) & (density >= 0))
    valid &= xp.all(
        xp.where(
            t.active,
            True,
            (p.max_flux_mol_m2_s == 0)
            & (p.area_m2 == 0)
            & (p.standard_free_energy_J_mol == 0)
            & ~p.reversible
            & (voltage == 0)
            & (opening == 0)
            & (density == 0),
        )
    )
    # Neutral replacements exist only in this predicate on a rejected trial.
    # The unchecked physical rates never substitute active substrate values.
    support = xp.zeros((t.species_valence.size, t.compartment_active.size), dtype=int)
    for terms in (t.reactants, t.products):
        owner = xp.where(terms.outside, t.outside, t.inside)
        support = support + ordered_scatter(
            (terms.coefficient > 0).astype(int).reshape(-1),
            support,
            (terms.species.reshape(-1), owner.reshape(-1)),
            xp=xp,
        )
    safe_c = xp.where(xp.isfinite(c) & (c >= 0), c, 1.0)
    safe_c = xp.where((support > 0) & (safe_c == 0), 1.0, safe_c)
    safe_p = Parameters(
        xp.where(xp.isfinite(p.max_flux_mol_m2_s), p.max_flux_mol_m2_s, 0.0),
        xp.where(xp.isfinite(p.area_m2), p.area_m2, 0.0),
        xp.where(xp.isfinite(p.standard_free_energy_J_mol), p.standard_free_energy_J_mol, 0.0),
        p.reversible,
        xp.where(
            xp.isfinite(raw_p.temperature_K) & (raw_p.temperature_K > 0),
            raw_p.temperature_K,
            298.15,
        ),
    )
    values = rates(
        safe_c,
        xp.where(xp.isfinite(voltage), voltage, 0.0),
        t,
        safe_p,
        xp.where(xp.isfinite(opening), opening, 0.0),
        xp.where(xp.isfinite(density), density, 0.0),
        xp=xp,
    )
    return valid & xp.all(
        xp.stack(
            [
                xp.all(xp.isfinite(v))
                for v in (*values, exchange_rates(values.extent_fmol_s, t, xp=xp))
            ]
        )
    )


def material_balances(initial, current, integrated_extents_fmol, topology, *, xp=jnp):
    delta = xp.asarray(current) - xp.asarray(initial)
    expected = exchange_rates(integrated_extents_fmol, topology, xp=xp)
    if delta.shape != expected.shape:
        raise ValueError("Amount histories must match explicit species/compartment ownership")
    residual = delta - expected
    return MaterialBalances(
        residual,
        xp.sum(residual, axis=-1),
        CHARGE_PER_FMOL * xp.sum(topology.species_valence[:, None] * residual, axis=-2),
    )


def bind(
    configurations,
    species_ids,
    species_valence,
    inside,
    outside,
    compartment_active,
    *,
    area_m2,
    temperature_K=298.15,
    route_capacity=None,
):
    """Host bind native cell-zone dictionaries; return static topology/parameters.

    ``inside`` and ``outside`` identify one physical owner per configuration.
    Geometry, profile targeting and the ``ignore ECM`` update choice belong to
    the composing model. Configured regulator zones are retained native no-ops.
    """
    ids, rows = tuple(species_ids), list(configurations)
    if not ids or any(not isinstance(s, str) or not s for s in ids) or len(set(ids)) != len(ids):
        raise ValueError("Require unique nonempty species identifiers")
    if np.asarray(species_valence).shape != (len(ids),):
        raise ValueError("Species identifiers and valences must match")
    n = len(rows)
    capacity = n if route_capacity is None else route_capacity
    if type(capacity) is not int or capacity < n:
        raise ValueError("Route capacity must hold all configured transporters")
    inner, outer = np.asarray(inside), np.asarray(outside)
    if n == 0 and inner.shape == (0,) and outer.shape == (0,):
        inner, outer = inner.astype(int), outer.astype(int)
    if (
        inner.shape != (n,)
        or outer.shape != (n,)
        or inner.dtype.kind not in "iu"
        or outer.dtype.kind not in "iu"
    ):
        raise ValueError("Require one explicit integer inside/outside owner per transporter")
    active, owners_i, owners_o = (
        np.arange(capacity) < n,
        np.zeros(capacity, int),
        np.zeros(capacity, int),
    )
    owners_i[:n], owners_o[:n] = inner, outer
    parsed_r, parsed_p, parsed_inf, maximum, standard, reversible, names = (
        [],
        [],
        [],
        [],
        [],
        [],
        [],
    )
    required = {
        "name",
        "reaction zone",
        "reactants",
        "reactant multipliers",
        "Km reactants",
        "products",
        "product multipliers",
        "Km products",
        "transfered out of cell",
        "transfered into cell",
        "max rate",
        "standard free energy",
    }
    optional = {
        "ignore ECM",
        "apply to",
        "transporter activators",
        "activator Km",
        "activator n",
        "activator zone",
        "transporter inhibitors",
        "inhibitor Km",
        "inhibitor n",
        "inhibitor zone",
    }
    for row in rows:
        if (
            not isinstance(row, dict)
            or not required <= row.keys()
            or set(row) - required - optional
        ):
            raise ValueError("Unsupported or incomplete native transporter configuration")
        name = row["name"]
        if not isinstance(name, str) or not name or name in names or row["reaction zone"] != "cell":
            raise ValueError("Require unique transporter names and supported cell reaction zone")
        names.append(name)
        groups = []
        for role, multiplier, km_key, transfer in (
            ("reactants", "reactant multipliers", "Km reactants", "transfered into cell"),
            ("products", "product multipliers", "Km products", "transfered out of cell"),
        ):
            substances, coefficients, km = row[role], row[multiplier], row[km_key]
            moved = row[transfer]
            if moved is None or moved == "None":
                moved = []
            if (
                not isinstance(substances, list)
                or not substances
                or any(not isinstance(s, str) for s in substances)
                or len(set(substances)) != len(substances)
                or any(s not in ids for s in substances)
                or not isinstance(coefficients, list)
                or not isinstance(km, list)
                or len(substances) != len(coefficients)
                or len(substances) != len(km)
                or not all(_number(v, positive=True) for v in (*coefficients, *km))
                or not isinstance(moved, list)
                or len(set(moved)) != len(moved)
                or not set(moved) <= set(substances)
            ):
                raise ValueError("Invalid native substrate, multiplier, Km or transfer ownership")
            groups.append(
                [
                    (ids.index(s), s in moved, float(v), float(k))
                    for s, v, k in zip(substances, coefficients, km, strict=True)
                ]
            )
        parsed_r.append(groups[0])
        parsed_p.append(groups[1])
        influencers = []
        for label, km_key, exponent_key, activator in (
            ("transporter activators", "activator Km", "activator n", True),
            ("transporter inhibitors", "inhibitor Km", "inhibitor n", False),
        ):
            configured = row.get(label)
            if configured is None or configured == "None" or configured == []:
                continue
            km, exponent = row.get(km_key), row.get(exponent_key)
            if (
                not isinstance(configured, list)
                or not isinstance(km, list)
                or not isinstance(exponent, list)
                or not len(configured) == len(km) == len(exponent)
            ):
                raise ValueError("Influencer names, Km and exponents must match")
            for index, (substance, k, power) in enumerate(
                zip(configured, km, exponent, strict=True)
            ):
                if (
                    not isinstance(substance, str)
                    or not _number(k, positive=True)
                    or not _number(power, positive=True)
                ):
                    raise ValueError("Invalid influencer identity, Km or exponent")
                substance = substance[:-1] if substance.endswith("*") else substance
                mode = ACTIVATE if activator else INHIBIT
                if substance.endswith("!"):
                    substance = substance[:-1]
                    mode = INDEPENDENT_ACTIVATE if activator else INHIBIT
                elif substance.endswith("&"):
                    substance = substance[:-1]
                    mode = DIRECT_ACTIVATE if activator else DIRECT_INHIBIT
                    if not activator and index != len(configured) - 1:
                        raise ValueError("Native direct inhibitor must be sole or last")
                if substance not in ids:
                    raise ValueError("Unknown native influencer species or suffix order")
                influencers.append((ids.index(substance), mode, float(k), float(power)))
        modes = {term[1] for term in influencers}
        if modes == {DIRECT_ACTIVATE, DIRECT_INHIBIT}:
            raise ValueError(
                "Native generator cannot combine only-direct activators and inhibitors"
            )
        parsed_inf.append(influencers)
        value = row["standard free energy"]
        rev = value is not None and value != "None"
        if not _number(row["max rate"], nonnegative=True) or (rev and not _number(value)):
            raise ValueError("Invalid native maximum rate or standard free energy")
        if rev and not any(term[1] for group in groups for term in group):
            raise ValueError("Native reversible generator requires at least one transfer term")
        maximum.append(float(row["max rate"]))
        standard.append(float(value) if rev else 0.0)
        reversible.append(rev)

    def packed(groups, cls, defaults, dtypes):
        count = max(map(len, groups), default=0)
        values = [
            np.full((count, capacity), v, dtype=dtype)
            for v, dtype in zip(defaults, dtypes, strict=True)
        ]
        for route, terms in enumerate(groups):
            for term, fields in enumerate(terms):
                for target, value in zip(values, fields, strict=True):
                    target[term, route] = value
        return cls(*values)

    topology = validate_topology(
        Topology(
            np.asarray(species_valence),
            np.asarray(compartment_active),
            owners_i,
            owners_o,
            active,
            packed(parsed_r, Terms, (0, False, 0.0, 1.0), (int, bool, float, float)),
            packed(parsed_p, Terms, (0, False, 0.0, 1.0), (int, bool, float, float)),
            packed(parsed_inf, Influencers, (0, 0, 1.0, 1.0), (int, int, float, float)),
        )
    )
    if topology.species_valence.shape != (len(ids),):
        raise ValueError("Species identifiers and valences must match")
    area = np.asarray(area_m2)
    if (
        not _numeric(area)
        or area.shape not in ((), (n,))
        or not np.isfinite(area).all()
        or np.any(area < 0)
    ):
        raise ValueError("Require real scalar area or one area per configured transporter")
    area = np.broadcast_to(area, (n,))

    def padded(values, dtype=float):
        result = np.zeros(capacity, dtype=dtype)
        result[:n] = values
        return result

    parameters = validate_parameters(
        Parameters(
            padded(maximum), padded(area), padded(standard), padded(reversible, bool), temperature_K
        ),
        topology,
    )
    return topology, parameters
