"""D099 full Cells history validation: explicit fixture, original units and guards."""

import math

from feedback_compare import (
    c,
    cells_tolerances,
    compare_histories,
    ctx,
    io,
    ready,
    ref,
    refcheck,
    unpack_arrays,
    zero,
)


def cells_points_and_checks(r, record, ledger):
    key = record["id"]
    definition = r["cells_definitions"][key]
    c.require(record["definition"] == definition, "Cells data definition differs")
    c.require(
        record["runtime"] == r["preparation_registration"]["cells_runtime"],
        "Cells trajectory runtime differs",
    )
    times, history, observations = unpack_arrays(record)
    dt, duration = definition["execution"]["dt"], definition["experiment"]["end_time"]
    count = round(duration / dt)
    c.require(
        record["start_step"] == 0
        and record["final_step_index"] == count
        and times == [i * dt for i in range(count)] + [duration],
        "Cells accepted grid differs",
    )
    c.require(set(history) == set(ready.STATE_SHAPES), "Cells full-state coverage differs")
    variant = key.split("/")[0]
    p, enabled = (
        r["reference_parameters"][variant],
        variant in ("blocked_channel", "active_channel"),
    )
    expected = ready.expected_initial(enabled)
    if enabled:
        expected["gate"] = [[gate] * 7 + [0.0] * 3 for gate in r["protocol"]["initial_gate"]]
    for name, shape in ready.STATE_SHAPES.items():
        c.require(
            record["history"][name]["shape"] == [len(times), *shape]
            and history[name][0] == expected[name],
            "Cells initial/full-state shape differs",
        )
    for j in range(len(times)):
        state = {name: values[j] for name, values in history.items()}
        for name in (
            "leak_transferred",
            "pump_cycles",
            "junction_gate",
            "junction_transferred",
            "junction_dissipated_energy_pJ",
        ):
            zero(state[name])
        zero(
            [
                state["amount_increment"][0],
                state["amount_increment"][2],
                state["extracellular_amount_increment"][0],
                state["extracellular_amount_increment"][2],
            ]
        )
        zero([v[7:] for v in state["amount_increment"]])
        zero([v[1:] for v in state["extracellular_amount_increment"]])
        zero([v[7:] for v in state["gate"]])
        zero(state["channel_transferred"][7:])
        zero(state["dissipated_energy_pJ"][7:])
        q, m, h, energy = (
            state["amount_increment"][1][:7],
            state["gate"][0][:7],
            state["gate"][1][:7],
            state["dissipated_energy_pJ"][:7],
        )
        packed = q + (m + h if enabled else []) + energy
        ref.readout(p, packed)  # Independent positivity/kinetic-domain check; no time step.
        ledger.compare(key + f"/transfer/{j}", state["channel_transferred"][:7], q, "state")
        ledger.compare(
            key + f"/bath/{j}",
            state["extracellular_amount_increment"][1][0],
            -math.fsum(q),
            "state",
        )
        ledger.compare(
            key + f"/energy/{j}",
            math.fsum(energy),
            refcheck.thermodynamic_dissipation(p, q),
            "energy",
        )
        c.require(all(v >= -1e-12 for v in energy), "Negative Cells dissipation")
        if variant != "active_channel":
            zero(q + energy + state["extracellular_amount_increment"][1])
        if not enabled:
            zero(state["gate"])
    diagnostics = record["diagnostics"]
    limits = {
        "max_balance_error_fmol": 1e-10,
        "max_extracellular_balance_error_fmol": 1e-10,
        "max_global_balance_error_fmol": 1e-10,
        "max_charge_balance_error_V": 1e-8,
        "max_countercharge_error_C": 1e-20,
        "max_energy_balance_error_pJ": 1e-6,
    }
    c.require(
        set(diagnostics) == set(limits)
        and all(0 <= diagnostics[k] <= limit for k, limit in limits.items()),
        "Production invariant diagnostics rejected",
    )
    c.require(
        observations["times"] == r["protocol"]["common_times_s"], "Cells observation clock differs"
    )
    points = []
    for j, time_s in enumerate(observations["times"]):
        index = round(time_s / dt)
        for name in ready.STATE_SHAPES:
            ledger.compare(
                key + f"/sample/{j}/{name}",
                observations[name][j],
                history[name][index],
                "gate" if name == "gate" else "state",
            )
        points.append(
            {
                "gate": [v[:7] for v in observations["gate"][j]],
                "voltage_V": observations["voltage_V"][j][:7],
                "cell_K_fmol": observations["amount"][j][1][:7],
                "bath_K_fmol": observations["extracellular_amount"][j][1][0],
                "transfer_fmol": observations["channel_transferred"][j][:7],
                "flux_fmol_per_s": observations["channel_flux_fmol_per_s"][j][:7],
                "permeability_m_per_s": observations["channel_effective_permeability_m_per_s"][j][
                    :7
                ],
                "inward_current_A": observations["membrane_current_A"][j][:7],
                "energy_pJ": observations["dissipated_energy_pJ"][j][:7],
            }
        )
        q = history["amount_increment"][index][1][:7]
        packed = (
            q
            + (history["gate"][index][0][:7] + history["gate"][index][1][:7] if enabled else [])
            + history["dissipated_energy_pJ"][index][:7]
        )
        own_state = ref.readout(p, packed)
        units = {
            "gate": "gate",
            "voltage_V": "voltage_V",
            "cell_K_fmol": "amount_fmol",
            "bath_K_fmol": "amount_fmol",
            "transfer_fmol": "amount_fmol",
            "flux_fmol_per_s": "flux_fmol_per_s",
            "permeability_m_per_s": "permeability_m_per_s",
            "inward_current_A": "current_A",
            "energy_pJ": "energy_pJ",
        }
        for field, unit in units.items():
            ledger.compare(
                key + f"/constitutive/{j}/" + field, points[-1][field], own_state[field], unit
            )
    return points


