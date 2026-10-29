"""Independent native ECM interpolation plus complete 43/48-field physics.

Only coefficient arithmetic uses the passive geometry view. Each physical RHS
rebinds the unchanged full water/repair oracle at the current face coefficients;
all pumps, free cytosolic ions, molecular stores and water/fuel energies remain
with that complete owner. No production or JAX imports occur here.
"""

import math
from copy import deepcopy

import numpy as np

from validation.tissue import calcium_energy_water_hcn_extra_reference as water
from validation.tissue import calcium_energy_water_repair_hcn_extra_reference as repair
from validation.transport import environment_barrier_interventions_reference as ecm
from validation.transport import environment_barrier_preparation_reference as static

OWNERS = {
    "resolved_calcium_energy_water_extracellular_barriers@1": (water.MODEL_ID, water),
    "resolved_calcium_energy_water_repair_extracellular_barriers@1": (repair.MODEL_ID, repair),
}
TIMING_POLICY = ecm.TIMING_POLICY
EXTRA = ecm.EXTRA_KEYS


def parent_definition(raw):
    result = deepcopy(raw)
    mid, process = OWNERS[result["model"]["id"]]
    for key in EXTRA:
        result["model"].pop(key)
    result["model"]["id"] = mid
    result["execution"].pop("barrier_target_capacity")
    if result["model"]["ionic"]["id"] != "resolved_tissue@12":
        raise ValueError("Require the exact full56 ionic owner")
    return result, process


