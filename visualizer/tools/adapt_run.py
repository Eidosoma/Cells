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
    # The engine's own run view notes of this field that it holds the passive membrane routes only.
    "membrane_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _OUT, "note": "the passive membrane routes only: what each channel population and each pump carried is its own ledger (as the engine's run view notes of this field)"},
    "channel_transferred": {"kind": "cumulative", "unit": "fmol", "sign": dict(_OUT, says="a positive amount has left the channel's cell for its outside, as for its membrane")},
    "junction_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _ALONG},
    "face_transferred": {"kind": "cumulative", "unit": "fmol", "sign": _ALONG},
    "pump_cycles": {"kind": "cumulative", "unit": "fmol", "sign": {"says": "positive cycles carry their ions into the cell: the stoichiometry times the cycles is taken from the membrane's total", "from": "outside node", "to": "cell", "by": TISSUE_SIGN_BY}},
    "reservoir_supplied": {"kind": "cumulative", "unit": "fmol", "sign": {"says": "a positive amount has entered the outside node from its reservoir", "by": TISSUE_SIGN_BY}},
    "metabolic_work_pJ": {"kind": "cumulative", "unit": "pJ"},
}
for _part in ("membrane", "channel", "junction", "face", "pump"):
    TISSUE_FIELDS[f"{_part}_dissipated_energy_pJ"] = {"kind": "cumulative", "unit": "pJ", "monotone": "non-decreasing"}


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
    # A layer the caller already lists is not listed again.
    if any(record.get("layer") == "junctions" for record in records) and all(layer != "junctions" for layer, _ in layers):
        layers = tuple(layers) + (("junctions", "Junction gating"),)
    if any(record.get("layer") == "ions" for record in records) and all(layer != "ions" for layer, _ in layers):
        layers = tuple(layers) + (("ions", "Ion concentrations"),)
    view = {
        "format": VIEW_FORMAT,
        "derived": True,
        "derivation": derivation,
        "run": run,
        "time": {"unit": "s", "record": "t"},
        # `placed`: the cells stand where the run's view prescribes them (a small network, not a sheet): the page draws each junction between its two cells.
        "space": {"unit": "um", "dimensions": 2, **({"placed": "prescribed"} if getattr(sheet, "prescribed", False) else {})},
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
# A run written by the engine's shared output paths (cells.records.io.write_run and
# cells.records.window_io.write_windowed_run; cells.io and cells.window_io before the engine's
# second source move, D188: the five worlds its writer wrote before and after it are the same files):
# resolved_config.json (the definition) beside either
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
    # A passive route's total (cells.passive_routes@1): what one route carried since the start, for each species, positive the way its sign says.
    "passive_transferred": (("species", "passive_route"), "Carried along a passive route", "transport"),
    "face_transferred": (("species", "face"), "Carried across a face", "transport"),
    "reservoir_supplied": (("species", "outside"), "Supplied by a reservoir", "transport"),
    "pump_cycles": (("membrane",), "Pump cycles", "transport"),
    "membrane_dissipated_energy_pJ": (("membrane",), "Energy dissipated at the membrane", "energy"),
    "channel_dissipated_energy_pJ": (("channel",), "Energy dissipated in a channel population", "energy"),
    "junction_dissipated_energy_pJ": (("junction",), "Energy dissipated in a junction", "energy"),
    "face_dissipated_energy_pJ": (("face",), "Energy dissipated across a face", "energy"),
    "pump_dissipated_energy_pJ": (("membrane",), "Energy dissipated by a pump", "energy"),
    "metabolic_work_pJ": (("membrane",), "Metabolic work", "energy"),
    # The ledgers of the operators that make and clear a secreted species (scheduled_species_turnover@1): totals since the start.
    "turnover_produced_fmol": (("species", "cell"), "Made in the cell", "turnover"),
    "turnover_cleared_fmol": (("species", "cell"), "Cleared in the cell", "turnover"),
    "turnover_outside_cleared_fmol": (("species", "outside"), "Cleared outside", "turnover"),
    # The ledger of the operator that carries a species across a membrane by declared routes (scheduled_species_exchange@1): one total for each route.
    "exchange_moved_fmol": (("route",), "Moved by an exchange route", "turnover"),
}
HISTORY_LAYERS = (("membrane", "Voltages"), ("junctions", "Junctions"), ("ions", "Amounts of each species"), ("transport", "Amounts carried"), ("energy", "Energy"), ("turnover", "Made and cleared"))
# The operators whose declarations name the species they secrete, make or clear: those species are the run's secreted ones.
SECRETION_LAWS = {"scheduled_species_turnover@1", "scheduled_species_exchange@1"}
# The operator whose routes carry a species across a membrane: each route names its membrane (its patch) and its species.
EXCHANGE_LAWS = {"scheduled_species_exchange@1"}
PLACE_WORDS = {"route": "exchange routes"}
EXAMPLE_FILE = "example.json"  # the run-fixture tool writes it into a run folder whose numbers it invented
# What the sheet opens with stays in the run's own file; every other field goes in a file of its own (rule 10).
HISTORY_MAIN = ("membrane_voltage_V", "cell_potential_V")
HISTORY_SETS = {"cell": "cells", "membrane": "membranes", "junction": "junctions", "outside": "extracellular", "face": "faces", "channel": "channels"}
RUN_FOLDER = re.compile(r"[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*\Z")
SIGN_FROM_ARRAYS = "the viewer's reading of the run's own saved arrays, not a declaration by the run"
# An exchange route's total (scheduled_species_exchange@1) is positive out of the cell, for an export and an import route alike: the
# engine's lead confirmed it on 15 November 2026 from the operator's own code, whose domain check holds an export's total at nought
# or more and an import's at nought or less. The run's files do not declare it, so it is given only where the run's own amounts agree.
EXCHANGE_SIGN_BY = "the engine's own convention for this operator, confirmed by the engine's lead on 15 November 2026 and not yet declared in the run's view"
OTHER_READINGS = (("in", "the other way round"), ("declared", "along each route's declared direction"))


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


def world_layout(tissue, sheet, membranes, derivation):
    """One tile for each cell and each outside node, touching where a junction, a membrane or a face joins them; or None.

    The run saves no positions. Where the places of a small world and what joins them fit a
    hexagonal lattice (one cell, the node it secretes into and the bath: three tiles round one
    corner), each is given a tile; the cells' tiles and the outside nodes' share one list of
    corners, so that the viewer finds the edge two of them share. Where they do not fit (a
    sheet whose every cell has a bath of its own), the outside nodes are given no place, and
    the cells stay as they were laid out.
    """
    if not membranes or not membranes["nodes"]:
        return None
    cells, nodes = len(sheet.cells), len(membranes["nodes"])
    node_index = {identifier: index for index, identifier in enumerate(membranes["nodes"])}
    edges = {tuple(sorted(pair)) for pair in sheet.ends}
    edges |= {(cell, cells + outside) for cell, outside in zip(membranes["cell"], membranes["outside"])}
    for face in tissue.get("faces") or []:
        if not isinstance(face, dict) or face.get("sender") not in node_index or face.get("receiver") not in node_index:
            return None
        edges.add(tuple(sorted((cells + node_index[face["sender"]], cells + node_index[face["receiver"]]))))
    try:
        lattice = embed(cells + nodes, sorted(edges))
    except LayoutError:
        derivation.append(
            "The outside nodes are not drawn: the run saves no positions, and its cells and outside nodes cannot be laid out as tiles that touch wherever a membrane or a face joins two of them."
        )
        return None
    vertices, faces, _ = hexagons(lattice, sheet.pitch)
    derivation.append(
        "Where the outside nodes stand: the run saves no positions. Each cell and each outside node is drawn as one tile, and two tiles touch where a junction, a membrane or a face joins them. "
        "That layout is the viewer's own; an outside node's tile says nothing of its shape or its size."
    )
    return SimpleNamespace(vertices=vertices, cells=faces[:cells], outside=faces[cells:])


def exchange_sign(fields, count, species, sheet, membranes, routes):
    """Which way an exchange route's saved total is positive: the engine's convention, where the run's own arrays agree; or None.

    The run's files declare no direction for it. The engine's convention is that a positive total has left the route's
    cell for its outside, whatever the route's declared direction (EXCHANGE_SIGN_BY). It is given only where the run's own
    amounts agree. Three readings are tried, on every cell that has a route and at every record: a positive total has left
    the route's cell for its outside; it has entered the cell; it has gone the way the route's own declaration names
    (export or import). A reading holds where the amount of the route's species in the cell is its amount at the start,
    plus what was made there, less what was cleared there, what crossed the cell's membranes and junctions, and the
    routes' totals read that way. The sign is given only where the first reading holds at every record and each other
    reading fails at some record. Whatever else moved the species (a pump, a ledger the run did not keep) leaves the
    amounts not adding up, and then no sign is given.
    """
    if not (routes and membranes and "amount" in fields and "exchange_moved_fmol" in fields):
        return None

    def at(field, step, *where):
        if field not in fields:
            return 0.0
        shape, values = tuple(fields[field][0]), fields[field][1]
        per = 1
        for size in shape:
            per *= size
        offset = 0
        for size, k in zip(shape, where):
            offset = offset * size + k
        return values[step * per + offset]

    readings = {
        "out": [1.0] * len(routes),
        "in": [-1.0] * len(routes),
        "declared": [-1.0 if route.get("direction") == "import" else 1.0 for route in routes],
    }
    patch = [membranes["ids"].index(route["patch"]) for route in routes]
    pairs = sorted({(membranes["cell"][patch[r]], species.index(route["species"])) for r, route in enumerate(routes)})
    scale = max((abs(at("amount", step, row, cell)) for cell, row in pairs for step in range(count)), default=0.0)
    holds = {name: True for name in readings}
    moved = False
    for cell, row in pairs:
        own = [m for m in range(len(membranes["ids"])) if membranes["cell"][m] == cell]
        through = [r for r, route in enumerate(routes) if membranes["cell"][patch[r]] == cell and species.index(route["species"]) == row]
        for step in range(count):
            change = at("amount", step, row, cell) - at("amount", 0, row, cell)
            others = at("turnover_produced_fmol", step, row, cell) - at("turnover_cleared_fmol", step, row, cell) - sum(at("membrane_transferred", step, row, m) for m in own)
            for j, (sender, receiver) in enumerate(sheet.ends):
                others += (-1.0 if sender == cell else 1.0 if receiver == cell else 0.0) * at("junction_transferred", step, row, j)
            moved = moved or any(at("exchange_moved_fmol", step, r) != 0.0 for r in through)
            for name, ways in readings.items():
                if not math.isclose(change, others - sum(ways[r] * at("exchange_moved_fmol", step, r) for r in through), rel_tol=1e-9, abs_tol=1e-9 * scale + 1e-30):
                    holds[name] = False
    # A reading that is the same as the first for this run (no route is an import) cannot be told from it, and need not fail.
    others_fail = all(not holds[name] for name in ("in", "declared") if readings[name] != readings["out"])
    if not (moved and holds["out"] and others_fail):
        return None
    return {
        "says": "a positive amount has left the route's cell for the outside its membrane faces",
        "from": "cell",
        "to": "outside node",
        "by": (
            f"{EXCHANGE_SIGN_BY}. The run's own saved amounts agree with it: at every record the amount of the route's species in its cell is the amount at the start, "
            "plus what was made there, less what was cleared there, what crossed the cell's membranes and the routes' totals. "
            f"Read {' or '.join(words for name, words in OTHER_READINGS if readings[name] != readings['out'])}, the amounts do not add up"
        ),
    }


def tissue_of(config):
    """The part of a definition that lists the tissue (cells, membranes, junctions, outsides): the model itself, or the ionic part of a larger one."""
    model = config.get("model") if isinstance(config, dict) else None
    for candidate in (model, (model or {}).get("ionic") if isinstance(model, dict) else None):
        if isinstance(candidate, dict) and all(isinstance(candidate.get(key), list) for key in ("cells", "membranes", "junctions", "extracellular")):
            return candidate
    return None


