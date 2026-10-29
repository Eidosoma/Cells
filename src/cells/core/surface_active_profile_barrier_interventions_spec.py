"""Two prescribed stage schedules on exactly one full56 ionic owner."""

from copy import deepcopy
from dataclasses import asdict, dataclass, fields, replace

from cells.core import active_profile_barrier_preparation as preparation
from cells.core import surface_active_barrier_interventions_spec as barrier
from cells.core import surface_active_profile_interventions_spec as membrane
from cells.core import surface_kinetic_spec as parent
from cells.core.specs import ConfigError, SimulationSpec, _fields, digest

MODEL_ID = "resolved_active_profile_barriers@1"
PARENT_MODEL_ID = parent.HCN_EXTRA_MODEL_ID
TIMING_POLICY = membrane.TIMING_POLICY
RESET_POLICY = membrane.RESET_POLICY
KIND = "cells.scheduled_active_profile_barriers@1"
EXTRA = {
    "coupled_preparation",
    "membrane_interventions",
    "barrier_intervention",
    "phase",
    "timing_policy",
    "reset_policy",
}


@dataclass(frozen=True)
class SurfaceActiveProfileBarrierInterventionModel(parent.SurfaceHCNExtraModel):
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
        model=parent.SurfaceHCNExtraModel(
            **{f.name: getattr(spec.model, f.name) for f in fields(parent.SurfaceHCNExtraModel)}
        ),
        execution=parent.Execution(
            **{f.name: getattr(spec.execution, f.name) for f in fields(parent.Execution)}
        ),
    )


def to_dict(spec):
    if (
        type(spec.model) is not SurfaceActiveProfileBarrierInterventionModel
        or type(spec.execution) is not Execution
    ):
        raise ConfigError("Require exact combined active model and execution types")
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
    return preparation.profiles._json(raw)


def parse(data):
    try:
        _fields(
            data,
            {"schema_version", "model", "experiment", "execution"},
            "combined active definition",
        )
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise ConfigError("Require combined active schema_version 1")
        raw = deepcopy(data)
        model = raw["model"]
        if not isinstance(model, dict) or model.get("id") != MODEL_ID or not EXTRA <= model.keys():
            raise ConfigError("Require the explicit combined active model")
        extra = {key: model.pop(key) for key in EXTRA}
        if (
            extra["phase"] not in ("INIT", "SIM")
            or extra["timing_policy"] != TIMING_POLICY
            or extra["reset_policy"] != RESET_POLICY
        ):
            raise ConfigError(
                "Declare fresh INIT/SIM, shared RK-stage clock and zero-buffer policies"
            )
        artifact = _fields(
            extra["coupled_preparation"],
            {"definition", "provenance"},
            "complete combined preparation",
        )
        prepared = preparation.replay(artifact["provenance"])
        if digest(prepared.definition) != digest(artifact["definition"]) or digest(
            prepared.provenance
        ) != digest(artifact["provenance"]):
            raise ConfigError("Combined preparation disagrees with its exact physical recipe")
        model["id"] = PARENT_MODEL_ID
        if digest(model) != digest(prepared.definition["model"]):
            raise ConfigError("Every physical owner, gate, pump and static coefficient must match")
        # Each qualified schedule parser validates its own native declarations
        # on its exact full physical parent. Neither uses passive dynamics.
        provenance = prepared.provenance
        first = deepcopy(raw)
        first["model"] = deepcopy(provenance["profile_preparation"]["definition"]["model"])
        first["model"].update(
            id=membrane.MODEL_ID,
            profile_preparation=deepcopy(provenance["profile_preparation"]),
            interventions=extra["membrane_interventions"],
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
            reset_policy=RESET_POLICY,
        )
        first["execution"].pop("barrier_target_capacity")
        ms = membrane.parse(first)
        second = deepcopy(raw)
        second["model"].update(
            id=barrier.MODEL_ID,
            barrier_preparation=deepcopy(provenance["barrier_preparation"]),
            intervention=extra["barrier_intervention"],
            phase=extra["phase"],
            timing_policy=TIMING_POLICY,
        )
        for key in ("intervention_capacity", "intervention_target_capacity"):
            second["execution"].pop(key)
        bs = barrier.parse(second)
        ordinary = barrier.owner_spec(bs)
        spec = SimulationSpec(
            SurfaceActiveProfileBarrierInterventionModel(
                **vars(ordinary.model),
                coupled_preparation=deepcopy(artifact),
                membrane_interventions=ms.model.interventions,
                barrier_intervention=bs.model.intervention,
                phase=extra["phase"],
                timing_policy=TIMING_POLICY,
                reset_policy=RESET_POLICY,
            ),
            ordinary.experiment,
            Execution(
                **vars(ordinary.execution),
                intervention_capacity=ms.execution.intervention_capacity,
                intervention_target_capacity=ms.execution.intervention_target_capacity,
                barrier_target_capacity=bs.execution.barrier_target_capacity,
            ),
        )
        from cells.models.surface_active_profile_barrier_interventions import check_definition

        check_definition(spec)
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError, AttributeError) as error:
        raise ConfigError("Invalid combined active schedules: " + str(error)) from error


def artifact(spec):
    raw = dict(
        kind=KIND,
        definition=to_dict(spec),
        parent_model_id=PARENT_MODEL_ID,
        preparation_identity=spec.model.coupled_preparation["provenance"]["identity"],
    )
    raw["identity"] = digest(raw)
    return raw


def replay(record):
    try:
        row = deepcopy(record)
        identity = row.pop("identity")
        if row["kind"] != KIND or digest(row) != identity:
            raise ConfigError("Stale combined schedule artifact")
        spec = parse(row["definition"])
        if digest(artifact(spec)) != digest(record):
            raise ConfigError("Combined schedule recipe changed")
        return spec
    except (KeyError, TypeError, ValueError, ArithmeticError) as error:
        raise ConfigError("Invalid combined schedule artifact: " + str(error)) from error
