"""Bounded one-cell composition without changing either component's physics."""

import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path

from cells.assembly.spec import AssemblyError
from cells.assembly_cell import MODEL_ID
from cells.assembly_pool.spec import parse_spec as parse_pool
from cells.core.specs import KineticFiniteExtracellularSpec
from cells.core.specs import parse_spec as parse_ionic


@dataclass(frozen=True)
class CoupledSpec:
    pool: object
    ionic: object
    inactive_availability: float
    active_availability: float
    window_ticks: int

    def to_dict(self):
        return {
            "model": MODEL_ID,
            "pool": self.pool.to_dict(),
            "ionic": self.ionic.to_dict(),
            "coupling": {
                "law": "root_component_has_cycle@1",
                "inactive_availability": self.inactive_availability,
                "active_availability": self.active_availability,
            },
            "window_ticks": self.window_ticks,
        }

    @property
    def fingerprint(self):
        return hashlib.sha256(json.dumps(self.to_dict(), sort_keys=True).encode()).hexdigest()

    @property
    def ticks(self):
        return round(self.pool.end_time_s / self.ionic.execution.dt)

    @property
    def working_bytes(self):
        from cells.models.kinetic_finite_extracellular import working_size

        return self.pool.working_bytes + self.pool.worlds * 64 * working_size(self.ionic)


def tick_at(spec, until):
    if type(until) not in (float, int) or not math.isfinite(until) or until < 0:
        raise AssemblyError("Invalid coupled observation time")
    ratio = until / spec.ionic.execution.dt
    tick = round(ratio)
    if abs(ratio - tick) > 1e-9 or not 0 <= tick <= spec.ticks:
        raise AssemblyError("Coupled observations must lie on the registered ionic grid")
    return tick


def parse_spec(data):
    if not isinstance(data, dict) or set(data) != {
        "model",
        "pool",
        "ionic",
        "coupling",
        "window_ticks",
    }:
        raise AssemblyError("Require complete assembly-cell definition")
    if data["model"] != MODEL_ID:
        raise AssemblyError("Unsupported assembly-cell identity")
    pool, ionic = parse_pool(data["pool"]), parse_ionic(data["ionic"])
    if (
        not isinstance(ionic.model, KineticFiniteExtracellularSpec)
        or len(ionic.model.cells) != 1
        or len(ionic.model.channels) != 1
        or ionic.model.junctions
    ):
        raise AssemblyError("Initial composition requires one kinetic finite cell and one channel")
    if len(ionic.experiment.changes) != 1 or ionic.experiment.changes[0].time != 0:
        raise AssemblyError("Initial assembly-cell composition requires constant external controls")
    if pool.end_time_s != ionic.experiment.end_time or pool.recording != "summary":
        raise AssemblyError("Components require the same horizon and summary assembly recording")
    if (
        not 1 <= pool.worlds <= 4096
        or not 0 < ionic.execution.dt <= 1e-4
        or not ionic.execution.jit
        or ionic.execution.solver != "rk4"
    ):
        raise AssemblyError("Require <=4096 worlds, compiled RK4, and ionic dt <= 0.0001 s")
    coupling = data["coupling"]
    if (
        not isinstance(coupling, dict)
        or set(coupling) != {"law", "inactive_availability", "active_availability"}
        or coupling["law"] != "root_component_has_cycle@1"
    ):
        raise AssemblyError("Require explicit cycle-dependent channel availability")
    values = [coupling[k] for k in ("inactive_availability", "active_availability")]
    if any(type(v) not in (float, int) or not math.isfinite(v) or not 0 <= v <= 1 for v in values):
        raise AssemblyError("Channel availability must be finite in [0,1]")
    window = data["window_ticks"]
    if type(window) is not int or not 1 <= window <= 256:
        raise AssemblyError("window_ticks must be an integer in [1,256]")
    spec = CoupledSpec(pool, ionic, *map(float, values), window)
    tick_at(spec, pool.end_time_s)
    for time in ionic.experiment.observation_times:
        tick_at(spec, time)
    if (
        spec.ticks > ionic.execution.max_steps
        or spec.ticks > 1000000
        or spec.working_bytes > 2 * 1024**3
    ):
        raise AssemblyError("Coupled tick/working-memory budget exceeded")
    from cells.core.schedule import control_values
    from cells.models.kinetic_finite_extracellular import check_steps

    check_steps(ionic, [ionic.execution.dt], control_values(ionic, [0.0]))
    return spec


def load_spec(path):
    return parse_spec(json.loads(Path(path).read_text()))
