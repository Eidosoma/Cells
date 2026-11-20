"""Compare the K–anion operator with the exact solution for two closed, equal volumes."""

import argparse
import json
from itertools import product

import jax
import numpy as np

from cells.definitions.pump_composite_spec import frozen_definition
from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.routes import k_anion_symport as law
from cells.operators import k_anion_symport as operator
from cells.registry.models import get_model
from validation.core_seams.references import design, exact
from validation.tissue import pump_water_fixtures as fixture


def rate_panel():
    evaluate = jax.jit(law.rates)
    pairs = [(40, 15, 10, 20), (10, 20, 40, 15), (4, 4, 8, 2)]
    cases = 0
    for concentrations, volume, opening in product(pairs, (0.8, 1.0, 1.2), (0.0, 0.25, 1.0)):
        params = law.Parameters(0.01, 1.0, 0.12)
        actual = evaluate(*map(float, concentrations), volume, 310.0, params, opening)
        with exact.context():
            ki, ai, ko, ao = map(exact.dec, concentrations)
            factor = ((exact.dec(volume) - 1) / exact.dec(params.steepness)).exp()
            cycles = (
                exact.dec(params.capacity_fmol_s_mM2)
                * exact.dec(opening)
                * factor
                * (ki * ai - ko * ao)
            )
            affinity = exact.RT_J_per_mol(310) * ((ki * ai) / (ko * ao)).ln()
            expect = [float(v) for v in (cycles, affinity, factor, cycles * affinity / 1000)]
        np.testing.assert_allclose(actual, expect, atol=0, rtol=design.BAND_EPS * exact.EPS)
        cases += 1
    return cases


def product_ratio(outside_exponent):
    # Both products are normal doubles in these cases. Only their quotient can overflow.
    outside = 2.0**outside_exponent
    params = law.Parameters(0.01, 1.0, 1.0)
    args = (16.0, 16.0, outside, outside, 1.0)
    actual = jax.jit(law.rates)(*args, 310.0, params, 1.0)
    with exact.context():
        affinity = exact.RT_J_per_mol(310) * 2 * (exact.dec(16).ln() - exact.dec(outside).ln())
        cycles = exact.dec(0.01) * (256 - exact.dec(outside) ** 2)
        expect = np.array([float(affinity), float(cycles * affinity / 1000)])
    observed = np.array([actual.affinity_J_mol, actual.dissipation_pJ_s], dtype=float)
    return dict(
        outside_exponent=outside_exponent,
        domain_valid=bool(law.domain_valid(*args, params, 1.0, xp=np)),
        reference_affinity_J_mol=expect[0],
        reference_heat_pJ_s=expect[1],
        finite_affinity_and_heat=bool(np.isfinite(observed).all()),
        passed=bool(np.allclose(observed, expect, rtol=design.BAND_EPS * exact.EPS, atol=0)),
    )


def closed_world(concentrations, capacity, duration, steps):
    dt = duration / steps
    raw = fixture.heredity_cell("D", dt=dt, end_time=duration, observation_times=[0.0, duration])
    model, experiment = raw["model"], raw["experiment"]
    cell, outside = model["cells"][0], model["extracellular"][0]
    outside["reservoir"] = False
    model["closure"]["gauge_reference"] = outside["id"]
    ki, ai, ko, ao = concentrations
    for node, k, a in ((cell, ki, ai), (outside, ko, ao)):
        node.update(
            volume_pL=1.0,
            initial_amount_fmol=dict(Na=30.0, K=k, M=a, P=30.0),
            fixed_charge_equivalent_fmol=a - k,
            initial_charge_C=0.0,
        )
    for key in ("membrane_controls", "channel_controls", "pump_controls"):
        for control in experiment[key]:
            control["schedule"][0]["availability"] = 0.0
    raw = fixture.with_symport(fixture.with_water(raw, availability=0.0), steepness=10.0)
    raw["model"]["symport"]["routes"][0]["capacity_fmol_s_mM2"] = capacity
    return parse_spec(frozen_definition(raw))


