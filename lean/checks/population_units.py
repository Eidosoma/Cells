"""Follow precursor molecules through maturation, surface abundance and channel flow."""

import argparse
import json
import math
from decimal import Decimal
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec as composite
from cells.definitions.specs import parse_spec
from cells.execution.runner import run
from cells.operators import membrane_state
from cells.registry.models import get_model
from tests.unit.test_population_unit_turnover import reference
from validation.fr7 import unit_turnover_fixtures as fx

DT = 1 / 1024
END = 8 * DT
MOLECULES_PER_FMOL = Decimal("602214076")


def bound(raw):
    spec = parse_spec(raw)
    model = get_model(spec.model)
    initial, layout = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in composite.control_values(spec, [0.0])))
    return spec, model, initial, control, layout


def shared_precursor():
    routes = [
        fx.route("direct", "kir_0", nu=2),
        fx.route("maturing", fx.SECOND, nu=7, pools=3, tau=3 / 50, initial=[70.0, 20.0, 5.0]),
    ]
    controls = {"direct": [(0.0, 12.0, 9.0)], "maturing": [(0.0, 20.0, 17.0)]}
    raw = fx.with_producer(fx.cell(dt=DT, end=END), routes, controls)
    spec, _, initial, _, params = bound(raw)
    result = run(spec)
    row = spec.model.species_ids.index(fx.PRECURSOR)
    n0 = float(params.amount_reference[row, 0])
    channels = [c.id for c in spec.model.channels]
    route_channels = [channels.index(route["population"]) for route in routes]
    declared = np.asarray(membrane_state.units(initial, params, xp=np))[route_channels]
    reference_routes = []
    for route, units in zip(routes, declared, strict=True):
        _, assembly, removal = controls[route["id"]][0]
        pools = route["initial_pool_units"]
        rate = len(pools) / route["maturation_time_s"] if pools else 0.0
        reference_routes.append(
            (
                assembly,
                MOLECULES_PER_FMOL / route["molecules_per_unit"],
                rate,
                pools,
                float(units),
                removal,
            )
        )

    max_units_error = max_amount_error = max_inventory_error = 0.0
    for k, t in enumerate(result.times):
        state = type(result.history)(*(field[k] for field in result.history))
        n_ref, route_ref = reference(n0, reference_routes, float(t))
        n = n0 + float(state.amount_increment[row, 0])
        np.testing.assert_allclose(n, float(n_ref), rtol=0, atol=2e-19)
        max_amount_error = max(max_amount_error, abs(n - float(n_ref)))
        units = membrane_state.units(state, params, xp=np)
        for i, (c, route) in enumerate(zip(route_channels, routes, strict=True)):
            taken, transit, surface, removed = route_ref[i]
            consumed = float(state.unit_consumed_fmol[i])
            np.testing.assert_allclose(consumed, float(taken), rtol=0, atol=2e-19)
            max_amount_error = max(max_amount_error, abs(consumed - float(taken)))
            pools = np.asarray(state.unit_pool_units[i, : len(transit)])
            assembled = MOLECULES_PER_FMOL * taken / route["molecules_per_unit"]
            inserted = surface - Decimal(float(declared[i])) + removed
            expected = np.array([*transit, surface, removed, assembled, inserted], dtype=float)
            got = np.array(
                [
                    *pools,
                    units[c],
                    state.unit_removed_units[c],
                    state.unit_assembled_units[i],
                    state.unit_inserted_units[c],
                ]
            )
            np.testing.assert_allclose(got, expected, rtol=0, atol=2e-10)
            max_units_error = max(max_units_error, max(abs(got - expected)))
            net = math.fsum(
                [
                    *pools,
                    units[c],
                    state.unit_removed_units[c],
                    -declared[i],
                    -sum(route["initial_pool_units"]),
                ]
            )
            inventory_error = (
                net * route["molecules_per_unit"] - float(MOLECULES_PER_FMOL) * consumed
            )
            assert abs(inventory_error) <= 2e-9
            max_inventory_error = max(max_inventory_error, abs(inventory_error))
    taken = np.asarray(result.final.state.unit_consumed_fmol)
    np.testing.assert_allclose(taken[0] / taken[1], 12 / 20, rtol=2e-15)
    return dict(
        checked_steps=len(result.times) - 1,
        route_consumption_fmol=taken.tolist(),
        max_amount_error_fmol=max_amount_error,
        max_chain_error_units=max_units_error,
        max_inventory_error_molecules=max_inventory_error,
    )


def pulse():
    units, rate, duration = 120.0, 40.0, 0.0125
    route = fx.route("pulse", "kir_0", pools=2, tau=2 / rate, initial=[units, 0.0])
    raw = fx.with_producer(fx.cell(dt=DT, end=END), [route], {"pulse": [(0.0, 0.0, 0.0)]})
    _, model, initial, control, p = bound(raw)
    op = model.operators[-1]
    state, ok = jax.device_get(
        jax.jit(lambda s, t, c, p: op.half_step(s, t, c, p, xp=jnp))(initial, duration, control, p)
    )
    assert ok
    x = rate * duration
    expected = [
        units * math.exp(-x),
        units * x * math.exp(-x),
        units * (1 - (1 + x) * math.exp(-x)),
    ]
    got = [*state.unit_pool_units[0], state.unit_inserted_units[0]]
    np.testing.assert_allclose(got, expected, atol=2e-13, rtol=0)
    np.testing.assert_array_equal(state.unit_consumed_fmol, 0.0)
    return dict(
        elapsed_s=duration,
        starting_units=units,
        first_pool=got[0],
        second_pool=got[1],
        inserted=got[2],
    )


