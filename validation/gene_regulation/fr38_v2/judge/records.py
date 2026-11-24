"""The reader (CRITERIA.md C0): the reference files, then the engine's export folder.

**The reference files** (SPEC.md §7 and §8, amendments 1 and 2). `read_reference` parses one file
and checks every unit, every class against SPEC.md §4's rules, every echoed input against SPEC.md
(`spec.spec_inputs`, to 10⁻¹² relative), every scale against READOUTS.md §3 and every judged
entry's accuracy against 10⁻¹¹ s_y. A missing output time, run, readout or registered key, or a
non-finite value, is a fault; any fault refuses the file. Unknown keys are ignored (amendment 2,
Q6). The invented family's inputs are its own, so they are checked for consistency, not against
SPEC.md.

**The engine's export** is amendment 4, §8's registered table (`read_tables`, `table_records`):
`table/table_<family>.json` for AF, AN, B, C and D with `table/SHA256SUMS`, and `table-retry/` for
the retry.

- **Runs.** `rungs` keyed by the step's repr, each with `dt_s` and `runs` by name: SPEC.md §1.3's
  names (B's `p=0.55 returned` and `p=0.55 held`), `blank returned` and `blank held` (each judged
  against the reference's one `blank`), and `<run> unlabelled` for a twin. Unknown names are
  recorded and ignored.
- **An entry** is a refusal (`refused`, `refusal`, `definition`) or holds `t`, `readouts`,
  `route2`, `survival` (labelled runs), `excess_over_blank` (runs with a blank), `checks`,
  `own_ledgers_at_end`, `steps`, `dt_s`, `definition`, `source`, `record` and `record_sha256`. A
  completed run without `source`, `record` or `record_sha256` is refused (item 6).
- **The restart** (AN) and **the plants** (rung "0.5", with `judged_as`; `P4 AN`, `P4 B`, `P8
  blank`) are entries of the same form. Entries for P1, P1′, P1″ and P6 are excluded from scoring
  and recorded: the judge forms those plants itself (item 5).
- **The declaration** is read at §8.5's keys (`definitions.py`). The judge forms S from the
  registered grid and g(ts) from the engine's counters; it never takes a tolerance term from the
  export, and records `steps` and `grid_error` only.
- **Open shapes.** Where §8 states a key but not its shape, the reader reads one narrow shape
  (`TABLE_OPEN_SHAPES` here, `definitions.OPEN_SHAPES` for the declaration) and fails closed on any
  other. Each needs a dated amendment before the judge's tag.
- **Numbers** are finite, except a survival ratio, whose undefined, NaN or infinite values are
  judged by C1 at an idle fate (amendment 1, item 3); elsewhere a non-finite ratio is refused.
- Extra keys are ignored. A refused record is never read as a gap.
"""

import dataclasses
import hashlib
import json
import math
import os

import numpy as np

from . import spec

REFERENCE_KIND = "cells.fr38_v2.reference@1"
UNITS = {"amount": "fmol", "energy": "pJ", "time": "s", "volume": "pL", "copy_fmol": spec.COPY_FMOL}


def _bits(x):
    return np.asarray(x, dtype=np.float64).view(np.uint64)


def is_pos_zero(x):
    return isinstance(x, float) and int(_bits(x)) == 0


def _refuse_constant(token):
    raise ValueError(f"non-finite token {token} (the reference writes null for undefined)")


def load_strict(path):
    """A JSON file whose numbers are all finite: NaN and Infinity tokens are refused."""
    raw = open(path, "rb").read()
    return json.loads(raw.decode("utf-8"), parse_constant=_refuse_constant), hashlib.sha256(
        raw
    ).hexdigest()


def load_lenient(path):
    raw = open(path, "rb").read()
    return json.loads(raw.decode("utf-8")), hashlib.sha256(raw).hexdigest()


def close(a, b, rel=spec.REL_INPUT):
    return abs(a - b) <= rel * max(abs(a), abs(b))


def compare_inputs(expected, got, path="", inexact=None):
    """Every expected key present and equal: numbers to 10⁻¹² relative, the rest exactly. Numbers
    within the tolerance but not the same double are listed in `inexact` (reported)."""
    faults = []
    if isinstance(expected, dict):
        if not isinstance(got, dict):
            return [f"{path}: expected a table, found {type(got).__name__}"]
        for k, v in expected.items():
            if k not in got:
                faults.append(f"{path}/{k}: missing")
            else:
                faults += compare_inputs(v, got[k], f"{path}/{k}", inexact)
        return faults
    if isinstance(expected, list):
        if not isinstance(got, list) or len(got) != len(expected):
            return [f"{path}: expected {expected!r}, found {got!r}"]
        for i, (a, b) in enumerate(zip(expected, got, strict=True)):
            faults += compare_inputs(a, b, f"{path}[{i}]", inexact)
        return faults
    if isinstance(expected, bool) or isinstance(expected, str) or expected is None:
        return (
            []
            if got == expected and type(got) is type(expected)
            else [f"{path}: expected {expected!r}, found {got!r}"]
        )
    if isinstance(got, bool) or not isinstance(got, (int, float)):
        return [f"{path}: expected the number {expected!r}, found {got!r}"]
    if not (math.isfinite(got) and close(float(expected), float(got))):
        return [f"{path}: expected {expected!r}, found {got!r} (beyond 10⁻¹² relative)"]
    if inexact is not None and float(expected) != float(got):
        inexact.append(f"{path}: {got!r} where SPEC.md's double is {expected!r}")
    return []


# ------------------------------------------------------------------ the internal record types


@dataclasses.dataclass
class RefSeries:
    """One reference readout over the output times: its classes, values, accuracies, scale."""

    constant: np.ndarray  # bool
    value: np.ndarray
    accuracy: np.ndarray  # NaN where null (a constant entry)
    scale: float


