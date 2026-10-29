"""Short public probes for complete ionic membrane/barrier composition."""

from copy import deepcopy
from functools import lru_cache

from cells.core import surface_active_profile_barrier_interventions_spec as schema
from cells.models import surface_active_profile_barrier_interventions as model
from cells.tissue_profiles import REQUEST_KIND, prepare_request
from validation.transport import active_profile_barrier_interventions_fixtures as fixtures

DT = 1e-9
OWNERS = {"ionic": (schema, model, 20)}


@lru_cache
def prepared():
    values = fixtures.inputs("duplicates", permuted=True, padded=True)
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


def definition(family="ionic", phase="SIM", backend="cpu"):
    if family not in OWNERS:
        raise ValueError(family)
    values, _, result = prepared()
    raw = fixtures.definition(deepcopy(values), result)
    raw["model"]["phase"] = phase
    raw["execution"]["backend"] = backend
    return raw
