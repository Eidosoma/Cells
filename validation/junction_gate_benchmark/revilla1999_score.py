"""FR-30's benchmark on Revilla, Castro and Barrio (1999): the held-out file's reader and the scorer
(docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.5; D311, D308).

Standard library only. The scorer never imports the engine, so no verdict depends on the law's code.
validation/junction_gate_benchmark/revilla1999.py makes the predictions, and its `verify` stage
recomputes them from their one stated parameter block before a judged score.

**The reader** (`resolve`) was written from the extractor's fit.json, the registration's train.json;
the held-out file itself was never opened by its author. It reads every entry under "observables"
and matches each by its (vj_mV, maps_to_registered_observable) pair; an entry without that mapping
is skipped (fit.json's amplitude ratio). It needs exactly one entry per held-out voltage and judged
observable, and it fails closed: a missing or duplicated entry, a missing key, a value that is not a
finite number, a sign against its polarity, unknown units or a dispersion other than an SEM is
refused, and a refusal names key paths only, never a value.

**Reader erratum 1** (§13.6). The extractor built the two files' entries the same way, but not
their containers. fit.json's "observables" is an object of named lists of entries (paths
observables.NAME[i]); held_out.json's is one flat list of entries (paths observables[i]). The reader
takes either, and every entry goes through the same checks. The erratum was written from the two
files' keys and shapes only, never their values; it changes no tolerance, rule or pass logic.

**The comparisons** (§13.5, from section 13's rule 4 with D311):
- a time passes if |ln(pred/obs)| <= ln 1.25 or |pred - obs| <= 2 SEM. Both outcomes are recorded,
  and the tolerance that applied: the wider band edge on the prediction's side (the ln band is
  asymmetric, -20% and +25%);
- G_ss/G_0 passes if |pred - obs| <= max(0.05, 2 SEM), with the one that applied;
- no SEM (dispersion null) leaves the base tolerance alone (section 13.1, point 4);
- a degenerate fit fails both time comparisons at its voltage, with its reasons, and its G_ss is
  still judged;
- the amplitudes are not judged (section 13.2); the digitising error is reported and widens nothing.

**The verdict:** cannot_predict if the law leaves its domain at a held-out voltage; otherwise pass
only if every comparison passes (two held-out voltages, so "more than half" means both: D311);
otherwise fail.

Stages (run from the checkout's root):
    python -m validation.junction_gate_benchmark.revilla1999_score resolve FILE [--voltages MV ...]
        resolve every judged entry and print key paths only, never a value
    python -m validation.junction_gate_benchmark.revilla1999_score score PREDICTIONS HELD_OUT OUT
            [--expect-sha256 HEX]
        the verdict, written to OUT with every value; stdout carries verdicts and key paths only
"""

import argparse
import hashlib
import json
import math
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

RULE = "docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.5"
LAW_ID = "junction_series_gates@1"
PREDICTIONS_SCHEMA = "fr30-revilla1999-predictions@1"
VERDICT_SCHEMA = "fr30-revilla1999-verdict@1"
HELD_OUT_MV = (-80, 80)  # Section 13's rule 1 on fit.json's split; two voltages (D311).
TIMES = ("tau_fast", "tau_slow")
STEADY = "G_ss/G_0"
JUDGED = TIMES + (STEADY,)
PREDICTED_KEY = {"tau_fast": "tau_fast_s", "tau_slow": "tau_slow_s", STEADY: "G_ss_over_G0"}
TIME_RATIO = 1.25  # |ln(pred/obs)| <= ln 1.25
STEADY_TOLERANCE = 0.05  # |pred - obs| <= 0.05 of G_0
SEM_FACTOR = 2.0  # 2 SEM replaces a tolerance where it is wider
TIME_UNITS = {"s": 1.0, "ms": 1e-3}
STEADY_UNITS = ("G/G(10-mV prepulse)",)  # fit.json's: the paper normalizes to the 10-mV prepulse
SEM_PREFIX = "SEM"
MAPPING = "maps_to_registered_observable"
NOT_JUDGED = {
    "A_fast": "not reported per voltage (section 13.2); the prediction's is reported only",
    "A_slow": "not reported per voltage (section 13.2); the prediction's is reported only",
}
STATUSES = ("predicted", "cannot_predict")


