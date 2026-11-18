"""Writes FR-3's registered design and values (``designs/``) from the registered inputs.

    OPENBLAS_NUM_THREADS=1 python -m validation.fr3.references.design            # write
    OPENBLAS_NUM_THREADS=1 python -m validation.fr3.references.design --check    # compare

``reference_inputs.json`` (written by ``worlds.py``) holds the worlds. ``fr3_reference_design.json``
holds the claims and their tolerance basis, the honest SSPRK(3,3) stand-in on the dt ladder, each
planted control's deviation, the ceilings, the zero-power cases and the notes.
``fr3_reference_values.json`` holds the references on every world. Long arrays keep every k-th
record and the last; floors keep their largest value. All of it is written before any engine
output. Generating takes about two minutes of one CPU.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

from . import api, kinetics, schemes, worlds

HERE = Path(__file__).resolve().parent
DESIGNS = HERE / "designs"
DESIGN_FILE = DESIGNS / "fr3_reference_design.json"
VALUES_FILE = DESIGNS / "fr3_reference_values.json"
REGISTERED = "2026-11-17"
MIN_MARGIN = 10.0
NOISE_CEILING = 1e-12
LADDER_WORLDS = ("q1_fast", "q1_eps_1e-1", "q2_closed", "q3_internalisation", "q5_washout")


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


def thin(o, key=""):
    if isinstance(o, dict):
        return {k: thin(v, k) for k, v in o.items()}
    if isinstance(o, list) and o and all(isinstance(x, (int, float)) for x in o):
        if "floor" in key:
            return max(abs(x) for x in o)
        if len(o) > 101:
            k = -(-len(o) // 100)
            idx = list(range(0, len(o), k))
            if idx[-1] != len(o) - 1:
                idx.append(len(o) - 1)
            return {"every": k, "values": [o[i] for i in idx]}
        return o
    if isinstance(o, list) and o and all(isinstance(x, list) for x in o):
        if "floor" in key:
            return max(abs(v) for row in o for v in row)
        if len(o) > 101:
            k = -(-len(o) // 100)
            idx = list(range(0, len(o), k))
            if idx[-1] != len(o) - 1:
                idx.append(len(o) - 1)
            return {"every": k, "values": [o[i] for i in idx]}
        return o
    return o


def _state(r: dict) -> np.ndarray:
    return np.column_stack([r["n_fmol"], r["B_fmol"], r["internalised_fmol"]])


def _radau(net, times) -> dict:
    return kinetics._integrate(net, times, "Radau", kinetics.RTOL_PRIMARY)


def _dev(a: dict, b: dict) -> float:
    return float(np.max(np.abs(_state(a) - _state(b))))


def _perturbed(world: dict, which: str) -> dict:
    w = copy.deepcopy(world)
    p = w["populations"][0]
    if which == "k_on_1pct":
        p["association_rate_per_mM_per_s"] *= 1.01
    elif which == "k_off_1pct":
        p["dissociation_rate_per_s"] *= 1.01
    elif which == "k_int_1pct":
        p["internalisation"]["rate_per_s"] *= 1.01
    elif which == "alpha_ignored":
        p["accessible_fraction"] = 1.0
    elif which == "binding_multiplier_ignored":
        for e in w["site_controls"]:
            e["binding"] = {k: 1.0 for k in e["binding"]}
    elif which == "binding_multiplier_squared":
        for e in w["site_controls"]:
            e["binding"] = {k: v * v for k, v in e["binding"].items()}
    elif which == "internalisation_multiplier_ignored":
        for e in w["site_controls"]:
            e["internalisation"] = {k: 1.0 for k in e["internalisation"]}
    return w


def _k_on_only(world: dict, times) -> dict:
    """The binding multiplier applied to k_on alone (k_off unscaled), one population on one
    node, binding only: J = m_b k_on c R - k_off B. A standalone integration (planted)."""
    from scipy.integrate import solve_ivp
    net = worlds.network(world)
    p = net.populations[0]
    V = float(net.volumes[p.node])
    starts = [float(e[0]) for e in net.epochs] + [float(times[-1])]
    y = [float(net.n0[p.node]), p.B0]
    t_all = np.asarray(times, dtype=np.float64)
    out_n, out_B = np.empty(t_all.size), np.empty(t_all.size)
    for e in range(len(net.epochs)):
        mb = (net.epochs[e][1] or {0: (1.0, 1.0)})[0][0]
        t0, t1 = starts[e], starts[e + 1]
        last = e == len(net.epochs) - 1
        sel = [k for k, t in enumerate(t_all) if t0 <= t and (t < t1 or (last and t == t1))]

        def rhs(_t, u, mb=mb):
            J = mb * p.k_on * (u[0] / V) * (p.S - u[1]) - p.k_off * u[1]
            return [-J, J]
        sol = solve_ivp(rhs, (t0, t1), y, method="Radau", rtol=1e-12, atol=1e-24,
                        t_eval=sorted(set([t_all[k] for k in sel] + [t1])))
        at = {float(t): sol.y[:, i] for i, t in enumerate(sol.t)}
        for k in sel:
            out_n[k], out_B[k] = at[float(t_all[k])]
        y = list(at[t1])
    return {"n_fmol": out_n, "B_fmol": out_B}


def _controls(inputs: dict, refs: dict) -> dict:
    plan = {"q1_fast": ["k_on_1pct", "k_off_1pct", "k_int_1pct", "wrong_destination"],
            "q1_eps_1e-1": ["k_on_1pct", "k_off_1pct", "k_int_1pct", "wrong_destination"],
            "q1_eps_1e-1_alpha_half": ["alpha_ignored"],
            "q2_closed": ["k_on_1pct", "k_off_1pct"],
            "q2_two_populations": ["k_on_1pct"],
            "q3_association": ["k_on_1pct", "k_off_1pct"],
            "q3_dissociation": ["k_on_1pct", "k_off_1pct"],
            "q3_internalisation": ["k_int_1pct"],
            "q3_binding_multiplier": ["binding_multiplier_ignored",
                                      "binding_multiplier_squared"],
            "q5_class_switch": ["internalisation_multiplier_ignored"],
            "q5_washout": ["k_int_1pct", "wrong_destination"]}
    out = {}
    for name, ctrls in plan.items():
        w = inputs["worlds"][name]
        t = np.asarray(w["record_times_s"], dtype=np.float64)
        base = _radau(worlds.network(w), t)
        row = {}
        for c in ctrls:
            if c == "wrong_destination":
                net = worlds.network(w)
                for p in net.populations:
                    if p.receiver:
                        p.receiver = p.node        # the cargo returns to the faced node
                r = _radau(net, t)
            else:
                r = _radau(worlds.network(_perturbed(w, c)), t)
            row[c] = _dev(r, base)
        out[name] = row
    # the binding multiplier applied to k_on alone: the equilibrium moves while m_b != 1
    w = inputs["worlds"]["q3_binding_multiplier"]
    t = np.asarray(w["record_times_s"], dtype=np.float64)
    base = _radau(worlds.network(w), t)
    bad = _k_on_only(w, t)
    node = base["nodes"].index(w["populations"][0]["owner"]["faces_node"])
    out["q3_binding_multiplier"]["binding_multiplier_on_k_on_only"] = float(max(
        np.max(np.abs(bad["B_fmol"] - base["B_fmol"][:, 0])),
        np.max(np.abs(bad["n_fmol"] - base["n_fmol"][:, node]))))
    # the receiving cell's volume taken as 1 pL: the state and the work it moves
    for name in ("q1_eps_1e-1", "q5_inward"):
        w = inputs["worlds"][name]
        t = np.asarray(w["record_times_s"], dtype=np.float64)
        base = _radau(worlds.network(w), t)
        net = worlds.network(w)
        net.volumes["cell_0"] = 1.0
        r = _radau(net, t)
        out.setdefault(name, {})["cell_volume_dropped"] = _dev(r, base)
        out[name]["cell_volume_dropped_work_pJ"] = float(np.max(np.abs(r["work_pJ"] -
                                                                       base["work_pJ"])))
    return out


def _ladder(inputs: dict, refs: dict) -> dict:
    out = {}
    for name in LADDER_WORLDS:
        w = inputs["worlds"][name]
        net = worlds.network(w)
        ref = refs[name]
        errs = []
        for dt in inputs["dt_ladder_s"]:
            s = schemes.run(net, w["record_times_s"], dt)
            errs.append(float(np.max(np.abs(_state(s) - np.column_stack(
                [ref["n_fmol"], ref["B_fmol"], ref["internalised_fmol"]])))))
        orders = [float(np.log2(a / b)) if b > 0 else None for a, b in zip(errs, errs[1:],
                                                                          strict=False)]
        floor = float(max(np.max(ref[k]) for k in ("n_fmol_floor", "B_fmol_floor",
                                                    "internalised_fmol_floor")))
        out[name] = {"dt_s": inputs["dt_ladder_s"], "honest_error_fmol": errs,
                     "observed_order": orders, "reference_floor_fmol": floor}
        if name == "q1_fast":
            planted = {}
            exact_state = np.column_stack([ref["n_fmol"], ref["B_fmol"],
                                           ref["internalised_fmol"]])
            for sch in ("ssprk22", "euler"):
                e2 = [float(np.max(np.abs(_state(schemes.run(net, w["record_times_s"], dt, sch))
                                          - exact_state))) for dt in inputs["dt_ladder_s"]]
                planted[sch] = {"error_fmol": e2,
                                "observed_order": [float(np.log2(a / b))
                                                   for a, b in zip(e2, e2[1:], strict=False)]}
            out[name]["planted_lower_orders"] = planted
    return out


def _accessibility(inputs: dict) -> dict:
    W = inputs["worlds"]
    out = {}
    for ctag in ("low", "high"):
        by = {1.0: W[f"q4_alpha_1_{ctag}"], 0.5: W[f"q4_alpha_1_2_{ctag}"],
              0.25: W[f"q4_alpha_1_4_{ctag}"]}
        acc = api.accessibility(by)
        net = worlds.network(by[1.0])
        p = net.populations[0]
        c = float(net.n0[p.node]) / float(net.volumes[p.node])
        Kd = p.K_d
        theta1 = c / (Kd + c)
        ctrl = {}
        for a in (0.5, 0.25):
            honest = acc["theta_ratio"][a]
            ctrl[f"K_kinetic_factor@{a}"] = abs(1.0 - honest)
            theta_A = (a * c) / (Kd + a * c)
            ctrl[f"A_affinity_factor@{a}"] = abs(theta_A / theta1 - honest)
        out[ctag] = {**acc, "controls_on_theta_ratio": ctrl,
                     "depletion_term": p.S / (float(net.volumes[p.node]) * (Kd + c))}
    return out


def _qss_order(refs: dict) -> dict:
    eps, rel = [], []
    for tag in ("1e-1", "1e-2", "1e-3"):
        q = refs[f"q1_eps_{tag}"]["qss"]
        eps.append(q["epsilon"])
        rel.append(q["relative_error_over_uptake"])
    orders = [float(np.log10(a / b) / np.log10(e1 / e2))
              for a, b, e1, e2 in zip(rel, rel[1:], eps, eps[1:], strict=False)]
    return {"epsilon": eps, "relative_error_over_uptake": rel, "observed_order": orders}


def _energy(inputs: dict, refs: dict) -> dict:
    out = {}
    for name, w in inputs["worlds"].items():
        r = refs[name]
        net = worlds.network(w)
        from . import energy as en
        Gs0 = sum(en.site_free_energy(p.B0, p.S, p.K_d, net.RT) for p in net.populations)
        GsT = sum(en.site_free_energy(r["B_fmol"][-1][j], p.S, p.K_d, net.RT)
                  for j, p in enumerate(net.populations))
        scale = max(abs(en.node_free_energy(net.n0[n], net.volumes[n], net.RT))
                    for n in net.volumes)
        H = np.asarray(r["heat_pJ"])
        allow = 8 * 2.0 ** -53 * float(np.max(np.abs(H))) if H.size else 0.0
        out[name] = {
            "max_ledger_residual_pJ": float(np.max(np.abs(r["ledger_residual_pJ"]))),
            "energy_scale_pJ": scale,
            "min_heat_increment_pJ": float(np.min(np.diff(H))),
            "heat_increment_allowance_pJ": allow,
            "controls": {"work_times_1_plus_1e-6": 1e-6 * float(np.max(np.abs(r["work_pJ"]))),
                         "site_free_energy_dropped": abs(GsT - Gs0),
                         "heat_sign": 2.0 * float(np.max(np.abs(r["heat_pJ"])))},
        }
    return out


def build() -> tuple:
    inputs = json.loads(worlds.INPUTS.read_text())
    refs = {name: api.reference(w) for name, w in inputs["worlds"].items()}
    values = {"kind": "fr3-references values@1", "registered": REGISTERED,
              "worlds": jsonable(refs)}
    ctrl = _controls(inputs, refs)
    ladder = _ladder(inputs, refs)
    ceilings = {}
    for name, row in ctrl.items():
        if name in ladder:
            # controls with power on the state: above 1e3 times the reference's floor (the cell
            # volume in q1_eps_1e-1 moves the work only, and is listed under zero power there)
            floor = ladder[name]["reference_floor_fmol"]
            powered = [v for k, v in row.items() if not k.endswith("_pJ") and v > 1e3 * floor]
            ceiling = min(powered) / MIN_MARGIN
            ceilings[name] = {"ceiling_fmol": ceiling,
                              "honest_margin_per_dt": [ceiling / e if e > 0 else None
                                                       for e in ladder[name]["honest_error_fmol"]]}
    design = {
        "kind": "fr3-references design@1", "registered": REGISTERED,
        "status": "registered before any engine output; the references are code-blind",
        "inputs": {"path": "validation/fr3/references/reference_inputs.json",
                   "written_by": "validation/fr3/references/worlds.py",
                   "git_blob": git_blob_id(worlds.INPUTS)},
        "min_margin": MIN_MARGIN,
        "claims": CLAIMS,
        "power": {"ladder_stand_in": ladder, "controls_fmol": ctrl, "ceilings": ceilings,
                  "accessibility": _accessibility(inputs), "qss_order": _qss_order(refs),
                  "energy": _energy(inputs, refs)},
        "readings": READINGS,
        "zero_power": ZERO_POWER,
        "notes": NOTES,
    }
    return jsonable(design), thin(jsonable(values))


CLAIMS = {
    "Q1": "the engine against R-ode at each eps (node, cell, B, heat and work), third order where "
          "errors stand above the reference's floor; on the reference side R-ode against R-qss, "
          "order 1 in eps, measured on the uptake's relative error",
    "Q2": "the long-time state against R-eq at the true V (large, small and shared node); the "
          "small node also against the depletion quadratic; the total heat against "
          "G(start) - G(eq)",
    "Q3": "the engine against R-ode at every record, and against the Riccati form directly in the "
          "closed node; on the reference side R-ode against the fixed-c exponentials, with the "
          "depletion term stated",
    "Q4": "theta(alpha)/theta(1) = alpha at c << K_d and c = 100 K_d (R-eq at the true V, "
          "depletion term <= 1.6e-7), saturation at alpha, a relaxation rate independent of "
          "alpha; the kinetic (K) and affinity (A) factors as negative controls",
    "Q5": "the ledger d(G_node) + d(G_site) + H - W = 0 at the reference's rounding, heat >= 0 on "
          "every record, the controls (work x (1 + 1e-6), the site free energy dropped, the heat's "
          "sign), the closed relaxation's heat, and the background guard",
    "tolerance_basis": "the protocol pins each judged tolerance from its dt study; a tolerance "
                       "has power where it lies below a world's ceiling (the smallest control's "
                       "deviation / 10) and above ten times the reference's floor; the honest "
                       "SSPRK(3,3) stand-in shows where an honest engine lies (power.ceilings)",
}

READINGS = [
    "RT = 1e-3 R T pJ/fmol with the exact SI R (Appendix A takes RT as an input); dG0 = RT "
    "ln(K_d/1 mM).",
    "R-ode carries the heat in a regular form, H = RT [Y - d(R ln(R/S) + B ln(B/S))] with "
    "dY/dt = sum J ln(c/K_d) + I ln(R/B), exact along the path and finite at B = 0 and R = 0.",
    "The order in eps is measured on the uptake's relative error with S varied at fixed V, "
    "§8.3's sweep; normalised by n0 with V varied, the same runs show order 2.",
    "Every world is face-free, and none combines site occupancy with a bath schedule.",
]

ZERO_POWER = [
    {"control": "Q1's third order in the slow worlds",
     "why": "an honest engine's error is at rounding there at every rung",
     "remedy": "q1_fast, where the order is 3.0 above the floor and the lower-order steppers "
               "(SSPRK(2,2), Euler) show orders 2 and 1"},
    {"control": "the work's control in passive worlds", "why": "binding alone books no work",
     "remedy": "the internalising worlds (Q1, q3_internalisation, q5_*) carry it"},
    {"control": "the receiving cell's volume on q1_eps_1e-1's state",
     "why": "internalisation is driven, so the cell's concentration moves only the work "
            "(3.3e-5 pJ there)", "remedy": "q5_inward, where an inward population binds from the "
            "cytosol and the state moves by 3.1e-7 fmol"},
    {"control": "k_on in q3_dissociation", "why": "rebinding into a near-empty 1e3 pL node is "
     "weak: 1.3e-10 fmol", "remedy": "k_on has power in every binding world (Q2, Q3)"},
    {"control": "the affinity factor (A) at c << K_d",
     "why": "below saturation (A) and the capacity form nearly agree (2.5e-3)",
     "remedy": "c = 100 K_d, where (A) departs by 0.49 (§2.3)"},
    {"control": "the background guard on heat and work", "why": "the trace's logarithm enters "
     "the receiving cell's potential", "remedy": "not a defect of the comparison: engine and "
     "references share the trace (notes)"},
]

NOTES = [
    "The background guard holds for the occupancy but not for the energy. Lowering the trace from "
    "the threshold 1e-6 K_d by 1e3 moves B by 1.4e-6 relative and n by 1.9e-5. It moves the heat "
    "by 6.9e-5 and the work by 1.9e-4, because the receiving cell starts at the trace and the "
    "work's RT ln(c_r) carries the trace's logarithm (q5_background_*). A tolerance on heat or "
    "work tighter than about 1e-3 relative will see the trace, so the guard's 'every compared "
    "quantity' needs that reading. The engine and the references are compared at the same trace, "
    "so the judged comparisons are not affected.",
    "Ledger residuals scale with the nodes' free energy: about 1e-9 pJ in the 1e6 pL worlds, "
    "whose G_node is about 1e6 pJ, which is rounding.",
]


def _dump(obj) -> str:
    return json.dumps(obj, indent=1) + "\n"


def write() -> None:
    worlds.write()
    design, values = build()
    DESIGNS.mkdir(parents=True, exist_ok=True)
    DESIGN_FILE.write_text(_dump(design))
    VALUES_FILE.write_text(_dump(values))


ROUNDING_NOISE = ("floor", "ledger_residual", "honest_error", "observed_order",
                  "min_heat_increment", "heat_increment_allowance", "error_fmol")


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
    out = []
    committed_inputs = json.loads(worlds.INPUTS.read_text())
    if committed_inputs != json.loads(json.dumps(worlds.build())):
        out.append("inputs: the committed reference_inputs.json differs from worlds.build()")
    design, values = build()
    out += _same(json.loads(DESIGN_FILE.read_text()), design, "design", rtol=1e-6)
    out += _same(json.loads(VALUES_FILE.read_text()), values, "values", rtol=1e-9)
    return out


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
