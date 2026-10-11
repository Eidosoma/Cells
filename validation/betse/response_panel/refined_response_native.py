"""Fresh native SIM response capture and control-aware lifecycle/linkage gates."""

import importlib
import json
import os
import resource
import sys
import traceback
import warnings
from datetime import UTC, datetime
from pathlib import Path

import refined_response_context as ctx

c, held = ctx.c, ctx.held
preparation = importlib.import_module("refined_dispatch_native")
dispatch = importlib.import_module("refined_dispatch_check")
typed = importlib.import_module("full_loop_audit")
capture = importlib.import_module("full_loop_bridge")
links = importlib.import_module("full_loop_bridge_check")
snapshot = importlib.import_module("phase_bridge")
base = importlib.import_module("profile_bridge")
exporter = importlib.import_module("trajectory")
old = importlib.import_module("trajectory_context")
evidence = importlib.import_module("trajectory_evidence")
observer_types = importlib.import_module("full_loop_observer")
PRE_LOOP_CALLS, FullLoopObserver = observer_types.PRE_LOOP_CALLS, observer_types.FullLoopObserver
arrays = importlib.import_module("trajectory_check")
numbers, unpack = arrays.numbers, arrays.unpack

VARIABLE = {"Dm_cells", "Dm_scheduled"}


def state_values(state, initial, owners):
    c.require(
        set(state) == set(initial) and set(state["arrays"]) == set(initial["arrays"]),
        "State coverage differs",
    )
    c.require(
        all(state[k] == initial[k] for k in initial if k != "arrays"), "State scaling changed"
    )
    values = {}
    for name, baseline in initial["arrays"].items():
        record = state["arrays"][name]
        if "scalar" in baseline:
            c.require(record == baseline and type(record["scalar"]) is int, "Scalar block differs")
            continue
        c.require(record["dtype"] == baseline["dtype"], "Native state precision changed")
        values[name] = typed.typed_values(record, baseline["shape"])
    c.require(
        all(state["arrays"][k] == initial["arrays"][k] for k in links.FIXED - VARIABLE),
        "Fixed control changed",
    )
    c.require(
        values["cc_at_mem"] == [[v[i] for i in owners] for v in values["cc_cells"]],
        "Membrane owner correspondence differs",
    )
    c.require(all(v == 0 for v in numbers(values["fluxes_gj"])), "Disabled junction transported")
    return values


def control(row, state, initial, availability, prior, atol):
    """Compare effective and scheduled diffusion against an independent held input."""
    arrays = state["arrays"]
    maximum = 0.0
    for s, perm in enumerate(prior["base_protocol"]["permeability_m_per_s"]):
        scale = perm * prior["base_protocol"]["thickness_m"]
        for j in range(30):
            effective, scheduled, baseline = (
                arrays[k]["values"][s][j] for k in ("Dm_cells", "Dm_scheduled", "Dm_base")
            )
            c.require(effective == scheduled + baseline, "Diffusion composition differs")
            if scale == 0 or row["condition"] == "static_blocked":
                c.require(effective == scheduled == 0, "Disabled diffusion is nonzero")
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
                error <= atol and 0 <= effective <= baseline, "Held effective diffusion differs"
            )
            if row["condition"] == "suppression_recovery":
                c.require(
                    effective > 0 and scheduled < 0, "Pulse was replaced by an exact square block"
                )
            else:
                c.require(
                    scheduled == 0 and arrays["Dm_cells"] == initial["arrays"]["Dm_cells"],
                    "No-op changed diffusion",
                )
    return maximum


def without(state, omitted):
    return state | {"arrays": {k: v for k, v in state["arrays"].items() if k not in omitted}}


