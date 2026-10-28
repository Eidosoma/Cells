"""Strict finite-energy ownership, projections and independent control clocks."""

from copy import deepcopy

import numpy as np
import pytest

from cells.core import surface_energy_spec as schema
from cells.core import surface_kinetic_spec as prior
from cells.core.runner import timeline
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.models import surface_energy as model
from cells.models.registry import get_model
from validation.tissue import surface_energy_fixtures as fixtures


@pytest.mark.parametrize("backend", ["cpu", "gpu"])
@pytest.mark.parametrize("padded", [False, True])
def test_registration_roundtrip_and_finite_pool_metabolism(backend, padded):
    raw = fixtures.definition("release", backend=backend, padded=padded)
    original = deepcopy(raw)
    spec = schema.parse(raw)
    assert spec == parse_spec(raw) == schema.parse(schema.to_dict(spec))
    assert spec.to_dict() == raw == original
    assert get_model(spec.model) is model
    assert len(model.STATE_TYPE._fields) == 23
    assert type(spec.model) is schema.SurfaceEnergyModel
    assert type(spec.execution) is schema.Execution
    assert spec.model.membranes[0].pump.metabolism == schema.PoolMetabolism(
        schema.METABOLISM_ID, "energy_0"
    )
    assert set(raw["model"]["membranes"][0]["pump"]["metabolism"]) == {"kind", "pool_id"}


def test_initial_ionic_projection_is_explicit_and_preserves_every_ionic_input():
    raw = fixtures.definition("two_patches", padded=True)
    spec = schema.parse(raw)
    initial = schema.initial_ionic_spec(spec)
    expected = deepcopy(raw)
    expected["model"]["id"] = prior.CAV_MODEL_ID
    pool = expected["model"].pop("energy_pools")[0]
    expected["model"].pop("regeneration_ports")
    expected["experiment"].pop("regeneration_controls")
    expected["execution"].pop("regeneration_capacity")
    for membrane in expected["model"]["membranes"]:
        membrane["pump"]["metabolism"] = dict(
            kind="maintained_chemical_reservoirs@1",
            atp_mM=0.0015,
            adp_mM=0.0001,
            pi_mM=0.0001,
            delta_g0_J_per_mol=pool["delta_g0_J_per_mol"],
        )
    assert initial == prior.parse(expected)
    assert initial.to_dict() == expected
    assert type(initial.model) is prior.SurfaceCavModel
    assert type(initial.execution) is prior.Execution
    assert "energy_pools" in spec.to_dict()["model"]


def test_reordered_species_and_pool_names_remain_explicit():
    raw = fixtures.definition("two_patches")
    raw["model"]["species"].reverse()
    raw["model"]["energy_pools"][0]["id"] = "renamed_pool"
    for patch in raw["model"]["membranes"]:
        patch["pump"]["metabolism"]["pool_id"] = "renamed_pool"
    raw["model"]["regeneration_ports"][0]["pool_id"] = "renamed_pool"
    spec = schema.parse(raw)
    assert spec.model.species_ids == ("Ca", "Cl", "K", "Na")
    assert spec.model.energy_pools[0].id == "renamed_pool"
    assert schema.parse(spec.to_dict()) == spec


def test_regeneration_controls_union_and_right_continuous_padding():
    raw = fixtures.definition("release", padded=True)
    spec = schema.parse(raw)
    times = timeline(spec)
    assert all(t in times for t in (13.3e-6, 17.3e-6, 23.7e-6, 31.1e-6, 37.1e-6, 41.3e-6))
    values = control_values(spec, [0.0, 13.3e-6, 23.7e-6, 31.1e-6, 41.3e-6])
    assert type(values) is schema.Control
    np.testing.assert_array_equal(values.regeneration[:, 0], [0.2, 0.0, 0.0, 0.9, 0.9])
    np.testing.assert_array_equal(values.pump[:, 0], [0.8, 0.8, 0.0, 0.0, 0.7])
    assert not np.any(values.regeneration[:, 1:])
    assert values._fields == ("membrane", "junction", "channel", "pump", "regeneration")


def test_absent_ports_and_pumps_are_explicit_and_supported():
    raw = fixtures.definition()
    raw["model"]["regeneration_ports"] = []
    raw["experiment"]["regeneration_controls"] = []
    raw["execution"]["regeneration_capacity"] = 0
    raw["model"]["membranes"][0]["pump"] = None
    raw["experiment"]["pump_controls"] = []
    spec = schema.parse(raw)
    state, p = model.initial_values(spec)
    controls = control_values(spec, [0.0])
    assert controls.regeneration.shape == (1, 0)
    assert state.regeneration_cycles_fmol.shape == (0,)
    assert not np.any(p.pump_present)
    assert schema.parse(spec.to_dict()) == spec


