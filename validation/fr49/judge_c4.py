"""FR-49's judge for C4, the four-way form (fr49-compartment-compositions-v1, amendment 2, A2.2 to
A2.6, with amendment 3's horizon for plant (e)).

It reads the driver's records (validation/fr49/driver_c4.py: one record per registered run, the
engine's own values, with the definition as built) and the tagged references
(fr49-references-2026-11-24: L.json, B.json's once values and C1.json's well), and writes every
number to OUT/verdict.json. The lead runs it, after the runs. The tagged judges are imported and
never edited: the references are read by the readers that exist at their tags
(judge_l.read_reference and judge_bc.read_reference; D308's later rule), and the bounds and helpers
are judge_bc's.

**Every record, before any value** (A2.2, A2.7; the reader, read_record):
- its job is exactly its row of RUNS, the judge's own table of the eight runs;
- it names the fresh process it ran in, and no two runs share one (one_process_each, first);
- its definition as built (`<id>.definition.json`) is present, hashes to the record's
  `definition_sha256`, and passes amendment 2's two gates, the values gate against cases.json and
  the decoupling gate (worlds_c4.gates_refusal, with the run's registered change). A run whose
  definition fails either gate is not judged: the judge refuses the set, naming it;
- its entity slots are world_c4()'s;
- once completed, its rows are exactly the dt grid from 0 to the horizon (judge_bc.grid_refusal,
  READING-2's reading 3), with every quantity and array one entry per row, its observations
  (`OBS.<name>`, C4-4's) on the observation grid instead, and its O, C and P arrays exactly C4-1's
  set (c4_physical_names), none missing and none extra.

**The criteria as written** (A2.4), each at 0.5 s, "every row" being every saved row:
- C4-1, the wash elsewhere: O's and C's physical rows (C4's entity rule: READING-3's, with the site
  operator's populations and sets classed P) and their label shares bit for bit the twin's on every
  row, gated on the wash's counts: the well's event applied exactly once at W in C4, its unlabelled
  and its unbound twins, none in the twin, none at C in any of the four;
- C4-2, the well: W's x and base amounts just after the wash (the 900.5 s row) within 1e-13
  relative of C1.json's well; its inconclusive rule reads the well's own cross-checks;
- C4-3, the host checks: the four runs completed, and label_closure_relative at most 64 eps on
  every row of the three labelled runs;
- C4-4, labels change no physics: every history field and observation of the unlabelled twin bit for
  bit C4's, the diagnostics equal, and C4's extra fields judge_l.LABELS_ONLY's alone;
- C4-5, G conserved: |n_G + B - L_T| <= 1e-10 L_T at C on every row of the four runs, L_T world B's
  declared n_L(0) + B(0);
- C4-6, G's equilibrium: |B - B*| <= 1e-10 B* on every row of C4 with t >= 550 s, B* B.json's;
- C4-7, by species: C4-1's set, less what binding legitimately changes (G's row at C, the site
  operator's fields on site_population and site_set, and its heat at C's slot), plus every label
  share at every cell and outside node, bit for bit the unbound twin's on every row; in the unbound
  twin B is 0 and n_G at C is n_G(0) on every row;
- C4-8, the labelled species: x_O and x_C exactly 0 on every row before t1 (L3), and
  e_q(0.5 s) <= 1e-3 for q in {n_O, n_C, x_O, x_C} against L.json at its sample times (L5); its
  inconclusive rule reads L.json's cross-checks.

**The inconclusive rule** (the registration's preamble): a criterion that reads a reference value
is inconclusive, not a pass, where that reference reports a cross-check outside its declared
accuracy: C4-2 the well's (judge_bc.well_checks), C4-6 and plant (a) B.json's, C4-8 L.json's.

**The plants** (A2.6). Each must fail at least one of its named criteria, and the judge reports
every criterion each plant fails:
- (a) no depletion, formed here from the declared values in 50-digit decimal arithmetic: C4-6;
- (c) K_d x 2: C4-6;
- (d) the wash at every finite node: C4-1, and C4-5;
- (c1) the buffer labelled x: C4-2;
- (e) the sites write the labelled species: C4-7, and C4-8 (C4-5 is reported).
C4-1 counts as a catch for (d) only and C4-7 for (e) only (READING-2's change 3's form); for the
other plants they are reported and not scored. A plant run refused by a named check is reported, and
is not the catch, so the part fails (READING-2's reading 2).

**Plant (e)'s own horizon** (amendment 3, A3.2 and A3.3): (e) runs to 1800 s, so its "every row" is
its own dt grid, 0 to 1800 s (3,601 rows). C4-1 and C4-7 compare it with the twin's and the unbound
twin's rows at t <= 1800 s, whose times must be its own bit for bit (on_rows; the twins'
observations, where read, at the instants t <= 1800 s). C4-8 reads it at the 31 of L's 61 sample
times to 1800 s, each e_q's numerator over those 31 and its scale, max |q_ref|, over all 61 of
L.json's (labelled_species). C4-2, C4-5 and C4-6 read its own rows. No cut touches an honest run.

Usage (from a snapshot's root, PYTHONPATH=src, JAX_ENABLE_X64=1, JAX_PLATFORMS=cpu):
  python -B -m validation.fr49.judge_c4 --records RECORDS --references REFS --out OUT
  python -B -m validation.fr49.judge_c4 --check-reader SAMPLES --cases CASES [--cases-l CASES_L]
      --out OUT
REFS holds L.json, B.json and C1.json, from `git archive` of their tag. SAMPLES holds the invented
format samples INVENTED_L.json, INVENTED_B.json and INVENTED_C1.json, read by structure only.
"""

