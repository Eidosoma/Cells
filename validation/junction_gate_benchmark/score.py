"""FR-30's junction-gate benchmarks: the observation files' reader, its value-free check, and the
scorer (docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.7; D334, D308).

Standard library only, so no verdict depends on the engine's code. `harness.py` beside this module
makes the predictions, and its `verify` stage recomputes them from their one stated parameter block
before a judged score.

**The layout** (§13.7 part 8.2).
- fit.json and held_out.json share one container: a "convention" block, a "split" block, and one
  flat list of entries under "observables" (§13.6's lesson: one container for both files).
- protocol.json carries the same convention block and the protocol's fields, each with its status.
- The reader fails closed, and every refusal names key paths only, never a value (K1 to K7).

**The split** (§13.7 part 3) is recomputed from the two files' own entries: S0's classes, then the
rank rule on the decay list and on the steady list. Any mismatch with the declared split is refused
(K4), and so is any training entry at a held-out magnitude (K5).

**The comparisons** (part 5).
- A time passes within ln 1.25 or 2 SEM.
- An amplitude passes within max(0.10, 2 SEM).
- G_ss/G_0 passes within max(0.05, 2 SEM).
- An SD becomes an SEM only where the paper states n and what n counts (D334). No other dispersion
  widens a tolerance.

**The one-cell rule** (D334).
- **Why.** Under every protocol type but "symmetric", the two polarities of a magnitude differ in
  the cells' membrane potentials as well as in V_j's sign. A law of V_j alone cannot separate the
  two: the comparison is not identifiable.
- **The rule.** Where an observable's + and − acceptance windows at a held-out magnitude are
  disjoint, both comparisons are reported as confounded, neither passed nor failed. Overlapping
  observables are judged.
- **The windows come from the observations alone,** never from a prediction.

**The verdict, in order:**
1. **undetermined**, if fewer than two held-out voltages carry both times (from structure);
2. **cannot_predict**, if the law leaves its domain at a held-out voltage;
3. **undetermined**, if the judged comparisons fall below the minimum judged set: two held-out
   voltages each carrying both judged times, and a judged G_ss wherever the paper reports G_ss at a
   held-out voltage;
4. otherwise **pass or fail**, by section 13's rule 4 on the judged comparisons.

**Part S,** the separately named steady-state result, is scored only when that verdict is
undetermined, and it never changes it.

Stages (from the checkout's root):
    python -m validation.junction_gate_benchmark.score check FIT HELD_OUT PROTOCOL
        the layout, the split and the protocol's fields: key paths, counts and voltages only
    python -m validation.junction_gate_benchmark.score resolve FILE --role train|held_out
        every mapped entry by key path, with no value
    python -m validation.junction_gate_benchmark.score score PREDICTIONS HELD_OUT FIT OUT
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

RULE = "docs/JUNCTION_TWO_RELAXATION_DESIGN.md §13.7"
SPLIT_RULE = "section 13.7 S0-S7"
LAW_ID = "junction_series_gates@1"
OBSERVATIONS_SCHEMA = "fr30-junction-observations@1"
PROTOCOL_SCHEMA = "fr30-junction-protocol@1"
PREDICTIONS_SCHEMA = "fr30-junction-predictions@1"
VERDICT_SCHEMA = "fr30-junction-verdict@1"
ROLES = ("train", "held_out")

TIMES = ("tau_fast", "tau_slow")
AMPLITUDES = ("A_fast", "A_slow")
STEADY = "G_ss/G_0"
MAPPED = TIMES + AMPLITUDES + (STEADY,)  # also the order of comparisons at a voltage
PREDICTED_KEY = {
    "tau_fast": "tau_fast_s",
    "tau_slow": "tau_slow_s",
    "A_fast": "A_fast",
    "A_slow": "A_slow",
    STEADY: "G_ss_over_G0",
}

POLARITIES = ("+", "-", "pooled")
TIME_UNITS = {"s": 1.0, "ms": 1e-3}
STEADY_UNITS = "G/G_0"
AMPLITUDE_UNITS = "fraction"
NORMALIZATIONS = ("prepulse", "instantaneous", "reference_step", "fitted_gmax")
ENTRY_NORMALIZATIONS = NORMALIZATIONS + ("not_stated",)
AMPLITUDE_DEFINITIONS = ("of_G0", "of_decaying_part")
DISPERSION_TYPES = ("SEM", "SD", "range")
METHODS = ("printed", "digitized")

# The protocol type (D334): an enumerated, value-free field. Only a symmetric protocol (both cells
# stepped by equal amounts of opposite sign) keeps the pair's mean membrane potential the same at
# both polarities; every other type, "not_stated" included, leaves the comparison confounded.
PROTOCOL_TYPES = ("one_sided", "symmetric", "other", "not_stated")
CONFOUNDING_PROTOCOLS = ("one_sided", "other", "not_stated")
SIGN_MAPS = ("as_printed", "negated", "not_stated")
CELLS = ("cell_1", "cell_2")
CONVENTION_KEYS = ("paper_vj_definition", "protocol_type", "stepped_cell", "holding_mV", "sign_map")
CLASSES = ("decay_list", "training_only", "steady_list", "training")
ENTRY_KEYS = (
    "id",
    "vj_mV",
    "polarity",
    "observable",
    "maps_to",
    "value",
    "units",
    "normalization",
    "amplitude_definition",
    "dispersion",
    "n",
    "source",
    "method",
    "digitizing_error",
)
FIELD_STATUSES = ("stated", "read", "not_stated")
FIT_OFFSETS = ("free", "fixed_constant", "fixed_from_data")
PROTOCOL_FIELDS = {  # name: the value's kind
    "step_duration_s": "positive",
    "step_durations_s": "positive_list",
    "gss_time_s": "positive",
    "prepulse_mV": "number",
    "prepulse_s": "nonnegative",
    "normalization": NORMALIZATIONS,
    "reference_mV": "number",
    "fit_window_s": "window",
    "fit_form": "text",
    "fit_offset": FIT_OFFSETS,
    "amplitude_definition": AMPLITUDE_DEFINITIONS,
    "sampling_Hz": "positive",
    "filter_Hz": "positive",
    "temperature_C": "number",
    "cells": "text",
    "construct": "text",
    "n": "count",
}

TIME_RATIO = 1.25  # |ln(pred/obs)| <= ln 1.25
STEADY_TOLERANCE = 0.05  # |pred - obs| <= 0.05 of G_0
AMPLITUDE_TOLERANCE = 0.10  # |pred - obs| <= 0.10, in the paper's amplitude definition
SEM_FACTOR = 2.0  # 2 SEM replaces a tolerance where it is wider
RELAXATION_FRACTION = 0.75  # at least 75% of the judged relaxation comparisons pass
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


def _finite(x):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


def _text(obj, key, where, *, nullable=False):
    x = obj.get(key) if isinstance(obj, dict) else None
    if x is None and nullable:
        return None
    if not isinstance(x, str) or not x.strip():
        raise Refusal(f"{where}.{key}: absent or not a non-empty string")
    return x


def _choice(obj, key, where, allowed, *, nullable=False):
    if not isinstance(obj, dict) or key not in obj:
        raise Refusal(f"{where}: no key '{key}'")
    x = obj[key]
    if x is None and nullable:
        return None
    if x not in allowed:
        raise Refusal(f"{where}.{key}: not one of {allowed}")
    return x


def _magnitudes(obj, key, where):
    """A list of distinct positive magnitudes (mV), as floats, sorted."""
    xs = obj.get(key) if isinstance(obj, dict) else None
    if not isinstance(xs, list):
        raise Refusal(f"{where}.{key}: absent or not a list")
    out = []
    for i, x in enumerate(xs):
        if not _finite(x) or not x > 0:
            raise Refusal(f"{where}.{key}[{i}]: not a positive finite number")
        out.append(float(x))
    if len(set(out)) != len(out):
        raise Refusal(f"{where}.{key}: a magnitude listed twice")
    return sorted(out)


def read_convention(doc, where="convention"):
    """The convention block (§13.7 E3): the paper's V_j definition, the protocol type, the stepped
    cell, each cell's holding level and the sign map, validated and copied."""
    conv = doc.get("convention") if isinstance(doc, dict) else None
    if not isinstance(conv, dict):
        raise Refusal(f"{where}: absent or not an object")
    for key in CONVENTION_KEYS:
        if key not in conv:
            raise Refusal(f"{where}: no key '{key}'")
    _text(conv, "paper_vj_definition", where)
    kind = _choice(conv, "protocol_type", where, PROTOCOL_TYPES)
    stepped = _choice(conv, "stepped_cell", where, CELLS, nullable=True)
    if kind == "one_sided" and stepped is None:
        raise Refusal(f"{where}.stepped_cell: a one_sided protocol names its stepped cell")
    if kind == "symmetric" and stepped is not None:
        raise Refusal(f"{where}.stepped_cell: a symmetric protocol steps both cells (null)")
    holding = conv["holding_mV"]
    if not isinstance(holding, dict) or set(holding) != set(CELLS):
        raise Refusal(f"{where}.holding_mV: not an object with exactly {CELLS}")
    for cell in CELLS:
        if holding[cell] is not None and not _finite(holding[cell]):
            raise Refusal(f"{where}.holding_mV.{cell}: neither null nor a finite number")
    _choice(conv, "sign_map", where, SIGN_MAPS)
    return {
        "paper_vj_definition": conv["paper_vj_definition"],
        "protocol_type": kind,
        "stepped_cell": stepped,
        "holding_mV": {c: holding[c] for c in CELLS},
        "sign_map": conv["sign_map"],
    }


