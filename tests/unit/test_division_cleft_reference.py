"""R-full (validation/division/cleft_egg_reference.py): laws, analytic limits, readout, plumbing.

Every dynamic case is a synthetic cell, not the J1 egg, so these tests compute no J1 Em.
"""

import math
from dataclasses import replace

import numpy as np
import pytest

from validation.division import cleft_egg_reference as ref

T = 300.0
CYTOSOL = (12.0, 140.0, 30.0)
BATH = (140.0, 5.0, 145.0)


def synthetic(**changes):
    """A small cell with a cleft lumen; every value is synthetic."""
    egg = ref.Egg(
        temperature_K=T,
        cytosol_volume_m3=1e-12,
        cytosol_mM=CYTOSOL,
        bath_mM=BATH,
        old_area_m2=1e-8,
        old_capacitance_F=1e-10,
        old_relative=(0.05, 1.0, 0.0),
        p_old=1e-8,
        new_permeability=(2e-11, 4e-10, 0.0),
        new_specific_capacitance_F_m2=1e-2,
        onset_s=1.0,
        activation_area_m2=1e-9,
        schedule=((1.0, 0.0),),
        gap_width_m=1e-6,
        access_law="logmean",
        access_D=(1.33e-9, 1.96e-9, 2.03e-9),
        a_over_l_m=1e-7,
        pulses=ref.Pulses(enabled=False),
    )
    return replace(egg, **changes)


def total_pa(egg, area):
    return tuple(
        egg.p_old * w * egg.old_area_m2 + p * area
        for w, p in zip(egg.old_relative, egg.new_permeability, strict=True)
    )


# ---------------------------------------------------------------- laws


def test_ghk_flux_vanishes_at_the_nernst_potential_and_is_fickian_at_zero_field():
    ci, co = 140.0, 5.0
    u_nernst = math.log(co / ci)  # z = 1
    assert abs(ref.ghk_flux(1e-16, 1, u_nernst, ci, co)) < 1e-30
    assert ref.ghk_flux(1e-16, 1, 0.0, ci, co) == pytest.approx(1e-16 * (ci - co), rel=1e-15)
    for x in (1e-7, -1e-7, 2e-6, -2e-6):  # the small-x branch joins the direct form
        direct = x / -math.expm1(-x)
        assert ref.ghk_factor(x) == pytest.approx(direct, rel=1e-12)


def test_access_laws_share_fick_and_equilibrium_and_differ_in_field():
    k, cl, cb = 1e-15, 20.0, 5.0
    for law in ("logmean", "constant_field"):
        assert ref.access_flux(law, k, 1, 0.0, cl, cb) == pytest.approx(k * (cl - cb), rel=1e-12)
        u_eq = -math.log(cl / cb)  # ln(cl/cb) + z u = 0
        assert abs(ref.access_flux(law, k, 1, u_eq, cl, cb)) < 1e-27
    assert ref.log_mean(7.0, 7.0) == 7.0
    assert ref.log_mean(7.0 * (1 + 1e-9), 7.0) == pytest.approx(7.0 * (1 + 5e-10), rel=1e-15)
    a = ref.access_flux("logmean", k, 1, 0.5, cl, cb)
    b = ref.access_flux("constant_field", k, 1, 0.5, cl, cb)
    assert abs(a - b) > 1e-2 * abs(b)
    assert ref.access_flux("logmean", 0.0, 1, 0.5, cl, cb) == 0.0


def test_ghk_flux_has_no_overflow_at_extreme_voltages():
    for u in (-900.0, -40.0, 40.0, 900.0):
        flux = ref.ghk_flux(1e-16, 1, u, 140.0, 5.0)
        assert math.isfinite(flux)
        expected = 1e-16 * u * (140.0 if u > 0 else 5.0)  # one side dominates
        assert flux == pytest.approx(expected, rel=1e-12)


# ---------------------------------------------------------------- analytic limits