import argparse
import functools
import hashlib
import json
from decimal import Decimal, localcontext
from pathlib import Path

import numpy as np

from validation.fr49 import judge_bc, judge_l
from validation.fr49.judge_bc import (
    B4_FROM,
    CLOSURE,
    CONSERVATION,
    EQUILIBRIUM,
    SITES_PER_FMOL,
    WELL,
    ReaderError,
    _bitwise,
    _criterion,
    _present,
    cross_checks,
    grid_refusal,
    process_of,
    well_checks,
)
from validation.fr49.judge_l import LABELS_ONLY, SIZE

RECORD_KIND = "fr49 C4 engine record, version 1"
READER_ERRORS = (ReaderError, judge_l.ReaderError)  # The two tagged readers' refusals.
PROTOCOL = judge_bc.PROTOCOL
# The registered runs (A2.3, A2.6): id -> (world, dt s, horizon s, observed every s, the wash's
# event, labelled, bound, plant). The driver holds its own copy (driver_c4.JOBS).
RUNS = {
    "C4-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, True, True, None),
    "C4-twin-dt0.5": ("C4", 0.5, 3600.0, 60.0, False, True, True, None),
    "C4-unlabelled-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, False, True, None),
    "C4-unbound-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, True, False, None),
    "C4-plant-c-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, True, True, "c"),
    "C4-plant-d-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, True, True, "d"),
    "C4-plant-c1-dt0.5": ("C4", 0.5, 3600.0, 60.0, True, True, True, "c1"),
    "C4-plant-e-dt0.5": ("C4", 0.5, 1800.0, 60.0, True, True, True, "e"),  # Its own (A3.2).
}
JOB_FIELDS = ("world", "dt", "horizon_s", "every_s", "event", "labelled", "bound", "plant")
C4, TWIN, UNLABELLED, UNBOUND = (
    "C4-dt0.5",
    "C4-twin-dt0.5",
    "C4-unlabelled-dt0.5",
    "C4-unbound-dt0.5",
)
FOUR = (C4, TWIN, UNLABELLED, UNBOUND)
LABELLED = (C4, TWIN, UNBOUND)
PLANTS = {"c": "C4-plant-c-dt0.5", "d": "C4-plant-d-dt0.5", "c1": "C4-plant-c1-dt0.5",
          "e": "C4-plant-e-dt0.5"}  # fmt: skip
