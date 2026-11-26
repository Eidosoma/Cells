"""Operator cells.operator.integer_unit_population@1: a low-count population of integer units in membrane patches,
whose stochastic events read the composite's finite pools and whose activity moves material between
them (FR-43 part 3, option B; D315).

docs/FR43_PART3_BUILD_PLAN.md; the physics is docs/FR43_SHARED_INVENTORIES_DESIGN.md §3.1 (branch
fr43-design). A few channels, transporters or machines in a membrane switch between integer states
(free subunits, assembled units) by stochastic events; each assembled unit conducts a neutral
species across its patch, and the event rates read the species' current concentrations. Between
events the counts are constants and the pools follow ordinary differential equations: a
piecewise-deterministic Markov process (Davis 1984, from memory), simulated exactly by the hybrid
next-reaction rule (Haseltine and Rawlings 2002; Alfonsi et al. 2005; from memory).

**Declaration.**
- `species`: the species it moves, with their identity (species_common.parse_species: neutral and
  impermeant on @3's own routes); `read_species`: species rows it only reads (parse_read_species).
- `seed`: the streams' seed, an integer in [0, 2**32) (numerics/counter_streams.py).
- `trace_events`: the trace's capacity T >= 0 per site: the first T events are recorded.
- `populations`, each with:
  - `unit_states`: [{id, subunits}], each with an integer subunit weight w >= 1;
  - `channels`: [{id, reactants, products, rate_per_s, read}], integer stoichiometry over the unit
    states (each at most MAX_ORDER, at least one reactant), conserving the subunits Σ w n; rate k
    >= 0 (1/s); read null or {species, at}: one species row at the site's cell ("cell") or outside
    node ("outside");
  - `transfers`: [{id, species, conductance_pL_per_s}], one per moved species, with a conductance
    g >= 0 (pL/s) per unit of each state;
  - `division`: "independent_segregation", or null where none of its sites divides;
  - `sites`: [{id, patch, initial_counts}], an isolated cluster of the population's units in a
    declared patch whose outside node is finite. Units interact only within their site, and a patch
    may hold several sites.
- `divisions`: [{parent, daughters: [first, second]}], site maps for the composite's division.

**The law**, per site s on patch m (cell c, outside node o, declared volumes V_c and V_o):
- propensity a_j = k_j Π_k ff(n_k, r_jk) φ_j, with ff(n, r) = n!/(n - r)! (ordered tuples, the
  convention of cells.reaction.stochastic_mass_action@1), and φ_j = c/(1 mM) of the declared read, else 1;
  a0 = Σ_j a_j, a serial left fold in declared order;
- the transfer of each route, J = G (n_c/V_c - n_o/V_o) fmol/s from cell to node, G = Σ_k g_k n_k:
  passive and linear. The units carry no free energy (a declared limit, as the gene unit's
  machines); the pools keep @3's terms;
- the clock H, integrated from the last event; event k fires at H = E_k = -ln u1_k, its channel the
  first j with c_j > min(u2_k a0, nextafter(a0, 0)) (c_j the partial sums at the crossing state, the
  exact kernel's rule); then N <- N - r_j + p_j, H <- 0. (u1_k, u2_k) is draw k of the site's events
  stream, counter-based (counter_streams), so a site's first event takes counter 0 whenever it
  occurs.

**The half-step** (SPLIT, kept split under RK4) advances only its own variables over h, every other
row frozen, so it is exact: between events the two pools of a route relax in closed form,
u(τ) = u0 e^{-λτ}, λ = G (1/V_c + 1/V_o), moved m(τ) = -u0 expm1(-λτ) V_c V_o/(V_c + V_o), and a
read row on one of the site's routes follows c(τ) = c0 + δ (1 - e^{-λτ}); any other read row is
constant within the half-step. So H(τ) = Σ_j a_j-coefficients [c0 τ + δ τ q(λτ)], q(x) =
1 - (1 - e^{-x})/x, is closed form. A site whose reads are all constant within the half-step has
H(τ) = a0 τ and fires at τ* = (E - H)/a0 exactly; any other locates the crossing by bisection on the
monotone H to rounding (BISECTION_STEPS). The pools move to the crossing, the event fires, and the
rest of the half-step runs at the new counts, up to EVENT_CAP events per half-step, in a fixed
trip of EVENT_CAP + 1 segments (masked no-ops once a site is done, so a batch's worlds run in step
on a GPU; a trip with no site running is skipped on the scalar path; the bisection's trip is fixed
too): a site that would need more refuses the step (never
truncated), and the definition refuses dt a0,max > 1 where a0,max is bounded
(check_hazard_bound). The time of an event is the operator's compensated clock at
the half-step's start (Neumaier's sum of its h's) plus the offset inside it. The splitting against
other writers of a row it reads or moves (turnover, exchange, @3's step) is Strang's, O(dt^2) in
the event times; with nothing else moving its rows, the event times are exact at every dt.

**Stages.** Sites whose rows meet, one of them moving a row the other moves or reads while both
can be live (stages: a parent and its daughters never meet, rows both only read do not), run in
different stages. With one stage the half-step is the exact flow above. With several it is a
palindrome of exact stages, the first stages over h/2 forward, the last over h, the first back over
h/2 (stage_plan), so coupled sites are split at second order, as any other co-writers are.

**Energy.** Each move's heat is -ΔF of the two pools, formed as m ln(c_c'/c_o') + n_c φ(-m/n_c) +
n_o φ(m/n_o) with φ(x) = x - log1p(x), every term >= 0 by construction (m and ln(c_c'/c_o') share
u0's sign), times 1e-3 RT (pJ/fmol): a monotone heat. The rounding magnitudes are @3's absolute
terms of each move (adapter.species_chemical_magnitude_pJ).

**Division** (the composite's lifecycle hook, D315; DIVIDES_OWNED): at a retiring operator's
division, `independent_segregation` sends each unit of a parent site to the first daughter site with
probability f, the partition's area fraction of the site's patch (maps["membrane_slot"]), drawn from
the parent site's partition stream at counter 0, one uniform per unit in declared unit order (state
order, then index; u < f: the first). Binomial partitioning, the standard model of random
segregation of low-copy components (Huh and Paulsson 2011, from memory). The daughters' counts sum
to the parent's exactly, in integers; the parent is zeroed, and a signed record books every move,
so each site's subunit ledger stays exact. The pools divide by the partition's own rule. A
daughter site keeps H = 0 and its own counter-0 threshold (exact by the strong Markov property at
a fixed time); the parent's clock is retired with it. exact_fraction and Protocol G belong to the
assembly family and are untouched.

**Reads beside a closer.** The patch mask membrane_active and the node anchors are current reads
at stage split (C1's fallback: no changer, no view, the declared values). A closed site (a pending
daughter, the retired parent) is selected idle: no rate, no move, its clock frozen, so close()'s
zero anchors are never read. Declared cell anchors are read at live sites only, where close()
leaves them as declared (amount_reference is not a view field). Volumes are fixed reads, so water
and the lumens are refused (version 1).

**Refused at the definition**, each with its reason: a charged moved species, or one with an @3
route; an unknown read species; a patch on a held bath; a malformed or non-conserving channel; a
reactant order above MAX_ORDER; more than MAX_SUBUNITS subunits at a site; a moved row that a D152
reaction or the gene unit
writes, or that an in-step process moves; replacement and every event that replaces amounts; a
provider or closer of the activity masks that does not divide through the composite's lifecycle
(insertion@1 and @2 among them), and a composite without the hook; a label owner; units at a site
whose cell is born later; a dividing patch whose sites lack site maps, maps that do not follow the
partition's patch maps, a dividing population without its token; dt a0,max > 1 where bounded; more
than the species cap. At run time: non-finite values, a pool that would not stay positive, the
event cap, and a division whose daughters disagree with the maps.

**Idle:** no site, statically idle. A world without the operator traces nothing of it (D148).
"""

import math
from dataclasses import dataclass
from types import MappingProxyType

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite_spec
from cells.definitions.spec_values import identifier
from cells.definitions.specs import ConfigError, _fields
from cells.models import pump_composite_adapter as adapter
from cells.numerics import counter_streams as streams
from cells.numerics.species_sums import entity_sum
from cells.operators import species_common as common
from cells.operators.contract import Operator, Read
from cells.registry import species_registry

LAW_ID = "cells.operator.integer_unit_population@1"
STEP_ID = "located_events_exact_transfer_half_steps@1"
DIVISION_TOKENS = ("independent_segregation",)
READ_AT = ("cell", "outside")
MAX_ORDER = 4  # A channel's reactant stoichiometry per unit state.
MAX_SUBUNITS = 1024  # Per site: the low-count scope, and the partition draw's block.
EVENT_CAP = 64  # Events per site per half-step; one more refuses the step.
BISECTION_STEPS = 64  # Halvings of the half-step: below one ulp of it.
HAZARD_BOUND = 1.0  # The definition refuses dt a0,max above it (bounded sites).
STANDARD_mM = 1.0  # A read's concentration unit: phi = c / (1 mM).
Q_SERIES = 20  # Terms of q(x) below x = 1.
PHI_SERIES = 40  # Terms of x - log1p(x) below |x| = 1/4.
PHI_SWITCH = 0.25
REPLACEMENT_LAWS = ("cells.operator.scheduled_cell_replacement@1", "cells.operator.scheduled_cell_replacement@2")
GENE_UNIT_LAW = "cells.operator.templated_polymerisation@1"
REACTIONS_LAW = "cells.operator.local_species_reactions@1"
LEDGER_FLOOR_UNITS = 0.0  # The subunit ledger is exact, in integers.

