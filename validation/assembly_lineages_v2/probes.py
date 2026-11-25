"""The probe driver of cells.assembly_lineages@2: the engine on OL1's registered inputs (OL5).

OL1's independent references register their inputs (format ool_references.*@1); their harness reads
the engine's saved outputs by role. This driver runs the engine on those inputs and saves the
outputs in the engine's own format: run bundles (records.py) for runs, and probe files for rate
tables and ensembles. It reads only the inputs' files, never the references' code.

    python -m validation.assembly_lineages_v2.probes freeze OUT
        freezes the checkout's source (validation/source_snapshot.py) into OUT/source;
    cd OUT/source && PYTHONPATH=src:. \
        python -m validation.assembly_lineages_v2.probes run INPUTS OUT
        runs from that snapshot (so every record names the revision) on the registered inputs'
        directory INPUTS, writing OUT/roles.json, OUT/FORMAT.md and one directory per role.

**The roles** (ol1_design.json), each under both probed token pairs, (multinomial, kept) and
(multinomial_less_one, extinct) (PAIRS; every output declares every token):
- `kernel_probe` (OL1-1, OL1-4a): ol1_wa's a⁺ and a⁻ for every step at each of the registered
  probe states, from the kernel's own rate function; the states echoed;
- `boundary_probe` (OL1-1, the references' dated amendment beaef20c): the same table for
  ol1_boundary at its registered states (§0.2a's extinct rule in the forward direction);
- `closed_world` (OL1-2, OL1-3): the same table at each closed-world state, for ol1_wa_closed and
  ol1_wa_closed_uncatalysed;
- `rescale_pair` (OL1-3): ol1_wa_closed and ol1_wa_closed_x2 from their initial states with one
  shared stream, RESCALE_EVENTS events each, with every draw's uniforms;
- `wb_ensemble` (OL1-4b): each rung of the large-system ladder, WB_RUNS runs with independent
  streams, none shared across the ladder's rungs and pairs (wb_lineages: lineage word
  WB_RUNS × (rung × 2 + pair) + run), observed at the registered times (the state after the last
  event at or before each);
- `ledger_run` (OL1-4c, OL1-4d, OL1-5): ol1_wa from its initial state, LEDGER_EVENTS events or
  LEDGER_T_END seconds, a row every LEDGER_ROW_EVERY events, the trace and every draw's uniforms;
- `replay` (OL1-6): the ledger run again; `other_stream` (OL1-6): the ledger run under lineage
  word 1;
- `refusals` (OL1-4d): each registered refusal world through the engine's parser, with its
  message, under the probed pair its `refused_under` names (else the first pair; refusal_pair).
The settings not in the registered inputs (the stream words, the molecule capacity, the chunk, the
event guard of the ensembles) are recorded in roles.json.
"""

import argparse
import dataclasses
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PROBE_FORMAT = "cells.assembly_lineages.probe@2"
ROLES_FORMAT = "cells.assembly_lineages.probe_roles@2"
PAIRS = (("multinomial", "kept"), ("multinomial_less_one", "extinct"))
BASE_TOKENS = {
    "free_energy_form": "discrete",
    "membrane_kinetics": "count_on_m",
    "lumen_volume": "declared",
    "empty_catalyst_phase": "uncatalysed",
}
SEED = 1
MOLECULES = 4096
CHUNK = 64
RESCALE_EVENTS = 500
WB_RUNS = 2000
WB_GUARD = 10**7
LEDGER_EVENTS, LEDGER_T_END, LEDGER_ROW_EVERY = 2000, 60.0, 100
KERNEL_WORLD, CLOSED_WORLDS = "ol1_wa", ("ol1_wa_closed", "ol1_wa_closed_uncatalysed")
BOUNDARY_WORLD = "ol1_boundary"
RESCALE_WORLDS = ("ol1_wa_closed", "ol1_wa_closed_x2")
WB_RUNGS = ("ol1_wb_m5", "ol1_wb_m20", "ol1_wb_m80", "ol1_wb_m320")


def tokens(pair):
    measure, last = pair
    return dict(BASE_TOKENS, condensed_measure=measure, last_molecule=last)


def pair_name(pair):
    return f"{pair[0]}__{pair[1]}"


# ------------------------------------------------------------------ the snapshot


def snapshot_files():
    listed = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "--cached", "--others", "--exclude-standard", "-z"]
        + ["--", "src/cells", "validation/assembly_lineages_v2", "validation/id_table.py"]
        + ["validation/source_snapshot.py"],
        check=True,
        capture_output=True,
        timeout=60,
    ).stdout
    names = sorted({os.fsdecode(n) for n in listed.split(b"\0") if n})
    names = [n for n in names if (ROOT / n).is_file() and "__pycache__" not in n]
    return {name: name for name in names} | {"pyproject.toml": "pyproject.toml"}


