"""What inputs.json registers: its worlds, its runs, their steps and their compared times, and the
grid rule (spec/SPEC.md §4). inputs_rehearsal.json has the same schema and is read by the same code.

Nothing here reads a record, and every number is inputs.json's own decimal.
"""

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
REGISTERED = FOLDER / "spec/inputs.json"
SCHEMA = "ensemble-reexpression inputs, version 1"
EPS = 2.0**-52
MATCH_S = 1e-12  # A time matches a registered one within this (spec/SPEC.md §4).
INVENTED = "inv_"  # The rehearsal's and the builder's own worlds and runs (spec/SPEC.md §8).

IONIC, DRIVEN, POOL = "ionic", "driven", "pool"
RUN_KEYS = {
    "name",
    "consumer",
    "family",
    "world",
    "seed_index",
    "world_id",
    "step_s",
    "role",
    "variant",
}
DECLARED_CHANGE = "declared_change"  # An invented plant's change (Amendment 1, item 4).
_RESTART = re.compile(r"(?:pool )?restart at (\S+)")
_RETRY = re.compile(r"(?P<family>.+) h=(?P<step>\S+) retry")


class InputsError(ValueError):
    """An inputs file, a run's name or a time that does not say what the spec says it says."""


class OffGridChange(ValueError):
    """A declared time that is not on its run's grid (spec/SPEC.md §4), by name."""


def read_json(path):
    """A JSON file, refused where one object gives a key twice."""

    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise InputsError(f"{path}: the key {key!r} is given twice")
            out[key] = value
        return out

    return json.loads(Path(path).read_text(), object_pairs_hook=pairs)


# ------------------------------------------------------------------ the grid rule


def grid_index(time, step):
    """The k of the grid point k x step that `time` is: they differ by at most 2 eps time, with k x
    step the double product. None where there is none."""
    k = round(time / step)
    return k if abs(time - k * step) <= 2 * EPS * time else None


def require_on_grid(times, step, what):
    """Refuse, by name, the first of these declared times that is not on the grid of `step`."""
    for time in times:
        if grid_index(time, step) is None:
            raise OffGridChange(
                f"off_grid_change: {what} declares {time!r} s, which is no grid point of the step "
                f"{step!r} s (nearest {round(time / step) * step!r} s)"
            )


def steps_of(end, step):
    """The accepted steps of a run without a split, end / step (spec/TABLE.md §3)."""
    k = grid_index(end, step)
    if k is None:
        raise OffGridChange(
            f"off_grid_change: the end {end!r} s is no grid point of the step {step!r} s"
        )
    return k


# ------------------------------------------------------------------ worlds


@dataclass(frozen=True)
class World:
    """One world's entry of inputs.json."""

    name: str
    consumer: str
    raw: dict

    @property
    def block(self):
        return self.raw["ionic"]

    @property
    def pools(self):
        """{cell: its pool's entry}, in the entry's order; {} for a world no pool drives."""
        return self.raw.get("pools", {})

    @property
    def order(self):
        return self.raw["p"]

    @property
    def end(self):
        return self.block["end_s"]

    @property
    def history_times(self):
        """The compared times of every readout but the potentials, where the entry gives a grid of
        them: i x spacing from its first to its last."""
        grid = self.raw.get("history_times")
        if grid is None:
            return None
        spacing = grid["spacing_s"]
        first, last = round(grid["first_s"] / spacing), round(grid["last_s"] / spacing)
        return tuple(i * spacing for i in range(first, last + 1))

    @property
    def potential_times(self):
        """The times of the potentials: the entry's, or 0 and then its summary times."""
        if "potential_times_s" in self.raw:
            return tuple(self.raw["potential_times_s"])
        return tuple(merged([0.0, *self.raw["summary_times_s"]]))

    @property
    def row_times(self):
        """The times a table holds rows at: the history's, or 0, the summary times and the end."""
        times = self.history_times
        if times is None:
            times = [0.0, *self.raw["summary_times_s"], self.end]
        return tuple(merged([0.0, *times]))


def merged(times):
    """The times in increasing order, one for each group that a match cannot tell apart."""
    out = []
    for time in sorted(times):
        if not out or time - out[-1] > MATCH_S:
            out.append(time)
    return out


# ------------------------------------------------------------------ runs


