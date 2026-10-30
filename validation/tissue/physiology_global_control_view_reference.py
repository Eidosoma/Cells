"""Independent ordered global proposals and full original-anchor held rates.

No production/JAX imports; original source binders keep their old temperature
and finite-family guards. New held contexts preserve their original charges.
"""

import math
from copy import deepcopy
from decimal import Decimal, localcontext

import numpy as np

from validation.perturbations import global_controls_reference as setters
from validation.tissue import open_calcium_reference as opened
from validation.tissue import physiology_active_temperature_reference as active
from validation.tissue import physiology_permeability_view_reference as physical
from validation.tissue import physiology_temperature_reference as thermal
from validation.tissue import surface_calcium_energy_reference as finite
from validation.tissue import surface_dynamics_reference as passive
from validation.tissue import surface_kinetic_reference as kinetic

KIND = "cells.physiology_global_control_view_binding@1"
POLICY = "active_uniform_isothermal_fixed_empirical_kinetics@1"
ORDER = ("temperature", "junction_block", "pump_block", "voltage")
ORACLES = thermal.ORACLES
flatten, unpack = active.flatten, active.unpack
F, R = active.F, active.R


def prepare(raw, binding_record, memory, base_control, event_time_s, events_enabled):
    if raw["model"]["id"] not in ORACLES:
        raise ValueError("Independent combined view requires one of the six original families")
    expected = {
        "kind",
        "policy",
        "source_definition_sha256",
        "program",
        "owners",
        "boundary_reservoir_ids",
        "junction_membranes",
        "source_order",
        "units",
        "baseline_policy",
        "clock_policy",
        "provenance",
        "identity",
    }
    if (
        set(binding_record) != expected
        or binding_record["kind"] != KIND
        or binding_record["policy"] != POLICY
        or binding_record["source_order"] != list(ORDER)
        or binding_record["source_definition_sha256"] != thermal._digest(raw)
        or binding_record["identity"]
        != thermal._digest(
            {key: value for key, value in binding_record.items() if key != "identity"}
        )
    ):
        raise ValueError("Independent simultaneous-control policy/source/order identity differs")
    if (
        binding_record["units"]
        != {"temperature": "K", "voltage": "V", "availability": "dimensionless"}
        or binding_record["baseline_policy"] != "multiply_original_held_controls_once@1"
        or binding_record["clock_policy"]
        != "native_event_label_distinct_from_accepted_checkpoint_clock@1"
    ):
        raise ValueError("Independent global-control units or composition semantics differ")
    m = raw["model"].get("ionic", raw["model"])
    if raw["model"]["id"] in ("resolved_calcium@11", "resolved_calcium_energy@5") and any(
        row["reservoir"] for row in m["extracellular"]
    ):
        raise ValueError("Independent original finite family cannot acquire reservoir clamps")
    axes = dict(
        cells=[row["id"] for row in m["cells"]],
        environment=[row["id"] for row in m["extracellular"]],
        membranes=[row["id"] for row in m["membranes"]],
        junctions=[row["id"] for row in m["junctions"]],
        faces=[row["id"] for row in m["faces"]],
        channel_populations=[row["id"] for row in m.get("channels", [])],
        stores=[row["cell_id"] for row in raw["model"].get("stores", [])],
        fuel_pools=[row["id"] for row in raw["model"].get("energy_pools", [])],
    )
    if [row[0] for row in binding_record["owners"]] != list(axes) or any(
        len(ids) != len(set(ids)) or set(ids) != set(axes[name])
        for name, ids in binding_record["owners"]
    ):
        raise ValueError("Independent global temperature owner declaration differs")
    program = binding_record["program"]
    events = program["events"]
    if (
        program["law"] != "betse_global_controls_source_v1_5_0@1"
        or program["identity"]
        != thermal._digest({key: value for key, value in program.items() if key != "identity"})
        or program["membrane_ids"] != axes["membranes"]
    ):
        raise ValueError("Independent native global program owner/identity mismatch")
    kinds = [row["kind"] for row in events]
    if kinds != [kind for kind in ORDER if kind in kinds] or len(set(kinds)) != len(kinds):
        raise ValueError("Independent native setter order or multiplicity differs")
    for event in events:
        if event["kind"] in ("junction_block", "pump_block") and event["amplitude"] != 0:
            raise ValueError("Independent blocker declaration cannot invent an amplitude law")
        if event["kind"] != "voltage" and (
            event["positive_boundary"] is not None or event["negative_boundary"] is not None
        ):
            raise ValueError("Independent non-voltage setter cannot declare electrode sides")
        if (
            not all(
                math.isfinite(event[name]) for name in ("on_s", "off_s", "change_s", "amplitude")
            )
            or event["off_s"] < event["on_s"]
            or event["change_s"] <= 0
        ):
            raise ValueError("Independent native pulse declaration is invalid")
        if (
            len(set(event["target_ids"])) != len(event["target_ids"])
            or any(name not in axes["membranes"] for name in event["target_ids"])
            or (event["kind"] != "junction_block" and event["target_ids"])
        ):
            raise ValueError("Independent native targets differ from actual membrane owners")
    pump_owners = any(row.get("pump") is not None for row in m["membranes"])
    if "pump_block" in kinds and not pump_owners:
        raise ValueError("Independent pump blocker has no actual Na/K owners")
    outside = {row["id"]: row for row in m["extracellular"]}
    rows = binding_record["boundary_reservoir_ids"]
    if [row[0] for row in rows] != list(setters.SIDES):
        raise ValueError("Independent global side declaration differs")
    for _, ids in rows:
        if len(ids) != len(set(ids)) or any(
            name not in outside or not outside[name]["reservoir"] for name in ids
        ):
            raise ValueError("Independent global voltage owners must be actual reservoirs")
    mapping = dict(rows)
    for event in events:
        if event["kind"] == "voltage" and (
            not mapping.get(event["positive_boundary"])
            or not mapping.get(event["negative_boundary"])
        ):
            raise ValueError("Independent active voltage setter has no physical boundary owners")
    membranes = {row["id"]: row for row in m["membranes"]}
    pairs = binding_record["junction_membranes"]
    if [row[0] for row in pairs] != axes["junctions"]:
        raise ValueError("Independent contact rows must match every actual junction")
    used = set()
    for edge, (_name, a, b) in zip(m["junctions"], pairs, strict=True):
        if (
            a == b
            or a not in membranes
            or b not in membranes
            or a in used
            or b in used
            or (membranes[a]["inside"], membranes[b]["inside"])
            != (edge["sender"], edge["receiver"])
        ):
            raise ValueError("Independent actual contact owners/exclusivity differ")
        used.update((a, b))
    if (
        type(events_enabled) is not bool
        or isinstance(event_time_s, bool)
        or not math.isfinite(event_time_s)
    ):
        raise ValueError("Independent source sampling needs an explicit finite event label")
    if (
        set(memory)
        != {"temperature_K", "junction_available", "pump_available", "boundary_voltage_V"}
        or len(memory["junction_available"]) != len(axes["membranes"])
        or len(memory["boundary_voltage_V"]) != 4
    ):
        raise ValueError("Independent native memory is incomplete")
    values = np.r_[
        memory["temperature_K"],
        memory["junction_available"],
        memory["pump_available"],
        memory["boundary_voltage_V"],
    ]
    if (
        not np.isfinite(values).all()
        or memory["temperature_K"] <= 0
        or not 0 <= memory["pump_available"] <= 1
        or any(not 0 <= value <= 1 for value in memory["junction_available"])
    ):
        raise ValueError("Independent original native memory leaves its domain")
    if raw["model"]["id"] != "resolved_tissue@1" and not 200 <= memory["temperature_K"] <= 400:
        raise ValueError("Independent original active memory leaves 200-400 K")
    after = setters.evaluate(
        program, memory, event_time_s, m["temperature_K"], events_enabled=events_enabled
    )
    if (
        not np.isfinite(
            np.r_[
                after["temperature_K"],
                after["junction_available"],
                after["pump_available"],
                after["boundary_voltage_V"],
            ]
        ).all()
        or after["temperature_K"] <= 0
        or not 0 <= after["pump_available"] <= 1
        or any(not 0 <= value <= 1 for value in after["junction_available"])
    ):
        raise ValueError("Independent simultaneous setter proposal leaves its physical domain")
    if raw["model"]["id"] != "resolved_tissue@1" and not 200 <= after["temperature_K"] <= 400:
        raise ValueError("Independent held active T leaves 200-400 K")
    if after["pump_available"] != 1 and not pump_owners:
        raise ValueError("Independent carried blocker has no actual Na/K owner")
    writes = {}
    for i, (_, ids) in enumerate(rows):
        value = after["boundary_voltage_V"][i]
        if not ids and value != 0:
            raise ValueError("Independent nonneutral voltage has no side owner")
        for name in ids:
            if name in writes and value != writes[name]:
                raise ValueError("Independent corner writes conflict")
            writes[name] = value
    effective_control = deepcopy(base_control)
    with localcontext() as precision:
        precision.prec = 100

        def multiply(a, b):
            return float(Decimal.from_float(float(a)) * Decimal.from_float(float(b)))

        for i, (_, a, b) in enumerate(pairs):
            av, bv = (after["junction_available"][axes["membranes"].index(name)] for name in (a, b))
            if av != bv:
                raise ValueError("Independent physical junction factors are asymmetric")
            effective_control["junction"][i] = multiply(base_control["junction"][i], av)
        if "pump" in effective_control:
            effective_control["pump"] = [
                multiply(value, after["pump_available"]) for value in base_control["pump"]
            ]
    return after, effective_control, writes


