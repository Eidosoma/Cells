"""Finite material/energy contracts; JAX prototypes are separately selectable."""

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import finite_energy as energy
from cells.processes import kinetic_pump as pump
from cells.processes.electrochemistry import F, R
from validation.betse.pump_contact import pump_reference
from validation.chemistry import finite_energy_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/chemistry/finite_energy_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
TEMPLATE = pump.Parameters(0.1, 1.5, 0.1, 0.1, 12.0, 0.2, 0.5, -37000.0)


def evidence(name, value):
    if EVIDENCE:
        path = Path(EVIDENCE) / "cpu"
        path.mkdir(parents=True, exist_ok=True)
        (path / ("finite-energy-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def close(actual, expected, key):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def single(amount=(3.0, 0.2, 0.3), volume=2.0, temperature=298.15, delta=-37000.0):
    p = energy.validate_parameters(energy.Parameters(temperature, delta, np.array([True])))
    return np.array(amount, dtype=float)[:, None], np.array([volume]), p


def setup():
    p = energy.validate_parameters(
        energy.Parameters(
            np.array([298.15, 310.0, 298.15]),
            np.array([-37000.0, -35000.0, 0.0]),
            np.array([True, True, False]),
        )
    )
    amount = np.array([[3.0, 4.0, 0.0], [0.2, 0.6, 0.0], [0.3, 0.8, 0.0]])
    volume = np.array([2.0, 3.0, 1.0])
    routes = energy.validate_routes(
        energy.Routes(
            np.array([0, 0, 1, 2]),
            np.array([True, True, True, False]),
        ),
        p,
    )
    supply_routes = energy.validate_routes(
        energy.Routes(
            np.array([0, 1, 1, 2]),
            np.array([True, True, True, False]),
        ),
        p,
    )
    return amount, volume, p, routes, supply_routes


def empty_routes(p):
    return energy.validate_routes(
        energy.Routes(np.array([], dtype=np.int64), np.array([], dtype=bool)), p
    )


@pytest.mark.parametrize(
    ("amount", "volume", "temperature", "delta"),
    [
        ((3.0, 0.2, 0.3), 2.0, 298.15, -37000.0),
        ((1.0, 1.0, 1000.0), 1.0, 298.15, 0.0),
        ((1e-6, 10.0, 50.0), 4.0, 310.0, -20000.0),
        ((10.0, 1e-6, 1e-4), 3.0, 273.15, -37000.0),
        ((2.0, 0.3, 5.0), 0.5, 200.0, -30000.0),
        ((2.0, 0.3, 5.0), 0.5, 400.0, -30000.0),
        ((1e-290, 2e-290, 4e-290), 2.0, 298.15, 0.0),
    ],
)
def test_decimal_chemical_potentials_free_energy_and_volume_derivative(
    amount, volume, temperature, delta
):
    n, v, p = single(amount, volume, temperature, delta)
    assert energy.domain_valid(n, v, p, xp=np)
    actual = energy.thermodynamics(n, v, p, xp=np)
    expected = reference.thermodynamics(amount, volume, temperature, delta)
    for name, key in (
        ("concentration_mM", "concentration_atol_mM"),
        ("chemical_potential_J_mol", "potential_atol_J_mol"),
        ("hydrolysis_free_energy_J_mol", "potential_atol_J_mol"),
        ("free_energy_pJ", "energy_atol_pJ"),
        ("osmolyte_amount_fmol", "material_atol_fmol"),
        ("volume_derivative_pJ_per_pL", "volume_derivative_atol_pJ_per_pL"),
    ):
        close(np.asarray(getattr(actual, name))[..., 0], expected[name], key)
    mu = actual.chemical_potential_J_mol
    close(mu[1] + mu[2] - mu[0], actual.hydrolysis_free_energy_J_mol, "potential_atol_J_mol")


def test_one_molar_standard_state_and_declared_standard_energy_gauge():
    n, volume, p = single()
    values = energy.thermodynamics(n, volume, p, xp=np)
    c = n[:, 0] / volume[0]
    legacy_numeric_mM = -37000 + R * 298.15 * math.log(c[1] * c[2] / c[0])
    close(
        legacy_numeric_mM - values.hydrolysis_free_energy_J_mol,
        R * 298.15 * math.log(1000),
        "potential_atol_J_mol",
    )
    assert energy.STANDARD_STATE_mM == PROTOCOL["standard_state_mM"] == 1000
    assert energy.HYDROLYSIS_STOICHIOMETRY == tuple(PROTOCOL["hydrolysis_stoichiometry"])
    evidence("standard-state", dict(status="passed", protocol=PROTOCOL, transformed_pH_Mg=True))


def test_free_energy_gradients_have_independent_difference_error_bounds():
    n, volume, p = single()
    values = energy.thermodynamics(n, volume, p, xp=np)
    nu = np.array([-1.0, 1.0, 1.0])[:, None]
    h = float(np.min(n)) * 1e-4
    plus = energy.thermodynamics(n + h * nu, volume, p, xp=np).free_energy_pJ
    minus = energy.thermodynamics(n - h * nu, volume, p, xp=np).free_energy_pJ
    finite_difference = (plus - minus) / (2 * h)
    third_bound = 1e-3 * R * 298.15 * np.sum(1 / (n - h) ** 2)
    error_bound = (
        h**2 * third_bound / 6 + 32 * np.finfo(float).eps * max(abs(plus[0]), abs(minus[0])) / h
    )
    assert abs(finite_difference[0] - 1e-3 * values.hydrolysis_free_energy_J_mol[0]) <= error_bound
    h = volume[0] * 1e-4
    plus = energy.thermodynamics(n, volume + h, p, xp=np).free_energy_pJ
    minus = energy.thermodynamics(n, volume - h, p, xp=np).free_energy_pJ
    third_bound = 2e-3 * R * 298.15 * np.sum(n) / (volume[0] - h) ** 3
    error_bound = (
        h**2 * third_bound / 6 + 32 * np.finfo(float).eps * max(abs(plus[0]), abs(minus[0])) / h
    )
    assert abs(((plus - minus) / (2 * h))[0] - values.volume_derivative_pJ_per_pL[0]) <= error_bound


@pytest.mark.parametrize("extent", [-0.1, 0.0, 0.05, 0.2, 0.9])
def test_exact_constant_demand_paths_preserve_material_and_change_drive(extent):
    initial, volume, p = single()
    route = energy.validate_routes(energy.Routes(np.array([0]), np.array([True])), p)
    sealed = empty_routes(p)
    current = initial + np.array([-1.0, 1.0, 1.0])[:, None] * extent
    assert energy.domain_valid(current, volume, p, xp=np)
    residuals = energy.material_balances(
        initial, current, np.array([extent]), route, np.array([]), sealed, p, xp=np
    )
    for residual in residuals:
        close(residual, 0.0, "material_atol_fmol")
    exchange = energy.exchange_rates(np.array([0.17]), route, np.array([]), sealed, p, xp=np)
    values = energy.thermodynamics(current, volume, p, xp=np)
    close(
        energy.chemical_power_pJ_s(exchange.amount_fmol_s, values, xp=np),
        1e-3 * 0.17 * values.hydrolysis_free_energy_J_mol,
        "power_atol_pJ_s",
    )
    expected = reference.thermodynamics(current[:, 0], volume[0], 298.15, -37000)
    close(
        values.hydrolysis_free_energy_J_mol[0],
        expected["hydrolysis_free_energy_J_mol"],
        "potential_atol_J_mol",
    )


def test_multiple_routes_worlds_gross_ledgers_and_declared_order():
    _, _, p, routes, supply_routes = setup()
    demand = np.array([[0.2, -0.03, 0.1, 0.0], [-0.1, 0.07, 0.04, 0.0]])
    supply = np.array([[0.12, 0.03, -0.01, 0.0], [0.02, 0.01, 0.03, 0.0]])
    assert energy.exchange_domain_valid(demand, routes, supply, supply_routes, p, xp=np)
    values = energy.exchange_rates(demand, routes, supply, supply_routes, p, xp=np)
    for world in range(2):
        expected = reference.exchange(demand[world, :3], [0, 0, 1], supply[world, :3], [0, 1, 1], 3)
        separate = energy.exchange_rates(
            demand[world], routes, supply[world], supply_routes, p, xp=np
        )
        for name, actual, one in zip(values._fields, values, separate, strict=True):
            close(actual[world], expected[name], "rate_atol_fmol_s")
            np.testing.assert_array_equal(actual[world], one)
    reversed_values = energy.exchange_rates(
        demand[::-1], routes, supply[::-1], supply_routes, p, xp=np
    )
    for original, reverse in zip(values, reversed_values, strict=True):
        np.testing.assert_array_equal(original[::-1], reverse)
    close(
        values.gross_hydrolysis_fmol_s - values.gross_synthesis_fmol_s,
        values.pump_hydrolysis_fmol_s - values.regeneration_synthesis_fmol_s,
        "rate_atol_fmol_s",
    )
    close(energy.invariants(values.amount_fmol_s, xp=np).adenylate_fmol, 0.0, "rate_atol_fmol_s")
    close(energy.invariants(values.amount_fmol_s, xp=np).phosphorus_fmol, 0.0, "rate_atol_fmol_s")
    # Repeated destinations retain NumPy's declared accumulation order; route
    # permutation is not a promise of commutative floating-point summation.
    repeated = energy.validate_routes(energy.Routes(np.array([0, 0, 0]), np.ones(3, dtype=bool)), p)
    scalar = energy.exchange_rates(
        np.array([1e16, 1.0, -1e16]), repeated, np.array([]), empty_routes(p), p, xp=np
    )
    assert scalar.pump_hydrolysis_fmol_s[0] == 0.0
    evidence(
        "ownership",
        dict(
            status="passed",
            worlds=2,
            active_owners=2,
            ordered_routes=True,
            partition_and_reorder="exact",
            gross_ledgers=True,
        ),
    )


def test_material_ledgers_detect_double_counting():
    initial, _, p, routes, supply_routes = setup()
    demand, supply = np.array([0.2, -0.03, 0.1, 0.0]), np.array([0.12, 0.03, -0.01, 0.0])
    change = energy.exchange_rates(demand, routes, supply, supply_routes, p, xp=np)
    current = initial + change.amount_fmol_s
    for value in energy.material_balances(
        initial, current, demand, routes, supply, supply_routes, p, xp=np
    ):
        close(value, 0.0, "material_atol_fmol")
    wrong = energy.material_balances(
        initial, current, 2 * demand, routes, supply, supply_routes, p, xp=np
    )
    assert np.max(np.abs(wrong.amount_residual_fmol)) > 0.01


@pytest.mark.parametrize("work", [0.0, 40000.0, 65000.0, 80000.0])
@pytest.mark.parametrize("opening", [0.0, 0.3, 1.0])
def test_regeneration_decimal_reference_work_heat_and_reverse_flow(work, opening):
    n, volume, p = single()
    routes = energy.validate_routes(energy.Routes(np.array([0]), np.array([True])), p)
    supply = energy.RegenerationParameters(0.4, work)
    assert energy.regeneration_domain_valid(n, volume, p, routes, supply, opening, xp=np)
    actual = energy.regeneration_rates(n, volume, p, routes, supply, opening, xp=np)
    expected = reference.regeneration(n[:, 0], volume[0], 298.15, -37000, 0.4, work, opening)
    for name, value in zip(actual._fields, actual, strict=True):
        key = (
            "rate_atol_fmol_s"
            if name == "synthesis_fmol_s"
            else (
                "potential_atol_J_mol"
                if name == "reaction_free_energy_J_mol"
                else "power_atol_pJ_s"
            )
        )
        close(value[0], expected[name], key)
    assert actual.dissipated_power_pJ_s[0] >= 0
    close(
        actual.pool_chemical_power_pJ_s + actual.dissipated_power_pJ_s - actual.supplied_power_pJ_s,
        0.0,
        "power_atol_pJ_s",
    )
    if opening == 0:
        assert (
            actual.synthesis_fmol_s[0]
            == actual.supplied_power_pJ_s[0]
            == actual.dissipated_power_pJ_s[0]
            == 0
        )
    elif work == 0:
        assert actual.synthesis_fmol_s[0] < 0 and actual.supplied_power_pJ_s[0] == 0
    elif work == 80000:
        assert actual.synthesis_fmol_s[0] > 0 and actual.supplied_power_pJ_s[0] > 0


def test_zero_supply_reversible_port_and_exact_stall():
    routes = energy.Routes(np.array([0]), np.array([True]))
    for amounts, sign in [
        ((0.01, 20.0, 20.0), 1),
        ((20.0, 0.01, 0.01), -1),
        ((1.0, 1.0, 1000.0), 0),
    ]:
        n, volume, p = single(amounts, 1.0, delta=0.0)
        supply = energy.RegenerationParameters(0.4, 0.0)
        assert energy.regeneration_domain_valid(n, volume, p, routes, supply, 1.0, xp=np)
        rate = energy.regeneration_rates(n, volume, p, routes, supply, 1.0, xp=np)
        assert np.sign(rate.synthesis_fmol_s[0]) == sign
        assert rate.supplied_power_pJ_s[0] == 0.0
        assert rate.dissipated_power_pJ_s[0] >= 0


def test_source_off_recovery_direction_and_fully_sealed_conservation():
    n, volume, p = single()
    routes = energy.Routes(np.array([0]), np.array([True]))
    supply = energy.RegenerationParameters(0.4, 80000.0)
    values = energy.thermodynamics(n, volume, p, xp=np)
    rows = []
    for opening in (0.0, 1.0):
        port = energy.regeneration_rates(n, volume, p, routes, supply, opening, xp=np)
        rates = energy.exchange_rates(
            np.array([0.05]), routes, port.synthesis_fmol_s, routes, p, xp=np
        )
        assert np.sign(rates.amount_fmol_s[0, 0]) == (-1 if opening == 0 else 1)
        assert port.dissipated_power_pJ_s[0] >= 0
        rows.append(
            dict(
                availability=opening,
                atp_rate_fmol_s=float(rates.amount_fmol_s[0, 0]),
                supplied_power_pJ_s=float(port.supplied_power_pJ_s[0]),
            )
        )
    sealed_port = energy.regeneration_rates(n, volume, p, routes, supply, 0.0, xp=np)
    sealed = energy.exchange_rates(
        np.zeros(1), routes, sealed_port.synthesis_fmol_s, routes, p, xp=np
    )
    assert not np.any(sealed.amount_fmol_s)
    assert not np.any(energy.chemical_power_pJ_s(sealed.amount_fmol_s, values, xp=np))
    assert not np.any(sealed_port.supplied_power_pJ_s)
    evidence(
        "supply-port",
        dict(
            status="passed",
            scope="Instantaneous source-off/recovery direction",
            regeneration_law=energy.REGENERATION_LAW_ID,
            cases=rows,
            both_routes_off_exact=True,
            trajectory=False,
        ),
    )


def test_current_volume_and_finite_amounts_drive_existing_pump_without_mutation():
    initial, volume, p = single((3.0, 0.2, 0.2))
    routes = energy.Routes(np.array([0]), np.array([True]))
    first = energy.pump_parameters(initial, volume, p, routes, TEMPLATE, xp=np)
    for actual, expected in zip(first, TEMPLATE, strict=True):
        np.testing.assert_array_equal(np.asarray(actual), np.asarray([expected]))
    moved = initial + np.array([[-0.5], [0.5], [0.5]])
    second = energy.pump_parameters(moved, volume, p, routes, TEMPLATE, xp=np)
    diluted = energy.pump_parameters(moved, 2 * volume, p, routes, TEMPLATE, xp=np)
    close(second.atp_mM, moved[0] / volume, "concentration_atol_mM")
    close(diluted.adp_mM, second.adp_mM / 2, "concentration_atol_mM")
    close(
        pump.chemical_drive(second, 298.15, xp=np),
        energy.thermodynamics(moved, volume, p, xp=np).hydrolysis_free_energy_J_mol,
        "potential_atol_J_mol",
    )
    assert not np.array_equal(
        pump.chemical_drive(first, 298.15, xp=np), pump.chemical_drive(second, 298.15, xp=np)
    )
    assert TEMPLATE == pump.Parameters(0.1, 1.5, 0.1, 0.1, 12.0, 0.2, 0.5, -37000.0)


def test_existing_pump_decimal_bridge_and_closed_energy_without_maintained_work():
    n, volume, p, routes, sealed = setup()
    template = TEMPLATE._replace(capacity_fmol_s=np.array([0.1, 0.2, 0.3, 0.0]))
    parameters = energy.pump_parameters(n, volume, p, routes, template, xp=np)
    temperature = p.temperature_K[routes.owner]
    voltage = np.array([-0.4, -0.08, 0.06, 0.0])
    mu_na = np.where(routes.active, R * temperature * np.log(12.0 / 140) + F * voltage, 0.0)
    mu_k = np.where(routes.active, R * temperature * np.log(140.0 / 4) + F * voltage, 0.0)
    assert pump.domain_valid(12.0, 4.0, mu_na, mu_k, temperature, parameters, 1.0, xp=np).all()
    rate = pump.kinetics(12.0, 4.0, mu_na, mu_k, temperature, parameters, 1.0, xp=np)
    assert rate.cycles_fmol_s[0] < 0 and rate.cycles_fmol_s[1] > 0 and rate.cycles_fmol_s[3] == 0
    for i in range(3):
        case = pump_reference.BASE | dict(
            id=f"finite-pool-route-{i}",
            temperature_K=float(temperature[i]),
            voltage_V=float(voltage[i]),
            atp_mM=float(parameters.atp_mM[i]),
            adp_mM=float(parameters.adp_mM[i]),
            pi_mM=float(parameters.pi_mM[i]),
            delta_g0_J_mol=float(parameters.delta_g0_J_mol[i]),
            alpha_mol_m2_s=float(parameters.capacity_fmol_s[i]) / 1e6,
        )
        expected = pump_reference.oracle(case, dict(F=F, R=R))
        close(rate.cycles_fmol_s[i], -expected["na_in_fmol_s"] / 3, "rate_atol_fmol_s")
    empty = empty_routes(p)
    exchange = energy.exchange_rates(rate.cycles_fmol_s, routes, np.array([]), empty, p, xp=np)
    chemical = energy.chemical_power_pJ_s(
        exchange.amount_fmol_s, energy.thermodynamics(n, volume, p, xp=np), xp=np
    )
    ionic = 1e-3 * rate.cycles_fmol_s * (-3 * mu_na + 2 * mu_k)
    heat = -1e-3 * rate.cycles_fmol_s * rate.cycle_free_energy_J_mol
    assert np.min(heat) >= 0
    close(np.sum(chemical) + np.sum(ionic) + np.sum(heat), 0.0, "power_atol_pJ_s")
    evidence(
        "pump-bridge",
        dict(
            status="passed",
            decimal_routes=3,
            finite_pool_energy=True,
            closed_energy_residual_pJ_s=float(np.sum(chemical) + np.sum(ionic) + np.sum(heat)),
            maintained_reservoir_work_counted=False,
        ),
    )


def test_bridge_gathers_matching_temperature_for_heterogeneous_worlds_and_owners():
    n, volume, original, routes, _ = setup()
    p = energy.validate_parameters(
        energy.Parameters(
            np.array([[298.15, 310.0, 298.15], [305.0, 290.0, 298.15]]),
            original.delta_g0_J_mol,
            original.active,
        )
    )
    n = np.stack((n, n * np.array([1.2, 0.8, 1.0])))
    volume = np.stack((volume, volume))
    stage = energy.pump_parameters(n, volume, p, routes, TEMPLATE, xp=np)
    temperature = np.where(routes.active, np.take(p.temperature_K, routes.owner, axis=-1), 298.15)
    expected = energy.thermodynamics(n, volume, p, xp=np).hydrolysis_free_energy_J_mol[
        ..., routes.owner
    ]
    close(pump.chemical_drive(stage, temperature, xp=np), expected, "potential_atol_J_mol")
    assert temperature.shape == (2, 4)
    assert not np.allclose(pump.chemical_drive(stage, 298.15, xp=np), expected)


@pytest.mark.parametrize(
    "fault",
    [
        "zero",
        "negative",
        "nan",
        "infinity",
        "boolean",
        "shape",
        "volume",
        "padding-amount",
        "padding-volume",
    ],
)
def test_invalid_pool_states_reject_without_clipping_even_with_no_routes(fault):
    n, volume, p, _, _ = setup()
    original = n.copy()
    if fault in ("zero", "negative", "nan", "infinity"):
        n[0, 0] = dict(zero=0.0, negative=-1.0, nan=np.nan, infinity=np.inf)[fault]
    elif fault == "boolean":
        n = np.ones_like(n, dtype=bool)
    elif fault == "shape":
        n = n[:2]
    elif fault == "volume":
        volume[0] = 0.0
    elif fault == "padding-amount":
        n[1, 2] = 0.1
    else:
        volume[2] = 2.0
    before = n.copy()
    assert not energy.domain_valid(n, volume, p, xp=np)
    np.testing.assert_array_equal(n, before)
    assert original[0, 0] == 3.0


@pytest.mark.parametrize("temperature", [199.0, 401.0, np.nan, np.inf, True, "298.15"])
def test_invalid_temperature_parameters(temperature):
    with pytest.raises(ValueError):
        energy.validate_parameters(energy.Parameters(temperature, -37000.0, np.array([True])))


@pytest.mark.parametrize("delta", [np.nan, np.inf, True, "-37000"])
def test_invalid_standard_potential_parameters(delta):
    with pytest.raises(ValueError):
        energy.validate_parameters(energy.Parameters(298.15, delta, np.array([True])))


@pytest.mark.parametrize(
    "fault",
    [
        "boolean-owner",
        "negative-owner",
        "overflow-owner",
        "inactive-owner",
        "mask-type",
        "shape",
        "nonzero-padding",
        "nonfinite-rate",
    ],
)
def test_invalid_route_ownership_masks_and_cycle_arrays(fault):
    _, _, p, routes, supply_routes = setup()
    owner, active = routes.owner.copy(), routes.active.copy()
    rates = np.array([0.2, 0.1, -0.03, 0.0])
    if fault == "boolean-owner":
        owner = owner.astype(bool)
    elif fault == "negative-owner":
        owner[0] = -1
    elif fault == "overflow-owner":
        owner[0] = len(p.active)
    elif fault == "inactive-owner":
        owner[0] = 2
    elif fault == "mask-type":
        active = active.astype(int)
    elif fault == "shape":
        active = active[:-1]
    elif fault == "nonzero-padding":
        rates[-1] = 0.1
    else:
        rates[0] = np.nan
    bad = energy.Routes(owner, active)
    if fault not in ("nonzero-padding", "nonfinite-rate"):
        with pytest.raises(ValueError):
            energy.validate_routes(bad, p)
    assert not energy.exchange_domain_valid(rates, bad, np.zeros(4), supply_routes, p, xp=np)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("capacity", -1.0),
        ("capacity", True),
        ("capacity", np.inf),
        ("capacity", 1e308),
        ("work", -1.0),
        ("work", np.inf),
        ("work", np.nan),
        ("work", True),
        ("work", 1e308),
        ("availability", -0.1),
        ("availability", 1.1),
        ("availability", True),
        ("availability", np.nan),
    ],
)
def test_invalid_regeneration_ports_and_output_overflow(field, value):
    n, volume, p = single()
    routes = energy.Routes(np.array([0]), np.array([True]))
    data = dict(capacity=0.4, work=80000.0, availability=1.0)
    data[field] = value
    supply = energy.RegenerationParameters(data["capacity"], data["work"])
    assert not energy.regeneration_domain_valid(
        n, volume, p, routes, supply, data["availability"], xp=np
    )


