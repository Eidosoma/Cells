"""MG1 I3 noise levels from the independent reference alone (numpy/scipy; no engine run).

I3 judges that the known-pressure tension error grows linearly with position noise.
That holds only while the least-squares problem's second-order term is small, which
judged-01 showed it was not at sigma = 1e-5 (its registered top decade). v2 therefore
sets the noise levels by an a-priori rule from the reference's own equilibria and its
own force-balance matrix, written before this runs:

  levels = the three largest integer decades sigma = 10^k with
           max(kappa_ref) * sigma / min(l_ref) <= KAPPA_SIGMA_OVER_L_MAX (1e-3),

where kappa_ref is the condition number of the reference's tension matrix (the
known-pressure problem) and l_ref the mean junction length, over the registered
inference inputs (8 x 8 and 12 x 12, seeds 0-4; definitions built by the driver's
inference_model, relaxed by mg1_reference.relax with Newton polish). The reference's own
slopes at those levels are reported as a consistency check; they do not choose them.

  PYTHONPATH=src:. taskset -c C python -m validation.morphogenesis.mg1_noise_reference \
      --output EVIDENCE_DIR/noise_reference.json
"""

import argparse
import json
import math
import time
from pathlib import Path

import numpy as np

from validation.morphogenesis import mg1_reference as ref
from validation.morphogenesis import mg1_vertex as driver

KAPPA_SIGMA_OVER_L_MAX = 1e-3
LEVEL_COUNT = 3
SIZES = (8, 12)
SEEDS = (0, 1, 2, 3, 4)


def study(sizes=SIZES, seeds=SEEDS):
    rows = []
    for n in sizes:
        for seed in seeds:
            t0 = time.perf_counter()
            model, rng = driver.inference_model(n, seed)
            tissue = ref.from_definition(
                {"model": model, "experiment": {"parameter_controls": [{}]}}
            )
            x, force, _ = ref.relax(tissue, tissue.position, gtol=1e-12, polish=True)
            tension, pressure = ref.true_tensions(tissue, x)
            mt, mp = ref.force_balance(tissue, x)
            sv = np.linalg.svd(mt, compute_uv=False)
            length = float(np.mean(np.linalg.norm(ref.junction_vectors(tissue, x), axis=1)))
            rows.append(
                {
                    "n": n,
                    "seed": seed,
                    "relaxed_max_force": force,
                    "balance_residual": float(np.max(np.abs(mt @ tension + mp @ pressure))),
                    "kappa": float(sv[0] / sv[-1]),
                    "mean_junction_length": length,
                    "_state": (tissue, x, tension, pressure, rng.standard_normal(x.shape)),
                    "seconds": time.perf_counter() - t0,
                }
            )
            print(
                f"{n}x{n} seed {seed}: kappa {rows[-1]['kappa']:.3e}, |F| {force:.1e}", flush=True
            )
    kappa = max(r["kappa"] for r in rows)
    length = min(r["mean_junction_length"] for r in rows)
    top = math.floor(math.log10(KAPPA_SIGMA_OVER_L_MAX * length / kappa))
    levels = [10.0**k for k in range(top - LEVEL_COUNT + 1, top + 1)]
    for r in rows:
        tissue, x, tension, pressure, direction = r.pop("_state")
        errors = []
        for sigma in levels:
            mt, mp = ref.force_balance(tissue, x + sigma * direction)
            estimate, *_ = np.linalg.lstsq(mt, -mp @ pressure, rcond=None)
            errors.append(float(np.sqrt(np.mean((estimate - tension) ** 2)) / np.mean(tension)))
        r["reference_errors"] = errors
        r["reference_slope"] = float(np.polyfit(np.log10(levels), np.log10(errors), 1)[0])
    return {
        "kind": "cells.morphogenesis_mg1_noise_reference@1",
        "rule": (
            f"the {LEVEL_COUNT} largest integer decades sigma = 10^k with "
            f"max(kappa_ref) sigma / min(l_ref) <= {KAPPA_SIGMA_OVER_L_MAX}"
        ),
        "kappa_max": kappa,
        "mean_junction_length_min": length,
        "levels": levels,
        "kappa_sigma_over_l_at_top_level": kappa * levels[-1] / length,
        "reference_slopes": [r["reference_slope"] for r in rows],
        "rows": rows,
        "independence": "numpy/scipy reference only; definitions from the driver's builder",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    t0 = time.perf_counter()
    result = study()
    result["wall_seconds"] = time.perf_counter() - t0
    with args.output.open("x") as stream:
        json.dump(result, stream, indent=1)
    print(json.dumps({k: result[k] for k in ("levels", "kappa_max", "reference_slopes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