def test_bath_equivalent_lumen_gives_the_parallel_zero_current_potential():
    """A/L and lumen volume -> infinity: Em -> both membranes' zero-current potential vs bath.

    A finite lumen holding its capacitor charge as a net ionic excess sits at an offset of
    about (RT/F) (q_c / F V_c) / sum z^2 c from the bath, so the gap is widened as well.
    """
    egg = synthetic(a_over_l_m=1e-1, gap_width_m=1e-4, new_permeability=(2.5e-11, 1e-8, 0.0))
    run = ref.simulate(egg, 1.5, record=(1.5,))
    s = run.at[1.5]
    expected = ref.zero_current_potential(
        total_pa(egg, egg.activation_area_m2), tuple(s["cytosol_mM"]), BATH, T
    )
    old_only = ref.zero_current_potential(total_pa(egg, 0.0), tuple(s["cytosol_mM"]), BATH, T)
    assert abs(expected - old_only) > 1e-3  # the limit discriminates the new membrane
    assert s["V"] == pytest.approx(expected, abs=1e-7)
    assert abs(s["phi_lumen"]) < 1e-7
    assert np.allclose(s["lumen_mM"], BATH, rtol=1e-5)


def test_small_lumen_offset_follows_its_capacitor_charge():
    egg = synthetic(a_over_l_m=1e-1, new_permeability=(2.5e-11, 1e-8, 0.0))
    s = ref.simulate(egg, 1.5, record=(1.5,)).at[1.5]
    qc = s["state"][ref.QC] * ref.FMOL  # mol of net charge
    vc = egg.gap_width_m * egg.activation_area_m2 / 2
    offset = -(ref.R * T / ref.F) * (qc / vc) / sum(BATH)
    assert s["phi_lumen"] == pytest.approx(offset, rel=0.05)


def test_sealed_lumen_tends_to_the_old_membranes_zero_current_potential():
    egg = synthetic(a_over_l_m=0.0, new_permeability=(1e-11, 4e-8, 0.0))
    run = ref.simulate(egg, 1.5, record=(1.0, 1.5))
    s = run.at[1.5]
    old_only = ref.zero_current_potential(total_pa(egg, 0.0), tuple(s["cytosol_mM"]), BATH, T)
    parallel = ref.zero_current_potential(
        total_pa(egg, egg.activation_area_m2), tuple(s["cytosol_mM"]), BATH, T
    )
    assert abs(parallel - old_only) > 3e-3
    assert s["V"] == pytest.approx(old_only, abs=1e-7)
    start, end = run.at[1.0]["state"], s["state"]
    lumen_cl = [x[ref.NAC] + x[ref.KC] - x[ref.QC] for x in (start, end)]
    assert lumen_cl[1] == pytest.approx(lumen_cl[0], abs=1e-6)  # no Cl route, static volume


def test_one_patch_insertion_at_fixed_charge():
    """V' = V C/(C + dC) and H = q^2 dC / (2 C (C + dC)); the capacitor energy falls by H."""
    c0, v0 = 1e-10, -0.05
    egg = synthetic(p_old=0.0, onset_s=1e9, initial_V=v0, old_capacitance_rate_F_s=c0 / 10.0)
    run = ref.simulate(egg, 10.0, record=(0.0, 10.0))
    c1 = 2 * c0
    q = c0 * v0
    assert run.at[10.0]["V"] == pytest.approx(v0 * c0 / c1, rel=1e-9)
    heat = 0.5 * q * q * (c1 - c0) / (c0 * c1)
    assert run.at[10.0]["heat_pJ"] * 1e-12 == pytest.approx(heat, rel=1e-8)
    drop = run.at[0.0]["capacitor_energy_J"] - run.at[10.0]["capacitor_energy_J"]
    assert drop == pytest.approx(heat, rel=1e-8)


