"""Operator local_species_reactions@1: reactions on the shared species inventory (D152, version 1).

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md (accepted 14 November 2026; rulings in §9). One reaction
network per composition, a split part (Strang halves) around @3's step. Every reaction is local: it
acts within one node, a cell or a finite outside node, on @3's neutral species rows, which @3 owns.
The operator writes those rows in place and books its writes in its own accumulators, as D150's
operators do (§1.1): no second inventory, no @3 route accumulator, no membrane-process hook.

Declaration (§2.1): `standard_concentration_mM` (c0 > 0); `species`, each a neutral species of the
inner model with `moieties` (integer counts; null: the species is its own moiety), `standard_mu_RT`
(mu°/RT at c0) and D150's identity (`catalogue`, `evidence`; species_common.parse_species, which
also refuses charged species and species with a membrane, junction or channel route); `reactions`,
each with `sites` ({"cells": [...] or "all", "outside": [...] or "all"}: cells and finite outside
nodes), integer `reactants` and `products`, a `law` with its parameters, and `factors`. Every
species a reaction names (reactant, product, catalyst, factor) is listed. A route is one reaction
at one site.

Laws (§2.2), with c = n/V at the declared volume V and m the scheduled multiplier:
* `mass_action` (driven): J = m F k V prod c^alpha, `rate_constant` k >= 0 in mM^(1-q)/s, order
  q = sum alpha <= 3;
* `michaelis_menten` (driven): J = m F V k_cat c_E c_S / (K_M + c_S) with `catalyst` E (read, never
  written) and `catalytic_rate_per_s` k_cat >= 0, or m F V V_max c_S / (K_M + c_S) with `catalyst`
  null and `max_rate_mM_per_s` V_max >= 0 (the other case's key is refused, with the reason);
  `saturation_mM` K_M > 0; reactants exactly {S: 1}, so no other species is consumed without
  appearing in the rate;
* `ideal_detailed_balance_mass_action@1` (passive): J = m V c0 k_f [prod a^alpha -
  exp(sum nu mu°/RT) prod a^beta], a = c/c0, `forward_rate_per_s` k_f > 0; closed, no factors,
  each side of molecularity <= 3; through processes/mass_action.reversible_flux, unchanged;
* factors on driven laws (they multiply): `hill_activation` x^n/(K^n + x^n) and `hill_inhibition`
  K^n/(K^n + x^n), `half_saturation_mM` K > 0 and `hill_coefficient` n > 0, the species x read.
Mass action consumes only its reactants (nu < 0 implies alpha >= 1), Michaelis-Menten only S, and
each passive flux every species it consumes, so no rate fails to vanish with a species it consumes
(§2.2): the parser makes that refusal unreachable. Parameters are per reaction, shared by its sites,
and bound per world as layout arrays, never closed-over constants (§2.3); the static structure
(species, stoichiometry, laws, factor kinds and species, sites) is the batch signature.

Material (§3.1): integer coefficients; a reaction that conserves every declared moiety is closed,
checked in integers; any other must be a pure source (every nu >= 0) or a pure sink (every nu <= 0),
or it is refused, as is one that changes no species. Neutral species only, so every charge term the
operator touches is an exact zero (§3.2).

Energy (§3.3). Per node, G = RT sum n (ln(n/V) - 1) + sum mu°' n with mu°' = RT (mu°/RT - ln c0):
@3's chemical term on the touched rows plus the standard-potential term, which @3's term lacks and
the operator owns as a declared free-energy term, not a flow (`reaction_standard_energy_pJ`). Heat
(HEAT_FIELDS) is booked for spontaneous steps and work (WORK_FIELDS) for driven ones, so the energy
ledger gains standard term + heat - work. ENERGY_GUARD_STATEMENT holds for these bookings.

Schedule `reaction_controls` (§2.1): per reaction (site null) and optionally per site, a
piecewise-constant multiplier m >= 0 from time 0, changing at exact multiples of dt inside the
horizon; on a passive reaction it scales both directions. A route takes its site's schedule, else
its reaction's.

Refusals at the definition (§2.5): the cases above; a held-bath site; more than 7 species per world
(D150's cap); an identity that differs from a D150 operator's; a turnover route on a (species, node)
a reaction writes (one local-kinetics writer per row, §1.1); a cell route on a slot that
scheduled_cell_replacement@1 replaces (§2.1); RK4 (§4.6); and every provider or closer of the
declared volumes, masks and outside anchors (CONFLICTS_VIEW: water, the lumens, replacement@2 by its
water, insertion@1 and @2, the partition and the bridge). The stationary analysis refuses the
composite by its own ID check (§4.6).

Milestone 1 (the contract fit, §10.4): the declaration, the refusals, the binding, the contract
parts (ENTITY_WRITES, the energy roles, the ledger and magnitude terms) and idleness. The half-step
selects its start state when every multiplier is zero and refuses any step with a positive
multiplier: the laws, the SSPRK(3,3) half-step under its stage condition and the bookings land at
milestone 2.

Idle (§4.5): no route, statically idle; every multiplier zero in a step, the start state is selected
(never offset by a computed zero), so every field is bitwise the composition's without the operator.
"""

import math
from dataclasses import dataclass

import jax.numpy as jnp
import numpy as np

from cells.core import pump_composite_spec as composite_spec
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields
from cells.models.operators import species_common as common
from cells.models.operators.contract import Operator

