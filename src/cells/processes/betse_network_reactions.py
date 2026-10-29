"""Literal BETSE 1.5.0 local reaction and cell growth/decay laws, version @1.

State is [..., species, compartment]; routes have one explicit local owner.
Concentration rates are mM/s, volumes m3 and extents fmol/s. Reversible cell,
mitochondrial and environment branches intentionally differ. The literal Q
conversion is outside each power. No heat, ATP, transport or clipping is owned.
"""

from numbers import Real
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.numerics.extracellular_field import ordered_scatter

LAW_ID = "betse_network_reactions_source_v1_5_0@1"
CELL, MIT, ENV, GROWTH = range(1, 5)
ACTIVATE, INDEPENDENT, DIRECT_ACTIVATE, INHIBIT, DIRECT_INHIBIT = range(1, 6)
NATIVE_R = 8.314


class Terms(NamedTuple):
    species: object
    coefficient: object  # Zero is padding.
    km_mM: object


class Influencers(NamedTuple):
    species: object
    owner: object
    mode: object  # Zero is padding.
    constant: object  # Native env reaction / cell regulator is the literal 1.
    km_mM: object
    exponent: object


class Topology(NamedTuple):
    species_valence: object
    compartment_zone: object  # 0 padding; CELL, MIT or ENV.
    kind: object  # 0 route padding; CELL, MIT, ENV or GROWTH.
    owner: object
    growth_species: object
    stoichiometry: object  # [species, route], including growth identity columns.
    reactants: Terms
    products: Terms
    influencers: Influencers
    decay_influencers: Influencers


class Parameters(NamedTuple):
    maximum_mM_s: object  # Reaction vmax or growth production rate.
    standard_free_energy_J_mol: object
    reversible: object
    growth_enabled: object
    basal_decay_per_s: object
    regulated_decay_per_s: object
    growth_scale: object
    time_factor: object
    growth_modulation: object
    growth_target: object
    temperature_K: object  # Scalar or [..., 1], one per independent world.
    gas_constant_J_mol_K: object  # Explicit native default; optional SI override.


class Rates(NamedTuple):
    concentration_rate_mM_s: object
    extent_fmol_s: object
    forward_saturation: object
    backward_saturation: object
    regulation: object
    log_source_quotient: object
    production_mM_s: object
    basal_decay_mM_s: object
    regulated_decay_mM_s: object
    growth_optimization_alpha: object  # Native auxiliary, not production rate.
    decay_optimization_mM_s: object  # Native auxiliary excludes regulated decay.


class Accounting(NamedTuple):
    reaction_conversion_fmol: object
    growth_source_sink_fmol: object
    total_change_fmol: object
    route_change_fmol: object  # [..., species, route], before owner accumulation.
    charge_change_in_elementary_fmol: object  # [..., compartment]; no current law.


def _real(value):
    return value.dtype.kind in "fiu"


def _number(value, *, positive=False, nonnegative=False):
    return (
        isinstance(value, Real)
        and not isinstance(value, (bool, np.bool_))
        and np.isfinite(value)
        and (not positive or value > 0)
        and (not nonnegative or value >= 0)
    )


