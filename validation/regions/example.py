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

**FR-33's labels are FR-42's shares** (D289; D300 retired D1's label families, rows of their own
with their own potentials). In each world below, one protein row `P` carries the labels as shares
(cells.operator.neutral_arrival_labels@1), and two plain rows of the same material, `P_L` (labelled) and `P_U`
(unlabelled), each node's `P` their sum, ride beside it as the exact reference: every law that moves
them is linear in each row, so each row's move is exact, while the shares follow at the label
owner's second order. The record reads the label by its shares (readouts.label_nodes) and by `P_L`.

**FR-33's acceptance on the synapse regions** (synapse_world): two synapse regions, finite outside
nodes `syn_1` and `syn_2` of 1 pL, joined by a face that diffuses the protein at R_SYNAPSE per
node, each bounded by a contact patch to the cell that nothing crosses. `P_L` starts at 1 mM in
syn_1 and `P_U` at 1 mM in syn_2, each 0.1 mM elsewhere. With `degrade`, turnover clears `P`, `P_L`
and `P_U` in syn_1 alike. The label moves both ways across the face (pure redistribution, its total
stable) or is also degraded.
- **Why not two compartments of one cell:** a cell-owned compartment can carry no face, and no
  constant-field route without a declared kind, and turnover refuses a species that permeates a
  patch or a junction (it would have no material-rate bound). So within one cell the engine cannot
  yet diffuse a cleared protein between two compartments: an engine gap, recorded for FR-33.

**FR-33's first test, as its requester asked** (first_test_world and first_test; the requester's
answer, relayed by the user on 22 November 2026: "Two named regions of the same cell joined by one
bidirectional face are sufficient for our first test"). Two named regions, `donor` and `receiver`,
finite nodes of FIRST_TEST_VOLUME_pL each, joined by one bidirectional face. The label starts at
1 mM in the donor (`P_L`), the rest of the protein at 1 mM in the receiver (`P_U`), each at the
usual 1e-9 mM trace elsewhere, so the receiver starts with no label. The face books its heat exactly
(heat_bookings: faces cells.heat.exact_free_energy_heat@1, F2), which keeps the energy ledger closed from a
trace start. No labelled production is declared.
- **Case "transfer":** the face open, and no turnover at all. The label total is conserved and the
  receiver's gain is the donor's loss.
- **Case "local_loss",** the local-loss control: the face closed for the protein and turnover
  clearing it at the donor. The receiver stays flat, and the cumulative clearance accounts for the
  donor's missing label. Turnover is declared in this case only: F2's version 1 refuses an
  operator's in-step writer on a row an exact face carries, so the open face and turnover on the
  same rows cannot share a world.
- **The record's "whole-cell label"** is the label summed over the two regions. The regions are
  nodes joined by a face, not compartments of a cell, so that sum is the definition, stated in the
  record. The cell's own small label, which nothing moves, is not counted.
