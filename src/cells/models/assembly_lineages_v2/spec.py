"""The definition of a run of version 2 (cells.assembly_lineages@2).

    {"schema_version": 1,
     "model": {"id": "cells.assembly_lineages@2", "world": {...}},     world.py's record
     "experiment": {"time_horizon_s", "event_limit", "row_every_events",
                    "observation_times_s", "trace", "uniforms"},
     "execution": {"backend", "precision", "mode", "stream": {seed, environment, lineage, branch},
                   "molecule_capacity", "place_capacity", "step_capacity", "chunk_events",
                   "unroll"}}

**The world** (world.py) holds everything two runs of it share; its id is the SHA-256 of its
canonical JSON, computed here, never written as a literal. Beside world.py's parts it resolves the
laws: every step's law is a reaction law of this family (`cells.reaction_law@1`, hosted by
cells.assembly_lineages@2); `free_energy` lists the terms of F, `cells.ideal_mixing@1` first and
exactly once, then the excess terms (`cells.regular_mixing@1`), each at most once; `rate_factor`
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
    IDEAL_MIXING,
    MEMBRANE_PERMEATION,
    MODEL_ID,
    MODES,
    PHASE_EXCHANGE,
    RATE_FACTOR_INTERFACE,
    REACTION_INTERFACE,
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
    conventions = conventions_rules.parse(raw["conventions"], geometry="geometry" in raw)
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
    _convention_refusals(world)
    if "geometry" in raw:
        block = raw["geometry"]
        if not isinstance(block, dict) or "law" not in block:
            raise ConfigError("world: geometry names its law")
        law = _law(block["law"], GEOMETRY_INTERFACE, "geometry")
        world = dataclasses.replace(world, geometry=(law.law_id, law.parse_data(block, world)))
    _geometry_refusals(world)
    _osmotic_refusals(world)
    if "division" in raw:  # OL3 milestone 1: shear fission (division.py).
        from cells.models.assembly_lineages_v2 import division as division_rules

        world = dataclasses.replace(
            world, division=division_rules.parse_data(raw["division"], world)
        )
    return world


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
        if not geometric:
            if step.locus == world_rules.MEMBRANE and len(phases) > 1:
                raise ConfigError(
                    f"world: step {step.id} crosses phases at the membrane; in a world with a "
                    "geometry a cross-phase step takes a geometric encounter law (phase exchange "
                    "for a join, permeation for an entry), and other interfaces are refused until "
                    "one is declared (§0.2c rule 3)"
                )
            continue
        _geometric_shape(step, law, by_name)
    if world.geometry is None:
        return
    if world.conventions.last_molecule != "kept":
        raise ConfigError(
            "world: a geometry's vesicle floor requires last_molecule kept (§0.2c rule 5), not "
            f"{world.conventions.last_molecule!r}"
        )
    from cells.models.assembly_lineages_v2 import geometry as geometry_rules

    quanta = geometry_rules.place_quanta(world, len(world.places))
    footprint = int(sum(int(c) * int(k) for c, k in zip(world.founder, quanta, strict=True)))
    if footprint < geometry_rules.floor_quanta(world):
        raise ConfigError(
            f"world: the founder's membrane footprint, {footprint} quanta, is below the vesicle "
            f"floor, {geometry_rules.floor_quanta(world)} (§0.2c rule 5)"
        )


def _geometric_shape(step, law, by_name):
    """Phase exchange is a join and permeation an entry, one molecule of one species (rule 2)."""
    want = {PHASE_EXCHANGE: "membrane", MEMBRANE_PERMEATION: "lumen"}.get(law.law_id)
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


def _convention_refusals(world):
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
    if world.conventions.last_molecule in ("kept", "extinct"):
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
    _keys(raw, EXPERIMENT_KEYS, EXPERIMENT_KEYS - {"schedules"}, "experiment")
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
    )


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
    execution = parse_execution(raw["execution"], model)
    return SimulationSpec(model, parse_experiment(raw["experiment"], model.world), execution)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
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


def stream_identity(spec):
    x = spec.execution
    return streams.identity(x.seed, x.environment, x.lineage, x.branch)
