#!/usr/bin/env python3
"""Compare a Cells result with a plain-BETSE reference: route-agnostic, NumPy only.

Inputs (no BETSE or Cells imports; any Cells model or route can produce the result):

* BETSE reference: a ``betse_reference_extract.py`` extraction directory, or a
  case directory containing ``extract/``.
* Cells result in the *comparison layout*, written by ``write_layout``::

      comparison_manifest.json
          kind                   "cells.betse_comparison_layout@1"
          protocol_sha256        SHA-256 of the protocol, fixed before the Cells run
          betse_geometry_sha256  SHA-256 of the case's geometry.npz the run was built on
          provenance             Cells revision, dirty diff, model, backend, ...
          phases                 {phase: {"elapsed_after_update_s": [...],
                                          "final_elapsed_s": t}}
          aliased                optional ["phase/observable", ...]
      <phase>_history.npz        vm_time (S, M), vm_ave_time (S, N), cc_time (S, ions, N),
                                 cc_env_time (S, ions, env), venv_time (S, grid)
      <phase>_final.npz          vm, vm_ave, cc_cells, cc_env, v_env

  Names, shapes, units (V, mol/m^3) and element order are those of the BETSE
  extraction of the same case (its geometry.npz ordering).
* A protocol JSON (validation/betse/protocols/): observables, tolerance classes
  and the verdict class. Optional keys, absent from older protocols (which give
  unchanged results):

  - observable ``"exclude": "grid_boundary_ring"``: leave the outermost row and
    column of the case's ECM grid (2 (R + C) - 4 sites of geometry X) out of the
    judged errors; their max errors are reported under ``excluded``.
  - observable ``"judged": false``: compute and report everything (including
    ``flat``) but leave it out of the verdict; it may be absent from the Cells
    result. ``diag_*`` entries (a name or the wildcard ``"diag_*"``, always
    ``judged`` false) report the Cells layout's diag arrays with no BETSE pairing.
  - a tolerance class value is a number for every phase or ``{phase: number}``; a
    phase's value may instead be ``{"by_ion": {ion: number, ...}}`` naming every ion
    of the case, for observables with an ions axis (cc_time, cc_env_time): each ion
    is then judged against its own tolerance (worst errors reported per ion).

Samples are paired on common elapsed times only (BETSE sample k holds the state
after k + 1 updates; see the extract manifest ``time``). The comparator refuses
(verdict ``refused``) on an invalid input, a protocol or geometry hash mismatch,
no common samples, a shape mismatch, an aliased series or non-finite reference
values. Otherwise each observable gets its max abs and max rel error with element
and time, its own dynamic range over the phase (``flat`` when it does not exceed
the tolerance, i.e. the comparison cannot discriminate), and pass/fail for every
tolerance class; the verdict uses the protocol's verdict class.

    python3 validation/betse/cells_betse_compare.py compare \\
        --betse CASE_OR_EXTRACT --cells LAYOUT --protocol P.json --out DIR
    python3 validation/betse/cells_betse_compare.py self-compare \\
        --betse CASE_OR_EXTRACT --protocol P.json --out DIR [--perturb-...]

Exit status: 0 pass, 1 fail, 2 refused, 3 comparator error (self-compare: 0 when both
checks behave as required).
Relative ``--out`` paths resolve against $CELLS_OUTPUT_ROOT.
"""

import argparse
import hashlib
import importlib.util
import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if __name__ == "__main__" and sys.path and Path(sys.path[0] or ".").resolve() == HERE:
    sys.path.pop(0)

import numpy as np  # noqa: E402

KIND = "cells.betse_comparison_result@1"
LAYOUT_KIND = "cells.betse_comparison_layout@1"
PROTOCOL_SCHEMA = "cells.betse_comparison_protocol@1"
LAYOUT_MANIFEST = "comparison_manifest.json"
PHASES = ("init", "sim")
DIAG_PREFIX, DIAG_ALL = "diag_", "diag_*"  # Cells-only arrays: reported, never judged
RING = "grid_boundary_ring"  # outermost row and column of the case's ECM grid
# History observable -> end-of-phase array of the same quantity.
SUPPORTED = {
    "vm_time": "vm",
    "vm_ave_time": "vm_ave",
    "cc_time": "cc_cells",
    "cc_env_time": "cc_env",
    "venv_time": "v_env",
}


class Refusal(ValueError):
    """The inputs cannot support a verdict; nothing is judged."""


def _load_sibling(name):
    spec = importlib.util.spec_from_file_location(f"_cells_{name}", HERE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_EXTRACT = _load_sibling("betse_reference_extract")  # NumPy-only helpers; BETSE import is lazy
_RUN = _load_sibling("betse_reference_run")  # stdlib only


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _npz(path):
    with np.load(path, allow_pickle=False) as data:
        return {key: data[key] for key in data.files}


def _json(path):
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError) as error:
        raise Refusal(f"unreadable JSON {path}: {error!r}") from error


def _valid_tolerance(value, phases):
    def positive(v):
        number = isinstance(v, (int, float)) and not isinstance(v, bool)
        return number and math.isfinite(v) and v > 0

    def entry(v):
        if isinstance(v, dict):
            ions = v.get("by_ion")
            return (
                set(v) == {"by_ion"}
                and isinstance(ions, dict)
                and ions
                and all(isinstance(k, str) and positive(t) for k, t in ions.items())
            )
        return positive(v)

    if isinstance(value, dict):
        return set(phases) <= set(value) <= set(PHASES) and all(map(entry, value.values()))
    return positive(value)


