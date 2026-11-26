"""FR-42's replacement event report (D296; erratum E, docs/TEMPLATED_POLYMERISATION_LAWS.md
§9.18) as one compiled engine row: what leaves at a replacement is recorded by label (FR-38's
step 5). And FR-44's labels across washes (D327) as a second: the twins below.

The replacement world is compiled once (about 20 s on a light CPU; the owner's event update and
the composite's event line run only in a compiled composition, which the NumPy rows in
tests/unit/test_neutral_arrival_labels.py do not reach). Two cells; replacement@1 swaps cell_0's
occupant for a template at 2 ms, and cell_1 keeps its own. S is labelled base, old and newcomer:
cell_0 starts a quarter base and three quarters old, cell_1 all old, and every arrival joins
newcomer from 2 ms. Nothing moves S between nodes, so its shares change only at the event.
- Before the event the record is zero. From the step that leaves 2 ms, cell_0's record is its S
  just before the event times those shares, a quarter base and three quarters old, and it stays
  there (cumulative, one event). cell_1's stays zero.
- After the event cell_0's S is the template's, all newcomer, and cell_1 keeps its shares bit for
  bit.

FR-44's twins (D327), the labelled run and its unlabelled twin, two compiles (about 35 s together
on a light CPU). Their reason (D224): the compiled event with its report is the one place where a
fusion change could move a physical record (D266), and the NumPy rows cannot see one. The world
is the wash fixtures' well without sites, since sites are refused beside labels. It is washed by
half at 0.02 s, by 3/7 three times (D266's condition: inexact products accumulated), and whole at
0.1 s, each wash for a buffer with S at 1e-5 mM (5 fmol at the first, against the well's 60).
- S is labelled base and cohort: 2/3 and 1/3 at the well, 1/4 and 3/4 in the specimen. The
  cohort's window is open from t = 0, so the base taking each buffer is the ruling, not a default.
- Cl, an ion, is labelled 1/2 and 1/2 at the well.
- Q is made at the well by a reaction (cells.operator.local_species_reactions@1, a reporter) at 100 fmol/s, into
  its cohort's open window, and is washed with S. It carries the triple of the labels, the wash
  and the reactions at the washed node, which FR-44 newly admits.
Its resume across a wash is in tests/unit/test_wash_schedule_resume.py.
"""

import math
from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.inventory_species import add_inventory_species
from cells.registry.models import get_model
from tests.unit.test_neutral_arrival_labels import same_physics
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import species_reactions_fixtures as rfx
from validation.tissue import wash_schedule_fixtures as wfx

LAW = "cells.operator.neutral_arrival_labels@1"
DT, END, EVENT = 1e-3, 4e-3, 2e-3
SHARES = {"cell_0": {"base": 0.25, "old": 0.75}, "cell_1": {"old": 1.0}}


def replaced_world():
    """The module docstring's world: two 1 pL cells at 1 mM S, cell_0 replaced at 2 ms by a template
    at 2 mM, every millisecond observed."""
    raw = fx.world(
        cells=(("cell_0", 1.0), ("cell_1", 1.0)),
        faces=(),
        concentrations_mM={"cell_0": 1.0, "cell_1": 1.0},
        dt=DT,
        end=END,
        observation_times=fx.grid_times(END, DT, DT),
    )
    template = fx.template(raw, "cell_0", "fresh", s_mM=2.0)
    raw = fx.with_replacement(raw, [template], [(EVENT, "cell_0", "fresh", "carrier_1")])
    raw["model"]["operators"].append(
        dict(
            law=LAW,
            species=[
                dict(
                    id="S",
                    labels=["base", "old", "newcomer"],
                    initial=[dict(node=n, shares=dict(s)) for n, s in SHARES.items()],
                )
            ],
        )
    )
    raw["experiment"]["label_arrivals"] = [
        dict(species="S", schedule=[dict(time=EVENT, label="newcomer")])
    ]
    return raw


