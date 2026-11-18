"""Writes the core-seams references' registered design and values (``designs/``) from the inputs.

    python -m validation.core_seams.references.design            # write
    python -m validation.core_seams.references.design --check    # regenerate and compare

``reference_inputs.json`` (written by ``worlds.py``) holds the laws, states, systems and nodes.
``core_seams_reference_values.json`` holds the references on every registered state, one record
per line. ``core_seams_reference_design.json`` holds the claims, each planted control's power (its
largest deviation over the registered states, where it is largest, and the states where it is
weak), the zero-power cases and the readings. All of it is written before any engine output for
seams A and C (CORE_SEAMS_DESIGN §19 item 7). Generating takes about a minute of one CPU.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import sys
from pathlib import Path

from . import api, exact, worlds
from . import cycles as C
from . import diagrams as D

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "designs"
DESIGN_FILE = DESIGNS / "core_seams_reference_design.json"
VALUES_FILE = DESIGNS / "core_seams_reference_values.json"
MIN_MARGIN = 10.0
BAND_EPS = 64.0          # "a few tens of eps of the terms' absolute sum" (§19 item 2), for verdicts
NEAR_EQ = 1e-3           # |ΔG/RT| below which a one-way plant is expected to be weak
FLOOR_OPS = 8.0          # a few operations' rounding beside ΔG/RT's terms, in eps


def floor_J(mode) -> float:
    """The honest absolute floor on a mode's J (fmol/s): (J⁺ + J⁻) × (ΔG/RT's terms + a few) eps.

    An honest float64 kernel's ΔG/RT is off by about its terms' absolute sum times eps, so its J is
    off by about (J⁺ + J⁻) times that; near equilibrium no relative floor exists."""
    return mode["J_scale"] * (mode["dG_RT_terms_abs"] + FLOOR_OPS) * exact.EPS


def rel_floor(terms) -> float:
    """The honest relative floor on a one-way flux or a slope at a state."""
    return (terms + FLOOR_OPS) * exact.EPS


def git_blob_id(path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def _ok(x):
    return x is not None and isinstance(x, (int, float)) and math.isfinite(x)


def _rel(a, b):
    if b == 0:
        return None
    return abs(a - b) / abs(b)


def summarise(tags, devs, weak=MIN_MARGIN) -> dict:
    """A plant's power over the registered states, each deviation in floors: its largest margin
    and where, its smallest, and the states where it is weak (below ``weak`` floors).

    Amendment F4: a state whose deviation is undefined (None, or not finite: a zero reference) is
    weak, listed in ``weak_at`` and counted, never dropped."""
    pairs = [(t, d) for t, d in zip(tags, devs, strict=True) if _ok(d)]
    undefined = [t for t, d in zip(tags, devs, strict=True) if not _ok(d)]
    if not pairs:
        return {"max": None, "states": len(tags), "undefined": len(undefined),
                "weak_at": list(undefined)}
    tmax, dmax = max(pairs, key=lambda p: p[1])
    tmin, dmin = min(pairs, key=lambda p: p[1])
    return {"max": dmax, "at": tmax, "min": dmin, "min_at": tmin,
            "weak_at": [t for t, d in zip(tags, devs, strict=True)
                        if not _ok(d) or d < weak],
            "states": len(tags), "undefined": len(undefined)}


# --------------------------------------------------------------------------------------------
# Seam A
# --------------------------------------------------------------------------------------------

def _laws(inputs):
    A = inputs["seam_a"]
    return A, A["registry"], {law["id"]: law for law in A["laws"]}


def wegscheider_verdict(law, reg, law_states) -> tuple:
    """The reference's verdict on a diagram law (§16: the full set of Hill cycles, each with an
    identically zero residual) and the per-cycle residuals for the values file."""
    comp = D.cycle_set_complete(law)
    w = api.wegscheider(law, reg, law_states)
    reasons = []
    # amendment A2 (Q7): each simple cycle declared once, each with a consistent direction
    keys = [tuple(sorted(eid for eid, _d in c["edges"])) for c in law["cycles"]]
    if len(keys) != len(set(keys)):
        reasons.append("a cycle declared more than once")
    for c in law["cycles"]:
        try:
            D.check_traversal(law, c)
        except ValueError as e:
            reasons.append(f"an inconsistent direction ({e})")
    if not comp["complete"]:
        reasons.append(f"the declared cycles are not the diagram's full set (missing "
                       f"{comp['missing']})")
        if D.basis_shares_an_edge(law):
            reasons.append("a declared basis whose cycles share an edge")
    for cid, row in w.items():
        cyc = next(c for c in law["cycles"] if c["id"] == cid)
        if not row["structurally_zero"]:
            reasons.append(f"cycle {cid}: the residual varies with "
                           f"{sorted(row['b']) + (['psi'] if row['b_psi'] else [])}")
        terms = 0.0
        for eid, _d in cyc["edges"]:
            e = next(x for x in law["edges"] if x["id"] == eid)
            terms += abs(math.log(e["fwd"]["k0_per_s"])) + abs(math.log(e["bwd"]["k0_per_s"]))
        for s, _e, n in cyc["nu"]:
            terms += abs(n * reg["species"][s]["mu0_RT"])
        row["r0_over_terms_eps"] = abs(row["r0"]) / (terms * exact.EPS)
        if row["r0_over_terms_eps"] > BAND_EPS:
            reasons.append(f"cycle {cid}: a constant residual {row['r0']:.3g}")
    return {"verdict": "refused" if reasons else "admitted", "reasons": reasons,
            "cycle_set": comp}, w


def layout_plants(law, pop, reg, st, vol) -> dict:
    """Errors only the general layout can make, and n ± 1, the fuel frame, the work's sign and a
    dropped voltage term: each one's relative deviation of J, the rows, heat and work."""
    ref = api.cycle_state(law, pop, reg, st, vol, with_slopes=False)
    n = law["parameters"]["n"]
    moved = "H" if law["law_id"].startswith("cells.proton") else "Z"

    def run(lw=law, pp=pop, rg=reg, s=st):
        return api.cycle_state(lw, pp, rg, s, vol, with_slopes=False)

    RT = float(exact.RT_J_per_mol(reg["temperature_K"]))
    q = ref["modes"]["cyc"]
    fJ = floor_J(q)
    J = abs(q["J"])
    rel = rel_floor(q["dG_RT_terms_abs"])
    g_held = abs(ref["work_pJ_per_s"]) * 1000 / (J * RT) if J > 0 else 0.0
    f_heat = (fJ * abs(q["dG_RT"]) + J * rel) * RT / 1000
    f_work = (fJ * g_held + J * rel) * RT / 1000

    def dev(r):
        """Each deviation over its honest floor (J, rows, heat, work)."""
        rows = [abs(r["rows_fmol_per_s"].get(k, 0.0) - v) / (n * fJ)
                for k, v in ref["rows_fmol_per_s"].items()]
        return {"J": abs(r["modes"]["cyc"]["J"] - q["J"]) / fJ,
                "rows": max(rows) if rows else None,
                "heat": abs(r["heat_pJ_per_s"] - ref["heat_pJ_per_s"]) / f_heat,
                "work": abs(r["work_pJ_per_s"] - ref["work_pJ_per_s"]) / f_work}

    out = {}
    held_b = [["ATP", "b"], ["ADP", "b"], ["Pi", "b"]]
    out["orientation_swapped"] = dev(run(pp=dict(pop, orientation={"N": "b"}, held_rows=held_b)))
    lw = copy.deepcopy(law)
    for row in lw["modes"][0]["nu"]:
        if row[0] in ("ATP", "ADP", "Pi"):
            row[1] = "P"
    for t in lw["modes"][0]["saturation"]:
        if t["species"] == "ATP":
            t["end"] = "P"
    out["fuel_end_misplaced"] = dev(run(lw=lw, pp=dict(pop, held_rows=held_b)))
    twice = dict(pop, capacity_fmol_per_s=2 * pop["capacity_fmol_per_s"])
    out["capacity_twice"] = dev(run(pp=twice))
    b_row = ref["rows_fmol_per_s"][f"{moved}@b"]
    out["rows_scattered"] = {"rows": abs(b_row) / (n * fJ)}
    for k in (n + 1, n - 1):
        if k < 1:
            continue
        lw = copy.deepcopy(law)
        m = lw["modes"][0]
        m["nu"] = [[s, e, (-k if v < 0 else k) if s == moved else v] for s, e, v in m["nu"]]
        for t in m["saturation"]:
            if t["species"] == moved:
                t["hill"] = k
        out[f"n_{'plus' if k > n else 'minus'}_one"] = dev(run(lw=lw))
    rg = copy.deepcopy(reg)
    for s in ("ATP", "ADP", "Pi"):
        rg["species"][s]["mu0_RT"] += math.log(1000.0)
    out["fuel_frame_1mM"] = dev(run(rg=rg))
    out["work_sign"] = {"work": 2 * abs(ref["work_pJ_per_s"]) / f_work}
    s0 = copy.deepcopy(st)
    s0["phi_V"]["a"] = s0["phi_V"]["b"]
    out["voltage_dropped"] = {"J": abs(run(s=s0)["modes"]["cyc"]["J"] - q["J"]) / fJ}
    return out