def read_split(doc, where="split"):
    """The split block (§13.7 S7): S0's classes, the magnitudes already seen, and the held-out
    magnitudes, as declared by the extractor."""
    split = doc.get("split") if isinstance(doc, dict) else None
    if not isinstance(split, dict):
        raise Refusal(f"{where}: absent or not an object")
    if split.get("rule") != SPLIT_RULE:
        raise Refusal(f"{where}.rule: absent or not '{SPLIT_RULE}'")
    classes = split.get("classes_mV")
    if not isinstance(classes, dict) or set(classes) != set(CLASSES):
        raise Refusal(f"{where}.classes_mV: not an object with exactly {CLASSES}")
    declared = {c: _magnitudes(classes, c, f"{where}.classes_mV") for c in CLASSES}
    every = [m for c in CLASSES for m in declared[c]]
    if len(set(every)) != len(every):
        raise Refusal(f"{where}.classes_mV: a magnitude in two classes")
    held = split.get("held_out")
    if not isinstance(held, dict) or set(held) != {"decay_mV", "steady_mV"}:
        raise Refusal(f"{where}.held_out: not an object with exactly decay_mV and steady_mV")
    return {
        "classes_mV": declared,
        "seen_mV": _magnitudes(split, "seen_mV", where),
        "held_out": {
            k: _magnitudes(held, k, f"{where}.held_out") for k in ("decay_mV", "steady_mV")
        },
    }