STATE_AXES = {
    "integer_counts": ["integer_site", "integer_state"],  # int64
    "integer_hazard": ["integer_site"],  # H since the last event.
    "integer_threshold": ["integer_site"],  # E = -ln u1 of the next event.
    "integer_events": ["integer_site"],  # int64: the events fired, the next event's counter.
    "integer_channel_events": ["integer_site", "integer_channel"],  # int64
    "integer_clock_s": ["integer_site"],  # Neumaier's sum of the half-steps' h ...
    "integer_clock_carry_s": ["integer_site"],  # ... and its compensation.
    "integer_transferred_fmol": ["integer_site", "integer_route"],  # Cell to node positive.
    "integer_transfer_dissipated_energy_pJ": ["integer_site"],
    "integer_energy_magnitude_pJ": ["integer_site"],
    "integer_divided_units": ["integer_site", "integer_state"],  # int64, signed.
    "integer_trace_time_s": ["integer_site", "integer_trace"],
    "integer_trace_channel": ["integer_site", "integer_trace"],  # int64; -1: not recorded.
    "integer_trace_cell_fmol": ["integer_site", "integer_trace", "integer_route"],
    "integer_trace_node_fmol": ["integer_site", "integer_trace", "integer_route"],
}
STATE_DTYPES = {
    "integer_counts": "int64",
    "integer_events": "int64",
    "integer_channel_events": "int64",
    "integer_divided_units": "int64",
    "integer_trace_channel": "int64",
}
LAYOUT_FIELDS = (
    "integer_site_cell",  # [site] int64
    "integer_site_node",  # [site] int64: the patch's outside node.
    "integer_site_patch",  # [site] int64
    "integer_weights",  # [site, state] int64 (0: a padded state)
    "integer_initial_counts",  # [site, state] int64
    "integer_reactants",  # [site, channel, state] int64
    "integer_change",  # [site, channel, state] int64: products - reactants
    "integer_rate_per_s",  # [site, channel] (0: a padded channel)
    "integer_read_at",  # [site, channel] int64: 0 none, 1 cell, 2 outside node
    "integer_read_species",  # [site, channel] int64
    "integer_read_route",  # [site, channel] int64: the route whose row it reads, -1 none
    "integer_route_species",  # [site, route] int64
    "integer_route_present",  # [site, route] bool
    "integer_conductance_pL_per_s",  # [site, route, state]
    "integer_linear",  # [site] bool: every read constant within a half-step
    "integer_events_key",  # [site, 2] int64: the events stream's key data
    "integer_partition_key",  # [site, 2] int64: the partition stream's key data
    "integer_map_parent",  # [map] int64
    "integer_map_daughters",  # [map, 2] int64
    "integer_block",  # [W]: its shape is the partition draw's block (static)
    "integer_site_stage",  # [site] int64: its stage of a half-step (stages)
    "integer_stages",  # [C]: its shape is the number of stages (static)
)
LEDGERS = ("integer_subunits",)
LEDGER_DIAGNOSTICS = ("integer_subunits_error",)
LEDGER_MESSAGE = "Integer unit population accounting failed: "


# ------------------------------------------------------------------ the declaration


@dataclass(frozen=True)
class UnitState:
    id: str
    subunits: int


@dataclass(frozen=True)
class Channel:
    id: str
    reactants: tuple  # ((state id, count), ...), in the population's state order, nonzero only
    products: tuple
    rate_per_s: float
    read: tuple | None  # (species, "cell" | "outside")


@dataclass(frozen=True)
class Transfer:
    id: str
    species: str
    conductance_pL_per_s: tuple  # ((state id, g), ...), every state


@dataclass(frozen=True)
class Site:
    id: str
    patch: str
    cell: str
    node: str
    initial_counts: tuple  # ((state id, count), ...), every state


@dataclass(frozen=True)
class Population:
    id: str
    unit_states: tuple
    channels: tuple
    transfers: tuple
    division: str | None
    sites: tuple


@dataclass(frozen=True)
class SiteMap:
    parent: str
    daughters: tuple  # (first recipient, second)


@dataclass(frozen=True)
class IntegerUnitPopulation:
    law: str
    species: tuple
    read_species: tuple
    seed: int
    trace_events: int
    populations: tuple
    divisions: tuple


def _count(value, what, *, low=0, high=None):
    if type(value) is not int or value < low or (high is not None and value > high):
        bound = f" and at most {high}" if high is not None else ""
        raise ConfigError(f"{LAW_ID}: {what} is an integer of at least {low}{bound}")
    return value


def _rate(value, what):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ConfigError(f"{LAW_ID}: {what} is a finite number >= 0")
    return float(value)


def _stoichiometry(raw, states, what):
    """((state id, count), ...) over the declared states, in their order, positive counts only."""
    if type(raw) is not dict:
        raise ConfigError(f"{LAW_ID}: {what} is an object {{unit state: count}}")
    for key in raw:
        if key not in states:
            raise ConfigError(f"{LAW_ID}: {what} names an undeclared unit state {key!r}")
    out = []
    for state in states:
        if state in raw:
            n = _count(raw[state], f"{what}'s count of {state}", low=0, high=MAX_ORDER)
            if n:
                out.append((state, n))
    return tuple(out)


def _per_state(raw, states, what, parse):
    if type(raw) is not dict or set(raw) != set(states):
        raise ConfigError(f"{LAW_ID}: {what} gives a value for every unit state {list(states)}")
    return tuple((state, parse(raw[state], f"{what} of {state}")) for state in states)


def parse_population(raw, base, moved, readable):
    _fields(raw, {"id", "unit_states", "channels", "transfers", "division", "sites"}, "population")
    name = identifier(raw["id"])
    if type(raw["unit_states"]) is not list or not raw["unit_states"]:
        raise ConfigError(f"{LAW_ID}: population {name} lists its unit states")
    states = []
    for entry in raw["unit_states"]:
        _fields(entry, {"id", "subunits"}, "unit state")
        states.append(
            UnitState(identifier(entry["id"]), _count(entry["subunits"], "a subunit weight", low=1))
        )
    ids = [s.id for s in states]
    if len(set(ids)) != len(ids):
        raise ConfigError(f"{LAW_ID}: population {name}'s unit-state IDs are unique")
    weight = {s.id: s.subunits for s in states}
    if type(raw["channels"]) is not list:
        raise ConfigError(f"{LAW_ID}: population {name} lists its channels")
    channels = []
    for entry in raw["channels"]:
        _fields(entry, {"id", "reactants", "products", "rate_per_s", "read"}, "channel")
        cid = identifier(entry["id"])
        reactants = _stoichiometry(entry["reactants"], ids, f"channel {cid}'s reactants")
        products = _stoichiometry(entry["products"], ids, f"channel {cid}'s products")
        if not reactants:
            raise ConfigError(
                f"{LAW_ID}: channel {cid} has a reactant: a channel conserves the subunits, so it "
                "converts units, never makes them from none"
            )
        before = sum(weight[s] * n for s, n in reactants)
        after = sum(weight[s] * n for s, n in products)
        if before != after:
            raise ConfigError(
                f"{LAW_ID}: channel {cid} conserves the subunits (reactants {before}, products "
                f"{after})"
            )
        if dict(reactants) == dict(products):
            raise ConfigError(f"{LAW_ID}: channel {cid} changes the counts")
        read = entry["read"]
        if read is not None:
            _fields(read, {"species", "at"}, "channel read")
            if read["species"] not in moved | readable:
                raise ConfigError(
                    f"{LAW_ID}: channel {cid} reads {read['species']!r}, which is neither a "
                    "listed species nor a listed read species"
                )
            if read["at"] not in READ_AT:
                raise ConfigError(f"{LAW_ID}: a read is at one of {READ_AT}")
            read = (read["species"], read["at"])
        channels.append(
            Channel(cid, reactants, products, _rate(entry["rate_per_s"], f"{cid}'s rate"), read)
        )
    if not channels or len({c.id for c in channels}) != len(channels):
        raise ConfigError(f"{LAW_ID}: population {name} has channels with unique IDs")
    if type(raw["transfers"]) is not list:
        raise ConfigError(f"{LAW_ID}: population {name} lists its transfers")
    transfers = []
    for entry in raw["transfers"]:
        _fields(entry, {"id", "species", "conductance_pL_per_s"}, "transfer")
        tid = identifier(entry["id"])
        if entry["species"] not in moved:
            raise ConfigError(f"{LAW_ID}: transfer {tid} moves {entry['species']!r}, not listed")
        g = _per_state(entry["conductance_pL_per_s"], ids, f"transfer {tid}'s conductance", _rate)
        transfers.append(Transfer(tid, entry["species"], g))
    if len({t.id for t in transfers}) != len(transfers):
        raise ConfigError(f"{LAW_ID}: population {name}'s transfer IDs are unique")
    if len({t.species for t in transfers}) != len(transfers):
        raise ConfigError(f"{LAW_ID}: population {name} moves each species by one transfer")
    division = raw["division"]
    if division is not None and division not in DIVISION_TOKENS:
        raise ConfigError(
            f"{LAW_ID}: a population's division token is one of {DIVISION_TOKENS} or null "
            "(exact_fraction is the assembly family's)"
        )
    m = base.model
    patches = {p.id: p for p in m.membranes}
    outside = {c.id: c for c in m.extracellular}
    if type(raw["sites"]) is not list or not raw["sites"]:
        raise ConfigError(f"{LAW_ID}: population {name} lists its sites")
    sites = []
    for entry in raw["sites"]:
        _fields(entry, {"id", "patch", "initial_counts"}, "site")
        sid = identifier(entry["id"])
        if entry["patch"] not in patches:
            raise ConfigError(f"{LAW_ID}: site {sid} is on an undeclared patch {entry['patch']!r}")
        patch = patches[entry["patch"]]
        if outside[patch.outside].reservoir:
            raise ConfigError(
                f"{LAW_ID}: site {sid}'s patch {patch.id} faces a held bath ({patch.outside}): "
                "its transfers join two finite pools"
            )
        counts = _per_state(
            entry["initial_counts"],
            ids,
            f"site {sid}'s initial counts",
            lambda v, what: _count(v, what, low=0),
        )
        total = sum(weight[s] * n for s, n in counts)
        if total > MAX_SUBUNITS:
            raise ConfigError(
                f"{LAW_ID}: site {sid} holds {total} subunits, above {MAX_SUBUNITS} (the low-count "
                "scope)"
            )
        sites.append(Site(sid, patch.id, patch.inside, patch.outside, counts))
    return Population(
        name, tuple(states), tuple(channels), tuple(transfers), division, tuple(sites)
    )