def test_cleft_insertion_moves_only_the_new_membrane_voltage_and_books_its_heat():
    a0, rate = 1e-9, 1e-10  # the area doubles in 10 s

    def charged(egg, y):
        y = y.copy()
        y[ref.QC] = 0.02 * egg.new_specific_capacitance_F_m2 * a0 / (ref.F * ref.FMOL)
        y[ref.NAC] += y[ref.QC]  # the lumen's excess charge as Na+
        return y

    egg = synthetic(
        p_old=0.0,
        new_permeability=(0.0, 0.0, 0.0),
        a_over_l_m=0.0,
        initial_V=-0.03,
        activation_area_m2=a0,
        schedule=((1.0, rate),),
    )
    run = ref.simulate(egg, 11.0, record=(1.0, 11.0), lumen_state=charged)
    first, last = run.at[1.0], run.at[11.0]
    qc = first["state"][ref.QC] * ref.FMOL * ref.F
    c_a, c_b = egg.new_specific_capacitance_F_m2 * a0, egg.new_specific_capacitance_F_m2 * 2 * a0
    assert first["v_new"] == pytest.approx(-qc / c_a, rel=1e-12)
    assert last["v_new"] == pytest.approx(-qc / c_b, rel=1e-9)
    assert last["V"] == pytest.approx(first["V"], rel=1e-12)
    heat = 0.5 * qc * qc * (1 / c_a - 1 / c_b)
    assert (last["heat_pJ"] - first["heat_pJ"]) * 1e-12 == pytest.approx(heat, rel=1e-8)
    drop = first["capacitor_energy_J"] - last["capacitor_energy_J"]
    assert drop == pytest.approx(heat, rel=1e-8)


def test_bath_facing_insertion_books_the_activation_jump():
    c0, v0, a0, rate = 1e-10, -0.05, 1e-9, 1e-9
    egg = synthetic(
        p_old=0.0,
        new_permeability=(0.0, 0.0, 0.0),
        initial_V=v0,
        new_faces="bath",
        activation_area_m2=a0,
        schedule=((1.0, rate),),
    )
    run = ref.simulate(egg, 3.0, record=(0.0, 3.0))
    c1 = c0 + egg.new_specific_capacitance_F_m2 * (a0 + 2.0 * rate)
    q = c0 * v0
    assert run.at[3.0]["V"] == pytest.approx(q / c1, rel=1e-9)
    heat = 0.5 * q * q * (1 / c0 - 1 / c1)
    assert run.at[3.0]["heat_pJ"] * 1e-12 == pytest.approx(heat, rel=1e-8)


# ---------------------------------------------------------------- pulse readout


def test_pulse_rm_of_an_exactly_linear_membrane():
    """Equal compositions make the constant-field I-V linear: Rm = RT / (F^2 sum z^2 P A c)."""
    same = BATH
    egg = synthetic(
        cytosol_mM=same,
        cytosol_volume_m3=1e-10,
        old_relative=(1.0, 1.0, 1.0),
        onset_s=1e9,
        pulses=ref.Pulses(amplitude_A=1e-10),
    )
    rm, run = ref.rm_at(egg, (0, 1))
    g = ref.F**2 / (ref.R * T) * egg.p_old * egg.old_area_m2 * sum(same)
    assert run.v0 == pytest.approx(0.0, abs=1e-15)
    assert rm == pytest.approx(1.0 / g, rel=1e-5)
    dv0 = run.sample_V[0] - run.onset_V[0]
    dv1 = run.sample_V[1] - run.onset_V[1]
    assert dv0 > 0 > dv1  # the first pulse depolarizes


def test_injected_chloride_returns_after_a_pulse_pair():
    egg = synthetic(p_old=1e-6, onset_s=1e9, pulses=ref.Pulses())
    run = ref.simulate(egg, 20.0, record=(0.0, 1.2, 20.0))

    def cl(s):
        x = s["state"]
        return x[ref.NAI] + x[ref.KI] + run.background_fmol - x[ref.QI]

    per_pulse = 0.5088 * 3e-8 * 1.2 / ref.F / ref.FMOL
    assert cl(run.at[0.0]) - cl(run.at[1.2]) == pytest.approx(per_pulse, rel=1e-6)
    assert cl(run.at[20.0]) == pytest.approx(cl(run.at[0.0]), abs=1e-2)


# ---------------------------------------------------------------- calibration


FAST_PULSES = ref.Pulses(amplitude_A=2e-10, duration_s=0.12, period_s=0.5, sample_s=0.1)


def test_old_membrane_calibration_round_trip():
    egg = synthetic(onset_s=1e9, pulses=FAST_PULSES)
    p = ref.calibrate_old(egg, 2.0e8, (0, 1), rtol=1e-9, method="LSODA")
    rm, _ = ref.rm_at(replace(egg, p_old=p), (0, 1), rtol=1e-9, method="LSODA")
    assert rm == pytest.approx(2.0e8, rel=1e-8)


