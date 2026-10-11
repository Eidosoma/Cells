"""NUM-009 data binding and explicit full/reduced coordinates; no ODE imports."""

import copy
import hashlib
import json
import math
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from tests import reference_finite_extracellular as spec

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/finite_extracellular_trajectories_v1.json"
PANEL_SHA256 = "81e7e68a1821a57dc9e8b96889dfcc0d9b4eca514785f4aac9dce32a77aff397"
F, R, QF = spec.ion.F, spec.ion.R, spec.ion.CHARGE_PER_FMOL
FIELD_NAMES = tuple(spec.State.__dataclass_fields__)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@dataclass(frozen=True)
class Layout:
    n: int
    s: int
    k: int
    e: int

    def __post_init__(self):
        for name in ("n", "s", "k", "e"):
            value = getattr(self, name)
            if type(value) is not int or value < (1 if name in ("n", "s") else 0):
                raise ValueError("Invalid finite-world layout extent")

    @cached_property
    def shapes(self):
        return (
            (self.n, self.s),
            (self.n, self.s),
            (self.n,),
            (self.n,),
            (self.k, 2),
            (self.k,),
            (self.e,),
            (self.e, self.s),
            (self.e,),
            (self.s,),
        )

    @cached_property
    def slices(self):
        edges = np.r_[0, np.cumsum([math.prod(s) for s in self.shapes])]
        return {
            name: slice(int(a), int(b))
            for name, a, b in zip(FIELD_NAMES, edges[:-1], edges[1:], strict=True)
        }

    @property
    def size(self):
        return self.slices[FIELD_NAMES[-1]].stop

    @property
    def reduced_size(self):
        return self.size - self.s

    @property
    def amount_count(self):
        return self.n * self.s

    def split(self, value):
        a = np.asarray(value, dtype=float)
        if not a.ndim or a.shape[-1] != self.size:
            raise ValueError("Invalid complete finite-world state shape")
        return {
            key: a[..., self.slices[key]].reshape(*a.shape[:-1], *shape)
            for key, shape in zip(FIELD_NAMES, self.shapes, strict=True)
        }

    def pack(self, state):
        return np.concatenate(
            [np.asarray(getattr(state, name), dtype=float).reshape(-1) for name in FIELD_NAMES]
        )

    def state(self, value):
        parts = self.split(value)
        if np.asarray(value).ndim != 1:
            raise ValueError("A physical state requires one flat vector")
        return spec.State(
            **{
                key: tuple(tuple(float(x) for x in row) for row in a)
                if a.ndim == 2
                else tuple(float(x) for x in a)
                for key, a in parts.items()
            }
        )


@dataclass(frozen=True)
class Control:
    time_s: float
    value: spec.graph.Control

    def __post_init__(self):
        spec.ion.number(self.time_s, "control time", nonnegative=True)
        if type(self.value) is not spec.graph.Control:
            raise ValueError("Require a complete finite-world control")