def normalized_owners(value):
    """Canonicalize explicit owner lists without reordering coordinates or gates."""
    if isinstance(value, dict):
        return {
            k: sorted(v)
            if k == "moieties" and isinstance(v, list) and all(isinstance(s, str) for s in v)
            else normalized_owners(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        rows = [normalized_owners(v) for v in value]
        for key in ("id", "cell_id", "membrane_id", "channel_id", "compartment_id"):
            if rows and all(isinstance(v, dict) and key in v for v in rows):
                if len({v[key] for v in rows}) == len(rows):
                    return sorted(rows, key=lambda row: row[key])
        return rows
    return value


def _static_recipe(artifact, parent_model):
    if not isinstance(artifact, dict) or set(artifact) != {"definition", "provenance"}:
        raise ValueError("Require the complete composed static preparation artifact")
    request = deepcopy(artifact["provenance"]["request"])
    if request["kind"] != "cells.composed_environment_barrier_preparation_request@1":
        raise ValueError("Require the composed static coefficient recipe")
    if request["definition"]["model"]["id"] != parent_model["id"]:
        raise ValueError("Static preparation belongs to another physical parent")
    expected = deepcopy(request["definition"]["model"])
    projected = deepcopy(request)
    projected["kind"] = static.REQUEST_KIND
    projected["definition"]["model"] = deepcopy(expected["ionic"])
    projected["definition"]["model"]["id"] = "resolved_tissue@1"
    prepared = static.prepare(projected)
    expected["ionic"]["faces"] = prepared["definition"]["model"]["faces"]
    actual = deepcopy(artifact["definition"]["model"])
    # Check independent rounding only for the coefficient maps; owners, stores,
    # physical anchors and all other model values must correspond exactly.
    old_faces = {v["id"]: v for v in expected["ionic"]["faces"]}
    if set(old_faces) != {v["id"] for v in actual["ionic"]["faces"]}:
        raise ValueError("Prepared face owners disagree with the source recipe")
    for row in actual["ionic"]["faces"]:
        values = old_faces[row["id"]]["diffusivity_m2_per_s"]
        if set(row["diffusivity_m2_per_s"]) != set(values) or any(
            not math.isclose(
                row["diffusivity_m2_per_s"][s], v, rel_tol=64 * np.finfo(float).eps, abs_tol=0
            )
            for s, v in values.items()
        ):
            raise ValueError("Static face coefficients disagree with the Decimal recipe")
        row["diffusivity_m2_per_s"] = values
    if normalized_owners(actual) != normalized_owners(expected):
        raise ValueError("Static preparation changed physical owners or parameters")
    if parent_model != artifact["definition"]["model"]:
        raise ValueError("Complete parent must match its prepared physical model")
    return projected, prepared


def bind(raw):
    m = raw.get("model", {})
    if m.get("id") not in OWNERS or not EXTRA <= m.keys():
        raise ValueError("Require the exact complete scheduled water/repair owner")
    if m["phase"] not in ("INIT", "SIM") or m["timing_policy"] != TIMING_POLICY:
        raise ValueError("Unsupported phase or stage-clock timing policy")
    parent, process = parent_definition(raw)
    request, prepared = _static_recipe(m["barrier_preparation"], parent["model"])
    if not {s["id"] for s in parent["model"]["ionic"]["species"]} <= ecm.NATIVE_SPECIES:
        raise ValueError("Native ECM supports named Na/K/Cl/Ca/M/P ions only")
    capacity = raw["execution"]["barrier_target_capacity"]
    if type(capacity) is not int or not 0 <= capacity <= 65536:
        raise ValueError("Require bounded integer target occurrence capacity")
    end = ecm._number(raw["experiment"]["end_time"], "end", positive=True)
    dt = ecm._number(raw["execution"]["dt"], "dt", positive=True)
    event = m["intervention"]
    if event is not None:
        if not isinstance(event, dict) or set(event) != {
            "name",
            "site_ids",
            "on_s",
            "off_s",
            "change_s",
            "amplitude",
        }:
            raise ValueError("Require one explicit native ECM event")
        if not isinstance(event["name"], str) or not event["name"]:
            raise ValueError("Require an event name")
        targets = event["site_ids"]
        if (
            not isinstance(targets, list)
            or not targets
            or len(targets) > capacity
            or any(not isinstance(s, str) or s not in request["grid"]["site_ids"] for s in targets)
        ):
            raise ValueError("Retain every ordered target occurrence within capacity")
        on, off, change, amplitude = [
            ecm._number(event[k], k) for k in ("on_s", "off_s", "change_s", "amplitude")
        ]
        if not 0 <= on < off <= end or change <= 0 or not 0 <= amplitude <= 1:
            raise ValueError("Invalid native pulse declaration")
        if m["phase"] == "SIM" and dt > change / 8 * (1 + 16 * np.finfo(float).eps):
            raise ValueError("Resolve the native transition by at least eight declared steps")
    context = process.bind(parent)
    return dict(
        raw=deepcopy(raw),
        parent_raw=parent,
        process=process,
        parent=context,
        request=request,
        static=prepared,
        phase=m["phase"],
        event=deepcopy(event),
        end_time=end,
        phase_clock_atol_s=64 * np.finfo(float).eps * max(end, dt),
        shapes=context["shapes"] | {"phase_clock_s": (1,)},
    )


def initial(context):
    return np.r_[context["process"].initial(context["parent"]), 0.0]


def flatten(context, values):
    return np.r_[
        context["process"].flatten(context["parent"], values),
        np.asarray(values["phase_clock_s"]).reshape(-1),
    ]


def unpack(context, state):
    if np.ndim(state) != 1 or np.size(state) != sum(
        math.prod(s) for s in context["shapes"].values()
    ):
        raise ValueError("Require every physical field and exactly one phase-clock slot")
    if not np.isfinite(state).all():
        raise ValueError("The complete scheduled state must be finite")
    return context["process"].unpack(context["parent"], state[:-1]) | {"phase_clock_s": state[-1:]}


coefficients = ecm.coefficients


def current_definition(context, state, time=None, *, held_control_time=None):
    values = unpack(context, state)
    clock = float(values["phase_clock_s"][0])
    if time is not None:
        if isinstance(time, np.floating):
            time = float(time)
        actual = ecm._number(time, "absolute stage time", nonnegative=True)
        if abs(actual - clock) > context["phase_clock_atol_s"]:
            raise ValueError("State-owned phase clock disagrees with absolute time")
    held = clock if held_control_time is None else float(held_control_time)
    if not math.isfinite(held) or not 0 <= held <= clock + context["phase_clock_atol_s"]:
        raise ValueError("Invalid left-held physical control time")
    signal = coefficients(context, clock)
    raw = deepcopy(context["parent_raw"])
    for face in raw["model"]["ionic"]["faces"]:
        face["diffusivity_m2_per_s"] = {
            s: rows[face["id"]] for s, rows in signal["face_m2_s"].items()
        }
    return raw, held, signal


def evaluate(context, state, time=None, *, held_control_time=None):
    raw, held, signal = current_definition(
        context, state, time, held_control_time=held_control_time
    )
    process = context["process"]
    current = process.bind(raw)
    slope, phi, proof = process.evaluate(current, state[:-1], held)
    return (
        np.r_[slope, 1.0],
        phi,
        proof
        | dict(
            phase_clock_s=float(state[-1]),
            native_ecm=signal,
            barrier_parameter_work_pJ_s=0.0,
            barrier_energetics_scope=(
                "Prescribed diffusivity; no added structural store or ATP debit"
            ),
        ),
    )


def free_energy_change(context, state, time=None):
    raw, held, _ = current_definition(context, state, time)
    process = context["process"]
    return process.free_energy_change(process.bind(raw), state[:-1], held)
