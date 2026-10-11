"""Strict, versioned inputs for the bounded fixed-bath assembly model."""

import hashlib
import json
import math
from dataclasses import asdict, dataclass, fields
from pathlib import Path

from cells.assembly import MODEL_ID
from cells.assembly.graph import RING, TOPOLOGY_ID, component, mask_of


class AssemblyError(ValueError):
    pass


@dataclass(frozen=True)
class AssemblySpec:
    model: str = MODEL_ID
    topology: str = TOPOLOGY_ID
    initial_nodes: tuple[int, ...] = RING
    root_node: int = 10
    free_trimer_M: float = 17e-9
    k_on_M_inv_s: float = 1e7
    k_off_s_inv: float = 10.0
    seed: int = 20260919
    world_id_start: int = 0
    worlds: int = 64
    end_time_s: float = 300.0
    max_events_per_world: int = 100000
    event_chunk_size: int = 128
    recording: str = "summary"
    max_output_bytes: int = 256 * 1024**2
    max_wall_seconds: float = 600.0

    def to_dict(self):
        result = asdict(self)
        result["initial_nodes"] = list(self.initial_nodes)
        return result

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    @property
    def initial_mask(self):
        return mask_of(self.initial_nodes)

    @property
    def working_bytes(self):
        # State, 60 event channels, bridge connectivity, traces and headroom.
        return self.worlds * (16384 + 32 * self.event_chunk_size) + 32 * 1024**2

    @property
    def output_bound(self):
        state = self.worlds * 2048 + 16 * 1024**2
        if self.recording == "events":
            # Up to one terminal/censor record per world, padded final chunk.
            state += (self.max_events_per_world + self.event_chunk_size) * self.worlds * 20
            state += (self.max_events_per_world // self.event_chunk_size + 2) * 2048
        return state


def parse_spec(data):
    if not isinstance(data, dict):
        raise AssemblyError("Assembly definition must be an object")
    known = {field.name for field in fields(AssemblySpec)}
    if set(data) - known:
        raise AssemblyError(f"Unknown assembly fields: {sorted(set(data) - known)}")
    values = AssemblySpec().to_dict() | data
    if values["model"] != MODEL_ID or values["topology"] != TOPOLOGY_ID:
        raise AssemblyError("Unsupported assembly model/topology identity")
    integer_bounds = {
        "root_node": (0, 19),
        "seed": (0, 2**32 - 1),
        "world_id_start": (0, 2**32 - 1),
        "worlds": (1, 1000000),
        "max_events_per_world": (1, 2**31 - 1),
        "event_chunk_size": (1, 4096),
        "max_output_bytes": (1024**2, 8 * 1024**3),
    }
    for name, (low, high) in integer_bounds.items():
        value = values[name]
        if type(value) is not int or not low <= value <= high:
            raise AssemblyError(f"{name} must be an integer in [{low}, {high}]")
    if values["world_id_start"] + values["worlds"] > 2**32:
        raise AssemblyError("World IDs would overflow the random stream namespace")
    for name in ("free_trimer_M", "k_on_M_inv_s", "k_off_s_inv", "end_time_s", "max_wall_seconds"):
        value = values[name]
        if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
            raise AssemblyError(f"{name} must be finite and nonnegative")
        values[name] = float(value)
    if not 0 < values["end_time_s"] <= 86400 or not 0 < values["max_wall_seconds"] <= 43200:
        raise AssemblyError("Positive horizon <= 86400 s and wall limit <= 43200 s required")
    association = values["k_on_M_inv_s"] * values["free_trimer_M"]
    if values["k_on_M_inv_s"] > 0 and values["free_trimer_M"] > 0 and association == 0:
        raise AssemblyError("Positive association propensity underflows float64")
    rate = max(association, values["k_off_s_inv"])
    if not math.isfinite(rate) or rate > 1e12:
        raise AssemblyError("Per-channel rate exceeds the bounded clock domain (1e12 /s)")
    nodes = values["initial_nodes"]
    if (
        not isinstance(nodes, (list, tuple))
        or not nodes
        or any(type(n) is not int or not 0 <= n < 20 for n in nodes)
        or len(set(nodes)) != len(nodes)
        or values["root_node"] not in nodes
    ):
        raise AssemblyError("Initial nodes must be unique graph nodes containing the root")
    values["initial_nodes"] = tuple(sorted(nodes))
    spec = AssemblySpec(**values)
    if component(spec.initial_mask, spec.root_node) != spec.initial_mask:
        raise AssemblyError("Initial assembly must be connected to the retained root")
    if spec.recording not in ("summary", "events"):
        raise AssemblyError("recording must be summary or events")
    if spec.working_bytes > 2 * 1024**3:
        raise AssemblyError("Estimated assembly working arrays exceed 2 GiB")
    if spec.output_bound > spec.max_output_bytes:
        raise AssemblyError("Estimated output exceeds max_output_bytes; reduce events/worlds")
    return spec


def load_spec(path):
    return parse_spec(json.loads(Path(path).read_text()))
