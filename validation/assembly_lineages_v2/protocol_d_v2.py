"""OL6 Protocol D, version 2: the re-registration's arithmetic (docs/OL6_PROTOCOL_D_V2.md; D318,
D323's R12, D334).

The document is the authority; this module is its registered arithmetic, tagged with it. It judges
with limit_qualification's registered functions (the worlds, the definitions, the reader, the
scales, mean_error, P, B, E, n_min and the plants) and with agreement.py's shared rule, and adds:
- **the seeds,** fresh, disjoint from every earlier range (`SEEDS`, `seeds`, `EARLIER_SEEDS`);
- **the classification of every pair M reads, from the model before any run** (`classify`): a
  pair is `constant` where the model holds every exact replica at one value, and `spread`
  elsewhere; no pair of D0-D7 is `derived`;
- **M repaired by the shared rule** (`criterion_m`): a constant pair by agreement.judge_constant,
  every exact replica and (d)'s value bit for bit against the model's value; a spread pair by the
  registered excess on `moments`, with the registered inequality evaluated exactly where the
  combined SE is 0, so that no zero SE is taken as no limit and no rounding floor is declared;
- **the constant pairs' precondition, judged first** (`floppy_margins`, `precondition`,
  `judge_world`): every vesicle the classification calls floppy is floppy in every exact replica
  and in (d) at that time, recomputed from each run's recorded counts; where it fails the pair is
  not judged and the world is inconclusive, with its tense runs counted;
- **the linear-noise variance of each floppy margin** (`linear_noise`, `noise_table`): the
  model's prediction, before any run, that no replica turns tense at a constant pair;
- **P-D8** (`pd8`): the constant rule's plant, one ulp in (d) alone on D6;
- **its checks** (`check`): the reader on invented inputs, M and the world's verdict on made-up
  columns, the zero-SE path on the registered constants, the classification, the seeds and the
  parse of every registered definition.

Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`:
- `python -m validation.assembly_lineages_v2.protocol_d_v2 check` runs the checks, on invented
  inputs and made-up columns only, and parses the registered definitions (it runs no world);
- `python -m validation.assembly_lineages_v2.protocol_d_v2 noise --out FILE` runs (d) alone on D5
  and D6 at every rung and writes the linear-noise table (the document's §4.3; a few minutes);
- `python -m validation.assembly_lineages_v2.protocol_d_v2 register --margins FILE --out FILE
  --noise FILE` writes protocol_d_v2.json from (d)'s margins and that table.
"""

import json
import math
import sys
from types import SimpleNamespace

import numpy as np

from validation.assembly_lineages_v2 import agreement
from validation.assembly_lineages_v2 import limit_qualification as lq

CONSTANT, DERIVED, SPREAD = agreement.CONSTANT, agreement.DERIVED, agreement.SPREAD

# ------------------------------------------------------------------ the seeds (the document's §3)

SEEDS = {"first": 670001, "retry": 690001}  # seeds base .. base + M - 1, environment 0
EARLIER_SEEDS = (  # every stream seed range registered, used or probed before this registration
    ("Protocol D, first seeds", 1, 256),
    ("Protocol D, retry seeds", 100001, 100256),
    ("Protocol G, seeds (@1 1001-1256 and @2 2001-2256 among them)", 1, 5256),
    ("Protocol G, matrix seeds", 20261123, 20261142),
    ("Protocol G's checker, timing smokes (unregistered, '900001+', no upper end recorded)",
     900001, None),
    ("FR-47, first seeds (W1, W1D, W2's rungs, P7, P8)", 470001, 471528),
    ("FR-47, retry seeds (W2's: the first plus 500,000)", 970001, 971528),
    ("the probes' and smokes' stream seeds, 1 and 7", 1, 7),
    ("D2's beta generator seed (a world input, kept)", 20261124, 20261124),
    ("this registration's first seeds as proposed at dbf17e84, withdrawn: the D7 clock-room "
     "probe ran D7's (d) on 640001-640128", 640001, 640256),
    ("this registration's retry seeds as proposed at dbf17e84, withdrawn (never run)",
     740001, 740256),
    ("the noise check: exact events on an unregistered 12.5 nm D5, seeds 1-128", 1, 128),
)  # fmt: skip


def seeds(name, which="first"):
    """The M seeds of one world: SEEDS[which] + 0 .. M - 1, M = lq.REPLICAS by family."""
    m = lq.REPLICAS["D0"] if name == "D0" else lq.REPLICAS[lq.family(name)]
    return list(range(SEEDS[which], SEEDS[which] + m))


def seeds_disjoint():
    """(ok, overlaps): every seed of every world and both sets against EARLIER_SEEDS (an upper end
    None is open)."""
    used = set()
    for name in ("D0", *lq.DENSITY, *lq.VESICLE):
        for which in SEEDS:
            used |= set(seeds(name, which))
    overlaps = [(label, lo, hi) for label, lo, hi in EARLIER_SEEDS
                if any(lo <= s and (hi is None or s <= hi) for s in used)]  # fmt: skip
    return not overlaps, overlaps


# ------------------------------------------------------------------ the classification (§4)

M_WORLDS = ("D1", "D2", "D3", "D4", "D5", "D6")  # M reads them; D0 has one size, D7 E only
DERIVED_KEYS = ("A_m2", "V_L", "sigma_N_per_m")


def _vesicles(world):
    """[(prefix, slot)] of the world's vesicles as the reader names them: ("", None) for a single
    lineage, (f"slot{k}:", k) for each population slot."""
    if world.geometry is None:
        return []
    if world.population is None:
        return [("", None)]
    return [(f"slot{k}:", k) for k in range(world.population["slots"])]


def reader_keys(world):
    """The observables the registered reader (lq.observables) gives for this world, from the model
    alone, in its order: the enveloped places (a population's pool places, then each slot's
    others), each vesicle's A, V and σ, and W_res where a step reads a held place (the reader
    adds it where the reservoir's work is nonzero, which a step on a held place makes it)."""
    places = [p.name for p in world.places]
    pool = {i for i, p in enumerate(world.places) if p.phase == "pool"}
    keys = []
    if world.population is None:
        keys += [places[i] for i in lq.enveloped(world)]
        if world.geometry is not None:
            keys += list(DERIVED_KEYS)
    else:
        keys += [places[i] for i in lq.enveloped(world) if i in pool]
        for prefix, _ in _vesicles(world):
            keys += [f"{prefix}{places[i]}" for i in lq.enveloped(world) if i not in pool]
            keys += [f"{prefix}{k}" for k in DERIVED_KEYS]
    if held_read(world):
        keys.append("W_res_kT")
    return keys


def held_read(world):
    """Whether a step reads a held place (so the reservoir does work)."""
    names = [name for step in world.steps for name, _ in (*step.reactants, *step.products)]
    return any(world.places[world.place_index(name)].held for name in names)


def lumen_moved_by_a_step(world):
    """Whether any step has a lumen place among its reactants or products (a permeant)."""
    names = [name for step in world.steps for name, _ in (*step.reactants, *step.products)]
    return any(world.places[world.place_index(name)].phase == "lumen" for name in names)


def first_operator_time(name):
    """The first time an operator acts on a vesicle's places: D6's shear; None elsewhere."""
    return lq.D6["shear_s"] if name == "D6" else None


def classify(name, rung, floppy):
    """({key: [class per registered time]}, {key: [the constant's value, or None]}) for one
    world and rung, from the model before any run.

    `floppy` is {vesicle prefix: [bool per registered time]}: (d)'s vesicle is floppy there, from
    (d)'s registered margins (protocol_d_v2.json; the document's §4.3). The rules (§4.1):
    - a vesicle's σ is constant, 0.0, at a time where no step moves its lumen and (d) has it
      floppy: tension is exactly 0.0 while floppy;
    - its V is constant at such a time when, besides, no operator has acted on the vesicle yet:
      its lumen count is then the founder's, and while floppy V = V_osm(N_L) reads N_L alone
      (lumen.log_volume's minimum returns ln V_osm's bits). The value is the reader's own
      function at the founder, lq.vesicle_derived;
    - every other pair is spread: each count is moved by a step, each A reads a footprint the
      exchange moves, W_res is a stochastic integral. No pair is derived."""
    spec = _parse(name, rung, False)
    world = spec.model.world
    times = list(lq.times_of(name, rung))
    keys = reader_keys(world)
    classes = {k: [SPREAD] * len(times) for k in keys}
    values = {k: [None] * len(times) for k in keys}
    if world.geometry is None or lumen_moved_by_a_step(world):
        return classes, values
    shear = first_operator_time(name)
    founder = _founder_states(spec)
    for prefix, slot in _vesicles(world):
        derived = lq.vesicle_derived(world, founder[slot])
        for j, t in enumerate(times):
            if not floppy[prefix][j]:
                continue
            classes[f"{prefix}sigma_N_per_m"][j] = CONSTANT
            values[f"{prefix}sigma_N_per_m"][j] = 0.0
            if shear is None or t < shear:
                classes[f"{prefix}V_L"][j] = CONSTANT
                values[f"{prefix}V_L"][j] = derived["V_L"]
    return classes, values


