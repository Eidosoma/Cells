"""FR-33's region export and passive tracer (validation/regions), run on the FR-7 lane's example
world with its transferred species also cleared and made in the cell
(validation/regions/example.py).

Two compiled worlds: the example's, 500 steps of 1 ms shared by the first two rows, and the
reviewer's two-node diffusion, 100 steps of 0.01 s, for the third. Their cost and reason (D224): two
compiles, about a minute on the timed lane. They keep the region export's quantities and the
tracer's cohorts working against their identities and closed forms, and keep the tracer refusing a
two-way movement its net records cannot see.

The tracer's error at the mixing node is its trapezoid split's, second order in dt, and set by the
inflow within a step relative to the node's amount (validation/regions/readouts.py, "Its limit").
The bounds below hold the measured errors with a margin. Without inflow its split is exact.

Host-only rows (the review of 21 November 2026; the example's world parsed, no run, synthetic
records from closed forms; about 1 s together, beside the module's imports) keep the tracer
refusing what it cannot do:
- finding 1, a step it cannot resolve (r = O/S above 0.01 where the node gains material or sends
  it along a route);
- finding 4, a law it neither reads nor lists as shown inert (the wash), with the registry walked so
  that a new law is refused until it is classified;
- finding 7, its own cohort names as a caller's;
- and, for D260's follow-up, a long draining run admitted at its records' rounding (about 1 s);
- D265's findings 2, 4 and 5: equivalent spellings of a time name one step, a drain followed by
  turnover is refused beside the long drain, and a region naming a node twice is refused.

Each is planted where its refusal is lifted: the returned rows' invariant (each cohort non-negative,
the cohorts summing to the node's amount) catches the negative split and the vanished cohort.
"""

import math
from types import SimpleNamespace

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.registry.models import get_model
from validation.compartment_transfer import example as base
from validation.regions import example, readouts


@pytest.fixture(scope="module")
def run():
    return example.run()


@pytest.fixture(scope="module")
def out(run):
    return example.exports(run)


def _close(a, b, scale):
    return abs(a - b) <= 1e-12 * scale + 1e-18


def test_the_region_export_keeps_its_identities(run, out):
    st, sd = out["ST"], out["SD"]
    for rows in (st, sd):
        assert len(rows["times"]) >= 10
        for inside, outside, whole in zip(rows["inside_fmol"], rows["outside_fmol"],
                                          rows["whole_cell_fmol"], strict=True):  # fmt: skip
            assert _close(inside + outside, whole, whole)
    # ST over [ecs_0]: the region's decrease is the release, and the cell's loss and production,
    # outside the region, change the whole cell.
    a0 = st["inside_fmol"][0]
    for k in range(len(st["times"])):
        assert _close(a0 - st["inside_fmol"][k], st["transfer_fmol"]["release"][k], a0)
        assert st["loss_fmol"][base.NODE_T][k] == 0.0
        net = st["loss_fmol"][base.CELL][k] - st["produced_fmol"][base.CELL][k]
        assert _close(st["whole_cell_fmol"][0] - st["whole_cell_fmol"][k], net, a0)
    assert st["transfer_fmol"]["release"][-1] > 0.3 * a0 and st["loss_fmol"][base.CELL][-1] > 0
    # SD over [ecs_1], local destruction: the region's decrease is its loss, and nothing moves.
    d0 = sd["inside_fmol"][0]
    assert sd["transfer_fmol"] == {}
    for k in range(len(sd["times"])):
        lost = sd["loss_fmol"][base.NODE_D][k]
        assert _close(d0 - sd["inside_fmol"][k], lost, d0)
        assert _close(sd["whole_cell_fmol"][0] - sd["whole_cell_fmol"][k], lost, d0)
    # A region of two nodes, the cell and ecs_1: the release flows into it.
    spec, times, states = run
    two = readouts.region_rows(spec, times, states, base.ST, [base.CELL, base.NODE_D],
                               samples=st["times"])  # fmt: skip
    for k in range(len(two["times"])):
        assert _close(two["inside_fmol"][k], st["outside_fmol"][k], a0)
        gain = (two["transfer_fmol"]["release"][k] + two["produced_fmol"][base.CELL][k]
                - two["loss_fmol"][base.CELL][k])  # fmt: skip
        assert _close(two["inside_fmol"][k] - two["inside_fmol"][0], gain, a0)
    # A region outside one cell's nodes is refused.
    with pytest.raises(ValueError, match="not the nodes of one cell"):
        readouts.region_rows(spec, times, states, base.ST, [base.NODE_T, "bath"])


