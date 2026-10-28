"""Active-water definitions, projections and independent control clocks."""

from copy import deepcopy

import numpy as np
import pytest

from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_water_kinetic_spec import prior_spec, water_spec
from cells.ensemble import ionic
from cells.models import surface_water_kinetic as model
from cells.models.registry import get_model
from validation.tissue import surface_water_kinetic_fixtures as fixtures


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registration_complete_state_roundtrip_and_ensemble(backend, padded):
    raw = fixtures.definition("release", backend=backend, padded=padded)
    unchanged = deepcopy(raw)
    spec = parse_spec(raw)
    assert raw == unchanged and parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    state, p = model.initial_values(spec)
    assert len(state) == 23 and len(p) == len(model.LAYOUT_TYPE._fields)
    assert state.channel_transferred.shape == (4, spec.execution.channel_capacity)
    assert not any(model.check_values(state, spec).values())
    assert (
        ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2)).simulation == spec
    )


def test_lossless_active_and_water_projections():
    spec = parse_spec(fixtures.definition("release"))
    active, water = prior_spec(spec), water_spec(spec)
    assert active.to_dict()["model"]["id"] == "resolved_tissue@7"
    assert water.to_dict()["model"]["id"] == "resolved_water@1"
    assert parse_spec(active.to_dict()) == active and parse_spec(water.to_dict()) == water
    assert active.model.channels == spec.model.channels
    assert active.model.membranes == spec.model.membranes
    assert active.experiment.pumps == spec.experiment.pumps
    assert water.model.water_compartments == spec.model.water_compartments
    assert water.experiment.water == spec.experiment.water
    assert not hasattr(water.execution, "channel_capacity")


def test_union_clocks_and_inactive_water_padding():
    spec = parse_spec(fixtures.definition("release"))
    times = timeline(spec)
    events = (13.3e-6, 17.3e-6, 23.7e-6, 31.1e-6, 37.1e-6, 41.3e-6)
    assert all(t in times for t in events)
    table = control_values(spec, events)
    assert table._fields == ("membrane", "junction", "channel", "pump", "water")
    np.testing.assert_array_equal(table.water[:, 0], [0, 0, 0, 0.8, 0.8, 0.8])
    np.testing.assert_array_equal(table.channel[:, 0], [0.8, 0, 0, 0, 0.7, 0.7])
    np.testing.assert_array_equal(table.pump[:, 0], [0.8, 0.8, 0, 0, 0, 0.7])
    assert not np.any(table.water[:, 1:])


@pytest.mark.parametrize(
    "fault",
    [
        "missing_water",
        "unknown_model_field",
        "unknown_experiment_field",
        "duplicate_owner",
        "unknown_owner",
        "negative_osmolyte",
        "volume_bound",
        "reservoir",
        "negative_permeability",
        "missing_control",
        "duplicate_control",
        "nan_control",
        "blocked_invalid_atp",
        "finite_metabolism",
        "missing_permeant_species",
        "duplicate_channel",
        "boolean_version",
    ],
)
def test_invalid_compositions_are_rejected(fault):
    raw = fixtures.definition("release")
    m, e = raw["model"], raw["experiment"]
    if fault == "missing_water":
        del m["water_membranes"]
    elif fault == "unknown_model_field":
        m["water_speed"] = 1.0
    elif fault == "unknown_experiment_field":
        e["water_time_scale"] = 2.0
    elif fault == "duplicate_owner":
        m["water_compartments"].append(deepcopy(m["water_compartments"][0]))
    elif fault == "unknown_owner":
        m["water_compartments"][0]["compartment_id"] = "missing"
    elif fault == "negative_osmolyte":
        m["water_compartments"][0]["impermeant_amount_fmol"] = -1.0
    elif fault == "volume_bound":
        m["water_compartments"][0]["minimum_volume_pL"] = m["cells"][0]["volume_pL"]
    elif fault == "reservoir":
        m["extracellular"][0]["reservoir"] = True
    elif fault == "negative_permeability":
        m["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = -1.0
    elif fault == "missing_control":
        e["water_controls"] = []
    elif fault == "duplicate_control":
        e["water_controls"].append(deepcopy(e["water_controls"][0]))
    elif fault == "nan_control":
        e["water_controls"][0]["schedule"][0]["availability"] = float("nan")
    elif fault == "blocked_invalid_atp":
        m["membranes"][0]["pump"]["metabolism"]["atp_mM"] = 0.0
        e["pump_controls"][0]["schedule"] = [dict(time=0.0, availability=0.0)]
    elif fault == "finite_metabolism":
        m["membranes"][0]["pump"]["metabolism"]["kind"] = "finite_atp_pool@1"
    elif fault == "missing_permeant_species":
        m["channels"][0]["permeant_ions"][0]["species_id"] = "missing"
    elif fault == "duplicate_channel":
        m["channels"].append(deepcopy(m["channels"][0]))
    else:
        raw["schema_version"] = True
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_gate_and_water_step_limits_are_both_preserved():
    timeline(parse_spec(fixtures.definition()))
    raw = fixtures.definition(dt=2.5e-6)
    with pytest.raises(ConfigError, match="CaV"):
        timeline(parse_spec(raw))
    raw = fixtures.definition()
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 1e-5
    with pytest.raises(ConfigError, match="water relaxation"):
        timeline(parse_spec(raw))


@pytest.mark.parametrize("arm", fixtures.ARMS)
def test_each_synthetic_arm_has_a_valid_bounded_definition(arm):
    spec = parse_spec(fixtures.definition(arm))
    assert len(timeline(spec)) > 1
    state, _ = model.initial_values(spec)
    assert not any(model.check_values(state, spec).values())
