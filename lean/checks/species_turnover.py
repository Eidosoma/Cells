"""Neutral-pool turnover and gross bookings, neuronal tracer chase and chamber gas recovery."""

import argparse
import json
import math
from itertools import product
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.operators.species_turnover import produced_cleared
from validation.core_seams.references import exact
from validation.tissue import secreted_species_fixtures as fixture


def endpoint(n, production, clearance, h):
    """Closed form about the equilibrium, independent of the two engine bookings."""
    n, production, clearance, h = map(exact.dec, (n, production, clearance, h))
    if clearance == 0:
        return n + production * h
    equilibrium = production / clearance
    return equilibrium + (n - equilibrium) * (-clearance * h).exp()


def component_panel():
    rows = list(
        product(
            (2**-10, 1.0, 8.0), (0.0, 0.25, 1.0, 4.0), (0.0, 0.125, 1.0, 4.0), (1 / 16, 0.5, 2.0)
        )
    )
    n, specific_production, k, h = np.array(rows).T
    p = n * specific_production
    with exact.context():
        endpoints = [endpoint(*args) for args in zip(n, p, k, h, strict=True)]
        gross = [exact.dec(pi) * exact.dec(hi) for pi, hi in zip(p, h, strict=True)]
        losses = [
            exact.dec(ni) + gain - end for ni, gain, end in zip(n, gross, endpoints, strict=True)
        ]
    reference = np.array([endpoints, gross, losses], dtype=np.float64)
    compiled = jax.jit(lambda n, p, k, h: produced_cleared(n, p, k, h, xp=jnp))
    result = {}
    for name, bookings in (
        ("numpy", produced_cleared(n, p, k, h, xp=np)),
        ("compiled_cpu", compiled(n, p, k, h)),
    ):
        made, lost = map(np.asarray, bookings)
        after = n + (made - lost)
        assert made.dtype == lost.dtype == np.float64
        assert np.all(made >= 0) and np.all(lost >= 0) and np.all(after > 0)
        scale = np.maximum(n, reference[1])
        err = float(np.max(np.abs(np.array([after, made, lost]) - reference) / scale))
        assert err < 8 * exact.EPS
        result[name] = dict(cases=len(n), max_error_over_start_or_production=err)
    return result


def scheduled_world(dt):
    # Each half-second phase gives cell production, two cell clearances and outside clearance.
    phases = [
        (0.375, 0.125, 0.25, 0.5),
        (0.875, 0.0, 0.0, 0.0),
        (0.0, 0.25, 0.5, 0.25),
        (0.25, 0.25, 0.25, 0.75),
    ]
    routes = [
        ("make", "cell_0", "production"),
        ("clear_a", "cell_0", "clearance"),
        ("clear_b", "cell_0", "clearance"),
        ("outside", "ecs_0", "clearance"),
    ]
    schedules = [
        (
            rid,
            "cell_0" if node == "cell_0" else None,
            [(0.5 * i, rates[j]) for i, rates in enumerate(phases)],
        )
        for j, (rid, node, _) in enumerate(routes)
    ]
    raw = fixture.face_free(pool_mM=1.0, node_mM=0.5, dt=dt, end=2.0)
    spec = parse_spec(fixture.with_turnover(raw, routes, schedules))
    result = run(spec)
    hist = result.history
    row = list(spec.model.species_ids).index(fixture.SPECIES)
    outside = next(
        i for i, node in enumerate(raw["model"]["extracellular"]) if node["id"] == "ecs_0"
    )
    actual = np.column_stack(
        (
            1.0 + hist.amount_increment[:, row, 0],
            0.5 + hist.extracellular_amount_increment[:, row, outside],
            hist.turnover_produced_fmol[:, row, 0],
            hist.turnover_cleared_fmol[:, row, 0],
            hist.turnover_outside_cleared_fmol[:, row, outside],
            hist.turnover_work_pJ[:, 0],
            hist.turnover_outside_work_pJ[:, outside],
        )
    )
    with exact.context():
        cell0, outside0 = exact.dec(1), exact.dec(0.5)
        cell, ext, made = cell0, outside0, exact.dec(0)
        rt = exact.RT_J_per_mol(raw["model"]["temperature_K"]) * exact.dec("0.001")

        def energy(n):
            # Both fixture volumes are 1 pL. n / (1 pL) is in mM.
            return rt * n * (n.ln() - 1)

        reference = []
        for step, t in enumerate(result.times):
            if step:
                p, k_a, k_b, k_out = phases[int(result.times[step - 1] / 0.5)]
                h = exact.dec(t) - exact.dec(result.times[step - 1])
                cell = endpoint(cell, p, k_a + k_b, h)
                ext = endpoint(ext, 0, k_out, h)
                made += exact.dec(p) * h
            reference.append(
                [
                    cell,
                    ext,
                    made,
                    cell0 + made - cell,
                    outside0 - ext,
                    energy(cell) - energy(cell0),
                    energy(ext) - energy(outside0),
                ]
            )
    errors = np.max(np.abs(actual - np.asarray(reference, dtype=np.float64)), axis=0)
    assert np.all(errors[:5] < 16 * exact.EPS) and np.all(errors[5:] < 32 * exact.EPS)
    balance = actual[int(0.5 / dt)]
    np.testing.assert_allclose(
        balance[[0, 2, 3]], [1.0, 0.1875, 0.1875], rtol=8 * exact.EPS, atol=0
    )
    return dict(
        dt_s=dt,
        stored_rows=len(result.times),
        steady_cell_fmol=balance[0],
        steady_produced_fmol=balance[2],
        steady_cleared_fmol=balance[3],
        final_cell_fmol=actual[-1, 0],
        final_outside_fmol=actual[-1, 1],
        max_amount_or_booking_error_fmol=max(errors[:5]),
        max_work_error_pJ=max(errors[5:]),
    )


