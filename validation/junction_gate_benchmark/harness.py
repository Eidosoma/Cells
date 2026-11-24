"""FR-30's junction-gate benchmarks: the conventions, the prediction and its readout
(docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.7 part 4; D334).

**The conventions** (`conventions`) are §13.7's table applied mechanically to protocol.json. A field
that is absent or not stated takes its default, and each value records the field and status it came
from, so nothing is left to judgment after the extraction. At a 30-s step with Revilla's fields
they give §13.5's protocol and readout exactly.

**The prediction** (`predict`) is junction_series_gates@1 clamped, as section 13 hosts it.
- Each gate starts at its steady state at the holding V_j.
- G_0 follows the paper's normalization:
  - **prepulse:** the conductance after the prepulse's duration at its voltage, with dt = 0 where
    the duration is not stated;
  - **reference step:** the law's G_ss at the reference voltage of the step's polarity;
  - **otherwise:** the holding conductance. The law has no instantaneous voltage dependence.
- The step to V_j is one call of `advance_clamped` with dt the grid's times (t_k = k ms), so each
  sample is exact and none is chained.
- G_ss/G_0 is the conductance at the G_ss sampling time over G_0, never a fitted offset.
- `domain_valid` must hold at the hold, the prepulse, the step and the end state, with a finite
  trace and G_0 > 0, or the voltage cannot be predicted.
- Both gate kinds read |V_j|, so one block gives the same prediction at both polarities.

**The readout** (`readout`): y = g/G_0 in the fit window.
- The form is y = C + A_f exp(-t/tau_f) + A_s exp(-t/tau_s), with C always free, by unweighted
  least squares.
- **Fitting:** variable projection from the start grid of §13.7's row 9, then Levenberg-Marquardt
  with Kaufman's Jacobian, as in §13.5.
- **Degenerate:** tau_s/tau_f < 1.5; A_f or A_s below 1e-3, signed; tau_s above 10 T; a refinement
  that does not converge; or a value that is not finite or a time that is not positive.

Stages (from the checkout's root, with PYTHONPATH=src and JAX_ENABLE_X64=1):
    python -m validation.junction_gate_benchmark.harness conventions PROTOCOL OUT
    python -m validation.junction_gate_benchmark.harness predict PARAMETERS CONVENTIONS FIT OUT
        predictions at both polarities of every held-out magnitude named by FIT's split
    python -m validation.junction_gate_benchmark.harness verify PREDICTIONS CONVENTIONS FIT
        recompute every prediction from the file's stated block, and refuse a difference
The scorer is score.py, standard library only.
"""

import argparse
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from cells.laws.junctions import junction_series_gates as series
from cells.laws.junctions import junction_voltage_relaxation as relaxation
from validation.junction_gate_benchmark import score as scorer
from validation.junction_gate_benchmark.score import Refusal

CONVENTIONS_SCHEMA = "fr30-junction-conventions@1"
CONVENTIONS_RULE = scorer.RULE + " part 4"
LADDER_MS = tuple(m * 10**e for e in range(7) for m in (1, 2, 5) if m * 10**e <= 1_000_000)
SAMPLE_MS = 1
DEFAULT_WINDOW_START_MS = 5
MIN_TAU_RATIO = 1.5
MIN_AMPLITUDE = 1e-3
MAX_TAU_SLOW_STEPS = 10  # tau_slow above 10 T is degenerate (300 s at a 30-s step, as §13.5)
REFINE_TOLERANCE = 1e-12
REFINE_MAX_EVALUATIONS = 1000
GATE_FIELDS = {
    "threshold_relaxation": relaxation.Parameters,
    "boltzmann_eyring": series.BoltzmannEyring,
}
VERIFIED = (
    "status",
    "G0",
    "domain",
    "tau_fast_s",
    "tau_slow_s",
    "A_fast",
    "A_slow",
    "A_fast_share",
    "C",
    "G_ss_over_G0",
    "degenerate",
    "degenerate_reasons",
)
VERIFY_RTOL = 1e-6
VERIFY_ATOL = 1e-12


