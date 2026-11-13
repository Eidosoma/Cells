"""Cost and step studies of resolved_pump_tissue@3 (channel populations, IMEX).

Parts (each writes <part>-<backend>.json in --output):
  cost      runner wall time per step at 825 nodes (validation/tissue/
            resolved_scale_world.py: 225 cells, 600 outside nodes) with NaV1.2
            and Kir2.1 on every patch (the heredity parameter set), against the
            same world with no channels; compile, analysis and peak memory.
  write     heredity single cell (validation/tissue/surface_pump_v3_fixtures.py):
            an H->D write by a Na-leak cue, successive refinement 4-0.125 ms
            (finest level as reference), the first 12 ms against RK4, and the
            ledger diagnostics of each run.
  tissue    825-node world with channels: dt 2, 1 and 0.5 ms against 0.25 ms
            over a short window from the electroneutral start.
  charge    global-charge residual against its scaled bound over 20 s of
            steady H and D cells at 1 ms (no runner history).
Usage:
  python -m validation.tissue.surface_pump_v3_study PART [PART ...] --output DIR
      [--backend cpu|gpu] [--quick]
"""

import argparse
import json
import resource
import time
import traceback
from pathlib import Path

import jax
import numpy as np

jax.config.update("jax_enable_x64", True)

from cells.core.runner import run  # noqa: E402
from cells.core.specs import parse_spec  # noqa: E402
from cells.core.surface_pump_v3_spec import (  # noqa: E402
    KIR2P1_LAW_ID,
    NALEAK_LAW_ID,
    NAV1P2_LAW_ID,
)
from validation.tissue import resolved_scale_world as world  # noqa: E402
from validation.tissue import surface_pump_v3_fixtures as fixtures  # noqa: E402

ARS = "imex_ars222_face_electromigration@1"
NA_LEAK_SCALE = 0.2  # Heredity pre-screen: Na leak x0.2 of BETSE's default.


def tissue_definition(
    *,
    dt,
    end_time,
    channels=True,
    backend="cpu",
    observation_times=None,
    field_solver="capacitive_reduction_gauged_damped_newton@2",
):
    """The 825-node scale world as @3, with NaV1.2 and Kir2.1 on every patch.

    field_solver: as resolved_scale_world.definition (default: version 2, as before D147).
    """
    raw = world.definition(
        dt=dt,
        end_time=end_time,
        solver=ARS,
        backend=backend,
        observation_times=observation_times,
        field_solver=field_solver,
    )
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    m["id"] = "resolved_pump_tissue@3"
    for p in m["membranes"]:
        p["calcium_pump"] = None
        p["permeability_m_per_s"]["Na"] *= NA_LEAK_SCALE
    e["calcium_pump_controls"] = []
    kir, nav = fixtures.steady_gates(0.0)  # Every compartment starts electroneutral.
    m["channels"] = []
    if channels:
        for p in m["membranes"]:
            k = p["id"].split("_")[1]
            for name, law, ion, permeability, gate in (
                ("kir", KIR2P1_LAW_ID, "K", fixtures.HEREDITY_KIR_M_S, kir),
                ("nav", NAV1P2_LAW_ID, "Na", fixtures.HEREDITY_NAV_M_S, nav),
            ):
                m["channels"].append(
                    dict(
                        id=f"{name}_{k}",
                        membrane_id=p["id"],
                        kinetic_law=law,
                        max_permeability_m_per_s=permeability,
                        abundance=1.0,
                        initial_gate=list(gate),
                        permeant_ions=[dict(species_id=ion, relative_permeability=1.0)],
                    )
                )
    e["channel_controls"] = [
        dict(channel_id=c["id"], schedule=[dict(time=0.0, availability=1.0)]) for c in m["channels"]
    ]
    x["channel_capacity"] = len(m["channels"])
    return raw


