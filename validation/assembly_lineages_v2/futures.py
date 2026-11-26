"""F12's restored futures on cells.model.assembly_lineages@2: fresh runs founded from a lineage's
post-fission landmarks (route (b), the lead's ruling of 20 November 2026; analysis tooling, no
engine change).

A future restores the state of a saved single-lineage division bundle just after one of its
splits, and runs the same world on from there with fresh streams. It is a new run of a new world:
the founder is part of the world's id, so keys, generations and relations restart at the
landmark, and the link to it lives in the future's provenance (manifest.json) and in this module's
index. Single lineages only: a population's slot relabelling has not been run.

**The landmark** is the shear row written after a split (row_kind `shear`): the followed daughter
with the pool as it was. Each is checked against the fission table, which the founder is not built
from: its vesicle places hold the followed daughter's counts, its pool places the parent's, and its
time is the split's.

**The future's definition** is the natural run's, with exactly these changes, and a check refuses
any other:
- the founder: the landmark's count in every finite place (the pool, the membrane and the lumen);
- the schedules: each declared time after the landmark, less its time. A Poisson schedule is kept
  as declared: its gaps are memoryless, so the future's own process from 0 has the law of the rest
  of the natural one;
- the horizon and the observation times: less the landmark's time (observations after it only);
- the stream's branch word: 1 + split × per_landmark + future, under the natural run's seed,
  environment and lineage words. A fresh founder holds key 0:0, so two landmarks' futures on one
  word would draw the same uniforms; the word is unique per (landmark, future), and differs from
  the natural run's. Natural runs that share their seed, environment and lineage words must not
  have futures together: give each its own lineage word.

**The checks on every future,** from its saved bundle:
- its start row is the landmark's count in every finite place;
- the kernel's full rate table at the future's start equals the natural world's at the landmark
  row, to rounding (kernel.rates on the host, both directions of every channel);
- its first attempt is at the natural run's next shear time less the landmark's (declared times).

**What the rate-table check shows, and what it does not.** Both tables are host evaluations of
kernel.rates, each with the factor and mixing states recomputed exactly from the counts. Given the
definition's check and the start row, they agree by construction: the largest relative difference
is 0. So the check guards the future's construction and the parser's reading of its world (a
dropped place, a changed datum), and nothing more. It does not see the natural run's device state
at the landmark: its incremental factor state and its rates there, which the bundle does not save.
A device-side check, with the post-split rates saved in records.py, is on the first builder's queue
after FR-21 (the lead's ruling of 20 November 2026). The independent check of a landmark is
landmarks() against the fission table.

**Refused landmarks** are recorded with their reason, counted, and never replaced or adjusted:
- a state the parser refuses (for example a finite pool whose solutes drifted above c_ext, which
  the natural run only reports);
- a landmark with no declared shear time after it (LandmarkRefused);
- a followed daughter that lysed at birth (no state to restore).

The index (futures.json) lists each landmark (its split, time, counts and parent's counts) and its
futures (word, bundle), and the refused landmarks. f12.futures() and
generation_inheritance.futures() read it. Each future's provenance carries the natural run's
declared amphiphiles (H's species set, D245), when it declares them.
"""

import copy
import json
from pathlib import Path

import numpy as np

FORMAT = "cells.assembly_lineages_v2.futures@1"
SHEAR_ROW = 4  # runner.SHEAR: the row written after a split
ALLOWED = (
    "model.world.founder",
    "experiment.schedules",
    "experiment.time_horizon_s",
    "experiment.observation_times_s",
    "execution.stream.branch",
)
RTOL = 1e-12
WORD = 2**32


class LandmarkRefused(ValueError):
    """A landmark with no future to run: a declared shear schedule has no time after it."""


def _differs(a, b, prefix=""):
    if isinstance(a, dict) and isinstance(b, dict):
        out = []
        for k in sorted(set(a) | set(b)):
            out += _differs(a.get(k), b.get(k), f"{prefix}{k}.")
        return out
    return [] if a == b else [prefix[:-1]]


def check_definition(natural, future):
    """The paths where the future's definition differs from the natural run's; refuses any path
    the rule does not change."""
    paths = _differs(natural, future)
    refused = [p for p in paths if not any(p == a or p.startswith(a + ".") for a in ALLOWED)]
    if refused:
        raise ValueError(f"A future changes only {list(ALLOWED)}, not {refused}")
    return paths


def word(split, future, per_landmark, natural_branch=0):
    """The future's branch word, unique per (landmark split, future)."""
    if not 0 <= future < per_landmark:
        raise ValueError(f"Future {future} is outside 0..{per_landmark - 1}")
    value = 1 + int(split) * int(per_landmark) + int(future)
    if value >= WORD or value == natural_branch:
        raise ValueError(f"Branch word {value} is outside [1, 2**32) or the natural run's")
    return value


