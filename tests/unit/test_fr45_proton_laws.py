"""Contract tests for FR-4's law kernels (docs/COMPARTMENT_PH_TRANSFER_DESIGN.md).

cells.kind.rapid_proton_buffer@1, cells.cycle.proton_atp_mass_action_positive@1, cells.route.passive_neutral_permeation@1 and
cells.route.proton_constant_field_leak@1: pure kernels, checked in NumPy (xp=np) against their defining
equations, with one JAX agreement check. Planted errors must fail where stated.
"""

import math

import numpy as np
import pytest

from cells.laws.electrochemistry import F, R
from cells.laws.pumps import proton_pump as pump
from cells.laws.reactions import rapid_proton_buffer as buf
from cells.laws.routes import constant_field_permeation as cfp
from cells.laws.routes import passive_permeation as passive
from cells.laws.transport import proton_leak as leak

T = 310.0
LN10 = math.log(10.0)
DECL = np.array([[True]])  # the declared (node, row) pair
DECL2 = np.array([[True], [False]])  # B_L declared in the lumen; B_c absent there


def ph_to_h(ph):
    return 1000.0 * 10.0 ** (-ph)


# --- cells.kind.rapid_proton_buffer@1 -------------------------------------------------------------------


def test_k_from_registry_potentials_gives_the_declared_pk():
    # §13's entries: (mu_HB - mu_B)/RT = -pK ln 10 with mu_H = 0.
    for pk in (7.2, 6.0):
        k = buf.dissociation_constant_mM(-pk * LN10, 0.0, c0_mM=1000.0, xp=np)
        assert -math.log10(k / 1000.0) == pytest.approx(pk, abs=1e-12)


@pytest.mark.parametrize("ph", [4.0, 5.0, 6.0, 7.2, 8.0])
def test_one_buffer_closed_form_recovers_the_equilibrium_h(ph):
    k = ph_to_h(6.0)
    h = ph_to_h(ph)
    b = 40.0
    total = h + b * h / (h + k)  # H_eq / V at that pH
    got, valid = buf.free_proton(np.array([total]), np.array([[b]]), np.array([[k]]), xp=np)
    assert valid.all()
    assert got[0] == pytest.approx(h, rel=1e-12)


def test_bisection_agrees_with_the_closed_form_and_solves_two_buffers():
    k = np.array([[ph_to_h(6.0)], [ph_to_h(7.2)]])
    b = np.array([[40.0], [0.0]])
    total = np.array([ph_to_h(5.0) + 40.0 * ph_to_h(5.0) / (ph_to_h(5.0) + k[0, 0])])
    two, ok2 = buf.free_proton(total, b, k, xp=np)  # bisection path (two rows, one empty)
    one, ok1 = buf.free_proton(total, b[:1], k[:1], xp=np)
    assert ok1.all() and ok2.all()
    assert two[0] == pytest.approx(one[0], rel=1e-13)
    b2 = np.array([[40.0], [50.0]])
    h, ok = buf.free_proton(np.array([60.0]), b2, k, xp=np)
    assert ok.all()
    assert abs(buf.residual(h, np.array([60.0]), b2, k, xp=np)[0]) <= 1e-13 * 60.0


def test_unbuffered_node_reads_h_equal_to_its_total():
    h, ok = buf.free_proton(np.array([3e-5]), np.array([[0.0]]), np.array([[1e-3]]), xp=np)
    assert ok.all() and h[0] == pytest.approx(3e-5, rel=1e-14)


def test_inadmissible_states_are_invalid():
    for total, b, k in (
        (0.0, 40.0, 1e-3),
        (-1.0, 40.0, 1e-3),
        (1.0, -1.0, 1e-3),
        (1.0, 4.0, 0.0),
        (float("nan"), 4.0, 1e-3),
    ):
        _, ok = buf.free_proton(np.array([total]), np.array([[b]]), np.array([[k]]), xp=np)
        assert not ok.any(), (total, b, k)


