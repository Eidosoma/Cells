"""D148's round for FR-45's in-place widening of cells.operator.site_occupancy@1 (D148, D327): the glue only.

Every site world is written once as JSON (`defs`), and the checkout's two existing tools read those definitions
at each revision's snapshot:
- `validation/fr43_part3/pair_check.py trace` and `compare`: the four traced programs after dead-code elimination,
  their constants, the bindings, and every state field at every step of a full-recording window (DEFS/*.json);
- `validation/results_baseline.py save --sets run-paths --from DEFS/origin` and `compare`: runner.run and the
  windowed, batch, batch-windowed and vector-windowed paths, saved per world at each revision and compared bit
  for bit (DEFS/origin/run-paths/*.json, results_baseline's origin form); `shards` splits the worlds by steps.

For the site worlds this module builds definitions and adds no comparison of its own. A set world has no base
revision to compare with, so `set-world` writes one invented set world for results_baseline's run paths at the
head, and `paths-agree` holds its saved paths against each other: the one check of this module's own.

The worlds:
- fr3_*: every registered world of fr3-site-occupancy-v1, from its own generator
  (validation/tissue/site_occupancy_acceptance_fixtures.registered_world, at its declared dt);
- suite_*: the suite's development site worlds, one per feature the widening could reach: binding alone,
  internalisation, the wash beside a stand-in wall and beside a node's own sites (FR-27, FR-28), W on a replaced
  slot (FR-26), and @2 reading a site population's occupied fraction (FR-24).

Usage (PYTHONPATH at a snapshot, JAX_ENABLE_X64=1, the CPUs the lead assigns):
  python -B -m validation.fr45.d148_round defs DEFS
  python -B -m validation.fr45.d148_round shards DEFS K          (K lines of world names, balanced by steps)
  python -B -m validation.fr45.d148_round set-world ORIGIN       (ORIGIN/run-paths/fr45_set_paths.json)
  python -B -m validation.fr45.d148_round paths-agree SAVED OUT_JSON
"""

import argparse
import json
import sys
from pathlib import Path


def fr3_worlds():
    """{name: raw definition} of fr3-site-occupancy-v1's registered worlds."""
    from validation.tissue import site_occupancy_acceptance_fixtures as acceptance

    return {f"fr3_{w}": acceptance.registered_world(w) for w in acceptance.world_ids()}


def _site_routed():
    """@2 routing a site population's occupied fraction to the turnover's production in its cell (FR-24's
    development form: the face-free cell, r0 on contact_0 at theta0 0.4, the site operator, @2, the turnover)."""
    from cells.registry.inventory_species import add_inventory_species
    from validation.tissue import regulated_availability_fixtures as rf
    from validation.tissue import secreted_species_fixtures as fx
    from validation.tissue import site_occupancy_fixtures as sfx

    raw = sfx.face_free_sites([sfx.population("r0", theta0=0.4)], end=0.02)
    raw = add_inventory_species(
        raw, "X0", trace_mM=1e-9, diffusivity_m2_per_s=1e-10, floor_fmol=1e-20
    )
    target = dict(operator=fx.TURNOVER, control="turnover_rate", ids=["make_x0"],
                  evaluation="target_half_steps", operating_range=[0.0, 1.0])  # fmt: skip
    entry = dict(id="c_site", target=target, law="site_fraction", basal=0.1,
                 source={"site_population": "r0", "quantity": "occupied_fraction"})  # fmt: skip
    raw = rf.with_coupling(raw, species=[], couplings=[entry])
    coupling = next(
        b
        for b in raw["model"]["operators"]
        if b["law"].startswith("cells.operator.species_regulated_availability@")
    )
    coupling["law"] = "cells.operator.species_regulated_availability@2"
    raw["model"]["operators"].append(dict(
        law=fx.TURNOVER, species=rf.identities(["X0"]), templates=[],
        routes=[dict(id="make_x0", species="X0", node="cell_0", kind="production")]))  # fmt: skip
    raw["experiment"]["turnover_controls"] = [
        dict(route_id="make_x0", carrier_id="cell_0", schedule=[dict(time=0.0, rate=2e-4)])
    ]
    return raw


