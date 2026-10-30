"""Independent named-owner SI reconstruction and full ordinary field/RHS oracles.

No Cells/JAX imports. Reconstruct current P using 80-digit division from raw
component D, declared thickness and actual owner IDs; never consume production
slot maps or a production runtime layout. Explicit controls are held inputs,
not a claim about their synchronization to a component or tissue clock.
"""

import hashlib
import json
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.tissue import surface_calcium_energy_reference as fuel
from validation.tissue import surface_calcium_reference as calcium
from validation.tissue import surface_dynamics_reference as passive
from validation.tissue import surface_kinetic_reference as ionic

ORACLES = {
    "resolved_tissue@1": passive,
    "resolved_tissue@12": ionic,
    "resolved_calcium@11": calcium,
    "resolved_calcium_energy@5": fuel,
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def _positive(value):
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError("Require actual positive finite geometric measures")
    return number


def reconstruct(raw, binding, current_diffusion_m2_s, held_control=None):
    if raw["model"]["id"] not in ORACLES:
        raise ValueError("Require one of the four exact ordinary model identities")
    if (
        binding.get("kind") != "cells.physiology_tissue_binding@1"
        or binding.get("source_definition_sha256") != _digest(raw)
        or binding.get("identity") != _digest({k: v for k, v in binding.items() if k != "identity"})
    ):
        raise ValueError("Independent source/binding provenance mismatch")
    result = deepcopy(raw)
    model = result["model"].get("ionic", result["model"])
    source = raw["model"].get("ionic", raw["model"])
    inputs = binding["inputs"]
    actual_axes = dict(
        cell_ids=[row["id"] for row in source["cells"]],
        membrane_ids=[row["id"] for row in source["membranes"]],
        environment_ids=[row["id"] for row in source["extracellular"]],
        ion_ids=[row["id"] for row in source["species"]],
    )
    for key, actual in actual_axes.items():
        declared = inputs[key]
        if len(declared) != len(set(declared)) or set(declared) != set(actual):
            raise ValueError("Independent component owners do not match actual tissue")
    membranes = {row["id"]: row for row in source["membranes"]}
    cells = {row["id"]: row for row in source["cells"]}
    outside = {row["id"]: row for row in source["extracellular"]}
    if len({row["volume_pL"] for row in outside.values()}) != 1:
        raise ValueError("Native matrix geometry cannot represent heterogeneous exterior volumes")
    geometry = binding["geometry"]
    for axis, key, values in (
        (
            "membrane_ids",
            "membrane_area_m2",
            [membranes[name]["area_m2"] for name in inputs["membrane_ids"]],
        ),
        (
            "cell_ids",
            "cell_volume_m3",
            [float(cells[name]["volume_pL"]) * 1e-15 for name in inputs["cell_ids"]],
        ),
        (
            "environment_ids",
            "environment_volume_m3",
            [float(outside[name]["volume_pL"]) * 1e-15 for name in inputs["environment_ids"]],
        ),
    ):
        if len(inputs[axis]) != len(values) or geometry[key] != values:
            raise ValueError("Independent geometry differs from actual source units")
    for key, field in (("membrane_cell_ids", "inside"), ("membrane_environment_ids", "outside")):
        if geometry[key] != [membranes[name][field] for name in inputs["membrane_ids"]]:
            raise ValueError("Independent membrane ownership mismatch")
    diffusion = np.asarray(current_diffusion_m2_s)
    if (
        diffusion.shape != (len(inputs["ion_ids"]), len(inputs["membrane_ids"]))
        or not np.isfinite(diffusion).all()
        or np.any(diffusion < 0)
    ):
        raise ValueError("Independent current D must be finite and nonnegative")
    thickness = inputs["membrane_thickness_m"]
    if set(thickness) != set(actual_axes["membrane_ids"]):
        raise ValueError("Independent thickness map must cover all membrane owners")
    with localcontext() as context:
        context.prec = 80
        for row in model["membranes"]:
            j = inputs["membrane_ids"].index(row["id"])
            _positive(thickness[row["id"]])
            length = Decimal.from_float(float(thickness[row["id"]]))
            for species in model["species"]:
                i = inputs["ion_ids"].index(species["id"])
                value = float(Decimal.from_float(float(diffusion[i, j])) / length)
                if not np.isfinite(value) or diffusion[i, j] != 0 and value == 0:
                    raise ValueError("Independent D/thickness conversion is unrepresentable")
                row["permeability_m_per_s"][species["id"]] = value
    if held_control is not None:
        _hold(result, held_control)
    return result


def _hold(raw, controls):
    """Independent named-route reconstruction of an explicit held packet at t=0."""
    model, experiment = raw["model"].get("ionic", raw["model"]), raw["experiment"]
    for key, values in controls.items():
        array = np.asarray(values)
        if not np.isfinite(array).all() or np.any((array < 0) | (array > 1)):
            raise ValueError("Invalid independent explicit held control: " + key)
    for kind, owner_field, owner_rows in (
        ("membrane", "membrane_id", model["membranes"]),
        ("junction", "junction_id", model["junctions"]),
        ("channel", "channel_id", model.get("channels", [])),
    ):
        if kind not in controls:
            continue
        order = [row["id"] for row in owner_rows]
        for row in experiment[kind + "_controls"]:
            row["schedule"] = [
                dict(time=0.0, availability=float(controls[kind][order.index(row[owner_field])]))
            ]
    if "pump" in controls:
        owners = {
            row["pump"]["id"]: i
            for i, row in enumerate(model["membranes"])
            if row["pump"] is not None
        }
        for row in experiment["pump_controls"]:
            row["schedule"] = [
                dict(time=0.0, availability=float(controls["pump"][owners[row["pump_id"]]]))
            ]
    if "er_reactions" in controls:
        cells = [row["id"] for row in model["cells"]]
        stores = {row["cell_id"]: row["model"] for row in raw["model"]["stores"]}
        for row in experiment["store_controls"]:
            i, store = cells.index(row["cell_id"]), stores[row["cell_id"]]
            row["controls"] = [
                dict(
                    time=0.0,
                    reactions={
                        v["id"]: float(controls["er_reactions"][i][j])
                        for j, v in enumerate(store["reactions"])
                    },
                    passive={
                        v["id"]: float(controls["er_passive"][i][j])
                        for j, v in enumerate(store["species"])
                    },
                    pump=float(controls["er_pump"][i]),
                    release=float(controls["er_release"][i]),
                )
            ]
        membranes = [row["id"] for row in model["membranes"]]
        for row in experiment["plasma_controls"]:
            i = membranes.index(row["membrane_id"])
            row["schedule"] = [
                dict(
                    time=0.0,
                    pump=float(controls["plasma_pump"][i]),
                    exchanger=float(controls["plasma_exchange"][i]),
                )
            ]
        channels = {row["id"]: row["membrane_id"] for row in raw["model"]["calcium_channels"]}
        for row in experiment["calcium_channel_controls"]:
            i = membranes.index(channels[row["channel_id"]])
            row["schedule"] = [dict(time=0.0, availability=float(controls["calcium_channel"][i]))]
    if "regeneration" in controls:
        order = [row["id"] for row in raw["model"]["regeneration_ports"]]
        for row in experiment["regeneration_controls"]:
            row["schedule"] = [
                dict(
                    time=0.0,
                    availability=float(
                        controls["regeneration"][order.index(row["regeneration_id"])]
                    ),
                )
            ]


def evaluate(raw, fields, binding_record, current_diffusion_m2_s, held_control=None):
    effective = reconstruct(raw, binding_record, current_diffusion_m2_s, held_control)
    oracle = ORACLES[effective["model"]["id"]]
    context = oracle.bind(effective)
    state = oracle.flatten(context, fields)
    derivative, potential, proof = oracle.evaluate(context, state, 0.0)
    return (
        context,
        derivative,
        potential,
        dict(
            proof,
            source_definition_sha256=_digest(raw),
            effective_definition_sha256=_digest(effective),
            named_owner_SI_reconstruction=True,
            explicit_held_control=True,
        ),
    )
