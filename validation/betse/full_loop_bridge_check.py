"""Saved-data pilot gates; exact correspondence, not a new numerical/biology audit."""

import contact as c
import full_loop_bridge_context as ctx
import phase_bridge as legacy
import profile_bridge_check as preparation
import profile_bridge_context as profiles
import trajectory_context as trajectory
from full_loop_observer import PRE_LOOP_CALLS
from trajectory_check import unpack

LINKS = {
    "inside_mM": "cc_cells",
    "outside_mM": "cc_env",
    "voltage_V": "vm",
    "rho_C_per_m3": "rho_cells",
    "inward_current_A": "I_mem",
    "boundary_voltage_V": "Phi_b",
}
FIXED = {
    "Dm_cells",
    "Dm_base",
    "Dm_scheduled",
    "P_cells",
    "P_base",
    "P_mod",
    "zs",
    "NaKATP_block",
    "CaATP_block",
    "gj_block",
    "Phi_b",
}


def prepared_packet(row):
    """The pilot uses exactly D074's six preparation inputs, not extrapolated metadata."""
    registered_rows = profiles.rows(c.read(profiles.PLAN))
    c.require(row in registered_rows, "Pilot row lacks an accepted D074 preparation")
    directory = (
        c.ROOT
        / c.read(ctx.PRIOR)["native_attempt"]
        / f"preparation-{registered_rows.index(row):02d}"
    )
    return {name: c.read(directory / (name + ".json")) for name in ("core", "ready", "metadata")}


def read_packet(directory, mode):
    c.require(mode in ctx.MODES, "Unknown observation mode")
    names = {"core": "core.json", "result": "result.json"}
    if mode == "observed":
        names |= {
            "dynamics": "dynamics.json",
            "entry": "loop-entry.json",
            "metadata": "loop-metadata.json",
            "events": "events.json",
        }
    packet = {name: c.read(directory / path) for name, path in names.items()}
    result = packet["result"]
    c.require(
        result["final_state"] == c.read(directory / "final-state.json")
        and result["final_metadata"] == c.read(directory / "final-metadata.json")
        and result["numerical"]["native_yaml_sha256"] == c.sha(directory / "native.yaml"),
        "Durable final copies or YAML link differ",
    )
    c.require(
        result["final_metadata"]["pickles_present"]
        == {
            name: (directory / path).is_file()
            for name, path in {
                "seed": "INITS/world_1.betse.gz",
                "init": "INITS/init_1.betse.gz",
                "sim": "SIMS/sim_1.betse.gz",
            }.items()
        },
        "Recorded/actual native serialization presence differs",
    )
    return packet


def state_snapshot(state):
    return {key: state["arrays"][name]["values"] for key, name in LINKS.items()}


def check_state(state, initial, owners):
    c.require(set(state) == set(initial), "Event-state fields differ")
    preparation.check_arrays(state["arrays"], legacy.EVENT_ARRAYS)
    c.require(
        {key: value for key, value in state.items() if key != "arrays"}
        == {key: value for key, value in initial.items() if key != "arrays"},
        "Event scaling/temperature differs",
    )
    arrays = state["arrays"]
    c.require(
        all(arrays[name] == initial["arrays"][name] for name in FIXED),
        "No-op pilot changed a fixed control",
    )
    c.require(
        arrays["cc_at_mem"]["values"]
        == [[values[i] for i in owners] for values in arrays["cc_cells"]["values"]],
        "Membrane concentration ownership differs",
    )
    c.require(
        all(v == 0 for v in legacy.flatten(arrays["fluxes_gj"]["values"])),
        "Disabled junction transport is nonzero",
    )


def numerical_payload(record, *, observer_pair=False):
    # YAML includes phase/profile/event settings and output paths, not numerical results.
    omit = {"native_yaml_sha256"} | ({"mode", "trace"} if observer_pair else set())
    return {key: value for key, value in record.items() if key not in omit}


