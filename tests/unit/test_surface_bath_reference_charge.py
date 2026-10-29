"""Independent charge accounting must retain small corruptions beside bath doses.

These are manufactured oracle-sensitivity checks, not biological cases or
additional trajectories. They call no production dynamics or accounting.
"""

import numpy as np
import pytest

from validation.transport import surface_bath_events_fixtures as fixtures
from validation.transport import surface_bath_events_reference as reference


@pytest.mark.parametrize("family", fixtures.FAMILIES)
@pytest.mark.parametrize("case", ("overlap", "permuted"))
def test_independent_bath_charge_budget_detects_small_saved_ledger_changes(family, case):
    raw = fixtures.definition(family, case)
    context = reference.bind(raw)
    values = reference.unpack(context, reference.initial(context))
    values["phase_clock_s"][0] = 2.5e-6
    baseline = reference.conservation(context, reference.flatten(context, values))
    for key in ("capacitor_charge_C", "electrode_charge_C", "global_charge_C"):
        np.testing.assert_allclose(baseline[key], 0.0, rtol=0, atol=3e-25)
    species = [row["id"] for row in raw["model"]["species"]]
    owners = [row["id"] for row in raw["model"]["extracellular"]]
    site = owners.index("bath")
    prescribed = reference.program(context, 2.5e-6)
    assert abs(prescribed["charge_C"][site]) > 1e-10

    for sign in (-1, 1):
        charge = sign * 2.5e-21
        corrupted = {key: np.array(value, copy=True) for key, value in values.items()}
        corrupted["electrode_charge_transferred_C"][site] += charge
        result = reference.conservation(context, reference.flatten(context, corrupted))
        np.testing.assert_allclose(result["global_charge_C"], charge, rtol=1e-12, atol=1e-30)
        expected = np.zeros(len(owners))
        expected[site] = charge
        np.testing.assert_allclose(result["electrode_charge_C"], expected, rtol=1e-12, atol=1e-30)

        supplied = sign * 3e-8
        corrupted = {key: np.array(value, copy=True) for key, value in values.items()}
        corrupted["reservoir_supplied"][species.index("Na"), site] += supplied
        result = reference.conservation(context, reference.flatten(context, corrupted))
        np.testing.assert_allclose(
            result["global_charge_C"], supplied * reference.F * 1e-15, rtol=1e-12, atol=1e-30
        )
        np.testing.assert_allclose(result["electrode_charge_C"], 0.0, rtol=0, atol=3e-25)
