"""The probe driver of cells.model.assembly_lineages@2 on OL5's registered OL2 and OL3 inputs.

OL5's references register OL2's and OL3's inputs: worlds (ool_references.world2@1), runs (run2@1),
probe states (probe_states2@1), the partition parents (ol3_parents@1), 22 refusal declarations,
and amendment 7's division inputs (division_inputs@1). Their harness (harness2) reads the engine's
outputs by role, through an adapter written from FORMAT_OL2.md alone. This driver runs the engine
on those inputs and saves its outputs in the engine's own format. It reads only the inputs' folder
(an export of them, INPUTS/designs/...), never the references' code.

    python -m validation.assembly_lineages_v2.probes2 freeze OUT
        freezes the checkout's source (validation/source_snapshot.py) into OUT/source;
    cd OUT/source && PYTHONPATH=src:. \
        python -m validation.assembly_lineages_v2.probes2 run INPUTS OUT
        runs from that snapshot (so every record names the revision) on the export folder INPUTS,
        writing OUT/roles2.json, OUT/FORMAT.md, OUT/FORMAT_OL2.md and one directory per role.

**The roles** (FORMAT_OL2.md, "OL5's probe roles"), each under the registered conventions:
- `refusals2` (OL2-5): each declaration through the reader (registered.py) and the engine's
  parser, with the parser's message; a run declaration on its registered world, with amendment 7's
  division inputs;
- `kernel2` (OL2-1, OL2-2): ol2_wa and ol2_wa_diffusion at their probe states, ol2_closed and
  ol2_two at their one-vesicle states (ol2_two on its first founder vesicle's world): a⁺ and a⁻ of
  every vesicle step from the kernel's own rate function on the host (probes.rate_table), whether
  each event's end state lyses (kernel.lysis_at, where the event's rate is positive), and the
  state's derived geometry (lumen.host_derived);
- `partition` (OL3-1): each parent's attempts: every attempt's block of uniforms from the engine's
  own fission stream (division.block) and its daughters from the engine's own split
  (division.split);
- `runs2` (OL2-3, OL2-4, OL3-2 to OL3-5): each registered run with amendment 7's division inputs,
  in the diagnostic mode (§0.2d item 10.5), as a bundle (records.py).
The settings not in the registered inputs (STREAM, CAPACITY, CHUNK, ROW_EVERY, the partition's
carrier keys) were fixed before the first run (the lead's rulings of 22 November 2026) and are
recorded in roles2.json; a different seed waits for a ruling.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

from validation.assembly_lineages_v2 import probes, registered

ROLES2_FORMAT = "cells.assembly_lineages.probe_roles2@1"
STREAM = {"seed": 1, "environment": 0, "lineage": 0, "branch": 0}
CAPACITY = 2**18  # above every registered count (162,389 at most) and every founder's
CHUNK = 64
ROW_EVERY = 1000
EXECUTION = {"backend": "cpu", "precision": "float64", "mode": "single_lineage", "stream": STREAM,
             "molecule_capacity": CAPACITY, "chunk_events": CHUNK}  # fmt: skip
PROBE_EXPERIMENT = {"time_horizon_s": 1.0, "event_limit": 1, "row_every_events": 1,
                    "observation_times_s": [], "trace": False, "uniforms": False}  # fmt: skip
RUN_EXPERIMENT = {"row_every_events": ROW_EVERY, "observation_times_s": [], "trace": True,
                  "uniforms": True, "diagnostic": True}  # fmt: skip
KERNEL_WORLDS = (
    ("ol2_wa", "ol2_wa_probe_states.json"),
    ("ol2_wa_diffusion", "ol2_wa_diffusion_probe_states.json"),
    ("ol2_closed", "ol2_closed_states.json"),
    ("ol2_two", "ol2_two_states.json"),
)
RUNS = ("ol2_lysis_run", "ol2_shared_run", "ol3_population_run", "ol3_shear_probe_run",
        "ol3_lineage_run", "ol3_slots_full_run")  # fmt: skip
OL3_WORLDS = ("ol3_population", "ol3_shear_probe", "ol3_lineage", "ol3_slots_full")
DIVISION = "ol3_division.json"
PARENTS = "ol3_parents.json"
_sha256, _json, _source = probes._sha256, probes._json, probes._source


def _designs(inputs):
    return Path(inputs) / "designs"


def _load(path):
    return json.loads(Path(path).read_text())


def _division(inputs):
    path = _designs(inputs) / DIVISION
    document = _load(path)
    if document.get("format") != registered.DIVISION_FORMAT:
        raise ValueError(f"{path.name} is {registered.DIVISION_FORMAT}")
    return document["worlds"], path


def _run_definition(inputs, run, experiment):
    """A registered run's definition (its world, amendment 7's division inputs, the settings)."""
    designs = _designs(inputs)
    world_path = designs / f"{run['world']}.world2.json"
    division, division_path = _division(inputs)
    definition = registered.definition2(
        _load(world_path), experiment=experiment, execution=EXECUTION, run=run,
        division=division.get(run["world"]),
    )  # fmt: skip
    return definition, {"registered_world": world_path.name,
                        "registered_world_sha256": _sha256(world_path),
                        "division_inputs": division_path.name,
                        "division_inputs_sha256": _sha256(division_path)}  # fmt: skip


# ------------------------------------------------------------------ refusals (OL2-5)


def refusals2(inputs, out):
    """Each registered declaration through the reader and the engine's parser."""
    from cells.definitions.specs import ConfigError, parse_spec

    directory = Path(out) / "refusals2"
    directory.mkdir(parents=True, exist_ok=False)
    results = {}
    for path in sorted((_designs(inputs) / "refusals2").glob("*.json")):
        document = _load(path)
        entry = {"file": path.name, "sha256": _sha256(path)}
        if document.get("format") == registered.RUN_FORMAT2:
            definition, provenance = _run_definition(inputs, document, PROBE_EXPERIMENT)
            entry |= provenance
        else:
            definition = registered.definition2(document, experiment=PROBE_EXPERIMENT,
                                                execution=EXECUTION)  # fmt: skip
        try:
            parse_spec(definition)
            entry |= {"refused": False, "message": None}
        except ConfigError as error:
            entry |= {"refused": True, "message": str(error)}
        results[document.get("id", path.name.split(".")[0])] = entry
    admitted = sorted(k for k, v in results.items() if not v["refused"])
    _json(
        directory / "refusals.json",
        {"format": probes.PROBE_FORMAT, "role": "refusals2", "source": _source(),
         "rule": "the engine's parser (cells.model.assembly_lineages@2's spec), after the reader "
                 "(validation/assembly_lineages_v2/registered.py), which checks nothing",
         "results": results, "all_refused": not admitted},
    )  # fmt: skip
    return f"admitted: {admitted}" if admitted else None