def parse_declaration(raw, base):
    keys = {"law", "species", "read_species", "seed", "trace_events", "populations", "divisions"}
    _fields(raw, keys, "integer unit population")
    if raw["law"] != LAW_ID:
        raise ConfigError("An integer unit population requires law " + LAW_ID)
    species = common.parse_species(raw["species"], base, LAW_ID, limit=": it moves neutral rows")
    read_species = common.parse_read_species(raw["read_species"], base, LAW_ID)
    moved = {s.id for s in species}
    readable = {s.id for s in read_species}
    if moved & readable:
        raise ConfigError(f"{LAW_ID}: a moved species is not listed again as a read species")
    try:
        seed = streams.check_seed(raw["seed"])
    except ValueError as error:
        raise ConfigError(f"{LAW_ID}: {error}") from None
    trace = _count(raw["trace_events"], "trace_events", low=0, high=65536)
    if type(raw["populations"]) is not list or not raw["populations"]:
        raise ConfigError(f"{LAW_ID} lists its populations")
    populations = tuple(parse_population(p, base, moved, readable) for p in raw["populations"])
    if len({p.id for p in populations}) != len(populations):
        raise ConfigError(f"{LAW_ID}: population IDs are unique")
    sites = [s for p in populations for s in p.sites]
    if len({s.id for s in sites}) != len(sites):
        raise ConfigError(f"{LAW_ID}: site IDs are unique across populations")
    population_of = {s.id: p for p in populations for s in p.sites}
    if type(raw["divisions"]) is not list:
        raise ConfigError(f"{LAW_ID} lists its site maps (divisions) explicitly")
    maps = []
    for entry in raw["divisions"]:
        _fields(entry, {"parent", "daughters"}, "site map")
        daughters = entry["daughters"]
        if type(daughters) is not list or len(daughters) != 2:
            raise ConfigError(f"{LAW_ID}: a site map names its two daughter sites")
        names = (entry["parent"], *daughters)
        for site in names:
            if site not in population_of:
                raise ConfigError(f"{LAW_ID}: a site map names an undeclared site {site!r}")
        if len(set(names)) != 3:
            raise ConfigError(f"{LAW_ID}: a site map's parent and daughters are distinct")
        if len({population_of[s].id for s in names}) != 1:
            raise ConfigError(f"{LAW_ID}: a site map stays within one population")
        if population_of[entry["parent"]].division is None:
            raise ConfigError(
                f"{LAW_ID}: site {entry['parent']} divides, so its population declares its "
                f"division token ({DIVISION_TOKENS[0]})"
            )
        maps.append(SiteMap(entry["parent"], tuple(daughters)))
    parents = [m.parent for m in maps]
    children = [d for m in maps for d in m.daughters]
    if len(set(parents)) != len(parents) or len(set(children)) != len(children):
        raise ConfigError(
            f"{LAW_ID}: a site is the parent of one map at most and a daughter of one"
        )
    return IntegerUnitPopulation(
        LAW_ID, species, read_species, seed, trace, populations, tuple(maps)
    )


def declaration_to_dict(declaration):
    if type(declaration) is not IntegerUnitPopulation:
        raise ConfigError("Require an explicit immutable integer unit population declaration")

    def population(p):
        return dict(
            id=p.id,
            unit_states=[dict(id=s.id, subunits=s.subunits) for s in p.unit_states],
            channels=[
                dict(
                    id=c.id,
                    reactants=dict(c.reactants),
                    products=dict(c.products),
                    rate_per_s=c.rate_per_s,
                    read=None if c.read is None else dict(species=c.read[0], at=c.read[1]),
                )
                for c in p.channels
            ],
            transfers=[
                dict(id=t.id, species=t.species, conductance_pL_per_s=dict(t.conductance_pL_per_s))
                for t in p.transfers
            ],
            division=p.division,
            sites=[
                dict(id=s.id, patch=s.patch, initial_counts=dict(s.initial_counts)) for s in p.sites
            ],
        )

    return dict(
        law=declaration.law,
        species=common.species_to_dict(declaration.species),
        read_species=common.species_to_dict(declaration.read_species),
        seed=declaration.seed,
        trace_events=declaration.trace_events,
        populations=[population(p) for p in declaration.populations],
        divisions=[
            dict(parent=m.parent, daughters=list(m.daughters)) for m in declaration.divisions
        ],
    )


def sites_of(declaration):
    """((population, site), ...) in declared order: the site axis."""
    return tuple((p, s) for p in declaration.populations for s in p.sites)


def site_rows(population, site):
    """(moved rows, read rows) of a site: {(species, node kind, node id)}."""
    moved = set()
    for t in population.transfers:
        moved |= {(t.species, "cell", site.cell), (t.species, "outside", site.node)}
    read = set()
    for c in population.channels:
        if c.read is not None:
            species, at = c.read
            read.add((species, at, site.cell if at == "cell" else site.node))
    return moved, read


def conflicts(a, b):
    """Whether two sites' rows meet where one of them moves the row: they then run in different
    stages of a half-step (stages). Rows both only read do not meet."""
    moved_a, read_a = a
    moved_b, read_b = b
    return bool(moved_a & moved_b or moved_a & read_b or read_a & moved_b)


def stages(declaration, lives=None):
    """Each site's stage [site], greedy in declared order: the first stage holding no site whose
    rows meet its own (conflicts) while both can be live. Sites whose cells' living intervals are
    disjoint (a parent and its daughters) never meet. One stage: every site independent."""
    lives = lives or {}
    pairs = sites_of(declaration)
    rows = [site_rows(p, s) for p, s in pairs]

    def interval(site):
        birth, retirement = lives.get(site.cell, (None, None))
        return (
            -math.inf if birth is None else birth,
            math.inf if retirement is None else retirement,
        )

    spans = [interval(s) for _, s in pairs]
    movers, readers = {}, {}  # {row: earlier sites that move it, or read it}
    out = []
    for i, (moved, read) in enumerate(rows):
        candidates = {j for row in moved for j in (*movers.get(row, ()), *readers.get(row, ()))}
        candidates |= {j for row in read for j in movers.get(row, ())}
        taken = {
            out[j] for j in candidates if spans[i][0] < spans[j][1] and spans[j][0] < spans[i][1]
        }
        out.append(next(c for c in range(len(taken) + 1) if c not in taken))
        for row in moved:
            movers.setdefault(row, []).append(i)
        for row in read:
            readers.setdefault(row, []).append(i)
    return out


# ------------------------------------------------------------------ binding


def dimensions(declaration):
    """(sites, states K, channels J, routes R, trace T, block W): the static axis sizes."""
    pairs = sites_of(declaration)
    k = max(len(p.unit_states) for p in declaration.populations)
    j = max(len(p.channels) for p in declaration.populations)
    r = max(1, max(len(p.transfers) for p in declaration.populations))  # A padded route at least.
    w = max(
        sum(u.subunits * n for u, (_, n) in zip(p.unit_states, site.initial_counts, strict=True))
        for p, site in pairs
    )
    return len(pairs), k, j, r, declaration.trace_events, max(w, 1)


