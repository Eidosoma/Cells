"""Independent finite-pool calcium contracts; CPU JAX prototypes select -k jax."""

import json
import math
import os
from pathlib import Path

import numpy as np
import pytest

from cells.processes import er_calcium, kinetic_pump, plasma_calcium
from cells.processes import finite_calcium_pumps as process
from cells.processes import finite_energy as energy
from cells.processes.electrochemistry import R
from validation.chemistry import finite_calcium_pump_reference as reference
from validation.chemistry import finite_energy_reference as pool_reference

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "validation/chemistry/finite_calcium_pump_protocol.json").read_text())
TOL = PROTOCOL["tolerances"]


def evidence(name, value):
    if directory := os.environ.get("CELLS_COMPONENT_EVIDENCE"):
        path = Path(directory) / "cpu"
        path.mkdir(parents=True, exist_ok=True)
        (path / ("finite-calcium-" + name + ".json")).write_text(
            json.dumps(value, indent=2, allow_nan=False) + "\n"
        )


def close(actual, expected, key="rate_atol_fmol_s"):
    np.testing.assert_allclose(actual, expected, rtol=TOL["relative"], atol=TOL[key])


def law(kind):
    return process.pmca_rates if kind == "pmca" else process.er_rates


def fixture():
    p = energy.validate_parameters(
        energy.Parameters(
            np.array([298.15, 310.0, 298.15]),
            np.array([-25000.0, 20000.0, 0.0]),
            np.array([True, True, False]),
        )
    )
    routes = energy.validate_routes(
        energy.Routes(
            np.array([0, 0, 1, 2]),
            np.array([True, True, True, False]),
        ),
        p,
    )
    pump = process.PumpParameters(
        np.array([0.003, 0.005, 0.002, 0]),
        np.array([0.001, 0.002, 0.003, 1]),
        np.array([0.5, 0.8, 0.2, 1]),
    )
    return dict(
        source=np.array([0.0002, 0.03, 0.005, 1]),
        destination=np.array([1, 0.01, 0.5, 1]),
        voltage=np.array([-0.04, 0.02, 0.01, 0]),
        amount=np.array([[3.0, 2.0, 0], [0.2, 0.4, 0], [0.3, 0.8, 0]]),
        volume=np.array([2.0, 3.0, 1.0]),
        p=p,
        routes=routes,
        pump=pump,
        availability=np.array([1.0, 0.3, 1.0, 0]),
    )


def single(*, delta=-37000.0, temperature=298.15):
    return dict(
        source=np.array([0.001]),
        destination=np.array([1.0]),
        voltage=np.array([-0.04]),
        amount=np.array([[3.0], [0.2], [0.3]]),
        volume=np.array([2.0]),
        p=energy.validate_parameters(energy.Parameters(temperature, delta, np.array([True]))),
        routes=energy.Routes(np.array([0]), np.array([True])),
        pump=process.PumpParameters(0.003, 0.001, 0.5),
        availability=np.array([1.0]),
    )


def scalar_oracle(f, i, kind):
    owner = int(f["routes"].owner[i])
    p, pump = f["p"], f["pump"]
    return reference.rates(
        f["source"][i],
        f["destination"][i],
        f["voltage"][i],
        f["amount"][:, owner],
        f["volume"][owner],
        np.broadcast_to(p.temperature_K, (len(p.active),))[owner],
        np.broadcast_to(p.delta_g0_J_mol, (len(p.active),))[owner],
        *(np.broadcast_to(v, (len(f["routes"].active),))[i] for v in pump),
        f["availability"][i],
        kind=kind,
    )


