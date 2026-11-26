"""cells.operator.species_regulated_availability@1, A2: the regulatory state compiled, under refinement.

docs/INVENTORY_COUPLING_DESIGN.md §4.4 A2 and Appendix A.3, with the criterion written before any
run (inventory-coupling-m2-20261114-01/HANDOFF.md). D150's face-free world with two 1 pL cells,
S in both, D150's turnover (clearance in each cell, a production route in cell_1), and one state s
of S in both cells (a Hill activation, K 1 µM, n 2). One window program (13-step windows) serves
every arm at every dt (10, 5, 2.5 and 1.25 ms to 0.4 s). The references are computed here from
Appendix A.3, with neither the operator's code nor the Hill helper:
* frozen input (no turnover) and retention (k_on 0): exact to rounding at every row and dt;
* moving input, second order: commitment (k_off 0) under clearance, against its closed form;
  clearance with k_off 5 and a production pulse in cell_1, against a tight ODE solve; U likewise,
  its closed form under clearance checked against quadrature;
* the crossing step brackets the reference's t* at every dt, with θ placed off every grid;
* a cell's prior condition: s0 per cell against s0 written at time 0, bitwise from the first step.
"""

import json
import os
from pathlib import Path

import numpy as np
import pytest
from scipy.integrate import quad, solve_ivp

from cells.definitions.specs import parse_spec
from cells.execution.windows import WindowPolicy, iter_windows
from validation.tissue import regulated_availability_fixtures as rf
from validation.tissue import secreted_species_fixtures as sfx

EPS = np.finfo(float).eps
K, N = 1e-3, 2.0  # mM; Hill coefficient.
VOLUME = 1.0  # pL, both cells.
END, EVERY, WINDOW = 0.4, 0.05, 13
DTS = (0.01, 0.005, 0.0025, 0.00125)
PULSE = (0.1, 0.2)  # s: cell_1's production on [0.1, 0.2), on every dt's grid.
CELLS = ("cell_0", "cell_1")


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "regulated_availability_state.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values)) + "\n")


def world(dt, *, k_on, k_off, s0, c0, clear=(0.0, 0.0), make=0.0, level=None, writes=()):
    raw = sfx.world(
        cells=tuple((c, VOLUME) for c in CELLS),
        nodes=(),
        contacts=(),
        faces=(),
        dt=dt,
        end=END,
        observation_times=[0.0, END],
        concentrations_mM=dict(zip(CELLS, c0, strict=True)),
    )
    raw = sfx.with_turnover(
        raw,
        [
            ("clear_0", "cell_0", "clearance"),
            ("clear_1", "cell_1", "clearance"),
            ("make_1", "cell_1", "production"),
        ],
        [
            ("clear_0", "cell_0", [(0.0, clear[0])]),
            ("clear_1", "cell_1", [(0.0, clear[1])]),
            ("make_1", "cell_1", [(0.0, 0.0), (PULSE[0], make), (PULSE[1], 0.0)]),
        ],
    )
    raw = rf.with_coupling(
        raw,
        species=[sfx.SPECIES],
        states=[
            rf.state(
                "s",
                list(CELLS),
                [("hill_activation", sfx.SPECIES, K, N)],
                on=k_on,
                off=k_off,
                initial=dict(zip(CELLS, s0, strict=True)),
                level=level,
            )
        ],
        writes=writes,
    )
    return parse_spec(raw)


def trajectory(spec):
    """{step k: (s, U, crossing record)} at every accepted row, and the final state."""
    dt, rows, final = spec.execution.dt, {}, None
    for window in iter_windows(spec, WindowPolicy(WINDOW, "full")):
        h = window.history
        for i, t in enumerate(np.asarray(window.times)):
            rows[round(float(t) / dt)] = (
                np.asarray(h.regulatory_state)[i].copy(),
                np.asarray(h.regulatory_input_integral)[i].copy(),
                np.asarray(h.regulatory_crossing_step)[i].copy(),
            )
        final = window.final
    return rows, final


def u_of(c):
    return c**N / (K**N + c**N)


def concentration(t, c0, k, make=0.0):
    """c(t) under first-order clearance k and a production `make` (fmol/s) on PULSE (closed
    form)."""
    n0 = c0 * VOLUME

    def relax(n, k, p, span):
        decay = np.exp(-k * span)
        return n * decay + (p / k * (1.0 - decay) if k > 0 else p * span)

    if t <= PULSE[0] or make == 0.0:
        return relax(n0, k, 0.0, t) / VOLUME
    n1 = relax(n0, k, 0.0, PULSE[0])
    if t <= PULSE[1]:
        return relax(n1, k, make, t - PULSE[0]) / VOLUME
    n2 = relax(n1, k, make, PULSE[1] - PULSE[0])
    return relax(n2, k, 0.0, t - PULSE[1]) / VOLUME


