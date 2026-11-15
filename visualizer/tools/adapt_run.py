#!/usr/bin/env python3
"""Turn saved Cells runs into replay files for the viewer.

The engine does not write a run view yet (D154 is in design), so this adapter builds one
from a run's saved files and marks it derived. It follows schema/RUN_VIEW.md, section
"Packaged for the viewer": one JSON per run, holding the view and its arrays as one
base64 payload, and one catalogue of every experiment adapted into the folder.

    python3 tools/adapt_run.py --evidence PATH
    python3 tools/adapt_run.py --experiment e07-v1 --root PATH/e07-v1-judged-20261113-01
    python3 tools/adapt_run.py --experiment e07-v1 --root PATH --run ARM/seed1 --run ARM/seed2

--evidence names the folder that holds the evidence folders: every experiment in
data/replays/selection.json is adapted from the folder the selection names for it.
--experiment with --root adapts one experiment from one folder; with no --run it takes
the runs the selection lists. Either way the catalogue keeps the experiments this call
does not adapt, with their runs and files. Output goes to out/runs/ and is never
committed.

What it keeps to:
  * It reads saved files only. Nothing is imported or run: records are parsed as a zip of
    .npy files, and constants in the evidence folder's source snapshot are read as text.
  * It judges nothing. A class is the experiment's own summary's, and readouts are
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
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from lib.hex_layout import LayoutError, embed, hexagons  # noqa: E402
from lib.npy_reader import read_npz  # noqa: E402

REPLAY_FORMAT = "cells.visualizer.replay@1"
VIEW_FORMAT = "cells.run_view@1"
INDEX_FORMAT = "cells.visualizer.replay_index@1"
PART_FORMAT = "cells.visualizer.replay_part@1"  # records of a run in a file of their own
LIMIT_BYTES = 1_000_000  # one run file stays under 1 MB
PATHS = re.compile(r"/(?:home|mnt|Users|tmp|var|root|opt|srv)/|[A-Za-z]:\\\\")
RUN_NAME = re.compile(r"[A-Za-z0-9._-]+/seed(\d+)\Z")
ARM_NAME = re.compile(r"[A-Za-z0-9._-]+\Z")
WORLD_NAME = re.compile(r"([A-Za-z0-9._-]+)/world-(\d+)\Z")
TURNOVER_LAYERS = (("membrane", "Membrane voltage"), ("replacement", "Cell replacement and junction formation"))
CUE_LAYERS = (("membrane", "Membrane voltage"), ("cue", "Write cue"))


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
    """(found, value) for a dotted name such as formation.lag_s. A number names an item of a list."""
    for part in dotted.split("."):
        if isinstance(data, dict) and part in data:
            data = data[part]
        elif isinstance(data, list) and part.isdigit() and int(part) < len(data):
            data = data[int(part)]
        else:
            return False, None
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


def snapshot_named(root, recorded, fallback=None):
    """The name of the source snapshot's folder inside the evidence folder.

    A run records the path of the source it ran from. One name is taken from that path, the
    folder that holds validation/, and only if the evidence folder has it. The path itself
    is never written.
    """
    if isinstance(recorded, str):
        parts = PurePosixPath(recorded).parts
        for index in range(1, len(parts)):
            if parts[index] == "validation" and ARM_NAME.match(parts[index - 1]) and (root / parts[index - 1] / "validation").is_dir():
                return parts[index - 1]
    return fallback


def driver_marks(root, snapshot, driver, grid_module, derivation):
    """The voltage above which the experiment counts a cell as D, and the record grid.

    Neither is in a run's own files. Both are constants of the driver, read as text from
    the evidence folder's source snapshot; if they cannot be read, they are left out.
    """
    threshold = grid = None
    if snapshot is None:
        derivation.append("No D mark is given: the run's files name no source snapshot in the evidence folder to read the threshold from.")
        return threshold, grid
    reader = SourceReader(root / snapshot)
    try:
        reader.tree(driver)
        try:
            module = reader.imported_from(driver, "THRESHOLD_V")
        except reader.Unresolved:
            module = driver  # the driver assigns the constant itself
        if "> THRESHOLD_V" not in reader.path(driver).read_text(encoding="utf-8"):
            raise reader.Unresolved("the driver does not compare a voltage with THRESHOLD_V")
        value = reader.constant(module, "THRESHOLD_V")
        if not isinstance(value, float):
            raise reader.Unresolved("THRESHOLD_V is not a number")
        threshold = value
        derivation.append(
            "The D mark on membrane voltage is not in the run's files. It is THRESHOLD_V, read as text from the evidence "
            f"folder's source snapshot ({snapshot}/{module.replace('.', '/')}.py), which the driver's analysis compares each cell's voltage with: "
            "above it a cell counts as D."
        )
    except (reader.Unresolved, OSError) as error:
        reason = error if isinstance(error, reader.Unresolved) else "a source file could not be read"
        derivation.append(f"No D mark is given: the threshold could not be read from the evidence folder's source snapshot ({reason}).")
    if grid_module:
        try:
            value = reader.constant(grid_module, "RECORD_S")
            grid = float(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else None
        except reader.Unresolved:
            pass
    return threshold, grid


def snapshot_revision(root, snapshot, derivation, otherwise):
    """The engine revision, if the evidence folder's source snapshot states it."""
    if snapshot is None:
        return None
    manifest = root / snapshot / "SNAPSHOT.json"
    if not manifest.is_file():
        return None
    data = read_json(manifest)
    revision = data.get("git_revision")
    if not (isinstance(revision, str) and re.fullmatch(r"[0-9a-f]{7,40}", revision)):
        return None
    derivation.append(f"The engine revision is the one the evidence folder's source snapshot records ({snapshot}/SNAPSHOT.json); {otherwise}.")
    return revision[:7]


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


# ---------------------------------------------------------------- what the sheet adapters share


def sphere_diameter_um(volume_pL):
    """The diameter of a sphere of this volume (1 pL is 1000 cubic micrometres)."""
    return (6.0 * volume_pL * 1000.0 / math.pi) ** (1.0 / 3.0)


def lay_out(name, model, derivation):
    """The cells and junctions of a definition, placed on the lattice their junctions make."""
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
    return SimpleNamespace(cells=cells, junctions=junctions, cell_index=cell_index, ends=ends, vertices=vertices, faces=faces, pitch=pitch)


