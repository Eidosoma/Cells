"""The registered OL2 and OL3 inputs: worlds, probe states, partition parents and runs
(``designs/ol2_*.json`` and ``designs/ol3_*.json``), registered 18 November 2026 before any
engine output.

Every quantity is a declared test parameter, unsourced, chosen for the forms' sake: the area
quantum q = 3e-17 m^2 makes a vesicle of 400-2000 quanta 20-50 nm in radius, and the constants
give rates of order 0.01-10 per second. No value here is a physical claim.

Conventions in every world: ``free_energy_form: discrete``, ``condensed_measure: multinomial``,
``membrane_kinetics: count_on_m`` (membrane-only steps), ``empty_catalyst_phase: uncatalysed``,
``last_molecule: kept`` (§0.2c rule 5), ``lumen_volume: osmotic``, and ``exchange_encounter`` as
named (§0.2c rule 1).

Worlds:
- ``ol2_wa`` and ``ol2_wa_diffusion`` (kernel probes, one per encounter token): membrane L1 (k = 1)
  and L2 (k = 2) with the area-preserving step 2 L1 -> L2; lumen S (impermeant) and G (permeant);
  pool places L1 and S (finite), L2 and G (held). Joins of L1 and L2, G's entry, sigma_max and the
  floor at W = 1000.
- ``ol2_closed`` (stationary, one vesicle) and ``ol2_two`` (stationary, two vesicles sharing a
  finite pool, one swollen and one relaxed: the tension-driven competition, §4.2): neither can lyse.
- ``ol2_shared`` (run, population, two-level map): ``ol2_two`` with a pool isomerisation A <-> B,
  four slots, no schedule.
- ``ol2_lysis`` (run, single lineage): a vesicle shrinking into an empty finite pool until it lyses.
- ``ol3_population`` (run, population): Poisson shear (k = 2) and serial transfers at declared
  times, the first with every assembly kept.
- ``ol3_shear_probe`` (run, population, declared shear times): parents that split at k = 3 with
  N mod 3 != 0, parents whose daughters lyse at birth, a fission refused at the floor and an
  assembly not admitted.
- ``ol3_lineage`` (run, single lineage, declared shear times): the clock rule on OL1's age counter
  and the unfollowed daughters' sink.
- ``ol3_slots_full`` (run): a shear with no free slot stops the run ``slots_full``.
- ``ol3_parents``: partition parents for C3x and the lumen split (N mod k != 0 at k = 2 and 3, equal
  and unequal areas, and one N mod k = 0 case).
"""

from __future__ import annotations

import itertools
import json
import math
from pathlib import Path

import numpy as np

from .ol2 import N_A, Channel, Law2, Vesicle2, World2
from .population import RunSpec, Schedule

REGISTERED_ON = "2026-11-18"
AUTHORITY = ("docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2b, §0.2c (rule 4 as corrected 18 November), §0.2d "
             "(7fb8816f; item 6 confirmed and extended, item 9 added, at 95c98b5a), §2.5, §3, §4, §5.2")
DESIGN_DIR = Path(__file__).resolve().parent / "designs"
Q = 3e-17
C0 = 1e-3
C_EXT = 0.3
T = 298.15
KAPPA, KAPPA_BAR = 10.0, -10.0          # C_close = 8 pi kappa + 4 pi kappa-bar = 40 pi k_BT
MOIETIES = {"L1": {"a": 1}, "L2": {"a": 2}, "S": {"s": 1}, "G": {"g": 1}, "A": {"b": 1}, "B": {"b": 1}}
CONVENTIONS = {"free_energy_form": "discrete", "condensed_measure": "multinomial", "membrane_kinetics": "count_on_m",
               "empty_catalyst_phase": "uncatalysed", "last_molecule": "kept", "lumen_volume": "osmotic"}


def v_pool(X: float) -> float:
    return X / (N_A * C0)


def v_sph_L(W: int) -> float:
    return (Q * W / 2) ** 1.5 / (6 * math.sqrt(math.pi)) * 1e3


def lumen_for(W: int, v: float, others: int = 0) -> int:
    """Impermeant molecules giving reduced volume v at W quanta (with ``others`` lumen molecules)."""
    return int(math.floor(v * v_sph_L(W) * N_A * C_EXT)) - others


def g_equilibrium(V_L: float, c_mM: float) -> int:
    return int(round(c_mM * 1e-3 * N_A * V_L))


