"""FR-44 step 3, admission by species (D327, D424): cells.operator.site_occupancy@1 beside
cells.operator.neutral_arrival_labels@1 and the four partners, as one compiled engine row.

The world is FR-44's twin world (tests/unit/test_neutral_labels_events.py) with the wash fixtures'
two site populations kept on the well, so S, their ligand, is not labelled. Cl and Q are labelled,
Cl half and half at the well, and Q from its base, every arrival joining its cohort from t = 0.
Beside the sites and the label owner, each of the four partners acts on a labelled row:
- the wash (cells.operator.scheduled_compartment_wash@1), at the sites' node, on FR-44's
  schedule: by half at 0.02 s, by 3/7 three times (D266's condition: inexact products
  accumulated), and whole at 0.1 s, each for a buffer with S and Q at 1e-5 mM;
- D152's reactions (cells.operator.local_species_reactions@1), making Q at the well;
- turnover (cells.operator.scheduled_species_turnover@1), making Q in the specimen;
- exchange (cells.operator.scheduled_species_exchange@1), importing Q into the specimen from well_2.
  well_2 is a second, unwashed well joined to the specimen by a copy of its patch. A route through
  a patch that faces the washed well is the wash's D263 refusal, and one that faces the held bath is
  exchange's own.
It is an invented world: no registration names it.

Its reason (D224): the compiled program with the label owner beside a split part that writes
species amounts and reports nothing is the one place a fusion change could move a physical record
(D266). Until admission by species no such composition parsed, so none had run compiled. Two
compiles: 100 s together, cold, on two CPUs shared with other work in development, where FR-44's
own twins took 70 s; measured cold on the timed lane at landing.

On the compiled runs' own histories, every 10 ms step:
- every physical field, observation and diagnostic of the labelled run is its unlabelled twin's,
  bit for bit, the sites' fields and the wash's records included (same_physics);
- at each wash, Q's material by label at the well is (1 - f) of its base plus the buffer, and
  (1 - f) of its cohort plus that step's production, within FR-44's bound. Cl's amount there is
  kept bit for bit while its shares become (1 - f) s + f at the base, and after the whole wash
  every non-base share is exactly 0;
- in the specimen, where turnover and exchange act, Q's base gains exactly what exchange imported,
  since imported material keeps well_2's shares, and its cohort exactly what turnover made, each
  within a rounding bound on every row. label_closure_relative stays at rounding;
- well_2's shares, and Cl's in both cells, keep their declared values bit for bit;
- S, the ligand, has no label row.
"""

import copy
import math

import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests.unit.test_neutral_arrival_labels import same_physics
from tests.unit.test_neutral_labels_events import (
    MAKE_Q,
    WASH_DT,
    WASH_END,
    WASHES,
    BUFFER_mM,
    Q,
    Q_mM,
)
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx
from validation.tissue import wash_schedule_fixtures as wfx

LAW = "cells.operator.neutral_arrival_labels@1"
MAKE_Q_CELL = 1e-6  # fmol/s: turnover's production of Q in the specimen.
UPTAKE_M_PER_S = 0.5  # Exchange's first-order uptake velocity, from well_2 into the specimen.
EPS = math.ulp(1.0)


def second_well(raw):
    """raw with well_2, a copy of the well and its contents, joined to the specimen by
    specimen_face_2, a copy of its patch (test_wash_schedule.py's _second_well form)."""
    out = copy.deepcopy(raw)
    m, e, x = out["model"], out["experiment"], out["execution"]
    node = copy.deepcopy(next(n for n in m["extracellular"] if n["id"] == "well"))
    node["id"] = "well_2"
    m["extracellular"].append(node)
    x["extracellular_capacity"] = len(m["extracellular"])
    patch = copy.deepcopy(next(p for p in m["membranes"] if p["id"] == "specimen_face"))
    patch.update(id="specimen_face_2", outside="well_2")
    m["membranes"].append(patch)
    x["membrane_capacity"] = len(m["membranes"])
    for c in [c for c in e["membrane_controls"] if c["membrane_id"] == "specimen_face"]:
        e["membrane_controls"].append(dict(copy.deepcopy(c), membrane_id="specimen_face_2"))
    return out


def for_q(raw):
    """raw with its last operator block's routes and species identity moved from S to Q."""
    out = copy.deepcopy(raw)
    block = out["model"]["operators"][-1]
    block["species"] = [dict(id=Q, catalogue=None, evidence=None)]
    for route in block["routes"]:
        route["species"] = Q
    return out


