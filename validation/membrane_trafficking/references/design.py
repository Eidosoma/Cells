"""Writes FR-2's registered reference values and design (``designs/``) from the frozen inputs.

    python -m validation.membrane_trafficking.references.design            # write
    python -m validation.membrane_trafficking.references.design --check    # regenerate, compare

``membrane_trafficking_reference_values.json`` holds the references on every registered drive and
world: each half-step's stages, sums, closed forms, floors and state after (T3-T6), T5's cycle,
ladder and compiled closed forms, and T8's products. ``membrane_trafficking_reference_design.json``
holds each planted control's deviation and margin against the test's tolerance, the floors set
beside the tolerances, the zero-power list and the primary comparisons. Numbers are 50-digit
strings where they are references, floats where they are margins, ratios or floors. Generating
takes about a minute of one CPU.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

from validation.core_seams.references.exact import context, dec

from . import network as N
from . import trafficking as T
from . import units as U
from . import worlds as W

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "designs"
VALUES_FILE = DESIGNS / "membrane_trafficking_reference_values.json"
DESIGN_FILE = DESIGNS / "membrane_trafficking_reference_design.json"
INTERFACE_FILE = HERE / "interface" / "comparison_bands.json"
FLOOR_FACTOR = 10          # the comparison band: max(the test's tolerance, 10 × the floor)
MIN_MARGIN = 10.0          # a plant below this many bands is weak

# The tests' tolerances (§12, and §13's answers of 19 November 2026)
TOL = {
    "T4_unchanged_of_max_phi": 1e-12, "T4_V_rel": 1e-12, "T4_heat_rel": 1e-9,
    "T4_R1_rel": 1e-9,
    "T5_closed_rel": 1e-13, "T5_conserved_rel": 1e-14, "T5_compiled_rel": 1e-12,
    "T5_ratio_band": (3.5, 4.5), "T5_err16_max": 1e-4, "T5_lie_ratio_max": 2.5,
    "T6_residual_rel_of_max_term": 1e-9, "T6_residual_abs_pJ": 1e-18,
    "T6_carriers_rel": 1e-6, "T6_carriers_abs_of_max_term": 1e-15,
    "T6_electrode_work_rel": 1e-14, "T6_reservoir_work_rel": 1e-12, "T6_share_rel": 1e-3,
    "T8_rel": 1e-12, "T8_start_rel": 1e-14,
}


def D(x) -> str:
    """A reference number as a 50-significant-digit string."""
    x = dec(x)
    if x == 0:
        return "0"
    return format(x, ".49e")


def F(x) -> float:
    return float(dec(x))


def _rel(a, b):
    a, b = dec(a), dec(b)
    return float(abs(a - b) / abs(b)) if b != 0 else (0.0 if a == 0 else float("inf"))


def _strs(d):
    """Decimals (also nested, with tuple keys) to strings."""
    if isinstance(d, dict):
        return {("/".join(k) if isinstance(k, tuple) else k): _strs(v) for k, v in d.items()}
    if isinstance(d, (list, tuple)):
        return [_strs(v) for v in d]
    if isinstance(d, Decimal):
        return D(d)
    return d


# --------------------------------------------------------------------------------------------
# T3-T6: the operator-level drives, half-step by half-step
# --------------------------------------------------------------------------------------------

SUM_KEYS = ("dG_chem_pJ", "dU_view_pJ", "heat_dense_pJ", "heat_closed_pJ", "W_res_pJ",
            "W_res_closed_pJ", "W_elec_pJ", "W_elec_closed_pJ", "W_carriers_pJ")


def snapshot(st: T.State, phi: dict) -> dict:
    w = st.world
    return {"potentials_V": dict(phi),
            "patches": {p: {"area_m2": x["area_m2"], "capacitance_F": x["capacitance_F"]}
                        for p, x in w.patches.items()},
            "voltages_V": {p: w.voltage(phi, p) for p in w.patches},
            "amounts_fmol": {n: dict(a) for n, a in w.amounts.items()
                             if w.nodes[n]["kind"] == "free"},
            "units": dict(st.units), "records": dict(st.records),
            "energy_pJ": w.energy_J(phi) * T.PJ}


def stage_json(rep: dict) -> dict:
    keep = {k: rep[k] for k in ("direction",) + SUM_KEYS + ("identity_closed_pJ", "terms_scale_pJ",
                                                            "electrode_C", "electrode_closed_C",
                                                            "supplied_fmol", "moved_into_fmol",
                                                            "dG_by_node_pJ")}
    keep["routes"] = {rid: {k: v for k, v in r.items() if k not in ("from", "to")}
                      | {"from": r["from"], "to": r["to"]} for rid, r in rep["routes"].items()}
    keep["potentials_after_V"] = rep["potentials_after"]
    return keep


def half_step_sums(reps: list, held: list, valences: dict) -> dict:
    with context():
        s = {k: sum((r[k] for r in reps), Decimal(0)) for k in SUM_KEYS}
        s["electrode_C"] = {h: sum((r["electrode_C"][h] for r in reps), Decimal(0)) for h in held}
        s["electrode_closed_C"] = {h: sum((r["electrode_closed_C"][h] for r in reps), Decimal(0))
                                   for h in held}
        s["electrode_abs_C"] = {h: sum((abs(r["electrode_C"][h]) for r in reps), Decimal(0))
                                for h in held}
        sup, moved, heat_r, wc_r = {}, {}, {}, {}
        for r in reps:
            for h, x in r["supplied_fmol"].items():
                for sp, n in x.items():
                    sup.setdefault(h, {})[sp] = sup.get(h, {}).get(sp, Decimal(0)) + n
            for nd, x in r["moved_into_fmol"].items():
                for sp, n in x.items():
                    moved.setdefault(nd, {})[sp] = moved.get(nd, {}).get(sp, Decimal(0)) + n
            for rid, rr in r["routes"].items():
                heat_r[rid] = heat_r.get(rid, Decimal(0)) + rr["heat_share_pJ"]
                wc_r[rid] = wc_r.get(rid, Decimal(0)) + rr["W_carriers_pJ"]
        s["supplied_fmol"], s["moved_into_fmol"] = sup, moved
        s["heat_by_route_pJ"], s["W_carriers_by_route_pJ"] = heat_r, wc_r
        terms = [s["dG_chem_pJ"], s["dU_view_pJ"], s["heat_closed_pJ"], s["W_res_pJ"],
                 s["W_elec_closed_pJ"], s["W_carriers_pJ"]]
        s["residual_pJ"] = terms[0] + terms[1] + terms[2] - terms[3] - terms[4] - terms[5]
        s["max_term_pJ"] = max(abs(x) for x in terms)
        s["residual_band_pJ"] = (dec(TOL["T6_residual_rel_of_max_term"]) * s["max_term_pJ"]
                                 + dec(TOL["T6_residual_abs_pJ"]))
        # §13: electrode transfer = −F Σ z × supplied (they cancel), work at the bath's potential
        s["supplied_charge_C"] = {h: sum((N.CHARGE_PER_FMOL * valences[sp] * n
                                          for sp, n in sup.get(h, {}).items()), Decimal(0))
                                  for h in held}
        s["electrode_plus_supplied_charge_C"] = {h: s["electrode_C"][h] + s["supplied_charge_C"][h]
                                                 for h in held}
        return s


def heat_floor_rel(cf: dict, fl: dict, src: str, dst: str, U0, U1) -> Decimal:
    """An honest relative floor on a one-direction half-step's merge heat against its exact value:
    H = C_d dC (V_d − V_s)²/(2 (C_d + dC)) moves by 2 H δ(V_d − V_s)/|V_d − V_s| with the start
    voltages' floors, plus the rounding of the two capacitor energies if H is taken as their
    difference, plus a few roundings of the products."""
    with context():
        u = N.UNIT_ROUNDOFF
        H = dec(cf["heat_pJ"]) / T.PJ
        dV = abs(dec(cf["V_destination_start_V"]) - dec(cf["V_source_start_V"]))
        f = 2 * (fl["voltage_before"][src] + fl["voltage_before"][dst]) / dV
        f += u * N.K_OPS * (U0 + U1) / H + u * N.K_OPS
        return f


def run_drive(inp: dict, key: str, d: dict) -> dict:
    st = W.build(inp, d["world"])
    held = st.world.held_nodes()
    phi0 = st.world.solve()
    out = {"world": d["world"], "test": d["test"], "H_s": d["H"], "start": snapshot(st, phi0),
           "N0_plus_R0": {p: st.units[p] + sum((x for (r, q), x in st.records.items() if q == p),
                                               Decimal(0)) for p in st.units},
           "half_steps": []}
    for ret, rec in d["half_steps"]:
        w0 = st.world
        phi_b = w0.solve()
        st1, reps = T.half_step(st, ret, rec, d["H"])
        w1 = st1.world
        phi_a = w1.solve()
        changed = {n for n in w1.amounts if w1.amounts[n] != w0.amounts.get(n)}
        fls = {m: N.potential_floors(w0, w1, phi_b, phi_a, changed, m) for m in N.FLOOR_MODELS}
        sums = half_step_sums(reps, held, w0.valences)
        with context():
            max_phi = max(abs(x) for x in phi_b.values())
            hs = {"rates_m2_per_s": {"retrieval": ret, "recycling": rec},
                  "stages": [stage_json(r) for r in reps], "sums": sums,
                  "after": snapshot(st1, phi_a), "potential_change_V":
                  {n: phi_a[n] - phi_b[n] for n in phi_a}, "max_abs_potential_V": max_phi}
            # §2.2's closed forms over the whole half-step (one direction running)
            dirs = {r["direction"] for r in reps}
            route = st.routes[0]
            k, b = route["plasma_patch"], route["pool_patch"]
            cf = {}
            if len(st.routes) == 1 and dirs == {"retrieval"}:
                pk, pb = w0.patches[k], w0.patches[b]
                dA = sum((r["routes"][route["id"]]["dA_m2"] for r in reps), Decimal(0))
                dC = pk["capacitance_F"] * dA / pk["area_m2"]
                Vk, Vb = w0.voltage(phi_b, k), w0.voltage(phi_b, b)
                Cb, Ck = pb["capacitance_F"], pk["capacitance_F"]
                cf = {"kind": "retrieval", "dA_m2": dA, "dC_F": dC, "source": k,
                      "destination": b, "V_source_start_V": Vk, "V_destination_start_V": Vb,
                      "V_b_after_V": (Cb * Vb + dC * Vk) / (Cb + dC),
                      "heat_pJ": Cb * dC * (Vb - Vk) ** 2 / (2 * (Cb + dC)) * T.PJ,
                      "R1_shift_V": Vk * dC / (Ck - dC),
                      "R1_V_b_after_V": Cb * Vb / (Cb + dC)}
                o = pk["outside"]
                if w0.nodes[o]["kind"] == "held":
                    cf["electrode_C"] = {o: dC * Vk}
                r1 = T.planted_R1(st, {route["id"]: dA})
                cf["R1_potentials_V"] = r1
                cf["R1_potential_change_V"] = {n: r1[n] - phi_b[n] for n in r1}
                # the planted carriers without z (δ = t δq/F): the potentials it leaves
                cf["no_valence_potentials_V"] = _plant_no_valence(st, ret, rec, d["H"])
            elif len(st.routes) == 1 and dirs == {"recycling"}:
                pk, pb = w0.patches[k], w0.patches[b]
                dA = sum((r["routes"][route["id"]]["dA_m2"] for r in reps), Decimal(0))
                dC = pb["capacitance_F"] * dA / pb["area_m2"]
                Vk, Vb = w0.voltage(phi_b, k), w0.voltage(phi_b, b)
                Ck = pk["capacitance_F"]
                cf = {"kind": "recycling", "dA_m2": dA, "dC_F": dC, "source": b,
                      "destination": k, "V_source_start_V": Vb, "V_destination_start_V": Vk,
                      "V_k_after_V": (Ck * Vk + dC * Vb) / (Ck + dC),
                      "heat_pJ": Ck * dC * (Vk - Vb) ** 2 / (2 * (Ck + dC)) * T.PJ}
                o = pk["outside"]
                if w0.nodes[o]["kind"] == "held":
                    cf["electrode_C"] = {o: -dC * Vb}
            hs["closed_forms"] = cf
            # the planted swapped transference numbers: the carriers' work it books
            hs["plant_swapped_t_W_carriers_pJ"] = _plant_swapped_t(st, ret, rec, d["H"])
            hs["floors"] = {"units_rel": len(reps) * N.K_OPS * N.UNIT_ROUNDOFF}
            for m, fl in fls.items():
                hf = (heat_floor_rel(cf, fl, cf["source"], cf["destination"], w0.energy_J(phi_b),
                                     w1.energy_J(phi_a)) if cf else None)
                hs["floors"][m] = {"potential_change_V": fl["change"],
                                   "potential_after_V": fl["after"],
                                   "voltage_before_V": fl["voltage_before"],
                                   "voltage_after_V": fl["voltage_after"], "heat_rel": hf}
            hs["floors"]["T6"] = _t6_floors(w0, w1, phi_b, phi_a, sums)
            # T3 per half-step
            hs["T3"] = {"N_plus_R_minus_N0_plus_R0": {
                p: st1.units[p] + sum((x for (r, q), x in st1.records.items() if q == p),
                                      Decimal(0)) - out["N0_plus_R0"][p] for p in st1.units},
                "dA_sum_by_cell_m2": _cell_sums(w0, w1, "area_m2"),
                "dC_sum_by_cell_F": _cell_sums(w0, w1, "capacitance_F")}
        out["half_steps"].append(hs)
        st = st1
    return out


def _cell_sums(w0: N.World, w1: N.World, key: str) -> dict:
    out = {}
    with context():
        for pid, p in w1.patches.items():
            c = p["inside"]
            out[c] = out.get(c, Decimal(0)) + p[key] - w0.patches[pid][key]
    return out


def _t6_floors(w0: N.World, w1: N.World, phi_b: dict, phi_a: dict, s: dict) -> dict:
    """Floors on T6's residual and carriers' work (pJ) under two models of ΔG_chem: a difference
    of two float64 totals (``naive_difference``), or a change computed stably, to a few roundings
    of its own size (``stable_change``; §4 calls the adapter's change exact). The capacitor terms
    are a difference of energies in both."""
    with context():
        u = N.UNIT_ROUNDOFF * N.K_OPS
        naive = _naive_dG_floor(w0, w1)
        held_ln = abs(dec(s["dG_chem_pJ"]) - dec(s["W_carriers_pJ"]))
        energies = u * (w0.energy_J(phi_b) + w1.energy_J(phi_a)) * T.PJ
        others = u * (abs(s["heat_closed_pJ"]) + abs(s["W_res_pJ"]) + abs(s["W_elec_closed_pJ"]))
        stable_dG = u * abs(s["dG_chem_pJ"])
        return {"naive_difference": {"residual_pJ": naive + energies + others + u * held_ln,
                                     "W_carriers_pJ": naive + u * held_ln},
                "stable_change": {"residual_pJ": stable_dG + energies + others + u * held_ln,
                                  "W_carriers_pJ": stable_dG + u * held_ln}}


def _naive_dG_floor(w0: N.World, w1: N.World) -> Decimal:
    """u K_OPS RT Σ |n (ln(n/V) − 1)| over the touched free nodes (pJ): the rounding of a float64
    ΔG_chem taken as a difference of two totals (an 'exact' adapter can do better)."""
    with context():
        RT = N.GAS_CONSTANT * w0.T_K
        tot = Decimal(0)
        for n in w1.free_nodes():
            if w1.amounts.get(n) == w0.amounts.get(n):
                continue
            for world in (w0, w1):
                V = world.nodes[n]["volume_pL"]
                for _s, x in world.amounts.get(n, {}).items():
                    if x > 0:
                        tot += abs(x * ((x / V).ln() - 1))
        return N.UNIT_ROUNDOFF * N.K_OPS * RT * tot * T.FMOL_J_TO_PJ


def _plant_no_valence(st: T.State, ret: dict, rec: dict, H) -> dict:
    """The half-step with every carrier's δ_s = t_s δq/CHARGE_PER_FMOL, z dropped (planted); the
    potentials it leaves, solved with the true valences."""
    st1, _reps = T.half_step(st, ret, rec, H, drop_valence=True)
    return st1.world.solve()


def _plant_swapped_t(st: T.State, ret: dict, rec: dict, H) -> Decimal:
    """The half-step's carriers' work with each route's two transference numbers swapped
    (planted); the charge carried is unchanged, so only the amounts and the work see it."""
    routes = []
    for r in st.routes:
        r2 = dict(r)
        ts = list(r["carriers"].items())
        if len(ts) == 2:
            r2["carriers"] = {ts[0][0]: ts[1][1], ts[1][0]: ts[0][1]}
        routes.append(r2)
    planted = st.copy()
    planted.routes = routes
    _st1, reps = T.half_step(planted, ret, rec, H)
    with context():
        return sum((r["W_carriers_pJ"] for r in reps), Decimal(0))


# --------------------------------------------------------------------------------------------
# T5: the cycle, the ladder and the compiled closed forms
# --------------------------------------------------------------------------------------------

def t5_values(inp: dict, drives: dict) -> dict:
    out = {}
    b = W.t5_both(inp)
    ladder = [8, 16, 32, 64]
    both = {"test": b["test"], "rates_m2_per_s": {"r1": b["r1"], "r2": b["r2"]},
            "duration_s": b["duration"], "A_k0_m2": b["A_k0"], "A_b0_m2": b["A_b0"],
            "ladder": ladder, "populations": {}}
    for p, q in b["populations"].items():
        args = (q["N0"], q["R0"], b["A_k0"], b["A_b0"], b["r1"], b["r2"], q["e"], q["e_r"])
        rec = {"e": q["e"], "e_r": q["e_r"], "N0": q["N0"], "R0": q["R0"]}
        with context():
            ex8 = U.two_direction_exact(*args, b["duration"], 8, 40)
            ex16 = U.two_direction_exact(*args, b["duration"], 16, 40)
            rich = U.richardson(*args, b["duration"], 512)
            rec["exact"] = {"N": ex16["N"], "R": ex16["R"],
                            "quadrature_8x40_vs_16x40_rel": _rel(ex8["N"], ex16["N"]),
                            "richardson_512_1024_N": rich["richardson"],
                            "richardson_vs_exact_rel": _rel(rich["richardson"], ex16["N"])}
            for scheme in ("palindrome", "lie"):
                o = U.orders(*args, b["duration"], ladder, scheme)
                rec[scheme] = {
                    "N": {str(n): r["N"] for n, r in zip(ladder, o["runs"], strict=True)},
                    "R": {str(n): r["R"] for n, r in zip(ladder, o["runs"], strict=True)},
                    "rel_error": {str(n): e / ex16["N"] for n, e in
                                  zip(ladder, o["errors"], strict=True)},
                    "ratio": {f"{ladder[i]}/{ladder[i + 1]}": x for i, x in enumerate(o["ratios"])}}
        both["populations"][p] = rec
    out["both_directions"] = both
    # the operator-level cycle: per half-step closed forms, and the planted e(1 + 1e-6)
    key = [k for k in drives if "cycle_follows" in k][0]
    d = drives[key]
    st = W.build(inp, d["world"])
    route = st.routes[0]
    e = route["enrichment"]
    er = route["recycling_enrichment"]
    rows = []
    with context():
        Np = dict(st.units)
        Rp = {p: Decimal(0) for p in Np}
        for ret, rec_ in d["half_steps"]:
            w0 = st.world
            Ak = w0.patches[route["plasma_patch"]]["area_m2"]
            Ab = w0.patches[route["pool_patch"]]["area_m2"]
            st1, reps = T.half_step(st, ret, rec_, d["H"])
            row = {"N": dict(st1.units), "R": {p: st1.records[(route["id"], p)] for p in Np},
                   "A_k_m2": st1.world.patches[route["plasma_patch"]]["area_m2"],
                   "A_b_m2": st1.world.patches[route["pool_patch"]]["area_m2"],
                   "closed": {}, "plant_e_1e-6_rel": {}, "plant_e_r_1e-6_rel": {}}
            dA = sum((r["routes"][route["id"]]["dA_m2"] for r in reps), Decimal(0))
            for p in Np:
                if reps[0]["direction"] == "retrieval":
                    Nn = U.retrieve(Np[p], Ak, dA, e[p])
                    Np_planted = U.retrieve(Np[p], Ak, dA, e[p] * (1 + Decimal("1e-6")))
                    Rp[p] += Np[p] - Nn
                    row["plant_e_1e-6_rel"][p] = abs(Np_planted - Nn) / Nn
                    Np[p] = Nn
                else:
                    Rn = U.recycle(Rp[p], Ab, dA, er[p])
                    Rn_planted = U.recycle(Rp[p], Ab, dA, er[p] * (1 + Decimal("1e-6")))
                    row["plant_e_r_1e-6_rel"][p] = abs(Rn_planted - Rn) / Rn
                    Np[p] += Rp[p] - Rn
                    Rp[p] = Rn
                row["closed"][p] = {"N": Np[p], "R": Rp[p],
                                    "N_rel_vs_stages": _rel(st1.units[p], Np[p])}
            rows.append(row)
            st = st1
    out["cycle_operator"] = {"test": d["test"], "half_steps": rows}
    # compiled: the cycle world and T7's batch
    w = inp["worlds"]["cycle"]
    r = w["routes"][0]
    sch = w["schedules"][0]
    times = [W.v(t) for t in w["clock"]["observation_times"]]
    e_c = {p: W.v(x) for p, x in r["retrieval_enrichment"].items()}
    er_c = {p: W.v(x) for p, x in r["recycling_enrichment"].items()}
    N0 = {p["id"]: W.v(p["N0"]) for p in w["populations"]}
    A_k0 = W._area(w, r["source_patch"])
    A_b0 = W._area(w, r["destination"]["patch"])
    C_k0 = [W.v(p["capacitance"]) for p in w["patches"] if p["id"] == r["source_patch"]][0]
    C_b0 = [W.v(p["capacitance"]) for p in w["patches"] if p["id"] == r["destination"]["patch"]][0]

    def schedule_of(s):
        knots = sorted({W.v(x["time"]) for x in s["retrieval"]}
                       | {W.v(x["time"]) for x in s["recycling"]})

        def at(lst, t):
            val = Decimal(0)
            for x in lst:
                if W.v(x["time"]) <= t:
                    val = W.v(x["rate"])
            return val
        return [(t, at(s["retrieval"], t), at(s["recycling"], t)) for t in knots]

    def closed(s):
        res = U.cycle_closed_forms(N0, e_c, er_c, A_k0, A_b0, schedule_of(s), times)
        with context():
            for row in res:
                row["C_k_F"] = C_k0 * row["A_k"] / A_k0
                row["C_b_F"] = C_b0 * row["A_b"] / A_b0
                row["N_plus_R"] = {p: row["N"][p] + row["R"][p] for p in N0}
        return res

    out["compiled_cycle"] = {"schedule": schedule_of(sch), "observations": closed(sch)}
    out["batch"] = {k: {"schedule": schedule_of(s[0]), "observations": closed(s[0])}
                    for k, s in w["cycle_batch_schedules"].items()}
    return out


# --------------------------------------------------------------------------------------------
# T8: the composed sheet's products
# --------------------------------------------------------------------------------------------

def t8_values(inp: dict) -> dict:
    w = inp["worlds"]["t8_sheet"]
    s_frozen = W.v(w["coupling"]["states"][0]["initial"])
    avail = {}
    for a in w["channel_availability"]:
        avail[a["channel"]] = [(W.v(x["time"]), W.v(x["availability"])) for x in a["schedule"]]
    pops = {p["id"]: p for p in w["populations"]}
    coupled = set(w["coupling"]["couplings"][0]["target"]["ids"])
    sched = {x["route"]: x for x in w["schedules"]}
    dt = W.v(w["clock"]["dt"])
    times = [W.v(t) for t in w["clock"]["observation_times"]]
    out = {"coupling_F": s_frozen, "populations": {}}
    with context():
        for r in w["routes"]:
            patch = r["source_patch"]
            A0 = W._area(w, patch)
            rate = W.v(sched[r["id"]]["retrieval"][0]["rate"])
            if len(sched[r["id"]]["retrieval"]) != 1 or any(W.v(x["rate"]) != 0
                                                             for x in sched[r["id"]]["recycling"]):
                raise ValueError("T8: a constant retrieval and no recycling expected")
            for pid, e in r["retrieval_enrichment"].items():
                p = pops[pid]
                e = W.v(e)
                N0 = W.v(p["N0"])
                rho = W.v(p["reference_density"])
                ab = W.v(p["abundance"])
                av0 = avail[pid][0][1]
                Fp = s_frozen if pid in coupled else Decimal(1)
                rec = {"patch": patch, "e": e, "coupled": pid in coupled, "N0": N0,
                       "start_m2": Fp * av0 * ab * A0,
                       "start_superseded_units": Fp * av0 * N0,
                       "observations": []}
                for i, t in enumerate(times):
                    t_run = dt * i
                    if abs(t_run - t) > Decimal("1e-15"):
                        raise ValueError("T8: observations off the dt grid")
                    A = A0 - rate * t_run
                    Nt = N0 * (e * (A / A0).ln()).exp()
                    abund = Nt / (A * rho)
                    av = [x for (tt, x) in avail[pid] if tt <= t][-1]
                    rec["observations"].append({
                        "t_s": t, "A_over_A0": A / A0, "N": Nt, "abundance": abund,
                        "factor_m2": Fp * av * abund * A,
                        "start_times_A_over_A0_m2": rec["start_m2"] * A / A0,
                        "plant_no_coupling_m2": av * abund * A,
                        "plant_no_retrieval_m2": Fp * av * ab * A0})
                out["populations"][pid] = rec
    return out


# --------------------------------------------------------------------------------------------
# The design: plants, floors, zero power
# --------------------------------------------------------------------------------------------

def _band(tol, floor):
    return max(float(tol), FLOOR_FACTOR * float(floor))


def plants_and_floors(vals: dict) -> dict:
    plants, floors = {}, {}
    weak = []

    def add(name, check, rows):
        """rows: [(where, deviation, band)]; the margin is deviation / band."""
        ms = [(w_, dv, bd, (dv / bd) if bd > 0 else float("inf")) for w_, dv, bd in rows]
        if not ms:
            return
        best = max(ms, key=lambda x: x[3])
        worst = min(ms, key=lambda x: x[3])
        plants[name] = {"check": check, "cases": len(ms), "max_margin": best[3], "at": best[0],
                        "min_margin": worst[3], "min_at": worst[0],
                        "weak_at": [x[0] for x in ms if x[3] < MIN_MARGIN],
                        "rows": [{"where": x[0], "deviation": x[1], "band": x[2], "margin": x[3]}
                                 for x in ms]}
        weak.extend(f"{name} @ {x[0]}" for x in ms if x[3] < MIN_MARGIN)

    r1, r1_free, novalence, heat_sign, elec_sign, res_no_phi, wc_sign = [], [], [], [], [], [], []
    share_all0, share_all1, swapped = [], [], []
    for key, dv in vals["drives"].items():
        for i, hs in enumerate(dv["half_steps"]):
            where = f"{key} #{i + 1}"
            cf = hs["closed_forms"]
            maxphi = dec(hs["max_abs_potential_V"])
            b = dv["pool_patch"]
            k = dv["plasma_patch"]
            pools = set(dv["pool_nodes"])
            # floors beside T4's tolerances, under both storage models: every potential but the
            # pools' (retrieval only), V_b' or V_k', V_b kept (recycling), and the heat
            floors[where] = {}
            for m in N.FLOOR_MODELS:
                fl = hs["floors"][m]
                f = {}
                if cf.get("kind") == "retrieval":
                    f["T4_unchanged_of_max_phi"] = F(max(
                        (dec(fl["potential_change_V"][n]) for n in fl["potential_change_V"]
                         if n not in pools), default=Decimal(0)) / maxphi)
                    Vb = dec(hs["after"]["voltages_V"][b])
                    f["T4_V_b_rel"] = F(dec(fl["voltage_after_V"][b]) / abs(Vb))
                    f["T4_heat_rel"] = F(fl["heat_rel"])
                elif cf.get("kind") == "recycling":
                    Vb = dec(hs["after"]["voltages_V"][b])
                    Vk = dec(hs["after"]["voltages_V"][k])
                    f["T4_V_b_unchanged_rel"] = F(
                        (dec(fl["voltage_after_V"][b]) + dec(fl["voltage_before_V"][b])) / abs(Vb))
                    f["T4_V_k_rel"] = F(dec(fl["voltage_after_V"][k]) / abs(Vk))
                    f["T4_heat_rel"] = F(fl["heat_rel"])
                floors[where][m] = f
            s = hs["sums"]
            mt = dec(s["max_term_pJ"])
            t6 = hs["floors"]["T6"]
            floors[where]["T6"] = {mm: {"residual_of_band": F(dec(x["residual_pJ"])
                                                              / dec(s["residual_band_pJ"])),
                                        "W_carriers_pJ": F(x["W_carriers_pJ"])}
                                   for mm, x in t6.items()}
            if cf.get("kind") == "retrieval":
                f_unch = floors[where]["absolute_storage"]["T4_unchanged_of_max_phi"]
                band_unch = _band(TOL["T4_unchanged_of_max_phi"], f_unch) * float(maxphi)
                owner = dv["owner"]
                o = dv["outside"]
                if dv["outside_held"]:
                    r1.append((where, abs(F(cf["R1_potential_change_V"][owner])), band_unch))
                else:
                    r1_free.append((where, abs(F(cf["R1_potential_change_V"][o])), band_unch))
                nv = cf["no_valence_potentials_V"]
                pa = hs["after"]["potentials_V"]
                dev = max(abs(F(dec(nv[n]) - dec(pa[n]))) for n in pa if n not in pools)
                novalence.append((where, dev, band_unch))
            # T6's bands: the test's, widened to 10 × the naive-difference floor (conservative)
            band = max(F(s["residual_band_pJ"]),
                       FLOOR_FACTOR * F(t6["naive_difference"]["residual_pJ"]))
            if dec(s["heat_closed_pJ"]) != 0:
                heat_sign.append((where, abs(2 * F(s["heat_closed_pJ"])), band))
            if dec(s["W_elec_closed_pJ"]) != 0:
                elec_sign.append((where, abs(2 * F(s["W_elec_closed_pJ"])), band))
            phi_part = dec(s["W_res_pJ"]) - dec(s["W_res_without_phi_pJ"])
            if phi_part != 0:
                res_no_phi.append((where, abs(F(phi_part)), band))
            if dec(s["W_carriers_pJ"]) != 0:
                wc_sign.append((where, abs(2 * F(s["W_carriers_pJ"])), band))
            wc = dec(s["W_carriers_pJ"])
            wfloor = FLOOR_FACTOR * F(t6["naive_difference"]["W_carriers_pJ"])
            bnd_wc = max(TOL["T6_carriers_rel"] * abs(float(wc)),
                         TOL["T6_carriers_abs_of_max_term"] * float(mt), wfloor)
            swapped.append((where, abs(F(dec(hs["plant_swapped_t_W_carriers_pJ"]) - wc)), bnd_wc))
            if len(s["W_carriers_by_route_pJ"]) > 1:
                cl = s["cleft_dG_pJ"]
                shares = s["cleft_shares"]
                for rid, sh in shares.items():
                    wr = dec(s["W_carriers_by_route_pJ"][rid])
                    bnd = max(TOL["T6_carriers_rel"] * abs(float(wr)),
                              TOL["T6_carriers_abs_of_max_term"] * float(mt), wfloor)
                    dev_all_here = abs(F((1 - dec(sh)) * dec(cl)))
                    dev_none_here = abs(F(dec(sh) * dec(cl)))
                    share_all0.append((f"{where} {rid} takes all", dev_all_here, bnd))
                    share_all1.append((f"{where} {rid} takes none", dev_none_here, bnd))
    add("R1 at a held bath: the owner's potential moves by V_k dC/(C_k - dC)",
        "T4 every potential but the pool's unchanged (<= 1e-12 of max|phi|)", r1)
    add("R1 at a free node: the outside node's potential moves by -V_k dC/(C_k - dC)",
        "T4 every potential but the pool's unchanged", r1_free)
    add("carriers without their valence (delta = t dq/F)",
        "T4 every potential but the pool's unchanged", novalence)
    add("a merge heat of the wrong sign", "T6 the residual within 1e-9 max|term| + 1e-18 pJ",
        heat_sign)
    add("the electrode work with the wrong sign", "T6 the residual", elec_sign)
    add("the reservoir work without z F phi_b", "T6 the residual", res_no_phi)
    add("the carriers' work with the wrong sign", "T6 the residual", wc_sign)
    add("the two transference numbers swapped",
        "T6 the carriers' work (relative 1e-6, absolute 1e-15 max|term|)", swapped)
    add("the whole cleft change on one route (this route takes all)",
        "T6 each route's carriers' work (relative 1e-6, absolute 1e-15 max|term|)", share_all0)
    add("the whole cleft change on one route (this route takes none)",
        "T6 each route's carriers' work", share_all1)
    # T3's dropped unit, at every drive's start
    rows = []
    for key, dv in vals["drives"].items():
        for p, m in dv["N0_plus_R0"].items():
            rows.append((f"{key} {p}", 1.0 / F(m), TOL["T5_conserved_rel"]))
    add("a unit dropped from the record",
        "T3 N + R = N0 + R0 per population (relative 1e-14, T5's conservation tolerance)", rows)
    # T5
    rows_e = []
    for i, hs in enumerate(vals["T5"]["cycle_operator"]["half_steps"]):
        for p, x in list(hs["plant_e_1e-6_rel"].items()) + list(hs["plant_e_r_1e-6_rel"].items()):
            rows_e.append((f"half-step {i + 1} {p}", F(x), TOL["T5_closed_rel"]))
    add("e (or e_r) off by 1 part in 10^6", "T5 the closed forms per half-step (relative 1e-13)",
        rows_e)
    kir = vals["T5"]["both_directions"]["populations"]["kir_0"]
    lie_ratio = F(kir["lie"]["ratio"]["8/16"])
    pal_ratio = F(kir["palindrome"]["ratio"]["8/16"])
    plants["the Lie split S_ret(h) S_rec(h)"] = {
        "check": "T5: err(8)/err(16) of Kir's N within (3.5, 4.5); the Lie plant below 2.5",
        "palindrome_ratio_8_16": pal_ratio, "lie_ratio_8_16": lie_ratio,
        "palindrome_err16_rel": F(kir["palindrome"]["rel_error"]["16"]),
        "caught": lie_ratio < TOL["T5_lie_ratio_max"] and not (3.5 < lie_ratio < 4.5),
        "palindrome_passes": 3.5 < pal_ratio < 4.5 and F(kir["palindrome"]["rel_error"]["16"])
        < TOL["T5_err16_max"]}
    # T8
    rows_c, rows_r = [], []
    for pid, rec in vals["T8"]["populations"].items():
        if not rec["coupled"]:
            continue
        for ob in rec["observations"]:
            f = dec(ob["factor_m2"])
            at = f"{pid} at {round(F(ob['t_s']) * 1e3)} ms"
            rows_c.append((at, _rel(ob["plant_no_coupling_m2"], f), TOL["T8_rel"]))
            rows_r.append((at, _rel(ob["plant_no_retrieval_m2"], f), TOL["T8_rel"]))
    add("T8 without the coupling", "T8 the factor = start x A(t)/A0 (relative 1e-12)", rows_c)
    add("T8 without the retrieval", "T8 the factor = start x A(t)/A0", rows_r)
    return {"plants": plants, "floors_by_half_step": floors, "weak": weak}


def floor_flags(floors: dict) -> dict:
    """Where a floor exceeds the test's tolerance, model by model: T4's under each storage model,
    T6's (the residual and the carriers' work) under each ΔG model. A flag is conditional on its
    model; neither model is known to be the engine's."""
    tol = {"T4_unchanged_of_max_phi": TOL["T4_unchanged_of_max_phi"], "T4_V_b_rel": TOL["T4_V_rel"],
           "T4_V_k_rel": TOL["T4_V_rel"], "T4_V_b_unchanged_rel": TOL["T4_V_rel"],
           "T4_heat_rel": TOL["T4_heat_rel"]}
    out = {m: [] for m in N.FLOOR_MODELS}
    out.update({"T6 " + m: [] for m in ("naive_difference", "stable_change")})
    for where, f in floors.items():
        for m in N.FLOOR_MODELS:
            for k, v in f[m].items():
                if v > tol[k]:
                    out[m].append({"where": where, "check": k, "floor": v, "tolerance": tol[k],
                                   "band": FLOOR_FACTOR * v})
        for m, x in f["T6"].items():
            if x["residual_of_band"] > 1:
                out["T6 " + m].append({"where": where, "check": "T6 residual",
                                       "floor_over_band": x["residual_of_band"]})
    return out


