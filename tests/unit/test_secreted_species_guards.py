"""Guards of record of the secreted-species operators (D150 version 1; design §7, §11.2-§11.5).

* **Energy, the species-only world** (the lead's ruling 4): with the ions quiescent, the energy
  bound is the species' own, so a booking error shows under IMEX. A misbooking of 1% of the booked
  secretion work is refused by the host energy ledger of the species-only world, and the same
  relative misbooking passes unseen in the mixed heredity chain, whose bound is the ions' (the
  shared bound is blind at µM-nM): the reason the species-only world and the NumPy dG tests are the
  guards of record.
* **The stiff front** (§7, §11.5 item 7): the radial world switched on from a 1e-15 mM trace under a
  1e-3 mM source, 2,000 steps of 1 ms through the checked step map (the runner's host energy ledger
  refuses this unresolved onset, a booking matter, §11.4): every step accepted and every amount
  positive, and the profile on the exact discrete solution where it is resolved. Amounts below
  about eps x their anchor stall positive (§1.3), which is not a failure.
* **The trace background** (§1.3): raising it a thousandfold moves the pre-formed radial profile by
  less than the trace's own change (a maximum principle), through the runner's host checks.
* **RK4** (the lead's ruling 6): the species-only radial world, zero ion face diffusivity, from a
  pre-formed profile at 0.1 ms through the runner, whose RK4 energy bound is the absolute 2e-8 pJ:
  the face heat and the clearance's work are booked to it. The profile follows the exact discrete
  solution to the splitting of turnover's half-steps around @3's RK4 step (second order in dt).
The radial world declares the exact spherical-shell conductances (validation/tissue/
secreted_species_radial). A few minutes of compiles: tier 3.
"""

import json
import os
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core import pump_composite_spec as cs
from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import parse_spec
from cells.models.registry import get_model
from validation.tissue import secreted_species_fixtures as fx
from validation.tissue import secreted_species_radial as radial

jax.config.update("jax_enable_x64", True)

GEOMETRY = radial.Geometry(10e-6, 5e-6, 24)  # R = 10 um, 24 shells of 5 um.
D, K, C0 = 4e-10, 1.0, 1e-3  # lambda = 20 um.
TRACE = 1e-15


def record(test, **values):
    """Append measured values to this run's output folder (the tier runner's CELLS_OUTPUT_ROOT)."""
    root = os.environ.get("CELLS_OUTPUT_ROOT")
    if root:
        path = Path(root) / "secreted_species_guards.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as out:
            out.write(json.dumps(dict(test=test, **values), default=float) + "\n")


def bounds(result):
    """[row] the energy ledger's bound without its rounding term: 2e-8 pJ + rtol x the accumulated
    heat and work (the energy-role table's fields)."""
    from cells.models.surface_pump import ENERGY_RTOL

    model = get_model(result.spec.model)
    flows = sum(
        np.sum(
            np.abs(np.asarray(getattr(result.history, k))).reshape(len(result.times), -1), axis=1
        )
        for k in model.ENERGY_FLOW_FIELDS
    )
    return 2e-8 + ENERGY_RTOL[result.spec.execution.solver] * flows


def misbooked(history, field, column, fraction):
    """The history with one booked work in error by `fraction` at every row (systematic)."""
    values = np.array(getattr(history, field), copy=True)
    values[:, column] *= 1.0 + fraction
    return history._replace(**{field: values})


def steps_of(result):
    return np.rint(np.asarray(result.times) / result.spec.execution.dt).astype(int)


def face_heat_control(result, label):
    """A systematic 1% error in the booked face heat (every face, every row), checked by the host
    ledgers: (refused, max over rows of the error over the energy bound without rounding)."""
    model = get_model(result.spec.model)
    heat = np.asarray(result.history.face_dissipated_energy_pJ)
    ratio = 0.01 * np.sum(np.abs(heat), axis=1) / bounds(result)
    wrong = result.history._replace(face_dissipated_energy_pJ=1.01 * heat)
    try:
        model.check_values(wrong, result.spec, steps=steps_of(result))
        refused = False
    except NumericalError as failure:
        refused = str(failure).endswith("energy")
    record("face_heat_control", world=label, refused=refused, max_ratio=np.max(ratio))
    return refused, float(np.max(ratio))


def face_free(operator, end=0.1):
    """A species-only world whose energy flow is one law's work alone: a cell secreting into its
    node (exchange), or a node clearing (turnover), with no face (so no face heat or bath work)."""
    raw = fx.face_free(end=end, observation_times=fx.grid_times(end, 1e-3, end / 4))
    if operator == "exchange":
        return fx.with_exchange(
            raw,
            [("secrete", "contact_0", "export", "first_order")],
            [("secrete", "cell_0", [(0.0, 0.1)])],
        )
    return fx.with_turnover(raw, [("clear", "ecs_0", "clearance")], [("clear", None, [(0.0, 0.5)])])


