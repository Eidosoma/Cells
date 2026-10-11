"""Control-aware preparation gates, independent of BETSE pulse evaluation or stepping."""

import contact as c
import dispatch_preflight_context as ctx
import held_intervention as held
import phase_bridge as snapshot
import profile_bridge_check as base

STAGES = ("core", "dynamics", "ready", "metadata", "dispatch", "final")
VARIABLE_ARRAYS = {"Dm_cells", "Dm_scheduled"}


def expected_metadata(row, prior, mapped):
    protocol, _ = ctx.mapping(row)
    overrides = {tuple(path): value for path, value in protocol["yaml_overrides"]}
    species = prior["base_protocol"]["expected_species"]
    default = {
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
            for ion in species
        },
    }
    targets = list(range(30))
    scheduled = dict.fromkeys(("Na_mem", "K_mem", "Cl_mem", "Ca_mem", "pressure", "ecmJ"), 0)
    effectors = {}
    if mapped["events_enabled"]:
        for ion in ("Na", "K", "Cl"):
            scheduled[ion + "_mem"] = [
                *mapped["mapped_pulse_times_s"],
                mapped["multiplier"],
                ["Base"],
                "None",
            ]
            effectors[ion] = {
                "scalar": 1.0,
                "dynamic_values": [1.0] * 40,
                "function": "None",
                "multiplier": mapped["multiplier"],
                "pulse_times_s": mapped["mapped_pulse_times_s"],
            }
    return {
        "phase": "SIM",
        "run_sim_flag": True,
        "profiles_enabled": True,
        "dt_s": row["dt_s"],
        "duration_s": mapped["duration_s"],
        "sampling_s": row["dt_s"],
        "sample_stride": 1,
        "configured_steps": mapped["steps"],
        "constants": prior["base_protocol"]["profiles"][row["profile"]],
        "geometry": prior["geometry"],
        "settings": prior["settings"],
        "thickness_m": prior["base_protocol"]["thickness_m"],
        "species": species,
        "moving_ion_indices": list(range(6)),
        "configured_default": default,
        "resolved_default": default,
        "profile_names": ["Base"],
        "additional_profile_count": 0,
        "cut_profile_count": 0,
        "membrane_targets": {"Base": targets},
        "cell_targets": {"Base": list(range(7))},
        "scheduled_options": scheduled,
        "global_options": dict.fromkeys(
            ("K_env", "Cl_env", "Na_env", "gj_block", "T_change", "NaKATP_block"), 0
        ),
        "cut_event_configured": True,
        "cut_event_enabled": False,
        "voltage_event_configured": False,
        "voltage_event_enabled": False,
        "event_targets": {ion: targets for ion in ("Na", "K", "Cl")}
        if mapped["events_enabled"]
        else {},
        "event_effectors": effectors,
        "paths": {
            "seed": "INITS/world_1.betse.gz",
            "init": "INITS/init_1.betse.gz",
            "sim": "SIMS/sim_1.betse.gz",
        },
        "pickles_present": {"seed": True, "init": False, "sim": False},
    }


def fixed_state(state):
    c.require(
        set(state) == {"arrays", "temperature_K", "rho_channel", "rho_pump"}, "State fields differ"
    )
    base.check_arrays(state["arrays"], snapshot.EVENT_ARRAYS)
    return state | {
        "arrays": {k: v for k, v in state["arrays"].items() if k not in VARIABLE_ARRAYS}
    }


