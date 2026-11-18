"""OL5's OL2 references: the registration, the law in integer quanta, the kernel and stationary
checks with their planted controls, lysis's booking and the refusals (code-blind; no engine)."""

from __future__ import annotations

import math

import numpy as np
import pytest

from validation.ool.references import design2
from validation.ool.references import harness2 as H2
from validation.ool.references import ol2_checks as OC
from validation.ool.references import refusals2 as RF
from validation.ool.references import registered2 as R2
from validation.ool.references.ol2 import N_A, PLANTED_LAW, Law2, Vesicle2

WORLDS = R2.worlds()


def test_committed_designs_equal_their_generators(tmp_path):
    R2.write_all(tmp_path)
    design2.write_design(tmp_path)
    generated = sorted(p.relative_to(tmp_path) for p in tmp_path.rglob("*.json"))
    assert len(generated) > 30
    for rel in generated:
        assert (R2.DESIGN_DIR / rel).read_bytes() == (tmp_path / rel).read_bytes(), rel
    committed = {p.relative_to(R2.DESIGN_DIR) for p in R2.DESIGN_DIR.rglob("*.json")
                 if p.name.startswith(("ol2_", "ol3_")) or p.parent.name == "refusals2"}
    assert committed <= set(generated), "a stale OL2/OL3 design file"


def test_worlds_parse_and_each_declaration_is_refused_for_its_rule():
    for w in WORLDS.values():
        RF.validate(R2.world_document(w))
    for r in R2.runs(WORLDS).values():
        RF.validate(R2.run_document(r))
    docs = RF.registered_documents()
    assert len(docs) == 22
    for d in docs:
        with pytest.raises(RF.Refused) as exc:
            RF.validate(d)
        assert exc.value.rule == d["refusal"]["rule"], d["id"]


def test_geometry_in_integer_quanta():
    w = WORLDS["ol2_wa"]
    law = Law2(w)
    v = Vesicle2((1800, 100), (1000, 0))
    assert law.W(v) == 2000
    A = w.q_m2 * 2000 / 2                                  # A = q W/2 (§0.2c rule 4, §0.2d 1)
    assert law.area(2000) == A
    assert law.radius(2000) == math.sqrt(A / (4 * math.pi))
    assert math.isclose(law.v_sph_L(2000), A ** 1.5 / (6 * math.sqrt(math.pi)) * 1e3, rel_tol=1e-15)
    assert math.isclose(w.C_close, 40 * math.pi, rel_tol=1e-15)
    kink = R2.lumen_for(2000, 1.0)
    floppy, tense = Vesicle2((1800, 100), (kink, 0)), Vesicle2((1800, 100), (kink + 2000, 0))
    assert law.tension(floppy) == 0.0 and law.reduced_volume(floppy) <= 1.0
    assert math.isclose(law.reduced_volume(tense), 1.0, rel_tol=1e-12)
    # Laplace: sigma = Delta p R/2, Delta p = k_BT (N_L/V - N_A c_ext) per m^3
    V = law.v_sph_L(2000)
    dp = w.kT * 1e3 * ((kink + 2000) / V - N_A * w.c_ext_M)
    assert math.isclose(law.tension(tense), dp * law.radius(2000) / 2, rel_tol=1e-12)
    # N_L counts every lumen species, permeants included (§0.2c rule 6)
    assert law.N_L(Vesicle2((1800, 100), (10, 7))) == 17
    assert law.volume_L(Vesicle2((1800, 100), (0, 0))) == 0.0 and law.F_lumen(Vesicle2((1800, 100), (0, 0))) == 0.0


def test_encounter_rates_follow_the_tokens():
    p = (30, 0)
    v = Vesicle2((1800, 100), (20000, 500))
    rho0 = N_A * 1e-3 * 1e3
    for name, extent in (("ol2_wa", lambda law: law.area(2000)),
                         ("ol2_wa_diffusion", lambda law: 4 * math.pi * law.radius(2000))):
        w = WORLDS[name]
        law = Law2(w)
        join_L1, join_L2, entry_G, r1 = w.steps
        assert math.isclose(law.rate(v, p, join_L1, 1), join_L1.constant * extent(law) * rho0 * 30 / w.X_pool,
                            rel_tol=1e-14)
        assert math.isclose(law.rate(v, p, join_L2, 1), join_L2.constant * extent(law) * rho0 * 1.0, rel_tol=1e-14)
        assert math.isclose(law.rate(v, p, entry_G, 1), entry_G.constant * law.area(2000) * rho0 * 5.0, rel_tol=1e-14)
        assert math.isclose(law.rate(v, p, r1, 1), 0.5 * 1800 * 1799 / 1900, rel_tol=1e-14)   # count_on_m, c = 0


def test_the_floor_zeroes_area_changing_pairs_only():
    w = WORLDS["ol2_wa"]
    law = Law2(w)
    join_L1, _, entry_G, r1 = w.steps
    below = Vesicle2((w.W_floor - 1, 0), (100, 10))
    at = Vesicle2((w.W_floor, 0), (100, 10))
    assert law.rate(below, (5, 0), join_L1, 1) == 0.0          # the pair (W_floor - 1, W_floor)
    assert law.rate(at, (5, 0), join_L1, -1) == 0.0            # its reverse
    assert law.rate(at, (5, 0), join_L1, 1) > 0.0
    assert law.rate(below, (5, 0), entry_G, 1) > 0.0           # area unchanged: fires below the floor
    assert law.rate(Vesicle2((w.W_floor - 3, 1), (100, 10)), (5, 0), r1, -1) > 0.0


