"""Self-tests of the independent references for cells.operator.species_regulated_availability@1
(validation/coupling/): R-fac, R-state, R-cell and R-feedback.

They are checked against analytic limits (closed forms, Hill identities, the quasi-steady limit),
against each other where they overlap (decimal against float64, quadrature against adaptive
integration, two integrators), and against R-tissue (validation/division/cleft_tissue_reference,
its static entry point only) where availability is constant. The first tests check that the
references stay independent of the engine: nothing under validation/coupling/ imports `cells`,
statically or in a fresh process, and the only thing taken from validation.division is R-full's
flux law. Every world here is synthetic.
"""

import ast
import math
import subprocess
import sys
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np
import pytest

from validation.coupling import cells_reference as rc
from validation.coupling import factor_reference as fr
from validation.coupling import state_reference as rs

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "coupling"
FORBIDDEN_TOP = {"cells", "jax", "jaxlib"}
ALLOWED_DIVISION = {"validation.division.cleft_egg_reference": {"ghk_flux"}}

# Synthetic worlds (S5's style). F and R are the exact SI products, passed in as inputs.
F_SI = 6.02214076e23 * 1.602176634e-19
R_SI = 6.02214076e23 * 1.380649e-23
CONST = rc.Constants(F_SI, R_SI, 300.0)
SP, Z = ("Na", "K", "Cl"), (1, 1, -1)
BATH = (140.0, 5.0, 145.0)
CYT_A, CYT_B = (12.0, 140.0, 30.0), (30.0, 120.0, 30.0)
LEAK = (1e-10, 2e-9, 5e-10)  # m/s per unit area
AREA, CAP, VOL = 4e-10, 4e-12, 2.0
KLEAK = (0.0, 1.0, 0.0)  # cells.channel.kleak_always_open@1's relative permeabilities
SMALL = dict(cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-12, cleft_amount=1e-14,
             heat=1e-15)  # R-tissue's tissue-scale tolerances (its tests' values)


# ------------------------------------------------------------------------ independence


def _imports(path):
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name, None
        elif isinstance(node, ast.ImportFrom):
            yield "." * node.level + (node.module or ""), tuple(a.name for a in node.names)
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "id", None) or getattr(func, "attr", None)
            if name in {"__import__", "import_module", "run_module", "run_path"}:
                yield "<dynamic import>", None


def test_references_import_nothing_from_cells():
    files = sorted(REFERENCES.glob("*.py"))
    assert len(files) >= 4
    for path in files:
        for name, names in _imports(path):
            assert name != "<dynamic import>", (path.name, name)
            assert not name.startswith("."), (path.name, "relative import", name)
            assert name.split(".")[0] not in FORBIDDEN_TOP, (path.name, name)
            if name.startswith("validation") and not name.startswith("validation.coupling"):
                # Only `from validation.division.cleft_egg_reference import ghk_flux`.
                assert name in ALLOWED_DIVISION and names is not None, (path.name, name)
                assert set(names) <= ALLOWED_DIVISION[name], (path.name, names)


def test_references_load_no_cells_j1_or_partition_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    banned = ("cells", "jax", "jaxlib")
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.coupling.{m}\n" for m in modules)
        + f"bad = sorted(m for m in sys.modules if m.split('.')[0] in {banned!r})\n"
        + "bad += sorted(m for m in sys.modules if m.startswith('validation.division.')\n"
        + "              and m != 'validation.division.cleft_egg_reference')\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0, out.stdout + out.stderr


# ------------------------------------------------------------------------ R-fac

GRID_X = np.concatenate([[0.0, 1e-300], np.logspace(-9, 9, 37), [0.37, 0.37 * (1 + 1e-15)]])


@pytest.mark.parametrize("law", fr.HILL_LAWS)
@pytest.mark.parametrize("n", [0.5, 1.0, 2.0, 4.0, 7.3])
def test_float_hill_is_within_a_few_ulps_of_the_exact_law(law, n):
    exact = fr.exact_grid(law, 0.0, x=GRID_X, K=0.37, n=n)
    approx = fr.law_value(law, x=GRID_X, K=0.37, n=n)
    assert int(np.max(fr.ulp_distance(approx, exact))) <= 2 + math.ceil(n / 2)


def test_exact_hill_against_the_literal_sixty_digit_formula():
    rng = np.random.default_rng(7)
    for _ in range(40):
        x, K = 10.0 ** rng.uniform(-6, 6, 2)
        n = float(rng.choice([1.0, 2.0, 3.7, 0.6]))
        with localcontext(prec=60):
            xd, kd, nd = Decimal(x), Decimal(K), Decimal(n)
            literal = xd**nd / (kd**nd + xd**nd)
            act = fr.exact_hill("hill_activation", x, K, n)
            inh = fr.exact_hill("hill_inhibition", x, K, n)
            assert abs(act - literal) <= Decimal("1e-36") * literal
            assert abs(act + inh - 1) <= Decimal("1e-38")