def suite_worlds():
    """{name: raw definition} of the suite's development site worlds (the module docstring)."""
    from validation.tissue import site_occupancy_fixtures as sfx
    from validation.tissue import wash_schedule_fixtures as wfx

    washed = dict(dt=0.01, end=0.05, observation_times=[0.0, 0.02, 0.05])
    event = [(0.02, "well", 0.5, {wfx.TRACER: wfx.TRACE_mM})]
    occupied = [sfx.population("o0", patch="contact_0", theta0=0.4),
                sfx.population("o1", patch="contact_1", theta0=0.1)]  # fmt: skip
    return {
        "suite_binding": sfx.face_free_sites(),
        "suite_internalisation": sfx.face_free_sites([sfx.population("i0", theta0=0.3, k_int=0.5)]),
        "suite_wash_stand_in": wfx.with_wash(wfx.well(**washed), ["well"], event),
        "suite_wash_node_sites": wfx.with_wash(wfx.well(wall="node", **washed), ["well"], event),
        "suite_occupant": sfx.replaced_sites(occupied, {"o1": (0.6, 1.0, None)}),
        "suite_site_source": _site_routed(),
    }


def _origin(out, made):
    """results_baseline's origin form: OUT/run-paths/NAME.json, {"name", "definition"}."""
    folder = Path(out) / "run-paths"
    folder.mkdir(parents=True, exist_ok=True)
    for name, raw in made.items():
        (folder / f"{name}.json").write_text(
            json.dumps(dict(name=name, definition=raw), sort_keys=True)
        )


