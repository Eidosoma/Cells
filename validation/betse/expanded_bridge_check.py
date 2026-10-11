"""Expanded capture gates, using actual entry states and explicit input expectations.

These are correspondence/control checks, not the later independent arithmetic audit.
No extrapolated preparation is presented as native evidence.
"""

import copy

import contact as c
import expanded_bridge_context as ctx
import full_loop_bridge_check as pilot
import phase_bridge as legacy
import profile_bridge_check as preparation
import profile_bridge_context as profiles
import trajectory_context as trajectory
from full_loop_observer import PRE_LOOP_CALLS
from trajectory_check import unpack


def input_expectations(row, prior):
    """Derive static metadata only; never synthesize an evolved/charged state."""
    ctx.validate_row(row)
    prepared = pilot.prepared_packet(ctx.pilot_row(row))
    _, mapped = profiles.mapping(row)
    expected = copy.deepcopy(prepared["metadata"])
    expected.update(
        constants=copy.deepcopy(prior["base_protocol"]["profiles"][row["profile"]]),
        dt_s=row["dt_s"],
        sampling_s=row["dt_s"],
        configured_steps=mapped["steps"],
    )
    if row["variant"] == "zero_amplitude":
        for ion in ("Na", "K", "Cl"):
            expected["scheduled_options"][ion + "_mem"] = [
                *mapped["mapped_pulse_times_s"],
                0.0,
                ["Base"],
                "None",
            ]
    # This validator checks the expected input against the registered mapping.
    # Observed native metadata is independently checked below, after export.
    preparation.check_metadata(row, expected, prior, mapped)
    return prepared, expected, mapped


def check_events(row, packet, initial, owners, count):
    entry, events = packet["entry"], packet["events"]
    result, trace = packet["result"], packet["result"]["numerical"]["trace"]
    c.require(
        entry["initial"] == trace["initial"] == pilot.state_snapshot(initial)
        and entry["pre_loop_calls"] == PRE_LOOP_CALLS
        and entry["labels_s"] == trace["labels_s"]
        and entry["sampled_indices"] == trace["sampled_indices"],
        "Observed native entry/clock differs",
    )
    c.require(
        result["lifecycle"] == {"calls": PRE_LOOP_CALLS, "run_returns": 1, "hook_restored": True},
        "Normal native lifecycle incomplete",
    )
    c.require(
        events["mode"] == "full_sim_loop"
        and events["initial"] == initial
        and events["integration_calls"] == 1
        and events["hook_restored"] is True
        and len(events["events"]) == len(trace["steps"]) == count,
        "Expanded event coverage differs",
    )
    previous = trace["initial"]
    for index, (event, step) in enumerate(zip(events["events"], trace["steps"], strict=True)):
        c.require(
            set(event)
            == {"index", "raw_label_s", "before", "after", "before_update", "flux_ion_indices"}
            and event["index"] == step["index"] == index
            and event["raw_label_s"] == trace["labels_s"][index]
            and event["flux_ion_indices"] == list(range(6))
            and step["before_elapsed_s"] == index * row["dt_s"]
            and step["after_elapsed_s"] == (index + 1) * row["dt_s"],
            "Event/flux/update order or clock differs",
        )
        for boundary in ("before", "after", "before_update"):
            pilot.check_state(event[boundary], initial, owners)
        c.require(event["before"] == event["after"], "No-op dispatch changed copied state bytes")
        c.require(pilot.state_snapshot(event["before"]) == previous, "Pre-event boundary differs")
        c.require(
            all(v == 0 for v in legacy.flatten(event["before"]["arrays"]["fluxes_mem"]["values"])),
            "Event did not follow native flux reset",
        )
        # Retain the real post-electroflux boundary (including native vm += nonce).
        c.require(
            pilot.state_snapshot(event["before_update"]) == step["before"]
            and event["before_update"]["arrays"]["fluxes_mem"]["values"]
            == step["density_mol_per_m2_s"]
            and event["before_update"]["arrays"]["fluxes_gj"]["values"]
            == step["junction_density_mol_per_m2_s"],
            "Post-flux event export differs from native step trace",
        )
        previous = step["after"]


