"""OL2 milestone 2: the osmotic lumen and lysis in cells.model.assembly_lineages@2
(docs/ORIGIN_OF_LIFE_OL2_OL3_CHECK.md §1.4–§1.6, §5; the design note's §0.2b–§0.2e).

Each claim with a planted error it must catch (D187):
- L1: F_osm is its closed form, and V(n) = min(N_L/(N_A c_ext), V_sph(A)) is F's minimiser over
  V ≤ V_sph (planted: a lumen species left out of N_L, whose V is not the minimiser); its change
  under a step, at tens of thousands of lumen molecules, is exact to double precision in each
  branch and across the kink (OL5's precision fix; planted: two values of F subtracted);
- L3: σ is Laplace's Δp·R/2, zero while floppy and continuous at the kink (planted: Δp·R); the
  host accessor of OL5's kernel probe (lumen.host_derived) gives W, A, R, V_osm, V_sph, V and σ by
  the kernel's own expressions, V and σ bitwise those of host_volume_L and host_tension (planted:
  V_sph in m³, a thousandth of its value in L);
- L2, L4: the osmotic verdict keeps the identity, and a closed world that crosses the kink relaxes
  to exp(−F)/Z, from the engine's own host rates (planted: F without its osmotic term);
- Y1: an event past σ_max ends the life lysed: its molecules return to their pool places, the
  closure cost is released, and one ledger row books q = −(F(n_after) − F(n)) + w (planted: the
  closure cost kept, which leaves the ledger open by exactly that cost);
- L5: c_ext's refusal and the drift report; every refusal of §0.2c rules 6–8 this milestone owns.

World-compiling cost: one program (the lysis world, run twice, with a finite and a held pool),
30.11 s for the whole file on the timed lane; the rest is host arithmetic.
Reason: the lysis booking is the only claim that needs the device's run.
"""

import copy
import math

import numpy as np
import pytest

from cells.definitions.specs import ConfigError, parse_spec
from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    MEMBRANE_PERMEATION,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    balance,
    ledger,
    lumen,
    model,
    records,
    reference,
    runner,
)
from tests.assembly_lineage_v2_fixtures import definition

Q = 1e-19  # m², the quantum
K_L = 60  # quanta of one L molecule
C_EXT_MM = 1000.0
NA = 6.02214076e23


def species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def osmotic_world(*, L_pool=4, L_mem=6, S_pool=3, S_lumen=1, I_lumen=2, mu_bilayer=-2.0,
                  sigma_max=1e3, floor=4 * K_L):  # fmt: skip
    """A closed world: L joins the membrane from the pool, S enters the lumen, I is impermeant."""
    u = "unsourced; test"
    return {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {
            "free_energy_form": "discrete",
            "condensed_measure": "multinomial",
            "membrane_kinetics": "count_on_m",
            "lumen_volume": "osmotic",
            "empty_catalyst_phase": "uncatalysed",
            "last_molecule": "kept",
            "exchange_encounter": "insertion_area",
        },  # fmt: skip
        "species": [
            species("L", {"l": 1}, solution=0.0, bilayer=mu_bilayer),
            species("S", {"s": 1}, solution=0.0),
            species("I", {"i": 1}, solution=0.0),
        ],  # fmt: skip
        "phases": {
            "pool": {
                "volume_L": 1e-22,
                "species": [
                    {"id": "L", "kind": "finite"},
                    {"id": "S", "kind": "finite"},
                    {"id": "I", "kind": "finite"},
                ],
            },
            "membrane": {"species": ["L"]},
            "lumen": {"species": ["S", "I"]},
        },  # fmt: skip
        "steps": [
            {
                "id": "join",
                "locus": "membrane",
                "reactants": {"L@pool": 1},
                "products": {"L@membrane": 1},
                "law": PHASE_EXCHANGE,
                "insertion_velocity_m_per_s": {"value": 2e-9, "provenance": u},
            },
            {
                "id": "entry",
                "locus": "membrane",
                "reactants": {"S@pool": 1},
                "products": {"S@lumen": 1},
                "law": MEMBRANE_PERMEATION,
                "permeability_m_per_s": {"value": 5e-10, "provenance": u},
            },
        ],  # fmt: skip
        "free_energy": [
            {"law": IDEAL_MIXING},
            {"law": OSMOTIC_LUMEN, "outside_osmolarity_mM": {"value": C_EXT_MM, "provenance": u}},
        ],
        "founder": {
            "L@pool": L_pool,
            "S@pool": S_pool,
            "I@pool": 0,
            "L@membrane": L_mem,
            "S@lumen": S_lumen,
            "I@lumen": I_lumen,
        },  # fmt: skip
        "geometry": {
            "law": BILAYER_GEOMETRY,
            "area_quantum_m2": Q,
            "area_per_leaflet": {"L": {"quanta": K_L, "provenance": u}},
            "vesicle_floor": {"quanta": floor, "provenance": u},
            "closure_cost_kT": {"value": 25.0, "provenance": u},
            "sigma_max_N_per_m": {"value": sigma_max, "provenance": u},
        },
    }


