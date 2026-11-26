"""OL6 Protocol G, the GARD limit (docs/OL6_PROTOCOL_G.md; D304): cells.model.assembly_lineages@2's exact
events against @1's, below the fission size, as registered inputs and judged statistics.

The protocol's text is the authority; this module is its registered arithmetic. It builds the
twenty worlds and their definitions in both families, the β plants, the tier-1 pathwise comparison
with its coincidence test on each kernel's own rate arithmetic, tier 2's two-sample statistics, and
the plants' power from @1 alone (computed before the tag; a reading of @1 only, never of @2).

`register` writes protocol_g.json: the registered constants, the worlds as numbers (the generator
below made them, at NumPy's default generator; the numbers are the record) and the plants' power.
Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`:

    python -m validation.assembly_lineages_v2.gard_limit register --out FILE
"""

import argparse
import json
import math
import sys

import numpy as np

C = 8  # molecular types (P1's)
N_SPLIT = 80  # @1's fission size: the first passage to N = 80 by a join ends scope 1's growth
SUM_K_RHO = 100.0  # Σ K_i ρ_i, as P1 draws the worlds
MU, SIGMA = -4.0, 4.0  # GARD's lognormal: β = exp(MU + SIGMA Z)
BIG = 1e5  # one entry, so that @2's factor takes its count-weighted-mean branch (κ > κ_limit)
MATRIX_SEEDS = tuple(range(20261123, 20261123 + 20))  # 16 lognormal, then 4 with one entry BIG
BIG_FROM = 16
TIER1_SEEDS = tuple(range(1, 65))  # 64 stream seeds per world, the same for @1 and @2
TIER2_SEEDS = {"v1": tuple(range(1001, 1257)), "v2": tuple(range(2001, 2257))}  # disjoint, 256
RETRY_SEEDS = {"tier1": tuple(range(3001, 3065)),
               "tier2": {"v1": tuple(range(4001, 4257)), "v2": tuple(range(5001, 5257))}}
GUARD = 40000  # @1's growth event guard (validation/assembly_lineages/worlds.py's)
V1_MOLECULES = 128  # @1's molecule_capacity (>= N_SPLIT)
V2_EVENT_LIMIT = 512  # @2's events in scope 1 (no division): past @1's first fission
V2_MOLECULES = 1024  # >= 9 C + V2_EVENT_LIMIT, so @2 never halts on capacity before the limit
V2_HORIZON = 1.0  # s; @1's first fission comes near 1e-2 (Σ K ρ = 100)
EPS = float(np.finfo(np.float64).eps)
# Rounding between the kernels (protocol §3.2): a rate differs by at most 32 ε (twice P1's 14 ε),
# a0 by that plus the 16-channel fold's 8 ε, a wait by one more ε for its division: 41 ε, so 48.
TIME_ULPS = 48
COINCIDENCE_ULPS = 128  # twice (41 + 1) ε, in ulps of the threshold: a divergence closer is rounding
COINCIDENCES_ALLOWED = 1  # expected about 3e-9 in the whole set (the protocol's §3.2)
Z_TIER2 = 4.5  # tier 2's two-sided threshold, per statistic
Z_POWER = 7.0  # a tier-2 plant must shift a statistic by this many SE: 4.5 + 2.33 (power 99%)
PATH_POWER = 0.99  # the tier-1 plant must make this fraction of each world's seeds diverge
PLANTS = {"tier1": 1.5, "tier2": 4.0}  # the largest β entry times this, in @2 only


# ------------------------------------------------------------------------------------- worlds


def generate(seed, big):
    """One world as P1 draws it (probe_gard_rates.gard_world), plus its founder."""
    rng = np.random.default_rng(seed)
    beta = np.exp(MU + SIGMA * rng.standard_normal((C, C)))
    if big:
        beta[0, 1] = BIG
    kb = rng.uniform(0.5, 2.0, C)
    weights = rng.uniform(0.5, 1.5, C)
    k = rng.uniform(0.5, 5.0, C)
    rho = SUM_K_RHO * weights / np.sum(weights) / k
    founder = rng.integers(1, 10, C)
    return {"matrix_seed": seed, "big_entry": bool(big), "beta": beta.tolist(), "K": k.tolist(),
            "kb": kb.tolist(), "rho": rho.tolist(),
            "founder": [int(x) for x in founder]}  # fmt: skip