LAW_ID = "local_species_reactions@1"
STEP_ID = "idle_selection_active_steps_refused@1"  # Milestone 1; the half-step is milestone 2's.
CONTROLS_KEY = "reaction_controls"
TURNOVER_LAW = "scheduled_species_turnover@1"
PASSIVE_LAW = "ideal_detailed_balance_mass_action@1"
MASS_ACTION, MICHAELIS_MENTEN = "mass_action", "michaelis_menten"
LAWS = (PASSIVE_LAW, MASS_ACTION, MICHAELIS_MENTEN)
# Route law codes (layout) and factor kinds (layout; 0 pads a reaction's unused factor slots).
PASSIVE, DRIVEN_MASS_ACTION, DRIVEN_MICHAELIS_MENTEN = range(3)
CODES = {
    PASSIVE_LAW: PASSIVE,
    MASS_ACTION: DRIVEN_MASS_ACTION,
    MICHAELIS_MENTEN: DRIVEN_MICHAELIS_MENTEN,
}
FACTOR_LAWS = {"hill_activation": 1, "hill_inhibition": 2}
LAW_KEYS = {PASSIVE_LAW: {"forward_rate_per_s"}, MASS_ACTION: {"rate_constant"}}
# Michaelis-Menten's rate key by case (the lead's ruling Q8): k_cat with a catalyst, V_max without.
CATALYTIC_RATE, MAX_RATE = "catalytic_rate_per_s", "max_rate_mM_per_s"
REACTION_KEYS = {"id", "sites", "reactants", "products", "law", "factors"}
MAX_MOLECULARITY = 3
# D150's statement (secreted-species design §7, the lead's ruling 4), adapted to these bookings
# (this note §3.4); this operator's own bound/booking ratio is C2's (§10.4).
ENERGY_GUARD_STATEMENT = (
    "Under the IMEX solvers the shared energy bound is set by the ions' flows and is blind to "
    "species bookings at µM–nM (D150's probe 2: bound/change 1.7 to 1,721 in a mixed world); the "
    "face-free species-only world, where this operator is the only energy flow, and a NumPy ΔG "
    "test per law are the guards of record."
)

STATE_AXES = {
    "reaction_extent_fmol": ["reaction_route"],  # Signed; non-negative on driven routes.
    "reaction_produced_fmol": ["species", "cell_slot"],
    "reaction_consumed_fmol": ["species", "cell_slot"],
    "reaction_outside_produced_fmol": ["species", "extracellular_slot"],
    "reaction_outside_consumed_fmol": ["species", "extracellular_slot"],
    "reaction_dissipated_energy_pJ": ["cell_slot"],
    "reaction_outside_dissipated_energy_pJ": ["extracellular_slot"],
    "reaction_work_pJ": ["cell_slot"],
    "reaction_outside_work_pJ": ["extracellular_slot"],
    "reaction_standard_energy_pJ": ["cell_slot"],  # The owned standard-potential term (§3.3).
    "reaction_outside_standard_energy_pJ": ["extracellular_slot"],
    "reaction_energy_magnitude_pJ": ["cell_slot"],
    "reaction_outside_energy_magnitude_pJ": ["extracellular_slot"],
}
CELL_FIELDS = (
    "reaction_produced_fmol",
    "reaction_consumed_fmol",
    "reaction_dissipated_energy_pJ",
    "reaction_work_pJ",
    "reaction_standard_energy_pJ",
    "reaction_energy_magnitude_pJ",
)
OUTSIDE_FIELDS = (
    "reaction_outside_produced_fmol",
    "reaction_outside_consumed_fmol",
    "reaction_outside_dissipated_energy_pJ",
    "reaction_outside_work_pJ",
    "reaction_outside_standard_energy_pJ",
    "reaction_outside_energy_magnitude_pJ",
)
NON_NEGATIVE_FIELDS = (
    "reaction_produced_fmol",
    "reaction_consumed_fmol",
    "reaction_outside_produced_fmol",
    "reaction_outside_consumed_fmol",
    "reaction_dissipated_energy_pJ",
    "reaction_outside_dissipated_energy_pJ",
    "reaction_energy_magnitude_pJ",
    "reaction_outside_energy_magnitude_pJ",
)
LAYOUT_FIELDS = (
    "reaction_rows",  # [species rows] int64: the network's species on @3's axis, declared order.
    "reaction_route_node",  # [route] int64: its cell, or its outside node.
    "reaction_route_outside",  # [route] bool: at an outside node (else a cell).
    "reaction_route_law",  # [route] int64: PASSIVE, DRIVEN_MASS_ACTION, DRIVEN_MICHAELIS_MENTEN.
    "reaction_reactants",  # [species rows, route]: alpha.
    "reaction_products",  # [species rows, route]: beta.
    "reaction_catalyst",  # [species rows, route]: 1 at a Michaelis-Menten route's catalyst.
    "reaction_route_substrate",  # [route] int64: a Michaelis-Menten route's substrate (row).
    "reaction_rate_constant",  # [route]: k, k_cat or V_max (driven), k_f (passive).
    "reaction_saturation_mM",  # [route]: K_M (1 on other laws).
    "reaction_factor_kind",  # [route, factor] int64: 0 none, 1 activation, 2 inhibition.
    "reaction_factor_species",  # [route, factor] int64: the factor's species (row).
    "reaction_factor_half_saturation_mM",  # [route, factor]: K (1 where none).
    "reaction_factor_coefficient",  # [route, factor]: n (1 where none).
    "reaction_standard_mu_RT",  # [species rows]: mu°/RT at c0.
    "reaction_standard_concentration_mM",  # []: c0.
)


