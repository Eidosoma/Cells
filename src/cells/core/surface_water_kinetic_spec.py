"""Finite compliant volumes with the existing shared-channel/ATPase catalog."""

from bisect import bisect_right
from copy import deepcopy
from dataclasses import asdict, dataclass, replace
from typing import NamedTuple

from cells.core import surface_kinetic_spec as prior
from cells.core import surface_water_spec as water
from cells.core.specs import ConfigError, _fields

MODEL_ID = "resolved_water@2"
MORRIS_LECAR_MODEL_ID = "resolved_water@3"


@dataclass(frozen=True)
class SurfaceWaterKineticModel(prior.SurfaceCavModel):
    water_compartments: tuple[water.WaterCompartment, ...]
    water_membranes: tuple[water.WaterMembrane, ...]


@dataclass(frozen=True)
class SurfaceWaterMorrisLecarModel(SurfaceWaterKineticModel):
    """53 shared laws sensing current compliant-volume concentrations."""


def model_id(model):
    return MORRIS_LECAR_MODEL_ID if isinstance(model, SurfaceWaterMorrisLecarModel) else MODEL_ID


class Control(NamedTuple):
    membrane: object
    junction: object
    channel: object
    pump: object
    water: object


@dataclass(frozen=True)
class Change(prior.Change):
    water: tuple[float, ...]


@dataclass(frozen=True)
class Experiment(prior.Experiment):
    water: tuple

    @property
    def changes(self):
        families = (self.membranes, self.junctions, self.channels, self.pumps, self.water)
        times = sorted({0.0, *(c.time for family in families for group in family for c in group)})
        return tuple(
            Change(
                time,
                *(
                    tuple(
                        group[bisect_right([c.time for c in group], time) - 1].availability
                        for group in family
                    )
                    for family in families
                ),
            )
            for time in times
        )


def prior_spec(spec):
    """Lossless ionic projection preserving the versioned channel catalog."""
    kind = (
        prior.SurfaceMorrisLecarModel
        if isinstance(spec.model, SurfaceWaterMorrisLecarModel)
        else prior.SurfaceCavModel
    )
    return replace(
        spec,
        model=kind(**{k: getattr(spec.model, k) for k in kind.__dataclass_fields__}),
        experiment=prior.Experiment(
            **{k: getattr(spec.experiment, k) for k in prior.Experiment.__dataclass_fields__}
        ),
    )


def water_spec(spec):
    """Project passive ions and the same volume owners onto resolved_water@1."""
    passive = prior.passive_spec(prior_spec(spec))
    return replace(
        passive,
        model=water.SurfaceWaterModel(
            **vars(passive.model),
            water_compartments=spec.model.water_compartments,
            water_membranes=spec.model.water_membranes,
        ),
        experiment=water.Experiment(**vars(passive.experiment), water=spec.experiment.water),
    )


def to_dict(spec):
    if (
        type(spec.model) not in (SurfaceWaterKineticModel, SurfaceWaterMorrisLecarModel)
        or type(spec.experiment) is not Experiment
    ):
        raise ConfigError("Active water requires its own model and experiment")
    raw = prior.to_dict(prior_spec(spec))
    raw["model"].update(
        id=model_id(spec.model),
        water_compartments=[asdict(row) for row in spec.model.water_compartments],
        water_membranes=[asdict(row) for row in spec.model.water_membranes],
    )
    raw["experiment"]["water_controls"] = [
        dict(membrane_id=patch.id, schedule=[asdict(c) for c in group])
        for patch, group in zip(spec.model.membranes, spec.experiment.water, strict=True)
    ]
    return raw


def parse(data):
    _fields(data, {"schema_version", "model", "experiment", "execution"}, "definition")
    raw = deepcopy(data)
    if not isinstance(raw["model"], dict) or raw["model"].get("id") not in (
        MODEL_ID,
        MORRIS_LECAR_MODEL_ID,
    ):
        raise ConfigError("Require resolved_water@2/@3")
    added = raw["model"]["id"] == MORRIS_LECAR_MODEL_ID
    try:
        compartments = raw["model"].pop("water_compartments")
        membranes = raw["model"].pop("water_membranes")
        controls = raw["experiment"].pop("water_controls")
    except (KeyError, TypeError, AttributeError) as error:
        raise ConfigError(
            "Active water requires explicit water owners, interfaces and controls"
        ) from error
    raw["model"]["id"] = prior.MORRIS_LECAR_MODEL_ID if added else prior.CAV_MODEL_ID
    original = prior.parse(raw)
    passive = prior.passive_spec(original).to_dict()
    passive["model"].update(
        id=water.MODEL_ID, water_compartments=compartments, water_membranes=membranes
    )
    passive["experiment"]["water_controls"] = controls
    validated = water.parse(passive)
    spec = replace(
        original,
        model=(SurfaceWaterMorrisLecarModel if added else SurfaceWaterKineticModel)(
            **vars(original.model),
            water_compartments=validated.model.water_compartments,
            water_membranes=validated.model.water_membranes,
        ),
        experiment=Experiment(**vars(original.experiment), water=validated.experiment.water),
    )
    from cells.models import surface_water_kinetic

    try:
        surface_water_kinetic.check_definition(spec)
    except (ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid active water definition: " + str(error)) from error
    return spec
