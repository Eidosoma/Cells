"""Water ownership and control contracts, without running a water trajectory."""

import json
from copy import deepcopy
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from cells.core import surface_tissue_spec as prior
from cells.core import surface_water_spec as water
from cells.core.specs import ConfigError, SpatialExtracellularExecutionSpec
from validation.tissue import surface_dynamics_fixtures

CONFIG = Path(__file__).resolve().parents[2] / "configs" / "resolved_water_tissue.json"
COMPARTMENT_NUMBERS = tuple(water.WaterCompartment.__dataclass_fields__)[1:]
BAD_NUMBERS = (
    pytest.param(True, id="true"),
    pytest.param(False, id="false"),
    pytest.param(float("nan"), id="nan"),
    pytest.param(float("inf"), id="infinity"),
    pytest.param(-float("inf"), id="negative-infinity"),
    pytest.param("1", id="string"),
    pytest.param(None, id="null"),
    pytest.param(10**400, id="float64-overflow"),
)


@pytest.fixture
def raw():
    return json.loads(CONFIG.read_text())


def schedule(*pairs):
    return [dict(time=t, availability=a) for t, a in pairs]


def at(value, path):
    for key in path:
        value = value[key]
    return value


@pytest.fixture
def network():
    raw = surface_dynamics_fixtures.definition("closed", backend="cpu")
    m, e = raw["model"], raw["experiment"]
    m["id"] = water.MODEL_ID
    m["water_compartments"] = [
        dict(
            compartment_id=p["id"],
            reference_volume_pL=0.9 * p["volume_pL"],
            minimum_volume_pL=0.5 * p["volume_pL"],
            maximum_volume_pL=1.5 * p["volume_pL"],
            impermeant_amount_fmol=7.0 + i,
            bulk_modulus_Pa=200000.0 + i,
            pressure_offset_Pa=-500.0 + i,
        )
        for i, p in enumerate(m["cells"] + m["extracellular"])
    ]
    m["water_membranes"] = [
        dict(membrane_id=p["id"], hydraulic_permeability_m_per_Pa_s=(i + 1) * 1e-13)
        for i, p in enumerate(m["membranes"])
    ]
    e["water_controls"] = [
        dict(membrane_id=p["id"], schedule=schedule((0.0, 0.1 * (i + 1))))
        for i, p in enumerate(m["membranes"])
    ]
    return raw


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
def test_example_roundtrip_and_immutable_definition(raw, backend):
    raw["execution"]["backend"] = backend
    untouched = deepcopy(raw)
    spec = water.parse(raw)
    assert type(spec.model) is water.SurfaceWaterModel
    assert type(spec.experiment) is water.Experiment
    assert type(spec.execution) is SpatialExtracellularExecutionSpec
    assert spec.execution.backend == backend
    assert water.parse(water.to_dict(spec)) == spec
    assert water.to_dict(spec) == raw == untouched
    assert len(spec.model.cells) == len(spec.model.extracellular) == 1
    assert not spec.model.extracellular[0].reservoir
    assert spec.model.water_membranes[0].hydraulic_permeability_m_per_Pa_s > 0
    with pytest.raises(FrozenInstanceError):
        spec.model.water_compartments[0].reference_volume_pL = 3.0


def test_example_water_block_and_release_are_independent(raw):
    spec = water.parse(raw)
    changes = {c.time: c for c in spec.experiment.changes}
    assert set(changes) == {0.0, 0.00037, 0.00073, 0.00113, 0.00151}
    assert changes[0.00037].water == (0.0,) and changes[0.00037].membrane == (1.0,)
    assert changes[0.00113].water == (0.8,) and changes[0.00113].membrane == (0.0,)
    assert changes[0.00151].water == (0.8,) and changes[0.00151].membrane == (0.75,)
    assert all(c.junction == () for c in changes.values())
    assert water.Control._fields == ("membrane", "junction", "water")
    assert water.Control((1.0,), (), (0.8,)).water == (0.8,)


@pytest.mark.parametrize("reorder_ionic", [False, True])
def test_water_records_follow_explicit_ionic_owner_and_membrane_order(network, reorder_ionic):
    if reorder_ionic:
        for key in ("cells", "extracellular", "membranes", "species"):
            network["model"][key].reverse()
    expected = water.parse(network)
    for key in ("water_compartments", "water_membranes"):
        network["model"][key].reverse()
    network["experiment"]["water_controls"].reverse()
    spec = water.parse(network)
    assert spec == expected
    assert tuple(p.compartment_id for p in spec.model.water_compartments) == tuple(
        p.id for p in (*spec.model.cells, *spec.model.extracellular)
    )
    assert tuple(p.membrane_id for p in spec.model.water_membranes) == tuple(
        p.id for p in spec.model.membranes
    )
    assert water.parse(water.to_dict(spec)) == spec


