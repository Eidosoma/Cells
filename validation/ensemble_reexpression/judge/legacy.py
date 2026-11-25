"""The legacy side: the captures and the planted legacy runs, read by what the spec folder pins.

Every file is checked against the sha256 that a pinned manifest gives it, before its content is used. Nothing here reads an engine table.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

import numpy as np

from . import constants as c
from . import strictjson
from .registration import Family, Registration, World

STEPS = ("h", "h2", "h4")


class Fault(Exception):
    """A fault of the reference side (a C0 fault): a missing file, a hash or a shape that is not the pinned one."""


# ----- the captured index of each series (READOUTS section 2) -----


def pick(raw: dict, series: str, world: World) -> np.ndarray:
    """A series of a legacy state, [lead, entity]. `raw` holds the state's arrays with one leading axis (rows, or worlds)."""
    entities = world.entities(series)

    def at(name, *index, order=()):
        if name not in raw:
            raise Fault(f"{world.name}: the array {name} is absent")
        array = raw[name]
        for i in index:
            array = array[:, i]
        positions = [order.index(entity) for entity in entities]
        if positions and max(positions) >= array.shape[1]:
            raise Fault(f"{world.name}: {name} has {array.shape[1]} slots for {series}")
        return array[:, positions]

    for prefix, name, order in (
        ("n_cell_", "amount_increment", world.cells),
        ("n_out_", "extracellular_amount_increment", world.regions),
        ("leak_", "leak_transferred", world.membranes),
        ("junction_", "junction_transferred", world.junctions),
        ("face_", "face_transferred", world.faces),
    ):
        if series.startswith(prefix) and series[len(prefix) :] in world.species:
            return at(name, world.species.index(series[len(prefix) :]), order=order)
    if series.startswith("channel_"):
        return at("channel_transferred", order=world.channels)
    if series == "pump":
        return at("pump_cycles", order=world.membranes)
    if series in ("gate_m", "gate_h"):
        return at("gate", ("gate_m", "gate_h").index(series), order=world.channels)
    if series == "junction_gate":
        return at("junction_gate", order=world.junctions)
    if series == "heat_membrane":
        return at("dissipated_energy_pJ", order=world.membranes)
    if series == "heat_junction":
        return at("junction_dissipated_energy_pJ", order=world.junctions)
    if series == "heat_face":
        return at("face_dissipated_energy_pJ", order=world.faces)
    raise KeyError(series)


def match(times: np.ndarray, wanted, what: str) -> list:
    """The row of each wanted time. Each needs exactly one row within the contract's tolerance."""
    out = []
    for time in wanted:
        found = np.flatnonzero(np.abs(times - time) <= c.TIME_TOL_S)
        if len(found) != 1:
            raise Fault(f"{what}: {len(found)} rows at {time!r} s")
        out.append(int(found[0]))
    return out


def join_windows(windows: list, what: str) -> dict:
    """The history and the observations of a run's windows, in order. The earlier window owns the row that two share."""
    times, history, observed = [], {}, {}
    for i, window in enumerate(windows):
        start = 0
        if i:
            if window["times"][0] != times[-1][-1]:
                raise Fault(f"{what}: window {i} does not begin at the time that the window before it ends at")
            start = 1
        times.append(window["times"][start:])
        for name, array in window.items():
            if name.startswith("history."):
                if i and not np.array_equal(array[0], history[name[8:]][-1][-1]):
                    raise Fault(f"{what}: the row that windows {i - 1} and {i} share differs in {name}")
                history.setdefault(name[8:], []).append(array[start:])
            elif name.startswith("observations."):
                observed.setdefault(name[13:], []).append(array)
    out = {name: np.concatenate(parts) for name, parts in history.items()}
    out["times"] = np.concatenate(times)
    out["observed"] = {name: np.concatenate(parts) for name, parts in observed.items()}
    return out