def cells_checks(r, output, aggregate):
    c.require(
        set(aggregate["records"]) == set(r["cells_definitions"])
        and aggregate["cells_trajectories"] == len(r["cells_definitions"]),
        "Cells trajectory coverage differs",
    )
    ledger = io.Ledger(
        cells_tolerances(r),
        2e-11,
        output / "cells-state-failures.jsonl",
    )
    points, records = {}, {}
    for key, path in aggregate["records"].items():
        record = io.read_compressed(output / path)
        points[key] = cells_points_and_checks(r, record, ledger)
        records[key] = record
    restarts, backends = {}, {}
    expected_resumes = {
        ctx.key(v, r["protocol"]["restart_step_s"], "jax_jit") for v in r["protocol"]["variants"]
    }
    c.require(
        set(aggregate["resumed"]) == expected_resumes
        and aggregate["resumed_segments"] == len(expected_resumes),
        "Restart coverage differs",
    )
    for key, path in aggregate["resumed"].items():
        resumed = io.read_compressed(output / path)
        start = round(r["protocol"]["restart_time_s"] / r["protocol"]["restart_step_s"])
        c.require(
            resumed["definition"] == records[key]["definition"]
            and resumed["runtime"] == records[key]["runtime"]
            and resumed["start_step"] == start
            and resumed["final_step_index"] == records[key]["final_step_index"],
            "Restart metadata differs",
        )
        restarts[key] = compare_histories(
            key,
            records[key],
            resumed,
            r["protocol"]["restart_absolute"],
            2e-11,
            output / "cells" / key / "restart-failures.jsonl",
            start,
        )
    for variant in r["protocol"]["variants"]:
        eager, compiled = (
            records[ctx.key(variant, r["protocol"]["cells_eager_step_s"], backend)]
            for backend in ("jax_eager", "jax_jit")
        )
        backends[variant] = compare_histories(
            variant,
            compiled,
            eager,
            r["protocol"]["backend_absolute"],
            2e-11,
            output / f"backend-{variant}-failures.jsonl",
        )
    failures = ledger.failed + sum(
        v["failed_comparisons"] for v in (*restarts.values(), *backends.values())
    )
    return {
        "status": "pass" if not failures else "fail",
        "failed_comparisons": failures,
        "state_checks": ledger.summary(),
        "restarts": restarts,
        "backends": backends,
        "points": points,
    }