def ms(seconds):
    """Seconds to integer milliseconds, rounded half up."""
    return int(math.floor(seconds * 1000.0 + 0.5))


def start_grid(step_ms):
    """Row 9: the 1-2-5 ladder in integer ms, every bound inclusive. tau_f has 600 tau_f >= T and
    15 tau_f <= T; tau_s has 30 tau_s >= T and 3 tau_s <= 5 T."""
    fast = [t for t in LADDER_MS if 600 * t >= step_ms and 15 * t <= step_ms]
    slow = [t for t in LADDER_MS if 30 * t >= step_ms and 3 * t <= 5 * step_ms]
    return fast, slow


def _given(field):
    return field["status"] in ("stated", "read") and field["value"] is not None


def conventions(protocol_doc):
    """§13.7's part 4 applied to protocol.json: {"values": ..., "sources": ...}."""
    protocol = scorer.read_protocol(protocol_doc)
    f, conv = protocol["fields"], protocol["convention"]
    sources = {}

    def take(name, value, source, status):
        sources[name] = {"from": source, "status": status}
        return value

    holding = conv["holding_mV"]
    if conv["protocol_type"] == "symmetric" or conv["stepped_cell"] is None:
        first, second = "cell_1", "cell_2"
    else:
        first = conv["stepped_cell"]
        second = "cell_2" if first == "cell_1" else "cell_1"
    if holding[first] is not None and holding[second] is not None:
        hold = take("hold_mV", float(holding[first] - holding[second]),
                    "convention.holding_mV", "stated")  # fmt: skip
    else:
        hold = take("hold_mV", 0.0, "convention.holding_mV", "default")

    if _given(f["step_duration_s"]):
        step = take("step_ms", ms(f["step_duration_s"]["value"]), "step_duration_s",
                    f["step_duration_s"]["status"])  # fmt: skip
    elif _given(f["step_durations_s"]):
        durations = f["step_durations_s"]["value"]
        status = f["step_durations_s"]["status"] + (": the only one" if len(durations) == 1
                                                    else ": the longest")  # fmt: skip
        step = take("step_ms", ms(max(durations)), "step_durations_s", status)
    else:
        raise Refusal("protocol.fields: no step duration, stated or read (step_duration_s or "
                      "step_durations_s); the kinetic part cannot be predicted")  # fmt: skip
    if step < 2 * DEFAULT_WINDOW_START_MS:
        raise Refusal("protocol.fields.step_duration_s: shorter than twice the window's start")

    if _given(f["gss_time_s"]):
        gss = take("gss_ms", ms(f["gss_time_s"]["value"]), "gss_time_s", f["gss_time_s"]["status"])
    else:
        gss = take("gss_ms", step, "default: the step's end", "default")

    if _given(f["fit_window_s"]):
        start, end = (ms(x) for x in f["fit_window_s"]["value"])
        if not 0 <= start < end <= step:
            raise Refusal("protocol.fields.fit_window_s: not within the step")
        window = take("window_ms", [start, end], "fit_window_s", f["fit_window_s"]["status"])
    else:
        window = take("window_ms", [DEFAULT_WINDOW_START_MS, step], "default: 5 ms to T",
                      "default")  # fmt: skip

    normalization = scorer.protocol_normalization(protocol)
    take("normalization", normalization, "normalization", f["normalization"]["status"])
    prepulse_mV, prepulse_ms, reference_mV = None, 0, None
    if normalization == "prepulse" and _given(f["prepulse_mV"]):
        prepulse_mV = take("prepulse_mV", f["prepulse_mV"]["value"], "prepulse_mV",
                           f["prepulse_mV"]["status"])  # fmt: skip
        if _given(f["prepulse_s"]):
            prepulse_ms = take("prepulse_ms", ms(f["prepulse_s"]["value"]), "prepulse_s",
                               f["prepulse_s"]["status"])  # fmt: skip
        else:
            prepulse_ms = take("prepulse_ms", 0, "default: dt = 0", "default")
    if normalization == "reference_step":
        if not _given(f["reference_mV"]):
            raise Refusal("protocol.fields.reference_mV: a reference_step normalization states it")
        reference_mV = take("reference_mV", abs(f["reference_mV"]["value"]), "reference_mV",
                            f["reference_mV"]["status"])  # fmt: skip

    fast, slow = start_grid(step)
    take("tau_fast_grid_ms", fast, "row 9: the ladder scaled with T", "rule")
    take("tau_slow_grid_ms", slow, "row 9: the ladder scaled with T", "rule")
    take("offset", "free", "row 8: C free in every case", "rule")
    values = {
        "hold_mV": hold,
        "normalization": normalization,
        "prepulse_mV": prepulse_mV,
        "prepulse_ms": prepulse_ms,
        "reference_mV": reference_mV,
        "step_ms": step,
        "gss_ms": gss,
        "sample_ms": SAMPLE_MS,
        "window_ms": window,
        "tau_fast_grid_ms": fast,
        "tau_slow_grid_ms": slow,
        "min_tau_ratio": MIN_TAU_RATIO,
        "min_amplitude": MIN_AMPLITUDE,
        "max_tau_slow_ms": MAX_TAU_SLOW_STEPS * step,
        "refine_tolerance": REFINE_TOLERANCE,
        "refine_max_evaluations": REFINE_MAX_EVALUATIONS,
        "offset": "free",
    }
    return {"schema": CONVENTIONS_SCHEMA, "rule": CONVENTIONS_RULE, "values": values,
            "sources": sources}  # fmt: skip


