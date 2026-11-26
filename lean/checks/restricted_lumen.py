"""Restricted-cleft geometry, dilution and mixing heat in compiled tissue worlds."""

import argparse
import json
from decimal import Decimal, localcontext
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import jax
import numpy as np

from cells.definitions.specs import parse_spec
from cells.execution.errors import NumericalError
from cells.execution.runner import run
from cells.laws.electrochemistry import R
from cells.operators import restricted_lumen as lumen
from cells.registry.inventory_species import add_inventory_species
from tests import membrane_insertion_fixtures as insertion
from tests import partition_fixtures as partition

DT = insertion.DT
ONSET = DT
DIVISION = 3 * DT
RATE = 2e-9  # m²/s, summed over the facing patches.
WIDTH = 2e-6  # m
INITIAL_VOLUME = 0.01  # pL
TIMES = [i * DT for i in range(7)]


def world(version, old, bath, *, divided=False):
    if divided:
        assert version == 2
        raw = partition.cleft_divided(
            f=0.6, area_fraction=0.6, rate=RATE, end=TIMES[-1], at=DIVISION, onset=ONSET
        )
    else:
        base = insertion.cleft_cell(end=TIMES[-1])
        raw = insertion.with_operators(base, insertion.furrow_insertion(rate=RATE, onset=ONSET))
        raw["model"]["operators"][1]["law"] = (
            f"cells.operator.scheduled_membrane_insertion@{version}"
        )
        raw["model"]["operators"].append(
            dict(
                law=f"cells.operator.restricted_cleft_lumen@{version}",
                lumens=[dict(node_id="cleft", source_id="bath_0", gap_width_m=WIDTH)],
            )
        )
    raw["experiment"]["observation_times"] = TIMES
    raw["experiment"]["pump_controls"] = []
    for row in raw["experiment"]["channel_controls"]:
        for value in row["schedule"]:
            value["availability"] = 0.0
    for membrane in raw["model"]["membranes"]:
        membrane["pump"] = None
        for species in membrane["permeability_m_per_s"]:
            membrane["permeability_m_per_s"][species] = 0.0
    raw = add_inventory_species(
        raw,
        "Tracer",
        trace_mM=1.0,
        concentrations_mM={"cleft": old, "bath_0": bath},
        diffusivity_m2_per_s=1e-10,
        floor_fmol=1e-22,
    )
    for face in raw["model"]["faces"]:
        for species in face["diffusivity_m2_per_s"]:
            face["diffusivity_m2_per_s"][species] = 0.0
    return parse_spec(raw)


def reference_heat(volume, delta, old, bath, temperature):
    """Endpoint ideal-solution energies in pJ for one species, from the binary64 inputs."""
    with localcontext() as ctx:
        ctx.prec = 75
        v, d, c, b, t, gas = map(
            Decimal.from_float, map(float, (volume, delta, old, bath, temperature, R))
        )
        n = v * c + d * b
        mixed = n / (v + d)
        return float(gas * t / 1000 * (v * c * c.ln() + d * b * b.ln() - n * mixed.ln()))


def morphometry():
    data = json.loads((Path(__file__).parent / "data" / "cleft_measurements.json").read_text())[
        "spring1979"
    ]
    area = data["lateral_area_per_cell_um2"]
    volume = data["assigned_interspace_volume_per_cell_um3"]
    per_length = data["control_interspace_volume_per_border_length_um3_per_um"]
    # Both use the same optical reconstructions. These calibrate a shared planar space.
    return dict(
        area_volume_width_um=2 * volume / area, section_width_um=per_length / data["height_um"]
    )


