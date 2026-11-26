"""Reading the engine's role set (FORMAT.md, cells.model.assembly_lineages@1, 17 November 2026).

The engine writes run bundles for the lineage roles, group JSONs for the multi-bundle
roles, and probe.json/probe.npz pairs for the probes. Each probe echoes its registered
inputs as ``input_*``, and arrays of both forms are named ``<form>.<array>``, with form
``pair_consistent`` or ``single_event``. This module maps that layout onto the plain
arrays the references read. It reads files only: nothing here imports or runs the engine.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .records import MissingRecord, RecordFormatError, load_bundle

FORM_TAGS = {"pair-consistent": "pair_consistent", "single-event": "single_event"}


def has(path, name: str) -> bool:
    return (Path(path) / name).is_file()


def load_json(path, name: str) -> dict:
    p = Path(path) / name
    if not p.is_file():
        raise MissingRecord(f"{p} is missing")
    return json.loads(p.read_text())


def load_engine_probe(path) -> tuple[dict, dict]:
    """probe.json and probe.npz; both must exist, and the npz must have the declared SHA-256."""
    p = Path(path)
    missing = [f for f in ("probe.json", "probe.npz") if not (p / f).is_file()]
    if missing:
        raise MissingRecord(f"probe {p} lacks {missing}")
    meta = json.loads((p / "probe.json").read_text())
    declared = meta.get("arrays_sha256")
    if declared is None:
        raise MissingRecord(f"{p}/probe.json lacks arrays_sha256")
    actual = hashlib.sha256((p / "probe.npz").read_bytes()).hexdigest()
    if actual != declared:
        raise RecordFormatError(f"{p}/probe.npz has SHA-256 {actual}, probe.json declares {declared}")
    with np.load(p / "probe.npz", allow_pickle=False) as npz:
        arrays = {k: npz[k] for k in npz.files}
    return meta, arrays


def need(arrays: dict, names, where) -> list[np.ndarray]:
    absent = [n for n in names if n not in arrays]
    if absent:
        raise MissingRecord(f"{where} lacks {absent}")
    return [np.asarray(arrays[n]) for n in names]


def members(path, group_file: str, key: str) -> dict:
    """A group JSON's members, by name, in their declared order."""
    g = load_json(path, group_file)
    if key not in g or not isinstance(g[key], dict):
        raise MissingRecord(f"{Path(path) / group_file} lacks {key!r}")
    return g[key]


def ensemble_paths(path) -> list[str]:
    m = members(path, "beta0_ensemble.json", "members")
    return [m[k] for k in sorted(m, key=lambda v: int(v))]


def ensemble_design_used(path) -> dict | None:
    """The design file the engine side copied into the ensemble's folder, if any."""
    p = Path(path) / "beta0_ensemble_design.json"
    return json.loads(p.read_text()) if p.is_file() else None


def branch_paths(path) -> list[str]:
    m = members(path, "branches.json", "branches")
    return [m[k] for k in sorted(m, key=lambda v: int(v))]


def batched_lane0(path) -> str:
    lanes = members(path, "batched.json", "lanes")
    if "lane0" not in lanes:
        raise MissingRecord(f"{path}/batched.json names no lane0")
    return lanes["lane0"]


def restart_cases(path) -> tuple[str, dict]:
    g = load_json(path, "restart.json")
    if "cases" not in g or "uninterrupted" not in g:
        raise MissingRecord(f"{path}/restart.json lacks cases or uninterrupted")
    return g["uninterrupted"], g["cases"]


def kernel_tables(path) -> tuple[dict, dict]:
    """Registered inputs and, per form, join, leave and leave_up (leave of type i at n + e_i)."""
    meta, arr = load_engine_probe(path)
    inputs = dict(zip(("beta", "states", "k_join", "k_leave", "rho"),
                      need(arr, ("input_beta", "input_states", "input_k_join", "input_k_leave", "input_rho"),
                           f"{path}/probe.npz")))
    tables = {}
    for form, tag in FORM_TAGS.items():
        j, lv, up = need(arr, (f"{tag}.join_rate", f"{tag}.leave_rate", f"{tag}.leave_rate_after_join"),
                         f"{path}/probe.npz")
        tables[form] = dict(join=j, leave=lv, leave_up=up)
    return inputs, tables


def closed_world_tables(path) -> dict:
    """Per registered world: its echoed inputs and, per form, the held-supply join and leave."""
    worlds = members(path, "closed_world.json", "worlds")
    out = {}
    for name, wpath in worlds.items():
        meta, arr = load_engine_probe(wpath)
        inputs = dict(zip(("states", "M", "theta", "rho", "k_join", "k_leave", "beta"),
                          need(arr, ("input_states", "input_M", "input_theta", "input_rho", "input_k_join",
                                     "input_k_leave", "input_beta"), f"{wpath}/probe.npz")))
        forms = {}
        for form, tag in FORM_TAGS.items():
            j, lv = need(arr, (f"{tag}.join_rate", f"{tag}.leave_rate"), f"{wpath}/probe.npz")
            forms[form] = dict(join=j, leave=lv)
        out[name] = dict(inputs=inputs, forms=forms, declared=meta.get("declared"))
    return out


def partition_splits(path) -> dict:
    """Per rule: parents [n, G] (the one registered parent repeated) and first-daughter splits."""
    rules = members(path, "partition_probe.json", "rules")
    out = {}
    for rule, rpath in rules.items():
        meta, arr = load_engine_probe(rpath)
        parent, first, second = need(arr, ("parent", "first", "second"), f"{rpath}/probe.npz")
        if first.ndim != 2 or first.shape[1] != parent.size:
            raise RecordFormatError(f"{rpath}: first has shape {first.shape}, parent {parent.shape}")
        if not np.array_equal(first + second, np.tile(parent, (first.shape[0], 1))):
            raise RecordFormatError(f"{rpath}: first + second differs from the parent")
        out[rule] = dict(parents=np.tile(parent, (first.shape[0], 1)), splits=first)
    return out


def observer_outputs(path) -> dict:
    meta, arr = load_engine_probe(path)
    P, D, H = need(arr, ("input_probe_parent", "input_probe_daughter", "similarity"), f"{path}/probe.npz")
    return dict(parents=P, daughters=D, H=H, inherited=arr.get("inherited"))


def f12_outputs(path) -> dict:
    p = Path(path)
    if not (p / "f12_table.npz").is_file():
        raise MissingRecord(f"{p}/f12_table.npz is missing")
    meta = load_json(path, "f12_table.json")
    with np.load(p / "f12_table.npz", allow_pickle=False) as npz:
        arrays = {k: npz[k] for k in npz.files}
    seqs, f12 = need(arrays, ("sequences", "f12"), f"{p}/f12_table.npz")
    return dict(sequences=seqs, f12=f12, certified_at=arrays.get("certified_at"), meta=meta)


def is_engine_group(path, group_file: str) -> bool:
    return has(path, group_file)


def load(path):
    return load_bundle(path)
