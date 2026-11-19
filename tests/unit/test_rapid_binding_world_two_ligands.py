"""The general closure through the engine, two ligands (docs/CORE_SEAMS_DESIGN.md §10's composed
check): the core-seams references' S3 at its registered state 0, H and Mg on the binder nuc4, in
heredity cell D under the general closure, with the planted reading carrier taking H out of the
cell at a tenth of its free H per run.
- Every ledger closes, the energy ledger with S_c over both ligands beside @3's ideal terms.
- H's stored total falls by the carried amount; Mg's and the binder's stored totals never move.
- The network's first-order lag at the cell stays inside its 1e-3 pX budget (0 off the closure).
- Mg's free amount follows: H's withdrawal frees the binder's sites, which take Mg, so free Mg
  falls while the free binder rises.
Planted: without the closure's term, the energy ledger fails.

Split from test_rapid_binding_world.py for the tiers, beside test_rapid_binding_world_run.py; the
world's helpers stay there.
"""

from dataclasses import replace

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.kinds import proton_buffer
from cells.registry import kind_registry, laws
from tests import kind_fixtures
from tests.unit.test_proton_buffer_kind import host
from tests.unit.test_rapid_binding_world import amounts, reading_carrier, reads_law, reference_cell


def test_a_two_ligand_cell_closes_every_ledger_and_its_mg_follows_the_carried_protons():
    raw, _ = reference_cell("S3", 0)
    registry = laws.active().extended(reads_law())
    kinds = kind_fixtures.registry(reading_carrier(), proton_buffer.PROTON_BUFFER)
    with kind_registry.scope(kinds), laws.scope(registry):
        start = parse_spec(kind_fixtures.declare_carrier(raw, species="H", rate=0.0))
        _, state, p, _ = host(start)
        read, ok = proton_buffer.stage_read(state, p, xp=np)
        assert ok
        ids = list(start.model.species_ids)
        h, mg, b = ids.index("H"), ids.index("Mg"), ids.index("nuc4")
        free = amounts(read, p)[:, 0]
        end = start.experiment.end_time
        rate = 0.1 * float(free[h]) / end
        carried = kind_fixtures.declare_carrier(raw, species="H", rate=rate)
        result = run(parse_spec(carried))
        final = result.final.state
        after, ok = proton_buffer.stage_read(type(final)(*map(np.asarray, final)), p, xp=np)
        assert ok
    moved = rate * end
    assert float(final.carrier_transferred[h, 0]) == pytest.approx(moved, rel=1e-12)
    assert float(final.amount_increment[h, 0]) == pytest.approx(-moved, rel=1e-12)  # H's total.
    assert float(final.amount_increment[mg, 0]) == 0.0  # Mg's total never moves,
    assert float(final.amount_increment[b, 0]) == 0.0  # nor the binder's.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-9
    lag = np.asarray(final.binding_max_lag_pX)
    assert 0.0 < float(lag[0]) <= 1e-3 and float(lag[1]) == 0.0  # The closure's cell; the bath.
    free_after = amounts(after, p)[:, 0]
    assert free_after[mg] < free[mg] * (1 - 1e-6)  # The freed sites take Mg,
    assert free_after[b] > free[b] * (1 + 1e-6)  # as the free binder rises.
    # Planted: without the closure's term, the energy ledger fails.
    unbooked = replace(proton_buffer.PROTON_BUFFER, ledger_terms=None)
    with kind_registry.scope(kind_fixtures.registry(reading_carrier(), unbooked)):
        with laws.scope(registry), pytest.raises(NumericalError, match="accounting failed: energy"):
            run(parse_spec(carried))