MUST_FAIL = {"a": ("C4-6",), "c": ("C4-6",), "d": ("C4-1", "C4-5"), "c1": ("C4-2",),
             "e": ("C4-7", "C4-8")}  # fmt: skip
SCORED_ONLY = {"C4-1": "d", "C4-7": "e"}  # Each counts as a catch for that plant alone.
L_TIMES = [60.0 * i for i in range(61)]  # World L's sample times (L.json's, A2.5).
# C4-7's minus: the fields binding legitimately changes (A2.4), beside G's row at C.
BINDING_PREFIX, BINDING_HEAT = "P.site_", "C.site_outside_dissipated_energy_pJ"


def change_of(run_id):
    """The registered change by which a run's definition departs from C4's (worlds_c4.CHANGES)."""
    _, _, _, _, event, labelled, bound, plant = RUNS[run_id]
    if not event:
        return "twin"
    if not labelled:
        return "unlabelled"
    if not bound:
        return "unbound"
    return {"c": "plant c", "e": "plant e"}.get(plant)


# ------------------------------------------------------------------ C4's world, as the judge reads


@functools.cache
def world():
    """C4's parsed world (worlds_c4.world_c4) and its indices: the owner O, the compartment C and
    the well W, G's and S's species rows, the expected entity slots (JSON form) and C4-1's names."""
    from cells.definitions.specs import parse_spec
    from cells.registry.models import get_model
    from validation.fr49 import worlds
    from validation.fr49 import worlds_bc as wb
    from validation.fr49 import worlds_c4 as w4

    raw = w4.world_c4()
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, _ = model.initial_values(spec)
    names = []
    try:
        slots = w4.c4_entity_slots(raw)
        for field in type(state)._fields:
            if field in LABELS_ONLY:
                continue
            axes = tuple(model.STATE_AXES.get(field, ()))
            part = w4.c4_part(axes, np.asarray(getattr(state, field))[None], slots)
            if part is not None:
                names.append(f"{part[0]}.{field}")
    except ValueError as error:
        raise ReaderError(f"C4-1's entity rule: {error}") from error
    ids = list(spec.model.species_ids)
    nodes = [c.id for c in spec.model.extracellular]
    return dict(
        owner=[c.id for c in spec.model.cells].index(worlds.CELL),
        node=nodes.index(worlds.NODE),
        well=nodes.index(wb.W),
        g=ids.index(w4.G),
        s=ids.index(worlds.S),
        species=len(ids),
        slots=json.loads(json.dumps(slots)),
        names=tuple(names),
    )


def c4_physical_names():
    """C4-1's arrays beyond the label shares: every non-label state field whose entity is O or C or
    a patch bounding them but W's, with the site operator's populations and sets (worlds_c4's rule),
    named `<class>.<field>` as the driver saves them."""
    return world()["names"]


def declared(name):
    from validation.fr49 import worlds

    return worlds.declared(name)


# ------------------------------------------------------------------ reading the records


def one_process_each(records):
    """Refuses a set of the registered runs' records in which two runs share one process."""
    seen = {}
    for run_id in RUNS:
        path = _present(Path(records) / f"{run_id}.json", run_id)
        identity = process_of(json.loads(path.read_text()), path)
        if identity in seen:
            raise ReaderError(f"{run_id} and {seen[identity]} share one process; each has its own")
        seen[identity] = run_id


def read_definition(records, run_id, record):
    """A run's definition as built, refused unless it hashes to its record's and passes amendment
    2's two gates (A2.2: a run whose definition fails either is not judged)."""
    from validation.fr49 import worlds_c4 as w4

    path = _present(Path(records) / f"{run_id}.definition.json", run_id)
    if hashlib.sha256(path.read_bytes()).hexdigest() != record.get("definition_sha256"):
        raise ReaderError(f"{path}: its hash is not its record's definition_sha256")
    definition = json.loads(path.read_text())
    refusal = w4.gates_refusal(definition, change_of(run_id))
    if refusal:
        raise ReaderError(
            f"{run_id} is not judged: its definition fails amendment 2's gates: {refusal}"
        )
    return definition


