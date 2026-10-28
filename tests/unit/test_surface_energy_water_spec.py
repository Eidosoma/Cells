"""Explicit neutral pool osmosis, faithful projections and six independent clocks."""

from copy import deepcopy

import numpy as np
import pytest

from cells.core import surface_energy_spec as energy
from cells.core import surface_energy_water_spec as schema
from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble import ionic
from cells.models import surface_energy_water as model
from cells.models.registry import get_model
from validation.tissue import surface_energy_water_fixtures as fixtures


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registered_complete_state_and_explicit_roundtrip(backend, padded):
    raw = fixtures.definition("release", backend=backend, padded=padded)
    original = deepcopy(raw)
    spec = parse_spec(raw)
    assert spec.to_dict() == raw == original
    assert parse_spec(spec.to_dict()) == spec
    assert type(spec.model) is schema.SurfaceEnergyWaterModel
    assert type(spec.execution) is energy.Execution
    assert get_model(spec.model) is model
    state, _ = model.initial_values(spec)
    assert len(state) == 28
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


def test_projections_preserve_energy_and_do_not_hide_pools_in_background():
    raw = fixtures.definition("two_patches", padded=True)
    spec = parse_spec(raw)
    expected = deepcopy(raw)
    expected["model"]["id"] = energy.MODEL_ID
    for k in ("energy_osmotic_coupling", "water_compartments", "water_membranes"):
        expected["model"].pop(k)
    expected["experiment"].pop("water_controls")
    assert schema.energy_spec(spec).to_dict() == expected
    projected = schema.water_spec(spec)
    assert projected.model.water_compartments == spec.model.water_compartments
    assert projected.model.water_compartments[0].impermeant_amount_fmol == 300.0
    assert not hasattr(projected.model, "energy_pools")
    assert len(projected.model.membranes) == 2


def test_six_independent_clocks_and_right_continuous_padding():
    spec = parse_spec(fixtures.definition("release", padded=True))
    times = timeline(spec)
    events = (11.3e-6, 13.3e-6, 17.3e-6, 23.7e-6, 29.1e-6, 31.1e-6, 37.1e-6, 41.3e-6)
    assert all(t in times for t in events)
    selected = [0.0, *events]
    values = control_values(spec, selected)
    assert values._fields == ("membrane", "junction", "channel", "pump", "regeneration", "water")
    np.testing.assert_array_equal(values.water[:, 0], [1, 0, 0, 0, 0, 0.8, 0.8, 0.8, 0.8])
    np.testing.assert_array_equal(values.regeneration[:, 0], [0.2, 0.2, 0, 0, 0, 0, 0.9, 0.9, 0.9])
    assert not np.any(values.water[:, 1:])
    assert not np.any(values.regeneration[:, 1:])


@pytest.mark.parametrize(
    "fault",
    [
        "missing_coupling",
        "unknown_coupling",
        "charged_coupling",
        "extra_field",
        "missing_compartments",
        "missing_controls",
        "unknown_owner",
        "duplicate_water",
        "invalid_initial_volume",
        "invalid_pool",
        "negative_hydraulic",
        "unknown_control",
    ],
)
def test_invalid_or_implicit_couplings_are_rejected(fault):
    raw = fixtures.definition()
    m, e = raw["model"], raw["experiment"]
    if fault == "missing_coupling":
        m.pop("energy_osmotic_coupling")
    elif fault in ("unknown_coupling", "charged_coupling"):
        m["energy_osmotic_coupling"] = fault
    elif fault == "extra_field":
        m["implicit_pool_particles"] = True
    elif fault == "missing_compartments":
        m.pop("water_compartments")
    elif fault == "missing_controls":
        e.pop("water_controls")
    elif fault == "unknown_owner":
        m["water_compartments"][0]["compartment_id"] = "unknown"
    elif fault == "duplicate_water":
        m["water_membranes"].append(deepcopy(m["water_membranes"][0]))
    elif fault == "invalid_initial_volume":
        m["water_compartments"][0]["minimum_volume_pL"] = 2.0
    elif fault == "invalid_pool":
        m["energy_pools"][0]["initial_amount_fmol"]["ATP"] = 0.0
    elif fault == "negative_hydraulic":
        m["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = -1e-10
    else:
        e["water_controls"][0]["membrane_id"] = "unknown"
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_water_step_ceiling_uses_conserved_pool_inventory():
    raw = fixtures.definition()
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 1e-5
    spec = parse_spec(raw)
    with pytest.raises(ConfigError, match="water relaxation"):
        model.check_steps(spec, np.asarray([fixtures.DT]), control_values(spec, [0.0]))