@dataclass(frozen=True)
class Conventions:
    """conventions.json's values, read and checked."""

    hold_mV: float
    normalization: str
    prepulse_mV: object
    prepulse_ms: int
    reference_mV: object
    step_ms: int
    gss_ms: int
    sample_ms: int
    window_ms: tuple
    tau_fast_grid_ms: tuple
    tau_slow_grid_ms: tuple
    min_tau_ratio: float
    min_amplitude: float
    max_tau_slow_ms: int
    refine_tolerance: float
    refine_max_evaluations: int
    offset: str

    @classmethod
    def from_json(cls, doc):
        if not isinstance(doc, dict) or doc.get("schema") != CONVENTIONS_SCHEMA:
            raise Refusal(f"conventions.schema: absent or not {CONVENTIONS_SCHEMA}")
        values = doc.get("values")
        names = cls.__dataclass_fields__
        if not isinstance(values, dict) or set(values) != set(names):
            raise Refusal("conventions.values: not exactly §13.7 part 4's conventions")
        out = dict(values)
        for key in ("window_ms", "tau_fast_grid_ms", "tau_slow_grid_ms"):
            out[key] = tuple(values[key])
        made = cls(**out)
        if made.offset != "free" or made.sample_ms != SAMPLE_MS:
            raise Refusal("conventions.values: C is free and the grid is 1 ms (rows 6 and 8)")
        if (list(made.tau_fast_grid_ms), list(made.tau_slow_grid_ms)) != start_grid(made.step_ms):
            raise Refusal("conventions.values: the start grid is not row 9's for this step")
        return made


