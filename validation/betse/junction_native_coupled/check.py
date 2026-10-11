"""Recorded source laws, independent native replay and CPU/L4 physical trajectories."""

import argparse
import sys
from pathlib import Path

import numpy as np

from cells.processes.junction_gate import Parameters

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

HERE = Path(__file__).resolve().parent
base = u.private("native_transport_checks", HERE.parent / "junction_trajectory/check.py")
production = u.private("production_coupled_checks", HERE.parent / "junction_coupled/check.py")
adapter = u.private("native_coupled_adapter", HERE / "compatibility.py")
ref = u.private("native_coupled_reference", HERE / "reference.py")


def bind(prepared, row, trace, protocol):
    c = base.ref.bind(prepared, row, trace, protocol | {"species": row["case"]["order"]})
    e = len(c["opening"])
    c.update(
        threshold=np.full(e, protocol["threshold_voltage_V"]),
        minimum=np.full(e, protocol["minimum_open_fraction"]),
        initial_gate=np.full(e, protocol["initial_gate"]),
        # Native storage, retained without an amount/volume round trip. This is
        # used only by the discrete compatibility replay, not the physical ODE.
        initial_concentration_mM=trace["initial_cc_cells"][c["indices"]].copy(),
        block=row["case"]["block"],
    )
    return c


def definition(c, protocol, dt, backend):
    raw = base.cells_bridge.definition(c, protocol, dt)
    raw["model"]["id"] = protocol["model"]
    for edge in raw["model"]["junctions"]:
        edge.pop("residual_fraction")
        edge["gate"] = {
            "law": "betse_rate_junction_relaxation@1",
            "threshold_voltage_V": protocol["threshold_voltage_V"],
            "minimum_open_fraction": protocol["minimum_open_fraction"],
            "initial_gate": protocol["initial_gate"],
        }
    for group in raw["experiment"]["junction_controls"]:
        group["schedule"][0]["open_fraction"] *= c["block"]
    raw["execution"].update(
        backend=backend, max_trace_bytes=protocol["resources"]["max_trace_bytes"]
    )
    return raw


def native_values(c, row, trace, gates, protocol):
    n, m, faces = row["steps"], len(c["species"]), len(c["owners"])
    tol = protocol["tolerances"]
    for name in ("before", "after", "voltage", "block"):
        u.need(
            gates[name].shape == (n * m, faces) and np.isfinite(gates[name]).all(),
            "Invalid gate trace " + name,
        )
    np.testing.assert_array_equal(gates["species"], np.tile(c["indices"], n))
    np.testing.assert_array_equal(gates["step"], np.repeat(np.arange(n), m))
    np.testing.assert_array_equal(trace["initial_gjopen"], row["fixture"]["after_setup"]["gjopen"])
    np.testing.assert_array_equal(gates["before"][0], trace["initial_gjopen"])
    np.testing.assert_array_equal(gates["before"][1:], gates["after"][:-1])
    shaped = {k: gates[k].reshape(n, m, faces) for k in ("before", "after", "voltage", "block")}
    np.testing.assert_array_equal(shaped["before"][:, 0], trace["before_gjopen"])
    np.testing.assert_array_equal(shaped["after"][:, -1], trace["transport_gjopen"])
    np.testing.assert_array_equal(trace["transport_gjopen"], trace["after_gjopen"])
    expected_block = np.zeros(faces)
    a, b = c["faces"].T
    np.testing.assert_array_equal(trace["initial_gjopen"][a], protocol["initial_gate"])
    np.testing.assert_array_equal(trace["initial_gjopen"][b], protocol["initial_gate"])
    expected_block[a] = expected_block[b] = c["opening"] * c["block"]
    np.testing.assert_array_equal(
        gates["block"], np.broadcast_to(expected_block, gates["block"].shape)
    )
    np.testing.assert_array_equal(row["fixture"]["after_setup"]["gj_block"], expected_block)
    voltage = trace["before_vm"].copy()
    for index in range(m):
        if index:
            voltage += 1e-25
        np.testing.assert_array_equal(
            shaped["voltage"][:, index], voltage[:, c["partners"]] - voltage
        )
    expected = adapter.gate_adapter.step(
        gates["before"],
        gates["voltage"],
        gates["block"],
        row["dt_s"],
        Parameters(protocol["threshold_voltage_V"], protocol["minimum_open_fraction"]),
    )
    np.testing.assert_allclose(
        gates["after"], expected, rtol=tol["source_gate_rtol"], atol=tol["source_gate_atol"]
    )
    np.testing.assert_allclose(
        gates["after"][:, a], gates["after"][:, b], rtol=0, atol=tol["source_gate_atol"]
    )
    u.need(np.min(gates["after"]) >= 0 and np.max(gates["after"]) <= 1, "Native stored gate domain")
    u.need(np.max(np.abs(gates["voltage"])) <= 0.120, "Native junction voltage domain")
    times, transport, accounting = base.native_values(
        c, row, trace, protocol, gate_by_species=shaped["after"][:, :, a]
    )
    edge_gate = np.concatenate((trace["initial_gjopen"][None, a], trace["after_gjopen"][:, a]))
    values = np.concatenate((transport, edge_gate), axis=-1)
    return (
        times,
        values,
        accounting
        | {
            "gate_calls": n * m,
            "source_gate_max_error": base.ref.maximum(gates["after"] - expected),
            "min_stored_gate": float(np.min(gates["after"])),
        },
    )


