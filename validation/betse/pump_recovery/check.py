"""Ordinary CPU/L4 runs, complete restarts, and retained all-state comparisons."""

import gc
import resource

import experiment as x
import numpy as np


def canonical_observations(result):
    values = vars(result.observations)
    return [
        x.canonical({k: np.asarray(values[k])[i].tolist() for k in x.context.STATE_FIELDS})
        for i in range(len(values["times"]))
    ]


def same_history(actual, expected):
    for a, b in zip(actual, expected, strict=True):
        np.testing.assert_array_equal(a, b)


def production(root, backend):
    from cells.core.runner import branch_checkpoint, run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, write_snapshot

    protocol, preparation = (x.u.read(root / p) for p in ("protocol.json", "preparation.json"))
    reports = []
    for arm in protocol["arms"]:
        for index, dt in enumerate(protocol["cells_steps_s"]):
            local = root / backend / arm / str(index)
            raw = x.definition(preparation, arm, protocol, dt, backend)
            x.u.write(local / "definition.json", raw)
            result = run(parse_spec(raw))
            devices = result.final.state.amount_increment.devices()
            x.u.need({d.platform for d in devices} == {backend}, "Recovery device mismatch")
            x.u.need(
                result.final.state.amount_increment.dtype == np.float64, "Recovery float64 required"
            )
            np.savez_compressed(
                local / "trajectory.npz", times_s=result.times, **result.history._asdict()
            )
            record = dict(
                arm=arm,
                backend=backend,
                dt_s=dt,
                times_s=result.observations.times.tolist(),
                states=canonical_observations(result),
                voltage_V=result.observations.voltage_V[:, :7].tolist(),
                diagnostics=result.diagnostics,
                timings=result.timings,
                devices=[str(d) for d in devices],
            )
            x.u.write(local / "observations.json", record)
            restarts = []
            if index == len(protocol["cells_steps_s"]) - 1:
                for name in ("block_time_s", "release_time_s"):
                    checkpoint = result.checkpoint_at(protocol[name])
                    write_snapshot(local / name, result.spec, checkpoint)
                    saved = load_snapshot(local / name)
                    resumed = run(saved.spec, saved.checkpoint)
                    same_history(
                        resumed.history, tuple(a[checkpoint.step_index :] for a in result.history)
                    )
                    restarts.append(dict(time_s=protocol[name], all_state_fields_exact=True))
                    del resumed
                if arm != "baseline":
                    base = load_snapshot(root / backend / "baseline" / str(index) / "block_time_s")
                    checkpoint = branch_checkpoint(base.spec, base.checkpoint, result.spec)
                    branch = run(result.spec, checkpoint)
                    same_history(
                        branch.history, tuple(a[checkpoint.step_index :] for a in result.history)
                    )
                    del branch
            if arm in ("held_block", "block_release"):
                end = protocol["duration_s"] if arm == "held_block" else protocol["release_time_s"]
                selected = (result.times >= protocol["block_time_s"]) & (result.times <= end)
                cycles = np.asarray(result.history.pump_cycles)[selected]
                np.testing.assert_array_equal(cycles, np.broadcast_to(cycles[0], cycles.shape))
            if arm in ("block_release", "half_release"):
                at_release = result.checkpoint_at(protocol["release_time_s"])
                x.u.need(
                    np.any(result.history.pump_cycles[-1] > at_release.state.pump_cycles),
                    "Released pump did not resume cycling",
                )
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            x.u.need(
                peak <= protocol["resources"]["max_worker_rss_bytes"], "Recovery host-memory cap"
            )
            reports.append(dict(arm=arm, dt_s=dt, restarts=restarts, peak_rss_bytes=peak))
            x.u.write(local / "checks.json", reports[-1])
            print(backend, arm, dt, "captured and checked", flush=True)
            del result
            gc.collect()
    return {"backend": backend, "rows": reports, "trajectories": len(reports)}


