"""Ordinary CPU/L4 trajectories, independent references and complete disk replay."""

import argparse
import sys
from pathlib import Path

import numpy as np

from cells.core.batch import BatchSpec, WorldSpec, run_batch
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.io import load_snapshot, write_snapshot

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "fresh_rerun"))
import common as u  # noqa: E402

fixtures = u.private("physical_junction_fixtures", Path(__file__).with_name("fixtures.py"))
ref = u.private("physical_junction_reference", Path(__file__).with_name("reference.py"))


def limits(errors, protocol):
    for key, value in errors.items():
        u.need(np.isfinite(value) and value <= protocol["tolerances"][key], f"{key} error: {value}")


def replay(result, directory, time):
    checkpoint = result.checkpoint_at(time)
    write_snapshot(directory / "restart", result.spec, checkpoint)
    saved = load_snapshot(directory / "restart")
    resumed = run(saved.spec, saved.checkpoint)
    for full, suffix in zip(result.history, resumed.history, strict=True):
        np.testing.assert_array_equal(full[checkpoint.step_index :], suffix)
    return {
        "disk_restart_exact": True,
        "restart_time_s": time,
        "all_state_fields": list(result.history._fields),
    }


def retained_run(raw, directory):
    directory.mkdir()
    u.write(directory / "definition.json", raw)
    result = run(parse_spec(raw))
    np.savez_compressed(
        directory / "trajectory.npz", times_s=result.times, **result.history._asdict()
    )
    np.savez_compressed(directory / "observations.npz", **vars(result.observations))
    u.need(result.final.state.amount_increment.dtype == np.float64, "Wrong production dtype")
    devices = result.final.state.amount_increment.devices()
    u.need(
        {d.platform for d in devices} == {raw["execution"]["backend"]}, "Wrong production device"
    )
    u.write(
        directory / "execution.json",
        {
            "devices": [str(d) for d in devices],
            "timings": result.timings,
            "diagnostics": result.diagnostics,
        },
    )
    return result


def check_case(case, protocol, directory):
    directory.mkdir()
    raw = fixtures.definition(case, protocol)
    c = ref.bind(raw)
    samples = np.asarray(raw["experiment"]["observation_times"])
    references, steps = {}, {}
    for method in ("DOP853", "Radau"):
        references[method], steps[method] = ref.integrate(c, protocol["reference"], samples, method)
    np.savez_compressed(directory / "references.npz", times_s=samples, **references)
    reference_error = ref.difference(c, references["DOP853"], references["Radau"])
    reference_accounting = {}
    for method, values in references.items():
        delta, transfer, energy, _ = ref.unpack(c, values)
        reference_accounting[method] = ref.transport.accounting(c, delta, transfer, energy)
    u.write(
        directory / "reference-checks.json",
        {"difference": reference_error, "steps": steps, "accounting": reference_accounting},
    )
    limits(reference_error, protocol)
    for accounting in reference_accounting.values():
        for name in ("material_fmol", "local_transfer_fmol"):
            u.need(
                accounting[name] <= protocol["tolerances"]["material_fmol"],
                "Reference material error",
            )
        u.need(
            accounting["energy_pJ"] <= protocol["tolerances"]["energy_pJ"], "Reference energy error"
        )
        u.need(
            accounting["minimum_dissipation_increment_pJ"] >= -1e-12,
            "Negative reference dissipation",
        )
    reports, cpu = [], {}
    for backend in ("cpu", "gpu"):
        voltage_errors = []
        for index, dt in enumerate(protocol["cells_steps_s"]):
            local = directory / f"{backend}-{index}"
            definition = fixtures.definition(case, protocol, dt=dt, backend=backend)
            result = retained_run(definition, local)
            actual = ref.physical(result.observations)
            errors = {
                method: ref.difference(c, actual, expected)
                for method, expected in references.items()
            }
            u.write(local / "comparison.json", errors)
            for difference in errors.values():
                limits(difference, protocol)
            voltage_errors.append(max(e["voltage_V"] for e in errors.values()))
            # The registered full block has zero transport but live intrinsic gates.
            blocked = (result.times >= 0.5) & (result.times <= 0.75)
            transfer = result.history.junction_transferred[blocked]
            np.testing.assert_array_equal(transfer, np.broadcast_to(transfer[0], transfer.shape))
            u.need(
                np.max(np.abs(np.diff(result.history.junction_gate[blocked], axis=0))) > 1e-8,
                "Blocked gate stopped evolving",
            )
            if case == "disconnected_mixed":
                np.testing.assert_array_equal(result.history.amount_increment, 0)
                np.testing.assert_array_equal(result.history.junction_transferred, 0)
            else:
                u.need(
                    np.max(np.abs(result.observations.voltage_V - c["initial_voltage_V"])) > 1e-5,
                    "Free-voltage experiment is trivial",
                )
            for field in (
                "extracellular_amount_increment",
                "leak_transferred",
                "pump_cycles",
                "dissipated_energy_pJ",
                "channel_transferred",
            ):
                np.testing.assert_array_equal(getattr(result.history, field), 0)
            resumed = replay(result, local, protocol["restart_time_s"])
            if backend == "cpu":
                cpu[index] = actual
                device_error = 0.0
            else:
                device_error = float(np.max(np.abs(actual - cpu[index])))
                u.need(
                    device_error <= protocol["tolerances"]["cpu_gpu_atol"],
                    "CPU/GPU coupled mismatch",
                )
            reports.append(
                {
                    "backend": backend,
                    "dt_s": dt,
                    "errors": errors,
                    "cpu_gpu_error": device_error,
                    **resumed,
                }
            )
            u.write(local / "checks.json", reports[-1])
        u.need(
            voltage_errors[1]
            <= protocol["tolerances"]["refinement_ratio_max"] * voltage_errors[0]
            + protocol["tolerances"]["refinement_floor_V"],
            "Coupled voltage refinement failed",
        )
    u.write(
        directory / "checks.json",
        {"case": case, "runs": reports, "reference_difference": reference_error},
    )
    return {"case": case, "runs": reports, "reference_difference": reference_error}