@dataclass(frozen=True)
class ReactingSpecies:
    identity: common.SpeciesIdentity
    moieties: tuple | None  # ((moiety, count), ...) as declared; None: its own moiety.
    standard_mu_RT: float


@dataclass(frozen=True)
class Factor:
    law: str
    species: str
    half_saturation_mM: float
    hill_coefficient: float


@dataclass(frozen=True)
class Reaction:
    id: str
    sites: tuple  # (("cells" | "outside", "all" or (node id, ...)), ...) as declared.
    reactants: tuple  # ((species, count), ...) as declared.
    products: tuple
    law: str
    rate_constant: float  # k, k_cat or V_max, or k_f (passive).
    saturation_mM: float | None  # Michaelis-Menten K_M.
    catalyst: str | None  # Michaelis-Menten catalyst.
    factors: tuple
    kind: str  # "closed", "source" or "sink" (§3.1).


@dataclass(frozen=True)
class Route:
    reaction: str
    kind: str  # "cell" or "outside".
    node: str


@dataclass(frozen=True)
class Reactions:
    law: str
    standard_concentration_mM: float
    species: tuple
    reactions: tuple
    routes: tuple  # Every (reaction, site), reaction by reaction in declared order.


@dataclass(frozen=True)
class ReactionControl:
    reaction_id: str
    site: str | None  # None: every site of the reaction without its own schedule.
    changes: tuple  # ((time, multiplier), ...).


# ------------------------------------------------------------------ the declaration


def _number(value, what, *, low=None, strict=False):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ConfigError(f"{LAW_ID}: {what} is a finite number")
    value = float(value)
    if low is not None and (value <= low if strict else value < low):
        raise ConfigError(f"{LAW_ID}: {what} must be {'>' if strict else '>='} {low}")
    return value


def _moieties(raw, name):
    if raw is None:
        return None
    if not isinstance(raw, dict) or not raw:
        raise ConfigError(
            f"{LAW_ID}: species {name} declares its moieties as integer counts (null: its own "
            "moiety)"
        )
    out = []
    for moiety, count in raw.items():
        if type(count) is not int or count < 1:
            raise ConfigError(f"{LAW_ID}: species {name}'s moiety counts are positive integers")
        out.append((identifier(moiety), count))
    return tuple(out)


def moiety_counts(species):
    """{moiety: count} of a ReactingSpecies (its own moiety when none is declared)."""
    if species.moieties is None:
        return {species.identity.id: 1}
    return dict(species.moieties)


def _species(raw, base):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID} declares the species its network names in a non-empty list")
    identities = []
    for entry in raw:
        _fields(
            entry, {"id", "moieties", "standard_mu_RT", "catalogue", "evidence"}, "reacting species"
        )
        identities.append({k: entry[k] for k in ("id", "catalogue", "evidence")})
    parsed = common.parse_species(identities, base, LAW_ID)  # Neutral, impermeant, identity.
    return tuple(
        ReactingSpecies(
            identity,
            _moieties(entry["moieties"], identity.id),
            _number(entry["standard_mu_RT"], f"species {identity.id}'s standard_mu_RT"),
        )
        for entry, identity in zip(raw, parsed, strict=True)
    )


def _side(raw, listed, name, which):
    if not isinstance(raw, dict):
        raise ConfigError(f"{LAW_ID}: reaction {name} declares its {which} as {{species: count}}")
    out = []
    for species, count in raw.items():
        if species not in listed:
            raise ConfigError(
                f"{LAW_ID}: reaction {name} names {species!r}, not a listed species of the network"
            )
        if type(count) is not int or count < 1:
            raise ConfigError(
                f"{LAW_ID}: reaction {name}'s coefficients are positive integers ({which} "
                f"{species}: {count!r})"
            )
        out.append((species, count))
    return tuple(out)


def _sites(raw, base, name):
    if not isinstance(raw, dict) or not raw or set(raw) - {"cells", "outside"}:
        raise ConfigError(
            f"{LAW_ID}: reaction {name} declares its sites as {{'cells': [...] or 'all', "
            "'outside': [...] or 'all'}"
        )
    m = base.model
    outside = {c.id: c for c in m.extracellular}
    known = dict(
        cells=[c.id for c in m.cells], outside=[c.id for c in m.extracellular if not c.reservoir]
    )
    declared, routes = [], []
    for kind in ("cells", "outside"):
        if kind not in raw:
            continue
        value = raw[kind]
        if value == "all":
            nodes = list(known[kind])
        elif type(value) is list and value:
            nodes = [identifier(v) for v in value]
            for node in nodes:
                if kind == "outside" and node in outside and outside[node].reservoir:
                    raise ConfigError(
                        f"{LAW_ID}: reaction {name} acts at a held bath ({node}), whose "
                        "composition is held: a reaction there would be a source or sink of the "
                        "bath, not of the inventory"
                    )
                if node not in known[kind]:
                    raise ConfigError(
                        f"{LAW_ID}: reaction {name} acts at {node!r}, not a declared "
                        + ("cell" if kind == "cells" else "outside node")
                    )
            if len(set(nodes)) != len(nodes):
                raise ConfigError(f"{LAW_ID}: reaction {name} lists a site twice")
        else:
            raise ConfigError(
                f"{LAW_ID}: reaction {name}'s {kind} sites are a non-empty list or 'all'"
            )
        declared.append((kind, "all" if value == "all" else tuple(nodes)))
        routes += [Route(name, "cell" if kind == "cells" else "outside", n) for n in nodes]
    if not routes:
        raise ConfigError(f"{LAW_ID}: reaction {name} acts at no site")
    return tuple(declared), routes


