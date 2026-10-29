"""Independent INIT bath carry and explicit SIM source/work operation.

Uses the qualified independent ordinary bath equations, never production code.
Complete typed histories/padding and original physical anchors are verified
separately from the new controller operation. Numerical factorization caches
remain the production bridge's exact-layout admission responsibility.
"""

import ast
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path

import numpy as np

from validation.transport import surface_bath_events_reference as scheduled

REQUEST_KIND = "cells.surface_bath_phase_handoff_request@1"
OWNERS = {
    "resolved_passive_bath_epoch@1": "resolved_passive_bath_events@1",
    "resolved_active_bath_epoch@1": "resolved_active_bath_events@1",
}
POLICIES = dict(
    operation="explicit_init_checkpoint_to_new_sim_epoch@1",
    state_policy="carry_all_bath_transport_and_chemical_work_arrays_original_anchors@1",
    clock_policy="new_sim_clock_zero_archive_both_init_clocks@1",
    controller_policy="explicit_new_sim_initial_dose_electrode_charge_and_work@1",
    control_policy="new_zero_based_sim_controls_archive_complete_init_history@1",
)
CAPACITIES = (
    "capacity",
    "extracellular_capacity",
    "membrane_capacity",
    "edge_capacity",
    "face_capacity",
    "field_solver",
)
flatten, unpack = scheduled.flatten, scheduled.unpack


