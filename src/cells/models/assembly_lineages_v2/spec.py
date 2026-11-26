"""The definition of a run of version 2 (cells.model.assembly_lineages@2).

    {"schema_version": 1,
     "model": {"id": "cells.model.assembly_lineages@2", "world": {...}},     world.py's record
     "experiment": {"time_horizon_s", "event_limit", "row_every_events",
                    "observation_times_s", "trace", "uniforms"},
     "execution": {"backend", "precision", "mode", "stream": {seed, environment, lineage, branch},
                   "molecule_capacity", "place_capacity", "step_capacity", "chunk_events",
                   "unroll"}}

**The world** (world.py) holds everything two runs of it share; its id is the SHA-256 of its
canonical JSON, computed here, never written as a literal. Beside world.py's parts it resolves the
laws: every step's law is a reaction law of this family (`cells.reaction_law@1`, hosted by
cells.model.assembly_lineages@2); `free_energy` lists the terms of F, `cells.free_energy.ideal_mixing@1` first and
exactly once, then the excess terms (`cells.free_energy.regular_mixing@1`), each at most once; `rate_factor`
is optional, a `cells.rate_factor_law@2` of this family. A law of another family or interface is
refused by name, so GARD's two forms (hosted by @1) cannot be named here.

**Refusals that follow from the conventions** (conventions.py; §0.2b rule 8):
- under `last_molecule: kept` or `extinct`, the founder's membrane holds at least one molecule;
- under `condensed_measure: multinomial_less_one`, a step with a membrane place on both sides is
  singular at the one state where the membrane holds exactly its reactants (its rate there is
  +inf, mass_action.py). Such a step is admitted only in a world declared to be probed,
  `world_role: probe`, where a probe reports +inf (and a run that reaches the state stops
  stalled); any other world declaring one is refused (§0.2b rule 8).

**The experiment.** The run ends at `time_horizon_s` (s), or at `event_limit` events (a guard), or
when the lifecycle ends it (kernel.py). A row is saved at the start, after every
`row_every_events` events, at each of `observation_times_s` (strictly increasing, within the
horizon; possibly none): the state after the last event at or before that time, and at the end.
`trace` saves every event's time and channel;
`uniforms` (diagnostic) saves every event's two uniforms, so an independent oracle can replay the
run exactly. Neither changes an event.

**The execution.** `molecule_capacity` bounds every count and the membrane's size (the
log-factorial table): an event that would pass it is refused (status capacity). The capacities of
places and steps are static buckets; `chunk_events` events run per device call and `unroll` sets
the channel fold's loop unrolling. None of these changes a value of a run.
"""

import copy
import dataclasses
from dataclasses import dataclass

from cells.definitions.specs import (
    ConfigError,
    SimulationSpec,
    bounded_integer,
    digest,
    finite_number,
    require_fields,
)
from cells.models.assembly_lineages_v2 import (
    FREE_ENERGY_INTERFACE,
    GEOMETRY_INTERFACE,
    HAZARD_INTERFACE,
    IDEAL_MIXING,
    MASS_ACTION,
    MEMBRANE_PERMEATION,
    MODE,
    MODEL_ID,
    MODES,
    PHASE_EXCHANGE,
    POPULATION,
    PORE_NUCLEATION,
    PRESCRIBED_SHELL,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
    SHELL_PERMEATION,
    SIZE_THRESHOLD_DIVISION,
    streams,
)
from cells.models.assembly_lineages_v2 import conventions as conventions_rules
from cells.models.assembly_lineages_v2 import world as world_rules
from cells.registry import laws as law_registry

EXPERIMENT_KEYS = {
    "time_horizon_s",
    "event_limit",
    "row_every_events",
    "observation_times_s",
    "trace",
    "uniforms",
    "schedules",
    "diagnostic",
    "tension_holds",
}
EXECUTION_KEYS = {
    "backend",
    "precision",
    "mode",
    "stream",
    "molecule_capacity",
    "place_capacity",
    "step_capacity",
    "chunk_events",
    "unroll",
}
EXECUTION_REQUIRED = {"backend", "precision", "mode", "stream", "molecule_capacity"}
STREAM_KEYS = {"seed", "environment", "lineage", "branch"}
BUCKETS = (8, 16, 32, 64, 128, 256, 512, 1024, 2048, 4096)
DEFAULT_CHUNK = 32
DEFAULT_UNROLL = 8
MAX_MOLECULES = 2**24


@dataclass(frozen=True)
class AssemblyModel:
    world: world_rules.World

    @property
    def id(self):
        return MODEL_ID


@dataclass(frozen=True)
class Experiment:
    time_horizon_s: float
    event_limit: int
    row_every_events: int
    observation_times_s: tuple
    trace: bool
    uniforms: bool
    schedules: tuple = ()  # OL3: the shear schedules (division.py), by index.
    diagnostic: bool = False  # OL2 milestone 3: §0.2d item 10.5's record (diagnostic.py)
    tension_holds: tuple = ()  # FR-31: the held tensions (tension_hold.py), by index.