@pytest.mark.parametrize("kind", ["pmca", "er"])
@pytest.mark.parametrize(
    "temperature,delta,amount,volume,source,destination,voltage,availability",
    [
        (298.15, -37000, (3.0, 0.2, 0.3), 2.0, 0.001, 1.0, -0.05, 1.0),
        (310.0, 60000, (2.0, 0.4, 0.8), 3.0, 0.005, 0.5, 0.01, 0.4),
        (273.15, -10000, (1.0, 1.0, 1000.0), 1.0, 1.0, 1.0, 0.0, 1.0),
        (200.0, -25000, (0.8, 0.2, 0.2), 0.5, 0.02, 0.04, 0.12, 1.0),
        (400.0, -25000, (0.8, 0.2, 0.2), 2.0, 0.01, 0.1, -0.12, 1.0),
        (298.15, -37000, (3.0, 0.2, 0.3), 2.0, 0.001, 1.0, -0.05, 0.0),
    ],
)
def test_decimal_rates_energy_and_old_maintained_reduction(
    kind, temperature, delta, amount, volume, source, destination, voltage, availability
):
    f = single(delta=delta, temperature=temperature)
    f.update(
        amount=np.array(amount)[:, None],
        volume=np.array([volume]),
        source=np.array([source]),
        destination=np.array([destination]),
        voltage=np.array([voltage]),
        availability=np.array([availability]),
    )
    assert process.domain_valid(**f, kind=kind, xp=np)
    actual = law(kind)(**f, xp=np)
    expected = scalar_oracle(f, 0, kind)
    for name, value in actual._asdict().items():
        key = (
            "potential_atol_J_mol"
            if "energy_J_mol" in name
            else "power_atol_pJ_s"
            if "power" in name
            else "rate_atol_fmol_s"
        )
        close(value[0], expected[name], key)
    native = process.pump_parameters(
        f["amount"], f["volume"], f["p"], f["routes"], f["pump"], xp=np
    )
    close(native.delta_g0_J_per_mol[0], expected["legacy_delta_g0_J_mol"], "potential_atol_J_mol")
    old = plasma_calcium.pump_rates if kind == "pmca" else er_calcium.pump_rates
    old_result = old(
        f["source"], f["destination"], f["voltage"], temperature, native, f["availability"], xp=np
    )
    for value, legacy in zip(actual[:3], old_result, strict=True):
        np.testing.assert_array_equal(value, legacy)
    powers = (
        actual.pool_chemical_power_pJ_s,
        actual.transport_power_pJ_s,
        actual.dissipated_power_pJ_s,
    )
    rounding = 64 * np.finfo(float).eps * sum(np.abs(v) for v in powers)
    assert np.all(np.abs(sum(powers)) <= TOL["power_atol_pJ_s"] + rounding)
    assert np.all(actual.dissipated_power_pJ_s >= 0)