def resolve_tolerance(value, phase):
    """A tolerance class value: one number for every phase, or {phase: number | by_ion}."""
    return value[phase] if isinstance(value, dict) else value


def _smallest(tolerance):
    """The tolerance itself, or the smallest per-ion tolerance (flat checks of unpaired data)."""
    return min(tolerance["by_ion"].values()) if isinstance(tolerance, dict) else tolerance


def _per_ion(error, axis):
    """Largest value per ion of an error (or change) array whose ion axis is ``axis``."""
    return error.max(axis=tuple(i for i in range(error.ndim) if i != axis))


def _relative_change(series):
    change = series.max(axis=0) - series.min(axis=0)
    scale = np.abs(series).max(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        return change, np.where(scale > 0, change / scale, 0.0)


def grid_boundary_ring(geometry):
    """Flat indices of the outermost rows and columns of the case's ECM grid, and its shape.

    BETSE flattens its ECM grid row-major (xypts = X, Y raveled; checked when present),
    so for an R x C grid the ring has 2 (R + C) - 4 sites.
    """
    if "X" not in geometry:
        raise Refusal(f"{RING} needs the case's ECM grid (geometry X)")
    rows, cols = geometry["X"].shape
    if "xypts" in geometry and not (
        np.array_equal(geometry["xypts"][:, 0], geometry["X"].ravel())
        and np.array_equal(geometry["xypts"][:, 1], geometry["Y"].ravel())
    ):
        raise Refusal("ECM grid points are not the row-major flattening of X and Y")
    i, j = np.divmod(np.arange(rows * cols), cols)
    ring = np.flatnonzero((i == 0) | (i == rows - 1) | (j == 0) | (j == cols - 1))
    return ring, (rows, cols)


def _ring_mask(shape, ring, grid):
    sites = grid[0] * grid[1]
    if not shape or shape[-1] != sites:
        raise Refusal(f"{RING} needs a last axis of {sites} ECM grid points, not {list(shape)}")
    mask = np.zeros(shape, dtype=bool)
    mask[..., ring] = True
    return mask


# ............................................................ inputs


def load_protocol(path):
    """Validated protocol, its SHA-256 and resolved tolerances."""
    path = Path(path)
    protocol = _json(path)
    if protocol.get("schema") != PROTOCOL_SCHEMA:
        raise Refusal(f"protocol schema must be {PROTOCOL_SCHEMA}")
    phases = protocol.get("phases")
    if not phases or not set(phases) <= set(PHASES) or len(set(phases)) != len(phases):
        raise Refusal(f"protocol phases must be a subset of {PHASES}")
    quantities = protocol.get("tolerance_quantities") or {}
    if not quantities or any(q.get("kind") not in ("abs", "rel") for q in quantities.values()):
        raise Refusal("every tolerance quantity needs kind 'abs' or 'rel'")
    classes = protocol.get("tolerance_classes") or {}
    for name, values in classes.items():
        if set(values) != set(quantities) or not all(
            _valid_tolerance(v, phases) for v in values.values()
        ):
            raise Refusal(
                f"tolerance class {name!r} must give a positive value, or one per phase "
                "({phase: value}), per quantity"
            )
    if protocol.get("verdict_class") not in classes:
        raise Refusal("verdict_class must name a tolerance class")
    observables = protocol.get("observables") or {}
    for name, row in observables.items():
        if not isinstance(row.get("judged", True), bool):
            raise Refusal(f"{name}: judged must be true or false")
        if name.startswith(DIAG_PREFIX):
            if row.get("judged", True) or {"final", "exclude"} & set(row):
                raise Refusal(f"{name}: Cells-only diag_* entries need judged false, no pairing")
            if row.get("tolerance") not in (None, *quantities):
                raise Refusal(f"{name}: tolerance must name a tolerance quantity")
            continue
        if SUPPORTED.get(name) is None or row.get("final") not in (SUPPORTED[name], None):
            raise Refusal(f"unsupported observable or final pairing: {name}")
        if row.get("tolerance") not in quantities:
            raise Refusal(f"{name}: tolerance must name a tolerance quantity")
        if row.get("exclude") not in (None, RING):
            raise Refusal(f"{name}: unknown exclusion {row.get('exclude')!r}")
    if not observables:
        raise Refusal("protocol lists no observables")
    if not any(row.get("judged", True) for row in observables.values()):
        raise Refusal("protocol judges no observable")
    atol = protocol.get("time_alignment_atol_s")
    if not isinstance(atol, (int, float)) or not atol > 0:
        raise Refusal("time_alignment_atol_s must be positive")
    if int(protocol.get("min_common_samples", 1)) < 1:
        raise Refusal("min_common_samples must be at least 1")
    return protocol, sha256_file(path)


def betse_extract_dir(path):
    path = Path(path)
    for candidate in (path, path / "extract"):
        if (candidate / "manifest.json").is_file():
            return candidate
    raise Refusal(f"no BETSE extraction (manifest.json) in {path} or {path / 'extract'}")


def load_betse(path):
    directory = betse_extract_dir(path)
    problems = _EXTRACT.verify_extract(directory)
    if problems:
        raise Refusal(f"BETSE extraction fails verification: {problems[:3]}")
    return directory, _json(directory / "manifest.json")


def load_layout(path, protocol_sha256, geometry_sha256):
    directory = Path(path)
    manifest = _json(directory / LAYOUT_MANIFEST)
    if manifest.get("kind") != LAYOUT_KIND:
        raise Refusal(f"Cells result is not in the comparison layout ({LAYOUT_KIND})")
    if manifest.get("protocol_sha256") != protocol_sha256:
        raise Refusal("Cells result does not name this protocol's sha256 (fixed before its run)")
    if manifest.get("betse_geometry_sha256") != geometry_sha256:
        raise Refusal("Cells result was not built on this BETSE case's geometry.npz")
    if not isinstance(manifest.get("provenance"), dict) or not manifest["provenance"]:
        raise Refusal("Cells result has no provenance")
    return directory, manifest


# ............................................................ alignment and errors


def align(betse_times, cells_times, atol):
    """Pairs (betse index, cells index, elapsed) of samples at common elapsed times."""
    betse_times = np.asarray(betse_times, dtype=np.float64)
    cells_times = np.asarray(cells_times, dtype=np.float64)
    for label, times in (("BETSE", betse_times), ("Cells", cells_times)):
        if times.ndim != 1 or not np.all(np.isfinite(times)):
            raise Refusal(f"{label} elapsed times must be finite numbers")
        if times.size > 1 and np.min(np.diff(times)) <= 2 * atol:
            raise Refusal(f"{label} elapsed times are not increasing by more than 2 * atol")
    pairs = []
    for i, t in enumerate(betse_times):
        hits = np.flatnonzero(np.abs(cells_times - t) <= atol)
        if hits.size:
            pairs.append((i, int(hits[0]), float(t)))
    return pairs


def _labels(element, axes, ions, owner):
    labels = {}
    for axis, index in zip(axes, element, strict=True):
        labels[axis] = int(index)
        if axis == "ions" and ions and index < len(ions):
            labels["ion"] = ions[index]
        if axis == "membranes" and owner is not None:
            labels["owner_cell"] = int(owner[index])
    return labels


def errors(betse, cells):
    """Absolute and relative error arrays; non-finite Cells values count as infinite."""
    betse = np.asarray(betse, dtype=np.float64)
    cells = np.asarray(cells, dtype=np.float64)
    absolute = np.abs(cells - betse)
    absolute[~np.isfinite(absolute)] = np.inf
    scale = np.abs(betse)
    with np.errstate(divide="ignore", invalid="ignore"):
        relative = np.where(scale > 0, absolute / scale, np.where(absolute == 0, 0.0, np.inf))
    return absolute, relative


def _worst(error, betse, cells, axes, ions, owner, when):
    index = np.unravel_index(int(np.argmax(error)), error.shape)
    sample, element = (index[0], index[1:]) if when is not None else (None, index)
    row = {
        "value": float(error[index]),
        "element": [int(i) for i in element],
        "labels": _labels(element, axes, ions, owner),
        "betse_value": float(betse[index]),
        "cells_value": float(cells[index]),
    }
    if when is not None:
        row.update(when(sample))
    return row


def dynamic_range(series, kind):
    """Range of the reference over the phase: the largest per-element change in time."""
    series = np.asarray(series, dtype=np.float64)
    change = series.max(axis=0) - series.min(axis=0)
    scale = np.abs(series).max(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        relative = np.where(scale > 0, change / scale, 0.0)
    return {
        "max_temporal_change": float(change.max()),
        "max_relative_temporal_change": float(relative.max()),
        "measure": "relative" if kind == "rel" else "absolute",
        "value_min": float(series.min()),
        "value_max": float(series.max()),
        "samples_including_final": int(series.shape[0]),
    }


def _masked(error, mask, keep):
    """Errors of kept (or, with keep False, excluded) elements; others become -1."""
    return error if mask is None else np.where(mask != keep, error, -1.0)


def compare_observable(context, name, row, betse_h, cells_h, betse_f, cells_f, pairs):
    kind = context["quantities"][row["tolerance"]]["kind"]
    axes = context["axes"][name]
    times = context["times"]
    ions, owner = context["ions"], context["owner"]
    rows = [p[0] for p in pairs], [p[1] for p in pairs]
    b, c = betse_h[rows[0]], cells_h[rows[1]]
    absolute, relative = errors(b, c)
    mask = None  # True marks an element excluded from judging
    if row.get("exclude") == RING:
        mask = _ring_mask(betse_h.shape[1:], *context["ring"])
        excluded = {
            "rule": RING,
            "grid_shape": list(context["ring"][1]),
            "sites": int(context["ring"][0].size),
            "elements": int(mask.sum()),
        }
        absolute_all, relative_all = absolute, relative
        absolute, relative = _masked(absolute, mask, True), _masked(relative, mask, True)

    def when(k):
        return {
            "elapsed_s": pairs[k][2],
            "betse_sample": pairs[k][0],
            "cells_sample": pairs[k][1],
        }

    history = {
        "max_abs": _worst(absolute, b, c, axes, ions, owner, when),
        "max_rel": _worst(relative, b, c, axes, ions, owner, when),
    }
    result = {"units": context["units"][name], "tolerance": row["tolerance"], "kind": kind}
    if not row.get("judged", True):
        result["judged"] = False
    result["history"] = history
    if mask is not None:
        excluded["history"] = {
            "max_abs": _worst(_masked(absolute_all, mask, False), b, c, axes, ions, owner, when),
            "max_rel": _worst(_masked(relative_all, mask, False), b, c, axes, ions, owner, when),
        }
    worst = {"abs": absolute.max(), "rel": relative.max()}[kind]
    if betse_f is not None:
        fa_all, fr_all = errors(betse_f, cells_f)
        fa, fr = _masked(fa_all, mask, True), _masked(fr_all, mask, True)
        final_at = {"elapsed_s": times["final"]}
        result["final"] = {
            "final_array": row.get("final"),
            "max_abs": {**_worst(fa, betse_f, cells_f, axes, ions, owner, None), **final_at},
            "max_rel": {**_worst(fr, betse_f, cells_f, axes, ions, owner, None), **final_at},
        }
        if mask is not None:
            excluded["final"] = {
                key: {**_worst(_masked(e, mask, False), betse_f, cells_f, axes, ions, owner, None)}
                | final_at
                for key, e in (("max_abs", fa_all), ("max_rel", fr_all))
            }
        worst = max(worst, {"abs": fa.max(), "rel": fr.max()}[kind])
        series = np.concatenate([betse_h, betse_f[None]], axis=0)
        final_errors = (fa, fr)
    else:
        series = betse_h
        final_errors = None
    full_series = series
    if mask is not None:
        series = series[:, ~mask]  # the judged elements' own change
        result["excluded"] = excluded
    result["dynamic_range"] = dynamic_range(series, kind)
    measure = result["dynamic_range"][
        "max_relative_temporal_change" if kind == "rel" else "max_temporal_change"
    ]
    result["worst_error_in_tolerance_kind"] = float(worst)
    result["classes"] = {}
    for label, values in context["classes"].items():
        tolerance = resolve_tolerance(values[row["tolerance"]], context["phase"])
        if isinstance(tolerance, dict):
            result["classes"][label] = _by_ion_class(
                context, name, axes, kind, tolerance, (absolute, relative), final_errors,
                full_series, mask,
            )  # fmt: skip
            continue
        result["classes"][label] = {
            "tolerance": tolerance,
            "pass": bool(worst <= tolerance),
            "flat": bool(measure <= tolerance),
        }
    return result


def _by_ion_class(context, name, axes, kind, tolerance, history, final, series, mask):
    """Verdict of one class whose tolerance names a value per ion."""
    ions = context["ions"]
    if "ions" not in axes or not ions or set(tolerance["by_ion"]) != set(ions):
        raise Refusal(f"{name}: per-ion tolerances need an ions axis and every case ion {ions}")
    axis = axes.index("ions")
    pick = 0 if kind == "abs" else 1
    worst = _per_ion(history[pick], axis + 1)
    if final is not None:
        worst = np.maximum(worst, _per_ion(final[pick], axis))
    change = _relative_change(series)[pick]
    if mask is not None:
        change = np.where(mask, -1.0, change)
    measure = _per_ion(change, axis)
    rows = {}
    for i, ion in enumerate(ions):
        limit = tolerance["by_ion"][ion]
        rows[ion] = {
            "worst": float(worst[i]),
            "tolerance": limit,
            "pass": bool(worst[i] <= limit),
            "flat": bool(measure[i] <= limit),
        }
    return {
        "tolerance": tolerance,
        "pass": all(r["pass"] for r in rows.values()),
        "flat": all(r["flat"] for r in rows.values()),
        "by_ion": rows,
    }


def absent_observable(context, name, row, betse_h, betse_f):
    """A reported-only observable that the Cells result does not provide."""
    kind = context["quantities"][row["tolerance"]]["kind"]
    series = betse_h if betse_f is None else np.concatenate([betse_h, betse_f[None]], axis=0)
    span = dynamic_range(series, kind)
    measure = span["max_relative_temporal_change" if kind == "rel" else "max_temporal_change"]
    classes = {}
    for label, values in context["classes"].items():
        tolerance = resolve_tolerance(values[row["tolerance"]], context["phase"])
        classes[label] = {"tolerance": tolerance, "flat": bool(measure <= _smallest(tolerance))}
    return {
        "units": context["units"][name],
        "tolerance": row["tolerance"],
        "kind": kind,
        "judged": False,
        "absent_in_cells": True,
        "dynamic_range": span,
        "classes": classes,
    }


def cells_only(context, entries, data, declared):
    """Report diag_* arrays of the Cells result: no BETSE pairing, never judged."""
    present = sorted(k for k in data["cells_history"] if k.startswith(DIAG_PREFIX))
    report = {}
    for entry, row in entries.items():
        for name in present if entry == DIAG_ALL else [entry]:
            if name not in data["cells_history"]:
                report[name] = {"judged": False, "absent_in_cells": True}
                continue
            series = np.asarray(data["cells_history"][name], dtype=np.float64)
            final_name = name.removesuffix("_time")
            final = data["cells_final"].get(final_name)
            if final is not None and final.shape == series.shape[1:]:
                series = np.concatenate([series, np.asarray(final, np.float64)[None]], axis=0)
            else:
                final_name = None
            out = {
                "judged": False,
                "cells_only": True,
                "shape": list(data["cells_history"][name].shape),
                "final_array": final_name,
                "samples_match_elapsed": len(data["cells_history"][name])
                == len(declared["elapsed_after_update_s"]),
                "finite": bool(np.all(np.isfinite(series))),
            }
            if out["finite"] and series.size:
                kind = context["quantities"].get(row.get("tolerance"), {}).get("kind", "abs")
                out["dynamic_range"] = dynamic_range(series, kind)
                if row.get("tolerance"):
                    measure = out["dynamic_range"][
                        "max_relative_temporal_change" if kind == "rel" else "max_temporal_change"
                    ]
                    out["classes"] = {}
                    for label, values in context["classes"].items():
                        tolerance = resolve_tolerance(values[row["tolerance"]], context["phase"])
                        out["classes"][label] = {
                            "tolerance": tolerance,
                            "flat": bool(measure <= _smallest(tolerance)),
                        }
            report[name] = out
    return report


# ............................................................ comparison


def _phase_inputs(phase, betse_dir, betse, layout_dir, layout, protocol):
    if phase not in betse.get("time", {}):
        raise Refusal(f"{phase}: absent from the BETSE extraction")
    declared = layout.get("phases", {}).get(phase)
    if not declared:
        raise Refusal(f"{phase}: absent from the Cells comparison manifest")
    names = {"history": f"{phase}_history.npz", "final": f"{phase}_final.npz"}
    for name in names.values():
        if not (layout_dir / name).is_file():
            raise Refusal(f"{phase}: Cells layout lacks {name}")
    data = {
        "betse_history": _npz(betse_dir / names["history"]),
        "betse_final": _npz(betse_dir / names["final"]),
        "cells_history": _npz(layout_dir / names["history"]),
        "cells_final": _npz(layout_dir / names["final"]),
    }
    times = betse["time"][phase]
    pairs = align(
        times["elapsed_after_update_s"],
        declared.get("elapsed_after_update_s", []),
        protocol["time_alignment_atol_s"],
    )
    if len(pairs) < int(protocol.get("min_common_samples", 1)):
        raise Refusal(f"{phase}: {len(pairs)} common elapsed times (no comparison possible)")
    final_b, final_c = times.get("final_state_elapsed_s"), declared.get("final_elapsed_s")
    if protocol.get("compare_final", True):
        if final_b is None or final_c is None:
            raise Refusal(f"{phase}: a final elapsed time is missing")
        if abs(float(final_b) - float(final_c)) > protocol["time_alignment_atol_s"]:
            raise Refusal(f"{phase}: final elapsed times differ (BETSE {final_b}, Cells {final_c})")
    return data, pairs, times, declared


def _check_series(phase, name, row, data, betse_arrays, layout):
    history_b, history_c = data["betse_history"], data["cells_history"]
    for label, arrays in (("BETSE", history_b), ("Cells", history_c)):
        if name not in arrays:
            if label == "Cells" and not row.get("judged", True):
                return False  # reported-only and not provided by this Cells result
            raise Refusal(f"{phase}/{name}: missing on the {label} side")
    meta = betse_arrays[f"{phase}_history.npz"]["arrays"][name]
    if meta.get("aliased_samples") or f"{phase}/{name}" in layout.get("aliased", []):
        raise Refusal(f"{phase}/{name}: aliased series (samples share one array)")
    if history_b[name].shape[1:] != history_c[name].shape[1:]:
        raise Refusal(
            f"{phase}/{name}: shape mismatch {history_b[name].shape} vs {history_c[name].shape}"
        )
    if not np.all(np.isfinite(history_b[name])):
        raise Refusal(f"{phase}/{name}: non-finite BETSE reference values")
    final = row.get("final")
    if final:
        for label, arrays in (("BETSE", data["betse_final"]), ("Cells", data["cells_final"])):
            if final not in arrays:
                raise Refusal(f"{phase}/{final}: missing on the {label} side")
        if data["betse_final"][final].shape != data["cells_final"][final].shape:
            raise Refusal(f"{phase}/{final}: final shape mismatch")
        if data["betse_final"][final].shape != history_b[name].shape[1:]:
            raise Refusal(f"{phase}/{final}: final shape differs from the history samples")
        if not np.all(np.isfinite(data["betse_final"][final])):
            raise Refusal(f"{phase}/{final}: non-finite BETSE reference values")
    return True


def run_comparison(betse_path, cells_path, protocol_path):
    """Comparison record (verdict pass/fail/refused); never raises Refusal."""
    record = {
        "kind": KIND,
        "created_utc": utc_now(),
        "comparator": {"path": str(Path(__file__).resolve()), "sha256": sha256_file(__file__)},
        "refusals": [],
    }
    try:
        protocol, protocol_sha = load_protocol(protocol_path)
        record["protocol"] = {
            "path": str(Path(protocol_path).resolve()),
            "sha256": protocol_sha,
            "id": protocol.get("id"),
            "verdict_class": protocol["verdict_class"],
            "content": protocol,
        }
        betse_dir, betse = load_betse(betse_path)
        geometry_sha = betse["files"]["geometry.npz"]["sha256"]
        record["betse"] = {
            "extract": str(betse_dir),
            "manifest_sha256": sha256_file(betse_dir / "manifest.json"),
            "geometry_sha256": geometry_sha,
            "case": betse.get("source_run", {}).get("case"),
            "run": betse.get("source_run", {}).get("directory"),
        }
        layout_dir, layout = load_layout(cells_path, protocol_sha, geometry_sha)
        record["cells"] = {
            "directory": str(layout_dir),
            "manifest_sha256": sha256_file(layout_dir / LAYOUT_MANIFEST),
            "files": {
                p.name: sha256_file(p) for p in sorted(layout_dir.glob("*.npz")) if p.is_file()
            },
            "provenance": layout["provenance"],
        }
        geometry = _npz(betse_dir / "geometry.npz")
        paired = {k: v for k, v in protocol["observables"].items() if k in SUPPORTED}
        diagnostics = {k: v for k, v in protocol["observables"].items() if k not in SUPPORTED}
        context = {
            "quantities": protocol["tolerance_quantities"],
            "classes": protocol["tolerance_classes"],
            "ions": betse.get("ions", {}).get("order"),
            "owner": geometry.get("mem_to_cells"),
        }
        if any(row.get("exclude") == RING for row in paired.values()):
            context["ring"] = grid_boundary_ring(geometry)
        phases = {}
        for phase in protocol["phases"]:
            data, pairs, times, declared = _phase_inputs(
                phase, betse_dir, betse, layout_dir, layout, protocol
            )
            arrays = betse["files"]
            present = {
                name: _check_series(phase, name, row, data, arrays, layout)
                for name, row in paired.items()
            }
            context["phase"] = phase
            context["axes"] = {
                name: arrays[f"{phase}_history.npz"]["arrays"][name]["axes"][1:] for name in paired
            }
            context["units"] = {
                name: arrays[f"{phase}_history.npz"]["arrays"][name]["units"] for name in paired
            }
            context["times"] = {"final": times.get("final_state_elapsed_s")}
            observables = {}
            for name, row in paired.items():
                final = row.get("final") if protocol.get("compare_final", True) else None
                betse_final = data["betse_final"][final] if final else None
                if not present[name]:
                    observables[name] = absent_observable(
                        context, name, row, data["betse_history"][name], betse_final
                    )
                    continue
                observables[name] = compare_observable(
                    context,
                    name,
                    row,
                    data["betse_history"][name],
                    data["cells_history"][name],
                    betse_final,
                    data["cells_final"][final] if final else None,
                    pairs,
                )
            phases[phase] = {
                "betse_samples": len(times["elapsed_after_update_s"]),
                "cells_samples": len(declared["elapsed_after_update_s"]),
                "common_samples": len(pairs),
                "common_elapsed_s": [pairs[0][2], pairs[-1][2]],
                "final_elapsed_s": times.get("final_state_elapsed_s"),
                "observables": observables,
            }
            if diagnostics:
                phases[phase]["cells_only"] = cells_only(context, diagnostics, data, declared)
        record["phases"] = phases
        judged = [
            obs
            for phase in phases.values()
            for obs in phase["observables"].values()
            if obs.get("judged", True)
        ]
        record["classes"] = {
            label: "pass" if all(obs["classes"][label]["pass"] for obs in judged) else "fail"
            for label in protocol["tolerance_classes"]
        }
        record["verdict"] = record["classes"][protocol["verdict_class"]]
    except Refusal as refusal:
        record["refusals"].append(str(refusal))
        record["verdict"] = "refused"
    except Exception as error:  # a comparator defect: keep the evidence, judge nothing
        record["error"] = {"type": type(error).__name__, "message": str(error)}
        record["verdict"] = "error"
    return record


def json_safe(value):
    """Non-finite floats (e.g. an infinite relative error) as strings for strict JSON."""
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    return value


def _tolerance_text(cls):
    if "by_ion" not in cls:
        return f"{cls['tolerance']:.3g}"
    return ", ".join(
        f"{ion} {row['worst']:.3g} of {row['tolerance']:.3g}{'' if row['pass'] else ' FAIL'}"
        for ion, row in cls["by_ion"].items()
    )


def summarize(record):
    """Short human-readable digest of a comparison record."""
    summary = {
        "verdict": record["verdict"],
        "refusals": record["refusals"],
        "protocol": record.get("protocol", {}).get("id"),
        "protocol_sha256": record.get("protocol", {}).get("sha256"),
        "verdict_class": record.get("protocol", {}).get("verdict_class"),
        "classes": record.get("classes"),
        "betse_case": record.get("betse", {}).get("case"),
        "cells": record.get("cells", {}).get("directory"),
        "phases": {},
        "flat_in_verdict_class": [],
    }
    label = summary["verdict_class"]
    for phase, row in record.get("phases", {}).items():
        lines = {}
        for name, obs in row["observables"].items():
            cls = obs["classes"][label]
            change = f"{obs['dynamic_range']['max_temporal_change']:.3g} {obs['units']}"
            flat = " (FLAT)" if cls["flat"] else ""
            if cls["flat"]:
                summary["flat_in_verdict_class"].append(f"{phase}/{name}")
            if obs.get("absent_in_cells"):
                lines[name] = "reported-only: absent from the Cells result; reference change "
                lines[name] += change + flat
                continue
            worst = obs["history"]["max_abs" if obs["kind"] == "abs" else "max_rel"]
            where = (
                f"history max at t={worst['elapsed_s']:.6g} s {worst['labels']}"
                if worst["value"]
                else "history identical"
            )
            lines[name] = (
                f"{'pass' if cls['pass'] else 'FAIL'}: worst {obs['kind']} error "
                f"{obs['worst_error_in_tolerance_kind']:.3g} (tol {_tolerance_text(cls)}); "
                f"{where}; reference change {change}{flat}"
            )
            if not obs.get("judged", True):
                lines[name] = "reported-only, " + lines[name]
            if "excluded" in obs:
                ring = obs["excluded"]["history"]["max_abs" if obs["kind"] == "abs" else "max_rel"]
                lines[name] += (
                    f"; excluded {obs['excluded']['sites']} ring sites "
                    f"(their worst {obs['kind']} error {ring['value']:.3g})"
                )
        summary["phases"][phase] = {"common_samples": row["common_samples"], "observables": lines}
        for name, diag in row.get("cells_only", {}).items():
            span = diag.get("dynamic_range")
            lines[name] = (
                "cells-only: absent"
                if diag.get("absent_in_cells")
                else f"cells-only: shape {diag['shape']}, finite {diag['finite']}"
                + (f", range [{span['value_min']:.4g}, {span['value_max']:.4g}]" if span else "")
            )
    return summary


def write_outputs(record, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    record["comparator"]["provenance"] = _RUN.git_provenance(
        [Path(__file__)], out / "git-dirty.diff"
    )
    _RUN.write_json(out / "result.json", json_safe(record))
    _RUN.write_json(out / "summary.json", json_safe(summarize(record)))
    return {"pass": 0, "fail": 1, "refused": 2}.get(record["verdict"], 3)


# ............................................................ layout writer and self-test


def write_layout(directory, phases, *, protocol_sha256, betse_geometry_sha256, provenance):
    """Write a Cells result in the comparison layout.

    ``phases`` maps phase -> {"elapsed_after_update_s": [...], "final_elapsed_s": t,
    "history": {observable: array}, "final": {final array: array}}.
    """
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    manifest = {
        "kind": LAYOUT_KIND,
        "created_utc": utc_now(),
        "protocol_sha256": protocol_sha256,
        "betse_geometry_sha256": betse_geometry_sha256,
        "provenance": provenance,
        "phases": {},
        "files": {},
    }
    for phase, row in phases.items():
        for part in ("history", "final"):
            name = f"{phase}_{part}.npz"
            with (directory / name).open("xb") as stream:
                np.savez(stream, **{k: np.asarray(v) for k, v in row[part].items()})
            manifest["files"][name] = sha256_file(directory / name)
        manifest["phases"][phase] = {
            "elapsed_after_update_s": [float(t) for t in row["elapsed_after_update_s"]],
            "final_elapsed_s": float(row["final_elapsed_s"]),
        }
    _RUN.write_json(directory / LAYOUT_MANIFEST, manifest)
    return manifest


def layout_from_betse(betse_dir, betse, protocol, perturbation=None):
    """The BETSE extraction's own observables as comparison-layout phases (optionally perturbed)."""
    phases = {}
    for phase in protocol["phases"]:
        history = _npz(Path(betse_dir) / f"{phase}_history.npz")
        final = _npz(Path(betse_dir) / f"{phase}_final.npz")
        phases[phase] = {
            "elapsed_after_update_s": betse["time"][phase]["elapsed_after_update_s"],
            "final_elapsed_s": betse["time"][phase]["final_state_elapsed_s"],
            "history": {
                name: history[name].copy() for name in protocol["observables"] if name in SUPPORTED
            },
            "final": {
                row["final"]: final[row["final"]].copy()
                for name, row in protocol["observables"].items()
                if name in SUPPORTED and row.get("final")
            },
        }
    if perturbation:
        part = "final" if perturbation["observable"] in SUPPORTED.values() else "history"
        array = phases[perturbation["phase"]][part][perturbation["observable"]]
        index = tuple(perturbation["index"])
        array[index] = perturbation["new_value"]
    return phases


def _perturbation(betse_dir, betse, protocol, args):
    phase, name = args.perturb_phase, args.perturb_observable
    if name not in protocol["observables"]:
        raise Refusal(f"perturbed observable {name} is not compared by the protocol")
    history = _npz(Path(betse_dir) / f"{phase}_history.npz")[name]
    sample = history.shape[0] // 2 if args.perturb_sample is None else args.perturb_sample
    shape = history.shape[1:]
    element = (
        tuple(int(i) for i in np.unravel_index(int(np.prod(shape)) // 2, shape))
        if args.perturb_element is None
        else tuple(args.perturb_element)
    )
    row = protocol["observables"][name]
    kind = protocol["tolerance_quantities"][row["tolerance"]]["kind"]
    tolerance = resolve_tolerance(
        protocol["tolerance_classes"][protocol["verdict_class"]][row["tolerance"]], phase
    )
    old = float(history[(sample, *element)])
    delta = args.perturb_multiple * tolerance * (abs(old) if kind == "rel" and old else 1.0)
    return {
        "phase": phase,
        "observable": name,
        "index": [sample, *element],
        "element": list(element),
        "elapsed_s": betse["time"][phase]["elapsed_after_update_s"][sample],
        "old_value": old,
        "new_value": old + delta,
        "delta": delta,
        "multiple_of_tolerance": args.perturb_multiple,
        "tolerance": tolerance,
        "kind": kind,
    }


def cmd_self_compare(args):
    """Identity comparison (must pass with zero error) and one perturbed copy (must fail)."""
    out = _RUN.resolve_out(args.out)
    out.mkdir(parents=True, exist_ok=False)
    protocol, protocol_sha = load_protocol(args.protocol)
    betse_dir, betse = load_betse(args.betse)
    geometry_sha = betse["files"]["geometry.npz"]["sha256"]
    provenance = {
        "producer": "cells_betse_compare.py self-compare (BETSE extraction rewritten in layout)",
        "betse_extract": str(betse_dir),
        "betse_manifest_sha256": sha256_file(betse_dir / "manifest.json"),
    }
    perturbation = _perturbation(betse_dir, betse, protocol, args)
    outcomes = {}
    for label, change in (("identity", None), ("perturbed", perturbation)):
        layout = out / label / "cells-layout"
        write_layout(
            layout,
            layout_from_betse(betse_dir, betse, protocol, change),
            protocol_sha256=protocol_sha,
            betse_geometry_sha256=geometry_sha,
            provenance={**provenance, "perturbation": change},
        )
        record = run_comparison(betse_dir, layout, args.protocol)
        write_outputs(record, out / label / "comparison")
        outcomes[label] = record
    checks = _self_checks(outcomes, perturbation)
    report = {
        "kind": "cells.betse_comparator_selftest@1",
        "created_utc": utc_now(),
        "betse_extract": str(betse_dir),
        "protocol": {"path": str(Path(args.protocol).resolve()), "sha256": protocol_sha},
        "perturbation": perturbation,
        "checks": checks,
        "pass": all(checks.values()),
    }
    _RUN.write_json(out / "selftest.json", report)
    print(json.dumps({"pass": report["pass"], "checks": checks}, indent=2))
    return 0 if report["pass"] else 1


def _self_checks(outcomes, perturbation):
    identity, perturbed = outcomes["identity"], outcomes["perturbed"]

    def observables(record):
        for phase, row in record.get("phases", {}).items():
            for name, obs in row["observables"].items():
                yield phase, name, obs

    zero = all(
        obs["history"]["max_abs"]["value"] == 0.0
        and obs["history"]["max_rel"]["value"] == 0.0
        and obs.get("final", {}).get("max_abs", {}).get("value", 0.0) == 0.0
        for _, _, obs in observables(identity)
    )
    target = perturbed.get("phases", {}).get(perturbation["phase"], {})
    obs = target.get("observables", {}).get(perturbation["observable"], {})
    worst = obs.get("history", {}).get("max_abs", {})
    others_clean = all(
        o["history"]["max_abs"]["value"] == 0.0
        for phase, name, o in observables(perturbed)
        if (phase, name) != (perturbation["phase"], perturbation["observable"])
    )
    label = perturbed.get("protocol", {}).get("verdict_class")
    return {
        "identity_passes_every_class": identity["verdict"] == "pass"
        and all(v == "pass" for v in identity.get("classes", {}).values()),
        "identity_errors_exactly_zero": zero,
        "perturbed_fails": perturbed["verdict"] == "fail",
        "perturbed_observable_fails": bool(obs) and not obs["classes"][label]["pass"],
        "located_at_perturbed_element": worst.get("element") == perturbation["element"],
        "located_at_perturbed_time": worst.get("elapsed_s") == perturbation["elapsed_s"],
        "error_equals_delta": bool(worst)
        and math.isclose(worst["value"], abs(perturbation["delta"]), rel_tol=1e-9),
        "other_observables_untouched": others_clean,
    }


def cmd_compare(args):
    record = run_comparison(args.betse, args.cells, args.protocol)
    status = write_outputs(record, _RUN.resolve_out(args.out))
    print(json.dumps(summarize(record), indent=2))
    return status


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    compare = sub.add_parser("compare", help="judge a Cells result against a BETSE case")
    compare.add_argument("--betse", required=True, help="BETSE case or extraction directory")
    compare.add_argument("--cells", required=True, help="Cells result in the comparison layout")
    compare.add_argument("--protocol", required=True)
    compare.add_argument("--out", required=True, help="fresh output directory")
    compare.set_defaults(func=cmd_compare)
    selftest = sub.add_parser("self-compare", help="identity and perturbed-copy self-test")
    selftest.add_argument("--betse", required=True)
    selftest.add_argument("--protocol", required=True)
    selftest.add_argument("--out", required=True)
    selftest.add_argument("--perturb-phase", default="sim", choices=PHASES)
    selftest.add_argument("--perturb-observable", default="vm_time", choices=sorted(SUPPORTED))
    selftest.add_argument("--perturb-sample", type=int, help="BETSE sample (default: middle)")
    selftest.add_argument("--perturb-element", type=int, nargs="+", help="default: middle")
    selftest.add_argument("--perturb-multiple", type=float, default=10.0)
    selftest.set_defaults(func=cmd_self_compare)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Refusal as refusal:
        print(json.dumps({"verdict": "refused", "refusals": [str(refusal)]}))
        return 2


if __name__ == "__main__":
    sys.exit(main())