def check_run(spec, old, bath, divided=False):
    result = run(spec)
    hist, obs = result.history, result.observations
    outside = [node.id for node in spec.model.extracellular]
    cleft, source = outside.index("cleft"), outside.index("bath_0")
    tracer = spec.model.species_ids.index("Tracer")
    temperature = spec.model.temperature_K
    rt = 1e-3 * R * temperature
    bath_node = spec.model.extracellular[source]
    composition = np.asarray(bath_node.initial_amount_fmol) / bath_node.volume_pL
    time = np.asarray(result.times)
    np.testing.assert_array_equal(time, obs.times)
    np.testing.assert_allclose(time, TIMES, rtol=0, atol=1e-17)
    area = RATE * np.maximum(0.0, time - ONSET)
    volume = 0.5e15 * WIDTH * area
    # At a saved row the final half-step of membrane growth awaits its next booked fill.
    booked = 0.5e15 * WIDTH * np.maximum(0.0, area - RATE * DT / 2)
    opened = time > ONSET
    observed_volume = np.asarray(obs.lumen_volume_pL)[:, cleft]
    expected_volume = np.where(opened, INITIAL_VOLUME + volume, 0.0)
    np.testing.assert_allclose(observed_volume, expected_volume, rtol=2e-14, atol=0)
    np.testing.assert_allclose(hist.lumen_volume_increment_pL[:, cleft], booked, rtol=2e-14, atol=0)
    supplied = np.asarray(hist.lumen_supplied_fmol)[:, :, cleft]
    np.testing.assert_allclose(supplied, booked[:, None] * composition, rtol=2e-14, atol=0)
    reservoir_tracer = np.asarray(hist.reservoir_supplied)[:, tracer, source]
    np.testing.assert_allclose(reservoir_tracer, bath * booked, rtol=2e-14, atol=0)
    expected_c = np.where(
        opened, (INITIAL_VOLUME * old + bath * volume) / (INITIAL_VOLUME + volume), 0
    )
    observed_c = np.asarray(obs.lumen_concentration_mM)[:, tracer, cleft]
    np.testing.assert_allclose(observed_c, expected_c, rtol=3e-14, atol=0)
    heat = np.asarray(hist.lumen_fill_dissipated_energy_pJ)[:, cleft]
    expected_heat = [reference_heat(INITIAL_VOLUME, d, old, bath, temperature) for d in booked]
    np.testing.assert_allclose(heat, expected_heat, rtol=3e-13, atol=2e-20)
    assert np.all(heat >= 0) and np.all(np.diff(heat) >= 0)
    np.testing.assert_allclose(
        hist.lumen_fluid_work_pJ[:, cleft], -rt * sum(composition) * booked, rtol=2e-14, atol=0
    )
    if divided:
        ids = [m.id for m in spec.model.membranes]
        patches = np.asarray(hist.membrane_area_increment_m2)
        for name, fraction in (("furrow", 1.0), ("furrow_d1", 0.6), ("furrow_d2", 0.4)):
            live = time <= DIVISION if name == "furrow" else time > DIVISION
            np.testing.assert_allclose(
                patches[:, ids.index(name)], np.where(live, fraction * area, 0), rtol=2e-14, atol=0
            )
    return dict(
        final_volume_pL=float(observed_volume[-1]),
        final_tracer_mM=float(observed_c[-1]),
        final_booked_volume_increment_pL=float(booked[-1]),
        final_heat_pJ=float(heat[-1]),
        max_heat_error_pJ=float(max(abs(heat - expected_heat))),
        max_observed_volume_error_pL=float(max(abs(observed_volume - expected_volume))),
        max_concentration_error_mM=float(max(abs(observed_c - expected_c))),
    )


