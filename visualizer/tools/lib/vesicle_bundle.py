"""Read a saved assembly_lineages@2 vesicle bundle using its public format tables."""

import hashlib
import json
import math
import re
import struct
from zipfile import BadZipFile

from npy_reader import read_npz


class VesicleError(ValueError):
    pass


def require(value, message):
    if not value:
        raise VesicleError(message)


STANDING = "Development run of Cells' engine (cells.assembly_lineages@2), not judged."
REFERENCE = (
    "On OL5's registered inputs, the engine's outputs agree with independent references written without "
    "its code on 9 of 10 rows (D285). The tenth differs on how a lysing step's pool is recorded, a "
    "convention FORMAT_OL2 now states."
)
JUDGING = "Nothing of Cells' origin-of-life engine is judged against experiment yet."
PICTURE = (
    "The engine's geometry is lumped: area and volume come from the counts, with no shape or position. "
    "The shell, the water, how lipids pack and how a pore looks are the picture's own."
)
PORE = (
    "The rupture law (cells.pore_nucleation@1) passed its registered blind test on held-out "
    "temperatures (D298), within a wide tolerance and with its in-sample misfit stated."
)


def numbers(value):
    return type(value) in (int, float) and math.isfinite(value)


def times(values, what):
    require(
        all(numbers(t) and t >= 0 for t in values) and all(a <= b for a, b in zip(values, values[1:])),
        f"{what} must be finite, nonnegative and in recorded time order",
    )


def nested(values, shape):
    if len(shape) == 1:
        return list(values)
    stride = math.prod(shape[1:])
    return [nested(values[i * stride : (i + 1) * stride], shape[1:]) for i in range(shape[0])]


class Records:
    def __init__(self, folder, run, places):
        self.table = run["records"]
        self.path = folder / "records.npz"
        self.sizes = {"place": places}
        self.spec = {}

    def want(self, name, axes, unit):
        entry = self.table.get(name)
        require(isinstance(entry, dict), f"run.json has no {name} record, which this replay needs")
        require(
            entry.get("file") == "records.npz" and isinstance(entry.get("array"), str),
            f"{name} must name an array in records.npz",
        )
        require(
            entry.get("axes") == axes.split() and entry.get("base") == axes.split()[0],
            f"{name} must have axes [{axes}]",
        )
        if unit is not None:
            require(entry.get("unit") == unit, f"{name} must be recorded in {unit}")
        self.spec[name] = entry

    def read(self):
        require(self.path.is_file(), "the replay needs records.npz")
        arrays = read_npz(self.path, [e["array"] for e in self.spec.values()], allow_fortran=True)
        result = {}
        for name, e in self.spec.items():
            a = arrays[e["array"]]
            require(len(a.shape) == len(e["axes"]), f"{name} has the wrong number of axes")
            for axis, n in zip(e["axes"], a.shape):
                require(self.sizes.setdefault(axis, n) == n, f"{name} disagrees on the length of its {axis} axis")
            result[name] = nested(a.values, a.shape)
        return result


def read_channels(run, places):
    index = {p["name"]: i for i, p in enumerate(places)}
    channels = []
    table = run["channels"]
    for ch in table.get("lineage", table)["rows"]:
        require(
            ch.get("direction") in ("forward", "reverse") and type(ch.get("event_channel")) is int,
            "a channel is missing its recorded direction or signed code",
        )
        item = {k: ch[k] for k in ("step", "direction", "event_channel")}
        for side in ("reactants", "products"):
            require(isinstance(ch.get(side), dict), f"channel {ch['step']} has no {side}")
            terms = []
            for name, n in ch[side].items():
                require(
                    name in index and type(n) is int and n > 0, f"{ch['step']} has an unknown place or count in {side}"
                )
                terms.append([index[name], n])
            item[side] = terms
        channels.append(item)
    require(len({ch["event_channel"] for ch in channels}) == len(channels), "two channels share an event code")
    return channels