def test_the_tracer_names_the_cohort_that_lost_material(run, out, monkeypatch):
    traced, closed, st = out["trace"], out["closed"], out["ST"]
    amount, loss, moved = traced["amount"], traced["loss"], traced["transfer"]
    a0 = amount["from_ecs_0"][base.NODE_T][0]
    # Every node's cohorts sum to the engine's amount there; the cell is the mixing node.
    for k, t in enumerate(traced["times"]):
        if t in st["times"]:
            row = st["times"].index(t)
            for node in (base.CELL, base.NODE_T, base.NODE_D):
                held = sum(amount[c][node][k] for c in amount)
                assert _close(held, st["node_fmol"][node][row], a0)
    # At the mixing node each cohort and its cumulative loss meet the closed forms: the received
    # one, the cell's own, and the made material, labelled pulse, then chase.
    for name, key, bound in (("from_ecs_0", "A", 1e-6), ("in_cell", "B", 5e-6),
                             ("pulse", "pulse", 5e-6), ("chase", "chase", 5e-6)):  # fmt: skip
        scale = max(closed[f"{key}_cell"])
        got, lost = amount[name][base.CELL], loss[name][base.CELL]
        assert max(abs(g - c) for g, c in zip(got, closed[f"{key}_cell"], strict=True)) <= (
            bound * scale
        ), name
        assert max(abs(g - c) for g, c in zip(lost, closed[f"{key}_lost"], strict=True)) <= (
            bound * scale
        ), name
    # The cell's loss is named by cohort: the shares sum to turnover's record there.
    total = sum(loss[c][base.CELL][-1] for c in loss)
    assert math.isclose(total, st["loss_fmol"][base.CELL][-1], rel_tol=1e-12)
    assert loss["unlabelled"][base.CELL][-1] == 0.0 and amount["chase"][base.CELL][0] == 0.0
    # The release carries the donor's one cohort.
    assert math.isclose(moved["from_ecs_0"]["release"][-1], st["transfer_fmol"]["release"][-1],
                        rel_tol=1e-12)  # fmt: skip
    assert moved["in_cell"]["release"][-1] == 0.0
    # Without inflow the split is exact: two cohorts at the donor keep their fractions.
    spec, times, states = run
    split = readouts.trace(spec, times, states, base.ST,
                           {"p30": {base.NODE_T: 0.3}, "p70": {base.NODE_T: 0.7}})  # fmt: skip
    p30, p70 = (np.array(split["amount"][c][base.NODE_T]) for c in ("p30", "p70"))
    assert np.max(np.abs(p30 / (p30 + p70) - 0.3)) <= 1e-14
    # A mover the tracer does not read breaks the closure, and the trace is refused.
    whole = readouts.world_map
    monkeypatch.setattr(readouts, "world_map", lambda s, x: dict(whole(s, x), routes=[]))
    with pytest.raises(ValueError, match="do not close"):
        readouts.trace(spec, times, states, base.ST, example.COHORTS)


def test_a_two_way_movement_the_net_records_cannot_see_is_refused():
    """The reviewer's case (validation/regions/example.py): equal totals exchanging by diffusion."""
    spec = parse_spec(example.two_node_diffusion())
    times, states = readouts.runs(spec)
    with pytest.raises(ValueError, match="face face_lr diffuses it"):
        readouts.trace(spec, times, states, "S", {"label": {"left": 0.9, "right": 0.1}})
    # The explicit label row carries the label through the face's own law: 0.3 fmol on the right.
    _, layout = get_model(spec.model).initial_values(spec)
    labelled = readouts.world_map(spec, "L")
    right = labelled["nodes"].index("right")
    assert abs(times[-1] - 1.0) < 1e-12
    amount = readouts.node_records(spec, layout, states[-1], labelled)[0][right]
    assert abs(amount - 0.3) <= 1e-5
    total = readouts.node_records(spec, layout, states[-1], readouts.world_map(spec, "S"))[0]
    assert abs(total[right] - 1.0) <= 1e-12  # S's own totals never move.


# ------------------------------------------------------------------ the review of 21 November 2026
# Host only: the example's world parsed (no run), with synthetic records built from closed forms.