def test_a_replacement_records_what_left_by_label():
    """The record (label_removed_fmol [labelled species, label, cell]) and the shares at every
    observed millisecond (module docstring), from the compiled run's own observations."""
    spec = parse_spec(replaced_world())
    result = run(spec)
    obs = result.observations
    times = np.asarray(spec.experiment.observation_times)
    s = list(spec.model.species_ids).index("S")
    amount = np.asarray(obs.amount)[:, s, :]  # [time, cell]
    record = np.asarray(obs.label_removed_fmol)[:, 0]  # [time, label, cell]
    share = np.asarray(obs.label_share)[:, 0]
    before, after = times <= EVENT + 1e-12, times > EVENT + 1e-12
    assert before.sum() == 3 and after.sum() == 2  # 0, 1 and 2 ms; 3 and 4 ms.
    assert np.all(record[before] == 0.0)
    leaving = amount[before][-1, 0]  # cell_0's S just before the event: its 1 fmol.
    assert leaving == pytest.approx(1.0, rel=1e-15)
    for row in record[after]:
        assert row[:, 0].tolist() == [leaving * 0.25, leaving * 0.75, 0.0]
        assert np.all(row[:, 1] == 0.0)  # cell_1 was not replaced.
    assert amount[after][0, 0] == pytest.approx(2.0, rel=1e-15)  # The template's S.
    assert np.all(share[after][:, :, 0] == [0.0, 0.0, 1.0])  # Newcomer material only.
    kept = np.tile([0.0, 1.0, 0.0], (len(times), 1))  # cell_1's shares, bit for bit.
    assert np.asarray(share)[:, :, 1].tobytes() == kept.tobytes()
    assert np.asarray(obs.label_pool_removed_fmol).size == 0  # No pool reporter: zero-size.


# ------------------------------------------------------------------ FR-44: labels across washes

WASH_DT, WASH_END = 0.01, 0.12  # s
WASHES = ((0.02, 0.5), (0.04, 3 / 7), (0.06, 3 / 7), (0.08, 3 / 7), (0.10, 1.0))  # (s, 1)
BUFFER_mM = 1e-5  # S's and Q's buffer at every wash.
Q, Q_mM, MAKE_Q = "Q", 1e-5, 1e-4  # Q at the well (10 fmol), made there at 1e-4 mM/s (100 fmol/s).
EPS = math.ulp(1.0)


def washed_world(labelled=True, *, made=True):
    """FR-44's twin world (module docstring), every 10 ms step observed; `labelled` False gives
    its unlabelled twin, and `made` False leaves Q and its reaction out (the resume's lighter
    world)."""
    times = [round(k * WASH_DT, 10) for k in range(round(WASH_END / WASH_DT) + 1)]
    raw = wfx.well(sites=False, dt=WASH_DT, end=WASH_END, observation_times=times)
    buffer = {wfx.TRACER: BUFFER_mM}
    if made:
        raw = add_inventory_species(
            raw,
            Q,
            trace_mM=wfx.TRACE_mM,
            diffusivity_m2_per_s=fx.D_S,
            floor_fmol=fx.FLOOR_FMOL,
            concentrations_mM={"well": Q_mM},
        )
        make = rfx.mass_action("make_q", {"outside": ["well"]}, {}, {Q: 1}, MAKE_Q)
        raw = rfx.with_reactions(raw, [rfx.species(Q, moieties={"Y": 1})], [make],
                                 rfx.always(["make_q"]))  # fmt: skip
        buffer[Q] = BUFFER_mM
    raw = wfx.with_wash(raw, ["well"], [(t, "well", f, buffer) for t, f in WASHES])
    if not labelled:
        return raw
    raw["model"]["operators"].append(
        dict(
            law=LAW,
            species=[
                dict(id=wfx.TRACER, labels=["base", "cohort"], initial=[
                    dict(node="well", shares={"base": 2 / 3, "cohort": 1 / 3}),
                    dict(node="specimen", shares={"base": 0.25, "cohort": 0.75}),
                ]),
                dict(id="Cl", labels=["base", "cohort"], initial=[
                    dict(node="well", shares={"base": 0.5, "cohort": 0.5}),
                ]),
                *([dict(id=Q, labels=["base", "cohort"], initial=[])] if made else []),
            ],
        )
    )  # fmt: skip
    raw["experiment"]["label_arrivals"] = [
        dict(species=name, schedule=[dict(time=0.0, label="cohort")])
        for name in (wfx.TRACER, Q)[: 2 if made else 1]
    ]
    return raw


