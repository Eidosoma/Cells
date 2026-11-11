"""resolved_pump_water@1: resolved_pump_tissue@3 plus osmotic water and compliant volumes.

Every field of resolved_pump_tissue@3 keeps its meaning and is parsed by that
identity's own parser. The model adds ``water``:

* ``law``: the water law, numerics/osmotic_water.LAW_ID (ideal van 't Hoff
  osmotic pressure with a linear compliance; docs/WATER_VOLUME_REFERENCE.md);
* ``compartments``: one row per cell and per finite (non-reservoir) outside
  node: reference, minimum and maximum volume (pL), the amount of *neutral*
  impermeant osmolytes beyond the declared species (fmol), the linear modulus
  (Pa) and the pressure offset (Pa). Declared species, including impermeant
  charged ones, already count through their amounts and are never counted again;
* ``baths``: one row per reservoir (held bath) with its hydrostatic pressure (Pa).
  A held bath keeps its composition and volume, so its water potential
  P - RT sum(c) is fixed: it supplies or takes water at that potential;
* ``membranes``: one row per membrane patch with its hydraulic permeability Lp
  (m/(Pa s)); Lp = Pf Vw / (R T) for an osmotic permeability Pf.

Water crosses membranes only: no water route on junctions (gap-junction flow
is convection carrying solute) or extracellular faces (pure solvent flow
between free-solution nodes has no physical semipermeable barrier). The
experiment adds ``water_controls``: one availability schedule per membrane
(aquaporin block, sealing, release), joining the event union. Membrane areas,
capacitances and every other @3 coefficient stay fixed (docs/PUMP_WATER_MODEL.md).
"""

import copy
from bisect import bisect_right
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

import numpy as np

from cells.core import surface_pump_spec as first
from cells.core import surface_pump_v2_spec as second
from cells.core import surface_pump_v3_spec as ionic
from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _number
from cells.numerics.osmotic_water import LAW_ID as WATER_LAW_ID

MODEL_ID = "resolved_pump_water@1"
COMPARTMENT_FIELDS = (
    "compartment_id",
    "reference_volume_pL",
    "minimum_volume_pL",
    "maximum_volume_pL",
    "impermeant_amount_fmol",
    "bulk_modulus_Pa",
    "pressure_offset_Pa",
)


@dataclass(frozen=True)
class WaterCompartment:
    compartment_id: str
    reference_volume_pL: float
    minimum_volume_pL: float
    maximum_volume_pL: float
    impermeant_amount_fmol: float
    bulk_modulus_Pa: float
    pressure_offset_Pa: float


@dataclass(frozen=True)
class WaterBath:
    compartment_id: str
    hydrostatic_pressure_Pa: float


@dataclass(frozen=True)
class WaterMembrane:
    membrane_id: str
    hydraulic_permeability_m_per_Pa_s: float


@dataclass(frozen=True)
class Water:
    law: str
    compartments: tuple[WaterCompartment, ...]  # Cells, then finite outside nodes.
    baths: tuple[WaterBath, ...]  # Reservoirs, in outside order.
    membranes: tuple[WaterMembrane, ...]  # Membrane order.


@dataclass(frozen=True)
class SurfacePumpWaterModel:
    species_ids: tuple[str, ...]
    valence: tuple[int, ...]
    temperature_K: float
    cells: tuple
    extracellular: tuple
    membranes: tuple
    junctions: tuple
    faces: tuple
    gauge_reference: str | None
    channels: tuple
    water: Water


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    calcium_pump: object
    water: object  # [..., membrane_capacity]; padding stays zero.


@dataclass(frozen=True)
class Change(second.Change):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(ionic.Experiment):
    """@3's experiment plus one water availability schedule per membrane."""

    water: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        groups = (
            self.membranes,
            self.junctions,
            self.channels,
            self.pumps,
            self.calcium_pumps,
            self.water,
        )
        times = sorted({0.0, *(c.time for family in groups for g in family for c in g)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        g[bisect_right([p.time for p in g], time) - 1].availability for g in family
                    )
                    for family in groups
                ),
            )
            for time in times
        )