def _factors(raw, listed, name, law):
    if type(raw) is not list:
        raise ConfigError(f"{LAW_ID}: reaction {name}'s factors are an explicit list")
    if raw and law == PASSIVE_LAW:
        raise ConfigError(
            f"{LAW_ID}: passive reaction {name} takes no factors in version 1 (a species-dependent "
            "factor of a reversible reaction is a later door)"
        )
    out = []
    for entry in raw:
        _fields(entry, {"law", "species", "half_saturation_mM", "hill_coefficient"}, "factor")
        if entry["law"] not in FACTOR_LAWS:
            raise ConfigError(f"{LAW_ID}: a factor's law is one of " + ", ".join(FACTOR_LAWS))
        if entry["species"] not in listed:
            raise ConfigError(
                f"{LAW_ID}: a factor of reaction {name} reads {entry['species']!r}, not a listed "
                "species of the network"
            )
        out.append(
            Factor(
                entry["law"],
                entry["species"],
                _number(
                    entry["half_saturation_mM"], "a factor's half_saturation_mM", low=0, strict=True
                ),
                _number(
                    entry["hill_coefficient"], "a factor's hill_coefficient", low=0, strict=True
                ),
            )
        )
    return tuple(out)


def _kind(reactants, products, species, name):
    """closed, source or sink (§3.1), in integer arithmetic; refused otherwise."""
    nu = {s.identity.id: 0 for s in species}
    for s, count in reactants:
        nu[s] -= count
    for s, count in products:
        nu[s] += count
    if not any(nu.values()):
        raise ConfigError(f"{LAW_ID}: reaction {name} changes no species")
    moieties = {}
    for s in species:
        for moiety, count in moiety_counts(s).items():
            moieties[moiety] = moieties.get(moiety, 0) + count * nu[s.identity.id]
    if not any(moieties.values()):
        return "closed"
    if all(v >= 0 for v in nu.values()):
        return "source"
    if all(v <= 0 for v in nu.values()):
        return "sink"
    raise ConfigError(
        f"{LAW_ID}: reaction {name} is unbalanced in its declared moieties and is neither a pure "
        "source (every net coefficient >= 0) nor a pure sink (every net coefficient <= 0)"
    )


def _law_keys(raw, law):
    """The law's parameter keys; Michaelis-Menten's rate key follows its catalyst (ruling Q8)."""
    if law != MICHAELIS_MENTEN:
        return LAW_KEYS[law]
    if "catalyst" not in raw:
        raise ConfigError(
            f"{LAW_ID}: a michaelis_menten reaction declares its catalyst (a listed species, or "
            "null)"
        )
    catalysed = raw["catalyst"] is not None
    key, other = (CATALYTIC_RATE, MAX_RATE) if catalysed else (MAX_RATE, CATALYTIC_RATE)
    if other in raw:
        raise ConfigError(
            f"{LAW_ID}: michaelis_menten reaction {raw.get('id')!r} "
            + (
                "declares a catalyst, so its rate is catalytic_rate_per_s (k_cat, 1/s: J = V k_cat "
                "c_E c_S / (K_M + c_S)), not max_rate_mM_per_s"
                if catalysed
                else "declares no catalyst, so its rate is max_rate_mM_per_s (V_max, mM/s: J = V "
                "V_max c_S / (K_M + c_S)), not catalytic_rate_per_s"
            )
        )
    return {"catalyst", "saturation_mM", key}


def _reaction(raw, base, species):
    listed = {s.identity.id for s in species}
    if not isinstance(raw, dict) or raw.get("law") not in LAWS:
        raise ConfigError(f"{LAW_ID}: a reaction's law is one of " + ", ".join(LAWS))
    law = raw["law"]
    _fields(raw, REACTION_KEYS | _law_keys(raw, law), f"{law} reaction")
    name = identifier(raw["id"])
    sites, routes = _sites(raw["sites"], base, name)
    reactants = _side(raw["reactants"], listed, name, "reactants")
    products = _side(raw["products"], listed, name, "products")
    factors = _factors(raw["factors"], listed, name, law)
    kind = _kind(reactants, products, species, name)
    alpha, beta = sum(c for _, c in reactants), sum(c for _, c in products)
    catalyst, saturation = None, None
    if law == PASSIVE_LAW:
        if kind != "closed":
            raise ConfigError(
                f"{LAW_ID}: passive reaction {name} must be closed in its declared moieties (an "
                "open passive reaction needs a chemostat, a later door)"
            )
        if alpha > MAX_MOLECULARITY or beta > MAX_MOLECULARITY:
            raise ConfigError(
                f"{LAW_ID}: passive reaction {name} has molecularity above {MAX_MOLECULARITY} "
                "(each direction is an elementary step)"
            )
        rate = _number(
            raw["forward_rate_per_s"], f"{name}'s forward_rate_per_s", low=0, strict=True
        )
    elif law == MASS_ACTION:
        if alpha > MAX_MOLECULARITY:
            raise ConfigError(
                f"{LAW_ID}: reaction {name} has molecularity above {MAX_MOLECULARITY} (orders 0 to "
                "3; cooperativity enters through Hill factors)"
            )
        rate = _number(raw["rate_constant"], f"{name}'s rate_constant", low=0)
    else:
        if len(reactants) != 1 or reactants[0][1] != 1:
            raise ConfigError(
                f"{LAW_ID}: michaelis_menten reaction {name} consumes one substrate S (reactants "
                "exactly {S: 1}); another reactant would be consumed without appearing in its rate"
            )
        catalyst = raw["catalyst"]
        if catalyst is not None:
            if catalyst not in listed:
                raise ConfigError(
                    f"{LAW_ID}: reaction {name}'s catalyst {catalyst!r} is not a listed species"
                )
            if any(catalyst == s for s, _ in (*reactants, *products)):
                raise ConfigError(
                    f"{LAW_ID}: reaction {name}'s catalyst is read, never written (it is not a "
                    "reactant or a product)"
                )
        key = CATALYTIC_RATE if catalyst is not None else MAX_RATE
        rate = _number(raw[key], f"{name}'s {key}", low=0)
        saturation = _number(raw["saturation_mM"], f"{name}'s saturation_mM", low=0, strict=True)
    reaction = Reaction(
        name, sites, reactants, products, law, rate, saturation, catalyst, factors, kind
    )
    return reaction, routes