def worlds():
    return [generate(s, i >= BIG_FROM) for i, s in enumerate(MATRIX_SEEDS)]


def branch(world):
    """The branch @2's transition-state factor takes for the world's data (its layout's flag):
    `count_weighted_mean` when the data's amplification passes transition_state.kappa_limit."""
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import model

    layout = model.layout(parse_spec(v2_definition(world, 1)))
    return "count_weighted_mean" if bool(np.asarray(layout.factor[2])[0]) else "cached"


def planted(beta, factor):
    """β with its largest entry (the first, in row-major order, at a tie) times `factor`."""
    out = np.array(beta, dtype=np.float64)
    i, j = np.unravel_index(int(np.argmax(out)), out.shape)
    out[i, j] *= factor
    return out.tolist(), (int(i), int(j))


def names():
    return [f"t{i}" for i in range(C)]  # @1's type ids (prefix t, count 8)


def v1_definition(w, seed, *, beta=None, law=None, fissions=1, trace=True, uniforms=False):
    """@1's definition: the claim's law is G1's registered default, pair_consistent@1."""
    from cells.models.assembly_lineages import (CONTINUATION, EXCHANGE_LAW, FISSION,
                                                GARD_PAIR_CONSISTENT, MODEL_ID)  # fmt: skip

    world = {
        "types": {"prefix": "t", "count": C, "transfer_constant": list(w["K"])},
        "supply": list(w["rho"]),
        "exchange": {"law": EXCHANGE_LAW, "leave_rate": list(w["kb"])},
        "law_data": {"catalysis_matrix": beta if beta is not None else w["beta"]},
        "founder": list(w["founder"]),
        "fission": {"operator": FISSION, "size": N_SPLIT,
                    "partition": {"rule": "exact_fraction", "fraction": 0.5}},
        "continuation": {"operator": CONTINUATION, "daughter": "first", "empty": "extinct",
                         "sink": "discard"},
        "units": {"time": "nominal", "temperature_K": None},
    }  # fmt: skip
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world,
                  "rate_factor": {"law": law or GARD_PAIR_CONSISTENT}},
        "experiment": {"fissions": fissions, "growth_event_limit": GUARD, "trace": trace,
                       "uniforms": uniforms},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": seed, "environment": 0, "lineage": 0, "branch": 0},
                      "type_capacity": C, "molecule_capacity": V1_MOLECULES},
    }  # fmt: skip


MEASURES = {  # D215: the exact measure is the claim; the physical one is reported
    "exact": {"condensed_measure": "multinomial_less_one", "last_molecule": "extinct"},
    "physical": {"condensed_measure": "multinomial", "last_molecule": "kept"},
}


