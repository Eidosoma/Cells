"""FR-9 / D165, the run: a world above the old species cap of 7 passes every host check.

tests/species_cap_fixtures.py's 9-species world (the W4 probe's cell_charged_9 rebuilt) through
the runner, 20 steps of 1 ms, every host check on every accepted row: it runs, and on its states
the host's species-axis sum (NumPy's pairwise order) differs from the explicit species-order sum
the ledgers use in some rows (17 of 21 here; the W4 probe: 4 of 6), while that explicit sum equals
the compiled one on every row. Tier 2: the run takes about 15 s whatever its length (14.7 to 17.3 s
for 5, 10, 20 and 40 steps, nearly all of it compilation), and this file 21 s, above tier 1's 20 s.

FR-43 (D315): the cap at 1,024. FR-43's 32-species chain (tests/species_cap_fixtures.chain_world)
through the runner for 40 steps of 5 ms meets its closed form at the declared accuracy, sees the
planted link, books its own free-energy drop as heat, and holds no more than the trace estimate.
About 20 s, nearly all of it compilation (the run's reason: the chain is the request's world, and
32 is the first size where every operator's padding and the fold's gate act).
"""

import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.resources import trace_bytes
from cells.execution.runner import run
from tests.species_cap_fixtures import (
    CHAIN_ACCURACY,
    chain_amounts,
    chain_free_energy_pJ,
    chain_reference,
    chain_world,
    charged_nine,
    species_order,
)
from validation.tissue import species_reactions_fixtures as rfx


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_a_nine_species_world_passes_every_host_check_while_the_host_order_differs():
    spec = parse_spec(charged_nine(steps=20))
    result = run(spec)  # Every host check on every accepted row, or a refusal.
    rows, differs, explicit_is_compiled = species_order(spec, result)
    assert rows == 21 and differs > 0 and explicit_is_compiled, (rows, differs)
    assert all(math.isfinite(v) for v in result.diagnostics.values())


def nbytes(tree):
    """Bytes of every array in a nest of tuples, lists, dicts and arrays."""
    if isinstance(tree, dict):
        return sum(nbytes(v) for v in tree.values())
    if isinstance(tree, (tuple, list)):
        return sum(nbytes(v) for v in tree)
    return np.asarray(tree).nbytes if tree is not None else 0


def test_the_32_species_chain_meets_its_closed_form_and_books_its_free_energy_drop():
    """FR-43 / D315, C1.2 and C1.3 at 32 species (3 ions and a 29-species chain), every host check
    on every row (the material, charge and energy books):
    - every saved amount within the declared accuracy of the closed form expm(K t) n0, while the
      reference with the middle link 0.1% fast is seen (8 times the accuracy at 40 steps);
    - the booked heat is the engine's own free-energy drop at rounding (a passive network books
      H = -dG per half-step), so with the amounts' accuracy it is the closed form's;
    - the trace estimate covers the bytes the run holds, its network layout counted once."""
    rows, dt, steps = 32, 0.005, 40
    raw = chain_world(rows, dt=dt, end=steps * dt, every=dt)
    spec = parse_spec(raw)
    result = run(spec)
    n = chain_amounts(spec, result)
    times = np.asarray(result.times)
    assert n.shape == (steps + 1, rows - 3)
    largest = float(np.max(n[0]))
    exact = chain_reference(n[0], times)
    error = float(np.max(np.abs(n - exact))) / largest
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
    held = nbytes(tuple(result.history)) + nbytes(result.observations) + nbytes(result.final.layout)
    assert trace_bytes(spec, steps) >= held, (trace_bytes(spec, steps), held)
