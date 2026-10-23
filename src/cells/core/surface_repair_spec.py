"""Fixed-geometry injury on owned calcium tissue, with explicit patch identities."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace

from cells.core import surface_calcium_spec as base
from cells.core.reaction_spec import bounded
from cells.core.spatial_calcium_spec import project
from cells.core.specs import ConfigError, SimulationSpec, _fields
from cells.processes.membrane_injury import LAW_ID

MODEL_ID = "resolved_repair@1"


@dataclass(frozen=True)
class Patch:
    membrane_id: str
    law: str
    initial_damage: float
    injury_rate_per_s: float
    resealing_rate_per_s: float
    permeability_m_per_s: tuple[float, ...]


@dataclass(frozen=True)
class SurfaceRepairModel(base.SurfaceCalciumCavModel):
    injury_patches: tuple[Patch, ...]


@dataclass(frozen=True)
class Intervention:
    time: float
    injury: float
    resealing: float


@dataclass(frozen=True)
class Change(base.Change):
    injury: tuple[float, ...]
    resealing: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(base.Experiment):
    injury: tuple[tuple[Intervention, ...], ...]

    @property
    def changes(self):
        original = super().changes
        groups = (original, *self.injury)
        clocks = [[p.time for p in g] for g in groups]
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
        model=project(spec.model, base.SurfaceCalciumCavModel),
        experiment=project(spec.experiment, base.Experiment),
    )


def accounting_spec(spec):
    """Permit the union of intact/injury ledger routes, without changing physics."""
    prior = base_spec(spec)
    return replace(
        prior,
        model=replace(
            prior.model,
            membranes=tuple(
                replace(
                    m,
                    permeability_m_per_s=tuple(
                        a + b
                        for a, b in zip(m.permeability_m_per_s, p.permeability_m_per_s, strict=True)
                    ),
                )
                for m, p in zip(prior.model.membranes, spec.model.injury_patches, strict=True)
            ),
        ),
    )


def to_dict(spec):
    raw = base.to_dict(base_spec(spec))
    raw["model"]["id"] = MODEL_ID
    raw["model"]["injury_patches"] = [
        asdict(p)
        | {
            "permeability_m_per_s": dict(
                zip(spec.model.species_ids, p.permeability_m_per_s, strict=True)
            )
        }
        for p in spec.model.injury_patches
    ]
    raw["experiment"]["injury_controls"] = [
        dict(membrane_id=p.membrane_id, schedule=[asdict(c) for c in g])
        for p, g in zip(spec.model.injury_patches, spec.experiment.injury, strict=True)
    ]
    return raw


def parse(data):
    raw = deepcopy(data)
    m, e = raw["model"], raw["experiment"]
    if m.get("id") != MODEL_ID or "injury_patches" not in m or "injury_controls" not in e:
        raise ConfigError("Resolved repair requires explicit injury patches and controls")
    patches, controls = m.pop("injury_patches"), e.pop("injury_controls")
    m["id"] = base.CAV_MODEL_ID
    prior = base.parse(raw)
    mids, ids = [p.id for p in prior.model.membranes], prior.model.species_ids
    # Initially restrict the lesion to the explicitly identified monovalent Na/K pair.
    na = prior.model.sodium_species
    potassium = "K"
    if potassium not in ids or prior.model.valence[ids.index(potassium)] != 1:
        raise ConfigError("Initial repair model requires explicit K(+1) and owned Na(+1)")
    rows = base.ordered(
        patches, "membrane_id", mids, set(Patch.__dataclass_fields__) - {"membrane_id"}
    )
    parsed = []
    for row in rows:
        if row["law"] != LAW_ID:
            raise ConfigError("Require the named prescribed injury/resealing law")
        permeability = _fields(row["permeability_m_per_s"], set(ids), "injury permeability")
        values = tuple(bounded(permeability[k], "injury permeability", 0, 1e-5) for k in ids)
        if any(v != 0 for k, v in zip(ids, values, strict=True) if k not in (na, potassium)):
            raise ConfigError("Initial injury routes are restricted to Na/K")
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
    for row in base.ordered(controls, "membrane_id", mids, {"schedule"}):
        if type(row["schedule"]) is not list or not row["schedule"]:
            raise ConfigError("Injury controls must start at zero")
        changes = []
        for item in row["schedule"]:
            _fields(item, {"time", "injury", "resealing"}, "injury intervention")
            t = bounded(item["time"], "injury time", 0, prior.experiment.end_time)
            if (not changes and t != 0) or (changes and t <= changes[-1].time):
                raise ConfigError("Injury control times must increase from zero")
            changes.append(
                Intervention(t, *(bounded(item[k], k, 0, 1) for k in ("injury", "resealing")))
            )
        schedules.append(tuple(changes))
    spec = SimulationSpec(
        SurfaceRepairModel(**vars(prior.model), injury_patches=tuple(parsed)),
        Experiment(**vars(prior.experiment), injury=tuple(schedules)),
        prior.execution,
    )
    from cells.models.surface_repair import check_definition

    check_definition(spec)
    return spec
