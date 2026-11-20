"""The registered inputs of OL5's fuel references (``designs/``), generated from exact parameters.

Every value is a declared test parameter, unsourced (provenance "unsourced"). The worlds follow the
fuel note at tag ol4-fuel-note-2026-11-20, §3 (d), with the lead's rulings of 20 November 2026 (Q1:
zero drive is mu_F = mu_W with held potentials including their activities; Q2: every arm compared
by total variation, modality reported; Q3: V1 in this registration). One convention pair is probed:
(multinomial, kept).

**Worlds without geometry** (``ool_references.world@1``, exact):
- ``ol4_fd_kernel``: the kernel probe. F and W held (drive mu_F - mu_W = ln 24); B, S, L1, L2 with
  pool and membrane places; every step of (d), L1 and L2 exchanged too. Rows OL4-1, OL4-2.
- ``ol4_fd_heldB``: no fuel; B and S held at mu_B - mu_S = ln 12 (the held-block world, §3.1's
  "activated monomers, held"). Rows OL4-1 to OL4-4.
- ``ol4_fd_d0`` and ``ol4_fd_null``: no fuel; B and S held at mu_B = mu_S (zero affinity), at
  rho = 1/9 ((d0), the note's C4 parameters) and rho = 2/3 (the dividing null, L6). The membrane
  grows in both. Rows OL4-1 to OL4-4, and OL4-8's predictions.
- ``ol4_fd_finite``: F and W finite: the fuel's free energy is stored inside F. Closed in both
  moieties, so its stationary law is exp(-F)/Z. Rows OL4-1, OL4-3, OL4-4, OL4-5.
- ``ol4_fd_heldF``: F held, W finite (the waste accumulates). Rows OL4-3, OL4-4.
- ``ol4_fd_ness`` (driven, beta > 0), ``ol4_fd_ness_beta0``, ``ol4_fd_zero`` (mu_F = mu_W) and
  ``ol4_fd_zero_beta0``: one chemistry, closed in the block (M = 15 blocks), F and W held. Chosen by
  an exact search (the staging folder's ``evidence/search``) so that the driven arm has two modes
  inside the composition range, the beta = 0 arm one central mode, and every arm comparable
  amphiphile counts: e^Delta1 = 1/8, e^Delta2 = 1, k2/k1 = 1/2, beta = 6, drive ln 32, X = 15/4.
  Rows OL4-5 to OL4-7.
- ``ol4_fd_edge`` and ``ol4_fd_edge_beta0``: the strongly downhill regime (e^Delta1 = e^Delta2 =
  1/8, k2/k1 = 1/10, A = ln 2048), registered as a reported counter-example: both arms put their
  modes on the edge where one amphiphile is absent (drift, not catalysis). Rows OL4-6, OL4-7.

**Vesicle worlds** (``ool_references.world2@1``, V1): ``ol4_fv_kernel`` and ``ol4_fv_closed``.

**Refusals**: a factor on the pool-only fuel step (L1), in both formats.
"""

from __future__ import annotations

import copy
import json
import math
from fractions import Fraction as Fr
from pathlib import Path

from ..ol2 import N_A, Channel
from . import chem as C
from . import vesicle as V

DESIGN_DIR = Path(__file__).resolve().parent / "designs"
PROBE_SEED = 2026112002
PROBE_BASES = 24
PROBE_MAX_COUNT = 9
CONVENTIONS = {"free_energy_form": "discrete", "condensed_measure": "multinomial", "membrane_kinetics": "count_on_m",
               "lumen_volume": "declared", "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept"}

# ---------------------------------------------------------------------------- chemistries

KERNEL = C.Chem(em_B_sol=Fr(1, 2), em_B_bil=Fr(1), em_S_sol=Fr(32), em_S_bil=Fr(16), em_L_bil=Fr(8),
                em_L_sol=Fr(1), em_F_sol=Fr(1, 4), em_W_sol=Fr(2), k_f=Fr(1, 2), k_jB=Fr(1), k_jS=Fr(3, 4),
                k_jL=Fr(1, 4), k1=Fr(2), k2=Fr(1, 3), beta=Fr(5, 2), X=Fr(8),
                held={"F": Fr(3, 2), "W": Fr(1, 2)}, L_pool=True)
