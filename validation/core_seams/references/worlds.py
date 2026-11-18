"""The registered inputs for seams A and C (``reference_inputs.json``), generated here.

    python -m validation.core_seams.references.worlds            # write
    python -m validation.core_seams.references.worlds --check    # compare

Everything is synthetic, labelled under D152 §2.4: the diagrams, their state energies and rate
scales, the registry's standard potentials and every concentration range are this package's own
bracket, not a source's numbers. The version-1 laws' forms are COMPARTMENT_PH_TRANSFER_DESIGN §6's
and R-fuel's statement of the neutral law; their parameters are synthetic too.

These are inputs only (CORE_SEAMS_DESIGN §19 item 1): states, edges, rate expressions and
constants, from which the engine builds its test laws. Expected values are in ``designs/``.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "reference_inputs.json"
REGISTERED = "2026-11-18"
SEED = 20261118
T_K = 310.0
C0_MM = 1000.0
LN10 = math.log(10.0)

# --------------------------------------------------------------------------------------------
# Registries (synthetic)
# --------------------------------------------------------------------------------------------

REGISTRY_A = {
    "temperature_K": T_K,
    "standard_concentration_mM": C0_MM,
    "species": {
        "H": {"valence": 1, "mu0_RT": 0.0},
        "X": {"valence": 1, "mu0_RT": -2.25},
        "Y": {"valence": 2, "mu0_RT": 4.5},
        "Z": {"valence": 0, "mu0_RT": 1.75},
        "ATP": {"valence": 0, "mu0_RT": 12.0},
        "ADP": {"valence": 0, "mu0_RT": 0.4},
        "Pi": {"valence": 0, "mu0_RT": -0.3},
    },
    "moieties": {"adenine": {"ATP": 1, "ADP": 1}, "phosphate": {"ATP": 3, "ADP": 2, "Pi": 1},
                 "H": {"H": 1}, "X": {"X": 1}, "Y": {"Y": 1}, "Z": {"Z": 1}},
    "note": ("Seam A's registry. ATP, ADP and Pi are neutral transformed rows (FR-4's "
             "convention), so Δ_rG'°/RT = 0.4 − 0.3 − 12.0 = −11.9 per hydrolysis. Every value is "
             "synthetic (D152 §2.4)."),
}


def _form(fid, counts, mu0_base, ln_beta, mu0_lig):
    """A form's μ°/RT from its binder's base μ°/RT and its ln β: ln β = μ°_b + Σ n μ°_L − μ°_f."""
    mu = mu0_base + sum(n * mu0_lig[L] for L, n in counts.items()) - ln_beta
    out = {"id": fid, "mu0_RT": mu}
    if counts:
        out["counts"] = dict(counts)
    return out


def _registry_c() -> dict:
    lig = {"H": 0.0, "Mg": 1.0, "Ca": -0.5}

    def kd(K_mM):           # an association constant in activities: β = c°/K_d
        return math.log(C0_MM / K_mM)

    def pk(p):              # a protonation: β = 10^pK (K_a/c° = 10^-pK)
        return p * LN10

    binders = {}

    def binder(name, zb, mu_b, forms):
        binders[name] = {"base_valence": zb,
                         "forms": [_form(name + "_base", {}, mu_b, 0.0, lig)] +
                         [_form(fid, counts, mu_b, lb, lig) for fid, counts, lb in forms]}

    binder("buf1", -1, 1.25, [("buf1_H", {"H": 1}, pk(7.0))])
    binder("buf2", 0, -0.75, [("buf2_H", {"H": 1}, pk(6.1))])
    binder("nuc4", -4, 3.5, [("nuc4_H", {"H": 1}, pk(6.5)),
                             ("nuc4_H2", {"H": 2}, pk(6.5) + pk(4.0)),
                             ("nuc4_Mg", {"Mg": 1}, kd(0.05)),
                             ("nuc4_MgH", {"H": 1, "Mg": 1}, pk(6.5) + kd(2.0)),
                             ("nuc4_Mg2", {"Mg": 2}, kd(0.05) + kd(20.0))])
    binder("nuc3", -3, 2.5, [("nuc3_H", {"H": 1}, pk(6.4)),
                             ("nuc3_Mg", {"Mg": 1}, kd(0.5)),
                             ("nuc3_MgH", {"H": 1, "Mg": 1}, pk(6.4) + kd(10.0))])
    binder("pi2", -2, -1.5, [("pi2_H", {"H": 1}, pk(6.8)),
                             ("pi2_PO4", {"H": -1}, -pk(12.3)),
                             ("pi2_Mg", {"Mg": 1}, kd(20.0))])
    binder("cab0", -2, 0.5, [("cab0_Ca", {"Ca": 1}, kd(1e-3))])
    binder("cabuf", -4, 2.0, [("cabuf_H", {"H": 1}, pk(9.0)),
                              ("cabuf_H2", {"H": 2}, pk(9.0) + pk(8.5)),
                              ("cabuf_Ca", {"Ca": 1}, kd(1e-4)),
                              ("cabuf_CaH", {"Ca": 1, "H": 1}, pk(9.0) + kd(0.05)),
                              ("cabuf_Mg", {"Mg": 1}, kd(5.0))])
    # amendment C3 (§19 amended at 19:52 UTC): a cooperative two-proton chain for the envelope.
    # Its first protonation is weak (pK 1) and its second strong (pK 13), so the singly protonated
    # form is scarce at every pH and the base ⇌ H2 conversion is the network's slowest mode; Mg²⁺
    # binds the base. It joins no system of S1-S6.
    binder("coop2", -2, 0.75, [("coop2_H", {"H": 1}, pk(1.0)),
                               ("coop2_H2", {"H": 2}, pk(1.0) + pk(13.0)),
                               ("coop2_Mg", {"Mg": 1}, kd(1.0))])
    # amendment C4 (§19's correction: the per-ligand floor is necessary, not sufficient, for
    # mixed-sign counts): a binder whose Mg²⁺ binding releases a proton (mgx_MgmH: H −1, Mg +1),
    # reached from its base by unit steps through mgx_Mg. ln β of MgmH is that of base + Mg ⇌
    # MgmH + H. It joins no system of S1-S6.
    binder("mgx", -2, -0.25, [("mgx_H", {"H": 1}, pk(7.0)),
                              ("mgx_Mg", {"Mg": 1}, kd(2.0)),
                              ("mgx_MgmH", {"H": -1, "Mg": 1}, math.log(2e-4))])
    return {
        "temperature_K": T_K,
        "standard_concentration_mM": C0_MM,
        "species": {"H": {"valence": 1, "mu0_RT": lig["H"]},
                    "Mg": {"valence": 2, "mu0_RT": lig["Mg"]},
                    "Ca": {"valence": 2, "mu0_RT": lig["Ca"]}},
        "binders": binders,
        "moieties": {"adenine": {"nuc4": 1, "nuc3": 1}, "phosphate": {"nuc4": 3, "nuc3": 2,
                                                                      "pi2": 1}},
        "note": ("Seam C's registry: binder rows hold totals at their base form's valence; ligand "
                 "rows hold total equivalents counted from each base form. A form's charge is "
                 "z_base + Σ n z_L. pi2_PO4 sits below its base (a count of −1), admitted by §19 "
                 "item 6. Every constant is synthetic (D152 §2.4)."),
    }


REGISTRY_C = _registry_c()


# --------------------------------------------------------------------------------------------
# Seam A: diagrams built to satisfy detailed balance at the registry's potentials
# --------------------------------------------------------------------------------------------

def _mu(registry, s):
    return float(registry["species"][s]["mu0_RT"])


def _act(c_mM):
    return c_mM / C0_MM


def diagram(law_id, states, edges, cycles, rate_scale, note, ref):
    """Build a diagram law. ``states`` = [(name, G0/RT)]; each edge (id, i, j, binds, releases,
    Q, load, rate) with ``binds``/``releases`` lists of (species, end, order); Q the charge moved
    N → P going i → j, ``load`` its share in the forward exponent; ``rate`` the geometric mean of
    the two pseudo-first-order rates at the reference state ``ref`` (1/s). The standard free-energy
    change of i → j is ΔG°/RT = G0_j − G0_i + Σ_rel o μ°/RT − Σ_bind o μ°/RT, split evenly between
    the directions, so ln(k0_f/k0_b) = −ΔG°/RT for every edge and every cycle satisfies
    Wegscheider's condition by construction (to the rounding of the doubles)."""
    G0 = [g for _n, g in states]
    out_edges = []
    for eid, i, j, binds, rel, Q, load, rate in edges:
        dG = (G0[j] - G0[i] + sum(o * _mu(REGISTRY_A, s) for s, _e, o in rel) -
              sum(o * _mu(REGISTRY_A, s) for s, _e, o in binds))
        af = math.prod(_act(ref[e][s]) ** o for s, e, o in binds) if binds else 1.0
        ab = math.prod(_act(ref[e][s]) ** o for s, e, o in rel) if rel else 1.0
        kappa = rate / math.sqrt(af * ab)
        out_edges.append({
            "id": eid, "from": i, "to": j,
            "fwd": {"k0_per_s": kappa * math.exp(-0.5 * dG),
                    "orders": [[s, e, o] for s, e, o in binds], "zeta": load * Q},
            "bwd": {"k0_per_s": kappa * math.exp(0.5 * dG),
                    "orders": [[s, e, o] for s, e, o in rel], "zeta": -(1.0 - load) * Q},
        })
    return {"id": law_id, "kind": "diagram", "rate_scale_per_s": rate_scale,
            "states": [n for n, _g in states], "edges": out_edges,
            "cycles": [{"id": cid, "edges": [[e, d] for e, d in walk], "nu": [list(r) for r in nu]}
                       for cid, walk, nu in cycles],
            "note": note}


