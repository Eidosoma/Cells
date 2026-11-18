"""Development evidence for the execution-path correction (fr45-physics b312936c): a refusal on the
vector path against the host path. K2's guard (a), the pump's moves flipped alone (the refusal the
engine's material ledger makes, test_fr4_world_engine), over FR-4's development world's first 5
steps, through engine_records.run on both paths. Analysis only, from an execution snapshot's root
(it ran from fr45/pipeline/ until it moved here, its logic unchanged, its body now in main()):

    python -m validation.compartment_ph_engine.refusal_paths OUT_JSON
"""

import copy
import dataclasses
import json
import sys
import time

from cells.kinds import transporter
from validation.compartment_ph_engine import definitions as defs
from validation.compartment_ph_engine import engine_records, planted

STEPS = 5


def short(definition, steps=STEPS):
    d = copy.deepcopy(definition)
    dt = d["execution"]["dt"]
    d["experiment"]["end_time"] = steps * dt
    d["experiment"]["observation_times"] = [0.0, steps * dt]
    d["execution"]["max_steps"] = steps + 8
    return d


def flipped(state, potentials, control, p, *, xp):
    r = transporter.rates(state, potentials, control, p, xp=xp)
    return r._replace(cell=-r.cell, outside=-r.outside)


def main(argv):
    guard = dataclasses.replace(transporter.TRANSPORTER, rates=flipped)
    out = {}
    for path in ("host", "vector"):
        started = time.perf_counter()
        record = engine_records.run(short(defs.fr4_world()), registry=planted.registry(guard),
                                    path=path)
        out[path] = {k: record.get(k) for k in ("path", "admitted", "completed", "refusal",
                                                "refusal_reason", "steps", "record_s")}
        out[path]["series_keys"] = sorted(record.get("series", {}))
        out[path]["seconds"] = time.perf_counter() - started
        print(path, json.dumps(out[path]), flush=True)
    out["same_verdict"] = all(out[p]["admitted"] and not out[p]["completed"] for p in out) and all(
        "accounting failed: local" in (out[p]["refusal"] or "") for p in ("host", "vector"))
    print("same verdict (admitted, refused, naming the local material ledger):",
          out["same_verdict"])
    with open(argv[0], "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main(sys.argv[1:])
