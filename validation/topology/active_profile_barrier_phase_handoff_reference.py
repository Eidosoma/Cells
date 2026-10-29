"""Independent complete ionic INIT-to-SIM carry and instantaneous equations.

The original physical anchors and all nineteen physical arrays are retained.
Only the phase clock resets.  The existing independent 56-law equations and
Decimal membrane/ECM coefficient arithmetic supply the stage oracle.  This
module does not integrate trajectories or call Cells/JAX code.  Cryptographic
layout replay and public runner admission remain separate software checks.
"""

import ast
import hashlib
import math
import sys
from copy import deepcopy
from pathlib import Path
from types import ModuleType

import numpy as np

from validation.transport import active_profile_barrier_interventions_reference as scheduled

REQUEST_KIND = "cells.active_profile_barrier_phase_handoff_request@1"
MODEL_ID = "resolved_active_profile_barrier_epoch@1"
SCHEDULED_ID = "resolved_active_profile_barriers@1"
CAPACITIES = (
    "capacity",
    "extracellular_capacity",
    "membrane_capacity",
    "edge_capacity",
    "face_capacity",
    "channel_capacity",
)
flatten, unpack = scheduled.flatten, scheduled.unpack


def active_owner_counts(raw):
    """Count declared owners independently of packed or padded array shapes."""
    model = raw["model"]
    families = {
        "cells": ("amount_increment",),
        "extracellular": (
            "extracellular_amount_increment",
            "reservoir_supplied",
            "electrode_charge_transferred_C",
            "reservoir_work_pJ",
            "electrode_work_pJ",
        ),
        "membranes": (
            "membrane_transferred",
            "membrane_dissipated_energy_pJ",
            "pump_cycles",
            "pump_dissipated_energy_pJ",
            "metabolic_work_pJ",
        ),
        "junctions": ("junction_transferred", "junction_dissipated_energy_pJ", "junction_gate"),
        "faces": ("face_transferred", "face_dissipated_energy_pJ"),
        "channels": ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ"),
    }
    return {name: len(model[family]) for family, names in families.items() for name in names} | {
        "phase_clock_s": 1
    }


def target_definition(epoch):
    value = deepcopy(epoch)
    if value["model"]["id"] != MODEL_ID:
        raise ValueError("Require the combined ionic epoch identity")
    value["model"] = value["model"]["scheduled"]
    return value


def padded_shapes(raw, context):
    """Derive every padded owner axis from the declared physical capacities."""
    x = raw["execution"]
    species = len(raw["model"]["species"])
    counts = active_owner_counts(raw)
    owners = {
        "amount_increment": "capacity",
        "extracellular_amount_increment": "extracellular_capacity",
        "membrane_transferred": "membrane_capacity",
        "junction_transferred": "edge_capacity",
        "face_transferred": "face_capacity",
        "reservoir_supplied": "extracellular_capacity",
        "membrane_dissipated_energy_pJ": "membrane_capacity",
        "junction_dissipated_energy_pJ": "edge_capacity",
        "face_dissipated_energy_pJ": "face_capacity",
        "electrode_charge_transferred_C": "extracellular_capacity",
        "reservoir_work_pJ": "extracellular_capacity",
        "electrode_work_pJ": "extracellular_capacity",
        "channel_gate": "channel_capacity",
        "channel_transferred": "channel_capacity",
        "channel_dissipated_energy_pJ": "channel_capacity",
        "junction_gate": "edge_capacity",
        "pump_cycles": "membrane_capacity",
        "pump_dissipated_energy_pJ": "membrane_capacity",
        "metabolic_work_pJ": "membrane_capacity",
    }
    result = {}
    for name, active_shape in context["shapes"].items():
        if name == "phase_clock_s":
            result[name] = (1,)
            continue
        capacity = x[owners[name]]
        if type(capacity) is not int or capacity < counts[name]:
            raise ValueError("Insufficient physical owner capacity: " + name)
        result[name] = (
            (2, capacity)
            if name == "channel_gate"
            else (species, capacity)
            if len(active_shape) == 2
            else (capacity,)
        )
    return result