def _parse(name, rung, representation, seed=1):
    from cells.definitions.specs import parse_spec

    return parse_spec(lq.definition(name, rung, seed, representation))


def _founder_states(spec):
    """{slot: counts} as the reader passes them to vesicle_derived at the founder: the whole
    founder for a single lineage (key None), each slot's own counts for a population."""
    world = spec.model.world
    founder = np.asarray(world.founder, dtype=np.float64)
    if world.population is None:
        return {None: founder}
    out = {}
    for k, slot in enumerate(world.population["founders"]):
        out[k] = np.asarray(slot, dtype=np.float64) + founder * 0
    return out


def constant_pairs(classes):
    """{key: [time index]} of the constant pairs."""
    out = {}
    for k, row in classes.items():
        hits = [j for j, c in enumerate(row) if c == CONSTANT]
        if hits:
            out[k] = hits
    return out


# ------------------------------------------------------------------ M, repaired (§5)


def spread_excess(e_k, se_k, e_b, se_b):
    """The registered excess, (|e_K| - |e_(K-1)|/2)/(SE_K² + SE_(K-1)²/4)^½, with the registered
    inequality evaluated exactly where the combined SE is 0: -inf where it holds (|e_K| at most
    |e_(K-1)|/2) and +inf where it does not. NaN where a term is NaN (a time after a run's end),
    so it enters no maximum, as registered."""
    e_k, se_k = np.asarray(e_k, dtype=np.float64), np.asarray(se_k, dtype=np.float64)
    e_b, se_b = np.asarray(e_b, dtype=np.float64), np.asarray(se_b, dtype=np.float64)
    combined = np.sqrt(se_k**2 + se_b**2 / 4.0)
    num = np.abs(e_k) - np.abs(e_b) / 2.0
    with np.errstate(divide="ignore", invalid="ignore"):
        ratio = num / np.where(combined > 0, combined, 1.0)
    exact = np.where(num <= 0, -np.inf, np.inf)
    out = np.where(combined > 0, ratio, exact)
    return np.where(np.isnan(combined) | np.isnan(num), np.nan, out)


def moments(exact, d):
    """e and SE per (observable, time), as the registered lq.mean_error gives them, except where at
    least two replicas are finite and every finite replica holds one value bit for bit. There e is
    that value minus y_d, one subtraction, and SE is 0, so the zero-SE path judges the pair
    exactly: identical replicas at (d)'s bits hold the inequality, and off them it decides. The
    registered sum leaves its rounding residue r there instead, SE = |r|/√(m − 1) and
    z = ±√(m − 1) (§1); the check finds it at the registered constants (§8)."""
    out = lq.mean_error(exact, d)
    for k, (e, se) in out.items():
        values = np.asarray(exact[k], dtype=np.float64)
        e, se = np.array(e, dtype=np.float64), np.array(se, dtype=np.float64)
        for j in range(values.shape[1]):
            column = values[:, j][np.isfinite(values[:, j])]
            if column.size >= 2 and np.all(column.view(np.uint64) == column[0:1].view(np.uint64)):
                e[j] = column[0] - np.float64(d[k][j])
                se[j] = 0.0
        out[k] = (e, se)
    return out


UNJUDGED = "unjudged"  # a constant pair where §6's precondition fails (judge_world): not judged


def _judge_constant(values, d_value, expected):
    """One constant pair at one rung: agreement.judge_constant on the exact replicas, and (d)'s
    value bit for bit; a NaN anywhere is not the constant."""
    replicas = agreement.judge_constant(values, expected)
    d_ok = bool(np.float64(d_value).view(np.uint64) == np.float64(expected).view(np.uint64))
    return {**replicas, "d_matches": d_ok, "passes": replicas["passes"] and d_ok,
            "fails": replicas["fails"] or not d_ok}  # fmt: skip


def criterion_m(exact_top, d_top, exact_below, d_below, classes_top, values_top, classes_below,
                values_below):  # fmt: skip
    """M at the top rung K against K - 1, each rung's observables as lq.observables gives them
    ({key: [M, T]} and {key: [T]}), with each rung's own classes and constants from `classify`
    (a V constant's value differs between rungs, so both are required).

    - A pair constant at K is judged by the constant rule at K, and at K - 1 where it is constant
      there too; it is not in the z. One replica off, or (d) off, fails M.
    - Every other pair is spread: `moments` at both rungs and `spread_excess`; the largest z
      passes at most lq.Z_STAR and fails beyond lq.Z_FAIL. Identical replicas are not excluded:
      they are judged exactly.
    - A pair marked UNJUDGED (judge_world, where §6's precondition fails) is in neither.
    - M passes when every constant pair passes and the largest z passes; it fails when a constant
      pair fails or the largest z fails; it is inconclusive otherwise. With no spread pair the
      largest z is -inf."""
    top, below = moments(exact_top, d_top), moments(exact_below, d_below)
    worst, judged, constants, failed = -np.inf, 0, {}, []
    for key, (e_k, se_k) in top.items():
        row = classes_top.get(key)
        if row is None:
            raise ValueError(f"M: the observable {key!r} has no class (classify before the run)")
        e_b, se_b = below[key]
        spread = np.asarray([c == SPREAD for c in row])
        if spread.any():
            excess = spread_excess(e_k[spread], se_k[spread], e_b[spread], se_b[spread])
            if np.any(np.isfinite(excess) | np.isinf(excess)):
                worst = max(worst, float(np.nanmax(excess)))
            judged += int(spread.sum())
        for j, c in enumerate(row):
            if c == DERIVED:
                raise ValueError("no pair of D0-D7 is derived (the document's §4.2)")
            if c != CONSTANT:
                continue
            verdicts = [_judge_constant(exact_top[key][:, j], d_top[key][j], values_top[key][j])]
            if classes_below[key][j] == CONSTANT:
                verdicts.append(_judge_constant(exact_below[key][:, j], d_below[key][j],
                                                values_below[key][j]))  # fmt: skip
            constants[f"{key}@{j}"] = verdicts
            if any(v["fails"] for v in verdicts):
                failed.append(f"{key}@{j}")
    constants_pass = not failed
    return {"largest_z": worst, "pairs_spread": judged, "pairs_constant": len(constants),
            "constant_failures": failed, "constants": constants,
            "passes": constants_pass and worst <= lq.Z_STAR,
            "fails": (not constants_pass) or worst > lq.Z_FAIL}  # fmt: skip


# ------------------------------------------------------------------ the precondition (§6)


def floppy_margins(spec, run, representation):
    """{vesicle prefix: [ln V_sph - ln V_osm per registered time]} of one run, read from its rows
    as lq.observables reads them (NaN after the run's end); positive where floppy. It recomputes
    floppiness from the recorded counts alone: N_L and W from each row's counts, then the engine's
    own lumen.log_branches. It reads no σ, no V and no flag of the run, so a wrong replica cannot
    read as floppy, and a tense one cannot read as floppy by a wrong σ."""
    from cells.models.assembly_lineages_v2 import geometry, lumen

    world = spec.model.world
    times = np.asarray(spec.experiment.observation_times_s, dtype=np.float64)
    t, observed, pool, slots, _ = lq._rows(run, representation)
    t_obs = np.asarray(t)[observed]
    is_lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.float64)
    quanta = geometry.place_quanta(world, len(world.places)).astype(np.float64)
    c = np.asarray(lumen.constants(world))
    states = {}
    if slots is None:
        states[""] = np.asarray(pool, dtype=np.float64)[observed][:, : len(world.places)]
    else:
        slots = np.asarray(slots, dtype=np.float64)[observed]
        for k in range(slots.shape[1]):
            states[f"slot{k}:"] = slots[:, k, : len(world.places)]
    out = {}
    for prefix, counts in states.items():
        log_osm, log_sph = lumen.log_branches(counts @ is_lumen, counts @ quanta, c, np)
        margin = np.asarray(log_sph - log_osm, dtype=np.float64)
        full = np.full(len(times), np.nan)
        for j, tj in enumerate(times):
            hit = np.flatnonzero(t_obs == tj)
            if hit.size:
                full[j] = margin[hit[0]]
        out[prefix] = full
    return out