def test_one_molar_pool_gauge_and_nak_bridge_are_unchanged():
    f = fixture()
    before = energy.thermodynamics(f["amount"], f["volume"], f["p"], xp=np)
    delta = f["p"].delta_g0_J_mol.copy()
    native = process.pump_parameters(
        f["amount"], f["volume"], f["p"], f["routes"], f["pump"], xp=np
    )
    for i in range(3):
        owner = f["routes"].owner[i]
        close(
            er_calcium.chemical_drive(native, f["p"].temperature_K[f["routes"].owner], xp=np)[i],
            before.hydrolysis_free_energy_J_mol[owner],
            "potential_atol_J_mol",
        )
        assert native.delta_g0_J_per_mol[i] != delta[owner]
    template = kinetic_pump.Parameters(0.1, 1.5, 0.1, 0.1, 12.0, 0.2, 0.5, -37000.0)
    nak = energy.pump_parameters(f["amount"], f["volume"], f["p"], f["routes"], template, xp=np)
    np.testing.assert_array_equal(nak.delta_g0_J_mol[:3], delta[f["routes"].owner[:3]])
    np.testing.assert_array_equal(f["p"].delta_g0_J_mol, delta)
    after = energy.thermodynamics(f["amount"], f["volume"], f["p"], xp=np)
    for a, b in zip(before, after, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "conventions",
        dict(
            status="passed",
            finite_standard_mM=1000,
            legacy_standard_mM=1,
            shifted_calcium_delta=native.delta_g0_J_per_mol.tolist(),
            unchanged_owner_delta=delta.tolist(),
            nak_standard_unchanged=True,
        ),
    )


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_multiple_pmca_and_er_routes_share_finite_owner_once_with_signed_material_energy(kind):
    f = fixture()
    assert process.domain_valid(**f, kind=kind, xp=np)
    outputs = [law(k)(**f, xp=np) for k in ("pmca", "er")]
    rates = np.concatenate([o.cycles_fmol_s for o in outputs])
    routes = energy.Routes(np.tile(f["routes"].owner, 2), np.tile(f["routes"].active, 2))
    assert np.any(rates > 0) and np.any(rates < 0)
    exchanged = process.pool_exchange(rates, routes, f["p"], xp=np)
    expected = reference.exchange(
        rates[routes.active].tolist(), routes.owner[routes.active].tolist(), 3
    )
    close(exchanged.amount_fmol_s, expected["amount_fmol_s"], "material_atol_fmol")
    close(exchanged.pump_hydrolysis_fmol_s, expected["signed_hydrolysis_fmol_s"])
    # Both independent elemental invariants vanish for the exact signed reaction.
    close(exchanged.amount_fmol_s[0] + exchanged.amount_fmol_s[1], 0, "material_atol_fmol")
    close(
        3 * exchanged.amount_fmol_s[0]
        + 2 * exchanged.amount_fmol_s[1]
        + exchanged.amount_fmol_s[2],
        0,
        "material_atol_fmol",
    )
    ca = np.asarray(expected["calcium_source_destination_fmol_s"])
    close(ca.sum(axis=-1), 0, "material_atol_fmol")
    close(ca[:, 1], rates[routes.active], "material_atol_fmol")
    finite = energy.thermodynamics(f["amount"], f["volume"], f["p"], xp=np)
    pool_power = energy.chemical_power_pJ_s(exchanged.amount_fmol_s, finite, xp=np).sum()
    transport = sum(o.transport_power_pJ_s.sum() for o in outputs)
    heat = sum(o.dissipated_power_pJ_s.sum() for o in outputs)
    close(pool_power + transport + heat, 0, "power_atol_pJ_s")
    independent_pool = 0.0
    for owner in range(2):
        oracle = pool_reference.thermodynamics(
            f["amount"][:, owner],
            f["volume"][owner],
            f["p"].temperature_K[owner],
            f["p"].delta_g0_J_mol[owner],
        )
        independent_pool += 1e-3 * np.dot(
            oracle["chemical_potential_J_mol"], np.asarray(expected["amount_fmol_s"])[:, owner]
        )
    close(independent_pool, pool_power, "power_atol_pJ_s")
    evidence(
        "shared-owners-" + kind,
        dict(
            status="passed",
            route_cycles=rates.tolist(),
            owner_temperature_K=f["p"].temperature_K.tolist(),
            pool_amount_rate=exchanged.amount_fmol_s.tolist(),
            first_law_residual_pJ_s=float(pool_power + transport + heat),
            formal_Ca_per_ATP=1,
        ),
    )


