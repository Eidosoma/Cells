"""Manufactured physical contracts; source probes and CPU JAX are separate."""

import json
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import cotransport as transport
from cells.processes.electrochemistry import CHARGE_PER_FMOL, R
from validation.transport import cotransport_reference as reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/transport/cotransport_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]
EVIDENCE = os.environ.get("CELLS_COMPONENT_EVIDENCE")
BACKEND = os.environ.get("CELLS_COMPONENT_BACKEND", "cpu")
IDS = ("Na", "K", "Cl")
Z = np.array([1, 1, -1])
LAWS = (transport.KCC_LAW_ID, transport.NKCC_LAW_ID)


def evidence(name, value, arrays=None):
    if EVIDENCE:
        path = Path(EVIDENCE) / BACKEND
        path.mkdir(parents=True, exist_ok=True)
        if arrays is not None:
            np.savez(path / ("cotransport-manufactured-" + name + ".npz"), **arrays)
        (path / ("cotransport-manufactured-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def close(actual, expected, key):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def single(law=transport.KCC_LAW_ID, temperature=298.15, capacity=2.0):
    nu = transport.named_stoichiometry(IDS, Z, law)[:, None]
    t = transport.validate_topology(
        transport.Topology(Z, np.ones(2, bool), np.array([0]), np.array([1]), nu, np.ones(1, bool))
    )
    p = transport.validate_parameters(transport.Parameters(capacity, temperature), t)
    return t, p


def shared():
    kcc = transport.named_stoichiometry(IDS, Z, LAWS[0])
    nkcc = transport.named_stoichiometry(IDS, Z, LAWS[1])
    t = transport.validate_topology(
        transport.Topology(
            Z,
            np.array([True, True, True, False]),
            np.array([0, 0, 2, 3]),
            np.array([1, 2, 1, 3]),
            np.stack((kcc, nkcc, kcc, np.zeros(3, np.int64)), axis=1),
            np.array([True, True, True, False]),
        )
    )
    p = transport.validate_parameters(
        transport.Parameters(np.array([2.0, 3.0, 0.5, 0.0]), 298.15), t
    )
    c = np.array([[12.0, 145.0, 30.0, 0.0], [140.0, 4.0, 20.0, 0.0], [10.0, 120.0, 40.0, 0.0]])
    return c, t, p, np.array([0.8, 0.6, 0.9, 0.0])


@pytest.mark.parametrize("law", LAWS)
@pytest.mark.parametrize("order", [(0, 1, 2), (2, 0, 1)])
def test_named_roles_bind_actual_species_and_zero_charge(law, order):
    ids, z = tuple(IDS[i] for i in order), Z[list(order)]
    nu = transport.named_stoichiometry(ids, z, law)
    expected = PROTOCOL["named_laws"][law]
    assert dict(zip(ids, nu.tolist(), strict=True)) == {s: expected.get(s, 0) for s in ids}
    assert int(z @ nu) == 0


@pytest.mark.parametrize(
    ("ids", "z", "law"),
    [
        (("K", "Cl"), [1, -1], "unknown@1"),
        (("K", "K", "Cl"), [1, 1, -1], LAWS[0]),
        (("K", "Cl"), [1, 1], LAWS[0]),
        (("Na", "K", "Cl"), [2, 1, -1], LAWS[1]),
        (("Na", "K", "Cl"), [1, 2, -1], LAWS[1]),
        (("K", "Cl"), [1, -1], LAWS[1]),
        (("Na", "K"), [1, 1], LAWS[1]),
        (("K", "Cl"), [1.0, -1.0], LAWS[0]),
        (("K", "Cl"), [True, False], LAWS[0]),
        (("", "K", "Cl"), [1, 1, -1], LAWS[0]),
    ],
)
def test_named_role_aliases_wrong_valences_and_missing_species_rejected(ids, z, law):
    with pytest.raises(ValueError):
        transport.named_stoichiometry(ids, z, law)


CASES = (
    ("physiological-gradient", [12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 2.0, 0.8),
    ("reverse-gradient", [145.0, 4.0, 120.0], [12.0, 140.0, 10.0], 310.0, 2.0, 0.8),
    ("stall", [4.0, 8.0, 16.0], [4.0, 8.0, 16.0], 298.15, 2.0, 1.0),
    ("near-stall", [4.0, 8.0, 16.0], [4.0, 8.0000000008, 16.0], 298.15, 2.0, 1.0),
    ("lower-temperature", [2.0, 4.0, 8.0], [8.0, 16.0, 32.0], 200.0, 2.0, 1.0),
    ("upper-temperature", [2.0, 4.0, 8.0], [8.0, 16.0, 32.0], 400.0, 2.0, 1.0),
    ("blocked", [12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 2.0, 0.0),
    ("zero-capacity", [12.0, 140.0, 10.0], [145.0, 4.0, 120.0], 298.15, 0.0, 1.0),
    ("extreme-positive", [1e-300, 1e-300, 1e-300], [1e300, 1e300, 1e300], 298.15, 2.0, 1.0),
)


@pytest.mark.parametrize("law", LAWS)
@pytest.mark.parametrize(
    ("name", "ci", "co", "temperature", "capacity", "opening"), CASES, ids=[v[0] for v in CASES]
)
def test_decimal_stall_forward_reverse_and_log_domain(
    law, name, ci, co, temperature, capacity, opening
):
    t, p = single(law, temperature, capacity)
    c = np.stack((ci, co), axis=-1)
    assert transport.domain_valid(c, t, p, opening, xp=np)
    actual = transport.rates(c, t, p, opening, xp=np)
    stem = law.split("_")[0] + "-" + name
    record = dict(
        kind="manufactured-tanh-contract",
        status="actual_captured",
        law=law,
        inputs=dict(
            inside_mM=ci,
            outside_mM=co,
            temperature_K=temperature,
            capacity_fmol_s=capacity,
            availability=opening,
        ),
    )
    arrays = {key: np.asarray(value) for key, value in actual._asdict().items()}
    evidence(stem, record, arrays)
    expected = reference.cycle(
        ci, co, t.stoichiometry[:, 0].tolist(), capacity, opening, temperature
    )
    record.update(status="captured", expected=expected)
    evidence(stem, record)
    for field in actual._fields:
        key = (
            "affinity_atol_J_mol"
            if "J_mol" in field
            else "power_atol_pJ_s"
            if "power" in field
            else "charge_atol_C"
            if "charge" in field
            else "rate_atol_fmol_s"
        )
        close(np.asarray(getattr(actual, field))[..., 0], expected[field], key)
    assert np.all(actual.dissipated_power_pJ_s >= 0)
    close(actual.chemical_power_pJ_s + actual.dissipated_power_pJ_s, 0, "power_atol_pJ_s")
    assert np.all(actual.direct_charge_C_s == 0)
    if name == "physiological-gradient":
        assert np.sign(actual.cycle_fmol_s[0]) == (-1 if law == LAWS[0] else 1)
    if name == "stall":
        assert np.all(actual.cycle_fmol_s == 0) and np.all(actual.affinity_J_mol == 0)
    record["status"] = "passed"
    evidence(stem, record)


@pytest.mark.parametrize("law", LAWS)
def test_unequal_concentrations_can_have_equal_product_and_stall(law):
    t, p = single(law)
    # Na is unused for KCC; NKCC compensates its Na gradient with K.
    ci = [4.0, 8.0, 4.0]
    co = [4.0, 4.0, 8.0] if law == LAWS[0] else [8.0, 4.0, 4.0]
    result = transport.rates(np.stack((ci, co), axis=-1), t, p, 1.0, xp=np)
    close(result.affinity_J_mol, 0, "affinity_atol_J_mol")
    close(result.cycle_fmol_s, 0, "rate_atol_fmol_s")


def test_shared_source_sink_ownership_signed_cycles_and_padding_match_scalar_loops():
    c, t, p, opening = shared()
    assert transport.domain_valid(c, t, p, opening, xp=np)
    cycles = np.array([0.7, -1.1, 0.25, 0.0])
    assert transport.exchange_domain_valid(cycles, t, xp=np)
    actual = transport.exchange_rates(cycles, t, xp=np)
    expected = reference.exchange(
        cycles.tolist(), t.inside.tolist(), t.outside.tolist(), t.stoichiometry.tolist(), 4
    )
    evidence(
        "ownership",
        dict(
            status="captured",
            kind="manufactured-owner-contract",
            cycles=cycles.tolist(),
            inside=t.inside.tolist(),
            outside=t.outside.tolist(),
            expected=expected,
        ),
        actual._asdict(),
    )
    close(actual.amount_fmol_s, expected, "rate_atol_fmol_s")
    close(actual.amount_fmol_s.sum(axis=-1), 0, "rate_atol_fmol_s")
    close(Z @ actual.amount_fmol_s, 0, "rate_atol_fmol_s")
    assert np.all(actual.amount_fmol_s[:, 3] == 0)
    # Both routes touching owner 0 are counted once, including reverse demand.
    close(
        actual.amount_fmol_s[:, 0],
        t.stoichiometry[:, 0] * cycles[0] + t.stoichiometry[:, 1] * cycles[1],
        "rate_atol_fmol_s",
    )
    evidence(
        "ownership", dict(status="passed", kind="manufactured-owner-contract", expected=expected)
    )


def test_world_axes_broadcast_real_concentrations_controls_capacities_and_temperatures():
    c, t, p, a = shared()
    concentrations = np.stack((c, c * np.array([1.2, 0.7, 1.6, 1.0])))[:, None, :, :]
    capacities = np.stack((p.capacity_fmol_s, p.capacity_fmol_s * 0.7, p.capacity_fmol_s * 1.3))[
        None, :, :
    ]
    temperatures = np.array([200.0, 400.0])[:, None, None]
    opening = np.broadcast_to(a, (2, 3, 4)).copy()
    opening[0, 1, 0] = 0
    opening[1, 2, 1] = 0.2
    params = transport.validate_parameters(transport.Parameters(capacities, temperatures), t)
    assert transport.domain_valid(concentrations, t, params, opening, xp=np)
    result = transport.rates(concentrations, t, params, opening, xp=np)
    assert result.cycle_fmol_s.shape == (2, 3, 4)
    assert result.transported_fmol_s.shape == (2, 3, 3, 4)
    exchange = transport.exchange_rates(result.cycle_fmol_s, t, xp=np)
    assert exchange.amount_fmol_s.shape == (2, 3, 3, 4)
    evidence(
        "worlds",
        dict(status="actual_captured", shape=list(result.cycle_fmol_s.shape)),
        result._asdict(),
    )
    for i in range(2):
        for j in range(3):
            for route in range(3):
                expected = reference.cycle(
                    concentrations[i, 0, :, t.inside[route]].tolist(),
                    concentrations[i, 0, :, t.outside[route]].tolist(),
                    t.stoichiometry[:, route].tolist(),
                    float(capacities[0, j, route]),
                    float(opening[i, j, route]),
                    float(temperatures[i, 0, 0]),
                )
                close(
                    result.cycle_fmol_s[i, j, route], expected["cycle_fmol_s"], "rate_atol_fmol_s"
                )
                close(
                    result.dissipated_power_pJ_s[i, j, route],
                    expected["dissipated_power_pJ_s"],
                    "power_atol_pJ_s",
                )
            expected_exchange = reference.exchange(
                result.cycle_fmol_s[i, j].tolist(),
                t.inside.tolist(),
                t.outside.tolist(),
                t.stoichiometry.tolist(),
                4,
            )
            close(exchange.amount_fmol_s[i, j], expected_exchange, "rate_atol_fmol_s")
    evidence("worlds", dict(status="passed", shape=[2, 3, 4], independent_worlds=6))


def test_independent_controls_do_not_change_other_routes_or_instantaneously_change_ions():
    c, t, p, a = shared()
    original = c.copy()
    before = transport.rates(c, t, p, a, xp=np)
    a[1] = 0
    after = transport.rates(c, t, p, a, xp=np)
    assert after.cycle_fmol_s[1] == 0
    np.testing.assert_array_equal(before.cycle_fmol_s[[0, 2, 3]], after.cycle_fmol_s[[0, 2, 3]])
    np.testing.assert_array_equal(c, original)


def test_compartment_and_species_relabelling_preserve_physical_routes():
    c, t, p, a = shared()
    before = transport.rates(c, t, p, a, xp=np)
    species_order, compartment_order = np.array([2, 0, 1]), np.array([2, 0, 3, 1])
    inverse = np.argsort(compartment_order)
    changed = transport.validate_topology(
        t._replace(
            species_valence=t.species_valence[species_order],
            compartment_active=t.compartment_active[compartment_order],
            inside=inverse[t.inside],
            outside=inverse[t.outside],
            stoichiometry=t.stoichiometry[species_order],
        )
    )
    after = transport.rates(c[species_order][:, compartment_order], changed, p, a, xp=np)
    close(after.cycle_fmol_s, before.cycle_fmol_s, "rate_atol_fmol_s")
    original = transport.exchange_rates(before.cycle_fmol_s, t, xp=np).amount_fmol_s
    reordered = transport.exchange_rates(after.cycle_fmol_s, changed, xp=np).amount_fmol_s
    close(reordered, original[species_order][:, compartment_order], "rate_atol_fmol_s")


def test_material_replay_reconstructs_every_species_and_detects_neutral_corruption():
    c, t, _, _ = shared()
    initial = c + np.array([1.0, 2.0, 3.0, 0.0])
    integrals = np.array([[0.1, -0.2, 0.05, 0.0], [-0.3, 0.1, 0.2, 0.0]])
    current = initial + np.asarray(
        [
            reference.exchange(
                v.tolist(), t.inside.tolist(), t.outside.tolist(), t.stoichiometry.tolist(), 4
            )
            for v in integrals
        ]
    )
    good = transport.material_balances(initial, current, integrals, t, xp=np)
    for name, field in good._asdict().items():
        close(field, 0, "charge_atol_C" if "charge" in name else "material_atol_fmol")
    current[0, 1, 0] += 0.03
    current[0, 2, 0] += (
        0.03  # Electrically neutral KCl corruption still violates per-species evidence.
    )
    bad = transport.material_balances(initial, current, integrals, t, xp=np)
    assert np.max(np.abs(bad.amount_residual_fmol)) > 0.02
    assert np.max(np.abs(bad.species_total_residual_fmol)) > 0.02
    close(bad.compartment_charge_residual_C, 0, "charge_atol_C")


@pytest.mark.parametrize("law", LAWS)
def test_finite_chemical_free_energy_derivative_equals_minus_heat(law):
    t, p = single(law)
    c = np.array([[12.0, 145.0], [140.0, 4.0], [10.0, 120.0]])
    volumes = np.array([2.0, 3.0])
    n = c * volumes
    result = transport.rates(c, t, p, 0.8, xp=np)
    derivative = transport.exchange_rates(result.cycle_fmol_s, t, xp=np).amount_fmol_s
    h = 1e-4 / np.max(np.abs(derivative) / n)
    minus, plus = n - h * derivative, n + h * derivative
    finite_difference = reference.chemical_free_energy_change(
        minus.tolist(), plus.tolist(), volumes.tolist(), 298.15
    ) / (2 * h)
    third_bound = (
        1e-3 * R * 298.15 * np.sum(np.abs(derivative) ** 3 / (n - h * np.abs(derivative)) ** 2)
    )
    scale = 1e-3 * R * 298.15 * np.sum(n * (np.abs(np.log(c / 1000)) + 1))
    bound = h**2 * third_bound / 6 + 32 * np.finfo(float).eps * scale / h
    heat = float(np.sum(result.dissipated_power_pJ_s))
    evidence(
        "chemical-energy-" + law.split("_")[0],
        dict(
            status="captured",
            finite_difference_pJ_s=finite_difference,
            heat_pJ_s=heat,
            independent_difference_error_bound=bound,
        ),
    )
    assert abs(finite_difference + heat) <= bound
    close(CHARGE_PER_FMOL * Z @ derivative, 0, "charge_atol_C")
    evidence(
        "chemical-energy-" + law.split("_")[0],
        dict(
            status="passed",
            finite_difference_pJ_s=finite_difference,
            heat_pJ_s=heat,
            independent_difference_error_bound=bound,
        ),
    )


@pytest.mark.parametrize("bad", [0.0, -1.0, np.nan, np.inf])
@pytest.mark.parametrize("blocking", ["control", "capacity"])
def test_bad_active_substrate_rejected_even_when_route_blocked(bad, blocking):
    t, p = single(capacity=0 if blocking == "capacity" else 2)
    c = np.ones((3, 2))
    c[0, 1] = bad  # Even the unused Na species is an active declared compartment substrate.
    assert not transport.domain_valid(c, t, p, 0.0 if blocking == "control" else 1.0, xp=np)


@pytest.mark.parametrize(
    "field",
    ["species_valence", "compartment_active", "inside", "outside", "stoichiometry", "active"],
)
def test_topology_wrong_types_and_axes_rejected(field):
    _, t, _, _ = shared()
    value = np.asarray(getattr(t, field))
    invalid = t._replace(
        **{field: value.astype(float) if value.dtype.kind != "f" else value[:, None]}
    )
    with pytest.raises(ValueError):
        transport.validate_topology(invalid)


@pytest.mark.parametrize(
    "failure",
    [
        "unsafe_in",
        "unsafe_out",
        "same_owner",
        "inactive_owner",
        "charge",
        "padding",
        "negative",
        "empty_cycle",
    ],
)
def test_topology_bad_ownership_charge_and_padding_rejected(failure):
    c, t, p, a = shared()
    if failure == "unsafe_in":
        t = t._replace(inside=np.array([-1, 0, 2, 3]))
    elif failure == "unsafe_out":
        t = t._replace(outside=np.array([4, 2, 1, 3]))
    elif failure == "same_owner":
        t = t._replace(outside=np.array([0, 2, 1, 3]))
    elif failure == "inactive_owner":
        t = t._replace(inside=np.array([3, 0, 2, 3]))
    else:
        nu = t.stoichiometry.copy()
        nu[1, 0] = {"charge": 2, "padding": 1, "negative": -1, "empty_cycle": 0}[failure]
        if failure == "padding":
            nu[:, 3] = nu[:, 0]
        if failure == "empty_cycle":
            nu[:, 0] = 0
        t = t._replace(stoichiometry=nu)
    with pytest.raises(ValueError):
        transport.validate_topology(t)
    assert not transport.domain_valid(c, t, p, a, xp=np)


@pytest.mark.parametrize("capacity", [-1.0, np.inf, np.nan, True])
def test_invalid_capacity_rejected_by_host_and_trial_predicate(capacity):
    t, _ = single()
    p = transport.Parameters(capacity, 298.15)
    with pytest.raises(ValueError):
        transport.validate_parameters(p, t)
    assert not transport.domain_valid(np.ones((3, 2)), t, p, 1.0, xp=np)


@pytest.mark.parametrize("temperature", [199.9, 400.1, np.nan, np.inf, True, [298.15, 310.0]])
def test_invalid_or_route_varying_temperature_rejected(temperature):
    t, _ = single()
    p = transport.Parameters(2.0, temperature)
    with pytest.raises(ValueError):
        transport.validate_parameters(p, t)
    assert not transport.domain_valid(np.ones((3, 2)), t, p, 1.0, xp=np)


@pytest.mark.parametrize("opening", [-0.1, 1.1, np.nan, np.inf, True, np.ones(2)])
def test_invalid_controls_and_route_shapes_rejected(opening):
    t, p = single()
    assert not transport.domain_valid(np.ones((3, 2)), t, p, opening, xp=np)


@pytest.mark.parametrize(
    "concentration",
    [np.ones((2, 3)), np.ones((3,)), np.ones((3, 2), bool), np.ones((3, 2), complex)],
)
def test_wrong_concentration_axes_and_nonreal_types_rejected(concentration):
    t, p = single()
    assert not transport.domain_valid(concentration, t, p, 1.0, xp=np)


@pytest.mark.parametrize("failure", ["concentration", "capacity", "availability", "cycle"])
def test_padding_is_exactly_neutral_in_state_parameters_controls_and_cycles(failure):
    c, t, p, a = shared()
    cycles = np.zeros(4)
    if failure == "concentration":
        c[0, 3] = 1
    elif failure == "capacity":
        cap = p.capacity_fmol_s.copy()
        cap[3] = 1
        p = p._replace(capacity_fmol_s=cap)
    elif failure == "availability":
        a[3] = 1
    else:
        cycles[3] = 1
    assert not (
        transport.exchange_domain_valid(cycles, t, xp=np)
        if failure == "cycle"
        else transport.domain_valid(c, t, p, a, xp=np)
    )


def test_empty_routes_preserve_compartment_domain_and_all_leading_worlds():
    t, _ = single()
    t = transport.validate_topology(
        t._replace(
            inside=np.zeros(0, np.int64),
            outside=np.zeros(0, np.int64),
            stoichiometry=np.zeros((3, 0), np.int64),
            active=np.zeros(0, bool),
        )
    )
    p = transport.validate_parameters(transport.Parameters(np.zeros(0), 298.15), t)
    c = np.ones((2, 3, 2))
    assert transport.domain_valid(c, t, p, np.zeros(0), xp=np)
    r = transport.rates(c, t, p, np.zeros(0), xp=np)
    assert r.cycle_fmol_s.shape == (2, 0) and r.transported_fmol_s.shape == (2, 3, 0)
    exchange = transport.exchange_rates(r.cycle_fmol_s, t, xp=np)
    assert exchange.amount_fmol_s.shape == (2, 3, 2) and np.all(exchange.amount_fmol_s == 0)
    assert not transport.domain_valid(c, t, p._replace(temperature_K=np.nan), np.zeros(0), xp=np)
    c[1, 0, 0] = 0
    assert not transport.domain_valid(c, t, p, np.zeros(0), xp=np)


def test_all_inactive_layout_has_zero_material_and_heat_without_log_zero():
    t = transport.validate_topology(
        transport.Topology(
            Z,
            np.zeros(2, bool),
            np.array([0]),
            np.array([0]),
            np.zeros((3, 1), np.int64),
            np.zeros(1, bool),
        )
    )
    p = transport.validate_parameters(transport.Parameters(0.0, 298.15), t)
    with np.errstate(all="raise"):
        assert transport.domain_valid(np.zeros((3, 2)), t, p, 0.0, xp=np)
        result = transport.rates(np.zeros((3, 2)), t, p, 0.0, xp=np)
    for value in result:
        assert np.isfinite(value).all() and np.all(value == 0)


def test_nonfinite_power_or_assembled_material_rejects_without_repair():
    t, p = single(capacity=1e308)
    c = np.array([[1.0, 1.0], [1e-300, 1e300], [1e-300, 1e300]])
    with np.errstate(over="ignore", invalid="ignore"):
        assert not transport.domain_valid(c, t, p, 1.0, xp=np)
        assert not transport.exchange_domain_valid(np.array([np.inf]), t, xp=np)
    assert not transport.exchange_domain_valid(np.array([True]), t, xp=np)


def test_jax_eager_jit_vmap_and_real_world_broadcasts():
    import jax
    import jax.numpy as jnp

    assert jax.default_backend() == "cpu" and jax.config.x64_enabled
    c, t, p, a = shared()
    worlds = np.stack((c, c * np.array([1.1, 0.8, 1.4, 1.0])))[:, None, :, :]
    capacities = np.stack((p.capacity_fmol_s, p.capacity_fmol_s * 0.7, p.capacity_fmol_s * 1.3))[
        None, :, :
    ]
    temperatures = np.array([200.0, 400.0])[:, None, None]
    opening = np.broadcast_to(a, (2, 3, 4)).copy()
    opening[0, 1, 0] = 0
    params = transport.Parameters(capacities, temperatures)
    expected = transport.rates(worlds, t, params, opening, xp=np)
    compiled = jax.jit(transport.rates)(jnp.asarray(worlds), t, params, opening)
    eager = transport.rates(jnp.asarray(worlds), t, params, opening)
    mapped = jax.jit(
        jax.vmap(
            lambda x, temp, control: transport.rates(
                x, t, transport.Parameters(capacities[0], temp), control
            )
        )
    )(jnp.asarray(worlds), jnp.asarray(temperatures), jnp.asarray(opening))
    for actual in (compiled, eager, mapped):
        for field in actual._fields:
            close(
                np.asarray(getattr(actual, field)),
                getattr(expected, field),
                "affinity_atol_J_mol"
                if "J_mol" in field
                else "power_atol_pJ_s"
                if "power" in field
                else "charge_atol_C"
                if "charge" in field
                else "rate_atol_fmol_s",
            )
    compiled_exchange = jax.jit(transport.exchange_rates)(compiled.cycle_fmol_s, t)
    close(
        np.asarray(compiled_exchange.amount_fmol_s),
        transport.exchange_rates(expected.cycle_fmol_s, t, xp=np).amount_fmol_s,
        "rate_atol_fmol_s",
    )
    evidence(
        "jax-array-contract",
        dict(status="passed", backend=jax.default_backend(), world_shape=[2, 3]),
    )


@pytest.mark.parametrize("law", LAWS)
def test_jax_stall_derivative_and_chemical_gradient(law):
    import jax
    import jax.numpy as jnp

    t, p = single(law)
    c = jnp.ones((3, 2)) * 10
    nu = t.stoichiometry[:, 0]
    derivative = jax.jit(jax.grad(lambda x: transport.rates(x, t, p, 0.8).cycle_fmol_s[0]))(c)
    expected = np.stack((-0.8 * nu / 10, 0.8 * nu / 10), axis=-1)
    close(np.asarray(derivative), expected, "rate_atol_fmol_s")
    volumes = jnp.array([2.0, 3.0])
    amounts = jnp.array([[12.0, 145.0], [140.0, 4.0], [10.0, 120.0]]) * volumes

    def free(n):
        return 1e-3 * R * 298.15 * jnp.sum(n * (jnp.log(n / (volumes * 1000)) - 1))

    mu = jax.jit(jax.grad(free))(amounts)
    result = jax.jit(transport.rates)(amounts / volumes, t, p, 0.8)
    delta = jax.jit(transport.exchange_rates)(result.cycle_fmol_s, t).amount_fmol_s
    close(
        np.asarray(jnp.sum(mu * delta)),
        -np.sum(np.asarray(result.dissipated_power_pJ_s)),
        "power_atol_pJ_s",
    )


def test_jax_invalid_trial_predicates_and_empty_route_exchange():
    import jax
    import jax.numpy as jnp

    c, t, p, a = shared()
    valid = jax.jit(transport.domain_valid)
    assert bool(valid(c, t, p, a))
    bad = c.copy()
    bad[1, 0] = 0
    assert not bool(valid(bad, t, p, np.zeros(4)))
    assert not bool(valid(c, t._replace(inside=np.array([-1, 0, 2, 3])), p, a))
    assert not bool(valid(c, t, p._replace(temperature_K=np.nan), a))
    assert not bool(valid(c, t, p, np.ones(4)))  # Nonzero inactive control.
    empty = transport.validate_topology(
        t._replace(
            inside=np.zeros(0, np.int64),
            outside=np.zeros(0, np.int64),
            stoichiometry=np.zeros((3, 0), np.int64),
            active=np.zeros(0, bool),
        )
    )
    ep = transport.validate_parameters(transport.Parameters(np.zeros(0), 298.15), empty)
    assert bool(valid(c, empty, ep, jnp.zeros(0)))
    result = jax.jit(transport.exchange_rates)(jnp.zeros((2, 0)), empty)
    assert result.amount_fmol_s.shape == (2, 3, 4)
    assert np.all(np.asarray(result.amount_fmol_s) == 0)
    predicate = jax.jit(transport.exchange_domain_valid)
    assert not bool(predicate(jnp.array([0.0, 0.0, 0.0, 1.0]), t))