def test_buffer_capacity_matches_a_finite_difference():
    k, b, ph = ph_to_h(6.0), 40.0, 6.3
    h = ph_to_h(ph)

    def total(p):
        hh = ph_to_h(p)
        return hh + b * hh / (hh + k)

    fd = -(total(ph + 1e-6) - total(ph - 1e-6)) / 2e-6
    beta = buf.buffer_capacity(np.array([h]), np.array([[b]]), np.array([[k]]), xp=np)[0]
    assert beta == pytest.approx(fd, rel=1e-6)


def test_closure_energy_derivative_is_the_free_proton_potential():
    # dG*/dH_eq = mu_H(free) = RT (ln h - ln c0) + mu_H°, in J/mol (G* in pJ, amounts in fmol).
    v, k, b_tot = 0.0654498, ph_to_h(6.0), 40.0 * 0.0654498
    mu_a, mu_b = -6.0 * LN10, 0.0
    h_eq = 20.0 * v
    eps = 1e-6 * h_eq
    args = (np.array([[b_tot]]), v, np.array([[k]]), 0.0, np.array([[mu_a]]), np.array([[mu_b]]), T)
    g_plus, ok1 = buf.closure_free_energy_pJ(np.array([h_eq + eps]), *args, c0_mM=1000.0, xp=np)
    g_minus, ok2 = buf.closure_free_energy_pJ(np.array([h_eq - eps]), *args, c0_mM=1000.0, xp=np)
    assert ok1.all() and ok2.all()
    slope = (g_plus[0] - g_minus[0]) / (2 * eps) * 1e3  # J/mol
    h, _ = buf.free_proton(np.array([h_eq / v]), np.array([[b_tot / v]]), np.array([[k]]), xp=np)
    assert slope == pytest.approx(R * T * (math.log(h[0]) - math.log(1000.0)), rel=1e-6)


def test_closure_speciation_minimises_the_free_energy():
    # Moving one bound proton off equilibrium (at fixed totals) raises G.
    k = ph_to_h(6.0)
    h_eq, b_tot = 20.0, 40.0
    h, _ = buf.free_proton(np.array([h_eq]), np.array([[b_tot]]), np.array([[k]]), xp=np)
    acid, _ = buf.speciation(h, np.array([[b_tot]]), np.array([[k]]), xp=np)
    mu_a = math.log(k / 1000.0)

    def g(h_free, a):
        b = b_tot - a
        terms = [(h_free, 0.0), (a, mu_a), (b, 0.0)]
        return sum(c * (math.log(c) - 1 + mu - math.log(1000.0)) for c, mu in terms)

    at_eq = g(h[0], acid[0, 0])
    for d in (1e-4, -1e-4):
        assert g(h[0] + d, acid[0, 0] - d) > at_eq


def test_envelope_flags_the_declared_outside_case_and_admits_the_inside_ones():
    # §4.2, revised: the FR-4 lumen at its start (pH 7.2, B_L 40 mM, pK 6), rho = 0.031 /s (the
    # pump's saturation S = 0.276 there). The check is the estimated lag within 1e-3 pH.
    h = np.array([ph_to_h(7.2)])
    b = np.array([[40.0]])
    k = np.array([[ph_to_h(6.0)]])
    rate = 0.031 * buf.buffer_capacity(h, b, k, xp=np) / LN10  # mM/s giving rho = 0.031 /s
    assert buf.envelope_valid(h, b, k, np.array([[1e7]]), rate, DECL, xp=np).all()
    assert buf.envelope_valid(h, b, k, np.array([[1e5]]), rate, DECL, xp=np).all()
    assert not buf.envelope_valid(h, b, k, np.array([[1e-3]]), rate, DECL, xp=np).any()


def test_planted_the_old_fixed_ratio_admits_a_case_the_lag_check_refuses():
    # The FR-4 references' run 02: at k_on = 1e3 /mM/s, lambda/rho is about 1.2e3 (the old
    # lambda >= 1e3 rho passes) while the lumen lags the closure by about 1.26e-2 pH.
    h = np.array([ph_to_h(7.2)])
    b = np.array([[40.0]])
    k = np.array([[ph_to_h(6.0)]])
    rate = 0.031 * buf.buffer_capacity(h, b, k, xp=np) / LN10
    k_on = np.array([[1e3]])
    lam = buf.relaxation_rate(h, b, k, k_on, DECL, xp=np)
    rho = buf.drive_rate(rate, h, b, k, xp=np)
    assert (lam >= 1e3 * rho).all()  # the old check would pass
    lag = buf.lag_estimate_ph(h, b, k, k_on, rate, DECL, xp=np)
    assert lag[0] == pytest.approx(1.26e-2, rel=0.05)  # the references' measured lag
    assert not buf.envelope_valid(h, b, k, k_on, rate, DECL, xp=np).any()
    # The threshold the references found: the budget holds from k_on of about 1.28e4.
    assert buf.envelope_valid(h, b, k, np.array([[1.3e4]]), rate, DECL, xp=np).all()
    assert not buf.envelope_valid(h, b, k, np.array([[1.2e4]]), rate, DECL, xp=np).any()


