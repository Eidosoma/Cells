"""Consistency checks over the interface files, independent of the code that wrote them.

Each check recomputes something from the stored numbers and the world descriptions in
inputs.json, and raises CheckError with a message naming what disagrees. Light by design (json,
math and numpy only), so that tests/unit/test_gene_regulation_references.py runs in about a
second. Used by that test and by the run before it writes the interface.
"""

from __future__ import annotations

import copy
import json
import math
from pathlib import Path

import numpy as np

from . import sheet

INTERFACE = Path(__file__).resolve().parent / "interface"
FILES = ("inputs", "trajectories_test_instances", "trajectories_edge_sets", "endpoints",
         "r_chain", "r_machine", "r_account", "r_noise", "plants", "convergence")
SHEET_PLANT_IDS = ("A1-1", "A1-2", "A1-3", "A1-4", "A1-5", "A1-6", "A1M-1", "A1M-2")
OWN_PLANT_IDS = ("own-1", "own-2", "own-3", "own-4", "own-5")


class CheckError(AssertionError):
    pass


def require(cond, msg: str) -> None:
    if not cond:
        raise CheckError(msg)


def load(folder: Path = INTERFACE) -> dict:
    return {name: json.loads((Path(folder) / f"{name}.json").read_text()) for name in FILES}


def copy_of(data: dict) -> dict:
    return copy.deepcopy(data)


# ---- the world descriptions -------------------------------------------------------------------
def _worlds(data: dict) -> dict:
    return {w["name"]: w for w in data["inputs"]["worlds"]}


def expected_readouts(w: dict) -> list[str]:
    names = [f"n_{s}" for s in w["rows0_fmol"]]
    names += [f"F_{q}" for q in w["pools_fmol"]]
    for r in w["routes"]:
        names += [f"C_{r['name']}_{j}" for j in range(1, r["m"] + 1)]
        names += [f"E_{r['name']}", f"W_{r['name']}", f"int_J_I_{r['name']}",
                  f"int_S_{r['name']}", f"int_Q_{r['name']}"]
    names += [f"int_D_{d['row']}" for d in w["degradations"]]
    if w["recharging"]:
        names += ["int_J_C", "H_rc", "dG_rc"]
    kinds = {r["kind"] for r in w["routes"]}
    names += ["G_minus_G0"] + [f"H_{k}" for k in sorted(kinds)]
    names += [f"dG_{k}" for k in sorted(kinds)]
    names += [f"dG_rel_{r['product']}" for r in w["routes"]]
    names += [f"dG_deg_{d['row']}" for d in w["degradations"]]
    names += ["H_deg_R"] if any(d["monomer"] == "M" for d in w["degradations"]) else []
    names += ["H_deg_P"] if any(d["monomer"] == "A" for d in w["degradations"]) else []
    if w["regulator"]:
        names.append("u")
    if w["window"]:
        names += [f"J_bar_{r['name']}" for r in w["routes"]]
    return names


