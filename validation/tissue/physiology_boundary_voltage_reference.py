"""Independent named reservoir mapping, full-node roots and ordinary full rates.

No Cells/JAX imports, production slot maps or temporary layouts. The source
setter uses the independent 125-digit expression; native execution is checked
separately. Capacitance endpoint accounting is rebuilt from named raw patches.
"""

import hashlib
import json
import math
from copy import deepcopy

import numpy as np

from validation.perturbations import global_controls_reference as setters
from validation.tissue import open_calcium_reference as open_calcium
from validation.tissue import physiology_permeability_view_reference as physical

KIND = "cells.physiology_boundary_voltage_binding@1"
SIDES = ("top", "bottom", "left", "right")
ORACLES = physical.ORACLES | {
    "resolved_open_calcium@1": open_calcium,
    "resolved_open_calcium_energy@1": open_calcium,
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def reconstruct(raw, binding_record, boundary_state, held_control, time_s, events_enabled):
    if raw["model"]["id"] not in ORACLES:
        raise ValueError("Independent voltage reference requires an exact ordinary family")
    expected = {
        "kind",
        "source_definition_sha256",
        "program",
        "boundary_reservoir_ids",
        "provenance",
        "identity",
    }
    if (
        set(binding_record) != expected
        or binding_record["kind"] != KIND
        or binding_record["source_definition_sha256"] != _digest(raw)
        or binding_record["identity"]
        != _digest({k: v for k, v in binding_record.items() if k != "identity"})
    ):
        raise ValueError("Independent boundary binding/source identity mismatch")
    program = binding_record["program"]
    if (
        program["law"] != "betse_global_controls_source_v1_5_0@1"
        or program["identity"] != _digest({k: v for k, v in program.items() if k != "identity"})
        or any(row["kind"] != "voltage" for row in program["events"])
        or len(program["events"]) > 1
    ):
        raise ValueError("Independent reference requires an authenticated voltage-only program")
    original = deepcopy(raw)
    physical._hold(original, held_control)
    result = deepcopy(original)
    model = result["model"].get("ionic", result["model"])
    if program["membrane_ids"] != [row["id"] for row in model["membranes"]]:
        raise ValueError("Independent native membrane axis mismatch")
    outside = {row["id"]: row for row in model["extracellular"]}
    rows = binding_record["boundary_reservoir_ids"]
    if [row[0] for row in rows] != list(SIDES):
        raise ValueError("Independent mapping must declare all four ordered sides")
    mapping = dict(rows)
    for owners in mapping.values():
        if len(owners) != len(set(owners)) or any(
            name not in outside or not outside[name]["reservoir"] for name in owners
        ):
            raise ValueError("Independent boundary owners must be unique actual reservoirs")
    for event in program["events"]:
        if not mapping[event["positive_boundary"]] or not mapping[event["negative_boundary"]]:
            raise ValueError("Independent active voltage side has no physical owner")
    state = dict(
        temperature_K=model["temperature_K"],
        junction_available=[1.0] * len(program["membrane_ids"]),
        pump_available=1.0,
        **boundary_state,
    )
    after = setters.evaluate(
        program, state, time_s, model["temperature_K"], events_enabled=events_enabled
    )
    writes = {}
    for side, owners in rows:
        value = after["boundary_voltage_V"][SIDES.index(side)]
        for owner in owners:
            if owner in writes and value != writes[owner]:
                raise ValueError("Independent corner owner receives incompatible side voltages")
            writes[owner] = value
    for name, value in writes.items():
        outside[name]["boundary_potential_V"] = value
    return original, result, after


def capacitor_change(raw, original_phi, changed_phi, effective):
    model = raw["model"].get("ionic", raw["model"])
    changed = effective["model"].get("ionic", effective["model"])
    cells = [row["id"] for row in model["cells"]]
    outside = [row["id"] for row in model["extracellular"]]
    old, new = np.asarray(original_phi), np.asarray(changed_phi)
    charge_terms = [[] for _ in outside]
    energy_terms, voltage_delta = [], []
    for patch in model["membranes"]:
        i, j = cells.index(patch["inside"]), len(cells) + outside.index(patch["outside"])
        vm0, vm1 = float(old[i] - old[j]), float(new[i] - new[j])
        capacitance = patch["capacitance_F"]
        voltage_delta.append(vm1 - vm0)
        charge_terms[outside.index(patch["outside"])].append(-capacitance * (vm1 - vm0))
        energy_terms.append(0.5e12 * capacitance * (vm1 - vm0) * (vm1 + vm0))
    delta_q = [
        math.fsum(terms) if row["reservoir"] else 0.0
        for row, terms in zip(model["extracellular"], charge_terms, strict=True)
    ]
    energy = math.fsum(energy_terms)
    work = math.fsum(
        0.5e12 * (before["boundary_potential_V"] + after["boundary_potential_V"]) * charge
        for before, after, charge in zip(
            model["extracellular"], changed["extracellular"], delta_q, strict=True
        )
    )
    return dict(
        electrode_charge_change_C=delta_q,
        membrane_voltage_change_V=voltage_delta,
        capacitor_energy_change_pJ=energy,
        conditional_linear_capacitive_ramp_work_pJ=work,
        conditional_work_residual_pJ=energy - work,
    )


def evaluate(raw, fields, binding_record, boundary_state, held_control, time_s, events_enabled):
    original, effective, after = reconstruct(
        raw, binding_record, boundary_state, held_control, time_s, events_enabled
    )
    oracle = ORACLES[raw["model"]["id"]]
    context = oracle.bind(effective)
    if set(fields) != set(context["shapes"]):
        raise ValueError("Independent voltage reference requires complete ordinary state fields")
    derivative, potential, proof = oracle.evaluate(context, oracle.flatten(context, fields), 0.0)
    parent = oracle.bind(original)
    _, old_phi, _ = oracle.evaluate(parent, oracle.flatten(parent, fields), 0.0)
    model = effective["model"].get("ionic", effective["model"])
    return (
        context,
        derivative,
        potential,
        dict(
            proof,
            source_definition_sha256=_digest(raw),
            effective_definition_sha256=_digest(effective),
            boundary_state=dict(boundary_voltage_V=after["boundary_voltage_V"]),
            named_reservoir_voltages={
                row["id"]: row["boundary_potential_V"] for row in model["extracellular"]
            },
            capacitor_change=capacitor_change(raw, old_phi, potential, effective),
            raw_owner_reconstruction=True,
            accepted_stepping=False,
        ),
    )