def fissions(run, a):
    result = []
    legend = run["records"].get("fission_outcome", {}).get("legend", {})
    for i, t in enumerate(a.get("fission_time", [])):
        outcome = legend.get(str(a["fission_outcome"][i]))
        require(isinstance(outcome, str), "a shear attempt has no named outcome in its legend")
        k, followed = a["fission_k"][i], a["fission_followed"][i]
        ds = a["fission_daughter_counts"][i]
        require(0 < k <= len(ds), "the shear's daughter axis does not fit its stated multiplicity")
        daughters = []
        if outcome == "split":
            require(0 <= followed < k, "the split does not identify the continuing daughter")
            for j in range(k):
                key = a["fission_daughters"][i][j]
                require(key >= 0, "a born daughter has no carrier key")
                daughters.append(
                    {"key": str(key), "counts": ds[j], "lysed_at_birth": bool(a["fission_lysed_at_birth"][i][j])}
                )
        result.append(
            {
                "time": t,
                "outcome": outcome,
                "schedule": a["fission_schedule"][i],
                "parent": str(a["fission_parent"][i]),
                "parent_counts": a["fission_parent_counts"][i],
                "daughters": daughters,
                "followed": followed if daughters else None,
                "shear_work_kT": a["fission_shear_work_kT"][i],
            }
        )
    times([r["time"] for r in result], "shear times")
    return result


def released(record, cause, pools):
    returned = record.get("returned")
    require(
        isinstance(returned, dict) and all(p in pools and type(n) is int and n >= 0 for p, n in returned.items()),
        f"the {cause} release must state its returned molecule counts by a named pool place",
    )
    return returned


def adapt(folder, standing):
    """The files' signed channel table already gives each event's direction; no rate or geometry is evaluated here."""
    try:
        return _adapt(folder, standing)
    except (KeyError, TypeError, IndexError) as error:
        raise VesicleError(f"{folder.name}: missing or malformed field {error} in the vesicle bundle") from error
    except (OSError, ValueError, BadZipFile, struct.error, SyntaxError) as error:
        raise VesicleError(f"{folder.name}: {error}") from error