def test_stage_read_over_cells_and_outside_nodes():
    structure = buf.ReadStructure(proton_row=0, buffer_rows=(1,), declared=((False, True),))
    v = np.array([4.18879, 0.0654498])
    k = np.array([ph_to_h(6.0)])
    h_lumen = ph_to_h(5.0)
    total_lumen = h_lumen + 40.0 * h_lumen / (h_lumen + k[0])
    cell = np.array([[1e-4 * v[0]], [0.0]])
    outside = np.array([[total_lumen * v[1]], [40.0 * v[1]]])
    p = buf.ReadLayout(
        volume_pL=v, k_mM=k, k_on_per_mM_s=np.array([1e7]), c0_mM=1000.0, temperature_K=T
    )
    values, valid = buf.evaluate(structure, cell, outside, p, xp=np)
    assert valid.all()
    assert values["h"][0] == pytest.approx(1e-4, rel=1e-12)
    assert values["pH"][1] == pytest.approx(5.0, abs=1e-12)


def test_jax_agrees_with_numpy_for_the_closure():
    jnp = pytest.importorskip("jax.numpy")
    import jax

    jax.config.update("jax_enable_x64", True)
    total = np.array([1e-3, 5.0, 60.0])
    b = np.array([[40.0, 40.0, 40.0], [50.0, 0.0, 10.0]])
    k = np.array([[1e-3], [6.3e-5]])
    h_np, ok_np = buf.free_proton(total, b, k, xp=np)
    h_jx, ok_jx = buf.free_proton(jnp.asarray(total), jnp.asarray(b), jnp.asarray(k), xp=jnp)
    assert ok_np.all() and np.asarray(ok_jx).all()
    np.testing.assert_allclose(np.asarray(h_jx), h_np, rtol=1e-13)


# --- cells.cycle.proton_atp_mass_action_positive@1 -------------------------------------------------------


H_REST = 1000.0 * 10.0 ** (-7.2)


def pump_inputs(h_in=H_REST, h_out=H_REST, v=0.0):
    return pump.Inputs(
        h_in_mM=h_in,
        h_out_mM=h_out,
        voltage_V=v,
        atp_mM=3.0,
        adp_mM=0.3,
        pi_mM=3.0,
        temperature_K=T,
    )


PUMP = pump.Parameters(
    capacity_fmol_s=8.3027e-3,
    protons_per_cycle=2.0,
    km_proton_mM=1e-4,
    km_atp_mM=0.1,
    delta_g0_prime_J_mol=-30500.0,
    fuel_ph_ref=7.2,
    fuel_ph_band=0.05,
)


def test_the_held_fuel_drive_is_the_note_value():
    drive = pump.chemical_drive(pump_inputs(), PUMP, xp=np)
    assert drive == pytest.approx(-30500.0 + R * T * math.log(0.3 * 3.0 / (3.0 * 1000.0)))
    assert drive / 1000 == pytest.approx(-51.41, abs=0.01)


def test_forward_at_rest_zero_at_static_head_and_reversed_beyond():
    rates = pump.kinetics(pump_inputs(), PUMP, 1.0, xp=np)
    assert rates.cycles_fmol_s > 0
    drive = pump.chemical_drive(pump_inputs(), PUMP, xp=np)
    v_head = drive / (2 * F)  # n (-F V) = -drive at equal pH: V = drive / (n F) < 0
    at_head = pump.kinetics(pump_inputs(v=v_head), PUMP, 1.0, xp=np)
    assert abs(at_head.cycle_free_energy_J_mol) < 1e-9
    assert abs(at_head.cycles_fmol_s) < 1e-12 * rates.cycles_fmol_s
    beyond = pump.kinetics(pump_inputs(v=v_head - 0.01), PUMP, 1.0, xp=np)
    assert beyond.cycles_fmol_s < 0
    assert pump.heat_pJ_s(beyond) >= 0 and pump.heat_pJ_s(rates) >= 0