# ------------------------------------------------------------------ kernel probes (OL2-1, OL2-2)


def _vesicle_steps(world):
    """The steps with a membrane or lumen place, in declared order (a pool step is not probed)."""
    return [
        r for r, step in enumerate(world.steps)
        if any(world.places[world.place_index(n)].phase != "pool"
               for n, _ in (*step.reactants, *step.products))
    ]  # fmt: skip


def kernel_table(spec, names, states):
    """(a_plus, a_minus, lyses_plus, lyses_minus [S, R], derived [S, 7], free energy [S]) at each
    registered state: the rates from the kernel's own function on the host; a lysis flag where the
    event's rate is positive, from the kernel's test of its end state (the engine's own change of
    that channel); the state's derived geometry (lumen.host_derived)."""
    from cells.models.assembly_lineages_v2 import diagnostic, kernel, lumen, model, runner

    world = spec.model.world
    plus, minus, free = probes.rate_table(spec, names, states)
    layout = model.layout(spec)
    change, _ = runner.changes(layout, diagnostic._shape(layout))
    capacity_steps = layout.entry_place.shape[0]
    index = [world.place_index(n) for n in names]
    places = layout.place_held.shape[0]
    R = len(world.steps)
    lyses_plus = np.zeros(plus.shape, dtype=bool)
    lyses_minus = np.zeros(minus.shape, dtype=bool)
    derived = np.zeros((len(states), len(lumen.DERIVED)))
    for s, state in enumerate(states):
        counts = np.zeros(places, dtype=np.int64)
        counts[index] = state
        values = lumen.host_derived(world, counts[: len(world.places)])
        derived[s] = [values[k] for k in lumen.DERIVED]
        for r in range(R):
            if plus[s, r] > 0:
                lyses_plus[s, r] = bool(kernel.lysis_at(counts + change[r], layout, np))
            if minus[s, r] > 0:
                lyses_minus[s, r] = bool(
                    kernel.lysis_at(counts + change[capacity_steps + r], layout, np)
                )
    return plus, minus, lyses_plus, lyses_minus, derived, free


