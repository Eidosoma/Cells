"""FR-33's maintained example: the donor, the receiver and the cumulative loss exported together,
under transfer (T) and under local destruction (D), in one world (README.md beside this file).

One cell owns two compartments (cells.operator.cell_owned_compartments@1), each a finite node bounded by one patch
that no ion crosses. Each holds the same amount of its own labelled neutral species:
- **T, transfer:** `ST` in `ecs_0` is released into the cell by cells.operator.scheduled_species_exchange@1's
  first-order import, at rate constant kappa out of the node;
- **D, local destruction:** `SD` in `ecs_1` is cleared at that node by
  cells.operator.scheduled_species_turnover@1, at the same kappa.

Both donors fade the same way, n0 exp(-kappa t). Only T's receiver (the cell's `ST`) rises, by
what the release moved. Only D's cumulative loss (turnover's cleared amount at `ecs_1`) rises, by
what its donor lost. The world runs at 1 ms through the windowed runner.

Per observed row and arm it exports:
- donor_fmol: the species' amount in its compartment;
- receiver_fmol: its amount in the cell;
- loss_fmol: turnover's cumulative cleared amount at the compartment's node
  (`turnover_outside_cleared_fmol`, per species and outside node);
- transfer_fmol: exchange's cumulative released amount (-`exchange_moved_fmol`, which counts
  export positive).
"""

import copy

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.registry.inventory_species import add_inventory_species
from validation.tissue import secreted_species_fixtures as fx

CELL, NODE_T, NODE_D = "cell_0", "ecs_0", "ecs_1"
PATCH_T, PATCH_D = "contact_0", "contact_1"
ST, SD = fx.SPECIES, "SD"  # The transferred and the destroyed labelled species.
VOLUME_pL = 1.0  # Each compartment's volume.
KAPPA = 1.0  # 1/s, synthetic.
DONOR_mM = 1e-3  # Each compartment's starting concentration of its species.
CELL_mM = 1e-6  # The cell's starting concentration of each.
DT, END, EVERY = 1e-3, 0.5, 0.05
PL_PER_M3 = 1e15


def uptake_velocity():
    """k_u (m/s): exchange's first-order import leaves the node at k_u A 1e15 / V_o = KAPPA."""
    return KAPPA * VOLUME_pL / (fx.CONTACT_AREA_M2 * PL_PER_M3)


def destruction_rate():
    """D's clearance rate, formed by the same operations as exchange's import rate constant."""
    return uptake_velocity() * fx.CONTACT_AREA_M2 * PL_PER_M3 / VOLUME_pL


def world():
    """The cell, its two compartments, T's release and D's destruction."""
    stride, steps = int(round(EVERY / DT)), int(round(END / DT))
    rows = [k * DT for k in range(0, steps + 1, stride)]  # On the step grid exactly.
    raw = fx.world(
        cells=((CELL, 1.0),),
        nodes=((NODE_T, VOLUME_pL), (NODE_D, VOLUME_pL)),
        contacts=((PATCH_T, CELL, NODE_T), (PATCH_D, CELL, NODE_D)),
        faces=(),
        dt=DT,
        end=END,
        observation_times=rows,
        concentrations_mM={CELL: CELL_mM, NODE_T: DONOR_mM, NODE_D: fx.TRACE_mM},
    )
    raw = add_inventory_species(
        raw,
        SD,
        trace_mM=fx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={CELL: CELL_mM, NODE_D: DONOR_mM},
    )
    out = copy.deepcopy(raw)
    ops = out["model"]["operators"]
    ops.append(
        dict(
            law="cells.operator.cell_owned_compartments@1",
            compartments=[
                dict(
                    id="donor_T", node=NODE_T, patch=PATCH_T, owner=CELL, label="T", reference=None
                ),
                dict(
                    id="donor_D", node=NODE_D, patch=PATCH_D, owner=CELL, label="D", reference=None
                ),
            ],
        )
    )
    ops.append(
        dict(
            law=fx.EXCHANGE,
            species=[dict(id=ST, catalogue=None, evidence=None)],
            routes=[
                dict(id="release", species=ST, patch=PATCH_T, direction="import", law="first_order")
            ],
            templates=[],
        )
    )
    ops.append(
        dict(
            law=fx.TURNOVER,
            species=[dict(id=SD, catalogue=None, evidence=None)],
            routes=[dict(id="destroy", species=SD, node=NODE_D, kind="clearance")],
            templates=[],
        )
    )
    e = out["experiment"]
    e["exchange_controls"] = [
        dict(route_id="release", carrier_id=CELL, schedule=[dict(time=0.0, rate=uptake_velocity())])
    ]
    e["turnover_controls"] = [
        dict(
            route_id="destroy", carrier_id=None, schedule=[dict(time=0.0, rate=destruction_rate())]
        )
    ]
    return out


