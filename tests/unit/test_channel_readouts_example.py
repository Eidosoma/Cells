"""FR-34's maintained example, run (validation/channel_readouts; D251).

One compiled world of 5 steps: two gate-free K populations on one patch with the same count,
at availability 1 and 0.5. Its cost and reason (D224): one compile, about 30-60 s on one quiet CPU
(114 s on a loaded light CPU); it keeps the documented readouts, count, availability and signed
current, working, with the request's control.
"""

from validation.channel_readouts import example


def test_halving_availability_halves_the_population_current():
    result = example.halving_control()
    control = result["control"]
    assert control["availability"] == (1.0, 0.5)
    assert control["same_units"] and control["same_voltage"]
    assert all(abs(r - 0.5) <= 1e-12 for r in control["current_ratio"])
    full = result["populations"][example.FULL]
    assert result["first_row_at_declared_voltage"]
    # Outward positive: at V0 above E_K the K current leaves the cell.
    assert full["current_A"][0] > 0 and all(f[1] > 0 for f in full["flux_fmol_s"][:1])