def finite_fuel_plants(law, pop, reg, st, vol) -> dict:
    """Amendment 1: the finite-fuel population's stored rate and moved fuel rows. Each deviation
    over its honest floor (J, rows, stored rate, work)."""
    ref = api.cycle_state(law, pop, reg, st, vol, with_slopes=False)
    RT = float(exact.RT_J_per_mol(reg["temperature_K"]))
    q = ref["modes"]["cyc"]
    fJ, J = floor_J(q), abs(q["J"])
    rel = rel_floor(q["dG_RT_terms_abs"])
    ln_c0 = math.log(reg["standard_concentration_mM"])
    nu = law["modes"][0]["nu"]
    std = [n * (reg["species"][sp]["mu0_RT"] - ln_c0) for sp, _e, n in nu]
    f_stored = (fJ * abs(sum(std)) + J * rel * sum(abs(x) for x in std)) * RT / 1000
    f_work = (fJ * q["dG_RT_terms_abs"] + J * rel) * RT / 1000
    sigma_nu = sum(n for _sp, _e, n in nu)

    def run(lw=law, pp=pop):
        return api.cycle_state(lw, pp, reg, st, vol, with_slopes=False)

    def dev(r):
        keys = set(ref["rows_fmol_per_s"]) | set(r["rows_fmol_per_s"])
        rows = [abs(r["rows_fmol_per_s"].get(k, 0.0) -
                    ref["rows_fmol_per_s"].get(k, 0.0)) / fJ for k in keys]
        return {"J": abs(r["modes"]["cyc"]["J"] - q["J"]) / fJ, "rows": max(rows),
                "stored": abs(r["stored_standard_pJ_per_s"] - ref["stored_standard_pJ_per_s"]) /
                f_stored,
                "work": abs(r["work_pJ_per_s"] - ref["work_pJ_per_s"]) / f_work}

    out = {}
    stored = ref["stored_standard_pJ_per_s"]
    # the 1 M frame: the standard part without its −(Σ ν) RT ln c° (FR-4 note §17.2's trap)
    out["stored_frame_1M"] = {"stored": abs(q["J"] * sigma_nu * ln_c0 * RT / 1000) / f_stored}
    out["stored_dropped"] = {"stored": abs(stored) / f_stored}
    out["stored_sign"] = {"stored": 2 * abs(stored) / f_stored}
    out["held_instead"] = dev(run(pp=dict(pop, held_rows=[["ATP", "a"], ["ADP", "a"],
                                                          ["Pi", "a"]])))
    lw = copy.deepcopy(law)
    for row in lw["modes"][0]["nu"]:
        if row[0] in ("ATP", "ADP", "Pi"):
            row[1] = "P"
    for t in lw["modes"][0]["saturation"]:
        if t["species"] == "ATP":
            t["end"] = "P"
    out["fuel_moved_at_b"] = dev(run(lw=lw))
    return out


def orientation_plants(law, pop, reg, st, vol) -> dict:
    """Amendment 1: the N = b population's orientation, ignored in each of four ways. Each deviation
    over its honest floor (J, rows, charge a → b, conductance)."""
    ref = api.cycle_state(law, pop, reg, st, vol, with_slopes=True)
    modes = ref["modes"]
    fJ = {m: floor_J(v) for m, v in modes.items()}
    nq = {c["id"]: C.parse_checks(c["nu"], reg)["n_q"] for c in law["cycles"]}
    f_rows = max(fJ.values()) * 3            # |ν| ≤ 3 in D2
    f_charge = sum(abs(nq[m]) * fJ[m] for m in modes)
    G = ref["slopes"]["conductance_pS"]
    f_G = abs(G) * rel_floor(max(v["dG_RT_terms_abs"] for v in modes.values()))

    def jdev(r):
        return max(abs(r["modes"][m]["J"] - modes[m]["J"]) / fJ[m] for m in modes)

    def rdev(rows):
        keys = set(ref["rows_fmol_per_s"]) | set(rows)
        return max(abs(rows.get(k, 0.0) - ref["rows_fmol_per_s"].get(k, 0.0)) / f_rows
                   for k in keys)

    out = {}
    r = api.cycle_state(law, dict(pop, orientation={"N": "a"}), reg, st, vol, with_slopes=False)
    out["read_as_N_a"] = {"J": jdev(r), "rows": rdev(r["rows_fmol_per_s"]),
                          "charge": abs(r["charge_a_to_b_fmol_per_s"] -
                                        ref["charge_a_to_b_fmol_per_s"]) / f_charge}
    s2 = copy.deepcopy(st)
    s2["phi_V"]["a"], s2["phi_V"]["b"] = st["phi_V"]["b"], st["phi_V"]["a"]
    r = api.cycle_state(law, pop, reg, s2, vol, with_slopes=False)
    out["voltage_orientation_ignored"] = {"J": jdev(r),
                                          "charge": abs(r["charge_a_to_b_fmol_per_s"] -
                                                        ref["charge_a_to_b_fmol_per_s"]) / f_charge}
    out["charge_sign"] = {"charge": 2 * abs(ref["charge_a_to_b_fmol_per_s"]) / f_charge}
    swapped = {(k.split("@")[0] + "@" + ("a" if k.endswith("@b") else "b")): v
               for k, v in ref["rows_fmol_per_s"].items()}
    out["rows_at_swapped_ends"] = {"rows": rdev(swapped)}
    out["conductance_sign"] = {"conductance": 2 * abs(G) / f_G if f_G > 0 else None}
    return out


def slope_plants(law, pop, reg, rec, vol) -> dict:
    """Planted slopes' relative deviations from the exact conductance and dJ/dV."""
    G = rec["slopes"]["conductance_pS"]
    out = {}
    F = float(exact.FARADAY)
    RT = float(exact.RT_J_per_mol(reg["temperature_K"]))
    k = pop["capacity_fmol_per_s"] * pop.get("availability", 1.0)
    if law["kind"] == "factored":
        m = law["modes"][0]
        nq = C.parse_checks(m["nu"], reg)["n_q"]
        S, g = rec["modes"]["cyc"]["S"], rec["modes"]["cyc"]["dG_RT"]
        if nq != 0:
            out["static_head_formula"] = _rel(nq * nq * F * F * k * S / RT * 1e-3, G)
            out["n_q_not_squared"] = _rel(abs(nq) * F * F * k * S * math.exp(g) / RT * 1e-3, abs(G))
    else:
        worst = None
        sign = 1.0 if pop["orientation"]["N"] == "a" else -1.0     # φ_N − φ_P = ±V
        for c in law["cycles"]:
            nq = C.parse_checks(c["nu"], reg)["n_q"]
            row = rec["modes"][c["id"]]
            frozen = sign * row["J_plus"] * math.exp(row["dG_RT"]) * nq * F / RT
            r = _rel(frozen, rec["slopes"]["dJ_dV"][c["id"]])
            if _ok(r):
                worst = r if worst is None else max(worst, r)
        out["S_frozen"] = worst
    if G != 0:
        out["half_RT"] = 0.5
    if rec["slopes"]["material"]:
        out["wrong_volume"] = abs(vol["a"] / vol["b"] - 1.0)
    rf = rel_floor(max(m["dG_RT_terms_abs"] for m in rec["modes"].values()))
    return {k: (v / rf if _ok(v) else None) for k, v in out.items()}


def seam_a(inputs) -> tuple:
    """(values, diagnostics): the references per state, and what the design summarises."""
    A, reg, laws = _laws(inputs)
    vol = A["volumes_pL"]
    val = {"laws": {}, "wegscheider": {}, "parse": {}}
    dia = {"methods": {}, "slope_check": {}, "oneway": {}, "basis": {}, "standin": {},
           "layout": {}, "slopes": {}, "weg": {}}
    for law in A["laws"]:
        pop = A["populations"][law["id"]]
        sts = A["states"][law["id"]]
        recs = [api.cycle_state(law, pop, reg, st, vol, with_slopes=law["kind"] != "net_flow")
                for st in sts]
        val["laws"][law["id"]] = {"population": pop, "states": recs}
        val["parse"][law["id"]] = {m["id"]: C.parse_checks(m["nu"], reg) for m in C.modes(law)}
        admitted = not law["id"].startswith("planted") and law["kind"] != "net_flow"
        if law["kind"] == "diagram":
            lsts = api.law_states_of(pop, sts)
            verdict, w = wegscheider_verdict(law, reg, lsts)
            val["wegscheider"][law["id"]] = _weg_values(verdict, w)
            dia["weg"][law["id"]] = w
            dia["methods"][law["id"]] = [api.method_agreement(law, pop, reg, st) for st in sts]
            dia["oneway"][law["id"]] = [api.oneway_plants(law, pop, reg, st) for st in sts]
            if law["id"] in ("d2_slip_exchanger", "d4_parallel_branches"):
                dia["basis"][law["id"]] = [api.basis_signs(law, pop, reg, st) for st in sts]
        if admitted:
            dia["standin"][law["id"]] = [api.guard_standin(law, pop, reg, st) for st in sts]
            dia["slope_check"][law["id"]] = [api.slope_agreement(law, pop, reg, st, vol)
                                             for st in sts]
            dia["slopes"][law["id"]] = [slope_plants(law, pop, reg, r, vol) for r in recs]
        if law["id"] == "ff_neutral_n1":
            dia["finite_fuel"] = [finite_fuel_plants(law, pop, reg, st, vol) for st in sts]
        elif law["id"] == "d2_slip_exchanger_Nb":
            dia["orientation"] = [orientation_plants(law, pop, reg, st, vol) for st in sts]
        elif law["kind"] == "factored" and admitted:
            dia["layout"][law["id"]] = [layout_plants(law, pop, reg, st, vol) for st in sts]
    for law in A["planted_laws"]:
        base = A["plant_states"][law["id"]]
        lsts = api.law_states_of(A["populations"][base], A["states"][base])
        verdict, w = wegscheider_verdict(law, reg, lsts)
        val["wegscheider"][law["id"]] = _weg_values(verdict, w)
        dia["weg"][law["id"]] = w
    # amendment A2: the engine's stated band on every cycle, and its guard at every state
    dia["engine_band"] = {law["id"]: {c["id"]: api.engine_wegscheider_band(law, c, reg)
                                      for c in law["cycles"]}
                          for law in A["laws"] + A["planted_laws"] if law["kind"] == "diagram"}
    dia["engine_guard"] = {law["id"]: [api.engine_guard(law, A["populations"][law["id"]], reg, st)
                                       for st in A["states"][law["id"]]]
                           for law in A["laws"]}
    for plant in A["parse_plants"]:
        r = reg if plant["registry"] == "A" else _registry_c_as_rows(inputs)
        val["parse"][plant["id"]] = C.parse_checks(plant["nu"], r)
    return val, dia


def _weg_values(verdict, w) -> dict:
    keep = ("r0", "b", "b_psi", "b_psi_exact", "n_q", "structurally_zero", "r0_over_terms_eps",
            "residual_at_states")
    return dict(verdict, cycles={cid: {k: row[k] for k in keep} for cid, row in w.items()})


