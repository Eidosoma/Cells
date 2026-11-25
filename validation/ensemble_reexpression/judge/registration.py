"""The registered inputs as the judge reads them: worlds, entries, families, runs, reference paths,
plants.

Everything comes from the spec folder's data files. A world's entries follow from its `scales`
(READOUTS section 3), so the same code reads the registered worlds and the rehearsal's.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from . import constants as c
from . import strictjson

SPEC = Path(__file__).resolve().parent.parent / "spec"

# What a set of inputs does not say in its data files. The rehearsal gives its own as a JSON file
# (README).
PART1 = {
    "names": {
        "inputs": "inputs.json",
        "legacy": "legacy_part1.json",
        "paths": "reference_paths.json",
        "margins": "margins.json",
        "manifest": "plants_manifest.json",
    },
    # SPEC section 7: where each world's captured runs are. "windows": history and observations in
    # window-*.npz.
    # "assembly": checkpoint/state.npz, with the summaries in result.json or in
    # observations/tick-*.json.
    "captures": {
        "jupiter_baseline": {
            "set": "captures",
            "kind": "windows",
            "folder": "runs/jupiter_baseline-{step}",
            "definition": "science/ionic/jupiter_baseline/{step}.json",
        },
        "jupiter_pump_release": {
            "set": "captures",
            "kind": "windows",
            "folder": "runs/jupiter_pump_release-{step}",
            "definition": "science/ionic/jupiter_pump_release/{step}.json",
        },
        "integrated": {
            "set": "integrated_capture",
            "kind": "windows",
            "folder": "runs/finite_junction_cluster-{step}",
            "definition": "extra/ionic/finite_junction_cluster/{step}.json",
        },
        "cell": {
            "set": "captures",
            "kind": "assembly",
            "folder": "runs/cell-{step}-s{seed}",
            "definition": "science/assembly/cell/{step}-s{seed}.json",
            "summaries": "result",
        },
        "base": {
            "set": "captures",
            "kind": "assembly",
            "folder": "runs/cluster_base-{step}-s{seed}",
            "definition": "science/assembly/cluster_base/{step}-s{seed}.json",
            "summaries": "ticks",
        },
    },
    # CRITERIA section 8: the families that a prototype had run.
    "not_blind": {"base": ["base s0 w0", "base s0 w1"]},
    "not_blind_pool_runs": ["base s0 pool"],
    "notes": {
        "jupiter": "jupiter_baseline is the same ionic world as base, value for value, with the "
        "channels open throughout. What a prototype showed on base bears on it. No entry of "
        "jupiter was run (CRITERIA section 8)."
    },
    # PLANTS section 5: the engine plants, their changes, their named entries and where their
    # registered distance is.
    "engine_plants": {
        "EP1": {
            "change": [{"path": ["channels", "*", "max_permeability_m_per_s"], "multiply": 1.01}],
            "named": ["channel_K"],
            "distance": {
                "world": "jupiter_baseline",
                "entry": "channel_K",
                "power_plant": "channel",
            },
            "planted_run": "PW-channel jupiter_baseline",
        },
        "EP2": {
            "change": [{"exchange_channels": ["cell_0", "cell_1"]}],
            "named": ["channel_K"],
            "distance": {
                "world": "base",
                "entry": "channel_K",
                "structural": "ST6 availability on the other cell's channel",
            },
            "planted_run": "ST6 availability on the other cell's channel",
        },
    },
    "counts": {  # READOUTS section 3, the published counts
        "jupiter": {"S": 50, "energy": 2, "R": 60, "E": 25},
        "cell": {"S": 480, "energy": 32, "R": 964, "E": 392},
        "base": {"S": 800, "energy": 32, "R": 968, "E": 496},
        "integrated": {"S": 9, "energy": 1, "R": 30, "E": 9},
    },
    "runs": 214,
    # Amendment 1, item 6: the runs that may be made with the off-grid switch on. None is
    # registered.
    "off_grid_runs": [],
    # PLANTS section 6: what the judge's plants name.
    "plant_targets": {
        "ionic": "jupiter_baseline",
        "other_schedule": "jupiter_pump_release",
        "junctions": "integrated",
        "restart": "jupiter_baseline h=2.5e-05 restart",
        "engine_plant": "jupiter_baseline plant channel",
        "pool": "base s1 pool",
        "pool_path": ["base s0 pool", "cell_0", "2"],
        "not_blind": "base s0 w0",
        "assembly": "base s1 w0",
    },
}


@dataclass(frozen=True)
class Entry:
    """One readout of a family, over all its entities and compared times."""

    name: str
    series: str
    where: str  # "rows", "potentials", or "formed" (heat_membrane)
    times: tuple
    entities: tuple
    scale: float
    amount_ref: float
    closure_V: float | None

    def e_round(self, steps: int) -> float:
        """The rounding bound of one code (SPEC section 6)."""
        return c.ROUND_COUNT * c.EPS * (steps + 1) * self.scale

    def e_store(self, steps: int) -> float:
        """What a state that stores amounts may round by (SPEC section 6). 0 for an entry that reads
        no amount.
        """
        return c.STORE_COUNT * c.EPS * (steps + 1) * self.amount_ref

    def e_close(self) -> float:
        """The closure bound of both codes (SPEC section 6)."""
        return c.CLOSE_SHARE * self.scale if self.closure_V is None else self.closure_V


def ids(block) -> tuple:
    """The IDs of a set of entities, in the order of the block. An empty set may be printed as a
    list.
    """
    return tuple(block) if isinstance(block, dict) else ()


def changes(schedule) -> list:
    """A schedule's or a path's changes: the entries whose value differs from the value before,
    beginning with 1 (SPEC section 3.2).
    """
    out, level = [], 1
    for time, value in schedule:
        if value != level:
            out.append([time, value])
            level = value
    return out


class World:
    """One world of the inputs, with its entries and its compared times."""

    def __init__(self, name: str, data: dict, constants: dict):
        self.name = name
        self.data = data
        self.consumer = data["consumer"]
        block = data["ionic"]
        self.block = block
        self.constants = constants
        self.p = data["p"]
        self.end_s = block["end_s"]
        self.species = tuple(block["species"])
        self.valence = dict(block["species"])
        self.cells = ids(block["cells"])
        self.regions = ids(block["outside"])
        self.membranes = ids(block["membranes"])
        self.channels = ids(block["channels"])
        self.junctions = ids(block["junctions"])
        self.faces = ids(block["faces"])
        self.gauge = block["closure"]["gauge_reference"]
        self.pumps = tuple(m for m in self.membranes if block["membranes"][m]["pump"] is not None)
        self.pools = data.get("pools")
        self.assembly = self.pools is not None
        if self.assembly:
            self.row_times = (data["final_s"],)
            self.potential_times = tuple(data["summary_times_s"])
            self.identity_times = tuple(data["summary_times_s"])
        else:
            h = data["history_times"]
            count = round((h["last_s"] - h["first_s"]) / h["spacing_s"])
            self.row_times = tuple(h["first_s"] + i * h["spacing_s"] for i in range(count + 1))
            self.potential_times = tuple(data["potential_times_s"])
            self.identity_times = self.row_times
        self.entries, self.zeros = self._entries()
        self.by_name = {e.name: e for e in self.entries}
        self.energy = Entry(
            "energy_identity",
            "energy_identity",
            "identity",
            self.identity_times,
            ("world",),
            data["scales"]["energy_identity"],
            data["amount_refs"].get("energy_identity", 0.0),
            None,
        )

    def entities(self, series: str) -> tuple:
        """The entities of a READOUTS name in this world."""
        if series in ("pump", "heat_pump", "work_pump"):
            return self.pumps
        if series in ("gate_m", "gate_h", "heat_channel"):
            return self.channels
        if series in ("junction_gate", "heat_junction"):
            return self.junctions
        if series == "heat_face":
            return self.faces
        if series in ("heat_leak", "heat_membrane", "voltage"):
            return self.membranes
        if series == "phi_out":
            return tuple(r for r in self.regions if r != self.gauge)
        for prefix, entities in (
            ("n_cell_", self.cells),
            ("n_out_", self.regions),
            ("leak_", self.membranes),
            ("junction_", self.junctions),
            ("face_", self.faces),
        ):
            if series.startswith(prefix) and series[len(prefix) :] in self.species:
                return entities
        if series.startswith("channel_") and series[len("channel_") :] in self.species:
            species = series[len("channel_") :]
            return tuple(
                k for k in self.channels if self.block["channels"][k]["species_id"] == species
            )
        raise KeyError(series)

    def _entries(self):
        scales, refs, close = (
            self.data["scales"],
            self.data["amount_refs"],
            self.data["closure_terms_V"],
        )
        entries, zeros = [], []

        def add(name, series, where, times):
            entry = Entry(
                name,
                series,
                where,
                tuple(times),
                self.entities(series),
                scales[series],
                refs.get(series, 0.0),
                close.get(series),
            )
            (zeros if entry.scale == 0.0 else entries).append(entry)

        for series in scales:
            if series == "energy_identity":
                continue
            if series in ("voltage", "phi_out"):
                add(series, series, "potentials", self.potential_times)
            elif series == "heat_membrane":
                add(series, series, "formed", self.row_times)
            else:
                add(series, series, "rows", self.row_times)
                if (
                    self.assembly
                    and series.startswith("channel_")
                    and len(self.potential_times) > 1
                ):
                    add(f"{series}_summary", series, "rows", self.potential_times)
        return entries, zeros

    # What an ionic run's rows hold (READOUTS section 2), by what the world has.
    def row_series(self) -> tuple:
        """Every series of READOUTS section 2 that a run of this world has rows of, but the
        potentials.
        """
        out = []
        for x in self.species:
            out += [f"n_cell_{x}", f"n_out_{x}"]
        if not self.zero_routes:
            out += [f"leak_{x}" for x in self.species]
        for x in sorted({self.block["channels"][k]["species_id"] for k in self.channels}):
            out.append(f"channel_{x}")
        if self.junctions:
            out += [f"junction_{x}" for x in self.species] + ["junction_gate", "heat_junction"]
        if self.faces:
            out += [f"face_{x}" for x in self.species] + ["heat_face"]
        if self.pumps:
            out += ["pump", "heat_pump", "work_pump"]
        if self.channels:
            out += ["gate_m", "gate_h", "heat_channel"]
        if not self.zero_routes:
            out.append("heat_leak")
        return tuple(out)

    @property
    def zero_routes(self) -> bool:
        """True where no membrane has a passive permeability, so that the world has no leak
        series.
        """
        return all(
            p == 0.0
            for m in self.membranes
            for p in self.block["membranes"][m]["passive"]["permeability_m_per_s"].values()
        )

    def guard_entries(self) -> list:
        """The entries whose rows the copy guard compares: class S rows of the table (CRITERIA
        section 5).
        """
        return [e for e in self.entries if e.where == "rows"]

    @property
    def identities_judged(self) -> bool:
        """True for an order-4 world. An order-2 world's identities are reported (SPEC section 8,
        READOUTS section 5).
        """
        return self.p == 4

    def membranes_of(self, cell: str) -> list:
        """The membranes whose inside is the cell."""
        return [m for m in self.membranes if self.block["membranes"][m]["inside"] == cell]

    def channels_of(self, membrane: str) -> list:
        """The channel populations of a membrane."""
        return [k for k in self.channels if self.block["channels"][k]["membrane_id"] == membrane]

    def steps(self, step_s: float) -> int:
        """end_s over a step, as the integer that it is."""
        return round(self.end_s / step_s)


@dataclass(frozen=True)
class Family:
    """The three runs of one world at h1 > h2 > h3."""

    name: str
    consumer: str
    world: World
    seed_index: int | None
    world_id: int | None
    runs: tuple
    steps_s: tuple

    @property
    def finest(self) -> str:
        """The run at h3, which owns the family's S entries."""
        return self.runs[2]

    @property
    def retry_step(self) -> float:
        """h3 / 2."""
        return self.steps_s[2] / 2

    @property
    def retry_name(self) -> str:
        """The name of the family's retry run (CRITERIA section 7)."""
        return f"{self.name} h={self.retry_step!r} retry"


