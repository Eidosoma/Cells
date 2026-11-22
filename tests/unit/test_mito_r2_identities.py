"""R2 (MT-1b's judged reference): the reference's own identities, as the documents declare them.

- Constants: the 50-digit derivations reproduce the laws appendix's printed values (K_base, m,
  the prefactor, Delta G deg_F, the species' potentials, the entries and section 10's band terms).
- Material and charge: every turnover conserves its moieties and moves q from N to P (appendix
  section 0); each outer-membrane form carries its rows' charge; the closure inverts exactly.
- Energy: each law's x agrees with sum nu mu deg/RT + sum nu ln c + q u within a small multiple of
  eps M (section 10); J x <= 0 for every process and face form; the outer membrane carries no net
  current (G5); dA/dt = held work + bath supply - dissipation at every state.
- A short integration closes the material, charge and energy ledgers.

Runs in about two seconds on one core: it evaluates the model at random states and integrates
2 ms from R2's start guesses; it compiles no world and imports nothing from src/cells.
"""

import math

import numpy as np
import pytest

from validation.mitochondria.references_r2 import constants, model, protocol

EPS = 2.0 ** -52
RNG_SEED = 20261122

ELECTRONS = {"NADH": 2, "QH2": 2, "c2": 1, "O2_N": -4, "O2_P": -4}
ADENINE = {"ATP_N": 1, "ADP_N": 1, "ATP_P": 1, "ADP_P": 1, "AMP_P": 1}
PHOSPHORUS = {"ATP_N": 3, "ADP_N": 2, "Pi_N": 1, "ATP_P": 3, "ADP_P": 2, "AMP_P": 1, "Pi_P": 1}
PAIRS = ({"NADH": 1, "NAD": 1}, {"QH2": 1, "Q": 1}, {"c2": 1, "c3": 1}, {"K_N": 1, "K_P": 1})
O2 = {"O2_N": 1, "O2_P": 1}  # conserved by every turnover but complex IV's, which uses one O2


@pytest.fixture(scope="module")
def world():
    return model.World()


def test_declared_constants_reproduce_the_appendix():
    assert constants.check_printed() == []


def test_turnovers_conserve_material_and_move_q(world):
    for name, (rows, q) in world.stoich.items():
        zN = sum(n * model.row_valence(r) for r, n in rows.items() if r in model.N_ROWS)
        zP = sum(n * model.row_valence(r) for r, n in rows.items() if r in model.P_ROWS)
        assert zN == -q and zP == q, name
        for moiety in (ADENINE, PHOSPHORUS) + PAIRS:
            assert sum(n * moiety.get(r, 0) for r, n in rows.items()) == 0, (name, moiety)
        assert sum(n * O2.get(r, 0) for r, n in rows.items()) == (-1 if name == "C4" else 0)
        electrons = sum(n * ELECTRONS.get(r, 0) for r, n in rows.items())
        assert electrons == (2 if name == "Supply" else 0), name  # the held pair gives two
    for form, z, carried, _ in model.FACE_FORMS:
        assert z == sum(n * model.row_valence(r) for r, n in carried.items()), form


def random_state(world, rng, o2="bath"):
    """A state on the appendix's section 10 grid, built from free values."""
    y = np.zeros(len(model.STATE))
    u = lambda a, b: rng.uniform(a, b)  # noqa: E731
    lu = lambda a, b: math.exp(rng.uniform(math.log(a), math.log(b)))  # noqa: E731
    y[0] = u(0.0, 250.0)
    for side, pH, Bt, KB in (("N", u(6.8, 8.2), world.B_N, world.KB_N),
                             ("P", u(6.5, 7.6), world.B_P, world.KB_P)):
        h, m = 10.0 ** -pH, lu(1e-4, 5e-3)
        adp = lu(1e-5, 5e-3)
        atp = adp * lu(1e-3, 1e3)
        pi = lu(1e-4, 2e-2)
        y[model.IDX["H_" + side]] = h + pi * h / (world.k_dH + h) + Bt * h / (KB + h)
        y[model.IDX["Mg_" + side]] = m + atp * m / (world.K_T + m) + adp * m / (world.K_D + m)
        y[model.IDX["ATP_" + side]], y[model.IDX["ADP_" + side]] = atp, adp
        y[model.IDX["Pi_" + side]] = pi
        y[model.IDX["K_" + side]] = lu(0.01, 0.2)
        y[model.IDX["O2_" + side]] = lu(1e-7, 3e-4)
    y[model.IDX["AMP_P"]] = lu(1e-6, 1e-3)
    for a, b, tot in (("NADH", "NAD", world.NAD_tot), ("QH2", "Q", world.Q_tot),
                      ("c2", "c3", world.cytC_tot)):
        f = u(0.01, 0.99)
        y[model.IDX[a]], y[model.IDX[b]] = f * tot, (1 - f) * tot
    y[model.IDX["O2_node"]] = lu(1e-7, 3e-4)
    return y


