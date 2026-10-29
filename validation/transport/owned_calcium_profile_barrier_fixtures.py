"""Complete calcium@11/fuel@5 inputs with both native coefficient schedules."""

from copy import deepcopy

from validation.transport import active_profile_barrier_interventions_fixtures as ionic
from validation.transport import owned_barrier_interventions_fixtures as exterior

FAMILIES = ("calcium", "energy")
CASES = ionic.CASES
MODEL_IDS = dict(
    calcium="resolved_calcium_profile_barriers@1",
    energy="resolved_calcium_energy_profile_barriers@1",
)
PARENT_IDS = dict(calcium="resolved_calcium@11", energy="resolved_calcium_energy@5")


def inputs(family="energy", case="joint", *, permuted=False, padded=True):
    if family not in FAMILIES:
        raise ValueError(family)
    values = ionic.inputs(case, permuted=permuted, padded=padded)
    full = exterior.inputs(
        family, "reseal" if case == "closed" else "asymmetric", permuted=permuted, padded=padded
    )
    raw = full["request"]["definition"]
    assert raw["model"]["id"] == PARENT_IDS[family]
    leaf = raw["model"]["ionic"]
    assert leaf["id"] == "resolved_tissue@12" and len(leaf["channels"]) == 63
    for key, layout_key in (
        ("cells", "cell_ids"),
        ("membranes", "membrane_ids"),
        ("extracellular", "environment_ids"),
    ):
        assert {r["id"] for r in leaf[key]} == set(
            values["profile_request"]["geometry"]["layout"][layout_key]
        )
    if case == "closed":
        for row in leaf["membranes"]:
            row["permeability_m_per_s"]["Na"] = 0.0
    # Retain actual finite-pool pump ownership, stores and all additional
    # controls. Never substitute ionic maintained pumps into the fuel owner.
    values["profile_request"]["definition"] = deepcopy(raw)
    values["barrier_template"] = deepcopy(full["request"])
    return values


def preparation_request(values, profile_preparation):
    result = ionic.preparation_request(values, profile_preparation)
    result["kind"] = "cells.calcium_profile_barrier_preparation_request@1"
    return result


def definition(values, prepared):
    result = ionic.definition(values, prepared)
    family = next(f for f in FAMILIES if prepared.definition["model"]["id"] == PARENT_IDS[f])
    result["model"]["id"] = MODEL_IDS[family]
    return result
