#!/usr/bin/env python3
"""Write a test's own made-up run folder in the engine's run format (cells.assembly_lineages.run@1,
as its FORMAT.md describes it), so that tools/adapt_assembly_run.py can be held to it where no run
of the engine is at hand. It is not a run of Cells' engine: its numbers are made up, and no page
carries it.

    python3 tests/fixtures/assembly-engine-run/make.py OUT [--form F] [--interfaces provisional|final] [--fault NAME]

Six types, a founder of four, a fission at eight, three fissions; the first daughter carries on.
--interfaces spells the family's interface IDs as the provisional set does or as the freeze will;
--fault breaks one thing the adapter must refuse (see FAULTS). Standard library only;
deterministic.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import struct
import zipfile
from pathlib import Path

TYPES = [f"t{i:03d}" for i in range(6)]
FOUNDER = [1, 0, 2, 0, 1, 0]
SIZE, FISSIONS = 8, 3
INTERFACES = {
    "provisional": {"law": "assembly_lineages.rate_factor@1", "exchange": "assembly_lineages.exchange_law@1", "operator": "assembly_lineages.operator@1"},
    "final": {"law": "cells.rate_factor_law@1", "exchange": "cells.exchange_law@1", "operator": "cells.lineage_operator@1"},
}
FAULTS = ("unknown-key", "missing-record", "tail-events", "nan-similarity", "bad-channel", "wrong-axes")


def npy(values, descr, shape):
    header = repr({"descr": descr, "fortran_order": False, "shape": tuple(shape)}).encode("latin1")
    pad = 64 - (10 + len(header) + 1) % 64
    header += b" " * pad + b"\n"
    code = {"<i8": "q", "<i4": "i", "<f8": "d", "|i1": "b"}[descr]
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + struct.pack(f"<{len(values)}{code}", *values)


def text_npy(values, width):
    header = repr({"descr": f"<U{width}", "fortran_order": False, "shape": (len(values),)}).encode("latin1")
    pad = 64 - (10 + len(header) + 1) % 64
    header += b" " * pad + b"\n"
    body = b"".join(value.ljust(width, "\x00").encode("utf-32-le") for value in values)
    return b"\x93NUMPY\x01\x00" + struct.pack("<H", len(header)) + header + body


def simulate(seed=7):
    """A made-up lineage: joins and leaves by a fixed little generator, a split in exact halves."""
    state = seed

    def uniform():
        nonlocal state
        state = (state * 6364136223846793005 + 1442695040888963407) % 2**64
        return ((state >> 11) + 0.5) / 2**53

    x, t = list(FOUNDER), 0.0
    events, times, growths, fissions = [], [], [], []
    for k in range(1, FISSIONS + 1):
        count = 0
        while sum(x) < SIZE:
            t += 0.1 + uniform()
            held = [i for i, c in enumerate(x) if c]
            if uniform() < 0.25 and len(held) > 1 and sum(x) > 1:
                i = held[int(uniform() * len(held))]
                x[i] -= 1
                events.append(-(i + 1))
            else:
                i = int(uniform() * len(TYPES))
                x[i] += 1
                events.append(i + 1)
            times.append(t)
            count += 1
        growths.append(count)
        parent = list(x)
        places = [i for i, c in enumerate(parent) for _ in range(c)]
        order = sorted(range(len(places)), key=lambda p: (uniform(), p))
        first = [0] * len(TYPES)
        for p in order[: len(places) // 2]:
            first[places[p]] += 1
        fissions.append({"t": t, "parent": parent, "first": first})
        x = list(first)
    growths.append(0)
    return events, times, growths, fissions


def cosine(a, b):
    dot = sum(p * q for p, q in zip(a, b))
    na, nb = math.sqrt(sum(p * p for p in a)), math.sqrt(sum(q * q for q in b))
    return dot / (na * nb) if na and nb else float("nan")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("out")
    parser.add_argument("--form", default="pair-consistent", choices=("pair-consistent", "single-event"))
    parser.add_argument("--interfaces", default="provisional", choices=sorted(INTERFACES))
    parser.add_argument("--fault", choices=FAULTS)
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    names = INTERFACES[args.interfaces]
    n = len(TYPES)
    events, times, growths, fissions = simulate()
    if args.fault == "tail-events":
        events.append(1)
        times.append(times[-1] + 1)
        growths[-1] = 1
    # Rows: the start, a parent and a daughter at each fission, and the end.
    rows = [("start", 0, 0.0, FOUNDER, 0)]
    joined, left, discarded = [0] * n, [0] * n, [0] * n
    at = 0
    for k, (fission, length) in enumerate(zip(fissions, growths), start=1):
        for value in events[at : at + length]:
            (joined if value > 0 else left)[abs(value) - 1] += 1
        at += length
        rows.append(("parent", k, fission["t"], fission["parent"], at, list(joined), list(left), list(discarded)))
        second = [p - f for p, f in zip(fission["parent"], fission["first"])]
        discarded = [d + s for d, s in zip(discarded, second)]
        rows.append(("daughter", k, fission["t"], fission["first"], at, list(joined), list(left), list(discarded)))
    rows.append(("end", 0, fissions[-1]["t"], fissions[-1]["first"], at, list(joined), list(left), list(discarded)))
    rows[0] = ("start", 0, 0.0, FOUNDER, 0, [0] * n, [0] * n, [0] * n)
    legend = {"0": "start", "1": "parent", "2": "daughter", "3": "end"}
    code = {words: int(key) for key, words in legend.items()}
    flat = lambda lists: [v for one in lists for v in one]  # noqa: E731
    channel = {}
    for i in range(n):
        channel[i + 1] = i + 1
        channel[-(i + 1)] = -(i + 1)
    trace = list(events)
    if args.fault == "bad-channel":
        trace[0] = 99
    similarity = flat([[cosine(f["parent"], f["first"]), cosine(f["parent"], [p - q for p, q in zip(f["parent"], f["first"])])] for f in fissions])
    if args.fault == "nan-similarity":
        similarity[0] = float("nan")
    arrays = {
        "assembly_count": (flat(r[3] for r in rows), "<i8", (len(rows), n, 1)),
        "joined_total": (flat(r[5] for r in rows), "<i8", (len(rows), n, 1)),
        "left_total": (flat(r[6] for r in rows), "<i8", (len(rows), n, 1)),
        "discarded_total": (flat(r[7] for r in rows), "<i8", (len(rows), n, 1)),
        "row_kind": ([code[r[0]] for r in rows], "|i1", (len(rows),)),
        "row_fission": ([r[1] for r in rows], "<i8", (len(rows),)),
        "row_time": ([r[2] for r in rows], "<f8", (len(rows),)),
        "row_event": ([r[4] for r in rows], "<i8", (len(rows),)),
        "occupant": ([0] + flat([[2 * k - 2 if k > 1 else 0, 2 * k - 1] for k in range(1, FISSIONS + 1)]) + [2 * FISSIONS - 1], "<i8", (len(rows), 1)),
        "event_channel": (trace, "<i4", (len(trace),)),
        "event_time": (times, "<f8", (len(times),)),
        "events_per_growth": (growths, "<i8", (len(growths),)),
        "growth_carrier": ([0] + [2 * k - 1 for k in range(1, FISSIONS + 1)], "<i8", (FISSIONS + 1,)),
        "fission_time": ([f["t"] for f in fissions], "<f8", (FISSIONS,)),
        "fission_parent": ([0] + [2 * k - 1 for k in range(1, FISSIONS)], "<i8", (FISSIONS,)),
        "fission_daughters": (flat([[2 * k - 1, 2 * k] for k in range(1, FISSIONS + 1)]), "<i8", (FISSIONS, 2)),
        "fission_split": (flat(f["first"] for f in fissions), "<i8", (FISSIONS, n)),
        "fission_followed": ([0] * FISSIONS, "<i8", (FISSIONS,)),
        "fission_similarity": (similarity, "<f8", (FISSIONS, 2)),
    }
    axes = {
        "assembly_count": ["row", "type", "assembly"], "joined_total": ["row", "type", "assembly"], "left_total": ["row", "type", "assembly"],
        "discarded_total": ["row", "type", "assembly"], "row_kind": ["row"], "row_fission": ["row"], "row_time": ["row"], "row_event": ["row"],
        "occupant": ["row", "assembly"], "event_channel": ["event"], "event_time": ["event"], "events_per_growth": ["growth"],
        "growth_carrier": ["growth"], "fission_time": ["fission"], "fission_parent": ["fission"], "fission_daughters": ["fission", "daughter"],
        "fission_split": ["fission", "type"], "fission_followed": ["fission"], "fission_similarity": ["fission", "daughter"],
    }
    units = {"assembly_count": "molecules", "joined_total": "molecules", "left_total": "molecules", "discarded_total": "molecules", "fission_split": "molecules"}
    records = {}
    for name, (_, _, shape) in arrays.items():
        base = axes[name][0]
        records[name] = {"array": name, "axes": axes[name], "base": base, "file": "records.npz", "layer": "assemblies", "owner": "a test", "unit": units.get(name, "1")}
    records["row_kind"]["legend"] = legend
    if args.fault == "wrong-axes":
        records["fission_split"]["axes"] = ["type", "fission"]
    if args.fault == "missing-record":
        del records["event_time"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, (values, descr, shape) in arrays.items():
            archive.writestr(f"{name}.npy", npy(values, descr, shape))
        archive.writestr("life_birth_kind.npy", text_npy(["founder"] + ["division"] * (2 * FISSIONS), 12))
    (out / "records.npz").write_bytes(buffer.getvalue())
    world = {
        "format": "cells.assembly_lineages.world@1",
        "world": {
            "types": {"prefix": "t", "count": n, "transfer_constant": 100.0},
            "supply": 0.01,
            "exchange": {"law": "a test's exchange", "leave_rate": 0.001},
            "law_data": {"catalysis_matrix": [[round(math.exp(-4 + 0.7 * ((3 * i + 5 * j) % 7)), 6) for j in range(n)] for i in range(n)]},
            "founder": FOUNDER,
            "fission": {"operator": "a test's fission", "size": SIZE, "partition": {"rule": "exact_fraction", "fraction": 0.5}},
            "continuation": {"operator": "a test's continuation", "daughter": "first", "empty": "extinct", "sink": "discard"},
            "units": {"time": "nominal", "temperature_K": None},
        },
        "derived": {"types": TYPES, "join_rate": [0.1] * n, "leave_rate": [0.001] * n, "founder_size": sum(FOUNDER)},
    }
    world["id"] = hashlib.sha256(json.dumps(world["world"], sort_keys=True).encode()).hexdigest()
    (out / "world.json").write_text(json.dumps(world, indent=1), encoding="utf-8")
    passive = args.form == "pair-consistent"
    run = {
        "format": "cells.assembly_lineages.run@1",
        "world": world["id"],
        "founder": "world",
        "mode": "single_lineage",
        "model": "a test's model",
        "engine_models": {"model": "test.assembly@1", "laws": ["test.exchange@1", f"test.{args.form}@1"], "operators": ["test.fission@1", "test.continuation@1"]},
        "definition_sha256": hashlib.sha256(args.form.encode()).hexdigest(),
        "run": {"qualifier": hashlib.sha256(f"{args.form} made up".encode()).hexdigest(), "start": "fresh"},
        "keys": {"spelling": "s:c, with key = s * 2**32 + c", "founder": "0:0"},
        "law": {
            "id": f"test.{args.form}@1",
            "form": args.form,
            "law_set": "gard",
            "interface": names["law"],
            "energy_role": "passive" if passive else "driven",
            "formulas": {"g_join_i(n)": "a test's join factor", "g_leave_i(n)": "a test's leave factor", "state": "not read"},
            "check": {"admitted_as": "passive" if passive else "driven", "local_detailed_balance": "holds" if passive else "fails", "probe": {"max_abs_deviation_ln": 1.25e-15 if passive else 1.5, "tolerance_ln": 1e-09}},
            "world_report": None if passive else {"max_abs_deviation_ln": 2.5, "states": 20},
            "exchange": {"id": "test.exchange@1", "interface": names["exchange"], "provenance": {"kind": "cited", "licence": "CC BY 4.0", "source": "a test's source", "place": "the exchange"}},
            "provenance": {"kind": "cited", "licence": "CC BY 4.0 (a test's)", "source": "a test's source", "place": "the law"},
        },
        "ledger": {"unit": "k_BT", "closure": {"checked": passive, "holds": passive, "law_energy_role": "passive" if passive else "driven", "max_abs_residual_kT": 3e-12 if passive else 12.5, "reads": "a test's words", "refused": None, "tolerance_rtol": 1e-10}},
        "operators": {
            "fission": {"id": "test.fission@1", "interface": names["operator"], "provenance": {"kind": "cited", "licence": "CC BY 4.0", "source": "a test's source", "place": "an exact half"}},
            "continuation": {"id": "test.continuation@1", "interface": names["operator"]},
        },
        "ssa": {"method": "a test's own little generator, one molecule per event"},
        "source": {"revision": "0" * 40, "dirty": False},
        "end": {"status": "complete", "fissions": FISSIONS, "events": len(events), "time": fissions[-1]["t"]},
        "time": {"unit": "nominal", "rates": "per nominal time unit"},
        "channels": {"rows": [{"event_channel": channel[v], "kind": "join" if v > 0 else "leave", "type": TYPES[abs(v) - 1], "type_index": abs(v) - 1} for v in [*range(1, n + 1), *range(-1, -n - 1, -1)]]},
        "records": records,
    }
    if args.fault == "unknown-key":
        run["judgement"] = {"judged": True}
    (out / "run.json").write_text(json.dumps(run, indent=1), encoding="utf-8")
    files = {name: hashlib.sha256((out / name).read_bytes()).hexdigest() for name in ("run.json", "world.json", "records.npz")}
    (out / "manifest.json").write_text(json.dumps({"files_sha256": files}, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