def test_labels_follow_each_wash_exactly_and_leave_the_physics_bit_for_bit():
    """FR-44 (D327; module docstring), on the compiled runs' own histories, one row per step. The
    row at a wash's time holds the state the wash acts on.
    - Every physical field, observation and diagnostic is the unlabelled twin's, bit for bit
      (same_physics): the report only reads the wash's own records, so no physical record moves.
    - At each wash the report's sample is that event's own, f n. S's material by label after it is
      (1 - f) n s_k, and the base's is that plus the buffer a, though the cohort's window is open.
      Each holds within 4 ulps of the new amount plus the anchored rounding eps (|anchor| + n + a).
    - The record after the first wash is 30 x (2/3, 1/3) fmol, bit for bit. Each later wash adds
      its sample times the shares just before it.
    - The books on every row: each label's material at the well, plus what left it, less the
      buffer at the base, is its start, within (1 + 4 per wash so far) eps of the node's stored
      scale.
    - Cl's amount at the well is kept bit for bit, while its shares become (1 - f) s + f at the
      base.
    - After the whole wash every non-base share is exactly 0, S's and Cl's alike.
    - The cells keep their shares bit for bit.
    - Q, made at the well into the open window (labels, the wash and the reactions together): on
      each row after a wash, its base is (1 - f) of its base plus the buffer, and its cohort is
      (1 - f) of its cohort plus that step's production, within 8 eps of the stored scale."""
    spec = parse_spec(washed_world())
    labelled, plain = run(spec), run(parse_spec(washed_world(labelled=False)))
    same_physics(labelled, plain)
    _, p = get_model(spec.model).initial_values(spec)
    h = labelled.history
    ids, outside = list(spec.model.species_ids), [c.id for c in spec.model.extracellular]
    s, cl, w = ids.index(wfx.TRACER), ids.index("Cl"), outside.index("well")
    anchor = float(p.extracellular_amount_reference[s, w])
    n = anchor + np.asarray(h.extracellular_amount_increment)[:, s, w]
    shares = np.asarray(h.label_outside_share)[:, 0, :, w]  # [row, label]
    record = np.asarray(h.label_outside_removed_fmol)[:, 0, :, w]
    sample = np.asarray(h.wash_last_sample_fmol)[:, s, w]
    supply = np.asarray(h.wash_last_supply_fmol)[:, s, w]
    cl_shares = np.asarray(h.label_outside_share)[:, 1, :, w]
    for t, f in WASHES:
        k = round(t / WASH_DT)
        r, a, after = sample[k + 1], supply[k + 1], n[k + 1]
        assert r == f * n[k], t  # The event's own sample, never a cumulative record's gain.
        bound = Fraction(4 * float(np.spacing(after)) + EPS * (abs(anchor) + n[k] + a))
        for label in (0, 1):
            exact = (1 - Fraction(f)) * Fraction(n[k]) * Fraction(shares[k, label])
            exact += Fraction(a) if label == 0 else 0
            assert abs(Fraction(after) * Fraction(shares[k + 1, label]) - exact) <= bound, (
                t,
                label,
            )
        assert np.allclose(record[k + 1], record[k] + r * shares[k], rtol=2 * EPS, atol=0), t
        diluted = (1 - f) * cl_shares[k] + f * np.array([1.0, 0.0])
        assert np.allclose(cl_shares[k + 1], diluted, rtol=0, atol=4 * EPS), t
    first = round(WASHES[0][0] / WASH_DT) + 1
    assert record[first].tobytes() == (30.0 * np.array([2 / 3, 1 / 3])).tobytes()
    supplied = np.asarray(h.wash_supplied_fmol)[:, s, w]
    rows = np.arange(len(n))
    washes = np.searchsorted([round(t / WASH_DT) + 1 for t, _ in WASHES], rows, side="right")
    scale = abs(anchor) + n.max() + supplied.max()
    books = (
        n[:, None] * shares + record - supplied[:, None] * np.array([1.0, 0.0]) - n[0] * shares[0]
    )
    assert np.all(np.abs(books) <= ((1 + 4 * washes) * EPS * scale)[:, None])
    cl_amount = (
        float(p.extracellular_amount_reference[cl, w])
        + np.asarray(h.extracellular_amount_increment)[:, cl, w]
    )
    assert len({x.tobytes() for x in cl_amount}) == 1  # Kept bit for bit.
    assert shares[-1].tolist() == [1.0, 0.0] and cl_shares[-1].tolist() == [1.0, 0.0]
    cells = np.asarray(h.label_share)
    assert all(cells[i].tobytes() == cells[0].tobytes() for i in rows)
    # Q, made at the well into its open window: the step after each wash also makes Q, which joins
    # the cohort, while the buffer joins the base.
    q = ids.index(Q)
    q_anchor = float(p.extracellular_amount_reference[q, w])
    nq = q_anchor + np.asarray(h.extracellular_amount_increment)[:, q, w]
    q_shares = np.asarray(h.label_outside_share)[:, 2, :, w]  # Q is the third labelled species.
    q_sample = np.asarray(h.wash_last_sample_fmol)[:, q, w]
    q_supply = np.asarray(h.wash_last_supply_fmol)[:, q, w]
    for t, f in WASHES:
        k = round(t / WASH_DT)
        r, a = q_sample[k + 1], q_supply[k + 1]
        assert r == f * nq[k], t
        made = nq[k + 1] - (nq[k] - r + a)  # The step's production, after the event.
        assert made > 0, t
        bound = 8 * EPS * (abs(q_anchor) + nq[k] + a + made)
        base = (1 - f) * nq[k] * q_shares[k, 0] + a
        cohort = (1 - f) * nq[k] * q_shares[k, 1] + made
        assert abs(nq[k + 1] * q_shares[k + 1, 0] - base) <= bound, t
        assert abs(nq[k + 1] * q_shares[k + 1, 1] - cohort) <= bound, t