def test_heat_plus_transport_free_energy_equals_supplied_work():
    i = pump_inputs(h_in=ph_to_h(7.2), h_out=ph_to_h(5.5), v=-0.02)
    rates = pump.kinetics(i, PUMP, 1.0, xp=np)
    transport = 2 * (R * T * math.log(i.h_out_mM / i.h_in_mM) - F * i.voltage_V)
    stored_rate = 1e-3 * rates.cycles_fmol_s * transport  # pJ/s into the gradient
    assert pump.work_pJ_s(rates) == pytest.approx(pump.heat_pJ_s(rates) + stored_rate, rel=1e-12)


def test_electrogenic_conductance_matches_a_finite_difference():
    i = pump_inputs(h_out=ph_to_h(6.0), v=-0.1)
    dv = 1e-7
    up = pump.kinetics(pump_inputs(h_out=ph_to_h(6.0), v=-0.1 + dv), PUMP, 1.0, xp=np)
    dn = pump.kinetics(pump_inputs(h_out=ph_to_h(6.0), v=-0.1 - dv), PUMP, 1.0, xp=np)
    fd = abs(up.cycles_fmol_s - dn.cycles_fmol_s) / (2 * dv) * 2 * F * 1e-15
    assert pump.electrogenic_conductance_S(i, PUMP, 1.0, xp=np) == pytest.approx(fd, rel=1e-6)


def test_domain_refuses_a_non_integer_stoichiometry_and_an_extreme_affinity():
    bad_n = PUMP._replace(protons_per_cycle=2.5)
    assert not pump.domain_valid(pump_inputs(), bad_n, 1.0, xp=np)
    assert not pump.domain_valid(pump_inputs(), PUMP._replace(protons_per_cycle=5.0), 1.0, xp=np)
    assert pump.domain_valid(pump_inputs(), PUMP, 1.0, xp=np)
    assert not pump.domain_valid(pump_inputs(v=-2.0), PUMP, 1.0, xp=np)  # |dG/RT| > 80


def test_zero_availability_is_an_exact_zero():
    assert pump.kinetics(pump_inputs(), PUMP, 0.0, xp=np).cycles_fmol_s == 0.0


# --- cells.route.passive_neutral_permeation@1 ------------------------------------------------------------


def test_neutral_flux_is_ficks_law_and_antisymmetric():
    j = passive.flux_fmol_s(1.0, 10.0, 7.854e-13, 4.12e-8, 1.0, xp=np)
    assert j == pytest.approx(7.854e-13 * 4.12e-8 * 9.0 / 1e-15, rel=1e-14)
    assert passive.flux_fmol_s(10.0, 1.0, 7.854e-13, 4.12e-8, 1.0, xp=np) == pytest.approx(-j)
    assert passive.flux_fmol_s(3.0, 3.0, 7.854e-13, 4.12e-8, 1.0, xp=np) == 0.0


def test_exact_booking_equals_the_free_energy_decrease_of_a_closed_pair():
    v1, v2 = 0.5, 2.0
    n1_0, n2_0, moved = 0.4, 30.0, 2.5  # moved into node 1 from node 2 over a large step
    n1_1, n2_1 = n1_0 + moved, n2_0 - moved

    def g(n, v):
        return R * T * n * (math.log(n / v) - 1) * 1e-3

    decrease = (g(n1_0, v1) + g(n2_0, v2)) - (g(n1_1, v1) + g(n2_1, v2))
    mu1 = passive.divided_potential_RT(n1_0, n1_1, v1, xp=np)
    mu2 = passive.divided_potential_RT(n2_0, n2_1, v2, xp=np)
    heat = passive.route_heat_pJ(moved, mu1, mu2, T, xp=np)
    assert heat == pytest.approx(decrease, rel=1e-13)
    assert heat > 0