# The misbooked work of each law: (field, column in the face-free world, column in the mixed chain).
WORKS = dict(
    exchange=("exchange_work_pJ", 0, 0),  # The secretion route in both.
    turnover=("turnover_outside_work_pJ", 1, fx.CHAIN + 2),  # ecs_0; ecs_2 after six baths.
)


@pytest.fixture(scope="module")
def mixed_run():
    return run(parse_spec(fx.chain_operators(fx.heredity_chain(secreted=True, end=0.1))))


@pytest.mark.parametrize("operator", ["exchange", "turnover"])
def test_a_misbooked_work_fails_the_species_only_world_and_passes_unseen_in_the_mixed_world(
    operator, mixed_run
):
    """A systematic 1% error in one law's booked work, at every row. The IMEX bound is 2e-3 of the
    accumulated heat and work, so a booking error of a law shows once it exceeds that share of the
    species' own flows (the species-only world, here one law's flow), and is invisible where the
    ions' flows set the bound (the mixed world: the known blindness at µM-nM). Where face heat
    dominates the species' flows, the IMEX ledger is that much less sensitive to a law's work; the
    RK4 worlds' absolute bound (2e-8 pJ) and the NumPy dG test per law cover it."""
    field, own, chain = WORKS[operator]
    species_only = run(parse_spec(face_free(operator)))
    report = {}
    for label, result, column in (
        ("species_only", species_only, own),
        ("mixed", mixed_run, chain),
    ):
        model = get_model(result.spec.model)
        steps = steps_of(result)
        model.check_values(result.history, result.spec, steps=steps)  # As booked: passes.
        work = np.asarray(getattr(result.history, field))[:, column]
        assert work[-1] != 0
        ratio = 0.01 * np.abs(work) / bounds(result)
        record(
            "misbooked_work",
            operator=operator,
            world=label,
            misbooking_final_pJ=0.01 * abs(work[-1]),
            bound_final_pJ=bounds(result)[-1],
            misbooking_over_bound_final=ratio[-1],
            misbooking_over_bound_max=np.max(ratio),
        )
        try:
            model.check_values(
                misbooked(result.history, field, column, 0.01), result.spec, steps=steps
            )
            report[label] = "passed"
        except NumericalError as failure:
            report[label] = str(failure)
        report[label + "_ratio"] = (float(ratio[-1]), float(np.max(ratio)))
    assert report["species_only"].endswith("energy"), report
    assert report["species_only_ratio"][0] > 1, report  # Caught at the end, not only at an onset.
    assert report["mixed"] == "passed" and report["mixed_ratio"][1] < 1e-2, report


def jump_world(dt=1e-3, end=2.0):
    raw = radial.world(
        GEOMETRY, diffusivity=D, clearance=K, c0_mM=C0, trace_mM=TRACE, dt=dt, end=end
    )
    return parse_spec(raw)


def test_a_stiff_front_from_the_trace_stays_positive_through_the_step_map():
    spec = jump_world()
    model = get_model(spec.model)
    state, p = model.initial_values(spec)
    controls = cs.control_values(spec, [0.0])
    control = type(controls)(*(jnp.asarray(v[0]) for v in controls))
    step = jax.jit(
        lambda x: model.checked_step(x, jnp.asarray(spec.execution.dt), control, p, p.active)
    )
    s = list(spec.model.species_ids).index(fx.SPECIES)
    ids = [o.id for o in spec.model.extracellular]
    cols = np.array([ids.index(f"shell_{i}") for i in range(GEOMETRY.shells)])
    anchor = np.asarray(p.extracellular_amount_reference)[s, cols]
    sampled = {250: 0.25, 500: 0.5, 1000: 1.0, 2000: 2.0}
    profiles, refused, positive = {}, 0, True
    for k in range(1, 2001):
        state, ok = step(state)
        refused += int(not bool(ok))
        if k in sampled or k % 50 == 0:
            amounts = anchor + np.asarray(state.extracellular_amount_increment)[s, cols]
            positive &= bool(np.all(amounts > 0))
            if k in sampled:
                profiles[sampled[k]] = amounts / GEOMETRY.volumes_pL
    record(
        "stiff_front",
        refused=refused,
        positive=positive,
        max_dt_K_ii=radial.max_dt_k(GEOMETRY, diffusivity=D, clearance=K, dt=spec.execution.dt),
    )
    assert refused == 0 and positive
    m, g = radial.operator(GEOMETRY, diffusivity=D, clearance=K, c0_mM=C0, outer_mM=TRACE)
    times = sorted(profiles)
    exact = radial.solution(m, g, np.full(GEOMETRY.shells, TRACE), times)
    resolved = exact > 1e3 * np.finfo(float).eps * TRACE  # Above the anchored resolution.
    for j, t in enumerate(times):
        error = np.max(np.abs(profiles[t] - exact[j])[resolved[j]])
        record("stiff_front", time=t, error_of_c0=error / C0)
        assert error <= 1e-5 * C0, (t, error)


