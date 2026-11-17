"""Seal static artifacts for bounded independent scheduled-barrier checks."""

import importlib
from copy import deepcopy

from cells.legacy.core import environment_barrier_composition_preparation as static
from validation.transport import joint_water_barrier_interventions_fixtures as fixtures

# Each family's definition and model modules, named in full (D188 R2).
COMPONENTS = {
    "water": (
        "cells.legacy.core.surface_calcium_energy_water_barrier_interventions_spec",
        "cells.legacy.models.surface_calcium_energy_water_barrier_interventions",
    ),
    "repair": (
        "cells.legacy.core.surface_calcium_energy_water_repair_barrier_interventions_spec",
        "cells.legacy.models.surface_calcium_energy_water_repair_barrier_interventions",
    ),
}


def components(family):
    if family not in fixtures.FAMILIES:
        raise ValueError(family)
    spec, model = COMPONENTS[family]
    return importlib.import_module(spec), importlib.import_module(model)


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