def v2_definition(w, seed, *, measure="exact", beta=None, trace=True, uniforms=False):
    """§7.3's configuration in @2 (P1's construction): held pool places at ρ_i (c0 = 1 mM, so
    ln(held/c0) = ln ρ_i), one join per type under mass action at the membrane locus with
    k_f = K_i kb_i, μ°_sol = 0 and μ°_bil = −ln K_i (so k⁻ = kb_i), the transition-state factor
    with ΔΔG‡_ij = log1p(β_ij), ideal mixing, no geometry, a single lineage, no division."""
    from cells.models.assembly_lineages_v2 import (IDEAL_MIXING, MASS_ACTION, MODEL_ID,
                                                   TRANSITION_STATE)  # fmt: skip

    beta = np.array(beta if beta is not None else w["beta"], dtype=np.float64)
    k, kb, rho = w["K"], w["kb"], w["rho"]
    ids = names()
    species = [{"id": s, "moieties": None,
                "standard_mu_RT": {"solution": 0.0, "bilayer": -math.log(k[i])},
                "catalogue": None, "evidence": None} for i, s in enumerate(ids)]  # fmt: skip
    steps = [{"id": f"join_{s}", "locus": "membrane", "reactants": {f"{s}@pool": 1},
              "products": {f"{s}@membrane": 1}, "law": MASS_ACTION,
              "forward_rate_per_s": float(k[i] * kb[i])} for i, s in enumerate(ids)]  # fmt: skip
    entries = [{"catalyst": ids[j], "step": f"join_{ids[i]}", "ddG_kT": math.log1p(beta[i, j])}
               for i in range(C) for j in range(C)]  # fmt: skip
    world = {
        "units": {"time": "s", "temperature_K": 298.15, "standard_concentration_mM": 1.0},
        "conventions": {"free_energy_form": "discrete", "membrane_kinetics": "count_on_m",
                        "lumen_volume": "declared", "empty_catalyst_phase": "uncatalysed",
                        **MEASURES[measure]},
        "species": species,
        "phases": {"pool": {"volume_L": 1e-21, "species": [
            {"id": s, "kind": "held", "held_mM": float(rho[i])} for i, s in enumerate(ids)]},
                   "membrane": {"species": ids}},
        "steps": steps,
        "free_energy": [{"law": IDEAL_MIXING}],
        "rate_factor": {"law": TRANSITION_STATE, "catalysing_phase": "membrane",
                        "entries": entries},
        "founder": {f"{s}@membrane": int(w["founder"][i]) for i, s in enumerate(ids)},
    }  # fmt: skip
    return {
        "schema_version": 1,
        "model": {"id": MODEL_ID, "world": world},
        "experiment": {"time_horizon_s": V2_HORIZON, "event_limit": V2_EVENT_LIMIT,
                       "row_every_events": V2_EVENT_LIMIT, "observation_times_s": [],
                       "trace": trace, "uniforms": uniforms},
        "execution": {"backend": "cpu", "precision": "float64", "mode": "single_lineage",
                      "stream": {"seed": seed, "environment": 0, "lineage": 0, "branch": 0},
                      "molecule_capacity": V2_MOLECULES, "place_capacity": 2 * C,
                      "step_capacity": C},
    }  # fmt: skip


# ------------------------------------------------------------- the first growth, from a trace


def first_growth(founder, codes, times):
    """The events up to and including the first join that brings N to N_SPLIT (@1's fission
    trigger; in @2's scope-1 runs, the same first passage). Codes are both families' signed
    channels: +(i+1) the join of type i, −(i+1) its leave (the channel map is the identity)."""
    counts = np.array(founder, dtype=np.int64)
    for k, code in enumerate(codes):
        i = abs(int(code)) - 1
        counts[i] += 1 if code > 0 else -1
        if code > 0 and counts.sum() == N_SPLIT:
            return k + 1, counts, float(times[k])
    return None, counts, None  # never reached: censored


def time_bound(k, t):
    """|t2(k) − t1(k)| allowed at event k (1-based): a wait's rounding difference (TIME_ULPS ε)
    plus one ulp per accumulated addition (k ε), relative to t."""
    return (TIME_ULPS + k) * EPS * abs(t)


def pathwise(codes1, times1, codes2, times2, k1):
    """Tier 1 on one seed, over @1's first growth (k1 events): the first index where the channel
    codes differ (None if none), and the largest time gap in units of its bound."""
    n = min(k1, len(codes2))
    a, b = np.asarray(codes1[:n]), np.asarray(codes2[:n])
    differ = np.flatnonzero(a != b)
    first = int(differ[0]) if differ.size else (None if len(codes2) >= k1 else n)
    upto = n if first is None else first
    ratio = 0.0
    for k in range(upto):
        bound = time_bound(k + 1, times1[k])
        ratio = max(ratio, float(abs(times2[k] - times1[k]) / bound) if bound > 0 else math.inf)
    return {"divergence": first, "events": int(k1), "time_ratio": ratio}


def v1_prefix(spec, counts):
    """@1's partial totals at a state, by its kernel's own functions (kernel.rates, the law's
    state and folds.prefix), on the host."""
    from cells.models.assembly_lineages import folds, kernel, model

    structure, layout = model.structure(spec), model.layout(spec)
    law = kernel.rate_factor(structure)
    padded = np.zeros(structure.capacity, dtype=np.float64)
    padded[: len(counts)] = counts
    state = () if law is None else law.state(padded, layout.factor, np)
    rates = kernel.rates(padded, np.float64(padded.sum()), layout, state, law, xp=np)
    return folds.prefix(np.asarray(rates), np)


