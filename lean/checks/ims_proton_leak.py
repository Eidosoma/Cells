"""Test which extracellular pH the bounding patch reads in a three-compartment Cells model."""

import json
import math
from statistics import mean, stdev
from dataclasses import replace
from pathlib import Path

import numpy as np
from scipy.optimize import brentq
from scipy.stats import t as student_t
from mitochondrial_cycles import seven_cycle_world
from proton_leak import inward_reference

from cells.definitions.pump_composite_spec import control_values
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes, proton_buffer
from cells.registry.models import get_model
from tests.unit.test_rapid_binding_world import host, leak_general, lumen_general
from validation.compartment_ph_engine import definitions as fr
from validation.compartment_ph_engine.parameters import World
from validation.tissue.surface_reference import F, R


def patch_read(lumen_ph, bath_ph):
    world = World()
    world = replace(
        world,
        end_s=1.0,
        cytosol_mM={**world.cytosol_mM, "pH": 7.0},
        lumen_mM={**world.lumen_mM, "pH": lumen_ph},
        bath_mM={**world.bath_mM, "pH": bath_ph},
    )
    spec = parse_spec(fr.declared_world(fr.fr4_world(world)))
    model = get_model(spec.model)
    state, layout = model.initial_values(spec)
    control = model.CONTROL_TYPE(*(v[0] for v in control_values(spec, [0.0])))
    h = spec.model.species_ids.index("H")
    values = model.readouts(state, control, layout, xp=np)
    assert values.valid
    _, _, view = model.clamp_inputs(state, control, layout)
    potential = values.ionic.field.potential_V
    step_voltage = potential[view.passive_inside] - potential[view.passive_outside]

    def clamp(voltage):
        flux, _ = model.clamped_kind(passive_routes.clamped_flux, state, control, layout, voltage)
        return flux

    np.testing.assert_array_equal(clamp(step_voltage), values.derivative.passive_transferred)
    rows = []
    for voltage in (0.0, 0.015):
        actual = float(clamp(voltage)[h, 0])
        args = (voltage, world.temperature_K, world.patch_area_m2, world.proton_leak_m_s, 1.0)
        # Neutralized initial charge and a common imposed voltage isolate the chemical read.
        local = inward_reference(1e-4, 10 ** (3 - lumen_ph), *args)
        bath = inward_reference(1e-4, 10 ** (3 - bath_ph), *args)
        np.testing.assert_allclose(actual, local, rtol=1e-8, atol=0.0)
        assert not np.isclose(actual, bath, rtol=1e-8, atol=0.0)
        rows.append(
            dict(
                voltage_mV=1000 * voltage,
                inward_fmol_s=actual,
                local_reference_fmol_s=local,
                bath_substitution_fmol_s=bath,
            )
        )
    return dict(lumen_pH=lumen_ph, bath_pH=bath_ph, clamped_flux=rows)


def general_binding(raw):
    parse_spec(raw)
    raw["model"]["passive_routes"] = [
        dict(
            id="inner_H_leak",
            patch=fr.BOUNDING,
            law="cells.route.proton_constant_field_leak@1",
            permeability_m_per_s=6e-7,
        )
    ]
    try:
        parse_spec(raw)
    except ConfigError as exc:
        reason = str(exc)
        if any(
            key not in reason
            for key in (
                "species H",
                "cells.route.proton_constant_field_leak@1",
                "cells.binding.rapid_binding@1",
            )
        ):
            raise
        return dict(admitted=False, reason=reason)
    return dict(admitted=True)