def landmarks(directory):
    """The post-fission landmarks of a saved single-lineage division bundle: [{split, row, time,
    counts, parent_counts}] (counts over every place), each checked against the fission table."""
    from cells.models.assembly_lineages_v2 import records

    _, record, arrays = records.read(directory)
    if record.get("mode") != "single_lineage" or "division" not in record:
        raise ValueError("Futures restore single-lineage division bundles (route (b))")
    table = record["places"]
    vesicle = [p["index"] for p in table if p["phase"] in ("membrane", "lumen")]
    pool = [p["index"] for p in table if p["phase"] == "pool"]
    rows = np.flatnonzero(arrays["row_kind"] == SHEAR_ROW).tolist()
    splits = np.flatnonzero(arrays["fission_outcome"] == 0).tolist()
    if len(rows) != len(splits):
        raise ValueError(f"{len(rows)} shear rows for {len(splits)} splits")
    out = []
    for row, r in zip(rows, splits, strict=True):
        counts = arrays["place_count"][row]
        followed = int(arrays["fission_followed"][r])
        daughter = arrays["fission_daughter_counts"][r, followed]
        parent = arrays["fission_parent_counts"][r]
        time = float(arrays["row_time"][row])
        if not (np.array_equal(counts[vesicle], daughter[vesicle])
                and np.array_equal(counts[pool], parent[pool])
                and time == float(arrays["fission_time"][r])):  # fmt: skip
            raise ValueError(f"Shear row {row} is not split {r}'s followed daughter and pool")
        out.append({"split": r, "row": row, "time": time,
                    "lysed_at_birth": bool(arrays["fission_lysed_at_birth"][r, followed]),
                    "counts": counts.tolist(), "parent_counts": parent.tolist()})  # fmt: skip
    return out


def definition(natural, landmark, branch):
    """The future's definition (module docstring), from the natural run's definition (a dict)."""
    from cells.definitions.specs import parse_spec

    if natural["execution"]["mode"] != "single_lineage":
        raise ValueError("Futures are single-lineage runs (route (b))")
    world = parse_spec(natural).model.world
    t0 = float(landmark["time"])
    out = copy.deepcopy(natural)
    out["model"]["world"]["founder"] = {
        p.name: int(n) for p, n in zip(world.places, landmark["counts"], strict=False)
        if not p.held
    }  # fmt: skip
    for schedule in out["experiment"].get("schedules", []):
        if "times_s" in schedule:
            schedule["times_s"] = [t - t0 for t in schedule["times_s"] if t > t0]
            if not schedule["times_s"]:
                raise LandmarkRefused(
                    f"Schedule {schedule['index']} has no time after the landmark"
                )
    out["experiment"]["time_horizon_s"] = natural["experiment"]["time_horizon_s"] - t0
    out["experiment"]["observation_times_s"] = [
        t - t0 for t in natural["experiment"]["observation_times_s"] if t > t0
    ]
    out["execution"]["stream"]["branch"] = int(branch)
    check_definition(natural, out)
    return out


def rate_table(spec, counts):
    """The kernel's rates of every channel (forwards, then reverses) at `counts`, on the host."""
    from cells.models.assembly_lineages_v2 import kernel, model

    structure, layout = model.structure(spec), model.layout(spec)
    full = np.zeros(layout.place_held.shape[0], dtype=np.int64)
    full[: len(counts)] = np.asarray(counts, dtype=np.int64)
    totals = kernel.totals_of(full, layout, np)
    factor_state, term_states = kernel.states(full, totals, layout, structure, np)
    return np.asarray(kernel.rates(full, totals, factor_state, term_states, layout, structure, np))


def rates_agree(natural_spec, landmark_counts, future_spec, start_counts):
    """(agree, largest relative difference): the natural world's rate table at the landmark row
    against the future's at its start, to rounding (zero exactly where the other is zero)."""
    a = rate_table(natural_spec, landmark_counts)
    b = rate_table(future_spec, start_counts)
    if a.shape != b.shape or not np.array_equal(a == 0, b == 0):
        return False, float("inf")
    nonzero = a != 0
    worst = float(np.max(np.abs(a[nonzero] - b[nonzero]) / np.abs(a[nonzero]), initial=0.0))
    return worst <= RTOL, worst