def controls(world, rng):
    return model.Controls(world, bath=["trace", "state3", "atp_bath"][rng.integers(3)],
                          a_unc=rng.uniform(0, 1), o2=["bath", "node"][rng.integers(2)])


def test_closure_inverts_and_x_agrees_with_the_potentials(world):
    rng = np.random.default_rng(RNG_SEED)
    mu = world.mu
    bands = world.c["bands"]
    ln1000 = math.log(1000.0)
    for _ in range(60):
        y = random_state(world, rng)
        ctl = controls(world, rng)
        ev = world.evaluate(list(y), ctl)
        N, P = world.forms(y)
        hN, mN, hP, mP = ev["free"]
        # The closure recovers the free values the state was built from.
        Pi_N, Bt = y[model.IDX["Pi_N"]], world.B_N
        rebuilt = hN + Pi_N * hN / (world.k_dH + hN) + Bt * hN / (world.KB_N + hN)
        assert abs(rebuilt - y[model.IDX["H_N"]]) <= 1e-14 * y[model.IDX["H_N"]]
        # x from the potentials table (appendix 9), free base forms, q u.
        pot = {
            "NADH": mu["NADH"] + math.log(N["NADH"]), "NAD": math.log(N["NAD"]),
            "QH2": mu["QH2"] + math.log(N["QH2"]), "Q": math.log(N["Q"]),
            "H_N": math.log(N["H"]), "H_P": math.log(P["H"]),
            "c2": mu["cytc_red"] + math.log(P["c2"]), "c3": math.log(P["c3"]),
            "O2_N": math.log(N["O2"]), "O2_P": math.log(P["O2"]),
            "ATP_N": mu["ATP"] + math.log(N["ATP4"]), "ADP_N": math.log(N["ADP3"]),
            "Pi_N": math.log(N["HPO4"]), "ATP_P": mu["ATP"] + math.log(P["ATP4"]),
            "ADP_P": math.log(P["ADP3"]), "Pi_P": math.log(P["HPO4"]),
            "AMP_P": mu["AMP"] + math.log(P["AMP"]), "K_N": math.log(N["K"]),
            "K_P": math.log(P["K"]),
        }
        for name, (rows, q) in world.stoich.items():
            x = sum(n * pot[r] for r, n in rows.items()) + q * ev["u"]
            if name == "Supply":
                x += world.mu_Sox_minus_Sred
            M = bands.get(name, sum(abs(n) * ln1000 for n in rows.values()))
            assert abs(x - ev["x"][name]) <= 64 * EPS * max(M, abs(x)), name


