"""CORE-010 independent equations, explicit ownership and shared-engine tests."""

import copy
from dataclasses import replace

import jax
import jax.numpy as jnp
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.resources import trace_bytes
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.core.state import initialise
from cells.models import spatial_extracellular as model
from cells.numerics.extracellular_field import logmean
from tests import spatial_extracellular_fields as independent
from tests import spatial_extracellular_numerical_checks as checks
from tests.spatial_extracellular_fixtures import (
    canonical,
    definition,
    load_cases,
    load_reference,
    potentials,
    spec_for,
)

PLAN, CASES = load_cases()


def short(name="binary_unequal", end=0.001):
    case = next(c for c in CASES if c.id == name)
    return replace(case, horizon_s=end, controls=(case.controls[0],))


@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_strict_roundtrip_and_complete_independent_stage(case):
    spec = spec_for(case)
    assert parse_spec(spec.to_dict()) == spec
    state, layout = model.initial_values(spec)
    assert len(state) == 6 and all(v.dtype == np.float64 for v in state)
    assert len(set(state._fields + layout._fields)) == len(state) + len(layout)
    initialise(spec)
    held = control_values(spec, [0])[0]
    expected, _ = independent.independent(case, case.controls[0], np.zeros(case.size))
    for xp in (np, jnp):
        y, g, c = jax.device_put((state, layout, held)) if xp is jnp else (state, layout, held)
        rate = model.rhs(y, c, g, g.active, xp=xp)
        np.testing.assert_allclose(
            canonical(case, rate._asdict()), expected, atol=2e-12, rtol=3e-12
        )
        assert model.domain_valid(y, g, g.active, xp=xp)


@pytest.mark.parametrize("dt", [0.000125, 0.0000625])
@pytest.mark.parametrize("case", CASES, ids=lambda c: c.id)
def test_full_frozen_trajectories(case, dt):
    oracle = load_reference(case)
    result = run(spec_for(case, dt=dt, samples=oracle["sample_times_s"]))
    values = canonical(case, vars(result.observations))
    report, phi = checks.inspect(
        case, result.observations.times, oracle["sample_state"], PLAN["accounting_limits"]
    )
    assert report["pass"]
    assert checks.errors(
        case,
        values,
        oracle["sample_state"],
        potentials(case, vars(result.observations)),
        phi,
        PLAN["trajectory_limits"],
    )["pass"]
    native = canonical(case, result.history._asdict())
    report, actual_phi = checks.inspect(case, result.times, native, PLAN["accounting_limits"])
    assert report["pass"]
    expected = checks.replay(case, oracle, "Radau", result.times)
    expected_phi = checks.potential_values(case, result.times, expected)[0]
    assert checks.errors(
        case, native, expected, actual_phi, expected_phi, PLAN["trajectory_limits"]
    )["pass"]
    assert checks.blocked_checks(case, result.times, native)["pass"]
    assert checks.blocked_checks(case, result.observations.times, values)["pass"]


@pytest.mark.parametrize(
    "path,value",
    [
        (("model", "id"), "finite_extracellular@1"),
        (("model", "cells"), []),
        (("model", "extracellular"), []),
        (("model", "extracellular", 0, "id"), "cell"),
        (("model", "extracellular", 0, "volume_pL"), 0),
        (("model", "extracellular", 0, "volume_pL"), 1e-320),
        (("model", "extracellular", 0, "initial_amount_fmol", "Cation"), 0),
        (("model", "extracellular", 0, "initial_amount_fmol", "Cation"), 1e308),
        (("model", "extracellular", 0, "fixed_charge_equivalent_fmol"), 99),
        (("model", "membranes", 0, "outside"), "missing"),
        (("model", "membranes", 0, "inside"), "near"),
        (("model", "membranes", 0, "capacitance_F"), 0),
        (("model", "membranes", 0, "capacitance_F"), 1e-320),
        (("model", "membranes", 0, "initial_voltage_V"), 10),
        (("model", "membranes", 0, "permeability_m_per_s", "Cation"), -1),
        (("model", "membranes", 0, "law"), "other"),
        (("model", "faces", 0, "sender"), "cell"),
        (("model", "faces", 0, "receiver"), "near"),
        (("model", "faces", 0, "area_m2"), 0),
        (("model", "faces", 0, "area_m2"), 1e308),
        (("model", "faces", 0, "length_m"), 1e-320),
        (("model", "faces", 0, "diffusivity_m2_per_s", "Cation"), True),
        (("model", "faces", 0, "law"), "other"),
        (("model", "closure", "law"), "poisson"),
        (("model", "closure", "gauge_reference"), "cell"),
        (("model", "bulk_capacitance"), 1),
        (("execution", "capacity"), 0),
        (("execution", "extracellular_capacity"), 1),
        (("execution", "face_capacity"), 0),
        (("execution", "edge_capacity"), 1),
        (("execution", "field_solver"), "automatic"),
        (("execution", "backend"), "gpu"),
        (("execution", "jit"), 1),
        (("execution", "material_balance_atol_fmol", "Cation"), 1e-9),
        (("experiment", "membrane_controls"), []),
        (("experiment", "membrane_controls", 0, "schedule"), []),
        (("experiment", "membrane_controls", 0, "schedule", 0, "time"), 0.0001),
        (("experiment", "membrane_controls", 0, "schedule", 0, "availability"), 1.01),
        (("experiment", "membrane_controls", 0, "schedule", 0, "availability"), False),
    ],
)
def test_invalid_definition_refused(path, value):
    raw = definition(short())
    target = raw
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = value
    with pytest.raises(ConfigError):
        parse_spec(raw)


