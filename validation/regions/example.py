"""FR-33's region export and tracer on the FR-7 lane's maintained example
(validation/compartment_transfer, 60cf2364), with one addition.

**The example's world.** One cell owns two compartments.
- **T:** exchange releases `ST` from `ecs_0` into the cell, at kappa = 1/s.
- **D:** turnover clears `SD` at `ecs_1`, at the same kappa.

**The addition:** turnover also clears `ST` in the cell, at K_CELL = 2/s, and makes it there, at
P_CELL = 1e-3 fmol/s. The cell then mixes the material it received, its own and what it makes, and
loses all of them, so the tracer has a node with inflow to split. The made material is labelled
`pulse` before T_PULSE = 0.25 s and `chase` after. The example's control is unchanged for `SD`: its
donor fades at kappa, and only its loss rises. For `ST`, the cell's loss and production change the
whole-cell total too, outside the region `ecs_0`.

`run()` runs the world once, recording every accepted step. `exports(run())` returns:
- the region export of `ST` over [`ecs_0`] and of `SD` over [`ecs_1`] (readouts.region_rows), at
  the example's output rows;
- the trace of `ST`, with cohorts `from_ecs_0` (all that `ecs_0` holds at the start) and `in_cell`
  (all the cell holds), the made `pulse` and `chase`, and the `unlabelled` trace in `ecs_1`;
- the closed forms of each cohort, for kappa, K_CELL and P_CELL (k = K_CELL, T = T_PULSE):
  - A_ecs0 = A0 e^(-kappa t);
  - A_cell = A0 kappa/(k - kappa) (e^(-kappa t) - e^(-k t));
  - B_cell = B0 e^(-k t);
  - pulse = (P/k)(1 - e^(-k min(t, T))) e^(-k max(0, t - T)), and chase = (P/k)(1 - e^(-k (t - T)))
    after T;
  - each one's cumulative loss in the cell: what reached the cell, less what it holds.

**The reviewer's case** (two_node_diffusion), which the tracer must refuse: two finite 1 pL nodes,
`left` and `right`, joined by a face that diffuses at ln 2 / 2 per second per node, 100 steps of
0.01 s. Each node faces the cell through a contact patch that nothing crosses, which places it in
the cell's capacitor component. `S` starts at 1 fmol in each, so its totals and its net face flux
stay at 0. `L` and `U` are the explicit label rows of the same material, 90% labelled on the left
and 10% on the right. Each diffuses down its own gradient, so `L` on the right reaches 0.3 fmol at
1 s (the difference halves).
A tracer of `S` driven by net records would see no movement and keep 0.1 there, so `trace` refuses
the face at setup.

Run: PYTHONPATH=src:. JAX_ENABLE_X64=1 JAX_PLATFORMS=cpu python -m validation.regions.example
"""

import copy
import json
import math

from cells.definitions.specs import parse_spec
from cells.registry.inventory_species import add_inventory_species
from validation.compartment_transfer import example as base
from validation.regions import readouts

K_CELL = 2.0  # 1/s: ST's clearance in the cell, synthetic.
P_CELL = 1e-3  # fmol/s: ST made in the cell, synthetic.
T_PULSE = 0.25  # s: made ST is labelled pulse before it and chase after (on the 1 ms grid).
COHORTS = {"from_ecs_0": {base.NODE_T: 1.0}, "in_cell": {base.CELL: 1.0}}
LABELS = [(0.0, "pulse"), (T_PULSE, "chase")]
R_DIFFUSION = math.log(2) / 2  # 1/s: each node's exchange rate in the reviewer's case.
FACE_AREA_M2, FACE_LENGTH_M = 1e-10, 1e-5


def world():
    """The example's world, with ST also cleared in the cell at K_CELL and made there at P_CELL."""
    out = copy.deepcopy(base.world())
    (turnover,) = [o for o in out["model"]["operators"] if o["law"] == base.fx.TURNOVER]
    turnover["species"].append(dict(id=base.ST, catalogue=None, evidence=None))
    for route, kind, rate in (("clear_cell", "clearance", K_CELL), ("make_cell", "production",
                                                                      P_CELL)):  # fmt: skip
        turnover["routes"].append(dict(id=route, species=base.ST, node=base.CELL, kind=kind))
        out["experiment"]["turnover_controls"].append(
            dict(route_id=route, carrier_id=base.CELL, schedule=[dict(time=0.0, rate=rate)])
        )
    return out