class Refusal(ValueError):
    """The reader's refusal: its message names key paths only, never a value."""


def _mv(v):
    return f"{v:+g} mV"


def number(obj, key, where, *, positive=False, nonnegative=False):
    """obj[key] as a float, refusing by key path alone: absent, not a finite number, or of the wrong
    sign. Nothing is converted from text, so no value can reach a message."""
    if not isinstance(obj, dict) or key not in obj:
        raise Refusal(f"{where}: no key '{key}'")
    x = obj[key]
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        raise Refusal(f"{where}.{key}: not a finite number")
    if positive and not x > 0:
        raise Refusal(f"{where}.{key}: not positive")
    if nonnegative and not x >= 0:
        raise Refusal(f"{where}.{key}: negative")
    return float(x)


def _reported(obj, key, scale):
    """A reported-only number (the digitising error): scaled, or None. Never refuses."""
    x = obj.get(key) if isinstance(obj, dict) else None
    if isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x):
        return None
    return float(x) * scale


def _entry(entry, where, observable):
    """One judged entry's value, SEM and reported digitising error, in seconds or in G/G_0."""
    units = entry.get("units")
    if observable in TIMES:
        scale = TIME_UNITS.get(units) if isinstance(units, str) else None
    else:
        scale = 1.0 if units in STEADY_UNITS else None
    if scale is None:
        raise Refusal(f"{where}.units: absent or not one of the known units")
    value = number(entry, "value", where, positive=observable in TIMES) * scale
    if "dispersion" not in entry:
        raise Refusal(f"{where}: no key 'dispersion'")
    dispersion = entry["dispersion"]
    if dispersion is None:
        sem, note = None, "no dispersion reported: the base tolerance alone (section 13.1, point 4)"
    elif isinstance(dispersion, dict):
        kind = dispersion.get("type")
        if not isinstance(kind, str) or not kind.startswith(SEM_PREFIX):
            raise Refusal(f"{where}.dispersion.type: absent or not an SEM (an SD is the lead's)")
        if dispersion.get("units") != units:
            raise Refusal(f"{where}.dispersion.units: absent or not the entry's units")
        sem = number(dispersion, "value", f"{where}.dispersion", nonnegative=True) * scale
        note = "the entry's SEM"
    else:
        raise Refusal(f"{where}.dispersion: neither null nor an object")
    return {
        "path": where,
        "value": value,
        "sem": sem,
        "sem_note": note,
        "digitizing_error": _reported(entry, "digitizing_error", scale),
        "digitizing_error_ln": _reported(entry, "digitizing_error_ln", 1.0)
        if observable in TIMES
        else None,
    }


def _entry_lists(doc):
    """The lists of entries under "observables", each with its key path's stem (reader erratum 1,
    §13.6): fit.json's object of named lists, in name order, or held_out.json's one flat list."""
    if not isinstance(doc, dict):
        raise Refusal("the top level is not an object")
    if "observables" not in doc:
        keys = sorted(str(k) for k in doc)
        raise Refusal(f"no 'observables' key at the top level (top-level keys: {keys})")
    groups = doc["observables"]
    if isinstance(groups, list):
        return [("observables", groups)]
    if isinstance(groups, dict):
        return [(f"observables.{name}", groups[name]) for name in sorted(groups, key=str)]
    raise Refusal("observables: present, but neither an object of lists nor a list of entries")