def test_hill_identities_at_zero_and_at_K():
    for n in (0.5, 1.0, 3.0):
        assert fr.hill_activation(0.0, 2.0, n) == 0.0 and fr.hill_inhibition(0.0, 2.0, n) == 1.0
        assert fr.hill_activation(2.0, 2.0, n) == 0.5 and fr.hill_inhibition(2.0, 2.0, n) == 0.5
        assert fr.to_float(fr.exact_hill("hill_activation", 2.0, 2.0, n)) == 0.5
    big = fr.hill_activation(1e300, 1e-300, 8.0)
    assert big == 1.0 and fr.hill_inhibition(1e300, 1e-300, 8.0) == 0.0  # no overflow


def test_basal_combination_and_switch():
    s = np.linspace(0.0, 1.0, 11)
    for b in (0.0, 0.2, 0.75):
        F = fr.coupling_factor("state_fraction", b, s=s)
        assert np.array_equal(F, b + (1.0 - b) * s)
        assert fr.coupling_factor("state_complement", b, s=1.0) == b
        assert fr.coupling_factor("state_fraction", b, s=1.0) == 1.0
        assert fr.coupling_factor("state_fraction", b, s=0.3, enabled=False) == 1.0
    assert np.array_equal(fr.coupling_factor("state_fraction", 0.0, s=s), s)  # b = 0 gives f
    x = np.logspace(-3, 3, 13)
    exact = fr.exact_grid("hill_inhibition", 0.2, x=x, K=1.5, n=2.0)
    assert int(np.max(fr.ulp_distance(fr.coupling_factor("hill_inhibition", 0.2, x=x, K=1.5,
                                                         n=2.0), exact))) <= 3


def test_sides_apply_the_basal_level_on_each_side_before_the_product():
    b, sa, sb = 0.2, 0.5, 0.25
    Fa, Fb = b + (1 - b) * (1 - sa), b + (1 - b) * (1 - sb)
    kw = dict(first=sa, second=sb)
    assert fr.side_factor("first", "state_complement", b, **kw) == Fa
    assert fr.side_factor("second", "state_complement", b, **kw) == Fb
    assert fr.side_factor("both", "state_complement", b, **kw) == Fa * Fb
    assert Fa * Fb != b + (1 - b) * (1 - sa) * (1 - sb)  # not the basal of the product
    exact = fr.exact_side_factor("both", "state_complement", b, **kw)
    assert fr.ulp_distance(fr.to_float(exact), Fa * Fb) <= 4  # three float roundings
    hill = fr.exact_side_factor("both", "hill_activation", 0.1, first=3.0, second=0.5, K=1.0,
                                n=2.0)
    f1, f2 = Decimal(9) / Decimal(10), Decimal(1) / Decimal(5)
    with localcontext(prec=40):
        manual = (Decimal("0.1") + Decimal("0.9") * f1) * (Decimal("0.1") + Decimal("0.9") * f2)
    assert abs(fr.to_float(hill) - fr.to_float(manual)) <= 2 * fr.EPS  # 0.1 is not exact
    with pytest.raises(ValueError):
        fr.side_factor("left", "state_fraction", 0.0, first=0.5, second=0.5)


def test_products_in_declared_order_and_exactly_representable_cases():
    # A3's multiple case with exactly representable values: s = 0.5 and 0.25, a schedule of 0.5.
    f1 = fr.coupling_factor("state_fraction", 0.0, s=0.5)
    f2 = fr.coupling_factor("state_fraction", 0.0, s=0.25)
    assert fr.effective_availability(0.5, [f1, f2]) == 0.0625
    assert fr.element_product([]) == 1.0 and fr.effective_availability(0.7, []) == 0.7
    # A3's zero case: b = 0 and s = 0 under state_fraction.
    assert fr.effective_availability(1.0, [fr.coupling_factor("state_fraction", 0.0, s=0.0)]) == 0
    rng = np.random.default_rng(3)
    factors = rng.uniform(0.01, 1.0, 9)
    forward = fr.element_product(factors)
    sequential = 1.0
    for f in factors:
        sequential *= f
    assert forward == sequential  # left to right
    exact = fr.to_float(fr.exact_product(factors, a_sched=0.3))
    assert fr.ulp_distance(fr.effective_availability(0.3, factors), exact) <= 6


def test_ulp_distance_and_domain_refusals():
    assert fr.ulp_distance(0.0, -0.0) == 0 and fr.ulp_distance(1.0, np.nextafter(1.0, 2)) == 1
    assert fr.ulp_distance(-5e-324, 5e-324) == 2
    for bad in (dict(x=-1.0, K=1.0, n=1.0), dict(x=1.0, K=0.0, n=1.0), dict(x=1.0, K=1.0, n=0.0)):
        with pytest.raises(ValueError):
            fr.law_value("hill_activation", **bad)
    with pytest.raises(ValueError):
        fr.coupling_factor("state_fraction", 1.0, s=0.5)
    with pytest.raises(ValueError):
        fr.law_value("state_fraction", s=1.5)
    with pytest.raises(ValueError):
        fr.law_value("hill_power", x=1.0, K=1.0, n=1.0)


def test_log_space_conditioning_grows_in_the_tail():
    assert fr.log_space_condition("hill_activation", 1e-8, 1.0, 4.0) > 50
    assert fr.log_space_condition("hill_activation", 1e3, 1.0, 1.0) < 1e-2


