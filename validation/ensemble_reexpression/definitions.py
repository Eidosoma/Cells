"""The definitions of every registered run, made from inputs.json and spec/SPEC.md §2 alone, and
their checks.

    python -m validation.ensemble_reexpression.definitions check [--inputs FILE]
    python -m validation.ensemble_reexpression.definitions write NAME DIRECTORY [--inputs FILE]
    python -m validation.ensemble_reexpression.definitions strings [--inputs FILE]

`check` parses the definitions of every run and runs none of them. It holds each to its block leaf
by leaf (SPEC §2.4; by the doubles too, but for the derived initial voltage), each registered block
to the literal one of SPEC §2.5, every declared time to the grid rule (SPEC §4), and the field
solver to D147. `strings` prints each run's labels in the strings note's form, for the lead.

- **An ionic world** is a closed `resolved_pump_tissue@3` definition (worlds.py).
- **A driven world** (`cell`, `base`) is a composed file, which `cells assembly-pool resolve` turns
  into one ordinary definition for each of the pools' worlds (cells.assembly_pool.resolve).
- **A pool run** is the pool's own definition, with its events recorded.

The integrator is the world's order's (labels.INTEGRATORS) and the field solver is D147's
(validation/tissue/field_solver_choice.py).
"""

import argparse
import copy
import json
import math
import re
import sys
from collections import Counter
from functools import cache
from pathlib import Path

from cells.assembly_pool import observables
from cells.assembly_pool.resolve import parse_composed
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.grid import EventGrid
from validation.ensemble_reexpression import worlds
from validation.ensemble_reexpression.inputs import (
    DRIVEN,
    FOLDER,
    IONIC,
    POOL,
    REGISTERED,
    Inputs,
    InputsError,
    require_on_grid,
    steps_of,
)
from validation.ensemble_reexpression.labels import (
    LABELS,
    declared_strings,
    integrator,
    note_entry,
    string,
)
from validation.tissue import field_solver_choice

SPEC_TEXT = FOLDER / "spec/SPEC.md"
EXCHANGE = "exchange_channels"


def _times(world, factor):
    """Every channel's maximal permeability times a factor, as a declared change."""
    return [
        {
            "path": ["channels", name, "max_permeability_m_per_s"],
            "value": channel["max_permeability_m_per_s"] * factor,
        }
        for name, channel in worlds.entities(world.block["channels"])
    ]


# The registered plants' declared changes (the lead's answer of 25 November, from PLANTS.md, which
# the builder does not read): EP1 takes both channels' maximal permeability times 1.01. EP2 has the
# two pools' channels exchanged in the composed file, so each channel follows the other cell's path.
REGISTERED_CHANGES = {
    "EP1": lambda world: _times(world, 1.01),
    "EP2": lambda world: [{EXCHANGE: list(world.pools)}],
}


# ------------------------------------------------------------------ declared changes


def declared_change(inputs, run):
    """A run's declared change, a list of items that each give a path of the world's block and the
    value there, or the two cells whose pools exchange their channels in the composed file: its own
    entry's, or a registered plant's; empty for every other run."""
    if run.declared_change is not None:
        change = run.declared_change
    elif run.role != "plant":
        change = []
    elif run.variant in REGISTERED_CHANGES:
        change = REGISTERED_CHANGES[run.variant](inputs.worlds[run.world])
    else:
        raise InputsError(f"{run.name!r}: the plant {run.variant!r} declares no change")
    forms = ({"path", "value"}, {EXCHANGE})
    if not isinstance(change, list) or any(set(item) not in forms for item in change):
        raise InputsError(
            f"{run.name!r}: a declared change is a list of paths with values, or of {EXCHANGE}"
        )
    return change


def changed_block(block, change):
    """The block with a declared change's values at their paths, each of which the block has."""
    out = copy.deepcopy(block)
    for item in change:
        if "path" not in item:
            continue
        *parents, last = item["path"]
        target = out
        try:
            for key in parents:
                target = target[key]
            _ = target[last]
        except (KeyError, IndexError, TypeError) as error:
            path = item["path"]
            raise InputsError(f"A declared change's path is not in the block: {path!r}") from error
        target[last] = item["value"]
    return out


# ------------------------------------------------------------------ ionic definitions


def floating(block):
    """The capacitor components of a block that its gauge is not in: membranes join a cell and a
    region into one component, and nothing else does. Each has a free field offset (D147)."""
    of = {name: name for name in (*block["cells"], *block["outside"])}

    def root(name):
        while of[name] != name:
            name = of[name]
        return name

    for _, m in worlds.entities(block["membranes"]):
        of[root(m["inside"])] = root(m["outside"])
    return len({root(name) for name in of} - {root(block["closure"]["gauge_reference"])})


