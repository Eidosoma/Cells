"""Bounded, optional reference capture from a local, unmodified BITSEY checkout.

Use the separate requirements-reference.txt environment. Does not import Cells,
copy upstream code into the package, patch its equations, or run network cases.
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
from time import perf_counter

REVISION = "b2cb370aaecbc8299f259bc4251d5396c81f19a6"
SOURCE_FILES = (
    "cancer_GJ_sims/GRN_miRNA.py",
    "sim.py",
    "sim_toolbox.py",
    "edebug.py",
    "eplot.py",
    "README.md",
)
MARKER = "CELLS_REFERENCE_JSON "


def inspect_source(source):
    def git(*args):
        return subprocess.check_output(["git", "-C", str(source), *args], text=True).strip()

    if git("rev-parse", "HEAD") != REVISION:
        raise ValueError("Reference checkout is not the pinned revision")
    if git("status", "--porcelain", "--untracked-files=all"):
        raise ValueError("Reference checkout is not clean")
    files = git("ls-tree", "-r", "--name-only", "HEAD").splitlines()
    return {
        "repository": "https://gitlab.com/grodstein/bitsey.git",
        "revision": REVISION,
        "source_hashes": {
            name: hashlib.sha256((source / name).read_bytes()).hexdigest() for name in SOURCE_FILES
        },
        "license_named_paths": [
            name
            for name in files
            if any(s in name.lower() for s in ("license", "licence", "copying"))
        ],
    }


def worker(source, case):
    sys.dont_write_bytecode = True
    sys.path[:0] = [str(source / "cancer_GJ_sims"), str(source)]
    import GRN_miRNA as grn
    import numpy as np
    import sim

    grn.instantiate()
    assert grn.ITERATE is False and grn.MIR200_TGT == -1
    indices = [grn.miR200_total, grn.Zeb_mRNA_total, grn.ZEB_prot]
    if case == "probes":
        gate = sim.GD_gates[0]
        # Boundary points and a seeded, predeclared grid; no endpoint fitting.
        points = [(72, 0, 0, 0), (72, 100, 0, 0), (72, 0, 100, 100), (72, 40, 30, 5)]
        rng = np.random.default_rng(82026)
        points += [tuple(row) for row in rng.uniform(0, 120, size=(32, 4))]
        results = []
        for snail, mir, mrna, protein in points:
            cc = sim.cc_cells.copy()
            cc[grn.snail, 0] = snail
            cc[indices, 0] = [mir, mrna, protein]
            derivative = gate.func(cc, None, None, 0)
            # The full isolated simulator must supply exactly the same three
            # regulatory slopes, independent of its evolving ionic subsystem.
            sim.cc_cells = cc.copy()
            full_derivative = sim.sim_slopes(0)[indices]
            np.testing.assert_array_equal(derivative, full_derivative)
            np.testing.assert_array_equal(cc[indices, 0], [mir, mrna, protein])
            results.append(
                {
                    "snail": float(snail),
                    "state": [float(mir), float(mrna), float(protein)],
                    "rhs": derivative[:, 0].tolist(),
                    "bound_complexes": cc[grn.bound0 : grn.bound0 + 7, 0].tolist(),
                    "mir200_free_proxy": float(cc[grn.miR200_free, 0]),
                }
            )
        return {"case": case, "full_isolated_slopes_equal_gate": True, "points": results}

    initial = [100, 0, 0] if case == "e" else [0, 100, 100]
    captured = {}

    def capture_return(frame, event, value):
        # Read-only observation of the source's accepted clock, which its helper
        # does not return. No patched numerical routine or replacement solver.
        if event == "return" and frame.f_code is sim.sim.__code__:
            captured["accepted_time"] = float(frame.f_locals["t"])
            captured["snapshot_times"], shots = value
            captured["snapshot_primary"] = [cc[indices, 0].tolist() for cc in shots]
            captured["minimum_sampled_full_state"] = float(min(np.min(cc) for cc in shots))
            captured["all_sampled_full_state_finite"] = bool(
                all(np.isfinite(cc).all() for cc in shots)
            )

    settings = {
        name: getattr(sim.GP, name)
        for name in (
            "time_step",
            "adaptive_timestep",
            "sim_integ_max_delt_Vm",
            "sim_integ_max_delt_cc",
            "use_implicit",
        )
    }
    started = perf_counter()
    sys.setprofile(capture_return)
    try:
        sampled = grn.sim_me(72, *initial)
    finally:
        sys.setprofile(None)
    return {
        "case": case,
        "initial": initial,
        "snail": 72,
        "requested_end_time": 10000,
        "source_settings": settings,
        "elapsed_seconds": perf_counter() - started,
        "last_sample_time": float(captured["snapshot_times"][-1]),
        "last_sample_primary": sampled[indices, 0].tolist(),
        "last_sample_label": grn.state_char(sampled[:, 0]),
        "accepted_primary": sim.cc_cells[indices, 0].tolist(),
        "accepted_label": grn.state_char(sim.cc_cells[:, 0]),
        "accepted_full_state": {name: float(sim.cc_cells[i, 0]) for name, i in sim.ion_i.items()},
        **captured,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--worker", choices=("probes", "e", "m"))
    args = parser.parse_args()
    source = args.source.resolve()
    if args.worker:
        print(MARKER + json.dumps(worker(source, args.worker), allow_nan=False))
        return 0
    if args.output is None:
        parser.error("--output is required")
    if args.output.exists():
        parser.error("Output already exists; choose a new directory")
    provenance = inspect_source(source)
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
    cases = {}
    for case in ("probes", "e", "m"):
        print(f"Capturing {case} (120-second limit)", flush=True)
        command = [sys.executable, str(Path(__file__).resolve()), str(source), "--worker", case]
        with (args.output / f"{case}.log").open("x") as log:
            subprocess.run(
                command,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                check=True,
                timeout=120,
            )
        lines = (args.output / f"{case}.log").read_text().splitlines()
        payloads = [line[len(MARKER) :] for line in lines if line.startswith(MARKER)]
        if len(payloads) != 1:
            raise ValueError(f"Expected exactly one result for {case}")
        cases[case] = json.loads(payloads[0])
    if inspect_source(source) != provenance:
        raise ValueError("Reference source changed during capture")
    receipt = {
        "schema_version": 1,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "pinned source comparison, not paper tables or licensing clearance",
        **provenance,
        "harness_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "python": platform.python_version(),
        "packages": {name: metadata.version(name) for name in ("numpy", "scipy", "matplotlib")},
        "worker_timeout_seconds": 120,
        "cases": cases,
    }
    with (args.output / "reference.json").open("x") as handle:
        json.dump(receipt, handle, indent=2, sort_keys=True, allow_nan=False)
        handle.write("\n")
    print(f"Reference saved: {args.output / 'reference.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