def _synthetic(times, cell, *, produced=None, cleared=None, ecs_1=None, donor=None, moved=None):
    """(spec, states) of the example's world with ST's cell amount cell(t) fmol, its cumulative
    production and clearance there, ecs_1's amount (its declared one by default), ecs_0's amount
    donor(t) and the release's cumulative move moved(t) into the cell (none by default), and
    every other record constant."""
    spec = parse_spec(example.world())
    state0, layout = get_model(spec.model).initial_values(spec)
    wmap = readouts.world_map(spec, base.ST)
    row = wmap["row"]
    c, d = wmap["cells"].index(base.CELL), wmap["outside"].index(base.NODE_D)
    e = wmap["outside"].index(base.NODE_T)
    (release,) = wmap["routes"]
    ref_c = np.asarray(layout.amount_reference)[row, c]
    ref_d = np.asarray(layout.extracellular_amount_reference)[row, d]
    ref_e = np.asarray(layout.extracellular_amount_reference)[row, e]
    states = []
    for t in times:
        amounts = np.zeros_like(np.asarray(state0.amount_increment))
        outside = np.zeros_like(np.asarray(state0.extracellular_amount_increment))
        amounts[row, c] = cell(t) - ref_c
        if ecs_1 is not None:
            outside[row, d] = ecs_1 - ref_d
        if donor is not None:
            outside[row, e] = donor(t) - ref_e
        exchange = np.zeros(len(np.asarray(state0.exchange_moved_fmol)))
        exchange[release["index"]] = 0.0 if moved is None else release["sign"] * moved(t)
        made, gone = np.zeros_like(amounts), np.zeros_like(amounts)
        made[row, c] = 0.0 if produced is None else produced(t)
        gone[row, c] = 0.0 if cleared is None else cleared(t)
        states.append(SimpleNamespace(
            amount_increment=amounts, extracellular_amount_increment=outside,
            turnover_produced_fmol=made, turnover_cleared_fmol=gone, exchange_moved_fmol=exchange,
        ))  # fmt: skip
    return spec, states


def test_the_tracer_refuses_a_step_it_cannot_resolve(monkeypatch):
    """Finding 1 (P1; host only, about 1 s). The cell's pool at 1 fmol, made at 4 fmol/s and
    cleared at 4/s, so it stays at 1 fmol:
    - one 1 s step has r = O/S = 2 at a node that gains material, so it is refused (the update would
      give its starting cohort -1/3 for e^-4 = 0.018316);
    - planted, the bound off: the returned rows' invariant refuses the negative cohort;
    - at 400 steps of 2.5 ms (r = 0.005) the starting cohort is e^-4 within the stated 4.3e-4 of
      it, the made one 1 - e^-4, and resolution_largest is 0.005;
    - with no gains a node is exact at any r: the cell cleared at 1/s, one 1 s step (r = 0.46),
      two cohorts keep 30 and 70% of its amount e^-1;
    - a node that sends material along a route is held to the bound too, since its arrivals shape
      its receiver's split: a donor at r = 0.76 into the cell at r = 0.01 is refused;
    - a node empty at both ends of every step (ecs_1 at 0 fmol) holds no cohort, with no NaN."""
    pool = {"cell": dict(cell=lambda t: 1.0, produced=lambda t: 4 * t, cleared=lambda t: 4 * t)}
    spec, states = _synthetic([0.0, 1.0], **pool["cell"])
    own = {"own": {base.CELL: 1.0}}
    with pytest.raises(ValueError, match="r = O/S = 2 .*above the tracer's resolution 0.01"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, own)
    monkeypatch.setattr(readouts, "RESOLUTION", np.inf)
    with pytest.raises(ValueError, match="cell_0, t = 1.0, are not non-negative"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, own)
    monkeypatch.undo()
    times = [k * 0.0025 for k in range(401)]
    spec, states = _synthetic(times, ecs_1=0.0, **pool["cell"])
    traced = readouts.trace(spec, times, states, base.ST, own)
    old, made = traced["amount"]["own"][base.CELL][-1], traced["amount"]["produced"][base.CELL][-1]
    assert abs(old - math.exp(-4)) <= 4.3e-4 * math.exp(-4)
    assert abs(made - (1 - math.exp(-4))) <= 4.3e-4 * math.exp(-4)
    assert traced["resolution_largest"] == pytest.approx(0.005, rel=1e-12)
    assert traced["resolution_bound"] == 0.01
    assert all(v == 0.0 for c in traced["amount"] for v in traced["amount"][c][base.NODE_D])
    spec, states = _synthetic(
        [0.0, 1.0], cell=lambda t: math.exp(-t), cleared=lambda t: 1 - math.exp(-t)
    )
    split = readouts.trace(spec, [0.0, 1.0], states, base.ST,
                           {"p30": {base.CELL: 0.3}, "p70": {base.CELL: 0.7}})  # fmt: skip
    p30, p70 = (split["amount"][c][base.CELL][-1] for c in ("p30", "p70"))
    assert p30 == pytest.approx(0.3 * math.exp(-1), rel=1e-15)
    assert p70 == pytest.approx(0.7 * math.exp(-1), rel=1e-15)
    assert split["resolution_largest"] == 0.0  # No node gained or sent material.
    # A donor draining most of itself in one step (kappa dt = 2) into the cell, which gains it at
    # r = 0.01: refused at the donor, whose own split is exact but whose arrivals would put 9.4e-4
    # of the cell's amount on the wrong cohort (the advisor's case).
    kappa, k = 2.0, 0.0183

    def fed(t):
        return math.exp(-k * t) + kappa / (k - kappa) * (math.exp(-kappa * t) - math.exp(-k * t))

    spec, states = _synthetic(
        [0.0, 1.0],
        fed,
        cleared=lambda t: 1.0 + (1.0 - math.exp(-kappa * t)) - fed(t),
        donor=lambda t: math.exp(-kappa * t),
        moved=lambda t: 1.0 - math.exp(-kappa * t),
    )
    with pytest.raises(ValueError, match="out of ecs_0, which gains material in it or sends it"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, {"own": {base.CELL: 1.0}})