def part_cost(args):
    report = {}
    device = jax.devices(args.backend)[0]
    end = 0.02 if args.quick else 0.2
    cases = (("channels", True), ("no_channels", False))
    for label, channels in (c for c in cases if c[0] in args.cases.split(",")):
        spec = parse_spec(
            tissue_definition(
                dt=1e-3,
                end_time=end,
                channels=channels,
                backend=args.backend,
                observation_times=[0.0, end],
            )
        )
        if args.backend == "gpu":
            device.memory_stats()  # Ensure the allocator is initialized.
        value = run(spec)
        steps = len(value.times) - 1
        entry = dict(
            steps=steps,
            nodes=len(spec.model.cells) + len(spec.model.extracellular),
            patches=len(spec.model.membranes),
            channel_populations=len(spec.model.channels),
            timings=value.timings,
            execute_ms_per_step=1e3 * value.timings["execute_seconds"] / steps,
            analysis_ms_per_row=1e3 * value.timings["analysis_seconds"] / (steps + 1),
            diagnostics=value.diagnostics,
            final_vm_range_mV=[
                float(1e3 * np.min(value.observations.membrane_voltage_V[-1])),
                float(1e3 * np.max(value.observations.membrane_voltage_V[-1])),
            ],
            peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
        )
        if args.backend == "gpu":
            entry["gpu_peak_bytes"] = device.memory_stats().get("peak_bytes_in_use")
        report[label] = entry
        write(args, "cost", report)
        np.savez_compressed(
            Path(args.output) / f"cost-final-{args.backend}-{label}.npz",
            **{k: np.asarray(v) for k, v in value.final.state._asdict().items()},
        )


def write_definition(dt, *, end_time, solver=ARS, backend="cpu", times=None, cue=(0.05, 0.35)):
    """Heredity cell at H with a 9x Na-leak cue on [cue[0], cue[1]) s within the horizon."""
    h = fixtures.HEREDITY_STATES["H"]
    raw = fixtures.heredity_cells(
        [h[:4]], dt=dt, end_time=end_time, solver=solver, backend=backend,
        observation_times=times,
    )  # fmt: skip
    raw["model"]["channels"].append(
        dict(
            id="cue_0",
            membrane_id="membrane_0",
            kinetic_law=NALEAK_LAW_ID,
            max_permeability_m_per_s=9 * fixtures.HEREDITY_PERMEABILITY["Na"],
            abundance=1.0,
            initial_gate=[],
            permeant_ions=[dict(species_id="Na", relative_permeability=1.0)],
        )
    )
    changes = [(0.0, 0.0), (cue[0], 1.0), (cue[1], 0.0)]
    schedule = {}
    for time_s, level in changes:
        if time_s <= end_time:
            schedule[time_s] = level  # A cue from t = 0 replaces the initial level.
    raw["experiment"]["channel_controls"].append(
        dict(
            channel_id="cue_0",
            schedule=[dict(time=t, availability=v) for t, v in sorted(schedule.items())],
        )
    )
    raw["execution"]["channel_capacity"] += 1
    return raw


def grid_times(dt, until, every=0.004):
    """Observation times every 4 ms as the accepted products i * dt (EventGrid)."""
    stride, steps = round(every / dt), round(until / dt)
    return [i * dt for i in range(0, steps, stride)] + [until]