class LegacyRun:
    """One legacy run of an ionic world: its series at any of its rows, and its potentials at its observations."""

    def __init__(self, world: World, raw: dict, what: str):
        self.world, self.raw, self.what = world, raw, what
        self.times = raw["times"]

    def entry(self, entry) -> np.ndarray:
        """An entry's array, [compared time, entity]."""
        if entry.where == "potentials":
            return self.potential(entry.series, entry.times)
        rows = match(self.times, entry.times, self.what)
        return pick(self.raw, entry.series, self.world)[rows]

    def series(self, series: str, times) -> np.ndarray:
        """A series at given times, [time, entity]."""
        return pick(self.raw, series, self.world)[match(self.times, times, self.what)]

    def potential(self, name: str, times) -> np.ndarray:
        """A potential at given observation times, [time, entity]."""
        observed = self.raw["observed"]
        rows = match(observed["times"], times, f"{self.what} observations")
        if name == "voltage":
            return observed["voltage_V"][rows][:, : len(self.world.membranes)]
        order = [self.world.regions.index(r) for r in self.world.entities("phi_out")]
        return observed["extracellular_potential_V"][rows][:, order]

    def initial_voltage(self) -> np.ndarray:
        """The voltage at time 0."""
        return self.potential("voltage", (0.0,))[0]


class LegacyAssembly:
    """One legacy run of an assembly world, at one world ID: the end state and the summaries."""

    def __init__(self, world: World, state: dict, summaries: dict, world_id: int, what: str):
        self.world, self.state, self.summaries, self.world_id, self.what = world, state, summaries, world_id, what
        self.raw = {name[6:]: array for name, array in state.items() if name.startswith("ionic_")}

    def entry(self, entry) -> np.ndarray:
        """An entry's array, [compared time, entity]."""
        if entry.where == "potentials":
            return np.array([self.voltage(time) for time in entry.times])
        if entry.name.endswith("_summary"):
            return np.array([self.transfer(time) for time in entry.times])
        return self.series(entry.series, entry.times)

    def series(self, series: str, times) -> np.ndarray:
        """A series at the end, [1, entity]. The captures hold no other row of an assembly world."""
        for time in times:
            if abs(time - self.world.end_s) > c.TIME_TOL_S:
                raise Fault(f"{self.what}: no captured row of {series} at {time!r} s")
        return pick(self.raw, series, self.world)[[self.world_id]]

    def _summary(self, time: float) -> dict:
        for known, summary in self.summaries.items():
            if abs(known - time) <= c.TIME_TOL_S:
                return summary
        raise Fault(f"{self.what}: no captured summary at {time!r} s")

    def voltage(self, time: float) -> np.ndarray:
        """`final_voltage_V` of a summary, by membrane."""
        summary = self._summary(time)
        values = np.atleast_1d(np.asarray(summary["final_voltage_V"][self.world_id], dtype=float))
        cells = summary.get("cell_ids", list(self.world.cells))
        inside = [self.world.block["membranes"][m]["inside"] for m in self.world.membranes]
        return np.array([values[cells.index(cell)] for cell in inside])

    def transfer(self, time: float) -> np.ndarray:
        """`channel_transferred_fmol` of a summary, by channel."""
        summary = self._summary(time)
        values = np.atleast_1d(np.asarray(summary["channel_transferred_fmol"][self.world_id], dtype=float))
        channels = summary.get("channel_ids", list(self.world.channels))
        return np.array([values[channels.index(channel)] for channel in self.world.channels])

    def initial_voltage(self) -> np.ndarray:
        """The voltage at time 0: the summary's where one is captured, and otherwise the declared one."""
        if any(abs(known) <= c.TIME_TOL_S for known in self.summaries):
            return self.voltage(0.0)
        block = self.world.block
        return np.array(
            [
                block["cells"][block["membranes"][m]["inside"]]["initial_charge_C"] / block["membranes"][m]["capacitance_F"]
                for m in self.world.membranes
            ]
        )


def _windows(names: list, folder: str) -> list:
    """The window files of a folder, in the natural order of their names."""
    found = [n for n in names if re.fullmatch(re.escape(folder) + r"/window-\d+\.npz", n)]
    natural = sorted(found, key=lambda n: int(re.search(r"window-(\d+)\.npz$", n).group(1)))
    if natural != sorted(found):
        raise Fault(f"{folder}: the windows' text order is not their natural order")
    if not natural:
        raise Fault(f"{folder}: no window")
    return natural