def bind(raw, binding_record, memory, base_control, event_time_s, events_enabled):
    after, control, writes = prepare(
        raw, binding_record, memory, base_control, event_time_s, events_enabled
    )
    source = deepcopy(raw)
    physical._hold(source, control)
    base = ORACLES[raw["model"]["id"]].bind(source)
    effective = deepcopy(source)
    ion = effective["model"].get("ionic", effective["model"])
    ion["temperature_K"] = after["temperature_K"]
    for owner in ion["extracellular"]:
        if owner["id"] in writes:
            owner["boundary_potential_V"] = writes[owner["id"]]
    with localcontext() as precision:
        precision.prec = 100
        for row in effective["model"].get("stores", []):
            row["model"]["temperature_K"] = after["temperature_K"]
            for species in row["model"]["species"]:
                species["standard_mu_RT"] = float(
                    Decimal.from_float(float(species["standard_mu_RT"]))
                    * Decimal.from_float(298.15)
                    / Decimal.from_float(after["temperature_K"])
                )
    model_id = raw["model"]["id"]
    is_open, is_fuel = model_id.startswith("resolved_open"), "energy" in model_id
    equation = opened.equation_definition(effective) if is_open else effective
    if model_id == "resolved_tissue@1":
        context = deepcopy(base)
        context["raw"] = deepcopy(effective)
        context["layout"]["temperature"] = after["temperature_K"]
    elif model_id == "resolved_tissue@12":
        context = active._ionic_context(base, effective)
    elif not is_fuel:
        context = active._calcium_context(base, equation)
    else:
        context = deepcopy(base)
        context.update(
            raw=deepcopy(equation),
            temperature=after["temperature_K"],
            calcium_template=deepcopy(base["calcium"]),
        )
        context["calcium"] = active._calcium_context(
            context["calcium_template"], finite._project(context, context["energy_initial"])
        )
    if is_open:
        context.update(open_definition=deepcopy(effective), equation_definition=deepcopy(equation))
    context["active_temperature"] = dict(
        source=source,
        effective=effective,
        setter=after,
        finite_fuel=is_fuel,
        open_world=is_open,
        source_model_id=model_id,
    )
    context["global_control"] = dict(after=after, effective_control=control, writes=writes)
    return context