def parse_reactions(raw, base):
    _fields(raw, {"law", "standard_concentration_mM", "species", "reactions"}, "species reactions")
    if raw["law"] != LAW_ID:
        raise ConfigError("Species reactions require law " + LAW_ID)
    c0 = _number(raw["standard_concentration_mM"], "standard_concentration_mM", low=0, strict=True)
    species = _species(raw["species"], base)
    if type(raw["reactions"]) is not list:
        raise ConfigError(f"{LAW_ID} reactions require an explicit list")
    reactions, routes = [], []
    for entry in raw["reactions"]:
        reaction, own = _reaction(entry, base, species)
        reactions.append(reaction)
        routes += own
    if len({r.id for r in reactions}) != len(reactions):
        raise ConfigError(f"{LAW_ID}: reaction IDs are unique")
    return Reactions(LAW_ID, c0, species, tuple(reactions), tuple(routes))


def reactions_to_dict(declaration):
    if type(declaration) is not Reactions or any(
        type(r) is not Reaction for r in declaration.reactions
    ):
        raise ConfigError("Require explicit immutable species reaction declaration types")
    species = [
        dict(
            id=s.identity.id,
            moieties=None if s.moieties is None else dict(s.moieties),
            standard_mu_RT=s.standard_mu_RT,
            catalogue=None
            if s.identity.catalogue is None
            else dict(catalogue=s.identity.catalogue[0], entry=s.identity.catalogue[1]),
            evidence=s.identity.evidence,
        )
        for s in declaration.species
    ]
    reactions = []
    for r in declaration.reactions:
        entry = dict(
            id=r.id,
            sites={k: v if v == "all" else list(v) for k, v in r.sites},
            reactants=dict(r.reactants),
            products=dict(r.products),
            law=r.law,
            factors=[
                dict(
                    law=f.law,
                    species=f.species,
                    half_saturation_mM=f.half_saturation_mM,
                    hill_coefficient=f.hill_coefficient,
                )
                for f in r.factors
            ],
        )
        if r.law == PASSIVE_LAW:
            entry["forward_rate_per_s"] = r.rate_constant
        elif r.law == MASS_ACTION:
            entry["rate_constant"] = r.rate_constant
        else:
            key = CATALYTIC_RATE if r.catalyst is not None else MAX_RATE
            entry.update(
                {"catalyst": r.catalyst, key: r.rate_constant, "saturation_mM": r.saturation_mM}
            )
        reactions.append(entry)
    return dict(
        law=declaration.law,
        standard_concentration_mM=declaration.standard_concentration_mM,
        species=species,
        reactions=reactions,
    )


ORDER_UNITS = ("mM/s", "1/s", "1/(mM s)", "1/(mM^2 s)")  # Mass action's k by order q = 0 to 3.


def parameters(reaction):
    """{law, parameters, units, factors}: a reaction's parameters under their law-specific names and
    units (the lead's ruling Q8), as each of its routes uses them."""
    if reaction.law == MASS_ACTION:
        order = sum(c for _, c in reaction.reactants)
        values = {"rate_constant": reaction.rate_constant}
        units = {"rate_constant": ORDER_UNITS[order]}
    elif reaction.law == MICHAELIS_MENTEN:
        key = CATALYTIC_RATE if reaction.catalyst is not None else MAX_RATE
        values = {key: reaction.rate_constant, "saturation_mM": reaction.saturation_mM}
        units = {key: "1/s" if reaction.catalyst is not None else "mM/s", "saturation_mM": "mM"}
        if reaction.catalyst is not None:
            values["catalyst"] = reaction.catalyst
    else:
        values = {"forward_rate_per_s": reaction.rate_constant}
        units = {"forward_rate_per_s": "1/s"}
    factors = [
        dict(
            law=f.law,
            species=f.species,
            half_saturation_mM=f.half_saturation_mM,
            hill_coefficient=f.hill_coefficient,
        )
        for f in reaction.factors
    ]
    return dict(law=reaction.law, parameters=values, units=units, factors=factors)


# ------------------------------------------------------------------ the schedule