@dataclass
class Registration:
    """The spec folder's data files, with their hashes, and what follows from them."""

    folder: Path = SPEC
    profile: dict = field(default_factory=lambda: PART1)
    rehearsal: bool = False
    only: object = (
        None  # a predicate on a run, for the small tests: the registered runs that are kept
    )

    def __post_init__(self):
        self.folder = Path(self.folder)
        self.files = {}
        names = self.profile["names"]
        self.inputs = self._read(names["inputs"])
        self.legacy = self._read(names["legacy"])
        self.paths = self._read(names["paths"])
        self.margins = self._read(names["margins"])
        self.manifest = self._read(names["manifest"])
        self.constants = self.inputs["constants"]
        self.worlds = {
            name: World(name, data, self.constants) for name, data in self.inputs["worlds"].items()
        }
        self.runs = {}
        for run in self.inputs["runs"]:
            if run["name"] in self.runs:
                raise ValueError(f"the run {run['name']!r} stands twice in the inputs")
            if self.only is None or self.only(run):
                self.runs[run["name"]] = run
        kept = {run["consumer"] for run in self.runs.values()}
        self.consumers = tuple(
            dict.fromkeys(w.consumer for w in self.worlds.values() if w.consumer in kept)
        )
        self.families = self._families()
        self.by_consumer = {
            k: [f for f in self.families.values() if f.consumer == k] for k in self.consumers
        }

    def _read(self, name):
        value, digest = strictjson.read(self.folder / name)
        self.files[name] = digest
        return value

    def _families(self):
        grouped = {}
        for run in self.runs.values():
            if run["role"] == "judged" and run["family"] is not None:
                grouped.setdefault(run["family"], []).append(run)
        out = {}
        for name, runs in grouped.items():
            runs = sorted(runs, key=lambda r: -r["step_s"])
            if len(runs) != 3:
                raise ValueError(f"the family {name!r} has {len(runs)} judged runs, and not three")
            first = runs[0]
            out[name] = Family(
                name,
                first["consumer"],
                self.worlds[first["world"]],
                first["seed_index"],
                first["world_id"],
                tuple(r["name"] for r in runs),
                tuple(r["step_s"] for r in runs),
            )
        return out

    def family(self, world: str, seed_index, world_id):
        """The family of a world, a seed index and a world ID. A missing one is an error, but in a
        test's subset.
        """
        for family in self.families.values():
            if (family.world.name, family.seed_index, family.world_id) == (
                world,
                seed_index,
                world_id,
            ):
                return family
        if self.only is None:
            raise KeyError((world, seed_index, world_id))
        return None

    def part(self, consumer: str) -> Registration:
        """The same registration with one consumer's runs alone, for the judge's plants."""
        view = copy.copy(self)
        view.only = lambda run: run["consumer"] == consumer
        view.runs = {name: run for name, run in self.runs.items() if run["consumer"] == consumer}
        view.families = {k: f for k, f in self.families.items() if f.consumer == consumer}
        view.by_consumer = {consumer: self.by_consumer[consumer]}
        view.consumers = (consumer,)
        return view

    # ----- by run -----

    def retry_run(self, name: str):
        """The registered run of a retry name, or None (CRITERIA section 7)."""
        for family in self.families.values():
            if family.retry_name == name:
                base = dict(self.runs[family.finest])
                base.update(name=name, step_s=family.retry_step, role="retry", variant=None)
                return base
        return None

    def is_pool(self, run: dict) -> bool:
        """True for a pool run: a run of an assembly world that has no step."""
        return self.worlds[run["world"]].assembly and run["step_s"] is None

    def declared_changes(self, run: dict) -> list:
        """What a plant or a rehearsal's run declares that its world's block does not hold."""
        if run.get("declared_change"):
            return run["declared_change"]
        plant = (
            self.profile["engine_plants"].get(run["variant"]) if run["role"] == "plant" else None
        )
        return plant["change"] if plant else []

    def expected_block(self, run: dict) -> dict:
        """The ionic block that a run's `inputs` echo, its declared changes made."""
        block = copy.deepcopy(self.worlds[run["world"]].block)
        for change in self.declared_changes(run):
            if "path" in change:
                path = list(change["path"])
                if path and path[0] == "ionic":
                    path = path[1:]
                _apply(block, path, change)
        return block

    def expected_paths(self, run: dict) -> dict:
        """Channel ID to the reference path (the list of events) that a run's schedule must
        follow.
        """
        world = self.worlds[run["world"]]
        cells = list(world.pools)
        source = {cell: cell for cell in cells}
        for change in self.declared_changes(run):
            if "exchange_channels" in change:
                a, b = change["exchange_channels"]
                source[a], source[b] = source[b], source[a]
        table = self.paths["worlds"][world.name][f"s{run['seed_index']}"]
        return {
            world.pools[cell]["channel"]: table[source[cell]][str(run["world_id"])]
            for cell in cells
        }

    def reference_path(self, world: str, seed_index: int, cell: str, world_id) -> list:
        """The committed events of one pool world (reference_paths.json)."""
        return self.paths["worlds"][world][f"s{seed_index}"][cell][str(world_id)]

    def events(self, run: dict) -> int:
        """The committed events of a world's pools, the most splits that its step list can hold
        (TABLE section 3).
        """
        return sum(len(path) for path in self.expected_paths(run).values())

    def restart_time(self, run: dict):
        """The checkpoint's time of a support run, from its registered variant, or None where it is
        none.
        """
        found = re.search(r"restart at ([0-9.eE+-]+)", run["variant"] or "")
        return float(found.group(1)) if found and run["role"] == "support" else None

    def restarted(self, run: dict):
        """The judged run that a restart is compared with."""
        for other in self.runs.values():
            if other["role"] != "judged" or other["world"] != run["world"]:
                continue
            if other["seed_index"] != run["seed_index"] or other["world_id"] != run["world_id"]:
                continue
            if other["step_s"] == run["step_s"]:
                return other["name"]
        return None

    # ----- plants -----

    def structural(self) -> list:
        """The structural plants: (consumer, world, family, plant name, its margins' block)."""
        out = []
        for world_name, block in self.margins["worlds"].items():
            world = self.worlds[world_name]
            for name, plant in block["structural"].items():
                seed, wid = (0, plant["world"]) if world.assembly else (None, None)
                family = self.family(world_name, seed, wid)
                if family is not None:
                    out.append((world.consumer, world, family, name, plant))
        return out

    def engine(self) -> list:
        """The engine plants: (consumer, run, plant name, its description, its registered distances
        by named entry).
        """
        out = []
        for run in self.runs.values():
            if run["role"] != "plant" or run["variant"] not in self.profile["engine_plants"]:
                continue
            plant = self.profile["engine_plants"][run["variant"]]
            where = plant["distance"]
            block = self.margins["worlds"][where["world"]]
            if "structural" in where:
                distance = block["structural"][where["structural"]][where["entry"]]["distance"]
            else:
                entry = block["entries"][where["entry"]]
                distance = entry["home_plants"][where["power_plant"]]["ratio"] * entry["largest"]
            out.append(
                (
                    run["consumer"],
                    run,
                    run["variant"],
                    plant,
                    {name: distance for name in plant["named"]},
                )
            )
        return out

    def mechanisms(self, world: str) -> dict:
        """Mechanism to its home entries in a world (margins.json)."""
        return {
            name: list(homes) for name, homes in self.margins["worlds"][world]["mechanisms"].items()
        }

    def ratio(self, world: str, entry: str) -> float:
        """The ratio that power reads (CRITERIA section 4.5)."""
        return self.margins["worlds"][world]["entries"][entry]["ratio"]

    def is_home(self, world: str, entry: str) -> bool:
        """True where an entry is a home of some mechanism of its world."""
        return any(entry in homes for homes in self.mechanisms(world).values())


