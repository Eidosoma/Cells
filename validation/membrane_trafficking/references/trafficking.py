"""R2's half-step on a world, stage by stage, with every booking (T3-T6's independent references).

Written from FR-2's design statement 1 §3, §4 and §12 and MEMBRANE_RETRIEVAL_DESIGN §2.1-§2.3
and §4.1. No engine code is read.

**A route** joins an owner cell i's plasma patch k (from i to its outside node o, held or free) to
the pool j of the compartment bounded by patch b (from i to j). Per stage:
- **S_ret(τ):** dA = r τ moves k → b, dC = (C_k/A_k) dA. The retrieved area's outside-plate share,
  δq = −dC V_k, moves o → j, carried by the route's carriers, δ_s = t_s δq/(z_s CHARGE_PER_FMOL).
  At a held o the reservoir supplies them. Units follow N' = N (A_k'/A_k)^e, and the moved amount
  joins the route's record.
- **S_rec(τ):** the mirror. dA moves b → k with dC = (C_b/A_b) dA; the packet's lumen share
  δq = −dC V_b moves j → o (into a held o's reservoir); the record follows R' = R (A_b'/A_b)^e_r,
  and the returned units join the plasma population.
- **The half-step** is S_ret(h/2) S_rec(h) S_ret(h/2). A stage with no positive rate keeps its
  state. Volumes never change (version 1 encloses no fluid, §2.3's F0).

**Two independent routes to each booking.** Every stage is re-solved densely (``network``), and
§2.2's closed forms are evaluated from the stage's start state beside it:
- the merge heat C_dst dC (V_dst − V_src)²/(2 (C_dst + dC)) per route, against the dense
  H = −ΔU + Σ_h φ_h (ΔQ_h + q_supplied,h);
- a held node's electrode charge, the change of its plates' charge: +dC V_k on retrieval from it
  and −dC V_b on recycling into it, against the dense Δ(Kφ)_h;
- the carriers, δ_s above, and the reservoir work Σ δ_s (RT ln c_ref + z F φ_h) at a held node.
The closed forms are exact when every potential but the destination side's stays put during the
stage. That holds for retrieval, and for recycling into a patch on a held node whose pool touches
nothing else. ``stage`` reports whether they agree. Recycling into a patch on a free node has only
the dense route, and no registered stage does that.

**Sharing among routes** (§4, and §13's answers of 19 November 2026): a stage's heat is shared by
the routes' first-order terms ½ dC (V_src − V_dst)², and a free node's free-energy change by
|the amount each route moved there| / Σ |amounts|, carrier row by carrier row. A stage where two
routes share a source patch, a pool patch or a population is refused here: the declared worlds
have none, and the rule for it is not stated.
"""

from __future__ import annotations

import copy
from decimal import Decimal

from validation.core_seams.references.exact import context, dec

from .network import CHARGE_PER_FMOL, FARADAY, GAS_CONSTANT, MOL_PER_FMOL, World

PJ = Decimal(10) ** 12                 # J -> pJ
FMOL_J_TO_PJ = MOL_PER_FMOL * PJ       # fmol × (J/mol) -> pJ


class State:
    """A world with its populations and records."""

    def __init__(self, world: World, routes: list, populations: dict, records: dict):
        self.world = world
        self.routes = copy.deepcopy(routes)
        self.units = {p: dec(v["units"]) for p, v in populations.items()}
        self.population_patch = {p: v["patch"] for p, v in populations.items()}
        self.records = {k: dec(v) for k, v in records.items()}      # (route, population) -> R

    def copy(self) -> "State":
        s = State.__new__(State)
        s.world = self.world.copy()
        s.routes = self.routes
        s.units = dict(self.units)
        s.population_patch = self.population_patch
        s.records = dict(self.records)
        return s


def _node_G_terms(world: World, node) -> dict:
    """n (ln(n/V) − 1) per species at a node (fmol; n/V in mM), the chemical free energy over RT."""
    V = world.nodes[node]["volume_pL"]
    return {s: (n * ((n / V).ln() - 1) if n > 0 else Decimal(0))
            for s, n in world.amounts.get(node, {}).items()}


