"""Both native schedules on exactly the complete calcium_energy full56 owner."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace

from cells.core import owned_calcium_profile_barrier_binding as binding
from cells.core import surface_calcium_energy_barrier_interventions_spec as barrier
from cells.core import surface_calcium_energy_spec as parent
from cells.core.specs import ConfigError, SimulationSpec
from cells.core.tissue_profile_preparation import _json

MODEL_ID = "resolved_calcium_energy_profile_barriers@1"
PARENT_MODEL_ID = parent.HCN_EXTRA_MODEL_ID
TIMING_POLICY = binding.TIMING_POLICY
RESET_POLICY = binding.RESET_POLICY


@dataclass(frozen=True)
class SurfaceCalciumEnergyProfileBarrierInterventionModel(parent.SurfaceCalciumEnergyHCNExtraModel):
    coupled_preparation: dict
    membrane_interventions: tuple
    barrier_intervention: barrier.Event | None
    phase: str
    timing_policy: str
    reset_policy: str


@dataclass(frozen=True)
class Execution(parent.Execution):
    intervention_capacity: int = 0
    intervention_target_capacity: int = 0
    barrier_target_capacity: int = 0


def owner_spec(spec):
    return replace(
        spec,
        model=parent.SurfaceCalciumEnergyHCNExtraModel(
            **{
                f.name: getattr(spec.model, f.name)
                for f in fields(parent.SurfaceCalciumEnergyHCNExtraModel)
            }
        ),
        execution=parent.Execution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(parent.Execution)}
        ),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceCalciumEnergyProfileBarrierInterventionModel
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Require exact combined calcium_energy model and execution types")
    raw = parent.to_dict(owner_spec(spec))
    m = spec.model
    raw["model"].update(
        id=MODEL_ID,
        coupled_preparation=deepcopy(m.coupled_preparation),
        membrane_interventions=[asdict(v) for v in m.membrane_interventions],
        barrier_intervention=None
        if m.barrier_intervention is None
        else asdict(m.barrier_intervention),
        phase=m.phase,
        timing_policy=m.timing_policy,
        reset_policy=m.reset_policy,
    )
    for key in ("intervention_capacity", "intervention_target_capacity", "barrier_target_capacity"):
        raw["execution"][key] = getattr(spec.execution, key)
    return _json(raw)


def parse(data):
    ordinary, extra, events, ec, tc, event, bc = binding.parse_owner(
        data, MODEL_ID, PARENT_MODEL_ID, parent.parse, barrier
    )
    spec = SimulationSpec(
        SurfaceCalciumEnergyProfileBarrierInterventionModel(
            **vars(ordinary.model),
            coupled_preparation=deepcopy(extra["coupled_preparation"]),
            membrane_interventions=events,
            barrier_intervention=event,
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
            reset_policy=RESET_POLICY,
        ),
        ordinary.experiment,
        Execution(
            **vars(ordinary.execution),
            intervention_capacity=ec,
            intervention_target_capacity=tc,
            barrier_target_capacity=bc,
        ),
    )
    from cells.models.surface_calcium_energy_profile_barrier_interventions import check_definition

    try:
        check_definition(spec)
    except (ValueError, TypeError, ArithmeticError) as error:
        raise ConfigError("Invalid full calcium_energy dual schedule: " + str(error)) from error
    return spec


def artifact(spec):
    return binding.artifact(spec, to_dict, MODEL_ID, PARENT_MODEL_ID)


def replay(record):
    return binding.replay(record, parse, artifact, MODEL_ID, PARENT_MODEL_ID)
