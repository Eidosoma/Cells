"""The canonical run bundle the harness reads, and its validation.

An engine layout would need an adapter onto these canonical names. None is planned: the
protocol's judge consumes the references through ``REFERENCES_USAGE.md`` (the lead,
17 November 2026).

**A bundle** is one directory with ``run.json``, ``records.npz`` and ``manifest.json``, the
manifest written last. A bundle without its manifest is refused.

``run.json``:
- ``world``: ``W1``, ``W2`` or ``W3`` (the inputs' worlds);
- ``solver`` and ``dt_s``;
- ``constants``: the SI block (optional; when present it must be the exact SI values);
- ``nodes`` (W1) and ``species``: the column orders of the arrays below.

``records.npz`` (every array optional unless its row needs it):
- ``time_s`` [T];
- ``node_amount_fmol`` [T, N] (W1), ``V_m_V`` [T] and ``cell_amount_fmol`` [T, S] (W2);
- ``supply_fmol`` [T, S]: the bath's cumulative supply to the tissue, positive out of the bath;
- ``event_time_s`` [E], ``dose_fmol`` [E, S], ``dG_b_pJ`` [E] and ``charge_C`` [E];
- ``K_pJ`` [T]: the operator's reconciliation term at the record times.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

RUN_KEYS = ("world", "solver", "dt_s")
WORLDS = ("W1", "W2", "W3")
ARRAYS = ("time_s", "node_amount_fmol", "V_m_V", "cell_amount_fmol", "supply_fmol",
          "event_time_s", "dose_fmol", "dG_b_pJ", "charge_C", "K_pJ")


class BundleError(Exception):
    """A missing or malformed bundle: the harness's exit status 2."""


def write_bundle(path, run: dict, arrays: dict) -> Path:
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    unknown = set(arrays) - set(ARRAYS)
    if unknown:
        raise ValueError(f"unknown arrays {sorted(unknown)}")
    (path / "run.json").write_text(json.dumps(run, indent=1) + "\n")
    np.savez(path / "records.npz", **{k: np.asarray(v) for k, v in arrays.items()})
    (path / "manifest.json").write_text(json.dumps(
        {"files": ["run.json", "records.npz"], "arrays": sorted(arrays)}, indent=1) + "\n")
    return path


def read_bundle(path) -> tuple:
    """(run, arrays) of a canonical bundle; BundleError when anything is missing or malformed."""
    path = Path(path)
    if not (path / "manifest.json").is_file():
        raise BundleError(f"{path}: no manifest.json (a bundle is complete only with it)")
    for name in ("run.json", "records.npz"):
        if not (path / name).is_file():
            raise BundleError(f"{path}: missing {name}")
    try:
        run = json.loads((path / "run.json").read_text())
    except json.JSONDecodeError as exc:
        raise BundleError(f"{path}/run.json: {exc}") from exc
    missing = [k for k in RUN_KEYS if k not in run]
    if missing:
        raise BundleError(f"{path}/run.json lacks {missing}")
    if run["world"] not in WORLDS:
        raise BundleError(f"{path}: unknown world {run['world']!r}")
    with np.load(path / "records.npz") as npz:
        arrays = {k: np.asarray(npz[k]) for k in npz.files}
    unknown = set(arrays) - set(ARRAYS)
    if unknown:
        raise BundleError(f"{path}: unknown arrays {sorted(unknown)}")
    return run, arrays


def need(arrays: dict, name: str, where) -> np.ndarray:
    if name not in arrays:
        raise BundleError(f"{where}: missing array {name}")
    a = arrays[name]
    if not np.all(np.isfinite(a)):
        raise BundleError(f"{where}: {name} is not finite")
    return a


def columns(run: dict, key: str, where) -> list:
    cols = run.get(key)
    if not isinstance(cols, list) or not cols:
        raise BundleError(f"{where}: run.json lacks the column order {key!r}")
    return cols