def test_a_start_at_zero_amount_books_finite_heat():
    v1, v2, moved = 0.5, 2.0, 1e-3
    mu1 = passive.divided_potential_RT(0.0, moved, v1, xp=np)
    mu2 = passive.divided_potential_RT(20.0, 20.0 - moved, v2, xp=np)
    heat = passive.route_heat_pJ(moved, mu1, mu2, T, xp=np)
    assert np.isfinite(heat) and heat > 0
    exact = (R * T * 1e-3) * (
        (20.0 * (math.log(20.0 / v2) - 1))
        - (
            moved * (math.log(moved / v1) - 1)
            + (20.0 - moved) * (math.log((20.0 - moved) / v2) - 1)
        )
    )
    assert heat == pytest.approx(exact, rel=1e-10)


def test_divided_potential_tends_to_the_potential_for_a_tiny_change():
    n, v = 3.0, 0.7
    mu = passive.divided_potential_RT(n, n * (1 + 1e-9), v, xp=np)
    assert mu == pytest.approx(math.log(n / v), rel=1e-8)


# --- cells.route.proton_constant_field_leak@1 ------------------------------------------------------------


def test_proton_leak_is_zero_at_electrochemical_equilibrium_and_dissipative_elsewhere():
    h_in, h_out = ph_to_h(7.2), ph_to_h(5.0)
    v_eq = R * T / F * math.log(h_out / h_in)  # inside minus outside at zero flux
    j0 = leak.flux_fmol_s(h_in, h_out, v_eq, T, 7.854e-10, 6e-7, 1.0, xp=np)
    j = leak.flux_fmol_s(h_in, h_out, 0.0, T, 7.854e-10, 6e-7, 1.0, xp=np)
    assert abs(j0) < 1e-12 * abs(j)
    assert j > 0  # inward, from the acid lumen to the cytosol
    assert leak.heat_pJ_s(j, h_in, h_out, 0.0, T, xp=np) > 0


@pytest.mark.parametrize("valence", [-2, -1, 1, 2])
def test_the_charged_route_law_is_the_leaks_flux_at_any_valence(valence):
    """FR-15 P2's kernel (laws/routes/constant_field_permeation.py; host side): zero flux at
    electrochemical equilibrium and dissipative elsewhere; at z = +1 the leak's flux bit for bit;
    the max-side conductance bounds the current's slope at every voltage tried; and the material
    slope at each end is the flux's |dJ/dn| (central differences)."""
    area, perm, c_in, c_out, v_in, v_out = 7.854e-10, 6e-7, 1e-3, 3e-3, 0.8, 2.5
    v_eq = R * T / (valence * F) * math.log(c_out / c_in)
    j0 = cfp.flux_fmol_s(c_in, c_out, v_eq, valence, T, area, perm, 1.0, xp=np)
    for v in (-0.12, 0.0, 0.07):
        j = cfp.flux_fmol_s(c_in, c_out, v, valence, T, area, perm, 1.0, xp=np)
        assert abs(j0) < 1e-12 * abs(j)
        assert cfp.heat_pJ_s(j, c_in, c_out, v, valence, T, xp=np) > 0
        if valence == 1:
            assert j == leak.flux_fmol_s(c_in, c_out, v, T, area, perm, 1.0, xp=np)
        dv = 1e-7
        current = [
            valence
            * F
            * 1e-15
            * cfp.flux_fmol_s(c_in, c_out, u, valence, T, area, perm, 1.0, xp=np)
            for u in (v - dv, v + dv)
        ]
        slope = abs(current[1] - current[0]) / (2 * dv)
        bound = cfp.conductance_S(c_in, c_out, v, valence, T, area, perm, 1.0, xp=np)
        assert slope <= bound * (1 + 1e-6)
        rates = cfp.material_slope_per_s(v, valence, T, area, perm, 1.0, v_in, v_out, xp=np)
        dn = 1e-5  # J is linear in each amount, so the central difference is exact to rounding.
        for k, (volume, before, after) in enumerate(
            (
                (v_in, (c_in - dn / v_in, c_out), (c_in + dn / v_in, c_out)),
                (v_out, (c_in, c_out - dn / v_out), (c_in, c_out + dn / v_out)),
            )
        ):
            change = cfp.flux_fmol_s(
                *after, v, valence, T, area, perm, 1.0, xp=np
            ) - cfp.flux_fmol_s(*before, v, valence, T, area, perm, 1.0, xp=np)
            assert abs(change) / (2 * dn) == pytest.approx(float(rates[k]), rel=1e-6), (k, volume)