def check_row(row, mode, packet, prior, plan, prepared, retained=None):
    c.require(
        row in ctx.native_rows(plan) and mode in plan["native_modes"], "Unregistered native row"
    )
    stages = {"core", "result"} | (
        {"dynamics", "entry", "metadata", "events"} if mode == "observed" else set()
    )
    c.require(set(packet) == stages, "Incomplete native capture")
    result = packet["result"]
    c.require(
        result["schema"] == "cells.betse_refined_response_native_row@1"
        and result["status"] == "exported_not_qualified"
        and result["row"] == row
        and result["mode"] == mode
        and result["hook_restored"] is True,
        "Native identity/status differs",
    )
    _, mapped = ctx.prior.mapping(row)
    count = mapped["steps"]
    expected = dispatch.expected_metadata(row, prior, mapped)
    c.require(
        prepared["metadata"] == expected and packet["core"] == prepared["core"],
        "Fresh native preparation differs from D083",
    )
    c.require(
        result["final_metadata"]
        == expected | {"pickles_present": {"seed": True, "init": False, "sim": True}},
        "Final native metadata/serialization differs",
    )
    c.require(result["final_junctions"] == packet["core"]["junctions"], "Topology changed")
    initial = prepared["ready"]["state"]
    owners = prior["geometry"]["membrane_owners"]
    final = state_values(result["final_state"], initial, owners)
    numerical = result["numerical"]
    c.require(
        set(numerical["ordinary"]) == set(old.ORDINARY_NAMES)
        and set(numerical["final"]) == set(old.FINAL_NAMES),
        "Numerical export coverage differs",
    )
    for group in ("ordinary", "final"):
        for array in numerical[group].values():
            unpack(array)
    c.require(
        {k: result["final_state"]["arrays"][k] for k in old.FINAL_NAMES} == numerical["final"],
        "Final copies disagree",
    )
    c.require(
        numerical["native_pickle_present"] is True and numerical["mode"] == mode,
        "Native serialization/mode differs",
    )
    c.require(
        numerical["permeability_m_per_s"]
        == [[v / prior["base_protocol"]["thickness_m"] for v in a] for a in final["Dm_cells"]],
        "Final permeability export differs",
    )
    if row["condition"] != "suppression_recovery":
        c.require(
            retained is not None
            and links.numerical_payload(numerical)
            == links.numerical_payload(retained["numerical"]),
            "No-op overlap differs from qualified expanded capture",
        )
    schedule = held.held_schedule(c.read(held.PLAN), row["condition"], row["dt_s"])
    maximum = control(
        row,
        result["final_state"],
        initial,
        schedule[-1]["multipliers"]["Na"],
        prior,
        plan["control_atol"],
    )
    if mode == "unobserved":
        c.require(
            result["lifecycle"] is numerical["trace"] is None,
            "Observer-off partner contains a trace",
        )
        return {
            "status": "capture_row_checks_pass",
            "observed_steps": 0,
            "maximum_baseline_scaled_control_error": maximum,
        }
    entry, events, trace = packet["entry"], packet["events"], numerical["trace"]
    c.require(
        packet["dynamics"] == packet["core"]
        and packet["metadata"] == expected
        and entry["state"] == initial
        and entry["initial"] == trace["initial"] == links.state_snapshot(initial)
        and entry["pre_loop_calls"] == PRE_LOOP_CALLS
        and entry["labels_s"] == trace["labels_s"] == mapped["raw_labels_s"]
        and entry["sampled_indices"] == trace["sampled_indices"] == list(range(1, count)),
        "Native setup/entry clock differs",
    )
    c.require(
        result["lifecycle"] == {"calls": PRE_LOOP_CALLS, "run_returns": 1, "hook_restored": True},
        "Native lifecycle incomplete",
    )
    c.require(
        set(events) == {"mode", "initial", "integration_calls", "hook_restored", "events"}
        and events["mode"] == "full_sim_loop"
        and events["initial"] == initial
        and events["integration_calls"] == 1
        and events["hook_restored"] is True
        and len(events["events"]) == len(trace["steps"]) == count,
        "Full-loop event coverage differs",
    )
    c.require(
        trace["loop_calls"] == trace["loop_returns"] == 1
        and trace["concentration_updates"] == count
        and trace["hook_restored"] is True
        and trace["storage"]
        == [{"index": k, "raw_label_s": mapped["raw_labels_s"][k]} for k in range(1, count)],
        "Native observer/storage incomplete",
    )
    previous, previous_control = trace["initial"], initial
    nonce = typed.voltage_nonce()
    for k, (event, step) in enumerate(zip(events["events"], trace["steps"], strict=True)):
        c.require(
            set(event)
            == {"index", "raw_label_s", "before", "after", "before_update", "flux_ion_indices"}
            and event["index"] == step["index"] == k
            and event["raw_label_s"] == step["raw_label_s"] == mapped["raw_labels_s"][k]
            and event["flux_ion_indices"] == list(range(6))
            and step["before_elapsed_s"] == k * row["dt_s"]
            and step["after_elapsed_s"] == (k + 1) * row["dt_s"],
            "Event/flux/update order or clock differs",
        )
        values = {
            boundary: state_values(event[boundary], initial, owners)
            for boundary in ("before", "after", "before_update")
        }
        c.require(
            without(event["before"], VARIABLE) == without(event["after"], VARIABLE),
            "Dispatch changed physical state or fixed controls",
        )
        c.require(
            all(event["before"]["arrays"][n] == previous_control["arrays"][n] for n in VARIABLE),
            "Pre-dispatch control chain differs",
        )
        maximum = max(
            maximum,
            control(
                row,
                event["after"],
                initial,
                schedule[k]["multipliers"]["Na"],
                prior,
                plan["control_atol"],
            ),
        )
        c.require(
            links.state_snapshot(event["before"]) == previous
            and all(v == 0 for v in numbers(values["before"]["fluxes_mem"])),
            "Pre-event state/reset differs",
        )
        c.require(
            without(event["after"], {"vm", "fluxes_mem"})
            == without(event["before_update"], {"vm", "fluxes_mem"}),
            "Flux evaluation changed unrelated state/control",
        )
        voltage = list(values["after"]["vm"])
        for _ in range(6):
            voltage = [v + nonce for v in voltage]
        c.require(values["before_update"]["vm"] == voltage, "Native in-place voltage nonce differs")
        c.require(
            links.state_snapshot(event["before_update"]) == step["before"]
            and values["before_update"]["fluxes_mem"] == step["density_mol_per_m2_s"]
            and values["before_update"]["fluxes_gj"] == step["junction_density_mol_per_m2_s"],
            "Post-flux export differs from native step",
        )
        previous, previous_control = step["after"], event["after"]
    c.require(
        links.state_snapshot(result["final_state"]) == previous
        and final["fluxes_mem"] == trace["steps"][-1]["density_mol_per_m2_s"],
        "Final state/flux linkage differs",
    )
    return {
        "status": "capture_row_checks_pass",
        "observed_steps": count,
        "maximum_baseline_scaled_control_error": maximum,
    }


