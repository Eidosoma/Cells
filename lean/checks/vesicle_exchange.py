"""Vesicle insertion, permeation and fixed-volume washout in cells.model.assembly_lineages@2."""

import json
import math
from functools import partial
from pathlib import Path

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.models.assembly_lineages_v2 import kernel, model, runner
from tests.assembly_lineage_v2_fixtures import definition
from tests.unit.test_assembly_lineages_v2_geometry import Q, lipid_world

NA = 6.02214076e23
DATA = Path(__file__).parent / "data" / "vesicle_exchange_measurements.json"


@partial(jax.jit, static_argnames=("structure",))
def device_rates(counts, layout, structure):
    totals = kernel.totals_of(counts, layout)
    factor, terms = kernel.states(counts, totals, layout, structure)
    return kernel.rates(counts, totals, factor, terms, layout, structure)


def channels(rates, spec):
    n = len(spec.model.world.steps)
    capacity = model.structure(spec).steps
    return np.concatenate((rates[:n], rates[capacity : capacity + n]))


def make_world(encounter, measure, held):
    raw = lipid_world(
        encounter=encounter,
        measure=measure,
        lumen=True,
        quanta={"L": 60, "P": 30},
        floor=120,
        k_join=2e-8 if encounter == "insertion_area" else 2e-18,
    )
    raw["steps"] = [step for step in raw["steps"] if step["id"] != "iso"]
    raw["steps"][1]["permeability_m_per_s"]["value"] = 1e-7
    if held:
        for place in raw["phases"]["pool"]["species"]:
            place.update(kind="held", held_mM={"L": 8.0, "S": 5.0}[place["id"]])
            del raw["founder"][place["id"] + "@pool"]
    return parse_spec(definition(raw, molecules=64, horizon=2000, event_limit=48, row_every=1))


def ideal_energy(world, counts):
    """Canonical ideal free energy from the finite-place partition weights, in k_BT."""
    total_membrane = 0
    contributions = []
    for place, n in zip(world.places, counts[: len(world.places)], strict=True):
        if place.held:
            continue
        if place.phase == "membrane":
            total_membrane += n
            mu = {"L": -2.0, "P": -2.5}[place.species]
        else:
            mu = -math.log(
                NA * world.volume(place.phase) * world.units.standard_concentration_mM / 1000
            )
        contributions.append(n * mu + math.lgamma(n + 1))
    contributions.append(-math.lgamma(total_membrane - world.conventions.offset + 1))
    return math.fsum(contributions)


def expected_rates(world, counts):
    """Four directional hazards in molecules/s, from lengths, volumes and molecule counts."""

    def get(place):
        return int(counts[world.place_index(place)])

    pool_volume = world.volume("pool") * 1e-3  # litres to m³
    density = {
        p.species: p.held_mM * NA if p.held else get(p.name) / pool_volume
        for p in world.places
        if p.phase == "pool"
    }
    lipid, other = get("L@membrane"), get("P@membrane")
    footprint = 60 * lipid + 30 * other
    join, entry = world.steps

    def encounter(w):
        area = Q * w / 2
        if join.rate_key == "diffusivity_m2_per_s":
            return 4 * math.pi * math.sqrt(area / (4 * math.pi))
        return area

    join_rate = (
        join.forward_rate_per_s * encounter(footprint) * density["L"] if footprint >= 120 else 0.0
    )
    leave = 0.0
    if lipid and footprint - 60 >= 120:
        mole_fraction = lipid / (lipid + other - world.conventions.offset)
        reference_density = NA * world.units.standard_concentration_mM
        leave = (
            join.forward_rate_per_s
            * encounter(footprint - 60)
            * reference_density
            * math.exp(-2.0)
            * mole_fraction
        )
    pa = entry.forward_rate_per_s * (Q * footprint / 2)
    return np.array(
        [join_rate, pa * density["S"], leave, pa * get("S@lumen") / (world.volume("lumen") * 1e-3)]
    )


