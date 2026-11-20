"""Compare water-potential equilibria and pressure-driven flow with primary measurements."""

import json
from pathlib import Path

import numpy as np
from scipy.optimize import brentq

from cells.numerics import osmotic_water as water
from validation.core_seams.references import exact

DATA = Path(__file__).with_name("data")


def stall_volume(v0, c0, bath, modulus, temperature):
    # Hold the outside at 1 pL. One mOsm/L gives one fmol of ideal particles per pL.
    ref = np.array([v0, 1.0])
    p = water.validate_parameters(
        water.Parameters(
            temperature_K=temperature,
            active=np.array([True, True]),
            reference_volume_pL=ref,
            minimum_volume_pL=0.1 * ref,
            maximum_volume_pL=3 * ref,
            impermeant_amount_fmol=np.array([v0 * c0, bath]),
            bulk_modulus_Pa=np.array([modulus, 0.0]),
            pressure_offset_Pa=np.zeros(2),
            edge_active=np.array([True]),
            sender=np.array([0]),
            receiver=np.array([1]),
            conductance_pL_per_Pa_s=np.array([1.0]),
        )
    )
    amounts = np.zeros((1, 2))

    def flow(volume):
        volumes = np.array([volume, 1.0])
        assert water.domain_valid(volumes, amounts, p)
        return water.edge_exchange(volumes, amounts, np.ones(1), p).edge_flow_pL_s[0]

    return brentq(flow, 0.2 * v0, 2.5 * v0, xtol=1e-15)


def vesicle_swelling():
    d = json.loads((DATA / "shibly2016_swelling.json").read_text())
    fit, test = d["fit"], d["evaluation"]
    c0 = d["initial_sucrose_mM"]
    t = 273.15 + d["temperature_C"]
    rt = float(exact.RT_J_per_mol(t))
    fraction = fit["mean_swelling_percent"] / 100
    modulus = rt * (c0 / (1 + fraction) - fit["bath_glucose_mM"]) / fraction
    np.testing.assert_allclose(stall_volume(1, c0, c0, modulus, t), 1, atol=1e-14, rtol=0)
    np.testing.assert_allclose(
        stall_volume(1, c0, fit["bath_glucose_mM"], modulus, t), 1 + fraction, atol=1e-14, rtol=0
    )
    c = test["bath_glucose_mM"]
    y = stall_volume(1, c0, c, modulus, t)
    # The positive root of the Lean quadratic, expressed without root subtraction.
    b = rt * c - modulus
    analytical = 2 * rt * c0 / (b + np.sqrt(b**2 + 4 * modulus * rt * c0))
    np.testing.assert_allclose(y, analytical, atol=1e-14, rtol=0)
    return dict(
        modulus_Pa=modulus,
        predicted_percent=100 * (y - 1),
        observed_percent=test["mean_swelling_percent"],
        ideal_percent=100 * (c0 / c - 1),
    )


def red_cell(d):
    c0, total0, _ = d["fit"]
    inactive = d["inactive_fL"]
    v0 = (total0 - inactive) / 1000
    # Any positive common temperature cancels at zero hydrostatic pressure difference.
    temperature = 273.15 + (25 if d["temperature_C"] is None else d["temperature_C"])
    rows = []
    for c, total, sd in d["evaluation"]:
        v = stall_volume(v0, c0, c, 0, temperature)
        np.testing.assert_allclose(v, v0 * c0 / c, atol=1e-15, rtol=0)
        rows.append(
            dict(
                bath_mOsm_L=c,
                predicted_fL=1000 * v + inactive,
                observed_fL=total,
                observed_SD_fL=sd,
            )
        )
    return dict(trapped_fmol=v0 * c0, held_out=rows)


def pressure_reversal():
    d = json.loads((DATA / "wendler1982_pressure.json").read_text())
    fit, test = d["fit"], d["evaluation"]
    # pressure_step_flow gives the initial inward change as minus G times the step.
    mobility = -fit["inward_flow_nL_s"] / fit["pressure_change_bar"]
    return dict(
        conductance_nL_per_bar_s=mobility,
        predicted_inward_nL_s=-mobility * test["pressure_change_bar"],
        observed_inward_nL_s=test["inward_flow_nL_s"],
    )


if __name__ == "__main__":
    cells = json.loads((DATA / "kwant1970_osmometry.json").read_text())
    print(
        json.dumps(
            dict(
                vesicles=vesicle_swelling(),
                ghosts=red_cell(cells["ghosts"]),
                intact=red_cell(cells["intact"]),
                pressure_clamp=pressure_reversal(),
            ),
            indent=2,
            allow_nan=False,
        )
    )