# ------------------------------------------------------------------------ R-state


def test_frozen_input_closed_form_and_the_half_step_formula():
    s0, u, kon, koff = 0.1, 0.6, 50.0, 5.0
    star = kon * u / (kon * u + koff)
    for h in (1e-6, 1e-3, 0.02, 1.0):
        exact = rs.frozen(h, s0, u, kon, koff, exact=True)
        assert abs(rs.frozen(h, s0, u, kon, koff) - fr.to_float(exact)) <= 4 * fr.EPS
        with localcontext(prec=40):  # A.3's half-step: s + (k_on u (1 - s) - k_off s) h phi(lam h)
            x = (Decimal(kon) * Decimal(u) + Decimal(koff)) * Decimal(h)
            phi = (1 - (-x).exp()) / x
            rate = Decimal(kon) * Decimal(u) * (1 - Decimal(s0)) - Decimal(koff) * Decimal(s0)
            step = Decimal(s0) + rate * Decimal(h) * phi
        assert abs(step - exact) <= Decimal("1e-35")
    assert abs(rs.frozen(1e3, s0, u, kon, koff) - star) <= fr.EPS
    run_inputs = [rs.Input("hill_activation", rs.constant(1.3), 0.6, 3.0)]
    run = rs.integrate(run_inputs, 50.0, 5.0, 0.1, 2.0, record=(0.001, 0.5, 2.0))
    u = float(rs.input_value(run_inputs, 0.0))
    for t, (s, U) in run.at.items():
        assert abs(s - fr.to_float(rs.frozen(t, 0.1, u, 50.0, 5.0, exact=True))) <= 1e-13
        assert abs(U - u * t) <= 1e-13 * max(1.0, t)
    assert abs(run.crossing(0.5) - rs.frozen_crossing(0.5, 0.1, u, 50.0, 5.0)) <= 1e-14
    assert rs.exposure(run_inputs, 2.0) == pytest.approx(2.0 * u, rel=1e-14)


def test_quasi_steady_value_and_the_effective_half_saturation():
    kon, koff, K, n = 7.0, 3.0, 0.8, 2.5
    for c in (0.01, 0.8, 5.0):
        u = float(fr.hill_activation(c, K, n))
        Keff = rs.effective_half_saturation(K, n, kon, koff)
        hill = kon / (kon + koff) * c**n / (c**n + Keff**n)
        assert rs.quasi_steady(u, kon, koff) == pytest.approx(hill, rel=1e-14)
    assert math.isnan(rs.quasi_steady(0.5, 0.0, 0.0))


@pytest.mark.parametrize("law", fr.HILL_LAWS)
@pytest.mark.parametrize("n", [1.0, 2.5])
def test_commitment_under_clearance_against_the_closed_forms(law, n):
    c0, k, K, kon, s0 = 2.0, 0.05, 0.7, 0.3, 0.1
    inputs = [rs.Input(law, rs.clearance(c0, k), K, n)]
    record = (1.0, 10.0, 60.0)
    run = rs.integrate(inputs, kon, 0.0, s0, 60.0, record=record)
    for t in record:
        s_exact = fr.to_float(rs.clearance_commitment(t, s0, kon, c0, k, K, n, law, exact=True))
        U_exact = fr.to_float(rs.clearance_exposure(t, c0, k, K, n, law, exact=True))
        assert abs(run.at[t][0] - s_exact) <= 1e-13
        assert abs(run.at[t][1] - U_exact) <= 1e-12
        assert abs(rs.clearance_exposure(t, c0, k, K, n, law) - U_exact) <= 4 * fr.EPS * U_exact
        assert abs(rs.exposure(inputs, t) - U_exact) <= 1e-13 * U_exact
    t_star = rs.clearance_commitment_crossing(0.5, s0, kon, c0, k, K, n, law)
    assert abs(run.crossing(0.5) - t_star) <= 1e-12 * t_star
    assert fr.to_float(rs.clearance_commitment(t_star, s0, kon, c0, k, K, n, law, exact=True)) \
        == pytest.approx(0.5, abs=1e-14)
    step = run.crossing_step(0.5, 0.01)
    assert step["k"] == math.ceil(t_star / 0.01)
    assert step["margin_after"] >= 0.0 and step["margin_before"] > 0.0


def test_commitment_saturates_below_a_level_it_never_reaches():
    c0, k, K, n, kon, s0 = 0.2, 1.0, 1.0, 1.0, 0.5, 0.0
    limit = 1 - (K**n / (K**n + c0**n)) ** (kon / (n * k))  # the tending value of A.3
    assert rs.clearance_commitment(1e3, s0, kon, c0, k, K, n, "hill_activation") == \
        pytest.approx(limit, rel=1e-14)
    assert rs.clearance_commitment_crossing(limit + 0.01, s0, kon, c0, k, K, n,
                                            "hill_activation") == math.inf
    run = rs.integrate([rs.Input("hill_activation", rs.clearance(c0, k), K, n)], kon, 0.0, s0,
                       30.0)
    assert run.crossing(limit + 0.01) == math.inf