def test_every_law_the_tools_do_not_read_is_refused():
    """Finding 4 (P2; host only, about 1 s). Fail closed: the tracer and the export refuse every
    operator law they neither read nor list as shown inert, and every declared kind.
    - FR-27's well without its sites, washed at 1 s: both refuse the wash by name (it moves every
      free species at its nodes, and declares no species, so a check for a species field missed it:
      the tracer kept all 60 fmol of the label while the wash took 30);
    - a law in no list is refused, and so is a kind, and a charged species (its channel, pump and
      membrane fluxes are in-step laws neither tool reads);
    - every registered law is classified, and each one listed as shown inert writes no species
      amount, provides no amount view, replaces none at an event and closes no node."""
    from validation.tissue import wash_schedule_fixtures as wash

    raw = wash.with_wash(wash.well(sites=False, end=2.0), ["well"],
                         [(1.0, "well", 0.5, {wash.TRACER: 60.0 / wash.V_WELL})])  # fmt: skip
    spec = parse_spec(raw)
    message = "cells.operator.scheduled_compartment_wash@1 collects and refills every free species at its nodes"
    with pytest.raises(ValueError, match=message):
        readouts.trace(spec, [0.0], [None], wash.TRACER, {"label": {"well": 1.0}})
    with pytest.raises(ValueError, match=message):
        readouts.region_rows(spec, [0.0], [None], wash.TRACER, ["specimen"])
    ion = parse_spec(example.world())
    charged = ion.model.species_ids[ion.model.valence.index(1)]
    with pytest.raises(ValueError, match="it is charged"):
        readouts.trace(ion, [0.0], [None], charged, {"label": {base.CELL: 1.0}})
    model = SimpleNamespace(species_ids=("S",), valence=(0,), faces=(), junctions=(), membranes=(),
                            operators=(SimpleNamespace(law="unclassified_law@1"),),
                            kinds=(("a_kind", None),))  # fmt: skip
    with pytest.raises(ValueError, match="unclassified_law@1 is not classified here.*kind a_kind"):
        readouts.check_movers(SimpleNamespace(model=model), "S", readouts.TRACER_READS)
    from cells.operators import OPERATORS

    reads = set(readouts.EXPORT_READS) | set(readouts.TRACER_READS)
    listed = [reads, set(readouts.SHOWN_INERT), set(readouts.REFUSED) - reads]
    assert sorted(set(OPERATORS) - set().union(*listed)) == [], "classify the new law here"
    assert not (set(readouts.SHOWN_INERT) & (set(readouts.REFUSED) | reads))
    amounts = {"amount_increment", "extracellular_amount_increment", "amount_reference",
               "extracellular_amount_reference"}  # fmt: skip
    masks = {"active", "outside_active", "membrane_active", "face_active", "junction_active"}
    for law in readouts.SHOWN_INERT:
        op = OPERATORS[law]
        written = set(op.ENTITY_WRITES) | set(op.REPLACES) | set(op.EVENT_REPLACES)
        assert not written & amounts, law
        assert not set(op.VIEW_FIELDS) & (amounts | masks), law
        assert not set(op.CLOSES) & (amounts | masks), law