@dataclass(frozen=True)
class Execution:
    backend: str
    precision: str
    mode: str
    seed: int
    environment: int
    lineage: int
    branch: int
    molecule_capacity: int
    place_capacity: int
    step_capacity: int
    chunk_events: int
    unroll: int


def bucket(count):
    for size in BUCKETS:
        if count <= size:
            return size
    raise ConfigError(f"No capacity bucket holds {count} (largest {BUCKETS[-1]})")


def _keys(raw, allowed, required, name):
    if not isinstance(raw, dict):
        raise ConfigError(f"{name} must be an object")
    unknown, missing = set(raw) - allowed, required - set(raw)
    if unknown or missing:
        raise ConfigError(f"{name}: missing={sorted(missing)}, unknown={sorted(unknown)}")


def _boolean(value, name):
    if type(value) is not bool:
        raise ConfigError(f"{name} must be true or false")
    return value


def family_laws(interface):
    """{law ID: declaration} of this family's laws of one interface, in the active registry."""
    return {law.law_id: law for law in law_registry.active().laws(interface, MODEL_ID)}


def _law(law_id, interface, what):
    found = family_laws(interface)
    if not isinstance(law_id, str) or law_id not in found:
        raise ConfigError(
            f"world: {what} {law_id!r} is not a {interface} of {MODEL_ID}; registered: "
            + (", ".join(sorted(found)) or "none")
        )
    return found[law_id]


def parse_terms(raw, world):
    if type(raw) is not list or not raw:
        raise ConfigError("world: free_energy is a non-empty list of terms")
    out = []
    for entry in raw:
        if not isinstance(entry, dict) or "law" not in entry:
            raise ConfigError("world: free_energy: each term names its law")
        law = _law(entry["law"], FREE_ENERGY_INTERFACE, "free-energy term")
        out.append((law.law_id, law.parse_data(entry, world)))
    ids = [law_id for law_id, _ in out]
    if ids[0] != IDEAL_MIXING or ids.count(IDEAL_MIXING) != 1:
        raise ConfigError(f"world: free_energy lists {IDEAL_MIXING} first, exactly once")
    if len(set(ids)) != len(ids):
        raise ConfigError("world: free_energy lists a term twice")
    if any(_law(i, FREE_ENERGY_INTERFACE, "term").part != "excess" for i in ids[1:]):
        raise ConfigError("world: free_energy: every term after the ideal one is an excess term")
    return tuple(out)


def parse_world(raw):
    _keys(raw, world_rules.WORLD_KEYS, world_rules.WORLD_REQUIRED, "world")
    units = world_rules.parse_units(raw["units"])
    shell = _declares_shell(raw)
    conventions = conventions_rules.parse(
        raw["conventions"], geometry="geometry" in raw and not shell
    )
    species = world_rules.parse_species(raw["species"])
    osmotic = conventions.lumen_volume == conventions_rules.OSMOTIC
    places, volumes = world_rules.parse_phases(raw["phases"], species, osmotic=osmotic)
    if type(raw["steps"]) is not list or not raw["steps"]:
        raise ConfigError("world: steps is a non-empty list")
    reaction_laws = family_laws(REACTION_INTERFACE)
    encounter = conventions.exchange_encounter
    steps = tuple(
        world_rules.parse_step(s, places, species, reaction_laws, encounter) for s in raw["steps"]
    )
    if len({s.id for s in steps}) != len(steps):
        raise ConfigError("world: step IDs are unique")
    founder = world_rules.parse_founder(raw["founder"], places)
    role = raw.get("world_role")
    if role is not None and role not in world_rules.ROLES:
        raise ConfigError(
            f"world: world_role is {', '.join(world_rules.ROLES)} when declared (§0.2b rule 8), "
            f"not {role!r}"
        )
    world = world_rules.World(
        units, conventions, species, volumes, places, steps, (), None, founder, role
    )
    terms = parse_terms(raw["free_energy"], world)
    rate_factor = None
    if "rate_factor" in raw:
        block = raw["rate_factor"]
        if not isinstance(block, dict) or "law" not in block:
            raise ConfigError("world: rate_factor names its law")
        law = _law(block["law"], RATE_FACTOR_INTERFACE, "rate factor")
        rate_factor = (law.law_id, law.parse_data(block, world))
    world = world_rules.World(
        units, conventions, species, volumes, places, steps, terms, rate_factor, founder, role
    )
    if "sites" in raw:  # FR-21: declared binding sites and their complexes (§0.2f); FR-46's face.
        pairs, inner = world_rules.parse_sites(raw["sites"], places)
        world = dataclasses.replace(world, sites=pairs, inner_sites=inner)
    _convention_refusals(world, founder="population" not in raw)  # a population's: per founder
    if "geometry" in raw:
        block = raw["geometry"]
        if not isinstance(block, dict) or "law" not in block:
            raise ConfigError("world: geometry names its law")
        law = _law(block["law"], GEOMETRY_INTERFACE, "geometry")
        world = dataclasses.replace(world, geometry=(law.law_id, law.parse_data(block, world)))
    _lumen_potential_refusals(world)  # FR-48: absent unless a species declares one
    if world.inner_sites and (world.geometry is None or world.geometry[0] != PRESCRIBED_SHELL):
        raise ConfigError(  # FR-46 (R6): even when no step binds from the lumen
            f"world: sites: an inner pair is declared, which version 1 admits in a "
            f"{PRESCRIBED_SHELL} world only (FR-46)"
        )
    founders = (world.founder,)
    if "population" in raw:  # OL2 milestone 3: K slots on one pool (population.py).
        from cells.models.assembly_lineages_v2 import population as population_rules

        world = dataclasses.replace(
            world, population=population_rules.parse_data(raw["population"], world)
        )
        founders = population_rules.founder_vectors(world)
    for vector in founders:  # each founder vesicle with the pool: rules 2-8's founder checks
        probe = dataclasses.replace(world, founder=vector)
        _convention_refusals(probe)
        _geometry_refusals(probe)
        _osmotic_refusals(probe)
    if "division" in raw and _sized(raw["division"]):  # OL6 S7 (size_division.py), by law
        from cells.models.assembly_lineages_v2 import size_division

        world = dataclasses.replace(
            world, size_division=size_division.parse_data(raw["division"], world)
        )
    elif "division" in raw:  # OL3 milestone 1: shear fission (division.py).
        from cells.models.assembly_lineages_v2 import division as division_rules

        world = dataclasses.replace(
            world, division=division_rules.parse_data(raw["division"], world)
        )
    if "hazard" in raw:  # FR-31 Phase A: a vesicle hazard (pore_nucleation.py), parsed last
        block = raw["hazard"]
        if not isinstance(block, dict) or "law" not in block:
            raise ConfigError("world: hazard names its law")
        law = _law(block["law"], HAZARD_INTERFACE, "hazard")
        world = dataclasses.replace(world, hazard=(law.law_id, law.parse_data(block, world)))
    return world