def bind(spec, declaration):
    m = spec.model
    staged = stages(declaration, lives(spec))
    species = list(m.species_ids)
    cells = [c.id for c in m.cells]
    outside = [c.id for c in m.extracellular]
    patches = [p.id for p in m.membranes]
    pairs = sites_of(declaration)
    n, k, j, r, t, w = dimensions(declaration)
    index = {site.id: i for i, (_, site) in enumerate(pairs)}
    layout = dict(
        integer_site_cell=np.zeros(n, dtype=np.int64),
        integer_site_node=np.zeros(n, dtype=np.int64),
        integer_site_patch=np.zeros(n, dtype=np.int64),
        integer_weights=np.zeros((n, k), dtype=np.int64),
        integer_initial_counts=np.zeros((n, k), dtype=np.int64),
        integer_reactants=np.zeros((n, j, k), dtype=np.int64),
        integer_change=np.zeros((n, j, k), dtype=np.int64),
        integer_rate_per_s=np.zeros((n, j)),
        integer_read_at=np.zeros((n, j), dtype=np.int64),
        integer_read_species=np.zeros((n, j), dtype=np.int64),
        integer_read_route=-np.ones((n, j), dtype=np.int64),
        integer_route_species=np.zeros((n, r), dtype=np.int64),
        integer_route_present=np.zeros((n, r), dtype=bool),
        integer_conductance_pL_per_s=np.zeros((n, r, k)),
        integer_linear=np.ones(n, dtype=bool),
        integer_events_key=np.zeros((n, 2), dtype=np.int64),
        integer_partition_key=np.zeros((n, 2), dtype=np.int64),
        integer_map_parent=np.asarray(
            [index[x.parent] for x in declaration.divisions], dtype=np.int64
        ),
        integer_map_daughters=np.asarray(
            [[index[d] for d in x.daughters] for x in declaration.divisions], dtype=np.int64
        ).reshape(len(declaration.divisions), 2),
        integer_block=np.zeros(w),
        integer_site_stage=np.asarray(staged, dtype=np.int64),
        integer_stages=np.zeros(max(staged, default=0) + 1),
    )
    for i, (population, site) in enumerate(pairs):
        states = [s.id for s in population.unit_states]
        layout["integer_site_cell"][i] = cells.index(site.cell)
        layout["integer_site_node"][i] = outside.index(site.node)
        layout["integer_site_patch"][i] = patches.index(site.patch)
        for q, s in enumerate(population.unit_states):
            layout["integer_weights"][i, q] = s.subunits
        for q, (_, count) in enumerate(site.initial_counts):
            layout["integer_initial_counts"][i, q] = count
        routes = {}
        for x, transfer in enumerate(population.transfers):
            layout["integer_route_species"][i, x] = species.index(transfer.species)
            layout["integer_route_present"][i, x] = True
            for q, (_, g) in enumerate(transfer.conductance_pL_per_s):
                layout["integer_conductance_pL_per_s"][i, x, q] = g
            routes[transfer.species] = x
        for y, channel in enumerate(population.channels):
            for state, count in channel.reactants:
                layout["integer_reactants"][i, y, states.index(state)] = count
                layout["integer_change"][i, y, states.index(state)] -= count
            for state, count in channel.products:
                layout["integer_change"][i, y, states.index(state)] += count
            layout["integer_rate_per_s"][i, y] = channel.rate_per_s
            if channel.read is not None:
                name, at = channel.read
                layout["integer_read_at"][i, y] = 1 + READ_AT.index(at)
                layout["integer_read_species"][i, y] = species.index(name)
                if name in routes:
                    layout["integer_read_route"][i, y] = routes[name]
                    layout["integer_linear"][i] = False
    layout["integer_events_key"] = streams.sites_key_data(declaration.seed, n, "events")
    layout["integer_partition_key"] = streams.sites_key_data(declaration.seed, n, "partition")
    counts = layout["integer_initial_counts"].copy()
    first = np.asarray(
        streams.site_uniforms(
            jnp.asarray(layout["integer_events_key"]), jnp.zeros(n, dtype=jnp.int64), 2
        )
    )
    state = dict(
        integer_counts=counts,
        integer_hazard=np.zeros(n),
        integer_threshold=-np.log(first[:, 0]) if n else np.zeros(0),
        integer_events=np.zeros(n, dtype=np.int64),
        integer_channel_events=np.zeros((n, j), dtype=np.int64),
        integer_clock_s=np.zeros(n),
        integer_clock_carry_s=np.zeros(n),
        integer_transferred_fmol=np.zeros((n, r)),
        integer_transfer_dissipated_energy_pJ=np.zeros(n),
        integer_energy_magnitude_pJ=np.zeros(n),
        integer_divided_units=np.zeros((n, k), dtype=np.int64),
        integer_trace_time_s=np.zeros((n, t)),
        integer_trace_channel=-np.ones((n, t), dtype=np.int64),
        integer_trace_cell_fmol=np.zeros((n, t, r)),
        integer_trace_node_fmol=np.zeros((n, t, r)),
    )
    return state, layout


# ------------------------------------------------------------------ the law


def falling_factorial(n, r):
    """ff(n, r) = n!/(n - r)! for int64 counts n and orders r <= MAX_ORDER, as float64: 0 where
    r > n, 1 where r = 0 (the product of the r factors n, n - 1, ...; exact in float64)."""
    out = jnp.ones(jnp.broadcast_shapes(n.shape, r.shape))
    for i in range(MAX_ORDER):
        factor = jnp.maximum(n - i, 0).astype(jnp.float64)
        out = jnp.where(i < r, out * factor, out)
    return out


def q_of(x):
    """q(x) = 1 - (1 - e^{-x})/x for x >= 0: its series sum_{n>=1} (-1)^{n+1} x^n/(n+1)! below
    x = 1 (Horner, Q_SERIES terms), the direct form above, where nothing cancels."""
    small = jnp.minimum(x, 1.0)
    acc = jnp.full_like(x, (-1.0) ** (Q_SERIES + 1) / math.factorial(Q_SERIES + 1))
    for n in range(Q_SERIES - 1, 0, -1):
        acc = (-1.0) ** (n + 1) / math.factorial(n + 1) + small * acc
    series = small * acc
    direct = 1.0 + jnp.expm1(-x) / jnp.where(x > 0, x, 1.0)
    return jnp.where(x < 1.0, series, direct)


def phi_of(x):
    """x - log1p(x) >= 0 for x > -1: x^2 sum_{m>=0} (-1)^m x^m/(m + 2) below |x| = PHI_SWITCH
    (Horner, PHI_SERIES terms), the direct form above, where nothing cancels."""
    small = jnp.clip(x, -PHI_SWITCH, PHI_SWITCH)
    acc = jnp.full_like(x, (-1.0) ** (PHI_SERIES - 1) / (PHI_SERIES + 1))
    for m in range(PHI_SERIES - 2, -1, -1):
        acc = (-1.0) ** m / (m + 2) + small * acc
    series = small * small * acc
    return jnp.where(jnp.abs(x) < PHI_SWITCH, series, x - jnp.log1p(x))


def _gather(p, state, view):
    """The site's rows at the half-step's start: (live [S], V_c, V_o [S], n_c, n_o [S, R] at the
    routes' rows, read concentrations c_read [S, J] of rows no route of the site moves)."""
    patch = p.integer_site_patch
    mask = p.membrane_active if view is None else view.membrane_active
    node_reference = (
        p.extracellular_amount_reference if view is None else view.extracellular_amount_reference
    )
    live = mask[patch]
    cell, node = p.integer_site_cell, p.integer_site_node
    vc, vo = p.volume[cell], p.extracellular_volume[node]
    sp = p.integer_route_species
    on = p.integer_route_present & live[:, None]
    nc = p.amount_reference[sp, cell[:, None]] + state.amount_increment[sp, cell[:, None]]
    no = node_reference[sp, node[:, None]] + state.extracellular_amount_increment[sp, node[:, None]]
    nc, no = jnp.where(on, nc, 1.0), jnp.where(on, no, 1.0)
    rs, at = p.integer_read_species, p.integer_read_at
    read_c = p.amount_reference[rs, cell[:, None]] + state.amount_increment[rs, cell[:, None]]
    read_o = (
        node_reference[rs, node[:, None]] + state.extracellular_amount_increment[rs, node[:, None]]
    )
    c_read = jnp.where(
        at == 1, read_c / vc[:, None], jnp.where(at == 2, read_o / vo[:, None], STANDARD_mM)
    )
    c_read = jnp.where(live[:, None], c_read, STANDARD_mM)
    return live, vc, vo, nc, no, c_read


def _flow(nc, no, counts, vc, vo, p):
    """(λ, u0, scale) per route [S, R] at counts: the closed-form relaxation's rate, the initial
    concentration difference and V_c V_o / (V_c + V_o)."""
    g = entity_sum(
        p.integer_conductance_pL_per_s * counts[:, None, :].astype(jnp.float64), axis=2, xp=jnp
    )
    lam = g * (1.0 / vc + 1.0 / vo)[:, None]
    u0 = nc / vc[:, None] - no / vo[:, None]
    scale = (vc * vo / (vc + vo))[:, None]
    return lam, u0, scale


