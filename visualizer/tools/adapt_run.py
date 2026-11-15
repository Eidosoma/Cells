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
import zipfile
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


def lay_out(name, model, derivation, row=False):
    """The cells and junctions of a definition, placed on the lattice their junctions make.

    With `row`, cells whose junctions make no hexagonal sheet (two cells, a chain, a world
    that is no sheet) are drawn side by side in the definition's order, and the view says so;
    without it such a run is refused.
    """
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
        if not row:
            raise Refused(f"{name}: {error}") from None
        lattice = None
    volumes = [cell["volume_pL"] for cell in model["cells"]]
    volume = sum(volumes) / len(volumes)
    pitch = sphere_diameter_um(volume)
    if lattice is None:
        vertices, faces, _ = hexagons([(index, 0) for index in range(len(cells))], pitch)
        beside = sum(1 for a, b in ends if abs(a - b) == 1)
        derivation.append(
            "Cell positions: the run saves no coordinates, and its junctions do not make a hexagonal sheet. The cells are drawn side by side in the definition's order. "
            f"A junction is drawn only between cells that stand next to each other in that row ({beside} of {len(ends)})."
        )
    else:
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


# ---------------------------------------------------------------- what a definition holds constant
#
# Two of the viewer's derivations read values from a run's definition: the temperature, each
# species' valence, a membrane's capacitance and area, the composition of a held bath
# (schema/QUANTITY_LAYERS.md, rule 1). They may do so only where no operator of that run
# changes the value. The adapter decides that from definition.json alone, by a list of what
# it knows, as KNOWN_CONTROLS does: a model, a law, a key or a control it does not know means
# that nothing is stated as a constant, and a layer that needs one is listed for that run
# with the reason.
#
# What the known replacement law may change is the engine's own contract for it, read in
# src/cells/models/operators/cell_replacement.py on main at 0854c7af (15 November 2026): it
# writes the replaced cells' amounts, resets their channel gates and the gates of their
# junctions, books the held baths' plate charge, and provides each place's route values
# (channel permeability and abundance, leak permeability, pump capacities) with a factor on
# junction availability. Templates are checked against the declared volume of their place
# ("so no other operator may provide a volume") and pump densities are scaled by the declared
# patch area ("so none may provide an area"). It names no capacitance. That reading is why
# the keys below are the whole list; the test itself is on the definition.
KNOWN_TOP_KEYS = {"schema_version", "model", "experiment", "execution", "note"}
KNOWN_MODEL_KEYS = {"id", "temperature_K", "species", "cells", "extracellular", "membranes", "junctions", "faces", "closure", "channels", "junction_heat_booking", "replacement"}
KNOWN_MODELS = {
    # model id: the replacement law, the inner model and the junction formation law it must name (None: no replacement at all)
    "resolved_pump_replacement@1": {"law": "scheduled_cell_replacement@1", "inner_model": "resolved_pump_tissue@3", "junction_formation": "delayed_first_order_junction_formation@1"},
    "resolved_pump_tissue@3": None,
    # The composite over the same inner model, with no operator: an operator is a law of its own, and none is known here yet.
    "resolved_pump_composite@1": None,
}
# The models whose fields the viewer's own table (TISSUE_FIELDS) speaks of.
TISSUE_FAMILY = set(KNOWN_MODELS)
KNOWN_REPLACEMENT_KEYS = {"law", "inner_model", "junction_formation", "templates", "template_capacity"}
KNOWN_TEMPLATE_KEYS = {"id", "volume_pL", "fixed_charge_equivalent_fmol", "amounts_fmol", "channel_gates", "route_values"}
KNOWN_ROUTE_VALUES = {"channel_permeability_m_per_s", "channel_abundance", "membrane_permeability_m_per_s", "pump_capacity_fmol_per_s_m2", "calcium_pump_capacity_fmol_per_s_m2"}
KNOWN_EVENT_KEYS = {"time", "slot", "newcomer", "template", "donor", "carrier_id"}
KNOWN_CONTROL_KEYS = {"schedule", "membrane_id", "junction_id", "pump_id", "channel_id"}
KNOWN_STEP_KEYS = {"time", "availability"}
KNOWN_CELL_KEYS = {"id", "volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol", "initial_charge_C"}
KNOWN_MEMBRANE_KEYS = {"id", "inside", "outside", "area_m2", "capacitance_F", "permeability_m_per_s", "law", "pump", "calcium_pump"}
KNOWN_OUTSIDE_KEYS = {"id", "volume_pL", "initial_amount_fmol", "fixed_charge_equivalent_fmol", "initial_charge_C", "reservoir", "boundary_potential_V"}
CLOSE = dict(rel_tol=1e-9, abs_tol=1e-18)


def is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def unknown(found, known):
    """The first key of a set that the adapter does not know, or None."""
    extra = sorted(set(found) - known)
    return extra[0] if extra else None


