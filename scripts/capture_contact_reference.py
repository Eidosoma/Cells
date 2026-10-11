"""Instantaneous BITSEY contact probes; no integrator or research-lane imports.

Run in .reference-venv against the clean, pinned, local checkout. No upstream
code is copied, patched, or redistributed. See docs/SOURCE_COUPLING_MAP.md.
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

from capture_emt_reference import inspect_source

MARKER = "CELLS_CONTACT_JSON "


def provenance(source):
    result = inspect_source(source)
    for name in ("GJ_lib.py", "cancer_GJ_sims/zombie.py"):
        result["source_hashes"][name] = hashlib.sha256((source / name).read_bytes()).hexdigest()
    return result


def worker(source):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / "cancer_GJ_sims"), str(source)]
    import GJ_lib
    import GRN_miRNA as grn
    import numpy as np
    import sim

    p = sim.Params()

    def pair(extra=("neutral",)):
        sim.init_big_arrays(2, 1, p, extra_ions=extra)
        sim.GJ_connects["from"] = 0
        sim.GJ_connects["to"] = 1

    pair()
    sim.cc_cells[:] = np.array([[12, 18], [140, 130], [10, 15], [80, 80], [7, 3]])
    sim.GJ_diffusion[:, 0] = [2e-15, 1e-15, 3e-15, 0, 4e-15]
    inputs = {
        "concentrations": sim.cc_cells.tolist(),
        "valences": sim.z_array.tolist(),
        "diffusion": sim.GJ_diffusion[:, 0].tolist(),
    }
    transport = []
    for delta in (-0.08, -0.02, 0.0, 0.02, 0.08):
        dv = np.array([delta])
        ith, gth = sim.GJ_norton(dv)
        flux = ith + dv * gth
        sim.GJ_connects["from"], sim.GJ_connects["to"] = 1, 0
        reverse_i, reverse_g = sim.GJ_norton(-dv)
        reverse = reverse_i - dv * reverse_g
        sim.GJ_connects["from"], sim.GJ_connects["to"] = 0, 1
        np.testing.assert_array_equal(reverse, -flux)
        transport.append(
            {"delta_v": delta, "flux": flux[:, 0].tolist(), "reverse": reverse[:, 0].tolist()}
        )

    # Source drift approximation versus the exact ideal-solution equilibrium.
    sim.cc_cells[sim.ion_i["Na"]] = [1.0, 2.0]
    limiting = []
    for x in (float(np.log(2)), 0.8):
        dv = np.array([x * p.kb * p.T / p.q])
        ith, gth = sim.GJ_norton(dv)
        flux = (ith + dv * gth)[sim.ion_i["Na"], 0]
        limiting.append(
            {"x": x, "delta_v": float(dv[0]), "normalized_flux": float(flux * p.GJ_len / 2e-15)}
        )

    # Exercise the executable orientation and scatter through the complete RHS.
    pair()
    sim.Dm_array.fill(0)
    sim.pump_scaling.fill(0)
    sim.GJ_diffusion.fill(0)
    sim.GJ_diffusion[sim.ion_i["Na"]] = 2e-15
    sim.cc_cells[sim.ion_i["Na"]] = [12.0, 18.0]
    requested_vm = np.array([-0.01, 0.02])
    sim.cc_cells[sim.ion_i["P"]] = (
        sim.cc_cells[sim.ion_i["Na"]]
        + sim.cc_cells[sim.ion_i["K"]]
        - sim.cc_cells[sim.ion_i["Cl"]]
        - requested_vm * p.cell_sa * p.cm / (p.F * p.cell_vol)
    )
    vm = sim.compute_Vm(sim.cc_cells)
    slopes = sim.sim_slopes(0)
    full_rhs = {
        "concentrations": sim.cc_cells.tolist(),
        "valences": sim.z_array.tolist(),
        "diffusion": sim.GJ_diffusion[:, 0].tolist(),
        "vm": vm.tolist(),
        "slopes": slopes.tolist(),
    }

    gates = []
    for kind in ("45/45", "40/37", "43/45"):
        pair()
        gate = GJ_lib.GJ_gate(kind)
        gate.set_ion_blocked_when_closed([sim.ion_i["neutral"]])
        gate.set_ion_fully_blocked([sim.ion_i["P"]])
        records = []
        for delta in (-0.08, -0.04, 0.0, 0.04, 0.08):
            dv = np.array([delta])
            scale = gate.func(None, None, dv, 0)
            later = gate.func(None, None, dv, 500)
            np.testing.assert_array_equal(later, scale)
            records.append(
                {
                    "delta_v": delta,
                    "on_fraction": float(gate.Chen_Izu_on_frac(dv)[0]),
                    "ordinary": float(scale[sim.ion_i["Na"], 0]),
                    "closed_blocked": float(scale[sim.ion_i["neutral"], 0]),
                    "fully_blocked": float(scale[sim.ion_i["P"], 0]),
                    "time_independent": bool(np.array_equal(later, scale)),
                }
            )
        gates.append(
            {"kind": kind, "parameters": list(GJ_lib.Chen_Izu_params[kind]), "records": records}
        )

    pair(grn.extra_ions())
    grn.build_GRN(None)
    if grn.ITERATE or grn.MIR200_TGT != -1 or grn.miR200_valence != -1:
        raise ValueError("Unexpected pinned regulatory approximation or transport valence")
    sim.cc_cells[grn.snail] = 72
    sim.cc_cells[grn.miR200_total] = [100, 40]
    sim.cc_cells[grn.Zeb_mRNA_total] = [15, 60]
    sim.cc_cells[grn.ZEB_prot] = [5, 80]
    sim.GD_gates[0].func(sim.cc_cells, None, None, 0)
    before = sim.cc_cells.copy()
    vm_before = sim.compute_Vm(before)
    changed = before.copy()
    changed[[grn.miR200_total, grn.miR200_free]] += 1000
    charge_excluded = bool(np.array_equal(vm_before, sim.compute_Vm(changed)))
    grn.set_GJdiff(2e-15)
    mirna = []
    for delta in (-0.08, 0.0, 0.08):
        dv = np.array([delta])
        flux = sim.GJ_add_gates[0].func(sim.cc_cells, vm_before, dv, 0)
        np.testing.assert_array_equal(sim.cc_cells, before)
        mirna.append({"delta_v": delta, "flux": float(flux[0])})
    selected = GJ_lib.GJ_gate()
    grn.set_GJ_diffusions(selected)
    grn_scales = selected.func(None, None, np.array([0.04]), 0)[:, 0]
    return {
        "constants": {
            name: getattr(p, name)
            for name in ("F", "R", "q", "kb", "T", "GJ_len", "cell_sa", "cell_vol", "cm", "tm")
        },
        "transport_inputs": inputs,
        "transport": transport,
        "limiting": limiting,
        "full_rhs": full_rhs,
        "gates": gates,
        "mirna": {
            "effective_transport_valence": grn.miR200_valence,
            "free_concentrations": before[grn.miR200_free].tolist(),
            "total_concentrations": before[grn.miR200_total].tolist(),
            "diffusion": grn.miR200_free_GJ_diffusion_val,
            "output_is_total": bool(sim.GJ_add_gates[0].out_ion == grn.miR200_total),
            "charge_excluded": charge_excluded,
            "temporary_valence_reset": bool(sim.z_array[grn.miR200_free] == 0),
            "temporary_diffusion_reset": bool(np.all(sim.GJ_diffusion[grn.miR200_free] == 0)),
            "primary_and_derived_unchanged_by_transport": bool(
                np.array_equal(sim.cc_cells, before)
            ),
            "records": mirna,
            "scale_at_40mv": {name: float(grn_scales[index]) for name, index in sim.ion_i.items()},
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    source = args.source.resolve()
    if args.worker:
        print(MARKER + json.dumps(worker(source), allow_nan=False))
        return 0
    if args.output is None or args.output.exists():
        parser.error("--output must name a new directory")
    original = provenance(source)
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
            [sys.executable, str(Path(__file__).resolve()), str(source), "--worker"],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            timeout=60,
            check=True,
        )
    lines = (args.output / "native.log").read_text().splitlines()
    payloads = [line[len(MARKER) :] for line in lines if line.startswith(MARKER)]
    if len(payloads) != 1 or provenance(source) != original:
        raise ValueError("Missing/ambiguous capture or changed reference checkout")
    result = {
        "schema_version": 1,
        "scope": "instantaneous source contact probes only; no trajectory or assay parity",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        **original,
        "harness_hashes": {
            name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ("capture_contact_reference.py", "capture_emt_reference.py")
        },
        "python": platform.python_version(),
        "packages": {name: metadata.version(name) for name in ("numpy", "scipy", "matplotlib")},
        "worker_timeout_seconds": 60,
        "probes": json.loads(payloads[0]),
    }
    with (args.output / "reference.json").open("x") as handle:
        json.dump(result, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(f"Contact reference saved: {args.output / 'reference.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
