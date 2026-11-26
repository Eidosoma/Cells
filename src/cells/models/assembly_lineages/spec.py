"""The definition of an assembly-lineage run (cells.model.assembly_lineages@1).

A definition is one run of one world:

    {"schema_version": 1,
     "model": {"id": "cells.model.assembly_lineages@1",
               "world": {...},                      the world record's content (below)
               "rate_factor": {"law": ID}},         optional: absent, exchange runs alone
     "experiment": {"fissions", "growth_event_limit", "trace", "uniforms", "life_budget"},
     "execution": {"backend", "precision", "mode", "stream": {seed, environment, lineage, branch},
                   "type_capacity", "molecule_capacity", "chunk_events", "unroll"}}

The world (GARD_DESIGN §5.4: written once, with an id its runs name) holds everything two runs
of one world share, so that a pair of law forms differs in its law alone:
- `types`: the type family and its transfer constants (family.py);
- `supply`: each type's held activity rho_i > 0, one number or one per type;
- `exchange`: {"law": cells.exchange.reservoir_exchange@1, "leave_rate": kb_i > 0};
- `law_data` (optional): the per-world data a rate-factor law reads, by field, such as GARD's
  catalysis_matrix (gard.py);
- `founder`: the founder's count of each type, declared data (one founder for every run of the
  world, and for both runs of a pair);
- `fission` (fission.py) and `continuation` (continuation.py): the operators' rules;
- `units` (optional): {"time": "nominal" or "s", "temperature_K": a temperature or null}. The
  clock and every rate constant are in that time unit; energies are in k_BT, and a declared
  temperature gives k_BT its physical value. The default, GARD's, is the nominal unit with no
  temperature (GARD_DESIGN §1.7), and to_dict writes it out explicitly.
Its id is the SHA-256 of its canonical JSON, computed here, never written as a literal.

The run's own choice is its rate-factor law: a world with law_data must name a law that reads
exactly those fields, and when it names none, the law set's default is taken and written out
explicitly (GARD: the pair-consistent form, D192 and the lead's ruling of 17 November 2026).

Values (supply, constants, matrix, founder, fission size and fraction, horizons) are layout data:
a change of value reuses the compiled program. Structure (capacities, the laws, the partition
and continuation rules, the chunk and the recording flags) selects the program.

Execution: `mode` is single_lineage (one continuing assembly per world: one daughter of each
fission is followed) or every_descendant (every daughter lives, as its own lane: population mode
P-a of docs/RELATIONSHIPS_DESIGN.md §1.4, exact under a held phase). In every_descendant mode
`experiment.fissions` is the generation limit (lives of that generation are born and censored at
the horizon, so the followed path is the single lineage of that many fissions), and
`experiment.life_budget` is required: the most lives that run. Growth is 2**g lives at generation
g, so a run holds at most min(2**(G + 1) - 1, 2 budget + 1) lives; when a generation's runnable
lives exceed what is left of the budget, that whole generation is censored at its birth (never
dropped) and the run ends. Single-lineage definitions omit life_budget, and their bytes and
fingerprints are as before it existed. The capacities are static buckets: `type_capacity` >= the
number of types and
`molecule_capacity` >= the fission size; `chunk_events` events run per device call, and `unroll`
sets the channel fold's loop unrolling. Neither changes a single value of a run.
"""

import copy
from dataclasses import dataclass

from cells.definitions.specs import (
    ConfigError,
    SimulationSpec,
    bounded_integer,
    digest,
    finite_number,
    require_fields,
)
from cells.models.assembly_lineages import (
    EVERY_DESCENDANT,
    EXCHANGE_LAW,
    MODE,
    MODEL_ID,
    MODES,
    factors,
    streams,
)
from cells.models.assembly_lineages import continuation as continuation_rules
from cells.models.assembly_lineages import family as type_family
from cells.models.assembly_lineages import fission as fission_rules