def precondition(classes, margins_by_run):
    """The constant pairs' precondition, at each rung M reads: at every time of a constant pair,
    no run's vesicle (each exact replica and (d), `margins_by_run` a list of floppy_margins) is
    tense by its recorded counts, a finite margin at or below 0. A run with no row at a time (it
    ended before it, NaN) has no counts there: it is not called tense, its pairs stay judged, and
    its missing value is not the constant (§5), as the first registration fails a censored
    replica. Returns {"holds", "violations": [(vesicle, time index, run index)]}."""
    times = {}
    for key, row in classes.items():
        prefix = key.split(":")[0] + ":" if ":" in key else ""
        for j, c in enumerate(row):
            if c == CONSTANT:
                times.setdefault(prefix, set()).add(j)
    bad = []
    for r, margins in enumerate(margins_by_run):
        for prefix, js in times.items():
            for j in sorted(js):
                m = margins[prefix][j]
                if np.isfinite(m) and not m > 0:
                    bad.append((prefix, j, r))
    return {"holds": not bad, "violations": bad}


def judge_world(exact_top, d_top, exact_below, d_below, classes_top, values_top, classes_below,
                values_below, margins_top, margins_below):  # fmt: skip
    """One world's M with §6's precondition judged first. `margins_top` and `margins_below` hold
    each rung's floppy_margins, one per exact replica in seed order, then (d)'s.

    - At each rung, a constant pair at a time where any run's vesicle is tense by its recorded
      counts (`precondition`) is marked UNJUDGED: neither the constant rule nor the z sees it, so
      a tense replica can never fail or pass it. A run with no row there is not tense: its
      missing value meets the constant rule.
    - The world **fails** when M fails on what is judged (a judged constant pair, or the z beyond
      lq.Z_FAIL). Otherwise it is **inconclusive** when the precondition fails anywhere or M is
      inconclusive. Otherwise it **passes**.
    - `tense` per rung: the runs with a vesicle tense at a constant time (exact replicas and
      whether (d)), and the count of such runs at each (vesicle, time index)."""
    judged, rungs = [], {}
    for label, classes, margins in (("top", classes_top, margins_top),
                                    ("below", classes_below, margins_below)):  # fmt: skip
        pre = precondition(classes, margins)
        bad = {}
        for prefix, j, _ in pre["violations"]:
            bad.setdefault(prefix, set()).add(j)
        marked = {}
        for key, row in classes.items():
            prefix = key.split(":")[0] + ":" if ":" in key else ""
            marked[key] = [UNJUDGED if c == CONSTANT and j in bad.get(prefix, ()) else c
                           for j, c in enumerate(row)]  # fmt: skip
        judged.append(marked)
        runs = {r for _, _, r in pre["violations"]}
        d_index = len(margins) - 1
        by_time = {}
        for prefix, j, _ in pre["violations"]:
            by_time[f"{prefix}{j}"] = by_time.get(f"{prefix}{j}", 0) + 1
        rungs[label] = {"holds": pre["holds"], "violations": pre["violations"],
                        "tense": {"exact_replicas": len(runs - {d_index}),
                                  "d": d_index in runs, "by_vesicle_time": by_time},
                        "unjudged": sorted(f"{k}@{j}" for k, row in marked.items()
                                           for j, c in enumerate(row) if c == UNJUDGED)}  # fmt: skip
    m = criterion_m(exact_top, d_top, exact_below, d_below, judged[0], values_top, judged[1],
                    values_below)  # fmt: skip
    holds = rungs["top"]["holds"] and rungs["below"]["holds"]
    if m["fails"]:
        verdict = "fail"
    elif not holds or not m["passes"]:
        verdict = "inconclusive"
    else:
        verdict = "pass"
    return {"verdict": verdict, "m": m, "precondition": rungs}


# ------------------------------------------------------------------ P-D8, the constant rule's plant


def pd8(exact_top, d_top, exact_below, d_below, classes_top, values_top, classes_below,
        values_below, margins_top, margins_below):  # fmt: skip
    """P-D8 (the lead's ruling 3): on D6's honest observables at the two rungs M reads, (d)'s value
    at one constant pair moved one ulp up (np.nextafter toward +inf; σ's +0.0 becomes the smallest
    subnormal), the exact replicas and every other value as run; once for each constant pair at
    each rung. A planted pair is caught when judge_world fails the world and M's constant failures
    are the honest judgement's plus that pair. P-D8 is caught when every planted pair that the
    precondition lets M judge is caught, and at least one is judged."""
    args = [exact_top, d_top, exact_below, d_below, classes_top, values_top, classes_below,
            values_below, margins_top, margins_below]  # fmt: skip
    honest = judge_world(*args)
    unjudged = {"top": set(honest["precondition"]["top"]["unjudged"]),
                "below": set(honest["precondition"]["below"]["unjudged"])}
    rows = []
    for label, index in (("top", 1), ("below", 3)):
        classes = classes_top if label == "top" else classes_below
        for key, row in classes.items():
            for j, c in enumerate(row):
                if c != CONSTANT:
                    continue
                if label == "below" and classes_top[key][j] != CONSTANT:
                    continue  # M judges K - 1's constants only where the pair is constant at K
                planted = {k: np.array(v, dtype=np.float64) for k, v in args[index].items()}
                planted[key][j] = np.nextafter(planted[key][j], np.inf)
                trial = list(args)
                trial[index] = planted
                result = judge_world(*trial)
                name = f"{key}@{j}"
                judged = name not in unjudged[label] and name not in unjudged["top"]
                want = sorted(set(honest["m"]["constant_failures"]) | {name})
                caught = (result["verdict"] == "fail"
                          and sorted(result["m"]["constant_failures"]) == want)  # fmt: skip
                rows.append({"rung": label, "pair": name, "judged": judged, "caught": caught})
    judged_rows = [r for r in rows if r["judged"]]
    return {"plant": "P-D8", "planted": len(rows), "judged": len(judged_rows),
            "caught": bool(judged_rows) and all(r["caught"] for r in judged_rows),
            "honest_verdict": honest["verdict"], "rows": rows}  # fmt: skip


# ------------------------------------------------------------------ the linear-noise variance (§4.3)

NOISE_GRID_S = {"D5": 0.1, "D6": 0.01}  # (d)'s observation grid for the variance's integration


def _noise_model(spec):
    """The world's drift, its Jacobian, the diffusion matrix and each vesicle's margin, on the core
    state [pool (P), slots (K × V)] (a single lineage: the whole world, P), from the engine's own
    Problem and Shape: each step's directions a+ = k_f exp(log_direction) and a- = a+ exp(ΔF),
    as `Problem.flux` forms J = a+ (1 - e^ΔF)."""
    import jax
    import jax.numpy as jnp

    from cells.models.assembly_lineages_v2 import lumen
    from cells.models.assembly_lineages_v2 import rate_equations as re_

    prob = re_.Problem(spec)
    shape = re_.Shape(prob)
    P, b = prob.P, shape.blocks
    alive = np.asarray(shape.initial()[1], dtype=bool)
    lay = prob.layout
    active, kf = np.asarray(lay.step_active), np.asarray(lay.kf)
    on = shape.vesicle_step if shape.population else active
    jumps = {}
    for k in (range(shape.K) if shape.population else (0,)):
        nu = np.zeros((prob.R, P + b))
        if shape.population:
            nu[:, :P] = shape.nu_pool
            nu[:, P + k * shape.V : P + (k + 1) * shape.V] = shape.nu_slot
        else:
            nu[:, :P] = prob.nu_finite
        jumps[k] = nu * np.asarray(on, dtype=np.float64)[:, None]

    def states(core):
        if not shape.population:
            return {0: core}
        full = shape.full(core[:P], core[P:].reshape((shape.K, shape.V)))
        return {k: full[k] for k in range(shape.K) if alive[k]}

    def rhs(core):
        y = jnp.concatenate((core, jnp.zeros(P + 2)))
        return shape.rhs(y, jnp.asarray(alive))[: P + b]

    def parts(core):
        f, d = jnp.zeros(P + b), jnp.zeros((P + b, P + b))
        for k, n in states(core).items():
            d_f = jnp.asarray(prob.nu_finite) @ prob.potentials(n) - np.asarray(lay.step_work)
            log_a = prob.log_direction(n, True)
            a_plus = jnp.where(active, kf * jnp.exp(jnp.where(active, log_a, 0.0)), 0.0)
            a_minus = a_plus * jnp.exp(jnp.where(active, d_f, 0.0))
            nu = jnp.asarray(jumps[k])
            f = f + nu.T @ (a_plus - a_minus)
            d = d + (nu.T * (a_plus + a_minus)[None, :]) @ nu
        return f, d

    def margin(core, k):
        n = states(core)[k]
        log_osm, log_sph = lumen.log_branches(n @ prob.lumen_mask, n @ prob.quanta,
                                              prob.lumen_c, jnp)  # fmt: skip
        return log_sph - log_osm

    vesicles = [k for k in (range(shape.K) if shape.population else (0,)) if alive[k]]
    return SimpleNamespace(
        prob=prob, shape=shape, P=P, rhs=jax.jit(rhs), jacobian=jax.jit(jax.jacfwd(rhs)),
        parts=jax.jit(parts), vesicles=vesicles,
        grad={k: jax.jit(jax.grad(lambda c, k=k: margin(c, k))) for k in vesicles},
        margin={k: jax.jit(lambda c, k=k: margin(c, k)) for k in vesicles})  # fmt: skip