def test_exhaustion_is_rejected_for_both_forward_and_reverse_extents():
    n, volume, p = single()
    routes = energy.Routes(np.array([0]), np.array([True]))
    for extent in (3.0, -0.2):
        exhausted = n + np.array([-1.0, 1.0, 1.0])[:, None] * extent
        assert not energy.domain_valid(exhausted, volume, p, xp=np)
        assert not energy.regeneration_domain_valid(
            exhausted, volume, p, routes, energy.RegenerationParameters(0.0, 0.0), 0.0, xp=np
        )


def test_explicit_inactive_padding_and_empty_routes_are_neutral():
    p = energy.validate_parameters(energy.Parameters(298.15, 0.0, np.array([False])))
    n, volume = np.zeros((3, 1)), np.ones(1)
    assert energy.domain_valid(n, volume, p, xp=np)
    empty = empty_routes(p)
    values = energy.thermodynamics(n, volume, p, xp=np)
    for value in values:
        assert np.isfinite(value).all() and not np.any(value)
    assert energy.exchange_domain_valid(np.array([]), empty, np.array([]), empty, p, xp=np)
    assert not np.any(
        energy.exchange_rates(np.array([]), empty, np.array([]), empty, p, xp=np).amount_fmol_s
    )
    inactive = energy.validate_routes(energy.Routes(np.array([0]), np.array([False])), p)
    assert energy.regeneration_domain_valid(
        n, volume, p, inactive, energy.RegenerationParameters(0.0, 0.0), 0.0, xp=np
    )


