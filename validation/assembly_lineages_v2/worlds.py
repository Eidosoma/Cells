"""Development worlds of cells.model.assembly_lineages@2 that combine catalysis with a vesicle's geometry,
its osmotic lumen, shear division and the pool (validation: world definitions, not engine physics).

The engine's laws compose as built (the second builder's plan of 20 November 2026: no refusal and
no missing law), but no world combined them. This module writes such worlds as plain definitions,
which the engine's parser checks; it never checks a world itself.

**Only undriven and held-amphiphile worlds** (the lead's ruling of 20 November 2026 on D242). A step
that consumes a held species to make something that enters the membrane is fuel, and no fueled
world runs before the user chooses a fuel option and OL5 registers its references. A held
amphiphile exchanging with its own membrane place is OL2's physics and is allowed. So every step
here is a join of an amphiphile into the membrane (`cells.reaction.phase_exchange@1`) or the entry of a
permeant solute into the lumen (`cells.reaction.membrane_permeation@1`); there is no pool reaction.

**The world.** G amphiphiles A0 .. A{G-1}, each with a pool place (finite, or held at a declared
concentration) and a membrane place, joined by insertion through the bilayer's area. The lumen
holds an impermeant solute I (with a pool place, since a lysed vesicle's molecules return to the
pool) and, when declared, a permeant solute S. Members catalyse the joins through
`cells.rate_factor.transition_state_factor@1` (catalysts in the membrane, steps that cross the membrane: never a
pool-only step, whose factor the first builder refuses). The geometry is `cells.assembly_geometry.bilayer_geometry@1`,
the lumen `cells.free_energy.osmotic_lumen@1`, and division `cells.operator.shear_fission@1`.

**The numbers are the unit tests' small-count scale** (the lumen test's world: a quantum of
1e-19 m², 60 quanta a molecule, a pool of 1e-22 L, c_ext 1000 mM or twice the pool's solutes, a
closure cost of 25 k_BT), so worlds hold tens of molecules. Every physical value is
unsourced and says so (§0.2e rule 3). The potentials are illustrative: a bilayer potential of
−2 k_BT puts each amphiphile's aggregation threshold at c0·e^−2, about 135 mM.

**Catalysis is per-world data** (ORIGIN_OF_LIFE_ENGINE_DESIGN §2.4), generated here with a
recorded seed and law (catalysis()): GARD's lognormal, β_ij = exp(μ + σ Z_ij) with the diagonal
kept and ΔΔG‡ = ln(1 + β); or uniform, each (catalyst, join) pair with probability p, at ΔΔG‡
uniform in [low, high]. The record goes beside the world (a world holds no free text).
"""

import copy

import numpy as np

from cells.models.assembly_lineages_v2 import (
    BILAYER_GEOMETRY,
    IDEAL_MIXING,
    MEMBRANE_PERMEATION,
    MODEL_ID,
    OSMOTIC_LUMEN,
    PHASE_EXCHANGE,
    SHARED_POOL,
    SHEAR_FISSION,
    TRANSITION_STATE,
)

UNSOURCED = "unsourced; development world (validation/assembly_lineages_v2/worlds.py)"
AVOGADRO = 6.02214076e23
QUANTUM_M2 = 1e-19
QUANTA = 60
POOL_L = 1e-22
C_EXT_MM = 1000.0
CLOSURE_KT = 25.0
SIGMA_MAX = 1e3  # N/m: far above any tension these worlds reach (no lysis by design)
INSERTION = 2e-9  # m/s
PERMEABILITY = 5e-10  # m/s
MU_BILAYER = -2.0  # k_BT at mole fraction 1; the solution potential is 0 at c0
FLOOR_MOLECULES = 4
DDG_MAX = 80.0  # the transition-state factor's domain above (§2.1)


def names(types):
    return [f"A{i}" for i in range(types)]


def _species(name, moieties, **mu):
    return {"id": name, "moieties": moieties, "standard_mu_RT": mu, "catalogue": None,
            "evidence": None}  # fmt: skip


def _value(value):
    return {"value": value, "provenance": UNSOURCED}