@dataclasses.dataclass
class RefRun:
    name: str
    blank: bool
    idle: object  # the idle fate or None
    series: dict
    excess: dict  # fate -> RefSeries
    route2: dict  # fate -> {ts: entry}
    survival: dict  # fate -> {ts: entry}
    not_compared: dict  # name -> np.ndarray
    checks: dict


@dataclasses.dataclass
class Reference:
    family: str
    profile: str
    path: str
    sha256: str
    inputs: dict
    times: np.ndarray
    samples: list
    window: tuple
    runs: dict
    plants: list
    method: dict
    provenance: dict
    faults: list
    notes: list

    @property
    def accepted(self):
        return not self.faults


def mapping_entries(mapping, profile, *, blank=None, status=None):
    out = []
    for e in mapping["readouts"]:
        st = e["status"].get(profile)
        if st is None or (status is not None and st != status):
            continue
        if blank is True and not e["blank"]:
            continue
        out.append(e)
    return out


# ------------------------------------------------------------------ the reference reader


def read_reference(path, family, profile, mapping, *, expected_inputs=None):
    """C0 on one reference file. `expected_inputs` is SPEC.md's (None for the invented family,
    whose inputs are its own)."""
    from . import rules  # the scales of READOUTS.md §3

    faults, notes = [], []
    try:
        doc, sha = load_strict(path)
    except (OSError, ValueError) as exc:
        return Reference(
            family,
            profile,
            path,
            "",
            {},
            np.zeros(0),
            [],
            (0.0, 0.0),
            {},
            [],
            {},
            {},
            [f"unreadable: {exc}"],
            [],
        )
    ref = Reference(
        family, profile, path, sha, {}, np.zeros(0), [], (0.0, 0.0), {}, [], {}, {}, faults, notes
    )
    for key in (
        "kind",
        "family",
        "inputs",
        "units",
        "times_s",
        "samples_s",
        "runs",
        "plants",
        "method",
        "provenance",
    ):
        if key not in doc:
            faults.append(f"missing registered key {key!r}")
    if faults:
        return ref
    if doc["kind"] != REFERENCE_KIND:
        faults.append(f"kind {doc['kind']!r} is not {REFERENCE_KIND!r}")
    if doc["family"] != family:
        faults.append(f"family {doc['family']!r} where {family!r} is read")
    # units
    units = doc["units"]
    for k, v in UNITS.items():
        if k not in units:
            faults.append(f"units/{k}: missing")
        elif isinstance(v, float):
            if not (isinstance(units[k], float) and units[k] == v):
                faults.append(f"units/{k}: {units[k]!r}, not the double {v!r}")
        elif units[k] != v:
            faults.append(f"units/{k}: {units[k]!r}, not {v!r}")
    inputs = doc["inputs"]
    ref.inputs = inputs
    # inputs
    if expected_inputs is not None:
        inexact = []
        faults += [f"inputs{f}" for f in compare_inputs(expected_inputs, inputs, "", inexact)]
        notes += [f"inputs{x} (within 10⁻¹² relative)" for x in inexact]
        notes.append(
            "SPEC.md inputs the echo does not carry (structure, not a fault): "
            + "; ".join(spec.UNECHOED_STRUCTURE)
        )
    for key in (
        "H0_copies",
        "tau_s",
        "k_I_per_mM_s",
        "k_d_per_s",
        "k_s_per_s",
        "p_sched",
        "window_s",
        "runs",
        "label_schedule_s",
        "samples_s",
        "horizon_s",
        "output_interval_s",
        "mu0_RT_at_1M",
    ):
        if key not in inputs:
            faults.append(f"inputs/{key}: missing registered key")
    if faults:
        return ref
    try:
        expected_times = spec.grid(inputs)
    except (KeyError, ValueError, TypeError) as exc:
        faults.append(f"inputs: no output grid ({exc})")
        return ref
    times = doc["times_s"]
    if not (
        isinstance(times, list)
        and len(times) == len(expected_times)
        and all(isinstance(a, float) and a == b for a, b in zip(times, expected_times, strict=True))
    ):
        faults.append(
            f"times_s is not the grid of {len(expected_times)} outputs "
            f"{inputs['output_interval_s']!r} s apart"
        )
        return ref
    ref.times = np.asarray(times, dtype=np.float64)
    samples = doc["samples_s"]
    if samples != inputs["samples_s"] or any(s not in times for s in samples):
        faults.append(f"samples_s {samples!r} are not the inputs' sample times on the grid")
        return ref
    ref.samples = [float(s) for s in samples]
    window = tuple(float(x) for x in inputs["window_s"])
    sched = inputs["label_schedule_s"]
    if window != (float(sched["win"]), float(sched["post"])) or window[1] != ref.samples[0]:
        faults.append(
            f"window_s {window!r} is not the label schedule's W with t2 the first sample time"
        )
        return ref
    ref.window = window
    # the runs
    expected_runs = list(inputs["runs"])
    for r in expected_runs:
        if r not in doc["runs"]:
            faults.append(f"runs/{r!r}: missing")
    for r in doc["runs"]:
        if r not in expected_runs:
            notes.append(f"runs/{r!r}: not a run of this family, ignored")
    if faults:
        return ref
    for name in expected_runs:
        run = _read_run(doc["runs"][name], name, ref, mapping, rules)
        ref.runs[name] = run
    if faults:
        return ref
    _check_scales_and_accuracy(ref, mapping, rules)
    _read_plants(doc["plants"], ref)
    _read_method(doc["method"], ref)
    _read_provenance(doc["provenance"], ref)
    if family == "invented":
        _check_invented_exercises(ref)
    return ref


