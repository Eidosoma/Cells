"""Scheduled ECM coefficients for exactly the complete water_repair full56 owner."""

from dataclasses import dataclass, fields, replace

from cells.core import surface_barrier_interventions_binding as native
from cells.core import surface_calcium_energy_water_repair_hcn_extra_spec as parent
from cells.core.specs import ConfigError, SimulationSpec
from cells.core.surface_calcium_energy_spec import Execution as ParentExecution

MODEL_ID = "resolved_calcium_energy_water_repair_extracellular_barriers@1"
PARENT_MODEL_ID = parent.MODEL_ID
TIMING_POLICY = native.TIMING_POLICY
Event = native.Event
bindings = native.bindings


@dataclass(frozen=True)
class SurfaceCalciumEnergyWaterRepairBarrierInterventionModel(
    parent.SurfaceCalciumEnergyWaterRepairHCNExtraModel
):
    barrier_preparation: dict
    intervention: Event | None
    phase: str
    timing_policy: str


@dataclass(frozen=True)
class Execution(ParentExecution):
    barrier_target_capacity: int = 0


def owner_spec(spec):
    return replace(
        spec,
        model=parent.SurfaceCalciumEnergyWaterRepairHCNExtraModel(
            **{
                f.name: getattr(spec.model, f.name)
                for f in fields(parent.SurfaceCalciumEnergyWaterRepairHCNExtraModel)
            }
        ),
        execution=ParentExecution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(ParentExecution)}
        ),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyWaterRepairBarrierInterventionModel
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Require exact complete-owner barrier model/execution types")
    return native.augment(parent.to_dict(owner_spec(spec)), spec, MODEL_ID)


def parse(data):
    ordinary, extra, event, capacity = native.parse_owner(
        data, MODEL_ID, PARENT_MODEL_ID, parent.parse
    )
    spec = SimulationSpec(
        SurfaceCalciumEnergyWaterRepairBarrierInterventionModel(
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
        from cells.models.surface_calcium_energy_water_repair_barrier_interventions import (
            check_definition,
        )

        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError(
            "Invalid complete water_repair scheduled barrier definition: " + str(error)
        ) from error
    return spec


def artifact(spec):
    return native.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID)


def replay(record):
    return native.replay(record, parse, artifact, MODEL_ID, PARENT_MODEL_ID)