def exports():
    """{times, T: {donor_fmol, receiver_fmol, loss_fmol, transfer_fmol}, D: the same}, at each
    observed row once (adjacent windows share an endpoint)."""
    spec = parse_spec(world())
    species = list(spec.model.species_ids)
    nodes = [o.id for o in spec.model.extracellular]
    cell = [c.id for c in spec.model.cells].index(CELL)
    from cells.registry.models import get_model  # noqa: PLC0415

    _, p = get_model(spec.model).initial_values(spec)
    ref_c, ref_o = np.asarray(p.amount_reference), np.asarray(p.extracellular_amount_reference)
    arms = {
        "T": (species.index(ST), nodes.index(NODE_T)),
        "D": (species.index(SD), nodes.index(NODE_D)),
    }
    out = dict(
        times=[],
        **{a: dict(donor_fmol=[], receiver_fmol=[], loss_fmol=[], transfer_fmol=[]) for a in arms},
    )
    for window in iter_windows(spec, WindowPolicy(window_steps=100, recording="observations")):
        obs = window.observations
        for i, t in enumerate(np.asarray(obs.times)):
            if out["times"] and float(t) <= out["times"][-1]:
                continue  # The shared endpoint of adjacent windows.
            out["times"].append(float(t))
            inc_o = np.asarray(obs.extracellular_amount_increment)[i]
            inc_c = np.asarray(obs.amount_increment)[i]
            cleared = np.asarray(obs.turnover_outside_cleared_fmol)[i]
            moved = np.asarray(obs.exchange_moved_fmol)[i]
            for arm, (s, n) in arms.items():
                rows = out[arm]
                rows["donor_fmol"].append(float(ref_o[s, n] + inc_o[s, n]))
                rows["receiver_fmol"].append(float(ref_c[s, cell] + inc_c[s, cell]))
                rows["loss_fmol"].append(float(cleared[s, n]))
                rows["transfer_fmol"].append(float(-moved[0]) if arm == "T" else 0.0)
    return out


def control(out=None):
    """The control's readings: the two donors' largest relative difference, and each arm's
    receiver gain and cumulative loss at the last row."""
    out = exports() if out is None else out
    t, d = out["T"], out["D"]
    donors = max(abs(a - b) / b for a, b in zip(t["donor_fmol"], d["donor_fmol"], strict=True))
    return dict(
        donor_largest_relative_difference=donors,
        receiver_gain_fmol=dict(
            T=t["receiver_fmol"][-1] - t["receiver_fmol"][0],
            D=d["receiver_fmol"][-1] - d["receiver_fmol"][0],
        ),
        loss_fmol=dict(T=t["loss_fmol"][-1], D=d["loss_fmol"][-1]),
        transfer_fmol=dict(T=t["transfer_fmol"][-1], D=d["transfer_fmol"][-1]),
        donor_lost_fmol=dict(
            T=t["donor_fmol"][0] - t["donor_fmol"][-1], D=d["donor_fmol"][0] - d["donor_fmol"][-1]
        ),
        donor_against_exp=max(
            abs(v - t["donor_fmol"][0] * np.exp(-KAPPA * s)) / v
            for v, s in zip(t["donor_fmol"], out["times"], strict=True)
        ),
    )


if __name__ == "__main__":
    import json

    print(json.dumps(control(), indent=1))
