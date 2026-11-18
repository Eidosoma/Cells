"""Every descendant on the T2-02-like world: the followed path against the single lineage.

A development check (not judged) of every-descendant mode (runner.run_population) at scale: the
T2-02-like comparison world (worlds.py; matrix seed 20261117, founder seed 1117, stream seed 1),
each GARD form, GENERATIONS generations at the default 64 lanes. For each form it writes both
bundles and check.json: the followed path's records against the single lineage of as many
fissions, array by array, bitwise (the storage column fission_slot apart); the census (every life
the founder or a daughter of a fission that ran); unique keys; and the ledger's closure.

    python -m validation.assembly_lineages.population_check freeze OUT
    cd OUT/source && PYTHONPATH=src:. \
        python -m validation.assembly_lineages.population_check run OUT
"""

import argparse
import json
from pathlib import Path

import numpy as np

from validation.assembly_lineages import probes

GENERATIONS, LANES, BUDGET = 5, 64, 4096


def path_records(run):
    """The followed path's records, selected from an every-descendant run."""
    table = run.fissions
    by_parent = {int(k): i for i, k in enumerate(table["fission_parent"])}
    path = [0]
    while path[-1] in by_parent:
        i = by_parent[path[-1]]
        path.append(int(table["fission_daughters"][i, int(table["fission_followed"][i])]))
    rows = np.isin(run.rows["occupant"][:, 0], path)
    fissions = np.isin(table["fission_parent"], path)
    growths = np.isin(run.trace["growth_carrier"], path)
    edges = np.concatenate(([0], np.cumsum(run.trace["events_per_growth"])))
    events = np.concatenate(
        [np.arange(edges[g], edges[g + 1]) for g in np.flatnonzero(growths)]
    ).astype(int)
    out = {f"rows.{k}": v[rows] for k, v in run.rows.items()}
    out |= {f"fissions.{k}": v[fissions] for k, v in table.items() if k != "fission_slot"}
    out |= {
        "trace.event_channel": run.trace["event_channel"][events],
        "trace.event_time": run.trace["event_time"][events],
        "trace.events_per_growth": run.trace["events_per_growth"][growths],
        "trace.growth_carrier": run.trace["growth_carrier"][growths],
    }
    return path, out


def run(out):
    from cells.definitions.specs import parse_spec
    from cells.models.assembly_lineages import (
        GARD_PAIR_CONSISTENT,
        GARD_SINGLE_EVENT,
        records,
        runner,
    )

    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    report = {}
    for form, law in (
        ("pair-consistent", GARD_PAIR_CONSISTENT),
        ("single-event", GARD_SINGLE_EVENT),
    ):
        data = probes.lineage_definition(law, fissions=GENERATIONS)
        single = runner.run(parse_spec(data))
        data["execution"] |= {"mode": "every_descendant", "lanes": LANES}
        data["experiment"]["life_budget"] = BUDGET
        population = runner.run_population(parse_spec(data))
        path, view = path_records(population)
        differs = [
            name
            for name, values in view.items()
            if not np.array_equal(
                getattr(single, name.split(".")[0])[name.split(".")[1]],
                values,
                equal_nan=values.dtype.kind == "f",
            )
        ]
        lives = population.lives
        divided = int(np.sum(lives["life_end_reason"] == "divided"))
        report[form] = {
            "followed_path": [int(k) for k in path],
            "differs_from_single_lineage": differs,
            "arrays_compared": sorted(view),
            "lives": int(len(lives["life_key"])),
            "census_holds": 2 * divided + 1 == len(lives["life_key"]),
            "keys_unique": len(set(lives["life_key"].tolist())) == len(lives["life_key"]),
            "end_reasons": {
                str(k): int(v)
                for k, v in zip(
                    *np.unique(lives["life_end_reason"], return_counts=True), strict=True
                )
            },
            "ledger": population.closure,
            "events": int(population.timings["events"]),
            "run_seconds": population.timings["run_seconds"],
            "status": population.status,
        }
        records.write_run(out / form / "single", single, provenance={"operation": "check"})
        records.write_run(
            out / form / "every_descendant", population, provenance={"operation": "check"}
        )
    record = {
        "kind": "cells.assembly_lineages.population_check@1",
        "judged": False,
        "generations": GENERATIONS,
        "lanes": LANES,
        "life_budget": BUDGET,
        "source": probes._source(),
        "forms": report,
        "holds": all(
            not r["differs_from_single_lineage"] and r["census_holds"] and r["keys_unique"]
            for r in report.values()
        ),
    }
    (out / "check.json").write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"holds": record["holds"]}))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze")
    frozen.add_argument("out", type=Path)
    running = commands.add_parser("run")
    running.add_argument("out", type=Path)
    args = parser.parse_args(argv)
    if args.command == "freeze":
        probes.freeze(args.out)
    else:
        run(args.out)


if __name__ == "__main__":
    main()