def integral_closed(t, c0, k):
    """U(t) under clearance alone (Appendix A.3, activation)."""
    c = c0 * np.exp(-k * t)
    return np.log((K**N + c0**N) / (K**N + c**N)) / (N * k)


def solve(times, *, k_on, k_off, s0, c0, k, make=0.0):
    """(s, U) at `times` from a tight ODE solve, split at the pulse's edges."""

    def rhs(t, y):
        u = u_of(concentration(t, c0, k, make))
        return [k_on * u * (1.0 - y[0]) - k_off * y[0], u]

    edges = sorted({0.0, END, *(PULSE if make else ())})
    out, y = {}, np.asarray([s0, 0.0])
    for a, b in zip(edges, edges[1:], strict=False):
        sol = solve_ivp(rhs, (a, b), y, method="DOP853", rtol=1e-12, atol=1e-15, dense_output=True)
        for t in times:
            if a < t <= b:
                out[float(t)] = tuple(sol.sol(t))
        y = sol.y[:, -1]
    return out


def compared_rows(dt):
    return [round(j * EVERY / dt) for j in range(1, round(END / EVERY) + 1)]


def test_the_closed_form_integral_is_its_quadrature():
    for c0, k in ((2e-3, 5.0), (1e-4, 2.0)):
        for t in (0.05, 0.2, 0.4):
            numeric, _ = quad(
                lambda tau, c0=c0, k=k: u_of(c0 * np.exp(-k * tau)),
                0.0,
                t,
                epsabs=1e-15,
                epsrel=1e-13,
            )
            assert abs(integral_closed(t, c0, k) - numeric) <= 1e-13


@pytest.mark.parametrize("dt", DTS)
def test_frozen_input_and_retention_are_exact_to_rounding(dt):
    c0 = (2e-3, 1e-3)
    u = u_of(np.asarray(c0))
    for k_on, k_off, s0 in ((50.0, 5.0, (0.1, 0.9)), (0.0, 5.0, (0.6, 0.9))):
        rows, final = trajectory(world(dt, k_on=k_on, k_off=k_off, s0=s0, c0=c0))
        lam = k_on * u + k_off
        target = k_on * u / lam
        worst = 0.0
        for k, (s, integral, _) in rows.items():
            t = k * dt
            s_ref = target + (np.asarray(s0) - target) * np.exp(-lam * t)
            bound = 64 * max(k, 1) * EPS
            worst = max(worst, float(np.max(np.abs(s - s_ref))) / (max(k, 1) * EPS))
            assert np.all(np.abs(s - s_ref) <= bound), (k_on, k, s, s_ref)
            assert np.all(np.abs(integral - u * t) <= bound * max(1.0, float(np.max(u * t)))), (
                k,
                integral,
            )
        assert int(np.asarray(final.state.coupling_step_count)[0]) == round(END / dt)
        record("exact", dt=dt, k_on=k_on, k_off=k_off, worst_error_in_step_eps=worst)


def errors(arm):
    """Largest row error of s and of U at each dt for a moving-input arm."""
    out = []
    for dt in DTS:
        rows, _ = trajectory(world(dt, **arm["engine"]))
        steps = compared_rows(dt)
        reference = arm["reference"]([k * dt for k in steps])
        e_s = max(float(np.max(np.abs(rows[k][0] - reference[k * dt][0]))) for k in steps)
        e_u = max(float(np.max(np.abs(rows[k][1] - reference[k * dt][1]))) for k in steps)
        out.append((dt, e_s, e_u))
    return out


def commitment_reference(times, *, s0, c0, clear, k_on):
    out = {}
    for t in times:
        s, u = [], []
        for i in range(2):
            c = c0[i] * np.exp(-clear[i] * t)
            power = k_on / (N * clear[i])
            s.append(1.0 - (1.0 - s0[i]) * ((K**N + c**N) / (K**N + c0[i] ** N)) ** power)
            u.append(integral_closed(t, c0[i], clear[i]))
        out[t] = (np.asarray(s), np.asarray(u))
    return out


def general_reference(times, *, k_on, k_off, s0, c0, clear, make):
    per_cell = [
        solve(
            times,
            k_on=k_on,
            k_off=k_off,
            s0=s0[i],
            c0=c0[i],
            k=clear[i],
            make=make if i == 1 else 0.0,
        )
        for i in range(2)
    ]
    return {
        t: (
            np.asarray([p[float(t)][0] for p in per_cell]),
            np.asarray([p[float(t)][1] for p in per_cell]),
        )
        for t in times
    }