def _check_invented_exercises(ref):
    """SPEC.md §8: the invented file has at most 61 outputs, an idle fate, a blank with
    `excess_over_blank`, and an entry for each core plant (every arm-A series is required above)."""
    if len(ref.times) > 61:
        ref.faults.append(f"the invented grid has {len(ref.times)} outputs, more than 61")
    if not any(r.idle for r in ref.runs.values()):
        ref.faults.append("the invented file has no idle fate (SPEC.md §8)")
    if "blank" not in ref.runs or not any(r.excess for r in ref.runs.values()):
        ref.faults.append("the invented file has no blank and excess_over_blank (SPEC.md §8)")
    sized = {e["plant"] for e in ref.plants}
    missing = [p for p in spec.CORE_PLANTS if p not in sized]
    if missing:
        ref.faults.append(f"the invented file sizes no entry of {missing} (SPEC.md §8)")


def _series_from(obj, n, where, faults, *, judged_constant_ok=True):
    """One {class, value, accuracy, scale} block, checked entry by entry."""
    for k in ("class", "value", "accuracy", "scale"):
        if k not in obj:
            faults.append(f"{where}: missing {k!r}")
            return None
    cl, val, acc, scale = obj["class"], obj["value"], obj["accuracy"], obj["scale"]
    if not all(isinstance(x, list) and len(x) == n for x in (cl, val, acc)):
        faults.append(
            f"{where}: class, value and accuracy are not {n} parallel entries "
            "(a missing output time)"
        )
        return None
    if not (
        isinstance(scale, (int, float))
        and not isinstance(scale, bool)
        and math.isfinite(scale)
        and scale >= 0.0
    ):
        faults.append(f"{where}: scale {scale!r} is not a finite non-negative number")
        return None
    constant = np.zeros(n, dtype=bool)
    value = np.zeros(n)
    accuracy = np.full(n, np.nan)
    for i, (c, v, a) in enumerate(zip(cl, val, acc, strict=True)):
        if c == "spread":
            faults.append(f"{where}[{i}]: a spread entry is refused (CRITERIA.md §2)")
            return None
        if c not in ("constant", "stepped"):
            faults.append(f"{where}[{i}]: class {c!r} is not constant or stepped")
            return None
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)):
            faults.append(f"{where}[{i}]: value {v!r} is not a finite number")
            return None
        if c == "constant":
            if not is_pos_zero(float(v)) or not isinstance(v, float):
                faults.append(f"{where}[{i}]: a constant entry is +0.0 exactly, not {v!r}")
                return None
            if a is not None:
                faults.append(f"{where}[{i}]: a constant entry's accuracy is null, not {a!r}")
                return None
            constant[i] = True
        else:
            if not (
                isinstance(a, (int, float))
                and not isinstance(a, bool)
                and math.isfinite(a)
                and a >= 0.0
            ):
                faults.append(
                    f"{where}[{i}]: a stepped entry's accuracy {a!r} is not a finite "
                    "non-negative number"
                )
                return None
            accuracy[i] = float(a)
        value[i] = float(v)
    return RefSeries(constant, value, accuracy, float(scale))


def _read_run(obj, name, ref, mapping, rules):
    faults, n = ref.faults, len(ref.times)
    blank = name == "blank"
    idle = None if blank else spec.idle_fate(spec.run_p(ref.inputs, name))
    run = RefRun(name, blank, idle, {}, {}, {}, {}, {}, {})
    need = ["series", "checks"]
    if not blank:
        need += ["route2", "survival", "not_compared"]
        if spec.has_blank(ref.profile):
            need.append("excess_over_blank")
    for k in need:
        if k not in obj:
            faults.append(f"runs/{name!r}: missing {k!r}")
    if any(k not in obj for k in need):
        return run
    for e in mapping_entries(mapping, ref.profile, blank=True if blank else None):
        kind, _, rname = e["reference"].partition("/")
        if kind != "series":
            continue
        where = f"runs/{name!r}/series/{rname}"
        if rname not in obj["series"]:
            faults.append(f"{where}: missing readout")
            continue
        s = _series_from(obj["series"][rname], n, where, faults)
        if s is None:
            continue
        expect = np.asarray(
            spec.constant_mask(rname, ref.times, ref.window, blank=blank, idle=idle)
        )
        bad = np.nonzero(expect != s.constant)[0]
        if bad.size:
            i = int(bad[0])
            faults.append(
                f"{where}: class at t = {float(ref.times[i])!r} s is "
                f"{'constant' if s.constant[i] else 'stepped'}, SPEC.md §4 makes it "
                f"{'constant' if expect[i] else 'stepped'} ({bad.size} entries)"
            )
        run.series[rname] = s
    if blank:
        run.checks = _read_checks(obj["checks"], f"runs/{name!r}/checks", faults)
        return run
    if spec.has_blank(ref.profile):
        for fate in spec.FATES:
            where = f"runs/{name!r}/excess_over_blank/{fate}"
            if fate not in obj["excess_over_blank"]:
                faults.append(f"{where}: missing readout")
                continue
            s = _series_from(obj["excess_over_blank"][fate], n, where, faults)
            if s is not None and s.constant.any():
                faults.append(f"{where}: the excess over the blank is never constant (SPEC.md §4)")
            if s is not None:
                run.excess[fate] = s
    run.route2 = _read_route2(obj["route2"], name, idle, ref, run)
    run.survival = _read_survival(obj["survival"], name, idle, ref, run)
    for fate in spec.FATES:
        key = f"cohort_net_{fate}"
        vals = obj["not_compared"].get(key)
        if not (
            isinstance(vals, list)
            and len(vals) == n
            and all(
                isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                for v in vals
            )
        ):
            faults.append(f"runs/{name!r}/not_compared/{key}: missing, short or non-finite")
            continue
        run.not_compared[key] = np.asarray(vals, dtype=np.float64)
    run.checks = _read_checks(obj["checks"], f"runs/{name!r}/checks", faults)
    return run


