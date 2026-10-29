"""Portable evolved INIT evidence; short SIM clocks exercise interfaces only."""

import json
from functools import lru_cache
from pathlib import Path

from cells.core import membrane_profile_phase_handoff as handoff
from validation.topology.membrane_profile_phase_handoff_fixtures import public_definitions

EXAMPLE = Path(__file__).resolve().parents[1] / "examples/tissue_phase/continued.request.json"


def request(*, small=False):
    value = json.loads(EXAMPLE.read_text())
    if small:
        _, value["simulation"] = public_definitions(value["simulation"])
    return value


@lru_cache
def prepared(*, small=False):
    return handoff.prepare(request(small=small))
