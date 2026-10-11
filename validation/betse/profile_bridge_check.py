"""Strict saved-preparation checks; no native/Cells imports or numerical integration."""

import contact as c
import phase_bridge as legacy
import profile_bridge_context as ctx
from trajectory_check import unpack

STAGES = ("core", "dynamics", "ready", "metadata", "dispatch", "final")
PREPARATION_CALLS = {
    "seed": 1,
    "init_core": 2,
    "init_dynamics": 1,
    "clear_storage": 1,
    "update_V": 1,
}
SHAPES = {
    "cc_cells": [6, 7],
    "cc_env": [6, 30],
    "cc_at_mem": [6, 30],
    "Dm_cells": [6, 30],
    "P_cells": [7],
    "zs": [6],
    "vm": [30],
    "rho_cells": [7],
    "I_mem": [30],
    "Phi_b": [100],
    "Dm_base": [6, 30],
    "Dm_scheduled": [6, 30],
    "P_base": [7],
    "P_mod": [7],
    "fluxes_mem": [6, 30],
    "fluxes_gj": [6, 30],
    "CaATP_block": [30],
}


def check_arrays(arrays, names):
    legacy.check_arrays(arrays, names)
    for name, record in arrays.items():
        if name in ("NaKATP_block", "gj_block"):
            c.require(record == {"scalar": 1}, "Unexpected pump/GJ block representation")
        else:
            c.require(record["shape"] == SHAPES[name], "Preparation array axis differs: " + name)


def check_state(state):
    c.require(
        set(state) == {"arrays", "temperature_K", "rho_channel", "rho_pump"}, "State fields differ"
    )
    check_arrays(state["arrays"], legacy.EVENT_ARRAYS)
    c.require(
        state["temperature_K"] == 310.15 and state["rho_channel"] == state["rho_pump"] == 1,
        "Native state scaling differs",
    )
    a = state["arrays"]
    c.require(a["Dm_cells"] == a["Dm_base"], "Diffusion baseline changed")
    c.require(a["zs"]["values"] == [1, 1, -1, 2, -1, -1], "Valence changed")
    for name in ("Dm_scheduled", "P_cells", "P_base", "P_mod", "fluxes_mem", "fluxes_gj"):
        c.require(
            all(v == 0 for v in legacy.flatten(a[name]["values"])), "Nonzero prepared " + name
        )
    c.require(all(v == 1 for v in a["CaATP_block"]["values"]), "Calcium pump block changed")


def check_metadata(row, m, prior, mapped):
    base = prior["base_protocol"]
    enabled = mapped["profiles_enabled"]
    c.require(
        m["phase"] == "SIM"
        and m["run_sim_flag"] is True
        and m["profiles_enabled"] is enabled
        and m["dt_s"] == m["sampling_s"] == row["dt_s"]
        and m["sample_stride"] == 1
        and m["duration_s"] == mapped["duration_s"]
        and m["configured_steps"] == mapped["steps"],
        "Native phase/profile/clock differs",
    )
    c.require(
        m["geometry"] == prior["geometry"]
        and m["settings"] == prior["settings"]
        and m["constants"] == base["profiles"][row["profile"]]
        and m["thickness_m"] == base["thickness_m"]
        and m["species"] == base["expected_species"]
        and m["moving_ion_indices"] == list(range(6)),
        "Physical preparation metadata differs",
    )
    protocol, _ = ctx.mapping(row)
    overrides = {tuple(path): value for path, value in protocol["yaml_overrides"]}
    configured = {
        "name": "Base",
        "diffusion_m2_per_s": {
            ion: overrides[
                (
                    "tissue profile definition",
                    "tissue",
                    "default",
                    "diffusion constants",
                    "Dm_" + ion,
                )
            ]
            for ion in base["expected_species"]
        },
    }
    c.require(m["configured_default"] == configured, "Configured default differs")
    c.require(
        m["resolved_default"] == (configured if enabled else None),
        "Resolved profile presence differs",
    )
    c.require(
        m["profile_names"] == (["Base"] if enabled else [])
        and m["additional_profile_count"] == m["cut_profile_count"] == 0,
        "Extra/missing profiles",
    )
    targets = list(range(30))
    c.require(
        m["membrane_targets"] == ({"Base": targets} if enabled else {})
        and m["cell_targets"] == ({"Base": list(range(7))} if enabled else {}),
        "Resolved target map differs",
    )
    zero = row["variant"] == "zero_amplitude"
    scheduled = {key: 0 for key in ("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ")}
    if zero:
        for ion in ("Na", "K", "Cl"):
            scheduled[ion + "_mem"] = [*mapped["mapped_pulse_times_s"], 0.0, ["Base"], "None"]
    c.require(m["scheduled_options"] == scheduled, "Scheduled event input differs")
    c.require(
        m["event_targets"] == ({ion: targets for ion in ("Na", "K", "Cl")} if zero else {}),
        "Event targets differ",
    )
    c.require(
        m["global_options"]
        == dict.fromkeys(("K_env", "Cl_env", "Na_env", "gj_block", "T_change", "NaKATP_block"), 0)
        and m["cut_event_configured"] is True
        and m["cut_event_enabled"] is False
        and m["voltage_event_configured"] is False
        and m["voltage_event_enabled"] is False,
        "Unexpected global/cutting/voltage event",
    )
    c.require(
        m["paths"]
        == {
            "seed": "INITS/world_1.betse.gz",
            "init": "INITS/init_1.betse.gz",
            "sim": "SIMS/sim_1.betse.gz",
        }
        and m["pickles_present"] == {"seed": True, "init": False, "sim": False},
        "Unexpected native output path/pickle",
    )


