"""Pinned BETSE local network control factors and ordered target writes, @1.

Sample state is [..., species, membrane+environment]; rule factors [...,rule,site].
Controls retain signed source factors. Channel core dynamics/fluxes and physical
energy/material ownership remain caller-owned. Frozen reaction activation/direct
semantics are reused; channel voltage and inhibitor-expression precedence are
handled explicitly here without changing that frozen component.
"""

from typing import NamedTuple

import jax
import jax.numpy as jnp
import numpy as np

from cells.processes import betse_network_reactions as regulation

LAW_ID = "betse_network_modulation_source_v1_5_0@1"
GJ, NAK, TJ, CHANNEL = range(1, 5)


class Topology(NamedTuple):
    species_valence: object
    membrane_to_environment: object
    environment_active: object
    ion_active: object
    rule_kind: object
    target_ion: object  # -1 means all TJ ion rows; zero for other targets/padding.
    init_active: object
    tj_targets: object
    channel_targets: object  # Carried to composing channel core; not a factor mask.
    influencers: regulation.Influencers
    voltage_coefficient: object  # Signed z, zero except active channel * Hill terms.
    inhibitor_maximum: object  # Source adds floors with its actual operator precedence.


class Parameters(NamedTuple):
    max_effect: object
    max_diffusivity_m2_s: object
    faraday_C_mol: object
    gas_constant_J_mol_K: object
    temperature_K: object  # p.T in source voltage-sensitive regulation, not sim.T.


class Controls(NamedTuple):
    gj: object
    nak: object
    tj: object
    channel_modulator: object  # [...,rule,membrane]; nonchannel rules are zero.


class Factors(NamedTuple):
    value: object
    regulation: object


def _real(value):
    return value.dtype.kind in "fiu"


def _shape(topology, *, xp):
    arrays = [xp.asarray(v) for v in topology[:9]]
    z, mapping, env, ions, kind, ion, init, targets, ct = arrays
    if (
        z.ndim != 1
        or not z.size
        or not _real(z)
        or mapping.ndim != 1
        or not mapping.size
        or mapping.dtype.kind not in "iu"
        or env.ndim != 1
        or not env.size
        or env.dtype.kind != "b"
        or ions.ndim != 1
        or not ions.size
        or ions.dtype.kind != "b"
        or kind.ndim != 1
        or kind.dtype.kind not in "iu"
        or ion.shape != kind.shape
        or ion.dtype.kind not in "iu"
        or init.shape != kind.shape
        or init.dtype.kind != "b"
        or targets.shape != env.shape
        or targets.dtype.kind != "b"
        or ct.shape != (kind.size, mapping.size)
        or ct.dtype.kind != "b"
    ):
        raise ValueError("Invalid explicit species/membrane/environment/ion/rule axes")
    sites, count = max(mapping.size, env.size), kind.size
    inf = regulation.Influencers(*(xp.asarray(v) for v in topology.influencers))
    s, owner, mode, constant, km, n = inf
    coef, floor = xp.asarray(topology.voltage_coefficient), xp.asarray(topology.inhibitor_maximum)
    if (
        s.ndim != 2
        or s.shape[-1] != count * sites
        or s.dtype.kind not in "iu"
        or owner.shape != s.shape
        or owner.dtype.kind not in "iu"
        or mode.shape != s.shape
        or mode.dtype.kind not in "iu"
        or constant.shape != s.shape
        or constant.dtype.kind != "b"
        or km.shape != s.shape
        or n.shape != s.shape
        or coef.shape != s.shape
        or floor.shape != s.shape
        or not all(_real(v) for v in (km, n, coef, floor))
    ):
        raise ValueError("Influencers require matching [term, flattened rule/site] arrays")
    return Topology(*arrays, inf, coef, floor)