def _npz(data: bytes) -> dict:
    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        return {name: z[name] for name in z.files}


def _tick(time: float, step_s: float) -> str:
    return f"observations/tick-{round(time / step_s):07d}.json"


class _Source:
    """Files of one legacy run by relative name, each checked against a pinned sha256."""

    def __init__(self, read, names):
        self.read, self.names = read, names

    def ionic(self, world: World, folder: str) -> LegacyRun:
        windows = [_npz(self.read(name)) for name in _windows(self.names, folder)]
        return LegacyRun(world, join_windows(windows, folder), folder)

    def state(self, folder: str) -> dict:
        return _npz(self.read(f"{folder}/checkpoint/state.npz"))

    def summaries(self, world: World, folder: str, style: str, step_s: float) -> dict:
        if style == "result":
            return {world.end_s: strictjson.loads(self.read(f"{folder}/result.json"))}
        out = {}
        for time in (0.0, *world.potential_times):
            out[time] = strictjson.loads(self.read(f"{folder}/{_tick(time, step_s)}"))
        return out


class Captures:
    """The captured runs (SPEC section 7)."""

    def __init__(self, registration: Registration):
        self.reg = registration
        self.opened = {}
        self._manifests, self._runs, self._states, self._summaries = {}, {}, {}, {}

    # ----- files -----

    def _pinned(self, path: Path, digest: str, what: str) -> bytes:
        try:
            data = path.read_bytes()
        except OSError as error:
            raise Fault(f"{what}: {error}") from error
        found = strictjson.sha256(data)
        if found != digest:
            raise Fault(f"{what}: the sha256 of {path} is {found}, and the pinned one is {digest}")
        self.opened[str(path)] = found
        return data

    def manifest(self, key: str) -> dict:
        """The manifest of a captured set, pinned by the legacy file."""
        if key not in self._manifests:
            block = self.reg.legacy[key]
            path = Path(block["root"]) / block["science"] / "MANIFEST.json"
            self._manifests[key] = strictjson.loads(self._pinned(path, block["science_manifest_sha256"], key))
        return self._manifests[key]

    def origin(self, key: str) -> dict:
        """The origin's manifest of a captured set (its definitions), pinned by the legacy file."""
        name = f"{key} origin"
        if name not in self._manifests:
            block = self.reg.legacy[key]
            path = Path(block["root"]) / block["origin"] / "manifest.json"
            self._manifests[name] = strictjson.loads(self._pinned(path, block["origin_manifest_sha256"], name))
        return self._manifests[name]

    def read(self, key: str, relative: str) -> bytes:
        """A file of a captured set, checked against its manifest."""
        block = self.reg.legacy[key]
        files = self.manifest(key)["files"]
        if relative not in files:
            raise Fault(f"{key}: {relative} is not in the manifest")
        return self._pinned(Path(block["root"]) / block["science"] / relative, files[relative]["sha256"], key)

    def definition(self, world: str, step: str, seed=None) -> dict:
        """A captured definition."""
        where = self.reg.profile["captures"][world]
        key = where["set"]
        block = self.reg.legacy[key]
        relative = where["definition"].format(step=step, seed=seed)
        files = self.origin(key)["files_sha256"]
        if relative not in files:
            raise Fault(f"{key}: {relative} is not in the origin's manifest")
        data = self._pinned(Path(block["root"]) / block["origin"] / relative, files[relative], key)
        return strictjson.loads(data)

    # ----- runs -----

    def _source(self, key: str) -> _Source:
        return _Source(lambda name: self.read(key, name), list(self.manifest(key)["files"]))

    def step_s(self, world: str, step: str) -> float:
        """A captured step, in s."""
        return self.reg.legacy["worlds"][world]["captured_steps_s"][STEPS.index(step)]

    def steps(self, world: str) -> int:
        """S_l: the steps of the finest captured run."""
        return self.reg.worlds[world].steps(self.step_s(world, "h4"))

    def ionic(self, world: str, step: str) -> LegacyRun:
        """A captured run of an ionic world."""
        if (world, step) not in self._runs:
            where = self.reg.profile["captures"][world]
            folder = where["folder"].format(step=step)
            self._runs[world, step] = self._source(where["set"]).ionic(self.reg.worlds[world], folder)
        return self._runs[world, step]

    def state(self, world: str, step: str, seed: int) -> dict:
        """The end state of a captured assembly run."""
        if (world, step, seed) not in self._states:
            where = self.reg.profile["captures"][world]
            folder = where["folder"].format(step=step, seed=seed)
            source = self._source(where["set"])
            self._states[world, step, seed] = source.state(folder)
            self._summaries[world, step, seed] = source.summaries(
                self.reg.worlds[world], folder, where["summaries"], self.step_s(world, step)
            )
        return self._states[world, step, seed]

    def run(self, family: Family, step: str):
        """The captured run of a family at a captured step."""
        world = family.world
        if not world.assembly:
            return self.ionic(world.name, step)
        state = self.state(world.name, step, family.seed_index)
        summaries = self._summaries[world.name, step, family.seed_index]
        what = f"{world.name} {step} s{family.seed_index} w{family.world_id}"
        return LegacyAssembly(world, state, summaries, family.world_id, what)

    # ----- pools -----

    def pool_arrays(self, world: str, seed: int, cell: str, step: str = "h4") -> dict:
        """The 19 captured arrays of one pool, [world, ...]."""
        state = self.state(world, step, seed)
        cells = list(self.reg.worlds[world].pools)
        out = {}
        for name in c.POOL_ARRAYS:
            array = state[f"pool_{name}"]
            out[name] = array if len(cells) == 1 else array[:, cells.index(cell)]
        return out

    def exposure(self, world: str, seed: int, cell: str, step: str = "h4"):
        """The captured exposure of one pool and the job's segments, by world."""
        state = self.state(world, step, seed)
        cells = list(self.reg.worlds[world].pools)
        exposure = state["availability_exposure_s"]
        return (exposure if len(cells) == 1 else exposure[:, cells.index(cell)]), state["segments"]