# ---------------------------------------------------------------- a run with the engine's own view
#
# The engine's run-view writer (cells.run_view@1) puts one view.json beside a run's files: every
# set, unit, time base, layer, owner, kind and sign, as the engine itself declares them. Where a
# run folder holds one, the run is packaged from it and from nothing else: none of the tables
# above is used, and nothing is read out of the arrays' values (no sign of a voltage, no
# direction of an operator's total, no "total since the start"). What the view does not state
# stays unstated, with the view's own reason, and a layer that needs it says so.
VIEW_FILE = "view.json"
VIEW_KEYS = {"format", "run", "time", "space", "layers", "sets", "records", "events", "constants", "unstated", "recording"}
# What the page calls a field. The engine's view gives a record no label: names are the viewer's own catalogue, and
# a field the catalogue does not name is not packaged for the page.
FIELD_LABELS = {field: label for field, (_, label, _) in HISTORY_FIELDS.items()}
TIME_CLOSE = dict(rel_tol=1e-9, abs_tol=1e-12)
# The writer's additions of 16 November 2026 (made on the development branch run-view-d154, on main since 050aa741;
# docs/RUN_VIEW_DESIGN.md §9). Each is read only
# where the view gives its key, so that a view of the 15 November shape is packaged exactly as before.
#
# A set's roles the page has a word for, as the end of a difference that is the higher when the value is positive: the
# page's `high` (src/replay/run.js, SIGN_HIGH). The word is read from the role's name, as the page reads a sign's `from`
# (src/layers/records.js, FROM_FIRST): a junction's or a face's sender is a link's first end, its receiver the second.
HIGH_WORDS = {"inside": "inside", "outside": "outside", "sender": "first", "receiver": "second"}
# What an operator's set may state of each of its entities, one value for each id (the writer's PER_ENTITY): the species
# each carries, a word each (its declared direction, its kind) and the entity each acts at ({set id: entity id}).
PER_ENTITY = ("carries", "direction", "kinds", "at")
# Door S's merged views (view_<field>, one for each observed row) that a layer of the page reads by the field's name,
# with what the page calls each. The others are not packaged, and the derivation names them.
VIEW_PREFIX = "view_"
VIEW_FIELD_LABELS = {"volume": "Cell volume", "extracellular_volume": "Volume outside", "membrane_area": "Membrane area", "membrane_capacitance": "Membrane capacitance"}
# The loop block: as designed (schema/RUN_VIEW.md, view.loop), and as the writer builds it from d7a11d5b on, with the
# records its closure leaves out by reason (not_measured) and those identically zero over the loop (closes.zero).
LOOP_KEYS = {"species", "cell_type", "cell", "period", "closes", "not_measured", "follows"}
# A level the page reads that the engine may store as an increment over a fixed reference (its RECORD_REFERENCES, from
# b08af640 on, the writer on main since 050aa741, 16 November 2026): where the run saved no record of the level itself,
# the level is the view's named reference plus the increment, worked out here and said to be.
INCREMENT_OF = {"amount": "amount_increment", "extracellular_amount": "extracellular_amount_increment"}
# The operators whose ledgers among the page's fields (HISTORY_FIELDS) are their own; every other field there is the
# inner model's. And the view's set for the page's name of a set where the two differ.
FIELD_OPERATORS = {
    "turnover_produced_fmol": "scheduled_species_turnover@1",
    "turnover_cleared_fmol": "scheduled_species_turnover@1",
    "turnover_outside_cleared_fmol": "scheduled_species_turnover@1",
    "exchange_moved_fmol": "scheduled_species_exchange@1",
}
FIELD_SETS = {"route": "exchange_route"}
CLOSES_KEYS = {"within", "tolerance", "says", "zero"}
# The core seams pass's three format items and its addition (docs/CORE_SEAMS_DESIGN.md §9 and §4.3 at the engine's
# revision 89bd2ffb; the writer on main from d64fb664, 18 November 2026). The format keeps its name, cells.run_view@1, and
# the saved views behind published replays are not written again (the engine's lead, 19 November 2026), so a view of
# either shape is read, and each item is read only where a view gives it:
# - kinds are words, and a law's ID goes under `laws`: an older view's kind that holds a law's ID is carried as written;
#   where a set that states facts of its entities gives `laws`, the derivation names each entity's law beside its kind;
# - each species a route carries moves with its own flux, not as a coupled set: an entity that lists several species is
#   said so; coupled stoichiometry is only a stated `per_cycle` (a membrane's pump, carried in `pumps`; a cycle kind's
#   set, named and not packaged);
# - a reference over a field the run did not save ({"field": X}) stands only with X's entry under `unstated`;
# - a channel set's `factors` (the routing door into @3) are named, with the note on channel_availability, and not packaged.
# Every key the adapter knows of the view's objects: read where the page uses it, or passed over on purpose (a set's
# members, the parts of the field nodes, the pumps' layout word, the species' identities, a run's fingerprint). A key
# beyond them is found and named in the derivation, never refused and never passed over unsaid.
VIEW_TOP_KEYS = VIEW_KEYS | {"loop"}
KNOWN_VIEW_KEYS = {
    "run": {"id", "label", "experiment", "arm", "seed", "revision", "engine_models", "composition", "definition_sha256", "end", "source", "model", "scale"},
    "time": {"unit", "bases", "event_rows"},
    "base": {"id", "array", "says", "files"},
    "space": {"unit", "dimensions", "representation", "source"},
    "layer": {"id", "label", "owner", "representation"},
    "constant": {"id", "unit", "axes", "values", "from", "says"},
    "unstated": {"id", "what", "why"},
    "recording": {"mode", "subset"},
    "event": {"time", "kind", "layer", "at", "from", "label"},
    "record": {"id", "field", "array", "base", "axes", "set", "unit", "layer", "owner", "kind", "sign", "difference", "monotone", "resets", "note", "writers", "diagnostic", "reference"},
    "set": {"id", "ids", "scale", "holds", "owner", "says", "geometry", "roles", "lifetimes", "laws", "reservoir", "outside", "pumps", "calcium_pumps", "pumps_are", "members", "composed_of", "species", "valence", "recorded", *PER_ENTITY},
}
# Said in sentences of their own: the channel set's factors, and a cycle kind's coupled stoichiometry on a set of its own.
OWN_WORDS_KEYS = {"factors", "per_cycle"}


def finite(value):
    return is_number(value) and math.isfinite(value)


def unread_keys(view):
    """What a view gives that the adapter does not know (KNOWN_VIEW_KEYS), as phrases "where: key, key": the view's top,
    its run, time, time bases, space, recording, each set by its id, and its layers, records, constants, unstated items
    and events. The channel set's factors and a set's per_cycle are said in sentences of their own (OWN_WORDS_KEYS)."""
    said = []

    def note(where, found, known):
        extra = sorted(set(found) - known) if isinstance(found, dict) else []
        if extra:
            said.append(f"{where}: {', '.join(extra)}")

    note("the view", view, VIEW_TOP_KEYS)
    note("its run", view.get("run"), KNOWN_VIEW_KEYS["run"])
    time = view.get("time")
    note("its time", time, KNOWN_VIEW_KEYS["time"])
    for base in (time.get("bases") or []) if isinstance(time, dict) else []:
        note(f"its time base {base.get('id') if isinstance(base, dict) else base}", base, KNOWN_VIEW_KEYS["base"])
    note("its space", view.get("space"), KNOWN_VIEW_KEYS["space"])
    note("its recording", view.get("recording"), KNOWN_VIEW_KEYS["recording"])
    for item in view.get("sets") or []:
        if isinstance(item, dict):
            note(f"the set {item.get('id')}", item, KNOWN_VIEW_KEYS["set"] | ({"factors"} if item.get("id") == "channel" else set()) | {"per_cycle"})
    for group, key in (("layers", "layer"), ("records", "record"), ("constants", "constant"), ("unstated", "unstated"), ("events", "event")):
        extra = sorted({found for item in view.get(group) or [] if isinstance(item, dict) for found in item} - KNOWN_VIEW_KEYS[key])
        if extra:
            said.append(f"its {group}: {', '.join(extra)}")
    return said


def view_rows(name, folder, base, array_name):
    """One array of a time base, read from the files the view names for that base: (shape after time, flat values, rows)."""
    shape, values, rows = None, array("d"), 0
    for part in base.get("files") or []:
        file, span = part.get("file") if isinstance(part, dict) else None, part.get("rows") if isinstance(part, dict) else None
        if not isinstance(file, str) or not RUN_FOLDER.match(file) or not (folder / file).is_file():
            raise Refused(f"{name}: its view names a file of the time base {base.get('id')} that is not in the run's folder")
        if array_name not in npz_names(folder / file):
            raise Refused(f"{name}: {Path(file).name} does not hold {array_name}, which its view says is saved there")
        data = read_npz(folder / file, [array_name])[array_name]
        if not (isinstance(span, list) and len(span) == 2 and span[0] == rows and span[1] - span[0] == data.shape[0]):
            raise Refused(f"{name}: {Path(file).name} does not hold the rows its view gives it for the time base {base.get('id')}")
        if shape is not None and tuple(data.shape[1:]) != shape:
            raise Refused(f"{name}: {array_name} changes its shape between the files of its time base")
        shape = tuple(data.shape[1:])
        values.extend(data.values)
        rows = span[1]
    if shape is None:
        raise Refused(f"{name}: the time base {base.get('id')} of its view names no file")
    return shape, values, rows


# A builder's length unit (the writer's LENGTH_UNITS), in the um the page draws in.
IN_UM = {"m": 1e6, "mm": 1e3, "um": 1.0, "nm": 1e-3}


def builder_polygons(geometry, space, kept):
    """The cells' polygons as the run's view gives them (a builder's geometry), for the cells kept (`kept`: their slots), in
    um, with coincident vertices given one index so that the page finds the edge two cells share: {vertices, faces,
    given, moved}; or None where the view gives no polygons in a plane, in a unit it names. A vertex within a billionth
    of the drawing's extent of an earlier one is given that one's index; `moved` is the largest distance, in um, between
    two vertices so given one index (rounding, where the builder's cells share their corners)."""
    if not (isinstance(geometry, dict) and geometry.get("kind") == "polygons" and isinstance(space, dict) and space.get("dimensions") == 2 and space.get("unit") in IN_UM):
        return None
    vertices, faces = geometry.get("vertices"), geometry.get("faces")
    if not (isinstance(vertices, list) and isinstance(faces, list) and all(isinstance(face, list) and len(face) >= 3 and all(type(v) is int and 0 <= v < len(vertices) for v in face) for face in (faces[k] for k in kept if k < len(faces)))):
        return None
    if not all(isinstance(v, list) and len(v) == 2 and all(finite(x) for x in v) for v in vertices) or len(faces) < max(kept, default=-1) + 1:
        return None
    factor = IN_UM[space["unit"]]
    points = [[x * factor, y * factor] for x, y in vertices]
    extent = max((max(abs(x), abs(y)) for x, y in points), default=0.0) or 1.0
    near, cell = 1e-9 * extent, 1e-6 * extent
    kept_points, index, grid, moved = [], {}, {}, 0.0
    for number, (x, y) in enumerate(points):
        key = (round(x / cell), round(y / cell))
        found = next((k for dx in (-1, 0, 1) for dy in (-1, 0, 1) for k in grid.get((key[0] + dx, key[1] + dy), ()) if abs(kept_points[k][0] - x) <= near and abs(kept_points[k][1] - y) <= near), None)
        if found is None:
            found = len(kept_points)
            kept_points.append([x, y])
            grid.setdefault(key, []).append(found)
        moved = max(moved, math.hypot(kept_points[found][0] - x, kept_points[found][1] - y))
        index[number] = found
    return {"vertices": kept_points, "faces": [[index[v] for v in faces[k]] for k in kept], "given": len(vertices), "moved": moved}


SPHERE_SIDES = 24  # a prescribed sphere's section drawn as a polygon of this many sides


def builder_spheres(geometry, space, kept):
    """The cells as the run's view prescribes them where it gives spheres in a plane (`centres` and `radius`, in a unit
    it names): each cell drawn as its section, a polygon of SPHERE_SIDES sides about its centre with the sphere's radius,
    in um, its corners its own. {vertices, faces, radius}; or None where the view gives no such geometry. Cells so placed
    need not touch: the page draws their junctions between them as the view joins them, not by shared edges."""
    if not (isinstance(geometry, dict) and geometry.get("kind") == "spheres" and isinstance(space, dict) and space.get("dimensions") == 2 and space.get("unit") in IN_UM):
        return None
    centres, radius = geometry.get("centres"), geometry.get("radius")
    if not (isinstance(centres, list) and isinstance(radius, list) and len(centres) == len(radius) and len(centres) >= max(kept, default=-1) + 1):
        return None
    if not all(isinstance(c, list) and len(c) == 2 and all(finite(x) for x in c) for c in centres) or not all(finite(r) and r > 0 for r in radius):
        return None
    factor = IN_UM[space["unit"]]
    vertices, faces = [], []
    for k in kept:
        (x, y), r = centres[k], radius[k]
        start = len(vertices)
        for side in range(SPHERE_SIDES):
            angle = 2.0 * math.pi * side / SPHERE_SIDES
            vertices.append([(x + r * math.cos(angle)) * factor, (y + r * math.sin(angle)) * factor])
        faces.append(list(range(start, start + SPHERE_SIDES)))
    return {"vertices": vertices, "faces": faces, "radius": [radius[k] * factor for k in kept]}


def looped(name, loop, cells, times, record_ids=()):
    """A view's loop block (FR-11; schema/RUN_VIEW.md, view.loop), checked against the run, in the shape the page reads:
    {species, cell, period, closes: {within, tolerance, says, zero?}, not_measured?, follows?}. `cells` are the view's
    named cells, `times` the replay's record times as the run saved them (64-bit) and `record_ids` the ids of the view's
    records. Refused where the block is malformed, where the run says it closes above its own tolerance, where its period
    is not the span of its records, or where it names a cell or a record the run does not have. What the closure leaves
    out (not_measured) and the records identically zero over the loop (closes.zero) are carried as written: a record not
    measured is not read as one that meets itself."""
    where = f"{name}: its view's loop"
    if not (isinstance(loop, dict) and {"species", "cell", "period", "closes"} <= set(loop) <= LOOP_KEYS):
        raise Refused(f"{where} does not give its species, cell, period and closure (and at most what its closure leaves out and the cells it follows)")
    if not (isinstance(loop["species"], str) and loop["species"]):
        raise Refused(f"{where} names no species")
    if loop["cell"] not in cells:
        raise Refused(f"{where} is of a cell the run does not have ({loop['cell']})")
    closes = loop["closes"]
    if not (isinstance(closes, dict) and {"within", "tolerance", "says"} <= set(closes) <= CLOSES_KEYS and finite(closes["within"]) and closes["within"] >= 0 and finite(closes["tolerance"]) and closes["tolerance"] >= 0 and isinstance(closes["says"], str) and closes["says"].strip()):
        raise Refused(f"{where} does not say how closely its last record meets its first (within), against which tolerance, and in what words")
    if "zero" in closes and not (isinstance(closes["zero"], list) and all(record in record_ids for record in closes["zero"])):
        raise Refused(f"{where} names, as records identically zero over the loop, what are not records of the view")
    left = loop.get("not_measured")
    if "not_measured" in loop and not (isinstance(left, list) and all(isinstance(group, dict) and set(group) == {"why", "records"} and isinstance(group["why"], str) and group["why"].strip() and isinstance(group["records"], list) and group["records"] and all(record in record_ids for record in group["records"]) for group in left)):
        raise Refused(f"{where} does not give, for each group of records its closure leaves out, the records by the view's ids and the reason")
    if closes["within"] > closes["tolerance"]:
        raise Refused(f"{where} says its last record meets its first within {closes['within']}, above its own tolerance of {closes['tolerance']}")
    span = times[-1] - times[0]
    if not (finite(loop["period"]) and loop["period"] > 0 and math.isclose(loop["period"], span, rel_tol=1e-9, abs_tol=1e-12)):
        raise Refused(f"{where} gives a period of {loop['period']} s, and its records span {span} s: they must be the same")
    if "cell_type" in loop and not (isinstance(loop["cell_type"], str) and loop["cell_type"].strip()):
        raise Refused(f"{where} names its cell type with no word")
    out = {"species": loop["species"], "cell": loop["cell"], "period": loop["period"], "closes": {"within": closes["within"], "tolerance": closes["tolerance"], "says": closes["says"]}}
    if "cell_type" in loop:
        out["cell_type"] = loop["cell_type"]
    if "zero" in closes:
        out["closes"]["zero"] = list(closes["zero"])
    if "not_measured" in loop:
        out["not_measured"] = [{"why": group["why"], "records": list(group["records"])} for group in left]
    if "follows" in loop:
        steps = loop["follows"]
        if not (isinstance(steps, list) and all(isinstance(step, dict) and set(step) == {"time", "from", "to"} and finite(step["time"]) and times[0] <= step["time"] <= times[-1] and step["from"] in cells and step["to"] in cells for step in steps)):
            raise Refused(f"{where} follows a cell the run does not have, or from a time outside its records")
        out["follows"] = [{"time": step["time"], "from": step["from"], "to": step["to"]} for step in steps]
    return out


# ---------------------------------------------------------------- a quantity the experiment states beside a run
# The experiment's driver may write, beside a package, a quantity over the cells that it works out itself (each cell's
# concentration, a criterion's quantity): schema/RUN_VIEW.md, "A quantity the experiment states". The run folder's
# index.json names the file (`packages[].sidecar`). It is copied as stated, at the replay's own times, and said on the
# page to be the experiment's quantity, never a field of the engine; the viewer works nothing out of it.
STATED_FORMATS = ("cells.experiment_quantity@1", "cells.experiment_criterion@1")
STATED_FILE = re.compile(r"^[a-z0-9_-]+\.json$")
STATED_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*$")
STATED_PREFIX = "stated."