def _domain_topology(topology, *, xp):
    t = _shape(topology, xp=xp)
    m, e, k = t.membrane_to_environment.size, t.environment_active.size, t.rule_kind.size
    sites = max(m, e)
    kind, site = xp.repeat(t.rule_kind, sites), xp.tile(xp.arange(sites), k)
    valid = (
        xp.all(xp.isfinite(t.species_valence)) & xp.all(t.environment_active) & xp.any(t.ion_active)
    )
    valid &= xp.all((t.membrane_to_environment >= 0) & (t.membrane_to_environment < e))
    valid &= xp.all((t.rule_kind >= 0) & (t.rule_kind <= CHANNEL))
    valid &= xp.all(
        xp.where(
            t.rule_kind == TJ,
            (t.target_ion >= -1) & (t.target_ion < t.ion_active.size),
            t.target_ion == 0,
        )
    )
    safe_ion = xp.clip(t.target_ion, 0, t.ion_active.size - 1)
    valid &= xp.all(
        xp.where((t.rule_kind == TJ) & (t.target_ion >= 0), t.ion_active[safe_ion], True)
    )
    valid &= xp.all(
        xp.where(t.rule_kind == CHANNEL, True, ~t.init_active & ~xp.any(t.channel_targets, axis=-1))
    )
    s, owner, mode, constant, km, n = t.influencers
    valid &= xp.all((s >= 0) & (s < t.species_valence.size) & (owner >= 0) & (owner < m + e))
    valid &= xp.all((mode >= 0) & (mode <= regulation.DIRECT_INHIBIT))
    valid &= xp.all(xp.isfinite(km) & (km > 0) & xp.isfinite(n) & (n > 0))
    valid &= xp.all(xp.isfinite(t.voltage_coefficient) & xp.isfinite(t.inhibitor_maximum))
    enabled = mode > 0
    active_site = (kind > 0) & (site < xp.where(kind == TJ, e, m))
    valid &= xp.all(
        xp.where(
            enabled,
            active_site,
            (s == 0)
            & (owner == 0)
            & ~constant
            & (km == 1)
            & (n == 1)
            & (t.voltage_coefficient == 0)
            & (t.inhibitor_maximum == 0),
        )
    )
    map_safe = xp.clip(t.membrane_to_environment, 0, e - 1)
    env_owner = m + map_safe[xp.clip(site, 0, m - 1)]
    allowed = xp.where(kind == TJ, (owner == m + site), (owner == site) | (owner == env_owner))
    valid &= xp.all(xp.where(enabled & ~constant, allowed, True))
    valid &= xp.all(xp.where(constant, (kind == TJ) & enabled, True))
    is_hill = (
        (mode == regulation.ACTIVATE)
        | (mode == regulation.INDEPENDENT)
        | (mode == regulation.INHIBIT)
    )
    valid &= xp.all(xp.where(t.voltage_coefficient != 0, (kind == CHANNEL) & is_hill, True))
    valid &= xp.all(
        xp.where(t.inhibitor_maximum != 0, (kind == CHANNEL) & (mode == regulation.INHIBIT), True)
    )
    seen_direct = xp.cumsum((mode == regulation.DIRECT_INHIBIT).astype(int), axis=0)
    valid &= xp.all(
        xp.where(
            mode >= regulation.INHIBIT, seen_direct <= (mode == regulation.DIRECT_INHIBIT), True
        )
    )
    ha = xp.any((mode >= regulation.ACTIVATE) & (mode <= regulation.DIRECT_ACTIVATE), axis=0)
    hi = xp.any(mode >= regulation.INHIBIT, axis=0)
    ordinary = xp.any(
        (mode == regulation.ACTIVATE)
        | (mode == regulation.INDEPENDENT)
        | (mode == regulation.INHIBIT),
        axis=0,
    )
    valid &= xp.all(~(ha & hi & ~ordinary))
    return valid, t._replace(
        influencers=t.influencers._replace(
            species=xp.clip(s, 0, t.species_valence.size - 1), owner=xp.clip(owner, 0, m + e - 1)
        )
    )


def validate_topology(topology):
    valid, t = _domain_topology(topology, xp=np)
    if not valid:
        raise ValueError("Invalid native modulation topology, regulator expression or padding")
    return t


