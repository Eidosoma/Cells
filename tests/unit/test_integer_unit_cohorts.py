"""FR-52's passive cohort record in the compiled program (docs/PASSIVE_COHORT_DESIGN.md §2.2, §3,
§5.3; the host rows are in tests/unit/test_integer_unit_population.py).

The qualification world (validation/fr52_cohorts/worlds.qualification: two populations on one
patch, a rule-resolved homo cohort with open2's two-pair table and a hetero cohort with row F's
declared join and cut), compiled observed and unobserved, with one in-process resume of the first:
* the run holds the ten events its seed was chosen for, on the engine's own trace;
* for both cohorts the record meets the reference's exact means within 8 (K + 1) u N at every
  row, and the reference's rebuilt counts equal the recorded counts at every event and the saved
  counts at every row (validation/fr52_cohorts/exact.read_run); before a site's first event the
  record is its start, bit for bit;
* the one-pair update, replayed on the engine's trace, departs at the homo's open2;
* the twins: every other field, observation and diagnostic of the unobserved run, bit for bit, in
  the observed one;
* sum-to-flux: over every event-free step of the homo's site, the record's conductance times the
  closed-form integral of the driving difference is the booked transfer, a drifting record and a
  conductance on the wrong state failing it;
* the readout: resolved at every row, FR-52's two quantities the reference's within the bound;
* case E: a same-seed restart cut inside both windows, between events, is bitwise the
  uninterrupted run, the record included; the record set to its start, or zeroed, at the cut is
  caught.

Its reason: the record's only compiled path, the twins and the restart need runs (two compiles,
about 60 s on one core, most of it the compiles); the existing file has no room for them under the
90 s cap (D224).
"""

import dataclasses
import math
from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from cells.numerics import unit_cohorts as uc
from cells.operators import integer_unit_population as iup
from cells.registry.models import get_model
from validation.fr52_cohorts import exact
from validation.fr52_cohorts import worlds as cw

WINDOW = 50  # Steps per window: the restart's cut at 1.5 s ends one.
RECORD = "integer_cohort_units"


def _collect(spec, checkpoint=None):
    windows = list(iter_windows(spec, WindowPolicy(WINDOW, "full"), checkpoint))
    rows = {}
    for window in windows:
        for i, _ in enumerate(np.asarray(window.times)):
            rows[window.start_step + i] = type(window.history)(
                *(np.asarray(v)[i] for v in window.history)
            )
    return windows, rows


@pytest.fixture(scope="module")
def observed():
    raw = cw.qualification()
    spec = parse_spec(raw)
    windows, rows = _collect(spec)
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    block = next(o for o in raw["model"]["operators"] if o["law"] == iup.LAW_ID)
    declaration = next(d for d in spec.model.operators if d.law == iup.LAW_ID)
    return dict(raw=raw, spec=spec, p=p, windows=windows, rows=rows, block=block,
                declaration=declaration)  # fmt: skip


@pytest.fixture(scope="module")
def unobserved():
    spec = parse_spec(cw.unobserved())
    windows, rows = _collect(spec)
    return dict(spec=spec, windows=windows, rows=rows)


def _events(rows, site, kind):
    last = rows[max(rows)]
    names = [c[0] for c in kind["channels"]]
    n = int(last.integer_events[site])
    return [(float(last.integer_trace_time_s[site, k]),
             names[int(last.integer_trace_channel[site, k])]) for k in range(n)]  # fmt: skip


def test_the_run_holds_the_events_its_seed_was_chosen_for(observed):
    rows = observed["rows"]
    assert sorted(rows) == list(range(int(round(cw.END / cw.DT)) + 1))  # A row every step.
    events = {
        cw.HOMO["site"]: _events(rows, 0, cw.HOMO),
        cw.HETERO["site"]: _events(rows, 1, cw.HETERO),
    }
    assert all(cw.required(events).values()), cw.required(events)
    last = rows[max(rows)]
    assert np.all(last.integer_events <= last.integer_trace_channel.shape[1])  # Complete traces.


@pytest.mark.parametrize("cohort", ["homo_units", "hetero_units"])
def test_the_record_meets_the_reference_at_every_row(observed, cohort):
    """The reference reads the declaration and the trace (never the engine's kernel): its rebuilt
    counts equal the recorded and the saved ones, and the record lies within its bound of the
    exact means at every row. Before the site's first event the record is its start, bit for bit."""
    rows = observed["rows"]
    report = exact.read_run(observed["block"], rows, cohort)
    assert report["resolved"], report["problems"]
    assert all(r["worst_entry"] <= 1 and r["worst_sum"] <= 1 for r in report["rows"].values())
    q = [c["id"] for c in observed["block"]["cohorts"]].index(cohort)
    start = rows[0]
    for row in rows.values():
        if int(row.integer_events[q]) == 0:
            assert getattr(row, RECORD)[q].tobytes() == getattr(start, RECORD)[q].tobytes()