def _moved(lam, u0, scale, tau):
    """The amount moved cell to node over tau [S] (closed form), [S, R]."""
    return -u0 * jnp.expm1(-lam * tau[:, None]) * scale


def _read_paths(lam, u0, vc, vo, nc, no, c_read, p):
    """(c0, δ, λ_j) [S, J]: each channel's read concentration c(τ) = c0 + δ (1 - e^{-λ_j τ})."""
    route = jnp.maximum(p.integer_read_route, 0)
    on_route = p.integer_read_route >= 0
    at_cell = p.integer_read_at == 1
    take = lambda a: jnp.take_along_axis(a, route, axis=1)  # noqa: E731
    c_cell, c_node = take(nc) / vc[:, None], take(no) / vo[:, None]
    u = take(u0)
    weight_cell = (vo / (vc + vo))[:, None]
    weight_node = (vc / (vc + vo))[:, None]
    c0 = jnp.where(on_route, jnp.where(at_cell, c_cell, c_node), c_read)
    delta = jnp.where(on_route, jnp.where(at_cell, -u * weight_cell, u * weight_node), 0.0)
    lam_j = jnp.where(on_route, take(lam), 0.0)
    return c0, delta, lam_j


def _base(counts, p):
    """k_j Π_k ff(n_k, r_jk) [S, J]."""
    ff = falling_factorial(counts[:, None, :], p.integer_reactants)
    return p.integer_rate_per_s * jnp.prod(ff, axis=2)


def _hazard(base, c0, delta, lam_j, tau):
    """H's increase over tau [S]: Σ_j base_j [c0 τ + δ τ q(λ_j τ)] / (1 mM), a left fold."""
    t = tau[:, None]
    terms = base * (c0 * t + delta * t * q_of(lam_j * t)) / STANDARD_mM
    out = terms[:, 0]
    for y in range(1, terms.shape[1]):
        out = out + terms[:, y]
    return out


def _heat(nc, no, vc, vo, lam, u0, moved, tau, temperature):
    """(heat >= 0, magnitude) [S, R] of each route's move over tau, pJ (module docstring)."""
    rt = 1e-3 * adapter.R * temperature
    gap = u0 * jnp.exp(-lam * tau[:, None])  # c_c' - c_o', with u0's sign.
    co_after = (no + moved) / vo[:, None]
    log_ratio = jnp.log1p(gap / co_after)
    heat = moved * log_ratio + nc * phi_of(-moved / nc) + no * phi_of(moved / no)
    magnitude = adapter.species_chemical_magnitude_pJ(
        nc, -moved, vc[:, None], temperature, xp=jnp
    ) + adapter.species_chemical_magnitude_pJ(no, moved, vo[:, None], temperature, xp=jnp)
    return rt * heat, magnitude


def _choose(base, c0, delta, lam_j, tau, u2):
    """The channel at the crossing state [S] (the exact kernel's rule) and a0 there."""
    c = c0 + delta * -jnp.expm1(-lam_j * tau[:, None])
    a = base * c / STANDARD_mM
    partial = [a[:, 0]]
    for y in range(1, a.shape[1]):
        partial.append(partial[-1] + a[:, y])
    total = partial[-1]
    target = jnp.minimum(u2 * total, jnp.nextafter(total, 0.0))
    chosen = jnp.full(total.shape, a.shape[1] - 1, dtype=jnp.int64)
    for y in reversed(range(a.shape[1])):
        chosen = jnp.where(partial[y] > target, y, chosen)
    return chosen, total


def _neumaier(total, carry, h):
    """(total + h, carry) by Neumaier's compensated sum."""
    new = total + h
    big = jnp.abs(total) >= jnp.abs(h)
    carry = carry + jnp.where(big, (total - new) + h, (h - new) + total)
    return new, carry


def _run_stage(state, length, offset, member, p, *, view):
    """(state, ok [site]) after `length` of the sites `member` [site] marks, every other row frozen:
    the closed-form flow between events, each event located and fired (module docstring). offset
    [site]: each site's elapsed time in the half-step when the stage starts."""
    live, vc, vo, nc0, no0, c_read = _gather(p, state, view)
    live = live & member
    n_sites, n_routes = nc0.shape
    trace = state.integer_trace_time_s.shape[1]
    t0 = state.integer_clock_s + state.integer_clock_carry_s + offset
    full = jnp.full((n_sites,), length)
    linear = p.integer_linear

    def segment(carry):
        (done, counts, hz, thr, k, chan, nc, no, moved, heat, mag, tt, tc, tcell, tnode, fired,
         ok, count) = carry  # fmt: skip
        running = live & ok & (done < length)
        rest = jnp.where(running, length - done, 0.0)
        lam, u0, scale = _flow(nc, no, counts, vc, vo, p)
        base = _base(counts, p)
        c0, delta, lam_j = _read_paths(lam, u0, vc, vo, nc, no, c_read, p)
        need = thr - hz
        whole = _hazard(base, c0, delta, lam_j, rest)
        event = running & (whole >= need)
        ok = ok & ~(event & (fired >= EVENT_CAP))
        event = event & ok
        a0 = _hazard(base, c0, delta, lam_j, jnp.ones_like(rest))  # Linear sites: a0 itself.
        exact = need / jnp.where(a0 > 0, a0, 1.0)

        def bisect(_):
            def body(_, bounds):
                lo, hi = bounds
                mid = 0.5 * (lo + hi)
                up = _hazard(base, c0, delta, lam_j, mid) >= need
                return jnp.where(up, lo, mid), jnp.where(up, mid, hi)

            return jax.lax.fori_loop(0, BISECTION_STEPS, body, (jnp.zeros_like(rest), rest))[1]

        located = jax.lax.cond(jnp.any(event & ~linear), bisect, lambda _: rest, None)
        crossing = jnp.where(linear, jnp.minimum(exact, rest), located)
        tau = jnp.where(event, crossing, rest)
        step = _moved(lam, u0, scale, tau)
        step = jnp.where(p.integer_route_present & running[:, None], step, 0.0)
        q_heat, q_mag = _heat(nc, no, vc, vo, lam, u0, step, tau, p.temperature)
        q_heat = jnp.where(step != 0, q_heat, 0.0)
        q_mag = jnp.where(step != 0, q_mag, 0.0)
        nc_new, no_new = nc - step, no + step
        draws = streams.site_uniforms(p.integer_events_key, k, 2)
        nexts = streams.site_uniforms(p.integer_events_key, k + 1, 2)
        chosen, _ = _choose(base, c0, delta, lam_j, tau, draws[:, 1])
        change = jnp.take_along_axis(p.integer_change, chosen[:, None, None], axis=1)[:, 0, :]
        counts_new = jnp.where(event[:, None], counts + change, counts)
        hz_new = jnp.where(event, 0.0, jnp.where(running, hz + whole, hz))
        thr_new = jnp.where(event, -jnp.log(nexts[:, 0]), thr)
        slot = jnp.minimum(k, max(trace - 1, 0))
        record = event & (k < trace)
        if trace:
            rows = jnp.arange(n_sites)
            tt = tt.at[rows, slot].set(jnp.where(record, t0 + done + tau, tt[rows, slot]))
            tc = tc.at[rows, slot].set(jnp.where(record, chosen, tc[rows, slot]))
            tcell = tcell.at[rows, slot].set(jnp.where(record[:, None], nc_new, tcell[rows, slot]))
            tnode = tnode.at[rows, slot].set(jnp.where(record[:, None], no_new, tnode[rows, slot]))
        hot = jax.nn.one_hot(chosen, chan.shape[1], dtype=jnp.int64)
        chan = jnp.where(event[:, None], chan + hot, chan)
        positive = (nc_new > 0) & (no_new > 0)
        ok = ok & jnp.all(jnp.where(running[:, None] & p.integer_route_present, positive, True), 1)
        ok = ok & jnp.all(counts_new >= 0, axis=1)
        done = jnp.where(event, done + tau, jnp.where(running, full, done))
        heat = heat + entity_sum(q_heat, axis=1, xp=jnp)
        mag = mag + entity_sum(q_mag, axis=1, xp=jnp)
        return (done, counts_new, hz_new, thr_new, jnp.where(event, k + 1, k), chan, nc_new,
                no_new, moved + step, heat, mag, tt, tc, tcell, tnode, fired + event, ok,
                count + 1)  # fmt: skip

    start = (
        jnp.zeros(n_sites), state.integer_counts, state.integer_hazard, state.integer_threshold,
        state.integer_events, state.integer_channel_events, nc0, no0,
        jnp.zeros((n_sites, n_routes)), jnp.zeros(n_sites), jnp.zeros(n_sites),
        state.integer_trace_time_s, state.integer_trace_channel, state.integer_trace_cell_fmol,
        state.integer_trace_node_fmol, jnp.zeros(n_sites, dtype=jnp.int64),
        jnp.ones(n_sites, dtype=bool), jnp.asarray(0),
    )  # fmt: skip

    # A fixed trip, EVENT_CAP events and the segment that finishes the stage, so every world of a
    # batch runs in step (GPU lockstep under vmap): a site done, or not running, is an exact no-op.
    # A trip in which no site of the world runs is skipped by lax.cond, which under vmap becomes a
    # select (the lanes stay in step) and on the scalar path skips the trips after the last event.
    def trip(_, carry):
        running = jnp.any(live & carry[16] & (carry[0] < length))
        return jax.lax.cond(running, segment, lambda unchanged: unchanged, carry)

    end = jax.lax.fori_loop(0, EVENT_CAP + 1, trip, start)
    (done, counts, hz, thr, k, chan, _, _, moved, heat, mag, tt, tc, tcell, tnode, _, ok,
     _) = end  # fmt: skip
    ok = ok & ~(live & (done < length))  # A site the loop could not finish: refused (the cap).
    sp, cell, node = p.integer_route_species, p.integer_site_cell, p.integer_site_node
    flowing = moved != 0
    inc_c, inc_o = state.amount_increment, state.extracellular_amount_increment
    out_c = inc_c.at[sp, cell[:, None]].add(jnp.where(flowing, -moved, 0.0))
    out_o = inc_o.at[sp, node[:, None]].add(jnp.where(flowing, moved, 0.0))
    touched_c = jnp.zeros(inc_c.shape, dtype=bool).at[sp, cell[:, None]].max(flowing)
    touched_o = jnp.zeros(inc_o.shape, dtype=bool).at[sp, node[:, None]].max(flowing)
    keep = live[:, None]
    new = state._replace(
        amount_increment=jnp.where(touched_c, out_c, inc_c),
        extracellular_amount_increment=jnp.where(touched_o, out_o, inc_o),
        integer_counts=jnp.where(keep, counts, state.integer_counts),
        integer_hazard=jnp.where(live, hz, state.integer_hazard),
        integer_threshold=jnp.where(live, thr, state.integer_threshold),
        integer_events=jnp.where(live, k, state.integer_events),
        integer_channel_events=jnp.where(keep, chan, state.integer_channel_events),
        integer_transferred_fmol=jnp.where(
            flowing, state.integer_transferred_fmol + moved, state.integer_transferred_fmol
        ),
        integer_transfer_dissipated_energy_pJ=state.integer_transfer_dissipated_energy_pJ + heat,
        integer_energy_magnitude_pJ=state.integer_energy_magnitude_pJ + mag,
        integer_trace_time_s=tt,
        integer_trace_channel=tc,
        integer_trace_cell_fmol=tcell,
        integer_trace_node_fmol=tnode,
    )
    return new, ok