def surface():
    raw = fx.cell(dt=DT, end=END)
    # Powers of two make the two declared counts exactly 3072 and 1536 on both backends.
    raw["model"]["membranes"][0]["area_m2"] = 2.0**-32
    for row in raw["model"]["operators"][0]["populations"]:
        row["reference_density_per_m2"] = 3.0 * 2**42
    spec, model, initial, control, p = bound(raw)
    potassium = spec.model.species_ids.index("K")
    counts = np.asarray(membrane_state.units(initial, p, xp=np))
    np.testing.assert_array_equal(counts, [3072.0, 1536.0])

    def read(s, c, p, xp):
        q = model.view(p, s, xp=xp)
        readout = model.readouts(s, c, p, xp=xp)
        return (
            membrane_state.units(s, p, xp=xp),
            q.channel_abundance,
            readout.ionic.channel_flux_fmol_s[potassium],
            readout.valid,
        )

    compiled = jax.jit(lambda s, c, p: read(s, c, p, jnp))
    empty = []
    max_flow_error = 0.0
    for backend, evaluate in (("numpy", lambda s, c, p: read(s, c, p, np)), ("jax_cpu", compiled)):
        base = np.asarray(evaluate(initial, control, p)[2])
        assert np.all(base > 0)
        for area in (1.0, 1.4, 1.8):
            for fraction in (1.0, 0.5, 0.0):
                state = initial._replace(
                    membrane_area_increment_m2=p.membrane_area * (area - 1),
                    population_abundance_increment=counts * (fraction - 1),
                )
                actual, abundance, flux, valid = jax.device_get(evaluate(state, control, p))
                assert valid
                np.testing.assert_array_equal(actual, counts * fraction)
                if fraction:
                    np.testing.assert_allclose(flux, base * fraction, rtol=8e-15, atol=0)
                    max_flow_error = max(max_flow_error, max(abs(flux / (base * fraction) - 1)))
                else:
                    empty.append(
                        dict(
                            backend=backend,
                            area_ratio=area,
                            first_units=float(actual[0]),
                            first_abundance=float(abundance[0]),
                            first_K_flux_fmol_s=float(flux[0]),
                            all_zero=bool(np.all(abundance == 0) and np.all(flux == 0)),
                        )
                    )
    return dict(declared_units=counts.tolist(), max_relative_flow_error=max_flow_error, empty=empty)


def physiology(data):
    cohort = data["strack2011_innervated_cohort@1"]
    (t0, anchor, *_), (t1, measured, *_) = cohort["fit"]
    rate_day = -math.log(measured / anchor) / (t1 - t0)
    day = 86400.0
    route = fx.route("cohort", "kir_0")
    raw = fx.with_producer(
        fx.cell(dt=DT, end=END), [route], {"cohort": [(0.0, 0.0, rate_day / day)]}
    )
    _, model, state, control, p = bound(raw)
    n0 = membrane_state.units(state, p, xp=np)[0]
    op = model.operators[-1]
    advance = jax.jit(lambda s, c, p: op.half_step(s, day, c, p, xp=jnp))
    readings = {t: (obs, lo, hi) for t, obs, lo, hi in cohort["evaluation"]}
    predictions = []
    for elapsed in range(1, max(readings) + 1):
        state, ok = advance(state, control, p)
        assert ok
        pct = float(100 * membrane_state.units(state, p, xp=np)[0] / n0)
        np.testing.assert_allclose(pct, anchor * math.exp(-rate_day * elapsed), rtol=5e-15)
        if elapsed in readings:
            obs, lo, hi = readings[elapsed]
            predictions.append(
                dict(
                    elapsed_days=elapsed,
                    predicted_percent=pct,
                    observed_percent=obs,
                    plotted_bar=[lo, hi],
                )
            )

    land = data["land1980_receptor_sites_and_current@1"]
    ((ref_sites, _, ref_current, _),) = land["fit"]
    amplitude = [
        dict(
            sites_per_um2=sites,
            predicted_nA=ref_current * sites / ref_sites,
            observed_nA=obs,
            error_nA=err,
        )
        for sites, _, obs, err in land["evaluation"]
    ]
    return dict(loss_rate_per_day=rate_day, cohort=predictions, current=amplitude)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--require-empty",
        action="store_true",
        help="check only that zero surface units give exactly zero abundance and flux",
    )
    args = parser.parse_args()
    assert jax.config.x64_enabled and jax.default_backend() == "cpu"
    report = {"surface": surface()}
    if not args.require_empty:
        measurements = Path(__file__).with_name("data") / "surface_population_measurements.json"
        report.update(
            shared=shared_precursor(),
            pulse=pulse(),
            physiology=physiology(json.loads(measurements.read_text())),
        )
    print(json.dumps(report, indent=2, allow_nan=False))
    if args.require_empty and not all(r["all_zero"] for r in report["surface"]["empty"]):
        raise SystemExit("empty surface population has residual abundance or channel flux")