def check_complete(data: dict) -> None:
    inp = data["inputs"]
    sets = inp["potential_sets"]
    require(len(sets) == 50, f"potential sets: {len(sets)}, expected 50 (§5.6)")
    require(inp["edge_sets"] == list(range(18)), "edge sets: expected the first 18")
    worlds = _worlds(data)
    require(len(worlds) == 16, f"worlds: {len(worlds)}, expected 16")
    full = data["trajectories_test_instances"]["sets"]
    require(sorted(full) == ["0", "1"], "full trajectories: the two test instances")
    for i, rec in full.items():
        traj = rec["worlds"]
        require(set(traj) == set(worlds), f"set {i} trajectories: worlds differ from inputs")
        for name, w in worlds.items():
            n_t = int(round(w["t_end"] / w["dt"])) + 1
            t = traj[name]["t"]
            require(len(t) == n_t and t[0] == 0 and t[-1] == w["t_end"],
                    f"set {i} {name}: output grid")
            ro = traj[name]["readouts"]
            for k in expected_readouts(w):
                require(k in ro, f"set {i} {name}: readout {k} missing")
                if not k.startswith("J_bar_"):
                    require(len(ro[k]) == n_t, f"set {i} {name}: readout {k} has {len(ro[k])}")
    edge = data["trajectories_edge_sets"]["sets"]
    require(sorted(edge, key=int) == [str(i) for i in range(2, 18)], "edge-set trajectories")
    for i, rec in edge.items():
        require(set(rec["worlds"]) == set(worlds), f"edge set {i}: worlds")
    ends = data["endpoints"]["sets"]
    require([e["set"] for e in ends] == list(range(18, 50)) and all(
        len(e["worlds"]) == 17 for e in ends), "endpoints: the 32 interior sets")
    require(len(data["r_chain"]["sets"]) == 50, "R-chain sets")
    require(len(data["r_chain"]["test_instance"]["closed_form"]["n_R"]) == 180, "R-chain series")
    require(len(data["r_machine"]["sets"]) == 50 and all(
        len(r["worlds"]) == 15 for r in data["r_machine"]["sets"]), "R-machine sets")
    require(len(data["r_account"]["rows"]) == 800, "R-account rows")
    require(len(data["convergence"]["rows"]) == 800, "convergence rows")
    nz = data["r_noise"]["worlds"]
    require(set(nz) == {"A1", "T10"}, "R-noise worlds")
    require(nz["A1"]["N"] == sheet.NOISE_REPLICATES and nz["T10"]["N"] == sheet.NOISE_REPLICATES,
            "R-noise: replicates")
    require(all(len(v["mean"]) == 181 for v in nz["A1"]["readouts"].values()), "R-noise A1 grid")
    require(all(len(v["mean"]) == 121 for v in nz["T10"]["readouts"].values()), "R-noise T10 grid")
    ids = {k.split()[0] for k in data["plants"]["summary"]}
    for pid in SHEET_PLANT_IDS + OWN_PLANT_IDS:
        require(pid in ids, f"plant {pid} missing")


# ---- identities, recomputed from the stored trajectories ---------------------------------------
def _moiety_weights(w: dict, moieties: dict) -> dict:
    out = {}
    for moiety, table in moieties.items():
        wt = {}
        for key, val in table.items():
            if key in ("R", "P"):
                for s, L in w["lengths"].items():
                    if (s.startswith("R") and key == "R") or (s == "P" and key == "P"):
                        wt[f"n_{s}"] = float(L)
            elif key in ("R_res", "P_res"):
                for r in w["routes"]:
                    if (r["kind"] == "tx") == (key == "R_res"):
                        wt[f"W_{r['name']}"] = float(val)
            elif key in w["rows0_fmol"]:
                wt[f"n_{key}"] = float(val)
        if wt:
            out[moiety] = wt
    return out


def identity_levels(name: str, w: dict, ro: dict, moieties: dict) -> dict:
    """§4.8's identities (and §1.2's W) as level = max|residual| / scale (scales at t_end)."""
    a = {k: np.asarray(v, float) for k, v in ro.items()}
    lv = {}
    for q, M in w["pools_fmol"].items():
        E = sum(a[f"E_{r['name']}"] for r in w["routes"] if r["pool"] == q)
        lv[f"machines_{q}"] = np.max(np.abs(a[f"F_{q}"] + E - M)) / M
    for r in w["routes"]:
        n, L, m = r["name"], r["L"], r["m"]
        rr = L // m
        S, Q, W = a[f"int_S_{n}"], a[f"int_Q_{n}"], a[f"W_{n}"]
        scale = rr * S[-1]
        lv[f"residues_{n}"] = np.max(np.abs(rr * S - W - L * Q)) / scale
        Wdef = rr * sum(j * a[f"C_{n}_{j + 1}"] for j in range(m))
        lv[f"W_definition_{n}"] = np.max(np.abs(W - Wdef)) / scale
        Esum = sum(a[f"C_{n}_{j}"] for j in range(1, m + 1))
        lv[f"E_sum_{n}"] = np.max(np.abs(a[f"E_{n}"] - Esum)) / np.max(np.abs(a[f"E_{n}"]))
        p = r["product"]
        D = a.get(f"int_D_{p}", 0.0)
        prod = a[f"n_{p}"]
        lv[f"products_{p}"] = (np.max(np.abs(prod - prod[0] - Q + D)) / (prod[0] + Q[-1]))
    for moiety, wt in _moiety_weights(w, moieties).items():
        tot = sum(v * a[k] for k, v in wt.items())
        lv[f"moiety_{moiety}"] = np.max(np.abs(tot - tot[0])) / abs(tot[0])
    H = sum(a[k] for k in ("H_tx", "H_tl", "H_deg_R", "H_deg_P", "H_rc") if k in a)
    lv["energy"] = np.max(np.abs(a["G_minus_G0"] + H)) / H[-1]
    return {k: float(v) for k, v in lv.items()}