def _physical_clock(raw, clock):
    """Independently rank the source event-split grid without horizon arrays."""
    if (
        set(clock) != {"time", "step_index", "event_index"}
        or isinstance(clock["time"], bool)
        or not isinstance(clock["time"], (int, float))
        or not math.isfinite(clock["time"])
        or any(
            type(clock[key]) is not int or clock[key] < 0 for key in ("step_index", "event_index")
        )
    ):
        raise ValueError("Independent physical checkpoint clock is malformed")
    events = {0.0}

    def visit(value):
        if isinstance(value, dict):
            if "time" in value:
                events.add(value["time"])
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(raw["experiment"])
    dt, end = raw["execution"]["dt"], raw["experiment"]["end_time"]
    t = clock["time"]
    if not 0 <= t <= end:
        raise ValueError("Independent physical time leaves the source horizon")
    last = max(0, math.ceil(end / dt) - 1)
    while last > 0 and last * dt >= end:
        last -= 1

    def nominal_rank(value):
        low, high = 0, last + 1
        while low < high:
            middle = (low + high) // 2
            if middle * dt < value:
                low = middle + 1
            else:
                high = middle
        return low

    extras = []
    for value in sorted(events):
        if value in (0.0, end):
            continue
        rank = nominal_rank(value)
        if rank > last or rank * dt != value:
            extras.append(value)
    rank = nominal_rank(t)
    if t != end and t not in extras and not (rank <= last and rank * dt == t):
        raise ValueError("Independent physical time is not an accepted source boundary")
    index = (last + 1 + len(extras)) if t == end else rank + sum(value < t for value in extras)
    event = sum(value <= t for value in events) - 1
    if clock["step_index"] != index or clock["event_index"] != event:
        raise ValueError("Independent physical step/event position differs from source schedule")