def _written(world, step, change, field_solver):
    return worlds.write(
        changed_block(world.block, change),
        step=step,
        observation_times=world.potential_times,
        solver=integrator(world.order),
        field_solver=string(field_solver),
    )


def ionic(world, step, change=()):
    """The ionic definition of a world at a step, with D147's field solver. A channel that a pool
    drives is declared at 1 throughout, the base that its path multiplies."""
    # The count of free offsets parses with the declared solver, and the floor variant admits both.
    floor = _written(world, step, change, "field_solver_floor")
    if field_solver_choice.free_field_offsets(floor):
        return field_solver_choice.declare(floor)
    return field_solver_choice.declare(_written(world, step, change, "field_solver"))


def submitted(world, step, change=()):
    """ionic(), or where the engine refuses to parse it, so that no count of its offsets can be
    made, the same declaration with the solver of its block's own count (floating)."""
    try:
        return ionic(world, step, change)
    except (ConfigError, ArithmeticError, KeyError, TypeError, AttributeError):
        floor = floating(changed_block(world.block, change))
        return _written(world, step, change, "field_solver_floor" if floor else "field_solver")


# ------------------------------------------------------------------ pools and composed files


def pool(world, cell, seed_index):
    """The definition of a cell's pool for one seed. Its harness is the block's but for `recording`:
    a path is read from recorded events."""
    entry = world.pools[cell]
    out = copy.deepcopy(entry["pool"])
    out["model"], out["topology"] = string(out["model"]), string(out["topology"])
    return (
        out | entry.get("harness", {}) | {"recording": "events", "seed": entry["seeds"][seed_index]}
    )


def pools(world, seed_index):
    """{cell: its pool's definition}, in the world's order of cells."""
    return {cell: pool(world, cell, seed_index) for cell in world.pools}


def levels(world):
    """The observable's levels: the coupling's active one where it holds, its inactive where not."""
    coupling = world.raw["coupling"]
    return {"true": coupling["active"], "false": coupling["inactive"]}


def composed(world, seed_index, step, change=(), *, definition=ionic):
    """The composed file of a driven world's ionic definition and its pools."""
    channels = {cell: [entry["channel"]] for cell, entry in world.pools.items()}
    for item in change:
        if EXCHANGE in item:
            one, other = item[EXCHANGE]
            channels[one], channels[other] = channels[other], channels[one]
    return {
        "schema_version": 1,
        "ionic": definition(world, step, change),
        "pools": [
            {
                "channels": channels[cell],
                "observable": string(world.raw["coupling"]["law"]),
                "levels": levels(world),
                "pool": raw,
            }
            for cell, raw in pools(world, seed_index).items()
        ],
    }


def first_step(inputs, run):
    """The largest step of a run's world, whose composed file its pool runs submit."""
    steps = [
        r.step_s for r in inputs.runs.values() if r.world == run.world and r.step_s is not None
    ]
    if not steps:
        raise InputsError(f"{run.name!r}: its world has no ionic run, so no composed file")
    return max(steps)


def definition(inputs, run):
    """What a run submits: an ionic definition, or a composed file. A pool run submits its world's
    composed file at the first step and runs the file's pools."""
    world, change = inputs.worlds[run.world], declared_change(inputs, run)
    if run.kind == IONIC:
        return submitted(world, run.step_s, change)
    step = first_step(inputs, run) if run.kind == POOL else run.step_s
    return composed(world, run.seed_index, step, change, definition=submitted)


# ------------------------------------------------------------------ the grid


def grid_faults(inputs, run):
    """The named refusal of a run whose declared times are not on its grid, or None: every change,
    every compared time and the end, against the run's step (SPEC §4)."""
    world = inputs.worlds[run.world]
    if run.kind == POOL:
        return None
    block = changed_block(world.block, declared_change(inputs, run))
    try:
        for key, schedules in block.get("controls", {}).items():
            for name, changes in worlds.entities(schedules):
                require_on_grid([t for t, _ in changes], run.step_s, f"controls.{key} {name}")
        require_on_grid(world.potential_times, run.step_s, "the potentials' times")
        require_on_grid(world.row_times, run.step_s, "the compared times")
        if run.restart_time is not None:
            require_on_grid([run.restart_time], run.step_s, "the checkpoint")
        steps_of(world.end, run.step_s)
    except ValueError as refusal:
        return str(refusal)
    return None


# ------------------------------------------------------------------ the checks


@cache
def literal_blocks(path=SPEC_TEXT):
    """The literal blocks of SPEC §2.5, in their order in the text."""
    text = Path(path).read_text()
    section = text[text.index("### 2.5 ") : text.index("## 3. ")]
    return tuple(json.loads(m) for m in re.findall(r"```json\n(.*?)```", section, re.DOTALL))