def resolve(doc, voltages=HELD_OUT_MV, observables=JUDGED):
    """Every judged entry of a held-out file (or of fit.json) at the given voltages, by key.

    "observables" is an object of named lists of entries (fit.json's) or one flat list of entries
    (held_out.json's; reader erratum 1, §13.6), and every entry is read the same way. Returns
    {"entries": {(vj_mV, observable): {...}}, "skipped": [path], "outside": [path]}: the skipped
    entries carry no judged mapping, the outside ones lie at other voltages. It refuses (Refusal),
    naming key paths only, anything it cannot resolve."""
    voltages, observables = tuple(voltages), tuple(observables)
    found, skipped, outside = {}, [], []
    for stem, group in _entry_lists(doc):
        if not isinstance(group, list):
            raise Refusal(f"{stem}: not a list")
        for i, entry in enumerate(group):
            where = f"{stem}[{i}]"
            if not isinstance(entry, dict):
                raise Refusal(f"{where}: not an object")
            mapped = entry.get(MAPPING)
            if not isinstance(mapped, str) or mapped not in observables:
                skipped.append(where)
                continue
            vj = number(entry, "vj_mV", where)
            if vj not in voltages:
                outside.append(where)
                continue
            if "polarity" in entry and entry["polarity"] != ("-" if vj < 0 else "+"):
                raise Refusal(f"{where}.polarity: absent from ('+', '-') or against vj_mV's sign")
            key = (voltages[voltages.index(vj)], mapped)
            if key in found:
                raise Refusal(
                    f"{found[key]['path']} and {where}: two entries for {mapped} at {_mv(vj)}"
                )
            found[key] = _entry(entry, where, mapped)
    missing = [f"{o} at {_mv(v)}" for v in voltages for o in observables if (v, o) not in found]
    if missing:
        raise Refusal(
            f"no entry for {', '.join(missing)} (entries skipped for want of a judged "
            f"'{MAPPING}': {skipped}; entries at other voltages: {outside})"
        )
    return {"entries": found, "skipped": skipped, "outside": outside}


def read_predictions(doc, voltages=HELD_OUT_MV):
    """predictions.json's entries at the held-out voltages, by key; refuses what does not resolve.

    One block of kinds and parameters serves every voltage (§13.5: both gate kinds read |V_j|), so
    an entry that carries its own is refused."""
    if not isinstance(doc, dict):
        raise Refusal("predictions: not an object")
    if doc.get("schema") != PREDICTIONS_SCHEMA:
        raise Refusal("predictions.schema: absent or not " + PREDICTIONS_SCHEMA)
    if doc.get("law") != LAW_ID:
        raise Refusal("predictions.law: absent or not " + LAW_ID)
    kinds, parameters = doc.get("kinds"), doc.get("parameters")
    if not (isinstance(kinds, list) and len(kinds) == 2 and all(isinstance(k, str) for k in kinds)):
        raise Refusal("predictions.kinds: not a list of the two gates' kinds")
    if not (isinstance(parameters, list) and len(parameters) == 2):
        raise Refusal("predictions.parameters: not one block of the two gates' parameters")
    entries = doc.get("predictions")
    if not isinstance(entries, list):
        raise Refusal("predictions.predictions: not a list")
    found = {}
    for i, entry in enumerate(entries):
        where = f"predictions[{i}]"
        if not isinstance(entry, dict):
            raise Refusal(f"{where}: not an object")
        if "kinds" in entry or "parameters" in entry:
            raise Refusal(f"{where}: carries its own kinds or parameters (one block serves all)")
        vj = number(entry, "vj_mV", where)
        if vj not in voltages:
            continue
        v = voltages[voltages.index(vj)]
        if v in found:
            raise Refusal(f"{where}: a second prediction at {_mv(v)}")
        status = entry.get("status")
        if status not in STATUSES:
            raise Refusal(f"{where}.status: absent or not one of {STATUSES}")
        record = {"path": where, "status": status}
        if status == "predicted":
            degenerate, reasons = entry.get("degenerate"), entry.get("degenerate_reasons")
            if not isinstance(degenerate, bool):
                raise Refusal(f"{where}.degenerate: absent or not a boolean")
            if not (isinstance(reasons, list) and all(isinstance(r, str) for r in reasons)):
                raise Refusal(f"{where}.degenerate_reasons: absent or not a list of strings")
            if degenerate != bool(reasons):
                raise Refusal(f"{where}: degenerate and degenerate_reasons disagree")
            record["degenerate_reasons"] = list(reasons)
            record[STEADY] = number(entry, PREDICTED_KEY[STEADY], where)
            for observable in TIMES:
                key = PREDICTED_KEY[observable]
                if degenerate:  # Reported as fitted where finite; never judged.
                    x = entry.get(key)
                    finite = isinstance(x, (int, float)) and not isinstance(x, bool)
                    record[observable] = float(x) if finite and math.isfinite(x) else None
                else:
                    record[observable] = number(entry, key, where, positive=True)
            for key in ("A_fast", "A_slow", "C"):
                record[key] = _reported(entry, key, 1.0)
        found[v] = record
    missing = [_mv(v) for v in voltages if v not in found]
    if missing:
        raise Refusal(f"predictions: no entry at {', '.join(missing)}")
    return found