def test_retention_and_zero_rates():
    inputs = [rs.Input("hill_activation", rs.constant(0.0), 1.0, 1.0)]  # u = 0
    run = rs.integrate(inputs, 5.0, 0.2, 0.8, 10.0, record=(3.0, 10.0))
    for t in (3.0, 10.0):
        assert abs(run.at[t][0] - fr.to_float(rs.retention(t, 0.8, 0.2, exact=True))) <= 1e-14
        assert run.at[t][1] == 0.0
    frozen = rs.integrate(inputs, 0.0, 0.0, 0.3, 5.0, record=(5.0,))
    assert frozen.at[5.0] == (0.3, 0.0)


def pulse_inputs():
    """A regulator cleared first order with a production pulse on [5, 15) s (D150's turnover)."""
    reg = rs.Turnover(0.5, 2.0, ((0.0, 0.0, 0.02), (5.0, 3.0, 0.02), (15.0, 0.0, 0.02)))
    return reg, [rs.Input("hill_activation", reg, 0.6, 3.0)]


def test_turnover_closed_form_against_its_ode_and_its_decimal_form():
    from scipy.integrate import solve_ivp

    reg, _ = pulse_inputs()
    for t in (0.0, 4.0, 5.0, 9.0, 15.0, 30.0):
        assert reg.amount(t) == pytest.approx(fr.to_float(reg.exact_amount(t)), rel=4 * fr.EPS)
    sol = solve_ivp(lambda t, n: [(3.0 if 5.0 <= t < 15.0 else 0.0) - 0.02 * n[0]], (0, 30),
                    [0.5], method="DOP853", rtol=1e-13, atol=1e-15, t_eval=(30.0,),
                    first_step=1e-3, max_step=0.05)
    assert sol.y[0, -1] == pytest.approx(reg.amount(30.0), rel=1e-9)
    assert reg.concentration(30.0) == reg.amount(30.0) / 2.0
    assert reg.breakpoints() == (5.0, 15.0)


def test_general_input_with_clearance_and_production_two_ways():
    _, inputs = pulse_inputs()
    kon, koff, s0 = 2.0, 0.5, 0.05
    radau = rs.integrate(inputs, kon, koff, s0, 16.0, record=(12.0, 16.0), method="Radau",
                         rtol=1e-11, atol=(1e-15, 1e-15))
    dop = rs.integrate(inputs, kon, koff, s0, 16.0, record=(12.0, 16.0))
    quad = rs.state_quadrature(inputs, kon, koff, s0, 12.0)  # inside the pulse
    assert abs(radau.at[12.0][0] - quad) <= 2e-12 and abs(dop.at[12.0][0] - quad) <= 1e-12
    for t in (12.0, 16.0):
        assert abs(radau.at[t][0] - dop.at[t][0]) <= 2e-12
        assert abs(radau.at[t][1] - rs.exposure(inputs, t)) <= 1e-11
    assert abs(radau.crossing(0.5) - dop.crossing(0.5)) <= 1e-11


def test_fast_arm_tracks_the_quasi_steady_value():
    reg = rs.Turnover(0.5, 2.0, ((0.0, 0.0, 0.5), (0.5, 3.0, 0.5), (1.5, 0.0, 0.5)))
    inputs = [rs.Input("hill_activation", reg, 0.6, 3.0)]
    kon, koff = 900.0, 100.0  # dt (k_on + k_off) = 1 at dt = 1 ms
    run = rs.integrate(inputs, kon, koff, 0.05, 1.2, record=(1.0, 1.2))
    radau = rs.integrate(inputs, kon, koff, 0.05, 1.2, record=(1.0, 1.2), method="Radau",
                         rtol=1e-10, atol=(1e-14, 1e-14))
    for t in (1.0, 1.2):
        star = float(rs.quasi_steady(rs.input_value(inputs, t), kon, koff))
        assert abs(run.at[t][0] - star) < 2e-3  # O(1/lambda) lag
        assert abs(run.at[t][0] - radau.at[t][0]) <= 1e-10


def test_state_refusals():
    with pytest.raises(ValueError):
        rs.Turnover(1.0, 1.0, ((1.0, 0.0, 0.0),))
    with pytest.raises(ValueError):
        rs.Turnover(1.0, 1.0, ((0.0, -1.0, 0.0),))
    with pytest.raises(ValueError):
        rs.Input("state_fraction", rs.constant(1.0), 1.0, 1.0)
    with pytest.raises(ValueError):
        rs.integrate([], 1.0, 1.0, 0.5, 1.0)
    with pytest.raises(ValueError):
        rs.frozen(1.0, 1.5, 0.5, 1.0, 1.0)


# ------------------------------------------------------------------------ R-cell, R-feedback


def r_cell(coupling, *, regulator=None, initial_V=-0.05, P=3e-9, schedule=((0.0, 1.0),),
           **cell):
    return rc.World(
        CONST, SP, Z, BATH,
        cells={"c0": rc.Cell(VOL, CYT_A, initial_V=initial_V, **cell)},
        patches={"c0.m": rc.Patch("c0", AREA, CAP, LEAK)},
        populations={"kleak": rc.Population("c0.m", P, KLEAK, schedule=schedule)},
        regulators={"X": rc.Regulator({"c0": regulator or rs.constant(1.0, VOL)})},
        couplings={"k_reg": coupling} if coupling else {},
    )