def test_prior_projection_preserves_every_ionic_input_and_clock(network):
    network["experiment"]["membrane_controls"][0]["schedule"] += schedule((0.00073, 0.3))
    network["experiment"]["junction_controls"][0]["schedule"] += schedule((0.00113, 0.4))
    network["experiment"]["water_controls"][0]["schedule"] += schedule((0.00037, 0.0))
    expected = deepcopy(network)
    expected["model"]["id"] = prior.MODEL_ID
    del expected["model"]["water_compartments"], expected["model"]["water_membranes"]
    del expected["experiment"]["water_controls"]
    spec = water.parse(network)
    projected = water.prior_spec(spec)
    assert projected == prior.parse(expected)
    assert prior.to_dict(projected) == expected
    assert projected.execution is spec.execution
    assert tuple(c.time for c in projected.experiment.changes) == (0.0, 0.00073, 0.00113)
    assert 0.00037 in tuple(c.time for c in spec.experiment.changes)


def test_union_clocks_are_right_continuous_at_separate_and_coincident_changes(network):
    e = network["experiment"]
    e["membrane_controls"][0]["schedule"] = schedule((0.0, 1.0), (0.00073, 0.2), (0.0013, 0.4))
    e["junction_controls"][0]["schedule"] = schedule((0.0, 0.6), (0.00083, 0.0), (0.00113, 0.7))
    e["water_controls"][0]["schedule"] = schedule((0.0, 0.9), (0.00037, 0.0), (0.00113, 0.8))
    e["water_controls"][1]["schedule"] = schedule((0.0, 0.3), (0.00171, 1.0))
    changes = water.parse(network).experiment.changes
    assert [(c.time, c.membrane[0], c.junction[0], *c.water[:2]) for c in changes] == [
        (0.0, 1.0, 0.6, 0.9, 0.3),
        (0.00037, 1.0, 0.6, 0.0, 0.3),
        (0.00073, 0.2, 0.6, 0.0, 0.3),
        (0.00083, 0.2, 0.0, 0.0, 0.3),
        (0.00113, 0.2, 0.7, 0.8, 0.3),
        (0.0013, 0.4, 0.7, 0.8, 0.3),
        (0.00171, 0.4, 0.7, 0.8, 1.0),
    ]


def test_osmolyte_count_reference_volume_and_signed_prestress_are_independent(raw):
    owner = raw["model"]["water_compartments"][0]
    owner.update(
        reference_volume_pL=1.5,
        impermeant_amount_fmol=0,
        bulk_modulus_Pa=0,
        pressure_offset_Pa=-1200,
    )
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 0
    spec = water.parse(raw)
    assert spec.model.cells[0].volume_pL == 2.0
    assert spec.model.cells[0].fixed_charge_equivalent_fmol == -284.0
    assert spec.model.water_compartments[0] == water.WaterCompartment(
        "cell_0", 1.5, 1.0, 3.0, 0.0, 0.0, -1200.0
    )
    assert spec.model.water_membranes[0].hydraulic_permeability_m_per_Pa_s == 0
    assert water.parse(water.to_dict(spec)) == spec


@pytest.mark.parametrize("field", COMPARTMENT_NUMBERS)
@pytest.mark.parametrize("value", BAD_NUMBERS)
def test_invalid_compartment_number_types_and_nonfinite_values(raw, field, value):
    raw["model"]["water_compartments"][0][field] = value
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize("value", BAD_NUMBERS + (pytest.param(-1.0, id="negative"),))
def test_invalid_hydraulic_permeability(raw, value):
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = value
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize("blocked", [False, True])
def test_overflowed_derived_hydraulic_conductance_is_rejected(raw, blocked):
    # A finite declared Lp must not hide an infinite area/unit-converted
    # conductance, including when every prescribed water availability is zero.
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = 1e308
    if blocked:
        for change in raw["experiment"]["water_controls"][0]["schedule"]:
            change["availability"] = 0.0
    with pytest.raises(ConfigError, match="conductance"):
        water.parse(raw)


@pytest.mark.parametrize("field", COMPARTMENT_NUMBERS[:-1])
def test_negative_water_compartment_parameters_are_rejected(raw, field):
    raw["model"]["water_compartments"][0][field] = -1.0
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize(
    "update",
    [
        {"minimum_volume_pL": 0.0},
        {"minimum_volume_pL": 2.0},
        {"maximum_volume_pL": 2.0},
        {"minimum_volume_pL": 2.1},
        {"maximum_volume_pL": 1.9},
        {"minimum_volume_pL": 4.0, "maximum_volume_pL": 1.0},
        {"reference_volume_pL": 0.0},
        {"reference_volume_pL": 1.0},
        {"reference_volume_pL": 3.0},
        {"reference_volume_pL": 0.9},
        {"reference_volume_pL": 3.1},
    ],
)
def test_initial_and_reference_volumes_must_both_be_strictly_inside_bounds(raw, update):
    raw["model"]["water_compartments"][0].update(update)
    with pytest.raises(ConfigError):
        water.parse(raw)


RECORDS = (
    (("model", "water_compartments"), "compartment_id"),
    (("model", "water_membranes"), "membrane_id"),
    (("experiment", "water_controls"), "membrane_id"),
)


