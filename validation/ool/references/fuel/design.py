"""The registered design of OL5's fuel references: rows, roles, worlds, runs, tolerances, and the
loaders of the registered inputs (``designs/``). ``write_all`` generates every committed file; a
test holds the committed copies byte-equal to it.

**Statistics** (row OL4-6's long run). N_net(t), the net count of fuel events, has mean
J t + (u(n_0) - pi u) + o(1) and variance D t + o(t) from a fixed start n_0, where Q u = -(h - J)
(``stationary.poisson``). The check is two-sided, z = (N_net - J t - (u(n_0) - pi u))/sqrt(D t) with
|z| <= 3.29 (alpha = 1e-3, the references' family-wise level, ``common.ALPHA``). The registered run
length gives power >= 0.99 against the planted engines listed in ``REGISTERED_MAGNITUDES`` (their
own J, computed exactly), and the forward-only flux, a reader's error, is caught pathwise by the
heat identity.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from ..common import ALPHA, MIN_POWER, CheckResult
from ..ledger import check_ledger
from ..world import Conventions
from . import bistability as BI
from . import chem as C
from . import kernel as K
from . import registered as R
from . import stationary as ST
from . import vesicle as V

DESIGN_FILE = "ol4_design.json"
ROWS = {
    "OL4-1": "The pair identity with fuel: ln a+ - ln a- = -Delta F + w, w = -Sum_held nu mu (fuel note §5 check 1), "
             "with the forward form and the reverse rates; in worlds without geometry and in a vesicle world (V1)",
    "OL4-2": "The cycle's drive: Sum ln(a+/a-) = mu_F - mu_W around every fuel cycle and 0 around every other "
             "(§5 check 3); Kolmogorov fails by exactly the drive",
    "OL4-3": "Closure with fuel: F(n_t) - F(n_0) = W - Q at every row, held and finite fuel, and the payers' split "
             "W = Sum_h mu_h supplied_h (§5 check 2)",
    "OL4-4": "Moieties: Sum M n - Sum_held M supplied constant for the block and the fuel (§5 check 5)",
    "OL4-5": "True equilibrium: at mu_F = mu_W the stationary law is exp(-F)/Z, with beta > 0 and beta = 0 "
             "(§5 check 4); and with finite fuel; and in a vesicle (V1)",
    "OL4-6": "The driven steady state: the law against the reference's, the fuel flux, mean heat rate = J A "
             "(§5 check 6), and on one long run the heat identity and the flux by a z-test",
    "OL4-7": "Modality (reported, registered definition) and the mean switching time from the engine's table "
             "(§3 (d))",
    "OL4-8": "§2.3's closed form, exact, with its nulls (equilibrium, beta = 0, the dividing null) and (d0); no "
             "engine record",
    "OL4-9": "The registered refusals (L1: a factor on a pool-only step)",
}

Z_CRIT = 3.290526731491926          # two-sided normal quantile at alpha = 1e-3
Z_POWER = 2.3263478740408408        # one-sided normal quantile at power 0.99
KERNEL_WORLDS = ("ol4_fd_kernel", "ol4_fd_heldB", "ol4_fd_d0", "ol4_fd_null", "ol4_fd_finite")
EQUILIBRIUM_WORLDS = ("ol4_fd_zero", "ol4_fd_zero_beta0", "ol4_fd_finite")
DRIVEN_WORLDS = ("ol4_fd_ness", "ol4_fd_ness_beta0", "ol4_fd_edge", "ol4_fd_edge_beta0")
V_KERNEL_WORLDS = ("ol4_fv_kernel",)
V_CLOSED_WORLDS = ("ol4_fv_closed",)
STATE_FILES = {"ol4_fd_ness": "ol4_fd_ness_states.json", "ol4_fd_ness_beta0": "ol4_fd_ness_states.json",
               "ol4_fd_zero": "ol4_fd_ness_states.json", "ol4_fd_zero_beta0": "ol4_fd_ness_states.json",
               "ol4_fd_edge": "ol4_fd_edge_states.json", "ol4_fd_edge_beta0": "ol4_fd_edge_states.json",
               "ol4_fd_finite": "ol4_fd_finite_states.json"}
LEDGER_RUNS = {
    "ol4_run_fuel_held": dict(world="ol4_fd_kernel", max_events=2000, row_every=100, t_end=1e9, seed=401),
    "ol4_run_fuel_finite": dict(world="ol4_fd_finite", max_events=2000, row_every=100, t_end=1e9, seed=402),
    "ol4_run_heldF": dict(world="ol4_fd_heldF", max_events=2000, row_every=100, t_end=1e9, seed=403),
    "ol4_run_heldB": dict(world="ol4_fd_heldB", max_events=2000, row_every=100, t_end=1e9, seed=404),
    "ol4_run_d0": dict(world="ol4_fd_d0", max_events=2000, row_every=100, t_end=1e9, seed=405),
    "ol4_run_null": dict(world="ol4_fd_null", max_events=2000, row_every=100, t_end=1e9, seed=406),
}
NESS_RUN = dict(id="ol4_run_ness_long", world="ol4_fd_ness", max_events=200000, row_every=10000, t_end=1e12, seed=407)
SWITCH_START: dict = {}
"""The registered start of each driven world's switching time: its reference law's most likely
state in the L1-rich region (filled at registration, ``switch_starts``)."""

REGISTERED_MAGNITUDES: dict = {}
"""The planted controls' magnitudes on the registered inputs (filled at registration)."""


