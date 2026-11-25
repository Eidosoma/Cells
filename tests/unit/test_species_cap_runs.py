"""FR-9 / D165, the run: a world above the old species cap of 7 passes every host check.

tests/species_cap_fixtures.py's 9-species world (the W4 probe's cell_charged_9 rebuilt) through
the runner, 20 steps of 1 ms, every host check on every accepted row: it runs, and on its states
the host's species-axis sum (NumPy's pairwise order) differs from the explicit species-order sum
the ledgers use in some rows (17 of 21 here; the W4 probe: 4 of 6), while that explicit sum equals
the compiled one on every row. Tier 2: the run takes about 15 s whatever its length (14.7 to 17.3 s
for 5, 10, 20 and 40 steps, nearly all of it compilation), and this file 21 s, above tier 1's 20 s.

FR-43 (D315): the cap at 1,024. FR-43's chain (tests/species_cap_fixtures.chain_world) through the
runner for 40 steps of 5 ms meets its closed form at the declared accuracy, sees the planted link,
books its own free-energy drop as heat, and holds no more than the trace estimate, at two sizes:
- 32 species: 22 s, nearly all of it compilation (the run's reason: the chain is the request's
  world, and 32 is the first size where every operator's padding and the fold's gate act);
- 16 species, the request's control (D347's gap 1, D365): 24 s, nearly all of it compilation (the
  run's reason: the old cap's largest world, whose species sums keep the unrolled fold, so a
  failure here is the chain's or its reference's, not the raise's).
Seconds cold on one timed CPU core (24 November 2026): the nine-species run 18.5 s, and this file
70.48 s with the control, as the record has it (41 s before it). The request's 256-row case is
test_species_cap_large.py's (tier 3): 36 s, which would take this file to about 106 s, past the 90 s
measuring cap.
"""

import math

import jax
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.resources import trace_bytes
from cells.execution.runner import run
from tests.species_cap_fixtures import (
    CHAIN_ACCURACY,
    chain_checks,
    chain_world,
    charged_nine,
    held_bytes,
    species_order,
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_a_nine_species_world_passes_every_host_check_while_the_host_order_differs():
    spec = parse_spec(charged_nine(steps=20))
    result = run(spec)  # Every host check on every accepted row, or a refusal.
    rows, differs, explicit_is_compiled = species_order(spec, result)
    assert rows == 21 and differs > 0 and explicit_is_compiled, (rows, differs)
    assert all(math.isfinite(v) for v in result.diagnostics.values())


def run_the_chain(rows, *, dt=0.005, steps=40):
    """FR-43's chain at `rows` species (3 ions and rows - 3 chain species) through the runner, every
    host check on every row (the material, charge and energy books), observed at every step:
    - every saved amount within the declared accuracy of the closed form expm(K t) n0, while the
      plant, the reference with the middle link 0.1% fast, is seen above 5 times the accuracy;
    - the booked heat is the engine's own free-energy drop at rounding (a passive network books
      H = -dG per half-step), so with the amounts' accuracy it is the closed form's;
    - the trace estimate covers the bytes the run holds, its network layout counted once."""
    raw = chain_world(rows, dt=dt, end=steps * dt, every=dt)
    spec = parse_spec(raw)
    result = run(spec)
    checks = chain_checks(raw, spec, result)
    assert checks["amounts"].shape == (steps + 1, rows - 3)
    assert checks["error"] <= CHAIN_ACCURACY, checks["error"]
    assert checks["seen"] > 5 * CHAIN_ACCURACY, checks["seen"]
    assert checks["heat"] <= 1e-10, checks["heat"]
    estimate, held = trace_bytes(spec, steps), held_bytes(result)
    assert estimate >= held, (estimate, held)


def test_the_32_species_chain_meets_its_closed_form_and_books_its_free_energy_drop():
    """FR-43 / D315, C1.2 and C1.3 at 32 species (3 ions and a 29-species chain): run_the_chain.
    The plant (link15 of 28, a fast link, 0.1% fast) is seen at 8 times the accuracy at 40 steps."""
    run_the_chain(32)


def test_the_16_species_control_meets_its_closed_form_and_books_its_free_energy_drop():
    """FR-43's control (C1.1; D347's gap 1, D365): 16 species (3 ions and a 13-species chain), the
    old cap's largest world, whose species sums keep the unrolled fold (16 terms), checked as the
    larger sizes are (run_the_chain). Its teeth: the plant (link7 of 12, a fast link, 0.1% fast) is
    seen at 10.1 times the declared accuracy at 40 steps, against the 5 times required, and the
    closed form is met at 1.63e-5 of the largest amount, the error of every size the design ran
    (docs/FR43_SHARED_INVENTORIES_DESIGN.md §1.2), against 2e-5."""
    run_the_chain(16)
