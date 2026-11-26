"""The judge's own honest tables, for its self-tests (PLANTS section 6, SPEC section 8). They are
fabricated: no engine ran.

Every value is the reference side's, moved by at most one unit in the last place. A membrane's heat
is split by an invented rule. Class E values are not moved. Where the reference side holds no row
(`base` at 5 and 10 ms), the row is invented so that the identities close.
"""

from __future__ import annotations

import copy
import zlib

import numpy as np

from . import constants as c
from . import identities, strictjson
from .legacy import STEPS, Captures, Planted
from .registration import Registration, World, changes

REVISION = "fab0" * 10
MARK = (
    "fabricated by the judge from the reference side's arrays, each moved by at most one unit "
    "in the last place; no engine ran"
)
SPLIT = {
    "heat_leak": 0.25,
    "heat_pump": 0.25,
    "heat_channel": 0.5,
}  # invented, exact in the order leak + pump + channel


def moved(array, key: str) -> np.ndarray:
    """An array with each value moved by -1, 0 or 1 unit in the last place, by a fixed rule of its
    key. A zero stays zero.
    """
    array = np.asarray(array, dtype=float)
    draw = np.random.default_rng(zlib.crc32(key.encode())).integers(-1, 2, size=array.shape)
    up, down = np.nextafter(array, np.inf), np.nextafter(array, -np.inf)
    out = np.where(draw > 0, up, np.where(draw < 0, down, array))
    return np.where(array == 0.0, array, out)


class Held:
    """Series already made, as `identities` reads them: name to [time, entity] at `times`."""

    def __init__(self, world: World, times, series: dict, voltages, V0):
        self.world, self.times, self.series, self._voltages, self._V0 = (
            world,
            list(times),
            series,
            voltages,
            V0,
        )

    def get(self, name, times):
        """A series at some of the times."""
        return self.series[name][[self.times.index(t) for t in times]]

    def voltage(self, times):
        """The voltage at some of the times."""
        return self._voltages[[self.times.index(t) for t in times]]

    def initial_voltage(self):
        """The voltage at time 0."""
        return self._V0

    def heats(self):
        """Every heat series."""
        return identities.heat_series(self.world)