def read_record(records, run_id):
    """(record, {q: float array}, times, arrays) of one run's record, the last three None unless it
    completed, refused unless it is in its registered layout (the module docstring)."""
    path = _present(Path(records) / f"{run_id}.json", run_id)
    record = json.loads(path.read_text())
    if record.get("kind") != RECORD_KIND or record.get("protocol") != PROTOCOL:
        raise ReaderError(f"{path} is not an FR-49 C4 engine record")
    job = record.get("job", {})
    if job.get("id") != run_id or tuple(job.get(k) for k in JOB_FIELDS) != RUNS[run_id]:
        raise ReaderError(f"{path}: its job is not the registered run {run_id} (RUNS)")
    process_of(record, path)
    read_definition(records, run_id, record)
    if record.get("c4_entity_slots") != world()["slots"]:
        raise ReaderError(f"{path}: it names other entity slots than world_c4()'s")
    if record.get("outcome") != "completed":
        return record, None, None, None
    times = np.asarray([float.fromhex(x) for x in record["times"]])
    _, dt, end, _, _, _, _, _ = RUNS[run_id]
    refusal = grid_refusal(times, dt, end)
    if refusal:
        raise ReaderError(f"{path}: {refusal}")
    quantities = {
        k: np.asarray([float.fromhex(x) for x in v]) for k, v in record["quantities"].items()
    }
    for k, values in quantities.items():
        if values.shape != times.shape:
            raise ReaderError(
                f"{path}: quantity {k} has {values.size} entries for {times.size} rows"
            )
    arrays = dict(np.load(_present(Path(records) / f"{run_id}.npz", run_id)))
    for name, values in arrays.items():
        if not name.startswith("OBS.") and values.shape[:1] != times.shape:
            raise ReaderError(f"{path}: array {name} has {values.shape[:1]} rows for {times.size}")
    observed = {n: v for n, v in arrays.items() if n.startswith("OBS.")}
    if observed:  # The observations lie on the observation grid, every `every` s to the horizon.
        every = RUNS[run_id][3]
        grid = np.arange(int(round(end / every)) + 1, dtype=float) * every
        if "OBS.times" not in observed or not np.array_equal(observed["OBS.times"], grid):
            raise ReaderError(
                f"{path}: its observations are not on the {every:g} s grid to {end:g} s"
            )
        for name, values in observed.items():
            if values.shape[:1] != grid.shape:
                raise ReaderError(f"{path}: observation {name} has {values.shape[:1]} rows")
    saved = {n for n in arrays if n.partition(".")[0] in ("O", "C", "P") and "." in n}
    expected = set(c4_physical_names())
    if saved != expected:
        raise ReaderError(
            f"{path}: its O, C and P arrays are not exactly C4-1's set: extra "
            f"{sorted(saved - expected)}, missing {sorted(expected - saved)}"
        )
    return record, quantities, times, arrays


def _completed(runs, run_ids):
    return {k: runs[k][0]["outcome"] for k in run_ids}


# ------------------------------------------------------------------ the criteria


def washes(arrays):
    """{W, C}: the wash's applied count at each, from its cumulative rows (None where they fall or
    go negative)."""
    found = {}
    for where in ("W", "C"):
        rows = np.asarray(arrays[f"wash_applied_{where}"])
        steady = rows.ndim == 1 and rows.min() >= 0 and bool(np.all(np.diff(rows) >= 0))
        found[where] = int(rows[-1]) if steady else None
    return found


