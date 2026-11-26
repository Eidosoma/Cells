"""OL6 Protocol D: cells.assembly_representation.rate_equations@1 against cells.model.assembly_lineages@2's exact events at large
counts (docs/OL6_PROTOCOL_D.md; D304), as registered worlds, rungs, seeds, observables, criteria and
plants.

The protocol's text is the authority; this module is its registered arithmetic:
- the worlds D0-D7 and their definitions in both representations, rung by rung (`definition`);
- the observables, read from either representation's rows by the same engine functions
  (`observables`);
- the criteria P, B, M, E and L as functions of arrays (`criterion_*`), and n_min's rule;
- the plants, as definition edits (`plant_definition`) or scoped patches of (d)'s path only
  (`plant_scope`).
It runs nothing by itself, except `size`, the author's (d)-alone sizing before the tag (disclosed
in the protocol's §12). Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`.
"""

import contextlib
import copy
import math

import numpy as np

NA = 6.02214076e23
C0_MM = 1000.0  # the standard concentration, mM (1 M): a dilute activity is n / (N_A V c0)
T_K = 298.15
U = "OL6 Protocol D's declared world (illustrative, unsourced)"

# --------------------------------------------------------------------------- the registered ladder

DENSITY = ("D1", "D2", "D3")
VESICLE = ("D4", "D5", "D6", "D7")
RUNGS = {"density": (1000, 4000, 16000, 64000), "vesicle": (25.0, 50.0, 100.0)}  # Ω; diameter nm
REPLICAS = {"density": 256, "vesicle": 128, "D0": 256}
SEED_BASE = {"first": 1, "retry": 100001}  # seeds SEED_BASE + 0 .. M - 1, environment 0
MIN_COUNT = 10.0  # the qualification runs' envelope (the note's §5.1), below every rung's counts
ENVELOPE = {"min_count": MIN_COUNT, "provenance": "Protocol D's qualification runs"}
INTEGRATORS = {
    "density": {"id": "cells.solver.rosenbrock_rodas4_dense@1", "rtol": 1e-10, "atol_count": 1e-6,
                "step_limit": 1000000},
    # The clock's bound (the lead's ruling (a)): 1e-10 absolute per step on H's embedded estimate
    # needs rtol 1e-12 and atol_count 1e-9 in a σ-from-F world; D4-D6 take the same, as D7's twins.
    "vesicle": {"id": "cells.solver.rosenbrock_rodas4_dense@1", "rtol": 1e-12, "atol_count": 1e-9,
                "step_limit": 1000000},
}  # fmt: skip
EXACT = {"chunk_events": 4096, "event_limit": 2**31 - 1}


def family(name):
    return "density" if name in DENSITY else "vesicle" if name in VESICLE else name


def seeds(name, which="first"):
    base = SEED_BASE[which]
    return tuple(range(base, base + REPLICAS["D0" if name == "D0" else family(name)]))


# --------------------------------------------------------------------------- shared declarations


def species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def mass_action(name, reactants, products, rate, *, phase=None, locus=None):
    from cells.models.assembly_lineages_v2 import MASS_ACTION

    out = {"id": name, "reactants": reactants, "products": products, "law": MASS_ACTION}
    out["phase" if phase is not None else "locus"] = phase if phase is not None else locus
    out["forward_rate_per_s"] = rate
    return out


def units():
    return {"time": "s", "temperature_K": T_K, "standard_concentration_mM": C0_MM}


def conventions(measure="multinomial", last="kept", **more):
    return {"free_energy_form": "discrete", "condensed_measure": measure,
            "membrane_kinetics": "count_on_m", "lumen_volume": "declared",
            "empty_catalyst_phase": "uncatalysed", "last_molecule": last, **more}  # fmt: skip


def volume_for(x):
    """The volume (L) at which a dilute phase's X = N_A V c0 equals x."""
    return x / (NA * C0_MM * 1e-3)


# ------------------------------------------------------------------------- the density worlds

# D0, the sparse plant (P4's world): 2A <-> B closed, T = n_A + 2 n_B = 12, q T = 4 with
# q = exp(2 mu_A - mu_B) / X: X = 12 and mu_B = -ln 4. Its founder sits at the fixed point, rounded.
D0 = {"T": 12, "X": 12.0, "mu_B": -math.log(4.0), "k_f": 1.0, "founder": {"A": 4, "B": 4},
      "times": (5.0, 10.0, 15.0, 20.0, 25.0, 30.0, 35.0, 40.0)}  # fmt: skip
# D1: A + B <-> C and 2A <-> D in a finite pool with X = Ω; founders (0.5, 0.3, 0.1, 0.1) Ω; the
# equilibrium (0.4, 0.25, 0.15, 0.125) Ω, so every place stays at or above 0.1 Ω.
D1 = {"mu": {"A": 0.0, "B": 0.0, "C": -math.log(1.5), "D": -math.log(0.78125)},
      "k": {"ab": 2.0, "aa": 1.0}, "founder": {"A": 0.5, "B": 0.3, "C": 0.1, "D": 0.1},
      "times": (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)}  # fmt: skip
# D2: four types join a membrane from held pool places (K_i rho_i summing to 1.5, so N grows),
# catalysed by GARD's lognormal factor (seed below), with T0 + T1 <-> C in the membrane.
D2 = {"K": (2.0, 1.5, 1.0, 3.0), "K_rho": (0.5, 0.4, 0.35, 0.25), "kb": (1.0, 0.8, 1.2, 1.0),
      "mu_C": -math.log(2.0), "k_dimer": 2.0, "beta_seed": 20261124,
      "founder": (0.3, 0.25, 0.25, 0.1, 0.1),  # T0..T3, C, as fractions of N0 = Ω
      "times": None}  # fmt: skip
# D3: three types between a finite pool (X = Ω) and a membrane, with regular mixing, relaxing.
D3 = {"mu_bil": (-1.0, -0.5, -0.75), "k": (3.0, 2.0, 2.0),
      "chi": ((0, 1, 1.5), (1, 2, -1.5)),
      "pool": (0.4, 0.3, 0.3), "membrane": (0.1, 0.2, 0.1),
      "times": (0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 4.0)}  # fmt: skip


