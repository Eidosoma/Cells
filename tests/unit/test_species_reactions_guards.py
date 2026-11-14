"""Guards in the engine branch for local_species_reactions@1 (D152 v1, milestone 2; design §3.4,
§4.4, §6.5 and §10.4's C2).

* **Energy, the face-free species-only world** (§3.4, guard 1). The network is the world's only
  energy flow, so the composite's energy residual is judged against rounding itself, 2.5 eps x
  steps x the energy magnitudes (surface_pump.LEDGER_STEP_ROUNDING), at every accepted row, not
  against 2e-3 of the flows. Every booking path is forced: driven-only nodes; a passive-only
  relaxation (total heat G(start) - G(end), the equilibrium its potentials set); the share (probe
  2d's passive switch-on from a 1e-12, 1e-9 and 1e-6 mM trace at a mixed node, no route
  reversing); the quadrature (probe 2e's crossing, every heat non-negative); the per-step class
  switch (the catalytic step off mid-run and back on: while off W = 0 and H = -dG); the reversal
  onset at the first step and at a mid-run switch-on (the known limit, documented: the same first
  active half-step in both, on the quadrature). Every heat element is non-negative and
  non-decreasing (the runner's dissipation check).
* **Negative controls** (§3.4, guard 3), edits of saved histories: work scaled by 1 + 1e-6, a
  dropped standard term and a heat of the wrong sign each fail the face-free world's residual at
  the first row they touch; in C2's mixed heredity chain the shared bound does not see the scaled
  work, and the wrong-sign heat is caught by the dissipation check.
* **C2** (§10.4): the shared bound over the operator's booking in the mixed chain, the reacting pair
  at µM and nM (recorded for the docstring statement), and whether the bound sees a dropped
  standard term there.
* **The stiff front** (§4.4): a species at 1e-15 mM under a fast sink at dt L = 0.99 and a product
  switched on from 1e-15 mM, through the compiled checked step: every step accepted and positive.
Waiting for the independent references (validation/reactions/REFERENCES_USAGE.md, not yet on main):
the share's and the quadrature's accuracy against the dissipation integral, the background guard on
H and W, and the reversal onset's size against the true heat. Measured values are appended to
species_reactions_guards.jsonl in the tier runner's CELLS_OUTPUT_ROOT. A few minutes of compiles.
"""

import json
import os
from decimal import Decimal, getcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.operators import species_reactions as sr
from cells.models.registry import get_model
from cells.models.surface_pump import ENERGY_RTOL, LEDGER_STEP_ROUNDING
from validation.tissue import species_reactions_fixtures as rfx

jax.config.update("jax_enable_x64", True)
getcontext().prec = 50
EPS = np.finfo(float).eps
R_SI = Decimal("6.02214076e23") * Decimal("1.380649e-23")
RT_PJ = Decimal("1e-3") * R_SI * Decimal("310")


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "species_reactions_guards.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


def steps_of(result):
    return np.rint(np.asarray(result.times) / result.spec.execution.dt).astype(int)


def rows_of(history):
    return [type(history)(*(np.asarray(v)[i] for v in history)) for i in range(len(history[0]))]


def residual_ratios(result, history=None):
    """[row] the energy residual over its rounding allowance, 2.5 eps x steps x the energy
    magnitudes (the guard of record in the face-free world; 0 where both are 0)."""
    model = get_model(result.spec.model)
    _, p = model.initial_values(result.spec)
    out = []
    for row, steps in zip(rows_of(history or result.history), steps_of(result), strict=True):
        residual = abs(float(model.balances(row, p)["energy"]))
        allowance = (
            LEDGER_STEP_ROUNDING * EPS * max(int(steps), 1) * float(model.magnitudes(row, p)[6])
        )
        out.append(0.0 if residual == 0.0 else residual / allowance if allowance > 0 else np.inf)
    return np.asarray(out)


def closes_at_rounding(result, label):
    ratios = residual_ratios(result)
    record("face_free_residual", world=label, max_ratio=float(np.max(ratios)), rows=len(ratios))
    assert np.all(ratios <= 1.0), (label, float(np.max(ratios)))
    return ratios


