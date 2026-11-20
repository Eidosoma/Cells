"""Compare a finite water–K/anion pair with an independent extent-based ODE."""

import json
from math import exp, log

import numpy as np
from potassium_anion_symport import closed_world
from scipy.integrate import solve_ivp

from cells.definitions.specs import ConfigError, parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators import k_anion_symport, osmotic_water
from cells.registry.models import get_model
from validation.core_seams.references import exact


def moving_world(concentrations, capacity, duration, steps, water_multiplier):
    raw = closed_world(concentrations, capacity, duration, steps).to_dict()
    raw["experiment"]["water_controls"][0]["schedule"][0]["availability"] = 1.0
    water, _ = raw["model"]["operators"]
    water["membranes"][0]["hydraulic_permeability_m_per_Pa_s"] *= water_multiplier
    return raw


def reference(raw):
    """Integrate only outward water and cycle extents plus their respective heats."""
    model = raw["model"]
    cell, outside = model["cells"][0], model["extracellular"][0]
    water, carrier = model["operators"]
    inside_compliance, outside_compliance = water["compartments"]
    route = carrier["routes"][0]
    g = (
        model["membranes"][0]["area_m2"]
        * 1e15
        * water["membranes"][0]["hydraulic_permeability_m_per_Pa_s"]
    )
    rt = float(exact.RT_J_per_mol(model["temperature_K"]))

    def pressure(node, compliance, volume, osmole_change):
        osmoles = sum(node["initial_amount_fmol"].values()) + compliance["impermeant_amount_fmol"]
        return (
            compliance["pressure_offset_Pa"]
            + compliance["bulk_modulus_Pa"] * (volume / compliance["reference_volume_pL"] - 1)
            - rt * (osmoles + osmole_change) / volume
        )

    ni, no = cell["initial_amount_fmol"], outside["initial_amount_fmol"]

    def rates(time, state):
        w, x = state[:2]
        vi, vo = cell["volume_pL"] - w, outside["volume_pL"] + w
        drive = pressure(cell, inside_compliance, vi, -2 * x) - pressure(
            outside, outside_compliance, vo, 2 * x
        )
        pin = (ni["K"] - x) * (ni["M"] - x) / vi**2
        pout = (no["K"] + x) * (no["M"] + x) / vo**2
        opening = exp((vi / route["set_volume_pL"] - 1) / route["steepness"])
        q = g * drive
        j = route["capacity_fmol_s_mM2"] * opening * (pin - pout)
        return q, j, q * drive / 1000, j * rt * log(pin / pout) / 1000

    end = raw["experiment"]["end_time"]
    # Two unrelated ODE integrators must resolve the error scale of the comparison.
    answers = []
    for method in ("DOP853", "Radau"):
        solution = solve_ivp(rates, (0, end), np.zeros(4), method=method, rtol=1e-11, atol=1e-15)
        if not solution.success:
            raise ArithmeticError(solution.message)
        answers.append(solution.y[:, -1])
    np.testing.assert_allclose(*answers, rtol=5e-10, atol=5e-15)
    return answers[0]


def compare(concentrations, capacity, duration, steps, multiplier=1.0):
    raw = moving_world(concentrations, capacity, duration, steps, multiplier)
    expected = reference(raw)
    record = dict(steps=steps, reference=expected.tolist())
    try:
        spec = parse_spec(raw)
        model = get_model(spec.model)
        state, layout = model.initial_values(spec)
        record["dt_times_water_bound"] = float(
            spec.execution.dt
            * osmotic_water.water_rate(state, layout.membrane_active.astype(float), layout, xp=np)
        )
        record["dt_times_symport_bound"] = float(
            spec.execution.dt * k_anion_symport.route_rate(spec, model)
        )
        result = run(spec)
    except (ConfigError, NumericalError) as error:
        return record | dict(completed=False, reason=str(error))
    final = result.final.state
    actual = [
        float(v[0])
        for v in (
            final.water_transferred_pL,
            final.symport_cycles_fmol,
            final.water_dissipated_energy_pJ,
            final.symport_dissipated_energy_pJ,
        )
    ]
    w, x = actual[:2]
    assert w != 0 and actual[2] > 0 and actual[3] >= 0
    allowance = 64 * exact.EPS
    np.testing.assert_allclose(
        [final.volume_increment_pL[0], final.extracellular_volume_increment_pL[0]],
        [-w, w],
        rtol=allowance,
        atol=0,
    )
    moved = [x if ion in ("K", "M") else 0 for ion in spec.model.species_ids]
    np.testing.assert_allclose(
        final.amount_increment[:, 0], -np.array(moved), atol=allowance, rtol=allowance
    )
    np.testing.assert_allclose(
        final.extracellular_amount_increment[:, 0], moved, atol=allowance, rtol=allowance
    )
    return record | dict(
        completed=True,
        engine=actual,
        max_global_water_error_pL=float(result.diagnostics["max_global_water_balance_error_pL"]),
        max_global_amount_error_fmol=float(result.diagnostics["max_global_balance_error_fmol"]),
        max_global_charge_error_C=float(result.diagnostics["max_global_charge_error_C"]),
        max_energy_balance_relative=float(result.diagnostics["max_energy_balance_relative"]),
    )


def main():
    ordinary = (40.0, 15.0, 10.0, 20.0)
    near_stall = (4.0, 4.0, 128.0, 0.125 - 2.0**-20)
    # The first pair uses faster water to resolve both extents and their heats.
    regular = [compare(ordinary, 0.01, 0.2, n, 8.0) for n in (16, 32)]
    stiff = [compare(near_stall, 2.5, 0.01, n) for n in (1, 32, 64)]
    pure_water = compare(ordinary, 0.0, 0.2, 32, 8.0)
    fast_water = compare(ordinary, 0.0, 0.2, 1, 12.0)
    report = dict(
        columns=["outward_water_pL", "outward_K_anion_fmol", "water_heat_pJ", "carrier_heat_pJ"],
        ordinary=regular,
        near_stall=stiff,
        water_only=pure_water,
        fast_water=fast_water,
    )
    print(json.dumps(report, indent=2, allow_nan=False), flush=True)
    for series, fine_rtol in ((regular, 2e-5), (stiff[-2:], 3e-3)):
        assert all(row["completed"] for row in series), series
        for row in series:
            assert np.all(np.sign(row["engine"][:2]) == np.sign(row["reference"][:2]))
        errors = np.abs([np.subtract(row["engine"], row["reference"]) for row in series])
        assert np.all((errors[0] / errors[1] > 3.3) & (errors[0] / errors[1] < 4.8)), errors
        np.testing.assert_allclose(
            series[-1]["engine"], series[-1]["reference"], rtol=fine_rtol, atol=0
        )
    coarse = stiff[0]
    assert pure_water["completed"]
    np.testing.assert_allclose(pure_water["engine"], pure_water["reference"], rtol=2e-5, atol=0)
    assert coarse["dt_times_water_bound"] < 0.05 and coarse["dt_times_symport_bound"] > 1
    assert (
        not coarse["completed"]
        and "Symport rate exceeds the explicit-rate bound" in coarse["reason"]
    )
    assert fast_water["dt_times_symport_bound"] == 0 and fast_water["dt_times_water_bound"] > 0.05
    assert (
        not fast_water["completed"]
        and "Water relaxation requires a smaller step" in fast_water["reason"]
    )


if __name__ == "__main__":
    main()