def evaluate(
    raw, fields, binding_record, memory, base_control, event_time_s, events_enabled, physical_clock
):
    _physical_clock(raw, physical_clock)
    context = bind(raw, binding_record, memory, base_control, event_time_s, events_enabled)
    if set(fields) != set(context["shapes"]):
        raise ValueError("Independent combined view requires every ordinary state field")
    policy = context["active_temperature"]
    if policy["open_world"]:
        opened.validate_padded_state(context, fields)
    packed = flatten(context, fields)
    if policy["source_model_id"] == "resolved_tissue@1":
        evaluator = passive.evaluate
    elif policy["source_model_id"] == "resolved_tissue@12":
        evaluator = kinetic.evaluate
    else:
        evaluator = active._fuel_rates if policy["finite_fuel"] else active._calcium_rates
    if policy["open_world"]:
        total = opened.ionic_moieties(context, packed)
        limit = context["ionic_moiety_ceiling_fmol"]
        if limit is not None and np.any(total > limit):
            raise ValueError("Independent open ionic ceiling exceeded")
    rate, phi, proof = evaluator(context, packed, 0.0)
    proof = dict(
        proof,
        policy=POLICY,
        source_definition_sha256=thermal._digest(raw),
        source_order=list(ORDER),
        native_proposal=context["global_control"]["after"],
        effective_control=context["global_control"]["effective_control"],
        named_boundary_voltages=context["global_control"]["writes"],
        original_physical_clock=deepcopy(physical_clock),
        native_event_time_s=event_time_s,
        accepted_stepping=False,
        accepted_heat_pJ=None,
    )
    proof["physical_field_columns"] = (
        field_columns(context, fields, rate, phi, proof)
        if policy["source_model_id"] == "resolved_tissue@1"
        else active.field_columns(context, fields, rate, phi, proof)
    )
    return context, rate, phi, proof