# ---------------------------------------------------------------------------- loaders

def _read(name: str) -> dict:
    return json.loads((R.DESIGN_DIR / name).read_text())


def kernel_inputs(wid: str) -> tuple:
    d = _read(f"{wid}_probe_states.json")
    return np.asarray(d["states"], dtype=np.int64), d["cycles"]


def closed_inputs(wid: str) -> np.ndarray:
    return np.asarray(_read(STATE_FILES[wid])["states"], dtype=np.int64)


def v_world(wid: str) -> V.FuelWorld2:
    return R.v_worlds()[wid]


def _vstates(raw) -> list:
    return [tuple(tuple(x) for x in s) for s in raw]


def v_kernel_inputs(wid: str) -> tuple:
    d = _read(f"{wid}_probe_states.json")
    return _vstates(d["states"]), d["cycles"]


def v_closed_inputs(wid: str) -> list:
    return _vstates(_read(f"{wid}_states.json")["states"])


def drive(wid: str) -> float:
    """mu_F - mu_W of a world with held fuel and waste (k_BT)."""
    w = R.registered_world(wid)
    mu = {p.species: p.mu0_kT + math.log(float(p.held_mM.exact / w.c0_mM.exact)) for p in w.places.values()
          if p.held}
    return mu["F"] - mu["W"]


# ---------------------------------------------------------------------------- the long run

def long_run_checks(law, states, ref: dict, table, n0, rec: dict, reader: str | None = None) -> dict:
    """Row OL4-6 on the long run: closure at its rows, the pathwise heat identity
    |Q_t - N_net A + (F(n_t) - F(n_0))| within the closure bound, and the z-test of N_net."""
    out = {}
    c = check_ledger(law, table, n0, rec["event_channel"], rec["row_event"], rec["counts"], rec["heat_kT"],
                     rec["work_kT"])
    out["closure"] = c
    r = ST.fuel_step_index(law.world)
    codes = np.asarray(rec["event_channel"], dtype=np.int64)
    fwd = [cd for cd, s, st in zip(table.code, table.sign, table.step) if st == r and s > 0][0]
    rev = [cd for cd, s, st in zip(table.code, table.sign, table.step) if st == r and s < 0][0]
    n_f, n_r = int(np.sum(codes == fwd)), int(np.sum(codes == rev))
    n_net = n_f if reader == "forward_only" else n_f - n_r
    t = float(np.asarray(rec["event_time"])[-1])
    A = drive(law.world.name)
    Ft = law.free_energy(tuple(int(v) for v in np.asarray(rec["counts"])[-1]))
    F0 = law.free_energy(tuple(int(v) for v in n0))
    Q = float(np.asarray(rec["heat_kT"])[-1])
    gap = Q - (n_net * A - (Ft - F0))
    tol = abs(c.detail.get("max_abs_closure", 0.0)) + 1e-9 * (abs(Q) + abs(n_net * A)) + 1e-9
    out["heat_identity"] = CheckResult("heat_is_net_fuel_events_times_drive", abs(gap) <= tol,
                                       dict(Q=Q, N_forward=n_f, N_reverse=n_r, N_net=n_net, drive=A, dF=Ft - F0,
                                            gap=gap, tol=tol, reader=reader))
    idx = {tuple(int(v) for v in s): k for k, s in enumerate(states)}
    bias = float(ref["u"][idx[tuple(int(v) for v in n0)]] - ref["pi"] @ ref["u"])
    z = (n_net - ref["J"] * t - bias) / math.sqrt(ref["D"] * t)
    out["flux"] = CheckResult("net_fuel_flux_z_test", abs(z) <= Z_CRIT,
                              dict(N_net=n_net, t=t, J=ref["J"], D=ref["D"], bias=bias, z=z, z_crit=Z_CRIT,
                                   reader=reader))
    return out


