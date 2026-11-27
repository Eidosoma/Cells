"""FR-43 part 2B (D315): one pool at changing volume, the engine's own checks (no reference).

validation/tissue/shared_inventory_fixtures.swelling_cell: one quiescent cell swelling under water
(declared first) against a bath at 0.4 of its osmolarity, with the impermeant tracer S and D152's
passive A + B <-> C beside it. Both read the cell's volume current at their split parts.
- C2.5: with every multiplier 0, S keeps its amount bit for bit at every row, its concentration is
  n0 / V(t) at every row to rounding, and it is half the start where V first reaches 2 V0.
- C2.7: F(N, V) + U(V) - F(N0, V0) - U(V0) = booked work - booked heat (the network's and the bath's
  water work; the network's and water's heat). F is computed here from the engine's amounts and
  volume, not from its ledger code; U = 0 (no modulus). The residual shrinks at second order
  between dt and dt/2 (ratio in [3.6, 4.4], Strang over second-order half-steps), and the network
  reading the declared volume V0 instead is refused by the engine's own energy ledger.
Its reason and cost: three runs of the swelling cell over 10 s (seconds as the tier tool measures).

FR-65 (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §4, §6.1; development evidence, no registered
criterion): cells.operator.scheduled_species_turnover@1 making and clearing S in the same swelling
cell, declared after water, at h, 2h and 4h. S keeps turnover's closed form at rounding; V, water's
heat, the bath's water work and turnover's work converge to an in-test reference at second order;
the endpoint identity, with turnover's work, is amendment 3's stepped entry, which a booking at V0
fails; a saved run holds amounts and volumes apart for replay (checked once against one saved
file) and resumes bitwise; labels leave the physics bitwise and follow a production cohort; A1
without the coupling, the symport and the bath schedule run beside water and turnover. The seconds
of each are in its docstring (D224).
"""

import math

import jax
import numpy as np
import pytest

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.electrochemistry import R
from cells.operators import species_reactions as sr
from cells.registry.models import get_model
from validation.tissue import shared_inventory_fixtures as sif

END = 10.0  # s: C2.7's horizon, most of the way to 2 V0 (reached at about 12.8 s).
DT = 0.01


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def outcome(raw):
    spec = parse_spec(raw)
    result = run(spec)  # Every host check on every accepted row.
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    n = np.asarray(p.amount_reference)[:, 0][None, :] + np.asarray(h.amount_increment)[:, :, 0]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0]
    return spec, ids, h, n, v


def test_c25_a_tracer_keeps_its_amount_and_dilutes_with_the_volume():
    spec, ids, _, n, v = outcome(sif.swelling_cell(network_multiplier=0.0, dt=DT, end=40.0))
    s = n[:, ids.index("S")]
    assert np.all(s == s[0])  # Bit for bit at every row.
    assert float(np.max(np.abs((s / v) * v - s[0]))) <= 4 * np.finfo(float).eps * s[0]
    crossed = np.flatnonzero(v >= 2 * v[0])
    assert len(crossed), "the cell never reached 2 V0"
    halved = (s[crossed[0]] / v[crossed[0]]) / (s[0] / v[0])
    assert 0.49 < halved <= 0.5, halved


def endpoint_residual(raw):
    """max |dF - (work - heat)| over the energy scale (largest |dF| + |heat| + |work|)."""
    spec, ids, h, n, v = outcome(raw)
    rt = 1e-3 * R * raw["model"]["temperature_K"]  # pJ/fmol.
    network = next(o for o in raw["model"]["operators"] if o["law"] == sr.LAW_ID)
    standard = np.zeros(len(ids))
    for s in network["species"]:  # Every other row's standard term is constant: it cancels.
        standard[ids.index(s["id"])] = rt * (
            s["standard_mu_RT"] - math.log(network["standard_concentration_mM"])
        )
    free = np.sum(rt * n * (np.log(n / v[:, None]) - 1.0) + standard[None, :] * n, axis=1)
    work = np.asarray(h.reaction_work_pJ)[:, 0] + np.asarray(h.bath_water_work_pJ).sum(axis=1)
    heat = np.asarray(h.reaction_dissipated_energy_pJ)[:, 0] + np.asarray(
        h.water_dissipated_energy_pJ
    ).sum(axis=1)
    residual = (free - free[0]) - (work - heat)
    scale = float(np.max(np.abs(free - free[0])) + np.max(np.abs(heat)) + np.max(np.abs(work)))
    return float(np.max(np.abs(residual))) / scale


def test_c27_the_energy_identity_closes_at_second_order_and_the_v0_plant_is_refused():
    coarse = endpoint_residual(sif.swelling_cell(dt=DT, end=END))
    fine = endpoint_residual(sif.swelling_cell(dt=DT / 2, end=END))
    assert 3.6 <= coarse / fine <= 4.4, (coarse, fine)
    original = sr.LocalSpeciesReactions.half_step

    def planted(self, *args, view=None, **kwargs):  # The declared volume V0: no view.
        return original(self, *args, **kwargs)

    jax.clear_caches()  # The runner's compiled rollout is cached per model: retrace the plant.
    sr.LocalSpeciesReactions.half_step = planted
    try:
        with pytest.raises(NumericalError, match="energy"):
            run(parse_spec(sif.swelling_cell(dt=DT, end=END)))
    finally:
        sr.LocalSpeciesReactions.half_step = original
        jax.clear_caches()


# ------------------------------------------------------------------ FR-65: turnover, swelling
#
# docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §4 and §6.1 (development evidence, no registered
# criterion): the swelling cell with S made and cleared by
# cells.operator.scheduled_species_turnover@1, declared after water, the network active. S grows to
# about 10 fmol, far below P/k (1,000 fmol), so its net move, and with it a booking at V0, stays
# large while V moves from V0 to about 1.9 V0.