def buffered_clamp(inside_ph, outside_ph, temperature, outside_buffer):
    """Set one-site totals analytically. Read the general closure through the version-2 route."""
    raw = leak_general()
    m = raw["model"]
    m["temperature_K"] = temperature
    fixture = World()
    (cell,) = m["cells"]
    lumen = next(n for n in m["extracellular"] if n["id"] == fr.LUMEN)
    valence = {s["id"]: s["valence"] for s in m["species"]}
    for node, ph, buffer in ((cell, inside_ph, fixture.cytosol_buffer),
                             (lumen, outside_ph, replace(fixture.lumen_buffer, total_mM=outside_buffer))):
        volume = node["volume_pL"]
        amounts = node["initial_amount_fmol"]
        amounts[buffer.name] = volume * buffer.total_mM
        amounts["H"] = fixture.proton_equivalents_fmol(ph, buffer, volume)
        node["fixed_charge_equivalent_fmol"] = node["initial_charge_C"] / fr.CHARGE_PER_FMOL - math.fsum(
            valence[s] * amount for s, amount in amounts.items())
    spec = parse_spec(raw)
    _, state, p, control = host(spec)
    read, ok = proton_buffer.stage_read(state, p, xp=np)
    assert bool(ok)
    h = list(spec.model.species_ids).index("H")

    def flux(state_read, voltage):
        rates, _ = passive_routes.clamped_flux(state_read, control, p, voltage, xp=np)
        return float(rates[h, 0])

    reversal = brentq(lambda v: flux(read, v), -0.2, 0.2, xtol=1e-14)
    assert flux(read, reversal - 0.001) > 0 > flux(read, reversal + 0.001)
    # Use the unprocessed proton-equivalent amounts at the same voltage as a wrong-read control.
    wrong = flux(state, reversal)
    at_zero = flux(read, 0)
    assert abs(wrong) > abs(at_zero)
    return dict(outside_buffer_mM=outside_buffer, reversal_mV=1000 * reversal,
                zero_voltage_fmol_s=at_zero, stored_total_flux_at_reversal_fmol_s=wrong)


def mitoplast_reversals():
    data = json.loads((Path(__file__).with_name("data") / "bertholet2019_proton_reversal.json").read_text())
    temperature = 273.15 + data["nernst_reference_temperature_C"]
    groups = []
    for group in data["groups"]:
        inside, outside = group["matrix_pH"], group["bath_pH"]
        clamps = [buffered_clamp(inside, outside, temperature, b) for b in (1.0, 100.0)]
        ideal = 1000 * R * temperature / F * math.log(10) * (inside - outside)
        np.testing.assert_allclose([c["reversal_mV"] for c in clamps], ideal, rtol=0, atol=1e-6)
        np.testing.assert_allclose(clamps[0]["zero_voltage_fmol_s"], clamps[1]["zero_voltage_fmol_s"],
                                   rtol=1e-7, atol=0)
        observed = group["reversal_mV"]
        n = len(observed)
        center = mean(observed)
        sem = stdev(observed) / math.sqrt(n)
        half = student_t.ppf(0.975, n - 1) * sem
        prediction = clamps[0]["reversal_mV"]
        groups.append(dict(matrix_pH=inside, bath_pH=outside, n=n, mean_mV=center, sem_mV=sem,
                           mean_ci95_mV=[center - half, center + half], prediction_mV=prediction,
                           prediction_minus_mean_mV=prediction - center,
                           within_descriptive_interval=bool(abs(prediction - center) <= half),
                           clamps=clamps))
    return groups


def comparison():
    # Independently change the free pH at the finite outside node and in the held bath.
    worlds = [patch_read(lumen, bath) for lumen in (6.65, 7.115) for bath in (7.10, 7.60)]
    for low, high in (worlds[:2], worlds[2:]):
        assert [v["inward_fmol_s"] for v in low["clamped_flux"]] == [
            v["inward_fmol_s"] for v in high["clamped_flux"]
        ]
    assert all(
        v["inward_fmol_s"] > 0 > v["bath_substitution_fmol_s"] for v in worlds[0]["clamped_flux"]
    )
    assert all(v["inward_fmol_s"] < 0 for v in worlds[2]["clamped_flux"])
    data = json.loads((Path(__file__).with_name("data") / "cortese1992_ims_ph.json").read_text())
    # pH = -log10(activity). The conversion reverses the order of a pH interval.
    activities = {name: [10**-high, 10**-low] for name, (low, high) in data["offset_pH"].items()}
    # Isolate the outside endpoint: the seven-cycle fixture has general binding on both sides.
    outside_only = lumen_general()
    read = outside_only["model"]["stage_reads"][0]
    del read["binders"][fr.CELL]
    del read["k_on_per_mM_s"]["B_c"]
    outside = general_binding(outside_only)
    if not outside["admitted"]:
        assert f"species H at {fr.LUMEN} " in outside["reason"]
    return dict(
        buffered_v2_reversals=mitoplast_reversals(),
        activity_ratio_ims_to_bath=activities,
        simple_proton_buffer=worlds,
        seven_cycle_general_binding=general_binding(seven_cycle_world()),
        outside_only_general_binding=outside,
    )


if __name__ == "__main__":
    print(json.dumps(comparison(), indent=2, allow_nan=False))