def stated_files(root, name, entry=None):
    """The files the run folder's index says stand beside a package (`packages[].sidecar`, one name or a list); in a run
    folder with no index, the file the experiment's overlay entry names beside every package (`sidecar`); none where neither says one.
    A run folder with a manifest (package.json) names them itself, in place of both (`packages[].sidecars`)."""
    manifest = package_manifest(root)
    if manifest is not None:
        return list(manifest["sidecars"].get(name, []))
    index = read_json(root / "index.json") if (root / "index.json").is_file() else None
    packages = index.get("packages") if isinstance(index, dict) else None
    package = next((item for item in packages if isinstance(item, dict) and item.get("arm") == name), None) if isinstance(packages, list) else None
    said = (package or {}).get("sidecar") if index is not None else (entry or {}).get("sidecar")
    if said is None:
        return []
    names = [said] if isinstance(said, str) else said
    if not (isinstance(names, list) and all(isinstance(item, str) and STATED_FILE.match(item) for item in names)):
        namer = "its folder's index" if index is not None else "its overlay entry"
        raise Refused(f"{name}: {namer} names a file beside it that is not a JSON file's plain name (sidecar)")
    return names


def stated_quantity(name, folder, file, cells, times):
    """One stated quantity over the kept cells at the replay's times, as {"record": its fields, "values": array, "states": (words, codes) or None}.

    Every replay time must be one of the file's own times and every cell one of its cells: nothing is resampled, matched
    by order or filled in. A criterion gives the scale its ticks in its own words (one threshold, or two with the word for
    between them); `states`, where given, are carried as the driver states them, and the colour is never worked out from them."""
    where = f"{name}: its {file}"
    if not (folder / file).is_file():
        raise Refused(f"{where}, which its folder's index names, is not there")
    data = read_json(folder / file)
    if not isinstance(data, dict) or data.get("format") not in STATED_FORMATS:
        raise Refused(f"{where} is not a stated quantity ({' or '.join(STATED_FORMATS)})")
    quantity = data.get("quantity")
    if not (isinstance(quantity, dict) and isinstance(quantity.get("id"), str) and STATED_ID.match(quantity["id"]) and isinstance(quantity.get("label"), str) and quantity["label"].strip() and isinstance(quantity.get("unit"), str)):
        raise Refused(f"{where} does not name its quantity (quantity: id, label, unit)")
    named, stated_times, values = data.get("cells"), data.get("times_s"), data.get("values")
    if not (isinstance(named, list) and named and all(isinstance(cell, str) and cell for cell in named) and len(set(named)) == len(named)):
        raise Refused(f"{where} does not name each of its cells once (cells)")
    if set(named) != set(cells):
        missing, unknown = [cell for cell in cells if cell not in named], [cell for cell in named if cell not in cells]
        raise Refused(f"{where} names other cells than the run's view: {'missing ' + ', '.join(missing[:4]) if missing else ''}{'; ' if missing and unknown else ''}{'not in the view ' + ', '.join(unknown[:4]) if unknown else ''}")
    if not (isinstance(stated_times, list) and stated_times and all(is_number(time) for time in stated_times) and isinstance(values, list) and len(values) == len(stated_times) and all(isinstance(row, list) and len(row) == len(named) and all(is_number(value) for value in row) for row in values)):
        raise Refused(f"{where} does not give one finite number for each of its cells at each of its times (times_s, values)")
    rows, at = [], 0
    for time in times:
        while at < len(stated_times) and stated_times[at] < time and not math.isclose(stated_times[at], time, **TIME_CLOSE):
            at += 1
        if not (at < len(stated_times) and math.isclose(stated_times[at], time, **TIME_CLOSE)):
            raise Refused(f"{where} has no row at the replay's time {plain_number(time)} s: a stated quantity is never resampled")
        rows.append(at)
    columns = [named.index(cell) for cell in cells]
    record = {
        "id": STATED_PREFIX + quantity["id"],
        "label": quantity["label"],
        "unit": quantity["unit"],
        "stated": {"file": file, "format": data["format"], "quantity": quantity["id"]},
    }
    states = None
    if data["format"] == "cells.experiment_criterion@1":
        said = data.get("criterion")
        worded = lambda holder, key: isinstance(holder.get(key), str) and bool(holder[key].strip())  # noqa: E731
        if not (isinstance(said, dict) and is_number(said.get("threshold")) and all(worded(said, key) for key in ("above", "words", "source"))):
            raise Refused(f"{where} does not state its criterion (criterion: threshold, above, words, source)")
        lower = said.get("lower")
        if lower is None:
            if not worded(said, "below"):
                raise Refused(f"{where}: its criterion's one threshold has no word for what lies below it (criterion.below)")
            record["marks"] = [{"value": said["threshold"], "label": f"{said['above']} above, {said['below']} below"}]
        else:
            if not (isinstance(lower, dict) and is_number(lower.get("threshold")) and lower["threshold"] < said["threshold"] and worded(lower, "below") and worded(said, "between")):
                raise Refused(f"{where}: its criterion's lower threshold needs a value under the upper one, its word below it, and the word for between the two (criterion.lower, criterion.between)")
            record["marks"] = [{"value": lower["threshold"], "label": f"{lower['below']} below, {said['between']} between"}, {"value": said["threshold"], "label": f"{said['above']} above"}]
        record["criterion"] = {"words": said["words"], "source": said["source"]}
        # What the driver states beside its criterion of the run as a whole, carried as given: the tumor's cells as seeded
        # (`tumor_cells`, cells of the view), the run's species by name (`species`), the arm's place against a threshold (`place`).
        if "tumor_cells" in data:
            if not (isinstance(data["tumor_cells"], list) and data["tumor_cells"] and all(isinstance(cell, str) and cell in cells for cell in data["tumor_cells"])):
                raise Refused(f"{where}: its tumor_cells are not cells of the run's view")
            record["tumor_cells"] = list(data["tumor_cells"])
        if "species" in data:
            if not (isinstance(data["species"], dict) and all(isinstance(key, str) and isinstance(value, str) and value for key, value in data["species"].items())):
                raise Refused(f"{where}: its species are not names of the run's species (species: id to name)")
            # Named apart from a record's own `species` (the one species a record of a species is of).
            record["species_names"] = dict(data["species"])
        if "place" in data:
            place = data["place"]
            if not (isinstance(place, dict) and isinstance(place.get("relative_to_x2"), str) and place.get("side") in ("below", "at", "above") and isinstance(place.get("source"), str)):
                raise Refused(f"{where}: its place does not say where the arm stands (relative_to_x2, side, source)")
            record["place"] = {key: place[key] for key in ("D", "x2", "ratio_to_x2", "relative_to_x2", "side", "source") if key in place}
        if "states" in data:
            given = data["states"]
            if not (isinstance(given, list) and len(given) == len(stated_times) and all(isinstance(row, list) and len(row) == len(named) and all(isinstance(state, str) and state for state in row) for row in given)):
                raise Refused(f"{where}: its states do not give one word for each of its cells at each of its times (states)")
            words = sorted({given[row][k] for row in rows for k in columns})
            if len(words) > 255:
                raise Refused(f"{where}: its states hold more than 255 words")
            states = (words, array("B", (words.index(given[row][k]) for row in rows for k in columns)))
    flat = array("f", (values[row][k] for row in rows for k in columns))
    return {"record": record, "values": flat, "states": states}