def _world(name, **kw) -> World2:
    base = dict(q_m2=Q, c0_M=C0, c_ext_M=C_EXT, T=T, kappa=KAPPA, kappa_bar=KAPPA_BAR, moieties=MOIETIES)
    base.update(kw)
    return World2(name=name, **base)


L1_L2 = [("L1", 1, -2.0), ("L2", 2, -3.0)]


def worlds() -> dict:
    out = {}
    founder_wa = (1800, 100)
    W_wa = founder_wa[0] + 2 * founder_wa[1]
    G_wa = 2000
    for name, token, kL1, kL2 in (("ol2_wa", "insertion_area", 1e-10, 5e-11),
                                  ("ol2_wa_diffusion", "diffusion_radius", 4e-16, 2e-16)):
        out[name] = _world(
            name, V_pool_L=v_pool(50.0), membrane=L1_L2, lumen=[("S", 0.0), ("G", 0.0)],
            pool_finite=[("L1", 0.0), ("S", 0.0)], pool_held=[("L2", 0.0, 1.0), ("G", 0.0, 5.0)],
            steps=[Channel("join", "join_L1", kL1, species="L1"), Channel("join", "join_L2", kL2, species="L2"),
                   Channel("entry", "entry_G", 1e-12, species="G"),
                   Channel("membrane", "r1", 0.5, reactants=(("L1", 2),), products=(("L2", 1),))],
            encounter=token, sigma_max=1e-2, W_floor=1000,
            founder=dict(n=founder_wa, l=(lumen_for(W_wa, 0.9, G_wa), G_wa), p=(30, 0)),
            description=f"OL2 kernel probe ({token}): joins from a finite (L1) and a held (L2) place, a permeant (G) "
                        "entering from a held place, an area-preserving membrane step, the floor and lysis.")
    one = dict(membrane=[("L1", 1, -1.0)], lumen=[("S", 0.0)], pool_finite=[("L1", 0.0), ("S", 0.0)], pool_held=[],
               steps=[Channel("join", "join_L1", 1e-10, species="L1")], encounter="insertion_area", sigma_max=1e3,
               W_floor=1500)
    out["ol2_closed"] = _world("ol2_closed", V_pool_L=v_pool(20.0), founder=dict(n=(1520,), l=(lumen_for(1553, 1.0),),
                                                                                 p=(40, 0)),
                               description="OL2 stationary law, one vesicle exchanging with a finite pool across its "
                                           "kink (tense below W = 1553); it cannot lyse.", **one)
    two_founders = [dict(n=(1540,), l=(lumen_for(1560, 1.0),)), dict(n=(1540,), l=(lumen_for(1500, 0.6),))]
    out["ol2_two"] = _world("ol2_two", V_pool_L=v_pool(20.0), founder=dict(vesicles=two_founders, p=(30, 0)),
                            description="OL2 stationary law of two vesicles sharing a finite pool, one swollen and "
                                        "one relaxed (the competition of §4.2); neither can lyse.", **one)
    shared = dict(one)
    shared["pool_finite"] = [("L1", 0.0), ("S", 0.0), ("A", 0.0), ("B", -0.5)]
    shared["steps"] = one["steps"] + [Channel("pool", "iso", 0.3, reactants=(("A", 1),), products=(("B", 1),))]
    out["ol2_shared"] = _world("ol2_shared", V_pool_L=v_pool(20.0), founder=dict(vesicles=two_founders, p=(30, 0, 3, 2)),
                               description="OL2 shared pool run: ol2_two's vesicles in four slots, with a pool "
                                           "isomerisation so that the pool's group fires.", **shared)
    W_lys = 1600
    V_lys = v_sph_L(W_lys) * 0.985
    G_lys = g_equilibrium(V_lys, 5.0)
    out["ol2_lysis"] = _world(
        "ol2_lysis", V_pool_L=v_pool(5000.0), membrane=L1_L2, lumen=[("S", 0.0), ("G", 0.0)],
        pool_finite=[("L1", 0.0), ("S", 0.0)], pool_held=[("L2", 0.0, 0.02), ("G", 0.0, 5.0)],
        steps=[Channel("join", "join_L1", 1e-9, species="L1"), Channel("join", "join_L2", 1e-9, species="L2"),
               Channel("entry", "entry_G", 1e-11, species="G")],
        encounter="insertion_area", sigma_max=1.4e-4, W_floor=1000,
        founder=dict(n=(1500, 50), l=(lumen_for(W_lys, 0.985, G_lys), G_lys), p=(0, 0)),
        description="OL2 lysis run: a vesicle near its kink loses amphiphiles to an empty finite pool (and L2 to a "
                    "held place below its CAC) until its tension passes sigma_max (sigma_max q/2 is about 0.5 k_BT).")
    pop = dict(membrane=[("L1", 1, -2.0)], lumen=[("S", 0.0)], pool_finite=[("L1", 0.0), ("S", 0.0)], pool_held=[],
               steps=[Channel("join", "join_L1", 1e-9, species="L1")], encounter="insertion_area", sigma_max=1e-2,
               W_floor=200)
    out["ol3_population"] = _world("ol3_population", V_pool_L=v_pool(2000.0),
                                   founder=dict(vesicles=[dict(n=(400,), l=(lumen_for(400, 1.0),))] * 4, p=(4000, 0)),
                                   description="OL3 population run: four vesicles grow from a supersaturated finite "
                                               "pool, split under Poisson shear (k = 2) and pass serial transfers.",
                                   **pop)
    probe_founders = []
    for _ in range(8):           # daughters at their kink on average: some are born beyond sigma_max
        probe_founders.append(dict(n=(600, 100), l=(lumen_for(800, 0.7066),), role="birth_lysis"))
    probe_founders.append(dict(n=(480, 0), l=(lumen_for(480, 0.6),), role="refused_at_floor"))
    probe_founders.append(dict(n=(800, 0), l=(lumen_for(800, 0.9),), role="not_admitted"))
    probe_founders.append(dict(n=(902, 0), l=(lumen_for(902, 0.5),), role="k3_N902"))
    probe_founders.append(dict(n=(800, 51), l=(lumen_for(902, 0.5),), role="k3_N851_unequal"))
    probe_founders.append(dict(n=(901, 0), l=(lumen_for(901, 0.5),), role="k3_N901"))
    cac2 = math.exp(-3.0)
    out["ol3_shear_probe"] = _world(
        "ol3_shear_probe", V_pool_L=v_pool(2000.0), membrane=L1_L2, lumen=[("S", 0.0)],
        pool_finite=[("L1", 0.0), ("S", 0.0)], pool_held=[("L2", 0.0, cac2)],
        steps=[Channel("join", "join_L1", 1e-11, species="L1"), Channel("join", "join_L2", 1e-11, species="L2")],
        encounter="insertion_area", sigma_max=2e-6, W_floor=250,
        founder=dict(vesicles=probe_founders, p=(270, 0)),
        description="OL3 shear probe: a k = 3 shear then a k = 2 shear at declared times; births beyond sigma_max, a "
                    "fission refused at the floor, an assembly not admitted, and C3x at N mod 3 != 0.")
    lin = dict(pop)
    lin["pool_finite"] = [("S", 0.0)]
    lin["pool_held"] = [("L1", 0.0, 1.0)]
    lin["steps"] = [Channel("join", "join_L1", 1e-8, species="L1")]
    out["ol3_lineage"] = _world("ol3_lineage", V_pool_L=v_pool(2000.0),
                                founder=dict(n=(400,), l=(lumen_for(400, 1.0),), p=(0,)),
                                description="OL3 single lineage: growth from a held pool and fission at declared shear "
                                            "times; the clock rule on the followed assembly's own stream.", **lin)
    out["ol3_slots_full"] = _world("ol3_slots_full", V_pool_L=v_pool(2000.0),
                                   founder=dict(vesicles=[dict(n=(400,), l=(lumen_for(400, 0.6),))] * 2, p=(270, 0)),
                                   description="OL3: two admissible assemblies in two slots at a k = 2 shear.", **pop)
    return out


