"""Regenerate FR-43 part 2's reference solutions: one JSON file per world and case in out/.

Usage (from the repository root, with the numpy/scipy environment):

    python validation/fr43_part2/references/run_references.py [--cases C2.3-sink ...]

Each case is integrated unsplit by the primary method (scipy's Radau IIA, order 5, at rtol 1e-11)
and by its second methods; the file records the largest difference of every quantity between the
primary and each second method.
"""

from __future__ import annotations

import os

# One BLAS thread, set before numpy loads OpenBLAS: a threaded LU varies in its last bits from run
# to run, which changes the step sequence (by about 1e-13 relative in the results). With one
# thread a regeneration reproduces the files bitwise on the same platform and library versions.
for _var in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ[_var] = "1"

import argparse  # noqa: E402
import json  # noqa: E402
import platform  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402
import time  # noqa: E402

import numpy as np  # noqa: E402
import scipy  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from fr43p2_reference import (ATOL_AMOUNT, ATOL_ENERGY, World, checks, compare,  # noqa: E402
                              integrate, readouts)

WORLDS = os.path.join(HERE, "worlds")
OUT = os.path.join(HERE, "out")

PRIMARY = {"method": "Radau", "rtol": 1e-11}
# No world is stiff once the pools' machines are counts (amendment 2), so the explicit DOP853 is
# usable everywhere as an independent method family, beside Radau at a tighter tolerance.
SECOND = [{"method": "DOP853", "rtol": 1e-13}, {"method": "Radau", "rtol": 1e-12}]

# case -> (the world files it serves, the network's rate-constant factor); the files of one kind
# differ only in the engine's step, which this calculation does not use.
CASES = {
    "C2.3-sink": (["C2.3-sink-dt0p5.json", "C2.3-sink-dt0p25.json"], 1.0),
    "C2.3-sink-planted": (["C2.3-sink-dt0p5.json", "C2.3-sink-dt0p25.json"], 1.01),
    "C2.3-source": (["C2.3-source-dt0p5.json", "C2.3-source-dt0p25.json"], 1.0),
    "C2.3-source-planted": (["C2.3-source-dt0p5.json", "C2.3-source-dt0p25.json"], 1.01),
    "C2.6-swelling-cell": (["C2.6-swelling-cell-dt0p01.json", "C2.6-swelling-cell-dt0p005.json"],
                           1.0),
    "C2.8-swelling-pair-sink": (["C2.8-swelling-pair-sink-dt0p01.json",
                                 "C2.8-swelling-pair-sink-dt0p005.json"], 1.0),
}

INTEGRATOR_NAMES = {
    "Radau": "scipy.integrate.solve_ivp Radau (implicit Radau IIA, order 5)",
    "DOP853": "scipy.integrate.solve_ivp DOP853 (explicit Runge-Kutta, order 8)",
}
ATOL_TEXT = (f"{ATOL_AMOUNT:g} fmol (amounts, machines, complexes, extents) and pL (volume); "
             f"{ATOL_ENERGY:g} pJ (heats and works)")


def git_identity() -> dict:
    """The checkout's revision and any changed or untracked path under this folder that can change
    a result: the code (*.py) and the input worlds (worlds/). Documents and out/ are not."""
    def run(*args):
        return subprocess.run(["git", "-C", HERE, *args], capture_output=True, text=True).stdout
    dirty = [ln[3:] for ln in run("status", "--porcelain", "--untracked-files=all", "--", HERE)
             .splitlines()]
    return {"revision": run("rev-parse", "HEAD").strip(),
            "dirty_code_and_input_paths": [p for p in dirty
                                           if p.endswith(".py") or "/worlds/" in p]}


def _method_record(spec, info, wall):
    rec = {"integrator": INTEGRATOR_NAMES[spec["method"]], "rtol": spec["rtol"],
           "atol": ATOL_TEXT, "steps": info["steps"], "rhs_evaluations": info["nfev"],
           "wall_s": round(wall, 1)}
    if "recharge_sign_changes_s" in info:
        rec["recharge_sign_changes_s"] = info["recharge_sign_changes_s"]
    return rec