def spec_of(world_dict, **kw):
    return parse_spec(definition(world_dict, molecules=64, **kw))


def v_sph_L(n_mem):
    area = Q * K_L * n_mem / 2.0
    return area**1.5 / (6.0 * math.sqrt(math.pi)) * 1e3


def test_the_osmotic_volume_is_f_s_minimiser_and_its_tension_is_laplace_s():
    s = spec_of(osmotic_world())
    w = s.model.world
    layout = model.layout(s)
    (term_layout,) = layout.terms
    c_ext = C_EXT_MM * 1e-3
    for n_mem, n_s, n_i in ((4, 0, 2), (6, 1, 2), (9, 3, 2), (12, 4, 2), (5, 0, 0)):
        counts = np.zeros(model.structure(s).places, dtype=np.int64)
        names = [p.name for p in w.places]
        counts[names.index("L@membrane")] = n_mem
        counts[names.index("S@lumen")] = n_s
        counts[names.index("I@lumen")] = n_i
        n_l = n_s + n_i
        f = lumen.value(counts, None, term_layout)
        derived = lumen.host_derived(w, counts[: len(w.places)])  # OL5's kernel probe
        assert derived["W"] == K_L * n_mem and derived["A_m2"] == Q * K_L * n_mem / 2.0
        assert derived["V_sph_L"] == pytest.approx(v_sph_L(n_mem), rel=1e-12, abs=0)
        assert derived["V_sph_L"] != pytest.approx(
            v_sph_L(n_mem) * 1e-3, rel=1e-6, abs=0
        )  # planted
        assert derived["V_L"] == lumen.host_volume_L(w, counts[: len(w.places)])
        assert derived["tension_N_per_m"] == lumen.host_tension(w, counts[: len(w.places)])
        if n_l == 0:
            assert f == 0.0
            assert derived["V_osm_L"] == derived["V_L"] == derived["tension_N_per_m"] == 0.0
            continue
        assert derived["V_osm_L"] == pytest.approx(n_l / (NA * c_ext), rel=1e-12, abs=0)
        assert derived["V_L"] == pytest.approx(
            min(n_l / (NA * c_ext), v_sph_L(n_mem)), rel=1e-12, abs=0
        )
        v = min(n_l / (NA * c_ext), v_sph_L(n_mem))

        def f_of(volume, n_l=n_l):
            return -n_l * math.log(NA * 1.0 * volume) + NA * c_ext * volume

        assert f == pytest.approx(f_of(v), rel=1e-12, abs=1e-12)
        grid = np.linspace(v * 1e-3, v_sph_L(n_mem), 4001)
        assert f_of(v) <= min(f_of(x) for x in grid) + 1e-9  # L1: V(n) is the minimiser
        # Planted: I left out of N_L, so V counts only S: not the minimiser where they differ.
        v_planted = min(n_s / (NA * c_ext), v_sph_L(n_mem))
        if n_i and n_s and v_planted < v_sph_L(n_mem) and v < v_sph_L(n_mem):
            assert f_of(v_planted) > f_of(v) + 1e-6
        # L3: Laplace's tension, zero while floppy.
        sigma = lumen.host_tension(w, counts[: len(w.places)])
        radius = math.sqrt(Q * K_L * n_mem / 2.0 / (4.0 * math.pi))
        assert derived["R_m"] == radius
        kT = 1.380649e-23 * 296.15
        dp = kT * (n_l / (v * 1e-3) - NA * c_ext * 1e3)
        expected = max(0.0, dp * radius / 2.0)
        assert sigma == pytest.approx(expected, rel=1e-10, abs=1e-15)
        if expected > 1e-9:  # tense (a floppy state's dp is rounding around 0)
            assert sigma != pytest.approx(dp * radius, rel=1e-6)  # Planted: Δp·R, no 1/2.
    # The kink: σ is 0 just below it and small just above it (continuous).
    n_mem = 9
    kink = NA * c_ext * v_sph_L(n_mem)  # N_L at V_osm = V_sph
    assert 6 < kink < 8  # so N_L = 6 is floppy and N_L = 8 tense in this world
    # OL5's precision fix: F_osm's change at large counts, exactly (50 digits, from the inputs'
    # float64 values) in each branch and across the kink, by lumen molecules and by footprint.
    from decimal import Decimal, localcontext

    c = term_layout[2]
    with localcontext() as context:
        context.prec = 50
        pi = Decimal(lumen.PI_50)

        def f_exact(n_l, w_q):
            half = Decimal(Q) * w_q / 2
            v_sph = half * half.sqrt() / (6 * pi.sqrt()) * 1000
            v = min(Decimal(n_l) / (Decimal(NA) * Decimal(c_ext)), v_sph)
            return -n_l * (Decimal(NA) * Decimal(1.0) * v).ln() + Decimal(NA) * Decimal(c_ext) * v

        w_q = 60 * 3334  # W = 200,040 quanta: the kink near N_L = 56,600
        n_kink = int(NA * c_ext * v_sph_L(3334))
        w_cross = next(w for w in range(w_q, 2 * w_q, 60)
                       if NA * c_ext * v_sph_L((w - 60) // 60) < n_kink < NA * c_ext
                       * v_sph_L(w // 60))  # fmt: skip
        cases = [(40000, w_q, 39999, w_q), (80000, w_q, 80000, w_q - 60),  # floppy; tense
                 (n_kink, w_q, n_kink + 1, w_q), (n_kink + 1, w_q, n_kink, w_q),  # across, by N_L
                 (n_kink, w_cross, n_kink, w_cross - 60)]  # across, by W  # fmt: skip
        for n0, w0, n1, w1 in cases:
            got = lumen.change_between(*(np.asarray([x]) for x in (n0, w0, n1, w1)), c, np)[0]
            want = f_exact(n1, w1) - f_exact(n0, w0)
            assert abs(Decimal(float(got)) - want) <= Decimal("2e-14")  # k_BT: 5e-15 at most
        two_values = (
            lumen.free_energy(np.asarray([80000]), np.asarray([w_q - 60]), c, np)
            - lumen.free_energy(np.asarray([80000]), np.asarray([w_q]), c, np)
        )[0]
        assert abs(
            Decimal(float(two_values)) - (f_exact(80000, w_q - 60) - f_exact(80000, w_q))
        ) > Decimal("1e-12")  # planted: the two values subtracted


def test_the_osmotic_verdict_holds_and_a_closed_world_relaxes_to_exp_minus_f():
    verdict = balance.osmotic_verdict()
    assert verdict["holds"] and verdict["probe"]["pairs"] > 1000
    assert verdict["probe"]["max_abs_deviation_ln"] <= balance.ATOL
    s = spec_of(osmotic_world())
    w = s.model.world
    structure, layout, tables = model.structure(s), model.layout(s), model.tables(s)
    names = [p.name for p in w.places]
    il, im, isp, isl = (names.index(n) for n in ("L@pool", "L@membrane", "S@pool", "S@lumen"))
    L_total, S_total = 10, 4
    states = [(m, sl) for m in range(4, L_total + 1) for sl in range(S_total + 1)]
    index = {x: i for i, x in enumerate(states)}

    def counts_of(x):
        c = np.zeros(structure.places, dtype=np.int64)
        c[il], c[im], c[isp], c[isl] = L_total - x[0], x[0], S_total - x[1], x[1]
        c[names.index("I@lumen")] = 2
        return c

    regimes = {lumen.host_tension(w, counts_of(x)[: len(w.places)]) > 0 for x in states}
    assert regimes == {True, False}  # the world crosses the kink
    R = structure.steps
    gen = np.zeros((len(states), len(states)))
    moves = {0: (1, 0), 1: (0, 1)}  # join, entry
    for x in states:
        rates = np.exp(balance.host_log_rates(counts_of(x), layout, structure))
        for r, (dm, ds) in moves.items():
            for sign, channel in ((1, r), (-1, R + r)):
                y = (x[0] + sign * dm, x[1] + sign * ds)
                if y in index and rates[channel] > 0:
                    gen[index[y], index[x]] += rates[channel]
                    gen[index[x], index[x]] -= rates[channel]
    a = gen.copy()
    a[-1, :] = 1.0
    b = np.zeros(len(states))
    b[-1] = 1.0
    pi = np.linalg.solve(a, b)
    f = np.asarray([ledger.free_energy(counts_of(x), tables, w.terms, layout.terms)
                    for x in states])  # fmt: skip
    boltzmann = np.exp(-(f - f.min()))
    boltzmann /= boltzmann.sum()
    assert 0.5 * np.abs(pi - boltzmann).sum() < 1e-9  # L4
    # Planted: F without its osmotic term is not the stationary law.
    ideal = np.asarray([ledger.free_energy(counts_of(x), tables, w.terms[:1], ())
                        for x in states])  # fmt: skip
    planted = np.exp(-(ideal - ideal.min()))
    planted /= planted.sum()
    assert 0.5 * np.abs(pi - planted).sum() > 1e-3


@pytest.mark.parametrize("held", [False, True], ids=["finite_pool", "held_pool"])
def test_lysis_ends_the_life_returns_its_molecules_and_books_one_row(held, tmp_path):
    base = osmotic_world(L_pool=2, L_mem=5, S_pool=0, S_lumen=0, I_lumen=4, mu_bilayer=3.0,
                         floor=K_L)  # fmt: skip
    if held:  # L's pool place is held: the release returns L to its reservoir.
        base["phases"]["pool"]["species"][0] = {"id": "L", "kind": "held", "held_mM": 10.0}
        base["founder"].pop("L@pool")
    founder_sigma = lumen.host_tension(spec_of(base).model.world, spec_of(base).model.world.founder)
    assert founder_sigma > 0  # tense: N_L = 4 above the kink at 5 molecules
    w = copy.deepcopy(base)
    w["geometry"]["sigma_max_N_per_m"]["value"] = founder_sigma * 1.0001
    s = spec_of(w, horizon=50.0, event_limit=2000, row_every=50, uniforms=True)
    run = runner.run(s).check()
    assert run.status == "lysed" and run.closure["holds"]
    names = [p.name for p in s.model.world.places]
    end = dict(zip(names, run.rows["place_count"][-1], strict=True))
    assert end["L@membrane"] == end["S@lumen"] == end["I@lumen"] == 0
    assert end["I@pool"] == 4  # every lumen molecule returned as a monomer
    lysis = run.osmotic["lysis"]
    assert lysis["sigma_N_per_m"] > lysis["sigma_max_N_per_m"]
    assert lysis["returned"]["I@pool"] == 4
    # F(n_after) in closed form, apart from the engine's ledger: everything is in the pool, so
    # F = Σ_finite pool [n (μ° − ln X_pool) + ln n!], no membrane, lumen or closure term.
    x_pool = NA * 1e-22 * 1.0  # N_A V c0, c0 = 1 mol/L
    closed = sum(n * (0.0 - math.log(x_pool)) + math.lgamma(n + 1)
                 for name, n in end.items() if name.endswith("@pool") and n)  # fmt: skip
    assert run.rows["free_energy_kT"][-1] == pytest.approx(closed, abs=1e-9)
    supplied = dict(zip(names, run.rows["reservoir_supplied"][-1], strict=True))
    if held:
        # The founder's five membrane L end in the reservoir: net supply −5. Their return books
        # reservoir work −Σ μ_held per molecule, with μ_held = μ° + ln(c/c0) = ln(10/1000).
        assert supplied["L@pool"] == -5
        returned = lysis["returned"]["L@pool"]
        assert lysis["release_reservoir_work_kT"] == pytest.approx(
            -returned * math.log(10.0 / 1000.0), rel=1e-12
        )
    else:
        assert end["L@pool"] == 7  # every L, wherever it was, is a pool monomer after the lysis
        assert lysis["release_reservoir_work_kT"] == 0.0
    # Planted: the closure cost kept after lysis leaves the books open by exactly that cost.
    f = run.rows["free_energy_kT"].copy()
    f[-1] += 25.0
    planted = ledger.residual(run.rows["event_heat_kT"], run.rows["reservoir_work_kT"], f, f[0])
    assert abs(planted[-1]) == pytest.approx(25.0, abs=1e-9)
    # L5: the drift report is the pool's solute osmolarity's change, relative to c_ext.
    counts = run.rows["place_count"]
    pool = [i for i, p in enumerate(s.model.world.places) if p.phase == "pool" and not p.held]
    held_mM = sum(p.held_mM for p in s.model.world.places if p.phase == "pool" and p.held)
    osm = counts[:, pool].sum(axis=1) / (NA * 1e-22) * 1e3 + held_mM
    drift = np.max(np.abs(osm - osm[0])) / C_EXT_MM
    assert run.osmotic["largest_relative_drift"] == pytest.approx(drift, rel=1e-12)
    # The bundle is written and read back, and the host oracle replays its trace.
    records.write_run(tmp_path / "bundle", run)
    world_record, run_record, arrays = records.read(tmp_path / "bundle")
    assert run_record["end"]["status"] == "lysed" and "lysed" in run_record["lifecycle"]["statuses"]
    assert run_record["osmotic"]["lysis"]["returned"] == lysis["returned"]
    assert set(arrays) >= {"lumen_volume_L", "tension_N_per_m", "membrane_footprint_quanta"}
    assert world_record["world"]["conventions"]["lumen_volume"] == "osmotic"
    channels, times = reference.replay(s, arrays["event_uniforms"])
    assert np.array_equal(channels, arrays["event_channel"])
    np.testing.assert_allclose(times, arrays["event_time"], rtol=1e-12, atol=0)


def _dimerising(w):
    """S + S -> D in the lumen: two lumen reactant molecules, refused by §0.2c rule 7."""
    w["species"].append(species("D", {"s": 2}, solution=0.0))
    w["phases"]["pool"]["species"].append({"id": "D", "kind": "finite"})
    w["phases"]["lumen"]["species"].append("D")
    w["founder"].update({"D@pool": 0, "D@lumen": 0})
    w["steps"].append({"id": "pair", "phase": "lumen", "reactants": {"S": 2},
                       "products": {"D": 1}, "law": "cells.reaction.stochastic_mass_action@1",
                       "forward_rate_per_s": 1.0})  # fmt: skip


REFUSALS = {
    "osmotic without a geometry": (
        lambda w: (w.pop("geometry"), w["conventions"].pop("exchange_encounter"),
                   w["steps"].clear()), "declares a geometry"),
    "a volume_L under osmotic": (
        lambda w: w["phases"]["lumen"].update(volume_L=1e-22), "declares no volume_L"),
    "osmotic without its term": (
        lambda w: w["free_energy"].pop(1), "declares cells.free_energy.osmotic_lumen@1"),
    "the term without osmotic": (
        lambda w: w["conventions"].update(lumen_volume="declared")
        or w["phases"]["lumen"].update(volume_L=1e-22)
        or w["geometry"].pop("sigma_max_N_per_m"), "only under lumen_volume osmotic"),
    "osmotic without sigma_max": (
        lambda w: w["geometry"].pop("sigma_max_N_per_m"), "declares sigma_max_N_per_m"),
    "two lumen reactants": (lambda w: _dimerising(w), "lumen reactant molecules"),
    "a lumen species without a pool place": (
        lambda w: w["phases"]["pool"]["species"].pop(2) and w["founder"].pop("I@pool"),
        "has a pool place"),
    "c_ext below the pool's solutes": (
        lambda w: w["free_energy"][1]["outside_osmolarity_mM"].update(value=10.0),
        "below its declared pool solutes"),
    "a founder beyond sigma_max": (
        lambda w: w["founder"].update({"I@lumen": 40, "L@membrane": 4})
        or w["geometry"]["sigma_max_N_per_m"].update(value=1e-6), "beyond sigma_max"),
}  # fmt: skip


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_every_refusal_of_the_osmotic_lumen(case):
    edit, message = REFUSALS[case]
    w = osmotic_world()
    edit(w)
    with pytest.raises(ConfigError, match=message):
        spec_of(w)
