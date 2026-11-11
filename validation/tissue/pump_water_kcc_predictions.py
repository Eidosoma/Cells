"""W2 predictions: stationary states of the heredity cell with water and a KCC-type route.

From the independent reduced reference (validation/tissue/pump_water_reference.py:
regulated_stationary_states and stationary_spectrum; no Cells code), computed and
frozen before any W2 engine run. The world is the W1 P2 heredity cell (approved
water parameters) with one route of k_anion_symport_mass_action@1 on its membrane
(roles K and M), V_set = the declared reference volume and availability 1:

  capacity  red-cell range 4, 15 and 20 mmol/(L cells h) of K:Cl efflux at the
            Lew et al. 1991 reference product difference (cell K 140 x Cl 95 minus
            K 5 x Cl 140 mM^2). These are reticulocyte-rich and young-cell data
            (Brugnara 1986/1987 via Lew 1991; Canessa et al. 1987), not normal
            mature red cells. Plus a neuron-scale arm, model-derived from Staley &
            Proctor 1999 (Vmax 6 mmol/(L s) = 21,600 mmol/(L h)).
  steepness s = 1 (Lew 1991) and s = 0.12 (Kaji 1986's 4-5x at 1.2 V, derived).

For each arm: the stationary states (Vm, composition, V/V0, osmolarity, route
cycles), the reference Jacobian's leading growth rate at each state, the D
volume against the route-free D (W1 P2) and its headroom to Vmax. The block arm
(VU0463271, availability 0) is the route-free W1 world.

Usage: python -m validation.tissue.pump_water_kcc_predictions --output DIR
"""

import argparse
import json
import time
import traceback
from pathlib import Path

from validation.tissue import pump_water_fixtures as fixtures
from validation.tissue import pump_water_reference as ref

REFERENCE_PRODUCT_DIFFERENCE_mM2 = 140 * 95 - 5 * 140  # Lew et al. 1991 reference state
CAPACITIES = {
    "red_cell_4": 4.0,
    "red_cell_15": 15.0,
    "red_cell_20": 20.0,
    "neuron_scale_model_derived": 21600.0,
}
STEEPNESS = {"lew_s1": 1.0, "kaji_s0.12": 0.12}


def capacity(flux_mmol_L_h, volume_pL):
    """k (fmol/(s mM^2)) of the cell: the flux per cell volume at the reference difference."""
    return flux_mmol_L_h * volume_pL / 3600.0 / REFERENCE_PRODUCT_DIFFERENCE_mM2


def states(raw, kcc):
    v0 = raw["model"]["cells"][0]["volume_pL"]
    vmax = raw["model"]["water"]["compartments"][0]["maximum_volume_pL"]
    out = []
    for state in ref.regulated_stationary_states(raw, kcc):
        vm, conc, volume, osmolarity, cycles = state
        out.append(
            dict(
                membrane_voltage_V=vm,
                concentration_mM=conc,
                volume_pL=volume,
                volume_ratio=volume / v0,
                osmolarity_mM=osmolarity,
                route_cycles_fmol_s=cycles,
                headroom_to_maximum=vmax / volume - 1,
                spectrum=ref.stationary_spectrum(raw, kcc, state),
            )
        )
    return out


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    out = Path(args.output)
    out.mkdir(parents=True, exist_ok=True)
    raw = fixtures.with_water(fixtures.heredity_cell("H"))
    v0 = raw["model"]["cells"][0]["volume_pL"]
    result = dict(
        reference="validation/tissue/pump_water_reference.py (numpy/scipy, no Cells code)",
        law="k_anion_symport_mass_action@1 with exponential_volume_activation@1",
        definition=raw,
        reference_product_difference_mM2=REFERENCE_PRODUCT_DIFFERENCE_mM2,
        route_free=None,
        arms={},
    )
    try:
        started = time.perf_counter()
        result["route_free"] = states(raw, None)
        route_free_d = max(result["route_free"], key=lambda s: s["membrane_voltage_V"])
        for cname, flux in CAPACITIES.items():
            for sname, s in STEEPNESS.items():
                kcc = dict(
                    capacity_fmol_s_mM2=capacity(flux, v0),
                    set_volume_pL=raw["model"]["water"]["compartments"][0]["reference_volume_pL"],
                    steepness=s,
                    availability=1.0,
                )
                found = states(raw, kcc)
                depolarized = [x for x in found if x["membrane_voltage_V"] > -0.03]
                result["arms"][f"{cname}-{sname}"] = dict(
                    flux_mmol_L_h=flux,
                    parameters=kcc,
                    states=found,
                    d_volume_ratio=depolarized[-1]["volume_ratio"] if depolarized else None,
                    d_volume_change_against_route_free=(
                        depolarized[-1]["volume_pL"] / route_free_d["volume_pL"] - 1
                        if depolarized
                        else None
                    ),
                )
                (out / "kcc-predictions.json").write_text(json.dumps(result, indent=2) + "\n")
        result["seconds"] = time.perf_counter() - started
        (out / "kcc-predictions.json").write_text(json.dumps(result, indent=2) + "\n")
    except Exception:
        (out / "failure.json").write_text(
            json.dumps(dict(arms=list(result["arms"]), traceback=traceback.format_exc()), indent=2)
            + "\n"
        )
        raise


if __name__ == "__main__":
    main()
