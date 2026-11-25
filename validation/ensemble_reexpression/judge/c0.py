"""C0: what the judge checks on the spec and on the reference side before it reads any engine table
(CRITERIA section 5).

Each clause counts what it checked and names every fault. The result also holds what stage 1 needs
of the captures: U_l and max |L3| of every family's entries, so that stage 1 opens no capture.
"""

from __future__ import annotations

import fnmatch
import json
import math
import re
from fractions import Fraction
from pathlib import Path

import numpy as np

from . import bands, identities, rules, strictjson
from . import constants as c
from .legacy import STEPS, Captures, Fault, Planted
from .registration import Registration, changes


class Clause:
    """One check of C0: how many items it looked at, its faults, and its numbers."""

    def __init__(self, name: str, where: str, what: str):
        self.name, self.where, self.what = name, where, what
        self.checked, self.faults, self.numbers, self.notes = 0, [], {}, []

    def check(self, good, fault: str) -> bool:
        """Count one item, and record the fault where it is not good."""
        self.checked += 1
        if not good:
            self.faults.append(fault)
        return bool(good)

    def record(self) -> dict:
        """The clause as JSON."""
        return {
            "clause": self.name,
            "where": self.where,
            "what": self.what,
            "status": "fail" if self.faults else "pass",
            "checked": self.checked,
            "faults": self.faults,
            "numbers": self.numbers,
            "notes": self.notes,
        }


def digits(value: float, count: int) -> str:
    """A number at so many significant digits, as the spec folder prints it."""
    return f"{value:.{count}g}"


def same(value: float, printed: float, count: int) -> bool:
    """True where a number, at so many significant digits, is the printed one."""
    return float(digits(value, count)) == printed


class LegacyRows:
    """The reference side as `identities` reads it: the captured series, and the pump's work from
    its cycles and its maintained fuel.
    """

    def __init__(self, world, run):
        self.world, self.run = world, run

    def get(self, series, times):
        """A series at given times, [time, entity]."""
        if series == "work_pump":
            cycles = self.run.series("pump", times)
            return cycles * np.array(
                [identities.fuel_energy(self.world, m) for m in self.world.pumps]
            )
        return self.run.series(series, times)

    def voltage(self, times):
        """The captured voltage at given times."""
        if self.world.assembly:
            return np.array([self.run.voltage(time) for time in times])
        return self.run.potential("voltage", times)

    def initial_voltage(self):
        """The captured voltage at time 0 (of `cell`, the declared one)."""
        return self.run.initial_voltage()

    def heats(self):
        """The captured heats. Legacy lumps a membrane's three."""
        present = self.world.data["scales"]
        return tuple(
            name for name in ("heat_membrane", "heat_junction", "heat_face") if name in present
        )