def what_may_change(definition):
    """Why the adapter cannot say that this run leaves its definition's values alone, or None when it can.

    None means: the model, its laws and every key and control of the definition are ones the
    adapter knows, and none of them changes a temperature, a valence, a volume, a membrane's
    capacitance or area, or the composition of a held bath. Each test is on the definition.
    """
    if not isinstance(definition, dict):
        return "the run has no definition the adapter can read"
    model, experiment = definition.get("model"), definition.get("experiment")
    if not isinstance(model, dict) or not isinstance(experiment, dict):
        return "the run's definition has no model or no experiment"
    key = unknown(definition, KNOWN_TOP_KEYS)
    if key:
        return f"the run's definition has a part the viewer does not know ({key}), which may change values during the run"
    if model.get("id") not in KNOWN_MODELS:
        return f"the run's model ({model.get('id')}) is not one whose operators the viewer knows"
    if model["id"] == "resolved_pump_composite@1":
        # A composition: its inner model must be the one known, and it may list no operator the viewer does not know (it knows none yet).
        if model.get("inner_model") != "resolved_pump_tissue@3":
            return f"the run's composition is over an inner model the viewer does not know ({model.get('inner_model')})"
        laws = [operator.get("law") if isinstance(operator, dict) else None for operator in model.get("operators") or []]
        if laws:
            return f"the run's composition has an operator whose effect on these values the viewer does not know ({laws[0]})"
    key = unknown(model, KNOWN_MODEL_KEYS | ({"inner_model", "operators"} if model["id"] == "resolved_pump_composite@1" else set()))
    if key:
        return f"the run's model has a part the viewer does not know ({key}), which may change values during the run"
    key = unknown(experiment, KNOWN_CONTROLS)
    if key:
        return f"the run schedules a control the viewer does not know ({key})"
    for control in sorted(set(experiment) & {name for name in KNOWN_CONTROLS if name.endswith("_controls")}):
        for item in experiment[control] or []:
            if not isinstance(item, dict) or unknown(item, KNOWN_CONTROL_KEYS) or any(not isinstance(step, dict) or unknown(step, KNOWN_STEP_KEYS) for step in item.get("schedule") or []):
                return f"a control of the run ({control}) schedules more than an availability"
    for group, known in (("cells", KNOWN_CELL_KEYS), ("membranes", KNOWN_MEMBRANE_KEYS), ("extracellular", KNOWN_OUTSIDE_KEYS)):
        for item in model.get(group) or []:
            key = unknown(item, known) if isinstance(item, dict) else "an entry that is not an object"
            if key:
                return f"the run's definition gives its {group} a value the viewer does not know ({key})"
    wanted, replacement = KNOWN_MODELS[model["id"]], model.get("replacement")
    if wanted is None:
        if replacement is not None or experiment.get("replacement_events"):
            return "the run's model names no replacement law, yet its definition schedules replacements"
        return None
    if not isinstance(replacement, dict):
        return "the run's model replaces cells, and its definition does not say by which law"
    key = unknown(replacement, KNOWN_REPLACEMENT_KEYS)
    if key:
        return f"the run's replacement has a part the viewer does not know ({key})"
    named = {"law": replacement.get("law"), "inner_model": replacement.get("inner_model"), "junction_formation": (replacement.get("junction_formation") or {}).get("law")}
    for part, law in wanted.items():
        if named[part] != law:
            return f"the run replaces cells by a law the viewer does not know ({part.replace('_', ' ')}: {named[part]})"
    volumes = {cell.get("id"): cell.get("volume_pL") for cell in model.get("cells") or [] if isinstance(cell, dict)}
    templates = {}
    for template in replacement.get("templates") or []:
        key = unknown(template, KNOWN_TEMPLATE_KEYS) if isinstance(template, dict) else "an entry that is not an object"
        if not key:
            values = template.get("route_values") or {}
            key = unknown(values, KNOWN_ROUTE_VALUES) if isinstance(values, dict) else "route values that are not an object"
        if key:
            return f"a newcomer's template gives a value the viewer does not know ({key})"
        templates[template.get("id")] = template
    for event in experiment.get("replacement_events") or []:
        key = unknown(event, KNOWN_EVENT_KEYS) if isinstance(event, dict) else "an entry that is not an object"
        if key:
            return f"a replacement gives a value the viewer does not know ({key})"
        if event.get("template") is not None:
            template = templates.get(event["template"])
            if template is None or not is_number(template.get("volume_pL")) or not is_number(volumes.get(event.get("slot"))) or not math.isclose(template["volume_pL"], volumes[event["slot"]], **CLOSE):
                return "a newcomer's template has another volume than the cell it replaces, or names none"
    return None


def membranes_of(definition, sheet):
    """Each membrane's cell and outside node, by index, as the definition lists them; or None.

    Returned as {"ids", "cell", "outside", "nodes"}: the membranes' ids, for each the index of
    its cell in the sheet and of its outside node, and the outside nodes' ids.
    """
    model = definition.get("model") or {}
    membranes, outside = model.get("membranes"), model.get("extracellular")
    if not isinstance(membranes, list) or not isinstance(outside, list) or not membranes or not outside:
        return None
    nodes = [node.get("id") for node in outside if isinstance(node, dict)]
    node_index = {identifier: index for index, identifier in enumerate(nodes)}
    if len(nodes) != len(outside) or len(node_index) != len(nodes) or any(not isinstance(identifier, str) for identifier in nodes):
        return None
    ids, cells, sides = [], [], []
    for membrane in membranes:
        if not isinstance(membrane, dict) or not isinstance(membrane.get("id"), str) or membrane.get("inside") not in sheet.cell_index or membrane.get("outside") not in node_index:
            return None
        ids.append(membrane["id"])
        cells.append(sheet.cell_index[membrane["inside"]])
        sides.append(node_index[membrane["outside"]])
    if len(set(ids)) != len(ids):
        return None
    return {"ids": ids, "cell": cells, "outside": sides, "nodes": nodes}


def one_membrane_each(membranes, sheet):
    """Whether every cell has exactly one membrane, and the membranes stand in the cells' order."""
    return membranes is not None and membranes["cell"] == list(range(len(sheet.cells)))