def v2_prefix(spec, counts):
    """@2's partial totals at a state: the kernel's host log rates (balance.host_log_rates),
    exponentiated, folded by folds.prefix."""
    from cells.models.assembly_lineages import folds
    from cells.models.assembly_lineages_v2 import balance, model

    structure, layout = model.structure(spec), model.layout(spec)
    world = spec.model.world
    full = np.zeros(structure.places, dtype=np.int64)
    membrane = [i for i, p in enumerate(world.places) if p.phase == "membrane"]
    full[membrane] = counts
    return folds.prefix(np.exp(balance.host_log_rates(full, layout, structure)), np)


def near_boundary(prefix, u2):
    """Whether the kernel's threshold min(u2 a0, nextafter(a0, 0)) lies within COINCIDENCE_ULPS of
    one of its partial totals."""
    prefix = np.asarray(prefix, dtype=np.float64)
    total = prefix[-1]
    threshold = min(u2 * total, np.nextafter(total, 0.0))
    return bool(np.min(np.abs(prefix - threshold)) <= COINCIDENCE_ULPS * np.spacing(threshold))


def coincidence(spec1, spec2, founder, codes, k, u2):
    """A divergence at event k (0-based) is a threshold coincidence when u2 a0 lies within
    COINCIDENCE_ULPS of a partial total in either kernel, at the state both reached before it."""
    counts = np.array(founder, dtype=np.int64)
    for code in codes[:k]:
        counts[abs(int(code)) - 1] += 1 if code > 0 else -1
    return near_boundary(v1_prefix(spec1, counts), u2) or near_boundary(
        v2_prefix(spec2, counts), u2
    )


# ------------------------------------------------------------------------------------ tier 2


def statistics(founder, traces):
    """Per seed: the time of the first passage to N_SPLIT and the counts there (tier 2's nine
    statistics); a censored seed (no passage) is counted apart."""
    times, counts, censored = [], [], 0
    for codes, event_times in traces:
        k, c, t = first_growth(founder, codes, event_times)
        if k is None:
            censored += 1
            continue
        times.append(t)
        counts.append(c)
    return np.asarray(times), np.asarray(counts, dtype=np.float64), censored


def two_sample(x, y):
    """z of mean(y) − mean(x), with the two samples' standard errors."""
    se = math.sqrt(np.var(x, ddof=1) / len(x) + np.var(y, ddof=1) / len(y))
    diff = float(np.mean(y) - np.mean(x))
    return diff / se if se > 0 else (0.0 if diff == 0 else math.inf)


def tier2_z(founder, traces_v1, traces_v2):
    """Tier 2's nine z values (time, then the eight counts at the first passage)."""
    t1, c1, cens1 = statistics(founder, traces_v1)
    t2, c2, cens2 = statistics(founder, traces_v2)
    z = [two_sample(t1, t2)] + [two_sample(c1[:, i], c2[:, i]) for i in range(C)]
    return {"z": [float(v) for v in z], "censored": [int(cens1), int(cens2)]}


# ----------------------------------------------------------------- the plants' power (@1 alone)


def _traces(definitions):
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import runner

    specs = [parse_spec(d) for d in definitions]
    runs = runner.run_lanes(specs)
    return [(r.trace["event_channel"], r.trace["event_time"]) for r in runs]


def power(world):
    """Both plants' power for one world, from @1 alone: the tier-1 plant (×1.5) by the fraction of
    TIER1_SEEDS whose first growth fails tier 1 against the unplanted run's (a channel divergence,
    or an event time beyond its bound before any divergence); the tier-2 plant (×4) by the
    largest |z| of tier 2's statistics between unplanted (TIER2 v1 seeds) and planted (v2 seeds)."""
    out = {}
    beta15, at15 = planted(world["beta"], PLANTS["tier1"])
    honest = _traces([v1_definition(world, s) for s in TIER1_SEEDS])
    plant = _traces([v1_definition(world, s, beta=beta15) for s in TIER1_SEEDS])
    channels = times = failed = 0
    for (c1, t1), (c2, t2) in zip(honest, plant, strict=True):
        k1, _, _ = first_growth(world["founder"], c1, t1)
        result = pathwise(c1, t1, c2, t2, k1)
        channel = result["divergence"] is not None
        late = bool(result["time_ratio"] > 1.0)  # over the events before any divergence
        channels += channel
        times += late
        failed += channel or late
    out["tier1"] = {"entry": at15, "factor": PLANTS["tier1"], "seeds": len(TIER1_SEEDS),
                    "channels_diverge": channels, "times_beyond_bound": times,
                    "fails_tier1": failed, "fraction": failed / len(TIER1_SEEDS),
                    "required": PATH_POWER}  # fmt: skip
    beta4, at4 = planted(world["beta"], PLANTS["tier2"])
    honest = _traces([v1_definition(world, s) for s in TIER2_SEEDS["v1"]])
    plant = _traces([v1_definition(world, s, beta=beta4) for s in TIER2_SEEDS["v2"]])
    z = tier2_z(world["founder"], honest, plant)
    out["tier2"] = {"entry": at4, "factor": PLANTS["tier2"], "seeds": len(TIER2_SEEDS["v1"]),
                    "z": z["z"], "censored": z["censored"],
                    "largest_abs_z": float(np.max(np.abs(z["z"]))), "required": Z_POWER}  # fmt: skip
    return out