def _lumen_potential_refusals(world):
    """FR-48 (D323): a species' lumen potential, version 1's scope. It is admitted in a world whose
    geometry is a prescribed shell (a declared lumen at a fixed volume: no osmotic lumen, lysis
    return or division reads it), on a species placed in the lumen, beside its solution potential
    (the records report Δ = μ°_lumen − μ°_solution). Each other case is refused by name."""
    declared = [s for s in world.species if s.mu_lumen is not None]
    if not declared:
        return
    names = ", ".join(s.id for s in declared)
    if world.geometry is None or world.geometry[0] != PRESCRIBED_SHELL:
        raise ConfigError(
            f"world: species {names} declare a lumen potential, which version 1 admits in a "
            f"{PRESCRIBED_SHELL} world only (FR-48): a bilayer's osmotic lumen, its lysis returns "
            "and its division would each read it"
        )
    in_lumen = {p.species for p in world.places if p.phase == world_rules.LUMEN}
    for s in declared:
        if s.id not in in_lumen:
            raise ConfigError(
                f"world: species {s.id} declares a lumen potential but has no lumen place (FR-48)"
            )
        if s.mu_solution is None:
            raise ConfigError(
                f"world: species {s.id} declares a lumen potential without a solution potential; "
                "the records report Δ = μ°_lumen − μ°_solution (FR-48)"
            )


def _sized(block):
    """Whether a division block names cells.operator.size_threshold_division@1 (OL6 S7)."""
    return isinstance(block, dict) and block.get("law") == SIZE_THRESHOLD_DIVISION


def _osmotic_refusals(world):
    """OL2 milestone 2's refusals (§0.2b rules 2 and 3, §0.2c rules 6–8), after the others."""
    from cells.models.assembly_lineages_v2 import OSMOTIC_LUMEN
    from cells.models.assembly_lineages_v2 import lumen as lumen_rules

    osmotic = world.conventions.lumen_volume == conventions_rules.OSMOTIC
    declared = [law_id for law_id, _ in world.terms if law_id == OSMOTIC_LUMEN]
    if not osmotic:
        if declared:
            raise ConfigError(
                f"world: free_energy: {OSMOTIC_LUMEN} is declared only under lumen_volume osmotic"
            )
        return
    if not declared:
        raise ConfigError(
            f"world: free_energy: under lumen_volume osmotic the world declares {OSMOTIC_LUMEN}, "
            "with the outside's total osmolarity (§0.2c rule 6)"
        )
    by_name = {p.name: p for p in world.places}
    lumen_places = [p for p in world.places if p.phase == world_rules.LUMEN]
    if not lumen_places:
        raise ConfigError("world: lumen_volume osmotic needs a lumen with its species")
    for step in world.steps:  # §0.2c rule 7: no rate that is +inf at an empty lumen on m.
        lumen_in = sum(c for n, c in step.reactants if by_name[n].phase == world_rules.LUMEN)
        if step.locus == world_rules.LUMEN and lumen_in >= 2:
            raise ConfigError(
                f"world: step {step.id} has {lumen_in} lumen reactant molecules; under "
                "lumen_volume osmotic its rate on m is +inf at an empty lumen, so it is refused "
                "(§0.2c rule 7)"
            )
        if step.locus == world_rules.MEMBRANE and lumen_in >= 1:
            raise ConfigError(
                f"world: step {step.id} is a membrane-locus step with a lumen reactant; under "
                "lumen_volume osmotic its rate on m is +inf at an empty lumen, so it is refused "
                "(§0.2c rule 7)"
            )
    pool = {p.species for p in world.places if p.phase == world_rules.POOL}
    homeless = sorted(
        {p.species for p in world.places if p.phase in (world_rules.MEMBRANE, world_rules.LUMEN)}
        - pool
    )
    if homeless:
        raise ConfigError(
            "world: in a world that can lyse, every membrane and lumen species has a pool place to "
            f"return to; {', '.join(homeless)} has none (§0.2c rule 8)"
        )
    c_ext = lumen_rules.outside_mM(world)
    solutes = 0.0
    pool_volume = world.volume(world_rules.POOL)
    for place, count in zip(world.places, world.founder, strict=True):
        if place.phase != world_rules.POOL:
            continue
        if place.held:
            solutes += place.held_mM
        else:
            solutes += count / (lumen_rules.AVOGADRO * pool_volume) * 1e3
    if c_ext < solutes:
        raise ConfigError(
            f"world: the outside's total osmolarity, {c_ext:g} mM, is below its declared pool "
            f"solutes' total, {solutes:.6g} mM (§0.2c rule 6)"
        )
    sigma = lumen_rules.host_tension(world, world.founder)
    sigma_max = world.geometry[1]["sigma_max_N_per_m"][0]
    if sigma > sigma_max:
        raise ConfigError(
            f"world: the founder's tension, {sigma:.6g} N/m, is beyond sigma_max, {sigma_max:g} "
            "N/m (§0.2c rule 8)"
        )