def test_equal_opposite_cycles_have_zero_net_and_separate_gross_directional_counts():
    f = single()
    routes = energy.Routes(np.array([0, 0]), np.array([True, True]))
    actual = process.pool_exchange(np.array([0.2, -0.2]), routes, f["p"], xp=np)
    np.testing.assert_array_equal(actual.amount_fmol_s, np.zeros((3, 1)))
    close(actual.gross_hydrolysis_fmol_s, 0.2)
    close(actual.gross_synthesis_fmol_s, 0.2)
    assert process.CALCIUM_PER_CYCLE == process.ATP_PER_CYCLE == 1


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_stall_near_stall_reverse_and_voltage_orientation(kind):
    f = single(delta=0.0)
    f.update(
        source=np.ones(1),
        destination=np.ones(1),
        voltage=np.zeros(1),
        amount=np.array([[1.0], [1.0], [1000.0]]),
        volume=np.ones(1),
    )
    stalled = law(kind)(**f, xp=np)
    close(stalled.reaction_free_energy_J_mol, 0, "potential_atol_J_mol")
    close(stalled.cycles_fmol_s, 0)
    results = []
    for offset in (-1e-8, 1e-8):
        changed = f | {"destination": np.exp(np.array([offset]))}
        out = law(kind)(**changed, xp=np)
        assert np.sign(out.cycles_fmol_s[0]) == -np.sign(offset)
        assert out.dissipated_power_pJ_s[0] >= 0
        results.append(float(out.cycles_fmol_s[0]))
    voltage = f | {"voltage": np.array([0.01])}
    vout = law(kind)(**voltage, xp=np)
    assert np.sign(vout.cycles_fmol_s[0]) == (1 if kind == "pmca" else -1)
    counterpart = law("er" if kind == "pmca" else "pmca")(
        **(f | {"voltage": np.array([-0.01])}), xp=np
    )
    for a, b in zip(vout, counterpart, strict=True):
        np.testing.assert_array_equal(a, b)
    evidence(
        "stall-" + kind,
        dict(
            status="passed",
            near_stall_cycles=results,
            voltage_orientation_cycle=float(vout.cycles_fmol_s[0]),
        ),
    )


@pytest.mark.parametrize("kind", ["pmca", "er"])
@pytest.mark.parametrize("block", ["capacity", "availability"])
def test_block_is_exact_and_does_not_excuse_invalid_fuel(kind, block):
    f = single()
    if block == "capacity":
        f["pump"] = f["pump"]._replace(capacity_fmol_per_s=0.0)
    else:
        f["availability"] = np.zeros(1)
    assert process.domain_valid(**f, kind=kind, xp=np)
    result = law(kind)(**f, xp=np)
    for value in (result.cycles_fmol_s, *result[4:]):
        np.testing.assert_array_equal(value, np.zeros(1))
    f["amount"][0, 0] = 0
    assert not process.domain_valid(**f, kind=kind, xp=np)


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_padding_ordering_current_volume_and_empty_routes(kind):
    f = fixture()
    actual = law(kind)(**f, xp=np)
    for value in actual:
        assert value[-1] == 0
    native = process.pump_parameters(
        f["amount"], f["volume"], f["p"], f["routes"], f["pump"], xp=np
    )
    assert tuple(v[-1] for v in native) == (0, 1, 1, 1, 1, 1, 0)
    order = np.array([2, 3, 0, 1])
    perm = f | {k: f[k][order] for k in ("source", "destination", "voltage", "availability")}
    perm["routes"] = energy.Routes(*(v[order] for v in f["routes"]))
    perm["pump"] = process.PumpParameters(*(v[order] for v in f["pump"]))
    moved = law(kind)(**perm, xp=np)
    for a, b in zip(actual, moved, strict=True):
        close(a[order], b)
    close(
        process.pool_exchange(actual.cycles_fmol_s, f["routes"], f["p"], xp=np).amount_fmol_s,
        process.pool_exchange(moved.cycles_fmol_s, perm["routes"], f["p"], xp=np).amount_fmol_s,
    )
    volume = f["volume"].copy()
    volume[:2] /= 2
    new = law(kind)(**(f | {"volume": volume}), xp=np)
    close(
        new.hydrolysis_free_energy_J_mol[:3] - actual.hydrolysis_free_energy_J_mol[:3],
        R * f["p"].temperature_K[f["routes"].owner[:3]] * np.log(2),
        "potential_atol_J_mol",
    )
    empty = f | {k: np.empty(0) for k in ("source", "destination", "voltage", "availability")}
    empty["pump"] = process.PumpParameters(np.empty(0), np.empty(0), np.empty(0))
    empty["routes"] = energy.Routes(np.empty(0, dtype=int), np.empty(0, dtype=bool))
    assert process.domain_valid(**empty, kind=kind, xp=np)
    out = law(kind)(**empty, xp=np)
    assert all(v.shape == (0,) for v in out)
    np.testing.assert_array_equal(
        process.pool_exchange(out.cycles_fmol_s, empty["routes"], f["p"], xp=np).amount_fmol_s,
        np.zeros((3, 3)),
    )
    assert not process.domain_valid(**(empty | {"availability": np.nan}), kind=kind, xp=np)


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_actual_two_by_three_world_broadcast_and_explicit_population_axes(kind):
    f = fixture()
    amount = np.stack([f["amount"], f["amount"] * np.array([1.2, 0.9, 1])])[..., None, :, :]
    volume = np.stack(
        [f["volume"], f["volume"] * np.array([0.9, 1.1, 1]), f["volume"] * np.array([1.2, 0.8, 1])]
    )[None, ...]
    temperature = np.stack([f["p"].temperature_K, np.array([300.0, 312.0, 298.15])])[:, None, :]
    p = f["p"]._replace(temperature_K=temperature)
    source = f["source"][None, None, :] * np.array([1, 1.1, 0.9])[None, :, None]
    source[..., 3] = 1
    worlds = f | dict(amount=amount, volume=volume, p=p, source=source)
    assert process.domain_valid(**worlds, kind=kind, xp=np)
    output = law(kind)(**worlds, xp=np)
    assert all(v.shape == (2, 3, 4) for v in output)
    for i in range(2):
        for j in range(3):
            separate = f | dict(
                amount=amount[i, 0],
                volume=volume[0, j],
                p=p._replace(temperature_K=temperature[i, 0]),
                source=source[0, j],
            )
            for a, b in zip(output, law(kind)(**separate, xp=np), strict=True):
                close(a[i, j], b, "power_atol_pJ_s")
    one = single()
    assert not process.domain_valid(
        **(one | {"availability": np.array([0.1, 0.2, 0.3])}), kind=kind, xp=np
    )
    assert process.domain_valid(
        **(one | {"availability": np.array([[0.1], [0.2], [0.3]])}), kind=kind, xp=np
    )