def test_the_one_pair_update_departs_at_open2(observed):
    """The plant of §5.2 on the compiled world's open2: the engine's trace replayed through an
    update that applies at most one pair per channel leaves the reference's exact means by more
    than the bound at the first open2, where the honest record meets them."""
    rows, block = observed["rows"], observed["block"]
    population = block["populations"][0]
    states = [u["id"] for u in population["unit_states"]]
    members = block["cohorts"][0]["states"]
    last = rows[max(rows)]
    channels = [int(c) for c in last.integer_trace_channel[0, : int(last.integer_events[0])]]
    first = next(k for k, c in enumerate(channels) if population["channels"][c]["id"] == "open2")
    counts = dict(population["sites"][0]["initial_counts"])
    units = np.zeros((len(states), len(uc.LABELS)))
    units[:, uc.INITIAL] = [counts[s] if s in members else 0 for s in states]
    record = exact.start_record(counts, members)
    for k in range(first + 1):
        c = population["channels"][channels[k]]
        r, p = exact.class_side(c["reactants"], members), exact.class_side(c["products"], members)
        pairs = exact.table(r, p)
        planted = dict(sorted(pairs.items())[:1])
        planted = {key: 1 for key in planted}
        label = exact.label_index(float(last.integer_trace_time_s[0, k]), cw.WINDOW_S)
        m = np.zeros((len(states), len(states)), dtype=np.int64)
        for (a, b), x in planted.items():
            m[states.index(a), states.index(b)] = x
        n, rv, pv = (np.array([side.get(s, 0) for s in states]) for side in (counts, r, p))
        units = uc.advance(units, n, rv, pv, m, np.asarray(label), xp=np)
        record = exact.update(record, counts, r, p, pairs, label)
        for s, n in c["reactants"].items():
            counts[s] -= n
        for s, n in c["products"].items():
            counts[s] += n
    most = exact.read_run(block, rows, "homo_units")["most"]
    error = max(abs(Fraction(float(units[states.index(s), x])) - record[s][x])
                for s in members for x in range(len(uc.LABELS)))  # fmt: skip
    assert error > exact.bound(first + 1, most), error


def _bits(value):
    value = np.asarray(value)
    return value.dtype.str, value.shape, value.tobytes()


def test_the_twins_agree_on_every_other_field(observed, unobserved):
    """Passive where declared (§2.2): the observed and unobserved runs, same seed and trace
    capacity, agree bit for bit on every field, observation column and diagnostic but the record,
    window by window, in the labels' same_physics form."""
    pairs = list(zip(observed["windows"], unobserved["windows"], strict=True))
    assert len(pairs) == int(round(cw.END / cw.DT)) // WINDOW
    for seen, plain in pairs:
        assert type(seen.history)._fields == type(plain.history)._fields
        for name in type(plain.history)._fields:
            if name != RECORD:
                a, b = getattr(seen.history, name), getattr(plain.history, name)
                assert _bits(a) == _bits(b), name
        for name, value in vars(plain.observations).items():
            if name != RECORD:
                assert _bits(getattr(seen.observations, name)) == _bits(value), name
        assert seen.diagnostics == plain.diagnostics
        assert np.asarray(getattr(plain.history, RECORD)).shape[1] == 0  # Zero-size undeclared.


FLUX_C = 4  # The rounding term's constant (measured worst 0.84 at c = 1, at the build).