def floor_flags_carriers(vals: dict) -> dict:
    """Where the carriers' work's floor exceeds the test's band (relative 1e-6, absolute 1e-15
    max|term|), per ΔG model, for the total and for each route."""
    out = {"naive_difference": [], "stable_change": []}
    for key, dv in vals["drives"].items():
        for i, hs in enumerate(dv["half_steps"]):
            s = hs["sums"]
            mt = F(s["max_term_pJ"])
            for m in out:
                fw = F(hs["floors"]["T6"][m]["W_carriers_pJ"])
                for who, w in [("total", F(s["W_carriers_pJ"]))] + [
                        (r, F(x)) for r, x in s["W_carriers_by_route_pJ"].items()]:
                    band = max(TOL["T6_carriers_rel"] * abs(w),
                               TOL["T6_carriers_abs_of_max_term"] * mt)
                    if fw > band:
                        out[m].append({"where": f"{key} #{i + 1}", "who": who, "floor": fw,
                                       "band": band})
    return out


ZERO_POWER = [
    {"what": "the potentials and the heat in the compiled worlds (cycle, t8_sheet)",
     "why": "they depend on the pumps, leaks and channels, which these references do not model; "
            "only the units, areas and capacitances are referenced there"},
    {"what": "T1's refusals, T2's idleness and T7's restart and batch equalities",
     "why": "rules and bitwise equalities, with no number to reference (T7's batch worlds get "
            "T5's closed forms only)"},
    {"what": "a dropped valence or swapped transference numbers, in the declared worlds",
     "why": "both declared carriers are +1 at t = 0.5; the stress worlds (K 0.75, M at z = -1 "
            "0.25) carry those plants"},
    {"what": "the per-species against the per-total sharing of a free node's free energy",
     "why": "both routes on the declared shared cleft move K and Na in one ratio (1:2), so the "
            "two rules agree; the stress worlds keep one route per node"},
    {"what": "the electrode and reservoir work's phi_b parts at a bath held at 0 V",
     "why": "zero there; held_bath_cell (20 mV) and the stress worlds carry them"},
    {"what": "recycling into a patch on a free node",
     "why": "only the dense route exists for its heat; no registered drive does it"},
    {"what": "per-route heats among several routes",
     "why": "no test compares them (§13); they are registered as the §4 share for completeness"},
]