REF_PUMP = {"N": {"H": 10 ** (3 - 7.2), "ATP": 3.0, "ADP": 0.1, "Pi": 2.0},
            "P": {"H": 10 ** (3 - 6.0)}}
REF_EXCH = {"N": {"X": 10.0, "Y": 1e-4, "H": 10 ** (3 - 7.2)},
            "P": {"X": 140.0, "Y": 1.8, "H": 10 ** (3 - 7.4)}}
REF_FIG8 = {"N": {"X": 10.0, "Z": 2.0}, "P": {"X": 140.0, "Z": 2.0}}


def law_d1():
    return diagram(
        "d1_pump", [("E_N", 0.0), ("E_N.H2", -32.7), ("E_N.H2*", -16.7), ("E_P", 7.3)],
        [("e01", 0, 1, [("H", "N", 2)], [], 0.0, 0.5, 400.0),
         ("e12", 1, 2, [("ATP", "N", 1)], [("ADP", "N", 1), ("Pi", "N", 1)], 0.0, 0.5, 300.0),
         ("e23", 2, 3, [], [("H", "P", 2)], 2.0, 0.375, 500.0),
         ("e30", 3, 0, [], [], 0.0, 0.5, 200.0)],
        [("A", [("e01", 1), ("e12", 1), ("e23", 1), ("e30", 1)],
          [("H", "N", -2), ("H", "P", 2), ("ATP", "N", -1), ("ADP", "N", 1), ("Pi", "N", 1)])],
        1000.0, "D1: one cycle, an electrogenic ATP-driven pump moving 2 H+ N -> P", REF_PUMP)


def law_d2():
    zE = -2      # the empty carrier's charge
    return diagram(
        "d2_slip_exchanger",
        [("E_N", 0.0), ("E_N.Y", -11.62), ("E_P.Y", -11.62), ("E_P", -9.8), ("E_P.X3", -22.45),
         ("E_N.X3", -20.58)],
        [("e01", 0, 1, [("Y", "N", 1)], [], 0.0, 0.5, 800.0),
         ("e12", 1, 2, [], [], float(zE + 2), 0.5, 600.0),
         ("e23", 2, 3, [], [("Y", "P", 1)], 0.0, 0.5, 900.0),
         ("e34", 3, 4, [("X", "P", 3)], [], 0.0, 0.5, 700.0),
         ("e45", 4, 5, [], [], -float(zE + 3), 0.375, 500.0),
         ("e50", 5, 0, [], [("X", "N", 3)], 0.0, 0.5, 800.0),
         ("e03", 0, 3, [], [], float(zE), 0.5, 2e-3)],
        [("A", [("e01", 1), ("e12", 1), ("e23", 1), ("e34", 1), ("e45", 1), ("e50", 1)],
          [("Y", "N", -1), ("Y", "P", 1), ("X", "P", -3), ("X", "N", 3)]),
         ("B", [("e01", 1), ("e12", 1), ("e23", 1), ("e03", -1)],
          [("Y", "N", -1), ("Y", "P", 1)]),
         ("C", [("e03", 1), ("e34", 1), ("e45", 1), ("e50", 1)],
          [("X", "P", -3), ("X", "N", 3)])],
        1000.0, ("D2: a 6-state exchanger, 3 X+ in for 1 Y2+ out, with a slip edge (the empty "
                 "carrier crossing): three Hill cycles that share edges"), REF_EXCH)


def law_d3():
    return diagram(
        "d3_figure_eight",
        [("E", 0.0), ("E.X", -6.86), ("E_P", -4.51), ("E_P'", 0.3), ("E_P'.Z", -4.16)],
        [("e01", 0, 1, [("X", "N", 1)], [], 0.0, 0.5, 500.0),
         ("e12", 1, 2, [], [("X", "P", 1)], 1.0, 0.375, 400.0),
         ("e20", 2, 0, [], [], 0.0, 0.5, 300.0),
         ("e03", 0, 3, [], [], 0.0, 0.5, 250.0),
         ("e34", 3, 4, [("Z", "P", 1)], [], 0.0, 0.5, 450.0),
         ("e40", 4, 0, [], [("Z", "N", 1)], 0.0, 0.5, 350.0)],
        [("alpha", [("e01", 1), ("e12", 1), ("e20", 1)], [("X", "N", -1), ("X", "P", 1)]),
         ("beta", [("e03", 1), ("e34", 1), ("e40", 1)], [("Z", "P", -1), ("Z", "N", 1)])],
        1000.0, ("D3: two cycles sharing only a state (an X+ uniport and a neutral Z uniport): "
                 "the admitted basis, which is the full set"), REF_FIG8)


