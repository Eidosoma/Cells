"""The reader (CRITERIA.md C0): the reference files, then the engine's export folder.

**The reference files** (SPEC.md §7 and §8, amendments 1 and 2). `read_reference` parses one file
and checks every unit, every class against SPEC.md §4's rules, every echoed input against SPEC.md
(`spec.spec_inputs`, to 10⁻¹² relative), every scale against READOUTS.md §3 and every judged
entry's accuracy against 10⁻¹¹ s_y. A missing output time, run, readout or registered key, or a
non-finite value, is a fault; any fault refuses the file. Unknown keys are ignored (amendment 2,
Q6). The invented family's inputs are its own, so they are checked for consistency, not against
SPEC.md.

**The engine's export folder**, as this judge reads it (the spec folder does not state one):

    <export>/manifest.json   {"kind": "cells.fr38_v2.engine_export@1", "provenance": {...}}
    <export>/**/<any>.json   one run record per file:
    {
     "kind": "cells.fr38_v2.engine_run@1",
     "family": "AN",                    AF, AN, B, C or D
     "run": "p_sched returned",         SPEC.md §1.3's name, "blank" for a blank
     "role": "honest",                  honest, blank, twin, restart or plant
     "plant": null,                     a world-data or host-side plant: P2, P3a, P3b, P4, P5,
                                        P7, P8 (its run and its own blank) or P9
     "attempt": "primary",              primary (rungs 2, 1, 0.5 s) or retry (1, 0.5, 0.25 s)
     "dt_s": 0.5,                       the rung; a restart and every plant at 0.5 s
     "status": "completed",             or "refused": the engine refused the run at run time
     "refusal": null,                   the engine's own reason, when refused
     "definition": {...},               the run as the engine built it (below)
     "times_s": [0.0, 30.0, ...],       the family's output grid, exactly
     "series": {"n_R": [...], ...},     READOUTS.md §1 and §2 names, one value per output time,
                                        `excess_over_blank_<fate>` and `released_present_gross_
                                        <fate>` among them
     "route2": [{"fate": "durable", "ts_s": 5400.0, "value": ...}, ...],
     "survival": [{"fate": "durable", "t2_s": 5400.0, "ts_s": 9000.0, "alive_t2": ...,
                   "alive_ts": ..., "ratio": ... or null}, ...],
     "checks": {"<name>": float, ...}   optional: the engine's own checks, compared with the
                                        twin's bit for bit
    }

- **The definition** is the family's inputs in the references' echo vocabulary (`spec.
  spec_inputs`, without `runs` and `blank`), with the run's own values in place, plus `machine`,
  `p_schedule` ([[t, p], ...]), `label_at` (`release`, or `completion` under P4), `labelled`
  (false for a twin), `gene_unit_volume` (family D: `current`, or `declared` under P9) and, for
  the restart, `checkpoint_s`. A blank declares H0_copies 0 and k_I_per_mM_s 0.0; its p is not
  read. A plant declares its registered change (`spec.plant_delta`) and nothing else.
- **Required content.** Labelled runs, the restart and plants: every series the profile's mapping
  names, with `route2` and `survival`. Blanks: every series the blank carries. Twins: every
  physical series (no labels, no `released_present_gross`) and `route2`.
- **The judge's own plants.** P1 and P1″ act on the judge's mapping file, P1′ and P6 on copies of
  the honest records at h; a record naming any of them is refused.
- **Numbers** are finite, except a survival ratio, whose undefined, NaN or infinite values are
  judged by C1 at an idle fate (amendment 1, item 3); elsewhere a non-finite ratio is refused.
  The engine writes floats with `repr`; NaN and Infinity tokens parse here so that C0 can name
  them.
- **The manifest** carries the export's provenance (revision, dirty paths, snapshot), copied into
  the verdict; a missing or unreadable manifest is recorded there, not refused.
- Extra series and keys are ignored. A refused record is never read as a gap.
"""

import dataclasses
import hashlib
import json
import math
import os

import numpy as np

from . import spec

REFERENCE_KIND = "cells.fr38_v2.reference@1"
EXPORT_KIND = "cells.fr38_v2.engine_export@1"
RUN_KIND = "cells.fr38_v2.engine_run@1"
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
            try:
                mine = ctx.scale(e["scale"], rname)
            except (KeyError, ValueError) as exc:
                faults.append(f"{where}: its scale cannot be formed ({exc})")
                continue
            if not close(s.scale, mine, spec.SCALE_REL):
                faults.append(f"{where}: scale {s.scale!r} is not READOUTS.md §3's {mine!r}")
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


