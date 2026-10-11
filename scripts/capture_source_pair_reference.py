"""Capture complete instantaneous BITSEY pair RHS probes, not trajectories.

Use the optional reference environment and the clean pinned checkout. No zombie
or continuing-research harness imports, integration, source edits, or vendoring.
"""

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from importlib import metadata
from pathlib import Path

from capture_contact_reference import provenance

ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "configs/reference/source_emt_pair_panel_v1.json"
MARKER = "CELLS_SOURCE_PAIR_JSON "


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_preparation(panel):
    """Validate the retained numeric packets against the previous native receipt."""
    prep = panel["preparation"]
    original_path = ROOT / prep["capture"]
    if sha(original_path) != prep["capture_sha256"]:
        raise ValueError("Previous preparation capture changed")
    original = json.loads(original_path.read_text())
    if original["revision"] != panel["source_revision"]:
        raise ValueError("Preparation revision differs")
    for retained, name in zip(prep["cells"], ("e", "m"), strict=True):
        native = original["cases"][name]
        comparisons = {
            "raw_packet": "accepted_full_state",
            "label": "accepted_label",
            "accepted_time": "accepted_time",
            "last_sample_time": "last_sample_time",
            "seed_regulation": "initial",
        }
        if any(retained[key] != native[value] for key, value in comparisons.items()):
            raise ValueError("Prepared packet/clock is not the retained native result")
        if prep["settings"] != native["source_settings"]:
            raise ValueError("Preparation numerical settings differ")
        if prep["requested_end_time"] != native["requested_end_time"]:
            raise ValueError("Preparation requested horizon differs")
    return {"capture_sha256": sha(original_path), "complete_packets_exact": True}