# ---------------------------------------------------------------- the tissue family's fields
#
# What a quantity layer needs to know of a field of the tissue family (resolved_pump_tissue@3
# and the models over it) that the run's view does not declare yet: what kind of number it
# is, and for a signed one which way it is positive. This is the viewer's own table, kept
# until the engine's run view declares these itself (docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md).
#
# The signs are the engine's own convention, as the owner of its core confirmed it on
# 15 November 2026: a positive transfer leaves the cell for its outside, or the sender for
# the receiver; pump cycles are positive inwards; what a reservoir supplies is positive into
# the outside node. A field with no sign here has none confirmed, and is shown as a size or a
# level, never with a direction. The table holds for the tissue family only: the older
# single-cell model's flux is positive from bath into cell, and is not to be read by it.
#
# Every *_dissipated_energy_pJ field that exists today is zero or more and never falls,
# element by element, at each accepted row (confirmed the same day): a total that only grows,
# so that a rate worked out from it is never negative. Under the rework's exact booking one
# route's own share may be negative: `never_falls` is to be asked again of a run made then.
TISSUE_SIGN_BY = "the engine's own convention for this family of models, confirmed by the owner of its core on 15 November 2026 and not yet declared in the run's view"
_OUT = {"says": "a positive amount has left the membrane's cell for its outside", "from": "cell", "to": "outside node", "by": TISSUE_SIGN_BY}
_ALONG = {"says": "a positive amount has left the sender for the receiver", "from": "first", "to": "second", "by": TISSUE_SIGN_BY}
TISSUE_FIELDS = {
    "membrane_voltage_V": {"kind": "level", "unit": "V"},
    "cell_potential_V": {"kind": "level", "unit": "V"},
    "junction_voltage_V": {"kind": "level", "unit": "V"},
    "amount": {"kind": "amount", "unit": "fmol"},
    "extracellular_amount": {"kind": "amount", "unit": "fmol"},
    "membrane_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _OUT},
    "channel_transferred": {"kind": "cumulative", "unit": "fmol", "sign": dict(_OUT, says="a positive amount has left the channel's cell for its outside, as for its membrane")},
    "junction_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _ALONG},
    "face_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _ALONG},
    "pump_cycles": {"kind": "cumulative", "unit": "fmol", "sign": {"says": "positive cycles carry their ions into the cell: the stoichiometry times the cycles is taken from the membrane's total", "from": "outside node", "to": "cell", "by": TISSUE_SIGN_BY}},
    "reservoir_supplied": {"kind": "cumulative", "unit": "fmol", "sign": {"says": "a positive amount has entered the outside node from its reservoir", "by": TISSUE_SIGN_BY}},
    "metabolic_work_pJ": {"kind": "cumulative", "unit": "pJ"},
}
for _part in ("membrane", "channel", "junction", "face", "pump"):
    TISSUE_FIELDS[f"{_part}_dissipated_energy_pJ"] = {"kind": "cumulative", "unit": "pJ", "never_falls": True}


def tissue_field(name):
    """What the viewer's table says of one field of the tissue family, or None when it does not list it."""
    entry = TISSUE_FIELDS.get(name)
    return json.loads(json.dumps(entry)) if entry else None


# The controls a turnover definition schedules. None of them changes the potential of a held bath.
KNOWN_CONTROLS = {"end_time", "observation_times", "membrane_controls", "junction_controls", "pump_controls", "calcium_pump_controls", "channel_controls", "replacement_events"}


def owners_of(definition):
    """The model or law that the run's definition names for each saved state: {record id: name or None}."""
    model = definition.get("model") or {}
    replacement = model.get("replacement") or {}
    gates = {(junction.get("gate") or {}).get("law") for junction in model.get("junctions") or []}
    name = lambda value: value if isinstance(value, str) and value else None  # noqa: E731
    return {
        "vm": name(model.get("id")),
        "generation": name(replacement.get("law")),
        "junction_abundance": name((replacement.get("junction_formation") or {}).get("law")),
        "junction_gate": name(next(iter(gates))) if len(gates) == 1 else None,
    }


def surroundings_of(definition):
    """Whether every cell's surroundings share one potential, as the definition states it; None when it does not say.

    Each membrane's outside must be a held bath (a reservoir), all at one boundary potential,
    and the experiment must schedule nothing beyond the controls known to leave a bath's
    potential alone. Only then is the difference of two cells' membrane voltages the voltage
    across the junction between them (schema/QUANTITY_LAYERS.md, rule 1).
    """
    model, experiment = definition.get("model") or {}, definition.get("experiment") or {}
    outside = {node.get("id"): node for node in model.get("extracellular") or [] if isinstance(node, dict)}
    membranes = model.get("membranes") or []
    nodes = [outside.get(membrane.get("outside")) for membrane in membranes if isinstance(membrane, dict)]
    if not nodes or len(nodes) != len(model.get("cells") or []):
        return None
    if any(node is None or node.get("reservoir") is not True or isinstance(node.get("boundary_potential_V"), bool) or not isinstance(node.get("boundary_potential_V"), (int, float)) for node in nodes):
        return None
    potentials = {float(node["boundary_potential_V"]) for node in nodes}
    if len(potentials) != 1 or set(experiment) - KNOWN_CONTROLS:
        return None
    potential = potentials.pop()
    return {"shared": True, "potential_V": potential, "says": f"In this run every cell's surroundings are a held bath at {potential:g} V: its definition says so, and nothing it schedules changes a bath's potential."}


def increasing(name, times):
    if any(later <= earlier for earlier, later in zip(times, times[1:])):
        raise Refused(f"{name}: the record times do not increase")


def d_mark(threshold):
    return [{"value": threshold, "label": "D above this voltage, H below"}] if threshold is not None else None