def defs(out):
    """Write every world's definition as DEFS/NAME.json (sorted keys) and in results_baseline's origin
    form under DEFS/origin, then list the names."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    made = {**fr3_worlds(), **suite_worlds()}
    for name, raw in made.items():
        (out / f"{name}.json").write_text(json.dumps(raw, sort_keys=True))
    _origin(out / "origin", made)
    print(len(made), "worlds:", " ".join(sorted(made)))
    return 0


def shards(folder, k):
    """Print K lines of world names (DEFS/*.json), each line's steps (end / dt) summed about evenly:
    the longest world first onto the lightest line."""
    steps = {}
    for path in sorted(Path(folder).glob("*.json")):
        raw = json.loads(path.read_text())
        steps[path.stem] = round(raw["experiment"]["end_time"] / raw["execution"]["dt"])
    lines = [[0, []] for _ in range(k)]
    for name in sorted(steps, key=lambda n: (-steps[n], n)):
        line = min(lines, key=lambda x: x[0])
        line[0] += steps[name]
        line[1].append(name)
    for _, names in lines:
        print(" ".join(sorted(names)))
    return 0


def set_paths_world():
    """An invented set world for the run paths (FR-45's first-run rule: no registered input): Q1
    and Q2 competing for contact_0's outside face, 300 steps of 2 ms (two windows of
    results_baseline's 200), and a wash of 0.4 of ecs_0 at 0.1 s for a buffer of Q2."""
    from validation.tissue import site_occupancy_fixtures as sfx
    from validation.tissue import wash_schedule_fixtures as wfx

    pops = [sfx.member("m1", ligand="Q1", theta0=0.35),
            sfx.member("m2", ligand="Q2", k_on=1.1e3, k_off=0.25)]  # fmt: skip
    raw = sfx.set_world(pops, [sfx.site_set()], node_mM={"Q1": 2.4e-3, "Q2": 1.3e-3}, dt=2e-3,
                        end=0.6, observation_times=[0.0, 0.6])  # fmt: skip
    buffer = {wfx.TRACER: 3e-12, "Q1": sfx.SET_TRACE_mM, "Q2": 5e-4}
    return wfx.with_wash(raw, ["ecs_0"], [(0.1, "ecs_0", 0.4, buffer)])


def set_world(out):
    _origin(out, {"fr45_set_paths": set_paths_world()})
    print("1 world: fr45_set_paths")
    return 0


# results_baseline saves every path's final state: runner.run's, run_windowed's and run_batch's
# checkpoints, held as jax arrays, are saved whole since its flatten reads an array-like as one
# array (3961cafb, D410), as the batch-windowed and vector-windowed checkpoints' host arrays always
# were. So: every path's final state, runner.run's own included, against runner.run's last history
# row; run_batch's histories against runner.run's history; and every path's final step index
# against runner.run's.
FINAL_STATES = (
    "run:final.state",
    "run_windowed:final.state",
    "run_batch:world1.final.state",
    "run_batch:world2.final.state",
    "run_batch_windowed:world1.final.state",
    "run_batch_windowed:world2.final.state",
    "run_vector_windowed:world1.final.state",
    "run_vector_windowed:world2.final.state",
)
HISTORIES = ("run_batch:world1.history", "run_batch:world2.history")
STEP_INDICES = (
    "run_windowed:final",
    "run_batch:world1.final",
    "run_batch:world2.final",
    "run_batch_windowed:world1.final",
    "run_batch_windowed:world2.final",
    "run_vector_windowed:world1.final",
    "run_vector_windowed:world2.final",
)


def _unequal(saved, reference, key):
    """None when saved[key] is reference bit for bit (dtype, shape and bytes), else the problem."""
    if key not in saved.files:
        return dict(key=key, problem="missing")
    q = saved[key]
    if reference.dtype != q.dtype or reference.shape != q.shape:
        return dict(
            key=key, problem=f"{q.dtype}{q.shape} against {reference.dtype}{reference.shape}"
        )
    if reference.tobytes() != q.tobytes():
        return dict(key=key, problem="not bitwise")
    return None


def paths_agree(saved, out):
    """Each world saved by results_baseline's run paths (SAVED/run-paths/*.npz) against itself, bit
    for bit (dtype, shape and bytes): every path's final state (runner.run's, run_windowed's, and both
    worlds' of run_batch, the batch-windowed and the vector-windowed paths) against runner.run's last
    history row, run_batch's two histories against runner.run's history, and every path's final step
    index against runner.run's. A baseline saved before results_baseline kept those final states
    (3961cafb, D410) lacks their keys, and they are reported missing. Writes OUT_JSON; exit 0 when all
    agree."""
    import numpy as np

    rows = {}
    for path in sorted((Path(saved) / "run-paths").glob("*.npz")):
        record = json.loads(path.with_suffix(".json").read_text())
        if "refusal" in record:
            rows[path.stem] = dict(agree=False, refusal=record["refusal"]["type"])
            continue
        a = np.load(path)
        fields = sorted(k[len("run:history.") :] for k in a.files if k.startswith("run:history."))
        pairs = []  # (the reference array, the key that must equal it)
        for f in fields:
            history = a[f"run:history.{f}"]
            pairs += [(history[-1], f"{p}.{f}") for p in FINAL_STATES]
            pairs += [(history, f"{p}.{f}") for p in HISTORIES]
        pairs += [(a["run:final.step_index"], f"{p}.step_index") for p in STEP_INDICES]
        bad = [problem for problem in (_unequal(a, ref, key) for ref, key in pairs) if problem]
        compared = len(pairs)
        rows[path.stem] = dict(agree=not bad and bool(fields), fields=len(fields), compared=compared,
                               problems=bad[:20])  # fmt: skip
    ok = bool(rows) and all(r["agree"] for r in rows.values())
    Path(out).write_text(json.dumps(dict(agree=ok, worlds=rows), indent=1) + "\n")
    print(
        ("agree" if ok else "DIFFERS")
        + f": {sum(r['agree'] for r in rows.values())} of {len(rows)} worlds"
    )
    return 0 if ok else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("defs").add_argument("defs")
    cut = sub.add_parser("shards")
    cut.add_argument("defs")
    cut.add_argument("k", type=int)
    sub.add_parser("set-world").add_argument("origin")
    agree = sub.add_parser("paths-agree")
    agree.add_argument("saved")
    agree.add_argument("out")
    args = parser.parse_args(argv)
    if args.command == "shards":
        return shards(args.defs, args.k)
    if args.command == "set-world":
        return set_world(args.origin)
    if args.command == "paths-agree":
        return paths_agree(args.saved, args.out)
    return defs(args.defs)


if __name__ == "__main__":
    sys.exit(main())
