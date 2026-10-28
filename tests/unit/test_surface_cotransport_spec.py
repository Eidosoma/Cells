"""Strict named routes, faithful finite-energy projection and six-clock hooks."""

from copy import deepcopy

import numpy as np
import pytest

from cells.core import surface_cotransport_spec as schema
from cells.core import surface_energy_spec as energy
from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.ensemble.families import parse_definition, population
from cells.models import surface_cotransport as model
from cells.models.registry import get_model
from validation.tissue import surface_cotransport_fixtures as fixtures


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registration_lossless_roundtrip_and_complete_state(backend, padded):
    raw = fixtures.definition("release", backend=backend, padded=padded)
    before = deepcopy(raw)
    spec = schema.parse(raw)
    assert spec == parse_spec(raw) == schema.parse(spec.to_dict())
    assert spec.to_dict() == before == raw
    assert get_model(spec.model) is model
    assert len(model.STATE_TYPE._fields) == 26
    assert type(spec.model) is schema.SurfaceCotransportModel
    assert type(spec.execution) is schema.Execution
    assert spec.model.cotransporters[0].roles == schema.CotransportRoles("K", "Cl")


def test_finite_energy_projection_preserves_every_non_cotransport_declaration():
    raw = fixtures.definition("two_patches", padded=True)
    spec = schema.parse(raw)
    expected = deepcopy(raw)
    expected["model"]["id"] = energy.MODEL_ID
    expected["model"].pop("cotransporters")
    expected["experiment"].pop("cotransport_controls")
    expected["execution"].pop("cotransport_capacity")
    projected = schema.energy_spec(spec)
    assert projected == energy.parse(expected)
    assert projected.to_dict() == expected
    assert type(projected.model) is energy.SurfaceEnergyModel
    assert type(projected.experiment) is energy.Experiment
    assert type(projected.execution) is energy.Execution
    assert schema.initial_ionic_spec(spec) == energy.initial_ionic_spec(projected)


def test_renamed_reordered_species_keep_correct_actual_roles_and_owners():
    spec = schema.parse(fixtures.definition("renamed", padded=True))
    assert spec.model.species_ids == ("calcium_ion", "chloride_ion", "potassium_ion", "sodium_ion")
    _, p = model.initial_values(spec)
    np.testing.assert_array_equal(
        p.cotransport_stoichiometry[:, :2], [[0, 0], [1, 2], [1, 1], [0, 1]]
    )
    assert not np.any(p.cotransport_stoichiometry[:, 2:])
    assert schema.parse(spec.to_dict()) == spec


def test_six_independent_clocks_right_continuity_padding_and_step_ceiling():
    spec = schema.parse(fixtures.definition("release", padded=True))
    times = timeline(spec)
    assert all(
        t in times
        for t in (
            11.1e-6,
            13.3e-6,
            17.3e-6,
            19.1e-6,
            23.7e-6,
            29.9e-6,
            31.1e-6,
            37.1e-6,
            41.3e-6,
            43.3e-6,
        )
    )
    controls = control_values(spec, [0.0, 11.1e-6, 19.1e-6, 29.9e-6, 43.3e-6])
    assert type(controls) is schema.Control
    assert controls._fields == (
        "membrane",
        "junction",
        "channel",
        "pump",
        "regeneration",
        "cotransport",
    )
    np.testing.assert_array_equal(
        controls.cotransport[:, :2], [[0.8, 0.6], [0.0, 0.6], [0, 0], [0.7, 0], [0.7, 0.9]]
    )
    assert not np.any(controls.cotransport[:, 2:])
    assert np.max(np.diff(times)) <= fixtures.DT * (1 + 1e-12)


def test_empty_routes_have_explicit_control_and_capacity_axes():
    spec = schema.parse(fixtures.definition("absent"))
    state, p = model.initial_values(spec)
    assert state.cotransport_transferred_fmol.shape == (4, 0)
    assert p.cotransport_active.shape == (0,)
    assert control_values(spec, [0.0]).cotransport.shape == (1, 0)
    assert schema.parse(spec.to_dict()) == spec


def test_ionic_world_family_accepts_the_new_physical_model_without_running_it():
    raw = dict(
        model="ionic_worlds@1",
        simulation=fixtures.definition("release", padded=True),
        worlds=2,
        window_steps=2,
    )
    family = parse_definition(raw)
    assert population(family).worlds == 2
    assert family.simulation.model == schema.parse(raw["simulation"]).model
    assert family.to_dict()["simulation"] == raw["simulation"]


