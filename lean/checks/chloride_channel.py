"""Compare the compiled tissue chloride leak with a scalar GHK/capacitor trajectory."""

import json

import jax
import numpy as np
from scipy.integrate import solve_ivp
from scipy.optimize import brentq

from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.laws.junctions.selective import selective_flux
from cells.registry import laws
from tests.unit.test_chloride_leak_law import chloride_world
from validation.betse.junction_transport.check import decimal_flux
from validation.tissue.surface_reference import F, R

DT, END = 2**-15, 2**-11
TIMES = [0.0, END / 2, END]
LAW = "cells.channel.clleak_always_open@1"


def paper_reversal_shift():
    """Ling et al., Fig. 1B. A fixed inside concentration cancels from the predicted shift."""
    temperature, inside = 310.15, 50.0

    def reversal(outside):
        def flux(voltage):
            return selective_flux(inside, outside, voltage, -1, temperature, 1, 1, 0, 1, 1, xp=np)

        return brentq(flux, -0.120, 0.060)

    shift = 1000 * (reversal(15.0) - reversal(145.0))
    ideal = 1000 * R * temperature / F * np.log(145.0 / 15.0)
    np.testing.assert_allclose(shift, ideal, atol=1e-8, rtol=0)
    return dict(outside_mM=[145.0, 15.0], temperature_K=temperature, model_shift_mV=shift)


def compare(swap, expected_direction):
    raw = chloride_world(patch=0.0, population=4e-9, swap=swap)
    model, experiment = raw["model"], raw["experiment"]
    patch = model["membranes"][0]
    patch["permeability_m_per_s"] = dict.fromkeys(patch["permeability_m_per_s"], 0.0)
    patch["pump"] = None
    experiment["pump_controls"] = []
    (channel,) = [ch for ch in model["channels"] if ch["kinetic_law"] == LAW]
    model["channels"] = [channel]
    experiment["channel_controls"] = [
        c for c in experiment["channel_controls"] if c["channel_id"] == channel["id"]
    ]
    experiment.update(end_time=END, observation_times=TIMES)
    raw["execution"].update(dt=DT, max_steps=32, channel_capacity=2)
    spec = parse_spec(raw)
    obs = run(spec).observations
    cl = spec.model.species_ids.index("Cl")

    cell, bath = model["cells"][0], model["extracellular"][0]
    ci = cell["initial_amount_fmol"]["Cl"] / cell["volume_pL"]
    co = bath["initial_amount_fmol"]["Cl"] / bath["volume_pL"]
    v0 = cell["initial_charge_C"] / patch["capacitance_F"]
    volts_per_fmol = F * 1e-15 / patch["capacitance_F"]

    def rate(transfer):
        return decimal_flux(
            ci - transfer / cell["volume_pL"],
            co,
            v0 + volts_per_fmol * transfer,
            -1,
            model["temperature_K"],
            patch["area_m2"],
            channel["max_permeability_m_per_s"],
            1,
            1,
            {"F": F, "R": R},
        )

    solution = solve_ivp(
        lambda _, x: [rate(x[0])],
        (0, END),
        [0.0],
        t_eval=TIMES,
        method="DOP853",
        rtol=2e-12,
        atol=1e-17,
    )
    if not solution.success:
        raise RuntimeError(solution.message)
    (transfer,) = solution.y
    flux = np.array([rate(x) for x in transfer])
    current = -F * 1e-15 * flux
    actual_flux = np.asarray(obs.channel_flux_fmol_s)[:, cl, 0]
    actual_transfer = np.asarray(obs.channel_transferred)[:, cl, 0]
    actual_current = np.asarray(obs.electrode_current_A)[:, 0]
    atol = raw["execution"]["material_balance_atol_fmol"]["Cl"]
    assert np.all(np.sign(actual_flux) == expected_direction)
    assert np.all(np.sign(actual_current) == -expected_direction)
    np.testing.assert_allclose(actual_flux, flux, atol=0, rtol=2e-6)
    np.testing.assert_allclose(actual_current, current, atol=0, rtol=2e-6)
    np.testing.assert_allclose(actual_transfer, transfer, atol=atol, rtol=0)
    for booked in (obs.amount_increment, obs.reservoir_supplied):
        np.testing.assert_allclose(booked[:, cl, 0], -transfer, atol=atol, rtol=0)
        np.testing.assert_array_equal(np.delete(booked[:, :, 0], cl, axis=1), 0)
    np.testing.assert_allclose(
        obs.electrode_charge_transferred_C[:, 0],
        -F * 1e-15 * transfer,
        atol=F * 1e-15 * atol,
        rtol=0,
    )
    np.testing.assert_allclose(
        obs.membrane_voltage_V[:, 0], v0 + volts_per_fmol * transfer, atol=1e-8, rtol=0
    )
    for values in (obs.channel_flux_fmol_s, obs.channel_transferred):
        np.testing.assert_array_equal(values[:, :, 1], 0)
        np.testing.assert_array_equal(np.delete(values[:, :, 0], cl, axis=1), 0)
    np.testing.assert_array_equal(obs.extracellular_amount_increment, 0)
    return dict(
        inside_mM=ci,
        bath_mM=co,
        temperature_K=model["temperature_K"],
        initial_voltage_V=v0,
        nernst_voltage_V=R * model["temperature_K"] / F * np.log(ci / co),
        initial_outward_flux_fmol_s=actual_flux[0],
        initial_electrode_current_A=actual_current[0],
        final_outward_transfer_fmol=actual_transfer[-1],
        max_transfer_error_fmol=float(np.max(abs(actual_transfer - transfer))),
        max_electrode_current_error_A=float(np.max(abs(actual_current - current))),
    )


if __name__ == "__main__":
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Run with JAX_PLATFORMS=cpu and JAX_ENABLE_X64=1")
    law = laws.active().lookup(LAW)
    assert law.gates == () and law.permeant == (("Cl", -1, 1.0),)
    print(
        json.dumps(
            dict(
                model="cells.model.resolved_pump_tissue@3",
                law=LAW,
                dt_s=DT,
                end_s=END,
                cases=[compare(-0.05, -1), compare(0.5, 1)],
                paper_reversal=paper_reversal_shift(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
