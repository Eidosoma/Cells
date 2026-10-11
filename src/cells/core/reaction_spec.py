"""Closed, compartment-owned reversible chemistry with explicit conserved moieties."""

from dataclasses import asdict, dataclass

import numpy as np

from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, ExecutionSpec, SimulationSpec, _fields, _integer, _number

MODEL_ID = "compartment_reactions@1"
LAW_ID = "ideal_detailed_balance_mass_action@1"


@dataclass(frozen=True)
class ChemicalSpecies:
    id: str
    valence: int
    moieties: tuple[int, ...]
    standard_mu_RT: float


@dataclass(frozen=True)
class ChemicalCompartment:
    id: str
    volume_pL: float
    initial_amount_fmol: tuple[float, ...]


@dataclass(frozen=True)
class ChemicalReaction:
    id: str
    compartment: str
    reactants: tuple[int, ...]
    products: tuple[int, ...]
    forward_rate_per_s: float


@dataclass(frozen=True)
class ReactionNetworkSpec:
    species: tuple[ChemicalSpecies, ...]
    moieties: tuple[str, ...]
    compartments: tuple[ChemicalCompartment, ...]
    reactions: tuple[ChemicalReaction, ...]
    temperature_K: float
    standard_concentration_mM: float


@dataclass(frozen=True)
class ReactionChange:
    time: float
    multipliers: tuple[float, ...]


@dataclass(frozen=True)
class ReactionExperiment:
    end_time: float
    observation_times: tuple[float, ...]
    changes: tuple[ReactionChange, ...]


@dataclass(frozen=True)
class ReactionExecution(ExecutionSpec):
    reaction_capacity: int = 0


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if not isinstance(e, ReactionExperiment) or not isinstance(x, ReactionExecution):
        raise ConfigError("Reaction network requires its own experiment/execution types")
    if x.edge_capacity or x.membrane_capacity:
        raise ConfigError("Local reactions do not declare transport or membrane capacity")
    species = [s.id for s in m.species]
    execution = asdict(x)
    del execution["edge_capacity"], execution["membrane_capacity"]
    return {
        "schema_version": 1,
        "model": {
            "id": MODEL_ID,
            "law": LAW_ID,
            "temperature_K": m.temperature_K,
            "standard_concentration_mM": m.standard_concentration_mM,
            "moieties": list(m.moieties),
            "species": [
                {
                    "id": s.id,
                    "valence": s.valence,
                    "moieties": dict(zip(m.moieties, s.moieties, strict=True)),
                    "standard_mu_RT": s.standard_mu_RT,
                }
                for s in m.species
            ],
            "compartments": [
                {
                    "id": c.id,
                    "volume_pL": c.volume_pL,
                    "initial_amount_fmol": dict(zip(species, c.initial_amount_fmol, strict=True)),
                }
                for c in m.compartments
            ],
            "reactions": [
                {
                    "id": r.id,
                    "compartment": r.compartment,
                    "reactants": {s: n for s, n in zip(species, r.reactants, strict=True) if n},
                    "products": {s: n for s, n in zip(species, r.products, strict=True) if n},
                    "forward_rate_per_s": r.forward_rate_per_s,
                }
                for r in m.reactions
            ],
        },
        "experiment": {
            "end_time": e.end_time,
            "observation_times": list(e.observation_times),
            "reaction_controls": [
                {
                    "time": p.time,
                    "multipliers": dict(
                        zip((r.id for r in m.reactions), p.multipliers, strict=True)
                    ),
                }
                for p in e.changes
            ],
        },
        "execution": execution,
    }


def named_rows(value, name, maximum, *, empty=False):
    if not isinstance(value, list) or not (0 if empty else 1) <= len(value) <= maximum:
        raise ConfigError(f"{name} must contain at most {maximum} named entries")
    if any(not isinstance(r, dict) or "id" not in r for r in value):
        raise ConfigError(f"{name} requires named objects")
    names = [identifier(r["id"]) for r in value]
    if len(set(names)) != len(names):
        raise ConfigError(f"Duplicate {name} ID")
    return sorted(value, key=lambda r: r["id"])


def bounded(value, name, low, high):
    value = _number(value, name)
    if not low <= value <= high:
        raise ConfigError(f"{name} must lie in [{low}, {high}]")
    return value