def _parameters(parameters, t, *, xp):
    values = [xp.asarray(v) for v in parameters]
    if not all(_real(v) for v in values):
        raise ValueError("Require real modulation parameters")
    for i in (2, 3, 4):
        if not values[i].ndim:
            values[i] = values[i].reshape((1,))
        if values[i].shape[-1] != 1:
            raise ValueError("F/R/temperature require singleton world axes")
    shape = np.broadcast_shapes((t.rule_kind.size,), *(v.shape for v in values))
    if shape[-1] != t.rule_kind.size:
        raise ValueError("Parameter rule axis mismatch")
    return Parameters(*(xp.broadcast_to(v, shape) if i < 2 else v for i, v in enumerate(values)))


def _parameter_domain(p, t, *, xp):
    valid = xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in p]))
    valid &= xp.all((p.faraday_C_mol > 0) & (p.gas_constant_J_mol_K > 0) & (p.temperature_K > 0))
    valid &= xp.all(xp.isfinite(p.gas_constant_J_mol_K * p.temperature_K))
    valid &= xp.all(p.max_diffusivity_m2_s >= 0)
    valid &= xp.all(
        xp.where(t.rule_kind == CHANNEL, p.max_effect == 1, p.max_diffusivity_m2_s == 0)
    )
    valid &= xp.all(xp.where(t.rule_kind == 0, p.max_effect == 0, True))
    return valid


def evaluate(sample_mM, voltage_V, topology, parameters, *, xp=jnp):
    """Pure source factors. Membrane samples are native mem_concs, not cell averages."""
    t, c, vm = topology, xp.asarray(sample_mM), xp.asarray(voltage_V)
    m, e, k = t.membrane_to_environment.size, t.environment_active.size, t.rule_kind.size
    sites = max(m, e)
    if (
        c.ndim < 2
        or c.shape[-2:] != (t.species_valence.size, m + e)
        or not _real(c)
        or vm.ndim < 1
        or vm.shape[-1] != m
        or not _real(vm)
    ):
        raise ValueError("Require [...,species,membrane+environment] samples and membrane voltage")
    p = _parameters(parameters, t, xp=xp)
    inf = t.influencers
    site = xp.tile(xp.arange(sites), k)
    vm_route = vm[..., xp.clip(site, 0, m - 1)]
    voltage_term = (p.faraday_C_mol / (p.gas_constant_J_mol_K * p.temperature_K)) * vm_route
    log_km = xp.log(inf.km_mM) + t.voltage_coefficient * voltage_term[..., None, :]
    km = xp.exp(log_km)
    # Reuse all frozen activator/direct rules; evaluate the native inhibitor
    # polynomial separately because nonzero maxima introduce unparenthesized +.
    no_inhibitor = inf._replace(
        mode=xp.where(inf.mode == regulation.INHIBIT, 0, inf.mode), km_mM=km
    )
    activation_direct = regulation._regulation(c, no_inhibitor, xp=xp)
    value = xp.where(inf.mode > 0, c[..., inf.species, inf.owner], 1.0)
    log_load = inf.exponent * (xp.log(value) - log_km)
    hill = xp.where(inf.constant, 1.0, xp.exp(-xp.logaddexp(0.0, log_load)))
    leading = np.broadcast_shapes(activation_direct.shape, hill.shape[:-2] + (hill.shape[-1],))
    total, running = xp.zeros(leading), xp.ones(leading)
    for i in range(inf.mode.shape[0]):
        inhibitory = inf.mode[i] == regulation.INHIBIT
        floor = t.inhibitor_maximum[i]
        running = xp.where(inhibitory, running * (1.0 - floor) * hill[..., i, :], running)
        split = inhibitory & (floor != 0)
        total = total + xp.where(split, running, 0.0)
        running = xp.where(split, floor, running)
    alpha = activation_direct * (total + running)
    kind = xp.repeat(t.rule_kind, sites)
    active = (kind > 0) & (site < xp.where(kind == TJ, e, m))
    alpha = xp.where(active, alpha, 0.0)
    shape = alpha.shape[:-1] + (k, sites)
    alpha = alpha.reshape(shape)
    return Factors(alpha * p.max_effect[..., :, None], alpha)