def d0_world():
    from cells.models.assembly_lineages_v2 import IDEAL_MIXING

    return {
        "units": units(), "conventions": conventions(),
        "species": [species("A", {"a": 1}, solution=0.0),
                    species("B", {"a": 2}, solution=D0["mu_B"]),
                    species("M", None, bilayer=0.0)],
        "phases": {"pool": {"volume_L": volume_for(D0["X"]),
                            "species": [{"id": "A", "kind": "finite"},
                                        {"id": "B", "kind": "finite"}]},
                   "membrane": {"species": ["M"]}},
        "steps": [mass_action("dimerise", {"A": 2}, {"B": 1}, D0["k_f"], phase="pool")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"A@pool": D0["founder"]["A"], "B@pool": D0["founder"]["B"], "M@membrane": 1},
    }  # fmt: skip


def d1_world(omega):
    from cells.models.assembly_lineages_v2 import IDEAL_MIXING

    mu, f = D1["mu"], D1["founder"]
    moieties = {"A": {"a": 1}, "B": {"b": 1}, "C": {"a": 1, "b": 1}, "D": {"a": 2}}
    return {
        "units": units(), "conventions": conventions(),
        "species": [species(s, moieties[s], solution=mu[s]) for s in "ABCD"]
        + [species("M", None, bilayer=0.0)],
        "phases": {"pool": {"volume_L": volume_for(omega),
                            "species": [{"id": s, "kind": "finite"} for s in "ABCD"]},
                   "membrane": {"species": ["M"]}},
        "steps": [mass_action("ab", {"A": 1, "B": 1}, {"C": 1}, D1["k"]["ab"], phase="pool"),
                  mass_action("aa", {"A": 2}, {"D": 1}, D1["k"]["aa"], phase="pool")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {**{f"{s}@pool": int(round(f[s] * omega)) for s in "ABCD"}, "M@membrane": 1},
    }  # fmt: skip


def d2_beta():
    z = np.random.default_rng(D2["beta_seed"]).standard_normal((4, 4))
    return np.exp(-4.0 + 4.0 * z)


def d2_world(omega, beta=None):
    from cells.models.assembly_lineages_v2 import IDEAL_MIXING, TRANSITION_STATE

    beta = d2_beta() if beta is None else np.asarray(beta)
    ids = [f"T{i}" for i in range(4)]
    k, k_rho, kb = D2["K"], D2["K_rho"], D2["kb"]
    sp = [species(s, {s.lower(): 1}, solution=0.0, bilayer=-math.log(k[i]))
          for i, s in enumerate(ids)]  # fmt: skip
    mu_c = -math.log(k[0]) - math.log(k[1]) + D2["mu_C"]
    sp.append(species("C", {"t0": 1, "t1": 1}, bilayer=mu_c))
    steps = [mass_action(f"join_{s}", {f"{s}@pool": 1}, {f"{s}@membrane": 1},
                         float(k[i] * kb[i]), locus="membrane") for i, s in enumerate(ids)]
    steps.append(mass_action("dimer", {"T0": 1, "T1": 1}, {"C": 1}, D2["k_dimer"],
                             phase="membrane"))  # fmt: skip
    entries = [{"catalyst": ids[j], "step": f"join_{ids[i]}", "ddG_kT": math.log1p(beta[i, j])}
               for i in range(4) for j in range(4)]  # fmt: skip
    f = D2["founder"]
    founder = {f"{s}@membrane": int(round(f[i] * omega)) for i, s in enumerate(ids)}
    founder["C@membrane"] = int(round(f[4] * omega))
    return {
        "units": {**units(), "standard_concentration_mM": 1.0},  # held activity rho = held_mM
        "conventions": conventions(),
        "species": sp,
        "phases": {"pool": {"volume_L": 1e-21, "species": [
            {"id": s, "kind": "held", "held_mM": float(k_rho[i] / k[i])}
            for i, s in enumerate(ids)]},
                   "membrane": {"species": [*ids, "C"]}},
        "steps": steps,
        "free_energy": [{"law": IDEAL_MIXING}],
        "rate_factor": {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                        "entries": entries},
        "founder": founder,
    }  # fmt: skip


def d3_world(omega):
    from cells.models.assembly_lineages_v2 import IDEAL_MIXING, REGULAR_MIXING

    ids = ["U0", "U1", "U2"]
    sp = [species(s, {s.lower(): 1}, solution=0.0, bilayer=D3["mu_bil"][i])
          for i, s in enumerate(ids)]  # fmt: skip
    steps = [mass_action(f"join_{s}", {f"{s}@pool": 1}, {f"{s}@membrane": 1}, D3["k"][i],
                         locus="membrane") for i, s in enumerate(ids)]  # fmt: skip
    chi = [{"pair": [ids[a], ids[b]], "chi": c} for a, b, c in D3["chi"]]
    founder = {f"{s}@pool": int(round(D3["pool"][i] * omega)) for i, s in enumerate(ids)}
    founder |= {f"{s}@membrane": int(round(D3["membrane"][i] * omega)) for i, s in enumerate(ids)}
    return {
        "units": units(), "conventions": conventions("multinomial_less_one"),
        "species": sp,
        "phases": {"pool": {"volume_L": volume_for(omega),
                            "species": [{"id": s, "kind": "finite"} for s in ids]},
                   "membrane": {"species": ids}},
        "steps": steps,
        "free_energy": [{"law": IDEAL_MIXING}, {"law": REGULAR_MIXING, "chi_kT": chi}],
        "founder": founder,
    }  # fmt: skip


# ------------------------------------------------------------------------- the vesicle worlds

Q_M2, K_L = 1e-20, 30  # 0.3 nm² per amphiphile per leaflet (the note's §5.1)
VES = {
    "c_ext_mM": 300.0,  # the outside osmolarity
    "mu_bil_L": -9.43,  # the note's transfer potential for oleate (§2.5), illustrative
    "closure_kT": 25.0,
    "floor_fraction": 0.05,  # the vesicle floor, as a fraction of the founder's membrane
}
# D4 (and D7, its twin with the pore law): a floppy vesicle whose lumen takes up a permeant S from
# a held pool, past the kink, to lysis at sigma_max; L joins from a held pool at its floppy
# equilibrium, so the tension pulls amphiphile in.
D4 = {"x0": 0.9, "c_ext_mM": 600.0, "S_held_mM": 480.0, "S_lumen_fraction": 0.1, "P_m_per_s": 1e-8,
      "insertion_m_per_s": 6.7e-7, "sigma_max": 3e-3, "times": None}  # fmt: skip
# D7's pore law (sigma from F): ln(A nu_A) at the founder's area, the line tension and the rest.
D7 = {"log_c": 34.0, "gamma_N": 4.5e-12, "E_A_J_per_mol": 27e3, "eta_298_Pa_s_m": 3e-10}
# D5: two vesicles on one finite pool of L, one tense (x0 > 1) and one floppy, exchanging L.
D5 = {"x0": (1.43, 0.85), "pool_fraction": 0.02, "insertion_m_per_s": 2e-6,
      "sigma_max": 2e-2, "times": None}  # fmt: skip
# D6: a floppy vesicle in a finite pool of L at its equilibrium, split at one shear time (k = 2,
# continuation first), the followed daughter then relaxing.
D6 = {"x0": 0.6, "pool_fraction": 0.02, "insertion_m_per_s": 2e-6, "shear_s": 1.0,
      "sigma_max": 2e-2, "horizon_s": 3.0, "times": (0.25, 0.5, 0.75, 1.25, 1.5, 2.0, 2.5, 3.0)}


def membrane_count(diameter_nm):
    """A sphere's amphiphiles at the diameter: N = 2 A / (q K_L), A = π d²."""
    area = math.pi * (diameter_nm * 1e-9) ** 2
    return int(round(2.0 * area / (Q_M2 * K_L)))


def lumen_count(n_mem, x0, c_mm):
    """The lumen's osmoles at which V_osm / V_sph = x0 (c_mm the outside osmolarity)."""
    area = Q_M2 * K_L * n_mem / 2.0
    v_sph = area**1.5 / (6.0 * math.sqrt(math.pi)) * 1e3  # L
    return int(round(x0 * v_sph * NA * c_mm * 1e-3))


def floppy_equilibrium_mM():
    """The held L concentration at which a floppy one-species membrane is at equilibrium:
    ln(c/c0) = mu_bil - mu_sol (its membrane activity is 1)."""
    return C0_MM * math.exp(VES["mu_bil_L"])


def _geometry(n_mem, sigma_max):
    from cells.models.assembly_lineages_v2 import BILAYER_GEOMETRY

    return {"law": BILAYER_GEOMETRY, "area_quantum_m2": Q_M2,
            "area_per_leaflet": {"L": {"quanta": K_L, "provenance": U}},
            "vesicle_floor": {"quanta": int(VES["floor_fraction"] * n_mem) * K_L,
                              "provenance": U},
            "closure_cost_kT": {"value": VES["closure_kT"], "provenance": U},
            "sigma_max_N_per_m": {"value": sigma_max, "provenance": U}}  # fmt: skip


def _osmotic(c_ext=None):
    from cells.models.assembly_lineages_v2 import IDEAL_MIXING, OSMOTIC_LUMEN

    value = VES["c_ext_mM"] if c_ext is None else c_ext
    return [{"law": IDEAL_MIXING},
            {"law": OSMOTIC_LUMEN, "outside_osmolarity_mM": {"value": value, "provenance": U}}]


def _join(velocity):
    from cells.models.assembly_lineages_v2 import PHASE_EXCHANGE

    return {"id": "join", "locus": "membrane", "reactants": {"L@pool": 1},
            "products": {"L@membrane": 1}, "law": PHASE_EXCHANGE,
            "insertion_velocity_m_per_s": {"value": velocity, "provenance": U}}  # fmt: skip


def vesicle_conventions():
    return conventions(lumen_volume="osmotic", exchange_encounter="insertion_area")


def d4_world(diameter_nm, *, pores=False):
    from cells.models.assembly_lineages_v2 import MEMBRANE_PERMEATION, PORE_NUCLEATION

    n = membrane_count(diameter_nm)
    c = D4["c_ext_mM"]
    n_i = lumen_count(n, D4["x0"], c)
    n_s = lumen_count(n, D4["x0"] * D4["S_lumen_fraction"], c)
    w = {
        "units": units(), "conventions": vesicle_conventions(),
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=VES["mu_bil_L"]),
                    species("I", {"i": 1}, solution=0.0), species("S", {"s": 1}, solution=0.0)],
        "phases": {"pool": {"volume_L": 1e-18, "species": [
            {"id": "L", "kind": "held", "held_mM": floppy_equilibrium_mM()},
            {"id": "S", "kind": "held", "held_mM": D4["S_held_mM"]},
            {"id": "I", "kind": "finite"}]},
                   "membrane": {"species": ["L"]}, "lumen": {"species": ["I", "S"]}},
        "steps": [_join(D4["insertion_m_per_s"]),
                  {"id": "permeate", "locus": "membrane", "reactants": {"S@pool": 1},
                   "products": {"S@lumen": 1}, "law": MEMBRANE_PERMEATION,
                   "permeability_m_per_s": {"value": D4["P_m_per_s"], "provenance": U}}],
        "free_energy": _osmotic(c),
        "founder": {"I@pool": 0, "L@membrane": n, "I@lumen": n_i - n_s, "S@lumen": n_s},
        "geometry": _geometry(n, D4["sigma_max"]),
    }  # fmt: skip
    if pores:
        area = Q_M2 * K_L * n / 2.0
        values = {"nu_A": math.exp(D7["log_c"]) / area, "gamma_N": D7["gamma_N"],
                  "E_A_J_per_mol": D7["E_A_J_per_mol"], "eta_298_Pa_s_m": D7["eta_298_Pa_s_m"]}
        w["hazard"] = {"law": PORE_NUCLEATION,
                       **{k: {"value": v, "provenance": U} for k, v in values.items()}}
    return w