def _van_loan(sigma, a, d, h):
    """Σ after h under dΣ/dt = AΣ + ΣAᵀ + D with A and D constant (Van Loan, 1978)."""
    from scipy.linalg import expm

    n = a.shape[0]
    big = np.zeros((2 * n, 2 * n))
    big[:n, :n], big[:n, n:], big[n:, n:] = -a, d, a.T
    e = expm(big * h)
    f = e[n:, n:].T
    return f @ sigma @ f.T + f @ e[:n, n:]


def linear_noise(name, rung, definition=None):
    """The linear-noise approximation (van Kampen) of the exact process about (d)'s own trajectory:
    {prefix: [{"t", "margin", "sd"}]} for each vesicle at the registered times, with
    `drift_check` (the directions' drift against the engine's right-hand side at a moved state).

    (d) runs alone on its registered definition (or `definition`) with a fine observation grid
    added. dΣ/dt = AΣ + ΣAᵀ + D from Σ = 0 at the fixed founder: A the drift's Jacobian, and
    D = Σ over every step's two directions of (a+ + a-) ν νᵀ, both at (d)'s state, each grid
    interval solved exactly with A and D at the mean of its two ends. At D6's shear (d) gives the
    followed daughter half the vesicle; the exact split (division.py) cuts a one-species membrane
    at equal areas (rule 9: variance at most 1/4) and sends each lumen molecule to it with p = 1/2
    (rule 10: variance N_L/4), so Σ → SΣSᵀ + diag(split), S halving the vesicle's places. The SD
    is (gᵀΣg)^½, g the margin's gradient."""
    import jax.numpy as jnp

    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import runner

    d = lq.definition(name, rung, 1, True) if definition is None else json.loads(
        json.dumps(definition))
    times = [float(t) for t in d["experiment"]["observation_times_s"]]
    horizon = float(d["experiment"]["time_horizon_s"])
    h = NOISE_GRID_S[name]
    grid = {round(h * i, 9) for i in range(1, int(round(horizon / h)) + 1)} | set(times)
    if name == "D6":
        grid.discard(float(lq.D6["shear_s"]))
    d["experiment"]["observation_times_s"] = sorted(grid)
    spec = parse_spec(d)
    m = _noise_model(spec)
    run = runner.run(spec)
    rows = run.rows
    kinds = [str(k) for k in np.asarray(rows["row_kind"])]
    t = np.asarray(rows["row_time_s"], dtype=np.float64)

    def padded(a):
        a = np.asarray(a, dtype=np.float64)
        out = np.zeros(a.shape[:-1] + (m.P,))
        out[..., : a.shape[-1]] = a
        return out

    if m.shape.population:
        slots = padded(rows["slot_counts"])[:, :, m.shape.places]
        core = np.concatenate((padded(rows["pool_counts"]), slots.reshape(len(t), -1)), axis=1)
    else:
        core = padded(rows["counts"])
    moved = core[0].copy()
    moved[moved > 0] *= 1.0 + 0.003 * np.arange(1, int(np.sum(moved > 0)) + 1)
    f_moved, _ = m.parts(jnp.asarray(moved))
    rhs_moved = np.asarray(m.rhs(jnp.asarray(moved)))
    drift_check = float(np.max(np.abs(np.asarray(f_moved) - rhs_moved)) / np.max(np.abs(rhs_moved)))

    def at(i):
        return np.asarray(m.jacobian(jnp.asarray(core[i]))), np.asarray(m.parts(
            jnp.asarray(core[i]))[1])

    n = core.shape[1]
    sigma = np.zeros((n, n))
    prefixes = {k: ("" if not m.shape.population else f"slot{k}:") for k in m.vesicles}
    out = {prefixes[k]: [] for k in m.vesicles}
    prev = 0
    a_prev, d_prev = at(0)
    for i in range(1, len(t)):
        if kinds[i] == "shear":
            if t[i] > t[prev]:
                sigma = _van_loan(sigma, a_prev, d_prev, t[i] - t[prev])
            prob = m.prob
            halve = np.where(prob.vesicle, 0.5, 1.0)
            split = np.zeros(n)
            lumen_places = np.flatnonzero(prob.vesicle & (prob.lumen_mask > 0))
            split[lumen_places] = core[prev][lumen_places] / 4.0
            split[np.flatnonzero(prob.vesicle & (prob.quanta > 0))] = 0.25
            sigma = halve[:, None] * sigma * halve[None, :] + np.diag(split)
            prev = i
            a_prev, d_prev = at(i)
            continue
        if kinds[i] not in ("observed", "end"):
            continue
        a_i, d_i = at(i)
        sigma = _van_loan(sigma, 0.5 * (a_prev + a_i), 0.5 * (d_prev + d_i), t[i] - t[prev])
        sigma = 0.5 * (sigma + sigma.T)
        prev, a_prev, d_prev = i, a_i, d_i
        if kinds[i] == "observed" and float(t[i]) in times:
            for k in m.vesicles:
                g = np.asarray(m.grad[k](jnp.asarray(core[i])))
                out[prefixes[k]].append({
                    "t": float(t[i]), "margin": float(m.margin[k](jnp.asarray(core[i]))),
                    "sd": math.sqrt(max(float(g @ sigma @ g), 0.0))})  # fmt: skip
    return {"status": run.status, "drift_check": drift_check, "vesicles": out}


def noise_table():
    """For D5 and D6 at every rung, each vesicle with constant pairs (D5's slot 1, D6's vesicle) at
    its constant times: (d)'s margin, the linear-noise SD, z = margin/SD and the Gaussian chance
    that one replica is tense there; at D6 after the shear also the lumen split's exact binomial
    tail (it dominates the SD there). Per world and rung, the chance that any of its M replicas is
    tense at any constant time, bounded by the union over times: 1 - (1 - Σ_t p_t)^M."""
    from scipy.stats import binom, norm

    margins = _registered_margins()
    out = {}
    for name in ("D5", "D6"):
        for rung in lq.RUNGS["vesicle"]:
            replicas = lq.REPLICAS["vesicle"]
            classes, _ = classify(name, rung, floppy_from_margins(name, rung, margins))
            world = _parse(name, rung, True).model.world
            is_lumen = np.asarray([p.phase == "lumen" for p in world.places], dtype=np.float64)
            noise = linear_noise(name, rung)
            for prefix, rows in noise["vesicles"].items():
                times = [j for j, c in enumerate(classes.get(f"{prefix}sigma_N_per_m", []))
                         if c == CONSTANT]  # fmt: skip
                if not times:
                    continue
                per_time = []
                for j in times:
                    r = rows[j]
                    z = r["margin"] / r["sd"] if r["sd"] > 0 else math.inf
                    row = {"t": r["t"], "margin": r["margin"], "sd": r["sd"], "z": z,
                           "p_tense": float(norm.sf(z))}  # fmt: skip
                    if name == "D6" and r["t"] > lq.D6["shear_s"]:
                        # the parent's lumen at the shear is the founder's: no step moves it
                        n_l = int(round(float(np.asarray(world.founder) @ is_lumen)))
                        bound = (n_l / 2.0) * math.exp(r["margin"])
                        row["p_tense_lumen_binomial"] = float(binom.sf(math.floor(bound), n_l, 0.5))
                    per_time.append(row)
                union = min(1.0, math.fsum(p["p_tense"] for p in per_time))
                out[f"{name}_{float(rung)}:{prefix or 'vesicle'}"] = {
                    "status": noise["status"], "drift_check": noise["drift_check"],
                    "constant_times": per_time,
                    "smallest_z": min(p["z"] for p in per_time),
                    "p_any_replica_tense": -math.expm1(replicas * math.log1p(-union)),
                    "m_reads": rung in lq.RUNGS["vesicle"][-2:]}  # fmt: skip
    return out