def adapt_engine_view(root, name, experiment, entry):
    """One run with the engine's own view beside its files (view.json, cells.run_view@1): packaged as that view declares it."""
    folder = root / name
    view = read_json(folder / VIEW_FILE)
    if not isinstance(view, dict) or view.get("format") != VIEW_FORMAT:
        raise Refused(f"{name}: its {VIEW_FILE} is not a run view ({VIEW_FORMAT})")
    if VIEW_KEYS - set(view):
        raise Refused(f"{name}: its {VIEW_FILE} lacks {', '.join(sorted(VIEW_KEYS - set(view)))}")
    if (folder / EXAMPLE_FILE).is_file():
        raise Refused(f"{name}: an example with invented numbers has no view of the engine's; the two are not read together")
    # A recording subset (recording.subset: the fields kept, the elements kept, the cadence), the run's own statement of
    # what it saved. What it kept is packaged; what it did not keep is said to be unrecorded, never filled in.
    recording = view.get("recording")
    subset = recording.get("subset") if isinstance(recording, dict) else None
    if subset is not None:
        kept_fields, kept_elements, every = (subset.get(key) for key in ("fields", "elements", "every")) if isinstance(subset, dict) else (None, None, None)
        if not (
            isinstance(subset, dict) and set(subset) == {"fields", "elements", "every"}
            and (kept_fields is None or (isinstance(kept_fields, list) and kept_fields and all(isinstance(field, str) and field for field in kept_fields)))
            and (kept_elements is None or (isinstance(kept_elements, dict) and all(isinstance(ids, list) and ids and all(isinstance(entity, str) and entity for entity in ids) for ids in kept_elements.values())))
            and type(every) is int and every >= 1
        ):  # fmt: skip
            raise Refused(f"{name}: its view's recording subset does not give the fields it keeps, the elements it keeps and its cadence (recording.subset)")
    derivation = [
        f"Read from the engine's own view of the run ({VIEW_FILE}, {VIEW_FORMAT}), beside its files: every set, unit, kind, sign, owner and layer is as that view declares it. "
        "The viewer adds no table of its own and reads nothing out of the arrays' values; what the view does not state is not stated here."
    ]

    # ---- the sets: every entity the view names; a slot with no name is padding, and is left out.
    sets = {item.get("id"): item for item in view["sets"] if isinstance(item, dict)}
    for needed in ("cell", "species"):
        if not isinstance(sets.get(needed, {}).get("ids"), list):
            raise Refused(f"{name}: its view lists no {needed}s")
    keep = {identifier: [k for k, entity in enumerate(item.get("ids") or []) if entity is not None] for identifier, item in sets.items()}
    place = {identifier: {old: new for new, old in enumerate(kept)} for identifier, kept in keep.items()}
    padding = {identifier: len(item.get("ids") or []) - len(keep[identifier]) for identifier, item in sets.items()}
    named = lambda identifier: [sets[identifier]["ids"][k] for k in keep.get(identifier, [])]  # noqa: E731

    def each(identifier, key):
        """One value of a set's list for each named entity, or None where the set gives no such list."""
        values = sets.get(identifier, {}).get(key)
        return [values[k] for k in keep[identifier]] if isinstance(values, list) and len(values) == len(sets[identifier]["ids"]) else None

    # What a set states beyond its ids, where the view gives it: the roles its records' signs name (each with what it
    # is), and an operator's facts of each entity. A list that is not one value for each id, or a fact that names what
    # the view does not declare, is refused: a fact dropped in silence would leave the page to assume it.
    declared_species = [entity for entity in sets["species"]["ids"] if entity is not None]
    for identifier, item in sets.items():
        if "roles" in item and not (isinstance(item["roles"], dict) and item["roles"] and all(isinstance(role, str) and role and isinstance(what, str) and what for role, what in item["roles"].items())):
            raise Refused(f"{name}: its view gives the set {identifier} roles that do not each say what the role is")
        for key in PER_ENTITY:
            if key not in item:
                continue
            values = item[key]
            if not (isinstance(values, list) and len(values) == len(item.get("ids") or [])):
                raise Refused(f"{name}: its view gives the set {identifier} '{key}' that is not one value for each of its entities")
            if key == "carries" and not all((value in declared_species) if isinstance(value, str) else (isinstance(value, list) and value and all(isinstance(each_, str) and each_ in declared_species for each_ in value)) for value in values):
                raise Refused(f"{name}: its view says an entity of {identifier} carries a species that is not among the run's species")
            if key == "at" and not all(isinstance(value, dict) and len(value) == 1 and next(iter(value)) in sets and next(iter(value.values())) in [entity for entity in sets[next(iter(value))].get("ids") or [] if entity is not None] for value in values):
                raise Refused(f"{name}: its view says an entity of {identifier} acts at an entity that is not one of the view's")
            if key in ("direction", "kinds") and not all(isinstance(value, str) and value for value in values):
                raise Refused(f"{name}: its view gives the set {identifier} '{key}' that is not a word for each of its entities")
    # The channel set's factors (the routing door into @3, from d64fb664): for each population the factor sources that scale
    # its availability, in declared order (none for one that declares none; null for a padding slot). Not one such list for
    # each population is refused, as the engine's own check refuses it.
    channel = sets.get("channel") or {}
    if "factors" in channel and not (
        isinstance(channel["factors"], list) and len(channel["factors"]) == len(channel.get("ids") or [])
        and all((value is None and entity is None) or (isinstance(value, list) and all(isinstance(source, str) and source for source in value)) for value, entity in zip(channel["factors"], channel.get("ids") or []))
    ):  # fmt: skip
        raise Refused(f"{name}: its view gives the channel set factors that are not, for each population, the list of the factor sources it declares")
    # The entities a recording subset kept: each set's `recorded` (indices into its ids) names exactly the elements the
    # subset lists for it, in their order. Only the species are read so far: a field saved once for each species is
    # packaged for the recorded ones. The page draws every entity of a set it shows, so a subset of cells, membranes or
    # any other set is refused, with the sets named.
    elements = (subset or {}).get("elements") or {}
    for identifier, item in sets.items():
        recorded = item.get("recorded")
        if (recorded is not None) != (identifier in elements):
            raise Refused(f"{name}: its view's set {identifier} and its recording subset disagree on whether only some of its entities were recorded")
        if recorded is not None:
            ids = item.get("ids") or []
            if not (isinstance(recorded, list) and all(type(k) is int and 0 <= k < len(ids) for k in recorded) and [ids[k] for k in recorded] == elements[identifier]):
                raise Refused(f"{name}: its view's set {identifier} records entities (recorded) that are not the ones its recording subset names")
    unknown_sets = sorted(set(elements) - set(sets))
    if unknown_sets:
        raise Refused(f"{name}: its view's recording subset keeps elements of {', '.join(unknown_sets)}, which the view does not list as a set")
    laid_out = sorted(set(elements) - {"species"})
    if laid_out:
        raise Refused(f"{name}: its view records only some entities of {', '.join(laid_out)} (recording.subset.elements), which the adapter does not lay out yet: the page draws every entity of a set it shows")
    # Which row of an array over the species holds which species: the recorded ones in their order, or every named one.
    recorded_species = sets["species"].get("recorded")
    species_rows = [(sets["species"]["ids"][k], j) for j, k in enumerate(recorded_species)] if recorded_species is not None else [(sets["species"]["ids"][k], k) for k in keep["species"]]

    def onto(identifier, target, index):
        """A set's index into another set, for its named entities, in that set's numbering without its padding."""
        try:
            return [place[target][index[k]] for k in keep[identifier]]
        except (KeyError, IndexError, TypeError):
            raise Refused(f"{name}: an entity of {identifier} in its view points at no named entity of {target}") from None

    def geometry_of(identifier):
        """A set's `on` or `links` geometry, renumbered; or None."""
        geometry = sets.get(identifier, {}).get("geometry")
        if not isinstance(geometry, dict):
            return None
        if geometry.get("kind") == "on" and geometry.get("set") in sets:
            return {"kind": "on", "set": geometry["set"], "index": onto(identifier, geometry["set"], geometry.get("index"))}
        if geometry.get("kind") == "links" and geometry.get("between") in sets:
            target, ends = geometry["between"], geometry.get("ends") or []
            try:
                return {"kind": "links", "between": target, "ends": [[place[target][ends[k][0]], place[target][ends[k][1]]] for k in keep[identifier]]}
            except (KeyError, IndexError, TypeError):
                raise Refused(f"{name}: a link of {identifier} in its view joins no named entity of {target}") from None
        return None

    constants_in = [item for item in view["constants"] if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("axes"), list)]
    cells, species = named("cell"), named("species")
    volume = next((item for item in constants_in if item["id"] == "volume" and item["axes"] == ["cell"] and isinstance(item.get("values"), list) and len(item["values"]) == len(sets["cell"]["ids"])), None)
    junction_links = geometry_of("junction") if "junction" in sets else None
    junction_ids = named("junction") if junction_links and junction_links["between"] == "cell" else []
    like = {
        "cells": [{"id": cell, "volume_pL": volume["values"][keep["cell"][k]] if volume else 1.0} for k, cell in enumerate(cells)],
        "junctions": [{"id": identifier, "sender": cells[a], "receiver": cells[b]} for identifier, (a, b) in zip(junction_ids, junction_links["ends"] if junction_ids else [])],
    }
    # Where the run gives its cells' polygons (a builder's geometry, in a plane), the picture stands them where the run
    # does; the adapter's own layout is the fallback where the view gives none, or gives a geometry the page cannot draw.
    built = builder_polygons(sets["cell"].get("geometry"), view.get("space"), keep["cell"])
    spheres = builder_spheres(sets["cell"].get("geometry"), view.get("space"), keep["cell"]) if built is None else None
    if spheres is not None:
        # Prescribed places: each cell where the view puts it, drawn as its section; a small network, not a sheet.
        sheet = lay_out(name, like, [], row=True)
        sheet.vertices, sheet.faces = spheres["vertices"], spheres["faces"]
        space = view["space"]
        sheet.prescribed = True
        derivation.append(
            f"Cell positions as the run's view prescribes them ({space['representation']}, from {space['source']}): each cell a sphere at its centre, "
            f"drawn as its section through the centre, a circle of its radius ({min(spheres['radius']):.3g} to {max(spheres['radius']):.3g} um). "
            "The cells need not touch: each junction is drawn between the two cells the view joins, not where they share an edge."
        )
    elif built is not None:
        sheet = lay_out(name, like, [], row=True)
        sheet.vertices, sheet.faces = built["vertices"], built["faces"]
        space = view["space"]
        derivation.append(
            f"Cell positions and shapes are the run's own geometry ({space['representation']}, from {space['source']}): each cell's polygon as the view gives it, in {space['unit']}"
            f"{'' if space['unit'] == 'um' else ', here in um'}. Vertices that coincide are given one index ({built['given']} given, {len(built['vertices'])} kept), so that the page finds the edge two cells share; the corners so joined were at most {built['moved']:.1g} um apart."
        )
    else:
        stated = sets["cell"].get("geometry")
        if isinstance(stated, dict) and stated.get("kind") == "polygons":
            derivation.append("The view places its cells itself (polygons), in a form the page does not draw (not in a plane, in no length unit the adapter knows, or not one face of its vertices for each cell); the adapter lays the cells out as below.")
        elif stated is not None:
            derivation.append(f"The view places its cells itself ({(stated or {}).get('kind')}); the adapter does not read a builder's geometry of that kind yet, and lays the cells out as below.")
        sheet = lay_out(name, like, derivation, row=True)
    if not volume:
        derivation.append("The view states no cell volume: the size the cells are drawn at stands for nothing.")
    membranes = None
    membrane_on = geometry_of("membrane") if "membrane" in sets else None
    faces_outside = sets.get("membrane", {}).get("outside")
    if membrane_on and membrane_on["set"] == "cell" and isinstance(faces_outside, dict) and faces_outside.get("set") in sets:
        membranes = {"ids": named("membrane"), "cell": membrane_on["index"], "outside": onto("membrane", faces_outside["set"], faces_outside.get("index")), "nodes": named(faces_outside["set"]), "set": faces_outside["set"]}

    # ---- the time bases: the replay steps through one of them, the observed rows where the run has them.
    bases = {base.get("id"): base for base in (view["time"] or {}).get("bases") or [] if isinstance(base, dict)}
    timeline = next((identifier for identifier in ("observation", "accepted") if identifier in bases and bases[identifier].get("files")), None)
    if timeline is None:
        raise Refused(f"{name}: its view names no time base the adapter knows (observation, accepted)")
    _, time_values, count = view_rows(name, folder, bases[timeline], bases[timeline].get("array"))
    times = list(time_values)
    increasing(name, times)
    derivation.append(f"The replay steps through the view's time base '{timeline}' ({bases[timeline].get('says') or 'as the view calls it'}): {count} records. Each record here names the base its array is saved on.")
    others = {identifier: base for identifier, base in bases.items() if identifier != timeline}
    other_rows = {}

    def rows_on(identifier):
        """For another time base: the row of it that falls on each time of the replay, or None where one has none."""
        if identifier not in other_rows:
            _, values, _ = view_rows(name, folder, others[identifier], others[identifier].get("array"))
            found, at = [], 0
            for time in times:
                while at < len(values) and values[at] < time and not math.isclose(values[at], time, **TIME_CLOSE):
                    at += 1
                found.append(at if at < len(values) and math.isclose(values[at], time, **TIME_CLOSE) else None)
            other_rows[identifier] = None if any(row is None for row in found) else found
        return other_rows[identifier]

    # ---- the records: those the page has a name for, as the view declares them.
    listed = [record for record in view["records"] if isinstance(record, dict) and isinstance(record.get("field"), str) and record.get("base") in bases]
    on_timeline = {record["field"] for record in listed if record["base"] == timeline}
    payload, records, parts, skipped, twins, sampled, unsampled, unnamed = Payload(), [], [], [], 0, [], [], set()
    records.append(describe(payload, "t", "Time", "s", ["time"], "float32", (count,), array("f", times)))
    layer_ids = {layer.get("id") for layer in view["layers"] if isinstance(layer, dict)}

    def merged(record):
        """Whether a record is door S's merged view of a field that the composition changes (view_<field>)."""
        return record.get("id") == VIEW_PREFIX + record["field"]

    # Which way a record is positive, where the view states it, is checked against the roles its set states: a flow's
    # `sign` names two of them as from and to, a difference's (a voltage's) `difference` names two as plus and minus. A
    # record of a set that states no roles (the 15 November shape) keeps its sign as written.
    for record in listed:
        sign, difference = record.get("sign"), record.get("difference")
        roles = (sets.get(record.get("set")) or {}).get("roles")
        where = f"{name}: its view's record {record.get('id')}"
        if sign is not None and difference is not None:
            raise Refused(f"{where} gives both a sign (a flow's ends) and a difference (a voltage's ends); a record is one or the other")
        if sign is not None and roles is not None and not (isinstance(sign, dict) and sign.get("from") in roles and sign.get("to") in roles and sign["from"] != sign["to"]):
            raise Refused(f"{where} names, as the ends its sign goes from and to, what are not two roles of its set {record.get('set')}")
        if difference is not None and not (isinstance(difference, dict) and roles is not None and difference.get("plus") in roles and difference.get("minus") in roles and difference["plus"] != difference["minus"] and isinstance(difference.get("says"), str) and difference["says"]):
            raise Refused(f"{where} gives a difference whose plus and minus are not two roles of its set {record.get('set')}, or that does not say what positive means")
        resets = record.get("resets")
        if isinstance(resets, dict) and "mask" in resets and not (isinstance(resets["mask"], str) and resets["mask"]):
            raise Refused(f"{where} says it restarts at a retirement, and names no mask for the slots that restart")
    # A field the composition changes is a merged view at each observed row, never a constant of the definition too.
    both = sorted({record["field"] for record in listed if merged(record)} & {item["id"] for item in constants_in})
    if both:
        raise Refused(f"{name}: its view states {', '.join(both)} both as a constant of the definition and as the merged view the composition changes ({VIEW_PREFIX}<field>)")
    # The two record roles (from b08af640 on; the writer on main since 050aa741, 16 November 2026): a diagnostic says in
    # words that the record is the residual of the engine's own check; a reference names the fixed reference a record
    # is stored over (a constant of the view, the merged view's record, or a field the run did not save). A role that
    # is not so given is refused, as the writer's own check refuses it.
    constant_ids = {item["id"] for item in constants_in}
    record_ids = {record.get("id") for record in view["records"] if isinstance(record, dict)}
    # A reference over a field the run did not save ({"field": X}: door S's merged view, not saved) stands only where the
    # view says why under `unstated`, by an entry for X (from d64fb664; no saved view before it has such a reference).
    unstated_why = {item.get("id"): item.get("why") for item in view["unstated"] if isinstance(item, dict) and isinstance(item.get("id"), str)}

    def over(reference):
        """A reference over a field the run did not save, in words, with the view's own reason."""
        why = unstated_why.get(reference["field"])
        return f"the field {reference['field']}, which the run did not save{f' ({why})' if isinstance(why, str) and why else ''}"

    for record in listed:
        where = f"{name}: its view's record {record.get('id')}"
        if "diagnostic" in record and not (isinstance(record["diagnostic"], str) and record["diagnostic"].strip()):
            raise Refused(f"{where} is marked a diagnostic with no words for what it is")
        reference = record.get("reference")
        if "reference" in record and not (isinstance(reference, dict) and len(reference) == 1 and (reference.get("constant") in constant_ids or reference.get("record") in record_ids or isinstance(reference.get("field"), str))):
            raise Refused(f"{where} names a reference that is not one constant, record or field of the view")
        if "reference" in record and "field" in reference and reference["field"] not in unstated_why:
            raise Refused(f"{where} is stored over the field {reference['field']} (its reference), which the run did not save, and its view gives no entry for {reference['field']} under unstated saying why")
    # A level the page reads that the run saved only as an increment over a fixed reference: the record of the increment
    # on the replay's own base where it has one; the level is worked out below as the reference plus the increment.
    summed = {}
    for level, increment in INCREMENT_OF.items():
        if any(record["field"] == level for record in listed):
            continue
        found = sorted((record for record in listed if record["field"] == increment and isinstance(record.get("reference"), dict)), key=lambda record: record["base"] != timeline)
        if found:
            summed[level] = found[0]
    # The fields a recording subset kept, by the writer's names (a merged view by its view_<field>): every record of the
    # view is of one of them. Of the fields the page has a name for, those it does not list are unrecorded, in the run's
    # own statement; nothing stands in for them.
    not_recorded = []
    if subset is not None and subset["fields"] is not None:
        strays = sorted({record["id"] if merged(record) else record["field"] for record in listed} - set(subset["fields"]))
        if strays:
            raise Refused(f"{name}: its view gives records of {', '.join(strays)}, which its recording subset does not keep")
        present = {record.get("field") for record in view["records"] if isinstance(record, dict)} | set(summed)
        # Only what the run could have recorded: a field of an operator the run's composition lacks, or over a set the view
        # gives no entity of, is said of nothing here, as for a full recording of such a run.
        operators = set((view["run"].get("composition") or {}).get("operators") or []) if isinstance(view["run"], dict) and isinstance(view["run"].get("composition"), dict) else set()

        def could_record(field):
            set_id = FIELD_SETS.get(HISTORY_FIELDS[field][0][-1], HISTORY_FIELDS[field][0][-1])
            owner = FIELD_OPERATORS.get(field)
            return (owner is None or owner in operators) and any(entity is not None for entity in (sets.get(set_id) or {}).get("ids") or [])

        not_recorded = [field for field in HISTORY_FIELDS if field not in subset["fields"] and field not in present and could_record(field)]
    labels = {**FIELD_LABELS, **VIEW_FIELD_LABELS}
    voltages, unread_voltages, referenced, sums, unsummed = {}, [], [], {}, []
    # What the picture opens with stays in the run's own file. A part of an experiment whose picture opens on a quantity
    # its driver states (`part_of`, `opens.record`) opens on that, so its voltages, like every other field, go in a file of
    # their own, fetched when a layer shows them.
    main_fields = () if entry.get("part_of") and (entry.get("opens") or {}).get("record") else HISTORY_MAIN
    if not main_fields:
        derivation.append("The voltages are packaged in a file of their own: this part's picture opens on the quantity its driver states (opens.record).")
    # A passive route's totals are packaged for a part whose picture draws them (the tumour tissue's beads); the example's
    # own runs keep the files they had, their layers reading other fields.
    passive_drawn = bool(entry.get("part_of"))
    if not passive_drawn and any(item["field"] == "passive_transferred" for item in listed):
        derivation.append("Its passive routes' totals (passive_transferred) are not packaged: no picture of this experiment's own draws them.")
    for field in [*HISTORY_FIELDS, *VIEW_FIELD_LABELS]:  # the page's own order of fields, then the merged views it reads
        if field == "passive_transferred" and not passive_drawn:
            continue
        for record in [item for item in listed if item["field"] == field and merged(item) == (field in VIEW_FIELD_LABELS)] + ([summed[field]] if field in summed else []):
            rows = range(count)
            if record["base"] != timeline:
                if field in on_timeline:
                    twins += 1
                    continue
                matched = rows_on(record["base"])
                if matched is None:
                    unsampled.append(field)
                    continue
                rows = matched
                sampled.append(field)
            axes = [axis for axis in record.get("axes") or [] if axis != "time"]
            if not (1 <= len(axes) <= 2 and all(axis in sets for axis in axes) and (len(axes) == 1 or axes[0] == "species") and record.get("layer") in layer_ids and isinstance(record.get("unit"), str) and isinstance(record.get("owner"), str)):
                skipped.append(field)
                continue
            shape, values, _ = view_rows(name, folder, bases[record["base"]], record.get("array"))
            if tuple(shape) != tuple(len(sets[axis]["recorded"]) if "recorded" in sets[axis] else len(sets[axis]["ids"]) for axis in axes):
                raise Refused(f"{name}: {record.get('array')} does not have the shape its view's axes give it")
            if "recorded" in sets[axes[-1]]:
                skipped.append(field)
                continue  # a field over the recorded species alone: the page reads a species' value as a field's record of its own
            entity, columns, width = axes[-1], keep[axes[-1]], shape[-1]
            if not columns:
                continue  # a set with no entity: nothing to package, and the view says that it has none
            per = 1
            for size in shape:
                per *= size
            fixed = None
            if record["field"] != field:
                # The level is the run's fixed reference plus its increment (the view's reference): the reference is a
                # named constant of the view, or the merged view's record on the same base; one the run did not save
                # (a field only) cannot be added, and the level is then not packaged.
                reference = record["reference"]
                if "constant" in reference:
                    constant = next(item for item in constants_in if item["id"] == reference["constant"])
                    if constant.get("axes") == axes and isinstance(constant.get("values"), list):
                        table = constant["values"]
                        fixed = lambda row, species_k, k: table[species_k][k] if len(axes) == 2 else table[k]  # noqa: E731
                elif "record" in reference:
                    held = next((item for item in listed if item.get("id") == reference["record"]), None)
                    if held is not None and held["base"] == record["base"] and [axis for axis in held.get("axes") or [] if axis != "time"] == axes:
                        _, held_values, _ = view_rows(name, folder, bases[held["base"]], held.get("array"))
                        fixed = lambda row, species_j, k: held_values[row * per + species_j * width + k] if len(axes) == 2 else held_values[row * per + k]  # noqa: E731
                if fixed is None:
                    unsummed.append(
                        f"{field} (its increment {record['field']} is stored over {over(reference)}, so the adapter cannot add it)"
                        if "field" in reference
                        else f"{field} (its increment {record['field']} is stored over {json.dumps(reference, sort_keys=True)}, which the run did not save in a form the adapter can add)"
                    )
                    continue
                sums[field] = (record["field"], reference)
            elif record.get("reference") is not None:
                # Stored as an increment over a fixed reference (its owner's RECORD_REFERENCES): its quantity is the
                # reference plus the record, which the page does not add. Not packaged, and said.
                referenced.append(f"{field} (over {over(record['reference']) if 'field' in record['reference'] else json.dumps(record['reference'], sort_keys=True)})")
                continue
            stated = {key: record[key] for key in ("kind", "sign", "monotone", "resets", "note", "writers", "diagnostic") if record.get(key) is not None}
            difference = record.get("difference")
            if difference is not None:
                # A voltage is a difference (plus less minus, by its set's roles), as the run's view states it. The page
                # reads which end is the higher as a sign's `high`: given where both roles have a word of the page's,
                # with the view's own words and their source; otherwise the record has no sign, and the page draws it
                # with no direction.
                stated["difference"] = dict(difference)
                high, low = HIGH_WORDS.get(difference["plus"]), HIGH_WORDS.get(difference["minus"])
                if high is not None and low is not None:
                    stated["sign"] = {"says": difference["says"], "high": high, **{key: difference[key] for key in ("confirmed", "source") if isinstance(difference.get(key), str)}}
                    voltages[field] = difference
                else:
                    unread_voltages.append(field)
            stated.update({"array": record.get("array"), "base": record["base"]})
            if record["base"] != timeline:
                stated["rows"] = f"the row of the base '{record['base']}' that falls on each of the replay's times"
            if fixed is not None:
                # The constant's rows run over every species, the array's over the recorded ones: each is read by its own.
                species_k = {identifier: sets["species"]["ids"].index(identifier) for identifier, _ in species_rows}
                is_constant = "constant" in record["reference"]
                stated["note"] = (
                    f"Worked out by the viewer: the run's fixed reference {record['reference'].get('constant') or record['reference'].get('record')} "
                    f"({'a named constant of the view' if is_constant else 'the merged view the run saved'}) plus its record {record.get('array')}, "
                    "as the view states the increment is stored (its reference)."
                )
                stated["reference"] = dict(record["reference"])
                split = (
                    {identifier: array("f", (values[row * per + old * width + k] + fixed(row, species_k[identifier] if is_constant else old, k) for row in rows for k in columns)) for identifier, old in species_rows}
                    if len(axes) == 2
                    else {None: array("f", (values[row * per + k] + fixed(row, None, k) for row in rows for k in columns))}
                )
            else:
                split = {identifier: array("f", (values[row * per + old * width + k] for row in rows for k in columns)) for identifier, old in species_rows} if len(axes) == 2 else {None: array("f", (values[row * per + k] for row in rows for k in columns))}

            # A set whose entities each say which species they carry (a passive route's `carries`): only those species' totals
            # are packaged, since no entity of the set can carry another; the derivation says which were left.
            carried_by = sets.get(entity, {}).get("carries") if len(axes) == 2 else None
            if isinstance(carried_by, list) and carried_by:
                carried = {identifier for value in carried_by for identifier in ([value] if isinstance(value, str) else value or [])}
                left = sorted(identifier for identifier in split if identifier not in carried)
                if left and len(left) < len(split):
                    split = {identifier: item for identifier, item in split.items() if identifier in carried}
                    derivation.append(f"{field} is packaged for the species the {entity} set's entities carry ({', '.join(sorted(split))}); its rows for {', '.join(left)}, which none of them carries, are left out.")

            def declare(target, values_, species_id=None, part=None):
                label = labels[field] if species_id is None else f"{labels[field]}: {species_id}"
                extra = {"field": field, "species": species_id} if species_id is not None else {}
                return describe(target, field if species_id is None else f"{field}.{species_id}", label, record["unit"], ["time", entity], "float32", (count, len(columns)), values_, set=entity, layer=record["layer"], owner=record["owner"], part=part, **stated, **extra)

            if field in main_fields:
                records.append(declare(payload, split[None]))
                continue
            slug = re.sub(r"[^a-z0-9]+", "-", field.lower()).strip("-")
            together = sum(len(item) * 4 for item in split.values()) * 4 / 3 < LIMIT_BYTES * 0.92
            own = Payload()
            for species_id, item in split.items():
                part = slug if together or species_id is None else f"{slug}-{re.sub(r'[^a-z0-9]+', '-', species_id.lower()).strip('-')}"
                if not together and species_id is not None:
                    own = Payload()
                records.append(declare(own, item, species_id, part))
                if not together and species_id is not None:
                    parts.append({"id": part, "label": f"{labels[field]}: {species_id}", "payload": own})
            if together or None in split:
                parts.append({"id": slug, "label": labels[field], "payload": own})
    # A quantity the experiment's driver states beside the run, where the folder's index names one: copied as stated.
    for file in stated_files(root, name, entry):
        stated = stated_quantity(name, folder, file, cells, times)
        record = stated["record"]
        if any(item["id"] == record["id"] for item in records):
            raise Refused(f"{name}: its {file} states a quantity ({record['id']}) another file beside it already states")
        extra = {key: record[key] for key in ("stated", "marks", "criterion", "tumor_cells", "species_names", "place") if key in record}
        if stated["states"]:
            extra["states"] = record["id"] + ".state"
        records.append(describe(payload, record["id"], record["label"], record["unit"], ["time", "cell"], "float32", (count, len(cells)), stated["values"], set="cell", **extra))
        if stated["states"]:
            words, codes = stated["states"]
            records.append(describe(payload, record["id"] + ".state", "The state, as the experiment's driver states it", "", ["time", "cell"], "uint8", (count, len(cells)), codes, set="cell", words=words, stated=record["stated"]))
        derivation.append(
            f"Beside the run, the experiment's driver states {record['label']} ({file}, {record['stated']['format']}): copied as stated at the replay's {count} times, "
            "the experiment's own quantity and not a field of the engine; the viewer works nothing out of it."
            + (" Its criterion gives the scale's ticks in its own words." if "marks" in record else "")
            + (" The state of each cell is carried as the driver states it; the colour is the quantity's, never worked out from the states." if stated["states"] else "")
        )
    unnamed = sorted({record["field"] for record in listed if record["base"] == timeline and record["field"] not in FIELD_LABELS and not merged(record)})
    unread_views = sorted({record["field"] for record in listed if merged(record) and record["field"] not in VIEW_FIELD_LABELS})
    if not any(record.get("set") == "cell" for record in records):
        raise Refused(f"{name}: its view names no record over its cells that the page could colour the sheet by")
    # Where every cell has one membrane, in the cells' order, each membrane's voltage is also its cell's: the same array, declared over the cells.
    own_voltage = next((record for record in records if record["id"] == "membrane_voltage_V"), None)
    if own_voltage and one_membrane_each(membranes, sheet):
        records.insert(records.index(own_voltage) + 1, {**own_voltage, "id": "vm", "set": "cell", "axes": ["time", "cell"], "same_as": "membrane_voltage_V"})
        derivation.append("The view gives every cell exactly one membrane, in the cells' order, so each membrane's saved voltage is also declared as its cell's (vm); no array is added.")
    if twins:
        derivation.append(f"{twins} record(s) of the view's other time base hold the same fields as records packaged here, at other rows: they are not packaged.")
    if sampled:
        derivation.append(f"Saved on another time base only, and packaged at the rows of that base that fall on the replay's times: {', '.join(sorted(set(sampled)))}.")
    if unsampled:
        derivation.append(f"Saved on another time base only, with no row at some of the replay's times, and so not packaged: {', '.join(sorted(set(unsampled)))}.")
    if skipped:
        derivation.append(f"Not packaged, because the page cannot lay out their axes: {', '.join(sorted(set(skipped)))}.")
    if unnamed:
        derivation.append(f"The view declares {len(unnamed)} more field(s) on this time base that the page has no name for; they are not packaged: {', '.join(unnamed)}.")
    for field, difference in voltages.items():
        caveat = f" The view says where that comes from: {difference['source']}." if isinstance(difference.get("source"), str) else f" The view says it was confirmed by {difference['confirmed']}." if isinstance(difference.get("confirmed"), str) else ""
        derivation.append(
            f"Which way {field} is positive is the run's own statement (its difference, plus less minus by the roles of its set): {difference['says']}.{caveat} "
            f"Its sign here gives the end the page calls the higher ({HIGH_WORDS[difference['plus']]}) from the role {difference['plus']}."
        )
    if unread_voltages:
        derivation.append(f"The view states which way {', '.join(sorted(unread_voltages))} is positive between roles the page has no word for: the difference is carried as written, with no sign, and the page draws no direction for it.")
    merged_packaged = sorted({record.get("field") or record["id"] for record in records if isinstance(record.get("array"), str) and record["array"].startswith(VIEW_PREFIX)})
    if merged_packaged:
        derivation.append(f"Changed by the run's operators, and so saved as the merged view at each observed row (the arrays {VIEW_PREFIX}<field>), not as constants: {', '.join(merged_packaged)}, packaged under the field's own name.")
    if unread_views:
        derivation.append(f"The view saves the merged view of {len(unread_views)} more field(s) that the run's operators change, which no layer of the page reads; they are not packaged: {', '.join(unread_views)}.")
    if referenced:
        derivation.append(f"Not packaged, because each is stored as an increment over a fixed reference that the page does not add (the view's reference): {', '.join(sorted(set(referenced)))}.")
    if sums:
        derivation.append(
            "Saved only as an increment over a fixed reference (the view's reference), and so worked out by the viewer as the reference plus the increment, row by row: "
            + "; ".join(f"{level} is {reference.get('constant') or reference.get('record')} plus {increment}" for level, (increment, reference) in sums.items())
            + ". Each such record says so in its note."
        )
    if unsummed:
        derivation.append(f"Not packaged: {'; '.join(unsummed)}.")
    diagnostics = sorted({record["field"] for record in listed if "diagnostic" in record})
    if diagnostics:
        said_of = next(record["diagnostic"] for record in listed if "diagnostic" in record)
        derivation.append(f"The view marks {len(diagnostics)} field(s) as diagnostics, in its words '{said_of}': {', '.join(diagnostics)}. The page shows none of them.")
    # A reference over a field the run did not save is named as such, with the view's reason (its unstated entry).
    stored_over = sorted({f"{record['field']} over {over(record['reference']) if 'field' in record['reference'] else next(iter(record['reference'].values()))}" for record in listed if isinstance(record.get("reference"), dict)})
    if stored_over:
        unsaved = any("field" in record["reference"] for record in listed if isinstance(record.get("reference"), dict))
        derivation.append(f"The view stores {len(stored_over)} field(s) as an increment over a fixed reference (its reference): {('; ' if unsaved else ', ').join(stored_over)}.")
    if subset is not None:
        kept = "every field" if subset["fields"] is None else f"{len(subset['fields'])} field(s) ({', '.join(subset['fields'])})"
        species_kept = f", and of the species only {', '.join(elements['species'])}" if "species" in elements else ""
        derivation.append(f"The run recorded a subset of itself (recording.subset, its own statement): {kept}{species_kept}, {'every observed row' if subset['every'] == 1 else f"one observed row in every {subset['every']}, from its first"}. The replay's records are the rows it kept.")
        if not_recorded:
            derivation.append(
                f"Of the fields the page has a name for, the run's recording subset lists none of these, and its view gives no record of them: {', '.join(not_recorded)}. "
                "Nothing is packaged for them and nothing stands in for them: each is listed as not stated, with that reason, and a layer that needs one says the run did not save it."
            )
        if "species" in elements:
            derivation.append(f"A field saved once for each species is packaged for the recorded species only ({', '.join(elements['species'])}); the others were not recorded.")
    left = sorted(f"{padding[identifier]} of {identifier}" for identifier in padding if padding[identifier])
    if left:
        derivation.append(f"Slots the view gives no name (padding) are left out, with their columns: {', '.join(left)}.")
    derivation.append("Times and values are stored as 32-bit numbers; the run saved 64-bit. Every field but the two the sheet opens with is in a file of its own beside this one.")

    # ---- how the run ended and what its catalogue entry asks to be copied: the run's own files, where it has them.
    config = read_json(folder / "resolved_config.json") if (folder / "resolved_config.json").is_file() else {}
    summary = read_json(folder / "summary.json") if (folder / "summary.json").is_file() else {}
    plan = {"execution": config.get("execution") or {}, "model": {key: value for key, value in (config.get("model") or {}).items() if not isinstance(value, (list, dict))}} if isinstance(config, dict) else {}
    parameters, readouts = copied(entry, plan, summary if isinstance(summary, dict) else {}, {})
    stated_run = view["run"] if isinstance(view["run"], dict) else {}
    arm = re.sub(r"[^A-Za-z0-9._-]+", "-", name)
    unstated_by_id = {item.get("id"): item for item in view["unstated"] if isinstance(item, dict)}
    # The engine's revision. The run's own record of its source (run.source: the running engine's revision and whether its
    # tree was dirty, from its execution snapshot) is the one the engine holds to; a caller's label (run.revision) is only
    # a label. Where the view states no source it says why, and a label is then given as the caller's, never as the engine's.
    revision = stated_run.get("revision") if isinstance(stated_run.get("revision"), str) else None
    source = stated_run.get("source")
    if source is not None:
        if not (isinstance(source, dict) and set(source) == {"revision", "dirty", "from"} and isinstance(source["revision"], str) and source["revision"] and type(source["dirty"]) is bool and isinstance(source["from"], str) and source["from"]):
            raise Refused(f"{name}: its view's run.source does not give the engine's revision, whether its tree was dirty, and where that is recorded")
        if revision is not None and not (source["revision"].startswith(revision) or revision.startswith(source["revision"])):
            raise Refused(f"{name}: its view names two revisions for the run: {revision} as the caller's label (run.revision) and {source['revision']} as the engine's own source (run.source)")
        if "source" in unstated_by_id:
            raise Refused(f"{name}: its view states the engine's source (run.source) and also lists it as unstated")
        revision = source["revision"]
        tree = (
            "its tree was dirty when the run was made, so the revision alone does not give the source that ran: the difference is in the run's frozen snapshot, which the view does not carry"
            if source["dirty"]
            else "its tree was clean when the run was made"
        )
        derivation.append(f"The engine's revision is the run's own record of its source (run.source, from {source['from']}): {source['revision']}; {tree}.")
    elif "source" in unstated_by_id:
        why = unstated_by_id["source"].get("why")
        label = f" The revision given, {revision}, is the caller's label for the run (run.revision), not the engine's own record of its source." if revision else " No revision is given."
        derivation.append(f"The view does not state the engine's own source{f' ({why})' if isinstance(why, str) else ''}.{label}")
    # How the run ended: the run's own statement (run.end) where the view gives it; its summary.json otherwise.
    stop = summary.get("status") if isinstance(summary, dict) and isinstance(summary.get("status"), str) else None
    end = stated_run.get("end")
    if end is not None:
        if not (isinstance(end, dict) and set(end) == {"status", "time", "step"} and isinstance(end["status"], str) and end["status"] and finite(end["time"]) and type(end["step"]) is int):
            raise Refused(f"{name}: its view's run.end does not give the run's status, its end time and its step")
        if stop is not None and stop != end["status"]:
            raise Refused(f"{name}: its view says the run ended '{end['status']}' (run.end), and its summary.json says '{stop}'")
        if times[-1] > end["time"] and not math.isclose(times[-1], end["time"], **TIME_CLOSE):
            raise Refused(f"{name}: its view says the run ended at {end['time']} s (run.end), before its last record at {times[-1]} s")
        stop = end["status"]
        derivation.append(f"How the run ended is the run's own statement (run.end): '{end['status']}' at {end['time']} s, at step {end['step']}.")
    if "id" in stated_run:
        if not (isinstance(stated_run["id"], str) and stated_run["id"]):
            raise Refused(f"{name}: its view's run.id is not a name")
        derivation.append(f"The view's own name for the run is {stated_run['id']} (run.id, its caller's label); the catalogue names runs by experiment and folder.")
    run = run_facts(
        experiment, arm, None, label=stated_run.get("label") if isinstance(stated_run.get("label"), str) else None, group=None,
        engine_models=[model for model in stated_run.get("engine_models") or [] if isinstance(model, str)], revision=revision,
        end_s=times[-1], stop=stop, parameters=parameters, readouts=readouts,
    )  # fmt: skip
    if source is not None:
        run["source"] = dict(source)
    if end is not None:
        run["end"] = dict(end)

    # ---- constants and what the view does not state, as written; a constant's values lose their padding slots.
    def trimmed(values, axes):
        if not axes:
            return values
        return [trimmed(values[k], axes[1:]) for k in keep[axes[0]]]

    def numbers(values):
        return is_number(values) if not isinstance(values, list) else all(numbers(value) for value in values)

    constants = []
    for item in constants_in:
        axes = item["axes"]
        if len(axes) > 2 or any(axis not in sets for axis in axes) or not isinstance(item.get("unit"), str) or not isinstance(item.get("says"), str):
            continue
        try:
            values = trimmed(item.get("values"), axes)
        except (IndexError, TypeError):
            continue
        if not numbers(values) or (axes and not values):
            continue  # a flag (true or false), or a set with no entity: nothing a layer reads
        constants.append({"id": item["id"], "unit": item["unit"], "axes": axes, "values": values, "from": item.get("from"), "says": item["says"]})
    unstated = [{"id": item["id"], "what": item.get("what"), "why": item["why"]} for item in view["unstated"] if isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("why"), str)]
    said = {item["id"] for item in unstated}
    unstated += [{"id": field, "what": "record", "why": "The run's recording subset does not list it (recording.subset.fields): the run kept only the fields that list names"} for field in not_recorded if field not in said]

    out = assemble(run, (), {}, sheet, records, [], [], derivation, parts, None, membranes=membranes, species=species, constants=constants, unstated=unstated)
    packaged = {item["id"]: item for item in out["sets"]}
    # What the view says of each set's entities is carried as written, for the named ones.
    for identifier, keys in (("cell", ("lifetimes",)), ("species", ("valence",)), ("outside", ("reservoir",)), ("membrane", ("pumps", "laws")), ("junction", ("laws",))):
        for key in keys:
            values = each(identifier, key)
            if identifier in packaged and values is not None and any(value is not None for value in values):
                packaged[identifier][key] = values
    for identifier in ("outside", "membrane"):
        if identifier in packaged and isinstance(sets.get(identifier, {}).get("holds"), str):
            packaged[identifier]["holds"] = sets[identifier]["holds"]
    # Every other set a packaged record lies on, or that the picture lays out, or of whose entities an operator states facts
    # (carries, direction, kinds, at): as the view gives it.
    stating = {identifier for identifier, item in sets.items() if any(key in item for key in PER_ENTITY)}
    used = {record["set"] for record in records if record.get("set")} | ({"face"} if "face" in sets else set()) | stating
    for identifier in [key for key in sets if key in used and key not in packaged]:
        item = {"id": identifier, "scale": sets[identifier].get("scale"), "ids": named(identifier)}
        for key in ("holds", "owner", "says"):
            if isinstance(sets[identifier].get(key), str):
                item[key] = sets[identifier][key]
        geometry = geometry_of(identifier)
        if geometry:
            item["geometry"] = geometry
        laws = each(identifier, "laws")
        if laws is not None and laws:
            item["laws"] = laws
        out["sets"].append(item)
        packaged[identifier] = item
    # The roles a set states, each with what it is: the ends its records' signs and differences name.
    for identifier, item in packaged.items():
        if isinstance(sets.get(identifier, {}).get("roles"), dict):
            item["roles"] = dict(sets[identifier]["roles"])
    # An operator's facts of each of its entities, as the view states them: the species each carries is the set's
    # `species` (what the page reads for a route); its declared direction and kind, and where it acts, as written.
    facts = []
    for identifier in [key for key in sets if key in stating]:
        item = packaged[identifier]
        carried, directions, kinds, places = each(identifier, "carries"), each(identifier, "direction"), each(identifier, "kinds"), each(identifier, "at")
        if carried is not None:
            item["species"] = carried
        for key, values in (("direction", directions), ("kinds", kinds), ("at", places)):
            if values is not None:
                item[key] = values
        # Where each entity acts, as the view states it (`at`: one entity of one set, by its id), is the set's place on the
        # picture where the view gives it no geometry of its own: a passive route stands on its junction.
        targets = {next(iter(value)) for value in places} if places else set()
        if places and "geometry" not in item and len(targets) == 1 and next(iter(targets)) in place and next(iter(targets)) in packaged:
            target = next(iter(targets))
            ids = sets[target].get("ids") or []
            item["geometry"] = {"kind": "on", "set": target, "index": [place[target][ids.index(next(iter(value.values())))] for value in places]}
        # Kinds are words, and a law's ID goes under `laws` (from d64fb664): where the set gives each entity's law, it is
        # named beside its kind, so the words keep what an older view's kind gave. An older view's kind is said as written.
        laws = each(identifier, "laws")
        said = []
        for k, entity in enumerate(item["ids"]):
            words = ", ".join(values[k] for values in (directions, kinds) if values)
            law = laws[k].get("law_id") if laws and isinstance(laws[k], dict) and isinstance(laws[k].get("law_id"), str) else None
            words = "; ".join(part for part in (words, f"law {law}" if law else "") if part)
            line = entity + (f" ({words})" if words else "")
            if carried:
                # Each species a route carries moves with its own flux, not as a coupled set: several are listed as such.
                value = carried[k]
                line += f" carries {value}" if isinstance(value, str) else f" carries {' and '.join(value)}" if len(value) == 1 else f" carries {', '.join(value)} (each with its own flux)"
            if places:
                line += f" at {next(iter(places[k].values()))}"
            said.append(line)
        facts.append(f"{identifier}: " + "; ".join(said))
    if facts:
        several = any(isinstance(value, list) and len(value) > 1 for identifier in stating for value in each(identifier, "carries") or [])
        derivation.append(
            f"What the run's operators state of each of their entities is carried as the view gives it ({' | '.join(facts)}); a route's species is the one the view says it carries."
            + (" Where an entity carries more than one species, each moves with its own flux, not as a coupled set: only a stated per_cycle couples species." if several else "")
        )
    operators = set((stated_run.get("composition") or {}).get("operators") or []) if isinstance(stated_run.get("composition"), dict) else set()
    # The inner model's kinds' sets (passive routes, say) carry species too, but no operator of the run moves those species
    # in or out of a cell by them: only an operator's sets are read for the secreted species.
    carriers = [identifier for identifier in sets if identifier in stating and each(identifier, "carries") is not None and sets[identifier].get("owner") in operators]
    if carriers:
        # The species the run's operators' entities carry, make or clear, as the view states it of each: the view calls no species secreted.
        carried = {species_id for identifier in carriers for value in each(identifier, "carries") for species_id in ([value] if isinstance(value, str) else value)}
        secreted = [identifier for identifier in species if identifier in carried]
        if secreted:
            packaged["species"]["secreted"] = secreted
            several = any(isinstance(value, list) and len(value) > 1 for identifier in carriers for value in each(identifier, "carries"))
            derivation.append(
                f"The species that the run's operators carry, make or clear ({', '.join(secreted)}, by what the view states of each of their entities: {', '.join(carriers)}) is taken as the species the run secretes: "
                "the view states which species each entity carries, and does not itself call any species secreted."
                + (" Where an entity carries more than one, each moves with its own flux, and each is taken on its own." if several else "")
            )
    else:
        # The species the run's operators declare: the view names the operator that declares each, and does not call it secreted.
        identities = each("species", "species") or []
        declared_by = [(species[k], (identity.get("identity") or {}).get("source")) for k, identity in enumerate(identities) if isinstance(identity, dict) and isinstance(identity.get("identity"), dict)]
        secreted = [identifier for identifier, source in declared_by if source in operators]
        if secreted:
            packaged["species"]["secreted"] = secreted
            derivation.append(
                f"The species an operator of the run declares ({', '.join(f'{identifier}, by {source}' for identifier, source in declared_by if source in operators)}) is taken as the species the run secretes: "
                "the view names the operator that declares it, and does not itself call it secreted."
            )
    # What the view states that the page does not draw, each named in the view's own words and not packaged: the channel set's
    # factors (with the note on channel_availability, which the page does not show either), a cycle kind's coupled
    # stoichiometry on a set of its own (per_cycle; the one the page draws is a membrane pump's, in the membrane set's
    # pumps), a membrane's calcium pump, and any key the adapter does not know.
    if "factors" in channel:
        named_factors = each("channel", "factors") or []
        held_note = next((record["note"] for record in view["records"] if isinstance(record, dict) and record.get("field") == "channel_availability" and isinstance(record.get("note"), str) and record["note"]), None)
        derivation.append(
            "The view states, for each channel population, the factor sources by which the routing door scales its availability at every stage (factors, in declared order): "
            + "; ".join(f"{entity}: {', '.join(sources) if sources else 'none'}" for entity, sources in zip(named("channel"), named_factors))
            + ". They are not packaged: no layer of the page reads a population's availability."
            + (f" Of its record channel_availability, which is not packaged either, the view says: {held_note}{'' if held_note.endswith(('.', '!', '?')) else '.'}" if held_note else "")
        )
    cycled = [identifier for identifier, item in sets.items() if "per_cycle" in item]
    if cycled:
        derivation.append(
            f"The view gives per_cycle on {', '.join(f'the set {identifier}' for identifier in cycled)}: a coupled stoichiometry, by mode and population, as the view states it. "
            "It is not packaged: no layer of the page draws a cycle kind's modes. The one coupled movement the page draws is a membrane pump's, from what one cycle of it moves (the membrane set's pumps, per_cycle)."
        )
    calcium = [entity for entity, pump in zip(named("membrane"), each("membrane", "calcium_pumps") or []) if pump is not None] if "membrane" in sets else []
    if calcium:
        derivation.append(f"The view gives {len(calcium)} membrane(s) a calcium pump (calcium_pumps: its law and what one cycle moves, per_cycle): {', '.join(calcium)}. They are not packaged: no layer of the page reads a calcium pump's cycles.")
    unread = unread_keys(view)
    if unread:
        derivation.append(f"The view gives what the adapter does not read, and none of it is packaged: {'; '.join(unread)}. Each is named here, never refused.")
    # The spaces outside the cells, where the viewer can stand them beside the cells: not beside the run's own geometry,
    # which places the cells and gives the outside nodes no tiles of the adapter's.
    if (built is not None or getattr(sheet, "prescribed", False)) and "outside" in packaged:
        derivation.append("The outside nodes are not drawn: the cells stand where the run's own geometry places them, and the adapter lays out no tiles of its own beside them.")
    elif membranes and "outside" in packaged:
        face_links = packaged.get("face", {}).get("geometry") if "face" in packaged else None
        nodes = membranes["nodes"]
        faces_like = [{"sender": nodes[a], "receiver": nodes[b]} for a, b in face_links["ends"]] if face_links and face_links.get("between") == membranes["set"] else []
        world = world_layout({"faces": faces_like}, sheet, membranes, derivation)
        if world is not None:
            packaged["cell"]["geometry"] = {"kind": "polygons", "vertices": world.vertices, "faces": world.cells}
            packaged["outside"]["geometry"] = {"kind": "polygons", "vertices": world.vertices, "faces": world.outside}
    # The view's events, each at an entity by its number here.
    events = []
    for event in view["events"]:
        if not (isinstance(event, dict) and is_number(event.get("time")) and isinstance(event.get("at"), dict) and len(event["at"]) == 1):
            continue
        item = {"time": event["time"], "kind": event.get("kind"), "layer": event.get("layer"), "label": event.get("label") or None}
        for end in ("at", "from"):
            if isinstance(event.get(end), dict) and len(event[end]) == 1:
                ((identifier, entity),) = event[end].items()
                if identifier in packaged and entity in packaged[identifier]["ids"]:
                    item[end] = {"set": identifier, "index": packaged[identifier]["ids"].index(entity)}
        if "at" in item:
            events.append(item)
    # A replay's timeline runs over its records: an event the run states outside them (a looping package keeps only its
    # last period) is not carried as an event, and the derivation says how many there are and when, before and after.
    def inside(item):
        return not ((item["time"] < times[0] and not math.isclose(item["time"], times[0], **TIME_CLOSE)) or (item["time"] > times[-1] and not math.isclose(item["time"], times[-1], **TIME_CLOSE)))

    stated_count = len(events)
    before = sorted(item["time"] for item in events if not inside(item) and item["time"] < times[0])
    after = sorted(item["time"] for item in events if not inside(item) and item["time"] > times[-1])
    events = [item for item in events if inside(item)]
    if before or after:
        kinds = sorted({item["kind"] for item in view["events"] if isinstance(item, dict) and isinstance(item.get("kind"), str)})
        said = []
        for times_, where, edge in ((before, "before its recorded period, which begins", times[0]), (after, "after its recorded period, which ends", times[-1])):
            if times_:
                span = f"at {times_[0]:g} s" if len(times_) == 1 else f"the first at {times_[0]:g} s, the last at {times_[-1]:g} s"
                said.append(f"{len(times_)} {'lies' if len(times_) == 1 else 'lie'} {where} at {edge:g} s: {span}")
        kind_words = " or ".join(f"'{kind}'" for kind in kinds)
        derivation.append(
            f"Of the run's {stated_count} events (of the kind {kind_words}), {'; '.join(said)}. They are not shown, because the replay runs over its records; "
            f"the {len(events)} that lie within them are."
        )
    if events:
        out["events"] = sorted(events, key=lambda item: item["time"])
    # The view's layers that a packaged record or event belongs to, each with its owner and how it is represented, as written.
    in_use = {record.get("layer") for record in records} | {event.get("layer") for event in events}
    out["layers"] = [{"id": layer["id"], "label": layer.get("label"), "representation": layer.get("representation"), "owner": layer.get("owner")} for layer in view["layers"] if isinstance(layer, dict) and layer.get("id") in in_use]
    out["time"]["base"] = {"id": timeline, "says": bases[timeline].get("says"), "others": [{"id": identifier, "says": base.get("says"), "rows": sum(part["rows"][1] - part["rows"][0] for part in base.get("files") or [] if isinstance(part, dict) and isinstance(part.get("rows"), list) and len(part["rows"]) == 2)} for identifier, base in others.items()]}
    # Which state a record saved at an event's time holds: the run's own sentence, carried as written.
    event_rows = (view["time"] or {}).get("event_rows")
    if event_rows is not None:
        if not (isinstance(event_rows, str) and event_rows.strip()):
            raise Refused(f"{name}: its view's time.event_rows does not say in words which state a record at an event's time holds")
        out["time"]["event_rows"] = event_rows
        derivation.append(f"Which state a record saved at an event's time holds is the run's own statement (time.event_rows), carried as written: {event_rows}")
    # Which slots restart when an operator retires one: the run's own statement (resets.mask), carried in each record's `resets`.
    masks = sorted({f"{record.get('field') or record['id']}: {record['resets']['mask']}" for record in records if isinstance(record.get("resets"), dict) and "mask" in record["resets"]})
    if masks:
        derivation.append(
            "Which slots restart when an operator retires one is the run's own statement, carried in each such record's resets: those where the named mask of the record's set closes at the event "
            f"(the mask's merged view, {VIEW_PREFIX}<mask>, where the run saved it). {'; '.join(masks)}."
        )
    # One period of a looping run (FR-11): the view's own block, checked and carried in the shape the page reads (src/layers/loop.js, readLoop).
    if "loop" in view:
        # The writer writes a loop only for a run that names its engine's source and saved its observed rows: a caller's
        # label is no engine's word for a looping package's revision.
        if source is None:
            raise Refused(f"{name}: its view gives a loop for a run that names no engine source (run.source): a looping run names the engine that made it, from its execution snapshot")
        if timeline != "observation":
            raise Refused(f"{name}: its view gives a loop for a run that saved no observed rows")
        out["loop"] = looped(name, view["loop"], named("cell"), times, [record.get("id") for record in view["records"] if isinstance(record, dict)])
        derivation.append(
            f"The run says it is one period of a loop (view.loop, carried as written): {out['loop']['period']} s of the cell {out['loop']['cell']}, for the species {out['loop']['species']}; "
            f"its last record meets its first within {out['loop']['closes']['within']}, and its tolerance is {out['loop']['closes']['tolerance']}."
        )
        for group in out["loop"].get("not_measured") or []:
            derivation.append(f"The loop's closure leaves out {len(group['records'])} record(s), in the run's words '{group['why']}': {', '.join(group['records'])}. Not measured says nothing of how they stand at the seam.")
        if out["loop"]["closes"].get("zero"):
            derivation.append(f"Identically zero over the loop, as the run states it (closes.zero), so not divided by in its closure: {', '.join(out['loop']['closes']['zero'])}.")
    missing = sorted({record["set"] for record in records if record.get("set")} - set(packaged))
    if missing:
        raise Refused(f"{name}: records lie on {', '.join(missing)}, which its view does not list as a set")
    notes = {"records": count, "cells": len(sheet.cells), "junctions": len(sheet.junctions), "events": len(events), "revision": run["revision"], "pitch_um": sheet.pitch, "windows": len(bases[timeline].get("files") or [])}
    notes["parts"] = {part["id"]: part["payload"].data() for part in parts}
    return out, payload.data(), notes


