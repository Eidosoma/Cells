"""NUM-005a bounded native full-RHS graph witnesses; never integrate.

Run in .reference-venv against the pinned reusable BITSEY modules. The worker
reads fully expanded inputs and imports no Cells/reference equations, cancer
driver or exploration harness. Configuration arrays specify independent edges;
no native equation is replaced and upstream remains clean.
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

ROOT = Path(__file__).resolve().parents[1]
MARKER = "CELLS_SOURCE_GRAPH_JSON "


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    with Path(path).open("x") as handle:
        json.dump(value, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")


def worker(source, inputs):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / "cancer_GJ_sims"), str(source)]
    import GJ_lib
    import GRN_miRNA as grn
    import numpy as np
    import sim
    import sim_toolbox as stb

    if grn.ITERATE or grn.MIR200_TGT != -1 or grn.miR200_valence != -1:
        raise ValueError("Unexpected source regulatory approximation")
    if not grn.miR200_is_medium_size or grn.Snail_input_conc != 72:
        raise ValueError("Unexpected source selectivity/input default")

    class PrescribedLeak(sim.Gate):
        def __init__(self, row, values):
            super().__init__(dest=self.GATE_IC, out_ion=row)
            self.values = values

        def func(self, cc, vm, delta_v, time):
            return self.values

    panel = inputs["panel"]
    records = []
    for case in inputs["cases"]:
        n, e = len(case["cell_ids"]), len(case["edge_ids"])
        p = sim.Params()
        if any(getattr(p, k) != v for k, v in panel["parameters"].items()):
            raise ValueError("Source defaults differ from inherited equation constants")
        p.no_dumps = True
        sim.init_big_arrays(n, e, p, extra_ions=grn.extra_ions() + ("ST",))
        grn.build_GRN(None)
        sim.GJ_diffusion[sim.ion_i["ST"]] = 0
        sim.GJ_connects["from"] = [case["cell_ids"].index(a) for a, _ in case["edges"]]
        sim.GJ_connects["to"] = [case["cell_ids"].index(b) for _, b in case["edges"]]
        primary_rows = [sim.ion_i[name] for name in panel["primary_rows"]]
        context_rows = [sim.ion_i[name] for name in panel["context_rows"]]
        sim.cc_cells[primary_rows] = case["primary"]
        sim.cc_cells[context_rows] = case["context"]
        sim.cc_cells[grn.miR200_free : grn.bound0 + 7] = np.arange(8 * n).reshape(8, n) + 700
        before = sim.cc_cells.copy()
        held = case["controls"]
        sim.Dm_array[:3] = case["membrane_diffusion"]
        sim.cc_env[:3] = panel["bath_ions"]
        sim.pump_scaling[:] = held["pump"]
        sim.GJ_diffusion[:3] = np.asarray(case["ionic_diffusion"]) * held["ion_contact"]
        # The native coefficient assignment broadcasts over edges; use its
        # existing array operation, not a rewritten flux or special donor rule.
        grn.set_GJdiff(np.asarray(case["mirna_diffusion"]) * held["mirna_contact"])
        for row, values in enumerate(held["leak"]):
            PrescribedLeak(row, np.asarray(values))
        gates = []
        for kind in sorted({k for k in case["gates"] if k is not None}):
            if list(GJ_lib.Chen_Izu_params[kind]) != panel["gate_parameters"][kind]:
                raise ValueError("Pinned gate constants differ")
            gate = GJ_lib.GJ_gate(kind)
            grn.set_GJ_diffusions(gate)
            outside = np.array([k != kind for k in case["gates"]])
            gate.Gmin[:, outside], gate.Gdelta[:, outside] = 1.0, 0.0
            swap = np.array(
                [
                    k == kind and flag
                    for k, flag in zip(case["gates"], case["swap_hemichannels"], strict=True)
                ]
            )
            gate.A1[swap], gate.A2[swap] = gate.A2[swap].copy(), gate.A1[swap].copy()
            gate.VO1[swap], gate.VO2[swap] = gate.VO2[swap].copy(), gate.VO1[swap].copy()
            gates.append(gate)
        parameter_arrays = [sim.Dm_array, sim.z_array, sim.GJ_diffusion, sim.pump_scaling]
        for gate in gates:
            parameter_arrays.extend([gate.A1, gate.A2, gate.VO1, gate.VO2, gate.Gmin, gate.Gdelta])
        parameters_before = [a.copy() for a in parameter_arrays]
        rate = sim.sim_slopes(0)
        after = sim.cc_cells.copy()
        repeated = sim.sim_slopes(19)
        vm = sim.compute_Vm(sim.cc_cells)
        delta = vm[sim.GJ_connects["from"]] - vm[sim.GJ_connects["to"]]
        leak = stb.GHK(sim.cc_env, sim.cc_cells, sim.Dm_array, sim.z_array, vm, p)
        for gate in sim.IC_gates:
            leak[gate.out_ion] *= gate.func(sim.cc_cells, vm, delta, 0)
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
        for gate in sim.GD_gates:
            local[gate.out_ion, :] += gate.func(sim.cc_cells, vm, delta, 0)
        ith, gth = sim.GJ_norton(delta)
        junction = ith + delta * gth
        for gate in sim.GJ_add_gates:
            junction[gate.out_ion] += gate.func(sim.cc_cells, vm, delta, 0)
        scales = np.ones_like(junction)
        for gate in sim.GJ_scale_gates:
            scales *= gate.func(sim.cc_cells, vm, delta, 0)
        junction *= scales
        excluded = after.copy()
        excluded[primary_rows[3:]] += 111
        excluded[grn.miR200_free] += 111
        records.append(
            {
                "case_id": case["id"],
                "origin": case["origin"],
                "input_packet": before.tolist(),
                "packet": after.tolist(),
                "native_packet_rate": rate.tolist(),
                "primary_rate": rate[primary_rows].tolist(),
                "voltage": vm.tolist(),
                "delta_v": delta.tolist(),
                "leak_flux": leak[:3].tolist(),
                "pump_flux": pump[:3].tolist(),
                "local_rate": local[primary_rows].tolist(),
                "junction_flux": junction[[0, 1, 2, grn.miR200_total]].tolist(),
                "gate_scales": scales[[0, 1, 2, grn.miR200_total]].tolist(),
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
                        np.array_equal(a, b)
                        for a, b in zip(parameters_before, parameter_arrays, strict=True)
                    ),
                    "finite": bool(
                        all(
                            np.isfinite(a).all()
                            for a in (rate, after, leak, pump, local, junction, scales)
                        )
                    ),
                },
            }
        )
    if any(
        name in sys.modules
        for name in ("cells", "zombie", "run_pilot", "tests.reference_source_graph")
    ):
        raise ValueError("Unexpected production/reference/experiment import in native worker")
    return {
        "row_names": list(sim.ion_i),
        "records": records,
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
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker-input", type=Path)
    parser.add_argument("--retain-fixture", type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    if args.worker_input is not None:
        print(
            MARKER
            + json.dumps(worker(source, json.loads(args.worker_input.read_text())), allow_nan=False)
        )
        return
    if args.output is None or args.output.exists():
        parser.error("--output must name a new directory")
    if args.retain_fixture is not None and args.retain_fixture.exists():
        parser.error("--retain-fixture must name a new file")
    from capture_contact_reference import provenance

    sys.path.insert(0, str(ROOT))
    from tests.source_graph_fixtures import DEFINITION, cases, definition, graph

    before = provenance(source)
    data = definition()
    inputs = {"panel": graph.eq.load_panel(), "cases": cases()}
    encoded = json.dumps(inputs, indent=2, sort_keys=True, allow_nan=False) + "\n"
    if len(encoded.encode()) > data["native_max_input_bytes"]:
        raise ValueError("Native graph input budget exceeded")
    source_files = [
        "scripts/capture_source_graph_reference.py",
        "scripts/capture_contact_reference.py",
        "scripts/capture_emt_reference.py",
        "tests/source_graph_fixtures.py",
        "tests/reference_source_graph.py",
        "tests/reference_source_pair.py",
        "tests/reference_emt.py",
        "scripts/check_e02_protocol.py",
    ]
    hashes = {name: sha(ROOT / name) for name in source_files}
    definition_hash = sha(DEFINITION)
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "inputs.json", inputs)
    input_hash = sha(args.output / "inputs.json")
    write_json(
        args.output / "registration.json",
        {
            "scope": data["scope"],
            "definition_sha256": definition_hash,
            "inputs_sha256": input_hash,
            "harness_hashes": hashes,
            "source": before,
            "case_ids": [c["id"] for c in inputs["cases"]],
            "worker_timeout_seconds": data["native_worker_timeout_seconds"],
        },
    )
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
    try:
        with (args.output / "native.log").open("x") as log:
            subprocess.run(
                [
                    sys.executable,
                    str(Path(__file__).resolve()),
                    str(source),
                    "--worker-input",
                    str((args.output / "inputs.json").resolve()),
                ],
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                env=env,
                timeout=data["native_worker_timeout_seconds"],
                check=True,
            )
        payloads = [
            line[len(MARKER) :]
            for line in (args.output / "native.log").read_text().splitlines()
            if line.startswith(MARKER)
        ]
        if (
            len(payloads) != 1
            or provenance(source) != before
            or sha(DEFINITION) != definition_hash
            or sha(args.output / "inputs.json") != input_hash
            or any(sha(ROOT / k) != v for k, v in hashes.items())
        ):
            raise ValueError("Missing result or source/input/harness changed during capture")
        result = {
            "schema_version": 1,
            "scope": data["scope"],
            "created_utc": datetime.now(timezone.utc).isoformat(),
            **before,
            "definition_sha256": definition_hash,
            "inputs_sha256": input_hash,
            "harness_hashes": hashes,
            "python": platform.python_version(),
            "packages": {name: metadata.version(name) for name in ("numpy", "scipy", "matplotlib")},
            "worker_timeout_seconds": data["native_worker_timeout_seconds"],
            "probes": json.loads(payloads[0]),
        }
        write_json(args.output / "reference.json", result)
        if args.retain_fixture is not None:
            write_json(args.retain_fixture, result)
    except Exception as error:
        write_json(
            args.output / "failure.json",
            {
                "status": "incomplete",
                "exception": type(error).__name__,
                "message": str(error),
                "definition_sha256": definition_hash,
                "inputs_sha256": input_hash,
            },
        )
        raise
    print(f"Native graph derivatives saved: {args.output / 'reference.json'}")


if __name__ == "__main__":
    main()
