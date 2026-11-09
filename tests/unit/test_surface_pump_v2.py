"""resolved_pump_tissue@2: resolved_pump_tissue@1 plus the plasma-membrane Ca-ATPase.

Equivalence: with no calcium pump the identity reproduces resolved_pump_tissue@1
(RK4 and IMEX). Law: ca_atp_mass_action_positive@1 is the existing Cells PMCA
kernel with a 1 M standard state. With calcium: exact explicit/implicit split,
material, charge, energy and metabolic ledgers, order of the IMEX schemes,
bitwise restart, definition errors and CPU/L4 agreement on small fixtures.
"""

import os

import jax
import numpy as np
import pytest

from cells.core.errors import NumericalError
from cells.core.runner import run
from cells.core.specs import ConfigError, parse_spec
from cells.core.surface_pump_v2_spec import control_values
from cells.io import load_snapshot, write_snapshot
from cells.models import surface_pump, surface_pump_v2
from cells.models.registry import get_model
from cells.numerics import surface_imex as imex
from cells.processes import calcium_atpase, er_calcium, plasma_calcium
from cells.processes.electrochemistry import R
from validation.tissue import surface_pump_fixtures as first
from validation.tissue import surface_pump_v2_fixtures as fixtures

BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
SOLVERS = (imex.EULER_ID, imex.ARS222_ID)
CALCIUM = surface_pump_v2.CALCIUM_STATE_FIELDS
CALCIUM_OBSERVATIONS = (
    *CALCIUM,
    "calcium_pump_cycle_rate_fmol_s",
    "calcium_pump_affinity_J_mol",
    "calcium_metabolic_power_pJ_s",
    "calcium_pump_availability",
)


@pytest.fixture(scope="module", autouse=True)
def x64():
    jax.config.update("jax_enable_x64", True)


def scaled_difference(a, b):
    a, b = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    scale = max(np.max(np.abs(a), initial=0), np.max(np.abs(b), initial=0))
    return 0.0 if scale == 0 else float(np.max(np.abs(a - b)) / scale)


def initial(raw):
    spec = parse_spec(raw)
    state, layout = get_model(spec.model).initial_values(spec)
    controls = control_values(spec, [0.0])
    return spec, state, layout, type(controls)(*(v[0] for v in controls))


@pytest.mark.parametrize("solver", ["rk4", *SOLVERS])
@pytest.mark.parametrize("arm", ["open", "clamped", "release"])
def test_without_calcium_pump_reproduces_resolved_pump_tissue_1(arm, solver):
    """Same states and observations as @1 to roundoff; the calcium ledgers stay zero.

    The calcium terms are exact zeros, so only compiled operation order can differ
    (observed: RK4 bitwise; IMEX up to 4e-14 of an array's magnitude, in the small
    net face transfers). The bound is the family's 1e-12 equivalence bound.
    """
    spec = parse_spec(fixtures.definition(arm, solver=solver, calcium=False))
    assert get_model(spec.model) is surface_pump_v2
    assert parse_spec(spec.to_dict()) == spec
    reference = parse_spec(first.definition(arm, solver=solver))
    assert get_model(reference.model) is surface_pump
    a, b = run(spec), run(reference)
    for key in surface_pump.STATE_TYPE._fields:
        assert scaled_difference(getattr(a.history, key), getattr(b.history, key)) <= 1e-12, key
    for key, value in vars(b.observations).items():
        if key in ("charge_residual_C", "component_current_residual_A", "energy_balance_pJ_s"):
            continue  # Roundoff-level constraint residuals.
        assert scaled_difference(getattr(a.observations, key), value) <= 1e-12, key
    for key in CALCIUM_OBSERVATIONS:
        assert not np.any(getattr(a.observations, key)), key
    assert a.diagnostics.keys() == b.diagnostics.keys()