def catalysis(types, *, law="lognormal", seed, mu=-4.0, sigma=4.0, p=0.25, low=0.0, high=2.0):
    """(entries, record): the factor's entries over the joins of `types` amphiphiles, catalyst A_j
    on the join of A_i, from NumPy's default generator at `seed`; the record states the law, the
    seed and the parameters. lognormal: GARD's β = exp(mu + sigma Z), every pair, the diagonal
    kept, ΔΔG‡ = ln(1 + β). uniform: each pair with probability p, ΔΔG‡ uniform in [low, high]."""
    rng = np.random.default_rng(seed)
    entries = []
    if law == "lognormal":
        beta = np.exp(mu + sigma * rng.standard_normal((types, types)))
        ddg = np.log1p(beta)
        params = {"mu": mu, "sigma": sigma, "ddG": "ln(1 + beta)", "diagonal": "kept"}
        pairs = [(i, j) for i in range(types) for j in range(types)]
    elif law == "uniform":
        chosen = rng.random((types, types)) < p
        ddg = rng.uniform(low, high, size=(types, types))
        params = {"p": p, "low_kT": low, "high_kT": high}
        pairs = [(i, j) for i in range(types) for j in range(types) if chosen[i, j]]
    else:
        raise ValueError(f"A catalysis law is lognormal or uniform, not {law!r}")
    for i, j in pairs:
        value = float(ddg[i, j])
        if not value <= DDG_MAX:
            raise ValueError(
                f"A drawn ddG of {value:.4g} k_BT is beyond the factor's domain ({DDG_MAX}); "
                "draw again with another seed or law rather than clip it"
            )
        entries.append({"catalyst": f"A{j}", "step": f"join_A{i}", "ddG_kT": value})
    record = {"law": law, "seed": seed, "generator": "numpy.random.default_rng",
              "parameters": params, "entries": len(entries)}  # fmt: skip
    return entries, record