def read_dispersion(entry, where, units, scale):
    """An entry's SEM (in seconds or the entry's units), or None, with the note that applies (K6).
    An SD becomes SD/sqrt(n) only where the dispersion states n >= 2 and what n counts (D334)."""
    dispersion = entry["dispersion"]
    if dispersion is None:
        return None, "no dispersion reported: the base tolerance alone"
    if not isinstance(dispersion, dict):
        raise Refusal(f"{where}.dispersion: neither null nor an object")
    kind = _choice(dispersion, "type", f"{where}.dispersion", DISPERSION_TYPES)
    if dispersion.get("units") != units:
        raise Refusal(f"{where}.dispersion.units: absent or not the entry's units")
    if kind == "range":
        bounds = dispersion.get("value")
        if not (isinstance(bounds, list) and len(bounds) == 2 and all(_finite(b) for b in bounds)):
            raise Refusal(f"{where}.dispersion.value: a range is [low, high], two finite numbers")
        if not bounds[0] <= bounds[1]:
            raise Refusal(f"{where}.dispersion.value: a range's low bound is above its high bound")
        return None, "a range: no widening"
    value = number(dispersion, "value", f"{where}.dispersion", nonnegative=True) * scale
    if kind == "SEM":
        return value, "the entry's SEM"
    n, counts = dispersion.get("n"), dispersion.get("n_counts")
    stated = isinstance(n, int) and not isinstance(n, bool) and n >= 2
    if stated and isinstance(counts, str) and counts.strip():
        return value / math.sqrt(n), "an SD with n and what n counts stated: SD/sqrt(n)"
    return None, "an SD without n and what n counts: no widening"


def read_entry(entry, where):
    """One entry (K2), with its value in seconds for times and its SEM where one applies."""
    if not isinstance(entry, dict):
        raise Refusal(f"{where}: not an object")
    for key in ENTRY_KEYS:
        if key not in entry:
            raise Refusal(f"{where}: no key '{key}'")
    _text(entry, "id", where)
    _text(entry, "observable", where)
    _text(entry, "source", where)
    _choice(entry, "method", where, METHODS)
    vj = number(entry, "vj_mV", where)
    polarity = _choice(entry, "polarity", where, POLARITIES)
    if (polarity == "-" and not vj < 0) or (polarity != "-" and not vj > 0):
        raise Refusal(f"{where}.polarity: against vj_mV's sign (a pooled entry carries |V_j| > 0)")
    n = entry["n"]
    if n is not None and (isinstance(n, bool) or not isinstance(n, int) or n < 1):
        raise Refusal(f"{where}.n: neither null nor a positive integer")
    error = entry["digitizing_error"]
    if error is not None and (not _finite(error) or error < 0):
        raise Refusal(f"{where}.digitizing_error: neither null nor a nonnegative number")
    mapped = _choice(entry, "maps_to", where, MAPPED, nullable=True)
    units = entry["units"]
    head = {"path": where, "vj_mV": vj, "polarity": polarity, "magnitude": abs(vj), "units": units}
    if mapped is None:
        return {**head, "maps_to": None}
    if mapped in TIMES:
        scale = TIME_UNITS.get(units) if isinstance(units, str) else None
    elif mapped == STEADY:
        scale = 1.0 if units == STEADY_UNITS else None
    else:
        scale = 1.0 if units == AMPLITUDE_UNITS else None
    if scale is None:
        raise Refusal(f"{where}.units: not one of the known units for {mapped}")
    normalization, definition = entry["normalization"], entry["amplitude_definition"]
    if mapped in TIMES:
        if normalization is not None or definition is not None:
            raise Refusal(f"{where}: a time carries no normalization or amplitude definition")
    else:
        _choice(entry, "normalization", where, ENTRY_NORMALIZATIONS)
        if mapped in AMPLITUDES:
            _choice(entry, "amplitude_definition", where, AMPLITUDE_DEFINITIONS)
        elif definition is not None:
            raise Refusal(f"{where}.amplitude_definition: only an amplitude carries one")
    value = number(entry, "value", where, positive=mapped in TIMES) * scale
    sem, note = read_dispersion(entry, where, units, scale)
    return {
        **head,
        "maps_to": mapped,
        "value": value,
        "sem": sem,
        "sem_note": note,
        "normalization": normalization,
        "amplitude_definition": definition,
        "digitizing_error": None if error is None else float(error) * scale,
    }


def read_observations(doc, role):
    """fit.json (role "train") or held_out.json (role "held_out") in the §13.7 layout (K1 to K3)."""
    if not isinstance(doc, dict):
        raise Refusal("the top level is not an object")
    if doc.get("schema") != OBSERVATIONS_SCHEMA:
        raise Refusal(f"schema: absent or not {OBSERVATIONS_SCHEMA}")
    if doc.get("role") != role:
        raise Refusal(f"role: absent or not '{role}'")
    convention, split = read_convention(doc), read_split(doc)
    if "observables" not in doc:
        raise Refusal("no 'observables' key at the top level")
    listed = doc["observables"]
    if isinstance(listed, dict):
        raise Refusal("observables: an object of named lists; the layout is one flat list (§13.6)")
    if not isinstance(listed, list):
        raise Refusal("observables: not a list")
    entries = [read_entry(e, f"observables[{i}]") for i, e in enumerate(listed)]
    withheld = doc.get("withheld")
    if not isinstance(withheld, list):
        raise Refusal("withheld: absent or not a list")
    for i, item in enumerate(withheld):
        _text(item, "name", f"withheld[{i}]")
        _text(item, "why", f"withheld[{i}]")
    if role == "train" and withheld:
        raise Refusal("withheld: not empty in a training file (E6: summaries go to held_out.json)")
    if not isinstance(doc.get("not_used"), list):
        raise Refusal("not_used: absent or not a list")
    _check_entries(entries)
    return {"convention": convention, "split": split, "entries": entries, "withheld": withheld}