def _topology_domain(topology, *, xp):
    z, zone, kind, owner, gs, matrix = (xp.asarray(v) for v in topology[:6])
    if (
        z.ndim != 1
        or not z.size
        or not _real(z)
        or zone.ndim != 1
        or not zone.size
        or zone.dtype.kind not in "iu"
        or kind.ndim != 1
        or kind.dtype.kind not in "iu"
        or owner.shape != kind.shape
        or owner.dtype.kind not in "iu"
        or gs.shape != kind.shape
        or gs.dtype.kind not in "iu"
        or matrix.shape != (z.size, kind.size)
        or not _real(matrix)
    ):
        raise ValueError("Require explicit species, compartment and route axes")
    valid = xp.all(xp.isfinite(z)) & xp.all((zone >= 0) & (zone <= ENV))
    valid &= xp.all((kind >= 0) & (kind <= GROWTH))
    valid &= xp.all((owner >= 0) & (owner < zone.size) & (gs >= 0) & (gs < z.size))
    safe_owner, safe_gs = xp.clip(owner, 0, zone.size - 1), xp.clip(gs, 0, z.size - 1)
    expected_zone = xp.where(kind == GROWTH, CELL, kind)
    valid &= xp.all(xp.where(kind > 0, zone[safe_owner] == expected_zone, owner == 0))
    valid &= xp.all(xp.where(kind == GROWTH, True, gs == 0))
    expected_matrix = xp.where(
        (kind == GROWTH)[None, :] & (xp.arange(z.size)[:, None] == safe_gs[None, :]), 1.0, 0.0
    )
    groups = []
    for sign, raw in ((-1, topology.reactants), (1, topology.products)):
        s, nu, km = (xp.asarray(v) for v in raw)
        if (
            s.ndim != 2
            or s.shape[-1] != kind.size
            or s.dtype.kind not in "iu"
            or nu.shape != s.shape
            or km.shape != s.shape
            or not _real(nu)
            or not _real(km)
        ):
            raise ValueError("Substrate arrays require [term, route] axes")
        valid &= xp.all((s >= 0) & (s < z.size))
        valid &= xp.all(xp.isfinite(nu) & (nu >= 0) & xp.isfinite(km) & (km > 0))
        valid &= xp.all(xp.where(nu > 0, (kind > 0) & (kind != GROWTH), (s == 0) & (km == 1)))
        valid &= xp.all(xp.where((kind > 0) & (kind != GROWTH), xp.any(nu > 0, axis=0), True))
        safe_s = xp.clip(s, 0, z.size - 1)
        # Preserve the native sequential += order, including repeated species.
        for term in range(s.shape[0]):
            expected_matrix += sign * xp.where(
                xp.arange(z.size)[:, None] == safe_s[term], nu[term], 0.0
            )
        groups.append(Terms(safe_s, nu, km))
    valid &= xp.all(xp.isfinite(matrix) & (matrix == expected_matrix))
    influencers = []
    for decay, raw in ((False, topology.influencers), (True, topology.decay_influencers)):
        s, io, mode, constant, km, n = (xp.asarray(v) for v in raw)
        if (
            s.ndim != 2
            or s.shape[-1] != kind.size
            or s.dtype.kind not in "iu"
            or io.shape != s.shape
            or io.dtype.kind not in "iu"
            or mode.shape != s.shape
            or mode.dtype.kind not in "iu"
            or constant.shape != s.shape
            or constant.dtype.kind != "b"
            or km.shape != s.shape
            or n.shape != s.shape
            or not _real(km)
            or not _real(n)
        ):
            raise ValueError("Influencer arrays require matching [term, route] axes")
        valid &= xp.all((s >= 0) & (s < z.size) & (io >= 0) & (io < zone.size))
        valid &= xp.all((mode >= 0) & (mode <= DIRECT_INHIBIT))
        valid &= xp.all(xp.isfinite(km) & (km > 0) & xp.isfinite(n) & (n > 0))
        safe_io = xp.clip(io, 0, zone.size - 1)
        enabled = mode > 0
        valid &= xp.all(
            xp.where(
                enabled,
                kind == GROWTH if decay else kind > 0,
                (s == 0) & (io == 0) & ~constant & (km == 1) & (n == 1),
            )
        )
        valid &= xp.all(xp.where(constant, (kind == ENV) & enabled, True))
        allowed = xp.where(
            kind == ENV,
            (safe_io == safe_owner) & (zone[safe_io] == ENV),
            xp.where(
                kind == MIT,
                safe_io == safe_owner,
                ((zone[safe_io] == CELL) & (safe_io == safe_owner)) | (zone[safe_io] == ENV),
            ),
        )
        valid &= xp.all(xp.where(enabled & ~constant, allowed, True))
        has_a, has_i = (
            xp.any((mode >= ACTIVATE) & (mode <= DIRECT_ACTIVATE), axis=0),
            xp.any(mode >= INHIBIT, axis=0),
        )
        regular_a = xp.any((mode == ACTIVATE) | (mode == INDEPENDENT), axis=0)
        regular_i = xp.any(mode == INHIBIT, axis=0)
        valid &= xp.all(~(has_a & has_i & ~regular_a & ~regular_i))
        # Direct inhibitors before another inhibitor alter native parsing.
        seen_direct = xp.cumsum((mode == DIRECT_INHIBIT).astype(int), axis=0)
        valid &= xp.all(xp.where(mode >= INHIBIT, seen_direct <= (mode == DIRECT_INHIBIT), True))
        influencers.append(Influencers(xp.clip(s, 0, z.size - 1), safe_io, mode, constant, km, n))
    return valid, Topology(z, zone, kind, safe_owner, safe_gs, matrix, *groups, *influencers)


