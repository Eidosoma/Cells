"""Explicit scheduled ideal baths for the full56 open calcium owner."""

from dataclasses import dataclass, replace

from cells.core import open_calcium_bath_binding as binding
from cells.core import surface_bath_events_binding as bath
from cells.core import surface_open_calcium_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_open_calcium_bath_events@1"
PARENT_MODEL_ID = parent.MODEL_ID
TIMING_POLICY = bath.TIMING_POLICY


@dataclass(frozen=True)
class SurfaceOpenCalciumBathEventModel(parent.SurfaceOpenCalciumModel):
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
        model=parent.SurfaceOpenCalciumModel(
            **binding.owner_fields(spec.model, parent.SurfaceOpenCalciumModel)
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceOpenCalciumBathEventModel:
        raise ConfigError("Require the exact scheduled open calcium model")
    return binding.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra = binding.parse_owner(data, MODEL_ID, parent)
    values = vars(ordinary.model) | dict(exterior_policy=binding.EXTERIOR_POLICY)
    spec = SimulationSpec(
        SurfaceOpenCalciumBathEventModel(**values, **extra), ordinary.experiment, ordinary.execution
    )
    from cells.models.surface_open_calcium_bath_events import check_definition

    try:
        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid scheduled open calcium bath: " + str(error)) from error
    return spec


def artifact(spec):
    from cells.models.surface_open_calcium_bath_events import initial_operation

    return bath.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID, initial_operation(spec))


def replay(record):
    return bath.replay(record, parse, artifact)