def test_law_is_the_existing_pmca_kernel_with_a_molar_standard_state():
    rng = np.random.default_rng(7)
    size = 64
    ci, co = rng.uniform(1e-5, 1e-3, size), rng.uniform(0.5, 3.0, size)
    voltage, temperature = rng.uniform(-0.1, 0.05, size), rng.uniform(280, 320, size)
    p = calcium_atpase.Parameters(
        rng.uniform(0, 1, size), *(rng.uniform(0.05, 3, size) for _ in range(3)),
        rng.uniform(1e-4, 1e-2, size), rng.uniform(0.1, 1, size), rng.uniform(-45e3, -20e3, size),
    )  # fmt: skip
    rate = calcium_atpase.kinetics(ci, co, voltage, temperature, p, 0.8, xp=np)
    legacy = er_calcium.PumpParameters(
        p.capacity_fmol_s, p.km_ca_mM, p.km_atp_mM, p.atp_mM, p.adp_mM, p.pi_mM,
        p.delta_g0_J_mol - R * temperature * np.log(1000.0),
    )  # fmt: skip
    cycles, energy, drive = plasma_calcium.pump_rates(
        ci, co, voltage, temperature, legacy, 0.8, xp=np
    )
    np.testing.assert_array_equal(rate.cycles_fmol_s, cycles)
    np.testing.assert_array_equal(rate.cycle_free_energy_J_mol, energy)
    np.testing.assert_allclose(rate.chemical_drive_J_mol, drive, rtol=1e-14)
    # Extrusion against the gradient when hydrolysis wins; zero at equilibrium.
    assert np.all(np.sign(rate.cycles_fmol_s) == -np.sign(energy))
    mu = R * temperature * (np.log(ci) - np.log(co)) + 2 * 96485.33212331001 * voltage
    np.testing.assert_allclose(energy, rate.chemical_drive_J_mol - mu, rtol=1e-12, atol=1e-6)
    stall = p._replace(delta_g0_J_mol=p.delta_g0_J_mol - energy)
    stalled = calcium_atpase.kinetics(ci, co, voltage, temperature, stall, 1.0, xp=np)
    assert np.max(np.abs(stalled.cycles_fmol_s) / p.capacity_fmol_s) < 1e-9
    assert calcium_atpase.domain_valid(ci, co, voltage, temperature, p, 0.8, xp=np).all()
    neutral = calcium_atpase.Parameters(0.0, 1.0, 1.0, 1000.0, 1.0, 1.0, 0.0)
    assert calcium_atpase.domain_valid(1.0, 1.0, 0.0, 298.15, neutral, 0.0, xp=np)
    for bad in (dict(ci=-1e-4), dict(voltage=0.2), dict(availability=1.5)):
        args = dict(ci=ci, voltage=voltage, availability=0.8) | bad
        assert not calcium_atpase.domain_valid(
            args["ci"], co, args["voltage"], temperature, p, args["availability"], xp=np
        ).all()


@pytest.mark.parametrize(
    "fault",
    [
        "law",
        "role_valence",
        "stoichiometry",
        "missing_membrane_key",
        "missing_controls",
        "unknown_control",
        "duplicate_id",
        "standard_state_kind",
        "negative_km",
    ],
)
def test_definition_errors_reject(fault):
    raw = fixtures.definition("clamped", solver=imex.ARS222_ID)
    m, e = raw["model"], raw["experiment"]
    pump = m["membranes"][0]["calcium_pump"]
    if fault == "law":
        pump["law"] = "nak_atp_mass_action_positive@1"
    elif fault == "role_valence":
        pump["roles"]["calcium"], pump["stoichiometry"] = "K", {"K": -1}
    elif fault == "stoichiometry":
        pump["stoichiometry"]["Ca"] = -2
    elif fault == "missing_membrane_key":
        del m["membranes"][1]["calcium_pump"]
    elif fault == "missing_controls":
        e["calcium_pump_controls"].pop()
    elif fault == "unknown_control":
        e["calcium_pump_controls"][0]["pump_id"] = "calcium_pump_9"
    elif fault == "duplicate_id":
        pump["id"] = "pump_0"
    elif fault == "standard_state_kind":
        pump["metabolism"]["kind"] = "finite_atp_pool@1"
    else:
        pump["km_ca_mM"] = -1e-3
    with pytest.raises(ConfigError):
        parse_spec(raw)


