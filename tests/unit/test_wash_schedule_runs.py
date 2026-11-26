"""cells.operator.scheduled_compartment_wash@1 (FR-27, D246) compiled, through the runner: one world, about 35 s.

Its reason: the only path through the compiled event map, the control arrays at its event time and
the runner's host checks on every accepted row (the domain with each event's heat, every ledger with
the wash's terms). The review's well (60 fmol free, 30 on the specimen's sites, 10 on the wall's)
is half washed with buffer at the tracer's trace at t_e. The row at t_e is the state before the
wash; from the next row on, the sample holds 30, the ions are unchanged bit for bit, and the four
amounts (free, both sites' bound, the sample less the supply) sum to 100 fmol on every row.

Which time each stock is read at (the Lean lane's request):
- **At the wash event, t_e = 0.02 s.** The history's row at t_e is the state the wash acts on, so
  the wall's 10 fmol and the specimen's 30 are read there.
- **The first saved row after it is 0.01 s later, at 0.03 s.** The wash books the sample at the
  event, so its 30 fmol is exact on that row and every later one. The two populations' bound stocks
  on that row are not the event's: they have begun to re-equilibrate with the halved free tracer.
  The wall's relaxation time is about 1 / (k_off + k_on c) = 1 / (0.6 + 0.3) per s, about 1.1 s
  (**S**), so 0.01 s is a small part of it.
"""

from decimal import Decimal
from fractions import Fraction

import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.registry.models import get_model
from tests.unit.test_wash_schedule import close, reference
from validation.tissue import wash_schedule_fixtures as wfx

DT, T_E, END = 0.01, 0.02, 0.05


def test_the_tracer_wash_runs_in_one_set_of_books():
    raw = wfx.with_wash(
        wfx.well(dt=DT, end=END, observation_times=[0.0, T_E, END]),
        ["well"],
        [(T_E, "well", 0.5, {wfx.TRACER: wfx.TRACE_mM})],
    )
    spec = parse_spec(raw)
    result = run(spec)  # Its host checks run on every accepted row; a failure raises.
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    times = np.asarray(result.times, dtype=float)
    k = int(np.flatnonzero(times == T_E)[0])
    s = list(spec.model.species_ids).index(wfx.TRACER)
    w = [c.id for c in spec.model.extracellular].index("well")
    increment = np.asarray(h.extracellular_amount_increment)
    free = np.asarray(p.extracellular_amount_reference)[s, w] + increment[:, s, w]
    bound = np.asarray(p.site_bound_anchor_fmol) + np.asarray(h.site_bound_increment_fmol)
    collected = np.asarray(h.wash_collected_fmol)[:, :, w]
    supplied = np.asarray(h.wash_supplied_fmol)[:, :, w]
    assert free[k] == 60.0 and not collected[k].any()  # The row at t_e: before the wash.
    assert collected[k + 1, s] == 30.0 and collected[-1, s] == 30.0
    assert supplied[-1, s] == 0.5 * wfx.V_WELL * wfx.TRACE_mM
    total = free + bound.sum(axis=1) + collected[:, s] - supplied[:, s]
    assert np.max(np.abs(total - 100.0)) <= 1e-12
    for i, z in enumerate(spec.model.valence):
        if z:  # f n out and the same in, bit for bit; the well's amount never moves.
            assert collected[-1, i].tobytes() == supplied[-1, i].tobytes()
            assert not np.any(increment[:, i, w])
    heat, _, _ = reference(free[k], wfx.V_WELL, 0.5, wfx.TRACE_mM, spec.model.temperature_K)
    last = np.asarray(h.wash_last_mixing_heat_pJ)[:, w]
    assert close(float(np.asarray(h.wash_mixing_heat_pJ)[-1, w]), heat, 64)
    assert last[-1] == np.asarray(h.wash_mixing_heat_pJ)[-1, w] and heat > Decimal(0)
    assert np.asarray(h.wash_applied)[-1, w] == 1


