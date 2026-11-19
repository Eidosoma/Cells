"""FR-2's code-blind references (validation/membrane_trafficking/references): the registered files
regenerate identically, the two routes to every booking agree at 60 digits, and every planted
control has its registered power. No engine code is imported."""

from __future__ import annotations

import json
from decimal import Decimal

import pytest

from validation.core_seams.references.exact import context
from validation.membrane_trafficking.references import design, network, trafficking, worlds

TIGHT = Decimal("1e-45")


@pytest.fixture(scope="module")
def computed():
    return design.compute()


@pytest.fixture(autouse=True)
def sixty_digits():
    """Every comparison here at the references' own 60 digits."""
    with context():
        yield


def test_registered_files_regenerate_identically(computed):
    vals, des = computed
    assert design.VALUES_FILE.read_text() == design.dumps(vals)
    assert design.DESIGN_FILE.read_text() == design.dumps(des)


def test_declared_inputs_are_frozen_with_their_provenance():
    inp = worlds.load()
    assert inp["declared_by"]["tree"]["revision"].startswith("c710d841")
    assert inp["declared_by"]["tree"]["dirty"] == []
    assert set(inp["worlds"]) == set(worlds.WORLDS)
    assert set(inp["stress_worlds"]) == set(worlds.STRESS)
    for name in worlds.WORLDS + worlds.STRESS:
        for node, rel in worlds.anchor_consistency(inp, name).items():
            assert rel < 2e-16, (name, node, rel)
    for name in worlds.STRESS:
        carriers = inp["stress_worlds"][name]["routes"][0]["carriers"]
        assert sum(Decimal(c["value"]) for c in carriers.values()) == 1


def _note_world(V_k=-0.070, C_k=10e-12, C_b=1e-12):
    """The design note's §2.2 example: a cell on a held bath at 0 V with a 10 pF plasma patch at
    −70 mV and a 1 pF pool patch at 0 mV, K the only carrier."""
    nodes = {"bath": {"kind": "held", "potential_V": 0.0, "reference_mM": {"K": 5.0}},
             "i": {"kind": "cell", "volume_pL": 1.0, "anchor_C": C_k * V_k},
             "j": {"kind": "free", "volume_pL": 0.1, "anchor_C": 0.0}}
    patches = {"k": {"inside": "i", "outside": "bath", "area_m2": 1e-9, "capacitance_F": C_k},
               "b": {"inside": "i", "outside": "j", "area_m2": 1e-10, "capacitance_F": C_b}}
    w = network.World(nodes, patches, {"i": {"K": 100.0}, "j": {"K": 1.0}}, {"K": 1}, 310.0)
    route = {"id": "r", "plasma_patch": "k", "pool_patch": "b", "pool_node": "j",
             "carriers": {"K": 1.0}, "enrichment": {}, "recycling_enrichment": {}}
    return trafficking.State(w, [route], {}, {})


def test_the_notes_arithmetic():
    """§2.2: 0.1 pF at −70 mV into a 1 pF pool at 0 mV ends at −6.36 mV with heat 2.23e-4 pJ,
    carrying 7.0e-15 C (7.25e-5 fmol); R1's ΔU for the 10 pF cell is 2.47e-4 pJ, V' −70.71 mV."""
    st = _note_world()
    with context():
        dA = Decimal("0.01") * st.world.patches["k"]["area_m2"]
        new, rep = trafficking.stage(st, "retrieval", {"r": dA})
        phi = rep["potentials_after"]
        Vb = new.world.voltage(phi, "b")
        assert abs(Vb - Decimal("-0.0063636")) < Decimal("1e-7")
        assert abs(rep["heat_closed_pJ"] - Decimal("2.227e-4")) < Decimal("1e-7")
        assert abs(rep["heat_dense_pJ"] - rep["heat_closed_pJ"]) < TIGHT
        q = rep["routes"]["r"]["charge_moved_C"]
        assert abs(q - Decimal("7.0e-15")) < Decimal("1e-20")
        assert abs(rep["routes"]["r"]["carriers_fmol"]["K"] - Decimal("7.255e-5")) < Decimal("1e-8")
        # R1 (insertion backwards, the cell's charge kept): V' = q/(C − dC), ΔU = q² dC/(2C(C − dC))
        C, dC, qc = Decimal("10e-12"), Decimal("0.1e-12"), Decimal("10e-12") * Decimal("-0.070")
        assert abs(qc / (C - dC) - Decimal("-0.0707071")) < Decimal("1e-7")
        dU_pJ = qc ** 2 * dC / (2 * C * (C - dC)) * 10 ** 12
        assert abs(dU_pJ - Decimal("2.4747e-4")) < Decimal("1e-8")