H = 0.01  # s: h, the finest rung; 2h and 4h are the others (the stepped entry's three).
HORIZON = 10.0  # s.
EVERY = 0.5  # s: the observed rows.
EPS = np.finfo(float).eps
FLOOR = 1e-8  # C2.6's: below it a ratio is too close to the reference's own accuracy.
BAND = (3.6, 4.4)  # Second order, the errors' ratio between 2h and h.
TURNOVER = "cells.operator.scheduled_species_turnover@1"


def turnover_world(dt=H, **kwargs):
    return sif.swelling_turnover(dt=dt, end=HORIZON, every=EVERY, **kwargs)


@pytest.fixture(scope="module")
def rungs():
    """{dt: (spec, result)} at h, 2h and 4h: three compiled runs, every host check on every row."""
    out = {}
    for dt in (H, 2 * H, 4 * H):
        spec = parse_spec(turnover_world(dt))
        out[dt] = spec, run(spec)
    return out


def books(spec, result):
    """{name: [row] array} of one run at every accepted row: the cell's volume V, every species'
    amount n [row, species], S's, the energy identity's terms and its residual r (pJ), and the
    identity's own magnitude s (amendment 3's: the bookings' and every species row's G term)."""
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    n = np.asarray(p.amount_reference)[:, 0][None, :] + np.asarray(h.amount_increment)[:, :, 0]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0]
    raw = spec.to_dict()
    rt = 1e-3 * R * raw["model"]["temperature_K"]
    network = next(o for o in raw["model"]["operators"] if o["law"] == sr.LAW_ID)
    standard = np.zeros(len(ids))
    for s in network["species"]:  # Every other row's standard term is 0, as turnover books S's.
        standard[ids.index(s["id"])] = rt * (
            s["standard_mu_RT"] - math.log(network["standard_concentration_mM"])
        )
    g = rt * n * (np.log(n / v[:, None]) - 1.0) + standard[None, :] * n  # [row, species]
    terms = dict(
        network_work=np.asarray(h.reaction_work_pJ)[:, 0],
        bath_work=np.asarray(h.bath_water_work_pJ).sum(axis=1),
        turnover_work=np.asarray(h.turnover_work_pJ)[:, 0],
        network_heat=np.asarray(h.reaction_dissipated_energy_pJ)[:, 0],
        water_heat=np.asarray(h.water_dissipated_energy_pJ).sum(axis=1),
    )
    free = g.sum(axis=1)
    work = terms["network_work"] + terms["bath_work"] + terms["turnover_work"]
    heat = terms["network_heat"] + terms["water_heat"]
    magnitude = sum(np.abs(x) for x in terms.values()) + np.abs(g).sum(axis=1)
    return dict(
        times=np.asarray(result.times),
        V=v,
        n=n,
        S=n[:, ids.index(sif.fx.SPECIES)],
        residual=(free - free[0]) - (work - heat),
        magnitude=magnitude,
        **terms,
    )


def common(rows, dt, step=4 * H):
    """rows sampled at the multiples of `step` (the coarsest rung's grid)."""
    every = int(round(step / dt))
    return {k: v[::every] for k, v in rows.items()}


def s_closed(times, n0, make, clear):
    """S's amount from n0 at time 0: n0 e^{-kt} + (P/k)(1 - e^{-kt}), formed with expm1 so the
    early rows keep their digits."""
    decay = np.expm1(-clear * times)  # e^{-kt} - 1.
    return n0 + n0 * decay - (make / clear) * decay


def reference(spec, times, make=sif.TURNOVER_MAKE):
    """FR-65's in-test reference (development evidence, not code-blind): the cell's volume and the
    network's amounts as one ODE, S from turnover's closed form, with the quadratures of water's
    heat, the bath's water work and turnover's work (RT ln(n_S/V) dn_S/dt, the continuous form of
    its exact bookings), by SciPy's Radau at rtol 1e-12. The right side is the engine's own rate
    functions at the bound layout (water_rates, the network's route_rates), so it checks the
    splitting and the time integration, not the laws. `make`: S's production (a planted value
    moves the reference)."""
    from scipy.integrate import solve_ivp

    from cells.definitions import pump_composite_spec as cs
    from cells.operators import osmotic_water as water

    state0, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    rows = np.asarray(p.reaction_rows)
    s_row = ids.index(sif.fx.SPECIES)
    controls = cs.control_values(spec, [0.0])
    availability = np.asarray(controls.water)[0]
    multiplier = np.asarray(controls.reaction_multiplier)[0]
    nu = np.asarray(p.reaction_products) - np.asarray(p.reaction_reactants)  # [rows, route]
    anchor = np.asarray(p.amount_reference)
    v0 = float(np.asarray(p.volume)[0])
    s0 = float(anchor[s_row, 0])
    clear = sif.TURNOVER_CLEAR
    rt = 1e-3 * R * float(np.asarray(p.temperature))

    def state_at(t, y):
        increment = np.asarray(state0.amount_increment).copy()
        increment[rows, 0] = y[1 : 1 + rows.size] - anchor[rows, 0]
        increment[s_row, 0] = s_closed(np.asarray(t), s0, make, clear) - anchor[s_row, 0]
        volume = np.asarray(state0.volume_increment_pL).copy()
        volume[0] = y[0] - v0
        return state0._replace(amount_increment=increment, volume_increment_pL=volume)

    def rhs(t, y):
        state = state_at(t, y)
        w = water.water_rates(state, availability, p, xp=np)
        volumes = (
            np.asarray(p.volume) + state.volume_increment_pL,
            np.asarray(p.extracellular_volume) + state.extracellular_volume_increment_pL,
        )
        net = sr.network(p, multiplier, xp=np, volumes=volumes)
        rates = sr.route_rates(sr.node_amounts(state, p, xp=np), net, p, xp=np)
        n_s = s_closed(np.asarray(t), s0, make, clear)
        return np.concatenate(
            (
                [w.cell[0]],
                nu @ rates.rate,
                [np.sum(w.heat), np.sum(w.work), rt * math.log(n_s / y[0]) * (make - clear * n_s)],
            )
        )

    y0 = np.concatenate(([v0], anchor[rows, 0], [0.0, 0.0, 0.0]))
    out = solve_ivp(rhs, (0.0, float(times[-1])), y0, method="Radau", t_eval=times,
                    rtol=1e-12, atol=1e-14)  # fmt: skip
    assert out.success, out.message
    y = out.y
    return dict(V=y[0], water_heat=y[-3], bath_work=y[-2], turnover_work=y[-1])