def field_columns(context, fields, rate, phi, proof):
    """Independent complete physical field outputs; solver counters are not physics."""
    policy = context["active_temperature"]
    physical = context["calcium"] if policy["finite_fuel"] else context
    state, slope = unpack(physical, flatten(physical, fields)), unpack(context, rate)
    raw = kinetic.base.stage(physical, flatten(physical, fields), 0.0)
    ion, p = physical["raw"]["model"], physical["layout"]
    n, o, nm = len(ion["cells"]), len(ion["extracellular"]), len(ion["membranes"])
    if policy["source_model_id"] not in ("resolved_tissue@1", "resolved_tissue@12"):
        raw["ci"] = np.stack(
            [
                (store.n0 + state["chemical_amount_increment"][i])[
                    [store.ids.index(row["id"]) for row in ion["species"]], store.cy
                ]
                / physical["vi"][i]
                for i, store in enumerate(physical["stores"])
            ],
            axis=1,
        )
    ci, co, z = np.asarray(raw["ci"]), np.asarray(raw["co"]), np.asarray(p["valence"])
    membrane = np.asarray(slope["membrane_transferred"]).copy()
    membrane_d = np.asarray(slope["membrane_dissipated_energy_pJ"]).copy() + slope.get(
        "pump_dissipated_energy_pJ", np.zeros(nm)
    )
    ids = [row["id"] for row in ion["species"]]
    patches = [row["id"] for row in ion["membranes"]]
    for j, population in enumerate(ion.get("channels", [])):
        k = patches.index(population["membrane_id"])
        membrane[:, k] += slope["channel_transferred"][:, j]
        membrane_d[k] += np.sum(slope["channel_dissipated_energy_pJ"][:, j])
    for j, patch in enumerate(ion["membranes"]):
        pump = patch.get("pump")
        if pump is not None:
            for name, coefficient in pump["stoichiometry"].items():
                membrane[ids.index(name), j] -= coefficient * slope["pump_cycles"][j]
    if "plasma_pump_cycles" in slope:
        model = policy["effective"]["model"]
        plasma = model["plasma_transport"]
        membrane[ids.index(plasma["calcium_species"])] += (
            slope["plasma_pump_cycles"]
            + slope["plasma_exchange_cycles"]
            + slope["calcium_channel_transferred"]
        )
        membrane[ids.index(plasma["sodium_species"])] -= 3 * slope["plasma_exchange_cycles"]
        membrane_d += (
            np.sum(slope["plasma_dissipated_energy_pJ"], axis=0)
            + slope["calcium_channel_dissipated_energy_pJ"]
        )
    targets = {}

    def add(name, value, atol=3e-12, rtol=3e-10):
        targets[name] = dict(value=np.asarray(value).tolist(), atol=atol, rtol=rtol)

    for name, value in (
        ("cell_rate_fmol_s", slope["amount_increment"]),
        ("outside_rate_fmol_s", slope["extracellular_amount_increment"]),
        ("reservoir_supply_fmol_s", slope["reservoir_supplied"]),
    ):
        add("rates." + name, value)
    for kind, left, right, dv, flux, diss in (
        (
            "membrane",
            ci[:, p["membrane_cell"]],
            co[:, p["membrane_outside"]],
            phi[np.asarray(p["membrane_cell"], dtype=int)]
            - phi[n + np.asarray(p["membrane_outside"], dtype=int)],
            membrane,
            membrane_d,
        ),
        (
            "junction",
            ci[:, p["junction_sender"]],
            ci[:, p["junction_receiver"]],
            phi[np.asarray(p["junction_sender"], dtype=int)]
            - phi[np.asarray(p["junction_receiver"], dtype=int)],
            slope["junction_transferred"],
            slope["junction_dissipated_energy_pJ"],
        ),
        (
            "face",
            co[:, p["face_sender"]],
            co[:, p["face_receiver"]],
            phi[n + np.asarray(p["face_sender"], dtype=int)]
            - phi[n + np.asarray(p["face_receiver"], dtype=int)],
            slope["face_transferred"],
            slope["face_dissipated_energy_pJ"],
        ),
    ):
        add("rates." + kind + "_voltage_V", dv, 3e-13)
        add("rates." + kind + "_flux_fmol_s", flux)
        add(
            "rates." + kind + "_delta_mu_J_mol",
            R * p["temperature"] * (np.log(left) - np.log(right)) + z * F * dv,
            3e-10,
        )
        add("rates." + kind + "_current_A", 1e-15 * F * np.sum(z * flux, axis=0), 3e-23)
        add("rates." + kind + "_dissipation_pJ_s", diss)
    matrix, active, reservoir, _, floating, _ = opened.electrical.topology(raw)
    capacitor_charge = matrix @ phi
    add("capacitor_node_charge_C", capacitor_charge, 3e-25, 2e-12)
    add(
        "membrane_charge_C",
        np.asarray(p["membrane_capacitance"]) * targets["rates.membrane_voltage_V"]["value"],
        3e-25,
        2e-12,
    )
    required = active & ~reservoir
    charge = np.r_[raw["cell_charge_C"], raw["outside_charge_C"]]
    add("charge_residual_C", np.where(required, capacitor_charge - charge, 0.0), 3e-25, 2e-12)
    add(
        "electrode_charge_C",
        np.where(p["reservoir"], (capacitor_charge - charge)[n:], 0.0),
        3e-25,
        2e-12,
    )
    current = (
        1e-15
        * F
        * np.sum(
            z * np.c_[slope["amount_increment"], slope["extracellular_amount_increment"]], axis=0
        )
    )
    pins = ~active | reservoir
    for members in floating:
        pins[members[0]] = True
    free = np.flatnonzero(~pins)
    dphi = np.zeros(n + o)
    dphi[free] = np.linalg.solve(matrix[np.ix_(free, free)], current[free])
    add(
        "membrane_voltage_rate_V_s",
        dphi[np.asarray(p["membrane_cell"], dtype=int)]
        - dphi[n + np.asarray(p["membrane_outside"], dtype=int)],
    )
    add("electrode_current_A", slope["electrode_charge_transferred_C"], 3e-23)
    add(
        "reservoir_supply_charge_A",
        1e-15 * F * np.sum(z * slope["reservoir_supplied"], axis=0),
        3e-23,
    )
    cap_energy, cap_power = 0.0, 0.0
    for j in range(nm):
        v = targets["rates.membrane_voltage_V"]["value"][j]
        dv = targets["membrane_voltage_rate_V_s"]["value"][j]
        cap_energy += 0.5e12 * p["membrane_capacitance"][j] * v**2
        cap_power += 1e12 * p["membrane_capacitance"][j] * v * dv
    add("capacitor_energy_pJ", cap_energy, 3e-14)
    add("capacitor_energy_rate_pJ_s", proof.get("capacitor_power_pJ_s", cap_power))
    chemical = (
        1e-3
        * R
        * p["temperature"]
        * (
            np.sum(np.log(ci) * slope["amount_increment"])
            + np.sum(np.log(co) * slope["extracellular_amount_increment"])
        )
    )
    add("chemical_energy_rate_pJ_s", proof.get("chemical_power_pJ_s", chemical))
    add("reservoir_power_pJ_s", np.sum(slope["reservoir_work_pJ"]))
    add("electrode_power_pJ_s", np.sum(slope["electrode_work_pJ"]))
    add(
        "dissipation_pJ_s",
        sum(
            float(np.sum(value))
            for name, value in slope.items()
            if name.endswith("_dissipated_energy_pJ")
        ),
    )
    add("energy_balance_pJ_s", proof.get("physical_energy_balance_pJ_s", 0.0))
    return targets