class Planted:
    """The planted legacy runs, by the plants manifest."""

    def __init__(self, registration: Registration):
        self.reg = registration
        self.opened = {}
        self.runs = {}
        for run in registration.manifest["runs"]:
            if run["name"] in self.runs:
                raise Fault(f"the planted run {run['name']!r} stands twice in the manifest")
            self.runs[run["name"]] = run
        self._cache = {}

    def read(self, name: str, relative: str) -> bytes:
        """A file of a planted run, checked against the manifest."""
        run = self.runs[name]
        digest = run["outputs_sha256"].get(relative)
        if digest is None:
            raise Fault(f"{name}: {relative} is not in the manifest")
        path = Path(run["output_folder"]) / relative
        try:
            data = path.read_bytes()
        except OSError as error:
            raise Fault(f"{name}: {error}") from error
        found = strictjson.sha256(data)
        if found != digest:
            raise Fault(f"{name}: the sha256 of {relative} is not the manifest's")
        self.opened[str(path)] = found
        return data

    def _source(self, name: str) -> _Source:
        return _Source(lambda relative: self.read(name, relative), list(self.runs[name]["outputs_sha256"]))

    def ionic(self, name: str, world: World) -> LegacyRun:
        """A planted run of an ionic world."""
        if name not in self._cache:
            self._cache[name] = self._source(name).ionic(world, "run")
        return self._cache[name]

    def assembly(self, name: str, world: World, world_id: int, step_s: float) -> LegacyAssembly:
        """A planted run of an assembly world, at one world ID."""
        if name not in self._cache:
            source = self._source(name)
            style = self.reg.profile["captures"][world.name]["summaries"]
            self._cache[name] = (source.state("run"), source.summaries(world, "run", style, step_s))
        state, summaries = self._cache[name]
        return LegacyAssembly(world, state, summaries, world_id, f"{name} w{world_id}")

    def run(self, name: str, family: Family, step_s: float):
        """A planted run, as its family's captured run would be read."""
        if family.world.assembly:
            return self.assembly(name, family.world, family.world_id, step_s)
        return self.ionic(name, family.world)