def ratio_errors(engine, ref, quantities):
    """{q: (e_q(2h), e_q(h))}, C2.6's e_q = max |q - q_ref| / max |q_ref| at the common rows."""
    out = {}
    for q in quantities:
        scale = np.max(np.abs(ref[q]))
        out[q] = tuple(float(np.max(np.abs(engine[dt][q] - ref[q]))) / scale for dt in (2 * H, H))
    return out


def in_band(coarse, fine):
    """C2.6's ratio criterion with its floor."""
    if coarse < FLOOR:
        return fine < FLOOR
    return BAND[0] <= coarse / fine <= BAND[1]


def test_fr65_s_keeps_its_closed_form_and_the_volume_follows_its_reference_at_second_order(rungs):
    """FR-65 §4.1 and §6.1. Seconds and reason (D224): about 90 s, the three rungs' compiles and
    runs (shared with the identity's row) and two reference integrations; the claims need the
    swelling cell's own runs.
    - S's amount follows turnover's closed form at every row of every rung, to the bookings'
      rounding over the steps taken (the update reads no volume).
    - V, water's heat, the bath's water work and turnover's cumulative work converge to the
      in-test reference at second order: e(2h) / e(h) in [3.6, 4.4], C2.6's form with its floor.
    Planted: S's amount 1 ulp-scale nudged by 1e-9 of itself at one row fails the closed form, and
    a reference whose S is made 1e-3 faster takes every quantity out of the band."""
    for dt, (spec, result) in rungs.items():
        rows = books(spec, result)
        closed = s_closed(rows["times"], rows["S"][0], sif.TURNOVER_MAKE, sif.TURNOVER_CLEAR)
        steps = len(rows["times"]) - 1
        bound = 8 * EPS * 2 * steps * np.max(np.abs(rows["S"]))  # Two half-steps per step.
        assert np.max(np.abs(rows["S"] - closed)) <= bound, dt
        nudged = rows["S"].copy()
        nudged[len(nudged) // 2] *= 1 + 1e-9
        assert np.max(np.abs(nudged - closed)) > bound
    engine = {dt: common(books(*rungs[dt]), dt) for dt in (H, 2 * H)}
    times = engine[H]["times"]
    assert np.allclose(engine[2 * H]["times"], times, rtol=0, atol=1e-12)
    quantities = ("V", "water_heat", "bath_work", "turnover_work")
    spec = rungs[H][0]
    errors = ratio_errors(engine, reference(spec, times), quantities)
    for q, (coarse, fine) in errors.items():
        assert in_band(coarse, fine), (q, coarse, fine, coarse / fine)
    planted = ratio_errors(engine, reference(spec, times, sif.TURNOVER_MAKE * 1.001), quantities)
    for q, (coarse, fine) in planted.items():
        assert not in_band(coarse, fine), (q, coarse, fine)


def stepped(rungs):
    """Amendment 3's stepped entry of the energy identity at the coarsest rung's rows: (max |r_h|,
    3 est + e_round, d1, d2, e_round)."""
    r = {dt: common(books(*rungs[dt]), dt) for dt in rungs}
    d1 = float(np.max(np.abs(r[2 * H]["residual"] - r[H]["residual"])))
    d2 = float(np.max(np.abs(r[4 * H]["residual"] - r[2 * H]["residual"])))
    est = max(d1 / 3, d2 / 12)
    steps = len(books(*rungs[H])["times"]) - 1
    e_round = 8 * EPS * steps * float(np.max(r[H]["magnitude"]))
    return float(np.max(np.abs(r[H]["residual"]))), 3 * est + e_round, d1, d2, e_round


def test_fr65_the_energy_identity_is_a_stepped_entry_and_the_v0_booking_fails_it(rungs):
    """FR-65 §4.1, amendment 3's stepped entry (e_ref = 0, p = 2) of the endpoint identity
    F(N_t, V_t) - F(N_0, V_0) = W - H, U = 0: W the network's, the bath's water and turnover's work,
    H the network's and water's heat, F computed here from the engine's amounts and volume.
    max |r_h| <= 3 est + e_round, est = max(d1/3, d2/12), and where d1 and d2 exceed 10 e_round the
    order q = log2(d2/d1) lies in [1.5, 3.5].
    Planted (P1): turnover's half-step drops the view and books at V0. Its amounts and V are the
    correct run's (the update reads no volume, and water reads no booking), and a booking at V0
    over-books the work by RT dn ln(V/V0) (F(n, V0) - F(n, V) = RT n ln(V/V0)), so its residual
    is the correct one less RT sum dn ln(V/V0) over the steps, formed here from the h rung: that
    fails the entry and is at least 100 times the correct residual (C2.7's rule, the plant world
    sized so). The engine's own energy ledger refuses the planted run, reported here as the run's
    refusal (§4.1: not relied on). Seconds and reason (D224): about 35 s more than the rungs, the
    planted run's compile and its steps until the ledger refuses it; the miss shows in energy
    only."""
    from cells.operators import species_turnover as st

    worst, allowed, d1, d2, e_round = stepped(rungs)
    assert worst <= allowed, (worst, allowed, d1, d2, e_round)
    if d1 > 10 * e_round and d2 > 10 * e_round:
        assert 1.5 <= math.log2(d2 / d1) <= 3.5, (d1, d2)
    spec, result = rungs[H]
    rows = books(spec, result)
    rt = 1e-3 * R * spec.to_dict()["model"]["temperature_K"]
    v, s = rows["V"], rows["S"]
    middle = 0.5 * (v[1:] + v[:-1])  # The volume a step's bookings see, to second order.
    miss = np.cumsum(rt * np.diff(s) * np.log(middle / v[0]))
    planted = float(np.max(np.abs(rows["residual"][1:] - miss)))
    assert planted > allowed and planted >= 100 * worst, (planted, allowed, worst)
    original = st.ScheduledSpeciesTurnover.half_step

    def at_v0(self, *args, view=None, **kwargs):  # The declared volume V0: no view.
        return original(self, *args, **kwargs)

    jax.clear_caches()  # The runner's compiled rollout is cached per model: retrace the plant.
    st.ScheduledSpeciesTurnover.half_step = at_v0
    try:
        with pytest.raises(NumericalError, match="energy"):
            run(parse_spec(turnover_world(H)))
    finally:
        st.ScheduledSpeciesTurnover.half_step = original
        jax.clear_caches()


def test_fr65_a_saved_run_holds_amounts_and_volumes_apart_and_resumes_bitwise(rungs, tmp_path):
    """FR-65 §4.2: the readouts a replay outside the engine needs, read from the code and the bound
    model by the design, checked here once against one saved file (this test is that check): the h
    rung written by cells.records.io.write_run, its trajectory.npz read back. It holds the state's
    increments of the amounts and volumes at every accepted row and their anchors; at each observed
    row the observed amount is anchor + increment, bit for bit, and the observed concentration times
    the observed volume is the amount, to 4 eps. Planted: the saved amount nudged by 1e-12 of itself
    fails it. A resume mid-run, in process and from a written snapshot, is bitwise the unbroken
    run's (§3.7). Seconds and reason (D224): about 25 s, the two resumed halves (no compile: the
    rung's model is warm) and the files."""
    from cells.records.io import load_snapshot, write_run, write_snapshot

    spec, result = rungs[H]
    write_run(tmp_path / "run", result)
    saved = np.load(tmp_path / "run" / "trajectory.npz")
    for name in (
        "amount_increment",
        "extracellular_amount_increment",
        "volume_increment_pL",
        "extracellular_volume_increment_pL",
        "amount_reference",
        "extracellular_amount_reference",
        "volume",
        "extracellular_volume",
        "observed_amount",
        "observed_cell_volume_pL",
        "observed_cell_concentration_mM",
    ):
        assert name in saved.files, name
    accepted, observed = saved["accepted_times"], saved["observation_times"]
    at = [int(np.flatnonzero(np.isclose(accepted, t, rtol=0, atol=1e-12))[0]) for t in observed]
    amounts = saved["amount_reference"][None] + saved["amount_increment"][at]

    def replays(amount):
        exact = np.array_equal(amount[..., 0], amounts[..., 0])
        volume = saved["observed_cell_volume_pL"][:, None, 0]
        product = saved["observed_cell_concentration_mM"][..., 0] * volume
        close = np.abs(product - amount[..., 0]) <= 4 * EPS * np.abs(amount[..., 0])
        return exact and bool(np.all(close))

    assert replays(saved["observed_amount"])
    nudged = saved["observed_amount"].copy()
    nudged[-1, list(spec.model.species_ids).index(sif.fx.SPECIES), 0] *= 1 + 1e-12
    assert not replays(nudged)
    middle = result.checkpoint_at(HORIZON / 2)
    resumed = run(spec, middle)
    for a, b in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[middle.step_index :])
    write_snapshot(tmp_path / "middle", result.spec, middle)
    loaded = load_snapshot(tmp_path / "middle")
    again = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a), np.asarray(b)[middle.step_index :])


