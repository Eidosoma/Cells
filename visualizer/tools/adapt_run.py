#!/usr/bin/env python3
"""Turn saved Cells runs into replay files for the viewer.

The engine does not write a run view yet (D154 is in design), so this adapter builds one
from a run's saved files and marks it derived. It follows schema/RUN_VIEW.md, section
"Packaged for the viewer": one JSON per run, holding the view and its arrays as one
base64 payload, and a catalogue of the runs adapted.

    python3 tools/adapt_run.py --experiment e07-v1 --root PATH/e07-v1-judged-20261113-01
    python3 tools/adapt_run.py --experiment e07-v1 --root PATH --run ARM/seed1 --run ARM/seed2

With no --run it adapts the runs that data/runs/selection.json lists for the experiment.
Output goes to out/runs/ and is never committed.

What it keeps to:
  * It reads saved files only. Nothing is imported or run: records are parsed as a zip of
    .npy files, and constants in the evidence folder's source snapshot are read as text.
  * It judges nothing. The class is the experiment's own summary's, and readouts are
    copied with the run's own words on which are supplementary.
  * Every piece the run did not save is listed under "derivation".
  * No machine path and no host name is written; the same input gives the same bytes.

Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import base64
import json
import math
import re
import sys
from array import array
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.hex_layout import LayoutError, embed, hexagons  # noqa: E402
from lib.npy_reader import read_npz  # noqa: E402

REPLAY_FORMAT = "cells.visualizer.replay@1"
VIEW_FORMAT = "cells.run_view@1"
INDEX_FORMAT = "cells.visualizer.replay_index@1"
LIMIT_BYTES = 1_000_000  # one run file stays under 1 MB
PATHS = re.compile(r"/(?:home|mnt|Users|tmp|var|root|opt|srv)/|[A-Za-z]:\\\\")
RUN_NAME = re.compile(r"[A-Za-z0-9._-]+/seed(\d+)\Z")


class Refused(SystemExit):
    """The adapter stops and says why, when a run does not fit what it knows."""

    def __init__(self, message):
        super().__init__(f"adapt_run: {message}")


def read_json(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise Refused(f"{Path(path).name} is missing in {Path(path).parent.name}/") from None


def lookup(data, dotted):
    """(found, value) for a dotted name such as formation.lag_s."""
    for part in dotted.split("."):
        if not isinstance(data, dict) or part not in data:
            return False, None
        data = data[part]
    return True, data


def plain_number(value):
    return value if value is None or isinstance(value, (bool, int, str)) else float(value)


# ---------------------------------------------------------------- constants read as text


class SourceReader:
    """Reads constants out of Python sources with ``ast``. Nothing is imported or run.

    It follows a name through module-level assignments and imports inside one source
    tree, and evaluates literals, tuples, lists, dicts, ``dict(key=...)``, subscripts and
    a minus sign. Anything else is unresolved.
    """

    class Unresolved(Exception):
        pass

    def __init__(self, root):
        self.root = Path(root)
        self.trees = {}

    def path(self, dotted):
        return self.root.joinpath(*dotted.split(".")).with_suffix(".py")

    def tree(self, dotted):
        if dotted not in self.trees:
            path = self.path(dotted)
            try:
                self.trees[dotted] = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                raise self.Unresolved(f"cannot read {dotted}") from None
        return self.trees[dotted]

    def scope(self, dotted):
        """(aliases, assignments) at the module's top level."""
        aliases, assignments = {}, {}
        for node in self.tree(dotted).body:
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                for alias in node.names:
                    module = f"{node.module}.{alias.name}"
                    target = ("module", module) if self.path(module).is_file() else ("name", node.module, alias.name)
                    aliases[alias.asname or alias.name] = target
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        aliases[alias.asname] = ("module", alias.name)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        assignments[target.id] = node.value
        return aliases, assignments

    def constant(self, dotted, name, depth=0):
        if depth > 20:
            raise self.Unresolved(f"{name}: too many steps")
        aliases, assignments = self.scope(dotted)
        if name in assignments:
            return self.evaluate(assignments[name], dotted, depth + 1)
        if name in aliases and aliases[name][0] == "name":
            return self.constant(aliases[name][1], aliases[name][2], depth + 1)
        raise self.Unresolved(f"{dotted} does not assign {name}")

    def evaluate(self, node, dotted, depth):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, (ast.Tuple, ast.List)):
            return [self.evaluate(item, dotted, depth) for item in node.elts]
        if isinstance(node, ast.Dict) and all(key is not None for key in node.keys):
            return {self.evaluate(key, dotted, depth): self.evaluate(value, dotted, depth) for key, value in zip(node.keys, node.values)}
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.USub, ast.UAdd)):
            value = self.evaluate(node.operand, dotted, depth)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return -value if isinstance(node.op, ast.USub) else value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dict" and not node.args:
            if all(keyword.arg for keyword in node.keywords):
                return {keyword.arg: self.evaluate(keyword.value, dotted, depth) for keyword in node.keywords}
        if isinstance(node, ast.Subscript):
            container, key = self.evaluate(node.value, dotted, depth), self.evaluate(node.slice, dotted, depth)
            try:
                return container[key]
            except (KeyError, IndexError, TypeError):
                raise self.Unresolved("a subscript that does not exist") from None
        if isinstance(node, ast.Name):
            return self.constant(dotted, node.id, depth + 1)
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name):
            aliases, _ = self.scope(dotted)
            target = aliases.get(node.value.id)
            if target and target[0] == "module":
                return self.constant(target[1], node.attr, depth + 1)
        raise self.Unresolved(f"an expression this reader does not follow in {dotted}")

    def imported_from(self, dotted, name):
        """The module a file imports ``name`` from, wherever in the file the import stands."""
        for node in ast.walk(self.tree(dotted)):
            if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                if any(alias.name == name and alias.asname in (None, name) for alias in node.names):
                    return node.module
        raise self.Unresolved(f"{dotted} does not import {name}")