class Fabricator:
    """Makes the honest tables and a strings note."""

    def __init__(self, registration: Registration, captures: Captures, planted: Planted):
        self.reg, self.captures, self.planted = registration, captures, planted

    # ----- the strings note -----

    def labels(self, run: dict) -> dict:
        """The labels of a run, by its world's block."""
        world = self.reg.worlds[run["world"]]
        block = world.block
        observable = world.data["coupling"]["law"] if world.assembly else None
        if self.reg.is_pool(run):
            pool = next(iter(world.pools.values()))["pool"]
            return {
                "model": pool["model"],
                "solver": None,
                "field_solver": None,
                "operators": [],
                "kinds": [],
                "laws": [],
                "pool": [pool["model"], pool["topology"]],
                "observable": observable,
            }
        laws = {"closure"}
        for membrane in block["membranes"].values():
            laws.add(membrane["passive"]["law"])
            if membrane["pump"]:
                laws |= {membrane["pump"]["law"], membrane["pump"]["metabolism"]["kind"]}
        laws |= {block["channels"][k]["kinetic_law"] for k in world.channels}
        laws |= {block["junctions"][k]["gate"]["law"] for k in world.junctions}
        laws |= {block["faces"][k]["law"] for k in world.faces}
        faced = {m["outside"] for m in block["membranes"].values()}
        return {
            "model": "inner_model",
            "solver": "rk4" if world.p == 4 else "imex",
            "field_solver": "field_solver" if faced == set(world.regions) else "field_solver_floor",
            "operators": [],
            "kinds": [],
            "laws": sorted(laws),
            "pool": [],
            "observable": observable,
        }

    def note(self) -> dict:
        """A fabricated strings note for every registered run."""
        runs = {name: self.labels(run) for name, run in self.reg.runs.items()}
        used = {
            label
            for r in runs.values()
            for v in r.values()
            for label in (v if isinstance(v, list) else [v])
            if label
        }
        labels = {label: f"fabricated.{label}" for label in sorted(used | set(c.LABELS))}
        return {
            "kind": c.STRINGS_KIND,
            "revision": REVISION,
            "rehearsal_revision": REVISION,
            "labels": labels,
            "runs": runs,
        }

    # ----- one entry -----

    def frame(self, name: str, run: dict) -> dict:
        """A run's entry with everything but its rows."""
        note = self._note
        labels = note["runs"][
            run["name"] if run["role"] != "retry" else self.reg.families[run["family"]].finest
        ]
        flat = sorted(
            {v for x in labels.values() for v in (x if isinstance(x, list) else [x]) if v}
        )
        strings = {label: note["labels"][label] for label in flat}
        machine = self.reg.legacy.get("captures", {})
        return {
            "status": "completed",
            "world": run["world"],
            "variant": run["variant"],
            "seed_index": run["seed_index"],
            "world_id": run["world_id"],
            "step_s": run["step_s"],
            "steps": None,
            "t": [],
            "rows": {},
            "potential_t": [],
            "potentials": {},
            "pool": None,
            "path": None,
            "inputs": {},
            "strings": strings,
            "declared_strings": sorted(set(strings.values())),
            "definition": {"fabricated": True},
            "checks": {"fabricated": 0.0},
            "restart": None,
            "host_patch": None,
            "refusal": None,
            "source": {
                "engine_revision": REVISION,
                "checkout_dirty": False,
                "snapshot": "fabricated",
                "snapshot_patch_sha256": c.EMPTY_SHA256,
                "python": "fabricated",
                "numpy": "fabricated",
                "jax": "fabricated",
                "jaxlib": "fabricated",
                "cpu_model": machine.get("cpu_model", "fabricated"),
                "blas_threads": 1,
            },
            "record": f"fabricated/{name}.json",
            "record_sha256": _digest(name),
        }

    def inputs(self, run: dict) -> dict:
        """An ionic run's inputs: its block, its declared changes made, and for an assembly world
        its schedule and `assembly`.
        """
        world = self.reg.worlds[run["world"]]
        block = self.reg.expected_block(run)
        if world.assembly:
            paths = self.reg.expected_paths(run)
            switches = {channel: changes(path) for channel, path in paths.items()}
            block["controls"]["channel"] = {
                channel: [[0.0, 1.0], *copy.deepcopy(listed)]
                for channel, listed in switches.items()
            }
            block["assembly"] = {
                "assembly_observable": world.data["coupling"]["law"],
                "composed_file_fingerprint": "fabricated",
                "pool_seeds": {
                    cell: pool["seeds"][run["seed_index"]] for cell, pool in world.pools.items()
                },
                "switch_list": copy.deepcopy(switches),
            }
        return block

    # ----- rows -----

    def rows(self, run: dict, legacy, key: str):
        """(t, rows, potential_t, potentials) of a run whose reference side is `legacy`. `key` fixes
        the moves.
        """
        world = self.reg.worlds[run["world"]]
        return (
            self._assembly(world, legacy, key)
            if world.assembly
            else self._windows(world, legacy, key)
        )

    def _split(self, world, heat):
        out = {}
        if not world.zero_routes:
            out["heat_leak"] = SPLIT["heat_leak"] * heat
        if world.pumps:
            out["heat_pump"] = (
                SPLIT["heat_pump"] * heat[:, [world.membranes.index(m) for m in world.pumps]]
            )
        if world.channels:
            owners = [
                world.membranes.index(world.block["channels"][k]["membrane_id"])
                for k in world.channels
            ]
            out["heat_channel"] = SPLIT["heat_channel"] * heat[:, owners]
        return out

    def _windows(self, world, legacy, key):
        times, series = list(world.row_times), {}
        for name in world.row_series():
            if name in ("heat_leak", "heat_pump", "heat_channel", "work_pump"):
                continue
            series[name] = moved(legacy.series(name, times), f"{key}|{name}")
        if "heat_membrane" in world.data["scales"]:
            series.update(
                self._split(
                    world, moved(legacy.series("heat_membrane", times), f"{key}|heat_membrane")
                )
            )
        if world.pumps:
            series["work_pump"] = series["pump"] * np.array(
                [identities.fuel_energy(world, m) for m in world.pumps]
            )
        potentials = {
            "voltage": moved(legacy.potential("voltage", world.potential_times), f"{key}|voltage")
        }
        if "phi_out" in world.data["scales"]:
            potentials["phi_out"] = moved(
                legacy.potential("phi_out", world.potential_times), f"{key}|phi_out"
            )
        return (
            times,
            self.as_rows(world, series),
            list(world.potential_times),
            self.as_rows(world, potentials),
        )

    def _assembly(self, world, legacy, key):
        summaries = list(world.potential_times)
        times = [0.0, *summaries]
        end = {}
        for name in world.row_series():
            if name not in ("heat_leak", "heat_pump", "heat_channel", "work_pump"):
                end[name] = moved(legacy.series(name, (world.end_s,)), f"{key}|{name}")[0]
        heat = moved(legacy.series("heat_membrane", (world.end_s,)), f"{key}|heat_membrane")[0]
        V0 = legacy.initial_voltage()
        voltages = np.array(
            [V0, *(moved(legacy.voltage(t), f"{key}|voltage {t!r}") for t in summaries)]
        )
        gates = {"gate_m": "m", "gate_h": "h"}
        series = {
            name: np.zeros((len(times), len(world.entities(name)))) for name in world.row_series()
        }
        for name, gate in gates.items():
            series[name][0] = [
                world.block["channels"][k]["initial_gate"][gate] for k in world.channels
            ]
        if world.junctions:
            series["junction_gate"][0] = [
                world.block["junctions"][j]["gate"]["initial_gate"] for j in world.junctions
            ]
        for i, time in enumerate(times[1:], start=1):
            if time == world.end_s:
                for name, value in end.items():
                    series[name][i] = value
                for name, value in self._split(world, heat[None, :]).items():
                    series[name][i] = value[0]
            else:
                self._invent(
                    world, series, i, time / world.end_s, end, heat, legacy, key, time, voltages, V0
                )
            if world.pumps:
                series["work_pump"][i] = series["pump"][i] * [
                    identities.fuel_energy(world, m) for m in world.pumps
                ]
        return (
            times,
            self.as_rows(world, series),
            list(times),
            self.as_rows(world, {"voltage": voltages}),
        )

    def _invent(self, world, series, i, share, end, heat, legacy, key, time, voltages, V0):
        """A row that no capture holds: the end row's share, with leak_K and the heats set so that
        the identities close.
        """
        for name, value in end.items():
            start = series[name][0]
            series[name][i] = start + share * (value - start)
        transfer = moved(legacy.transfer(time), f"{key}|transfer {time!r}")
        for j, channel in enumerate(world.channels):
            species = world.block["channels"][channel]["species_id"]
            series[f"channel_{species}"][i][world.entities(f"channel_{species}").index(channel)] = (
                transfer[j]
            )
        if world.pumps:
            series["work_pump"][i] = series["pump"][i] * [
                identities.fuel_energy(world, m) for m in world.pumps
            ]
        K = world.constants
        balance = "K"
        for x in world.species:
            series[f"n_cell_{x}"][i] = 0.0
            if x == balance:
                series[f"leak_{x}"][i] = 0.0
        held = Held(world, [time], {n: v[[i]] for n, v in series.items()}, voltages[[i]], V0)
        for x in world.species:
            series[f"n_cell_{x}"][i] = -identities.cell_residual(world, held, x, [time])[0]
        for m, membrane in enumerate(world.membranes):
            block = world.block["membranes"][membrane]
            cell = world.cells.index(block["inside"])
            charge = (
                block["capacitance_F"]
                * (voltages[i][m] - V0[m])
                / (K["F_C_per_mol"] * K["fmol_to_mol"])
            )
            rest = sum(world.valence[x] * series[f"n_cell_{x}"][i][cell] for x in world.species)
            series[f"leak_{balance}"][i][m] = (charge - rest) / world.valence[balance]
            series[f"n_cell_{balance}"][i][cell] += series[f"leak_{balance}"][i][m]
        for x in world.species:
            series[f"n_out_{x}"][i] = 0.0
        held = Held(world, [time], {n: v[[i]] for n, v in series.items()}, voltages[[i]], V0)
        for x in world.species:
            series[f"n_out_{x}"][i] = -identities.region_residual(world, held, x, [time])[0]
        for name in ("heat_leak", "heat_pump", "heat_channel"):
            if name in series:
                series[name][i] = 0.0
        held = Held(world, [time], {n: v[[i]] for n, v in series.items()}, voltages[[i]], V0)
        missing = -float(identities.energy(world, held, [time])[0, 0])
        for name, value in self._split(world, (missing * heat / heat.sum())[None, :]).items():
            series[name][i] = value[0]

    def as_rows(self, world, series: dict) -> dict:
        """Arrays as the table holds them: name to entity to a list."""
        return {
            name: {entity: array[:, i].tolist() for i, entity in enumerate(world.entities(name))}
            for name, array in series.items()
        }

    # ----- runs -----

    def ionic(self, name: str, run: dict, legacy, key: str) -> dict:
        """An ionic run's entry from a legacy run."""
        world = self.reg.worlds[run["world"]]
        entry = self.frame(name, run)
        entry["inputs"] = self.inputs(run)
        entry["t"], entry["rows"], entry["potential_t"], entry["potentials"] = self.rows(
            run, legacy, key
        )
        entry["steps"] = world.steps(run["step_s"]) + (
            self.reg.events(run) if world.assembly else 0
        )
        return entry

    def pool(self, name: str, run: dict) -> dict:
        """A pool run's entry: the captured arrays, the reference paths and the seeds, none of them
        moved.
        """
        world = self.reg.worlds[run["world"]]
        seed = run["seed_index"]
        start = self.reg.restart_time(run)
        entry = self.frame(name, run)
        entry["pool"], entry["path"] = {}, {}
        for position, (cell, pool) in enumerate(world.pools.items()):
            arrays = self.captures.pool_arrays(run["world"], seed, cell)
            entry["pool"][cell] = {
                "arrays": {n: a.tolist() for n, a in arrays.items()},
                "seed": pool["seeds"][seed],
                "stream_id": position,
            }
            ids = [pool["pool"]["world_id_start"] + i for i in range(pool["pool"]["worlds"])]
            paths = {
                str(w): copy.deepcopy(self.reg.reference_path(run["world"], seed, cell, w))
                for w in ids
            }
            if start is not None:
                paths = {
                    w: [event for event in path if event[0] > start] for w, path in paths.items()
                }
            entry["path"][cell] = paths
            entry["inputs"][cell] = {
                "channel": pool["channel"],
                "stream_id": pool["stream_id"],
                "seed": pool["seeds"][seed],
                "pool": copy.deepcopy(pool["pool"]),
            }
        if start is not None:
            entry["restart"] = {
                "time_s": start,
                "step_index": None,
                "through": "a file (fabricated)",
            }
        return entry

    def restart(self, name: str, run: dict, whole: dict) -> dict:
        """An ionic restart's entry: the uninterrupted run's rows from the restart's time on."""
        world = self.reg.worlds[run["world"]]
        start = self.reg.restart_time(run)
        entry = self.frame(name, run)
        entry["inputs"] = self.inputs(run)
        keep = [i for i, t in enumerate(whole["t"]) if t >= start - c.TIME_TOL_S]
        entry["t"] = [whole["t"][i] for i in keep]
        entry["rows"] = {
            s: {e: [v[i] for i in keep] for e, v in table.items()}
            for s, table in whole["rows"].items()
        }
        keep = [i for i, t in enumerate(whole["potential_t"]) if t > start + c.TIME_TOL_S]
        entry["potential_t"] = [whole["potential_t"][i] for i in keep]
        entry["potentials"] = {
            s: {e: [v[i] for i in keep] for e, v in table.items()}
            for s, table in whole["potentials"].items()
        }
        entry["steps"] = round((world.end_s - start) / run["step_s"])
        entry["restart"] = {
            "time_s": start,
            "step_index": round(start / run["step_s"]),
            "through": "a file (fabricated)",
        }
        return entry

    def tables(self) -> tuple:
        """(consumer to table, strings note): every registered run of every consumer, honest."""
        self._note = self.note()
        runs = {}
        for name, run in self.reg.runs.items():
            if self.reg.is_pool(run):
                runs[name] = self.pool(name, run)
            elif run["role"] == "judged":
                family = self.reg.families[run["family"]]
                step = STEPS[family.runs.index(name)]
                runs[name] = self.ionic(name, run, self.captures.run(family, step), name)
        for name, run in self.reg.runs.items():
            if name in runs:
                continue
            if run["role"] == "support":
                runs[name] = self.restart(name, run, runs[self.reg.restarted(run)])
            elif run["role"] == "plant":
                family = self.reg.families[run["family"]]
                step_s = self.captures.step_s(run["world"], "h4")
                planted = self.planted.run(
                    self.reg.profile["engine_plants"][run["variant"]]["planted_run"], family, step_s
                )
                runs[name] = self.ionic(name, run, planted, name)
        tables = {}
        for consumer in self.reg.consumers:
            mine = {
                name: runs[name]
                for name, run in self.reg.runs.items()
                if run["consumer"] == consumer
            }
            tables[consumer] = {
                "kind": c.TABLE_KIND,
                "part": c.PART,
                "consumer": consumer,
                "units": dict(c.UNITS),
                "missing": [],
                "runs": mine,
                "fabricated": MARK,
            }
        return tables, self._note

    def retry_tables(self, owed: list) -> dict:
        """Honest retry tables for the runs that a retry is owed, from the finest captured arrays
        under other moves.
        """
        self._note = self.note()
        tables = {}
        for name in owed:
            run = self.reg.retry_run(name)
            family = self.reg.families[run["family"]]
            entry = self.ionic(name, run, self.captures.run(family, "h4"), name)
            table = tables.setdefault(
                run["consumer"],
                {
                    "kind": c.TABLE_KIND,
                    "part": c.PART,
                    "consumer": run["consumer"],
                    "units": dict(c.UNITS),
                    "missing": [],
                    "runs": {},
                    "fabricated": MARK,
                },
            )
            table["runs"][name] = entry
        return tables


def digests(tables: dict) -> dict:
    """The sha256 of each table, by the bytes that `fabricate` writes."""
    return {
        f"table_{consumer}.json": strictjson.sha256(strictjson.encode(table))
        for consumer, table in tables.items()
    }


def _digest(name: str) -> str:
    import hashlib

    return hashlib.sha256(f"fabricated {name}".encode()).hexdigest()