def amounts(result, row, names, node="cell_0"):
    spec = result.spec
    model = get_model(spec.model)
    _, p = model.initial_values(spec)
    cells = [c.id for c in spec.model.cells]
    i = cells.index(node)
    out = {}
    for name in names:
        s = list(spec.model.species_ids).index(name)
        out[name] = float(
            p.amount_reference[s, i] + np.asarray(result.history.amount_increment)[row][s, i]
        )
    return out


def free_energy(result, row, names, node="cell_0"):
    """Appendix A's G at the cell (1 pL), Decimal, with the network's mu°' (c0 = 1 mM)."""
    declaration = next(d for d in result.spec.model.operators if d.law == sr.LAW_ID)
    c0 = Decimal(declaration.standard_concentration_mM)
    mu = {s.identity.id: RT_PJ * (Decimal(s.standard_mu_RT) - c0.ln()) for s in declaration.species}
    total = Decimal(0)
    for name, value in amounts(result, row, names, node).items():
        n = Decimal(value)
        total += RT_PJ * n * (n.ln() - 1) + mu[name] * n  # V = 1 pL.
    return total


def first_half_step(result, row, multiplier, p=None):
    """The first half-step of the step from `row` (face-free: @3 moves no network row)."""
    if p is None:
        _, p = get_model(result.spec.model).initial_values(result.spec)
    state = type(result.history)(*(np.asarray(v)[row] for v in result.history))
    h = 0.5 * result.spec.execution.dt
    return sr.half_step_terms(state, np.asarray(multiplier, dtype=float), h, p, xp=np)


# ------------------------------------------------------------------ guard 1: every booking path


def test_driven_only_nodes_book_work_alone_and_close_at_rounding():
    result = run(parse_spec(rfx.driven_only(end=0.05, dt=1e-3)))
    closes_at_rounding(result, "driven_only")
    h = result.history
    assert not np.any(np.asarray(h.reaction_dissipated_energy_pJ))
    assert not np.any(np.asarray(h.reaction_outside_dissipated_energy_pJ))
    assert (
        np.asarray(h.reaction_work_pJ)[-1][0] != 0
        and np.asarray(h.reaction_outside_work_pJ)[-1][1] != 0
    )


def test_a_passive_relaxation_books_its_free_energy_drop_as_heat():
    result = run(parse_spec(rfx.passive_relaxation(end=40.0, dt=0.1)))
    closes_at_rounding(result, "passive_relaxation")
    h = result.history
    assert not np.any(np.asarray(h.reaction_work_pJ))
    start, end = free_energy(result, 0, ("S", "P")), free_energy(result, -1, ("S", "P"))
    heat = Decimal(float(np.asarray(h.reaction_dissipated_energy_pJ)[-1][0]))
    assert abs(heat - (start - end)) <= Decimal("1e-12") * (start - end)
    final = amounts(result, -1, ("S", "P"))
    assert abs(final["P"] / final["S"] / 10.0 - 1.0) < 1e-12
    record("passive_relaxation", heat_pJ=float(heat), drop_pJ=float(start - end))


@pytest.mark.parametrize("trace", [1e-12, 1e-9, 1e-6])
def test_the_share_books_a_passive_switch_on_from_the_trace(trace):
    """Probe 2d's recipe at a mixed node: the binding switches on from the trace driven by its own
    affinity and never reverses, so every first half-step takes the share."""
    result = run(parse_spec(rfx.enzyme_recipe(trace, end=1.0, dt=0.025)))
    closes_at_rounding(result, f"share_{trace:g}")
    _, p = get_model(result.spec.model).initial_values(result.spec)
    branches = [bool(first_half_step(result, k, [1.0, 1.0], p).nonreversing[0]) for k in range(40)]
    assert all(branches), branches
    h = result.history
    heat, work = (
        np.asarray(h.reaction_dissipated_energy_pJ)[:, 0],
        np.asarray(h.reaction_work_pJ)[:, 0],
    )
    assert heat[1] > 0 and np.all(np.diff(heat) >= 0)
    record(
        "share_onset",
        trace=trace,
        first_heat_pJ=heat[1],
        first_work_pJ=work[1],
        heat_1s_pJ=heat[-1],
        work_1s_pJ=work[-1],
    )