"""e^Delta1 = 1/8, e^Delta2 = 1/2; drive mu_F - mu_W = ln(em_W c_F / (em_F c_W)) = ln 24."""

HELD_B = C.Chem(em_B_sol=Fr(1, 2), em_B_bil=Fr(1), em_S_sol=Fr(32), em_S_bil=Fr(16), em_L_bil=Fr(8),
                k_f=Fr(1), k_jB=Fr(1), k_jS=Fr(3, 4), k1=Fr(2), k2=Fr(1, 3), beta=Fr(5, 2), X=Fr(8),
                held={"B": Fr(3, 4), "S": Fr(4)}, fuel=False)
"""mu_B - mu_S = ln((c_B/em_B_sol)/(c_S/em_S_sol)) = ln((3/4 * 2)/(4/32)) = ln 12."""


def zero_affinity(rho: Fr, beta: Fr, k2: Fr) -> C.Chem:
    """Held B and S at mu_B = mu_S, every potential zero (e^Delta1 = e^Delta2 = 1, K_B = K_S = 1):
    with fast exchange x_B = c_B/c0 and x_S = c_S/c0, T = 1 - x_B - x_S, rho = T/(2 x_S)."""
    xS = 1 / (2 * rho + 2)            # x_B = x_S and T = 2 rho x_S with x_B + x_S + T = 1
    return C.Chem(em_B_sol=Fr(1), em_B_bil=Fr(1), em_S_sol=Fr(1), em_S_bil=Fr(1), em_L_bil=Fr(1), k_f=Fr(1),
                  k_jB=Fr(10), k_jS=Fr(10), k1=Fr(1), k2=k2, beta=beta, X=Fr(8), held={"B": xS, "S": xS}, fuel=False)


D0 = zero_affinity(Fr(1, 9), Fr(20), Fr(1, 100))      # x_B = x_S = 9/20, T = 1/10: the note's C4
NULL = zero_affinity(Fr(2, 3), Fr(20), Fr(1, 100))    # x_B = x_S = 3/10, T = 2/5: rho = 2/3

FINITE = C.Chem(em_B_sol=Fr(1, 2), em_B_bil=Fr(1), em_S_sol=Fr(32), em_S_bil=Fr(16), em_L_bil=Fr(8),
                em_F_sol=Fr(1, 4), em_W_sol=Fr(2), k_f=Fr(1, 2), k_jB=Fr(1), k_jS=Fr(3, 4), k1=Fr(2), k2=Fr(1, 3),
                beta=Fr(5, 2), X=Fr(4), held={})
HELD_F = C.Chem(em_B_sol=Fr(1, 2), em_B_bil=Fr(1), em_S_sol=Fr(32), em_S_bil=Fr(16), em_L_bil=Fr(8),
                em_F_sol=Fr(1, 4), em_W_sol=Fr(2), k_f=Fr(1, 2), k_jB=Fr(1), k_jS=Fr(3, 4), k1=Fr(2), k2=Fr(1, 3),
                beta=Fr(5, 2), X=Fr(8), held={"F": Fr(3, 2)})


def ness_chem(beta: Fr, thF: Fr) -> C.Chem:
    """The searched chemistry (``evidence/search``): see ``NESS``."""
    p = NESS
    em_B = Fr(1)
    em_L = em_B / p["e1"]
    em_S = em_L / p["e2"]
    return C.Chem(em_B_sol=em_B, em_B_bil=em_B, em_S_sol=em_S, em_S_bil=em_S, em_L_bil=em_L, k_f=p["kf"],
                  k_jB=p["kj"], k_jS=p["kj"], k1=Fr(1), k2=p["k2"], beta=beta, X=p["X"],
                  held={"F": thF, "W": Fr(1)})