def compare_world(concentrations, capacity, duration, steps):
    # V = 1 pL, so an extent of one fmol changes each concentration by one mM.
    with exact.context():
        ki, ai, ko, ao = map(exact.dec, concentrations)
        total = ki + ai + ko + ao
        equilibrium = (ki * ai - ko * ao) / total
        z = exact.dec(duration / steps) * exact.dec(capacity) * total
        exact_extent = float(equilibrium * (1 - (-z * steps).exp()))
        tableau_extent = float(equilibrium * (1 - (1 - z + z**2 / 2) ** steps))
    result = dict(
        steps=steps,
        concentrations_mM=concentrations,
        capacity_fmol_s_mM2=capacity,
        duration_s=duration,
        dt_times_closed_rate=float(z),
        exact_outward_fmol=exact_extent,
        ars222_outward_fmol=tableau_extent,
    )
    try:
        spec = closed_world(concentrations, capacity, duration, steps)
        result["dt_times_operator_bound"] = float(
            spec.execution.dt * operator.route_rate(spec, get_model(spec.model))
        )
        rollout = run(spec)
    except (ConfigError, NumericalError) as error:
        refused_at_step_bound = isinstance(error, ConfigError) and "explicit-rate bound" in str(
            error
        )
        return result | dict(completed=False, reason=str(error), passed=refused_at_step_bound)
    state = rollout.final.state
    actual = float(state.symport_cycles_fmol[0])
    moved = np.array([actual if s in ("K", "M") else 0.0 for s in spec.model.species_ids])
    atol = design.BAND_EPS * exact.EPS * max(concentrations)
    np.testing.assert_allclose(state.amount_increment[:, 0], -moved, rtol=0, atol=atol)
    np.testing.assert_allclose(state.extracellular_amount_increment[:, 0], moved, rtol=0, atol=atol)
    assert np.all(state.volume_increment_pL == 0) and np.all(
        state.extracellular_volume_increment_pL == 0
    )
    assert state.symport_dissipated_energy_pJ[0] >= 0
    return result | dict(
        completed=True,
        booked_outward_fmol=actual,
        charge_error_C=float(rollout.diagnostics["max_global_charge_error_C"]),
        material_error_fmol=float(rollout.diagnostics["max_global_balance_error_fmol"]),
        follows_ars222=abs(actual - tableau_extent) <= atol,
        passed=bool(np.sign(actual) == np.sign(exact_extent)),
    )


def main(controls_only):
    ordinary = compare_world((40.0, 15.0, 10.0, 20.0), 0.01, 0.04, 20)
    near_stall = (4.0, 4.0, 128.0, 0.125 - 2.0**-20)
    steps = [32, 64] if controls_only else [1, 32, 64]
    worlds = [compare_world(near_stall, 2.5, 0.01, n) for n in steps]
    controls = [ordinary, *worlds[-2:]]
    for row in controls:
        assert row["completed"] and row["passed"] and row["follows_ars222"], row
    errors = [abs(row["booked_outward_fmol"] - row["exact_outward_fmol"]) for row in worlds[-2:]]
    assert 3.5 < errors[0] / errors[1] < 4.5  # Second-order convergence at fixed duration.
    component = [product_ratio(n) for n in ([-500] if controls_only else [-500, -510])]
    report = dict(
        component_cases=rate_panel(),
        ordinary=ordinary,
        near_stall=worlds,
        refinement_error_ratio=errors[0] / errors[1],
        product_ratio=component,
    )
    print(json.dumps(report, indent=2, allow_nan=False))
    safe_steps = all(row["passed"] for row in worlds)
    return safe_steps and all(row["passed"] for row in component)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls-only", action="store_true")
    raise SystemExit(0 if main(parser.parse_args().controls_only) else 1)