WORLD_KEYS = {
    "types",
    "supply",
    "exchange",
    "law_data",
    "founder",
    "fission",
    "continuation",
    "units",
}
WORLD_REQUIRED = WORLD_KEYS - {"law_data", "units"}
TIME_UNITS = ("nominal", "s")
EXPERIMENT_KEYS = {"fissions", "growth_event_limit", "trace", "uniforms", "life_budget"}
EXECUTION_KEYS = {
    "backend",
    "precision",
    "mode",
    "stream",
    "type_capacity",
    "molecule_capacity",
    "chunk_events",
    "unroll",
    "lanes",
}
EXECUTION_REQUIRED = {"backend", "precision", "mode", "stream"}
DEFAULT_LANES = 64  # Every descendant: the lane batch's width (it changes no value).
STREAM_KEYS = {"seed", "environment", "lineage", "branch"}
DEFAULT_CHUNK = 32
DEFAULT_UNROLL = 8
MAX_FISSIONS = 10**7
MAX_GENERATIONS = 62  # Every descendant: 2**g lives at generation g stay countable in int64.
MAX_LIFE_BUDGET = 2**24


@dataclass(frozen=True)
class Units:
    time: str  # One of TIME_UNITS: the clock's unit and the rate constants' (per unit time).
    temperature_K: float | None  # Gives k_BT its physical value; None: energies in k_BT only.


NOMINAL = Units("nominal", None)


@dataclass(frozen=True)
class World:
    types: type_family.TypeFamily
    supply: tuple[float, ...]
    exchange_law: str
    leave_rate: tuple[float, ...]
    law_data: tuple  # ((field, value), ...) in sorted field order; () when none.
    founder: tuple[int, ...]
    fission: fission_rules.Fission
    continuation: continuation_rules.Continuation
    units: Units = NOMINAL

    @property
    def data(self):
        return dict(self.law_data)

    @property
    def join_rate(self):
        """kf_i = K_i kb_i, derived (exchange.py)."""
        return tuple(
            k * b for k, b in zip(self.types.transfer_constant, self.leave_rate, strict=True)
        )

    @property
    def id(self):
        return digest(world_to_dict(self))


@dataclass(frozen=True)
class LineageModel:
    world: World
    rate_factor: str | None  # The rate-factor law's ID, or None (exchange alone).


@dataclass(frozen=True)
class Experiment:
    fissions: int  # The lineage stops after this many fissions.
    growth_event_limit: int  # Events of one growth (since a birth) before the run stops.
    trace: bool  # The event trace, saved by default for one lineage (§5.4).
    uniforms: bool  # Diagnostic: every draw's uniforms, saved for a replay.
    life_budget: int | None = None  # Every descendant only: the most lives that run.


@dataclass(frozen=True)
class Execution:
    backend: str
    precision: str
    mode: str
    seed: int
    environment: int
    lineage: int
    branch: int
    type_capacity: int
    molecule_capacity: int
    chunk_events: int
    unroll: int
    lanes: int | None = None  # Every descendant only: the lane batch's width.


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


def parse_units(raw):
    _keys(raw, {"time", "temperature_K"}, {"time"}, "world: units")
    if raw["time"] not in TIME_UNITS:
        raise ConfigError(f"world: units: time is one of {', '.join(TIME_UNITS)}")
    temperature = raw.get("temperature_K")
    if temperature is not None:
        temperature = finite_number(temperature, "world: units: temperature_K", positive=True)
    return Units(raw["time"], temperature)