@pytest.mark.parametrize(
    "fault",
    [
        "missing_pool",
        "duplicate_pool",
        "unknown_cell",
        "duplicate_id",
        "unknown_pool",
        "pool_owner",
        "maintained_fields",
        "pool_temperature",
        "pool_volume",
        "pool_law",
        "port_law",
        "port_owner",
        "duplicate_port",
        "duplicate_control",
        "missing_control",
        "capacity",
        "capacity_bool",
        "pool_nonpositive",
        "pool_nonfinite",
        "pool_bool",
        "port_negative",
        "port_nonfinite",
        "work_negative",
        "metabolism_kind",
        "stoichiometry",
        "temperature",
        "reservoir",
        "model_unknown",
        "schema_bool",
        "schedule_time",
        "schedule_opening",
        "schedule_order",
        "schedule_after_end",
        "schedule_empty",
    ],
)
def test_invalid_finite_energy_definitions_are_rejected_without_mutation(fault):
    raw = fixtures.definition()
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    pool, port, patch = m["energy_pools"][0], m["regeneration_ports"][0], m["membranes"][0]
    if fault == "missing_pool":
        m["energy_pools"] = []
    elif fault == "duplicate_pool":
        m["energy_pools"].append(deepcopy(pool))
    elif fault == "unknown_cell":
        pool["cell_id"] = "unknown"
    elif fault == "duplicate_id":
        port["id"] = pool["id"]
    elif fault in ("unknown_pool", "pool_owner"):
        patch["pump"]["metabolism"]["pool_id"] = "outside_0"
    elif fault == "maintained_fields":
        patch["pump"]["metabolism"]["atp_mM"] = 1.5
    elif fault in ("pool_temperature", "pool_volume"):
        pool["temperature_K" if fault == "pool_temperature" else "volume_pL"] = 2.0
    elif fault == "pool_law":
        pool["law"] = "legacy_numeric_mM"
    elif fault == "port_law":
        port["law"] = "free_ATP"
    elif fault == "port_owner":
        port["pool_id"] = "unknown"
    elif fault == "duplicate_port":
        m["regeneration_ports"].append(deepcopy(port))
    elif fault == "duplicate_control":
        e["regeneration_controls"].append(deepcopy(e["regeneration_controls"][0]))
    elif fault == "missing_control":
        e["regeneration_controls"] = []
    elif fault in ("capacity", "capacity_bool"):
        x["regeneration_capacity"] = 0 if fault == "capacity" else True
    elif fault in ("pool_nonpositive", "pool_nonfinite", "pool_bool"):
        pool["initial_amount_fmol"]["ATP"] = {
            "pool_nonpositive": 0.0,
            "pool_nonfinite": float("inf"),
            "pool_bool": True,
        }[fault]
    elif fault in ("port_negative", "port_nonfinite"):
        port["capacity_fmol_per_s"] = -1.0 if fault == "port_negative" else float("inf")
    elif fault == "work_negative":
        port["supplied_energy_J_per_mol"] = -1.0
    elif fault == "metabolism_kind":
        patch["pump"]["metabolism"]["kind"] = "maintained_chemical_reservoirs@1"
    elif fault == "stoichiometry":
        patch["pump"]["stoichiometry"]["Na"] = -2
    elif fault == "temperature":
        m["temperature_K"] = 310.0
    elif fault == "reservoir":
        m["extracellular"][0]["reservoir"] = True
        m["closure"]["gauge_reference"] = None
    elif fault == "model_unknown":
        m["new_physics"] = True
    elif fault == "schema_bool":
        raw["schema_version"] = True
    elif fault == "schedule_time":
        e["regeneration_controls"][0]["schedule"][0]["time"] = True
    elif fault == "schedule_opening":
        e["regeneration_controls"][0]["schedule"][0]["availability"] = 1.1
    elif fault == "schedule_order":
        e["regeneration_controls"][0]["schedule"].append(dict(time=0.0, availability=0.0))
    elif fault == "schedule_after_end":
        e["regeneration_controls"][0]["schedule"].append(dict(time=1.0, availability=0.0))
    else:
        e["regeneration_controls"][0]["schedule"] = []
    before = deepcopy(raw)
    with np.errstate(all="ignore"), pytest.raises(ConfigError):
        schema.parse(raw)
    assert raw == before


def test_wrong_cell_cannot_consume_a_second_cells_finite_pool():
    raw = fixtures.definition()
    cell = deepcopy(raw["model"]["cells"][0])
    cell["id"] = "cell_1"
    raw["model"]["cells"].append(cell)
    pool = deepcopy(raw["model"]["energy_pools"][0])
    pool.update(id="energy_1", cell_id="cell_1")
    raw["model"]["energy_pools"].append(pool)
    raw["model"]["membranes"][0]["pump"]["metabolism"]["pool_id"] = "energy_1"
    with pytest.raises(ConfigError, match="inside cell"):
        schema.parse(raw)
