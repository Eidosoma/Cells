"""Short complete-owner histories for public phase interfaces, not science claims."""

from copy import deepcopy
from functools import lru_cache

from cells.core import owned_calcium_profile_phase_handoff as handoff
from cells.core import surface_calcium_energy_profile_epoch_spec as fuel_schema
from cells.core import surface_calcium_profile_epoch_spec as calcium_schema
from cells.models import surface_calcium_energy_profile_epoch as fuel
from cells.models import surface_calcium_profile_epoch as calcium
from tests.unit.test_owned_calcium_profile_interventions_dispatch import (
    definition,
    evolved_checkpoint,
)
from validation.topology.owned_calcium_profile_interventions_fixtures import _scaled

OWNERS = {"calcium6": (calcium_schema, calcium, 34), "fuel5": (fuel_schema, fuel, 38)}


def source_checkpoint(family):
    return evolved_checkpoint(family, "INIT")


def request(family):
    schema, _, _ = OWNERS[family]
    source, point = source_checkpoint(family)
    target = definition(family, "SIM")
    target["execution"]["jit"] = False
    for name, rows in target["experiment"].items():
        if name.endswith("_controls"):
            for row in rows:
                key = "controls" if "controls" in row else "schedule"
                row[key] = [_scaled(value, 0.5) for value in row[key]]
    return dict(
        kind=handoff.REQUEST_KIND,
        policies=deepcopy(schema.POLICIES),
        source=handoff.capture_source(source, point),
        simulation=target,
    )


@lru_cache
def prepared(family):
    return handoff.prepare(request(family))