def _finite_pool_vesicle(n_ref, pool_fraction, velocity, sigma_max):
    """A one-species vesicle world whose finite pool of L sits at the floppy equilibrium's
    concentration, holding pool_fraction of n_ref amphiphiles, and an impermeant lumen I."""
    pool_l = max(int(round(pool_fraction * n_ref)), 1)
    volume = pool_l / (NA * floppy_equilibrium_mM() * 1e-3)
    return {
        "units": units(), "conventions": vesicle_conventions(),
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=VES["mu_bil_L"]),
                    species("I", {"i": 1}, solution=0.0)],
        "phases": {"pool": {"volume_L": volume, "species": [{"id": "L", "kind": "finite"},
                                                            {"id": "I", "kind": "finite"}]},
                   "membrane": {"species": ["L"]}, "lumen": {"species": ["I"]}},
        "steps": [_join(velocity)],
        "free_energy": _osmotic(),
        "founder": {"L@pool": pool_l, "I@pool": 0},
        "geometry": _geometry(n_ref, sigma_max),
    }  # fmt: skip


def d5_world(diameter_nm):
    from cells.models.assembly_lineages_v2 import SHARED_POOL

    n = membrane_count(diameter_nm)
    w = _finite_pool_vesicle(2 * n, D5["pool_fraction"], D5["insertion_m_per_s"],
                             D5["sigma_max"])  # fmt: skip
    w["founder"] |= {"L@membrane": 0, "I@lumen": 0}
    w["population"] = {"structure": SHARED_POOL, "slots": 2, "founders": [
        {"L@membrane": n, "I@lumen": lumen_count(n, x0, VES["c_ext_mM"])} for x0 in D5["x0"]]}
    return w


