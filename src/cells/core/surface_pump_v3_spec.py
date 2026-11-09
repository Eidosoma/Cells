"""resolved_pump_tissue@3: resolved_pump_tissue@2 plus voltage-gated channel populations.

Every field of resolved_pump_tissue@2 keeps its meaning and is parsed by that
identity's parser. The model adds ``channels``: populations on named membrane
patches, each with one law of CHANNEL_LAWS, a maximal permeability (m/s), an
abundance, its law's gate state and its law's permeant ion (the shared-gate
population format of resolved_tissue@5 and later). The experiment adds
``channel_controls`` (one availability schedule per population) and the
execution ``channel_capacity``. With no channels the identity reproduces
resolved_pump_tissue@2.

The gate laws are the existing Cells kinetics under neutral IDs (the stage-B
proposals in stage-b-plan-20261108-01): Kv1.5 m*h (processes/voltage_gates.py),
Kir2.1 m*h^2 (processes/potassium_channels.py) and NaV1.2 m^3*h
(processes/sodium_channels.py), whose rate laws and coefficients come from the
BETSE v1.5.0 channel library, plus always-open K and Na leaks, which carry no
gate state here. Like their source laws, the gates have no temperature term:
the declared temperature (the pump law's 200-400 K domain, as in @1 and @2)
enters the constant-field flux, the affinities and the pumps only.
"""

import copy
from dataclasses import asdict, dataclass, replace

import numpy as np

from cells.core import surface_kinetic_spec as kinetic
from cells.core import surface_pump_spec as first
from cells.core import surface_pump_v2_spec as second
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, _fields, _integer, _number
from cells.core.voltage_gated_spec import fraction

MODEL_ID = "resolved_pump_tissue@3"
KV1P5_LAW_ID = "kv1p5_mh@1"
KIR2P1_LAW_ID = "kir2p1_mh2@1"
NAV1P2_LAW_ID = "nav1p2_m3h_regularized@1"
KLEAK_LAW_ID = "kleak_always_open@1"
NALEAK_LAW_ID = "naleak_always_open@1"
# Codes 0-2 are those of processes/sodium_channels.LAW_CODES, whose dispatch the
# model reuses; 3 and 4 are gate-free leaks. Padding slots are inactive, not a code.
LAW_CODES = {KV1P5_LAW_ID: 0, KIR2P1_LAW_ID: 1, NAV1P2_LAW_ID: 2, KLEAK_LAW_ID: 3, NALEAK_LAW_ID: 4}
GATED_CODES = 3  # Codes below this have two relaxation gates (m, h).
LAW_PERMEABILITIES = {
    KV1P5_LAW_ID: (("K", 1.0),),
    KIR2P1_LAW_ID: (("K", 1.0),),
    NAV1P2_LAW_ID: (("Na", 1.0),),
    KLEAK_LAW_ID: (("K", 1.0),),
    NALEAK_LAW_ID: (("Na", 1.0),),
}
GATE_COUNTS = {law: 2 if code < GATED_CODES else 0 for law, code in LAW_CODES.items()}
SPECIES_VALENCE = {"Na": 1, "K": 1}
CHANNEL_FIELDS = set(kinetic.ChannelPopulation.__dataclass_fields__)
Control = second.Control  # The channel field is filled; absent slots stay zero.


@dataclass(frozen=True)
class SurfacePumpChannelModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple
    extracellular: tuple
    membranes: tuple[second.Membrane, ...]
    junctions: tuple[kinetic.Junction, ...]
    faces: tuple
    gauge_reference: str | None
    channels: tuple[kinetic.ChannelPopulation, ...]


@dataclass(frozen=True)
class Experiment(second.Experiment):
    """@2's experiment with populated channel schedules (one per population)."""


def projection(spec):
    """The resolved_pump_tissue@2 part of a definition (no channel populations)."""
    m, e = spec.model, spec.experiment
    model = second.SurfacePumpModel(
        **{
            k: getattr(m, k)
            for k in second.SurfacePumpModel.__dataclass_fields__
            if k != "channels"
        }
    )
    experiment = second.Experiment(
        **{k: getattr(e, k) for k in second.Experiment.__dataclass_fields__ if k != "channels"},
        channels=(),
    )
    return replace(
        spec,
        model=model,
        experiment=experiment,
        execution=replace(spec.execution, channel_capacity=0),
    )


