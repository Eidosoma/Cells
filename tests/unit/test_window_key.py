"""vector_windows.world_key: the part of compile_window's key that one world fixes.

docs/INNER_MODEL_V4_DESIGN.md §7.4 (e) 4, for the packed planner's grouping (worlds with equal
keys share one executable). On the host, before any compile:
- value twins (parameter values changed, structure and capacities kept) get equal keys;
- a structure change (NaV1.2 removed) or a capacity change gets another key;
- a planted kind's value twins (another exchange rate) share a key, which differs from the world
  without the kind.
compile_window's own key starts with this part (tests/unit/test_inner_executable_reuse.py).
"""

import copy

from cells.definitions.specs import parse_spec
from cells.execution.state import initialise
from cells.execution.vector_windows import spec_world_key
from cells.registry import kind_registry
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests import kind_fixtures
from validation.tissue import pump_water_fixtures as water_fixtures

NAV = "cells.channel.nav1p2_m3h_regularized@1"


def key(raw):
    spec = parse_spec(raw)
    return spec_world_key(get_model(spec.model), spec, initialise(spec))


def heredity():
    return water_fixtures.heredity_cell("D", dt=1e-3, end_time=8e-3)


def scaled(raw, factor):
    raw = copy.deepcopy(raw)
    for membrane in raw["model"]["membranes"]:
        p = membrane["permeability_m_per_s"]
        membrane["permeability_m_per_s"] = {k: factor * v for k, v in p.items()}
    for channel in raw["model"]["channels"]:
        channel["abundance"] = factor * channel["abundance"]
    return raw


def without_nav(raw):
    raw = copy.deepcopy(raw)
    gone = {c["id"] for c in raw["model"]["channels"] if c["kinetic_law"] == NAV}
    raw["model"]["channels"] = [c for c in raw["model"]["channels"] if c["id"] not in gone]
    controls = raw["experiment"]["channel_controls"]
    raw["experiment"]["channel_controls"] = [g for g in controls if g["channel_id"] not in gone]
    return raw


def padded(raw):
    raw = copy.deepcopy(raw)
    raw["execution"]["channel_capacity"] += 1
    return raw


def test_value_twins_share_a_key_and_structure_or_capacity_does_not():
    base = heredity()
    assert parse_spec(scaled(base, 0.75)) != parse_spec(base)  # The twin's values differ.
    assert key(scaled(base, 0.75)) == key(base)
    assert key(without_nav(base)) != key(base)
    assert key(padded(base)) != key(base)


def test_a_planted_kinds_value_twins_share_a_key():
    raw = add_inventory_species(
        heredity(), "B", trace_mM=1.0, diffusivity_m2_per_s=1e-10, floor_fmol=1e-12
    )
    plain = key(raw)
    with kind_registry.scope(kind_fixtures.registry()):
        one = key(kind_fixtures.declare(raw, rate=1e-3))
        two = key(kind_fixtures.declare(raw, rate=2e-3))
    assert one == two
    assert one != plain