def run_case(name: str) -> dict:
    files, k_factor = CASES[name]
    primary, seconds = PRIMARY, SECOND
    worlds = [World(os.path.join(WORLDS, f), network_k_factor=k_factor) for f in files]
    world = worlds[0]
    for other in worlds[1:]:  # one calculation serves every file of the kind
        if other.observation_times != world.observation_times or other.n0 != world.n0:
            raise ValueError(f"{files} differ in more than the engine's step")
    times = world.observation_times
    t0 = time.time()
    Y, info = integrate(world, times, **primary)
    method = {"primary": _method_record(primary, info, time.time() - t0)}
    method["primary"]["sampling"] = ("integrated segment by segment between the reported times "
                                     "(and recharging's sign changes), so every reported value "
                                     "is a step end; no dense output")
    ro = readouts(world, times, Y, info)
    method["second"] = []
    worst = {}
    for sec in seconds:
        t0 = time.time()
        Y2, info2 = integrate(world, times, **sec)
        rec = _method_record(sec, info2, time.time() - t0)
        rec["difference_from_primary"] = compare(readouts(world, times, Y2, info2), ro)
        method["second"].append(rec)
        for k, v in rec["difference_from_primary"].items():
            worst[k] = max(worst.get(k, 0.0), v["e_max_normalised"])
    method["largest_difference_e"] = worst
    method["difference_measure"] = (
        "e = max_i |q_second(t_i) - q_primary(t_i)| / max_i |q_primary(t_i)|, CRITERIA.md's "
        "normalisation; max_pointwise_relative is the largest |dq|/|q| over rows with q != 0")
    doc = {"case": name, "world_files": files, "network_rate_constant_factor": k_factor,
           "times_s": times}
    doc.update(ro)
    doc["method"] = method
    doc["checks"] = checks(world, Y, info)
    doc["provenance"] = {"git": git_identity(), "python": platform.python_version(),
                         "numpy": np.__version__, "scipy": scipy.__version__,
                         "generator": "validation/fr43_part2/references/run_references.py"}
    return doc


def summary() -> str:
    """README.md's results table, from the files in out/."""
    rows = ["| Case | Primary steps | Second method: largest e (quantity) | Identities: largest "
            "residual |", "| --- | --- | --- | --- |"]
    for name in CASES:
        path = os.path.join(OUT, f"{name}.json")
        if not os.path.exists(path):
            continue
        with open(path) as fh:
            doc = json.load(fh)
        m = doc["method"]
        secs = []
        for s in m["second"]:
            q, v = max(s["difference_from_primary"].items(), key=lambda kv: kv[1]["e_max_normalised"])
            label = s["integrator"].split(" ")[1] + f" {s['rtol']:g}"
            secs.append(f"{label}: {v['e_max_normalised']:.1e} (`{q}`)")
        chk = doc["checks"]
        fmol = max(v for k, v in chk.items() if k.endswith("_fmol")) if any(
            k.endswith("_fmol") for k in chk) else None
        parts = [f"energy {chk['energy_identity_relative_to_scale']:.1e} of scale"]
        if fmol is not None:
            parts.insert(0, f"books, machines, residues, products, moieties {fmol:.1e} fmol")
        rows.append(f"| {name} | {m['primary']['steps']} | {'; '.join(secs)} | {'; '.join(parts)} |")
    return "\n".join(rows)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cases", nargs="*", default=list(CASES))
    ap.add_argument("--summary", action="store_true", help="print README.md's results table")
    args = ap.parse_args(argv)
    if args.summary:
        print(summary())
        return
    os.makedirs(OUT, exist_ok=True)
    for name in args.cases:
        t0 = time.time()
        doc = run_case(name)
        path = os.path.join(OUT, f"{name}.json")
        with open(path, "w") as fh:
            json.dump(doc, fh, indent=1)
            fh.write("\n")
        worst = max(doc["method"]["largest_difference_e"].values())
        print(f"{name}: {time.time() - t0:.0f} s, largest e between methods {worst:.2e} -> {path}",
              flush=True)


if __name__ == "__main__":
    main()