def test_dissipation_current_and_energy_identity(world):
    rng = np.random.default_rng(RNG_SEED + 1)
    for _ in range(60):
        y = random_state(world, rng)
        ctl = controls(world, rng)
        ev = world.evaluate(list(y), ctl)
        for name in model.PROCESSES:
            assert ev["J"][name] * ev["x"][name] <= 0.0, name
        for j, x in zip(ev["Jf"], world.face_x(ev), strict=True):
            assert j * x <= 0.0
        # No net charge crosses the outer membrane (G5).
        current = sum(z * j for z, j in zip(world.face_z, ev["Jf"], strict=True))
        magnitude = sum(abs(z * j) for z, j in zip(world.face_z, ev["Jf"], strict=True))
        assert abs(current) <= 1e-12 * magnitude
        # dA/dt from the row potentials equals held work + bath supply - dissipation.
        dy = world.rhs(0.0, y, ctl)
        N, P = world.forms(y)
        mu = world.mu
        pot = {
            "H_N": math.log(N["H"]), "K_N": math.log(N["K"]), "Mg_N": math.log(N["Mg"]),
            "ATP_N": mu["ATP"] + math.log(N["ATP4"]), "ADP_N": math.log(N["ADP3"]),
            "Pi_N": math.log(N["HPO4"]), "NADH": mu["NADH"] + math.log(N["NADH"]),
            "NAD": math.log(N["NAD"]), "QH2": mu["QH2"] + math.log(N["QH2"]),
            "Q": math.log(N["Q"]), "O2_N": math.log(N["O2"]),
            "H_P": math.log(P["H"]), "K_P": math.log(P["K"]), "Mg_P": math.log(P["Mg"]),
            "ATP_P": mu["ATP"] + math.log(P["ATP4"]), "ADP_P": math.log(P["ADP3"]),
            "AMP_P": mu["AMP"] + math.log(P["AMP"]), "Pi_P": math.log(P["HPO4"]),
            "O2_P": math.log(P["O2"]), "c2": mu["cytc_red"] + math.log(P["c2"]),
            "c3": math.log(P["c3"]),
        }
        terms = [pot[r] * dy[model.IDX[r]] * world.W_x for r in model.N_ROWS]
        terms += [pot[r] * dy[model.IDX[r]] * world.W_i for r in model.P_ROWS]
        terms.append(world.C_IM * world.f_mV * y[0] * dy[0])
        if ctl.o2 == "node":
            c = y[model.IDX["O2_node"]]
            terms.append(math.log(c) * dy[model.IDX["O2_node"]] * world.node_water)
        k = model.NPHYS
        dD = sum(dy[k + i] for i in range(len(model.PROCESSES) + 1))
        dW = dy[model.IDX["W_held"]] + dy[model.IDX["W_bath"]]
        scale = sum(abs(t) for t in terms) + abs(dD) + abs(dW)
        assert abs(sum(terms) - (dW - dD)) <= 1e-11 * scale


def test_short_integration_closes_the_ledgers(world):
    # From R2's start guesses, far from every law's equilibrium: 2 ms of fast transients.
    ctl = model.Controls(world, bath="trace")
    y0 = world.guess_state(ctl)
    sol, _ = protocol.integrate(world, y0, 0.0, 2e-3, ctl, np.array([0.0, 1e-3, 2e-3]), 1e-10)
    inv0 = world.invariants(sol.y[:, 0], ctl.o2)
    A0 = world.free_energy(sol.y[:, 0], ctl.o2)
    for k in range(1, sol.y.shape[1]):
        y = sol.y[:, k]
        inv = world.invariants(y, ctl.o2)
        scales = world.invariant_scales(y, ctl.o2)
        for key, v0 in inv0.items():
            assert abs(inv[key] - v0) <= 1e-12 * max(scales[key], 1e-300), key
        A, D, W = world.energy_terms(y, ctl.o2)
        assert D > 0.0
        assert abs((A - A0) + D - W) <= 1e-8 * D


def test_printed_exchange_is_the_declared_one_only_when_balanced():
    # Plant P-a's switch (erratum 2): Eq. 14's printed two-fraction form equals the declared
    # J = S (1 - e^x) when theta_P + theta_N = 1. With the plant's 0.35 and 0.70 its zero moves to
    # x = 0.05 u, so between x = 0 and 0.05 u it runs against its own x.
    rng = np.random.default_rng(RNG_SEED + 3)
    declared = model.World()
    printed = model.World(overrides={"exchange_form": "printed"})
    planted = model.World(overrides={"exchange_form": "printed", "theta_N": 0.70})
    for _ in range(30):
        y = random_state(declared, rng)
        ctl = model.Controls(declared)
        j0 = declared.evaluate(list(y), ctl)["J"]["ANT"]
        j1 = printed.evaluate(list(y), model.Controls(printed))["J"]["ANT"]
        assert abs(j1 - j0) <= 1e-12 * declared.X_ANT
        # Set dPsi so that the exchange's x = L - u is 0.025 u, a little past its equilibrium.
        ev = declared.evaluate(list(y), ctl)
        L = ev["x"]["ANT"] + ev["u"]
        if abs(L) < 0.5:
            continue
        y[0] = L / 1.025 / declared.f_mV
        ev = declared.evaluate(list(y), ctl)
        assert abs(ev["x"]["ANT"] - 0.025 * ev["u"]) < 1e-9 * abs(ev["u"])
        assert ev["J"]["ANT"] * ev["x"]["ANT"] < 0.0
        ev = planted.evaluate(list(y), model.Controls(planted))
        assert ev["J"]["ANT"] * ev["x"]["ANT"] > 0.0
