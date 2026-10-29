"""Short public-interface probes; physical barrier histories are qualified separately."""

from copy import deepcopy
from functools import lru_cache

from cells.core import surface_calcium_energy_water_barrier_interventions_spec as water
from cells.core import surface_calcium_energy_water_repair_barrier_interventions_spec as repair
from cells.models import surface_calcium_energy_water_barrier_interventions as water_model
from cells.models import surface_calcium_energy_water_repair_barrier_interventions as repair_model
from cells.tissue_profiles import prepare_request
from validation.transport import environment_barrier_composition_fixtures as fixtures

OWNERS = {
    "water": (water, water_model, 44),
    "repair": (repair, repair_model, 49),
}
DT = 1e-9


@lru_cache
def _prepared(family):
    request = fixtures.request(family, "asymmetric_modulators", permuted=True, padded=True)
    raw = request["definition"]
    raw["experiment"].update(end_time=2 * DT, observation_times=[0.0, DT, 2 * DT])
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = group[key][:1]
    # A real boundary ensures public dispatch preserves right-continuous
    # channel controls along with every calcium and finite-fuel control family.
    row = raw["experiment"]["channel_controls"][0]
    row["schedule"].append(dict(time=DT, availability=0.0))
    raw["execution"].update(dt=DT, max_steps=4, jit=True, max_trace_bytes=2**30)
    return prepare_request(request)


def definition(family, phase="SIM", backend="cpu"):
    schema, _, _ = OWNERS[family]
    prepared = _prepared(family)
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=schema.MODEL_ID,
        barrier_preparation=dict(
            definition=deepcopy(prepared.definition), provenance=deepcopy(prepared.provenance)
        ),
        intervention=dict(
            name="public_barrier_probe",
            site_ids=["outside_0", "outside_2", "outside_0"],
            on_s=0.5 * DT,
            off_s=1.5 * DT,
            change_s=8 * DT,
            amplitude=0.6,
        ),
        phase=phase,
        timing_policy=schema.TIMING_POLICY,
    )
    result["execution"].update(backend=backend, barrier_target_capacity=4)
    return result
