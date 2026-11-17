"""Writes FR-1's registered reference design and values (``designs/``) from the inputs.

    python -m validation.fr1.references.design            # (re)write both files
    python -m validation.fr1.references.design --check    # compare the committed files

``fr1_reference_design.json`` holds the settled readings, the claims and their tolerance basis,
each planted control's deviation (the power), the honest split stand-ins and the zero-power
cases. ``fr1_reference_values.json`` holds the references' outputs on the registered inputs,
with their floors. Both are written before any engine output. Generate with
``OPENBLAS_NUM_THREADS=1`` (the engine's setting, D190); ``--check`` compares the references'
values to a relative 1e-12, control deviations to 1e-6, and rounding-level floors within a
factor of 2 or below 1e-12.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from decimal import localcontext
from pathlib import Path

import numpy as np

from . import api, forms, splits, stepmap
from .exact import DIGITS, FARADAY, GAS_CONSTANT, UNIT_ROUNDOFF, dec, exact

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "reference_inputs.json"
DESIGNS = HERE / "designs"
DESIGN_FILE = DESIGNS / "fr1_reference_design.json"
VALUES_FILE = DESIGNS / "fr1_reference_values.json"
REGISTERED = "2026-11-17"
SOURCE = ("branch fr1-protocol, commit f78dacb9 (unchanged since cf61c252), "
          "validation/closed_compartment/reference_inputs.json (copied byte for byte)")
MIN_MARGIN = 10.0
NOISE_CEILING = 1e-12


def git_blob_id(path) -> str:
    data = Path(path).read_bytes()
    return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, np.bool_):
        return bool(o)
    return o


THIN_ABOVE = 101
"""Registered value arrays longer than this keep every k-th record and the last (k = ceil(n/100));
floors are registered as their largest value. The API returns every record."""


def thin(o, key=""):
    if isinstance(o, dict):
        return {k: thin(v, k) for k, v in o.items()
                if not k.endswith(("_float64_fmol", "_expm_fmol", "radau_V"))}
    if isinstance(o, list) and o and all(isinstance(x, (int, float)) for x in o):
        if "floor" in key:
            return max(abs(x) for x in o)
        if len(o) > THIN_ABOVE:
            k = -(-len(o) // 100)
            idx = list(range(0, len(o), k))
            if idx[-1] != len(o) - 1:
                idx.append(len(o) - 1)
            return {"every": k, "values": [o[i] for i in idx]}
        return o
    if isinstance(o, list):
        return [thin(v, key) for v in o]
    return o


def _maxdev(a: dict, b: dict) -> float:
    return float(max(np.max(np.abs(np.asarray(a[k]) - np.asarray(b[k]))) for k in a))


def _scaled(world: dict, factor: float, key: str) -> dict:
    w = copy.deepcopy(world)
    for r in w["routes"]:
        s = r["schedule"][0]
        if key in s:
            s[key] = float(exact(s[key]) * exact(factor))
            if key == "kappa_per_s" and "k_u_m_per_s" in s:
                s["k_u_m_per_s"] = float(exact(s["k_u_m_per_s"]) * exact(factor))
            if key == "a_fmol_per_s" and "V_max_fmol_per_s_m2" in s:
                s["V_max_fmol_per_s_m2"] = float(exact(s["V_max_fmol_per_s_m2"]) *
                                                 exact(factor))
    return w


def _late(world: dict, ref: dict, dt: float) -> float:
    """The whole schedule one step late: amounts held for one dt, the closed form after."""
    w = copy.deepcopy(world)
    t = np.asarray(w["record_times_s"], dtype=np.float64)
    shifted = np.maximum(t - dt, 0.0)
    w["record_times_s"] = sorted(set(shifted.tolist()))
    r = api.closed(w)
    pos = np.searchsorted(np.asarray(w["record_times_s"]), shifted)
    late = {k: np.asarray(v)[pos] for k, v in r["amount_fmol"].items()}
    return _maxdev(late, ref["amount_fmol"])


def _rounding_allowance(world: dict) -> float:
    """8 ulps of the total amount per step, accumulated to the last record (C3's 'rounding')."""
    steps = float(world["end_s"]) / float(world["dt_s"])
    total = sum(float(exact(v)) for n in world["nodes"].values()
                for v in n["initial_fmol"].values())
    return 8 * UNIT_ROUNDOFF * (steps + 1) * total


def _closed_power(inputs: dict, values: dict) -> dict:
    out = {}
    for name, w in inputs["R_closed"]["worlds"].items():
        ref = values["R_closed"][name]
        dt = float(w["dt_s"])
        allow = _rounding_allowance(w)
        ctrl = {"one_step_late": _late(w, ref, dt)}
        key = {"C3_flux": "J_fmol_per_s", "C3_first_order": "k_e_per_s",
               "C5_saturable": "a_fmol_per_s"}.get(name)
        if key:
            ctrl["rate_1pct"] = _maxdev(api.closed(_scaled(w, 1.01, key))["amount_fmol"],
                                        ref["amount_fmol"])
        if name == "C3_flux":
            ctrl["half_the_moved"] = _maxdev(api.closed(_scaled(w, 0.5, key))["amount_fmol"],
                                             ref["amount_fmol"])
        if name == "C4_two_way":
            ctrl["export_1pct"] = _maxdev(api.closed(_scaled(w, 1.01, "k_e_per_s"))
                                          ["amount_fmol"], ref["amount_fmol"])
            # kappa on the cytosol's volume (1 pL) instead of the compartment's (0.1 pL)
            ctrl["kappa_on_cytosol_volume"] = _maxdev(
                api.closed(_scaled(w, 0.1, "kappa_per_s"))["amount_fmol"], ref["amount_fmol"])
        if name == "C5_saturable":
            s = w["routes"][0]["schedule"][0]
            bad = copy.deepcopy(w)
            bs = bad["routes"][0]["schedule"][0]
            bs["b_fmol"] = s["K_M_mM"]                         # K_M taken as an amount
            bs.pop("K_M_mM")
            ctrl["K_M_as_amount"] = _maxdev(api.closed(bad)["amount_fmol"], ref["amount_fmol"])
            # first order at the initial slope a/b instead of saturable
            t = np.asarray(w["record_times_s"])
            n0 = float(w["nodes"]["ecs_0"]["initial_fmol"]["S"])
            k = float(s["a_fmol_per_s"]) / (float(s["b_fmol"]) + n0)
            fo = forms.two_way(float(w["nodes"]["cell_0"]["initial_fmol"]["S"]), n0, 0.0, k, t)
            ctrl["first_order_instead"] = _maxdev({"cell_0": fo["n_c_fmol"],
                                                   "ecs_0": fo["n_o_fmol"]}, ref["amount_fmol"])
        floor = float(max(np.max(v) for v in ref["floor_fmol"].values()))
        out[name] = {"rounding_allowance_fmol": allow, "floor_fmol": floor, "controls": ctrl,
                     "margins": {k: v / allow for k, v in ctrl.items()}}
    return out


def _step_map_power(inputs: dict, values: dict) -> dict:
    rungs = []
    for name, w in inputs["R_step_map"]["worlds"].items():
        ref = values["R_step_map"][name]
        closed = api.closed(w)
        honest_vs_closed = _maxdev(ref["amount_fmol"], closed["amount_fmol"])
        a, b, dt = ref["a_per_s"], ref["b_per_s"], ref["dt_s"]
        c0 = float(w["nodes"]["cell_0"]["initial_fmol"]["S"])
        o0 = float(w["nodes"]["ecs_0"]["initial_fmol"]["S"])
        every = int(ref["steps"][1])
        steps = int(ref["steps"][-1])
        ctrl = {}
        for plan in ("lie", "swapped"):
            it = stepmap.iterate(c0, o0, a, b, dt, steps, plan=plan, every=every)
            dev = _maxdev({"c": it["n_c_fmol"], "o": it["n_o_fmol"]},
                          {"c": ref["amount_fmol"]["cell_0"], "o": ref["amount_fmol"]["ecs_0"]})
            dev_closed = _maxdev({"c": it["n_c_fmol"], "o": it["n_o_fmol"]},
                                 {"c": closed["amount_fmol"]["cell_0"],
                                  "o": closed["amount_fmol"]["ecs_0"]})
            ctrl[plan] = {"vs_honest_map_fmol": dev, "vs_closed_form_fmol": dev_closed}
        allow = ref["rounding_allowance_fmol"]
        rungs.append({
            "dt_s": dt, "honest_map_vs_closed_form_fmol": honest_vs_closed,
            "rounding_allowance_fmol": allow,
            "floor_fmol": float(max(np.max(v) for v in ref["floor_fmol"].values())),
            "controls": ctrl,
            "margin_against_map_to_rounding": {p: c["vs_honest_map_fmol"] / allow
                                               for p, c in ctrl.items()},
            "splitting": ref["splitting"],
        })
    devs = [r["honest_map_vs_closed_form_fmol"] for r in rungs]
    orders = [float(np.log2(x / y)) for x, y in zip(devs, devs[1:], strict=False)]
    return {"per_rung": rungs, "honest_map_vs_closed_form_order": orders}


def _linear_power(inputs: dict, values: dict) -> dict:
    out = {}
    for name, w in inputs["R_linear"]["worlds"].items():
        ref = values["R_linear"][name]
        flat = {f"{n}.{s}": v for n, d in ref["amount_fmol"].items() for s, v in d.items()}
        ctrl = {}
        r = api.linear(_scaled(w, 1.01, "k_e_per_s"))
        ctrl["export_1pct"] = _maxdev({f"{n}.{s}": v for n, d in r["amount_fmol"].items()
                                       for s, v in d.items()}, flat)
        if name == "C6_load_and_degrade":
            bad = copy.deepcopy(w)
            bad["clearance_per_s"] = {k: v * 1.01 for k, v in w["clearance_per_s"].items()}
            ctrl["clearance_1pct"] = _maxdev(_flat(api.linear(bad)), flat)
            bad = copy.deepcopy(w)
            bad["clearance_node"] = "cell_0"
            ctrl["clearance_in_the_cytosol"] = _maxdev(_flat(api.linear(bad)), flat)
        if name == "C7_load_and_react":
            bad = copy.deepcopy(w)
            bad["reactions"]["convert"]["sites"] = {"outside": [], "cells": ["cell_0"]}
            ctrl["reaction_in_the_cytosol"] = _maxdev(_flat(api.linear(bad)), flat)
            bad = copy.deepcopy(w)
            bad["reactions"]["convert"]["rate_constant_per_s"] *= 1.01
            ctrl["reaction_1pct"] = _maxdev(_flat(api.linear(bad)), flat)
        if name == "C8_uptake_path":
            ctrl["uptake_1pct"] = _maxdev(_flat(api.linear(_scaled(w, 1.01, "kappa_per_s"))),
                                          flat)
        split = _split_standins(w, ref)
        honest = max(split.values())
        ceiling = min(ctrl.values()) / MIN_MARGIN
        out[name] = {"controls": ctrl, "split_stand_ins": split, "ceiling_fmol": ceiling,
                     "honest_margin": ceiling / honest if honest > 0 else None,
                     "floor_fmol": float(max(np.max(f) for d in ref["floor_fmol"].values()
                                             for f in d.values()))}
    return out


def _flat(r: dict) -> dict:
    return {f"{n}.{s}": v for n, d in r["amount_fmol"].items() for s, v in d.items()}


def _split_standins(w: dict, ref: dict) -> dict:
    """Lie and Strang splits of the world's two sub-flows at its dt (honest split engines)."""
    nodes = ref["nodes"]
    species = ref["species"]
    states = [(n, s) for n in nodes for s in species]
    idx = {x: i for i, x in enumerate(states)}
    M = len(states) + 1
    G1, G2 = np.zeros((M, M)), np.zeros((M, M))

    def move(G, src, dst, k):
        G[src, src] -= k
        G[dst, src] += k
    routes = api._routes(w)
    first = routes[0]
    for law, _d, s, d, p in routes:
        target = G1 if (law, s, d) == (first[0], first[2], first[3]) else G2
        move(target, idx[(s, "S")], idx[(d, "S")], float(p["k"]))
    if "clearance_per_s" in w:
        for k in w["clearance_per_s"].values():
            move(G2, idx[(w["clearance_node"], "S")], M - 1, float(k))
    for rx in w.get("reactions", {}).values():
        a_s, b_s = next(iter(rx["reactants"])), next(iter(rx["products"]))
        for node in rx["sites"].get("outside", []):
            move(G2, idx[(node, a_s)], idx[(node, b_s)], float(rx["rate_constant_per_s"]))
    y0 = [float(w["nodes"][n]["initial_fmol"].get(s, 0.0)) for n, s in states] + [0.0]
    exact_flat = np.column_stack([ref["amount_fmol"][n][s] for n, s in states])
    out = {}
    for order in ("lie", "strang"):
        y = splits.split_run(G1, G2, y0, float(w["dt_s"]), ref["times_s"], order)
        out[order] = float(np.max(np.abs(y[:, :len(states)] - exact_flat)))
    return out


def _energy_power(inputs: dict, values: dict) -> dict:
    out = {}
    worlds = dict(inputs["R_energy"]["worlds"])
    worlds.update({k: inputs["R_closed"]["worlds"][k]
                   for k in ("C3_flux", "C3_first_order", "C4_two_way", "C5_saturable")})
    for name, w in worlds.items():
        ref = values["R_energy"][name]
        dG = np.asarray(ref["dG_pJ"])
        T = w["temperature_K"]
        rt = float(GAS_CONSTANT * exact(T)) * 1e-3
        Vc = float(w["nodes"]["cell_0"]["volume_pL"])
        Vo = float(w["nodes"]["ecs_0"]["volume_pL"])
        dno = np.asarray(ref["amount_fmol"]["ecs_0"]) - \
            float(w["nodes"]["ecs_0"]["initial_fmol"]["S"])
        ctrl = {
            "sign": float(np.max(np.abs(2 * dG))),
            "volume_dropped": float(np.max(np.abs(rt * dno * np.log(Vo / Vc)))),
            "rounded_RT": float(np.max(np.abs(dG)) * abs(2577.0 / (rt * 1e3) - 1)),
            "dropped_minus_one": 0.0,
            "one_molar_standard_state": 0.0,
        }
        floor = float(np.max(ref["dG_floor_pJ"]))
        out[name] = {"max_abs_dG_pJ": float(np.max(np.abs(dG))), "floor_pJ": floor,
                     "controls": ctrl,
                     "margins_over_floor": {k: (v / floor if v else 0.0)
                                            for k, v in ctrl.items()}}
    return out


def build(inputs_path=INPUTS) -> tuple:
    inputs = json.loads(Path(inputs_path).read_text())
    from .exact import check_constants
    check_constants(inputs["constants"])
    values = {"kind": "fr1-references values@1", "registered": REGISTERED,
              "R_closed": {k: api.closed(w) for k, w in inputs["R_closed"]["worlds"].items()},
              "R_step_map": {k: api.step_map(w) for k, w in
                             inputs["R_step_map"]["worlds"].items()},
              "R_linear": {k: api.linear(w) for k, w in inputs["R_linear"]["worlds"].items()}}
    net = inputs["R_capacitor"]["network"]
    q = {"silent": ([-6e-14], [0.0]), "charged_compartment": ([-6e-14], [1e-17]),
         "both_charged": ([3e-14], [-2e-16])}
    values["R_capacitor"] = {k: {"q_i_C": v[0], "q_j_C": v[1], **api.capacitor(net, *v)}
                             for k, v in q.items()}
    ew = dict(inputs["R_energy"]["worlds"])
    ew.update({k: inputs["R_closed"]["worlds"][k]
               for k in ("C3_flux", "C3_first_order", "C4_two_way", "C5_saturable")})
    values["R_energy"] = {k: api.energy(w, inputs["constants"]) for k, w in ew.items()}
    values = jsonable(values)
    registered_values = thin(values)

    with localcontext() as ctx:
        ctx.prec = DIGITS
        const = {"faraday_C_per_mol": str(dec(FARADAY)),
                 "gas_constant_J_per_mol_K": str(dec(GAS_CONSTANT)),
                 "RT_pJ_per_fmol_at_310K": str(dec(GAS_CONSTANT * 310) / 1000)}
    cap_ctrl = {}
    for k, v in values["R_capacitor"].items():
        Vb = abs(v["V_b_V"][0])
        cap_ctrl[k] = {"orientation_flipped_V": 2 * Vb,
                       "zero_power": Vb == 0.0}
    design = {
        "kind": "fr1-references design@1",
        "registered": REGISTERED,
        "status": "registered before any engine output; the references are code-blind",
        "inputs": {"path": "validation/fr1/references/reference_inputs.json", "source": SOURCE,
                   "git_blob": git_blob_id(inputs_path)},
        "constants": const,
        "min_margin": MIN_MARGIN,
        "settled_readings": SETTLED,
        "claims": CLAIMS,
        "power": {
            "C3_C4_C5_closed_forms": _closed_power(inputs, values),
            "C4_step_map": _step_map_power(inputs, values),
            "C6_C7_C8_linear": _linear_power(inputs, values),
            "C9_capacitor": cap_ctrl,
            "C10_C11_energy": _energy_power(inputs, values),
        },
        "zero_power": ZERO_POWER,
        "notes": NOTES,
    }
    return jsonable(design), registered_values


SETTLED = [
    {"reading": "1. A.4's comparison 'to rounding'",
     "settled": "the inputs fix the plan S(h) = E(h/2) I(h) E(h/2), S(dt/2) twice per step "
                "(convention 6). The floor is the float64 moved-form iteration's distance from "
                "the 50-digit map; the registered rounding allowance is 4 ulps of N per stage, "
                "accumulated (power.C4_step_map)"},
    {"reading": "2. A.5's units",
     "settled": "the inputs declare a = 2.0000000000000004e-4 fmol/s = A V_max with V_max in "
                "fmol/s/m^2, and b = 5e-4 fmol = K_M V_o; both are used as declared and checked "
                "against their parameters to 1e-14"},
    {"reading": "3. A.7's standard potentials",
     "settled": "C7 declares none, and R_energy does not ask for C7's energy: no reaction work "
                "is computed"},
    {"reading": "4. A.8's face",
     "settled": "C8 declares no face to a bath: the uptake path is the closed three-node chain"},
    {"reading": "5. A.9's orientation",
     "settled": "the inputs' R_capacitor names V_b = phi_i - phi_j and V_pm = phi_i - phi_b, as "
                "this package computes them"},
    {"reading": "6. A declared rate beside its parameters",
     "settled": "kappa_per_s is used as declared (19.999999999999996 and 1.9999999999999998, "
                "the doubles of 1e15 k_u A/V) and checked against 1e15 k_u A/V of the import's "
                "source to 1e-14; a mismatch is refused"},
    {"reading": "7. The splitting term",
     "settled": "the inputs' returns line reads 'x* - x_eq beside -a(a + 2b) dt^2/96'; the "
                "design's wording since 4adb6fed names the relative displacement, x*/x_eq - 1 = "
                "-a(a + 2b) dt^2/96 (§2.3). Both are returned: the relative displacement meets "
                "the leading term (ratio 1 - O(dt)), the absolute one is x_eq times it"},
    {"reading": "8. C7's moiety",
     "settled": "S + P over the cytosol's S and the compartment's S and P; P's cytosolic row is "
                "untouched and is reported as its own constant"},
    {"reading": "9. Energy along a trajectory",
     "settled": "dG(t) is the change of G over the two nodes the law touches, evaluated per node "
                "as a stable increment from the declared start, in decimals, with RT = 1e-3 R T "
                "pJ/fmol from the exact SI R"},
]

CLAIMS = {
    "C3 (A.2)": {"quantity": "each node's S at every record time, flux and first-order loading",
                 "reference": "exact rationals (flux); 50-digit decimals (first-order)",
                 "second_method": "float64 with expm1", "tolerance_basis": "the engine equals "
                 "the closed form to rounding: the registered allowance is 8 ulps of the total "
                 "amount per step, accumulated (power.C3_C4_C5_closed_forms)"},
    "C4 (A.3, A.4)": {"quantity": "each node's S at every record time; x_eq; at each rung the "
                      "map's x*, x(t), the amounts, and the splitting term",
                      "reference": "A.3 in decimals; A.4's map iterated in 50-digit decimals",
                      "second_method": "SciPy expm (A.3); the float64 moved-form iteration (A.4)",
                      "tolerance_basis": "against the closed form: the dt study's tolerance, "
                      "which an honest map meets at its own O(dt^2) distance "
                      "(power.C4_step_map.per_rung.honest_map_vs_closed_form_fmol); against the "
                      "map: rounding, 4 ulps of N per stage; the splitting term: the relative "
                      "displacement over -a(a + 2b) dt^2/96 = 1 - O(dt)"},
    "C5 (A.5)": {"quantity": "each node's S at every record time",
                 "reference": "Newton on the implicit form in 50-digit decimals",
                 "second_method": "Wright's omega (SciPy)",
                 "tolerance_basis": "the protocol pins it; the controls' deviations and the "
                                    "rounding allowance are in power.C3_C4_C5_closed_forms"},
    "C6, C7, C8 (A.6, A.7, A.8)": {"quantity": "each node's S (C7's P at the compartment) at "
                                   "every record time; C6's cleared amount; C7's moiety",
                                   "reference": "50-digit matrix exponential",
                                   "second_method": "SciPy expm",
                                   "tolerance_basis": "the protocol's dt study; an honest split "
                                   "engine's distance is bracketed by the Lie and Strang "
                                   "stand-ins at the declared dt, and the ceiling is the "
                                   "smallest control's deviation / 10 (power.C6_C7_C8_linear)"},
    "C9 (A.9)": {"quantity": "V_b and V_pm from the charges", "reference": "exact rationals",
                 "second_method": "NumPy's dense solve", "tolerance_basis": "rounding; V_b = "
                 "-q_j/C_b exactly, so a silent compartment's V_b is 0"},
    "C10, C11 (A.10)": {"quantity": "dG of the nodes each law touches at every record time; G",
                        "reference": "stable per-node increments in 50-digit decimals",
                        "second_method": "float64 of the same increments",
                        "tolerance_basis": "the protocol's (RK4's absolute 2e-8 pJ, the NumPy "
                                           "dG test); the floor is below 1e-16 pJ"},
}

NOTES = [
    "C6 to C8 at the declared 1 ms: a first-order (Lie) split of exchange and clearance, reaction "
    "or uptake errs by about 2.5e-7 fmol, near a 1% rate error's 2e-6/10; a second-order (Strang) "
    "split errs by about 6e-11. So a rate error is caught with margin 10 at 1 ms only if the "
    "engine's split is second order. A dt study separates the two: the split error falls with "
    "dt, a rate error does not (power.C6_C7_C8_linear).",
    "C4: the swapped palindrome I(h/2) E(h) I(h/2) lies 2.8e-9 fmol from the closed form at "
    "1 ms, within the honest map's own 3.5e-9: it is caught only by the comparison with the "
    "map to rounding (margin 2.3e6 at 1 ms, 4.6e3 at 0.125 ms), not by the closed form at a "
    "dt-study tolerance.",
    "C10 and C11: Appendix A's rounded RT moves dG by 2.5e-8 to 1.2e-6 pJ, so against RK4's "
    "absolute 2e-8 pJ its margin is 1 to 60 (power.C10_C11_energy).",
    "The registered values keep every k-th record of long arrays and the last, and each floor's "
    "largest value; the API returns every record and every floor.",
]

ZERO_POWER = [
    {"control": "kappa on the wrong volume in C8", "why": "ecs_e and cell_0 are both 1 pL",
     "remedy": "an extracellular node of another volume"},
    {"control": "a dropped -1, or a 1 M standard state, in A.10's dG",
     "why": "every world moves S between two nodes, so sum dn = 0 and both shifts vanish",
     "remedy": "a law that changes the total, such as C6's clearance or C7's reaction, in "
               "R_energy"},
    {"control": "V_b's orientation", "why": "a silent compartment has q_j = 0, so V_b = 0 either "
     "way", "remedy": "a charged compartment (q_j != 0), which version 1 refuses"},
    {"control": "the swapped palindrome against the closed form (C4)",
     "why": "its O(dt^2) distance is the honest map's size", "remedy": "the comparison with "
     "the iterated map to rounding, which C4 makes"},
    {"control": "the halves plan against the single plan (A.4)",
     "why": "they are one map in exact arithmetic", "remedy": "none needed: not an error"},
]


def _dump(obj) -> str:
    return json.dumps(obj, indent=1) + "\n"


def write() -> None:
    design, values = build()
    DESIGNS.mkdir(parents=True, exist_ok=True)
    DESIGN_FILE.write_text(_dump(design))
    VALUES_FILE.write_text(_dump(values))


ROUNDING_NOISE = ("floor", "allowance", "split_stand_ins", "margins_over_floor", "float64")


def _same(a, b, path="", rtol=1e-12) -> list:
    if isinstance(a, dict) and isinstance(b, dict):
        if set(a) != set(b):
            return [f"{path}: keys {sorted(set(a) ^ set(b))}"]
        return [m for k in a for m in _same(a[k], b[k], f"{path}/{k}", rtol)]
    if isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            return [f"{path}: length {len(a)} != {len(b)}"]
        return [m for i, (x, y) in enumerate(zip(a, b, strict=True))
                for m in _same(x, y, f"{path}[{i}]", rtol)]
    if isinstance(a, (int, float)) and isinstance(b, (int, float)) and \
            not isinstance(a, bool) and not isinstance(b, bool):
        if a == b:
            return []
        if any(tag in path for tag in ROUNDING_NOISE):
            ok = max(abs(a), abs(b)) <= NOISE_CEILING or abs(a - b) <= 0.5 * max(abs(a), abs(b))
        else:
            ok = abs(a - b) <= rtol * max(abs(a), abs(b))
        return [] if ok else [f"{path}: {a!r} != {b!r}"]
    return [] if a == b else [f"{path}: {a!r} != {b!r}"]


def check() -> list:
    design, values = build()
    return _same(json.loads(DESIGN_FILE.read_text()), design, "design", rtol=1e-6) + \
        _same(json.loads(VALUES_FILE.read_text()), values, "values", rtol=1e-12)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    if args.check:
        diffs = check()
        for d in diffs[:50]:
            print(d)
        return 1 if diffs else 0
    write()
    print(DESIGN_FILE)
    print(VALUES_FILE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
