"""Absolute bath recipes, dose and reservoir work, and measured potassium reversal shifts."""

import argparse
import json
import math
from fractions import Fraction
from pathlib import Path

import jax
import numpy as np
from scipy.optimize import brentq

from cells.definitions.pump_composite_spec import control_values
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.electrochemistry import CHARGE_PER_FMOL, F, R
from cells.laws.junctions.selective import selective_flux
from validation.fr10.references import faces, records
from validation.tissue import bath_schedule_fixtures as bath
from validation.tissue import secreted_species_fixtures as pools
from validation.tissue.bath_schedule_qualification import records_of


def pulse(solver, dt):
    c0 = 2.0**-10
    interval = 1 / 64
    levels = np.array([1.0, 2.0, 0.5, 1.5, 1.0]) * c0
    switches = np.arange(1, len(levels)) * interval
    end = len(levels) * interval
    times = sorted(map(float, {0.0, end, *switches, *(switches + dt), *(switches - dt)}))
    area, length = bath.FACE_5
    raw = bath.dosed_world(
        c0=c0,
        dt=dt,
        end=end,
        solver=solver,
        face=(area, length),
        observation_times=times,
        profile=dict(bath=c0, ecs_0=0.75 * c0, cell_0=c0),
    )
    schedule = [
        (float(t), ["bath"], {"cargo": float(c - c0)})
        for t, c in zip(switches, levels[1:], strict=True)
    ]
    spec = parse_spec(bath.with_bath_schedule(raw, ["bath"], bath.CARGO, schedule))
    series = records_of(run(spec))["series"]
    s = pools.SPECIES
    # Both independent references take absolute concentrations as input.
    world = dict(
        valence={s: 0},
        temperature_K=spec.model.temperature_K,
        record_times_s=times,
        finite_nodes={"ecs_0": {"volume_pL": 1, f"{s}_mM": 0.75 * c0}},
        faces=[
            {
                "id": "face_0",
                "between": ["ecs_0", "bath"],
                "area_m2": area,
                "length_m": length,
                f"{s}_diffusivity_m2_per_s": pools.D_S,
            }
        ],
        bath=dict(
            volume_pL=1,
            declared_mM={s: c0},
            events=[
                dict(time_s=t, concentration_mM={s: c})
                for t, c in zip(switches, levels[1:], strict=True)
            ],
        ),
    )
    stamps = np.asarray(times)
    supply = np.asarray(series[f"supplied_{s}_fmol"])
    # On the saved boundary the previous step has finished. The event is applied
    # before the next interval's first transport evaluation.
    held_epoch = np.searchsorted(switches, stamps, side="left")
    # In this 1 pL bath the amount in fmol equals the concentration in mM.
    held = levels[held_epoch]
    dose = np.asarray(series[f"bath_dose_{s}_fmol"])
    np.testing.assert_array_equal(series[f"bath_held_{s}_fmol"], held)
    np.testing.assert_array_equal(dose, held - c0)
    np.testing.assert_array_equal(series["bath_compensation_charge_C"], 0.0)
    events = records.event_records(world)
    reference_energy = np.array([0.0, *(e["cumulative_dG_b_pJ"] for e in events)])[held_epoch]
    energy_error = float(np.max(np.abs(reference_energy - series["bath_dose_free_energy_pJ"])))
    assert energy_error < 2e-14
    trajectory = faces.solve(faces.parse(world))
    pool_error = np.max(np.abs(trajectory["amount_fmol"][:, 0] - series[f"amount_{s}_ecs_0"]))
    supply_error = np.max(np.abs(trajectory["supply_fmol"] - supply))
    # Isolate work arithmetic from transport error, then check the combined result.
    k_seen = np.asarray(series["bath_reconciliation_pJ"])
    k_measured = records.reconciliation_K(world, stamps, {s: supply})["K_pJ"]
    k_ref = records.reconciliation_K(world, stamps, {s: trajectory["supply_fmol"]})["K_pJ"]
    work_error = np.max(np.abs(k_seen - k_measured))
    combined_error = np.max(np.abs(k_seen - k_ref))
    amount_atol, work_atol = (3e-9, 1e-8) if solver == bath.ARS else (2e-15, 2e-14)
    assert max(pool_error, supply_error) < amount_atol
    assert work_error < 2e-16 and combined_error < work_atol
    # When the original composition returns the correction still carries the work of past supply.
    assert dose[-1] == 0 and abs(supply[-1]) > 1e-5 and abs(k_seen[-1]) > 1e-5
    assert np.min(np.diff(supply)) < 0 < np.max(np.diff(supply))
    return dict(
        solver=solver,
        dt_s=dt,
        rows=len(times),
        final_dose_fmol=dose[-1],
        final_tissue_supply_fmol=supply[-1],
        final_bath_energy_pJ=series["bath_dose_free_energy_pJ"][-1],
        final_reconciliation_pJ=k_seen[-1],
        max_dose_energy_error_pJ=energy_error,
        max_pool_error_fmol=pool_error,
        max_supply_error_fmol=supply_error,
        max_reconciliation_error_given_engine_supply_pJ=work_error,
        max_reconciliation_error_vs_continuous_pJ=combined_error,
    )


