"""FR-33's maintained example, run (validation/compartment_transfer; D251).

One compiled world of 500 steps of 1 ms. One cell owns two compartments: one releases its labelled
species into the cell (T), and one destroys its own at its node (D), at the same rate constant. Its
cost and reason (D224): one compile, about 30-60 s on one quiet CPU (93 s on a loaded light CPU); it
keeps the donor, receiver and cumulative-loss exports working, with the request's control.
"""

import math

from validation.compartment_transfer import example


def test_transfer_alone_raises_the_receiver_and_destruction_alone_the_loss():
    out = example.exports()
    c = example.control(out)
    assert c["donor_largest_relative_difference"] <= 1e-12  # The same fading donor.
    assert c["donor_against_exp"] <= 1e-12  # n0 exp(-kappa t).
    t_gain, d_gain = c["receiver_gain_fmol"]["T"], c["receiver_gain_fmol"]["D"]
    lost = c["donor_lost_fmol"]["T"]
    assert lost > 0 and math.isclose(t_gain, lost, rel_tol=1e-9) and d_gain == 0.0
    assert math.isclose(c["transfer_fmol"]["T"], lost, rel_tol=1e-12)
    assert c["loss_fmol"]["T"] == 0.0
    assert math.isclose(c["loss_fmol"]["D"], c["donor_lost_fmol"]["D"], rel_tol=1e-9)
