"""Reuse ordinary runners, durable full-state snapshots and comparison ledgers."""

import copy
import gc
import resource

import context as x
import numpy as np
import reference


def same(a, b):
    for first, second in zip(a, b, strict=True):
        np.testing.assert_array_equal(first, second)


def reference_worker(root):
    protocol, definitions = x.inputs(root)
    reports = []
    for arm, raw in definitions.items():
        for setting in protocol["references"]:
            result = reference.integrate(raw, setting, rhs_cap=protocol["reference_rhs_cap"])
            x.u.write(root / "reference" / arm / (setting["method"] + ".json"), result)
            reports.append(
                dict(arm=arm, **setting, rhs_calls=result["rhs_calls"], steps=result["steps"])
            )
            print("reference", arm, setting["method"], "completed", flush=True)
    return dict(solves=len(reports), rows=reports)


def production(root, backend):
    from cells.core.runner import branch_checkpoint, run
    from cells.core.specs import parse_spec
    from cells.io import load_snapshot, write_run, write_snapshot

    protocol, definitions = x.inputs(root)
    reports = []
    for arm in protocol["arms"]:
        for index, dt in enumerate(protocol["steps_s"]):
            raw = copy.deepcopy(definitions[arm])
            raw["execution"].update(backend=backend, dt=dt)
            result = run(parse_spec(raw))
            path = root / backend / arm / str(index)
            write_run(path / "run", result)
            x.u.need(
                {d.platform for d in result.final.state.amount_increment.devices()} == {backend},
                "Spatial execution device mismatch",
            )
            x.u.need(
                result.final.state.amount_increment.dtype == np.float64, "Spatial float64 required"
            )
            c = reference.bind(raw)
            x.u.write(
                path / "observations.json",
                dict(
                    states=reference.flatten(c, vars(result.observations)).tolist(),
                    voltage_V=result.observations.voltage_V[:, : len(c["cells"])].tolist(),
                    times_s=result.observations.times.tolist(),
                    diagnostics=result.diagnostics,
                ),
            )
            restarts = []
            if index == len(protocol["steps_s"]) - 1:
                for time_s in protocol["restart_times_s"]:
                    checkpoint = result.checkpoint_at(time_s)
                    saved_path = path / ("restart-" + str(time_s))
                    write_snapshot(saved_path, result.spec, checkpoint)
                    saved = load_snapshot(saved_path)
                    resumed = run(saved.spec, saved.checkpoint)
                    write_run(saved_path / "resumed", resumed)
                    same(resumed.history, tuple(a[checkpoint.step_index :] for a in result.history))
                    restarts.append(dict(time_s=time_s, complete_state_bitwise_equal=True))
                if arm == "baseline":
                    changed = copy.deepcopy(raw)
                    for group in changed["experiment"]["membrane_controls"]:
                        group["pump"].append({"time": checkpoint.time, "multiplier": 0.0})
                    spec = parse_spec(changed)
                    branch = run(spec, branch_checkpoint(result.spec, checkpoint, spec))
                    write_run(path / "pump-off-branch", branch)
                    same(tuple(v[0] for v in branch.history), checkpoint.state)
                    np.testing.assert_array_equal(
                        branch.history.pump_cycles[-1], checkpoint.state.pump_cycles
                    )
                    x.u.need(
                        np.any(
                            branch.history.face_transferred[-1] != checkpoint.state.face_transferred
                        ),
                        "Spatial branch did not retain active outside transport",
                    )
            if arm.endswith("_release"):
                field = {
                    "pump_release": "pump_cycles",
                    "channel_release": "channel_transferred",
                    "junction_release": "junction_transferred",
                }[arm]
                times = result.times
                selected = (times >= 0.005) & (times <= 0.01)
                history = np.asarray(getattr(result.history, field))[selected]
                np.testing.assert_array_equal(history, np.broadcast_to(history[0], history.shape))
                if arm != "pump_release":
                    gate = "gate" if arm == "channel_release" else "junction_gate"
                    g = np.asarray(getattr(result.history, gate))[selected]
                    x.u.need(np.any(g[-1] != g[0]), "Blocked intrinsic gates stopped evolving")
            if arm == "blocked":
                for key in (
                    "amount_increment",
                    "leak_transferred",
                    "pump_cycles",
                    "channel_transferred",
                    "junction_transferred",
                    "dissipated_energy_pJ",
                    "junction_dissipated_energy_pJ",
                ):
                    np.testing.assert_array_equal(getattr(result.history, key), 0)
                x.u.need(
                    np.any(result.history.face_transferred[-1] != 0),
                    "Blocked cell lost bulk diffusion",
                )
            peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
            x.u.need(
                peak <= protocol["resources"]["max_worker_rss_bytes"],
                "Spatial host-memory allowance",
            )
            record = dict(
                arm=arm,
                dt_s=dt,
                diagnostics=result.diagnostics,
                restarts=restarts,
                peak_rss_bytes=peak,
                timings=result.timings,
            )
            x.u.write(path / "checks.json", record)
            reports.append(record)
            print(backend, arm, dt, "captured and checked", flush=True)
            del result
            gc.collect()
    # Exercise the same world-ID and full snapshot path used by GPU scheduling.
    # Two different physical worlds verify isolation; this is not a throughput claim.
    from cells.batch_io import load_batch_snapshot, write_batch_snapshot
    from cells.core.batch import BatchSpec, WorldSpec, run_batch

    worlds = []
    for identity, arm in ((41, "baseline"), (79, "blocked")):
        raw = copy.deepcopy(definitions[arm])
        raw["execution"].update(backend=backend, dt=protocol["steps_s"][0])
        worlds.append(WorldSpec(identity, parse_spec(raw)))
    batch_spec = BatchSpec(tuple(worlds), 2, 10000, 512 * 1024**2)
    batch = run_batch(batch_spec)
    checkpoints = {identity: world.final for identity, world in batch.worlds.items()}
    write_batch_snapshot(root / backend / "batch-checkpoint", batch_spec, checkpoints)
    saved = load_batch_snapshot(root / backend / "batch-checkpoint")
    u = x.u
    u.need(
        saved.spec == batch_spec and set(saved.checkpoints) == {41, 79}, "Spatial batch ownership"
    )
    for identity, arm in ((41, "baseline"), (79, "blocked")):
        same(saved.checkpoints[identity].state, checkpoints[identity].state)
        with np.load(root / backend / arm / "0/run/trajectory.npz", allow_pickle=False) as scalar:
            for name, values in batch.worlds[identity].history._asdict().items():
                np.testing.assert_array_equal(values, scalar[name])
    record = dict(
        world_ids=[41, 79],
        scalar_histories_bitwise_equal=True,
        complete_checkpoint_roundtrip=True,
        timings=batch.timings,
    )
    u.write(root / backend / "batch-checks.json", record)
    return dict(backend=backend, trajectories=len(reports), rows=reports, batch=record)


