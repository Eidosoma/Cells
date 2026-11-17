"""Run bundles: reading an engine run's saved records, with loud failure.

Format (GARD_DESIGN §5.1-5.2 and §5.4, with the array names the engine side declared
on 17 November 2026). One directory per run holds:

- ``world.json``: the world record, written once and shared by the runs of one world.
- ``run.json``: the run record. It holds the law's form, the stream identity, the SSA
  and ledger conventions, the mode, and a table of every array.
- ``records.npz``: the arrays. The row base is the start row, then two rows per fission:
  the parent before the split, then the followed daughter.
- ``manifest.json``: written last; a bundle without it is incomplete and refused.

Only ``adapt_world`` and ``adapt_run`` know the JSON key layout. ``WORLD_FIELDS`` and
``RUN_FIELDS`` are this module's canonical guess. When the engine's container is fixed,
the lead passes its key names and only these two tables change. Every reference reads
the canonical views.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np


class MissingRecord(KeyError):
    """A record, array or declared field a reference needs is absent."""

    def __str__(self) -> str:  # KeyError quotes its argument; keep the message readable
        return str(self.args[0]) if self.args else "missing record"


class RecordFormatError(ValueError):
    """A record exists but has the wrong shape, dtype or encoding."""


ROW_ARRAYS = ("row_time", "row_event", "assembly_count", "joined_total", "left_total",
              "discarded_total", "exchange_heat_kT", "fission_work_kT", "discarded_free_energy_kT",
              "log_weight", "ledger_residual_kT", "occupant", "generation")
FISSION_ARRAYS = ("fission_time", "fission_slot", "fission_parent", "fission_daughters",
                  "fission_followed", "fission_split", "fission_similarity", "fission_partition_counter")
EVENT_ARRAYS = ("event_time", "event_channel", "events_per_growth")
DIAGNOSTIC_ARRAYS = ("event_uniforms", "partition_uniforms", "continuation_uniform")
INTEGER_ARRAYS = ("row_event", "assembly_count", "joined_total", "left_total", "discarded_total",
                  "occupant", "generation", "fission_slot", "fission_parent", "fission_daughters",
                  "fission_followed", "fission_split", "fission_partition_counter",
                  "event_channel", "events_per_growth")

WORLD_FIELDS = {
    "types": "types",
    "rho": "supply.rho",
    "supply_kind": "supply.kind",
    "k_join": "constants.k_join",
    "k_leave": "constants.k_leave",
    "beta": "beta",
    "founder": "founder",
    "fission_mass": "rules.fission.mass",
    "event_guard": "rules.fission.event_guard",
    "partition": "rules.fission.partition",
    "partition_fraction": "rules.fission.fraction",
    "partition_p": "rules.fission.p",
    "continuation": "rules.continuation.rule",
    "boundary": "rules.boundary",
    "units": "units",
}
WORLD_OPTIONAL = ("event_guard", "partition_fraction", "partition_p", "boundary", "units")

RUN_FIELDS = {
    "world_id": "world_id",
    "founder": "founder",
    "form": "law.form",
    "law_id": "law.id",
    "energy_role": "law.energy_role",
    "check_verdict": "law.check_verdict",
    "mode": "mode",
    "stream": "stream",
    "ssa_convention": "ssa_convention",
    "ledger_conventions": "ledger_conventions",
    "revision": "revision",
    "end_status": "end_status",
    "channels": "channels",
    "time": "time",
}
RUN_OPTIONAL = ("energy_role", "check_verdict", "ledger_conventions", "end_status", "revision",
                "ssa_convention", "channels", "time")


def _dig(obj: dict, dotted: str):
    cur = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise KeyError(dotted)
        cur = cur[part]
    return cur


@dataclass
class WorldView:
    """The canonical view of a world record that every reference reads."""

    world_id: str
    types: list
    beta: np.ndarray
    rho: np.ndarray
    k_join: np.ndarray
    k_leave: np.ndarray
    founder: np.ndarray
    fission_mass: int
    partition: str
    partition_fraction: float | None
    partition_p: float | None
    continuation: str
    event_guard: int | None
    boundary: str
    units: dict | None = None
    raw: dict = field(repr=False, default_factory=dict)

    @property
    def n_types(self) -> int:
        return self.beta.shape[0]

    @property
    def type_names(self) -> list:
        """Type names, whether the record lists names or objects carrying a name."""
        out = []
        for t in self.types:
            out.append(t.get("name", t.get("id")) if isinstance(t, dict) else t)
        return out


@dataclass
class RunView:
    world_id: str
    founder: str
    form: str
    law_id: str
    mode: str
    stream: object
    ssa_convention: dict | None
    energy_role: str | None
    check_verdict: object
    ledger_conventions: dict | None
    revision: str | None
    end_status: object
    channels: dict | None = None
    time: dict | None = None
    raw: dict = field(repr=False, default_factory=dict)


def adapt_world(raw: dict, source: str = "world.json") -> WorldView:
    """Map a raw world record onto the canonical view; list every missing field at once."""
    values, missing = {}, []
    for name, dotted in WORLD_FIELDS.items():
        try:
            values[name] = _dig(raw, dotted)
        except KeyError:
            if name in WORLD_OPTIONAL:
                values[name] = None
            else:
                missing.append(f"{source}:{dotted}")
    if missing:
        raise MissingRecord(f"world record lacks {missing}")
    if values["supply_kind"] != "held":
        raise RecordFormatError(f"{source}: supply kind {values['supply_kind']!r}; the lineage references "
                                "need a held supply")
    beta = np.asarray(values["beta"], dtype=np.float64)
    G = beta.shape[0]
    if beta.shape != (G, G):
        raise RecordFormatError(f"{source}: beta is not square")
    def per_type(v, name):
        a = np.asarray(v, dtype=np.float64)
        a = np.full(G, float(a)) if a.ndim == 0 else a
        if a.shape != (G,):
            raise RecordFormatError(f"{source}: {name} has shape {a.shape}, expected ({G},)")
        return a
    founder = np.asarray(values["founder"])
    if founder.shape != (G,) or not np.issubdtype(founder.dtype, np.integer):
        raise RecordFormatError(f"{source}: founder must be {G} integer counts")
    if len(values["types"]) != G:
        raise RecordFormatError(f"{source}: {len(values['types'])} types but beta is {G}x{G}")
    partition = str(values["partition"])
    if partition not in ("binomial", "exact_fraction"):
        raise RecordFormatError(f"{source}: unknown partition {partition!r}")
    if partition == "exact_fraction" and values["partition_fraction"] is None:
        raise MissingRecord(f"{source}: exact_fraction partition without its fraction")
    if partition == "binomial" and values["partition_p"] is None:
        raise MissingRecord(f"{source}: binomial partition without its p")
    return WorldView(
        world_id=str(raw.get("id", "")), types=list(values["types"]), beta=beta,
        rho=per_type(values["rho"], "rho"), k_join=per_type(values["k_join"], "k_join"),
        k_leave=per_type(values["k_leave"], "k_leave"), founder=founder.astype(np.int64),
        fission_mass=int(values["fission_mass"]), partition=partition,
        partition_fraction=None if values["partition_fraction"] is None else float(values["partition_fraction"]),
        partition_p=None if values["partition_p"] is None else float(values["partition_p"]),
        continuation=str(values["continuation"]),
        event_guard=None if values["event_guard"] is None else int(values["event_guard"]),
        boundary=str(values["boundary"] or "last_molecule_stays"), units=values["units"], raw=raw)


def adapt_run(raw: dict, source: str = "run.json") -> RunView:
    values, missing = {}, []
    for name, dotted in RUN_FIELDS.items():
        try:
            values[name] = _dig(raw, dotted)
        except KeyError:
            if name in RUN_OPTIONAL:
                values[name] = None
            else:
                missing.append(f"{source}:{dotted}")
    if missing:
        raise MissingRecord(f"run record lacks {missing}")
    return RunView(raw=raw, **values)


@dataclass
class Bundle:
    """One run's saved records."""

    path: str
    world_raw: dict
    run_raw: dict
    arrays: dict
    _world: WorldView | None = field(default=None, repr=False)
    _run: RunView | None = field(default=None, repr=False)

    @property
    def world(self) -> WorldView:
        if self._world is None:
            self._world = adapt_world(self.world_raw, f"{self.path}/world.json")
        return self._world

    @property
    def run(self) -> RunView:
        if self._run is None:
            self._run = adapt_run(self.run_raw, f"{self.path}/run.json")
        return self._run

    def require(self, *names: str) -> list[np.ndarray]:
        """Return the named arrays; raise one MissingRecord listing all that are absent."""
        missing = [n for n in names if n not in self.arrays]
        if missing:
            raise MissingRecord(f"{self.path}/records.npz lacks {missing}")
        out = []
        for n in names:
            a = np.asarray(self.arrays[n])
            if n in INTEGER_ARRAYS and not np.issubdtype(a.dtype, np.integer):
                raise RecordFormatError(f"{self.path}: {n} must be integer, found {a.dtype}")
            out.append(a)
        return out

    def optional(self, name: str):
        return None if name not in self.arrays else np.asarray(self.arrays[name])