def check_identities(data: dict, tol: float = sheet.TOL_IDENTITY) -> dict:
    worlds = _worlds(data)
    moieties = data["inputs"]["declared"]["moieties"]
    out = {}
    for i, full in data["trajectories_test_instances"]["sets"].items():
        for name, rec in full["worlds"].items():
            lv = identity_levels(name, worlds[name], rec["readouts"], moieties)
            for k, v in lv.items():
                require(v <= tol, f"set {i} {name}: identity {k} at {v:.3e} > {tol:g}")
            out[(i, name)] = lv
    return out


def check_window(data: dict) -> None:
    for name, w in _worlds(data).items():
        if not w["window"]:
            continue
        k_end = int(round(w["t_end"] / w["dt"]))
        k_w = int(round((w["t_end"] - w["window"]) / w["dt"]))
        for i, full in data["trajectories_test_instances"]["sets"].items():
            ro = full["worlds"][name]["readouts"]
            for r in w["routes"]:
                q = ro[f"int_Q_{r['name']}"]
                jb = (q[k_end] - q[k_w]) / w["window"]
                stored = ro[f"J_bar_{r['name']}"][0]
                require(abs(jb - stored) <= 1e-12 * abs(jb),
                        f"set {i} {name}: J̄_{r['name']} {stored} ≠ {jb}")


# ---- closed forms, recomputed in floats --------------------------------------------------------
def _consts(data: dict) -> dict:
    c = data["inputs"]["constants"]
    return {"RT": float(c["RT_kJ_mol"]), "c1": float(c["c_1_mM"]),
            "fpc": float(c["fmol_per_copy"])}


def _mu0(p: dict, RT: float) -> dict:
    g = float(p["G_ATP_kJ_mol"]) / RT
    mu = {"ADP": 0.0, "Pi": 0.0, "M": 0.0, "A": 0.0, "ATP": g * -1.0}
    mu["N"] = float(p["E_rc_RT"]) + 2 * mu["ATP"]
    mu["R_res"] = -float(p["E_pd_kJ_mol"]) / RT
    mu["P_res"] = -float(p["E_pep_kJ_mol"]) / RT
    return mu


def machine_closed(data: dict, p: dict, name: str) -> dict:
    """§5.2's J*, E*, F* in floats from the declared values and the four symbols."""
    k = _consts(data)
    A1, A1M = data["inputs"]["declared"]["A1"], data["inputs"]["declared"]["A1M"]
    mu = _mu0(p, k["RT"])
    la = lambda c: math.log(float(c) / 1000.0)  # noqa: E731
    w = _worlds(data)[name]
    if name.startswith("rib"):
        x = (mu["P_res"] + 4 * la(A1["c_ADP"]) + 4 * la(A1["c_Pi"]) - la(A1M["c_A"])
             - 4 * (mu["ATP"] + la(A1["c_ATP"])))
        sat = (float(A1M["c_A"]) / (float(A1["K_A_tl"]) + float(A1M["c_A"]))
               * float(A1["c_ATP"]) / (float(A1["K_ATP_tl"]) + float(A1["c_ATP"])))
        v, kI, M = float(A1["v_tl"]), float(A1M["k_I_tl"]), float(A1M["M_rib"]) * k["fpc"]
        nR = w["rows0_fmol"]["R"] / k["fpc"]
        genes = [("tl", A1["L_P"], round(nR))]
    else:
        x = mu["R_res"] + 2 * la(A1["c_Pi"]) - (mu["N"] + la(A1M["c_N"]))
        sat = float(A1M["c_N"]) / (float(A1["K_N_tx"]) + float(A1M["c_N"]))
        v, kI, M = float(A1["v_tx"]), float(A1M["k_I_tx"]), float(A1M["M_pol"]) * k["fpc"]
        genes = [(r["name"], r["L"], r["copies"]) for r in w["routes"]]
    phi = sat * -math.expm1(x)
    lam = {g: kI * k["c1"] * n for g, _, n in genes}
    tau = {g: L / (v * phi) for g, L, _ in genes}
    den = 1 + sum(lam[g] * tau[g] for g in lam)
    out = {"F": M / den}
    for g in lam:
        out[f"J_{g}"] = lam[g] * M / den
        out[f"E_{g}"] = out[f"J_{g}"] * tau[g]
    return out