def test_a_nodes_own_wall_runs_as_the_stand_in_did():
    """FR-28 (D268, option A; docs/NODE_SURFACE_SITES_DESIGN.md §8's compiled pair): the review's
    well with its wall owned by the node, and the same well with the review's stand-in cell, each
    washed by half at 0.05 s and run to 0.1 s at 10 ms through the runner (its host checks on every
    accepted row). The rows compared are the history's accepted steps: the row at 0.05 s holds the
    stock the wash acts on, and the first row after the wash is 0.01 s later, at 0.06 s, when the
    wall has begun to re-equilibrate. The request says the numbers are unaffected: the well's free
    tracer and both populations' R, B and bound net are bitwise equal on every row; the heat at
    the well, the work and the magnitudes, from two programs of different shape, within 16 ulps;
    free, bound and the
    sample sum to 100 fmol within 1e-12 on every row. Two compiles: about 25 s on a quiet CPU (its
    tier row is measured on the timed lane). Its reason (D224): the request's statement that the
    numbers are unaffected needs the runner."""
    histories = {}
    for wall in ("node", "stand-in"):
        raw = wfx.with_wash(
            wfx.well(wall=wall, end=0.1),
            ["well"],
            [(0.05, "well", 0.5, {wfx.TRACER: wfx.TRACE_mM})],
        )
        spec = parse_spec(raw)
        result = run(spec)
        _, p = get_model(spec.model).initial_values(spec)
        w = [c.id for c in spec.model.extracellular].index("well")
        s = list(spec.model.species_ids).index(wfx.TRACER)
        free = (
            np.asarray(p.extracellular_amount_reference)[s, w]
            + np.asarray(result.history.extracellular_amount_increment)[:, s, w]
        )
        histories[wall] = (result.history, free, p, s, w)
    (hn, free_n, pn, s, w), (hs, free_s, _, _, _) = histories["node"], histories["stand-in"]
    assert free_n.tobytes() == free_s.tobytes()
    for name in ("site_free_increment_fmol", "site_bound_increment_fmol", "site_bound_net_fmol"):
        assert np.asarray(getattr(hn, name)).tobytes() == np.asarray(getattr(hs, name)).tobytes()
    for name in ("site_outside_dissipated_energy_pJ", "site_work_pJ", "site_energy_magnitude_pJ"):
        a, b = np.asarray(getattr(hn, name)), np.asarray(getattr(hs, name))
        if name == "site_outside_dissipated_energy_pJ":
            a, b = a[:, w], b[:, w]
        np.testing.assert_allclose(a, b, rtol=16 * np.finfo(float).eps, atol=0)
    bound = (np.asarray(pn.site_bound_anchor_fmol) + np.asarray(hn.site_bound_increment_fmol)).sum(
        1
    )
    sample = (
        np.asarray(hn.wash_collected_fmol)[:, s, w] - np.asarray(hn.wash_supplied_fmol)[:, s, w]
    )
    assert np.max(np.abs(free_n + bound + sample - 100.0)) <= 1e-12


@pytest.mark.parametrize("fraction", ["3/7", "1/2"])
def test_an_unchanged_ion_is_collected_and_supplied_alike_at_any_fraction(fraction):
    """D266, a user's finding: the review's well without sites (1 uL), washed three times by 3/7 or
    1/2 of its liquid, compiled through the runner, whose host checks run on every accepted row at
    their tolerances. Before the fix, at 3/7 chloride's records ended one ulp (2^-25 fmol) apart and
    the outside ledger refused the run; at 1/2 they were equal. Now both runs complete, every ion's
    amount never moves, its collected and supplied records are equal bit for bit at every row, and
    both are the events' f n (eight eps). The two share one compiled program: about 22 s."""
    f = float(Fraction(fraction))
    times = (0.02, 0.04, 0.06)
    raw = wfx.with_wash(
        wfx.well(sites=False, volume=1e6, dt=0.01, end=0.08),
        ["well"],
        [(t, "well", f, {wfx.TRACER: wfx.TRACE_mM}) for t in times],
    )
    spec = parse_spec(raw)
    result = run(spec)  # Its host checks run on every accepted row; a failure raises.
    _, p = get_model(spec.model).initial_values(spec)
    h = result.history
    w = [c.id for c in spec.model.extracellular].index("well")
    ions = np.flatnonzero(spec.model.valence)
    amounts = np.asarray(h.extracellular_amount_increment)[:, ions, w]
    assert not np.any(amounts)  # Every ion's amount never moves.
    collected = np.asarray(h.wash_collected_fmol)[:, ions, w]
    supplied = np.asarray(h.wash_supplied_fmol)[:, ions, w]
    assert collected.tobytes() == supplied.tobytes()  # Equal bit for bit at every row.
    count = np.asarray(h.wash_applied)[:, w]
    assert count[-1] == len(times)
    expected = count[:, None] * f * np.asarray(p.extracellular_amount_reference)[ions, w]
    np.testing.assert_allclose(collected, expected, rtol=8 * np.finfo(float).eps, atol=0)
