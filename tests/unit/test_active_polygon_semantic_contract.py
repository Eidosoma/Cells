"""Representation checks; no physical trajectory or independent-case credit."""

from copy import deepcopy

import pytest

from cells.core.active_polygon_physiology_preparation import _semantic
from validation.geometry.active_polygon_physiology_reference import semantic


@pytest.fixture(params=[_semantic, semantic], ids=["admission", "independent-comparison"])
def normalize(request):
    return request.param


def definition():
    return {
        "model": {
            "id": "resolved_calcium@1",
            "ionic": {
                "species": [{"id": "Na"}, {"id": "Ca"}],
                "channels": [{"id": "gate", "initial_gate": [0.2, 0.7]}],
            },
            "stores": [
                {
                    "cell_id": "cell",
                    "model": {
                        "moieties": ["Ca", "B"],
                        "species": [
                            {"id": "Ca", "moieties": {"Ca": 1, "B": 0}},
                            {"id": "B", "moieties": {"Ca": 0, "B": 1}},
                        ],
                        "compartments": [
                            {"id": "er", "initial_amount_fmol": {"Ca": 0.2, "B": 0.4}},
                            {"id": "cytosol", "initial_amount_fmol": {"Ca": 0.1, "B": 0.3}},
                        ],
                        "reactions": [
                            {"id": "r2", "reactants": {"Ca": 1}, "forward_rate_per_s": 0.2},
                            {"id": "r1", "reactants": {"B": 1}, "forward_rate_per_s": 0.1},
                        ],
                    },
                }
            ],
        },
        "experiment": {
            "membrane_controls": [
                {
                    "membrane_id": "patch",
                    "schedule": [
                        {"time": 0.0, "availability": 0.8},
                        {"time": 0.5, "availability": 0.2},
                    ],
                }
            ]
        },
    }


def test_named_chemical_table_permutations_preserve_every_association(normalize):
    first = definition()
    second = deepcopy(first)
    chemical = second["model"]["stores"][0]["model"]
    for name in ("moieties", "species", "compartments", "reactions"):
        chemical[name].reverse()
    saved = deepcopy(first)
    assert normalize(first) == normalize(second)
    assert first == saved


@pytest.mark.parametrize("axis", ["ionic-species", "gate-state", "control-time", "other-moieties"])
def test_ordered_physical_axes_and_schedules_remain_distinct(normalize, axis):
    first = definition()
    first["provenance"] = {"moieties": ["Ca", "B"]}
    second = deepcopy(first)
    if axis == "ionic-species":
        second["model"]["ionic"]["species"].reverse()
    elif axis == "gate-state":
        second["model"]["ionic"]["channels"][0]["initial_gate"].reverse()
    elif axis == "control-time":
        second["experiment"]["membrane_controls"][0]["schedule"].reverse()
    else:
        second["provenance"]["moieties"].reverse()
    assert normalize(first) != normalize(second)


@pytest.mark.parametrize("change", ["inventory", "stoichiometry", "rate", "owner", "moiety"])
def test_chemical_values_and_owners_cannot_be_hidden_by_normalization(normalize, change):
    first = definition()
    second = deepcopy(first)
    chemical = second["model"]["stores"][0]["model"]
    if change == "inventory":
        chemical["compartments"][0]["initial_amount_fmol"]["Ca"] += 0.01
    elif change == "stoichiometry":
        chemical["species"][0]["moieties"]["Ca"] = 2
    elif change == "rate":
        chemical["reactions"][0]["forward_rate_per_s"] += 0.01
    elif change == "owner":
        chemical["compartments"][0]["id"] = "different-compartment"
    else:
        chemical["moieties"][0] = "different-moiety"
    assert normalize(first) != normalize(second)


@pytest.mark.parametrize("name", ["moieties", "species", "compartments", "reactions"])
def test_duplicate_chemical_identifiers_are_refused(normalize, name):
    raw = definition()
    rows = raw["model"]["stores"][0]["model"][name]
    rows.append(deepcopy(rows[0]))
    with pytest.raises((ValueError, AssertionError)):
        normalize(raw)
