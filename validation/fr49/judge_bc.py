"""FR-49's judge for Parts B and C: World B, C1 and C2 against fr49-compartment-compositions-v1
(validation/fr49/REGISTRATION.md §4 and §5).

It reads the driver's records (validation/fr49/driver_bc.py: one record per registered run, the
engine's own values) and the code-blind references (B.json, C1.json and C2.json of the tag
fr49-references-2026-11-24). It writes every number to OUT/verdict.json. The lead runs it, after the
runs (D424). Its reader reads a references file by structure and declared inputs, never by value,
and was checked on the references' invented format samples (`--check-reader`) before its tag (D308).

**The criteria as written:**
- **World B** (§4.2):
  - B1: every host check on every row, so each of World B's honest runs completed;
  - B2: |n_L + B − L_T| ≤ 1e-10 L_T at lys on every row;
  - B3: 7.2 ≤ e_B(0.1 s)/e_B(0.05 s) ≤ 8.8; where e_B(0.1 s) < 1e-12 the ratio is not judged, and B
    passes if e_B(0.05 s) < 1e-12;
  - B4: |B − B*| ≤ 1e-10 B* at every sample with t ≥ 550 s, at both steps;
  - B5: lys's every species row and the population's R and B bit for bit the twin's on every row;
  - B6: the node-owned variant's site layout arrays bit for bit the facing population's, a host row
    with no compile.
- **C1** (§5): C1-1, O's and C's physical rows and label shares bit for bit the twin's on every row;
  C1-2, W's x and base amounts just after the wash within 1e-13 relative of LAWS.md §4's; C1-3,
  every host check, the label owner's closure included, so both runs completed.
- **C2** (§5): C2-1, each ligand conserved to 1e-10 of its total on every row; C2-2, B1's and B2's
  order windows with B3's floor rule; C2-3, |B_j − B_j*| ≤ 1e-10 B_j* at every sample with
  t ≥ 1800 s.

**The errors** (§1): e_q(h) = max_i |q_h(t_i) − q_ref(t_i)| / max_i |q_ref(t_i)| over the sample
times.

**The plants** (§4.2 and §5): World B's (a), the free-ligand Langmuir B = S c0/(K_d + c0) with
c0 = L_T/V_C, is this judge's substitution and must fail B4. World B's (b), (c) and (d) are runs and
must each fail B2, B4 or B5, against the honest twin for B5. C1's must fail C1-2, and C2's C2-3. A
plant run refused by a named check is reported as such, beside whether it fails a registered
criterion; only the latter is the registration's catch.

**The inconclusive rule** (the registration's preamble): a criterion that reads a reference value is
inconclusive, not a pass, where that reference reports a cross-check difference above its declared
accuracy. That is any `within` that is false in its `method`.

**Two readings,** to be ruled before this judge's tag:
- C1-2's "just after the wash" is the first saved row after the wash time, which is the step after
  900 s; "just before" is the row at 900 s. W has no route, so its amounts are constant in between.
- A plant's catch is a registered criterion's failure.

**The judge's literals** (RUNS) are its own table of the registered runs. Every record's job must
equal its row in world, step, horizon, observation interval, event and plant, or the judge refuses
the record. The lead also checks the table against the job files before any run (D424).

Usage (PYTHONPATH at a snapshot; the references taken from their tag with `git archive`):
  python -B -m validation.fr49.judge_bc --records RECORDS --references REFS --out OUT
  python -B -m validation.fr49.judge_bc --check-reader SAMPLES --cases INVENTED_CASES --out OUT
SAMPLES holds INVENTED_B.json, INVENTED_C1.json and INVENTED_C2.json, and INVENTED_CASES is the
invented cases file they were made from.
"""

import argparse
import json
from decimal import Decimal, InvalidOperation, localcontext
from pathlib import Path

import numpy as np

from validation.fr49.judge_l import KIND, LABELS_ONLY, PROTOCOL