def two_node_diffusion(*, dt=0.01, steps=100):
    """The reviewer's case (module docstring): S at 1 mM in both nodes, and its label rows L (0.9
    and 0.1 mM) and U (0.1 and 0.9 mM), each diffusing on the face at R_DIFFUSION per node."""
    pl_m3 = 1e-15
    diffusivity = R_DIFFUSION * FACE_LENGTH_M * pl_m3 / FACE_AREA_M2  # r = D A / (L V), V = 1 pL.
    end = dt * steps
    raw = base.fx.world(
        cells=((base.CELL, 1.0),),
        nodes=(("left", 1.0), ("right", 1.0)),
        contacts=(("contact_0", base.CELL, "left"), ("contact_1", base.CELL, "right")),
        faces=(("face_lr", "left", "right", FACE_AREA_M2, FACE_LENGTH_M),),
        dt=dt,
        end=end,
        observation_times=base.fx.grid_times(end, dt, end / 10),
        concentrations_mM={"left": 1.0, "right": 1.0},
        diffusivity=diffusivity,
    )
    for name, left, right in (("L", 0.9, 0.1), ("U", 0.1, 0.9)):
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=base.fx.TRACE_mM,
            diffusivity_m2_per_s=diffusivity,
            floor_fmol=base.fx.FLOOR_FMOL,
            concentrations_mM={"left": left, "right": right},
        )
    return raw


def run():
    """(spec, times, states) of every accepted step of the world."""
    spec = parse_spec(world())
    times, states = readouts.runs(spec)
    return spec, times, states


def closed_forms(times, a0, b0):
    """The cohorts of ST by the closed forms (module docstring), per time."""
    kappa, k, P, T = base.KAPPA, K_CELL, P_CELL, T_PULSE
    out = {key: [] for key in ("A_ecs0", "A_cell", "B_cell", "pulse_cell", "chase_cell",
                               "A_lost", "B_lost", "pulse_lost", "chase_lost")}  # fmt: skip
    for t in times:
        a_cell = a0 * kappa / (k - kappa) * (math.exp(-kappa * t) - math.exp(-k * t))
        pulse = P / k * -math.expm1(-k * min(t, T)) * math.exp(-k * max(0.0, t - T))
        chase = P / k * -math.expm1(-k * (t - T)) if t > T else 0.0
        out["A_ecs0"].append(a0 * math.exp(-kappa * t))
        out["A_cell"].append(a_cell)
        out["B_cell"].append(b0 * math.exp(-k * t))
        out["pulse_cell"].append(pulse)
        out["chase_cell"].append(chase)
        out["A_lost"].append(a0 * -math.expm1(-kappa * t) - a_cell)
        out["B_lost"].append(b0 * -math.expm1(-k * t))
        out["pulse_lost"].append(P * min(t, T) - pulse)
        out["chase_lost"].append(P * max(0.0, t - T) - chase)
    return out


def exports(result=None):
    """The region exports, the trace and the closed forms (module docstring)."""
    spec, times, states = run() if result is None else result
    rows = [t for t in times if any(abs(t - s) < 1e-12 for s in spec.experiment.observation_times)]
    st = readouts.region_rows(spec, times, states, base.ST, [base.NODE_T], samples=rows)
    sd = readouts.region_rows(spec, times, states, base.SD, [base.NODE_D], samples=rows)
    traced = readouts.trace(spec, times, states, base.ST, COHORTS, produced=LABELS)
    a0 = traced["amount"]["from_ecs_0"][base.NODE_T][0]
    b0 = traced["amount"]["in_cell"][base.CELL][0]
    return dict(ST=st, SD=sd, trace=traced, closed=closed_forms(traced["times"], a0, b0))


if __name__ == "__main__":
    out = exports()
    last = {k: v[-1] for k, v in out["ST"].items() if k.endswith("_fmol") and isinstance(v, list)}
    print(json.dumps(dict(ST_last=last, closure=out["trace"]["closure_largest"]), indent=1))
