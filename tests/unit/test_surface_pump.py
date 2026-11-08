"""resolved_pump_tissue@1 and the factored field (surface_field solver version 2).

Equivalence: the factored solver reproduces version 1 on every surface-field
protocol case, and the RK4 identity reproduces resolved_tissue@2 with no
channels. IMEX: exact explicit/implicit split, family ledgers, observed order,
bitwise restart, step refusal and CPU/L4 agreement on the small fixtures.
"""

import json
import os
from pathlib import Path

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.schedule import control_values
from cells.core.specs import ConfigError, parse_spec
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_kinetic, surface_pump
from cells.models.registry import get_model
from cells.numerics import surface_field as field
from cells.numerics import surface_imex as imex
from cells.numerics import surface_transport as surface
from validation.tissue import surface_field_fixtures
from validation.tissue import surface_pump_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
EXCLUDED = {"charge_residual_C", "charge_normalized", "component_current_residual_A"}
EXCLUDED |= {"current_normalized", "energy_balance_pJ_s", "iterations", "converged", "rates"}


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def physical(values):
    result = {k: np.asarray(v) for k, v in values._asdict().items() if k not in EXCLUDED}
    result.update(
        {"rates__" + k: np.asarray(v) for k, v in values.rates._asdict().items() if k != "valid"}
    )
    return result


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def protocol_floor(name):
    """Declared absolute comparison floors of the surface-field protocol, by unit."""
    tol = json.loads(
        Path(surface_field_fixtures.__file__).with_name("surface_field_protocol.json").read_text()
    )
    tol = tol["tolerances"]
    for suffix, key in (
        ("_V_s", "voltage_rate_atol_V_s"),
        ("_V", "voltage_atol_V"),
        ("_C", "charge_atol_C"),
        ("_J_mol", "chemical_potential_atol_J_mol"),
        ("_A", "current_comparison_atol_A"),
        ("_pJ_s", "power_atol_pJ_s"),
        ("_pJ", "energy_atol_pJ"),
    ):
        if name.endswith(suffix):
            return tol[key]
    return tol["flux_atol_fmol_s"]


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("name", surface_field_fixtures.CASES)
def test_factored_field_matches_dense_solver(name):
    """Each output agrees within 1e-12 of its own magnitude, on device and host."""
    *args, dense = surface_field_fixtures.arrays(surface_field_fixtures.definition(name))
    factored = field.bind(dense.surface, dense.gauge_mask, solver=field.FACTORED_SOLVER_ID)
    assert type(factored) is field.FactoredLayout
    for key in field.Layout._fields[1:]:
        np.testing.assert_array_equal(getattr(factored, key), getattr(dense, key))
    device = jax.devices(BACKEND)[0]
    solve = jax.jit(field.solve)
    on_device = [solve(*jax.device_put((*args, p), device)) for p in (dense, factored)]
    on_host = [field.solve(*args, p, xp=np) for p in (dense, factored)]
    for a, b in (jax.tree.map(np.asarray, on_device), on_host):
        assert a.converged and b.converged and a.iterations == b.iterations
        for key, value in physical(a).items():
            # 1e-12 of each output's magnitude, above the protocol's unit floors
            # (sums such as the reservoir supply charge cancel to roundoff).
            other = physical(b)[key]
            bound = 1e-12 * np.max(np.abs(other), initial=0) + protocol_floor(key)
            assert np.max(np.abs(value - other), initial=0) <= bound, (name, key)


def test_cholesky_solve_host_and_device_match_dense_solve():
    rng = np.random.default_rng(3)
    a = rng.normal(size=(150, 150))
    matrix = a @ a.T + 150 * np.eye(150)
    rhs = rng.normal(size=(150, 3))
    factor = np.linalg.cholesky(matrix)
    expected = np.linalg.solve(matrix, rhs)
    for xp in (np, jax.numpy):
        actual = np.asarray(field.cholesky_solve(factor, rhs, xp=xp))
        np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-14)
        vector = np.asarray(field.cholesky_solve(factor, rhs[:, 0], xp=xp))
        np.testing.assert_allclose(vector, expected[:, 0], rtol=1e-12, atol=1e-14)


