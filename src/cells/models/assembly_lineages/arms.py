"""Ensemble arms of assembly lineages: one definition, many worlds, in lane batches.

An arm (GARD_DESIGN §3; docs/GPU_ENSEMBLES.md's arms) fixes one definition and its sample count.
World w, for w = world_id_start ... world_id_start + worlds - 1, is the definition's lineage keyed
by (seed, environment, lineage = w, branch): the arm owns the seed and the lineage word, so the
definition holds the arm's seed and lineage word 0. A world's streams follow from its identity
alone (streams.py), so batch boundaries, the lane width, pauses and the order of batches change no
value of any world.

run(arm, lanes) runs the worlds in batches of `lanes` lanes of one compiled program (runner.
run_lanes). A batch may pause between device calls (`calls`): every lane still running is saved
verbatim (checkpoints.py), and resume() continues those lanes bitwise. Each world's records are
its LineageRun's; summary() states the arm and each world's end.

The family's own arm: hooking it into `cells ensemble`'s queue goes through the model table's
runner entry when seam F's next step builds that (CORE_SEAMS_DESIGN §15), not here.
"""

import dataclasses
from dataclasses import dataclass

from cells.definitions.specs import ConfigError, bounded_integer, parse_spec
from cells.models.assembly_lineages import MODE, keys, runner, streams

FORMAT = "cells.assembly_lineages.arm@1"


@dataclass(frozen=True)
class Arm:
    definition: dict
    worlds: int
    world_id_start: int
    seed: int


def parse(raw):
    if not isinstance(raw, dict) or set(raw) != {"definition", "worlds", "world_id_start", "seed"}:
        raise ConfigError("An arm is {definition, worlds, world_id_start, seed}")
    worlds = bounded_integer(raw["worlds"], "arm: worlds", minimum=1, maximum=2**24)
    start = bounded_integer(raw["world_id_start"], "arm: world_id_start", minimum=0)
    try:
        seed = streams.check_word(raw["seed"], "arm: seed")
        streams.check_word(start + worlds - 1, "arm: the last world ID")
    except ValueError as error:
        raise ConfigError(str(error)) from error
    spec = parse_spec(raw["definition"])
    if spec.execution.mode != MODE:
        raise ConfigError(f"An arm's worlds are {MODE} lineages")
    if spec.execution.seed != seed or spec.execution.lineage != 0:
        raise ConfigError(
            "The arm owns the seed and the lineage word: its definition holds the arm's seed and "
            "lineage word 0"
        )
    return Arm(spec.to_dict(), worlds, start, seed)


def world_ids(arm):
    return range(arm.world_id_start, arm.world_id_start + arm.worlds)


def world_spec(arm, world):
    spec = parse_spec(arm.definition)
    return dataclasses.replace(
        spec, execution=dataclasses.replace(spec.execution, lineage=int(world))
    )


def run(arm, lanes, *, calls=None, worlds=None):
    """{world ID: LineageRun} of the arm's worlds (or the given subset), in batches of `lanes`.
    With `calls`, each batch pauses after that many device calls (runner.run_lanes)."""
    lanes = bounded_integer(lanes, "arm: lanes", minimum=1, maximum=4096)
    ids = list(world_ids(arm) if worlds is None else worlds)
    out = {}
    for start in range(0, len(ids), lanes):
        batch = ids[start : start + lanes]
        runs = runner.run_lanes([world_spec(arm, w) for w in batch], calls=calls)
        out.update(zip(batch, runs, strict=True))
    return out


def resume(arm, paused, lanes, *, calls=None):
    """Continue each paused world from its checkpoint: {world ID: LineageRun of the rest}."""
    ids = [w for w, r in paused.items() if r.status == "stopped"]
    out = {}
    for start in range(0, len(ids), lanes):
        batch = ids[start : start + lanes]
        specs = [world_spec(arm, w) for w in batch]
        states = [paused[w].checkpoint() for w in batch]
        runs = runner.run_lanes(specs, starts=states, calls=calls)
        out.update(zip(batch, runs, strict=True))
    return out


def summary(arm, runs):
    """The arm and each world's end, as JSON data."""
    worlds = {}
    for w, r in sorted(runs.items()):
        worlds[str(w)] = {
            "status": r.status,
            "qualifier": r.qualifier,
            "fissions": int(len(r.fissions["fission_time"])),
            "events": int(r.timings["events"]),
            "end_time": float(r.rows["row_time"][-1]),
            "occupant": keys.spelled(int(r.rows["occupant"][-1, 0])),
            "lives": int(len(r.lives["life_key"])),
        }
    return {
        "format": FORMAT,
        "arm": {
            "worlds": arm.worlds,
            "world_id_start": arm.world_id_start,
            "seed": arm.seed,
            "definition_sha256": parse_spec(arm.definition).fingerprint,
        },
        "keying": "world w is the definition's lineage keyed by (seed, environment, lineage = w, "
        "branch); batch boundaries, lane width and pauses change no value",
        "worlds": worlds,
    }
