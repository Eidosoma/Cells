"""Ideal-bath programming around the complete 56-law ionic owner."""

from dataclasses import dataclass, fields, replace

from cells.core import surface_bath_events_binding as binding
from cells.core import surface_kinetic_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_active_bath_events@1"
PARENT_MODEL_ID = parent.HCN_EXTRA_MODEL_ID
TIMING_POLICY = binding.TIMING_POLICY


@dataclass(frozen=True)
class SurfaceActiveBathEventModel(parent.SurfaceHCNExtraModel):
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
        model=parent.SurfaceHCNExtraModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(parent.SurfaceHCNExtraModel)}
        ),
    )


def to_dict(spec):
    if type(spec.model) is not SurfaceActiveBathEventModel:
        raise ConfigError("Require the exact complete ionic bath owner")
    return binding.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra = binding.parse_owner(data, MODEL_ID, PARENT_MODEL_ID, parent.parse)
    spec = SimulationSpec(
        SurfaceActiveBathEventModel(**vars(ordinary.model), **extra),
        ordinary.experiment,
        ordinary.execution,
    )
    try:
        from cells.models.surface_active_bath_events import check_definition

        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid complete ionic bath definition: " + str(error)) from error
    return spec


def artifact(spec):
    from cells.models.surface_active_bath_events import initial_operation

    return binding.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID, initial_operation(spec))


def replay(record):
    return binding.replay(record, parse, artifact)