def _read_checks(obj, where, faults):
    if not isinstance(obj, dict):
        faults.append(f"{where}: not a table")
        return {}
    out = {}
    for k, v in obj.items():
        if not (isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)):
            faults.append(f"{where}/{k}: {v!r} is not a finite number")
        else:
            out[k] = float(v)
    return out


def _num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x)


def _read_route2(entries, name, idle, ref, run):
    """Amendment 1, item 1: one entry per fate and sample time; the `win` class there."""
    faults, out = ref.faults, {f: {} for f in spec.FATES}
    if not isinstance(entries, list):
        faults.append(f"runs/{name!r}/route2: not a list")
        return out
    for e in entries:
        where = f"runs/{name!r}/route2/{e.get('fate')!r}@{e.get('ts_s')!r}"
        if not all(k in e for k in ("fate", "ts_s", "class", "value", "accuracy", "scale")):
            faults.append(f"{where}: missing a registered key")
            continue
        if e["fate"] not in spec.FATES or e["ts_s"] not in ref.samples:
            faults.append(f"{where}: not a fate and sample time")
            continue
        out[e["fate"]][float(e["ts_s"])] = e
    for fate in spec.FATES:
        row = spec.FATE_ROW[fate]
        win = run.series.get(f"label_{row}_win")
        for ts in ref.samples:
            where = f"runs/{name!r}/route2/{fate}@{ts!r}"
            e = out[fate].get(ts)
            if e is None:
                faults.append(f"{where}: missing entry")
                continue
            if idle == fate:
                if not (
                    e["class"] == "constant" and is_pos_zero(e["value"]) and e["accuracy"] is None
                ):
                    faults.append(
                        f"{where}: at an idle fate the entry is constant +0.0 with null accuracy"
                    )
                continue
            if e["class"] != "stepped" or not (
                _num(e["value"])
                and _num(e["accuracy"])
                and _num(e["scale"])
                and e["accuracy"] >= 0.0
            ):
                faults.append(f"{where}: a stepped entry with finite value, accuracy and scale")
                continue
            if win is not None:
                i = int(np.searchsorted(ref.times, ts))
                if not (
                    close(e["value"], win.value[i], spec.ULP_REL)
                    and close(e["accuracy"], win.accuracy[i], spec.ULP_REL)
                ):
                    faults.append(
                        f"{where}: value and accuracy are not the win class's there "
                        "(amendment 1, item 1)"
                    )
    return out


def _read_survival(entries, name, idle, ref, run):
    """Amendment 1, item 3: both counts and the ratio, at each later sample time."""
    faults, out = ref.faults, {f: {} for f in spec.FATES}
    if not isinstance(entries, list):
        faults.append(f"runs/{name!r}/survival: not a list")
        return out
    t2 = ref.window[1]
    for e in entries:
        where = f"runs/{name!r}/survival/{e.get('fate')!r}@{e.get('ts_s')!r}"
        if not all(
            k in e for k in ("fate", "t2_s", "ts_s", "alive_t2", "alive_ts", "ratio", "accuracy")
        ):
            faults.append(f"{where}: missing a registered key")
            continue
        if e["fate"] not in spec.FATES or e["t2_s"] != t2 or e["ts_s"] not in ref.samples[1:]:
            faults.append(f"{where}: not a fate, t2 and later sample time")
            continue
        out[e["fate"]][float(e["ts_s"])] = e
    for fate in spec.FATES:
        win = run.series.get(f"label_{spec.FATE_ROW[fate]}_win")
        for ts in ref.samples[1:]:
            where = f"runs/{name!r}/survival/{fate}@{ts!r}"
            e = out[fate].get(ts)
            if e is None:
                faults.append(f"{where}: missing entry")
                continue
            acc = e["accuracy"]
            if not (isinstance(acc, list) and len(acc) == 3):
                faults.append(f"{where}: accuracy is not three entries")
                continue
            if idle == fate:
                if not (
                    is_pos_zero(e["alive_t2"])
                    and is_pos_zero(e["alive_ts"])
                    and e["ratio"] is None
                    and acc == [None, None, None]
                ):
                    faults.append(
                        f"{where}: at an idle fate both counts are +0.0 with null "
                        "accuracy and the ratio is null (amendment 1, item 3)"
                    )
                continue
            if not (
                all(_num(x) for x in (e["alive_t2"], e["alive_ts"], e["ratio"]))
                and all(_num(a) and a >= 0.0 for a in acc)
                and e["alive_t2"] > 0.0
            ):
                faults.append(f"{where}: finite counts, ratio and accuracies, with alive_t2 > 0")
                continue
            if win is not None:
                i2 = int(np.searchsorted(ref.times, t2))
                i3 = int(np.searchsorted(ref.times, ts))
                if not (
                    close(e["alive_t2"], win.value[i2], spec.ULP_REL)
                    and close(e["alive_ts"], win.value[i3], spec.ULP_REL)
                ):
                    faults.append(f"{where}: the counts are not the win class at t2 and ts")
            if not close(e["ratio"], e["alive_ts"] / e["alive_t2"], spec.ULP_REL):
                faults.append(f"{where}: the ratio is not alive_ts / alive_t2")
    return out