def edge_comparisons(spec):
    world, layout, structure = spec.model.world, model.layout(spec), model.structure(spec)
    error = balance_error = 0.0
    pairs = blocked = 0
    # Include a fourfold area change, an empty donor, the floor, and a state below the floor.
    states = [(4, 2, 6, 4, 2), (16, 8, 6, 4, 2), (2, 0, 6, 4, 1), (0, 2, 6, 4, 1), (4, 2, 0, 0, 0)]
    first_rates = []
    for lipid, other, outside_l, outside_s, inside in states:
        counts = model.founder(spec).copy()
        for name, value in zip(
            ("L@membrane", "P@membrane", "L@pool", "S@pool", "S@lumen"),
            (lipid, other, outside_l, outside_s, inside),
            strict=True,
        ):
            i = world.place_index(name)
            if not world.places[i].held:
                counts[i] = value
        rates = channels(device_rates(counts, layout, structure), spec)
        expected = expected_rates(world, counts)
        active = expected > 0
        blocked += int((~active).sum())
        np.testing.assert_array_equal(rates[~active], 0)
        np.testing.assert_allclose(rates[active], expected[active], rtol=2e-13, atol=0)
        error = max(error, float(np.max(np.abs(rates[active] / expected[active] - 1))))
        first_rates.append(rates[:2])
        for step, (donor, recipient) in enumerate(
            (("L@pool", "L@membrane"), ("S@pool", "S@lumen"))
        ):
            if not active[step]:
                continue
            after = counts.copy()
            i = world.place_index(donor)
            p = world.places[i]
            work = math.log(p.held_mM / world.units.standard_concentration_mM) if p.held else 0.0
            if not p.held:
                after[i] -= 1
            after[world.place_index(recipient)] += 1
            reverse = channels(device_rates(after, layout, structure), spec)[2 + step]
            residual = (
                math.log(rates[step] / reverse)
                + ideal_energy(world, after)
                - ideal_energy(world, counts)
                - work
            )
            assert abs(residual) < 2e-13
            balance_error = max(balance_error, abs(residual))
            pairs += 1
    ratio = first_rates[1] / first_rates[0]
    np.testing.assert_allclose(
        ratio,
        [4 if world.steps[0].rate_key == "insertion_velocity_m_per_s" else 2, 4],
        rtol=2e-13,
        atol=0,
    )
    return dict(
        active_pairs=pairs,
        blocked_directions=blocked,
        max_rate_relative_error=error,
        max_balance_error_kT=balance_error,
        double_radius_forward_ratio=ratio.tolist(),
    )


def finite_trajectory(spec):
    run = runner.run(spec).check()
    assert run.closure["holds"]
    world = spec.model.world
    counts, fired = run.rows["place_count"], run.rows["channel_fired"]
    # Channel records are cumulative, with a column for each forward and then each reverse.
    net = fired[:, :2] - fired[:, 2:]
    for step, (donor, recipient) in enumerate((("L@pool", "L@membrane"), ("S@pool", "S@lumen"))):
        np.testing.assert_array_equal(
            counts[:, world.place_index(donor)], counts[0, world.place_index(donor)] - net[:, step]
        )
        np.testing.assert_array_equal(
            counts[:, world.place_index(recipient)],
            counts[0, world.place_index(recipient)] + net[:, step],
        )
    assert np.all(np.diff(fired, axis=0).sum(axis=1) <= 1)
    assert (fired[-1] > 0).all(), fired[-1]
    return dict(
        events_by_direction=fired[-1].tolist(),
        rows=len(counts),
        max_closure_residual_kT=float(np.max(np.abs(run.rows["ledger_residual_kT"]))),
    )


def assay_world(radius_m, permeability, temperature_K, bath_mol_L):
    """Fix measured geometry exactly by choosing an integer lipid count and its area quantum."""
    area = 4 * math.pi * radius_m**2
    n_lipid = round(2 * area / 0.65e-18)
    raw = lipid_world(lumen=True)
    raw["steps"] = [next(step for step in raw["steps"] if step["id"] == "entry")]
    raw["steps"][0]["permeability_m_per_s"] = dict(value=permeability, provenance="comparison")
    raw["units"]["temperature_K"] = temperature_K
    raw["geometry"]["area_quantum_m2"] = 2 * area / n_lipid
    raw["geometry"]["area_per_leaflet"] = {
        s: dict(quanta=1, provenance="assigned area") for s in ("L", "P")
    }
    raw["geometry"]["vesicle_floor"]["quanta"] = 1
    raw["phases"]["lumen"]["volume_L"] = 4 * math.pi * radius_m**3 / 3 * 1000
    raw["founder"].update(
        {
            "L@pool": 0,
            "L@membrane": 0,
            "P@membrane": n_lipid,
            "S@pool": 8 if bath_mol_L else 0,
            "S@lumen": 0,
        }
    )
    if bath_mol_L:
        raw["phases"]["pool"]["volume_L"] = 8 / (NA * bath_mol_L)
    return parse_spec(definition(raw, molecules=n_lipid + 16))