def adapt_history(root, name, experiment, entry):
    """One run written by the engine's shared output path (a folder that holds resolved_config.json and its arrays)."""
    if not RUN_FOLDER.match(name):
        raise Refused(f"'{name}' is not a run folder's name")
    folder = root / name
    if not folder.is_dir():
        raise Refused(f"no run folder {name} in {root.name}/")
    # A run with the engine's own view beside its files is packaged from that view, and from none of the adapter's tables.
    if (folder / VIEW_FILE).is_file():
        return adapt_engine_view(root, name, experiment, entry)
    config = read_json(folder / "resolved_config.json")
    tissue = tissue_of(config)
    if tissue is None:
        raise Refused(f"{name}: its definition lists no cells, membranes, junctions and outside nodes the adapter can read")
    # A run folder the run-fixture tool wrote says so itself: its numbers are invented, and the view carries that word.
    example = read_json(folder / EXAMPLE_FILE) if (folder / EXAMPLE_FILE).is_file() else None
    if example is not None and not (isinstance(example, dict) and example.get("example") is True and isinstance(example.get("says"), str) and example["says"]):
        raise Refused(f"{name}: its {EXAMPLE_FILE} does not say in words that the run is an example")
    model_id = (config.get("model") or {}).get("id")
    family = model_id in TISSUE_FAMILY
    derivation = []
    sheet = lay_out(name, tissue, derivation, row=True)
    fields, times, windows = history_arrays(name, folder, derivation)
    # Who computed each readout, where the run's own manifest says it (a composition's field map): the inner model, or an operator's law.
    manifest = read_json(folder / "manifest.json") if (folder / "manifest.json").is_file() else {}
    owners = ((manifest.get("field_owners") or {}).get("observations") or {}) if isinstance(manifest, dict) else {}
    if example:
        owners = {}  # no model computed an example's numbers: none is named as their owner
    count = len(times)
    # The definition as the constants and the surroundings are read from: the tissue with the run's own experiment.
    definition = config if tissue is config.get("model") else {"model": tissue, "experiment": config.get("experiment") or {}}
    membranes = membranes_of(definition, sheet)
    species = species_of(definition) or []
    index_of = {key: {item.get("id"): number for number, item in enumerate(tissue.get(HISTORY_SETS[key]) or []) if isinstance(item, dict)} for key in HISTORY_SETS}
    sizes = {key: len(tissue.get(listed) or []) for key, listed in HISTORY_SETS.items()}
    sizes["species"] = len(species)
    # The routes of the operators that carry a species across a membrane, where each names a membrane and a species of the run.
    composed = config.get("model") or {}
    routes = [route for operator in composed.get("operators") or [] if isinstance(operator, dict) and operator.get("law") in EXCHANGE_LAWS for route in operator.get("routes") or []]
    if not (membranes and all(isinstance(route, dict) and isinstance(route.get("id"), str) and route.get("patch") in membranes["ids"] and route.get("species") in species for route in routes)) or len({route["id"] for route in routes}) != len(routes):
        routes = []
    sizes["route"] = len(routes)

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
    inner_model = (config.get("model") or {}).get("inner_model")

    def owner_of(field):
        """The model or law that computed a field: the run's manifest where it says, the model otherwise."""
        said = owners.get(field)
        said = said[-1] if isinstance(said, list) and said else said
        if said == "inner" and isinstance(inner_model, str):
            return inner_model
        if isinstance(said, str) and said != "inner":
            return said
        return model_id if isinstance(model_id, str) and not example else None
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

    moved_sign = exchange_sign(fields, count, species, sheet, membranes, routes) if routes else None
    if moved_sign:
        signs["exchange_moved_fmol"] = moved_sign

    totals = set()  # fields the adapter read as totals from the arrays themselves

    def declare(target, field, entity, n, values, species_id=None, part=None):
        table = tissue_field(field) if family else None
        unit = (table or {}).get("unit") or next((unit_ for suffix, unit_ in (("_V", "V"), ("_pJ", "pJ"), ("_fmol", "fmol")) if field.endswith(suffix)), "")
        sign = signs.get(field) or (table or {}).get("sign")
        label = HISTORY_FIELDS[field][1] if species_id is None else f"{HISTORY_FIELDS[field][1]}: {species_id}"
        layer = HISTORY_FIELDS[field][2]
        used_layers.add(layer)
        extra = {"field": field, "species": species_id} if species_id is not None else {}
        kind = (table or {}).get("kind")
        monotone = (table or {}).get("monotone")
        if kind is None and layer == "turnover" and all(values[k] == 0 for k in range(n)) and all(values[step * n + k] >= values[(step - 1) * n + k] for step in range(1, count) for k in range(n)):
            # An operator's ledger the viewer's table does not list: it starts at nought and never falls, so it is read as a total since the start.
            kind, monotone = "cumulative", "non-decreasing"
            totals.add(field)
        if kind is None and field == "exchange_moved_fmol" and field in signs:
            kind = "cumulative"  # the cells' amounts add up with it as a total since the start: the same check that gives its sign
        return describe(
            target, field if species_id is None else f"{field}.{species_id}", label, unit, ["time", entity], "float32", (count, n), values,
            set=entity, layer=layer, kind=kind, owner=owner_of(field), sign=sign, part=part, monotone=monotone, note=(table or {}).get("note"), **extra,
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
        derivation.append(f"The run has no {' and no '.join(PLACE_WORDS.get(place) or HISTORY_SETS[place] for place in places)}, so the fields that lie on them are empty and are not packaged: {', '.join(empty)}.")
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
        if sign["by"].startswith(EXCHANGE_SIGN_BY):
            derivation.append(f"Which way {HISTORY_FIELDS[field][1].lower()} is positive is not declared by the run's files. It is {sign['by']}.")
        else:
            derivation.append(f"Which way {HISTORY_FIELDS[field][1].lower()} is positive is not declared by the run. It is read from its arrays: {sign['by'].split(': ', 1)[1]}.")
    if totals:
        derivation.append(f"Read as totals since the run's start, because their arrays begin at nought and never fall: {', '.join(sorted(totals))}. The viewer's table does not list these fields, and the run's files do not say what kind of number they are.")
    if owners:
        derivation.append("Each record's owner is the one the run's own manifest names for that readout (its field map): the inner model, or the operator's law.")
    stated = layers_stated(entry, derivation)
    summary = read_json(folder / "summary.json") if (folder / "summary.json").is_file() else {}
    plan = {"execution": config.get("execution") or {}, "model": {key: value for key, value in (config.get("model") or {}).items() if not isinstance(value, (list, dict))}}
    parameters, readouts = copied(entry, plan, summary if isinstance(summary, dict) else {}, {})
    derivation.append("Parameters are copied under their own names from resolved_config.json (execution and the model's plain values) and readouts from summary.json. The run's files name no revision of the engine by its commit, so none is given.")
    models = [model_id] if isinstance(model_id, str) else []
    if isinstance(composed.get("inner_model"), str):
        models += [composed["inner_model"], *[operator.get("law") for operator in composed.get("operators") or [] if isinstance(operator, dict) and isinstance(operator.get("law"), str)]]
    if example:
        models = []  # no engine model ran
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
        # The ions each population lets through, as the definition lists them: a population with one is drawn in that ion's colour.
        permeant = [[item.get("species_id") for item in channel.get("permeant_ions") or [] if isinstance(item, dict) and item.get("species_id") in species] for channel in channels]
        if any(permeant):
            view["sets"][-1]["species"] = permeant
    # The exchange routes, each on its membrane, with the species it carries.
    if routes and any(record.get("set") == "route" for record in records):
        view["sets"].append({"id": "route", "holds": "route", "scale": "cell", "ids": [route["id"] for route in routes], "geometry": {"kind": "on", "set": "membrane", "index": [membranes["ids"].index(route["patch"]) for route in routes]}, "species": [route["species"] for route in routes]})
        derivation.append("The exchange routes are those the run's definition lists for its exchange operator: each names the membrane it lies on and the species it carries.")
    # What one cycle of each membrane's pump moves, as its declaration gives it: a law's own numbers, which nothing the run schedules changes.
    membrane_set = next((item for item in view["sets"] if item["id"] == "membrane"), None)
    declared_pumps = {membrane.get("id"): membrane.get("pump") for membrane in tissue.get("membranes") or [] if isinstance(membrane, dict)}
    if membrane_set is not None:
        # In the shape the engine's own run view gives a pump: what one cycle moves, by role, a positive count into the cell.
        pumps = []
        for identifier in membrane_set["ids"]:
            pump = declared_pumps.get(identifier) if isinstance(declared_pumps.get(identifier), dict) else {}
            moves, roles = pump.get("stoichiometry"), pump.get("roles") if isinstance(pump.get("roles"), dict) else {}
            if isinstance(moves, dict) and moves and all(key in species and is_number(value) for key, value in moves.items()):
                role_of = {ion: role for role, ion in roles.items()}
                pumps.append({"id": pump.get("id"), "law_id": pump.get("law"), "per_cycle": [{"role": role_of.get(ion), "species": ion, "count": count} for ion, count in moves.items()], "per_cycle_sign": "inward-positive"})
            else:
                pumps.append(None)
        if any(pumps):
            membrane_set["pumps"] = pumps
            derivation.append("What one cycle of each membrane's pump moves is the pump's own declaration in the run's definition (its stoichiometry): a positive count is carried into the cell.")
    # The outside nodes: which are held baths, and where the viewer stands them; the species the run's secretion operators name.
    outside = next((item for item in view["sets"] if item["id"] == "outside"), None)
    if outside is not None:
        outside["reservoir"] = [node.get("reservoir") is True for node in tissue.get("extracellular") or []]
        world = world_layout(tissue, sheet, membranes, derivation)
        if world is not None:
            cells_set = next(item for item in view["sets"] if item["id"] == "cell")
            cells_set["geometry"] = {"kind": "polygons", "vertices": world.vertices, "faces": world.cells}
            outside["geometry"] = {"kind": "polygons", "vertices": world.vertices, "faces": world.outside}
    named = []
    for operator in composed.get("operators") or []:
        if isinstance(operator, dict) and operator.get("law") in SECRETION_LAWS:
            named += [item.get("id") for item in operator.get("species") or [] if isinstance(item, dict) and item.get("id") in species and item.get("id") not in named]
    species_set = next((item for item in view["sets"] if item["id"] == "species"), None)
    if named and species_set is not None:
        species_set["secreted"] = named
        derivation.append(f"The secreted species ({', '.join(named)}) is the one the run's definition names in its operators that make, clear and exchange a species.")
    listed = {item["id"] for item in view["sets"]}
    missing = sorted({record["set"] for record in records if record.get("set")} - listed)
    if missing:
        raise Refused(f"{name}: records lie on {', '.join(missing)}, which the definition does not list in a form the adapter can read")
    if example:
        view["example"] = {"says": example["says"], "made_by": example.get("made_by") if isinstance(example.get("made_by"), str) else None}
        derivation.insert(0, f"{example['says']}. Every number of this run was written by the run-fixture tool in the layout of the engine's shared output path. No engine ran, and no model is named as the owner of a record.")
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


SUMMARY_FORMAT = "cells.experiment_summary@1"


def sweeps_of(path, rows):
    """An experiment's sweeps for the catalogue, read from its summary and from nothing else.

    The summary (cells.experiment_summary@1, schema/RUN_VIEW.md, "A sweep's chart") lists, for
    each sweep, its parameter and its readouts with their names and units, and for each arm the
    arm's name, its parameter's value, its readouts' values and, where the experiment states
    one, its own reference value for a readout, with the reference's words. Each arm is joined
    to the run of this call whose arm it names (null where none is packaged). Nothing is
    computed from the numbers: they are copied as the summary states them, and a summary that
    does not state what the chart reads is refused.
    """
    summary = read_json(path)
    if not isinstance(summary, dict) or summary.get("format") != SUMMARY_FORMAT:
        raise Refused(f"{path.name} is not an experiment summary ({SUMMARY_FORMAT})")
    def named(item, where):
        if not (isinstance(item, dict) and all(isinstance(item.get(key), str) and (item[key] or key == "unit") for key in ("id", "label", "unit"))):
            raise Refused(f"{path.name}: {where} needs an id, a label and a unit")

    def finite(value):
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

    by_arm = {}
    for row in rows:
        by_arm.setdefault(row["arm"], row["id"])
    sweeps = []
    for sweep in summary.get("sweeps") or []:
        if not (isinstance(sweep, dict) and isinstance(sweep.get("id"), str) and isinstance(sweep.get("label"), str)):
            raise Refused(f"{path.name}: a sweep needs an id and a label")
        named(sweep.get("parameter"), f"sweep {sweep['id']}'s parameter")
        readouts = sweep.get("readouts")
        if not (isinstance(readouts, list) and readouts):
            raise Refused(f"{path.name}: sweep {sweep['id']} lists no readout")
        for readout in readouts:
            named(readout, f"a readout of sweep {sweep['id']}")
        ids = [readout["id"] for readout in readouts]
        reference = sweep.get("reference")
        if reference is not None and not (isinstance(reference, dict) and isinstance(reference.get("label"), str) and reference["label"]):
            raise Refused(f"{path.name}: sweep {sweep['id']}'s reference needs the summary's words for it (label)")
        arms, seen = [], set()
        for arm in sweep.get("arms") or []:
            if not (isinstance(arm, dict) and isinstance(arm.get("arm"), str) and finite(arm.get("parameter"))):
                raise Refused(f"{path.name}: an arm of sweep {sweep['id']} needs its name and its parameter's value")
            if arm["arm"] in seen:
                raise Refused(f"{path.name}: sweep {sweep['id']} lists arm {arm['arm']} twice")
            seen.add(arm["arm"])
            values = arm.get("readouts") or {}
            if not (isinstance(values, dict) and set(values) <= set(ids) and all(finite(value) for value in values.values())):
                raise Refused(f"{path.name}: arm {arm['arm']} gives a readout the sweep does not list, or one that is not a number")
            refs = arm.get("reference") or {}
            if refs and (reference is None or not (isinstance(refs, dict) and set(refs) <= set(ids) and all(finite(value) for value in refs.values()))):
                raise Refused(f"{path.name}: arm {arm['arm']} gives a reference value the sweep does not name")
            item = {"arm": arm["arm"], "run": by_arm.get(arm["arm"]), "parameter": arm["parameter"], "readouts": {key: values[key] for key in ids if key in values}}
            # The arm's place against a threshold, where the summary states it, carried as given (its label, side and source).
            if isinstance(arm.get("place"), dict) and isinstance(arm["place"].get("relative_to_x2"), str) and isinstance(arm["place"].get("source"), str):
                item["place"] = {key: arm["place"][key] for key in ("D", "x2", "ratio_to_x2", "relative_to_x2", "side", "source") if key in arm["place"]}
            if refs:
                item["reference"] = {key: refs[key] for key in ids if key in refs}
            arms.append(item)
        if len(arms) < 2:
            raise Refused(f"{path.name}: sweep {sweep['id']} needs two arms or more for a chart")
        out = {"id": sweep["id"], "label": sweep["label"], "parameter": {key: sweep["parameter"][key] for key in ("id", "label", "unit")}, "readouts": [{key: readout[key] for key in ("id", "label", "unit")} for readout in readouts], "arms": arms}
        if reference is not None:
            out["reference"] = {key: reference[key] for key in ("label", "source") if isinstance(reference.get(key), str)}
        if isinstance(sweep.get("plain"), str):
            out["plain"] = sweep["plain"]
        # What the summary states of the sweep's world as data: the tumor's cells as seeded, and the species by name.
        if isinstance(sweep.get("tumor_cells"), list) and all(isinstance(cell, str) for cell in sweep["tumor_cells"]):
            out["tumor_cells"] = list(sweep["tumor_cells"])
        if isinstance(sweep.get("species"), dict) and all(isinstance(value, str) for value in sweep["species"].values()):
            out["species"] = dict(sweep["species"])
        sweeps.append(out)
    return sweeps


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


REFUSED_FILE = "REFUSED.json"  # a folder of a pick an engine check refused: its record up to the refusal, and no view
# A run folder's manifest (schema/EXPERIMENT_PACKAGE.md; the names are proposals until the engine's lead accepts them). Where a
# run folder holds one, its packages are the arms, with the sidecars each names, and its refused picks are those it lists: in
# place of index.json, of the overlay's `sidecar`, and of the search for folders that hold a view or REFUSED.json. Nothing
# else of it is read here: the experiment's words still come from the overlay. tools/check_package.py checks the whole of it.
MANIFEST_FILE = "package.json"
MANIFEST_FORMAT = "cells.experiment_package@1"
MANIFEST_NOTES = set()


def package_manifest(root):
    """The run folder's manifest as {"arms": [arm], "sidecars": {arm: [file]}, "refused": [(arm, file)]}, or None where it
    has none. A package is read from the folder named as its arm; one of a kind the adapter does not read is named and left
    out. A manifest the adapter cannot read so is refused, never passed over."""
    path = Path(root) / MANIFEST_FILE
    if not path.is_file():
        return None
    where = f"{Path(root).name}/{MANIFEST_FILE}"
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError):
        raise Refused(f"{where} is not JSON") from None
    if not (isinstance(manifest, dict) and manifest.get("format") == MANIFEST_FORMAT and manifest.get("level") == "source"):
        raise Refused(f"{where} is not the manifest of a source package ({MANIFEST_FORMAT}, level source)")
    packages, refused = manifest.get("packages"), manifest.get("refused", [])
    if not (isinstance(packages, list) and packages and all(isinstance(item, dict) for item in packages) and isinstance(refused, list) and all(isinstance(item, dict) for item in refused)):
        raise Refused(f"{where} lists no packages, or a package or a refused pick that is not an object (packages, refused)")
    plain = lambda text: isinstance(text, str) and bool(ARM_NAME.match(text)) and bool(text.strip("."))  # noqa: E731
    arms, sidecars, picks, seen = [], {}, [], set()
    for item in packages:
        arm, said = item.get("arm"), item.get("sidecars", [])
        if not (plain(arm) and item.get("path") == arm):
            raise Refused(f"{where} lists a package that is not read from the folder named as its arm (arm, path)")
        if arm in seen:
            raise Refused(f"{where} names the arm {arm} twice")
        seen.add(arm)
        if item.get("kind") != VIEW_FORMAT:
            note = f"note: {where}: the package {arm} is of the kind {item.get('kind')!r}, which the adapter does not read; it is left out"
            if note not in MANIFEST_NOTES:  # said once, however often the manifest is read
                MANIFEST_NOTES.add(note)
                print(note, file=sys.stderr)
            continue
        if not (isinstance(said, list) and all(isinstance(file, str) and STATED_FILE.match(file) for file in said)):
            raise Refused(f"{where}: the package {arm} names a file beside it that is not a JSON file's plain name (sidecars)")
        arms.append(arm)
        sidecars[arm] = list(said)
    for item in refused:
        arm, file = item.get("arm"), item.get("file")
        if not (plain(arm) and plain(file)) or arm in seen:
            raise Refused(f"{where} lists a refused pick that is not one arm, once, with its file's plain name (refused: arm, file)")
        seen.add(arm)
        picks.append((arm, file))
    return {"arms": arms, "sidecars": sidecars, "refused": picks}