def bounded(errors, protocol, prefix=""):
    for key, value in errors.items():
        base.bound(value, protocol["tolerances"][prefix + key], prefix + key)


def physical_accounting(c, values, protocol):
    delta, transfer, energy, _ = ref.physical.unpack(c, values)
    checks = base.ref.accounting(c, delta, transfer, energy)
    base.check_accounting(checks, protocol["tolerances"], "energy_pJ")
    return checks


def load_row(directory, record, protocol):
    path = directory / record["path"]
    u.need(u.sha(path / "result.json") == record["sha256"], "Changed native result")
    row = u.read(path / "result.json")
    u.need(row["hook_restored"] and row["native_pickle_present"], "Incomplete native lifecycle")
    u.need(
        u.sha(path / "preparation.json") == row["preparation_sha256"], "Changed native preparation"
    )
    expected = dict.fromkeys(row["settings"], 0)
    expected.update(
        v_sensitive_gj=True,
        gj_surface=protocol["gj_surface_fraction"],
        gj_min=protocol["minimum_open_fraction"],
        gj_vthresh=1000 * protocol["threshold_voltage_V"],
    )
    u.need(row["settings"] == expected, "Changed native process settings")
    for key, name in (("trace_sha256", "trace.npz"), ("gates_sha256", "gates.npz")):
        if row["mode"] == "observed":
            u.need(u.sha(path / name) == row[key], "Changed native " + name)
    return row