def literals():
    """{world: its literal block} and the literal block of a pool run. SPEC §2.5 prints the first
    JUPITER arm, `cell`, `integrated` and one pool; the other two worlds it states as changes."""
    jupiter, cell, integrated, one_pool = literal_blocks()
    release, base = copy.deepcopy(jupiter), copy.deepcopy(jupiter)
    off = re.search(r"differs in `controls\.pump` alone, (\[\[.*?\]\]) for", SPEC_TEXT.read_text())
    release["controls"]["pump"] = {m: json.loads(off[1]) for m in release["membranes"]}
    base["controls"]["channel"] = cell["controls"]["channel"]
    return {
        "jupiter_baseline": jupiter,
        "jupiter_pump_release": release,
        "integrated": integrated,
        "cell": cell,
        "base": base,
    }, one_pool


def derived_faults(world):
    """SPEC §2.2's derived declarations of a block, formed again: a cell's charge from its voltage
    and its membrane's capacitance, and a region's as minus the rounded sum of the charges of the
    cells that face it."""
    block, out = world.block, []
    charges = {name: c["initial_charge_C"] for name, c in block["cells"].items()}
    for _, m in worlds.entities(block["membranes"]):
        cell = block["cells"][m["inside"]]
        if cell["initial_charge_C"] != m["capacitance_F"] * cell["initial_voltage_V"]:
            out.append(f"{world.name} {m['inside']}: its charge is not capacitance x voltage")
    for name, region in block["outside"].items():
        facing = [
            m["inside"] for _, m in worlds.entities(block["membranes"]) if m["outside"] == name
        ]
        expected = -math.fsum(charges[c] for c in facing) if facing else 0.0
        if region["initial_charge_C"] != expected:
            out.append(f"{world.name} {name}: its charge is not minus the sum that faces it")
    return out


def block_faults(found, expected, what, *, driven):
    """The leaves of a definition's block that depart from the registered one: by SPEC §2.4's rule,
    and by their doubles but for the derived initial voltage."""
    skip = (("controls", "channel"),) if driven else ()
    out = [f"{what}: {path} {a!r} != {b!r}" for path, a, b in worlds.departures(
        found, expected, skip=skip)]  # fmt: skip
    for path, a, b in worlds.departures(found, expected, exact=True, skip=skip):
        if path[-1] != "initial_voltage_V":
            out.append(f"{what}: {path} is not the same double: {a!r} != {b!r}")
    return out


def pool_faults(world, seed_index, parsed):
    """Each pool's definition, as its composed file parses it, against its block."""
    out = []
    for (cell, entry), drive in zip(world.pools.items(), parsed.drives, strict=True):
        found, where = drive.pool.to_dict(), f"{world.name} s{seed_index} {cell}"
        for key, value in entry["pool"].items():
            if found[key] != string(value):
                out.append(f"{where}: pool {key} {found[key]!r} != {value!r}")
        if found["seed"] != entry["seeds"][seed_index]:
            out.append(f"{where}: the pool's seed")
        if found["recording"] != "events":
            out.append(f"{where}: the pool records no events")
        if drive.observable.law_id != string(world.raw["coupling"]["law"]):
            out.append(f"{where}: the observable is {drive.observable.law_id!r}")
        if drive.level_of() != levels(world):
            out.append(f"{where}: its levels are {drive.level_of()!r}")
    return out


def run_faults(inputs, run, parsed):
    """Every fault of one run's definition; `parsed` keeps what several runs share."""
    world, what = inputs.worlds[run.world], run.name
    change = declared_change(inputs, run)
    step = first_step(inputs, run) if run.kind == POOL else run.step_s
    key = (run.world, run.seed_index, step, repr(change))
    if key not in parsed:
        if run.kind == IONIC:
            parsed[key] = parse_spec(ionic(world, step, change))
        else:
            parsed[key] = parse_composed(composed(world, run.seed_index, step, change))
    if run.kind == POOL:
        return pool_faults(world, run.seed_index, parsed[key])
    spec = parsed[key] if run.kind == IONIC else parsed[key].ionic
    out = [] if run.kind == IONIC else pool_faults(world, run.seed_index, parsed[key])
    expected = changed_block(world.block, change)
    raw = spec.to_dict()
    out += block_faults(worlds.read(raw), expected, what, driven=run.kind == DRIVEN)
    refusal = grid_faults(inputs, run)
    if refusal is not None:
        out.append(f"{what}: {refusal}")
    steps = len(EventGrid(spec)) - 1
    if steps != steps_of(world.end, run.step_s):
        out.append(f"{what}: its clock takes {steps} steps")
    if field_solver_choice.declare(raw) != raw:
        out.append(f"{what}: its field solver is not D147's")
    if field_solver_choice.free_field_offsets(raw) != floating(expected):
        out.append(f"{what}: its free offsets are not its block's")
    if declared_strings(raw) != sorted(LABELS[name] for name in _labels(inputs, run)):
        out.append(f"{what}: it declares {declared_strings(raw)}")
    return out


