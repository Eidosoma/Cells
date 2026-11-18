"""FR-3's registered worlds: the self-contained inputs file, and its parsing into R-ode networks.

    python -m validation.fr3.references.worlds      # writes reference_inputs.json

The worlds follow ``docs/SITE_OCCUPANCY_DESIGN.md`` §8.3's items Q1 to Q5 and §3.4's energy guard
worlds. They are described physically: nodes (cells and closed finite outside nodes) with volumes
and ligand concentrations, site populations with their owner, copies, sites per copy, accessible
fraction, rates and starting occupancy, the multipliers' epochs, and the record times. They are
not engine declarations; the protocol maps them. Every value is synthetic and labelled so (D152
§2.4's rule): K_d = 1 uM, k_on = 1e3 /(mM s), k_int = 0.1 /s and 1e5 copies are a receptor-like
bracket, not a measurement.

Every world is face-free: a population's patch is the only link between its cell and the node it
faces. There is no face and no held bath (version 1 refuses sites facing a held bath), and no
world combines site occupancy with a bath schedule (the lead's scope ruling). The ligand is
neutral and impermeant at every membrane, so the ions, which the protocol keeps quiescent, are
decoupled from it.
"""

from __future__ import annotations

import json
import sys
from fractions import Fraction
from pathlib import Path

from .exact import SITES_PER_FMOL, exact

HERE = Path(__file__).resolve().parent
INPUTS = HERE / "reference_inputs.json"
REGISTERED = "2026-11-17"

K_ON, K_OFF, K_INT = 1.0e3, 1.0, 0.1
COPIES = 1.0e5
TRACE_MM = 1.0e-12
TEMPERATURE_K = 310.0
DT_LADDER = [1e-3, 5e-4, 2.5e-4]


def _records(end_s: float, every_s: float) -> list:
    n = round(end_s / every_s)
    return [float(Fraction(k) * exact(every_s)) for k in range(n + 1)]


def _pop(pid, cell, faces, copies=COPIES, nu=1, alpha=1.0, k_on=K_ON, k_off=K_OFF,
         theta0=0.0, k_int=None, orientation="outward"):
    return {
        "id": pid,
        "owner": {"cell": cell, "orientation": orientation, "faces_node": faces},
        "copies": copies, "sites_per_copy": nu, "accessible_fraction": alpha,
        "association_rate_per_mM_per_s": k_on, "dissociation_rate_per_s": k_off,
        "initial_occupancy": theta0,
        "internalisation": None if k_int is None else {"rate_per_s": k_int,
                                                       "destination": "cell"},
    }


def _world(items, form, nodes, pops, end_s, every_s, controls=None, note=None, trace=TRACE_MM):
    w = {"items": items, "form": form, "temperature_K": TEMPERATURE_K, "trace_mM": trace,
         "nodes": nodes, "populations": pops, "end_s": end_s,
         "record_times_s": _records(end_s, every_s),
         "site_controls": controls or [{"time_s": 0.0, "binding": {p["id"]: 1.0 for p in pops},
                                        "internalisation": {p["id"]: 1.0 for p in pops}}]}
    if note:
        w["note"] = note
    return w


def _cell(V=1.0, c=TRACE_MM):
    return {"kind": "cell", "volume_pL": V, "L_mM": c}


def _node(V, c):
    return {"kind": "finite_outside", "volume_pL": V, "L_mM": c}


def _eps_copies(eps: float, V: float, c0: float, alpha: float = 1.0) -> float:
    """Copies giving eps = (S/V)/(K_M + c0) with K_M = (k_off + k_int)/k_on."""
    KM = (exact(K_OFF) + exact(K_INT)) / exact(K_ON)
    S = exact(eps) * exact(V) * (KM + exact(c0))
    return float(S * SITES_PER_FMOL / exact(alpha))


