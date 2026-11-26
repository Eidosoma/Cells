"""Count-normalized Kv1.5 clamp currents and a two-endpoint density comparison."""

import json
from pathlib import Path

import jax
import jax.numpy as jnp
import numpy as np

from cells.definitions import pump_composite_spec, surface_pump_v3_spec
from cells.definitions.specs import ConfigError, parse_spec
from cells.models import surface_pump_v3
from cells.registry.models import get_model
from tests.unit import test_regulated_availability_population as population
from tests.unit.test_chloride_leak_law import chloride_world
from validation.fr7 import unit_turnover_fixtures
from validation.tissue.regulated_availability_fixtures import schedule_channel
from validation.tissue.surface_pump_v3_fixtures import channel


REFERENCE_PER_UM2 = 500.0
AREAS_UM2 = np.array([100.0, 160.0, 240.0])
VOLTAGES_V = np.array([-0.120, 0.060])


def density_route(density, half, maximum, *, self_source=False):
    """An actual composite density route, with its source and reporter named separately."""
    raw = unit_turnover_fixtures.cell()
    model = raw["model"]
    source = next(c for c in model["channels"] if c["id"] == population.SOURCE)
    source["abundance"] = density / REFERENCE_PER_UM2
    membrane = next(op for op in model["operators"] if op["law"] == unit_turnover_fixtures.STATE)
    source_units = next(p for p in membrane["populations"] if p["channel_id"] == population.SOURCE)
    source_units["reference_density_per_m2"] = 1e12 * REFERENCE_PER_UM2
    target = population.SOURCE if self_source else population.TARGET
    route = population.coupling(ids=(target,), law="hill_inhibition", basal=0.0,
                                half_saturation_per_um2=half, hill_coefficient=1.0)
    route["target"]["operating_range"] = [0.0, REFERENCE_PER_UM2]
    return parse_spec(schedule_channel(population.with_coupling(raw, [route]), target, maximum))


def reporter_availability(density, half, maximum):
    spec = density_route(density, half, maximum)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(row[0] for row in pump_composite_spec.control_values(spec, [0.0])))
    effective = model.control_view(control, state, layout, xp=np)
    slot = [c.id for c in spec.model.channels].index(population.TARGET)
    return float(effective.channel[slot])


def kv15_clamp(area_um2, density, availability):
    raw = chloride_world(patch=0.0)
    raw["model"]["membranes"][0]["area_m2"] = area_um2 * 1e-12
    raw["model"]["channels"] = [channel("kv", 0, "cells.channel.kv1p5_mh@1", "K", 4e-9,
                                        density / REFERENCE_PER_UM2, [0.65, 0.8])]
    raw["experiment"]["channel_controls"] = [
        dict(channel_id="kv", schedule=[dict(time=0.0, availability=availability)])
    ]
    raw["execution"]["channel_capacity"] = 1
    spec = parse_spec(raw)
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = model.Control(*(row[0] for row in surface_pump_v3_spec.control_values(spec, [0.0])))
    return state, control, layout


def normalized_currents(densities, fractions):
    if jax.default_backend() != "cpu" or not jax.config.x64_enabled:
        raise RuntimeError("Use JAX CPU with JAX_ENABLE_X64=1")
    compiled = jax.jit(jax.vmap(
        lambda v, s, c, p: surface_pump_v3.clamped_channel_flux(s, c, p, v, xp=jnp)[1][0],
        in_axes=(0, None, None, None),
    ))
    arms = {}
    for name, controls in (("constant", np.full_like(fractions, fractions[0])),
                           ("measured_controls", fractions)):
        numpy_rows, jax_rows = [], []
        for area, density, availability in zip(AREAS_UM2, densities, controls, strict=True):
            state, control, layout = kv15_clamp(area, density, availability)
            currents = [surface_pump_v3.clamped_channel_flux(state, control, layout, v, xp=np)[1][0]
                        for v in VOLTAGES_V]
            numpy_rows.append(currents)
            jax_rows.append(np.asarray(compiled(VOLTAGES_V, state, control, layout)))
        expected = controls / controls[0]
        by_backend = {}
        for backend, currents in (("numpy", numpy_rows), ("jax_cpu", jax_rows)):
            per_channel = np.asarray(currents) / (AREAS_UM2 * densities)[:, None]
            assert np.all(per_channel[0] != 0)
            ratios = per_channel / per_channel[0]
            np.testing.assert_allclose(ratios, np.broadcast_to(expected[:, None], ratios.shape),
                                       rtol=3e-14, atol=0)
            by_backend[backend] = ratios.tolist()
        arms[name] = by_backend
    return arms


def run():
    data = json.loads((Path(__file__).parent / "data/maverick2022_kv_density.json").read_text())
    data = data["maverick2022_kv_density"]
    low, high = data["kv15_density_series"]
    points = (low, data["kv15_middle"], high)
    densities = np.array([point["gating_channels_per_um2"] for point in points], dtype=float)
    fractions = np.array([point["conducting_fraction"] for point in points])
    x0, xm, x1 = densities
    f0, fm, f1 = fractions
    # Endpoints determine A and K in A*K/(K+x). The middle observation never enters the fit.
    half = (f1 * x1 - f0 * x0) / (f0 - f1)
    maximum = f0 * (1 + x0 / half)
    assert 0 < maximum <= 1 and half > 0
    routed = [reporter_availability(x, half, maximum) for x in densities]
    w = (xm - x0) / (x1 - x0)
    middle_prediction = 1 / ((1 - w) / f0 + w / f1)
    np.testing.assert_allclose(routed, [f0, middle_prediction, f1], rtol=3e-15)
    try:
        density_route(xm, half, maximum, self_source=True)
    except ConfigError as exc:
        if "own abundance onto its availability" not in str(exc):
            raise
    else:
        raise AssertionError("The declared own-density route was accepted; review D218")
    return {
        "density_per_um2": densities.tolist(), "figure_conducting_fraction": fractions.tolist(),
        "fit": {"half_saturation_per_um2": half, "scheduled_maximum": maximum,
                "hill_coefficient": 1, "basal": 0, "cross_population_availability": routed},
        "middle": {"reciprocal_interpolation": middle_prediction, "figure": fm,
                   "constant_from_low": f0, "prediction_minus_figure": routed[1] - fm},
        "self_density_route": "refused (D218)", "area_um2": AREAS_UM2.tolist(),
        "clamp_voltage_V": VOLTAGES_V.tolist(), "reference_channels_per_um2": REFERENCE_PER_UM2,
        "current_per_count_relative_to_low": normalized_currents(densities, fractions),
    }


if __name__ == "__main__":
    print(json.dumps(run(), indent=2, allow_nan=False))
