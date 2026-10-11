"""One finite cytosol/ER pair, local chemistry and explicit source-law routes."""

from dataclasses import asdict, dataclass, fields

from cells.core import reaction_spec as chemistry
from cells.core.bioelectric_spec import signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ConfigError, SimulationSpec, _fields, _integer
from cells.processes.er_calcium import METABOLISM, PUMP_LAW, RELEASE_LAW

MODEL_ID = "er_calcium@1"


@dataclass(frozen=True)
class ERPump:
    law: str
    capacity_fmol_per_s: float
    km_ca_mM: float
    km_atp_mM: float
    metabolism: str
    atp_mM: float
    adp_mM: float
    pi_mM: float
    delta_g0_J_per_mol: float


@dataclass(frozen=True)
class ERRelease:
    law: str
    permeability_m_per_s: float
    activation_mM: float
    activation_n: int
    inhibition_mM: float
    inhibition_n: int


@dataclass(frozen=True)
class ERMembrane:
    id: str
    cytosol: str
    er: str
    calcium_species: str
    area_m2: float
    specific_capacitance_F_per_m2: float
    initial_voltage_V: float
    permeability_m_per_s: tuple[float, ...]
    pump: ERPump | None
    release: ERRelease | None


@dataclass(frozen=True)
class ERModel(chemistry.ReactionNetworkSpec):
    membrane: ERMembrane


@dataclass(frozen=True)
class ERChange:
    time: float
    reactions: tuple[float, ...]
    passive: tuple[float, ...]
    pump: float
    release: float


@dataclass(frozen=True)
class ERExperiment:
    end_time: float
    observation_times: tuple[float, ...]
    changes: tuple[ERChange, ...]


def chemistry_spec(spec):
    model = chemistry.ReactionNetworkSpec(
        **{
            field.name: getattr(spec.model, field.name)
            for field in fields(chemistry.ReactionNetworkSpec)
        }
    )
    experiment = chemistry.ReactionExperiment(
        spec.experiment.end_time,
        spec.experiment.observation_times,
        tuple(chemistry.ReactionChange(c.time, c.reactions) for c in spec.experiment.changes),
    )
    return SimulationSpec(model, experiment, spec.execution)