def _check_scales_and_accuracy(ref, mapping, rules):
    """READOUTS.md §3's scales from the reference's own solution; accuracy ≤ 10⁻¹¹ s_y."""
    faults = ref.faults
    blank = ref.runs.get("blank")
    for name, run in ref.runs.items():
        values = {k: s.value for k, s in run.series.items()}
        ctx = rules.ScaleContext(
            ref.profile,
            ref.inputs,
            values,
            blank=run.blank,
            blank_values=None if blank is None else {k: s.value for k, s in blank.series.items()},
        )
        entries = mapping_entries(mapping, ref.profile, blank=True if run.blank else None)
        for e in entries:
            kind, _, rname = e["reference"].partition("/")
            judged = e["status"][ref.profile] == "judged"
            if kind == "series":
                s = run.series.get(rname)
                where = f"runs/{name!r}/series/{rname}"
            elif kind == "excess_over_blank":
                s = run.excess.get(rname)
                where = f"runs/{name!r}/excess_over_blank/{rname}"
            elif kind == "route2":
                _check_route2_scale(ref, run, rname, ctx, e, judged)
                continue
            elif kind == "survival":
                _check_survival_accuracy(ref, run, rname, ctx, e, judged)
                continue
            else:
                continue
            if s is None:
                continue
            # amendment 4, item 1: a stated scale is checked where a judged entry's accuracy
            # requirement rests on it; a reported entry's departure is recorded, not refused
            try:
                mine = ctx.scale(e["scale"], rname)
            except (KeyError, ValueError) as exc:
                (faults if judged else ref.notes).append(
                    f"{where}: its scale cannot be formed ({exc})"
                )
                continue
            if not close(s.scale, mine, spec.SCALE_REL):
                msg = f"{where}: scale {s.scale!r} is not READOUTS.md §3's {mine!r}"
                if judged:
                    faults.append(msg)
                else:
                    ref.notes.append(msg + " (a reported entry: recorded, not refused)")
                continue
            if judged:
                over = np.nonzero(~s.constant & (s.accuracy > spec.ACCURACY_FACTOR * mine))[0]
                if over.size:
                    i = int(over[0])
                    faults.append(
                        f"{where}: accuracy {float(s.accuracy[i])!r} at t = "
                        f"{float(ref.times[i])!r} s "
                        f"exceeds 10⁻¹¹ s_y = {spec.ACCURACY_FACTOR * mine!r} "
                        f"({over.size} entries)"
                    )


def _check_route2_scale(ref, run, fate, ctx, e, judged):
    mine = ctx.scale(e["scale"])
    for ts, entry in run.route2.get(fate, {}).items():
        if entry["class"] != "stepped":
            continue
        where = f"runs/{run.name!r}/route2/{fate}@{ts!r}"
        if not close(float(entry["scale"]), mine, spec.SCALE_REL):
            ref.faults.append(
                f"{where}: scale {entry['scale']!r} is not the release counter's maximum {mine!r}"
            )
        elif judged and entry["accuracy"] > spec.ACCURACY_FACTOR * mine:
            ref.faults.append(f"{where}: accuracy {entry['accuracy']!r} exceeds 10⁻¹¹ s_y")


def _check_survival_accuracy(ref, run, fate, ctx, e, judged):
    mine = ctx.scale(e["scale"])
    for ts, entry in run.survival.get(fate, {}).items():
        if entry["ratio"] is None or not judged:
            continue
        a2, a3, ar = entry["accuracy"]
        if max(a2, a3) > spec.ACCURACY_FACTOR * mine or ar > spec.ACCURACY_FACTOR * 1.0:
            ref.faults.append(
                f"runs/{run.name!r}/survival/{fate}@{ts!r}: an accuracy exceeds "
                "10⁻¹¹ s_y (the label's scale, 1 for the ratio)"
            )


def _read_plants(entries, ref):
    faults = ref.faults
    if not isinstance(entries, list):
        faults.append("plants: not a list")
        return
    names = set()
    for i, e in enumerate(entries):
        where = f"plants[{i}]"
        if not all(
            k in e
            for k in (
                "plant",
                "run",
                "quantity",
                "time_s",
                "honest",
                "planted",
                "relative_distance",
            )
        ):
            faults.append(f"{where}: missing a registered key")
            continue
        if e["plant"] not in spec.CORE_PLANTS + ("P8", "P9"):
            faults.append(f"{where}: unknown plant {e['plant']!r}")
            continue
        if e["run"] not in ref.runs or e["time_s"] not in list(ref.times):
            faults.append(f"{where}: run {e['run']!r} or time {e['time_s']!r} not in the file")
            continue
        if not all(_num(e[k]) for k in ("honest", "planted", "relative_distance")):
            faults.append(f"{where}: honest, planted and relative_distance are finite numbers")
            continue
        names.add(e["plant"])
        ref.plants.append(e)
    for p in spec.REFERENCE_PLANTS.get(ref.family, ()):
        if p not in names:
            faults.append(f"plants: no entry sizes {p} (SPEC.md §6)")


def _read_method(m, ref):
    for k in (
        "primary",
        "second",
        "tolerances",
        "safety_factor",
        "largest_difference_between_methods",
        "run_time_s",
    ):
        if k not in m:
            ref.faults.append(f"method/{k}: missing registered key")
    if "safety_factor" in m and not (_num(m["safety_factor"]) and m["safety_factor"] >= 2.0):
        ref.faults.append(f"method/safety_factor {m['safety_factor']!r} is below 2 (SPEC.md §3)")
    if m.get("run_time_s") != "out/run_times.json":
        ref.faults.append("method/run_time_s is not the sidecar's path (amendment 2, Q5)")
    ref.method = m


def _read_provenance(p, ref):
    for k in (
        "revision",
        "dirty_paths",
        "writer_version",
        "python",
        "numpy",
        "scipy",
        "mpmath",
        "sha256_of_this_file_excluded",
    ):
        if k not in p:
            ref.faults.append(f"provenance/{k}: missing registered key")
    if p.get("sha256_of_this_file_excluded") is not True:
        ref.faults.append("provenance/sha256_of_this_file_excluded is not true (amendment 2)")
    ref.provenance = p


# ------------------------------------------------------------------ the engine's tables (§8)