def _registry_c_as_rows(inputs) -> dict:
    """Seam C's registry seen as rows: ligands with their valences, binders at base valences."""
    rc = inputs["seam_c"]["registry"]
    sp = {k: dict(v) for k, v in rc["species"].items()}
    for b, v in rc["binders"].items():
        sp[b] = {"valence": v["base_valence"], "mu0_RT": v["forms"][0]["mu0_RT"]}
    return {"species": sp, "moieties": rc["moieties"]}


# --------------------------------------------------------------------------------------------
# Seam C
# --------------------------------------------------------------------------------------------

def seam_c(inputs) -> tuple:
    Cc = inputs["seam_c"]
    reg = Cc["registry"]
    val = {"systems": {}, "p1": {}, "movers": {}, "parse": {}}
    dia = {"systems": {}}
    for name, sysd in Cc["systems"].items():
        spec = {"ligands": sysd["ligands"], "binders": sysd["binders"]}
        V = sysd["volume_pL"]
        rows, drows = [], []
        for k, st in enumerate(Cc["manufactured_states"][name]):
            extra = k < 2 or not st["tag"].startswith("random")
            rec, sp, sy = api.binding_state(spec, reg, st["totals"], V, extra_checks=extra)
            with exact.context():
                man = max(abs((sp["x_mM"][L] / exact.dec(st["free_mM"][L])).ln())
                          for L in sy.ligands)
            rec = dict({"tag": st["tag"]}, **rec)
            rec["manufactured_dln"] = exact.fl(man)
            d = {"tag": st["tag"],
                 "plants": api.binding_plants(spec, reg, st["totals"], V, sysd["designated"]),
                 "gradient_plant": api.gradient_plant(spec, reg, st["totals"], V),
                 "nonminimum_plant": api.nonminimum_plant(spec, reg, st["totals"], V,
                                                          sysd["designated"])}
            B_of = next(B for B in sysd["binders"] if any(f["id"] == sysd["designated"]
                                                          for f in reg["binders"][B]["forms"]))
            d["charge_plant_fmol_e"] = rec["forms_mM"][B_of][sysd["designated"]] * V
            if "parts" in sysd:
                worst = 0.0
                for part in sysd["parts"]:
                    tot = {"ligands_fmol": {L: st["totals"]["ligands_fmol"][L]
                                            for L in part["ligands"]},
                           "binders_fmol": {B: st["totals"]["binders_fmol"][B]
                                            for B in part["binders"]}}
                    r2, _sp2, _sy2 = api.binding_state(part, reg, tot, V)
                    for L in part["ligands"]:
                        worst = max(worst, abs(r2["x_mM"][L] / rec["x_mM"][L] - 1.0))
                d["joint_vs_separate_rel"] = worst
            rows.append(rec)
            drows.append(d)
        val["systems"][name] = {"spec": spec, "volume_pL": V, "states": rows,
                                "pairs": booked_pairs(rows)}
        dia["systems"][name] = drows
    for name, node in Cc["p1_nodes"].items():
        val["p1"][name] = api.p1(node, reg)
    for mv in Cc["movers"]:
        val["movers"][mv["id"]] = api.mover_verdict(mv, reg)
    if "envelope" in Cc:
        val["envelope"] = envelope_values(Cc)
    if "validity" in Cc:
        val["validity"] = validity_values(Cc)
    val["parse"]["form_valences"] = {
        B: {f["id"]: int(b["base_valence"]) + sum(int(n) * int(reg["species"][L]["valence"])
                                                  for L, n in f.get("counts", {}).items())
            for f in b["forms"]} for B, b in reg["binders"].items()}
    val["parse"]["planted_declared_valence"] = {
        "form": "nuc4_Mg", "declared": -1,
        "derived": val["parse"]["form_valences"]["nuc4"]["nuc4_Mg"], "verdict": "refused"}
    return val, dia


def validity_values(Cc) -> dict:
    """Amendment C4: the joint margin t* at every registered state (exact, and by the LP), and the
    planted validity states with each solver's outcome."""
    from . import binding as Bd
    from . import primal as Pr
    reg = Cc["registry"]

    def margin(spec, TL, TB):
        sy = Bd.System(spec, reg)
        jm = Bd.joint_margin(sy, TL, TB)
        return sy, {"t_star_fmol": float(jm["t_star"]), "t_star_exact": str(jm["t_star"]),
                    "lambda_star": [str(x) for x in jm["lambda_star"]],
                    "per_ligand_fmol": {L: float(v) for L, v in jm["per_ligand"].items()},
                    "valid": jm["valid"], "per_ligand_valid": jm["per_ligand_valid"],
                    "lp_t_star_fmol": Bd.joint_margin_lp(sy, TL, TB)}

    out = {"systems": {}, "planted": {}}
    for name, sysd in Cc["systems"].items():
        spec = {"ligands": sysd["ligands"], "binders": sysd["binders"]}
        rows = []
        for st in Cc["manufactured_states"][name]:
            _sy, m = margin(spec, st["totals"]["ligands_fmol"], st["totals"]["binders_fmol"])
            rows.append(dict({"tag": st["tag"]}, **m))
        out["systems"][name] = rows
    for tag, ps in Cc["validity"]["planted"].items():
        sysd = Cc["systems"][ps["system"]]
        spec = {"ligands": sysd["ligands"], "binders": sysd["binders"]}
        TL, TB = ps["totals"]["ligands_fmol"], ps["totals"]["binders_fmol"]
        sy, m = margin(spec, TL, TB)
        V = sysd["volume_pL"]
        for route, fn in (("dual", lambda sy=sy, TL=TL, TB=TB, V=V: Bd.solve(sy, TL, TB, V)),
                          ("primal", lambda spec=spec, TL=TL, TB=TB, V=V:
                           Pr.solve_primal(spec, reg, TL, TB, V))):
            try:
                r = fn()
                m[route] = {"outcome": "solved",
                            "x_mM": {L: exact.fl(v) for L, v in r["x_mM"].items()}}
            except (ValueError, RuntimeError) as e:
                m[route] = {"outcome": "refused", "reason": str(e)}
        if m["dual"]["outcome"] == "solved" and m["primal"]["outcome"] == "solved":
            m["dual_vs_primal_max_rel"] = max(abs(m["dual"]["x_mM"][L] / m["primal"]["x_mM"][L]
                                                  - 1) for L in sysd["ligands"])
        out["planted"][tag] = dict(m, system=ps["system"])
    return out


def envelope_values(Cc) -> dict:
    """Amendment C3: every envelope case, its plants, and the reachability verdicts."""
    from . import envelope as En
    reg = Cc["registry"]
    env = Cc["envelope"]
    out = {"cases": {}, "reachability": {}}
    for cid, case in env["cases"].items():
        r = En.run_case(case, reg)
        lag = r["first_order_dln"]
        plants = {}
        # a k_on that ignores the ligand (each binder's first ligand's for all), and swapped k_on
        kon = {(B, L): k for B, L, k in case["kon_per_mM_per_s"]}
        if len(case["ligands"]) > 1:
            first = {B: kon[(B, case["ligands"][0])] for B in case["binders"]}
            same = copy.deepcopy(case)
            same["kon_per_mM_per_s"] = [[B, L, first[B]] for B, L, _k in case["kon_per_mM_per_s"]]
            swap = copy.deepcopy(case)
            ligs = case["ligands"]
            swap["kon_per_mM_per_s"] = [[B, L, kon[(B, ligs[1 - ligs.index(L)])]]
                                        if len(ligs) == 2 else [B, L, k]
                                        for B, L, k in case["kon_per_mM_per_s"]]
            for name, variant in (("kon_ignores_the_ligand", same), ("kon_swapped", swap)):
                rv = En.run_case(variant, reg, kinetic=False)["first_order_dln"]
                plants[name] = {L: (abs(rv[L] / lag[L] - 1) if lag[L] != 0 else None)
                                for L in case["ligands"]}
        plants["per_step_minimum"] = {
            L: (abs(lag[L]) / abs(r["per_step_estimate_dln"]["min_over_all_steps"][L])
                if r["per_step_estimate_dln"]["min_over_all_steps"][L] != 0 else None)
            for L in case["ligands"]}
        r["plants"] = plants
        rates = r["slowest_network_rates_per_s"]
        lam_max = max(st["lambda_per_s"] for st in r["steps"])
        r["first_order_floor_rel"] = 8 * exact.EPS * lam_max / rates[0]
        last = r["kinetic"]["rows"][-1]
        r["kinetic_vs_first_order_rel"] = {
            L: (abs(last["lag_dln"][L] / last["first_order_dln"][L] - 1)
                if last["first_order_dln"][L] != 0 else None) for L in case["ligands"]}
        out["cases"][cid] = r
    for B in reg["binders"]:
        lig = sorted({L for f in reg["binders"][B]["forms"] for L in f.get("counts", {})})
        kon = {(B, L): 1.0 for L in lig}
        try:
            En.Network({"ligands": lig, "binders": [B]}, reg, kon, 1.0)
            out["reachability"][B] = {"verdict": "admitted"}
        except ValueError as e:
            out["reachability"][B] = {"verdict": "refused", "reason": str(e)}
    preg = copy.deepcopy(reg)
    preg["binders"].update(env["planted_unreachable_binders"])
    for B in env["planted_unreachable_binders"]:
        try:
            En.Network({"ligands": ["H"], "binders": [B]}, preg, {(B, "H"): 1.0}, 1.0)
            out["reachability"][B] = {"verdict": "admitted", "planted": True}
        except ValueError as e:
            out["reachability"][B] = {"verdict": "refused", "reason": str(e), "planted": True}
    return out