class C0:
    """The clauses, in order. `run()` gives the record."""

    def __init__(
        self,
        registration: Registration,
        captures: Captures | None = None,
        planted: Planted | None = None,
    ):
        self.reg = registration
        self.captures = captures or Captures(registration)
        self.planted = planted or Planted(registration)
        self.clauses = []
        self.legacy = {}

    def run(self) -> dict:
        """Every clause, and the record. A clause that cannot go on is a fault and not a crash."""
        steps = (
            self.spec_keys,
            self.run_list,
            self.literal_blocks,
            self.pins,
            self.captured_files,
            self.definitions,
            self.scales,
            self.grid,
            self.pools,
            self.paths,
            self.padding,
            self.legacy_classes,
            self.reference_identities,
            self.exposures,
            self.plant_files,
            self.controls,
            self.margins,
            self.mechanisms,
            self.power,
            self.structural,
            self.engine_plants,
            self.counts,
        )
        registered_only = (
            self.spec_keys,
            self.run_list,
            self.literal_blocks,
            self.pins,
            self.definitions,
            self.controls,
            self.margins,
            self.mechanisms,
        )
        if self.reg.rehearsal:
            steps = [step for step in steps if step not in registered_only]
        for step in steps:
            before = len(self.clauses)
            try:
                step()
            except (Fault, KeyError, IndexError, ValueError, TypeError, OSError) as error:
                clause = (
                    self.clauses[-1]
                    if len(self.clauses) > before
                    else self.clause(step.__name__, "", "")
                )
                clause.faults.append(f"could not go on: {type(error).__name__}: {error}")
        records = [clause.record() for clause in self.clauses]
        return {
            "kind": c.C0_KIND,
            "protocol": c.PROTOCOL,
            "part": c.PART,
            "status": "fail" if any(r["status"] == "fail" for r in records) else "pass",
            "spec_sha256": self.reg.files,
            "texts_sha256": {
                n: strictjson.sha256((self.reg.folder / n).read_bytes()) for n in self.texts()
            },
            "clauses": records,
            "legacy": self.legacy,
            "opened": {**self.captures.opened, **self.planted.opened},
            "not_done": NOT_DONE,
        }

    def texts(self) -> list:
        """The texts of Part 1 that the folder holds, by name."""
        amendments = sorted(p.name for p in self.reg.folder.glob("AMENDMENT-*.md"))
        return [n for n in (*TEXTS, *amendments) if (self.reg.folder / n).is_file()]

    def seeds(self, world) -> list:
        """The seed indices of the world's judged pool runs, or one None for a world
        without pools.
        """
        found = [
            r["seed_index"]
            for r in self.reg.runs.values()
            if r["world"] == world.name and r["role"] == "judged" and self.reg.is_pool(r)
        ]
        return sorted(found) if world.assembly else [None]

    def clause(self, name, where, what) -> Clause:
        """A new clause."""
        self.clauses.append(Clause(name, where, what))
        return self.clauses[-1]

    # ----- the spec folder -----

    def spec_keys(self):
        """Every key of the five data files."""
        k = self.clause(
            "spec_keys", "CRITERIA 5 (C0)", "every key of the data files, and their schemas"
        )

        def keys(value, wanted, what):
            k.check(
                isinstance(value, dict) and set(value) == set(wanted),
                f"{what}: keys {sorted(value)} and not {sorted(wanted)}",
            )

        inputs = self.reg.inputs
        keys(inputs, ("schema", "part", "constants", "worlds", "runs"), "inputs")
        k.check(
            inputs["schema"] == "ensemble-reexpression inputs, version 1" and inputs["part"] == 1,
            "inputs: schema or part",
        )
        keys(inputs["constants"], ("F_C_per_mol", "R_J_per_mol_K", "fmol_to_mol"), "constants")
        F = 6.02214076e23 * 1.602176634e-19
        R = 6.02214076e23 * 1.380649e-23
        k.check(
            inputs["constants"] == {"F_C_per_mol": F, "R_J_per_mol_K": R, "fmol_to_mol": 1e-15},
            "the constants are not SPEC 0's",
        )
        common = {"consumer", "ionic", "scales", "p", "amount_refs", "closure_terms_V"}
        for name, world in inputs["worlds"].items():
            if "pools" in world:
                keys(world, common | {"final_s", "summary_times_s", "pools", "coupling"}, name)
                keys(world["coupling"], ("law", "active", "inactive"), f"{name} coupling")
                k.check(
                    world["coupling"]
                    == {"law": "assembly_observable", "active": 1.0, "inactive": 0.0},
                    f"{name}: coupling",
                )
                k.check(
                    world["final_s"] == world["ionic"]["end_s"], f"{name}: final_s is not end_s"
                )
                k.check(
                    world["summary_times_s"][-1] == world["ionic"]["end_s"],
                    f"{name}: the last summary time is not end_s",
                )
                for cell, pool in world["pools"].items():
                    keys(
                        pool, ("channel", "stream_id", "pool", "harness", "seeds"), f"{name} {cell}"
                    )
                    k.check(len(pool["seeds"]) == 4, f"{name} {cell}: {len(pool['seeds'])} seeds")
            else:
                keys(world, common | {"history_times", "potential_times_s"}, name)
                keys(
                    world["history_times"],
                    ("first_s", "last_s", "spacing_s"),
                    f"{name} history_times",
                )
            k.check(world["p"] == 4, f"{name}: p is not 4")
            view = self.reg.worlds[name]
            names = {e.name for e in view.entries} | {e.name for e in view.zeros}
            wanted = set(world["scales"]) - {"energy_identity"}
            k.check(
                names - {n for n in names if n.endswith("_summary")} == wanted,
                f"{name}: the entries are not the scales'",
            )
        for run in inputs["runs"]:
            keys(
                run,
                (
                    "name",
                    "consumer",
                    "family",
                    "world",
                    "seed_index",
                    "world_id",
                    "step_s",
                    "role",
                    "variant",
                ),
                str(run.get("name")),
            )
        legacy = self.reg.legacy
        keys(
            legacy,
            ("schema", "part", "captures", "threshold_rule", "worlds", "integrated_capture"),
            "legacy",
        )
        k.check(
            set(legacy["worlds"]) == set(inputs["worlds"]), "legacy: its worlds are not the inputs'"
        )
        for name, block in legacy["worlds"].items():
            view = self.reg.worlds[name]
            k.check(
                set(block["entries"]) == {e.name for e in view.entries},
                f"legacy {name}: its entries are not the world's",
            )
            zeros = {e.name for e in view.zeros}
            k.check(
                set(block.get("zero_entries", [])) == zeros,
                f"legacy {name}: its zero entries are not the world's",
            )
            counts = [view.steps(s) for s in block["captured_steps_s"]]
            k.check(counts == block["captured_step_counts"], f"legacy {name}: step counts")
        paths = self.reg.paths
        keys(
            paths,
            ("schema", "made_by", "entry", "calcium_clusters", "events", "worlds"),
            "reference_paths",
        )
        pools = {n: w for n, w in self.reg.worlds.items() if w.assembly}
        keys(paths["worlds"], pools, "reference_paths worlds")
        for name, world in pools.items():
            keys(paths["worlds"][name], [f"s{i}" for i in range(4)], f"reference_paths {name}")
            for seed, cells in paths["worlds"][name].items():
                keys(cells, world.pools, f"reference_paths {name} {seed}")
                for cell, table in cells.items():
                    first, count = (
                        world.pools[cell]["pool"]["world_id_start"],
                        world.pools[cell]["pool"]["worlds"],
                    )
                    keys(
                        table,
                        [str(first + i) for i in range(count)],
                        f"reference_paths {name} {seed} {cell}",
                    )
        margins = self.reg.margins
        keys(
            margins,
            ("schema", "part", "date", "bands", "rule", "worlds", "pool_plants", "refused"),
            "margins",
        )
        keys(margins["worlds"], inputs["worlds"], "margins worlds")
        for name, block in margins["worlds"].items():
            keys(block, ("S_c", "S_l", "entries", "structural", "mechanisms"), f"margins {name}")
            k.check(
                set(block["entries"]) == {e.name for e in self.reg.worlds[name].entries},
                f"margins {name}: entries",
            )
        manifest = self.reg.manifest
        keys(manifest, ("schema", "part", "snapshot", "runs", "pool_plants"), "plants_manifest")
        run_keys = (
            "name kind base base_sha256 modify modified_leaves patch command environment affinity "
            "started finished seconds outcome "
            "definition_sha256 driver_sha256 capture_tool_sha256 outputs_sha256 output_folder"
        ).split()
        for run in manifest["runs"]:
            keys(run, run_keys, f"plants_manifest {run.get('name')}")
        k.check(
            len(manifest["runs"]) == 50,
            f"the manifest has {len(manifest['runs'])} runs, and 50 are named in the protocol",
        )
        k.check(
            sum(r["outcome"] != "completed" for r in manifest["runs"]) == 2,
            "the manifest does not hold two refused runs",
        )

    def run_list(self):
        """The registered runs, by SPEC section 4's rule."""
        k = self.clause(
            "run_list",
            "SPEC 3.1, 4",
            "the registered runs by rule: names, roles, steps, seeds, world IDs",
        )
        expected = []

        def add(name, consumer, family, world, seed, wid, step, role, variant):
            expected.append(
                {
                    "name": name,
                    "consumer": consumer,
                    "family": family,
                    "world": world,
                    "seed_index": seed,
                    "world_id": wid,
                    "step_s": step,
                    "role": role,
                    "variant": variant,
                }
            )

        fine = (2.5e-05, 1.25e-05, 6.25e-06)
        for world in ("jupiter_baseline", "jupiter_pump_release"):
            for h in fine:
                add(f"{world} h={h!r}", "jupiter", world, world, None, None, h, "judged", None)
        add(
            "jupiter_baseline h=2.5e-05 restart",
            "jupiter",
            None,
            "jupiter_baseline",
            None,
            None,
            2.5e-05,
            "support",
            "restart at 0.01",
        )
        add(
            "jupiter_baseline plant channel",
            "jupiter",
            "jupiter_baseline",
            "jupiter_baseline",
            None,
            None,
            6.25e-06,
            "plant",
            "EP1",
        )
        for h in (0.0001, 5e-05, 2.5e-05):
            add(
                f"integrated h={h!r}",
                "integrated",
                "integrated",
                "integrated",
                None,
                None,
                h,
                "judged",
                None,
            )
        for world in ("cell", "base"):
            for s in range(4):
                add(f"{world} s{s} pool", world, None, world, s, None, None, "judged", "pool")
            for s in range(4):
                for w in range(8):
                    for h in fine:
                        add(
                            f"{world} s{s} w{w} h={h!r}",
                            world,
                            f"{world} s{s} w{w}",
                            world,
                            s,
                            w,
                            h,
                            "judged",
                            "ionic",
                        )
            add(
                f"{world} s0 pool restart",
                world,
                None,
                world,
                0,
                None,
                None,
                "support",
                "pool restart at 0.01",
            )
        add("base plant swapped", "base", "base s0 w2", "base", 0, 2, 6.25e-06, "plant", "EP2")
        wanted = {run["name"]: run for run in expected}
        k.check(
            len(self.reg.runs) == self.reg.profile["runs"] == len(wanted),
            f"{len(self.reg.runs)} runs",
        )
        for name in sorted(set(wanted) | set(self.reg.runs)):
            k.check(
                wanted.get(name) == self.reg.runs.get(name), f"the run {name!r} is not the rule's"
            )
        for family in self.reg.families.values():
            h1, h2, h3 = family.steps_s if len(family.steps_s) == 3 else (0, 0, 0)
            k.check(
                h2 == h1 / 2 and h3 == h2 / 2, f"{family.name}: its steps are not three halvings"
            )

    def literal_blocks(self):
        """SPEC section 2.5's literal blocks against the inputs."""
        k = self.clause(
            "literal_blocks",
            "SPEC 2.5",
            "the literal blocks of SPEC.md equal the inputs', as JSON values",
        )
        text = (self.reg.folder / "SPEC.md").read_text()
        blocks = [
            strictjson.loads(b.encode()) for b in re.findall(r"```json\n(.*?)\n```", text, re.S)
        ]
        k.check(len(blocks) == 4, f"{len(blocks)} literal blocks, and not 4")
        worlds = self.reg.inputs["worlds"]
        k.check(blocks[0] == worlds["jupiter_baseline"]["ionic"], "the block of jupiter")
        release = json.loads(json.dumps(blocks[0]))
        release["controls"]["pump"] = {
            m: [[0.0, 1.0], [0.005, 0.0], [0.01, 1.0]] for m in release["membranes"]
        }
        k.check(
            release == worlds["jupiter_pump_release"]["ionic"], "the block of jupiter_pump_release"
        )
        k.check(blocks[1] == worlds["cell"]["ionic"], "the block of cell")
        base = json.loads(json.dumps(blocks[0]))
        base["controls"]["channel"] = blocks[1]["controls"]["channel"]
        k.check(base == worlds["base"]["ionic"], "the block of base")
        k.check(blocks[2] == worlds["integrated"]["ionic"], "the block of integrated")
        pool = worlds["cell"]["pools"]["cell_0"]
        wanted = {
            "channel": pool["channel"],
            "stream_id": pool["stream_id"],
            "seed": pool["seeds"][0],
            "pool": pool["pool"],
        }
        k.check(blocks[3] == wanted, "the block of a pool run")
        for cell, block in worlds["base"]["pools"].items():
            changed = dict(pool["pool"], k_close_s_inv=1000.0, k_off_s_inv=300.0, worlds=8)
            k.check(
                block["pool"] == changed,
                f"base {cell}: its pool is not cell's with the three changes",
            )

    # ----- the captures -----

    def pins(self):
        """The manifests' sha256, and what they say of the snapshot, the machine and the jobs."""
        k = self.clause(
            "pins",
            "SPEC 7, legacy_part1.json",
            "the pinned manifests, the snapshot's record and the machine",
        )
        for key in ("captures", "integrated_capture"):
            block = self.reg.legacy[key]
            manifest, origin = self.captures.manifest(key), self.captures.origin(key)
            k.checked += 2
            for name, value in (("science", manifest), ("origin", origin)):
                snapshot = value["snapshot"]
                k.check(
                    snapshot["manifest_sha256"] == block["snapshot_manifest_sha256"],
                    f"{key} {name}: the snapshot's manifest",
                )
                k.check(
                    snapshot["git_revision"] == block["snapshot_revision"],
                    f"{key} {name}: the snapshot's revision",
                )
                k.check(
                    snapshot["clean"] is True and snapshot["patch_sha256"] == c.EMPTY_SHA256,
                    f"{key} {name}: not clean",
                )
            k.check(
                manifest["origin"]["manifest_sha256"] == block["origin_manifest_sha256"],
                f"{key}: the origin of the jobs",
            )
            k.check(set(manifest["counts"]) == {"ok"}, f"{key}: a job did not end ok")
            k.check(
                manifest["run"]["cpu_model"] == self.reg.legacy["captures"]["cpu_model"],
                f"{key}: the machine",
            )
        block = self.reg.legacy["captures"]
        path = Path(block["root"]) / block["snapshot"] / "SNAPSHOT.json"
        k.check(
            strictjson.sha256(path.read_bytes()) == block["snapshot_manifest_sha256"],
            "the snapshot's manifest file",
        )
        k.notes.append(
            "The snapshot's manifest file is hashed and not read. The snapshot of "
            "integrated_capture is outside the captures' root, so its recorded sha256 is compared "
            "and no file is opened."
        )

    def captured_files(self):
        """Every file of every captured run that Part 1 names."""
        k = self.clause(
            "captured_files",
            "SPEC 7",
            "every file of the captured runs of Part 1, against the manifests' sha256",
        )
        for world, where in self.reg.profile["captures"].items():
            for step in STEPS:
                for seed in self.seeds(self.reg.worlds[world]):
                    folder = where["folder"].format(step=step, seed=seed) + "/"
                    names = [
                        n
                        for n in self.captures.manifest(where["set"])["files"]
                        if n.startswith(folder)
                    ]
                    k.check(names, f"{world}: no file in {folder}")
                    for name in names:
                        try:
                            self.captures.read(where["set"], name)
                            k.checked += 1
                        except Fault as error:
                            k.check(False, str(error))

    def definitions(self):
        """The blocks of the inputs against the captured definitions, leaf by leaf, and the orders
        of their entities.
        """
        k = self.clause(
            "definitions",
            "SPEC 2.1, 2.2, 2.5",
            "every block and pool of the inputs against the captured definitions, value by value",
        )
        worst_anchor = 0.0
        for name, world in self.reg.worlds.items():
            for seed in self.seeds(world):
                for step in STEPS:
                    whole = self.captures.definition(name, step, seed)
                    ionic = whole["ionic"] if world.assembly else whole["definition"]
                    k.check(
                        ionic["execution"]["dt"] == self.captures.step_s(name, step),
                        f"{name} {step}: its step",
                    )
                    block = canonical(ionic, world)
                    k.check(
                        block == world.block,
                        f"{name} {step} s{seed}: the block differs: "
                        f"{differences(block, world.block)}",
                    )
                    for group in (
                        "cells",
                        "outside",
                        "membranes",
                        "junctions",
                        "faces",
                        "channels",
                    ):
                        mine, theirs = world.block[group], block[group]
                        k.check(list(mine) == list(theirs), f"{name} {step}: the order of {group}")
                    k.check(
                        list(block["species"]) == list(world.species),
                        f"{name} {step}: the order of the species",
                    )
                    if world.assembly:
                        self._pool_definition(k, name, world, whole, seed)
            F, unit = world.constants["F_C_per_mol"], world.constants["fmol_to_mol"]
            for group in ("cells", "outside"):
                for v in world.block[group].values():
                    total = math.fsum(
                        world.valence[x] * v["initial_amount_fmol"][x] for x in world.species
                    )
                    gap = (
                        F * unit * (total + v["fixed_charge_equivalent_fmol"])
                        - v["initial_charge_C"]
                    )
                    worst_anchor = max(worst_anchor, abs(gap))
        k.numbers["largest_charge_anchor_gap_C"] = digits(worst_anchor, 2)
        k.check(
            worst_anchor < 1e-20,
            "a fixed charge departs from its rule by more than the anchor floor (1e-20 C)",
        )

    def _pool_definition(self, k, name, world, whole, seed):
        found = (
            [{"cell_id": "cell_0", "stream_id": 0, "pool": whole["pool"]}]
            if "pool" in whole
            else whole["pools"]
        )
        couplings = (
            [whole["coupling"]] if "coupling" in whole else [p["coupling"] for p in whole["pools"]]
        )
        k.check(
            [p["cell_id"] for p in found] == list(world.pools), f"{name}: the order of the pools"
        )
        for pool, coupling in zip(found, couplings, strict=True):
            mine = world.pools[pool["cell_id"]]
            k.check(pool["stream_id"] == mine["stream_id"], f"{name} {pool['cell_id']}: stream_id")
            k.check(
                pool["pool"]["seed"] == mine["seeds"][seed],
                f"{name} {pool['cell_id']} s{seed}: the seed",
            )
            for key, value in pool["pool"].items():
                if key in ("seed", "model"):
                    continue
                place = mine["harness"] if key in mine["harness"] else mine["pool"]
                k.check(place.get(key) == value, f"{name} {pool['cell_id']}: {key}")
            levels = (coupling["active_availability"], coupling["inactive_availability"])
            k.check(
                levels == (world.data["coupling"]["active"], world.data["coupling"]["inactive"]),
                f"{name}: the levels",
            )

    def scales(self):
        """The scales, the amount references and the closures by rule."""
        k = self.clause(
            "scales",
            "SPEC 5, 6",
            "scales, amount_refs, closure_terms_V and p by their rules, to 1e-12 relative",
        )
        worst = 0.0
        for name, world in self.reg.worlds.items():
            for what, mine, theirs in zip(
                ("scales", "amount_refs", "closure_terms_V"),
                rules.scales(world),
                (world.data["scales"], world.data["amount_refs"], world.data["closure_terms_V"]),
                strict=True,
            ):
                k.check(
                    set(mine) == set(theirs),
                    f"{name} {what}: keys {sorted(set(mine) ^ set(theirs))}",
                )
                for key in theirs:
                    a, b = mine.get(key, math.nan), theirs[key]
                    gap = abs(a - b) / abs(b) if b else abs(a)
                    worst = max(worst, gap)
                    k.check(
                        gap <= c.ECHO_RTOL,
                        f"{name} {what} {key}: {a!r} by rule and {b!r} in the inputs",
                    )
        k.numbers["largest_relative_difference"] = worst

    def grid(self):
        """Every registered time on every registered grid, and the events' distances from it."""
        k = self.clause(
            "grid",
            "SPEC 3.2, 4",
            "registered times on the registered grids (2 eps t), and the events' distances from "
            "them",
        )
        worst = 0.0
        for family in self.reg.families.values():
            world = family.world
            times = (
                set(world.row_times)
                | set(world.potential_times)
                | set(world.identity_times)
                | {world.end_s}
            )
            for schedules in world.block["controls"].values():
                if isinstance(schedules, dict):
                    times |= {time for schedule in schedules.values() for time, _ in schedule}
            times |= {
                t
                for t in (
                    self.reg.restart_time(r)
                    for r in self.reg.runs.values()
                    if r["world"] == world.name
                )
                if t
            }
            for step in (*family.steps_s, family.retry_step):
                k.check(
                    step > 0 and abs(world.end_s / step - round(world.end_s / step)) < 1e-9,
                    f"{family.name}: end_s over {step!r}",
                )
                for time in times:
                    point = round(time / step) * step
                    gap = abs(time - point)
                    if gap > c.GRID_TOL * time and self.reg.rehearsal:
                        k.checked += 1
                        k.notes.append(f"{family.name}: {time!r} s is off the grid of {step!r} s")
                        continue
                    k.check(
                        gap <= c.GRID_TOL * time,
                        f"{family.name}: {time!r} s is off the grid of {step!r} s",
                    )
                    if time:
                        worst = max(worst, gap / (c.EPS * time))
        k.numbers["largest_gap_over_eps_t"] = digits(worst, 2)
        if self.reg.rehearsal:
            return
        steps = (2.5e-05, 1.25e-05, 6.25e-06, 3.125e-06, 1.5625e-06)
        nearest, stage = (Fraction(1), None), (Fraction(1), None)
        events = 0
        for name, seeds in self.reg.paths["worlds"].items():
            for seed, cells in seeds.items():
                for cell, table in cells.items():
                    for wid, path in table.items():
                        for time, _ in path:
                            events += 1
                            for step in steps:
                                for half, best in ((1, "grid"), (2, "stage")):
                                    h = Fraction(step) / half
                                    gap = abs(Fraction(time) / h - round(Fraction(time) / h)) / half
                                    if best == "grid" and gap < nearest[0]:
                                        nearest = (gap, (name, seed, cell, wid, time, step))
                                    if best == "stage" and gap < stage[0]:
                                        stage = (gap, (name, seed, cell, wid, time, step))
        k.check(events == self.reg.paths["events"] == 683, f"{events} events")
        k.numbers["nearest_event_over_step"] = digits(float(nearest[0]), 4)
        k.numbers["nearest_event"] = list(nearest[1])
        k.numbers["nearest_stage_over_step"] = digits(float(stage[0]), 4)
        k.numbers["nearest_stage_event"] = list(stage[1])
        k.check(
            digits(float(nearest[0]), 4) == "0.0001779",
            "the nearest event is not at the published 1.779e-4 of a step",
        )
        k.check(
            digits(float(stage[0]), 4) == "8.893e-05",
            "the nearest stage time is not at the published 8.893e-5 of a step",
        )
        where = ("cell", "s2", "cell_0", "28", 0.007676562222089895)
        k.check(
            nearest[1][:5] == where and stage[1][:5] == where,
            "the nearest event is not the published one",
        )

    def pools(self):
        """The captured pool arrays: one reference per seed, whatever the step."""
        k = self.clause(
            "pools",
            "READOUTS 4",
            "the 19 captured pool arrays are identical at h, h/2 and h/4, and finite",
        )
        for name, world in self.reg.worlds.items():
            if not world.assembly:
                continue
            for seed in self.seeds(world):
                for cell, pool in world.pools.items():
                    fine = self.captures.pool_arrays(name, seed, cell)
                    for step in STEPS[:2]:
                        other = self.captures.pool_arrays(name, seed, cell, step)
                        for array in c.POOL_ARRAYS:
                            good = (
                                fine[array].dtype == other[array].dtype
                                and fine[array].tobytes() == other[array].tobytes()
                            )
                            k.check(good, f"{name} s{seed} {cell} {array}: {step} differs from h4")
                    for array in c.POOL_ARRAYS:
                        k.check(
                            len(fine[array]) == pool["pool"]["worlds"],
                            f"{name} s{seed} {cell} {array}: worlds",
                        )
                        k.check(
                            np.all(np.isfinite(fine[array])),
                            f"{name} s{seed} {cell} {array}: a value that is not finite",
                        )

    def paths(self):
        """The reference paths against the captured pool arrays."""
        k = self.clause(
            "paths",
            "SPEC 3.2, READOUTS 4",
            "the reference paths against the captured counts, last times and final masks",
        )
        for name, world in self.reg.worlds.items():
            if not world.assembly:
                continue
            for seed in self.seeds(world):
                for cell, pool in world.pools.items():
                    arrays = self.captures.pool_arrays(name, seed, cell)
                    for i in range(pool["pool"]["worlds"]):
                        path = self.reg.reference_path(
                            name, seed, cell, pool["pool"]["world_id_start"] + i
                        )
                        what = f"{name} s{seed} {cell} w{i}"
                        times = [time for time, _ in path]
                        k.check(len(path) == int(arrays["event_count"][i]), f"{what}: events")
                        last = times[-1] if times else 0.0
                        k.check(
                            last == float(arrays["last_event_time_s"][i]),
                            f"{what}: the last event's time",
                        )
                        k.check(
                            all(a < b for a, b in zip(times, times[1:], strict=False)),
                            f"{what}: the times do not increase",
                        )
                        k.check(
                            not times or (times[0] > 0 and times[-1] <= world.end_s),
                            f"{what}: a time outside the run",
                        )
                        closed = (
                            int(arrays["bonds"][i]).bit_count()
                            >= int(arrays["occupied"][i]).bit_count()
                        )
                        level = path[-1][1] if path else 1
                        k.check(
                            level == int(closed),
                            f"{what}: the last availability is not the final masks'",
                        )
                        k.check(
                            all(value in (0, 1) for _, value in path),
                            f"{what}: an availability that is not 0 or 1",
                        )

    def padding(self):
        """Captured slots past the declared entities hold zeros (READOUTS section 7)."""
        k = self.clause(
            "padding",
            "READOUTS 7, SPEC 2.3",
            "slots past the declared entities hold zeros, and an absent mechanism's arrays are "
            "zero",
        )
        for family in self.reg.families.values():
            world = family.world
            run = self.captures.run(family, "h4")
            sizes = {
                "amount_increment": (2, len(world.cells)),
                "extracellular_amount_increment": (2, len(world.regions)),
                "leak_transferred": (2, len(world.membranes)),
                "junction_transferred": (2, len(world.junctions)),
                "face_transferred": (2, len(world.faces)),
                "pump_cycles": (1, len(world.membranes)),
                "gate": (2, len(world.channels)),
                "channel_transferred": (1, len(world.channels)),
                "junction_gate": (1, len(world.junctions)),
                "dissipated_energy_pJ": (1, len(world.membranes)),
                "junction_dissipated_energy_pJ": (1, len(world.junctions)),
                "face_dissipated_energy_pJ": (1, len(world.faces)),
            }
            for name, (axis, size) in sizes.items():
                if name in run.raw:
                    rest = run.raw[name][:, size:] if axis == 1 else run.raw[name][:, :, size:]
                    k.check(
                        not np.any(rest),
                        f"{family.name} {name}: a slot past the declared entities is not zero",
                    )
            if not world.pumps:
                k.check(
                    not np.any(run.raw["pump_cycles"]),
                    f"{family.name}: a pump's cycles without a pump",
                )
            if world.zero_routes:
                k.check(
                    not np.any(run.raw["leak_transferred"]),
                    f"{family.name}: a leak without a permeability",
                )
            for entry in world.zeros:
                for step in STEPS:
                    whole = self.captures.run(family, step)
                    values = (
                        whole.series(entry.series, whole.times)
                        if not world.assembly
                        else whole.entry(entry)
                    )
                    k.check(
                        not np.any(values),
                        f"{family.name} {entry.name} {step}: the captured zero is not zero",
                    )

    def legacy_classes(self):
        """The legacy side's classes by the order rule, and U_l and max |L3| of every family's
        entries.
        """
        k = self.clause(
            "legacy_classes",
            "CRITERIA 4.3",
            "the captured entries' classes by rule, against legacy_part1.json, and no C0 fault "
            "among them",
        )
        counts = {}
        for name, world in self.reg.worlds.items():
            steps_l = self.captures.steps(name)
            printed = self.reg.legacy["worlds"][name].get("entries", {})
            found = {entry.name: [] for entry in world.entries}
            for family in [f for f in self.reg.families.values() if f.world is world]:
                runs = [self.captures.run(family, step) for step in STEPS]
                table = self.legacy.setdefault(family.name, {"S_l": steps_l, "entries": {}})
                for entry in world.entries:
                    arrays = [run.entry(entry) for run in runs]
                    k.check(
                        all(np.all(np.isfinite(a)) for a in arrays),
                        f"{family.name} {entry.name}: not finite",
                    )
                    d2, d1, U_l = bands.estimate(*arrays, c.LEGACY_ORDER)
                    theta = bands.legacy_threshold(entry, steps_l)
                    order_class = bands.classify(d2, d1, theta, c.LEGACY_ORDER)
                    size = bands.largest(arrays[2])
                    q = bands.observed_order(d2, d1)
                    table["entries"][entry.name] = {
                        "d2": d2,
                        "d1": d1,
                        "U_l": U_l,
                        "theta": theta,
                        "class": order_class,
                        "order": q,
                        "largest": size,
                    }
                    found[entry.name].append((d2, d1, theta, size, order_class, q))
                    counts[order_class] = counts.get(order_class, 0) + 1
                    bad = order_class == "resolved outside its window" or d1 > theta >= d2
                    k.check(not bad, f"{family.name} {entry.name}: {order_class}, a C0 fault")
            for entry in world.entries:
                if (self.reg.rehearsal and entry.name not in printed) or self.reg.only is not None:
                    continue
                rows, theirs = found[entry.name], printed[entry.name]
                if world.assembly:
                    tally = {}
                    for row in rows:
                        tally[row[4]] = tally.get(row[4], 0) + 1
                    good = tally == theirs["classes"]
                    good &= same(max(r[0] for r in rows), theirs["largest_d2"], 3) and same(
                        max(r[1] for r in rows), theirs["largest_d1"], 3
                    )
                    good &= same(rows[0][2], theirs["threshold"], 3) and same(
                        max(r[3] for r in rows), theirs["largest"], 3
                    )
                    good &= same(
                        min(r[3] for r in rows), theirs["smallest_of_the_families_largest"], 3
                    )
                else:
                    d2, d1, theta, size, order_class, q = rows[0]
                    good = (
                        order_class == theirs["class"]
                        and same(d2, theirs["d2"], 3)
                        and same(d1, theirs["d1"], 3)
                    )
                    good &= same(theta, theirs["threshold"], 3) and same(size, theirs["largest"], 3)
                    good &= (q is None) == (theirs["observed_order"] is None) and (
                        q is None or round(q, 2) == theirs["observed_order"]
                    )
                k.check(good, f"{name} {entry.name}: not the printed class or numbers")
        k.numbers["classes"] = counts
        k.check(
            self.reg.rehearsal or set(counts) == {"unresolved"},
            f"the spec says that every captured entry is unresolved, and the classes are {counts}",
        )

    def reference_identities(self):
        """The balances, the capacitor and the energy identity on the captured arrays at h/4."""
        k = self.clause(
            "reference_identities",
            "READOUTS 5",
            "every identity on the captured arrays at h/4, within its bound at U_c = 0 and e_store "
            "= 0",
        )
        worst = {"balance": 0.0, "capacitor": 0.0, "energy_identity": 0.0}
        for family in self.reg.families.values():
            world, steps = family.world, self.captures.steps(family.world.name)
            rows = LegacyRows(world, self.captures.run(family, "h4"))
            times = (world.end_s,) if world.assembly else world.identity_times
            for species in world.species:
                for kind, residual in (
                    ("cells", identities.cell_residual),
                    ("regions", identities.region_residual),
                    ("closed", identities.closed_residual),
                ):
                    value = bands.largest(residual(world, rows, species, times))
                    bound = identities.balance_bound(world, kind, species, steps)[1]
                    k.check(value <= bound, f"{family.name}: the balance of {kind}, {species}")
                    if bound:
                        worst["balance"] = max(worst["balance"], value / bound)
            at = (world.end_s,) if world.assembly else world.potential_times
            value = bands.largest(identities.capacitor_residual(world, rows, at))
            bound = identities.capacitor_bound(world, steps)[1]
            k.check(value <= bound, f"{family.name}: the capacitor")
            worst["capacitor"] = max(worst["capacitor"], value / bound)
            value = bands.largest(identities.energy(world, rows, times))
            bound = world.energy.e_round(steps) + world.energy.e_close()
            k.check(value <= bound, f"{family.name}: the energy identity")
            worst["energy_identity"] = max(worst["energy_identity"], value / bound)
        k.numbers["largest_over_bound"] = {name: digits(value, 2) for name, value in worst.items()}
        k.numbers["published"] = {
            "balance": "5.3e-04",
            "capacitor": "3.1e-06",
            "energy_identity": "1.1e-06",
        }
        k.notes.append(
            "Both residuals are rounding of their own formation, so the last digit of the "
            "published maxima is not a criterion."
        )
        k.notes.append(
            "The captures hold no row of base at 5 and 10 ms but for the voltage and the channel's "
            "transfer, so cell and base are formed at 20 ms alone."
        )

    def exposures(self):
        """The reference paths' exposures against the captured ones."""
        k = self.clause(
            "exposures",
            "READOUTS 5",
            "the exposure of every reference path, against the captured one at h/4, within its "
            "bound",
        )
        worst = 0.0
        for name, world in self.reg.worlds.items():
            if not world.assembly:
                continue
            for seed in self.seeds(world):
                for cell, pool in world.pools.items():
                    captured, segments = self.captures.exposure(name, seed, cell)
                    for i in range(pool["pool"]["worlds"]):
                        path = self.reg.reference_path(
                            name, seed, cell, pool["pool"]["world_id_start"] + i
                        )
                        value = identities.exposure(path, world.end_s)
                        bound = identities.exposure_bound(world.end_s, segments[i])
                        gap = abs(value - float(captured[i]))
                        worst = max(worst, gap / bound)
                        k.check(gap <= bound, f"{name} s{seed} {cell} w{i}: the exposure")
        k.numbers["largest_over_bound"] = digits(worst, 2)

    # ----- the planted runs -----

    def plant_files(self):
        """The planted runs' files, and their definitions against their bases with the declared
        change.
        """
        k = self.clause(
            "plant_files",
            "CRITERIA 5 (C0), plants_manifest.json",
            "every planted run's outputs by sha256, and its definition as its base with the "
            "declared change alone",
        )
        root = Path(self.reg.legacy["captures"]["root"])
        for name, run in self.planted.runs.items():
            for relative in run["outputs_sha256"]:
                try:
                    self.planted.read(name, relative)
                    k.checked += 1
                except Fault as error:
                    k.check(False, str(error))
            k.check(
                run["definition_sha256"] == run["outputs_sha256"].get("definition.json"),
                f"{name}: the definition's sha256",
            )
            base = Path(run["base"])
            k.check(
                self.reg.rehearsal or base.is_relative_to(root),
                f"{name}: its base is not a captured definition",
            )
            data = base.read_bytes()
            k.check(
                strictjson.sha256(data) == run["base_sha256"], f"{name}: the sha256 of its base"
            )
            mine = strictjson.loads(self.planted.read(name, "definition.json"))
            theirs = strictjson.loads(data)
            if run["kind"] == "ionic":
                mine, theirs = mine["definition"], theirs["definition"]
            leaves = []
            for item in run["modify"]:
                leaves.append(modify(theirs, [p for p in item["path"].split("/") if p], item))
            k.check(
                leaves == run["modified_leaves"] or sum(leaves) == sum(run["modified_leaves"]),
                f"{name}: {leaves} leaves changed",
            )
            k.check(
                mine == theirs, f"{name}: its definition is not its base with the declared change"
            )
        k.numbers["runs"] = len(self.planted.runs)
        for pool in self.reg.manifest.get("pool_plants", []):
            k.notes.append(
                f"{pool['name']}: its output lies outside the folder that the judge may open, so "
                f"its sha256 is not checked. Class E has no margin."
            )

    def controls(self):
        """The unpatched runs against the captures, bit for bit."""
        k = self.clause(
            "controls",
            "PLANTS 8",
            "every unpatched run of the snapshot equals the captured arrays bit for bit",
        )
        published = {
            "jupiter_baseline": 364,
            "jupiter_pump_release": 364,
            "integrated": 288,
            "base": 35,
            "cell": 33,
        }
        tally = {}
        for name, run in self.planted.runs.items():
            match = re.fullmatch(r"control (\w+)(?: s0)? h4(?: again)?", name)
            if not match:
                continue
            world = match.group(1)
            where = self.reg.profile["captures"][world]
            folder = where["folder"].format(step="h4", seed=0)
            files = [f for f in run["outputs_sha256"] if f.endswith(".npz")]
            count = 0
            for relative in files:
                mine = _load(self.planted.read(name, relative))
                theirs = _load(
                    self.captures.read(where["set"], folder + relative.removeprefix("run"))
                )
                k.check(set(mine) == set(theirs), f"{name} {relative}: other arrays")
                for array in theirs:
                    count += 1
                    good = (
                        array in mine
                        and mine[array].dtype == theirs[array].dtype
                        and mine[array].shape == theirs[array].shape
                    )
                    k.check(
                        good and mine[array].tobytes() == theirs[array].tobytes(),
                        f"{name} {relative} {array}: not the capture's bits",
                    )
            k.check(
                count == published[world],
                f"{name}: {count} arrays, and {published[world]} are published",
            )
            tally.setdefault(world, []).append(count)
        k.numbers["arrays"] = tally
        wanted = {
            "jupiter_baseline": 2,
            "jupiter_pump_release": 2,
            "integrated": 2,
            "base": 1,
            "cell": 1,
        }
        k.check({w: len(v) for w, v in tally.items()} == wanted, f"the controls are {tally}")

    def margins(self):
        """Every ratio, band, largest value and margin of margins.json, formed again from the
        planted runs.
        """
        k = self.clause(
            "margins",
            "PLANTS 1, 8, CRITERIA 5 (C0)",
            "every margin of margins.json formed again from the planted runs it names, at four "
            "digits",
        )
        smallest, smallest_home = (math.inf, None), (math.inf, None)
        for name, world in self.reg.worlds.items():
            block = self.reg.margins["worlds"][name]
            families = self._plant_families(world)
            steps_c, steps_l = world.steps(families[0].steps_s[2]), self.captures.steps(name)
            k.check((block["S_c"], block["S_l"]) == (steps_c, steps_l), f"{name}: S_c and S_l")
            plants = {}
            for run_name in self.planted.runs:
                match = re.fullmatch(r"PW-(\w+) (\w+)", run_name)
                if match and match.group(2) == name:
                    plants[match.group(1)] = run_name
            for entry in world.entries:
                printed = block["entries"][entry.name]
                data = []
                for family in families:
                    honest = self.captures.run(family, "h4").entry(entry)
                    U_l = self.legacy[family.name]["entries"][entry.name]["U_l"]
                    beta = bands.band(entry, 0.0, U_l, steps_c, steps_l)["beta"]
                    moved = {
                        plant: bands.largest(
                            self.planted.run(
                                run_name, family, self.captures.step_s(name, "h4")
                            ).entry(entry)
                            - honest
                        )
                        for plant, run_name in plants.items()
                    }
                    data.append((beta, bands.largest(honest), moved))
                # The published margin of an assembly entry is the smallest distance over the band
                # with the largest U_l of the worlds.
                # It is at most the smallest margin of the worlds, and departs from it in the fourth
                # digit of two entries.
                wide = max(d[0] for d in data)
                ratio = {plant: min(d[2][plant] / d[1] for d in data) for plant in plants}
                margin = {plant: min(d[2][plant] for d in data) / wide for plant in plants}
                by_world = {plant: min(d[2][plant] / d[0] for d in data) for plant in plants}
                best = max(ratio, key=ratio.get)
                homes = list(printed["home_plants"])
                source = homes[0] if printed["home"] else best
                what = f"{name} {entry.name}"
                k.check(
                    printed["ratio_from"] == source,
                    f"{what}: its ratio is from {printed['ratio_from']}, by rule {source}",
                )
                k.check(same(ratio[source], printed["ratio"], 4), f"{what}: the ratio")
                k.check(same(margin[source], printed["margin"], 4), f"{what}: the margin")
                if not same(by_world[source], printed["margin"], 4):
                    k.notes.append(
                        f"{what}: the smallest margin by world is {digits(by_world[source], 4)}, "
                        f"and the printed one {digits(printed['margin'], 4)}"
                    )
                k.check(
                    margin[source] <= by_world[source] * (1 + 1e-12),
                    f"{what}: the printed margin is above the smallest by world",
                )
                k.check(same(wide, printed["band_at_U_c_0"], 4), f"{what}: the band")
                k.check(
                    same(min(d[1] for d in data), printed["largest"], 4), f"{what}: the largest"
                )
                for plant, numbers in printed["home_plants"].items():
                    good = same(ratio[plant], numbers["ratio"], 4) and same(
                        margin[plant], numbers["margin"], 4
                    )
                    k.check(good, f"{what}: the home plant {plant}")
                if "best_ratio" in printed:
                    good = (
                        best == printed["best_from"]
                        and same(ratio[best], printed["best_ratio"], 4)
                        and same(margin[best], printed["best_margin"], 4)
                    )
                    k.check(good, f"{what}: the plant that moves it most")
                elif printed["home"]:
                    k.check(
                        best == source,
                        f"{what}: another plant moves it more, and margins.json does not say so",
                    )
                k.check(printed["margin"] >= c.PLANT_RULE, f"{what}: its margin is below the rule")
                if margin[source] < smallest[0]:
                    smallest = (margin[source], what)
                if printed["home"] and margin[source] < smallest_home[0]:
                    smallest_home = (margin[source], what)
        k.numbers["smallest_margin"] = [digits(smallest[0], 2), smallest[1]]
        k.numbers["smallest_home_margin"] = [digits(smallest_home[0], 1), smallest_home[1]]
        k.check(
            digits(smallest[0], 2) == "1.3e+03" and smallest[1] == "cell n_out_Cl",
            "the smallest margin is not the published one",
        )
        k.check(
            digits(smallest_home[0], 1) == "2e+04" and smallest_home[1] == "integrated voltage",
            "the smallest home margin is not the published one",
        )
        refused = {
            n: r["outcome"] for n, r in self.planted.runs.items() if r["outcome"] != "completed"
        }
        k.check(refused == self.reg.margins["refused"], "the refused plants are not margins.json's")

    def _plant_families(self, world):
        """The families of seed 0, over which an assembly world's smallest is taken."""
        return [
            f for f in self.reg.families.values() if f.world is world and f.seed_index in (None, 0)
        ]

    def mechanisms(self):
        """Every mechanism of every consumer has a home entry with a ratio (PLANTS section 2)."""
        k = self.clause(
            "mechanisms",
            "PLANTS 2, CRITERIA 5 (C0)",
            "every mechanism has a home entry with a ratio, and the list is PLANTS section 2's",
        )
        homes = {
            "leak permeability": ["leak_Na", "leak_K", "leak_Cl"],
            "channel permeability": ["channel_K", "channel_K_summary"],
            "channel kinetics": ["gate_m", "gate_h"],
            "Na/K pump": ["pump"],
            "junction permeability": ["junction_Na", "junction_K", "junction_Cl"],
            "junction gate": ["junction_gate"],
            "faces": ["face_Na", "face_K", "face_Cl"],
            "electrical closure": ["voltage", "phi_out"],
        }
        held = {
            "jupiter": set(homes),
            "base": set(homes),
            "cell": {
                "leak permeability",
                "channel permeability",
                "channel kinetics",
                "Na/K pump",
                "electrical closure",
            },
            "integrated": {"junction permeability", "junction gate", "electrical closure"},
        }
        closure = {"jupiter": "pump", "base": "pump", "cell": "leak", "integrated": "junction"}
        for name, world in self.reg.worlds.items():
            block = self.reg.margins["worlds"][name]
            k.check(set(block["mechanisms"]) == held[world.consumer], f"{name}: its mechanisms")
            for mechanism, entries in block["mechanisms"].items():
                wanted = [e for e in homes[mechanism] if e in world.by_name]
                k.check(
                    list(entries) == wanted and wanted,
                    f"{name} {mechanism}: its homes are {list(entries)}",
                )
                for entry, plants in entries.items():
                    k.check(
                        block["entries"][entry]["home"] is True
                        and plants == block["entries"][entry]["home_plants"],
                        f"{name} {entry}: a home that the entries do not hold",
                    )
                    k.check(
                        all(p["ratio"] > 0 for p in plants.values()) and plants,
                        f"{name} {entry}: no ratio",
                    )
            k.check(
                list(block["mechanisms"]["electrical closure"]["voltage"])
                == [closure[world.consumer]],
                f"{name}: the plant of voltage",
            )
            marked = {e for e, v in block["entries"].items() if v["home"]}
            k.check(
                marked == {e for v in block["mechanisms"].values() for e in v},
                f"{name}: the homes that the entries mark",
            )

    def power(self):
        """The power check at U_c = 0, for every family."""
        k = self.clause(
            "power",
            "CRITERIA 4.5, 5 (C0)",
            "every entry of every family is tested at U_c = 0: beta at most a tenth of its planted "
            "distance",
        )
        untested = []
        for family in self.reg.families.values():
            world = family.world
            steps_c, steps_l = world.steps(family.steps_s[2]), self.captures.steps(world.name)
            for entry in world.entries:
                legacy = self.legacy[family.name]["entries"][entry.name]
                beta = bands.band(entry, 0.0, legacy["U_l"], steps_c, steps_l)["beta"]
                distance = self.reg.ratio(world.name, entry.name) * legacy["largest"]
                tested = beta <= distance / c.POWER_FACTOR
                k.check(
                    tested or self.reg.rehearsal,
                    f"{family.name} {entry.name}: not tested at U_c = 0",
                )
                if not tested:
                    untested.append([family.name, entry.name])
        k.numbers["untested"] = untested

    def structural(self):
        """The structural plants' distances, and the planted legacy arrays scored with the reference
        side in the candidate's place.
        """
        k = self.clause(
            "structural",
            "PLANTS 4, 8, CRITERIA 6",
            "the structural plants: distances and margins formed again, scorable (above 2 beta), "
            "and caught by the reference side's own L*",
        )
        table = {}
        for _, world, family, name, plant in self.reg.structural():
            steps_c, steps_l = world.steps(family.steps_s[2]), self.captures.steps(world.name)
            step_s = self.captures.step_s(world.name, "h4")
            k.check(
                self.planted.runs[plant["run"]]["outcome"] == "completed",
                f"{name}: the planted run did not complete",
            )
            for named in plant["named"]:
                entry = world.by_name[named]
                honest = [self.captures.run(family, step).entry(entry) for step in STEPS]
                wrong = self.planted.run(plant["run"], family, step_s).entry(entry)
                distance = bands.largest(wrong - honest[2])
                U_l = self.legacy[family.name]["entries"][named]["U_l"]
                beta = bands.band(entry, 0.0, U_l, steps_c, steps_l)["beta"]
                printed = plant[named]
                what = f"{name} ({family.name}) {named}"
                k.check(
                    same(distance, printed["distance"], 4)
                    and same(distance / beta, printed["margin"], 4),
                    f"{what}: distance or margin",
                )
                k.check(distance / beta >= c.PLANT_RULE, f"{what}: below the sizing rule")
                k.check(printed["distance"] > 2 * beta, f"{what}: unscorable at U_c = 0")
                star = bands.extrapolate(honest[1], honest[2], c.LEGACY_ORDER)
                caught = bands.largest(star - wrong) > beta
                k.check(caught, f"{what}: the reference side's own L* does not catch it")
                table[what] = {
                    "distance": digits(distance, 2),
                    "margin": digits(distance / beta, 1),
                    "score": "caught" if caught else "not caught",
                }
            if "recorded_channel_K_relative_per_world" in plant and not self.reg.rehearsal:
                got = []
                for wid in range(len(plant["recorded_channel_K_relative_per_world"])):
                    other = self.reg.family(world.name, 0, wid)
                    entry = world.by_name["channel_K"]
                    honest = self.captures.run(other, "h4").entry(entry)
                    wrong = self.planted.run(plant["run"], other, step_s).entry(entry)
                    got.append(bands.largest(wrong - honest) / bands.largest(honest))
                good = all(
                    same(a, b, 4)
                    for a, b in zip(
                        got, plant["recorded_channel_K_relative_per_world"], strict=True
                    )
                )
                k.check(good, f"{name}: the recorded relative changes by world")
        k.numbers["plants"] = table

    def engine_plants(self):
        """The engine plants' registered distances from the planted runs, and that they are scorable
        at U_c = 0.
        """
        k = self.clause(
            "engine_plants",
            "PLANTS 5",
            "EP1's and EP2's registered distances, and that each is above 2 beta at U_c = 0",
        )
        expected = {"EP1": "jupiter_baseline", "EP2": "base s0 w2"}
        for _, run, name, plant, distances in self.reg.engine():
            family = self.reg.families[run["family"]]
            world = family.world
            planted = plant["planted_run"]
            k.check(
                self.reg.rehearsal or family.name == expected[name],
                f"{name}: its family is {family.name}",
            )
            steps_c, steps_l = world.steps(family.steps_s[2]), self.captures.steps(world.name)
            for named, distance in distances.items():
                entry = world.by_name[named]
                honest = self.captures.run(family, "h4").entry(entry)
                wrong = self.planted.run(
                    planted, family, self.captures.step_s(world.name, "h4")
                ).entry(entry)
                formed = bands.largest(wrong - honest)
                k.check(
                    abs(formed - distance) <= 1e-3 * distance,
                    f"{name} {named}: the registered distance is not the planted runs'",
                )
                U_l = self.legacy[family.name]["entries"][named]["U_l"]
                beta = bands.band(entry, 0.0, U_l, steps_c, steps_l)["beta"]
                k.check(distance > 2 * beta, f"{name} {named}: unscorable at U_c = 0")
        if self.reg.rehearsal:
            return
        k.check(
            [name for _, _, name, _, _ in self.reg.engine()] == ["EP1", "EP2"],
            "the engine plants are not EP1 and EP2",
        )
        run = self.reg.runs["base plant swapped"]
        swapped = self.reg.expected_paths(run)
        honest = self.reg.expected_paths(self.reg.runs["base s0 w2 h=6.25e-06"])
        k.check(
            swapped["channel_0"] == honest["channel_1"]
            and swapped["channel_1"] == honest["channel_0"],
            "EP2's paths are not the swapped ones",
        )
        k.check(
            changes(swapped["channel_0"]) != changes(honest["channel_0"]),
            "EP2's two paths do not differ",
        )

    def counts(self):
        """The entries that READOUTS section 3 counts."""
        k = self.clause(
            "counts",
            "READOUTS 3, 4",
            "the entries per consumer by class, against READOUTS section 3's counts",
        )
        from .scoring import expected_counts

        table = {}
        for consumer, wanted in self.reg.profile.get("counts", {}).items():
            found = expected_counts(self.reg, consumer)
            table[consumer] = found
            for name, number in wanted.items():
                k.check(
                    found[name] == number,
                    f"{consumer}: {found[name]} entries of class {name}, and {number} are "
                    f"published",
                )
        k.numbers["counts"] = table