def compare(root):
    x.u.module_path("pump_matched_pilot")
    from pilot_math import Ledger, contraction

    protocol, definitions = x.inputs(root)
    t = protocol["tolerances"]
    ledger, refinement = Ledger(), []
    for arm in protocol["arms"]:
        c = reference.bind(definitions[arm])
        refs = [
            x.u.read(root / "reference" / arm / (s["method"] + ".json"))
            for s in protocol["references"]
        ]
        ledger.compare(
            "reference_agreement",
            refs[0]["state"],
            refs[1]["state"],
            t["state_atol"],
            t["state_rtol"],
        )
        for backend in ("cpu", "gpu"):
            errors, voltages = [], []
            for i, _ in enumerate(protocol["steps_s"]):
                path = root / backend / arm / str(i)
                actual = x.u.read(path / "observations.json")
                for target in refs:
                    x.u.need(
                        actual["times_s"] == target["times_s"], "Spatial observation clock mismatch"
                    )
                    ledger.compare(
                        "independent_state",
                        actual["states"],
                        target["state"],
                        t["state_atol"],
                        t["state_rtol"],
                    )
                    delta = reference.unpack(c, np.asarray(target["state"]))["amount_increment"]
                    expected_v = reference.voltage(c, delta)
                    ledger.compare(
                        "independent_voltage_V",
                        actual["voltage_V"],
                        expected_v.tolist(),
                        t["voltage_V"],
                    )
                errors.append(
                    float(np.max(np.abs(np.asarray(actual["states"]) - refs[0]["state"])))
                )
                target_v = reference.voltage(
                    c, reference.unpack(c, np.asarray(refs[0]["state"]))["amount_increment"]
                )
                voltages.append(float(np.max(np.abs(np.asarray(actual["voltage_V"]) - target_v))))
                for key, limit in (
                    ("max_balance_error_fmol", "material_fmol"),
                    ("max_extracellular_balance_error_fmol", "material_fmol"),
                    ("max_global_balance_error_fmol", "material_fmol"),
                    ("max_countercharge_error_C", "charge_C"),
                    ("max_component_charge_C", "charge_C"),
                    ("max_energy_balance_error_pJ", "energy_pJ"),
                ):
                    ledger.compare(key, [actual["diagnostics"][key]], [0.0], t[limit])
                x.u.need(
                    actual["diagnostics"]["max_current_normalized"] <= 1.0,
                    "Spatial Kirchhoff residual",
                )
                if backend == "gpu":
                    with (
                        np.load(path / "run/trajectory.npz", allow_pickle=False) as a,
                        np.load(
                            root / "cpu" / arm / str(i) / "run/trajectory.npz", allow_pickle=False
                        ) as b,
                    ):
                        x.u.need(set(a.files) == set(b.files), "CPU/GPU archive field mismatch")
                        for name in a.files:
                            x.u.need(a[name].shape == b[name].shape, "CPU/GPU field shape mismatch")
                            if name in ("accepted_times", "observation_times"):
                                np.testing.assert_array_equal(a[name], b[name])
                            elif name == "observed_current_normalized":
                                for label, values in (("cpu", b[name]), ("gpu", a[name])):
                                    x.u.need(np.all(values >= 0), "Negative residual normalization")
                                    ledger.compare(
                                        label + "_normalized_field_residual",
                                        values.tolist(),
                                        np.zeros_like(values).tolist(),
                                        1.0,
                                    )
                            else:
                                atol = t["cpu_gpu_atol"]
                                for suffix, key in (
                                    ("_A", "current_A"),
                                    ("_C", "charge_C"),
                                    ("_W", "power_W"),
                                    ("_J", "work_J"),
                                ):
                                    if name.endswith(suffix):
                                        atol = t["cpu_gpu_" + key]
                                ledger.compare(
                                    "cpu_gpu_state_and_physical_fields",
                                    a[name].tolist(),
                                    b[name].tolist(),
                                    atol,
                                    t["cpu_gpu_rtol"],
                                )
            refinement.append(
                dict(
                    arm=arm,
                    backend=backend,
                    state=contraction(errors, t["contraction_floor"], t["contraction_max"]),
                    voltage=contraction(voltages, t["contraction_floor"], t["contraction_max"]),
                )
            )
    return dict(
        status="spatial_kinetic_cluster_cpu_gpu_panel_pass",
        comparisons=ledger.comparisons,
        maxima=ledger.maxima,
        refinement=refinement,
        trajectories=36,
        reference_solves=12,
        exact_disk_restarts=24,
        pump_off_branches=2,
        batch_worlds_per_backend=2,
        batch_checkpoint_roundtrips=4,
        scope=protocol["scope"],
        electrical_scope=protocol["electrical_scope"],
        native_betse_spatial_parity=False,
        full_betse_parity=False,
        biological_validation=False,
        multi_gpu_scaling=False,
    )