# ------------------------------------------------------------------ the registered numbers (§4.3)


def floppy_from_margins(name, rung, margins):
    """{vesicle prefix: [bool per time]} from (d)'s registered margins of that world and rung."""
    entry = margins[f"{name}_{float(rung)}"]
    return {prefix: [bool(m > 0) for m in row] for prefix, row in entry.items()}


def classification_table(margins):
    """Every world and rung's classes and constants from (d)'s registered margins: the table
    protocol_d_v2.json records, {f"{name}_{rung}": {"constant": {key: [[j, value]]},
    "spread_keys": [...], "times": [...]}}."""
    out = {}
    for name in M_WORLDS:
        for rung in lq.RUNGS[lq.family(name)]:
            floppy = (floppy_from_margins(name, rung, margins) if name in ("D5", "D6")
                      else {})  # fmt: skip
            classes, values = classify(name, rung, floppy)
            constant = {k: [[j, values[k][j]] for j in js]
                        for k, js in constant_pairs(classes).items()}  # fmt: skip
            out[f"{name}_{float(rung)}"] = {"times": list(lq.times_of(name, rung)),
                                            "keys": list(classes), "constant": constant}
    return out


def margins_from_probe(path):
    """(d)'s margins at the registered times from the author's (d)-alone runs (the probe file of
    §4.3: {f"{name}_{rung}": {"vesicles": [{"slot", "times", "margin_ln"}]}}), the founder's row
    dropped: {f"{name}_{rung}": {prefix: [margin per registered time]}}."""
    doc = json.loads(open(path).read())
    out = {}
    for key, entry in doc.items():
        name, rung = key.split("_")
        single = name == "D6"
        times = list(lq.times_of(name, float(rung)))
        by = {}
        for ves in entry["vesicles"]:
            row = dict(zip(ves["times"], ves["margin_ln"], strict=True))
            prefix = "" if single else f"slot{ves['slot']}:"
            by[prefix] = [float(row[t]) for t in times]
        out[f"{name}_{float(rung)}"] = by
    return out


# ------------------------------------------------------------------ the checks (§8)

REPLICAS, TIMES = 128, 8


def _made_up(rng, value, spread, ties=()):
    """A made-up rung of one observable: (d)'s values and REPLICAS replicas around them, the
    replicas bitwise (d)'s at the columns `ties`."""
    d = value * (1.0 + 0.1 * np.arange(TIMES))
    a = d[None, :] * (1.0 + spread * rng.standard_normal((REPLICAS, TIMES)))
    a[:, list(ties)] = d[list(ties)]
    return a, d


def _same(a, b):
    return np.float64(a).view(np.uint64) == np.float64(b).view(np.uint64)


def _m_checks(rng):
    """M on made-up columns only."""
    out = {}
    classes = {"V": [CONSTANT] * 3 + [SPREAD] * 5}
    a_top, d_top = _made_up(rng, 0.7316, 1e-3, ties=(0, 1, 2))
    a_below, d_below = _made_up(rng, 0.6113, 2e-3, ties=(0, 1, 2))
    values_top = {"V": [float(d_top[j]) if j < 3 else None for j in range(TIMES)]}
    values_below = {"V": [float(d_below[j]) if j < 3 else None for j in range(TIMES)]}
    m = criterion_m({"V": a_top}, {"V": d_top}, {"V": a_below}, {"V": d_below}, classes,
                    values_top, classes, values_below)  # fmt: skip
    top = lq.mean_error({"V": a_top[:, 3:]}, {"V": d_top[3:]})
    below = lq.mean_error({"V": a_below[:, 3:]}, {"V": d_below[3:]})
    registered = lq.criterion_m(top, below)["largest_z"]
    every = lq.criterion_m(lq.mean_error({"V": a_top}, {"V": d_top}),
                           lq.mean_error({"V": a_below}, {"V": d_below}))["largest_z"]  # fmt: skip
    out["constant pairs by the constant rule, the rest bitwise the registered z"] = {
        "z": m["largest_z"], "registered_over_every_pair": every,
        "ok": m["passes"] and m["pairs_constant"] == 3 and _same(m["largest_z"], registered)
        and every > 6.0}  # fmt: skip

    for label, edit in (("one replica 1 ulp off", "replica"), ("(d) 1 ulp off", "d"),
                        ("-0.0 against 0.0", "signed"), ("a NaN replica", "nan")):  # fmt: skip
        a, d, value = a_top.copy(), d_top.copy(), float(d_top[0])
        if edit == "replica":
            a[5, 0] = np.nextafter(a[5, 0], np.inf)
        elif edit == "d":
            d[0] = np.nextafter(d[0], np.inf)
        elif edit == "signed":
            a[:, 0], d[0], value = -0.0, -0.0, 0.0
        else:
            a[7, 0] = np.nan
        vt = {"V": [value if j == 0 else values_top["V"][j] for j in range(TIMES)]}
        m = criterion_m({"V": a}, {"V": d}, {"V": a_below}, {"V": d_below}, classes, vt,
                        classes, values_below)  # fmt: skip
        out[f"a constant pair fails: {label}"] = {"failures": m["constant_failures"],
                                                  "ok": m["fails"] and m["constant_failures"]
                                                  == ["V@0"]}  # fmt: skip

    spread_all = {"V": [SPREAD] * TIMES}
    none = {"V": [None] * TIMES}
    count_top = np.full((REPLICAS, TIMES), 120.0)
    count_below = np.full((REPLICAS, TIMES), 60.0)
    m = criterion_m({"V": count_top}, {"V": np.full(TIMES, 120.0)}, {"V": count_below},
                    {"V": np.full(TIMES, 60.0)}, spread_all, none, spread_all, none)  # fmt: skip
    out["zero SE, zero error (identical integer replicas at (d)): the inequality holds"] = {
        "z": m["largest_z"], "ok": m["passes"] and m["largest_z"] == -np.inf}
    m = criterion_m({"V": count_top}, {"V": np.full(TIMES, 119.25)}, {"V": count_below},
                    {"V": np.full(TIMES, 59.75)}, spread_all, none, spread_all, none)  # fmt: skip
    old = lq.criterion_m(lq.mean_error({"V": count_top}, {"V": np.full(TIMES, 119.25)}),
                         lq.mean_error({"V": count_below}, {"V": np.full(TIMES, 59.75)}))
    out["zero SE, nonzero error: fails (the registered code took it as no limit)"] = {
        "z": m["largest_z"], "registered_z": old["largest_z"],
        "ok": m["fails"] and m["largest_z"] == np.inf and old["passes"]}  # fmt: skip

    a, d = _made_up(rng, 0.7316, 1e-3, ties=range(TIMES))
    b, db = _made_up(rng, 0.6113, 2e-3, ties=range(TIMES))
    m = criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, spread_all, none, spread_all, none)
    old = lq.criterion_m(lq.mean_error({"V": a}, {"V": d}), lq.mean_error({"V": b}, {"V": db}))
    off = a.copy()
    off[:, 3] = np.nextafter(d[3], np.inf)
    m_off = criterion_m({"V": off}, {"V": d}, {"V": b}, {"V": db}, spread_all, none, spread_all,
                        none)  # fmt: skip
    label = ("identical non-integer replicas at a spread pair are judged exactly: at (d)'s bits "
             "-inf, all one ulp off +inf (the registered mean_error's residue gave a z)")
    out[label] = {"z": m["largest_z"], "z_one_ulp_off": m_off["largest_z"],
                  "registered_z": old["largest_z"],
                  "ok": m["passes"] and m["largest_z"] == -np.inf and m_off["fails"]
                  and m_off["largest_z"] == np.inf and old["largest_z"] > 6.0}  # fmt: skip

    a, d = _made_up(rng, 3.2, 1e-2)
    b, db = _made_up(rng, 3.1, 2e-2)
    m = criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, spread_all, none, spread_all, none)
    registered = lq.criterion_m(lq.mean_error({"V": a}, {"V": d}),
                                lq.mean_error({"V": b}, {"V": db}))["largest_z"]  # fmt: skip
    out["genuine spread columns: z bitwise the registered one"] = {
        "z": m["largest_z"], "ok": _same(m["largest_z"], registered)}
    try:
        criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, {}, {}, {}, {})
        refused = False
    except ValueError:
        refused = True
    out["an observable without a class is refused"] = {"ok": refused}
    return out