@pytest.mark.parametrize(
    "field,value",
    [
        ("source", 0.0),
        ("source", -0.1),
        ("source", True),
        ("source", np.nan),
        ("destination", 0.0),
        ("destination", np.inf),
        ("voltage", 0.151),
        ("voltage", np.nan),
        ("availability", -0.1),
        ("availability", 1.1),
        ("availability", np.nan),
        ("availability", True),
        ("capacity_fmol_per_s", -0.1),
        ("capacity_fmol_per_s", np.inf),
        ("capacity_fmol_per_s", True),
        ("km_ca_mM", 0.0),
        ("km_ca_mM", -1.0),
        ("km_atp_mM", 0.0),
        ("km_atp_mM", np.nan),
    ],
)
def test_strict_invalid_route_fields(field, value):
    f = single()
    if field in f["pump"]._fields:
        f["pump"] = f["pump"]._replace(**{field: value})
    else:
        f[field] = value
    for kind in ("pmca", "er"):
        assert not process.domain_valid(**f, kind=kind, xp=np)


@pytest.mark.parametrize(
    "change",
    [
        "negative-owner",
        "large-owner",
        "float-owner",
        "matrix-owner",
        "nonbool-mask",
        "inactive-owner",
        "bad-padding",
        "empty-owner",
        "bad-amount-axis",
        "bad-temperature",
        "bad-delta",
        "exhaustion",
        "volume",
        "complex",
        "unknown-kind",
    ],
)
def test_invalid_ownership_pool_padding_and_shapes(change):
    f = fixture()
    kind = "pmca"
    if change in ("negative-owner", "large-owner", "float-owner", "matrix-owner"):
        owner = f["routes"].owner.copy()
        if change == "negative-owner":
            owner[0] = -1
        if change == "large-owner":
            owner[0] = 3
        if change == "float-owner":
            owner = owner.astype(float)
        if change == "matrix-owner":
            owner = owner[None, :]
        f["routes"] = f["routes"]._replace(owner=owner)
    elif change == "nonbool-mask":
        f["routes"] = f["routes"]._replace(active=np.ones(4))
    elif change == "inactive-owner":
        f["routes"] = f["routes"]._replace(active=np.ones(4, dtype=bool))
    elif change == "bad-padding":
        f["availability"][-1] = 0.1
    elif change == "empty-owner":
        f["p"] = f["p"]._replace(active=np.empty(0, dtype=bool))
    elif change == "bad-amount-axis":
        f["amount"] = np.ones((2, 3))
    elif change == "bad-temperature":
        f["p"] = f["p"]._replace(temperature_K=199.0)
    elif change == "bad-delta":
        f["p"] = f["p"]._replace(delta_g0_J_mol=np.nan)
    elif change == "exhaustion":
        f["amount"][2, 0] = 0
    elif change == "volume":
        f["volume"][0] = 0
    elif change == "complex":
        f["source"] = f["source"].astype(complex)
    elif change == "unknown-kind":
        kind = "ncx"
    assert not process.domain_valid(**f, kind=kind, xp=np)


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_affinity_and_power_limits_reject_even_with_finite_parameters(kind):
    f = single()
    f.update(
        source=np.ones(1),
        destination=np.ones(1),
        voltage=np.zeros(1),
        amount=np.array([[0.8], [0.2], [0.2]]),
        volume=np.ones(1),
    )
    rt = R * 298.15
    for opening in (0.0, 1.0):
        excessive = f | dict(
            p=f["p"]._replace(delta_g0_J_mol=rt * (81 - np.log(0.2 * 0.2 / (1000 * 0.8)))),
            availability=np.array([opening]),
        )
        assert not process.domain_valid(**excessive, kind=kind, xp=np)
    huge = f | dict(
        p=f["p"]._replace(delta_g0_J_mol=rt * (8 - np.log(0.2 * 0.2 / (1000 * 0.8)))),
        pump=process.PumpParameters(1e305, 1.0, 0.5),
    )
    with np.errstate(over="ignore"):
        out = law(kind)(**huge, xp=np)
    assert np.isfinite(out.cycles_fmol_s).all() and not np.isfinite(out.dissipated_power_pJ_s).all()
    assert not process.domain_valid(**huge, kind=kind, xp=np)