- Every readout is in fmol, at the same saved times (the world's observation times), and each
  region keeps its ID and declared volume in the record.

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
R_SYNAPSE = 1.0  # 1/s: each synapse region's exchange rate through their face.
K_DEGRADE = 0.5  # 1/s: the protein's clearance in syn_1, when degraded.
SYNAPSES = ("syn_1", "syn_2")
REFERENCE = ("P_L", "P_U")  # The label's exact reference rows: labelled, then unlabelled.
LABELS_LAW = "cells.operator.neutral_arrival_labels@1"


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


def _labelled_protein(raw, labels, homes, diffusivity, trace):
    """raw with the protein row P (each node holding P_L's and P_U's sum, their split its shares,
    labels[0] for P_L's material) and the label owner: homes {node: (P_L mM, P_U mM)} at the nodes
    that differ from the trace, `trace` mM of each elsewhere."""
    nodes = [c["id"] for c in raw["model"]["cells"]]
    nodes += [o["id"] for o in raw["model"]["extracellular"] if not o.get("reservoir")]
    held = {n: homes.get(n, (trace, trace)) for n in nodes}
    raw = add_inventory_species(
        raw,
        "P",
        trace_mM=2 * trace,
        diffusivity_m2_per_s=diffusivity,
        floor_fmol=base.fx.FLOOR_FMOL,
        concentrations_mM={n: a + b for n, (a, b) in held.items()},
    )
    initial = [
        dict(node=n, shares={labels[0]: a / (a + b), labels[1]: b / (a + b)})
        for n, (a, b) in held.items()
    ]
    raw["model"]["operators"].append(
        dict(law=LABELS_LAW, species=[dict(id="P", labels=list(labels), initial=initial)])
    )
    raw["experiment"]["label_arrivals"] = []
    return raw


def _cleared_alike(raw, rows, node, rate, prefix):
    """raw with turnover clearing each of `rows` at `node` at `rate`, alike."""
    raw["model"]["operators"].append(dict(
        law=base.fx.TURNOVER,
        species=[dict(id=r, catalogue=None, evidence=None) for r in rows],
        routes=[dict(id=f"{prefix}_{r}", species=r, node=node, kind="clearance") for r in rows],
        templates=[],
    ))  # fmt: skip
    raw["experiment"]["turnover_controls"] = [
        dict(route_id=f"{prefix}_{r}", carrier_id=None, schedule=[dict(time=0.0, rate=rate)])
        for r in rows
    ]
    return raw


def synapse_world(*, degrade=0.0, dt=1e-3, steps=200):
    """FR-33's acceptance world on the synapse regions (module docstring): the label as P's shares
    beside its exact reference rows P_L and P_U; turnover clears P, P_L and P_U in syn_1 at
    `degrade` (1/s) alike, so a zero rate and a positive one share one program."""
    pl_m3 = 1e-15
    diffusivity = R_SYNAPSE * FACE_LENGTH_M * pl_m3 / FACE_AREA_M2  # r = D A / (L V), V = 1 pL.
    end = dt * steps
    raw = base.fx.world(
        cells=((base.CELL, 1.0),),
        nodes=tuple((s, 1.0) for s in SYNAPSES),
        contacts=(("contact_1", base.CELL, "syn_1"), ("contact_2", base.CELL, "syn_2")),
        faces=(("face_12", "syn_1", "syn_2", FACE_AREA_M2, FACE_LENGTH_M),),
        dt=dt,
        end=end,
        observation_times=base.fx.grid_times(end, dt, end / 10),
        diffusivity=diffusivity,
    )
    for name, node in zip(REFERENCE, SYNAPSES, strict=True):
        # 1 mM where it starts and 0.1 mM elsewhere: the protein's total is even, so only the
        # labels move (at a 1e-9 mM trace a node's face terms failed the energy ledger's check).
        others = {n: 0.1 for n in (base.CELL, *SYNAPSES) if n != node}
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=base.fx.TRACE_mM,
            diffusivity_m2_per_s=diffusivity,
            floor_fmol=base.fx.FLOOR_FMOL,
            concentrations_mM={node: 1.0, **others},
        )
    homes = {SYNAPSES[0]: (1.0, 0.1), SYNAPSES[1]: (0.1, 1.0), base.CELL: (0.1, 0.1)}
    raw = _labelled_protein(raw, ("labelled", "unlabelled"), homes, diffusivity, base.fx.TRACE_mM)
    return _cleared_alike(raw, ("P", *REFERENCE), "syn_1", degrade, "degrade")


FIRST_TEST_REGIONS = ("donor", "receiver")
FIRST_TEST_VOLUME_pL = 1.0
FIRST_TEST_CLEARANCE = 0.5  # 1/s: the local-loss control's clearance at the donor.
FIRST_TEST_CASES = ("transfer", "local_loss")
WHOLE_CELL_LABEL = (
    "the label summed over the two regions, donor and receiver: they are finite nodes joined by "
    "one face, not compartments of a cell, so that sum is the definition (the cell's own small "
    "label, which nothing moves, is not counted)"
)