def check_row(row, mode, packet, prior, retained):
    c.require(mode in ctx.MODES, "Unknown observation mode")
    expected_stages = {"core", "result"}
    if mode == "observed":
        expected_stages |= {"dynamics", "entry", "metadata", "events"}
    c.require(set(packet) == expected_stages, "Incomplete expanded evidence")
    result = packet["result"]
    c.require(
        result["schema"] == "cells.betse_full_loop_bridge_row@1"
        and result["status"] == "exported_not_qualified"
        and result["row"] == row
        and result["mode"] == mode
        and result["hook_restored"] is True,
        "Expanded row identity/status differs",
    )
    prepared, expected, mapped = input_expectations(row, prior)
    # Geometry/core concentrations/permeability/topology are F/R and dt independent;
    # charge and voltage are NOT: those are checked against the matching INIT below.
    c.require(packet["core"] == prepared["core"], "Fresh SIM core differs from fixed preparation")
    c.require(
        result["final_metadata"]
        == expected | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "Final metadata/normal SIM serialization differs from explicit inputs",
    )
    c.require(result["final_junctions"] == packet["core"]["junctions"], "Junction topology changed")
    numerical = result["numerical"]
    c.require(
        numerical["id"] == ctx.group_key(row)
        and numerical["mode"] == mode
        and numerical["dt_s"] == row["dt_s"]
        and numerical["constants"] == expected["constants"]
        and numerical["configured_steps"] == mapped["steps"]
        and pilot.numerical_payload(numerical) == pilot.numerical_payload(retained),
        "SIM numerical record differs from matching retained INIT",
    )
    c.require(
        set(numerical["ordinary"]) == set(trajectory.ORDINARY_NAMES)
        and set(numerical["final"]) == set(trajectory.FINAL_NAMES),
        "Numerical export coverage differs",
    )
    for group in ("ordinary", "final"):
        for array in numerical[group].values():
            unpack(array)
    owners = prior["geometry"]["membrane_owners"]
    # Observer-off has no captured entry. Its fixed-control reference is D074;
    # its complete final arrays are checked to INIT here and to its observed pair.
    initial = packet["entry"]["state"] if mode == "observed" else prepared["ready"]["state"]
    preparation.check_state(initial)
    pilot.check_state(result["final_state"], initial, owners)
    c.require(
        {name: result["final_state"]["arrays"][name] for name in trajectory.FINAL_NAMES}
        == numerical["final"],
        "Final event-state and numerical arrays disagree",
    )
    if mode == "unobserved":
        c.require(result["lifecycle"] is None and numerical["trace"] is None, "Observer-off trace")
        return {"status": "capture_row_checks_pass", "observed_steps": 0}
    preparation.check_metadata(row, packet["metadata"], prior, mapped)
    c.require(
        packet["metadata"] == expected
        and packet["dynamics"] == packet["core"]
        and {name: initial["arrays"][name] for name in legacy.CORE_ARRAYS}
        == packet["core"]["arrays"]
        and pilot.state_snapshot(initial) == retained["trace"]["initial"]
        and initial["arrays"]["Dm_cells"] == retained["final"]["Dm_cells"],
        "Actual observed preparation differs from inputs/matching INIT",
    )
    pilot.check_state(initial, initial, owners)
    check_events(row, packet, initial, owners, mapped["steps"])
    return {"status": "capture_row_checks_pass", "observed_steps": mapped["steps"]}


def check_variant(baseline, alternate):
    left, right = baseline["result"], alternate["result"]
    c.require(
        left["row"]["variant"] == "baseline"
        and right["row"]["variant"] in ("default_profile", "zero_amplitude")
        and ctx.group_key(left["row"]) == ctx.group_key(right["row"]),
        "Wrong variant comparison group",
    )
    for stage in ("core", "dynamics", "entry", "events"):
        c.require(baseline[stage] == alternate[stage], "Variant changes physical " + stage)
    c.require(
        pilot.numerical_payload(left["numerical"]) == pilot.numerical_payload(right["numerical"])
        and left["final_state"] == right["final_state"]
        and left["final_junctions"] == right["final_junctions"],
        "Variant changes numerical trajectory/final state",
    )
    return {"status": "variant_control_exact", "variant": right["row"]["variant"]}


def check_overlap(row, mode, packet):
    c.require(ctx.overlap(row), "Row is outside original pilot overlap")
    saved = pilot.read_packet(ctx.pilot_path(row, mode), mode)
    for stage in set(packet) - {"result"}:
        c.require(packet[stage] == saved[stage], "Original pilot overlap stage differs: " + stage)
    left, right = packet["result"], saved["result"]
    c.require(
        {k: v for k, v in left.items() if k != "numerical"}
        == {k: v for k, v in right.items() if k != "numerical"}
        and pilot.numerical_payload(left["numerical"])
        == pilot.numerical_payload(right["numerical"]),
        "Original pilot overlap result differs",
    )
    return {"status": "original_pilot_overlap_exact"}