def manufactured_constants():
    depleted = (3 - math.sqrt(5)) / 2
    recovered = (33 - math.sqrt(65)) / 32
    depletion_tau = (0.5 + depleted) / (0.05 * (1 + 2 * (1 - depleted)))
    recovery_tau = 2 / (0.05 * (1 / recovered + 2 / (1 - recovered)))
    return depleted, recovered, depletion_tau, recovery_tau


def integrate_manufactured(steps, kind):
    depleted, recovered, tau_d, tau_r = manufactured_constants()
    f = single(delta=R * 298.15 * math.log(1000))
    f.update(
        source=np.ones(1),
        destination=np.ones(1),
        voltage=np.zeros(1),
        volume=np.ones(1),
        pump=process.PumpParameters(0.1, 1.0, 0.5),
    )
    initial = np.array([0.8, 0.2, 0.2])[:, None]
    # Independent reaction extents are state coordinates, not a pool projection.
    # State = pump extent, synthesis extent, pump heat, regeneration heat, work.
    y = np.zeros(5)
    output = []
    all_valid = True
    minimum_amount = math.inf
    supplied = energy.RegenerationParameters(0.05, R * 298.15 * math.log(16))
    for phase, seconds in enumerate((12 * tau_d, 12 * tau_r)):
        h = seconds / steps

        def derivative(state, phase=phase):
            nonlocal all_valid, minimum_amount
            amount = initial + np.array([-1.0, 1.0, 1.0])[:, None] * (state[0] - state[1])
            inputs = f | dict(amount=amount, availability=np.array([1.0 if phase == 0 else 0.0]))
            all_valid &= bool(process.domain_valid(**inputs, kind=kind, xp=np))
            minimum_amount = min(minimum_amount, float(amount.min()))
            pump = law(kind)(**inputs, xp=np)
            if phase == 1:
                regen = energy.regeneration_rates(
                    amount, f["volume"], f["p"], f["routes"], supplied, 1.0, xp=np
                )
                return np.array(
                    [
                        pump.cycles_fmol_s[0],
                        regen.synthesis_fmol_s[0],
                        pump.dissipated_power_pJ_s[0],
                        regen.dissipated_power_pJ_s[0],
                        regen.supplied_power_pJ_s[0],
                    ]
                )
            return np.array([pump.cycles_fmol_s[0], 0.0, pump.dissipated_power_pJ_s[0], 0.0, 0.0])

        for _ in range(steps):
            k1 = derivative(y)
            k2 = derivative(y + h * k1 / 2)
            k3 = derivative(y + h * k2 / 2)
            k4 = derivative(y + h * k3)
            y += h * (k1 + 2 * k2 + 2 * k3 + k4) / 6
        amount = initial + np.array([-1.0, 1.0, 1.0])[:, None] * (y[0] - y[1])
        free = energy.thermodynamics(amount, f["volume"], f["p"], xp=np).free_energy_pJ[0]
        initial_free = energy.thermodynamics(initial, f["volume"], f["p"], xp=np).free_energy_pJ[0]
        output.append(
            dict(
                ATP_fmol=float(amount[0, 0]),
                state=y.tolist(),
                first_law_residual_pJ=float(free - initial_free + y[2] + y[3] - y[4]),
            )
        )
    assert all_valid and minimum_amount > 0
    return output, minimum_amount