def _declares_shell(raw):
    """FR-21: whether the world's geometry is a prescribed shell, refusing first the conventions a
    shell cannot have, with their reasons (a bilayer's conventions are parsed as before)."""
    block = raw.get("geometry")
    if not (isinstance(block, dict) and block.get("law") == PRESCRIBED_SHELL):
        return False
    tokens = raw["conventions"] if isinstance(raw["conventions"], dict) else {}
    if tokens.get("lumen_volume") == conventions_rules.OSMOTIC:
        raise ConfigError(
            "world: a prescribed shell's lumen is declared, not osmotic: the wall does not swell "
            "(FR-21)"
        )
    if conventions_rules.ENCOUNTER in tokens:
        raise ConfigError(
            f"world: a prescribed shell declares no {conventions_rules.ENCOUNTER}: it takes up no "
            "amphiphiles, so no join is declared (FR-21)"
        )
    for step in raw["steps"] if isinstance(raw["steps"], list) else ():
        if isinstance(step, dict) and step.get("law") in (PHASE_EXCHANGE, MEMBRANE_PERMEATION):
            _refuse_other_kind(step.get("id"), step["law"], PRESCRIBED_SHELL)
    return True


def _declared_binding(step, world, by_name):
    """FR-21 (§0.2f) and FR-46 (D323): exactly one dilute molecule and one declared site forming
    the site's declared complex, declared in that direction, under cells.reaction.stochastic_mass_action@1
    with count_on_m, on the pair's own face: X@pool + site@membrane -> complex@membrane for an outer
    pair, and, in a prescribed shell, X@lumen + site@membrane -> complex@membrane for an inner pair.
    Its encounter is the site count: the law's membrane factor cancels to n_site, so
    a+ = k_f theta+ n_site (mass_action.py), theta+ the ligand's own phase's activity."""
    return _binding_face(step, world, by_name) is not None


def _binding_face(step, world, by_name):
    """(face, ligand species, complex species) of an admitted binding step, or None. The reactants
    are listed in place order (pool, membrane, lumen), so the ligand is found by its phase."""
    if (
        world.sites is None
        or step.law != MASS_ACTION
        or world.conventions.membrane_kinetics != "count_on_m"
        or len(step.reactants) != 2
        or len(step.products) != 1
    ):
        return None
    dilute = [(n, k) for n, k in step.reactants if by_name[n].phase in world_rules.DILUTE]
    wall = [(n, k) for n, k in step.reactants if by_name[n].phase == world_rules.MEMBRANE]
    if len(dilute) != 1 or len(wall) != 1:
        return None
    (ligand, a), (site, b) = dilute[0], wall[0]
    (complex_, c) = step.products[0]
    if (a, b, c) != (1, 1, 1) or by_name[complex_].phase != world_rules.MEMBRANE:
        return None
    pair = (by_name[site].species, by_name[complex_].species)
    if pair not in world.sites:
        return None
    face = "outer" if by_name[ligand].phase == world_rules.POOL else "inner"
    if face == "inner" and (world.geometry is None or world.geometry[0] != PRESCRIBED_SHELL):
        return None  # R6: inner-face binding in a prescribed shell only, in version 1
    if (face == "inner") != (pair in (world.inner_sites or ())):
        return None  # a pair binds on its own face only
    return face, by_name[ligand].species, by_name[complex_].species