def worker(source, panel):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / "cancer_GJ_sims"), str(source)]
    import GJ_lib
    import GRN_miRNA as grn
    import numpy as np
    import sim
    import sim_toolbox as stb

    if grn.ITERATE or grn.MIR200_TGT != -1 or grn.miR200_valence != -1:
        raise ValueError("Unexpected regulatory approximation or transport valence")
    if not grn.miR200_is_medium_size or grn.Snail_input_conc != 72:
        raise ValueError("Unexpected regulatory profile")

    class PrescribedLeak(sim.Gate):
        # Caller-supplied constant controls, not a replacement for source physics.
        def __init__(self, row, values):
            super().__init__(dest=self.GATE_IC, out_ion=row)
            self.values = values

        def func(self, cc, vm, delta_v, time):
            return self.values

    records = []
    for case in panel["cases"]:
        controls = dict(panel["default_controls"])
        controls.update(case.get("controls", {}))
        phases = [{"time": 0.0, "set": {}}] + case.get("events", [])
        for phase in phases:
            controls.update(phase["set"])
            p = sim.Params()
            if any(getattr(p, name) != value for name, value in panel["parameters"].items()):
                raise ValueError("Panel constants are not the pinned source defaults")
            p.no_dumps = True
            sim.init_big_arrays(2, 1, p, extra_ions=grn.extra_ions() + ("ST",))
            grn.build_GRN(None)
            sim.GJ_diffusion[sim.ion_i["ST"]] = 0
            edge = case.get("edge", [0, 1])
            sim.GJ_connects["from"], sim.GJ_connects["to"] = edge
            primary_rows = [sim.ion_i[name] for name in panel["primary_rows"]]
            context_rows = [sim.ion_i[name] for name in panel["context_rows"]]
            if case["initial"] == "prepared":
                for cell, prepared in enumerate(panel["preparation"]["cells"]):
                    for name, value in prepared["raw_packet"].items():
                        sim.cc_cells[sim.ion_i[name], cell] = value
            else:
                initial = panel["constructed_initials"][case["initial"]]
                sim.cc_cells[primary_rows] = initial["primary"]
                sim.cc_cells[context_rows] = initial["context"]
            # Finite but deliberately wrong plotting caches. The full native RHS
            # must refresh these from primary state before the miRNA flux call.
            sim.cc_cells[grn.miR200_free : grn.bound0 + 7] = np.arange(16).reshape(8, 2) + 700
            before = sim.cc_cells.copy()
            sim.Dm_array[:3] = case.get("membrane_diffusion", panel["membrane_diffusion"])
            sim.cc_env[:3] = panel["bath_ions"]
            sim.pump_scaling[:] = controls["pump"]
            sim.GJ_diffusion[:3, 0] = (
                np.asarray(panel["junction_ion_diffusion"]) * controls["ion_contact"]
            )
            grn.set_GJdiff(panel["junction_mirna_diffusion"] * controls["mirna_contact"])
            for row, values in enumerate(controls["leak"]):
                if values != [1.0, 1.0]:
                    PrescribedLeak(row, np.asarray(values))
            if case["gate"] is not None:
                if (
                    list(GJ_lib.Chen_Izu_params[case["gate"]])
                    != panel["gate_parameters"][case["gate"]]
                ):
                    raise ValueError("Gate constants differ from pinned source")
                gate = GJ_lib.GJ_gate(case["gate"])
                grn.set_GJ_diffusions(gate)
                if case.get("swap_hemichannels", False):
                    gate.A1, gate.A2 = gate.A2.copy(), gate.A1.copy()
                    gate.VO1, gate.VO2 = gate.VO2.copy(), gate.VO1.copy()
            parameter_arrays = [a.copy() for a in (sim.Dm_array, sim.z_array, sim.GJ_diffusion)]
            rate = sim.sim_slopes(phase["time"])
            after = sim.cc_cells.copy()
            repeated = sim.sim_slopes(phase["time"] + 19.0)
            vm = sim.compute_Vm(sim.cc_cells)
            delta = vm[edge[0] : edge[0] + 1] - vm[edge[1] : edge[1] + 1]
            # Independently expose native contributions alongside sim_slopes.
            leak = stb.GHK(sim.cc_env, sim.cc_cells, sim.Dm_array, sim.z_array, vm, p)
            for g in sim.IC_gates:
                leak[g.out_ion] *= g.func(sim.cc_cells, vm, delta, phase["time"])
            na, potassium = stb.pumpNaKATP(
                sim.cc_cells[0],
                sim.cc_env[0],
                sim.cc_cells[1],
                sim.cc_env[1],
                vm,
                p.T,
                p,
                sim.pump_scaling,
            )
            pump = np.zeros_like(rate)
            pump[:2] = np.array([na, potassium]) * np.any(sim.Dm_array > 0, axis=0)
            local = np.zeros_like(rate)
            for g in sim.GD_gates:
                local[g.out_ion, :] += g.func(sim.cc_cells, vm, delta, phase["time"])
            ith, gth = sim.GJ_norton(delta)
            junction = ith + delta * gth
            for g in sim.GJ_add_gates:
                junction[g.out_ion] += g.func(sim.cc_cells, vm, delta, phase["time"])
            scales = np.ones_like(junction)
            for g in sim.GJ_scale_gates:
                scales *= g.func(sim.cc_cells, vm, delta, phase["time"])
            junction *= scales
            excluded = after.copy()
            excluded[primary_rows[3:]] += 111
            excluded[grn.miR200_free] += 111
            records.append(
                {
                    "case_id": case["id"],
                    "control_time": phase["time"],
                    "state_semantics": "case initial state under each control; no evolution",
                    "input_packet": before.tolist(),
                    "packet": after.tolist(),
                    "native_packet_rate": rate.tolist(),
                    "primary_rate": rate[primary_rows].tolist(),
                    "voltage": vm.tolist(),
                    "delta_v": float(delta[0]),
                    "leak_flux": leak[:3].tolist(),
                    "pump_flux": pump[:3].tolist(),
                    "local_rate": local[primary_rows].tolist(),
                    "junction_flux": junction[[0, 1, 2, grn.miR200_total], 0].tolist(),
                    "gate_scales": scales[[0, 1, 2, grn.miR200_total], 0].tolist(),
                    "audits": {
                        "primary_unchanged": bool(
                            np.array_equal(before[primary_rows], after[primary_rows])
                        ),
                        "context_unchanged": bool(
                            np.array_equal(before[context_rows], after[context_rows])
                        ),
                        "repeat_rhs_exact": bool(np.array_equal(rate, repeated)),
                        "readouts_do_not_change_refreshed_packet": bool(
                            np.array_equal(after, sim.cc_cells)
                        ),
                        "nonprimary_native_slopes_zero": bool(
                            np.all(np.delete(rate, primary_rows, axis=0) == 0)
                        ),
                        "regulatory_charge_excluded": bool(
                            np.array_equal(vm, sim.compute_Vm(excluded))
                        ),
                        "temporary_parameters_restored": all(
                            np.array_equal(old, new)
                            for old, new in zip(
                                parameter_arrays,
                                (sim.Dm_array, sim.z_array, sim.GJ_diffusion),
                                strict=True,
                            )
                        ),
                        "finite": bool(
                            all(
                                np.isfinite(a).all()
                                for a in (rate, after, leak, pump, local, junction)
                            )
                        ),
                    },
                }
            )
    return {
        "row_names": list(sim.ion_i),
        "records": records,
        "geometry": {"area": p.cell_sa, "volume": p.cell_vol, "ghk_voltage_factor": p.k26mV_inv},
        "profile": {
            "iterate_binding": grn.ITERATE,
            "mirna_target": grn.MIR200_TGT,
            "mirna_drift_valence": grn.miR200_valence,
            "mirna_in_voltage": False,
            "mirna_medium_size": grn.miR200_is_medium_size,
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--panel", type=Path, default=PANEL)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--retain-fixture", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    panel = json.loads(args.panel.read_text())
    source = args.source.resolve()
    if args.worker:
        print(MARKER + json.dumps(worker(source, panel), allow_nan=False))
        return 0
    if args.output is None or args.output.exists():
        parser.error("--output must name a new directory")
    if args.retain_fixture is not None and args.retain_fixture.exists():
        parser.error("Retained fixture already exists")
    before = provenance(source)
    panel_hash = sha(args.panel)
    prepared = check_preparation(panel)
    if panel["source_revision"] != before["revision"]:
        raise ValueError("Panel source revision differs")
    args.output.mkdir(parents=True, exist_ok=False)
    env = os.environ.copy()
    env.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "MPLBACKEND": "Agg",
            "OPENBLAS_NUM_THREADS": "1",
            "OMP_NUM_THREADS": "1",
            "MKL_NUM_THREADS": "1",
            "MPLCONFIGDIR": str(args.output.resolve() / "matplotlib-cache"),
        }
    )
    with (args.output / "native.log").open("x") as log:
        subprocess.run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                str(source),
                "--panel",
                str(args.panel.resolve()),
                "--worker",
            ],
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            env=env,
            timeout=60,
            check=True,
        )
    payloads = [
        line[len(MARKER) :]
        for line in (args.output / "native.log").read_text().splitlines()
        if line.startswith(MARKER)
    ]
    if len(payloads) != 1 or provenance(source) != before or sha(args.panel) != panel_hash:
        raise ValueError("Missing/ambiguous result or source/panel changed during capture")
    if check_preparation(panel) != prepared:
        raise ValueError("Preparation changed during capture")
    result = {
        "schema_version": 1,
        "scope": "instantaneous complete source-pair RHS only; no integration",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **before,
        "panel_sha256": panel_hash,
        "preparation_audit": prepared,
        "harness_hashes": {
            name: sha(Path(__file__).parent / name)
            for name in (
                "capture_source_pair_reference.py",
                "capture_contact_reference.py",
                "capture_emt_reference.py",
            )
        },
        "python": platform.python_version(),
        "packages": {name: metadata.version(name) for name in ("numpy", "scipy", "matplotlib")},
        "worker_timeout_seconds": 60,
        "probes": json.loads(payloads[0]),
    }
    encoded = json.dumps(result, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with (args.output / "reference.json").open("x") as handle:
        handle.write(encoded)
    if args.retain_fixture is not None:
        with args.retain_fixture.open("x") as handle:
            handle.write(encoded)
    print(f"Source-pair instantaneous reference saved: {args.output / 'reference.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