def test_node_bounds_by_solver_version():
    assert field.NODE_BOUNDS == {field.SOLVER_ID: 256, field.FACTORED_SOLVER_ID: 2048}
    n, o = 1, 299
    layout = surface.Layout(
        np.asarray(298.15),
        np.asarray([[1.0], [-1.0]]),
        np.ones(n, bool),
        np.ones(o, bool),
        np.arange(o) == 0,
        np.ones(1, bool),
        np.zeros(1, np.int64),
        np.ones(1, np.int64),
        np.ones(1),
        np.ones(1) * 1e-12,
        np.ones((2, 1)) * 1e-9,
        np.ones(o - 1, bool),
        np.arange(o - 1),
        np.arange(1, o),
        np.ones((2, o - 1)) * 1e-19,
        np.zeros(0, bool),
        np.zeros(0, np.int64),
        np.zeros(0, np.int64),
        np.zeros(0),
        np.zeros((2, 0)),
    )
    gauge = np.zeros(o, bool)
    with pytest.raises(ValueError, match="node limit"):
        field.bind(layout, gauge)
    assert type(field.bind(layout, gauge, solver=field.FACTORED_SOLVER_ID)) is field.FactoredLayout
    with pytest.raises(ValueError, match="Unknown"):
        field.bind(layout, gauge, solver="dense_inverse@1")


@pytest.mark.parametrize("arm", ["open", "clamped"])
def test_rk4_identity_reproduces_resolved_tissue_2_without_channels(arm):
    """Factored field and neutral gate ID: same trajectory as the dense identity."""
    spec = parse_spec(fixtures.definition(arm))
    assert get_model(spec.model) is surface_pump
    assert parse_spec(spec.to_dict()) == spec
    reference = parse_spec(fixtures.reduction(arm))
    assert get_model(reference.model) is surface_kinetic
    a, b = run(spec), run(reference)
    for key in surface_pump.STATE_TYPE._fields:
        assert scaled_difference(getattr(a.history, key), getattr(b.history, key)) <= 1e-12, key
    for key, value in vars(a.observations).items():
        if key in EXCLUDED:  # Roundoff-level constraint residuals.
            continue
        other = np.asarray(getattr(b.observations, key))
        bound = 1e-12 * np.max(np.abs(other), initial=0) + protocol_floor(key)
        assert np.max(np.abs(np.asarray(value) - other), initial=0) <= bound, key


@pytest.mark.parametrize(
    "fault",
    [
        "cold",
        "hot",
        "old_gate_law",
        "channels",
        "channel_capacity",
        "dense_field",
        "solver",
        "pump_role",
        "pump_controls",
        "gate_threshold",
    ],
)
def test_definition_errors_reject(fault):
    raw = fixtures.definition("clamped", solver=imex.ARS222_ID)
    m, e, x = raw["model"], raw["experiment"], raw["execution"]
    if fault == "cold":
        m["temperature_K"] = 199.0
    elif fault == "hot":
        m["temperature_K"] = 400.5
    elif fault == "old_gate_law":
        m["junctions"][0]["gate"]["law"] = "betse_rate_junction_relaxation@1"
    elif fault == "channels":
        m["channels"] = []
    elif fault == "channel_capacity":
        x["channel_capacity"] = 0
    elif fault == "dense_field":
        x["field_solver"] = field.SOLVER_ID
    elif fault == "solver":
        x["solver"] = "implicit_euler@1"
    elif fault == "pump_role":
        m["membranes"][0]["pump"]["roles"]["sodium"] = "Cl"
    elif fault == "pump_controls":
        e["pump_controls"].pop()
    else:
        m["junctions"][0]["gate"]["threshold_voltage_V"] = -0.001
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_temperature_domain_admits_physiological_temperature():
    spec = parse_spec(fixtures.definition("clamped", temperature_K=310.0))
    assert spec.model.temperature_K == 310.0
    assert parse_spec(spec.to_dict()) == spec


@pytest.mark.parametrize("arm", ["open", "closed", "clamped"])
def test_explicit_and_implicit_parts_sum_to_the_law(arm):
    """At the law's own potentials, the split rates equal resolved kinetic rates."""
    spec, state, p, control = initial(fixtures.definition(arm, solver=imex.ARS222_ID))
    law = surface_kinetic.readouts(state, control, p, xp=np)
    explicit, valid = surface_pump.explicit_rates(state, law.field.potential_V, control, p, xp=np)
    assert law.valid and valid
    co = np.where(p.outside_active, (p.extracellular_amount_reference) / p.extracellular_volume, 1)
    weight, _ = imex.face_weights(co, surface_pump.tissue.field_layout(p).surface, xp=np)
    drift = surface_pump.implicit_rates(weight, law.field.potential_V, state, p, xp=np)
    for key in (
        "amount_increment",
        "extracellular_amount_increment",
        "membrane_transferred",
        "junction_transferred",
        "face_transferred",
        "reservoir_supplied",
        "junction_gate",
        "pump_cycles",
        "pump_dissipated_energy_pJ",
        "metabolic_work_pJ",
    ):
        total = getattr(explicit, key) + getattr(drift, key)
        assert scaled_difference(total, getattr(law.derivative, key)) <= 1e-13, key