def d6_world(diameter_nm):
    from cells.models.assembly_lineages_v2 import SHEAR_FISSION

    n = membrane_count(diameter_nm)
    w = _finite_pool_vesicle(n, D6["pool_fraction"], D6["insertion_m_per_s"], D6["sigma_max"])
    w["founder"] |= {"L@membrane": n, "I@lumen": lumen_count(n, D6["x0"], VES["c_ext_mM"])}
    w["division"] = {"law": SHEAR_FISSION, "continuation": "first"}
    return w


WORLDS = {"D0": lambda rung: d0_world(), "D1": d1_world, "D2": d2_world, "D3": d3_world,
          "D4": d4_world, "D5": d5_world, "D6": d6_world,
          "D7": lambda d: d4_world(d, pores=True)}  # fmt: skip


# --------------------------------------------------------------------------- the definitions


def experiment(name, rung, times):
    """The experiment block both representations share: the horizon is the last observation
    time (D4 and D7: their registered horizons), and D6's one shear time."""
    horizon = HORIZONS[name][rung] if name in ("D4", "D7") else times[-1]
    out = {"time_horizon_s": float(horizon), "event_limit": EXACT["event_limit"],
           "row_every_events": EXACT["event_limit"], "observation_times_s": list(times),
           "trace": False, "uniforms": False}  # fmt: skip
    if name == "D6":
        out["schedules"] = [{"index": 0, "kind": "shear", "k": 2, "times_s": [D6["shear_s"]]}]
    return out


# The registered observation times and horizons that the (d)-alone sizing fixed (the protocol's
# §2 and §12). D4 and D7, per rung from (d)'s kink t_k and lysis t* (sizing at seed 1): three
# times at (0.3, 0.6, 0.9) t_k, then five at t_k + (0.2 .. 1.0)(0.75 t* - t_k); the horizon 2 t*.
SIZED = {25.0: (0.065, 0.3776), 50.0: (0.13, 0.3840), 100.0: (0.26, 0.4922)}  # (t_k, t*), s


def _vesicle_times(t_k, t_star):
    late = 0.75 * t_star - t_k
    return tuple(round(x, 6) for x in (0.3 * t_k, 0.6 * t_k, 0.9 * t_k,
                                       *(t_k + f * late for f in (0.2, 0.4, 0.6, 0.8, 1.0))))


TIMES = {
    "D2": {r: (0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4) for r in RUNGS["density"]},
    "D4": {r: _vesicle_times(*SIZED[r]) for r in RUNGS["vesicle"]},
    "D5": {r: (7.5, 15.0, 22.5, 30.0, 37.5, 45.0, 52.5, 60.0) for r in RUNGS["vesicle"]},
}
TIMES["D7"] = {r: () for r in RUNGS["vesicle"]}  # D7 is judged on its paired event only (§2)
HORIZONS = {"D4": {r: round(2.0 * SIZED[r][1], 6) for r in RUNGS["vesicle"]}}
HORIZONS["D7"] = HORIZONS["D4"]


def times_of(name, rung):
    if name == "D0":
        return D0["times"]
    if name in ("D1", "D3"):
        return {"D1": D1, "D3": D3}[name]["times"]
    if name == "D6":
        return D6["times"]
    return TIMES[name][rung]


def capacity(world):
    """The exact kernel's molecule capacity: a power of two above every count it can reach."""
    founder = world["founder"]
    total = sum(founder.values())
    for f in world.get("population", {}).get("founders", []):
        total += sum(f.values())
    return 1 << int(math.ceil(math.log2(max(4 * total, 256))))


def definition(name, rung, seed, representation):
    """One run's definition: `representation` False for exact events, True for (d)."""
    from cells.models.assembly_lineages_v2 import MODEL_ID, RATE_EQUATIONS

    world = WORLDS[name](rung)
    mode = "population" if "population" in world else "single_lineage"
    out = {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world},
        "experiment": experiment(name, rung, times_of(name, rung)),
        "execution": {"backend": "cpu", "precision": "float64", "mode": mode,
                      "stream": {"seed": int(seed), "environment": 0, "lineage": 0,
                                 "branch": 0}},
    }  # fmt: skip
    if representation:
        out["execution"]["representation"] = {
            "id": RATE_EQUATIONS, "envelope": dict(ENVELOPE),
            "integrator": dict(INTEGRATORS["density" if name in ("D0", *DENSITY)
                                            else "vesicle"])}  # fmt: skip
    else:
        out["execution"] |= {"molecule_capacity": capacity(world),
                             "chunk_events": EXACT["chunk_events"]}  # fmt: skip
    return out


# --------------------------------------------------------------------------- the observables

OBSERVED = {"exact": 3, "d": "observed"}  # runner.ROW_KINDS' index of "observed"; (d)'s name


def vesicle_derived(world, counts):
    """A (m²), V (L) and σ (N/m) of one vesicle's state (its places, pool included), by the
    engine's own lumen functions on real N_L and W, the same for either representation."""
    from cells.models.assembly_lineages_v2 import geometry, lumen

    n = np.asarray(counts, dtype=np.float64)
    is_lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.float64)
    quanta = geometry.place_quanta(world, len(world.places)).astype(np.float64)
    n_l, w = np.float64(n @ is_lumen), np.float64(n @ quanta)
    q = world.geometry[1]["area_quantum_m2"]
    kT = lumen.BOLTZMANN * world.units.temperature_K
    c = np.asarray(lumen.constants(world))
    return {"A_m2": float(q * w / 2.0), "V_L": float(np.exp(lumen.log_volume(n_l, w, c, np))),
            "sigma_N_per_m": float(lumen.tension(n_l, w, kT, q, c, np))}  # fmt: skip


def enveloped(world):
    """The envelope's places (the note's §1.5): the indices rate_equations.enveloped marks, every
    finite place some rate reads."""
    from cells.models.assembly_lineages_v2 import rate_equations

    return [i for i, on in enumerate(rate_equations.enveloped(world)) if on]