def definition_constants(definition, sheet, membranes):
    """The values a derivation may read from the definition, as (constants, unstated).

    constants is a list for view.constants; unstated is [{"id", "why"}] for each value the view
    does not state, with the reason in plain words. Every value is the definition's own number.
    """
    ids = ("temperature", "valence", "volume", "extracellular_volume", "membrane_capacitance", "membrane_area", "extracellular_concentration_mM")
    why = what_may_change(definition)
    if why:
        return [], [{"id": identifier, "why": f"Not stated as a constant: {why}."} for identifier in ids]
    model = definition["model"]
    constants, unstated = [], []

    def state(identifier, label, unit, axes, values, says, **extra):
        constants.append({"id": identifier, "label": label, "unit": unit, **extra, "axes": axes, "values": values, "from": "definition.json", "says": says})

    def leave(identifier, reason):
        unstated.append({"id": identifier, "why": f"Not stated as a constant: {reason}."})

    nothing = "Nothing this run schedules changes it: its model, its laws and its controls are ones the viewer knows, and none of them does."
    if is_number(model.get("temperature_K")) and model["temperature_K"] > 0:
        state("temperature", "Temperature", "K", [], float(model["temperature_K"]), f"The model's temperature in the run's definition. {nothing}")
    else:
        leave("temperature", "the run's definition gives no temperature")
    species = [item for item in model.get("species") or [] if isinstance(item, dict)]
    if species and all(isinstance(item.get("id"), str) and isinstance(item.get("valence"), int) and not isinstance(item.get("valence"), bool) for item in species) and len({item["id"] for item in species}) == len(species):
        state("valence", "Valence", "1", ["species"], [item["valence"] for item in species], "Each species' valence in the run's definition.")
    else:
        species = []
        leave("valence", "the run's definition does not list its species with their valences")
    cells = [cell for cell in model.get("cells") or [] if isinstance(cell, dict)]
    if len(cells) == len(sheet.cells) and all(is_number(cell.get("volume_pL")) and cell["volume_pL"] > 0 for cell in cells):
        state(
            "volume", "Cell volume", "pL", ["cell"], [float(cell["volume_pL"]) for cell in cells],
            "Each cell's volume in the run's definition. A replacement keeps the volume of its place: a newcomer's template states that same volume (checked on the definition), and a copy of a donor names none.",
            set="cell",
        )  # fmt: skip
    else:
        leave("volume", "the run's definition does not give every cell a volume")
    outsides = [node for node in model.get("extracellular") or [] if isinstance(node, dict)]
    if outsides and len(outsides) == len(model.get("extracellular") or []) and all(is_number(node.get("volume_pL")) and node["volume_pL"] > 0 for node in outsides):
        state(
            "extracellular_volume", "Volume outside", "pL", ["outside"], [float(node["volume_pL"]) for node in outsides],
            f"Each outside node's volume in the run's definition. {nothing}",
            set="outside",
        )  # fmt: skip
    else:
        leave("extracellular_volume", "the run's definition does not give every outside node a volume")
    listed = model.get("membranes") or []
    if membranes is None:
        if any(constant["id"] == "extracellular_volume" for constant in constants):
            constants[:] = [constant for constant in constants if constant["id"] != "extracellular_volume"]
            leave("extracellular_volume", "the run's definition does not list each membrane with its cell and its outside, so the view lists no outside nodes")
        for identifier in ("membrane_capacitance", "membrane_area", "extracellular_concentration_mM"):
            leave(identifier, "the run's definition does not list each membrane with its cell and its outside")
        return constants, unstated
    kept = "A replacement gives a cell new contents, gates and route strengths: a newcomer's template names no capacitance and no area (checked on the definition), and no control of the run changes one."
    for identifier, label, key, unit in (("membrane_capacitance", "Membrane capacitance", "capacitance_F", "F"), ("membrane_area", "Membrane area", "area_m2", "m2")):
        if all(is_number(membrane.get(key)) and membrane[key] > 0 for membrane in listed):
            state(identifier, label, unit, ["membrane"], [float(membrane[key]) for membrane in listed], f"Each membrane's {label.split()[-1]} in the run's definition. {kept}", set="membrane")
        else:
            leave(identifier, f"the run's definition does not give every membrane its {label.split()[-1]}")
    # The composition outside: only where every membrane's outside is a held bath, whose amounts stay as declared.
    nodes = model.get("extracellular") or []
    faced = sorted(set(membranes["outside"]))
    held = bool(species) and all(
        nodes[index].get("reservoir") is True and is_number(nodes[index].get("volume_pL")) and nodes[index]["volume_pL"] > 0
        and isinstance(nodes[index].get("initial_amount_fmol"), dict) and all(is_number(nodes[index]["initial_amount_fmol"].get(item["id"])) for item in species)
        for index in faced
    )  # fmt: skip
    if held and faced == list(range(len(nodes))):
        values = [[nodes[index]["initial_amount_fmol"][item["id"]] / nodes[index]["volume_pL"] for index in range(len(nodes))] for item in species]
        state(
            "extracellular_concentration_mM", "Concentration outside", "mM", ["species", "outside"], values,
            "Each cell's outside is a held bath: its declared amount of each species over its declared volume (fmol over pL is mM). A held bath keeps its composition, and the run schedules no control of a bath.",
            set="outside",
        )  # fmt: skip
    else:
        leave("extracellular_concentration_mM", "not every membrane's outside is a held bath with a declared composition, and the run did not save the composition outside over time")
    return constants, unstated


# Where the sign of the voltage comes from. It is not one of the signs the owner of the engine's core confirmed
# (TISSUE_SIGN_BY): it is read from each run's own files, and said to be.
VOLTAGE_SIGN_BY = (
    "the viewer's reading of the run's own files, not a declaration by the run: at the first record every cell's saved voltage equals the charge its definition gives the cell, "
    "over the capacitance it gives the cell's membrane"
)


