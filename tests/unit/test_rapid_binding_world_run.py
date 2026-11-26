"""The general closure through the engine, one ligand: protons carried out of B4's buffered cell
under the general closure (phase 1's split, docs/CORE_SEAMS_DESIGN.md §19 as amended) close every
ledger, the energy ledger with the closure's term S_c beside @3's ideal terms; without the term
it fails; and a carrier whose law lacks the closure's read is refused at the definition.

Split from test_rapid_binding_world.py for the tiers: its runs take most of a minute, so the fast
world checks there join the gate without them; the tier record places each file. The carrier,
its test-namespace law and the world's helpers stay there.
"""

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.registry import kind_registry, laws
from tests import kind_fixtures
from tests.unit.test_rapid_binding_world import carried, reads_law


def test_carried_protons_close_every_ledger_with_the_general_term_and_fail_without_it():
    registry = laws.active().extended(reads_law())
    kinds, raw = carried()
    with kind_registry.scope(kinds), laws.scope(registry):
        spec = parse_spec(raw)
        result = run(spec)  # Every row's host checks: the energy ledger with the stored term.
    final = result.final.state
    ids = list(spec.model.species_ids)
    h, b = ids.index("H"), ids.index("B")
    moved = 1e-3 * spec.experiment.end_time
    assert float(final.carrier_transferred[h, 0]) == pytest.approx(moved, rel=1e-12)
    assert float(final.amount_increment[h, 0]) == pytest.approx(-moved, rel=1e-12)  # H's total.
    assert float(final.amount_increment[b, 0]) == 0.0  # The binder's total never moves.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-3
    lag = np.asarray(final.binding_max_lag_pX)
    assert 0.0 < float(lag[0]) <= 1e-3 and float(lag[1]) == 0.0  # The closure's cell; the bath.
    # Planted: without the closure's term, the energy ledger fails.
    kinds, raw = carried(ledger=False)
    with kind_registry.scope(kinds), laws.scope(registry):
        with pytest.raises(NumericalError, match="accounting failed: energy"):
            run(parse_spec(raw))
    # And the carrier whose law reads only the stored row is refused at the definition.
    kinds, raw = carried(carrier=kind_fixtures.carrier)
    with kind_registry.scope(kinds), pytest.raises(ConfigError, match="lack cells.binding.rapid_binding@1"):
        parse_spec(raw)