def booked_pairs(rows) -> list:
    """Amendment C1: the three booked-term plants on consecutive registered states (k, k + 1) of
    one system. Each plant's deviation of the booked change from ΔE_c (pJ):
    - G* booked whole: Σ_r ΔT_r μ°′_r;
    - B4's formula carried to moved binders: Σ_B ΔT_B μ°′_B (against S_c in B4's split);
    - S_c alone with @3's ideal terms masked: Σ_r Δ ideal_r (None where a total is ≤ 0).

    The floor is the rounding of the difference: 8 eps of both states' terms."""
    out = []
    for k in range(len(rows) - 1):
        a, b = rows[k]["booked_term"], rows[k + 1]["booked_term"]
        binders = [r for r in a["standard_parts_pJ"] if r in rows[k]["forms_mM"]]
        whole = abs(b["standard_total_pJ"] - a["standard_total_pJ"])
        b4 = abs(sum(b["standard_parts_pJ"][B] - a["standard_parts_pJ"][B] for B in binders))
        masked = (abs(b["ideal_total_pJ"] - a["ideal_total_pJ"])
                  if a["ideal_total_pJ"] is not None and b["ideal_total_pJ"] is not None
                  else None)
        floor = 8 * exact.EPS * (a["terms_abs_pJ"] + b["terms_abs_pJ"])
        out.append({"pair": [k, k + 1], "tags": [rows[k]["tag"], rows[k + 1]["tag"]],
                    "dE_c_pJ": b["E_c_pJ"] - a["E_c_pJ"],
                    "dS_c_pJ": (b["S_c_pJ"] - a["S_c_pJ"]) if a["S_c_pJ"] is not None and
                    b["S_c_pJ"] is not None else None,
                    "floor_pJ": floor,
                    "plants_pJ": {"G_star_booked_whole": whole,
                                  "B4_formula_on_moved_binders": b4,
                                  "S_c_alone_ideal_masked": masked}})
    return out


# --------------------------------------------------------------------------------------------
# The design: claims, power, zero power and readings
# --------------------------------------------------------------------------------------------

def power_a(inputs, va, da) -> dict:
    A, reg, laws = _laws(inputs)
    RT = float(exact.RT_J_per_mol(reg["temperature_K"]))
    power = {}

    # A1: sign and zero, and the diagrams' own backward fluxes against the contract's
    a1 = {}
    for lid, rec in va["laws"].items():
        if laws[lid]["kind"] == "net_flow":
            continue
        sts = rec["states"]
        jdg = [max(s["modes"][m]["J"] * s["modes"][m]["dG_RT"] for m in s["modes"]) for s in sts]
        row = {"max_J_dG_RT": max(jdg), "at": sts[jdg.index(max(jdg))]["tag"]}
        if laws[lid]["kind"] == "diagram":
            # amendment F4: no pair is filtered; a zero backward flux is a zero case, which
            # agrees only when the diagram's own flux is zero too
            logs, zeros, mismatched = [], 0, 0
            for s_ in sts:
                for m in s_["modes"]:
                    jm, jd = s_["modes"][m]["J_minus"], s_["modes"][m]["J_minus_diagram"]
                    if jm == 0 or jd == 0:
                        zeros += 1
                        mismatched += int(jm != jd)
                    else:
                        logs.append(abs(math.log(jd / jm)))
            row["max_abs_ln_diagram_over_contract_backward"] = max(logs)
            row["backward_pairs"] = len(logs) + zeros
            row["backward_zero_cases"] = zeros
            row["backward_zero_mismatches"] = mismatched
        a1[lid] = row
    neg = va["laws"]["planted_negative_S_n1"]["states"]
    a1["planted_negative_S_n1"]["states_with_S_below_zero"] = [
        s["tag"] for s in neg if s["modes"]["cyc"]["S"] < 0]
    a1["planted_negative_S_n1"]["min_J_dG_RT_there"] = min(
        s["modes"]["cyc"]["J"] * s["modes"]["cyc"]["dG_RT"] for s in neg
        if s["modes"]["cyc"]["S"] < 0)
    # over the guard's allowance there: J ΔG/RT against BAND_EPS eps of (J⁺ + J⁻) × ΔG's terms
    a1["planted_negative_S_n1"]["min_over_allowance_there"] = min(
        s["modes"]["cyc"]["J"] * s["modes"]["cyc"]["dG_RT"] /
        (BAND_EPS * exact.EPS * s["modes"]["cyc"]["J_scale"] * s["modes"]["cyc"]["dG_RT_terms_abs"])
        for s in neg if s["modes"]["cyc"]["S"] < 0)
    power["A1_sign_and_zero"] = a1

    # A2: Wegscheider (and the generic states' affine independence in ln a and ψ)
    import numpy as np
    generic = {}
    for lid in A["generic_states"]:
        law, pop = laws[lid], A["populations"][lid]
        keys = sorted({(s, e) for c in law["cycles"] for s, e, _n in c["nu"]} |
                      {(s, e) for ed in law["edges"] for side in ("fwd", "bwd")
                       for s, e, _o in ed[side].get("orders", [])})
        rows = []
        for st in A["states"][lid][:A["generic_states"][lid]]:
            ls = C.law_state(pop, st)
            rows.append([1.0] + [math.log(ls["c_mM"][e][s] / 1000.0) for s, e in keys] +
                        [ls["phi_V"]["N"] - ls["phi_V"]["P"]])
        generic[lid] = {"variables": [f"{s}@{e}" for s, e in keys] + ["psi", "constant"],
                        "rank": int(np.linalg.matrix_rank(np.array(rows))),
                        "states": len(rows)}
    weg = {"generic_sets": generic}
    for lid, w in da["weg"].items():
        base = A["plant_states"].get(lid, lid)
        tags = [s["tag"] for s in A["states"][base]]
        unit = tags.index("unit_activity_zero_voltage")
        ng = A["generic_states"][base]
        cyc = {}
        for cid, c in w.items():
            rel = c["residual_over_terms_eps"]
            others = [(t, x) for i, (t, x) in enumerate(zip(tags, rel, strict=True)) if i != unit]
            cyc[cid] = {"structurally_zero": c["structurally_zero"], "b": c["b"],
                        "b_psi": c["b_psi"], "r0": c["r0"],
                        "residual_eps": summarise([t for t, _x in others], [x for _t, x in others],
                                                  weak=BAND_EPS * MIN_MARGIN),
                        "min_residual_eps_over_generic": min(rel[:ng]),
                        "residual_eps_at_unit_state": rel[unit],
                        "standin_max_eps": max(max(c["standin_sum_of_logs_eps"]),
                                               max(c["standin_log_of_ratio_eps"])),
                        "r0_over_terms_eps": c["r0_over_terms_eps"]}
        weg[lid] = {"verdict": va["wegscheider"][lid]["verdict"],
                    "reasons": va["wegscheider"][lid]["reasons"], "cycles": cyc}
    power["A2_wegscheider"] = weg

    # amendment A2: the engine's band (B, B_ψ, R0 against B_W), and Q7's rule, against the
    # references' verdicts; the declared doubles' own residual's place inside B_W
    verdicts = {k: v["verdict"] for k, v in va["wegscheider"].items()}
    reasons = {k: v["reasons"] for k, v in va["wegscheider"].items()}
    eb = {}
    for lid, cyc in da["engine_band"].items():
        q7 = not any(r.startswith(("the declared cycles", "a declared basis", "a cycle declared",
                                   "an inconsistent")) for r in reasons[lid])
        band = all(c["admitted"] for c in cyc.values())
        eb[lid] = {"band_admits_every_cycle": band, "q7_complete_once_consistent": q7,
                   "engine_admits": band and q7, "reference_verdict": verdicts[lid],
                   "agree": (band and q7) == (verdicts[lid] == "admitted"),
                   "cycles": {cid: {k: c[k] for k in ("R0_over_B_W", "B_W",
                                                      "B_W_in_eps_of_this_terms", "B",
                                                      "B_psi", "B_psi_band", "admitted")}
                              for cid, c in cyc.items()}}
    passing = [c["R0_over_B_W"] for lid, r in eb.items() if "__" not in lid
               for c in r["cycles"].values()]
    const = [c["R0_over_B_W"] for lid, r in eb.items() if lid.endswith(("__k_1pct", "__k_1e-6"))
             for c in r["cycles"].values() if not c["admitted"]]
    bw_eps = [c["B_W_in_eps_of_this_terms"] for r in eb.values() for c in r["cycles"].values()]
    power["A2_amendment_engine_band"] = {
        "laws": eb,
        "every_verdict_agrees": all(r["agree"] for r in eb.values()),
        "passing_R0_over_B_W_max": max(passing),
        "planted_constant_R0_over_B_W_min": min(const),
        "B_W_in_eps_of_this_terms": [min(bw_eps), max(bw_eps)],
        "this_window_eps": [10 * max(c["r0_over_terms_eps"] for lid, r in da["weg"].items()
                                     if "__" not in lid for c in r.values()),
                            min(power["A2_wegscheider"][lid]["cycles"][cid]
                                ["min_residual_eps_over_generic"]
                                for lid in power["A2_wegscheider"] if lid.endswith("__k_1e-6")
                                for cid, c in power["A2_wegscheider"][lid]["cycles"].items()
                                if not c["structurally_zero"] or c["r0_over_terms_eps"] > 64)
                            / 10]}

    # A3: the population guard (its rounding scale from the one-way magnitudes and ΔG's terms)
    guard = {}
    for gid in ("fb_shift", "fb_masked", "fb_basis"):
        rows = []
        for s in va["laws"][gid]["states"]:
            scale = sum(s["modes"][m]["J_scale"] * s["modes"][m]["dG_RT_terms_abs"]
                        for m in s["modes"]) * RT / 1000 * exact.EPS
            tot = s["guard_total_pJ_per_s"]
            against = [m for m in s["modes"]
                       if s["modes"][m]["J"] * s["modes"][m]["dG_RT"] * RT / 1000 >
                       BAND_EPS * scale]
            rows.append({"tag": s["tag"], "total_pJ_per_s": tot, "scale_pJ_per_s": scale,
                         "fires": tot > BAND_EPS * scale, "modes_against_dG": against})
        fires = [r for r in rows if r["fires"]]
        # the stated band (in eps) for which each verdict holds: a firing state fires while the
        # band is below total/(scale/eps); a silent state with a positive total stays silent while
        # the band is above it; a total ≤ 0 is silent for any band
        in_eps = [r["total_pJ_per_s"] / r["scale_pJ_per_s"] if r["scale_pJ_per_s"] > 0 else None
                  for r in rows]
        fire_below = [x for r, x in zip(rows, in_eps, strict=True) if r["fires"] and _ok(x)]
        silent_above = [x for r, x in zip(rows, in_eps, strict=True)
                        if not r["fires"] and _ok(x) and x > 0]
        guard[gid] = {"fires_at": [r["tag"] for r in fires],
                      "verdicts_hold_for_a_band_in_eps": [max(silent_above, default=0.0),
                                                          min(fire_below, default=None)],
                      "conditional_on_the_band": [r["tag"] for r, x in zip(rows, in_eps,
                                                                          strict=True)
                                                  if r["fires"] and _ok(x) and x < 1e6],
                      "silent_at": [r["tag"] for r in rows if not r["fires"]],
                      "a_mode_against_its_dG_at": [r["tag"] for r in rows if r["modes_against_dG"]],
                      "min_total_over_allowance_where_fires":
                          min((r["total_pJ_per_s"] / (BAND_EPS * r["scale_pJ_per_s"])
                               for r in fires), default=None),
                      "max_total_over_allowance_where_silent":
                          max((r["total_pJ_per_s"] / (BAND_EPS * r["scale_pJ_per_s"])
                               for r in rows if not r["fires"] and r["scale_pJ_per_s"] > 0),
                              default=None)}
    guard["admitted_laws"] = {lid: {"standin_difference_max_eps": max(x["difference_over_scale_eps"]
                                                                       for x in rows),
                                    "standin_expm1_max_total": max(x["expm1_total"] for x in rows)}
                              for lid, rows in da["standin"].items()}
    # amendment A2: the engine's stated allowance A at every state, its verdicts against the
    # references', and A's place in this package's window
    eg = {}
    for lid, rows in da["engine_guard"].items():
        tags = [s_["tag"] for s_ in va["laws"][lid]["states"]]
        fires = [t for t, r in zip(tags, rows, strict=True) if r["fires"]]
        a_eps = [r["A_in_eps_of_this_scale"] for r in rows
                 if r["A_in_eps_of_this_scale"] is not None]
        if lid in guard:
            expected = guard[lid]["fires_at"]
        elif lid == "planted_negative_S_n1":
            expected = a1["planted_negative_S_n1"]["states_with_S_below_zero"]
        else:
            expected = []
        eg[lid] = {"engine_fires_at": fires, "expected": expected, "agree": fires == expected,
                   "A_in_eps_of_this_scale": [min(a_eps), max(a_eps)] if a_eps else None,
                   "max_G_over_A": max((r["G_over_A"] for r in rows
                                        if r["G_over_A"] is not None), default=None)}
    guard["engine_allowance"] = {
        "laws": eg, "every_verdict_agrees": all(r["agree"] for r in eg.values()),
        "fb_shift_A_in_eps": eg["fb_shift"]["A_in_eps_of_this_scale"],
        "this_window_eps": guard["fb_shift"]["verdicts_hold_for_a_band_in_eps"],
        "inside_the_window": (guard["fb_shift"]["verdicts_hold_for_a_band_in_eps"][0] <
                              eg["fb_shift"]["A_in_eps_of_this_scale"][0] and
                              eg["fb_shift"]["A_in_eps_of_this_scale"][1] <
                              guard["fb_shift"]["verdicts_hold_for_a_band_in_eps"][1]),
        "substitution_planted_negative_S": (
            "the engine's factored form is a Hill product carried as log S, so S − 0.05 cannot "
            "be declared; its plant injects S − 0.05 into the factored flux's evaluation, and "
            "the guard refuses it (the kinds owner's batch, item 4, at the lead's acceptance)")}
    power["A3_population_guard"] = guard

    # A4: one-way fluxes
    ow = {}
    for lid, rows in da["oneway"].items():
        sts = va["laws"][lid]["states"]
        tags = [s["tag"] for s in sts]
        per = {}
        for cid in rows[0]:
            per[cid] = {}
            floors = [rel_floor(s["modes"][cid]["dG_RT_terms_abs"]) for s in sts]
            for plant in ("exponent_flipped", "edge_in_place_of_cycle", "sigma_omitted",
                          "basis_in_place_of_hill"):
                devs = [r[cid].get(plant) / f if _ok(r[cid].get(plant)) else None
                        for r, f in zip(rows, floors, strict=True)]
                if any(_ok(x) for x in devs):
                    per[cid][plant] = summarise(tags, devs)
        meth = da["methods"][lid]
        ow[lid] = {"plants": per,
                   "routes_over_floor": {
                       "trees_vs_minors": max(m["trees_vs_minors_over_floor"] for m in meth),
                       "occupancy_trees_vs_solve": max(m["occupancy_trees_vs_solve_over_floor"]
                                                       for m in meth),
                       "edge_cycle_consistency": max(m["edge_cycle_consistency_over_floor"]
                                                     for m in meth)},
                   "routes_compared": {"j_pairs": sum(m["j_pairs"] for m in meth),
                                       "occupancies": sum(m["occupancy_pairs"] for m in meth),
                                       "edges": sum(m["edges"] for m in meth)},
                   "routes_zero_cases": sum(m["j_zero_cases"] + m["occupancy_zero_cases"] +
                                            m["edge_zero_cases"] for m in meth),
                   "routes_failures": sum(len(m["failures"]) for m in meth)}
    for lid, rows in da["basis"].items():
        tags = [s["tag"] for s in va["laws"][lid]["states"]]
        ow[lid]["basis_readout"] = {
            "states_with_a_basis_mode_against_its_dG": [
                t for t, r in zip(tags, rows, strict=True)
                if r["mode_A_against_dG"] or r["mode_B_against_dG"]],
            "total_basis_vs_hill_max_over_floor": max(r["basis_vs_hill_over_floor"]
                                                      for r in rows),
            "states_with_a_zero_hill_total": [t for t, r in zip(tags, rows, strict=True)
                                              if r["hill_total_is_zero"]],
            "every_state_agrees": all(r["agrees"] for r in rows)}
    power["A4_one_way_fluxes"] = ow

    # A5: two layouts
    lay = {}
    for lid, rows in da["layout"].items():
        tags = [s["tag"] for s in va["laws"][lid]["states"]]
        lay[lid] = {plant: {key: summarise(tags, [(r[plant] or {}).get(key) for r in rows])
                            for key in ("J", "rows", "heat", "work")
                            if any(_ok((r[plant] or {}).get(key)) for r in rows)}
                    for plant in rows[0]}
    power["A5_two_layouts"] = lay

    # A6: slopes
    sl = {}
    for lid, rows in da["slopes"].items():
        tags = [s["tag"] for s in va["laws"][lid]["states"]]
        plants = sorted(set().union(*[set(r) for r in rows]))
        chk = da["slope_check"][lid]
        sl[lid] = {"plants": {p: summarise(tags, [r.get(p) for r in rows]) for p in plants},
                   "exact_vs_differences": {
                       "rule": "|x − y| ≤ 10 τ for every pair (amendment F4)",
                       "states": len(chk),
                       "pairs": sum(c["pairs"] for c in chk),
                       "zero_cases": sum(c["zero_cases"] for c in chk),
                       "zero_cases_with_zero_floor": sum(c["zero_cases_with_zero_floor"]
                                                         for c in chk),
                       "worst_over_floor": max(c["worst_over_floor"] for c in chk),
                       "failures": sum(len(c["failures"]) for c in chk)}}
    power["A6_slopes"] = sl

    # A8, A9: amendment 1's finite-fuel and N = b populations
    for key, lid, row in (("finite_fuel", "ff_neutral_n1", "A8_finite_fuel_stored_rate"),
                          ("orientation", "d2_slip_exchanger_Nb", "A9_orientation_N_b")):
        rows = da[key]
        tags = [s["tag"] for s in va["laws"][lid]["states"]]
        power[row] = {plant: {k: summarise(tags, [(r[plant] or {}).get(k) for r in rows])
                              for k in sorted({k for r in rows for k in (r[plant] or {})})
                              if any(_ok((r[plant] or {}).get(k)) for r in rows)}
                      for plant in rows[0]}
    power["A8_finite_fuel_stored_rate"]["stored_rate_max_abs_pJ_per_s"] = max(
        abs(s["stored_standard_pJ_per_s"]) for s in va["laws"]["ff_neutral_n1"]["states"])

    # A7: parse-time checks
    power["A7_parse_checks"] = {p["id"]: va["parse"][p["id"]] for p in A["parse_plants"]}
    return power


