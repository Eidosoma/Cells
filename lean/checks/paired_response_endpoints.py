"""Measure the observable shared by each preparation using the Cells law's own readout."""

import json
import math
from pathlib import Path

import jax
import jax.numpy as jnp
import leaflet_packing
import numpy as np
import pool_withdrawal
import vesicle
import vesicle_events
import wall_wash

from cells.laws.routes import inward_rectifier_linear_driving_force as kir
from cells.models.assembly_lineages_v2 import kernel, model
from cells.operators import species_exchange

DATA = Path(__file__).with_name("data")


def load(filename):
    return json.loads((DATA / filename).read_text())


def thermal_area():
    inputs = load("leaflet_packing.json")
    rows = {}
    for key in ("kucerka2011_popc_temperature@1", "leftin2014_popc_temperature@1"):
        study = inputs[key]
        cold, warm = study["temperature_C"]
        first, second = study["area_per_lipid_A2"]
        a, b, c = (
            leaflet_packing.compiled_area(t, area, study["doi"])
            for t, area in ((cold, first), (warm, first), (warm, second))
        )
        assert a == b < c
        rows[key] = {"fixed_warm_over_cold": b / a, "warm_over_cold_with_measured_inputs": c / a}
    return rows


def rupture_at_tension(sigma_mN_m, limit_mN_m, temperature_K):
    # Realize the requested tension on one stationary spherical state. Geometry and counts
    # only supply the native threshold input; they do not represent an experimental vesicle.
    n, r = 64, 1e-9
    area = 4 * math.pi * r * r
    cap = area * r / 3
    avogadro, kb = float(vesicle.NA), float(vesicle.KB)
    bath = (n / cap - 2 * (sigma_mN_m / 1000) / (r * kb * temperature_K)) / avogadro
    assert bath > 0
    raw = vesicle.osmotic_world(
        L_pool=0,
        L_mem=64,
        S_pool=0,
        S_lumen=0,
        I_lumen=1,
        floor=64 * vesicle.K_L,
        sigma_max=limit_mN_m / 1000,
    )
    raw["units"]["temperature_K"] = temperature_K
    raw["geometry"]["area_quantum_m2"] = 2 * area / (64 * vesicle.K_L)
    raw["free_energy"][1]["outside_osmolarity_mM"]["value"] = bath
    spec = vesicle.spec_of(raw, event_limit=4, row_every=1)
    counts = model.founder(spec)
    # A founder must survive. Evaluate lysis on the trial state, as the engine does.
    counts[spec.model.world.place_index("I@lumen")] = n
    actual = vesicle.lumen.host_tension(spec.model.world, counts[: len(spec.model.world.places)])
    np.testing.assert_allclose(actual * 1000, sigma_mN_m, atol=1e-9)
    return bool(kernel.lysis_at(counts, model.layout(spec), xp=np))


def intact_vesicles():
    rows = load("paired_wet_lab_measurements.json")
    v = rows["viallat2004_sucrose_deflation@1"]
    start, _ = vesicle.bath_world(v["initial_sucrose_mM"], v["initial_sucrose_mM"])
    end, _ = vesicle.bath_world(v["initial_sucrose_mM"], v["final_glucose_mM"])
    observed = (v["final_radius_um"] / v["initial_radius_um"]) ** 3
    first = vesicle_events.intact_deflation()
    karal = load("vesicle_rupture_holds.json")["karal2015_dopc_hold@1"]
    hold = next(row for row in karal["series"] if row["temperature_C"] == 32)
    ramp = rows["evans2003_dopc_tension_ramps@1"]
    # An illustrative 9 mN/m threshold lies in the gap between reported high-count
    # regions. Any common fixed threshold crosses at the same tension at either rate.
    probes = [
        *ramp["slow_high_count_region_mN_per_m_approx"],
        *ramp["fast_high_count_region_mN_per_m_approx"],
    ]
    mask = [rupture_at_tension(s, 9, 298.15) for s in probes]
    assert mask == [False, False, True, True]
    assert not rupture_at_tension(8, 9, 305.15) and rupture_at_tension(8, 7, 305.15)
    return dict(
        fujiwara=(
            first["compiled_final_over_initial"],
            first["measured_final_over_initial_approx"],
        ),
        viallat=(end / start, observed),
        hold_survival_points=hold["points"],
        hold_fate_at_8mN_m={"threshold_7": "rupture", "threshold_9": "survive"},
        ramp_rate_mN_m_s=ramp["ramp_rates_mN_per_m_per_s"],
        tension_probes_mN_m=probes,
        threshold_9_fates_at_either_ramp=mask,
    )


def sugar_rates():
    studies = load("paired_wet_lab_measurements.json")

    def gain(h, c, km):
        return species_exchange.saturable_removed(c, 1.0, km, h, xp=jnp)[0]

    slope = jax.jit(jax.grad(gain))
    cold = studies["klepper2001_cold_red_cell_influx@1"]["km_mM"]
    warm = studies["batt1973_red_cell_influx@1"]["kt_mM"]
    results = []
    for k in (cold, *warm):
        ratios = [float(slope(0.0, c, k)) for c in (k / 2, k, k * 2)]
        np.testing.assert_allclose(ratios, [1 / 3, 1 / 2, 2 / 3], rtol=2e-14)
        results.append(dict(measured_half_mM=k, native_fraction_of_capacity=ratios))
    return results


def kir_reversal():
    recombinant = load("tada1998_kir41.json")
    frog = load("paired_calibration_measurements.json")["kucheryavykh2008_muller_reversal@1"]

    def shift(low, high, t):
        # Change in the zero is independent of fixed internal K.
        return float(1000 * (kir.reversal_V(100, high, t) - kir.reversal_V(100, low, t)))

    return dict(
        recombinant_mV=shift(
            recombinant["outside_K_mM"][0],
            recombinant["outside_K_mM"][-1],
            recombinant["temperature_K"],
        ),
        frog_mV_at_25C=shift(*frog["outside_K_mM"], 298.15),
    )


if __name__ == "__main__":
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    wall, _ = wall_wash.compare("node", 1.0, wall_wash.fx.TRACE_mM, trajectory=False)
    result = dict(
        thermal_area=thermal_area(),
        vesicles=intact_vesicles(),
        sugar=sugar_rates(),
        kir_reversal=kir_reversal(),
        bead_fractions=pool_withdrawal.droplets(),
        withdrawal_events=pool_withdrawal.host_counts(),
        native_wall_draw=wall,
    )
    print(json.dumps(result, indent=2, allow_nan=False))
