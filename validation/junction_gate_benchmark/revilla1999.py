"""FR-30's benchmark on Revilla, Castro and Barrio (1999): the prediction and its readout
(docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.5; D311).

**The prediction** (`predict`) is junction_series_gates@1 clamped, as section 13 hosts it:
- each gate starts at its steady state at the holding level, V_j = 0 (`kinetics(0).target`);
- G_0 is the conductance after a zero-length step to the +10 mV prepulse (`advance_clamped` with
  dt = 0). The law has no instantaneous voltage dependence, so G_0 is the 0-mV steady conductance,
  computed and never assumed to be 1;
- the 30-s step to V_j is one call of `advance_clamped` from that state, with dt the grid's times
  (t_k = k ms, k = 0 to 30000, from the step's onset), so each sample is exact and none is chained;
- `domain_valid` holds at the holding level, the prepulse, the step (dt = 30 s) and the end state,
  with a finite trace and G_0 > 0, or the voltage cannot be predicted (section 13, rule 4).
Both gate kinds read |V_j|, so one block of kinds and parameters gives the same prediction at both
polarities (§13.5).

**The readout** (`readout`), on y = g/G_0 over the window 5 ms <= t <= 30 s (29,996 samples):
- the form y = C + A_f exp(-t/tau_f) + A_s exp(-t/tau_s), C free, by unweighted least squares;
- variable projection: C, A_f and A_s by linear least squares at each (tau_f, tau_s);
- the start: the fixed grid tau_f in {0.05, 0.1, 0.2, 0.5, 1, 2} s by tau_s in {1, 2, 5, 10, 20, 50}
  s with tau_f < tau_s (33 pairs), the smallest residual sum of squares, and the first in grid order
  (tau_f, then tau_s, ascending) on a tie;
- the refinement: the projected residual over (ln tau_f, ln tau_s), unbounded, by Levenberg-
  Marquardt (scipy's least_squares, method "lm") with Kaufman's Jacobian, xtol = ftol = gtol =
  1e-12 and at most 1000 evaluations; then C, A_f and A_s at the final pair, and the terms sorted so
  that tau_f < tau_s;
- G_ss/G_0 is the t = 30 s sample over G_0, never the offset C or an asymptote, whatever the fit;
- degenerate: tau_s/tau_f < 1.5, A_f or A_s below 1e-3 (signed, so a rising term is degenerate),
  tau_s above 300 s, or a refinement that does not converge or ends non-finite or non-positive. The
  scorer then fails that voltage's time comparisons, with these reasons.

Stages (from the checkout's root, with PYTHONPATH=src and JAX_ENABLE_X64=1):
    python -m validation.junction_gate_benchmark.revilla1999 predict PARAMETERS OUT [--voltages MV]
        predictions.json from one parameter block, {"kinds": [k, k], "gates": [{...}, {...}]}
    python -m validation.junction_gate_benchmark.revilla1999 verify PREDICTIONS
        recompute every prediction from the file's stated block and refuse a difference
The scorer is revilla1999_score.py (standard library only); `score` is re-exported here.
"""

import argparse
import json
import math
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares

from cells.laws.junctions import junction_series_gates as series
from cells.laws.junctions import junction_voltage_relaxation as relaxation
from validation.junction_gate_benchmark import revilla1999_score as scorer
from validation.junction_gate_benchmark.revilla1999_score import HELD_OUT_MV, Refusal, score

__all__ = ["PROTOCOL", "READOUT", "LawParameters", "predict", "readout", "score", "verify"]

GATE_FIELDS = {
    "threshold_relaxation": relaxation.Parameters,
    "boltzmann_eyring": series.BoltzmannEyring,
}
# verify's comparison: the readout's judged and reported quantities, within a relative 1e-6 (far
# inside every judged tolerance, and loose enough for another BLAS thread count).
VERIFIED = (
    "status",
    "G0",
    "domain",
    "tau_fast_s",
    "tau_slow_s",
    "A_fast",
    "A_slow",
    "C",
    "G_ss_over_G0",
    "degenerate",
    "degenerate_reasons",
)
VERIFY_RTOL = 1e-6
VERIFY_ATOL = 1e-12


@dataclass(frozen=True)
class Protocol:
    """The step protocol (§13.5), in integer milliseconds so that the grid is exact."""

    hold_mV: float = 0.0
    prepulse_mV: float = 10.0
    step_ms: int = 30_000
    sample_ms: int = 1
    window_ms: tuple = (5, 30_000)