def power_c(inputs, vc, dc) -> dict:
    power = {}
    cp = {}
    for name, srec in vc["systems"].items():
        rows, drows = srec["states"], dc["systems"][name]
        tags = [r["tag"] for r in rows]
        floors = [max(list(r["floor_residual_1e-13"]["x"].values()) +
                      list(r["floor_residual_1e-13"]["forms"].values())) for r in rows]
        per = {}
        for plant in ("K_1pct", "K_1e-6", "form_dropped", "count_off_by_one",
                      "conservation_1e-10"):
            refused = [t for t, d in zip(tags, drows, strict=True)
                       if d["plants"][plant].get("variant_refused")]
            kept = [(t, d["plants"][plant]["max_abs_dln"] / f)
                    for t, d, f in zip(tags, drows, floors, strict=True) if t not in refused]
            per[plant] = summarise([t for t, _ in kept], [x for _, x in kept], weak=MIN_MARGIN)
            per[plant]["caught_by_refusal_at"] = refused
            per[plant]["note"] = ("deviation over the residual-bound floor at each state; where "
                                  "the planted closure refuses the state, it is caught by "
                                  "refusal")
        grad = [r["gradient_vs_differences_rel"] for r in rows
                if "gradient_vs_differences_rel" in r]
        bis = [r["newton_vs_bisection_rel"] for r in rows if "newton_vs_bisection_rel" in r]
        spec_part = [r["speciation_part_pJ"] for r in rows if r["speciation_part_pJ"] is not None]
        cp[name] = {
            "plants": per,
            "floor_residual_max": max(floors),
            "floor_input_max": max(max(list(r["floor_input_rounding"]["x"].values()) +
                                       list(r["floor_input_rounding"]["forms"].values()))
                                   for r in rows),
            "manufactured_max_dln": max(r["manufactured_dln"] for r in rows),
            "residual_max_rel": max(max(r["residual_rel"].values()) for r in rows),
            "conservation_max_rel": max(max(r["conservation_rel"].values()) for r in rows),
            "charge_max_abs_fmol_e": max(abs(r["charge"]["difference_fmol_e"]) for r in rows),
            "gradient_vs_differences_max_rel": max(grad) if grad else None,
            "newton_vs_bisection_max_rel": max(bis) if bis else None,
            "joint_vs_separate_max_rel": max([d.get("joint_vs_separate_rel", 0.0) for d in drows]),
            "gradient_plant": summarise(tags, [d["gradient_plant"]["max_abs_J_per_mol"]
                                               for d in drows], weak=1.0),
            "nonminimum_plant_min_excess_pJ": min(d["nonminimum_plant"]["excess_pJ"]
                                                  for d in drows
                                                  if d["nonminimum_plant"]["excess_pJ"]
                                                  is not None),
            "charge_plant_min_fmol_e": min(d["charge_plant_fmol_e"] for d in drows),
            "speciation_part_max_pJ": max(spec_part) if spec_part else None,
            "states_with_a_total_not_positive": [r["tag"] for r in rows
                                                 if not r["every_total_positive"]],
        }
    power["C1_C2_C4_binding"] = cp
    # amendment C1: the booked term's plants over consecutive pairs, its identity, its gradient in
    # @3's frame, and the primal route's agreement with the dual
    bt = {}
    for name, srec in vc["systems"].items():
        pairs = srec["pairs"]
        tags = [f"{p['tags'][0]}->{p['tags'][1]}" for p in pairs]
        plants = {}
        for plant in ("G_star_booked_whole", "B4_formula_on_moved_binders",
                      "S_c_alone_ideal_masked"):
            devs = [(p["plants_pJ"][plant] / p["floor_pJ"]
                     if p["plants_pJ"][plant] is not None else None) for p in pairs]
            plants[plant] = summarise(tags, devs)
            plants[plant]["undefined_at"] = [t for t, d in zip(tags, devs, strict=True)
                                             if d is None]
        rows = srec["states"]
        ident = [abs(r["booked_term"]["identity_residual_pJ"]) for r in rows
                 if r["booked_term"]["identity_residual_pJ"] is not None]
        grad = [r["E_c_gradient_vs_differences_abs_J_per_mol"] for r in rows
                if "E_c_gradient_vs_differences_abs_J_per_mol" in r]
        bt[name] = {"plants": plants,
                    "identity_E_c_minus_S_c_minus_ideal_max_pJ": max(ident) if ident else None,
                    "E_c_gradient_vs_differences_max_J_per_mol": max(grad) if grad else None,
                    "states_where_S_c_is_undefined": [r["tag"] for r in rows
                                                      if r["booked_term"]["S_c_pJ"] is None],
                    "primal_vs_dual_max_abs_dln": max(r["primal"]["max_abs_dln_vs_dual"]
                                                      for r in rows),
                    "primal_certificate_max": max(r["primal"]["certificate"] for r in rows),
                    "primal_iterations_max": max(r["primal"]["iterations"] for r in rows)}
    power["C1_amendment_booked_term_and_primal"] = bt
    # amendment C2: the convergence scale V A_L against |T_L|, and the tolerance each gives in
    # ulps of the residual's terms (1e-13 V A_L/(eps V A_L) = 450 on the new scale)
    cs = {}
    for name, srec in vc["systems"].items():
        rows = srec["states"]
        ratios = {r["tag"]: min(r["totals_over_scale"].values()) for r in rows}
        tags = list(ratios)
        lo = min(tags, key=lambda t: ratios[t])
        cs[name] = {"min_total_over_scale": ratios[lo], "at": lo,
                    "states_where_the_scales_differ": [t for t in tags
                                                       if abs(ratios[t] - 1) > 1e-12],
                    "old_scale_tolerance_ulps_at_min": 1e-13 * ratios[lo] / exact.EPS,
                    "new_scale_tolerance_ulps": 1e-13 / exact.EPS,
                    "residual_max_rel_to_scale": max(max(r["residual_rel"].values())
                                                     for r in rows)}
    power["C2_amendment_convergence_scale"] = cs
    # amendment C4: the joint validity margin
    if "validity" in vc:
        vv = vc["validity"]
        reg_rows = {name: {"states": len(rows),
                           "min_t_star_fmol": min(r["t_star_fmol"] for r in rows),
                           "every_state_valid": all(r["valid"] for r in rows),
                           "exact_vs_lp_max_abs_fmol": max(abs(r["t_star_fmol"] -
                                                               r["lp_t_star_fmol"])
                                                           for r in rows)}
                    for name, rows in vv["systems"].items()}
        planted = {tag: {"t_star_exact": r["t_star_exact"], "valid": r["valid"],
                         "per_ligand_valid": r["per_ligand_valid"],
                         "exact_vs_lp_abs_fmol": abs(r["t_star_fmol"] - r["lp_t_star_fmol"]),
                         "dual": r["dual"]["outcome"], "primal": r["primal"]["outcome"]}
                   for tag, r in vv["planted"].items()}
        power["C4_amendment_joint_validity"] = {
            "registered": reg_rows, "planted": planted,
            "per_ligand_floor_admits_an_invalid_state": [
                t for t, r in planted.items() if r["per_ligand_valid"] and not r["valid"]]}
    # amendment C3: the envelope
    if "envelope" in vc:
        budget = inputs["seam_c"]["envelope"]["budget_pH"]
        ec = {}
        for cid, r in vc["envelope"]["cases"].items():
            row = {"slowest_network_rate_per_s": r["slowest_network_rates_per_s"][0],
                   "min_step_rate_per_s": r["min_step_rate_per_s"],
                   "network_over_min_step": r["slowest_network_rates_per_s"][0] /
                   r["min_step_rate_per_s"],
                   "first_order_floor_rel": r["first_order_floor_rel"],
                   "kinetic_vs_first_order_rel": r["kinetic_vs_first_order_rel"],
                   "radau_vs_bdf_max_dln": max(max(x["floor_dln"].values())
                                               for x in r["kinetic"]["rows"]),
                   "plants": {}}
            for plant, devs in r["plants"].items():
                fl_ = r["first_order_floor_rel"]
                row["plants"][plant] = {L: ({"value": v, "over_floor": v / fl_}
                                            if v is not None else None) for L, v in devs.items()}
            if "first_order_pH" in r:
                row["first_order_pH"] = r["first_order_pH"]
                row["per_step_pH"] = r["per_step_pH"]
                row["verdict_first_order"] = ("outside" if r["first_order_pH"] > budget
                                              else "inside")
                row["verdict_per_step"] = "outside" if r["per_step_pH"] > budget else "inside"
                last_H = r["kinetic"]["rows"][-1]["lag_dln"]["H"]
                row["kinetic_pH_last"] = abs(last_H) / math.log(10)
            if "b4_formula_pH" in r:
                row["b4_formula_vs_general_rel"] = abs(r["b4_formula_pH"] / r["first_order_pH"] - 1)
            ec[cid] = row
        cases = vc["envelope"]["cases"]
        lagH = {cid: abs(cases[cid]["first_order_dln"]["H"]) for cid in cases}
        ec["scalings"] = {"E1_chain_over_kon10": lagH["E1_chain"] / lagH["E1_chain_kon10"],
                          "E1_chain_over_kon100": lagH["E1_chain"] / lagH["E1_chain_kon100"],
                          "E1_chain_over_small_drive": lagH["E1_chain"] / lagH["E1_chain_small"],
                          "second_order_ratio": (ec["E1_chain"]["kinetic_vs_first_order_rel"]["H"]
                                                 / ec["E1_chain_small"]
                                                 ["kinetic_vs_first_order_rel"]["H"])}
        ec["reachability"] = vc["envelope"]["reachability"]
        power["C3_amendment_envelope"] = ec
    power["C3_movers"] = vc["movers"]
    power["C2_parse"] = vc["parse"]["planted_declared_valence"]
    power["C5_p1"] = {k: {kk: v[kk] for kk in ("threshold_free_fmol", "threshold_stored_fmol",
                                               "threshold_linearised_free_fmol",
                                               "ratio_stored_over_free",
                                               "ratio_linearised_over_free",
                                               "admissible_floor_fmol")}
                      for k, v in vc["p1"].items()}
    return power