def parse_world(raw):
    _keys(raw, WORLD_KEYS, WORLD_REQUIRED, "world")
    family = type_family.parse(raw["types"])
    supply = type_family.per_type(raw["supply"], family.count, "world: supply", positive=True)
    exchange = raw["exchange"]
    require_fields(exchange, {"law", "leave_rate"}, "world: exchange")
    if exchange["law"] != EXCHANGE_LAW:
        raise ConfigError(f"world: the exchange law is {EXCHANGE_LAW}")
    leave = type_family.per_type(
        exchange["leave_rate"], family.count, "world: leave_rate", positive=True
    )
    founder = raw["founder"]
    if not isinstance(founder, list) or len(founder) != family.count:
        raise ConfigError(f"world: the founder gives a count for each of the {family.count} types")
    founder = tuple(
        bounded_integer(c, f"world: founder[{i}]", minimum=0, maximum=2**31 - 1)
        for i, c in enumerate(founder)
    )
    fission = fission_rules.parse(raw["fission"])
    if not 1 <= sum(founder) < fission.size:
        raise ConfigError(
            f"world: the founder holds {sum(founder)} molecules; it must hold at least one and "
            f"fewer than the fission size {fission.size}"
        )
    law_data = ()
    if "law_data" in raw:
        fields = raw["law_data"]
        if not isinstance(fields, dict) or not fields:
            raise ConfigError("world: law_data is an object of the rate-factor law's fields")
        law = _law_reading(sorted(fields))
        law_data = tuple(sorted(law.parse_data(fields, family.count).items()))
    world = World(
        family,
        supply,
        exchange["law"],
        leave,
        law_data,
        founder,
        fission,
        continuation_rules.parse(raw["continuation"]),
        parse_units(raw["units"]) if "units" in raw else NOMINAL,
    )
    for i, value in enumerate(world.join_rate):
        if not 0 < value < float("inf"):
            raise ConfigError(f"world: type {i}'s join constant K kb = {value!r} is not finite")
    return world


def _law_reading(fields):
    """Some registered law that reads exactly these law_data fields (for parsing them)."""
    for law in factors.registered().values():
        if sorted(law.data) == list(fields):
            return law
    raise ConfigError(f"world: no registered rate-factor law reads law_data {fields}")


def world_to_dict(world):
    result = {
        "types": type_family.to_dict(world.types),
        "supply": type_family.compact(world.supply),
        "exchange": {
            "law": world.exchange_law,
            "leave_rate": type_family.compact(world.leave_rate),
        },
        "founder": list(world.founder),
        "fission": fission_rules.to_dict(world.fission),
        "continuation": continuation_rules.to_dict(world.continuation),
        "units": {"time": world.units.time, "temperature_K": world.units.temperature_K},
    }
    if world.law_data:
        result["law_data"] = _law_reading(sorted(world.data)).data_to_dict(world.data)
    return result


def default_law(world):
    """The default rate-factor law of the world's law_data: its law set's DEFAULT."""
    if not world.law_data:
        return None
    from cells.models.assembly_lineages import gard

    if sorted(world.data) == [gard.FIELD]:
        return gard.DEFAULT
    raise ConfigError("world: law_data names no law set with a default; name the rate factor")


def parse_model(raw):
    _keys(raw, {"id", "world", "rate_factor"}, {"id", "world"}, "model")
    if raw["id"] != MODEL_ID:
        raise ConfigError(f"model: the id is {MODEL_ID}")
    world = parse_world(raw["world"])
    if "rate_factor" in raw:
        require_fields(raw["rate_factor"], {"law"}, "model: rate_factor")
        law_id = raw["rate_factor"]["law"]
    else:
        law_id = default_law(world)
    if law_id is not None:
        law = factors.resolve(law_id)
        if sorted(law.data) != sorted(world.data):
            raise ConfigError(
                f"{law_id} reads law_data {sorted(law.data)}; the world holds {sorted(world.data)}"
            )
        if law.domain is not None:
            law.domain(world)  # The declared law's own numerical domain (D246).
    elif world.law_data:
        raise ConfigError("world: law_data is given but no rate-factor law reads it")
    return LineageModel(world, law_id)