def recipe_orders(anchor, increment, scale):
    """Three names with distinct integer stoichiometries give the same exact net dose."""
    s, dt = pools.SPECIES, 1 / 1024
    units = {"pair": {s: 2}, "single": {s: 1}, "triple": {s: 3}}
    offsets = {"pair": 12 * scale, "single": increment, "triple": -8 * scale}
    raw = pools.world(nodes=(), contacts=(), faces=(), dt=dt, end=4 * dt, trace_mM=anchor)
    doses = {}
    for names in (("pair", "triple", "single"), ("pair", "single", "triple")):
        recipe = {name: offsets[name] for name in names}
        exact = sum(units[name][s] * Fraction(value) for name, value in recipe.items())
        assert exact == Fraction(increment)
        # The three products are exactly representable in these examples.
        assert math.fsum(units[name][s] * value for name, value in recipe.items()) == increment
        spec = parse_spec(bath.with_bath_schedule(raw, ["bath"], units, [(dt, ["bath"], recipe)]))
        row = spec.model.species_ids.index(s)
        target = float(control_values(spec, [dt]).bath_target_amount_fmol[0, row, 0])
        result = run(spec)
        held = float(result.history.bath_held_amount_fmol[-1, row, 0])
        dose = float(result.history.bath_dose_fmol[-1, row, 0])
        assert target == held == anchor + dose
        doses[" ".join(names)] = dose
    return dict(
        anchor_mM=anchor,
        intended_dose_fmol=increment,
        opposing_terms_mM=24 * scale,
        booked_doses_fmol=doses,
        correct=all(v == increment for v in doses.values()),
    )


def potassium_reversals():
    data = json.loads((Path(__file__).parent / "data/randle1991_potassium.json").read_text())
    conditions = data["conditions"]
    k = np.array([row["KCl_mM"] for row in conditions])
    t = 273.15 + np.mean(data["bath_temperature_C"])
    salt = sum(data["reference_salts_mM"].values())
    ci = 143.0  # Nominal pipette K. It cancels from the predicted shifts at fixed composition.
    dt = 1 / 2048
    raw = bath.ion_world(dt=dt, end=8 * dt, events=False)
    raw["experiment"]["observation_times"] = [step * dt for step in range(9)]
    m = raw["model"]
    m["temperature_K"] = float(t)
    cell, reservoir, wall = m["cells"][0], m["extracellular"][0], m["membranes"][0]
    # Only the exchanged salts set the K-selective reversal. The other bath solutes stay fixed.
    reservoir["initial_amount_fmol"].update(K=float(k[0]), Na=float(salt - k[0]), Cl=salt)
    reservoir["fixed_charge_equivalent_fmol"] = 0.0
    cell["initial_amount_fmol"]["K"] = ci
    charge = float(wall["capacitance_F"] * R * t / F * math.log(k[0] / ci))
    cell["initial_charge_C"] = charge
    cell["fixed_charge_equivalent_fmol"] = charge / CHARGE_PER_FMOL - math.fsum(
        z * cell["initial_amount_fmol"][s] for s, z in pools.ION_SPECIES
    )
    for i, concentration in enumerate(k[1:], 1):
        offset = float(concentration - k[0])
        raw["experiment"]["bath_composition_events"].append(
            dict(time=2 * i * dt, baths=["bath"], formula_units_mM={"KCl": offset, "NaCl": -offset})
        )
    spec = parse_spec(raw)
    obs = run(spec).observations
    slots = list(spec.model.species_ids)
    rows = [0, 3, 5, 7]  # Initial row and first accepted row after each switch.
    tissue_k = np.asarray(obs.amount)[rows, slots.index("K"), 0]
    held = np.asarray(obs.bath_held_amount_fmol)[rows, :, 0]
    for s, expected in (("K", k), ("Na", salt - k), ("Cl", np.full(k.shape, salt))):
        np.testing.assert_allclose(held[:, slots.index(s)], expected, atol=3e-14, rtol=0)
    np.testing.assert_allclose(
        np.asarray(obs.bath_compensation_charge_C)[rows, 0], 0.0, atol=3e-24, rtol=0
    )
    area, permeability = wall["area_m2"], wall["permeability_m_per_s"]["K"]

    def flux(v, inside, outside):
        return selective_flux(inside, outside, v, 1, t, area, permeability, 0.0, 1.0, 1.0, xp=np)

    co = held[:, slots.index("K")]
    # Check the actual currents at the saved state, then voltage-scan at a common pipette K.
    np.testing.assert_allclose(
        flux(np.asarray(obs.membrane_voltage_V)[rows, 0], tissue_k, co),
        np.asarray(obs.membrane_flux_fmol_s)[rows, slots.index("K"), 0],
        atol=1e-16,
        rtol=2e-13,
    )
    roots = np.array([1000 * brentq(flux, -0.2, 0.05, args=(ci, c), xtol=5e-17) for c in co])
    shifts = np.diff(roots)
    analytic = 1000 * R * t / F * np.log(k[1:] / k[:-1])
    np.testing.assert_allclose(shifts, analytic, atol=2e-12, rtol=0)
    observed = np.diff([row["mean_mV"] for row in conditions])
    return dict(
        bath_K_mM=co.tolist(),
        predicted_adjacent_shifts_mV=shifts.tolist(),
        observed_adjacent_shifts_mV=observed.tolist(),
        temperature_K=t,
        predicted_5p4_to_12_over_reported_temperature_mV=[
            1000 * R * (273.15 + c) / F * math.log(12 / 5.4) for c in data["bath_temperature_C"]
        ],
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="omit the high-cancellation recipes"
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        ordinary = recipe_orders(2**-10, 2**-11, 1)
        assert ordinary["correct"]
        report = dict(
            ordinary_recipe=ordinary,
            neutral_pulse=[pulse(bath.ARS, 1 / 1024), pulse(bath.RK4, 1 / 16384)],
            potassium=potassium_reversals(),
        )
        if not args.controls_only:
            report["cancelling_recipes"] = [
                recipe_orders(2**-10, 2**-11, 2**39),
                recipe_orders(2**-49, 2**-49, 1),
            ]
        print(json.dumps(report, indent=2, allow_nan=False))
        raise SystemExit(int(any(not r["correct"] for r in report.get("cancelling_recipes", []))))