def law_d4():
    zE = -2
    return diagram(
        "d4_parallel_branches",
        [("E_N", 0.0), ("E_N.Y", -11.62), ("E_P.Y", -11.62), ("E_P", -9.8)],
        [("e01", 0, 1, [("Y", "N", 1)], [], 0.0, 0.5, 700.0),
         ("e12a", 1, 2, [], [], float(zE + 2), 0.5, 500.0),
         ("e12b", 1, 2, [("H", "N", 1)], [("H", "P", 1)], float(zE + 3), 0.375, 50.0),
         ("e23", 2, 3, [], [("Y", "P", 1)], 0.0, 0.5, 800.0),
         ("e30", 3, 0, [], [], -float(zE), 0.5, 300.0)],
        [("K1", [("e01", 1), ("e12a", 1), ("e23", 1), ("e30", 1)],
          [("Y", "N", -1), ("Y", "P", 1)]),
         ("K2", [("e01", 1), ("e12b", 1), ("e23", 1), ("e30", 1)],
          [("Y", "N", -1), ("Y", "P", 1), ("H", "N", -1), ("H", "P", 1)]),
         ("K3", [("e12a", 1), ("e12b", -1)], [("H", "P", -1), ("H", "N", 1)])],
        1000.0, ("D4: parallel branches between two states (one co-transports H+), giving three "
                 "Hill cycles; the 2-cycle K3 is the branches' slip"), REF_EXCH)


# --------------------------------------------------------------------------------------------
# Seam A: the version-1 laws (factored), a planted S < 0, and the guard's net-flow laws
# --------------------------------------------------------------------------------------------

def law_v1_proton(n=2):
    return {"id": f"v1_proton_n{n}", "kind": "factored",
            "law_id": "cells.proton_atp_mass_action_positive@1",
            "parameters": {"n": n, "K_H_mM": 10 ** (3 - 7.0), "K_ATP_mM": 0.1},
            "modes": [{"id": "cyc",
                       "nu": [["H", "N", -n], ["H", "P", n], ["ATP", "N", -1], ["ADP", "N", 1],
                              ["Pi", "N", 1]],
                       "saturation": [{"species": "H", "end": "N", "K_mM": 10 ** (3 - 7.0),
                                       "hill": n},
                                      {"species": "ATP", "end": "N", "K_mM": 0.1, "hill": 1}]}],
            "note": ("COMPARTMENT_PH_TRANSFER_DESIGN §6: J = k a S (1 − e^{ΔG/RT}), "
                     "S = [1 + (K_H/h_N)^n]^-1 [1 + K_ATP/c_ATP]^-1, N the inside (fuel) end")}


def law_v1_neutral(n=1, offset=None):
    law = {"id": f"v1_neutral_n{n}" if offset is None else f"planted_negative_S_n{n}",
           "kind": "factored", "law_id": "cells.atp_driven_transporter_mass_action_positive@1",
           "parameters": {"n": n, "K_Y_mM": 1.0, "K_ATP_mM": 0.1},
           "modes": [{"id": "cyc",
                      "nu": [["Z", "N", -n], ["Z", "P", n], ["ATP", "N", -1], ["ADP", "N", 1],
                             ["Pi", "N", 1]],
                      "saturation": [{"species": "Z", "end": "N", "K_mM": 1.0, "hill": n},
                                     {"species": "ATP", "end": "N", "K_mM": 0.1, "hill": 1}]}],
           "note": ("R-fuel's statement (validation/compartment_ph/REFERENCES_USAGE.md): §6's form "
                    "with a neutral solute (here Z) in place of H+ and no voltage term")}
    if offset is not None:
        law["modes"][0]["planted_S_offset"] = offset
        law["note"] = (f"PLANTED: the neutral law with S − {offset}, negative wherever "
                       f"S < {offset}; the kind must refuse those states")
    return law


NU_A = [["Y", "N", -1], ["Y", "P", 1], ["X", "P", -3], ["X", "N", 3]]
NU_B = [["Y", "N", -1], ["Y", "P", 1]]
NU_C = [["X", "P", -3], ["X", "N", 3]]
NU_LEAK = [["X", "P", -1], ["X", "N", 1]]


def guard_laws():
    return [
        {"id": "fb_shift", "kind": "net_flow",
         "modes": [{"id": "ex", "nu": NU_A,
                    "flux_terms": [{"capacity_fmol_per_s": 0.05, "cycle_nu": NU_A,
                                    "shift_psi": 0.2}]}],
         "note": ("PLANTED (net-flow mode): J = k (1 − exp(ΔG/RT + 0.2 ψ)), an effective charge "
                  "1.2 against the mode's 1, booked in the 3:1 stoichiometry. J ΔG > 0 in the "
                  "band between ΔG = 0 and ΔG/RT = −0.2 ψ")},
        {"id": "fb_masked", "kind": "net_flow",
         "modes": [{"id": "ex", "nu": NU_A,
                    "flux_terms": [{"capacity_fmol_per_s": 0.05, "cycle_nu": NU_A,
                                    "shift_psi": 0.2}]},
                   {"id": "leak", "nu": NU_LEAK,
                    "flux_terms": [{"capacity_fmol_per_s": 2.5, "cycle_nu": NU_LEAK}]}],
         "note": ("PLANTED (net-flow mode): fb_shift's exchange beside an admitted X+ leak 50 "
                  "times its capacity. The exchange runs against its ΔG in the band, but the "
                  "population's total stays dissipative: the guard cannot see it")},
        {"id": "fb_basis", "kind": "net_flow",
         "modes": [{"id": "A", "nu": NU_A,
                    "flux_terms": [{"capacity_fmol_per_s": 0.02, "cycle_nu": NU_A},
                                   {"capacity_fmol_per_s": 0.08, "cycle_nu": NU_C}]},
                   {"id": "B", "nu": NU_B,
                    "flux_terms": [{"capacity_fmol_per_s": 0.01, "cycle_nu": NU_B},
                                   {"capacity_fmol_per_s": -0.08, "cycle_nu": NU_C}]}],
         "note": ("CONTROL (net-flow mode): the cycles A, B and C = A − B booked in the basis "
                  "{A, B}, as J_A + J_C and J_B − J_C with each J_x = k_x (1 − e^{ΔG_x/RT}). A "
                  "mode runs against its own ΔG at some states while Σ J ΔG ≤ 0 everywhere: the "
                  "guard must not fire")},
    ]


# --------------------------------------------------------------------------------------------
# Seam A: planted diagram variants (Wegscheider) and declared bases
# --------------------------------------------------------------------------------------------

def _edge(law, eid):
    return next(e for e in law["edges"] if e["id"] == eid)


def plant_constant(law, eid, factor, tag):
    w = copy.deepcopy(law)
    w["id"] = f"{law['id']}__k_{tag}"
    _edge(w, eid)["fwd"]["k0_per_s"] *= factor
    w["note"] = f"PLANTED: {eid}'s forward k0 × {factor!r} (a wrong constant)"
    return w


def plant_charge(law, eid, dq):
    w = copy.deepcopy(law)
    w["id"] = f"{law['id']}__charge"
    _edge(w, eid)["fwd"]["zeta"] += dq
    w["note"] = (f"PLANTED: {eid}'s voltage exponent moves {dq!r} more charge N -> P than its "
                 f"cycles carry (a wrong voltage exponent; zero at V = 0)")
    return w


def plant_order(law, eid, direction, species, end):
    w = copy.deepcopy(law)
    w["id"] = f"{law['id']}__conc"
    r = _edge(w, eid)[direction]
    for row in r["orders"]:
        if row[0] == species and row[1] == end:
            row[2] -= 1
    r["orders"] = [row for row in r["orders"] if row[2] != 0]
    w["note"] = (f"PLANTED: {eid}'s {direction} rate lacks one factor of a({species}@{end}) (a "
                 f"wrong concentration exponent; zero where that activity is 1, c = c°)")
    return w


def plant_swap(law, eid, direction, species):
    w = copy.deepcopy(law)
    w["id"] = f"{law['id']}__swap"
    r = _edge(w, eid)[direction]
    for row in r["orders"]:
        if row[0] == species:
            row[1] = "P" if row[1] == "N" else "N"
    w["note"] = (f"PLANTED: {eid}'s {direction} rate reads {species} at the wrong end (zero where "
                 f"the two ends' activities are equal)")
    return w