@pytest.mark.parametrize(
    "fault",
    [
        "missing_routes",
        "missing_controls",
        "missing_capacity",
        "wrong_id",
        "unknown_field",
        "routes_not_list",
        "duplicate_route",
        "colliding_id",
        "unknown_membrane",
        "unknown_law",
        "missing_role",
        "extra_role",
        "unknown_species",
        "aliased_roles",
        "wrong_valence",
        "negative_capacity",
        "bool_capacity",
        "nonfinite_capacity",
        "overflow_capacity",
        "short_capacity",
        "fractional_capacity",
        "bool_axis_capacity",
        "duplicate_control",
        "missing_control",
        "unknown_control",
        "empty_schedule",
        "negative_time",
        "nonzero_start",
        "decreasing_time",
        "past_end",
        "bad_availability",
        "bool_availability",
        "unknown_control_field",
    ],
)
def test_invalid_declarations_rejected_without_mutating_inputs(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    r, control = m["cotransporters"][0], e["cotransport_controls"][0]
    if fault == "missing_routes":
        m.pop("cotransporters")
    elif fault == "missing_controls":
        e.pop("cotransport_controls")
    elif fault == "missing_capacity":
        x.pop("cotransport_capacity")
    elif fault == "wrong_id":
        m["id"] = "resolved_energy@1"
    elif fault == "unknown_field":
        r["temperature_K"] = 298.15
    elif fault == "routes_not_list":
        m["cotransporters"] = {}
    elif fault == "duplicate_route":
        m["cotransporters"].append(deepcopy(r))
        x["cotransport_capacity"] += 1
    elif fault == "colliding_id":
        r["id"] = m["energy_pools"][0]["id"]
    elif fault == "unknown_membrane":
        r["membrane_id"] = "absent_patch"
    elif fault == "unknown_law":
        r["law"] = "native_betse_kcc@1"
    elif fault == "missing_role":
        r["roles"].pop("chloride")
    elif fault == "extra_role":
        r["roles"]["sodium"] = "Na"
    elif fault == "unknown_species":
        r["roles"]["potassium"] = "absent_species"
    elif fault == "aliased_roles":
        r["roles"]["chloride"] = r["roles"]["potassium"]
    elif fault == "wrong_valence":
        r["roles"]["chloride"] = "Ca"
    elif fault == "negative_capacity":
        r["capacity_fmol_per_s"] = -1
    elif fault == "bool_capacity":
        r["capacity_fmol_per_s"] = True
    elif fault == "nonfinite_capacity":
        r["capacity_fmol_per_s"] = np.nan
    elif fault == "overflow_capacity":
        # NKCC has sufficient affinity here to make power nonfinite; KCC's
        # initial power at this same large capacity can still be representable.
        m["cotransporters"][1]["capacity_fmol_per_s"] = 1e308
    elif fault == "short_capacity":
        x["cotransport_capacity"] = 1
    elif fault == "fractional_capacity":
        x["cotransport_capacity"] = 2.5
    elif fault == "bool_axis_capacity":
        x["cotransport_capacity"] = True
    elif fault == "duplicate_control":
        e["cotransport_controls"].append(deepcopy(control))
    elif fault == "missing_control":
        e["cotransport_controls"].pop()
    elif fault == "unknown_control":
        control["cotransport_id"] = "absent_route"
    elif fault == "empty_schedule":
        control["schedule"] = []
    elif fault == "negative_time":
        control["schedule"][0]["time"] = -1
    elif fault == "nonzero_start":
        control["schedule"][0]["time"] = 1e-6
    elif fault == "decreasing_time":
        control["schedule"].append(dict(time=0, availability=0))
    elif fault == "past_end":
        control["schedule"].append(dict(time=1, availability=0))
    elif fault == "bad_availability":
        control["schedule"][0]["availability"] = 1.1
    elif fault == "bool_availability":
        control["schedule"][0]["availability"] = True
    else:
        control["extra"] = 1
    before = deepcopy(raw)
    with pytest.raises(ConfigError):
        schema.parse(raw)
    # NaN equality needs a structural representation rather than Python dict equality.
    assert repr(raw) == repr(before)