def digest(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def target_definition(epoch):
    result = deepcopy(epoch)
    model = result["model"]
    if model["id"] not in OWNERS or model["scheduled"]["id"] != OWNERS[model["id"]]:
        raise ValueError("Require a passive or complete ionic bath epoch")
    result["model"] = model["scheduled"]
    return result


def state_geometry(raw, context):
    m, x = raw["model"], raw["execution"]
    owners = {
        "cells": ("capacity", ("amount_increment",)),
        "extracellular": (
            "extracellular_capacity",
            (
                "extracellular_amount_increment",
                "reservoir_supplied",
                "electrode_charge_transferred_C",
                "reservoir_work_pJ",
                "electrode_work_pJ",
                "reservoir_chemical_work_pJ",
            ),
        ),
        "membranes": (
            "membrane_capacity",
            (
                "membrane_transferred",
                "membrane_dissipated_energy_pJ",
                "pump_cycles",
                "pump_dissipated_energy_pJ",
                "metabolic_work_pJ",
            ),
        ),
        "junctions": (
            "edge_capacity",
            ("junction_transferred", "junction_dissipated_energy_pJ", "junction_gate"),
        ),
        "faces": ("face_capacity", ("face_transferred", "face_dissipated_energy_pJ")),
        "channels": (
            "channel_capacity",
            ("channel_gate", "channel_transferred", "channel_dissipated_energy_pJ"),
        ),
    }
    shapes, masks = {}, {}
    for kind, (key, fields) in owners.items():
        if kind not in m:
            continue
        capacity, count = x[key], len(m[kind])
        if type(capacity) is not int or capacity < count:
            raise ValueError("Insufficient declared bath owner capacity")
        for name in fields:
            if name not in context["shapes"]:
                continue
            compact = context["shapes"][name]
            shape = (*compact[:-1], capacity)
            shapes[name] = shape
            masks[name] = np.zeros(shape, dtype=bool)
            masks[name][..., :count] = True
    shapes["phase_clock_s"] = (1,)
    masks["phase_clock_s"] = np.ones(1, dtype=bool)
    if set(shapes) != set(context["shapes"]):
        raise ValueError("Incomplete independent bath state ownership")
    return shapes, masks


def _leaves(value):
    if type(value) is list:
        for child in value:
            yield from _leaves(child)
    else:
        yield value


def _typed(record, shape, dtype):
    if (
        type(record) is not dict
        or set(record) != {"dtype", "shape", "values"}
        or record["dtype"] != np.dtype(dtype).str
        or type(record["shape"]) is not list
        or any(type(v) is not int for v in record["shape"])
        or tuple(record["shape"]) != shape
    ):
        raise ValueError("Typed bath array shape/precision disagrees")
    scalar = bool if np.dtype(dtype).kind == "b" else int if np.dtype(dtype).kind in "iu" else float
    if any(type(v) is not scalar for v in _leaves(record["values"])):
        raise ValueError("Typed bath scalar disagrees")
    value = np.asarray(record["values"], dtype=dtype)
    if value.size == math.prod(shape) == 0:
        value = value.reshape(shape)
    if value.shape != shape or not np.isfinite(value).all():
        raise ValueError("Bath array values are malformed/nonfinite")
    return value


def decode_state(record, shapes, masks):
    if type(record) is not dict or set(record) != set(shapes):
        raise ValueError("Require every bath transport and chemical-work history")
    values = {}
    for key, shape in shapes.items():
        values[key] = _typed(record[key], shape, np.float64)
        if np.any(values[key][~masks[key]] != 0):
            raise ValueError("Bath owner padding is nonzero: " + key)
    return values


def validate_original_layout(record, raw, context):
    """Independent physical anchors/geometry; no copied solver factorization."""
    m, x, parent = raw["model"], raw["execution"], context["parent"]
    expected = {}
    for kind, cap, volume, amount, charge in (
        ("cells", "capacity", "volume", "amount_reference", "initial_cell_charge_C"),
        (
            "extracellular",
            "extracellular_capacity",
            "extracellular_volume",
            "extracellular_amount_reference",
            "initial_outside_charge_C",
        ),
    ):
        count, capacity = len(m[kind]), x[cap]
        expected[volume] = np.ones(capacity)
        expected[volume][:count] = [v["volume_pL"] for v in m[kind]]
        expected[amount] = np.zeros((len(m["species"]), capacity))
        expected[amount][:, :count] = parent["ai" if kind == "cells" else "ao"]
        expected[charge] = np.zeros(capacity)
        expected[charge][:count] = parent["qi" if kind == "cells" else "qo"]
    expected.update(
        temperature=np.asarray(m["temperature_K"]),
        valence=np.asarray([v["valence"] for v in m["species"]], dtype=float)[:, None],
        boundary_V=np.zeros(x["extracellular_capacity"]),
        reservoir=np.zeros(x["extracellular_capacity"], dtype=bool),
    )
    count = len(m["extracellular"])
    expected["boundary_V"][:count] = [v["boundary_potential_V"] for v in m["extracellular"]]
    expected["reservoir"][:count] = [v["reservoir"] for v in m["extracellular"]]
    for kind, cap in (
        ("cell", "capacity"),
        ("outside", "extracellular_capacity"),
        ("membrane", "membrane_capacity"),
        ("junction", "edge_capacity"),
        ("face", "face_capacity"),
    ):
        rows = m[
            "cells" if kind == "cell" else "extracellular" if kind == "outside" else kind + "s"
        ]
        expected[kind + "_active"] = np.arange(x[cap]) < len(rows)
    expected["active"] = expected["cell_active"]
    for name, value in expected.items():
        if name not in record or not np.array_equal(
            _typed(record[name], value.shape, value.dtype), value
        ):
            raise ValueError("Original bath physical anchor/layout changed: " + name)
    for name in (
        "membrane_cell",
        "membrane_outside",
        "junction_sender",
        "junction_receiver",
        "face_sender",
        "face_receiver",
    ):
        kind, side = name.split("_")
        names = [
            v["id"]
            for v in m[
                "cells" if kind == "junction" or name == "membrane_cell" else "extracellular"
            ]
        ]
        source_key = "inside" if side == "cell" else "outside" if kind == "membrane" else side
        capacity = x[
            {"membrane": "membrane_capacity", "junction": "edge_capacity", "face": "face_capacity"}[
                kind
            ]
        ]
        value = np.zeros(capacity, dtype=np.int64)
        value[: len(m[kind + "s"])] = [names.index(v[source_key]) for v in m[kind + "s"]]
        if not np.array_equal(_typed(record[name], value.shape, value.dtype), value):
            raise ValueError("Original bath route owner changed: " + name)


def accepted_index(raw, time):
    end, dt = raw["experiment"]["end_time"], raw["execution"]["dt"]
    if (
        isinstance(time, bool)
        or not isinstance(time, (int, float))
        or not math.isfinite(time)
        or not 0 <= time <= end
    ):
        raise ValueError("Invalid INIT checkpoint time")
    count = end / dt
    if not math.isfinite(count) or count > raw["execution"]["max_steps"]:
        raise ValueError("Source grid exceeds its bound")
    last = max(0, math.ceil(count) - 1)
    while last > 0 and last * dt >= end:
        last -= 1

    def lower_bound(value):
        lo, hi = 0, last + 1
        while lo < hi:
            mid = (lo + hi) // 2
            if mid * dt < value:
                lo = mid + 1
            else:
                hi = mid
        return lo

    clocks = {0.0}
    for key, rows in raw["experiment"].items():
        if key.endswith("_controls"):
            clocks.update(v["time"] for row in rows for v in row["schedule"])
    extras = []
    for value in sorted(clocks - {0.0, end}):
        i = lower_bound(value)
        if i > last or i * dt != value:
            extras.append(value)
    nominal = lower_bound(time)
    if time == end:
        step = last + 1 + len(extras)
    elif nominal <= last and nominal * dt == time or time in extras:
        step = nominal + sum(v < time for v in extras)
    else:
        raise ValueError("Source time is not an accepted boundary")
    return step, sum(v <= time for v in clocks) - 1


def bind(request):
    if (
        type(request) is not dict
        or set(request) != {"kind", "policies", "source", "simulation"}
        or request["kind"] != REQUEST_KIND
        or request["policies"] != POLICIES
    ):
        raise ValueError("Require explicit bath INIT/SIM carry and controller policies")
    source = request["source"]
    if type(source) is not dict or set(source) != {"definition", "checkpoint", "identity"}:
        raise ValueError("Require a complete sealed bath source")
    body = {key: value for key, value in source.items() if key != "identity"}
    if digest(body) != source["identity"]:
        raise ValueError("Bath source identity disagrees")
    raw, target = source["definition"], request["simulation"]
    if (
        raw["model"]["id"] != target["model"]["id"]
        or raw["model"]["phase"] != "INIT"
        or target["model"]["phase"] != "SIM"
    ):
        raise ValueError("Require an identical ordinary bath owner, strictly INIT to SIM")
    if scheduled.parent_definition(raw)["model"] != scheduled.parent_definition(target)["model"]:
        raise ValueError("Bath carry changed an original physical owner or accounting anchor")
    keys = (*CAPACITIES, "channel_capacity") if "channels" in raw["model"] else CAPACITIES
    if any(raw["execution"][key] != target["execution"][key] for key in keys):
        raise ValueError("Bath carry cannot remap any physical capacity")
    original, current = scheduled.bind(raw), scheduled.bind(target)
    shapes, masks = state_geometry(raw, original)
    checkpoint = source["checkpoint"]
    if set(checkpoint) != {"time", "step_index", "event_index", "state", "layout"}:
        raise ValueError("Require a complete bath checkpoint")
    arrays = decode_state(checkpoint["state"], shapes, masks)
    validate_original_layout(checkpoint["layout"], raw, original)
    step, event = accepted_index(raw, checkpoint["time"])
    if (
        type(checkpoint["step_index"]) is not int
        or checkpoint["step_index"] != step
        or type(checkpoint["event_index"]) is not int
        or checkpoint["event_index"] != event
    ):
        raise ValueError("Bath source clock/control index disagrees")
    allowance = (
        64 * np.finfo(float).eps * max(raw["execution"]["dt"], raw["experiment"]["end_time"])
    )
    if abs(arrays["phase_clock_s"][0] - checkpoint["time"]) > allowance:
        raise ValueError("Source phase clock differs from accepted checkpoint time")
    source_vector = flatten(original, arrays)
    if step == 0 and not np.array_equal(source_vector, scheduled.initial(original)):
        raise ValueError("Initial bath source rewrites histories or gates")
    _, _, domain_proof = scheduled.evaluate(original, source_vector, held_time=checkpoint["time"])
    proof = scheduled.conservation(original, source_vector)
    for key in ("local_fmol", "outside_fmol", "global_fmol"):
        if np.max(np.abs(proof[key]), initial=0) > 3e-14:
            raise ValueError("Source material history is inconsistent")
    for key in ("global_charge_C", "electrode_charge_C", "capacitor_charge_C"):
        if np.max(np.abs(proof[key]), initial=0) > 3e-25:
            raise ValueError("Source charge history is inconsistent")
    for key in ("energy_residual_pJ", "chemical_work_residual_pJ", "electrode_work_residual_pJ"):
        if np.max(np.abs(proof[key]), initial=0) > 1e-10:
            raise ValueError("Source energy or variable chemical-work history is inconsistent")
    carried = {key: value.copy() for key, value in arrays.items()}
    carried["phase_clock_s"] = np.zeros(1)
    current.update(
        source_context=original,
        source_arrays=arrays,
        carried_arrays=carried,
        source_time_s=checkpoint["time"],
        source_phase_clock_s=float(arrays["phase_clock_s"][0]),
        padded_shapes=shapes,
        active_masks=masks,
        simulation=deepcopy(target),
        source_proof=proof,
        source_domain_proof=domain_proof,
    )
    return current


def initial(request):
    context = bind(request)
    return context, flatten(context, context["carried_arrays"])


def evaluate(context, state, *, held_time=None):
    return scheduled.evaluate(context, state, held_time=held_time)


def conservation(context, state):
    return scheduled.conservation(context, state)


def operation(context):
    return scheduled.program(context, 0.0)


def verify_epoch(epoch):
    target = target_definition(epoch)
    record = epoch["model"]["handoff"]
    if set(record) != {*POLICIES, "source", "clocks", "controller_operation"}:
        raise ValueError("Incomplete bath epoch operation")
    context, state = initial(
        dict(
            kind=REQUEST_KIND,
            policies={k: record[k] for k in POLICIES},
            source=record["source"],
            simulation=target,
        )
    )
    clocks = dict(
        init_checkpoint_time_s=context["source_time_s"],
        init_phase_clock_s=context["source_phase_clock_s"],
        sim_epoch_time_s=0.0,
        sim_phase_clock_s=0.0,
    )
    if record["clocks"] != clocks:
        raise ValueError("Archived INIT/SIM clocks disagree")
    op = record["controller_operation"]
    if set(op) != {
        "kind",
        "time_s",
        "original_parent_definition_digest",
        "native_bath_binding_identities",
        "bath_site_ids",
        "dose_fmol",
        "charge_C",
        "chemical_work_pJ",
        "electrochemical_work_pJ",
        "electrode_charge_C",
        "electrode_work_pJ",
        "accounting",
        "identity",
    }:
        raise ValueError("Incomplete initial controller dose/charge/work operation")
    if op["kind"] != "cells.surface_bath_initial_controller_operation@1" or op["time_s"] != 0.0:
        raise ValueError("Require the explicit initial controller operation")
    if digest({key: value for key, value in op.items() if key != "identity"}) != op["identity"]:
        raise ValueError("Controller operation identity disagrees")
    if op["original_parent_definition_digest"] != digest(scheduled.parent_definition(target)):
        raise ValueError("Controller operation rebases an original physical anchor")
    m = target["model"]
    if op["bath_site_ids"] != m["bath_site_ids"] or op["accounting"] != (
        "additive initial controller operation against unchanged original anchors"
    ):
        raise ValueError("Controller operation changes its declared owners or accounting policy")
    expected_bindings = []
    for name in m["bath_site_ids"]:
        j = next(i for i, row in enumerate(m["extracellular"]) if row["id"] == name)
        expected_bindings.append(
            digest(
                dict(
                    grid=digest(dict(species=[v["id"] for v in m["species"]], site=name)),
                    events=m["bath_events"],
                    baseline=(context["parent"]["ao"][:, j] / context["parent"]["vo"][j]).tolist(),
                    is_ecm=True,
                    enabled_Cl=m["enabled_Cl"],
                )
            )
        )
    if op["native_bath_binding_identities"] != expected_bindings:
        raise ValueError("Controller operation's literal native bath binding changed")
    expected = operation(context)
    for name in (
        "dose_fmol",
        "charge_C",
        "chemical_work_pJ",
        "electrochemical_work_pJ",
        "electrode_work_pJ",
    ):
        actual = np.asarray(op[name])
        desired = expected[name]
        padded = np.pad(
            desired, [(0, a - b) for a, b in zip(actual.shape, desired.shape, strict=True)]
        )
        if not np.allclose(
            actual, padded, rtol=5e-13, atol=3e-25 if name.endswith("_C") else 3e-12
        ):
            raise ValueError("New SIM controller dose/charge/work disagrees: " + name)
    if not np.allclose(op["electrode_charge_C"], -np.asarray(op["charge_C"]), rtol=0, atol=3e-25):
        raise ValueError("Controller electrode compensation disagrees")
    return context, state


def dependency_manifest(root):
    # The ordinary audit hashes its accepted scalar-helper import closure.
    # This new adapter has no extra local numerical dependencies.
    result = scheduled.dependency_manifest(root)
    path = Path(__file__).resolve()
    tree = ast.parse(path.read_bytes())
    for node in ast.walk(tree):
        names = (
            [v.name for v in node.names]
            if isinstance(node, ast.Import)
            else [node.module or ""]
            if isinstance(node, ast.ImportFrom)
            else []
        )
        if any(name.split(".")[0] in {"cells", "jax", "jaxlib"} for name in names):
            raise ValueError("Production/JAX import in bath epoch reference")
    result[str(path.relative_to(Path(root).resolve()))] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    return dict(sorted(result.items()))