def parse_channel(raw, ids, z, membranes):
    _fields(raw, CHANNEL_FIELDS, "channel")
    law = raw["kinetic_law"]
    if type(law) is not str or law not in LAW_CODES or type(raw["permeant_ions"]) is not list:
        raise ConfigError("Channel requires a resolved_pump_tissue@3 law and permeant ions")
    ions = []
    for ion in raw["permeant_ions"]:
        _fields(ion, set(kinetic.PermeantIon.__dataclass_fields__), "permeant ion")
        species = identifier(ion["species_id"])
        weight = _number(ion["relative_permeability"], "relative permeability")
        if species not in ids or z[ids.index(species)] != SPECIES_VALENCE.get(species):
            raise ConfigError("Channel ion requires its law's species and valence")
        ions.append(kinetic.PermeantIon(species, weight))
    if tuple((i.species_id, i.relative_permeability) for i in ions) != LAW_PERMEABILITIES[law]:
        raise ConfigError("Channel ions must exactly match the named law's permeability ratios")
    patch = identifier(raw["membrane_id"])
    if (
        patch not in membranes
        or type(raw["initial_gate"]) is not list
        or len(raw["initial_gate"]) != GATE_COUNTS[law]
    ):
        raise ConfigError("Channel requires its patch and exactly its law's gate state")
    return kinetic.ChannelPopulation(
        identifier(raw["id"]),
        patch,
        law,
        _number(raw["max_permeability_m_per_s"], "channel permeability"),
        _number(raw["abundance"], "channel abundance"),
        tuple(fraction(v, "initial channel gate") for v in raw["initial_gate"]),
        tuple(ions),
    )


def channel_to_dict(p):
    if type(p) is not kinetic.ChannelPopulation or any(
        type(i) is not kinetic.PermeantIon for i in p.permeant_ions
    ):
        raise ConfigError("Require explicit immutable channel population types")
    return asdict(p) | {
        "initial_gate": list(p.initial_gate),
        "permeant_ions": [asdict(i) for i in p.permeant_ions],
    }


def to_dict(spec):
    m, e, x = spec.model, spec.experiment, spec.execution
    if (
        type(m) is not SurfacePumpChannelModel
        or type(e) is not Experiment
        or type(x) is not kinetic.Execution
    ):
        raise ConfigError("Resolved pump tissue @3 requires its own model and experiment")
    raw = second.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["channels"] = [channel_to_dict(p) for p in m.channels]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id=p.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.channels, e.channels, strict=True)
    ]
    raw["execution"]["channel_capacity"] = x.channel_capacity
    return raw


def parse(data):
    raw = copy.deepcopy(data)
    m, e, x = raw.get("model"), raw.get("experiment"), raw.get("execution")
    if (
        not isinstance(m, dict)
        or not isinstance(e, dict)
        or not isinstance(x, dict)
        or m.get("id") != MODEL_ID
    ):
        raise ConfigError("Require resolved_pump_tissue@3")
    if "channels" not in m or "channel_controls" not in e or "channel_capacity" not in x:
        raise ConfigError("Declare channels, channel_controls and channel_capacity")
    channels, controls = m.pop("channels"), e.pop("channel_controls")
    capacity = x.pop("channel_capacity")
    if type(channels) is not list:
        raise ConfigError("channels requires an explicit list")
    m["id"] = second.MODEL_ID
    base = second.parse(raw)
    ids, z = base.model.species_ids, base.model.valence
    parsed = tuple(parse_channel(c, ids, z, {p.id for p in base.model.membranes}) for c in channels)
    model = base.model
    names = [
        p.id
        for p in (
            *model.cells,
            *model.extracellular,
            *model.membranes,
            *model.junctions,
            *model.faces,
            *(p.pump for p in model.membranes if p.pump is not None),
            *(p.calcium_pump for p in model.membranes if p.calcium_pump is not None),
            *parsed,
        )
    ]
    if len(names) != len(set(names)):
        raise ConfigError("Owner, route, pump and channel IDs must be globally unique")
    schedules = first._schedules(
        controls, "channel", [c.id for c in parsed], base.experiment.end_time
    )
    model = SurfacePumpChannelModel(
        **{
            k: getattr(model, k)
            for k in SurfacePumpChannelModel.__dataclass_fields__
            if k != "channels"
        },
        channels=parsed,
    )
    experiment = Experiment(
        **{
            k: getattr(base.experiment, k)
            for k in second.Experiment.__dataclass_fields__
            if k != "channels"
        },
        channels=tuple(schedules[c.id] for c in parsed),
    )
    execution = replace(
        base.execution,
        channel_capacity=_integer(capacity, "channel_capacity", minimum=len(parsed)),
    )
    spec = replace(base, model=model, experiment=experiment, execution=execution)
    from cells.models.surface_pump_v3 import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump @3 definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """resolved_pump_tissue@2 controls with the channel availabilities filled in."""
    base = second.control_values(projection(spec), times)
    changes = spec.experiment.changes
    indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
    values = np.asarray([c.channel for c in changes], dtype=np.float64)
    padded = np.zeros((len(times), spec.execution.channel_capacity))
    padded[:, : values.shape[-1]] = values[indices]
    return base._replace(channel=padded)
