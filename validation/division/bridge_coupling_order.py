"""The open-bridge coupling's step dependence (S5 design §7.3, Q4; a development measurement).

tests/unit/test_bridge_closure_runs.py compares 1 - V2/V1 with the two-cell DC ratio
R_b / (Rm + R_b) on passive worlds, where the injection's split half-steps and the bridge's
fast antisymmetric mode interact. This measures the relative excess of 1 - V2/V1 over the
ratio at dt = 1, 0.5 and 0.25 ms, and the observed order of that excess. It uses the test's
own worlds and voltages, and reads no reference.

Usage: python -m validation.division.bridge_coupling_order OUTPUT_FILE (through
scripts/run_detached.sh; a few minutes per step size).
"""

import json
import sys

import jax
import numpy as np

from tests import partition_fixtures as fx
from tests.unit import test_bridge_closure_runs as limit

STEPS = (1e-3, 5e-4, 2.5e-4)


def excess(dt):
    limit.DT = dt  # The test module's step, read by final_voltages.
    bridge = ("exponential", limit.TAU)
    coupled, (_, _, state, _) = limit.final_voltages(
        fx.divided(bridge=bridge, injection=limit.CURRENT_A, end=limit.END)
    )
    base, _ = limit.final_voltages(fx.divided(bridge=bridge, end=limit.END))
    alone, _ = limit.final_voltages(fx.divided(injection=limit.CURRENT_A, end=limit.END))
    alone_base, _ = limit.final_voltages(fx.divided(end=limit.END))
    rm = (alone["d1"] - alone_base["d1"]) / limit.CURRENT_A
    rb = 1.0 / (2 * float(np.asarray(state.bridge_aperture_m)[0]) * fx.SIGMA_CYT)
    v1, v2 = coupled["d1"] - base["d1"], coupled["d2"] - base["d2"]
    return (1 - v2 / v1) / (rb / (rm + rb)) - 1


def main(path):
    jax.config.update("jax_enable_x64", True)
    values = {dt: excess(dt) for dt in STEPS}
    orders = [float(np.log2(values[a] / values[b])) for a, b in zip(STEPS, STEPS[1:], strict=False)]
    report = dict(relative_excess={str(k): v for k, v in values.items()}, observed_orders=orders)
    with open(path, "w") as f:
        json.dump(report, f, indent=1)
    print(json.dumps(report, indent=1), flush=True)


if __name__ == "__main__":
    main(sys.argv[1])
