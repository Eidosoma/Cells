"""Contract tests for cells.cycle.atp_driven_transporter_mass_action_positive@1 (the transporter kind's kernel),
on R-fuel's calibrated first case (validation/compartment_ph/REFERENCES_USAGE.md)."""

import math

import numpy as np
import pytest

from cells.laws.electrochemistry import R
from cells.laws.pumps import atp_transporter as tk

T = 310.0
U = np.finfo(float).eps / 2  # The unit roundoff, for the bounds derived from it.
P = tk.Parameters(capacity_fmol_s=0.1, stoichiometry=1.0, km_role_mM=1.0, km_atp_mM=0.1)


def inputs(c_in=10.0, c_out=10.0, atp=3.0, adp=0.3, pi=3.0):
    return tk.Inputs(c_in, c_out, atp, adp, pi, -30500.0, 1000.0, T)


def test_rational_and_exponential_forms_agree_on_positive_states():
    for state in (inputs(), inputs(c_out=86.9, atp=3.27, adp=0.03),
                  inputs(atp=1.74e-4, adp=3.3, pi=6.0), inputs(c_in=10.0, c_out=118.5)):
        e = tk.kinetics(state, P, 1.0, xp=np).cycles_fmol_s
        r = tk.cycles_rational(state, P, 1.0, xp=np)
        assert r == pytest.approx(e, rel=1e-12, abs=1e-30)


def test_rational_form_is_finite_at_zero_atp_and_reverses():
    r = tk.cycles_rational(inputs(atp=0.0), P, 1.0, xp=np)
    assert np.isfinite(r) and r < 0  # no ATP: the cycle runs backward toward synthesis


def test_zero_at_static_head_and_reversal_beyond():
    drive = tk.chemical_drive(inputs(), xp=np)
    c_out_head = 10.0 * math.exp(-drive / (R * T))  # n RT ln(c_out/c_in) = -drive
    at_head = tk.kinetics(inputs(c_out=c_out_head), P, 1.0, xp=np)
    assert abs(at_head.cycle_free_energy_J_mol) < 1e-8
    assert abs(at_head.cycles_fmol_s) < 1e-12
    assert tk.kinetics(inputs(c_out=c_out_head * 1.01), P, 1.0, xp=np).cycles_fmol_s < 0
    assert tk.kinetics(inputs(c_out=c_out_head * 0.99), P, 1.0, xp=np).cycles_fmol_s > 0


def test_delta_g_per_cycle_closes_against_the_moved_rows():
    # NumPy dG: per cycle, the stored free energy changes by the drive plus the role's transport;
    # heat = -cycles dG_cyc, and for held fuel work = -cycles x drive.
    s = inputs(c_out=50.0)
    rates = tk.kinetics(s, P, 1.0, xp=np)
    transport = R * T * math.log(50.0 / 10.0)
    # Identities to rounding, at 1e-12 relative (far above the few roundings in each), with abs=0:
    # approx's default abs of 1e-12 exceeds these pJ/s values.
    assert rates.cycle_free_energy_J_mol == pytest.approx(
        rates.chemical_drive_J_mol + transport, rel=1e-12, abs=0
    )
    stored = 1e-3 * rates.cycles_fmol_s * transport
    assert tk.held_work_pJ_s(rates) == pytest.approx(tk.heat_pJ_s(rates) + stored, rel=1e-12, abs=0)
    assert tk.heat_pJ_s(rates) >= 0
    # The role moves -stoichiometry per cycle (1 here): one product, within u.
    assert tk.role_inward_fmol_s(rates, P) == pytest.approx(-rates.cycles_fmol_s, rel=U, abs=0)
    assert tk.FUEL_STOICHIOMETRY == {"ATP": -1, "ADP": 1, "Pi": 1}


def test_the_drive_comes_from_the_registry_input_not_a_parameter():
    assert "delta_g0_prime_J_mol" not in tk.Parameters._fields
    assert "delta_g0_prime_J_mol" in tk.Inputs._fields


def test_domain_refusals():
    assert tk.domain_valid(inputs(), P, 1.0, xp=np)
    assert not tk.domain_valid(inputs(atp=0.0), P, 1.0, xp=np)
    assert not tk.domain_valid(inputs(), P._replace(stoichiometry=1.5), 1.0, xp=np)
    assert not tk.domain_valid(inputs(), P._replace(stoichiometry=5.0), 1.0, xp=np)
    assert not tk.domain_valid(inputs(), P, 1.5, xp=np)
    assert not tk.domain_valid(inputs(c_out=1e50), P, 1.0, xp=np)  # |dG/RT| ~ 93 > 80


def test_planted_flipped_role_sign_fails_the_energy_identity():
    s = inputs(c_out=50.0)
    rates = tk.kinetics(s, P, 1.0, xp=np)
    transport = R * T * math.log(50.0 / 10.0)
    flipped = 1e-3 * (-rates.cycles_fmol_s) * transport  # the role moved the wrong way
    # The identity's own tolerance (test_delta_g_per_cycle_closes_against_the_moved_rows).
    assert tk.held_work_pJ_s(rates) != pytest.approx(tk.heat_pJ_s(rates) + flipped, rel=1e-12, abs=0)