def on_rows(runs, run_id, other):
    """`other`'s arrays on `run_id`'s rows (amendment 3, A3.3). A run of a shorter horizon than
    `other`'s, plant (e)'s, is compared with `other`'s rows at t <= its horizon and with its
    observations at the instants t <= its horizon; a run of `other`'s horizon, with every row, as
    registered. Either way `other`'s times on those rows, and its observation instants where both
    runs saved observations, must be the run's own bit for bit, or the comparison is refused
    (ReaderError)."""
    times, theirs = runs[run_id][2], runs[other][2]
    rows = times.size
    if theirs.size < rows or theirs[:rows].tobytes() != times.tobytes():
        raise ReaderError(
            f"{other}'s times on {run_id}'s rows are not {run_id}'s bit for bit (amendment 3, A3.3)"
        )
    arrays = runs[other][3]
    if theirs.size == rows:
        return arrays
    cut = {name: values[:rows] for name, values in arrays.items() if not name.startswith("OBS.")}
    if "OBS.times" in arrays:
        keep = arrays["OBS.times"] <= times[-1]
        cut.update({n: v[keep] for n, v in arrays.items() if n.startswith("OBS.")})
        own = runs[run_id][3].get("OBS.times")
        if own is not None and own.tobytes() != cut["OBS.times"].tobytes():
            raise ReaderError(
                f"{other}'s observation instants to {run_id}'s horizon are not {run_id}'s bit for "
                "bit (amendment 3, A3.3)"
            )
    return cut


def c4_one(runs, run_id):
    """C4-1's comparison of one run against the twin, on the run's rows (on_rows): (differing
    names, wash counts)."""
    w = world()
    a, t = runs[run_id][3], on_rows(runs, run_id, TWIN)
    differing = [n for n in c4_physical_names() if not _bitwise(a[n], t[n])]
    cuts = {
        "label_share at O": lambda x: x["label_share"][..., w["owner"]],
        "label_outside_share at C": lambda x: x["label_outside_share"][..., w["node"]],
    }
    differing += [name for name, cut in cuts.items() if not _bitwise(cut(a), cut(t))]
    return differing


def c4_seven(runs, run_id):
    """C4-7's comparison of one run against the unbound twin, on the run's rows (on_rows): the
    names that differ."""
    w = world()
    a, u = runs[run_id][3], on_rows(runs, run_id, UNBOUND)
    differing = []
    for name in c4_physical_names():
        if name.startswith(BINDING_PREFIX) or name == BINDING_HEAT:
            continue
        x, y = a[name], u[name]
        if name == "C.extracellular_amount_increment":  # G's row at C is binding's own.
            keep = [i for i in range(x.shape[1]) if i != w["g"]]
            x, y = x[:, keep], y[:, keep]
        if not _bitwise(x, y):
            differing.append(name)
    differing += [n for n in ("label_share", "label_outside_share") if not _bitwise(a[n], u[n])]
    return differing


def conserved(runs, run_id):
    v = declared("B")
    total = float(Decimal(v["initial_fmol"]["n_L"]) + Decimal(v["initial_fmol"]["B"]))
    q = runs[run_id][1]
    return float(np.max(np.abs(q["n_G"] + q["B"] - total)) / total)


def equilibrium(runs, run_id, b_star):
    q, t = runs[run_id][1], runs[run_id][2]
    late = t >= B4_FROM
    return float(np.max(np.abs(q["B"][late] - b_star)) / b_star)


def well(runs, run_id, reference):
    """C4-2's engine values and gaps: W's x and base amounts at the wash's row and the first row
    after it."""
    t_wash = float(declared("C1")["wash"]["time_s"])
    q, t = runs[run_id][1], runs[run_id][2]
    before = int(np.flatnonzero(np.abs(t - t_wash) <= 1e-9 * t_wash)[0])
    after = int(np.flatnonzero(t > t_wash * (1 + 1e-9))[0])
    n, x, base = q["n_W"], q["share_x_W"], q["share_base_W"]
    found = dict(
        before_time=float(t[before]),
        after_time=float(t[after]),
        x_W_before=float(n[before] * x[before]),
        b_W_before=float(n[before] * base[before]),
        x_W_after=float(n[after] * x[after]),
        b_W_after=float(n[after] * base[after]),
    )
    gaps = {k: abs(found[k] - reference[k]) / abs(reference[k]) for k in ("x_W_after", "b_W_after")}
    return found, gaps


