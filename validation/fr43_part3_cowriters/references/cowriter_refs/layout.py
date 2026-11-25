"""SPEC section 7's reference files: plain values in, bytes fixed by the values out."""

from __future__ import annotations

import json

from . import checks
from .build import context, upward

KIND = "fr43 part 3 co-writers reference, version 2"


def dump(value):
    """The bytes of a file: sorted keys, fixed separators, floats in their shortest round-trip form."""
    text = json.dumps(value, sort_keys=True, indent=1, separators=(",", ": "), ensure_ascii=True, allow_nan=False)
    return (text + "\n").encode("ascii")


def number(value):
    return None if value is None else float(value)


def copy_events(copy):
    return {
        "K": copy.judged,
        "K_all": len(copy.times),
        "time_s": [float(t) for t in copy.times],
        "channel": list(copy.channels),
        "counts_after": [list(counts) for counts in copy.counts_after],
        "accuracy_s": upward(copy.time_accuracy),
    }


def copy_series(copy):
    return {
        name: {"value": [float(v) for v in values], "accuracy": [upward(copy.accuracy[name])] * len(values)}
        for name, values in copy.series.items()
    }


def statistics(got):
    return {
        "d": [float(d) for d in got["d"]],
        "used": got["used"],
        "q": number(got["q"]),
        "E": float(got["E"]),
        "est": float(got["est"]),
        "tau": float(got["tau"]),
    }


def ratio(got):
    return {key: float(got[key]) for key in ("rms", "threshold", "ratio")}


def reported(world_set):
    """SPEC section 7's `reported`: K_all, the draws used, the pairwise orders and the coarse-rung errors."""
    out = []
    for copy in world_set.copies:
        out.append({"name": f"K_all {world_set.name} c{copy.index}", "value": len(copy.times)})
        out.append({"name": f"draws used {world_set.name} c{copy.index}", "value": len(copy.times) + 1})
    rungs = world_set.families[0]["rungs_s"]
    for family in world_set.families:
        for item in world_set.judged["S"]:
            got = world_set.sizing[family["id"]][item["readout"]]["first"]
            label = f"{family['id']} {item['readout']}"
            for j, order in enumerate(got["pairwise"]):
                if order is not None:
                    out.append({"name": f"pairwise order {label} {j + 1}", "value": float(order)})
            for rung, error in zip(rungs, got["coarse_errors"], strict=False):
                out.append({"name": f"error against the reference {label} h={rung!r}", "value": float(error)})
    return out


def reference(world_set, inputs_sha256, draws_differ, provenance):
    """One world's reference object."""
    with context():
        return _reference(world_set, inputs_sha256, draws_differ, provenance)


def _reference(world_set, inputs_sha256, draws_differ, provenance):
    name = world_set.name
    copies = []
    for c, copy in enumerate(world_set.copies):
        listed = checks.copy_checks(world_set, c, draws_differ[c])
        if c == 0:
            listed = listed + checks.world_checks(world_set)
        copies.append(
            {
                "copy": copy.index,
                "seed": copy.seed,
                "events": copy_events(copy),
                "samples_s": [float(t) for t in world_set.world.samples],
                "series": copy_series(copy),
                "checks": listed,
            }
        )
    classes = {item["readout"]: "S" for item in world_set.judged["S"]}
    if not classes:
        classes = {"t_events": "R"}
    planted = {}
    for plant in world_set.plants:
        families = [family["id"] for family in world_set.families_of(plant)]
        if plant["id"] in world_set.planted:
            listed = [
                {"copy": copy.index, "events": copy_events(copy), "series": copy_series(copy)}
                for copy in world_set.planted[plant["id"]]
            ]
            planted[plant["id"]] = {family: listed for family in families}
        elif plant["kind"] == "reference":
            planted[plant["id"]] = {
                family["id"]: {"shift_s": float(world_set.shift(family))} for family in world_set.families_of(plant)
            }
    sizing = {
        family["id"]: {
            readout: {**statistics(got["first"]), "retry": statistics(got["retry"])}
            for readout, got in world_set.sizing[family["id"]].items()
        }
        for family in world_set.families
    }
    sizing["mutant"] = {
        family: {"E": [float(e) for e in got["E"]], "q": float(got["q"])}
        for family, got in world_set.sizing["mutant"].items()
    }
    sizing["pair"] = {readout: ratio(got) for readout, got in world_set.sizing["pair"].items()}
    sizing["rungs"] = {
        family: {readout: ratio(got) for readout, got in rows.items()}
        for family, rows in world_set.sizing["rungs"].items()
    }
    plants = []
    for margin in world_set.margins:
        entry = dict(margin)
        for key in ("distance", "expected_tolerance", "margin"):
            entry[key] = number(margin[key])
        plants.append(entry)
    pairs = world_set.inputs["draws"]["pairs_per_copy"]
    return {
        "kind": KIND,
        "world": name,
        "inputs_sha256": inputs_sha256,
        "copies": copies,
        "scales": {readout: float(scale) for readout, scale in world_set.scales.items()},
        "classes": classes,
        "planted": planted,
        "sizing": sizing,
        "plants": plants,
        "draws_check": {"identical": sum(draws_differ) == 0, "entries": 2 * pairs * len(world_set.copies)},
        "reported": reported(world_set),
        "provenance": provenance,
    }