def _values(value):
    if type(value) is list:
        for child in value:
            yield from _values(child)
    else:
        yield value


def decode_state(record, shapes, owner_counts):
    """Reject malformed arrays before compacting; inspect padding as history."""
    if type(record) is not dict or set(record) != set(shapes):
        raise ValueError("Require every complete checkpoint state field exactly once")
    result = {}
    for name, shape in shapes.items():
        row = record[name]
        if type(row) is not dict or set(row) != {"dtype", "shape", "values"}:
            raise ValueError("Require a typed complete array: " + name)
        if (
            row["dtype"] != np.dtype("float64").str
            or type(row["shape"]) is not list
            or any(type(v) is not int for v in row["shape"])
            or row["shape"] != list(shape)
            or type(row["values"]) is not list
            or any(type(v) is not float for v in _values(row["values"]))
        ):
            raise ValueError("Invalid checkpoint shape/precision/scalars: " + name)
        try:
            value = np.asarray(row["values"], dtype=np.float64)
        except (TypeError, ValueError, OverflowError) as error:
            raise ValueError("Malformed checkpoint array: " + name) from error
        if value.shape != shape or not np.isfinite(value).all():
            raise ValueError("Wrong shape or nonfinite checkpoint array: " + name)
        active = owner_counts[name]
        if np.any(value[..., active:] != 0.0):
            raise ValueError("Nonzero history in an absent owner: " + name)
        result[name] = value.copy()
    return result


def bind(request):
    if request.get("kind") != REQUEST_KIND:
        raise ValueError("Require the explicit combined ionic phase request")
    source, target = request["source"]["definition"], request["simulation"]
    if any(raw["model"]["id"] != SCHEDULED_ID for raw in (source, target)):
        raise ValueError("Require ordinary combined ionic source and target")
    if source["model"]["phase"] != "INIT" or target["model"]["phase"] != "SIM":
        raise ValueError("Require the declared INIT-to-SIM direction")
    original, context = scheduled.bind(source), scheduled.bind(target)
    if original["parent_definition"]["model"] != context["parent_definition"]["model"]:
        raise ValueError("Physical anchors and complete owners must remain unchanged")
    if source["model"]["coupled_preparation"] != target["model"]["coupled_preparation"]:
        raise ValueError("Static membrane and exterior preparation must remain unchanged")
    if any(source["execution"][k] != target["execution"][k] for k in CAPACITIES):
        raise ValueError("Cannot remap physical owner capacities at phase handoff")
    checkpoint = request["source"]["checkpoint"]
    shapes = padded_shapes(source, original)
    counts = active_owner_counts(source)
    arrays = decode_state(checkpoint["state"], shapes, counts)
    time = checkpoint["time"]
    if (
        type(time) not in (int, float)
        or not math.isfinite(time)
        or not 0 <= time <= source["experiment"]["end_time"]
        or abs(arrays["phase_clock_s"][0] - time) > original["phase_clock_atol_s"]
    ):
        raise ValueError("Invalid original INIT checkpoint clock")
    for name in ("step_index", "event_index"):
        if type(checkpoint[name]) is not int or checkpoint[name] < 0:
            raise ValueError("Invalid checkpoint clock index")
    carried = {name: value.copy() for name, value in arrays.items()}
    carried["phase_clock_s"] = np.zeros((1,), dtype=np.float64)
    context.update(
        source_context=original,
        source_arrays=arrays,
        carried_arrays=carried,
        padded_shapes=shapes,
        active_owner_counts=counts,
        source_time_s=float(time),
        simulation=deepcopy(target),
    )
    return context


def initial(request):
    context = bind(request)
    return context, flatten(context, context["carried_arrays"])


def carried_arrays(request):
    return bind(request)["carried_arrays"]