def compare_time(predicted, observed, sem, degenerate_reasons=()):
    """One time comparison: |ln(pred/obs)| <= ln 1.25 or |pred - obs| <= 2 SEM, both recorded."""
    ln_tolerance = math.log(TIME_RATIO)
    sem_tolerance = None if sem is None else SEM_FACTOR * sem
    record = {
        "predicted": predicted,
        "observed": observed,
        "units": "s",
        "sem": sem,
        "ln_tolerance": ln_tolerance,
        "sem_tolerance": sem_tolerance,
    }
    if degenerate_reasons:
        reason = "degenerate fit: " + "; ".join(degenerate_reasons)
        return {
            **record,
            "within_ln": None,
            "within_sem": None,
            "applied": None,
            "passes": False,
            "reason": reason,
        }
    ln_ratio = math.log(predicted / observed)
    within_ln = abs(ln_ratio) <= ln_tolerance
    within_sem = None if sem is None else abs(predicted - observed) <= sem_tolerance
    above = predicted >= observed
    ln_edge = observed * TIME_RATIO if above else observed / TIME_RATIO
    if sem is None:
        sem_edge, applied = None, "ln 1.25"
    else:
        sem_edge = observed + sem_tolerance if above else observed - sem_tolerance
        wider = sem_edge > ln_edge if above else sem_edge < ln_edge
        applied = "2 SEM" if wider else "ln 1.25"
    passes = within_ln or bool(within_sem)
    return {
        **record,
        "ln_ratio": ln_ratio,
        "abs_difference": abs(predicted - observed),
        "side": "above" if above else "below",
        "ln_edge": ln_edge,
        "sem_edge": sem_edge,
        "within_ln": within_ln,
        "within_sem": within_sem,
        "applied": applied,
        "passes": passes,
        "reason": None if passes else f"outside both tolerances (the wider, {applied}, applied)",
    }


def compare_steady(predicted, observed, sem):
    """G_ss/G_0: |pred - obs| <= max(0.05, 2 SEM), the one that applied recorded."""
    sem_tolerance = None if sem is None else SEM_FACTOR * sem
    wider = sem_tolerance is not None and sem_tolerance > STEADY_TOLERANCE
    tolerance = sem_tolerance if wider else STEADY_TOLERANCE
    difference = abs(predicted - observed)
    passes = difference <= tolerance
    return {
        "predicted": predicted,
        "observed": observed,
        "units": "G/G_0",
        "sem": sem,
        "abs_difference": difference,
        "tolerance": tolerance,
        "applied": "2 SEM" if wider else "0.05",
        "passes": passes,
        "reason": None if passes else f"outside {'2 SEM' if wider else '0.05'}",
    }