def _rows(run, representation):
    """(times, kinds mask of observed rows, per-row vesicle states) from either run's rows."""
    rows = run.rows
    if representation:
        times, observed = rows["row_time_s"], rows["row_kind"] == OBSERVED["d"]
        if "slot_counts" in rows:
            return times, observed, rows["pool_counts"], rows["slot_counts"], rows
        return times, observed, rows["counts"], None, rows
    times, observed = rows["row_time"], rows["row_kind"] == OBSERVED["exact"]
    if "slot_count" in rows:
        return times, observed, rows["pool_count"], rows["slot_count"], rows
    return times, observed, rows["place_count"], None, rows


def observables(name, spec, run, representation, *, start=False):
    """The registered observables at the registered observation times (protocol §3): a dict of
    name -> array over the times, NaN where the run had ended (lysed) before that time. With
    start, the same observables at the founder (the start row), as arrays of one."""
    world = spec.model.world
    times = np.asarray(spec.experiment.observation_times_s, dtype=np.float64)
    t, observed, pool, slots, rows = _rows(run, representation)
    if start:
        kinds = np.asarray(rows["row_kind"])
        observed = kinds == ("start" if representation else 0)  # runner.ROW_KINDS[0]
        times = np.asarray([0.0])
    t_obs = np.asarray(t)[observed]
    out = {}

    def at(values):
        values = np.asarray(values, dtype=np.float64)[observed]
        full = np.full(len(times), np.nan)
        for k, tk in enumerate(times):
            hit = np.flatnonzero(t_obs == tk)
            if hit.size:
                full[k] = values[hit[0]]
        return full

    places = [p.name for p in world.places]
    if slots is None:
        counts = np.asarray(pool, dtype=np.float64)
        for i in enveloped(world):
            out[places[i]] = at(counts[:, i])
        if world.geometry is not None:
            derived = [vesicle_derived(world, c) for c in counts]
            for key in ("A_m2", "V_L", "sigma_N_per_m"):
                out[key] = at([d[key] for d in derived])
    else:
        pool, slots = np.asarray(pool, dtype=np.float64), np.asarray(slots, dtype=np.float64)
        pool_places = [i for i, p in enumerate(world.places) if p.phase == "pool"]
        for i in enveloped(world):
            if i in pool_places:
                out[places[i]] = at(pool[:, i])
        for k in range(slots.shape[1]):
            for i in enveloped(world):
                if i not in pool_places:
                    out[f"slot{k}:{places[i]}"] = at(slots[:, k, i])
            derived = [vesicle_derived(world, pool[r] * 0 + slots[r, k]) for r in range(len(pool))]
            for key in ("A_m2", "V_L", "sigma_N_per_m"):
                out[f"slot{k}:{key}"] = at([d[key] for d in derived])
    if "reservoir_work_kT" in rows and np.any(np.asarray(rows["reservoir_work_kT"]) != 0):
        out["W_res_kT"] = at(rows["reservoir_work_kT"])
    return out


def event_time(run, representation, kind):
    """The vesicle's end time, by `kind` (lysis at σ_max, or the pore's opening), or None."""
    if representation:
        hits = [e for e in run.events if e.get("kind") in ("lysis", "rupture")
                and e.get("cause") == kind]  # fmt: skip
        return float(hits[0]["time_s"]) if hits else None
    if kind == "pore":
        events = (run.pores or {}).get("events") or []
        return float(events[0]["time_s"]) if events else None
    lysis = (run.osmotic or {}).get("lysis")
    return float(lysis["time_s"]) if lysis else None


# ------------------------------------------------------------------------------ the criteria

Z_STAR = 4.5  # criterion M's and B's sampling threshold (the protocol's §5)
Z_FAIL = 6.0  # beyond it a statistical criterion fails outright; between, inconclusive
SLOPE = {"centre": -0.5, "half_width": 0.1}  # criterion P (the protocol's §5.1)
B_MEAN = 2.0  # b: the envelope's mean budget, b / n_min relative
C_SPREAD = 5.0  # c_r: the envelope's replica budget, c_r / sqrt(n_min) relative
SPREAD_QUANTILE = 0.99
E_RATIO = 0.75  # criterion E: SD_K <= 0.75 SD_(K-1), 0.5 expected


def scales(d_values, d_start):
    """s_y: the largest |y_d| over the founder (d_start, observables(..., start=True)) and the
    registered times (the protocol's §3)."""
    return {k: float(max(np.nanmax(np.abs(v)), np.nanmax(np.abs(d_start[k]))))
            for k, v in d_values.items()}  # fmt: skip


def is_count(key):
    """B judges the counts only (the protocol's §5.3); A, V, σ and W_res are judged under M."""
    return "@" in key


def criterion_p(d_rms, sizes):
    """P: the least-squares slope of ln D_k against ln N_k, with its window."""
    x, y = np.log(np.asarray(sizes, dtype=np.float64)), np.log(np.asarray(d_rms))
    slope = float(np.polyfit(x, y, 1)[0])
    lo, hi = SLOPE["centre"] - SLOPE["half_width"], SLOPE["centre"] + SLOPE["half_width"]
    return {"slope": slope, "window": [lo, hi], "passes": bool(lo <= slope <= hi)}


def pathwise_rms(exact, d, scale):
    """D_k: the root mean square over replicas, times and observables of (y_a - y_d)/s_y.
    exact: {obs: [M, T]}, d: {obs: [T]}."""
    terms = [((exact[k] - d[k][None, :]) / scale[k]) for k in d if scale[k] > 0]
    stacked = np.concatenate([t.ravel() for t in terms])
    return float(np.sqrt(np.nanmean(stacked**2)))


def mean_error(exact, d):
    """e and SE per (observable, time): mean over replicas of y_a, minus y_d."""
    out = {}
    for k in d:
        values = exact[k]
        m = np.sum(np.isfinite(values), axis=0)
        out[k] = (np.nanmean(values, axis=0) - d[k],
                  np.nanstd(values, axis=0, ddof=1) / np.sqrt(np.maximum(m, 1)))
    return out