def check_row(row, packet, prior, retained, plan):
    ctx.validate_plan(plan)
    c.require(set(packet) == set(STAGES), "Incomplete preparation stages")
    _, mapped = ctx.mapping(row)
    ready, m = packet["ready"], packet["metadata"]
    c.require(ready["row"] == row and ready["mapping"] == mapped, "Preparation identity differs")
    for stage in ("core", "dynamics"):
        check_arrays(packet[stage]["arrays"], legacy.CORE_ARRAYS)
        c.require(packet[stage]["geometry"] == prior["geometry"], "Prepared geometry differs")
    c.require(packet["core"] == packet["dynamics"], "Dynamics changed core preparation or topology")
    check_metadata(row, m, prior, mapped)
    c.require(
        ready["preparation_calls"] == PREPARATION_CALLS and ready["hook_restored"] is True,
        "Preparation call coverage/hook differs",
    )
    state = ready["state"]
    check_state(state)
    c.require(
        {k: state["arrays"][k] for k in legacy.CORE_ARRAYS} == packet["dynamics"]["arrays"],
        "Core state changed during closure",
    )
    a = state["arrays"]
    links = {
        "inside_mM": "cc_cells",
        "outside_mM": "cc_env",
        "voltage_V": "vm",
        "rho_C_per_m3": "rho_cells",
        "inward_current_A": "I_mem",
        "boundary_voltage_V": "Phi_b",
    }
    c.require(
        ready["initial"]
        == retained["trace"]["initial"]
        == {key: a[name]["values"] for key, name in links.items()},
        "SIM initial state differs from retained INIT",
    )
    c.require(
        a["Dm_cells"] == retained["final"]["Dm_cells"],
        "Native diffusion bytes differ from accepted baseline",
    )
    owners = prior["geometry"]["membrane_owners"]
    c.require(
        a["cc_at_mem"]["values"]
        == [[values[i] for i in owners] for values in a["cc_cells"]["values"]],
        "Membrane concentration ownership differs",
    )
    for index, ion in enumerate(m["species"]):
        c.require(
            all(
                v == m["configured_default"]["diffusion_m2_per_s"][ion]
                for v in a["Dm_cells"]["values"][index]
            ),
            "Configured/actual diffusion differs",
        )
    junctions = packet["core"]["junctions"]
    c.require(
        junctions["weights"]["shape"] == [30] and unpack(junctions["weights"]) == [1.0] * 30,
        "Junction weight differs",
    )
    neighbours = junctions["membrane_neighbours"]
    c.require(
        len(neighbours) == 30 and all(type(i) is int and 0 <= i < 30 for i in neighbours),
        "Invalid membrane-neighbour map",
    )
    c.require(
        len(junctions["cell_neighbours"]) == 7
        and all(
            type(i) is int and 0 <= i < 7
            for indices in junctions["cell_neighbours"]
            for i in indices
        ),
        "Invalid cell-neighbour map",
    )
    probe = packet["dispatch"]
    labels = [mapped["raw_clock_scale"] * t for t in plan["dispatch_elapsed_times_s"]]
    c.require(
        probe["mode"] == "preparation_dispatch_only"
        and probe["initial"] is None
        and probe["integration_calls"] == 0
        and probe["hook_restored"] is True
        and len(probe["events"]) == len(labels),
        "Event dispatch coverage differs",
    )
    for index, event in enumerate(probe["events"]):
        check_state(event["before"])
        check_state(event["after"])
        c.require(
            event["index"] == index
            and event["raw_label_s"] == labels[index]
            and event["flux_ion_indices"] == []
            and event["before"] == event["after"] == state,
            "No-op event changed state/control bytes or clock",
        )
    check_state(packet["final"]["state"])
    c.require(
        packet["final"] == {"state": state, "metadata": m, "junctions": junctions},
        "Event dispatch changed final setup",
    )
    return {
        "status": "preparation_checks_pass",
        "event_dispatches": len(labels),
        "integration_calls": 0,
    }


def check_controls(packets, plan):
    """Physical setup equality across separate freshly seeded preparations."""
    expected = {(row["case"]["id"], row["variant"]) for row in ctx.rows(plan)}
    c.require(set(packets) == expected, "Incomplete preparation matrix")
    for case in plan["case_ids"]:
        baseline = packets[case, "baseline"]
        for variant in ("default_profile", "zero_amplitude"):
            other = packets[case, variant]
            for stage in ("core", "dynamics"):
                c.require(other[stage] == baseline[stage], "Profile changes physical core/topology")
            for name in ("state", "initial"):
                c.require(
                    other["ready"][name] == baseline["ready"][name],
                    "Profile changes starting state",
                )
            c.require(
                other["dispatch"] == baseline["dispatch"], "No-op/profile dispatch changes state"
            )
    return {
        "status": "exact_preparation_controls_pass",
        "comparisons": 4,
        "trajectory_qualified": False,
    }