def check_zero(packets):
    baseline, zero = (packets[k] for k in ("baseline", "zero_amplitude"))
    for name in ("core", "dynamics", "entry", "events"):
        c.require(baseline[name] == zero[name], "Zero-amplitude changes native " + name)
    a, b = baseline["result"], zero["result"]
    c.require(
        links.numerical_payload(a["numerical"]) == links.numerical_payload(b["numerical"])
        and a["final_state"] == b["final_state"],
        "Zero-amplitude changes native response",
    )
    return {"status": "baseline_zero_response_exact"}


def run_row(row, mode, directory, prior, package):
    c.require(
        mode in ("observed", "unobserved") and sys.getprofile() is None,
        "Unexpected observation context",
    )
    directory.mkdir(parents=True, exist_ok=False)
    c.write(
        directory / "started.json",
        {"row": row, "mode": mode, "started_utc": datetime.now(UTC).isoformat()},
    )
    observer = None
    try:
        phase, mapped = preparation.fresh_phase(row, directory, prior)
        c.write(directory / "core.json", base.core_snapshot(phase))
        if mode == "observed":
            observer = FullLoopObserver(
                phase,
                package / "science",
                exporter.native_snapshot,
                exporter.native_fluxes,
                snapshot.event_snapshot,
                directory,
                base.core_snapshot,
                lambda: preparation.legacy.metadata(phase, directory, mapped, prior),
            )
            with observer:
                phase.sim.run_sim_core(phase)
            c.write(directory / "events.json", observer.event_result())
        else:
            phase.sim.run_sim_core(phase)
        final_state = snapshot.event_snapshot(phase.sim)
        final_metadata = preparation.legacy.metadata(phase, directory, mapped, prior)
        c.write(directory / "final-state.json", final_state)
        c.write(directory / "final-metadata.json", final_metadata)
        c.write(
            directory / "result.json",
            {
                "schema": "cells.betse_refined_response_native_row@1",
                "status": "exported_not_qualified",
                "row": row,
                "mode": mode,
                "numerical": capture.numerical_record(phase, row, mode, directory, prior, observer),
                "final_state": final_state,
                "final_metadata": final_metadata,
                "final_junctions": base.junctions(phase),
                "lifecycle": observer.lifecycle_result() if observer else None,
                "hook_restored": sys.getprofile() is None,
            },
        )
    except BaseException:
        c.write(
            directory / "failure.json",
            {
                "status": "failed_not_qualified",
                "row": row,
                "mode": mode,
                "traceback": traceback.format_exc(),
                "hook_restored": sys.getprofile() is None,
            },
        )
        if observer is not None:
            try:
                c.write(directory / "partial-observer.json", observer.partial())
            except Exception:
                c.write(
                    directory / "partial-export-failure.json", {"traceback": traceback.format_exc()}
                )
        raise