WINDOW = (2.0, 4.0)  # s: the labelled rung's production window, its cohort.
A1_DT, A1_END = 0.01, 10.0  # s: A1 in a swelling cell, within water's relaxation bound.


def test_fr65_labels_beside_water_leave_the_physics_bitwise_and_follow_a_cohort(rungs):
    """FR-65 §3.3 and §4.1: the h rung with FR-42's labels on S
    (cells.operator.neutral_arrival_labels@1), the production in WINDOW joining the cohort's label.
    Every physical field is bitwise the
    unlabelled rung's, and the cohort's labelled amount follows its closed form, whatever V does:
    (P/k)(1 - e^{-k(t - t1)}) inside the window and that times e^{-k(t - t2)} after it, to the
    label shares' rounding. Planted: the cohort's closed form 1e-6 high fails. Seconds and reason
    (D224): about 30 s, one compile and 1,000 steps; labels beside water are newly admitted."""
    from validation.gene_regulation import worlds as gw

    spec, result = rungs[H]
    raw = gw.with_share_labels(turnover_world(H), rows=(sif.fx.SPECIES,), window=WINDOW,
                               labels=("base", "cohort"))  # fmt: skip
    labelled = run(parse_spec(raw))
    plain = dict(zip(result.history._fields, result.history, strict=True))
    for name, value in zip(labelled.history._fields, labelled.history, strict=True):
        if not name.startswith("label_"):
            assert np.array_equal(np.asarray(value), np.asarray(plain[name])), name
    rows = books(spec, result)
    times = rows["times"]
    share = np.asarray(labelled.history.label_share)[:, 0, 1, 0]  # S, the cohort, the cell.
    cohort = share * rows["S"]
    make, clear = sif.TURNOVER_MAKE, sif.TURNOVER_CLEAR
    t1, t2 = WINDOW
    inside = (make / clear) * -np.expm1(-clear * np.clip(times - t1, 0.0, t2 - t1))
    closed = np.where(times <= t2, inside, inside * np.exp(-clear * np.maximum(times - t2, 0.0)))
    bound = 64 * EPS * (len(times) - 1) * np.max(rows["S"])

    def follows(value):
        return bool(np.all(np.abs(value - closed) <= bound))

    assert follows(cohort), float(np.max(np.abs(cohort - closed)))
    assert not follows(closed * (1 + 1e-6) + (closed == 0) * 1e-6)