def r_feedback(kon=5.0, koff=0.5, *, s0=0.1, law="state_complement", b=0.2, K=20.0, n=2.0,
               contact_P=(2e-6, 3e-6, 4e-6), leak_a=LEAK, leak_b=LEAK, side="both", theta=0.5):
    return rc.World(
        CONST, SP, Z, BATH,
        cells={"a": rc.Cell(VOL, CYT_A, initial_V=-0.06),
               "b": rc.Cell(VOL, CYT_B, initial_V=-0.04)},
        patches={"a.m": rc.Patch("a", AREA, CAP, leak_a), "b.m": rc.Patch("b", AREA, CAP, leak_b)},
        contacts={"e": rc.Contact(("a", "b"), 1e-10, contact_P)},
        states={"s1": rc.State(("a", "b"), (rc.Input("hill_activation", "Na", K, n),), kon, koff,
                               initial=s0, crossing_level=theta)},
        couplings={"j": rc.Coupling("e", law, "s1", basal=b, side=side)},
    )


@pytest.fixture(scope="module")
def feedback():
    """R-feedback's default world over 1 s: the coupled run every feedback test reads."""
    return rc.simulate(r_feedback(), 1.0, record=(0.0, 0.5, 1.0))


NO_NA = (0.0, 2e-9, 5e-10)


@pytest.fixture(scope="module")
def held():
    """The same world with every sodium route closed: the states see constant inputs."""
    world = r_feedback(leak_a=NO_NA, leak_b=NO_NA, contact_P=(0.0, 3e-6, 4e-6))
    return rc.simulate(world, 1.0, record=(0.3, 1.0))


def test_r_cell_at_constant_availability_equals_r_tissue():
    world = r_cell(rc.Coupling("kleak", "hill_activation", "X", basal=0.0, K_mM=1.0, n=1.0))
    run = rc.simulate(world, 2.0, record=(0.01, 1.0, 2.0))
    assert run.at[1.0]["elements"]["kleak"]["a_eff"] == 0.5  # c = K
    from validation.division import cleft_tissue_reference as rt

    perm = tuple(LEAK[k] + 3e-9 * KLEAK[k] * 0.5 for k in range(3))
    tw = rt.World(temperature_K=300.0, bath_mM=BATH,
                  cells={"c0": rt.CellSpec(volume_pL=VOL, mM=CYT_A, initial_V=-0.05)},
                  patches={"c0.m": rt.PatchSpec("c0", "bath", perm, area_m2=AREA,
                                                capacitance_F=CAP)})
    ref = rt.simulate_static(tw, 2.0, record=(0.01, 1.0, 2.0), atol=SMALL)
    for t in (0.01, 1.0, 2.0):
        assert abs(run.at[t]["V"]["c0"] - ref.at[t]["V"]["c0"]) <= 1e-13
        for x, y in zip(run.at[t]["amounts_fmol"]["c0"], ref.at[t]["cells"]["c0"]["amounts_fmol"],
                        strict=True):
            assert abs(x - y) <= 1e-10


def test_r_feedback_with_frozen_states_equals_r_tissue_with_the_product_gate():
    world = r_feedback(kon=0.0, koff=0.0, s0=0.25)
    run = rc.simulate(world, 0.8, record=(0.4, 0.8))
    gate = (0.2 + 0.8 * 0.75) ** 2
    assert run.at[0.8]["elements"]["e"]["a_eff"] == gate
    from validation.division import cleft_tissue_reference as rt

    tw = rt.World(
        temperature_K=300.0, bath_mM=BATH,
        cells={"a": rt.CellSpec(volume_pL=VOL, mM=CYT_A, initial_V=-0.06),
               "b": rt.CellSpec(volume_pL=VOL, mM=CYT_B, initial_V=-0.04)},
        patches={"a.m": rt.PatchSpec("a", "bath", LEAK, area_m2=AREA, capacitance_F=CAP),
                 "b.m": rt.PatchSpec("b", "bath", LEAK, area_m2=AREA, capacitance_F=CAP)},
        contacts={"e": rt.ContactSpec(("a", "b"), (2e-6, 3e-6, 4e-6), area_m2=1e-10, gate=gate)})
    ref = rt.simulate_static(tw, 0.8, record=(0.4, 0.8), atol=SMALL)
    for t in (0.4, 0.8):
        for c in "ab":
            assert abs(run.at[t]["V"][c] - ref.at[t]["V"][c]) <= 1e-13
            for x, y in zip(run.at[t]["amounts_fmol"][c], ref.at[t]["cells"][c]["amounts_fmol"],
                            strict=True):
                assert abs(x - y) <= 1e-10
        assert run.at[t]["elements"]["e"]["current_A"] == pytest.approx(
            ref.at[t]["junctions"]["e"]["current_A"], rel=1e-8, abs=1e-22)