def apply(factors, controls, topology, *, initialization=False, xp=jnp):
    """Ordered overwrite, including TJ ion/site selections and INIT channel skip.

    Channel factors are assigned before the composing channel core runs. Core
    target masks are carried in topology but do not mask alpha itself upstream.
    """
    t, value = topology, xp.asarray(factors)
    m, e, k = t.membrane_to_environment.size, t.environment_active.size, t.rule_kind.size
    gj, nak, tj, channels = (xp.asarray(v) for v in controls)
    init = xp.asarray(initialization)
    if (
        value.ndim < 2
        or value.shape[-2:] != (k, max(m, e))
        or gj.shape[-1:] != (m,)
        or nak.shape[-1:] != (m,)
        or tj.shape[-2:] != (t.ion_active.size, e)
        or channels.shape[-2:] != (k, m)
        or init.dtype.kind != "b"
        or not all(_real(v) for v in (value, gj, nak, tj, channels))
    ):
        raise ValueError("Control/factor axes or explicit initialization flag mismatch")
    shape = np.broadcast_shapes(
        value.shape[:-2],
        gj.shape[:-1],
        nak.shape[:-1],
        tj.shape[:-2],
        channels.shape[:-2],
        init.shape,
    )
    state = Controls(
        xp.broadcast_to(gj, shape + (m,)),
        xp.broadcast_to(nak, shape + (m,)),
        xp.broadcast_to(tj, shape + tj.shape[-2:]),
        xp.broadcast_to(channels, shape + (k, m)),
    )
    value, init = xp.broadcast_to(value, shape + value.shape[-2:]), xp.broadcast_to(init, shape)

    def update(i, state):
        kind, ion = t.rule_kind[i], t.target_ion[i]
        gj = xp.where(kind == GJ, value[..., i, :m], state.gj)
        nak = xp.where(kind == NAK, value[..., i, :m], state.nak)
        selection = (
            (kind == TJ)
            & t.tj_targets[None, :]
            & t.ion_active[:, None]
            & ((ion < 0) | (xp.arange(t.ion_active.size)[:, None] == ion))
        )
        tj = xp.where(selection, value[..., i, None, :e], state.tj)
        run = (kind == CHANNEL) & (~init | t.init_active[i])
        updated = xp.where(run[..., None], value[..., i, :m], state.channel_modulator[..., i, :])
        if xp is np:
            channels = state.channel_modulator.copy()
            channels[..., i, :] = updated
        else:
            channels = state.channel_modulator.at[..., i, :].set(updated)
        return Controls(gj, nak, tj, channels)

    if xp is np:
        for i in range(k):
            state = update(i, state)
        return state
    return jax.lax.fori_loop(0, k, update, state) if k else state


def channel_run_mask(topology, *, initialization=False, xp=jnp):
    """Source channel dispatch predicate, one flag per world/rule."""
    init = xp.asarray(initialization)
    if init.dtype.kind != "b":
        raise ValueError("Require an explicit boolean initialization phase")
    return (topology.rule_kind == CHANNEL) & (~init[..., None] | topology.init_active)


def channel_diffusivity(
    core_opening, relative_permeability, controls, topology, parameters, *, xp=jnp
):
    """Source DChan after core.run: [..., ion, rule, membrane], in m2/s.

    Caller supplies core.P after its own update and respects INIT run masks.
    Some cores already include their modulator in P; do not remove either source
    occurrence. This function adds the explicit outer modulator exactly once.
    """
    t, opening, relative = topology, xp.asarray(core_opening), xp.asarray(relative_permeability)
    if opening.shape[-2:] != (t.rule_kind.size, t.membrane_to_environment.size) or relative.shape[
        -2:
    ] != (t.ion_active.size, t.rule_kind.size):
        raise ValueError("Opening and permeability require rule/membrane and ion/rule axes")
    p = _parameters(parameters, t, xp=xp)
    result = (
        opening[..., None, :, :]
        * relative[..., :, :, None]
        * p.max_diffusivity_m2_s[..., None, :, None]
        * controls.channel_modulator[..., None, :, :]
    )
    return xp.where(
        (t.rule_kind == CHANNEL)[None, :, None] & t.ion_active[:, None, None], result, 0.0
    )