def first_test_world(case, *, dt=1e-3, steps=200):
    """FR-33's first test (module docstring): case "transfer" (the face open, no turnover) or
    "local_loss" (the face closed for both rows, turnover clearing both at the donor, alike). Each
    starts the label at the usual trace outside its own region, with the face's heat booked
    exactly (F2)."""
    if case not in FIRST_TEST_CASES:
        raise ValueError(f"the case is one of {FIRST_TEST_CASES}")
    donor, receiver = FIRST_TEST_REGIONS
    pl_m3 = 1e-15
    diffusivity = R_SYNAPSE * FACE_LENGTH_M * pl_m3 / FACE_AREA_M2  # r = D A / (L V), V = 1 pL.
    end = dt * steps
    raw = base.fx.world(
        cells=((base.CELL, 1.0),),
        nodes=tuple((r, FIRST_TEST_VOLUME_pL) for r in FIRST_TEST_REGIONS),
        contacts=(("contact_donor", base.CELL, donor), ("contact_receiver", base.CELL, receiver)),
        faces=(("face_dr", donor, receiver, FACE_AREA_M2, FACE_LENGTH_M),),
        dt=dt,
        end=end,
        observation_times=base.fx.grid_times(end, dt, end / 10),
        diffusivity=diffusivity,
    )
    trace = base.fx.TRACE_mM
    for name, node in zip(REFERENCE, (donor, receiver), strict=True):
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=trace,
            diffusivity_m2_per_s=diffusivity,
            floor_fmol=base.fx.FLOOR_FMOL,
            concentrations_mM={node: 1.0},  # The usual trace elsewhere.
        )
    homes = {donor: (1.0, trace), receiver: (trace, 1.0)}
    raw = _labelled_protein(raw, FIRST_TEST_REGIONS, homes, diffusivity, trace)
    m = raw["model"]
    m["heat_bookings"] = {"faces": "cells.heat.exact_free_energy_heat@1"}  # F2: exact from a trace start.
    if case == "transfer":
        return raw
    (face,) = m["faces"]  # The local-loss control: the face closed for the protein, alike.
    face["diffusivity_m2_per_s"].update(dict.fromkeys(("P", *REFERENCE), 0.0))
    return _cleared_alike(raw, ("P", *REFERENCE), donor, FIRST_TEST_CLEARANCE, "clear")


def first_test(case, result=None):
    """FR-33's first test's record for one case (module docstring): the regions with their IDs and
    declared volumes, the definitions, and the donor's, the receiver's and the whole-cell label and
    the donor's cumulative clearance, all in fmol at the world's observation times, by the label's
    shares (readouts.label_nodes) and, beside them, by the exact reference row P_L. result: (spec,
    times, states) of a run of first_test_world(case), or None to run it."""
    if result is None:
        spec = parse_spec(first_test_world(case))
        times, states = readouts.runs(spec)
    else:
        spec, times, states = result
    from cells.registry.models import get_model

    _, layout = get_model(spec.model).initial_values(spec)
    donor, receiver = FIRST_TEST_REGIONS
    volumes = {o.id: o.volume_pL for o in spec.model.extracellular}
    observed = spec.experiment.observation_times
    shared = readouts.label_nodes(spec, times, states, "P", donor, samples=observed)
    protein, reference = readouts.world_map(spec, "P"), readouts.world_map(spec, REFERENCE[0])
    nodes = {r: protein["nodes"].index(r) for r in FIRST_TEST_REGIONS}
    outside = [o.id for o in spec.model.extracellular]
    out = dict(
        case=case,
        regions=[dict(id=r, node=r, volume_pL=float(volumes[r])) for r in FIRST_TEST_REGIONS],
        labels=dict(species="P", label=donor, owner=LABELS_LAW, reference=REFERENCE[0]),
        units="fmol",
        definitions=dict(
            whole_cell_label_fmol=WHOLE_CELL_LABEL,
            cleared_fmol="turnover's cumulative clearance of the protein at the donor times the "
            "label's share there (constant, since nothing arrives at the donor in that case)",
        ),
        times_s=list(shared["times"]),
        donor_label_fmol=list(shared["node_fmol"][donor]),
        receiver_label_fmol=list(shared["node_fmol"][receiver]),
        whole_cell_label_fmol=[a + b for a, b in zip(shared["node_fmol"][donor],
                                                     shared["node_fmol"][receiver], strict=True)],
        cleared_fmol=[],
        reference_fmol=dict(donor=[], receiver=[], cleared=[]),
    )  # fmt: skip
    for t in observed:
        state = states[readouts.step_index(times, t, "a saved time")]
        _, _, lost, _ = readouts.node_records(spec, layout, state, protein)
        exact, _, lost_exact, _ = readouts.node_records(spec, layout, state, reference)
        share = float(state.label_outside_share[0, 0, outside.index(donor)])
        out["cleared_fmol"].append(float(lost[nodes[donor]]) * share)
        out["reference_fmol"]["donor"].append(float(exact[nodes[donor]]))
        out["reference_fmol"]["receiver"].append(float(exact[nodes[receiver]]))
        out["reference_fmol"]["cleared"].append(float(lost_exact[nodes[donor]]))
    return out


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