def to_dict(spec):
    if type(spec.experiment) is not ERExperiment:
        raise ConfigError("ER model requires its explicit controls")
    raw = chemistry.to_dict(chemistry_spec(spec))
    raw["model"]["id"] = MODEL_ID
    membrane = asdict(spec.model.membrane)
    species = [s.id for s in spec.model.species]
    membrane["permeability_m_per_s"] = dict(
        zip(species, membrane["permeability_m_per_s"], strict=True)
    )
    raw["model"]["membrane"] = membrane
    del raw["experiment"]["reaction_controls"]
    raw["experiment"]["controls"] = [
        {
            "time": p.time,
            "reactions": dict(zip((r.id for r in spec.model.reactions), p.reactions, strict=True)),
            "passive": dict(zip(species, p.passive, strict=True)),
            "pump": p.pump,
            "release": p.release,
        }
        for p in spec.experiment.changes
    ]
    return raw


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
            "membrane",
        },
        "ER model",
    )
    experiment = _fields(
        data["experiment"], {"end_time", "observation_times", "controls"}, "ER experiment"
    )
    controls = experiment["controls"]
    if not isinstance(controls, list) or not controls:
        raise ConfigError("ER controls must start at time zero")
    for p in controls:
        _fields(p, {"time", "reactions", "passive", "pump", "release"}, "ER control")
    base_data = {
        "model": {k: v for k, v in raw.items() if k != "membrane"} | {"id": chemistry.MODEL_ID},
        "experiment": {
            "end_time": experiment["end_time"],
            "observation_times": experiment["observation_times"],
            "reaction_controls": [
                {"time": p["time"], "multipliers": p["reactions"]} for p in controls
            ],
        },
        "execution": data["execution"],
    }
    base = chemistry.parse(base_data)
    if (
        raw["id"] != MODEL_ID
        or len(base.model.compartments) != 2
        or not 200 <= base.model.temperature_K <= 400
    ):
        raise ConfigError("ER requires exactly two finite compartments and 200–400 K")
    m = _fields(raw["membrane"], {f.name for f in fields(ERMembrane)}, "ER membrane")
    cy, er, ca = (identifier(m[k]) for k in ("cytosol", "er", "calcium_species"))
    if cy == er or {cy, er} != {c.id for c in base.model.compartments}:
        raise ConfigError("ER membrane must bind its two distinct declared compartments")
    ids = [s.id for s in base.model.species]
    if ca not in ids or base.model.species[ids.index(ca)].valence != 2:
        raise ConfigError("ER calcium role requires a declared divalent species")
    _fields(m["permeability_m_per_s"], set(ids), "ER permeability")
    bound = chemistry.bounded
    pump = m["pump"]
    if pump is not None:
        _fields(pump, {f.name for f in fields(ERPump)}, "ER pump")
        if pump["law"] != PUMP_LAW or pump["metabolism"] != METABOLISM:
            raise ConfigError("ER pump requires its named BETSE law and maintained mM quotient")
        drive = signed_number(pump["delta_g0_J_per_mol"], "ER hydrolysis potential")
        if abs(drive) > 100000:
            raise ConfigError("ER hydrolysis potential exceeds the bounded domain")
        pump = ERPump(
            PUMP_LAW,
            bound(pump["capacity_fmol_per_s"], "pump capacity", 0, 1e3),
            *(bound(pump[k], k, 1e-9, 1e3) for k in ("km_ca_mM", "km_atp_mM")),
            METABOLISM,
            *(bound(pump[k], k, 1e-9, 1e3) for k in ("atp_mM", "adp_mM", "pi_mM")),
            drive,
        )
    release = m["release"]
    if release is not None:
        _fields(release, {f.name for f in fields(ERRelease)}, "ER release")
        if release["law"] != RELEASE_LAW:
            raise ConfigError("ER release requires its named calcium-only BETSE law")
        release = ERRelease(
            RELEASE_LAW,
            bound(release["permeability_m_per_s"], "release permeability", 0, 1e-3),
            bound(release["activation_mM"], "activation_mM", 1e-9, 1e3),
            _integer(release["activation_n"], "activation_n", maximum=8),
            bound(release["inhibition_mM"], "inhibition_mM", 1e-9, 1e3),
            _integer(release["inhibition_n"], "inhibition_n", maximum=8),
        )
    voltage = signed_number(m["initial_voltage_V"], "ER voltage")
    if abs(voltage) > 0.15:
        raise ConfigError("ER voltage is outside ±0.15 V")
    membrane = ERMembrane(
        identifier(m["id"]),
        cy,
        er,
        ca,
        bound(m["area_m2"], "area_m2", 1e-12, 1e-6),
        bound(m["specific_capacitance_F_per_m2"], "capacitance density", 1e-4, 1),
        voltage,
        tuple(bound(m["permeability_m_per_s"][s], "permeability", 0, 1e-3) for s in ids),
        pump,
        release,
    )
    changes = []
    for p, reaction in zip(controls, base.experiment.changes, strict=True):
        _fields(p["passive"], set(ids), "ER passive availability")
        changes.append(
            ERChange(
                reaction.time,
                reaction.multipliers,
                tuple(bound(p["passive"][s], "passive multiplier", 0, 1) for s in ids),
                bound(p["pump"], "pump multiplier", 0, 1),
                bound(p["release"], "release multiplier", 0, 1),
            )
        )
    spec = SimulationSpec(
        ERModel(**vars(base.model), membrane=membrane),
        ERExperiment(base.experiment.end_time, base.experiment.observation_times, tuple(changes)),
        base.execution,
    )
    from cells.models.er_calcium import check_definition

    check_definition(spec)
    return spec