@pytest.mark.parametrize("engine", ["eager", "jit", "vmap"])
def test_jax_world_broadcast_and_dynamic_leaves(engine):
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    n, volume, p, routes, supply_routes = setup()
    n = np.stack((n, n * np.array([1.2, 0.8, 1.0])))
    volume = np.stack((volume, volume))
    supply = energy.RegenerationParameters(
        np.array([0.4, 0.3, 0.2, 0.0]), np.array([80000.0, 65000.0, 0.0, 0.0])
    )
    opening = np.array([1.0, 0.7, 0.4, 0.0])
    demand = np.array([0.2, -0.03, 0.1, 0.0])

    def apply(a, v, parameters, support, *, xp):
        thermo = energy.thermodynamics(a, v, parameters, xp=xp)
        regen = energy.regeneration_rates(
            a, v, parameters, supply_routes, support, xp.asarray(opening), xp=xp
        )
        exchange = energy.exchange_rates(
            xp.asarray(demand), routes, regen.synthesis_fmol_s, supply_routes, parameters, xp=xp
        )
        return (
            thermo,
            regen,
            exchange,
            energy.regeneration_domain_valid(
                a, v, parameters, supply_routes, support, xp.asarray(opening), xp=xp
            ),
        )

    def compute(a, v, parameters, support):
        return apply(a, v, parameters, support, xp=jnp)

    if engine == "jit":
        compute = jax.jit(compute)
    elif engine == "vmap":
        compute = jax.vmap(compute, in_axes=(0, 0, None, None))
    dynamic = energy.Parameters(*(jnp.asarray(v) for v in p))
    support = energy.RegenerationParameters(*(jnp.asarray(v) for v in supply))
    actual = compute(jnp.asarray(n), jnp.asarray(volume), dynamic, support)
    expected = apply(n, volume, p, supply, xp=np)
    for actual_leaf, expected_leaf in zip(
        jax.tree.leaves(actual[:3]), jax.tree.leaves(expected[:3]), strict=True
    ):
        np.testing.assert_allclose(
            actual_leaf, expected_leaf, rtol=TOL["relative"], atol=TOL["potential_atol_J_mol"]
        )
    assert np.asarray(actual[3]).all() and np.asarray(expected[3]).all()
    changed = compute(
        jnp.asarray(n),
        jnp.asarray(volume),
        dynamic,
        support._replace(capacity_fmol_s=0.5 * support.capacity_fmol_s),
    )
    close(changed[1].synthesis_fmol_s, 0.5 * actual[1].synthesis_fmol_s, "rate_atol_fmol_s")
    assert not np.array_equal(changed[1].synthesis_fmol_s, actual[1].synthesis_fmol_s)


