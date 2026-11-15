"""Self-tests of FR-4's references (validation/compartment_ph/): the rapid-buffer closure
(R-closure, Appendix A) and the full protonation kinetics (R-kinetic, Appendix A.2).

They check the closure's algebra, the kinetic system at equilibrium, the convergence of R-kinetic
to R-closure as k_on grows (inside the 1e-3 pH budget at k_on >= 1e5 mM^-1 s^-1, outside it at
1e-3), the lag's first-order term at its peak, the reaction heat vanishing as 1/k_on, the energy
identity dG_stored + Q = W, charge and material, the pump law, and the negative control (P_K = 0)
stalling acidification by far more than the budget. The first tests check
independence: nothing under validation/compartment_ph/ imports `cells` or validation.tissue.
"""

import ast
import math
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from validation.compartment_ph import ph_reference as ph

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "compartment_ph"
C0 = 1000.0
BUDGET = 1e-3  # pH (§4.2)


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


def test_references_import_nothing_from_cells_or_the_engine():
    files = sorted(REFERENCES.glob("*.py"))
    assert files
    for path in files:
        for name, names in _imports(path):
            assert name != "<dynamic import>" and not name.startswith("."), (path.name, name)
            assert name.split(".")[0] not in {"cells", "jax", "jaxlib"}, (path.name, name)
            if name.startswith("validation") and not name.startswith("validation.compartment_ph"):
                assert name == "validation.coupling" and names == ("piecewise_ode",), name


def test_references_load_no_cells_or_tissue_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.compartment_ph.{m}\n" for m in modules)
        + "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')\n"
        + "  or m.startswith(('validation.tissue', 'validation.division')))\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0, out.stdout + out.stderr


# ------------------------------------------------------------------------ the closure


def test_the_closure_solves_its_equation_and_the_registry_gives_the_pK():
    b = ph.Buffer(50.0, -1, -7.2 * ph.LN10)
    assert -math.log10(b.K_mM(C0) / C0) == pytest.approx(7.2, rel=1e-15)
    K = b.K_mM(C0)
    for Heq in (1e-6, 1e-3, 0.5, 25.0, 60.0, 1e3):
        h = ph.free_proton(Heq, [(50.0, K)], C0)
        assert h + 50.0 * h / (h + K) == pytest.approx(Heq, rel=1e-14)
        # Two buffers by Brent's method, one of them empty-equivalent, against the closed form.
        h2 = ph.free_proton(Heq, [(50.0, K), (1e-300, 1.0)], C0)
        assert h2 == pytest.approx(h, rel=1e-12)
    pairs = [(50.0, K), (40.0, 1e-3)]
    h = ph.free_proton(30.0, pairs, C0)
    assert h + sum(B * h / (h + k) for B, k in pairs) == pytest.approx(30.0, rel=1e-13)
    # beta = -dHeq/dpH, against a central difference of the closure's inverse.
    d = 1e-6
    heq = [hh + sum(B * hh / (hh + k) for B, k in pairs) for hh in (h * 10 ** d, h * 10 ** -d)]
    assert ph.buffer_capacity(h, pairs) == pytest.approx((heq[0] - heq[1]) / (2 * d), rel=1e-6)
    with pytest.raises(ValueError):
        ph.free_proton(0.0, pairs, C0)


def test_the_kinetic_system_at_its_equilibrium_start_stays_without_transport():
    w = replace(ph.acceptance_world(), pump=None, proton_permeability_m_s=0.0,
                permeability_m_s={})
    run = ph.integrate(w, 5.0, record=(5.0,), kinetic=True)
    r = run.at[5.0]
    assert r["pH_L"] == pytest.approx(7.2, abs=1e-12) and r["pH_c"] == pytest.approx(7.2,
                                                                                    abs=1e-12)
    assert abs(r["heat_pJ"]) <= 1e-12 and r["work_pJ"] == 0.0


# ------------------------------------------------------------------------ the acceptance world


@pytest.fixture(scope="module")
def short_runs():
    """§13.1's world over 6 s, densely recorded early: R-closure and R-kinetic at three k_on and
    the outside case (the lumen's k_on = 1e-3 mM^-1 s^-1)."""
    T = 6.0
    rec = tuple(sorted({*np.geomspace(0.01, T, 25), T}))
    w = ph.acceptance_world()
    out = dict(T=T, rec=rec, closure=ph.integrate(w, T, record=rec))
    for kon in (1e3, 1e5, 1e7):
        out[kon] = ph.integrate(w, T, record=rec, kinetic=True, k_on=(kon, kon))
    out["outside"] = ph.integrate(w, T, record=rec, kinetic=True, k_on=(None, 1e-3))
    return out