def _apply(block, path, change):
    """Set or multiply the leaves that a path names. `*` stands for every key of a map."""
    key, rest = path[0], path[1:]
    keys = list(block) if key == "*" else [key]
    for k in keys:
        if rest:
            _apply(block[k], rest, change)
        elif "value" in change:
            block[k] = change["value"]
        else:
            block[k] = block[k] * change["multiply"]


def load_profile(path) -> dict:
    """A rehearsal's profile: the same keys as `PART1`, from a JSON file."""
    return json.loads(Path(path).read_text())


class StringsNote:
    """The strings note (TABLE section 5): labels to exact strings, and the labels of every run."""

    def __init__(self, data: dict, digest: str, rehearsal: bool = False):
        self.data = data
        self.sha256 = digest
        self.labels = data["labels"]
        self.runs = data["runs"]
        self.revision = data["rehearsal_revision"] if rehearsal else data["revision"]

    @classmethod
    def read(cls, path, rehearsal: bool = False):
        """The note of a file."""
        data, digest = strictjson.read(Path(path))
        return cls(data, digest, rehearsal)

    def faults(self, registration: Registration) -> list:
        """What makes the note unusable: a wrong kind, no revision, an empty string, a run without
        labels, an unknown label.
        """
        out = []
        if self.data.get("kind") != c.STRINGS_KIND:
            out.append("the note's kind is not the contract's")
        if not isinstance(self.revision, str) or len(self.revision) != 40:
            out.append("the note has no revision of 40 hex digits")
        for label, string in self.labels.items():
            if not isinstance(string, str) or not string:
                out.append(f"the label {label} has no string")
        for name in registration.runs:
            if name not in self.runs:
                out.append(f"the run {name} has no labels")
                continue
            for label in self.labels_of(name):
                if label not in self.labels:
                    out.append(
                        f"the run {name} names the label {label}, which the note does not hold"
                    )
        return out

    def labels_of(self, name: str) -> list:
        """The full set of labels of a run."""
        run = self.runs[name]
        single = [
            run.get("model"),
            run.get("solver"),
            run.get("field_solver"),
            run.get("observable"),
        ]
        several = [
            label for key in ("operators", "kinds", "laws", "pool") for label in run.get(key, [])
        ]
        return sorted({label for label in single + several if label is not None})

    def expected(self, name: str) -> dict:
        """Label to exact string, for a run of the note."""
        return {label: self.labels[label] for label in self.labels_of(name)}