# ------------------------------------------------------------------ the engine export


@dataclasses.dataclass
class EngineRun:
    path: str
    sha256: str
    family: str
    run: str
    role: str
    plant: object
    attempt: str
    dt: float
    machine: str
    status: str
    refusal: object
    definition: dict
    series: dict  # name -> np.ndarray
    route2: dict  # (fate, ts) -> float
    survival: dict  # (fate, ts) -> (alive_t2, alive_ts, ratio or None)
    checks: dict
    faults: list
    times: list = dataclasses.field(default_factory=list)
    has_route2: bool = False
    has_survival: bool = False

    @property
    def key(self):
        return (
            self.family,
            self.role,
            self.run,
            self.plant,
            self.attempt,
            self.dt,
            self.machine
            if self.role == "blank" or self.plant == "P8" and self.run == "blank"
            else None,
        )


ROLES = ("honest", "blank", "twin", "restart", "plant")
RECORD_PLANTS = ("P2", "P3a", "P3b", "P4", "P5", "P7", "P8", "P9")


def read_export(folder):
    """The engine export's manifest and run records (not yet checked against the references)."""
    manifest_path = os.path.join(folder, "manifest.json")
    faults = []
    try:
        manifest, msha = load_lenient(manifest_path)
        if manifest.get("kind") != EXPORT_KIND:
            faults.append(f"manifest kind {manifest.get('kind')!r} is not {EXPORT_KIND!r}")
    except (OSError, ValueError) as exc:
        manifest, msha = {}, ""
        faults.append(f"manifest.json unreadable: {exc}")
    records = []
    for root, _, files in sorted(os.walk(folder)):
        for fn in sorted(files):
            if not fn.endswith(".json") or os.path.join(root, fn) == manifest_path:
                continue
            records.append(_read_record(os.path.join(root, fn)))
    return {"manifest": manifest, "manifest_sha256": msha, "faults": faults, "records": records}