def test_r_kinetic_converges_to_the_closure_as_k_on_grows(short_runs):
    rec, clo = short_runs["rec"], short_runs["closure"]
    err = {kon: max(abs(short_runs[kon].at[t]["pH_L"] - clo.at[t]["pH_L"]) for t in rec)
           for kon in (1e3, 1e5, 1e7)}
    assert err[1e3] > 30 * err[1e5] > 30 * 30 * err[1e7] > 0  # first order in 1/k_on (100x)
    assert err[1e5] < BUDGET and err[1e7] < BUDGET  # inside the envelope: within the budget
    outside = max(abs(short_runs["outside"].at[t]["pH_L"] - clo.at[t]["pH_L"]) for t in rec)
    assert outside > 100 * BUDGET  # outside the envelope: the comparison must fail
    # The envelope at the declared k_on (1e7) holds by orders of magnitude in the closure run.
    assert min(min(clo.at[t]["envelope_ratio"]) for t in rec) > 1e6
    # At its peak the lag is the closure's first-order (quasi-steady) correction, read from the
    # kinetic run's own state: dpH = (rho/lambda) (beta/ln 10 - h)/(h ln 10) with one buffer per
    # node (Keener and Sneyd 2009, ch. 7, the rapid-buffer expansion).
    for kon, tol in ((1e3, 5e-2), (1e5, 1e-2), (1e7, 1e-2)):
        run = short_runs[kon]
        t = max(rec, key=lambda s, run=run: abs(run.at[s]["pH_L"] - clo.at[s]["pH_L"]))
        r = run.at[t]
        lag = (r["buffer_capacity"][1] / ph.LN10 - r["h_L"]) / (r["h_L"] * ph.LN10)
        assert err[kon] == pytest.approx(lag / r["envelope_ratio"][1], rel=tol)
    # §4.2's envelope (lambda >= 1e3 rho) admits k_on = 1e3 here by more than 1e3, yet its lag
    # exceeds the budget: the bound-to-free factor above is about 1.5e4 at the lumen's start.
    assert min(short_runs[1e3].at[t]["envelope_ratio"][1] for t in rec) > 1e3 * 1e3
    assert err[1e3] > 10 * BUDGET
    # A.2: the reaction's heat is never negative and vanishes in the limit, as 1/k_on.
    T = short_runs["T"]
    heat = {kon: short_runs[kon].at[T]["reaction_heat_pJ"] for kon in (1e3, 1e5, 1e7)}
    assert heat[1e3] > 30 * heat[1e5] > 30 * 30 * heat[1e7] > 0
    assert clo.at[T]["reaction_heat_pJ"] == 0.0


def test_the_energy_identity_charge_and_material(short_runs):
    T = short_runs["T"]
    for run in (short_runs["closure"], short_runs[1e7], short_runs["outside"]):
        r = run.at[T]
        assert r["work_pJ"] > 0 and r["heat_pJ"] > 0
        assert abs(r["energy_residual_pJ"]) <= 1e-10 * r["work_pJ"]
        assert abs(r["phi_c"]) <= 1e-9  # the owner stays at the bath's potential
        m = run.model
        heq0 = sum(m.Heq0)
        assert r["Heq_c"] + r["Heq_L"] == pytest.approx(heq0, rel=1e-12)
        k0 = m.ions0[0]["K"] + m.ions0[1]["K"]
        assert r["ions_c"]["K"] + r["ions_L"]["K"] == pytest.approx(k0, rel=1e-13)
        # K+ leaves the lumen in step with the pumped charge (the counterion); V_b stays small.
        assert r["J_ions"]["K"] < 0 and abs(r["Vb"]) < 0.02


def test_the_negative_control_stalls_far_beyond_the_budget():
    T = 20.0
    with_k = ph.integrate(ph.acceptance_world(), T, record=(T,))
    without = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=(T,))
    stall = 7.2 - without.at[T]["pH_L"]
    assert 0.03 < stall < 0.09  # §13.1: about 0.06 pH units
    assert without.at[T]["Vb"] == pytest.approx(-0.26, abs=0.01)  # at the pump's static head
    assert with_k.at[T]["pH_L"] < without.at[T]["pH_L"] - 100 * BUDGET
    kin = ph.integrate(ph.acceptance_world(P_K=0.0), T, record=(T,), kinetic=True)
    assert abs(kin.at[T]["pH_L"] - without.at[T]["pH_L"]) < BUDGET


def test_the_pump_law_vanishes_at_static_head_and_reverses():
    w = ph.acceptance_world()
    m = ph._Model(w, kinetic=False)
    sp = m.speciation(m.y0)
    rt, F = m.rt, m.F
    dG_atp = w.pump.dG0_prime_J_per_mol + rt * math.log(0.3 * 3.0 / (3.0 * C0))
    assert dG_atp == pytest.approx(-51.4e3, rel=2e-3)  # §13.1: about -51.4 kJ/mol
    Vhead = dG_atp / (w.pump.n * F)  # dG_cyc = 0 at equal pH
    for Vb, sign in ((Vhead, 0), (Vhead * 0.9, 1), (Vhead * 1.1, -1)):
        tr = m.transport(sp, Vb)
        if sign == 0:
            assert abs(tr["J_cyc"]) <= 1e-12 * w.pump.capacity_fmol_per_s
        else:
            assert np.sign(tr["J_cyc"]) == sign
        assert -tr["dG_cyc"] * tr["J_cyc"] >= 0.0  # the pump's heat is never negative
    assert ph.psi(0.0) == 1.0 and ph.psi(1e-7) == pytest.approx(1 + 5e-8, rel=1e-15)