def test_planted_sign_error_in_the_leak_heat_is_caught():
    h_in, h_out = ph_to_h(7.2), ph_to_h(5.0)
    j = leak.flux_fmol_s(h_in, h_out, 0.0, T, 7.854e-10, 6e-7, 1.0, xp=np)
    assert -leak.heat_pJ_s(j, h_in, h_out, 0.0, T, xp=np) < 0  # the planted error fails


# --- review additions (the advisor, 15 November) ---------------------------------------------


def test_envelope_ignores_a_buffer_row_absent_at_the_node():
    # §13's layout: two buffer rows, B_c absent in the lumen. The inside case k_on = 1e5 must pass.
    h = np.array([ph_to_h(7.2)])
    b = np.array([[40.0], [0.0]])
    k = np.array([[ph_to_h(6.0)], [ph_to_h(7.2)]])
    rate = 0.1 * buf.buffer_capacity(h, b, k, xp=np) / LN10
    assert buf.envelope_valid(h, b, k, np.array([[1e5], [1e5]]), rate, DECL2, xp=np).all()
    assert not buf.envelope_valid(h, b, k, np.array([[1e-3], [1e5]]), rate, DECL2, xp=np).any()
    unbuffered = buf.relaxation_rate(
        h, np.zeros((2, 1)), k, np.array([[1e5], [1e5]]), np.zeros((2, 1), bool), xp=np
    )
    assert np.isinf(unbuffered).all()


def test_pump_and_leak_signs_combine_at_the_lumen():
    # Inward-positive throughout: the pump's inward transfer is -n cycles; the lumen (outside)
    # gains minus every inward flux. An acid lumen leaks inward, so its gain is n c - J_leak.
    i = pump_inputs(h_out=ph_to_h(5.5), v=-0.01)
    rates = pump.kinetics(i, PUMP, 1.0, None, xp=np)
    pumped_in = pump.proton_inward_fmol_s(rates, PUMP)
    leak_in = leak.flux_fmol_s(i.h_in_mM, i.h_out_mM, i.voltage_V, T, 7.854e-10, 6e-7, 1.0, xp=np)
    lumen_gain = -(pumped_in + leak_in)
    assert rates.cycles_fmol_s > 0 and pumped_in < 0 and leak_in > 0
    assert lumen_gain == pytest.approx(2 * rates.cycles_fmol_s - leak_in, rel=1e-14)
    assert pump.MOVES == (("proton", "-protons_per_cycle"),)


def test_loop_rates_match_finite_differences_at_both_nodes():
    base = pump_inputs(h_in=ph_to_h(7.21), h_out=ph_to_h(6.0), v=-0.05)
    q_in, v_in, q_out, v_out = 0.4, 4.18879, 0.2, 0.0654498
    inside, outside = pump.loop_rates_per_s(base, PUMP, 1.0, q_in, v_in, q_out, v_out, xp=np)

    def cycles(h_in, h_out):
        return pump.kinetics(base._replace(h_in_mM=h_in, h_out_mM=h_out), PUMP, 1.0, xp=np)[0]

    for which, got, h0, q, v in (
        ("in", inside, base.h_in_mM, q_in, v_in),
        ("out", outside, base.h_out_mM, q_out, v_out),
    ):
        dh = 1e-7 * h0
        if which == "in":
            d = (cycles(h0 + dh, base.h_out_mM) - cycles(h0 - dh, base.h_out_mM)) / (2 * dh)
        else:
            d = (cycles(base.h_in_mM, h0 + dh) - cycles(base.h_in_mM, h0 - dh)) / (2 * dh)
        assert got == pytest.approx(abs(2 * d) * q / v, rel=1e-5), which


def test_domain_refuses_the_fuel_node_outside_its_ph_band():
    assert pump.domain_valid(pump_inputs(h_in=ph_to_h(7.24)), PUMP, 1.0, xp=np)
    assert not pump.domain_valid(pump_inputs(h_in=ph_to_h(7.3)), PUMP, 1.0, xp=np)