def validate_topology(topology):
    valid, t = _topology_domain(topology, xp=np)
    if not valid:
        raise ValueError("Invalid native reaction ownership, matrix, influencers or padding")
    return t


def _parameters(parameters, t, *, xp):
    values = [xp.asarray(v) for v in parameters]
    for index, value in enumerate(values):
        if value.dtype.kind != "b" if index in (2, 3, 9) else not _real(value):
            raise ValueError("Require real parameters and explicit boolean flags")
    for index in (10, 11):
        if not values[index].ndim:
            values[index] = values[index].reshape((1,))
        if values[index].shape[-1] != 1:
            raise ValueError("Temperature and R require singleton world axes")
    shape = np.broadcast_shapes((t.kind.size,), *(v.shape for v in values))
    if shape[-1] != t.kind.size:
        raise ValueError("Parameter route axis mismatch")
    return Parameters(*(xp.broadcast_to(v, shape) if i < 10 else v for i, v in enumerate(values)))


def _parameter_domain(p, t, *, xp):
    active, growth = t.kind > 0, t.kind == GROWTH
    valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in p]))
    for value in (p.maximum_mM_s, p.basal_decay_per_s, p.regulated_decay_per_s, p.time_factor):
        valid &= xp.all(value >= 0)
    valid &= xp.all((p.growth_scale > 0) & (p.temperature_K > 0) & (p.gas_constant_J_mol_K > 0))
    valid &= xp.all(xp.isfinite(p.temperature_K * p.gas_constant_J_mol_K))
    valid &= xp.all(xp.where(p.reversible, active & ~growth, p.standard_free_energy_J_mol == 0))
    valid &= xp.all(
        xp.where(
            growth,
            True,
            ~p.growth_enabled
            & ~p.growth_target
            & (p.basal_decay_per_s == 0)
            & (p.regulated_decay_per_s == 0)
            & (p.growth_scale == 1)
            & (p.time_factor == 1)
            & (p.growth_modulation == 1),
        )
    )
    valid &= xp.all(xp.where(active, True, (p.maximum_mM_s == 0) & ~p.reversible))
    valid &= xp.all(
        xp.where(
            growth & ~p.growth_enabled,
            (p.maximum_mM_s == 0)
            & (p.basal_decay_per_s == 0)
            & (p.regulated_decay_per_s == 0)
            & ~p.growth_target,
            True,
        )
    )
    return valid


def validate_parameters(parameters, topology):
    t = validate_topology(topology)
    p = _parameters(parameters, t, xp=np)
    if not _parameter_domain(p, t, xp=np):
        raise ValueError("Invalid native reaction/growth parameters or padding")
    return p


def _substrates(c, terms, t, *, xp):
    return xp.where(terms.coefficient > 0, c[..., terms.species, t.owner], 1.0)


def _regulation(c, inf, *, xp):
    s, owner, mode, constant, km, n = inf
    value = xp.where(mode > 0, c[..., s, owner], 1.0)
    log_load = n * (xp.log(value) - xp.log(km))
    hill_a = xp.where(constant, 1.0, xp.exp(-xp.logaddexp(0.0, -log_load)))
    hill_i = xp.where(constant, 1.0, xp.exp(-xp.logaddexp(0.0, log_load)))
    regular = xp.prod(xp.where(mode == ACTIVATE, hill_a, 1.0), axis=-2)
    independent = xp.sum(xp.where(mode == INDEPENDENT, hill_a, 0.0), axis=-2)
    inhibitor = xp.prod(xp.where(mode == INHIBIT, hill_i, 1.0), axis=-2)
    direct = xp.sum(
        xp.where(
            mode == DIRECT_ACTIVATE,
            xp.where(constant, 1.0, value),
            xp.where(mode == DIRECT_INHIBIT, xp.where(constant, 1.0, -value), 0.0),
        ),
        axis=-2,
    )
    return (
        (regular + independent)
        * inhibitor
        * xp.where(
            xp.any((mode == DIRECT_ACTIVATE) | (mode == DIRECT_INHIBIT), axis=0), direct, 1.0
        )
    )


