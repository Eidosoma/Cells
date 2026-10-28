"""Prescribed Na/K injury on the live calcium, fuel and compliant-water owners."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_calcium_energy_water_spec as base
from cells.core.reaction_spec import bounded
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, _fields
from cells.core.surface_calcium_spec import ordered
from cells.core.surface_repair_spec import Intervention, Patch
from cells.processes.membrane_injury import LAW_ID

MODEL_ID = "resolved_calcium_energy_water_repair@1"


@dataclass(frozen=True)
class SurfaceCalciumEnergyWaterRepairModel(base.SurfaceCalciumEnergyWaterModel):
    injury_patches: tuple[Patch, ...]


Control = NamedTuple(
    "SurfaceCalciumEnergyWaterRepairControl",
    [(k, object) for k in (*base.Control._fields, "injury", "resealing")],
)


@dataclass(frozen=True)
class Change(base.Change):
    injury: tuple[float, ...]
    resealing: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(base.Experiment):
    injury: tuple[tuple[Intervention, ...], ...]

    @property
    def changes(self):
        groups = (super().changes, *self.injury)
        clocks = [[p.time for p in group] for group in groups]
        result = []
        for time in sorted({t for clock in clocks for t in clock}):
            held = [g[bisect_right(c, time) - 1] for g, c in zip(groups, clocks, strict=True)]
            result.append(
                Change(
                    **(vars(held[0]) | {"time": time}),
                    injury=tuple(p.injury for p in held[1:]),
                    resealing=tuple(p.resealing for p in held[1:]),
                )
            )
        return tuple(result)


def base_spec(spec):
    return replace(
        spec,
        model=project(spec.model, base.SurfaceCalciumEnergyWaterModel),
        experiment=project(spec.experiment, base.Experiment),
    )


def accounting_spec(spec):
    """Permit the intact/injury ledger union for checks, without changing rates."""
    parent = base_spec(spec)
    return replace(
        parent,
        model=replace(
            parent.model,
            membranes=tuple(
                replace(
                    m,
                    permeability_m_per_s=tuple(
                        a + b
                        for a, b in zip(m.permeability_m_per_s, p.permeability_m_per_s, strict=True)
                    ),
                )
                for m, p in zip(parent.model.membranes, spec.model.injury_patches, strict=True)
            ),
        ),
    )


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"].update(
        id=MODEL_ID,
        injury_patches=[
            asdict(p)
            | {
                "permeability_m_per_s": dict(
                    zip(spec.model.species_ids, p.permeability_m_per_s, strict=True)
                )
            }
            for p in spec.model.injury_patches
        ],
    )
    raw["experiment"]["injury_controls"] = [
        dict(membrane_id=p.membrane_id, schedule=[asdict(c) for c in group])
        for p, group in zip(spec.model.injury_patches, spec.experiment.injury, strict=True)
    ]
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if not isinstance(raw["model"], dict) or raw["model"].get("id") != MODEL_ID:
        raise ConfigError("Require " + MODEL_ID)
    try:
        patches = raw["model"].pop("injury_patches")
        controls = raw["experiment"].pop("injury_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError("Joint repair requires explicit injury patches and controls") from error
    raw["model"]["id"] = base.MODEL_ID
    parent = base.parse(raw)
    mids, ids = [p.id for p in parent.model.membranes], parent.model.species_ids
    sodium, potassium = parent.model.sodium_species, "K"
    if potassium not in ids or parent.model.valence[ids.index(potassium)] != 1:
        raise ConfigError("Prescribed repair requires explicit K(+1) and owned Na(+1)")
    parsed = []
    for row in ordered(
        patches, "membrane_id", mids, set(Patch.__dataclass_fields__) - {"membrane_id"}
    ):
        if row["law"] != LAW_ID:
            raise ConfigError("Require the named prescribed injury/resealing law")
        permeability = _fields(row["permeability_m_per_s"], set(ids), "injury permeability")
        values = tuple(bounded(permeability[k], "injury permeability", 0, 1e-5) for k in ids)
        if any(v != 0 for k, v in zip(ids, values, strict=True) if k not in (sodium, potassium)):
            raise ConfigError("Prescribed injury routes are restricted to Na/K")
        parsed.append(
            Patch(
                row["membrane_id"],
                LAW_ID,
                bounded(row["initial_damage"], "initial damage", 0, 1),
                bounded(row["injury_rate_per_s"], "injury rate", 0, 1e5),
                bounded(row["resealing_rate_per_s"], "resealing rate", 0, 1e5),
                values,
            )
        )
    schedules = []
    for row in ordered(controls, "membrane_id", mids, {"schedule"}):
        if type(row["schedule"]) is not list or not row["schedule"]:
            raise ConfigError("Injury controls must start at zero")
        changes = []
        for item in row["schedule"]:
            _fields(item, {"time", "injury", "resealing"}, "injury intervention")
            t = bounded(item["time"], "injury time", 0, parent.experiment.end_time)
            if (not changes and t != 0) or (changes and t <= changes[-1].time):
                raise ConfigError("Injury control times must increase from zero")
            changes.append(
                Intervention(t, *(bounded(item[k], k, 0, 1) for k in ("injury", "resealing")))
            )
        schedules.append(tuple(changes))
    spec = replace(
        parent,
        model=SurfaceCalciumEnergyWaterRepairModel(
            **vars(parent.model), injury_patches=tuple(parsed)
        ),
        experiment=Experiment(**vars(parent.experiment), injury=tuple(schedules)),
    )
    from cells.models.surface_calcium_energy_water_repair import check_definition

    check_definition(spec)
    return spec
