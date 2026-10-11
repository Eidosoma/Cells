"""Explicit finite material and new kinetic assumptions; the paper model is separate."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from cells.assembly.graph import EDGES, RING, TOPOLOGY_ID
from cells.assembly.spec import AssemblyError
from cells.assembly.spec import parse_spec as parse_baseline
from cells.assembly_pool import MODEL_ID

AVOGADRO = 6.02214076e23
FULL_BONDS = (1 << 30) - 1


@dataclass(frozen=True)
class PoolSpec:
    model: str = MODEL_ID
    topology: str = TOPOLOGY_ID
    initial_nodes: tuple[int, ...] = RING
    initial_bond_indices: tuple[int, ...] | None = None
    root_node: int = 10
    initial_free_trimers: int = 50
    pool_volume_L: float = 5e-15
    k_on_M_inv_s: float = 1e7
    k_close_s_inv: float = 100.0
    k_off_s_inv: float = 10.0
    k_fragment_dissolve_s_inv: float = 1.0
    seed: int = 20260920
    world_id_start: int = 0
    worlds: int = 64
    end_time_s: float = 30.0
    max_events_per_world: int = 100000
    event_chunk_size: int = 128
    recording: str = "summary"
    max_output_bytes: int = 256 * 1024**2
    max_wall_seconds: float = 600.0

    def to_dict(self):
        result = asdict(self)
        result["initial_nodes"] = list(self.initial_nodes)
        result["initial_bond_indices"] = (
            None if self.initial_bond_indices is None else list(self.initial_bond_indices)
        )
        return result

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    @property
    def initial_mask(self):
        return sum(1 << i for i in self.initial_nodes)

    @property
    def initial_bonds(self):
        return sum(1 << i for i in self.initial_bond_indices)

    @property
    def total_trimers(self):
        return self.initial_free_trimers + len(self.initial_nodes)

    @property
    def working_bytes(self):
        return self.worlds * (16896 + 32 * self.event_chunk_size) + 32 * 1024**2

    @property
    def output_bound(self):
        size = self.worlds * 2048 + 16 * 1024**2
        if self.recording == "events":
            size += (self.max_events_per_world + self.event_chunk_size) * self.worlds * 32
            size += (self.max_events_per_world // self.event_chunk_size + 2) * 2048
        return size


def parse_spec(data):
    if not isinstance(data, dict) or set(data) - {f.name for f in fields(PoolSpec)}:
        raise AssemblyError("Unknown finite-bond assembly definition fields")
    values = asdict(PoolSpec()) | data
    if values["model"] != MODEL_ID or values["topology"] != TOPOLOGY_ID:
        raise AssemblyError("Unsupported finite-bond assembly model/topology")
    if (
        type(values["initial_free_trimers"]) is not int
        or not 0 <= values["initial_free_trimers"] <= 10**8
    ):
        raise AssemblyError("initial_free_trimers must be an integer in [0, 100000000]")
    for name in ("pool_volume_L", "k_close_s_inv", "k_fragment_dissolve_s_inv"):
        value = values[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise AssemblyError(f"{name} must be finite and nonnegative")
        values[name] = float(value)
    if not 1e-24 <= values["pool_volume_L"] <= 1:
        raise AssemblyError("pool_volume_L must be in [1e-24, 1] litres")
    common = {
        key: values[key]
        for key in (
            "initial_nodes",
            "root_node",
            "k_on_M_inv_s",
            "k_off_s_inv",
            "seed",
            "world_id_start",
            "worlds",
            "end_time_s",
            "max_events_per_world",
            "event_chunk_size",
            "recording",
            "max_output_bytes",
            "max_wall_seconds",
        )
    }
    # Reuse the existing strict graph/clock/recording validation at the largest
    # possible free concentration; physical pool state still stays explicit.
    common["free_trimer_M"] = (values["initial_free_trimers"] + 20) / (
        AVOGADRO * values["pool_volume_L"]
    )
    base = parse_baseline(common)
    if (
        values["k_on_M_inv_s"] > 0
        and values["k_on_M_inv_s"] / (AVOGADRO * values["pool_volume_L"]) == 0
    ):
        raise AssemblyError("Positive per-trimer association propensity underflows float64")
    if (
        max(
            values["k_close_s_inv"],
            values["k_fragment_dissolve_s_inv"] * (values["initial_free_trimers"] + 20),
        )
        > 1e12
    ):
        raise AssemblyError("Pool reaction rate exceeds the bounded clock domain")
    for name in common:
        if name != "free_trimer_M":
            values[name] = getattr(base, name)
    indices = values["initial_bond_indices"]
    if indices is None:
        nodes = set(base.initial_nodes)
        indices = [i for i, (a, b) in enumerate(EDGES) if a in nodes and b in nodes]
    if (
        not isinstance(indices, (tuple, list))
        or any(type(i) is not int or not 0 <= i < 30 for i in indices)
        or len(set(indices)) != len(indices)
    ):
        raise AssemblyError("Initial bonds must be distinct graph edge indices")
    values["initial_bond_indices"] = tuple(sorted(indices))
    spec = PoolSpec(**values)
    from cells.assembly_pool.reference import bonds_within, connected

    if bonds_within(spec.initial_mask, spec.initial_bonds) != spec.initial_bonds:
        raise AssemblyError("Initial bond has an unoccupied endpoint")
    if connected(spec.initial_mask, spec.initial_bonds, spec.root_node) != spec.initial_mask:
        raise AssemblyError("Initial bonds must connect all occupied nodes to the retained root")
    if spec.working_bytes > 2 * 1024**3 or spec.output_bound > spec.max_output_bytes:
        raise AssemblyError("Finite-bond assembly working/output budget exceeded")
    return spec


def load_spec(path):
    return parse_spec(json.loads(Path(path).read_text()))