@pytest.mark.parametrize("coupling", [False, True], ids=["without the coupling", "with it"])
def test_fr65_a1_runs_in_a_swelling_cell(coupling, tmp_path):
    """FR-65 §3.6, and its coupling step's T2 (§11.8): A1 (the gene unit and turnover of X) in a
    swelling cell, and with the coupling's Hill factor of X routed onto transcription's
    initiation, the composed check of its readers (§3.8). Every host check on every row, and X,
    turnover's alone, follows its closed form at the bookings' rounding while V moves. The sheet's
    A1 starts X at its steady state P/k, so the closed form is that constant: the swelling, which
    dilutes X's concentration, leaves its amount there. With the coupling:
    - transcription's route has coupling_factor b + (1 - b) f(n_X/V) at every observed row (the gene
      unit observes only its own state, so its routed rate has no column: tier-1's row 4 checks it);
    - the saved records, against one saved file (this test is that check): write_run's
      trajectory.npz holds X's amounts and V, from which its coupling_factor follows to rounding;
    - a resume mid-run, in process and from a written snapshot, is bitwise the unbroken run's.
    Planted: the closed form at k x 1.001 drifts off X and misses; the factor at V0 misses.
    Seconds and reason (D224): about 40 s without the coupling and 80 s with it (one compile each,
    and two resumed halves), the gene unit beside water and turnover, and then the coupling, newly
    admitted together."""
    from cells.records.io import load_snapshot, write_run, write_snapshot
    from validation.gene_regulation import sheet_check as sheet

    raw = sif.swelling_a1(coupling=coupling, dt=A1_DT, end=A1_END, every=A1_END / 4)
    spec = parse_spec(raw)
    result = run(spec)  # Every host check on every accepted row.
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history
    x = np.asarray(p.amount_reference)[ids.index("X"), 0] + np.asarray(h.amount_increment)[
        :, ids.index("X"), 0
    ]
    v = np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0]
    assert v[-1] > 1.05 * v[0]  # The cell swells.
    a = sheet.A1
    make, clear = float(a["P_on"]), float(a["k_X"])
    closed = s_closed(np.asarray(result.times), x[0], make, clear)
    bound = 8 * EPS * 2 * (len(x) - 1) * np.max(np.abs(x))
    assert np.max(np.abs(x - closed)) <= bound, float(np.max(np.abs(x - closed)))
    planted = s_closed(np.asarray(result.times), x[0], make, clear * 1.001)
    assert np.max(np.abs(x - planted)) > bound
    if not coupling:
        return
    names = ("half_saturation_mM", "coefficient", "basal")
    k, n, b = (float(np.asarray(getattr(p, "coupling_route_" + f))[0]) for f in names)

    def factor(amount, volume):
        a = (np.asarray(amount) / np.asarray(volume) / k) ** n
        return b + (1 - b) * a / (1 + a)

    at = [int(np.flatnonzero(np.asarray(result.times) == t)[0]) for t in
          spec.experiment.observation_times]  # fmt: skip
    observed = np.asarray(result.observations.coupling_factor)[:, 0]
    assert np.allclose(observed, factor(x[at], v[at]), rtol=1e-13, atol=0.0)
    assert not np.allclose(observed, factor(x[at], v[0]), rtol=1e-6, atol=0.0)  # At V0.
    write_run(tmp_path / "run", result)
    saved = np.load(tmp_path / "run" / "trajectory.npz")
    rows = [int(np.flatnonzero(np.isclose(saved["accepted_times"], t, rtol=0, atol=1e-12))[0])
            for t in saved["observation_times"]]  # fmt: skip
    k_x = ids.index("X")
    amount = saved["amount_reference"][k_x, 0] + saved["amount_increment"][rows, k_x, 0]
    volume = saved["volume"][0] + saved["volume_increment_pL"][rows, 0]
    replayed = saved["observed_coupling_factor"][:, 0]
    assert np.allclose(replayed, factor(amount, volume), rtol=1e-13, atol=0.0)
    middle = result.checkpoint_at(A1_END / 2)
    resumed = run(spec, middle)
    for a_, b_ in zip(resumed.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a_), np.asarray(b_)[middle.step_index :])
    write_snapshot(tmp_path / "middle", result.spec, middle)
    loaded = load_snapshot(tmp_path / "middle")
    again = run(loaded.spec, loaded.checkpoint)
    for a_, b_ in zip(again.history, result.history, strict=True):
        assert np.array_equal(np.asarray(a_), np.asarray(b_)[middle.step_index :])