CLAIMS = [
    {"row": "A1", "claim": ("Each mode's flux has the sign of −ΔG and is zero at its equilibrium: "
                            "J = k a S (1 − e^{ΔG/RT}) with S ≥ 0"),
     "reference": "the exact fluxes at every registered state (values: seam_a.laws)",
     "plants": ["planted_negative_S_n1 (S − 0.05): J ΔG > 0 where S < 0"]},
    {"row": "A2", "claim": ("Wegscheider's condition holds on every declared Hill cycle at the "
                            "engine's potentials, decided exactly (the residual is affine in ln a "
                            "and ψ); a law that fails, or declares a basis sharing an edge, is "
                            "refused (§16, §19 item 2)"),
     "reference": ("the residual's exact affine coefficients and its 50-digit value at every "
                   "state; the honest float64 stand-in in eps of its terms' absolute sum"),
     "plants": ["k ×1.01 and ×(1 + 1e-6)", "a voltage exponent moving 0.2 more charge",
                "a missing concentration factor", "a species read at the wrong end",
                "D2 declared as the basis {A, B}, D4 as {K1, K2}"]},
    {"row": "A3", "claim": ("The population's Σ J ΔG ≤ 0 at run time, beyond a rounding bound "
                            "from its terms; per-mode bookings are readouts (§16)"),
     "reference": "Σ J ΔG and each mode's term at every guard state",
     "plants": ["fb_shift must fire in its band", "fb_masked: the guard cannot see it",
                "fb_basis must not fire (a false-refusal control)",
                "the admitted laws' float64 stand-in, inside the bound"]},
    {"row": "A4", "claim": ("Every admitted Hill cycle exposes J⁺ and J⁻ = J⁺ e^{ΔG/RT}, and the "
                            "declared set is the diagram's full set (§16, D202)"),
     "reference": ("j± by spanning trees and by the matrix-tree minors, the master equation's "
                   "steady state, and the edge-cycle consistency"),
     "plants": ["the exponent's sign flipped", "an edge's one-way fluxes", "Σ_κ omitted",
                "the basis's one-way fluxes"]},
    {"row": "A5", "claim": ("A version-1-form world gives the same rates in either layout; the "
                            "expected rates hold for any selector (§19 item 5)"),
     "reference": ("J, rows per host end, held supply, heat, work, the stored rate and the charge "
                   "flux for proton_atp_mass_action_positive@1 (n = 2) and the neutral law "
                   "(n = 1, 2)"),
     "plants": ["N/P swapped", "the fuel end misplaced", "capacity counted twice",
                "rows scattered to one end", "n ± 1", "the fuel's 1 mM frame (RT ln 1000)",
                "the work's sign", "the voltage term dropped"]},
    {"row": "A6", "claim": ("The electrogenic conductance and each moved row's material slope, "
                            "exact, against central differences (§3.3, taken by §19)"),
     "reference": "exact slopes by forward-mode duals at every state",
     "plants": ["the static-head formula off static head", "n_q not squared",
                "∂S/∂V ignored (diagrams)", "F/(2RT)", "the wrong node's volume"]},
    {"row": "A7", "claim": "Parse-time charge and moiety balance per mode; n_q derived (§3.2)",
     "reference": "the integer sums per declared mode",
     "plants": ["X+ not conserved (charge +1)", "ATP -> ADP without Pi (phosphate −1)",
                "base-form hydrolysis without its proton (charge −1)"]},
    {"row": "A8", "claim": ("Amendment 1: finite fuel is moved rows; the stored rate is their "
                            "standard part in @3's 1 mM frame, RT (Σ ν μ°/RT − (Σ ν) ln c°) per "
                            "cycle, with no work (§3.4; COMPARTMENT_PH_TRANSFER_DESIGN §17.2)"),
     "reference": "ff_neutral_n1: rows, stored rate, heat and zero work at every state",
     "plants": ["the 1 M frame (−(Σ ν) RT ln c° dropped)", "the stored rate dropped",
                "its sign", "the fuel held instead", "the fuel moved at the other end"]},
    {"row": "A9", "claim": ("Amendment 1: a population with N = b reads its N end at the host's b, "
                            "its voltage as φ_b − φ_a, and books its rows and charge at the right "
                            "host ends (§3.1)"),
     "reference": "d2_slip_exchanger_Nb at every state, slopes included",
     "plants": ["read as N = a", "the voltage's orientation ignored", "the charge's sign",
                "rows at swapped ends", "the conductance's sign"]},
    {"row": "C1", "claim": ("The closure's free forms satisfy every binding's equilibrium and "
                            "every conservation, to its residual |g|/T ≤ 1e-13 (§19 item 2)"),
     "reference": ("Newton on the convex dual at 60 digits, nested bisection (≤ 2 ligands) and "
                   "manufactured solutions; floors from the inputs' rounding and from the "
                   "residual's bound"),
     "plants": ["a K off by 1% and by 1e-6", "a dropped form", "a count off by one",
                "conservation off by 1e-10"]},
    {"row": "C2", "claim": "Charge from totals only: Σ z n = Σ z_L T_L + Σ z_B T_B, exactly",
     "reference": "the species' charge against the totals' at 60 digits",
     "plants": ["a form declared at a valence other than z_B + Σ n z_L"]},
    {"row": "C3", "claim": ("Only movers that declare their stoichiometry in base forms, every "
                            "ligand written out, move a multi-form row (§5.2)"),
     "reference": "a verdict per registered mover",
     "plants": ["the scalar proton omitted", "a form moved as a row", "an undeclared mover"]},
    {"row": "C4", "claim": ("G* is the speciation minimum and ∂G*/∂T is each row's free base "
                            "form's potential; the booked term follows its ruling (§19 item 3)"),
     "reference": "G* at 60 digits; its gradient analytically and by central differences",
     "plants": ["the rows' own ideal potentials as the gradient", "a non-minimum speciation"]},
    {"row": "C4b", "claim": ("Amendment C1: the booked term E_c = G* − Σ_r T_r μ°′_r over the "
                             "closure's rows holds in either split, S_c with @3's ideal terms or "
                             "E_c alone; its gradient is each row's free form's potential in @3's "
                             "frame, RT ln(c_free/1 mM) (§19 amended at 19:52 UTC)"),
     "reference": ("E_c, S_c, @3's ideal terms, the standard parts and B4's formula at every "
                   "state; E_c's gradient analytically and by central differences; the primal "
                   "route (primal.py) as the second solve"),
     "plants": ["G* booked whole (Σ ΔT_r μ°′_r)", "B4's formula on moved binders (Σ_B ΔT_B μ°′_B)",
                "S_c alone with @3's ideal terms masked (Σ Δ ideal_r)"]},
    {"row": "C1b", "claim": ("Amendment C2: the closure converges on |g_L| ≤ 1e-13 A_L, A_L = "
                             "x_L + Σ|n| c, in place of |T_L|; identical where every count is ≥ 0 "
                             "(§19 amended at 19:52 UTC)"),
     "reference": ("V A_L at every state (`residual_scale_fmol`), the solution floors restated on "
                   "that scale, and S4's cancelling state, where |T_H| = 1e-9 V A_H"),
     "plants": ["the |T_L| scale at the cancelling state: a tolerance far below one ulp of the "
                "residual's terms, which no solver can meet"]},
    {"row": "C6", "claim": ("Amendment C3: the envelope is the first-order lag of the linearised "
                            "binding network, with k_on per (binder, ligand); it reduces to B4's "
                            "for one two-form buffer; every form is reachable from its base by "
                            "unit steps (§19 amended at 19:52 UTC)"),
     "reference": ("δ = −K⁻¹ P D at 60 digits; the full nonlinear network under the drive by "
                   "Radau and BDF, its lag measured against the closure at each state's own "
                   "totals; eight cases, one a cooperative chain"),
     "plants": ["a per-step minimum λ (non-conservative on the chain: the budget's verdict flips)",
                "a k_on that ignores the ligand", "k_on swapped between the ligands",
                "a binder with a form not reachable by unit steps"]},
    {"row": "C7", "claim": ("Amendment C4: the closure's validity is the joint condition t* > 0, "
                            "t* = min over the ligand simplex of λ·T − Σ_B T_B min_f λ·n_f; the "
                            "per-ligand floors Σ T_B min n are its values at the simplex's "
                            "vertices, necessary and not sufficient for mixed-sign counts (§19 "
                            "amended at 19:52 UTC)"),
     "reference": ("t* exactly in rationals by the arrangement's vertices, and by the primal LP "
                   "(HiGHS); every registered state; four planted states of S7, whose Mg²⁺ "
                   "binding releases H⁺"),
     "plants": ["the per-ligand floors alone, which admit joint_infeasible (t* = −1/2 fmol)",
                "the boundary, t* = 0: not an interior state"]},
    {"row": "C5", "claim": ("P1's buffered node: a predictor must read the quantity it "
                            "differentiates (§17, §18)"),
     "reference": ("rate-normalised thresholds (the free amount, the stored equivalents above "
                   "their admissible floor, the linearised free amount) and the equilibrated "
                   "free amount on a ladder of draws"),
     "plants": ["today's predictor: the free amount against the stored derivative"]},
]

