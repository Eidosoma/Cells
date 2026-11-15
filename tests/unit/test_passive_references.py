"""Self-tests of the passive permeation law's closed-pair reference (validation/passive/).

The closed form is checked against its 50-digit form across a start-ratio sweep up to a trace
start, against an independent integration (amounts and the integrated dissipation), against
R-tissue's static entry point on the coordinator's world (two cells joined by a junction, a z = 0
species permeant only there), and for the closed test's properties: conserved material, zero flux
at equal chemical potential, reversal with the driving force, the free-energy decrease dissipated
as heat, and no work. The first tests check independence: nothing under validation/passive/
imports `cells` or validation.tissue.
"""

import ast
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from validation.passive import passive_reference as pr

ROOT = Path(__file__).resolve().parents[2]
REFERENCES = ROOT / "validation" / "passive"
RT = 2.5775  # pJ/fmol, an input (the reference never holds it)
EPS = float(np.finfo(float).eps)
V_A, V_B, PA = 2.0, 0.75, 3e-18  # pL, pL, m^3/s


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


def test_references_import_nothing_from_cells_or_the_engine_fixtures():
    files = sorted(REFERENCES.glob("*.py"))
    assert files
    for path in files:
        for name, names in _imports(path):
            assert name != "<dynamic import>" and not name.startswith("."), (path.name, name)
            assert name.split(".")[0] not in {"cells", "jax", "jaxlib"}, (path.name, name)
            if name.startswith("validation") and not name.startswith("validation.passive"):
                allowed = {("validation.coupling", ("piecewise_ode",))}
                if path.name == "passive_crosschecks.py":  # the evidence driver's cross-check
                    allowed.add(("validation.division", ("cleft_tissue_reference",)))
                assert (name, names) in allowed, (path.name, name, names)


def test_references_load_no_cells_or_tissue_module_in_a_fresh_process():
    modules = sorted(p.stem for p in REFERENCES.glob("*.py"))
    code = (
        f"import sys; sys.path.insert(0, {str(ROOT)!r})\n"
        + "".join(f"import validation.passive.{m}\n" for m in modules)
        + "bad = sorted(m for m in sys.modules if m.split('.')[0] in ('cells', 'jax', 'jaxlib')\n"
        + "  or m.startswith(('validation.tissue', 'validation.division')))\n"
        + "print(bad); sys.exit(1 if bad else 0)\n"
    )
    out = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True,
                         timeout=120, check=False)
    assert out.returncode == 0, out.stdout + out.stderr


@pytest.mark.parametrize("ratio", [1e2, 1e6, 1e12])
def test_closed_form_against_fifty_digits_and_the_integration_up_to_a_trace_start(ratio):
    n_a0, n_b0 = 1.0 * V_A, 1.0 / ratio * V_B
    k = pr.rate_constant(PA, V_A, V_B)
    times = (0.01 / k, 1.0 / k, 3.0 / k)
    world = pr.World(RT, {"a": pr.Compartment(V_A, n_a0), "b": pr.Compartment(V_B, n_b0)},
                     {"j": pr.Route("a", "b", PA)})
    run = pr.integrate(world, times[-1], record=times, method="DOP853", rtol=1e-13)
    for t in times:
        cf = pr.closed_pair(t, n_a0, n_b0, V_A, V_B, PA, rt=RT)
        ex = pr.exact_closed_pair(t, n_a0, n_b0, V_A, V_B, PA, RT)
        for side in ("a", "b"):
            exact = float(ex[f"n_{side}"])
            assert abs(cf[f"n_{side}"] - exact) <= 4 * EPS * exact  # the trace keeps its digits
            assert abs(run.at[t]["n_fmol"][side] - exact) <= 1e-12 * exact
        heat = float(ex["heat"])
        assert heat > 0.0
        assert abs(cf["heat_pJ"] - heat) <= 64 * EPS * heat
        # The integrated dissipation is independent evidence for H here (no term cancels).
        assert abs(run.at[t]["heat_pJ"] - heat) <= 1e-12 * heat
        assert abs(run.at[t]["material_residual_fmol"]) <= 1e-13 * (n_a0 + n_b0)


