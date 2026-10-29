"""Seal static artifacts for bounded independent scheduled-barrier checks."""

import importlib
from copy import deepcopy

from cells.core import environment_barrier_composition_preparation as static
from validation.transport import joint_water_barrier_interventions_fixtures as fixtures


def components(family):
    if family not in fixtures.FAMILIES:
        raise ValueError(family)
    module = "surface_calcium_energy_water" + ("_repair" if family == "repair" else "")
    module += "_barrier_interventions"
    return (
        importlib.import_module("cells.core." + module + "_spec"),
        importlib.import_module("cells.models." + module),
    )


def definition(family="water", case="partial", *, permuted=False, padded=True):
    options = fixtures.inputs(family, case, permuted=permuted, padded=padded)
    prepared = static.prepare(options["request"])
    result = deepcopy(prepared.definition)
    result["model"].update(
        id=fixtures.MODEL_IDS[family],
        barrier_preparation=dict(definition=prepared.definition, provenance=prepared.provenance),
        intervention=options["intervention"],
        phase=options["phase"],
        timing_policy=options["timing_policy"],
    )
    result["execution"]["barrier_target_capacity"] = options["barrier_target_capacity"]
    return result