SCOPE2_FISSIONS = 50
SCOPE2_AT = (1, SCOPE2_FISSIONS)  # scope 2's tier-2 statistics: at these fissions


def v1_at_fission(founder, run, g):
    """@1's parent at its g-th fission (1-based): its time and its counts, by replaying the trace
    growth by growth, each growth continuing from the followed (first) daughter's composition."""
    codes, times = run.trace["event_channel"], run.trace["event_time"]
    per_growth = np.asarray(run.trace["events_per_growth"], dtype=np.int64)
    split = np.asarray(run.fissions["fission_split"], dtype=np.int64)
    counts, at = np.array(founder, dtype=np.int64), 0
    for growth in range(g):
        for code in codes[at : at + per_growth[growth]]:
            counts[abs(int(code)) - 1] += 1 if code > 0 else -1
        at += per_growth[growth]
        if growth == g - 1:
            return float(times[at - 1]), counts
        counts = split[growth].copy()  # continuation `first`: the first daughter
    raise ValueError("the run did not reach that fission")


def power_scope2(world):
    """G-P2's power in scope 2, from @1 alone: tier 2's statistics at the first and the 50th
    fission (SCOPE2_AT) between unplanted @1 (tier 2's @1 seeds) and @1 with the largest entry × 4
    (its @2 seeds), from the same runs through 50 fissions."""
    import jax

    jax.config.update("jax_enable_x64", True)
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import runner

    beta4, at4 = planted(world["beta"], PLANTS["tier2"])
    sides = []
    for seeds, beta in ((TIER2_SEEDS["v1"], None), (TIER2_SEEDS["v2"], beta4)):
        specs = [parse_spec(v1_definition(world, s, beta=beta, fissions=SCOPE2_FISSIONS))
                 for s in seeds]  # fmt: skip
        runs = runner.run_lanes(specs)
        sides.append({g: [v1_at_fission(world["founder"], r, g) for r in runs] for g in SCOPE2_AT})
    out = {"entry": at4, "factor": PLANTS["tier2"], "seeds": len(TIER2_SEEDS["v1"]),
           "required": Z_POWER, "at_fission": {}}  # fmt: skip
    for g in SCOPE2_AT:
        (t1, c1), (t2, c2) = ((np.asarray([t for t, _ in side[g]]),
                               np.asarray([c for _, c in side[g]], dtype=np.float64))
                              for side in sides)  # fmt: skip
        z = [two_sample(t1, t2)] + [two_sample(c1[:, i], c2[:, i]) for i in range(C)]
        out["at_fission"][str(g)] = {"z": [float(v) for v in z],
                                     "largest_abs_z": float(np.max(np.abs(z)))}  # fmt: skip
    out["largest_abs_z"] = max(v["largest_abs_z"] for v in out["at_fission"].values())
    return out