def test_jax_free_energy_gradients_match_potentials_and_volume_derivative():
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    n, volume, p = single()
    values = energy.thermodynamics(n, volume, p, xp=np)
    differentiate = jax.jit(
        jax.grad(
            lambda a, v: energy.thermodynamics(a, v, p).free_energy_pJ.sum(),
            argnums=(0, 1),
        )
    )
    amount_gradient, volume_gradient = differentiate(jnp.asarray(n), jnp.asarray(volume))
    close(amount_gradient, 1e-3 * values.chemical_potential_J_mol, "energy_atol_pJ")
    close(volume_gradient, values.volume_derivative_pJ_per_pL, "volume_derivative_atol_pJ_per_pL")
    n, volume, p = single((1.0, 1.0, 1000.0), 1.0, delta=-5000.0)
    route = energy.Routes(np.array([0]), np.array([True]))
    gradient = jax.jit(
        jax.grad(
            lambda work: energy.regeneration_rates(
                jnp.asarray(n),
                jnp.asarray(volume),
                p,
                route,
                energy.RegenerationParameters(0.4, work),
                0.6,
            ).synthesis_fmol_s.sum()
        )
    )(5000.0)
    close(gradient, 0.4 * 0.6 / (2 * R * 298.15), "rate_atol_fmol_s")