def declared_basis(law, keep, tag):
    w = copy.deepcopy(law)
    w["id"] = f"{law['id']}__basis_{tag}"
    w["cycles"] = [c for c in w["cycles"] if c["id"] in keep]
    w["note"] = (f"PLANTED: declares only the basis {sorted(keep)}; its cycles share an edge, so "
                 f"it must be refused (§16)")
    return w


def planted_diagrams(d1, d2, d3, d4) -> list:
    out = []
    for law, k_edge, q_edge, conc, swap in (
            (d1, "e12", "e23", ("e01", "fwd", "H", "N"), ("e23", "bwd", "H")),
            (d2, "e12", "e45", ("e34", "fwd", "X", "P"), ("e01", "fwd", "Y")),
            (d3, "e12", "e12", ("e34", "fwd", "Z", "P"), ("e40", "bwd", "Z")),
            (d4, "e12b", "e12a", ("e01", "fwd", "Y", "N"), ("e12b", "fwd", "H"))):
        out.append(plant_constant(law, k_edge, 1.01, "1pct"))
        out.append(plant_constant(law, k_edge, 1.0 + 1e-6, "1e-6"))
        out.append(plant_charge(law, q_edge, 0.2))
        out.append(plant_order(law, *conc))
        out.append(plant_swap(law, *swap))
    out.append(declared_basis(d2, {"A", "B"}, "AB"))
    out.append(declared_basis(d4, {"K1", "K2"}, "K1K2"))
    return out


PARSE_PLANTS = [
    {"id": "mode_species_unbalanced", "registry": "A",
     "nu": [["X", "N", -1], ["X", "P", 2]],
     "note": "PLANTED: one X+ leaves N and two arrive at P (charge +1, X +1)"},
    {"id": "mode_moiety_unbalanced", "registry": "A",
     "nu": [["ATP", "N", -1], ["ADP", "N", 1], ["H", "N", -2], ["H", "P", 2]],
     "note": "PLANTED: ATP -> ADP without Pi (charge 0 in neutral rows; phosphate −1)"},
    {"id": "mode_base_forms_no_proton", "registry": "C",
     "nu": [["nuc4", "N", -1], ["nuc3", "N", 1], ["pi2", "N", 1]],
     "note": ("PLANTED: hydrolysis in base forms with its scalar proton omitted (charge −1; "
              "adenine and phosphate balance)")},
    {"id": "mode_base_forms_hydrolysis", "registry": "C",
     "nu": [["nuc4", "N", -1], ["nuc3", "N", 1], ["pi2", "N", 1], ["H", "N", 1]],
     "note": "CONTROL: hydrolysis in base forms with every ligand written out (admitted)"},
]


# --------------------------------------------------------------------------------------------
# Seam A: states on the host (a = the population's cell, b = the outside node)
# --------------------------------------------------------------------------------------------

DOMAINS = {   # per law family: (species, host end, lo, hi, scale); V_a − V_b uniform in volts
    "pump": [("H", "a", 6.8, 7.6, "pH"), ("H", "b", 4.5, 7.0, "pH"), ("ATP", "a", 1.0, 8.0, "log"),
             ("ADP", "a", 0.02, 2.0, "log"), ("Pi", "a", 0.5, 15.0, "log"),
             ("ATP", "b", 0.1, 1.0, "log"), ("ADP", "b", 0.5, 3.0, "log"),
             ("Pi", "b", 0.5, 3.0, "log")],
    "exch": [("X", "a", 4.0, 30.0, "log"), ("X", "b", 100.0, 160.0, "log"),
             ("Y", "a", 5e-5, 5e-3, "log"), ("Y", "b", 0.5, 3.0, "log"),
             ("H", "a", 6.8, 7.6, "pH"), ("H", "b", 6.5, 7.8, "pH")],
    "fig8": [("X", "a", 4.0, 30.0, "log"), ("X", "b", 100.0, 160.0, "log"),
             ("Z", "a", 0.1, 10.0, "log"), ("Z", "b", 0.1, 10.0, "log")],
    "neutral": [("Z", "a", 0.5, 20.0, "log"), ("Z", "b", 0.5, 50.0, "log"),
                ("ATP", "a", 0.05, 8.0, "log"), ("ADP", "a", 0.02, 2.0, "log"),
                ("Pi", "a", 0.5, 15.0, "log"), ("ATP", "b", 0.1, 1.0, "log"),
                ("ADP", "b", 0.5, 3.0, "log"), ("Pi", "b", 0.5, 3.0, "log")],
}
V_RANGE = (-0.12, 0.06)
# Amendment 1 (18 November 2026): D2 with N = b reads its N end at the host's b, so its host states
# carry the exchange family's ends swapped, and the voltage range is mirrored (φ_N − φ_P = −V).
DOMAINS["exch_Nb"] = [(s, "b" if end == "a" else "a", lo, hi, scale)
                      for s, end, lo, hi, scale in DOMAINS["exch"]]
V_RANGE_NB = (-0.06, 0.12)
N_RANDOM = 12
OFFSETS = (0.0, 1e-9, -1e-9, 1e-4, -1e-4, 1.0, -1.0)
FAR = (-25.0, 25.0)


def random_states(rng, family, n=N_RANDOM, v_range=V_RANGE) -> list:
    out = []
    for _ in range(n):
        c = {"a": {}, "b": {}}
        for s, end, lo, hi, scale in DOMAINS[family]:
            if scale == "pH":
                c[end][s] = 10.0 ** (3.0 - float(rng.uniform(lo, hi)))
            else:
                c[end][s] = float(np.exp(rng.uniform(math.log(lo), math.log(hi))))
        out.append({"phi_V": {"a": float(rng.uniform(*v_range)), "b": 0.0}, "c_mM": c})
    return out


def _dG_RT_float(nu, registry, st, orientation_N="a"):
    """ΔG/RT of a mode at a host state in doubles (only used to place the states)."""
    F = 96485.33212331001
    R = 8.31446261815324
    pend = "b" if orientation_N == "a" else "a"
    ends = {"N": orientation_N, "P": pend}
    g = 0.0
    for s, e, n in nu:
        sp = registry["species"][s]
        he = ends[e]
        g += n * (sp["mu0_RT"] + math.log(st["c_mM"][he][s] / C0_MM) +
                  sp["valence"] * F * st["phi_V"][he] / (R * T_K))
    return g


def placed(nu, registry, base, target, family_neutral_species=None, orientation_N="a"):
    """A copy of ``base`` with ΔG/RT of the mode moved to ``target``: by the voltage for a charged
    mode, or by the P-end concentration of ``family_neutral_species`` for a neutral one."""
    F = 96485.33212331001
    R = 8.31446261815324
    st = copy.deepcopy(base)
    nq = sum(registry["species"][s]["valence"] * n for s, e, n in nu if e == "P")
    g = _dG_RT_float(nu, registry, st, orientation_N)
    sign = 1.0 if orientation_N == "a" else -1.0      # φ_N − φ_P = ±(φ_a − φ_b)
    if nq != 0:
        # ΔG/RT = chem − n_q F (φ_N − φ_P)/RT
        st["phi_V"]["a"] = st["phi_V"]["a"] + sign * (g - target) * R * T_K / (nq * F)
    else:
        s = family_neutral_species
        pend = "b" if orientation_N == "a" else "a"
        nP = sum(n for sp, e, n in nu if sp == s and e == "P")
        st["c_mM"][pend][s] = st["c_mM"][pend][s] * math.exp((target - g) / nP)
    return st