def stage_plan(count, h):
    """((stage, length, offset), ...) of one half-step over `count` stages: the stage itself over h
    when there is one; else a palindrome of exact stages, the first count - 1 over h/2 forward, the
    last over h, then the first count - 1 over h/2 back (each site's second pass starts at h/2), so
    the half-step is symmetric and the splitting between coupled sites second order (static)."""
    if count == 1:
        return ((0, h, 0.0),)
    half = 0.5 * h
    forward = tuple((c, half, 0.0) for c in range(count - 1))
    back = tuple((c, half, half) for c in reversed(range(count - 1)))
    return (*forward, (count - 1, h, 0.0), *back)


def half_step(state, h, p, *, view=None):
    """(state after h of the operator, validity) (module docstring): its stages in stage_plan's
    order. Sites at a closed patch are selected unchanged; the clock advances for all."""
    stage = p.integer_site_stage
    ok = jnp.ones(stage.shape, dtype=bool)
    for c, length, offset in stage_plan(p.integer_stages.shape[0], h):
        member = stage == c
        state, done = _run_stage(
            state, length, jnp.where(member, offset, 0.0), member, p, view=view
        )
        ok = ok & done
    clock, carry_s = _neumaier(state.integer_clock_s, state.integer_clock_carry_s, h)
    new = state._replace(integer_clock_s=clock, integer_clock_carry_s=carry_s)
    return new, jnp.all(ok) & own_valid(new, p, xp=jnp)


def own_valid(state, p, *, xp):
    """Its own fields: finite; counts and event numbers >= 0; 0 <= H and 0 < E; heat and
    magnitude >= 0."""
    valid = xp.all(state.integer_counts >= 0) & xp.all(state.integer_events >= 0)
    valid &= xp.all(state.integer_channel_events >= 0)
    hz, thr = state.integer_hazard, state.integer_threshold
    valid &= xp.all(xp.isfinite(hz) & xp.isfinite(thr) & (hz >= 0) & (thr > 0))
    for name in (
        "integer_clock_s",
        "integer_clock_carry_s",
        "integer_transferred_fmol",
        "integer_trace_time_s",
        "integer_trace_cell_fmol",
        "integer_trace_node_fmol",
    ):
        valid &= xp.all(xp.isfinite(getattr(state, name)))
    heat, mag = state.integer_transfer_dissipated_energy_pJ, state.integer_energy_magnitude_pJ
    return valid & xp.all(xp.isfinite(heat) & (heat >= 0) & xp.isfinite(mag) & (mag >= 0))


def subunits(counts, p, *, xp):
    """Σ_k w_k n_k per site [S], int64."""
    return entity_sum(p.integer_weights * counts, axis=-1, xp=xp)


# ------------------------------------------------------------------ division


def segregate(counts, f, uniform, *, xp):
    """independent_segregation of a parent's counts [M, K] with first-recipient probabilities f [M]
    and uniforms [M, W] (W >= every parent's units): (first [M, K], second [M, K]), each unit in
    declared unit order (state order, then index) to the first where its uniform is below f."""
    ends = xp.cumsum(counts, axis=1)
    starts = ends - counts
    position = xp.arange(uniform.shape[1])[None, :, None]
    inside = (position >= starts[:, None, :]) & (position < ends[:, None, :])  # [M, W, K]
    below = inside & (uniform[:, :, None] < f[:, None, None])
    first = entity_sum(below, axis=1, xp=xp).astype(np.int64)
    return first, counts - first


def divide(state, maps, p, *, xp):
    """(state, valid) after the due divisions of a retiring operator (the composite's lifecycle
    hook): each mapped site whose patch the due division retires sends its units to its daughter
    sites by independent_segregation, f the patch map's area fraction (module docstring)."""
    if p.integer_map_parent.shape[0] == 0:  # Static: no site maps.
        return state, xp.asarray(True)
    parent_rows, daughter_rows, fraction, due = maps["membrane_slot"]
    parent, kids = p.integer_map_parent, p.integer_map_daughters
    patch = p.integer_site_patch
    hit = (parent_rows[None, :] == patch[parent][:, None]) & due[None, :]  # [map, patch row]
    divides = xp.any(hit, axis=1)
    f = entity_sum(xp.where(hit, fraction[None, :], 0.0), axis=1, xp=xp)
    first_patch = entity_sum(xp.where(hit, daughter_rows[None, :, 0], 0), axis=1, xp=xp)
    second_patch = entity_sum(xp.where(hit, daughter_rows[None, :, 1], 0), axis=1, xp=xp)
    valid = xp.all(entity_sum(hit, axis=1, xp=xp) <= 1)
    valid &= xp.all(
        xp.where(
            divides,
            (first_patch == patch[kids[:, 0]]) & (second_patch == patch[kids[:, 1]]),
            True,
        )
    )
    counts = state.integer_counts
    held = counts[parent]
    words = p.integer_partition_key[parent]
    block = p.integer_block.shape[0]
    uniform = streams.site_uniforms(
        jnp.asarray(words), jnp.zeros(parent.shape[0], dtype=jnp.int64), block
    )
    if xp is np:
        uniform = np.asarray(uniform)
    first, second = segregate(held, f, uniform, xp=xp)
    valid &= xp.all(xp.where(divides, entity_sum(held, axis=1, xp=xp) <= block, True))
    empty = (counts[kids[:, 0]] == 0) & (counts[kids[:, 1]] == 0)
    valid &= xp.all(xp.where(divides[:, None], empty, True))
    on = divides[:, None]
    zero = xp.zeros_like(held)
    record = state.integer_divided_units

    def add(array, rows, values):
        if xp is np:
            out = np.array(array, copy=True)
            np.add.at(out, rows, values)
            return out
        return array.at[rows].add(values)

    counts = add(counts, parent, xp.where(on, -held, zero))
    counts = add(counts, kids[:, 0], xp.where(on, first, zero))
    counts = add(counts, kids[:, 1], xp.where(on, second, zero))
    record = add(record, parent, xp.where(on, -held, zero))
    record = add(record, kids[:, 0], xp.where(on, first, zero))
    record = add(record, kids[:, 1], xp.where(on, second, zero))
    new = state._replace(integer_counts=counts, integer_divided_units=record)
    valid &= xp.all(counts >= 0)
    return new, valid


# ------------------------------------------------------------------ definition checks