def pre_formed(trace, dt=1e-3, end=0.5, solver=fx.IMEX, every=0.1):
    profile = radial.pre_formed(GEOMETRY, diffusivity=D, clearance=K, c0_mM=C0, trace_mM=trace)
    raw = radial.world(
        GEOMETRY,
        diffusivity=D,
        clearance=K,
        c0_mM=C0,
        trace_mM=trace,
        profile_mM=profile,
        dt=dt,
        end=end,
        solver=solver,
        observation_every=every,
    )
    return parse_spec(raw), profile


def test_a_thousandfold_trace_moves_the_profile_by_less_than_itself():
    profiles = {}
    for trace in (1e-15, 1e-12):
        spec, _ = pre_formed(trace)
        result = run(spec)  # Every host check, the energy ledger included.
        profiles[trace] = radial.shell_concentrations(spec, result.observations, GEOMETRY)
    change = np.max(np.abs(profiles[1e-12] - profiles[1e-15]))
    record("trace", change_mM=change, change_over_trace_change=change / (1e-12 - 1e-15))
    assert 0 < change <= 1e-12 - 1e-15


def test_the_rk4_radial_world_books_face_heat_and_clearance_to_the_absolute_bound():
    spec, profile = pre_formed(TRACE, dt=1e-4, end=0.2, solver="rk4", every=0.05)
    result = run(spec)  # RK4's host energy bound: 2e-8 pJ, no solver tolerance.
    assert result.diagnostics["max_energy_balance_error_pJ"] < 2e-8
    concentrations = radial.shell_concentrations(spec, result.observations, GEOMETRY)
    times = np.asarray(result.observations.times)
    m, g = radial.operator(GEOMETRY, diffusivity=D, clearance=K, c0_mM=C0, outer_mM=TRACE)
    exact = radial.solution(m, g, profile, times)
    error = np.max(np.abs(concentrations - exact))
    record(
        "rk4_radial",
        energy_error_pJ=result.diagnostics["max_energy_balance_error_pJ"],
        error_of_c0=error / C0,
    )
    assert error <= 1e-6 * C0  # Turnover's splitting around the RK4 step, O(dt^2).
    # The face heat's negative control: RK4's absolute bound sees a 1% error in it.
    refused, ratio = face_heat_control(result, "rk4_radial")
    assert refused and ratio > 1, ratio


def test_the_imex_radial_world_closes_every_host_check_and_is_second_order_in_dt():
    """ARS(2,2,2) transport with turnover's exact half-steps around it (Strang): the error against
    the exact discrete solution is the splitting's and the scheme's, both second order in dt (at
    1 ms, dt K_ii = 0.049, it is about 1e-5 of c0). The splitting of the uniform clearance from the
    held boundaries' sources sets its steady part, dt^2 k (g - k c_ss) / 4 at the first shell under
    ARS (/12 under exact transport), with g the source face's kappa c0 / V0 (the evidence folder's
    splitting_bias.json)."""
    errors = {}
    for dt in (1e-3, 5e-4):
        spec, profile = pre_formed(TRACE, dt=dt, end=0.5)
        result = run(spec)  # Every host check.
        assert result.diagnostics["max_energy_balance_relative"] < 2e-3
        concentrations = radial.shell_concentrations(spec, result.observations, GEOMETRY)
        m, g = radial.operator(GEOMETRY, diffusivity=D, clearance=K, c0_mM=C0, outer_mM=TRACE)
        exact = radial.solution(m, g, profile, np.asarray(result.observations.times))
        errors[dt] = float(np.max(np.abs(concentrations - exact)))
        if dt == 1e-3:  # The face heat's negative control under the IMEX bound.
            refused, ratio = face_heat_control(result, "imex_radial")
            assert refused == (ratio > 1), (refused, ratio)
        record(
            "imex_radial",
            dt=dt,
            energy_relative=result.diagnostics["max_energy_balance_relative"],
            error_of_c0=errors[dt] / C0,
        )
    ratio = errors[1e-3] / errors[5e-4]
    record("imex_radial_order", ratio=ratio)
    assert errors[1e-3] <= 3e-5 * C0 and 3.5 < ratio < 4.5