NESS = dict(M=15, e1=Fr(1, 8), e2=Fr(1), k2=Fr(1, 2), kf=Fr(10), kj=Fr(10), X=Fr(15, 4), beta=Fr(6), thF=Fr(32))
"""The search's pick (``evidence/search/candidates3_M15.jsonl``): at M = 15 the driven arm has two
interior modes, (L1, L2) = (1, 10) and (10, 1); beta = 0 one mode at (3, 4); zero drive one at (4, 4);
mean amphiphile counts 10.6, 7.2 and 8.7. Its large-size limit is bistable at its own fractions
(the mean-field f_- = 0.36, ``evidence/search/meanfield.py``)."""

EDGE = dict(M=12, e1=Fr(1, 8), e2=Fr(1, 8), k2=Fr(1, 10), kf=Fr(10), kj=Fr(10), X=Fr(4), beta=Fr(20), thF=Fr(2048))


def edge_chem(beta: Fr) -> C.Chem:
    p = EDGE
    em_L = 1 / p["e1"]
    em_S = em_L / p["e2"]
    return C.Chem(em_B_sol=Fr(1), em_B_bil=Fr(1), em_S_sol=em_S, em_S_bil=em_S, em_L_bil=em_L, k_f=p["kf"],
                  k_jB=p["kj"], k_jS=p["kj"], k1=Fr(1), k2=p["k2"], beta=beta, X=p["X"],
                  held={"F": p["thF"], "W": Fr(1)})


def _closed_initial(M: int) -> dict:
    """A state with M blocks: half the amphiphiles' worth each of L1 and L2, the rest B in the pool."""
    a = M // 3
    return {"L1@membrane": a, "L2@membrane": a, "B@membrane": 1, "B@pool": M - 2 * a - 1}


# ---------------------------------------------------------------------------- documents

def world_documents() -> dict:
    d = {}
    d["ol4_fd_kernel"] = C.world_document(
        "ol4_fd_kernel", "Fuel kernel probe (rows OL4-1, OL4-2): option (d) without geometry; F and W held (drive "
        "ln 24); B, S, L1 and L2 with pool and membrane places; the fuel step, five joins, the catalysed core steps "
        "and the decays.", KERNEL,
        {"B@membrane": 3, "S@membrane": 2, "L1@membrane": 4, "L2@membrane": 3, "B@pool": 4, "S@pool": 5,
         "L1@pool": 1, "L2@pool": 1})
    d["ol4_fd_heldB"] = C.world_document(
        "ol4_fd_heldB", "Held-block world (rows OL4-1 to OL4-4): no fuel; B and S held in the pool at mu_B - mu_S = "
        "ln 12; the membrane is open and grows or shrinks.", HELD_B,
        {"B@membrane": 3, "S@membrane": 2, "L1@membrane": 4, "L2@membrane": 3})
    d["ol4_fd_d0"] = C.world_document(
        "ol4_fd_d0", "(d0), the no-fuel variant (rows OL4-1 to OL4-4, OL4-8): B and S held at mu_B = mu_S, the "
        "note's C4 parameters (x_B = x_S = 9/20 with fast exchange, rho = 1/9, beta = 20, k2/k1 = 1/100).", D0,
        {"B@membrane": 9, "S@membrane": 9, "L1@membrane": 1, "L2@membrane": 1})
    d["ol4_fd_null"] = C.world_document(
        "ol4_fd_null", "The dividing null (L6; rows OL4-1 to OL4-4, OL4-8): B and S held at mu_B = mu_S with "
        "rho = 2/3 (x_B = x_S = 3/10 with fast exchange), beta = 20, k2/k1 = 1/100.", NULL,
        {"B@membrane": 3, "S@membrane": 3, "L1@membrane": 2, "L2@membrane": 2})
    d["ol4_fd_finite"] = C.world_document(
        "ol4_fd_finite", "Finite fuel (rows OL4-1, OL4-3 to OL4-5): F and W finite, so the fuel's free energy is "
        "stored inside F; closed in both moieties (6 blocks, 6 fuel).", FINITE,
        {"F@pool": 6, "L1@membrane": 2, "L2@membrane": 2, "S@pool": 2})
    d["ol4_fd_heldF"] = C.world_document(
        "ol4_fd_heldF", "Held fuel, finite waste (rows OL4-3, OL4-4): the waste accumulates in the pool.", HELD_F,
        {"L1@membrane": 3, "L2@membrane": 3, "S@pool": 4, "B@pool": 2})
    M = NESS["M"]
    for wid, beta, thF, what in (("ol4_fd_ness", NESS["beta"], NESS["thF"], "driven, beta > 0"),
                                 ("ol4_fd_ness_beta0", Fr(0), NESS["thF"], "driven, beta = 0"),
                                 ("ol4_fd_zero", NESS["beta"], Fr(1), "zero drive (mu_F = mu_W), beta > 0"),
                                 ("ol4_fd_zero_beta0", Fr(0), Fr(1), "zero drive, beta = 0")):
        d[wid] = C.world_document(
            wid, f"Closed in the block, M = {M} ({what}); rows OL4-5 to OL4-7. Chosen by the registered search.",
            ness_chem(beta, thF), _closed_initial(M), extra={"block_total": M})
    Me = EDGE["M"]
    for wid, beta in (("ol4_fd_edge", EDGE["beta"]), ("ol4_fd_edge_beta0", Fr(0))):
        d[wid] = C.world_document(
            wid, f"The edge regime, a reported counter-example (M = {Me}, beta = {beta}): modes on the edge where one "
            "amphiphile is absent, by drift.", edge_chem(beta), _closed_initial(Me), extra={"block_total": Me})
    return d


