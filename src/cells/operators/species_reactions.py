"""Operator local_species_reactions@1: reactions on the shared species inventory (D152, version 1).

docs/SHARED_INVENTORY_REACTIONS_DESIGN.md (accepted 14 November 2026; rulings in §9). One reaction
network per composition, a split part (Strang halves) around @3's step. Every reaction is local: it
acts within one node, a cell or a finite outside node, on @3's species rows, which @3 owns
(neutral ones, and charged ones under FR-15 S1). The operator writes those rows in place and books
its writes in its own accumulators, as D150's operators do (§1.1): no second inventory, no @3 route
accumulator, no membrane-process hook.

Declaration (§2.1): `standard_concentration_mM` (c0 > 0); `species`, each a species of the inner
model with `moieties` (integer counts; null: the species is its own moiety), `standard_mu_RT`
(mu°/RT at c0), D150's identity (`catalogue`, `evidence`; species_common.parse_species, which
refuses a species with a membrane, junction or channel route of @3's, a channel whose law declares
its material term excepted) and, optionally,
`counter_ion` (FR-15 S1: a charged row that keeps @3's routes where @3's explicit-rate bound
covers it, species_common.check_counter_ion); `reactions`, each with `sites` ({"cells": [...] or
"all", "outside": [...] or "all"}: cells and finite outside nodes), integer `reactants` and
`products`, a `law` with its parameters, and `factors`. Every
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
  each side of molecularity <= 3; through laws/reactions/mass_action.reversible_flux, unchanged;
* factors on driven laws (they multiply): `hill_activation` x^n/(K^n + x^n) and `hill_inhibition`
  K^n/(K^n + x^n), `half_saturation_mM` K > 0 and `hill_coefficient` n > 0, the species x read.
Mass action consumes only its reactants (nu < 0 implies alpha >= 1), Michaelis-Menten only S, and
each passive flux every species it consumes, so no rate fails to vanish with a species it consumes
(§2.2): the parser makes that refusal unreachable. Parameters are per reaction, shared by its sites,
and bound per world as layout arrays, never closed-over constants (§2.3); the static structure
(species, stoichiometry, laws, factor kinds and species, sites) is the batch signature.

Material (§3.1): integer coefficients; a reaction that conserves every declared moiety is closed,
checked in integers; any other must be a pure source (every nu >= 0) or a pure sink (every nu <= 0),
or it is refused, as is one that changes no species. Charged species (FR-15 S1, 19 November
2026): every reaction conserves charge, sum nu z = 0 in integers, so a source or sink of a
charged species carries its counter-ions. In exact arithmetic every node's charge is then
unchanged and the z F phi terms of the booked rows cancel; in floating point each written row's
stored increment rounds once per half-step, so a node's charge moves by at most
(eps/2) F sum_s |z_s| (|d_s'| + |dn_s|) per half-step, d' the row's increment after the update,
plus the rounding of each nu dxi. The capacitor ledger allows the stored increments' rounding,
COMPONENT_STEP_ROUNDING (2.5) eps x steps x sum |z F d|, beside @3's own; the operator's two
half-steps take at most 2 eps of it per step in the worst case, and the measured runs use about
1e-4 of the allowance (surface_field's note) (§3.2). Neutral rows are as before.

The half-step (§4.2, Appendix A): SSPRK(3,3) in Butcher form at one sub-step, h = dt/2, per node
on the combined node axis (cells, then outside nodes): Y1 = n, Y2 = n + h nu J(Y1), Y3 = n + h nu
(J(Y1) + J(Y2))/4, dxi = h (J(Y1) + J(Y2) + 4 J(Y3))/6, dn = nu dxi, so the material identity
holds by construction. The stage condition h max L <= 1/2 at every stage, on unidirectional fluxes
(a passive route's forward flux consumes its reactants and its reverse flux its products), is
dt L <= 1; with it every stage is positive (the SSP property). A failure, or any non-finite or
non-positive stage or result, refuses the step (refused, never repaired); stage_report diagnoses
one on the host.

The step a declared accuracy needs (FR-43 / D315; docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.5). The
half-step is third order (the chain's errors at dt = 10, 5 and 2.5 ms fell by 8.9 and 8.4), so at a
fixed k dt the error is fixed, and accuracy, not the stage condition, sets the step for fast
transfers. Measured on FR-43's chain (tests/species_cap_fixtures.chain_world; links at k_f = 20
and 0.2 /s, L = 33 /s): at 16 to 1,024 species the error over the largest amount is 1.45e-4,
1.63e-5 and 1.93e-6 at dt = 10, 5 and 2.5 ms (dt L = 0.33, 0.17, 0.08), the same at every size, so
2e-5 needs dt of about 0.1 / k_f, six times below the stage condition's dt L <= 1 (30 ms here). At
k_f = 400 /s, dt = 5 ms (dt L = 3.3) is refused at the first step, dt = 1 ms (dt L = 0.66) gives
1.4e-3, and 2e-5 needs about 0.25 ms. So a run costs about 10 k_f steps per simulated second at
that accuracy. A transfer fast against the step the rest of a world needs is stiff, and needs a
separate law with a stiff integrator (D152 §7.3's door, deferred by D315), not a smaller check.

Energy (§3.3). Per node, G = RT sum n (ln(n/V) - 1) + sum mu°' n with mu°' = RT (mu°/RT - ln c0):
@3's chemical term on the touched rows plus the standard-potential term, which @3's term lacks and
the operator owns as a declared free-energy term, not a flow (`reaction_standard_energy_pJ`).
Per node and half-step the exact dG of the written rows, anchored at the half-step's start (D150's
adapter.species_chemical_free_energy_pJ, @3's own term one row at a time, plus the standard term),
is booked by the node's class in the step, which its multipliers set: driven only, W = dG and
H = 0; passive only, H = -dG and W = 0; both, H = sum of the passive routes' H_r and W = dG + H,
each H_r by the per-route hybrid: a route whose three stage rates and end-state affinity share one
nonzero sign books its average-vector-field share -dxi_r sum_s nu_sr mu-bar_s (McLachlan, Quispel
& Robidoux 1999), with mu-bar_s the divided-difference potential over the half-step; any other
books its stage quadrature h sum_k b_k RT J_r(Y_k) A_r(Y_k) >= 0. So W - H = dG exactly, and the
energy ledger gains standard term + heat - work. The known limit (§3.3, option (a)): at a half-step
in which a driven route carries a trace species across a passive route's equilibrium, the
quadrature samples the log-singular start and overbooks that step's heat (5.4-5.6 times at a
1e-12 mM trace in probe 2g), W by the same amount; guard and production worlds stay resolved at
every switch-on.

Energy guards (ENERGY_GUARD_STATEMENT). Under the IMEX solvers the shared energy bound is set by the
ions' flows, not by these bookings: in C2's mixed heredity chain it was 0.35 times this operator's
booking |W - H| with the reacting pair at µM and 409 times at nM, so an error the size of a booking
is seen at µM and unseen at nM, and a 1e-6 relative error is unseen at both; the face-free
species-only world, where this operator is the only energy flow, judged at rounding, and a NumPy ΔG
test per law are the guards of record.

Schedule `reaction_controls` (§2.1): per reaction (site null) and optionally per site, a
piecewise-constant multiplier m >= 0 from time 0, changing on the clock's grid (D283) inside the
horizon; on a passive reaction it scales both directions. A route takes its site's schedule, else
its reaction's.

Refusals at the definition (§2.5): the cases above; a held-bath site; more than 1,024 species per
world (D150's cap: FR-43 / D315, 16 by FR-9 / D165); an identity that differs from a D150
operator's; a turnover route on a (species, node) a reaction writes (one local-kinetics writer per
row, §1.1); a cell route on a slot that scheduled_cell_replacement@1 replaces (§2.1); RK4 (§4.6);
every provider or closer of the masks and outside anchors (CONFLICTS_VIEW: insertion@1 and @2, the
partition and the bridge); and a volume changer other than water (the lumens, replacement@2 by its
water: check_volume_changers). The stationary analysis refuses the composite by its own ID check
(§4.6).

Volumes (FR-43 / D315; composition option A, D152 §7.3's volume door). The cell and outside volumes
are current reads at the split (SCOPED_READS). Where water changes them, each half-step takes the
view's volumes for its concentrations, rates, stage condition and bookings, held over the half-step,
so a reacting row's dilution has its booked counterpart in water's dilution term and the energy
ledger closes; the palindrome is second order for the coupled system. Water is declared before the
network (C2's order rule). Where no operator changes the volumes, the part receives no view (C1's
fallback) and its program is today's.

Benign padding (the lead's ruling Q11 (a)): padded nodes hold an amount of 1 and a volume of 1,
padded factor slots K = 1 and n = 1 with kind 0, other laws' K_M 1, so every unused law branch and
padded entry stays finite.

Idle (§4.5): no route, statically idle; every multiplier zero in a step, the start state is selected
(never offset by a computed zero), so every field is bitwise the composition's without the operator.
Within a step, each (species, node) entry is written only where a route with a positive multiplier
changes it, and each node's fields only where such a route acts: a catalyst's or factor's row is
read, never offset, and an idle node beside an active one keeps every field bit for bit.

Labels (FR-42, D289; operators/species_labels.py): a reporter. Given labels (rows, arrival), the
half-step also returns its one-way moves for the labelled rows (one_way_moves): each route's
forward and reverse extents, the SSPRK(3,3) combination of its stages' one-way rates (a driven
route's are its extent and 0; a passive route's its two unidirectional fluxes, FR-42's stage 3),
times its consumed coefficients as out and its produced ones, at the arrival label, as into. The
physics is unchanged: the labelled call's state is bit for bit the unlabelled one's, and without
labels nothing of it is traced.
"""

