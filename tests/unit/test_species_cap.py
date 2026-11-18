"""FR-9 / D165: the species cap at 16, and the sum order a world above the old cap of 7 exercises.

On tests/species_cap_fixtures.py's 9-species world (the W4 probe's cell_charged_9 rebuilt: one
heredity cell, four mobile charged species and D150's S; a single cell column, seven moving
charged rows below slot 8):
1. the cap, now 16, admits it (above the old cap of 7);
2. on its own layout the host's species-axis sum (surface_tissue.charge_increment, NumPy's
   pairwise order for a single column of 8 or more species) differs from the explicit
   species-order sum that every ledger uses (capacitor_change) for seeded increments in the
   charged rows, while the explicit host sum equals the compiled one bitwise. The order the old
   cap guarded against is real, and the ledgers do not depend on it.
The world run through the runner with every host check on every accepted row is
test_species_cap_runs.py, in tier 2: the run takes about 15 s whatever its length (14.7 to 17.3 s
for 5, 10, 20 and 40 steps, nearly all of it compilation), and that file 21 s, above tier 1's 20 s.
The refusal above 16 is tested in test_secreted_species.py and test_species_reactions_refusals.py.
"""

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.state import initialise
from cells.models import pump_composite as pc
from cells.models import surface_tissue as tissue
from cells.operators import species_common
from tests.species_cap_fixtures import charged_nine


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


@pytest.fixture(scope="module")
def world():
    return parse_spec(charged_nine(steps=20))


def test_the_cap_is_16_and_admits_the_nine_species_world(world):
    assert species_common.MAX_SPECIES == 16
    assert list(world.model.species_ids)[4:8] == ["Q1", "Q2", "Q3", "Q4"]
    assert len(world.model.species_ids) == 9


def test_the_host_sum_order_differs_while_the_ledgers_explicit_sum_is_the_compiled_one(world):
    model = pc.model_for(world.model)
    _, parameters = model.initial_values(world)
    layout = model.inner.inner_layout(parameters)
    inner = model.inner_state(initialise(world).state)
    charged = (np.asarray(layout.valence).reshape(-1) != 0)[:, None]
    cells = layout.active.size
    assert cells == 1  # A single column: NumPy's pairwise case.
    compiled = jax.jit(lambda s: tissue.capacitor_change(s, layout, xp=jnp)[0])
    rng = np.random.default_rng(20261114)
    differs = 0
    for _ in range(20):
        shape_cells = np.shape(inner.amount_increment)
        shape_outside = np.shape(inner.extracellular_amount_increment)
        state = inner._replace(
            amount_increment=np.where(charged, rng.normal(scale=1e-4, size=shape_cells), 0.0),
            extracellular_amount_increment=np.where(
                charged, rng.normal(scale=1e-4, size=shape_outside), 0.0
            ),
        )
        host = np.asarray(tissue.charge_increment(state, layout, xp=np))
        explicit = np.asarray(tissue.capacitor_change(state, layout, xp=np)[0])
        differs += int(not np.array_equal(host[:cells], explicit[:cells]))
        np.testing.assert_array_equal(explicit, np.asarray(compiled(state)))
    assert differs > 0, "the host's order never differed: the guard did not reach the cap's reason"
