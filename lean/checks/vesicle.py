"""Bilayer area, osmotic volume, rupture at a tension threshold and measured vesicle volumes."""

import argparse
import json
import math
from decimal import Decimal, localcontext
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.models.assembly_lineages_v2 import geometry, lumen, runner
from tests.unit.test_assembly_lineages_v2_lumen import K_L, Q, osmotic_world, spec_of, species

DATA = Path(__file__).parent / "data"
PI = Decimal("3.141592653589793238462643383279502884197169399375105820974944592307816406286")
NA = Decimal("6.02214076e23")
KB = Decimal("1.380649e-23")


def reference(q, footprint, solutes, bath_mM, temperature, standard_mM):
    """Independent 70-digit calculation from radius and sphere volume, in SI units."""
    with localcontext() as ctx:
        ctx.prec = 70
        area = Decimal.from_float(q) * int(footprint) / 2
        r = (area / (4 * PI)).sqrt()
        sphere = 4 * PI * r**3 / 3  # m³
        n = Decimal(int(solutes))
        c = NA * Decimal.from_float(float(bath_mM))  # particles/m³
        volume = min(n / c, sphere)
        excess = max(Decimal(0), n / sphere - c)
        tension = KB * Decimal.from_float(temperature) * r * excess / 2
        standard = NA * Decimal.from_float(standard_mM)
        energy = -n * (standard * volume).ln() + c * volume if n else Decimal(0)
        return dict(
            area_m2=float(area),
            radius_m=float(r),
            cap_L=float(sphere * 1000),
            volume_L=float(volume * 1000),
            tension_N_m=tension,
            energy_kT=float(energy),
        )


def moving_bilayer(refinement):
    raw = osmotic_world(I_lumen=4)
    raw["species"].append(species("M", {"m": 1}, solution=0.0, bilayer=-1.0))
    raw["phases"]["pool"]["species"].append(dict(id="M", kind="finite"))
    raw["phases"]["membrane"]["species"].append("M")
    raw["founder"].update({"M@pool": 0, "M@membrane": 2})
    raw["geometry"]["area_per_leaflet"]["M"] = dict(quanta=15, provenance="synthetic")
    refine(raw, refinement)
    return spec_of(raw, horizon=100, event_limit=96, row_every=1)


def refine(raw, factor):
    geometry = raw["geometry"]
    geometry["area_quantum_m2"] /= factor
    geometry["vesicle_floor"]["quanta"] *= factor
    for lipid in geometry["area_per_leaflet"].values():
        lipid["quanta"] *= factor


@jax.jit
def device_rows(solutes, footprint, constants):
    return lumen.free_energy(solutes, footprint, constants, jnp)


def trajectory(factor):
    spec = moving_bilayer(factor)
    result = runner.run(spec).check()
    world, rows = spec.model.world, result.rows
    names = [p.name for p in world.places]
    counts = rows["place_count"]
    footprint = factor * (
        K_L * counts[:, names.index("L@membrane")] + 15 * counts[:, names.index("M@membrane")]
    )
    n = counts[:, names.index("S@lumen")] + counts[:, names.index("I@lumen")]
    np.testing.assert_array_equal(rows["membrane_footprint_quanta"], footprint)
    ref = [
        reference(
            Q / factor, w, s, 1000, world.units.temperature_K, world.units.standard_concentration_mM
        )
        for w, s in zip(footprint, n, strict=True)
    ]
    v = np.array([r["volume_L"] for r in ref])
    sigma = np.array([r["tension_N_m"] for r in ref], dtype=float)
    f = np.array([r["energy_kT"] for r in ref])
    np.testing.assert_allclose(rows["lumen_volume_L"], v, rtol=3e-14, atol=0)
    np.testing.assert_allclose(rows["tension_N_per_m"], sigma, rtol=2e-12, atol=2e-17)
    energy = np.asarray(device_rows(n, footprint, np.array(lumen.constants(world))))
    np.testing.assert_allclose(energy, f, rtol=1e-12, atol=1e-12)
    assert (
        result.closure["holds"]
        and len(set(footprint)) > 2
        and np.any(sigma > 0)
        and np.any(sigma == 0)
    )
    return (
        counts,
        rows["row_time"],
        dict(
            refinement=factor,
            events=result.final["events"].item(),
            rows=len(v),
            distinct_footprints=len(set(footprint)),
            slack_rows=int(sum(sigma == 0)),
            taut_rows=int(sum(sigma > 0)),
            max_relative_volume_error=float(max(abs(rows["lumen_volume_L"] / v - 1))),
            max_tension_error_N_m=float(max(abs(rows["tension_N_per_m"] - sigma))),
            max_energy_error_kT=float(max(abs(energy - f))),
        ),
    )