def runs(ws: dict | None = None) -> dict:
    """The registered runs. Carrier keys are the stand-in's; an engine's own keys are recorded."""
    ws = ws or worlds()

    def founders(w, key0):
        f = w.founder
        ves = f.get("vesicles") or [dict(n=f["n"], l=f["l"])]
        return [(Vesicle2(tuple(v["n"]), tuple(v["l"])), key0 + j) for j, v in enumerate(ves)]

    def spec(name, world, mode, slots, t_end, schedules=(), max_events=200000, seed=0):
        w = ws[world]
        return RunSpec(world=w, mode=mode, slots=slots, t_end=t_end, max_events=max_events, schedules=tuple(schedules),
                       world_key=1000 + seed, founders=founders(w, 100 * (seed + 1)), pool=tuple(w.founder["p"]),
                       seed=seed, name=name)

    return {
        "ol2_shared_run": spec("ol2_shared_run", "ol2_shared", "population", 4, 600.0, seed=11),
        "ol2_lysis_run": spec("ol2_lysis_run", "ol2_lysis", "single_lineage", 1, 400.0, seed=12),
        "ol3_population_run": spec("ol3_population_run", "ol3_population", "population", 32, 60.0,
                                   [Schedule(0, "shear", rate=0.2, k=2),
                                    Schedule(1, "transfer", times=(2.0, 30.0, 45.0), K_keep=4, fresh_pool=(4000, 0))],
                                   seed=13),
        "ol3_shear_probe_run": spec("ol3_shear_probe_run", "ol3_shear_probe", "population", 40, 0.03,
                                    [Schedule(0, "shear", times=(0.01,), k=3), Schedule(1, "shear", times=(0.02,), k=2)],
                                    seed=14),
        "ol3_lineage_run": spec("ol3_lineage_run", "ol3_lineage", "single_lineage", 1, 26.0,
                                [Schedule(0, "shear", times=(5.0, 10.0, 15.0, 20.0, 25.0), k=2)], seed=15),
        "ol3_slots_full_run": spec("ol3_slots_full_run", "ol3_slots_full", "population", 2, 0.03,
                                   [Schedule(0, "shear", times=(0.01,), k=2)], seed=16),
    }