TABLE_KIND = "cells.fr38_v2.engine_table@1"
TABLE_DIRS = (("primary", "table"), ("retry", "table-retry"))
RUNG_KEYS = {"primary": ("2.0", "1.0", "0.5"), "retry": ("1.0", "0.5", "0.25")}
ROLES = ("honest", "blank", "twin", "restart", "plant")
RECORD_PLANTS = ("P2", "P3a", "P3b", "P4", "P5", "P7", "P8", "P9")
TABLE_PLANTS = {"P2": "P2", "P3a": "P3a", "P3b": "P3b", "P4 AN": "P4", "P4 B": "P4",
                "P5": "P5", "P7": "P7", "P8": "P8", "P8 blank": "P8", "P9": "P9"}  # fmt: skip
JUDGE_PLANTS = ("P1", "P1′", "P1″", "P6", "P1'", "P1''")  # formed by the judge (amendment 4, §5)
TABLE_OPEN_SHAPES = (
    "`route2`: a list of {fate, ts_s, value, grid_error}; `grid_error` is recorded beside the "
    "judge's own g(ts), never used",
    "`survival`: a list of {fate, t2_s, ts_s, alive_t2, alive_ts, ratio}",
    '`excess_over_blank`: {"blank": <the matched blank\'s name>, "durable": [...], '
    '"short_lived": [...]}',
    '`plants`: under rung "0.5", an object keyed by the plant\'s name: P2, P3a, P3b, "P4 AN", '
    '"P4 B", P5, P7, P8, "P8 blank" (judged_as "blank returned"), P9',
    "`restart`: a top-level entry of AN's table; the checkpoint's identity under `checkpoint`, "
    "required",
    "provenance: `source` and `record` any non-empty value, `record_sha256` a sha256 string, all "
    "three keys of the entry itself",
    "`checks`: any JSON value; the restart and AF's two blanks compare it whole, the twin as a "
    "recursive subset of its labelled run's (bit for bit)",
    "a `SHA256SUMS` line: `<sha256>  <file name>`",
)


@dataclasses.dataclass
class EngineRun:
    table: str
    table_sha256: str
    family: str
    name: str
    run: str
    role: str
    plant: object
    attempt: str
    dt: float
    machine: str
    status: str
    refusal: object
    definition: object
    series: dict = dataclasses.field(default_factory=dict)  # name -> np.ndarray
    route2: dict = dataclasses.field(default_factory=dict)  # (fate, ts) -> value
    route2_grid_error: dict = dataclasses.field(default_factory=dict)  # recorded, never used
    survival: dict = dataclasses.field(default_factory=dict)  # (fate, ts) -> (a2, a3, ratio)
    checks: object = None
    faults: list = dataclasses.field(default_factory=list)
    notes: list = dataclasses.field(default_factory=list)
    times: list = dataclasses.field(default_factory=list)
    has_route2: bool = False
    has_survival: bool = False
    has_excess: bool = False
    excess_blank: object = None
    steps: object = None
    provenance: dict = dataclasses.field(default_factory=dict)
    extras: dict = dataclasses.field(default_factory=dict)
    unchecked: list = dataclasses.field(default_factory=list)

    @property
    def key(self):
        blankish = self.role == "blank" or (self.plant == "P8" and self.run == "blank")
        return (self.family, self.role, self.run, self.plant, self.attempt, self.dt,
                self.machine if blankish else None)  # fmt: skip


def _read_sums(path):
    sums = {}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            digest, _, name = line.partition("  ")
            sums[name.strip().lstrip("*")] = digest.strip()
    return sums


def read_tables(export_dir, families):
    """The engine's hashed tables: table/table_<family>.json with table/SHA256SUMS, and
    table-retry/ for the retry (amendment 4, §8.1). A missing SHA256SUMS is recorded and flagged to
    the checker (item 6); a table whose hash departs from an index that lists it is refused."""
    out = {"tables": [], "faults": [], "notes": [], "index": {}}
    for attempt, sub in TABLE_DIRS:
        d = os.path.join(export_dir, sub)
        if not os.path.isdir(d):
            if attempt == "primary":
                out["faults"].append(f"{sub}/ is missing: every primary run is missing")
            continue
        sums_path = os.path.join(d, "SHA256SUMS")
        sums = _read_sums(sums_path) if os.path.exists(sums_path) else None
        out["index"][sub] = {"SHA256SUMS": sums is not None}
        if sums is None:
            out["notes"].append(f"FLAG for the checker: {sub}/SHA256SUMS is missing (recorded, "
                                "not refused; amendment 4, item 6)")  # fmt: skip
        for fam in families:
            fn = f"table_{fam}.json"
            path = os.path.join(d, fn)
            if not os.path.exists(path):
                out["notes"].append(f"{sub}/{fn} is absent")
                continue
            tab = {"family": fam, "attempt": attempt, "path": path, "faults": [], "doc": None}
            try:
                tab["doc"], tab["sha256"] = load_lenient(path)
            except (OSError, ValueError) as exc:
                tab["faults"].append(f"{sub}/{fn} unreadable: {exc}")
                tab["sha256"] = ""
            if sums is not None:
                if fn not in sums:
                    tab["faults"].append(f"{sub}/{fn} is not in {sub}/SHA256SUMS")
                elif sums[fn] != tab["sha256"]:
                    tab["faults"].append(f"{sub}/{fn}'s sha256 departs from {sub}/SHA256SUMS "
                                         "(refused: a table changed after its index)")  # fmt: skip
            out["tables"].append(tab)
    return out


def _classify(name, honest_runs):
    if name in honest_runs:
        return "honest", name, None
    if name in ("blank returned", "blank held"):
        return "blank", "blank", name.split()[1]
    if name.endswith(" unlabelled") and name[: -len(" unlabelled")] in honest_runs:
        return "twin", name[: -len(" unlabelled")], None
    return None