SPEC = Path(__file__).resolve().parent / "references" / "spec" / "cases.json"
RECORD_KIND = "fr49 Parts B and C engine record, version 1"
# The registered runs (§4.1 and §5): id -> (world, dt s, horizon s, observed every s, event, plant).
RUNS = {
    "B-dt0.1": ("B", 0.1, 600.0, 5.0, True, None),
    "B-dt0.05": ("B", 0.05, 600.0, 5.0, True, None),
    "B-twin-dt0.1": ("B", 0.1, 600.0, 5.0, False, None),
    "B-plant-b-dt0.1": ("B", 0.1, 600.0, 5.0, True, "b"),
    "B-plant-c-dt0.1": ("B", 0.1, 600.0, 5.0, True, "c"),
    "B-plant-d-dt0.1": ("B", 0.1, 600.0, 5.0, True, "d"),
    "C1-dt2": ("C1", 2.0, 3600.0, 60.0, True, None),
    "C1-twin-dt2": ("C1", 2.0, 3600.0, 60.0, False, None),
    "C1-plant-dt2": ("C1", 2.0, 3600.0, 60.0, True, "c1"),
    "C2-dt0.1": ("C2", 0.1, 2000.0, 20.0, None, None),
    "C2-dt0.05": ("C2", 0.05, 2000.0, 20.0, None, None),
    "C2-plant-dt0.1": ("C2", 0.1, 2000.0, 20.0, None, "c2"),
}
JOB_FIELDS = ("world", "dt", "horizon_s", "every_s", "event", "plant")
# The bounds (§4.2 and §5), fixed before any reference value was seen.
CONSERVATION = 1e-10  # B2 and C2-1, relative to the total.
WINDOW = (7.2, 8.8)  # B3 and C2-2: third order (the site operator's SSPRK(3,3) half-steps).
FLOOR = 1e-12  # B3's floor rule, and C2-2's.
EQUILIBRIUM = 1e-10  # B4 and C2-3, relative to the equilibrium.
B4_FROM, C2_3_FROM = 550.0, 1800.0  # s: about 35 and 36 relaxation times.
WELL = 1e-13  # C1-2, relative.
SITES_PER_FMOL = Decimal(602214076)
# The references' layout (the spec README's "What to produce", as the format samples show it).
QUANTITIES = {
    "B": ("B", "n_L", "c"),
    "C1": ("n_O", "n_C", "x_O", "x_C", "base_O", "base_C", "share_x_O", "share_x_C"),
    "C2": ("B1", "B2", "c1", "c2", "R"),
}
ONCE = {
    "B": ("S", "K_d", "b", "c*", "B*", "B1", "B2", "lambda", "L_T", "d"),
    "C2": ("c1*", "c2*", "B1*", "B2*", "R*", "S", "K_1", "K_2"),
}
WELL_KEYS = tuple(
    f"{q}_{when}"
    for when in ("before", "after")
    for q in ("x_W", "b_W", "n_W", "share_x_W", "share_b_W")
)
DECLARED = {
    "B": ("V_C_pL", "sites", "k_on_per_mM_per_s", "k_off_per_s", "initial_fmol", "horizon_s"),
    "C1": ("V_W_pL", "initial_fmol"),
    "C2": ("V_C_pL", "sites", "ligands", "initial_bound_fmol", "horizon_s"),
}
SHARE_FIELDS = ("label_share", "label_outside_share")  # C1-1's shares, the label owner's fields.
assert set(SHARE_FIELDS) <= LABELS_ONLY  # The judge's explicit list (judge_l, erratum 1).


class ReaderError(ValueError):
    """A references file or a record not in its layout, or not answering the registered inputs."""


# ------------------------------------------------------------------ reading the references


def _equal(a, b):
    """Declared values equal as decimals, objects key by key and lists item by item."""
    if isinstance(a, dict) or isinstance(b, dict):
        if not (isinstance(a, dict) and isinstance(b, dict) and a.keys() == b.keys()):
            return False
        return all(_equal(a[k], b[k]) for k in a)
    if isinstance(a, list) or isinstance(b, list):
        if not (isinstance(a, list) and isinstance(b, list) and len(a) == len(b)):
            return False
        return all(_equal(x, y) for x, y in zip(a, b, strict=True))
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except InvalidOperation:
        return a == b