def test_the_read_closes_over_its_structure_and_takes_the_published_arguments():
    read = buf.make_read(
        buf.ReadStructure(proton_row=0, buffer_rows=(1,), declared=((False, True),))
    )
    v = np.array([1.0, 0.5])
    p = buf.ReadLayout(
        volume_pL=v,
        k_mM=np.array([ph_to_h(6.0)]),
        k_on_per_mM_s=np.array([1e7]),
        c0_mM=1000.0,
        temperature_K=T,
    )
    values, valid = read.evaluate(np.array([[2e-4], [0.0]]), np.array([[10.0], [20.0]]), p, xp=np)
    assert read.read_id == "cells.kind.rapid_proton_buffer@1" and valid.all()
    assert values["h"][0] == pytest.approx(2e-4, rel=1e-13)


def test_declared_term_at_an_unbuffered_node_is_minus_rt_ln_c0_per_proton():
    # mu°(H+) = 0 at c0 = 1000 mM, while the inner model's row term is referenced to 1 mM, so the
    # declared term is -RT ln(1000) per proton, not zero: it must be evaluated on every H node.
    n, v = 2e-5, 0.5
    term, ok = buf.declared_term_pJ(
        np.array([n]),
        np.zeros((1, 1)),
        v,
        np.array([[1e-3]]),
        0.0,
        np.zeros((1, 1)),
        np.zeros((1, 1)),
        T,
        c0_mM=1000.0,
        xp=np,
    )
    assert ok.all()
    assert term[0] == pytest.approx(-1e-3 * R * T * n * math.log(1000.0), rel=1e-12)


# --- the lead's rulings (registry c0, declared-pair masks) -------------------------------------


def test_planted_registry_c0_conversion_gives_the_same_k():
    # Potentials at c0 = 1000 mM give pK 7.2 and 6.0. Converted consistently to c0 = 1 mM (each
    # species' mu/RT gains ln(c0'/c0)), they give the same K. The unconverted entries at 1 mM are
    # off by ln(c0/1000): 3 pH units.
    shift = math.log(1.0 / 1000.0)
    for pk in (7.2, 6.0):
        k1000 = buf.dissociation_constant_mM(-pk * LN10, 0.0, 0.0, c0_mM=1000.0, xp=np)
        k1 = buf.dissociation_constant_mM(-pk * LN10 + shift, shift, shift, c0_mM=1.0, xp=np)
        assert k1 == pytest.approx(k1000, rel=1e-12)
        wrong = buf.dissociation_constant_mM(-pk * LN10, 0.0, 0.0, c0_mM=1.0, xp=np)
        assert -math.log10(wrong / k1000) == pytest.approx(3.0, abs=1e-12)


def test_planted_an_undeclared_trace_leaves_h_bitwise_unchanged():
    # B_L declared in the lumen only; a B_L trace in the cytosol is a free row there, not a buffer.
    structure = buf.ReadStructure(
        proton_row=0, buffer_rows=(1, 2), declared=((True, False), (False, True))
    )
    v = np.array([4.18879, 0.0654498])
    p = buf.ReadLayout(
        volume_pL=v,
        k_mM=np.array([ph_to_h(7.2), ph_to_h(6.0)]),
        k_on_per_mM_s=np.array([1e7, 1e7]),
        c0_mM=1000.0,
        temperature_K=T,
    )
    cell = np.array([[30.0 * v[0]], [50.0 * v[0]], [0.0]])
    lumen = np.array([[20.0 * v[1]], [0.0], [40.0 * v[1]]])
    base, ok = buf.evaluate(structure, cell, lumen, p, xp=np)
    cell_t = cell.copy()
    cell_t[2, 0] = 1e-9 * v[0]  # an undeclared B_L trace in the cytosol
    lumen_t = lumen.copy()
    lumen_t[1, 0] = 1e-9 * v[1]  # an undeclared B_c trace in the lumen
    traced, ok_t = buf.evaluate(structure, cell_t, lumen_t, p, xp=np)
    assert ok.all() and ok_t.all()
    assert np.array_equal(base["h"], traced["h"])
