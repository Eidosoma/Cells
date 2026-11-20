"""FR-33's region export and tracer on the FR-7 lane's maintained example
(validation/compartment_transfer, 60cf2364), with one addition.

**The example's world.** One cell owns two compartments.
- **T:** exchange releases `ST` from `ecs_0` into the cell, at kappa = 1/s.
- **D:** turnover clears `SD` at `ecs_1`, at the same kappa.

**The addition:** turnover also clears `ST` in the cell, at K_CELL = 2/s. The cell then mixes the
material it received with its own and loses both, so the tracer has a node with inflow to split.
The example's control is unchanged for `SD`: its donor fades at kappa, and only its loss rises.
For `ST`, the cell's loss lowers the whole-cell total too, outside the region `ecs_0`.

`run()` runs the world once, recording every accepted step. `exports(run())` returns:
- the region export of `ST` over [`ecs_0`] and of `SD` over [`ecs_1`] (readouts.region_rows), at
  the example's output rows;
- the trace of `ST`, with cohorts `from_ecs_0` (all that `ecs_0` holds at the start) and `in_cell`
  (all the cell holds), and the `unlabelled` trace in `ecs_1`;
- the closed forms of both cohorts, for kappa and K_CELL:
  - A_ecs0 = A0 e^(-kappa t);
  - A_cell = A0 kappa/(K_CELL - kappa) (e^(-kappa t) - e^(-K_CELL t));
  - B_cell = B0 e^(-K_CELL t);
  - their cumulative losses in the cell, A0 (1 - e^(-kappa t)) - A_cell and B0 (1 - e^(-K_CELL t)).

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu python -m validation.regions.example
"""

import copy
import json
import math

from cells.definitions.specs import parse_spec
from validation.compartment_transfer import example as base
from validation.regions import readouts

K_CELL = 2.0  # 1/s: ST's clearance in the cell, synthetic.
COHORTS = {"from_ecs_0": {base.NODE_T: 1.0}, "in_cell": {base.CELL: 1.0}}


def world():
    """The example's world, with ST also cleared in the cell at K_CELL."""
    out = copy.deepcopy(base.world())
    (turnover,) = [o for o in out["model"]["operators"] if o["law"] == base.fx.TURNOVER]
    turnover["species"].append(dict(id=base.ST, catalogue=None, evidence=None))
    turnover["routes"].append(dict(id="clear_cell", species=base.ST, node=base.CELL,
                                   kind="clearance"))  # fmt: skip
    out["experiment"]["turnover_controls"].append(
        dict(route_id="clear_cell", carrier_id=base.CELL, schedule=[dict(time=0.0, rate=K_CELL)])
    )
    return out


def run():
    """(spec, times, states) of every accepted step of the world."""
    spec = parse_spec(world())
    times, states = readouts.runs(spec)
    return spec, times, states


def closed_forms(times, a0, b0):
    """The cohorts of ST by the closed forms (module docstring), per time."""
    kappa, k = base.KAPPA, K_CELL
    out = dict(A_ecs0=[], A_cell=[], B_cell=[], A_lost=[], B_lost=[])
    for t in times:
        a_cell = a0 * kappa / (k - kappa) * (math.exp(-kappa * t) - math.exp(-k * t))
        out["A_ecs0"].append(a0 * math.exp(-kappa * t))
        out["A_cell"].append(a_cell)
        out["B_cell"].append(b0 * math.exp(-k * t))
        out["A_lost"].append(a0 * -math.expm1(-kappa * t) - a_cell)
        out["B_lost"].append(b0 * -math.expm1(-k * t))
    return out


def exports(result=None):
    """The region exports, the trace and the closed forms (module docstring)."""
    spec, times, states = run() if result is None else result
    rows = [t for t in times if any(abs(t - s) < 1e-12 for s in spec.experiment.observation_times)]
    st = readouts.region_rows(spec, times, states, base.ST, [base.NODE_T], samples=rows)
    sd = readouts.region_rows(spec, times, states, base.SD, [base.NODE_D], samples=rows)
    traced = readouts.trace(spec, times, states, base.ST, COHORTS)
    a0 = traced["amount"]["from_ecs_0"][base.NODE_T][0]
    b0 = traced["amount"]["in_cell"][base.CELL][0]
    return dict(ST=st, SD=sd, trace=traced, closed=closed_forms(traced["times"], a0, b0))


if __name__ == "__main__":
    out = exports()
    last = {k: v[-1] for k, v in out["ST"].items() if k.endswith("_fmol") and isinstance(v, list)}
    print(json.dumps(dict(ST_last=last, closure=out["trace"]["closure_largest"]), indent=1))
