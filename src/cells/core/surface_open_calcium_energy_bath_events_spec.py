"""Explicit scheduled ideal baths with actual finite ATP/ADP/Pi feedback."""

from dataclasses import dataclass, replace

from cells.core import open_calcium_bath_binding as binding
from cells.core import surface_bath_events_binding as bath
from cells.core import surface_open_calcium_energy_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_open_calcium_energy_bath_events@1"
PARENT_MODEL_ID = parent.MODEL_ID
TIMING_POLICY = bath.TIMING_POLICY


@dataclass(frozen=True)
class SurfaceOpenCalciumEnergyBathEventModel(parent.SurfaceOpenCalciumEnergyModel):
    bath_events: tuple
    bath_site_ids: tuple
    enabled_Cl: bool
    phase: str
    timing_policy: str
    controller_policy: str
    baseline_policy: str


def owner_spec(spec):
    return replace(
        spec,
        model=parent.SurfaceOpenCalciumEnergyModel(
            **binding.owner_fields(spec.model, parent.SurfaceOpenCalciumEnergyModel)
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceOpenCalciumEnergyBathEventModel:
        raise ConfigError("Require the exact scheduled open calcium/fuel model")
    return binding.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra = binding.parse_owner(data, MODEL_ID, parent)
    values = vars(ordinary.model) | dict(exterior_policy=binding.EXTERIOR_POLICY)
    spec = SimulationSpec(
        SurfaceOpenCalciumEnergyBathEventModel(**values, **extra),
        ordinary.experiment,
        ordinary.execution,
    )
    from cells.models.surface_open_calcium_energy_bath_events import check_definition

    try:
        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid scheduled open calcium/fuel bath: " + str(error)) from error
    return spec


def artifact(spec):
    from cells.models.surface_open_calcium_energy_bath_events import initial_operation

    return bath.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID, initial_operation(spec))


def replay(record):
    return bath.replay(record, parse, artifact)