def first_fill(old, bath, temperature):
    """Isolate the tracer in the first positive half-step and retain the rounded residuals."""
    v = INITIAL_VOLUME
    dv = 0.5e15 * WIDTH * RATE * DT / 2
    mixed = (v * old + dv * bath) / (v + dv)
    e = dv * (old - bath) / ((v + dv) * mixed)
    eb = v * (bath - old) / ((v + dv) * mixed)
    p = SimpleNamespace(lumen_node=np.array([True]), temperature=temperature)
    with np.errstate(divide="ignore", invalid="ignore"):
        heat, _ = lumen.fill_energy(
            np.array([[v * old]]), np.array([v]), np.array([[bath]]), np.array([dv]), p, xp=np
        )
    readable = float(heat[0]) if np.isfinite(heat[0]) else None
    return dict(
        old_mM=old,
        bath_mM=bath,
        old_residual=e,
        bath_residual=eb,
        old_ratio=old / mixed,
        bath_ratio=bath / mixed,
        engine_heat_pJ=readable,
        reference_heat_pJ=reference_heat(v, dv, old, bath, temperature),
    )


def ratio_phi(x, xp):
    # Near equilibrium keep the engine's series. Below 1/2 the positive ratio
    # is available directly and subtracting nearly equal terms is no concern.
    safe = xp.where(x > 0, x, 1.0)
    return xp.where(x < 0.5, x * xp.log(safe) - x + 1, lumen.mixing(xp.maximum(x, 0.5) - 1, xp=xp))


def ratio_diagnostic(original):
    """Substitute ratio-based heat only where the original result is nonfinite."""

    def evaluate(amounts, volume, bath, dv, p, *, xp):
        heat, fluid = original(amounts, volume, bath, dv, p, xp=xp)
        active = p.lumen_node & (dv > 0)
        v = xp.where(active, volume, 1.0)
        n = xp.where(active, amounts, 1.0)
        b = xp.where(active, bath, 1.0)
        m = (n + b * dv) / (v + dv)
        terms = m * (v * ratio_phi(n / v / m, xp) + dv * ratio_phi(b / m, xp))
        alternative = 1e-3 * R * p.temperature * xp.sum(terms, axis=0)
        return xp.where(active & ~xp.isfinite(heat), alternative, heat), fluid

    return evaluate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--controls-only", action="store_true", help="only run ordinary concentrations"
    )
    args = parser.parse_args()
    jax.config.update("jax_enable_x64", True)
    controls = []
    for version, divided, old, bath in (
        (1, False, 4.0, 1.0),
        (2, False, 4.0, 1.0),
        (2, True, 4.0, 1.0),
        (1, False, 1.0, 4.0),
        (1, False, 1.0, 1.0),
    ):
        values = check_run(world(version, old, bath, divided=divided), old, bath, divided)
        controls.append(dict(version=version, divided=divided, old_mM=old, bath_mM=bath, **values))
    cases = []
    refused = []
    if not args.controls_only:
        for old, bath in ((1.0, 2.0**-60), (2.0**-60, 1.0)):
            for version in (1, 2):
                spec = world(version, old, bath)
                diagnostic = first_fill(old, bath, spec.model.temperature_K)
                assert min(diagnostic["old_ratio"], diagnostic["bath_ratio"]) > 0
                assert diagnostic["reference_heat_pJ"] > 0
                case = dict(version=version, **diagnostic)
                try:
                    case["production"] = check_run(spec, old, bath)
                except NumericalError as error:
                    if "domain failure on [0.001, 0.002]" not in str(error):
                        raise
                    if diagnostic["engine_heat_pJ"] is not None:
                        raise
                    case["refusal"] = str(error)
                    refused.append((spec, case))
                cases.append(case)
        if refused:
            # Retrace the same complete worlds so that only the failing heat is replaced.
            jax.clear_caches()
            with patch.object(lumen, "fill_energy", ratio_diagnostic(lumen.fill_energy)):
                for spec, case in refused:
                    case["ratio_replay"] = check_run(spec, case["old_mM"], case["bath_mM"])
            jax.clear_caches()
    print(
        json.dumps(
            dict(controls=controls, trace_cases=cases, morphometry=morphometry()),
            indent=2,
            allow_nan=False,
        )
    )
    return int(bool(refused))


if __name__ == "__main__":
    raise SystemExit(main())