@pytest.mark.parametrize("kind", ["pmca", "er"])
def test_physical_time_depletion_stall_and_driven_recovery_with_independent_refinement(kind):
    depleted, recovered, tau_d, tau_r = manufactured_constants()
    expected = reference.manufactured_path(
        TOL["trajectory_reference_steps_per_phase"], 12 * tau_d, 12 * tau_r
    )
    runs = []
    for steps in TOL["trajectory_refinement_steps_per_phase"]:
        result, minimum = integrate_manufactured(steps, kind)
        error = max(abs(result[i]["ATP_fmol"] - expected[i]) for i in range(2))
        runs.append(
            dict(
                steps=steps,
                result=result,
                max_ATP_error_fmol=error,
                minimum_stage_amount_fmol=minimum,
            )
        )
    # Integrated power balance has a larger smooth error than a nearly stalled
    # endpoint. Its refinement is a useful whole-path accuracy check.
    errors = [max(abs(p["first_law_residual_pJ"]) for p in run["result"]) for run in runs]
    orders = [math.log2(a / b) for a, b in zip(errors, errors[1:], strict=False)]
    assert min(orders) >= TOL["minimum_rk4_order"]
    assert errors[-1] < TOL["trajectory_first_law_atol_pJ"]
    assert runs[-1]["max_ATP_error_fmol"] < 2e-7
    assert 0.8 - expected[0] > 0.4 and expected[1] - expected[0] > 0.39
    assert abs(expected[0] - depleted) < 1e-5 and abs(expected[1] - recovered) < 1e-5
    assert runs[-1]["result"][1]["state"][0] == runs[-1]["result"][0]["state"][0]
    evidence(
        "physical-time-" + kind,
        dict(
            status="passed",
            protocol=PROTOCOL["manufactured_path"],
            duration_seconds=[12 * tau_d, 12 * tau_r],
            relaxation_seconds=[tau_d, tau_r],
            equilibrium_ATP_fmol=[depleted, recovered],
            decimal_reference_ATP_fmol=expected,
            power_balance_orders=orders,
            runs=runs,
        ),
    )