@dataclass(frozen=True)
class Run:
    """One registered run, or a retry's, which is registered by its family's rule."""

    name: str
    consumer: str
    family: str | None
    world: str
    seed_index: int | None
    world_id: int | None
    step_s: float | None
    role: str
    variant: str | None
    kind: str
    declared_change: tuple | dict | None = None
    retry: bool = False

    @property
    def restart_time(self):
        """The time of the checkpoint this run resumes, as its variant's decimal, or None."""
        match = _RESTART.fullmatch(self.variant or "")
        return None if match is None else float(match[1])

    @property
    def judged_name(self):
        """The run whose checkpoint a restart resumes."""
        if self.restart_time is None:
            return None
        if not self.name.endswith(" restart"):
            raise InputsError(f"{self.name!r} is a restart whose name does not end in ' restart'")
        return self.name[: -len(" restart")]

    @property
    def slug(self):
        """The run's name as a folder's."""
        return re.sub(r"[^A-Za-z0-9.=_+-]", "_", self.name)

    @property
    def invented(self):
        return self.name.startswith(INVENTED)


class Inputs:
    """A parsed inputs file."""

    def __init__(self, path=REGISTERED):
        self.path = Path(path)
        data = self.path.read_bytes()
        self.sha256 = hashlib.sha256(data).hexdigest()
        self.raw = read_json(self.path)
        if self.raw.get("schema") != SCHEMA:
            raise InputsError(f"{path}: its schema is not {SCHEMA!r}")
        self.part = self.raw["part"]
        self.worlds = {
            name: World(name, entry["consumer"], entry)
            for name, entry in self.raw["worlds"].items()
        }
        self.runs = {}
        for entry in self.raw["runs"]:
            run = self._run(entry)
            if run.name in self.runs:
                raise InputsError(f"{path}: the run {run.name!r} is listed twice")
            self.runs[run.name] = run
        if len({r.slug for r in self.runs.values()}) != len(self.runs):
            raise InputsError(f"{path}: two run names make one folder name")

    def _run(self, entry):
        unknown = sorted(set(entry) - RUN_KEYS - {DECLARED_CHANGE})
        missing = sorted(RUN_KEYS - set(entry))
        if unknown or missing:
            raise InputsError(f"Run {entry.get('name')!r}: unknown {unknown}, missing {missing}")
        if entry["world"] not in self.worlds:
            raise InputsError(f"Run {entry['name']!r}: no world {entry['world']!r}")
        world = self.worlds[entry["world"]]
        if entry["step_s"] is None:
            kind = POOL
        else:
            kind = DRIVEN if world.pools else IONIC
        if kind != IONIC and entry["seed_index"] is None:
            raise InputsError(f"Run {entry['name']!r}: a run of pools names its seed index")
        if kind == DRIVEN and entry["world_id"] is None:
            raise InputsError(f"Run {entry['name']!r}: a driven run names its world ID")
        values = {key: entry[key] for key in RUN_KEYS}
        return Run(**values, kind=kind, declared_change=entry.get(DECLARED_CHANGE))

    @property
    def consumers(self):
        """The consumers in the runs' order."""
        return tuple(dict.fromkeys(run.consumer for run in self.runs.values()))

    def families(self):
        """{family: its judged runs, in falling step order}."""
        out = {}
        for run in self.runs.values():
            if run.family is not None and run.role == "judged":
                out.setdefault(run.family, []).append(run)
        return {name: sorted(runs, key=lambda r: -r.step_s) for name, runs in out.items()}

    def retry(self, name):
        """The retry's run of this name, `<family> h=<step> retry`: its family's finest run at half
        that run's step, which the name's decimal must say."""
        match = _RETRY.fullmatch(name)
        families = self.families()
        if match is None or match["family"] not in families:
            raise InputsError(f"{name!r} is no retry of a family of {self.path.name}")
        finest = families[match["family"]][-1]
        step = float(match["step"])
        if step != finest.step_s / 2:
            raise InputsError(
                f"{name!r}: the retry's step is half of {finest.step_s!r} s, the finest of its "
                "family"
            )
        return Run(
            name,
            finest.consumer,
            finest.family,
            finest.world,
            finest.seed_index,
            finest.world_id,
            step,
            finest.role,
            finest.variant,
            finest.kind,
            finest.declared_change,
            retry=True,
        )

    def run(self, name):
        """The run of this name, a retry's among them."""
        if name in self.runs:
            return self.runs[name]
        if name.endswith(" retry"):
            return self.retry(name)
        raise InputsError(f"No run {name!r} in {self.path.name}")

    def owed(self, path):
        """The retry's runs that the judge's retry_owed.json names (spec/TABLE.md §6)."""
        note = read_json(path)
        if note.get("kind") != "ensemble-reexpression retry owed, version 1":
            raise InputsError(f"{path} is no retry note")
        return tuple(self.retry(name) for name in note["runs"])


def matched(times, wanted):
    """{index into `wanted`: index into `times`} of the wanted times that a time matches."""
    out = {}
    for k, time in enumerate(wanted):
        best = min(range(len(times)), key=lambda i: abs(times[i] - time), default=None)
        if best is not None and abs(times[best] - time) <= MATCH_S:
            out[k] = best
    return out
