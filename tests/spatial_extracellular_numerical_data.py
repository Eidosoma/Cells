"""NUM-010 immutable bindings, complete coordinate layout and declared sampling.

No production or integrator imports. Physical definitions are copied literally
from SPEC-009; generated line cases are explicit frozen data, not runtime repairs.
"""

import copy
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType

import numpy as np

from tests import reference_spatial_extracellular as spec

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/spatial_extracellular_trajectories_v1.json"
PANEL_SHA256 = "642528abeba897ea25d6650074fa979721d95bf8f7519466a16270e41914f194"
INHERITED_SHA256 = {
    "configs/reference/spatial_extracellular_v1.json": (
        "8b644559899961d0d54233e13eb9b1c867fc4ab5454e48b3b3e2c63e0791273d"
    ),
    "docs/SPATIAL_EXTRACELLULAR_SPEC.md": (
        "a45052bff09400cd7b26c065e198b33ba71617a88fce4c25817535b2b04a5a9d"
    ),
    "reports/spec-009-design-check.json": (
        "116942ff1a27bf2d80690a85536409d94588f11fd28c347cfb9352eebdb188a5"
    ),
    "tests/reference_spatial_extracellular.py": (
        "9a688b7a266f7376c758de4f999e396f647501f56dc4fe51f3e35b79700cc886"
    ),
    "tests/reference_multispecies.py": (
        "c9f388fdb45b26ccc2a501907b39fbc33b8ef405941fd4165d676f963d0094f6"
    ),
    "runs/core-009-2026-09-10/acceptance-02/verification.json": (
        "247e2bd8f00cb58736e2b6e7ef2bf0c0855742fa8e929e6067ef861bc2ad3b92"
    ),
}
F, R, A, QF = spec.F, spec.R, spec.A, spec.A * spec.F


@dataclass(frozen=True)
class Layout:
    shapes: object
    slices: object
    size: int
    amount_count: int

    @classmethod
    def from_geometry(cls, g):
        n, s, m, e = len(g.ids), len(g.z), len(g.membrane_pairs), len(g.face_pairs)
        shapes = {
            "amount": (n, s),
            "membrane_transfer": (m, s),
            "face_transfer": (e, s),
            "membrane_dissipation": (m,),
            "face_dissipation": (e,),
        }
        slices, at = {}, 0
        for key, shape in shapes.items():
            count = int(np.prod(shape))
            slices[key] = slice(at, at + count)
            at += count
        return cls(MappingProxyType(shapes), MappingProxyType(slices), at, n * s)

    def split(self, state):
        array = np.asarray(state)
        if array.ndim < 1 or array.shape[-1] != self.size:
            raise ValueError("Incomplete spatial state")
        return {
            key: array[..., self.slices[key]].reshape(*array.shape[:-1], *shape)
            for key, shape in self.shapes.items()
        }

    def pack(self, values):
        if set(values) != set(self.shapes):
            raise ValueError("All five coordinate fields are required")
        result = np.empty(self.size)
        for key, shape in self.shapes.items():
            array = np.asarray(values[key])
            if array.shape != shape:
                raise ValueError("Invalid spatial coordinate extent")
            result[self.slices[key]] = array.ravel()
        return result


@dataclass(frozen=True)
class Control:
    time_s: float
    availability: tuple


@dataclass(frozen=True)
class Case:
    id: str
    raw: dict
    g: spec.Geometry
    layout: Layout
    horizon_s: float
    controls: tuple
    outside: tuple

    @property
    def size(self):
        return self.layout.size

    def definition(self):
        return copy.deepcopy(self.raw)

    def control_at(self, time):
        if not np.isfinite(time) or not 0 <= time <= self.horizon_s:
            raise ValueError("Control query outside the declared horizon")
        index = np.searchsorted([c.time_s for c in self.controls], time, side="right") - 1
        return self.controls[int(index)]