def _changes(raw, base, what):
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: {what} lists its changes")
    dt, end = base.execution.dt, base.experiment.end_time
    changes = []
    for change in raw:
        _fields(change, {"time", "multiplier"}, f"{CONTROLS_KEY} change")
        time = _number(change["time"], f"a change time of {what}")
        if time != round(time / dt) * dt:
            raise ConfigError(
                f"{LAW_ID}: a schedule change must be an exact multiple of dt (k * dt)"
            )
        if not 0.0 <= time <= end:
            raise ConfigError(f"{LAW_ID}: a schedule change lies outside the horizon")
        changes.append((time, _number(change["multiplier"], f"a multiplier of {what}", low=0)))
    times = [t for t, _ in changes]
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError(f"{LAW_ID}: schedule times increase strictly")
    if times[0] != 0.0:
        raise ConfigError(f"{LAW_ID}: {what} starts at time 0")
    return tuple(changes)


def parse_controls(raw, base, declaration):
    entries = raw[CONTROLS_KEY]
    if type(entries) is not list:
        raise ConfigError(f"{CONTROLS_KEY} requires an explicit list")
    sites = {r.id: [] for r in declaration.reactions}
    for route in declaration.routes:
        sites[route.reaction].append(route.node)
    controls, seen = [], set()
    for entry in entries:
        _fields(entry, {"reaction_id", "site", "schedule"}, f"{CONTROLS_KEY} entry")
        reaction, site = entry["reaction_id"], entry["site"]
        if reaction not in sites:
            raise ConfigError(f"{CONTROLS_KEY} names an undeclared reaction {reaction!r}")
        if site is not None and identifier(site) not in sites[reaction]:
            raise ConfigError(f"{LAW_ID}: {site!r} is not a site of reaction {reaction}")
        if (reaction, site) in seen:
            raise ConfigError(f"{LAW_ID}: one schedule per reaction and site ({reaction}, {site})")
        seen.add((reaction, site))
        what = f"the schedule of {reaction}" + ("" if site is None else f" at {site}")
        controls.append(ReactionControl(reaction, site, _changes(entry["schedule"], base, what)))
    for reaction, nodes in sites.items():
        own = [n for n in nodes if (reaction, n) in seen]
        if (reaction, None) not in seen and len(own) != len(nodes):
            missing = next(n for n in nodes if (reaction, n) not in seen)
            raise ConfigError(
                f"{LAW_ID}: reaction {reaction} needs a schedule at {missing} (its own or the "
                "reaction's, site null)"
            )
        if (reaction, None) in seen and len(own) == len(nodes):
            raise ConfigError(
                f"{LAW_ID}: the schedule of reaction {reaction} (site null) applies to no site: "
                "every site has its own"
            )
    return tuple(controls)


def route_tables(declaration, schedule):
    """Per route, its multiplier table ((time, multiplier), ...): its site's, else its
    reaction's."""
    keyed = {(c.reaction_id, c.site): c.changes for c in schedule}
    return [
        keyed.get((r.reaction, r.node), keyed.get((r.reaction, None))) for r in declaration.routes
    ]


# ------------------------------------------------------------------ binding


def bind(spec, declaration):
    m, x = spec.model, spec.execution
    names = [s.identity.id for s in declaration.species]
    row = {n: i for i, n in enumerate(names)}
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    by_id = {r.id: r for r in declaration.reactions}
    routes = declaration.routes
    k, count = len(names), len(routes)
    width = max((len(r.factors) for r in declaration.reactions), default=0)
    alpha, beta, catalyst = np.zeros((k, count)), np.zeros((k, count)), np.zeros((k, count))
    node, law = np.zeros(count, dtype=np.int64), np.zeros(count, dtype=np.int64)
    substrate = np.zeros(count, dtype=np.int64)
    rate, saturation = np.zeros(count), np.ones(count)
    factor_kind = np.zeros((count, width), dtype=np.int64)
    factor_species = np.zeros((count, width), dtype=np.int64)
    factor_k, factor_n = np.ones((count, width)), np.ones((count, width))
    for j, route in enumerate(routes):
        r = by_id[route.reaction]
        for s, c in r.reactants:
            alpha[row[s], j] = c
        for s, c in r.products:
            beta[row[s], j] = c
        node[j] = cells.index(route.node) if route.kind == "cell" else outside.index(route.node)
        law[j] = CODES[r.law]
        rate[j] = r.rate_constant
        if r.law == MICHAELIS_MENTEN:
            substrate[j] = row[r.reactants[0][0]]
            saturation[j] = r.saturation_mM
            if r.catalyst is not None:
                catalyst[row[r.catalyst], j] = 1.0
        for i, f in enumerate(r.factors):
            factor_kind[j, i] = FACTOR_LAWS[f.law]
            factor_species[j, i] = row[f.species]
            factor_k[j, i], factor_n[j, i] = f.half_saturation_mM, f.hill_coefficient
    layout = dict(
        reaction_rows=np.asarray([species.index(n) for n in names], dtype=np.int64),
        reaction_route_node=node,
        reaction_route_outside=np.asarray([r.kind == "outside" for r in routes], dtype=bool),
        reaction_route_law=law,
        reaction_reactants=alpha,
        reaction_products=beta,
        reaction_catalyst=catalyst,
        reaction_route_substrate=substrate,
        reaction_rate_constant=rate,
        reaction_saturation_mM=saturation,
        reaction_factor_kind=factor_kind,
        reaction_factor_species=factor_species,
        reaction_factor_half_saturation_mM=factor_k,
        reaction_factor_coefficient=factor_n,
        reaction_standard_mu_RT=np.asarray([s.standard_mu_RT for s in declaration.species]),
        reaction_standard_concentration_mM=np.asarray(declaration.standard_concentration_mM),
    )
    shapes = dict(
        species=len(species),
        cell_slot=x.capacity,
        extracellular_slot=x.extracellular_capacity,
        reaction_route=count,
    )
    state = {k: np.zeros([shapes[a] for a in axes]) for k, axes in STATE_AXES.items()}
    return state, layout