@dataclass(frozen=True)
class Case:
    id: str
    world: spec.World
    horizon_s: float
    controls: tuple[Control, ...]

    def __post_init__(self):
        spec.ion.identifier(self.id)
        spec.ion.number(self.horizon_s, "horizon", positive=True)
        if self.horizon_s > 0.3 or type(self.world) is not spec.World:
            raise ValueError("NUM-009 requires a finite world and horizon <= 0.3 seconds")
        if type(self.controls) is not tuple or not self.controls:
            raise ValueError("Require immutable nonempty controls")
        if any(type(c) is not Control for c in self.controls):
            raise ValueError("Require timed finite-world controls")
        ts = [c.time_s for c in self.controls]
        if (
            ts[0] != 0
            or ts[-1] > self.horizon_s
            or any(b <= a for a, b in zip(ts[:-1], ts[1:], strict=True))
        ):
            raise ValueError("Controls must start at zero and increase within the horizon")
        for c in self.controls:
            spec.graph.validate_control(self.world, c.value)

    @cached_property
    def layout(self):
        w = self.world
        return Layout(len(w.cells), len(w.species_ids), len(w.channels), len(w.junctions))

    @property
    def size(self):
        return self.layout.size

    @cached_property
    def initial_amount(self):
        a = np.asarray([c.initial_amount_fmol for c in self.world.cells])
        a.flags.writeable = False
        return a

    @cached_property
    def outside_initial(self):
        a = np.asarray(self.world.extracellular.initial_amount_fmol)
        a.flags.writeable = False
        return a

    @property
    def endpoints(self):
        return self.world.endpoints

    @property
    def channel_cells(self):
        return self.world.channel_cells

    def control_at(self, time):
        spec.ion.number(time, "query time", nonnegative=True)
        if time > self.horizon_s:
            raise ValueError("Control query outside horizon")
        return self.controls[
            np.searchsorted([c.time_s for c in self.controls], time, side="right") - 1
        ]

    def definition(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def resolve_control(world, row):
    groups = ("leak", "pump", "channel", "junction")
    spec.ion.fields(row, {"time_s", "overrides", *groups}, "control snapshot")
    spec.ion.fields(row["overrides"], groups, "control overrides")
    owners = (
        world.cell_ids,
        world.cell_ids,
        tuple(c.id for c in world.channels),
        tuple(e.id for e in world.junctions),
    )
    for name, ids in zip(groups, owners, strict=True):
        spec.channel.fraction(row[name], "group control")
        overrides = row["overrides"][name]
        if type(overrides) is not dict or not set(overrides) <= set(ids):
            raise ValueError("Overrides must use existing owner IDs")
    leak = []
    for cell in world.cell_ids:
        overrides = row["overrides"]["leak"].get(cell, {})
        if type(overrides) is not dict or not set(overrides) <= set(world.species_ids):
            raise ValueError("Unknown leak species ID")
        leak.append(tuple(overrides.get(s, row["leak"]) for s in world.species_ids))
    value = spec.graph.Control(
        tuple(leak),
        *(
            tuple(row["overrides"][group].get(i, row[group]) for i in ids)
            for group, ids in zip(groups[1:], owners[1:], strict=True)
        ),
    )
    spec.graph.validate_control(world, value)
    return Control(row["time_s"], value)


def resolve_cases(plan, physical):
    definitions = {a["id"]: a["definition"] for a in physical["assemblies"]}
    cases = []
    for item in plan["cases"]:
        spec.ion.fields(item, {"id", "assembly", "profile", "outside_override"}, "case")
        raw = copy.deepcopy(definitions[item["assembly"]])
        if item["outside_override"] is not None:
            raw["extracellular"] = copy.deepcopy(
                plan["outside_overrides"][item["outside_override"]]
            )
        world = spec.resolve(raw)
        profile = plan["profiles"][item["profile"]]
        spec.ion.fields(profile, {"horizon_s", "controls"}, "profile")
        cases.append(
            Case(
                item["id"],
                world,
                profile["horizon_s"],
                tuple(resolve_control(world, row) for row in profile["controls"]),
            )
        )
    if len(cases) != 14 or len({c.id for c in cases}) != 14:
        raise ValueError("Require fourteen unique frozen cases")
    return tuple(cases)


def load_panel():
    if sha(PANEL) != PANEL_SHA256:
        raise ValueError("Frozen NUM-009 panel changed")
    plan = spec.ion.load_json(PANEL)
    for name, digest in plan["inherited_sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Inherited source changed: {name}")
    source = ROOT / plan["definitions_source"]
    if sha(source) != plan["definitions_source_sha256"]:
        raise ValueError("Frozen SPEC-008 definitions changed")
    release = spec.ion.load_json(ROOT / "runs/core-008-2026-09-10/release-audit.json")
    current = {
        str(p.relative_to(ROOT / "src/cells")): sha(p)
        for p in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    if current != release["source_hashes"]:
        raise ValueError("NUM-009 must leave production unchanged")
    for name, digest in release["implementation_files_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Accepted implementation dependency changed: {name}")
    return plan, resolve_cases(plan, spec.ion.load_json(source))


def layout(case):
    w = case["world"]
    return Layout(len(w["cells"]), len(w["species_ids"]), len(w["channels"]), len(w["junctions"]))


def initial_state(case):
    result = case.layout.pack(spec.initial_state(case.world))
    parts = case.layout.split(result)
    parts["amount"][:] = 0
    parts["extracellular_amount"][:] = 0
    return result


def physical_state(case, value):
    result = np.asarray(value, dtype=float).copy()
    parts = case.layout.split(result)
    parts["amount"] += case.initial_amount
    parts["extracellular_amount"] += case.outside_initial
    return case.layout.state(result)


def expand(case, reduced):
    """Linear coordinate map, not repair of an independently supplied outside."""
    a = np.asarray(reduced, dtype=float)
    if not a.ndim or a.shape[-1] != case.layout.reduced_size or not np.isfinite(a).all():
        raise ValueError("Invalid reduced coordinate vector")
    inside = a[..., : case.layout.amount_count].reshape(*a.shape[:-1], case.layout.n, case.layout.s)
    return np.concatenate((a, -np.sum(inside, axis=-2)), axis=-1)