def states_for(law, family, rng, neutral_species=None, orientation_N="a",
               v_range=V_RANGE) -> list:
    """Random states, then every mode's equilibrium neighbourhood and two far states."""
    rnd = random_states(rng, family, v_range=v_range)
    out = [dict(s, tag=f"random_{k}") for k, s in enumerate(rnd)]
    modes = law["cycles"] if law["kind"] == "diagram" else law["modes"]
    for m in modes:
        for off in OFFSETS:
            st = placed(m["nu"], REGISTRY_A, rnd[0], off, neutral_species, orientation_N)
            st["tag"] = f"near_{m['id']}_{off:+g}"
            out.append(st)
    m0 = modes[0]
    for far in FAR:
        st = placed(m0["nu"], REGISTRY_A, rnd[1], far, neutral_species, orientation_N)
        st["tag"] = f"far_{m0['id']}_{far:+g}"
        out.append(st)
    return out


def unit_state(family) -> dict:
    """Every activity 1 (c = c°) and ψ = 0: the one reference state at which a voltage- or a
    concentration-exponent plant has a zero residual (§19 item 2: never decide there alone)."""
    c = {"a": {}, "b": {}}
    for s, end, *_r in DOMAINS[family]:
        c[end][s] = C0_MM
    return {"phi_V": {"a": 0.0, "b": 0.0}, "c_mM": c, "tag": "unit_activity_zero_voltage"}


def band_states(law, rng) -> list:
    """fb_shift's band: for base concentrations, the true reversal ψ_eq (ΔG = 0) and the law's
    own zero ψ_z (ΔG/RT + 0.2 ψ = 0), their edges, the middle, and states outside the band."""
    F = 96485.33212331001
    R = 8.31446261815324
    out = []
    base = random_states(rng, "exch", 4)
    for k, b in enumerate(base):
        b = copy.deepcopy(b)
        b["phi_V"]["a"] = 0.0
        chem = _dG_RT_float(NU_A, REGISTRY_A, b)           # ΔG/RT at ψ = 0
        # n_q = −1: ΔG/RT = chem + ψ; the law's zero: chem + 1.2 ψ = 0
        psi_eq, psi_z = -chem, -chem / 1.2
        for name, ps in (("eq", psi_eq), ("eq_inside", psi_eq + 1e-6 * (psi_z - psi_eq)),
                         ("mid", 0.5 * (psi_eq + psi_z)),
                         ("z_inside", psi_z - 1e-6 * (psi_z - psi_eq)), ("z", psi_z),
                         ("outside_eq", psi_eq - 0.3 * (psi_z - psi_eq)),
                         ("outside_z", psi_z + 0.3 * (psi_z - psi_eq))):
            st = copy.deepcopy(b)
            st["phi_V"]["a"] = ps * R * T_K / F
            st["tag"] = f"band{k}_{name}"
            out.append(st)
    return out


def v1_states(law, rng, family, neutral_species=None) -> list:
    rnd = random_states(rng, family)
    out = [dict(s, tag=f"random_{k}") for k, s in enumerate(rnd)]
    m = law["modes"][0]
    for off in (0.0, 1e-6, -1e-6, 1e-3, -1e-3, 0.1, -0.1, 1.0, -1.0):
        st = placed(m["nu"], REGISTRY_A, rnd[0], off, neutral_species)
        st["tag"] = f"static_head_{off:+g}"
        out.append(st)
    for far in (-15.0, -5.0):
        st = placed(m["nu"], REGISTRY_A, rnd[1], far, neutral_species)
        st["tag"] = f"far_{far:+g}"
        out.append(st)
    return out


POP_DIAGRAM = {"capacity_fmol_per_s": 0.1, "availability": 0.8, "orientation": {"N": "a"}}
VOLUMES_PL = {"a": 2.0, "b": 0.25}


def seam_a(rng) -> dict:
    d1, d2, d3, d4 = law_d1(), law_d2(), law_d3(), law_d4()
    laws = [d1, d2, d3, d4, law_v1_proton(2), law_v1_neutral(1), law_v1_neutral(2),
            law_v1_neutral(1, offset=0.05)] + guard_laws()
    planted = planted_diagrams(d1, d2, d3, d4)
    families = {"d1_pump": "pump", "d2_slip_exchanger": "exch", "d3_figure_eight": "fig8",
                "d4_parallel_branches": "exch"}
    states = {}
    for law in (d1, d2, d3, d4):
        fam = families[law["id"]]
        st = states_for(law, fam, rng, "Z" if fam == "fig8" else None)
        st.append(unit_state(fam))
        states[law["id"]] = st
    states["v1_proton_n2"] = v1_states(laws[4], rng, "pump")
    states["v1_neutral_n1"] = v1_states(laws[5], rng, "neutral", "Z")
    states["v1_neutral_n2"] = v1_states(laws[6], rng, "neutral", "Z")
    st = random_states(rng, "neutral", 12)
    for k, s in enumerate(st):
        s["tag"] = f"random_{k}"
    st[0]["c_mM"]["a"]["Z"] = 0.02          # S below the plant's offset: Z far below K_Y
    st[1]["c_mM"]["a"]["ATP"] = 0.004       # ATP far below K_ATP
    states["planted_negative_S_n1"] = st
    gst = band_states(None, rng)
    rnd = random_states(rng, "exch", 6)
    for k, s in enumerate(rnd):
        s["tag"] = f"random_{k}"
    for law in guard_laws():
        states[law["id"]] = copy.deepcopy(gst + rnd)
    populations = {}
    for law in laws:
        pop = dict(POP_DIAGRAM)
        if law["kind"] == "factored":
            pop = {"capacity_fmol_per_s": 0.2, "availability": 0.75, "orientation": {"N": "a"},
                   "held_rows": [["ATP", "a"], ["ADP", "a"], ["Pi", "a"]]}
        if law["kind"] == "net_flow":
            pop = {"capacity_fmol_per_s": 1.0, "availability": 1.0, "orientation": {"N": "a"}}
        if law["kind"] == "diagram" and law["id"] == "d1_pump":
            pop = dict(POP_DIAGRAM, held_rows=[["ATP", "a"], ["ADP", "a"], ["Pi", "a"]])
        populations[law["id"]] = pop
    return {"registry": REGISTRY_A, "laws": laws, "planted_laws": planted,
            "parse_plants": PARSE_PLANTS, "states": states, "populations": populations,
            "volumes_pL": VOLUMES_PL,
            "generic_states": {law["id"]: generic_count(law) for law in (d1, d2, d3, d4)},
            "plant_states": {p["id"]: p["id"].split("__")[0] for p in planted}}


def generic_count(law) -> int:
    """d + 1: the number of distinct (species, end) activities in the rates and modes, plus ψ, plus
    the constant. The first d + 1 random states are the generic set."""
    keys = set()
    for e in law["edges"]:
        for side in ("fwd", "bwd"):
            for s, end, _o in e[side].get("orders", []):
                keys.add((s, end))
    for c in law["cycles"]:
        for s, end, _n in c["nu"]:
            keys.add((s, end))
    return len(keys) + 2


# --------------------------------------------------------------------------------------------
# Seam C: systems, states (manufactured), P1's nodes and the movers
# --------------------------------------------------------------------------------------------