def _moments_checks(rng):
    """`moments` against the registered lq.mean_error, e and SE bit for bit, at every observable
    and time whose replicas are not all identical: made-up columns at a V's, a count's and a σ's
    magnitudes, one with NaN replicas (runs that ended early) and one with a single finite
    replica; and one mixed observable, its first three columns identical at (d)'s bits (there
    `moments` gives e 0 and SE 0 exactly) and the rest varying (there bit for bit the registered)."""
    exact, d = {}, {}
    for key, value, spread in (("V_L", 2.7488312e-19, 1e-3), ("L@pool", 8378.0, 1e-2),
                               ("sigma_N_per_m", 1.3e-4, 3e-1)):  # fmt: skip
        exact[key], d[key] = _made_up(rng, value, spread)
    nan, d["with_nan"] = _made_up(rng, 0.7316, 1e-3)
    nan[[3, 50, 99], 2] = np.nan
    nan[7, 5] = np.nan
    exact["with_nan"] = nan
    single, d["one_finite"] = _made_up(rng, 3.1, 2e-2)
    single[1:, 4] = np.nan
    exact["one_finite"] = single
    mixed, d["mixed"] = _made_up(rng, 0.6113, 2e-3, ties=(0, 1, 2))
    exact["mixed"] = mixed
    import warnings

    with warnings.catch_warnings():  # the single-replica column's ddof=1 SD is NaN in both
        warnings.simplefilter("ignore", RuntimeWarning)
        ours, registered = moments(exact, d), lq.mean_error(exact, d)
    same, exact_ties = True, True
    for key in exact:
        for j in range(TIMES):
            if key == "mixed" and j < 3:
                exact_ties &= bool(ours[key][0][j] == 0.0 and ours[key][1][j] == 0.0)
                continue
            for a, b in zip(ours[key], registered[key]):
                same &= bool(np.float64(a[j]).view(np.uint64) == np.float64(b[j]).view(np.uint64))
    residues = int(sum(registered["mixed"][1][j] > 0 for j in range(3)))
    return {"moments equals the registered mean_error bit for bit wherever replicas differ (e and "
            "SE, every observable and time; NaN and single-replica columns; one mixed case)": {
                "observables": len(exact), "mixed_identical_columns_exact": exact_ties,
                "registered_residues_at_the_mixed_ties": residues,
                "ok": same and exact_ties}}


def _zero_se_checks():
    """The zero-SE path on the registered constants: every constant pair of D5 and D6 at the rungs
    M reads, as 128 identical replicas at the registered value with (d) at it, classed spread at
    both rungs. `moments` gives SE 0 and e 0 at every one, so the excess is -inf; the registered
    mean_error leaves its rounding residue at some of them (counted, with their z)."""
    table = json.loads(_registered_path().read_text())["classification"]
    pairs, residue, worst = 0, 0, -np.inf
    exact_path = True
    for name in ("D5", "D6"):
        for rung in lq.RUNGS["vesicle"][-2:]:
            for _, rows in table[f"{name}_{float(rung)}"]["constant"].items():
                for _, value in rows:
                    column = np.full((REPLICAS, 1), np.float64(value))
                    d = np.asarray([np.float64(value)])
                    e, se = moments({"x": column}, {"x": d})["x"]
                    exact_path &= bool(e[0] == 0.0 and se[0] == 0.0)
                    exact_path &= bool(spread_excess(e, se, e, se)[0] == -np.inf)
                    e_r, se_r = lq.mean_error({"x": column}, {"x": d})["x"]
                    if se_r[0] > 0:
                        residue += 1
                        worst = max(worst, float(spread_excess(e_r, se_r, np.zeros(1),
                                                               np.zeros(1))[0]))  # fmt: skip
                    pairs += 1
    return {"the zero-SE path on the registered constants: identical replicas at (d)'s bits are an "
            "exact match": {"pairs": pairs, "registered_mean_error_residues": residue,
                            "registered_largest_z": worst, "ok": exact_path and pairs == 54}}


def _world_checks(rng):
    """judge_world and P-D8 on made-up columns: a constant V before an operator, a constant σ and
    a spread count, at two rungs, with invented margins."""
    out = {}
    v_top, v_below = 2.7488312e-19, 3.4360390e-20
    classes = {"V_L": [CONSTANT] * 3 + [SPREAD] * 5, "sigma_N_per_m": [CONSTANT] * TIMES,
               "L@pool": [SPREAD] * TIMES}  # fmt: skip

    def rung(v, spread_v, count):
        a_v, d_v = _made_up(rng, v, spread_v, ties=(0, 1, 2))
        a_v[:, :3], d_v[:3] = v, v
        a_n, d_n = _made_up(rng, count, 1e-2)
        exact = {"V_L": a_v, "sigma_N_per_m": np.zeros((REPLICAS, TIMES)), "L@pool": a_n}
        d = {"V_L": d_v, "sigma_N_per_m": np.zeros(TIMES), "L@pool": d_n}
        values = {"V_L": [v] * 3 + [None] * 5, "sigma_N_per_m": [0.0] * TIMES,
                  "L@pool": [None] * TIMES}  # fmt: skip
        return exact, d, values

    e_top, d_top, val_top = rung(v_top, 1e-3, 8378.0)
    e_below, d_below, val_below = rung(v_below, 2e-3, 2094.0)
    floppy = {"": [0.51] * 3 + [0.164] * 5}

    def margins(tense_run=None, at=6):
        runs = [{"": list(floppy[""])} for _ in range(REPLICAS + 1)]
        if tense_run is not None:
            runs[tense_run][""][at] = -0.004
        return runs

    def world(e_t=None, d_t=None, m_t=None, m_b=None):
        return judge_world(e_top if e_t is None else e_t, d_top if d_t is None else d_t, e_below,
                           d_below, classes, val_top, classes, val_below,
                           margins() if m_t is None else m_t,
                           margins() if m_b is None else m_b)  # fmt: skip

    honest = world()
    out["the world's verdict: every run floppy, every constant exact: pass"] = {
        "verdict": honest["verdict"], "ok": honest["verdict"] == "pass"}
    tense = world(m_t=margins(17))
    physical = {k: v.copy() for k, v in e_top.items()}
    physical["sigma_N_per_m"][17, 6] = 1.3e-4  # the tense replica's own tension, as it would be
    tense_physical = world(e_t=physical, m_t=margins(17))
    d_tense = world(m_t=margins(REPLICAS))
    label = "a tense replica gives inconclusive, never pass (its σ moved or not; (d) tense alike)"
    out[label] = {
        "verdicts": [tense["verdict"], tense_physical["verdict"], d_tense["verdict"]],
        "tense": tense["precondition"]["top"]["tense"],
        "ok": [tense["verdict"], tense_physical["verdict"], d_tense["verdict"]]
        == ["inconclusive"] * 3
        and tense["precondition"]["top"]["tense"] == {"exact_replicas": 1, "d": False,
                                                      "by_vesicle_time": {"6": 1}}
        and d_tense["precondition"]["top"]["tense"]["d"]
        and tense["precondition"]["top"]["unjudged"] == ["sigma_N_per_m@6"]}  # fmt: skip
    wrong = {k: v.copy() for k, v in e_top.items()}
    wrong["V_L"][40, 1] = np.nextafter(v_top, np.inf)
    both = world(e_t=wrong, m_t=margins(17))
    out["a floppy replica one ulp off fails the world, a tense one elsewhere notwithstanding"] = {
        "verdict": both["verdict"], "failures": both["m"]["constant_failures"],
        "ok": both["verdict"] == "fail" and both["m"]["constant_failures"] == ["V_L@1"]}
    plant = pd8(e_top, d_top, e_below, d_below, classes, val_top, classes, val_below, margins(),
                margins())  # fmt: skip
    plant_tense = pd8(e_top, d_top, e_below, d_below, classes, val_top, classes, val_below,
                      margins(17), margins())  # fmt: skip
    out["P-D8 on made-up columns: every planted constant pair caught; a tense time's not judged"] = {
        "planted": plant["planted"], "judged": plant["judged"],
        "judged_with_a_tense_replica": plant_tense["judged"],
        "ok": plant["caught"] and plant["planted"] == 22 and plant["judged"] == 22
        and plant_tense["caught"] and plant_tense["judged"] == 20}  # fmt: skip
    return out