def resolve(raw):
    raw = copy.deepcopy(raw)
    spec.ion.fields(
        raw,
        {"id", "source_case", "world", "horizon_s", "controls", "analytic_kind", "mesh_parameters"},
        "numerical case",
    )
    name = spec.ion.identifier(raw["id"])
    horizon = spec.ion.number(raw["horizon_s"], "horizon", positive=True)
    g = spec.resolve(raw["world"])
    ids = [m["id"] for m in raw["world"]["membranes"]]
    controls = []
    for c in raw["controls"]:
        spec.ion.fields(c, {"time_s", "membrane_availability"}, "control snapshot")
        time = spec.ion.number(c["time_s"], "control time", nonnegative=True)
        if time > horizon or set(c["membrane_availability"]) != set(ids):
            raise ValueError("Every membrane needs a bound control within the horizon")
        values = tuple(
            spec.ion.number(c["membrane_availability"][i], "availability", nonnegative=True)
            for i in ids
        )
        if any(v > 1 for v in values):
            raise ValueError("Availability outside [0,1]")
        controls.append(Control(time, values))
    if (
        not controls
        or controls[0].time_s != 0
        or any(b.time_s <= a.time_s for a, b in zip(controls[:-1], controls[1:], strict=True))
    ):
        raise ValueError("Controls must begin at zero and be strictly increasing")
    if raw["analytic_kind"] not in {None, "binary_relaxation", "cosine_line"}:
        raise ValueError("Unknown analytic comparison")
    outside = tuple(
        i for i, c in enumerate(raw["world"]["compartments"]) if c["kind"] == "extracellular"
    )
    return Case(name, raw, g, Layout.from_geometry(g), horizon, tuple(controls), outside)


def load_panel():
    if file_sha(PANEL) != PANEL_SHA256 or any(
        file_sha(ROOT / path) != expected for path, expected in INHERITED_SHA256.items()
    ):
        raise ValueError("Frozen spatial protocol or inherited evidence changed")
    production = json.loads(
        (ROOT / "runs/core-009-2026-09-10/acceptance-02/verification.json").read_text()
    )
    if any(
        file_sha(ROOT / "src/cells" / p) != value
        for p, value in production["source_hashes"].items()
    ):
        raise ValueError("Accepted production changed during the reference-only slice")
    plan = json.loads(PANEL.read_text())
    if plan["schema"] != "cells.spatial_extracellular_trajectories@1":
        raise ValueError("Unsupported numerical panel")
    inherited = json.loads((ROOT / "configs/reference/spatial_extracellular_v1.json").read_text())
    source = {c["id"]: c for c in inherited["cases"]}
    for c in plan["cases"]:
        if c["source_case"] is not None and c["world"] != source[c["source_case"]]:
            raise ValueError("An inherited physical definition changed")
    cases = tuple(resolve(c) for c in plan["cases"])
    if len({c.id for c in cases}) != len(cases) or len(cases) != 14:
        raise ValueError("The registered panel requires fourteen unique cases")
    return plan, cases


def initial_state(case):
    return np.zeros(case.size, dtype=np.float64)


def candidate_grid(case, dt, *, start=0.0, end=None):
    spec.ion.number(dt, "candidate step", positive=True)
    end = case.horizon_s if end is None else end
    if not 0 <= start <= end <= case.horizon_s:
        raise ValueError("Invalid integration interval")
    if np.ceil(case.horizon_s / dt) > 100000:
        raise ValueError("Candidate step budget exceeded")
    grid = np.unique(
        np.r_[
            np.arange(int(np.ceil(case.horizon_s / dt))) * dt,
            [c.time_s for c in case.controls],
            start,
            end,
        ]
    )
    return grid[(grid >= start) & (grid <= end)]


def observations(case, count=201):
    cuts = np.unique([c.time_s for c in case.controls] + [case.horizon_s])
    extra = [
        left + (right - left) * f
        for left, right in zip(cuts[:-1], cuts[1:], strict=True)
        for f in (0.25, 0.5, 0.75)
    ]
    return np.unique(np.r_[np.linspace(0, case.horizon_s, count), cuts, extra])


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()