def check_machine(data: dict, rel: float = 1e-12) -> None:
    sets = data["inputs"]["potential_sets"]
    for row in data["r_machine"]["sets"]:
        p = sets[row["set"]]
        for name, d in row["worlds"].items():
            mine = machine_closed(data, p, name)
            for key, v in mine.items():
                stored = float(d["closed"][key])
                require(abs(stored - v) <= rel * abs(v),
                        f"R-machine {name} set {row['set']}: {key} {stored} ≠ {v}")
            for key, g in d["gaps"].items():
                ck = "F" if key.startswith("F_") else key.replace("J_bar_", "J_")
                c = float(d["closed"][ck])
                mine_g = abs(d["ode"][key] - c) / c
                require(abs(mine_g - g) <= 1e-9 * max(g, 1e-300) + 1e-18,
                        f"R-machine {name} set {row['set']}: gap {key}")
            require(d["within_eps_M"] == (max(d["gaps"].values()) <= sheet.EPS_M),
                    f"R-machine {name} set {row['set']}: within flag")


def _P(j: int, y: float) -> float:
    term, total = 1.0, 0.0
    for i in range(j):
        if i:
            term *= y / i
        total += term
    return 1.0 - math.exp(-y) * total


def check_chain(data: dict, rel: float = 1e-12) -> None:
    A1 = data["inputs"]["declared"]["A1"]
    ti = data["r_chain"]["test_instance"]
    fr = {k: float(v) for k, v in ti["frozen"].items()}
    J, k0R, kap = fr["J_I_tx"], fr["k0_R"], fr["kappa0_tx"]
    m = A1["m_tx"]
    st = {k: float(v) for k, v in ti["steady"].items()}
    require(abs(st["n_R"] - J / k0R) <= rel * st["n_R"], "R-chain: n_R* ≠ J/k0_R")
    require(abs(st["E_tx"] - J * fr["tau0_tx"]) <= rel * st["E_tx"], "R-chain: E_tx* ≠ J τ0")
    require(abs(st["n_P"] - fr["beta_tl"] * st["n_R"] / fr["k0_P"]) <= rel * st["n_P"],
            "R-chain: n_P* ≠ β n_R*/k0_P")
    nR0 = float(A1["c_R"]) * float(A1["V"])
    for k in (1, 5, 30, 179):  # §5.1's scalar formulas at a few outputs
        t = float(ti["times"][k])
        dk = kap - k0R
        nR = nR0 * math.exp(-k0R * t) + J / k0R * (
            _P(m, kap * t) - math.exp(-k0R * t) * (kap / dk) ** m * _P(m, dk * t))
        E = J / kap * sum(_P(j, kap * t) for j in range(1, m + 1))
        require(abs(float(ti["closed_form"]["n_R"][k]) - nR) <= 1e-11 * abs(nR),
                f"R-chain: n_R({t}) differs from §5.1's formula")
        require(abs(float(ti["closed_form"]["E_tx"][k]) - E) <= 1e-11 * abs(E),
                f"R-chain: E_tx({t}) differs from §5.1's formula")
    ro = data["trajectories_test_instances"]["sets"]["0"]["worlds"]["A1"]["readouts"]
    stored = data["r_chain"]["sets"][0]["gaps"]
    for key in ("n_R", "n_P", "E_tx", "E_tl"):
        cf = np.array([float(x) for x in ti["closed_form"][key]])
        g = float(np.max(np.abs(cf - np.asarray(ro[key][:180]))) / st[key])
        require(abs(g - stored[key]) <= 1e-9 * stored[key], f"R-chain: gap {key}")
    for row in data["r_chain"]["sets"]:
        require(row["within_eps_A1"] == (row["gap_max"] <= sheet.EPS_A1), "R-chain within flag")