def labelled_species(runs, run_id, l_ref):
    """C4-8's engine side: L3's zeros before t1, and L5's errors at L's sample times within the
    run's horizon: all 61, or plant (e)'s 31 to 1800 s (amendment 3, A3.3). Each e_q's numerator
    runs over those times, and its scale, max |q_ref|, over all 61 of L.json's (section 1's scale,
    kept)."""
    t1 = float(declared("L")["pulse_s"]["t1"])
    q, t = runs[run_id][1], runs[run_id][2]
    early = t < t1
    zeros = bool(np.all(q["share_x_O"][early] == 0.0) and np.all(q["share_x_C"][early] == 0.0))
    within = [i for i, s in enumerate(L_TIMES) if s <= RUNS[run_id][2]]
    index = [
        int(np.flatnonzero(np.abs(t - L_TIMES[i]) <= 1e-9 * max(1.0, L_TIMES[i]))[0])
        for i in within
    ]
    engine = dict(
        n_O=q["n_O"][index],
        n_C=q["n_C"][index],
        x_O=(q["n_O"] * q["share_x_O"])[index],
        x_C=(q["n_C"] * q["share_x_C"])[index],
    )
    errors = {
        k: float(np.max(np.abs(engine[k] - np.asarray(l_ref[k], dtype=float)[within]))
                 / np.max(np.abs(np.asarray(l_ref[k], dtype=float))))
        for k in judge_l.QUANTITIES
    }  # fmt: skip
    return dict(rows_before_t1=int(early.sum()), zeros=zeros, e=errors, samples=len(within),
                passed=zeros and all(e <= SIZE for e in errors.values()))  # fmt: skip


def plant_a(b_star):
    """(a) no depletion: B = S c0/(K_d + c0), c0 = L_T / V_C, from the declared values at 50
    digits."""
    v = declared("B")
    sites = v["sites"]
    with localcontext() as context:
        context.prec = 50
        capacity = (Decimal(sites["accessible_fraction"]) * int(sites["sites_per_copy"])
                    * Decimal(sites["copies"]) / SITES_PER_FMOL)  # fmt: skip
        k_d = Decimal(v["k_off_per_s"]) / Decimal(v["k_on_per_mM_per_s"])
        total = Decimal(v["initial_fmol"]["n_L"]) + Decimal(v["initial_fmol"]["B"])
        c0 = total / Decimal(v["V_C_pL"])
        langmuir = float(capacity * c0 / (k_d + c0))
    gap = abs(langmuir - b_star) / b_star
    fails = ["C4-6"] if gap > EQUILIBRIUM else []
    return dict(caught=bool(fails), fails=fails, C4_6_relative_gap=gap)