def batch_definition(protocol, backend):
    """Reusable resource preflight and execution definition for four distinct worlds."""
    worlds = []
    for i in range(4):
        raw = fixtures.definition("network_mixed", protocol, backend=backend, end=0.002)
        raw["execution"]["channel_capacity"] = 2
        for edge in raw["model"]["junctions"]:
            edge["gate"]["threshold_voltage_V"] += i * 0.001
        if i == 3:
            raw = fixtures.with_membrane_processes(raw)
        worlds.append(WorldSpec(i + 1, parse_spec(raw)))
    return BatchSpec(tuple(worlds), 4, 100000, 536870912)


def check_batch(protocol, directory, backend):
    """Heterogeneous ordinary-world batch, including active pump/channel composition."""
    directory.mkdir()
    spec = batch_definition(protocol, backend)
    worlds = spec.worlds
    u.write(directory / "batch.json", spec.to_dict())
    result = run_batch(spec)
    checkpoints = {}
    for identity, world in result.worlds.items():
        path = directory / f"world-{identity}"
        path.mkdir()
        np.savez_compressed(path / "trajectory.npz", times_s=world.times, **world.history._asdict())
        write_snapshot(path / "restart", world.spec, world.checkpoint_at(0.001))
        saved = load_snapshot(path / "restart")
        checkpoints[identity] = saved.checkpoint
    resumed = run_batch(spec, checkpoints)
    for identity, world in resumed.worlds.items():
        for suffix, full in zip(world.history, result.worlds[identity].history, strict=True):
            np.testing.assert_array_equal(suffix, full[checkpoints[identity].step_index :])
    max_partition_error = 0.0
    for group in (worlds[:2], worlds[2:]):
        part = run_batch(BatchSpec(tuple(group), 2, 100000, 536870912))
        for identity, world in part.worlds.items():
            for a, b in zip(world.history, result.worlds[identity].history, strict=True):
                max_partition_error = max(
                    max_partition_error, float(np.max(np.abs(a - b), initial=0))
                )
                np.testing.assert_allclose(
                    a, b, atol=protocol["tolerances"]["cpu_gpu_atol"], rtol=0
                )
    composed = result.worlds[4]
    u.need(
        np.any(composed.history.pump_cycles[-1])
        and np.any(composed.history.channel_transferred[-1])
        and np.any(composed.history.junction_transferred[-1]),
        "Composed processes inactive",
    )
    report = {
        "backend": backend,
        "worlds": 4,
        "batch_disk_restart_exact": True,
        "max_partition_error": max_partition_error,
        "pump_channel_junction_composition": True,
    }
    u.write(directory / "checks.json", report)
    return {i: w.history for i, w in result.worlds.items()}, report


def check(output):
    protocol = u.read(output / "protocol.json")
    runtime = u.runtime()
    comparison = output / "comparison"
    comparison.mkdir()
    cases = []
    for case in protocol["cases"]:
        cases.append(check_case(case, protocol, comparison / case))
        print(case, "CPU/L4 reference/restart comparisons passed", flush=True)
        u.budget(output)
    histories, batches = {}, []
    for backend in ("cpu", "gpu"):
        histories[backend], report = check_batch(
            protocol, comparison / (backend + "-batch"), backend
        )
        batches.append(report)
    maximum_batch_error = 0.0
    for identity in histories["cpu"]:
        for a, b in zip(histories["cpu"][identity], histories["gpu"][identity], strict=True):
            maximum_batch_error = max(maximum_batch_error, float(np.max(np.abs(a - b), initial=0)))
            np.testing.assert_allclose(a, b, atol=protocol["tolerances"]["cpu_gpu_atol"], rtol=0)
    u.need(runtime == u.runtime(), "Coupled checker runtime changed")
    return {
        "status": "physical_time_junction_coupled_cpu_gpu_pass",
        "model": protocol["model"],
        "cases": cases,
        "batches": batches,
        "max_batch_cpu_gpu_error": maximum_batch_error,
        "runtime": runtime,
        "comparison_files_sha256": u.inventory(comparison),
        "scope": protocol["scope"],
        "full_betse_parity": False,
        "biological_validation": False,
        "gpu_throughput_qualified": False,
        "multi_gpu_scaling": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    u.write(args.output / "comparison-result.json", check(args.output))