def test_incremental_delta_F_equals_the_difference_of_F():
    rng = np.random.default_rng(5)
    for name in ("ol2_wa", "ol2_lysis"):
        w = WORLDS[name]
        law = Law2(w)
        for _ in range(60):
            n = (int(rng.integers(1100, 1900)), int(rng.integers(1, 200)))
            l = (R2.lumen_for(n[0] + 2 * n[1], float(rng.uniform(0.3, 1.4))), int(rng.integers(0, 3000)))
            v, p = Vesicle2(n, l), (int(rng.integers(1, 50)), 3)
            for ch in w.vesicle_channels():
                for sign in (1, -1):
                    nxt = law.after(v, p, ch, sign)
                    if nxt is None:
                        continue
                    exact = law.F([nxt[0]], nxt[1]) - law.F([v], p)
                    assert abs(law.dF(v, p, *nxt) - exact) <= 1e-12 * law.F_scale([v], p)


@pytest.mark.parametrize("world", ["ol2_wa", "ol2_wa_diffusion"])
def test_kernel_checks_pass_on_the_reference_and_fail_on_each_planted_law(world):
    w = WORLDS[world]
    states = H2.registered_states(world)
    honest = Law2(w)
    t = OC.kernel_table(honest, states)
    for fn in (OC.kolmogorov, OC.identity, OC.forward_form, OC.geometry):
        assert fn(honest, states, t)["passed"], fn.__name__
    assert t["lyses_plus"].sum() + t["lyses_minus"].sum() > 0         # lysis flags are exercised
    for form in PLANTED_LAW:
        p = OC.kernel_table(Law2(w, form), states)
        failed = [fn.__name__ for fn in (OC.kolmogorov, OC.identity, OC.forward_form, OC.geometry)
                  if not fn(honest, states, p)["passed"]]
        if form == "radius_for_area" and w.encounter == "diffusion_radius":
            assert not failed                                             # zero power: the forms coincide
        else:
            assert failed, form
    ident = OC.identity(honest, states, OC.kernel_table(Law2(w, "no_lumen_term"), states))
    assert ident["max_abs_residual"] > 70.0                              # registered 72.8, tolerance 1e-8
    fwd = OC.forward_form(honest, states, OC.kernel_table(Law2(w, "extent_on_target"), states))
    assert fwd["max_abs_log_residual"] >= 9e-4                            # registered 0.001, tolerance 1e-12


def test_stationary_laws_and_the_tension_driven_competition():
    for world in ("ol2_closed", "ol2_two"):
        w = WORLDS[world]
        honest = Law2(w)
        states, slots = H2.closed_world_states(world)
        assert OC.stationary_check(honest, honest, states, slots)["total_variation"] <= 1e-10
        assert OC.stationary_check(Law2(w, "no_lumen_term"), honest, states, slots)["total_variation"] >= 0.06
    w = WORLDS["ol2_two"]
    states, _ = H2.closed_world_states("ol2_two")
    bz = OC.boltzmann(Law2(w), states, 2)
    swollen = float(sum(b * s[0].n[0] for b, s in zip(bz, states)))
    relaxed = float(sum(b * s[1].n[0] for b, s in zip(bz, states)))
    assert swollen > relaxed + 40          # the swollen vesicle takes amphiphiles from the relaxed one (§4.2)


def test_lysis_books_one_row_and_releases_the_closure_cost():
    w = WORLDS["ol2_lysis"]
    law = Law2(w)
    join_L1 = w.steps[0]
    W = 1600
    S = next(s for s in range(R2.lumen_for(W, 1.0), R2.lumen_for(W, 1.2), 5)
             if law.lyses(Vesicle2((1499, 50), (s, 100))))
    v, p = Vesicle2((1500, 50), (S, 100)), (10, 0)
    assert not law.lyses(v)
    v_end, p_end = law.after(v, p, join_L1, -1)                      # a leave: the end state lyses
    assert law.lyses(v_end)
    b = law.lysis_booking(v, p, v_end, p_end, 0.0)
    held = {s: law.held_mu(s) for s, _, _ in w.pool_held}
    w_res = -(50 * held["L2"] + 100 * held["G"])
    assert b["pool_after"] == (10 + 1 + 1499, S)                     # the leave, then monomers to their places
    assert math.isclose(b["reservoir_work_release"], w_res, rel_tol=1e-14)
    dF = law.F_pool(b["pool_after"]) - (law.F_vesicle(v) + law.F_pool(p))
    assert math.isclose(b["heat"], -dF + w_res, rel_tol=1e-12)
    kept = Law2(w, "closure_not_released").lysis_booking(v, p, v_end, p_end, 0.0)
    assert math.isclose(b["heat"] - kept["heat"], w.C_close, rel_tol=1e-9)
    omitted = Law2(w, "release_work_omitted").lysis_booking(v, p, v_end, p_end, 0.0)
    assert math.isclose(b["heat"] - omitted["heat"], w_res, rel_tol=1e-9)
