"""FR-30, Revilla, Castro and Barrio (1999): the labelled, non-blind diagnostic's Deliverable 2
(D343, D344), as declared in revilla1999_diagnostic.json, which was committed before this driver.

Labelled and non-blind: it decides nothing (W6), and changes no verdict and no law. Every result is
one study's indication. Its author never fits FR-30 again in any registered role.

**The question** (the lead's ruling (b), with G_ss kept in the training set). A parameter set is
training-compatible at margin m when the registered fit's objective (17 residuals on fit.json, the
registered fitter's own) exceeds the polarity floor by at most m. Which tau_slow and tau_fast at
80 mV do compatible sets predict, against the -80 and +80 mV windows? Beside it, labelled "kinetics
alone": does any set pass every tau comparison at all six voltages?

**What it calls.** Every reported number and every compatibility or window decision comes from the
tagged revilla1999.predict and revilla1999.readout, judged by the tagged scorer's compare_time,
compare_steady, resolve and score. Inside the search loop only, it uses the registered fitter's
surrogate: the tagged fit_two_exponentials and degenerate_reasons on every 10th sample of predict's
trace in the readout window, with G_ss/G_0 from the full trace. The objective is this module's
re-implementation of fit_revilla1999.py's (f734b96e, branch fr30-revilla-fit); the identity stage
shows it returns the judged fit's chi^2 and each of its residuals at the judged parameters.

**The search** (the declaration's): stage A minimizes chi^2 from every declared start; stage B
traces profiles (chi^2 with the constraint residual (ln Q - ln q)/0.002 at each grid target q) by
chains warm-started from distinct stage-A solutions, then one repair sweep each way; stage C
re-evaluates every solution with the exact readout and polishes the profile points near the margins.

Stages (from a frozen snapshot's root, with PYTHONPATH=src and JAX_ENABLE_X64=1):
    python -m validation.junction_gate_benchmark.revilla1999_diagnostic identity OUT_DIR \
            --predicted PREDICTIONS
        the objective at the judged parameters, the gates' shared slope and midpoint, and the
        comparison of a fresh `revilla1999 predict` output with predictions.json
    python -m validation.junction_gate_benchmark.revilla1999_diagnostic search OUT_DIR [--workers 4]
    python -m validation.junction_gate_benchmark.revilla1999_diagnostic smoke OUT_DIR [--workers 2]
        the search's code paths with tiny budgets and the predicted magnitude swapped to 60 mV, a
        training magnitude, so that the smoke evaluates nothing at 80 mV
"""

import argparse
import difflib
import hashlib
import json
import math
import multiprocessing
import platform
import statistics
import subprocess
import sys
import time
import traceback
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.optimize import least_squares

from cells.laws.junctions import junction_series_gates as series
from validation.junction_gate_benchmark import revilla1999 as harness
from validation.junction_gate_benchmark import revilla1999_score as scorer

DECLARATION = Path(__file__).with_name("revilla1999_diagnostic.json")
INPUT_NAMES = (
    "fit_json",
    "held_out_json",
    "fit_report_json",
    "params_json",
    "predictions_json",
    "verdict_json",
    "checker_verdict_json",
)
KINDS = ("boltzmann_eyring", "boltzmann_eyring")
TIMES = scorer.TIMES
STEADY = scorer.STEADY
# The registered fitter's objective (fit_revilla1999.py at f734b96e).
TIMED_MV = (-100, -60, 60, 100)
STEADY_ONLY_MV = (-40, -20, 20, 40)
TRAINING_MAGNITUDES = (20, 40, 60, 100)
TRAINING_READOUTS = (60, 100)
RATIO_VJ_MV = -100
RATIO_PREFIX = "ratio of the fast to the slow amplitude"
RATIO_SIGMA_LN = 0.2
PENALTY = 30.0  # the fitter's: a training residual where the law gives no reading
SURROGATE_EVERY = 10
TOLERANCE = 1e-9
DIFF_STEP = 1e-6
COORDINATES = ("ln_rate", "slope", "midpoint", "split", "residual")
LOWER = {"ln_rate": math.log(1e-4), "slope": 0.01, "midpoint": 0.0, "split": 0.0, "residual": 0.0}
UPPER = {"ln_rate": math.log(1e3), "slope": 3.3, "midpoint": 1.2, "split": 1.0, "residual": 0.999}
FAMILIES = {"free": COORDINATES, "slice": tuple(c for c in COORDINATES if c != "split")}
# This diagnostic's (declared).
SIGMA_C = 0.002  # the profile constraint's scale, in ln units
CONSTRAINT_PENALTY = 1e4  # a profile constraint where the law gives no reading (not declared:
# far above any reachable constraint residual, so a missing reading is never preferred)
KINETICS_TARGET_U = 0.8
SEEDS = {"free": 20261124, "slice": 20261125}
IDENTITY_RTOL = 1e-9
IDENTITY_ATOL = 1e-12
GATE_RTOL = 1e-12


@dataclass(frozen=True)
class Budget:
    stage_a_nfev: int = 1500
    profile_nfev: int = 400
    polish_nfev: int = 60
    kinetics_nfev: int = 400
    chains: int = 6
    chain_excess: float = 10.0
    distinct_ln: float = 0.02
    repair_ln: float = 0.01
    polish_excess: float = 3.0
    registered_starts: int = 16
    recorded_starts: int = 6
    random_starts: int = 16
    exact_batch: int = 12


DECLARED = Budget()
SMOKE = Budget(
    stage_a_nfev=12,
    profile_nfev=8,
    polish_nfev=3,
    kinetics_nfev=8,
    chains=1,
    registered_starts=1,
    recorded_starts=1,
    random_starts=1,
    exact_batch=4,
)


def utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def log(message):
    print(f"{utc()} {message}", flush=True)


def jsonable(x):
    if isinstance(x, dict):
        return {(k if isinstance(k, str) else str(k)): jsonable(v) for k, v in x.items()}
    return harness._jsonable(x) if not isinstance(x, (list, tuple)) else [jsonable(v) for v in x]


def provenance():
    root = Path(__file__).resolve().parents[2]

    def git(*args):
        done = subprocess.run(("git", "-C", str(root), *args), capture_output=True, text=True)
        return done.stdout if done.returncode == 0 else None

    revision, status = git("rev-parse", "HEAD"), git("status", "--porcelain")
    snapshot = root / "SNAPSHOT.json"
    frozen = None
    if snapshot.is_file():
        meta = json.loads(snapshot.read_text())
        frozen = {k: meta.get(k) for k in ("git_revision", "patch_sha256", "repository")}
    return {
        "root": str(root),
        "git_revision": revision.strip() if revision else None,
        "dirty_paths": status.splitlines() if status is not None else None,
        "snapshot": frozen,
    }