def runs_in_index(folder):
    """The runs a run folder's own index.json chooses (`selected`, else every package whose view was written): so that
    arms added to the folder later are data alone. A run folder with no index: every package in it that holds the
    engine's view (view.json), by name. A run folder with a manifest (package.json): its packages, in its order."""
    manifest = package_manifest(folder)
    if manifest is not None:
        if not manifest["arms"]:
            raise Refused(f"{folder.name}/{MANIFEST_FILE} lists no package of a kind the adapter reads ({VIEW_FORMAT})")
        return list(manifest["arms"])
    path = folder / "index.json"
    if not path.is_file():
        names = sorted(item.name for item in folder.iterdir() if item.is_dir() and (item / VIEW_FILE).is_file() and ARM_NAME.match(item.name))
        if not names:
            raise Refused(f"the selection reads its runs from {folder.name}/, which has no index.json and no package with a view ({VIEW_FILE})")
        return names
    index = read_json(path)
    names = index.get("selected") if isinstance(index.get("selected"), list) else [package.get("arm") for package in index.get("packages") or [] if isinstance(package, dict) and package.get("view") == "written"]
    if not (names and all(isinstance(name, str) and ARM_NAME.match(name) for name in names)):
        raise Refused(f"{folder.name}/index.json chooses no run by its folder's name")
    return names