def glycerol_washout(data):
    radii = [
        (data[k]["outer_diameter_nm"] / 2 - data["bilayer_thickness_nm"]) * 1e-9
        for k in ("calibration", "evaluation")
    ]
    permeability = data["calibration"]["rate_per_s"] * radii[0] / 3
    rows = []
    for r in radii:
        spec = assay_world(r, permeability, 273.15 + data["temperature_C"], 0)
        counts = model.founder(spec)
        layout, structure = model.layout(spec), model.structure(spec)
        slopes = []
        for n in (1, 7, 14):
            counts[spec.model.world.place_index("S@lumen")] = n
            inward, outward = channels(device_rates(counts, layout, structure), spec)
            assert inward == 0
            slopes.append(outward / n)
        np.testing.assert_allclose(slopes, 3 * permeability / r, rtol=2e-13, atol=0)
        rows.append(dict(inner_radius_nm=r * 1e9, exit_per_molecule_s=slopes[0]))
    return dict(
        permeability_m_s=permeability,
        sizes=rows,
        measured_held_out_s=data["evaluation"]["rate_per_s"],
    )


def urea_uptake(data):
    start, end = data["window_s_after_radius_minimum"]
    error = data["radius_reading_allowance_um"]

    def uptake(a, b):
        # A cubic micrometre is 1e-15 L. Converting mol to fmol cancels that factor.
        return data["bath_mol_L"] * (4 * math.pi / 3) * (b**3 - a**3) / (end - start)

    rows, forward = [], []
    for row in data["traces"]:
        a, b = row["start_um"], row["end_um"]
        # A common 1:1000 length scale fits the compiled count capacity and preserves area ratios.
        # The arbitrary common permeability and synthetic temperature drop out of the ratio.
        r = row["radius_min_um"] * 1e-9
        spec = assay_world(r, 1e-8, 296.15, data["bath_mol_L"])
        rates = device_rates(model.founder(spec), model.layout(spec), model.structure(spec))
        forward.append(channels(rates, spec)[0])
        rows.append(
            dict(
                curve=row["curve"],
                estimated_fmol_s=uptake(a, b),
                figure_reading_range_fmol_s=[
                    uptake(a + error, b - error),
                    uptake(a - error, b + error),
                ],
            )
        )
    smallest = min(range(len(rows)), key=lambda i: data["traces"][i]["radius_min_um"])
    for i, row in enumerate(rows):
        row["uptake_ratio_to_smallest"] = (
            row["estimated_fmol_s"] / rows[smallest]["estimated_fmol_s"]
        )
        row["engine_area_ratio"] = forward[i] / forward[smallest]
        geometric = (
            data["traces"][i]["radius_min_um"] / data["traces"][smallest]["radius_min_um"]
        ) ** 2
        np.testing.assert_allclose(row["engine_area_ratio"], geometric, rtol=2e-13, atol=0)
    return rows


def main():
    data = json.loads(DATA.read_text())
    edges, trajectories = {}, {}
    for encounter in ("insertion_area", "diffusion_radius"):
        for measure in ("multinomial", "multinomial_less_one"):
            for held in (False, True):
                spec = make_world(encounter, measure, held)
                edges[f"{encounter}/{measure}/{'held' if held else 'finite'}"] = edge_comparisons(
                    spec
                )
                if measure == "multinomial" and not held:
                    trajectories[encounter] = finite_trajectory(spec)
    print(
        json.dumps(
            dict(
                edges=edges,
                trajectories=trajectories,
                glycerol=glycerol_washout(data["branden2010"]),
                urea=urea_uptake(data["peterlin2012"]),
            ),
            indent=2,
            allow_nan=False,
        )
    )


if __name__ == "__main__":
    main()