def load():
    """The declaration and its inputs, each refused unless its bytes are the record's."""
    declaration = json.loads(DECLARATION.read_text())
    docs, record = {}, {}
    for name in INPUT_NAMES:
        path, expected = declaration["inputs"][name]["path"], declaration["inputs"][name]["sha256"]
        digest = sha256(path)
        if digest != expected:
            raise SystemExit(f"{name}: sha256 {digest} is not the record's {expected}")
        docs[name] = json.loads(Path(path).read_text())
        record[name] = {"path": path, "sha256": digest}
    return declaration, docs, record


# ---------------------------------------------------------------- the registered objective


def training(fit_doc):
    """fit.json's 17 training rows, as fit_revilla1999.training reads them, and the G_ss floor."""
    timed = scorer.resolve(fit_doc, TIMED_MV)["entries"]
    steady = scorer.resolve(fit_doc, STEADY_ONLY_MV, (STEADY,))["entries"]
    entries = {**timed, **steady}
    reported = [e["sem"] for (v, o), e in entries.items() if o == STEADY and e["sem"]]
    floor = statistics.median(reported)
    rows = []
    for (v, observable), e in sorted(entries.items()):
        row = {"vj_mV": v, "observable": observable, "value": e["value"]}
        if observable in TIMES:
            row.update(kind="time", sigma=e["sem"] / e["value"])
        else:
            row.update(kind="steady", sigma=e["sem"] if e["sem"] is not None else floor)
        rows.append(row)
    ratios = [
        entry
        for _, group in sorted(fit_doc["observables"].items())
        for entry in group
        if isinstance(entry, dict)
        and entry.get("vj_mV") == RATIO_VJ_MV
        and str(entry.get("observable", "")).startswith(RATIO_PREFIX)
    ]
    if len(ratios) != 1:
        raise SystemExit("fit.json: not one amplitude ratio at -100 mV")
    value = scorer.number(ratios[0], "value", "ratio", positive=True)
    rows.append(
        {
            "vj_mV": RATIO_VJ_MV,
            "observable": "A_fast/A_slow",
            "value": value,
            "kind": "ratio",
            "sigma": RATIO_SIGMA_LN,
        }
    )
    return rows, floor


