"""Bounded unmodified native adaptive-Euler paths, with actual accepted clocks.

No imports of zombie, Cells, or the continuing research harness. Uses the existing
optional reference environment. The default 60-second process budget can be
explicitly raised to 180 seconds with a recorded resource-only justification.
"""

import argparse
import inspect
import json
import os
import platform
import subprocess
import sys
import zipfile
from importlib import metadata
from pathlib import Path

from capture_source_pair_reference import check_preparation, provenance, sha
from source_pair_native_protocol import native_plan

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/source_emt_pair_panel_v1.json"
PROTOCOL = ROOT / "configs/reference/source_emt_pair_numerics_v1.json"
FIXTURE = ROOT / "tests/fixtures/source_pair_probes.json"


def write_json(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def worker(source, output, case_id, level_name, extension=None):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / "cancer_GJ_sims"), str(source)]
    import GJ_lib
    import GRN_miRNA as grn
    import numpy as np
    import sim

    panel, protocol = json.loads(PANEL.read_text()), json.loads(PROTOCOL.read_text())
    cases, levels = native_plan(extension)
    case = next(c for c in cases if c["id"] == case_id)
    level = next(c for c in levels if c["name"] == level_name)
    p = sim.Params()
    if any(getattr(p, name) != value for name, value in panel["parameters"].items()):
        raise ValueError("Unexpected source constants")
    p.time_step = level["time_step"]
    p.sim_integ_max_delt_Vm = level["max_delta_voltage"]
    p.sim_integ_max_delt_cc = level["max_fractional_concentration"]
    p.no_dumps = True
    if (
        grn.ITERATE
        or grn.MIR200_TGT != -1
        or grn.miR200_valence != -1
        or not grn.miR200_is_medium_size
    ):
        raise ValueError("Unexpected source GRN profile")
    sim.init_big_arrays(2, 1, p, extra_ions=grn.extra_ions() + ("ST",))
    grn.build_GRN(None)
    sim.GJ_diffusion[sim.ion_i["ST"]] = 0
    primary = [sim.ion_i[name] for name in panel["primary_rows"]]
    fixed = [sim.ion_i[name] for name in panel["context_rows"]]
    derived = list(range(grn.miR200_free, grn.bound0 + 7))
    if case["initial"] == "prepared":
        for cell, data in enumerate(panel["preparation"]["cells"]):
            for name, value in data["raw_packet"].items():
                sim.cc_cells[sim.ion_i[name], cell] = value
    else:
        initial = panel["constructed_initials"][case["initial"]]
        sim.cc_cells[primary] = initial["primary"]
        sim.cc_cells[fixed] = initial["context"]
    fixed_values = sim.cc_cells[fixed].copy()
    sim.GJ_connects["from"], sim.GJ_connects["to"] = case.get("edge", [0, 1])
    sim.Dm_array[:3] = case.get("membrane_diffusion", panel["membrane_diffusion"])
    sim.cc_env[:3] = panel["bath_ions"]

    class PrescribedLeak(sim.Gate):
        def __init__(self, row):
            super().__init__(dest=self.GATE_IC, out_ion=row)
            self.values = np.ones(2)

        def func(self, cc, vm, delta_v, time):
            return self.values

    leaks = [PrescribedLeak(row) for row in range(3)]
    if case["gate"] is not None:
        if list(GJ_lib.Chen_Izu_params[case["gate"]]) != panel["gate_parameters"][case["gate"]]:
            raise ValueError("Unexpected source gate parameters")
        gate = GJ_lib.GJ_gate(case["gate"])
        grn.set_GJ_diffusions(gate)
        if case.get("swap_hemichannels", False):
            gate.A1, gate.A2 = gate.A2.copy(), gate.A1.copy()
            gate.VO1, gate.VO2 = gate.VO2.copy(), gate.VO1.copy()
    controls = panel["default_controls"] | case.get("controls", {})
    phases = [{"time": 0.0, "set": {}}] + case.get("events", [])
    ends = [phase["time"] for phase in phases[1:]] + [case["end_time"]]
    actual_start, total_steps = 0.0, 0
    records = []
    lines, first_line = inspect.getsourcelines(sim.sim)

    def source_line(statement):
        found = [first_line + i for i, line in enumerate(lines) if line.strip() == statement]
        if len(found) != 1:
            raise ValueError("Pinned source observation boundary changed")
        return found[0]

    raw_line = source_line("slew_cc = sim_slopes(t)")
    update_line = source_line("cc_cells += slew_cc * n_steps * time_step")
    for phase_index, (phase, requested_end) in enumerate(zip(phases, ends, strict=True)):
        controls.update(phase["set"])
        for row, leak in enumerate(leaks):
            leak.values = np.asarray(controls["leak"][row])
        sim.pump_scaling[:] = controls["pump"]
        sim.GJ_diffusion[:3, 0] = (
            np.asarray(panel["junction_ion_diffusion"]) * controls["ion_contact"]
        )
        grn.set_GJdiff(panel["junction_mirna_diffusion"] * controls["mirna_contact"])
        before_probe = sim.cc_cells.copy()
        probe = sim.sim_slopes(0)
        np.testing.assert_array_equal(sim.cc_cells[primary], before_probe[primary])
        if phase_index == 0:
            frozen = next(
                r
                for r in json.loads(FIXTURE.read_text())["probes"]["records"]
                if r["case_id"] == case_id and r["control_time"] == 0
            )
            np.testing.assert_allclose(probe, frozen["native_packet_rate"], atol=5e-12, rtol=2e-12)
        # This explicit cache refresh does not alter evolving/fixed coordinates.
        initial_packet = sim.cc_cells.copy()
        times, raw, caches, rates, counts = [], [], [], [], []
        captured = {}
        max_steps = protocol["native_limits"]["steps_per_case"]

        def watch(
            frame,
            event,
            returned,
            *,
            times=times,
            raw=raw,
            caches=caches,
            rates=rates,
            counts=counts,
            captured=captured,
            max_steps=max_steps,
        ):
            nonlocal total_steps
            if event == "line":
                if frame.f_lineno == raw_line:
                    total_steps += 1
                    if total_steps > max_steps:
                        raise ValueError("Native step budget exceeded")
                    times.append(float(frame.f_locals["t"]))
                    raw.append(sim.cc_cells.copy())
                elif frame.f_lineno == update_line:
                    if not np.array_equal(sim.cc_cells[primary], raw[-1][primary]):
                        raise ValueError("Native RHS changed primary state")
                    if not np.array_equal(sim.cc_cells[fixed], fixed_values):
                        raise ValueError("Native RHS changed fixed context")
                    if not np.isfinite(sim.cc_cells).all() or np.any(sim.cc_cells < 0):
                        raise ValueError("Invalid native refreshed state")
                    if np.any(sim.z_array[4:]) or np.any(sim.GJ_diffusion[4:]):
                        raise ValueError("Native temporary GRN parameters not restored")
                    derivative = frame.f_locals["slew_cc"]
                    if np.any(np.delete(derivative, primary, axis=0)):
                        raise ValueError("Unexpected non-primary native RHS")
                    caches.append(sim.cc_cells[derived].copy())
                    rates.append(derivative[primary].copy())
                    counts.append(int(frame.f_locals["n_steps"]))
            elif event == "return":
                captured["time"] = float(frame.f_locals["t"])
                captured["packet"] = sim.cc_cells.copy()
            return frame.f_trace

        def dispatch(frame, event, returned, callback=watch):
            return callback if frame.f_code is sim.sim.__code__ else None

        print(f"Starting {case_id}/{level_name} phase {phase_index}", flush=True)
        sys.settrace(dispatch)
        try:
            sample_times, sample_packets = sim.sim(requested_end - phase["time"])
        finally:
            sys.settrace(None)
        if (
            captured["time"] < requested_end - phase["time"]
            or actual_start + captured["time"] > protocol["native_limits"]["max_total_clock"]
        ):
            raise ValueError("Unexpected native accepted clock")
        final = captured["packet"]
        np.testing.assert_array_equal(final[fixed], fixed_values)
        if not np.isfinite(final).all() or np.any(final < 0):
            raise ValueError("Invalid native final packet")
        path = output / f"phase-{phase_index}.npz"
        with path.open("xb") as handle:
            np.savez_compressed(
                handle,
                incoming_packet=before_probe,
                initial_packet=initial_packet,
                start_times=np.asarray(times),
                raw_start_packets=np.asarray(raw),
                refreshed_caches=np.asarray(caches),
                primary_slopes=np.asarray(rates),
                step_multiples=np.asarray(counts),
                final_packet=final,
                sample_times=np.asarray(sample_times),
                sample_packets=np.asarray(sample_packets),
            )
        records.append(
            {
                "index": phase_index,
                "requested_start": phase["time"],
                "requested_end": requested_end,
                "actual_start": actual_start,
                "actual_end": actual_start + captured["time"],
                "local_accepted_time": captured["time"],
                "last_sample_time": float(sample_times[-1]),
                "steps": len(times),
                "controls": json.loads(json.dumps(controls)),
                "payload": path.name,
                "sha256": sha(path),
            }
        )
        actual_start += captured["time"]
    result = {
        "status": "pass",
        "case": case,
        "level": level,
        "row_names": list(sim.ion_i),
        "phases": records,
        "steps": total_steps,
        "initial_probe_matches_frozen_fixture": True,
        "observer": "read_only_source_loop_line_trace",
    }
    write_json(output / "result.json", result)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--worker", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--level")
    parser.add_argument("--native-extension", type=Path)
    parser.add_argument(
        "--runs", nargs="+", help="optional exact case-level identifiers for bounded recapture"
    )
    parser.add_argument("--worker-timeout", type=int, choices=(60, 180))
    parser.add_argument("--budget-note")
    args = parser.parse_args()
    if args.worker:
        worker(args.source.resolve(), args.output, args.case, args.level, args.native_extension)
        return 0
    if args.output.exists():
        parser.error("Output must be new")
    panel, protocol = json.loads(PANEL.read_text()), json.loads(PROTOCOL.read_text())
    cases, levels = native_plan(args.native_extension)
    available = {f"{c['id']}-{level['name']}" for c in cases for level in levels}
    if args.runs is not None and (
        len(set(args.runs)) != len(args.runs) or set(args.runs) - available
    ):
        raise ValueError("Unknown or duplicated native recapture target")
    timeout = args.worker_timeout or protocol["native_limits"]["worker_timeout_seconds"]
    if timeout != protocol["native_limits"]["worker_timeout_seconds"] and not args.budget_note:
        raise ValueError("A resource-only budget change requires a recorded justification")
    if sha(PANEL) != protocol["panel_sha256"]:
        raise ValueError("Frozen panel changed")
    source = args.source.resolve()
    before = provenance(source)
    prepared = check_preparation(panel)
    args.output.mkdir(parents=True)
    names = [
        "scripts/capture_source_pair_trajectories.py",
        "scripts/source_pair_native_protocol.py",
        "scripts/capture_source_pair_reference.py",
        "scripts/capture_contact_reference.py",
        "scripts/capture_emt_reference.py",
        "configs/reference/source_emt_pair_panel_v1.json",
        "configs/reference/source_emt_pair_numerics_v1.json",
        "tests/fixtures/source_pair_probes.json",
        "requirements-reference.txt",
    ]
    if args.native_extension is not None:
        names.append(str(args.native_extension.resolve().relative_to(ROOT)))
    hashes = {name: sha(ROOT / name) for name in names}
    with zipfile.ZipFile(
        args.output / "capture_sources.zip", "x", compression=zipfile.ZIP_DEFLATED
    ) as capsule:
        for name in names:
            capsule.write(ROOT / name, name)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLBACKEND": "Agg",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
        }
    )
    results = {}
    for case in cases:
        for level in levels:
            name = f"{case['id']}-{level['name']}"
            if args.runs is not None and name not in args.runs:
                continue
            print(name, flush=True)
            output = args.output / name
            output.mkdir()
            env["MPLCONFIGDIR"] = str(output.resolve() / "matplotlib-cache")
            with (output / "native.log").open("x") as log:
                try:
                    subprocess.run(
                        [
                            sys.executable,
                            str(Path(__file__).resolve()),
                            str(source),
                            "--output",
                            str(output.resolve()),
                            "--worker",
                            "--case",
                            case["id"],
                            "--level",
                            level["name"],
                        ]
                        + (
                            []
                            if args.native_extension is None
                            else ["--native-extension", str(args.native_extension.resolve())]
                        ),
                        env=env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.DEVNULL,
                        timeout=timeout,
                        check=True,
                    )
                    results[name] = {"status": "pass", "result_sha256": sha(output / "result.json")}
                except (subprocess.SubprocessError, OSError) as error:
                    results[name] = {"status": "failed_worker", "error": str(error)}
                    write_json(output / "failure.json", results[name])
    if provenance(source) != before or any(
        sha(ROOT / name) != value for name, value in hashes.items()
    ):
        raise ValueError("Source or capture inputs changed")
    result = {
        "status": "pass"
        if all(r["status"] == "pass" for r in results.values())
        else "capture_incomplete",
        "scope": "native source trajectories; independent numerical comparison not yet applied",
        **before,
        "preparation_audit": prepared,
        "capture_source_hashes": hashes,
        "python": platform.python_version(),
        "packages": {name: metadata.version(name) for name in ("numpy", "scipy", "matplotlib")},
        "runs": results,
        "actual_worker_timeout_seconds": timeout,
        "resource_budget_note": args.budget_note,
    }
    write_json(args.output / "verification.json", result)
    print(result["status"], flush=True)
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