def freeze(out):
    from validation import source_snapshot

    out = Path(out)
    record = source_snapshot.freeze(ROOT, out / "source", snapshot_files())
    print(json.dumps({"source": str(out / "source"), "git_revision": record["git_revision"]}))


# ------------------------------------------------------------------ files


def _sha256(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=1, sort_keys=True) + "\n")


def _source():
    from cells.records.run_view import _engine_source

    return _engine_source() or {"unstated": "the engine ran from a checkout, not a snapshot"}


def write_probe(directory, role, arrays, descriptor, inputs):
    """A probe's output: probe.npz (its arrays and the echoed inputs) and probe.json."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=False)
    saved = dict(arrays)
    for name, value in inputs["arrays"].items():
        saved[f"input_{name}"] = value
    np.savez(directory / "probe.npz", **saved)
    _json(
        directory / "probe.json",
        {
            "format": PROBE_FORMAT,
            "role": role,
            "source": _source(),
            "inputs": {k: v for k, v in inputs.items() if k != "arrays"}
            | {"arrays": sorted(inputs["arrays"])},
            "arrays_sha256": _sha256(directory / "probe.npz"),
            **descriptor,
        },
    )
    return directory


def _registered(inputs, name):
    path = Path(inputs) / f"{name}.world.json"
    return json.loads(path.read_text()), path


def _definition(registered_world, pair, *, horizon, events, row_every, observations=(),
                trace=True, uniforms=False, lineage=0):  # fmt: skip
    from validation.assembly_lineages_v2 import registered

    experiment = {
        "time_horizon_s": horizon,
        "event_limit": events,
        "row_every_events": row_every,
        "observation_times_s": list(observations),
        "trace": trace,
        "uniforms": uniforms,
    }
    execution = {
        "backend": "cpu",
        "precision": "float64",
        "mode": "single_lineage",
        "stream": {"seed": SEED, "environment": 0, "lineage": lineage, "branch": 0},
        "molecule_capacity": MOLECULES,
        "chunk_events": CHUNK,
    }
    return registered.definition(registered_world, tokens(pair), experiment, execution)


# ------------------------------------------------------------------ rate tables


def rate_table(spec, names, states):
    """(a_plus [S, steps], a_minus [S, steps], free energy [S]) at each state from the kernel's own
    rates on the host: a_plus[s, r] the rate of state -> state + nu_r, a_minus[s, r] the rate of
    state -> state - nu_r (0 where impossible; +inf at a singular state of @1's measure)."""
    from cells.models.assembly_lineages_v2 import kernel, ledger, model

    world = spec.model.world
    structure, layout, tables = model.structure(spec), model.layout(spec), model.tables(spec)
    index = [world.place_index(n) for n in names]
    R = len(world.steps)
    plus = np.zeros((len(states), R))
    minus = np.zeros((len(states), R))
    free = np.zeros(len(states))
    for s, state in enumerate(states):
        counts = np.zeros(structure.places, dtype=np.int64)
        counts[index] = state
        totals = kernel.totals_of(counts, layout, np)
        factor_state, term_states = kernel.states(counts, totals, layout, structure, np)
        rates = kernel.rates(counts, totals, factor_state, term_states, layout, structure, np)
        plus[s] = rates[:R]
        minus[s] = rates[structure.steps : structure.steps + R]
        free[s] = ledger.free_energy(counts, tables, world.terms, layout.terms)
    return plus, minus, free


def _step_work(spec):
    from cells.models.assembly_lineages_v2 import model

    return model.layout(spec).step_work[: len(spec.model.world.steps)]


def _rate_probe(inputs, out, role, world_name, states_file):

    data = json.loads((Path(inputs) / states_file).read_text())
    states = np.asarray(data["states"], dtype=np.int64)
    registered_world, path = _registered(inputs, world_name)
    for pair in PAIRS:
        spec = _parsed_or_refusal(
            Path(out) / role / pair_name(pair),
            _definition(registered_world, pair, horizon=1.0, events=1, row_every=1),
            {"role": role, "registered": path.name, "registered_sha256": _sha256(path)},
        )
        if spec is None:
            continue
        assert [s.id for s in spec.model.world.steps] == data["steps"]
        plus, minus, free = rate_table(spec, data["places"], states)
        write_probe(
            Path(out) / role / pair_name(pair),
            role,
            {"a_plus": plus, "a_minus": minus, "free_energy_kT": free,
             "reservoir_work_kT": _step_work(spec)},
            _descriptor(spec, data, path),
            _inputs(Path(inputs) / states_file, {"states": states}),
        )  # fmt: skip


def kernel_probe(inputs, out):
    _rate_probe(inputs, out, "kernel_probe", KERNEL_WORLD, "ol1_kernel_probe_states.json")


def boundary_probe(inputs, out):
    _rate_probe(inputs, out, "boundary_probe", BOUNDARY_WORLD, "ol1_boundary_probe_states.json")


def closed_world(inputs, out):

    data = json.loads((Path(inputs) / "ol1_closed_world_states.json").read_text())
    states = np.asarray(data["states"], dtype=np.int64)
    for name in CLOSED_WORLDS:
        registered_world, path = _registered(inputs, name)
        for pair in PAIRS:
            spec = _parsed_or_refusal(
                Path(out) / "closed_world" / name / pair_name(pair),
                _definition(registered_world, pair, horizon=1.0, events=1, row_every=1),
                {"role": "closed_world", "registered": path.name,
                 "registered_sha256": _sha256(path)},
            )  # fmt: skip
            if spec is None:
                continue
            assert [s.id for s in spec.model.world.steps] == data["steps"]
            plus, minus, free = rate_table(spec, data["places"], states)
            write_probe(
                Path(out) / "closed_world" / name / pair_name(pair),
                "closed_world",
                {"a_plus": plus, "a_minus": minus, "free_energy_kT": free},
                _descriptor(spec, data, path),
                _inputs(Path(inputs) / "ol1_closed_world_states.json", {"states": states}),
            )


def _descriptor(spec, data, world_path):
    from cells.models.assembly_lineages_v2 import kernel
    from cells.models.assembly_lineages_v2 import spec as v2_spec

    world = spec.model.world
    return {
        "world": {"registered": world_path.name, "sha256": _sha256(world_path),
                  "engine_world_id": v2_spec.world_id(world)},
        "conventions": v2_spec.conventions_rules.to_dict(world.conventions),
        "definition": spec.to_dict(),
        "places": list(data["places"]),
        "steps": list(data["steps"]),
        "channels": kernel.channel_table(world),
        "says": {
            "a_plus": "[state, step]: the rate (1/s) of state -> state + nu, from the kernel's own "
            "rate function (kernel.rates on the host); 0 where impossible; +inf at a singular "
            "state of @1's measure",
            "a_minus": "[state, step]: the rate of state -> state - nu (the step's reverse "
            "channel at the state)",
            "free_energy_kT": "[state]: F(state), the ledger's exact value (k_BT)",
            "reservoir_work_kT": "[step]: w, the held reservoirs' work of the step's forward "
            "(k_BT); its reverse books -w",
            "input_states": "[state, place]: the registered states, echoed, places in `places` "
            "order",
        },
    }  # fmt: skip


def _inputs(path, arrays):
    return {"file": Path(path).name, "sha256": _sha256(path), "arrays": arrays}


# ------------------------------------------------------------------ runs


def _bundle(directory, spec, provenance):
    from cells.models.assembly_lineages_v2 import records, runner

    run = runner.run(spec).check()
    records.write_run(directory, run, provenance=provenance)
    return run


def _parsed_or_refusal(directory, definition, provenance):
    """The parsed definition, or None after writing refused.json with the engine parser's message
    in `directory` (§0.2b rule 8, for one: the world's own declaration decides, never the
    driver)."""
    from cells.definitions.specs import ConfigError, parse_spec

    try:
        return parse_spec(definition)
    except ConfigError as error:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        _json(directory / "refused.json",
              {"format": PROBE_FORMAT, "refused": True, "message": str(error),
               "conventions": definition["model"]["world"]["conventions"],
               "rule": "the engine's parser (cells.assembly_lineages@2's spec)",
               **provenance})  # fmt: skip
        return None


def _run_or_refusal(directory, definition, provenance):
    """A run's bundle, or, when the engine's parser refuses its world (§0.2b rule 8: a run world
    under multinomial_less_one with a membrane place on both sides of a step), refused.json with
    the parser's message in the role's folder."""
    from cells.definitions.specs import ConfigError, parse_spec

    try:
        spec = parse_spec(definition)
    except ConfigError as error:
        directory = Path(directory)
        directory.mkdir(parents=True, exist_ok=False)
        _json(directory / "refused.json",
              {"format": PROBE_FORMAT, "refused": True, "message": str(error),
               "conventions": definition["model"]["world"]["conventions"],
               "rule": "docs/ORIGIN_OF_LIFE_ENGINE_DESIGN.md §0.2b rule 8",
               **provenance})  # fmt: skip
        return None
    return _bundle(directory, spec, provenance)


def rescale_pair(inputs, out):
    for pair in PAIRS:
        for name in RESCALE_WORLDS:
            registered_world, path = _registered(inputs, name)
            _run_or_refusal(
                Path(out) / "rescale_pair" / pair_name(pair) / name,
                _definition(registered_world, pair, horizon=1e9, events=RESCALE_EVENTS,
                            row_every=100, uniforms=True),
                {"operation": "fresh", "role": "rescale_pair", "registered": path.name,
                 "registered_sha256": _sha256(path)},
            )  # fmt: skip


def ledger_runs(inputs, out):
    registered_world, path = _registered(inputs, KERNEL_WORLD)
    for pair in PAIRS:
        for role, lineage in (("ledger_run", 0), ("replay", 0), ("other_stream", 1)):
            _run_or_refusal(
                Path(out) / role / pair_name(pair),
                _definition(registered_world, pair, horizon=LEDGER_T_END, events=LEDGER_EVENTS,
                            row_every=LEDGER_ROW_EVERY, uniforms=True, lineage=lineage),
                {"operation": "fresh", "role": role, "registered": path.name,
                 "registered_sha256": _sha256(path)},
            )  # fmt: skip


def wb_lineages(rung, pair):
    """The lineage words of one rung's runs under one pair (indices in WB_RUNGS and PAIRS order).

    The references' design (OL1-4b) has the ladder's streams "independent, one per run; none
    shared", over all its rungs: each (rung, pair) block takes its own WB_RUNS consecutive words,
    WB_RUNS × (rung × len(PAIRS) + pair) + run, so no two runs of the ladder share a stream identity
    (seed SEED, environment 0, branch 0). The first block keeps the words 0 .. WB_RUNS − 1."""
    base = WB_RUNS * (rung * len(PAIRS) + pair)
    return tuple(range(base, base + WB_RUNS))


def wb_specs(spec, rung, pair):
    """One spec per run of a ladder block, each with its own lineage word (wb_lineages)."""
    return [
        dataclasses.replace(spec, execution=dataclasses.replace(spec.execution, lineage=word))
        for word in wb_lineages(rung, pair)
    ]


def wb_ensemble(inputs, out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import runner

    design = json.loads((Path(inputs) / "ol1_design.json").read_text())
    wb = design["rows"]["OL1-4"]["b_large_system"]
    assert wb["runs_per_rung"] == WB_RUNS and tuple(wb["worlds"]) == WB_RUNGS
    times = tuple(wb["observation_times_s"])
    for rung, name in enumerate(WB_RUNGS):
        registered_world, path = _registered(inputs, name)
        for index, pair in enumerate(PAIRS):
            words = wb_lineages(rung, index)
            spec = parse_spec(
                _definition(registered_world, pair, horizon=wb["t_end_s"], events=WB_GUARD,
                            row_every=WB_GUARD, observations=times, trace=False,
                            lineage=words[0])
            )  # fmt: skip
            specs = wb_specs(spec, rung, index)
            runs = runner.run_lanes(specs)
            world = spec.model.world
            observed, statuses, events = [], [], []
            for run in runs:
                run.check()
                rows = run.rows
                mask = rows["row_kind"] == runner.OBSERVED
                if mask.sum() != len(times) or not np.allclose(rows["row_time"][mask], times):
                    raise AssertionError(f"{name}: a run was not observed at every time")
                observed.append(rows["place_count"][mask])
                statuses.append(run.status)
                events.append(int(rows["row_event"][-1]))
            write_probe(
                Path(out) / "wb_ensemble" / name / pair_name(pair),
                "wb_ensemble",
                {"observed": np.stack(observed), "events": np.asarray(events, dtype=np.int64),
                 "lineage": np.asarray([s.execution.lineage for s in specs], dtype=np.int64),
                 "status": np.asarray(statuses, dtype="<U12")},
                {"world": {"registered": path.name, "sha256": _sha256(path)},
                 "conventions": tokens(pair),
                 "definition": spec.to_dict(),
                 "places": [p.name for p in world.places],
                 "observation_times_s": list(times),
                 "streams": f"one per run, none shared across the ladder's rungs and pairs: "
                 f"seed {SEED}, environment 0, branch 0, lineage word = {WB_RUNS} x (rung index x "
                 f"{len(PAIRS)} + pair index) + the run's index, rungs in the registered order and "
                 f"pairs as listed in roles.json; this block's words {words[0]}..{words[-1]}",
                 "cut": "the state after the last event at or before each observation time",
                 "says": {"observed": "[run, time, place]: the counts at each observation time, "
                          "places in `places` order", "events": "[run]: committed events to the "
                          "horizon", "lineage": "[run]: its stream's lineage word",
                          "status": "[run]: how it ended (complete: held to the horizon)"}},
                {"file": "ol1_design.json", "sha256": _sha256(Path(inputs) / "ol1_design.json"),
                 "arrays": {"observation_times_s": np.asarray(times)}},
            )  # fmt: skip


def refusal_pair(registered_world):
    """The probed pair a registered refusal world is parsed under: the first pair whose tokens
    include the world's `refused_under` (the references' amendment 4: §0.2b rule 8 refuses only
    under multinomial_less_one), else the first pair."""
    wanted = registered_world.get("refused_under") or {}
    for pair in PAIRS:
        if all(tokens(pair).get(key) == value for key, value in wanted.items()):
            return pair
    raise AssertionError(f"{registered_world.get('id')}: no probed pair has {wanted}")


def refusals(inputs, out):
    from cells.definitions.specs import ConfigError, parse_spec

    directory = Path(out) / "refusals"
    directory.mkdir(parents=True, exist_ok=False)
    results = []
    for path in sorted((Path(inputs) / "refusals").glob("*.world.json")):
        registered_world = json.loads(path.read_text())
        pair = refusal_pair(registered_world)
        entry = {"registered": path.name, "sha256": _sha256(path), "conventions": tokens(pair)}
        try:
            parse_spec(_definition(registered_world, pair, horizon=1.0, events=1, row_every=1))
            entry |= {"refused": False, "message": None}
        except ConfigError as error:
            entry |= {"refused": True, "message": str(error)}
        results.append(entry)
    _json(
        directory / "refusals.json",
        {"format": PROBE_FORMAT, "role": "refusals", "source": _source(),
         "conventions": tokens(PAIRS[0]), "results": results,  # each result: its own pair
         "all_refused": all(r["refused"] for r in results)},
    )  # fmt: skip
    if not all(r["refused"] for r in results):
        raise AssertionError("A registered refusal world was admitted")


ROLES = {
    "refusals": refusals,
    "kernel_probe": kernel_probe,
    "boundary_probe": boundary_probe,
    "closed_world": closed_world,
    "rescale_pair": rescale_pair,
    "ledger_run": ledger_runs,
    "wb_ensemble": wb_ensemble,
}


def run(inputs, out, only=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    inputs = Path(inputs)
    (out / "FORMAT.md").write_bytes((Path(__file__).parent / "FORMAT.md").read_bytes())
    for name, role in ROLES.items():
        if only is None or name in only:
            role(inputs, out)
    files = {
        str(p.relative_to(out)): _sha256(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "roles.json"
    }
    _json(
        out / "roles.json",
        {
            "format": ROLES_FORMAT,
            "source": _source(),
            "inputs": {"directory": str(inputs),
                       "files": {str(p.relative_to(inputs)): _sha256(p)
                                 for p in sorted(inputs.rglob("*.json"))}},
            "pairs": [tokens(p) for p in PAIRS],
            "settings": {"seed": SEED, "molecule_capacity": MOLECULES, "chunk_events": CHUNK,
                         "rescale_events": RESCALE_EVENTS, "wb_runs": WB_RUNS,
                         "wb_event_guard": WB_GUARD, "ledger_events": LEDGER_EVENTS,
                         "ledger_t_end_s": LEDGER_T_END, "ledger_row_every": LEDGER_ROW_EVERY,
                         "other_stream_lineage": 1,
                         "wb_lineage_words": f"{WB_RUNS} x (rung index x {len(PAIRS)} + pair "
                         "index) + the run's index: rungs in the registered order, pairs in "
                         "`pairs` order; none shared across the ladder"},
            "roles": sorted(ROLES),
            "files": files,
            "standing": "development run of the engine, not judged",
        },
    )  # fmt: skip
    print(json.dumps({"out": str(out), "files": len(files)}))


def main(argv=None):
    parser = argparse.ArgumentParser(prog="validation.assembly_lineages_v2.probes")
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("out")
    r = sub.add_parser("run")
    r.add_argument("inputs")
    r.add_argument("out")
    r.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        freeze(args.out)
    else:
        run(args.inputs, args.out, args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
