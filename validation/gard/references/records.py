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
    "guard_rule": "rules.fission.guard_rule",
    "units": "units",
}
WORLD_OPTIONAL = ("event_guard", "partition_fraction", "partition_p", "boundary", "guard_rule", "units")
ENGINE_BOUNDARY = "extinction_uncatalysed"
"""The pair-consistent form's edge rule: the last molecule leaves uncatalysed, Phi(empty) = 0."""

ENGINE_BOUNDARY_BY_FORM = {"pair-consistent": "extinction_uncatalysed", "single-event": "extinction",
                           "none": "extinction_uncatalysed"}
"""The edge rule per form, for a world that does not name one (amended 17 November 2026).
The pair-consistent leave does not count the leaving molecule, so the last molecule leaves
uncatalysed. The single-event form is the preprint's kernel: it counts the leaving
molecule, so the last molecule's leave carries 1 + beta_ii (GARD_DESIGN §2.3 and §2.5)."""

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
    "restart": "restart",
    "t_end": "t_end",
}
RUN_OPTIONAL = ("energy_role", "check_verdict", "ledger_conventions", "end_status", "revision",
                "ssa_convention", "channels", "time", "restart", "t_end")
IDENTITY_FIELDS = ("world_id", "founder", "form", "law_id", "mode", "stream", "ssa_convention", "channels",
                   "ledger_conventions", "time")
"""Canonical run fields that define what was run; replays must agree on them."""


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
    boundary_declared: bool = True
    guard_rule: str = "stop"
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
    restart: dict | None = None
    t_end: float | None = None
    raw: dict = field(repr=False, default_factory=dict)

    def identity(self) -> dict:
        """The identity fields, by canonical name (None when the run does not declare one)."""
        return {k: getattr(self, k) for k in IDENTITY_FIELDS}


def is_engine_world(raw: dict) -> bool:
    """The engine's layout (FORMAT.md): {format, id, world, derived}."""
    return isinstance(raw.get("world"), dict) and isinstance(raw.get("derived"), dict)


def adapt_world(raw: dict, source: str = "world.json", config: dict | None = None) -> WorldView:
    """Map a raw world record onto the canonical view; list every missing field at once."""
    if is_engine_world(raw):
        return adapt_engine_world(raw, source, config)
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
    if values["boundary"] is not None and values["boundary"] not in ("last_molecule_stays", "extinction",
                                                                    "extinction_uncatalysed"):
        raise RecordFormatError(f"{source}: unknown boundary rule {values['boundary']!r}")
    if values["guard_rule"] is not None and values["guard_rule"] not in ("stop", "fission"):
        raise RecordFormatError(f"{source}: unknown guard rule {values['guard_rule']!r}")
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
    K_declared = [t.get("K", t.get("transfer_constant")) for t in values["types"] if isinstance(t, dict)]
    if K_declared and all(k is not None for k in K_declared):
        K = np.asarray(K_declared, dtype=np.float64)
        ratio = per_type(values["k_join"], "k_join") / per_type(values["k_leave"], "k_leave")
        if K.shape != (G,) or np.any(np.abs(K - ratio) > 1e-12 * np.abs(ratio)):
            raise RecordFormatError(f"{source}: the types' transfer constants K disagree with k_join/k_leave")
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
        boundary=str(values["boundary"] or ENGINE_BOUNDARY), units=values["units"],
        boundary_declared=values["boundary"] is not None, guard_rule=str(values["guard_rule"] or "stop"),
        raw=raw)


def adapt_run(raw: dict, source: str = "run.json") -> RunView:
    if is_engine_run(raw):
        return adapt_engine_run(raw, source)
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


# ------------------------------------------------------------- the engine's layout
#
# FORMAT.md of the engine's probe set (17 November 2026; cells.model.assembly_lineages@1). Only
# the interface ID strings change at the engine's freeze; they are not read here.

ENGINE_SSA = {
    "tau": {"tau = -ln(u1) / a0": "neg_log_u1_over_a0"},
    "select": {"the first j with c_j > min(u2 * a0, nextafter(a0, 0))": "first_prefix_gt_u2_a0"},
    "uniform_prefix": ("u = (m + 1/2) * 2**-52, m the low 52 bits", "low52_plus_half_times_2^-52"),
    "prefix": "serial left fold in channel order",
}
"""The engine's declared SSA prose, mapped onto the oracle's tokens. Any other wording
leaves the token out, and the oracle then refuses the run."""

VERDICTS = {"passive": "passive", "driven": "refused_as_passive"}


def _need(obj, dotted: str, source: str, missing: list):
    try:
        return _dig(obj, dotted)
    except KeyError:
        missing.append(f"{source}:{dotted}")
        return None


