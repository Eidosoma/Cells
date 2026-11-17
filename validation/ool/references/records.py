"""Reading the records the harness checks: probes, runs and groups, in the references' canonical
layout.

Every record directory ends with ``manifest.json``, written last; a directory without it is
refused (status 2). Arrays are in ``*.npz`` files read with ``allow_pickle=False``. The engine's
own layout is mapped onto this one by ``engine_layout.py``, written once the family's FORMAT.md
exists; until then the stand-in (``standin.py``) writes this layout directly.

Canonical layout:
- **probe** (``kernel_probe``, ``closed_world``, ``closed_world_uncatalysed``): ``probe.json``
  with ``world``, ``conventions``, ``steps``, ``places``; ``probe.npz`` with ``input_states``
  [S, D], ``a_plus`` and ``a_minus`` [S, R].
- **run** (``ledger_run``, ``replay``, ``other_stream``, and the two runs of ``rescale_pair``):
  ``run.json`` with ``world``, ``conventions``, ``ssa`` (``tau``, ``select``), ``channels``
  (rows of step, direction, code, in fold order), ``stream`` (an identity) and
  ``initial_state``; ``records.npz`` with ``event_time``, ``event_channel``, and as the role
  needs ``event_uniforms`` [E, 2], ``row_event``, ``counts`` [rows, D], ``heat_kT``, ``work_kT``.
- **ensemble** (``wb_ensemble``): ``ensemble.json`` with ``rungs`` {M: {streams: [...]}} and
  ``ensemble.npz`` with ``observation_counts_m{M}`` [runs, times, D].
- **refusals**: ``refusals.json`` {declaration id: {refused, message}}.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from .common import MissingRecord, RecordFormatError

MANIFEST = "manifest.json"


def _dir(path) -> Path:
    p = Path(path)
    if not p.is_dir():
        raise MissingRecord(f"{p} is not a directory")
    if not (p / MANIFEST).is_file():
        raise MissingRecord(f"{p} has no {MANIFEST}; a record without its manifest is refused")
    return p


def _json(p: Path, name: str) -> dict:
    f = p / name
    if not f.is_file():
        raise MissingRecord(f"{f} is missing")
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError as exc:
        raise RecordFormatError(f"{f} is not valid JSON: {exc}") from exc


def _npz(p: Path, name: str) -> dict:
    f = p / name
    if not f.is_file():
        raise MissingRecord(f"{f} is missing")
    with np.load(f, allow_pickle=False) as z:
        return {k: z[k] for k in z.files}


def need(arrays: dict, names, where) -> list:
    absent = [n for n in names if n not in arrays]
    if absent:
        raise MissingRecord(f"{where} lacks {absent}")
    return [np.asarray(arrays[n]) for n in names]


def load_probe(path) -> tuple[dict, dict]:
    p = _dir(path)
    meta = _json(p, "probe.json")
    for key in ("world", "conventions", "steps", "places"):
        if key not in meta:
            raise MissingRecord(f"{p}/probe.json lacks {key!r}")
    return meta, _npz(p, "probe.npz")


def load_run(path) -> tuple[dict, dict]:
    p = _dir(path)
    meta = _json(p, "run.json")
    for key in ("world", "conventions", "ssa", "channels", "stream", "initial_state"):
        if key not in meta:
            raise MissingRecord(f"{p}/run.json lacks {key!r}")
    return meta, _npz(p, "records.npz")


def load_ensemble(path) -> tuple[dict, dict]:
    p = _dir(path)
    meta = _json(p, "ensemble.json")
    if "rungs" not in meta:
        raise MissingRecord(f"{p}/ensemble.json lacks 'rungs'")
    return meta, _npz(p, "ensemble.npz")


def load_refusals(path) -> dict:
    p = _dir(path)
    return _json(p, "refusals.json")


def write_manifest(p: Path, files) -> None:
    (p / MANIFEST).write_text(json.dumps({"files": sorted(files)}, indent=1))
