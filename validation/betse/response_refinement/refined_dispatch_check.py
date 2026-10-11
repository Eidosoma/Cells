"""Variable-length, control-only gates; retain D080 physics and tolerance unchanged."""

import copy
import importlib

import refined_dispatch_context as ctx

c = ctx.c
legacy = importlib.import_module("dispatch_preflight_check")
base, snapshot = legacy.base, legacy.snapshot


def expected_metadata(row, prior, mapped):
    """Inherit the frozen physical/target contract, amend only clock-dependent fields."""
    coarse = ctx.coarse_row(row["condition"])
    original_map = ctx.legacy.mapping(coarse)[1]
    result = copy.deepcopy(legacy.expected_metadata(coarse, prior, original_map))
    result |= {"dt_s": row["dt_s"], "sampling_s": row["dt_s"], "configured_steps": mapped["steps"]}
    if mapped["events_enabled"]:
        for ion in ("Na", "K", "Cl"):
            result["scheduled_options"][ion + "_mem"][:3] = mapped["mapped_pulse_times_s"]
            result["event_effectors"][ion] |= {
                "dynamic_values": [1.0] * mapped["steps"],
                "pulse_times_s": mapped["mapped_pulse_times_s"],
            }
    return result


def check_prepared(row, packet, prior, retained, plan, preparation):
    ctx.validate_plan(plan)
    c.require(row in ctx.rows(plan), "Preparation is outside finer dispatch panel")
    mapped = ctx.mapping(row)[1]
    ready, state = packet["ready"], packet["ready"]["state"]
    c.require(ready["row"] == row and ready["mapping"] == mapped, "Preparation identity differs")
    c.require(
        ready["preparation_calls"] == base.PREPARATION_CALLS and ready["hook_restored"] is True,
        "Preparation call coverage differs",
    )
    base.check_state(state)
    c.require(
        packet["core"] == packet["dynamics"] == preparation["core"],
        "Physical preparation or topology differs",
    )
    c.require(
        all(state["arrays"][n] == packet["core"]["arrays"][n] for n in snapshot.CORE_ARRAYS),
        "Prepared core state changed",
    )
    c.require(state == preparation["ready"]["state"], "Fresh initial physical state differs")
    c.require(
        ready["initial"] == retained["trace"]["initial"] == preparation["ready"]["initial"],
        "Initial state differs from retained INIT",
    )
    expected = expected_metadata(row, prior, mapped)
    c.require(packet["metadata"] == expected, "Native metadata/targets/effectors differ")
    for s, ion in enumerate(expected["species"]):
        default = expected["configured_default"]["diffusion_m2_per_s"][ion]
        c.require(
            all(v == default for v in state["arrays"]["Dm_base"]["values"][s]),
            "Tissue default and baseline differ",
        )
    return mapped, expected


def check_dispatch(row, probe, ready, prior, mapped, plan):
    count = mapped["steps"]
    c.require(
        set(probe) == {"mode", "initial", "hook_restored", "integration_calls", "events"}
        and probe["mode"] == "preparation_dispatch_only"
        and probe["initial"] is None
        and probe["hook_restored"] is True
        and type(probe["integration_calls"]) is int
        and probe["integration_calls"] == 0
        and len(probe["events"]) == count,
        "Dispatch coverage or scope differs",
    )
    schedule = ctx.held.held_schedule(c.read(ctx.held.PLAN), row["condition"], row["dt_s"])
    c.require(len(schedule) == count, "Prescribed input coverage differs")
    initial_fixed, previous, maximum = legacy.fixed_state(ready), ready, 0.0
    for k, event in enumerate(probe["events"]):
        c.require(
            set(event) == {"index", "raw_label_s", "before", "after", "flux_ion_indices"}
            and type(event["index"]) is int
            and event["index"] == k
            and event["raw_label_s"] == mapped["raw_labels_s"][k]
            and event["flux_ion_indices"] == []
            and event["before"] == previous,
            "Dispatch identity/clock/state chain differs",
        )
        after = event["after"]
        c.require(
            legacy.fixed_state(after) == initial_fixed,
            "Dispatch changed physical state or disabled controls",
        )
        a, availability = after["arrays"], schedule[k]["multipliers"]["Na"]
        for s, perm in enumerate(prior["base_protocol"]["permeability_m_per_s"]):
            scale = perm * prior["base_protocol"]["thickness_m"]
            for j in range(30):
                effective = a["Dm_cells"]["values"][s][j]
                scheduled = a["Dm_scheduled"]["values"][s][j]
                baseline = a["Dm_base"]["values"][s][j]
                c.require(effective == scheduled + baseline, "Native diffusion composition differs")
                if scale == 0 or row["condition"] == "static_blocked":
                    c.require(effective == scheduled == 0, "Blocked/immobile diffusion changed")
                    continue
                error = (
                    max(
                        abs(effective - availability * scale),
                        abs(scheduled - (availability - 1) * scale),
                    )
                    / scale
                )
                maximum = max(maximum, error)
                c.require(
                    error <= plan["control_atol"], "Declared/actual effective diffusion differs"
                )
                c.require(
                    0 <= effective <= baseline, "Effective diffusion outside suppression domain"
                )
                if row["condition"] == "suppression_recovery":
                    c.require(effective > 0 and scheduled < 0, "Smooth pulse became a square block")
                else:
                    c.require(
                        scheduled == 0 and a["Dm_cells"] == ready["arrays"]["Dm_cells"],
                        "No-op control changed diffusion",
                    )
        previous = after
    return {
        "event_dispatch_calls": count,
        "control_values_checked": count * 6 * 30 * 2,
        "maximum_baseline_scaled_control_error": maximum,
    }


def check_row(row, packet, prior, retained, plan, preparation):
    c.require(set(packet) == set(legacy.STAGES), "Incomplete preparation stages")
    mapped, expected = check_prepared(row, packet, prior, retained, plan, preparation)
    result = check_dispatch(row, packet["dispatch"], packet["ready"]["state"], prior, mapped, plan)
    c.require(
        packet["final"]
        == {
            "state": packet["dispatch"]["events"][-1]["after"],
            "metadata": expected,
            "junctions": packet["core"]["junctions"],
        },
        "Final state/metadata/topology differs",
    )
    return {
        "status": "refined_dispatch_checks_pass",
        "integration_calls": 0,
        "trajectory_qualified": False,
        **result,
    }