def criterion_m(top, below):
    """M at the top rung K against K - 1: |e_K| <= z (SE_K² + SE_(K-1)²/4)^½ + |e_(K-1)|/2, per
    (observable, time); the largest excess in units of the combined SE."""
    worst = -np.inf
    for k, (e_k, se_k) in top.items():
        e_b, se_b = below[k]
        combined = np.sqrt(se_k**2 + se_b**2 / 4.0)
        excess = (np.abs(e_k) - np.abs(e_b) / 2.0) / np.where(combined > 0, combined, np.inf)
        worst = max(worst, float(np.nanmax(excess)))
    return {"largest_z": worst, "passes": worst <= Z_STAR,
            "fails": worst > Z_FAIL}  # fmt: skip


def criterion_b(exact, d, errors, scale, n_k):
    """B at one rung: the mean, |e| <= z SE + b s_y / n_k, and each replica, the 99th percentile
    over replicas of max over the times of |y_a - y_d|/s_y <= c_r / sqrt(n_k). Returns each
    world's smallest passing b and c_r beside the verdict (the constants' sensitivity)."""
    b_needed, c_needed = 0.0, 0.0
    for k in d:
        if scale[k] <= 0 or not is_count(k):
            continue
        e, se = errors[k]
        excess = np.maximum(np.abs(e) - Z_STAR * se, 0.0)
        b_needed = max(b_needed, float(np.nanmax(excess)) * n_k / scale[k])
        worst = np.nanmax(np.abs(exact[k] - d[k][None, :]) / scale[k], axis=1)
        c_needed = max(c_needed, float(np.quantile(worst, SPREAD_QUANTILE)) * math.sqrt(n_k))
    return {"b_needed": b_needed, "c_r_needed": c_needed, "mean_passes": b_needed <= B_MEAN,
            "spread_passes": c_needed <= C_SPREAD}  # fmt: skip


def criterion_b_at(exact, d, errors, scale, n_min):
    """B held at the envelope's budget (a world outside it, and the plant P-D1): n_k = n_min."""
    return criterion_b(exact, d, errors, scale, n_min)


def criterion_e(times_by_rung, d_by_rung):
    """E: M on mean(T_a) - t*_d between the top two rungs, and the spread from the bottom rung to
    the top, SD_K <= 0.75 SD_1 (a fourfold diameter: 0.5 expected). For D7, times are the paired
    Δ = T_a - t*_d(E) and d_by_rung zeros, with RMS(Δ) for the spread (pass them as such)."""
    first = np.asarray(times_by_rung[0]) - np.asarray(d_by_rung[0])
    (t_b, d_b), (t_k, d_k) = zip(times_by_rung[-2:], d_by_rung[-2:], strict=True)
    e_b, e_k = float(np.mean(t_b) - d_b), float(np.mean(t_k) - d_k)
    se_b, se_k = float(np.std(t_b, ddof=1) / math.sqrt(len(t_b))), float(
        np.std(t_k, ddof=1) / math.sqrt(len(t_k))
    )
    z = (abs(e_k) - abs(e_b) / 2.0) / math.sqrt(se_k**2 + se_b**2 / 4.0)
    ratio = float(np.std(np.asarray(t_k) - np.asarray(d_k), ddof=1) / np.std(first, ddof=1))
    return {"mean_z": z, "sd_ratio": ratio, "passes": z <= Z_STAR and ratio <= E_RATIO,
            "fails": z > Z_FAIL or ratio > E_RATIO}  # fmt: skip


def n_min_rule(results, ladder_passes):
    """n_min: the smallest n_k such that every (world, rung) with n_k at or above it passes B, P and
    M passing over the ladder (ladder_passes); rounded up to two significant figures.
    results: [(n_k, passes)]. None when the ladder fails or no such n_k exists."""
    if not ladder_passes:
        return None
    ordered = sorted(results)
    for i, (n_k, _) in enumerate(ordered):
        if all(passes for _, passes in ordered[i:]):
            digits = 10 ** (math.floor(math.log10(n_k)) - 1)
            return math.ceil(n_k / digits) * digits
    return None