PRIMARY = {
    "dated": "2026-11-19, from design statement 1 §13 (written 04:31 UTC), before any engine "
             "comparison",
    "T3": "N + R = N0 + R0 per population (every drive's half-steps), per-cell sums of dA and dC "
          "zero; the planted dropped unit deviates by 1 unit",
    "T4": "after one half-step: every potential but the pool's against the start (1e-12 of "
          "max|phi|), V_b (retrieval) or V_k (recycling) against the closed form (relative "
          "1e-12, here with the floor: max(1e-12, 10 x floor)), the single route's booked heat "
          "against C_b dC (V_b - V_k)^2/(2 (C_b + dC)) (relative 1e-9); R1's owner shift V_k "
          "dC/(C_k - dC) (relative 1e-9)",
    "T5": "the operator-level cycle's N and R per half-step against the closed forms (relative "
          "1e-13), N + R (1e-14); both directions: Kir's N only, relative error at 4 ms, n = 8 "
          "and 16: 3.5 < err(8)/err(16) < 4.5 and err(16) < 1e-4, the Lie plant below 2.5; here "
          "also the scheme's own N at n = 8 and 16 to float64 floors; compiled: the closed forms "
          "at each observation (1e-12)",
    "T6": "per half-step: |dG_chem + dU_view + H - W_res - W_elec - W_carriers| <= 1e-9 "
          "max|term| + 1e-18 pJ; the carriers' work against the independent value (relative "
          "1e-6, absolute 1e-15 max|term|); a held bath (retrieval): electrode transfer = -F "
          "sum z supplied, electrode work = phi_b x transfer (1e-14), reservoir work = 1e-3 sum "
          "mu supplied (1e-12); two routes: each route's work its pool's change plus its "
          "|amount| share of the cleft's (1e-6), shares 1:2 (1e-3)",
    "T8": "per Kir population: F x availability x abundance x area (m^2, abundance = N/(A rho)) "
          "= start x A(t)/A0 (relative 1e-12), start = 1/2 x availability x abundance x A0 "
          "(relative 1e-14)",
}