def check_noise(data: dict) -> None:
    for w, d in data["r_noise"]["worlds"].items():
        N = d["N"]
        outside = 0
        n = 0
        for name, r in d["readouts"].items():
            mean, se, det = (np.asarray(r[k], float) for k in ("mean", "se", "det"))
            band = sheet.NOISE_BAND_SE * se + sheet.NOISE_FLOOR / N
            gap = np.abs(mean - det)
            require(np.allclose(band, r["band"], rtol=1e-14, atol=0), f"R-noise {w} {name}: band")
            require(np.allclose(gap, r["gap"], rtol=1e-12, atol=1e-12), f"R-noise {w} {name}: gap")
            outside += int((gap > band).sum())
            n += gap.size
        require(outside == d["outside"] and n == d["comparisons"], f"R-noise {w}: counts")
        require(d["passes"] == (outside == 0), f"R-noise {w}: verdict")
    require(data["r_noise"]["worlds"]["T10"]["passes"], "R-noise: the T = 10 control is outside")


def check_plants(data: dict) -> None:
    rows = data["plants"]["rows"]
    tol = {"trajectory": sheet.TOL_TRAJECTORY, "identity": sheet.TOL_IDENTITY}
    factor = {"trajectory": 10}  # a trajectory change counts beyond 10× the resolution
    for r in rows:
        for v in r["verdicts"]:
            kind = v["item"].split()[0]
            t = tol.get(kind, sheet.EPS_M)
            require(v["tolerance"] == t, f"plant {r['id']}: tolerance of {v['item']}")
            if v["measure"] is not None:
                require(abs(v["margin"] - v["measure"] / t) <= 1e-12 * v["margin"],
                        f"plant {r['id']}: margin of {v['item']}")
                require(v["fails"] == (v["measure"] > factor.get(kind, 1) * t),
                        f"plant {r['id']}: verdict {v['item']}")
            name = v["item"].split(" ", 1)[1]
            if kind == "trajectory":
                require(v["measure"] == r["changes"].get(name), f"plant {r['id']}: {name}")
            elif kind == "identity":
                require(v["measure"] == r["identity_levels"].get(name), f"plant {r['id']}: {name}")
    summ = data["plants"]["summary"]
    for key, s in summ.items():
        pid = key.split()[0]
        mine = {}
        for r in rows:
            if f"{r['id']} {'+'.join(r['edits'])}" != key:
                continue
            for v in r["verdicts"]:
                mine.setdefault(v["item"], True)
                mine[v["item"]] &= bool(v["fails"])
        require({k: n["fails_everywhere"] for k, n in s["named"].items()} == mine,
                f"plant {key}: summary")
        if pid in SHEET_PLANT_IDS:
            require(s["caught"], f"plant {key} is not caught")


def check_summaries(data: dict) -> None:
    acc = data["r_account"]["summary"]
    require(acc["all_within_tolerance"], f"R-account: identity at {acc['worst_identity_level']}")
    require(acc["heats_nonnegative_nondecreasing"], "R-account: a heat class decreased")
    rows = data["r_account"]["rows"]
    require(all(min(r["heat_min_increment_rel"].values()) >= -sheet.TOL_IDENTITY
                and min(r["heat_rate_min_rel"].values()) >= -sheet.TOL_IDENTITY for r in rows),
            "R-account: a heat class decreased, or a heat rate is negative, beyond rounding")
    require(all(v <= sheet.X_DOM for r in rows for v in r["domain_max"].values()),
            "R-account: a one-sided move left the domain")
    require(acc["domain_respected"], "R-account: the domain was left")
    worst = max(max(r["identity_levels"].values()) for r in data["r_account"]["rows"])
    require(worst == acc["worst_identity_level"], "R-account: summary's worst level")
    conv = data["convergence"]["summary"]
    require(conv["within"] and conv["worst"] <= sheet.TOL_TRAJECTORY, "convergence: trajectories")
    require(conv["closed_forms_within"], "convergence: closed forms")
    worst_c = max(r["worst"] for r in data["convergence"]["rows"])
    require(worst_c == conv["worst"], "convergence: summary's worst")
    tc = data["inputs"]["transcription_check"]
    bad = [k for k, v in tc.items() if not v["agrees"]]
    require(not bad, f"§5.3 values not reproduced: {bad}")


def check_all(data: dict) -> None:
    check_complete(data)
    check_identities(data)
    check_window(data)
    check_machine(data)
    check_chain(data)
    check_noise(data)
    check_plants(data)
    check_summaries(data)