def load_bundle(path: str | os.PathLike) -> Bundle:
    """Read a run bundle; refuse an incomplete one."""
    p = Path(path)
    missing = [f for f in ("world.json", "run.json", "records.npz", "manifest.json") if not (p / f).is_file()]
    if missing:
        raise MissingRecord(f"bundle {p} lacks {missing} (manifest.json is written last; "
                            "without it the bundle is incomplete)")
    world = json.loads((p / "world.json").read_text())
    run = json.loads((p / "run.json").read_text())
    with np.load(p / "records.npz", allow_pickle=False) as npz:
        arrays = {k: npz[k] for k in npz.files}
    table = run.get("arrays")
    if isinstance(table, dict):
        absent = [k for k in table if k not in arrays]
        if absent:
            raise MissingRecord(f"{p}/run.json declares arrays absent from records.npz: {absent}")
        for k, spec in table.items():
            axes = spec.get("axes") if isinstance(spec, dict) else None
            if axes is not None and len(axes) != np.ndim(arrays[k]):
                raise RecordFormatError(f"{p}: {k} has {np.ndim(arrays[k])} axes, declared {axes}")
    return Bundle(str(p), world, run, arrays)


def canonical_digest(obj: dict) -> str:
    data = json.dumps(obj, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(data).hexdigest()


def write_bundle(path: str | os.PathLike, world: dict, run: dict, arrays: dict) -> Path:
    """Write a bundle in the canonical layout (used by the host oracle and the tests)."""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=False)
    (p / "world.json").write_text(json.dumps(world, sort_keys=True, indent=1))
    (p / "run.json").write_text(json.dumps(run, sort_keys=True, indent=1))
    np.savez(p / "records.npz", **arrays)
    (p / "manifest.json").write_text(json.dumps(
        {"files": ["world.json", "run.json", "records.npz"], "complete": True}, sort_keys=True))
    return p


def in_memory_bundle(world: dict, run: dict, arrays: dict, path: str = "<memory>") -> Bundle:
    return Bundle(path, world, run, dict(arrays))