def turnover_records(name, folder, sheet, result, threshold, grid, entry, derivation, definition=None):
    """The arrays of a turnover run's records.npz, as (payload, records, saved arrays, parts).

    parts are records that go in files of their own beside the run's, fetched when a layer
    needs them (schema/QUANTITY_LAYERS.md, rule 10): [{"id", "label", "payload"}].
    """
    cells, junctions = sheet.cells, sheet.junctions
    owners = owners_of(definition or {})
    saved = read_npz(folder / "records.npz", ["t", "vm", "generation", "abundance", "regular", "valid"])
    count = saved["t"].shape[0]
    expected = {"t": (count,), "vm": (count, len(cells)), "generation": (count, len(cells)), "abundance": (count, len(junctions)), "regular": (count,), "valid": (count,)}
    for key, shape in expected.items():
        if saved[key].shape != shape:
            raise Refused(f"{name}: records.npz {key} has shape {saved[key].shape}, expected {shape}")
    if result.get("records") not in (None, count):
        raise Refused(f"{name}: result.json counts {result['records']} records, records.npz holds {count}")
    times = saved["t"].values
    increasing(name, times)
    labels = entry.get("records", {})
    label_of = lambda identifier, fallback: labels.get(identifier, {}).get("label", fallback)  # noqa: E731
    payload, records = Payload(), []
    records.append(describe(payload, "t", "Time", "s", ["time"], "float32", (count,), array("f", times)))
    records.append(
        describe(payload, "vm", label_of("vm", "Membrane voltage"), "V", ["time", "cell"], "float32", saved["vm"].shape, array("f", saved["vm"].values), set="cell", layer="membrane", marks=d_mark(threshold), kind="level", owner=owners["vm"])
    )
    generation = saved["generation"].values
    if min(generation) < 0:
        raise Refused(f"{name}: a negative generation")
    code, dtype = ("B", "uint8") if max(generation) < 256 else ("H", "uint16") if max(generation) < 65536 else ("i", "int32")
    records.append(
        describe(payload, "generation", label_of("generation", "Generation"), "1", ["time", "cell"], dtype, saved["generation"].shape, array(code, generation), set="cell", layer="replacement", kind="level", owner=owners["generation"])
    )
    abundance = saved["abundance"].values
    label = label_of("junction_abundance", "Junction abundance")
    if all(math.isfinite(value) and -1e-9 <= value <= 1 + 1e-9 for value in abundance):
        stored = array("B", (min(255, max(0, round(value * 255))) for value in abundance))
        records.append(
            describe(payload, "junction_abundance", label, "1", ["time", "junction"], "uint8", saved["abundance"].shape, stored, value_scale=1 / 255, set="junction", layer="replacement", kind="level", owner=owners["junction_abundance"])
        )
        derivation.append("Junction abundance is stored in 256 steps, for drawing only (value = stored x 1/255); the run saved it as 64-bit numbers.")
    else:
        records.append(
            describe(payload, "junction_abundance", label, "1", ["time", "junction"], "float32", saved["abundance"].shape, array("f", abundance), set="junction", layer="replacement", kind="level", owner=owners["junction_abundance"])
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
    stated = "the model or law that the run's definition.json names for that state" if any(owners.values()) else "not stated: the run's definition.json names no model or law for these states"
    derivation.append(
        f"What kind of number each record is (a level) is read from the driver that wrote records.npz, which states none. Each record's owner is {stated}. "
        "Which way the membrane voltage is positive is stated by neither, so it is shown as a level and given no direction."
    )
    parts = []
    # Each junction's gate, where the run saved it, goes in a file of its own: only the layer that reads it fetches it.
    try:
        gate = read_npz(folder / "records.npz", ["gate"])["gate"]
    except ValueError:
        gate = None
    if gate is not None:
        if gate.shape != (count, len(junctions)):
            raise Refused(f"{name}: records.npz gate has shape {gate.shape}, expected {(count, len(junctions))}")
        if not all(math.isfinite(value) and -1e-9 <= value <= 1 + 1e-9 for value in gate.values):
            raise Refused(f"{name}: a junction's gate is not between 0 and 1")
        own = Payload()
        stored = array("B", (min(255, max(0, round(value * 255))) for value in gate.values))
        records.append(
            describe(own, "junction_gate", label_of("junction_gate", "Junction gate"), "1", ["time", "junction"], "uint8", gate.shape, stored, value_scale=1 / 255, set="junction", layer="junctions", kind="level", owner=owners["junction_gate"], part="junction-gate")
        )
        parts.append({"id": "junction-gate", "label": "Each junction's gate", "payload": own})
        derivation.append("Each junction's gate (how far it is open, 0 to 1) is stored in 256 steps, for drawing only, in a file of its own beside this one; the run saved it as 64-bit numbers.")
    return payload, records, saved, parts


def replacement_events(name, definition, plan, sheet, last, derivation):
    """The scheduled replacements up to the run's last record, as (events, how many were left out)."""
    cell_index = sheet.cell_index
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
    return events, dropped


def disc_region(name, entry, sheet, indices):
    indices = sorted(int(index) for index in indices)
    if indices and (indices[0] < 0 or indices[-1] >= len(sheet.cells) or len(set(indices)) != len(indices)):
        raise Refused(f"{name}: the disc names cells the sheet does not have")
    return {"id": "disc", "label": entry.get("regions", {}).get("disc", {}).get("label", "The disc"), "set": "cell", "indices": indices}


def copied(entry, plan, outcome, supplementary):
    """The plan values and outcome values the catalogue names, under the run's own names."""
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
    return parameters, readouts


def layers_stated(entry, derivation):
    stated = entry.get("layers", {})
    if any(layer.get("representation") for layer in stated.values()):
        derivation.append("How each layer is represented (simulated, modelled or prescribed) is not stated by the run's files; it is the catalogue's curated entry.")
    else:
        derivation.append("How each layer is represented (simulated, modelled or prescribed) is not stated by the run's files, and is left unset.")
    return stated


def refusal_of(recorded):
    """A refusal as the run's files record it. A traceback is left out: it holds machine paths."""
    if isinstance(recorded, dict):
        recorded = {key: value for key, value in recorded.items() if key != "traceback"}
    return recorded or None


def assemble(run, layers, stated, sheet, records, regions, events, derivation, parts=(), surroundings=None):
    if any(record.get("layer") == "junctions" for record in records):
        layers = tuple(layers) + (("junctions", "Junction gating"),)
    view = {
        "format": VIEW_FORMAT,
        "derived": True,
        "derivation": derivation,
        "run": run,
        "time": {"unit": "s", "record": "t"},
        "space": {"unit": "um", "dimensions": 2},
        "layers": [{"id": layer, "label": stated.get(layer, {}).get("label", fallback), "representation": stated.get(layer, {}).get("representation")} for layer, fallback in layers],
        "sets": [
            {"id": "cell", "scale": "cell", "ids": sheet.cells, "geometry": {"kind": "polygons", "vertices": sheet.vertices, "faces": sheet.faces}},
            {"id": "junction", "scale": "cell", "ids": sheet.junctions, "geometry": {"kind": "links", "between": "cell", "ends": sheet.ends}},
        ],
        "records": records,
        "regions": regions,
        "events": events,
    }
    if not regions:
        del view["regions"]
    if parts:
        # Records in files of their own: each named by the run's id and the part's.
        view["parts"] = [{"id": part["id"], "label": part["label"], "file": f"runs/{run['id']}.{part['id']}.json", "byte_length": part["payload"].length} for part in parts]
    if surroundings:
        view["surroundings"] = surroundings
    return view


def run_facts(experiment, arm, seed, *, label, group, engine_models, revision, end_s, stop, refusal=None, run_class=None, judged_s=None, parameters, readouts):
    """view.run. A class and a refusal are there only when the run's files record one."""
    run = {"id": run_id(experiment, arm, seed), "experiment": experiment, "arm": arm, "seed": seed, "label": label, "group": group}
    run.update({"engine_models": list(engine_models or []), "revision": revision, "end_s": plain_number(end_s), "stop": stop})
    if refusal is not None:
        run["refusal"] = refusal
    if run_class is not None:
        run["class"] = run_class
    run.update({"judged_s": plain_number(judged_s), "parameters": parameters, "readouts": readouts})
    return run


def above(values, threshold):
    return [index for index, value in enumerate(values) if value > threshold]


def turnover_notes(saved, sheet, events, dropped, revision, threshold, regions):
    """For the terminal only: nothing here is written to the view."""
    count, width = saved["t"].shape[0], len(sheet.cells)
    notes = {"records": count, "on_grid": sum(saved["regular"].values), "valid": sum(saved["valid"].values), "cells": width, "junctions": len(sheet.junctions), "events": len(events), "dropped": dropped, "pitch_um": sheet.pitch, "revision": revision}
    if threshold is not None:
        voltages = saved["vm"].values
        notes["above_mark_first"] = len(above(voltages[:width], threshold))
        notes["above_mark_last"] = len(above(voltages[-width:], threshold))
        if regions:
            notes["first_equals_disc"] = above(voltages[:width], threshold) == regions[0]["indices"]
    return notes


# ---------------------------------------------------------------- E07-v1


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
    # A class is the summary's. An experiment whose catalogue entry lists classes has one for every run.
    recorded = (summary.get("runs") or {}).get(name) or {}
    run_class = recorded.get("run_class")
    if entry.get("classes") and run_class is None:
        raise Refused(f"summary.json records no class for {name}")
    if run_class is not None and "run_class" in outcome and outcome["run_class"] != run_class:
        raise Refused(f"{name}: summary.json says {run_class!r}, outcome.json says {outcome['run_class']!r}")
    derivation = []
    sheet = lay_out(name, definition["model"], derivation)
    snapshot = snapshot_named(root, (result.get("provenance") or {}).get("source"), "snapshot")
    threshold, grid = driver_marks(root, snapshot, "validation.tissue.e07_v1_run", "validation.tissue.e07_v1_turnover", derivation)
    payload, records, saved, parts = turnover_records(name, folder, sheet, result, threshold, grid, entry, derivation, definition)
    events, dropped = replacement_events(name, definition, plan, sheet, saved["t"].values[-1], derivation)

    regions = []
    if plan.get("scope") == "disc" and len(plan.get("permutation") or []) == plan.get("size"):
        regions.append(disc_region(name, entry, sheet, plan["permutation"]))
        derivation.append("The disc is the plan's replacement order (permutation): in this arm only the disc's cells are replaced (scope 'disc'), so the plan lists exactly them.")
    elif threshold is not None and isinstance(plan.get("size"), int):
        # An arm that replaces the whole sheet names no disc. The disc is the written cells, so it
        # is taken as the cells the experiment counts as D at the first record, and only if they
        # are as many as the plan says the disc has.
        indices = above(saved["vm"].values[: len(sheet.cells)], threshold)
        if len(indices) == plan["size"]:
            regions.append(disc_region(name, entry, sheet, indices))
            derivation.append(
                f"The disc is not named in this arm's files. It is taken as the cells above the D mark at the first record: {len(indices)} cells, the disc size the plan states."
            )
        else:
            derivation.append(f"No disc is drawn: {len(indices)} cells are above the D mark at the first record, and the plan states a disc of {plan['size']}.")

    parameters, readouts = copied(entry, plan, outcome, summary.get("supplementary_readouts") or {})
    if run_class is not None:
        derivation.append("The class is the one summary.json records for this run. Parameters are copied from plan.json and readouts from outcome.json, under their own names.")
    else:
        derivation.append("Parameters are copied from plan.json and readouts from outcome.json, under their own names. The experiment's summary records no class for this run.")
    stated = layers_stated(entry, derivation)
    revision = snapshot_revision(root, snapshot, derivation, "the run's own result.json states none")
    run = run_facts(
        experiment, arm, seed, label=plan.get("label"), group=plan.get("group"), engine_models=result.get("engine_models"), revision=revision,
        end_s=result.get("end_s"), stop=result.get("stop"), refusal=refusal_of(result.get("refusal")), run_class=run_class,
        judged_s=outcome.get("judged_s"), parameters=parameters, readouts=readouts,
    )  # fmt: skip
    surroundings = surroundings_of(definition)
    if surroundings:
        derivation.append("That every cell's surroundings share one potential is read from definition.json: each membrane's outside is a held bath (a reservoir), all at one boundary potential, and the experiment schedules no control of a bath.")
    view = assemble(run, TURNOVER_LAYERS, stated, sheet, records, regions, events, derivation, parts, surroundings)
    notes = turnover_notes(saved, sheet, events, dropped, revision, threshold, regions)
    notes["parts"] = {part["id"]: part["payload"].data() for part in parts}
    return view, payload.data(), notes


# ---------------------------------------------------------------- the turnover pre-screen


def adapt_turnover_literature(root, name, experiment, entry):
    """One arm of the turnover pre-screen under the literature newcomer rule (arms/<arm>).

    The files are those of an E07-v1 run, which grew out of this driver, with three
    differences: an arm is one run and has no seed, the plan names no group and no scope,
    and nothing records a class.
    """
    if not ARM_NAME.match(name):
        raise Refused(f"'{name}' is not an arm's name")
    folder = root / "arms" / name
    if not folder.is_dir():
        raise Refused(f"no arm folder arms/{name} in {root.name}/")
    plan, outcome, result, definition = (read_json(folder / f"{part}.json") for part in ("plan", "outcome", "result", "definition"))
    summary = read_json(root / "summary.json")
    for label, data in (("outcome.json", outcome), ("result.json", result)):
        if data.get("arm") != name:
            raise Refused(f"arms/{name}/{label} is for {data.get('arm')}")
    recorded = (summary.get("arms") or {}).get(name)
    if recorded is None:
        raise Refused(f"summary.json lists no arm called {name}")
    for key in ("stop", "end_s"):
        if not (recorded.get(key) == outcome.get(key) == result.get(key)):
            raise Refused(f"{name}: {key} differs between summary.json, outcome.json and result.json")
    derivation = []
    sheet = lay_out(name, definition["model"], derivation)
    driver = "validation.tissue.heredity_turnover_literature"
    snapshot = snapshot_named(root, (result.get("provenance") or {}).get("source"))
    threshold, grid = driver_marks(root, snapshot, driver, driver, derivation)
    payload, records, saved, parts = turnover_records(name, folder, sheet, result, threshold, grid, entry, derivation, definition)
    events, dropped = replacement_events(name, definition, plan, sheet, saved["t"].values[-1], derivation)

    # The driver replaces only the disc's cells, in the order of the plan's permutation.
    order = plan.get("permutation") or []
    if len(order) != plan.get("size"):
        raise Refused(f"{name}: the plan's permutation has {len(order)} cells and its disc {plan.get('size')}")
    disc = disc_region(name, entry, sheet, order)
    if any(event["at"]["index"] not in disc["indices"] for event in events):
        raise Refused(f"{name}: a replacement falls outside the plan's permutation, so the permutation is not the disc")
    derivation.append("The disc is the plan's replacement order (permutation): this driver replaces only the disc's cells, so the plan lists exactly them.")
    counted = None
    if threshold is not None:
        counted = counts_agree(name, saved["t"].values, saved["vm"].values, sheet, disc["indices"], threshold, outcome.get("series") or {})

    group = plan.get("kind")
    derivation.append("The plan names no group. Runs are grouped by the plan's newcomer kind (kind).")
    parameters, readouts = copied(entry, plan, outcome, {})
    derivation.append("Parameters are copied from plan.json and readouts from outcome.json, under their own names. An arm is one run: it has no seed of its own, and the experiment records no class.")
    stated = layers_stated(entry, derivation)
    revision = snapshot_revision(root, snapshot, derivation, "the run's own result.json states none")
    run = run_facts(
        experiment, name, None, label=None, group=group if isinstance(group, str) else None, engine_models=result.get("engine_models"), revision=revision,
        end_s=result.get("end_s"), stop=result.get("stop"), refusal=refusal_of(result.get("refusal")), parameters=parameters, readouts=readouts,
    )  # fmt: skip
    surroundings = surroundings_of(definition)
    if surroundings:
        derivation.append("That every cell's surroundings share one potential is read from definition.json: each membrane's outside is a held bath (a reservoir), all at one boundary potential, and the experiment schedules no control of a bath.")
    view = assemble(run, TURNOVER_LAYERS, stated, sheet, records, [disc], events, derivation, parts, surroundings)
    notes = turnover_notes(saved, sheet, events, dropped, revision, threshold, [disc])
    notes["counts_checked"] = counted
    notes["parts"] = {part["id"]: part["payload"].data() for part in parts}
    return view, payload.data(), notes


def counts_agree(name, times, voltages, sheet, disc, threshold, series):
    """Check the D cells inside and outside the disc against the run's own counts per record.

    The run's outcome lists, for each record on its grid, how many cells it counted as D
    inside and outside the disc. The same counts are made here from the saved voltages. If
    they differ, the disc, the mark or the order of the cells was read wrongly, and the
    run is refused. Returns how many records were compared.
    """
    listed = {round(float(time), 6): (inside, outside) for time, inside, outside in zip(series.get("t_s") or [], series.get("d_inside") or [], series.get("d_outside") or [])}
    if not listed:
        return None
    width, inside_disc = len(sheet.cells), set(disc)
    compared = 0
    for row, time in enumerate(times):
        counts = listed.get(round(float(time), 6))
        if counts is None:
            continue
        d_cells = above(voltages[row * width : (row + 1) * width], threshold)
        inside = sum(1 for cell in d_cells if cell in inside_disc)
        if (inside, len(d_cells) - inside) != (int(counts[0]), int(counts[1])):
            raise Refused(f"{name}: at {time:g} s the saved voltages give {inside} D cells inside the disc and {len(d_cells) - inside} outside; the run's own counts are {counts[0]} and {counts[1]}")
        compared += 1
    return compared


# ---------------------------------------------------------------- the W1 heredity pilot


def logged_snapshot(root, study, part):
    """The source snapshot the evidence folder's run log names for one part of a study.

    runs.jsonl has one line per launch, with the folder it wrote into, its arguments and
    the path of the source it ran from. Only the snapshot folder's name is taken.
    """
    log = root / "runs.jsonl"
    if not log.is_file():
        return None
    found = None
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and item.get("output") == study and str(item.get("args") or "").split()[:1] == [part] and isinstance(item.get("source"), str):
            folder = PurePosixPath(item["source"]).name
            if ARM_NAME.match(folder) and (root / folder / "validation").is_dir():
                found = folder  # the last launch is the one whose files are there
    return found


def cue_schedule(name, definition, sheet):
    """Per cell, the availability schedule of its cue channels: {cell index: [(time, availability)]}.

    The cue is a channel population on every membrane patch of the disc's cells, switched
    by the definition's channel controls. A cell's patches must share one schedule.
    """
    model = definition["model"]
    inside = {membrane["id"]: membrane["inside"] for membrane in model["membranes"]}
    membrane_of = {channel["id"]: channel["membrane_id"] for channel in model["channels"]}
    schedules = {}
    for control in definition["experiment"].get("channel_controls") or []:
        steps = [(float(step["time"]), float(step["availability"])) for step in control.get("schedule") or []]
        channel = control["channel_id"]
        if not channel.startswith("cue_"):
            if len(steps) > 1:
                raise Refused(f"{name}: the channel {channel} is switched during the run and is not a cue population")
            continue
        cell = sheet.cell_index.get(inside.get(membrane_of.get(channel)))
        if cell is None:
            raise Refused(f"{name}: the cue channel {channel} is on no cell of the sheet")
        if schedules.setdefault(cell, steps) != steps:
            raise Refused(f"{name}: the cue channels of {sheet.cells[cell]} do not share one schedule")
    return schedules


def cue_events(name, schedules, last, derivation):
    """One event per cell each time its cue switches on or off, up to the run's last record."""
    events, dropped = [], 0
    for cell in sorted(schedules):
        steps = schedules[cell]
        for (_, before), (time, after) in zip(steps, steps[1:]):
            if before == 0 and after > 0:
                kind = "cue_on"
            elif before > 0 and after == 0:
                kind = "cue_off"
            else:
                raise Refused(f"{name}: a cue availability changes from {before:g} to {after:g}, which is neither on nor off")
            if time > last + 1e-9:
                dropped += 1
                continue
            events.append({"time": time, "kind": kind, "layer": "cue", "at": {"set": "cell", "index": cell}, "label": f"availability {after:g}"})
    events.sort(key=lambda event: (event["time"], event["at"]["index"]))
    if dropped:
        derivation.append(f"{dropped} scheduled cue changes after the run's last record ({last:g} s) are left out: the run stopped before them.")
    return events, dropped


def adapt_pilot_w1(root, name, experiment, entry):
    """One world of a W1 pilot run (<study>/world-N): a cue writes a disc on the full tissue.

    A study folder holds, under run/, one definition per world, the per-cell voltages the
    driver saved (world-N-cell-vm.npz) and run.json. There are no replacements; the cue is
    a schedule in the definition.
    """
    match = WORLD_NAME.match(name)
    if not match:
        raise Refused(f"'{name}' is not STUDY/world-N")
    study, world = match.group(1), match.group(2)
    folder = root / study / "run"
    if not folder.is_dir():
        raise Refused(f"no run folder {study}/run in {root.name}/")
    recorded = read_json(folder / "run.json")
    facts = (recorded.get("worlds") or {}).get(world)
    if not isinstance(facts, dict):
        raise Refused(f"{study}/run/run.json lists no world {world}")
    definition = read_json(folder / "definitions" / f"world-{world}.json")
    model = definition["model"]
    derivation = []
    sheet = lay_out(name, model, derivation)
    snapshot = logged_snapshot(root, study, "run")
    driver = "validation.tissue.heredity_pilot"
    if snapshot is not None:
        try:
            described = " ".join(SourceReader(root / snapshot).path(driver).read_text(encoding="utf-8").split())
        except (OSError, UnicodeDecodeError):
            described = ""
        if "jittered hexagonal lattice" in described:
            derivation.append("The driver describes the tissue's cells as lying on a jittered hexagonal lattice. The saved definition holds no coordinates, so the jitter is not drawn.")
    derivation.append(
        f"The tissue also has {len(model.get('extracellular') or [])} compartments of fluid around the cells, joined by {len(model.get('faces') or [])} faces. "
        "They are not drawn: the run saved one voltage per cell, and the replay shows the cells and their junctions."
    )

    saved = read_npz(folder / "records" / f"world-{world}-cell-vm.npz", ["times_s", "cell_vm_V"])
    count = saved["times_s"].shape[0]
    if saved["times_s"].shape != (count,) or saved["cell_vm_V"].shape != (count, len(sheet.cells)):
        raise Refused(f"{name}: cell_vm_V has shape {saved['cell_vm_V'].shape}, expected {(count, len(sheet.cells))}")
    times, voltages = saved["times_s"].values, saved["cell_vm_V"].values
    increasing(name, times)
    threshold, _ = driver_marks(root, snapshot, driver, None, derivation)
    if snapshot is not None:
        derivation.append(f"The source snapshot ({snapshot}) is the one the evidence folder's run log (runs.jsonl) names for this run; run.json names none.")
    labels = entry.get("records", {})
    payload, records = Payload(), []
    records.append(describe(payload, "t", "Time", "s", ["time"], "float32", (count,), array("f", times)))
    records.append(
        describe(
            payload, "vm", labels.get("vm", {}).get("label", "Membrane voltage"), "V", ["time", "cell"], "float32", saved["cell_vm_V"].shape, array("f", voltages),
            set="cell", layer="membrane", marks=d_mark(threshold),
            note="One voltage per cell, as the run saved it (cell_vm_V): the driver averages the membrane voltages of the cell's patches.",
        )
    )  # fmt: skip
    derivation.append("Record names and units are the saved arrays' own (times_s, cell_vm_V): times in s, and one voltage in V per cell, in the definition's order.")
    derivation.append("Times and membrane voltages are stored as 32-bit numbers; the run saved 64-bit.")

    schedules = cue_schedule(name, definition, sheet)
    events, dropped = cue_events(name, schedules, times[-1], derivation)
    cued = [cell for cell, steps in schedules.items() if any(availability > 0 for _, availability in steps)]
    if facts.get("disc_cells") != len(cued):
        raise Refused(f"{name}: the definition switches the cue on in {len(cued)} cells; run.json states a disc of {facts.get('disc_cells')}")
    disc = disc_region(name, entry, sheet, cued)
    derivation.append(f"The disc is the cells whose cue the definition's schedule switches on: {len(cued)} cells, the disc size run.json states.")
    counted = None
    if threshold is not None:
        counted = counts_agree(name, times, voltages, sheet, disc["indices"], threshold, own_counts(folder / "records" / f"world-{world}.jsonl"))

    failure = refusal_of(recorded.get("failure"))
    plan = dict(facts)
    plan["phases_s"] = recorded.get("phases_s") or {}
    plan["execution"] = {"dt": (definition.get("execution") or {}).get("dt")}
    plan["model"] = {key: model[key] for key in ("junction_heat_booking",) if key in model}
    outcome_file = folder / "results.json"
    outcome = ((read_json(outcome_file).get("worlds") or {}).get(world) or {}) if outcome_file.is_file() else {}
    parameters, readouts = copied(entry, plan, outcome, {})
    derivation.append(
        "Parameters are copied under their own names from run.json (this world's entry and phases_s) and from the definition (execution.dt and the model's options)."
        + (" Readouts are copied from results.json." if outcome else " The run saved no outcome file, so no readout is copied.")
    )
    derivation.append("The run's files give no word for how it ended, so none is given; a failure that run.json records is carried as the refusal, without its traceback. The end time is the last saved record's.")
    stated = layers_stated(entry, derivation)
    revision = snapshot_revision(root, snapshot, derivation, "run.json states none")
    seed = facts.get("seed") if isinstance(facts.get("seed"), int) else None
    run = run_facts(
        experiment, f"{study}-world-{world}", seed, label=None, group=study, engine_models=[model["id"]] if isinstance(model.get("id"), str) else [], revision=revision,
        end_s=times[-1], stop=None, refusal=failure, parameters=parameters, readouts=readouts,
    )  # fmt: skip
    view = assemble(run, CUE_LAYERS, stated, sheet, records, [disc], events, derivation)
    width = len(sheet.cells)
    notes = {"records": count, "cells": width, "junctions": len(sheet.junctions), "events": len(events), "dropped": dropped, "pitch_um": sheet.pitch, "revision": revision, "counts_checked": counted}
    if threshold is not None:
        notes["above_mark_first"] = len(above(voltages[:width], threshold))
        notes["above_mark_last"] = len(above(voltages[-width:], threshold))
    return view, payload.data(), notes


def own_counts(path):
    """The run's own per-record D counts (world-N.jsonl), as the series counts_agree reads."""
    series = {"t_s": [], "d_inside": [], "d_outside": []}
    if not path.is_file():
        return series
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            item = json.loads(line)
        except ValueError:
            continue
        if isinstance(item, dict) and all(isinstance(item.get(key), (int, float)) for key in ("t", "d_inside", "d_outside")):
            series["t_s"].append(item["t"])
            series["d_inside"].append(item["d_inside"])
            series["d_outside"].append(item["d_outside"])
    return series


ADAPTERS = {"e07-v1": adapt_e07_v1, "heredity-turnover-literature": adapt_turnover_literature, "heredity-pilot-w1": adapt_pilot_w1}


# ---------------------------------------------------------------- writing


def run_id(experiment, arm, seed=None):
    """<experiment>--<arm>--seed<n>, or <experiment>--<arm> for a run that has no seed."""
    name = f"{experiment}--{arm}" if seed is None else f"{experiment}--{arm}--seed{seed}"
    text = re.sub(r"[^a-z0-9.-]+", "-", name.lower())
    if not re.fullmatch(r"[a-z0-9.-]+", text):
        raise Refused(f"cannot make a run id from {experiment}, {arm}, seed {seed}")
    return text


def serialise(data):
    return (json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def check_clean(name, text):
    found = PATHS.search(text)
    if found:
        raise Refused(f"{name} would carry a machine path ({found.group(0)}...)")


def row_of(run, records, size, parts=()):
    """A run's line in the catalogue. A class and a refusal are there only when the run has one.

    parts lists the run's records that are in files of their own, [{"id", "file", "bytes"}], so
    that whoever publishes the runs knows every file without opening one.
    """
    row = {"id": run["id"], "experiment": run["experiment"], "arm": run["arm"], "seed": run["seed"], "label": run["label"], "group": run["group"]}
    if "class" in run:
        row["class"] = run["class"]
    row["stop"] = run["stop"]
    if "refusal" in run:
        row["refusal"] = run["refusal"]
    row.update({"records": records, "end_s": run["end_s"], "file": f"runs/{run['id']}.json", "bytes": size})
    if parts:
        row["parts"] = list(parts)
    return row


def experiments_of(selection):
    """The selection's experiments: its other keys, such as the note, are not experiments."""
    return {key: value for key, value in selection.items() if isinstance(value, dict)}


def jobs_of(arguments, curated):
    """What this call adapts, as [(experiment, evidence folder, run names)]."""
    if arguments.root:
        if arguments.evidence or not arguments.experiment:
            raise Refused("--root is one experiment's evidence folder: give it with --experiment, and without --evidence")
        root = Path(arguments.root).resolve()
        if not root.is_dir():
            raise Refused("the evidence folder given with --root does not exist")
        names = list(arguments.run)
        if not names:
            chosen = experiments_of(read_json(arguments.selection)).get(arguments.experiment) or {}
            names = list(chosen.get("runs") or [])
            if chosen.get("evidence_folder") and chosen["evidence_folder"] != root.name:
                print(f"note: the selection names the evidence folder {chosen['evidence_folder']}; reading {root.name}", file=sys.stderr)
        jobs = [(arguments.experiment, root, names)]
    elif arguments.evidence:
        parent = Path(arguments.evidence).resolve()
        if not parent.is_dir():
            raise Refused("the folder given with --evidence does not exist")
        chosen = experiments_of(read_json(arguments.selection))
        wanted = [arguments.experiment] if arguments.experiment else list(chosen)
        if arguments.run and len(wanted) != 1:
            raise Refused("--run names runs of one experiment: give --experiment as well")
        jobs = []
        for experiment in wanted:
            item = chosen.get(experiment)
            if item is None:
                raise Refused(f"the selection lists no experiment called {experiment}")
            folder = item.get("evidence_folder")
            if not isinstance(folder, str) or not ARM_NAME.match(folder):
                raise Refused(f"the selection gives {experiment} no evidence folder's name")
            if not (parent / folder).is_dir():
                raise Refused(f"the evidence folder {folder} is not in the folder given with --evidence")
            jobs.append((experiment, parent / folder, list(arguments.run) or list(item.get("runs") or [])))
    else:
        raise Refused("give --evidence, or --experiment with --root")
    for experiment, _, names in jobs:
        entry = curated.get(experiment)
        if entry is None:
            raise Refused(f"the overlay has no experiment called {experiment}")
        if entry.get("adapter", experiment) not in ADAPTERS:
            raise Refused(f"no adapter for {entry.get('adapter', experiment)} (known: {', '.join(sorted(ADAPTERS))})")
        if not names:
            raise Refused(f"no runs to adapt for {experiment}: give --run, or list runs in the selection")
        if len(set(names)) != len(names):
            raise Refused(f"a run of {experiment} is named twice")
    if len({experiment for experiment, _, _ in jobs}) != len(jobs):
        raise Refused("an experiment is named twice")
    return jobs


def catalogue_in(out):
    """The catalogue already in the output folder, as ({experiment: entry}, {experiment: rows})."""
    entries, rows = {}, {}
    path = out / "index.json"
    if path.is_file():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            existing = None
        listed = existing.get("experiments") if isinstance(existing, dict) else None
        runs = existing.get("runs") if isinstance(existing, dict) else None
        if not (isinstance(existing, dict) and existing.get("format") == INDEX_FORMAT and isinstance(listed, list) and isinstance(runs, list)):
            raise Refused(f"index.json in {out.name}/ is not a replay catalogue ({INDEX_FORMAT}); it is left as it is")
        for item in listed:
            if not (isinstance(item, dict) and isinstance(item.get("id"), str)):
                raise Refused(f"index.json in {out.name}/ lists an experiment with no id; it is left as it is")
            entries[item["id"]] = item
            rows[item["id"]] = []
        for row in runs:
            if not (isinstance(row, dict) and row.get("experiment") in entries and isinstance(row.get("id"), str)):
                raise Refused(f"index.json in {out.name}/ lists a run of an experiment it does not list; it is left as it is")
            rows[row["experiment"]].append(row)
    return entries, rows


def merged_catalogue(out, existing, order, adapted):
    """The folder's catalogue with this call's experiments put in.

    adapted is {experiment: (catalogue entry, rows)}. An experiment adapted now has exactly
    the runs of this call. Every other experiment already in the folder's catalogue keeps
    its entry and its runs as they are. Experiments stand in the overlay's order.
    """
    entries, rows = dict(existing[0]), dict(existing[1])
    kept = [identifier for identifier in entries if identifier not in adapted]
    for identifier, (entry, listed) in adapted.items():
        entries[identifier] = {"id": identifier, **entry}
        rows[identifier] = listed
    for identifier in kept:
        gone = [row["id"] for row in rows[identifier] if not (out / f"{row['id']}.json").is_file()]
        if gone:
            print(f"note: {len(gone)} run(s) of {identifier} have no file in {out.name}/ any more and are taken out of the catalogue: {', '.join(gone[:4])}", file=sys.stderr)
            rows[identifier] = [row for row in rows[identifier] if row["id"] not in gone]
    ordered = [identifier for identifier in order if identifier in entries] + [identifier for identifier in entries if identifier not in order]
    index = {"format": INDEX_FORMAT, "experiments": [entries[identifier] for identifier in ordered], "runs": [row for identifier in ordered for row in rows[identifier]]}
    return index, kept


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--evidence", help="the folder that holds the evidence folders; adapts every experiment in the selection (read only)")
    parser.add_argument("--experiment", help="one experiment's id in the overlay, for example e07-v1")
    parser.add_argument("--root", help="that experiment's evidence folder (read only)")
    parser.add_argument("--run", action="append", default=[], help="a run's name in its evidence folder, for example ARM/seedN; may be given several times (default: the selection's runs)")
    parser.add_argument("--selection", default=str(HERE.parent / "data" / "replays" / "selection.json"))
    parser.add_argument("--overlay", default=str(HERE.parent / "data" / "replays" / "overlay.json"))
    parser.add_argument("--out", default=str(HERE.parent / "out" / "runs"))
    arguments = parser.parse_args(argv)

    curated = read_json(arguments.overlay).get("experiments") or {}
    jobs = jobs_of(arguments, curated)
    out = Path(arguments.out)
    out.mkdir(parents=True, exist_ok=True)
    existing = catalogue_in(out)  # an index.json that is not a catalogue stops the call before anything is written
    adapted, written = {}, set()
    for experiment, root, names in jobs:
        entry = curated[experiment]
        adapter = ADAPTERS[entry.get("adapter", experiment)]
        listed = []
        for name in names:
            view, data, notes = adapter(root, name, experiment, entry)
            replay = {"format": REPLAY_FORMAT, "view": view, "payload": {"encoding": "base64", "byte_length": len(data), "data": base64.b64encode(data).decode("ascii")}}
            check_clean(name, json.dumps(view, ensure_ascii=False))
            content = serialise(replay)
            if len(content) >= LIMIT_BYTES:
                raise Refused(f"{name} would be {len(content):,} bytes; a run file stays under {LIMIT_BYTES:,}")
            run = view["run"]
            if run["id"] in written:
                raise Refused(f"two runs would both be called {run['id']}")
            written.add(run["id"])
            (out / f"{run['id']}.json").write_bytes(content)
            # The run's records in files of their own, each under the same size limit.
            beside = []
            for part in view.get("parts") or []:
                arrays = notes["parts"][part["id"]]
                text = serialise({"format": PART_FORMAT, "run": run["id"], "part": part["id"], "payload": {"encoding": "base64", "byte_length": len(arrays), "data": base64.b64encode(arrays).decode("ascii")}})
                if len(text) >= LIMIT_BYTES:
                    raise Refused(f"{name}: its part {part['id']} would be {len(text):,} bytes; a file of a run stays under {LIMIT_BYTES:,}")
                (out / Path(part["file"]).name).write_bytes(text)
                beside.append({"id": part["id"], "file": part["file"], "bytes": len(text)})
            listed.append(row_of(run, notes["records"], len(content), beside))
            flags = "" if "on_grid" not in notes else f" ({notes['on_grid']} on the grid, {notes['valid']} valid)"
            words = [f"class {run['class']!r}"] if "class" in run else []
            words += [f"stop {run['stop']!r}"] if run["stop"] else []
            words += ["a refusal"] if "refusal" in run else []
            words.append(f"revision {notes['revision']}")
            print(f"{run['id']}: {len(content):,} bytes; {notes['records']} records{flags}; {notes['cells']} cells placed, {notes['junctions']} junctions checked, {notes['events']} events; {'; '.join(words)}")
            if "above_mark_first" in notes:
                disc = "" if "first_equals_disc" not in notes else f" ({'exactly the disc' if notes['first_equals_disc'] else 'NOT the disc'})"
                checked = f"; D counts equal the run's own at {notes['counts_checked']} records" if notes.get("counts_checked") else ""
                print(f"  cells above the D mark: {notes['above_mark_first']} at the first record{disc}, {notes['above_mark_last']} at the last{checked}")
        adapted[experiment] = ({key: value for key, value in entry.items() if key != "adapter"}, listed)

    index, kept = merged_catalogue(out, existing, list(curated), adapted)
    check_clean("index.json", json.dumps(index, ensure_ascii=False))
    (out / "index.json").write_bytes((json.dumps(index, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
    known = {f"{row['id']}.json" for row in index["runs"]} | {Path(part["file"]).name for row in index["runs"] for part in row.get("parts") or []} | {"index.json"}
    stale = sorted(path.name for path in out.glob("*.json") if path.name not in known)
    if stale:
        print(f"note: {len(stale)} other file(s) in the output folder are not in the catalogue and were left in place: {', '.join(stale[:4])}", file=sys.stderr)
    for experiment, (_, listed) in adapted.items():
        print(f"{experiment}: {len(listed)} run(s), {sum(row['bytes'] for row in listed):,} bytes")
    if kept:
        print(f"kept as they were: {', '.join(kept)}")
    print(f"wrote {sum(len(listed) for _, listed in adapted.values())} run(s) and index.json ({len(index['experiments'])} experiment(s), {len(index['runs'])} run(s)) to {out.name}/")


if __name__ == "__main__":
    main()
