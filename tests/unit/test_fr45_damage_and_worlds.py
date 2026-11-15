"""FR-5's kernels (bounding_patch_damage@1, ph_conditioned_factor@1) and the first acceptance
worlds' fixtures (validation/compartment_ph), checked against the FR-4/FR-5 note's equations."""

import math

import numpy as np
import pytest
from scipy.integrate import solve_ivp

from cells.processes import patch_damage as dmg
from cells.processes import ph_condition as phc
from validation.compartment_ph import definitions as defs
from validation.compartment_ph import dt_study
from validation.compartment_ph.parameters import DamageWorld, World

# --- bounding_patch_damage@1 -------------------------------------------------------------------


@pytest.mark.parametrize("d0,a,b,h", [(0.0, 1.0, 0.0, 10.0), (0.3, 1.0, 0.05, 0.7),
                                      (0.9, 0.0, 0.05, 3.0), (0.5, 2.0, 2.0, 1e-12)])
def test_exact_step_matches_the_ode(d0, a, b, h):
    sol = solve_ivp(lambda _t, y: [a * (1 - y[0]) - b * y[0]], (0, h), [d0], rtol=1e-12,
                    atol=1e-15, method="Radau")
    got = dmg.exact_step(np.float64(d0), a, b, 1.0, 1.0, h, xp=np)
    assert got == pytest.approx(sol.y[0, -1], abs=1e-11)
    assert 0.0 <= got <= 1.0


def test_injury_opens_toward_its_equilibrium_and_resealing_closes():
    d = 0.0
    for _ in range(100):
        d = dmg.exact_step(d, 1.0, 0.05, 1.0, 0.0, 0.1, xp=np)  # injury on, resealing off
    assert d == pytest.approx(1.0 - math.exp(-10.0), rel=1e-12)
    for _ in range(100):
        d = dmg.exact_step(d, 1.0, 0.05, 0.0, 1.0, 1.0, xp=np)  # resealing only
    assert d < 1e-2


def test_no_schedule_leaves_damage_unchanged_and_the_domain_refuses_out_of_range():
    assert dmg.exact_step(0.4, 1.0, 1.0, 0.0, 0.0, 5.0, xp=np) == 0.4
    assert dmg.domain_valid(0.5, 1.0, 0.05, 1.0, 0.0, xp=np)
    assert not dmg.domain_valid(1.2, 1.0, 0.05, 1.0, 0.0, xp=np)
    assert not dmg.domain_valid(0.5, -1.0, 0.05, 1.0, 0.0, xp=np)
    assert dmg.leak_permeability_m_s(0.25, 1e-6) == pytest.approx(2.5e-7)


# --- ph_conditioned_factor@1 -------------------------------------------------------------------


def test_the_ph_factor_is_open_below_ph50_and_closed_above():
    assert phc.factor(5.5, 5.5, 4.0, xp=np) == pytest.approx(0.5, abs=1e-15)
    low, high = phc.factor(4.5, 5.5, 4.0, xp=np), phc.factor(6.5, 5.5, 4.0, xp=np)
    assert low == pytest.approx(1 / (1 + 10 ** -4), rel=1e-12)
    assert high == pytest.approx(1 / (1 + 10 ** 4), rel=1e-12)
    grid = phc.factor(np.linspace(3, 9, 61), 5.5, 4.0, xp=np)
    assert np.all(np.diff(grid) < 0) and np.all((grid >= 0) & (grid <= 1))
    assert phc.factor(40.0, 5.5, 4.0, xp=np) >= 0.0  # no overflow far above


def test_the_routing_door_multiplies_and_refuses_out_of_range_factors():
    value, ok = phc.combine([0.5, 0.25], xp=np)
    assert ok and value == pytest.approx(0.125)
    _, bad = phc.combine([0.5, 1.5], xp=np)
    assert not bad
    assert not phc.factor_valid(5.0, 5.5, -1.0, xp=np)  # the planted sign of the slope fails


# --- the worlds' parameters and definitions ---------------------------------------------------


def test_the_world_reproduces_the_note_values():
    w = World()
    assert w.pump_capacity_fmol_s == pytest.approx(8.3027e-3, rel=1e-4)
    assert w.counterion_rate_per_s() == pytest.approx(0.0253, abs=1e-4)  # at 1 ms, max-side
    assert w.held_fuel_drive_J_mol() / 1000 == pytest.approx(-51.41, abs=0.01)
    assert w.lumen_volume_pL == pytest.approx(6.54498e-2, rel=1e-5)
    assert w.patch_capacitance_F == pytest.approx(7.85398e-12, rel=1e-5)
    assert w.lumen_buffer.k_mM == pytest.approx(1e-3, rel=1e-12)  # pK 6 from the potentials
    assert w.control().counterion_k_m_s == 0.0 and w.counterion_k_m_s == 5e-10


def test_every_node_starts_electroneutral_and_with_its_proton_equivalents():
    d = defs.fr4_world()
    z = dict(defs.SPECIES)
    for node in d["model"]["cells"] + d["model"]["extracellular"]:
        a = node["initial_amount_fmol"]
        assert math.fsum(z[s] * n for s, n in a.items()) + node["fixed_charge_equivalent_fmol"] \
            == pytest.approx(0.0, abs=1e-12)
    lumen = next(n for n in d["model"]["extracellular"] if n["id"] == defs.LUMEN)
    w = World()
    h = 1000 * 10 ** -7.2
    expected = w.lumen_volume_pL * (h + 40.0 * h / (h + 1e-3))
    assert lumen["initial_amount_fmol"]["H"] == pytest.approx(expected, rel=1e-12)
    assert len(d["model"]["species"]) == 9  # §12: FR-4 uses 9 rows


def test_today_only_strips_every_pending_part_and_the_control_removes_the_route():
    d = defs.fr4_world(World().control())
    today = defs.today_only(d)
    assert not set(defs.PENDING_MODEL_KEYS) & set(today["model"])
    assert not set(defs.PENDING_EXPERIMENT_KEYS) & set(today["experiment"])
    bounding = next(p for p in today["model"]["membranes"] if p["id"] == defs.BOUNDING)
    assert all(v == 0.0 for v in bounding["permeability_m_per_s"].values())


def test_the_fr5_world_adds_cargo_damage_and_three_routes_without_ionic_pores():
    d = defs.fr5_world(DamageWorld())
    assert len(d["model"]["species"]) == 10  # §12: FR-5 uses 10 rows
    routes = {r["id"]: r for r in d["model"]["passive_routes"]}
    assert set(routes) == {"proton_leak_0", "cargo_transfer_0", "cargo_pore_0", "proton_pore_0"}
    assert routes["proton_pore_0"]["law"] == "proton_constant_field_leak@1"
    assert not DamageWorld().ionic_pores
    assert "damage_controls" not in defs.today_only(d)["experiment"]


def test_the_dt_study_ladder_and_criteria():
    rungs = dt_study.build_rungs()
    products = [r["product"] for r in rungs]
    assert products[1] == pytest.approx(0.0253, abs=1e-4)
    assert all(a / b == pytest.approx(2.0) for a, b in zip(products, products[1:], strict=False))
    assert set(dt_study.CRITERIA["checks"]) == {f"C{i}_" + s for i, s in enumerate(
        ("admission", "order", "state_error_at_declared_dt", "energy", "ledgers", "bands",
         "envelope", "reference", "control"), start=1)}
    assert dt_study.observed_order(1.0, 0.25, 0.0625) == pytest.approx(2.0)