import math
from dataclasses import dataclass
from types import MappingProxyType
from typing import NamedTuple

import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.laws.electrochemistry import R
from cells.laws.reactions.mass_action import reversible_flux
from cells.models import pump_composite_adapter as adapter
from cells.numerics.clock_instants import ON_THE_GRID, on_grid  # D283's one predicate.
from cells.numerics.species_sums import entity_sum, species_sum
from cells.operators import species_common as common
from cells.operators.contract import Operator, Read
from cells.operators.species_turnover import ROW_BARRIER, set_rows

LAW_ID = "local_species_reactions@1"
STEP_ID = "ssprk33_unidirectional_stage_condition_exact_bookings@1"
THETA = 0.5  # The stage condition h max L <= THETA at every stage (dt L <= 1 at one sub-step).
SERIES_BELOW = 1e-6  # |x| below which mu-bar's ratio (1 + x) log1p(x) / x takes its series.
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
# Each law as a word, for the run view's set of routes (a set's kinds are words, never IDs).
LAW_WORDS = {
    PASSIVE_LAW: "passive",
    MASS_ACTION: "mass_action",
    MICHAELIS_MENTEN: "michaelis_menten",
}
# Michaelis-Menten's rate key by case (the lead's ruling Q8): k_cat with a catalyst, V_max without.
CATALYTIC_RATE, MAX_RATE = "catalytic_rate_per_s", "max_rate_mM_per_s"
REACTION_KEYS = {"id", "sites", "reactants", "products", "law", "factors"}
MAX_MOLECULARITY = 3
# D150's statement (secreted-species design §7, the lead's ruling 4), adapted to these bookings
# with C2's measured ratios (this note §3.4, §10.4; tests/unit/test_species_reactions_guards.py).
ENERGY_GUARD_STATEMENT = (
    "Under the IMEX solvers the shared energy bound is set by the ions' flows, not by these "
    "bookings: in C2's mixed heredity chain it was 0.35 times this operator's booking |W - H| "
    "with the reacting pair at µM and 409 times at nM, so an error the size of a booking is seen "
    "at µM and unseen at nM, and a 1e-6 relative error is unseen at both; the face-free "
    "species-only world, where this operator is the only energy flow, judged at rounding, and a "
    "NumPy ΔG test per law are the guards of record."
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
    "reaction_energy_magnitude_pJ",
    "reaction_outside_energy_magnitude_pJ",
)
SIGNED_FIELDS = (  # Finite; the heat's sign is the composite's dissipation check's (_own_valid).
    "reaction_extent_fmol",
    "reaction_dissipated_energy_pJ",
    "reaction_outside_dissipated_energy_pJ",
    "reaction_work_pJ",
    "reaction_outside_work_pJ",
    "reaction_standard_energy_pJ",
    "reaction_outside_standard_energy_pJ",
)
READOUT_COLUMNS = (
    "reaction_rate_fmol_per_s",  # [route] at each row's state and held controls.
    "reaction_affinity_RT",  # [route] A/RT on passive routes, 0 on driven ones.
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
    "reaction_factor_slots",  # [declared factor] int64: its slot route x width + i, route-major.
    "reaction_standard_mu_RT",  # [species rows]: mu°/RT at c0.
    "reaction_standard_concentration_mM",  # []: c0.
)