def worker(registered, output):
    import betse
    import numpy as np

    ctx.validate_registration(registered)
    plan, prior = registered["plan"], evidence.trusted_registration()
    c.require(sorted(os.sched_getaffinity(0)) == [0, 1, 2, 3], "Worker CPU affinity differs")
    resource.setrlimit(resource.RLIMIT_FSIZE, (plan["max_worker_file_bytes"],) * 2)
    package = Path(betse.__file__).resolve().parent
    installed = {"betse/" + str(p.relative_to(package)): c.sha(p) for p in package.rglob("*.py")}
    c.require(
        installed
        == {
            n: h
            for n, h in prior["upstream"]["files_sha256"].items()
            if n.startswith("betse/") and n.endswith(".py")
        }
        and package.is_relative_to(c.REFERENCE_PYTHON.parent.parent),
        "Installed BETSE differs from pinned source",
    )
    results, pairs, packets = [], [], {}
    with (
        warnings.catch_warnings(record=True) as caught,
        np.errstate(over="raise", invalid="raise", divide="raise"),
    ):
        warnings.simplefilter("error", RuntimeWarning)
        for row in registered["native_rows"]:
            pair = {}
            for mode in plan["native_modes"]:
                directory = output / "native" / ctx.prior.key(row) / mode
                run_row(row, mode, directory, prior, package)
                capture.check_budget(output, plan)
                packet = links.read_packet(directory, mode)
                retained = (
                    c.read(ctx.overlap_path(row, mode))
                    if row["condition"] != "suppression_recovery"
                    else None
                )
                checked = check_row(row, mode, packet, prior, plan, ctx.prepared(row), retained)
                c.write(directory / "checks.json", checked)
                pair[mode] = packet
                results.append(
                    {
                        "row": row,
                        "mode": mode,
                        "path": str((directory / "result.json").relative_to(output)),
                        "sha256": c.sha(directory / "result.json"),
                        **checked,
                    }
                )
                print(
                    json.dumps({"native_run_completed": ctx.prior.key(row), "mode": mode}),
                    flush=True,
                )
            pairs.append({"row_id": ctx.prior.key(row), **links.check_pair(pair)})
            packets.setdefault(f"{row['dt_s']:.8f}", {})[row["condition"]] = pair["observed"]
        zero = {key: check_zero(panel) for key, panel in packets.items()}
        c.require(not caught, "Native response emitted Python warnings")
    c.require(
        len(results) == plan["native_runs"]
        and sum(r["observed_steps"] for r in results) == plan["observed_native_steps"],
        "Incomplete native response panel",
    )
    c.require(
        not any(n == "cells" or n.startswith("cells.") for n in sys.modules),
        "Native worker imported Cells",
    )
    return {
        "schema": "cells.betse_refined_response_native_worker@1",
        "status": "capture_controls_pass_pending_comparison",
        "engine": "actual_betse_full_sim_loop",
        "results": results,
        "pairs": pairs,
        "zero_control": zero,
        "installed_python_sha256": installed,
        "package_path": str(package),
        "environment": c.environment(),
        "warnings": [],
        "trajectory_run": True,
    }