def _entries(spec):
    return tuple(composite_spec.entries(spec))


def check_writers(spec, declaration, model):
    """The writers, closers and neighbours version 1 admits (module docstring)."""
    rows = set()
    for population, site in sites_of(declaration):
        moved, _ = site_rows(population, site)
        rows |= moved
    moved_species = {s.id for s in declaration.species}
    for op, other, _ in _entries(spec):
        if op.LAW_ID == LAW_ID:
            continue
        if op.LAW_ID in REPLACEMENT_LAWS or "amount_increment" in op.EVENT_REPLACES:
            raise ConfigError(
                f"{LAW_ID}: {op.LAW_ID} replaces a slot's amounts at an event, and a replaced "
                "slot's units and clock have no rule here (refused, as D301 found for the gene "
                "unit)"
            )
        if op.LABEL_OWNER:
            raise ConfigError(
                f"{LAW_ID}: {op.LAW_ID} labels species rows, and this operator reports no one-way "
                "moves to a label owner (FR-42's stages)"
            )
        changes_masks = op.CLOSES or set(op.VIEW_FIELDS) & set(adapter.MASK_FIELDS)
        if changes_masks and not (op.RETIRES and op.TAKES_LIFECYCLE):
            raise ConfigError(
                f"{LAW_ID}: {op.LAW_ID} opens or closes slots without dividing them through the "
                "composite's lifecycle, so a site there would gain or keep units with no rule "
                "(fails closed)"
            )
        if op.LAW_ID == REACTIONS_LAW:
            from cells.operators import species_reactions

            written = {(s, n) for s, n in species_reactions.written(other)}
            for species, _, node in sorted(rows):
                if (species, node) in written:
                    raise ConfigError(
                        f"{LAW_ID}: a {REACTIONS_LAW} reaction writes {species} at {node}, a row "
                        "this operator moves: one local-kinetics writer per reacting row (D152)"
                    )
        if op.LAW_ID == GENE_UNIT_LAW:
            shared = sorted(moved_species & {s.id for s in op.species_identities(other)})
            if shared:
                raise ConfigError(
                    f"{LAW_ID}: {GENE_UNIT_LAW} lists {shared[0]!r}, which this operator moves; "
                    "the gene unit is its listed rows' one writer"
                )
    if any(op.CLOSES for op, _, _ in _entries(spec)):
        if not any(o is not None and o.LAW_ID == LAW_ID for o in _owned_dividers(model)):
            raise ConfigError(
                f"{LAW_ID}: a closer is composed, and this composite does not divide owned state "
                "through its lifecycle (DIVIDES_OWNED), so a dividing site's units would be lost"
            )
    movers = species_registry.moved_in_step(spec)
    for species, kind, _ in sorted(rows):
        found = movers.get(species, {}).get(kind, ())
        if found:
            raise ConfigError(
                f"{LAW_ID}: {species} is moved inside the inner step by {found[0]}; a row this "
                "operator moves has writers with exact half-steps only"
            )


def _owned_dividers(model):
    return tuple(getattr(model, "owned_dividers", ()))


def lives(spec):
    """{cell id: (birth, retirement)} from every operator that decides lives (host side)."""
    out = {}
    for op, declaration, schedule in _entries(spec):
        out.update(op.living_intervals(spec, declaration, schedule))
    return out


def patch_maps(spec):
    """{patch id: (daughter patch ids)} from every operator that maps patches (host side)."""
    out = {}
    for op, declaration, _ in _entries(spec):
        out.update(op.patch_maps(declaration))
    return out


def check_lives(spec, declaration):
    """Units at a site whose cell is born later are refused; a site whose patch divides has a site
    map onto sites at the patch's daughter patches, in order."""
    cell_lives, maps = lives(spec), patch_maps(spec)
    by_id = {site.id: site for _, site in sites_of(declaration)}
    parents = {m.parent: m for m in declaration.divisions}
    for _, site in sites_of(declaration):
        birth, retirement = cell_lives.get(site.cell, (None, None))
        if birth is not None and any(n for _, n in site.initial_counts):
            raise ConfigError(
                f"{LAW_ID}: site {site.id}'s cell {site.cell} is born at {birth!r}, so it declares "
                "no units: a daughter site's units come from its parent"
            )
        if retirement is not None and site.patch in maps:
            if site.id not in parents:
                raise ConfigError(
                    f"{LAW_ID}: site {site.id}'s patch {site.patch} divides, so a site map names "
                    "its two daughter sites"
                )
    for m in declaration.divisions:
        parent = by_id[m.parent]
        mapped = maps.get(parent.patch)
        found = tuple(by_id[d].patch for d in m.daughters)
        if mapped is None or tuple(mapped) != found:
            raise ConfigError(
                f"{LAW_ID}: site map {m.parent} -> {list(m.daughters)} does not follow the "
                f"composite's patch map of {parent.patch} ({mapped!r} against {list(found)})"
            )


def check_hazard_bound(spec, declaration):
    """dt a0,max <= HAZARD_BOUND per site, where a0,max is bounded: the largest counts the
    subunits allow, the rates, and for a read of a moved species its largest concentration, all
    of that species' declared material in cells and finite nodes, plus turnover's largest
    production over the horizon, at the read node's volume. A read of a read-only species is not
    bounded here: the run-time cap guards it (module docstring)."""
    m, dt = spec.model, spec.execution.dt
    species = list(m.species_ids)
    volume = {c.id: c.volume_pL for c in m.cells} | {c.id: c.volume_pL for c in m.extracellular}
    moved = {s.id for s in declaration.species}
    material = {}
    for s in moved:
        i = species.index(s)
        total = math.fsum(c.initial_amount_fmol[i] for c in m.cells)
        total += math.fsum(c.initial_amount_fmol[i] for c in m.extracellular if not c.reservoir)
        material[s] = total
    horizon = spec.experiment.end_time if hasattr(spec.experiment, "end_time") else None
    for op, block, schedules in _entries(spec):
        if op.LAW_ID != "cells.operator.scheduled_species_turnover@1" or horizon is None:
            continue
        kind = {r.id: r for r in block.routes}
        for s in schedules:
            route = kind[s.route_id]
            if route.kind == "production" and route.species in material:
                material[route.species] += horizon * max(float(v[0]) for _, v in s.changes)
    for population, site in sites_of(declaration):
        weight = {u.id: u.subunits for u in population.unit_states}
        total = sum(weight[s] * n for s, n in site.initial_counts)
        top = 0.0
        bounded = True
        for c in population.channels:
            ff = 1.0
            for state, r in c.reactants:
                most = total // weight[state]
                ff *= math.perm(most, r) if most >= r else 0.0
            factor = 1.0
            if c.read is not None:
                name, at = c.read
                if name not in moved:
                    bounded = False
                    continue
                node = site.cell if at == "cell" else site.node
                factor = material[name] / volume[node] / STANDARD_mM
            top += c.rate_per_s * ff * factor
        if bounded and dt * top > HAZARD_BOUND:
            raise ConfigError(
                f"{LAW_ID}: site {site.id} has dt a0,max = {dt * top:.3g} > {HAZARD_BOUND}; "
                f"the located events take at most {EVENT_CAP} per half-step"
            )


# ------------------------------------------------------------------ the operator