@pytest.mark.parametrize(
    ("sink", "dt", "offset"), [(1.0, 0.1, 0.01), (1.0, 0.1, 0.04), (10.0, 0.05, 0.01)]
)
def test_the_quadrature_books_probe_2e_crossing_non_negatively(sink, dt, offset):
    """The sink carries S across the passive equilibrium within the first half-step: the route
    reverses there and takes the quadrature, which is positive; the run's every heat is >= 0."""
    result = run(parse_spec(rfx.crossing(end=5 * dt, dt=dt, sink=sink, offset=offset)))
    closes_at_rounding(result, f"crossing_{sink:g}_{offset:g}")
    first = first_half_step(result, 0, [1.0, 1.0])
    assert not first.nonreversing[0] and first.heat[0] > 0
    heat = np.asarray(result.history.reaction_dissipated_energy_pJ)[:, 0]
    assert np.all(np.diff(heat) >= 0) and heat[-1] > 0
    record("crossing", sink=sink, dt=dt, offset=offset, first_heat_pJ=float(first.heat[0]))


def test_the_class_follows_the_multipliers_mid_run():
    """The catalytic step off from 20 to 30 ms and back on (the resolved recipe): while off the
    cell is passive-only, W unchanged and H = -dG step by step; mixed again after."""
    raw = rfx.enzyme_recipe(
        None,
        resolved=True,
        catalysis=[(0.0, 1.0), (0.02, 0.0), (0.03, 1.0)],
        end=0.05,
        dt=1e-3,
        observation_times=[0.0, 0.02, 0.03, 0.05],
    )
    result = run(parse_spec(raw))
    closes_at_rounding(result, "class_switch")
    h = result.history
    work, heat = (
        np.asarray(h.reaction_work_pJ)[:, 0],
        np.asarray(h.reaction_dissipated_energy_pJ)[:, 0],
    )
    names = ("S", "E", "C", "P")
    for k in range(21, 31):  # The steps that start at 20 ... 29 ms: catalysis off.
        assert work[k] == work[k - 1], k
        drop = free_energy(result, k - 1, names) - free_energy(result, k, names)
        booked = Decimal(float(heat[k] - heat[k - 1]))
        # The stored states resolve G to about 8 ulp(n) |mu| per species: 1e-16 pJ here.
        assert abs(booked - drop) <= Decimal("1e-9") * abs(drop) + Decimal("1e-16"), k
        assert drop > Decimal("1e-12"), k  # A real step's heat, far above that resolution.
    assert work[20] != work[19] and work[31] != work[30]  # Mixed before and after.


def test_the_reversal_onset_is_the_same_at_the_first_step_and_at_a_mid_run_switch_on():
    """The known limit (§3.3, option (a)): the half-step depends only on the state and the
    multipliers, so a switch-on mid-run from the trace books its first half-step exactly as a start
    does (the same function on bitwise the same network rows), both on the quadrature; the two
    compiled runs (different horizons, so different programs, §4.5) agree to rounding. Its size
    against the true heat awaits the references."""
    start = run(parse_spec(rfx.reversal_onset(1e-12, end=0.1, dt=0.025)))
    later = run(parse_spec(rfx.reversal_onset(1e-12, end=0.15, dt=0.025, switch_on=0.05)))
    closes_at_rounding(start, "reversal_onset_start")
    closes_at_rounding(later, "reversal_onset_mid_run")
    _, p = get_model(start.spec.model).initial_values(start.spec)
    k = 2  # The step starting at 50 ms.
    rows = list(p.reaction_rows)
    for name in ("amount_increment", "extracellular_amount_increment"):
        a, b = np.asarray(getattr(start.history, name)), np.asarray(getattr(later.history, name))
        assert a[0][rows].tobytes() == b[k][rows].tobytes(), name  # Held until the switch-on.
    first, again = (
        first_half_step(start, 0, [1.0, 1.0], p),
        first_half_step(later, k, [1.0, 1.0], p),
    )
    assert not first.nonreversing[0] and not again.nonreversing[0]
    for name in ("dn", "extent", "free_energy", "heat", "work", "route_heat"):
        assert (
            np.asarray(getattr(first, name)).tobytes() == np.asarray(getattr(again, name)).tobytes()
        )
    for name in ("reaction_dissipated_energy_pJ", "reaction_work_pJ"):
        a, b = np.asarray(getattr(start.history, name)), np.asarray(getattr(later.history, name))
        assert np.allclose(a[1] - a[0], b[k + 1] - b[k], rtol=1e-12, atol=0.0), name
    heat = np.asarray(start.history.reaction_dissipated_energy_pJ)[:, 0]
    record(
        "reversal_onset",
        trace=1e-12,
        first_half_step_heat_pJ=float(first.heat[0]),
        first_step_heat_pJ=heat[1],
        heat_end_pJ=heat[-1],
    )