def judge_c4(records, refs):
    """The criteria and the plants (the module docstring), and the part's verdict."""
    b_ref, c1_ref, l_ref = refs["B"], refs["C1"], refs["L"]
    b_star = b_ref["once"]["B*"]
    well_cross = well_checks(c1_ref["cross_checks"])
    if not well_cross:
        raise ReaderError("C1.json's method holds no cross-check of the well")
    runs = {k: read_record(records, k) for k in RUNS}
    out, plants = {}, {}
    completed = _completed(runs, FOUR)
    closure = {}
    for k in LABELLED:
        if runs[k][3] is None or "label_closure_relative" not in runs[k][3]:
            continue
        values = np.asarray(runs[k][3]["label_closure_relative"], dtype=float)
        closure[k] = float(np.max(values)) if values.size else None
    within = all(
        runs[k][3] is not None
        and "label_closure_relative" in runs[k][3]
        and runs[k][3]["label_closure_relative"].size > 0
        and bool(
            np.all(
                np.isfinite(runs[k][3]["label_closure_relative"])
                & (runs[k][3]["label_closure_relative"] <= CLOSURE)
            )
        )  # fmt: skip
        for k in LABELLED
    )
    out["C4-3"] = dict(
        passed=all(o == "completed" for o in completed.values()) and within,
        outcomes=completed,
        label_closure_relative_max=closure,
        bound=CLOSURE,
    )
    if not all(o == "completed" for o in completed.values()):
        return dict(verdict="failed", criteria=out, plants={})
    counts = {k: washes(runs[k][3]) for k in FOUR}
    want = {
        C4: dict(W=1, C=0),
        TWIN: dict(W=0, C=0),
        UNLABELLED: dict(W=1, C=0),
        UNBOUND: dict(W=1, C=0),
    }
    counted = counts == want
    differing = c4_one(runs, C4)
    out["C4-1"] = dict(passed=not differing and counted, differing=differing, washes=counts,
                       counts_as_registered=counted,
                       compared=len(c4_physical_names()) + 2)  # fmt: skip
    found, gaps = well(runs, C4, c1_ref["well"])
    out["C4-2"] = _criterion(all(g <= WELL for g in gaps.values()), True, well_cross, engine=found,
                             relative_gap=gaps)  # fmt: skip
    a, u = runs[C4], runs[UNLABELLED]
    fields_u = sorted(k for k in u[3] if k.startswith("H."))
    fields_c = sorted(k for k in a[3] if k.startswith("H."))
    observed = sorted(k for k in u[3] if k.startswith("OBS."))
    if not fields_u or not fields_c:
        raise ReaderError("C4's or its unlabelled twin's record holds no history fields (C4-4)")
    differ4 = [k for k in fields_u + observed if k not in a[3] or not _bitwise(u[3][k], a[3][k])]
    extra = sorted({k[2:] for k in fields_c} - {k[2:] for k in fields_u})
    diagnostics_equal = a[0].get("diagnostics") is not None and a[0].get("diagnostics") == u[0].get(
        "diagnostics"
    )
    out["C4-4"] = dict(passed=not differ4 and diagnostics_equal and set(extra) <= LABELS_ONLY,
                       differing=differ4, history_fields=len(fields_u), observations=len(observed),
                       diagnostics_equal=diagnostics_equal, extra_fields=extra)  # fmt: skip
    gaps5 = {k: conserved(runs, k) for k in FOUR}
    out["C4-5"] = dict(passed=all(g <= CONSERVATION for g in gaps5.values()), relative_gap=gaps5)
    b_cross = b_ref["cross_checks"]
    eq = equilibrium(runs, C4, b_star)
    out["C4-6"] = _criterion(eq <= EQUILIBRIUM, True, b_cross, relative_gap=eq)
    differ7 = c4_seven(runs, C4)
    q_u = runs[UNBOUND][1]
    unbound_still = bool(np.all(q_u["B"] == 0.0) and np.all(q_u["n_G"] == q_u["n_G"][0]))
    out["C4-7"] = dict(passed=not differ7 and unbound_still, differing=differ7,
                       unbound_B_zero_and_n_G_constant=unbound_still)  # fmt: skip
    l_cross = l_ref["cross_checks"]
    eight = labelled_species(runs, C4, l_ref)
    out["C4-8"] = _criterion(eight.pop("passed"), True, l_cross, **eight)

    plants["a"] = plant_a(b_star)
    for name, run_id in PLANTS.items():
        record, q, _, arrays = runs[run_id]
        if q is None:
            plants[name] = dict(caught=False, fails=[], refused=record.get("refusal"))
            continue
        report, fails = {}, []
        report["C4-1"] = dict(differing=c4_one(runs, run_id), washes=washes(arrays))
        if report["C4-1"]["differing"] or report["C4-1"]["washes"] != dict(W=1, C=0):
            fails.append("C4-1")
        if "share_x_W" in q:
            report["C4-2"] = well(runs, run_id, c1_ref["well"])[1]
            if any(g > WELL for g in report["C4-2"].values()):
                fails.append("C4-2")
        report["C4-5"] = conserved(runs, run_id)
        if report["C4-5"] > CONSERVATION:
            fails.append("C4-5")
        report["C4-6"] = equilibrium(runs, run_id, b_star)
        if report["C4-6"] > EQUILIBRIUM:
            fails.append("C4-6")
        report["C4-7"] = c4_seven(runs, run_id)
        if report["C4-7"]:
            fails.append("C4-7")
        report["C4-8"] = labelled_species(runs, run_id, l_ref)
        if not report["C4-8"]["passed"]:
            fails.append("C4-8")
        scored = [c for c in fails if c in MUST_FAIL[name] and SCORED_ONLY.get(c, name) == name]
        plants[name] = dict(caught=bool(scored), fails=fails, scored=scored, report=report)
    return dict(verdict=judge_bc.part_verdict(out, plants), criteria=out, plants=plants)