# ------------------------------------------------------------------ probe states

def square_corners(law: Law2, s) -> set:
    """s, its single moves by every step (both directions) and every square's far corner."""
    v, p = Vesicle2(tuple(s[0]), tuple(s[1])), tuple(s[2])
    chs = law.w.vesicle_channels()
    out = {(v.n, v.l, p)}
    for a, cha in enumerate(chs):
        for sign in (1, -1):
            e = law.after(v, p, cha, sign)
            if e is not None:
                out.add((e[0].n, e[0].l, e[1]))
        e1 = law.after(v, p, cha, 1)
        if e1 is None:
            continue
        for chb in chs[a + 1:]:
            top = law.after(*e1, chb, 1)
            e2 = law.after(v, p, chb, 1)
            if top is not None and e2 is not None:
                out.update({(top[0].n, top[0].l, top[1]), (e2[0].n, e2[0].l, e2[1])})
    return out


def kernel_states(w: World2, seed: int = 2026111802, n_base: int = 40) -> list:
    """Random bases (reduced volume 0.3-1.5 of the sphere: floppy to tense below sigma_max) with
    their squares; the floor's boundary; the first states beyond sigma_max and their neighbours;
    an empty lumen."""
    rng = np.random.default_rng(seed)
    law = Law2(w)
    states = set()
    for _ in range(n_base):
        n = (int(rng.integers(1100, 2000)), int(rng.integers(0, 300)))
        W = n[0] + 2 * n[1]
        l = (lumen_for(W, float(rng.uniform(0.3, 1.5))), int(rng.integers(0, 3000)))
        p = (int(rng.integers(2, 60)), int(rng.integers(0, 5)))
        states.update(square_corners(law, (n, l, p)))
    for W in range(w.W_floor - 2, w.W_floor + 3):
        states.update(square_corners(law, ((W, 0), (lumen_for(W, 0.5), 10), (5, 0))))
    states.add(((1500, 0), (0, 0), (5, 0)))
    states.add(((1500, 0), (0, 1), (5, 0)))
    S0 = lumen_for(2000, 1.0)
    for S in range(S0, 3 * S0, 200):
        if law.tension(Vesicle2((2000, 0), (S, 0))) > w.sigma_max:
            for s in (((2000, 0), (S, 0), (5, 0)), ((2000, 0), (S - 200, 0), (5, 0)),
                      ((1999, 0), (S - 200, 0), (6, 0))):
                states.update(square_corners(law, s))
            break
    out = sorted(states)
    for n, l, p in out:          # no registered state's tension within 1e-6 of sigma_max
        t = law.tension(Vesicle2(n, l))
        assert abs(t - w.sigma_max) > 1e-6 * w.sigma_max, (n, l, p)
    return out


def closed_states(w: World2) -> list:
    """Every state of ``ol2_closed``: (vesicle, pool)."""
    total = w.founder["n"][0] + w.founder["p"][0]
    l = tuple(w.founder["l"])
    return [(Vesicle2((n,), l), (total - n, 0)) for n in range(w.W_floor, total + 1)]


