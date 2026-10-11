"""NUM-008 resolved inputs and explicit reference layout; no trajectory solver.

Reference arrays are cell-/edge-major, not the proposed production layout.
This module owns data binding only, never the reference or candidate equations.
"""

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from functools import cached_property
from pathlib import Path

import numpy as np

from tests import reference_physical_ionic_graph as spec

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/physical_ionic_graph_trajectories_v1.json"
PANEL_SHA256 = "d09e21f945525769aea541e668625b168586f4c29d2cd852767b301ef2d8e00f"
F, R, QF = spec.ionic.F, spec.ionic.R, spec.ionic.CHARGE_PER_FMOL
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
                raise ValueError("Invalid graph layout extent")

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
    def amount_count(self):
        return self.n * self.s

    def split(self, value):
        a = np.asarray(value, dtype=float)
        if not a.ndim or a.shape[-1] != self.size:
            raise ValueError("Invalid complete graph state shape")
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
    value: spec.Control

    def __post_init__(self):
        spec.ionic.number(self.time_s, "control time", nonnegative=True)
        if type(self.value) is not spec.Control:
            raise ValueError("Require a complete graph control")


@dataclass(frozen=True)
class Case:
    id: str
    graph: spec.Graph
    horizon_s: float
    controls: tuple[Control, ...]
    independent_cell_reduction: bool = False

    def __post_init__(self):
        spec.ionic.identifier(self.id)
        spec.ionic.number(self.horizon_s, "horizon", positive=True)
        if self.horizon_s > 0.3 or type(self.graph) is not spec.Graph:
            raise ValueError("NUM-008 requires a graph and horizon <= 0.3 seconds")
        if type(self.controls) is not tuple or not self.controls:
            raise ValueError("Require immutable nonempty controls")
        if any(type(c) is not Control for c in self.controls):
            raise ValueError("Require timed graph controls")
        ts = [c.time_s for c in self.controls]
        if (
            ts[0] != 0
            or ts[-1] > self.horizon_s
            or any(b <= a for a, b in zip(ts[:-1], ts[1:], strict=True))
        ):
            raise ValueError("Controls must start at zero and increase within the horizon")
        for c in self.controls:
            spec.validate_control(self.graph, c.value)
        if type(self.independent_cell_reduction) is not bool or (
            self.independent_cell_reduction and self.graph.junctions
        ):
            raise ValueError("Independent cell reduction requires no edges")

    @cached_property
    def layout(self):
        g = self.graph
        return Layout(len(g.cells), len(g.species_ids), len(g.channels), len(g.junctions))

    @property
    def size(self):
        return self.layout.size

    @cached_property
    def initial_amount(self):
        a = np.asarray([c.initial_amount_fmol for c in self.graph.cells])
        a.flags.writeable = False
        return a

    @cached_property
    def endpoints(self):
        return self.graph.endpoints

    @cached_property
    def channel_cells(self):
        return self.graph.channel_cells

    def control_at(self, time):
        spec.ionic.number(time, "query time", nonnegative=True)
        if time > self.horizon_s:
            raise ValueError("Control query outside horizon")
        return self.controls[
            np.searchsorted([c.time_s for c in self.controls], time, side="right") - 1
        ]

    def definition(self):
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def resolve_control(graph, row):
    groups = ("leak", "pump", "channel", "junction")
    spec.ionic.fields(row, {"time_s", "overrides", *groups}, "control snapshot")
    spec.ionic.fields(row["overrides"], groups, "control overrides")
    for name in groups:
        spec.channel.fraction(row[name], "group control")
        if type(row["overrides"][name]) is not dict:
            raise ValueError("Overrides must be ID-keyed maps")
    cells, channels, edges = (
        graph.cell_ids,
        tuple(c.channel.id for c in graph.channels),
        tuple(e.id for e in graph.junctions),
    )
    for group, ids in zip(groups, (cells, cells, channels, edges), strict=True):
        if not set(row["overrides"][group]) <= set(ids):
            raise ValueError("Unknown control owner ID")
    leak = []
    for cell in cells:
        overrides = row["overrides"]["leak"].get(cell, {})
        if type(overrides) is not dict or not set(overrides) <= set(graph.species_ids):
            raise ValueError("Unknown leak species ID")
        leak.append(tuple(overrides.get(s, row["leak"]) for s in graph.species_ids))
    value = spec.Control(
        tuple(leak),
        *(
            tuple(row["overrides"][group].get(i, row[group]) for i in ids)
            for group, ids in zip(groups[1:], (cells, channels, edges), strict=True)
        ),
    )
    spec.validate_control(graph, value)
    return Control(row["time_s"], value)