def _check_entries(entries):
    """K3 and S0's precedence: one entry per (vj, polarity, maps_to), and no magnitude carrying both
    per-polarity and pooled entries of one observable."""
    seen, kinds = {}, {}
    for e in entries:
        if e["maps_to"] is None:
            continue
        key = (e["vj_mV"], e["polarity"], e["maps_to"])
        if key in seen:
            raise Refusal(
                f"{seen[key]} and {e['path']}: two entries for one voltage and observable"
            )
        seen[key] = e["path"]
        pooled = e["polarity"] == "pooled"
        kinds.setdefault((e["magnitude"], e["maps_to"]), set()).add(pooled)
    for (_, mapped), flags in kinds.items():
        if len(flags) == 2:
            raise Refusal(
                f"observables: per-polarity and pooled entries of {mapped} at one magnitude "
                "(S0: the per-polarity ones are the data units; list the pooled under not_used)"
            )


def classify(entries):
    """S0's classes from mapped entries: per magnitude, decays (times and amplitudes) and G_ss at
    each polarity or pooled."""
    found = {}
    for e in entries:
        if e["maps_to"] is None:
            continue
        kind = "steady" if e["maps_to"] == STEADY else "decay"
        found.setdefault(e["magnitude"], {"decay": set(), "steady": set()})[kind].add(e["polarity"])

    def both(polarities):
        return {"+", "-"} <= polarities or "pooled" in polarities

    classes = {c: [] for c in CLASSES}
    for m in sorted(found):
        decay, steady = found[m]["decay"], found[m]["steady"]
        if decay and both(decay):
            classes["decay_list"].append(m)
        elif decay:
            classes["training_only"].append(m)
        elif both(steady):
            classes["steady_list"].append(m)
        else:
            classes["training"].append(m)
    return classes


def rank_rule(magnitudes, seen=()):
    """S1 and S2: drop the magnitudes already seen, sort, and hold out the interior ones at even
    rank; the smallest and the largest stay in training."""
    ranked = sorted(m for m in magnitudes if m not in set(seen))
    return [m for i, m in enumerate(ranked, start=1) if 1 < i < len(ranked) and i % 2 == 0]


def pair(fit, held):
    """K4 and K5 over the two files read: identical convention and split blocks, S0's classes and
    the held-out sets recomputed from the entries, no training entry at a held-out magnitude, and
    every held-out magnitude present at each of its units. Returns the held-out units."""
    if fit["convention"] != held["convention"]:
        raise Refusal("convention: the two files' blocks differ")
    if fit["split"] != held["split"]:
        raise Refusal("split: the two files' blocks differ")
    split = fit["split"]
    entries = fit["entries"] + held["entries"]
    keys = {}
    for e in entries:
        if e["maps_to"] is None:
            continue
        key = (e["vj_mV"], e["polarity"], e["maps_to"])
        if key in keys:
            raise Refusal(f"{keys[key]} and {e['path']}: one voltage and observable in both files")
        keys[key] = e["path"]
    classes = classify(entries)
    for c in CLASSES:
        if classes[c] != split["classes_mV"][c]:
            raise Refusal(f"split.classes_mV.{c}: not S0 applied to the files' entries")
    seen = split["seen_mV"]
    rule = {
        "decay_mV": rank_rule(classes["decay_list"], seen),
        "steady_mV": rank_rule(classes["steady_list"], seen),
    }
    for k in ("decay_mV", "steady_mV"):
        if rule[k] != split["held_out"][k]:
            raise Refusal(f"split.held_out.{k}: not S1 to S5 applied to the files' entries")
    held_out = set(rule["decay_mV"]) | set(rule["steady_mV"])
    for e in fit["entries"]:
        if e["magnitude"] in held_out:
            raise Refusal(f"fit {e['path']}: a training entry at a held-out magnitude (K5)")
    for e in held["entries"]:
        if e["magnitude"] not in held_out:
            raise Refusal(f"held_out {e['path']}: an entry at a magnitude not held out (K5)")
    units = []
    for m in sorted(held_out):
        here = [e for e in held["entries"] if e["magnitude"] == m and e["maps_to"] is not None]
        if any(e["polarity"] == "pooled" for e in here):
            units.append(("pooled", m))
            continue
        for sign, polarity in ((-1.0, "-"), (1.0, "+")):
            if not any(e["polarity"] == polarity for e in here):
                raise Refusal(f"held_out: no mapped entry at {_mv(sign * m)} (K5)")
            units.append((polarity, m))
    return {"classes": classes, "held_out": rule, "units": units}


def read_protocol(doc):
    """protocol.json: its convention block and every field of §13.7 E7 with its status."""
    if not isinstance(doc, dict):
        raise Refusal("protocol: the top level is not an object")
    if doc.get("schema") != PROTOCOL_SCHEMA:
        raise Refusal(f"protocol.schema: absent or not {PROTOCOL_SCHEMA}")
    if doc.get("role") != "protocol":
        raise Refusal("protocol.role: absent or not 'protocol'")
    convention = read_convention(doc, "protocol.convention")
    fields = doc.get("fields")
    if not isinstance(fields, dict) or set(fields) != set(PROTOCOL_FIELDS):
        raise Refusal("protocol.fields: not an object with exactly §13.7 E7's fields")
    out = {}
    for name, kind in PROTOCOL_FIELDS.items():
        where = f"protocol.fields.{name}"
        field = fields[name]
        if not isinstance(field, dict):
            raise Refusal(f"{where}: not an object")
        status = _choice(field, "status", where, FIELD_STATUSES)
        for key in ("value", "quote", "place", "how"):
            if key not in field:
                raise Refusal(f"{where}: no key '{key}'")
        value = field["value"]
        if status == "not_stated":
            if value is not None:
                raise Refusal(f"{where}.value: not null where the status is not_stated")
            out[name] = {"value": None, "status": status}
            continue
        if status == "stated":
            _text(field, "quote", where)
            _text(field, "place", where)
        else:
            _text(field, "how", where)
        out[name] = {"value": _field_value(value, kind, where), "status": status}
    return {"convention": convention, "fields": out}