def two_states(w: World2) -> list:
    """Every state of ``ol2_two``: (vesicle 0, vesicle 1, pool)."""
    v0, v1 = w.founder["vesicles"]
    total = v0["n"][0] + v1["n"][0] + w.founder["p"][0]
    out = []
    for a, b in itertools.product(range(w.W_floor, total + 1), repeat=2):
        if a + b <= total:
            out.append((Vesicle2((a,), tuple(v0["l"])), Vesicle2((b,), tuple(v1["l"])), (total - a - b, 0)))
    return out


def one_vesicle_states(states, slots: int) -> list:
    """The one-vesicle probe states (n, l, p) a closed world's generator needs."""
    out = set()
    for s in states:
        for j in range(slots):
            out.add((s[j].n, s[j].l, tuple(s[slots])))
    return sorted(out)


DIVISION_ON = "2026-11-19"
DIVISION = {
    # amendment 7: the division inputs the engine's division block declares, as the references assume
    "ol3_lineage": {"continuation": "first", "critical_stress_Pa": None},
    "ol3_population": {"critical_stress_Pa": None},
    "ol3_shear_probe": {"critical_stress_Pa": None},
    "ol3_slots_full": {"critical_stress_Pa": None},
}


def division_document() -> dict:
    return {"format": "ool_references.division_inputs@1", "registered": DIVISION_ON,
            "amends": f"the OL2/OL3 inputs registered {REGISTERED_ON}",
            "keys": {"continuation": "first: the lineage follows daughter 0 (single-lineage worlds only)",
                     "critical_stress_Pa": "null: no critical stress is declared"},
            "worlds": DIVISION}


OL3_PARENTS = [
    dict(id="eq_N5_k3", counts=(2, 1, 2), k_area=(1, 1, 1), lumen=(30, 6), k=3),
    dict(id="eq_N8_k3", counts=(4, 4), k_area=(1, 1), lumen=(40,), k=3),
    dict(id="eq_N7_k2", counts=(4, 3), k_area=(1, 1), lumen=(25, 5), k=2),
    dict(id="eq_N6_k3", counts=(3, 3), k_area=(1, 1), lumen=(12,), k=3),
    dict(id="uneq_N7_k3", counts=(3, 2, 2), k_area=(1, 2, 3), lumen=(20,), k=3),
    dict(id="uneq_N5_k2", counts=(3, 2), k_area=(1, 2), lumen=(12, 3), k=2),
]
PARTITION_ATTEMPTS = 4000


# ------------------------------------------------------------------ documents

def world_document(w: World2) -> dict:
    def step_doc(c: Channel) -> dict:
        d = {"id": c.id, "kind": c.kind}
        if c.kind == "join":
            d.update(species=c.species, direction="pool_to_membrane", encounter=w.encounter,
                     constant={"insertion_area": "k_ins_m_per_s", "diffusion_radius": "D_m2_per_s"}[w.encounter],
                     value=c.constant)
        elif c.kind == "entry":
            d.update(species=c.species, direction="pool_to_lumen", encounter="permeation_area", locus="membrane",
                     constant="P_m_per_s", value=c.constant)
        else:
            phase = "membrane" if c.kind == "membrane" else "pool"
            d.update(locus=phase, law="cells.stochastic_mass_action@1",
                     **({"membrane_kinetics": "count_on_m"} if phase == "membrane" else {}),
                     reactants=[{"phase": phase, "species": s, "count": x} for s, x in c.reactants],
                     products=[{"phase": phase, "species": s, "count": x} for s, x in c.products],
                     forward_rate_constant_per_s=c.constant)
        return d

    species = sorted({s for s, _, _ in w.membrane} | {s for s, _ in w.lumen} | {s for s, _ in w.pool_finite}
                     | {s for s, _, _ in w.pool_held})
    mu = {}
    for s, _, m in w.membrane:
        mu.setdefault(s, {})["bilayer"] = m
    for s, m in w.lumen + w.pool_finite:
        mu.setdefault(s, {})["solution"] = m
    for s, m, _ in w.pool_held:
        mu.setdefault(s, {})["solution"] = m
    founder = {}
    for k, v in w.founder.items():
        founder[k] = [dict((kk, list(vv) if isinstance(vv, tuple) else vv) for kk, vv in x.items()) for x in v] \
            if k == "vesicles" else list(v)
    return {"format": "ool_references.world2@1", "id": w.name, "registered": REGISTERED_ON, "authority": AUTHORITY,
            "description": w.description,
            "units": {"q": "m^2", "concentration": "mol/L (held places: mM)", "volume": "L", "k_ins": "m/s",
                      "D": "m^2/s", "P": "m/s", "sigma_max": "N/m", "energy": "k_BT", "time": "s"},
            "conventions": dict(CONVENTIONS, exchange_encounter=w.encounter),
            "geometry": {"interface": "cells.assembly_geometry@1", "model": "cells.bilayer_geometry@1",
                         "area_quantum_m2": w.q_m2, "vesicle_floor_quanta": w.W_floor,
                         "sigma_max_N_per_m": w.sigma_max, "sigma_max_source": "a declared test parameter, unsourced",
                         "kappa_kT": w.kappa, "kappa_bar_kT": w.kappa_bar,
                         "closure_cost_kT": "8 pi kappa + 4 pi kappa_bar"},
            "temperature_K": w.T, "standard_concentration_M": w.c0_M, "outside_osmolarity_M": w.c_ext_M,
            "pool_volume_L": w.V_pool_L,
            "species": [{"id": s, "moieties": w.moieties[s], "standard_mu_kT": mu[s]} for s in species],
            "membrane": [{"species": s, "area_quanta": k} for s, k, _ in w.membrane],
            "lumen": [{"species": s} for s, _ in w.lumen],
            "pool": {"finite": [s for s, _ in w.pool_finite], "held_mM": {s: c for s, _, c in w.pool_held}},
            "steps": [step_doc(c) for c in w.steps], "founder": founder}