def score(predictions, held_out, voltages=HELD_OUT_MV):
    """Section 13's rule 4 with D311 (§13.5): every comparison at every held-out voltage, the
    tolerance each used, and the verdict. Both documents are resolved, by key, before any value is
    compared."""
    voltages = tuple(voltages)
    predicted = read_predictions(predictions, voltages)
    observed = resolve(held_out, voltages)
    comparisons = []
    for v in voltages:
        p = predicted[v]
        for observable in JUDGED:
            o = observed["entries"][(v, observable)]
            head = {"vj_mV": v, "observable": observable, "held_out_path": o["path"]}
            reported = {
                "sem_note": o["sem_note"],
                "digitizing_error": o["digitizing_error"],
                "digitizing_error_ln": o["digitizing_error_ln"],
            }
            if p["status"] == "cannot_predict":
                comparisons.append(
                    {
                        **head,
                        "observed": o["value"],
                        "passes": False,
                        "reason": "cannot predict: the law leaves its domain",
                    }
                )
            elif observable in TIMES:
                c = compare_time(p[observable], o["value"], o["sem"], p["degenerate_reasons"])
                comparisons.append({**head, **c, **reported})
            else:
                comparisons.append(
                    {**head, **compare_steady(p[observable], o["value"], o["sem"]), **reported}
                )
    cannot = [v for v in voltages if predicted[v]["status"] == "cannot_predict"]
    if cannot:
        verdict = "cannot_predict"
    else:
        verdict = "pass" if all(c["passes"] for c in comparisons) else "fail"
    amplitudes = {
        _mv(v): {k: predicted[v].get(k) for k in ("A_fast", "A_slow", "C")} for v in voltages
    }
    return {
        "schema": VERDICT_SCHEMA,
        "rule": RULE,
        "verdict": verdict,
        "held_out_mV": list(voltages),
        "cannot_predict_mV": cannot,
        "comparisons": comparisons,
        "passed": sum(c["passes"] for c in comparisons),
        "compared": len(comparisons),
        "not_judged": NOT_JUDGED,
        "predicted_amplitudes_reported_only": amplitudes,
        "held_out_entries_skipped": observed["skipped"],
        "held_out_entries_at_other_voltages": observed["outside"],
        "tolerances": {
            "time_ratio": TIME_RATIO,
            "steady": STEADY_TOLERANCE,
            "sem_factor": SEM_FACTOR,
        },
    }


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    r = stages.add_parser("resolve", help="resolve every judged entry; print key paths only")
    r.add_argument("file")
    r.add_argument("--voltages", type=float, nargs="+", default=list(HELD_OUT_MV))
    s = stages.add_parser("score", help="the verdict, written to OUT")
    s.add_argument("predictions")
    s.add_argument("held_out")
    s.add_argument("out")
    s.add_argument("--expect-sha256", help="the held-out file's registered digest (D311)")
    args = parser.parse_args(argv)
    try:
        if args.stage == "resolve":
            voltages = tuple(args.voltages)
            resolved = resolve(json.loads(Path(args.file).read_text()), voltages)
            for (v, observable), entry in sorted(resolved["entries"].items()):
                print(f"{_mv(v)} {observable}: {entry['path']}")
            print(f"skipped (no judged mapping): {resolved['skipped']}")
            print(f"at other voltages: {resolved['outside']}")
            print(f"resolved {len(resolved['entries'])} entries; no value printed")
            return 0
        digest = _sha256(args.held_out)
        if args.expect_sha256 and digest != args.expect_sha256.lower():
            raise Refusal(f"the held-out file's sha256 is {digest}, not the registered one")
        result = score(
            json.loads(Path(args.predictions).read_text()),
            json.loads(Path(args.held_out).read_text()),
        )
        result["files"] = {
            "predictions": {
                "path": str(Path(args.predictions).resolve()),
                "sha256": _sha256(args.predictions),
            },
            "held_out": {
                "path": str(Path(args.held_out).resolve()),
                "sha256": digest,
                "expected_sha256": args.expect_sha256,
            },
        }
        result["utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
        for c in result["comparisons"]:
            mark = "pass" if c["passes"] else "FAIL"
            why = f" ({c['reason']})" if c.get("reason") else ""
            print(f"{_mv(c['vj_mV'])} {c['observable']}: {mark}, applied {c.get('applied')}{why}")
        print(
            f"verdict: {result['verdict']} ({result['passed']} of {result['compared']} pass); "
            f"values in {args.out}"
        )
        return 0
    except Refusal as err:
        print(f"REFUSED: {err}", file=sys.stderr)
        return 2
    except Exception as err:  # Its text could carry a held-out value, so only its type and frames.
        frames = [
            f"{f.filename}:{f.lineno} in {f.name}" for f in traceback.extract_tb(err.__traceback__)
        ]
        print(
            f"ERROR: {type(err).__name__}, its message withheld\n  " + "\n  ".join(frames),
            file=sys.stderr,
        )
        return 3


if __name__ == "__main__":
    sys.exit(main())