def test_the_tracers_own_cohort_names_are_refused(monkeypatch):
    """Finding 7 (P2; host only, about 1 s): a caller's cohort named unlabelled or produced is
    refused (the tracer's own column replaced it on export, and a 1 fmol pool exported 0 fmol at
    t = 0); so are an unknown node and a fraction outside [0, 1]. Planted, the names admitted: the
    returned rows' invariant refuses the vanished cohort."""
    spec, states = _synthetic([0.0, 1.0], cell=lambda t: 1.0)
    for name in ("unlabelled", "produced"):
        with pytest.raises(ValueError, match=f"cohort '{name}' is the tracer's own name"):
            readouts.trace(spec, [0.0, 1.0], states, base.ST, {name: {base.CELL: 1.0}})
    with pytest.raises(ValueError, match="unknown node 'nowhere'"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, {"c": {"nowhere": 1.0}})
    with pytest.raises(ValueError, match="lies outside \\[0, 1\\]"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, {"c": {base.CELL: -0.5}})
    monkeypatch.setattr(readouts, "RESERVED", ())
    with pytest.raises(ValueError, match="cell_0, t = 0.0, sum to 0.0 fmol, not the node's 1.0"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, {"unlabelled": {base.CELL: 1.0}})


def test_a_long_draining_run_closes_at_its_records_rounding(monkeypatch):
    """The closure's tolerance follows the terms actually summed (D260's follow-up; host only,
    about 1 s): each node's stored reference and increment, and each cumulative record, at both
    ends of the step.
    - A long draining run is admitted: the cell cleared at 1/s from its declared amount for 40 s
      in 2000 steps, to e^-40 of it, far below its reference's rounding. Its two cohorts keep 30
      and 70%.
    - Planted, with those sizes left out (records_rounding): the closure refuses it, as it did
      before (a false refusal, for the records' own rounding).
    - The reviewer's f1, the steady pool in one 1 s step, is still refused, by the resolution."""
    times = [k * 0.02 for k in range(2001)]
    spec, _ = _synthetic([0.0], cell=lambda t: 0.0)
    _, layout = get_model(spec.model).initial_values(spec)
    wmap = readouts.world_map(spec, base.ST)
    n0 = float(np.asarray(layout.amount_reference)[wmap["row"], 0])
    spec, states = _synthetic(
        times, cell=lambda t: n0 * math.exp(-t), cleared=lambda t: n0 * (1 - math.exp(-t))
    )
    cohorts = {"p30": {base.CELL: 0.3}, "p70": {base.CELL: 0.7}}
    traced = readouts.trace(spec, times, states, base.ST, cohorts)
    p30, p70 = (np.asarray(traced["amount"][c][base.CELL]) for c in ("p30", "p70"))
    assert np.max(np.abs(p30 / (p30 + p70) - 0.3)) <= 1e-12
    assert p30[-1] + p70[-1] == pytest.approx(n0 * math.exp(-40), rel=1e-6)
    monkeypatch.setattr(readouts, "records_rounding", lambda *args: 0.0)
    with pytest.raises(ValueError, match="do not close"):
        readouts.trace(spec, times, states, base.ST, cohorts)
    monkeypatch.undo()
    pool = dict(cell=lambda t: 1.0, produced=lambda t: 4 * t, cleared=lambda t: 4 * t)
    spec, states = _synthetic([0.0, 1.0], **pool)
    with pytest.raises(ValueError, match="r = O/S = 2 .*above the tracer's resolution 0.01"):
        readouts.trace(spec, [0.0, 1.0], states, base.ST, {"own": {base.CELL: 1.0}})
    # D265 finding 4, beside the long drain: 1 fmol drained to 2^-47 in 1 s, then made and cleared
    # at four times that pool. The cumulative clearance's rounding exceeds the second step's pool,
    # so the resolution test and the cohort bound read the step's own terms: refused at r = 2 (on
    # main the old cohort was -33% with both checks at 0). Planted, the bound off: the rows'
    # invariant refuses the negative cohort.
    x = 2.0**-47
    spec, states = _synthetic(
        [0.0, 1.0, 2.0],
        cell=lambda t: 1.0 if t == 0 else x,
        produced=lambda t: 4 * x if t == 2 else 0.0,
        cleared=lambda t: {0.0: 0.0, 1.0: 1 - x}.get(t, 1 - x + 4 * x),
    )
    old = {"old": {base.CELL: 1.0}}
    with pytest.raises(ValueError, match="t = 2.0 s .*r = O/S = 2 "):
        readouts.trace(spec, [0.0, 1.0, 2.0], states, base.ST, old)
    monkeypatch.setattr(readouts, "RESOLUTION", np.inf)
    with pytest.raises(ValueError, match="cell_0, t = 2.0, are not non-negative"):
        readouts.trace(spec, [0.0, 1.0, 2.0], states, base.ST, old)