def run_document(r: RunSpec) -> dict:
    return {"format": "ool_references.run2@1", "id": r.name, "world": r.world.name, "registered": REGISTERED_ON,
            "mode": r.mode, "slots": r.slots, "t_end_s": r.t_end, "max_events": r.max_events,
            "schedules": [s.document() for s in r.schedules],
            "streams": {"world_selection": "domain 5, three uniforms per draw (population)",
                        "lineage_events": "domain 1, OL1's two per draw, the age counter (single lineage)",
                        "fission": "domain 2, the parent's key, one block of N + k + N_L per attempt",
                        "schedules": "domain 6, the declared index as the key, one draw per gap or per living assembly"}}


def documents() -> dict:
    ws = worlds()
    docs = {f"{name}.world2.json": world_document(w) for name, w in ws.items()}
    for name in ("ol2_wa", "ol2_wa_diffusion"):
        st = kernel_states(ws[name])
        docs[f"{name}_probe_states.json"] = {
            "format": "ool_references.probe_states2@1", "world": name, "registered": REGISTERED_ON, "count": len(st),
            "state": "[membrane counts in membrane order, lumen counts in lumen order, finite pool counts]",
            "states": [[list(a), list(b), list(c)] for a, b, c in st]}
    for name, states, slots in (("ol2_closed", closed_states(ws["ol2_closed"]), 1),
                                ("ol2_two", two_states(ws["ol2_two"]), 2)):
        one = one_vesicle_states(states, slots)
        docs[f"{name}_states.json"] = {
            "format": "ool_references.probe_states2@1", "world": name, "registered": REGISTERED_ON,
            "closed_world_states": len(states), "count": len(one),
            "state": "one-vesicle probe states [membrane, lumen, finite pool]; the closed world's states are every "
                     "combination of its vesicles' counts above the floor with the conserved total",
            "states": [[list(a), list(b), list(c)] for a, b, c in one]}
    docs["ol3_division.json"] = division_document()
    docs["ol3_parents.json"] = {"format": "ool_references.ol3_parents@1", "registered": REGISTERED_ON,
                                "authority": "§0.2c rules 9 and 10", "attempts_per_parent": PARTITION_ATTEMPTS,
                                "parents": OL3_PARENTS}
    for name, r in runs(ws).items():
        docs[f"{name}.json"] = run_document(r)
    return docs


def canonical(doc) -> bytes:
    """Indented JSON; a probe-state document keeps one state per line."""
    if "states" not in doc:
        return (json.dumps(doc, indent=1) + "\n").encode()
    head = json.dumps({k: v for k, v in doc.items() if k != "states"}, indent=1)
    body = ",\n".join("  " + json.dumps(s, separators=(",", ":")) for s in doc["states"])
    return (head[:-2] + ',\n "states": [\n' + body + "\n ]\n}\n").encode()


def write_all(out_dir=DESIGN_DIR) -> list:
    from . import refusals2

    out = []
    for name, doc in documents().items():
        p = Path(out_dir) / name
        p.write_bytes(canonical(doc))
        out.append(p)
    return out + refusals2.write_all(Path(out_dir) / "refusals2")