# ------------------------------------------------------------------ guard 3: negative controls


@pytest.fixture(scope="module")
def face_free_run():
    return run(parse_spec(rfx.enzyme_network(faces=False, end=0.05, observation_times=[0.0, 0.05])))


def edits(history):
    return dict(
        scaled_work=history._replace(
            reaction_work_pJ=np.asarray(history.reaction_work_pJ) * (1 + 1e-6),
            reaction_outside_work_pJ=np.asarray(history.reaction_outside_work_pJ) * (1 + 1e-6),
        ),
        dropped_standard=history._replace(
            reaction_standard_energy_pJ=np.zeros_like(
                np.asarray(history.reaction_standard_energy_pJ)
            ),
            reaction_outside_standard_energy_pJ=np.zeros_like(
                np.asarray(history.reaction_outside_standard_energy_pJ)
            ),
        ),
        wrong_sign_heat=history._replace(
            reaction_dissipated_energy_pJ=-np.asarray(history.reaction_dissipated_energy_pJ),
            reaction_outside_dissipated_energy_pJ=-np.asarray(
                history.reaction_outside_dissipated_energy_pJ
            ),
        ),
    )


def touched(history, name):
    field = dict(
        scaled_work=("reaction_work_pJ", "reaction_outside_work_pJ"),
        dropped_standard=("reaction_standard_energy_pJ", "reaction_outside_standard_energy_pJ"),
        wrong_sign_heat=("reaction_dissipated_energy_pJ", "reaction_outside_dissipated_energy_pJ"),
    )[name]
    nonzero = np.zeros(len(history[0]), dtype=bool)
    for f in field:
        values = np.asarray(getattr(history, f))
        nonzero |= np.any(values.reshape(len(values), -1) != 0, axis=1)
    return int(np.flatnonzero(nonzero)[0])


def test_each_misbooking_fails_the_face_free_world_at_the_first_row_it_touches(face_free_run):
    result = face_free_run
    assert np.all(residual_ratios(result) <= 1.0)
    for name, wrong in edits(result.history).items():
        ratios = residual_ratios(result, wrong)
        first = touched(result.history, name)
        assert ratios[first] > 1.0 and np.all(ratios[:first] <= 1.0), (
            name,
            first,
            ratios[: first + 2],
        )
        record(
            "negative_control_face_free", control=name, first_row=first, ratio=float(ratios[first])
        )
    with pytest.raises(NumericalError):  # The wrong-sign heat is also refused by dissipation.
        get_model(result.spec.model).check_values(
            edits(result.history)["wrong_sign_heat"], result.spec, steps=steps_of(result)
        )


# ------------------------------------------------------------------ C2: the mixed chain


@pytest.fixture(scope="module", params=[1e-3, 1e-6], ids=["uM", "nM"])
def mixed_run(request):
    return request.param, run(parse_spec(rfx.mixed_chain(request.param, end=0.1)))


