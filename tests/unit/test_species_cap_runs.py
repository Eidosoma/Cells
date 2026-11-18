"""FR-9 / D165, the run: a world above the old species cap of 7 passes every host check.

tests/species_cap_fixtures.py's 9-species world (the W4 probe's cell_charged_9 rebuilt) through
the runner, 20 steps of 1 ms, every host check on every accepted row: it runs, and on its states
the host's species-axis sum (NumPy's pairwise order) differs from the explicit species-order sum
the ledgers use in some rows (17 of 21 here; the W4 probe: 4 of 6), while that explicit sum equals
the compiled one on every row. Tier 2: the run takes about 15 s whatever its length (14.7 to 17.3 s
for 5, 10, 20 and 40 steps, nearly all of it compilation), and this file 21 s, above tier 1's 20 s.
"""

import math

import jax
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from tests.species_cap_fixtures import charged_nine, species_order


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def test_a_nine_species_world_passes_every_host_check_while_the_host_order_differs():
    spec = parse_spec(charged_nine(steps=20))
    result = run(spec)  # Every host check on every accepted row, or a refusal.
    rows, differs, explicit_is_compiled = species_order(spec, result)
    assert rows == 21 and differs > 0 and explicit_is_compiled, (rows, differs)
    assert all(math.isfinite(v) for v in result.diagnostics.values())