def test_jax_eager_jit_vmap_arrays_controls_and_once_only_shared_exchange():
    import jax
    import jax.numpy as jnp

    f = fixture()

    def stage(amount, opening):
        values = process.pmca_rates(**(f | dict(amount=amount, availability=opening)))
        return (
            values,
            process.pool_exchange(values.cycles_fmol_s, f["routes"], f["p"]),
            process.domain_valid(**(f | dict(amount=amount, availability=opening)), kind="pmca"),
        )

    expected = stage(jnp.asarray(f["amount"]), jnp.asarray(f["availability"]))
    compiled = jax.jit(stage)
    actual = compiled(f["amount"], f["availability"])
    assert bool(actual[-1])
    for a, b in zip(jax.tree.leaves(actual), jax.tree.leaves(expected), strict=True):
        close(np.asarray(a), np.asarray(b), "power_atol_pJ_s")
    numpy_rates = process.pmca_rates(**f, xp=np)
    numpy_result = (
        numpy_rates,
        process.pool_exchange(numpy_rates.cycles_fmol_s, f["routes"], f["p"], xp=np),
        process.domain_valid(**f, kind="pmca", xp=np),
    )
    for a, b in zip(jax.tree.leaves(actual), jax.tree.leaves(numpy_result), strict=True):
        close(np.asarray(a), b, "power_atol_pJ_s")
    worlds = np.stack([f["amount"], f["amount"] * np.array([1.2, 0.9, 1])])
    batched = jax.jit(jax.vmap(stage, in_axes=(0, None)))(worlds, f["availability"])
    for i in range(2):
        separate = stage(worlds[i], f["availability"])
        for a, b in zip(jax.tree.leaves(batched), jax.tree.leaves(separate), strict=True):
            close(np.asarray(a)[i], np.asarray(b), "power_atol_pJ_s")
    bad = f["amount"].copy()
    bad[0, 0] = 0
    assert not bool(compiled(bad, np.zeros(4))[-1])
    assert not bool(compiled(f["amount"], np.full(4, np.nan))[-1])
    assert all(v.device.platform == "cpu" for v in jax.tree.leaves(actual))


def test_jax_finite_pool_gradient_bridge_stall_and_signed_energy_derivatives():
    import jax

    f = single(delta=0.0)
    f.update(
        source=np.ones(1),
        destination=np.ones(1),
        voltage=np.zeros(1),
        amount=np.array([[1.0], [1.0], [1000.0]]),
        volume=np.ones(1),
    )

    def stage(amount):
        result = process.er_rates(**(f | dict(amount=amount)))
        free = energy.thermodynamics(amount, f["volume"], f["p"]).free_energy_pJ.sum()
        return result, free

    result, free = jax.jit(stage)(f["amount"])
    close(result.cycles_fmol_s, 0)
    gradient = jax.jit(jax.grad(lambda n: stage(n)[1]))(f["amount"])
    chemical = energy.thermodynamics(
        f["amount"], f["volume"], f["p"], xp=np
    ).chemical_potential_J_mol
    close(gradient, 1e-3 * chemical, "power_atol_pJ_s")
    rate_jac = jax.jit(jax.jacrev(lambda n: stage(n)[0].cycles_fmol_s))(f["amount"])
    assert np.isfinite(rate_jac).all() and rate_jac[0, 0, 0] > 0 and rate_jac[0, 1, 0] < 0
    h = 1e-4
    for species in range(3):
        direction = np.zeros_like(f["amount"])
        direction[species, 0] = h
        plus = process.er_rates(**(f | dict(amount=f["amount"] + direction)), xp=np).cycles_fmol_s
        minus = process.er_rates(**(f | dict(amount=f["amount"] - direction)), xp=np).cycles_fmol_s
        np.testing.assert_allclose(
            rate_jac[0, species, 0], (plus - minus)[0] / (2 * h), rtol=2e-7, atol=1e-12
        )
    temperature_case = single()

    def chemical_drive(t):
        inputs = temperature_case | {"p": temperature_case["p"]._replace(temperature_K=t)}
        return process.er_rates(**inputs).hydrolysis_free_energy_J_mol[0]

    dT = jax.jit(jax.grad(chemical_drive))(298.15)
    close(dT, R * math.log(0.1 * 0.15 / (1000 * 1.5)), "potential_atol_J_mol")
    assert math.isfinite(float(free))