@pytest.mark.parametrize(("path", "id_field"), RECORDS)
@pytest.mark.parametrize("fault", ["missing", "duplicate", "unknown", "extra", "boolean-id"])
def test_every_water_owner_membrane_and_control_has_exactly_one_declaration(
    raw, path, id_field, fault
):
    rows = at(raw, path)
    if fault == "missing":
        rows.pop()
    elif fault == "duplicate":
        rows.append(deepcopy(rows[0]))
    elif fault == "unknown":
        rows[0][id_field] = "unknown_owner"
    elif fault == "extra":
        rows.append(deepcopy(rows[0]) | {id_field: "unowned"})
    else:
        rows[0][id_field] = True
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize(("path", "id_field"), RECORDS)
@pytest.mark.parametrize("value", [None, {}, True, ()])
def test_water_declarations_require_explicit_lists(raw, path, id_field, value):
    at(raw, path[:-1])[path[-1]] = value
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize(
    "path",
    [
        (),
        ("model",),
        ("experiment",),
        ("execution",),
        ("model", "water_compartments", 0),
        ("model", "water_membranes", 0),
        ("experiment", "water_controls", 0),
        ("experiment", "water_controls", 0, "schedule", 0),
    ],
)
def test_unknown_fields_are_rejected_at_every_schema_level(raw, path):
    at(raw, path)["unsupported"] = 0
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize("field", tuple(water.WaterCompartment.__dataclass_fields__))
def test_every_water_compartment_property_is_explicit(raw, field):
    del raw["model"]["water_compartments"][0][field]
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize(
    "path",
    [
        ("model", "water_compartments"),
        ("model", "water_membranes"),
        ("experiment", "water_controls"),
        ("model", "water_membranes", 0, "membrane_id"),
        ("model", "water_membranes", 0, "hydraulic_permeability_m_per_Pa_s"),
        ("experiment", "water_controls", 0, "membrane_id"),
        ("experiment", "water_controls", 0, "schedule"),
        ("experiment", "water_controls", 0, "schedule", 0, "time"),
        ("experiment", "water_controls", 0, "schedule", 0, "availability"),
    ],
)
def test_water_lists_membrane_properties_and_control_fields_are_required(raw, path):
    del at(raw, path[:-1])[path[-1]]
    with pytest.raises(ConfigError):
        water.parse(raw)


@pytest.mark.parametrize(
    "changes",
    [
        None,
        {},
        (),
        [],
        [None],
        schedule((0.0001, 1.0)),
        schedule((0.0, 1.0), (0.0, 0.0)),
        schedule((0.0, 1.0), (0.001, 0.0), (0.0005, 1.0)),
        schedule((0.0, 1.0), (0.003, 0.0)),
        schedule((-0.0001, 1.0)),
        schedule((False, 1.0)),
        schedule((float("nan"), 1.0)),
        schedule((float("inf"), 1.0)),
        schedule((0.0, -0.1)),
        schedule((0.0, 1.1)),
        schedule((0.0, True)),
        schedule((0.0, float("nan"))),
        schedule((0.0, float("inf"))),
    ],
)
def test_water_controls_require_finite_ordered_bounded_schedules(raw, changes):
    raw["experiment"]["water_controls"][0]["schedule"] = changes
    with pytest.raises(ConfigError):
        water.parse(raw)


def test_control_change_at_terminal_time_is_retained(raw):
    raw["experiment"]["water_controls"][0]["schedule"] += schedule((0.002, 0.0))
    spec = water.parse(raw)
    assert spec.experiment.changes[-1].time == 0.002
    assert spec.experiment.changes[-1].water == (0.0,)
    assert water.parse(water.to_dict(spec)) == spec


def test_held_outside_reservoirs_are_rejected(raw):
    raw["model"]["extracellular"][0]["reservoir"] = True
    raw["model"]["closure"]["gauge_reference"] = None
    with pytest.raises(ConfigError, match="finite closed outside"):
        water.parse(raw)


@pytest.mark.parametrize("version", [True, 0, 2, "1"])
def test_schema_version_remains_strict(raw, version):
    raw["schema_version"] = version
    with pytest.raises(ConfigError):
        water.parse(raw)


def test_wrong_model_identifier_is_rejected(raw):
    raw["model"]["id"] = prior.MODEL_ID
    with pytest.raises(ConfigError, match="resolved_water@1"):
        water.parse(raw)


def test_existing_ionic_ownership_and_charge_checks_are_retained(raw):
    raw["model"]["cells"][0]["fixed_charge_equivalent_fmol"] += 1.0
    with pytest.raises(ConfigError, match="charge anchor"):
        water.parse(raw)


def test_failed_parse_does_not_modify_inputs(raw):
    raw["model"]["water_membranes"][0]["hydraulic_permeability_m_per_Pa_s"] = -1.0
    untouched = deepcopy(raw)
    with pytest.raises(ConfigError):
        water.parse(raw)
    assert raw == untouched
