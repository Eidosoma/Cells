"""Strict finite water owners on fixed resolved ionic interfaces.

Impermeant osmolyte amounts are explicit and independent of fixed charge. The
compliant volumes do not change interface geometry, and this Cells extension
does not establish native BETSE volume-trajectory correspondence.
"""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_tissue_spec as prior
from cells.core.bioelectric_spec import positive, signed_number
from cells.core.multispecies_spec import identifier
from cells.core.specs import ChannelChange, ConfigError, _fields, _number
from cells.core.voltage_gated_spec import fraction

MODEL_ID = "resolved_water@1"


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
class WaterMembrane:
    membrane_id: str
    hydraulic_permeability_m_per_Pa_s: float


@dataclass(frozen=True)
class SurfaceWaterModel(prior.SurfaceTissueModel):
    water_compartments: tuple[WaterCompartment, ...]
    water_membranes: tuple[WaterMembrane, ...]


class Control(NamedTuple):
    membrane: object
    junction: object
    water: object


@dataclass(frozen=True)
class Change(prior.SurfaceChange):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.SurfaceExperiment):
    water: tuple[tuple[ChannelChange, ...], ...]

    @property
    def changes(self):
        families = (self.membranes, self.junctions, self.water)
        times = sorted({0.0, *(c.time for family in families for g in family for c in g)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        g[bisect_right([c.time for c in g], time) - 1].availability for g in family
                    )
                    for family in families
                ),
            )
            for time in times
        )


def prior_spec(spec):
    """Remove water declarations and controls while retaining all ionic inputs."""
    return replace(
        spec,
        model=prior.SurfaceTissueModel(
            **{k: getattr(spec.model, k) for k in prior.SurfaceTissueModel.__dataclass_fields__}
        ),
        experiment=prior.SurfaceExperiment(
            **{k: getattr(spec.experiment, k) for k in prior.SurfaceExperiment.__dataclass_fields__}
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceWaterModel or type(spec.experiment) is not Experiment:
        raise ConfigError("Resolved water requires its own model and experiment")
    raw = prior.to_dict(prior_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        water_compartments=[asdict(p) for p in spec.model.water_compartments],
        water_membranes=[asdict(p) for p in spec.model.water_membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=p.id, schedule=[asdict(c) for c in group])
        for p, group in zip(spec.model.membranes, spec.experiment.water, strict=True)
    ]
    return raw


def _ordered_rows(rows, fields, id_field, ids, name):
    if type(rows) is not list:
        raise ConfigError(name + " declarations require an explicit list")
    mapped = {}
    for row in rows:
        _fields(row, fields, name)
        key = identifier(row[id_field])
        if key in mapped:
            raise ConfigError("Duplicate " + name + " ID")
        mapped[key] = row
    if set(mapped) != set(ids):
        raise ConfigError(name + " IDs must exactly match their ionic owners or membranes")
    return tuple(mapped[key] for key in ids)


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    if type(data["schema_version"]) is not int or data["schema_version"] != 1:
        raise ConfigError("Only schema_version 1 is supported")
    raw = deepcopy(data)
    m = _fields(
        raw["model"],
        {
            "id",
            "species",
            "temperature_K",
            "cells",
            "extracellular",
            "membranes",
            "junctions",
            "faces",
            "closure",
            "water_compartments",
            "water_membranes",
        },
        "resolved water model",
    )
    e = _fields(
        raw["experiment"],
        {
            "end_time",
            "observation_times",
            "membrane_controls",
            "junction_controls",
            "water_controls",
        },
        "resolved water experiment",
    )
    if m["id"] != MODEL_ID:
        raise ConfigError("Require resolved_water@1")
    compartments = m.pop("water_compartments")
    membranes = m.pop("water_membranes")
    controls = e.pop("water_controls")
    m["id"] = prior.MODEL_ID
    original = prior.parse(raw)
    base = original.model
    if any(p.reservoir for p in base.extracellular):
        raise ConfigError("Resolved water requires finite closed outside owners: reservoir=false")
    owners = (*base.cells, *base.extracellular)
    owner_ids = tuple(p.id for p in owners)
    patches = tuple(p.id for p in base.membranes)
    rows = _ordered_rows(
        compartments,
        set(WaterCompartment.__dataclass_fields__),
        "compartment_id",
        owner_ids,
        "water compartment",
    )
    water_compartments = []
    for p, owner in zip(rows, owners, strict=True):
        reference, minimum, maximum = (
            positive(p[k], k)
            for k in ("reference_volume_pL", "minimum_volume_pL", "maximum_volume_pL")
        )
        if not (minimum < owner.volume_pL < maximum and minimum < reference < maximum):
            raise ConfigError("Initial and reference water volumes must lie strictly within bounds")
        water_compartments.append(
            WaterCompartment(
                owner.id,
                reference,
                minimum,
                maximum,
                _number(p["impermeant_amount_fmol"], "impermeant osmolyte amount"),
                _number(p["bulk_modulus_Pa"], "water bulk modulus"),
                signed_number(p["pressure_offset_Pa"], "water pressure offset"),
            )
        )
    rows = _ordered_rows(
        membranes,
        set(WaterMembrane.__dataclass_fields__),
        "membrane_id",
        patches,
        "water membrane",
    )
    water_membranes = tuple(
        WaterMembrane(
            p["membrane_id"],
            _number(p["hydraulic_permeability_m_per_Pa_s"], "hydraulic permeability"),
        )
        for p in rows
    )
    rows = _ordered_rows(
        controls,
        {"membrane_id", "schedule"},
        "membrane_id",
        patches,
        "water control",
    )
    schedules = []
    for p in rows:
        changes = p["schedule"]
        if type(changes) is not list or not changes:
            raise ConfigError("Each water membrane requires a nonempty control schedule")
        for c in changes:
            _fields(c, {"time", "availability"}, "water control change")
        values = tuple(
            ChannelChange(
                _number(c["time"], "water control time"),
                fraction(c["availability"], "water availability"),
            )
            for c in changes
        )
        if (
            values[0].time != 0
            or any(c.time > original.experiment.end_time for c in values)
            or any(b.time <= a.time for a, b in zip(values, values[1:], strict=False))
        ):
            raise ConfigError("Water controls must start at zero and increase within the horizon")
        schedules.append(values)
    spec = replace(
        original,
        model=SurfaceWaterModel(
            **vars(base),
            water_compartments=tuple(water_compartments),
            water_membranes=water_membranes,
        ),
        experiment=Experiment(**vars(original.experiment), water=tuple(schedules)),
    )
    from cells.models.surface_water import check_definition

    try:
        check_definition(spec)
    except (ArithmeticError, ValueError) as error:
        raise ConfigError("Invalid resolved water definition: " + str(error)) from error
    return spec