# --------------------------------------------------------------------------------------------

def compute() -> tuple:
    """Every value and the design, all at the references' 60 digits."""
    with context():
        return _compute()


def _compute() -> tuple:
    inp = W.load()
    drives = W.drives(inp)
    vals = {"about": "FR-2 v1's code-blind reference values (design statement 1 §12-§13)",
            "inputs": "reference_inputs.json", "drives": {}}
    for key, d in drives.items():
        dv = run_drive(inp, key, d)
        st = W.build(inp, d["world"])
        route = st.routes[0]
        dv["pool_patch"] = route["pool_patch"]
        dv["plasma_patch"] = route["plasma_patch"]
        dv["pool_node"] = route["pool_node"]
        dv["pool_nodes"] = [r["pool_node"] for r in st.routes]
        dv["owner"] = st.world.patches[route["plasma_patch"]]["inside"]
        dv["outside"] = st.world.patches[route["plasma_patch"]]["outside"]
        dv["outside_held"] = st.world.nodes[dv["outside"]]["kind"] == "held"
        _extras(dv, st)
        vals["drives"][key] = _strs(dv)
    vals["T5"] = _strs(t5_values(inp, drives))
    vals["T8"] = _strs(t8_values(inp))
    pf = plants_and_floors(vals)
    design = {"about": "FR-2 v1's code-blind references: plants, floors, zero power, primary "
                       "comparisons",
              "tolerances": {k: list(v) if isinstance(v, tuple) else v for k, v in TOL.items()},
              "band_rule": f"max(the test's tolerance, {FLOOR_FACTOR} x the floor)",
              "min_margin": MIN_MARGIN, "plants": pf["plants"], "weak": pf["weak"],
              "floors_by_half_step": pf["floors_by_half_step"],
              "floor_flags": floor_flags(pf["floors_by_half_step"]),
              "floor_flags_carriers": floor_flags_carriers(vals),
              "zero_power": ZERO_POWER, "primary_comparisons": PRIMARY}
    return vals, design