def _face_rule(world, by_name):
    """FR-46 (D323): one face per complex, propagated by ligand moiety over every wall state.

    Each admitted binding step seeds its complex with its face, for each moiety of its ligand.
    Every step, binding steps included, joins per moiety each membrane reactant that holds the
    moiety with each membrane product that holds it: the stoichiometry decides, not the declared
    pairs, so a wall state with no binding pair of its own carries the face on, and so does a
    binding step whose site already holds the ligand (a co-ligand bound from the other face). A
    component that holds both faces for one moiety lets that moiety pass through the wall from the
    pool to the lumen: a carrier, refused by name with its wall states. Stepwise binding of one
    ligand from both faces on one site is refused with it, conservatively: the moieties cannot
    tell which molecule is which."""
    moieties = {s.id: set(s.moiety_counts()) for s in world.species}
    seeds = []  # (moiety, wall species, face)
    for step in world.steps:
        found = _binding_face(step, world, by_name)
        if found is not None:
            face, ligand, complex_ = found
            seeds += [(m, complex_, face) for m in sorted(moieties[ligand])]
    if {face for _, _, face in seeds} != {"outer", "inner"}:
        return  # one face, or none: no carrier is possible
    parent = {}

    def root(node):
        parent.setdefault(node, node)
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    ligand_moieties = sorted({m for m, _, _ in seeds})
    wall = world_rules.MEMBRANE
    for step in world.steps:
        for m in ligand_moieties:
            left = [by_name[n].species for n, _ in step.reactants
                    if by_name[n].phase == wall and m in moieties[by_name[n].species]]  # fmt: skip
            right = [by_name[n].species for n, _ in step.products
                     if by_name[n].phase == wall and m in moieties[by_name[n].species]]  # fmt: skip
            for a in left:
                for b in right:
                    parent[root((m, a))] = root((m, b))
    faces = {}
    for m, species, face in seeds:
        faces.setdefault(root((m, species)), set()).add(face)
    for top, found in sorted(faces.items()):
        if len(found) > 1:
            m = top[0]
            states = sorted({sp for (mm, sp) in list(parent) if mm == m and root((mm, sp)) == top}
                            | {sp for mm, sp, _ in seeds
                               if mm == m and root((mm, sp)) == top})  # fmt: skip
            raise ConfigError(
                f"world: the ligand moiety {m} can pass through the wall's states {states} from "
                "an outer-face complex to an inner-face one: a carrier across the wall, refused "
                "(FR-46's face rule: one face per complex, propagated by ligand moiety over every "
                "wall state)"
            )


def _geometry_refusals(world):
    """OL2's refusals (§0.2c rules 2, 3 and 5), after OL1's, so no earlier refusal changes."""
    registry = law_registry.active()
    by_name = {p.name: p for p in world.places}
    for step in world.steps:
        law = registry.lookup(step.law)
        geometric = getattr(law, "extent", "locus") == "geometric"
        phases = {by_name[n].phase for n, _ in (*step.reactants, *step.products)}
        if world.geometry is None:
            if geometric:
                raise ConfigError(
                    f"world: step {step.id}'s law {step.law} takes its encounter from a geometry, "
                    "and the world declares none (§0.2c rule 3)"
                )
            continue
        if world.geometry is not None:  # FR-21: each geometric law belongs to its geometry kind.
            _refuse_other_kind(step.id, step.law, world.geometry[0])
        if not geometric:
            if step.locus == world_rules.MEMBRANE and len(phases) > 1:
                if _declared_binding(step, world, by_name):
                    continue  # FR-21 and FR-46: rule 3's admitted interfacial shapes.
                raise ConfigError(
                    f"world: step {step.id} crosses phases at the membrane; in a world with a "
                    "geometry a cross-phase step takes a geometric encounter law (phase exchange "
                    "for a join, permeation for an entry), and other interfaces are refused until "
                    "one is declared (§0.2c rule 3). Two shapes are admitted, each for a declared "
                    "pair on its own face, under mass action with count_on_m: a pool molecule "
                    "binding an outer site, X@pool + site@membrane -> complex@membrane (§0.2f), "
                    "and, in a prescribed shell, a lumen molecule binding an inner site, X@lumen + "
                    "site@membrane -> complex@membrane (FR-46)"
                )
            continue
        _geometric_shape(step, law, by_name)
    if world.sites is not None:
        _face_rule(world, by_name)  # FR-46: one face per complex
    if world.geometry is None:
        return
    if world.conventions.last_molecule != "kept":
        raise ConfigError(
            "world: a geometry's vesicle floor requires last_molecule kept (§0.2c rule 5), not "
            f"{world.conventions.last_molecule!r}"
        )
    if world.geometry[0] == PRESCRIBED_SHELL:
        return  # FR-21: a prescribed wall has no floor; nothing removes it
    from cells.models.assembly_lineages_v2 import geometry as geometry_rules

    quanta = geometry_rules.place_quanta(world, len(world.places))
    footprint = int(sum(int(c) * int(k) for c, k in zip(world.founder, quanta, strict=True)))
    if footprint < geometry_rules.floor_quanta(world):
        raise ConfigError(
            f"world: the founder's membrane footprint, {footprint} quanta, is below the vesicle "
            f"floor, {geometry_rules.floor_quanta(world)} (§0.2c rule 5)"
        )