@pytest.mark.parametrize("companion", ["symport", "bath schedule"])
def test_fr65_a_companion_beside_water_and_turnover(companion):
    """FR-65 §3.6, the lead's ruling (a pairing that newly parses gets one composed-world check):
    turnover making and clearing S in the cell beside water and
    cells.operator.k_anion_symport_mass_action@1 (its volume factor reads the same V that turnover's
    osmolytes move), or cells.operator.scheduled_bath_composition@1 (an isosmotic step at 0.05 s,
    its event changing the held bath's anchors and water's exchange with it). Every host check on
    every row of 100 steps of 1 ms, and S's amount against its closed form at the bookings'
    rounding. Planted: S nudged by 1e-9 of itself at one row misses it.
    Seconds and reason (D224): about 25 s each, one compile and 100 steps."""
    fx = sif.fx
    make, clear = sif.COMPANION_MAKE, sif.COMPANION_CLEAR
    spec = parse_spec(sif.companion_world(companion))  # The fixture module's, since §11.
    result = run(spec)  # Every host check on every accepted row.
    _, p = get_model(spec.model).initial_values(spec)
    row = list(spec.model.species_ids).index(fx.SPECIES)
    s = np.asarray(p.amount_reference)[row, 0] + np.asarray(result.history.amount_increment)[
        :, row, 0
    ]
    closed = s_closed(np.asarray(result.times), s[0], make, clear)
    bound = 8 * EPS * 2 * (len(s) - 1) * np.max(np.abs(s))
    assert np.max(np.abs(s - closed)) <= bound, float(np.max(np.abs(s - closed)))
    assert s[-1] > 2 * s[0]  # S moves.
    nudged = s.copy()
    nudged[len(s) // 2] *= 1 + 1e-9
    assert np.max(np.abs(nudged - closed)) > bound


# ------------------------------------------------------------------ the coupling beside water
# FR-65's coupling step (docs/TURNOVER_CHANGING_VOLUME_DESIGN.md §11.8): T1, the water door, at
# every place the coupling is evaluated; T2's labelled row. Tier 1's rows are in
# test_species_regulated_availability.py.


def _hill(x, k, n, law):
    """x^n / (K^n + x^n) (activation, law 1) or K^n / (K^n + x^n) (inhibition, law 2), plainly."""
    a = (np.asarray(x, dtype=float) / k) ** n
    return a / (1.0 + a) if law == 1 else 1.0 / (1.0 + a)


@pytest.fixture(scope="module")
def door_rungs():
    """T1 (sif.water_door, version 2) at h, 2h and 4h: three compiled runs, every host check on
    every row."""
    out = {}
    for dt in (H, 2 * H, 4 * H):
        spec = parse_spec(sif.water_door(dt=dt, end=HORIZON, every=EVERY))
        out[dt] = spec, run(spec)
    return out


def door_rows(spec, result):
    """{name: [accepted row] array} of one door run: times, V, R's and S's amounts, s, and every
    route's applied factor [row, route]."""
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    h = result.history

    def amount(name):
        k = ids.index(name)
        return np.asarray(p.amount_reference)[k, 0] + np.asarray(h.amount_increment)[:, k, 0]

    return dict(
        times=np.asarray(result.times),
        V=np.asarray(p.volume)[0] + np.asarray(h.volume_increment_pL)[:, 0],
        R=amount(sif.REGULATOR),
        S=amount(sif.fx.SPECIES),
        s=np.asarray(h.regulatory_state)[:, 0],
        **({"applied": np.asarray(h.coupling_applied_factor)}  # Version 2's record only.
           if hasattr(h, "coupling_applied_factor") else {}),  # fmt: skip
    )


def door_factors(p, c_r, c_s, s):
    """[..., route] each route's factor, written plainly: inst and make (R's activations), gate
    (s), bind (R's inhibition), self (S's inhibition); routes in the declaration's order."""
    k, n = np.asarray(p.coupling_route_half_saturation_mM), np.asarray(p.coupling_route_coefficient)
    b = np.asarray(p.coupling_route_basal)

    def f(i, x, law):
        return b[i] + (1 - b[i]) * _hill(x, k[i], n[i], law)

    routes = [lambda: f(0, c_r, 1), lambda: np.asarray(s, float), lambda: f(2, c_r, 1),
              lambda: f(3, c_r, 2), lambda: f(4, c_s, 2)]  # fmt: skip
    return np.stack([route() for route in routes[: k.shape[0]]], axis=-1)  # @1 has the first two.


def door_reference(spec, *, v0=False):
    """T1's in-test reference (development evidence, not code-blind), dense in time: the cell's
    volume, the network's amounts, S and the state s as one ODE, by SciPy's Radau at rtol 1e-12.
    Water's rate and the network's rates are the engine's own functions at the bound layout, as
    reference() above; the coupling's factors, the two-state law and S's turnover are written
    plainly from the declaration. R is conserved, so its concentration is n_R / V. v0: the
    coupling's factors read V0 (a planted reference). Returns (solution, the layout p, n_R)."""
    from scipy.integrate import solve_ivp

    from cells.definitions import pump_composite_spec as cs
    from cells.operators import osmotic_water as water

    state0, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    rows = np.asarray(p.reaction_rows)
    s_row, r_row = ids.index(sif.fx.SPECIES), ids.index(sif.REGULATOR)
    controls = cs.control_values(spec, [0.0])
    availability = np.asarray(controls.water)[0]
    multiplier = np.asarray(controls.reaction_multiplier)[0]
    make, clear = (float(v) for v in np.asarray(controls.turnover_rate)[0][:2])
    nu = np.asarray(p.reaction_products) - np.asarray(p.reaction_reactants)
    anchor = np.asarray(p.amount_reference)
    v0_ = float(np.asarray(p.volume)[0])
    n_r = float(anchor[r_row, 0] + np.asarray(state0.amount_increment)[r_row, 0])
    k_in = float(np.asarray(p.regulatory_input_half_saturation_mM)[0, 0])
    n_in = float(np.asarray(p.regulatory_input_coefficient)[0, 0])
    k_on, k_off = float(p.regulatory_on_rate[0]), float(p.regulatory_off_rate[0])

    def state_at(y):
        increment = np.asarray(state0.amount_increment).copy()
        increment[rows, 0] = y[1 : 1 + rows.size] - anchor[rows, 0]
        increment[s_row, 0] = y[1 + rows.size] - anchor[s_row, 0]
        volume = np.asarray(state0.volume_increment_pL).copy()
        volume[0] = y[0] - v0_
        return state0._replace(amount_increment=increment, volume_increment_pL=volume)

    def rhs(t, y):
        state = state_at(y)
        at = v0_ if v0 else y[0]
        c_r, c_s = n_r / at, y[1 + rows.size] / at
        f = door_factors(p, c_r, c_s, y[2 + rows.size])
        w = water.water_rates(state, availability, p, xp=np)
        volumes = (
            np.asarray(p.volume) + state.volume_increment_pL,
            np.asarray(p.extracellular_volume) + state.extracellular_volume_increment_pL,
        )
        net = sr.network(p, multiplier * f[3], xp=np, volumes=volumes)
        rates = sr.route_rates(sr.node_amounts(state, p, xp=np), net, p, xp=np)
        d_s = make * f[2] * f[4] - clear * y[1 + rows.size]
        u = _hill(c_r, k_in, n_in, 1)
        d_state = k_on * u * (1 - y[2 + rows.size]) - k_off * y[2 + rows.size]
        return np.concatenate(([w.cell[0]], nu @ rates.rate, [d_s, d_state]))

    y0 = np.concatenate(([v0_], anchor[rows, 0], [anchor[s_row, 0]],
                         [float(state0.regulatory_state[0])]))  # fmt: skip
    out = solve_ivp(rhs, (0.0, float(spec.experiment.end_time)), y0, method="Radau",
                    dense_output=True, rtol=1e-12, atol=1e-14)  # fmt: skip
    assert out.success, out.message
    return out.sol, p, n_r


def test_fr65_coupling_the_water_door_holds_its_identities_at_every_row(door_rungs):
    """FR-65's coupling step, T1 (§11.8; A7's acceptance for version 1.1, "concentration following
    n/V(t) at conserved n"), on the h rung's observed rows: R's amount bitwise constant while V
    grows by 5% or more; the inner model's channel_availability of the population equal to its
    schedule times inst's factor at n_R/V and the row's s; every route's coupling_factor equal to
    its factor at n/V (s for the state route); and the network's reaction_rate_fmol_per_s for bind
    equal to its rate at the row's state with the routed multiplier, from the network's own rate
    functions. Planted: each expected value taken at V0, which the observed one misses. Seconds
    and reason (D224): the rungs' (shared with the next rows): about 150 s for three compiles and
    1,750 steps, the one composed check of every place the coupling is evaluated."""
    from cells.definitions import pump_composite_spec as cs

    spec, result = door_rungs[H]
    rows = door_rows(spec, result)
    _, p = get_model(spec.model).initial_values(spec)
    assert np.all(rows["R"] == rows["R"][0])  # Conserved: nothing moves R.
    assert rows["V"][-1] > 1.05 * rows["V"][0]  # The cell swells.
    model = get_model(spec.model)
    at = [int(np.flatnonzero(rows["times"] == t)[0]) for t in spec.experiment.observation_times]
    obs = result.observations
    for volume, honest in ((rows["V"][at], True), (rows["V"][0], False)):
        want = door_factors(p, rows["R"][at] / volume, rows["S"][at] / volume, rows["s"][at])
        schedule = np.asarray(cs.control_values(spec, [0.0]).channel)[0][0]
        availability = np.asarray(obs.channel_availability)[:, 0]
        checks = (
            np.allclose(availability, schedule * want[:, 0] * want[:, 1], rtol=1e-13, atol=0.0),
            np.allclose(np.asarray(obs.coupling_factor), want, rtol=1e-13, atol=0.0),
        )
        assert all(checks) if honest else not any(checks), (honest, checks)
    multiplier = np.asarray(cs.control_values(spec, [0.0]).reaction_multiplier)[0]
    for j, i in enumerate(at):
        state = model.STATE_TYPE(*(np.asarray(v[i]) for v in result.history))
        volumes = (
            np.asarray(p.volume) + state.volume_increment_pL,
            np.asarray(p.extracellular_volume) + state.extracellular_volume_increment_pL,
        )
        f = door_factors(p, rows["R"][i] / rows["V"][i], rows["S"][i] / rows["V"][i], rows["s"][i])
        net = sr.network(p, multiplier * f[3], xp=np, volumes=volumes)
        rate = sr.route_rates(sr.node_amounts(state, p, xp=np), net, p, xp=np).rate
        observed = np.asarray(obs.reaction_rate_fmol_per_s)[j]
        assert np.allclose(observed, rate, rtol=1e-12, atol=0.0), j
        f0 = door_factors(p, rows["R"][i] / rows["V"][0], 0.0, rows["s"][i])  # At V0's c_R.
        stale = sr.network(p, multiplier * f0[3], xp=np, volumes=volumes)
        at_v0 = sr.route_rates(sr.node_amounts(state, p, xp=np), stale, p, xp=np).rate
        if j > 0:
            assert not np.allclose(observed, at_v0, rtol=1e-9, atol=0.0), j


def test_fr65_coupling_the_water_door_follows_its_reference_at_second_order(door_rungs):
    """T1: V, S and s converge to the in-test reference (door_reference) at second order,
    e(2h) / e(h) in [3.6, 4.4] (C2.6's form with its floor), and so do the applied factors of the
    routes of R and of the state (coupling_applied_factor at each step's end) against their
    factors at the reference's state half a step earlier, where they were evaluated: water's
    first half sets the volume they read. The self-moved route's applied factor is evaluated at
    the midpoint's predictor and is tier 1's row 4 (exact). The energy identity is amendment 3's
    stepped entry, as the first build's swelling cell's. Planted: the reference's coupling factors
    read at V0, which takes V, S or s out of the band. Seconds and reason (D224): the rungs', and
    two reference integrations of about 5 s."""
    engine = {dt: common(door_rows(*door_rungs[dt]), dt) for dt in (H, 2 * H)}
    times = engine[H]["times"]
    spec = door_rungs[H][0]
    solution, p, n_r = door_reference(spec)
    n_rows = int(np.asarray(p.reaction_rows).size)
    ref_at = solution(times)
    ref = dict(V=ref_at[0], S=ref_at[1 + n_rows], s=ref_at[2 + n_rows])
    errors = ratio_errors(engine, ref, ("V", "S", "s"))
    for q, (coarse, fine) in errors.items():
        assert in_band(coarse, fine), (q, coarse, fine, coarse / fine)
    applied = {}
    for dt in (H, 2 * H):
        rows = engine[dt]
        half = solution(rows["times"][1:] - dt / 2)
        f = door_factors(p, n_r / half[0], half[1 + n_rows] / half[0], half[2 + n_rows])
        applied[dt] = rows["applied"][1:, :4] - f[:, :4]
    scale = np.max(np.abs(engine[H]["applied"][:, :4]))
    coarse = float(np.max(np.abs(applied[2 * H]))) / scale
    fine = float(np.max(np.abs(applied[H]))) / scale
    assert in_band(coarse, fine), (coarse, fine, coarse / fine)
    worst, allowed, d1, d2, e_round = stepped(door_rungs)
    assert worst <= allowed, (worst, allowed, d1, d2, e_round)
    if d1 > 10 * e_round and d2 > 10 * e_round:
        assert 1.5 <= math.log2(d2 / d1) <= 3.5, (d1, d2)
    planted, _, _ = door_reference(spec, v0=True)
    at = planted(times)
    stale = dict(V=at[0], S=at[1 + n_rows], s=at[2 + n_rows])
    missed = ratio_errors(engine, stale, ("V", "S", "s"))
    assert not all(in_band(c, f_) for c, f_ in missed.values()), missed


def test_fr65_coupling_version_1_beside_water():
    """T1's @1 run (the lead's ruling 3: @1 beside water is a newly admitted combination): the
    water door without the routed routes, which @1 does not have, at h. Every host check on every
    row; the inner model's channel_availability and every route's coupling_factor at n_R/V and s
    at every observed row. The state's integration is the code @2 inherits, so its order is shown
    by @2's rungs. Planted: the expected values taken at V0, which the observed ones miss. Seconds
    and reason (D224): about 40 s, one compile and 1,000 steps."""
    from cells.definitions import pump_composite_spec as cs

    spec = parse_spec(sif.water_door(version=1, dt=H, end=HORIZON, every=EVERY))
    result = run(spec)
    rows = door_rows(spec, result)
    _, p = get_model(spec.model).initial_values(spec)
    assert rows["V"][-1] > 1.05 * rows["V"][0]
    at = [int(np.flatnonzero(rows["times"] == t)[0]) for t in spec.experiment.observation_times]
    schedule = np.asarray(cs.control_values(spec, [0.0]).channel)[0][0]
    for volume, honest in ((rows["V"][at], True), (rows["V"][0], False)):
        want = door_factors(p, rows["R"][at] / volume, 0.0, rows["s"][at])[:, :2]
        checks = (
            np.allclose(
                np.asarray(result.observations.channel_availability)[:, 0],
                schedule * want[:, 0] * want[:, 1],
                rtol=1e-13,
                atol=0.0,
            ),
            np.allclose(
                np.asarray(result.observations.coupling_factor), want, rtol=1e-13, atol=0.0
            ),
        )
        assert all(checks) if honest else not any(checks), (honest, checks)


def test_fr65_coupling_arm_b_labels_beside_water_leave_the_physics_bitwise():
    """T2's labelled row (§11.8): FR-38 v2's arm B (A1 with transcription's release), labelled and
    unlabelled, in a swelling cell (sif.swelling_arm_b: a short made-up B, water first), with the
    coupling's Hill factor of X routed onto transcription's initiation. Every host check on every
    row; every physical field bitwise the unlabelled run's; transcription's route has
    coupling_factor at n_X/V at every observed row. Planted: the factor at V0, which misses.
    Seconds and reason (D224): about 40 s each, two compiles and 1,000 steps each; labels beside
    the coupling and water are newly admitted."""
    labelled = run(parse_spec(sif.swelling_arm_b("p=0.55 returned")))
    spec = parse_spec(sif.swelling_arm_b("p=0.55 returned unlabelled"))
    plain = run(spec)
    fields = dict(zip(plain.history._fields, plain.history, strict=True))
    for name, value in zip(labelled.history._fields, labelled.history, strict=True):
        if not name.startswith("label_"):
            assert np.array_equal(np.asarray(value), np.asarray(fields[name])), name
    _, p = get_model(spec.model).initial_values(spec)
    ids = list(spec.model.species_ids)
    k_x = ids.index("X")
    at = [int(np.flatnonzero(np.asarray(plain.times) == t)[0]) for t in
          spec.experiment.observation_times]  # fmt: skip
    x = np.asarray(p.amount_reference)[k_x, 0] + np.asarray(plain.history.amount_increment)[
        at, k_x, 0
    ]
    v = np.asarray(p.volume)[0] + np.asarray(plain.history.volume_increment_pL)[at, 0]
    assert v[-1] > 1.01 * v[0]
    names = ("half_saturation_mM", "coefficient", "basal")
    k, n, b = (float(np.asarray(getattr(p, "coupling_route_" + f))[0]) for f in names)
    observed = np.asarray(plain.observations.coupling_factor)[:, 0]
    for volume, honest in ((v, True), (v[0], False)):
        a = (x / volume / k) ** n
        close = np.allclose(observed, b + (1 - b) * a / (1 + a), rtol=1e-13, atol=0.0)
        assert close == honest, honest