def power(J: float, J_planted: float, D: float, t: float) -> float:
    """Two-sided power of the z-test at time t against a planted flux (normal approximation)."""
    from math import erf, sqrt

    shift = abs(J_planted - J) * math.sqrt(t / D)
    Phi = lambda x: 0.5 * (1 + erf(x / sqrt(2)))  # noqa: E731
    return Phi(shift - Z_CRIT) + Phi(-shift - Z_CRIT)


# ---------------------------------------------------------------------------- predictions

def reduced_at_fast_exchange(c: C.Chem) -> BI.Reduced:
    """§2.3's reduced model at a held-block world's fast-exchange fractions x_B = K_B c_B/c0,
    x_S = K_S c_S/c0, T = 1 - x_B - x_S (membrane B, S, L only)."""
    xB = c.em_B_bil / c.em_B_sol * c.held["B"]
    xS = c.em_S_bil / c.em_S_sol * c.held["S"]
    return BI.Reduced(beta=c.beta, xB=xB, xS=xS, T=1 - xB - xS, k1=c.k1, k2=c.k2, E1=c.e_delta1, E2=c.e_delta2)


def zero_affinity_predictions() -> dict:
    out = {}
    for wid, c in (("ol4_fd_d0", R.D0), ("ol4_fd_null", R.NULL)):
        p = reduced_at_fast_exchange(c)
        cf = BI.closed_form(p)
        out[wid] = dict(A=p.A, rho=float(p.rho), rho_exact=str(p.rho), bistable=cf["bistable"],
                        stable=cf["stable"], gamma_even=cf["gamma_even"], gamma_stable=cf["gamma_stable"],
                        raw_stable=BI.raw_count(p)["stable"])
    return out


# ---------------------------------------------------------------------------- generation

def switch_starts(laws_states: dict) -> dict:
    out = {}
    for wid, (law, states, pi) in laws_states.items():
        R1, _ = ST.regions(law.world, states)
        k = int(np.argmax(np.where(R1, pi, -1.0)))
        out[wid] = [int(v) for v in states[k]]
    return out


def design_document() -> dict:
    return {
        "format": "ool_references.fuel_design@1",
        "registered": C.REGISTERED_ON,
        "source": C.SOURCE,
        "rulings": "lead, 20 November 2026: Q1 zero drive is mu_F = mu_W with held potentials including their "
                   "activities; Q2 every arm compared by total variation, modality reported under the registered "
                   "definition, the bimodal (d) world chosen by an exact search at M 14-16, the edge regime a "
                   "reported counter-example, comparable amphiphile counts; Q3 V1 in this registration, the "
                   "composed population run later; Q4 the switching time from the engine's table; Q5 the driven-"
                   "law refusal is the builder's registration test; Q6 a constructed set with gamma = 0",
        "conventions": [{"condensed_measure": "multinomial", "last_molecule": "kept"}],
        "rows": ROWS,
        "roles": {"kernel": list(KERNEL_WORLDS), "tables": sorted(set(EQUILIBRIUM_WORLDS + DRIVEN_WORLDS)),
                  "vkernel": list(V_KERNEL_WORLDS), "vtables": list(V_CLOSED_WORLDS),
                  "runs": list(LEDGER_RUNS) + [NESS_RUN["id"]], "refusals": list(R.refusal_documents())},
        "ledger_runs": LEDGER_RUNS,
        "ness_run": NESS_RUN,
        "switch_start": SWITCH_START,
        "tolerances": {
            "kernel": "64u(4 + |ln a+| + |ln a-| + |dF|) per edge; 64u(rates + Sum |ln a| + |target|) per cycle",
            "closure": "OL1-5's derived bound", "payers": "2(16 u E (1 + max|mu|) + 4 u Sum|mu s|)",
            "moieties": "exact integers",
            "equilibrium_tv": ST.TV_EQUILIBRIUM, "driven_tv": ST.TV_DRIVEN, "flux_and_heat_rtol": ST.FLUX_RTOL,
            "switching_rtol": ST.MFPT_RTOL, "vesicle_log_atol": V.LOG_ATOL, "vesicle_forward_rtol": V.FORWARD_RTOL,
            "vesicle_tv": V.STATIONARY_TV, "z_crit": Z_CRIT, "alpha": ALPHA, "min_power": MIN_POWER},
        "modality": {"definition": "clusters of local maxima of the law of (L1@membrane, L2@membrane) over the "
                                   "8-neighbourhood, ties merged, peaks >= 1/20 of the largest; kinds one_central, "
                                   "two_interior, two_edge, one_offcentre, other",
                     "switch_regions": "share f = L1/(L1 + L2) with L1 + L2 >= 2: R1 f >= 3/4, R2 f <= 1/4"},
        "closed_form": {"sample_seed": BI.SAMPLE_SEED, "sample_size": BI.SAMPLE_SIZE,
                        "planted": list(BI.PLANTED)},
        "search": {"what": "evidence/search in the OL5 fuel staging folder: search_interior.py, candidates.py and "
                           "their JSON-line outputs", "pick": {k: str(v) for k, v in R.NESS.items()},
                   "edge": {k: str(v) for k, v in R.EDGE.items()}},
        "magnitudes": REGISTERED_MAGNITUDES,
    }


