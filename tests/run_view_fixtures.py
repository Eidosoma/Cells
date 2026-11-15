"""Worlds and planted declarations for the run view's tests (cells/run_view.py).

The worked example's world, short: one cell secreting S into a finite node that leaks to its held
bath (validation/tissue/secreted_species_fixtures; scheduled_species_turnover@1 and
scheduled_species_exchange@1). Declarations an operator does not carry yet are planted for a
test's duration only (plant), never in a source file.
"""

import json

from cells import run_view
from cells.core.specs import parse_spec
from cells.models.operators import OPERATORS
from validation.tissue import secreted_species_fixtures as fx

DT = 1e-3
TURNOVER = "scheduled_species_turnover@1"
EXCHANGE = "scheduled_species_exchange@1"
PARTITION = "isopotential_partition@1"
STATE = "membrane_entity_state@1"


def secretion(end=0.01, every=0.002, produce=1e-4, **world):
    """The worked example's world (a cell secretes S into a node that leaks to its bath), short:
    by default 10 steps and six observations (0 to 10 ms, every 2 ms)."""
    builder = fx.world if world else fx.secreting_cell
    raw = builder(
        end=end, dt=DT, solver=fx.IMEX, observation_times=fx.grid_times(end, DT, every), **world
    )
    cell = (world.get("cells") or (("cell_0", 1.0),))[0][0]
    raw = fx.with_turnover(
        raw,
        [("produce", cell, "production"), ("clear", "ecs_0", "clearance")],
        [("produce", cell, [(0.0, produce)]), ("clear", None, [(0.0, 0.5)])],
    )
    raw = fx.with_exchange(
        raw,
        [
            ("secrete", "contact_0", "export", "first_order"),
            ("sink", "contact_0", "import", "saturable"),
        ],
        [("secrete", cell, [(0.0, 0.1)]), ("sink", cell, [(0.0, 1e6, 5e-4)])],
    )
    return parse_spec(raw)


def route_set(self, spec, declaration):
    """Exchange's route axis as the view's set (the operator's view_sets)."""
    routes = declaration.routes
    return {
        "exchange_route": {
            "id": "exchange_route",
            "ids": tuple(r.id for r in routes),
            "holds": "exchange route",
            "on": ("membrane", tuple(r.patch for r in routes)),
        }
    }


def plant(patch, law, **declarations):
    """Set declarations on a registered operator's class through a MonkeyPatch."""
    for name, value in declarations.items():
        patch.setattr(type(OPERATORS[law]), name, value, raising=False)


def layers(layer_id, label, representation="prescribed"):
    return (dict(id=layer_id, label=label, representation=representation),)


def declare_secretion(patch):
    """Turnover's and exchange's view declarations, whether or not their files carry them."""
    plant(patch, TURNOVER, VIEW_LAYERS=layers("turnover", "Species turnover"))
    plant(patch, EXCHANGE, VIEW_LAYERS=layers("exchange", "Species exchange"), view_sets=route_set)


def load(directory):
    return json.loads((directory / run_view.FILE).read_text())