def test_round_trip_and_example_world_without_some_pumps():
    raw = fixtures.definition("open", solver=imex.ARS222_ID)
    raw["model"]["membranes"][2]["calcium_pump"] = None
    raw["experiment"]["calcium_pump_controls"].pop(2)
    spec = parse_spec(raw)
    assert spec.model.membranes[2].calcium_pump is None
    assert parse_spec(spec.to_dict()) == spec
    _, state, p, control = initial(raw)
    assert list(p.calcium_pump_present[:4]) == [True, True, False, True]
    assert control.calcium_pump.shape == (spec.execution.membrane_capacity,)


@pytest.mark.parametrize("arm", ["open", "closed", "clamped"])
def test_explicit_and_implicit_parts_sum_to_the_law(arm):
    """At the law's own potentials, the split rates equal the identity's readouts."""
    spec, state, p, control = initial(fixtures.definition(arm, solver=imex.ARS222_ID))
    law = surface_pump_v2.readouts(state, control, p, xp=np)
    explicit, valid = surface_pump_v2.explicit_rates(
        state, law.field.potential_V, control, p, xp=np
    )
    assert law.valid and valid
    assert np.all(law.derivative.calcium_pump_cycles[:4] > 0)  # Extrusion from the start.
    co = np.where(p.outside_active, p.extracellular_amount_reference / p.extracellular_volume, 1)
    weight, _ = imex.face_weights(co, surface_pump_v2.tissue.field_layout(p).surface, xp=np)
    drift = surface_pump_v2.implicit_rates(weight, law.field.potential_V, state, p, xp=np)
    for key in (
        "amount_increment",
        "extracellular_amount_increment",
        "membrane_transferred",
        "junction_transferred",
        "face_transferred",
        "reservoir_supplied",
        "membrane_dissipated_energy_pJ",
        "junction_dissipated_energy_pJ",
        "junction_gate",
        "pump_cycles",
        "pump_dissipated_energy_pJ",
        "metabolic_work_pJ",
        *CALCIUM,
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


@pytest.mark.parametrize("arm", ["closed", "clamped", "release"])
@pytest.mark.parametrize("solver", SOLVERS)
def test_imex_ledgers_constraints_and_calcium_transfer(arm, solver, imex_runs):
    value = imex_runs[arm, solver]
    d = value.diagnostics
    tol = value.spec.execution.material_balance_atol_fmol
    for key in ("balance", "extracellular_balance", "global_balance"):
        assert d[f"max_{key}_error_fmol"] <= min(tol)
    assert d["max_capacitor_charge_error_C"] <= 3e-25 and d["max_global_charge_error_C"] <= 3e-25
    assert d["max_reservoir_work_error_pJ"] <= 3e-12 and d["max_metabolic_work_error_pJ"] <= 3e-12
    assert d["max_energy_balance_relative"] <= surface_pump_v2.ENERGY_RTOL[solver]
    history, ca = value.history, value.spec.model.species_ids.index("Ca")
    cycles = np.asarray(history.calcium_pump_cycles)
    assert np.all(cycles[-1, :4] > 0) and not np.any(cycles[:, 4:])
    # Each cycle moves one Ca out: the cells' Ca equals leak and junction exchange
    # minus the pump cycles, so the pump changes the inventory it is said to change.
    _, p = surface_pump_v2.initial_values(value.spec)
    leak = np.zeros_like(history.amount_increment[:, ca])
    np.add.at(leak, (slice(None), p.membrane_cell), np.asarray(history.membrane_transferred)[:, ca])
    pumped = np.zeros_like(leak)
    np.add.at(pumped, (slice(None), p.membrane_cell), cycles)
    gap = np.asarray(history.junction_transferred)[:, ca]
    junction = np.zeros_like(leak)
    np.add.at(junction, (slice(None), p.junction_sender), -gap)
    np.add.at(junction, (slice(None), p.junction_receiver), gap)
    expected = -leak - pumped + junction
    np.testing.assert_allclose(history.amount_increment[:, ca], expected, rtol=0, atol=1e-15)
    assert np.all(np.asarray(history.calcium_pump_dissipated_energy_pJ)[-1, :4] > 0)
    assert np.all(np.asarray(history.calcium_metabolic_work_pJ)[-1, :4] > 0)
    if arm == "release":
        before = value.times <= 0.00073
        assert not np.any(history.calcium_pump_cycles[before])
        assert np.all(value.observations.calcium_pump_availability[0] == 0)


@pytest.mark.parametrize("solver, tolerance", [(imex.EULER_ID, 2e-2), (imex.ARS222_ID, 1e-3)])
def test_imex_dissipation_and_work_ledgers_track_rk4(solver, tolerance, imex_runs):
    value, reference = imex_runs["clamped", solver], imex_runs["clamped", "rk4"]
    for key in surface_pump_v2.STATE_TYPE._fields:
        if key.endswith(("_dissipated_energy_pJ", "_work_pJ")):
            expected = np.sum(np.asarray(getattr(reference.final.state, key)))
            actual = np.sum(np.asarray(getattr(value.final.state, key)))
            assert abs(actual - expected) <= tolerance * abs(expected) + 3e-12, key


def test_imex_observed_order_against_rk4_with_calcium():
    """Euler first and ARS(2,2,2) second order in Vm and cytosolic Ca."""
    base = fixtures.definition("clamped")
    base["execution"]["dt"] = 6.25e-6
    base["execution"]["max_steps"] = 1024
    value = run(parse_spec(base))
    ca = value.spec.model.species_ids.index("Ca")
    references = (
        value.observations.membrane_voltage_V[-1],
        value.observations.amount[-1, ca],
    )
    for solver, order in ((imex.EULER_ID, 1), (imex.ARS222_ID, 2)):
        errors = [[], []]
        for dt in (1e-4, 5e-5, 2.5e-5):
            raw = fixtures.definition("clamped", solver=solver)
            raw["execution"]["dt"] = dt
            value = run(parse_spec(raw))
            observed = (
                value.observations.membrane_voltage_V[-1],
                value.observations.amount[-1, ca],
            )
            for row, a, b in zip(errors, observed, references, strict=True):
                row.append(float(np.max(np.abs(a - b))))
        for values in errors:
            rates = np.log2(np.asarray(values[:-1]) / np.asarray(values[1:]))
            assert np.all(rates > order - 0.25), (solver, values)


def test_restart_is_bitwise_and_invalid_controls_refuse_the_step(tmp_path, imex_runs):
    value = imex_runs["clamped", imex.ARS222_ID]
    checkpoint = value.checkpoint_at(0.001)
    write_snapshot(tmp_path / "checkpoint", value.spec, checkpoint)
    loaded = load_snapshot(tmp_path / "checkpoint")
    resumed = run(loaded.spec, loaded.checkpoint)
    for a, b in zip(resumed.history, value.history, strict=True):
        np.testing.assert_array_equal(np.asarray(a), np.asarray(b)[checkpoint.step_index :])
    spec, state, p, control = initial(fixtures.definition("clamped", solver=imex.ARS222_ID))
    bad = control._replace(calcium_pump=np.full_like(control.calcium_pump, 1.01))
    kept, valid = jax.jit(surface_pump_v2.checked_step)(state, 1e-4, bad, p, p.active)
    assert not valid
    for a, b in zip(kept, state, strict=True):
        np.testing.assert_array_equal(np.asarray(a), b)
    with pytest.raises(NumericalError):
        surface_pump_v2.check_values(
            state._replace(calcium_pump_cycles=state.calcium_pump_cycles + 0.01), spec
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
    for key in surface_pump_v2.STATE_TYPE._fields:
        a, b = (np.asarray(getattr(values[k].history, key)) for k in ("cpu", "gpu"))
        assert scaled_difference(a, b) <= 3e-12, key