def _adapt(folder, standing):
    require(
        standing.get("standing") == "development" and standing.get("from"),
        "give the development standing and its source",
    )
    run = json.loads((folder / "run.json").read_text())
    world = json.loads((folder / "world.json").read_text())
    require(
        run.get("format") == "cells.assembly_lineages.run@2" and run.get("model") == "cells.assembly_lineages@2",
        "expected an assembly_lineages@2 run",
    )
    require(
        world.get("format") == "cells.assembly_lineages.world@2" and world.get("id") == run["world"],
        "run.json and world.json must identify the same @2 world",
    )
    require(run["time"].get("unit") == "s", "the vesicle replay needs the run's clock in seconds")
    qualifier = run["run"]["qualifier"]
    require(
        isinstance(qualifier, str) and re.fullmatch(r"[0-9a-f]{64}", qualifier), "the run needs its SHA-256 qualifier"
    )
    mode = run["mode"]
    require(mode in ("single_lineage", "population"), f"unsupported vesicle mode {mode}")
    pop = mode == "population"
    require(
        not pop or ("pores" in run and "division" not in run and not run.get("population", {}).get("transfers")),
        "the population replay reads a held-tension pore population without division or transfers",
    )
    manifest = json.loads((folder / "manifest.json").read_text())
    hashes = {}
    for name in ("run.json", "world.json", "records.npz"):
        digest = hashlib.sha256((folder / name).read_bytes()).hexdigest()
        require(manifest["files_sha256"].get(name) == digest, f"{name} does not match the run manifest")
        hashes[name] = digest
    places = [{k: p[k] for k in ("index", "name", "phase", "species", "kind", "held_mM")} for p in run["places"]]
    require(
        places
        and [p["index"] for p in places] == list(range(len(places)))
        and len({p["name"] for p in places}) == len(places),
        "the places table must give unique names in index order",
    )
    for p in places:
        require(
            p["phase"] in ("membrane", "pool", "lumen") and p["kind"] in ("held", "finite"),
            f"unknown phase or kind for {p['name']}",
        )
    channels = read_channels(run, places)
    cols = Records(folder, run, len(places))
    for k, ax, u in (
        ("row_time", "row", "s"),
        ("row_kind", "row", "1"),
        ("row_event", "row", "events"),
        ("event_time", "event", "s"),
        ("event_channel", "event", "1"),
    ):
        cols.want(k, ax, u)
    geometry = "row slot" if pop else "row"
    cols.want("membrane_footprint_quanta", geometry, "quanta")
    for k, u in (("lumen_volume_L", "L"), ("tension_N_per_m", "N/m")):
        if run["conventions"]["lumen_volume"] == "osmotic" or k in cols.table:
            cols.want(k, geometry, u)
    if pop:
        for k, ax, u in (
            ("slot_count", "row slot place", "molecules"),
            ("pool_count", "row place", "molecules"),
            ("slot_key", "row slot", None),
            ("event_group", "event", None),
        ):
            cols.want(k, ax, u)
    else:
        cols.want("place_count", "row place", "molecules")
    if "division" in run:
        for k, ax, u in (
            ("time", "fission", "s"),
            ("k", "fission", "1"),
            ("schedule", "fission", "1"),
            ("parent", "fission", "carrier key"),
            ("outcome", "fission", "1"),
            ("followed", "fission", "1"),
            ("parent_counts", "fission place", "molecules"),
            ("daughters", "fission daughter", "carrier key"),
            ("daughter_counts", "fission daughter place", "molecules"),
            ("lysed_at_birth", "fission daughter", "1"),
            ("shear_work_kT", "fission", "k_BT"),
        ):
            cols.want("fission_" + k, ax, u)
    a = cols.read()
    times(a["row_time"], "row times")
    times(a["event_time"], "event times")
    end = run["end"]
    require(
        numbers(end["time"])
        and a["row_time"]
        and a["row_time"][-1] == end["time"]
        and len(a["event_time"]) == end["events"]
        and all(a["row_time"][0] <= t <= end["time"] for t in a["event_time"]),
        "rows, trace and the run's end disagree",
    )
    codes = {ch["event_channel"] for ch in channels}
    require(all(c in codes for c in a["event_channel"]), "the trace refers to a code missing from the channels table")
    shear = fissions(run, a)
    pool_names = {p["name"] for p in places if p["phase"] == "pool"}
    events = []
    lysis = (run.get("osmotic") or {}).get("lysis")
    if lysis:
        require(
            all(numbers(lysis[k]) and lysis[k] >= 0 for k in ("sigma_N_per_m", "sigma_max_N_per_m")),
            "a threshold lysis needs its triggering and limit tensions in N/m",
        )
        require(lysis.get("cause", "threshold") == "threshold", "an osmotic lysis has an unsupported cause")
        events.append(
            {
                "time": lysis["time_s"],
                "cause": "threshold",
                "slot": 0,
                "tension_N_per_m": lysis["sigma_N_per_m"],
                "threshold_N_per_m": lysis["sigma_max_N_per_m"],
                "returned": released(lysis, "threshold", pool_names),
            }
        )
    pores = run.get("pores")
    if pores is not None:
        for e in pores["events"]:
            require(
                type(e["slot"]) is int
                and e["slot"] >= 0
                and type(e["key"]) is int
                and e["key"] >= 0
                and numbers(e["area_m2"])
                and e["area_m2"] > 0,
                "a pore rupture needs its slot, carrier key and recorded area",
            )
            require(e["cause"] == "pore", "a pore record has an unexpected cause")
            events.append(
                {
                    "time": e["time_s"],
                    "cause": "pore",
                    "slot": e["slot"],
                    "key": str(e["key"]),
                    "hold": e["hold"],
                    "tension_N_per_m": e["sigma_N_per_m"],
                    "area_m2": e["area_m2"],
                    "returned": released(e["release"], "pore", pool_names),
                }
            )
    events.sort(key=lambda e: e["time"])
    times([e["time"] for e in events], "release times")
    require(not any(e["time"] > end["time"] for e in events), "a release falls beyond the recorded end")
    require(end["status"] != "lysed" or bool(events), "the run ends lysed but gives no release or cause")
    previous = {}
    rows = []
    slots = cols.sizes.get("slot", 1)
    legend = cols.table["row_kind"]["legend"]
    for i, t in enumerate(a["row_time"]):
        kind = legend.get(str(a["row_kind"][i]))
        require(
            kind and 0 <= a["row_event"][i] <= end["events"], "a saved row has no kind or has an invalid event index"
        )
        row = {"t": t, "event": a["row_event"][i], "kind": kind, "slots": []}
        if pop:
            row["pool"] = a["pool_count"][i]
            require(
                all(type(c) is int and c >= 0 for c in row["pool"]),
                "a population pool count is not a nonnegative integer",
            )
        for s in range(slots):
            key = a["slot_key"][i][s] if pop else 0
            require(type(key) is int and key >= -1, "a slot must identify its carrier or be marked vacant")
            state = None
            if key >= 0:
                counts = a["slot_count"][i][s] if pop else a["place_count"][i]
                require(
                    all(type(c) is int and c >= 0 for c in counts), "a vesicle place count is not a nonnegative integer"
                )
                state = {"key": str(key) if pop else None, "counts": counts}
                for k in ("membrane_footprint_quanta", "lumen_volume_L", "tension_N_per_m"):
                    if k in a:
                        value = a[k][i][s] if pop else a[k][i]
                        require(numbers(value) and value >= 0, f"invalid {k} at row {i}, slot {s}")
                        state[k] = value
            if i == 0 or previous.get(s) != state:
                row["slots"].append([s, state])
                previous[s] = state
        rows.append(row)
    if not pop:
        for e in events:
            require(
                any(
                    r["t"] == e["time"]
                    and any(s is not None and s["membrane_footprint_quanta"] == 0 for _, s in r["slots"])
                    for r in rows
                ),
                "the release has no recorded empty vesicle at its time",
            )
    require(rows[0]["kind"] == "start" and rows[-1]["kind"] == "end", "the saved rows need a start and an end")
    if pop:
        require(all(e["slot"] in range(slots) for e in events), "a rupture names a missing slot")
        initial = dict(rows[0]["slots"])
        occupants = {s: state["key"] for s, state in initial.items() if state is not None}
        removed = {(e["time"], e["slot"]): e["key"] for e in events}
        require(len(removed) == len(events), "duplicate rupture of the same slot at the same time")
        require(
            all(type(g) is int and 0 <= g <= slots for g in a["event_group"]),
            "the trace names an unknown population group",
        )
        for row in rows[1:]:
            for slot, state in row["slots"]:
                if state is None:
                    require(
                        row["kind"] == "pore"
                        and (row["t"], slot) in removed
                        and removed.pop((row["t"], slot)) == occupants.pop(slot, None),
                        "a disappearing slot does not match its recorded pore time and carrier key",
                    )
                else:
                    require(
                        occupants.get(slot) == state["key"], "a held population changed carriers without a pore event"
                    )
        require(not removed, "a pore event has no released slot row")
    holds = [{k: h[k] for k in ("index", "start_s", "end_s", "sigma_N_per_m")} for h in run.get("tension_hold", [])]
    if pores is not None:
        require(holds, "a pore replay needs its recorded tension hold")
        for h in holds:
            require(
                all(numbers(h[k]) for k in ("start_s", "end_s", "sigma_N_per_m"))
                and 0 <= h["start_s"] < h["end_s"]
                and h["sigma_N_per_m"] > 0,
                "a tension hold has an invalid time range or applied tension",
            )
        for e in events:
            require(
                any(
                    h["index"] == e["hold"]
                    and h["start_s"] <= e["time"] <= h["end_s"]
                    and h["sigma_N_per_m"] == e["tension_N_per_m"]
                    for h in holds
                ),
                "a pore's time or applied tension disagrees with its recorded hold",
            )
    source = run["source"]
    require(
        isinstance(source.get("revision"), str) and source["revision"] and type(source.get("dirty")) is bool,
        "the bundle has no engine source identity",
    )
    species = [{k: s[k] for k in ("id", "catalogue") if k in s} for s in world["world"]["species"]]
    return {
        "format": "cells.visualizer.assembly_run@2",
        "model": {"id": "origin-vesicles", "engine": run["model"]},
        "time": {"base": "second", "unit": "s"},
        "id": qualifier,
        "world": run["world"],
        "mode": mode,
        "source": {"revision": source["revision"], "dirty": source["dirty"], "files_sha256": hashes},
        "development": {
            "says": STANDING,
            "from": standing["from"],
            "ol5": REFERENCE,
            "judging": JUDGING,
            "picture": PICTURE,
            **({"rupture": PORE} if pores is not None else {}),
        },
        "places": places,
        "species": species,
        "channels": channels,
        "end": end,
        "rows": rows,
        "trace": {
            "time": a["event_time"],
            "channel": a["event_channel"],
            **({"group": a["event_group"]} if pop else {}),
        },
        "shears": shear,
        "releases": events,
        "holds": holds,
    }