def read_references(references, *, cases=None):
    """{L, B, C1}: the tagged references by the readers at their tags, with their cross-checks."""
    refs = Path(references)
    spec = judge_bc.SPEC if cases is None else cases
    l_path = refs / "L.json"
    l_ref = judge_l.read_reference(l_path, L_TIMES, cases=spec)
    l_ref["cross_checks"] = cross_checks(json.loads(l_path.read_text()).get("method"))
    if not l_ref["cross_checks"]:
        raise ReaderError("L.json's method holds no cross-check")
    return dict(
        L=l_ref,
        B=judge_bc.read_reference(refs / "B.json", "B", cases=spec),
        C1=judge_bc.read_reference(refs / "C1.json", "C1", cases=spec),
    )


def judge(records, references):
    one_process_each(records)  # Before any value is read.
    refs = read_references(references)
    part = judge_c4(records, refs)
    return dict(protocol=PROTOCOL, runs=list(RUNS), parts={"C4": part}, verdict=part["verdict"],
                cross_checks={k: v["cross_checks"] for k, v in refs.items()})  # fmt: skip


def check_reader(samples, cases, cases_l=None):
    """D308: the tagged readers on the invented format samples, by structure, values unread."""
    report = {}
    readers = {
        "L": lambda path, invented: judge_l.read_reference(
            path, L_TIMES, cases=cases_l or cases, invented=invented
        ),  # fmt: skip
        "B": lambda path, invented: judge_bc.read_reference(
            path, "B", cases=cases, invented=invented
        ),
        "C1": lambda path, invented: judge_bc.read_reference(
            path, "C1", cases=cases, invented=invented
        ),  # fmt: skip
    }
    for world_name, read in readers.items():
        path = Path(samples) / f"INVENTED_{world_name}.json"
        try:
            parsed = read(path, True)
            report[world_name] = dict(parsed=True, keys=sorted(parsed))
        except READER_ERRORS as error:
            report[world_name] = dict(parsed=False, why=str(error))
        try:
            read(path, False)
            report[world_name]["refused_as_the_references"] = False
        except READER_ERRORS:
            report[world_name]["refused_as_the_references"] = True
    report.update(samples=str(samples), cases=str(cases), cases_l=str(cases_l or cases))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--records", type=Path)
    parser.add_argument("--references", type=Path)
    parser.add_argument("--check-reader", type=Path, default=None)
    parser.add_argument("--cases", type=Path, default=None)
    parser.add_argument("--cases-l", type=Path, default=None)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.check_reader is not None:
        if args.cases is None:
            parser.error(
                "--check-reader reads the invented cases the samples were made from (--cases)"
            )
        report = check_reader(args.check_reader, args.cases, args.cases_l)
        (args.out / "reader_check.json").write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps(report, indent=1))
        return
    if args.records is None or args.references is None:
        parser.error("a judged run gives --records and --references")
    verdict = judge(args.records, args.references)
    (args.out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=float) + "\n")
    print(verdict["verdict"])


if __name__ == "__main__":
    main()