SYSTEMS = {
    "S1": {"ligands": ["H"], "binders": ["buf1"], "volume_pL": 1.0,
           "note": "one ligand and one binder (B4's case)", "designated": "buf1_H"},
    "S2": {"ligands": ["H"], "binders": ["buf1", "buf2"], "volume_pL": 0.5,
           "note": "one ligand, two binders", "designated": "buf2_H"},
    "S3": {"ligands": ["H", "Mg"], "binders": ["nuc4"], "volume_pL": 1.0,
           "note": "two ligands on one binder, with a form holding both", "designated": "nuc4_MgH"},
    "S4": {"ligands": ["H", "Mg"], "binders": ["nuc4", "nuc3", "pi2"], "volume_pL": 2.0,
           "note": "two ligands, three binders, a form below its base (pi2_PO4)",
           "designated": "nuc4_MgH"},
    "S5": {"ligands": ["H", "Ca"], "binders": ["buf1", "cab0"], "volume_pL": 1.0,
           "note": "two disjoint ligand sets at one node", "designated": "cab0_Ca",
           "parts": [{"ligands": ["H"], "binders": ["buf1"]},
                     {"ligands": ["Ca"], "binders": ["cab0"]}]},
    "S6": {"ligands": ["H", "Mg", "Ca"], "binders": ["nuc4", "cabuf"], "volume_pL": 1.0,
           "note": "three ligands connected through shared binders", "designated": "cabuf_CaH"},
}
FREE_RANGES = {"H": ("pH", 5.5, 8.5), "Mg": ("log", 0.01, 5.0), "Ca": ("log", 1e-5, 1e-2)}
TOTAL_RANGES_MM = {"buf1": (1.0, 60.0), "buf2": (1.0, 30.0), "nuc4": (0.5, 10.0),
                   "nuc3": (0.02, 2.0), "pi2": (0.5, 20.0), "cab0": (0.01, 2.0),
                   "cabuf": (0.1, 10.0)}
HARD = {   # (tag, free concentrations mM, binder concentrations mM)
    "S1": [("mostly_bound", {"H": 10 ** (3 - 8.4)}, {"buf1": 60.0}),
           ("saturated_binder", {"H": 10 ** (3 - 4.0)}, {"buf1": 60.0}),
           ("trace_binder", {"H": 10 ** (3 - 7.0)}, {"buf1": 1e-3})],
    "S2": [("mostly_bound", {"H": 10 ** (3 - 8.3)}, {"buf1": 50.0, "buf2": 30.0})],
    "S3": [("mg_mostly_bound", {"H": 10 ** (3 - 7.2), "Mg": 1e-4}, {"nuc4": 10.0}),
           ("mg_saturating", {"H": 10 ** (3 - 7.2), "Mg": 40.0}, {"nuc4": 10.0})],
    "S4": [("high_pH_negative_total", {"H": 10 ** (3 - 11.0), "Mg": 0.5},
            {"nuc4": 5.0, "nuc3": 0.5, "pi2": 20.0}),
           ("acidic", {"H": 10 ** (3 - 5.0), "Mg": 2.0}, {"nuc4": 8.0, "nuc3": 1.0, "pi2": 10.0})],
    "S5": [("ca_mostly_bound", {"H": 10 ** (3 - 7.2), "Ca": 1e-5}, {"buf1": 40.0, "cab0": 2.0})],
    "S6": [("ca_mostly_bound", {"H": 10 ** (3 - 7.2), "Mg": 0.8, "Ca": 1e-6},
            {"nuc4": 5.0, "cabuf": 10.0})],
}
N_RANDOM_C = 10
P1_NODES = {
    "P1a": {"system": {"ligands": ["H"], "binders": ["buf1"]}, "volume_pL": 0.05,
            "free_mM": {"H": 10 ** (3 - 7.2)}, "binders_mM": {"buf1": 40.0}, "ligand": "H",
            "note": "a buffered outside node: 40 mM of a pK 7.0 buffer at pH 7.2"},
    "P1b": {"system": {"ligands": ["H", "Mg"], "binders": ["nuc4", "nuc3", "pi2", "buf1"]},
            "volume_pL": 0.05, "free_mM": {"H": 10 ** (3 - 7.4), "Mg": 0.8},
            "binders_mM": {"nuc4": 5.0, "nuc3": 0.5, "pi2": 10.0, "buf1": 20.0}, "ligand": "H",
            "note": "the same draw from a node holding H+ and Mg2+ under one closure"},
}
MOVERS = [
    {"id": "base_form_hydrolysis", "declares_base_forms": True,
     "nu": [["nuc4", "N", -1], ["nuc3", "N", 1], ["pi2", "N", 1], ["H", "N", 1]],
     "expected": "admitted", "note": "every ligand written out"},
    {"id": "base_form_hydrolysis_no_proton", "declares_base_forms": True,
     "nu": [["nuc4", "N", -1], ["nuc3", "N", 1], ["pi2", "N", 1]],
     "expected": "refused", "note": "PLANTED: the scalar proton omitted (charge −1)"},
    {"id": "mgatp_written_out", "declares_base_forms": True,
     "nu": [["nuc4", "N", -1], ["Mg", "N", -1], ["nuc4", "P", 1], ["Mg", "P", 1]],
     "expected": "admitted", "note": "MgATP moved as its base form and its ligand"},
    {"id": "mgatp_as_a_unit", "declares_base_forms": True,
     "nu": [["nuc4_Mg", "N", -1], ["nuc4_Mg", "P", 1]],
     "expected": "refused", "note": "PLANTED: a form moved as if it were a row"},
    {"id": "undeclared_mover", "declares_base_forms": False,
     "nu": [["nuc4", "N", -1], ["nuc4", "P", 1]],
     "expected": "refused", "note": "PLANTED: a mover of a multi-form row that declares no forms"},
]


def seam_c(rng) -> dict:
    states = {}
    for name, sysd in SYSTEMS.items():
        out = []
        for k in range(N_RANDOM_C):
            free = {}
            for L in sysd["ligands"]:
                kind, lo, hi = FREE_RANGES[L]
                free[L] = (10.0 ** (3.0 - float(rng.uniform(lo, hi))) if kind == "pH"
                           else float(np.exp(rng.uniform(math.log(lo), math.log(hi)))))
            tot = {}
            for B in sysd["binders"]:
                lo, hi = TOTAL_RANGES_MM[B]
                tot[B] = float(np.exp(rng.uniform(math.log(lo), math.log(hi))))
            out.append({"tag": f"random_{k}", "free_mM": free, "binders_mM": tot})
        for tag, free, tot in HARD.get(name, []):
            out.append({"tag": tag, "free_mM": dict(free), "binders_mM": dict(tot)})
        states[name] = out
    return {"registry": REGISTRY_C, "systems": SYSTEMS, "manufactured_states": states,
            "p1_nodes": P1_NODES, "movers": MOVERS}


def totals_from_manufactured(system_spec, st, volume):
    """The registered totals (doubles) of a manufactured state, computed exactly then rounded."""
    from . import binding
    sy = binding.System(system_spec, REGISTRY_C)
    tB = {B: st["binders_mM"][B] * volume for B in system_spec["binders"]}
    TL = binding.manufacture(sy, st["free_mM"], tB, volume)
    return {"ligands_fmol": {L: float(v) for L, v in TL.items()},
            "binders_fmol": {B: float(v) for B, v in tB.items()}}