def test_jax_compiled_invalid_pool_and_port_predicates_reject_without_repair():
    import jax
    import jax.numpy as jnp

    jax.config.update("jax_enable_x64", True)
    n, volume, p = single()
    route = energy.Routes(np.array([0]), np.array([True]))

    def evaluate(amount, capacity, opening):
        return (
            energy.domain_valid(amount, jnp.asarray(volume), p),
            energy.regeneration_domain_valid(
                amount,
                jnp.asarray(volume),
                p,
                route,
                energy.RegenerationParameters(capacity, 80000.0),
                opening,
            ),
        )

    compiled = jax.jit(evaluate)
    for invalid in (0.0, -1.0, np.nan, np.inf):
        bad = n.copy()
        bad[0, 0] = invalid
        before = bad.copy()
        pool_ok, port_ok = compiled(jnp.asarray(bad), 0.0, 0.0)
        assert not pool_ok and not port_ok
        np.testing.assert_array_equal(bad, before)
    for capacity, opening in ((-1.0, 1.0), (0.4, -0.1), (0.4, 1.1), (1e308, 1.0)):
        pool_ok, port_ok = compiled(jnp.asarray(n), capacity, opening)
        assert pool_ok and not port_ok
    assert all(compiled(jnp.asarray(n), 0.4, 1.0))