def readings(params, every, magnitudes, readout_magnitudes):
    """G_ss/G_0 at each magnitude, and the readout at those asked (every = 1: the tagged exact
    readout; else the fitter's surrogate on every `every`-th sample). None if out of domain."""
    out = {}
    for magnitude in magnitudes:
        trace = harness.predict(params, magnitude)
        if not trace["in_domain"]:
            return None
        reading = {"G_ss/G_0": float(trace["g"][-1] / trace["G0"])}
        if magnitude in readout_magnitudes:
            if every == 1:
                fit = harness.readout(trace)
            else:
                protocol = trace["protocol"]
                first, last = (ms // protocol.sample_ms for ms in protocol.window_ms)
                y = trace["g"] / trace["G0"]
                window = slice(first, last + 1, every)
                fit = harness.fit_two_exponentials(trace["t_s"][window], y[window])
                fit["degenerate_reasons"] = harness.degenerate_reasons(fit)
            reading.update(
                tau_fast=fit["tau_fast_s"],
                tau_slow=fit["tau_slow_s"],
                A_fast=fit["A_fast"],
                A_slow=fit["A_slow"],
                C=fit["C"],
                degenerate_reasons=list(fit["degenerate_reasons"]),
            )
        out[magnitude] = reading
    return out


def train_residuals(reads, rows):
    """fit_revilla1999.residuals on given readings."""
    out = np.full(len(rows), PENALTY)
    if reads is None:
        return out
    for i, o in enumerate(rows):
        reading = reads[abs(o["vj_mV"])]
        if o["kind"] == "steady":
            out[i] = (reading["G_ss/G_0"] - o["value"]) / o["sigma"]
            continue
        if o["kind"] == "time":
            x = reading[o["observable"]]
        else:
            a_f, a_s = reading["A_fast"], reading["A_slow"]
            x = a_f / a_s if a_f > 0 and a_s > 0 else math.nan
        if math.isfinite(x) and x > 0:
            out[i] = math.log(x / o["value"]) / o["sigma"]
    return out


def gate(ln_rate, slope, midpoint, split, residual):
    return series.BoltzmannEyring(
        rate_per_s=math.exp(ln_rate),
        slope_per_V=100.0 * slope,
        midpoint_V=0.1 * midpoint,
        split=split,
        residual=residual,
    )


def to_params(z, family):
    z = [float(x) for x in z]
    if family == "free":
        fast, slow = z[:5], z[5:]
    else:
        fast, slow = z[:3] + [0.5] + z[3:4], z[4:7] + [0.5] + z[7:8]
    return harness.LawParameters(KINDS, (gate(*fast), gate(*slow)))


def bounds(family):
    names = [c for _ in series.GATES for c in FAMILIES[family]]
    return np.array([LOWER[n] for n in names]), np.array([UPPER[n] for n in names])


# ---------------------------------------------------------------- the starts


def registered_starts(rows, family):
    """fit_revilla1999.starts: 16 fixed starts (V0, A and r per gate, delta 1/2, lambda from the
    training times' inverse-variance log-mean at 60 mV)."""

    def log_mean(observable):
        chosen = [o for o in rows if abs(o["vj_mV"]) == 60 and o["observable"] == observable]
        weights = [1.0 / o["sigma"] ** 2 for o in chosen]
        mean = sum(w * math.log(o["value"]) for w, o in zip(weights, chosen, strict=True))
        return math.exp(mean / sum(weights))

    rates = {"fast": 1.0 / log_mean("tau_fast"), "slow": 1.0 / log_mean("tau_slow")}
    out = []
    for v0_fast in (0.05, 0.07):
        for v0_slow in (0.05, 0.07):
            for slope in (80.0, 140.0):
                for r_fast, r_slow in ((0.3, 0.6), (0.6, 0.3)):
                    z = []
                    for name, v0, r in (("fast", v0_fast, r_fast), ("slow", v0_slow, r_slow)):
                        u = slope * (0.06 - v0)
                        lam = rates[name] / (math.exp(-0.5 * u) + math.exp(0.5 * u))
                        block = [math.log(lam), slope / 100.0, v0 / 0.1, 0.5, r]
                        z += block if family == "free" else block[:3] + block[4:]
                    out.append(z)
    return out


def recorded_starts(fit_report, family):
    """The registered fit's refined solutions (fit_report.json), split 1/2 inserted where needed."""
    out = []
    for r in fit_report["refined"]:
        z = list(r["z"])
        label = f"recorded-{r['mode']}-start{r['start']}"
        if r["mode"] == "free" and family == "free":
            out.append((label, z))
        elif r["mode"] == "symmetric_barrier":
            if family == "free":
                z = z[:3] + [0.5] + z[3:4] + z[4:7] + [0.5] + z[7:8]
            out.append((label, z))
    return out


def all_starts(rows, fit_report, family, budget):
    lo, hi = bounds(family)
    starts = [(f"registered-{i}", z) for i, z in enumerate(registered_starts(rows, family))]
    starts = starts[: budget.registered_starts]
    starts += recorded_starts(fit_report, family)[: budget.recorded_starts]
    rng = np.random.default_rng(SEEDS[family])
    draws = [lo + (hi - lo) * rng.random(lo.size) for _ in range(DECLARED.random_starts)]
    starts += [(f"random-{i}", list(z)) for i, z in enumerate(draws)][: budget.random_starts]
    return [
        (label, [float(x) for x in np.clip(np.asarray(z, float), lo, hi)]) for label, z in starts
    ]


# ---------------------------------------------------------------- the lines


def time_line(predicted, entry, degenerate):
    """One time comparison by the scorer, with its window units (Deliverable 1's)."""
    c = scorer.compare_time(predicted, entry["value"], entry["sem"], degenerate)
    line = {"predicted": predicted, "observed": entry["value"], "passes": c["passes"]}
    if degenerate:
        return {**line, "u": None, "reason": c["reason"]}
    edge = c["sem_edge"] if c["applied"] == "2 SEM" else c["ln_edge"]
    return {
        **line,
        "u": (predicted - entry["value"]) / abs(edge - entry["value"]),
        "applied": c["applied"],
    }


def steady_line(predicted, entry):
    c = scorer.compare_steady(predicted, entry["value"], entry["sem"])
    u = (predicted - entry["value"]) / c["tolerance"]
    return {
        "predicted": predicted,
        "observed": entry["value"],
        "passes": c["passes"],
        "u": u,
        "applied": c["applied"],
    }


# ---------------------------------------------------------------- the solves (pool workers)


def train_fun(z, family, rows, every):
    reads = readings(to_params(z, family), every, TRAINING_MAGNITUDES, TRAINING_READOUTS)
    return train_residuals(reads, rows)


def profile_fun(z, family, rows, every, pred_mV, quantity, ln_q):
    magnitudes = tuple(sorted(set(TRAINING_MAGNITUDES) | {pred_mV}))
    reads = readings(to_params(z, family), every, magnitudes, tuple(sorted({60, 100, pred_mV})))
    r = train_residuals(reads, rows)
    if reads is None:
        c = CONSTRAINT_PENALTY
    else:
        x = reads[pred_mV][quantity]
        c = (math.log(x) - ln_q) / SIGMA_C if math.isfinite(x) and x > 0 else CONSTRAINT_PENALTY
    return np.append(r, c)


def solve(fun, z0, family, args, max_nfev):
    lo, hi = bounds(family)
    began = time.monotonic()
    result = least_squares(
        fun,
        np.clip(np.asarray(z0, dtype=float), lo, hi),
        bounds=(lo, hi),
        args=args,
        method="trf",
        diff_step=DIFF_STEP,
        xtol=TOLERANCE,
        ftol=TOLERANCE,
        gtol=TOLERANCE,
        max_nfev=max_nfev,
    )
    return result, round(time.monotonic() - began, 2)


def at_prediction(z, family, every, pred_mV):
    reads = readings(to_params(z, family), every, (pred_mV,), (pred_mV,))
    if reads is None:
        return {"in_domain": False}
    r = reads[pred_mV]
    return {
        "tau_slow": r["tau_slow"],
        "tau_fast": r["tau_fast"],
        "G_ss/G_0": r["G_ss/G_0"],
        "degenerate_reasons": r["degenerate_reasons"],
    }


def profile_point(z0, family, ctx, quantity, q, max_nfev, every):
    args = (family, ctx["rows"], every, ctx["pred_mV"], quantity, math.log(q))
    result, seconds = solve(profile_fun, z0, family, args, max_nfev)
    r = result.fun
    offset = float(r[-1] * SIGMA_C) if abs(r[-1]) < CONSTRAINT_PENALTY else None
    return {
        "family": family,
        "quantity": quantity,
        "target": q,
        "z0": [float(x) for x in z0],
        "z": [float(x) for x in result.x],
        "chi2_search": float(r[:-1] @ r[:-1]),
        "ln_offset": offset,
        "status": int(result.status),
        "nfev": int(result.nfev),
        "seconds": seconds,
        "every": every,
    }


def exact_evaluation(z, family, ctx):
    """Every reported number for one set: the exact chi^2 and excess, the readouts at 60, the
    predicted magnitude and 100 mV, and its six lines there by the scorer."""
    pred = ctx["pred_mV"]
    magnitudes = tuple(sorted(set(TRAINING_MAGNITUDES) | {pred}))
    reads = readings(to_params(z, family), 1, magnitudes, tuple(sorted({60, 100, pred})))
    if reads is None:
        return {"in_domain": False, "compatible_base": False}
    r = train_residuals(reads, ctx["rows"])
    chi2 = float(r @ r)
    p = reads[pred]
    degenerate = {m: reads[m]["degenerate_reasons"] for m in sorted({60, pred, 100})}
    lines = {}
    for v in (-pred, pred):
        for o in TIMES:
            lines[f"{v:+d} {o}"] = time_line(p[o], ctx["obs_pred"][(v, o)], p["degenerate_reasons"])
        lines[f"{v:+d} {STEADY}"] = steady_line(p["G_ss/G_0"], ctx["obs_pred"][(v, STEADY)])
    return {
        "in_domain": True,
        "chi2": chi2,
        "excess": chi2 - ctx["floor"],
        "compatible_base": not degenerate[60] and not degenerate[100],
        "degenerate": {str(m): reasons for m, reasons in degenerate.items()},
        "at_prediction": {
            "tau_slow": p["tau_slow"],
            "tau_fast": p["tau_fast"],
            "A_fast": p["A_fast"],
            "A_slow": p["A_slow"],
            "C": p["C"],
            "G_ss/G_0": p["G_ss/G_0"],
        },
        "lines": lines,
    }


def kinetics_fun(z, ctx, every):
    magnitudes = ctx["kinetics_magnitudes"]
    reads = readings(to_params(z, "free"), every, magnitudes, magnitudes)
    n = len(ctx["kinetics_entries"]) + 4 * len(magnitudes)
    if reads is None:
        return np.full(n, PENALTY)
    out = []
    for (v, o), entry in ctx["kinetics_entries"]:
        p = reads[abs(v)][o]
        if not (math.isfinite(p) and p > 0):
            out.append(PENALTY)
            continue
        out.append(max(0.0, abs(time_line(p, entry, [])["u"]) - KINETICS_TARGET_U))
    for m in magnitudes:
        f = reads[m]
        tf, ts, af, a_s = f["tau_fast"], f["tau_slow"], f["A_fast"], f["A_slow"]
        if not all(math.isfinite(x) for x in (tf, ts, af, a_s)) or tf <= 0:
            out += [PENALTY] * 4
            continue
        out += [
            max(0.0, 1.6 - ts / tf),
            100.0 * max(0.0, 0.002 - af),
            100.0 * max(0.0, 0.002 - a_s),
            max(0.0, ts - 250.0) / 250.0,
        ]
    return np.asarray(out)


def kinetics_verify(z, ctx):
    """The twelve tau lines by the exact readout and the scorer; feasible when every one passes."""
    magnitudes = ctx["kinetics_magnitudes"]
    reads = readings(to_params(z, "free"), 1, magnitudes, magnitudes)
    if reads is None:
        return {"in_domain": False, "feasible": False}
    lines = {}
    for (v, o), entry in ctx["kinetics_entries"]:
        r = reads[abs(v)]
        lines[f"{v:+d} {o}"] = time_line(r[o], entry, r["degenerate_reasons"])
    us = [abs(line["u"]) for line in lines.values() if line["u"] is not None]
    return {
        "in_domain": True,
        "feasible": all(line["passes"] for line in lines.values()),
        "max_abs_u": max(us) if len(us) == len(lines) else None,
        "degenerate": {str(m): reads[m]["degenerate_reasons"] for m in magnitudes},
        "readouts": {
            str(m): {
                k: reads[m][k]
                for k in ("tau_fast", "tau_slow", "A_fast", "A_slow", "C", "G_ss/G_0")
            }
            for m in magnitudes
        },
        "lines": lines,
    }


def work(task):
    """One pool task. Errors come back as records, so one failure never stops the run."""
    try:
        kind, ctx = task["kind"], task["context"]
        if kind == "minimize":
            args = (task["family"], ctx["rows"], ctx["every"])
            result, seconds = solve(train_fun, task["z0"], task["family"], args, task["max_nfev"])
            return {
                "kind": kind,
                "id": task["id"],
                "family": task["family"],
                "start": task["start"],
                "z0": task["z0"],
                "z": [float(x) for x in result.x],
                "chi2_search": float(2.0 * result.cost),
                "status": int(result.status),
                "nfev": int(result.nfev),
                "seconds": seconds,
                "search_at_prediction": at_prediction(
                    result.x, task["family"], ctx["every"], ctx["pred_mV"]
                ),
            }
        if kind == "chain":
            z, solves = task["z0"], []
            for q in task["targets"]:
                point = profile_point(
                    z, task["family"], ctx, task["quantity"], q, task["max_nfev"], ctx["every"]
                )
                solves.append({**point, "stage": "B-chain", "chain": task["id"]})
                z = point["z"]
            return {"kind": kind, "id": task["id"], "solves": solves}
        if kind == "sweep":
            current, solves = list(task["bests"]), []
            order = list(range(len(task["targets"])))
            if task["direction"] == "down":
                order.reverse()
            for previous, k in zip(order, order[1:], strict=False):
                if current[previous] is None:
                    continue
                q = task["targets"][k]
                point = profile_point(
                    current[previous]["z"],
                    task["family"],
                    ctx,
                    task["quantity"],
                    q,
                    task["max_nfev"],
                    ctx["every"],
                )
                solves.append({**point, "stage": "B-repair", "chain": task["id"]})
                ok = point["ln_offset"] is not None and abs(point["ln_offset"]) <= task["repair_ln"]
                if ok and (current[k] is None or point["chi2_search"] < current[k]["chi2_search"]):
                    current[k] = point
            return {"kind": kind, "id": task["id"], "solves": solves}
        if kind == "exact":
            out = []
            for item in task["items"]:
                out.append(
                    {
                        "ref": item["ref"],
                        "family": item["family"],
                        "exact": exact_evaluation(item["z"], item["family"], ctx),
                    }
                )
            return {"kind": kind, "id": task["id"], "evaluations": out}
        if kind == "polish":
            point = profile_point(
                task["z0"],
                task["family"],
                ctx,
                task["quantity"],
                task["target"],
                task["max_nfev"],
                1,
            )
            point.update(stage="C-polish", chain=task["id"], polished_from=task["ref"])
            return {
                "kind": kind,
                "id": task["id"],
                "solves": [point],
                "exact": exact_evaluation(point["z"], task["family"], ctx),
            }
        if kind == "kinetics":
            result, seconds = solve(
                kinetics_fun, task["z0"], "free", (ctx, ctx["every"]), task["max_nfev"]
            )
            return {
                "kind": kind,
                "id": task["id"],
                "start": task["start"],
                "z0": task["z0"],
                "z": [float(x) for x in result.x],
                "hinge_cost": float(2.0 * result.cost),
                "status": int(result.status),
                "nfev": int(result.nfev),
                "seconds": seconds,
                "verified": kinetics_verify(result.x, ctx),
            }
        raise ValueError(f"unknown task kind {kind!r}")
    except Exception as err:  # noqa: BLE001 -- recorded, never swallowed silently
        return {
            "kind": task.get("kind"),
            "id": task.get("id"),
            "error": f"{type(err).__name__}: {err}",
            "traceback": traceback.format_exc(),
        }


# ---------------------------------------------------------------- the run


def grids(smoke):
    if smoke:  # around the 60 mV training values: nothing at 80 mV
        return {"tau_slow": [18.0, 22.0, 26.0], "tau_fast": [2.0, 3.0, 4.0]}
    slow = set(float(x) for x in np.geomspace(5.0, 50.0, 31))
    slow |= {10.0163, 12.1361, 14.2638, 16.7647, 20.7601, 12.1361 * 1.005, 16.7647 / 1.005}
    fast = set(float(x) for x in np.geomspace(0.2, 6.0, 25))
    fast |= {0.4746, 1.3370, 3.7662, 3.8554, 0.4746 * 1.005, 3.7662 / 1.005}
    return {"tau_slow": sorted(slow), "tau_fast": sorted(fast)}


PROFILES = (("free", "tau_slow"), ("free", "tau_fast"), ("slice", "tau_slow"))


class Run:
    def __init__(self, out, workers, smoke):
        self.out, self.workers, self.smoke = Path(out), workers, smoke
        self.out.mkdir(parents=True, exist_ok=True)
        self.budget = SMOKE if smoke else DECLARED
        self.declaration, self.docs, self.inputs = load()
        rows, sem_floor = training(self.docs["fit_json"])
        self.pred_mV = 60 if smoke else 80
        obs_fit = scorer.resolve(self.docs["fit_json"], TIMED_MV)["entries"]
        obs_held = {} if smoke else scorer.resolve(self.docs["held_out_json"], (-80, 80))["entries"]
        source = obs_fit if smoke else obs_held
        obs_pred = {k: v for k, v in source.items() if abs(k[0]) == self.pred_mV}
        kinetics_magnitudes = (60, 100) if smoke else (60, 80, 100)
        kinetics_entries = [
            (key, entry)
            for key, entry in sorted({**obs_fit, **obs_held}.items())
            if key[1] in TIMES and abs(key[0]) in kinetics_magnitudes
        ]
        self.context = {
            "rows": rows,
            "floor": float(self.declaration["objective"]["floor"]),
            "every": SURROGATE_EVERY,
            "pred_mV": self.pred_mV,
            "obs_pred": obs_pred,
            "kinetics_entries": kinetics_entries,
            "kinetics_magnitudes": kinetics_magnitudes,
        }
        self.sem_floor = sem_floor
        self.solves = (self.out / "solves.jsonl").open("a")
        self.exacts = (self.out / "exact.jsonl").open("a")
        self.records = []  # every solve, in arrival order
        self.exact = {}  # ref -> exact evaluation
        self.errors = []
        self.seconds = {}

    def write(self, stream, record):
        stream.write(json.dumps(jsonable(record)) + "\n")
        stream.flush()

    def run_tasks(self, pool, tasks, label):
        began = time.monotonic()
        results = []
        futures = [pool.submit(MODULE.work, t) for t in tasks]
        for done, future in enumerate(as_completed(futures), 1):
            result = future.result()
            if "error" in result:
                self.errors.append(result)
                log(f"{label}: task {result.get('id')} failed: {result['error']}")
            results.append(result)
            for solve_record in result.get("solves", []):
                ref = f"S{len(self.records)}"
                solve_record["ref"] = ref
                self.records.append(solve_record)
                self.write(self.solves, solve_record)
            if result.get("kind") in ("minimize", "kinetics") and "error" not in result:
                ref = f"S{len(self.records)}"
                result["ref"] = ref
                self.records.append(result)
                self.write(self.solves, result)
            if done % max(1, len(tasks) // 10) == 0 or done == len(tasks):
                log(f"{label}: {done} of {len(tasks)} tasks")
        self.seconds[label] = round(time.monotonic() - began, 1)
        return results

    def task(self, kind, ident, **fields):
        return {"kind": kind, "id": ident, "context": self.context, **fields}

    def go(self):
        b = self.budget
        log(f"start: smoke={self.smoke}, predicted magnitude {self.pred_mV} mV, budget {asdict(b)}")
        context = multiprocessing.get_context("spawn")
        with ProcessPoolExecutor(max_workers=self.workers, mp_context=context) as pool:
            # Stage A: unconstrained, from every declared start of both families.
            tasks = []
            for family in ("free", "slice"):
                for label, z0 in all_starts(
                    self.context["rows"], self.docs["fit_report_json"], family, b
                ):
                    tasks.append(
                        self.task(
                            "minimize",
                            f"A-{family}-{label}",
                            family=family,
                            start=label,
                            z0=z0,
                            max_nfev=b.stage_a_nfev,
                        )
                    )
            stage_a = [r for r in self.run_tasks(pool, tasks, "stage A") if "error" not in r]

            # Stage B: chains from distinct stage-A solutions, per profile.
            grid = grids(self.smoke)
            tasks, self.chain_seeds = [], {}
            for family, quantity in PROFILES:
                seeds = self.chain_seed_choice(stage_a, family, quantity)
                self.chain_seeds[f"{family} {quantity}"] = [s["id"] for s in seeds]
                targets = grid[quantity]
                for s in seeds:
                    q0 = s["search_at_prediction"][quantity]
                    j0 = int(np.argmin([abs(math.log(t) - math.log(q0)) for t in targets]))
                    up, down = targets[j0:], targets[: j0 + 1][::-1]
                    for direction, sequence in (("up", up), ("down", down)):
                        ident = f"B-{family}-{quantity}-{s['start']}-{direction}"
                        tasks.append(
                            self.task(
                                "chain",
                                ident,
                                family=family,
                                quantity=quantity,
                                z0=s["z"],
                                targets=sequence,
                                max_nfev=b.profile_nfev,
                            )
                        )
            self.run_tasks(pool, tasks, "stage B chains")

            # Stage B repair: one sweep each way from each target's best so far.
            tasks = []
            for family, quantity in PROFILES:
                targets = grid[quantity]
                bests = [self.best_search(family, quantity, q) for q in targets]
                for direction in ("up", "down"):
                    ident = f"B-{family}-{quantity}-repair-{direction}"
                    tasks.append(
                        self.task(
                            "sweep",
                            ident,
                            family=family,
                            quantity=quantity,
                            targets=targets,
                            bests=bests,
                            direction=direction,
                            max_nfev=b.profile_nfev,
                            repair_ln=b.repair_ln,
                        )
                    )
            self.run_tasks(pool, tasks, "stage B repair")

            # Stage C: every solution with the exact readout, then the polish near the margins.
            items = [
                {"ref": r["ref"], "family": r["family"], "z": r["z"]}
                for r in self.records
                if r.get("kind") != "kinetics" and "z" in r
            ]
            tasks = [
                self.task("exact", f"C-exact-{i}", items=items[i : i + b.exact_batch])
                for i in range(0, len(items), b.exact_batch)
            ]
            for result in self.run_tasks(pool, tasks, "stage C exact"):
                for e in result.get("evaluations", []):
                    self.exact[e["ref"]] = e["exact"]
                    self.write(self.exacts, e)
            tasks = []
            for family, quantity in PROFILES:
                for q in grid[quantity]:
                    best = self.best_exact(family, quantity, q, stages=("B-chain", "B-repair"))
                    if best is not None and self.exact[best["ref"]]["excess"] <= b.polish_excess:
                        ident = f"C-polish-{family}-{quantity}-{q:.6g}"
                        tasks.append(
                            self.task(
                                "polish",
                                ident,
                                family=family,
                                quantity=quantity,
                                target=q,
                                z0=best["z"],
                                ref=best["ref"],
                                max_nfev=b.polish_nfev,
                            )
                        )
            for result in self.run_tasks(pool, tasks, "stage C polish"):
                if "error" in result:
                    continue
                ref = result["solves"][0]["ref"]
                self.exact[ref] = result["exact"]
                self.write(
                    self.exacts,
                    {"ref": ref, "family": result["solves"][0]["family"], "exact": result["exact"]},
                )

            # Kinetics alone, beside.
            tasks = []
            for label, z0 in all_starts(
                self.context["rows"], self.docs["fit_report_json"], "free", b
            ):
                tasks.append(
                    self.task(
                        "kinetics", f"K-{label}", start=label, z0=z0, max_nfev=b.kinetics_nfev
                    )
                )
            seen = set()
            for family, quantity in PROFILES:
                if family != "free":
                    continue
                for ident in self.chain_seeds[f"{family} {quantity}"]:
                    if ident in seen:
                        continue
                    seen.add(ident)
                    s = next(r for r in stage_a if r["id"] == ident)
                    tasks.append(
                        self.task(
                            "kinetics",
                            f"K-seed-{ident}",
                            start=f"seed {ident}",
                            z0=s["z"],
                            max_nfev=b.kinetics_nfev,
                        )
                    )
            self.kinetics = [
                r for r in self.run_tasks(pool, tasks, "kinetics alone") if "error" not in r
            ]
        return self.summarize(stage_a, grid)

    def chain_seed_choice(self, stage_a, family, quantity):
        floor = self.context["floor"]
        candidates = sorted(
            (r for r in stage_a if r["family"] == family), key=lambda r: r["chi2_search"]
        )
        chosen = []
        for r in candidates:
            q = r["search_at_prediction"].get(quantity)
            if q is None or not (math.isfinite(q) and q > 0):
                continue
            if r["chi2_search"] - floor > self.budget.chain_excess and chosen:
                break
            if all(
                abs(math.log(q) - math.log(c["search_at_prediction"][quantity]))
                > self.budget.distinct_ln
                for c in chosen
            ):
                chosen.append(r)
            if len(chosen) == self.budget.chains:
                break
        return chosen

    def profile_solves(self, family, quantity, q, stages):
        return [
            r
            for r in self.records
            if r.get("stage") in stages
            and r["family"] == family
            and r["quantity"] == quantity
            and r["target"] == q
            and r["ln_offset"] is not None
            and abs(r["ln_offset"]) <= self.budget.repair_ln
        ]

    def best_search(self, family, quantity, q):
        solves = self.profile_solves(family, quantity, q, ("B-chain",))
        return min(solves, key=lambda r: r["chi2_search"]) if solves else None

    def best_exact(self, family, quantity, q, stages):
        solves = [
            r
            for r in self.profile_solves(family, quantity, q, stages)
            if self.exact.get(r["ref"], {}).get("in_domain")
        ]
        return min(solves, key=lambda r: self.exact[r["ref"]]["chi2"]) if solves else None

    # ------------------------------------------------------------ the summary

    def summarize(self, stage_a, grid):
        log("summary")
        margins = self.declaration["compatibility"]["margins"]
        pred = self.pred_mV
        evaluated = [
            {
                "ref": r["ref"],
                "family": r["family"],
                "stage": r.get("stage", "A"),
                "z": r["z"],
                **self.exact[r["ref"]],
            }
            for r in self.records
            if r.get("kind") != "kinetics" and r.get("ref") in self.exact
        ]
        families = {}
        for family in ("free", "slice"):
            sets = [e for e in evaluated if e["family"] == family and e["in_domain"]]
            usable = [e for e in sets if e["compatible_base"]]
            predicted = [e for e in usable if not e["degenerate"][str(pred)]]

            def passes(e, observable, polarities=(-pred, pred)):
                return all(e["lines"][f"{v:+d} {observable}"]["passes"] for v in polarities)

            def least(selection):
                return min(selection, key=lambda s: s["excess"]) if selection else None

            deciding = least([e for e in predicted if passes(e, "tau_slow")])
            context_numbers = {
                "tau_slow_passes_minus": least(
                    [e for e in predicted if passes(e, "tau_slow", (-pred,))]
                ),
                "tau_slow_passes_plus": least(
                    [e for e in predicted if passes(e, "tau_slow", (pred,))]
                ),
                "tau_fast_passes_both": least([e for e in predicted if passes(e, "tau_fast")]),
                "G_ss_passes_both": least([e for e in predicted if passes(e, STEADY)]),
                "least_excess_overall": least(usable),
            }
            per_margin = {}
            for m in margins:
                compatible = [e for e in usable if e["excess"] <= m]
                inside = [e for e in compatible if not e["degenerate"][str(pred)]]
                entry = {
                    "compatible_sets": len(compatible),
                    "degenerate_at_prediction": len(compatible) - len(inside),
                }
                for observable in TIMES:
                    if not inside:
                        entry[observable] = None
                        continue
                    lo = min(inside, key=lambda e: e["at_prediction"][observable])
                    hi = max(inside, key=lambda e: e["at_prediction"][observable])
                    entry[observable] = {
                        "min": lo["at_prediction"][observable],
                        "max": hi["at_prediction"][observable],
                        "min_ref": lo["ref"],
                        "max_ref": hi["ref"],
                        "min_lines": {k: lo["lines"][k] for k in lo["lines"] if observable in k},
                        "max_lines": {k: hi["lines"][k] for k in hi["lines"] if observable in k},
                        "any_passes_both": any(passes(e, observable) for e in inside),
                        "any_passes_minus": any(passes(e, observable, (-pred,)) for e in inside),
                        "any_passes_plus": any(passes(e, observable, (pred,)) for e in inside),
                    }
                if deciding is not None:
                    entry["tau_slow_reaches_both_windows"] = deciding["excess"] <= m
                else:
                    entry["tau_slow_reaches_both_windows"] = False
                per_margin[str(m)] = entry
            families[family] = {
                "evaluated_sets": len(sets),
                "usable_sets": len(usable),
                "deciding": self.brief(deciding),
                "context": {k: self.brief(v) for k, v in context_numbers.items()},
                "per_margin": per_margin,
            }
        meanings = self.declaration["reported"]["meanings_fixed_by_the_lead"]
        reading = {}
        for m in margins:
            reached = families["free"]["per_margin"][str(m)]["tau_slow_reaches_both_windows"]
            reading[str(m)] = {
                "reached": reached,
                "meaning": meanings["reached" if reached else "not_reached"],
            }
        profiles = {}
        for family, quantity in PROFILES:
            curve = []
            for q in grid[quantity]:
                best = self.best_exact(
                    family, quantity, q, stages=("B-chain", "B-repair", "C-polish")
                )
                if best is None:
                    curve.append({"target": q, "found": False})
                    continue
                e = self.exact[best["ref"]]
                curve.append(
                    {
                        "target": q,
                        "found": True,
                        "ref": best["ref"],
                        "stage": best["stage"],
                        "excess": e["excess"],
                        "compatible_base": e["compatible_base"],
                        "degenerate": e["degenerate"],
                        "at_prediction": e["at_prediction"],
                        "passes": {k: v["passes"] for k, v in e["lines"].items()},
                        "parameters": to_params(best["z"], family).to_json(),
                    }
                )
            profiles[f"{family} {quantity}"] = curve
        witnesses = {}
        for family in ("free", "slice"):
            d = families[family]["deciding"]
            if d is not None:
                witnesses[family] = self.witness(d["ref"], family)
        feasible = [k for k in self.kinetics if k["verified"]["feasible"]]
        best_kinetics = min(
            (k for k in self.kinetics if k["verified"].get("max_abs_u") is not None),
            key=lambda k: k["verified"]["max_abs_u"],
            default=None,
        )
        proof = min(feasible, key=lambda k: k["verified"]["max_abs_u"]) if feasible else None
        kinetics = {
            "label": "kinetics alone: every tau window at all six voltages, no G_ss and no amplitude ratio",
            "solves": len(self.kinetics),
            "feasible_solutions": len(feasible),
            "feasible": bool(feasible),
            "proof": self.kinetics_brief(proof),
            "best_max_abs_u": self.kinetics_brief(best_kinetics),
        }
        statuses = Counter(
            (r.get("stage", "A" if r.get("kind") == "minimize" else r.get("kind")), r.get("status"))
            for r in self.records
        )
        search = {
            "starts": {
                f: len(
                    all_starts(self.context["rows"], self.docs["fit_report_json"], f, self.budget)
                )
                for f in ("free", "slice")
            },
            "chain_seeds": self.chain_seeds,
            "solves_by_stage_and_status": {
                f"{k[0]} status {k[1]}": n for k, n in sorted(statuses.items(), key=str)
            },
            "evaluations": int(sum(r.get("nfev", 0) for r in self.records)),
            "exact_evaluated_sets": len(self.exact),
            "stage_seconds": self.seconds,
            "errors": self.errors,
            "stage_A": [
                {
                    k: r[k]
                    for k in (
                        "id",
                        "family",
                        "start",
                        "chi2_search",
                        "status",
                        "nfev",
                        "seconds",
                        "ref",
                    )
                }
                | {
                    "excess_exact": self.exact.get(r["ref"], {}).get("excess"),
                    "at_prediction_exact": self.exact.get(r["ref"], {}).get("at_prediction"),
                }
                for r in stage_a
            ],
        }
        doc = {
            "kind": "fr30-revilla1999-diagnostic-d2@1",
            "label": self.declaration["label"],
            "smoke": self.smoke,
            "predicted_magnitude_mV": pred,
            "began_utc": self.began,
            "ended_utc": utc(),
            "declaration": {"path": str(DECLARATION), "sha256": sha256(DECLARATION)},
            "inputs": self.inputs,
            "provenance": provenance(),
            "module_root": str(Path(__file__).resolve().parents[2]),
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "budget": asdict(self.budget),
            "floor": self.context["floor"],
            "margins": margins,
            "reading_of_the_lead_meanings": reading,
            "families": families,
            "kinetics_alone": kinetics,
            "witnesses": witnesses,
            "profiles": profiles,
            "search": search,
        }
        (self.out / "results.json").write_text(json.dumps(jsonable(doc), indent=1) + "\n")
        self.print_summary(doc)
        return 0 if not self.errors else 4

    def brief(self, e):
        if e is None:
            return None
        return {
            "ref": e["ref"],
            "family": e["family"],
            "stage": e["stage"],
            "excess": e["excess"],
            "chi2": e["chi2"],
            "at_prediction": e["at_prediction"],
            "lines": e["lines"],
            "degenerate": e["degenerate"],
            "parameters": to_params(e["z"], e["family"]).to_json(),
        }

    def kinetics_brief(self, k):
        if k is None:
            return None
        return {
            "ref": k["ref"],
            "start": k["start"],
            "status": k["status"],
            "hinge_cost": k["hinge_cost"],
            "parameters": to_params(k["z"], "free").to_json(),
            "verified": k["verified"],
        }

    def witness(self, ref, family):
        """The tagged chain end to end: predictions_document (predict and readout at the held-out
        voltages) scored by the tagged scorer against the held-out file."""
        z = next(r["z"] for r in self.records if r.get("ref") == ref)
        params = to_params(z, family)
        voltages = (-self.pred_mV, self.pred_mV)
        doc = harness.predictions_document(params, voltages)
        held = self.docs["fit_json"] if self.smoke else self.docs["held_out_json"]
        scored = scorer.score(doc, held, voltages)
        return {
            "ref": ref,
            "parameters": params.to_json(),
            "predictions": doc["predictions"],
            "score": {k: scored[k] for k in ("verdict", "passed", "compared", "comparisons")},
        }

    def print_summary(self, doc):
        pred = doc["predicted_magnitude_mV"]
        for family, f in doc["families"].items():
            d = f["deciding"]
            log(
                f"{family}: {f['usable_sets']} usable sets; least excess with tau_slow({pred}) passing both: "
                + (
                    "none found"
                    if d is None
                    else f"{d['excess']:.4f} (tau_slow {d['at_prediction']['tau_slow']:.3f} s, {d['ref']})"
                )
            )
            for m, entry in f["per_margin"].items():
                parts = [f"margin {m}: {entry['compatible_sets']} compatible"]
                for o in TIMES:
                    r = entry[o]
                    parts.append(
                        f"{o} "
                        + (
                            "none"
                            if r is None
                            else f"[{r['min']:.3f}, {r['max']:.3f}] s, both {r['any_passes_both']}"
                        )
                    )
                log("  " + "; ".join(parts))
        k = doc["kinetics_alone"]
        log(
            f"kinetics alone: feasible {k['feasible']} ({k['feasible_solutions']} of {k['solves']} solves)"
        )
        for m, r in doc["reading_of_the_lead_meanings"].items():
            log(f"margin {m}: {'reached' if r['reached'] else 'not reached'}")


MODULE = None


def search(out, workers, smoke):
    global MODULE
    from validation.junction_gate_benchmark import (
        revilla1999_diagnostic as module,
    )  # the workers' unit by name

    MODULE = module
    run = Run(out, workers, smoke)
    run.began = utc()
    return run.go()


# ---------------------------------------------------------------- the identity stage


def identity(out, predicted):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    declaration, docs, inputs = load()
    record = {
        "kind": "fr30-revilla1999-diagnostic-identity@1",
        "utc": utc(),
        "provenance": provenance(),
        "inputs": inputs,
    }
    ok = True

    # (a) the tagged predict stage's fresh output against predictions.json.
    recorded_path = Path(inputs["predictions_json"]["path"])
    recorded_text, fresh_text = recorded_path.read_text(), Path(predicted).read_text()
    recorded, fresh = json.loads(recorded_text), json.loads(fresh_text)
    substituted, replaced = fresh_text, []
    for path, new, old in (
        ("utc", fresh.get("utc"), recorded.get("utc")),
        (
            "provenance.root",
            fresh.get("provenance", {}).get("root"),
            recorded.get("provenance", {}).get("root"),
        ),
    ):
        if new != old:
            needle = json.dumps(new)
            if substituted.count(needle) != 1:
                raise SystemExit(f"identity: {path}'s value is not unique in the fresh output")
            substituted = substituted.replace(needle, json.dumps(old))
            replaced.append(path)
    digest = hashlib.sha256(substituted.encode()).hexdigest()
    same = digest == inputs["predictions_json"]["sha256"]
    diff = (
        []
        if same
        else list(
            difflib.unified_diff(
                recorded_text.splitlines(), substituted.splitlines(), lineterm="", n=0
            )
        )[:80]
    )
    record["predict"] = {
        "fresh": {"path": str(Path(predicted).resolve()), "sha256": sha256(predicted)},
        "replaced": replaced,
        "sha256_after_replacement": digest,
        "identical_apart_from_replaced": same,
        "diff": diff,
    }
    ok &= same

    # (b) the objective at the judged parameters, with the exact readout.
    params = harness.LawParameters.from_json(docs["params_json"])
    rows, sem_floor = training(docs["fit_json"])
    reads = readings(params, 1, TRAINING_MAGNITUDES, TRAINING_READOUTS)
    residuals = train_residuals(reads, rows)
    chi2 = float(residuals @ residuals)
    report = docs["fit_report_json"]
    recorded_rows = {
        (r["vj_mV"], r["observable"]): r["weighted_residual"] for r in report["training_residuals"]
    }
    rows_out = []
    for row, value in zip(rows, residuals, strict=True):
        expected = recorded_rows[(row["vj_mV"], row["observable"])]
        agree = math.isclose(value, expected, rel_tol=IDENTITY_RTOL, abs_tol=IDENTITY_ATOL)
        rows_out.append(
            {
                "vj_mV": row["vj_mV"],
                "observable": row["observable"],
                "residual": float(value),
                "recorded": expected,
                "agree": agree,
            }
        )
    expected_chi2 = report["selected"]["chi2"]
    chi2_agree = math.isclose(chi2, expected_chi2, rel_tol=IDENTITY_RTOL)
    surrogate = train_residuals(
        readings(params, SURROGATE_EVERY, TRAINING_MAGNITUDES, TRAINING_READOUTS), rows
    )
    record["objective"] = {
        "chi2": chi2,
        "recorded_chi2": expected_chi2,
        "agree": chi2_agree and all(r["agree"] for r in rows_out),
        "rows": rows_out,
        "rows_count": len(rows_out),
        "steady_sem_floor": sem_floor,
        "surrogate_chi2_at_the_same_parameters": float(surrogate @ surrogate),
        "excess_over_floor": chi2 - float(declaration["objective"]["floor"]),
    }
    ok &= record["objective"]["agree"]

    # (c) one u = A(|V| - V0) per gate sets both the steady target and the relaxation rate.
    checks = []
    for entry in docs["predictions_json"]["predictions"]:
        v = 1e-3 * entry["vj_mV"]
        law = series.kinetics(v, params.gates, kinds=KINDS, xp=np)
        at_hold = series.kinetics(0.0, params.gates, kinds=KINDS, xp=np)
        for gate_params, recorded_gate, rates, hold in zip(
            params.gates, entry["gates"], law, at_hold, strict=True
        ):
            lam, slope, midpoint, split, residual = gate_params
            u = slope * (abs(v) - midpoint)
            relaxation = lam * math.exp(-split * u) + lam * math.exp((1.0 - split) * u)
            target = residual + (1.0 - residual) / (1.0 + math.exp(u))
            u0 = slope * (0.0 - midpoint)
            c_hold = residual + (1.0 - residual) / (1.0 + math.exp(u0))
            pairs = {
                "relaxation_per_s": (
                    relaxation,
                    recorded_gate["relaxation_per_s"],
                    float(rates.relaxation_per_s),
                ),
                "target": (target, recorded_gate["target"], float(rates.target)),
                "c_hold": (c_hold, recorded_gate["c_hold"], float(hold.target)),
            }
            agree = all(
                math.isclose(a, b, rel_tol=GATE_RTOL) and math.isclose(a, c, rel_tol=GATE_RTOL)
                for a, b, c in pairs.values()
            )
            checks.append(
                {
                    "vj_mV": entry["vj_mV"],
                    "gate": recorded_gate["gate"],
                    "u": u,
                    "values": pairs,
                    "agree": agree,
                }
            )
    record["shared_slope_and_midpoint"] = {
        "code": "cells.laws.junctions.junction_series_gates.boltzmann_eyring_kinetics computes u = slope * (|V| - midpoint) once; alpha = rate exp(-split u) and beta = rate exp((1 - split) u) give the relaxation rate alpha + beta that sets the times, and the steady open fraction 1/(1 + exp(u)) gives the steady target residual + (1 - residual)/(1 + exp(u)). The registered G_ss/G_0 is the 30 s end-of-step value over the 0 mV steady conductance, so it also depends on the rate and split wherever a gate has not relaxed by 30 s.",
        "checks": checks,
        "agree": all(c["agree"] for c in checks),
    }
    ok &= record["shared_slope_and_midpoint"]["agree"]
    record["pass"] = bool(ok)
    (out / "identity.json").write_text(json.dumps(jsonable(record), indent=1) + "\n")
    print(f"predict: identical apart from {replaced or 'nothing'}: {same}")
    print(
        f"objective: chi2 {chi2!r} against {expected_chi2!r}; all 17 residuals agree: {record['objective']['agree']}"
    )
    print(
        f"shared slope and midpoint: {record['shared_slope_and_midpoint']['agree']} ({len(checks)} gate checks)"
    )
    print(f"identity: {'pass' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    i = stages.add_parser("identity")
    i.add_argument("out")
    i.add_argument("--predicted", required=True)
    s = stages.add_parser("search")
    s.add_argument("out")
    s.add_argument("--workers", type=int, default=4)
    m = stages.add_parser("smoke")
    m.add_argument("out")
    m.add_argument("--workers", type=int, default=2)
    args = parser.parse_args(argv)
    if args.stage == "identity":
        return identity(args.out, args.predicted)
    return search(args.out, args.workers, smoke=args.stage == "smoke")


if __name__ == "__main__":
    sys.exit(main())
