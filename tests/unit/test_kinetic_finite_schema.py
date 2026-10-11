"""Version isolation, strict parameter ownership and host-before-allocation guards."""

import copy
from dataclasses import replace

import numpy as np
import pytest

from cells.core.resources import trace_bytes
from cells.core.runner import timeline, validate_checkpoint
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.models import finite_extracellular as old
from cells.models import kinetic_finite_extracellular as model
from cells.models.registry import get_model
from tests.kinetic_finite_fixtures import definition, evidence, spec_for

PLAN, _ = evidence()
CASES = PLAN["cases"]


@pytest.mark.parametrize("case", CASES, ids=lambda c: c["id"])
def test_roundtrip_roles_layout_and_resource_contract(case):
    spec = spec_for(case)
    assert parse_spec(spec.to_dict()) == spec
    assert get_model(spec.model) is model
    state, layout = model.initial_values(spec)
    n = len(case["volume_pL"])
    assert len(state) == 10 and len(layout) == len(old.LAYOUT_TYPE._fields) + 10
    assert all(v.dtype == np.float64 for v in state)
    np.testing.assert_array_equal(layout.pump_present, np.arange(4) < n)
    assert all(np.isfinite(v).all() for v in layout)
    assert np.all(layout.pump_capacity[n:] == 0) and np.all(layout.pump_drive[n:] == 0)
    assert model.domain_valid(state, layout, layout.active, xp=np)
    assert trace_bytes(
        replace(spec, execution=replace(spec.execution, membrane_capacity=20)), 1
    ) > trace_bytes(spec, 1)


@pytest.mark.parametrize(
    "path,value",
    [
        (("law",), "nak_atp_affinity_tanh@1"),
        (("law",), "unknown"),
        (("roles", "sodium"), "K"),
        (("roles", "potassium"), "Cl"),
        (("roles", "sodium"), "unknown"),
        (("stoichiometry", "Na"), -2),
        (("stoichiometry", "K"), True),
        (("stoichiometry", "Cl"), 0),
        (("capacity_fmol_per_s",), -1),
        (("capacity_fmol_per_s",), True),
        (("capacity_fmol_per_s",), float("inf")),
        (("drive_J_per_mol",), -60000),
        (("surface_density",), 1e-7),
        (("km_na_mM",), 0),
        (("km_k_mM",), -1),
        (("km_atp_mM",), False),
        (("metabolism", "kind"), "finite_inventory@1"),
        (("metabolism", "atp_mM"), 0),
        (("metabolism", "adp_mM"), float("nan")),
        (("metabolism", "pi_mM"), False),
        (("metabolism", "delta_g0_J_per_mol"), 1e300),
        (("metabolism", "schedule"), []),
    ],
)
def test_invalid_pump_parameters_refused(path, value):
    raw = definition(CASES[0])
    node = raw["model"]["cells"][0]["membrane"]["pump"]
    for k in path[:-1]:
        node = node[k]
    node[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_missing_fields_temperature_and_duplicate_pump_owner_refused():
    raw = definition(CASES[-1])
    for key in tuple(raw["model"]["cells"][0]["membrane"]["pump"]):
        changed = copy.deepcopy(raw)
        del changed["model"]["cells"][0]["membrane"]["pump"][key]
        with pytest.raises(ConfigError):
            parse_spec(changed)
    for temp in (199.0, 401.0):
        changed = copy.deepcopy(raw)
        changed["model"]["temperature_K"] = temp
        with pytest.raises(ConfigError, match="pump"):
            parse_spec(changed)
    raw["model"]["cells"][1]["membrane"]["pump"]["id"] = "pump_0"
    with pytest.raises(ConfigError, match="unique"):
        parse_spec(raw)


def test_v1_remains_distinct_and_rejects_kinetic_configuration():
    raw = definition(CASES[0])
    v2 = parse_spec(raw)
    raw["model"]["id"] = "finite_extracellular@1"
    with pytest.raises(ConfigError):
        parse_spec(raw)
    p = raw["model"]["cells"][0]["membrane"]["pump"]
    for key in ("metabolism", "km_na_mM", "km_k_mM", "km_atp_mM"):
        del p[key]
    p.update(law="nak_atp_affinity_tanh@1", drive_J_per_mol=-60000.0)
    v1 = parse_spec(raw)
    assert get_model(v1.model) is old and v1.fingerprint != v2.fingerprint
    assert parse_spec(v1.to_dict()) == v1
    raw["model"]["id"] = "finite_extracellular@2"
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("name", model.LAYOUT_TYPE._fields[-10:] + ("pump_drive", "stoichiometry"))
def test_every_new_layout_coefficient_is_checkpoint_owned(name):
    spec = spec_for(CASES[0], end=0.0001)
    cp = initialise(spec)
    value = np.asarray(getattr(cp.layout, name)).copy()
    value.flat[0] = not value.flat[0] if value.dtype == bool else value.flat[0] + 1
    changed = replace(cp, layout=cp.layout._replace(**{name: value}))
    with pytest.raises(ConfigError, match="layout"):
        validate_checkpoint(spec, changed)


def test_resource_and_timestep_rejection_precedes_capacity_allocation(monkeypatch):
    spec = spec_for(CASES[0])
    with pytest.raises(ConfigError, match="0.0001"):
        timeline(replace(spec, execution=replace(spec.execution, dt=0.001)))

    def no_allocate(_):
        raise AssertionError("Capacity allocation must not happen")

    monkeypatch.setattr(model, "initial_values", no_allocate)
    with pytest.raises(ConfigError, match="storage"):
        timeline(replace(spec, execution=replace(spec.execution, capacity=10**8)))