@dataclass(frozen=True)
class Readout:
    """The readout's fit and its degenerate criteria (§13.5)."""

    tau_fast_grid_s: tuple = (0.05, 0.1, 0.2, 0.5, 1.0, 2.0)
    tau_slow_grid_s: tuple = (1.0, 2.0, 5.0, 10.0, 20.0, 50.0)
    min_tau_ratio: float = 1.5
    min_amplitude: float = 1e-3
    max_tau_slow_s: float = 300.0
    refine_tolerance: float = 1e-12
    refine_max_evaluations: int = 1000


PROTOCOL = Protocol()
READOUT = Readout()


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
        if not (
            isinstance(kinds, list)
            and len(kinds) == series.GATE_COUNT
            and all(k in series.KINDS for k in kinds)
        ):
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


def time_grid(protocol=PROTOCOL):
    """t_k = k sample_ms from the step's onset, k = 0 to step_ms/sample_ms, in seconds."""
    return (np.arange(protocol.step_ms // protocol.sample_ms + 1) * protocol.sample_ms) / 1000.0


def predict(params, vj_mV, protocol=PROTOCOL):
    """The law's clamped trace for one step to vj_mV (signed, mV), as §13.5 pins it."""
    kinds, p = tuple(params.kinds), tuple(params.gates)
    v_hold, v_pre, v_step = (1e-3 * x for x in (protocol.hold_mV, protocol.prepulse_mV, vj_mV))
    held = tuple(np.float64(r.target) for r in series.kinetics(v_hold, p, kinds=kinds, xp=np))
    at_prepulse = series.advance_clamped(held, v_pre, p, 0.0, kinds=kinds, xp=np)
    g0 = float(series.conductance(at_prepulse, xp=np))
    t = time_grid(protocol)
    gates = series.advance_clamped(held, v_step, p, t, kinds=kinds, xp=np)
    gates = tuple(np.broadcast_to(np.asarray(c, dtype=np.float64), t.shape) for c in gates)
    g = np.asarray(series.conductance(gates, xp=np), dtype=np.float64)
    end = tuple(c[-1] for c in gates)
    step_s = protocol.step_ms / 1000.0
    domain = {
        "hold": series.domain_valid(held, v_hold, p, 1.0, 0.0, kinds=kinds, xp=np),
        "prepulse": series.domain_valid(held, v_pre, p, 1.0, 0.0, kinds=kinds, xp=np),
        "step": series.domain_valid(held, v_step, p, 1.0, step_s, kinds=kinds, xp=np),
        "end": series.domain_valid(end, v_step, p, 1.0, 0.0, kinds=kinds, xp=np),
    }
    domain = {k: bool(v) for k, v in domain.items()}
    domain["finite"] = bool(np.all(np.isfinite(g)) and math.isfinite(g0) and g0 > 0)
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
        "protocol": protocol,
        "t_s": t,
        "g": g,
        "G0": g0,
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


def fit_two_exponentials(t, y, rule=READOUT):
    """C + A_f exp(-t/tau_f) + A_s exp(-t/tau_s) by variable projection from the fixed grid."""
    grid = [(f, s) for f in rule.tau_fast_grid_s for s in rule.tau_slow_grid_s if f < s]
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

    tol = rule.refine_tolerance
    result = least_squares(
        residual,
        np.log(start),
        jac=jacobian,
        method="lm",
        xtol=tol,
        ftol=tol,
        gtol=tol,
        max_nfev=rule.refine_max_evaluations,
    )
    tau = np.exp(result.x)
    _, coefficients, r = _project(t, y, *tau)
    terms = sorted(((tau[0], coefficients[1]), (tau[1], coefficients[2])), key=lambda x: x[0])
    (tau_f, a_f), (tau_s, a_s) = terms
    return {
        "tau_fast_s": float(tau_f),
        "tau_slow_s": float(tau_s),
        "A_fast": float(a_f),
        "A_slow": float(a_s),
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


def degenerate_reasons(fit, rule=READOUT):
    """§13.5's degenerate fit: every reason that holds (an empty list: not degenerate)."""
    reasons = []
    if not fit["refinement"]["converged"]:
        reasons.append("the refinement did not converge")
    values = [fit[k] for k in ("tau_fast_s", "tau_slow_s", "A_fast", "A_slow", "C")]
    if not all(math.isfinite(x) for x in values) or not fit["tau_fast_s"] > 0:
        return reasons + ["a fitted value is not finite, or a time not positive"]
    if fit["tau_slow_s"] / fit["tau_fast_s"] < rule.min_tau_ratio:
        reasons.append(f"tau_slow/tau_fast below {rule.min_tau_ratio:g}")
    for key in ("A_fast", "A_slow"):
        if fit[key] < rule.min_amplitude:
            reasons.append(f"{key} below {rule.min_amplitude:g}")
    if fit["tau_slow_s"] > rule.max_tau_slow_s:
        reasons.append(f"tau_slow above {rule.max_tau_slow_s:g} s")
    return reasons


def readout(trace, rule=READOUT):
    """The fitted times, amplitudes and offset, G_ss/G_0 and the degenerate test (§13.5)."""
    protocol = trace["protocol"]
    head = {
        "vj_mV": trace["vj_mV"],
        "G0": trace["G0"],
        "domain": trace["domain"],
        "gates": trace["gates"],
    }
    if not trace["in_domain"]:
        return {**head, "status": "cannot_predict"}
    y = trace["g"] / trace["G0"]
    first, last = (ms // protocol.sample_ms for ms in protocol.window_ms)
    fit = fit_two_exponentials(trace["t_s"][first : last + 1], y[first : last + 1], rule)
    reasons = degenerate_reasons(fit, rule)
    end = protocol.step_ms // protocol.sample_ms
    return {
        **head,
        "status": "predicted",
        **fit,
        "G_ss_over_G0": float(y[end]),
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


def predictions_document(params, voltages=HELD_OUT_MV, protocol=PROTOCOL, rule=READOUT):
    """predictions.json: one block of kinds and parameters, and its readout at each voltage."""
    block = params.to_json()
    return _jsonable(
        {
            "schema": scorer.PREDICTIONS_SCHEMA,
            "law": series.LAW_ID,
            "conventions": scorer.RULE,
            "kinds": block["kinds"],
            "parameters": block["gates"],
            "protocol": asdict(protocol),
            "readout": asdict(rule),
            "predictions": [readout(predict(params, v, protocol), rule) for v in voltages],
        }
    )


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
    elif (
        isinstance(stated, numbers)
        and isinstance(fresh, numbers)
        and not isinstance(stated, bool)
        and not isinstance(fresh, bool)
    ):
        if not math.isclose(stated, fresh, rel_tol=VERIFY_RTOL, abs_tol=VERIFY_ATOL):
            out.append(where)
    elif stated != fresh:
        out.append(where)
    return out


def verify(doc):
    """Recompute predictions.json from its one stated block with this module's pinned protocol and
    readout, and refuse any difference, naming its paths."""
    entries = doc.get("predictions") if isinstance(doc, dict) else None
    if not isinstance(entries, list) or not entries:
        raise Refusal("predictions.predictions: absent, empty or not a list")
    voltages = tuple(scorer.number(e, "vj_mV", f"predictions[{i}]") for i, e in enumerate(entries))
    scorer.read_predictions(doc, voltages)
    if doc.get("protocol") != _jsonable(asdict(PROTOCOL)):
        raise Refusal("predictions.protocol: not §13.5's pinned protocol")
    if doc.get("readout") != _jsonable(asdict(READOUT)):
        raise Refusal("predictions.readout: not §13.5's pinned readout")
    params = LawParameters.from_json({"kinds": doc["kinds"], "gates": doc["parameters"]})
    fresh = predictions_document(params, voltages)
    differences = []
    for key in ("schema", "law", "conventions", "kinds", "parameters"):
        _differences(doc.get(key), fresh[key], f"predictions.{key}", differences)
    for i, (stated, again) in enumerate(zip(entries, fresh["predictions"], strict=True)):
        for key in VERIFIED:
            if key in stated or key in again:
                _differences(
                    stated.get(key), again.get(key), f"predictions[{i}].{key}", differences
                )
    if differences:
        raise Refusal(f"the stated predictions differ from their recomputation at {differences}")
    return True


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    p = stages.add_parser("predict", help="predictions.json from one parameter block")
    p.add_argument("parameters")
    p.add_argument("out")
    p.add_argument("--voltages", type=float, nargs="+", default=list(HELD_OUT_MV))
    v = stages.add_parser("verify", help="recompute predictions.json from its stated block")
    v.add_argument("predictions")
    args = parser.parse_args(argv)
    try:
        if args.stage == "predict":
            params = LawParameters.from_json(json.loads(Path(args.parameters).read_text()))
            doc = predictions_document(params, args.voltages)
            doc["provenance"] = provenance()
            doc["utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            Path(args.out).write_text(json.dumps(doc, indent=1) + "\n")
            for e in doc["predictions"]:
                extra = f", degenerate: {e['degenerate_reasons']}" if e.get("degenerate") else ""
                print(f"{e['vj_mV']:+g} mV: {e['status']}{extra}")
            return 0
        verify(json.loads(Path(args.predictions).read_text()))
        print("verified: every prediction recomputes from the stated block")
        return 0
    except Refusal as err:
        print(f"REFUSED: {err}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