@pytest.fixture(scope="module")
def imex_runs():
    runs = {
        (arm, solver): run(parse_spec(fixtures.definition(arm, solver=solver, backend=BACKEND)))
        for arm in ("closed", "clamped", "release")
        for solver in SOLVERS
    }
    runs["clamped", "rk4"] = run(parse_spec(fixtures.definition("clamped", backend=BACKEND)))
    return runs


@pytest.mark.parametrize("solver, tolerance", [(imex.EULER_ID, 2e-2), (imex.ARS222_ID, 1e-3)])
def test_imex_dissipation_and_work_ledgers_track_rk4(solver, tolerance, imex_runs):
    """Each energy ledger total, including the applied-flux face heat, follows RK4."""
    value, reference = imex_runs["clamped", solver], imex_runs["clamped", "rk4"]
    for key in surface_pump.STATE_TYPE._fields:
        if key.endswith(("_dissipated_energy_pJ", "_work_pJ")):
            expected = np.sum(np.asarray(getattr(reference.final.state, key)))
            actual = np.sum(np.asarray(getattr(value.final.state, key)))
            assert abs(actual - expected) <= tolerance * abs(expected) + 3e-12, key


@pytest.mark.parametrize("arm", ["closed", "clamped", "release"])
@pytest.mark.parametrize("solver", SOLVERS)
def test_imex_ledgers_constraints_and_law_field(arm, solver, imex_runs):
    value = imex_runs[arm, solver]
    d = value.diagnostics
    tol = value.spec.execution.material_balance_atol_fmol
    for key in ("balance", "extracellular_balance", "global_balance"):
        assert d[f"max_{key}_error_fmol"] <= min(tol)
    assert d["max_capacitor_charge_error_C"] <= 3e-25 and d["max_global_charge_error_C"] <= 3e-25
    assert d["max_reservoir_work_error_pJ"] <= 3e-12 and d["max_metabolic_work_error_pJ"] <= 3e-12
    assert d["max_energy_balance_relative"] <= surface_pump.ENERGY_RTOL[solver]
    reservoir = np.asarray(value.final.layout.reservoir)
    assert not np.any(value.history.extracellular_amount_increment[..., reservoir])
    if arm == "closed":
        assert not np.any(value.history.reservoir_supplied)
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(value.history.junction_transferred[before])
        assert not np.any(value.history.pump_cycles[before])
    # Every accepted state carries a converged law field (observe_history checks).
    assert np.all(np.isfinite(value.observations.membrane_voltage_V))


def test_imex_observed_order_against_rk4():
    """Euler is first order and ARS(2,2,2) second order on the clamped fixture.

    The voltage error against RK4 and the relative energy-identity residual
    (which the declared IMEX energy bound admits) both converge at that order.
    RK4 itself keeps the family's absolute energy bound with no relative term.
    """
    base = fixtures.definition("clamped")
    base["execution"]["dt"] = 6.25e-6
    base["execution"]["max_steps"] = 1024
    value = run(parse_spec(base))
    assert surface_pump.ENERGY_RTOL["rk4"] == 0.0
    assert value.diagnostics["max_energy_balance_error_pJ"] <= 2e-8
    reference = value.observations.membrane_voltage_V[-1]
    for solver, order in ((imex.EULER_ID, 1), (imex.ARS222_ID, 2)):
        errors, energy = [], []
        for dt in (1e-4, 5e-5, 2.5e-5):
            raw = fixtures.definition("clamped", solver=solver)
            raw["execution"]["dt"] = dt
            value = run(parse_spec(raw))
            vm = value.observations.membrane_voltage_V[-1]
            errors.append(float(np.max(np.abs(vm - reference))))
            energy.append(value.diagnostics["max_energy_balance_relative"])
        for values in (errors, energy):
            rates = np.log2(np.asarray(values[:-1]) / np.asarray(values[1:]))
            assert np.all(rates > order - 0.25), (solver, values)