def rates(concentration_mM, volume_m3, topology, parameters, *, xp=jnp):
    """Unchecked literal rates; callers accept trials using ``domain_valid``.

    All routes evaluate the same incoming state. Growth profile targets apply
    to the complete net rate. Native optimization auxiliaries remain unmasked.
    Every owner volume is explicit; there is no implicit reservoir or transport.
    """
    t, c, volume = topology, xp.asarray(concentration_mM), xp.asarray(volume_m3)
    if (
        c.ndim < 2
        or c.shape[-2:] != (t.species_valence.size, t.compartment_zone.size)
        or not _real(c)
    ):
        raise ValueError("Concentration axes must match species/compartments")
    if not volume.ndim or volume.shape[-1] != t.compartment_zone.size or not _real(volume):
        raise ValueError("Volumes require an explicit final compartment axis")
    p = _parameters(parameters, t, xp=xp)
    r, s = t.reactants, t.products
    cr, cp = (_substrates(c, terms, t, xp=xp) for terms in (r, s))
    logs = []
    for terms, value in ((r, cr), (s, cp)):
        load = terms.coefficient * (xp.log(value) - xp.log(terms.km_mM))
        logs.append(
            xp.sum(xp.where(terms.coefficient > 0, -xp.logaddexp(0.0, -load), 0.0), axis=-2)
        )
    lf, lb = logs
    log_q = xp.sum(
        xp.where(s.coefficient > 0, np.log(1e-3) + s.coefficient * xp.log(cp), 0.0), axis=-2
    ) - xp.sum(xp.where(r.coefficient > 0, np.log(1e-3) + r.coefficient * xp.log(cr), 0.0), axis=-2)
    alpha = _regulation(c, t.influencers, xp=xp)
    reverse = xp.where(
        p.reversible,
        log_q + p.standard_free_energy_J_mol / (p.gas_constant_J_mol_K * p.temperature_K),
        0.0,
    )
    # The reversible cell generator drops BOTH saturation coefficients.
    base = xp.where(t.kind == CELL, 0.0, lf)
    near = xp.abs(reverse) < 0.5
    common = xp.exp(base) * -xp.expm1(xp.where(near, reverse, 0.0))
    far = xp.exp(base) - xp.exp(base + xp.where(near, 0.0, reverse))
    reversible_rate = xp.where(near, common, far)
    mit_exponent = lb + reverse - lf
    mit_near = xp.abs(mit_exponent) < 0.5
    mit_difference = xp.where(
        mit_near,
        xp.exp(lf) * -xp.expm1(xp.where(mit_near, mit_exponent, 0.0)),
        xp.exp(lf) - xp.exp(lb + reverse),
    )
    reversible_rate = xp.where(t.kind == MIT, mit_difference, reversible_rate)
    chemical = p.maximum_mM_s * alpha * xp.where(p.reversible, reversible_rate, xp.exp(lf))
    is_growth, active = t.kind == GROWTH, t.kind > 0
    growth_alpha = xp.where(p.growth_enabled & is_growth, alpha, 0.0)
    decay_alpha = _regulation(c, t.decay_influencers, xp=xp)
    cc = c[..., t.growth_species, t.owner] / p.growth_scale
    production = p.maximum_mM_s * p.time_factor * p.growth_modulation * growth_alpha
    basal = xp.where(is_growth & p.growth_enabled, p.basal_decay_per_s * p.time_factor * cc, 0.0)
    regulated = xp.where(
        is_growth & p.growth_enabled,
        p.regulated_decay_per_s * p.time_factor * decay_alpha * cc,
        0.0,
    )
    net = xp.where(
        is_growth, xp.where(p.growth_target, production - basal - regulated, 0.0), chemical
    )
    net = xp.where(active, net, 0.0)
    shape = np.broadcast_shapes(net.shape, volume.shape[:-1] + (t.kind.size,))
    net = xp.broadcast_to(net, shape)
    zero = xp.zeros_like(net)

    def local(value):
        return xp.broadcast_to(value, shape)

    reaction = active & ~is_growth
    return Rates(
        net,
        net * volume[..., t.owner] / 1e-15,
        local(xp.where(reaction, xp.exp(lf), 0.0)),
        local(xp.where(reaction, xp.exp(lb), 0.0)),
        local(xp.where(active, alpha, 0.0)),
        local(xp.where(reaction, log_q, 0.0)),
        local(xp.where(is_growth & p.growth_target, production, 0.0)),
        local(xp.where(p.growth_target, basal, 0.0)),
        local(xp.where(p.growth_target, regulated, 0.0)),
        local(growth_alpha) + zero,
        local(basal) + zero,
    )