def _field_value(value, kind, where):
    if isinstance(kind, tuple):
        if value not in kind:
            raise Refusal(f"{where}.value: not one of {kind}")
        return value
    if kind == "text":
        if not isinstance(value, str) or not value.strip():
            raise Refusal(f"{where}.value: not a non-empty string")
        return value
    if kind == "count":
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            raise Refusal(f"{where}.value: not a positive integer")
        return value
    if kind == "positive_list":
        if not isinstance(value, list) or not value:
            raise Refusal(f"{where}.value: not a non-empty list")
        if not all(_finite(x) and x > 0 for x in value):
            raise Refusal(f"{where}.value: an item is not a positive finite number")
        return [float(x) for x in value]
    if kind == "window":
        ok = isinstance(value, list) and len(value) == 2 and all(_finite(x) for x in value)
        if not ok or not 0 <= value[0] < value[1]:
            raise Refusal(f"{where}.value: not [start, end] with 0 <= start < end")
        return [float(x) for x in value]
    if not _finite(value):
        raise Refusal(f"{where}.value: not a finite number")
    if kind == "positive" and not value > 0:
        raise Refusal(f"{where}.value: not positive")
    if kind == "nonnegative" and not value >= 0:
        raise Refusal(f"{where}.value: negative")
    return float(value)


def protocol_normalization(protocol):
    """The normalization each G_ss and amplitude entry must carry: the protocol's, or not_stated."""
    field = protocol["fields"]["normalization"]
    return field["value"] if field["status"] != "not_stated" else "not_stated"


def check(fit_doc, held_doc, protocol_doc):
    """The value-free structure check (§13.7 E9): K1 to K7 over the three files, the protocol's
    convention block equal to the data files', and every G_ss and amplitude entry carrying the
    protocol's normalization. Returns counts, labels, voltages and statuses, never a value."""
    fit, held = read_observations(fit_doc, "train"), read_observations(held_doc, "held_out")
    protocol = read_protocol(protocol_doc)
    if protocol["convention"] != fit["convention"]:
        raise Refusal("protocol.convention: not the data files' block")
    split = pair(fit, held)
    expected = protocol_normalization(protocol)
    for label, read in (("fit", fit), ("held_out", held)):
        for e in read["entries"]:
            if e["maps_to"] in (STEADY,) + AMPLITUDES and e["normalization"] != expected:
                raise Refusal(f"{label} {e['path']}.normalization: not the protocol's")
    counts = {}
    for label, read in (("fit", fit), ("held_out", held)):
        rows = {}
        for e in read["entries"]:
            if e["maps_to"] is None:
                key = (e["vj_mV"], e["polarity"], "unmapped", "-", "-", "-")
            else:
                sem_kind = e["sem_note"].split(":")[0]
                key = (
                    e["vj_mV"],
                    e["polarity"],
                    e["maps_to"],
                    e["units"],
                    e["normalization"] or "-",
                    sem_kind,
                )
            rows[key] = rows.get(key, 0) + 1
        counts[label] = sorted(rows.items())
    convention = fit["convention"]
    return {
        "counts": counts,
        "classes_mV": split["classes"],
        "held_out_mV": split["held_out"],
        "units": split["units"],
        "protocol_type": convention["protocol_type"],
        "confounding_protocol": convention["protocol_type"] in CONFOUNDING_PROTOCOLS,
        "sign_map": convention["sign_map"],
        "protocol_fields": {k: v["status"] for k, v in protocol["fields"].items()},
        "withheld": len(held["withheld"]),
    }


def resolve(doc, role):
    """Every mapped entry of one file by key: {(vj, polarity, maps_to): path}, value-free."""
    read = read_observations(doc, role)
    mapped = {(e["vj_mV"], e["polarity"], e["maps_to"]): e["path"] for e in read["entries"]
              if e["maps_to"] is not None}  # fmt: skip
    skipped = [e["path"] for e in read["entries"] if e["maps_to"] is None]
    return {"entries": mapped, "skipped": skipped}


def read_predictions(doc, voltages):
    """predictions.json's entries at the given signed voltages, by key; one block serves all."""
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
        if vj in found:
            raise Refusal(f"{where}: a second prediction at {_mv(vj)}")
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
                    record[observable] = float(x) if _finite(x) else None
                else:
                    record[observable] = number(entry, key, where, positive=True)
            for key in ("A_fast", "A_slow", "C", "A_fast_share"):
                x = entry.get(key)
                record[key] = float(x) if _finite(x) else None
        found[vj] = record
    missing = [_mv(v) for v in sorted(voltages) if v not in found]
    if missing:
        raise Refusal(f"predictions: no entry at {', '.join(missing)}")
    return found


def time_window(observed, sem):
    """A time's acceptance window: the union of the ln 1.25 band and the 2-SEM band, an interval
    because both contain the observation."""
    low, high = observed / TIME_RATIO, observed * TIME_RATIO
    if sem is not None:
        low, high = min(low, observed - SEM_FACTOR * sem), max(high, observed + SEM_FACTOR * sem)
    return low, high


def band(observed, sem, base):
    """A band's tolerance, max(base, 2 SEM), and its window."""
    sem_tolerance = None if sem is None else SEM_FACTOR * sem
    wider = sem_tolerance is not None and sem_tolerance > base
    tolerance = sem_tolerance if wider else base
    return tolerance, wider, (observed - tolerance, observed + tolerance)


def window(entry):
    """The observation's acceptance window for its observable (P1)."""
    if entry["maps_to"] in TIMES:
        return time_window(entry["value"], entry["sem"])
    base = STEADY_TOLERANCE if entry["maps_to"] == STEADY else AMPLITUDE_TOLERANCE
    return band(entry["value"], entry["sem"], base)[2]