def bath_world(effective_mM, bath_mM, temperature_K=298.15):
    """A pinned, 64-osmole vesicle with the specified isotonic solute count per spherical volume."""
    n = 64
    cap = n / (float(NA) * effective_mM)  # m³
    r = (3 * cap / (4 * math.pi)) ** (1 / 3)
    area = 4 * math.pi * r**2
    raw = osmotic_world(L_pool=0, L_mem=n, S_pool=0, S_lumen=0, I_lumen=n, floor=n * K_L)
    raw["units"]["temperature_K"] = temperature_K
    raw["geometry"]["area_quantum_m2"] = 2 * area / (n * K_L)
    raw["free_energy"][1]["outside_osmolarity_mM"]["value"] = bath_mM
    spec = spec_of(raw, event_limit=4, row_every=1)
    result = runner.run(spec).check()
    assert result.closure["holds"] and not np.any(result.rows["channel_fired"])
    q = raw["geometry"]["area_quantum_m2"]
    ref = reference(q, n * K_L, n, bath_mM, spec.model.world.units.temperature_K, 1000.0)
    vs = result.rows["lumen_volume_L"]
    np.testing.assert_allclose(vs, ref["volume_L"], rtol=3e-14, atol=0)
    np.testing.assert_allclose(
        result.rows["tension_N_per_m"], float(ref["tension_N_m"]), rtol=3e-12, atol=2e-17
    )
    sigma = result.rows["tension_N_per_m"][-1]
    return float(vs[-1] / ref["cap_L"]), float(sigma / ref["radius_m"])


def popc_footprint():
    data = json.loads((DATA / "kucerka2011_popc.json").read_text())
    n, q = 64, 1e-21
    measured = data["area_A2"] * 1e-20
    k = round(measured / q)
    raw = osmotic_world(L_pool=0, L_mem=n, S_pool=0, S_lumen=0, I_lumen=0, floor=n * k)
    raw["units"]["temperature_K"] = 273.15 + data["temperature_C"]
    raw["geometry"]["area_quantum_m2"] = q
    raw["geometry"]["area_per_leaflet"]["L"] = dict(
        quanta=k, provenance="measured", sourced_m2=measured, source=data["doi"]
    )
    spec = spec_of(raw, event_limit=4, row_every=1)
    run = runner.run(spec).check()
    assert run.closure["holds"] and not np.any(run.rows["channel_fired"])
    footprint = run.rows["membrane_footprint_quanta"]
    np.testing.assert_array_equal(footprint, n * k)
    area = geometry.area_m2(spec.model.world, footprint)
    np.testing.assert_allclose(area, n * measured / 2, rtol=2e-15, atol=0)
    np.testing.assert_array_equal(run.rows["lumen_volume_L"], 0)
    np.testing.assert_array_equal(run.rows["tension_N_per_m"], 0)
    return dict(
        leaflet_quanta=k,
        membrane_lipids=n,
        bilayer_area_nm2=float(area[-1] * 1e18),
        area_uncertainty_nm2=n / 2 * data["reported_uncertainty_A2"] * 0.01,
    )


def measurements():
    series = json.loads((DATA / "wolfisberg2025_vesicle.json").read_text())
    points = series["points"]
    initial = series["initial_lumen_sucrose_mM"]
    anchored = points[0]["bath_mOsm_L"] * points[0]["reduced_volume"]
    deflation = []
    for point in points:
        bath = point["bath_mOsm_L"]
        nominal, _ = bath_world(initial, bath)
        fitted, _ = bath_world(anchored, bath)
        assert abs(nominal - min(1, initial / bath)) < 3e-14
        assert abs(fitted - min(1, anchored / bath)) < 3e-14
        deflation.append(dict(**point, nominal=nominal, first_point_calibrated=fitted))
    study = json.loads((DATA / "shibly2016_swelling.json").read_text())
    initial = study["initial_sucrose_mM"]
    # Calibrate the common area reserve with the first swelling. The second is held out.
    reserve = 1 + study["fit"]["mean_swelling_percent"] / 100
    swelling = []
    for key in ("fit", "evaluation"):
        row = study[key]
        bath = row["bath_glucose_mM"]
        sphere, _ = bath_world(initial, bath)
        reduced, _ = bath_world(initial / reserve, bath)
        with_reserve = reserve * reduced
        assert abs(sphere - 1) < 3e-14 and abs(with_reserve - reserve) < 3e-14
        swelling.append(
            dict(
                **row,
                spherical_percent=100 * (sphere - 1),
                calibrated_percent=100 * (with_reserve - 1),
            )
        )
    tension = study["rupture_rate_tension"]
    delta = tension["initial_osmotic_difference_mM"]
    temperature = study["temperature_C"] + 273.15
    radius = tension["initial_radius_um"] * 1e-6
    # For an initially full, inextensible sphere sigma/r is independent of radius.
    _, per_radius = bath_world(initial, initial - delta, temperature)
    prediction = per_radius * radius * 1000
    np.testing.assert_allclose(
        prediction, float(KB * NA) * temperature * delta * radius * 500, rtol=1e-12, atol=0
    )
    return dict(
        popc=popc_footprint(),
        rupture_holds=rupture_holds(),
        deflation=deflation,
        first_point_effective_mM=anchored,
        swelling=swelling,
        tension_mN_m=dict(
            fixed_sphere=prediction, measured=tension["estimated_osmotic_tension_mN_m"]
        ),
    )