def stage(state: State, direction: str, dA: dict, drop_valence: bool = False) -> tuple:
    """One stage, every route at once (each route's dA in m², ≥ 0). Returns (state', report).
    ``drop_valence`` plants carriers moved as δ_s = t_s δq/CHARGE_PER_FMOL, z ignored."""
    w = state.world
    active = [r for r in state.routes if dec(dA.get(r["id"], 0)) > 0]
    for key in ("plasma_patch", "pool_patch"):
        seen = [r[key] for r in active]
        if len(seen) != len(set(seen)):
            raise ValueError(f"two routes share a {key} in one stage: not a stated rule")
    phi = w.solve()
    U0 = w.energy_J(phi)
    Q0 = w.held_charge(phi)
    new = state.copy()
    nw = new.world
    report = {"direction": direction, "routes": {}, "supplied_fmol": {}, "moved_into_fmol": {},
              "potentials_before": phi}
    moved_at = {}            # node -> species -> route -> signed amount moved into the node
    touched_pops = set()
    with context():
        G0 = {n: _node_G_terms(w, n) for n in w.free_nodes()}
        for route in active:
            rid = route["id"]
            a = dec(dA[rid])
            k, b, j = route["plasma_patch"], route["pool_patch"], route["pool_node"]
            o = w.patches[k]["outside"]
            Vk, Vb = w.voltage(phi, k), w.voltage(phi, b)
            if direction == "retrieval":
                src_id, dst_id, Vsrc, Vdst, frm, to = k, b, Vk, Vb, o, j
            elif direction == "recycling":
                src_id, dst_id, Vsrc, Vdst, frm, to = b, k, Vb, Vk, j, o
            else:
                raise ValueError(direction)
            src, dst = w.patches[src_id], w.patches[dst_id]
            if not (Decimal(0) < a < src["area_m2"]):
                raise ValueError(f"{rid}: a piece as large as its source")
            dC = src["capacitance_F"] * a / src["area_m2"]
            dq = -dC * Vsrc                                  # moved frm -> to (C)
            Cdst = dst["capacitance_F"]
            closed_heat = Cdst * dC * (Vdst - Vsrc) ** 2 / (2 * (Cdst + dC))
            first_order = dC * (Vsrc - Vdst) ** 2 / 2
            electrode_closed = {}
            if w.nodes[o]["kind"] == "held":
                electrode_closed[o] = dC * Vk if direction == "retrieval" else -dC * Vb
            moved, W_res_closed, held_ln = {}, Decimal(0), Decimal(0)
            RT = GAS_CONSTANT * w.T_K
            for s, t in route["carriers"].items():
                z_used = 1 if drop_valence else w.valences[s]
                n = dec(t) * dq / (z_used * CHARGE_PER_FMOL)
                moved[s] = n
                for node, sign in ((frm, -1), (to, +1)):
                    rep_in = report["moved_into_fmol"].setdefault(node, {})
                    rep_in[s] = rep_in.get(s, Decimal(0)) + sign * n
                    if w.nodes[node]["kind"] == "held":
                        sup = report["supplied_fmol"].setdefault(node, {})
                        sup[s] = sup.get(s, Decimal(0)) - sign * n
                        nd = w.nodes[node]
                        lnc = dec(nd["reference_mM"][s]).ln()
                        W_res_closed += (-sign * n) * (RT * lnc + w.valences[s] * FARADAY
                                                       * dec(nd["potential_V"]))
                        held_ln += (-sign * n) * RT * lnc
                    else:
                        nw.amounts.setdefault(node, {})
                        nw.amounts[node][s] = nw.amounts[node].get(s, Decimal(0)) + sign * n
                        moved_at.setdefault(node, {}).setdefault(s, {})[rid] = sign * n
            # areas and capacitances
            nw.patches[src_id]["area_m2"] -= a
            nw.patches[src_id]["capacitance_F"] -= dC
            nw.patches[dst_id]["area_m2"] += a
            nw.patches[dst_id]["capacitance_F"] += dC
            # units: N' = N (A'/A)^e on retrieval, R' = R (A_b'/A_b)^e_r on recycling
            units_moved = {}
            ratio = (src["area_m2"] - a) / src["area_m2"]
            if direction == "retrieval":
                for pop, e in route["enrichment"].items():
                    if state.population_patch[pop] != k:
                        continue
                    if pop in touched_pops:
                        raise ValueError(f"{pop}: two routes on one population in one stage")
                    touched_pops.add(pop)
                    N = state.units[pop]
                    Nn = N * (dec(e) * ratio.ln()).exp() if N != 0 else Decimal(0)
                    units_moved[pop] = N - Nn
                    new.units[pop] = Nn
                    key = (rid, pop)
                    new.records[key] = state.records.get(key, Decimal(0)) + (N - Nn)
            else:
                for pop, e in route["recycling_enrichment"].items():
                    if pop in touched_pops:
                        raise ValueError(f"{pop}: two routes on one population in one stage")
                    touched_pops.add(pop)
                    key = (rid, pop)
                    R = state.records.get(key, Decimal(0))
                    Rn = R * (dec(e) * ratio.ln()).exp() if R != 0 else Decimal(0)
                    units_moved[pop] = -(R - Rn)
                    new.records[key] = Rn
                    new.units[pop] = new.units[pop] + (R - Rn)
            report["routes"][rid] = {
                "dA_m2": a, "dC_F": dC, "V_source": Vsrc, "V_destination": Vdst,
                "V_destination_closed": (Cdst * Vdst + dC * Vsrc) / (Cdst + dC),
                "charge_moved_C": dq, "carriers_fmol": moved, "from": frm, "to": to,
                "closed_form_heat_pJ": closed_heat * PJ, "first_order_term_pJ": first_order * PJ,
                "electrode_closed_C": electrode_closed,
                "W_res_closed_pJ": W_res_closed * FMOL_J_TO_PJ,
                "held_ln_share_pJ": held_ln * FMOL_J_TO_PJ, "units_moved": units_moved}
        # the state after: the dense solve and every booking
        phi1 = nw.solve()
        U1 = nw.energy_J(phi1)
        Q1 = nw.held_charge(phi1)
        G1 = {n: _node_G_terms(nw, n) for n in nw.free_nodes()}
        RT = GAS_CONSTANT * w.T_K
        dG_node = {n: {s: RT * (G1[n].get(s, Decimal(0)) - G0[n].get(s, Decimal(0))) * FMOL_J_TO_PJ
                       for s in sorted(set(G0[n]) | set(G1[n]))} for n in G0}
        dG_chem = sum((x for d in dG_node.values() for x in d.values()), Decimal(0))
        q_sup = {h: Decimal(0) for h in w.held_nodes()}
        W_res = Decimal(0)
        for h, sup in report["supplied_fmol"].items():
            nd = w.nodes[h]
            for s, n in sup.items():
                q_sup[h] += CHARGE_PER_FMOL * w.valences[s] * n
                W_res += n * (RT * dec(nd["reference_mM"][s]).ln() + w.valences[s] * FARADAY
                              * dec(nd["potential_V"]))
        electrode = {h: Q1[h] - Q0[h] for h in w.held_nodes()}
        W_elec = sum((dec(w.nodes[h]["potential_V"]) * electrode[h] for h in w.held_nodes()),
                     Decimal(0))
        electrode_closed = {h: Decimal(0) for h in w.held_nodes()}
        for r in report["routes"].values():
            for h, x in r["electrode_closed_C"].items():
                electrode_closed[h] += x
        W_elec_closed = sum((dec(w.nodes[h]["potential_V"]) * electrode_closed[h]
                             for h in w.held_nodes()), Decimal(0))
        dU = U1 - U0
        heat_dense = -dU + sum((dec(w.nodes[h]["potential_V"]) * (electrode[h] + q_sup[h])
                                for h in w.held_nodes()), Decimal(0))
        heat_closed = sum((r["closed_form_heat_pJ"] for r in report["routes"].values()),
                          Decimal(0))
        held_ln_total = sum((r["held_ln_share_pJ"] for r in report["routes"].values()),
                            Decimal(0))
        W_carriers = dG_chem - held_ln_total
        # per-route shares: heat by first-order terms, a free node's ΔG by amounts moved there
        fo_total = sum((r["first_order_term_pJ"] for r in report["routes"].values()), Decimal(0))
        for rid, r in report["routes"].items():
            r["heat_share_pJ"] = (heat_dense * PJ * r["first_order_term_pJ"] / fo_total
                                  if fo_total != 0 else Decimal(0))
            share = Decimal(0)
            for node, per_s in moved_at.items():
                for s, by_route in per_s.items():
                    if rid not in by_route:
                        continue
                    tot = sum((abs(x) for x in by_route.values()), Decimal(0))
                    if tot != 0:
                        share += dG_node[node][s] * abs(by_route[rid]) / tot
            r["W_carriers_pJ"] = share - r["held_ln_share_pJ"]
        report.update({
            "potentials_after": phi1, "dU_view_pJ": dU * PJ, "heat_dense_pJ": heat_dense * PJ,
            "heat_closed_pJ": heat_closed, "electrode_C": electrode,
            "electrode_closed_C": electrode_closed, "W_elec_pJ": W_elec * PJ,
            "W_elec_closed_pJ": W_elec_closed * PJ, "W_res_pJ": W_res * FMOL_J_TO_PJ,
            "W_res_closed_pJ": sum((r["W_res_closed_pJ"] for r in report["routes"].values()),
                                   Decimal(0)),
            "dG_chem_pJ": dG_chem, "dG_by_node_pJ": dG_node, "W_carriers_pJ": W_carriers,
        })
        # the closure with the closed-form heat and electrode charge: the physical check (the
        # dense heat closes it by construction)
        terms = (report["dG_chem_pJ"], report["dU_view_pJ"], heat_closed, report["W_res_pJ"],
                 report["W_elec_closed_pJ"], W_carriers)
        report["identity_closed_pJ"] = (terms[0] + terms[1] + terms[2] - terms[3] - terms[4]
                                        - terms[5])
        report["terms_scale_pJ"] = sum((abs(x) for x in terms), Decimal(0))
        return new, report