def _labels(inputs, run):
    """The labels that the block of a run's world and SPEC §3.1 name for its ionic definition."""
    world = inputs.worlds[run.world]
    block = world.block
    found = {"inner_model", "closure", "constant_field"}
    found.add("rk4" if world.order == 4 else "imex")
    found.add("field_solver_floor" if floating(block) else "field_solver")
    for _, m in worlds.entities(block["membranes"]):
        if m.get("pump") is not None:
            found |= {m["pump"]["law"], m["pump"]["metabolism"]["kind"]}
    found |= {c["kinetic_law"] for _, c in worlds.entities(block.get("channels"))}
    found |= {j["gate"]["law"] for _, j in worlds.entities(block.get("junctions"))}
    found |= {f["law"] for _, f in worlds.entities(block.get("faces"))}
    return found


def check(inputs, *, runs=None):
    """(the faults of every definition, their counts): parse only."""
    faults, parsed = [], {}
    selected = list(inputs.runs.values()) if runs is None else runs
    if inputs.path.resolve() == REGISTERED.resolve():
        blocks, one_pool = literals()
        for name, literal in blocks.items():
            if inputs.worlds[name].block != literal:
                faults.append(f"{name}: inputs.json's block is not SPEC 2.5's")
        found = inputs.worlds["cell"].pools["cell_0"]
        shown = {"channel": found["channel"], "stream_id": found["stream_id"]}
        shown |= {"seed": found["seeds"][0], "pool": found["pool"]}
        if shown != one_pool:
            faults.append("cell: inputs.json's pool is not SPEC 2.5's")
    for world in inputs.worlds.values():
        faults += derived_faults(world)
        laws = observables.registered()
        if world.pools and string(world.raw["coupling"]["law"]) not in laws:
            faults.append(f"{world.name}: its coupling names no registered observable")
    for run in selected:
        faults += run_faults(inputs, run, parsed)
    kinds = Counter(r.kind for r in selected)
    counts = {
        "runs": len(selected),
        "by kind": dict(kinds),
        "ionic definitions": sum(1 for v in parsed.values() if not hasattr(v, "drives")),
        "composed files": sum(1 for v in parsed.values() if hasattr(v, "drives")),
        "world definitions used of the composed files": kinds[DRIVEN],
        "pools of the pool runs": sum(
            len(inputs.worlds[r.world].pools) for r in selected if r.kind == POOL
        ),
    }
    return faults, counts


def run_strings(inputs, run):
    """Every registered string that a run's definition declares, as its table entry lists them: an
    ionic definition's, with its pools' observable where pools drive it; a pool run's pools' and
    their observable (the lead's answer, 25 November)."""
    parsed = definition(inputs, run)
    if run.kind == IONIC:
        return declared_strings(parse_spec(parsed).to_dict())
    parsed = parse_composed(parsed)
    if run.kind == POOL:
        found = declared_strings(*(d.pool.to_dict() for d in parsed.drives))
    else:
        found = declared_strings(parsed.ionic.to_dict())
    return sorted({*found, *(d.observable.law_id for d in parsed.drives)})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("check", "write", "strings"):
        command = commands.add_parser(name)
        command.add_argument("--inputs", type=Path, default=REGISTERED)
        if name == "write":
            command.add_argument("name", help="a run's name")
            command.add_argument("directory", type=Path, help="a new folder")
    args = parser.parse_args(argv)
    inputs = Inputs(args.inputs)
    if args.command == "check":
        faults, counts = check(inputs)
        print(json.dumps({"inputs_sha256": inputs.sha256, **counts, "faults": faults}, indent=2))
        return 1 if faults else 0
    if args.command == "strings":
        shown = {}
        for run in inputs.runs.values():
            entry = note_entry(run_strings(inputs, run))
            shown.setdefault(json.dumps(entry, sort_keys=True), []).append(run.name)
        for entry, names in shown.items():
            print(f"{len(names)} runs, the first {names[0]!r}:")
            print("  " + entry)
        return 0
    run = inputs.run(args.name)
    if not run.invented:
        print(f"A registered run's definition, for reading: {run.name}", file=sys.stderr)
    args.directory.mkdir()
    (args.directory / "definition.json").write_text(
        json.dumps(definition(inputs, run), indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