ZERO_POWER = [
    {"control": "the voltage-exponent plant at ψ = 0", "why": "its residual is 0.2 ψ",
     "remedy": "every state with V ≠ 0; the unit state shows it (residual_eps_at_unit_state)"},
    {"control": "the concentration-exponent plant at c = c°", "why": "its residual is ± ln a",
     "remedy": "every registered state but the unit state"},
    {"control": "the swapped-end plant where both ends' activities are equal",
     "why": "its residual is ln(a_N/a_P); a neutral uniport at equilibrium has equal ends",
     "remedy": "the random states (unequal ends)"},
    {"control": "a one-state Wegscheider check",
     "why": ("at the unit state (a = 1, ψ = 0) only the constant is left, so the charge, "
             "concentration and swap plants pass"),
     "remedy": "§19 item 2: algebraic, or d + 1 generic states (seam_a.generic_states)"},
    {"control": "the exponent-flip plant at a cycle's exact equilibrium",
     "why": ("J⁻ = J⁺ there either way (the near_*_+0 states, and the unit state, where a "
             "transport cycle's standard potentials cancel); at |ΔG/RT| = 1e-9 it is already "
             "about 3e5 floors"),
     "remedy": "every other state"},
    {"control": "Σ_κ omitted, on a cycle through every state (D1's A, D2's A, D4's K1 and K2)",
     "why": "Σ_κ = 1", "remedy": "D2's B and C, D3's α and β, D4's K3"},
    {"control": "the basis's one-way fluxes where the dependent cycle barely turns",
     "why": "J_C⁺ ≪ J_A⁺ (D2's A at far_A_+25)",
     "remedy": "every other state of D2 and D4"},
    {"control": "the population guard on fb_masked",
     "why": "the leak's dissipation masks the exchange's wrong sign in the total",
     "remedy": "none at run time: in a diagram law Wegscheider at parse catches the same error"},
    {"control": "the guard on any factored or admitted diagram law",
     "why": "J ΔG ≤ 0 by construction, and its sign is exact in doubles with expm1",
     "remedy": "the net-flow plants fb_shift and planted_negative_S_n1"},
    {"control": ("capacity counted twice, rows scattered to one end, and the work's sign, at "
                 "static head"),
     "why": "J ≈ 0 there, so there is no flux to double, scatter or book",
     "remedy": "every other state (at least 1e11 floors off static head)"},
    {"control": "the voltage-dropped plant on the neutral law", "why": "n_q = 0",
     "remedy": "the proton law (at least 6e5 floors at every state)"},
    {"control": "the static-head formula at static head", "why": "it is exact there",
     "remedy": "the random and far states"},
    {"control": "∂S/∂V ignored at a cycle's equilibrium", "why": "(1 − e^{ΔG/RT}) = 0 kills it",
     "remedy": "every state off equilibrium"},
    {"control": "n_q not squared with |n_q| = 1", "why": "n_q² = |n_q|",
     "remedy": "the proton law at n = 2"},
    {"control": "conductance plants on neutral modes (the neutral law)", "why": "no charge moves",
     "remedy": "the material slopes"},
    {"control": "a dropped standard potential of a transported species",
     "why": "it cancels between the ends of a transport mode",
     "remedy": "the fuel rows' potentials (hydrolysis) and seam C's forms"},
    {"control": ("in every held-fuel population, the moved rows' standard part (the stored "
                 "rate, §3.4) and its frame: "
                 "RT (Σ ν μ°/RT − (Σ ν) ln c0) per cycle (COMPARTMENT_PH_TRANSFER_DESIGN §17.2)"),
     "why": ("every registered population holds its fuel and moves each species between its two "
             "ends, so Σ ν μ°' = 0 and stored_standard_pJ_per_s is exactly 0 at every state; "
             "fuel_frame_1mM tests the held ΔG's activity frame, a different error"),
     "remedy": ("ff_neutral_n1, the finite-fuel population added by amendment 1 (power.A8); "
                "the other populations hold their fuel")},
    {"control": "a population with N = b (the outside end as N), before amendment 1",
     "why": ("every population registered at f1808037 has N = a; the orientation plant shows only "
             "that an N = a world is not read as N = b"),
     "remedy": "d2_slip_exchanger_Nb, added by amendment 1 (power.A9)"},
    {"control": ("amendment 1's stored-rate plants (the 1 M frame, dropped, its sign) and the "
                 "fuel held instead, at static head"),
     "why": "J ≈ 0 there, so nothing is stored or moved",
     "remedy": "every other state of ff_neutral_n1"},
    {"control": "the fuel held instead, on J; the fuel moved at b, on work",
     "why": ("the kinetics do not depend on how the fuel is booked, and finite fuel books no work "
             "either way"),
     "remedy": "the rows, the stored rate and the work (held instead); J, rows and stored (at b)"},
    {"control": "amendment 1's N = b plants at the unit state",
     "why": "both ends are identical there (every activity 1, V = 0)",
     "remedy": "every other state of d2_slip_exchanger_Nb"},
    {"control": ("amendment C1: B4's formula on moved binders, at a pair whose binder totals are "
                 "equal (S1 mostly_bound -> saturated_binder, S3 mg_mostly_bound -> "
                 "mg_saturating)"),
     "why": "Σ_B ΔT_B μ°′_B = 0 there: B4's formula is exact while binder rows do not move",
     "remedy": "every other pair, where the binders' totals differ"},
    {"control": "amendment C1: S_c alone with @3's ideal terms masked, at pairs with S4[10]",
     "why": "S_c and @3's ideal term on the H row are undefined at a negative total",
     "remedy": "E_c, which is defined there, and every other pair"},
    {"control": "amendment C2: the convergence scale, where every count is ≥ 0",
     "why": "V A_L = |T_L| there, so both criteria are the same (S1, S2, S3, S5, S6)",
     "remedy": "S4, whose pi2_PO4 has a count of −1, and its cancelling state above all"},
    {"control": "amendment C3: a per-step minimum λ on a network without a bottleneck (E2)",
     "why": "every mode is about as fast as its slowest step, so the per-step bound holds there",
     "remedy": "E1's cooperative chain, where it is non-conservative"},
    {"control": "amendment C3: a k_on that ignores the ligand, on E1's H⁺ lag under an H⁺ drive",
     "why": ("only the Mg²⁺ steps' k_on changes, and they barely carry the H⁺ lag: 4e-9 relative, "
             "below the first order's floor of 2.3e-8"),
     "remedy": ("the Mg²⁺ lag in the same cases (2.3e-3), E1_chain_two_drives (1.19 on Mg²⁺) and "
                "E2 (0.68 and 1.0)")},
    {"control": "amendment C3: the kinetic lag in the first relaxation times",
     "why": "the lag builds up from zero (the run starts at the closure's state)",
     "remedy": "the later record times (8 and 16 slowest relaxation times)"},
    {"control": "bitwise agreement of the two layouts", "why": "the engine against itself",
     "remedy": "the engine's own test; the references give the rates both must meet"},
    {"control": "a K plant on a form that holds little of its ligand",
     "why": "the free amounts barely move", "remedy": "that form's own concentration"},
    {"control": "today's P1 predictor while θ dt |J| < n_free", "why": "both predictors agree",
     "remedy": "the ladder's draws beyond the free amount"},
    {"control": "a declared form valence",
     "why": "if the engine derives valences and never reads a declared one, the plant cannot occur",
     "remedy": "the parse identity z_form = z_base + Σ n z_L (seam_c.parse.form_valences)"},
]