def d0_stationary():
    """P-D1's closed form (S): D0's exact stationary law, P(n_B = j) ∝ q^j / ((T - 2j)! j!) with
    q = exp(2 mu_A - mu_B) / X, its rate-equation fixed point, and the deviation of n_A, in units
    of s_A = 4, that a single time reaches with probability at least 1%."""
    total, q = D0["T"], math.exp(-D0["mu_B"]) / D0["X"]
    j = np.arange(total // 2 + 1)
    log_p = j * math.log(q) - np.array([math.lgamma(total - 2 * k + 1) + math.lgamma(k + 1)
                                        for k in j])  # fmt: skip
    p = np.exp(log_p - log_p.max())
    p /= p.sum()
    n_a = total - 2 * j
    fixed = (-1.0 + math.sqrt(1.0 + 8.0 * q * total)) / (4.0 * q)
    s_a = float(D0["founder"]["A"])
    deviation = np.abs(n_a - fixed) / s_a
    order = np.argsort(-deviation)
    reached = deviation[order][np.searchsorted(np.cumsum(p[order]), 0.01)]
    return {"p_n_A": {int(a): float(x) for a, x in zip(n_a, p, strict=True)},
            "fixed_point_n_A": fixed, "exact_mean_n_A": float(np.sum(p * n_a)),
            "p_n_A_at_least_8": float(np.sum(p[n_a >= 8])),
            "deviation_reached_at_1_percent": float(reached),
            "budget_at_smallest_n_min": C_SPREAD / math.sqrt(97.0)}


# -------------------------------------------------------------------------------- the plants

PLANTS = ("P-D1", "P-D2", "P-D3", "P-D4", "P-D5", "P-D6", "P-D7")
PLANTED_LAW = (
    "validation.reaction.ol6_plant_power_off_by_one@1"  # P-D2's law, in a scoped registry only
)


def plant_definition(plant, name, rung, seed):
    """The (d) definition of a definition-level plant:
    - P-D1: D0 with the envelope's min_count at 1, so the sparse world is admitted;
    - P-D2: D1 with its steps on PLANTED_LAW (run inside plant_scope("P-D2"));
    - P-D3: D2 with its largest β entry × 1.5, in (d)'s world only."""
    out = definition(name, rung, seed, True)
    if plant == "P-D1":
        out["execution"]["representation"]["envelope"] = {
            "min_count": 1.0, "provenance": "P-D1: the envelope check disabled (OL6 Protocol D)"}
    elif plant == "P-D2":
        for st in out["model"]["world"]["steps"]:
            st["law"] = PLANTED_LAW
    elif plant == "P-D3":
        beta = d2_beta()
        i, j = np.unravel_index(int(np.argmax(beta)), beta.shape)
        beta[i, j] *= 1.5
        out["model"]["world"] = d2_world(rung, beta)
    else:
        raise ValueError(f"{plant} is not a definition-level plant")
    return out


@contextlib.contextmanager
def plant_scope(plant, *, check=False):
    """A plant on (d)'s path only, for the duration of (d) runs in their own process (exact runs
    never run inside it):
    - P-D2: PLANTED_LAW, mass action with each reactant's power raised by one in its limit
      kernel, registered in a scoped registry; with check False the world's own limit check
      (rate_equations.limit_check) is a no-op, with check True it runs as built;
    - P-D4: the Laplace factor doubled in the tension (d)'s guards read (lumen.tension), so its
      lysis guard sees 2σ;
    - P-D5: each crossing's root snapped to its bracket's end (rate_equations._locate), and the
      re-step's secant correction off (RESTEPS = 0);
    - P-D6: the heat's sign flipped in (d)'s right-hand side (Shape.rhs, the heat row)."""
    from cells.models.assembly_lineages_v2 import rate_equations as re_

    restore = []
    try:
        if plant == "P-D2":
            import dataclasses

            import jax.numpy as jnp

            from cells.models.assembly_lineages_v2 import MASS_ACTION
            from cells.registry import laws as law_registry

            honest = law_registry.active().lookup(MASS_ACTION)

            def off_by_one(view, *args):
                return honest.limit(view._replace(coeff=jnp.where(view.coeff > 0,
                                                                  view.coeff + 1, 0)), *args)

            planted = dataclasses.replace(honest, law_id=PLANTED_LAW, limit=off_by_one)
            scope = law_registry.scope(law_registry.BUILTIN.extended(planted))
            scope.__enter__()
            restore.append(lambda: scope.__exit__(None, None, None))
            if not check:
                saved = re_.limit_check
                re_.limit_check = lambda *a, **k: 0.0
                restore.append(lambda: setattr(re_, "limit_check", saved))
        elif plant == "P-D4":
            from cells.models.assembly_lineages_v2 import lumen

            saved_t = lumen.tension
            lumen.tension = lambda *a, **k: 2.0 * saved_t(*a, **k)
            restore.append(lambda: setattr(lumen, "tension", saved_t))
        elif plant == "P-D5":
            saved_l, saved_r = re_._locate, re_.RESTEPS
            re_._locate = lambda guard_at, lo, hi, g_lo, g_hi, tolerance=1e-13: hi
            re_.RESTEPS = 0
            restore.append(lambda: (setattr(re_, "_locate", saved_l),
                                    setattr(re_, "RESTEPS", saved_r)))  # fmt: skip
        elif plant == "P-D6":
            saved_rhs = re_.Shape.rhs

            def flipped(self, y, alive):
                out = saved_rhs(self, y, alive)
                return out.at[self.heat_at].multiply(-1.0)

            re_.Shape.rhs = flipped
            restore.append(lambda: setattr(re_.Shape, "rhs", saved_rhs))
        else:
            raise ValueError(f"{plant} is not a scoped plant")
        yield
    finally:
        for undo in reversed(restore):
            undo()


def plant_d7_caught(spec):
    """P-D7: one species' μ° shifted by 0.5 k_BT in F_cont only (the ideal term's limit value),
    on the world's own Problem; True when the limit's check refuses it (item 1, the identity)."""
    import dataclasses

    from cells.definitions.specs import ConfigError
    from cells.models.assembly_lineages_v2 import rate_equations as re_

    problem = re_.Problem(spec)
    ideal = problem.terms[0]
    problem.terms = (dataclasses.replace(
        ideal, limit=lambda n, t, lay, xp: ideal.limit(n, t, lay, xp) + 0.5 * n[0]),
        *problem.terms[1:])  # fmt: skip
    try:
        re_.limit_check(problem, np.random.default_rng(re_.CHECK_SEED), states=4)
    except ConfigError as error:
        return "not the products' law" in str(error)
    return False


# P-D5's closed-form check (N): the regression identity of the S3 tests, a held vesicle whose area
# no step changes, so its opening falls at start + E/k_v exactly (pore_clock.rupture_time).
PD5 = {"n_mem": 20000, "sigma": 7.5e-3, "start_s": 0.5, "end_s": 8.0, "gamma_N": 11e-12,
       "log_c": 34.0, "q": 1e-19, "k_l": 60}  # fmt: skip


def pd5_definition():
    from cells.models.assembly_lineages_v2 import (BILAYER_GEOMETRY, IDEAL_MIXING, MODEL_ID,
                                                   PORE_NUCLEATION, RATE_EQUATIONS)  # fmt: skip

    area = PD5["q"] * PD5["k_l"] * PD5["n_mem"] / 2.0
    values = {"nu_A": math.exp(PD5["log_c"]) / area, "gamma_N": PD5["gamma_N"],
              "E_A_J_per_mol": 27e3, "eta_298_Pa_s_m": 3e-10}
    world = {
        "units": {**units(), "temperature_K": 296.15},
        "conventions": conventions(exchange_encounter="insertion_area"),
        "species": [species("L", {"l": 1}, solution=0.0, bilayer=-9.43),
                    species("A", {"a": 1}, solution=0.0), species("B", {"a": 1}, solution=-0.5)],
        "phases": {"pool": {"volume_L": 1e-17,
                            "species": [{"id": n, "kind": "finite"} for n in "LAB"]},
                   "membrane": {"species": ["L"]}},
        "steps": [mass_action("flip", {"A": 1}, {"B": 1}, 2.0, phase="pool")],
        "free_energy": [{"law": IDEAL_MIXING}],
        "founder": {"L@pool": 0, "A@pool": 5000, "B@pool": 3000, "L@membrane": PD5["n_mem"]},
        "geometry": {"law": BILAYER_GEOMETRY, "area_quantum_m2": PD5["q"],
                     "area_per_leaflet": {"L": {"quanta": PD5["k_l"], "provenance": U}},
                     "vesicle_floor": {"quanta": 1000 * PD5["k_l"], "provenance": U},
                     "closure_cost_kT": {"value": 25.0, "provenance": U}},
        "hazard": {"law": PORE_NUCLEATION,
                   **{k: {"value": v, "provenance": U} for k, v in values.items()}},
    }  # fmt: skip
    return {
        "schema_version": 1, "model": {"id": MODEL_ID, "world": world},
        "experiment": {"time_horizon_s": 10.0, "event_limit": EXACT["event_limit"],
                       "row_every_events": EXACT["event_limit"],
                       "observation_times_s": [0.25, 1.0, 5.0], "trace": False,
                       "uniforms": False,
                       "tension_holds": [{"index": 0, "sigma_N_per_m": PD5["sigma"],
                                          "start_s": PD5["start_s"], "end_s": PD5["end_s"]}]},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": 1, "environment": 0, "lineage": 0, "branch": 0},
                      "representation": {"id": RATE_EQUATIONS, "envelope": dict(ENVELOPE),
                                         "integrator": dict(INTEGRATORS["vesicle"])}},
    }  # fmt: skip