def test_access_calibration_round_trip_on_a_small_cleft():
    egg = synthetic(
        onset_s=0.5,
        new_permeability=(1e-10, 1e-6, 0.0),
        schedule=((0.5, 0.0),),
        pulses=FAST_PULSES,
        activation_area_m2=1e-9,
    )
    kw = dict(rtol=1e-9, method="LSODA")
    sealed, _ = ref.rm_at(replace(egg, a_over_l_m=0.0), (2, 3), **kw)
    open_, _ = ref.rm_at(replace(egg, a_over_l_m=1e-3), (2, 3), **kw)
    target = math.sqrt(sealed * open_)
    al, log = ref.calibrate_access(egg, target, (2, 3), guess=1e-7, xtol=1e-8, **kw)
    rm, _ = ref.rm_at(replace(egg, a_over_l_m=al), (2, 3), **kw)
    assert sealed > 2 * target and target > 2 * open_
    assert rm == pytest.approx(target, rel=1e-7)
    assert len(log) <= 12


def test_secant_solver_falls_back_to_a_bracket():
    calls = []

    def miss(x):  # decreasing, kinked so the secant overshoots
        calls.append(x)
        return math.atan(-5.0 * (x - 1.3))

    x, log = ref.solve_decreasing(miss, -2.0, step=0.05, xtol=1e-12)
    assert x == pytest.approx(1.3, abs=1e-10)
    assert log and calls


# ---------------------------------------------------------------- declared inputs


def test_declared_inputs_build_the_registered_definition():
    d = ref.load_declared()
    assert d["status"].startswith("REGISTERED")
    values = ref.scalar_values(d)
    egg = ref.build(d, values)
    expected = d["inputs"]["new_membrane_specific_resistance_ohm_m2"][
        "derived_now_default_PK_m_per_s"
    ]
    assert egg.new_permeability[1] == pytest.approx(expected, rel=1e-7)
    assert egg.new_permeability[0] == pytest.approx(0.033522 * expected, rel=1e-6)
    assert egg.access_law == "logmean"
    assert egg.area(1800.0) == pytest.approx(1.39e-6, rel=1e-12)
    assert egg.schedule[0][1] * 60e6 == pytest.approx(0.0604, abs=5e-5)
    assert egg.gap_width_m == 2.0e-6 and egg.pulses.amplitude_A == 3e-8
    back = ref.build(d, ref.scalar_values(d, {"schedule": "back_loaded"}))
    assert back.area(1800.0) == pytest.approx(1.39e-6, rel=1e-12)
    assert back.area(1020.0) == pytest.approx(1e-9 + 6.6667e-10 * 600.0, rel=1e-12)
    with pytest.raises(KeyError):
        ref.scalar_values(d, {"unknown": 1.0})


def test_band_members_follow_the_registered_ranges():
    d = ref.load_declared()
    members = ref.band_members(d)
    assert len(members) == 23
    labels = [label for label, _ in members]
    assert "rm2_target_ohm:low" in labels and "insertion_schedule:back_loaded" in labels
    assert dict(members)["gap_width_m:high"] == {"gap_width_m": 2.5e-6}


def test_band_combination_is_the_registered_worst_case_sum():
    record = {"prediction_of_record_V": -0.0128}
    base = -0.0128 + 1e-12  # the band integrator's default, a hair off the record
    results = {
        "a:low": {"em_V": base - 0.002},
        "a:high": {"em_V": base + 0.001},
        "b:low": {"em_V": base + 0.0005},
        "b:high": {"em_V": base + 0.0015},  # both ends on one side
        "insertion_schedule:back_loaded": {"em_V": base - 0.0003},
    }
    band = ref.band_combination(record, base, results, None)
    assert band["lo_V"] == pytest.approx(-0.0128 - 0.0023, abs=1e-15)
    assert band["hi_V"] == pytest.approx(-0.0128 + 0.0025, abs=1e-15)
    assert band["width_V"] == pytest.approx(0.0048, abs=1e-15)
    assert band["per_input"]["a"]["largest_abs_V"] == pytest.approx(0.002, abs=1e-15)