def table_records(tab, family_inputs):
    """Every run entry of one table, as engine records; unknown names and the judge's own plants
    are recorded and left out (amendment 4, items 5 and 8)."""
    doc, fam, attempt = tab["doc"], tab["family"], tab["attempt"]
    notes, recs = [], []
    table_faults = list(tab["faults"])
    if isinstance(doc, dict):
        if doc.get("kind") != TABLE_KIND:
            table_faults.append(f"kind {doc.get('kind')!r} is not {TABLE_KIND!r}")
        if doc.get("family") != fam:
            table_faults.append(f"family {doc.get('family')!r} in table_{fam}.json")
        for key in ("window_s", "samples_s"):
            want = [float(x) for x in family_inputs[key]]
            got = doc.get(key)
            if not (
                isinstance(got, list)
                and len(got) == len(want)
                and all(_num(a) and float(a) == b for a, b in zip(got, want, strict=True))
            ):
                table_faults.append(f"{key} {got!r} is not SPEC.md's {want!r}")
        if doc.get("missing"):
            notes.append(f"the table lists missing records: {doc.get('missing')!r}")
        rungs = doc.get("rungs")
    else:
        table_faults.append("the table is not an object")
        rungs = None
    if not isinstance(rungs, dict):
        table_faults.append("rungs is not an object")
        rungs = {}
    honest = [r for r in family_inputs["runs"] if r != "blank"]

    def make(entry, name, role, run, plant, dt, machine):
        rec = EngineRun(tab["path"], tab.get("sha256", ""), fam, name, run, role, plant, attempt,
                        dt, machine or "", "", None, None)  # fmt: skip
        rec.faults += table_faults
        _read_entry(rec, entry)
        recs.append(rec)
        return rec

    for key, rung in rungs.items():
        if key not in RUNG_KEYS[attempt]:
            notes.append(f"rung {key!r} is not a rung of the {attempt} attempt: ignored")
            continue
        dt = float(key)
        if not isinstance(rung, dict) or not isinstance(rung.get("runs"), dict):
            table_faults.append(f"rung {key}: no runs")
            continue
        if not (_num(rung.get("dt_s")) and float(rung["dt_s"]) == dt):
            table_faults.append(f"rung {key}: dt_s {rung.get('dt_s')!r}")
        for name, entry in rung["runs"].items():
            c = _classify(name, honest)
            if c is None:
                notes.append(f"rung {key}: run {name!r} is not a registered name: ignored")
                continue
            role, run, machine = c
            make(entry, name, role, run, None, dt, machine)
        plants = rung.get("plants")
        if plants is None:
            continue
        if key != "0.5" or attempt != "primary" or not isinstance(plants, dict):
            notes.append(f"rung {key}: plants outside the primary rung 0.5, or not an object: "
                         "ignored")  # fmt: skip
            continue
        for name, entry in plants.items():
            if name in JUDGE_PLANTS:
                notes.append(f"plant entry {name!r}: formed by the judge itself, excluded from "
                             "scoring and recorded (amendment 4, item 5)")  # fmt: skip
                continue
            if name not in TABLE_PLANTS:
                notes.append(f"plant entry {name!r} is not a registered name: ignored")
                continue
            plant = TABLE_PLANTS[name]
            judged_as = entry.get("judged_as") if isinstance(entry, dict) else None
            if name == "P8 blank":
                run, machine = "blank", "returned"
                ok = judged_as == "blank returned"
            else:
                run, machine = judged_as, None
                ok = judged_as in honest
            rec = make(entry, name, "plant", run if ok else str(judged_as), plant, dt, machine)
            rec.extras["judged_as"] = judged_as
            if not ok:
                rec.faults.append(f"plant {name!r}: judged_as {judged_as!r} is not its honest run")
    if attempt == "primary" and isinstance(doc, dict) and doc.get("restart") is not None:
        rec = make(doc["restart"], "restart", "restart", "p_sched returned", None, 0.5, None)
        cp = doc["restart"].get("checkpoint") if isinstance(doc["restart"], dict) else None
        rec.extras["checkpoint"] = cp
        if cp is None and rec.status == "completed":
            rec.faults.append("the restart carries no checkpoint identity (`checkpoint`)")
    return recs, notes