def run(natural_dir, out, *, splits, per_landmark, lanes=16, provenance=None):
    """Futures of the saved natural bundle `natural_dir` from the landmarks after `splits` (fission
    rows), `per_landmark` each, run in batches of `lanes` lanes; bundles and futures.json in `out`.
    Returns the index."""
    from cells.definitions.specs import ConfigError, parse_spec
    from cells.models.assembly_lineages_v2 import records, runner

    natural_dir, out = Path(natural_dir), Path(out)
    out.mkdir(parents=True, exist_ok=False)
    natural = json.loads((natural_dir / "resolved_config.json").read_text())
    natural_spec = parse_spec(natural)
    _, natural_record, natural_arrays = records.read(natural_dir)
    stated = json.loads((natural_dir / "manifest.json").read_text())["provenance"]
    declared = {"amphiphiles": stated["amphiphiles"]} if "amphiphiles" in stated else {}
    by_split = {m["split"]: m for m in landmarks(natural_dir)}
    times = natural_arrays["fission_time"]
    index = {"format": FORMAT, "natural": str(natural_dir),
             "natural_qualifier": natural_record["run"]["qualifier"],
             "natural_world": natural_record["world"], "per_landmark": per_landmark,
             "landmarks": [], "refused": []}  # fmt: skip
    jobs = []
    for split in splits:
        landmark = by_split.get(split)
        if landmark is None:
            raise ValueError(f"Fission row {split} is not a split of the natural run")
        if landmark["lysed_at_birth"]:
            index["refused"].append({"split": split, "reason": "its followed daughter lysed at "
                                     "birth: no state to restore"})  # fmt: skip
            continue
        entry = {key: landmark[key] for key in ("split", "row", "time", "counts",
                                                "parent_counts")}  # fmt: skip
        entry["futures"] = []
        later = [float(t) for t in times if float(t) > landmark["time"]]
        entry["natural_next_attempt_s"] = later[0] if later else None
        try:
            specs = []
            for f in range(per_landmark):
                w = word(split, f, per_landmark, natural["execution"]["stream"]["branch"])
                specs.append((w, parse_spec(definition(natural, landmark, w))))
        except (ConfigError, LandmarkRefused) as error:  # recorded, never replaced
            index["refused"].append({"split": split, "reason": str(error)})
            continue
        index["landmarks"].append(entry)
        jobs += [(entry, w, s) for w, s in specs]
    for start in range(0, len(jobs), lanes):
        batch = jobs[start : start + lanes]
        for (entry, w, spec), result in zip(batch, runner.run_lanes([s for _, _, s in batch]),
                                            strict=True):  # fmt: skip
            result.check()
            bundle = out / f"split{entry['split']}" / f"word{w}"
            bundle.parent.mkdir(exist_ok=True)
            records.write_run(bundle, result, provenance={
                "operation": "future", "route": "(b): a fresh run founded from a post-fission "
                "landmark", "landmark": {"natural": str(natural_dir),
                "natural_qualifier": index["natural_qualifier"], "split": entry["split"],
                "row": entry["row"], "time": entry["time"]}, "word": w, **declared,
                **(provenance or {}),
            })  # fmt: skip
            entry["futures"].append({"word": w, "bundle": str(bundle),
                                     **_checks(natural_spec, entry, spec, bundle)})  # fmt: skip
    (out / "futures.json").write_text(json.dumps(index, indent=1, sort_keys=True) + "\n")
    return index


def _checks(natural_spec, entry, spec, bundle):
    """The checks on one future (module docstring), from its saved bundle; refuses a failure."""
    from cells.models.assembly_lineages_v2 import records

    _, record, arrays = records.read(bundle)
    finite = [p["index"] for p in record["places"] if p["kind"] == "finite"]
    start = arrays["place_count"][0]
    landmark = np.asarray(entry["counts"])
    if not np.array_equal(start[finite], landmark[finite]):
        raise ValueError(f"{bundle}: the start row is not the landmark's counts")
    agree, worst = rates_agree(natural_spec, landmark, spec, start)
    if not agree:
        raise ValueError(f"{bundle}: the rate table differs from the landmark's ({worst:.3g})")
    first = None
    attempts = arrays["fission_time"]
    shears = [s for s in record["division"]["schedules"] if s["kind"] == "shear"]
    declared = shears and all("times_s" in s for s in shears)
    if len(attempts) and entry["natural_next_attempt_s"] is not None:
        first = float(attempts[0])
        want = entry["natural_next_attempt_s"] - entry["time"]
        if declared and first != want:
            raise ValueError(f"{bundle}: its first attempt is at {first}, not {want}")
    return {"rates_largest_relative_difference": worst, "first_attempt_s": first,
            "status": record["end"]["status"]}  # fmt: skip