# ------------------------------------------------------------------ amendment G: derived producers


def chase(kind):
    """FR-38's step-5 world (validation/gene_regulation/replace_restart.py), its producer declared
    `producers` and derived (amendment G), or hand-written correctly in the derivation's own
    convention: each generation's label, then its window's, and the source's schedule."""
    from cells.operators import species_labels as labels
    from validation.gene_regulation import replace_restart as rr

    raw = rr.chase_world()  # It declares its producers (amendment G; the gene lane's Work 3).
    owner = next(o for o in raw["model"]["operators"] if o["law"] == labels.LAW_ID)
    g0, g1 = rr.G0, rr.G1
    if kind == "derived":
        return raw
    for entry in owner["species"]:
        entry.pop("producers")
        entry["labels"] = ["base", g0, f"{g0}-cohort", g1, f"{g1}-cohort"]
    schedule = [
        dict(time=0.0, label=f"{g0}-cohort"), dict(time=rr.W, label=g0), dict(time=rr.T_E, label=g1)
    ]  # fmt: skip
    raw["experiment"]["label_arrivals"].append(
        dict(species=rr.ROWS[0], source=rr.CHAIN, schedule=schedule)
    )
    return raw


def test_derived_producer_labels_are_a_correct_hand_written_declaration_bit_for_bit():
    """Amendment G (TEMPLATED_POLYMERISATION_LAWS §9.20, option (a); D307), host side, no compile:
    on the step-5 world the owner derives transcription's producer labels, cell_0-g<k>-tx and
    their cohort window's, and its source's schedule from replacement@1's occupants. The derived
    definition binds to the hand-written one's types, initial state, layout and every control
    array bit for bit, so the programs that run are unchanged. A definition round trip writes the
    declared producers back, not the labels, and derives the same again (a resume reads the
    definition)."""
    import copy

    from cells.definitions import pump_composite_spec as cs
    from cells.operators import species_labels as labels
    from cells.registry.models import get_model

    bound = {}
    for kind in ("derived", "hand-written"):
        spec = parse_spec(chase(kind))
        model = get_model(spec.model)
        state, p = model.initial_values(spec)
        controls = cs.control_values(spec, np.asarray(spec.experiment.observation_times))
        bound[kind] = (spec, state, p, controls)
    (spec, *mine), (_, *theirs) = bound.values()
    for a, b in zip(mine, theirs, strict=True):
        assert type(a)._fields == type(b)._fields
        pairs = zip(a, b, strict=True)
        assert all(np.asarray(x).tobytes() == np.asarray(y).tobytes() for x, y in pairs)
    owner = next(d for op, d, _ in cs.entries(spec) if op.LABEL_OWNER)
    expanded, schedules = labels.derived(spec, owner)
    assert expanded.species[0].labels == (
        "base", "cell_0-g0-tx", "cell_0-g0-tx-cohort", "cell_0-g1-tx", "cell_0-g1-tx-cohort"
    )  # fmt: skip
    own = ((0.0, "cell_0-g0-tx-cohort"), (1200.0, "cell_0-g0-tx"), (3000.0, "cell_0-g1-tx"))
    assert schedules == ((("R", "tx"), own),)  # Transcription's: its source is R's (label_sources).
    again = parse_spec(copy.deepcopy(spec.to_dict()))
    declared = next(d for op, d, _ in cs.entries(again) if op.LABEL_OWNER)
    assert declared == owner and labels.derived(again, declared) == (expanded, schedules)
    assert "producers" in spec.to_dict()["model"]["operators"][-1]["species"][0]