def kernel2(inputs, out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages_v2 import kernel, lumen
    from cells.models.assembly_lineages_v2 import spec as v2_spec

    designs = _designs(inputs)
    for world_name, states_file in KERNEL_WORLDS:
        world_path, states_path = designs / f"{world_name}.world2.json", designs / states_file
        document, data = _load(world_path), _load(states_path)
        vesicle = 0 if "vesicles" in document["founder"] else None
        spec = parse_spec(registered.definition2(document, experiment=PROBE_EXPERIMENT,
                                                 execution=EXECUTION, vesicle=vesicle))  # fmt: skip
        world = spec.model.world
        names = ([f"{e['species']}@membrane" for e in document["membrane"]]
                 + [f"{e['species']}@lumen" for e in document["lumen"]]
                 + [f"{s}@pool" for s in document["pool"]["finite"]])  # fmt: skip
        states = np.asarray([[c for part in s for c in part] for s in data["states"]],
                            dtype=np.int64)  # fmt: skip
        plus, minus, l_plus, l_minus, derived, free = kernel_table(spec, names, states)
        steps = _vesicle_steps(world)
        probes.write_probe(
            Path(out) / "kernel2" / world_name,
            "kernel2",
            {"a_plus": plus[:, steps], "a_minus": minus[:, steps], "lyses_plus": l_plus[:, steps],
             "lyses_minus": l_minus[:, steps], "derived": derived, "free_energy_kT": free,
             "reservoir_work_kT": probes._step_work(spec)[steps]},
            {"world": {"registered": world_path.name, "sha256": _sha256(world_path),
                       "engine_world_id": v2_spec.world_id(world),
                       "founder_vesicle": vesicle},
             "conventions": v2_spec.conventions_rules.to_dict(world.conventions),
             "definition": spec.to_dict(),
             "places": names,
             "steps": [world.steps[r].id for r in steps],
             "channels": kernel.channel_table(world),
             "derived": list(lumen.DERIVED),
             "says": {
                 "input_states": "[state, place]: the registered states, echoed in the registered "
                 "order (membrane, lumen, finite pool; `places` names each column)",
                 "a_plus": "[state, step]: the rate (1/s) of the step's forward event at the "
                 "state, from the kernel's own rate function (kernel.rates on the host); 0 where "
                 "it cannot fire; steps in `steps` order (the vesicle steps, declared order)",
                 "a_minus": "[state, step]: the rate of the step's reverse event at the state",
                 "lyses_plus": "[state, step]: whether the forward event's end state has "
                 "sigma > sigma_max (kernel.lysis_at); false where a_plus is 0",
                 "lyses_minus": "[state, step]: the same for the reverse event; false where "
                 "a_minus is 0",
                 "derived": "[state, 7]: W (quanta), A (m^2), R (m), V_osm, V_sph and V (L), "
                 "sigma (N/m) at the state (lumen.host_derived; V_osm 0 at an empty lumen)",
                 "free_energy_kT": "[state]: F(state), the ledger's value (k_BT)",
                 "reservoir_work_kT": "[step]: the held reservoirs' work of the forward event "
                 "(k_BT); its reverse books minus that",
             }},
            {"file": states_path.name, "sha256": _sha256(states_path),
             "arrays": {"states": states}},
        )  # fmt: skip
    return None


# ------------------------------------------------------------------ the partition probe (OL3-1)


def _ol3_quantum(inputs):
    """The area quantum the registered OL3 worlds declare (all equal): the lumen split's weights
    are V_sph(A_j)/Σ V_sph(A_l), in which it cancels."""
    quanta = {_load(_designs(inputs) / f"{w}.world2.json")["geometry"]["area_quantum_m2"]
              for w in OL3_WORLDS}  # fmt: skip
    if len(quanta) != 1:
        raise ValueError(f"the OL3 worlds declare several area quanta: {sorted(quanta)}")
    return quanta.pop()


def partition(inputs, out):
    from cells.models.assembly_lineages_v2 import division, streams

    path = _designs(inputs) / PARENTS
    data = _load(path)
    q = _ol3_quantum(inputs)
    base = streams.base_key_data(STREAM["seed"], STREAM["environment"], STREAM["lineage"],
                                 STREAM["branch"])  # fmt: skip
    attempts = int(data["attempts_per_parent"])
    arrays, parents = {}, []
    for key, parent in enumerate(data["parents"]):
        membrane, quanta, k = parent["counts"], parent["k_area"], parent["k"]
        lumen = parent["lumen"]
        size = int(sum(membrane)) + int(k) + int(sum(lumen))
        u = np.zeros((attempts, size))
        by_membrane = np.zeros((attempts, k, len(membrane)), dtype=np.int64)
        by_lumen = np.zeros((attempts, k, len(lumen)), dtype=np.int64)
        for counter in range(attempts):
            block = division.block(base, key, counter, size)
            u[counter] = block
            by_membrane[counter], by_lumen[counter] = division.split(membrane, quanta, lumen, k, q,
                                                                     block)  # fmt: skip
        arrays |= {f"{parent['id']}_u": u, f"{parent['id']}_membrane": by_membrane,
                   f"{parent['id']}_lumen": by_lumen}  # fmt: skip
        parents.append({"id": parent["id"], "carrier_key": key, "counters": [0, attempts - 1],
                        "k": k, "uniforms_per_attempt": size})  # fmt: skip
    probes.write_probe(
        Path(out) / "partition",
        "partition",
        arrays,
        {"parents": parents,
         "stream": STREAM,
         "area_quantum_m2": q,
         "says": {
             "<id>_u": "[attempt, N + k + N_L]: the attempt's block of uniforms, as used: rule 9's "
             "N (one per listed membrane molecule) and k (pi), then rule 10's N_L (one per listed "
             "lumen molecule); the engine's fission stream (domain 2) of the parent's carrier key "
             "at counter = the attempt's index (division.block)",
             "<id>_membrane": "[attempt, daughter, species]: each daughter's membrane counts, by "
             "daughter (block t went to daughter pi[t]), from the engine's split (division.split)",
             "<id>_lumen": "[attempt, daughter, lumen species]: each daughter's lumen counts",
         }},
        {"file": path.name, "sha256": _sha256(path), "arrays": {}},
    )  # fmt: skip
    return None


# ------------------------------------------------------------------ the runs (OL2-3, OL2-4, OL3)


def runs2(inputs, out):
    """Each registered run's bundle; a run the engine refuses (its parser, or a check before the
    first event) writes refused.json with the message in its folder instead, and the role reports
    it, after the other runs."""
    from cells.definitions.specs import ConfigError, parse_spec

    refused = []
    for name in RUNS:
        run_path = _designs(inputs) / f"{name}.json"
        run = _load(run_path)
        definition, provenance = _run_definition(inputs, run, RUN_EXPERIMENT)
        provenance = {"operation": "fresh", "role": "runs2", "registered_run": run_path.name,
                      "registered_run_sha256": _sha256(run_path), **provenance}  # fmt: skip
        directory = Path(out) / "runs2" / name
        try:
            probes._bundle(directory, parse_spec(definition), provenance)
        except ConfigError as error:
            directory.mkdir(parents=True, exist_ok=True)
            _json(directory / "refused.json",
                  {"format": probes.PROBE_FORMAT, "refused": True, "message": str(error),
                   "rule": "the engine's parser or its checks before the first event",
                   **provenance})  # fmt: skip
            refused.append(name)
    return f"refused: {refused}" if refused else None


ROLES2 = {"refusals2": refusals2, "kernel2": kernel2, "partition": partition, "runs2": runs2}


def run(inputs, out, only=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    inputs = Path(inputs)
    here = Path(__file__).parent
    for page in ("FORMAT.md", "FORMAT_OL2.md"):
        (out / page).write_bytes((here / page).read_bytes())
    chosen = [name for name in ROLES2 if only is None or name in only]
    problems = {}
    for name in chosen:
        problem = ROLES2[name](inputs, out)
        if problem:
            problems[name] = problem
    files = {
        str(p.relative_to(out)): _sha256(p)
        for p in sorted(out.rglob("*"))
        if p.is_file() and p.name != "roles2.json"
    }
    _json(
        out / "roles2.json",
        {
            "format": ROLES2_FORMAT,
            "source": _source(),
            "inputs": {"directory": str(inputs),
                       "files": {str(p.relative_to(inputs)): _sha256(p)
                                 for p in sorted(inputs.rglob("*.json"))}},
            "settings": {
                "stream": STREAM, "molecule_capacity": CAPACITY, "chunk_events": CHUNK,
                "row_every_events": ROW_EVERY, "execution": EXECUTION,
                "probe_experiment": PROBE_EXPERIMENT, "run_experiment": RUN_EXPERIMENT,
                "partition": {"carrier_keys": "each parent's index in ol3_parents.json",
                              "counters": "0 to attempts_per_parent - 1",
                              "area_quantum_m2": "the registered OL3 worlds' (all equal)"},
                "fixed": "before the first run (the lead's rulings of 22 November 2026); a "
                         "different seed waits for a ruling",
            },
            "roles": chosen,
            "problems": problems,
            "files": files,
            "standing": "the engine's outputs on OL5's registered OL2 and OL3 inputs, judged only "
                        "by OL5's harness through its adapter",
        },
    )  # fmt: skip
    print(json.dumps({"out": str(out), "files": len(files), "problems": problems}))
    if problems:
        raise SystemExit(f"probes2: {problems}")


def main(argv=None):
    parser = argparse.ArgumentParser(prog="validation.assembly_lineages_v2.probes2")
    sub = parser.add_subparsers(dest="command", required=True)
    f = sub.add_parser("freeze")
    f.add_argument("out")
    r = sub.add_parser("run")
    r.add_argument("inputs")
    r.add_argument("out")
    r.add_argument("--only", nargs="*")
    args = parser.parse_args(argv)
    if args.command == "freeze":
        probes.freeze(args.out)
    else:
        run(args.inputs, args.out, args.only)
    return 0


if __name__ == "__main__":
    sys.exit(main())