# ------------------------------------------------------------------ definition checks


def written(declaration):
    """{(species, node id): reaction id} of every row a reaction writes (net coefficient != 0)."""
    by_id = {r.id: r for r in declaration.reactions}
    out = {}
    for route in declaration.routes:
        r = by_id[route.reaction]
        nu = dict.fromkeys((s for s, _ in (*r.reactants, *r.products)), 0)
        for s, c in r.reactants:
            nu[s] -= c
        for s, c in r.products:
            nu[s] += c
        for s, v in nu.items():
            if v:
                out.setdefault((s, route.node), r.id)
    return out


def check_turnover_rows(spec, declaration):
    """Refuse a turnover route on a (species, node) the network writes (§1.1)."""
    rows = written(declaration)
    for op, other, _ in composite_spec.entries(spec):
        if op.LAW_ID != TURNOVER_LAW:
            continue
        for route in other.routes:
            reaction = rows.get((route.species, route.node))
            if reaction is not None:
                raise ConfigError(
                    f"{LAW_ID}: turnover route {route.id} acts on {route.species} at {route.node}, "
                    f"which reaction {reaction} writes: one local-kinetics writer per species and "
                    "node in version 1; declare the production and clearance of a reacting species "
                    "as source and sink reactions of the network"
                )


def check_replaced_slots(spec, declaration):
    """Refuse a cell route on a slot that replacement@1 replaces (§2.1, the lead's ruling 6)."""
    _, events = common.replacement_of(spec)
    slots = {v.slot for v in events}
    for route in declaration.routes:
        if route.kind == "cell" and route.node in slots:
            raise ConfigError(
                f"{LAW_ID}: reaction {route.reaction} acts in cell {route.node}, a slot "
                f"{common.REPLACEMENT_LAW} replaces: version 1 refuses cell routes on replaced "
                "slots (outside routes compose; the occupant rule for cell routes is version 1.1's)"
            )


# ------------------------------------------------------------------ device parts


def _species_mask(rows, size, *, xp):
    """[species] True on the network's rows."""
    if xp is jnp:
        return jnp.zeros(size, dtype=bool).at[rows].set(True)
    out = np.zeros(size, dtype=bool)
    out[np.asarray(rows)] = True
    return out


def _own_valid(state, p, *, xp):
    valid = xp.asarray(True)
    for name in NON_NEGATIVE_FIELDS:
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in (
        "reaction_extent_fmol",
        "reaction_work_pJ",
        "reaction_outside_work_pJ",
        "reaction_standard_energy_pJ",
        "reaction_outside_standard_energy_pJ",
    ):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    driven = p.reaction_route_law != PASSIVE
    return valid & xp.all(xp.where(driven, state.reaction_extent_fmol >= 0, True))


def reactions_domain_valid(state, p, *, xp):
    """Its own fields (finite, signed as booked, zero on padding and off the network's rows) and
    the network's rows (finite and positive at active cells and finite outside nodes)."""
    valid = _own_valid(state, p, xp=xp)
    rows = p.reaction_rows
    listed = _species_mask(rows, state.amount_increment.shape[0], xp=xp)
    finite = p.outside_active & ~p.reservoir
    for names, mask in ((CELL_FIELDS, p.active), (OUTSIDE_FIELDS, finite)):
        for name in names:
            value = getattr(state, name)
            where = mask if value.ndim == 1 else listed[:, None] & mask[None, :]
            valid &= xp.all(xp.where(where, True, value == 0))
    cells = p.amount_reference[rows] + state.amount_increment[rows]
    nodes = p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows]
    valid &= xp.all(xp.where(p.active[None, :], xp.isfinite(cells) & (cells > 0), True))
    valid &= xp.all(xp.where(finite[None, :], xp.isfinite(nodes) & (nodes > 0), True))
    return valid


def reactions_half_step(state, multiplier, h, p, *, xp=jnp):
    """(state after h of the network, validity).

    Milestone 1 (the contract fit): every multiplier zero selects the start state; any positive
    multiplier refuses the step, since the laws and the SSPRK(3,3) half-step land at milestone 2.
    """
    flowing = xp.any(multiplier > 0)
    return state, ~flowing


# ------------------------------------------------------------------ the operator