def _extras(dv: dict, st: T.State) -> None:
    """Per half-step: the reservoir work without z F phi_b, and the shared cleft's ΔG and the
    routes' |amount| shares (for the T6 plants)."""
    for hs in dv["half_steps"]:
        s = hs["sums"]
        with context():
            RT = N.GAS_CONSTANT * st.world.T_K
            noz = Decimal(0)
            for h, sup in s["supplied_fmol"].items():
                for sp, n in sup.items():
                    noz += n * RT * dec(st.world.nodes[h]["reference_mM"][sp]).ln()
            s["W_res_without_phi_pJ"] = noz * T.FMOL_J_TO_PJ
            shared = {}
            for stg in hs["stages"]:
                for rid, r in stg["routes"].items():
                    frm = r["from"]
                    if st.world.nodes[frm]["kind"] == "free" and frm != r.get("to"):
                        shared.setdefault(frm, set()).add(rid)
            shared = {n: rids for n, rids in shared.items() if len(rids) > 1}
            if shared:
                (node, rids), = shared.items()
                rids = sorted(rids)
                cl = sum((sum(stg["dG_by_node_pJ"][node].values(), Decimal(0))
                          for stg in hs["stages"]), Decimal(0))
                moved = {rid: sum((abs(x) for stg in hs["stages"]
                                   for x in stg["routes"][rid]["carriers_fmol"].values()),
                                  Decimal(0)) for rid in rids}
                tot = sum(moved.values(), Decimal(0))
                s["cleft_dG_pJ"] = cl
                s["cleft_shares"] = {rid: m / tot for rid, m in moved.items()}


def dumps(o) -> str:
    return json.dumps(o, indent=1, sort_keys=True, allow_nan=True) + "\n"


def interface_text(text_v: str, text_d: str) -> str:
    """The comparison bands (``bands.py``), built from the values and design exactly as written."""
    from . import bands
    return dumps(bands.build(json.loads(text_v), json.loads(text_d)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args(argv)
    vals, design = compute()
    text_v, text_d = dumps(vals), dumps(design)
    text_i = interface_text(text_v, text_d)
    if a.check:
        ok = (VALUES_FILE.read_text() == text_v and DESIGN_FILE.read_text() == text_d
              and INTERFACE_FILE.read_text() == text_i)
        print("design --check:", "identical" if ok else "DIFFERS")
        return 0 if ok else 1
    DESIGNS.mkdir(exist_ok=True)
    VALUES_FILE.write_text(text_v)
    DESIGN_FILE.write_text(text_d)
    INTERFACE_FILE.parent.mkdir(exist_ok=True)
    INTERFACE_FILE.write_text(text_i)
    print(f"wrote {VALUES_FILE.name}, {DESIGN_FILE.name} and {INTERFACE_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