def _read_entry(rec, entry):
    """One run's entry (§8.3): a refusal, or its records with their provenance."""
    faults = rec.faults
    if not isinstance(entry, dict):
        faults.append("the entry is not an object")
        return
    rec.definition = entry.get("definition")
    if entry.get("refused"):
        rec.status, rec.refusal = "refused", entry.get("refusal")
        return
    rec.status = "completed"
    for k in ("source", "record", "record_sha256"):
        v = entry.get(k)
        empty = v is None or (isinstance(v, (str, list, dict)) and not v)
        if empty or (k == "record_sha256" and not isinstance(v, str)):
            faults.append(f"{k} is missing: a run without its provenance is refused")
        rec.provenance[k] = v
    sha = rec.provenance.get("record_sha256")
    if (
        isinstance(sha, str)
        and sha
        and not (len(sha) == 64 and all(c in "0123456789abcdef" for c in sha))
    ):
        faults.append(f"record_sha256 {sha!r} is not a sha256")
    t = entry.get("t")
    if not (isinstance(t, list) and all(_num(x) for x in t)):
        faults.append("t is not a list of output times")
    else:
        rec.times = [float(x) for x in t]
    if not (_num(entry.get("dt_s")) and float(entry["dt_s"]) == rec.dt):
        faults.append(f"dt_s {entry.get('dt_s')!r} is not its rung's {rec.dt!r}")
    steps = entry.get("steps")
    rec.steps = steps if isinstance(steps, int) and not isinstance(steps, bool) else None
    readouts = entry.get("readouts")
    if not isinstance(readouts, dict):
        faults.append("readouts is not an object")
        readouts = {}
    for k, v in readouts.items():
        arr = _finite_array(v)
        if arr is None:
            faults.append(f"readouts/{k}: not a list of finite numbers")
        else:
            rec.series[k] = arr
    ex = entry.get("excess_over_blank")
    if ex is not None:
        rec.has_excess = True
        if not isinstance(ex, dict):
            faults.append("excess_over_blank is not an object")
        else:
            rec.excess_blank = ex.get("blank")
            for fate in spec.FATES:
                arr = _finite_array(ex.get(fate))
                if arr is None:
                    faults.append(f"excess_over_blank/{fate}: not a list of finite numbers")
                else:
                    rec.series[f"excess_over_blank_{fate}"] = arr
    r2 = entry.get("route2")
    if r2 is not None:
        rec.has_route2 = True
        for e in r2 if isinstance(r2, list) else [None]:
            if not (isinstance(e, dict) and e.get("fate") in spec.FATES and _num(e.get("ts_s"))
                    and _num(e.get("value"))):  # fmt: skip
                faults.append(f"route2 entry {e!r}: fate, ts_s and a finite value")
                continue
            rec.route2[(e["fate"], float(e["ts_s"]))] = float(e["value"])
            rec.route2_grid_error[(e["fate"], float(e["ts_s"]))] = e.get("grid_error")
    sv = entry.get("survival")
    if sv is not None:
        rec.has_survival = True
        for e in sv if isinstance(sv, list) else [None]:
            ok = (
                isinstance(e, dict)
                and e.get("fate") in spec.FATES
                and _num(e.get("ts_s"))
                and _num(e.get("t2_s"))
                and _num(e.get("alive_t2"))
                and _num(e.get("alive_ts"))
                and (
                    e.get("ratio") is None
                    or (
                        isinstance(e.get("ratio"), (int, float))
                        and not isinstance(e.get("ratio"), bool)
                    )
                )
            )
            if not ok:
                faults.append(f"survival entry {e!r}: fate, t2_s, ts_s, finite counts and a ratio")
                continue
            r = e["ratio"]
            rec.survival[(e["fate"], float(e["ts_s"]))] = (
                float(e["alive_t2"]),
                float(e["alive_ts"]),
                None if r is None else float(r),
            )
    rec.checks = entry.get("checks")
    for k in ("own_ledgers_at_end", "source"):
        if k in entry:
            rec.extras[k] = entry[k] if k == "source" else "present"


def _finite_array(v):
    if not isinstance(v, list) or any(isinstance(x, (bool, str)) or x is None for x in v):
        return None
    try:
        arr = np.asarray(v, dtype=np.float64)
    except (TypeError, ValueError):
        return None
    if arr.ndim != 1 or not np.all(np.isfinite(arr)):
        return None
    return arr


def matched_blank_name(family_inputs, run, two_blanks):
    machine = family_inputs["runs"][run]["machine"] if two_blanks else "returned"
    return f"blank {machine}"


def check_record(rec, family_inputs, times, mapping, profile, *, allowed_blank_machines,
                 two_blanks):  # fmt: skip
    """C0 on one engine record: its rung, grid, provenance, readouts and declaration (plants'
    declarations are compared with their honest runs' in the judge, §8.5)."""
    from . import definitions

    faults = rec.faults
    rungs = spec.PRIMARY_RUNGS if rec.attempt == "primary" else spec.RETRY_RUNGS
    if rec.dt not in rungs:
        faults.append(f"dt {rec.dt!r} is not a rung of the {rec.attempt} attempt {rungs}")
    if rec.role in ("restart", "plant") and (rec.dt != spec.H_STEP_S or rec.attempt != "primary"):
        faults.append("a restart or plant runs at h = 0.5 s, primary attempt only")
    if rec.run == "blank" and rec.machine not in allowed_blank_machines:
        faults.append(f"a blank {rec.machine!r}; this family runs {allowed_blank_machines}")
    if rec.role != "plant" and rec.status in ("completed", "refused"):
        df, unchecked = definitions.check_definition(
            rec.definition, family_inputs, profile, rec.run, rec.role, rec.machine, rec.dt
        )
        faults += df
        rec.unchecked = unchecked
    if rec.status != "completed":
        return
    S = int(round(float(family_inputs["horizon_s"]) / rec.dt)) if rec.dt else None
    if rec.steps is not None and rec.steps != S:
        rec.notes.append(f"steps {rec.steps} where the registered grid gives S = {S}: C2 and C4 "
                         "use the grid's S, never the export's")  # fmt: skip
    if list(rec.times) != list(times):
        faults.append("t is not the family's output grid (a missing output time)")
        return
    n = len(times)
    for k, v in rec.series.items():
        if v.size != n:
            faults.append(f"{k}: {v.size} values for {n} output times")
    blank = rec.run == "blank"
    p8_blank = rec.plant == "P8" and blank
    for e in mapping_entries(mapping, profile, blank=True if blank else None):
        kind, _, name = e["engine"].partition("/")
        if kind == "series":
            if rec.role == "twin" and (
                name.startswith("label_") or name.startswith("released_present_gross_")
            ):
                continue
            if name not in rec.series:
                faults.append(f"readouts/{name}: missing readout")
        elif kind == "route2" and not blank and not rec.has_route2:
            faults.append("route2: missing readout")
        elif kind == "survival" and not blank and rec.role != "twin" and not rec.has_survival:
            faults.append("survival: missing readout")
    if spec.has_blank(profile) and not blank and not p8_blank:
        if rec.role == "plant" and rec.plant == "P8":
            want = "P8 blank"
        elif rec.role == "plant":
            want = None  # its excess enters no criterion: the name is recorded only
        else:
            want = matched_blank_name(family_inputs, rec.run, two_blanks)
        if want is not None and rec.excess_blank != want:
            faults.append(f"excess_over_blank names the blank {rec.excess_blank!r}, not "
                          f"its matched {want!r}")  # fmt: skip