COMMITMENT = dict(k_on=50.0, k_off=0.0, s0=(0.1, 0.0), c0=(2e-3, 1e-4), clear=(5.0, 2.0))
GENERAL = dict(k_on=50.0, k_off=5.0, s0=(0.2, 0.3), c0=(2e-3, 1e-3), clear=(5.0, 2.0), make=0.01)
ARMS = {
    "commitment": dict(
        engine=COMMITMENT,
        reference=lambda times: commitment_reference(
            times, **{k: COMMITMENT[k] for k in ("s0", "c0", "clear", "k_on")}
        ),
    ),
    "clearance, k_off and a production pulse": dict(
        engine=GENERAL,
        reference=lambda times: general_reference(times, **GENERAL),
    ),
}


@pytest.mark.parametrize("name", sorted(ARMS))
def test_moving_input_is_second_order(name):
    table = errors(ARMS[name])
    orders = [
        (float(np.log2(e_s / f_s)), float(np.log2(e_u / f_u)))
        for (_, e_s, e_u), (_, f_s, f_u) in zip(table, table[1:], strict=False)
    ]
    record("order", arm=name, errors=table, orders_s_and_U=orders)
    for (dt, e_s, e_u), (_, f_s, f_u) in zip(table, table[1:], strict=False):
        for e, f, what in ((e_s, f_s, "s"), (e_u, f_u, "U")):
            order = np.log2(e / f)
            assert 1.8 <= order <= 2.2, (name, what, dt, e, f, order, table)
    dt, e_s, e_u = table[-1]
    rounding = 64 * round(END / dt) * EPS
    assert e_s >= 1e3 * rounding and e_u >= 1e3 * rounding, (name, table)


def test_the_crossing_step_brackets_the_reference_crossing():
    """θ = s_ref(t_target) on cell_0's commitment curve, with t_target 23.6 ms off every grid by
    more than 5% of dt; cell_1's weak input never crosses."""
    t_target = 0.0236
    arm = COMMITMENT
    theta = float(
        commitment_reference([t_target], **{k: arm[k] for k in ("s0", "c0", "clear", "k_on")})[
            t_target
        ][0][0]
    )
    for dt in DTS:
        fraction = (t_target / dt) % 1.0
        assert 0.05 <= fraction <= 0.95, (dt, fraction)  # The pre-registered placement.
        rows, final = trajectory(world(dt, **arm, level=theta))
        crossing = np.asarray(final.state.regulatory_crossing_step)
        k = int(crossing[0])
        assert int(crossing[1]) == -1
        # δ: the row error near t* over |ds/dt| there (the commitment curve's slope at t*).
        c = arm["c0"][0] * np.exp(-arm["clear"][0] * t_target)
        slope = arm["k_on"] * u_of(c) * (1.0 - theta)
        near = commitment_reference(
            [k * dt], **{key: arm[key] for key in ("s0", "c0", "clear", "k_on")}
        )
        delta = abs(float(rows[k][0][0]) - float(near[k * dt][0][0])) / slope
        record("crossing", dt=dt, step=k, t_star=t_target, delta=delta, theta=theta)
        assert (k - 1) * dt < t_target + delta and t_target - delta <= k * dt, (
            dt,
            k,
            t_target,
            delta,
        )


def test_a_prior_condition_per_cell_equals_it_written_at_time_zero():
    """§7.2's amendment to A2: s0 = (0.7, 0.3) against s0 = (0.2, 0.3) with 0.7 written to cell_0 at
    0; the state from the first step on and U at every row are bitwise equal; the crossing (level
    0.5) is recorded at step 0 from s0 and at step 1 from the write."""
    dt = 0.005
    arm = dict(GENERAL, level=0.5)
    by_initial, initial_final = trajectory(world(dt, **dict(arm, s0=(0.7, 0.3))))
    by_write, write_final = trajectory(
        world(dt, **dict(arm, s0=(0.2, 0.3)), writes=[("s", "cell_0", 0.0, 0.7)])
    )
    assert by_initial.keys() == by_write.keys()
    for k in by_initial:
        a, b = by_initial[k], by_write[k]
        if k > 0:
            assert a[0].tobytes() == b[0].tobytes(), k
        assert a[1].tobytes() == b[1].tobytes(), k
    assert list(np.asarray(initial_final.state.regulatory_crossing_step))[0] == 0
    assert list(np.asarray(write_final.state.regulatory_crossing_step))[0] == 1
