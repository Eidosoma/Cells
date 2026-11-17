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

**A refusal that follows from the conventions** (conventions.py): under `last_molecule: kept` or
`extinct`, the founder's membrane holds at least one molecule. (Under `condensed_measure:
multinomial_less_one`, a step with a membrane place on both sides is singular at the one state
where the membrane holds exactly its reactants: the rate there is +inf, a run that reaches it stops
stalled, and a probe reports +inf (mass_action.py).)

**The experiment.** The run ends at `time_horizon_s` (s), or at `event_limit` events (a guard), or
when the lifecycle ends it (kernel.py). A row is saved at the start, after every
`row_every_events` events, at each of `observation_times_s` (strictly increasing, within the
horizon; possibly none): the state after the last event at or before that time, and at the end. `trace` saves every event's time and channel;
`uniforms` (diagnostic) saves every event's two uniforms, so an independent oracle can replay the
run exactly. Neither changes an event.

**The execution.** `molecule_capacity` bounds every count and the membrane's size (the
log-factorial table): an event that would pass it is refused (status capacity). The capacities of
places and steps are static buckets; `chunk_events` events run per device call and `unroll` sets
the channel fold's loop unrolling. None of these changes a value of a run.
"""

import copy
from dataclasses import dataclass

from cells.core.specs import (
    ConfigError,
    SimulationSpec,
    bounded_integer,
    digest,
    finite_number,
    require_fields,
)
from cells.models.assembly_lineages_v2 import (
    FREE_ENERGY_INTERFACE,
    IDEAL_MIXING,
    MODE,
    MODEL_ID,
    MODES,
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
    conventions = conventions_rules.parse(raw["conventions"])
    species = world_rules.parse_species(raw["species"])
    places, volumes = world_rules.parse_phases(raw["phases"], species)
    if type(raw["steps"]) is not list or not raw["steps"]:
        raise ConfigError("world: steps is a non-empty list")
    reaction_laws = family_laws(REACTION_INTERFACE)
    steps = tuple(world_rules.parse_step(s, places, species, reaction_laws) for s in raw["steps"])
    if len({s.id for s in steps}) != len(steps):
        raise ConfigError("world: step IDs are unique")
    founder = world_rules.parse_founder(raw["founder"], places)
    world = world_rules.World(units, conventions, species, volumes, places, steps, (), None, founder)
    terms = parse_terms(raw["free_energy"], world)
    rate_factor = None
    if "rate_factor" in raw:
        block = raw["rate_factor"]
        if not isinstance(block, dict) or "law" not in block:
            raise ConfigError("world: rate_factor names its law")
        law = _law(block["law"], RATE_FACTOR_INTERFACE, "rate factor")
        rate_factor = (law.law_id, law.parse_data(block, world))
    world = world_rules.World(
        units, conventions, species, volumes, places, steps, terms, rate_factor, founder
    )
    _convention_refusals(world)
    return world


def _convention_refusals(world):
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


def parse_experiment(raw):
    _keys(raw, EXPERIMENT_KEYS, EXPERIMENT_KEYS, "experiment")
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
    return SimulationSpec(model, parse_experiment(raw["experiment"]), execution)


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


def stream_identity(spec):
    x = spec.execution
    return streams.identity(x.seed, x.environment, x.lineage, x.branch)