def world(*, types=2, pool="finite", pool_counts=20, held_mM=200.0, membrane=6, impermeant=2,
          permeant=False, entries=None, mu_bilayer=MU_BILAYER, quanta=QUANTA,
          floor_molecules=FLOOR_MOLECULES, c_ext_mM=None):  # fmt: skip
    """One vesicle and its pool: `types` amphiphiles, finite in the pool (`pool_counts` each, an int
    or a list) or held (`held_mM` each); `membrane` molecules of each in the founder; `impermeant`
    molecules of I in the lumen; with `permeant`, S in the pool and the lumen and its entry step;
    `entries` the factor's entries (catalysis()), or none. c_ext is the declared value, or the
    larger of 1000 mM and twice the pool's solutes (§0.2c rule 6 refuses less than their total)."""
    if pool not in ("finite", "held"):
        raise ValueError(f"A pool is finite or held, not {pool!r}")
    amphiphiles = names(types)
    counts = [pool_counts] * types if isinstance(pool_counts, int) else list(pool_counts)
    held = [held_mM] * types if isinstance(held_mM, (int, float)) else list(held_mM)
    founder_m = [membrane] * types if isinstance(membrane, int) else list(membrane)
    mus = [mu_bilayer] * types if isinstance(mu_bilayer, (int, float)) else list(mu_bilayer)
    sizes = [quanta] * types if isinstance(quanta, int) else list(quanta)
    if not len(counts) == len(held) == len(founder_m) == len(mus) == len(sizes) == types:
        raise ValueError("Each per-amphiphile list gives one value per amphiphile")
    species = [
        _species(a, None, solution=0.0, bilayer=float(m))
        for a, m in zip(amphiphiles, mus, strict=True)
    ]
    species.append(_species("I", None, solution=0.0))
    pool_species = []
    founder = {}
    for a, n, c in zip(amphiphiles, counts, held, strict=True):
        if pool == "held":
            pool_species.append({"id": a, "kind": "held", "held_mM": float(c)})
        else:
            pool_species.append({"id": a, "kind": "finite"})
            founder[f"{a}@pool"] = int(n)
    pool_species.append({"id": "I", "kind": "finite"})
    founder["I@pool"] = 0
    lumen = ["I"]
    steps = [
        {"id": f"join_{a}", "locus": "membrane", "reactants": {f"{a}@pool": 1},
         "products": {f"{a}@membrane": 1}, "law": PHASE_EXCHANGE,
         "insertion_velocity_m_per_s": _value(INSERTION)}
        for a in amphiphiles
    ]  # fmt: skip
    if permeant:
        species.append(_species("S", None, solution=0.0))
        pool_species.append({"id": "S", "kind": "finite"})
        lumen.append("S")
        founder["S@pool"] = 4
        steps.append({"id": "entry_S", "locus": "membrane", "reactants": {"S@pool": 1},
                      "products": {"S@lumen": 1}, "law": MEMBRANE_PERMEATION,
                      "permeability_m_per_s": _value(PERMEABILITY)})  # fmt: skip
    for a, m in zip(amphiphiles, founder_m, strict=True):
        founder[f"{a}@membrane"] = int(m)
    founder["I@lumen"] = int(impermeant)
    if permeant:
        founder["S@lumen"] = 0
    finite = sum(v for k, v in founder.items() if k.endswith("@pool"))
    solutes = (sum(held) if pool == "held" else 0.0) + finite / (AVOGADRO * POOL_L) * 1e3
    c_ext = c_ext_mM if c_ext_mM is not None else max(C_EXT_MM, 2.0 * solutes)
    out = {
        "units": {"time": "s", "temperature_K": 296.15, "standard_concentration_mM": 1000.0},
        "conventions": {
            "free_energy_form": "discrete",
            "condensed_measure": "multinomial",
            "membrane_kinetics": "count_on_m",
            "lumen_volume": "osmotic",
            "empty_catalyst_phase": "uncatalysed",
            "last_molecule": "kept",
            "exchange_encounter": "insertion_area",
        },
        "species": species,
        "phases": {
            "pool": {"volume_L": POOL_L, "species": pool_species},
            "membrane": {"species": list(amphiphiles)},
            "lumen": {"species": lumen},
        },
        "steps": steps,
        "free_energy": [
            {"law": IDEAL_MIXING},
            {"law": OSMOTIC_LUMEN, "outside_osmolarity_mM": _value(float(c_ext))},
        ],
        "founder": founder,
        "geometry": {
            "law": BILAYER_GEOMETRY,
            "area_quantum_m2": QUANTUM_M2,
            "area_per_leaflet": {
                a: {"quanta": int(k), "provenance": UNSOURCED}
                for a, k in zip(amphiphiles, sizes, strict=True)
            },
            "vesicle_floor": {"quanta": int(floor_molecules * min(sizes)), "provenance": UNSOURCED},
            "closure_cost_kT": _value(CLOSURE_KT),
            "sigma_max_N_per_m": _value(SIGMA_MAX),
        },
    }
    if entries:
        out["rate_factor"] = {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                              "entries": copy.deepcopy(list(entries))}  # fmt: skip
    return out


def amphiphiles(the_world):
    """H's species set (D245), for a run's provenance: every membrane species of a world built
    here is an amphiphile, since these worlds have no fuel, and so no block or spent form."""
    return list(the_world["phases"]["membrane"]["species"])


def vesicle_places(the_world):
    """The founder's membrane and lumen places, in the world's order."""
    return [k for k in the_world["founder"] if k.endswith("@membrane") or k.endswith("@lumen")]


def population(the_world, founders, slots):
    """The world as `slots` slots on its pool (cells.population.shared_pool@1): the founder keeps the pool and
    every vesicle place 0; `founders` lists each founding vesicle as {place: count} over every
    membrane and lumen place (a missing place is 0)."""
    out = copy.deepcopy(the_world)
    places = vesicle_places(out)
    vesicles = [{p: int(f.get(p, 0)) for p in places} for f in founders]
    for p in places:
        out["founder"][p] = 0
    out["population"] = {"structure": SHARED_POOL, "slots": int(slots), "founders": vesicles}
    return out


