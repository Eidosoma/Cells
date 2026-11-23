"""FR-43 / D315: a world at the species cap, 1,024 species, through the runner (tier 3).

FR-43's chain at 1,024 species (3 ions and a 1,021-species chain; tests/species_cap_fixtures
.chain_world) over the design note's full horizon, 400 steps of 5 ms (2 s), every host check on
every row (the material, charge and energy books): every saved amount within the declared accuracy
of the closed form expm(K t) n0, the reference with the middle link 0.1% fast seen, and the booked
heat the engine's own free-energy drop at rounding; then a 1,025th species refused at the parse.
Its reason and cost: the size the cap admits, where the species sums take the fold's scan above
16 terms, over the horizon of the design note's record (docs/FR43_SHARED_INVENTORIES_DESIGN.md
§1.2: error 1.63e-5, the planted link at 2.7e-4). On one CPU core: about 25 s to build the
1,024-species definition, 42 s of compile and 0.43 s per step, so about 4 min, tier 3, run
deliberately (20 steps took 70 s, which would have been every gate's tier-2 cost).
"""

import jax
import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from tests.species_cap_fixtures import (
    CHAIN_ACCURACY,
    chain_amounts,
    chain_free_energy_pJ,
    chain_reference,
    chain_world,
)
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def raw():
    return chain_world(1024, dt=0.005, end=2.0, every=0.25)


def test_a_1024_species_chain_meets_its_closed_form_and_books_its_free_energy_drop(raw):
    spec = parse_spec(raw)
    assert len(spec.model.species_ids) == 1024
    result = run(spec)
    n = chain_amounts(spec, result)
    times = np.asarray(result.times)
    largest = float(np.max(n[0]))
    error = float(np.max(np.abs(n - chain_reference(n[0], times)))) / largest
    seen = float(np.max(np.abs(n - chain_reference(n[0], times, planted=True)))) / largest
    assert error <= CHAIN_ACCURACY, error
    assert seen > 5 * CHAIN_ACCURACY, seen
    model = raw["model"]
    network = next(o for o in model["operators"] if o["law"] == rfx.REACTIONS)
    free = chain_free_energy_pJ(
        n,
        volume_pL=model["cells"][0]["volume_pL"],
        temperature_K=model["temperature_K"],
        c0_mM=network["standard_concentration_mM"],
    )
    drop = free[0] - free
    booked = np.asarray(result.history.reaction_dissipated_energy_pJ).sum(axis=1)
    assert float(np.max(np.abs(booked - drop))) <= 1e-10 * float(np.max(np.abs(drop)))


def test_a_1025th_species_is_refused_at_the_parse(raw):
    more = add_inventory_species(
        raw, "Y", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
    )
    with pytest.raises(ConfigError, match="admits at most 1024 species per world"):
        parse_spec(more)