def parse_experiment(raw, mode=MODE):
    _keys(raw, EXPERIMENT_KEYS, {"fissions", "growth_event_limit"}, "experiment")
    budget = raw.get("life_budget")
    if mode == EVERY_DESCENDANT:
        if budget is None:
            raise ConfigError(
                "experiment: every_descendant mode states its bound: life_budget, the most lives "
                "that run (growth is 2**g lives at generation g)"
            )
        budget = bounded_integer(
            budget, "experiment: life_budget", minimum=1, maximum=MAX_LIFE_BUDGET
        )
        limit = MAX_GENERATIONS
    else:
        if budget is not None:
            raise ConfigError("experiment: life_budget is every_descendant mode's")
        limit = MAX_FISSIONS
    return Experiment(
        fissions=bounded_integer(raw["fissions"], "experiment: fissions", maximum=limit),
        growth_event_limit=bounded_integer(
            raw["growth_event_limit"], "experiment: growth_event_limit", maximum=2**31 - 1
        ),
        trace=_boolean(raw.get("trace", True), "experiment: trace"),
        uniforms=_boolean(raw.get("uniforms", False), "experiment: uniforms"),
        life_budget=budget,
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
    lanes = raw.get("lanes")
    if raw["mode"] == EVERY_DESCENDANT:
        lanes = bounded_integer(
            DEFAULT_LANES if lanes is None else lanes, "execution: lanes", maximum=4096
        )
    elif lanes is not None:
        raise ConfigError("execution: lanes is every_descendant mode's")
    # A default bucket only where no capacity is declared: an explicit capacity is bounded below
    # (the types, the fission size) and above (2^16, 2^20) by itself, never by the buckets' largest
    # (the Lean proofs project's finding of 22 November 2026: an explicit 4,097 had been refused).
    capacity = (raw["type_capacity"] if "type_capacity" in raw
                else type_family.bucket(world.types.count))  # fmt: skip
    molecules = (raw["molecule_capacity"] if "molecule_capacity" in raw
                 else type_family.bucket(world.fission.size))  # fmt: skip
    return Execution(
        backend=raw["backend"],
        precision=raw["precision"],
        mode=raw["mode"],
        type_capacity=bounded_integer(
            capacity, "execution: type_capacity", minimum=world.types.count, maximum=2**16
        ),
        molecule_capacity=bounded_integer(
            molecules, "execution: molecule_capacity", minimum=world.fission.size, maximum=2**20
        ),
        chunk_events=bounded_integer(
            raw.get("chunk_events", DEFAULT_CHUNK), "execution: chunk_events", maximum=4096
        ),
        unroll=bounded_integer(raw.get("unroll", DEFAULT_UNROLL), "execution: unroll", maximum=64),
        lanes=lanes,
        **words,
    )


def parse(data):
    raw = copy.deepcopy(data)
    require_fields(raw, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(raw["schema_version"]) is not int or raw["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    model = parse_model(raw["model"])
    execution = parse_execution(raw["execution"], model)
    return SimulationSpec(model, parse_experiment(raw["experiment"], execution.mode), execution)


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    model = {"id": MODEL_ID, "world": world_to_dict(m.world)}
    if m.rate_factor is not None:
        model["rate_factor"] = {"law": m.rate_factor}
    return {
        "schema_version": 1,
        "model": model,
        "experiment": {
            "fissions": e.fissions,
            "growth_event_limit": e.growth_event_limit,
            "trace": e.trace,
            "uniforms": e.uniforms,
        }
        | ({} if e.life_budget is None else {"life_budget": e.life_budget}),
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
            "type_capacity": x.type_capacity,
            "molecule_capacity": x.molecule_capacity,
            "chunk_events": x.chunk_events,
            "unroll": x.unroll,
        }
        | ({} if x.lanes is None else {"lanes": x.lanes}),
    }


def stream_identity(spec):
    x = spec.execution
    return streams.identity(x.seed, x.environment, x.lineage, x.branch)