def stiff_world(k):
    """The target is 2 fmol, one fmol above the starting pool at both rates."""
    raw = fixture.face_free(pool_mM=1.0, node_mM=0.5, dt=1.0, end=1.0)
    p = 2 * k
    routes = [("make", "cell_0", "production"), ("clear", "cell_0", "clearance")]
    controls = [("make", "cell_0", [(0.0, p)]), ("clear", "cell_0", [(0.0, k)])]
    spec = parse_spec(fixture.with_turnover(raw, routes, controls))
    row = list(spec.model.species_ids).index(fixture.SPECIES)
    with exact.context():
        ref = endpoint(1, p, k, 1)
        rt = exact.RT_J_per_mol(raw["model"]["temperature_K"]) * exact.dec("0.001")
        expected_work = float(rt * (ref * (ref.ln() - 1) + 1))
    # Direct net update from the Lean identity over the same two half-steps.
    direct = 1.0
    for _ in range(2):
        direct += (p / k - direct) * -np.expm1(-k * 0.5)
    assert abs(direct - float(ref)) <= 4 * exact.EPS
    case = dict(
        clearance_per_s=k,
        production_fmol_per_s=p,
        expected_fmol=float(ref),
        direct_net_fmol=direct,
        expected_work_pJ=expected_work,
    )
    try:
        hist = run(spec).history
    except NumericalError as exc:
        return dict(case, admitted=False, consistent=False, reason=str(exc))
    after = float(1 + hist.amount_increment[-1, row, 0])
    booked_work = float(hist.turnover_work_pJ[-1, 0])
    return dict(
        case,
        admitted=True,
        stored_fmol=after,
        produced_fmol=float(hist.turnover_produced_fmol[-1, row, 0]),
        cleared_fmol=float(hist.turnover_cleared_fmol[-1, row, 0]),
        booked_work_pJ=booked_work,
        consistent=abs(after - float(ref)) <= 8 * exact.EPS
        and abs(booked_work - expected_work) <= 16 * exact.EPS,
    )


def pulse_chase():
    data = json.loads((Path(__file__).parent / "data/dorrbaum2018_protein_chase.json").read_text())
    result = {}
    for protein, series in data["series"].items():
        means = {r["day"]: r["sum"] / r["cells"] for r in series["chase"]}
        t0, t1 = data["fit_days"]
        fits = {}
        for name, bg in (
            ("raw", 0.0),
            ("measured_background", series["background"]["sum"] / series["background"]["cells"]),
        ):
            k = math.log((means[t0] - bg) / (means[t1] - bg)) / (t1 - t0)
            points = []
            for r in series["chase"]:
                day = r["day"]
                if day in data["fit_days"]:
                    continue
                # Track a normalized pulse-labeled cohort with zero new labeled input.
                # Convert days to seconds for the engine, then map its retained fraction to signal.
                _, removed = produced_cleared(1.0, 0.0, k / 86400, (day - t0) * 86400, xp=np)
                predicted = bg + (means[t0] - bg) * (1.0 - removed)
                sd = math.sqrt((r["sum_squares"] - r["cells"] * means[day] ** 2) / (r["cells"] - 1))
                points.append(
                    dict(day=day, cells=r["cells"], observed=means[day], sd=sd, predicted=predicted)
                )
            fits[name] = dict(background=bg, clearance_per_day=k, held_out=points)
        result[protein] = fits
    return result


def chamber_recovery():
    """Apply the same linear law to CO2 volume fraction in a fixed-volume mixing chamber."""
    data = json.loads((Path(__file__).parent / "data/lizana2023_chamber_recovery.json").read_text())
    volume = data["chamber_volume_L"]
    exhaust = data["exhaust_L_per_min"]
    injection = data["injected_mixture_L_per_min"]
    ambient = data["ambient_CO2_fraction"]
    clearance = exhaust / volume / 60
    supply_on = (
        (injection * data["injected_CO2_fraction"] + (exhaust - injection) * ambient) / volume / 60
    )
    supply_off = exhaust * ambient / volume / 60
    switch = data["injection_end_min"]
    points = []
    for row in data["observations"]:
        times = np.asarray(row["time_min"])
        added, removed = produced_cleared(
            ambient, supply_on, clearance, 60 * np.minimum(times, switch), xp=np
        )
        fraction = ambient + (added - removed)
        added, removed = produced_cleared(
            fraction, supply_off, clearance, 60 * np.maximum(times - switch, 0), xp=np
        )
        predicted = 100 * (fraction + (added - removed))
        observed = np.asarray(row["outlet_CO2_vol_percent"])
        points.append(
            dict(
                nominal_min=row["nominal_min"],
                observed_mean_vol_percent=observed.mean(),
                observed_sd_vol_percent=observed.std(ddof=1),
                predicted_mean_vol_percent=predicted.mean(),
            )
        )
    return dict(clearance_per_min=clearance * 60, held_out=points)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controls-only", action="store_true", help="omit the extreme-rate worlds")
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    with jax.default_device(jax.devices("cpu")[0]):
        results = dict(
            components=component_panel(),
            schedules=[scheduled_world(dt) for dt in (0.25, 0.125)],
            biology=pulse_chase(),
            physical_calibration=chamber_recovery(),
        )
        if not args.controls_only:
            results["extreme_rates"] = [stiff_world(float(2**i)) for i in (53, 54)]
        print(json.dumps(results, indent=2, allow_nan=False))
        raise SystemExit(int(any(not r["consistent"] for r in results.get("extreme_rates", []))))