def refused_picks(root, sweeps):
    """The arms of a run folder that an engine check refused (a folder holding REFUSED.json and no view), named and no
    more: each by its arm and its value of the sweep's parameter, as the file states them. Nothing else of the file is
    read: not its error, not when it was refused. A run folder with a manifest names them itself (`refused`), in its order."""
    manifest = package_manifest(root)
    if manifest is not None:
        picks = [(root / arm, file) for arm, file in manifest["refused"]]
    else:
        picks = [(folder, REFUSED_FILE) for folder in sorted(root.iterdir()) if folder.is_dir() and (folder / REFUSED_FILE).is_file() and not (folder / VIEW_FILE).is_file()]
    found = []
    for folder, file in picks:
        if len(sweeps) != 1:
            raise Refused(f"{folder.name}: a refused pick is named by its sweep's parameter, and the summary states {len(sweeps)} sweeps, not one")
        said, parameter = read_json(folder / file), sweeps[0]["parameter"]["id"]
        if not (isinstance(said, dict) and said.get("arm") == folder.name and said.get("status") == "refused" and finite(said.get(parameter))):
            raise Refused(f"{folder.name}/{file} does not name its own arm as refused with its value of {parameter} (arm, status, {parameter})")
        found.append({"arm": folder.name, "sweep": sweeps[0]["id"], "parameter": said[parameter], "file": file})
    return found


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
            names = runs_in_index(root) if chosen.get("runs") == "index" else list(chosen.get("runs") or [])
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
            # The runs may stand in a run folder nested inside the evidence folder: named folder by folder (`within`), never a path.
            within = item.get("within") or []
            if not (isinstance(within, list) and all(isinstance(name, str) and ARM_NAME.match(name) for name in within)):
                raise Refused(f"the selection's run folder for {experiment} is named folder by folder (within), never as a path")
            root = parent / folder
            for name in within:
                root = root / name
            if not root.is_dir():
                raise Refused(f"the run folder {'/'.join([folder, *within])} is not there")
            listed = item.get("runs")
            jobs.append((experiment, root, list(arguments.run) or (runs_in_index(root) if listed == "index" else list(listed or []))))
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
            # An example (invented numbers) stands under "Examples" and never among experiments; an experiment's run is never listed as one.
            if bool(view.get("example")) != (entry.get("example") is True):
                raise Refused(f"{name}: {'the run is an example with invented numbers, and its catalogue entry does not say so' if view.get('example') else 'its catalogue entry calls it an example, and the run folder does not'}")
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
            if view.get("example"):
                listed[-1]["example"] = True
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
        # How the runs' parts are published (parts_together) is the export's to read from the overlay, not the catalogue's.
        written_entry = {key: value for key, value in entry.items() if key not in ("adapter", "summary", "sidecar", "parts_together")}
        # An experiment whose summary lists arms with a parameter and readouts: its sweeps, for the chart (a file's name in its evidence folder, never a path).
        if isinstance(entry.get("summary"), str):
            if "/" in entry["summary"] or entry["summary"].startswith("."):
                raise Refused(f"{experiment}: its summary is named by a file's name in its evidence folder, not a path")
            written_entry["sweeps"] = sweeps_of(Path(root) / entry["summary"], listed)
            for sweep in written_entry["sweeps"]:
                print(f"{experiment}: sweep {sweep['id']}: {len(sweep['arms'])} arms, {sum(1 for arm in sweep['arms'] if arm['run'])} with a run in this call")
            # Picks an engine check refused, beside the packages: named, never hidden, and never drawn as a run.
            if entry.get("refused_picks") is True:
                written_entry["refused_picks"] = refused_picks(Path(root), written_entry["sweeps"])
                print(f"{experiment}: {len(written_entry['refused_picks'])} pick(s) refused by an engine check, named from their {REFUSED_FILE}")
        adapted[experiment] = (written_entry, listed)

    index, kept = merged_catalogue(out, existing, list(curated), adapted)
    # The page's other examples, which open a view of their own (a model system's entry, e.g. GARD): named by the overlay, listed with
    # the experiments. An overlay that says nothing of them (a fixture's, adapting one more experiment) keeps those the catalogue had.
    said = read_json(arguments.overlay)
    before = json.loads((out / "index.json").read_text(encoding="utf-8")) if "doors" not in said and (out / "index.json").is_file() else {}
    doors = said["doors"] if "doors" in said else before.get("doors") or []
    if not (isinstance(doors, list) and all(isinstance(door, dict) and isinstance(door.get("entry"), str) and door["entry"] for door in doors)):
        raise Refused("the overlay's doors each name an entry")
    if doors:
        index["doors"] = [{"entry": door["entry"]} for door in doors]
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