def domain_valid(
    sample_mM, voltage_V, controls, topology, parameters, *, initialization=False, xp=jnp
):
    """One scalar trial predicate; vmap it for independent world rejection."""
    try:
        valid, t = _domain_topology(topology, xp=xp)
        p = _parameters(parameters, t, xp=xp)
        c, vm = xp.asarray(sample_mM), xp.asarray(voltage_V)
        values = evaluate(c, vm, t, p, xp=xp)
        current = Controls(*(xp.asarray(v) for v in controls))
        updated = apply(values.value, current, t, initialization=initialization, xp=xp)
    except (TypeError, ValueError, IndexError, AttributeError):
        return xp.asarray(False)
    valid &= _parameter_domain(p, t, xp=xp)
    valid &= xp.all(xp.isfinite(c) & (c >= 0)) & xp.all(xp.isfinite(vm))
    valid &= xp.all(xp.stack([xp.all(xp.isfinite(v)) for v in (*values, *current, *updated)]))
    valid &= xp.all(xp.where(t.ion_active[:, None], True, current.tj == 0))
    valid &= xp.all(
        xp.where((t.rule_kind == CHANNEL)[:, None], True, current.channel_modulator == 0)
    )
    return valid


def bind(
    modulators,
    channels,
    species_ids,
    species_valence,
    membrane_to_environment,
    environment_count,
    ion_ids,
    *,
    tj_targets,
    channel_targets=None,
    rule_capacity=None,
    faraday_C_mol=96485.0,
    gas_constant_J_mol_K=8.314,
    temperature_K=310.0,
):
    """Bind native control dictionaries; no native channel core is constructed.

    Channels accept full read_channels fields; named profiles/express require
    explicit core target masks. Regulator alpha remains unmasked. Channel class
    and type are dispatch declarations for the caller's already qualified core.
    """
    ids, ions, mods, chans = tuple(species_ids), tuple(ion_ids), list(modulators), list(channels)
    if (
        not ids
        or len(set(ids)) != len(ids)
        or any(not isinstance(s, str) or not s for s in ids)
        or np.asarray(species_valence).shape != (len(ids),)
    ):
        raise ValueError("Require explicit unique species identities/valences")
    if not ions or len(set(ions)) != len(ions) or any(s not in ids for s in ions):
        raise ValueError("Require unique native ion identities")
    mapping = np.asarray(membrane_to_environment)
    if (
        mapping.ndim != 1
        or not mapping.size
        or mapping.dtype.kind not in "iu"
        or type(environment_count) is not int
        or environment_count < 1
        or np.any((mapping < 0) | (mapping >= environment_count))
    ):
        raise ValueError("Require nonempty explicit membrane-to-environment owners")
    m, e = mapping.size, environment_count
    target_mask = np.asarray(tj_targets)
    if target_mask.shape != (e,) or target_mask.dtype.kind != "b":
        raise ValueError("TJ targets require a boolean environment mask")
    names = []
    for group in (mods, chans):
        group_names = [r.get("name") for r in group]
        if len(set(group_names)) != len(group_names) or any(
            not isinstance(s, str) or not s for s in group_names
        ):
            raise ValueError("Require unique nonempty names within each source dictionary")
        names.extend(group_names)
    n = len(mods) + len(chans)
    capacity = n if rule_capacity is None else rule_capacity
    if type(capacity) is not int or capacity < n:
        raise ValueError("Rule capacity must hold all native definitions")
    targets = channel_targets or {}
    if set(targets) - {r["name"] for r in chans}:
        raise ValueError("Unknown channel profile target name")
    sites = max(m, e)
    kinds, ion_values, initials, maxima, diffusivities = [], [], [], [], []
    parsed, coefficients, floors, masks = [], [], [], []
    mod_fields = {
        "name",
        "target",
        "target ion",
        "max effect",
        "activators",
        "activator Km",
        "activator n",
        "activator zone",
        "inhibitors",
        "inhibitor Km",
        "inhibitor n",
        "inhibitor zone",
    }
    chan_fields = {
        "name",
        "channel class",
        "channel type",
        "max conductivity",
        "max Dm",
        "apply to",
        "init active",
        "channel activators",
        "activator Km",
        "activator n",
        "activator zone",
        "activator max",
        "channel inhibitors",
        "inhibitor Km",
        "inhibitor n",
        "inhibitor zone",
        "inhibitor max",
    }
    for row_index, row in enumerate([*mods, *chans]):
        channel = row_index >= len(mods)
        if set(row) - (chan_fields if channel else mod_fields):
            raise ValueError("Unsupported native control configuration key")
        if channel:
            if (
                not {"channel class", "channel type", "apply to"} <= row.keys()
                or row["channel class"] not in ("Na", "K", "Cl", "Ca", "Fun", "Cat", "ML")
                or not isinstance(row["channel type"], str)
                or not row["channel type"]
            ):
                raise ValueError("Unsupported native channel dispatch declaration")
            kind, ion = CHANNEL, 0
            maximum = row.get("max conductivity")
            maximum = row.get("max Dm") if maximum is None else maximum
            if not regulation._number(maximum, nonnegative=True):
                raise ValueError("Require nonnegative native maximum DChan coefficient")
            init = row.get("init active", True)
            if not isinstance(init, bool):
                raise ValueError("Require boolean channel init active")
            profile = row["apply to"]
            if profile is not None and profile != "all" and row["name"] not in targets:
                raise ValueError("Named/express channel profiles require explicit core targets")
            mask = np.asarray(targets.get(row["name"], np.ones(m, bool)))
            if mask.shape != (m,) or mask.dtype.kind != "b":
                raise ValueError("Channel core targets require a boolean membrane mask")
            if profile == "express" and not np.all(mask):
                raise ValueError("Native express channel initialization selects every membrane")
            max_effect, max_dm = 1.0, float(maximum)
        else:
            if (
                not {"target", "max effect"} <= row.keys()
                or row["target"] not in ("GJ", "Na/K-ATPase", "TJ")
                or not regulation._number(row["max effect"])
            ):
                raise ValueError("Unsupported native target or signed maximum effect")
            kind = {"GJ": GJ, "Na/K-ATPase": NAK, "TJ": TJ}[row["target"]]
            target_ion = row.get("target ion")
            if kind == TJ and target_ion not in (None, "None") and target_ion not in ions:
                raise ValueError("Unknown TJ target ion")
            ion = (
                (-1 if target_ion in (None, "None") else ions.index(target_ion))
                if kind == TJ
                else 0
            )
            init, mask, max_effect, max_dm = False, np.zeros(m, bool), float(row["max effect"]), 0.0
        # Reuse the frozen parser/location/suffix checks in a zero-rate shell.
        shell = {
            "name": "regulator",
            "reaction zone": "env" if kind == TJ else "cell",
            "reactants": [ids[0]],
            "reactant multipliers": [1.0],
            "Km reactants": [1.0],
            "products": [ids[0]],
            "product multipliers": [1.0],
            "Km products": [1.0],
            "max rate": 0.0,
            "standard free energy": "None",
        }
        extras = {}
        for activating in (True, False):
            prefix = "activator" if activating else "inhibitor"
            label = ("channel " if channel else "") + prefix + "s"
            raw_names = row.get(label)
            shell["reaction " + prefix + "s"] = raw_names
            for suffix in ("Km", "n", "zone"):
                shell[prefix + " " + suffix] = row.get(prefix + " " + suffix)
            if raw_names is None or raw_names == "None" or raw_names == []:
                if channel and row.get(prefix + " max") not in (None, []):
                    raise ValueError("Native regulator maxima require matching influencer names")
                continue
            maxima_list = row.get(prefix + " max") if channel else None
            if maxima_list is None:
                maxima_list = [0.0] * len(raw_names)
            if (
                not isinstance(maxima_list, list)
                or len(maxima_list) != len(raw_names)
                or any(v is not None and not regulation._number(v) for v in maxima_list)
            ):
                raise ValueError("Native channel regulator maxima must match names")
            tags = row.get(prefix + " zone")
            tags = (
                ["cell"] * len(raw_names) if tags is None or tags == "None" or tags == [] else tags
            )
            for index, (name, tag, floor) in enumerate(
                zip(raw_names, tags, maxima_list, strict=True)
            ):
                special_name = name[:-1] if isinstance(name, str) and name.endswith("*") else name
                base_name = (
                    special_name[:-1]
                    if isinstance(special_name, str) and special_name.endswith(("!", "&"))
                    else special_name
                )
                star = (
                    isinstance(name, str) and name.endswith("*") and not special_name.endswith("&")
                )
                z = float(species_valence[ids.index(base_name)]) if base_name in ids else 0.0
                extras[(activating, index)] = (
                    (z if tag == "env" else -z) if channel and star else 0.0,
                    float(floor)
                    if channel
                    and not activating
                    and floor is not None
                    and not special_name.endswith("&")
                    else 0.0,
                )
        rt, _ = regulation.bind(
            [shell],
            [],
            ids,
            species_valence,
            ["cell"] * m + ["env"] * e,
            cell_to_environment={i: m + int(mapping[i]) for i in range(m)},
        )
        inf = rt.influencers
        coef, floor = np.zeros(inf.mode.shape), np.zeros(inf.mode.shape)
        ai, ii = 0, 0
        for term in range(inf.mode.shape[0]):
            activating = inf.mode[term, 0] < regulation.INHIBIT
            idx = ai if activating else ii
            a, b = extras[(bool(activating), idx)]
            coef[term, :], floor[term, :] = a, b
            if activating:
                ai += 1
            else:
                ii += 1
        kinds.append(kind)
        ion_values.append(ion)
        initials.append(init)
        maxima.append(max_effect)
        diffusivities.append(max_dm)
        masks.append(mask)
        parsed.append(inf)
        coefficients.append(coef)
        floors.append(floor)
    terms = max((inf.mode.shape[0] for inf in parsed), default=0)
    arrays = [
        np.full((terms, capacity * sites), default, dtype=dtype)
        for default, dtype in (
            (0, int),
            (0, int),
            (0, int),
            (False, bool),
            (1.0, float),
            (1.0, float),
        )
    ]
    coefficient, floor_values = (
        np.zeros((terms, capacity * sites)),
        np.zeros((terms, capacity * sites)),
    )
    for i, inf in enumerate(parsed):
        owners = range(e) if kinds[i] == TJ else range(m)
        for j in owners:
            for dest, source in zip(arrays, inf, strict=True):
                dest[: inf.mode.shape[0], i * sites + j] = source[:, j]
            coefficient[: inf.mode.shape[0], i * sites + j] = coefficients[i][:, j]
            floor_values[: inf.mode.shape[0], i * sites + j] = floors[i][:, j]

    def padded(values, default, dtype):
        result = np.full(capacity, default, dtype=dtype)
        result[:n] = values
        return result

    ct = np.zeros((capacity, m), bool)
    ct[:n] = np.asarray(masks, bool).reshape(n, m)
    topology = validate_topology(
        Topology(
            np.asarray(species_valence),
            mapping,
            np.ones(e, bool),
            np.ones(len(ions), bool),
            padded(kinds, 0, int),
            padded(ion_values, 0, int),
            padded(initials, False, bool),
            target_mask,
            ct,
            regulation.Influencers(*arrays),
            coefficient,
            floor_values,
        )
    )
    p = _parameters(
        Parameters(
            padded(maxima, 0.0, float),
            padded(diffusivities, 0.0, float),
            faraday_C_mol,
            gas_constant_J_mol_K,
            temperature_K,
        ),
        topology,
        xp=np,
    )
    if not _parameter_domain(p, topology, xp=np):
        raise ValueError("Invalid native modulation parameters")
    return topology, p