def adapt_engine_world(raw: dict, source: str, config: dict | None) -> WorldView:
    missing: list = []
    w = raw["world"]
    d = raw["derived"]
    types = _need(d, "types", source, missing)
    k_join = _need(d, "join_rate", source, missing)
    k_leave = _need(d, "leave_rate", source, missing)
    rho = _need(w, "supply", source, missing)
    founder = _need(w, "founder", source, missing)
    size = _need(w, "fission.size", source, missing)
    rule = _need(w, "fission.partition.rule", source, missing)
    daughter = _need(w, "continuation.daughter", source, missing)
    K = _need(w, "types.transfer_constant", source, missing)
    if missing:
        raise MissingRecord(f"world record lacks {missing}")
    G = len(types)
    beta = np.asarray(w["law_data"]["catalysis_matrix"], dtype=np.float64) if "law_data" in w \
        else np.zeros((G, G))  # no rate factor: the exchange law alone (beta = 0)
    if beta.shape != (G, G):
        raise RecordFormatError(f"{source}: catalysis_matrix is {beta.shape}, {G} types declared")
    def per_type(v, name):
        a = np.asarray(v, dtype=np.float64)
        a = np.full(G, float(a)) if a.ndim == 0 else a
        if a.shape != (G,):
            raise RecordFormatError(f"{source}: {name} has shape {a.shape}, expected ({G},)")
        return a
    kj, kl, Kv = per_type(k_join, "join_rate"), per_type(k_leave, "leave_rate"), per_type(K, "transfer_constant")
    if np.any(np.abs(Kv - kj / kl) > 1e-12 * np.abs(kj / kl)):
        raise RecordFormatError(f"{source}: the types' transfer constants K disagree with k_join/k_leave")
    founder = np.asarray(founder)
    if founder.shape != (G,) or not np.issubdtype(founder.dtype, np.integer):
        raise RecordFormatError(f"{source}: founder must be {G} integer counts")
    if rule not in ("binomial", "exact_fraction"):
        raise RecordFormatError(f"{source}: unknown partition {rule!r}")
    part = w["fission"]["partition"]
    fraction = part.get("fraction")
    p = part.get("probability", part.get("p"))
    if rule == "exact_fraction" and fraction is None:
        raise MissingRecord(f"{source}: exact_fraction partition without its fraction")
    if rule == "binomial" and p is None:
        raise MissingRecord(f"{source}: binomial partition without its probability")
    guard = None
    if config is not None:
        try:
            guard = int(_dig(config, "experiment.growth_event_limit"))
        except KeyError:
            guard = None
    return WorldView(
        world_id=str(raw.get("id", "")), types=list(types), beta=beta, rho=per_type(rho, "supply"), k_join=kj,
        k_leave=kl, founder=founder.astype(np.int64), fission_mass=int(size), partition=str(rule),
        partition_fraction=None if fraction is None else float(fraction), partition_p=None if p is None else float(p),
        continuation=str(daughter), event_guard=guard, boundary=ENGINE_BOUNDARY, units=w.get("units"),
        boundary_declared=False, guard_rule="stop", raw=raw)


def is_engine_run(raw: dict) -> bool:
    return isinstance(raw.get("ssa"), dict) and isinstance(raw.get("ledger"), dict) and "world" in raw


def adapt_engine_run(raw: dict, source: str) -> RunView:
    missing: list = []
    for key in ("world", "founder", "law", "mode", "stream", "ssa", "channels", "end"):
        if key not in raw:
            missing.append(f"{source}:{key}")
    if missing:
        raise MissingRecord(f"run record lacks {missing}")
    law = raw["law"] or {}
    form = law.get("form") or "none"  # "none": the exchange law alone (beta = 0, both forms agree)
    check = law.get("check") or {}
    ssa = raw["ssa"]
    conv = {}
    if ENGINE_SSA["tau"].get(ssa.get("tau")):
        conv["tau"] = ENGINE_SSA["tau"][ssa["tau"]]
    if ENGINE_SSA["select"].get(ssa.get("channel")):
        conv["select"] = ENGINE_SSA["select"][ssa["channel"]]
    uni = str(raw["stream"].get("uniform", ""))
    if uni.startswith(ENGINE_SSA["uniform_prefix"][0]):
        conv["uniform"] = ENGINE_SSA["uniform_prefix"][1]
    if not str(ssa.get("prefix", "")).startswith(ENGINE_SSA["prefix"]):
        conv.pop("select", None)  # an unknown fold order: refuse rather than assume
    verdict = check.get("admitted_as")
    end = raw["end"] or {}
    return RunView(
        world_id=str(raw["world"]), founder=str(raw["founder"]), form=form,
        law_id=str(law.get("id") or (law.get("exchange") or {}).get("id")), mode=str(raw["mode"]),
        stream=raw["stream"], ssa_convention=conv, energy_role=law.get("energy_role"),
        check_verdict=VERDICTS.get(verdict, verdict), ledger_conventions=raw.get("ledger"),
        revision=(raw.get("source") or {}).get("revision"), end_status=end.get("status"),
        channels=raw["channels"], time=raw.get("time"), restart=None, t_end=end.get("time"), raw=raw)


@dataclass
class Bundle:
    """One run's saved records."""

    path: str
    world_raw: dict
    run_raw: dict
    arrays: dict
    config_raw: dict | None = None
    _world: WorldView | None = field(default=None, repr=False)
    _run: RunView | None = field(default=None, repr=False)

    @property
    def world(self) -> WorldView:
        if self._world is None:
            self._world = adapt_world(self.world_raw, f"{self.path}/world.json", self.config_raw)
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
    table = run.get("arrays") if isinstance(run.get("arrays"), dict) else run.get("records")
    if isinstance(table, dict):
        def in_npz(spec):
            return not isinstance(spec, dict) or spec.get("file", "records.npz") == "records.npz"
        absent = [k for k, spec in table.items()
                  if in_npz(spec) and (spec.get("array", k) if isinstance(spec, dict) else k) not in arrays]
        if absent:
            raise MissingRecord(f"{p}/run.json declares arrays absent from records.npz: {absent}")
        for k, spec in table.items():
            if not in_npz(spec):
                continue
            axes = spec.get("axes") if isinstance(spec, dict) else None
            name = spec.get("array", k) if isinstance(spec, dict) else k
            if axes is not None and len(axes) != np.ndim(arrays[name]):
                raise RecordFormatError(f"{p}: {name} has {np.ndim(arrays[name])} axes, declared {axes}")
    config = json.loads((p / "resolved_config.json").read_text()) if (p / "resolved_config.json").is_file() else None
    return Bundle(str(p), world, run, arrays, config)


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