def test_four_species_with_an_impermeant_anion_equal_r_tissue():
    """The engine's worlds carry Na, K, M (permeant) and P (impermeant), §7.1 item 12: P, the last
    charged species, is the follower recovered from the charge, and it must stay constant."""
    from validation.division import cleft_tissue_reference as rt

    sp, z, bath = ("Na", "K", "M", "P"), (1, 1, -1, -1), (145.0, 5.0, 140.0, 10.0)
    cyt, leak = (6.0, 136.0, 7.0, 135.0), (5e-11, 1.3e-10, 1.3e-10, 0.0)
    world = rc.World(CONST, sp, z, bath, cells={"c": rc.Cell(0.75, cyt, initial_V=-0.08)},
                     patches={"c.m": rc.Patch("c", 3.26e-10, 1.63e-11, leak)})
    run = rc.simulate(world, 0.5, record=(0.5,))
    tw = rt.World(temperature_K=300.0, bath_mM=bath, species=sp, z=z,
                  cells={"c": rt.CellSpec(volume_pL=0.75, mM=cyt, initial_V=-0.08)},
                  patches={"c.m": rt.PatchSpec("c", "bath", leak, area_m2=3.26e-10,
                                               capacitance_F=1.63e-11)})
    ref = rt.simulate_static(tw, 0.5, record=(0.5,), atol=SMALL)
    assert abs(run.at[0.5]["V"]["c"] - ref.at[0.5]["V"]["c"]) <= 1e-12
    for x, y in zip(run.at[0.5]["amounts_fmol"]["c"], ref.at[0.5]["cells"]["c"]["amounts_fmol"],
                    strict=True):
        assert abs(x - y) <= 1e-10
    assert run.at[0.5]["amounts_fmol"]["c"][3] == pytest.approx(135.0 * 0.75, abs=1e-10)


def test_zero_availability_uncouples_the_cells():
    world = r_feedback(kon=0.0, koff=0.0, s0=0.0, law="state_fraction", b=0.0)
    run = rc.simulate(world, 1.0, record=(1.0,))
    assert run.at[1.0]["elements"]["e"]["a_eff"] == 0.0
    assert run.at[1.0]["elements"]["e"]["current_A"] == 0.0
    alone = rc.World(CONST, SP, Z, BATH, cells={"a": rc.Cell(VOL, CYT_A, initial_V=-0.06)},
                     patches={"a.m": rc.Patch("a", AREA, CAP, LEAK)})
    single = rc.simulate(alone, 1.0, record=(1.0,))
    assert abs(run.at[1.0]["V"]["a"] - single.at[1.0]["V"]["a"]) <= 1e-12


def test_held_sodium_gives_the_frozen_closed_form(held):
    run = held
    for cell, c in (("a", CYT_A[0]), ("b", CYT_B[0])):
        u = float(fr.hill_activation(c, 20.0, 2.0))
        for t in (0.3, 1.0):
            assert run.at[t]["mM"][cell][0] == pytest.approx(c, rel=1e-13)
            exact = fr.to_float(rs.frozen(t, 0.1, u, 5.0, 0.5, exact=True))
            assert abs(run.at[t]["s"][("s1", cell)] - exact) <= 1e-11
            assert abs(run.at[t]["U"][("s1", cell)] - u * t) <= 1e-11
        assert run.crossings[("s1", cell)] == pytest.approx(rs.frozen_crossing(0.5, 0.1, u, 5.0,
                                                                               0.5), rel=1e-9)


def test_feedback_conserves_amounts_and_the_recorded_factor_is_r_fac(feedback):
    run = feedback
    first, last = run.at[0.0], run.at[1.0]
    for k in range(3):
        total = sum(last["amounts_fmol"][c][k] - first["amounts_fmol"][c][k] for c in "ab")
        assert abs(total - last["exchanged_fmol"][k]) <= 1e-9
    for t in (0.5, 1.0):
        r = run.at[t]
        F = fr.side_factor("both", "state_complement", 0.2, first=r["s"][("s1", "a")],
                           second=r["s"][("s1", "b")])
        assert r["routes"][("j", "e")]["F"] == F == r["elements"]["e"]["a_eff"]
        for c in "ab":
            u = fr.hill_activation(r["mM"][c][0], 20.0, 2.0)
            assert r["u"][("s1", c)] == pytest.approx(u, rel=1e-15)
            q = r["charge_C"][c] / (1e-15 * F_SI)
            content = sum(zk * n for zk, n in zip(Z, r["amounts_fmol"][c], strict=True))
            assert q == pytest.approx(content + r["background_fmol"][c], abs=1e-12)


def test_the_loop_is_live_and_a_perturbed_K_moves_it_beyond_the_floor(feedback, held):
    T, base = 1.0, feedback
    # An upper estimate of the error at rtol 1e-10: the distance to a run 100 times looser.
    coarse = rc.simulate(r_feedback(), T, record=(T,), rtol=1e-8)
    floor = max(abs(base.at[T]["s"][k] - coarse.at[T]["s"][k]) for k in base.at[T]["s"])
    assert floor < 1e-8
    # One way: the held world, whose states see sodium at its initial values.
    perturbed = rc.simulate(r_feedback(K=20.0 * 1.01), T, record=(T,))  # §4.2's control
    for other in (held, perturbed):
        moved = max(abs(base.at[T]["s"][k] - other.at[T]["s"][k]) for k in base.at[T]["s"])
        assert moved > 1e3 * max(floor, 1e-15)
        assert abs(base.at[T]["V"]["a"] - other.at[T]["V"]["a"]) > 1e-9