def pd5_gap(spec, run):
    """The regression identity's gap in units of its tolerance, 10 (H_ERROR + 1e-9 max(1, E))/k_v
    (the S3 test's): at most 1 passes. A run that did not open its pore returns inf."""
    from cells.models.assembly_lineages_v2 import pore_clock
    from cells.models.assembly_lineages_v2 import rate_equations as re_

    events = [e for e in run.events if e.get("cause") == "pore"]
    if run.status != "lysed" or not events:
        return math.inf
    area = PD5["q"] * PD5["k_l"] * PD5["n_mem"] / 2.0
    _, energy = pore_clock.threshold(re_._Run(spec).base_key, 0, 0)
    t_star, _, log_k = pore_clock.rupture_time(spec.model.world, spec.experiment.tension_holds,
                                               area, energy)  # fmt: skip
    rate = math.exp(log_k)
    tolerance = 10 * (re_.H_ERROR + 1e-9 * max(1.0, energy)) / rate
    return abs(events[0]["time_s"] - t_star) / tolerance


# ------------------------------------------------------------------------------ the record


def header():
    from cells.models.assembly_lineages_v2 import (BILAYER_GEOMETRY, IDEAL_MIXING, MASS_ACTION,
                                                   MEMBRANE_PERMEATION, MODEL_ID, OSMOTIC_LUMEN,
                                                   PHASE_EXCHANGE, PORE_NUCLEATION,
                                                   RATE_EQUATIONS, REGULAR_MIXING, SHARED_POOL,
                                                   SHEAR_FISSION, TRANSITION_STATE)  # fmt: skip

    chem = [MASS_ACTION, IDEAL_MIXING]
    ves = [BILAYER_GEOMETRY, PHASE_EXCHANGE, OSMOTIC_LUMEN, IDEAL_MIXING]
    return {
        "kind": "cells.ol6.protocol_d@1",
        "status": "proposed for registration: tag ol6-protocol-d-registered-2026-11-23, before any "
        "comparison of cells.assembly_representation.rate_equations@1 with exact events; D7 held "
        "for the lead's choice "
        "(the protocol's §7), by an amendment tagged before it runs",
        "document": "docs/OL6_PROTOCOL_D.md",
        "engine_models": {
            "representation": [RATE_EQUATIONS, "cells.assembly_representation@1",
                               "cells.solver.rosenbrock_rodas4_dense@1"],
            "exact": [MODEL_ID],
            "worlds": {"D0": chem, "D1": chem, "D2": chem + [TRANSITION_STATE],
                       "D3": chem + [REGULAR_MIXING], "D4": ves + [MEMBRANE_PERMEATION],
                       "D5": ves + [SHARED_POOL], "D6": ves + [SHEAR_FISSION],
                       "D7": ves + [MEMBRANE_PERMEATION, PORE_NUCLEATION]},
        },  # fmt: skip
        "not_blind": "the note's probes P2b and P2c (arithmetic identities) and P4 (D0's exact "
        "stationary mean against the rate-equation fixed point, closed form, 2.0% at T = 12) were "
        "read; the parity item of the limit's check (the builders' tests) compares each limit with "
        "its exact kernel at scaled states; S3's clock table (STATE.md); the author ran "
        "cells.assembly_representation.rate_equations@1 alone at snapshot 8df9b012 to size every "
        "world (seed 1; D7 also "
        "seeds 1-12) and to compute the plants' effects; no exact-event run of any registered "
        "world was made, and exact definitions were parsed only",
    }


def constants():
    return {
        "ladder": {"rungs": {k: list(v) for k, v in RUNGS.items()}, "replicas": REPLICAS,
                   "seeds": {"first": SEED_BASE["first"], "retry": SEED_BASE["retry"],
                             "rule": "seeds base .. base + M - 1, environment 0, lineage 0, "
                             "branch 0"}},
        "envelope": ENVELOPE, "integrators": INTEGRATORS, "exact": EXACT,
        "worlds": {"D0": D0, "D1": D1, "D2": {**D2, "beta": d2_beta().tolist()}, "D3": D3,
                   "vesicles": {"Q_m2": Q_M2, "K_L": K_L, **VES}, "D4": D4, "D5": D5, "D6": D6,
                   "D7": D7, "PD5": PD5},
        "times": {name: {str(r): list(t) for r, t in by.items()} for name, by in TIMES.items()},
        "horizons": {name: {str(r): h for r, h in by.items()} for name, by in HORIZONS.items()},
        "sized_vesicle_kink_and_lysis_s": {str(r): list(v) for r, v in SIZED.items()},
        "criteria": {"z_star": Z_STAR, "z_fail": Z_FAIL, "slope": SLOPE, "b": B_MEAN,
                     "c_r": C_SPREAD, "spread_quantile": SPREAD_QUANTILE, "e_ratio": E_RATIO,
                     "moiety_rtol": 1e-12},
        "plants": list(PLANTS),
    }  # fmt: skip


def _json_safe(value):
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    return value


def main(argv=None):
    import argparse
    import json

    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="write the registered inputs (protocol_d.json)")
    reg.add_argument("--out", required=True)
    reg.add_argument("--plants", help="the (d)-alone plant results to record beside them")
    reg.add_argument("--clock", nargs="*", default=(),
                     help="the (d)-alone clock measurements (protocol §7.2, §7.4) to record")
    args = parser.parse_args(argv)
    doc = {**header(), "constants": constants(), "pd1_closed_form": d0_stationary()}
    if args.plants:
        with open(args.plants) as handle:
            doc["plant_power_d_alone"] = json.load(handle)
    if args.clock:
        doc["clock_d_alone"] = {}
        for path in args.clock:
            with open(path) as handle:
                doc["clock_d_alone"][path.rsplit("/", 1)[-1]] = json.load(handle)
    with open(args.out, "w") as handle:
        json.dump(_json_safe(doc), handle, indent=1)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