def amendment_1(a: dict, rng) -> None:
    """CORE_SEAMS_DESIGN §19, amended the same evening: two blind spots registered before A's first
    output, drawn after every earlier input so that nothing registered before moves.
    - ``ff_neutral_n1``: the neutral law on finite fuel rows (ATP, ADP and Pi moved at its fuel
      end, finite_fuel_rows@1), so the stored rate, the moved rows' standard part in @3's 1 mM
      frame (§3.4; COMPARTMENT_PH_TRANSFER_DESIGN §17.2), has power;
    - ``d2_slip_exchanger_Nb``: D2 with N = b, the host's outside end as N."""
    ff = law_v1_neutral(1)
    ff["id"] = "ff_neutral_n1"
    ff["note"] = ("AMENDMENT 1: the neutral law on finite fuel rows (finite_fuel_rows@1): ATP, ADP "
                  "and Pi are moved at N = a, nothing is held, and the stored rate is the moved "
                  "rows' standard part, RT (Σ ν μ°/RT − (Σ ν) ln c°) per cycle (§3.4)")
    nb = law_d2()
    nb["id"] = "d2_slip_exchanger_Nb"
    nb["note"] = ("AMENDMENT 1: D2 with N = b (the outside node as N); its host states are the "
                  "exchange family's with the ends swapped")
    a["laws"] += [ff, nb]
    a["states"]["ff_neutral_n1"] = v1_states(ff, rng, "neutral", "Z")
    st = states_for(nb, "exch_Nb", rng, orientation_N="b", v_range=V_RANGE_NB)
    st.append(unit_state("exch_Nb"))
    a["states"]["d2_slip_exchanger_Nb"] = st
    a["populations"]["ff_neutral_n1"] = {"capacity_fmol_per_s": 0.2, "availability": 0.75,
                                         "orientation": {"N": "a"}}
    a["populations"]["d2_slip_exchanger_Nb"] = dict(POP_DIAGRAM, orientation={"N": "b"})
    a["generic_states"]["d2_slip_exchanger_Nb"] = generic_count(nb)
    a["amendments"] = [{"date": "2026-11-18", "id": "amendment_1",
                        "before_engine_output": True,
                        "added": ["ff_neutral_n1", "d2_slip_exchanger_Nb"],
                        "ruling": "CORE_SEAMS_DESIGN §19, amended the same evening"}]


def amendment_c2(c: dict) -> None:
    """Amendment C2 (§19, amended at 19:52 UTC): S4 gains one state, appended, where the H total
    nearly cancels (T_H ≈ 1e-9 V A_H): the bound protons of nuc4, nuc3 and pi2_H against pi2_PO4's
    count of −1. There the scale |T_L| and the scale V A_L part by 1e9. The pH is found by
    bisection on the exact manufactured T_H; the other free values are S4[10]'s."""
    from decimal import Decimal

    from . import binding, exact
    sysd = SYSTEMS["S4"]
    spec = {"ligands": sysd["ligands"], "binders": sysd["binders"]}
    sy = binding.System(spec, REGISTRY_C)
    V = sysd["volume_pL"]
    bm = {"nuc4": 5.0, "nuc3": 0.5, "pi2": 20.0}
    tB = {B: bm[B] * V for B in sysd["binders"]}

    def totals(pH):
        """The exact H total and V A_H of the forward (manufactured) speciation: no solve."""
        free = {"H": 10.0 ** (3.0 - pH), "Mg": 0.5}
        TL = binding.manufacture(sy, free, tB, V)
        with exact.context():
            u = {L: (Decimal(free[L]) / sy.c0).ln() for L in sy.ligands}
            _E, W = sy._weights(u)
            forms = {B: {f["id"]: Decimal(tB[B]) / Decimal(V) * w / sum(W[B], Decimal(0))
                         for f, w in zip(sy.forms[B], W[B], strict=True)}
                     for B in sy.binders}
            A = binding.residual_scale(sy, {"x_mM": {L: Decimal(free[L]) for L in sy.ligands},
                                            "forms_mM": forms}, V)
        return TL["H"], A["H"], free

    lo, hi = 8.0, 11.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        T, A, _f = totals(mid)
        if T > Decimal("1e-9") * A:
            lo = mid
        else:
            hi = mid
    pH = lo
    _T, _A, free = totals(pH)
    st = {"tag": "near_zero_H_total", "free_mM": free, "binders_mM": dict(bm),
          "amendment": "C2"}
    st["totals"] = totals_from_manufactured(spec, st, V)
    c["manufactured_states"]["S4"].append(st)


ENVELOPE_BUDGET_PH = 1e-3
ENVELOPE_RECORD_SLOW_TIMES = [0.5, 2.0, 8.0, 16.0]


def amendment_c3(c: dict) -> None:
    """Amendment C3 (§19 amended at 19:52 UTC): the two-ligand kinetic reference for the envelope.
    Each case is a closed node at the closure's state, with k_on per (binder, ligand) (D175's
    stand-in parameter, the closure's declaration) and a constant drive (fmol/s) on free ligands or
    on a binder's base form. Every value is synthetic (D152 §2.4)."""
    from . import binding

    def case(tag, ligands, binders, V, free, bm, kon, drive, note):
        spec = {"ligands": ligands, "binders": binders}
        tB = {B: bm[B] * V for B in binders}
        st = totals_from_manufactured(spec, {"free_mM": free, "binders_mM": bm}, V)
        assert st["binders_fmol"] == {B: float(v) for B, v in tB.items()}
        binding.System(spec, REGISTRY_C)               # parses
        return tag, {"ligands": ligands, "binders": binders, "volume_pL": V, "free_mM": free,
                     "binders_mM": bm, "totals": st,
                     "kon_per_mM_per_s": [[B, L, k] for (B, L), k in kon.items()],
                     "drive_fmol_per_s": [[k, v] for k, v in drive.items()],
                     "record_slow_times": ENVELOPE_RECORD_SLOW_TIMES, "note": note}

    chain = {("coop2", "H"): 1e7, ("coop2", "Mg"): 1e4}
    cases = dict([
        case("E0_b4", ["H"], ["buf1"], 0.05, {"H": 10 ** (3 - 7.2)}, {"buf1": 40.0},
             {("buf1", "H"): 1e5}, {"H": 1e-4},
             "one ligand and one two-form buffer: the general lag must equal B4's formula"),
        case("E1_chain", ["H", "Mg"], ["coop2"], 1.0, {"H": 1e-4, "Mg": 0.5}, {"coop2": 5.0},
             chain, {"H": 3e-5},
             ("the cooperative chain: its slowest mode is slower than every single step; the true "
              "lag is outside the 1e-3 pH budget while a per-step minimum puts it inside")),
        case("E1_chain_small", ["H", "Mg"], ["coop2"], 1.0, {"H": 1e-4, "Mg": 0.5},
             {"coop2": 5.0}, chain, {"H": 3e-6},
             ("E1_chain at a tenth of the drive: the kinetic lag meets the first order at "
              "second order")),
        case("E1_chain_kon10", ["H", "Mg"], ["coop2"], 1.0, {"H": 1e-4, "Mg": 0.5},
             {"coop2": 5.0}, {k: 10 * v for k, v in chain.items()}, {"H": 3e-5},
             "E1_chain with every k_on ten times larger: the lag falls tenfold"),
        case("E1_chain_kon100", ["H", "Mg"], ["coop2"], 1.0, {"H": 1e-4, "Mg": 0.5},
             {"coop2": 5.0}, {k: 100 * v for k, v in chain.items()}, {"H": 3e-5},
             "E1_chain with every k_on a hundred times larger: the closure is the limit"),
        case("E1_chain_two_drives", ["H", "Mg"], ["coop2"], 1.0, {"H": 1e-4, "Mg": 0.5},
             {"coop2": 5.0}, chain, {"H": 3e-6, "Mg": 1e-3},
             "E1_chain driven in both ligands: the Mg²⁺ steps and the coupling through the base"),
        case("E2_nuc4", ["H", "Mg"], ["nuc4"], 1.0, {"H": 10 ** (3 - 7.2), "Mg": 0.5},
             {"nuc4": 5.0}, {("nuc4", "H"): 1e7, ("nuc4", "Mg"): 1e4}, {"H": 1e-3, "Mg": 1e-3},
             "a two-ligand binder without a bottleneck: a per-step minimum is conservative here"),
        case("E2_nuc4_binder_drive", ["H", "Mg"], ["nuc4"], 1.0, {"H": 10 ** (3 - 7.2), "Mg": 0.5},
             {"nuc4": 5.0}, {("nuc4", "H"): 1e7, ("nuc4", "Mg"): 1e4}, {"nuc4": 1e-3},
             "E2 with its binder's base form moved in (a moved binder row)"),
    ])
    planted = {"unreach2": {"base_valence": -2, "forms": [{"id": "unreach2_base", "mu0_RT": 0.0},
                                                          {"id": "unreach2_H2", "counts": {"H": 2},
                                                           "mu0_RT": -20.0}]}}
    c["envelope"] = {"budget_pH": ENVELOPE_BUDGET_PH, "cases": cases,
                     "planted_unreachable_binders": planted,
                     "note": ("amendment C3: k_on per (binder, ligand); drives on free ligands or "
                              "a binder's base form; record times in units of the network's "
                              "slowest relaxation time")}


