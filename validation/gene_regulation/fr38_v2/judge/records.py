"""The reader (CRITERIA.md C0): the reference files, then the engine's export folder.

**The reference files** (SPEC.md §7 and §8, amendments 1 and 2). `read_reference` parses one file
and checks every unit, every class against SPEC.md §4's rules, every echoed input against SPEC.md
(`spec.spec_inputs`, to 10⁻¹² relative), every scale against READOUTS.md §3 and every judged
entry's accuracy against 10⁻¹¹ s_y. A missing output time, run, readout or registered key, or a
non-finite value, is a fault; any fault refuses the file. Unknown keys are ignored (amendment 2,
Q6). The invented family's inputs are its own, so they are checked for consistency, not against
SPEC.md.

**The engine's export** is the registered tables (amendment 4, §8; amendment 5):
`table/table_<family>.json` for AF, AN, B, C and D with `table/SHA256SUMS`, and `table-retry/` for
the retry.

- **Two passes.** The structure pass (`shapes.structure`) reads keys, nesting and types, by name,
  as the format sample's check reads them. Where it finds no fault, the value pass here reads the
  numbers, and C0's echo (`definitions`) the declaration.
- **What refuses.** A missing or mistyped pinned key; a table that departs from `SHA256SUMS`, is not
  listed there, or is the format sample's; a dirty checkout; a missing or doubled `route2` or
  `survival` entry; a checkpoint or a V₀ patch that is not the registered one; a grid, readout or
  declaration that is not SPEC.md's. Each is named by path. A refusal is never read as a gap.
- **What is recorded** (amendment 5, item 4): extra keys, unregistered names, engine_run's other
  exports, a blank's `route2` and `survival`, `blank`, `k_per_s`, `steps`, `host_patch`, the three
  other keys of `checkpoint` and the four of `source`. What departs is flagged to the checker.
- **What the judge forms itself:** S from the registered grid, g(ts) from the engine's counters, and
  the plants P1, P1′, P1″ and P6, whose entries are excluded (amendment 4, item 5).
- **Numbers** are finite, except a survival ratio, whose undefined, NaN or infinite values are
  judged by C1 at an idle fate (amendment 1, item 3); elsewhere a non-finite ratio is refused.
"""

import dataclasses
import hashlib
import json
import math
import os
import re

import numpy as np

from . import definitions, shapes, spec

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


def _unique(pairs):
    out = dict(pairs)
    if len(out) != len(pairs):
        keys = [k for k, _ in pairs]
        raise ValueError(f"a key is repeated: {sorted({k for k in keys if keys.count(k) > 1})}")
    return out


def load_lenient(path):
    """An engine table: no key repeated (a repeated run would hide the other), and NaN and Infinity
    tokens parsed, so that C0 can name them."""
    raw = open(path, "rb").read()
    return (
        json.loads(raw.decode("utf-8"), object_pairs_hook=_unique),
        hashlib.sha256(raw).hexdigest(),
    )


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


# ------------------------------------------------------------------ the engine's tables


TABLE_DIRS = (("primary", "table"), ("retry", "table-retry"))
ROLES = ("honest", "blank", "twin", "restart", "plant")
RECORD_PLANTS = ("P2", "P3a", "P3b", "P4", "P5", "P7", "P8", "P9")


@dataclasses.dataclass
class EngineRun:
    """One entry of a table, read by the structure pass and, where it finds no fault, by value."""

    table: str
    table_sha256: str
    family: str
    where: str
    name: str
    kind: str
    run: str
    role: str
    plant: object
    attempt: str
    dt: float
    machine: str
    status: str = ""
    refusal: object = None
    record: object = None
    definition: object = None
    series: dict = dataclasses.field(default_factory=dict)  # name -> np.ndarray
    route2: dict = dataclasses.field(default_factory=dict)  # (fate, ts) -> value
    route2_grid_error: dict = dataclasses.field(default_factory=dict)  # recorded, never used
    route2_k: dict = dataclasses.field(default_factory=dict)  # recorded, flagged if it departs
    survival: dict = dataclasses.field(default_factory=dict)  # (fate, ts) -> (a2, a3, ratio)
    checks: object = None
    own_ledgers: object = None
    faults: list = dataclasses.field(default_factory=list)
    notes: list = dataclasses.field(default_factory=list)
    flags: list = dataclasses.field(default_factory=list)
    times: list = dataclasses.field(default_factory=list)
    steps: object = None
    blank_name: object = None
    source: dict = dataclasses.field(default_factory=dict)
    recorded: dict = dataclasses.field(default_factory=dict)

    @property
    def blank(self):
        return self.run == "blank"

    @property
    def key(self):
        return (self.family, self.role, self.run, self.plant, self.attempt, self.dt,
                self.machine if self.blank else None)  # fmt: skip