def parse(data):
    raw = _fields(
        data["model"],
        {
            "id",
            "law",
            "temperature_K",
            "standard_concentration_mM",
            "moieties",
            "species",
            "compartments",
            "reactions",
        },
        "reaction model",
    )
    if raw["id"] != MODEL_ID or raw["law"] != LAW_ID:
        raise ConfigError("Require the named closed detailed-balance reaction law")
    moieties = raw["moieties"]
    if not isinstance(moieties, list) or not 1 <= len(moieties) <= 16:
        raise ConfigError("Require 1 to 16 conserved moieties")
    moieties = tuple(sorted(identifier(v) for v in moieties))
    if len(set(moieties)) != len(moieties):
        raise ConfigError("Duplicate conserved moiety")
    species = []
    for s in named_rows(raw["species"], "species", 16):
        _fields(s, {"id", "valence", "moieties", "standard_mu_RT"}, "chemical species")
        if type(s["valence"]) is not int or not -8 <= s["valence"] <= 8:
            raise ConfigError("Chemical valence must be an integer in [-8,8]")
        _fields(s["moieties"], set(moieties), "species moieties")
        counts = tuple(_integer(s["moieties"][k], k, minimum=0, maximum=64) for k in moieties)
        mu = signed_number(s["standard_mu_RT"], "standard chemical potential / RT")
        if not any(counts) or abs(mu) > 30:
            raise ConfigError("Every species needs conserved material and |standard_mu_RT| <= 30")
        species.append(ChemicalSpecies(s["id"], s["valence"], counts, mu))
    species = tuple(species)
    ids = tuple(s.id for s in species)
    if not np.all(np.sum([s.moieties for s in species], axis=0) > 0):
        raise ConfigError("Each declared moiety must occur in a species")
    compartments = []
    for c in named_rows(raw["compartments"], "compartments", 32):
        _fields(c, {"id", "volume_pL", "initial_amount_fmol"}, "chemical compartment")
        _fields(c["initial_amount_fmol"], set(ids), "compartment amounts")
        compartments.append(
            ChemicalCompartment(
                c["id"],
                bounded(c["volume_pL"], "volume_pL", 1e-6, 1e6),
                tuple(
                    bounded(c["initial_amount_fmol"][s], "initial fmol", 1e-12, 1e6) for s in ids
                ),
            )
        )
    reactions = []
    for r in named_rows(raw["reactions"], "reactions", 128, empty=True):
        _fields(r, {"id", "compartment", "reactants", "products", "forward_rate_per_s"}, "reaction")
        if identifier(r["compartment"]) not in {c.id for c in compartments}:
            raise ConfigError("Reaction owner must be a declared compartment")
        sides = []
        for name in ("reactants", "products"):
            side = r[name]
            if not isinstance(side, dict) or not side or set(side) - set(ids):
                raise ConfigError("Reaction sides must name existing material species")
            for value in side.values():
                _integer(value, "stoichiometric coefficient", minimum=1, maximum=4)
            counts = tuple(side.get(s, 0) for s in ids)
            if sum(counts) > 4:
                raise ConfigError("Reaction molecular order must be at most four on either side")
            sides.append(counts)
        nu = np.subtract(sides[1], sides[0])
        if not np.any(nu):
            raise ConfigError("Reaction must change at least one species")
        if np.any(np.array([s.moieties for s in species]).T @ nu) or np.dot(
            [s.valence for s in species], nu
        ):
            raise ConfigError("Each reaction must conserve every declared moiety and charge")
        reactions.append(
            ChemicalReaction(
                r["id"],
                r["compartment"],
                *sides,
                bounded(r["forward_rate_per_s"], "forward rate", 0, 1e6),
            )
        )
    model = ReactionNetworkSpec(
        species,
        moieties,
        tuple(compartments),
        tuple(reactions),
        bounded(raw["temperature_K"], "temperature_K", 1, 1e4),
        bounded(raw["standard_concentration_mM"], "standard concentration", 1e-6, 1e3),
    )
    e = _fields(
        data["experiment"], {"end_time", "observation_times", "reaction_controls"}, "experiment"
    )
    end = positive(e["end_time"], "end time")
    if not isinstance(e["observation_times"], list) or not e["observation_times"]:
        raise ConfigError("Require observation times")
    times = tuple(_number(v, "observation time") for v in e["observation_times"])
    if any(t > end for t in times) or any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ConfigError("Observation times must strictly increase within the horizon")
    if not isinstance(e["reaction_controls"], list) or not e["reaction_controls"]:
        raise ConfigError("Require explicit reaction controls, including at time zero")
    changes = []
    for p in e["reaction_controls"]:
        _fields(p, {"time", "multipliers"}, "reaction control")
        _fields(p["multipliers"], {r.id for r in reactions}, "reaction multipliers")
        time = _number(p["time"], "control time")
        if time > end or (changes and time <= changes[-1].time):
            raise ConfigError("Reaction control times must strictly increase within the horizon")
        changes.append(
            ReactionChange(
                time, tuple(bounded(p["multipliers"][r.id], "multiplier", 0, 1) for r in reactions)
            )
        )
    if changes[0].time != 0:
        raise ConfigError("Reaction controls must start at zero")
    x = _fields(
        data["execution"],
        set(ReactionExecution.__dataclass_fields__) - {"edge_capacity", "membrane_capacity"},
        "execution",
    )
    if (
        x["backend"] not in ("cpu", "gpu")
        or x["precision"] != "float64"
        or x["solver"] != "rk4"
        or type(x["jit"]) is not bool
    ):
        raise ConfigError("Reaction execution requires CPU/GPU float64 RK4 and a boolean jit flag")
    execution = ReactionExecution(
        dt=positive(x["dt"], "dt"),
        capacity=_integer(
            x["capacity"], "compartment capacity", minimum=len(compartments), maximum=64
        ),
        reaction_capacity=_integer(
            x["reaction_capacity"], "reaction capacity", minimum=len(reactions), maximum=256
        ),
        jit=x["jit"],
        backend=x["backend"],
        max_steps=_integer(x["max_steps"], "max_steps", maximum=1000000),
        max_trace_bytes=_integer(x["max_trace_bytes"], "max_trace_bytes", maximum=2**31),
    )
    spec = SimulationSpec(model, ReactionExperiment(end, times, tuple(changes)), execution)
    from cells.models.compartment_reactions import check_definition

    check_definition(spec)
    return spec