def accounting(extents_fmol, topology, *, xp=jnp):
    """Signed stoichiometric conversions and named growth source/sink amounts.

    Arguments may instead be fmol/s rates. Unbalanced chemical reactions remain
    visible as explicit species/charge changes; no missing fuel is invented.
    """
    t, extents = topology, xp.asarray(extents_fmol)
    if not extents.ndim or extents.shape[-1] != t.kind.size or not _real(extents):
        raise ValueError("Extents require an explicit final route axis")
    changes = t.stoichiometry * xp.where(t.kind > 0, extents, 0.0)[..., None, :]
    shape = changes.shape[:-2] + (t.species_valence.size, t.compartment_zone.size)
    target = xp.zeros(shape, dtype=changes.dtype)
    si = xp.broadcast_to(xp.arange(t.species_valence.size)[:, None], changes.shape[-2:]).reshape(-1)
    owner = xp.broadcast_to(t.owner, changes.shape[-2:]).reshape(-1)

    def accumulate(values):
        return ordered_scatter(
            values.reshape(values.shape[:-2] + (-1,)), target, (si, owner), xp=xp
        )

    growth = accumulate(xp.where(t.kind == GROWTH, changes, 0.0))
    reaction = accumulate(xp.where((t.kind > 0) & (t.kind != GROWTH), changes, 0.0))
    total = reaction + growth
    charge = xp.sum(total * t.species_valence[:, None], axis=-2)
    return Accounting(reaction, growth, total, changes, charge)


def material_residual(initial_fmol, current_fmol, integrated_extents_fmol, topology, *, xp=jnp):
    expected = accounting(integrated_extents_fmol, topology, xp=xp).total_change_fmol
    initial, current = xp.asarray(initial_fmol), xp.asarray(current_fmol)
    if initial.shape != current.shape or initial.shape != expected.shape:
        raise ValueError("Amount histories must match species/compartment ownership")
    return current - initial - expected


def projected_changes(extents_fmol, topology, species_weights, *, xp=jnp):
    """Return [..., declared moiety/charge basis, route] signed changes.

    The caller supplies meaningful basis weights [basis, species] and accounts
    for any nonzero result as an explicit source/sink. No balance is assumed.
    """
    weights = xp.asarray(species_weights)
    if (
        weights.ndim != 2
        or weights.shape[-1] != topology.species_valence.size
        or not _real(weights)
    ):
        raise ValueError("Weights require [basis, species] axes")
    return xp.einsum(
        "ms,...sr->...mr", weights, accounting(extents_fmol, topology, xp=xp).route_change_fmol
    )


def domain_valid(concentration_mM, volume_m3, topology, parameters, *, xp=jnp):
    """Complete scalar predicate for one world; use vmap for world isolation."""
    try:
        valid, t = _topology_domain(topology, xp=xp)
        p = _parameters(parameters, t, xp=xp)
        c, volume = xp.asarray(concentration_mM), xp.asarray(volume_m3)
        values = rates(c, volume, t, p, xp=xp)
        ledger = accounting(values.extent_fmol_s, t, xp=xp)
    except (ValueError, TypeError, AttributeError, IndexError):
        return xp.asarray(False)
    valid &= _parameter_domain(p, t, xp=xp)
    valid &= xp.all(xp.where(t.compartment_zone > 0, xp.isfinite(c) & (c >= 0), c == 0))
    valid &= xp.all(
        xp.where(t.compartment_zone > 0, xp.isfinite(volume) & (volume > 0), volume == 0)
    )
    for terms in (t.reactants, t.products):
        value = _substrates(c, terms, t, xp=xp)
        valid &= xp.all(xp.isfinite(value) & (value > 0))
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (*values, *ledger)]))
    return valid