_SUM = re.compile(r"^([0-9a-fA-F]{64})  ([^/]+)$")


def read_sums(path):
    """A SHA256SUMS file (amendment 5, item 5): the digest, two spaces and the file's name. A
    malformed line, or one name with two digests, leaves the table it should name unlisted."""
    sums, bad, twice = {}, [], set()
    with open(path, encoding="utf-8") as fh:
        for line in fh.read().splitlines():
            if not line.strip():
                continue
            m = _SUM.match(line)
            if not m:
                bad.append(line)
                continue
            digest, name = m.group(1).lower(), m.group(2)
            if name in sums and sums[name] != digest:
                twice.add(name)
            sums[name] = digest
    for name in twice:
        sums.pop(name)
        bad.append(f"two digests for {name}")
    return sums, bad


def read_tables(export_dir, families, sample=None):
    """The hashed tables: table/table_<family>.json with table/SHA256SUMS, and table-retry/ for the
    retry (amendment 4, §8.1; amendment 5, §4 (a) and §6). A missing SHA256SUMS is recorded and
    flagged to the checker. A table whose hash departs from it, or that it does not list, is
    refused, and so are a listed table that is missing and one whose hash is one of `sample`'s."""
    out = {"tables": [], "faults": [], "notes": [], "flags": [], "index": {}}
    for attempt, sub in TABLE_DIRS:
        d = os.path.join(export_dir, sub)
        if not os.path.isdir(d):
            if attempt == "primary":
                out["faults"].append(f"{sub}/ is missing: every primary run is missing")
            continue
        sums_path = os.path.join(d, "SHA256SUMS")
        sums, bad = read_sums(sums_path) if os.path.exists(sums_path) else (None, [])
        out["index"][sub] = {"SHA256SUMS": sums is not None, "malformed_lines": bad}
        if sums is None:
            out["flags"].append(f"{sub}/SHA256SUMS is missing (recorded, not refused; amendment "
                                "4, item 6)")  # fmt: skip
        for fn in sorted(sums or ()):
            if not os.path.exists(os.path.join(d, fn)):
                out["faults"].append(f"{sub}/{fn} is listed in {sub}/SHA256SUMS and missing from "
                                     "the folder (§4 (a): refused)")  # fmt: skip
            elif not any(fn == f"table_{f}.json" for f in families):
                out["notes"].append(f"{sub}/{fn} is listed and is not a table judged here")
        for fam in families:
            fn = f"table_{fam}.json"
            path = os.path.join(d, fn)
            if not os.path.exists(path):
                out["notes"].append(f"{sub}/{fn} is absent")
                continue
            tab = {"family": fam, "attempt": attempt, "path": path, "file": f"{sub}/{fn}",
                   "faults": [], "doc": None, "sha256": ""}  # fmt: skip
            try:
                tab["doc"], tab["sha256"] = load_lenient(path)
            except (OSError, ValueError) as exc:
                tab["faults"].append(f"{sub}/{fn} unreadable: {exc}")
            if sums is not None:
                if fn not in sums:
                    tab["faults"].append(f"{sub}/{fn} is not listed in {sub}/SHA256SUMS")
                elif sums[fn] != tab["sha256"]:
                    tab["faults"].append(f"{sub}/{fn}'s sha256 departs from {sub}/SHA256SUMS")
            if sample and tab["sha256"] in sample.values():
                tab["faults"].append(f"{sub}/{fn} is the registered format sample's, refused in "
                                     "judgement (amendment 5, §6)")  # fmt: skip
            out["tables"].append(tab)
    return out


def table_structure(tab, profile, role, inputs, restart_run, table_shapes):
    """The structure pass of one table (`shapes.structure`), as the judgement and the sample check
    both run it."""
    honest = [r for r in inputs["runs"] if r != "blank"]
    return shapes.structure(tab["doc"], tab["family"], tab["attempt"], profile, role, honest,
                            table_shapes, restart_run=restart_run)  # fmt: skip


def _finding(f):
    kind, path, detail = f
    return f"{path}: {kind}: {detail}"


def table_records(tab, st, inputs, times, samples, window):
    """Every entry of one table as an engine record: the structure pass's faults, then its values.
    Returns (records, table faults)."""
    table_faults = list(tab["faults"]) + [_finding(f) for f in st.faults]
    doc = tab["doc"] if isinstance(tab["doc"], dict) else {}
    if not st.faults:
        for key in ("window_s", "samples_s"):
            want = [float(x) for x in inputs[key]]
            got = doc[key]
            if len(got) != len(want) or not all(
                close(float(a), b) for a, b in zip(got, want, strict=True)
            ):
                table_faults.append(f"{key}: {got!r} is not SPEC.md's {want!r}")
        for key, rung in doc["rungs"].items():
            if key in shapes.RUNG_KEYS[tab["attempt"]] and not close(
                float(rung["dt_s"]), float(key)
            ):
                table_faults.append(f"rungs.{key}.dt_s: {rung['dt_s']!r} is not its key's step")
    recs = []
    for e in st.entries:
        rec = EngineRun(tab["path"], tab["sha256"], tab["family"], e.where, e.name, e.kind, e.run,
                        e.role, e.plant, tab["attempt"], e.dt, e.machine or "")  # fmt: skip
        rec.faults += table_faults + [_finding(f) for f in e.faults]
        rec.notes += [_finding(f) for f in e.findings if f[0] not in shapes.FAULTS]
        if e.definition_findings:
            rec.recorded["definition_shape"] = [_finding(f) for f in e.definition_findings]
        if isinstance(e.obj, dict):
            rec.definition = e.obj.get("definition")
            rec.status = "refused" if e.kind == "refused" else "completed"
        if not rec.faults and rec.status == "refused":
            rec.refusal, rec.record = e.obj["refusal"], e.obj["record"]
        elif not rec.faults:
            _values(rec, e.obj, times, samples, window)
        recs.append(rec)
    return recs, table_faults


def _matched(x, times):
    """The registered time x is, at 10⁻¹² relative (amendment 5, item 4), or None."""
    return next((t for t in times if close(float(x), t)), None)


def _values(rec, obj, times, samples, window):
    """The value pass of one completed entry, whose keys and types the structure pass accepted."""
    faults = rec.faults
    for k, v in obj["readouts"].items():
        rec.series[k] = np.asarray(v, dtype=np.float64)
    for fate, v in obj.get("excess_over_blank", {}).items():
        rec.series[f"excess_over_blank_{fate}"] = np.asarray(v, dtype=np.float64)
    rec.times = [float(x) for x in obj["t"]]
    rec.steps, rec.checks, rec.own_ledgers = obj["steps"], obj["checks"], obj["own_ledgers_at_end"]
    rec.record, rec.source, rec.blank_name = obj["record"], obj["source"], obj["blank"]
    rec.recorded["record_sha256"] = obj["record_sha256"]
    for k in ("checkpoint", "host_patch", "judged_as"):
        if k in obj:
            rec.recorded[k] = obj[k]
    if not close(float(obj["dt_s"]), rec.dt):
        faults.append(f"{rec.where}.dt_s: {obj['dt_s']!r} is not its step {rec.dt!r}")
    if obj["source"]["checkout_dirty"] is not False:
        faults.append(f"{rec.where}.source.checkout_dirty: the run's checkout was dirty (item 5)")
    if rec.blank:
        return  # item 4: a blank's route2 and survival are recorded, never judged
    for i, e in enumerate(obj["route2"]):
        ts = _matched(e["ts_s"], samples)
        if e["fate"] not in spec.FATES or ts is None:
            faults.append(f"{rec.where}.route2[{i}]: no registered fate and sample time")
            continue
        if (e["fate"], ts) in rec.route2:
            faults.append(f"{rec.where}.route2[{i}]: ({e['fate']}, {ts!r} s) is duplicated")
        rec.route2[(e["fate"], ts)] = float(e["value"])
        rec.route2_grid_error[(e["fate"], ts)] = float(e["grid_error"])
        rec.route2_k[(e["fate"], ts)] = float(e["k_per_s"])
    for fate in spec.FATES:
        for ts in samples:
            if (fate, ts) not in rec.route2:
                faults.append(f"{rec.where}.route2: missing ({fate}, {ts!r} s)")
    if "survival" not in obj:
        return
    for i, e in enumerate(obj["survival"]):
        ts = _matched(e["ts_s"], samples[1:])
        if e["fate"] not in spec.FATES or ts is None or _matched(e["t2_s"], [window[1]]) is None:
            faults.append(f"{rec.where}.survival[{i}]: no registered fate, t2 and later sample")
            continue
        if (e["fate"], ts) in rec.survival:
            faults.append(f"{rec.where}.survival[{i}]: ({e['fate']}, {ts!r} s) is duplicated")
        r = e["ratio"]
        rec.survival[(e["fate"], ts)] = (float(e["alive_t2"]), float(e["alive_ts"]),
                                         None if r is None else float(r))  # fmt: skip
    for fate in spec.FATES:
        for ts in samples[1:]:
            if (fate, ts) not in rec.survival:
                faults.append(f"{rec.where}.survival: missing ({fate}, {ts!r} s)")