def test_fast_states_approach_the_instantaneous_hill_limit():
    # 1 - s* is a Hill inhibition with K_eff and amplitude k_on/(k_on + k_off), so a fast
    # state_complement coupling tends to a hill_inhibition coupling of Na with basal
    # b' = 1 - (1 - b) k_on/(k_on + k_off): an instantaneous ion factor, a limit the engine
    # refuses (ruling 1).
    kon, koff, b, K, n = 9e3, 1e3, 0.2, 20.0, 2.0
    star = {c: float(rs.quasi_steady(fr.hill_activation(x[0], K, n), kon, koff))
            for c, x in (("a", CYT_A), ("b", CYT_B))}
    fast = rc.simulate(r_feedback(kon, koff, b=b, s0=star), 0.5, record=(0.5,))
    amp = kon / (kon + koff)
    hill = r_feedback(kon, koff)
    couplings = {"j": rc.Coupling("e", "hill_inhibition", "Na", basal=1 - (1 - b) * amp,
                                  K_mM=rs.effective_half_saturation(K, n, kon, koff), n=n,
                                  side="both")}
    limit = rc.simulate(rc.World(**{**hill.__dict__, "couplings": couplings}), 0.5,
                        record=(0.5,))
    da = abs(fast.at[0.5]["elements"]["e"]["a_eff"] - limit.at[0.5]["elements"]["e"]["a_eff"])
    assert da < 1e-4
    assert abs(fast.at[0.5]["mM"]["a"][0] - limit.at[0.5]["mM"]["a"][0]) < 1e-4


def test_r_cell_follows_a_turnover_regulator_and_its_voltage_tracks_zero_current():
    from scipy.optimize import brentq

    from validation.division import cleft_egg_reference as rfull

    reg = rs.Turnover(0.2 * VOL, VOL, ((0.0, 0.0, 0.5), (1.0, 4.0, 0.5), (3.0, 0.0, 0.5)))
    world = r_cell(rc.Coupling("kleak", "hill_inhibition", "X", basal=0.1, K_mM=1.0, n=2.0),
                   regulator=reg, P=2e-8)
    run = rc.simulate(world, 3.0, record=(0.5, 2.0, 3.0))
    for t in (0.5, 2.0, 3.0):
        r = run.at[t]
        c = reg.concentration(t)
        assert r["regulators_mM"][("X", "c0")] == c
        F = fr.coupling_factor("hill_inhibition", 0.1, x=c, K=1.0, n=2.0)
        assert r["routes"][("k_reg", "kleak")]["F"] == pytest.approx(F, rel=1e-15)
        # The membrane relaxes in about C/G, far faster than a(t): V stays near zero current
        # with the population's K permeability at 2e-8 F (per unit area).
        perm = tuple(LEAK[k] + 2e-8 * F * KLEAK[k] for k in range(3))
        conc = r["mM"]["c0"]

        def current(v, perm=perm, conc=conc):
            x = F_SI * v / CONST.rt
            return sum(zk * rfull.ghk_flux(perm[k] * AREA, zk, x, conc[k], BATH[k])
                       for k, zk in enumerate(Z))

        assert abs(r["V"]["c0"] - brentq(current, -0.2, 0.2, xtol=1e-15)) < 5e-4  # a lag C/G
    early, mid = (run.at[t]["routes"][("k_reg", "kleak")]["F"] for t in (0.5, 2.0))
    assert mid < early  # the pulse raises X, which inhibits the K route
    assert run.at[2.0]["V"]["c0"] - run.at[0.5]["V"]["c0"] > 5e-3  # and depolarises the cell