def projection(spec):
    """The resolved_pump_tissue@3 part of a definition (no water declarations)."""
    m, e = spec.model, spec.experiment
    model = ionic.SurfacePumpChannelModel(
        **{k: getattr(m, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__}
    )
    experiment = ionic.Experiment(
        **{k: getattr(e, k) for k in ionic.Experiment.__dataclass_fields__}
    )
    return replace(spec, model=model, experiment=experiment)


def to_dict(spec):
    m, e = spec.model, spec.experiment
    if type(m) is not SurfacePumpWaterModel or type(e) is not Experiment:
        raise ConfigError("Resolved pump water requires its own model and experiment")
    w = m.water
    if (
        type(w) is not Water
        or any(type(p) is not WaterCompartment for p in w.compartments)
        or any(type(p) is not WaterBath for p in w.baths)
        or any(type(p) is not WaterMembrane for p in w.membranes)
    ):
        raise ConfigError("Require explicit immutable water declaration types")
    raw = ionic.to_dict(projection(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["water"] = dict(
        law=w.law,
        compartments=[asdict(p) for p in w.compartments],
        baths=[asdict(p) for p in w.baths],
        membranes=[asdict(p) for p in w.membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=p.id, schedule=[asdict(c) for c in g])
        for p, g in zip(m.membranes, e.water, strict=True)
    ]
    return raw


def _rows(rows, fields, key, ids, name):
    """Declaration rows keyed by `key`, exactly one per expected ID, in ID order."""
    if type(rows) is not list:
        raise ConfigError(name + " declarations require an explicit list")
    mapped = {}
    for row in rows:
        _fields(row, set(fields), name)
        k = identifier(row[key])
        if k in mapped:
            raise ConfigError("Duplicate " + name + " ID")
        mapped[k] = row
    if set(mapped) != set(ids):
        raise ConfigError(name + " IDs must exactly match their owners")
    return [mapped[k] for k in ids]


def parse_water(raw, base):
    _fields(raw, {"law", "compartments", "baths", "membranes"}, "water")
    if raw["law"] != WATER_LAW_ID:
        raise ConfigError("Water requires law " + WATER_LAW_ID)
    m = base.model
    finite = [p for p in m.extracellular if not p.reservoir]
    owners = (*m.cells, *finite)
    compartments = []
    rows = _rows(
        raw["compartments"],
        COMPARTMENT_FIELDS,
        "compartment_id",
        [p.id for p in owners],
        "water compartment",
    )
    for row, owner in zip(rows, owners, strict=True):
        reference, minimum, maximum = (
            positive(row[k], k)
            for k in ("reference_volume_pL", "minimum_volume_pL", "maximum_volume_pL")
        )
        if not (minimum < owner.volume_pL < maximum and minimum < reference < maximum):
            raise ConfigError("Initial and reference water volumes must lie strictly within bounds")
        compartments.append(
            WaterCompartment(
                owner.id,
                reference,
                minimum,
                maximum,
                _number(row["impermeant_amount_fmol"], "neutral impermeant amount"),
                _number(row["bulk_modulus_Pa"], "water bulk modulus"),
                signed_number(row["pressure_offset_Pa"], "water pressure offset"),
            )
        )
    rows = _rows(
        raw["baths"],
        ("compartment_id", "hydrostatic_pressure_Pa"),
        "compartment_id",
        [p.id for p in m.extracellular if p.reservoir],
        "water bath",
    )
    baths = tuple(
        WaterBath(
            row["compartment_id"], signed_number(row["hydrostatic_pressure_Pa"], "bath pressure")
        )
        for row in rows
    )
    membranes = tuple(
        WaterMembrane(
            row["membrane_id"],
            _number(row["hydraulic_permeability_m_per_Pa_s"], "hydraulic permeability"),
        )
        for row in _rows(
            raw["membranes"],
            ("membrane_id", "hydraulic_permeability_m_per_Pa_s"),
            "membrane_id",
            [p.id for p in m.membranes],
            "water membrane",
        )
    )
    return Water(WATER_LAW_ID, tuple(compartments), baths, membranes)


def parse(data):
    raw = copy.deepcopy(data)
    m, e = raw.get("model"), raw.get("experiment")
    if not isinstance(m, dict) or not isinstance(e, dict) or m.get("id") != MODEL_ID:
        raise ConfigError("Require resolved_pump_water@1")
    if "water" not in m or "water_controls" not in e:
        raise ConfigError("Declare water and water_controls")
    water, controls = m.pop("water"), e.pop("water_controls")
    m["id"] = ionic.MODEL_ID
    base = ionic.parse(raw)
    declared = parse_water(water, base)
    ids = [p.id for p in base.model.membranes]
    schedules = first._schedules(controls, "membrane", ids, base.experiment.end_time)
    model = SurfacePumpWaterModel(
        **{k: getattr(base.model, k) for k in ionic.SurfacePumpChannelModel.__dataclass_fields__},
        water=declared,
    )
    experiment = Experiment(
        **{k: getattr(base.experiment, k) for k in ionic.Experiment.__dataclass_fields__},
        water=tuple(schedules[i] for i in ids),
    )
    spec = replace(base, model=model, experiment=experiment)
    from cells.models.surface_pump_water import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved pump water definition: " + str(error)) from error
    return spec


def control_values(spec, times):
    """resolved_pump_tissue@3 controls plus the water availabilities (padded to membranes)."""
    base = ionic.control_values(projection(spec), times)
    changes = spec.experiment.changes
    indices = np.searchsorted([c.time for c in changes], times, side="right") - 1
    values = np.asarray([c.water for c in changes], dtype=np.float64)
    padded = np.zeros((len(times), spec.execution.membrane_capacity))
    padded[:, : values.shape[-1]] = values[indices]
    return Control(*base, padded)