def resolve_cases(plan, physical):
    definitions = {c["id"]: c["definition"] for c in physical["cases"]}
    result = []
    for item in plan["cases"]:
        spec.ionic.fields(item, {"id", "assembly", "profile", "independent_cell_reduction"}, "case")
        graph = spec.resolve(definitions[item["assembly"]])
        profile = plan["profiles"][item["profile"]]
        spec.ionic.fields(profile, {"horizon_s", "controls"}, "profile")
        result.append(
            Case(
                item["id"],
                graph,
                profile["horizon_s"],
                tuple(resolve_control(graph, row) for row in profile["controls"]),
                item["independent_cell_reduction"],
            )
        )
    if len(result) != 12 or len({c.id for c in result}) != 12:
        raise ValueError("Require twelve unique frozen cases")
    return tuple(result)


def load_panel():
    if sha(PANEL) != PANEL_SHA256:
        raise ValueError("Frozen NUM-008 panel changed")
    plan = spec.ionic.load_json(PANEL)
    physical = ROOT / plan["physical_panel"]
    if sha(physical) != plan["physical_panel_sha256"]:
        raise ValueError("Frozen SPEC-007 panel changed")
    for name, digest in plan["inherited_sources_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Inherited source changed: {name}")
    release = spec.ionic.load_json(ROOT / "runs/core-007-2026-09-10/release-audit.json")
    production = {
        str(p.relative_to(ROOT / "src/cells")): sha(p)
        for p in sorted((ROOT / "src/cells").rglob("*.py"))
    }
    if production != release["source_hashes"]:
        raise ValueError("NUM-008 must leave production unchanged")
    for name, digest in release["implementation_files_sha256"].items():
        if sha(ROOT / name) != digest:
            raise ValueError(f"Accepted implementation dependency changed: {name}")
    return plan, resolve_cases(plan, spec.ionic.load_json(physical))


def layout(case):
    g = case["graph"]
    return Layout(
        len(g["cells"]), len(g["cells"][0]["species_ids"]), len(g["channels"]), len(g["junctions"])
    )


def initial_state(case, *, absolute=False):
    result = case.layout.pack(spec.initial_state(case.graph))
    if not absolute:
        result[: case.layout.amount_count] = 0.0
    return result


def canonical(case, value, *, absolute):
    result = np.asarray(value, dtype=float).copy()
    if absolute:
        result[..., : case.layout.amount_count] -= case.initial_amount.ravel()
    return result


def local_definition(case, index):
    """ID-bound local oracle input, usable by audit without an ODE import."""
    p = case["graph"]["cells"][index]
    binding = next(
        (c for c in case["graph"]["channels"] if c["assembly"]["cell_id"] == p["cell_id"]), None
    )
    controls = []
    slot = case["graph"]["channels"].index(binding) if binding else None
    for row in case["controls"]:
        control = row["value"]
        item = {
            "time_s": row["time_s"],
            "leak": control["leak"][index],
            "pump": control["pump"][index],
        }
        if binding:
            item["availability"] = control["channel"][slot]
        controls.append(item)
    result = {
        "id": case["id"] + "_" + p["cell_id"],
        "parameters": p,
        "horizon_s": case["horizon_s"],
        "controls": controls,
    }
    if binding:
        result["channel"] = binding["channel"]
    return result


def project_local(case, values, index):
    parts = layout(case).split(values)
    keys = ("amount", "leak_transferred", "pump_cycles", "membrane_dissipated_energy_pJ")
    arrays = [
        parts[key][..., index, :].reshape(len(values), -1)
        if parts[key].ndim == 3
        else parts[key][..., index, None]
        for key in keys
    ]
    owner = case["graph"]["cells"][index]["cell_id"]
    for k, binding in enumerate(case["graph"]["channels"]):
        if binding["assembly"]["cell_id"] == owner:
            arrays.extend((parts["membrane_gate"][:, k], parts["channel_transferred"][:, k, None]))
    return np.concatenate(arrays, axis=1)