def rupture_holds():
    data = json.loads((DATA / "vesicle_rupture_holds.json").read_text())
    osmotic = data["shibly2016_dopc_hold@1"]
    (_, early), (_, late) = osmotic["points"]
    loss = (early - late) / osmotic["vesicles"]
    return dict(
        isosmotic=[
            dict(
                temperature_C=row["temperature_C"],
                min_max_error_constant_fraction=(row["points"][0][1] - row["points"][-1][1]) / 2,
            )
            for row in data["karal2015_dopc_hold@1"]["series"]
        ],
        osmotic=dict(
            fraction_lost_from_initial_cohort=loss,
            fraction_lost_among_early_survivors=(early - late) / early,
            min_max_error_constant_fraction=loss / 2,
        ),
    )


def rupture_cases(controls_only):
    # At the founder the sole possible event removes one lipid. Examine precisely that event.
    exact = reference(Q, 4 * K_L, 4, 1000.0, 296.15, 1000.0)["tension_N_m"]
    thresholds = [0.99 * float(exact), 1.01 * float(exact)]
    if not controls_only:
        thresholds += [0.0008412963098275742, 0.0008412963098275802]
    outcome = []
    for limit in thresholds:
        for factor in (1, 32):
            raw = osmotic_world(
                L_pool=0,
                L_mem=5,
                S_pool=0,
                S_lumen=0,
                I_lumen=4,
                mu_bilayer=3.0,
                sigma_max=limit,
                floor=K_L,
            )
            refine(raw, factor)
            spec = spec_of(raw, horizon=100.0, event_limit=1, row_every=1)
            result = runner.run(spec).check()
            rows = result.rows
            assert result.closure["holds"] and int(rows["row_event"][-1]) == 1
            # The columns are join, entry and their two reverses.
            np.testing.assert_array_equal(rows["channel_fired"][-1], [0, 0, 1, 0])
            assert result.status in ("event_limit", "lysed")
            names = [p.name for p in spec.model.world.places]
            release = result.osmotic["lysis"]
            membrane = int(rows["place_count"][-1, names.index("L@membrane")])
            trapped = int(rows["place_count"][-1, names.index("I@lumen")])
            ruptured = result.status == "lysed"
            assert (membrane, trapped) == ((0, 0) if ruptured else (4, 4))
            sigma = release["sigma_N_per_m"] if ruptured else rows["tension_N_per_m"][-1]
            # The same area computed first gives a representation-independent binary64 comparison.
            a = (Q / factor) * (4 * K_L * factor) / 2
            r = math.sqrt(a / (4 * math.pi))
            vol = 4 * math.pi * r**3 / 3
            direct = float(KB) * 296.15 * r / 2 * max(0.0, 4 / vol - float(NA) * 1000)
            predicted_lysis = exact > Decimal.from_float(limit)
            assert (direct > limit) == predicted_lysis
            outcome.append(
                dict(
                    refinement=factor,
                    threshold_N_m=limit,
                    reference_tension_N_m=float(exact),
                    engine_recorded_tension_N_m=float(sigma),
                    direct_tension_N_m=direct,
                    predicted_lysis=predicted_lysis,
                    status=result.status,
                    membrane_lipids=membrane,
                    lumen_osmoles=trapped,
                    agrees=ruptured == predicted_lysis,
                )
            )
    return outcome


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="omit the two close lysis thresholds"
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    a, ta, one = trajectory(1)
    b, tb, refined = trajectory(32)
    np.testing.assert_array_equal(a, b)
    np.testing.assert_allclose(ta, tb, rtol=2e-12, atol=0)
    cases = rupture_cases(args.controls_only)
    result = dict(trajectories=[one, refined], biology=measurements(), rupture=cases)
    print(json.dumps(result, indent=2, allow_nan=False))
    return int(any(not case["agrees"] for case in cases))


if __name__ == "__main__":
    raise SystemExit(main())