def build() -> dict:
    W = {}
    c0 = 1e-4
    KM = (K_OFF + K_INT) / K_ON
    theta_q = float(exact(c0) / ((exact(K_OFF) + exact(K_INT)) / exact(K_ON) + exact(c0)))
    for tag, eps in (("1e-1", 1e-1), ("1e-2", 1e-2), ("1e-3", 1e-3)):
        W[f"q1_eps_{tag}"] = _world(
            ["Q1"] + (["Q5 mixed"] if tag == "1e-1" else []),
            "binding with internalisation, occupancy pre-formed at its quasi-steady value at c0"
            + ("; the receiving cell is 2 pL" if tag == "1e-1" else ""),
            {"cell_0": _cell(V=2.0 if tag == "1e-1" else 1.0), "ecs_0": _node(1.0, c0)},
            [_pop("r0", "cell_0", "ecs_0", copies=_eps_copies(eps, 1.0, c0), theta0=theta_q,
                  k_int=K_INT)], 20.0, 0.1,
            note=f"eps = (S/V)/(K_M + c0) = {eps:g}, K_M = (k_off + k_int)/k_on = {KM:g} mM")
    # Q1's dt-study world: the same eps = 0.1 at rates 100 times faster, so that an honest
    # third-order engine's error stands above the reference's floor on the ladder.
    fast_on, fast_off, fast_int = 1.0e5, 100.0, 10.0
    KMf = (exact(fast_off) + exact(fast_int)) / exact(fast_on)
    W["q1_fast"] = _world(
        ["Q1 dt study"],
        "Q1's eps = 0.1 world with every rate 100 times faster (K_d and K_M unchanged)",
        {"cell_0": _cell(), "ecs_0": _node(1.0, c0)},
        [_pop("r0", "cell_0", "ecs_0", copies=float(exact(0.1) * (KMf + exact(c0)) *
                                                     SITES_PER_FMOL),
              k_on=fast_on, k_off=fast_off, theta0=float(exact(c0) / (KMf + exact(c0))),
              k_int=fast_int)], 0.2, 0.002,
        note="dt L_B = (k_off + k_int) dt = 0.11 at 1 ms, inside the stage condition")
    W["q1_eps_1e-1_alpha_half"] = _world(
        ["Q1", "Q4"], "Q1's eps = 0.1 world with half the sites accessible (eps = 0.05)",
        {"cell_0": _cell(), "ecs_0": _node(1.0, c0)},
        [_pop("r0", "cell_0", "ecs_0", copies=_eps_copies(1e-1, 1.0, c0), alpha=0.5,
              theta0=theta_q, k_int=K_INT)], 20.0, 0.1)
    W["q2_large"] = _world(["Q2"], "binding to equilibrium in a large node at c = K_d",
                           {"cell_0": _cell(), "ecs_0": _node(1.0e3, 1.0e-3)},
                           [_pop("r0", "cell_0", "ecs_0")], 10.0, 0.05)
    W["q2_closed"] = _world(["Q2", "Q3", "Q5 closed relaxation"],
                            "binding in a small closed node: depletion (the Riccati form)",
                            {"cell_0": _cell(), "ecs_0": _node(0.1, 1.0e-3)},
                            [_pop("r0", "cell_0", "ecs_0")], 10.0, 0.05)
    W["q2_two_populations"] = _world(
        ["Q2", "Q5 two populations"], "two cells' populations facing one node",
        {"cell_a": _cell(), "cell_b": _cell(), "ecs_0": _node(1.0, 5.0e-4)},
        [_pop("ra", "cell_a", "ecs_0"),
         _pop("rb", "cell_b", "ecs_0", copies=4.0e3, nu=2, k_on=5.0e2, k_off=2.0, theta0=0.1)],
        20.0, 0.1)
    W["q3_association"] = _world(["Q3"], "association in a large node",
                                 {"cell_0": _cell(), "ecs_0": _node(1.0e3, 1.0e-4)},
                                 [_pop("r0", "cell_0", "ecs_0")], 5.0, 0.025)
    W["q3_dissociation"] = _world(["Q3"], "dissociation into a large node held near zero",
                                  {"cell_0": _cell(), "ecs_0": _node(1.0e3, TRACE_MM)},
                                  [_pop("r0", "cell_0", "ecs_0", theta0=0.5)], 5.0, 0.025)
    mb = [{"time_s": t, "binding": {"r0": m}, "internalisation": {"r0": 1.0}}
          for t, m in ((0.0, 1.0), (1.0, 0.25), (4.0, 1.0))]
    W["q3_binding_multiplier"] = _world(
        ["Q3", "Q6 multiplier"],
        "the closed node with the binding multiplier at 1/4 from 1 s to 4 s: k_on and k_off scale "
        "together, so the approach slows and the equilibrium does not move",
        {"cell_0": _cell(), "ecs_0": _node(0.1, 1.0e-3)},
        [_pop("r0", "cell_0", "ecs_0")], 10.0, 0.05, controls=mb)
    W["q3_internalisation"] = _world(["Q3"], "binding and internalisation in a large node",
                                     {"cell_0": _cell(), "ecs_0": _node(1.0e3, 1.0e-4)},
                                     [_pop("r0", "cell_0", "ecs_0", k_int=K_INT)], 5.0, 0.025)
    for alpha, atag in ((1.0, "1"), (0.5, "1/2"), (0.25, "1/4")):
        for c, ctag, end, every in ((1.0e-5, "low", 10.0, 0.05), (0.1, "high", 0.2, 1e-3)):
            W[f"q4_alpha_{atag.replace('/', '_')}_{ctag}"] = _world(
                ["Q4"], f"accessibility alpha = {atag} at c = {c:g} mM "
                        f"({'0.01' if ctag == 'low' else '100'} K_d) in a large node",
                {"cell_0": _cell(), "ecs_0": _node(1.0e6, c)},
                [_pop("r0", "cell_0", "ecs_0", alpha=alpha)], end, every)
    W["q5_passive_from_zero"] = _world(["Q5 passive-only"], "binding from B = 0, closed node",
                                       {"cell_0": _cell(), "ecs_0": _node(1.0, 1.0e-4)},
                                       [_pop("r0", "cell_0", "ecs_0")], 10.0, 0.05)
    W["q5_passive_preformed"] = _world(["Q5 passive-only"],
                                       "a pre-formed occupancy above equilibrium, closed node",
                                       {"cell_0": _cell(), "ecs_0": _node(1.0, 1.0e-4)},
                                       [_pop("r0", "cell_0", "ecs_0", theta0=0.5)], 10.0, 0.05)
    W["q5_washout"] = _world(["Q5 quadrature branch"],
                             "a washout: internalisation drains the bound pool, the node at trace",
                             {"cell_0": _cell(), "ecs_0": _node(1.0, TRACE_MM)},
                             [_pop("r0", "cell_0", "ecs_0", theta0=0.5, k_int=K_INT)], 20.0, 0.1)
    sw = [{"time_s": t, "binding": {"r0": 1.0}, "internalisation": {"r0": m}}
          for t, m in ((0.0, 0.0), (5.0, 1.0), (10.0, 0.0))]
    W["q5_class_switch"] = _world(
        ["Q5 class switch"], "Q1's eps = 0.1 world, internalisation off, on at 5 s, off at 10 s",
        {"cell_0": _cell(), "ecs_0": _node(1.0, c0)},
        [_pop("r0", "cell_0", "ecs_0", copies=_eps_copies(1e-1, 1.0, c0), theta0=theta_q,
              k_int=K_INT)], 20.0, 0.1, controls=sw)
    W["q5_inward"] = _world(
        ["Q5 receiving cell faced by an inward population"],
        "cell_0 (2 pL) receives internalised ligand and is faced by an inward population",
        {"cell_0": _cell(V=2.0), "ecs_0": _node(1.0, c0)},
        [_pop("r_out", "cell_0", "ecs_0", k_int=K_INT),
         _pop("r_in", "cell_0", "cell_0", copies=2.0e4, orientation="inward")], 20.0, 0.1)
    for tag, trace in (("threshold", 1.0e-9), ("lowered", TRACE_MM)):
        W[f"q5_background_{tag}"] = _world(
            ["Q5 background guard"],
            f"a washout into a small node at the trace, trace_mM = {trace:g} "
            f"({'the threshold 1e-6 K_d' if tag == 'threshold' else '1e3 below it'}); the "
            "trace's share of the node's content, c_bg V / n, stays near 1e-5",
            {"cell_0": _cell(c=trace), "ecs_0": _node(1.0, trace)},
            [_pop("r0", "cell_0", "ecs_0", theta0=0.5, k_int=K_INT)], 20.0, 0.1, trace=trace)
    return {
        "kind": "FR-3 site occupancy: the references' registered inputs",
        "registered": REGISTERED,
        "forms": "docs/SITE_OCCUPANCY_DESIGN.md, Appendix A (A.1 to A.5) and §8.3",
        "units": {"amount": "fmol", "volume": "pL", "concentration": "mM (fmol/pL)",
                  "time": "s", "rate": "1/s", "association": "1/(mM s)", "energy": "pJ",
                  "copies": "molecules", "sites": "fmol (S = alpha nu N / N_f)"},
        "constants": {"avogadro_per_mol": 6.02214076e23, "elementary_charge_C": 1.602176634e-19,
                      "boltzmann_J_per_K": 1.380649e-23,
                      "gas_constant_J_per_mol_K": "avogadro_per_mol x boltzmann_J_per_K (exact)",
                      "sites_per_fmol": "avogadro_per_mol x 1e-15 = 602,214,076 (exact)",
                      "RT_pJ_per_fmol": "1e-3 R T"},
        "conventions": [
            "c = n/V with n in fmol, V in pL and c in mM; every node's initial ligand is listed "
            "as a concentration, the trace included, and nothing but the populations' routes "
            "changes the ligand",
            "a population's accessible sites are S = alpha nu N / N_f fmol; R + B = S, with "
            "B0 = initial_occupancy x S",
            "binding: J = m_b (k_on c R - k_off B), c the faced node's; internalisation: "
            "I = m_i k_int B, into the owner cell's ligand row, the site returning free",
            "an outward population faces its patch's outside node; an inward population faces "
            "its owner's cytosol, and internalisation is declared on outward populations only",
            "site_controls hold their multipliers from each time on (right-continuous); every "
            "time is an exact multiple of each dt of the ladder",
            "records are the states at the record times, t = 0 included",
            "the free energies are A.3's: G_node = RT n (ln(n/V) - 1) and G_site = B (dG0 + RT "
            "ln(B/S)) + RT R ln(R/S), dG0 = RT ln(K_d/1 mM), with RT = 1e-3 R T pJ/fmol",
        ],
        "ligand": {"id": "L", "valence": 0, "membrane_permeable": False,
                   "trace_mM": TRACE_MM, "trace_rule": "trace_mM <= 1e-6 K_d of every population"},
        "dt_ladder_s": DT_LADDER,
        "worlds": W,
    }