def _flux_error(observed, *, scale=1.0, state="open"):
    """The worst sum-to-flux departure over the homo site's event-free steps, as a fraction of its
    tolerance: Σ_l g E_state,l I against the booked change of integer_transferred_fmol, I the
    closed-form integral of the driving difference over the step from the start row. The tolerance
    is the record's bound times g I, plus FLUX_C ε times the scale the two closed forms round at:
    the cumulative books at both rows (the booked change is their difference) and the step's move
    times (c_c + c_o)/|u0| (u0 is a difference of the two concentrations)."""
    spec, p, rows = observed["spec"], observed["p"], observed["rows"]
    s = list(spec.model.species_ids).index(cw.part3.SPECIES)
    states = [u for u, _ in cw.HOMO["states"]]
    g = float(np.asarray(p.integer_conductance_pL_per_s)[0, 0, states.index("open")])
    vc, vo = cw.CELL_pL, cw.NODE_pL
    most = 16 // 2
    worst = 0.0
    for k in sorted(rows)[:-1]:
        a, b = rows[k], rows[k + 1]
        if int(a.integer_events[0]) != int(b.integer_events[0]):
            continue
        nc = float(np.asarray(p.amount_reference)[s, 0] + a.amount_increment[s, 0])
        no = float(np.asarray(p.extracellular_amount_reference)[s, 1])
        no += float(a.extracellular_amount_increment[s, 1])
        u0 = nc / vc - no / vo
        lam = g * int(a.integer_counts[0, states.index("open")]) * (1.0 / vc + 1.0 / vo)
        integral = -u0 * math.expm1(-lam * cw.DT) / lam if lam > 0 else u0 * cw.DT
        booked = float(b.integer_transferred_fmol[0, 0] - a.integer_transferred_fmol[0, 0])
        record = getattr(a, RECORD)[0, states.index(state)] * scale
        predicted = g * float(np.sum(record)) * integral
        bound = uc.rounding_bound(int(a.integer_events[0]), most)
        books = abs(float(a.integer_transferred_fmol[0, 0]))
        books += abs(float(b.integer_transferred_fmol[0, 0]))
        pools = abs(booked) * (abs(nc / vc) + abs(no / vo)) / abs(u0) if u0 else 0.0
        tolerance = bound * g * abs(integral) + FLUX_C * np.finfo(float).eps * (books + pools)
        worst = max(worst, abs(predicted - booked) / tolerance if tolerance else abs(predicted))
    return worst


def test_sum_to_flux_over_event_free_steps(observed):
    """§3's sum-to-flux with teeth: within its tolerance on every event-free step of the homo's
    site, while a record whose total drifts by 1e-12 per event and the conductance put on the
    closed state each leave it."""
    assert _flux_error(observed) <= 1.0
    events = int(observed["rows"][max(observed["rows"])].integer_events[0])
    assert _flux_error(observed, scale=(1 + 1e-12) ** events) > 1.0
    assert _flux_error(observed, state="closed") > 1.0


def test_the_readout_at_every_row(observed):
    """The host readout is resolved at every row, and FR-52's two quantities (the initial units
    still conducting, the units formed in the window) are the reference's exact sums within the
    bound."""
    rows, block, p = observed["rows"], observed["block"], observed["p"]
    declaration = observed["declaration"]
    references = {c["id"]: exact.read_run(block, rows, c["id"]) for c in block["cohorts"]}
    conducting = {"homo_units": ["open"], "hetero_units": []}
    for step, row in rows.items():
        for entry in iup.cohort_readout(declaration, p, row, delta_c_mM={"flow": 1.0}):
            assert entry["resolved"], (step, entry["problems"])
            exact_row = references[entry["cohort"]]["rows"][step]
            want_initial = sum(exact_row["exact"][s][0] for s in conducting[entry["cohort"]])
            want_inside = sum(exact_row["exact"][s][2] for s in entry["states"])
            for got, want in ((entry["initial_conducting_units"], want_initial),
                              (entry["inside_units"], want_inside)):  # fmt: skip
                assert abs(Fraction(got) - want) <= len(entry["states"]) * exact_row["bound"]


def test_a_restart_inside_the_window_is_bitwise_and_its_plants_are_caught(observed):
    """Case E: the run cut at 1.5 s (inside both windows, between events) and resumed with the same
    seed is bitwise the uninterrupted run, the record included. The record set at the cut to its
    start values (as if initial were taken at the resume), or zeroed, is caught."""
    spec, windows, rows = observed["spec"], observed["windows"], observed["rows"]
    cut = int(round(cw.RESTART_S / cw.DT))
    checkpoint = next(w.checkpoint_at(float(t)) for w in windows for t in np.asarray(w.times)
                      if abs(t - cw.RESTART_S) < 1e-9)  # fmt: skip
    _, resumed = _collect(spec, checkpoint)
    for k in range(cut, len(rows)):
        for a, b in zip(resumed[k], rows[k], strict=True):
            assert np.asarray(a).tobytes() == np.asarray(b).tobytes(), k
    start = getattr(rows[0], RECORD)
    for name, planted in (("reset", start), ("zeroed", np.zeros_like(start))):
        state = checkpoint.state._replace(**{RECORD: planted})
        _, again = _collect(spec, dataclasses.replace(checkpoint, state=state))
        end = len(rows) - 1
        assert getattr(again[end], RECORD).tobytes() != getattr(rows[end], RECORD).tobytes(), name