def _refuse_other_kind(step_id, law_id, geometry):
    """FR-21: a shell world takes cells.reaction.shell_permeation@1 and refuses joins and the bilayer's
    permeation; a bilayer world refuses the shell's permeation."""
    if geometry == PRESCRIBED_SHELL and law_id in (PHASE_EXCHANGE, MEMBRANE_PERMEATION):
        reason = (
            "a prescribed shell takes up no amphiphiles, so it has no join"
            if law_id == PHASE_EXCHANGE
            else f"a shell's entry takes {SHELL_PERMEATION}, at its declared area"
        )
        raise ConfigError(f"world: step {step_id}'s law {law_id} is refused: {reason} (FR-21)")
    if geometry != PRESCRIBED_SHELL and law_id == SHELL_PERMEATION:
        raise ConfigError(
            f"world: step {step_id}'s law {SHELL_PERMEATION} is a prescribed shell's; a bilayer's "
            f"entry takes {MEMBRANE_PERMEATION} (FR-21)"
        )


def _geometric_shape(step, law, by_name):
    """Phase exchange is a join and permeation an entry, one molecule of one species (rule 2); so
    is the shell's permeation (FR-21)."""
    want = {PHASE_EXCHANGE: "membrane", MEMBRANE_PERMEATION: "lumen",
            SHELL_PERMEATION: "lumen"}.get(law.law_id)  # fmt: skip
    ok = want is not None and len(step.reactants) == len(step.products) == 1
    if ok:
        (r, a), (p, b) = step.reactants[0], step.products[0]
        ok = (
            a == b == 1
            and by_name[r].phase == world_rules.POOL
            and by_name[p].phase == want
            and by_name[r].species == by_name[p].species
        )
    if not ok:
        kind = {"membrane": "a join", "lumen": "an entry"}.get(want, "a geometric step")
        raise ConfigError(
            f"world: step {step.id} of {law.law_id} is declared as {kind}: one molecule of one "
            f"species from the pool to the {want} (§0.2c rule 2)"
        )


def _convention_refusals(world, founder=True):
    if world.conventions.offset == 1 and world.role != "probe":
        by_name = {p.name: p for p in world.places}
        for step in world.steps:
            both = {n for n, _ in step.reactants} & {n for n, _ in step.products}
            if any(by_name[n].phase == world_rules.MEMBRANE for n in both):
                raise ConfigError(
                    f"world: step {step.id} has a membrane place on both sides; under "
                    "condensed_measure multinomial_less_one its rate is singular (+inf) where the "
                    "membrane holds exactly its reactants, so it is admitted only in a world "
                    "declared world_role: probe (§0.2b rule 8)"
                )
    if founder and world.conventions.last_molecule in ("kept", "extinct"):
        membrane = sum(
            c for p, c in zip(world.places, world.founder, strict=True) if p.phase == "membrane"
        )
        if membrane < 1:
            raise ConfigError(
                f"world: under last_molecule {world.conventions.last_molecule}, the founder's "
                "membrane holds at least one molecule"
            )


def world_to_dict(world):
    registry = law_registry.active()
    terms = [
        {"law": law_id, **registry.lookup(law_id).data_to_dict(data)}
        for law_id, data in world.terms
    ]
    out = {
        "units": {
            "time": world.units.time,
            "temperature_K": world.units.temperature_K,
            "standard_concentration_mM": world.units.standard_concentration_mM,
        },
        "conventions": conventions_rules.to_dict(world.conventions),
        "species": world_rules.species_to_dict(world.species),
        "phases": world_rules.phases_to_dict(world),
        "steps": world_rules.steps_to_dict(world.steps),
        "free_energy": terms,
        "founder": {
            p.name: count
            for p, count in zip(world.places, world.founder, strict=True)
            if not p.held
        },
    }
    if world.rate_factor is not None:
        law_id, data = world.rate_factor
        out["rate_factor"] = {"law": law_id, **registry.lookup(law_id).data_to_dict(data)}
    if world.role is not None:
        out["world_role"] = world.role
    if world.geometry is not None:
        law_id, data = world.geometry
        out["geometry"] = {"law": law_id, **registry.lookup(law_id).data_to_dict(data)}
    if world.division is not None:
        from cells.models.assembly_lineages_v2 import division as division_rules

        out["division"] = division_rules.data_to_dict(world.division)
    if world.size_division is not None:  # OL6 S7
        from cells.models.assembly_lineages_v2 import size_division

        out["division"] = size_division.data_to_dict(world.size_division)
    if world.population is not None:
        from cells.models.assembly_lineages_v2 import population as population_rules

        out["population"] = population_rules.data_to_dict(world.population)
    if world.sites is not None:
        out["sites"] = world_rules.sites_to_dict(world.sites, world.inner_sites)
    if world.hazard is not None:
        law_id, data = world.hazard
        out["hazard"] = registry.lookup(law_id).data_to_dict(data)
    return out


def world_id(world):
    return digest(world_to_dict(world))


def parse_model(raw):
    _keys(raw, {"id", "world"}, {"id", "world"}, "model")
    if raw["id"] != MODEL_ID:
        raise ConfigError(f"model: the id is {MODEL_ID}")
    return AssemblyModel(parse_world(raw["world"]))