def write_all(out_dir=None) -> list:
    """Every committed design file: worlds, probe states with cycles, state lists, refusals and the
    design document."""
    out = Path(out_dir) if out_dir is not None else R.DESIGN_DIR
    out.mkdir(parents=True, exist_ok=True)
    (out / "refusals").mkdir(exist_ok=True)
    paths = []
    docs = R.world_documents()
    for wid, doc in docs.items():
        p = out / f"{wid}.world.json"
        p.write_bytes(R.canonical_bytes(doc))
        paths.append(p)
    for wid, doc in R.v_documents().items():
        p = out / f"{wid}.world2.json"
        p.write_bytes(R.canonical_bytes(doc))
        paths.append(p)
    from .law import parse_fuel_world

    for wid in KERNEL_WORLDS:
        w = parse_fuel_world(docs[wid])
        states, bases, cycles = K.probe_states(w, R.PROBE_SEED, R.PROBE_BASES, R.PROBE_MAX_COUNT)
        doc = {"format": "ool_references.fuel_probe_states@1", "world": wid, "registered": C.REGISTERED_ON,
               "seed": R.PROBE_SEED, "bases": [list(map(int, b)) for b in bases], "cycles": cycles,
               "count": int(len(states)), "places": [p.name for p in w.finite],
               "states": [list(map(int, s)) for s in states]}
        p = out / f"{wid}_probe_states.json"
        p.write_bytes(R.states_bytes(doc))
        paths.append(p)
    for name, wid in (("ol4_fd_ness_states.json", "ol4_fd_ness"), ("ol4_fd_edge_states.json", "ol4_fd_edge"),
                      ("ol4_fd_finite_states.json", "ol4_fd_finite")):
        w = parse_fuel_world(docs[wid])
        totals = {q: int(v) for q, v in zip(w.moiety_names(),
                                            np.asarray(w.moiety_matrix()) @ np.asarray(w.state_from(w.initial_state)))}
        states = ST.reachable_states(w, w.initial_state)
        doc = {"format": "ool_references.fuel_states@1", "worlds": sorted(k for k, v in STATE_FILES.items()
                                                                         if v == name),
               "registered": C.REGISTERED_ON, "moiety_totals": totals, "count": int(len(states)),
               "places": [p.name for p in w.finite], "states": [list(map(int, s)) for s in states]}
        p = out / name
        p.write_bytes(R.states_bytes(doc))
        paths.append(p)
    vws = R.v_worlds()
    law = V.FuelLaw2(vws["ol4_fv_kernel"])
    states, cycles = V.kernel_probe(law, R.V_SEED, R.V_BASES, R.lumen_for(R.VQ))
    doc = {"format": "ool_references.fuel_probe_states2@1", "world": "ol4_fv_kernel", "registered": C.REGISTERED_ON,
           "seed": R.V_SEED, "cycles": cycles, "count": len(states),
           "states": [[list(a), list(b), list(c)] for a, b, c in states]}
    p = out / "ol4_fv_kernel_probe_states.json"
    p.write_bytes(R.states_bytes(doc))
    paths.append(p)
    lc = V.FuelLaw2(vws["ol4_fv_closed"])
    st = V.closed_states(lc, R.V_CLOSED_TOTAL)
    doc = {"format": "ool_references.fuel_states2@1", "world": "ol4_fv_closed", "registered": C.REGISTERED_ON,
           "block_total": R.V_CLOSED_TOTAL, "count": len(st), "states": [[list(a), list(b), list(c)] for a, b, c in st]}
    p = out / "ol4_fv_closed_states.json"
    p.write_bytes(R.states_bytes(doc))
    paths.append(p)
    for rid, doc in R.refusal_documents().items():
        p = out / "refusals" / f"{rid}.world.json"
        p.write_bytes(R.canonical_bytes(doc))
        paths.append(p)
    p = out / DESIGN_FILE
    p.write_bytes((json.dumps(design_document(), indent=1) + "\n").encode())
    paths.append(p)
    return paths