def _numbers(values, name):
    """A list of finite numbers (decimal strings or JSON numbers) in binary64, or ReaderError."""
    if not isinstance(values, list) or not values:
        raise ReaderError(f"{name} is missing or not a list")
    try:
        array = np.asarray([float(x) for x in values], dtype=float)
    except (TypeError, ValueError) as error:
        raise ReaderError(f"{name} holds an entry that is not a number") from error
    if not np.isfinite(array).all():
        raise ReaderError(f"{name} holds an entry that is not finite")
    return array


def _number(value, name):
    return float(_numbers([value], name)[0])


def cross_checks(method, path="method"):
    """[(path, within)] of every cross-check in a references file's method block: each dict that
    holds `within`, and a `within_declared_accuracy` flag."""
    found = []
    if isinstance(method, dict):
        for key, value in method.items():
            if key == "within" or key == "within_declared_accuracy":
                found.append((f"{path}.{key}", value is True))
            elif isinstance(value, dict):
                found += cross_checks(value, f"{path}.{key}")
    return found


def sample_times(world):
    """The registered sample times of a world, from its horizon and observation interval (RUNS)."""
    _, _, end, every, _, _ = next(r for r in RUNS.values() if r[0] == world)
    return [every * i for i in range(int(round(end / every)) + 1)]


def _indices(t, times, name):
    index = []
    for target in times:
        hit = np.flatnonzero(np.abs(t - target) <= 1e-9 * max(1.0, abs(target)))
        if not hit.size:
            raise ReaderError(f"the sample time {target:g} s is not among the {name}'s {t.size}")
        index.append(int(hit[0]))
    return index


def read_reference(path, world, *, cases=SPEC, invented=False):
    """{q: values at the registered sample times, "once": {...}, "well": {...},
    "cross_checks": [...]} from a references file in the results layout. It checks structure and
    declared inputs, never values:
    - kind, protocol and world;
    - `inputs.invented` is `invented`, so that a format sample is never judged as the references;
    - the declared inputs are `cases`'s for the world, compared as decimals, and so are the
      sample-time rule, the wash's time and fraction, and the sites per fmol;
    - `sample_times_s` holds each registered sample time, and each quantity is a list of finite
      numbers, one per sample time; each once value, and each of C1's well values, is finite.
    Raises ReaderError naming what is wrong, never a value."""
    doc = json.loads(Path(path).read_text())
    if not isinstance(doc, dict):
        raise ReaderError("the file is not a JSON object")
    for key, want in (("kind", KIND), ("protocol", PROTOCOL), ("world", world)):
        if doc.get(key) != want:
            raise ReaderError(f"{key} is {doc.get(key)!r}, not {want!r}")
    inputs = doc.get("inputs")
    if not isinstance(inputs, dict) or bool(inputs.get("invented", False)) != invented:
        raise ReaderError(
            "inputs.invented is not true: --check-reader reads a format sample only"
            if invented
            else "inputs.invented is true: a format sample, not the references"
        )
    spec = json.loads(Path(cases).read_text())["worlds"][world]
    declared = doc.get("declared")
    if not isinstance(declared, dict):
        raise ReaderError("declared is missing")
    for key in DECLARED[world]:
        if key not in declared or not _equal(declared[key], spec[key]):
            raise ReaderError(f"declared {key} is not world {world}'s in {cases}")
    if world in ("B", "C2"):
        if declared.get("sample_times_rule") != spec["sample_times_s"]["rule"]:
            raise ReaderError(f"declared sample_times_rule is not world {world}'s in {cases}")
        if not _equal(declared.get("sites_per_fmol"), str(SITES_PER_FMOL)):
            raise ReaderError("declared sites_per_fmol is not 602214076")
    if world == "B":
        wash = declared.get("wash_elsewhere") or {}
        for key in ("time_s", "fraction"):
            if not _equal(wash.get(key), spec["wash_elsewhere"][key]):
                raise ReaderError(f"declared wash_elsewhere.{key} is not world B's in {cases}")
    if world == "C1":
        wash = declared.get("wash") or {}
        for key in ("time_s", "fraction", "buffer_mM"):
            if not _equal(wash.get(key), spec["wash"][key]):
                raise ReaderError(f"declared wash.{key} is not C1's in {cases}")
        if not str(wash.get("buffer_label", "")).startswith("base"):
            raise ReaderError("declared wash.buffer_label is not the base")
    out = {}
    times = sample_times(world)
    t = _numbers(doc.get("sample_times_s"), "sample_times_s")
    index = _indices(t, times, "file")
    for q in QUANTITIES[world]:
        array = _numbers(doc.get(q), q)
        if array.shape != t.shape:
            raise ReaderError(f"{q} has {array.size} entries for {t.size} sample times")
        out[q] = array[index]
    if world in ONCE:
        once = doc.get("once")
        if not isinstance(once, dict):
            raise ReaderError("once is missing")
        out["once"] = {k: _number(once.get(k), f"once.{k}") for k in ONCE[world]}
    if world == "C1":
        well = doc.get("well")
        if not isinstance(well, dict):
            raise ReaderError("well is missing")
        out["well"] = {k: _number(well.get(k), f"well.{k}") for k in WELL_KEYS}
    checks = cross_checks(doc.get("method"))
    if not checks:
        raise ReaderError("method holds no cross-check")
    out["cross_checks"] = checks
    return out