SYSTEM_S7 = {"ligands": ["H", "Mg"], "binders": ["mgx"], "volume_pL": 1.0,
             "note": ("amendment C4: a binder whose Mg²⁺ binding releases H⁺, so the per-ligand "
                      "floors are not the joint condition"),
             "designated": "mgx_MgmH"}


def amendment_c4(c: dict, rng) -> None:
    """Amendment C4: S7, an ordinary system of the mixed-sign binder (drawn after every earlier
    input), and four planted validity states of it, given by their totals:
    - joint_infeasible: each per-ligand floor passes (H > −T_B, Mg > 0), but freeing the protons
      takes more Mg²⁺ than there is: t* = −1/2 fmol;
    - boundary: t* = 0 exactly, not an interior state;
    - feasible_near: t* = +1/2 fmol, solvable;
    - per_ligand_infeasible: below the H floor, refused by either test."""
    c["systems"]["S7"] = SYSTEM_S7
    spec = {"ligands": SYSTEM_S7["ligands"], "binders": SYSTEM_S7["binders"]}
    V = SYSTEM_S7["volume_pL"]
    out = []
    for k in range(8):
        free = {"H": 10.0 ** (3.0 - float(rng.uniform(6.0, 9.0))),
                "Mg": float(np.exp(rng.uniform(math.log(0.01), math.log(5.0))))}
        bm = {"mgx": float(np.exp(rng.uniform(math.log(1.0), math.log(20.0))))}
        st = {"tag": f"random_{k}", "free_mM": free, "binders_mM": bm}
        st["totals"] = totals_from_manufactured(spec, st, V)
        out.append(st)
    st = {"tag": "mostly_MgmH", "free_mM": {"H": 10 ** (3 - 9.5), "Mg": 2.0},
          "binders_mM": {"mgx": 10.0}}
    st["totals"] = totals_from_manufactured(spec, st, V)
    out.append(st)
    c["manufactured_states"]["S7"] = out

    def planted(TH, TMg, note):
        return {"system": "S7", "totals": {"ligands_fmol": {"H": TH, "Mg": TMg},
                                           "binders_fmol": {"mgx": 10.0}}, "note": note}
    c["validity"] = {
        "note": ("amendment C4: t* = min over the ligand simplex of λ·T − Σ_B T_B min_f λ·n_f; "
                 "a state is valid iff t* > 0; the per-ligand floors are t at λ = e_L"),
        "planted": {
            "joint_infeasible": planted(-2.0, 1.0, "per-ligand floors pass; jointly infeasible"),
            "boundary": planted(-2.0, 2.0, "t* = 0: on the boundary, not interior"),
            "feasible_near": planted(-2.0, 3.0, "t* = +1/2: valid, close to the boundary"),
            "per_ligand_infeasible": planted(-11.0, 20.0, "below the H floor −T_B"),
        }}


def build() -> dict:
    rng = np.random.default_rng(SEED)
    a = seam_a(rng)
    c = seam_c(rng)
    for name, sysd in SYSTEMS.items():
        for st in c["manufactured_states"][name]:
            st["totals"] = totals_from_manufactured(sysd, st, sysd["volume_pL"])
    for node in P1_NODES.values():
        node["totals"] = totals_from_manufactured(node["system"],
                                                  {"free_mM": node["free_mM"],
                                                   "binders_mM": node["binders_mM"]},
                                                  node["volume_pL"])
    amendment_1(a, rng)
    amendment_c2(c)
    amendment_c3(c)
    amendment_c4(c, rng)
    return {
        "kind": "cells.core_seams_reference_inputs@1",
        "registered": REGISTERED,
        "units": {"amount": "fmol", "volume": "pL", "concentration": "mM", "potential": "V",
                  "time": "s", "molar_energy": "J/mol", "energy": "pJ", "current": "pA",
                  "conductance": "pS"},
        "constants": {"avogadro_per_mol": 6.02214076e23, "elementary_charge_C": 1.602176634e-19,
                      "boltzmann_J_per_K": 1.380649e-23,
                      "note": "exact SI (2019); F = N_A e and R = N_A k_B"},
        "conventions": {
            "activity": "a = c/c°, c° the registry's standard_concentration_mM (1000 mM)",
            "potential": "μ̃ = μ° + RT ln a + z F φ_e; ΔG_m = Σ ν_{s,e} μ̃_{s,e}",
            "rates": ("α = k0 Π a_{s,e}^order exp(ζ ψ), ψ = F (φ_N − φ_P)/RT; ζ_fwd − ζ_bwd is "
                      "the charge an edge moves N -> P"),
            "cycles": ("a cycle's edges carry +1 (from -> to) or −1 in its + direction; ν is "
                       "the change of each row per + cycle"),
            "host": ("a population's host is a patch with ends a (its cell) and b (the outside "
                     "node), V = φ_a − φ_b; orientation names the host end that is N"),
            "factored": "J = k a S (1 − e^{ΔG/RT}); J⁺ = k a S, J⁻ = J⁺ e^{ΔG/RT}",
            "diagram": ("S_κ = j⁺_κ/ω with j±_κ = Π±_κ Σ_κ/Σ per carrier (1/s) and ω the law's "
                        "rate_scale_per_s; k = N_carriers ω"),
            "net_flow": "J_m = a Σ_t k_t (1 − exp(ΔG_t/RT + ε_t ψ))",
            "binding": ("forms carry integer ligand counts relative to their binder's base form; "
                        "ligand rows hold total equivalents counted from the base forms"),
            "synthetic": "every constant and range is this package's own, D152 §2.4",
        },
        "seam_a": a,
        "seam_c": c,
    }


def write(path=INPUTS) -> None:
    Path(path).write_text(json.dumps(build(), indent=1, sort_keys=False) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        fresh = json.dumps(build(), indent=1, sort_keys=False) + "\n"
        same = INPUTS.read_text() == fresh
        print("inputs: identical" if same else "inputs: DIFFER")
        return 0 if same else 1
    write()
    print(f"wrote {INPUTS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