def _observations(raw, horizon):
    if type(raw) is not list:
        raise ConfigError("experiment: observation_times_s is a list of times (s), possibly empty")
    times = tuple(
        finite_number(t, f"experiment: observation_times_s[{i}]", positive=True)
        for i, t in enumerate(raw)
    )
    if any(b <= a for a, b in zip(times, times[1:], strict=False)) or any(
        t > horizon for t in times
    ):
        raise ConfigError(
            "experiment: observation_times_s are strictly increasing and within the horizon"
        )
    return times


def parse_experiment(raw, world=None):
    _keys(raw, EXPERIMENT_KEYS, EXPERIMENT_KEYS - {"schedules", "diagnostic", "tension_holds"},
          "experiment")  # fmt: skip
    schedules = ()
    if "schedules" in raw:
        from cells.models.assembly_lineages_v2 import division as division_rules

        schedules = division_rules.parse_schedules(raw["schedules"], world)
    horizon = finite_number(raw["time_horizon_s"], "experiment: time_horizon_s", positive=True)
    return Experiment(
        time_horizon_s=horizon,
        event_limit=bounded_integer(raw["event_limit"], "experiment: event_limit", maximum=2**62),
        row_every_events=bounded_integer(
            raw["row_every_events"], "experiment: row_every_events", maximum=2**62
        ),
        observation_times_s=_observations(raw["observation_times_s"], horizon),
        trace=_boolean(raw["trace"], "experiment: trace"),
        uniforms=_boolean(raw["uniforms"], "experiment: uniforms"),
        schedules=schedules,
        diagnostic=_boolean(raw.get("diagnostic", False), "experiment: diagnostic"),
        tension_holds=_holds(raw["tension_holds"]) if "tension_holds" in raw else (),
    )


def _holds(raw):
    from cells.models.assembly_lineages_v2 import tension_hold

    return tension_hold.parse(raw)


def parse_execution(raw, model):
    _keys(raw, EXECUTION_KEYS, EXECUTION_REQUIRED, "execution")
    if raw["backend"] not in ("cpu", "gpu") or raw["precision"] != "float64":
        raise ConfigError("execution: backend cpu or gpu, precision float64")
    if raw["mode"] not in MODES:
        raise ConfigError(f"execution: mode is one of {', '.join(MODES)}")
    stream = raw["stream"]
    require_fields(stream, STREAM_KEYS, "execution: stream")
    words = {}
    for key in sorted(STREAM_KEYS):
        try:
            words[key] = streams.check_word(stream[key], f"execution: stream {key}")
        except ValueError as error:
            raise ConfigError(str(error)) from error
    world = model.world
    largest = max(
        max(world.founder),
        sum(c for p, c in zip(world.places, world.founder, strict=True) if p.phase == "membrane"),
    )
    molecules = bounded_integer(
        raw["molecule_capacity"],
        "execution: molecule_capacity",
        minimum=max(largest, 1),
        maximum=MAX_MOLECULES,
    )
    places = bounded_integer(
        raw.get("place_capacity", bucket(len(world.places))),
        "execution: place_capacity",
        minimum=len(world.places),
        maximum=BUCKETS[-1],
    )
    steps = bounded_integer(
        raw.get("step_capacity", bucket(len(world.steps))),
        "execution: step_capacity",
        minimum=len(world.steps),
        maximum=BUCKETS[-1],
    )
    return Execution(
        backend=raw["backend"],
        precision=raw["precision"],
        mode=raw["mode"],
        molecule_capacity=molecules,
        place_capacity=places,
        step_capacity=steps,
        chunk_events=bounded_integer(
            raw.get("chunk_events", DEFAULT_CHUNK), "execution: chunk_events", maximum=4096
        ),
        unroll=bounded_integer(raw.get("unroll", DEFAULT_UNROLL), "execution: unroll", maximum=64),
        **words,
    )