def test_the_closed_test_properties():
    # Zero flux at equal chemical potential, with unequal volumes (n/V equal exactly in floats).
    eq = pr.closed_pair(50.0, 0.5, 1.0, 1.0, 2.0, PA, rt=RT)
    assert eq["flux_fmol_per_s"] == 0.0 and eq["n_a"] == 0.5 and eq["n_b"] == 1.0
    assert eq["heat_pJ"] == 0.0 and eq["work_pJ"] == 0.0
    # Reversal with the driving force, and antisymmetry under swapping the compartments.
    fwd = pr.closed_pair(10.0, 2.0, 0.3, V_A, V_B, PA, rt=RT)
    rev = pr.closed_pair(10.0, 0.3, 2.0, V_B, V_A, PA, rt=RT)
    assert fwd["flux_fmol_per_s"] > 0 > rev["flux_fmol_per_s"]
    assert fwd["flux_fmol_per_s"] == -rev["flux_fmol_per_s"]
    assert fwd["n_a"] == rev["n_b"] and fwd["heat_pJ"] == rev["heat_pJ"]
    # Material conserved; the heat non-negative, monotone and equal to the free-energy decrease.
    k = pr.rate_constant(PA, V_A, V_B)
    heats = [pr.closed_pair(t, 2.0, 0.3, V_A, V_B, PA, rt=RT)["heat_pJ"]
             for t in np.linspace(0, 5 / k, 21)]
    assert heats[0] == 0.0 and all(b >= a for a, b in zip(heats, heats[1:], strict=False))
    for t in (1.0, 1 / k, 4 / k):
        cf = pr.closed_pair(t, 2.0, 0.3, V_A, V_B, PA, rt=RT)
        assert cf["n_a"] + cf["n_b"] == pytest.approx(2.3, rel=4 * EPS)
        dG = (pr.free_energy(cf["n_a"], V_A, RT) + pr.free_energy(cf["n_b"], V_B, RT)
              - pr.free_energy(2.0, V_A, RT) - pr.free_energy(0.3, V_B, RT))
        assert cf["heat_pJ"] == pytest.approx(-dG, rel=1e-12)
    eqm = pr.equilibrium(2.0, 0.3, V_A, V_B, rt=RT)
    assert pr.closed_pair(60 / k, 2.0, 0.3, V_A, V_B, PA, rt=RT)["heat_pJ"] == pytest.approx(
        eqm["heat_pJ"], rel=1e-12)
    assert eqm["c_eq"] == pytest.approx(2.3 / (V_A + V_B), rel=EPS)


def test_the_per_step_heat_against_fifty_digits():
    rng = np.random.default_rng(3)
    for _ in range(200):
        a = 10 ** rng.uniform(-15, 1, 2)  # trace to large
        V = 10 ** rng.uniform(-1, 1, 2)
        d = rng.uniform(-0.5, 0.5) * min(a)
        deltas = (-d, d)  # a closed step moves d from one side to the other
        heat, scale = pr.step_heat(a, deltas, V, RT)
        exact = pr.exact_step_heat(a, deltas, V, RT)
        assert abs(heat - float(exact)) <= 4 * EPS * scale
    assert pr.exact_step_heat((1.0, 2.0), (0.0, 0.0), (1.0, 1.0), RT) == 0


