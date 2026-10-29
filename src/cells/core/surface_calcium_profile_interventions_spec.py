"""Scheduled background plasma D for exactly the complete calcium @6 owner."""

from dataclasses import dataclass, fields, replace

from cells.core import owned_calcium_profile_binding as native
from cells.core import surface_calcium_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_calcium_membrane_profiles@1"
PARENT_MODEL_ID = parent.CAV_MODEL_ID
TIMING_POLICY = native.TIMING_POLICY
RESET_POLICY = native.RESET_POLICY
bindings = native.bindings


@dataclass(frozen=True)
class SurfaceCalciumProfileInterventionModel(parent.SurfaceCalciumCavModel):
    profile_preparation: dict
    interventions: tuple
    phase: str
    timing_policy: str
    reset_policy: str


@dataclass(frozen=True)
class Execution(parent.Execution):
    intervention_capacity: int = 0
    intervention_target_capacity: int = 0


def owner_spec(spec):
    return replace(
        spec,
        model=parent.SurfaceCalciumCavModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(parent.SurfaceCalciumCavModel)}
        ),
        execution=parent.Execution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(parent.Execution)}
        ),
    )


def to_dict(spec):
    return native.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra, events, ec, tc = native.parse_owner(
        data, MODEL_ID, PARENT_MODEL_ID, parent.parse
    )
    spec = SimulationSpec(
        SurfaceCalciumProfileInterventionModel(
            **vars(ordinary.model),
            profile_preparation=extra["profile_preparation"],
            interventions=events,
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
            reset_policy=RESET_POLICY,
        ),
        ordinary.experiment,
        Execution(
            **vars(ordinary.execution), intervention_capacity=ec, intervention_target_capacity=tc
        ),
    )
    try:
        native.bindings(spec.model, spec.execution)
        from cells.models.surface_calcium_profile_interventions import check_definition

        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid complete calcium profile definition: " + str(error)) from error
    return spec


def artifact(spec):
    return native.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID)


def replay(record):
    return native.replay(record, parse, artifact, MODEL_ID, PARENT_MODEL_ID)