def compare_time(predicted, observed, sem, degenerate_reasons=()):
    """|ln(pred/obs)| <= ln 1.25 or |pred - obs| <= 2 SEM, both recorded, with the wider band edge
    on the prediction's side as the tolerance applied (§13.5, unchanged)."""
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
        return {**record, "applied": None, "passes": False, "reason": reason}
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


def compare_band(predicted, observed, sem, base, units, degenerate_reasons=()):
    """G_ss/G_0 (base 0.05) or an amplitude (base 0.10): |pred - obs| <= max(base, 2 SEM)."""
    tolerance, wider, _ = band(observed, sem, base)
    applied = "2 SEM" if wider else f"{base:.2f}"
    record = {
        "predicted": predicted,
        "observed": observed,
        "units": units,
        "sem": sem,
        "tolerance": tolerance,
        "applied": applied,
    }
    if degenerate_reasons or predicted is None:
        why = "degenerate fit: " + "; ".join(degenerate_reasons) if degenerate_reasons else None
        return {**record, "passes": False, "reason": why or "no predicted value"}
    difference = abs(predicted - observed)
    passes = difference <= tolerance
    return {
        **record,
        "abs_difference": difference,
        "passes": passes,
        "reason": None if passes else f"outside {applied}",
    }


def needed(units):
    """The signed voltages predictions must carry: both polarities of every held-out magnitude."""
    return sorted({s * m for _, m in units for s in (-1.0, 1.0)})


def more_than_half(k):
    """Section 13's rule 4 (b): passes at no fewer than floor(k/2) + 1 of k voltages."""
    return k // 2 + 1


def score(predictions, held_out, fit):
    """Section 13.7's comparisons, the one-cell rule, the verdict, Part S and the diagnostics. Both
    observation files are read and paired, by key, before any value is compared."""
    train, held = read_observations(fit, "train"), read_observations(held_out, "held_out")
    split = pair(train, held)
    convention = train["convention"]
    confounding = convention["protocol_type"] in CONFOUNDING_PROTOCOLS
    predicted = read_predictions(predictions, set(needed(split["units"])))
    decay_held = set(split["held_out"]["decay_mV"])
    used = {e["vj_mV"] for e in held["entries"] if e["maps_to"] is not None}
    cannot = sorted(v for v in used if predicted[v]["status"] == "cannot_predict")

    comparisons = []
    for e in sorted(
        (e for e in held["entries"] if e["maps_to"] is not None),
        key=lambda e: (e["vj_mV"] if e["polarity"] != "pooled" else e["magnitude"],
                       MAPPED.index(e["maps_to"])),
    ):  # fmt: skip
        vj = e["vj_mV"]  # a pooled unit is predicted at +|V_j|; the law is symmetric in |V_j|
        p = predicted[vj]
        head = {
            "vj_mV": vj,
            "polarity": e["polarity"],
            "magnitude_mV": e["magnitude"],
            "list": "decay" if e["magnitude"] in decay_held else "steady",
            "observable": e["maps_to"],
            "held_out_path": e["path"],
            "sem_note": e["sem_note"],
            "digitizing_error": e["digitizing_error"],
            "window": list(window(e)),
        }
        if e["maps_to"] == "A_slow" and e["amplitude_definition"] == "of_decaying_part":
            note = "not judged: under of_decaying_part A_slow's share is 1 minus A_fast's"
            comparisons.append({**head, "observed": e["value"], "judged": False, "note": note})
            continue
        if p["status"] == "cannot_predict":
            reason = "cannot predict: the law leaves its domain"
            comparisons.append({**head, "observed": e["value"], "passes": False, "reason": reason})
            continue
        reasons = p["degenerate_reasons"]
        if e["maps_to"] in TIMES:
            c = compare_time(p[e["maps_to"]], e["value"], e["sem"], reasons)
        elif e["maps_to"] == STEADY:
            c = compare_band(p[STEADY], e["value"], e["sem"], STEADY_TOLERANCE, "G/G_0")
        else:
            key = (
                "A_fast_share" if e["amplitude_definition"] == "of_decaying_part" else e["maps_to"]
            )
            c = compare_band(p[key], e["value"], e["sem"], AMPLITUDE_TOLERANCE,
                             e["amplitude_definition"], reasons)  # fmt: skip
        comparisons.append({**head, **c})

    overlap = []  # D1, and the one-cell rule's input
    for m in sorted(set(split["held_out"]["decay_mV"]) | set(split["held_out"]["steady_mV"])):
        for observable in MAPPED:
            plus = [c for c in comparisons if c["magnitude_mV"] == m and c["polarity"] == "+"
                    and c["observable"] == observable]  # fmt: skip
            minus = [c for c in comparisons if c["magnitude_mV"] == m and c["polarity"] == "-"
                     and c["observable"] == observable]  # fmt: skip
            if not (plus and minus) or plus[0].get("judged") is False:
                continue
            (lp, hp), (lm, hm) = plus[0]["window"], minus[0]["window"]
            disjoint = hp < lm or hm < lp
            confounded = disjoint and confounding
            overlap.append({"magnitude_mV": m, "observable": observable,
                            "window_plus": [lp, hp], "window_minus": [lm, hm],
                            "disjoint": disjoint, "confounded": confounded})  # fmt: skip
            if confounded:
                for c in plus + minus:
                    c["confounded"] = True
    for c in comparisons:
        c.setdefault("judged", not c.get("confounded", False))
        c.setdefault("confounded", False)

    def judged(observable=None, voltages=None):
        return [c for c in comparisons if c["judged"]
                and (observable is None or c["observable"] == observable)
                and (voltages is None or c["magnitude_mV"] in voltages)]  # fmt: skip

    decay_units = sorted({c["vj_mV"] for c in comparisons if c["list"] == "decay"})
    units_both = [v for v in decay_units
                  if all(any(c["vj_mV"] == v and c["observable"] == t for c in comparisons)
                         for t in TIMES)]  # fmt: skip
    verdict, basis = _kinetic(comparisons, units_both, cannot, judged)
    part_s = None
    if verdict == "undetermined":
        part_s = _part_s(comparisons, cannot, judged)

    return {
        "schema": VERDICT_SCHEMA,
        "rule": RULE,
        "verdict": verdict,
        "verdict_basis": basis,
        "part_s": part_s,
        "held_out_mV": split["held_out"],
        "units": [[pol, m] for pol, m in split["units"]],
        "protocol_type": convention["protocol_type"],
        "confounding_protocol": confounding,
        "cannot_predict_mV": cannot,
        "comparisons": comparisons,
        "judged": len(judged()),
        "passed": sum(1 for c in judged() if c.get("passes")),
        "confounded": [[c["vj_mV"], c["observable"]] for c in comparisons if c["confounded"]],
        "diagnostics": _diagnostics(train, held, comparisons, overlap, convention, predicted),
        "tolerances": {
            "time_ratio": TIME_RATIO,
            "steady": STEADY_TOLERANCE,
            "amplitude": AMPLITUDE_TOLERANCE,
            "sem_factor": SEM_FACTOR,
            "relaxation_fraction": RELAXATION_FRACTION,
        },
    }