TEXTS = ("README.md", "SPEC.md", "READOUTS.md", "CRITERIA.md", "TABLE.md", "PLANTS.md")
NOT_DONE = [
    "The independent scalar reference of SPEC section 7 was not run: its file is not in the "
    "judge's reading list. The author's run of 25 November is the evidence (protocol section 11).",
    "The pool plants' two output files (plants_manifest.json pool_plants) lie outside the planted "
    "folder that the judge may open.",
    "The snapshot of integrated_capture lies outside the captures' root: its recorded manifest "
    "sha256 is compared, and no file is opened.",
]


def _load(data: bytes) -> dict:
    import io

    with np.load(io.BytesIO(data), allow_pickle=False) as z:
        return {name: z[name] for name in z.files}


def modify(value, path: list, item: dict) -> int:
    """Set or multiply the leaves of a definition that a path names, and count them. `*` stands for
    every key or index.
    """
    key, rest = path[0], path[1:]
    if isinstance(value, list):
        keys = range(len(value)) if key == "*" else [int(key)]
    else:
        keys = [k for k in value if fnmatch.fnmatchcase(k, key)] if "*" in key else [key]
    count = 0
    for k in keys:
        if rest:
            count += modify(value[k], rest, item)
        else:
            value[k] = item["set"] if "set" in item else value[k] * item["mul"]
            count += 1
    return count