READINGS = [
    ("Doubles carry rounding into the residual. Every passing cycle's constant term is about "
     "1e-16, not 0, because a ratio of published k0 is irrational. A load fraction that is not "
     "dyadic leaves the voltage coefficient off by about 5e-17. So an algebraic Wegscheider check "
     "needs "
     "§19's rounding band as well. The registered loads are dyadic, so every passing law's "
     "structural coefficients are exactly zero."),
    ("A diagram's own backward flux Π⁻Σ_κ/Σ differs from the contract's J⁺ e^{ΔG/RT} by e^{−r}. "
     "The residual r is about 1e-16 for the passing laws "
     "(power.A1_sign_and_zero.*.max_abs_ln_diagram_over_contract_backward). Booked with its own "
     "backward flux, an admitted diagram law shows J ΔG > 0 within |ΔG/RT| < |r| of equilibrium, "
     "at about 1e-37 here. The contract's J⁻ keeps the sign exact."),
    ("A form below its base (pi2_PO4) can make a ligand's total equivalents legitimately negative "
     "(S4's high-pH state, T_H = −1.86 fmol). The admissible floor is Σ_B T_B min_f n_{L,f}, not "
     "zero. Then @3's per-row ideal term RT n (ln(n/V) − 1) on the H row is undefined, and so is "
     "'G* less the stored rows' own terms'. The booked term's ruling (§19 item 3) and any "
     "positivity guard on that row must account for it. P1b's floor is −0.5 fmol."),
    ("The guard's teeth show only on net-flow laws, since factored and admitted diagram laws "
     "cannot trip it. So its plants are published as net-flow test laws."),
]

NOTES = [
    "Every constant, range and diagram is synthetic (D152 §2.4).",
    ("Hill 1989 and King and Altman 1956 are cited as CORE_SEAMS_DESIGN cites them, unread. The "
     "decomposition is self-verified by two routes and the edge-cycle consistency."),
    "The booked closure term is registered by a dated amendment once ruled (§19 item 3).",
    "The two composed worlds come later, with composition's references (§19).",
    ("Every deviation is in floors at its state. For seam A the floor is honest float64 rounding: "
     "on J (and rows, heat, work) (J⁺ + J⁻) × (ΔG/RT's terms + 8) eps, absolute, since near "
     "equilibrium no relative floor exists; on one-way fluxes and slopes (terms + 8) eps "
     "relative. For seam C it is the solution error that |g|/T ≤ 1e-13 admits. 'weak_at' lists "
     "the states below ten floors; a plant has power where its largest margin clears ten "
     "tolerances and the tolerance clears ten floors."),
]


# --------------------------------------------------------------------------------------------

def build() -> tuple:
    inputs = json.loads(worlds.INPUTS.read_text())
    va, da = seam_a(inputs)
    vc, dc = seam_c(inputs)
    vals = {"kind": "cells.core_seams_reference_values@1", "registered": worlds.REGISTERED,
            "inputs_git_blob": git_blob_id(worlds.INPUTS), "seam_a": va, "seam_c": vc}
    des = {
        "kind": "cells.core_seams_reference_design@1",
        "registered": worlds.REGISTERED,
        "status": ("registered before any engine output for seams A and C (CORE_SEAMS_DESIGN §19 "
                   "item 7: the kinds and binding owners had not started)"),
        "inputs": {"path": "validation/core_seams/references/reference_inputs.json",
                   "git_blob": git_blob_id(worlds.INPUTS)},
        "min_margin": MIN_MARGIN, "verdict_band_eps": BAND_EPS, "weak_below_floors": MIN_MARGIN,
        "claims": CLAIMS,
        "power": dict(power_a(inputs, va, da), **power_c(inputs, vc, dc)),
        "zero_power": ZERO_POWER, "readings": READINGS, "notes": NOTES,
    }
    return des, vals


def dump(o, compact=("states", "residual_at_states", "ladder")) -> str:
    """JSON with indent 1, except that each element of a ``compact`` list sits on one line."""
    def enc(x, ind, key=None):
        pad = " " * ind
        if isinstance(x, dict):
            if not x:
                return "{}"
            items = [f'{pad} {json.dumps(k)}: {enc(v, ind + 1, k)}' for k, v in x.items()]
            return "{\n" + ",\n".join(items) + "\n" + pad + "}"
        if isinstance(x, list):
            if key in compact and x:
                inner = [pad + " " + json.dumps(v, separators=(",", ":"), allow_nan=False)
                         for v in x]
                return "[\n" + ",\n".join(inner) + "\n" + pad + "]"
            if x and any(isinstance(v, (dict, list)) for v in x):
                inner = [pad + " " + enc(v, ind + 1) for v in x]
                return "[\n" + ",\n".join(inner) + "\n" + pad + "]"
            return json.dumps(x, allow_nan=False)
        return json.dumps(x, allow_nan=False)
    return enc(o, 0) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    d, v = build()
    if args.check:
        same_d = DESIGN_FILE.read_text() == dump(d)
        same_v = VALUES_FILE.read_text() == dump(v)
        print(f"design: {'identical' if same_d else 'DIFFERS'}; "
              f"values: {'identical' if same_v else 'DIFFER'}")
        return 0 if same_d and same_v else 1
    DESIGNS.mkdir(exist_ok=True)
    DESIGN_FILE.write_text(dump(d))
    VALUES_FILE.write_text(dump(v))
    print(f"wrote {DESIGN_FILE.name} and {VALUES_FILE.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
