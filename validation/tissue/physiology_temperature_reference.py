"""Independent Kelvin setter/owner reconstruction and full ordinary rate oracles.

No Cells/JAX imports. Active catalog temperature restrictions remain explicit.
The reported Gibbs-functional coefficient change is not a heat calculation.
"""

import hashlib
import json
import math
from copy import deepcopy
from decimal import Decimal, localcontext

from validation.perturbations import global_controls_reference as setters
from validation.tissue import open_calcium_reference as open_calcium
from validation.tissue import physiology_permeability_view_reference as physical

KIND = "cells.physiology_temperature_binding@1"
POLICY = "uniform_prescribed_kelvin_original_model_domain@1"
ORACLES = physical.ORACLES | {
    "resolved_open_calcium@1": open_calcium,
    "resolved_open_calcium_energy@1": open_calcium,
}


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def reconstruct(raw, binding_record, current_temperature_K, held_control, time_s, events_enabled):
    if raw["model"]["id"] not in ORACLES:
        raise ValueError("Independent temperature reference requires a reviewed model identity")
    expected = {
        "kind",
        "policy",
        "units",
        "source_definition_sha256",
        "program",
        "owners",
        "provenance",
        "identity",
    }
    if (
        set(binding_record) != expected
        or binding_record["kind"] != KIND
        or binding_record["policy"] != POLICY
        or binding_record["units"] != {"temperature": "K", "native_amplitude": "dimensionless"}
        or binding_record["source_definition_sha256"] != _digest(raw)
        or binding_record["identity"]
        != _digest({key: value for key, value in binding_record.items() if key != "identity"})
    ):
        raise ValueError("Independent temperature source/owner/unit identity mismatch")
    model = raw["model"].get("ionic", raw["model"])
    actual = dict(
        cells=[row["id"] for row in model["cells"]],
        environment=[row["id"] for row in model["extracellular"]],
        membranes=[row["id"] for row in model["membranes"]],
        junctions=[row["id"] for row in model["junctions"]],
        faces=[row["id"] for row in model["faces"]],
        channel_populations=[row["id"] for row in model.get("channels", [])],
        stores=[row["cell_id"] for row in raw["model"].get("stores", [])],
        fuel_pools=[row["id"] for row in raw["model"].get("energy_pools", [])],
    )
    rows = binding_record["owners"]
    if [row[0] for row in rows] != list(actual):
        raise ValueError("Independent temperature owner axes differ")
    for name, owners in rows:
        if len(owners) != len(set(owners)) or set(owners) != set(actual[name]):
            raise ValueError("Independent actual physical owner association differs: " + name)
    program = binding_record["program"]
    if (
        program["law"] != "betse_global_controls_source_v1_5_0@1"
        or program["identity"]
        != _digest({key: value for key, value in program.items() if key != "identity"})
        or program["membrane_ids"] != actual["membranes"]
        or len(program["events"]) > 1
        or any(row["kind"] != "temperature" for row in program["events"])
    ):
        raise ValueError("Independent temperature-only source program differs")
    if not math.isfinite(current_temperature_K) or current_temperature_K <= 0:
        raise ValueError("Independent temperature memory must be positive Kelvin")
    current = dict(
        temperature_K=current_temperature_K,
        pump_available=1.0,
        junction_available=[1.0] * len(actual["membranes"]),
        boundary_voltage_V=[0.0] * 4,
    )
    proposed = setters.evaluate(
        program, current, time_s, model["temperature_K"], events_enabled=events_enabled
    )
    target = proposed["temperature_K"]
    if not math.isfinite(target) or target <= 0:
        raise ValueError("Independent native setter produced nonpositive/nonfinite Kelvin")
    if raw["model"]["id"] != "resolved_tissue@1" and target != model["temperature_K"]:
        raise ValueError("Independent active catalog retains its original 298.15-K domain")
    effective = deepcopy(raw)
    physical._hold(effective, held_control)
    effective["model"].get("ionic", effective["model"])["temperature_K"] = target
    return effective, proposed


def functional_shift(raw, fields, target_temperature_K):
    if raw["model"]["id"] != "resolved_tissue@1":
        return 0.0
    model = raw["model"]
    species = [row["id"] for row in model["species"]]
    with localcontext() as precision:
        precision.prec = 100
        coefficient = Decimal(0)
        for owners, key in (
            (model["cells"], "amount_increment"),
            (model["extracellular"], "extracellular_amount_increment"),
        ):
            for j, owner in enumerate(owners):
                if owner.get("reservoir", False):
                    continue
                for i, ion in enumerate(species):
                    amount = Decimal.from_float(
                        float(owner["initial_amount_fmol"][ion])
                    ) + Decimal.from_float(float(fields[key][i][j]))
                    volume = Decimal.from_float(float(owner["volume_pL"]))
                    coefficient += amount * ((amount / volume).ln() - 1)
        delta = Decimal.from_float(float(target_temperature_K)) - Decimal.from_float(
            float(model["temperature_K"])
        )
        return float(
            Decimal("0.001") * Decimal.from_float(float(physical.passive.R)) * delta * coefficient
        )


def evaluate(
    raw, fields, binding_record, current_temperature_K, held_control, time_s, events_enabled
):
    effective, source = reconstruct(
        raw, binding_record, current_temperature_K, held_control, time_s, events_enabled
    )
    oracle = ORACLES[raw["model"]["id"]]
    context = oracle.bind(effective)
    if set(fields) != set(context["shapes"]):
        raise ValueError("Independent temperature readout requires complete ordinary state fields")
    derivative, potential, proof = oracle.evaluate(context, oracle.flatten(context, fields), 0.0)
    return (
        context,
        derivative,
        potential,
        dict(
            proof,
            source_definition_sha256=_digest(raw),
            effective_definition_sha256=_digest(effective),
            held_temperature_K=source["temperature_K"],
            finite_owner_mixing_functional_shift_pJ=functional_shift(
                raw, fields, source["temperature_K"]
            ),
            accepted_thermal_transition=False,
            accepted_heat_pJ=None,
            full_physical_owner_reconstruction=True,
        ),
    )