def write(path=INPUTS) -> Path:
    Path(path).write_text(json.dumps(build(), indent=1) + "\n")
    return Path(path)


def network(world: dict):
    """The R-ode network of a world block (see ``kinetics.Network``)."""
    from . import kinetics
    from .exact import RT_pJ_per_fmol
    vols = {k: v["volume_pL"] for k, v in world["nodes"].items()}
    n0 = {k: float(exact(v["L_mM"]) * exact(v["volume_pL"])) for k, v in world["nodes"].items()}
    trace = exact(world["trace_mM"])
    for k, v in world["nodes"].items():
        if exact(v["L_mM"]) < trace:
            raise ValueError(f"node {k} lies below the declared trace")
    pops = []
    for p in world["populations"]:
        S = kinetics.sites_fmol(p["copies"], p["sites_per_copy"], p["accessible_fraction"])
        kd = exact(p["dissociation_rate_per_s"]) / exact(p["association_rate_per_mM_per_s"])
        if trace > kd / 10 ** 6 * (1 + Fraction(1, 10 ** 12)):
            raise ValueError(f"population {p['id']}: trace above 1e-6 K_d")
        owner = p["owner"]
        faces = owner["faces_node"]
        if owner["orientation"] == "inward" and faces != owner["cell"]:
            raise ValueError("an inward population faces its own cell")
        k_int = 0.0
        recv = None
        if p["internalisation"] is not None:
            if owner["orientation"] != "outward":
                raise ValueError("internalisation is declared on outward populations only")
            k_int = float(p["internalisation"]["rate_per_s"])
            recv = owner["cell"]
        pops.append(kinetics.Population(faces, float(S), float(p["association_rate_per_mM_per_s"]),
                                        float(p["dissociation_rate_per_s"]), k_int, recv,
                                        float(exact(p["initial_occupancy"]) * S)))
    epochs = []
    ids = [p["id"] for p in world["populations"]]
    for e in world["site_controls"]:
        spec = {i: (float(e["binding"].get(pid, 1.0)), float(e["internalisation"].get(pid, 1.0)))
                for i, pid in enumerate(ids)}
        epochs.append((float(e["time_s"]), spec))
    return kinetics.Network(vols, n0, pops, float(RT_pJ_per_fmol(world["temperature_K"])),
                            epochs=epochs)


if __name__ == "__main__":
    print(write())
    sys.exit(0)