def test_equivalent_spellings_of_a_time_name_one_step(monkeypatch):
    """D265 finding 2 (P1; host only, about 1 s). A label switch or a sample at 0.3 and at
    0.1 + 0.2 name the same step: one resolver (step_index) gives the index both tools use. On
    main the second spelling put none of the step's production into the new cohort and the export
    returned no row. A time no step matches, or that two match, is refused, and so are two samples
    or two switches naming one step. Planted, the resolver made exact: the second spelling is
    refused, never silently given another step."""
    times = [0.0, 0.1, 0.2, 0.3, 0.4]
    spec, states = _synthetic(times, cell=lambda t: 1.0, produced=lambda t: 1e-3 * t,
                              cleared=lambda t: 1e-3 * t)  # fmt: skip
    own = {"own": {base.CELL: 1.0}}
    made, rows = [], []
    for at in (0.3, 0.1 + 0.2):
        traced = readouts.trace(spec, times, states, base.ST, own, produced=[(0.0, "a"), (at, "b")])
        made.append(traced["amount"]["b"][base.CELL])
        rows.append(readouts.region_rows(spec, times, states, base.ST, [base.NODE_T], samples=[at]))
    assert made[0] == made[1] and made[0][-1] > 0
    assert rows[0] == rows[1] and rows[0]["times"] == [0.3]
    for bad, message in (([0.35], "not an accepted step's time"), ([0.3, 0.1 + 0.2], "same step")):
        with pytest.raises(ValueError, match=message):
            readouts.region_rows(spec, times, states, base.ST, [base.NODE_T], samples=bad)
    with pytest.raises(ValueError, match="label switch to 'b' at 0.35 s is not an accepted"):
        readouts.trace(spec, times, states, base.ST, own, produced=[(0.35, "b")])
    with pytest.raises(ValueError, match="two label switches name the same step"):
        readouts.trace(spec, times, states, base.ST, own, produced=[(0.3, "a"), (0.1 + 0.2, "b")])
    close = [0.0, 0.3, 0.3 + 1e-13, 0.4]
    spec2, states2 = _synthetic(close, cell=lambda t: 1.0)
    with pytest.raises(ValueError, match="ambiguous: 2 steps"):
        readouts.region_rows(spec2, close, states2, base.ST, [base.NODE_T], samples=[0.3])
    monkeypatch.setattr(readouts, "TIME_RTOL", 0.0)
    with pytest.raises(ValueError, match="0.30000000000000004 s is not an accepted step's time"):
        readouts.trace(spec, times, states, base.ST, own, produced=[(0.1 + 0.2, "b")])


def test_a_region_naming_a_node_twice_is_refused(monkeypatch):
    """D265 finding 5 (P2; host only, about 1 s). On main, ecs_0 named twice returned 0.002 fmol
    inside and -0.000999 outside a cell holding 0.001001001 fmol. A repeated node is refused,
    from one list or from overlapping ones. Planted, the repetition admitted: every row's bounds
    (0 <= inside <= whole cell, so outside >= 0) refuse it."""
    spec, states = _synthetic([0.0], cell=lambda t: 1e-6)
    for region in ([base.NODE_T, base.NODE_T], [base.CELL] + [base.CELL, base.NODE_D]):
        with pytest.raises(ValueError, match="names a node twice"):
            readouts.region_rows(spec, [0.0], states, base.ST, region)
    monkeypatch.setattr(readouts, "_distinct", lambda region: None)
    with pytest.raises(ValueError, match="outside -0.000998999.* below 0"):
        readouts.region_rows(spec, [0.0], states, base.ST, [base.NODE_T, base.NODE_T])