class LocalSpeciesReactions(Operator):
    LAW_ID = LAW_ID
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"  # Declared; RK4 is refused at the definition (§4.6).
    STATE_AXES = STATE_AXES
    HEAT_FIELDS = ("reaction_dissipated_energy_pJ", "reaction_outside_dissipated_energy_pJ")
    WORK_FIELDS = ("reaction_work_pJ", "reaction_outside_work_pJ")
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONTROL_FIELDS = ("reaction_multiplier",)
    EXPERIMENT_KEYS = (CONTROLS_KEY,)
    # Concentrations and dG read the declared volumes; a closer counts as a mask's provider (S5);
    # insertion@1 provides the outside mask and anchors (§1.4).
    CONFLICTS_VIEW = (
        "volume",
        "extracellular_volume",
        "active",
        "outside_active",
        "extracellular_amount_reference",
    )
    ENTITY_WRITES = {
        "amount_increment": ("reaction_produced_fmol", "reaction_consumed_fmol"),
        "extracellular_amount_increment": (
            "reaction_outside_produced_fmol",
            "reaction_outside_consumed_fmol",
        ),
    }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_reactions(raw, base)

    def to_dict(self, declaration, base):
        return reactions_to_dict(declaration)

    def parse_schedule(self, raw, base, declaration):
        return parse_controls(raw, base, declaration)

    def schedule_to_dict(self, schedule, base, declaration):
        return {
            CONTROLS_KEY: [
                dict(
                    reaction_id=c.reaction_id,
                    site=c.site,
                    schedule=[dict(time=t, multiplier=v) for t, v in c.changes],
                )
                for c in schedule
            ]
        }

    def schedule_times(self, schedule):
        return common.schedule_times(schedule)

    def value_at(self, schedule, time):
        return common.value_at(schedule, time)

    def control_values(self, spec, declaration, schedule, records, indices, times):
        tables = route_tables(declaration, schedule)
        return (common.control_arrays(tables, times, 1)[..., 0],)

    def check_definition(self, spec, declaration, schedule, model):
        if spec.execution.solver == "rk4":
            raise ConfigError(
                f"{LAW_ID} refuses RK4 in version 1 (§4.6): its bookings are exact and checked "
                "at rounding in the face-free world under IMEX, D150's RK4 worlds stay the "
                "transport's sharp reference, and no consumer needs it"
            )
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, tuple(s.identity for s in declaration.species))
        check_turnover_rows(spec, declaration)
        check_replaced_slots(spec, declaration)

    def batch_signature(self, declaration):
        """The static network: species, stoichiometry, laws, catalysts, factor kinds and species,
        and sites; identities, moieties and every parameter are not part of it."""
        return (
            LAW_ID,
            tuple(s.identity.id for s in declaration.species),
            tuple(
                (
                    r.law,
                    r.reactants,
                    r.products,
                    r.catalyst,
                    tuple((f.law, f.species) for f in r.factors),
                )
                for r in declaration.reactions
            ),
            tuple(
                (
                    [r.id for r in declaration.reactions].index(route.reaction),
                    route.kind,
                    route.node,
                )
                for route in declaration.routes
            ),
        )

    def working_size(self, spec):
        x, s = spec.execution, len(spec.model.species_ids)
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        k, count = len(declaration.species), len(declaration.routes)
        return 8 * ((4 * s + 8) * (x.capacity + x.extracellular_capacity) + count * (6 * k + 16))

    def summary(self, spec, declaration, schedule, history):
        identities = common.summary_identities(tuple(s.identity for s in declaration.species))
        by_id = {r.id: r for r in declaration.reactions}
        return {
            "reaction_law": LAW_ID,
            "reaction_standard_concentration_mM": declaration.standard_concentration_mM,
            "reaction_species": {
                s.identity.id: dict(
                    identities[s.identity.id],
                    moieties=moiety_counts(s),
                    standard_mu_RT=s.standard_mu_RT,
                )
                for s in declaration.species
            },
            "reaction_network": {
                r.id: dict(
                    law=r.law,
                    kind=r.kind,
                    reactants=dict(r.reactants),
                    products=dict(r.products),
                    sites=[route.node for route in declaration.routes if route.reaction == r.id],
                )
                for r in declaration.reactions
            },
            "reaction_routes": [
                dict(reaction=route.reaction, site=route.node, **parameters(by_id[route.reaction]))
                for route in declaration.routes
            ],
            "reaction_step": "milestone 1: idle selection; an active step is refused",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.reaction_route_node.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp):
        return reactions_half_step(state, control.reaction_multiplier, h, p, xp=xp)

    def control_valid(self, control, p, *, xp):
        m = control.reaction_multiplier
        return xp.all(xp.isfinite(m) & (m >= 0))

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & reactions_domain_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = reactions_domain_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        """@3's local and outside ledgers gain consumed - produced, the total their node sums; the
        energy ledger gains the standard-potential term + heat - work (§2.5)."""
        cell = row.reaction_consumed_fmol - row.reaction_produced_fmol
        outside = row.reaction_outside_consumed_fmol - row.reaction_outside_produced_fmol
        result["local"] = result["local"] + cell
        result["outside"] = result["outside"] + outside
        result["total"] = result["total"] + xp.sum(cell, axis=1) + xp.sum(outside, axis=1)
        result["energy"] = (
            result["energy"]
            + xp.sum(row.reaction_standard_energy_pJ)
            + xp.sum(row.reaction_outside_standard_energy_pJ)
            + xp.sum(row.reaction_dissipated_energy_pJ)
            + xp.sum(row.reaction_outside_dissipated_energy_pJ)
            - xp.sum(row.reaction_work_pJ)
            - xp.sum(row.reaction_outside_work_pJ)
        )
        return result, {}

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The moved amounts in the material ledgers and the absolute terms of every booking in
        the energy ledger's; every term is zero without reactions, so the bounds are then @3's."""
        cell = row.reaction_produced_fmol + row.reaction_consumed_fmol
        outside = row.reaction_outside_produced_fmol + row.reaction_outside_consumed_fmol
        magnitudes[0] = magnitudes[0] + cell
        magnitudes[1] = magnitudes[1] + outside
        magnitudes[2] = magnitudes[2] + xp.sum(cell, axis=1) + xp.sum(outside, axis=1)
        energy = xp.sum(row.reaction_energy_magnitude_pJ) + xp.sum(
            row.reaction_outside_energy_magnitude_pJ
        )
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes
