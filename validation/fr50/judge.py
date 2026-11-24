"""FR-50's judge: the engine's one-way records against the code-blind references, by
fr50-one-way-records-v1's criteria.

This file is the registration's addendum (D308). Its reader was written from the references' format
sample alone (the keys and shapes of ten INVENTED_* files and invented_cases.json), and it is tagged
before any reference is read. The criteria are REGISTRATION.md's §1-§3 with their bands as written
there. Both phases' criteria are here, chosen with --phase, so that phase 2's judge is as blind as
phase 1's.

**The reader** takes the results layout `cells.fr50_reference_result@1`, one file per case of the
spec, `<case ID>.json`. A case is judged by its file's `case_kind` (K1, K2, K3, K4, K4h, E1, E2, E3,
E4, E6), so no case ID is written here. The reader checks:
- the kind and protocol, the case's ID, and that `declared` is the spec's case, of its kind's phase;
- every value, a finite decimal string;
- the record times: from 0, increasing, and for K1, K2 and K4 multiples of the registered steps,
  ending at the registered horizon;
- the evaluations: K3's are the spec's voltages in order, and E6's are the spec's voltages times its
  availabilities;
- the method's accuracy entries.
A failure is named. A judged run refuses invented inputs.

**The inconclusive rule** (the registration's preamble). A case's reference is trusted when:
- `method.within_declared_accuracy` is true and `method.max` is at most `method.declared_accuracy`;
- every route of `method.other_routes` is `within`, its max at most its accuracy;
- `checks.E_K_50_digit_strings_equal` is true, where E_K is formed.
A criterion that reads an untrusted reference's values is inconclusive, neither a pass nor a fail;
its comparison is still reported. The gap, closure, the restart, K4-2 and the kernel closure read
the engine alone.

**The engine's values** come from a function named at run time (`--engine MODULE:FUNCTION`), written
with the build, so this file reads no engine code. It is called as engine(request), and builds its
world from the spec's case alone. The request:
- kind, case_id, spec (the spec's case), and plant: None, or a name of PLANTS;
- record kinds (K1, K2, K4, E1-E4): record_times_s, the reference's decimal strings; dt_s, the
  registered steps (decimal strings), or None where none is registered and the step is the engine's;
  restart_at_s and restart_dt_s, a checkpoint to restart from, or None;
- K3: voltages_V; E6: evaluations, [(V_V, availability)]; all decimal strings;
- the refusals: kind "K5" or "E5" alone.
The engine returns a mapping:
- direction: the forward direction's first word, "inward", "outward", "forward" (cycles) or
  "sender", which must be the reference's;
- record kinds: runs, {dt_s: rows}, with every observed row from n = 0. The rows are n (the steps
  so far, integers), and F, B, net and gap (`one_way_gap_relative`), all float64, in fmol, or fmol
  of cycles for a transporter, each in its net record's orientation. E4's rows also carry
  split_forward, split_backward and channel_flux (fmol/s): the split's two directions and
  `channel_rates`' outward flux at the row's state;
- record kinds asked for a restart: restart, holding dt_s, from_n, the restarted run's rows after
  the checkpoint (n, F, B, net, gap), and state and uninterrupted_state, {field: array}, the two
  runs' whole states at the end;
- K3: forward and backward (fmol/s) at the voltages. K4h: J_plus and J_minus (fmol of cycles per
  s). E6: u, forward, backward and channel_flux at the evaluations;
- the refusals: refusals, {name: {refused, message, control_accepted}} for each name of REFUSALS.
  The control is the same world without the declaration, which must be accepted.

**Arithmetic.** Every comparison is exact: an engine value is the Decimal of its float64, a
reference value the Decimal of its string, and the arithmetic runs at 400 digits. Closure's epsilon
is binary64's, 2^-52, as in the site operator's ROUNDING.

Usage:
  python -m validation.fr50.judge --check-reader DIR --cases CASES_JSON --out OUT
      the reader on DIR's files (a format sample, or results/), structure only, values unread;
  python -m validation.fr50.judge --references DIR --engine MODULE:FUNCTION --phase 1 --out OUT
      the judged comparison against the tagged references, after the judge's tag.
"""

import argparse
import copy
import hashlib
import importlib
import json
from dataclasses import dataclass
from decimal import Context, Decimal, InvalidOperation, localcontext
from functools import wraps
from pathlib import Path

import numpy as np

KIND = "cells.fr50_reference_result@1"
PROTOCOL = "fr50-one-way-records-v1"
SPEC = Path(__file__).resolve().parent / "references" / "spec" / "cases.json"
PHASE = {"K1": 1, "K2": 1, "K3": 1, "K4": 1, "K4h": 1, "E1": 2, "E2": 2, "E3": 2, "E4": 2, "E6": 2}
DIRECTIONS = ("inward", "outward", "forward", "sender")

# The results layout of each kind, as the format sample shows it.
_FLUXES = ("prefactor_pL_per_s", "forward_fmol_per_s", "backward_fmol_per_s", "net_fmol_per_s")
_RECORDS = ("F_fmol", "B_fmol")
_CYCLES = ("F_fmol_cycles", "B_fmol_cycles")
_TRANSPORTER = ("dG_cyc_over_RT", "S", "J_plus_fmol_cycles_per_s", "J_minus_fmol_cycles_per_s")
_SPLIT = (
    "forward_fmol_per_s",
    "backward_fmol_per_s",
    "ratio_inward_over_outward",
    "ratio_backward_over_forward",
)
LAYOUT = {
    "K1": dict(scalars=_FLUXES, records=_RECORDS),
    "K2": dict(
        scalars=("a_pL_per_s", "k_per_s", "c_bar_mM"),
        records=_RECORDS,
        series=("c_cell_mM", "c_node_mM"),
    ),
    "K3": dict(rows=("V_V",) + _SPLIT),
    "K4": dict(scalars=_TRANSPORTER + ("net_fmol_cycles_per_s",), records=_CYCLES),
    "K4h": dict(scalars=_TRANSPORTER + ("J_minus_over_J_plus",)),
    "E1": dict(scalars=("E_K_V", "V_V") + _FLUXES, records=_RECORDS, e_k=True),
    "E2": dict(scalars=_FLUXES, records=_RECORDS),
    "E3": dict(scalars=_FLUXES, records=_RECORDS),
    "E4": dict(scalars=("E_K_V", "V_V", "u") + _FLUXES, records=_RECORDS, e_k=True),
    "E6": dict(
        scalars=("E_K_V",),
        rows=("V_V", "availability", "V_ref_V", "u")
        + _SPLIT
        + ("difference_forward_minus_backward_fmol_per_s",),
        e_k=True,
    ),
}
PHASE_KINDS = {1: ("K1", "K2", "K3", "K4", "K4h"), 2: ("E1", "E2", "E3", "E4", "E6")}

# The registered steps and horizons (s, REGISTRATION.md §2) and K2-4's checkpoint. World 1 (E1, E4)
# restarts at mid-run, half its last record time; phase 2 registers no step.
STEPS = {"K1": ("0.1",), "K2": ("0.1", "0.05"), "K4": ("0.1",)}
HORIZON = {"K1": Decimal("100"), "K2": Decimal("200"), "K4": Decimal("100")}
RESTART = {"K2": Decimal("100")}
MID_RUN_RESTART = ("E1", "E4")

# The bands, fixed by the registration before any reference value was seen.
REL_RECORD = Decimal("1e-11")  # K1-1, K4-1, E1-1 to E4-1: each record at each record time.
REL_HOST = Decimal("1e-12")  # K3, K4h, E6-1 and E6-3.
GAP = Decimal("1e-12")  # K1-2, K4-2, E1-2 to E4-2: one_way_gap_relative on every row.
NET = Decimal("1e-12")  # K4-2: |net| <= 1e-12 F on every row.
ORDER = (Decimal("3.6"), Decimal("4.4"))  # K2-1: e_q(0.1 s) / e_q(0.05 s).
ORDER_FLOOR = Decimal("1e-8")  # K2-1: below it at 0.1 s the ratio is not judged.
GAP_FINE = Decimal("1e-5")  # K2-2: the gap at the horizon at 0.05 s.
GAP_ORDER = (Decimal("3.0"), Decimal("5.0"))  # K2-2: the gap's ratio between the steps.
GAP_ORDER_FLOOR = Decimal("1e-12")  # K2-2: below it at 0.1 s the ratio is not judged.
CLOSURE = Decimal("2.5")  # |F - B - (net - net0)| <= 2.5 eps n (F + B + |net| + |net0|).
EPS = Decimal(2) ** -52  # binary64's machine epsilon.
ULPS = 4  # The kernel closure: within 4 ulps of (forward + backward).
K1A_GAP = Decimal(1) / Decimal(3)  # Plant K1 (a)'s gap, as the registration describes it.

# The criteria that read a reference value, and so are inconclusive on an untrusted reference.
READS_REFERENCE = (
    "K1-1",
    "K2-1",
    "K3",
    "K4-1",
    "K4h",
    "E1-1",
    "E2-1",
    "E3-1",
    "E4-1",
    "E6-1",
    "E6-3",
)

# The registered plants (§2, §3), each the engine with one planted change, and the criteria each
# must fail. `only` is the registration's description of what fails, reported, not judged.
PLANTS = {
    "K1a_backward_halved": dict(kind="K1", must_fail=("K1-2",), only=("K1-2",)),
    "K1b_both_halved": dict(kind="K1", must_fail=("K1-1",), only=("K1-1",)),
    "K3_bernoulli_exchanged": dict(kind="K3", must_fail=("K3",), every_nonzero_voltage=True),
    "K4a_no_saturation": dict(kind="K4", must_fail=("K4-1",)),
    "K4b_ratio_inverted": dict(kind="K4h", must_fail=("K4h",)),
    "E4_block_omitted": dict(kind="E4", must_fail=("E4-1",), only=("E4-1",)),
    "E6a_availability_omitted": dict(kind="E6", must_fail=("E6-1", "E6-2")),
    "E6b_block_omitted": dict(kind="E6", must_fail=("E6-1", "E6-2")),
    "E6c_bernoulli_exchanged": dict(kind="E6", must_fail_any=("E6-1", "E6-2", "E6-3")),
}

# K5 and E5: refused at the definition, each with its reason. A reason names its cause (any one of
# the words) and the declaration.
REFUSALS = {
    "K5": {
        "rectifier_route": ("rectif",),
        "net_flow_transporter_mode": ("net-flow", "net flow", "net_flow"),
        "rk4": ("rk4",),
        "slot_operator": ("retire", "close"),
    },
    "E5": {
        "charged_face_row": ("charged",),
        "forms_face": ("forms",),
        "pump": ("pump",),
        "rk4": ("rk4",),
    },
}
DECLARATION_WORDS = ("one_way", "one-way")

_CTX = Context(prec=400)


class ReaderError(ValueError):
    """A references file whose structure the reader refuses, naming what is wrong."""


class EngineOutputError(ValueError):
    """An engine mapping outside the contract in this module's docstring."""


def _exact(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        with localcontext(_CTX):
            return function(*args, **kwargs)

    return wrapped


# ------------------------------------------------------------------ the reader


@dataclass(frozen=True)
class Reference:
    case_id: str
    case_kind: str
    declared: dict
    direction: str  # forward_direction's first word.
    scalars: dict  # {name: Decimal}
    times_raw: tuple  # The record times, the reference's strings.
    times: tuple  # The same, Decimal.
    series: dict  # {name: tuple of Decimal}, over the record times.
    rows_raw: tuple  # The evaluations, the reference's strings.
    rows: tuple  # The same, Decimal.
    trusted: bool
    untrusted_because: tuple
    invented: bool
    revision: str
    sha256: str

    @property
    def record_keys(self):
        return LAYOUT[self.case_kind]["records"]


def _decimal(value, what):
    if not isinstance(value, str):
        raise ReaderError(f"{what} is not a decimal string")
    try:
        number = Decimal(value)
    except InvalidOperation:
        raise ReaderError(f"{what} is not a decimal number: {value[:40]!r}") from None
    if not number.is_finite():
        raise ReaderError(f"{what} is not finite")
    return number


def _decimals(values, what):
    if not isinstance(values, list) or not values:
        raise ReaderError(f"{what} is not a nonempty list")
    return tuple(_decimal(v, f"{what}[{i}]") for i, v in enumerate(values))


def _token(direction, what):
    if not isinstance(direction, str) or not direction.strip():
        raise ReaderError(f"{what} is not a nonempty string")
    word = direction.split(":")[0].split()[0].lower()
    if word not in DIRECTIONS:
        raise ReaderError(f"{what} begins with {word!r}, not one of {DIRECTIONS}")
    return word


def _trust(doc, path, e_k):
    """(trusted, why not): the inconclusive rule's reading of the method and the checks."""
    why = []
    method = doc.get("method")
    if not isinstance(method, dict):
        raise ReaderError(f"{path}: no method object")
    within = method.get("within_declared_accuracy")
    if not isinstance(within, bool):
        raise ReaderError(f"{path}: method.within_declared_accuracy is not a boolean")
    largest = _decimal(method.get("max"), f"{path}: method.max")
    accuracy = _decimal(method.get("declared_accuracy"), f"{path}: method.declared_accuracy")
    if not within:
        why.append("method.within_declared_accuracy is false")
    if largest > accuracy:
        why.append("method.max exceeds method.declared_accuracy")
    routes = method.get("other_routes")
    if not isinstance(routes, dict):
        raise ReaderError(f"{path}: method.other_routes is not an object")
    for name, route in routes.items():
        what = f"{path}: method.other_routes.{name}"
        if not isinstance(route, dict) or not isinstance(route.get("within"), bool):
            raise ReaderError(f"{what}.within is not a boolean")
        if not route["within"]:
            why.append(f"other route {name} is not within its accuracy")
        if "max" in route and "declared_accuracy" in route:  # Checked where the route gives both.
            if _decimal(route["max"], f"{what}.max") > _decimal(
                route["declared_accuracy"], f"{what}.declared_accuracy"
            ):
                why.append(f"other route {name}'s max exceeds its accuracy")
    if e_k:
        checks = doc.get("checks")
        flag = checks.get("E_K_50_digit_strings_equal") if isinstance(checks, dict) else None
        if not isinstance(flag, bool):
            raise ReaderError(f"{path}: checks.E_K_50_digit_strings_equal is not a boolean")
        if not flag:
            why.append("E_K's 50-digit strings differ between the routes")
    return not why, tuple(why)


@_exact
def _record_times(doc, path, kind, length_of):
    raw = doc.get("record_times_s")
    times = _decimals(raw, f"{path}: record_times_s")
    if len(times) < 2 or times[0] != 0:
        raise ReaderError(f"{path}: record_times_s does not start at 0 with a later time")
    if any(b <= a for a, b in zip(times, times[1:], strict=False)):
        raise ReaderError(f"{path}: record_times_s is not increasing")
    if kind in HORIZON:
        if times[-1] != HORIZON[kind]:
            raise ReaderError(f"{path}: the last record time is not the registered horizon")
        for dt in STEPS[kind]:
            if any((t / Decimal(dt)) % 1 != 0 for t in times):
                raise ReaderError(f"{path}: a record time is not a multiple of the step {dt} s")
    series = {}
    for name in length_of:
        series[name] = _decimals(doc.get(name), f"{path}: {name}")
        if len(series[name]) != len(times):
            raise ReaderError(
                f"{path}: {name} has {len(series[name])} values for {len(times)} times"
            )
    return tuple(raw), times, series


def _evaluations(doc, path, kind, names, spec_case):
    rows = doc.get("evaluations")
    if not isinstance(rows, list) or not rows:
        raise ReaderError(f"{path}: evaluations is not a nonempty list")
    raw, parsed = [], []
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ReaderError(f"{path}: evaluations[{i}] is not an object")
        parsed.append({n: _decimal(row.get(n), f"{path}: evaluations[{i}].{n}") for n in names})
        raw.append({n: row[n] for n in names})
    try:
        voltages = [Decimal(v) for v in spec_case["voltages_V"]]
        if kind == "K3":
            if [row["V_V"] for row in parsed] != voltages:
                raise ReaderError(f"{path}: the evaluations are not the spec's voltages, in order")
        else:
            wanted = sorted((v, Decimal(a)) for v in voltages for a in spec_case["availabilities"])
            if sorted((row["V_V"], row["availability"]) for row in parsed) != wanted:
                raise ReaderError(
                    f"{path}: the evaluations are not the spec's voltages times its availabilities"
                )
    except (KeyError, TypeError, InvalidOperation):
        raise ReaderError(f"{path}: the spec's case has no readable voltage list") from None
    return tuple(raw), tuple(parsed)


def read_case(path, case_id, spec_case, *, allow_invented=False):
    """One case's results file, checked against the spec's case (cases.json's entry)."""
    path = Path(path)
    try:
        data = path.read_bytes()
        doc = json.loads(data)
    except (OSError, json.JSONDecodeError) as error:
        raise ReaderError(f"{path}: not readable JSON: {error}") from None
    if not isinstance(doc, dict):
        raise ReaderError(f"{path}: not a JSON object")
    for key, expected in (("kind", KIND), ("protocol", PROTOCOL), ("case_id", case_id)):
        if doc.get(key) != expected:
            raise ReaderError(f"{path}: {key} is {doc.get(key)!r}, not {expected!r}")
    kind = doc.get("case_kind")
    if kind not in LAYOUT:
        raise ReaderError(f"{path}: case_kind {kind!r} is not one of {tuple(LAYOUT)}")
    if doc.get("declared") != spec_case:
        raise ReaderError(f"{path}: declared is not the spec's case {case_id!r}")
    if spec_case.get("phase") != PHASE[kind]:
        raise ReaderError(f"{path}: the spec's phase is not {kind}'s, {PHASE[kind]}")
    inputs = doc.get("inputs")
    if not isinstance(inputs, dict) or not isinstance(inputs.get("invented"), bool):
        raise ReaderError(f"{path}: inputs.invented is not a boolean")
    if inputs["invented"] and not allow_invented:
        raise ReaderError(f"{path}: invented inputs, refused in a judged run")
    provenance = doc.get("provenance")
    revision = provenance.get("git_revision") if isinstance(provenance, dict) else None
    if not isinstance(revision, str):
        raise ReaderError(f"{path}: provenance.git_revision is not a string")
    layout = LAYOUT[kind]
    scalars = {n: _decimal(doc.get(n), f"{path}: {n}") for n in layout.get("scalars", ())}
    times_raw, times, series = (), (), {}
    if "records" in layout:
        names = layout.get("series", ()) + layout["records"]
        times_raw, times, series = _record_times(doc, path, kind, names)
    rows_raw, rows = (), ()
    if "rows" in layout:
        rows_raw, rows = _evaluations(doc, path, kind, layout["rows"], spec_case)
    trusted, why = _trust(doc, path, layout.get("e_k", False))
    return Reference(
        case_id=case_id,
        case_kind=kind,
        declared=spec_case,
        direction=_token(doc.get("forward_direction"), f"{path}: forward_direction"),
        scalars=scalars,
        times_raw=times_raw,
        times=times,
        series=series,
        rows_raw=rows_raw,
        rows=rows,
        trusted=trusted,
        untrusted_because=why,
        invented=inputs["invented"],
        revision=revision,
        sha256=hashlib.sha256(data).hexdigest(),
    )


def read_spec(cases_json):
    spec = json.loads(Path(cases_json).read_text())
    if not isinstance(spec, dict) or not isinstance(spec.get("cases"), dict) or not spec["cases"]:
        raise ReaderError(f"{cases_json}: no cases object")
    return spec["cases"]


def read_results(directory, cases_json=SPEC, *, phase=None, allow_invented=False):
    """{case ID: Reference} for each case of the spec (of the phase, if given), each from
    DIRECTORY/<case ID>.json. Every kind of the phase (of both, without one) must be present."""
    out = {}
    for case_id, spec_case in read_spec(cases_json).items():
        if not isinstance(spec_case, dict):
            raise ReaderError(f"{cases_json}: case {case_id!r} is not an object")
        if phase is not None and spec_case.get("phase") != phase:
            continue
        path = Path(directory) / f"{case_id}.json"
        out[case_id] = read_case(path, case_id, spec_case, allow_invented=allow_invented)
    wanted = PHASE_KINDS[phase] if phase is not None else tuple(LAYOUT)
    missing = sorted(set(wanted) - {ref.case_kind for ref in out.values()})
    if missing:
        raise ReaderError(f"the spec has no case of kind {', '.join(missing)}")
    return out


# ------------------------------------------------------------------ the engine's values


def _float64(values, what, *, length=None, scalar=False):
    array = np.asarray(values)
    if array.dtype != np.float64:
        raise EngineOutputError(f"{what} is {array.dtype}, not float64")
    if scalar and array.shape != ():
        raise EngineOutputError(f"{what} is not a scalar")
    if not scalar and (array.ndim != 1 or (length is not None and array.size != length)):
        raise EngineOutputError(f"{what} has shape {array.shape}, not ({length},)")
    if not np.all(np.isfinite(array)):
        raise EngineOutputError(f"{what} is not finite")
    return array


def _exact_values(array):
    return [Decimal(float(x)) for x in np.asarray(array).ravel()]


def _rows(rows, what, extra=(), *, from_zero=True):
    """A run's rows: n increasing integers (from 0, unless they follow a checkpoint), and float64
    arrays of the same length."""
    if not isinstance(rows, dict):
        raise EngineOutputError(f"{what} is not a mapping")
    n = np.asarray(rows.get("n"))
    if n.ndim != 1 or n.size < 1 + from_zero or not np.issubdtype(n.dtype, np.integer):
        raise EngineOutputError(f"{what}.n is not a 1-D integer array of rows")
    if (from_zero and n[0] != 0) or np.any(np.diff(n) <= 0):
        raise EngineOutputError(f"{what}.n does not increase from its start")
    out = {"n": n.astype(np.int64)}
    for name in ("F", "B", "net", "gap") + extra:
        out[name] = _float64(rows.get(name), f"{what}.{name}", length=n.size)
    return out


def _direction(ref, out):
    if not isinstance(out, dict) or out.get("direction") != ref.direction:
        raise EngineOutputError(
            f"{ref.case_id}: the engine's direction is not the reference's {ref.direction!r}"
        )


def _runs(ref, out, request):
    runs = out.get("runs")
    if not isinstance(runs, dict) or not runs:
        raise EngineOutputError(f"{ref.case_id}: runs is not a nonempty mapping")
    if request["dt_s"] is not None and sorted(runs) != sorted(request["dt_s"]):
        raise EngineOutputError(f"{ref.case_id}: runs are not at the registered steps")
    extra = ("split_forward", "split_backward", "channel_flux") if ref.case_kind == "E4" else ()
    return {dt: _rows(rows, f"{ref.case_id}.runs[{dt}]", extra) for dt, rows in runs.items()}


@_exact
def _index(run, dt, t, what):
    """The row at time t, a whole number of steps dt (both decimal), or an EngineOutputError."""
    steps = Decimal(t) / Decimal(dt)
    if steps % 1 != 0:
        raise EngineOutputError(f"{what}: {t} s is not a whole number of steps {dt} s")
    steps = int(steps)
    at = int(np.searchsorted(run["n"], steps))
    if at >= run["n"].size or run["n"][at] != steps:
        raise EngineOutputError(f"{what}: no row at {t} s (n = {steps})")
    return at


# ------------------------------------------------------------------ the comparisons


def _result(passed, worst=None, **detail):
    return dict(passed=bool(passed), worst=worst, **detail)


def _merge(results):
    """Several runs' results of one criterion: passed by all, the largest worst, each kept."""
    worst = [r["worst"] for r in results.values() if r["worst"] is not None]
    return _result(
        all(r["passed"] for r in results.values()), max(worst) if worst else None, runs=results
    )


def _relative(engine, reference):
    """|e - r| / |r|: 0 where both are equal, infinite where r is 0 and e is not."""
    difference = abs(engine - reference)
    if reference == 0:
        return Decimal(0) if difference == 0 else Decimal("Infinity")
    return difference / abs(reference)


def _within(engines, references, band):
    """|e - r| <= band |r| at every point (so e = r exactly where r = 0): (passed, worst, where)."""
    passed, worst, where = True, Decimal(0), 0
    for i, (e, r) in enumerate(zip(engines, references, strict=True)):
        if abs(e - r) > band * abs(r):
            passed = False
        relative = _relative(e, r)
        if relative > worst:
            worst, where = relative, i
    return passed, worst, where


@_exact
def check_absolute(ref, run, dt):
    """K1-1, K4-1, E1-1 to E4-1: each record within 1e-11 of the reference at each record time."""
    at = [_index(run, dt, t, ref.case_id) for t in ref.times_raw]
    detail, passed, worst = {}, True, Decimal(0)
    for q, key in zip(("F", "B"), ref.record_keys, strict=True):
        ok, largest, where = _within(_exact_values(run[q][at]), ref.series[key], REL_RECORD)
        detail[q] = dict(passed=ok, worst=largest, at_s=ref.times_raw[where])
        passed, worst = passed and ok, max(worst, largest)
    return _result(passed, worst, **detail)


@_exact
def check_gap(run):
    """X-2: one_way_gap_relative in [0, 1e-12] on every row."""
    gap = _exact_values(run["gap"])
    return _result(all(0 <= g <= GAP for g in gap), max(gap), smallest=min(gap))


@_exact
def check_closure(run):
    """|F - B - (net - net0)| <= 2.5 eps n (F + B + |net| + |net0|) on every row."""
    F, B, net = (_exact_values(run[q]) for q in ("F", "B", "net"))
    net0, passed, worst, where = net[0], True, Decimal(0), 0
    for i, n in enumerate(run["n"]):
        excess = abs(F[i] - B[i] - (net[i] - net0))
        bound = CLOSURE * EPS * int(n) * (F[i] + B[i] + abs(net[i]) + abs(net0))
        if excess > bound:
            passed = False
        ratio = Decimal(0) if excess == 0 else (excess / bound if bound > 0 else Decimal("Inf"))
        if ratio > worst:
            worst, where = ratio, i
    return _result(passed, worst, at_n=int(run["n"][where]), measure="excess / bound")


@_exact
def check_net_and_gap(run):
    """K4-2: |net| <= 1e-12 F on every row, and the gap at most 1e-12."""
    F, net = _exact_values(run["F"]), _exact_values(run["net"])
    passed = all(abs(x) <= NET * f for x, f in zip(net, F, strict=True))
    worst = max(
        abs(x) / f if f > 0 else (Decimal(0) if x == 0 else Decimal("Infinity"))
        for x, f in zip(net, F, strict=True)
    )
    gap = check_gap(run)
    return _result(passed and gap["passed"], worst, measure="|net| / F", gap=gap)


@_exact
def check_kernel_closure(forward, backward, flux, labels):
    """E4-4 and E6-2: forward - backward is channel_rates' flux within 4 ulps of
    (forward + backward)."""
    passed, worst, where = True, Decimal(0), 0
    for i, (f, b, j) in enumerate(zip(forward, backward, flux, strict=True)):
        excess = abs(Decimal(float(f)) - Decimal(float(b)) - Decimal(float(j)))
        ulp = Decimal(float(np.spacing(abs(np.float64(f) + np.float64(b)))))
        if excess > ULPS * ulp:
            passed = False
        if excess / ulp > worst:
            worst, where = excess / ulp, i
    return _result(passed, worst, measure="ulps of (forward + backward)", at=labels[where])


@_exact
def _record_error(ref, run, dt, q, key):
    """e_q(h) of §1: max |q_engine - q_ref| over the record times, over max |q_ref|."""
    at = [_index(run, dt, t, ref.case_id) for t in ref.times_raw]
    engine, reference = _exact_values(run[q][at]), ref.series[key]
    scale = max(abs(r) for r in reference)
    if scale == 0:
        raise ReaderError(f"{ref.case_id}: {key} is zero at every record time")
    return max(abs(e - r) for e, r in zip(engine, reference, strict=True)) / scale


@_exact
def check_order(ref, runs):
    """K2-1: 3.6 <= e_q(0.1)/e_q(0.05) <= 4.4 for F and B; below 1e-8 at 0.1 s, e_q(0.05) < 1e-8."""
    coarse, fine = STEPS["K2"]
    detail, passed = {}, True
    for q, key in zip(("F", "B"), ref.record_keys, strict=True):
        e_coarse = _record_error(ref, runs[coarse], coarse, q, key)
        e_fine = _record_error(ref, runs[fine], fine, q, key)
        if e_coarse < ORDER_FLOOR:
            ratio, ok = None, e_fine < ORDER_FLOOR
        else:
            ratio = e_coarse / e_fine if e_fine > 0 else Decimal("Infinity")
            ok = ORDER[0] <= ratio <= ORDER[1]
        detail[q] = dict(passed=ok, e_coarse=e_coarse, e_fine=e_fine, ratio=ratio)
        passed = passed and ok
    return _result(passed, None, **detail)


@_exact
def check_gap_order(ref, runs):
    """K2-2: the gap at the horizon at most 1e-5 at 0.05 s; its ratio between the steps in [3, 5]
    where it is at least 1e-12 at 0.1 s."""
    coarse, fine = STEPS["K2"]
    horizon = ref.times_raw[-1]
    gap = {
        dt: Decimal(float(runs[dt]["gap"][_index(runs[dt], dt, horizon, ref.case_id)]))
        for dt in (coarse, fine)
    }
    ok_fine = gap[fine] <= GAP_FINE
    if gap[coarse] >= GAP_ORDER_FLOOR:
        ratio = gap[coarse] / gap[fine] if gap[fine] > 0 else Decimal("Infinity")
        ok_ratio = GAP_ORDER[0] <= ratio <= GAP_ORDER[1]
    else:
        ratio, ok_ratio = None, True
    return _result(
        ok_fine and ok_ratio,
        None,
        gap_coarse=gap[coarse],
        gap_fine=gap[fine],
        ratio=ratio,
        fine_within=ok_fine,
        ratio_within=ok_ratio,
    )


def _same_bits(a, b):
    a, b = np.asarray(a), np.asarray(b)
    return a.dtype == b.dtype and a.shape == b.shape and a.tobytes() == b.tobytes()


@_exact
def check_restart(ref, out, runs, request):
    """K2-4, E1-R and E4-R: the run restarted from its checkpoint is the uninterrupted run, bit for
    bit: every row after the checkpoint (the records and the gap included) and the whole state."""
    restart = out.get("restart")
    if not isinstance(restart, dict) or restart.get("dt_s") not in runs:
        raise EngineOutputError(f"{ref.case_id}: no restart at one of the runs' steps")
    dt = restart["dt_s"]
    if request["restart_dt_s"] is not None and dt != request["restart_dt_s"]:
        raise EngineOutputError(f"{ref.case_id}: the restart is not at the asked step")
    from_n = restart.get("from_n")
    if not isinstance(from_n, (int, np.integer)) or isinstance(from_n, bool):
        raise EngineOutputError(f"{ref.case_id}: the restart's from_n is not an integer")
    from_n = int(from_n)
    if Decimal(dt) * from_n != Decimal(request["restart_at_s"]):
        raise EngineOutputError(f"{ref.case_id}: the checkpoint is not at the asked time")
    run = runs[dt]
    rows = _rows(restart, f"{ref.case_id}.restart", from_zero=False)
    n = rows["n"]
    if n[0] <= from_n or n[-1] != run["n"][-1]:
        raise EngineOutputError(f"{ref.case_id}: the restart's rows do not run to the end")
    at = np.searchsorted(run["n"], n)
    if np.any(at >= run["n"].size) or np.any(run["n"][np.minimum(at, run["n"].size - 1)] != n):
        raise EngineOutputError(f"{ref.case_id}: a restart row is not a row of the run")
    rows_equal = {q: _same_bits(rows[q], run[q][at]) for q in ("F", "B", "net", "gap")}
    state, uninterrupted = restart.get("state"), restart.get("uninterrupted_state")
    if not isinstance(state, dict) or not isinstance(uninterrupted, dict) or not state:
        raise EngineOutputError(f"{ref.case_id}: the restart has no states to compare")
    fields_equal = sorted(state) == sorted(uninterrupted)
    differing = sorted(
        k for k in state if k in uninterrupted and not _same_bits(state[k], uninterrupted[k])
    )
    passed = all(rows_equal.values()) and fields_equal and not differing
    return _result(
        passed,
        None,
        rows=int(n.size),
        from_n=from_n,
        rows_equal=rows_equal,
        fields=len(state),
        same_fields=fields_equal,
        differing=differing,
    )


def _inward_outward(direction, forward, backward):
    if direction == "inward":
        return forward, backward
    if direction == "outward":
        return backward, forward
    raise EngineOutputError(
        f"a ratio inward/outward needs an inward or outward direction, not {direction!r}"
    )


@_exact
def check_k3(ref, out):
    """K3: each direction, and the ratio inward/outward, within 1e-12 at every declared voltage."""
    _direction(ref, out)
    count = len(ref.rows)
    forward = _float64(out.get("forward"), f"{ref.case_id}.forward", length=count)
    backward = _float64(out.get("backward"), f"{ref.case_id}.backward", length=count)
    per_voltage, passed, worst = [], True, Decimal(0)
    for i, row in enumerate(ref.rows):
        f, b = Decimal(float(forward[i])), Decimal(float(backward[i]))
        inward, outward = _inward_outward(ref.direction, f, b)
        ratio = inward / outward if outward != 0 else Decimal("Infinity")
        checks = [
            _within([f], [row["forward_fmol_per_s"]], REL_HOST),
            _within([b], [row["backward_fmol_per_s"]], REL_HOST),
            _within([ratio], [row["ratio_inward_over_outward"]], REL_HOST)
            if ratio.is_finite()
            else (False, Decimal("Infinity"), 0),
        ]
        ok, largest = all(c[0] for c in checks), max(c[1] for c in checks)
        per_voltage.append(
            dict(V_V=ref.rows_raw[i]["V_V"], passed=ok, worst=largest, zero=row["V_V"] == 0)
        )
        passed, worst = passed and ok, max(worst, largest)
    return _result(passed, worst, per_voltage=per_voltage)


@_exact
def check_k4h(ref, out):
    """K4h: J-/J+ = e^(dG_cyc/RT) within 1e-12, and J+ within 1e-12 of the reference."""
    _direction(ref, out)
    j_plus = Decimal(float(_float64(out.get("J_plus"), f"{ref.case_id}.J_plus", scalar=True)))
    j_minus = Decimal(float(_float64(out.get("J_minus"), f"{ref.case_id}.J_minus", scalar=True)))
    target = ref.scalars["dG_cyc_over_RT"].exp()
    ratio = j_minus / j_plus if j_plus != 0 else Decimal("Infinity")
    ok_ratio, worst_ratio, _ = (
        _within([ratio], [target], REL_HOST)
        if ratio.is_finite()
        else (False, Decimal("Infinity"), 0)
    )
    ok_plus, worst_plus, _ = _within([j_plus], [ref.scalars["J_plus_fmol_cycles_per_s"]], REL_HOST)
    return _result(
        ok_ratio and ok_plus,
        max(worst_ratio, worst_plus),
        ratio=dict(passed=ok_ratio, worst=worst_ratio),
        J_plus=dict(passed=ok_plus, worst=worst_plus),
        info_J_minus=_relative(j_minus, ref.scalars["J_minus_fmol_cycles_per_s"]),
        info_reference_ratio_against_exp=_relative(ref.scalars["J_minus_over_J_plus"], target),
    )


@_exact
def check_e6(ref, out):
    """E6-1: u and each direction within 1e-12; E6-2: the kernel closure within 4 ulps; E6-3: the
    ratio inward/outward within 1e-12 of the reference's (c_o/c_i) e^(-x)."""
    _direction(ref, out)
    count = len(ref.rows)
    values = {
        q: _float64(out.get(q), f"{ref.case_id}.{q}", length=count)
        for q in ("u", "forward", "backward", "channel_flux")
    }
    labels = [f"V={r['V_V']} availability={r['availability']}" for r in ref.rows_raw]
    absolute, ratio_ok, worst_abs, worst_ratio, per = True, True, Decimal(0), Decimal(0), []
    for i, row in enumerate(ref.rows):
        f, b = Decimal(float(values["forward"][i])), Decimal(float(values["backward"][i]))
        u = Decimal(float(values["u"][i]))
        checks = [
            _within([u], [row["u"]], REL_HOST),
            _within([f], [row["forward_fmol_per_s"]], REL_HOST),
            _within([b], [row["backward_fmol_per_s"]], REL_HOST),
        ]
        inward, outward = _inward_outward(ref.direction, f, b)
        ratio = inward / outward if outward != 0 else Decimal("Infinity")
        r_ok, r_worst, _ = (
            _within([ratio], [row["ratio_inward_over_outward"]], REL_HOST)
            if ratio.is_finite()
            else (False, Decimal("Infinity"), 0)
        )
        ok = all(c[0] for c in checks)
        absolute, ratio_ok = absolute and ok, ratio_ok and r_ok
        largest = max(c[1] for c in checks)
        worst_abs, worst_ratio = max(worst_abs, largest), max(worst_ratio, r_worst)
        per.append(dict(at=labels[i], absolute=ok, worst=largest, ratio=r_ok, ratio_worst=r_worst))
    closure = check_kernel_closure(
        values["forward"], values["backward"], values["channel_flux"], labels
    )
    return {
        "E6-1": _result(absolute, worst_abs, per_evaluation=per),
        "E6-2": closure,
        "E6-3": _result(ratio_ok, worst_ratio),
    }


def judge_case(ref, out, request):
    """{criterion: result} for one case, from the engine's mapping for its request."""
    kind = ref.case_kind
    if kind == "K3":
        return {"K3": check_k3(ref, out)}
    if kind == "K4h":
        return {"K4h": check_k4h(ref, out)}
    if kind == "E6":
        return check_e6(ref, out)
    _direction(ref, out)
    runs = _runs(ref, out, request)
    results = {}
    if kind == "K2":
        results["K2-1"] = check_order(ref, runs)
        results["K2-2"] = check_gap_order(ref, runs)
        results["K2-3"] = _merge({dt: check_closure(run) for dt, run in runs.items()})
        if request["restart_at_s"] is not None:
            results["K2-4"] = check_restart(ref, out, runs, request)
        return results
    results[f"{kind}-1"] = _merge({dt: check_absolute(ref, run, dt) for dt, run in runs.items()})
    if kind == "K4":
        results["K4-2"] = _merge({dt: check_net_and_gap(run) for dt, run in runs.items()})
    else:
        results[f"{kind}-2"] = _merge({dt: check_gap(run) for dt, run in runs.items()})
    results[f"{kind}-3"] = _merge({dt: check_closure(run) for dt, run in runs.items()})
    if kind == "E4":
        results["E4-4"] = _merge(
            {
                dt: check_kernel_closure(
                    run["split_forward"],
                    run["split_backward"],
                    run["channel_flux"],
                    [f"n={int(n)}" for n in run["n"]],
                )
                for dt, run in runs.items()
            }
        )
    if request["restart_at_s"] is not None:
        results[f"{kind}-R"] = check_restart(ref, out, runs, request)
    return results


@_exact
def request_for(ref, plant=None):
    """The engine's request for one case: the plants run without a restart."""
    request = dict(
        kind=ref.case_kind, case_id=ref.case_id, spec=copy.deepcopy(ref.declared), plant=plant
    )
    if ref.times_raw:
        request.update(
            record_times_s=list(ref.times_raw), dt_s=None, restart_at_s=None, restart_dt_s=None
        )
        if ref.case_kind in STEPS:
            request["dt_s"] = list(STEPS[ref.case_kind])
        if plant is None and ref.case_kind in RESTART:
            request["restart_at_s"] = str(RESTART[ref.case_kind])
            request["restart_dt_s"] = STEPS[ref.case_kind][0]
        elif plant is None and ref.case_kind in MID_RUN_RESTART:
            request["restart_at_s"] = str(ref.times[-1] / 2)
    if ref.case_kind == "K3":
        request["voltages_V"] = [row["V_V"] for row in ref.rows_raw]
    if ref.case_kind == "E6":
        request["evaluations"] = [(row["V_V"], row["availability"]) for row in ref.rows_raw]
    return request


def check_refusals(kind, out):
    """K5 and E5: each refused at the definition with its reason, its control accepted."""
    refusals = out.get("refusals") if isinstance(out, dict) else None
    if not isinstance(refusals, dict) or sorted(refusals) != sorted(REFUSALS[kind]):
        raise EngineOutputError(f"{kind}: refusals do not name {sorted(REFUSALS[kind])}")
    results = {}
    for name, words in REFUSALS[kind].items():
        entry = refusals[name]
        message = entry.get("message") if isinstance(entry, dict) else None
        if not isinstance(message, str):
            raise EngineOutputError(f"{kind}.{name}: no message")
        text = message.lower()
        names_cause = any(w in text for w in words)
        names_declaration = any(w in text for w in DECLARATION_WORDS)
        passed = (
            entry.get("refused") is True
            and entry.get("control_accepted") is True
            and names_cause
            and names_declaration
        )
        results[name] = dict(
            passed=passed,
            refused=entry.get("refused") is True,
            control_accepted=entry.get("control_accepted") is True,
            names_cause=names_cause,
            names_declaration=names_declaration,
            message=message,
        )
    return results


def _plant_caught(plant, results):
    failed = {name for name, r in results.items() if not r["passed"]}
    if plant.get("every_nonzero_voltage"):
        nonzero = [v for v in results["K3"]["per_voltage"] if not v["zero"]]
        return bool(nonzero) and not any(v["passed"] for v in nonzero), failed
    if "must_fail_any" in plant:
        return bool(failed & set(plant["must_fail_any"])), failed
    return set(plant["must_fail"]) <= failed, failed


def judge(references, engine, phase):
    """The phase's verdict: every criterion over its cases, the plants and the refusals."""
    cases = sorted(
        (ref for ref in references.values() if PHASE[ref.case_kind] == phase),
        key=lambda ref: (PHASE_KINDS[phase].index(ref.case_kind), ref.case_id),
    )
    criteria = {}
    for ref in cases:
        request = request_for(ref)
        for name, result in judge_case(ref, engine(request), request).items():
            untrusted = name in READS_REFERENCE and not ref.trusted
            status = "inconclusive" if untrusted else ("pass" if result["passed"] else "fail")
            criteria.setdefault(name, {})[ref.case_id] = dict(result, status=status)
    plants = {}
    for name, plant in PLANTS.items():
        if PHASE[plant["kind"]] != phase:
            continue
        plants[name] = {}
        for ref in (r for r in cases if r.case_kind == plant["kind"]):
            request = request_for(ref, plant=name)
            results = judge_case(ref, engine(request), request)
            caught, failed = _plant_caught(plant, results)
            entry = dict(caught=caught, failed=sorted(failed), results=results)
            if "only" in plant:
                entry["as_registered"] = failed == set(plant["only"])
            if name == "K1a_backward_halved":
                gap = results["K1-2"]["worst"]
                entry["gap"] = gap
                entry["as_registered"] = entry["as_registered"] and abs(gap - K1A_GAP) <= Decimal(
                    "1e-9"
                )
            plants[name][ref.case_id] = entry
    refusal_kind = "K5" if phase == 1 else "E5"
    refusals = check_refusals(refusal_kind, engine(dict(kind=refusal_kind, plant=None)))
    failed = (
        any(r["status"] == "fail" for per in criteria.values() for r in per.values())
        or any(not e["caught"] for per in plants.values() for e in per.values())
        or any(not r["passed"] for r in refusals.values())
    )
    inconclusive = any(r["status"] == "inconclusive" for p in criteria.values() for r in p.values())
    verdict = "fail" if failed else ("inconclusive" if inconclusive else "pass")
    return dict(
        protocol=PROTOCOL,
        phase=phase,
        verdict=verdict,
        criteria=criteria,
        plants=plants,
        refusals={refusal_kind: refusals},
    )


# ------------------------------------------------------------------ the command line


def _json(value):
    """The verdict as JSON: each Decimal as a short string, each array as a list."""
    if isinstance(value, Decimal):
        return format(value, ".6e") if value.is_finite() and value != 0 else str(value.normalize())
    if isinstance(value, dict):
        return {str(k): _json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _engine(spec):
    module, _, name = spec.partition(":")
    return getattr(importlib.import_module(module), name)


def check_reader(directory, cases_json):
    """The reader on DIRECTORY's files: each case's structure, values unread."""
    report = {}
    for case_id, spec_case in read_spec(cases_json).items():
        try:
            ref = read_case(
                Path(directory) / f"{case_id}.json", case_id, spec_case, allow_invented=True
            )
            report[case_id] = dict(
                parsed=True,
                case_kind=ref.case_kind,
                phase=PHASE[ref.case_kind],
                direction=ref.direction,
                scalars=sorted(ref.scalars),
                series={name: len(values) for name, values in ref.series.items()},
                evaluations=len(ref.rows),
                invented=ref.invented,
            )
        except ReaderError as error:
            report[case_id] = dict(parsed=False, why=str(error))
    kinds = {v.get("case_kind") for v in report.values() if v["parsed"]}
    return report, sorted(set(LAYOUT) - kinds)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--check-reader", type=Path, default=None)
    parser.add_argument("--cases", type=Path, default=SPEC)
    parser.add_argument("--references", type=Path, default=None)
    parser.add_argument("--engine", default=None, help="MODULE:FUNCTION")
    parser.add_argument("--phase", type=int, choices=(1, 2), default=None)
    args = parser.parse_args(argv)
    args.out.mkdir(parents=True, exist_ok=True)
    if args.check_reader is not None:  # D308: the reader on a format sample, values unread.
        report, missing = check_reader(args.check_reader, args.cases)
        document = dict(
            cases=str(args.cases),
            directory=str(args.check_reader),
            report=report,
            kinds_missing=missing,
        )
        (args.out / "reader_check.json").write_text(json.dumps(document, indent=1) + "\n")
        print(json.dumps({k: v["parsed"] for k, v in report.items()}))
        return 0 if all(v["parsed"] for v in report.values()) and not missing else 1
    if args.references is None or args.engine is None or args.phase is None:
        parser.error("--references, --engine and --phase, or --check-reader")
    references = read_results(args.references, args.cases, phase=args.phase)
    verdict = judge(references, _engine(args.engine), args.phase)
    verdict.update(
        engine=args.engine,
        spec=dict(path=str(args.cases), sha256=_sha256(args.cases)),
        references={
            ref.case_id: dict(
                case_kind=ref.case_kind,
                sha256=ref.sha256,
                revision=ref.revision,
                trusted=ref.trusted,
                untrusted_because=list(ref.untrusted_because),
            )
            for ref in references.values()
        },
    )
    (args.out / "verdict.json").write_text(json.dumps(_json(verdict), indent=1) + "\n")
    print(f"phase {args.phase}: {verdict['verdict']}")
    for name, per in verdict["criteria"].items():
        print(f"  {name}: " + ", ".join(f"{c} {r['status']}" for c, r in per.items()))
    for name, per in verdict["plants"].items():
        print(
            f"  plant {name}: "
            + ", ".join(f"{c} {'caught' if e['caught'] else 'NOT caught'}" for c, e in per.items())
        )
    for kind, per in verdict["refusals"].items():
        print(
            f"  {kind}: "
            + ", ".join(f"{n} {'pass' if r['passed'] else 'fail'}" for n, r in per.items())
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