def header():
    """The record's statement of what it is (protocol_models.py reads `status`)."""
    from cells.models.assembly_lineages import (CONTINUATION, EXCHANGE_LAW, FISSION,
                                                GARD_PAIR_CONSISTENT, GARD_PAIR_CONSISTENT_V2,
                                                MODEL_ID as V1)  # fmt: skip
    from cells.models.assembly_lineages_v2 import (IDEAL_MIXING, MASS_ACTION, MODEL_ID as V2,
                                                   TRANSITION_STATE)  # fmt: skip

    return {
        "kind": "cells.ol6.protocol_g@1",
        "status": "proposed for registration: tag ol6-protocol-g-registered-2026-11-23, before any "
        "comparison of @2's exact events with @1's",
        "document": "docs/OL6_PROTOCOL_G.md",
        "engine_models": {"v1": [V1, EXCHANGE_LAW, GARD_PAIR_CONSISTENT, FISSION, CONTINUATION],
                          "v1_reported_beside": [GARD_PAIR_CONSISTENT_V2],
                          "v2": [V2, MASS_ACTION, TRANSITION_STATE, IDEAL_MIXING],
                          "v2_scope2_adds": ["cells.operator.size_threshold_division@1"]},
        "not_blind": "P1 (the previous owner's desk probe) compared @1's and @2's rates at 4,000 "
        "random states (3.1e-15, 13% bitwise, 0 of 256,000 selections differ) and sized tier 1's "
        "bounds; the author ran @1 alone for the plants' power (seeds 1-64 unplanted and x1.5; "
        "1001-1256 unplanted and 2001-2256 x4, to the first fission and to the 50th), so @1's side "
        "of both tiers has been run, only its summaries printed; @2 was parsed only (every "
        "definition, measure and plant, and its layout's branch), and drew no event",
    }


def constants():
    return {
        "types": C, "fission_size": N_SPLIT, "sum_K_rho": SUM_K_RHO,
        "beta": {"mu": MU, "sigma": SIGMA, "big_entry": BIG, "big_at": [0, 1],
                 "big_from_world": BIG_FROM},
        "matrix_seeds": list(MATRIX_SEEDS), "generator": "numpy.random.default_rng(seed): "
        "standard_normal((8, 8)), then uniform(0.5, 2, 8) for kb, uniform(0.5, 1.5, 8) for the "
        "weights, uniform(0.5, 5, 8) for K, rho = 100 w / sum(w) / K, integers(1, 10, 8) for the "
        "founder (P1's draw, probe_gard_rates.gard_world); the recorded numbers are the record",
        "seeds": {"tier1": list(TIER1_SEEDS), "tier2": {k: list(v) for k, v in
                                                       TIER2_SEEDS.items()},
                  "retry": {"tier1": list(RETRY_SEEDS["tier1"]),
                            "tier2": {k: list(v) for k, v in RETRY_SEEDS["tier2"].items()}}},
        "v1": {"molecule_capacity": V1_MOLECULES, "growth_event_limit": GUARD, "fissions": 1},
        "v2": {"event_limit": V2_EVENT_LIMIT, "molecule_capacity": V2_MOLECULES,
               "time_horizon_s": V2_HORIZON},
        "tier1": {"time_bound": "(TIME_ULPS + k) * eps * |t1(k)|, k the 1-based event index",
                  "time_ulps": TIME_ULPS, "eps": EPS, "coincidence_ulps": COINCIDENCE_ULPS,
                  "coincidences_allowed": COINCIDENCES_ALLOWED},
        "tier2": {"z": Z_TIER2, "fail_z": 6.0, "statistics": "scope 1: the time of the first "
                  "passage to N = 80 by a join, and the count of each type there, nine per world; "
                  "scope 2: the same at the first and the 50th fission, eighteen per world",
                  "scope2_at_fissions": list(SCOPE2_AT)},
        "plants": {"tier1": {"factor": PLANTS["tier1"], "power": PATH_POWER},
                   "tier2": {"factor": PLANTS["tier2"], "power_z": Z_POWER}},
    }  # fmt: skip


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    reg = sub.add_parser("register", help="write the registered inputs and the plants' power")
    reg.add_argument("--out", required=True)
    reg.add_argument("--worlds-only", action="store_true")
    args = parser.parse_args(argv)
    ws = worlds()
    for w in ws:
        w["branch"] = branch(w)
    doc = {**header(), "constants": constants(), "worlds": ws}
    if not args.worlds_only:
        doc["power"] = [power(w) for w in ws]
        for row, w in zip(doc["power"], ws, strict=True):
            row["scope2_tier2"] = power_scope2(w)
    with open(args.out, "w") as handle:
        json.dump(doc, handle, indent=1)
        handle.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