def test_sides_switches_products_and_a_state_sourced_population():
    """The advertised paths beyond side "both": a first and a second side, two couplings on one
    element in declared order under a schedule of 0.5, a switch at 2 ms with both sides of it,
    and a population gated by a state, each against R-fac at the recorded state."""
    world = rc.World(
        CONST, SP, Z, BATH,
        cells={"a": rc.Cell(VOL, CYT_A, initial_V=-0.06),
               "b": rc.Cell(VOL, CYT_B, initial_V=-0.04)},
        patches={"a.m": rc.Patch("a", AREA, CAP, LEAK), "b.m": rc.Patch("b", AREA, CAP, LEAK)},
        populations={"kleak_a": rc.Population("a.m", 3e-9, KLEAK)},
        contacts={"e": rc.Contact(("a", "b"), 1e-10, (2e-6, 3e-6, 4e-6), schedule=((0.0, 0.5),))},
        regulators={"X": rc.Regulator({"b": rs.constant(0.8, VOL)})},
        states={"s1": rc.State(("a", "b"), (rc.Input("hill_activation", "Na", 20.0, 2.0),), 50.0,
                               5.0, initial={"a": 0.1, "b": 0.7})},
        couplings={
            "c1": rc.Coupling("e", "state_fraction", "s1", basal=0.1, side="first"),
            "c2": rc.Coupling("e", "hill_activation", "X", basal=0.3, K_mM=1.0, n=2.0,
                              side="second", enabled=((0.0, 1), (0.002, 0))),
            "c3": rc.Coupling("kleak_a", "state_complement", "s1", basal=0.2),
        },
    )
    run = rc.simulate(world, 0.004, record=(0.001, 0.002, 0.003))
    on = float(fr.coupling_factor("hill_activation", 0.3, x=0.8, K=1.0, n=2.0))
    assert run.slots == [("s1", "a"), ("s1", "b")]  # the engine's regulatory_slot order
    for t, before, after in ((0.001, on, on), (0.002, on, 1.0), (0.003, 1.0, 1.0)):
        r = run.at[t]
        sa, sb = r["s"][("s1", "a")], r["s"][("s1", "b")]
        F1 = fr.side_factor("first", "state_fraction", 0.1, first=sa, second=sb)
        assert r["routes"][("c1", "e")]["F"] == r["routes"][("c1", "e")]["F_left"] == F1
        assert F1 != fr.side_factor("second", "state_fraction", 0.1, first=sa, second=sb)
        c2 = r["routes"][("c2", "e")]
        assert c2["F_left"] == pytest.approx(before, rel=1e-15)
        assert c2["F_right"] == pytest.approx(after, rel=1e-15)
        assert c2["F"] == c2["F_left"]  # as built: a row at a switch time shows the old switch
        e = r["elements"]["e"]
        assert e["G_right"] == F1 * c2["F_right"] and e["G_left"] == F1 * c2["F_left"]
        assert e["a_eff"] == 0.5 * e["G"] and e["a_sched"] == e["a_sched_left"] == 0.5
        if t == 0.002:  # the same state on both sides: the flux scales with a_eff
            assert e["current_A_left"] == pytest.approx(on * e["current_A_right"], rel=1e-12)
        F3 = fr.coupling_factor("state_complement", 0.2, s=sa)
        assert r["routes"][("c3", "kleak_a")]["F"] == F3 == r["elements"]["kleak_a"]["a_eff"]
    tight = rc.simulate(world, 0.004, record=(0.001, 0.002, 0.003), rtol=1e-12,
                        atol={k: v / 1000 for k, v in rc.ATOL.items()})
    floor = rc.compare(run, tight, (0.001, 0.002, 0.003))
    assert floor["s"] < 1e-11 and floor["amounts"] < 1e-9 and floor["V"] < 1e-12


def test_records_at_a_schedule_change_give_both_sides():
    world = r_cell(None, schedule=((0.0, 1.0), (1.0, 0.25)))
    run = rc.simulate(world, 2.0, record=(1.0, 2.0))
    r = run.at[1.0]["elements"]["kleak"]
    assert (r["a_sched_left"], r["a_sched_right"]) == (1.0, 0.25)
    assert r["a_sched"] == r["a_sched_right"]  # as built: schedules from t on (§1.9)
    assert r["current_A_left"] == pytest.approx(4 * r["current_A"], rel=1e-12)
    late = run.at[2.0]["elements"]["kleak"]
    assert late["a_sched_left"] == late["a_sched"] == late["a_sched_right"] == 0.25


def test_initial_state_rules():
    coupling = rc.Coupling("kleak", "hill_activation", "X", basal=0.0, K_mM=1.0, n=1.0)
    zc = rc.simulate(r_cell(coupling, initial_V=math.nan), 1e-3, record=(0.0,))
    v0 = zc.initial["c0"]["V"]
    assert abs(zc.model.bath_current(0, v0, [1.0], [True], [])) < 1e-22
    given = rc.simulate(r_cell(coupling, initial_V=-0.07), 1e-3, record=(0.0,))
    assert given.at[0.0]["V"]["c0"] == pytest.approx(-0.07, abs=1e-15)
    X = given.initial["c0"]["background_fmol"]
    back = rc.simulate(r_cell(coupling, initial_V=math.nan, background_fmol=X), 1e-3,
                       record=(0.0,))
    assert back.at[0.0]["V"]["c0"] == pytest.approx(-0.07, abs=1e-11)


def test_world_refusals():
    good = r_feedback()
    bad = [
        {"couplings": {"j": rc.Coupling("e", "state_complement", "s1", basal=0.2)}},  # no side
        {"couplings": {"j": rc.Coupling("e", "state_complement", "nope", side="both")}},
        {"couplings": {"j": rc.Coupling("e", "hill_activation", "Na", side="both")}},  # no K, n
        {"couplings": {"j": rc.Coupling("e", "state_complement", "s1", basal=1.0,
                                        side="both")}},
        {"states": {"s1": rc.State(("a",), (rc.Input("hill_activation", "Na", 20.0, 2.0),), 1.0,
                                   1.0)}},  # the coupling reads b, where the state is undeclared
        {"cells": {"a": rc.Cell(VOL, CYT_A, initial_V=-0.06, background_fmol=-1.0),
                   "b": rc.Cell(VOL, CYT_B)}},
        {"patches": {"e": rc.Patch("a", AREA, CAP, LEAK),  # a patch named like the contact
                     "b.m": rc.Patch("b", AREA, CAP, LEAK)}},
    ]
    for change in bad:
        with pytest.raises(ValueError):
            rc.check_world(rc.World(**{**good.__dict__, **change}))