def _read_record(path):
    faults = []
    try:
        doc, sha = load_lenient(path)
    except (OSError, ValueError) as exc:
        return EngineRun(
            path,
            "",
            "",
            "",
            "",
            None,
            "",
            0.0,
            "",
            "unreadable",
            None,
            {},
            {},
            {},
            {},
            {},
            [f"unreadable: {exc}"],
        )
    get = doc.get
    definition = get("definition") if isinstance(get("definition"), dict) else {}
    rec = EngineRun(
        path,
        sha,
        str(get("family", "")),
        str(get("run", "")),
        str(get("role", "")),
        get("plant"),
        str(get("attempt", "")),
        float(get("dt_s")) if _num(get("dt_s")) else 0.0,
        str(definition.get("machine", "")),
        str(get("status", "")),
        get("refusal"),
        definition,
        {},
        {},
        {},
        {},
        faults,
    )
    if get("kind") != RUN_KIND:
        faults.append(f"kind {get('kind')!r} is not {RUN_KIND!r}")
    if rec.role not in ROLES:
        faults.append(f"role {rec.role!r} is not one of {ROLES}")
    if rec.role == "plant" and rec.plant not in RECORD_PLANTS:
        faults.append(f"plant {rec.plant!r} is not an engine-record plant {RECORD_PLANTS}")
    if rec.role != "plant" and rec.plant is not None:
        faults.append("a record that is not a plant names no plant")
    if rec.attempt not in ("primary", "retry"):
        faults.append(f"attempt {rec.attempt!r} is not primary or retry")
    if rec.status not in ("completed", "refused"):
        faults.append(f"status {rec.status!r} is not completed or refused")
    if rec.status == "refused":
        return rec
    times = get("times_s")
    if not (isinstance(times, list) and all(isinstance(t, float) for t in times)):
        faults.append("times_s is not a list of floats")
        return rec
    rec.times = times
    series = get("series")
    if not isinstance(series, dict):
        faults.append("series is not a table")
        return rec
    for k, v in series.items():
        try:
            if not isinstance(v, list) or any(isinstance(x, (bool, str)) or x is None for x in v):
                raise TypeError
            arr = np.asarray(v, dtype=np.float64)
        except (TypeError, ValueError):
            arr = None
        if arr is None or arr.ndim != 1 or not np.all(np.isfinite(arr)):
            faults.append(f"series/{k}: not a list of finite numbers")
            continue
        rec.series[k] = arr
    for e in get("route2") or []:
        if not (
            isinstance(e, dict)
            and e.get("fate") in spec.FATES
            and _num(e.get("ts_s"))
            and _num(e.get("value"))
        ):
            faults.append(f"route2 entry {e!r}: fate, ts_s and a finite value")
            continue
        rec.route2[(e["fate"], float(e["ts_s"]))] = float(e["value"])
    for e in get("survival") or []:
        ok = (
            isinstance(e, dict)
            and e.get("fate") in spec.FATES
            and _num(e.get("ts_s"))
            and _num(e.get("t2_s"))
            and _num(e.get("alive_t2"))
            and _num(e.get("alive_ts"))
            and (e.get("ratio") is None or isinstance(e.get("ratio"), (int, float)))
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
    checks = get("checks") or {}
    if not isinstance(checks, dict):
        faults.append("checks is not a table")
    else:
        for k, v in checks.items():
            if not _num(v):
                faults.append(f"checks/{k}: {v!r} is not a finite number")
            else:
                rec.checks[k] = float(v)
    rec.has_route2 = "route2" in doc
    rec.has_survival = "survival" in doc
    return rec


def expected_definition(family_inputs, record, *, restart=None, gene_unit_volume=False):
    """SPEC.md's definition of the run the record names, with a plant's registered change."""
    d = {
        k: json.loads(json.dumps(v)) for k, v in family_inputs.items() if k not in ("runs", "blank")
    }
    if record.run == "blank":
        d["H0_copies"] = 0
        d["k_I_per_mM_s"] = 0.0
        d["machine"] = record.machine if record.machine in ("returned", "held") else "returned"
    else:
        rdef = family_inputs["runs"][record.run]
        d["machine"] = rdef["machine"]
        d["p_schedule"] = json.loads(json.dumps(rdef["p"]))
    d["label_at"] = "release"
    d["labelled"] = record.role != "twin"
    if gene_unit_volume:
        d["gene_unit_volume"] = "current"
    if record.role == "restart" and restart is not None:
        d["checkpoint_s"] = float(restart)
    if record.role == "plant":
        spec.plant_delta(record.plant, d, family_inputs)
    return d


def check_record(
    record,
    family_inputs,
    times,
    mapping,
    profile,
    *,
    restart=None,
    allowed_blank_machines=("returned",),
):
    """C0 on one engine record: its rung, grid, definition and required readouts."""
    faults = record.faults
    rungs = spec.PRIMARY_RUNGS if record.attempt == "primary" else spec.RETRY_RUNGS
    if record.dt not in rungs:
        faults.append(f"dt_s {record.dt!r} is not a rung of the {record.attempt} attempt {rungs}")
    if record.role in ("restart", "plant") and (
        record.dt != spec.H_STEP_S or record.attempt != "primary"
    ):
        faults.append("a restart or plant runs at h = 0.5 s, primary attempt only")
    horizon = float(family_inputs["horizon_s"])
    if record.dt > 0 and round(horizon / record.dt) * record.dt != horizon:
        faults.append("the horizon is not a whole number of steps")
    if record.run == "blank" and record.machine not in allowed_blank_machines:
        faults.append(
            f"a blank with machine {record.machine!r}; this family runs {allowed_blank_machines}"
        )
    if record.run != "blank" and record.run not in family_inputs["runs"]:
        faults.append(f"run {record.run!r} is not a run of family {record.family}")
        return
    if record.role not in ROLES or (record.role == "plant" and record.plant not in RECORD_PLANTS):
        return  # already refused: no registered definition to check it against
    expected = expected_definition(
        family_inputs, record, restart=restart, gene_unit_volume=profile == "D"
    )
    faults += [f"definition{f}" for f in compare_inputs(expected, record.definition)]
    if record.status == "refused":
        return
    if list(getattr(record, "times", [])) != list(times):
        faults.append("times_s is not the family's output grid (a missing output time)")
        return
    n = len(times)
    for k, v in record.series.items():
        if v.size != n:
            faults.append(f"series/{k}: {v.size} values for {n} output times")
    blank = record.run == "blank"
    for e in mapping_entries(mapping, profile, blank=True if blank else None):
        kind, _, name = e["engine"].partition("/")
        if kind == "series":
            if record.role == "twin" and (
                name.startswith("label_")
                or name.startswith("released_present_gross_")
                or name.startswith("excess_over_blank_")
            ):
                continue
            if name not in record.series:
                faults.append(f"series/{name}: missing readout")
        elif kind == "route2" and not blank:
            if not getattr(record, "has_route2", False):
                faults.append("route2: missing readout")
        elif kind == "survival" and not blank and record.role != "twin":
            if not getattr(record, "has_survival", False):
                faults.append("survival: missing readout")