def _half_steps(vals):
    for key, dv in vals["drives"].items():
        for i, hs in enumerate(dv["half_steps"]):
            yield key, i, dv, hs


def test_R2_moves_only_the_pools_and_matches_the_closed_forms(computed):
    vals, _ = computed
    n_ret = n_rec = 0
    for key, i, dv, hs in _half_steps(vals):
        cf = hs["closed_forms"]
        if not cf:
            continue
        pools = set(dv["pool_nodes"])
        maxphi = Decimal(hs["max_abs_potential_V"])
        after = hs["after"]["voltages_V"]
        H = Decimal(cf["heat_pJ"])
        assert abs(Decimal(hs["sums"]["heat_dense_pJ"]) - H) <= TIGHT * H
        if cf["kind"] == "retrieval":
            n_ret += 1
            for n, d in hs["potential_change_V"].items():
                if n not in pools:
                    assert abs(Decimal(d)) <= TIGHT * maxphi, (key, i, n)
            Vb = Decimal(after[dv["pool_patch"]])
            assert abs(Vb - Decimal(cf["V_b_after_V"])) <= TIGHT * abs(Vb), (key, i)
            if dv["outside_held"]:
                shift = Decimal(cf["R1_potential_change_V"][dv["owner"]])
                assert abs(shift - Decimal(cf["R1_shift_V"])) <= TIGHT * abs(shift)
        else:
            n_rec += 1
            Vk = Decimal(after[dv["plasma_patch"]])
            assert abs(Vk - Decimal(cf["V_k_after_V"])) <= TIGHT * abs(Vk), (key, i)
            Vb0 = Decimal(next(iter(hs["stages"][0]["routes"].values()))["V_source"])
            assert abs(Decimal(after[dv["pool_patch"]]) - Vb0) <= TIGHT * abs(Vb0), (key, i)
    assert n_ret >= 20 and n_rec >= 8


def test_energy_bookings_close_and_agree(computed):
    vals, _ = computed
    for key, i, dv, hs in _half_steps(vals):
        s = hs["sums"]
        mt = Decimal(s["max_term_pJ"])
        assert abs(Decimal(s["residual_pJ"])) <= TIGHT * mt, (key, i)
        assert Decimal(s["heat_closed_pJ"]) > 0
        for st in hs["stages"]:
            assert Decimal(st["heat_closed_pJ"]) > 0
            assert abs(Decimal(st["heat_dense_pJ"]) - Decimal(st["heat_closed_pJ"])) <= TIGHT * mt
        assert abs(Decimal(s["W_res_pJ"]) - Decimal(s["W_res_closed_pJ"])) <= TIGHT * mt
        assert abs(Decimal(s["W_elec_pJ"]) - Decimal(s["W_elec_closed_pJ"])) <= TIGHT * mt
        for h, x in s["electrode_plus_supplied_charge_C"].items():
            scale = (abs(Decimal(s["electrode_C"][h])) + abs(Decimal(s["supplied_charge_C"][h]))
                     + Decimal("1e-12"))                     # the plates' charge scale, C
            assert abs(Decimal(x)) <= TIGHT * scale, (key, i, h)
        wsum = sum((Decimal(x) for x in s["W_carriers_by_route_pJ"].values()), Decimal(0))
        assert abs(wsum - Decimal(s["W_carriers_pJ"])) <= TIGHT * mt
        for p, x in hs["T3"]["N_plus_R_minus_N0_plus_R0"].items():
            assert abs(Decimal(x)) <= TIGHT * Decimal(dv["N0_plus_R0"][p])
        for x in hs["T3"]["dA_sum_by_cell_m2"].values():
            assert abs(Decimal(x)) <= TIGHT * Decimal("1e-9")
        for x in hs["T3"]["dC_sum_by_cell_F"].values():
            assert abs(Decimal(x)) <= TIGHT * Decimal("1e-11")