def differences(a, b, path="") -> list:
    """The paths at which two JSON values differ, at most five."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for key in sorted(set(a) | set(b)):
            if key not in a or key not in b:
                out.append(f"{path}/{key}")
            else:
                out += differences(a[key], b[key], f"{path}/{key}")
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b, strict=True)):
            out += differences(x, y, f"{path}/{i}")
    elif a != b:
        out.append(path)
    return out[:5]


def canonical(definition: dict, world) -> dict:
    """A captured definition in the inputs' form (SPEC sections 2.1, 2.2 and 2.5), with a label for
    every registered ID.
    """
    model, experiment = definition["model"], definition["experiment"]
    extracellular = model["extracellular"]
    regions = [extracellular, *model.get("surroundings", [])]
    gauge = model["closure"]["gauge_reference"] if "closure" in model else extracellular["id"]
    cells, membranes, channels = {}, {}, {}
    for item in model["cells"]:
        cell, membrane, channel = item["cell"], item["membrane"], item["channel"]
        capacitance = membrane["area_m2"] * membrane["specific_capacitance_F_per_m2"]
        cells[cell["id"]] = {
            "volume_pL": cell["volume_pL"],
            "initial_amount_fmol": cell["initial_amount_fmol"],
            "fixed_charge_equivalent_fmol": cell["fixed_charge_equivalent_fmol"],
            "initial_voltage_V": cell["initial_voltage_V"],
            "initial_charge_C": capacitance * cell["initial_voltage_V"],
        }
        pump = membrane["pump"]
        if pump is not None:
            fuel = {k: v for k, v in pump["metabolism"].items() if k != "kind"}
            pump = {k: v for k, v in pump.items() if k not in ("id", "law", "metabolism")}
            pump.update(law="nak_pump_positive", metabolism={"kind": "maintained_fuel", **fuel})
        membranes[membrane["id"]] = {
            "inside": membrane["inside"],
            "outside": membrane["outside"],
            "area_m2": membrane["area_m2"],
            "capacitance_F": capacitance,
            "passive": {
                "law": "constant_field",
                "permeability_m_per_s": membrane["passive"]["permeability_m_per_s"],
            },
            "pump": pump,
        }
        if channel is not None:
            channels[channel["id"]] = {
                "membrane_id": channel["membrane_id"],
                "species_id": channel["species_id"],
                "kinetic_law": "kv15_mh",
                "max_permeability_m_per_s": channel["max_permeability_m_per_s"],
                "abundance": channel["abundance"],
                "initial_gate": channel["initial_gate"],
            }
    outside = {}
    for region in regions:
        facing = [
            cells[m["inside"]]["initial_charge_C"]
            for m in membranes.values()
            if m["outside"] == region["id"]
        ]
        outside[region["id"]] = {
            "volume_pL": region["volume_pL"],
            "initial_amount_fmol": region["initial_amount_fmol"],
            "fixed_charge_equivalent_fmol": region["fixed_charge_equivalent_fmol"],
            "initial_charge_C": -math.fsum(facing) if facing else 0.0,
        }
    junctions = {
        j["id"]: {
            "from_cell": j["from_cell"],
            "to_cell": j["to_cell"],
            "area_m2": j["area_m2"],
            "permeability_m_per_s": j["permeability_m_per_s"],
            "gate": {**j["gate"], "law": "junction_relaxation"},
        }
        for j in model["junctions"]
    }
    faces = {
        f["id"]: {
            "sender": f["sender"],
            "receiver": f["receiver"],
            "area_m2": f["area_m2"],
            "length_m": f["length_m"],
            "diffusivity_m2_per_s": f["diffusivity_m2_per_s"],
            "law": "logmean_face",
        }
        for f in model.get("faces", [])
    }
    leak, pumps = {}, {}
    for control in experiment["membrane_controls"]:
        name = control["membrane_id"]
        if any(m != 1 for entry in control["leak"] for m in entry["multipliers"].values()):
            raise Fault(f"{name}: a leak multiplier that is not 1")
        leak[name] = [[0.0, 1.0]]
        if membranes[name]["pump"] is not None:
            pumps[name] = [[entry["time"], entry["multiplier"]] for entry in control["pump"]]
    channel_controls = {
        item["channel_id"]: [[e["time"], e["availability"]] for e in item["schedule"]]
        for item in experiment["channel_controls"]
    }
    junction_controls = {
        item["junction_id"]: [[e["time"], e["open_fraction"]] for e in item["schedule"]]
        for item in experiment["junction_controls"]
    }
    if world.assembly:
        channel_controls = world.block["controls"]["channel"]
    return {
        "temperature_K": model["temperature_K"],
        "species": {s["id"]: s["valence"] for s in model["species"]},
        "cells": cells,
        "outside": outside,
        "closure": {"gauge_reference": gauge},
        "membranes": membranes,
        "channels": channels or [],
        "junctions": junctions or [],
        "faces": faces or [],
        "controls": {
            "leak": leak,
            "pump": pumps or [],
            "channel": channel_controls or [],
            "junction": junction_controls or [],
        },
        "material_tolerance_fmol": definition["execution"]["material_balance_atol_fmol"],
        "end_s": experiment["end_time"],
    }