# ---------------------------------------------------------------- the payload


class Payload:
    """The arrays of one run, end to end, each starting on a multiple of four bytes."""

    def __init__(self):
        self.parts, self.length = [], 0

    def add(self, data):
        offset = self.length
        self.parts.append(data)
        self.length += len(data)
        padding = -self.length % 4
        if padding:
            self.parts.append(b"\0" * padding)
            self.length += padding
        return offset

    def data(self):
        return b"".join(self.parts)


def little_endian(values):
    if sys.byteorder == "big" and values.itemsize > 1:
        values = array(values.typecode, values)
        values.byteswap()
    return values.tobytes()


def value_range(values):
    finite = [value for value in values if isinstance(value, int) or math.isfinite(value)]
    return [plain_number(min(finite)), plain_number(max(finite))] if finite else None


def describe(payload, identifier, label, unit, axes, dtype, shape, stored, *, value_scale=None, **extra):
    """Add an array to the payload and return its entry for view.records."""
    low_high = value_range(stored)
    if value_scale is not None and low_high:
        low_high = [low_high[0] * value_scale, low_high[1] * value_scale]
    entry = {"id": identifier, "label": label, "unit": unit}
    entry.update({key: extra.pop(key) for key in ("set", "layer") if extra.get(key)})
    entry.update({"axes": axes, "dtype": dtype, "offset": payload.add(little_endian(stored)), "shape": list(shape), "range": low_high})
    if value_scale is not None:
        entry.update({"scale": value_scale, "quantised": True})
    entry.update({key: value for key, value in extra.items() if value not in (None, [], "")})
    return entry


# ---------------------------------------------------------------- E07-v1


def sphere_diameter_um(volume_pL):
    """The diameter of a sphere of this volume (1 pL is 1000 cubic micrometres)."""
    return (6.0 * volume_pL * 1000.0 / math.pi) ** (1.0 / 3.0)


def e07_marks(root, derivation):
    """The voltage above which the experiment counts a cell as D, and the record grid.

    Neither is in a run's own files. Both are constants of the driver, read as text from
    the evidence folder's source snapshot; if they cannot be read, they are left out.
    """
    reader = SourceReader(root / "snapshot")
    driver = "validation.tissue.e07_v1_run"
    threshold = grid = None
    try:
        module = reader.imported_from(driver, "THRESHOLD_V")
        if "> THRESHOLD_V" not in reader.path(driver).read_text(encoding="utf-8"):
            raise reader.Unresolved("the driver does not compare a voltage with THRESHOLD_V")
        value = reader.constant(module, "THRESHOLD_V")
        if not isinstance(value, float):
            raise reader.Unresolved("THRESHOLD_V is not a number")
        threshold = value
        derivation.append(
            "The D mark on membrane voltage is not in the run's files. It is THRESHOLD_V, read as text from the evidence "
            f"folder's source snapshot ({module.replace('.', '/')}.py), which the driver's analysis compares each cell's voltage with: "
            "above it a cell counts as D."
        )
    except (reader.Unresolved, OSError) as error:
        derivation.append(f"No D mark is given: the threshold could not be read from the evidence folder's source snapshot ({error}).")
    try:
        value = reader.constant("validation.tissue.e07_v1_turnover", "RECORD_S")
        grid = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
    except reader.Unresolved:
        pass
    return threshold, grid