def bind(
    reactions,
    growth,
    species_ids,
    species_valence,
    compartment_zones,
    *,
    cell_to_environment=None,
    growth_targets=None,
    growth_modulation=None,
    time_dilation=1.0,
    temperature_K=298.15,
    gas_constant_J_mol_K=NATIVE_R,
    route_capacity=None,
):
    """Bind native dictionaries to explicit owners and return topology/parameters.

    Each definition expands over every owner in its configured zone. Route order
    is growth in supplied molecule order, then cell/mit/env definitions in native
    insertion order, each in owner order. Growth target/modulation maps are keyed
    by molecule name with one value per CELL owner. Profile/function evaluation,
    geometry, transport, checkpoint migration and time stepping are caller-owned.
    """
    ids, raw_reactions, raw_growth = tuple(species_ids), list(reactions), list(growth)
    if not ids or len(set(ids)) != len(ids) or any(not isinstance(s, str) or not s for s in ids):
        raise ValueError("Require unique nonempty species identifiers")
    if np.asarray(species_valence).shape != (len(ids),):
        raise ValueError("Species identities and valences must match")
    zones_by_name = {"cell": CELL, "mit": MIT, "env": ENV, "padding": 0}
    if not compartment_zones or any(s not in zones_by_name for s in compartment_zones):
        raise ValueError("Require explicit compartment zones")
    zones = np.array([zones_by_name[s] for s in compartment_zones], int)
    cells = np.flatnonzero(zones == CELL)
    mapping = {} if cell_to_environment is None else dict(cell_to_environment)
    if any(
        type(k) not in (int, np.int64)
        or type(v) not in (int, np.int64)
        or k not in cells
        or v < 0
        or v >= len(zones)
        or zones[v] != ENV
        for k, v in mapping.items()
    ):
        raise ValueError("Invalid explicit cell-to-environment ownership map")
    targets, modulation = growth_targets or {}, growth_modulation or {}
    names_growth = [r.get("name") for r in raw_growth]
    if len(set(names_growth)) != len(names_growth) or any(s not in ids for s in names_growth):
        raise ValueError("Growth molecule names must be unique known species")
    if set(targets) - set(names_growth) or set(modulation) - set(names_growth):
        raise ValueError("Unknown growth control name")
    if not _number(time_dilation, nonnegative=True):
        raise ValueError("Require finite nonnegative time dilation")

    def regulators(row, owner, zone, *, growth_role=None):
        result = []
        for activating in (True, False):
            if growth_role is None:
                prefix = "activator" if activating else "inhibitor"
                label = "reaction " + prefix + "s"
                keys = (prefix + " Km", prefix + " n", prefix + " zone")
            else:
                label = ("decay " if growth_role == "decay" else "") + (
                    "activators" if activating else "inhibitors"
                )
                keys = ("Km " + label, "n " + label, "zone " + label)
            labels = row.get(label)
            if labels is None or labels == "None" or labels == []:
                continue
            km, n, tags = (row.get(k) for k in keys)
            if tags is None or tags == "None" or tags == []:
                tags = ["cell"] * len(labels)
            if not all(isinstance(v, list) for v in (labels, km, n, tags)) or not len(
                labels
            ) == len(km) == len(n) == len(tags):
                raise ValueError("Influencer names, Km, exponents and zones must match")
            for i, (name, k, power, tag) in enumerate(zip(labels, km, n, tags, strict=True)):
                if (
                    not isinstance(name, str)
                    or not _number(k, positive=True)
                    or not _number(power, positive=True)
                    or tag not in ("cell", "env")
                ):
                    raise ValueError("Invalid native influencer or zone")
                name = name[:-1] if name.endswith("*") else name
                mode = ACTIVATE if activating else INHIBIT
                if name.endswith("!"):
                    name = name[:-1]
                    mode = INDEPENDENT if activating else INHIBIT
                elif name.endswith("&"):
                    name = name[:-1]
                    mode = DIRECT_ACTIVATE if activating else DIRECT_INHIBIT
                    if not activating and i != len(labels) - 1:
                        raise ValueError("Native direct inhibitor must be sole or last")
                if name not in ids:
                    raise ValueError("Unknown influencer species or suffix order")
                constant = zone == ENV and tag == "cell"
                io = owner
                if zone in (CELL, GROWTH) and tag == "env":
                    if owner not in mapping:
                        raise ValueError(
                            "Cell extracellular regulator requires an explicit environment map"
                        )
                    io = mapping[owner]
                result.append((ids.index(name), io, mode, constant, float(k), float(power)))
        modes = {term[2] for term in result}
        if modes == {DIRECT_ACTIVATE, DIRECT_INHIBIT}:
            raise ValueError("Native only-direct activator/inhibitor combination is broken")
        return result

    routes, seen = [], set()
    required = {
        "name",
        "reaction zone",
        "reactants",
        "reactant multipliers",
        "Km reactants",
        "products",
        "product multipliers",
        "Km products",
        "max rate",
        "standard free energy",
    }
    optional = {
        "reaction activators",
        "activator Km",
        "activator n",
        "activator zone",
        "reaction inhibitors",
        "inhibitor Km",
        "inhibitor n",
        "inhibitor zone",
    }
    for row in raw_reactions:
        if (
            not isinstance(row, dict)
            or not required <= row.keys()
            or set(row) - required - optional
        ):
            raise ValueError("Unsupported or incomplete native reaction dictionary")
        name, zone = row["name"], row["reaction zone"]
        if (
            not isinstance(name, str)
            or not name
            or zone not in ("cell", "mit", "env")
            or (zone, name) in seen
        ):
            raise ValueError("Require unique per-zone reaction names and enabled native zones")
        seen.add((zone, name))
        if not np.any(zones == zones_by_name[zone]):
            raise ValueError("Configured reaction zone has no owners")
        for role, mult, kmkey in (
            ("reactants", "reactant multipliers", "Km reactants"),
            ("products", "product multipliers", "Km products"),
        ):
            items, nu, km = row[role], row[mult], row[kmkey]
            if (
                not all(isinstance(v, list) and len(v) for v in (items, nu, km))
                or not len(items) == len(nu) == len(km)
                or any(s not in ids for s in items)
                or not all(_number(v, positive=True) for v in (*nu, *km))
            ):
                raise ValueError("Require nonempty matching native substrates, multipliers and Km")
        energy = row["standard free energy"]
        if (
            energy is None
            or (energy != "None" and not _number(energy))
            or not _number(row["max rate"], nonnegative=True)
        ):
            raise ValueError("Native reader requires numeric free energy or literal string None")
    for row in raw_growth:
        if set(row) - {"name", "growth and decay", "use time dilation"}:
            raise ValueError("Unsupported growth molecule keys")
        name, gad = row["name"], row.get("growth and decay")
        enabled = gad is not None and gad != "None"
        if not isinstance(row.get("use time dilation", False), bool):
            raise ValueError("Require boolean time dilation flag")
        allowed_gad = {
            "production rate",
            "decay rate",
            "scale factor",
            "apply to",
            "modulator function",
            "activators",
            "Km activators",
            "n activators",
            "zone activators",
            "inhibitors",
            "Km inhibitors",
            "n inhibitors",
            "zone inhibitors",
            "decay max",
            "decay activators",
            "Km decay activators",
            "n decay activators",
            "zone decay activators",
            "decay inhibitors",
            "Km decay inhibitors",
            "n decay inhibitors",
            "zone decay inhibitors",
        }
        if enabled and (
            not isinstance(gad, dict)
            or not {"production rate", "decay rate", "apply to"} <= gad.keys()
            or set(gad) - allowed_gad
        ):
            raise ValueError("Incomplete or unsupported native growth dictionary")
        gad = gad if enabled else {}
        if enabled and (
            not all(
                _number(v, nonnegative=True)
                for v in (gad["production rate"], gad["decay rate"], gad.get("decay max", 0.0))
            )
            or not _number(gad.get("scale factor", 1.0), positive=True)
        ):
            raise ValueError("Invalid native growth rate or nested scale")
        if enabled and name not in targets and gad["apply to"] not in (None, "all"):
            raise ValueError("Named growth profiles require explicit target masks")
        if (
            enabled
            and gad.get("modulator function") not in (None, "None")
            and name not in modulation
        ):
            raise ValueError("Named growth modulator requires explicit sampled values")
        target = np.asarray(targets.get(name, np.ones(cells.size, bool)))
        mod = np.asarray(modulation.get(name, np.ones(cells.size)))
        if (
            target.shape != cells.shape
            or target.dtype.kind != "b"
            or mod.shape != cells.shape
            or not _real(mod)
            or not np.isfinite(mod).all()
        ):
            raise ValueError("Growth controls require one boolean/real value per cell")
        for i, owner in enumerate(cells):
            routes.append(
                dict(
                    kind=GROWTH,
                    owner=owner,
                    species=ids.index(name),
                    r=[],
                    p=[],
                    inf=regulators(gad, owner, GROWTH, growth_role="growth") if enabled else [],
                    decayinf=regulators(gad, owner, GROWTH, growth_role="decay") if enabled else [],
                    maximum=gad.get("production rate", 0.0),
                    standard=0.0,
                    reversible=False,
                    enabled=enabled,
                    basal=gad.get("decay rate", 0.0),
                    regulated=gad.get("decay max", 0.0),
                    scale=gad.get("scale factor", 1.0),
                    time=time_dilation if row.get("use time dilation", False) else 1.0,
                    mod=mod[i],
                    target=bool(target[i]) and enabled,
                )
            )
    for zone in ("cell", "mit", "env"):
        for row in raw_reactions:
            if row["reaction zone"] != zone:
                continue
            for owner in np.flatnonzero(zones == zones_by_name[zone]):
                groups = []
                for role, mult, kmkey in (
                    ("reactants", "reactant multipliers", "Km reactants"),
                    ("products", "product multipliers", "Km products"),
                ):
                    groups.append(
                        [
                            (ids.index(s), float(nu), float(km))
                            for s, nu, km in zip(row[role], row[mult], row[kmkey], strict=True)
                        ]
                    )
                energy = row["standard free energy"]
                routes.append(
                    dict(
                        kind=zones_by_name[zone],
                        owner=owner,
                        species=0,
                        r=groups[0],
                        p=groups[1],
                        inf=regulators(row, owner, zones_by_name[zone]),
                        decayinf=[],
                        maximum=row["max rate"],
                        standard=0.0 if energy == "None" else float(energy),
                        reversible=energy != "None",
                        enabled=False,
                        basal=0.0,
                        regulated=0.0,
                        scale=1.0,
                        time=1.0,
                        mod=1.0,
                        target=False,
                    )
                )
    n = len(routes)
    capacity = n if route_capacity is None else route_capacity
    if type(capacity) is not int or capacity < n:
        raise ValueError("Route capacity must hold the expanded native network")

    def column(key, default, dtype):
        result = np.full(capacity, default, dtype=dtype)
        result[:n] = [r[key] for r in routes]
        return result

    def packed(key, cls, defaults, dtypes):
        count = max((len(r[key]) for r in routes), default=0)
        values = [
            np.full((count, capacity), value, dtype=dtype)
            for value, dtype in zip(defaults, dtypes, strict=True)
        ]
        for j, row in enumerate(routes):
            for i, term in enumerate(row[key]):
                for array, value in zip(values, term, strict=True):
                    array[i, j] = value
        return cls(*values)

    matrix = np.zeros((len(ids), capacity))
    for j, row in enumerate(routes):
        if row["kind"] == GROWTH:
            matrix[row["species"], j] = 1.0
        for sign, key in ((-1, "r"), (1, "p")):
            for s, nu, _ in row[key]:
                matrix[s, j] += sign * nu
    topology = validate_topology(
        Topology(
            np.asarray(species_valence),
            zones,
            column("kind", 0, int),
            column("owner", 0, int),
            column("species", 0, int),
            matrix,
            packed("r", Terms, (0, 0.0, 1.0), (int, float, float)),
            packed("p", Terms, (0, 0.0, 1.0), (int, float, float)),
            *(
                packed(
                    key,
                    Influencers,
                    (0, 0, 0, False, 1.0, 1.0),
                    (int, int, int, bool, float, float),
                )
                for key in ("inf", "decayinf")
            ),
        )
    )
    parameters = validate_parameters(
        Parameters(
            *(
                column(key, default, dtype)
                for key, default, dtype in (
                    ("maximum", 0.0, float),
                    ("standard", 0.0, float),
                    ("reversible", False, bool),
                    ("enabled", False, bool),
                    ("basal", 0.0, float),
                    ("regulated", 0.0, float),
                    ("scale", 1.0, float),
                    ("time", 1.0, float),
                    ("mod", 1.0, float),
                    ("target", False, bool),
                )
            ),
            temperature_K,
            gas_constant_J_mol_K,
        ),
        topology,
    )
    return topology, parameters
