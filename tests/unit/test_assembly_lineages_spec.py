"""The assembly-lineage definition: its registration, its round trip, its world id, its refusals.

Planted errors it must catch: every malformed definition in REFUSED (a negative catalysis entry, a
law reading data the world lacks, a founder at the fission size, ...) is refused at parse.
"""

import copy

import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages import (
    GARD_PAIR_CONSISTENT,
    GARD_PAIR_CONSISTENT_V2,
    GARD_SINGLE_EVENT,
    MODEL_ID,
)
from cells.models.assembly_lineages import spec as lineage_spec
from cells.registry.models import get_model
from tests.assembly_lineage_fixtures import definition, world


def test_registered_through_the_chain_and_round_trip():
    data = definition(world(), GARD_SINGLE_EVENT)
    spec = parse_spec(data)
    assert isinstance(spec.model, lineage_spec.LineageModel)
    assert get_model(spec.model).__name__ == "cells.models.assembly_lineages.model"
    again = parse_spec(spec.to_dict())
    assert again.to_dict() == spec.to_dict() and again.fingerprint == spec.fingerprint
    assert spec.to_dict()["model"]["id"] == MODEL_ID


def test_one_world_id_for_both_forms_and_the_default_form_written():
    the_world = world()
    single = parse_spec(definition(the_world, GARD_SINGLE_EVENT))
    pair = parse_spec(definition(the_world, GARD_PAIR_CONSISTENT))
    implicit = parse_spec(definition(the_world, None))  # GARD data, no law named.
    assert single.model.world.id == pair.model.world.id == implicit.model.world.id
    assert single.fingerprint != pair.fingerprint
    assert implicit.model.rate_factor == GARD_PAIR_CONSISTENT
    assert implicit.to_dict()["model"]["rate_factor"] == {"law": GARD_PAIR_CONSISTENT}
    assert implicit.fingerprint == pair.fingerprint
    bare = parse_spec(definition(world(matrix=False), None))
    assert bare.model.rate_factor is None and "rate_factor" not in bare.to_dict()["model"]


def test_version_2_refuses_a_world_beyond_its_budget_at_parse():
    """@2's domain (D246): with fission size 8, a row [2^k, 1] needs k + 4 bits, so k = 102 is
    admitted and k = 103 refused, naming the bits; @1 has no such domain. The same world is one
    world for both versions."""
    for k, bits in ((102, None), (103, 107)):
        the_world = world(count=2, size=8, beta=[[2.0**k, 1.0], [0.0, 0.0]])
        old = parse_spec(definition(the_world, GARD_PAIR_CONSISTENT))
        if bits is None:
            new = parse_spec(definition(the_world, GARD_PAIR_CONSISTENT_V2))
            assert new.model.world.id == old.model.world.id
            continue
        with pytest.raises(ConfigError, match=f"row 0 needs {bits} bits .* the 106-bit budget"):
            parse_spec(definition(the_world, GARD_PAIR_CONSISTENT_V2))
    # The range (the Lean proofs project's findings of 22 November 2026): the largest value, the
    # largest entry times the fission size 8, below 2^1020, and every entry's lowest set bit in the
    # normal range. Planted, at main: 2^1023 parsed and stalled on NaN words; 2^-1074 parsed, and
    # the compiled cache flushed it to 0.
    for k, refusal in ((1016, None), (1017, "not below 2\\^1020"), (-1022, None),
                       (-1074, "below the normal range")):  # fmt: skip
        the_world = world(count=2, size=8, beta=[[2.0**k, 0.0], [0.0, 0.0]])
        if refusal is None:
            parse_spec(definition(the_world, GARD_PAIR_CONSISTENT_V2))
            continue
        with pytest.raises(ConfigError, match=refusal):
            parse_spec(definition(the_world, GARD_PAIR_CONSISTENT_V2))
    # An explicit molecule capacity is bounded by itself, not by the default buckets' largest:
    # 4,097 for a fission size of 4,097 (planted, at main: "No capacity bucket holds 4097").
    big = world(count=2, size=4097, beta=[[1.0, 0.0], [0.0, 1.0]])
    spec = parse_spec(definition(big, GARD_PAIR_CONSISTENT_V2, molecules=4097))
    assert spec.execution.molecule_capacity == 4097


def test_units_default_to_the_nominal_clock_and_are_written_out():
    spec = parse_spec(definition(world(), GARD_PAIR_CONSISTENT))
    assert spec.to_dict()["model"]["world"]["units"] == {"time": "nominal", "temperature_K": None}
    seconds = world()
    seconds["units"] = {"time": "s", "temperature_K": 310.0}
    other = parse_spec(definition(seconds, GARD_PAIR_CONSISTENT))
    assert other.model.world.units == lineage_spec.Units("s", 310.0)
    assert other.model.world.id != spec.model.world.id


def _edit(path, value):
    def change(data):
        node = data
        for key in path[:-1]:
            node = node[key]
        if value is DELETE:
            del node[path[-1]]
        else:
            node[path[-1]] = value

    return change


DELETE = object()
W = ("model", "world")
REFUSED = {
    "negative catalysis": lambda d: d["model"]["world"]["law_data"]["catalysis_matrix"][
        1
    ].__setitem__(2, -0.5),
    "non-finite catalysis": lambda d: d["model"]["world"]["law_data"]["catalysis_matrix"][
        0
    ].__setitem__(0, float("inf")),
    "short matrix row": lambda d: d["model"]["world"]["law_data"]["catalysis_matrix"][0].pop(),
    "law without its data": _edit((*W, "law_data"), DELETE),
    "unknown law": _edit(("model", "rate_factor", "law"), "cells.unknown_factor@1"),
    "founder at the fission size": _edit((*W, "founder"), [6, 6, 0, 0, 0, 0]),
    "empty founder": _edit((*W, "founder"), [0] * 6),
    "founder of the wrong length": _edit((*W, "founder"), [1] * 5),
    "negative supply": _edit((*W, "supply"), -0.1),
    "zero leave rate": _edit((*W, "exchange", "leave_rate"), 0.0),
    "another exchange law": _edit((*W, "exchange", "law"), "cells.other_exchange@1"),
    "fraction of one": _edit(
        (*W, "fission", "partition"), {"rule": "exact_fraction", "fraction": 1.0}
    ),
    "unknown partition": _edit((*W, "fission", "partition"), {"rule": "halves", "fraction": 0.5}),
    "unknown daughter rule": _edit((*W, "continuation", "daughter"), "largest"),
    "unknown world key": _edit((*W, "volume"), 1.0),
    "population mode": _edit(("execution", "mode"), "population"),
    "stream word too large": _edit(("execution", "stream", "seed"), 2**32),
    "type capacity below the types": _edit(("execution", "type_capacity"), 4),
    "molecule capacity below the fission size": _edit(("execution", "molecule_capacity"), 8),
    "float fission count": _edit(("experiment", "fissions"), 2.0),
    "unknown time unit": _edit((*W, "units"), {"time": "ms"}),
    "negative temperature": _edit((*W, "units"), {"time": "s", "temperature_K": -1.0}),
}


@pytest.mark.parametrize("name", sorted(REFUSED))
def test_malformed_definitions_are_refused(name):
    data = definition(world(), GARD_PAIR_CONSISTENT)
    parse_spec(copy.deepcopy(data))  # The unplanted definition parses.
    REFUSED[name](data)
    with pytest.raises(ConfigError):
        parse_spec(data)
