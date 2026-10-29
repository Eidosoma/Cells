"""Short public probes for complete water/repair membrane/barrier composition."""

from copy import deepcopy
from functools import lru_cache

from cells.core import surface_calcium_energy_water_profile_barrier_interventions_spec as water
from cells.core import (
    surface_calcium_energy_water_repair_profile_barrier_interventions_spec as repair,
)
from cells.models import surface_calcium_energy_water_profile_barrier_interventions as water_model
from cells.models import (
    surface_calcium_energy_water_repair_profile_barrier_interventions as repair_model,
)
from cells.tissue_profiles import REQUEST_KIND, prepare_request
from validation.transport import joint_water_profile_barrier_interventions_fixtures as fixtures

DT = 1e-9
OWNERS = {"water": (water, water_model, 44), "repair": (repair, repair_model, 49)}


@lru_cache
def prepared(family):
    values = fixtures.inputs(family, "duplicates", permuted=True, padded=True)
    raw = values["profile_request"]["definition"]
    raw["experiment"].update(end_time=2 * DT, observation_times=[0.0, DT, 2 * DT])
    for name, groups in raw["experiment"].items():
        if name.endswith("_controls"):
            for group in groups:
                key = "controls" if "controls" in group else "schedule"
                group[key] = group[key][:1]
    raw["experiment"]["channel_controls"][0]["schedule"].append(dict(time=DT, availability=0.0))
    raw["execution"].update(dt=DT, max_steps=4, jit=True, max_trace_bytes=2**30)
    for i, event in enumerate(values["membrane_interventions"]):
        event.update(on_s=(0.25 + 0.25 * i) * DT, off_s=(1.25 + 0.25 * i) * DT, change_s=8 * DT)
    values["barrier_intervention"].update(on_s=0.5 * DT, off_s=1.5 * DT, change_s=8 * DT)
    first = prepare_request(dict(schema_version=1, kind=REQUEST_KIND, **values["profile_request"]))
    request = fixtures.preparation_request(
        values, dict(definition=first.definition, provenance=first.provenance)
    )
    return values, request, prepare_request(request)


def definition(family="repair", phase="SIM", backend="cpu"):
    if family not in OWNERS:
        raise ValueError(family)
    values, _, result = prepared(family)
    raw = fixtures.definition(deepcopy(values), result)
    raw["model"]["phase"] = phase
    raw["execution"]["backend"] = backend
    return raw