def check_dispatch(row, probe, ready, prior, mapped, plan):
    c.require(
        set(probe) == {"mode", "initial", "hook_restored", "integration_calls", "events"}
        and probe["mode"] == "preparation_dispatch_only"
        and probe["initial"] is None
        and probe["hook_restored"] is True
        and probe["integration_calls"] == 0
        and len(probe["events"]) == 40,
        "Dispatch coverage or scope differs",
    )
    initial_fixed = fixed_state(ready)
    schedule = held.held_schedule(c.read(held.PLAN), row["condition"], row["dt_s"])
    previous, maximum = ready, 0.0
    for k, event in enumerate(probe["events"]):
        c.require(
            set(event) == {"index", "raw_label_s", "before", "after", "flux_ion_indices"}
            and event["index"] == k
            and event["raw_label_s"] == mapped["raw_labels_s"][k]
            and event["flux_ion_indices"] == []
            and event["before"] == previous,
            "Dispatch identity/clock/state chain differs",
        )
        after = event["after"]
        c.require(
            fixed_state(after) == initial_fixed,
            "Dispatch changed physical state or disabled controls",
        )
        a = after["arrays"]
        availability = schedule[k]["multipliers"]["Na"]
        for s, perm in enumerate(prior["base_protocol"]["permeability_m_per_s"]):
            scale = perm * prior["base_protocol"]["thickness_m"]
            for j in range(30):
                effective = a["Dm_cells"]["values"][s][j]
                scheduled = a["Dm_scheduled"]["values"][s][j]
                baseline = a["Dm_base"]["values"][s][j]
                c.require(effective == scheduled + baseline, "Native diffusion composition differs")
                if scale == 0 or row["condition"] == "static_blocked":
                    c.require(
                        effective == scheduled == 0, "Blocked/immobile diffusion is not exact zero"
                    )
                    continue
                expected = availability * scale
                expected_scheduled = (availability - 1) * scale
                error = max(abs(effective - expected), abs(scheduled - expected_scheduled)) / scale
                maximum = max(maximum, error)
                c.require(
                    error <= plan["control_atol"], "Declared/actual effective diffusion differs"
                )
                c.require(
                    0 <= effective <= baseline, "Effective diffusion outside suppression domain"
                )
                if row["condition"] != "suppression_recovery":
                    c.require(
                        scheduled == 0 and a["Dm_cells"] == ready["arrays"]["Dm_cells"],
                        "No-op control changed diffusion",
                    )
                else:
                    c.require(
                        effective > 0 and scheduled < 0, "Smooth pulse is not an exact square block"
                    )
        previous = after
    return {
        "event_dispatch_calls": 40,
        "maximum_baseline_scaled_control_error": maximum,
        "control_values_checked": 40 * 6 * 30 * 2,
    }


def check_prepared(row, packet, prior, retained, plan, retained_preparation):
    ctx.validate_plan(plan)
    _, mapped = ctx.mapping(row)
    ready, state = packet["ready"], packet["ready"]["state"]
    c.require(ready["row"] == row and ready["mapping"] == mapped, "Preparation identity differs")
    c.require(
        ready["preparation_calls"] == base.PREPARATION_CALLS and ready["hook_restored"] is True,
        "Preparation call coverage differs",
    )
    base.check_state(state)
    c.require(
        packet["core"] == packet["dynamics"] == retained_preparation["core"],
        "Physical preparation or topology differs",
    )
    for name in snapshot.CORE_ARRAYS:
        c.require(
            state["arrays"][name] == packet["core"]["arrays"][name], "Prepared core state changed"
        )
    c.require(
        state == retained_preparation["ready"]["state"],
        "Fresh prepared state differs from qualified no-event preparation",
    )
    c.require(
        ready["initial"]
        == retained["trace"]["initial"]
        == retained_preparation["ready"]["initial"],
        "Initial state differs from retained INIT",
    )
    expected = expected_metadata(row, prior, mapped)
    c.require(packet["metadata"] == expected, "Native metadata/targets/effectors differ")
    for s, ion in enumerate(expected["species"]):
        expected_dm = expected["configured_default"]["diffusion_m2_per_s"][ion]
        c.require(
            all(v == expected_dm for v in state["arrays"]["Dm_base"]["values"][s]),
            "Tissue default and actual baseline differ",
        )
    return mapped, expected


def check_row(row, packet, prior, retained, plan, retained_preparation):
    c.require(set(packet) == set(STAGES), "Incomplete preparation stages")
    mapped, expected = check_prepared(row, packet, prior, retained, plan, retained_preparation)
    result = check_dispatch(row, packet["dispatch"], packet["ready"]["state"], prior, mapped, plan)
    c.require(
        packet["final"]
        == {
            "state": packet["dispatch"]["events"][-1]["after"],
            "metadata": expected,
            "junctions": packet["core"]["junctions"],
        },
        "Final preparation state/metadata/topology differs",
    )
    return {
        "status": "nonzero_dispatch_checks_pass",
        "integration_calls": 0,
        "trajectory_qualified": False,
        **result,
    }


def check_controls(packets, plan):
    c.require(set(packets) == set(plan["conditions"]), "Incomplete control panel")
    baseline, zero, pulse = (
        packets[k] for k in ("baseline", "zero_amplitude", "suppression_recovery")
    )
    c.require(
        baseline["dispatch"] == zero["dispatch"], "Enabled zero-amplitude differs from no event"
    )
    for stage in ("core", "dynamics"):
        c.require(baseline[stage] == zero[stage] == pulse[stage], "Control preparation differs")
    c.require(
        baseline["ready"]["state"] == zero["ready"]["state"] == pulse["ready"]["state"],
        "Pulse changes initial physical state",
    )
    return {
        "status": "exact_preparation_controls_pass",
        "baseline_zero_dispatch_equal": True,
        "fresh_normal_preparations_equal": True,
    }
