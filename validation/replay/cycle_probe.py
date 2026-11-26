"""The minimal cells' cycle: its admission probe (FR-11; LOOPING_REPLAY_DESIGN §6, ruling 5).

Host only: nothing is stepped. It asks the engine which compositions the cycle's loop would need
it admits, each answer in the engine's own words:
- growth by production (cells.operator.scheduled_species_turnover@1), the volume following it
  (cells.operator.ideal_osmosis_linear_compliance_water@1), the membrane area following it
  (cells.operator.membrane_entity_state@1, or cells.operator.scheduled_membrane_insertion@2) and division
  (cells.operator.isopotential_partition@1): every pair, and the four together, each in the order the cycle
  would declare them with any prerequisite an operator requires (REQUIRES) placed before it and
  named, through the composite's structure check on the inner adapter
  (pump_composite.structure_errors: door S's whole-field rules; a pair whose change and read are
  both scoped is decided per slot at the definition instead, by scope_errors);
- definitions, parsed and bound (parse_spec, initial_values) on S5's compact worlds
  (tests/partition_fixtures.py): one division, two rounds of division (the slots a world allows),
  and a dividing cell that keeps its Na/K pump (the partition's definition check).

Usage: python -m validation.replay.cycle_probe OUT.json
Writes OUT.json and prints one line per question. No verdict: the cycle is built only once this
probe passes (ruling 5), and an engine gap it finds becomes a general feature (D144), never a
workaround in a driver.
"""

import copy
import itertools
import json
import sys
from pathlib import Path

from cells.definitions.specs import ConfigError, parse_spec
from cells.models import pump_composite
from cells.models import pump_composite_adapter as adapter
from cells.operators import OPERATORS
from cells.registry.models import get_model

# The roles in the order the cycle would declare them: the area law (or insertion), water,
# production, division.
LAWS = {
    "area": "cells.operator.membrane_entity_state@1",
    "insertion": "cells.operator.scheduled_membrane_insertion@2",
    "volume": "cells.operator.ideal_osmosis_linear_compliance_water@1",
    "production": "cells.operator.scheduled_species_turnover@1",
    "division": "cells.operator.isopotential_partition@1",
}
CYCLES = (
    ("area", "volume", "production", "division"),
    ("insertion", "volume", "production", "division"),
)


def admission(roles):
    """The structure check of one composition in declared order, each operator's prerequisites
    (REQUIRES) placed before it where the composition lacks them, and named."""
    laws = [LAWS[r] for r in roles]
    added = []
    for law in laws:
        added += [r for r in OPERATORS[law].REQUIRES if r not in laws and r not in added]
    ordered = [*added, *laws]
    errors = pump_composite.structure_errors(adapter, [OPERATORS[law] for law in ordered])
    return {
        "roles": list(roles),
        "laws": ordered,
        "added_prerequisites": added,
        "admitted": not errors,
        "errors": list(errors),
    }


def bound(name, build):
    """A definition parsed and bound, or the engine's refusal."""
    try:
        spec = parse_spec(build())
        get_model(spec.model).initial_values(spec)
    except (ConfigError, ValueError) as exc:
        return {"world": name, "admitted": False, "error": str(exc)}
    return {"world": name, "admitted": True, "cells": [c.id for c in spec.model.cells]}


def with_pump():
    """S5's world whose dividing parent keeps the heredity cell's Na/K pump."""
    from tests import partition_fixtures as pf
    from validation.tissue import pump_water_fixtures as water

    raw = pf.divided()
    cell = water.heredity_cell("H", dt=pf.DT, end_time=0.004)
    patches = {p["id"]: p for p in raw["model"]["membranes"]}
    patches["membrane_0"]["pump"] = copy.deepcopy(cell["model"]["membranes"][0]["pump"])
    raw["experiment"]["pump_controls"] = copy.deepcopy(cell["experiment"]["pump_controls"])
    return raw


def probe():
    from tests import partition_fixtures as pf

    return {
        "pairs": [admission(p) for p in itertools.combinations(LAWS, 2)],
        "cycles": [admission(c) for c in CYCLES],
        "worlds": [
            bound("one division", pf.divided),
            bound("two rounds of division", lambda: pf.divided(second=0.003)),
            bound("a dividing cell with its pump", with_pump),
        ],
    }


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    result = probe()
    Path(argv[0]).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    for item in (*result["pairs"], *result["cycles"]):
        print("admitted" if item["admitted"] else "refused ", " + ".join(item["roles"]))
        for error in item["errors"]:
            print("   ", error)
    for item in result["worlds"]:
        print("admitted" if item["admitted"] else "refused ", item["world"], item.get("error", ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
