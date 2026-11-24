"""FR-43 / D315: a world at the species cap, 1,024 species, and the request's 256-row case, through
the runner (tier 3).

FR-43's chain (tests/species_cap_fixtures.chain_world) over the design note's full horizon, 400
steps of 5 ms (2 s), every host check on every row (the material, charge and energy books): every
saved amount within the declared accuracy of the closed form expm(K t) n0, the reference with the
middle link 0.1% fast seen, and the booked heat the engine's own free-energy drop at rounding
(tests/species_cap_fixtures.chain_checks); then a 1,025th species refused at the parse.
- 1,024 species (3 ions and a 1,021-species chain). Its reason and cost: the size the cap admits,
  where the species sums take the fold's scan above 16 terms, over the horizon of the design note's
  record (docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.2: error 1.63e-5, the planted link at 2.7e-4).
  On one CPU core: about 25 s to build the 1,024-species definition, 42 s of compile and 0.43 s per
  step, so about 4 min, tier 3, run deliberately (20 steps took 70 s, which would have been every
  gate's tier-2 cost).
- 256 species (3 ions and a 253-species chain), the request's middle size (D347's gap 1, D365).
  Its reason and cost: the size where the dense network layout first sets the step's cost (the
  note's §1.6), run at the fixtures' default 2 GiB trace budget, which the estimate before FR-43
  refused for this run; 36 s cold on one timed CPU core (24 November 2026), nearly two thirds of
  it compilation, which in test_species_cap_runs.py would take that file (66 s) past the 90 s
  measuring cap and out of tier 2.
"""

import jax
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution import batch, batch_windows, resources, windows
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from tests.species_cap_fixtures import CHAIN_ACCURACY, chain_checks, chain_world, held_bytes
from validation.tissue import secreted_species_fixtures as fx

STEPS = 400  # 5 ms each: the design note's 2 s horizon.


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def raw():
    return chain_world(1024, dt=0.005, end=2.0, every=0.25)


def run_the_chain(raw):
    """The chain's run with every host check on every row, and chain_checks' bounds."""
    spec = parse_spec(raw)
    result = run(spec)
    checks = chain_checks(raw, spec, result)
    assert checks["amounts"].shape == (STEPS + 1, len(spec.model.species_ids) - 3)
    assert checks["error"] <= CHAIN_ACCURACY, checks["error"]
    assert checks["seen"] > 5 * CHAIN_ACCURACY, checks["seen"]
    assert checks["heat"] <= 1e-10, checks["heat"]
    return spec, result


def test_a_1024_species_chain_meets_its_closed_form_and_books_its_free_energy_drop(raw):
    spec, _ = run_the_chain(raw)
    assert len(spec.model.species_ids) == 1024


def test_a_256_species_chain_meets_its_closed_form_under_the_default_trace_budget():
    """FR-43's 256-row case (C1.1 to C1.3; D347's gap 1, D365), over the design note's horizon. Its
    teeth: the plant (link127 of 252, a fast link, 0.1% fast) is seen at 9.3 times the declared
    accuracy against the 5 times required, and the closed form is met at 1.63e-5 of the largest
    amount against 2e-5 (the note's §1.2 record: 1.63e-5 and 1.86e-4); the run is admitted under the
    fixtures' 2 GiB budget, which the layout counted on every saved row (the estimate before FR-43,
    9.9 GB here) refused, and that budget's estimate covers the bytes the run holds."""
    raw = chain_world(256, dt=0.005, end=2.0, every=0.25)
    spec, result = run_the_chain(raw)
    assert len(spec.model.species_ids) == 256
    assert spec.execution.max_trace_bytes == 2**31  # The fixtures' budget, not raised.
    assert resources.fixed_bytes(spec) * (STEPS + 1) > spec.execution.max_trace_bytes
    assert resources.trace_bytes(spec, STEPS) >= held_bytes(result)


def test_a_1025th_species_is_refused_at_the_parse(raw):
    more = add_inventory_species(
        raw, "Y", trace_mM=fx.TRACE_mM, diffusivity_m2_per_s=fx.D_S, floor_fmol=fx.FLOOR_FMOL
    )
    with pytest.raises(ConfigError, match="admits at most 1024 species per world"):
        parse_spec(more)


def test_its_windowed_run_and_a_two_world_batch_are_admitted_under_2_gib(raw):
    """The layout counted once per world (FR-43 / D315): at 1,024 species it is 0.37 GiB, and
    counted with every copy of the rows a two-world batch of this world was refused under 2 GiB."""
    spec = parse_spec(raw)
    two = batch.parse_batch(
        dict(
            schema_version=1,
            kind="independent_worlds",
            worlds=[dict(world_id=i, simulation=raw) for i in (1, 2)],
            execution=dict(
                mapping="lax_map", max_worlds=4, max_padded_steps=10**6, max_working_bytes=2**31
            ),
        )
    )
    policy = windows.WindowPolicy(256)
    assert windows.plan_windows(spec, policy).estimated_working_bytes <= 2**31
    assert batch.plan_batch(two).estimated_working_bytes <= 2**31
    assert batch_windows.plan_batch_windows(two, policy).estimated_working_bytes <= 2**31