def check_row(row, mode, packet, prior, retained, prepared):
    expected_stages = {"core", "result"}
    if mode == "observed":
        expected_stages |= {"dynamics", "entry", "metadata", "events"}
    c.require(set(packet) == expected_stages, "Incomplete full-loop evidence")
    result = packet["result"]
    c.require(
        result["schema"] == "cells.betse_full_loop_bridge_row@1"
        and result["status"] == "exported_not_qualified"
        and result["row"] == row
        and result["mode"] == mode
        and result["hook_restored"] is True,
        "Full-loop row identity/status differs",
    )
    _, mapped = profiles.mapping(row)
    preparation.check_metadata(row, prepared["metadata"], prior, mapped)
    preparation.check_state(prepared["ready"]["state"])
    c.require(packet["core"] == prepared["core"], "Fresh SIM core differs from D074")
    # Validate actual final lifecycle flags. Only this field may differ from
    # accepted preparation metadata; no fictional pre-serialization record is made.
    c.require(
        result["final_metadata"]
        == prepared["metadata"] | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "Final metadata/normal SIM serialization presence differs",
    )
    c.require(result["final_junctions"] == packet["core"]["junctions"], "Junction topology changed")
    numerical = result["numerical"]
    c.require(
        numerical_payload(numerical) == numerical_payload(retained),
        "SIM numerical record differs from retained INIT",
    )
    c.require(
        set(numerical["ordinary"]) == set(trajectory.ORDINARY_NAMES)
        and set(numerical["final"]) == set(trajectory.FINAL_NAMES),
        "Numerical export coverage differs",
    )
    for group in ("ordinary", "final"):
        for array in numerical[group].values():
            unpack(array)
    initial = prepared["ready"]["state"]
    owners = prior["geometry"]["membrane_owners"]
    check_state(result["final_state"], initial, owners)
    c.require(
        {name: result["final_state"]["arrays"][name] for name in trajectory.FINAL_NAMES}
        == numerical["final"],
        "Final event-state and numerical arrays disagree",
    )
    if mode == "unobserved":
        c.require(
            result["lifecycle"] is None and numerical["trace"] is None,
            "Observer-off partner contains a trace",
        )
        return {"status": "capture_row_checks_pass", "observed_steps": 0}
    entry, events, trace = packet["entry"], packet["events"], numerical["trace"]
    c.require(
        packet["dynamics"] == packet["core"]
        and packet["metadata"] == prepared["metadata"]
        and entry["state"] == initial
        and entry["initial"] == trace["initial"] == state_snapshot(initial)
        and entry["pre_loop_calls"] == PRE_LOOP_CALLS
        and entry["labels_s"] == trace["labels_s"]
        and entry["sampled_indices"] == trace["sampled_indices"],
        "Observed native setup/entry differs",
    )
    c.require(
        result["lifecycle"] == {"calls": PRE_LOOP_CALLS, "run_returns": 1, "hook_restored": True},
        "Normal native lifecycle incomplete",
    )
    count = mapped["steps"]
    c.require(
        events["mode"] == "full_sim_loop"
        and events["initial"] == initial
        and events["integration_calls"] == 1
        and events["hook_restored"] is True
        and len(events["events"]) == len(trace["steps"]) == count,
        "Full-loop event coverage differs",
    )
    previous = trace["initial"]
    for index, (event, step) in enumerate(zip(events["events"], trace["steps"], strict=True)):
        c.require(
            set(event)
            == {"index", "raw_label_s", "before", "after", "before_update", "flux_ion_indices"}
            and event["index"] == index
            and event["raw_label_s"] == trace["labels_s"][index]
            and event["flux_ion_indices"] == list(range(6))
            and step["before_elapsed_s"] == index * row["dt_s"]
            and step["after_elapsed_s"] == (index + 1) * row["dt_s"],
            "Event/flux/update order or clock differs",
        )
        for boundary in ("before", "after", "before_update"):
            check_state(event[boundary], initial, owners)
        c.require(event["before"] == event["after"], "No-op dispatch changed copied state bytes")
        c.require(state_snapshot(event["before"]) == previous, "Pre-event boundary differs")
        c.require(
            all(v == 0 for v in legacy.flatten(event["before"]["arrays"]["fluxes_mem"]["values"])),
            "Event did not follow native flux reset",
        )
        # electroflux mutates vm by its source nonce; before_update is the legacy
        # post-flux boundary, NOT an assertion that the entire event state stayed fixed.
        c.require(
            state_snapshot(event["before_update"]) == step["before"]
            and event["before_update"]["arrays"]["fluxes_mem"]["values"]
            == step["density_mol_per_m2_s"]
            and event["before_update"]["arrays"]["fluxes_gj"]["values"]
            == step["junction_density_mol_per_m2_s"],
            "Post-flux event export differs from the native step trace",
        )
        previous = step["after"]
    return {"status": "capture_row_checks_pass", "observed_steps": count}


def check_pair(pair):
    c.require(set(pair) == set(ctx.MODES), "Missing observer partner")
    left, right = (pair[mode]["result"] for mode in ctx.MODES)
    c.require(
        numerical_payload(left["numerical"], observer_pair=True)
        == numerical_payload(right["numerical"], observer_pair=True)
        and pair["observed"]["core"] == pair["unobserved"]["core"]
        and all(left[k] == right[k] for k in ("final_state", "final_metadata", "final_junctions")),
        "Observer changes physical/numerical outputs",
    )
    return {"status": "observer_pair_exact"}


def check_variants(variants):
    c.require(set(variants) == set(ctx.VARIANTS), "Missing phase/profile/no-op control")
    baseline = variants["baseline"]
    for name in ("default_profile", "zero_amplitude"):
        alternate = variants[name]
        for stage in ("core", "dynamics", "entry", "events"):
            c.require(alternate[stage] == baseline[stage], "Variant changes physical " + stage)
        left, right = alternate["result"], baseline["result"]
        c.require(
            numerical_payload(left["numerical"]) == numerical_payload(right["numerical"])
            and left["final_state"] == right["final_state"]
            and left["final_junctions"] == right["final_junctions"],
            "Variant changes numerical trajectory/final state",
        )
    return {"status": "profile_and_noop_controls_exact", "comparisons": 2}