def _invented_rows(spec, representation, rng, tense=False):
    """An invented run of one registered world, in the representation's row layout, from its
    founder with made-up perturbations of every moved place at the registered times; the lumen is
    left as founded (a floppy vesicle, unmoved). With `tense`, every vesicle's lumen is scaled up
    tenfold at the last time."""
    world = spec.model.world
    times = [float(t) for t in spec.experiment.observation_times_s]
    n_places = len(world.places)
    founder = np.asarray(world.founder, dtype=np.float64)
    is_lumen = np.asarray([p.phase == "lumen" for p in world.places])
    moved = np.zeros(n_places, dtype=bool)
    for i in lq.enveloped(world):
        moved[i] = not is_lumen[i]

    def state(base, j):
        out = base.copy()
        out[moved] = out[moved] * (1.0 + 0.01 * j) + rng.integers(0, 3, int(moved.sum()))
        if tense and j == len(times) and is_lumen.any():
            out[is_lumen] *= 10.0
        return out

    all_times = [0.0, *times]
    if world.population is None:
        counts = np.stack([state(founder, j) for j in range(len(all_times))])
        pool, slots = counts, None
    else:
        pool = np.stack([state(founder, j) for j in range(len(all_times))])
        bases = [np.asarray(f, dtype=np.float64) for f in world.population["founders"]]
        slots = np.stack([np.stack([state(b, j) for b in bases])
                          for j in range(len(all_times))])  # fmt: skip
    work = np.linspace(0.0, 1.5, len(all_times)) if held_read(world) else np.zeros(len(all_times))
    rows = {"reservoir_work_kT": work}
    if representation:
        rows["row_time_s"] = np.asarray(all_times)
        rows["row_kind"] = np.asarray(["start", *["observed"] * len(times)])
        if slots is None:
            rows["counts"] = pool
        else:
            rows["pool_counts"], rows["slot_counts"] = pool, slots
    else:
        rows["row_time"] = np.asarray(all_times)
        rows["row_kind"] = np.asarray([0, *[lq.OBSERVED["exact"]] * len(times)])
        if slots is None:
            rows["place_count"] = pool
        else:
            rows["pool_count"], rows["slot_count"] = pool, slots
    return SimpleNamespace(rows=rows)


def _reader_checks(rng, margins):
    """The registered reader (lq.observables) on invented runs of the registered worlds, both
    layouts: it gives exactly the classification's keys, and at an unmoved floppy vesicle the
    constant pairs' values bit for bit; the margins read positive where floppy and negative after
    an invented tension."""
    out = {}
    for name, rung in (("D1", 1000), ("D2", 1000), ("D4", 25.0), ("D5", 50.0), ("D6", 50.0)):
        floppy = floppy_from_margins(name, rung, margins) if name in ("D5", "D6") else {}
        classes, values = classify(name, rung, floppy)
        ok, detail = True, {}
        for representation in (False, True):
            spec = _parse(name, rung, representation)
            run = _invented_rows(spec, representation, rng)
            obs = lq.observables(name, spec, run, representation)
            keys_ok = list(obs) == list(classes)
            same = all(_same(obs[k][j], values[k][j])
                       for k, js in constant_pairs(classes).items() for j in js)  # fmt: skip
            ok &= keys_ok and same
            detail["d" if representation else "exact"] = {
                "keys": len(obs), "keys_match": keys_ok, "constants_bitwise": same}
        out[f"the reader on invented {name} rows at {rung}: keys and constants"] = {
            **detail, "ok": ok}
    spec = _parse("D6", 50.0, True)
    honest = floppy_margins(spec, _invented_rows(spec, True, rng), True)
    tense = floppy_margins(spec, _invented_rows(spec, True, rng, tense=True), True)
    out["the margins: floppy positive, an invented tension negative"] = {
        "ok": bool(np.all(honest[""] > 0)) and bool(tense[""][-1] < 0)
        and bool(np.all(tense[""][:-1] > 0))}  # fmt: skip
    classes, _ = classify("D6", 50.0, floppy_from_margins("D6", 50.0, margins))
    pre = precondition(classes, [honest, tense])
    out["the precondition names the tense run's constant times"] = {
        "violations": pre["violations"],
        "ok": not pre["holds"] and pre["violations"] == [("", 7, 1)]}
    return out


def _end_to_end_checks(rng, margins):
    """judge_world and P-D8 end to end, as the checker will feed them: invented runs of the
    registered D5 and D6 at the two rungs M reads, 128 exact replicas in the exact row layout and
    one (d) run in (d)'s, each through the registered reader (lq.observables) and floppy_margins.
    D5's tense slot 0 has no constant pair, so its tension enters nothing. (d)'s spread values are
    set to what makes e exactly 0, so that only the constant path and the precondition decide."""
    out = {}

    def read(name, spec, run, representation):
        return (lq.observables(name, spec, run, representation),
                floppy_margins(spec, run, representation))  # fmt: skip

    def matching(exact, d, classes):
        d = {k: np.array(v, dtype=np.float64) for k, v in d.items()}
        for k, row in classes.items():
            for j, c in enumerate(row):
                if c != SPREAD:
                    continue
                column = exact[k][:, j][np.isfinite(exact[k][:, j])]
                same = column.size >= 2 and np.all(column.view(np.uint64)
                                                   == column[0:1].view(np.uint64))  # fmt: skip
                d[k][j] = column[0] if same else np.nanmean(exact[k][:, j])
        return d

    def dropped_last(run):
        return SimpleNamespace(rows={k: np.asarray(v)[:-1] for k, v in run.rows.items()})

    for name in ("D5", "D6"):
        prefix = "slot1:" if name == "D5" else ""
        rungs = {}
        for label, rung in (("top", 100.0), ("below", 50.0)):
            classes, values = classify(name, rung, floppy_from_margins(name, rung, margins))
            spec_x, spec_d = _parse(name, rung, False), _parse(name, rung, True)
            runs = [_invented_rows(spec_x, False, rng) for _ in range(REPLICAS)]
            reads = [read(name, spec_x, r, False) for r in runs]
            exact = {k: np.stack([o[k] for o, _ in reads]) for k in reads[0][0]}
            d_obs, d_margin = read(name, spec_d, _invented_rows(spec_d, True, rng), True)
            rungs[label] = {"classes": classes, "values": values, "spec": spec_x, "runs": runs,
                            "exact": exact, "d": d_obs,
                            "margins": [m for _, m in reads] + [d_margin]}  # fmt: skip

        def world(top=None, top_margins=None):
            t, b = rungs["top"], rungs["below"]
            exact_top = t["exact"] if top is None else top
            return judge_world(
                exact_top, matching(exact_top, t["d"], t["classes"]), b["exact"],
                matching(b["exact"], b["d"], b["classes"]), t["classes"], t["values"],
                b["classes"], b["values"], t["margins"] if top_margins is None else top_margins,
                b["margins"])  # fmt: skip

        top = rungs["top"]
        honest = world()
        wrong = {k: v.copy() for k, v in top["exact"].items()}
        wrong[f"{prefix}sigma_N_per_m"][5, 3] = 1e-6  # a wrong σ on floppy counts
        wrong_sigma = world(wrong)
        tense_run = _invented_rows(top["spec"], False, rng, tense=True)
        tense_obs, tense_margin = read(name, top["spec"], tense_run, False)
        tensed = {k: v.copy() for k, v in top["exact"].items()}
        for k in tensed:
            tensed[k][9] = tense_obs[k]
        tense_margins = list(top["margins"])
        tense_margins[9] = tense_margin
        tense = world(tensed, tense_margins)
        short_obs, short_margin = read(name, top["spec"], dropped_last(top["runs"][11]), False)
        shorted = {k: v.copy() for k, v in top["exact"].items()}
        for k in shorted:
            shorted[k][11] = short_obs[k]
        short_margins = list(top["margins"])
        short_margins[11] = short_margin
        short = world(shorted, short_margins)
        last = len(lq.times_of(name, 100.0)) - 1
        want_short = sorted(f"{k}@{last}" for k, row in top["classes"].items()
                            if row[last] == CONSTANT)  # fmt: skip
        out[f"end to end, {name} at 100 against 50 nm: the reader's rows into judge_world"] = {
            "verdicts": {"honest": honest["verdict"], "wrong_sigma_on_floppy_counts":
                         wrong_sigma["verdict"], "tense_replica": tense["verdict"],
                         "replica_without_its_last_row": short["verdict"]},
            "tense": tense["precondition"]["top"]["tense"],
            "ok": honest["verdict"] == "pass" and wrong_sigma["verdict"] == "fail"
            and wrong_sigma["m"]["constant_failures"] == [f"{prefix}sigma_N_per_m@3"]
            and wrong_sigma["precondition"]["top"]["holds"]
            and tense["verdict"] == "inconclusive"
            and tense["precondition"]["top"]["tense"] == {
                "exact_replicas": 1, "d": False, "by_vesicle_time": {f"{prefix}{last}": 1}}
            and short["verdict"] == "fail" and short["precondition"]["top"]["holds"]
            and sorted(short["m"]["constant_failures"]) == want_short}  # fmt: skip
        if name == "D6":
            b = rungs["below"]
            plant = pd8(top["exact"], matching(top["exact"], top["d"], top["classes"]),
                        b["exact"], matching(b["exact"], b["d"], b["classes"]), top["classes"],
                        top["values"], b["classes"], b["values"], top["margins"],
                        b["margins"])  # fmt: skip
            out["end to end, P-D8 on D6's read rows: all 22 single-pair plants caught"] = {
                "planted": plant["planted"], "judged": plant["judged"],
                "honest": plant["honest_verdict"],
                "ok": plant["caught"] and plant["planted"] == plant["judged"] == 22
                and plant["honest_verdict"] == "pass"}  # fmt: skip
    return out