def test_imex_restart_is_bitwise_and_invalid_controls_refuse_the_step(tmp_path, imex_runs):
    value = imex_runs["clamped", imex.ARS222_ID]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    spec, state, p, control = initial(fixtures.definition("clamped", solver=imex.ARS222_ID))
    bad = control._replace(junction=np.full_like(control.junction, 1.01))
    kept, valid = jax.jit(surface_pump.checked_step)(state, 1e-4, bad, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    with pytest.raises(NumericalError):
        surface_pump.check_values(
            state._replace(face_transferred=state.face_transferred + 0.01), spec
        )


def test_global_charge_bound_scales_with_moved_charge_and_catches_injected_error(imex_runs):
    """Rounding of the moved charge passes; an injected charge error fails first here."""
    from cells.processes.electrochemistry import CHARGE_PER_FMOL

    value = imex_runs["clamped", imex.ARS222_ID]
    _, p = surface_kinetic.initial_values(value.spec)
    row = surface_pump.STATE_TYPE(*(np.asarray(v) for v in value.final.state))
    bound = surface_pump.global_charge_bound(row, p)
    assert bound > surface_pump.GLOBAL_CHARGE_ATOL_C  # The clamped arm moves charge.
    reservoir = int(np.flatnonzero(p.reservoir)[0])

    def injected(charge_C):
        # Below the material tolerance, so only the charge accounting can see it.
        supplied = row.reservoir_supplied.copy()
        supplied[0, reservoir] += charge_C / CHARGE_PER_FMOL
        return row._replace(reservoir_supplied=supplied)

    surface_pump.check_values(injected(0.1 * bound), value.spec)
    with pytest.raises(NumericalError, match="global_charge"):
        surface_pump.check_values(injected(10 * bound), value.spec)
    # Large cancelling supply (charge moved, none created): a few-eps residual is
    # admitted, while an error of 1e-10 of the moved charge is far outside.
    moved = np.zeros_like(row.reservoir_supplied)
    na, cl = (value.spec.model.species_ids.index(k) for k in ("Na", "Cl"))
    moved[na, reservoir] = moved[cl, reservoir] = 1e4
    large = surface_pump.global_charge_bound(row._replace(reservoir_supplied=moved), p)
    total = 2e4 * CHARGE_PER_FMOL
    assert 4 * np.finfo(float).eps * total < large < 1e-10 * total


def test_ionic_ensemble_reproduces_the_imex_run(imex_runs):
    """Batch windows (lax.map worlds, 7-step windows) give the plain run's state."""
    from cells.ensemble import ionic

    value = imex_runs["clamped", imex.ARS222_ID]
    raw = value.spec.to_dict()
    spec = ionic.parse_spec(dict(model="ionic_worlds@1", simulation=raw, worlds=2, window_steps=7))
    checkpoints, report = ionic.run(spec, backend=BACKEND)
    for checkpoint in checkpoints.values():
        for a, b in zip(checkpoint.state, value.final.state, strict=True):
            np.testing.assert_array_equal(np.asarray(a), np.asarray(b))
    assert report["physical_model"] == "resolved_pump_tissue@1"
    assert report["final_voltage_axis"] == "membrane_patch"
    np.testing.assert_array_equal(
        report["final_voltage_V"][0], value.observations.membrane_voltage_V[-1, :4]
    )


def test_cpu_and_gpu_trajectories_agree():
    if not any(d.platform == "gpu" for d in jax.devices()):
        pytest.skip("Requires the L4 GPU environment")
    values = {}
    for backend in ("cpu", "gpu"):
        value = run(
            parse_spec(fixtures.definition("clamped", solver=imex.ARS222_ID, backend=backend))
        )
        assert all(v.device.platform == backend for v in value.final.state)
        values[backend] = value
    for key in surface_pump.STATE_TYPE._fields:
        a, b = (np.asarray(getattr(values[k].history, key)) for k in ("cpu", "gpu"))
        assert scaled_difference(a, b) <= 3e-12, key


def test_example_config_parses_and_round_trips():
    root = Path(__file__).resolve().parents[2]
    raw = json.loads((root / "configs/resolved_pump_tissue.json").read_text())
    spec = parse_spec(raw)
    assert spec.model.temperature_K == 310.0 and spec.execution.solver == imex.ARS222_ID
    assert parse_spec(spec.to_dict()) == spec