def e07_revision(root, derivation):
    """The engine revision, if the evidence folder's source snapshot states it."""
    manifest = root / "snapshot" / "SNAPSHOT.json"
    if not manifest.is_file():
        return None
    data = read_json(manifest)
    revision = data.get("git_revision")
    if not (isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{7,40}", revision)):
        return None
    derivation.append("The engine revision is the one the evidence folder's source snapshot records (snapshot/SNAPSHOT.json); the run's own result.json states none.")
    return revision[:7]


def adapt_e07_v1(root, name, experiment, entry):
    """One E07-v1 run folder (runs/<arm>/seedN) as (view, payload bytes, notes for the terminal)."""
    match = RUN_NAME.match(name)
    if not match:
        raise Refused(f"'{name}' is not ARM/seedN")
    folder = root / "runs" / name
    if not folder.is_dir():
        raise Refused(f"no run folder runs/{name} in {root.name}/")
    arm, seed = name.split("/")[0], int(match.group(1))
    plan, outcome, result, definition = (read_json(folder / f"{part}.json") for part in ("plan", "outcome", "result", "definition"))
    summary = read_json(root / "summary.json")
    for label, data in (("plan.json", plan), ("outcome.json", outcome), ("result.json", result)):
        if data.get("arm") != arm or data.get("seed") != seed:
            raise Refused(f"runs/{name}/{label} is for {data.get('arm')} seed {data.get('seed')}")
    recorded = (summary.get("runs") or {}).get(name)
    if recorded is None or "run_class" not in recorded:
        raise Refused(f"summary.json records no class for {name}")
    if "run_class" in outcome and outcome["run_class"] != recorded["run_class"]:
        raise Refused(f"{name}: summary.json says {recorded['run_class']!r}, outcome.json says {outcome['run_class']!r}")
    derivation = []

    # ---- who is who, and where
    model = definition["model"]
    cells = [cell["id"] for cell in model["cells"]]
    junctions = [junction["id"] for junction in model["junctions"]]
    cell_index = {identifier: index for index, identifier in enumerate(cells)}
    try:
        ends = [[cell_index[junction["sender"]], cell_index[junction["receiver"]]] for junction in model["junctions"]]
    except KeyError as error:
        raise Refused(f"{name}: a junction names the unknown cell {error}") from None
    try:
        lattice = embed(len(cells), ends)
    except LayoutError as error:
        raise Refused(f"{name}: {error}") from None
    volumes = [cell["volume_pL"] for cell in model["cells"]]
    volume = sum(volumes) / len(volumes)
    pitch = sphere_diameter_um(volume)
    vertices, faces, _ = hexagons(lattice, pitch)
    derivation.append(
        "Cell positions: the run saves no coordinates. They are an exact hexagonal lattice laid out from the saved junctions "
        "(which two cells each joins). Where the sheet sits, which way it is turned and its handedness are arbitrary."
    )
    derivation.append(
        f"Cell size: the distance between neighbouring cells is the diameter of a sphere of the declared cell volume ({volume:.4g} pL gives "
        f"{pitch:.2f} um{'' if max(volumes) == min(volumes) else ', from the mean volume'}). The run declares volumes and areas, not shapes; each cell is drawn as a regular hexagon."
    )

    # ---- records
    saved = read_npz(folder / "records.npz", ["t", "vm", "generation", "abundance", "regular", "valid"])
    count = saved["t"].shape[0]
    expected = {"t": (count,), "vm": (count, len(cells)), "generation": (count, len(cells)), "abundance": (count, len(junctions)), "regular": (count,), "valid": (count,)}
    for key, shape in expected.items():
        if saved[key].shape != shape:
            raise Refused(f"{name}: records.npz {key} has shape {saved[key].shape}, expected {shape}")
    if result.get("records") not in (None, count):
        raise Refused(f"{name}: result.json counts {result['records']} records, records.npz holds {count}")
    times = saved["t"].values
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise Refused(f"{name}: the record times do not increase")
    threshold, grid = e07_marks(root, derivation)
    labels = entry.get("records", {})
    label_of = lambda identifier, fallback: labels.get(identifier, {}).get("label", fallback)  # noqa: E731
    payload, records = Payload(), []
    records.append(describe(payload, "t", "Time", "s", ["time"], "float32", (count,), array("f", times)))
    marks = [{"value": threshold, "label": "D above this voltage, H below"}] if threshold is not None else None
    records.append(
        describe(payload, "vm", label_of("vm", "Membrane voltage"), "V", ["time", "cell"], "float32", saved["vm"].shape, array("f", saved["vm"].values), set="cell", layer="membrane", marks=marks)
    )
    generation = saved["generation"].values
    if min(generation) < 0:
        raise Refused(f"{name}: a negative generation")
    code, dtype = ("B", "uint8") if max(generation) < 256 else ("H", "uint16") if max(generation) < 65536 else ("i", "int32")
    records.append(
        describe(payload, "generation", label_of("generation", "Generation"), "1", ["time", "cell"], dtype, saved["generation"].shape, array(code, generation), set="cell", layer="replacement")
    )
    abundance = saved["abundance"].values
    label = label_of("junction_abundance", "Junction abundance")
    if all(math.isfinite(value) and -1e-9 <= value <= 1 + 1e-9 for value in abundance):
        stored = array("B", (min(255, max(0, round(value * 255))) for value in abundance))
        records.append(
            describe(payload, "junction_abundance", label, "1", ["time", "junction"], "uint8", saved["abundance"].shape, stored, value_scale=1 / 255, set="junction", layer="replacement")
        )
        derivation.append("Junction abundance is stored in 256 steps, for drawing only (value = stored x 1/255); the run saved it as 64-bit numbers.")
    else:
        records.append(
            describe(payload, "junction_abundance", label, "1", ["time", "junction"], "float32", saved["abundance"].shape, array("f", abundance), set="junction", layer="replacement")
        )
    every = f"{grid:g} s" if grid else "regular"
    records.append(
        describe(
            payload, "regular", "On the record grid", "1", ["time"], "uint8", (count,), array("B", saved["regular"].values),
            note=f"1 for a record on the run's {every} record grid; 0 for a record taken at a replacement event's own time, which the run saves as well. "
            "A record at an event's time holds the state just before that event. The experiment's readings use the grid records only.",
        )
    )  # fmt: skip
    records.append(
        describe(
            payload, "valid", "Field solve converged", "1", ["time"], "uint8", (count,), array("B", saved["valid"].values),
            note="1 where the field solve behind this record's membrane voltages converged: the model's own flag, saved with each record. A record that is 0 is never shown as data.",
        )
    )  # fmt: skip
    derivation.append("Record names, units and axes: records.npz states none. They are read from the driver that wrote it: times in s, membrane voltage in V with one column per cell, abundance with one column per junction, in the definition's order.")
    derivation.append("Times and membrane voltages are stored as 32-bit numbers; the run saved 64-bit.")

    # ---- events
    last = times[-1]
    events, dropped = [], 0
    scheduled = definition["experiment"].get("replacement_events") or []
    for order, event in enumerate(scheduled):
        if event["slot"] not in cell_index or (event.get("donor") is not None and event["donor"] not in cell_index):
            raise Refused(f"{name}: replacement event {order} names an unknown cell")
        if order < len(plan.get("events") or []):
            step, slot, donor = plan["events"][order][:3]
            same = slot == cell_index[event["slot"]] and (donor is None) == (event.get("donor") is None) and (donor is None or donor == cell_index[event["donor"]])
            if not same or abs(step * plan["dt"] - event["time"]) > 1e-6:
                raise Refused(f"{name}: replacement event {order} differs between plan.json and definition.json")
        if event["time"] > last + 1e-9:
            dropped += 1  # the run stopped before this event
            continue
        item = {"time": event["time"], "kind": "replacement", "layer": "replacement", "at": {"set": "cell", "index": cell_index[event["slot"]]}}
        if event.get("donor") is not None:
            item["from"] = {"set": "cell", "index": cell_index[event["donor"]]}
        item["label"] = event.get("carrier_id") or f"event {order}"
        events.append(item)
    if dropped:
        derivation.append(f"{dropped} scheduled replacements after the run's last record ({last:g} s) are left out: the run stopped before them.")

    # ---- regions
    regions = []
    if plan.get("scope") == "disc" and len(plan.get("permutation") or []) == plan.get("size"):
        indices = sorted(int(index) for index in plan["permutation"])
        if indices and (indices[0] < 0 or indices[-1] >= len(cells) or len(set(indices)) != len(indices)):
            raise Refused(f"{name}: the plan's disc names cells the sheet does not have")
        regions.append({"id": "disc", "label": entry.get("regions", {}).get("disc", {}).get("label", "The disc"), "set": "cell", "indices": indices})
        derivation.append("The disc is the plan's replacement order (permutation): in this arm only the disc's cells are replaced (scope 'disc'), so the plan lists exactly them.")

    # ---- the run's own words
    supplementary = summary.get("supplementary_readouts") or {}
    readouts = []
    for identifier in entry.get("readouts", {}):
        found, value = lookup(outcome, identifier)
        if not found or isinstance(value, (dict, list)):
            continue
        head = identifier.split(".")[0]
        parent = outcome.get(head) if "." in identifier else None
        status = parent.get("status") if isinstance(parent, dict) and isinstance(parent.get("status"), str) else supplementary.get(head)
        flagged = isinstance(status, str) and "supplementary" in status.lower()
        readouts.append({"id": identifier, "value": plain_number(value), "supplementary": bool(flagged), "status": status if flagged else None})
    parameters = []
    for identifier in entry.get("parameters", {}):
        found, value = lookup(plan, identifier)
        if found and not isinstance(value, (dict, list)):
            parameters.append({"id": identifier, "value": plain_number(value)})
    derivation.append("The class is the one summary.json records for this run. Parameters are copied from plan.json and readouts from outcome.json, under their own names.")
    stated = entry.get("layers", {})
    if any(layer.get("representation") for layer in stated.values()):
        derivation.append("How each layer is represented (simulated, modelled or prescribed) is not stated by the run's files; it is the catalogue's curated entry.")
    else:
        derivation.append("How each layer is represented (simulated, modelled or prescribed) is not stated by the run's files, and is left unset.")
    revision = e07_revision(root, derivation)

    identifier = run_id(experiment, arm, seed)
    view = {
        "format": VIEW_FORMAT,
        "derived": True,
        "derivation": derivation,
        "run": {
            "id": identifier,
            "experiment": experiment,
            "arm": arm,
            "seed": seed,
            "label": plan.get("label"),
            "group": plan.get("group"),
            "engine_models": list(result.get("engine_models") or []),
            "revision": revision,
            "end_s": plain_number(result.get("end_s")),
            "stop": result.get("stop"),
            "class": recorded["run_class"],
            "judged_s": plain_number(outcome.get("judged_s")),
            "parameters": parameters,
            "readouts": readouts,
        },
        "time": {"unit": "s", "record": "t"},
        "space": {"unit": "um", "dimensions": 2},
        "layers": [
            {"id": layer, "label": stated.get(layer, {}).get("label", fallback), "representation": stated.get(layer, {}).get("representation")}
            for layer, fallback in (("membrane", "Membrane voltage"), ("replacement", "Cell replacement and junction formation"))
        ],
        "sets": [
            {"id": "cell", "scale": "cell", "ids": cells, "geometry": {"kind": "polygons", "vertices": vertices, "faces": faces}},
            {"id": "junction", "scale": "cell", "ids": junctions, "geometry": {"kind": "links", "between": "cell", "ends": ends}},
        ],
        "records": records,
        "regions": regions,
        "events": events,
    }
    if not regions:
        del view["regions"]

    # ---- for the terminal only: nothing here is written to the view
    notes = {"records": count, "on_grid": sum(saved["regular"].values), "valid": sum(saved["valid"].values), "cells": len(cells), "junctions": len(junctions), "events": len(events), "dropped": dropped, "pitch_um": pitch, "revision": revision}
    if threshold is not None:
        voltages, width = saved["vm"].values, len(cells)
        notes["above_mark_first"] = sum(value > threshold for value in voltages[:width])
        notes["above_mark_last"] = sum(value > threshold for value in voltages[-width:])
        if regions:
            notes["first_equals_disc"] = [index for index in range(width) if voltages[index] > threshold] == regions[0]["indices"]
    return view, payload.data(), notes


ADAPTERS = {"e07-v1": adapt_e07_v1}


# ---------------------------------------------------------------- writing


def run_id(experiment, arm, seed):
    text = re.sub(r"[^a-z0-9.-]+", "-", f"{experiment}--{arm}--seed{seed}".lower())
    if not re.fullmatch(r"[a-z0-9.-]+", text):
        raise Refused(f"cannot make a run id from {experiment}, {arm}, seed {seed}")
    return text


def serialise(data):
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def check_clean(name, text):
    found = PATHS.search(text)
    if found:
        raise Refused(f"{name} would carry a machine path ({found.group(0)}...)")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--experiment", required=True, help="the experiment's id in the overlay, for example e07-v1")
    parser.add_argument("--root", required=True, help="the experiment's evidence folder (read only)")
    parser.add_argument("--run", action="append", default=[], help="ARM/seedN; may be given several times (default: the selection's runs)")
    parser.add_argument("--selection", default=str(HERE.parent / "data" / "runs" / "selection.json"))
    parser.add_argument("--overlay", default=str(HERE.parent / "data" / "runs" / "overlay.json"))
    parser.add_argument("--out", default=str(HERE.parent / "out" / "runs"))
    arguments = parser.parse_args(argv)

    root = Path(arguments.root).resolve()
    if not root.is_dir():
        raise Refused("the evidence folder given with --root does not exist")
    overlay = read_json(arguments.overlay)
    entry = (overlay.get("experiments") or {}).get(arguments.experiment)
    if entry is None:
        raise Refused(f"the overlay has no experiment called {arguments.experiment}")
    adapter = ADAPTERS.get(entry.get("adapter", arguments.experiment))
    if adapter is None:
        raise Refused(f"no adapter for {entry.get('adapter', arguments.experiment)} (known: {', '.join(sorted(ADAPTERS))})")
    names = list(arguments.run)
    if not names:
        chosen = read_json(arguments.selection).get(arguments.experiment) or {}
        names = list(chosen.get("runs") or [])
        if chosen.get("evidence_folder") and chosen["evidence_folder"] != root.name:
            print(f"note: the selection names the evidence folder {chosen['evidence_folder']}; reading {root.name}", file=sys.stderr)
    if not names:
        raise Refused("no runs to adapt: give --run, or list runs in the selection")
    if len(set(names)) != len(names):
        raise Refused("a run is named twice")

    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    listed = []
    for name in names:
        view, data, notes = adapter(root, name, arguments.experiment, entry)
        replay = {"format": REPLAY_FORMAT, "view": view, "payload": {"encoding": "base64", "byte_length": len(data), "data": base64.b64encode(data).decode("ascii")}}
        check_clean(name, json.dumps(view, ensure_ascii=False))
        content = serialise(replay)
        if len(content) >= LIMIT_BYTES:
            raise Refused(f"{name} would be {len(content):,} bytes; a run file stays under {LIMIT_BYTES:,}")
        run = view["run"]
        (out / f"{run['id']}.json").write_bytes(content)
        listed.append(
            {
                "id": run["id"], "experiment": run["experiment"], "arm": run["arm"], "seed": run["seed"], "label": run["label"],
                "group": run["group"], "class": run["class"], "stop": run["stop"], "records": notes["records"], "end_s": run["end_s"],
                "file": f"runs/{run['id']}.json", "bytes": len(content),
            }
        )  # fmt: skip
        print(f"{run['id']}: {len(content):,} bytes; {notes['records']} records ({notes['on_grid']} on the grid, {notes['valid']} valid); "
              f"{notes['cells']} cells placed, {notes['junctions']} junctions checked, {notes['events']} events; class {run['class']!r}; revision {notes['revision']}")  # fmt: skip
        if "above_mark_first" in notes:
            disc = "" if "first_equals_disc" not in notes else f" ({'exactly the disc' if notes['first_equals_disc'] else 'NOT the disc'})"
            print(f"  cells above the D mark: {notes['above_mark_first']} at the first record{disc}, {notes['above_mark_last']} at the last")
    catalogue = {key: value for key, value in entry.items() if key != "adapter"}
    index = {"format": INDEX_FORMAT, "experiments": [{"id": arguments.experiment, **catalogue}], "runs": listed}
    check_clean("index.json", json.dumps(index, ensure_ascii=False))
    (out / "index.json").write_bytes((json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    kept = {f"{run['id']}.json" for run in listed} | {"index.json"}
    stale = sorted(path.name for path in out.glob("*.json") if path.name not in kept)
    if stale:
        print(f"note: {len(stale)} other file(s) in the output folder are not in this catalogue and were left in place: {', '.join(stale[:4])}", file=sys.stderr)
    print(f"wrote {len(listed)} run(s) and index.json to {out.name}/")


if __name__ == "__main__":
    main()