def test_two_routes_share_the_cleft_by_amount(computed):
    vals, des = computed
    (key,) = [k for k in vals["drives"] if k.startswith("two_routes_one_cleft")]
    s = vals["drives"][key]["half_steps"][0]["sums"]
    sh = {r: Decimal(x) for r, x in s["cleft_shares"].items()}
    assert abs(sh["uptake_0"] - Decimal(1) / 3) < TIGHT
    assert abs(sh["uptake_1"] - Decimal(2) / 3) < TIGHT
    for name in ("the whole cleft change on one route (this route takes all)",
                 "the whole cleft change on one route (this route takes none)"):
        assert des["plants"][name]["min_margin"] > 1e7


def test_units_closed_forms_and_orders(computed):
    vals, des = computed
    both = vals["T5"]["both_directions"]["populations"]
    for p, rec in both.items():
        assert rec["exact"]["quadrature_8x40_vs_16x40_rel"] < 1e-45
        assert rec["exact"]["richardson_vs_exact_rel"] < 1e-13
        pal = [float(x) for x in rec["palindrome"]["ratio"].values()]
        lie = [float(x) for x in rec["lie"]["ratio"].values()]
        assert all(3.9 < x < 4.05 for x in pal) and all(1.85 < x < 2.05 for x in lie), p
    plant = des["plants"]["the Lie split S_ret(h) S_rec(h)"]
    assert plant["caught"] and plant["palindrome_passes"]
    for row in vals["T5"]["cycle_operator"]["half_steps"]:
        for pop, c in row["closed"].items():
            assert c["N_rel_vs_stages"] < 1e-45, pop
    assert des["plants"]["e (or e_r) off by 1 part in 10^6"]["min_margin"] > 1e4


def test_compiled_closed_forms_and_T8(computed):
    vals, des = computed
    for block in [vals["T5"]["compiled_cycle"]] + list(vals["T5"]["batch"].values()):
        obs = block["observations"]
        A0 = Decimal(obs[0]["A_k"]) + Decimal(obs[0]["A_b"])
        for ob in obs:
            assert abs(Decimal(ob["A_k"]) + Decimal(ob["A_b"]) - A0) <= TIGHT * A0
            for pop, x in ob["N_plus_R"].items():
                assert abs(Decimal(x) - Decimal(obs[0]["N_plus_R"][pop])) < TIGHT * Decimal(x)
    for rec in vals["T8"]["populations"].values():
        if not rec["coupled"]:
            continue
        start = Decimal("0.5") * Decimal(1.0) * Decimal(3.261272165616906e-10)
        assert abs(Decimal(rec["start_m2"]) - start) <= TIGHT * start
        for ob in rec["observations"]:
            f, g = Decimal(ob["factor_m2"]), Decimal(ob["start_times_A_over_A0_m2"])
            assert abs(f - g) <= Decimal("1e-15") * g
    assert des["plants"]["T8 without the coupling"]["min_margin"] > 1e10


EXPECTED_WEAK = {
    "carriers without their valence (delta = t dq/F)": "declared worlds: both carriers +1",
    "the two transference numbers swapped": "declared worlds: t = 0.5 and 0.5",
    "T8 without the retrieval": "t = 0, before any retrieval",
}


def test_plants_have_their_registered_power(computed):
    _, des = computed
    for name, p in des["plants"].items():
        if "rows" not in p:
            continue
        if name in EXPECTED_WEAK:
            for w in p["weak_at"]:
                assert (w.startswith(("held_bath_cell", "cleft_cell", "two_routes"))
                        or w.endswith(" at 0 ms")), (name, w)
            strong = [r for r in p["rows"] if r["where"].startswith("stress")]
            if name != "T8 without the retrieval":
                assert strong and min(r["margin"] for r in strong) > design.MIN_MARGIN, name
        else:
            assert not p["weak_at"], (name, p["weak_at"][:3])
    # the floors are registered beside each T4 tolerance under both storage models, and flagged
    # exactly where they exceed it; the unchanged-potentials floor only on retrieval half-steps
    for m in ("absolute_storage", "increment_storage"):
        flagged = {(f["where"], f["check"]) for f in des["floor_flags"][m]}
        for where, f in des["floors_by_half_step"].items():
            for k, v in f[m].items():
                tol = {"T4_heat_rel": 1e-9}.get(k, 1e-12)
                assert ((where, k) in flagged) == (v > tol)
            if "T4_unchanged_of_max_phi" in f[m]:
                assert "T4_V_b_rel" in f[m]
    assert not des["floor_flags"]["increment_storage"]


def test_values_file_is_plain_json():
    json.loads(design.VALUES_FILE.read_text())
    json.loads(design.DESIGN_FILE.read_text())