def voltage_sign(saved, definition, sheet, membranes):
    """Which way the saved membrane voltage is positive, as the run's own files show it; or None.

    The run declares no sign. Its definition gives each cell a charge and each membrane a
    capacitance, and where every cell has one membrane to a held bath the first record's voltage
    is that charge over that capacitance. Where this holds for every cell, a positive voltage
    means the inside is positive against the outside; where it does not, nothing is said.
    """
    if not one_membrane_each(membranes, sheet) or saved["t"].values[0] != 0.0:
        return None
    model = definition.get("model") or {}
    cells, listed = model.get("cells") or [], model.get("membranes") or []
    first = saved["vm"].values[: len(sheet.cells)]
    for index, voltage in enumerate(first):
        charge, capacitance = cells[index].get("initial_charge_C"), listed[index].get("capacitance_F")
        if not is_number(charge) or not is_number(capacitance) or capacitance <= 0 or charge == 0 or not math.isclose(voltage, charge / capacitance, rel_tol=1e-9, abs_tol=1e-12):
            return None
    return {
        "says": "a positive voltage means the cell's inside is positive against its outside",
        "high": "inside",
        "by": VOLTAGE_SIGN_BY,
    }


def concentration_species(saved, definition, sheet):
    """The species of each row of the saved concentrations, as the run's own files show them; or None.

    records.npz names no species and no unit. The driver that wrote it takes the first rows of
    the definition's species, each cell's amount over its volume. That is checked here on the
    first record against the definition's own amounts and volumes; where it does not hold, the
    concentrations are left out.
    """
    conc = saved.get("conc")
    model = definition.get("model") or {}
    species, cells = model.get("species") or [], model.get("cells") or []
    width = len(sheet.cells)
    if conc is None or len(conc.shape) != 3 or conc.shape[2] != width or conc.shape[1] > len(species) or len(cells) != width or saved["t"].values[0] != 0.0:
        return None
    names = []
    for row in range(conc.shape[1]):
        identifier = species[row].get("id") if isinstance(species[row], dict) else None
        if not isinstance(identifier, str):
            return None
        for index, cell in enumerate(cells):
            amount, volume = (cell.get("initial_amount_fmol") or {}).get(identifier), cell.get("volume_pL")
            if not is_number(amount) or not is_number(volume) or volume <= 0 or not math.isclose(conc.values[row * width + index], amount / volume, rel_tol=1e-9, abs_tol=1e-12):
                return None
        names.append(identifier)
    return names if len(set(names)) == len(names) else None


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
    definition = definition or {}
    owners = owners_of(definition)
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
    membranes = membranes_of(definition, sheet)
    sign = voltage_sign(saved, definition, sheet, membranes)
    voltage = describe(
        payload, "vm", label_of("vm", "Membrane voltage"), "V", ["time", "cell"], "float32", saved["vm"].shape, array("f", saved["vm"].values),
        set="cell", layer="membrane", marks=d_mark(threshold), kind="level", owner=owners["vm"], sign=sign,
    )  # fmt: skip
    records.append(voltage)
    if one_membrane_each(membranes, sheet):
        # The same numbers, declared over the membranes: no array is added.
        records.append({**{key: value for key, value in voltage.items() if key != "marks"}, "id": "membrane_voltage_V", "set": "membrane", "axes": ["time", "membrane"], "same_as": "vm"})
        derivation.append(
            "The run saved one voltage per cell. Its definition gives every cell exactly one membrane, in the cells' order, so the same numbers are also declared as each membrane's voltage (membrane_voltage_V); no array is added."
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
        + (
            "Which way the membrane voltage is positive is not declared by the run. It is read from the run's own files: at the first record every cell's saved voltage equals the charge "
            "its definition gives the cell, over the capacitance it gives the cell's membrane. So a positive voltage means the inside is positive against the outside; the legend says where this comes from."
            if sign
            else "Which way the membrane voltage is positive is stated by neither, so it is shown as a level and given no direction."
        )
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
    # Each ion's concentration in each cell, where the run saved it: one record and one file per ion.
    try:
        saved["conc"] = read_npz(folder / "records.npz", ["conc"])["conc"]
    except ValueError:
        pass
    if "conc" in saved:
        conc = saved["conc"]
        if len(conc.shape) != 3 or conc.shape[0] != count or conc.shape[2] != len(cells):
            raise Refused(f"{name}: records.npz conc has shape {conc.shape}, expected {(count, 'species', len(cells))}")
        named = concentration_species(saved, definition, sheet)
        if named is None:
            derivation.append(
                "records.npz holds concentrations, but the run's files do not show which species and which unit they are: the first record is not the definition's amounts over its volumes, row by row. They are left out."
            )
        else:
            rows, width, used = conc.shape[1], len(cells), set()
            for row, species in enumerate(named):
                slug = re.sub(r"[^a-z0-9]+", "-", species.lower()).strip("-") or f"row-{row}"
                if slug in used:
                    slug = f"{slug}-{row}"
                used.add(slug)
                own = Payload()
                stored = array("f", (conc.values[(step * rows + row) * width + cell] for step in range(count) for cell in range(width)))
                if not all(math.isfinite(value) and value > 0 for value in stored):
                    raise Refused(f"{name}: a concentration of {species} is not a positive number")
                records.append(
                    describe(
                        own, f"concentration_mM.{species}", f"{species} in the cell", "mM", ["time", "cell"], "float32", (count, width), stored,
                        set="cell", layer="ions", kind="level", owner=owners["vm"], field="concentration_mM", species=species, part=f"concentration-{slug}",
                    )
                )  # fmt: skip
                parts.append({"id": f"concentration-{slug}", "label": f"The concentration of {species} in each cell", "payload": own})
            listed = [item.get("id") for item in (definition.get("model") or {}).get("species") or [] if isinstance(item, dict)]
            unsaved = [identifier for identifier in listed if identifier not in named]
            derivation.append(
                f"Concentrations: records.npz holds {rows} rows per record and names no species and no unit. The driver that wrote it takes the first {rows} species of the definition, "
                f"in its order ({', '.join(named)}), each cell's amount over its volume, in mM. That is checked: at the first record every value equals the definition's own amount over its own volume. "
                "Each ion's concentration is stored as 32-bit numbers in a file of its own beside this one; the run saved 64-bit."
                + (f" The run did not save the concentration of {', '.join(unsaved)}." if unsaved else "")
            )
    return payload, records, saved, parts, membranes


def species_of(definition):
    """The ids of the definition's species, in its order, where it lists them; or None."""
    listed = (definition.get("model") or {}).get("species")
    if not isinstance(listed, list) or not listed or any(not isinstance(item, dict) or not isinstance(item.get("id"), str) for item in listed):
        return None
    ids = [item["id"] for item in listed]
    return ids if len(set(ids)) == len(ids) else None


def quantity_inputs(definition, sheet, membranes, derivation):
    """What the quantity layers need beside the records, as keywords for assemble: the membranes, the species, the constants."""
    species = species_of(definition)
    constants, unstated = definition_constants(definition, sheet, membranes)
    if constants:
        derivation.append(
            f"Named constants ({', '.join(constant['id'] for constant in constants)}) are the definition's own numbers. They are stated because the adapter knows everything the definition can change "
            "(its model, its replacement law, every key of its cells, membranes, outsides, templates and replacements, and every control) and none of it changes them: "
            "a newcomer's template states the volume of the place it takes and names no capacitance and no area, a control schedules an availability only, and every cell's outside is a held bath."
        )
    if unstated and (definition.get("model") or {}).get("membranes"):
        derivation.append(f"Not stated as constants: {', '.join(item['id'] for item in unstated)}. The reason: {unstated[0]['why'].replace('Not stated as a constant: ', '', 1)}")
    return {"membranes": membranes, "species": species, "constants": constants, "unstated": unstated}


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


def assemble(run, layers, stated, sheet, records, regions, events, derivation, parts=(), surroundings=None, membranes=None, species=None, constants=(), unstated=()):
    if any(record.get("layer") == "junctions" for record in records):
        layers = tuple(layers) + (("junctions", "Junction gating"),)
    if any(record.get("layer") == "ions" for record in records):
        layers = tuple(layers) + (("ions", "Ion concentrations"),)
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
    # What a layer on one cell's membrane needs to find its way: which membrane is on which cell and faces which outside.
    if species:
        view["sets"].append({"id": "species", "ids": species})
    if membranes:
        view["sets"].append({"id": "outside", "holds": "outside node", "scale": "cell", "ids": membranes["nodes"]})
        view["sets"].append(
            {"id": "membrane", "scale": "cell", "ids": membranes["ids"], "geometry": {"kind": "on", "set": "cell", "index": membranes["cell"]}, "outside": {"set": "outside", "index": membranes["outside"]}}
        )
    if constants:
        view["constants"] = list(constants)
    if unstated:
        view["unstated"] = list(unstated)
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
    payload, records, saved, parts, membranes = turnover_records(name, folder, sheet, result, threshold, grid, entry, derivation, definition)
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
    view = assemble(run, TURNOVER_LAYERS, stated, sheet, records, regions, events, derivation, parts, surroundings, **quantity_inputs(definition, sheet, membranes, derivation))
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
    payload, records, saved, parts, membranes = turnover_records(name, folder, sheet, result, threshold, grid, entry, derivation, definition)
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
    view = assemble(run, TURNOVER_LAYERS, stated, sheet, records, [disc], events, derivation, parts, surroundings, **quantity_inputs(definition, sheet, membranes, derivation))
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


# ---------------------------------------------------------------- the engine's own output
#
# A run written by the engine's shared output paths (cells.io.write_run and
# cells.window_io.write_windowed_run): resolved_config.json (the definition) beside either
# trajectory.npz, or windows.jsonl with one chunk of arrays for each window. The readouts
# the run observed are saved under the engine's own names, as observed_<field> at
# observation_times; those names are the records' names here.
#
# Where each field lies is the viewer's own table for the tissue family, by field name, until
# the engine's run view declares it (docs/ENGINE_NEEDS_FOR_QUANTITY_LAYERS.md): its axes after
# time, what the page calls it, and the layer of the view it belongs to.
HISTORY_FIELDS = {
    "membrane_voltage_V": (("membrane",), "Membrane voltage", "membrane"),
    "cell_potential_V": (("cell",), "Cell potential", "membrane"),
    "extracellular_potential_V": (("outside",), "Potential outside", "membrane"),
    "junction_voltage_V": (("junction",), "Junction voltage", "junctions"),
    "junction_gate": (("junction",), "Junction gate", "junctions"),
    "amount": (("species", "cell"), "Amount in the cell", "ions"),
    "extracellular_amount": (("species", "outside"), "Amount outside", "ions"),
    "membrane_transferred": (("species", "membrane"), "Carried across the membrane", "transport"),
    "channel_transferred": (("channel",), "Carried through a channel population", "transport"),
    "junction_transferred": (("species", "junction"), "Carried through a junction", "transport"),
    "face_transferred": (("species", "face"), "Carried across a face", "transport"),
    "reservoir_supplied": (("species", "outside"), "Supplied by a reservoir", "transport"),
    "pump_cycles": (("membrane",), "Pump cycles", "transport"),
    "membrane_dissipated_energy_pJ": (("membrane",), "Energy dissipated at the membrane", "energy"),
    "channel_dissipated_energy_pJ": (("channel",), "Energy dissipated in a channel population", "energy"),
    "junction_dissipated_energy_pJ": (("junction",), "Energy dissipated in a junction", "energy"),
    "face_dissipated_energy_pJ": (("face",), "Energy dissipated across a face", "energy"),
    "pump_dissipated_energy_pJ": (("membrane",), "Energy dissipated by a pump", "energy"),
    "metabolic_work_pJ": (("membrane",), "Metabolic work", "energy"),
}
HISTORY_LAYERS = (("membrane", "Voltages"), ("junctions", "Junctions"), ("ions", "Amounts of each species"), ("transport", "Amounts carried"), ("energy", "Energy"))
# What the sheet opens with stays in the run's own file; every other field goes in a file of its own (rule 10).
HISTORY_MAIN = ("membrane_voltage_V", "cell_potential_V")
HISTORY_SETS = {"cell": "cells", "membrane": "membranes", "junction": "junctions", "outside": "extracellular", "face": "faces", "channel": "channels"}
RUN_FOLDER = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\Z")
SIGN_FROM_ARRAYS = "the viewer's reading of the run's own saved arrays, not a declaration by the run"


def npz_names(path):
    """The names of the arrays a .npz file holds, without reading them."""
    with zipfile.ZipFile(path) as archive:
        return [info.filename[:-4] for info in archive.infolist() if info.filename.endswith(".npy")]


def history_arrays(name, folder, derivation):
    """The readouts a run kept, as ({field: (shape, flat values)}, times, how many windows): from trajectory.npz, or from the chunks windows.jsonl lists."""
    wanted = ["observation_times"] + [f"observed_{field}" for field in HISTORY_FIELDS]
    single = folder / "trajectory.npz"
    if single.is_file():
        names = set(npz_names(single))
        if "observation_times" not in names:
            raise Refused(f"{name}: trajectory.npz holds no observation times: the run kept no readouts")
        chunks = [read_npz(single, [item for item in wanted if item in names])]
        derivation.append("Records: the readouts the engine's shared output path wrote at the run's observation times (trajectory.npz, the arrays called observed_...), under the engine's own names.")
    elif (folder / "windows.jsonl").is_file():
        chunks = []
        for line in (folder / "windows.jsonl").read_text(encoding="utf-8").splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                raise Refused(f"{name}: windows.jsonl has a line that is not JSON") from None
            if not (isinstance(item, dict) and item.get("kind") == "window" and item.get("observation_records") and isinstance(item.get("path"), str)):
                continue
            if not RUN_FOLDER.match(item["path"]) or not (folder / item["path"]).is_file():
                raise Refused(f"{name}: windows.jsonl names a chunk that is not in the run's folder")
            names = set(npz_names(folder / item["path"]))
            chunks.append(read_npz(folder / item["path"], [entry for entry in wanted if entry in names]))
        if not chunks:
            raise Refused(f"{name}: no window of the run kept its readouts")
        derivation.append(f"Records: the readouts the engine's windowed output path wrote at the run's observation times, put end to end from its {len(chunks)} window file(s) in the order windows.jsonl lists them, under the engine's own names.")
    else:
        raise Refused(f"{name}: neither trajectory.npz nor windows.jsonl is in the run's folder")
    times, fields = [], {}
    kept = set(chunks[0]) - {"observation_times"}
    for chunk in chunks:
        kept &= set(chunk)
    dropped = 0
    for chunk in chunks:
        count = chunk["observation_times"].shape[0]
        for row in range(count):
            time = chunk["observation_times"].values[row]
            if times and time == times[-1]:
                dropped += 1  # a record at a window's first time repeats the one at the last window's end
                continue
            times.append(time)
            for key in kept:
                shape = chunk[key].shape
                width = 1
                for size in shape[1:]:
                    width *= size
                if shape[0] != count:
                    raise Refused(f"{name}: {key} has {shape[0]} rows for {count} observation times")
                entry = fields.setdefault(key[len("observed_"):], [shape[1:], array("d")])
                if tuple(entry[0]) != tuple(shape[1:]):
                    raise Refused(f"{name}: {key} changes its shape between windows")
                entry[1].extend(chunk[key].values[row * width : (row + 1) * width])
    if dropped:
        derivation.append(f"{dropped} record(s) at the first time of a window repeat the record at the end of the window before, and are left out.")
    increasing(name, times)
    return fields, times, len(chunks)


def tissue_of(config):
    """The part of a definition that lists the tissue (cells, membranes, junctions, outsides): the model itself, or the ionic part of a larger one."""
    model = config.get("model") if isinstance(config, dict) else None
    for candidate in (model, (model or {}).get("ionic") if isinstance(model, dict) else None):
        if isinstance(candidate, dict) and all(isinstance(candidate.get(key), list) for key in ("cells", "membranes", "junctions", "extracellular")):
            return candidate
    return None


def adapt_history(root, name, experiment, entry):
    """One run written by the engine's shared output path (a folder that holds resolved_config.json and its arrays)."""
    if not RUN_FOLDER.match(name):
        raise Refused(f"'{name}' is not a run folder's name")
    folder = root / name
    if not folder.is_dir():
        raise Refused(f"no run folder {name} in {root.name}/")
    config = read_json(folder / "resolved_config.json")
    tissue = tissue_of(config)
    if tissue is None:
        raise Refused(f"{name}: its definition lists no cells, membranes, junctions and outside nodes the adapter can read")
    model_id = (config.get("model") or {}).get("id")
    family = model_id in TISSUE_FAMILY
    derivation = []
    sheet = lay_out(name, tissue, derivation, row=True)
    fields, times, windows = history_arrays(name, folder, derivation)
    count = len(times)
    # The definition as the constants and the surroundings are read from: the tissue with the run's own experiment.
    definition = config if tissue is config.get("model") else {"model": tissue, "experiment": config.get("experiment") or {}}
    membranes = membranes_of(definition, sheet)
    species = species_of(definition) or []
    index_of = {key: {item.get("id"): number for number, item in enumerate(tissue.get(HISTORY_SETS[key]) or []) if isinstance(item, dict)} for key in HISTORY_SETS}
    sizes = {key: len(tissue.get(listed) or []) for key, listed in HISTORY_SETS.items()}
    sizes["species"] = len(species)

    def rows(field):
        """A field's values as {species or None: flat values over (time, the first n entities)}, with its set; or None when it is not there or does not fit."""
        if field not in fields:
            return None
        axes, (shape, values) = HISTORY_FIELDS[field][0], fields[field]
        shape = tuple(shape)
        # A channel population's total may be kept for each species or as one number: its shape says which.
        if field == "channel_transferred" and len(shape) == 2:
            axes = ("species", "channel")
        if len(shape) != len(axes) or any(shape[k] < sizes[axis] for k, axis in enumerate(axes)) or (axes[0] == "species" and shape[0] != sizes["species"]) or not sizes[axes[-1]]:
            return None
        entity, width, n = axes[-1], shape[-1], sizes[axes[-1]]
        per = len(values) // count
        if axes[0] == "species":
            out = {name_: array("f", (values[step * per + row * width + k] for step in range(count) for k in range(n))) for row, name_ in enumerate(species)}
        else:
            out = {None: array("f", (values[step * per + k] for step in range(count) for k in range(n)))}
        return entity, n, out

    payload, records, parts, used_layers = Payload(), [], [], set()
    records.append(describe(payload, "t", "Time", "s", ["time"], "float32", (count,), array("f", times)))
    owner = model_id if isinstance(model_id, str) else None
    signs = {}
    # Which way the voltages are positive is checked on the saved arrays themselves, wherever they allow it.
    voltage, inner, outer = fields.get("membrane_voltage_V"), fields.get("cell_potential_V"), fields.get("extracellular_potential_V")
    if membranes and voltage and inner and outer and all(tuple(item[0])[0] >= size for item, size in ((voltage, sizes["membrane"]), (inner, sizes["cell"]), (outer, sizes["outside"]))):
        widths = [tuple(item[0])[0] for item in (voltage, inner, outer)]
        # The reading holds at every record, and at least one voltage is not nought: one that is nought everywhere shows no sign.
        if all(
            math.isclose(voltage[1][step * widths[0] + m], inner[1][step * widths[1] + membranes["cell"][m]] - outer[1][step * widths[2] + membranes["outside"][m]], rel_tol=1e-9, abs_tol=1e-12)
            for step in range(count) for m in range(sizes["membrane"])
        ) and any(abs(voltage[1][step * widths[0] + m]) > 1e-9 for step in range(count) for m in range(sizes["membrane"])):  # fmt: skip
            signs["membrane_voltage_V"] = {"says": "a positive voltage means the cell's inside is at a higher potential than its outside", "high": "inside", "by": f"{SIGN_FROM_ARRAYS}: at every record each membrane's saved voltage equals the saved potential of its cell less that of the outside node it faces"}
    across = fields.get("junction_voltage_V")
    if across and inner and sizes["junction"] and tuple(across[0])[0] >= sizes["junction"]:
        wide, cells_wide = tuple(across[0])[0], tuple(inner[0])[0]
        if all(
            math.isclose(across[1][step * wide + j], inner[1][step * cells_wide + sheet.ends[j][0]] - inner[1][step * cells_wide + sheet.ends[j][1]], rel_tol=1e-9, abs_tol=1e-12)
            for step in range(count) for j in range(sizes["junction"])
        ) and any(abs(across[1][step * wide + j]) > 1e-9 for step in range(count) for j in range(sizes["junction"])):  # fmt: skip
            signs["junction_voltage_V"] = {"says": "a positive voltage means the junction's first cell, its sender, is at the higher potential", "high": "first", "by": f"{SIGN_FROM_ARRAYS}: at every record each junction's saved voltage equals the saved potential of its sender less that of its receiver"}

    def declare(target, field, entity, n, values, species_id=None, part=None):
        table = tissue_field(field) if family else None
        unit = (table or {}).get("unit") or ("V" if field.endswith("_V") else "pJ" if field.endswith("_pJ") else "")
        sign = signs.get(field) or (table or {}).get("sign")
        label = HISTORY_FIELDS[field][1] if species_id is None else f"{HISTORY_FIELDS[field][1]}: {species_id}"
        layer = HISTORY_FIELDS[field][2]
        used_layers.add(layer)
        extra = {"field": field, "species": species_id} if species_id is not None else {}
        return describe(
            target, field if species_id is None else f"{field}.{species_id}", label, unit, ["time", entity], "float32", (count, n), values,
            set=entity, layer=layer, kind=(table or {}).get("kind"), owner=owner, sign=sign, part=part, **extra,
        )  # fmt: skip

    left_out, empty = [], []
    for field in HISTORY_FIELDS:
        found = rows(field)
        if found is None:
            if field in fields:
                (empty if not sizes[HISTORY_FIELDS[field][0][-1]] else left_out).append(field)
            continue
        entity, n, values = found
        if field in HISTORY_MAIN:
            records.append(declare(payload, field, entity, n, values[None]))
            continue
        slug = re.sub(r"[^a-z0-9]+", "-", field.lower()).strip("-")
        # One file for the field where it fits under the size limit; one for each species where it does not.
        together = sum(len(item) * 4 for item in values.values()) * 4 / 3 < LIMIT_BYTES * 0.92
        own = Payload()
        for species_id, item in values.items():
            part = slug if together or species_id is None else f"{slug}-{re.sub(r'[^a-z0-9]+', '-', species_id.lower()).strip('-')}"
            if not together and species_id is not None:
                own = Payload()
            records.append(declare(own, field, entity, n, item, species_id, part))
            if not together and species_id is not None:
                parts.append({"id": part, "label": f"{HISTORY_FIELDS[field][1]}: {species_id}", "payload": own})
        if together or None in values:
            parts.append({"id": slug, "label": HISTORY_FIELDS[field][1], "payload": own})
    if not any(record.get("set") == "cell" for record in records):
        raise Refused(f"{name}: the run kept no readout over its cells that the sheet could be coloured by")
    # Where every cell has one membrane, in the cells' order, the membranes' voltage is also each cell's: the same array, declared over the cells.
    own_voltage = next((record for record in records if record["id"] == "membrane_voltage_V"), None)
    if own_voltage and one_membrane_each(membranes, sheet):
        records.insert(records.index(own_voltage) + 1, {**own_voltage, "id": "vm", "set": "cell", "axes": ["time", "cell"], "same_as": "membrane_voltage_V"})
        derivation.append("The run's definition gives every cell exactly one membrane, in the cells' order, so each membrane's saved voltage is also declared as its cell's (vm); no array is added.")
    elif own_voltage:
        derivation.append("A cell of this run has several membranes, or none: no voltage is declared for a cell, and none is averaged. The sheet is coloured by a record the run kept for each cell.")
    if left_out:
        derivation.append(f"Left out, because their arrays do not have the shape the adapter knows for them: {', '.join(left_out)}.")
    if empty:
        places = sorted({HISTORY_FIELDS[field][0][-1] for field in empty})
        derivation.append(f"The run has no {' and no '.join(HISTORY_SETS[place] for place in places)}, so the fields that lie on them are empty and are not packaged: {', '.join(empty)}.")
    derivation.append("Times and values are stored as 32-bit numbers; the run saved 64-bit. Every field but the two the sheet opens with is in a file of its own beside this one.")
    derivation.append(
        "Which entity each column is: the arrays name none. Columns are taken in the order of the run's definition (its cells, membranes, junctions, outside nodes, faces and channel populations), "
        "and only as many as the definition lists: an array made for more places than the run uses is cut there."
    )
    if family:
        derivation.append(
            "What kind of number each record is, its unit and, for the amounts carried, which way is positive come from the viewer's own table for this family of models; "
            "the signs in it are the engine's convention as the owner of its core confirmed it on 15 November 2026. The run's files declare none of these."
        )
    else:
        derivation.append(f"The run's model ({model_id}) is not of the family the viewer's table speaks of: no kind and no sign is given for its records, and a unit only where the field's name ends in one.")
    for field, sign in signs.items():
        derivation.append(f"Which way {HISTORY_FIELDS[field][1].lower()} is positive is not declared by the run. It is read from its arrays: {sign['by'].split(': ', 1)[1]}.")
    stated = layers_stated(entry, derivation)
    summary = read_json(folder / "summary.json") if (folder / "summary.json").is_file() else {}
    plan = {"execution": config.get("execution") or {}, "model": {key: value for key, value in (config.get("model") or {}).items() if not isinstance(value, (list, dict))}}
    parameters, readouts = copied(entry, plan, summary if isinstance(summary, dict) else {}, {})
    derivation.append("Parameters are copied under their own names from resolved_config.json (execution and the model's plain values) and readouts from summary.json. The run's files name no revision of the engine by its commit, so none is given.")
    models = [model_id] if isinstance(model_id, str) else []
    composed = config.get("model") or {}
    if isinstance(composed.get("inner_model"), str):
        models += [composed["inner_model"], *[operator.get("law") for operator in composed.get("operators") or [] if isinstance(operator, dict) and isinstance(operator.get("law"), str)]]
    arm = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    run = run_facts(
        experiment, arm, None, label=None, group=None, engine_models=models, revision=None, end_s=times[-1],
        stop=summary.get("status") if isinstance(summary, dict) and isinstance(summary.get("status"), str) else None, parameters=parameters, readouts=readouts,
    )  # fmt: skip
    surroundings = surroundings_of(definition)
    if surroundings:
        derivation.append("That every cell's surroundings share one potential is read from the definition: each membrane's outside is a held bath (a reservoir), all at one boundary potential, and the experiment schedules no control of a bath.")
    inputs = quantity_inputs(definition, sheet, membranes, derivation)
    layers = tuple(item for item in HISTORY_LAYERS if item[0] in used_layers)
    view = assemble(run, layers, stated, sheet, records, [], [], derivation, parts, surroundings, **inputs)
    # The faces between outside nodes and the channel populations on membranes, where the definition lists them.
    faces = [face for face in tissue.get("faces") or [] if isinstance(face, dict)]
    if membranes and faces and all(face.get("sender") in index_of["outside"] and face.get("receiver") in index_of["outside"] and isinstance(face.get("id"), str) for face in faces):
        view["sets"].append({"id": "face", "holds": "face", "scale": "cell", "ids": [face["id"] for face in faces], "geometry": {"kind": "links", "between": "outside", "ends": [[index_of["outside"][face["sender"]], index_of["outside"][face["receiver"]]] for face in faces]}})
    channels = [channel for channel in tissue.get("channels") or [] if isinstance(channel, dict)]
    if membranes and channels and all(channel.get("membrane_id") in index_of["membrane"] and isinstance(channel.get("id"), str) for channel in channels):
        view["sets"].append({"id": "channel", "holds": "channel population", "scale": "cell", "ids": [channel["id"] for channel in channels], "geometry": {"kind": "on", "set": "membrane", "index": [index_of["membrane"][channel["membrane_id"]] for channel in channels]}})
    listed = {item["id"] for item in view["sets"]}
    missing = sorted({record["set"] for record in records if record.get("set")} - listed)
    if missing:
        raise Refused(f"{name}: records lie on {', '.join(missing)}, which the definition does not list in a form the adapter can read")
    notes = {"records": count, "cells": len(sheet.cells), "junctions": len(sheet.junctions), "events": 0, "revision": None, "pitch_um": sheet.pitch, "windows": windows}
    notes["parts"] = {part["id"]: part["payload"].data() for part in parts}
    return view, payload.data(), notes


ADAPTERS = {"e07-v1": adapt_e07_v1, "heredity-turnover-literature": adapt_turnover_literature, "heredity-pilot-w1": adapt_pilot_w1, "standard-history": adapt_history}


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