def check_case(output, protocol, case, rows):
    protocol = protocol | {
        key: case[key]
        for key in ("duration_s", "observation_step_s", "restart_time_s")
        if key in case
    }
    directory = output / "comparison" / case["id"]
    directory.mkdir(parents=True)
    native_reports, c = [], None
    for index, dt in enumerate(protocol["native_steps_s"]):
        key = f"{case['id']}/step-{index}"
        observed, bare = (rows[key + "/" + mode] for mode in ("observed", "bare"))
        for row, mode in ((observed, "observed"), (bare, "bare")):
            u.need(
                row["case"] == case and row["dt_s"] == dt and row["mode"] == mode,
                "Changed native row identity",
            )
        u.need(
            observed["final"] == bare["final"] and observed["fixture"] == bare["fixture"],
            "Observer changed native evolution",
        )
        path = output / "native" / key / "observed"
        with np.load(path / "trace.npz", allow_pickle=False) as archive:
            trace = dict(archive)
        with np.load(path / "gates.npz", allow_pickle=False) as archive:
            gates = dict(archive)
        mapped = bind(u.read(path / "preparation.json"), observed, trace, protocol)
        if c is None:
            c = mapped
            u.write(
                directory / "mapping.json",
                {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in c.items()},
            )
        else:
            for k in c:
                np.testing.assert_array_equal(c[k], mapped[k])
        times, actual, accounting = native_values(c, observed, trace, gates, protocol)
        np.savez_compressed(directory / f"native-{index}.npz", times_s=times, values=actual)
        replay_reports, cpu = [], None
        for backend in ("cpu", "gpu"):
            predicted, lagged, device = adapter.replay(c, protocol, dt, backend)
            np.savez_compressed(
                directory / f"replay-{index}-{backend}.npz",
                values=predicted,
                lagged_amount_increment=lagged,
            )
            errors = ref.physical.difference(c, predicted, actual)
            bounded(errors, protocol, "replay_")
            native_delta = ref.physical.unpack(c, actual)[0]
            expected_lag = np.concatenate((np.zeros_like(native_delta[:1]), native_delta[:-1]))
            base.bound(
                base.ref.maximum(lagged - expected_lag),
                protocol["tolerances"]["replay_amount_fmol"],
                "Native compatibility lagged inventory",
            )
            u.need(
                device["platform"] == backend and device["dtype"] == "float64",
                "Replay device/dtype mismatch",
            )
            if cpu is None:
                cpu = predicted
                device_error = 0.0
            else:
                device_error = base.ref.maximum(cpu - predicted)
                base.bound(
                    device_error, protocol["tolerances"]["cpu_gpu_atol"], "Replay CPU/GPU agreement"
                )
            replay_reports.append(device | {"errors": errors, "cpu_gpu_error": device_error})
        delta = ref.physical.unpack(c, actual)[0]
        report = {
            "dt_s": dt,
            "accounting": accounting,
            "replays": replay_reports,
            "voltage_change_V": base.ref.maximum(
                base.ref.voltage(c, delta) - c["initial_voltage_V"]
            ),
        }
        if case["block"] == 1:
            limits, refsteps = {}, {}
            for method in ("DOP853", "Radau"):
                limits[method], refsteps[method] = ref.integrate(
                    c, protocol, times, method, calls_per_step=len(case["order"])
                )
            np.savez_compressed(directory / f"native-limit-{index}.npz", times_s=times, **limits)
            agreement = ref.physical.difference(c, limits["DOP853"], limits["Radau"])
            bounded(agreement, protocol)
            report.update(
                continuous_limit_errors=ref.native_difference(c, actual, limits["DOP853"]),
                reference_agreement=agreement,
                reference_steps=refsteps,
                native_clock_multiplier=len(case["order"]),
            )
        u.write(directory / f"native-{index}-checks.json", report)
        native_reports.append(report)
    if case["block"] == 1:
        bounded(native_reports[-1]["continuous_limit_errors"], protocol, "native_")
        for coarse, fine in zip(native_reports[:-1], native_reports[1:], strict=True):
            for field in ("voltage_V", "gate"):
                t = protocol["tolerances"]
                base.bound(
                    fine["continuous_limit_errors"][field],
                    t["native_refinement_ratio_max"] * coarse["continuous_limit_errors"][field]
                    + t["native_refinement_floor_" + ("V" if field == "voltage_V" else "gate")],
                    "Native " + field + " refinement",
                )
    base.check_accounting(
        native_reports[-1]["accounting"], protocol["tolerances"], "native_energy_pJ"
    )
    samples = np.linspace(
        0,
        protocol["duration_s"],
        round(protocol["duration_s"] / protocol["observation_step_s"]) + 1,
    )
    physical = {
        method: ref.integrate(c, protocol, samples, method)[0] for method in ("DOP853", "Radau")
    }
    np.savez_compressed(directory / "physical-references.npz", times_s=samples, **physical)
    bounded(ref.physical.difference(c, physical["DOP853"], physical["Radau"]), protocol)
    u.write(
        directory / "physical-reference-checks.json",
        {method: physical_accounting(c, values, protocol) for method, values in physical.items()},
    )
    cells_reports, cpu = [], {}
    for backend in ("cpu", "gpu"):
        for index, dt in enumerate(protocol["cells_steps_s"]):
            local = directory / f"{backend}-{index}"
            result = production.retained_run(definition(c, protocol, dt, backend), local)
            values = ref.physical.physical(result.observations)
            errors = {
                method: ref.physical.difference(c, values, expected)
                for method, expected in physical.items()
            }
            u.write(local / "comparison.json", errors)
            for values_ in errors.values():
                bounded(values_, protocol)
            balances = physical_accounting(c, values, protocol)
            for field in (
                "extracellular_amount_increment",
                "leak_transferred",
                "pump_cycles",
                "dissipated_energy_pJ",
                "channel_transferred",
            ):
                np.testing.assert_array_equal(getattr(result.history, field), 0)
            replay = production.replay(result, local, protocol["restart_time_s"])
            if backend == "cpu":
                cpu[index] = values
            device_error = base.ref.maximum(cpu[index] - values)
            base.bound(
                device_error, protocol["tolerances"]["cpu_gpu_atol"], "Physical CPU/GPU agreement"
            )
            report = {
                "backend": backend,
                "dt_s": dt,
                "errors": errors,
                "accounting": balances,
                "cpu_gpu_error": device_error,
                **replay,
            }
            u.write(local / "checks.json", report)
            cells_reports.append(report)
    native_physical, _ = ref.integrate(c, protocol, times, "DOP853")
    difference = ref.native_difference(c, actual, native_physical)
    if case["id"] in ("network_nakcl", "network_cl_k_na"):
        u.need(
            difference["gate"] >= protocol["tolerances"]["minimum_clock_difference"],
            "Repeated native clock not resolved",
        )
    if case["block"] == 0.5:
        u.need(
            difference["gate"] >= protocol["tolerances"]["minimum_block_difference"],
            "Stored-state blocking difference not resolved",
        )
        for coarse, fine in zip(native_reports[:-1], native_reports[1:], strict=True):
            base.bound(
                fine["voltage_change_V"],
                protocol["tolerances"]["blocked_response_ratio_max"] * coarse["voltage_change_V"]
                + protocol["tolerances"]["native_refinement_floor_V"],
                "Stored-state block response does not contract under refinement",
            )
    if case["topology"] == "disconnected":
        np.testing.assert_array_equal(actual[:, : c["initial_amount_fmol"].size], 0)
    else:
        delta = ref.physical.unpack(c, actual)[0]
        u.need(
            base.ref.maximum(base.ref.voltage(c, delta) - c["initial_voltage_V"])
            > protocol["tolerances"][
                "minimum_voltage_change_V"
                if case["block"] == 1
                else "minimum_blocked_voltage_change_V"
            ],
            "Trivial free-voltage trajectory",
        )
    answer = {
        "case": case,
        "native": native_reports,
        "cells": cells_reports,
        "native_vs_physical_model": difference,
        "same_continuous_equations": len(case["order"]) == 1 and case["block"] == 1,
    }
    u.write(directory / "checks.json", answer)
    print(
        case["id"],
        "native replay, clock comparison and CPU/L4 physical trajectories passed",
        flush=True,
    )
    return answer


def check(output):
    protocol = u.read(output / "protocol.json")
    panel = u.read(output / "native/panel.json")
    u.need(panel["protocol"] == protocol, "Changed native protocol")
    expected = {
        f"{c['id']}/step-{i}/{m}"
        for c in protocol["cases"]
        for i in range(len(protocol["native_steps_s"]))
        for m in protocol["native_modes"]
    }
    u.need(
        len(panel["rows"]) == len(expected) and {r["path"] for r in panel["rows"]} == expected,
        "Incomplete/duplicated native panel",
    )
    runtime = u.runtime()
    rows = {r["path"]: load_row(output / "native", r, protocol) for r in panel["rows"]}
    cases = [check_case(output, protocol, case, rows) for case in protocol["cases"]]
    u.need(u.runtime() == runtime, "Checker runtime changed")
    return {
        "status": "native_dynamic_free_voltage_correspondence_pass",
        "cases": cases,
        "runtime": runtime,
        "native_pairs": len(rows) // 2,
        "comparison_files_sha256": u.inventory(output / "comparison"),
        "scope": protocol["scope"],
        "full_betse_parity": False,
        "biological_validation": False,
        "gpu_throughput_qualified": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    u.write(args.output / "comparison-result.json", check(args.output))