# ------------------------------------------------------------------ reading the records


def read_record(records, run_id):
    """(record, {q: float array}, times, npz arrays or None) of one run's record, refused unless its
    job is the judge's own row for it (RUNS)."""
    path = Path(records) / f"{run_id}.json"
    record = json.loads(path.read_text())
    if record.get("kind") != RECORD_KIND or record.get("protocol") != PROTOCOL:
        raise ReaderError(f"{path} is not an FR-49 Parts B and C engine record")
    job = record.get("job", {})
    if job.get("id") != run_id or tuple(job.get(k) for k in JOB_FIELDS) != RUNS[run_id]:
        raise ReaderError(f"{path}: its job is not the registered run {run_id} (RUNS)")
    if record.get("outcome") != "completed":
        return record, None, None, None
    quantities = {
        k: np.asarray([float.fromhex(x) for x in v]) for k, v in record["quantities"].items()
    }
    times = np.asarray([float.fromhex(x) for x in record["times"]])
    arrays = np.load(Path(records) / f"{run_id}.npz")
    return record, quantities, times, arrays


def _bitwise(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


def _error(engine, reference):
    return float(np.max(np.abs(engine - reference)) / np.max(np.abs(reference)))


def _order(coarse, fine):
    """B3's rule: (ratio, judged, passed) for errors e(0.1 s) and e(0.05 s)."""
    judged = coarse >= FLOOR
    ratio = coarse / fine if fine > 0 else float("inf")
    passed = (WINDOW[0] <= ratio <= WINDOW[1]) if judged else fine < FLOOR
    return ratio, bool(judged), bool(passed)


def _criterion(passed, reads_reference, cross, **numbers):
    """A criterion's entry: passed, or inconclusive where it reads a reference whose cross-checks
    are not all within their declared accuracy."""
    inconclusive = reads_reference and not all(ok for _, ok in cross)
    return dict(passed=bool(passed) and not inconclusive, inconclusive=inconclusive, **numbers)


# ------------------------------------------------------------------ the parts


def declared_values(world, cases=SPEC):
    return json.loads(Path(cases).read_text())["worlds"][world]


def b_six():
    """B6, a host row: the node-owned variant's site layout arrays against the facing one's."""
    from cells.definitions.specs import parse_spec
    from cells.registry.models import get_model
    from validation.fr49 import worlds_bc as wb

    def layout(owner):
        spec = parse_spec(wb.world_b(owner=owner))
        return get_model(spec.model).initial_values(spec)[1]

    facing, owned = layout("patch"), layout("node")
    fields = [f for f in type(facing)._fields if f.startswith("site_")]
    differ = [f for f in fields if not _bitwise(getattr(facing, f), getattr(owned, f))]
    return dict(passed=not differ and len(fields) > 10, fields=len(fields), differing=differ)


def judge_b(records, reference):
    v = declared_values("B")
    total = Decimal(v["initial_fmol"]["n_L"]) + Decimal(v["initial_fmol"]["B"])
    cross, times = reference["cross_checks"], sample_times("B")
    b_star = reference["once"]["B*"]
    runs = {k: read_record(records, k) for k in RUNS if RUNS[k][0] == "B"}
    out = {}

    def conserved(run_id):
        _, q, _, _ = runs[run_id]
        gap = np.abs(q["n_L"] + q["B"] - float(total)) / float(total)
        return float(np.max(gap))

    def at_samples(run_id):
        _, q, t, _ = runs[run_id]
        return q["B"][_indices(t, times, f"record {run_id}")]

    late = np.asarray(times) >= B4_FROM

    def equilibrium(values):
        return float(np.max(np.abs(values[late] - b_star)) / b_star)

    honest = ("B-dt0.1", "B-dt0.05", "B-twin-dt0.1")
    completed = {k: runs[k][0]["outcome"] for k in honest}
    out["B1"] = dict(passed=all(o == "completed" for o in completed.values()), outcomes=completed)
    if not out["B1"]["passed"]:
        return out, {}
    gaps = {k: conserved(k) for k in honest}
    out["B2"] = dict(passed=all(g <= CONSERVATION for g in gaps.values()), relative_gap=gaps)
    e = {k: _error(at_samples(k), reference["B"]) for k in ("B-dt0.1", "B-dt0.05")}
    ratio, judged, passed = _order(e["B-dt0.1"], e["B-dt0.05"])
    out["B3"] = _criterion(passed, True, cross, e=e, ratio=ratio, judged=judged)
    eq = {k: equilibrium(at_samples(k)) for k in ("B-dt0.1", "B-dt0.05")}
    out["B4"] = _criterion(all(x <= EQUILIBRIUM for x in eq.values()), True, cross,
                           relative_gap=eq)  # fmt: skip
    a, b = runs["B-dt0.1"][3], runs["B-twin-dt0.1"][3]
    names = ("lys_rows", "site_free_increment_fmol", "site_bound_increment_fmol")
    differing = [n for n in names if not _bitwise(a[n], b[n])]
    out["B5"] = dict(passed=not differing, differing=differing,
                     wash_applied_at_the_well=int(a["wash_applied_well"][-1]),
                     wash_applied_at_the_well_in_the_twin=int(b["wash_applied_well"][-1]),
                     wash_applied_at_lys=int(np.max(a["wash_applied_lys"])))  # fmt: skip
    out["B6"] = b_six()

    plants = {}
    sites = v["sites"]
    with localcontext() as context:
        context.prec = 50
        capacity = (Decimal(sites["accessible_fraction"]) * int(sites["sites_per_copy"])
                    * Decimal(sites["copies"]) / SITES_PER_FMOL)  # fmt: skip
        k_d = Decimal(v["k_off_per_s"]) / Decimal(v["k_on_per_mM_per_s"])
        c0 = total / Decimal(v["V_C_pL"])
        langmuir = float(capacity * c0 / (k_d + c0))
    gap = abs(langmuir - b_star) / b_star
    plants["a"] = dict(caught=gap > EQUILIBRIUM, fails=["B4"] if gap > EQUILIBRIUM else [],
                       B4_relative_gap=gap)  # fmt: skip
    twin = runs["B-twin-dt0.1"][3]
    for name in ("b", "c", "d"):
        run_id = f"B-plant-{name}-dt0.1"
        record, q, t, arrays = runs[run_id]
        if q is None:
            plants[name] = dict(caught=False, fails=[], refused=record.get("refusal"))
            continue
        fails = []
        if conserved(run_id) > CONSERVATION:
            fails.append("B2")
        if equilibrium(at_samples(run_id)) > EQUILIBRIUM:
            fails.append("B4")
        if any(not _bitwise(arrays[n], twin[n]) for n in names):
            fails.append("B5")
        plants[name] = dict(caught=bool(fails), fails=fails, B2_gap=conserved(run_id),
                            B4_gap=equilibrium(at_samples(run_id)))  # fmt: skip
    return out, plants


def judge_c1(records, reference):
    v = declared_values("C1")
    # C1-2 reads the well's values only, so the well's own cross-checks decide its inconclusive
    # rule (World L's, also in C1.json, are World L's).
    cross = [(path, ok) for path, ok in reference["cross_checks"] if path.startswith("method.well")]
    t_wash = float(v["wash"]["time_s"])
    runs = {k: read_record(records, k) for k in RUNS if RUNS[k][0] == "C1"}
    out = {}
    completed = {k: runs[k][0]["outcome"] for k in ("C1-dt2", "C1-twin-dt2")}
    closure = {k: runs[k][0].get("label_closure_relative_max") for k in completed}
    out["C1-3"] = dict(passed=all(o == "completed" for o in completed.values()),
                       outcomes=completed, label_closure_relative_max=closure)  # fmt: skip
    if not out["C1-3"]["passed"]:
        return out, {}
    a, b = runs["C1-dt2"][3], runs["C1-twin-dt2"][3]
    names = ("O_rows", "C_rows", "O_shares", "C_shares")
    differing = [n for n in names if not _bitwise(a[n], b[n])]
    out["C1-1"] = dict(passed=not differing, differing=differing)

    def well(run_id):
        _, q, t, _ = runs[run_id]
        before = int(np.flatnonzero(np.abs(t - t_wash) <= 1e-9 * t_wash)[0])
        after = int(np.flatnonzero(t > t_wash * (1 + 1e-9))[0])
        n, x, base = q["n_W"], q["share_x_W"], q["share_base_W"]
        return dict(
            before_time=float(t[before]),
            after_time=float(t[after]),
            x_W_before=float(n[before] * x[before]),
            b_W_before=float(n[before] * base[before]),
            x_W_after=float(n[after] * x[after]),
            b_W_after=float(n[after] * base[after]),
        )

    ref = reference["well"]

    def gaps(found):
        return {k: abs(found[k] - ref[k]) / abs(ref[k]) for k in ("x_W_after", "b_W_after")}

    found = well("C1-dt2")
    out["C1-2"] = _criterion(all(g <= WELL for g in gaps(found).values()), True, cross,
                             engine=found, relative_gap=gaps(found),
                             before_gap={k: abs(found[k] - ref[k]) / abs(ref[k])
                                         for k in ("x_W_before", "b_W_before")})  # fmt: skip
    record, q, _, _ = runs["C1-plant-dt2"]
    if q is None:
        plants = {"c1": dict(caught=False, fails=[], refused=record.get("refusal"))}
    else:
        planted = gaps(well("C1-plant-dt2"))
        fails = ["C1-2"] if any(g > WELL for g in planted.values()) else []
        plants = {"c1": dict(caught=bool(fails), fails=fails, relative_gap=planted)}
    return out, plants


def judge_c2(records, reference):
    v = declared_values("C2")
    cross, times = reference["cross_checks"], sample_times("C2")
    once = reference["once"]
    totals = [float(Decimal(g["total_fmol"])) for g in v["ligands"]]
    runs = {k: read_record(records, k) for k in RUNS if RUNS[k][0] == "C2"}
    late = np.asarray(times) >= C2_3_FROM
    out = {}
    completed = {k: runs[k][0]["outcome"] for k in ("C2-dt0.1", "C2-dt0.05")}
    if not all(o == "completed" for o in completed.values()):
        out["C2-1"] = dict(passed=False, outcomes=completed)
        return out, {}

    def conserved(run_id):
        _, q, _, _ = runs[run_id]
        return {
            g["id"]: float(np.max(np.abs(q[f"n_{g['id']}"] + q[f"B{j + 1}"] - totals[j]))
                           / totals[j])
            for j, g in enumerate(v["ligands"])
        }  # fmt: skip

    def at_samples(run_id, q_name):
        _, q, t, _ = runs[run_id]
        return q[q_name][_indices(t, times, f"record {run_id}")]

    def equilibrium(run_id):
        return {
            f"B{j}": float(np.max(np.abs(at_samples(run_id, f"B{j}")[late] - once[f"B{j}*"]))
                           / once[f"B{j}*"])
            for j in (1, 2)
        }  # fmt: skip

    gaps = {k: conserved(k) for k in completed}
    out["C2-1"] = dict(passed=all(g <= CONSERVATION for run in gaps.values() for g in run.values()),
                       relative_gap=gaps)  # fmt: skip
    orders = {}
    for q_name in ("B1", "B2"):
        e = {k: _error(at_samples(k, q_name), reference[q_name]) for k in completed}
        ratio, judged, passed = _order(e["C2-dt0.1"], e["C2-dt0.05"])
        orders[q_name] = dict(e=e, ratio=ratio, judged=judged, passed=passed)
    out["C2-2"] = _criterion(all(o["passed"] for o in orders.values()), True, cross, **orders)
    eq = {k: equilibrium(k) for k in completed}
    out["C2-3"] = _criterion(all(g <= EQUILIBRIUM for run in eq.values() for g in run.values()),
                             True, cross, relative_gap=eq)  # fmt: skip
    record, q, _, _ = runs["C2-plant-dt0.1"]
    if q is None:
        plants = {"c2": dict(caught=False, fails=[], refused=record.get("refusal"))}
    else:
        planted = equilibrium("C2-plant-dt0.1")
        fails = ["C2-3"] if any(g > EQUILIBRIUM for g in planted.values()) else []
        plants = {"c2": dict(caught=bool(fails), fails=fails, relative_gap=planted)}
    return out, plants


def part_verdict(criteria, plants):
    """failed if a criterion failed or a plant was not caught; else inconclusive if a criterion
    was; else passed."""
    if any(not c["passed"] and not c.get("inconclusive") for c in criteria.values()):
        return "failed"
    if any(not p["caught"] for p in plants.values()):
        return "failed"
    if any(c.get("inconclusive") for c in criteria.values()):
        return "inconclusive"
    return "passed"


def judge(records, references):
    refs = Path(references)
    verdict = dict(protocol=PROTOCOL, parts={}, runs=list(RUNS))
    judges = {"B": judge_b, "C1": judge_c1, "C2": judge_c2}
    for world, judge_part in judges.items():
        reference = read_reference(refs / f"{world}.json", world)
        criteria, plants = judge_part(records, reference)
        verdict["parts"][world] = dict(
            verdict=part_verdict(criteria, plants),
            criteria=criteria,
            plants=plants,
            cross_checks=reference["cross_checks"],
        )
    parts = [p["verdict"] for p in verdict["parts"].values()]
    verdict["verdict"] = (
        "failed" if "failed" in parts else "inconclusive" if "inconclusive" in parts else "passed"
    )
    return verdict


def check_reader(samples, cases):
    """D308: the reader on the invented format samples, by structure, values unread."""
    report = {}
    for world in ("B", "C1", "C2"):
        path = Path(samples) / f"INVENTED_{world}.json"
        try:
            parsed = read_reference(path, world, cases=cases, invented=True)
            report[world] = dict(
                parsed=True,
                quantities={q: len(parsed[q]) for q in QUANTITIES[world]},
                once=sorted(parsed.get("once", {})),
                well=sorted(parsed.get("well", {})),
                cross_checks=len(parsed["cross_checks"]),
            )
        except ReaderError as error:
            report[world] = dict(parsed=False, why=str(error))
        try:  # Each sample, read as the references, is refused: the invented flag is checked.
            read_reference(path, world, cases=cases, invented=False)
            report[world]["refused_as_the_references"] = False
        except ReaderError:
            report[world]["refused_as_the_references"] = True
    report.update(samples=str(samples), cases=str(cases))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--records", type=Path, help="the driver's records of the registered runs")
    parser.add_argument(
        "--references", type=Path, help="B.json, C1.json and C2.json from their tag"
    )
    parser.add_argument(
        "--check-reader",
        type=Path,
        default=None,
        help="parse the invented format samples, structure only, and stop",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=None,
        help="with --check-reader: the invented cases.json of the samples",
    )
    args = parser.parse_args(argv)
    if (args.cases is None) != (args.check_reader is None):
        parser.error(
            "--check-reader and --cases go together; a judged run reads the registered spec"
        )
    args.out.mkdir(parents=True, exist_ok=True)
    if args.check_reader is not None:
        report = check_reader(args.check_reader, args.cases)
        (args.out / "reader_check.json").write_text(json.dumps(report, indent=1) + "\n")
        print(json.dumps(report, indent=1))
        return
    if args.records is None or args.references is None:
        parser.error("a judged run gives --records and --references")
    verdict = judge(args.records, args.references)
    (args.out / "verdict.json").write_text(json.dumps(verdict, indent=1, default=float) + "\n")
    print(json.dumps({w: p["verdict"] for w, p in verdict["parts"].items()}, indent=1),
          verdict["verdict"])  # fmt: skip


if __name__ == "__main__":
    main()