class IntegerUnitPopulationOperator(Operator):
    LAW_ID = LAW_ID
    IDENTITY_ROLE = "author"  # It declares the species it moves (D176).
    STEP_ID = STEP_ID
    SPLIT = True
    RK4 = "split"
    STATE_AXES = MappingProxyType(STATE_AXES)
    STATE_DTYPES = MappingProxyType(STATE_DTYPES)
    HEAT_FIELDS = ("integer_transfer_dissipated_energy_pJ",)
    LAYOUT_FIELDS = LAYOUT_FIELDS
    CONFLICTS_VIEW = ("volume", "extracellular_volume")
    VIEW_READS = ("membrane_active", "extracellular_amount_reference")
    SCOPED_READS = MappingProxyType(
        {
            "membrane_active": Read("current", "split"),
            "extracellular_amount_reference": Read("current", "split"),
        }
    )
    ENTITY_WRITES = MappingProxyType(
        {
            "amount_increment": ("integer_transferred_fmol",),
            "extracellular_amount_increment": ("integer_transferred_fmol",),
        }
    )
    LEDGERS = LEDGERS
    LEDGER_DIAGNOSTICS = LEDGER_DIAGNOSTICS
    LEDGER_MESSAGE = LEDGER_MESSAGE
    # The composite's lifecycle hook (D315): its owned state divides at a retiring operator's
    # division (divide_owned).
    DIVIDES_OWNED = True
    VIEW_LAYERS = (
        {"id": "integer_units", "label": "Integer unit population", "representation": "simulated"},
    )
    RECORD_KINDS = MappingProxyType(
        {
            "integer_counts": "amount",
            "integer_hazard": "level",
            "integer_threshold": "level",
            "integer_events": "cumulative",
            "integer_channel_events": "cumulative",
            "integer_clock_s": "level",
            "integer_clock_carry_s": "level",
            "integer_transferred_fmol": "cumulative",
            "integer_transfer_dissipated_energy_pJ": "cumulative",
            "integer_energy_magnitude_pJ": "cumulative",
            "integer_divided_units": "cumulative",
            "integer_trace_time_s": "level",
            "integer_trace_channel": "level",
            "integer_trace_cell_fmol": "amount",
            "integer_trace_node_fmol": "amount",
        }
    )
    UNITS = MappingProxyType(
        {
            "integer_counts": "units",
            "integer_hazard": "1",
            "integer_threshold": "1",
            "integer_events": "events",
            "integer_channel_events": "events",
            "integer_trace_channel": "index",
            "integer_divided_units": "units",
        }
    )
    ORIENTATION = MappingProxyType(
        {
            "integer_transferred_fmol": {
                "from": "inside",
                "to": "outside",
                "says": "a positive amount has left the cell of the site's patch for that patch's "
                "outside node",
            }
        }
    )

    def view_sets(self, spec, declaration):
        """The run view's sets of its own axes: sites (on their patches), unit states, channels,
        routes and trace slots, each by the first population's IDs where axes are padded."""
        pairs = sites_of(declaration)
        first = declaration.populations[0]
        n, k, j, r, t, _ = dimensions(declaration)

        def pad(ids, size, word):
            return tuple(ids) + tuple(f"{word}_{i}" for i in range(len(ids), size))

        return {
            "integer_site": {
                "id": "integer_site",
                "ids": tuple(s.id for _, s in pairs),
                "holds": "integer unit site",
                "on": ("membrane", tuple(s.patch for _, s in pairs)),
                "roles": {
                    "inside": "the cell of the site's patch",
                    "outside": "that patch's outside node",
                },
            },
            "integer_state": {
                "id": "integer_state",
                "ids": pad([u.id for u in first.unit_states], k, "state"),
                "holds": "unit state",
            },
            "integer_channel": {
                "id": "integer_channel",
                "ids": pad([c.id for c in first.channels], j, "channel"),
                "holds": "event channel",
            },
            "integer_route": {
                "id": "integer_route",
                "ids": pad([x.id for x in first.transfers], r, "route"),
                "holds": "transfer route",
            },
            "integer_trace": {
                "id": "integer_trace",
                "ids": tuple(f"event_{i}" for i in range(t)),
                "holds": "recorded event",
            },
        }

    # ------------------------------------------------------------ definition

    def parse(self, raw, base, inner_model):
        return parse_declaration(raw, base)

    def to_dict(self, declaration, base):
        return declaration_to_dict(declaration)

    def species_identities(self, declaration):
        return declaration.species

    def check_definition(self, spec, declaration, schedule, model):
        common.check_species_cap(spec, LAW_ID)
        common.check_identities(spec, LAW_ID, declaration.species)
        check_writers(spec, declaration, model)
        check_lives(spec, declaration)
        check_hazard_bound(spec, declaration)

    def batch_signature(self, declaration):
        """The static structure; the seed, rates, conductances and counts are per-world data."""
        return (
            LAW_ID,
            tuple(s.id for s in declaration.species),
            tuple(s.id for s in declaration.read_species),
            dimensions(declaration)[:5],
            dimensions(declaration)[5],
            tuple(
                (
                    p.id,
                    tuple(s.id for s in p.unit_states),
                    tuple((c.id, c.reactants, c.products, c.read) for c in p.channels),
                    tuple((t.id, t.species) for t in p.transfers),
                    p.division,
                    tuple((s.id, s.patch) for s in p.sites),
                )
                for p in declaration.populations
            ),
            tuple((m.parent, m.daughters) for m in declaration.divisions),
        )

    def working_size(self, spec):
        """Values per saved row (execution/resources.row_bytes): its owned fields, the trace
        included, times a margin of 2."""
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        n, k, j, r, t, _ = dimensions(declaration)
        return 2 * n * ((2 * k + j + r + 7) + t * (2 + 2 * r))

    def fixed_working_size(self, spec):
        """Values held once per resident copy (execution/resources.fixed_bytes): its bound
        layout, times a margin of 2."""
        (declaration,) = (d for op, d, _ in composite_spec.entries(spec) if op.LAW_ID == LAW_ID)
        n, k, j, r, _, w = dimensions(declaration)
        maps = len(declaration.divisions)
        return 2 * (n * (12 + 2 * k + 2 * j * k + 4 * j + 2 * r + r * k) + 3 * maps + w + n)

    def summary(self, spec, declaration, schedule, history):
        return {
            "integer_law": LAW_ID,
            "integer_step": STEP_ID,
            "integer_streams": streams.identity(declaration.seed),
            "integer_species": common.summary_identities(declaration.species),
            "integer_read_species": [s.id for s in declaration.read_species],
            "integer_populations": declaration_to_dict(declaration)["populations"],
            "integer_site_maps": [
                dict(parent=m.parent, daughters=list(m.daughters)) for m in declaration.divisions
            ],
            "integer_event_cap_per_half_step": EVENT_CAP,
            "integer_propensity": "k_j prod_k n_k!/(n_k - r_jk)! (c/1 mM where read)",
        }

    # ------------------------------------------------------------ binding

    def initial_values(self, spec, declaration, schedule, inner_state, inner_layout):
        return bind(spec, declaration)

    # ------------------------------------------------------------ step parts

    def statically_idle(self, p):
        return p.integer_site_cell.shape[0] == 0

    def half_step(self, state, h, control, p, *, xp, view=None):
        """view: the reader view where an operator changes membrane_active or the node anchors
        (door S; C1: none otherwise, and the declared values are read)."""
        new, valid = half_step(state, h, p, view=view)
        if xp is np:
            return jax.tree.map(np.asarray, new), bool(valid)
        return new, valid

    def divide_owned(self, state, maps, masks, p, *, xp):
        """The composite's lifecycle hook: its sites' units at the due divisions (divide)."""
        return divide(state, maps, p, xp=xp)

    def rates(self, state, control, p, view, *, xp):
        return {k: xp.zeros_like(getattr(state, k)) for k in self.STATE_AXES}, None, None

    def rate_checks(self, state, control, p, valid, *, xp):
        return valid & own_valid(state, p, xp=xp)

    def domain_valid(self, state, p, valid, *, xp):
        own = own_valid(state, p, xp=xp)
        return own if valid is None else valid & own

    # ------------------------------------------------------------ ledgers

    def ledger_terms(self, result, row, p, *, xp):
        if self.statically_idle(p):
            return result, self.own_ledgers(row, p, xp=xp)
        moved = row.integer_transferred_fmol
        sp = p.integer_route_species
        cell = xp.broadcast_to(p.integer_site_cell[:, None], sp.shape)
        node = xp.broadcast_to(p.integer_site_node[:, None], sp.shape)
        present = p.integer_route_present
        local = xp.where(present, moved, 0.0)
        result["local"] = _scatter(result["local"], (sp, cell), local, xp=xp)
        result["outside"] = _scatter(result["outside"], (sp, node), -local, xp=xp)
        result["energy"] = result["energy"] + entity_sum(
            row.integer_transfer_dissipated_energy_pJ, axis=None, xp=xp
        )
        return result, self.own_ledgers(row, p, xp=xp)

    def magnitude_terms(self, magnitudes, row, p, *, xp):
        if self.statically_idle(p):
            return magnitudes
        moved = xp.abs(xp.where(p.integer_route_present, row.integer_transferred_fmol, 0.0))
        sp = p.integer_route_species
        cell = xp.broadcast_to(p.integer_site_cell[:, None], sp.shape)
        node = xp.broadcast_to(p.integer_site_node[:, None], sp.shape)
        magnitudes[0] = _scatter(magnitudes[0], (sp, cell), moved, xp=xp)
        magnitudes[1] = _scatter(magnitudes[1], (sp, node), moved, xp=xp)
        magnitudes[2] = _scatter(magnitudes[2], (sp,), 2.0 * moved, xp=xp)
        energy = entity_sum(row.integer_energy_magnitude_pJ, axis=None, xp=xp)
        magnitudes[6] = energy if magnitudes[6] is None else magnitudes[6] + energy
        return magnitudes

    def own_ledgers(self, row, p, *, xp):
        """integer_subunits: Σ_k w_k (n_k - n_k(0) - divided_k) per site, exactly 0."""
        weights = p.integer_weights
        held = row.integer_counts - p.integer_initial_counts - row.integer_divided_units
        total = entity_sum(weights * held, axis=-1, xp=xp)
        return dict(integer_subunits=total.astype(np.float64))

    def own_magnitudes(self, row, p, *, xp):
        total = entity_sum(p.integer_weights * xp.abs(row.integer_counts), axis=-1, xp=xp)
        return (total.astype(np.float64),)

    def own_bounds(self, magnitudes, steps):
        return tuple(LEDGER_FLOOR_UNITS + 0.0 * m for m in magnitudes)


def _scatter(array, index, values, *, xp):
    """array with values added at index (duplicates accumulate)."""
    if xp is np:
        out = np.array(array, copy=True)
        np.add.at(out, index, values)
        return out
    return array.at[index].add(values)