@dataclass(frozen=True)
class ReactingSpecies:
    identity: common.SpeciesIdentity
    moieties: tuple | None  # ((moiety, count), ...) as declared; None: its own moiety.
    standard_mu_RT: float
    # FR-15 S1: a charged row that carries a reaction's charge balance and keeps @3's own routes,
    # admitted where @3's explicit-rate bound covers it (species_common.check_counter_ion).
    counter_ion: bool = False


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
    # FR-26's occupant rule (D244): ((replacement template ID, ((reaction ID, multiplier), ...)),
    # ...), a newcomer's multiplier for each reaction's route in its cell; () when not declared.
    templates: tuple = ()


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
    identities, counter_ions = [], set()
    for entry in raw:
        keys = {"id", "moieties", "standard_mu_RT", "catalogue", "evidence"}
        if isinstance(entry, dict) and "counter_ion" in entry:
            keys.add("counter_ion")  # Optional (FR-15 S1); absent, a row as before.
        _fields(entry, keys, "reacting species")
        identities.append({k: entry[k] for k in ("id", "catalogue", "evidence")})
        flag = entry.get("counter_ion", False)
        if type(flag) is not bool:
            raise ConfigError(f"{LAW_ID}: species {entry['id']!r}'s counter_ion is true or false")
        if flag:
            counter_ions.add(identifier(entry["id"]))
    # Charged rows admitted (FR-15 S1), each impermeant on @3's routes unless a covered counter-ion.
    parsed = common.parse_species(
        identities, base, LAW_ID, charged=True, counter_ions=frozenset(counter_ions)
    )
    return tuple(
        ReactingSpecies(
            identity,
            _moieties(entry["moieties"], identity.id),
            _number(entry["standard_mu_RT"], f"species {identity.id}'s standard_mu_RT"),
            identity.id in counter_ions,
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


def _kind(reactants, products, species, name, valence):
    """closed, source or sink (§3.1), in integer arithmetic; refused otherwise. Every reaction
    conserves charge, sum nu z = 0, in integers (FR-15 S1; valence: {species: z})."""
    nu = {s.identity.id: 0 for s in species}
    for s, count in reactants:
        nu[s] -= count
    for s, count in products:
        nu[s] += count
    if not any(nu.values()):
        raise ConfigError(f"{LAW_ID}: reaction {name} changes no species")
    charge = sum(int(valence[s]) * v for s, v in nu.items())
    if charge:
        raise ConfigError(
            f"{LAW_ID}: reaction {name} changes the net charge by sum(nu z) = {charge}: every "
            "reaction conserves charge, so a source or sink of a charged species carries its "
            "counter-ions (FR-15)"
        )
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
    valence = dict(zip(base.model.species_ids, base.model.valence, strict=True))
    kind = _kind(reactants, products, species, name, valence)
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


def _templates(raw, reactions):
    """FR-26's optional templates: [{template_id, multipliers: {reaction id: multiplier}}]."""
    if type(raw) is not list or not raw:
        raise ConfigError(f"{LAW_ID}: templates, where given, is a non-empty list")
    names = {r.id for r in reactions}
    out = []
    for entry in raw:
        _fields(entry, {"template_id", "multipliers"}, f"{LAW_ID} template")
        tid = identifier(entry["template_id"])
        if not isinstance(entry["multipliers"], dict) or not entry["multipliers"]:
            raise ConfigError(f"{LAW_ID}: template {tid} names its reactions' multipliers")
        rows = []
        for reaction, value in entry["multipliers"].items():
            if reaction not in names:
                raise ConfigError(f"{LAW_ID}: template {tid} names an undeclared reaction")
            rows.append((reaction, _number(value, f"{tid}'s multiplier of {reaction}", low=0)))
        out.append((tid, tuple(rows)))
    if len({tid for tid, _ in out}) != len(out):
        raise ConfigError(f"{LAW_ID}: a template is declared twice")
    return tuple(out)


def parse_reactions(raw, base):
    keys = {"law", "standard_concentration_mM", "species", "reactions"}
    _fields(raw, keys | ({"templates"} if "templates" in raw else set()), "species reactions")
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
    templates = _templates(raw["templates"], reactions) if "templates" in raw else ()
    return Reactions(LAW_ID, c0, species, tuple(reactions), tuple(routes), templates)


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
            **({"counter_ion": True} if s.counter_ion else {}),  # Absent as before (FR-15 S1).
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
    out = dict(
        law=declaration.law,
        standard_concentration_mM=declaration.standard_concentration_mM,
        species=species,
        reactions=reactions,
    )
    if (
        declaration.templates
    ):  # FR-26: absent when not declared, so definitions round-trip as before.
        out["templates"] = [
            dict(template_id=tid, multipliers=dict(rows)) for tid, rows in declaration.templates
        ]
    return out


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
        if on_grid(time, dt) is None:
            raise ConfigError(f"{LAW_ID}: a schedule change must be {ON_THE_GRID}")
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


def route_tables(declaration, schedule, spec=None):
    """Per route, its multiplier table ((time, multiplier), ...): its site's, else its
    reaction's. FR-26's occupant rule (D244): with templates and replacement@1 in `spec`, a cell
    route on a replaced slot follows the slot's occupants, the founder's table ending at its death
    and each newcomer's template multiplier held through its life (a newcomer's own schedule is
    version 1.1); a founder's change at or after its death is refused. Without templates the tables
    are as before, bit for bit."""
    keyed = {(c.reaction_id, c.site): c.changes for c in schedule}
    tables = [
        keyed.get((r.reaction, r.node), keyed.get((r.reaction, None))) for r in declaration.routes
    ]
    if spec is None or not declaration.templates:
        return tables
    lives = common.occupants(spec)
    multipliers = {tid: dict(rows) for tid, rows in declaration.templates}
    for k, route in enumerate(declaration.routes):
        if route.kind != "cell" or len(lives[route.node]) == 1:
            continue
        newcomers = lives[route.node][1:]
        death = newcomers[0].birth
        late = [t for t, _ in tables[k] if t >= death]
        if late:
            raise ConfigError(
                f"{LAW_ID}: reaction {route.reaction}'s schedule at {route.node} changes at "
                f"{late[0]:g} s, after its founder's death at {death:g} s; a newcomer takes its "
                "template's multiplier (give the other sites their own schedules)"
            )
        given = [(o.birth, multipliers.get(o.template, {}).get(route.reaction)) for o in newcomers]
        # A gap is refused at the definition (check_replaced_slots); the controls may be built
        # before that check runs.
        tables[k] = (*tables[k], *((t, m) for t, m in given if m is not None))
    return tables


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
        reaction_factor_slots=np.flatnonzero(factor_kind).astype(np.int64),
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


WATER = "ideal_osmosis_linear_compliance_water@1"  # The one volume changer admitted (FR-43).


def check_volume_changers(spec, law=LAW_ID):
    """FR-43 / D315: `law` reads the volumes current at the split, and water is the one changer of
    them admitted beside it. A restricted lumen (its lumen volumes) and replacement@2 (a newcomer's
    volume written into water's state) stay refused until a probe covers them."""
    for op, _, _ in composite_spec.entries(spec):
        if op.LAW_ID in (law, WATER):
            continue
        if {"volume", "extracellular_volume"} & set(op.VIEW_FIELDS) or (
            "volume_increment_pL" in op.ENTITY_WRITES
        ):
            raise ConfigError(
                f"{law}: {op.LAW_ID} changes the volumes it reads; water is the one volume "
                "changer admitted beside it (FR-43 / D315)"
            )


def row_volumes(op, view, model):
    """The (cell, outside) volumes at an observed row: the view's where op reads them current (the
    composite passes it views, FR-43), else None: the declared ones (network())."""
    if view is None or op not in getattr(model, "view_readers", ()):
        return None
    return (np.asarray(view.volume), np.asarray(view.extracellular_volume))


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
    """A cell route on a slot that replacement@1 replaces is admitted only where every newcomer
    there comes from a template whose multiplier for the route's reaction this declaration gives
    (FR-26's occupant rule, D244); a donor copy there is version 1.1. Each template is a replacement
    template, and each multiplier a reaction with a cell route on a slot its newcomers fill
    (outside routes compose as before; §2.1, the lead's ruling 6)."""
    replacement, events = common.replacement_of(spec)
    multipliers = {tid: dict(rows) for tid, rows in declaration.templates}
    known = set() if replacement is None else {t.id for t in replacement.templates}
    for tid in multipliers:
        if tid not in known:
            raise ConfigError(
                f"{LAW_ID} declares multipliers for {tid}, not a replacement template"
            )
    filled = {}
    for v in events:
        filled.setdefault(v.slot, []).append(v)
    used = set()
    for route in declaration.routes:
        if route.kind != "cell" or route.node not in filled:
            continue
        for v in filled[route.node]:
            if v.newcomer != "isolated_template":
                raise ConfigError(
                    f"{LAW_ID}: reaction {route.reaction} acts in cell {route.node}, which a "
                    "donor copy fills; a donor copy's reaction multipliers are version 1.1"
                )
            if route.reaction not in multipliers.get(v.template, {}):
                raise ConfigError(
                    f"{LAW_ID}: reaction {route.reaction} acts in cell {route.node}, a slot "
                    f"{common.REPLACEMENT_LAW} replaces, and a newcomer from template "
                    f"{v.template} takes no multiplier for it: declare it in this operator's "
                    "templates (its occupant rule)"
                )
            used.add((v.template, route.reaction))
    for tid, rows in multipliers.items():
        unused = sorted(set(rows) - {r for t, r in used if t == tid})
        if unused:
            raise ConfigError(
                f"{LAW_ID}: template {tid}'s multiplier for {unused[0]} applies to no cell route "
                "on a slot its newcomers fill"
            )


# ------------------------------------------------------------------ device parts


def _species_mask(rows, size, *, xp):
    """[species] True on the network's rows."""
    if xp is jnp:
        return jnp.zeros(size, dtype=bool).at[rows].set(True)
    out = np.zeros(size, dtype=bool)
    out[np.asarray(rows)] = True
    return out


def _to_nodes(values, node, size, *, xp):
    """[rows, route] values summed onto [rows, node] by each route's node."""
    if xp is jnp:
        return jnp.zeros((values.shape[0], size), dtype=values.dtype).at[:, node].add(values)
    out = np.zeros((values.shape[0], size))
    np.add.at(out, (slice(None), np.asarray(node)), values)
    return out


def _placed(values, slots, shape, *, xp):
    """values [k] at the flat slots [k] of an array of `shape`, zero elsewhere (exact placement)."""
    size = int(np.prod(shape))
    if xp is jnp:
        return jnp.zeros(size, dtype=values.dtype).at[slots].set(values).reshape(shape)
    out = np.zeros(size)
    out[np.asarray(slots)] = values
    return out.reshape(shape)


def _node_sum(values, node, size, *, xp):
    """[route] values summed onto [node]."""
    if xp is jnp:
        return jnp.zeros(size, dtype=values.dtype).at[node].add(values)
    out = np.zeros(size)
    np.add.at(out, np.asarray(node), values)
    return out


class Network(NamedTuple):
    """The network's arrays for one half-step, on the combined node axis (cells, then outside)."""

    node: object  # [route] combined node index.
    size: int  # Cells plus outside slots (static).
    mask: object  # [node] active cells and finite outside nodes.
    volume: object  # [node] pL: the view's current ones, else the declared ones (network()).
    route_volume: object  # [route] pL.
    alpha: object  # [rows, route].
    beta: object
    nu: object
    catalysis: object  # [rows, route]: alpha + the Michaelis-Menten catalyst's order 1.
    passive: object  # [route] bool.
    saturable: object  # [route] bool: Michaelis-Menten.
    on: object  # [route] bool: a positive multiplier in this step.
    driven_scale: object  # [route] m k V (driven laws), fmol/s per mM^q.
    passive_scale: object  # [route] m V c0 k_f.
    delta_mu_RT: object  # [route] sum nu mu°/RT.
    standard_pJ: object  # [rows] mu°' = RT (mu°/RT - ln c0), pJ/fmol.
    RT: object  # pJ/fmol.


def network(p, multiplier, *, xp, volumes=None):
    """volumes: (cell, outside) pL, the view's current volumes where an operator of the composition
    changes them (FR-43 / D315), else None: the declared ones bound at the definition (C1's
    fallback, today's program)."""
    n = p.active.shape[0]
    size = n + p.outside_active.shape[0]
    node = xp.where(p.reaction_route_outside, n + p.reaction_route_node, p.reaction_route_node)
    mask = xp.concatenate((p.active, p.outside_active & ~p.reservoir))
    cell, outside = (p.volume, p.extracellular_volume) if volumes is None else volumes
    volume = xp.concatenate((cell, outside))
    route_volume = volume[node]
    alpha, beta = p.reaction_reactants, p.reaction_products
    law = p.reaction_route_law
    c0, rate = p.reaction_standard_concentration_mM, p.reaction_rate_constant
    nu = beta - alpha
    RT = 1e-3 * R * p.temperature
    return Network(
        node=node,
        size=size,
        mask=mask,
        volume=volume,
        route_volume=route_volume,
        alpha=alpha,
        beta=beta,
        nu=nu,
        catalysis=alpha + p.reaction_catalyst,
        passive=law == PASSIVE,
        saturable=law == DRIVEN_MICHAELIS_MENTEN,
        on=multiplier > 0,
        driven_scale=multiplier * rate * route_volume,
        passive_scale=multiplier * route_volume * c0 * rate,
        delta_mu_RT=species_sum(nu * p.reaction_standard_mu_RT[:, None], xp=xp),
        standard_pJ=RT * (p.reaction_standard_mu_RT - xp.log(c0)),
        RT=RT,
    )


def node_amounts(state, p, *, xp):
    """[rows, node] the network's amounts, cells then outside nodes (1 where masked: benign)."""
    rows = p.reaction_rows
    amounts = xp.concatenate(
        (
            p.amount_reference[rows] + state.amount_increment[rows],
            p.extracellular_amount_reference[rows] + state.extracellular_amount_increment[rows],
        ),
        axis=1,
    )
    mask = xp.concatenate((p.active, p.outside_active & ~p.reservoir))
    return xp.where(mask[None, :], amounts, 1.0)


class Rates(NamedTuple):
    rate: object  # [route] fmol/s, signed on passive routes.
    affinity: object  # [route] A/RT on passive routes (finite padding elsewhere).
    consumption: object  # [rows, route] fmol/s: what each route's fluxes consume of each row.


def route_rates(amounts, net, p, *, xp, one_way=False):
    """Each route's rate at the node amounts [rows, node] (§2.2, Appendix A); with one_way (FR-42,
    static) (Rates, its one-way rates: ([route] forward, [route] reverse) fmol/s)."""
    held = amounts[:, net.node]  # [rows, route]
    log_c = xp.log(held) - xp.log(net.route_volume)[None, :]
    # Passive: the kernel's net rate and affinity, unchanged; its unidirectional fluxes from the
    # same activity logarithms, for the stage condition only.
    activity = held / (net.route_volume * p.reaction_standard_concentration_mM)[None, :]
    net_rate, affinity = reversible_flux(
        activity, net.alpha, net.beta, net.delta_mu_RT, net.passive_scale, xp=xp
    )
    log_a = xp.log(activity)
    forward = net.passive_scale * xp.exp(species_sum(xp.moveaxis(net.alpha * log_a, -2, 0), xp=xp))
    reverse = net.passive_scale * xp.exp(
        species_sum(xp.moveaxis(net.beta * log_a, -2, 0), xp=xp) + net.delta_mu_RT
    )
    # Driven: m F k V prod c^alpha (mass action), m F k V c_E c_S / (K_M + c_S) (Michaelis-Menten,
    # with or without its catalyst), the factors in log space, evaluated at the declared factors'
    # slots only (the padding's ln f is 0, placed). One branch each: ln f = -logaddexp(0, s z)
    # with s = -1 on an activation and +1 on an inhibition, and s z is -z or z exactly, so every
    # ln f is bit for bit the two-branch form's, and the sum over the factor axis is unchanged.
    kind, slots = p.reaction_factor_kind, p.reaction_factor_slots
    route = slots // max(kind.shape[1], 1)
    x = log_c[p.reaction_factor_species.reshape(-1)[slots], route]  # [declared factor] ln x.
    z = p.reaction_factor_coefficient.reshape(-1)[slots] * (
        x - xp.log(p.reaction_factor_half_saturation_mM.reshape(-1)[slots])
    )
    sign = xp.where(kind.reshape(-1)[slots] == 1, -1.0, 1.0)
    log_f = _placed(-xp.logaddexp(0.0, sign * z), slots, kind.shape, xp=xp)
    factor = xp.exp(entity_sum(log_f, axis=1, xp=xp))
    substrate = xp.take_along_axis(held, p.reaction_route_substrate[None, :], axis=0)[0]
    c_s = substrate / net.route_volume
    saturation = xp.where(net.saturable, p.reaction_saturation_mM + c_s, 1.0)
    driven = (
        net.driven_scale * factor * xp.exp(species_sum(net.catalysis * log_c, xp=xp)) / saturation
    )
    rate = xp.where(net.passive, net_rate, driven)
    consumed, produced = xp.maximum(-net.nu, 0.0), xp.maximum(net.nu, 0.0)
    consumption = xp.where(
        net.passive[None, :], consumed * forward + produced * reverse, consumed * driven
    )
    if not one_way:
        return Rates(rate, affinity, consumption)
    # FR-42 (static): each route's one-way rates, a passive route's two, a driven route's own.
    gross = (xp.where(net.passive, forward, driven), xp.where(net.passive, reverse, 0.0))
    return Rates(rate, affinity, consumption), gross


def stage_rates(amounts, net, p, h, *, xp, one_way=False):
    """(Rates, the stage condition h max L <= 1/2 at these amounts, max h L); with one_way
    (FR-42, static) the stage's one-way rates last."""
    rates = route_rates(amounts, net, p, xp=xp, one_way=one_way)
    rates, *gross = rates if one_way else (rates,)
    load = _to_nodes(rates.consumption, net.node, net.size, xp=xp) / amounts
    hl = xp.where(net.mask[None, :], h * load, 0.0)
    return (rates, xp.all(hl <= THETA), xp.max(hl, initial=0.0), *gross)


def _change(values, net, *, xp):
    """[rows, node] sum_r nu_r values_r at each node."""
    return _to_nodes(net.nu * values[None, :], net.node, net.size, xp=xp)


def divided_potential(n, dn, net, *, xp):
    """mu-bar [rows, node], pJ/fmol: the divided difference of g(n) = RT n (ln(n/V) - 1) + mu°' n
    over the half-step, in its stable form (§3.3; the series 1 + x/2 - x^2/6 for |x| < 1e-6)."""
    x = dn / n
    small = xp.abs(x) < SERIES_BELOW
    ratio = xp.where(
        small, 1.0 + x / 2 - x * x / 6, (1.0 + x) * xp.log1p(x) / xp.where(small, 1.0, x)
    )
    mean = xp.log(n / net.volume[None, :]) + ratio - 1.0
    return net.RT * mean + net.standard_pJ[:, None]


class Step(NamedTuple):
    """One half-step of the network: everything the state update and the bookings read."""

    dn: object  # [rows, node] the net change.
    extent: object  # [route] delta xi.
    written: object  # [rows, node] bool: a row a route with a positive multiplier changes.
    touched: object  # [node] bool: a node with a route with a positive multiplier.
    mixed: object  # [node] bool.
    passive_only: object
    driven_only: object
    free_energy: object  # [node] dG, standard term included, pJ.
    standard: object  # [node] the standard-potential term, pJ.
    magnitude: object  # [node] |terms| of the bookings, pJ.
    heat: object  # [node] pJ.
    work: object  # [node] pJ.
    nonreversing: object  # [route] bool: the hybrid's branch (meaningful on passive routes).
    route_heat: object  # [route] H_r at mixed nodes (0 on driven routes).
    rates: object  # ([route] J at Y1, Y2, Y3), fmol/s.
    affinities: object  # ([route] A/RT at Y1, Y2, Y3), and at the end state below.
    end_affinity: object
    max_hl: object  # The largest h L over the three stages.
    valid: object


def half_step_terms(state, multiplier, h, p, *, xp, one_way=False, volumes=None):
    """SSPRK(3,3) over h on the network (§4.2, Appendix A) and the bookings (§3.3): a Step; with
    one_way (FR-42, static) (Step, each stage's one-way rates). volumes: network()'s, held fixed
    over the half-step: its concentrations, rates, stage condition and bookings take them."""
    net = network(p, multiplier, xp=xp, volumes=volumes)
    n = node_amounts(state, p, xp=xp)
    s1, ok1, l1, *g1 = stage_rates(n, net, p, h, xp=xp, one_way=one_way)
    y2 = n + h * _change(s1.rate, net, xp=xp)
    s2, ok2, l2, *g2 = stage_rates(y2, net, p, h, xp=xp, one_way=one_way)
    y3 = n + h * _change(0.25 * (s1.rate + s2.rate), net, xp=xp)
    s3, ok3, l3, *g3 = stage_rates(y3, net, p, h, xp=xp, one_way=one_way)
    extent = h * (s1.rate + s2.rate + 4.0 * s3.rate) / 6.0
    dn = _change(extent, net, xp=xp)
    end = n + dn
    rows = net.mask[None, :]
    valid = ok1 & ok2 & ok3
    for amounts in (y2, y3, end):
        valid &= xp.all(xp.where(rows, xp.isfinite(amounts) & (amounts > 0), True))
    # The node's class in this step, from its multipliers (§3.3).
    on = xp.where(net.on, 1.0, 0.0)
    driven_on = _node_sum(xp.where(net.passive, 0.0, on), net.node, net.size, xp=xp) > 0
    passive_on = _node_sum(xp.where(net.passive, on, 0.0), net.node, net.size, xp=xp) > 0
    touched = (driven_on | passive_on) & net.mask
    mixed = driven_on & passive_on & net.mask
    written = (_to_nodes(xp.abs(net.nu) * on[None, :], net.node, net.size, xp=xp) > 0) & rows
    # The exact dG of the rows written, anchored at the half-step's start (@3's own term, one row at
    # a time, plus the owned standard-potential term), with its absolute terms.
    change = xp.where(written, dn, 0.0)
    chemical = adapter.species_chemical_free_energy_pJ(
        n, change, net.volume[None, :], p.temperature, xp=xp
    )
    chemical_terms = adapter.species_chemical_magnitude_pJ(
        n, change, net.volume[None, :], p.temperature, xp=xp
    )
    standard_rows = net.standard_pJ[:, None] * change
    free_energy = species_sum(chemical + standard_rows, xp=xp, barrier=ROW_BARRIER)
    standard = species_sum(standard_rows, xp=xp, barrier=ROW_BARRIER)
    magnitude = species_sum(chemical_terms + xp.abs(standard_rows), xp=xp, barrier=ROW_BARRIER)
    # The hybrid at mixed nodes (§3.3): a passive route keeps its share unless it reverses within
    # the step (three stage rates and the end-state affinity of one nonzero sign), else its stage
    # quadrature of RT A J, which is non-negative by construction.
    _, end_affinity = reversible_flux(
        end[:, net.node] / (net.route_volume * p.reaction_standard_concentration_mM)[None, :],
        net.alpha,
        net.beta,
        net.delta_mu_RT,
        net.passive_scale,
        xp=xp,
    )
    sign = xp.sign(s1.rate)
    nonreversing = (
        (sign != 0)
        & (xp.sign(s2.rate) == sign)
        & (xp.sign(s3.rate) == sign)
        & (xp.sign(end_affinity) == sign)
    )
    potential = divided_potential(n, change, net, xp=xp)
    share = -extent * species_sum(net.nu * potential[:, net.node], xp=xp)
    quadrature = (
        h
        * net.RT
        * (s1.rate * s1.affinity + s2.rate * s2.affinity + 4.0 * s3.rate * s3.affinity)
        / 6.0
    )
    route_heat = xp.where(net.passive & net.on, xp.where(nonreversing, share, quadrature), 0.0)
    mixed_heat = _node_sum(route_heat, net.node, net.size, xp=xp)
    passive_only = passive_on & ~driven_on & net.mask
    driven_only = driven_on & ~passive_on & net.mask
    heat = xp.where(mixed, mixed_heat, xp.where(passive_only, -free_energy, 0.0))
    work = xp.where(mixed, free_energy + heat, xp.where(driven_only, free_energy, 0.0))
    magnitude = magnitude + xp.where(mixed, xp.abs(heat), 0.0)
    for value in (free_energy, heat, work, magnitude):
        valid &= xp.all(xp.where(net.mask, xp.isfinite(value), True))
    max_hl = xp.maximum(xp.maximum(l1, l2), l3)
    step = Step(
        dn,
        extent,
        written,
        touched,
        mixed,
        passive_only,
        driven_only,
        free_energy,
        standard,
        magnitude,
        heat,
        work,
        nonreversing,
        route_heat,
        (s1.rate, s2.rate, s3.rate),
        (s1.affinity, s2.affinity, s3.affinity),
        end_affinity,
        max_hl,
        valid,
    )
    return (step, (*g1, *g2, *g3)) if one_way else step


def _own_valid(state, p, *, xp):
    """Finite, and signed as booked: the material accumulators and magnitudes >= 0, a driven
    route's extent >= 0. The heat's sign is the composite's dissipation check's (-1e-12 pJ), since
    a passive-only node books -dG, which rounding can leave at about -1e-18 pJ (§3.3)."""
    valid = xp.asarray(True)
    for name in NON_NEGATIVE_FIELDS:
        value = getattr(state, name)
        valid &= xp.all(xp.isfinite(value)) & xp.all(value >= 0)
    for name in SIGNED_FIELDS:
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


def _split(values, n):
    return values[..., :n], values[..., n:]


def reactions_half_step(state, multiplier, h, p, *, xp=jnp, labels=None, volumes=None):
    """(state after h of the network, validity): the network's rows and the operator's own fields,
    each entry selected where a route with a positive multiplier writes it, else its start value
    (never offset by a computed zero, §4.5). With labels (FR-42, D289; static), also its one-way
    moves (one_way_moves). volumes: the view's current volumes, or None (network())."""
    if labels is None:
        step = half_step_terms(state, multiplier, h, p, xp=xp, volumes=volumes)
    else:
        step, gross = half_step_terms(state, multiplier, h, p, xp=xp, one_way=True, volumes=volumes)
    rows = p.reaction_rows
    n = p.active.shape[0]
    cell_rows, outside_rows = _split(step.written, n)
    cell_dn, outside_dn = _split(step.dn, n)
    cell_on, outside_on = _split(step.touched, n)

    def rows_update(full, written, values):
        old = full[rows]
        return set_rows(full, rows, xp.where(written, old + values, old), xp=xp)

    def nodes_update(old, touched, values):
        return xp.where(touched, old + values, old)

    heat, work = _split(step.heat, n), _split(step.work, n)
    standard, magnitude = _split(step.standard, n), _split(step.magnitude, n)
    new = state._replace(
        amount_increment=rows_update(state.amount_increment, cell_rows, cell_dn),
        extracellular_amount_increment=rows_update(
            state.extracellular_amount_increment, outside_rows, outside_dn
        ),
        reaction_extent_fmol=xp.where(
            multiplier > 0, state.reaction_extent_fmol + step.extent, state.reaction_extent_fmol
        ),
        reaction_produced_fmol=rows_update(
            state.reaction_produced_fmol, cell_rows, xp.maximum(cell_dn, 0.0)
        ),
        reaction_consumed_fmol=rows_update(
            state.reaction_consumed_fmol, cell_rows, xp.maximum(-cell_dn, 0.0)
        ),
        reaction_outside_produced_fmol=rows_update(
            state.reaction_outside_produced_fmol, outside_rows, xp.maximum(outside_dn, 0.0)
        ),
        reaction_outside_consumed_fmol=rows_update(
            state.reaction_outside_consumed_fmol, outside_rows, xp.maximum(-outside_dn, 0.0)
        ),
        reaction_dissipated_energy_pJ=nodes_update(
            state.reaction_dissipated_energy_pJ, cell_on, heat[0]
        ),
        reaction_outside_dissipated_energy_pJ=nodes_update(
            state.reaction_outside_dissipated_energy_pJ, outside_on, heat[1]
        ),
        reaction_work_pJ=nodes_update(state.reaction_work_pJ, cell_on, work[0]),
        reaction_outside_work_pJ=nodes_update(state.reaction_outside_work_pJ, outside_on, work[1]),
        reaction_standard_energy_pJ=nodes_update(
            state.reaction_standard_energy_pJ, cell_on, standard[0]
        ),
        reaction_outside_standard_energy_pJ=nodes_update(
            state.reaction_outside_standard_energy_pJ, outside_on, standard[1]
        ),
        reaction_energy_magnitude_pJ=nodes_update(
            state.reaction_energy_magnitude_pJ, cell_on, magnitude[0]
        ),
        reaction_outside_energy_magnitude_pJ=nodes_update(
            state.reaction_outside_energy_magnitude_pJ, outside_on, magnitude[1]
        ),
    )
    valid = step.valid & _own_valid(new, p, xp=xp)
    if labels is None:
        return new, valid
    return new, valid, one_way_moves(gross, multiplier, h, p, labels, xp=xp)


def one_way_moves(gross, multiplier, h, p, labels, *, xp=jnp):
    """(out [m, node], into [m, label, node], ()) of the labelled rows over a half-step h (FR-42's
    interface, operators/contract.py; the network's node axis, cells then outside nodes). Each
    route's one-way extents, forward and reverse, are the SSPRK(3,3) combination of its stages'
    one-way rates, as its extent is of its net rates (a driven route's forward extent is its
    extent, its reverse 0; FR-42's stage 3 adds a passive route's two). The forward extent
    consumes max(-nu, 0) and makes max(nu, 0), the reverse the opposite, so a species on both
    sides of a route counts its net in each direction. Out is what they consume, into what they
    make, at the arrival label. Into minus out is each row's booked move, at rounding."""
    net = network(p, multiplier, xp=xp)
    (f1, r1), (f2, r2), (f3, r3) = gross
    forward = h * (f1 + f2 + 4.0 * f3) / 6.0
    reverse = h * (r1 + r2 + 4.0 * r3) / 6.0
    consumed, produced = xp.maximum(-net.nu, 0.0), xp.maximum(net.nu, 0.0)
    taken = consumed * forward[None, :] + produced * reverse[None, :]
    made = produced * forward[None, :] + consumed * reverse[None, :]
    taken = _to_nodes(taken, net.node, net.size, xp=xp)
    made = _to_nodes(made, net.node, net.size, xp=xp)
    label_rows, arrival = labels
    match = p.reaction_rows[None, :] == xp.asarray(label_rows)[:, None]  # [m, network rows]
    own, at = xp.any(match, axis=1)[:, None], xp.argmax(match, axis=1)
    out = xp.where(own, taken[at], 0.0)
    return out, arrival[:, :, None] * xp.where(own, made[at], 0.0)[:, None, :], ()


def stage_report(state, control, p, dt, volumes=None):
    """Host-side diagnosis of a refused step (§4.2): the largest h L over the three stages at this
    state and control (h = dt/2), the condition's verdict, and the largest dt that the start state's
    own rates admit (dt L <= 1 at the first stage; the later stages can bind sooner). volumes: the
    row's current volumes where they change (network()), else the declared ones."""
    multiplier = np.asarray(control.reaction_multiplier)
    step = half_step_terms(state, multiplier, 0.5 * dt, p, xp=np, volumes=volumes)
    net = network(p, multiplier, xp=np, volumes=volumes)
    n = node_amounts(state, p, xp=np)
    rates = route_rates(n, net, p, xp=np)
    load = np.where(
        net.mask[None, :], _to_nodes(rates.consumption, net.node, net.size, xp=np) / n, 0
    )
    largest = float(np.max(load, initial=0.0))
    return dict(
        max_hL=float(step.max_hl),
        admitted=bool(step.max_hl <= THETA),
        valid=bool(step.valid),
        start_rate_per_s=largest,
        admissible_dt_at_start_s=math.inf if largest == 0 else 1.0 / largest,
    )


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
    # B1′: D152's multiplier, which a rate route may multiply in the half-steps (both directions,
    # so detailed balance is kept; docs/INVENTORY_COUPLING_DESIGN.md §2.1).
    ROUTABLE_CONTROLS = MappingProxyType({"reaction_multiplier": "rate"})
    EXPERIMENT_KEYS = (CONTROLS_KEY,)
    # The volumes are current reads at the split (FR-43 / D315; composition option A, D152 §7.3's
    # volume door): where water changes them, each half-step's concentrations, rates, stage
    # condition and bookings take the view's, held over the half-step; where no operator changes
    # them the part receives no view and reads the declared ones (C1's fallback, today's program).
    # Water is the one changer admitted (check_volume_changers). A closer counts as a mask's
    # provider (S5), and insertion@1 provides the outside mask and anchors (§1.4): refused.
    CONFLICTS_VIEW = ("active", "outside_active", "extracellular_amount_reference")
    VIEW_READS = ("volume", "extracellular_volume")
    # Door S (docs/SCOPED_COMPOSITION_DESIGN.md §5): its outside reads are at finite nodes only
    # (node_amounts and reactions_domain_valid mask held baths), so a change at a held bath, such
    # as a bath dose, does not meet them.
    SCOPED_READS = {
        "volume": Read("current", "split"),
        "extracellular_volume": Read("current", "split", scoped=True),
        "outside_active": Read("fixed", "split", scoped=True),
        "extracellular_amount_reference": Read("fixed", "split", scoped=True),
    }
    READOUT_COLUMNS = READOUT_COLUMNS
    ENTITY_WRITES = {
        "amount_increment": ("reaction_produced_fmol", "reaction_consumed_fmol"),
        "extracellular_amount_increment": (
            "reaction_outside_produced_fmol",
            "reaction_outside_consumed_fmol",
        ),
    }
    # Its layer in the run view (docs/RUN_VIEW_DESIGN.md §3): simulated, since every rate follows
    # from the state (the multipliers only scale it).
    VIEW_LAYERS = (
        {"id": "reactions", "label": "Species reactions", "representation": "simulated"},
    )
    # Its records in the run view (the contract): the readouts are per route, as the extent is;
    # A/RT is a number; every accumulator is a total since the start (the heat and work fields by
    # their roles); the rate is a rate and the affinity a level.
    OBSERVATION_AXES = {
        "reaction_rate_fmol_per_s": ("reaction_route",),
        "reaction_affinity_RT": ("reaction_route",),
    }
    UNITS = {"reaction_affinity_RT": "1"}
    RECORD_KINDS = {
        "reaction_extent_fmol": "cumulative",
        "reaction_produced_fmol": "cumulative",
        "reaction_consumed_fmol": "cumulative",
        "reaction_outside_produced_fmol": "cumulative",
        "reaction_outside_consumed_fmol": "cumulative",
        "reaction_standard_energy_pJ": "cumulative",
        "reaction_outside_standard_energy_pJ": "cumulative",
        "reaction_energy_magnitude_pJ": "cumulative",
        "reaction_outside_energy_magnitude_pJ": "cumulative",
        "reaction_rate_fmol_per_s": "rate",
        "reaction_affinity_RT": "level",
    }
    # Signs, by the roles of its route set (view_sets), as the code computes them: a passive
    # route's net rate is its forward flux less its reverse one, and its affinity the forward
    # log-term less the reverse one (laws/reactions/mass_action.reversible_flux); a driven route
    # runs forward only, and its affinity is reported as 0 (observe).
    ORIENTATION = {
        "reaction_extent_fmol": {
            "from": "reactants",
            "to": "products",
            "says": "a positive extent is net forward progress since the start: the route has "
            "turned its reactants into its products; a driven route's is zero or more",
            "source": "species_reactions' half-step: dxi = h (J(Y1) + J(Y2) + 4 J(Y3)) / 6",
        },
        "reaction_rate_fmol_per_s": {
            "from": "reactants",
            "to": "products",
            "says": "a positive rate runs the route forward, its reactants into its products; a "
            "passive route's is its forward flux less its reverse flux, a driven route's is zero "
            "or more",
            "source": "laws/reactions/mass_action.reversible_flux and "
            "species_reactions.route_rates",
        },
        "reaction_affinity_RT": {
            "plus": "reactants",
            "minus": "products",
            "says": "A/RT, the reactants' chemical potential less the products' over RT (minus "
            "the reaction's free energy over RT): positive drives a passive route forward, zero "
            "at its equilibrium; 0 on driven routes",
            "source": "laws/reactions/mass_action.reversible_flux and species_reactions.observe",
        },
    }

    def view_sets(self, spec, declaration):
        """The run view's set of its own axis (cells/records/run_view.py): its routes, each one reaction
        at one site, in the declaration's order (reaction by reaction, then site), each named
        `reaction:node`, at its cell or outside node, with its law as a word and the roles its
        signs name."""  # noqa: E501
        laws = {r.id: r.law for r in declaration.reactions}
        routes = declaration.routes
        return {
            "reaction_route": {
                "id": "reaction_route",
                "ids": tuple(f"{r.reaction}:{r.node}" for r in routes),
                "holds": "reaction route",
                "at": tuple({"cell" if r.kind == "cell" else "outside": r.node} for r in routes),
                "kinds": tuple(LAW_WORDS[laws[r.reaction]] for r in routes),
                "roles": {
                    "reactants": "the species the route's reaction consumes when it runs forward",
                    "products": "the species it makes when it runs forward",
                },
            }
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
        tables = route_tables(declaration, schedule, spec)
        return (common.control_arrays(tables, times, 1)[..., 0],)

    def routable_elements(self, declaration, field):
        """B1′: reaction_multiplier's elements are its routes (reaction, site), by reaction ID,
        each at its cell (None for an outside node), in control order."""
        return tuple(
            (route.reaction, route.node if route.kind == "cell" else None)
            for route in declaration.routes
        )

    def half_step_rows(self, declaration):
        """B1′: each reaction's reactants and products at each of its cell sites (a catalyst and
        a rate factor are read, not moved)."""
        reactions = {r.id: r for r in declaration.reactions}
        return tuple(
            dict.fromkeys(
                (species, route.node)
                for route in declaration.routes
                if route.kind == "cell"
                for species, _ in (
                    *reactions[route.reaction].reactants,
                    *reactions[route.reaction].products,
                )
            )
        )

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
        check_volume_changers(spec)
        common.registry.check_shared_rows(spec, LAW_ID)
        check_replaced_slots(spec, declaration)
        route_tables(declaration, schedule, spec)  # FR-26: a founder's change after its death.

    def read_slots(self, spec, declaration):
        """Door S: every finite outside node (its domain reads them all; held baths are masked)."""
        finite = tuple(i for i, c in enumerate(spec.model.extracellular) if not c.reservoir)
        return dict.fromkeys((k for k, r in self.SCOPED_READS.items() if r.scoped), finite)

    def species_identities(self, declaration):
        """The species identities it declares (registry/species_registry.py, D176)."""
        return tuple(s.identity for s in declaration.species)

    def written_species(self, declaration):
        """The species its routes write (a nonzero net coefficient at a node): the registry's
        shared-row rule reads them (species_registry.check_shared_rows; FR-43 / D315)."""
        return tuple(dict.fromkeys(name for name, _ in written(declaration)))

    def species_potentials(self, declaration):
        """Its declared mu°/RT of each reacting species at its c0 (core/species_registry.py,
        check_potentials: the registry's, where it gives one, must agree; F2)."""
        c0 = declaration.standard_concentration_mM
        return tuple((s.identity.id, s.standard_mu_RT, c0) for s in declaration.species)

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
        """Values per saved row (execution/resources.row_bytes): the accumulators at every slot and
        the routes' extents, times a margin of 8."""
        x, s = spec.execution, len(spec.model.species_ids)
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        count = len(declaration.routes)
        return 8 * ((4 * s + 8) * (x.capacity + x.extracellular_capacity) + count)

    def fixed_working_size(self, spec):
        """Values held once per resident copy (execution/resources.fixed_bytes): the bound network,
        its dense [species rows, route] arrays and its per-route and per-factor values, times a
        margin of 8. Before FR-43 (D315) working_size counted it on every saved row, about k times
        the rows' own size for a chain of k species: 9.5 GiB for 256 species at 400 steps, against a
        measured peak of 1.1 GiB (docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.6)."""
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        k, count = len(declaration.species), len(declaration.routes)
        return 8 * count * (6 * k + 16)

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
            "reaction_step": "SSPRK(3,3) half-steps under h max L <= 1/2 (dt L <= 1), exact "
            "dG bookings with the per-route hybrid at mixed nodes",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.reaction_route_node.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp, labels=None, view=None):
        """labels (FR-42, D289; static): (rows, arrival); the call then also returns its one-way
        moves. view: the reader view the composite passes where an operator changes the volumes
        (FR-43 / D315), whose current volumes the half-step takes; without one (C1's fallback),
        today's call."""
        m = control.reaction_multiplier
        volumes = None if view is None else (view.volume, view.extracellular_volume)
        if labels is None:
            return reactions_half_step(state, m, h, p, xp=xp, volumes=volumes)
        return reactions_half_step(state, m, h, p, xp=xp, labels=labels, volumes=volumes)

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
        result["total"] = (
            result["total"] + entity_sum(cell, axis=1, xp=xp) + entity_sum(outside, axis=1, xp=xp)
        )
        result["energy"] = (
            result["energy"]
            + entity_sum(row.reaction_standard_energy_pJ, axis=None, xp=xp)
            + entity_sum(row.reaction_outside_standard_energy_pJ, axis=None, xp=xp)
            + entity_sum(row.reaction_dissipated_energy_pJ, axis=None, xp=xp)
            + entity_sum(row.reaction_outside_dissipated_energy_pJ, axis=None, xp=xp)
            - entity_sum(row.reaction_work_pJ, axis=None, xp=xp)
            - entity_sum(row.reaction_outside_work_pJ, axis=None, xp=xp)
        )
        return result, {}

    def observe(self, row, state, control, p, view, model, spec):
        columns = {k: getattr(state, k) for k in self.STATE_AXES}
        multiplier = np.asarray(control.reaction_multiplier)
        net = network(p, multiplier, xp=np, volumes=row_volumes(self, view, model))
        rates = route_rates(node_amounts(state, p, xp=np), net, p, xp=np)
        columns["reaction_rate_fmol_per_s"] = np.asarray(rates.rate)
        columns["reaction_affinity_RT"] = np.where(net.passive, rates.affinity, 0.0)
        return columns

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        """The moved amounts in the material ledgers and the absolute terms of every booking in
        the energy ledger's; every term is zero without reactions, so the bounds are then @3's."""
        cell = row.reaction_produced_fmol + row.reaction_consumed_fmol
        outside = row.reaction_outside_produced_fmol + row.reaction_outside_consumed_fmol
        magnitudes[0] = magnitudes[0] + cell
        magnitudes[1] = magnitudes[1] + outside
        magnitudes[2] = (
            magnitudes[2] + entity_sum(cell, axis=1, xp=xp) + entity_sum(outside, axis=1, xp=xp)
        )
        energy = entity_sum(row.reaction_energy_magnitude_pJ, axis=None, xp=xp) + entity_sum(
            row.reaction_outside_energy_magnitude_pJ, axis=None, xp=xp
        )
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes
