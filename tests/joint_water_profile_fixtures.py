"""Short public-interface inputs; physical trajectories have separate fixtures."""

import importlib
from copy import deepcopy

from cells.tissue_profiles import REQUEST_KIND, prepare_request
from validation.topology import joint_water_profile_interventions_fixtures as physical
from validation.topology.owned_calcium_profile_interventions_fixtures import _scaled

DT = 1e-9
FAMILIES = physical.FAMILIES
FIELDS = {"water": 44, "repair": 49}


def components(family):
    if family not in FAMILIES:
        raise ValueError(family)
    name = "surface_calcium_energy_water" + ("_repair" if family == "repair" else "")
    name += "_profile_interventions"
    return (
        importlib.import_module("cells.core." + name + "_spec"),
        importlib.import_module("cells.models." + name),
    )


def definition(family, phase="SIM", *, backend="cpu", jit=False):
    raw = deepcopy(physical.public_inputs(family))
    for name, rows in raw["definition"]["experiment"].items():
        if name.endswith("_controls"):
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                first = row[key][0]
                second = _scaled(first, 0.7)
                second["time"] = DT
                if name == "injury_controls":
                    first.update(injury=0.8, resealing=0.4)
                    second.update(injury=0.2, resealing=0.7)
                row[key] = [first, second]
    options = {
        key: raw.pop(key)
        for key in (
            "interventions",
            "phase",
            "intervention_capacity",
            "intervention_target_capacity",
        )
    }
    # Exercise the public preparation route before binding the scheduled owner.
    prepared = prepare_request(dict(schema_version=1, kind=REQUEST_KIND, **raw))
    schema, _ = components(family)
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=schema.MODEL_ID,
        profile_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        interventions=options["interventions"],
        phase=phase,
        timing_policy=schema.TIMING_POLICY,
        reset_policy=schema.RESET_POLICY,
    )
    result["execution"].update(
        backend=backend,
        jit=jit,
        max_trace_bytes=2**32,
        intervention_capacity=options["intervention_capacity"],
        intervention_target_capacity=options["intervention_target_capacity"],
    )
    return result