@pytest.mark.parametrize("padded", [False, True])
@pytest.mark.parametrize("name", ["single_outside", "pure_bulk", "line_8"])
def test_absent_axes_are_real_not_fake_owners(name, padded):
    case = short(name)
    spec = spec_for(case, padded=padded)
    result = run(spec)
    if not spec.model.cells:
        assert not np.any(result.final.layout.active)
        assert np.all(result.history.amount_increment == 0)
        assert np.all(result.history.membrane_transferred == 0)
        if not padded:
            assert result.history.amount_increment.shape[-1] == 0
    if not spec.model.faces:
        assert np.all(result.history.face_transferred == 0)


@pytest.mark.parametrize("key", model.STATE_TYPE._fields)
def test_every_padding_state_leaf_guarded(key):
    spec = spec_for(short())
    state, layout = model.initial_values(spec)
    getattr(state, key).flat[-1] = 1
    assert not model.domain_valid(state, layout, layout.active, xp=np)
    with pytest.raises(NumericalError):
        model.check_values(state, spec)


def test_duplicate_edges_controls_and_disconnected_graph_refused():
    for key, root in (("faces", "model"), ("membrane_controls", "experiment")):
        raw = definition(short())
        duplicate = copy.deepcopy(raw[root][key][0])
        if key == "faces":
            duplicate["id"] = "another_face"
            duplicate["sender"], duplicate["receiver"] = duplicate["receiver"], duplicate["sender"]
        raw[root][key].append(duplicate)
        with pytest.raises(ConfigError):
            parse_spec(raw)
    raw = definition(short())
    raw["model"]["faces"] = []
    with pytest.raises(ConfigError, match="connected"):
        parse_spec(raw)


@pytest.mark.parametrize(
    "left,right", [(1, 1), (1, 1 + 1e-12), (120, 10), (1e-200, 1e200), (1e308, 1e308)]
)
def test_logmean_positive_symmetric_and_equal_limit(left, right):
    a, b = logmean(np.asarray(left, dtype=float), np.asarray(right, dtype=float), xp=np)
    c, d = logmean(np.asarray(right, dtype=float), np.asarray(left, dtype=float), xp=np)
    assert np.isfinite(a) and a > 0
    np.testing.assert_allclose(a, c, rtol=2e-15)
    assert b == -d
    if left == right:
        assert a == left and b == 0
    else:
        np.testing.assert_allclose(a * b, left - right, rtol=2e-15)


def test_dense_scratch_and_all_axes_enter_resource_guard():
    spec = spec_for(short())
    base = trace_bytes(spec, 4)
    for key in ("capacity", "membrane_capacity", "extracellular_capacity", "face_capacity"):
        larger = replace(
            spec, execution=replace(spec.execution, **{key: getattr(spec.execution, key) + 3})
        )
        assert trace_bytes(larger, 4) > base
    huge = replace(spec, execution=replace(spec.execution, extracellular_capacity=1_000_000))
    with pytest.raises(ConfigError, match="budget|memory|bytes"):
        run(huge)


def test_inherited_step_ceiling_not_weakened():
    spec = spec_for(short(end=0.002), dt=0.00025)
    with pytest.raises(ConfigError, match="0.000125"):
        run(spec)