def parse(data):
    raw = copy.deepcopy(data)
    require_fields(raw, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    model = parse_model(raw["model"])
    if isinstance(raw["execution"], dict) and "representation" in raw["execution"]:
        from cells.models.assembly_lineages_v2 import rate_equations  # OL6 (D304)

        execution = rate_equations.parse_execution(raw["execution"], model)
        experiment = parse_experiment(raw["experiment"], model.world)
        rate_equations.refusals(model.world, experiment, execution)
        return SimulationSpec(model, experiment, execution)
    held = isinstance(raw["experiment"], dict) and "tension_holds" in raw["experiment"]
    if model.world.hazard is not None and model.world.hazard[0] == PORE_NUCLEATION and held:
        from cells.models.assembly_lineages_v2 import pore_nucleation  # FR-31 Phase A (OL6 S3)

        # exact events under a hold: areas fixed under the host clock (T2; OL6 S4 lifts it with no
        # hold, where σ comes from F and the clock is on the device)
        pore_nucleation.phase_a_refusals(model.world)
    execution = parse_execution(raw["execution"], model)
    _mode_refusals(model.world, execution.mode)
    experiment = parse_experiment(raw["experiment"], model.world)
    _capacity_refusals(model.world, experiment, execution)
    if model.world.size_division is not None:  # OL6 S7: its experiment's and execution's checks
        from cells.models.assembly_lineages_v2 import size_division

        size_division.cross_checks(model.world, experiment, execution)
    if model.world.hazard is not None or experiment.tension_holds:  # FR-31: the cross-checks
        from cells.models.assembly_lineages_v2 import tension_hold

        tension_hold.cross_checks(model.world, experiment.tension_holds)
    return SimulationSpec(model, experiment, execution)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    out = _to_dict(m, e, x)
    from cells.models.assembly_lineages_v2 import rate_equations  # OL6 (D304)

    if isinstance(x, rate_equations.RepresentationExecution):
        out["execution"] = rate_equations.execution_to_dict(x)
    return out


def _to_dict(m, e, x):
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world_to_dict(m.world)},
        "experiment": {
            "time_horizon_s": e.time_horizon_s,
            "event_limit": e.event_limit,
            "row_every_events": e.row_every_events,
            "observation_times_s": list(e.observation_times_s),
            "trace": e.trace,
            "uniforms": e.uniforms,
            **({"schedules": _schedules_to_dict(e.schedules)} if e.schedules else {}),
            **({"diagnostic": True} if e.diagnostic else {}),
            **({"tension_holds": _holds_to_dict(e.tension_holds)} if e.tension_holds else {}),
        },
        "execution": {
            "backend": x.backend,
            "precision": x.precision,
            "mode": x.mode,
            "stream": {
                "seed": x.seed,
                "environment": x.environment,
                "lineage": x.lineage,
                "branch": x.branch,
            },
            "molecule_capacity": x.molecule_capacity,
            "place_capacity": x.place_capacity,
            "step_capacity": x.step_capacity,
            "chunk_events": x.chunk_events,
            "unroll": x.unroll,
        },
    }


def _schedules_to_dict(schedules):
    from cells.models.assembly_lineages_v2 import division as division_rules

    return division_rules.schedule_to_dict(schedules)


def _holds_to_dict(holds):
    from cells.models.assembly_lineages_v2 import tension_hold

    return tension_hold.to_dict(holds)


def _capacity_refusals(world, experiment, execution):
    """Every declared count fits the molecule capacity, the log-factorial table's last index (a
    Lean finding of 20 November, on FR-20): a population's founder vesicles (each place, and the
    membrane's total), and each schedule's fresh pool, a transfer's or a replacement's. Equality is
    valid. A count above the capacity would read the table's clamped last entry, ln C! for ln n!,
    and the run's own ledger, which reads the same table, would not see it."""
    capacity = execution.molecule_capacity
    if world.population is not None:
        from cells.models.assembly_lineages_v2 import population as population_rules

        membrane = [i for i, p in enumerate(world.places) if p.phase == world_rules.MEMBRANE]
        for k, vector in enumerate(population_rules.founder_vectors(world)):
            total = sum(vector[i] for i in membrane)
            if max(vector) > capacity or total > capacity:
                raise ConfigError(
                    f"execution: founder vesicle {k} holds {max(max(vector), total)} molecules in "
                    f"a place or its membrane, above molecule_capacity {capacity}: every count is "
                    "at most the capacity, the log-factorial table's last index"
                )
    names = [p.name for p in world.places if p.phase == world_rules.POOL and not p.held]
    for schedule in experiment.schedules:
        if schedule.fresh is None:
            continue
        for name, count in zip(names, schedule.fresh, strict=True):
            if count > capacity:
                raise ConfigError(
                    f"experiment: {schedule.kind} {schedule.index}'s fresh {name} is {count}, "
                    f"above molecule_capacity {capacity}: every count is at most the capacity, "
                    "the log-factorial table's last index (equality is valid)"
                )


def _mode_refusals(world, mode):
    """The world and the mode agree: a population block exactly in population mode; a single
    lineage's division declares its continuation, a population's none (every daughter lives)."""
    if (world.population is not None) != (mode == POPULATION):
        raise ConfigError(
            "execution: mode population exactly when the world declares a population block"
        )
    if world.division is not None:
        continuation = world.division["continuation"]
        if mode == POPULATION and continuation is not None:
            raise ConfigError(
                "world: division: a population declares no continuation (every daughter lives)"
            )
        if mode != POPULATION and continuation is None:
            raise ConfigError("world: division: a single lineage declares its continuation")
    if world.size_division is not None and mode != MODE:  # OL6 S7
        raise ConfigError(
            f"world: division ({SIZE_THRESHOLD_DIVISION}): a single lineage in version 1 (a "
            "population's comes when a consumer needs it)"
        )


def stream_identity(spec):
    x = spec.execution
    later = x.mode == POPULATION or any(  # domain 5 is drawn, or domain 6
        s.rate is not None or s.kind == "transfer" for s in spec.experiment.schedules
    )
    if spec.model.world.hazard is not None:  # FR-31: domain 7 is drawn too
        return streams.pore_identity(x.seed, x.environment, x.lineage, x.branch, scheduled=later)
    build = streams.scheduled_identity if later else streams.identity
    return build(x.seed, x.environment, x.lineage, x.branch)