def _classification_checks(margins):
    """From the model and (d)'s registered margins: D5's floppy slot's V and σ at every time and
    D6's σ at every time and V before the shear are the only constant pairs, at every rung."""
    table = classification_table(margins)
    want = {"D5": {"slot1:V_L": list(range(8)), "slot1:sigma_N_per_m": list(range(8))},
            "D6": {"V_L": [0, 1, 2], "sigma_N_per_m": list(range(8))}}
    ok, found = True, {}
    for key, entry in table.items():
        name = key.split("_")[0]
        got = {k: [j for j, _ in v] for k, v in entry["constant"].items()}
        found[key] = got
        ok &= got == want.get(name, {})
        for k, pairs in entry["constant"].items():
            ok &= all(v == 0.0 for _, v in pairs) if k.endswith("sigma_N_per_m") else \
                all(v > 0 for _, v in pairs)  # fmt: skip
    return {"the constant pairs, from the model": {"constant": found, "ok": bool(ok)}}


def _parse_checks():
    """Every registered definition parses at this head: exact everywhere, (d) everywhere but D0,
    which the envelope refuses at parse (the protocol's §6)."""
    from cells.definitions.specs import ConfigError

    problems = []
    for name in ("D0", *lq.DENSITY, *lq.VESICLE):
        rungs = [None] if name == "D0" else lq.RUNGS[lq.family(name)]
        for rung in rungs:
            for representation in (False, True):
                try:
                    _parse(name, rung, representation, seed=seeds(name)[0])
                    if name == "D0" and representation:
                        problems.append("D0 admitted in (d)")
                except ConfigError as error:
                    if not (name == "D0" and representation and "below the envelope" in str(error)):
                        problems.append(f"{name} {rung} {representation}: {str(error)[:120]}")
    return {"every registered definition parses (D0 refused in (d) as registered)": {
        "problems": problems, "ok": not problems}}


def check(margins_path=None):
    """The registration's checks (§8): invented inputs and made-up columns only, and the parse of
    the registered definitions. `margins_path` defaults to protocol_d_v2.json's own margins."""
    rng = np.random.default_rng(20261124)
    margins = _registered_margins(margins_path)
    ok, overlaps = seeds_disjoint()
    out = {"the seeds are disjoint from every earlier range": {"overlaps": overlaps, "ok": ok}}
    out |= _m_checks(rng)
    out |= _moments_checks(rng)
    out |= _zero_se_checks()
    out |= _world_checks(rng)
    out |= _end_to_end_checks(rng, margins)
    out |= _classification_checks(margins)
    out |= _reader_checks(rng, margins)
    out |= _parse_checks()
    for result in out.values():
        result["ok"] = bool(result["ok"])
    return out


def _registered_path():
    from pathlib import Path

    return Path(__file__).with_name("protocol_d_v2.json")


def _registered_margins(path=None):
    if path is None:
        return json.loads(_registered_path().read_text())["d_margins"]
    return margins_from_probe(path)


# ------------------------------------------------------------------ the registered file


COST = {  # the document's §9, measured from the first check of the same worlds (CPU-seconds)
    "exact_first_seed_set_s": {"D0": 83, "D1": 2156, "D2": 5396, "D3": 5926, "D4": 1666,
                               "D5": 21762, "D6": 1691, "D7": 2409},
    "d_paired_D7_s": 2683, "d_other_runs_s_about": 3600, "plants_s_about": 1000,
    "source": "the first check's exact folders' meta.json `seconds` and D7's (d) records' "
    "run_seconds, read for these numbers alone",
}  # fmt: skip


PLANTS = {  # the document's §8: the plant this registration adds, with its registered effect
    "P-D8": {"world": "D6", "rungs": [50.0, 100.0], "where": "(d) alone, on the honest run's "
             "observables: one constant pair's value one ulp up, once per constant pair and rung",
             "criterion": "M's constant rule (judge_world)",
             "registered_effect": "each planted pair that the precondition lets M judge fails "
             "the world, M's constant failures the honest judgement's plus that pair; 22 "
             "single-pair plants (11 pairs at each rung); a pair the precondition leaves "
             "unjudged is reported, not counted; caught when every judged plant is caught and at "
             "least one is judged", "cost": "none: it reads the honest D6 runs"},
}  # fmt: skip


def register(margins_path, out_path, noise_path=None):
    """protocol_d_v2.json: the seeds, the earlier ranges, (d)'s margins and the linear-noise table
    at them, the classification table, the plant it adds and the cost (§3, §4.3, §8 and §9)."""
    margins = margins_from_probe(margins_path)
    doc = {
        "kind": "cells.ol6.protocol_d@2",
        "status": "proposed for registration: Protocol D's re-registration (D318), before any run "
        "of its comparison",
        "document": "docs/OL6_PROTOCOL_D_V2.md",
        "seeds": {"first": SEEDS["first"], "retry": SEEDS["retry"],
                  "rule": "seeds base .. base + M - 1, environment 0, lineage 0, branch 0",
                  "earlier": [list(r) for r in EARLIER_SEEDS]},
        "d_margins": margins,
        "linear_noise": json.loads(open(noise_path).read()) if noise_path else None,
        "classification": classification_table(margins),
        "derived_pairs": [],
        "plants": PLANTS,
        "cost": COST,
    }  # fmt: skip
    with open(out_path, "w") as handle:
        json.dump(doc, handle, indent=1)
        handle.write("\n")
    return doc


def main(argv):
    if argv[:1] == ["check"]:
        results = check(argv[1] if len(argv) > 1 else None)
        print(json.dumps(results, indent=1, default=str))
        return 0 if all(r["ok"] for r in results.values()) else 1
    if argv[:2] == ["noise", "--out"] and len(argv) == 3:
        table = noise_table()
        with open(argv[2], "w") as handle:
            json.dump(table, handle, indent=1)
            handle.write("\n")
        for key, row in table.items():
            print(key, "smallest z", round(row["smallest_z"], 2), "P(any replica tense)",
                  f"{row['p_any_replica_tense']:.2e}", "drift check", f"{row['drift_check']:.1e}")
        return 0
    registering = argv[:1] == ["register"] and len(argv) in (5, 7)
    if registering and argv[1] == "--margins" and argv[3] == "--out":
        register(argv[2], argv[4], argv[6] if len(argv) == 7 and argv[5] == "--noise" else None)
        return 0
    raise SystemExit("usage: python -m validation.assembly_lineages_v2.protocol_d_v2 check "
                     "[MARGINS] | noise --out FILE | register --margins FILE --out FILE "
                     "[--noise FILE]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