def sited_world(labelled=True):
    """The module docstring's world, every 10 ms step observed; `labelled` False gives its
    unlabelled twin."""
    times = [round(k * WASH_DT, 10) for k in range(round(WASH_END / WASH_DT) + 1)]
    raw = second_well(wfx.well(dt=WASH_DT, end=WASH_END, observation_times=times))
    raw = add_inventory_species(
        raw,
        Q,
        trace_mM=wfx.TRACE_mM,
        diffusivity_m2_per_s=fx.D_S,
        floor_fmol=fx.FLOOR_FMOL,
        concentrations_mM={"well": Q_mM, "well_2": Q_mM},
    )
    make = rfx.mass_action("make_q", {"outside": ["well"]}, {}, {Q: 1}, MAKE_Q)
    raw = rfx.with_reactions(raw, [rfx.species(Q, moieties={"Y": 1})], [make],
                             rfx.always(["make_q"]))  # fmt: skip
    raw = for_q(fx.with_turnover(raw, [("make_q_cell", "specimen", "production")],
                                 [("make_q_cell", "specimen", [(0.0, MAKE_Q_CELL)])]))  # fmt: skip
    raw = for_q(fx.with_exchange(raw, [("q_in", "specimen_face_2", "import", "first_order")],
                                 [("q_in", "specimen", [(0.0, UPTAKE_M_PER_S)])]))  # fmt: skip
    buffer = {wfx.TRACER: BUFFER_mM, Q: BUFFER_mM}
    raw = wfx.with_wash(raw, ["well"], [(t, "well", f, buffer) for t, f in WASHES])
    if not labelled:
        return raw
    raw["model"]["operators"].append(
        dict(
            law=LAW,
            species=[
                dict(id="Cl", labels=["base", "cohort"], initial=[
                    dict(node="well", shares={"base": 0.5, "cohort": 0.5}),
                ]),
                dict(id=Q, labels=["base", "cohort"], initial=[]),
            ],
        )
    )  # fmt: skip
    raw["experiment"]["label_arrivals"] = [
        dict(species=Q, schedule=[dict(time=0.0, label="cohort")])
    ]
    return raw


def test_sites_beside_labels_and_four_partners_keep_the_physics_and_follow_each_label():
    """FR-44 step 3 (D327, D424; module docstring), on the compiled runs' own histories, one row
    per step. The row at a wash's time holds the state the wash acts on."""
    spec = parse_spec(sited_world())
    labelled, plain = run(spec), run(parse_spec(sited_world(labelled=False)))
    same_physics(labelled, plain)
    _, p = get_model(spec.model).initial_values(spec)
    h = labelled.history
    ids = list(spec.model.species_ids)
    cells = [c.id for c in spec.model.cells]
    outside = [c.id for c in spec.model.extracellular]
    q, cl, s = ids.index(Q), ids.index("Cl"), ids.index(wfx.TRACER)
    w, w2, sp = outside.index("well"), outside.index("well_2"), cells.index("specimen")
    rows_labelled = np.asarray(p.label_rows).tolist()
    assert s not in rows_labelled  # S, the ligand, has no label row.
    jcl, jq = rows_labelled.index(cl), rows_labelled.index(q)
    steps = np.arange(np.asarray(h.amount_increment).shape[0])

    # The well: Q made into its open window and washed with the buffer at the base (FR-44's rows).
    q_anchor = float(p.extracellular_amount_reference[q, w])
    nq = q_anchor + np.asarray(h.extracellular_amount_increment)[:, q, w]
    q_shares = np.asarray(h.label_outside_share)[:, jq, :, w]
    q_sample = np.asarray(h.wash_last_sample_fmol)[:, q, w]
    q_supply = np.asarray(h.wash_last_supply_fmol)[:, q, w]
    cl_shares = np.asarray(h.label_outside_share)[:, jcl, :, w]
    for t, f in WASHES:
        k = round(t / WASH_DT)
        r, a = q_sample[k + 1], q_supply[k + 1]
        assert r == f * nq[k], t  # The event's own sample, never a cumulative record's gain.
        made = nq[k + 1] - (nq[k] - r + a)  # The step's production, after the event.
        assert made > 0, t
        bound = 8 * EPS * (abs(q_anchor) + nq[k] + a + made)
        base = (1 - f) * nq[k] * q_shares[k, 0] + a
        cohort = (1 - f) * nq[k] * q_shares[k, 1] + made
        assert abs(nq[k + 1] * q_shares[k + 1, 0] - base) <= bound, t
        assert abs(nq[k + 1] * q_shares[k + 1, 1] - cohort) <= bound, t
        diluted = (1 - f) * cl_shares[k] + f * np.array([1.0, 0.0])
        assert np.allclose(cl_shares[k + 1], diluted, rtol=0, atol=4 * EPS), t
    cl_amount = (
        float(p.extracellular_amount_reference[cl, w])
        + np.asarray(h.extracellular_amount_increment)[:, cl, w]
    )
    assert len({x.tobytes() for x in cl_amount}) == 1  # Kept bit for bit.
    assert cl_shares[-1].tolist() == [1.0, 0.0]  # The whole wash leaves no cohort behind.

    # The specimen: exchange's import keeps well_2's base, turnover's production joins the cohort.
    anchor = float(p.amount_reference[q, sp])
    n = anchor + np.asarray(h.amount_increment)[:, q, sp]
    shares = np.asarray(h.label_share)[:, jq, :, sp]
    imported = -np.asarray(h.exchange_moved_fmol)[:, 0]  # Export positive.
    produced = np.asarray(h.turnover_produced_fmol)[:, q, sp]
    assert imported[-1] > 0 and produced[-1] > 0
    scale = abs(anchor) + n[0] + imported + produced
    bound = (1 + 16 * steps) * EPS * scale  # 4 eps per reporter half-step applied.
    assert np.all(np.abs(n * shares[:, 0] - (n[0] + imported)) <= bound)
    assert np.all(np.abs(n * shares[:, 1] - produced) <= bound)
    assert float(np.max(np.asarray(h.label_closure_relative))) <= 64 * EPS

    # What nothing labels or moves keeps its declared shares bit for bit.
    q_well_2 = np.asarray(h.label_outside_share)[:, jq, :, w2]
    assert q_well_2.tobytes() == np.tile([1.0, 0.0], (len(steps), 1)).tobytes()
    cl_cells = np.asarray(h.label_share)[:, jcl]
    assert all(cl_cells[i].tobytes() == cl_cells[0].tobytes() for i in steps)