def refusal_documents() -> dict:
    base = world_documents()["ol4_fd_kernel"]
    doc = copy.deepcopy(base)
    doc["id"] = "refuse_factor_on_pool_step"
    doc["description"] = ("Must be refused (fuel note §6, L1): the fuel step f1, whose places all lie in the pool, "
                          "carries a transition-state factor entry with the membrane catalyst L1.")
    f1 = next(s for s in doc["steps"] if s["id"] == "f1")
    f1["transition_state_factor"] = [{"catalyst": "L1@membrane", "beta": "3", "ddG_kT": math.log1p(3.0)}]
    return {"refuse_factor_on_pool_step": doc}


def canonical_bytes(doc: dict) -> bytes:
    return json.dumps(doc, indent=1).encode()


def states_bytes(doc: dict) -> bytes:
    head = json.dumps({k: v for k, v in doc.items() if k != "states"}, indent=1)
    body = ",\n".join("  " + json.dumps(s, separators=(",", ":")) for s in doc["states"])
    return (head[:-2] + ',\n "states": [\n' + body + "\n ]\n}").encode()


def registered_world(wid: str):
    from .law import load_fuel_world

    return load_fuel_world(DESIGN_DIR / f"{wid}.world.json")


# ---------------------------------------------------------------------------- V1: vesicle worlds

VQ = 3e-17                    # the area quantum of the kernel world (m^2), as OL2's
VC0, VCEXT, VT = 1e-3, 0.3, 298.15
V_SEED = 2026112003
V_BASES = 12
V_CLOSED_TOTAL = 8


def v_pool_L(X: float) -> float:
    return X / (N_A * VC0)


def lumen_for(q: float):
    def f(W: int, v: float) -> int:
        """Impermeant molecules giving reduced volume v at W quanta."""
        vs = (q * W / 2) ** 1.5 / (6 * math.sqrt(math.pi)) * 1e3
        return int(math.floor(v * vs * N_A * VCEXT))
    return f