def shear(index, *, k=2, times=None, rate=None):
    """A shear schedule: declared times, or a Poisson rate (1/s)."""
    if (times is None) == (rate is None):
        raise ValueError("A shear schedule declares times or a rate")
    out = {"index": int(index), "kind": "shear", "k": int(k)}
    if times is not None:
        out["times_s"] = [float(t) for t in times]
    else:
        out["poisson_rate_per_s"] = float(rate)
    return out


def transfer(index, *, times, keep, fresh):
    """A serial transfer: at each time, keep `keep` assemblies and give the pool `fresh` (one count
    per finite pool place, in the world's pool order)."""
    return {"index": int(index), "kind": "transfer", "times_s": [float(t) for t in times],
            "K_keep": int(keep), "fresh_pool": [int(n) for n in fresh]}  # fmt: skip


def fresh_pool(the_world):
    """The founder's finite pool counts, in the world's pool order (a transfer's default)."""
    pool = the_world["phases"]["pool"]["species"]
    return [int(the_world["founder"][f"{p['id']}@pool"]) for p in pool if p["kind"] == "finite"]


def definition(the_world, *, schedules, horizon, mode="single_lineage", continuation="uniform",
               seed=1, lineage=0, branch=0, molecules=1024, event_limit=10**7, row_every=1000,
               observations=(), trace=True, uniforms=False, chunk=128):  # fmt: skip
    """A definition of `the_world` with shear division: one lineage (its `continuation`, first or
    uniform) or a population (every daughter lives, so no continuation)."""
    if mode not in ("single_lineage", "population"):
        raise ValueError(f"A mode is single_lineage or population, not {mode!r}")
    if (mode == "population") != ("population" in the_world):
        raise ValueError("A population world runs in population mode, and only it")
    w = copy.deepcopy(the_world)
    w["division"] = {"law": SHEAR_FISSION}
    if mode == "single_lineage":
        w["division"]["continuation"] = continuation
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": w},
        "experiment": {
            "time_horizon_s": float(horizon),
            "event_limit": int(event_limit),
            "row_every_events": int(row_every),
            "observation_times_s": [float(t) for t in observations],
            "trace": bool(trace),
            "uniforms": bool(uniforms),
            "schedules": copy.deepcopy(list(schedules)),
        },
        "execution": {
            "backend": "cpu",
            "precision": "float64",
            "mode": mode,
            "stream": {"seed": int(seed), "environment": 0, "lineage": int(lineage),
                       "branch": int(branch)},
            "molecule_capacity": int(molecules),
            "chunk_events": int(chunk),
        },
    }  # fmt: skip


def regular_times(period, count, *, start=None):
    """`count` declared times, one every `period` seconds from `start` (default `period`)."""
    first = period if start is None else start
    return [first + period * i for i in range(count)]


def kept_line(the_world, *, times, gap):
    """D247's induced arm, undriven: a population of two slots whose transfer keeps one vesicle
    right after each shear. Returns (the population world, its schedules).

    Each cycle the one vesicle divides in two (k = 2, into the free slot), and `gap` seconds later a
    transfer keeps one of the two by a uniform draw and removes the other. So the kept vesicles form
    a single lineage with uniform continuation, and population_lines reads it as the only survivor's
    line of descent. Two things differ from a single-lineage world: the two daughters share the pool
    for `gap` seconds, and each transfer replaces the pool with the founder's (its fresh pool). A
    pulse that induces a break comes through FR-20's pool replacement, which works in population
    mode only, once it lands. No fuel step: the world is the one given, undriven or held-amphiphile.
    """
    times = [float(t) for t in times]
    if not gap > 0 or any(t + gap >= u for t, u in zip(times, times[1:], strict=False)):
        raise ValueError("Each transfer falls after its shear and before the next one")
    founder = {p: v for p, v in the_world["founder"].items() if p in vesicle_places(the_world)}
    w = population(the_world, [founder], 2)
    schedules = [
        shear(0, times=times),
        transfer(1, times=[t + gap for t in times], keep=1, fresh=fresh_pool(w)),
    ]
    return w, schedules