def evaluate(context, vector, time):
    values = np.asarray(vector)
    expected = sum(math.prod(shape) for shape in context["shapes"].values())
    if (
        values.shape != (expected,)
        or not np.isfinite(values).all()
        or isinstance(time, (bool, np.bool_))
        or not isinstance(time, (int, float, np.integer, np.floating))
        or not math.isfinite(time)
        or not 0 <= time <= context["simulation"]["experiment"]["end_time"]
    ):
        raise ValueError("Require a finite complete state and phase-local stage time")
    return scheduled.evaluate(context, values, float(time))


def conservation(context, vector):
    """Original-inventory history plus independently reconstructed charge owners."""
    result = scheduled.conservation(context, vector)
    c, active = context["parent"], scheduled.active
    d = unpack(context, vector)
    z = np.asarray(c["layout"]["valence"])
    dq = (
        active.F
        * 1e-15
        * np.r_[
            np.sum(z * d["amount_increment"], axis=0),
            np.sum(z * d["extracellular_amount_increment"], axis=0),
        ]
    )
    stage = active.base.stage(c, vector[:-1], float(vector[-1]))
    matrix, enabled, reservoir, _, floating, _ = active.electrical.topology(stage)
    pins = ~enabled | reservoir
    for group in floating:
        pins[group[0]] = True
    free = np.flatnonzero(~pins)
    potential_change = np.zeros_like(dq)
    potential_change[free] = np.linalg.solve(matrix[np.ix_(free, free)], dq[free])
    n = len(c["vi"])
    result.update(
        original_cell_amount_fmol=c["ai"].copy(),
        original_outside_amount_fmol=c["ao"].copy(),
        original_cell_charge_C=c["qi"].copy(),
        original_outside_charge_C=c["qo"].copy(),
        cell_amount_fmol=c["ai"] + d["amount_increment"],
        outside_amount_fmol=c["ao"] + d["extracellular_amount_increment"],
        cell_charge_C=c["qi"] + dq[:n],
        outside_charge_C=c["qo"] + dq[n:],
        global_material_residual_fmol=d["amount_increment"].sum(axis=1)
        + d["extracellular_amount_increment"].sum(axis=1)
        - d["reservoir_supplied"].sum(axis=1),
        capacitor_charge_residual_C=(matrix @ potential_change - dq)[enabled & ~reservoir],
        electrode_charge_residual_C=d["electrode_charge_transferred_C"]
        - np.where(reservoir[n:], (matrix @ potential_change)[n:], 0.0),
        global_charge_residual_C=float(
            d["electrode_charge_transferred_C"].sum()
            + active.F * 1e-15 * np.sum(z * d["reservoir_supplied"])
        ),
    )
    return result


def dependency_manifest(root):
    """Bind the full independent closure, including imported helper functions."""
    root = Path(root).resolve()
    pending, seen, result = [sys.modules[__name__]], set(), {}
    while pending:
        module = pending.pop()
        if module.__name__ in seen:
            continue
        seen.add(module.__name__)
        path = Path(module.__file__).resolve()
        legacy_reference = path.parent == root / "tests" and path.name.startswith("reference_")
        if not path.is_relative_to(root / "validation") and not legacy_reference:
            raise ValueError("Oracle depends on a non-reference project module: " + str(path))
        # Legacy scalar references live under tests/, but are equation helpers,
        # not production fixtures. Audit their imports before admitting them.
        if legacy_reference:
            for node in ast.walk(ast.parse(path.read_text())):
                imported = (
                    [alias.name for alias in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                    if isinstance(node, ast.ImportFrom)
                    else []
                )
                if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in imported):
                    raise ValueError("Production dependency in legacy reference: " + str(path))
        with path.open("rb") as stream:
            result[str(path.relative_to(root))] = hashlib.file_digest(stream, "sha256").hexdigest()
        for value in vars(module).values():
            name = (
                value.__name__
                if isinstance(value, ModuleType)
                else getattr(value, "__module__", "")
            )
            candidate = sys.modules.get(name)
            location = getattr(candidate, "__file__", None)
            if location and Path(location).resolve().is_relative_to(root):
                pending.append(candidate)
    return dict(sorted(result.items()))