def test_derived_producer_labels_follow_cell_ids_and_events_not_the_cells_order(monkeypatch):
    """Amendment G, the requester's identity (cell, generation, chain) across cell reordering: two
    producer cells, one replaced twice. Listing the cells and their chains in the other order
    derives the same labels and schedules, named by cell ID and numbered by event order (planted
    occupants and sources, no world)."""
    from types import SimpleNamespace

    from cells.operators import species_common
    from cells.operators import species_labels as labels

    def life(cell, births):
        return tuple(species_common.Occupant(cell, b, 0.0, "newcomer", None, None) for b in births)

    lives = {"cell_a": life("cell_a", (0.0, 2.0, 5.0)), "cell_b": life("cell_b", (0.0,))}
    chains = (("tx_a", "R", "cell_a"), ("tx_b", "R", "cell_b"))
    entry = labels.Labelled(
        "R", ("base",), (), (("tx_a", (("pulse", 1.0, 3.0),)), ("tx_b", ()))
    )  # fmt: skip
    declaration = labels.Labels(labels.LAW_ID, (entry,))
    spec = SimpleNamespace(experiment=SimpleNamespace(end_time=8.0))
    out = []
    for order in (1, -1):
        source = SimpleNamespace(label_sources=lambda d, o=order: chains[::o])
        monkeypatch.setattr(labels, "reporters", lambda s, flag, r=source: ((r, None),))
        reordered = dict(list(lives.items())[::order])
        monkeypatch.setattr(species_common, "occupants", lambda s, r=reordered: r)
        out.append(labels.derived(spec, declaration))
    assert out[0] == out[1]
    expanded, schedules = out[0]
    assert expanded.species[0].labels == (
        "base", "cell_a-g0-tx_a", "cell_a-g0-tx_a-pulse", "cell_a-g1-tx_a", "cell_a-g1-tx_a-pulse",
        "cell_a-g2-tx_a", "cell_a-g2-tx_a-pulse", "cell_b-g0-tx_b",
    )  # fmt: skip
    assert dict(schedules)[("R", "tx_a")] == (
        (0.0, "cell_a-g0-tx_a"), (1.0, "cell_a-g0-tx_a-pulse"), (2.0, "cell_a-g1-tx_a-pulse"),
        (3.0, "cell_a-g1-tx_a"), (5.0, "cell_a-g2-tx_a"),
    )  # fmt: skip
    assert dict(schedules)[("R", "tx_b")] == ((0.0, "cell_b-g0-tx_b"),)


def test_a_batch_of_producer_worlds_is_refused():
    """Amendment G's batch limit, fail-closed: a producer world's label count follows its cells'
    replacement events, which the batch's signature check cannot read, so version 1 batches it with
    no other world. Two members whose producer cells see one and two events are refused by the
    batch's own check, and so are two identical members; a batch of one parses (parses only)."""
    from cells.definitions.specs import ConfigError
    from cells.execution.batch import parse_batch
    from validation.gene_regulation import replace_restart as rr

    def batch(*worlds):
        return dict(
            schema_version=1, kind="independent_worlds",
            worlds=[dict(world_id=k, simulation=w) for k, w in enumerate(worlds, start=1)],
            execution=dict(mapping="lax_map", max_worlds=8, max_padded_steps=10**6,
                           max_working_bytes=2**40),
        )  # fmt: skip

    twice = chase("derived")
    events = twice["experiment"]["replacement_events"]
    events.append(dict(events[0], time=rr.T_C, carrier_id=f"{events[0]['carrier_id']}_2"))
    for pair in ((chase("derived"), twice), (chase("derived"), chase("derived"))):
        with pytest.raises(ConfigError, match="matching model array axes"):
            parse_batch(batch(*pair))
    parse_batch(batch(chase("derived")))
