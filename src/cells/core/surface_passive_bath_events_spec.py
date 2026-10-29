"""Ideal-bath programming around the exact resolved passive tissue owner."""

from dataclasses import dataclass, fields, replace

from cells.core import surface_bath_events_binding as binding
from cells.core import surface_tissue_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_passive_bath_events@1"
PARENT_MODEL_ID = parent.MODEL_ID
TIMING_POLICY = binding.TIMING_POLICY


@dataclass(frozen=True)
class SurfacePassiveBathEventModel(parent.SurfaceTissueModel):
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
        model=parent.SurfaceTissueModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(parent.SurfaceTissueModel)}
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfacePassiveBathEventModel:
        raise ConfigError("Require the exact passive bath owner")
    return binding.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra = binding.parse_owner(data, MODEL_ID, PARENT_MODEL_ID, parent.parse)
    spec = SimulationSpec(
        SurfacePassiveBathEventModel(**vars(ordinary.model), **extra),
        ordinary.experiment,
        ordinary.execution,
    )
    try:
        from cells.models.surface_passive_bath_events import check_definition

        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid passive bath definition: " + str(error)) from error
    return spec


def artifact(spec):
    from cells.models.surface_passive_bath_events import initial_operation

    return binding.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID, initial_operation(spec))


def replay(record):
    return binding.replay(record, parse, artifact)