def test_r_tissue_on_the_coordinators_world_agrees():
    """Two cells joined by a junction; X (z = 0) absent from the bath (a trace there) and
    impermeant at the membranes: R-tissue's static entry point integrates the full electrical
    world, and X follows the closed form (the unit factor and the valence-0 kernel)."""
    from validation.division import cleft_tissue_reference as rt

    sp, z = ("Na", "K", "Cl", "X"), (1, 1, -1, 0)
    leak = (1e-10, 2e-9, 5e-10, 0.0)
    P_X, A_e = 1e-7, 1e-11
    world = rt.World(
        temperature_K=300.0, bath_mM=(140.0, 5.0, 145.0, 1e-15), species=sp, z=z,
        cells={"a": rt.CellSpec(volume_pL=V_A, mM=(12.0, 140.0, 30.0, 1.0), initial_V=-0.06),
               "b": rt.CellSpec(volume_pL=V_B, mM=(14.0, 135.0, 32.0, 1e-3), initial_V=-0.05)},
        patches={"a.m": rt.PatchSpec("a", "bath", leak, area_m2=4e-10, capacitance_F=4e-12),
                 "b.m": rt.PatchSpec("b", "bath", leak, area_m2=4e-10, capacitance_F=4e-12)},
        contacts={"e": rt.ContactSpec(("a", "b"), (2e-7, 3e-7, 4e-7, P_X), area_m2=A_e)})
    k = pr.rate_constant(P_X * A_e, V_A, V_B)
    times = (0.1 / k, 1.0 / k)
    small = dict(cell_charge=1e-15, cleft_charge=1e-17, cell_amount=1e-14, cleft_amount=1e-14,
                 heat=1e-15)
    run = rt.simulate_static(world, times[-1], record=times, atol=small)
    for t in times:
        cf = pr.closed_pair(t, 1.0 * V_A, 1e-3 * V_B, V_A, V_B, P_X * A_e)
        assert run.at[t]["cells"]["a"]["amounts_fmol"][3] == pytest.approx(cf["n_a"], rel=1e-12)
        assert run.at[t]["cells"]["b"]["amounts_fmol"][3] == pytest.approx(cf["n_b"], rel=1e-12)


def test_refusals():
    with pytest.raises(ValueError):
        pr.closed_pair(1.0, 0.0, 1.0, 1.0, 1.0, PA)  # absent is a trace, not zero
    with pytest.raises(ValueError):
        pr.closed_pair(1.0, 1.0, 1.0, 1.0, 1.0, -PA)
    with pytest.raises(ValueError):
        pr.check_world(pr.World(RT, {"a": pr.Compartment(1.0, 1.0)},
                                {"j": pr.Route("a", "a", PA)}))


@pytest.mark.parametrize("ratio", [1.0 + 1e-8, 1.0 + 1e-3])
def test_near_equal_starts_hold_the_heat_to_its_rounding_scale(ratio):
    n_a0, n_b0 = 1.0 * V_A, 1.0 / ratio * V_B
    k = pr.rate_constant(PA, V_A, V_B)
    for t in (0.1 / k, 3.0 / k):
        cf = pr.closed_pair(t, n_a0, n_b0, V_A, V_B, PA, rt=RT)
        exact = float(pr.exact_closed_pair(t, n_a0, n_b0, V_A, V_B, PA, RT)["heat"])
        assert exact > 0.0
        # The heat is second order in the gradient, its terms first order: judged on the scale.
        assert abs(cf["heat_pJ"] - exact) <= 8 * EPS * cf["heat_scale_pJ"]


def test_a_three_compartment_chain_with_the_default_method():
    world = pr.World(RT, {"a": pr.Compartment(1.0, 3.0), "b": pr.Compartment(2.0, 1e-12),
                          "c": pr.Compartment(0.5, 0.2)},
                     {"ab": pr.Route("a", "b", 2e-18), "bc": pr.Route("b", "c", 5e-18)})
    k = pr.rate_constant(2e-18, 1.0, 2.0)
    T = 40.0 / k
    run = pr.integrate(world, T, record=(1.0 / k, T))
    for t in (1.0 / k, T):
        r = run.at[t]
        assert abs(r["material_residual_fmol"]) <= 1e-12 * 3.2
        assert abs(r["closure_pJ"]) <= 1e-12 * RT * 3.2
        assert r["heat_pJ"] > 0.0
    c_eq = 3.2 / 3.5
    for x in ("a", "b", "c"):
        assert run.at[T]["c_mM"][x] == pytest.approx(c_eq, rel=1e-9)
