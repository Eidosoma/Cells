"""FR-42's stage 2 as engine rows: labels carried by @3's routes (D289), against plain rows of the
same material in the same world, whose transport is linear in each row and so the exact
reference. The routes' world compiled twice, labelled and as its unlabelled twin, about 60 s
(FR-33's two cases, the faces' rows, are in tests/unit/test_region_label_shares.py).

- **Routes:** Q labelled a and b as shares, beside Q_a and Q_b as plain rows. It moves between
  two cells by a junction and from each cell to their outside node by a membrane route
  (cells.route.constant_field@1, linear in each end for an uncharged row), and the shares follow the exact
  rows within 2e-6 at every node, at the share update's and @3's trapezoid's second order, and the
  labelled run's records are its unlabelled twin's bit for bit. (The label's total over the nodes
  holds to that second order in general; here it held at rounding, 3.7e-16, with no loss.)
- **RK4:** labels moved in the step are refused under RK4 (parses only).
"""

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.registry.inventory_species import add_inventory_species
from validation.regions import readouts
from validation.tissue import secreted_species_fixtures as fx

EPS = np.finfo(float).eps
LAW = "cells.operator.neutral_arrival_labels@1"
ROUTE_PERMEABILITY = 1e-4  # m/s: about 1/s through each 1e-11 m^2 patch or junction, 1 pL a node.
CELLS, NODE = ("cell_0", "cell_1"), "ecs_0"


def routes_world(*, dt=1e-3, steps=100):
    """Two cells joined by a gated junction, each by a contact patch to the outside node: the plain
    rows Q_a (1 mM in cell_0) and Q_b (1 mM in cell_1), each 0.1 mM at the other two nodes (at a
    1e-9 mM trace the routes' heat failed the energy ledger's check, as the synapse world's faces
    did), and Q, their sum at every node with their split as its shares, crossing the patches and
    the junction alike."""
    end, trace = dt * steps, fx.TRACE_mM
    raw = fx.world(
        cells=tuple((c, 1.0) for c in CELLS),
        nodes=((NODE, 1.0),),
        contacts=tuple((f"contact_{k}", c, NODE) for k, c in enumerate(CELLS)),
        junctions=(("gj_0", *CELLS),),
        faces=(),
        dt=dt,
        end=end,
        observation_times=fx.grid_times(end, dt, end / 4),
    )
    held = {
        "Q_a": {CELLS[0]: 1.0, CELLS[1]: 0.1, NODE: 0.1},
        "Q_b": {CELLS[0]: 0.1, CELLS[1]: 1.0, NODE: 0.1},
    }
    held["Q"] = {n: held["Q_a"][n] + held["Q_b"][n] for n in (*CELLS, NODE)}
    for name in ("Q_a", "Q_b", "Q"):
        raw = add_inventory_species(
            raw,
            name,
            trace_mM=2 * trace if name == "Q" else trace,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM=held[name],
        )
    m = raw["model"]
    for entity in (*m["membranes"], *m["junctions"]):
        if entity["id"].startswith(("contact_", "gj_")):
            entity["permeability_m_per_s"].update(
                dict.fromkeys(("Q", "Q_a", "Q_b"), ROUTE_PERMEABILITY)
            )
    initial = [
        dict(node=n, shares=dict(a=held["Q_a"][n] / held["Q"][n], b=held["Q_b"][n] / held["Q"][n]))
        for n in (*CELLS, NODE)
    ]
    m["operators"].append(dict(law=LAW, species=[dict(id="Q", labels=["a", "b"], initial=initial)]))
    raw["experiment"]["label_arrivals"] = []
    return raw


def test_routes_carry_the_shares_with_the_exact_rows():
    """The junction and the membrane routes' one-way transfers (@3's side) carry Q's shares: at
    every saved time and node, Q times its share a matches the plain row Q_a within 2e-6 of Q_a's
    scale, and the closure diagnostic reads rounding. The world run without the label owner, its
    twin, has every history field, observation and diagnostic of the labelled run bit for bit:
    @3's transfers are non-zero here, and change nothing physical."""
    import copy

    from cells.execution.runner import run
    from cells.registry.models import get_model

    raw = routes_world()
    twin = copy.deepcopy(raw)
    twin["model"]["operators"] = [o for o in twin["model"]["operators"] if o["law"] != LAW]
    del twin["experiment"]["label_arrivals"]
    labelled, plain = run(parse_spec(raw)), run(parse_spec(twin))
    for name in type(plain.history)._fields:
        assert (
            np.asarray(getattr(labelled.history, name)).tobytes()
            == np.asarray(getattr(plain.history, name)).tobytes()
        ), name
    for name, value in vars(plain.observations).items():
        assert (
            np.asarray(getattr(labelled.observations, name)).tobytes()
            == np.asarray(value).tobytes()
        ), name
    assert labelled.diagnostics == plain.diagnostics
    spec = parse_spec(raw)
    times, states = readouts.runs(spec)
    _, layout = get_model(spec.model).initial_values(spec)
    shared, reference = readouts.world_map(spec, "Q"), readouts.world_map(spec, "Q_a")
    outside = [o.id for o in spec.model.extracellular]
    scale = None
    for t in spec.experiment.observation_times:
        state = states[readouts.step_index(times, t, "a saved time")]
        amount = readouts.node_records(spec, layout, state, shared)[0]
        exact = readouts.node_records(spec, layout, state, reference)[0]
        scale = scale or float(np.max(np.abs(exact)))
        for k, c in enumerate(CELLS):
            node = shared["nodes"].index(c)
            labelled = float(amount[node]) * float(state.label_share[0, 0, k])
            assert abs(labelled - float(exact[node])) <= 2e-6 * scale, (t, c)
        node = shared["nodes"].index(NODE)
        labelled = float(amount[node]) * float(state.label_outside_share[0, 0, outside.index(NODE)])
        assert abs(labelled - float(exact[node])) <= 2e-6 * scale, (t, NODE)
    assert float(np.max(states[-1].label_closure_relative)) <= 64 * EPS
    moved = float(
        readouts.node_records(spec, layout, states[-1], reference)[0][shared["nodes"].index(NODE)]
    )
    assert moved > 0.01 * scale  # The label reached the outside node.


def test_labels_moved_in_the_step_are_refused_under_rk4():
    """Version 1 follows labels through the IMEX step only: RK4 beside a followed mover (here the
    routes) is refused at the definition, naming FR-42 (parses only)."""
    from cells.definitions.specs import ConfigError

    raw = routes_world()
    raw["execution"]["solver"] = "rk4"
    with pytest.raises(ConfigError, match=r"follows labels through the IMEX step only, not RK4"):
        parse_spec(raw)