def _kinetic(comparisons, units_both, cannot, judged):
    """FR-30's verdict and its basis, in §13.7's order."""
    if len(units_both) < 2:
        return "undetermined", "fewer than two held-out voltages carry both times (structure)"
    if cannot:
        return "cannot_predict", "the law leaves its domain at a held-out voltage"
    both_judged = [v for v in units_both
                   if all(any(c["vj_mV"] == v and c["observable"] == t and c["judged"]
                              for c in comparisons) for t in TIMES)]  # fmt: skip
    steady_reported = [c for c in comparisons if c["observable"] == STEADY]
    if len(both_judged) < 2:
        return "undetermined", (
            "below the minimum judged set: fewer than two held-out voltages carry both judged "
            "times (the others are confounded by V_m)"
        )
    if steady_reported and not judged(STEADY):
        return "undetermined", (
            "below the minimum judged set: G_ss is reported at held-out voltages and every one "
            "is confounded by V_m"
        )
    steady_ok = all(c["passes"] for c in judged(STEADY))
    relaxation = [c for c in judged() if c["observable"] != STEADY]
    each = {}
    for observable in TIMES + AMPLITUDES:
        rows = judged(observable)
        if rows:
            k, passed = len(rows), sum(1 for c in rows if c["passes"])
            each[observable] = passed >= more_than_half(k)
    fraction_ok = sum(1 for c in relaxation if c["passes"]) >= RELAXATION_FRACTION * len(relaxation)
    if steady_ok and all(each.values()) and fraction_ok:
        return "pass", "every judged G_ss, more than half of each judged observable, and 75% pass"
    failed = []
    if not steady_ok:
        failed.append("a judged G_ss fails")
    failed += [f"{o} passes at no more than half of its judged voltages"
               for o, ok in each.items() if not ok]  # fmt: skip
    if not fraction_ok:
        failed.append("fewer than 75% of the judged relaxation comparisons pass")
    return "fail", "; ".join(failed)


def _part_s(comparisons, cannot, judged):
    """Part S, the separately named steady-state result (D334): every held-out G_ss, judged by the
    G_ss rule under the one-cell rule, with at least two judged comparisons."""
    steady = [c for c in comparisons if c["observable"] == STEADY]
    if not steady:
        return {"verdict": "not_applicable", "basis": "no held-out G_ss"}
    if cannot:
        return {"verdict": "cannot_predict", "basis": "the law leaves its domain"}
    rows = judged(STEADY)
    if len(rows) < 2:
        return {"verdict": "undetermined", "basis": "fewer than two judged G_ss comparisons"}
    ok = all(c["passes"] for c in rows)
    return {
        "verdict": "pass" if ok else "fail",
        "basis": f"{sum(1 for c in rows if c['passes'])} of {len(rows)} judged G_ss pass",
        "note": "a steady-state result only: FR-30's own verdict stays undetermined",
    }


