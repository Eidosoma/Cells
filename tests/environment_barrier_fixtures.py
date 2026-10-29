"""Materialize the exact static artifact around independent dynamic input data."""

from copy import deepcopy
from functools import lru_cache

from cells.core import environment_barrier_preparation as preparation
from cells.core.environment_barrier_interventions_spec import MODEL_ID
from validation.transport import environment_barrier_interventions_fixtures as fixtures


@lru_cache
def definition(case="partial", *, permuted=False, padded=False):
    raw = fixtures.inputs(case, permuted=permuted, padded=padded)
    artifact = preparation.prepare(raw["request"])
    result = deepcopy(artifact.definition)
    result["model"].update(
        id=MODEL_ID,
        barrier_preparation=dict(definition=artifact.definition, provenance=artifact.provenance),
        intervention=deepcopy(raw["intervention"]),
        phase=raw["phase"],
        timing_policy=raw["timing_policy"],
    )
    result["execution"]["barrier_target_capacity"] = raw["barrier_target_capacity"]
    return result


def public_definition():
    raw = deepcopy(definition())
    raw["experiment"].update(end_time=2e-9, observation_times=[0.0, 1e-9, 2e-9])
    for family in ("membrane_controls", "junction_controls"):
        for group in raw["experiment"][family]:
            group["schedule"] = group["schedule"][:1]
    raw["model"]["intervention"].update(on_s=0.5e-9, off_s=1.5e-9, change_s=8e-9)
    raw["execution"].update(dt=1e-9, max_steps=4, jit=False)
    return raw