def half_step(state: State, rates_ret: dict, rates_rec: dict, h, scheme: str = "palindrome",
              drop_valence: bool = False):
    """S_ret(h/2) S_rec(h) S_ret(h/2) (or, planted, the Lie split S_ret(h) S_rec(h)): returns the
    state and the stages' reports. Rates in m²/s."""
    h = dec(h)
    reports = []
    with context():
        if scheme == "palindrome":
            plan = [("retrieval", h / 2), ("recycling", h), ("retrieval", h / 2)]
        elif scheme == "lie":
            plan = [("retrieval", h), ("recycling", h)]
        else:
            raise ValueError(scheme)
        for direction, tau in plan:
            rates = rates_ret if direction == "retrieval" else rates_rec
            dA = {rid: dec(r) * tau for rid, r in rates.items() if dec(r) > 0}
            if not dA:
                continue
            state, rep = stage(state, direction, dA, drop_valence)
            reports.append(rep)
    return state, reports


def planted_R1(state: State, dA: dict) -> dict:
    """R1, insertion's rule run backwards (planted): the capacitance moves k → b at fixed free-node
    charges, with no carrier written. Returns every node's potential after, for T4's plant."""
    nw = state.world.copy()
    with context():
        for route in state.routes:
            a = dec(dA.get(route["id"], 0))
            if a <= 0:
                continue
            k, b = route["plasma_patch"], route["pool_patch"]
            pk = nw.patches[k]
            dC = pk["capacitance_F"] * a / pk["area_m2"]
            pk["area_m2"] -= a
            pk["capacitance_F"] -= dC
            nw.patches[b]["area_m2"] += a
            nw.patches[b]["capacitance_F"] += dC
    return nw.solve()
