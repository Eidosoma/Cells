"""The population axis through the runner, compiled (the kinds owner's design statement 1, §10).

§10's composed world, with its plant (D187), on tests/unit/test_cycle_kind.py's worlds: an
electrogenic diagram exchanger and a finite-fuel pump on one patch run with every ledger closing at
every accepted row (the runner's host checks); the fuel's rows change by the pump's cycles alone,
nothing is held, so no work and no supply, and heat never falls (planted: the ATP change 1e-9 off,
refused by its check). The one compiled run of the population axis among the tests (the layouts'
agreement steps on the host: tests/unit/test_cycle_kind.py).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.kinds import transporter
from tests.unit import test_cycle_kind as ck

U = np.finfo(float).eps / 2


def test_an_electrogenic_exchanger_beside_a_finite_fuel_pump_on_one_patch():
    """§10's composed world, with finite fuel's own checks (its stored part and produced chemistry
    close the energy and total ledgers at every accepted row)."""
    raw = ck.exchange_world(ck.exchanger(), ck.FINITE_POP)
    with ck.scoped():
        spec = parse_spec(raw)
        declared = dict(spec.model.kinds)[transporter.KIND_ID]
        assert [t.id for t in declared] == ["exchanger_0", "fuel_pump_0"]
        result = run(spec)  # The runner's host checks: every ledger at every accepted row.
    final, ids = result.final.state, list(spec.model.species_ids)
    exchange, pumped = final.cycle_count[:, 0], float(final.cycle_count[0, 1])
    assert np.any(exchange != 0) and pumped > 0
    # The fuel's rows and the cycles sum the same per-step increments (nu = -1, +1, +1; nothing
    # else moves the fuel): each sum within (steps + 1) u of its terms, so twice that apart.
    rel = 2 * (result.final.step_index + 1) * U
    atp, adp, pi = (ids.index(r) for r in ("ATP", "ADP", "Pi"))
    assert float(final.amount_increment[atp, 0]) == pytest.approx(-pumped, rel=rel, abs=0)
    assert float(final.amount_increment[adp, 0]) == pytest.approx(pumped, rel=rel, abs=0)
    assert float(final.amount_increment[pi, 0]) == pytest.approx(pumped, rel=rel, abs=0)
    assert float(np.max(np.abs(final.cycle_metabolic_work_pJ))) == 0.0  # Nothing held.
    assert float(np.sum(np.abs(final.cycle_supplied_fmol))) == 0.0
    assert float(np.min(final.cycle_dissipated_energy_pJ)) >= 0.0  # Heat, never negative.
    assert result.diagnostics["max_energy_balance_relative"] < 1e-6
    # Planted: the ATP change 1e-9 off is refused by the fuel's own check.
    off = float(final.amount_increment[atp, 0]) * (1 + 1e-9)
    assert off != pytest.approx(-pumped, rel=rel, abs=0)