def _diagnostics(train, held, comparisons, overlap, convention, predicted):
    """D1 to D4 (§13.7 part 7): reported, never judged."""
    entries = [e for e in train["entries"] + held["entries"] if e["maps_to"] is not None]
    differences = []  # D2
    for m in sorted({e["magnitude"] for e in entries}):
        for observable in MAPPED:
            plus = [e for e in entries if e["magnitude"] == m and e["polarity"] == "+"
                    and e["maps_to"] == observable]  # fmt: skip
            minus = [e for e in entries if e["magnitude"] == m and e["polarity"] == "-"
                     and e["maps_to"] == observable]  # fmt: skip
            if not (plus and minus):
                continue
            p, q = plus[0], minus[0]
            combined = (math.hypot(p["sem"], q["sem"])
                        if p["sem"] is not None and q["sem"] is not None else None)  # fmt: skip
            diff = p["value"] - q["value"]
            differences.append({
                "magnitude_mV": m,
                "observable": observable,
                "plus_minus_minus": diff,
                "combined_sem": combined,
                "z": diff / combined if combined else None,
                "file": "held_out" if p in held["entries"] else "fit",
            })  # fmt: skip
    means = []  # D3
    for row in overlap:
        m, observable = row["magnitude_mV"], row["observable"]
        plus = [e for e in held["entries"] if e["magnitude"] == m and e["polarity"] == "+"
                and e["maps_to"] == observable][0]  # fmt: skip
        minus = [e for e in held["entries"] if e["magnitude"] == m and e["polarity"] == "-"
                 and e["maps_to"] == observable][0]  # fmt: skip
        mean = (plus["value"] + minus["value"]) / 2
        sem = (math.hypot(plus["sem"], minus["sem"]) / 2
               if plus["sem"] is not None and minus["sem"] is not None else None)  # fmt: skip
        p = predicted.get(m, {})  # +|V_j|: the law is symmetric in |V_j|
        if observable in AMPLITUDES and plus["amplitude_definition"] == "of_decaying_part":
            value = p.get("A_fast_share")
        else:
            value = p.get(observable)
        means.append({"magnitude_mV": m, "observable": observable, "polarity_mean": mean,
                      "mean_sem": sem, "predicted": value})  # fmt: skip
    oriented = convention["sign_map"] != "not_stated"
    vm = []  # D4
    for row in differences:
        if row["observable"] != STEADY:
            continue
        sign = "+ below -" if row["plus_minus_minus"] < 0 else "+ not below -"
        vm.append({"magnitude_mV": row["magnitude_mV"], "observed": sign if oriented else
                   "unoriented"})  # fmt: skip
    return {
        "D1_window_overlap": overlap,
        "D2_polarity_differences": differences,
        "D3_polarity_mean": means,
        "D4_protocol_and_vm": {
            "protocol_type": convention["protocol_type"],
            "stepped_cell": convention["stepped_cell"],
            "holding_mV": convention["holding_mV"],
            "sign_map": convention["sign_map"],
            "hypothesis": (
                "Revilla, Bennett and Barrio (2000), doi:10.1073/pnas.97.26.14760: equal "
                "depolarization of both cells decreases g(j); under a one-cell protocol it "
                "predicts G_ss(+) <= G_ss(-), + meaning the stepped cell relatively positive"
            ),
            "observed_sign_by_magnitude": vm,
        },
    }


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load(path):
    return json.loads(Path(path).read_text())


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    stages = parser.add_subparsers(dest="stage", required=True)
    c = stages.add_parser("check", help="the value-free structure check (E9)")
    c.add_argument("fit")
    c.add_argument("held_out")
    c.add_argument("protocol")
    r = stages.add_parser("resolve", help="every mapped entry by key path, no value")
    r.add_argument("file")
    r.add_argument("--role", choices=ROLES, required=True)
    s = stages.add_parser("score", help="the verdict, written to OUT")
    s.add_argument("predictions")
    s.add_argument("held_out")
    s.add_argument("fit")
    s.add_argument("out")
    s.add_argument("--expect-sha256", help="the held-out file's registered digest")
    args = parser.parse_args(argv)
    try:
        if args.stage == "check":
            summary = check(_load(args.fit), _load(args.held_out), _load(args.protocol))
            for label in ("fit", "held_out"):
                for (vj, pol, mapped, units, norm, sem), n in summary["counts"][label]:
                    print(f"{label}: {_mv(vj)} ({pol}) {mapped} [{units}; {norm}; {sem}]: {n}")
            for name, mags in summary["classes_mV"].items():
                print(f"class {name}: {[f'{m:g}' for m in mags]}")
            for name, mags in summary["held_out_mV"].items():
                print(f"held out {name}: {[f'{m:g}' for m in mags]}")
            print(f"units: {[f'{pol}{m:g}' for pol, m in summary['units']]}")
            print(
                f"protocol type: {summary['protocol_type']} (confounding: "
                f"{summary['confounding_protocol']}); sign map: {summary['sign_map']}"
            )
            for name, status in summary["protocol_fields"].items():
                print(f"protocol field {name}: {status}")
            print(f"withheld summaries: {summary['withheld']}")
            print("check passed; no value printed")
            return 0
        if args.stage == "resolve":
            resolved = resolve(_load(args.file), args.role)
            for (vj, pol, mapped), path in sorted(resolved["entries"].items()):
                print(f"{_mv(vj)} ({pol}) {mapped}: {path}")
            print(f"unmapped: {resolved['skipped']}")
            print(f"resolved {len(resolved['entries'])} entries; no value printed")
            return 0
        digest = _sha256(args.held_out)
        if args.expect_sha256 and digest != args.expect_sha256.lower():
            raise Refusal(f"the held-out file's sha256 is {digest}, not the registered one")
        result = score(_load(args.predictions), _load(args.held_out), _load(args.fit))
        result["files"] = {
            name: {"path": str(Path(path).resolve()), "sha256": _sha256(path)}
            for name, path in (("predictions", args.predictions), ("held_out", args.held_out),
                               ("fit", args.fit))
        }  # fmt: skip
        result["files"]["held_out"]["expected_sha256"] = args.expect_sha256
        result["utc"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        Path(args.out).write_text(json.dumps(result, indent=1) + "\n")
        for comp in result["comparisons"]:
            label = f"{_mv(comp['vj_mV'])} {comp['observable']}"
            if comp["confounded"]:
                print(f"{label}: confounded by V_m (the + and - windows are disjoint; not judged)")
            elif not comp["judged"]:
                print(f"{label}: not judged ({comp['note']})")
            else:
                mark = "pass" if comp["passes"] else "FAIL"
                why = f" ({comp['reason']})" if comp.get("reason") else ""
                print(f"{label}: {mark}, applied {comp.get('applied')}{why}")
        print(
            f"verdict: {result['verdict']} ({result['passed']} of {result['judged']} judged pass; "
            f"{len(result['confounded'])} confounded); values in {args.out}"
        )
        if result["part_s"] is not None:
            print(f"part S (steady state): {result['part_s']['verdict']}")
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
