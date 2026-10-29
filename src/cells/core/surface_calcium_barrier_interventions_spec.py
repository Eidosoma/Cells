"""Scheduled ECM coefficients for exactly the complete calcium full56 owner."""

from dataclasses import dataclass, fields, replace

from cells.core import surface_barrier_interventions_binding as native
from cells.core import surface_calcium_spec as parent
from cells.core.specs import ConfigError, SimulationSpec

MODEL_ID = "resolved_calcium_extracellular_barriers@1"
PARENT_MODEL_ID = parent.HCN_EXTRA_MODEL_ID
TIMING_POLICY = native.TIMING_POLICY
Event = native.Event
bindings = native.bindings


@dataclass(frozen=True)
class SurfaceCalciumBarrierInterventionModel(parent.SurfaceCalciumHCNExtraModel):
    barrier_preparation: dict
    intervention: Event | None
    phase: str
    timing_policy: str


@dataclass(frozen=True)
class Execution(parent.Execution):
    barrier_target_capacity: int = 0


def owner_spec(spec):
    return replace(
        spec,
        model=parent.SurfaceCalciumHCNExtraModel(
            **{
                f.name: getattr(spec.model, f.name)
                for f in fields(parent.SurfaceCalciumHCNExtraModel)
            }
        ),
        execution=parent.Execution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(parent.Execution)}
        ),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumBarrierInterventionModel
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Require exact complete-owner barrier model/execution types")
    return native.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra, event, capacity = native.parse_owner(
        data, MODEL_ID, PARENT_MODEL_ID, parent.parse
    )
    spec = SimulationSpec(
        SurfaceCalciumBarrierInterventionModel(
            **vars(ordinary.model),
            barrier_preparation=extra["barrier_preparation"],
            intervention=event,
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
        ),
        ordinary.experiment,
        Execution(**vars(ordinary.execution), barrier_target_capacity=capacity),
    )
    try:
        bindings(spec.model, spec.execution)
        from cells.models.surface_calcium_barrier_interventions import check_definition

        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete calcium scheduled barrier definition: " + str(error)
        ) from error
    return spec


def artifact(spec):
    return native.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID)


def replay(record):
    return native.replay(record, parse, artifact, MODEL_ID, PARENT_MODEL_ID)