def part_write(args):
    """Successive refinement 4 ms -> 0.125 ms; the finest level is the reference.

    A much finer IMEX reference (15.625 us, 64,000 steps) fails the family's
    scaled global-charge bound (write-cpu-02): the residual grows with the
    number of steps taken through a transient while the bound grows only with
    the moved charge (part "charge": steady cells do not accumulate it). The
    levels are instead checked against RK4 (2.5 us) on the first 12 ms of a
    cue switched on at t = 0, where every run is short.
    """
    end = 0.2 if args.quick else 1.0
    steps = (4e-3, 2e-3, 1e-3, 5e-4, 2.5e-4, 1.25e-4)
    report = dict(end_time_s=end, observation_step_s=0.004, steps_s=list(steps))

    def trial(dt, solver=ARS, until=end, cue=(0.05, 0.35)):
        started = time.perf_counter()
        times = grid_times(dt, until)
        raw = write_definition(dt, end_time=until, solver=solver, times=times, cue=cue)
        value = run(parse_spec(raw))
        vm = np.asarray(value.observations.membrane_voltage_V[:, 0])
        return value, vm, time.perf_counter() - started

    early = {}
    for label, dt, solver in (
        ("rk4_2.5us", 2.5e-6, "rk4"),
        ("ars_15.625us", 1.5625e-5, ARS),
        ("ars_0.125ms", 1.25e-4, ARS),
        ("ars_1ms", 1e-3, ARS),
    ):
        value, vm, wall = trial(dt, solver=solver, until=0.012, cue=(0.0, 1.0))
        early[label] = vm
        report.setdefault("first_12ms", {})[label] = dict(
            wall_s=wall, diagnostics=value.diagnostics, vm_mV=list(1e3 * vm)
        )
    for label in ("ars_15.625us", "ars_0.125ms", "ars_1ms"):
        report["first_12ms"][label]["max_abs_dvm_vs_rk4_V"] = float(
            np.max(np.abs(early[label] - early["rk4_2.5us"]))
        )
    write(args, "write", report)
    vms = {}
    for dt in steps:
        try:
            value, vm, wall = trial(dt)
            vms[dt] = vm
            report[str(dt)] = dict(
                status="ok",
                wall_s=wall,
                final_vm_mV=float(1e3 * vm[-1]),
                vm_mV=list(1e3 * vm),
                diagnostics=value.diagnostics,
            )
        except Exception as error:  # A refusal is a result.
            report[str(dt)] = dict(status="failed", error=f"{type(error).__name__}: {error}")
        write(args, "write", report)
    ok = [dt for dt in steps if dt in vms]
    finest = ok[-1]
    for dt in ok[:-1]:
        error = np.abs(vms[dt] - vms[finest])
        report[str(dt)].update(
            reference_dt_s=finest,
            max_abs_dvm_V=float(np.max(error)),
            final_abs_dvm_V=float(error[-1]),
        )
    differences = [float(np.max(np.abs(vms[a] - vms[b]))) for a, b in zip(ok, ok[1:], strict=False)]
    labels = [str(dt) for dt in ok[:-1]]
    report["successive_max_abs_dvm_V"] = dict(zip(labels, differences, strict=True))
    report["observed_orders"] = [
        float(np.log2(a / b)) for a, b in zip(differences, differences[1:], strict=False) if b > 0
    ]
    write(args, "write", report)


def part_tissue(args):
    end = 0.01 if args.quick else 0.05
    report = dict(end_time_s=end)
    values = {}
    for dt in (2.5e-4, 5e-4, 1e-3, 2e-3):
        times = [0.0, round(end / 2 / dt) * dt, end]  # Accepted products i * dt.
        try:
            started = time.perf_counter()
            spec = parse_spec(
                tissue_definition(
                    dt=dt, end_time=end, backend=args.backend, observation_times=times
                )
            )
            value = run(spec)
            values[dt] = np.asarray(value.observations.membrane_voltage_V)
            report[str(dt)] = dict(
                status="ok",
                wall_s=time.perf_counter() - started,
                execute_ms_per_step=1e3 * value.timings["execute_seconds"] / (len(value.times) - 1),
                diagnostics=value.diagnostics,
            )
            np.save(Path(args.output) / f"tissue-vm-{args.backend}-{dt}.npy", values[dt])
            if dt != 2.5e-4 and 2.5e-4 in values:  # Each level against 0.25 ms as it ends.
                report[str(dt)]["max_abs_dvm_V_vs_0.25ms"] = float(
                    np.max(np.abs(values[dt] - values[2.5e-4]))
                )
        except Exception as error:
            report[str(dt)] = dict(status="failed", error=f"{type(error).__name__}: {error}")
        write(args, "tissue", report)