def v_worlds() -> dict:
    mo = {"B": {"block": 1}, "S": {"block": 1}, "L1": {"block": 1}, "L2": {"block": 1}, "F": {"fuel": 1},
          "W": {"fuel": 1}, "X": {"x": 1}}
    mem = [("B", 1, -1.0), ("S", 1, -2.5), ("L1", 1, -2.0), ("L2", 1, -2.0)]
    steps = [Channel("pool", "f1", 0.5, reactants=(("F", 1), ("S", 1)), products=(("B", 1), ("W", 1))),
             Channel("join", "jB", 1e-10, species="B"), Channel("join", "jS", 8e-11, species="S"),
             Channel("join", "jL1", 2e-11, species="L1"), Channel("join", "jL2", 2e-11, species="L2"),
             Channel("membrane", "a1", 2.0, reactants=(("B", 1), ("L1", 1)), products=(("L1", 2),)),
             Channel("membrane", "a2", 2.0, reactants=(("B", 1), ("L2", 1)), products=(("L2", 2),)),
             Channel("membrane", "d1", 0.3, reactants=(("L1", 1),), products=(("S", 1),)),
             Channel("membrane", "d2", 0.3, reactants=(("L2", 1),), products=(("S", 1),))]
    cats = {"a1": [("L1", 2.5)], "a2": [("L2", 2.5)]}
    lf = lumen_for(VQ)
    n0 = (200, 100, 600, 500)
    kern = V.FuelWorld2(
        name="ol4_fv_kernel", q_m2=VQ, c0_M=VC0, c_ext_M=VCEXT, T=VT, V_pool_L=v_pool_L(50.0), membrane=mem,
        lumen=[("X", 0.0)], pool_finite=[("B", 0.5), ("S", -1.5), ("L1", 1.0), ("L2", 1.0)],
        pool_held=[("F", 1.0, 1.5), ("W", -1.5, 0.5)], steps=steps, encounter="insertion_area", sigma_max=1e-2,
        kappa=10.0, kappa_bar=-10.0, W_floor=1000, moieties=mo, catalysts=cats,
        founder=dict(n=n0, l=(lf(sum(n0), 0.9),), p=(30, 30, 2, 2)),
        description="Fuel kernel probe in a vesicle (V1): option (d)'s chemistry with bilayer geometry, an osmotic "
                    "lumen with one impermeant solute, insertion_area joins, held fuel and waste (drive "
                    "mu_F - mu_W = 2.5 + ln 3), the catalysed core steps, the floor and lysis.")
    # the closed vesicle: the kink between tense and floppy at W = 5 (two impermeant molecules)
    l_closed = 2
    V_osm = l_closed / (N_A * VCEXT) * 1e-3          # m^3
    A_kink = (6 * math.sqrt(math.pi) * V_osm) ** (2 / 3)
    q_closed = 2 * A_kink / 5
    closed = V.FuelWorld2(
        name="ol4_fv_closed", q_m2=q_closed, c0_M=VC0, c_ext_M=VCEXT, T=VT, V_pool_L=v_pool_L(4.0), membrane=mem,
        lumen=[("X", 0.0)], pool_finite=[("B", 0.5), ("S", -1.5), ("L1", 1.0), ("L2", 1.0), ("X", 0.0)],
        pool_held=[("F", 1.0, 1.0), ("W", 1.0, 1.0)],
        steps=[Channel("pool", "f1", 0.5, reactants=(("F", 1), ("S", 1)), products=(("B", 1), ("W", 1))),
               Channel("join", "jB", 1e-10, species="B"), Channel("join", "jS", 8e-11, species="S"),
               Channel("join", "jL1", 2e-11, species="L1"), Channel("join", "jL2", 2e-11, species="L2")] + steps[5:],
        encounter="insertion_area", sigma_max=1e3, kappa=10.0, kappa_bar=-10.0, W_floor=2, moieties=mo,
        catalysts={"a1": [("L1", 8.0)], "a2": [("L2", 8.0)]},
        founder=dict(n=(1, 1, 2, 2), l=(l_closed,), p=(1, 1, 0, 0, 0)),
        description="Closed vesicle at zero drive (V1, row OL4-5): mu_F = mu_W; 8 block molecules in membrane and "
                    "pool; two impermeant lumen molecules put the kink between tense and floppy at W = 5; it "
                    "cannot lyse (sigma_max 1e3 N/m).")
    return {"ol4_fv_kernel": kern, "ol4_fv_closed": closed}


def v_documents() -> dict:
    return {wid: V.world_document(w, C.REGISTERED_ON, C.SOURCE, CONVENTIONS | {"lumen_volume": "osmotic"})
            for wid, w in v_worlds().items()}