@dataclass(frozen=True)
class LawParameters:
    """One block of kinds and parameters for the two gates, fast then slow (series.GATES)."""

    kinds: tuple
    gates: tuple

    @classmethod
    def from_json(cls, doc):
        """{"kinds": [kind, kind], "gates": [{field: number}, {field: number}]}, each gate's keys
        exactly its kind's fields."""
        if not isinstance(doc, dict) or set(doc) != {"kinds", "gates"}:
            raise Refusal("parameters: not an object with exactly 'kinds' and 'gates'")
        kinds, blocks = doc["kinds"], doc["gates"]
        if not (isinstance(kinds, list) and len(kinds) == series.GATE_COUNT
                and all(k in series.KINDS for k in kinds)):  # fmt: skip
            raise Refusal(f"parameters.kinds: not {series.GATE_COUNT} of {series.KINDS}")
        if not (isinstance(blocks, list) and len(blocks) == series.GATE_COUNT):
            raise Refusal(f"parameters.gates: not {series.GATE_COUNT} objects")
        gates = []
        for i, (kind, block) in enumerate(zip(kinds, blocks, strict=True)):
            fields = GATE_FIELDS[kind]._fields
            if not isinstance(block, dict) or set(block) != set(fields):
                raise Refusal(f"parameters.gates[{i}]: keys are not {fields}")
            values = {f: scorer.number(block, f, f"parameters.gates[{i}]") for f in fields}
            gates.append(GATE_FIELDS[kind](**values))
        return cls(tuple(kinds), tuple(gates))

    def to_json(self):
        gates = [{f: float(x) for f, x in g._asdict().items()} for g in self.gates]
        return {"kinds": list(self.kinds), "gates": gates}