def part_charge(args):
    """Global-charge residual against its scaled bound in steady H and D cells.

    Steps the IMEX scheme directly (no runner history) for 20 s at 1 ms and
    evaluates balances() every second. At a steady state the moved charge,
    and so the bound, stops growing while per-step rounding accumulates.
    """
    import jax.numpy as jnp

    from cells.core.surface_pump_v3_spec import control_values
    from cells.models import surface_pump_v3 as model

    dt, chunk = 1e-3, 1000
    seconds = 2 if args.quick else 20
    states = fixtures.HEREDITY_STATES
    raw = fixtures.heredity_cells(
        [states["H"][:4], states["D"][:4]], dt=dt, end_time=seconds, backend=args.backend
    )
    spec = parse_spec(raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    control = type(controls)(*(v[0] for v in controls))
    device = jax.devices(args.backend)[0]
    state, p, control = jax.device_put((state, p, control), device)

    @jax.jit
    def advance(y):
        def body(carry, _):
            value, ok = carry
            new, valid = model.checked_step(value, dt, control, p, p.active)
            return (new, ok & valid), None

        return jax.lax.scan(body, (y, jnp.asarray(True)), None, length=chunk)[0]

    host = type(p)(*(np.asarray(v) for v in p))
    rows = []
    for k in range(seconds):
        state, ok = advance(state)
        row = model.STATE_TYPE(*(np.asarray(v) for v in state))
        b = model.balances(row, host)
        bound = float(model.global_charge_bound(row, host))
        rows.append(
            dict(
                time_s=(k + 1) * chunk * dt,
                steps_valid=bool(ok),
                global_charge_C=float(b["global_charge"]),
                bound_C=bound,
                ratio=abs(float(b["global_charge"])) / bound,
                capacitor_charge_max_C=float(np.max(np.abs(b["charge"]))),
            )
        )
        write(args, "charge", dict(dt_s=dt, cells=["H", "D"], rows=rows))


def write(args, name, report):
    suffix = "" if name != "cost" or args.cases == "channels,no_channels" else "-" + args.cases
    path = Path(args.output) / f"{name}-{args.backend}{suffix}.json"
    path.write_text(json.dumps(report, indent=2, default=float) + "\n")


PARTS = dict(cost=part_cost, write=part_write, tissue=part_tissue, charge=part_charge)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("parts", nargs="+", choices=sorted(PARTS))
    parser.add_argument("--output", required=True)
    parser.add_argument("--backend", choices=("cpu", "gpu"), default="cpu")
    parser.add_argument("--quick", action="store_true", help="short windows to smoke-test parts")
    parser.add_argument(
        "--cases",
        default="channels,no_channels",
        help="cost cases in order; one per process separates first-compile autotuning",
    )
    args = parser.parse_args()
    Path(args.output).mkdir(parents=True, exist_ok=True)
    status = {}
    for name in args.parts:
        started = time.perf_counter()
        try:
            PARTS[name](args)
            status[name] = dict(status="completed", seconds=time.perf_counter() - started)
        except Exception as error:  # Preserve the failure and continue with other parts.
            status[name] = dict(
                status="failed",
                seconds=time.perf_counter() - started,
                error=repr(error),
                traceback=traceback.format_exc(),
            )
        print(json.dumps({name: status[name]["status"]}), flush=True)
        if status[name]["status"] == "failed":
            print(status[name]["traceback"], flush=True)
    outcome = "failure" if any(v["status"] == "failed" for v in status.values()) else "result"
    summary = dict(
        parts=status,
        backend=args.backend,
        argv=vars(args),
        peak_rss_MiB=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024,
    )
    (Path(args.output) / f"{outcome}-{args.backend}.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n"
    )


if __name__ == "__main__":
    main()