def check_record(rec, inputs, times, mapping, profile, *, blank_machines, two_blanks,
                 checkpoint_s):  # fmt: skip
    """C0 on one record's values: its grid, readouts and declaration. A plant's declaration is
    compared with its honest run's in the judge (§8.5)."""
    faults = rec.faults
    if rec.role == "blank" and rec.machine not in blank_machines:
        faults.append(f"{rec.where}: a blank {rec.machine!r}; this family runs {blank_machines}")
    if rec.status not in ("completed", "refused"):
        return
    if rec.role != "plant" and isinstance(rec.definition, dict):
        faults += definitions.check_definition(
            rec.definition, inputs, profile, rec.run, rec.role, rec.machine, rec.dt
        )
        values, flags = definitions.recorded(rec.definition, inputs, profile)
        rec.recorded["declaration"] = values
        rec.flags += [f"definition.{x}" for x in flags]
    if rec.status != "completed" or not rec.source:
        return
    n = len(times)
    if len(rec.times) != n or any(not close(a, b) for a, b in zip(rec.times, times, strict=True)):
        faults.append(f"{rec.where}.t: not the family's output grid (a missing output time)")
        return
    for k, v in rec.series.items():
        if v.size != n:
            faults.append(f"{rec.where}: {k} has {v.size} values for {n} output times")
    S = int(round(float(inputs["horizon_s"]) / rec.dt))
    if rec.steps != S:
        rec.flags.append(f"{rec.where}.steps: {rec.steps}, where the registered grid gives S = {S} "
                         "(§4 (d): S comes from the grid)")  # fmt: skip
    _required(rec, mapping, profile)
    _flag_rates(rec)
    want = None
    if rec.plant == "P8" and not rec.blank:
        want = "P8 blank"
    elif rec.role in ("honest", "twin", "restart") and spec.has_blank(profile):
        want = f"blank {inputs['runs'][rec.run]['machine'] if two_blanks else 'returned'}"
    if rec.blank_name != want:
        rec.flags.append(f"{rec.where}.blank: {rec.blank_name!r}, where its matched blank is "
                         f"{want!r} (recorded, never judged: item 4)")  # fmt: skip
    if rec.source["snapshot_patch_sha256"] != shapes.EMPTY_SHA256:
        rec.flags.append(f"{rec.where}.source.snapshot_patch_sha256: not an empty file's")
    if rec.role == "restart":
        got = rec.recorded["checkpoint"]["time_s"]
        if not close(float(got), checkpoint_s):
            faults.append(f"{rec.where}.checkpoint.time_s: {got!r}, not {checkpoint_s!r} s")
    if rec.plant == "P9":
        hp = rec.recorded["host_patch"]
        if hp["id"] != "V0" or hp["operator"] != shapes.GENE_UNIT:
            faults.append(f"{rec.where}.host_patch: {hp['id']!r} on {hp['operator']!r} is not the "
                          "V₀ patch of the gene unit (item 7)")  # fmt: skip


def _required(rec, mapping, profile):
    """Every readout the kind of entry owes (READOUTS.md; the README's kinds); what a twin must not
    carry (item 7); the engine's other exports are recorded only."""
    kind_excess = rec.kind in ("labelled", "twin", "restart", "P8")
    for e in mapping_entries(mapping, profile, blank=True if rec.blank else None):
        kind, _, name = e["engine"].partition("/")
        if kind != "series":
            continue
        if rec.role == "twin" and not physical(name):
            continue
        if name.startswith("excess_over_blank_") and not kind_excess:
            continue
        if name not in rec.series:
            rec.faults.append(f"{rec.where}.readouts.{name}: missing readout")
    if rec.role == "twin":
        carried = sorted(k for k in rec.series if not physical(k))
        if carried or rec.survival:
            rec.faults.append(f"{rec.where}: a twin is unlabelled, yet it carries "
                              f"{carried or ['survival']} (item 7)")  # fmt: skip


def physical(name):
    return not (name.startswith("label_") or name.startswith("released_present_gross_"))


def _flag_rates(rec):
    """route2's `k_per_s` against the entry's own declared k_f (item 4: recorded and flagged)."""
    for fate in spec.FATES:
        try:
            k = definitions.declared_rate(rec.definition, fate)
        except (definitions.Unreadable, IndexError, TypeError, ValueError):
            continue
        for (f, ts), got in sorted(rec.route2_k.items()):
            if f == fate and not close(got, k):
                rec.flags.append(f"{rec.where}.route2 ({fate}, {ts!r} s): k_per_s {got!r} is not "
                                 f"the declared {k!r}")  # fmt: skip