def time_grid(conv):
    """t_k = k ms from the step's onset, k = 0 to T/1 ms, in seconds."""
    return (np.arange(conv.step_ms // conv.sample_ms + 1) * conv.sample_ms) / 1000.0


def predict(params, vj_mV, conv):
    """The law's clamped trace for one step to vj_mV (signed, mV), as §13.7's part 4 pins it."""
    kinds, p = tuple(params.kinds), tuple(params.gates)
    v_hold, v_step = 1e-3 * conv.hold_mV, 1e-3 * vj_mV
    held = tuple(np.float64(r.target) for r in series.kinetics(v_hold, p, kinds=kinds, xp=np))
    t = time_grid(conv)
    gates = series.advance_clamped(held, v_step, p, t, kinds=kinds, xp=np)
    gates = tuple(np.broadcast_to(np.asarray(c, dtype=np.float64), t.shape) for c in gates)
    g = np.asarray(series.conductance(gates, xp=np), dtype=np.float64)
    if conv.gss_ms == conv.step_ms:
        at_gss = tuple(c[-1] for c in gates)
    else:
        at_gss = series.advance_clamped(held, v_step, p, conv.gss_ms / 1000.0, kinds=kinds, xp=np)
    g_ss = float(series.conductance(at_gss, xp=np))
    longest_s = max(conv.step_ms, conv.gss_ms) / 1000.0
    end = at_gss if conv.gss_ms >= conv.step_ms else tuple(c[-1] for c in gates)
    domain = {
        "hold": series.domain_valid(held, v_hold, p, 1.0, 0.0, kinds=kinds, xp=np),
        "step": series.domain_valid(held, v_step, p, 1.0, longest_s, kinds=kinds, xp=np),
        "end": series.domain_valid(end, v_step, p, 1.0, 0.0, kinds=kinds, xp=np),
    }
    if conv.normalization == "prepulse" and conv.prepulse_mV is not None:
        v_pre = 1e-3 * conv.prepulse_mV
        dt = conv.prepulse_ms / 1000.0
        at_pre = series.advance_clamped(held, v_pre, p, dt, kinds=kinds, xp=np)
        domain["prepulse"] = series.domain_valid(held, v_pre, p, 1.0, dt, kinds=kinds, xp=np)
        g0 = float(series.conductance(at_pre, xp=np))
    elif conv.normalization == "reference_step":
        v_ref = 1e-3 * math.copysign(conv.reference_mV, vj_mV)
        at_ref = series.advance_clamped(held, v_ref, p, conv.gss_ms / 1000.0, kinds=kinds, xp=np)
        domain["reference"] = series.domain_valid(held, v_ref, p, 1.0, conv.gss_ms / 1000.0,
                                                  kinds=kinds, xp=np)  # fmt: skip
        g0 = float(series.conductance(at_ref, xp=np))
    else:
        g0 = float(series.conductance(held, xp=np))
    domain = {k: bool(v) for k, v in domain.items()}
    domain["finite"] = bool(np.all(np.isfinite(g)) and math.isfinite(g0) and g0 > 0
                            and math.isfinite(g_ss))  # fmt: skip
    rates = series.kinetics(v_step, p, kinds=kinds, xp=np)
    report = [
        {
            "gate": name,
            "kind": kind,
            "c_hold": float(c),
            "target": float(r.target),
            "relaxation_per_s": float(r.relaxation_per_s),
        }
        for name, kind, c, r in zip(series.GATES, kinds, held, rates, strict=True)
    ]
    return {
        "vj_mV": float(vj_mV),
        "t_s": t,
        "g": g,
        "G0": g0,
        "G_ss": g_ss,
        "domain": domain,
        "in_domain": all(domain.values()),
        "gates": report,
    }


def _project(t, y, tau_fast, tau_slow):
    """Variable projection at one pair: the design, its linear coefficients (C, A_f, A_s) and the
    residual, design @ coefficients - y."""
    design = np.column_stack((np.ones_like(t), np.exp(-t / tau_fast), np.exp(-t / tau_slow)))
    coefficients = np.linalg.lstsq(design, y, rcond=None)[0]
    return design, coefficients, design @ coefficients - y


def fit_two_exponentials(t, y, conv):
    """C + A_f exp(-t/tau_f) + A_s exp(-t/tau_s) by variable projection from row 9's grid."""
    fast = [x / 1000.0 for x in conv.tau_fast_grid_ms]
    slow = [x / 1000.0 for x in conv.tau_slow_grid_ms]
    grid = [(f, s) for f in fast for s in slow if f < s]
    sums = [float(r @ r) for r in (_project(t, y, f, s)[2] for f, s in grid)]
    start = grid[int(np.argmin(sums))]  # argmin's first minimum: grid order breaks a tie

    def residual(ln_tau):
        return _project(t, y, *np.exp(ln_tau))[2]

    def jacobian(ln_tau):  # Kaufman's: (I - P) (dPhi/d ln tau_j) a, one column per time
        tau = np.exp(ln_tau)
        design, coefficients, _ = _project(t, y, *tau)
        q = np.linalg.qr(design)[0]
        columns = []
        for j in (0, 1):
            d = coefficients[1 + j] * design[:, 1 + j] * (t / tau[j])
            columns.append(d - q @ (q.T @ d))
        return np.column_stack(columns)

    tol = conv.refine_tolerance
    result = least_squares(
        residual,
        np.log(start),
        jac=jacobian,
        method="lm",
        xtol=tol,
        ftol=tol,
        gtol=tol,
        max_nfev=conv.refine_max_evaluations,
    )
    tau = np.exp(result.x)
    _, coefficients, r = _project(t, y, *tau)
    terms = sorted(((tau[0], coefficients[1]), (tau[1], coefficients[2])), key=lambda x: x[0])
    (tau_f, a_f), (tau_s, a_s) = terms
    total = float(a_f + a_s)
    return {
        "tau_fast_s": float(tau_f),
        "tau_slow_s": float(tau_s),
        "A_fast": float(a_f),
        "A_slow": float(a_s),
        "A_fast_share": float(a_f) / total if total != 0 and math.isfinite(total) else None,
        "C": float(coefficients[0]),
        "rms": float(np.sqrt(np.mean(r * r))),
        "samples": int(t.size),
        "grid_start_s": [float(x) for x in start],
        "grid_rss": float(min(sums)),
        "refinement": {
            "status": int(result.status),
            "converged": bool(result.status > 0),
            "evaluations": int(result.nfev),
        },
    }


def degenerate_reasons(fit, conv):
    """Row 11's degenerate fit: every reason that holds (an empty list: not degenerate)."""
    reasons = []
    if not fit["refinement"]["converged"]:
        reasons.append("the refinement did not converge")
    values = [fit[k] for k in ("tau_fast_s", "tau_slow_s", "A_fast", "A_slow", "C")]
    if not all(math.isfinite(x) for x in values) or not fit["tau_fast_s"] > 0:
        return reasons + ["a fitted value is not finite, or a time not positive"]
    if fit["tau_slow_s"] / fit["tau_fast_s"] < conv.min_tau_ratio:
        reasons.append(f"tau_slow/tau_fast below {conv.min_tau_ratio:g}")
    for key in ("A_fast", "A_slow"):
        if fit[key] < conv.min_amplitude:
            reasons.append(f"{key} below {conv.min_amplitude:g}")
    if fit["tau_slow_s"] * 1000.0 > conv.max_tau_slow_ms:
        reasons.append(f"tau_slow above {conv.max_tau_slow_ms / 1000.0:g} s")
    return reasons


def readout(trace, conv):
    """The fitted times, amplitudes and offset, G_ss/G_0 and the degenerate test (rows 7 to 12)."""
    head = {"vj_mV": trace["vj_mV"], "G0": trace["G0"], "domain": trace["domain"],
            "gates": trace["gates"]}  # fmt: skip
    if not trace["in_domain"]:
        return {**head, "status": "cannot_predict"}
    y = trace["g"] / trace["G0"]
    first, last = (x // conv.sample_ms for x in conv.window_ms)
    fit = fit_two_exponentials(trace["t_s"][first : last + 1], y[first : last + 1], conv)
    reasons = degenerate_reasons(fit, conv)
    return {
        **head,
        "status": "predicted",
        **fit,
        "G_ss_over_G0": float(trace["G_ss"] / trace["G0"]),
        "degenerate": bool(reasons),
        "degenerate_reasons": reasons,
    }


def _jsonable(x):
    if isinstance(x, dict):
        return {k: _jsonable(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_jsonable(v) for v in x]
    if isinstance(x, (bool, np.bool_)):
        return bool(x)
    if isinstance(x, (int, np.integer)):
        return int(x)
    if isinstance(x, (float, np.floating)):
        return float(x) if math.isfinite(x) else None
    return x


def held_out_voltages(fit_doc):
    """Both polarities of every held-out magnitude named by fit.json's split, read without any
    held-out value (the predictor never opens held_out.json)."""
    split = scorer.read_observations(fit_doc, "train")["split"]["held_out"]
    magnitudes = sorted(set(split["decay_mV"]) | set(split["steady_mV"]))
    return [s * m for m in magnitudes for s in (-1.0, 1.0)]


def predictions_document(params, conv, voltages, conventions_sha256=None):
    """predictions.json: one block of kinds and parameters, and its readout at each voltage."""
    block = params.to_json()
    return _jsonable(
        {
            "schema": scorer.PREDICTIONS_SCHEMA,
            "law": series.LAW_ID,
            "rule": scorer.RULE,
            "kinds": block["kinds"],
            "parameters": block["gates"],
            "conventions": {k: getattr(conv, k) for k in conv.__dataclass_fields__},
            "conventions_sha256": conventions_sha256,
            "predictions": [readout(predict(params, v, conv), conv) for v in voltages],
        }
    )


def provenance():
    """The checkout's Git revision and its dirty paths, where this module sits in one."""
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        done = subprocess.run(("git", "-C", str(root), *args), capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    revision, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    return {
        "root": str(root),
        "git_revision": revision.strip() if revision else None,
        "dirty_paths": status.splitlines() if status is not None else None,
    }


def _differences(stated, fresh, where, out):
    """Paths where two JSON values differ: numbers beyond VERIFY_RTOL, anything else unequal."""
    numbers = (int, float)
    if isinstance(stated, dict) and isinstance(fresh, dict):
        for key in sorted(set(stated) | set(fresh), key=str):
            if key not in stated or key not in fresh:
                out.append(f"{where}.{key}")
            else:
                _differences(stated[key], fresh[key], f"{where}.{key}", out)
    elif isinstance(stated, list) and isinstance(fresh, list):
        if len(stated) != len(fresh):
            out.append(where)
        for i, (a, b) in enumerate(zip(stated, fresh, strict=False)):  # lengths checked above
            _differences(a, b, f"{where}[{i}]", out)
    elif (isinstance(stated, numbers) and isinstance(fresh, numbers)
          and not isinstance(stated, bool) and not isinstance(fresh, bool)):  # fmt: skip
        if not math.isclose(stated, fresh, rel_tol=VERIFY_RTOL, abs_tol=VERIFY_ATOL):
            out.append(where)
    elif stated != fresh:
        out.append(where)
    return out


def verify(doc, conv, voltages):
    """Recompute predictions.json from its one stated block under the given conventions, at the
    given voltages, and refuse any difference, naming its paths."""
    scorer.read_predictions(doc, set(voltages))
    stated_conventions = doc.get("conventions")
    if stated_conventions != _jsonable({k: getattr(conv, k) for k in conv.__dataclass_fields__}):
        raise Refusal("predictions.conventions: not the conventions given")
    params = LawParameters.from_json({"kinds": doc["kinds"], "gates": doc["parameters"]})
    fresh = predictions_document(params, conv, voltages)
    differences = []
    for key in ("schema", "law", "rule", "kinds", "parameters"):
        _differences(doc.get(key), fresh[key], f"predictions.{key}", differences)
    stated = {e.get("vj_mV"): e for e in doc["predictions"] if isinstance(e, dict)}
    for i, again in enumerate(fresh["predictions"]):
        entry = stated.get(again["vj_mV"], {})
        for key in VERIFIED:
            if key in entry or key in again:
                _differences(entry.get(key), again.get(key), f"predictions[{i}].{key}",
                             differences)  # fmt: skip
    if differences:
        raise Refusal(f"the stated predictions differ from their recomputation at {differences}")
    return True


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    c = stages.add_parser("conventions", help="§13.7 part 4 applied to protocol.json")
    c.add_argument("protocol")
    c.add_argument("out")
    p = stages.add_parser("predict", help="predictions.json from one parameter block")
    p.add_argument("parameters")
    p.add_argument("conventions")
    p.add_argument("fit")
    p.add_argument("out")
    v = stages.add_parser("verify", help="recompute predictions.json from its stated block")
    v.add_argument("predictions")
    v.add_argument("conventions")
    v.add_argument("fit")
    args = parser.parse_args(argv)
    try:
        if args.stage == "conventions":
            doc = conventions(json.loads(Path(args.protocol).read_text()))
            doc["protocol_sha256"] = _sha256(args.protocol)
            Path(args.out).write_text(json.dumps(doc, indent=1) + "\n")
            for name, source in sorted(doc["sources"].items()):
                print(f"{name}: from {source['from']} ({source['status']})")
            return 0
        conv = Conventions.from_json(json.loads(Path(args.conventions).read_text()))
        voltages = held_out_voltages(json.loads(Path(args.fit).read_text()))
        if args.stage == "predict":
            params = LawParameters.from_json(json.loads(Path(args.parameters).read_text()))
            doc = predictions_document(params, conv, voltages, _sha256(args.conventions))
            doc["provenance"] = provenance()
            doc["utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            Path(args.out).write_text(json.dumps(doc, indent=1) + "\n")
            for e in doc["predictions"]:
                extra = f", degenerate: {e['degenerate_reasons']}" if e.get("degenerate") else ""
                print(f"{e['vj_mV']:+g} mV: {e['status']}{extra}")
            return 0
        verify(json.loads(Path(args.predictions).read_text()), conv, voltages)
        print("verified: every prediction recomputes from the stated block")
        return 0
    except Refusal as err:
        print(f"REFUSED: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
