"""Test which extracellular pH the bounding patch reads in a three-compartment Cells model."""

import json
from dataclasses import replace
from pathlib import Path

import numpy as np
from mitochondrial_cycles import seven_cycle_world
from proton_leak import inward_reference

from cells.definitions.pump_composite_spec import control_values
from cells.definitions.specs import ConfigError, parse_spec
from cells.kinds import passive_routes
from cells.registry.models import get_model
from tests.unit.test_rapid_binding_world import lumen_general
from validation.compartment_ph_engine import definitions as fr
from validation.compartment_ph_engine.parameters import World


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
            law="proton_constant_field_leak@1",
            permeability_m_per_s=6e-7,
        )
    ]
    try:
        parse_spec(raw)
    except ConfigError as exc:
        reason = str(exc)
        if any(
            key not in reason
            for key in ("species H", "proton_constant_field_leak@1", "rapid_binding@1")
        ):
            raise
        return dict(admitted=False, reason=reason)
    return dict(admitted=True)


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
        activity_ratio_ims_to_bath=activities,
        simple_proton_buffer=worlds,
        seven_cycle_general_binding=general_binding(seven_cycle_world()),
        outside_only_general_binding=outside,
    )


if __name__ == "__main__":
    print(json.dumps(comparison(), indent=2, allow_nan=False))