def compare(root):
    from pilot_math import Ledger, contraction
    from reference import equations

    protocol, preparation = (x.u.read(root / p) for p in ("protocol.json", "preparation.json"))
    plan = x.plan(protocol)
    ledger, reports, summaries = Ledger(), [], {}
    for arm in protocol["arms"]:
        primary = x.u.read(root / "reference" / arm / (plan["reference"]["primary"] + ".json"))
        for backend in protocol["backends"]:
            errors = {key: [] for key in ("amount", "energy", "voltage")}
            for index, dt in enumerate(protocol["cells_steps_s"]):
                local = root / backend / arm / str(index)
                record = x.u.read(local / "observations.json")
                x.u.need(
                    record["arm"] == arm and record["backend"] == backend and record["dt_s"] == dt,
                    "Recovery row identity changed",
                )
                x.u.need(record["times_s"] == primary["times_s"], "Recovery comparison clock")
                for setting in plan["reference"]["solves"]:
                    expected = x.u.read(root / "reference" / arm / (setting["id"] + ".json"))
                    ledger.compare(
                        "cells_state",
                        record["states"],
                        expected["states"],
                        plan["trajectory"]["cells_state_atol"],
                        plan["trajectory"]["cells_state_rtol"],
                    )
                    ledger.compare(
                        "cells_voltage",
                        record["voltage_V"],
                        expected["voltage_V"],
                        plan["trajectory"]["cells_voltage_V"],
                    )
                a, b = np.asarray(record["states"]), np.asarray(primary["states"])
                for key, value in (
                    ("amount", np.max(np.abs(a[:, :52] - b[:, :52]))),
                    ("energy", np.max(np.abs(a[:, 52:] - b[:, 52:]))),
                    (
                        "voltage",
                        np.max(np.abs(np.asarray(record["voltage_V"]) - primary["voltage_V"])),
                    ),
                ):
                    errors[key].append(float(value))
                for key, budget in (
                    ("max_balance_error_fmol", "cells_material_fmol"),
                    ("max_extracellular_balance_error_fmol", "cells_material_fmol"),
                    ("max_global_balance_error_fmol", "cells_material_fmol"),
                    ("max_countercharge_error_C", "cells_charge_C"),
                    ("max_energy_balance_error_pJ", "cells_energy_pJ"),
                ):
                    ledger.compare(
                        key, [record["diagnostics"][key]], [0.0], plan["accounting"][budget]
                    )
                with (
                    np.load(local / "trajectory.npz", allow_pickle=False) as actual,
                    np.load(
                        root / "cpu" / arm / str(index) / "trajectory.npz", allow_pickle=False
                    ) as cpu,
                    np.load(
                        root / backend / "baseline" / str(index) / "trajectory.npz",
                        allow_pickle=False,
                    ) as base,
                ):
                    np.testing.assert_array_equal(actual["times_s"], base["times_s"])
                    before = actual["times_s"] <= protocol["block_time_s"]
                    for key in x.context.STATE_FIELDS:
                        np.testing.assert_allclose(
                            actual[key], cpu[key], atol=protocol["cpu_gpu_atol"], rtol=0
                        )
                        np.testing.assert_array_equal(actual[key][before], base[key][before])
                        if arm == "no_op":
                            np.testing.assert_array_equal(actual[key], base[key])
            report = {
                key: contraction(
                    values,
                    plan["refinement"][
                        "floor_"
                        + {"amount": "amount_fmol", "energy": "energy_pJ", "voltage": "voltage_V"}[
                            key
                        ]
                    ],
                    plan["refinement"]["contraction_max"],
                )
                for key, values in errors.items()
            }
            reports.append(dict(arm=arm, backend=backend, refinement=report))
        case = x.case(preparation, arm, protocol)
        final = primary["states"][-1]
        rates = equations.rhs(case, final, x.control_at(case["controls"], protocol["duration_s"]))
        baseline = x.u.read(root / "reference/baseline" / (plan["reference"]["primary"] + ".json"))
        release_index = primary["times_s"].index(protocol["release_time_s"])
        distances = {}
        for name, index in (("at_release", release_index), ("at_end", -1)):
            distances[name] = dict(
                max_voltage_difference_V=float(
                    np.max(
                        np.abs(
                            np.asarray(primary["voltage_V"][index]) - baseline["voltage_V"][index]
                        )
                    )
                ),
                max_inventory_difference_fmol=float(
                    np.max(
                        np.abs(
                            np.asarray(primary["states"][index][:24])
                            - baseline["states"][index][:24]
                        )
                    )
                ),
            )
        if arm in ("block_release", "held_block"):
            x.u.need(
                distances["at_release"]["max_voltage_difference_V"]
                >= protocol["minimum_response_V"],
                "Pump intervention response is unresolved",
            )
        summaries[arm] = dict(
            distances_from_unperturbed=distances,
            final_inside_rates_mM_s=[
                [rates[3 * i + s] / case["volume_pL"][i] for s in range(3)] for i in range(7)
            ],
            final_bath_rates_mM_s=[v / case["outside_volume_pL"] for v in rates[21:24]],
            equilibrium_or_complete_recovery_inferred=False,
        )
    return dict(
        status="pump_availability_cpu_gpu_panel_pass",
        trajectories=30,
        reference_solves=15,
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
        refinement=reports,
        transient_response=summaries,
        scope=protocol["scope"],
        native_runs=0,
        native_recovery_qualified=False,
        steady_state_qualified=False,
        full_betse_parity=False,
        biological_validation=False,
        multi_gpu_scaling=False,
    )
