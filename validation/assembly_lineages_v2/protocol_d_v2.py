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
  registered excess, with the registered inequality evaluated exactly where the combined SE is
  0, so that no zero SE is taken as no limit and no rounding floor is declared;
- **the constant pairs' precondition** (`floppy_margins`, `precondition`): every vesicle the
  classification calls floppy is floppy in every exact replica and in (d) at that time;
- **its checks** (`check`): the reader on invented inputs, M on made-up columns, the
  classification, the seeds and the parse of every registered definition.

Run with `PYTHONPATH=src:. JAX_ENABLE_X64=1`:
- `python -m validation.assembly_lineages_v2.protocol_d_v2 check` runs the checks, on invented
  inputs and made-up columns only, and parses the registered definitions (it runs no world);
- `python -m validation.assembly_lineages_v2.protocol_d_v2 register --margins FILE --out FILE
  --scale FILE` writes protocol_d_v2.json from (d)'s margins and the model's fluctuation scale at
  them (the document's §4.3).
"""

import json
import sys
from types import SimpleNamespace

import numpy as np

from validation.assembly_lineages_v2 import agreement
from validation.assembly_lineages_v2 import limit_qualification as lq

CONSTANT, DERIVED, SPREAD = agreement.CONSTANT, agreement.DERIVED, agreement.SPREAD

# ------------------------------------------------------------------ the seeds (the document's §3)

SEEDS = {"first": 640001, "retry": 740001}  # seeds base .. base + M - 1, environment 0
EARLIER_SEEDS = (  # every stream seed range registered or used before this registration
    ("Protocol D, first seeds", 1, 256),
    ("Protocol D, retry seeds", 100001, 100256),
    ("Protocol G, seeds (@1 1001-1256 and @2 2001-2256 among them)", 1, 5256),
    ("Protocol G, matrix seeds", 20261123, 20261142),
    ("Protocol G's checker, timing smokes (unregistered, 900001 onward)", 900001, 999999),
    ("FR-47, first seeds (W1, W1D, W2's rungs, P7, P8)", 470001, 471528),
    ("FR-47, retry seeds (W2's: the first plus 500,000)", 970001, 971528),
    ("the probes' and smokes' stream seeds, 1 and 7", 1, 7),
    ("D2's beta generator seed (a world input, kept)", 20261124, 20261124),
)


def seeds(name, which="first"):
    """The M seeds of one world: SEEDS[which] + 0 .. M - 1, M = lq.REPLICAS by family."""
    m = lq.REPLICAS["D0"] if name == "D0" else lq.REPLICAS[lq.family(name)]
    return list(range(SEEDS[which], SEEDS[which] + m))


def seeds_disjoint():
    """(ok, overlaps): every seed of every world and both sets against EARLIER_SEEDS."""
    used = set()
    for name in ("D0", *lq.DENSITY, *lq.VESICLE):
        for which in SEEDS:
            used |= set(seeds(name, which))
    overlaps = [(label, lo, hi) for label, lo, hi in EARLIER_SEEDS
                if any(lo <= s <= hi for s in used)]  # fmt: skip
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


def _judge_constant(values, d_value, expected):
    """One constant pair at one rung: agreement.judge_constant on the exact replicas, and (d)'s
    value bit for bit; a NaN anywhere is not the constant."""
    replicas = agreement.judge_constant(values, expected)
    d_ok = bool(np.float64(d_value).view(np.uint64) == np.float64(expected).view(np.uint64))
    return {**replicas, "d_matches": d_ok, "passes": replicas["passes"] and d_ok,
            "fails": replicas["fails"] or not d_ok}  # fmt: skip


def criterion_m(exact_top, d_top, exact_below, d_below, classes_top, values_top,
                classes_below=None, values_below=None):  # fmt: skip
    """M at the top rung K against K - 1, each rung's observables as lq.observables gives them
    ({key: [M, T]} and {key: [T]}), with the pairs' classes and constants from `classify`.

    - A pair constant at K is judged by the constant rule at K, and at K - 1 where it is constant
      there too; it is not in the z. One replica off, or (d) off, fails M.
    - Every other pair is spread: lq.mean_error at both rungs and `spread_excess`; the largest z
      passes at most lq.Z_STAR and fails beyond lq.Z_FAIL. Identical replicas are not excluded.
    - M passes when every constant pair passes and the largest z passes; it fails when a constant
      pair fails or the largest z fails; it is inconclusive otherwise. With no spread pair the
      largest z is -inf."""
    classes_below = classes_top if classes_below is None else classes_below
    values_below = values_top if values_below is None else values_below
    top, below = lq.mean_error(exact_top, d_top), lq.mean_error(exact_below, d_below)
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
    as lq.observables reads them (NaN after the run's end); positive where floppy. The engine's
    own lumen.log_branches on real N_L and W."""
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
    every run's vesicle (each exact replica and (d), `margins_by_run` a list of floppy_margins) is
    floppy, its margin finite and positive. Returns {"holds", "violations": [(vesicle, time
    index, run index)]}."""
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
                if not (np.isfinite(m) and m > 0):
                    bad.append((prefix, j, r))
    return {"holds": not bad, "violations": bad}


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
                    {"V": np.full(TIMES, 60.0)}, spread_all, none)  # fmt: skip
    out["zero SE, zero error (identical integer replicas at (d)): the inequality holds"] = {
        "z": m["largest_z"], "ok": m["passes"] and m["largest_z"] == -np.inf}
    m = criterion_m({"V": count_top}, {"V": np.full(TIMES, 119.25)}, {"V": count_below},
                    {"V": np.full(TIMES, 59.75)}, spread_all, none)  # fmt: skip
    old = lq.criterion_m(lq.mean_error({"V": count_top}, {"V": np.full(TIMES, 119.25)}),
                         lq.mean_error({"V": count_below}, {"V": np.full(TIMES, 59.75)}))
    out["zero SE, nonzero error: fails (the registered code took it as no limit)"] = {
        "z": m["largest_z"], "registered_z": old["largest_z"],
        "ok": m["fails"] and m["largest_z"] == np.inf and old["passes"]}  # fmt: skip

    a, d = _made_up(rng, 0.7316, 1e-3, ties=range(TIMES))
    b, db = _made_up(rng, 0.6113, 2e-3, ties=range(TIMES))
    m = criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, spread_all, none)
    label = "identical replicas at a spread pair still face the test (the artifact, unclassified)"
    out[label] = {"z": m["largest_z"], "ok": not m["passes"]}

    a, d = _made_up(rng, 3.2, 1e-2)
    b, db = _made_up(rng, 3.1, 2e-2)
    m = criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, spread_all, none)
    registered = lq.criterion_m(lq.mean_error({"V": a}, {"V": d}),
                                lq.mean_error({"V": b}, {"V": db}))["largest_z"]  # fmt: skip
    out["genuine spread columns: z bitwise the registered one"] = {
        "z": m["largest_z"], "ok": _same(m["largest_z"], registered)}
    try:
        criterion_m({"V": a}, {"V": d}, {"V": b}, {"V": db}, {}, {})
        refused = False
    except ValueError:
        refused = True
    out["an observable without a class is refused"] = {"ok": refused}
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
    out |= _classification_checks(margins)
    out |= _reader_checks(rng, margins)
    out |= _parse_checks()
    for result in out.values():
        result["ok"] = bool(result["ok"])
    return out


def _registered_margins(path=None):
    from pathlib import Path

    if path is None:
        path = Path(__file__).with_name("protocol_d_v2.json")
        return json.loads(Path(path).read_text())["d_margins"]
    return margins_from_probe(path)


# ------------------------------------------------------------------ the registered file


COST = {  # the document's §9, measured from the first check of the same worlds (CPU-seconds)
    "exact_first_seed_set_s": {"D0": 83, "D1": 2156, "D2": 5396, "D3": 5926, "D4": 1666,
                               "D5": 21762, "D6": 1691, "D7": 2409},
    "d_paired_D7_s": 2683, "d_other_runs_s_about": 3600, "plants_s_about": 1000,
    "source": "the first check's exact folders' meta.json `seconds` and D7's (d) records' "
    "run_seconds, read for these numbers alone",
}  # fmt: skip


def register(margins_path, out_path, scale_path=None):
    """protocol_d_v2.json: the seeds, the earlier ranges, (d)'s margins and the model's
    fluctuation scale at them, the classification table and the cost (§4.3 and §9)."""
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
        "floppy_scale_estimate": json.loads(open(scale_path).read()) if scale_path else None,
        "classification": classification_table(margins),
        "derived_pairs": [],
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
    registering = argv[:1] == ["register"] and len(argv) in (5, 7)
    if registering and argv[1] == "--margins" and argv[3] == "--out":
        register(argv[2], argv[4], argv[6] if len(argv) == 7 and argv[5] == "--scale" else None)
        return 0
    raise SystemExit("usage: python -m validation.assembly_lineages_v2.protocol_d_v2 check "
                     "[MARGINS] | register --margins FILE --out FILE [--scale FILE]")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