def bound_and_booking(result, history=None):
    """At the last row: the shared energy bound without rounding (2e-8 pJ + rtol x every heat
    and work of the composition) and the operator's booking |sum W - sum H| (its dG, pJ)."""
    history = history or result.history
    model = get_model(result.spec.model)
    flows = sum(
        np.sum(np.abs(np.asarray(getattr(history, k))[-1])) for k in model.ENERGY_FLOW_FIELDS
    )
    bound = 2e-8 + ENERGY_RTOL[result.spec.execution.solver] * flows
    work = sum(
        np.sum(np.asarray(getattr(history, k))[-1])
        for k in ("reaction_work_pJ", "reaction_outside_work_pJ")
    )
    heat = sum(
        np.sum(np.asarray(getattr(history, k))[-1])
        for k in ("reaction_dissipated_energy_pJ", "reaction_outside_dissipated_energy_pJ")
    )
    return bound, abs(work - heat), abs(work) + abs(heat)


def test_c2_the_shared_bound_is_blind_to_these_bookings_in_the_mixed_chain(mixed_run):
    level, result = mixed_run
    bound, booking, gross = bound_and_booking(result)
    assert booking > 0
    model = get_model(result.spec.model)
    steps = steps_of(result)
    unseen = {}
    for name, wrong in edits(result.history).items():
        try:
            model.check_values(wrong, result.spec, steps=steps)
            unseen[name] = True
        except NumericalError as failure:
            unseen[name] = False
            reason = str(failure)
        if name == "wrong_sign_heat":
            assert not unseen[name] and ("dissipation" in reason or "energy" in reason), name
    assert unseen["scaled_work"], unseen
    standard = abs(
        sum(
            np.sum(np.asarray(getattr(result.history, k))[-1])
            for k in ("reaction_standard_energy_pJ", "reaction_outside_standard_energy_pJ")
        )
    )
    record(
        "c2_mixed_chain",
        level_mM=level,
        bound_pJ=bound,
        booking_dG_pJ=booking,
        gross_W_plus_H_pJ=gross,
        bound_over_booking=bound / booking,
        bound_over_gross=bound / gross,
        standard_term_pJ=standard,
        bound_over_standard=bound / standard if standard else None,
        unseen=unseen,
    )


# ------------------------------------------------------------------ the stiff front


def test_the_stiff_front_stays_positive_through_the_compiled_step():
    """§4.4: Q at 1e-15 mM under a fast sink and P switched on from 1e-15 mM by a fast conversion
    of S, at dt L = 0.99 (h L = 0.495), 200 steps through the compiled checked step."""
    cell = {"cells": ["cell_0"]}
    raw = rfx.face_free_network(
        ("P", "Q"),
        [rfx.species(n, moieties={"X": 1}) for n in ("S", "P", "Q")],
        [
            rfx.mass_action("sink", cell, {"Q": 1}, {}, 9.9),
            rfx.mass_action("convert", cell, {"S": 1}, {"P": 1}, 9.9),
        ],
        rfx.always(["sink", "convert"]),
        profile=dict(S=dict(cell_0=1e-3), P=dict(cell_0=1e-15), Q=dict(cell_0=1e-15)),
        end=20.0,
        dt=0.1,
    )
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = cs.control_values(spec, [0.0])
    control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
    step = jax.jit(lambda x, c: model.checked_step(x, jnp.asarray(0.1), c, p, p.active))
    rows = [list(spec.model.species_ids).index(n) for n in ("S", "P", "Q")]
    smallest = np.inf
    for k in range(200):
        state, ok = step(state, control)
        assert bool(ok), k
        n = np.asarray(p.amount_reference)[rows, 0] + np.asarray(state.amount_increment)[rows, 0]
        assert np.all(np.isfinite(n)) and np.all(n > 0), (k, n)
        smallest = min(smallest, float(n[2]))
    final = np.asarray(p.amount_reference)[rows, 0] + np.asarray(state.amount_increment)[rows, 0]
    assert final[1] > 0.99e-3  # P took up S.
    record("stiff_front", smallest_Q_fmol=smallest, final_fmol=final.tolist())
